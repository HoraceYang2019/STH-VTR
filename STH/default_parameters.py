
'''
Created on 2024-02-23 13:16:52

@author: MilkTea_shih
'''

#%%    Packages
import dataclasses

import IsDataclassProtocol

#%%    Variable
@dataclasses.dataclass
class Parameters(IsDataclassProtocol.IsDataclass):
    # *key*: *hint*
    #  or  #
    # *key*: *hint* = *default value*
    time_interval: float = 0.5
    usage_order: tuple[str, ...] = ("cpu",
                                    "memory",
                                    "disk",
                                    "runtime interval")
    save_usage: bool = True
    record_system_usage_runtime_interval: bool = True


parameter_dict: dict = {
    # dictionary type, e.g.,
    #"default_key": "value",    #default_value
    # "*key*": *value*,    #*default value*
    "time_interval": 0.5,    #0.1
    "usage_order": ("cpu", "memory", "disk", "runtime interval"),
    "save_usage": True,
    "record_system_usage_runtime_interval": True,

}

#%%    Functions


#%%    Main Function


#%%    Main
if __name__ == '__main__':
    pass

#%%
