# -*- coding: utf-8 -*-
#--------------------------------------------------------------------------------------------------------
Release time
  6/14, 2024
********************************************************************************************
Structure of Code Folder: 

STH-W3-I                       # major folder
    InitSTH.py                 # the inital parameters for STH associated files
    initSTH_u.json             # updated parameters of InitSTH.py by UI
    
  ---- communicate with STH
    STHComm_13_r1.py           # communicate with STH 3
        HeaderSplit_4_1_1           # split message header from STH data  
        Printer_1_0                 # print header
        STHSync_5_0                 # on-line sync command via STH/sync 
            ParseData_2_1           # parse raw data, detrend, avaerage, and calculate torque
                Denoise_1_1         # denoise raw signal
                STHSense_2_0        # parse analog dataprocess into digital
            UpdateSTHParm_1_0
        UpdateSTHParm_1_0           # adopt the updated parameters
        MonitorNetSocket_1_0        # monitor a loss of network socket
        MonitorSystemUsage_1_0      # monitor the usages of CPU and memory

    STHComm_11_0_1.py               # communicate with STH 3
        HeaderSplit_2_0             # split message header from STH data  
        Printer_1_0                 # print header
        STHSync_4_2_3               # on-line sync command via STH/sync 
            ParseData_1_2_1         # parse raw data into torque
                Denoise_1_1_1       # denoise raw signal
                STHSense_2_0_1      # parse analog dataprocess into digital
                InitCollection_1_0  # initial conditions          
            UpdateSTHParm_1_0
        UpdateSTHParm_1_0       # adopt the updated parameters
    
    STHComm_10_4_0.py               # communicate with STH 3
        HeaderSplit_1_1             # split message header from STH data  
        Printer_1_0                 # print header
        STHSync_4_2_3               # on-line sync command via STH/sync 
            ParseData_1_2_1         # parse raw data into torque
                Denoise_1_1_1       # denoise raw signal
                STHSense_2_0_1      # parse analog dataprocess into digital
                InitCollection_1_0  # initial conditions          
            UpdateSTHParm_1_0
        UpdateSTHParm_1_0       # adopt the updated parameters   

  ---- data process  
    DataProcess_10_5_1.py         # read the raw txt and parse it to csv
        STHSense_2_0_1            # parse analog dataprocess into digital
        Denoise_1_1_1             # denoise raw signal
        UpdateSTHParm_1_0
        STHSync_4_2_3               # on-line sync command via STH/sync 
            ParseData_1_2_1         # parse raw data into torque
                Denoise_1_1_1       # denoise of raw signal
                STHSense_2_0_1      # parse analog dataprocess into digital
                InitCollection_1_0  # initial conditions          
            UpdateSTHParm_1_0 
        CalToolPolar_0_1            # derive the tool polar
        GetCalbraCoef_0_2           # find the calbriation coeff.
            HeaderSplit_1_1         # splite headers
            ParsePlan_1_0           # parse exp. plan   

  ---- network and resource check
    STHScan_7_0_2.py             # scan all available STHs
        SystemCheck_3_0          # check necessary router, ip, port, and web 
        UpdateSTHParm_1_0
        STHSync_4_2_3               # on-line sync command via STH/sync 
            ParseData_1_2_1         # parse raw data into torque
                Denoise_1_1_1       # denoise of raw signal
                STHSense_2_0_1      # parse analog dataprocess into digital
                InitCollection_1_0  # initial conditions          
            UpdateSTHParm_1_0 
    
  ----  node-red operation
    loadInitSTH.py             # load initSTH.py into Node-red
      
  ----  on-line control 
    RemoteControl_2.py         # send STH/sync command to activate collecting STH data  
    
********************************************************************************************


********************************************************************************************
VTR: virtual tool room
STH: smart tool holder

********************************************************************************************
Root Folder 
	c:\VTR

********************************************************************************************

Application Files in c:\VTR
	InitSTH.py:       initial values of parameters for the executable files DataProcess and STHLink.
        iniySTH_u.json    updated parameters of InitSTH.py by UI

        STHScan.exe:      scan/setup the network of STHs

	STHLink.exe:         link and communicate with a STH
           STHComm.exe:      main program for communicating with a STH
   	   DataProcess.exe:  process sensing raw data (located at ‘.\RawData\Source\Data’) in txt to force data (located at ‘.\RawData\Output’) in CSV

********************************************************************************************
SubFolders of c:\VTR
    .\Libray:         library used for the specific functions
	.\Logs:           Errro logging files generated from Node-red and STHLink  
	.\Node-red:       User flow and system configuration files
	.\Plans:          The production or experimental plans in YAML/JSON, used in Node-red 
	.\RawData:        The collected raw data by STHLink and can be processed by Data.Process.exe
	.\Reports:        Data reports related to a yaml plan used in Node-red 
	.\Simuation:      Simulation CSV file related to a yaml plan by HiNC
----------------------------------
File in Library Folder
        MergeFile.exe:    execution function for merging files in a folder            

----------------------------------
Files in Logs
	STHerror.txt:     Error logs recored from STHLink
	msg_log (MM-dd mm-ss):   MQTT message collected by Node-red

----------------------------------
Files in NodeRed Folder
	setting.js:       Setup file for Node-red
	VTR-flows (yyyyMMv):     flow nodes for Node-red
        .\YYYYMMv:        individual flows of node-red
        .\Medium:         image files for node-red

----------------------------------
Files in Plans Folder
	LL-FR-A-MC-ID-IP-YYMMDD-setup-.yml:    production plan in yaml
	LL-FR-A-MC-ID-IP-YYMMDD-setup-.json:   production plan in json

----------------------------------
Files in RawData Folder
	.\Source:       Source folder for storing raw data (.txt) collected from STHLink
	   .\Data
              .\(YYYY-MM-DD-hh-mm)
                  *.txt  : raw txt files 

	.\Output:                       Output folder for storing parsed data (.csv) processed from Source/Data
              .\(YYYYMMDDhh):           recording time in folder 
                  *.csv:                parsed csv files 
              (YYYYMMDDhh)merged.csv:   merged csv file by folder  
    .\Coefficient
        AvailableSTH.csv
----------------------------------
Files in Report Folder

----------------------------------
Files in Simulation Folder
        .\NCfile
	       sim_part_YYYMMddV.csv:    Simulation data 

********************************************************************************************
Setup of Node-red
In setting.js
        flowFile: 'vtr_flows(YYYYMMDDV).json',
        functionGlobalContext: {
                fs: require('fs'),
                csv: require('csv-parser'),
                path: require('path'),
                async: require('async'),
                yaml: require('js-yaml'),
                os:require('os')
        },

********************************************************************************************
Usage of a STH

Step 1. New a browser with http:/127.0.0.1:1880 

Step 2. In setup tab of VTR of node-red UI, 
          First, click 'BIND' to bind a STH with a tool
          Then, click 'GENERATE/NEW PLAN' to produce a production plan.
          
          *** please notice that "HolderID": mac and "ToolID": tool-id in the group of plan updates.
             e.g. In the "Plan Updates" group,
             	it shows "ToolRelated": { "Binding": { "No1": { "HolderID": "7cdfa139d4d6", "PortNum": 6500, "ToolID": "T1", "State": false }..., 

Step 3. In network tab,
          First, click 'RESET DEFAULT'to check the default values of parameters.
          Then, if needs, click 'Auto-Assign New port' and 'Different Port' to set new port of target STH. 
          Alos, click 'APPLY UPDATE' to make sure the parameter values.
          Finally, click to 'SCAN/ASSIGN STH' to check the list of available STHs.
          
          *** please notice that each STH should be assigned a individual port.
              e.g. In the "Available STHs" group, 
		it shows "STH1-MAC: 7cdfa139d4d6, Port: 6503, STH2-MAC: 7cdfa1036646, Port: 6502"

Step 4: In startup tab, 
          First, click 'CHECK ACTIVE STH' to find an active STH, 
          Then, click 'APPLY UPDATES' to update the parameters of JSON file.
          Finally, click 'START STH LINK' to load 'dataprocess.exe' and 'STHComm.exe'.

         *** please notice that the active STH should be binded with a tool in the production plan.
             e.g. In the "Parameter Updates" group, 
		it shows "target_STH_mac": "7cdfa139d4d6", "target_STH_port": 6503, "target_tool_id": "T1"

Step 5: In monitor tab,
          First, click 'Record' to start collect STH data
          Then, click 'No Record' to stop collect STH data

         *** please notice that the target onitor. 
             e.g. In the "Online Overview" group, 
		it shows "STH ID: 7cdfa139d4d6".

Step 6. In Review tab,
          First, click 'MERGE FILES' and select a folder to merge all files in the selected folder.
          Finally, click 'SCAN FILES' and 'Select file' to select what file to review
