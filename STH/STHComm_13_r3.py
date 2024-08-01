# -*- coding: utf-8 -*-
"""
Created on 2024-03-15 11:25:36
@author: MilkTea_shih, Horace Yang
"""

#%%    TODO:  #NOTE:
'''
    1.  sock.accept(): when time-out happen, to show and solve it.
    2.  argument in `csock.recv` which number is better
    3.  if the csock never bind, collect thread will forever loop
        "target_STH_mac": "84f703ce2064", 
'''

#%%    Packages
import collections
import ctypes
import dataclasses
import datetime
import functools
import gc
import logging
import multiprocessing as mp
import re
import socket
import subprocess
import sys
import threading
import time
import traceback
import types
import os
import queue
import keyboard
import platform

from multiprocessing.sharedctypes import Synchronized, SynchronizedBase
from typing import Match
from typing import Any, Callable, Deque, Optional, Union
version: str = "STHComm v13.R2"

# customized functions
import HeaderSplit_4_1_1 as HeaderSplit

import Printer_1_0 as Printer
import STHSync_5_0 as SynSTH
import UpdateSTHParm_1_0 as usp

from MonitorNetSocket_1_0 import PacketLoss
from MonitorSysUsage_1_0 import ProcessUsage, save_usage

messageType = tuple[str, datetime.datetime]
#SharedFlag = Synchronized

@dataclasses.dataclass
class CommunicationModule:
    mac: str
    port: str = '6500'

enable_func: bool = True
master: bool = False
slave: bool = False
func_name: str = 'STHComm'
max_time_out: int = 300 # maximum timeout without any connection from STH (sec) 

# In[]
def LogMessage(file_path: str):
    logging.basicConfig(filename=file_path,
                        filemode='a',
                        format='[%(levelname)s]: %(asctime)s %(message)s',
                        level=logging.INFO)

# In[1]
def SetParameter(set_p: Union[types.ModuleType, Any]):  # Any -> toUpdate
    r_folder: str = set_p.raw_data_folder
    l_file: str = set_p.log_file

    s_host: str = usp.init.STH_host
    s_port: int = set_p.STH_base_port
    t_mac: str = set_p.target_STH_mac  #sth mac
    t_port: int = set_p.STH_base_port if set_p.target_STH_port is None \
        else set_p.target_STH_port     #tcp port

    b_address: str = set_p.broker_address
    b_port: int = set_p.broker_port
    l_topic: str = usp.init.log_topic
    p_topic: str = usp.init.pdata_topic

    h_length: int = usp.init.header_length
    m_frame: int = usp.init.mode0_frame_size  #24384 Bytes ~= 24 KB
    s_timeout: float = usp.init.socket_timeout
    
    delimiter: str = usp.init.txt_delimiter
    return (r_folder, l_file, s_host, s_port,
            t_mac, t_port, b_address, b_port,
            l_topic, p_topic, h_length, m_frame,
            s_timeout, delimiter)

#%%
class CommSTH(mp.Process):
    def __init__(self, role: str, connected_flag: ctypes.c_bool,
                 preset: Optional[CommunicationModule] = None,
                 stop_flag: Optional[ctypes.c_bool] = None,
                 ) -> None:

        super().__init__()
        self.source_path, self.log_file, self.STH_host, self.Edge_base_port, \
            self.STH_mac, self.Edge_target_port, self.broker_address, \
            self.broker_port, self.log_topic, self.pdata_topic, \
            self.header_length, self.mode0_frame_size, self.socket_timeout, self.delimiter = \
            SetParameter(usp.init) if not usp.updated_state \
            else SetParameter(usp.updated)

        if preset is not None:
            self.STH_mac = preset.mac
            self.Edge_target_port = int(preset.port)

            self.source_path += preset.mac + '/'

        self.package_length: int = int(self.header_length
                                       + self.mode0_frame_size)

        self.buffer: Deque[messageType] = collections.deque([])

        self._pid: int = os.getpid()

        self.csock: Optional[socket.socket] = None
        #TODO: `header_result` from `dict` to `list[dict]`,
        # to get more than 1 headers in one packet,
        # `HeaderSplit_4_1` implements in `PacketInformation()`.
        self.header_result: dict = {}

        self.save_event: threading.Event = threading.Event()

        #step by step stop checker

        self.stop_flag = mp.Value(
            ctypes.c_bool, False, lock=False) if stop_flag is None \
            else stop_flag

        self.stop_event: threading.Event = threading.Event()
        #self.stop_event: threading.Event = (Synchronized(mp.Value(
        #    ctypes, False)) if stop_event is None else stop_event)

        self.stop_collect: threading.Event = threading.Event()
        self.stop_save: threading.Event = threading.Event()
        self.stop_check_header: threading.Event = threading.Event()

        self.reconnect_event: threading.Event = threading.Event()

        self.collect_thread: threading.Thread = threading.Thread(
            target=self.CollectThread,
            name="collecting thread"
        )
        self.save_thread: threading.Thread = threading.Thread(
            target=self.SaveThread,
            name="saving thread"
        )
        self.bridge_thread: threading.Thread = threading.Thread(
            target=self.BridgeThread,
            name="bridge thread"
        )
        self.monitor_packet_loss_thread: PacketLoss = PacketLoss(
            self.header_result,
            self.stop_event
        )
        self.monitor_packet_loss_thread.name = "Packet Loss Thread"
        self.monitor_system_usage_thread: ProcessUsage = ProcessUsage(
            self.pid,
            shut_event=self.stop_event
        )
        self.monitor_system_usage_thread.name = "System Usage Thread"

        #
        self.pub_data: SynSTH.PublishStatus = SynSTH.PublishStatus(
            self.broker_address,
            self.broker_port,
            self.pdata_topic,
        )
        self.pub_data.daemon = True  #when main thread is closed, close it.
        self.pub_data.name = "Publish Thread"

        # New a keyboard stop thread
        self.gui_stop_thread: threading.Thread = threading.Thread(
            target=self.GUIStopThread,
            name="manual stop thread"
        )
        #
        self.remote_stop_thread: threading.Thread = threading.Thread(
            target=self.RemoteStopThread,
            name="remote stop thread"
        )
        self.remote_record: threading.Thread = threading.Thread(
            target=SynSTH.RemoteRecord,
            name="remote start/stop record"
        )

        self.print_thread: Printer.PrintThread = Printer.PrintThread()

        self.pub_state: SynSTH.PublishStatus = SynSTH.PublishStatus(
            self.broker_address,
            self.broker_port,
            self.pdata_topic
        )

        self.role: str = role
        self.running_state: bool = True

        msg: str = f'{self.role} is initialized.'
        self.ShowMsg(self.log_topic, func_name, msg)

        self.sock: Optional[socket.socket] = None
        # Event to check is connecting the correct STH
        self.STH_Cflag: ctypes.c_bool = connected_flag

        # 
        self.max_retries: int = 3
        self.sth_scan: queue = queue.Queue()

    @property 
    def pid(self) -> int:
        return self._pid

    @pid.setter
    def pid(self, pid: int) -> None:
        self.pid = pid

    def ShowMsg(self, topic: str, key: Any, msg: Any) -> None:
        timetag: str = time.strftime("%H:%M:%S", time.localtime())
        print(f'[INFO: {timetag}] <STHComm> {msg}')
        self.pub_state.FuncLogPub(topic, {key: '[' + timetag + '] ' + msg})

#-------------
    def CheckMac(self, ip: str
                 ) -> tuple[int,
                            Optional[subprocess.CompletedProcess[str]],
                            str]:
        #TODO: This function can be independent
        try:
            if platform.system() == "Windows":
                command = ['arp', '-a', ip]
                encoding = "big5"
            else:
                command = ['arp', '-n']  # '-n' to show addresses numerically (IP addresses)
                encoding = "utf-8"  # Adjust encoding if necessary

            proc_ret: subprocess.CompletedProcess = \
                subprocess.run(command,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               encoding=encoding,
                               timeout=2,)
            
                # Output the result
            if platform.system() != "Windows":
                # Filter output for the specific IP address on Linux
                proc_ret = subprocess.run(
                    ['grep', ip],
                    input=proc_ret.stdout,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    encoding=encoding,
                    timeout=2,
                )

            if (ret := proc_ret.returncode) == 0:
                cmp_pattern: str = r'([0-9a-fA-F\-\:]{17})' #r'([0-9a-fA-F-]{17})' matches a sequence of 17 characters 
                output: str = proc_ret.stdout
                match: Optional[Match] = re.search(cmp_pattern, output)

                target = '-' if platform.system() == "Windows" else ':'

                mac: str = match.group(1).replace(target, '') if match else ''
                match is None and print("[TRAC] <CheckMac> No correct mac!\n")
            else:
                error: str = proc_ret.stderr
                print(f"[TRAC]  <CheckMac> error: {error}")

        except Exception as err:
            print(f"[TRAC]  <CheckMac> Unexpected {err=}, {type(err)=}")
            return -1, None, ''

        else:
            return ret, proc_ret, mac

    #-------------initialize communication with a STH with retry 3 times

    def InitSocket(self, host: str, port: int,
                   max_retries: int = 2,
                   retry_delay: int = 1
                   ) -> Optional[socket.socket]:
        # Create a new socket
        try:
            # sock as tcp server resource
            sock: socket.socket = socket.socket(socket.AF_INET,
                                                socket.SOCK_STREAM)
        except socket.error as msg:
            sys.stderr.write(f"[ERROR]  {msg}\n")
            sys.exit(1)

        # Set socket options
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        server_address: tuple[str, int] = (host, port)
        retries: int = 1
        while retries < max_retries:
            try:
                # Connect to the remote server
                sock.bind(server_address)

                #maximum queuing number for incoming connections
                sock.listen(3)
                sock.settimeout(30)  #timeout for listening

            except socket.error as e:
                error_code: int = e.errno
                logging.error(str(e))
                print(f"[TRAC]  <InitSocket> Socket error occurred.  Error code: {error_code}")
                # Close the existing socket
                sock.close()

                # Increment the retry count
                retries += 1
                #TODO: use printer thread to print out
                # and error_code will be the input
                if error_code == 10054:
                    print("[TRAC]  <InitSocket> Connection reset by peer.  "
                          + f"Retrying in {retry_delay} seconds...")
                elif error_code == 10038:
                    print(f"[TRAC]  <InitSocket> Socket operation on non-socket.  "
                          + f"Retrying in {retry_delay} seconds...")
                else:
                    print(f"[TRAC]  <InitSocket> Other socket error.  "
                          + f"Retrying in {retry_delay} seconds...")

                time.sleep(retry_delay)

            else:
                # Return the socket if connection is successful
                return sock
        else:
            print("[TRAC]  <InitSocket> Maximum retries exceeded. "
                  + "Unable to establish the connection.")
            #raise
            # Return None if connection couldn't be established
            return None

    #-------------
    # esnure the mac and port are correct when connecting with a STH
    def SecureTargetMac(self, t_mac: str, t_port: int,
                        security: bool = False,
                        ) -> bool:
        retries: int = 0
        msg: str

        #TODO: in built-in function function:
        # print(`STHComm` -> {func_name}) is better?
        # clear flag of STH connected
        self.STH_Cflag.value = False
        connected: bool = self.STH_Cflag.value
        #
        while retries < self.max_retries and not connected:
            # Initialize TCP/IP socket
            sock: Optional[socket.socket] = self.InitSocket(self.STH_host,
                                                            t_port)
            print("[TRAC]  <STHComm.SecureTargetMac> "
                  + f'scans MAC: {t_mac} via port: {t_port} in sock:{sock}')

            if sock is not None:
                try:
                    csock, adr = sock.accept()  # Accept incoming connections
                except:
                    print('[TRAC]  <STHComm.SecureTargetMac> '
                          + f'scans MAC: {t_mac} via port:{t_port} now time-out.')
                    break
                ret, proc_ret, mac = self.CheckMac(csock.getpeername()[0])
                # set timeout when receiving sockets
                csock.settimeout(self.socket_timeout)
                msg = f'{self.role} tries to connect a STH: {csock}'
                self.ShowMsg(self.log_topic, func_name, msg)

                if (security and (t_mac == mac)) or (not security):
                    msg = f'Great! Target MAC: {self.STH_mac} ' \
                        + f'with current MAC: {mac} ' \
                        + f'via port: {sock.getsockname()[1]}'
                    self.ShowMsg(self.log_topic, func_name, msg)
                    self.sock = sock
                    self.csock = csock
                    connected = True
                    self.STH_Cflag.value = connected
                    self.max_retries = 0    # no more try to connect a STH
                    self.sth_scan.put(True) # put a True into the queue
                    return True

                else:
                    msg = f'A thread with current MAC: {mac} '\
                        + f'does not match the target MAC: {self.STH_mac} '\
                        + f'via Edge port: {sock.getsockname()[1]} is closed'
                    self.ShowMsg(self.log_topic, func_name, msg)
                    #TODO: move two line code under this line
                    # out of this function to be more clear
                    csock.send(b'cmd\n')
                    time.sleep(1)
                    csock.send(b'sleep\n')
                    time.sleep(1)
                    csock.close()
                    sock.close()

            retries += 1
            print('[TRAC]  <STHComm.SecureTargetMac> '
                  + f'retries {retries} times to scan port# {t_port}.')
            time.sleep(0.1)

        print('[NOTE]  <STHComm.SecureTargetMac> '
              + f'stops to scan MAC: {t_mac}, port: {t_port}.')
        self.sth_scan.put(False)
        return False

    #-------------
    def ReceiveMessage(self, csock: Optional[socket.socket],
                       index: int = 0
                       ) -> tuple[int,
                                  Optional[Union[bytes, bool]],
                                  datetime.datetime]:
        """Receive raw message from STH Communicate board

        Args:
            csock (Optional[socket.socket]): a new socket \\
                representing the connection by `socket.accept()`
            index (int, optional): _description_. Defaults to 0.

        Returns:
            tuple[int, Optional[Union[bytes, bool]], datetime.datetime]
        """
        # Distinguish whether an exception condition occurred
        # or data was not obtained.
        # error happened: None
        # no csock: False
        message: Optional[Union[bytes, bool]] = None
        recv_time: Optional[datetime.datetime] = None
        try:
            #TODO: find and check argument in `csock.recv`
            # which number is better,
            # to judge the parameter of max length received bytes
            # should bigger than 1 packet or not.
            message_: bytes | bool = csock.recv(
                self.package_length) if csock else False
            recv_time = datetime.datetime.now()

        except socket.timeout:    #break loop after timeout
            self.stop_event.set()
            self.reconnect_event.set()
            logging.warning(
                f'Connection of {self.role} is time-out.  '
                + 'Another thread is initialized.')

        except socket.error as e:
            csock.close() if csock else 0
            logging.error(f'Connection of {self.role} is {e}.  '
                          + 'Another thread is initialized.')
            logging.warning(traceback.format_exc())
            self.stop_event.set()
            self.reconnect_event.set()

        else:
            index += 1
            message = message_
        finally:
            if recv_time is None:
                return index, message, datetime.datetime.now()

            return index, message, recv_time

    #-------------

    def SaveData(self, msgs: list[messageType] | messageType, mode: bool
                 ) -> list[str]:
        """Save raw data with the `socket.recv` time \\
            as its filename in four decimals.

        Args:
            msgs (list[messageType] | messageType): The message \\
                received time and its data are being saved.
            mode (bool): To save the message or not.

        Returns:
            list[str]: The filenames of saved file.
        """
        time_string_list: list[str] = []
        if isinstance(msgs, list):
            time_string_list = [self.SaveData(msg, mode)[0] for msg in msgs]
        else:
            message, timestamp = msgs
            # from six-digit milliseconds get four digits
            time_string: str = timestamp.strftime("%Y-%m-%d-%H-%M-%S-%f")[:-2]
            file_path: str = self.source_path + time_string

            if mode:    # True to save data in txt
                with open(file_path + '.txt', 'w+') as file:
                    file.write('\n' + message + '\n')
                #   f.write(bytes(message, encoding='utf-8'))
            #print(f"\n{time_string}:  {len(message.split())}\n", flush=True)
            return [time_string]
        return time_string_list

    #-------------
    def ChkEvent(self):
        print(f'stop_event: {self.stop_event.is_set()}')
        print(f'stop_collect: {self.stop_collect.is_set()}')
        print(f'stop_check_header: {self.stop_check_header.is_set()}')
        print(f'stop_save: {self.stop_save.is_set()}\n')

    #--------------------------
    # stop by @even: stop_event -> enable @event: stop_collect
    #--------------------------

    def CollectThread(self) -> None:

        port_list: list[int] = [self.Edge_target_port,
                                self.Edge_base_port]
        port_list[0] == port_list[1] and port_list.pop()

        msg: str = f'Scans ports will be: {port_list}.'
        #print(f'[TRAC]  <STHComm.CollectThread> {msg}')
        self.ShowMsg(self.log_topic, func_name, msg)

        t_mac: str = self.STH_mac
        secure: bool = False if t_mac == '' else True

        def ScanThread(port: int, /,
                       target_mac: str = t_mac,
                       security: bool = secure,

                       ) -> threading.Thread:
            # scan ports in the list to find the target STH
            return threading.Thread(target=self.SecureTargetMac,
                                    name=f"#{port}",
                                    args=(target_mac, port, security))

        [ScanThread(port).start() for port in port_list]    # type: ignore

        print('[TRAC]  <STHComm.CollectThread> starts to scan STH...')

        start_time: float = time.time()
        while not self.csock:
            try:
                time.sleep(1)
                if self.sth_scan.qsize() >=2:
                    if not any([self.sth_scan.queue[i] for i in range(2)]):
                        self.stop_event.set()
                        msg = f'None of STH are detected.'
                        print(f'[TRAC]  <STHComm.ScanThread> {msg}')
                        break

            except KeyboardInterrupt: break
            if time.time() - start_time > max_time_out: 
                self.stop_event.set(); break                

        msg = f'is receiving data from the target STH...'
        print(f'[TRAC]  <STHComm.CollectThread> {msg}')
        self.ShowMsg(self.log_topic, func_name, msg)
        self.reconnect_event.clear()

        message_index: int = 0
        message_temp: str = ''

        timestamp_list: list[datetime.datetime] = []
        add_delimiter: Callable[[str, str], str] = lambda x, y: \
            x + self.delimiter + y

        while True:
            # Receive message from client
            #start: float = timer()
            message_index, message_, timestamp = self.ReceiveMessage(
                self.csock, message_index)

            if message_:  #pass non-message
                #TODO: timeit!!
                #start_msg_timer: float = timer()
                message: str = functools.reduce(add_delimiter,
                                                map(str, bytearray(message_)))
                message_temp += message

                #TODO: can check header before change data type
                header: dict = HeaderSplit.HeaderInformation(message) #, self.delimiter)

                if header:
                    self.header_result = header

                    #NOTICE: use the first timestamp of i-th package's data
                    # to be filename
                    message_list: messageType = (
                        message_temp,
                        timestamp_list[0] if timestamp_list
                        else timestamp
                    )
                    self.buffer.append(message_list)

                    message_temp = ''
                    timestamp_list.clear()

                else:
                    #add `delimiter` between two packet
                    message_temp += self.delimiter
                    timestamp_list.append(timestamp)

            else:
                # handle disconnect from socket client
                self.csock.close() if self.csock else 0
                self.stop_event.set()
                self.reconnect_event.set()
                logging.warning(f'Connection of {self.role} is disconnect. '
                                + 'Another thread is initialized')

            if self.stop_event.is_set():
                self.stop_collect.set()

                msg = f'<CollectThread> is stop.'
                print(f'[TRAC]  <STHComm> {msg}')
                self.ShowMsg(self.log_topic, func_name, msg)
                #self.ChkEvent()
                break

        self.csock.close() if self.csock else 0
        self.sock.close() if self.sock else 0

        msg = f'{self.role} closes the connection with the STH.'
        self.ShowMsg(self.log_topic, func_name, msg)

    #--------------------------
    # stop by @even: stop_check_header -> enable @event: stop_save
    #--------------------------

    def SaveThread(self) -> None:
        while True:
            self.save_event.wait()    #wait for event trigger to save data
            message_list: list[messageType] = []

            while self.buffer:
                message_list.append(self.buffer.popleft())

            #start = timer()
            # get record_raw_data from MqttSub
            file_list: list[str] = self.SaveData(message_list,
                                                 SynSTH.record_raw_data)

            self.save_event.clear()

            if self.stop_check_header.is_set() and not self.buffer:
                #TODO: save and clear all data in buffer!
                self.stop_save.set()

                msg: str = f'<SaveThread> is stop'
                print(f'[TRAC]  <STHComm.CollectThread> {msg}')
                self.ShowMsg(self.log_topic, func_name, msg)
                #self.ChkEvent()
                break

    #--------------------------
    # stop by @even: stop_collect -> enable @event: stop_check_header
    #--------------------------

    def BridgeThread(self) -> None:
        publish_rawdata_gap: int = int((3 + 1) * (  # 3 char + 1 delimiter
            (self.header_length + 1) + ((3 + 4 * 6 + 3) + 1)  # 55 + 31
        ))
        # 4 * (55 + 31) = 344

        packet_number: int = -1
        while True:
            #REVIEW: Remove `event.wait()`, and let each data in the buffer
            # contain at least 1 header so that this thread will verify
            # the packet sequence number to publish out/refresh.

            packet_number_: int = self.header_result.get(
                "Packet Sequence Number", -1)
            packet_number = (packet_number_ if (
                new_packet := (packet_number_ > packet_number))
                else packet_number)

            if new_packet and self.buffer:
                header: dict = self.header_result
                try:
                    data_temp: messageType = self.buffer[-1]

                except IndexError:
                    #TODO: SaveThread get the element in buffer first,
                    # let new thread to open rawdata with the newest file,
                    # process and publish out.
                    print(f'None value in buffer\n{self.buffer = }')
                except Exception:
                    print(f'[WARN]  raw_data is not available')

                else:
                    self.monitor_packet_loss_thread._header = header

                    #REVIEW: try to remove try-except
                    if len(data_temp[0]) > publish_rawdata_gap:
                        self.pub_data.data_queue.append(
                            (data_temp, header)
                        )
                        if self.pub_data.trigger_event.is_set():
                            continue
                        self.pub_data.trigger_event.set()

                finally:
                    self.save_event.set()

            if self.stop_collect.is_set():
                self.stop_check_header.set()

                self.save_event.set()
                print('[TRAC]  <STHComm.CheckHeaderThread> breaks.')
                #self.ChkEvent()
                break

    #--------------------------
    # stop by manual -> enable @event: stop_event
    #--------------------------

    def GUIStopThread(self):
        print('[Action]  press Ctl-C to stop')
        while not self.stop_event.is_set():
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                print("[TRAC]  <STHComm.GUIStopThread> "
                      + "stops all threads, manually.")
                self.stop_event.set()    #stop other threads
                #self.ChkEvent()
                break

    #--------------------------
    # stop by remote -> enable @event: stop_event
    #--------------------------

    def RemoteStopThread(self):
        #REVIEW: Check the shared variable state between two process.
        while not self.stop_flag.value:
            time.sleep(1)
            if SynSTH.close_comm:
                print("[TRAC]  <STHComm.RemoteStopThread> "
                      + "stops all threads, remotely.")
                self.stop_event.set()    #stop other threads
                #self.ChkEvent()
                break

        self.stop_event.set()  #REVIEW: stop all threads in this process

    #-------------
    def run(self) -> None:
        msg: str = f'Title:  {self.role} {version}'
        self.ShowMsg(self.log_topic, func_name, msg)
        # LogMessage(self.log_file)

        self.collect_thread.start()
        self.save_thread.start()
        self.bridge_thread.start()
        self.remote_stop_thread.start()
        #DEBUG: thread bomb is fixed by passing the Runtime error
        self.remote_record.start()

        # new thread
        #self.monitor_packet_loss_thread.start()
        self.monitor_system_usage_thread.start()
        self.pub_data.start()

        msg = f'{self.role} in Pid:{self.pid} ' \
            + 'is ready to communicate with a STH...'
        self.ShowMsg(self.log_topic, func_name, msg)

        #TODO: can write 2 sheets at the same time by using `openpyxl`
        self.monitor_system_usage_thread._save_done_event.wait()
        save_time: threading.Thread = threading.Thread(
            None, save_usage, "Save Runtime Thread",
            (self.pub_data.return_data_list[1:], (
                "total_processing_time",
                "parse_data_total_time",
                "rest_in_queue"),  #pass setup value
             self.monitor_system_usage_thread.output_path,
             "Runtime Interval",
             'a',
             )
        )
        save_time.start()
        self.monitor_system_usage_thread._save_done_event.clear()

        # these thread needs to be finished
        self.save_thread.join()
        save_time.join()

        msg = f'{self.role} Pid:{self.pid} is terminated.'
        self.ShowMsg(self.log_topic, func_name, msg)
        self.running_state = False

        #return False if self.reconnect_event.is_set() else True

# In[]
def RemoteCtl(
    connected_state: ctypes.c_bool,
    parameter: Optional[CommunicationModule] = None,
    stop_connecting_event: Optional[ctypes.c_bool] = None,
):
    global master, slave

    cs_m, cs_s = None, None
    comm_alive = False
    #TODO: `SynSTH.RemoteComm` will make thread bomb
    remote_cmd = threading.Thread(target=SynSTH.RemoteComm,
                                  name="Remote Cmd Thread")
    remote_cmd.start()
    print(f'[TRAC]  <STHComm.RemoteCtl> in Pid:{os.getpid()} '
          + f'is waiting for SynSTH.enable_comm to be True.')

    # Create the event
    #connecting the correct STH?
    stop_connecting_event = mp.Value(
        ctypes.c_bool, False, lock=False) if stop_connecting_event is None \
        else stop_connecting_event

    while ((not SynSTH.close_comm or comm_alive)
           and not stop_connecting_event.value):
        if SynSTH.enable_comm or comm_alive:

            if not master:
                cs_m = CommSTH(role='master',
                               connected_flag=connected_state,
                               preset=parameter if isinstance(
                                   parameter, CommunicationModule) else None,
                               stop_flag=stop_connecting_event)
                master = True
                comm_alive = True
                cs_m.run()
                if cs_m.reconnect_event.is_set():
                    break
                else:
                    master = False
                    gc.collect()    # Garbage Collection

            if not slave:
                cs_s = CommSTH(role='slave',
                               connected_flag=connected_state,
                               preset=parameter if isinstance(
                                   parameter, CommunicationModule) else None,
                               stop_flag=stop_connecting_event
                               )
                slave = True
                cs_s.run()

                if cs_s.reconnect_event.is_set():
                    break
                else:
                    slave = False
                    gc.collect()
        else:
            master = slave = False
        time.sleep(1)

    remote_cmd.join()
    print(f'[TRAC]  <STHComm.RemoteCtl> Pid:{os.getpid()} '
          + 'inside of RemoteCtl is close.')

#%%    MAIN cell
if __name__ == '__main__':
    preset_parameter: Optional[CommunicationModule]
    if len(sys.argv) >= 2:
        _, mac, *port = sys.argv
        if port:
            preset_parameter = CommunicationModule(mac, port[0])
        else:
            preset_parameter = CommunicationModule(mac)

    else:
        preset_parameter = None

    msg = f'{version}'
    # os.system('title ' + msg)
    print(msg)

    connected_state: ctypes.c_bool = mp.Value(ctypes.c_bool, False,
                                              lock=False)
    stop_connecting_event: threading.Event = threading.Event()
    RemoteCtl(connected_state, preset_parameter)  #, stop_connecting_event
    #connected_event: threading.Event = threading.Event()
    #cs_m: CommSTH = CommSTH(role='master', event=connected_event)
    #cs_m.run()

    print('[TRAC]  <STHComm.main> will be close in 10 sec.')
    SynSTH.close_comm = True  # type: ignore    # To stop the SynSTH thread
    print('[TRAC]  <STHComm.main> is close, finally.')

#%%
