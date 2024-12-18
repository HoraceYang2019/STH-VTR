# -*- coding: utf-8 -*-
"""
Created on Mon Apr 24 16:51:53 2023

@author: MilkTea_shih, Horace Yang
"""

# In[0]:
version: str = 'STHSync v5.0'

#%%
import ast
import collections
import datetime
import logging
import json
import os
import paho.mqtt.client as mqtt  # type: ignore
import paho.mqtt.subscribe as subscribe  # type: ignore
import queue
import socket
import threading
import time
from typing import Any, Deque, Union
from types import ModuleType

#customized functions
import ParseData
import UpdateSTHParm as usp

DataFormat = tuple[float, float, int]

# In[1]
def SetParameter(set_p: Union[ModuleType, Any]):  #Any -> toUpdate
    #syn_topic: str = usp.init.sync_topic
    r_scan: str = usp.init.remt_scan_topic
    r_comm: str = usp.init.remt_comm_topic
    r_pars: str = usp.init.remt_pars_topic
    r_recd: str = usp.init.remt_recd_topic
    r_merg: str = usp.init.remt_merg_topic
    r_emul: str = usp.init.remt_emul_topic

    pdata: str = usp.init.pdata_topic
    reload: bool = usp.init.reload_parameter
    address: str = set_p.broker_address
    port: int = set_p.broker_port
    record: bool = set_p.record_raw_data
    return r_scan, r_comm, r_pars, r_recd, r_merg, r_emul, pdata, reload, address, port, record

remt_scan_topic, remt_comm_topic, remt_pars_topic, remt_recd_topic, remt_merg_topic, remt_emul_topic, \
    pdata_topic, reload_parameter, broker_address, broker_port, record_raw_data = \
    SetParameter(usp.init) if not usp.updated_state else SetParameter(usp.updated)

enable_scan, enable_comm, enable_pars, enable_merg, enable_emul = True, True, True, False, True
close_scan, close_comm, close_pars, close_merg, close_emul = False, False, False, False, False
loop_scan: bool = False
timeout: int = 10

func_msg = {'Standby': 'reset for standby',
            'Enable': 'enable for running',
            'Close': 'close for finishing',
            'Loop': 'enable with loop',
            }
mqtt_sleep_delay: float = 0.2
#%%
def LogMessage():
    logging.basicConfig(filename=usp.init.log_file,
                        filemode='a',
                        format='[%(levelname)s]: %(asctime)s %(message)s',
                        level=logging.WARNING)

#%%
def subscribe_with_timeout(broker, broker_port, topic, timeout):
    # Define a function to handle the subscription
    def subscription_handler(queue) -> None:
        try:
            msg: mqtt.MQTTMessage = subscribe.simple(topic,
                                                     0,
                                                     hostname=broker,
                                                     port=broker_port)
            queue.put(ast.literal_eval(msg.payload.decode("UTF-8")))
        except:
            pass

    result_queue = queue.Queue()
    subscription_thread = threading.Thread(None,
                                           subscription_handler,
                                           None,
                                           (result_queue,))

    # Start the subscription thread
    subscription_thread.start()

    # Wait for the subscription thread to complete or timeout
    #REVIEW: passing `RuntimeError`
    try:
        subscription_thread.join(timeout)
    except RuntimeError:
        pass
    except Exception as error:
        print(error)
    if result_queue:
        return result_queue.get()
    else:
        return None
    #if subscription_thread.is_alive():
    #    return None #{'Function': 'close'} # auto timeout
    #else:
    #    return result_queue.get()

#%%
def RemoteRecord():
    global record_raw_data, close_comm

    state_msg = {'0': 'Stop Record',
                 '1': 'Start to Record'
                 }
    key = 'State'
    while not close_comm:
        message_payload = subscribe_with_timeout(
            broker_address, broker_port, remt_recd_topic, timeout)

        if isinstance(message_payload, dict):
            try:
                cmd = str(message_payload['State'])
                #REVIEW: catch error input, but maybe it has not to assert!
                #NOTICE: I only change code in this writing style here.

                if cmd == '0':
                    record_raw_data = False
                elif cmd == '1':
                    record_raw_data = True
                else:
                    assert False, "Incorrect KEY or VALUE"
            except Exception:
                print(f"{key=}: {cmd=}")
            else:
                print(f'\n[INFO]  <RemoteRecord> is to {state_msg[cmd]}.')

        else:
            print(f"Wrong data type, please uses type of dictionary")

        time.sleep(mqtt_sleep_delay)

#%%
def RemoteScan():
    global enable_scan, close_scan, loop_scan

    while True:
        message_payload = subscribe_with_timeout(
            broker_address, broker_port, remt_scan_topic, timeout)
       # print(f'received: {message_payload}')

        if isinstance(message_payload, dict):
            try:
                cmd = str(message_payload['Func'])
                print(f'\n[INFO]  <RemoteScan> is to {func_msg[cmd]}.')

                if cmd == 'Standby':
                    enable_scan = False
                    close_scan = False
                    loop_scan = False
                if cmd == 'Enable':
                    enable_scan = True
                    loop_scan = False
                if cmd == 'Loop':
                    enable_scan = True
                    loop_scan = True
                if cmd == 'Close':
                    close_scan = True
                    break
            except:
                pass
        time.sleep(mqtt_sleep_delay)
    return True

#%%
def RemoteComm():
    global enable_comm, close_comm

    while True:
        message_payload = subscribe_with_timeout(
            broker_address, broker_port, remt_comm_topic, timeout)

        if isinstance(message_payload, dict):
            try:
                cmd = str(message_payload['Func'])
                print(f'\n[INFO]  <RemoteComm> is to {func_msg[cmd]}.')

                if cmd == 'Standby':
                    enable_comm = False
                    close_comm = False
                if cmd == 'Enable':
                    enable_comm = True
                if cmd == 'Close':
                    close_comm = True
                    break
            except:
                pass
        time.sleep(mqtt_sleep_delay)
    return True

#%%
def RemotePars():
    global enable_pars, close_pars

    while True:
        message_payload = subscribe_with_timeout(
            broker_address, broker_port, remt_pars_topic, timeout)

        if isinstance(message_payload, dict):
            try:
                cmd = str(message_payload['Func'])
                print(f'\n[INFO]  <RemoteParm> is to {func_msg[cmd]}.')
                if cmd == 'Standby':
                    enable_pars = False
                    close_pars = False
                if cmd == 'Enable':
                    enable_pars = True
                if cmd == 'Close':
                    close_pars = True
                    break
            except:
                pass

        time.sleep(mqtt_sleep_delay)
    return True

#%%
def RemoteMerge():
    global enable_merg, close_merg

    while True:
        message_payload = subscribe_with_timeout(
            broker_address, broker_port, remt_merg_topic, timeout)

        if isinstance(message_payload, dict):
            try:
                cmd = str(message_payload['Func'])
                print(f'\n[INFO]  <RemotMerge> is to {func_msg[cmd]}.')
                if cmd == 'Standby':
                    enable_merg = False
                    close_merg = False
                if cmd == 'Enable':
                    enable_merg = True
                if cmd == 'Close':
                    close_merg = True
                    break
            except:
                pass

        time.sleep(mqtt_sleep_delay)
    return True

#%%
def RemoteEmulate():
    global enable_emul, close_emul

    while True:
        message_payload = subscribe_with_timeout(
            broker_address, broker_port, remt_merg_topic, timeout)

        if isinstance(message_payload, dict):
            try:
                cmd = str(message_payload['Func'])
                print(f'\n[INFO]  <RemotMerge> is to {func_msg[cmd]}.')
                if cmd == 'Standby':
                    enable_emul = False
                    close_emul = False
                if cmd == 'Enable':
                    enable_emul = True
                if cmd == 'Close':
                    close_emul = True
                    break
            except:
                pass

        time.sleep(mqtt_sleep_delay)
    return True
#%%
class PublishStatus(threading.Thread): # used to publish data

    def __init__(self, broker: str, port: int, pub_topic: str):
        threading.Thread.__init__(self)

        self.mqtt_broker: str = broker
        self.mqtt_port: int = port

        self.client_publish = mqtt.Client()
        try:
            self.client_publish.connect(self.mqtt_broker, self.mqtt_port)
        except socket.error as err:
            print(err)

        self.pub_topic: str = pub_topic
        #REVIEW: truly run in thread
        self.trigger_event: threading.Event = threading.Event()
        self.data_queue: Deque[tuple[messageType, dict]] = collections.deque([])
        #[(`total_processing_time`, `process_data_time`), ...]
        self.__data_list: list[DataFormat] = []

    def DataPub(self, timetag: datetime.datetime, header: dict, content: str):
        if header == 'Emul':
            self.client_publish.publish(self.pub_topic, json.dumps(content, indent=8), 0)
        else:
            self.client_publish.publish(
                self.pub_topic,
                json.dumps(ParseData.DataPublish(timetag.strftime("%Y-%m-%d %H:%M:%S.%f"), header, content),
                           indent=10),
                0)

    def FuncLogPub(self, topic: str, content: dict):
        self.client_publish.publish(topic, json.dumps(content, indent=9), 0)

    @property
    def return_data_list(self) -> list[DataFormat]:
        return self.__data_list

    def run(self) -> None:

        while True:
            self.trigger_event.wait()
            (raw_data, timetag), header = self.data_queue.popleft()
            parse_data_start: float = time.time()
            self.DataPub(timetag, header, raw_data)
            total_processing_time: float = (datetime.datetime.now()
                                            - timetag
                                            ).total_seconds()
            #print(total_processing_time)
            self.__data_list.append((total_processing_time,
                                     time.time() - parse_data_start,
                                     len(self.data_queue)))

            if self.data_queue:
                continue
            self.trigger_event.clear()

#%%
if __name__ == '__main__':

    os.system(f'Title:  {version}')
    LogMessage()
    pars_remote = threading.Thread(target=RemotePars(), name="DataProcess master & slave")
    pars_remote.start()
