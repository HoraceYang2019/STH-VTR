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

# customized functions
import STHComm_13_r2 as STHComm

# Variables
version: str = "runSTHJobs_v1_R0"
job_file_name: str = 'STH_Jobs.json'
coef_file:str = 'C:/VTR/RawData/Source/Data/coef.csv'
ConnectionFormat = tuple[ctypes.c_bool, STHComm.CommunicationModule]
ConnectionMap = dict[Hashable, dict[str, str]]
max_timeout: float = 45 # in sec

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
def set_connection(mac: str, port: str) -> ConnectionFormat:
    assert isinstance(port, str)
    return (mp.Value(ctypes.c_bool, False, lock=False),
        STHComm.CommunicationModule(mac, port))

def establish_connection(parameter: ConnectionFormat,
                        est_interval: float) -> float:
    connected_state, module_setup = parameter

    stop_event: ctypes.c_bool = mp.Value(ctypes.c_bool, False, lock=False)
    # mp.set_start_method('spawn', True)
    process: mp.Process = mp.Process(
    None, STHComm.RemoteCtl, module_setup.mac,
        (connected_state, module_setup, stop_event)
        )
    process.daemon: bool = True  # Set the process as a daemon
    process.start() # start a process
    try_connect_time: float = time.time()
    interval_start_time = try_connect_time

    connect_timeout: bool = False 
    while not connected_state.value:
        time.sleep(0.1)
        if (time.time() - try_connect_time) > max_timeout:
            connect_timeout  = True  # exceed the specified timeout
            break 
    
    if not connect_timeout: # the assigned job is executed
        interval_start_time: float = time.time()  
        while time.time() - interval_start_time < est_interval:
            time.sleep(1) # wait for completion of the threads of STHComm
    
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

    for tool_no in jobs.keys():   # focus on different jobs by tool ID 
        # get taget mac, port, and defualt interval time by Tool ID
        
        if os.path.exists(coef_file): os.remove(coef_file) # clear to find new one

        mac, port, interval = jobs[tool_no]['mac'], str(jobs[tool_no]['port']), jobs[tool_no]['interval']
        # build and set connection, and get data from STH
        run_time.append(round(establish_connection(
            set_connection(mac,port), interval), 4)) 

        print(f'{run_time = }') 
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
    mutex = create_mutex(version)

    p = STH_Jobs(job_file_name)   #Create an instance of class STH_Jobs 
    
    print("Starting subprocess.")
    p.start()
    p.join() 
    print('Main process:', os.getpid())

    # Release the mutex when the application exits
    print("Releasing mutex.")
    ctypes.windll.kernel32.ReleaseMutex(mutex)    

#%%    Main
if __name__ == '__main__':
    # Set start method to 'spawn' to prevent re-executing the main script in child processes
    #      mp.set_start_method('spawn')
    #if mp.current_process().name == 'MainProcess':
    #    main()
    #else:
    #    print('[Note]  Another instance is terminated.') 
    
    # Set start method to 'spawn' to prevent re-executing the main script in child processes
    
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