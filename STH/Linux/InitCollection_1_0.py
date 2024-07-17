# -*- coding: utf-8 -*-
# For STH-2-2021, STH-3-2022
#%%
#-----------------------------------------------------------------------------------------
# =============================================================================
#
# source_path = './Source/01xx-22-TOSG'
#   # parsed data file from the source files
# output_path = './Output/01xx-22-TOSG'
#
#   # machining conditions
# condition ={
#         'Machine': 'xxx',
#         'Mode': 'Drilling',                    # machining mode
#         'Holder_Type': 'BT-30',
#         'Speed': '?',                          # spindel speed
#         'Feed': '?',                           # feed rate
#         'NC_Code':'http://',                   # link of nc code
#         }
#   # location of machine
# location = 'TOSG'
#   # scan number of channels
# total_ch = 4
#   # STH version, version = {2, 3, 4}
# ''' ex. Mac ID, DateTime, data mode,
#  > 9c65f9208738 20000101001737 60001 0019F779D66
#  > 13,10,13,10,57,99,54,53,102,57,50,48,56,55,51,56,32,50,48,48,48,48,49,48,49,48,48,49,55,51,55,32,54,48,48,48,50,32,48,48,50,57,70,50,54,67,57,68,54,32
# '''
# STH_version = 2
#   # the specified port number
# port = 6500
#
#   # one of Mac address
# Mac_address = '9c65f9208738'
#   # each channel needs to be calibrated
# calibration = [1, 1, 1, 1]
# =============================================================================

#--------------------------------------------------------------------------------------
#%%
# related source path
source_path = './Source/lab1223'
# parsed data file from the source files
output_path = './Output/lab1223'

# machining conditions
condition = {
    'Machine': 'TMV-720',
    'Mode': 'Milling',                   # machining mode
    'Holder_Type': 'BT-40',
    'Speed': 6000,                       # spindel speed
    'Feed': 1000,                        # feed rate
    'NC_Code': 'http://',                # link of nc code
}
# location of machine
location = 'lab'
# scan number of channels
total_ch = 4
# STH version, version = {2, 3, 4}
''' ex.
  > 13,10,13,10, 55,99,100,102,97,49,51,57,100,53,49,48,32,48,  55,46,55,50,44,55,53,66,52,32,32,32,32,32,48,48,48,48,48,32,45,48,48,52,52,32,48,48,48,48,48, 32, 13,10,13,10
  > 171,248,255,131,213,152,255,128,205,127,255,129,126,32,0,130,41,249,255,131,17,153,255,128,31,128,255,129,32,33,0,130,175,249,255,131,147,153,255,128,169,128,255,129,221,33, ...
'''
STH_version = 3
# the specified port number
port = 6500

# one of Mac address
Mac_address = ['55', '99', '100', '102', '97', '49', '51', '57', '100', '53', '49', '48']
# each channel needs to be calibrated
calibration = (1.0, 1, 1, 1)
# store sensing data in the json file False: not store
store_sensing_data = False
#REVIEW: use in `ParseData_2`
average_interval = 4

#%%
