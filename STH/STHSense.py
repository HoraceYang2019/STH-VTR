# -*- coding: utf-8 -*-
"""
Created on Mon May  2 07:05:08 2022
version 0.5.1
@author: hao
"""
import numpy as np

#%%:
version: str = 'STHSense v2.0'

# In[1]: derive the temperature value of for STH-2
def DeriveSTH2Temperature(buffer): 
    temp_data = int('0x' + ''.join(buffer), 16) # transfer power data from list to int 
    ADC_Voltage = temp_data / 7864320*5.1
    R = 510/(5/ADC_Voltage-1)
    T = (R-100)/0.385 - 8.8
    return round(T, 1)  

# In[2]: derive the power value of STH2
def DeriveSTH2Power(buffer): 
    power = int('0x' + ''.join(buffer), 16)   # transfer power data from list to int 
    V = power / 7864320 * 5.1 * 2.045         # derive the actual voltage
    return round(V, 2)  

# In[3]: parse the temperature and power data of STH2
def ParseSTH2TempPowerData(sdata):
    ''' example:
   > 13,10,13,10,  57,99,54,53,102,57,50,48,56,55,51,56,  32,  50,48,48,48,48,49,48,49,48,48,49,55,51,55,
      \r\n\r\n               Device ID                 space                Date Time
      
   > 32,      54,48,48,48,50,    32,    48,48,50,   57,70,     50,54,67,57,68,54,      32
    space   power Id (60001)   space      002     reserved     actual power value      space
    
    '''
    target = np.array([['54', '48', '48', '48', '49'], ['54', '48', '48', '48', '50']]) # 60001 and 60002
    source = [sdata[32:37]]
    for i in range(2):
        power = []; temperature = []        
        if (source == target[i]).all() == True:  # find the exact pattern    
            buffer = []
            for j in range(-7,-1):               # decode the last 6 bytes 
                buffer += chr(int(sdata[j]))
            if i == 0:  temperature = DeriveSTH2Temperature(buffer)
            else:       power = DeriveSTH2Power(buffer)
    return [power, temperature]

# In[10]: derive battery voltage and temperature of STH-3
def ParseSTH3ParameterData(data):
    header_start = np.array(['13','10','13','10'])  # starting header  
    header_spacing = np.array(['32','32','32','32','32'])   # breaking spaces
    PTC_R1 = 620                  # 分壓電阻(PTC_R1)
    start = [data[0:4]]; spacing = [data[27:32]]    # having the received data
    
    # find the exact pattern
    if (start == header_start).all() and (spacing == header_spacing).all() == True:  
        buffer = []
        for i in range(17, 22):        # parsing the power of battery  
            buffer += chr(int(data[i]))
        power = float(''.join(buffer)) # transform the list to float 
        
        buffer = []
        for i in range(23, 27):         # parsing the temperature 
            buffer += chr(int(data[i]))
        temp_value = int(''.join(buffer), 16)  # transform the list to int
        temp_V = temp_value * ((3.3 / 4) / 32767 ) # take the voltage
        PTC_R = (PTC_R1 * temp_V)/(3.3 - temp_V)
        temperature = round((PTC_R-100)/0.39, 1)   # derive the real temperature value    
        return [power, temperature]
    else:
        return []

# In[20]: transform the three bytes data in Hex into Dec, the three bytes are inverse 
def DeriveStrainData(ch_data):
    if len(ch_data) == 3:
        first_byte = hex(int(ch_data[2]))[2:]
        second_byte = hex(int(ch_data[1]))[2:]
        third_byte = hex(int(ch_data[0]))[2:] 
    
        # In case of data loss 
        if len(third_byte) < 2:
            third_byte = '0' + third_byte
        if len(second_byte) < 2:
            second_byte = '0' + second_byte  
        
        # assemble the three bytes into one value
        AD16Hex = first_byte + second_byte + third_byte
        AD16HextoDec = int(AD16Hex,16)
        
        # convert the analog data into digital format with signed dec
        if AD16HextoDec > 8388608:
           AD16HextoDec = ~AD16HextoDec & 0xFFFFFF
           AD16HextoDec = (-1) * (AD16HextoDec+1)
        value = AD16HextoDec / 7864320 * 5.1
        return round(value, 6)
    else:
        return []  # not available data

# In[21]: parse the signal data of four channels of strain gauges 
def ParseRawData(sdata, total_ch, STH, ch_calibration):
    SG_data = []; Parameter_data =[]   
    
     # specific header of STH02 
    if STH == 2 and len(sdata) == 50 : # if the power and temperature data are located in ???
        Parameter_data = ParseSTH2TempPowerData(sdata)
    if STH == 3 and len(sdata) == 54:   # find the header with parameters
        Parameter_data = ParseSTH3ParameterData(sdata)
    else:
        target = np.array(['128', '129', '130', '131']) # the specified IDs of strain gauges
        
        # scan all receiving txt data from STH
        index = 4; chs_values=[]    #從txt檔每一行的值，第4個開始讀
                                    #因為有4個channel
        while index < len(sdata)-8:
            source = [sdata[index-4], sdata[index], sdata[index+4], sdata[index+8]] # find the IDs of four channels
      
            if (source == target).all() == True:   # find the exact pattern
                ch_data = sdata[index-7: index+9]  # get the 16 bytes, and +9 can work bc the check number is at the end of the value
                                                   # it means [value1, value2, value3, check number]
                chs_values=[]
                for i in range(total_ch):          # scan all channels
                    value = DeriveStrainData(ch_data[i*total_ch: 3+i*total_ch])
                    
                    if value != []: 
                        chs_values.append(value * ch_calibration[i])
               # print(f'{chs_values}')
                index += 4*total_ch
                ''' testing debug
                if np.array(chs_values).sum() > 0.5:
                    print(chs_values)
                '''
                if chs_values == []:
                    pass
                else:
                    SG_data.append(chs_values)
            else: 
                index += 1

    return Parameter_data, SG_data
