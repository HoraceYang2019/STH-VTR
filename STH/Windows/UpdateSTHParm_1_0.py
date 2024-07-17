# -*- coding: utf-8 -*-
"""
Created on Sun Jul 16 16:48:57 2023
load extranl InitSTH.py and InitSTH_u.json as the default parameters
@author: hao
"""
import importlib.util
import json
import typing
import types
import os

#%%:
version: str = 'UpdateSTHParm v1.0'

#%%
base_path: str = 'D:/Xuan/Code/STH/STH-W3-l/'
file_path: str = base_path + 'InitSTH.py'
updated_file: str = base_path + 'InitSTH_u.json'
module_name: str = ''
spec: typing.Any = importlib.util.spec_from_file_location(module_name, file_path)  #Any -> ModuleSpec
init: types.ModuleType = importlib.util.module_from_spec(spec)  # parameters from InitSTH.py
spec.loader.exec_module(init)            # parameters from InitSTH_u.json

updated_state: bool = os.path.exists(updated_file)
if updated_state:
    class toUpdate:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    with open(updated_file, encoding="utf-8") as f:
        data = json.load(f)

    updated: toUpdate = toUpdate(**data)
