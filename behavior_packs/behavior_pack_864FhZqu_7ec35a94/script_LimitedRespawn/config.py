# -*- coding: utf-8 -*-
import editorConfig
from mod.server.extraServerApi import GetEngineNamespace, GetEngineSystemName
from mod.server.serverEvent import ServerEvent

# Mod Version
ModName = "LimitedRespawnMod"
ModVersion = "0.0.1"

# Server System
ServerSystemName = "LimitedRespawnServerSystem"
ServerSystemClsPath = "serverSystem.LimitedRespawnServerSystem"

# Client System
ClientSystemName = "LimitedRespawnClientSystem"
ClientSystemClsPath = "clientSystem.LimitedRespawnClientSystem"

# Event
UpdateUIEvent = "UpdateUIEvent"
AddServerPlayerEvent = ServerEvent.AddServerPlayerEvent

# Engine
Minecraft = "Minecraft"

# UI
UIName = "limitedRespawnUI"
UIPyClsPath = "ui.LimitedRespawnUIScreen"
UIScreenDef = "limitedRespawnUI.main"

# 配置内容
ResetTimingOption = {
	0: {
		'namespace': 'StartLogicMod',
		"system": 'StartLogicServerSystem',
		"event": "StartLogicEvent"
	},
	1: {
		'namespace': GetEngineNamespace(),
		"system": GetEngineSystemName(),
		"event": AddServerPlayerEvent
	}
}
RespawnPointOption = {
	0: {
		'showText': '默认复活点',
		'value': (32, 88, 22)
	},
	1: {
		'showText': '随机复活点',
		'value': [(32, 88, 22), (33, 88, 32)],
	},
	2: {
		'showText': '安全区随机点',
		'namespace': 'SafeAreaMod',
		'system': "SafeAreaServerSystem",
		'method': 'GetRandomPoint'
	},
	3: {
		'showText': '队伍复活点',
	},
}
# editor config begin
defaultRespawnPoint = (4.0, 72.0, 20.0)
respawnPointSelection = 1
respawnTime = 5
resetTimingSelection = 0
respawnPoint = (4.0, 172.0, 20.0)
compPath = 'a'
randomPointList = [{"pos": (0.0, 0.0, 0.0)}, {"pos": (0.0, 0.0, 0.0)}, {"pos": (0.0, 0.0, 0.0)}]
teamPosList = [{"teamName": "队伍2", "pos": (0.0, 0.0, 0.0)}, {"teamName": "队伍1", "pos": (0.0, 0.0, 0.0)}, {"teamName": "队伍3", "pos": (0.0, 0.0, 0.0)}]
# editor config end
for _, data in editorConfig.dataDict.items():
	for key, value in data.items():
		locals()[key] = value
RespawnTime = respawnTime  # 复活次数
DefaultRespawnPoint = defaultRespawnPoint  # 没有复活次数时的复活点
RespawnPointOption[0]['value'] = tuple(respawnPoint)

RespawnPointSelection = respawnPointSelection
ResetTimingSelection = 0  # 恒为0

for i in range(len(randomPointList)):
	randomPointList[i] = randomPointList[i]['pos']
teamPosDict = {}
for i in teamPosList:
	teamPosDict[i['teamName']] = i['pos']
RespawnPointOption[1]['value'] = randomPointList
