# -*- coding: utf-8 -*-
# =====================================================================
# GomokuMod 总配置 —— 所有可调整参数都在这个文件，服务端逻辑零硬编码数值。
# 分两大区：上区是ModSDK系统注册（勿动），下区是玩法参数（随意调）。
# 改完在MCStudio里重进地图生效；标★的参数有联动事项，见行尾注释。
# =====================================================================

# ---------------------- 系统注册区（勿动） ----------------------
ModName = "GomokuMod"
ModVersion = "0.2.0"
# 脚本文件夹名（用于构建RegisterSystem的类路径）
ScriptFolderName = "script_Gomoku"

# Server System
ServerSystemName = "GomokuServerSystem"
ServerSystemClsPath = "gomokuServerSystem.GomokuServerSystem"

# Engine（引擎组件名）
Minecraft = "Minecraft"
CommandComponent = "command"
ItemComponent = "item"
PosComponent = "pos"
EngineTypeComponent = "engineType"

# Server Event
#  Engine
AddServerPlayerEvent = "AddServerPlayerEvent"
ServerBlockUseEvent = "ServerBlockUseEvent"
ServerItemUseOnEvent = "ServerItemUseOnEvent"
ServerPlayerTryDestroyBlockEvent = "ServerPlayerTryDestroyBlockEvent"
PlayerAttackEntityEvent = "PlayerAttackEntityEvent"
# 掉落物实体移除事件（被捡起/超时消失/回合清理）——用于物品存量计数剔除
EntityRemoveEvent = "EntityRemoveEvent"
ScriptTickServerEvent = "OnScriptTickServer"
#  Custom（服务端广播给所有客户端，供后续五子棋UI监听）
GomokuGameResultEvent = "GomokuGameResultEvent"

# 跨Mod事件/系统名（★改=对应Mod的config同步改，且事件名是字符串字面量广播，需全局搜）
StartLogicModName = "StartLogicMod"
StartLogicServerSystemName = "StartLogicServerSystem"
StartLogicEvent = "StartLogicEvent"
EndLogicModName = "EndLogicMod"
EndLogicServerSystemName = "EndLogicServerSystem"
TeamModName = "TeamMod"
TeamServerSystemName = "TeamServerSystem"

# ---------------------- 棋盘 ----------------------
# 棋盘中心 = 编辑器里放置的Anchor方块预设的位置（启动时从地图 db/presets.json 读取）
AnchorPresetName = "Anchor"
# presets.json 读取失败时的兜底棋盘中心（★即当前Anchor所在坐标，编辑器里移动Anchor后同步更新）
FallbackBoardCenter = (1854, 62, 565)
# 棋盘边长（格数），实际铺设为 BoardSize x BoardSize 的基座方阵，基座层会覆盖掉Anchor方块
# ★须为奇数（棋盘才有正中心）；改动后资源环最小内半径须 > BoardSize/2，否则物品会掉在棋盘上
BoardSize = 9
# 玩家进服后延迟多少秒尝试铺盘（避初始化竞态；0=立即）
BoardBuildDelaySeconds = 1

# ---------------------- 资源刷新：高度与维度 ----------------------
# 矿石贴地表放置（GetTopBlockHeight随地形）；
# 物品生成在地表上方ItemSpawnHeightOffset格，靠掉落物自身重力落地。
# 地表查询API异常时的兜底平面 = 棋盘基座层Y + ResourceSpawnYOffset
ResourceSpawnYOffset = 1
ItemSpawnHeightOffset = 3
# 主世界维度id（0=主世界）
MainDimensionId = 0
# 刷新条目没写count时，单次物品刷新的默认个数
DefaultSpawnCount = 1
# 刷新条目没写chance时，每次刷新时刻的默认刷出概率（1.0=必刷，0.3=每次只有三成概率真的刷出）
DefaultSpawnChance = 1.0

# ---------------------- 棋盘区域常驻加载（tickingarea） ----------------------
# 等待阶段玩家在1800格外，棋盘区块不会自然加载，/fill会失败，用tickingarea常驻加载。
# 半径单位为区块（1区块=16格），4区块=64格，需覆盖最外资源环(35格)。
# ★重名区域重复添加会失败（日志警告可忽略）；若加最外环半径，这里同步加大
TickingAreaName = "gomoku_board"
TickingAreaRadius = 4

# ---------------------- 自定义方块（名字须与netease_blocks/下JSON一致） ----------------------
# 棋盘基座
ChessBaseBlockName = "wihzo:McChess_ChessBase"
# 已落子的棋石（颜色=落子方队伍；普通/硬化外观相同、挖掘耗时不同，硬化版destroy_time更大；
# 挖掉即销毁无掉落，并释放引擎对应格子）
StoneBlackName = "wihzo:gomoku_stone_black"
StoneWhiteName = "wihzo:gomoku_stone_white"
StoneBlackHardenedName = "wihzo:gomoku_stone_black_hardened"
StoneWhiteHardenedName = "wihzo:gomoku_stone_white_hardened"
StoneGoldName = "wihzo:gomoku_stone_gold"
# 全部棋石方块集合（挖掘时按棋盘格处理）
StoneBlockNameSet = {
    StoneBlackName, StoneWhiteName, StoneGoldName,
    StoneBlackHardenedName, StoneWhiteHardenedName,
}

# ---------------------- 自定义物品（名字须与行为包netease_items_beh/、
# 资源包netease_items_res/下的JSON identifier一致） ----------------------
PickaxeStoneName = "wihzo:gomoku_pickaxe_stone"
PickaxeIronName = "wihzo:gomoku_pickaxe_iron"
ExecutionSwordName = "wihzo:execution_sword"
PieceItemNormal = "wihzo:gomoku_piece_normal"
PieceItemHardened = "wihzo:gomoku_piece_hardened"
PieceItemGold = "wihzo:gomoku_piece_gold"

# ---------------------- 道具表 ----------------------
# 所有道具的统一定义，后续开发新道具只加这里，系统按 type 分派行为：
#   name:       短显示名（播报用；物品JSON里的display_name是带说明的详细版）
#   type:       'piece' 棋子 / 'pickaxe' 采集镐 / 'weapon' 武器
#   consumable: 使用一次即销毁（耐久1）
#   piece 专用:  fromOre 产出该棋子的矿 / wildcard 万能挡子（金棋子，落子不分颜色、只挡线不获胜）
#   pickaxe专用: mineOre 能采集的矿（各挖各的）
#   weapon 专用: damage 攻击玩家造成的伤害（缺省用DefaultWeaponDamage）
ItemTable = {
	PieceItemNormal: {
		"name": "普通棋子", "type": "piece",
		"fromOre": "wihzo:gomoku_ore_normal",
	},
	PieceItemHardened: {
		"name": "硬化棋子", "type": "piece",
		"hardened": True,  # 落子后用硬化棋石（外观同色，挖掘耗时更长）
		"fromOre": "wihzo:gomoku_ore_hardened",
	},
	PieceItemGold: {
		"name": "金棋子", "type": "piece", "wildcard": True,
		"fromOre": "wihzo:gomoku_ore_gold",
	},
	PickaxeStoneName: {
		"name": "石镐", "type": "pickaxe", "consumable": True,
		"mineOre": "wihzo:gomoku_ore_normal",
	},
	PickaxeIronName: {
		"name": "铁镐", "type": "pickaxe", "consumable": True,
		"mineOre": "wihzo:gomoku_ore_hardened",
	},
	ExecutionSwordName: {
		"name": "处决剑", "type": "weapon", "consumable": True,
		"damage": 9999,
	},
}

# 武器没写damage时的兜底伤害
DefaultWeaponDamage = 9999

# 派生表（由道具表自动生成，勿手改）
# 镐 -> 可采集的矿
PickaxeOreDict = {item: cfg["mineOre"] for item, cfg in ItemTable.iteritems() if cfg["type"] == "pickaxe"}
# 矿 -> 采到的棋子物品
OrePieceItemDict = {cfg["fromOre"]: item for item, cfg in ItemTable.iteritems() if "fromOre" in cfg}

# ---------------------- 队伍阵营映射 ----------------------
# 队伍名 -> 阵营（★须与Team组件编辑器里配置的队伍名一致，改队伍名=这里同步改）
TeamSideDict = {
	"森林之子": "white",
	"火焰使者": "black",
}
# 阵营 -> 播报显示名
SideNameDict = {"white": "白方", "black": "黑方", "gold": "金棋子"}

# 单人调试开关：True时单人落子黑白交替（无视队伍），用于单人验证双方颜色与胜负逻辑；
# 正式对战必须为False（按落子方队伍定色）。金棋子不受影响（本就不分队）
DebugSoloAlternateSides = False

# ---------------------- 资源总量维持 ----------------------
# 每种资源在地图上的存量上限：刷新时先数当前已有的数量——已有 >= 上限就跳过本次刷新，
# 总量维持恒定，玩家采走（存量下降）后才会补刷。
# 矿石计数：开局全环重扫一遍（兼容存档残留），此后每RecountIntervalSeconds秒重扫修正，
# 平时靠 刷出+1 / 挖碎-1 实时维护；物品计数：按刷出的掉落物实体跟踪（捡起/消失/回合清理即剔除）。
SpawnMaxCountDict = {
	# 普通矿：黑白两半区合计（每半区常驻约6个）
	"wihzo:gomoku_ore_normal": 12,
	# 硬化矿：中环合计
	"wihzo:gomoku_ore_hardened": 6,
	# 金矿：外环守卫区，极稀少
	"wihzo:gomoku_ore_gold": 2,
	# 直刷棋子物品
	PieceItemNormal: 5,
	PieceItemHardened: 3,
	# 道具（孤注一掷的投资，存量天然稀少）
	PickaxeStoneName: 2,
	PickaxeIronName: 2,
	ExecutionSwordName: 1,
}
# 矿石全环重扫间隔（秒）：重扫分帧进行，每帧查ScanColumnsPerTick列，避免单tick卡顿
RecountIntervalSeconds = 30
ScanColumnsPerTick = 25
# 掉落物自然消失时间（秒）：超龄的计数条目剔除，防实体移除事件丢失导致计数虚高
ItemDespawnSeconds = 300

# ---------------------- 资源刷新表（以棋盘中心为基准的环形区域，参数按策划案doc） ----------------------
# 每条一个刷新协程，开局(OnRoundStart)时启动。字段：
#   type:       'ore' 在地表放矿石方块 / 'item' 在地表上方掉落物品（自带重力、5分钟后自动消失）
#   blockName/itemName: 刷什么（方块名/物品名）
#   count:      （可选，仅item）单次刷新个数，缺省DefaultSpawnCount
#   chance:     （可选）每次刷新时刻的刷出概率0~1，缺省DefaultSpawnChance（必刷）
#   radius:     (内半径, 外半径)，单位格——生成范围；★内半径须 > BoardSize/2，否则会刷在棋盘上
#   angleRange: 环上角度范围（度，0=北/顺时针），生成范围的扇区部分，用于把区域切成两半做黑白半区，(0,360)=整环
#   interval:   刷新间隔（秒）——生成频率；间隔到点后按chance掷骰、按SpawnMaxCountDict查存量决定是否真刷
# 稀有感调节口诀：interval控制多久一次机会，chance控制机会兑现的概率，radius控制摊薄的范围，
# SpawnMaxCountDict控制存量天花板（维持总量）
SpawnConfigList = [
	# 普通棋子矿：近环，黑白两个半区各一片（策划案：每区约3~5s/个）
	{"type": "ore", "blockName": "wihzo:gomoku_ore_normal", "radius": (8, 14), "angleRange": (0, 180), "interval": 4},
	{"type": "ore", "blockName": "wihzo:gomoku_ore_normal", "radius": (8, 14), "angleRange": (180, 360), "interval": 4},
	# 硬化棋子矿：中环
	{"type": "ore", "blockName": "wihzo:gomoku_ore_hardened", "radius": (14, 22), "angleRange": (0, 360), "interval": 15},
	# 金棋子矿：外环守卫区（跑一趟=离开战场很久），徒手可挖
	{"type": "ore", "blockName": "wihzo:gomoku_ore_gold", "radius": (25, 35), "angleRange": (0, 360), "interval": 60},
	# 普通棋子物品：近环高频直刷
	{"type": "item", "itemName": PieceItemNormal, "radius": (5, 9), "angleRange": (0, 360), "interval": 3},
	# 硬化棋子物品：中环直接掉落
	{"type": "item", "itemName": PieceItemHardened, "radius": (9, 14), "angleRange": (0, 360), "interval": 15},
	# 石镐：近环
	{"type": "item", "itemName": PickaxeStoneName, "radius": (5, 9), "angleRange": (0, 360), "interval": 12},
	# 铁镐：中环
	{"type": "item", "itemName": PickaxeIronName, "radius": (9, 14), "angleRange": (0, 360), "interval": 25},
	# 处决剑：中环
	{"type": "item", "itemName": ExecutionSwordName, "radius": (11, 16), "angleRange": (0, 360), "interval": 35},
]

# ---------------------- 胜利条件 ----------------------
# 连珠数（几子连珠获胜）
WinRowLength = 5
