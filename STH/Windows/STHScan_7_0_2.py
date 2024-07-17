# -*- coding: utf-8 -*-
"""
Created on Thu Jun 15 04:56:38 2023

pyinstaller --noconfirm --onedir --console 
--paths "C:/Users/hao/anaconda3-2022/envs/STH-W3/Lib" 
--paths "D:/Dropbox/Codes/Python/ToolHolder/STH-W3-G"  

@author: hao
"""
version: str = ''

# In[0]:

import logging
import socket
import time
import re
import sys
import json
import paho.mqtt.client as mqtt
import threading
import typing 
import types
import os 

#customerized functions
import SystemCheck_3_1_0 as sc
import UpdateSTHParm_1_0 as usp
import STHSync_5_0 as SynSTH # import STHSync_4_2_3 as SynSTH

# In[1]
def SetParameter(set_p: typing.Union[types.ModuleType, typing.Any]):  #Any -> toUpdate    
    # using the default values
    head_length: int = usp.init.header_length   # header size
    mode_size: int = usp.init.mode0_frame_size  # 6*1016*4=24384bytes
    s_topic: str = usp.init.scan_topic
    l_topic: str = usp.init.log_topic
    
    # using the updated values
    edge_ip: str = set_p.Edge_IP                # The server's hostname or IP address
    base_port: int = set_p.STH_base_port             # The port used by the server    
    RWIFI_used: bool = set_p.Router_WIFI_used   # Does the router use WIFI
    total_num: int = set_p.total_STH_num        # maximum STH number to scan?    
    reset_port: bool = set_p.reset_STH_port     # Are all STH port numbers reset to 6500?
    auto_port: bool = set_p.auto_assign_port     # Is new STH port number to be assigned?
    manual_port: bool = set_p.manual_assign_port # Manually assign port number  

    scan_port: int = set_p.scan_STH_port        # target port number used to scan 
    b_address: str = set_p.broker_address    # broker address
    b_port: int = set_p.broker_port          # broker port
    max_stime: int = set_p.max_scan_time     # maximum scan time-out    
    
    ret = [edge_ip, base_port, head_length, mode_size, reset_port, auto_port, manual_port, scan_port,\
        max_stime, total_num, RWIFI_used, b_address, b_port, s_topic, l_topic]
    return ret
    
def SetParialParm(updated_file: str = usp.updated_file):  #Any -> toUpdate   
    class toUpdate:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    with open(updated_file, encoding="utf-8") as f:
        data = json.load(f) 
     
    updated: toUpdate = toUpdate(**data)
    total_num: int = updated.total_STH_num  
    reset_port: bool = updated.reset_STH_port     # Are all STH port numbers reset to 6500?
    auto_port: bool = updated.auto_assign_port     # Is new STH port number to be assigned?
    manual_port: bool = updated.manual_assign_port # Manually assign port number 
    
    ret = [total_num, reset_port, auto_port, manual_port]
    return ret

# In[]
enable_func = True
master = False
slave = False

scanned_STH: dict = {}
absolute_timeout: int = 5  
rescan_time_delay: int = 3     # in sec
publish_msg = None
func_name = 'STHScan'

[host, base_port, header_length, mode0_frame_size, reset_STH_port, auto_assign_port, manual_assign_port, \
     scan_STH_port, max_scan_time, total_STH_num, Router_WIFI_used, broker_address, broker_port, scan_topic, log_topic] = \
    SetParameter(usp.init) if not usp.updated_state else SetParameter(usp.updated)
    
# In[] wsb header decorder information class
class Device_Info:
    def __init__(self):
        self.mac:str = ""
        self.voltage:float = None
        self.temp_raw:int = None
        self.serial_num:int = None
        self.rssi:int=None
        self.inv_time:int=None

# In[2]:    Log errors         
def LogMessage():
    logging.basicConfig(filename = usp.init.log_file, \
                        filemode = 'a',\
                        format = '[%(levelname)s]: %(asctime)s %(message)s', \
                        level = logging.ERROR)
        
# In[]
def ShowMsg(topic, key, msg):
    timetag = time.strftime("%H:%M:%S", time.localtime())
    print(f'[{timetag}]  <STHScan> {msg}')
    publish_msg.FuncLogPub(topic, {key: '[' + timetag + '] ' + msg})
    
# In[]
def DecodeHeader(data_in:bytes, info_out:Device_Info):
    ret: int = -1
    # header => '\r\n\r\n7cdfa102d0c0 07.11,4DB1     01494 -0027 00035 \r\n\r\n'
    # compare_string=data_in.decode('utf8')
    compare_string = data_in
    pattern = b'\r\n\r\n([0-9a-fA-F-]{12}) ([\d.]+),([\dA-F]+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+\r\n\r\n'
    match = re.match(pattern, compare_string)
    if match:
        ret = 0
        info_out.mac = match.group(1)
        info_out.voltage = match.group(2)
        info_out.temp_raw = match.group(3)
        info_out.serial_num = match.group(4)
        info_out.rssi = match.group(5)
        info_out.inv_time = match.group(6)
    else:
        e = "No Received String Being Matched."; print(e)
        logging.error(e)
        
    return ret

# In[]
def RecvDataWithTimeout(sock, total_size, timeout, stop_string = None):
    received_data: str = b''                     # initialize a buffer for receving data
    socket_timeout_backup = sock.gettimeout()
    start_time = time.time()                # record the staring time 
    timeout = timeout if(timeout>=1) else 1   # minimum timeout is 1
    sock.settimeout(timeout)                # set timeout when receving sockets

    ret = "Error-Free"
    while (len(received_data) < total_size) or (total_size == 0):
        # x if condition else y
        remaining_size = (total_size - len(received_data)) if  (total_size>0) else header_length
        try:
            data = sock.recv(remaining_size) # max receive
            if not data:                     # connection is closed or error if no data received
                ret = 'No Data Received -> Warning'
                break

            received_data += data
            #if stop_string and stop_string in received_data.decode():
            if stop_string and stop_string in received_data:       # break this loop after receving the specified pattern
                ret = f'{stop_string} -> OK' # get the correct feedback
                break
        except socket.timeout:         # break loop after timeout
            if total_size != 0:
                ret = 'Timeout in Receving Sockets -> Warning'
            break

        # Check timeout or not
        elapsed_time = time.time() - start_time
        if total_size == 0:  # command mode
            ret = 'Unexpected Received Data in Command Mode -> Warning' if (ret == 'Error-Free') else ret
        elif elapsed_time >= timeout:
            ret = 'Timeout in Receving Data -> Warning'
            break

    if len(received_data) >= total_size and total_size==0:
        ret = 'Extra Data Received -> Warning' if (ret == 'Error-Free') else ret

    sock.settimeout(socket_timeout_backup)  # 回復原始tcp socket timeout設定
    return [received_data], ret

# In[]
def InitSocket(tid, host, port, max_retries = 3, retry_delay = 2):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)# sock為tcp server resource
    except socket.error as msg:
        sys.stderr.write(f"[{tid}]  [ERROR] %s\n" % msg[1])
        sys.exit(1)
        
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Set socket options
    retries = 0

    while retries < max_retries:
        try:
            # Connect to the remote server
            sock.bind((host, port))
            sock.listen(5)   # Listen for incoming connections
            return sock      # Return the socket if connection is successful

        except socket.error as e:
            error_code = f"({tid})  Socket error occurred. Error code: {e}"
            print(error_code)
            
            sock.close()    # Close the existing socket

        retries += 1        # Increment the retry count
        
        print(f'({tid})  Retry {retries} times')
        if error_code == 10054:
            print(f"({tid})  Connection reset by peer. Retrying in", retry_delay, "seconds...")
        elif error_code == 10038:
            print(f"({tid})  Socket operation on non-socket. Retrying in", retry_delay, "seconds...")
        else:
            print(f"({tid})  Other socket error. Retrying in", retry_delay, "seconds...")

        if retries < max_retries:
            time.sleep(retry_delay)
        else:
            error_code = f"({tid})  Maximum retries exceeded. Unable to establish the connection."
            print(error_code)
            logging.error(error_code)
            
# In[]
def ScanOne(tid, sock):  
    (csock, adr) = sock.accept()             # Accept incoming connections
    client_address = csock.getpeername()     # get tcp client(WSB) resource=> IP & Port 2 tuple
    server_address = sock.getsockname()

    msg = f'({tid})  Edge IP: {server_address[0]}, Port: {server_address[1]}'
    ShowMsg(log_topic, func_name, msg) 

    msg = f"({tid})  STH IP: {client_address[0]}, Port: {client_address[1]}"
    ShowMsg(log_topic, func_name, msg) 

    msg_list = []
    header_info = Device_Info()
    msg_list, ret = RecvDataWithTimeout(sock= csock, total_size = (header_length + mode0_frame_size)*2, \
                    timeout = 1)
    DecodeHeader(msg_list[0], header_info) # get device header 
    mac = '-' if header_info.mac == '' else header_info.mac.decode() 
    msg = f"({tid})  detects MAC = {mac}"
    ShowMsg(log_topic, func_name, msg) 

    return csock, mac

# In[]
def ToCommand(tid, csock, mac):           # Change Device to Config Mode    
    csock.send(b'cmd\n')
    msg_end = b'Enter Configuration Mode\n'
    msg_list, ret = RecvDataWithTimeout(sock= csock, total_size = 0, timeout = 1, stop_string = msg_end)
    print(f'({tid})  MAC:{mac} echoes {ret}')
    
def ChangePort(tid, csock, mac, port):    # set different port as need
    csock.send(bytes('port:'+ str(port) + '\n', 'utf-8'))
    msg_end = bytes('Port setting "' + str(port)+ '" OK\n', 'utf-8')
    msg_list, ret = RecvDataWithTimeout(sock= csock, total_size = 0, timeout = 1, stop_string = msg_end)
    msg = f'({tid})  MAC:{mac} echoes {ret}'
    ShowMsg(log_topic, func_name, msg) 
    
    time.sleep(0.5)
    
def ToSleepMode(tid, csock, mac, port):             # enter sleep mode
    global scanned_STH
    csock.send(b'sleep\n')
    msg_end = b'Enter Sleep Mode'
    msg_list, ret = RecvDataWithTimeout(sock= csock, total_size = 0, timeout = 1, stop_string = msg_end)
    print(f'({tid})  MAC:{mac} echoes {ret}')
    
    scanned_mac = []
    for value in scanned_STH.values():
        mac_value = value.split(',')[0].strip()
        scanned_mac.append(mac_value)
    
    if mac not in scanned_mac and mac != '-':
        scanned_STH['STH' + str(len(scanned_STH)+1)] = mac + ',' + str(port)
       
    time.sleep(0.5)

def PublishMsg(broker, port, topic, msg_list):
    client = mqtt.Client()     
    try:
        client.connect(broker, port)
    except socket.error as err:
        print(f'[ERR] <PublishMsg> {err}')
    else:
        payload = json.dumps(msg_list)
        client.publish(topic, payload, 0)  # support 0 only
    msg = f'Publish message : {payload} via MQTT'
    ShowMsg(log_topic, func_name, msg) 

def ScanPort(host, scan_port, max_scan_time, total_num, reset_STH, auto_assign, manual_assign):
    STH_list = []
    STH_dict = {}
    tid = threading.current_thread().name
    
    msg = f'({tid})  scanning port ({scan_port}) for {max_scan_time} sec.'
    ShowMsg(log_topic, func_name, msg) 
    
    sock = InitSocket(tid, host, scan_port)   
    sock.settimeout(max_scan_time)  # Set the timeout for the connection attempt 
    count = 1
    next_port = 1            
    
    start_time = time.time() 
    while True:
        try:
            csock, mac = ScanOne(tid,sock)  # scan one available port
            
            scanned_mac = []
            for value in scanned_STH.values():
                mac_value = value.split(',')[0].strip()
                scanned_mac.append(mac_value)
                
            if mac not in scanned_mac:
                port = scan_port        # set an initial scan port
                ToCommand(tid, csock, mac)       # set to this connected STH into configuration mode
    
                if reset_STH:          # if the port of this STH needs to be reset
                    port = base_port        # set back to base_port 6500
                    ChangePort(tid, csock, mac, port)  # change the port by setting new port
                    
                elif auto_assign:       # if the port of this STH needs to assign a new port
                     port = scan_port + next_port      # shift one port number  
                     next_port += 1  
                     ChangePort(tid, csock, mac, port)
                elif manual_assign:
                    pass
                             
                ToSleepMode(tid, csock, mac, port)     # set this STH to sleep mode                       
                STH_list.append('"No.' + str(count)+ '":"' + mac + ',' + str(port) + '"')
                count += 1
                
            csock.close()      # close connection of this STH
            
            if len(scanned_mac) >= total_num: break
            if time.time() > start_time + absolute_timeout: break

        except socket.timeout:    
            #print(f'[{tid}]  complete {max_scan_time} (sec) scan!')
            break
    
    sock.close()
    #input("Press Enter to continue")
    STH_dict = {item.split(':')[0].strip('"'): eval(item.split(':')[1]) for item in STH_list}
    msg = f'({tid})  available STHs- {STH_dict}'
    ShowMsg(log_topic, func_name, msg) 

# In[]
class ScanSTH(object):
    def __init__(self):
        super().__init__()
        self.connected = True
        if Router_WIFI_used:   # whether the Router is connected via WIFI
            sys_chk = sc.SysChk() 
            self.connected = sys_chk.ConnectToWifi()     
            
    def run(self):
        global scanned_STH, publish_msg 

        LogMessage()                   # error log    

        publish_msg = SynSTH.PublishStatus(broker_address, broker_port, scan_topic)
        msg = 'Waiting for SynSTH.enable_scan to be True.'
        ShowMsg(log_topic, func_name, msg)

        remote_cmd = threading.Thread(target = SynSTH.RemoteScan, name="Remote Scan Thread")
        remote_cmd.start()   
        scan_once = True             
        
        while self.connected and not SynSTH.close_scan:
            if not SynSTH.enable_scan: 
                scan_once = True
            else:
                if scan_once or SynSTH.loop_scan:
                    [total_num, reset_STH, auto_assign, manual_assign] = SetParialParm()
                            
                    scan = [None]*total_STH_num
                    for i in range(total_STH_num):
                        scan[i] = threading.Thread(target = ScanPort, \
                                name = f"T#{scan_STH_port + i}",\
                                args=(host, scan_STH_port + i, max_scan_time, total_num, reset_STH, auto_assign, manual_assign))
                        scan[i].start()
                   
                    for i in range(total_STH_num):
                        scan[i].join()
                    
                    PublishMsg(broker_address, broker_port, scan_topic, scanned_STH)
                    scanned_STH = {}
                    scan_once = False # one shot if SynSTH.loop is False
                    
                    msg = f'End of scan. Press "Enable Scan" to scan STHs again.'
                    ShowMsg(log_topic, func_name, msg)
                    time.sleep(rescan_time_delay)
            
            time.sleep(1)
            
        msg = 'Function Closed.'
        ShowMsg(log_topic, func_name, msg) 
        remote_cmd.join()
        
# In[]
if __name__ == "__main__":
    msg = f'{version}'
    os.system('title '+ msg); print(msg)

    p1 = ScanSTH()
    p1.run()  # Start the Jobs process in the main process