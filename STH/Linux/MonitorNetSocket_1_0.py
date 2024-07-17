
'''
Created on 2024-02-27 17:27:37

@author: MilkTea_shih
'''

# In[0]:
version: str = 'MonitorNetSocket v1.0'

#%%    Packages
import collections
import copy
import functools
import itertools

#import logging
import os
import threading
import time

from typing import Any, Callable, Deque, Iterator, Optional, Sequence
from typing import TypeVar, cast

PacketHistoryDetailFormat = tuple[tuple[list[Iterator[int]],  #history
                                  dict[int, int]],  #duplicate_packet
                                  set[int]]  #all_loss_index
T = TypeVar('T')
DefaultType = TypeVar('DefaultType')

from MonitorSysUsage_1_0 import ProcessUsage
from MonitorSysUsage_1_0 import ProcessUsageReturnFormat, UsageFormat
from MonitorSysUsage_1_0 import MINIMA_INTERVAL
#MINIMA_INTERVAL = 0.1

#%%    Variable
MINIMA_PACKET_LOSS_LENGTH: int = 2
PACKET_LOSS_OUTPUT_DIGITS: int = 3

#%%    Functions
def SetLogging(**kwargs):
    #TODO: write a function to log information or error/warning
    import logging
    logging.basicConfig(**kwargs)

def convert_input(max_number: int, flag: bool
                  ) -> Callable[[Sequence[int]], tuple[bool, ...]]:
    def convert_input_setter(numbers: Sequence[int]
                             ) -> tuple[bool, ...]:
        number_set: set[int] = set(numbers)

        def condition(number: int) -> bool:
            return number in number_set if flag \
                else not (number in number_set)
        return tuple(map(condition, range(max_number)))
    return convert_input_setter

def test_input_checker(func: Callable | Sequence
                       ) -> Callable[[int], Sequence[int]]:
    def print_test_input(number: int
                         ) -> Sequence[int]:
        test_list: Sequence[int] = func if isinstance(func, Sequence) \
            else tuple(func(number))
        print(f'''{test_list = }
              \r{len(test_list) = }
              
              \rExpected packet loss rate: {(number - len(test_list)) 
              / number: .{PACKET_LOSS_OUTPUT_DIGITS}f}
              ''')

        return test_list

    return print_test_input

def assert_type(arg_type: type
                ) -> Callable[[Callable],
                              Callable[[DefaultType | type], Any]]:
    def decorator(func: Callable
                  ) -> Callable[[DefaultType],
                                Callable[[DefaultType | type], Any]]:
        table: dict = {
            Iterator: iter,
            Sequence: list,
            int: int,
            float: float,
            str: str
        }
        def wrap(arg: DefaultType
                 ) -> Callable[[DefaultType | type], Any]:
            converted: DefaultType | type
            if not isinstance(arg, arg_type):
                try:
                    converted = table[arg_type](arg)
                except KeyError:
                    print(f"{arg_type} not in {table.keys()}")
                except Exception as error:
                    print(error)
                else:
                    return func(converted)
            return func(arg)

        return wrap
    return decorator

def print_information(func: Callable) -> Callable:
    def wrap(arg, *args) -> None:
        if args:
            printer(f"[{func(arg):0<5}]:  ")
            printer(args)
        else:
            func(arg)

    @assert_type(Iterator)
    def printer(arg: Iterator) -> None:
        try:
            temp: Any = arg.__next__()
        except StopIteration:
            pass
        else:
            #print(temp, end='', flush=True)
            printer(arg)

    return wrap

def round_number(digits: Optional[int] = None
                 ) -> Callable[[Callable], Callable[[object], float]]:
    digit: int = PACKET_LOSS_OUTPUT_DIGITS if digits is None \
        else int(digits)

    def round_number_setter(func: Callable
                            ) -> Callable[[object], float]:
        def wrap(*arg, **kwargs) -> float:
            return float(round(func(*arg),
                               kwargs.get("ndigits", digit)))

        return wrap
    return round_number_setter

@print_information
@round_number(3)
def time_difference(start_time: float, *message) -> float:
    return time.time() - start_time
    #

def slice_deque(d: Deque[T], *,
                start: int = 0,
                stop: Optional[int] = None,
                step: int = 1
                ) -> list[T]:
    stop = len(d) if stop is None else stop
    index_slice: tuple[int, ...] = tuple(map(int, (start, stop, step)))
    d.rotate(-start)
    sliced_deque: list[T] = list(itertools.islice(d, *index_slice))
    d.rotate(start)
    return sliced_deque

def DictionarySetter(dictionary: dict[int, int], key: int) -> dict:
    exist_key: Optional[int] = dictionary.get(key)
    if exist_key is None:
        dictionary[key] = 1
    else:
        dictionary[key] += 1

    return dictionary

"""    test `check_time_sleep` with `print_information` decorator
start_time: float = time.time()
time.sleep(10)  #simulate initialization time of system
check_time_sleep(start_time, "Start", "\n")
"""

class PacketLoss(threading.Thread):
    def __init__(self, header: dict = {},
                 shut_event: threading.Event = threading.Event(), *,
                 packet_loss_denominator: int = 100,
                 interval: float = MINIMA_INTERVAL
                 ) -> None:
        super().__init__()
        self.__run_state: bool = False

        self._header: dict = header
        self._packet_loss_denominator: int = packet_loss_denominator
        self.__time_interval: float = interval

        self._bool_list: Deque[bool] = collections.deque(
            [False for _ in range(self.__denominator)],
            self.__denominator)
        # To know the number of the first element in `self._bool_list`
        self.__bool_list_index: int = 0

        # Initialization in MainSetter -> Init()
        self.__recorded_number: int
        self.__current_header_number: int  #initial package number: 0

        #old version uses list data type
        #self.__loss_index_list: list[int] = []
        self.__loss_index_dict: dict[int, int] = {}
        self.__out_of_order_index_set: set[int] = set()

        self.__duplicate_index_dict: dict[int, int] = {}
        self.__compression_ratio: int = 100
        self.__loss_index_history: list[Iterator[int]] = []

        self._shut_event: threading.Event = shut_event

    @functools.lru_cache(10)    #NOTICE: argument can be changed
    def TimeInterval(self, func: Callable) -> Callable:
        second: float = self.time_interval
        idx: int = 0
        # print(f"[MonitorNetSocket] {func.__name__}")

        def wrap() -> None:
            nonlocal idx
            start_time: float = time.time()
            time.sleep(second)
            time_difference(start_time, f"{(idx := idx + 1)=}", "\n")

            func()
        return wrap

    def __update_number(self, list_index: Optional[int] = None) -> int:
        received_index: int = self.__current_header_number
        difference: int = received_index - self.__record_number
        list_index = self.current_index if list_index is None \
            else list_index + 1

        package_in_order: bool = difference > 0
        #REVIEW: Recursion if difference between
        # recorded number and received package number is bigger than 0.
        if package_in_order:
            self.__record_number += 1
            if difference > 1:
                self._bool_list.appendleft(True)
                #old version uses list data type
                #self.__packet_loss += [self.__record_number]
                self.__packet_loss = DictionarySetter(
                    self.__packet_loss, self.__record_number)
                return self.__update_number(list_index)
            else:  #difference == 1
                self._bool_list.appendleft(False)
                list_index += 1
            #
        #NOTICE: testing!
        elif difference == 0:
            #REVIEW: Before doing `self.UpdateNumber`,
            # `self.NumberComparison` excludes equal to zero cases.
            raise Exception
        else:
            #REVIEW: package retransmission
            #self.__out_of_order_index_set.add(received_index)

            within_bool_list: bool = (list_index - self.__denominator
                                      <= received_index
                                      <= self.__record_number)
            if within_bool_list:  #modify *bool* in `self._bool_list`
                #_index = abs(received_index - self.__record_number) \
                #    % self.__denominator
                #_index = self.__record_number - received_index + 1
                self._bool_list[(self.__record_number
                                 - received_index + 1)] = False
                self.__packet_loss.pop(received_index, None)
            else:  #out of interval, add to `self.__duplicate_packet`
                self.__duplicate_packet = DictionarySetter(
                    self.__duplicate_packet, received_index)
            #raise Exception

        return list_index

    def __resize_loss_index_list(self, ratio: int) -> None:
        shadow_history: list[Iterator[int]] = self.__loss_index_history

        def resize_loss_index_list(resized: dict[int, int]
                                   | tuple[tuple[int, int], ...]
                                   ) -> None:
            resized = tuple(resized.items()) if isinstance(resized, dict) \
                else resized
            resized_, resized = resized[:ratio], resized[ratio:]
            key, _ = zip(*resized_)
            shadow_history.append(iter(key))

            if len(resized) > ratio:
                return resize_loss_index_list(resized)
            else:
                self.__packet_loss = dict(resized)

        return resize_loss_index_list(self.__packet_loss)

    @round_number()
    def __calculate_packet_loss(self) -> float:
        if self.current_index > self.__denominator:
            return sum(self._bool_list) / self.__denominator
        else:
            return self.__calculate_packet_loss_not_full_queue()

    @round_number()
    def __calculate_packet_loss_not_full_queue(self) -> float:
        package_loss: list[bool] = slice_deque(self._bool_list,
                                               stop=self.current_index)
        if package_loss:
            #print(len(package_loss))
            return sum(package_loss) / len(package_loss)
        else:  #empty `package_loss` means non-received yet, return -1
            return -1

    def __count_packet_loss(self) -> int:
        return self.__packet_loss.__len__()

    def get_packet_loss(self, percent_flag: bool = True
                        ) -> float | Sequence[bool]:
        if percent_flag:
            return self.__calculate_packet_loss()
        else:
            return self._bool_list

    def get_packet_loss_history(self, detail_flag: bool = True
                                ) -> PacketHistoryDetailFormat | int:
        """Return the history of packet loss.
        The first of the return elements is the compressing packet loss 
        with the [0, 1] index. 
        The first index(0) of the first element of return is a
        `list[Iterator[int]]` data type.
        While packet retransmission happens, the packet sequence number 
        between the interval of `self._bool_list` is removed; 
        otherwise, the packet sequence number is appended to 
        the element of the second index(1) with a `dict[int, int]` type.
        The second of the return elements records the sequence number 
        when packet loss occurs, and never delete the element even though
        the packet retransmission happens.

        Args:
            detail_flag (bool, optional): Return the whole history or \\
                the count of packet loss history. Defaults to True.

        Returns:
            PacketHistoryDetailFormat | int: data_type_description \\
            tuple[tuple[list[Iterator[int]],
                        dict[int, int]],
                  set[int]] \\
            | int
        """
        if detail_flag:
            history: list[Iterator[int]] = self.__loss_index_history.copy()
            # old version uses list data type
            #history.append(iter(self.__packet_loss.copy()))

            history.append(iter(list(self.__packet_loss.copy())))
            return ((history, self.__duplicate_packet),
                    self.__out_of_order_index_set)
        else:
            return (self.__loss_index_history.__len__()
                    * self.compression_ratio
                    + self.__count_packet_loss())

    @property
    def number_comparison(self) -> bool:
        header_index: int = self.packet_sequence_number

        if header_index == self.__current_header_number:
            return False  #means pass this round
        else:  #header_index <> self.__current_header_index
            self.__current_header_number = header_index
            return True

    @property
    def state(self) -> bool:
        return self.__run_state

    @property
    def __denominator(self) -> int:
        return self._packet_loss_denominator

    @__denominator.setter
    def __denominator(self, value: int) -> None:
        self._packet_loss_denominator = (
            int(value) if value >= MINIMA_PACKET_LOSS_LENGTH
            else MINIMA_PACKET_LOSS_LENGTH)

    @property
    def time_interval(self) -> float:
        return self.__time_interval

    @time_interval.setter
    def time_interval(self, value: float) -> None:
        self.__time_interval = value if value >= MINIMA_INTERVAL \
            else MINIMA_INTERVAL

    @property
    def compression_ratio(self) -> int:
        return self.__compression_ratio

    @compression_ratio.setter
    def compression_ratio(self, value: int) -> None:
        msg: str
        if self.state:
            msg = "Can not set `compression_ratio`."
        else:
            msg = "Set `compression_ratio` done."
            self.__compression_ratio = int(value)
        print(f"{self.state=}: {msg}")

    @property
    def packet_sequence_number(self) -> int:
        return self._header.get("Packet Sequence Number", -1)

    @property
    def __record_number(self) -> int:
        return self.__recorded_number

    @__record_number.setter
    def __record_number(self, value: int) -> None:
        self.__recorded_number = value

    @property
    def current_index(self) -> int:
        return self.__bool_list_index

    #@_current_index.setter
    #def _current_index(self, value: int) -> None:
    #    self.__bool_list_index = value

    @property
    def __packet_loss(self) -> dict[int, int]:
        return self.__loss_index_dict

    @__packet_loss.setter
    def __packet_loss(self, value: dict[int, int]) -> None:
        self.__loss_index_dict = value

    @property
    def __duplicate_packet(self) -> dict[int, int]:
        return self.__duplicate_index_dict

    @__duplicate_packet.setter
    def __duplicate_packet(self, value: dict[int, int]) -> None:
        self.__duplicate_index_dict = value
        #key: int = tuple(value)[0]
        #exist_key: Optional[int] = self.__duplicate_index_dict.get(key)
        #if exist_key is None:
        #    self.__duplicate_index_dict[key] = 1
        #else:
        #    self.__duplicate_index_dict[key] += 1

    #TODO: add this method in `self` to reset `self.__duplicate_packet`
    @__duplicate_packet.deleter
    def __duplicate_packet(self) -> None:
        self.__duplicate_packet.clear()

    #@TimeInterval
    #def Main(self) -> None:
    #    if self.NumberComparison:
    #        self._bool_list_index = self.UpdateNumber()

    def MainSetter(self, initial_flag: bool) -> Callable:
        def __Init() -> None:
            while self._header.get("Packet Sequence Number") is None:
                #TODO: something error here because of the connection
                #self.TimeInterval(__Init)()
                time.sleep(self.time_interval)
            self.__record_number = self.packet_sequence_number
            #REVIEW: Let `__current_header_index` = `packet_sequence_number`
            # to avoid passing `self.number_comparison`
            # but can not update number
            # because of the difference between `__current_header_index`
            # and `record_number` is *zero*.
            self.__current_header_number = self.packet_sequence_number

        if initial_flag:
            return __Init
        else:
            #NOTICE: #
            ratio: int = self.compression_ratio
            # Avoid printing `func.__name__`
            # in `self.TimeInterval` when initializing.

            @self.TimeInterval
            def __Main() -> None:
                if self.number_comparison:
                    self.__bool_list_index = self.__update_number()
                    # Use `elif` and move under *self.number_comparison*
                    # could let `Main()` do one thing every called.
                    # In this case, `self.TimeInterval` should be smaller;
                    # otherwise, maybe skip the packet.
                    if self.__count_packet_loss() > ratio:
                        #If the performance is not good enough,
                        # use a thread instead.
                        self.__resize_loss_index_list(ratio)

            return __Main

    #
    def run(self) -> None:
        self.MainSetter(True)()  #initialization
        self.__run_state = True
        main: Callable = self.MainSetter(False)
        while not self._shut_event.is_set():
            main()

        def output_test() -> None:
            #[format]
            #print(*f"""{f'{self.value= }'
            #            .replace('= ', '~= ')}""".split('~'),
            #            sep='\n', end='\n\n')
            print(*f"""{f'{self.get_packet_loss(percent_flag=False)= }'
                        .replace('= ', '~= ')}""".split('~'),
                  sep='\n', end='\n\n')
            print(*f"""{f'{self.get_packet_loss(percent_flag=True)= }'
                        .replace('= ', '~= ')}""".split('~'),
                  sep='\n', end='\n\n')
            print(*f"""{f'{self.current_index= }'
                        .replace('= ', '~= ')}""".split('~'),
                  sep='\n', end='\n\n')
            print(*f"""{f'{self.__packet_loss= }'
                        .replace('= ', '~= ')}""".split('~'),
                  sep='\n', end='\n\n')
            print(*f"""{f'{self.get_packet_loss_history(detail_flag=False)= }'
                        .replace('= ', '~= ')}""".split('~'),
                  sep='\n', end='\n\n')
            print(*f"""{f'{self.get_packet_loss_history(detail_flag=True)= }'
                        .replace('= ', '~= ')}""".split('~'),
                  sep='\n', end='\n\n')

            #print(*f"""{f'{self.value= }'
            #            .replace('= ', '~= ')}""".split('~'),
            #            sep='\n', end='\n\n')

        output_test()
        self.__run_state = False


def plot_result_sharedY(x1: Sequence[bool], x2: Sequence[float],
                        ylabel: str, *,
                        x2label: str = 'Packet loss(%)') -> None:
    color: str
    main_text_size: int = 20
    sub_text_size: int = 16
    tick_size: int = 14
    fig, ax1 = plt.subplots()

    color = 'tab:red'
    #ax1.set_xlabel('Converted boolean', color=color)
    ax1.set_ylabel(ylabel, fontsize=sub_text_size)
    ax1.tick_params(axis='both', which='major', labelsize=tick_size)
    ax1.plot(x1, color=color, linestyle=':',
             label='received(1);  non-received(0)', )

    plt.grid(axis='both')
    plt.legend(fontsize=main_text_size,
               bbox_to_anchor=(0.5, 0), loc='lower center',
               bbox_transform=fig.transFigure, frameon=False)

    ax2 = ax1.twiny()

    color = 'tab:blue'
    ax2.set_xlabel(x2label, color=color, fontsize=main_text_size)
    ax2.tick_params(axis='both', which='major', labelsize=tick_size)
    #ax2.set_ylabel('percent')
    ax2.plot(x2, color=color,
             label='loss ratio', linewidth=3)
    #plt.grid()

    plt.tight_layout()


def plot_system_usage(usage_iter: Iterator[tuple[float, float, float]]
                      ) -> None:
    main_text_size: int = 20
    sub_text_size: int = 16
    tick_size: int = 14

    cpu, memory, disk = zip(*usage_iter)

    plt.figure()
    plt.suptitle("System Usage", fontsize=sub_text_size)

    plt.subplot(311)
    plt.plot(cpu)
    plt.title(f"cpu_percent", fontsize=main_text_size)
    plt.ylabel("percent", fontsize=sub_text_size)
    plt.tick_params(axis='both', which='major', labelsize=tick_size)

    plt.subplot(312)
    plt.plot(memory)
    plt.title(f"memory_percent", fontsize=main_text_size)
    plt.ylabel("percent", fontsize=sub_text_size)
    plt.tick_params(axis='both', which='major', labelsize=tick_size)

    plt.subplot(313)
    plt.plot(disk)
    plt.title(f"disk_usage", fontsize=main_text_size)
    plt.ylabel("bytes", fontsize=sub_text_size)
    plt.tick_params(axis='both', which='major', labelsize=tick_size)

    plt.tight_layout()

def plot_system_usage_runtime_interval(intervals: UsageFormat,
                                       base_interval: float,
                                       unit: str = "milliseconds"
                                       ) -> None:
    main_text_size: int = 20
    sub_text_size: int = 16
    tick_size: int = 14

    unit_dictionary: dict[str, float] = {
        "second": 1,
        "millisecond": 1e3,
        "microsecond": 1e6,
    }

    unit_rate: Optional[float] = unit_dictionary.get(unit.rstrip('s'))
    if unit_rate is None:
        print(f"[WARN]  '{unit}' is not in {unit_dictionary.keys()}.")
        #default parameters
        unit_rate = 1
        unit = "second"

    plt.figure()

    plt.plot([((time - base_interval) * unit_rate)
              for time in intervals])  #millisecond unit
    plt.title("time_interval", fontsize=main_text_size)

    plt.xlabel("points", fontsize=sub_text_size)
    plt.ylabel(unit, fontsize=sub_text_size)  #millisecond
    plt.tick_params(axis='both', which='major', labelsize=tick_size)

    plt.tight_layout()


#%%    Main Function
@test_input_checker
def loss_packet_test(number: int) -> filter:
    def is_prime(n):
        for i in range(2, int(n ** 0.5) + 1):
            if n % i == 0:
                return False
        return True

    n_list = filter(is_prime, range(number))
    #n_list = [0, 1, 2, 3]  #the begin of package sequence number
    #for i in range(4, number + 1):
    #    # The prime and numbers divisible by `ten` are out of the test.
    #    condition: bool = not is_prime(i) and bool(i % 10)
    #    if condition:
    #        n_list.append(i)
    #
    return n_list

@test_input_checker
def normal_test(number: int) -> range:
    return range(number)

@test_input_checker
def retransmission_packet_test(number: int) -> list[int]:
    import random
    random.seed(3588)

    packet_sequence_list: list[int] = list(normal_test(number))
    random.shuffle(packet_sequence_list)

    return packet_sequence_list

def given_test(number: int) -> list[int]:
    def is_not_prime(n):
        for i in range(2, int(n ** 0.5) + 1):
            if n % i == 0:
                return not False
        return not True
    n_list: list[int] = [0, 1, 2, 3]
    n_filter: filter = filter(is_not_prime, range(number))
    n_list.extend(n_filter)

    return n_list

#MAIN
def MAIN() -> None:
    def simulate_communication_module(input_state: tuple[bool, ...],
                                      test_input: Sequence[int],
                                      header_output: dict
                                      ) -> None:
        state_index: int = -1
        state_length: int = len(input_state) - 1
        input_index: int = 0
        input_length: int = len(test_input)
        while state_index < state_length and input_index < input_length:
            time.sleep(0.4)  #transmission delay of communication module
            state_index += 1
            if input_state[state_index]:
                value: int = test_input[input_index]
                input_index += 1
            else:
                continue
            header_output.update({"Packet Sequence Number": value})
        #

    #@PacketLoss.TimeInterval
    def record_packet_loss(PacketLossThread: PacketLoss,
                           list_output: list[float]) -> None:
        def add_loss(loss_list: list[float]) -> list[float]:
            loss: float | Sequence[bool] = \
                PacketLossThread.get_packet_loss()
            assert isinstance(loss, float)
            loss_list.append(loss)
            return loss_list

        if not PacketLossThread.state:
            while not PacketLossThread.state:
                time.sleep(MINIMA_INTERVAL)
        start_record: float = time.time()
        while not PacketLossThread._shut_event.is_set():
            list_output = add_loss(list_output)
            #

            time.sleep(MINIMA_INTERVAL)

        #get 1 more `packet_loss`
        while PacketLossThread.state:  #wait for `PacketLossThread`
            time.sleep(MINIMA_INTERVAL)
        time_difference(start_record, "Stop Recording...")
        list_output = add_loss(list_output)

    testing_range: int
    testing_input: Sequence
    if __name__ == '__main__':
        testing_range = test_range
        testing_input = copy.copy(test_input)
    else:
        # test_list:  1. normal_test, 2. loss_packet_test,
        # 3. retransmission_packet_test, 4. given_test(not done yet)
        testing_range = 100
        testing_input = loss_packet_test(testing_range)
    convert_setter: Callable[[Sequence[int]], tuple[bool, ...]] = \
        convert_input(testing_range,
                      True)
    testing_bool_list: tuple[bool, ...] = convert_setter(testing_input)

    header_dict: dict = {}
    packet_loss_list: list[float] = []

    #can import from another program
    shut_event: threading.Event = threading.Event()

    packet_loss_thread: threading.Thread = PacketLoss(header_dict,
                                                      shut_event)
    packet_loss_thread.name = "PacketLoss"  #thread.setName("PacketLoss")

    system_usage_thread: ProcessUsage = ProcessUsage(os.getpid(),
                                                     shut_event=shut_event)
    system_usage_thread.name = "SystemUsage"

    packet_loss_thread.start()
    system_usage_thread.start()
    #
    start_initial_time: float = time.time()
    print(f"{time.asctime(time.localtime())}:  Start program")

    print("Initializing...")

    communication_thread: threading.Thread = threading.Thread(
        None,
        simulate_communication_module,
        "SimulateCommunicationThread",
        (testing_bool_list, testing_input, header_dict),
        daemon=True  #break when Main Thread is closed.
    )

    record_thread: threading.Thread = threading.Thread(
        None,
        record_packet_loss,
        "RecordPacketLossThread",
        (packet_loss_thread, packet_loss_list)
    )

    time.sleep(10)  #simulate initialization time of system
    time_difference(start_initial_time, "Initialize done.", "\n")

    #
    start_running_time: float = time.time()
    print(f"\n{time.strftime('%H:%M:%S', time.localtime())}:  Running...")

    communication_thread.start()
    record_thread.start()

    #wait until communication is done or `time.sleep` for specification
    communication_thread.join()
    #time.sleep(400)

    shut_event.set()
    time_difference(start_running_time, "Stop!", "\n")

    #
    record_thread.join()
    #packet_loss_thread.join()
    print(f"\n\n{time.asctime(time.localtime())}:  All Done!\n")

    system_usage_return: ProcessUsageReturnFormat = \
        system_usage_thread.return_data

    system_usage: Iterator[tuple[float, float, float]]
    system_usage_runtime_interval: UsageFormat
    system_usage, system_usage_runtime_interval = system_usage_return

    #
    test_input_checker(testing_input)(testing_range)
    packet_loss_list = list(filter(lambda x: x >= 0, packet_loss_list))

    '''    old plot
        #
        plt.figure()
        plt.title(f"{testing_range}")

        plt.subplot(211)
        plt.plot(packet_loss_list)

        plt.grid()

        plt.subplot(212)
        plt.plot(testing_bool_list)

        plt.grid()

        plt.show()
    '''
    plot_result_sharedY(testing_bool_list, packet_loss_list, 'percent')

    plot_system_usage(system_usage)

    plot_system_usage_runtime_interval(system_usage_runtime_interval,
                                       system_usage_thread.time_interval)


#%%    Main
if __name__ == '__main__':
    from matplotlib import pyplot as plt  # type: ignore
    test_range: int = 11
    # test_list:  1. normal_test, 2. loss_packet_test,
    # 3. retransmission_packet_test, 4. given_test(not done yet)
    test_input: Sequence = given_test(test_range)
    MAIN()

    plt.show()


#%%
