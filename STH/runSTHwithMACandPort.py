'''
Created on 2024-05-27 21:50:45
@author: MilkTea_Shih, Horace_Yang
'''

#%%    Packages
import ctypes
import multiprocessing as mp
import pandas as pd
import time

from typing import Hashable, Optional, Sequence

import STHComm_13_r1 as STHComm

ConnectionFormat = tuple[ctypes.c_bool, STHComm.CommunicationModule]
    
#%%    Variable
FIXED_PORT: int = 6500

#NOTICE: e.g., [tool, mac, port] = ['T1', '7cdfa139d4ce', 6500]
tool_list: tuple[str, ...] = (
    'T1',
    'T2',  
    'T3',
    'T4'
)
mac_list: tuple[str, ...] = (
    '7cdfa139d4d6',
    '7cdfa1036646',
    '7cdfa139d4d6',
    '7cdfa1036646'
)
port_list: tuple[int, ...] = (
    6501,
    6502,
    6501,
    6502,
)

connection: pd.DataFrame = pd.DataFrame(zip(tool_list, mac_list, port_list),
                                        columns=('tool', 'mac', 'port'))
ConnectionMap = dict[Hashable, dict[str, str]]
max_timeout: float = 45 # in sec

#%%    Functions
def set_connection(mac: str, port: str) -> ConnectionFormat:
    assert isinstance(port, str)
    return (mp.Value(ctypes.c_bool, False, lock=False),
            STHComm.CommunicationModule(mac, port))

def establish_connection(parameter: ConnectionFormat,
                         process_time: float) -> float:
    connected_state, module_setup = parameter

    #with mp.Manager() as manager:
    #    stop_event: threading.Event = manager.Event()
    #stop_event: threading.Event = threading.Event()
    stop_event: ctypes.c_bool = mp.Value(ctypes.c_bool, False, lock=False)
    process: mp.Process = mp.Process(
        None, STHComm.RemoteCtl, module_setup.mac,
        (connected_state, module_setup, stop_event)
    )
    process.start()
    process_start_time: float = time.time()

    _timeout = False
    while not connected_state.value:
        time.sleep(0.1)
        if (time.time() - process_start_time) > max_timeout:
            _timeout  = True
            break 

    if not _timeout:
        #print(f'Connected to {module_setup.mac} by {module_setup.port}')
        start_processing_time: float = time.time()
        while time.time() - start_processing_time < process_time:
            time.sleep(1)

    process_total_time: float = time.time() - process_start_time
    stop_event.value = True

    try:
        process.kill()
    except AttributeError:
        del process
    except Exception as error:
        print(error)
    finally:
        del process

    return process_total_time

def view_connection_map(column_as_index: Optional[str] = None) -> None:
    if column_as_index is None:
        print(connection)
    else:
        try:
            df: pd.DataFrame = connection.set_index(connection.index)
        except (TypeError, KeyError) as error:
            print(f'{error} happened, it is using the default map.')
            df = connection
        finally:
            print(df)
            del df

# output: the current mac, port, and tool(ID) 
def get_module_setup(tool_name: str) -> dict[Hashable, str]:
    if tool_name in tool_list:
        module_setup: dict[Hashable, str] = {}
        connected_map: ConnectionMap = connection.set_index('tool').to_dict()
        for key, item in connected_map.items():
            module_setup[key] = str(item[tool_name])

        return module_setup # ex.{'mac': '7cdfa139d4d6', 'port': '6501'}
    else:
        raise KeyError

#%%    Main Function
def process_jobs(jobs: Sequence[tuple[str, float]]) -> float:
    processes_time: list[float] = [round(establish_connection(
        set_connection((module := get_module_setup(tool))['mac'],
                       module['port']),
        processing_time), 4) for tool, processing_time in jobs]

    print(f'{processes_time = }')
    print(f'Sum: {(amount_processing_time := sum(processes_time)):.3f}')

    return amount_processing_time

#%%    Main
if __name__ == '__main__':
    jobs: list[tuple[str, float]] = [
        ('T1', 30), ('T2', 30) , ('T3', 30), ('T4', 30)
        ]
    
    print('Working Performance:',
          f'{100*sum(job[1] for job in jobs) / process_jobs(jobs):.3f} %.',
          sep=' ')

#%%
#0.778934: 90, 115.5425138