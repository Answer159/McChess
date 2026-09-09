# _*_ coding:utf-8 _*_
# 这个文件保存了MOD中使用的一些变量，这样做的好处很多，建议参考
import mod.server.extraServerApi as serverApi
from .. import editorConfig

# Mod Version
ModName = "TeamMod"
StartLogicModName = "StartLogicMod"
ModVersion = "0.0.1"

# Modeule Path


# Server System
ServerSystemName = "TeamServerSystem"
ServerSystemClsPath = "modServer.serverSystem.teamServerSystem.TeamServerSystem"
StartLogicServerSystemName = "StartLogicServerSystem"

# Client System
ClientSystemName = "TeamClientSystem"
ClientSystemClsPath = "modClient.clientSystem.teamClientSystem.TeamClientSystem"

# Engine
Minecraft = "Minecraft"

# Server Event
# Engine
ServerChatEvent = "ServerChatEvent"
ScriptTickServerEvent = "OnScriptTickServer"
AddServerPlayerEvent = "AddServerPlayerEvent"
PlayerAttackEntityEvent = "PlayerAttackEntityEvent"
PlayerDieEvent = "PlayerDieEvent"
MobDieEvent = "MobDieEvent"
DelServerPlayerEvent = "DelServerPlayerEvent"
# Custom
UpdateScoreboardEvent = "UpdateScoreboardEvent"
ShowTeamUIEvent = "ShowTeamUIEvent"
StartLogicEvent = "StartLogicEvent"
InitSkillUIEvent = "InitSkillUI"
# Engine
ScriptTickClientEvent = "OnScriptTickClient"
UiInitFinishedEvent = "UiInitFinished"
# Custom

# Server Component
# Engine
PosComponent = "pos"
EngineTypeComponent = "engineType"
# Client Component
# Engine

# Type


# UI
TeamUIName = "teamUI"
TeamUIPyClsPath = "modClient.ui.teamUI.TeamUIScreen"
TeamUIScreenDef = "teamUI.main"

# 可配置的参数
# 队伍分配方式(组件编辑器所选择的队伍分配方式)
allocationMethod = 'MinmunAllocation'
# 是否可伤害队友
canHurtTeammate = True  # canHurtTeammate

for v in editorConfig.childDataDict['TeamCommon'].values():
	allocationMethod = v['allocationMethod']
	canHurtTeammate = v['canHurtTeammate']

# 队伍名称映射（限于UI显示，最多5队）
queueNameDict = []  # teamName
# 队伍文字颜色设置
queueColorDict = [(1, 0, 0, 1), (0, 1, 0, 1), (0, 0, 1, 1), (1, 1, 0, 1), (1, 0, 1, 1)]
# 队伍数量（限于UI显示，最多5队）
queueNum = len(editorConfig.dataDict.values())
# 每队人数上限
queueTopNumList = []  # teamMaxNum

# 积分获得方式选项
queueKillScore = []  # wayGetPointKillMonster
for v in editorConfig.dataDict.values():
	queueNameDict.append(v['teamName'])
	queueTopNumList.append(v['maxNum'])
	killMonsterScore = {}
	for i in v['wayGetPoint']:
		killMonsterScore[i['prefabID']] = i['getPoint']
	queueKillScore.append(killMonsterScore)
