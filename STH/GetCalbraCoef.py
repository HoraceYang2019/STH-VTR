
'''
Created on 2023-09-12 13:56:20

@author: MilkTea_shih
'''
version: str = 'GetCalbraCoef v0.2'

#%%    Packages
import functools
import pathlib
import pandas as pd
# import win32api
from typing import Callable, Optional, Union
from typing import cast
import platform

#%%
import HeaderSplit as hds
import ParsePlan as pp

#%%    Variable
if platform.system() == "Windows":
    default_path: str = r"C:/VTR/RawData/Coefficient"
    filepath: str = r"C:/VTR/RawData/Source/Data"
else:
    default_path: str = "/var/VTR/RawData/Coefficient"
    filepath: str = "/var/VTR/RawData/Source/Data"
default_file: str = "AvailableSTH.csv"
filename: str = "coef"
file_extension: str = ".csv"

coef_name: tuple[str, ...] = ('CH1_A', 
                              'CH1_B', 
                              'CH2_A', 
                              'CH2_B', 
                              'CH3_A', 
                              'CH3_B', 
                              'CH4_A', 
                              'CH4_B')

holder_height = 108.0
#path: "C:\VTR\RawData\Source\Data\(2023-08-31-12-55)\(2023-09-12-15-10)\2023-08-15-17-08-00-019217.txt"
#%%%
test_input: str = ""

#%%    Functions
def CheckMAC(s: str, df: pd.DataFrame) -> list[bool, Optional[pd.Series], str]:
    header_MAC: Optional[str]
    normal: bool = False
    
    if not (header_MAC := hds.HeaderInformation(s).get("MAC", None)):
        print('[TRAC]  In this package, there is no MAC in RawData')
        return normal, None, None    #didn't find MAC in RawData
    if not tuple(df.index.intersection((header_MAC,))):
        print(f'''
              \r[WARNING]  {header_MAC} is not in the file of default coef!
              \rUsing 1 to be the coef in every channel.
              ''')
        return normal, pd.Series((1,) * len(df_c := df.columns), index=df_c), header_MAC  #, name=f'{header_MAC}'
    normal = True
    return normal, df.loc[header_MAC], header_MAC

def GetDefaultCoef(raw_data: str, coef_path: pathlib.Path) \
    -> tuple[tuple[Optional[tuple[float, ...]], Optional[tuple[float, ...]]], bool]:
    def OpenFile(p: str, f: str) -> Optional[pd.DataFrame]:
        try:
            df: pd.DataFrame = pd.read_csv(filepath_or_buffer := (pathlib.Path(p).joinpath(f)),  index_col = 0, 
                                           )
        except FileNotFoundError:
            print(f'''
                  \rMissing the file of default coef, please put the file under the path:
                  \r{filepath_or_buffer.parent}\\
                  \n\rFile Name: {filepath_or_buffer.name}
                  ''')
            return None
        except PermissionError as err:
            print(err)
            """
            re try
            """
            return None
        except Exception as err:
            print(err)
            return None
        else:
            df.dropna(axis=0, how='any', inplace=True)
            
            return df
    
    def GetCoefValue(s: str, df: pd.DataFrame) -> tuple[bool, Optional[tuple[float, ...]], Optional[tuple[float, ...]]]:
        #print(f'[TRAC]  available MACs are {df.index}')

        # df_ = [normal, df.loc[header_MAC], header_MAC]
        flag, coef_df, header_mac = CheckMAC(s, df)
        if coef_df is not None:
            coefs: tuple[tuple[str, float, str], ...] = \
                tuple(sorted(filter(lambda x: x[0] in coef_name, 
                                    zip(df_ii := ((df_v := coef_df).index), 
                                        df_v, 
                                        df_ii)), 
                             key=lambda x: (x[2][-1], x[0])))
            
            coef_list: list[float] = list(map(lambda x: x[1], coefs))
            a, b = coef_list[:(coef_dict_len := int(len(coefs)/2))], coef_list [coef_dict_len:] 

            # get the actual full length of tool to correct bending forces
            # GetSTHApt-> input: sth_id(mac), output: tool_id, full_height, flute_height  
            flute_height = pp.GetSTHApt(header_mac)[0][-1] 
            for i in [2,3]: # bending forces in CH2 and CH3
                a[i] = round(float(a[i])* holder_height/(holder_height + flute_height), 1)
            # get the actual full length of tool 

            return (flag, a, b, header_mac) # True, coef_a, coef_b, mac
        else:
            return (flag, None, None, header_mac) # False, none, none, mac
        
    def SaveCoef(df_b: bool, a: Optional[tuple[float, ...]], b: Optional[tuple[float, ...]], mac: str, f_p: pathlib.Path) -> bool:
        if a and b:
            pd.DataFrame((*zip(a, b),)).to_csv(f_p, mode='w', header=None, index=None)
            (0 if df_b 
             else f_p.rename(f_p.parent.joinpath("Coef" + file_extension)))
            return True
        return False
    
    coef: list[bool, Optional[tuple[float, ...]], Optional[tuple[float, ...]], str] = \
        GetCoefValue(raw_data, OpenFile(default_path, default_file))    
    
    return coef[1:-1], SaveCoef(*coef, coef_path), coef[-1]
    
@functools.lru_cache()
def GetSettingCoef(f: pathlib.Path) -> tuple[Optional[tuple[float, ...]], ...]:
    try:
        a, b, *_ = (*zip(*pd.read_csv(f, header=None).itertuples(False)),)
    except PermissionError as err:
        print(err)
        return (None, None)
    except Exception:
        # win32api.ShellExecute(0, 'open', 'notepad.exe', str(f), '', 1)
        """
        pyautogui
        """
        return (None, None)
    
    return (a, b)

#%%    Main Function
def GetCoef(s: str, f_p: str = filepath, f_n: str = filename, f_ext: str = file_extension) \
    -> tuple[bool, tuple[Optional[tuple[float, ...]], ...]]:
    _state = False
    header_mac = ''
    if (boolean := ( available := pathlib.Path(f_p).joinpath(f_n + f_ext)).exists()):
        result = GetSettingCoef(available)
        #return GetSettingCoef(undefault)
    else:
        result, _state, header_mac = GetDefaultCoef(s, available)
        #return GetDefaultCoef(s, undefault)
        
    #print(f'{boolean = }\n{result = }')
    return (boolean or _state, result, header_mac) 

#%%    Main
if __name__ == '__main__':
    print(GetCoef(test_input))