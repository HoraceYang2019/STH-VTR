# -*- coding: utf-8 -*-
"""
Created on Mon May 22 07:36:36 2023
@author: hao
"""
import subprocess
import re
import netifaces
import logging
import requests
import paho.mqtt.client as mqtt
from pywifi import const, PyWiFi, Profile
from time import sleep
from importlib import util

#%%:
version: str = 'SystemCheck v3.1.0'

# In[1]
class SysChk:
    def __init__(self):
        file_path = 'InitSTH.py'
        module_name = ''
        
        spec = util.spec_from_file_location(module_name, file_path)
        init = util.module_from_spec(spec)
        spec.loader.exec_module(init)
        
        self.Router_WIFI_used: bool = init.Router_WIFI_used
        self.STH_router: str = init.STH_router 
        self.Router_pass: str = "1234567890"
        self.Edge_IP: str = init.Edge_IP 
        
        self.web_address: str = init.web_address
        self.web_url: str = init.web_url                # Replace with the appropriate URL for your Node-RED instance
        self.broker_address: str = init.broker_address  # MQTT broker address
        self.broker_port: int = init.broker_port        # MQTT broker port
    
    # In[]
    def ConnectToWifi(self):
        link_media = 'LAN'
        if self.Router_WIFI_used:
            link_media = 'WIFI'
            wifi = PyWiFi()  # Create an instance of the PyWiFi class
            iface = wifi.interfaces()[0]  # Get the first wireless interface
            iface.disconnect()  # Disconnect from any previous connections
        
            sleep(1) # Wait for a while to ensure disconnection
        
            profile = Profile()  # Create a new WiFi profile
            profile.ssid = self.STH_router  # Set the SSID (network name)
            profile.auth = const.AUTH_ALG_OPEN  # Authentication algorithm
            profile.akm.append(const.AKM_TYPE_WPA2PSK) # Set the encryption type (WPA2 or WEP)
            profile.cipher = const.CIPHER_TYPE_CCMP    # Set the password
            profile.key = self.Router_pass
        
            iface.remove_all_network_profiles()       # Remove all existing profiles
            tmp_profile = iface.add_network_profile(profile)  # Add the new profile
            iface.connect(tmp_profile)  # Connect to the WiFi network
            sleep(1)        # Wait for the connection to be established
        
            # Check the connection status
            if iface.status() == const.IFACE_CONNECTED:
                print("Connected to WiFi!")
                return True
            else:            
                error_msg = "Failed to connect to WiFi. Check the router status."
                print(error_msg)
                logging.error(error_msg)
                return False
        print(f'[INFO]  The link between the Edge and Router is using {link_media}')
        
    # In[B] check router by taking the ssid by guid
    def GetSSID(self, guid):
        # Retrieve the SSID of the connected Wi-Fi network
        wlan = subprocess.check_output(['netsh', 'wlan', 'show', 'interfaces']).decode('big5')
        wlan_exist = re.search(r'\bSSID\s*:\s(.+)', wlan)
        try:
            wlan_ssid = wlan_exist.group(1)
            if wlan_ssid: wlan_ssid = wlan_ssid.strip()  # remove extra space
            wlan_guid = re.search(r'\bGUID\s*:\s(.+)', wlan).group(1).strip()
            
            # search there exits guid with case-insensitivity
            match = re.search(wlan_guid, guid, re.IGNORECASE)
        
        except Exception: 
            logging.error('No available WIFI: ')
            match = None
        finally:
            if match:
                return [wlan_ssid]
            else: 
                return []
            
    # In[A] check network interfaces 
    def ScanNetIfaces(self):
        all_net = {}; wlan_net ={}
        # Get the list of network interfaces
        interfaces = subprocess.check_output(['netsh', 'interface', 'show', 'interface'])
        try:
            interfaces = interfaces.decode('big5')
        except UnicodeDecodeError:
            interfaces = interfaces.decode('utf-8')
    
        # print(f'[INFO] All Network Interfaces: {interfaces}')
        # logging.info(str(interfaces))
        
        for guid in netifaces.interfaces():
            addresses = netifaces.ifaddresses(guid) # '{07CDD722-AFDE-4E19-A205-6B2FB4F60493}'
            
            # address keys = {netifaces.AF_LINK: -1000, netifaces.AF_INET: 2, 23} 
            if netifaces.AF_INET in addresses: # netifaces.AF_INET = 2
                ipv4_addresses = [addr['addr'] for addr in addresses[netifaces.AF_INET]]
                subnet_mask = [netmask['netmask'] for netmask in addresses[netifaces.AF_INET]]
                ssid = self.GetSSID(guid)
            else:
                ipv4_addresses = []
                subnet_mask = []
                ssid = []
    
            if netifaces.AF_LINK in addresses: # netifaces.AF_LINK = -1000
                mac_addresses = [addr['addr'] for addr in addresses[netifaces.AF_LINK]]
            else:
                mac_addresses = []
    
            all_net[guid] = {
                'ipv4': ipv4_addresses,
                'mask': subnet_mask,
                'ssid': ssid,
                'mac': mac_addresses
            }
            if ssid:
                wlan_net ={
                    'ipv4': ipv4_addresses,
                    'ssid': ssid,
                    'mac': mac_addresses }
    
        return all_net, wlan_net

    def CheckRouterLinking(self):
        ip_match = None
        ssid_match = None
        _, wlan_net = self.ScanNetIfaces()    
    
        try:
            ip_match = re.search(self.Edge_IP, str(wlan_net['ipv4']))
            ssid_match = re.search(self.STH_router, str(wlan_net['ssid']))
            print(f'[INFO]  This setting IP: [{self.Edge_IP}]')
            if self.Router_WIFI_used:            
                if not ip_match: 
                    print(f'[ALARM] But current IP is {wlan_net["ipv4"]}')

                print(f'[INFO]  Wifi Router [{self.STH_router}]: OK, linking.') \
                    if ssid_match else print(f'[ERROR]  Please try to find the correct SSID: {self.STH_router}')        
            else:
                try:
                    subprocess.run(f'netsh interface ip set address "{self.STH_router}" static {self.Edge_IP} "255.255.255.0" "10.0.1.1"', check=True)
                    print(f"[INFO]  linking {self.STH_router} with IP {self.Edge_IP} by LAN")
                except subprocess.CalledProcessError as e:
                    print(f"[ERROR]:  Please enable the router for linking \n{e}")
                        
        except Exception as e:
            logging.error(str(e))
            print(f'[WARN]  Current Router status: {wlan_net}, it needs the "SSID: ST_route" ')    
            
        return True if ip_match and ssid_match else False
        
    # In[C]: check web server (node-red)
    def CheckWebServerRunning(self):
        try:
            response = requests.get(self.web_url)
            if response.status_code == 200:
                print("[INFO]  Web Server in [localhost]: OK, Running.")
                return True
            else:
                print("[ERROR]  Web Server (Node-RED): Not running.")
        except requests.exceptions.ConnectionError:
            print("[ERROR]  Failed to connect to Web Server (Node-RED).")
        
        return False
    
    # In[D]:  check MQTT message broker (Mosquitto)
    def CheckMQTTBrokerRunning(self):
        client = mqtt.Client()
        try:
            client.connect(self.broker_address, self.broker_port)
            print(f"[INFO]  MQTT Broker [{self.broker_address}]: OK, Running.")
            client.disconnect()
            return True
        except ConnectionRefusedError:
            print("[ERROR]  Failed to connect to MQTT broker (Mosquitto).")
            return False
    
# In[E]:    Log errors         
def LogMessage():
    logging.basicConfig(filename = 'error.log', \
                        filemode = 'a',\
                        format = '[%(levelname)s]: %(asctime)s %(message)s', \
                        level = logging.ERROR)
        
#%%    MAIN cell
if __name__ == '__main__':
    LogMessage()                   # error log
    sys_chk = SysChk()
    sys_chk.ConnectToWifi()
    sys_chk.CheckRouterLinking()           # check network interfaces and router 
    sys_chk.CheckWebServerRunning()        # check web server (node-red)
    sys_chk.CheckMQTTBrokerRunning()       # check MQTT message broker (Mosquitto)
       