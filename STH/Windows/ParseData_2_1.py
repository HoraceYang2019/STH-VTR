# -*- coding: utf-8 -*-
"""
Created on 2024-04-15 17:29:43

Input: *.txt from STH
Ouput: 

@author: MilkTea_shih
"""

#%%
import numpy as np
import numpy.typing as npt
import time
from scipy import signal  # type: ignore
from typing import Callable, Any, Callable, Union

#customized functions
import Denoise_1_1 as Denoise
import STHSense_2_0 as STHSense
import InitCollection_1_0 as InitCollection
import UpdateSTHParm_1_0 as usp

DataFormat = npt.NDArray[np.float64]

sth: int = usp.init.parm_dict['STH_version']  
total_channels: int = usp.init.parm_dict['total_ch']    #4
calibration: tuple[float, ...] = usp.init.parm_dict['calibration']
average_points: int = int(usp.init.parm_dict['time_average'] * 3700 )
machining_mode: str = usp.updated.machining_mode

data_column: list[str] = ['Torque',
                          'Bending_X',
                          'Bending_Y']

#%%
def AverageData(x: DataFormat, interval: int = 20
                ) -> DataFormat:
    quotient, remainder = divmod(len(x), interval)
    if quotient:
        x_: DataFormat = x[:-remainder if remainder else None]
        result: DataFormat = np.average(x_.reshape(-1, interval), 1)
        return np.append(result, np.average(x[-remainder:]))
    else:
        return np.asarray(np.average(x))

def DataDetrend(x_: DataFormat, mode: str) -> DataFormat:
    try:
        if mode == 'Drilling':
            x: DataFormat = np.asarray(Denoise.wden(x_,
                                                    'sqtwolog',
                                                    'soft',
                                                    'mln',
                                                    2,
                                                    'db3'))
        else:
            x: DataFormat = signal.detrend(Denoise.wden(x_,
                                                    'sqtwolog',
                                                    'soft',
                                                    'mln',
                                                    2,
                                                    'db3'))
    except ValueError:
        return np.asarray(
            [0, 0, 0, 0] * average_points).reshape(total_channels, -1)
    else:
        return AverageData(x, average_points)

def CalculateTorque(x: DataFormat):
    return np.linalg.norm(x, 2, 0, True)

def ParseData(data: str,
              channels: int,
              version: int,
              ratio: tuple[float, ...]
              ) -> DataFormat:
    #parse the raw data by using the STH library
    SG_data: list[list[float]] = STHSense.ParseRawData(data.split(),
                                                       channels,
                                                       version,
                                                       ratio)
    return np.asarray(SG_data[1])

def DataProcessSetter(channels: int,
                      version: int,
                      ratio: tuple[float, ...]
                      ) -> Callable[[str], DataFormat]:
    def DataProcess(message_str: str) -> DataFormat:  #tuple[DataFormat, DataFormat]:
        data: DataFormat = ParseData(message_str,
                                     channels,
                                     version,
                                     ratio)
        #TODO: if data does not have to average
        data_detrend: DataFormat = np.asarray(tuple(map(DataDetrend,
                                                        data.T, machining_mode)))
        
        
        #TODO: IndexError: too many indices for array: array is 1-dimensional, but 2 were indexed
        def is_abnormal_array(arr):
            # Check if the input is a numpy array
            if not isinstance(arr, np.ndarray):
                raise ValueError("Input must be a numpy array")
            # Check if the array is one-dimensional
            return arr.ndim == 1
        
        if is_abnormal_array(data_detrend):
            return data_detrend 
        else:
            return np.vstack((CalculateTorque(data_detrend[0:2, :]),
                          data_detrend[2:, :]))
            
    return DataProcess

#%%
data_process_setter: Callable[[str], DataFormat] = DataProcessSetter(
    total_channels, sth, calibration
)
def DataPublish(timetag: str, header: dict, data: str) -> dict:
    data_array = data_process_setter(data)  #, ch1_and_ch2
    data_dict: dict[str, list[float]] = dict(
        zip(data_column, data_array.tolist()))
    #publish_dict: ChainMap = ChainMap(data_dict, header)
    return header | data_dict | {"timetag": timetag}


#%%
if __name__ == '__main__':
    file = r''
    with open(file, 'r') as f:
        raw_data: list[str] = f.readlines()
        a = time.process_time()

        res: DataFormat = ParseData(raw_data[1],
                                    total_channels,
                                    sth,
                                    calibration)
        result_: DataFormat = np.asarray(tuple(map(DataDetrend, res.T)))

        result: DataFormat = np.vstack((CalculateTorque(result_[0:2, :]),
                                        result_[2:, :]))

        data_dict: dict[str, list[float]] = dict(zip(data_column,
                                                     result.tolist()))
        b = time.process_time()
        print(abs(b - a))
