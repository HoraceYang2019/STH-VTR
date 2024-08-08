
'''
Created on 2024-02-11 15:52:59

@author: MilkTea_shih
'''

#%%    TODO:
'''
    1.  Add a new sheet and share xlsx with Confirmation.py
    
'''

# In[0]:
version: str = 'MonitorSystemUsage v1.0'

#%%    Packages
import collections
import dataclasses
import functools
import threading
import time

import os
import pandas as pd  # type: ignore
import pathlib
import psutil   # type: ignore

from typing import Any, Callable, Deque, Iterator, Sequence, Optional
from typing import NamedTuple
from types import ModuleType

from ConfirmDataDelay import CheckOutputPath
from IsDataclassProtocol import IsDataclass

UsageFormat = tuple[float, ...]
ProcessUsageReturnFormat = tuple[Iterator[tuple[float, float, float]],
                                 UsageFormat]

#%%    Variable
#minima interval called between `psutil.process.cpu_percent()`
MINIMA_INTERVAL: float = 0.1

#NOTE: copy from default_parameters.py without default value
@dataclasses.dataclass
class DefaultParameter(IsDataclass):
    time_interval: float
    usage_order: tuple[str, ...]
    save_usage: bool
    record_system_usage_runtime_interval: bool

#%%    Functions
def GetParameterArgument(func: Callable
                         ) -> Callable[[dict], IsDataclass]:
    def wrap(kwargs: dict) -> IsDataclass:
        if not kwargs.__len__():
            return func()
        keywords: tuple[str, ...] = (
            "name", "path",
        )
        if kwargs.get(keywords[0]) is not None:
            return func(kwargs[keywords[0]])
        elif kwargs.get(keywords[1]) is not None:
            return func(path=kwargs[keywords[1]])
        else:
            raise KeyError(f"""Check argument: {kwargs = }
                           \rCan not find argument in {keywords = }.
                           \r""")

    return wrap


"""old version is hard to read
def ProcessPIO() -> Callable[[Callable[[psutil.Process], psutil._pswindows.pio]],
                             Callable[[object, psutil.Process], float]]:
    def GetPIOSetter(func: Callable[[psutil._pswindows.pio], float]
                     ) -> Callable[[object, psutil.Process], psutil._pswindows.pio]:
        def GetPIO(self: object, process: psutil.Process) -> psutil._pswindows.pio:
            return func(process.io_counters())
        return GetPIO
    return GetPIOSetter
    
@ProcessPIO() and not passing non-argument
"""
def ProcessPIO(func) -> Callable[[object, psutil.Process], float]:
    def get_pio(self, process: psutil.Process) -> float:
        return func(process.io_counters())
    return get_pio

@GetParameterArgument
def get_parameter(name: Optional[str] = None, *,
                  path: Optional[pathlib.Path | str] = None
                  ) -> DefaultParameter | IsDataclass:
    #REVIEW: parameter named `parameter_dict` in default file

    #NOTE: Add the other arguments as default parameter dictionary
    parameters: dict = {    #default
        # dictionary type, e.g.,
        #"default_key": "value",    #default_value
        # "*key*": *value*,    #*default value*
        "time_interval": 0.5,    #0.1
        "usage_order": ("cpu", "memory", "disk", "runtime interval"),
        "save_usage": True,
        "record_system_usage_runtime_interval": True,

    }
    if path is not None:
        #TODO: open `path`.csv, whatever `name` is not *None*
        ...
    elif name is not None:  # specify parameter file with .py extension
        import importlib.machinery
        import importlib.util
        filepath: str = "\\".join((os.getcwd(), f"{name}.py"))
        spec: Optional[importlib.machinery.ModuleSpec] = \
            importlib.util.spec_from_file_location(name, filepath)

        if spec is not None:
            module: ModuleType = importlib.util.module_from_spec(spec)

            from importlib.abc import Loader
            assert isinstance(spec.loader, Loader)

            spec.loader.exec_module(module)
            parameters = module.parameter_dict

    else:  #NOTE: The type of output above is dictionary
        try:
            import default_parameters

            if not os.path.exists(f"{default_parameters.__name__}.py"):
                raise FileNotFoundError
        except (FileNotFoundError, ModuleNotFoundError) as error:
            #NOTICE: write into log
            print(f"[MonitorSysUsage]  {error}\nIt will run with {parameters=}")
        except Exception as error:
            print("[MonitorSysUsage]" + error)    #NOTICE: write into log
        else:
            return default_parameters.Parameters()  #non-error happened

    try:
        return default_parameters.Parameters(**parameters)
    except Exception as error:  #parameters is not exactly the same as default
        import dacite
        print(f"[MonitorSysUsage]  {error}")
        #NOTICE: change/add attribute in `DefaultParameter` is allowed
        return dacite.from_dict(DefaultParameter, parameters)


class ProcessUsage(threading.Thread):
    def __init__(self, pid_: Optional[int] = None, *,
                 shut_event: threading.Event,
                 **kwargs  #parameter setting
                 ) -> None:
        super().__init__()
        # Get pid of current program
        self.__pid = os.getpid() if pid_ is None else int(pid_)

        self.__process: psutil.Process = psutil.Process(pid_)
        #DEBUG: open these comment
        """"""
        #from default_parameters import Parameters
        #self.__parameters: Parameters = Parameters()
        """"""
        self.__parameters: DefaultParameter = get_parameter(kwargs)  # type: ignore

        self.__time_interval: float = self.__set_time_interval()
        #self.__time_interval: float = 0.1

        self.__max_queue_length: int = 1 if self.time_interval > 1 \
            else int(1 / self.time_interval)

        self.__denominator: float = (self.__max_queue_length
                                     * self.time_interval)
        self.__max_queue_length += 1  #make 1 more temp

        self.__shut_event: threading.Event = shut_event
        self.__return_event: threading.Event = threading.Event()
        self._save_done_event: threading.Event = threading.Event()

        self.__data_list: list[tuple[float, ...]] = []
        self.__disk_usage: Deque[float] = collections.deque(
            [], self.__max_queue_length)

        self.__time_difference_each_round: list[float] = []
        self.__record_runtime: bool = self.__set_runtime_record()

    def __set_time_interval(self) -> float:
        #import default_parameters
        #self.__parameters = default_parameters.Parameters()
        interval: float = self.__parameters.time_interval
        return MINIMA_INTERVAL if interval < MINIMA_INTERVAL else interval

    def __set_runtime_record(self) -> bool:
        #import default_parameters
        #self.__parameters = default_parameters.Parameters()
        boolean: bool = self.__parameters.record_system_usage_runtime_interval
        return boolean if isinstance(boolean, bool) else True

    def print_time_difference(self, start_time: float) -> None:
        print(f"[MonitorSysUsage]  {(time.time() - start_time):.3f}")

    def __record_runtime_interval(self, start_time: float) -> None:
        time_difference: float = round(time.time() - start_time, 6)
        self.__time_difference_each_round.append(time_difference)

    def TimeInterval(self, func: Callable) -> Callable:
        second: float = self.time_interval
        idx: int = 0
        # print(f"[MonitorSysUsage]  current func name is {func.__name__}")

        function_start_time: float = time.time()

        def time_sleep() -> None:
            nonlocal idx

            time.sleep(second)
            func()

            print(f"[MonitorSysUsage]  {(idx := idx + 1):< 6,d}: ", end='')
            self.print_time_difference(function_start_time)

        def record_runtime_with_time_sleep() -> None:
            start_time: float = time.time()

            time.sleep(second)
            func()

            self.__record_runtime_interval(start_time)

        def return_running_times() -> int:
            return idx

        if func is None:
            return return_running_times

        return record_runtime_with_time_sleep if self.__record_runtime \
            else time_sleep

    @ProcessPIO
    def disk_write_usage(pio) -> float:
        """Get bytes of disk writing.

        Args:
            pio (psutil._pswindows.pio): a namedtuple with *`index`: `field`*
            0: read_count, 1: write_count, 2: read_bytes, 3: write_bytes

        Returns:
            float: value from disk information
        """
        return pio.write_bytes  #index: 3

    #TODO: calculate the unit, it is bytes now.
    @functools.lru_cache(2)
    def calculate_disk_usage_setter(self) -> Callable[[], float]:
        denominator: float = self.__denominator

        def calculate_disk_usage() -> float:
            head, *mid, last = self.__disk_usage
            return abs((last - head) / denominator)

        return calculate_disk_usage

    def get_usage(self, process: psutil.Process) -> tuple[float, ...]:
        cpu_percent: float = process.cpu_percent()
        #memory_usage: float = process.memory_info().rss
        memory_percent: float = round(process.memory_percent(), 4)

        self.__disk_usage.append(self.disk_write_usage(process))
        disk_usage: float = self.calculate_disk_usage_setter()()

        #return (cpu_percent, memory_usage, memory_percent, disk_usage)
        return (cpu_percent, memory_percent, disk_usage)

    @property
    def yield_data(self) -> Iterator:
        return iter(self.__data_list.copy())

    @property
    def return_data(self) -> tuple[Iterator, UsageFormat]:
        self.Stop()
        self.__return_event.wait()
        return (iter(self.__data_list),
                tuple(self.__time_difference_each_round))

    @property
    def state(self) -> bool:
        return True if self.__shut_event.is_set() else False

    @property
    def pid(self) -> int:
        return self.__pid

    @property
    def time_interval(self) -> float:
        return self.__time_interval

    def MainSetter(self, initial_flag: bool) -> Callable:
        process: psutil.Process = self.__process

        @self.TimeInterval
        def __Initial() -> None:
            self.__disk_usage.append(self.disk_write_usage(process))

        @self.TimeInterval
        def __Main() -> None:
            self.__data_list.append(self.get_usage(process))

        if initial_flag:
            return __Initial
        else:
            return __Main
    #

    def Start(self, restart_flag: bool = False) -> "ProcessUsage":
        if restart_flag:
            return self.__ReStart()
        else:
            self.__shut_event.clear()
            threading.Thread(None, self.run).start()
            return self

    def __ReStart(self, thread: Optional["ProcessUsage"] = None
                  ) -> "ProcessUsage":
        if thread is None:
            return self.__ReStart(ProcessUsage(self.__pid,
                                               shut_event=threading.Event()))
        else:
            thread.start()
            return thread

    '''return new event
    def __ReStart(self, thread: Optional["ProcessUsage"] = None
                  ) -> "ProcessUsage" | tuple["ProcessUsage", threading.Event]:
        if thread is None:
            return self.__ReStart(ProcessUsage(self._pid,
                                               shut_event=threading.Event()))
        else:
            #
            thread.start()
            #thread._shut_event.clear()
            return thread, thread._shut_event
'''

    def Stop(self) -> None:
        self.__shut_event.set()

    def run(self) -> None:
        if self.__return_event.is_set():
            self.return_data  #just return data
            print(f"[MonitorSysUsage]  To get data while running, use {self.yield_data = }")
            return None

        # Initialization
        init: Callable = self.MainSetter(True)
        main: Callable = self.MainSetter(False)

        while len(self.__disk_usage) <= self.__max_queue_length - 1:
            # Let `self.__disk_usage` have the history
            init()

        # MAIN
        self.__time_difference_each_round.clear()  #setup done
        #REVIEW: use event to stop
        while not self.__shut_event.is_set():
            main()

        self.__return_event.set()
        print(f"[MonitorSysUsage]  {self.__return_event.is_set()=}: Returning data...")

        #TODO: set as attribute
        usage_iter: Iterator[tuple[float, float, float]]
        usage_iter, runtime_interval_list = self.return_data
        if self.__parameters.save_usage:
            usage_list: list[tuple[float, float, float, float]] = [
                (*usages, runtime_interval_list[idx])
                for idx, usages in enumerate(usage_iter)
            ]
            field_name: Optional[tuple[str, ...]] = \
                self.__parameters.usage_order
            file_path: pathlib.Path | str = CheckOutputPath(
                time.strftime('%Y-%m-%d-%H-%M-%S', time.localtime()),
                '.xlsx',
                pathlib.Path("C:\VTR\RawData\Verify")
            )
            save_file_thread: threading.Thread = threading.Thread(
                None, save_usage,
                "SaveDataFrameThread",
                ((usage_list, field_name, file_path)),
            )
            save_file_thread.start()
            save_file_thread.join()

            self.output_path: pathlib.Path | str = file_path

        self._save_done_event.set()
        print("[MonitorSysUsage]  Waiting for `self._save_done_event.clear()`...")
        while self._save_done_event.is_set():
            time.sleep(1)  #wait for getting `self.output_path`

        print("[MonitorSysUsage]  DONE!")

def plot_system_usage(data_iter: Iterator[tuple[float, float, float]]
                      | list[tuple[float, float, float, float]]
                      ) -> None:
    main_text_size: int = 20
    sub_text_size: int = 16
    tick_size: int = 14

    #NOTE: `_` temp variable in order to avoid error while unpacking
    cpu, memory, disk, *_ = zip(*data_iter)

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
        print(f"[MonitorSysUsage]  -WARN  '{unit}' is not in {unit_dictionary.keys()}.")
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

def write_xlsx(writer: Any | pd.ExcelWriter,
               data: pd.DataFrame,
               sheet_name: str
               ) -> None:
    def size_compare(shape: tuple[int, int]) -> tuple[bool, bool]:
        LIMIT_ROW: int = 1048576 - 1  #1: field name
        LIMIT_COLUMN: int = 16384
        return shape[0] >= LIMIT_ROW, shape[1] >= LIMIT_COLUMN

    # use byte to determine which mode
    mode: int = int.from_bytes(b''.join(map(int.to_bytes,
                                            size_compare(data.shape))))
    match mode:
        case 0:
            data.to_excel(writer,
                          sheet_name,
                          index=False)
        case 1:  #data length of columns reach SHEET_LIMIT_COLUMN
            #write_xlsx(sheet_name=f"{index}")
            ...

        case 256:  #data length of rows reach SHEET_LIMIT_ROW
            ...

        case 257:  #both rows and columns reach SHEET_LIMIT !
            ...


def save_usage(data_list: Sequence[UsageFormat],
               columns_name: Optional[Sequence[str]],
               path: pathlib.Path | str,
               sheet_name: str = "SystemUsage",
               write_mode: str = 'w',
               ):

    data_frame: pd.DataFrame = pd.DataFrame(data_list,
                                            columns=columns_name)

    if isinstance(path, pathlib.Path):
        with pd.ExcelWriter(path.as_posix(), 'auto', mode=write_mode) as w:
            write_xlsx(w, data_frame, sheet_name)

        print(f"[MonitorSysUsage]  Done!\nThe result is at {path.as_posix()}.")
    else:  #type(path) == str
        print(f"[MonitorSysUsage]  {path = }: means the filename exists in "
              + f"'C:\VTR\RawData\Verify' with many times!")

#%%    Main Function


#%%    Main
if __name__ == '__main__':

    shut_event: threading.Event = threading.Event()  #can import from another program
    this_process: ProcessUsage = ProcessUsage(shut_event=shut_event,
                                              name='default_parameters')
    #this_process.run()
    #%% %    Test
    this_process.start()
    start_time: float = time.time()
    time.sleep(3)
    print(f"[MonitorSysUsage]  {(time.time() - start_time):.3f}")
    data_yield: Iterator = this_process.yield_data
    time.sleep(7)

    #shut_event.set()    #also can stop this thread
    this_process.Stop()    #rewrite a function to stop
    #time.sleep(1)

    print(f"{(time.time() - start_time):.3f}")
    data_full, data_full_time_intervals = this_process.return_data
    print("[MonitorSysUsage]  Done")

    #%% %    GO ON
    print("TESTING")
    this_process.Start()  #please use `thread.Start(restart_flag=True)`
    time.sleep(2)
    this_process.Stop()

    data_test_return, data_test_return_time_ = this_process.return_data

    print("ReStart")
    '''return new event version
    new_thread, new_event = this_process.Start(True)
'''
    new_thread: ProcessUsage = this_process.Start(True)
    time.sleep(25)

    new_thread.Stop()
    #time.sleep(1)

    print(f"{(time.time() - start_time):.3f}")
    new_data: Iterator = new_thread.yield_data
    #
    data_list: tuple[Iterator, ...] = (data_yield,
                                       data_full,
                                       data_test_return,
                                       new_data,
                                       )

    class DataClass(NamedTuple):  #reserve variable names
        data_yield: Iterator
        data_full: Iterator
        data_test_return: Iterator
        new_data: Iterator

    data_dict: DataClass = DataClass(*data_list)

    #data_dict: dict[str, Iterator[tuple[float, ...]]] = (
    #    {f"{data=}".split("=")[0]: data for data in data_list})

    #data_dict.update({f"{data=}".split("=")[0]: data
    #                  for data in data_list})

    #%% %%    Print with data_list
    """
    print("\n")
    for data in data_list:
        index: int = 0
        variable_name: str = f"{data=}".split("=")[0]
        print(f"{variable_name = }\n")
        print(sum(1 for _ in data))
        '''  each value
        while True:
            try:
                value: tuple[float, ...] = next(data)
            except StopIteration:
                break
            else:
                index += 1
                #print(f"{f'{index=}': <10}{f'{value}': <20}")
                
        '''
"""
    #%% %%    Print with data_dict and Plot out
    import matplotlib.pyplot as plt  # type: ignore
    key: str
    value: tuple[tuple[float, ...], ...]
    figure_number: int = 0
    for key, value in data_dict._asdict().items():

        #data_length: int = sum(1 for _ in value)
        #print(f"{key=}: {data_length}")

        cpu, memory, disk = zip(*value)

        plt.figure((figure_number := figure_number + 1))
        plt.suptitle(key)

        plt.subplot(131)
        plt.plot(cpu)
        plt.title(f"cpu_percent")

        plt.subplot(132)
        plt.plot(memory)
        plt.title(f"memory_percent")

        plt.subplot(133)
        plt.plot(disk)
        plt.title(f"disk_usage")

    plt.figure()
    plt.plot(data_full_time_intervals)
    plt.title("data_full_time_interval")

    plt.show()

    #%% %% Another pid
    a_process_pid: int = 99999
    A_process: ProcessUsage = ProcessUsage(a_process_pid, shut_event=shut_event)

#%%
