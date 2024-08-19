# -*- coding: utf-8 -*-
import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

windows = 50
tm = 10
multiplying = 5
ucl_data = []
ucl_minvalue = 0.04
lcl_data = []
lcl_minvalue = 0

def average(csv):
    Mean = np.mean(csv)
    Std = np.std(csv)
    return Mean, Std

file_path = r'./rawdata/TT/Ref/circle2.csv'
df =pd.read_csv(file_path)
df = df[['TimeTag', 'Torque']].to_numpy()
df = np.split(df, 2, axis = 1) #水平分割
torque = df[1]

for i in range(len(torque)// int(windows/2)):
    length = torque[int(windows * (i/2)): int(windows * ((i/2) + 1))]    
    mean, std = average(length)
    ucl_value = mean + (std * multiplying)
    if ucl_value < ucl_minvalue:
        ucl_value = ucl_minvalue
    lcl_value = mean - (std * multiplying)
    if lcl_value < lcl_minvalue:
        lcl_value = lcl_minvalue
    ucl_data.extend([ucl_value] * int(windows/2))
    lcl_data.extend([lcl_value] * int(windows/2))
ucl_data = np.array(ucl_data)
ucl_data = np.max(ucl_data[:len(ucl_data) - (len(ucl_data) % 10)].reshape(-1,50), axis = 1)
lcl_data = np.array(lcl_data)
lcl_data = np.max(lcl_data[:len(lcl_data) - (len(lcl_data) % 10)].reshape(-1,50), axis = 1)
torque = np.max(torque[:len(torque) - (len(torque) % 50)].reshape(-1,50), axis = 1)
plt.plot(torque)
plt.plot(ucl_data)
plt.plot(lcl_data)
plt.show()
#%%test
# file_path = r'./rawdata/TT/Ref/circle2.csv'
# df =pd.read_csv(file_path)
# df = df[['TimeTag', 'Torque']].to_numpy()
# df = np.split(df, 2, axis = 1) #水平分割
# df = [np.max(base[:len(base) - 19].reshape(-1, 50), axis = 1) for base in df] #每10點取max
# df = np.vstack((df[0], df[1]))
# torque = df[1]

# for i in range(len(torque)// int(windows/2)):
#     length = torque[int(windows * (i/2)): int(windows * ((i/2) + 1))]    
#     mean, std = average(length)
#     ucl_value = mean + (std * 5)
#     if ucl_value < ucl_minvalue:
#         ucl_value = ucl_minvalue
#     lcl_value = mean - (std * 5)
#     if lcl_value < lcl_minvalue:
#         lcl_value = lcl_minvalue
#     ucl_data.extend([ucl_value] * int(windows/2))
#     lcl_data.extend([lcl_value] * int(windows/2))
# plt.plot(torque)
# plt.plot(ucl_data)
# plt.plot(lcl_data)
# plt.show()
#%%
a = pd.DataFrame({'Timetag':df[0][:15040], 'Torque':torque[:15040], 'UCL':ucl_data[:15040], 'LCL':lcl_data[:15040]})
a.to_csv('./rawdata/TT/Ref/ref5.csv', encoding = 'utf-8',index = False)