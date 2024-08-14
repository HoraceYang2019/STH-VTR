# -*- coding: utf-8 -*-
"""
Created on Tue July 30 20:43:34 2024
 
@author: Guan
"""
import ast
import clr
import json
import numpy as np
import paho.mqtt.subscribe as subscribe
import paho.mqtt.publish as publish
import time
import threading

from datetime import datetime
from typing import List, Dict, Any

import config
from . import *
#%%
config_ = config.readconfig()
syntecremotecnc = config.ref_syntecAPi(config_['IP_ADDRESS'])
#%%
def ConvertToStr(input_):
    return input_.decode('utf-8')
def ConvertToFloat(input_):
    return np.float16(input_)
def ChangeToolFunc(changetype):
    '''
    WRITE_plc_addr:(
        ADDR string:
        PLCStar int:
        PLCEnd int:
        PLCType int: 0: byte, 1: short, 2, int
        PLCData byte:  
        PLCData short:  
        PLCData int:
        )  
    '''
    syntecremotecnc.WRITE_plc_addr('R',
                                   60,
                                   60,
                                   2,
                                   np.bytes_(np.array([],dtype=np.bytes_)),
                                   np.bytes_(np.array([],dtype=np.int16)),
                                   np.bytes_(np.array([changetype]))
                                   )
def RUL(t_code):
    return (np.int32(syntecremotecnc.READ_plc_addr('R',
                                                  config_['MAX_LIFE']
                                                  +int(t_code)*10,
                                                  config_['MAX_LIFE']
                                                  +int(t_code)*10)[4]
                                                  )[0]
      - np.int32(syntecremotecnc.READ_plc_addr('R',
                                               config_['CURRENT_LIFE']
                                               +int(t_code)*10,
                                               config_['CURRENT_LIFE']
                                               +int(t_code)*10)[4]
                                               )[0]
            )
def GetParam() -> Dict[str, Any]:
    init_name = (syntecremotecnc.READ_status()[1])
    init_ext = ConvertToFloat(syntecremotecnc.READ_work_coord_single('EXT')[1])
    init_g54 = ConvertToFloat(syntecremotecnc.READ_work_coord_single('G54')[1])
    ovRate = syntecremotecnc.READ_spindle()
    init_spindle_ovRate = ConvertToFloat(ovRate[2])
    init_feedrate_ovRate = ConvertToFloat(ovRate[1])
    t_code = np.int32(syntecremotecnc.READ_plc_addr('R',102,102)[4])[0] # Tcode
    # offset_title = np.array(syntecremotecnc.READ_offset_title()[1])
    offset_scope = ConvertToFloat(syntecremotecnc.READ_offset_scope(1,10)[1])
    rul = RUL(t_code)
    return {
        'NCFile': init_name ,
        'OffCoord':{'X':float(init_ext[0]),
                    'Y':float(init_ext[1]),
                    'Z':float(init_ext[2]),},
        'SpdOver': float(init_spindle_ovRate),
        'FedOver':float(init_feedrate_ovRate),
        'G54': {'X': float(init_g54[0]),
                'Y': float(init_g54[1]),
                'Z': float(init_g54[2])},
        "SpdTool":{'TCode': int(t_code),
                   'RUL': int(rul),},
        'RadiusComp': offset_scope[:,0].tolist(),
        'RadiusWear': offset_scope[:,1].tolist(),
        'LengthComp': offset_scope[:,2].tolist(),
    }
#%%
class CtlMotion(threading.Thread):
    def __init__(self, sdataclass: ShareVar):
        super().__init__()
        self.dclass = sdataclass
    def CheackingStart(self):
        machine_state = None
        while state:            
            if machine_state != syntecremotecnc.READ_status()[5]:
                if syntecremotecnc.READ_status()[5] == 'START':
                    print('CycleStart!')
                    self.dclass.cycle_start_event.set()
                    msg = {"Cycle": 'Start'}
                    jmsg = json.dumps(msg, ensure_ascii=False)
                    publish.single(config_['CYCLE_START_TOPIC'], 
                                   jmsg, 
                                   hostname= config_['MQTT_HOST']
                                   )
                    if self.dclass.ready_type['Ready'] != '0':
                        np.int16(syntecremotecnc.WRITE_plc_addr(
                        'I',114,114,0,np.bytes_(np.array([0])),
                        np.bytes_(np.array([],dtype=np.int16)),
                        np.bytes_(np.array([],dtype=np.int0)))
                        )
                        
                elif syntecremotecnc.READ_status()[5] == 'FEEDHOLD':
                    print('FEEDHOLD!')
                    self.dclass.cycle_start_event.clear()
                    # self.dclass.init_status_event.set()
                    ...
                elif syntecremotecnc.READ_status()[5] == 'STOP':
                    print('SingleBlock!')
                    self.dclass.cycle_start_event.clear()
                    # self.dclass.init_status_event.set()
                    msg = {"Cycle": 'End'}
                    jmsg = json.dumps(msg, ensure_ascii = False)
                    publish.single(config_['CYCLE_START_TOPIC'], 
                                   jmsg, 
                                   hostname= config_['MQTT_HOST']
                                   )
                    self.dclass.ready_type = {'Ready': '0'}
                else:
                    print('CycleEnd!')
                    self.dclass.cycle_start_event.clear()
                    # self.dclass.init_status_event.set()
                    msg = {"Cycle": 'End'}
                    jmsg = json.dumps(msg, ensure_ascii = False)
                    publish.single(config_['CYCLE_START_TOPIC'], 
                                   jmsg, 
                                   hostname= config_['MQTT_HOST']
                                   ) 
                    self.dclass.ready_type = {'Ready': '0'}                       
                machine_state =  syntecremotecnc.READ_status()[5]
            time.sleep(0.5)
    def CheckTcode(self):
        init_tcode = np.int32(syntecremotecnc.READ_plc_addr('R',102,102)[4])[0]
        while state:
            new_code = np.int32(
                syntecremotecnc.READ_plc_addr('R',102,102)[4]
                )[0]
            if init_tcode != new_code:
                np.int16(syntecremotecnc.WRITE_plc_addr(
                    'I',114,114,0,np.bytes_(np.array([255])),
                    np.bytes_(np.array([],dtype=np.int16)),
                    np.bytes_(np.array([],dtype=np.int0)))
                    )
                change_msg = {
                    "SpdTool":{
                        "Tcode": int(new_code),
                        "RUL": int(RUL(new_code))
                    }
                }
                change_jmsg = json.dumps(change_msg, ensure_ascii=False)
                publish.single(config_['STATUS_TOPIC'], 
                               change_jmsg, 
                               hostname= config_['MQTT_HOST'])
                init_tcode = new_code
                # self.dclass.init_status_event.set()
            time.sleep(3)
    def CNCChangeTool(self):
        while state:
            change_key = 'ToolChange'
            change_msg = subscribe.simple(config_['STATUS_TOPIC'], 
                                          hostname = config_['MQTT_HOST'])
            msg_byte = change_msg.payload 
            byte_decode = msg_byte.decode("utf-8")
            change_type: Dict = ast.literal_eval(byte_decode)
            if [*change_type.keys()][0] == change_key: 
                ChangeToolFunc(change_type[change_key]) 
    def run(self):
        check_starting = threading.Thread(target= self.CheackingStart)
        check_Tcode = threading.Thread(target= self.CheckTcode)
        cnc_change_tool = threading.Thread(target= self.CNCChangeTool)

        check_starting.start()
        check_Tcode.start()
        cnc_change_tool.start()

        check_starting.join()
        check_Tcode.join()
        cnc_change_tool.join()