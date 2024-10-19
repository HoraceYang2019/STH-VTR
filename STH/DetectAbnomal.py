# -*- coding: utf-8 -*-
'''
TODO:

'''
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import datetime
import time
from scipy.spatial.distance import euclidean
from fastdtw import fastdtw
import plotly.graph_objects as pgo
import plotly.io as pio
import threading
import queue
import paho.mqtt.client as mqtt
import threading
import platform
#%%
NC = ['']
begin = 0
time_step = 0.0053
# MQTT host的位址和埠號
S_host = "10.0.0.103"
P_host = "10.0.0.103"
port = 1883
topic_pdata = "STH/Pdata"
topic_csv = "STH/Pdetect"
topic_changetool = 'STH/CNC/CYCLE'
topic_cnc = 'STH/CNC'
topic_alm = "STH/alarm"
topic_state = "STH/state"

receive_pdata = False   #Control the acceptance of pdata
client = mqtt.Client()
current_queue = queue.Queue()

if platform.system() == "Windows":
    base_path: str = 'C:\VTR/'
else:
    base_path: str = '/var/VTR/'

#%%
def on_connect(client, userdata, flags, rc):
    print("Connected with result code " + str(rc))
    client.subscribe([(topic_csv, 0), (topic_pdata, 0),(topic_cnc, 0)])

# turn on handle_pdata function
def on_message(client, userdata, msg):
    global NC
    global receive_pdata
    if msg.topic == topic_csv:
        message = msg.payload.decode()
        if message == "{'Cmd':'Start'}":
            receive_pdata = True
            print("Starting")
        elif message == "{'Cmd':'End'}":
            receive_pdata = False
            begin = 0
            print("Stopping")
    elif msg.topic == topic_cnc:
        message = json.loads(msg.payload.decode())
        try:
            if NC != message['NCFile']:
                NC = message['NCFile']
                path = './rawdata/' + NC + '.csv'
                base_np = detector.BuildBaseLines(path)
                print(f'{NC}.csv')
        except:
            pass
# collect smart tool holder signal
def handle_pdata():
    def on_pdata_message(client, userdata, msg):
        if receive_pdata:
            try:
                data = json.loads(msg.payload.decode())
                current_queue.put(data)
            except json.JSONDecodeError:
                print("Failed to decode JSON data.")
    pdata_client = mqtt.Client()
    pdata_client.on_message = on_pdata_message
    pdata_client.connect(S_host, port, 60)
    pdata_client.subscribe(topic_pdata)
    pdata_client.loop_forever()
def process():
    while True:
        if not current_queue.empty():
            detector.Run(current_queue.get())

#%% files for testing
with open('FilePool.json', encoding="utf-8") as f:
    var = json.load(f)

base_file = var['base_file']
group_size = var['group_size']   # how many points will be as a group
torque_index = var['torque_index']  # the torque index of the matrix   
scale = var['torque_scale']
STH_interval = var['STH_interval']
minmum_power = var['minmum_power']
# NC = var['NCcode']

with open(base_path + 'InitSTH_u.json', encoding="utf-8") as f:
    var = json.load(f)
TargetMac = var['target_STH_mac']
target = ['CH1_A', 'CH1_B',	'CH2_A', 'CH2_B']
coef_path = base_path + "RawData/Coefficient/AvailableSTH.csv"
csv = pd.read_csv(coef_path)
#%%
class DetectAbnoraml:
    def __init__(self, scale:int = scale, max_time_len:int = 26):
        self.scale: int = scale
        self.max_time_len: int = max_time_len
        self.base_np = self.BuildBaseLines(base_file) # 34256 x 4 of the base_file

    def ParseDatetime(self, date_str):
        try:
            return datetime.datetime.strptime(date_str[:self.max_time_len], "%H:%M:%S.%f")
        except ValueError as e:
            print(f"Error parsing date: {e}")
            return None

#%% build a base for reference
    def DeriveGroupMax(self, data_matrix, group_size: int = group_size):
        n, k = data_matrix.shape          # (342565, 4) of the base_file
        num_groups = n // group_size # 34256 
        if num_groups > 0:
            # Select the first column values from the first row of each group
            first_column = data_matrix[::, 0]
            reshaped_matrix = data_matrix[:num_groups*group_size, 1:].reshape(num_groups, group_size, -1)
            # Compute the max values for the remaining columns along the grouping axis
            max_columns = np.max(reshaped_matrix, axis=1)
            # Combine the first column and the max columns
            return np.column_stack((first_column, reshaped_matrix))
        return None

    def BuildBaseLines(self, ref_file: str)-> np.array:
        # sel_window: window點取max
        df = pd.read_csv(ref_file)
        data_np = df.to_numpy()
        data_np = np.transpose(data_np)

        # Vectorized datetime parsing and time difference calculation
        parsed_time = np.array([self.ParseDatetime(timetag) for timetag in data_np[0]])
        if None in parsed_time:        return None
        data_np[0] = np.array([(ctime - parsed_time[0]).total_seconds() for ctime in parsed_time])
        data_np = np.transpose(data_np)
        return data_np
        # return  self.DeriveGroupMax(data_np)

    # base_df = BuildBaseLines(r'./rawdata/Fanuc-2/Ref/Case2-Milling.csv')
#%% low power
    def Serch_Power(self, data):
        if float(data.get("Power")) < minmum_power:
            message = "{Alarm:'1'}"
            return self.Alarm(topic_alm, message)
    def SerchMac(self, mac):
        global TargetMac
        try:
            index = csv[csv['MAC'] == mac].index
            coef = csv.loc[index, target].values[0]
            print(coef)
            return coef
        except:
            pass
            # print(f'not this MAC coefficient')
#%%
    def TransforTime(self, data, time_step):
        global begin
        global TargetMac
        global coefficient
        if begin == 0:
            begin = int(data["Packet Sequence Number"])
        if data["MAC"] != TargetMac:
            coefficient = self.SerchMac(data["MAC"])
        # Count_torque = [[list(map(lambda x:x * coefficient, data["ch1"])), list(map(lambda x:x * coefficient, data["ch2"]))]]
        # torque_data = np.linalg.norm(Count_torque, 2, 0, True)
        
        torque_data = np.array(data.get("Torque", []))
        torque_data = torque_data * self.scale
        start_time = (int(data["Packet Sequence Number"]) - begin) * 0.3975
        try:
            time_series_length = len(torque_data)
        except:
            time_series_length = 1
        end_time = start_time + (time_series_length - 1) * time_step
        time_series = np.linspace(start_time, end_time, time_series_length)
        torque_with_time = np.column_stack((time_series, torque_data))
        return torque_with_time
#%%
    def FindBaseIndex(self, raw_np, tolerance: float = STH_interval):
        index = raw_np[0][0]
        # find the range of possible timetag
        while index > self.base_np[-1, 0]:
            index = index - self.base_np[-1, 0]
        index = index + self.base_np[400, 0]
        indexs = np.where((self.base_np[:, 0] > index - tolerance) & (self.base_np[:, 0] < index + tolerance)) 
        return raw_np, indexs

    # filter_df, base_index = FindBaseIndex(base_df, raw_df, actual_start_time)
#%%    
    def FindStartIndex(self, data, indexs):
        length, _ = data.shape
        man_dist = lambda x, y: np.abs(x - y)
        dtw_distances = {
            str(index): fastdtw(data[:, torque_index], self.base_np[index: index + length, torque_index], dist=man_dist)[0]
            for index in indexs[0]
        }
        # Find the start index with the minimum DTW distance
        try:
            start_index = min(dtw_distances, key=dtw_distances.get)
        except:
            start_index = dtw_distances.get
        return start_index

    # start_index = FindStartIndex(filter_df, base_index)
#%%
    def DetectCurrentState(self, data, start):
        # Initialize the state
        state = "{'ToolChange':1}"  # Initial state
        # Extract the relevant data slices
        data_slice = data[:, 1]                               # Torque
        ucl_slice = self.base_np[start:start + len(data), 2]  # UCL
        lcl_slice = self.base_np[start:start + len(data), 3]  # LCL
        if len(ucl_slice) < len(data_slice):
            data_slice = data_slice[:len[ucl_slice]]
        # Vectorized comparison
        over_ucl = np.any(data_slice > ucl_slice)
        lower_lcl = np.any(data_slice < lcl_slice)
        if over_ucl:
            self.Alarm(topic_changetool, state)
            # state = 'Over-UCL'
        elif lower_lcl:
            self.Alarm(topic_changetool, state)
            # state = 'Lower-UCL'
    # print(Compare(filter_df, start_index))
#%%
    def PlotlyResult(self, data, start_index, sel_file, local_show, state, time_used):
        # Initialize the figure
        fig = pgo.Figure()

        # Add the 'On-line' data trace
        fig.add_trace(pgo.Scatter(
            x = np.arange(len(data)),
            y = np.concatenate((np.zeros(start_index - 1), sel_file[:,1], np.zeros(len(data) - start_index + len(sel_file)))),
            mode = 'markers',
            marker = dict(color='red'),
            name = 'On-line',
            # title = sel_file
        ))

        # Add the 'Simulation' data trace
        fig.add_trace(pgo.Scatter(
            x = np.arange(len(self.base_np)),
            y = self.base_np[:, 1],
            mode = 'lines',
            line = dict(dash='dashdot', color='gray'),
            name = 'Simulation'
        ))

        # Add the 'UCL' data trace
        fig.add_trace(pgo.Scatter(
            x = np.arange(len(self.base_np)),
            y = self.base_np[:, 2],
            mode = 'lines',
            line = dict(dash='dashdot', color='orange'),
            name = 'UCL'
        ))

        # Add the 'LCL' data trace
        fig.add_trace(pgo.Scatter(
            x = np.arange(len(self.base_np)),
            y = self.base_np[:, 3],
            mode = 'lines',
            line = dict(dash='dashdot', color='blue'),
            name = 'LCL'
        ))

        # Set the title and labels
        fig.update_layout(
            title = 'torque',
            xaxis_title = f"Samples (per {group_size} ms)",
            yaxis_title = "Nm",
            legend = dict(font=dict(size=12)),
            template = 'plotly_white',
            width = 800,  # Set the width of the figure
            height = 600  # Set the height of the figure
        )
            # Add the annotation (label)
        fig.add_annotation(
            text = f'State: {state}, Time Used: {time_used} ms',
            showarrow = True,
            arrowhead = 4
        )

        if local_show:
            fig.show()
        else:                 # Return the HTML representation of the plot
            return pio.to_html(fig, full_html=False)
#%%
    def Alarm(self, topic, message):
        global begin
        begin = 0
        publish_client = mqtt.Client()
        publish_client.connect(P_host, 1883, 60)
        publish_client.publish(topic, message)
        publish_client.loop_forever()
#%%
    def Run(self, data, id = None, local_show: bool = True):
        # record current timestamp
        start = datetime.datetime.now()
        self.Serch_Power(data)
        # detect abnomal
        raw_np = self.TransforTime(data, time_step)
        filter_np, base_index = self.FindBaseIndex(raw_np)
        start_index = int(self.FindStartIndex(filter_np, base_index))
        current_state = self.DetectCurrentState(filter_np, start_index)
        state_meesage = json.dumps({"state": current_state})
        client.publish(topic_state, state_meesage)
        # record loop end timestamp
        end = datetime.datetime.now()
        # find difference loop start and end time and display
        time_used = (end - start).total_seconds() * 10**3
        print(f"The time of execution of detect abnormal is : {time_used:.03f} ms")
        print(current_state)

        # return self.PlotlyResult(self.base_np, start_index, filter_np, local_show, current_state, time_used)
#%%
if __name__ == "__main__":
    detector = DetectAbnoraml()
    coefficient = detector.SerchMac(TargetMac)
    # 初始化MQTT Client
    client.on_connect = on_connect
    client.on_message = on_message
    # 啟動處理STH/pdata訊號的執行緒
    pdata_thread = threading.Thread(target=handle_pdata)
    pdata_thread.start()

    process_thread = threading.Thread(target=process)
    process_thread.start()

    # 連接到MQTT host並開始接收控制消息
    client.connect(S_host, port, 60)
    client.loop_forever()