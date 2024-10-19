'''
Created on 2024-05-27 21:50:45
@author: MilkTea_Shih, Horace_Yang
input: STH_Jobs.json
output: communication results of STHComm and time summary of the total jobs
'''

#%%    Packages
import ctypes
import multiprocessing as mp
import subprocess
import pandas as pd
import time
from typing import Hashable
import os
import sys
import time
import paho.mqtt.client as pub
import paho.mqtt.subscribe as sub
import threading
import time
from typing import Any, Deque, Union
from types import ModuleType

# customized functions
import STHComm
import UpdateSTHParm as usp

# Variables
version: str = "runSTHJobs_v1_R0"
job_file_name: str = 'STH_Jobs.json'
coef_file:str = 'C:/VTR/RawData/Source/Data/coef.csv'
ConnectionFormat = tuple[ctypes.c_bool, STHComm.CommunicationModule]
ConnectionMap = dict[Hashable, dict[str, str]]
max_timeout: float = 180 # in sec

# for process communicate
job_mode: str = ''
cycle_state: bool = False
tool_changed: bool = False
check_interval: float = 0.001

def SetParameter(set_p: Union[ModuleType, Any]):  #Any -> toUpdate
    address: str = set_p.broker_address
    port: int = set_p.broker_port
    qos: int = usp.init.qos
    
    r_comm: str = usp.init.remt_comm_topic
    r_recd: str = usp.init.remt_recd_topic
    ready: str = usp.init.sth_ready_topic
    job: str = usp.init.sth_job_topic
    cnc: str = usp.init.sth_cnc_topic
    detect: str = usp.init.sth_detect_topic
    
    return address, port, qos, r_comm, r_recd, ready, job, cnc, detect

host, portNo, qos, remt_comm_topic, remt_recd_topic, sth_ready_topic,\
    sth_job_topic, sth_cnc_topic, sth_detect_topic = \
    SetParameter(usp.init) if not usp.updated_state else SetParameter(usp.updated)

STHClient = pub.Client(pub.CallbackAPIVersion.VERSION1)
STHClient.connect(host, portNo)

#%%
def create_mutex(mutex_name):
    # Create a new mutex or get a handle to an existing one
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
    # Check if the mutex already exists
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        print("Another instance is already running.")
        sys.exit(0)
    return mutex

#%%    Functions
def get_STHJOB():
    while True:
        msg = sub.simple(sth_job_topic, hostname=host, port=portNo, qos=qos)
        job_dict = dict(eval(msg.payload.decode('utf-8')))
        with shared_dict['lock']:
            shared_dict['job_mode'] = job_dict['Mode']

def get_STHCNC():
    while True:
        msg = sub.simple(sth_cnc_topic, hostname=host, port=portNo, qos=qos)
        try:    #"NCFile": null
            cnc_dict = dict(eval(msg.payload.decode('utf-8')))
        except Exception:
            pass
        cncKey = list(cnc_dict.keys())
        if len(cncKey) == 1:
            if cncKey[0] == 'Cycle':
                if cnc_dict['Cycle'] == 'Start':
                    with shared_dict['lock']:
                        shared_dict['cycle_state'] = True
                elif cnc_dict['Cycle'] == 'End':
                    with shared_dict['lock']:
                        shared_dict['cycle_state'] = False
            elif cncKey[0] == 'SpdTool':
                with shared_dict['lock']:
                    shared_dict['tool_changed'] = True

def set_connection(mac: str, port: str) -> ConnectionFormat:
    assert isinstance(port, str)
    return (mp.Value(ctypes.c_bool, False, lock=False),
        STHComm.CommunicationModule(mac, port))

def establish_connection(parameter: ConnectionFormat,
                        est_interval: float,
                        shared_dict: dict) -> float:
    connected_state, module_setup = parameter
     
    stop_event: ctypes.c_bool = mp.Value(ctypes.c_bool, False, lock=False)

    process: mp.Process = mp.Process(
    None, STHComm.RemoteCtl, module_setup.mac,
        (connected_state, module_setup, stop_event)
        )
    process.daemon = True  # Set the process as a daemon
    process.start() # start a process
    try_connect_time: float = time.time()
    interval_start_time = try_connect_time
    
    # send comm Enable
    STHClient.publish(remt_comm_topic, '{"Func":"Enable"}', qos)

    connect_timeout: bool = False 
    while not connected_state.value:
        time.sleep(0.1)
        if (time.time() - try_connect_time) > max_timeout:
            connect_timeout  = True  # exceed the specified timeout
            break 
           
    if not connect_timeout: # the assigned job is executed
        # success communicate send ready and start (record or detect) 
        ret = STHClient.publish(sth_ready_topic, '{"Ready":"1"}', qos)
        with shared_dict['lock']:
            shared_dict['tool_changed'] = False
            shared_dict['cycle_state'] = True 
        if shared_dict['job_mode'] == 'Reference':
            STHClient.publish(remt_recd_topic, "{'State':'1'}", qos)
        elif shared_dict['job_mode'] == 'Monitor':
            STHClient.publish(sth_detect_topic, "{'Cmd':'Start'}", qos)

        interval_start_time: float = time.time()

        while time.time() - interval_start_time < est_interval:
            # Tool changed or Cycle end    
            if (shared_dict['tool_changed'] == True) or (shared_dict['cycle_state'] == False):
                with shared_dict['lock']:
                    shared_dict['tool_changed'] = False
                if shared_dict['job_mode'] == 'Reference':
                    ret = STHClient.publish(remt_recd_topic, "{'State':'0'}", qos)
                elif shared_dict['job_mode'] == 'Monitor':
                    ret = STHClient.publish(sth_detect_topic, "{'Cmd':'End'}", qos)
                break
            time.sleep(0.001) # wait for completion of the threads of STHComm
    # normal end or timeout
    # stop record and comm
    if shared_dict['job_mode'] == 'Reference':
        ret = STHClient.publish(remt_recd_topic, "{'State':'0'}", qos)
    elif shared_dict['job_mode'] == 'Monitor':
        STHClient.publish(sth_detect_topic, "{'Cmd':'End'}", qos)
    ret = STHClient.publish(remt_comm_topic, "{'Func':'Close'}", qos)

    actual_interval: float = time.time() - interval_start_time
    stop_event.value = True # a signal to stop a process

    try:
        # kill this subprocess to provent memory leak
        process.kill()
    except AttributeError:
        del process
    except Exception as error:
        print(error)
    finally:
        del process

    return actual_interval

#%%
def runJobs(shared_dict, job_file: str = job_file_name) -> float:
    import json

    print(f'Running job with file: {job_file}')    
    with open(job_file, encoding="utf-8") as f:
        jobs = json.load(f)        

    run_time: list = []

    max_timeout = jobs['Timeout'] # get max_timeout from JSON file
    del jobs['Timeout']  

    # wait until cycle start send and tcode change 
    while (shared_dict['cycle_state'] != True) or (shared_dict['tool_changed'] != True):
        time.sleep(shared_dict['check_interval'])
    
    for tool_no in jobs.keys():   # focus on different jobs by tool ID 
        # get taget mac, port, and defualt interval time by Tool ID
        
        if os.path.exists(coef_file): os.remove(coef_file) # clear to find new one

        mac, port, interval = jobs[tool_no]['mac'], str(jobs[tool_no]['port']), jobs[tool_no]['interval']
        # build and set connection, and get data from STH
        run_time.append(round(establish_connection(
            set_connection(mac,port), interval, shared_dict), 4)) 

        print(f'{run_time = }') 
        # Reference only has 1 tool, break for loop and start merge file
        if shared_dict['job_mode'] == 'Reference':
            # merge files
            return (amount_processing_time := sum(run_time))

    # summarize the total processing time
    print(f'Sum: {(amount_processing_time := sum(run_time)):.3f}')
        
    return amount_processing_time

class STH_Jobs(mp.Process):
    def __init__(self, job_file, shared_dict):
        super().__init__()
        self.job_file = job_file
        self.shared_dict = shared_dict

    #%%
    def run(self) -> float:
        print('[TRAC]  Running subprocess:', os.getpid(), os.getppid())
        # run the jobs in the job file
        
        runJobs(self.shared_dict, self.job_file)
        print('Subprocess:', os.getpid(), os.getppid())

def main():
    # Create the mutex in the main process only
    """     if not hasattr(sys, 'frozen'):
        mutex = create_mutex(version) """
    # Check for existing mutex

    # wait until job_mode send
    while shared_dict['job_mode'] == '':
        time.sleep(shared_dict['check_interval'])
   
    # mutex = create_mutex(version)
    p = STH_Jobs(job_file_name, shared_dict)   #Create an instance of class STH_Jobs
  
    print("Starting subprocess.")
    p.start()
    p.join() 

    print('Main process:', os.getpid())

    # Release the mutex when the application exits
    # print("Releasing mutex.")
    # ctypes.windll.kernel32.ReleaseMutex(mutex)    

#%%    Main
if __name__ == '__main__':
    # for process global variable
    manager = mp.Manager()
    shared_dict = manager.dict()
    shared_dict['job_mode'] = job_mode
    shared_dict['cycle_state'] = cycle_state
    shared_dict['tool_changed'] = tool_changed
    shared_dict['check_interval'] = check_interval
    shared_dict['lock'] = manager.Lock()
    
    # listen topic and change process global variable
    get_STHJOB_th = threading.Thread(target = get_STHJOB)
    get_STHCNC_th = threading.Thread(target = get_STHCNC)    
    get_STHJOB_th.start()
    get_STHCNC_th.start()
    
    mp.set_start_method('spawn', force=True)

#     Ensure that sys.argv[0] is correct for the frozen executable
    if hasattr(sys, 'frozen'):
        mp.freeze_support()
        if mp.current_process().name == 'MainProcess':
            print("Running main() in frozen state.")
            main()
    else:
        print("Running main() in script state.") 
        main()