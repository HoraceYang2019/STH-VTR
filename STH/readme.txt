# -*- coding: utf-8 -*-
#--------------------------------------------------------------------------------------------------------
Release time
  10/14, 2024
********************************************************************************************
Structure of Code Folder: 

STH-W3-J                       # major folder
    InitSTH.py                 # the inital parameters for STH associated files
    initSTH_u.json             # updated parameters of InitSTH.py by UI
    
  ---- communicate with STH   
    STHComm.py                  # communicate with STH 3
        HeaderSplit             # split message header from STH data  
        Printer                 # print header
        STHSync                 # on-line sync command via STH/sync 
            ParseData           # parse raw data into torque
                Denoise         # denoise raw signal
                STHSense        # parse analog dataprocess into digital
                InitCollection  # initial conditions          
            UpdateSTHParm
        UpdateSTHParm           # adopt the updated parameters   
        MonitorNetSocket        # monitor network performance
        MinitorSysUsage         # monitor CPU, memory, and disk usages

  ---- data process  
    DataProcess.py              # read the raw txt and parse it to csv
        STHSense                # parse analog dataprocess into digital
        Denoise                 # denoise raw signal
        UpdateSTHParm
        STHSync                 # on-line sync command via STH/sync 
            ParseData           # parse raw data into torque
                Denoise         # denoise of raw signal
                STHSense        # parse analog dataprocess into digital
                InitCollection  # initial conditions          
            UpdateSTHParm 
        CalToolPolar            # derive the tool polar
        GetCalbraCoef           # find the calbriation coeff.
            HeaderSplit         # splite headers
            ParsePlan           # parse exp. plan   

  ---- network and resource check
    STHScan.py                  # scan all available STHs
        SystemCheck             # check necessary router, ip, port, and web 
        UpdateSTHParm
        STHSync                 # on-line sync command via STH/sync 
            ParseData           # parse raw data into torque
                Denoise         # denoise of raw signal
                STHSense        # parse analog dataprocess into digital
                InitCollection  # initial conditions          
            UpdateSTHParm_1_0 
    
  ---- node-red operation
    loadInitSTH.py              # load initSTH.py into Node-red
      
  ---- job assoicated 
    runSTHJobs.py               # run jobs based on STH_Jobs.json
        STH_Jobs.json           # jobs for running
        coef.csv                # coefficients for the current STH calibration
        STHComm                 # communicate with STH 3
    
    STH_Jobs.json               # specify mac, port, and intervals by Tool

    DetectAbnormal.py           # detect abnormal based on Reference in window   

  ---- controller associated
  ---- monitor tools
    MonitorNetSocket.py         # monitor network performance
    MinitorSysUsage.py          # monitor CPU, memory, and disk usages    

  ---- compile to exe
    exeSpec.spec                # configuration for compiling *.py into .exe
    
    
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
