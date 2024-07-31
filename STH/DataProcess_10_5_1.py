# -*- coding: utf-8 -*-
"""
Created on Tue Jul 11 18:02:25 2023
pip install pythonnet
pip install pypiwin32

TODO:
1. add "current_plan" in the initSTH_u.json after updating in Node-red
2. 

Usage:
  python DataProcess_x_y.py
    
@author: MilkTea_shih, Horace Yang
"""

#%%
import glob
import logging
import threading 
from multiprocessing import current_process
import numpy as np
import numpy.typing as npt
import os
import pandas as pd
import re
import shutil
import time
import datetime
from scipy.signal import detrend
import types 
import typing
import sys
import platform

#%%
import STHSense_2_0 as sth       # parse sensing data from STH 
import Denoise_1_1 as Denoise    # denoise of receiving data
import UpdateSTHParm_1_0 as usp  # get the updated and init parameters 
import STHSync_5_0 as SynSTH     # syc control of services fro STH
# import CalToolPolar_0_1 as ctp   # calculate tool polar 
import GetCalbraCoef_0_2 as gcr  # get the calbriation coefficients

version: str = 'DataProcess v10.5.1'
active = False
publish_msg = None
remote_enable = False
remote_stop = False
func_name = 'DataProcess'
data_places = 5  # data in 
ms_places = 3    # time in ms
# polar_folder = r'C:/VTR/RawData/Output/ToolPolar/'
if platform.system() == "Windows":    
    coef_file = "C:/VTR/RawData/Source/Data/coef.csv" 
else:
    coef_file = "/var/VTR/RawData/Source/Data/coef.csv"
data_in_seq = True    # 
txt_separtor = ' '

# ctp.cmd = '-t'                       # test a target file
# ctp.CSV_file = r'2022-01-24-23-04-03.txt_Nm.csv'  # assign a csv file
# ctp.polar_file = r't3.png'           # assign the polar name

#%%    Log errors         
def LogMessage():
    logging.basicConfig(filename = usp.init.log_file, 
                        filemode = 'a', 
                        format = '[%(levelname)s]: %(asctime)s %(message)s', 
                        level = logging.ERROR)
    
#%%
def SetParameter(set_p: typing.Union[types.ModuleType, typing.Any]):  #Any -> toUpdate
    b_addr: str = set_p.broker_address
    b_port: int = set_p.broker_port
    l_topic: str = usp.init.log_topic
    p_topic: str = usp.init.pdata_topic

    s_path: str = set_p.raw_data_folder  #source_path 
    o_path: str = set_p.output_path
    l_file: str = set_p.log_file
    
    k_data: float = float(set_p.keep_data_th)
    b_file: bool = bool(set_p.backup_raw_file)
    
    s_file: bool = bool(set_p.save_parsed_file)
    t_force: bool = set_p.trans_force    #if True change CH1 and CH2 to torque; else constant data
    t_average: float = float(set_p.time_average)
    c_mode: str = set_p.to_csv_mode
    w_time: float = float(set_p.parse_wait_time)

    t_csv: int = int(set_p.txt_num_in_csv)
    
    return b_addr, b_port, l_topic, p_topic, s_path, o_path, l_file, k_data, b_file, s_file, t_force, t_average, c_mode, w_time, t_csv

#%%
def ShowMsg(topic, key, msg):    
    timetag = time.strftime("%H:%M:%S", time.localtime())
    print(f'[INFO] [{timetag}] <DataProcess> {msg}')
    publish_msg.FuncLogPub(topic, {key: '[' + timetag + '] ' + msg})
    
#%%       
class DataProcess(object):
    def __init__(self, role):
        super().__init__()
        self.broker_addr, self.broker_port, self.log_topic, self.pdata_topic, self.source_path, \
        self.output_path, self.log_file, self.keep_data_th, self.backup_raw_file, self.save_parsed_file, \
        self.trans_force, self.time_average, self.to_csv_mode, self.wait_time, self.txt_num_in_csv = \
        SetParameter(usp.init) if not usp.updated_state else SetParameter(usp.updated)   
            
        self.sampling_interval: float = 1/3722
        if not os.path.exists(self.output_path):   os.makedirs(self.output_path) 
        
        self.now_time: str = datetime.datetime.now().strftime('(%Y-%m-%d-%H-%M)')
        self.index_time_tag: int = 0
        self.time_offset: np.float_ = np.float_(0)
        
        self.var_list: tuple[int, 
                        int, 
                        npt.NDArray[np.float_], 
                        tuple[float, float, float, float]] = (usp.init.total_ch, 
                                                              usp.init.STH_version, 
                                                              np.asarray(usp.init.calibration), 
                                                              usp.init.force_ratio)
        self.datetime_type: str = "%Y-%m-%d-%H-%M-%S-%f"
        self.index_time_tag: int = 0
        self.index_BX: int = 2   # 
        self.available_data: bool = False   
        self.disable_DP: bool = False

        self.role: str = role
        # self.cal_tool_polar = ctp.calToolPolar()

#%%
    def CalculateTime(self, f_list: list[str], t_format: str)  -> tuple[npt.NDArray[np.float64],  typing.Optional[list[datetime.datetime]]]:
        
        def FilenameIndex(f: list) -> typing.Union[tuple[int, int], None]:
            if f:
                target = r"[folder\\\.]" if platform.system() == "Windows" else r"[\\/\.]"
                
                # Get filename of the first file in this path to define the string type
                filename_time: list[str] = re.split(target, f_list[0])
                
                #time_re[-2]: filename_time;  time_[-1]: file_extension
                file_extension: int = len(filename_time[-1]) + 1  #+1: '.'
                time_string_start: int = len(filename_time[-2]) + file_extension
                
                return (time_string_start, file_extension)
            else:
                return None
            
        def Str2TimeSetter(t_start: int, t_end: int) -> typing.Callable:
            def Str2Time(x: str) -> typing.Union[datetime.datetime, None]:
                try:
                    res: datetime.datetime = datetime.datetime.strptime(x[-t_start:-t_end], t_format)
                except Exception:
                    return None
                else:
                    return res
            
            return Str2Time
        
        filename_index: typing.Union[tuple[int, int], None] = FilenameIndex(f_list)
        if filename_index:
            str2time_setter: typing.Callable = Str2TimeSetter(*filename_index)
                
            try:
                time_stamp: list[datetime.datetime] = list(filter(None, map(str2time_setter, f_list)))
            except ValueError as e:    #this folder has txt file not named by rul
                logging.warning(str(e))
                f_list.pop(0)
                if f_list != []:
                    time_diff, time_stamp = self.CalculateTime(f_list, t_format)  # type: ignore  #!!!
                else:
                    return (np.asarray(0, dtype='f8'), None)
            else:
                # get the time differences of the consecutive txt files
                time_diff_: tuple[float, ...] = tuple(map(lambda x: (x[1] - x[0]).total_seconds(), 
                                                       zip(time_stamp[:-1], time_stamp[1:])))            
                time_diff = np.asarray(time_diff_, dtype='f8')
            
        else:    #this folder is empty
            return (np.asarray(0, dtype='f8'), None)
        return (time_diff, time_stamp) #(time difference list, txt file time list)
    
    #%%
    def DataPreprocess(self, data: list[list[float]], coef: tuple[tuple[float, ...], tuple[float, ...]]) -> npt.NDArray[np.float_]:
        
        def DataDetrend(x_: npt.NDArray[np.float_], a: float, b: float) -> npt.NDArray[np.float_]:
            x: npt.NDArray[np.float_] = detrend(Denoise.wden(x_ , 'sqtwolog', 'soft', 'mln', 2, 'db3'))
            x *= a
            x += b
            return x 
        
        return np.asarray(tuple(map(DataDetrend, np.array(data).T, *coef))).T  #(data_row, channel)
    
    #%%
    def GetData(self, f_name: str) -> list[str]:
        with open(f_name, 'r') as f:
            try:
                next(f)    #skip the first line
            except:
                return None
            return f.readlines()
        
    def ParseData(self, f_list: list[str], 
                  t_list: npt.NDArray[np.float64], 
                  v_list: tuple[typing.Union[int, typing.Any], int, npt.NDArray[np.float_], tuple[tuple[float, ...], tuple[float, ...]]], 
                  n_folder: str, 
                  backup_raw: bool) \
        -> tuple[npt.NDArray[np.float_], npt.NDArray[np.float_]]:
        
        *variable_list, calbar_coef = v_list
        
        data_array: npt.NDArray[np.float_] = np.empty((0, variable_list[0]), float)    #[0]: total channels
        time_tag: npt.NDArray[np.float_] = np.array([])
        time_iter: float = 0.0
        
        0 if os.path.isdir(n_folder) else os.makedirs(n_folder)
            
        def Rate():
            ...
            
        def ConvertDataSetter(*v: typing.Union[int, npt.NDArray[np.float_]]) -> typing.Callable:
            def ConvertData(s: str) -> typing.Union[list[list[float]], None]:
                if len(s) > 138:
                    s_split: npt.NDArray[np.str_] = np.asarray(s.split(txt_separtor))
                    result: tuple[list, list[list[float]]] = sth.ParseRawData(s_split, *v)    
                    return result[1]  #!!!check temp[0] always '[]'
                else:
                    return None
            return ConvertData
        
        # Timetag of first file doesn't exist, so it will be made by multiplying data length and sampling rate
        first_file: str = f_list.pop(0)
        convert_data_setter: typing.Callable = ConvertDataSetter(*variable_list)
        
        for line, data in enumerate(self.GetData(first_file)):
            SG_data: list[list[float]] = convert_data_setter(data)
                
            if SG_data:
                #ch1, ch2, ch3, ch4 = DataPreprocess(zip(*s_list), t_rate)
                data_array = np.vstack((data_array, self.DataPreprocess(SG_data, calbar_coef)))
                    
                time_value: npt.NDArray[np.float_] = np.linspace(time_iter, len(SG_data)*self.sampling_interval, len(SG_data))
                time_tag = np.hstack((time_tag, time_value))
                time_iter += round(time_tag[-1], ms_places) # up to ms
            
        shutil.move(first_file, n_folder + os.path.basename(first_file)) if backup_raw else os.remove(first_file)
            
        for index, filename in enumerate(f_list):    #open files and process values
            content: list[str] = self.GetData(filename)
            msg = f'Parsing {os.path.basename(filename)}...'                
            ShowMsg(self.log_topic, func_name, msg) 
            
            for line, data in enumerate(content):
                SG_data = convert_data_setter(data)
                    
                if SG_data:
                    #ch1, ch2, ch3, ch4 = DataPreprocess(zip(*s_list), t_rate)
                    data_array = np.vstack((data_array, self.DataPreprocess(SG_data, calbar_coef)))
                        
                    if data_in_seq: # allocate all txt data in seqence
                        offset = round(len(SG_data)*self.sampling_interval, ms_places)  # up to ms
                        time_value = np.linspace(time_iter, time_iter + offset, len(SG_data))
                        time_iter += offset   
                    else:       # allocate each txt data by its time_tag (in file name)
                        time_value = np.linspace(time_iter, time_iter + t_list[index], len(SG_data))
                        time_iter += round(t_list[index], ms_places)
                    time_tag = np.hstack((time_tag, time_value))
                                    
            shutil.move(filename, n_folder + os.path.basename(filename)) if backup_raw else os.remove(filename)
        return (data_array, time_tag)
    
    #%%
    def CalculateTorque(self, x: npt.NDArray[np.float_]):
        return np.linalg.norm(x, ord = 2, axis = 1, keepdims = True)
    
    #%% 
    def AverageDataByTimetag(self, d_array: npt.NDArray[np.float_], tags: npt.NDArray[np.float_], 
                             t_average: float, threshold_BX: bool) \
        -> npt.NDArray[np.float_]:
            
        global available_data
        result_array: npt.NDArray[np.float_] = np.empty((0, d_array.shape[1] + 1), float)
        def AverageValue(x):
            #return np.linalg.norm(x, 2, 0, False)
            return np.average(x)
        
        time_start: float = 0.0
        time_end: float = 0.0
        
        sample_count: int = 0
        while(sample_count <= tags.size):    #i think time_sum should start at 1 because it just used in searching index
            time_end += t_average

            #find the number of time_tag between time_start and time_end
            sample_time_gap = 0.0 # if (sample_count % avg_time_calbr) == 0 else 0.00013  # 1/2 of 1/3722, sample rate:3722

            sample_size: int = tags[np.where(np.logical_and(time_start<tags, tags <= time_end + sample_time_gap))].size    ###update tags<time_end -> tags<=time_end
            if sample_size:    #time_index == 0 will break the while loop bc the index doesn't exist.
                data_mean: npt.NDArray[np.float_] = np.asarray(tuple(map(AverageValue, d_array[sample_count:sample_count + sample_size, :].T)))
                result_array = np.vstack((result_array, np.hstack((time_start, data_mean))))
        
                time_start = time_end
                sample_count += sample_size
            else:
                break

        max_force = 0
        try:
            max_force = max(result_array[:, self.index_BX])
        except:
            pass 
        if not self.available_data and max_force >= threshold_BX: 
            self.available_data = True
            
        return result_array, max_force
    
    #%% 
    def WriteCSVSetter(self, act: bool, st: typing.Any = '') -> typing.Callable:
        def WriteCSV(d: typing.Union[None, npt.NDArray, pd.core.frame.DataFrame] = None, s_name: str = ' '):
            
            df: pd.core.frame.DataFrame = pd.DataFrame(d, columns = usp.init.column_name \
                                                       if not self.trans_force else ['TimeTag', 'Torque', 'Bending-X', 'Bending-Y']) \
                if not isinstance(d, pd.core.frame.DataFrame) else d
            
            file_name = f"{self.output_path}{s_name}{temp}_.csv"
            df.to_csv(file_name, 
                      mode = w_mode, header = act, index = False, encoding = 'utf-8')
            return file_name
                
        temp: str = st if st == '' else f'_{type(st).__name__}'
        w_mode: str = 'w' if act else 'a'
        
        return WriteCSV
    
    #%%     
    def ShiftTimeSetter(self, st: datetime.datetime) -> typing.Callable:
        def ShiftTime(v: np.int_) -> datetime.datetime:
            return st + datetime.timedelta(microseconds=int(v))
        
        return ShiftTime
    
    def run(self): # thread start with this run function
        global remote_enable, remote_stop, publish_msg

        LogMessage()         
        publish_msg = SynSTH.PublishStatus(self.broker_addr, self.broker_port, self.pdata_topic)        
        
        msg = f'Title:  {version} with role: {self.role} in Pid:{current_process().pid}'
        os.system(msg)
        ShowMsg(self.log_topic, func_name, msg) 
        
        remote_cmd = threading.Thread(target = SynSTH.RemotePars, name="Remote Cmd Thread")
        remote_cmd.start()
        
        write_csv = self.WriteCSVSetter(True)
        msg = f'{self.role}> Pid:{current_process().pid} Start to parse files and and save in {usp.init.output_path}'
        ShowMsg(self.log_topic, func_name, msg) 
        
        # toolpolar
        # self.cal_tool_polar.start()          # start tool polar 
        # toolpolar
        
        while True:            
            if SynSTH.enable_pars:
                #file_list: list[str, ..., str] = os.listdir(input_path + folder)
                current_list: list[str] = glob.glob(os.path.join(self.source_path, '*.txt'))
                file_list = []; calbar_coef = []
                if os.path.exists(coef_file): os.remove(coef_file) # clear to find new one

                if current_list != []:
                    for i in range(self.txt_num_in_csv):
                        try:
                            file_list.append(current_list.pop(0))  # take files to proces
                        except:
                            pass
                    for i in file_list:
                        try:
                            data = DataProcess.GetData(self, i)
                            if data != None:
                                coef_exist, calbar_coef, header_mac = gcr.GetCoef(data.pop(0))
                        except:
                            coef_exist = False

                        if coef_exist:
                            break
                        else:
                            continue
                    if not any(calbar_coef):
                        calbar_coef = ((1.0, 1.0, 1.0, 1.0), (0, 0, 0, 0))
                    print(f'[TRAC]  calbar_coef: {calbar_coef}')
                    st: float = time.process_time()
              
                    time_diff, time_st_ = self.CalculateTime(file_list, self.datetime_type)
                    if time_st_:
                        time_st: datetime.datetime = sorted(time_st_)[0]
                        # Insert the median value from array at index 0
                        # time_diff = np.insert(time_diff, 0, round(np.median(time_diff), 4))
                        
                        try:
                            data_temp, time_tag = self.ParseData(file_list, time_diff, (*self.var_list[:-1], calbar_coef), f'{self.source_path}/{self.now_time}/', self.backup_raw_file)
                        except Exception as err:
                            print(f"Unexpected {err=}, {type(err)=}")
                            #time.sleep(self.wait_time)
                            continue
                        
                        #switch variable: change data type or not, if trans_force == True will change!
                        torque_array: npt.NDArray[np.float64] = np.hstack((self.CalculateTorque(data_temp[:, 0:2]), data_temp[:, 2:])) 
                        
                        data_array =  np.hstack((data_temp, torque_array[:,0].reshape(-1, 1))) if not self.trans_force else torque_array
                        #switch variable: average data or not, if time_average > 0 will average!

                        avg_data, max_force = self.AverageDataByTimetag(data_array, time_tag, self.time_average, self.keep_data_th)
                        save_data_array: npt.NDArray[np.float64] = np.round(avg_data \
                            if self.time_average > 0 else np.hstack((time_tag.reshape(-1, 1), data_array)), data_places)
        
                        if self.save_parsed_file:
                            save_data_timetag_, *save_data_ = save_data_array.T
                            save_data_timetag: npt.NDArray[np.int_] = np.rint(save_data_timetag_ * 1e6).astype(int)
                            
                            shift_time_setter: typing.Callable = self.ShiftTimeSetter(time_st)
                            temp: tuple[datetime.datetime, ...] = tuple(map(lambda x: x.strftime('%H:%M:%S.%f'), map(shift_time_setter, save_data_timetag)))
                            
                            save_data: pd.core.frame.DataFrame = \
                                pd.DataFrame(zip(*save_data_), \
                                              columns = usp.init.column_name[1:] \
                                                  if not self.trans_force else ['Torque', 'BendingX', 'BendingY'])
                                    
                            save_data.insert(0, "TimeTag", temp)  # add timetag to the data array
                            
                            try:
                                file_name = write_csv(save_data, time_st.strftime('%Y-%m-%d-%H-%M-%S.%f') + '-(' + header_mac + ')')

                                # toolpolar
                                if max_force > self.keep_data_th:
                                    target_file = os.path.basename(file_name)
                                    # shutil.copyfile(file_name, polar_folder + target_file)
                                    # print(f'copy from {file_name} to {polar_folder + target_file}')
                                    # ctp.cmd = '-t'
                                    # ctp.CSV_file = target_file
                                    # ctp.polar_file = r't3.png'
                                # toolpolar
                                    
                            except Exception as e:    #if the file is opening or other OSError will cache in this error                    
                                logging.warning('DataProcess: '+ str(e))
                                logging.warning(save_data)
            
                    et: float = time.process_time()
                
                    if file_list:    
                        msg: str = f'Available files in {sum(time_diff):.2f} (s)'  
                        msg = f'{msg} are processed in {(et - st):.2f} (s)'
                        ShowMsg(self.log_topic, func_name, msg) 
                    else:
                        print('.', end="")
                    
            time.sleep(self.wait_time)
            if SynSTH.close_pars: break
        remote_cmd.join()
        # ctp.cmd = '-q'
        sys.exit()
        return True
        
#%%
if __name__ == "__main__":
    if len(sys.argv) >= 2:
        _, txt_separtor = sys.argv

    print(f'current separtor: {txt_separtor}')
    msg = f'{version}'

    # os.system('title '+ msg)
    print(msg)

    p3 = DataProcess('master')
    p3.run()  # Start the Jobs process in the main process