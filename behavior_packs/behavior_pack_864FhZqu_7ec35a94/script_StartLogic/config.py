# -*- coding: utf-8 -*-
import editorConfig
# Mod Version
ModName = "StartLogicMod"
ModVersion = "0.0.1"

# Server System
ServerSystemName = "StartLogicServerSystem"
ServerSystemClsPath = "startLogicServerSystem.StartLogicServerSystem"
TeamServerSystemName = "TeamServerSystem"
EndLogicServerSystemName = "EndLogicServerSystem"

# Client System
ClientSystemName = "StartLogicClientSystem"
ClientSystemClsPath = "startLogicClientSystem.StartLogicClientSystem"

# UI
StartLogicUIName = "startLogicUI"
StartLogicUIPyClsPath = "startLogicUI.StartLogicUIScreen"
StartLogicUIScreenDef = "startLogicUI.main"

# Engine
Minecraft = "Minecraft"

# Server Component
# Engine
PosComponent = "pos"
CommandComponent = "command"

# Client Component
# Engine

# Custom
# Server Event
# Engine
ScriptTickServerEvent = "OnScriptTickServer"
AddServerPlayerEvent = "AddServerPlayerEvent"
DelServerPlayerEvent = "DelServerPlayerEvent"
# Custom
UpdateUIEvent = "UpdateUIEvent"
StartLogicEvent = "StartLogicEvent"
# Client Event
# Engine
ScriptTickClientEvent = "OnScriptTickClient"
UiInitFinishedEvent = "UiInitFinished"
# Custom
EnsureJoinGameEvent = "EnsureJoinGameEvent"
TeamModName = "TeamMod"
EndLogicModName = "EndLogicMod"

# 玩家等待坐标
startGameWaitPos = [50, 64, 50]
# 最低开局玩家人数
gameMinPlayerNum = 1
# 是否自动开始游戏标志
autoStartFlag = True
# 倒计时长度
countDownTime = 5
# 是否清除掉落物标志
clearDropsFlag = True

# editor config begin
compPath = 'aa'
countDownTime = 5
clearDropsFlag = True
autoStartFlag = True
waitArea = {"startPoint": (1, 64, 1), "endPoint": (10, 64, 10)}
gameMinPlayerNum = 2
posOption = 1
randomPointList = [{"pos": (0.0, 0.0, 0.0)}, {"pos": (0.0, 0.0, 0.0)}, {"pos": (0.0, 0.0, 0.0)}]
teamPosList = [{"teamName": "队伍2", "pos": (0.0, 0.0, 0.0)}, {"teamName": "队伍1", "pos": (0.0, 0.0, 0.0)}, {"teamName": "队伍3", "pos": (0.0, 0.0, 0.0)}]
# editor config end
for _, data in editorConfig.dataDict.items():
	for key, value in data.items():
		locals()[key] = value

# 单人测试：最低开局人数改为1（编辑器组件里仍为2，以这里的手写覆盖为准）
gameMinPlayerNum = 1
# 最高开局玩家人数：乱斗每人一色棋石（黑/白/蓝/绿，见script_Gomoku的
# FFAMaxPlayers与StoneNormalNameByValue），颜色只有4种，超过4人不让开局
# （等待阶段/确认/倒计时中人数回落到上限内才继续，见CheckState）
gameMaxPlayerNum = 4


startPoint = waitArea['startPoint']
endPoint = waitArea['endPoint']
teamPosDict = {}
for i in range(len(randomPointList)):
	randomPointList[i] = randomPointList[i]['pos']
for i in teamPosList:
	teamPosDict[i['teamName']] = i['pos']
