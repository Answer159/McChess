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
# 定时结算时长（单位秒，代码按 *30帧=1秒 换算）：到点一律平局结算。
# 本图结算只有两种：超时平局 / 五子棋连珠获胜（见endLogicServerSystem.ExternalSettleGame）
clockEndTime = 600
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

# ---------------------- 系列赛（整场多局，如五局三胜） ----------------------
# 注意：以下key均为手写层新增，editorConfig.dataDict不提供，不会被编辑器覆盖；
# 另外勿走editorConfig——现有restartGameTime(读)/reStartGameTime(写)拼写不一致的坑说明手写层才可靠。
# 夺冠所需胜场数（某队胜场达到此值即夺得整场总冠军；五局三胜=3）
matchWinLimit = 3
# 系列赛比分广播事件（服务端->本mod客户端，驱动场地记分牌）
UpdateSeriesScoreEvent = "UpdateSeriesScoreEvent"
# 记分牌标题文案格式（{0}=matchWinLimit）
SeriesScoreTitleFormat = "先取{0}胜"
# 记分牌初始文案（服务端首次广播前显示）
SeriesBoardInitText = "等待系列赛开始"
# 记分牌世界坐标（参照编辑器里原TextBoard预设的摆放位置）与缩放
scoreboardPos = (1853.38, 63.91, 549.95)
scoreboardScale = (2.0, 2.0)
# 记分牌文字颜色（RGBA 0-1）
SeriesBoardTextColor = (1.0, 1.0, 1.0, 1.0)
