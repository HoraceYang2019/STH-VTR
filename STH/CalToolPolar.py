# pythonnet
import clr
import sys
import threading
import time

DataFolder = r"C:/VTR/RawData/Output/ToolPolar/" 
base0 = DataFolder + r'2023-07-10-10-27-12.394400_.csv'
CSV_file = base0

LibFolder = r"C:/VTR/Library/"
Dll = LibFolder + r"ToolStatus"   # dll檔案位置
Ini = LibFolder + r"Setting.ini"  #ini檔案位置

ImgFolder = r"C:/VTR/NodeRed/ui/"
polar_file =  ImgFolder + r't2.png'
cmd = ''

# In[]
class calToolPolar(threading.Thread):    
    def __init__(self):
        threading.Thread.__init__(self)
        clr.AddReference(Dll)
        from ToolStatus import Def  # import ToolStatus.dll
        self.TS = Def.Tool() 
        self.TS.OpenFile(base0, Ini, ImgFolder + r't0.png')  #自動載入並計算特徵csv 
        self.TS.Data_Check()#檢查資料是否異常    
        #print(f'Before: {self.TS.unSym},{self.TS.maxTorqueRatio},{self.TS.deflection}') #輸出三大定義值

    def run(self):
        global cmd, CSV_file, polar_file
        
        while True:
            if cmd == '-b':   
                self.TS.OpenFile(DataFolder + CSV_file, Ini, ImgFolder + polar_file) 
                self.TS.Data_Check() 
                self.TS.Setini()
                cmd = ''
                print(f'\n[INFO]  <calToolPolar>->Base {CSV_file} with: {self.TS.unSym},{self.TS.maxTorqueRatio},{self.TS.deflection}') 

            if cmd == '-t':
                self.TS.OpenFile(DataFolder + CSV_file, Ini, ImgFolder + polar_file) 
                self.TS.Data_Check() 
                print(f'\n[INFO]  <calToolPolar>->Test {CSV_file} with: {self.TS.unSym},{self.TS.maxTorqueRatio},{self.TS.deflection}') 
                cmd = ''
            
            time.sleep(1)
            if cmd == '-q': break

#%%  usage: python -[b][t] filename 
if __name__ == '__main__':  
    
    print('usage: python -[b][t][q] datafile.csv ')
    
    cal_tool_polar = calToolPolar()
    cal_tool_polar.start()
    
    cmd = '-t'
    CSV_file = r'2023-07-10-10-28-08.540900_.csv'
    polar_file = r't3.png'

            