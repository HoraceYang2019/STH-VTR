
'''
Created on 2024-04-26 13:42:18

@author: MilkTea_shih
'''

#%%    Packages
from dataclasses import dataclass
from typing import ClassVar, Dict, Protocol, Any

#%%    Variable


#%%    Functions
class IsDataclass(Protocol):
    # as already noted in comments, checking for this attribute is currently
    # the most reliable way to ascertain that something is a dataclass
    __dataclass_fields__: ClassVar[Dict[str, Any]]

def example_dataclass_only(x: IsDataclass):
    ...  # do something that only makes sense with a dataclass

#%%    Main Function


#%%    Main
if __name__ == '__main__':
    @dataclass
    class DataClass_:
        pass

    class NotDataClass:
        pass
    # a static type check should show that this line is fine ..
    example_dataclass_only(DataClass_())    # a static type check
    example_dataclass_only(NotDataClass())  # .. and this one is not

#%%
