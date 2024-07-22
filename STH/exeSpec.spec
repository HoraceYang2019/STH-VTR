# -*- mode: python ; coding: utf-8 -*-
# pyinstaller --noconfirm --clean exeSpec.spec
#     pathex=[r'C:/Users/hao/anaconda3/envs/STH-py3-11/Lib']
#   or pathex = [r'C:/Users/hao/anaconda3/envs/Python11/Lib'],
# C:\Users\hao\anaconda3\envs\STHW3

filename = 'runSTHJobs_1_r0' #'STHScan_7_0_2'#'DataProcess_10_5_1'##'STHComm_13_r1'#'DataProcess_10_5_1' #'STHScan_7_0_2' # # # 
block_cipher = None
py_files = [
    filename + '.py',
]

a = Analysis(
    py_files,
    pathex = [r'C:/Users/hao/anaconda3/envs/Python11/Lib'],
    binaries = [],
    datas = [],
    hiddenimports = ['paho.mqtt.client','paho.mqtt.subscribe','scipy.signal',
    'json','numpy','pywt','multiprocessing','pandas'],
    hookspath = [],
    hooksconfig = {},
    runtime_hooks = [],
    excludes = [],
    noarchive = False,
    cipher = block_cipher
)
pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    [],
    exclude_binaries = True,
    name = filename,
    debug = False,
    bootloader_ignore_signals = False,
    strip = False,
    upx = True,
    console = True,
    disable_windowed_traceback = False,
    argv_emulation = False,
    target_arch = None,
    codesign_identity = None,
    entitlements_file = None,
    icon = 'ICO/STHScan.ico'
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip = False,
    upx = True,
    upx_exclude = [],
    name = filename,
)
