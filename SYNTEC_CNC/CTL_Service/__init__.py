import threading
state = True
interval = 0.6
item = 4
state = True

class ShareVar():
    def __init__(self):
        self.cycle_start_event = threading.Event()
        self.init_status_event = threading.Event()

        self.buffer = [[],[]]
        self.buffer_index = 0
        self.save_index = 0
        self.ready_type = {'Ready': '0'}