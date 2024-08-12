# -*- coding: utf-8 -*-
"""
Created on Tue August 06 20:24:55 2024
 
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
print(syntecremotecnc.Host)
#%%
def ConvertToStr(input_):
    return input_.decode('utf-8')
def ConvertToFloat(input_):
    return np.float16(input_)
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
    rul = (np.int32(syntecremotecnc.READ_plc_addr('R',
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
class CtlComm(threading.Thread):
    def __init__(self, sdataclass: ShareVar):
        super().__init__()
        self.dclass = sdataclass
    def CNCStatus(self):
        while state:
            # self.dclass.init_status_event.wait()
            parameters = GetParam()
            cnc_status = json.dumps(parameters, indent=4)
            now_time = datetime.now()            
            with open(now_time.strftime(
                config_['SAVE_DIR']
                + '/ChangeToolLog_%Y%m%d_%H%M%S.%f.json'), 'w') as file:
                json.dump(parameters, file,indent=4)   
            publish.single(config_['STATUS_TOPIC'], 
                           cnc_status, 
                           hostname = config_['MQTT_HOST'])            
            # self.dclass.init_status_event.clear() 
            time.sleep(5)
    def CNCCoord(self):
        # buffer use class
        result = np.empty(item,dtype='object')
        while state:
            if self.dclass.cycle_start_event.is_set():
                nc_point = int(
                    ConvertToFloat(syntecremotecnc.READ_nc_pointer()[1]) )   
                coord = ConvertToFloat(syntecremotecnc.READ_position()[4])
                result[0] = nc_point
                result[1:5] = coord[:-1]
                self.dclass.buffer[self.dclass.buffer_index].append(
                                                                result.tolist())
    def CNCPublish(self):
        while state:
            try:
                self.pevent.wait()
                self.dclass.buffer_index = (1 if self.dclass.buffer_index == 0 
                                            else  0)
                data = np.array(self.dclass.buffer[self.dclass.save_index])
                self.coord_msg: dict = {
                    'LineNo': data[:,0].tolist(),
                    'NowCoord': {
                    'X': data[:,1].tolist(),
                    'Y': data[:,2].tolist(),
                    'Z': data[:,3].tolist(),
                    }
                }
                pub_msg = json.dumps(self.coord_msg, ensure_ascii = False)
                with open(config_['SAVE_DIR']+('/NowCoord.json'), 'w') as file:
                    json.dump(self.coord_msg, file,indent=4)  
                publish.single(config_['STATUS_TOPIC'], 
                               pub_msg, 
                               hostname= config_['MQTT_HOST'])
                self.dclass.buffer[self.dclass.save_index] = []    
                self.dclass.save_index = (1 if self.dclass.save_index == 0 
                                          else  0)
                self.pevent.clear()
            except:
                pass
    def Timer(self, interval = interval):
        while state:
            if self.dclass.cycle_start_event.is_set():
                time.sleep(interval)
                self.pevent.set()
    def Ready(self):
        while state:
            ready_msg = subscribe.simple(config_['READY_TOPIC'], 
                                hostname = config_['MQTT_HOST'])
            msg_byte = ready_msg.payload 
            byte_decode = msg_byte.decode("utf-8")
            self.dclass.ready_type = ast.literal_eval(byte_decode)
            if self.dclass.ready_type['Ready'] == '1':
                syntecremotecnc.WRITE_plc_addr('R',
                                               65,
                                               65,
                                               2,
                                               np.bytes_(
                                                   np.array([],dtype=np.bytes_)
                                                   ),
                                               np.bytes_(
                                                   np.array([],dtype=np.int16)
                                                   ),
                                               np.bytes_(
                                                   np.array([1])
                                                   ) 
                                               )
                print('start')           
    def run(self):
        self.pevent = threading.Event()

        cnc_status = threading.Thread(target= self.CNCStatus)
        cnc_coord = threading.Thread(target= self.CNCCoord)
        cnc_publish = threading.Thread(target= self.CNCPublish)
        cnc_timer = threading.Thread(target= self.Timer)
        cnc_ready = threading.Thread(target= self.Ready)

        cnc_status.start()
        cnc_coord.start()
        cnc_publish.start()
        cnc_timer.start()
        cnc_ready.start()

        cnc_status.join()
        cnc_coord.join()
        cnc_status.join()
        cnc_timer.join()
        cnc_ready.join()




