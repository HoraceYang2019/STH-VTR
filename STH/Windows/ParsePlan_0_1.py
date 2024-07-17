
import json
import pandas as pd
#%%
version: str = 'ParsePlan v1.0.0'

#%%
def GetToolRelated(initSTH_u: str = 'c:/vtr/initSTH_u.json'):
    # get plan name from the updated STH JSON file
    with open(initSTH_u) as initSTH_file:
        plan_name = json.load(initSTH_file)

    # get the holder, binding, and toolhouse data from current plan file
    with open(plan_name['current_plan']+'.json', encoding =  'utf-8') as json_file:
        plan_data = json.load(json_file)

    return plan_data['ToolRelated']['ToolHolder'], plan_data['ToolRelated']['Binding'], plan_data['ToolRelated']['ToolHouse']

#%% get STH IDs
def GetSTHID(holder):
    sth_id = []
    for i in holder.keys():
        if holder[i]['HolderID'] == '': break
        sth_id.append(holder[i]['HolderID'])  
    
    return sth_id 

#%% get tool apt by sth id
def FindToolApt(STH_id, binding, tool_house):
    STH_Tool = []
    full_height = flute_height = 0.0001
    msg = f'No avaliable Tool Apt based on the HolderID {STH_id}'
    for i in binding.keys():
        if binding[i]['HolderID'] in STH_id:
            tool_id = binding[i]['ToolID']
            port = binding[i]['PortNum']
            for j in tool_house.keys():
                if tool_id == tool_house[j]['ID']:
                    full_height = (tool_house[j]['Apt']['FullHeight'])
                    flute_height = (tool_house[j]['Apt']['FluteHeight'])
                    msg = f'Tool Apt is found based on the HolderID {STH_id}'
                    break
            STH_Tool.append([binding[i]['HolderID'], port, tool_id, full_height, flute_height])
    print('[TRAC]  <ParsePlan>: '+ msg)
    return STH_Tool 

#%% get tool apt by current plan and binding
def GetAllSTHApt():
    tool_holder, binding, tool_house = GetToolRelated() 
    sth_id = GetSTHID(tool_holder)
    col_names = ['STH id', 'tool id', 'full height', 'flute height']
    sth_tools = []
    for sid in sth_id:
        tid, full_height, flute_height = FindToolApt(sid, binding, tool_house)
        sth_tools.append([sid, tid, full_height, flute_height])

    return pd.DataFrame(sth_tools, columns = col_names)

def GetSTHApt(sth_id):
    _, binding, tool_house = GetToolRelated() 
    return FindToolApt(sth_id, binding, tool_house) 

#%%
if __name__ == "__main__":
    sth_tools_par = GetSTHApt(sth_id = ['7cdfa139d4d6','7cdfa1036646'])
    print(sth_tools_par[0])