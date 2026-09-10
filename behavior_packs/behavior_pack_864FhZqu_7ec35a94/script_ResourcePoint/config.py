# -*- coding: utf-8 -*-
import editorConfig
# Mod Version
ModName = "ResourcePointConfigMod"
ModVersion = "0.0.1"

# Server System
ServerSystemName = "ResourcePointServerSystem"
ServerSystemClsPath = "serverSystem.ResourcePointServerSystem"

# Client System
ClientSystemName = "ResourcePointClientSystem"
ClientSystemClsPath = "clientSystem.ResourcePointClientSystem"

Minecraft = "Minecraft"
ItemComponent = "item"
CommandComponent = "command"
ServerChatEvent = "ServerChatEvent"
ScriptTickServerEvent = "OnScriptTickServer"
AddServerPlayerEvent = "AddServerPlayerEvent"
ScriptTickClientEvent = "OnScriptTickClient"

resourceStartPointList = []
resourceEndPointList = []
# 资源名称列表
resourceList = []
# 资源生成数量
resourceCountList = []
# 资源生成速度（单位秒）
resourceIntervalList = []
for k, v in editorConfig.dataDict.items():
	resourceStartPointList.append(v['area']['min'])
	resourceEndPointList.append(v['area']['max'])
	resourceList.append(v['item'])
	resourceCountList.append(v['itemNumber'])
	resourceIntervalList.append(v['interval'])

# 五子棋玩法已用自身的资源环接管资源投放（script_Gomoku），
# 这里清空模板自带的刷新点（铁锭/钻石/木棍），使其不再掉落。
# 注：刷新点实例仍留在编辑器组件里，如需彻底清理请在MCStudio组件编辑器中删除。
resourceStartPointList = []
resourceEndPointList = []
resourceList = []
resourceCountList = []
resourceIntervalList = []
