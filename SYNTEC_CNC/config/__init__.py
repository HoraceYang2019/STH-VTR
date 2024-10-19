import json
import clr
def readconfig():
    with open('./config/CTLConfig.json') as j:
        data = json.load(j)
    return data
def ref_syntecAPi(ip):
    clr.AddReference('./config/Syntec.OpenCNC')
    from Syntec.Remote import  SyntecRemoteCNC # type: ignore
    return SyntecRemoteCNC(ip)