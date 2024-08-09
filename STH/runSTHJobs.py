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

# customized functions
import STHComm

# Variables
version: str = "runSTHJobs_v1_R0"
job_file_name: str = 'STH_Jobs.json'
coef_file:str = 'C:/VTR/RawData/Source/Data/coef.csv'
ConnectionFormat = tuple[ctypes.c_bool, STHComm.CommunicationModule]
ConnectionMap = dict[Hashable, dict[str, str]]
max_timeout: float = 45 # in sec

host: str = '10.0.0.103'
portNo: int = 1883
qos = 0
remt_comm_topic: str = 'STH/remt/comm'
remt_recd_topic: str = 'STH/remt/record'
sth_ready_topic: str = 'STH/RDY'
sth_job_topic: str = 'STH/JOB'
sth_cnc_topic: str = 'STH/CNC'
sth_detect_topic: str = 'STH/Pdetect'

job_mode: str = ''
cycle_state: bool = False
tool_changed: bool = False
complete_job: bool = False
check_interval: float = 0.001

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
    global job_mode
    while True:
        msg = sub.simple(sth_job_topic, hostname=host, port=portNo, qos=qos)
        job_dict = dict(eval(msg.payload.decode('utf-8')))
        job_mode = job_dict['Mode']

def get_STHCNC():
    global cycle_state, tool_changed
    while True:
        msg = sub.simple(sth_cnc_topic, hostname=host, port=portNo, qos=qos)
        cnc_dict = dict(eval(msg.payload.decode('utf-8')))
        cncKey = list(cnc_dict.keys())
        if len(cncKey) == 1:
            if cncKey[0] == 'Cycle':
                if cnc_dict['Cycle'] == 'Start':
                    cycle_state = True
                elif cnc_dict['Cycle'] == 'End':
                    cycle_state = False
            elif cncKey[0] == 'SpdTool':
                tool_changed = True

def set_connection(mac: str, port: str) -> ConnectionFormat:
    assert isinstance(port, str)
    return (mp.Value(ctypes.c_bool, False, lock=False),
        STHComm.CommunicationModule(mac, port))

def establish_connection(parameter: ConnectionFormat,
                        est_interval: float) -> float:
    global complete_job
    connected_state, module_setup = parameter
     
    stop_event: ctypes.c_bool = mp.Value(ctypes.c_bool, False, lock=False)

    process: mp.Process = mp.Process(
    None, STHComm.RemoteCtl, module_setup.mac,
        (connected_state, module_setup, stop_event)
        )
    process.daemon: bool = True  # Set the process as a daemon
    process.start() # start a process
    try_connect_time: float = time.time()
    interval_start_time = try_connect_time
    
    # TODO
    # send    MQTT Topic: STH/remt/comm {"Func": "Enable"}
    STHClient.publish(remt_comm_topic, '{"Func":"Enable"}', qos)

    connect_timeout: bool = False 
    while not connected_state.value:
        time.sleep(0.1)
        if (time.time() - try_connect_time) > max_timeout:
            connect_timeout  = True  # exceed the specified timeout
            break 
    # TODO  
    # send  MQTT Topic: STH/RDY {"Ready": "1"}
    # If reference
    #     send  MQTT Topic: STH/remt/record {"State": "1"}
    # If monitor
    #     send  MQTT Topic: STH/PDetect   {"Cmd": "Start"}
    STHClient.publish(sth_ready_topic, '{"Ready":"1"}', qos)
    if job_mode == 'Reference':
        STHClient.publish(remt_recd_topic, "{'State':'1'}", qos)
    elif job_mode == 'Monitor':
        STHClient.publish(remt_recd_topic, "{'Cmd':'Start'}", qos)
           
    if not connect_timeout: # the assigned job is executed
        interval_start_time: float = time.time()

        while time.time() - interval_start_time < est_interval:
            # TODO 
            # listen  MQTT Topic: STH/CNC {"Cycle": "End"}  
            # If reference
            #     send  MQTT Topic: STH/remt/record {"State": "0"}
            #     break the while loop
            # If monitor
            #     send  MQTT Topic: STH/PDetect  {"Cmd": "End"}   
            #     complete_job = True
            #     break the while loop
            while cycle_state != False:
                time.sleep(check_interval)
            if job_mode == 'Reference':
                STHClient.publish(remt_recd_topic, "{'State':'0'}", qos)
                break
            elif job_mode == 'Monitor':
                STHClient.publish(sth_detect_topic, "{'Cmd':'End'}", qos)
                complete_job = True     #??
                break
                
            time.sleep(1) # wait for completion of the threads of STHComm

            # TODO
            # listen MQTT Topic: STH/CNC {"SpdTool": {"TCode": /int/,  "RUL": /int/}}
            # if Tcode is changed -> break the while loop    
            if tool_changed == True:    #??
                tool_changed = False
                break

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
def runJobs(job_file: str = job_file_name) -> float:
    import json

    print(f'Running job with file: {job_file}')    
    with open(job_file, encoding="utf-8") as f:
        jobs = json.load(f)        

    run_time: list = []

    max_timeout = jobs['Timeout'] # get max_timeout from JSON file
    del jobs['Timeout']  

    # TODO
    # listen  MQTT Topic: STH/CNC {"Cycle": "Start"}      
    # cycle_start.wait()
    while cycle_state != True:
        time.sleep(check_interval)
     
    for tool_no in jobs.keys():   # focus on different jobs by tool ID 
        # get taget mac, port, and defualt interval time by Tool ID
        
        if os.path.exists(coef_file): os.remove(coef_file) # clear to find new one

        mac, port, interval = jobs[tool_no]['mac'], str(jobs[tool_no]['port']), jobs[tool_no]['interval']
        # build and set connection, and get data from STH
        run_time.append(round(establish_connection(
            set_connection(mac,port), interval), 4)) 

        print(f'{run_time = }') 
        # TODO
        # if Tcode is changed
        #     send  MQTT Topic: STH/PDetect  {"Cmd": "End"} 
        #     send  MQTT Topic: STH/remt/comm {"Func": "Disable"}
        # If monitor and complete_job
        #     send  MQTT Topic: STH/PDetect  {"Cmd": "End"}
        #     send  MQTT Topic: STH/remt/comm {"Func": "Disable"} 
        #     return  amount_processing_time 
        # If reference
        #     merge files
        #     return amount_processing_time
        if tool_changed == True:
            STHClient.publish(sth_detect_topic, "{'Cmd':'End'}", qos)
            STHClient.publish(remt_comm_topic, "{'Func':'Close'}", qos)
        if job_mode == 'Monitor' and complete_job:      #??
            STHClient.publish(sth_detect_topic, "{'Cmd':'End'}", qos)
            STHClient.publish(remt_comm_topic, "{'Cmd':'Close'}", qos)
        if job_mode == 'Reference':
            # merge files
            return amount_processing_time
        

    # summarize the total processing time
    print(f'Sum: {(amount_processing_time := sum(run_time)):.3f}')
        
    return amount_processing_time

class STH_Jobs(mp.Process):
    def __init__(self, job_file):
        super().__init__()
        self.job_file = job_file

    #%%
    def run(self) -> float:
        print('[TRAC]  Running subprocess:', os.getpid(), os.getppid())
        # run the jobs in the job file
        
        runJobs(self.job_file)
        print('Subprocess:', os.getpid(), os.getppid())

def main():
    # Create the mutex in the main process only
    """     if not hasattr(sys, 'frozen'):
        mutex = create_mutex(version) """
    # Check for existing mutex

    # TODO 
    # listen  MQTT Topic: STH/JOB {"Mode": "Monitor/Reference"}  
    # job_mode.wait()
    while cycle_state == '':
        time.sleep(check_interval)
   
    mutex = create_mutex(version)
    p = STH_Jobs(job_file_name)   #Create an instance of class STH_Jobs
  
    print("Starting subprocess.")
    p.start()
    p.join() 

    # TODO 
    # send    MQTT Topic: STH/remt/comm {"Func": "Disable"}
    STHClient.publish(remt_comm_topic, '{"Func":"Close"}', qos)
    print('Main process:', os.getpid())

    # Release the mutex when the application exits
    print("Releasing mutex.")
    ctypes.windll.kernel32.ReleaseMutex(mutex)    

#%%    Main
if __name__ == '__main__':   
    mp.set_start_method('spawn', force=True)
    
    get_STHJOB_th = threading.Thread(target = get_STHJOB)
    get_STHCNC_th = threading.Thread(target = get_STHCNC)
    
    get_STHJOB_th.start()
    get_STHCNC_th.start()
    
#     Ensure that sys.argv[0] is correct for the frozen executable
    if hasattr(sys, 'frozen'):
        mp.freeze_support()
        if mp.current_process().name == 'MainProcess':
            print("Running main() in frozen state.")
            main()
    else:
        print("Running main() in script state.") 
        main()