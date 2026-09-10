# -*- coding: utf-8 -*-
# Mod Version
ModName = "GomokuMod"
ModVersion = "0.2.0"

# 脚本文件夹名（用于构建RegisterSystem的类路径）
ScriptFolderName = "script_Gomoku"

# Server System
ServerSystemName = "GomokuServerSystem"
ServerSystemClsPath = "gomokuServerSystem.GomokuServerSystem"

# Engine
Minecraft = "Minecraft"
CommandComponent = "command"
ItemComponent = "item"
PosComponent = "pos"
EngineTypeComponent = "engineType"

# Server Event
#  Engine
AddServerPlayerEvent = "AddServerPlayerEvent"
ServerBlockUseEvent = "ServerBlockUseEvent"
PlayerAttackEntityEvent = "PlayerAttackEntityEvent"
ScriptTickServerEvent = "OnScriptTickServer"
#  Custom（服务端广播给所有客户端，供后续五子棋UI监听）
GomokuGameResultEvent = "GomokuGameResultEvent"

# 跨Mod事件/系统
StartLogicModName = "StartLogicMod"
StartLogicServerSystemName = "StartLogicServerSystem"
StartLogicEvent = "StartLogicEvent"
EndLogicModName = "EndLogicMod"
EndLogicServerSystemName = "EndLogicServerSystem"
TeamModName = "TeamMod"
TeamServerSystemName = "TeamServerSystem"

# ---------------- 棋盘 ----------------
# 棋盘中心坐标（★需要在MCStudio编辑器里确认实际坐标后修改★）
# 当前占位值取自StartLogic队伍出生点(1854,64,587)/(1855,64,541)的中点附近
BoardCenter = (1854, 64, 564)
# 棋盘边长（格数），实际铺设为 BoardSize x BoardSize 的基座方阵
BoardSize = 9

# 资源地表扫描范围（从ScanMaxY自上而下找第一个非空气方块，矿石放其上方）
ScanMaxY = 90
ScanMinY = 50
# 扫描API不可用时的兜底高度（棋盘Y + 该偏移）
FallbackSpawnYOffset = 1

# ---------------- 自定义方块 ----------------
ChessBaseBlockName = "wihzo:McChess_ChessBase"
# 已落子的棋石（颜色由落子方队伍决定，徒手不可破坏）
StoneBlackName = "wihzo:gomoku_stone_black"
StoneWhiteName = "wihzo:gomoku_stone_white"
StoneGoldName = "wihzo:gomoku_stone_gold"

# ---------------- 自定义物品 ----------------
PickaxeStoneName = "wihzo:gomoku_pickaxe_stone"
PickaxeIronName = "wihzo:gomoku_pickaxe_iron"
ExecutionSwordName = "wihzo:execution_sword"
PieceItemPrefix = "wihzo:gomoku_piece_"
PieceItemNormal = "wihzo:gomoku_piece_normal"
PieceItemHardened = "wihzo:gomoku_piece_hardened"
PieceItemGold = "wihzo:gomoku_piece_gold"

# 镐 -> 可采集的矿（各挖各的）
PickaxeOreDict = {
	PickaxeStoneName: "wihzo:gomoku_ore_normal",
	PickaxeIronName: "wihzo:gomoku_ore_hardened",
}
# 矿 -> 采到的棋子物品
OrePieceItemDict = {
	"wihzo:gomoku_ore_normal": PieceItemNormal,
	"wihzo:gomoku_ore_hardened": PieceItemHardened,
	"wihzo:gomoku_ore_gold": PieceItemGold,
}

# 队伍名 -> 阵营（★需与Team组件编辑器里配置的队伍名一致★）
TeamSideDict = {
	"森林之子": "white",
	"火焰使者": "black",
}
SideNameDict = {"white": "白方", "black": "黑方", "gold": "金棋子"}

# ---------------- 资源刷新（以棋盘中心为基准的环形区域） ----------------
# type:     'ore' 在地表放矿石方块 / 'item' 在地表掉落物品
# radius:   (内半径, 外半径)，单位格
# angleRange: 环上角度范围（度，0=北/顺时针），用于把区域切成两半做黑白半区
# interval: 刷新间隔（秒）
SpawnConfigList = [
	# 普通棋子矿：近环，黑白两个半区各一片
	{"type": "ore", "blockName": "wihzo:gomoku_ore_normal", "radius": (8, 14), "angleRange": (0, 180), "interval": 4},
	{"type": "ore", "blockName": "wihzo:gomoku_ore_normal", "radius": (8, 14), "angleRange": (180, 360), "interval": 4},
	# 硬化棋子矿：中环
	{"type": "ore", "blockName": "wihzo:gomoku_ore_hardened", "radius": (14, 22), "angleRange": (0, 360), "interval": 15},
	# 金棋子矿：外环守卫区，极低频率
	{"type": "ore", "blockName": "wihzo:gomoku_ore_gold", "radius": (25, 35), "angleRange": (0, 360), "interval": 60},
	# 石镐：近环
	{"type": "item", "itemName": PickaxeStoneName, "radius": (8, 14), "angleRange": (0, 360), "interval": 20},
	# 铁镐：中环
	{"type": "item", "itemName": PickaxeIronName, "radius": (14, 22), "angleRange": (0, 360), "interval": 30},
	# 处决剑：中环
	{"type": "item", "itemName": ExecutionSwordName, "radius": (14, 22), "angleRange": (0, 360), "interval": 40},
]

# 胜利条件：连珠数
WinRowLength = 5
