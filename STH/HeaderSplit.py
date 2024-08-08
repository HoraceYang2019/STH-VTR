
'''
Created on 2024-01-24 03:05:58

Input: *.txt from STH
Ouput: {'MAC': '7cdfa139d4ce', 'Power': 7.52, 'Temperature': 32767, 'Packet Sequence Number': 0, 'RSSI': -32, 'TTOLP': 0}
((), ('196,126,0,131,36,197,0,128,189,132,0,129,162,96,0,130,185,126,0,131,28,197,0,128,185,132,0,129,134,96,0,130,201,126,0,131,25,197,0,128,201,132,0,129,143,96,0,130,214,126,0,131,24,197,0,128,188,132,0,129,129,96,0,130,221,126,0,131,4..

@author: MilkTea_shih
'''

#%%    Packages
import functools
import operator
import re

from typing import Any, Callable, Iterator, Optional, Union
from typing import Match, Pattern

#IntervalFormat: (start_index, end_index)
IntervalFormat = tuple[int, int]
#HeaderNameFormat: (key for dictionary, (type of value, base of value))
HeaderFormat = tuple[str, tuple[Any, ...]]
#PacketFormat: (multi-header, multi-content)
HeaderType = tuple[dict, ...]
ContentType = tuple[str, ...]
PacketFormat = tuple[HeaderType, ContentType]

#%%    Variable
delimiter: str = ' '  #TODO: add argument in InitSTH.py to define delimiter

#%%    Functions
#REVIEW: add decorator to return `HeaderInformation()`
# with the last or empty dictionary
def ParsePacket(delimiter: str = ' ') -> Callable:
    r: str = f'13{delimiter}'
    n: str = f'10{delimiter}'

    def PacketInformationSetter(func: Callable) -> Optional[Callable]:
        func_list: set[str] = {"HeaderInformation",
                               "ContentInformation",
                               "ParsePacket",
                               "PacketInformationSetter"
                               }

        def PacketInformation(strings: str
                              ) -> Union[PacketFormat, Callable]:
            header_rule: tuple[HeaderFormat, ...] = (
                ('MAC', (str,)),
                ('Power', (float,)),
                ('Temperature', (int, 16)),
                ('Packet Sequence Number', (int,)),
                ('RSSI', (int,)),   #Received Signal Strength Indicator
                ('TTOLP', (int,)),  #Transmission Time Of Last Packet
            )

            def FindHeader(pattern: Pattern, s: str) -> Iterator[Match]:
                return pattern.finditer(s)

            def Decimal2ASCII(string_decimal_: Match) -> list[str]:
                def IsValue(string: str) -> list[str]:
                    return string.strip(delimiter).split(delimiter)

                def Convert2ASCII(string_list: list[str]) -> str:
                    #TODO: timeit!
                    return ''.join(tuple(map(chr, map(int, string_list))))
                    #return ''.join(tuple(map(lambda x: chr(int(x)), string_list)))

                string_decimal: str = max(string_decimal_.groups(), key=len)
                value: filter = filter(str.strip,
                                       string_decimal.split(f'{delimiter}32'))
                words: list[str] = list(map(Convert2ASCII,
                                            map(IsValue, value)))

                return words

            def ConvertHeaderSetter(formats: tuple[HeaderFormat, ...]
                                    ) -> Callable:
                """Setter for `ConvertHeader` 
                to avoid reassign `formats` in each loop.

                Args:
                    formats (tuple[HeaderNameFormat, ...]): key and data type

                Returns:
                    Callable: _description_
                """
                def ConvertHeader(data_list: list[str]) -> dict:
                    dictionary: dict = {}

                    def ConvertType(data: str,
                                    format_: HeaderFormat
                                    ) -> tuple[str, Any]:
                        key, (convert, *base) = format_
                        return key, (data if isinstance(convert, str)
                                     else convert(data, base=base[0]) if base
                                     else convert(data))

                    # Split Battery Power and Temperature
                    data_list.insert(2, '')
                    data_list[1], data_list[2] = data_list[1].split(',')
                    #
                    dictionary.update(tuple(map(ConvertType,
                                                data_list, formats)))
                    return dictionary

                return ConvertHeader

            def GetIndexSetter(spans: list[Match], str_len: int) -> Callable:
                spans.reverse()    #NOTE: list.pop() after `reverse()`

                def GetIndex(interval: list[Union[IntervalFormat, Any]] = [],
                             temp: int = 0
                             ) -> list[IntervalFormat]:
                    interval = interval if temp else []
                    #REVIEW: list.pop(0) is bad, its time complexity is O(n²)
                    #use `iter()` to optimize or list.pop() after `reverse()`
                    #p.s.  list.pop() time complexity is O(1)
                    span: IntervalFormat = spans.pop().span() if spans \
                        else (str_len,) * 2  #2: `len(IntervalFormat)`

                    interval.append((temp, span[0] - 1))
                    temp = span[1]
                    return (GetIndex(interval, temp) if (spans
                                                         or temp != str_len)
                            else interval)

                return GetIndex

            def ExtractContent(s: str, intervals: list[IntervalFormat]
                               ) -> ContentType:
                #slice_string: Callable[[str, IntervalFormat], str] = lambda x, y: x[slice(*y)]
                slice_string: map = map(lambda x: s[slice(*x)], intervals)
                split_string: map = (map(str.split, slice_string) if delimiter == ' '
                                     else map(lambda x: x.split(delimiter), slice_string))

                def ConcatenateContent(s_list: tuple[list[str], ...]
                                       ) -> ContentType:
                    return tuple(functools.reduce(operator.iconcat, s_list, []))

                return ConcatenateContent(tuple(split_string))

            header_pattern: Pattern = re.compile(f'({r})?'
                                                 + f'({n}{r}{n})'
                                                 + f'(.*?)'
                                                 + f'({delimiter}{r}{n}{r}?)'
                                                 + f'({n}?)?')

            #REVIEW: check should clean string or not
            #before: strings = strings[:-1].strip(delimiter)
            #   string cleaning removes '\n' of the last element and `delimiter`
            strings = strings.strip().strip(delimiter)

            header_match: list[Match] = list(FindHeader(header_pattern,
                                                        strings))
            header_: map = map(Decimal2ASCII, header_match)
            header_info_: map = map(ConvertHeaderSetter(header_rule), header_)

            header_information: HeaderType = tuple(header_info_)

            if func_name == 'HeaderInformation':
                return func(header_information)

            get_content_index_setter: Callable = GetIndexSetter(header_match,
                                                                len(strings))
            content_interval: list[IntervalFormat] = get_content_index_setter()

            contents: ContentType = ExtractContent(strings, content_interval)
            if func_name == 'ContentInformation':
                return func(contents)

            return header_information, contents  #ParsePacket

        return PacketInformation if (func_name := func.__name__) in func_list \
            else print(f"[WARN]  {func_name} not in {func_list = }!")
    return PacketInformationSetter

@ParsePacket(delimiter)
def HeaderInformation(headers: HeaderType) -> dict:
    return headers[-1] if len(headers) else {}

@ParsePacket(delimiter)
def ContentInformation(contents: ContentType):
    #NOTICE: Maybe use more input,
    # such as the length of headers is more than one or equal to one
    # that separates `content + header` and `content + header + content`.
    #TODO: What is the information in content, e.g.,
    # length of contents, the first check byte(128 ~ 131), and the first byte.
    ...

#%%    Main
if __name__ == '__main__':
    file_index = 0
    target_folder: str = ""

    filenames: tuple[str, ...] = ("2024-02-22-10-34-12-2061",
                                  "2024-02-22-10-34-12-6292"
                                  )

    root_path: str = r"C:\VTR\RawData\Source\Data"
    test_path: str = r"C:\VTR\RawData\Source\Test"
    import pathlib
    target_path: pathlib.Path = pathlib.Path(test_path).joinpath(target_folder)

    def GetRawData(p: pathlib.Path) -> str:
        with open(p, 'r') as f:
            next(f)    #skip first line for '\n'
            raw_data: str = f.readline()
        return raw_data

    #raw_data: str = GetRawData(target_path.joinpath(f'{filename}.txt'))
    raw_data: str = GetRawData(target_path.joinpath(
        f'{filenames[file_index]}.txt'))

    header_info: dict = HeaderInformation("13 10 13 10 55 99 100 102 97 49 51 57 100 52 99 101 32 48 55 46 53 50 44 55 70 70 70 32 32 32 32 32 48 48 48 48 48 32 45 48 48 51 50 32 48 48 48 48 48 32 13 10 13 10 40 199 7 128 72 250 59 129 246 199 7 130 222 249 59 131 124 199 7 128 99 250 59 129 207 199 7 130 184 249 59 131 143 199 7 128 108 250 59 129 38 200 7 130 19 250 59 131 248 199 7 128 109 250 59 129 195 199 7 130 94 251 59 131 86 196 7 128 232 249 59 129 182 197 7 130 247 248 59 131 51 201 7 128 225 249 59 129 104 202 7 130 27 251 59 131 28 199 7 128 152 250 ")
    print(header_info)

    information: PacketFormat = ParsePacket(delimiter)(
        ParsePacket)(raw_data)
    print(information)
