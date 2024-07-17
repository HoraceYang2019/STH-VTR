# -*- coding: utf-8 -*-
"""
Created on Sat Apr 22 20:36:55 2023

@author: MilkTea_shih
"""

#%%
import threading

#%%
headerLength: int = 54      #header大小
mode_data_length: int = 4
mode0_data_num: int = 1016  #512
mode0_data_frame: int = 6   #24
mode0_buf_sizes: int = mode0_data_frame * mode0_data_num * mode_data_length  #24384 Bytes ~= 24 KB

#%%
class PrintThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        
        self.information: str = ''

    def run(self, source: str = '', txt: str = ''):
        #global TsEnd

        if source == 'C':    #from collect thread
            txt_length: int = len(txt[1])
            if txt_length != (mode0_buf_sizes + headerLength):  #24438
                self.information = f"\ncollect on \t'{txt[0]}'"
            else:
                txt = ''
                self.information = "\nTrue"
        elif source == 'S':    #from save thread
            self.information = f"\nsave on \t'{txt[0]}'"
        
        # print(self.information, flush=True, end='')
    
#%%
