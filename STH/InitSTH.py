# -*- coding: utf-8 -*-
"""
Created on Sun May 28 15:42:58 2023
@author: Horace Yang
"""
import time
import platform
if platform.system() == "Windows":
    root_folder: str = 'c:/VTR'
else:
    root_folder: str = '/var/VTR'               # os.getcwd()
raw_data_folder: str = root_folder + '/RawData/Source/Data/'    #temp folder
log_file = root_folder + '/Logs/STHUsage.log'

#%% used for all modules
STH_host: str = ''
STH_router: str = 'ST_route'
Router_WIFI_used: bool = False # if the Router is connected via WIFI

Edge_IP: str = '10.0.0.103'
scan_STH_port: int = 6500    # default port for scanning by case
target_STH_port: int = 6502  # the port of the target STH
STH_base_port: int = 6500    # the factory default port

header_length: int = 54      # fixed header size
data_length: int = 4         # fixed 4 bytes/sample
packet_size: int = 1016      # total sample num in one packet
packet_num_in_frame: int = 6 # total packet num in one frame
mode0_frame_size: int = packet_num_in_frame * packet_size * data_length # 6*1016*4=24384bytes

local_broker: bool = True
broker_address: str = '127.0.0.1' if local_broker else '10.0.0.111'
broker_port: int = 1883  # Replace with the port number of your MQTT broker

web_address: str = '127.0.0.1'
web_port: int = 1880
web_url: str = 'http://'+ web_address+ ':' + str(web_port)  # Replace with the appropriate URL for your Node-RED instance

reload_parameter: bool = False
#%% used for STHComm
parm_dict: dict = {'folder': time.strftime("(%Y%m%d%H)/"), 
                   'time_average': 0.1, 
                   'calibration': [1.0, 1.0, 1.0, 1.0], 
                   'force_ratio': (1.0002, 1.0032, 0.9972, 0.9906), 
                   'total_ch': 4, 
                   'column_name': ['TimeTag', 'CH1', 'CH2', 'BendingX', 'BendingY', 'Torque'], 
                   'STH_version': 3}

folder: str = parm_dict['folder']
time_average: float = parm_dict['time_average']

source_path: str = root_folder + '/RawData/Source/' + folder
output_path: str = root_folder + '/RawData/Output/' + folder

# scan number of channels
total_ch: int = parm_dict['total_ch']
column_name: list[str] = parm_dict['column_name']

STH_version: int = parm_dict['STH_version']
# each channel needs to be calibrated  
calibration: list[float, float, float, float] = parm_dict['calibration']
force_ratio: tuple[float, float, float, float] = parm_dict['force_ratio']
socket_timeout: float = 5.0  # in sec

#%% used for DataProcess
keep_data_th: float = 0.00       # Bending X in Nm

record_raw_data: bool = False    # record the receiving raw data  
backup_raw_file: bool = True     # backup the raw file to another folder
reload_parameter: bool = False

to_csv_mode: str = 'a'
save_parsed_file: bool = True    # save parsed file in CSV or not
parse_wait_time: float = 3       # waiting time in sec for next batch of raw data
trans_force: bool = False        # only transform data into cutting force

txt_num_in_csv: int = 10         # number of txt file in one parsed file in csv format
txt_delimiter: str = ' '         # txt separtor

#%% used for StateUpdate
send_cmd: bool = True

#%% used for STHScan
reset_STH_port: bool = False     # Are all STH port numbers reset to 6500
auto_assign_port: bool = False   # auto assign new port number to a STH
manual_assign_port: bool = False # manually assign port numbwe
max_scan_time: int = 5           # max time for scanning STH
total_STH_num: int = 5           # total ports for scanning STH

#%% used for STHSync

remt_scan_topic: str = 'STH/remt/scan'   # remote control for scanning STH
remt_comm_topic: str = 'STH/remt/comm'   # remote control for communicating with STH 
remt_pars_topic: str = 'STH/remt/pars'   # remote control for parsing data collected from STH
remt_recd_topic: str = 'STH/remt/record' # remote control for recording STH data 
remt_merg_topic: str = 'STH/remt/merge'  # remote control for merging parsed data
remt_emul_topic: str = 'STH/remt/emul'   # remote control for merging parsed data

sync_topic: str = 'STH/syn'              # sync control of STHs
pdata_topic: str = 'STH/Pdata'           # STH parsed data message from STH
log_topic: str = 'STH/log'               # Log message of functions
scan_topic: str = 'STH/scan'             # scan results of STHs
emul_topic: str = 'STH/emul'             # emulation output of historical STH

#%% used for Filemerge
control_limit_target_column: list[str] = ['Torque']
control_limit_window_size: int = 600
control_limit_weight: float = 3
