# -*- coding: utf-8 -*-
"""
Created on Fri Jul 28 15:23:08 2023
@author: hao
"""

import pandas as pd
import os
import threading
import queue
from multiprocessing import current_process
import typing 
import types 
import sys
import time

import UpdateSTHParm as usp
import STHSync as SynSTH

# In[]
version: str = 'FileMerge v1.0.0'
target_file = 'merged.csv'

# In[]
def SetParameter(set_p: typing.Union[types.ModuleType, typing.Any]):  #Any -> toUpdate    
    l_topic: str = usp.init.log_topic
    o_path: str = set_p.output_path
    ret = [l_topic, o_path]
    return ret

[log_topic, folder_path] = \
    SetParameter(usp.init) if not usp.updated_state else SetParameter(usp.updated)

def worker_function(folder, output_queue):
    msg = f'Target folder: {folder}'
    print(msg)
    output_queue.put(msg)
    sys.stdout.flush()  # Flush the standard output to ensure real-time printing
        
    merged_df = pd.DataFrame()
    merged_csv = folder + target_file
    
    if not os.path.isfile(merged_csv): 
        for filename in os.listdir(folder):
            if filename.endswith('_.csv'):  # Ensure that only CSV files are considered
                file_path = os.path.join(folder, filename)
                
                msg = f"{file_path} is merging"
                output_queue.put(msg)
                sys.stdout.flush()  # Flush the standard output to ensure real-time printing                    
                print(msg)
                
                df = pd.read_csv(file_path)
            merged_df = pd.concat([merged_df, df], ignore_index=True)
    
        merged_df.to_csv(merged_csv, mode = 'w+', index=False)
    else: 
        print('File existed')
        
    msg = 'Finish!'
    output_queue.put(msg)
    sys.stdout.flush()  # Flush the standard output to ensure real-time printing
    print(msg)
    
def msg_consumer(mq):
    while True:
        try:
            msg = mq.get(timeout=1)
            print(msg)
        except queue.Empty:
            break
        
class MergeFile(object):
    def __init__(self):
        super().__init__()
        self.name = version
        print(f'Start: {self.name}[pid:{current_process().pid}] in {__name__}')
        
    def run(self):
        mq = queue.Queue()
        msg_consumer_thread = threading.Thread(target = msg_consumer, args=(mq,))
        msg_consumer_thread.start()
        
        remote_merge = threading.Thread(target = SynSTH.RemoteMerge, name="remote merge csv files")  
        remote_merge.start()
        once = True
        
        while not SynSTH.close_merg:
            if not SynSTH.enable_merg: 
                once = True
            else:
                if once:
                    job = threading.Thread(target = worker_function, args=(folder_path, mq))
                    job.start()
                    job.join()
                    once = False

            time.sleep(1)            
        msg_consumer_thread.join()
        remote_merge.join()
        
# In[]
if __name__ == '__main__':
    p4 = MergeFile()
    p4.run()  # Start the Jobs process in the main process
    
    