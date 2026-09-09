# -*- coding: utf-8 -*-
# 这个文件保存了MOD中使用的一些变量，这样做的好处很多，建议参考
from .. import editorConfig
# Mod Version
ModName = "SkillMod"
ModVersion = "0.0.1"
TeamModName = "TeamMod"
StartLogicModName = "StartLogicMod"
EndLogicModName = "EndLogicMod"

# Client System
ClientSystemName = "SkillClientSystem"
ClientSystemClsPath = "modClient.clientSystem.skillClientSystem.SkillClientSystem"

# Server System
ServerSystemName = "SkillServerSystem"
ServerSystemClsPath = "modServer.serverSystem.skillServerSystem.SkillServerSystem"
TeamServerSystemName = "TeamServerSystem"
StartLogicServerSystemName = "StartLogicServerSystem"
EndLogicServerSystemName = "EndLogicServerSystem"


# Engine
Minecraft = "Minecraft"

# Client Component
## Engine
ScriptTypeCompClient = "type"
PathComponent = "path"
FrameAniBindComponent = "frameAniEntityBind"
FrameAniCtrlComponent = "frameAniControl"
ParticleBindComponent = "particleEntityBind"
ParticleCtrlComponent = "particleControl"

# Server Component
## Engine
EngineTypeComponent = "engineType"
ScriptTypeCompServer = "type"
PosComponent = "pos"
RotComponent = "rot"

# UI
SkillUIName = "skillUI"
SkillUIPyClsPath = "modClient.ui.skillUI.SkillUIScreen"
SkillUIScreenDef = "skillUI.main"

# Server Event
## System
ScriptTickServerEvent = "OnScriptTickServer"
ProjectileDoHitEffectEvent = "ProjectileDoHitEffectEvent"
## custom
GetTeamNameEvent = "GetTeamName"
InitSkillUIEvent = "InitSkillUI"
SkillReleaseEvent = "SkillRelease"
ProjectileHitEvent = "ProjectileSkillHit"
ProjectileFlyFrameEvent = "ProjectileSkillFlyFrame"
HideSkillUIEvent = "HideSkillUI"
StartGameEvent = "StartLogicEvent"
EndGameEvent = "NotifyVictoryEvent"

# Client Component
ClientSkillComponent = "ClientSkill"
ClientSkillCompClsPath = "modClient.clientComponent.skillComponentClient.SkillComponentClient"

# Server Component
ServerSkillComponent = "ServerSkill"
ServerSkillCompClsPath = "modServer.serverComponent.skillComponentServer.SkillComponentServer"

# Skill Type
LaunchProjectileType = 0
AddBuffType = 1

# Buff Type 可查询Minecraft Wiki
SpeedBuff = "speed"
SlownessBuff = "slonwness"
HasteBuff = "haste"
StrengthBuff = "strength"
InstantHealthBuff = "instant_health"
JumpBoostBuff = "jump_boost"
NauseaBuff = "nausea"
RegenerationBuff = "regeneration"
ResistanceBuff = "resistance"
FireResistanceBuff = "fire_resistance"
WaterBreathingBuff = "water_breathing"
InvisibilityBuff = "invisibility"
BlindnessBuff = "blindness"
NightVisionBuff = "night_vision"
HungerBuff = "hunger"
WeaknessBuff = "weakness"
PoisonBuff = "poison"
WitherBuff = "wither"
LevitationBuff = "levitation"

# Effective Target
SelfTarget = 0
TeamTarget = 1
TeammateTarget = 2
NonTeammateTarget = 3
BlockTarget = 4
PlayerTarget = 5
NonPlayerEntityTarget = 6
AllTarget = 7

# Skill Number
FirstSkill = 0
SecondSkill = 1
ThirdSkill = 2

# Skill State
StateCD = 0
StateNotCD = 1

# 可配置的参数
# Skill key: uuid value: skillConfig
SkillConfigs = editorConfig.dataDict

# 技能CD提示持续时间
HintShowTime = 2
