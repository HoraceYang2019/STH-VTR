"""CNC 資料採集、非同步 MQTT 傳送與 CSV 紀錄；僅使用讀取 API。"""

import time
import json
import queue
import threading
import datetime
import numpy as np
import paho.mqtt.client as mqtt
import statistics
import os
import csv


# 載入新代 CNC 設定
import config

# --- CNC 連線管理類別 (改用 Syntec API) ---
class SyntecCNCManager:
    def __init__(self):
        # 讀取 config 設定並初始化 API
        self.config_ = config.readconfig()
        self.api = config.ref_syntecAPi(self.config_['IP_ADDRESS'])
        self.ip = self.config_['IP_ADDRESS']

        # 計數器和緩存機制
        self.read_count = 4
        self.last_spindle = 0
        self.last_feed = 0
        self.last_ext = np.array([0, 0, 0], dtype=np.float64)
        self.last_g54 = np.array([0, 0, 0], dtype=np.float64)
        # 初始擷取旗標：只在程式啟動期間擷取一次，之後回傳 None
        self.initial_ext_captured = False
        self.initial_ext_returned = False
        self.initial_ext = None

        self.initial_g54_captured = False
        self.initial_g54_returned = False
        self.initial_g54 = None

        # H1～H10 刀長補正：保留 double 精度，首次成功讀取後記錄一次。
        self.initial_length_comp = None
        self.initial_length_comp_returned = False

    def connect(self):
        """
        Syntec API 的連線機制通常在初始化或首次呼叫時建立。
        利用讀取狀態來測試連線是否真正通暢，具備無限重試機制。
        """
        while True:
            try:
                # 嘗試發送一次簡單的讀取請求作為 ping
                self.api.READ_status()
                print(f"\n成功連線至 Syntec CNC ({self.ip})")
                break
            except Exception as e:
                print(f"\r無法連線至 CNC ({self.ip})，5 秒後自動重試... ", end="", flush=True)
                time.sleep(5)

    def read_data(self):
        """讀取資料，若發生異常 (例如網路斷開)，回傳 None 讓主迴圈處理"""
        try:
            # 呼叫 CNC API 取得各項資料
            start_time = datetime.datetime.now()

            coord = self.api.READ_position()[4]
            position_time = datetime.datetime.now()
            position_delay = (position_time - start_time).total_seconds() * 1000

            # EXT / G54: 只在啟動時擷取一次，之後回傳 None
            try:
                ext_raw = self.api.READ_work_coord_single('EXT')[1]
            except Exception:
                ext_raw = None
            if (not self.initial_ext_captured) and (ext_raw is not None):
                try:
                    # 保留控制器原始精度，避免 float16 將座標小數捨去。
                    ext_arr = np.array(ext_raw, dtype=np.float64)
                    if ext_arr.size >= 3 and not np.any(np.isnan(ext_arr)):
                        self.initial_ext = ext_arr
                        self.initial_ext_captured = True
                except Exception:
                    pass

            try:
                g54_raw = self.api.READ_work_coord_single('G54')[1]
            except Exception:
                g54_raw = None
            if (not self.initial_g54_captured) and (g54_raw is not None):
                try:
                    g54_arr = np.array(g54_raw, dtype=np.float64)
                    if g54_arr.size >= 3 and not np.any(np.isnan(g54_arr)):
                        self.initial_g54 = g54_arr
                        self.initial_g54_captured = True
                except Exception:
                    pass

            if self.initial_length_comp is None:
                try:
                    offsets = np.asarray(
                        self.api.READ_offset_scope(1, 10)[1], dtype=np.float64
                    )
                    if (offsets.ndim == 2 and offsets.shape[0] >= 10
                            and offsets.shape[1] >= 3
                            and np.all(np.isfinite(offsets[:10, 2]))):
                        self.initial_length_comp = offsets[:10, 2].tolist()
                except Exception:
                    # 讀取失敗時留待下次重試，不以零值冒充實際補正值。
                    pass

            nc_point = int(self.api.READ_nc_pointer()[1])
            nc_point_time = datetime.datetime.now()
            nc_point_delay = (nc_point_time - position_time).total_seconds() * 1000

            # 四次更新才更新一次 進給跟轉速，大約 1200ms ~ 1600ms 更新一次
            # 預設為 None，只有每第 4 次才去呼叫 API 並回傳值
            self.read_count += 1
            spindle_val = None
            feed_val = None
            if self.read_count >= 4:
                # 每四次讀取才更新一次 spindle 和 feed，減少 API 呼叫頻率
                try:
                    spindle_raw = self.api.READ_plc_addr('R', 2, 2)
                    if spindle_raw and len(spindle_raw) > 4 and spindle_raw[4]:
                        spindle_val = spindle_raw[4][0]
                except Exception:
                    spindle_val = None

                try:
                    feed_raw = self.api.READ_plc_addr('R', 700, 700)
                    if feed_raw and len(feed_raw) > 4 and feed_raw[4]:
                        feed_val = feed_raw[4][0] / 1000
                except Exception:
                    feed_val = None

                self.read_count = 0

            feed_time = datetime.datetime.now()

            spindle = spindle_val
            feed = feed_val

            status = self.api.READ_status()[5]

            end_time = datetime.datetime.now()
            status_delay = (end_time - feed_time).total_seconds() * 1000
            total_delay = (end_time - start_time).total_seconds() * 1000

            # 正常印出資訊 (使用 \r 覆蓋同一行)
            feed_str = f"{feed:.2f}" if (feed is not None) else "None"
            spindle_str = f"{spindle:.2f}" if (spindle is not None) else "None"
            output_str = (
                f"\r[Status: {status}] "
                f"座標 [X: {coord[0]:8.3f}, Y: {coord[1]:8.3f}, Z: {coord[2]:8.3f}] | "
                f"NC_Point: {nc_point} | F: {feed_str} | S: {spindle_str}    "
                f"總延遲: {total_delay:.2f} ms"
            )
            print(output_str, end="", flush=True)

            # 準備 EXT/G54 回傳值：只有第一次回傳實際數值，之後為 None
            if self.initial_ext_captured and (not self.initial_ext_returned):
                ext_x = float(self.initial_ext[0])
                ext_y = float(self.initial_ext[1])
                ext_z = float(self.initial_ext[2])
                self.initial_ext_returned = True
            else:
                ext_x = None
                ext_y = None
                ext_z = None

            if self.initial_g54_captured and (not self.initial_g54_returned):
                g54_x = float(self.initial_g54[0])
                g54_y = float(self.initial_g54[1])
                g54_z = float(self.initial_g54[2])
                self.initial_g54_returned = True
            else:
                g54_x = None
                g54_y = None
                g54_z = None

            length_comp = None
            if (self.initial_length_comp is not None
                    and not self.initial_length_comp_returned):
                length_comp = self.initial_length_comp
                self.initial_length_comp_returned = True

            return {
            "t_request": start_time,
            "t_receive": end_time,
            "coord": coord,
            "nc_point": nc_point,
            "spindle": spindle,
            "feed": feed,
            "status": status,

            "EXT_X": ext_x,
            "EXT_Y": ext_y,
            "EXT_Z": ext_z,
            "G54_X": g54_x,
            "G54_Y": g54_y,
            "G54_Z": g54_z,
            "LengthComp": length_comp,
        }

        except Exception as e:
            # 如果讀取過程報錯，表示連線可能中斷
            print(f"\n讀取資料失敗 (網路或 API 異常): {e}")
            # 回傳 None，觸發外部的重新連線機制
            return None

    def disconnect(self):
        # 若 Syntec API 內部有提供關閉連線的方法可在此呼叫，否則僅作提示
        print("\nCNC 連線已停止讀取")

# --- MQTT 連線管理類別 (維持原樣) ---
class AsyncMQTTManager:
    def __init__(self, broker="10.0.0.103", topic="STH/CNC"):
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.topic = topic
        self.broker = broker
        self.data_queue = queue.Queue()
        self.running = True

    def connect(self):
        while True:
            try:
                self.client.connect(self.broker, 1883, 60)
                print(f"\n成功連線至 MQTT Broker ({self.broker})")
                break
            except Exception as e:
                print(f"\r無法連線至 MQTT Broker ({self.broker})，5 秒後重試... ", end="", flush=True)
                time.sleep(5)

        self.client.loop_start()
        self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.worker_thread.start()

    def _process_queue(self):
        while self.running:
            try:
                data = self.data_queue.get(timeout=1)
                payload = json.dumps(data)
                self.client.publish(self.topic, payload, qos=1)
                self.data_queue.task_done()
            except queue.Empty:
                continue

    def add_to_queue(self, data):
        self.data_queue.put(data)

    def stop(self):
        self.running = False
        self.client.loop_stop()
        self.client.disconnect()

# --- 外部主程式 ---
def main_calculation():
    print("系統啟動，準備初始化連線...")

    # 1. 初始化 MQTT
    settings = config.readconfig()
    mqtt_manager = AsyncMQTTManager(
        broker=settings['MQTT_HOST'], topic=settings['STATUS_TOPIC']
    )
    mqtt_manager.connect()

    # 2. 初始化 Syntec CNC 連線
    cnc_manager = SyntecCNCManager()
    cnc_manager.connect()
    log = []

    try:
        while True:
            # 3. 讀取資料
            nc_values = cnc_manager.read_data()

            # 若發生斷線或異常，nc_values 會是 None
            if not nc_values:
                print("準備重新建立 CNC 連線...")
                time.sleep(2)
                cnc_manager.connect()
                continue

            # 4. 組織 MQTT 酬載 (Payload)
            result = {
                "Time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                "t_request": nc_values.get("t_request", datetime.datetime.now()).isoformat(),
                "t_receive": nc_values.get("t_receive", datetime.datetime.now()).isoformat(),
                "NC_point": str(nc_values["nc_point"]),
                "Actual_Spindle_RPM": nc_values["spindle"],
                "Actual_Feed_mm_min": nc_values["feed"],
                "Offset_X": nc_values["coord"][0],
                "Offset_Y": nc_values["coord"][1],
                "Offset_Z": nc_values["coord"][2],
                "Status": str(nc_values["status"]),
                "EXT_X": nc_values["EXT_X"],
                "EXT_Y": nc_values["EXT_Y"],
                "EXT_Z": nc_values["EXT_Z"],
                "G54_X": nc_values["G54_X"],
                "G54_Y": nc_values["G54_Y"],
                "G54_Z": nc_values["G54_Z"],
                "LengthComp": nc_values["LengthComp"],
            }
            log.append(result)
            mqtt_manager.add_to_queue(result)

            # 採樣頻率 0.1 秒
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n測試結束，開始統計與儲存資料...")

        # 建立 log 資料夾
        os.makedirs("logs", exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = f"logs/cnc_latency_log_{timestamp}.csv"
        if log:
            keys = log[0].keys()
            with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
                dict_writer = csv.DictWriter(f, fieldnames=keys)
                dict_writer.writeheader()  # 寫入第一列標題
                dict_writer.writerows(log) # 寫入所有資料內容
            print(f"已儲存紀錄檔: {csv_path}")
        else:
            print("尚未收到資料，沒有紀錄可儲存。")

        # # 開啟儲存的 csv 檔案，讀取 cnc_delay_s 欄位資料
        # with open(csv_path, "r", encoding="utf-8-sig") as f:
        #         reader = csv.DictReader(f)
        # # 統計延遲
        # if latencies:
        #     mean_delay = statistics.mean(latencies) * 1000
        #     min_delay = min(latencies) * 1000
        #     max_delay = max(latencies) * 1000
        #     std_delay = statistics.stdev(latencies) * 1000 if len(latencies) > 1 else 0

        #     print("\n CNC 延遲統計結果")
        #     print(f"筆數: {len(latencies)}")
        #     print(f"平均延遲: {mean_delay:.2f} ms")
        #     print(f"最小延遲: {min_delay:.2f} ms")
        #     print(f"最大延遲: {max_delay:.2f} ms")
        #     print(f"標準差: {std_delay:.2f} ms")
        # else:
        #     print("沒有任何延遲資料。")

    finally:
        mqtt_manager.stop()
        cnc_manager.disconnect()
