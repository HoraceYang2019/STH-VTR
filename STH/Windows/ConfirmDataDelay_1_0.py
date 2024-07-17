
'''
Created on 2024-01-24 03:22:09

@author: MilkTea_shih


INPUT: folder path of txts
OUTPUT: xlsx extension with columns
    column:  
        FileName ; TTOLP ; TimeDifference ; nextTimeTag ; DataLength ; 
        ContentLength ; PacketSequenceNumber

'''

#%%    TODO:
'''
    1.  verify MAC in this folder, if find the minority, return filename
    2.  add RSSI column
    3.  add more column to confirmation, 
        -1: calculate the correct data length by its timeDifference
            column name: ActualLength
            formula: `timeDifference` * `sampling rate`
        -2: subtract the actual length from the theoretical
            column name: LengthDifference
            formula: `timeDifference` * `sampling rate` - `DataLength`
        -3: judgmental of length difference
            column name: LengthDifference_bool
            formula: `True` if `LengthDifference` >= 0 else `False`
        -X:
            column name: 
            formula: 
        
    4. 
'''

#%%    Packages
import datetime
import functools
import numpy as np
import numpy.typing as npt
import operator
import pandas as pd   # type: ignore
import pathlib

import HeaderSplit_4_1_1 as HeaderSplit
import STHSense_2_0 as STHS

from typing import Any, Callable, Generator, Iterator, Optional, Sequence, Union
DataFrameFormat = tuple[str, datetime.datetime, int, float, str, int, int, int]
IntervalFormat = tuple[int, int]
PathFormat = Union[pathlib.Path, str]

#%%    Variable
delimiter: str = ' '
#REVIEW: rule setting
raw_data_naming_rule: str = "%Y-%m-%d-%H-%M-%S-%f"
datetime_rule: str = "%H:%M:%S.%f"

default_excel_datetime_format: str = "hh:mm:ss.000"
#
#TODO: add argument to save the digit of the filename
filename_decimal_digit: int = 4

#%%    Functions
def GetFileNameOfData(p_: PathFormat,
                      ext: str = ''
                      ) -> Generator:
    p: pathlib.Path = pathlib.Path(p_) if isinstance(p_, str) else p_
    return p.glob(f'*.{ext}' if ext else '*')

def CalculateFilenameDigit(num_decimal: int,
                           *,
                           max_digit: int = 6
                           ) -> Optional[int]:
    digit: Optional[int] = (int(num_decimal - max_digit) if (num_decimal
                                                             < max_digit)
                            else None)
    return digit

def GetRawData(p: pathlib.Path) -> str:
    with open(p, 'r') as f:
        next(f)    #skip first line for '\n'
        raw_data: str = f.readline()
    return raw_data

def ZipVariable(*args: Any) -> Iterator:
    def Map2Tuple(arg: map) -> tuple:
        return tuple(arg)
    return zip(*map(Map2Tuple, args))

@functools.lru_cache()
def ConvertContentSetter(*v_: Union[int, npt.NDArray[np.float64]]
                         ) -> Callable:
    v: Union[tuple[int, int, npt.NDArray[np.float_]], tuple[object, ...]] = \
        v_ if v_ else (4, 3, np.asarray((1, 1, 1, 1)))

    def ConvertContent(c: Sequence[str]) -> Union[list[list[float]], list[Any]]:
        return STHS.ParseRawData(np.asarray(c), *v)[1] if len(c) > 344 else []

    return ConvertContent

def LengthOf2DSequence(iters: Sequence[Sequence]) -> tuple[int, ...]:
    return tuple(map(len, iters))

def GetHeadersValueSetter(*keys: str) -> Callable:
    def GetHeadersValue(headers: tuple[dict, ...]
                        ) -> tuple[tuple[Any, ...], ...]:
        def GetValue(header: dict) -> tuple[Any, ...]:
            value: map[Callable[[str], Any]] = map(
                lambda x: header.get(x, np.nan), keys)
            return tuple(value)

        #return tuple(map(lambda x:
        #    tuple(map(lambda y: x.get(y, np.nan),
        #              keys)),
        #    headers))
        return tuple(map(GetValue, headers))

    return GetHeadersValue

def FilePath2DateTime(string: pathlib.Path,
                      t_format: str = "%Y-%m-%d-%H-%M-%S-%f"
                      ) -> datetime.datetime:
    return datetime.datetime.strptime(string.stem, t_format)

def Time2StrSetter(slice_num: Optional[int] = -2) -> Callable:
    def TimeFormat(t_format: str) -> Callable:
        def Time2Str(time: datetime.datetime) -> str:
            return time.strftime(t_format)[:slice_num]

        return Time2Str
    return TimeFormat

def CalculateTimeDifference(time1: datetime.datetime,
                            time2: datetime.datetime
                            ) -> float:
    return operator.sub(time2, time1).total_seconds()

def FlatData(data_zip: Iterator) -> list[DataFrameFormat]:
    """Flat data if the number of header in a packet is plural, 
    e.g., tuple[tuple[dict, ...]] -> tuple[dict, ...].

    Args:
        data_zip (Iterator): all data in zip iterator

    Returns:
        list[DataFrameFormat]: flatten data
    """
    data_list: list[Union[DataFrameFormat, Any]] = []
    b4header_value: int = 2
    data_slice: slice = slice(0, b4header_value)

    def DataOrder(temp: list[Any], value: tuple[int, int]) -> None:
        """Separate the element in `value` which gets from the header, 
        e.g., Transmission Time Of Last Packet and Packet Sequence Number, 
        and append into `data_list` in the outer function.

        Args:
            temp (list[Any]): all values except header's
            value (tuple[int, int]): value of header

        Returns:
            _type_: `list.append()` returns no value
        """
        return data_list.append((*temp[:b4header_value],
                                 value[0],
                                 *temp[b4header_value:],
                                 value[1]))

    def DataFlatten(data: tuple[Any, tuple[tuple[int, int], ...]]) -> None:
        *data_temp, header_value = data
        data_temp_: list[Any] = [0] * len(data_temp)
        if (header_value_length := len(header_value) - 1):
            ""
            *data_temp_[data_slice], data_temp_[b4header_value + 1] = \
                *data_temp[data_slice], data_temp[b4header_value + 1]

        tuple(map(DataOrder,
                  (data_temp, *((data_temp_,) * header_value_length)),
                  header_value))

    tuple(map(DataFlatten, data_zip))
    return data_list

def VerifyMAC(headers: tuple[dict, ...]
              ) -> Union[tuple[str, ...], tuple]:
    header_MAC: filter = filter(lambda x: x != np.nan,
                                map(GetHeadersValueSetter("MAC"),
                                    headers))
    MAC_set: set[tuple[str]] = set(functools.reduce(operator.iconcat,
                                                    header_MAC,
                                                    []))
    MAC_list: Union[tuple[str, ...], tuple]
    if len(MAC_set) == 1:
        MAC_list = next(iter(MAC_set))
    else:
        MAC_list = tuple(functools.reduce(operator.iconcat,
                                          MAC_set,
                                          []))

    return MAC_list

def MakeSheetName(strings: Union[tuple[str, ...], tuple]) -> str:
    if strings:
        return ','.join(strings)
    else:
        return 'MAC_not_found'

def CheckOutputPath(folder: str,
                    extension: str,
                    reference_path: pathlib.Path | str,
                    max_retry: int = 10
                    ) -> PathFormat:
    output_temp: str = (''.join(folder_split) if (len(folder_split :=
                                                      folder.split('\\'))
                                                  > 1)
                        else folder)

    reference_path = pathlib.Path(reference_path)
    output_path: pathlib.Path = reference_path.joinpath(output_temp)
    0 if reference_path.exists() else reference_path.mkdir(parents=True,
                                                           exist_ok=True)

    output_path = output_path.with_suffix(extension)
    file_exist: Callable = pathlib.Path(output_file :=
                                        output_path.as_posix()).exists

    msg: str
    if file_exist():
        retry_init: int = 1
        retry: int = retry_init
        new_filename: tuple[str, ...] = (output_path.stem,
                                         '_',
                                         str(retry)
                                         )
        #output_file = output_file.replace(new_filename[0],
        #                                  ''.join(new_filename))
        while retry < max_retry if file_exist() else False:
            if retry != retry_init:
                msg = f'[WARN]  {file_exist() = }: {output_file}\n' \
                    + f'Start looking for path not exist in ' \
                    + f'{max_retry - retry} times.'
                output_file = output_file.replace(f"_{retry - 1}",
                                                  f"_{retry}")
            else:
                msg = f'[WARN]  {file_exist() = }: {output_file}\n' \
                    + f'Start looking for path not exist in ' \
                    + f'{max_retry - retry} times.'
                output_file = output_file.replace(new_filename[0],
                                                  ''.join(new_filename))

            print(msg, end='\n\n')

            file_exist = pathlib.Path(output_file).exists
            retry += 1
        else:
            mode: str
            if not file_exist():
                mode = "Y"
                msg = f'[INFO]  New filepath will be: {output_file}'
                print(msg)
            else:
                #output_file = output_file.replace(f"_{retry - 1}",
                #                                  f"_{retry - 2}")
                msg = f'[WARN]  {output_file} will be replaced!\n' \
                    + f'[ACTION]  Enter "y/Y" to replace or just ENTER\n\n'
                print(msg)
                mode = input("[ACTION]  Replace the file?  (y/Y)\n"
                             + "[OPTION]: ")

                mode = mode[0] if mode else mode

            if mode == 'Y' or mode == 'y':
                output_path = pathlib.Path(output_file)
            else:    #mode == 'N' or mode == 'n'
                return output_temp
    else:
        msg = f'[INFO]  {file_exist() = }: \n' \
            + f'Filepath will be: {output_file}\n'
        print(msg)

    return output_path

#%%    Main Function
def DataConfirmation(folder_name: str, max_retry_time: int = 10) -> None:
    output_path: pathlib.Path = pathlib.Path("C:\VTR\RawData\Verify")
    output_extension: str = '.xlsx'
    root_path: str = r"C:\VTR\RawData\Source\Data"
    target_path: pathlib.Path = pathlib.Path(root_path).joinpath(folder_name)
    #
    file: tuple[pathlib.Path, ...] = tuple(GetFileNameOfData(target_path,
                                                             'txt'))

    slice_filename: Optional[int] = CalculateFilenameDigit(filename_decimal_digit)
    convert_time2str_setter: Callable = Time2StrSetter(slice_filename)

    #REVIEW: use HeaderSplit_4_1.ParsePacket()
    ParsePacket: Callable = HeaderSplit.ParsePacket(delimiter)
    information: map = map(ParsePacket(ParsePacket),
                           map(GetRawData, file))
    header_information, content = zip(*tuple(information))

    #Union[list[list[float]], list[Any]]
    data: map = map(ConvertContentSetter(), content)

    content_length, data_length = tuple(map(LengthOf2DSequence,
                                            (content, tuple(data))))

    header_value_list: tuple[str, ...] = ("TTOLP",
                                          "Packet Sequence Number",
                                          )
    #tuple[IntervalFormat, ...]
    header_value: map = map(GetHeadersValueSetter(*header_value_list),
                            header_information)

    file_time: tuple[datetime.datetime, ...] = tuple(map(FilePath2DateTime,
                                                         file))
    #Callable[[int], str]
    file_name: map = map(convert_time2str_setter(raw_data_naming_rule),
                         file_time)

    next_time: list[datetime.datetime] = list(file_time[1:])
    next_time.append(next_time[-1])  #copy the last element to fill up

    time_difference: tuple[float, ...] = tuple(map(CalculateTimeDifference,
                                                   file_time,
                                                   next_time))

    next_time_str: map[str] = map(convert_time2str_setter(datetime_rule),
                                  next_time)

    data_columns: tuple[str, ...] = ("FileName",
                                     "DateTime",
                                     "TTOLP",
                                     "TimeDifference",
                                     "nextTimeTag",
                                     "DataLength",
                                     "ContentLength",
                                     "PacketSequenceNumber",
                                     )
    data_zip: Iterator = ZipVariable(file_name,
                                     file_time,
                                     time_difference,
                                     next_time_str,
                                     data_length,
                                     content_length,
                                     #the last must be `header_value`
                                     header_value,
                                     )
    '''
    #REVIEW: variable in data_zip:
        #NOTE: [...] means there are multiple elements in the same index
        FileName -> file_name
        DateTime -> file_time
        TTOLP -> header_value[...][0]
        TimeDifference -> time_difference
        nextTimeTag -> next_time_str
        DataLength -> data_length
        ContentLength -> content_length
        PacketSequenceNumber -> header_value[...][1]
    '''
    data_frame_: list[DataFrameFormat] = FlatData(data_zip)

    #TODO: verify MAC here
    # if `len(MAC_list)` > 1, add 1 more column to recode
    MAC_list: Union[tuple[str, ...], tuple] = VerifyMAC(header_information)
    #TODO: discuss the sheet name rule
    sheet_name: str = MakeSheetName(MAC_list)

    data_frame: pd.DataFrame = pd.DataFrame(data_frame_,
                                            columns=data_columns, )

    output_file: PathFormat = CheckOutputPath(folder_name,
                                              output_extension,
                                              output_path,
                                              max_retry_time)
    if isinstance(output_file, pathlib.Path):
        with pd.ExcelWriter(f'{output_file}', 'auto', None,
                            default_excel_datetime_format, 'w') as w:
            #sheet name: MAC of the first header
            data_frame.to_excel(w, sheet_name, index=False)

        print(f"\n\n[INFO]  Done!\nThe result is at {output_file.as_posix()}.\n")
    else:  #type(output_file) == str
        #retry_filename: pathlib.Path = output_path.joinpath(f'{output_file}_'
        #                                                    + f'{max_retry_time - 1}'
        #                                                    + f'{output_extension}')
        print(f"\n\n[INFO]  {output_file = }: means the filename exists in "
              + f"'{output_path.as_posix()}' with {max_retry_time} times!\n")


#%%    Main
if __name__ == '__main__':
    #target_folder: str = '(2023-12-11-17-43)'
    target_folder: str = 'Test'
    #sub_folder: str = '(2023-12-28-14-12)'  #no sub folder: ''
    sub_folder: str = 'TestComm12_1'
    #sub_folder: str = ''

    #target_folder: str = ""

    DataConfirmation('\\'.join((target_folder, sub_folder)) if sub_folder
                     else target_folder)
    pass

#%%
