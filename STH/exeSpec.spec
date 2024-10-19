# pyinstaller --noconfirm --clean exeSpec.spec
# 'STHScan' 'STHComm' 'DataProcess' 'runSTHJobs' 'FileMerge'
# pathex => packages path

filename = 'DataProcess'
block_cipher = None
py_files = [
    filename + '.py',
]

a = Analysis(
    py_files,
    pathex = [r'C:\Users\user\anaconda3\envs\sth\Lib'],
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
