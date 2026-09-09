# -*- coding: utf-8 -*-
import editorConfig
# Mod Version
ModName = "EndLogicMod"
ModVersion = "0.0.1"

# Server System
ServerSystemName = "EndLogicServerSystem"
ServerSystemClsPath = "endLogicServerSystem.EndLogicServerSystem"
StartLogicServerSystemName = "StartLogicServerSystem"
TeamServerSystemName = "TeamServerSystem"

# Client System
ClientSystemName = "EndLogicClientSystem"
ClientSystemClsPath = "endLogicClientSystem.EndLogicClientSystem"

# UI
EndLogicUIName = "endLogicUI"
EndLogicUIPyClsPath = "endLogicUI.EndLogicUIScreen"
EndLogicUIScreenDef = "endLogicUI.main"

# Engine
Minecraft = "Minecraft"

# Server Component
#  Engine
NameComponent = "name"
PosComponent = "pos"
EngineTypeComponent = "engineType"

# Server Event
#  Engine
ServerChatEvent = "ServerChatEvent"
ScriptTickServerEvent = "OnScriptTickServer"
AddServerPlayerEvent = "AddServerPlayerEvent"
PlayerDieEvent = "PlayerDieEvent"
MobDieEvent = "MobDieEvent"
EntityRemoveEvent = "EntityRemoveEvent"
DelServerPlayerEvent = "DelServerPlayerEvent"
PlayerAttackEntityEvent = "PlayerAttackEntityEvent"
#  Custom
NotifyVictoryEvent = "NotifyVictoryEvent"
# Client Event
#  Engine
UiInitFinishedEvent = "UiInitFinished"
ScriptTickClientEvent = "OnScriptTickClient"
#  Custom

TeamModName = 'TeamMod'
StartLogicModName = 'StartLogicMod'

# 配置项说明
# 结束判断条件列表
endConditionTypeList = ["player", "team"]
endJudgeConditionList = ["clockEndCondition", "reachVictoryCondition"]

# 胜利判断条件列表
victoryJudgeConditionList = {
	("team", "clockEndCondition"): ["queueScoreMax"],
	("player", "clockEndCondition"): ["deathNumMin", "killNumMax"],
	("team", "reachVictoryCondition"): ["onlyOneQueue"],
	("player", "reachVictoryCondition"): ["onlyOnePlayer"],
	("player", "capitalCondition"): ["capitalCondition"]
}

# 可配置参数
victoryJudgeConditionKey = ["player", "clockEndCondition"]
victoryJudgeConditionValue = "deathNumMin"
clockEndTime = 10
showEndNotifyUIFlag = True
restartGameTime = 5
restartGameFlag = False
clearInvFlag = False
endWaitPos = [0, 0, 0]
finalBossName = ""
finalBossType = ""
finalBossCount = ""
endConditionType = 'player'
endJudgeCondition = "clockEndCondition"
victoryJudgeCondition = "deathNumMin"
# editor config begin

for _, data in editorConfig.dataDict.items():
	for k, v in data.items():
		locals()[k] = v

# editor config end

# 根据编辑器保存的参数更新可配置参数
victoryJudgeConditionKey = [endConditionType, endJudgeCondition]
victoryJudgeConditionValue = victoryJudgeCondition
