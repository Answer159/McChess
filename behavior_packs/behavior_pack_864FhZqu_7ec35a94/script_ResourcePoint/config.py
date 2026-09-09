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
