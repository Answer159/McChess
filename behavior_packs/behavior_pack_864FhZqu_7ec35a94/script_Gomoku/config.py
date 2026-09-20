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

# Client System（一个客户端系统三件事：比分文字板——TextBoard是纯客户端
# 组件服务端没这套API；说明书弹窗；混乱药水/时间停止的输入控制。见gomokuClientSystem）
ClientSystemName = "GomokuClientSystem"
ClientSystemClsPath = "gomokuClientSystem.GomokuClientSystem"

# Engine（引擎组件名）
Minecraft = "Minecraft"
CommandComponent = "command"
ItemComponent = "item"
EffectComponent = "effect"
PosComponent = "pos"
EngineTypeComponent = "engineType"
NameComponent = "name"

# Server Event
#  Engine
AddServerPlayerEvent = "AddServerPlayerEvent"
ServerBlockUseEvent = "ServerBlockUseEvent"
ServerItemUseOnEvent = "ServerItemUseOnEvent"
# 玩家点击右键尝试使用物品（不依赖方块目标——对空气右键也触发，物品名取
# itemDict['newItemName']，对照官方GodChef模板用法）。换位符走这里：
# 指着方块右键时ServerItemUseOnEvent先到，对空气右键只有本事件会触发
ServerItemTryUseEvent = "ServerItemTryUseEvent"
ServerPlayerTryDestroyBlockEvent = "ServerPlayerTryDestroyBlockEvent"
PlayerAttackEntityEvent = "PlayerAttackEntityEvent"
# 玩家即将捡起掉落物事件——棋子携带超上限时cancel拦截
# （EntityRemoveEvent已弃用：SpawnItemToLevel拿不到entityId，物品计数改为
#   自维护itemExpireDict模型，不再依赖掉落物实体移除事件）
ServerPlayerTryTouchEvent = "ServerPlayerTryTouchEvent"
ServerChatEvent = "ServerChatEvent"
ScriptTickServerEvent = "OnScriptTickServer"
ScriptTickClientEvent = "OnScriptTickClient"
# 键盘按下/弹起（客户端引擎事件；混乱药水用它维护真实WASD按键状态，
# 见gomokuClientSystem——GetInputVector锁定中只返回回声，真实输入只能从这拿）
OnKeyPressInGameEvent = "OnKeyPressInGame"
# 手柄摇杆事件（客户端引擎事件，x/y为-1~1；混乱药水用它适配手柄移动，见gomokuClientSystem）
GamepadStickClientEvent = "OnGamepadStickClientEvent"
# 屏幕点击松手（客户端引擎事件，仅移动端/F11触发；假摇杆用它判定拖动结束）
TapOrHoldReleaseClientEvent = "TapOrHoldReleaseClientEvent"
PlayerDieEvent = "PlayerDieEvent"
# 引擎重生流程走完（玩家已落地）：陷阱模式用这个时机把重生的人拉回棋盘边
# 安全圈——LimitedRespawn在同事件的回调里会把人传到队伍复活点（经典模式的
# 复活行为），跨mod监听顺序不保证谁先，模式那边延迟几帧再传稳定压过它
# （见trapMode.DelayTeleportAfterRespawn）
PlayerRespawnFinishServerEvent = "PlayerRespawnFinishServerEvent"
DelServerPlayerEvent = "DelServerPlayerEvent"
DamageEvent = "DamageEvent"
# 实体（含玩家）尝试放置方块：陷阱模式用它拦住"往陷阱格上放方块搭桥"
# （args['cancel']=True 即取消放置，见OnEntityTryPlaceBlock）
ServerEntityTryPlaceBlockEvent = "ServerEntityTryPlaceBlockEvent"
# Client Event
#  Engine（客户端就绪信号：比分文字板在此之后延迟创建，见gomokuClientSystem）
UiInitFinishedEvent = "UiInitFinished"

#  Custom（服务端广播给所有客户端，供后续五子棋UI监听）
GomokuGameResultEvent = "GomokuGameResultEvent"
# 比分刷新（服务端 -> 客户端）：data['rows'] = [[整行文字, RGBA四元组], ...]，
# 排版与颜色都在服务端算好（见BuildScoreBoardData），客户端只按行建板
GomokuScoreBoardEvent = "GomokuScoreBoardEvent"
# 索要当前比分（客户端 -> 服务端）：客户端把板建好后主动请求一次，
# 让晚进服/重连的玩家不用等到下一局结算才看到比分（见OnScoreBoardRequest）
GomokuScoreRequestEvent = "GomokuScoreRequestEvent"
# 请求打开说明书弹窗（服务端 -> 客户端）
ManualOpenEvent = "GomokuManualOpenEvent"
# 通知玩家被混乱（服务端 -> 客户端：客户端开启移动反向，见gomokuClientSystem）
ChaosConfuseEvent = "GomokuChaosConfuseEvent"
# 通知玩家被时间停止（服务端 -> 客户端：客户端关闭移动/跳跃/攻击输入，
# 见gomokuClientSystem）
TimestopFreezeEvent = "GomokuTimestopFreezeEvent"

# 跨Mod事件/系统名（★改=对应Mod的config同步改，且事件名是字符串字面量广播，需全局搜）
StartLogicModName = "StartLogicMod"
StartLogicServerSystemName = "StartLogicServerSystem"
StartLogicEvent = "StartLogicEvent"
EndLogicModName = "EndLogicMod"
EndLogicServerSystemName = "EndLogicServerSystem"
TeamModName = "TeamMod"
TeamServerSystemName = "TeamServerSystem"

# ---------------------- 玩法模式（模式工厂） ----------------------
# 本局用哪个玩法模式。模式之间零耦合：五子棋本体（棋盘/落子/判胜/道具）共用，
# 模式只负责"地形怎么铺、资源刷在哪、能不能放方块、死后在哪重生、每帧查什么"
# 这几个钩子（见gameModes/baseMode.py）。可选值来自gameModes/modeFactory.py的
# 注册表；各模式自己的参数在各自的配置文件里，与本文件互不干扰：
#   "random"  每局随机（默认）：每局开局从注册表独立抽一个模式并全服播报
#             本局是哪个（见SwitchGameModeForRound；两局连出同模式属正常随机）
#   "classic" 固定经典模式：地图原生地形，资源在环形区域随机刷（模式框架之前的行为）
#   "trap"    固定陷阱模式：只有通往道具生成点的路是安全的，踩到路外的格子
#             -> 变岩浆+掉血+弹回上一个安全格（参数见
#             gameModes/trapModeConfig.py：陷阱区半边长/安全圈/路径条数/岩浆时长…）
# ★固定模式改完重进地图生效；"random"的抽取每局开局重掷。写成没注册的名字
# 会记警告并退回"classic"
GameMode = "random"

# ---------------------- 棋盘 ----------------------
# 棋盘中心（唯一事实来源）。编辑器里移动棋盘后，把Anchor新坐标同步到这里即可。
# 注意：不能在运行时读 db/presets.json 取Anchor坐标——游戏加载世界后引擎会把
# virtual预设消耗掉（落成方块后清空该文件），脚本读到的永远是空列表（已实测）；
# ModSDK也没有查询预设坐标的API，Anchor方块本体又是普通泥土无法扫描识别。
BoardCenter = (1871, 62, 556)
# 棋盘基础边长（格数）：2人局的实际边长。多人乱斗按人数扩容（见下方
# "PvPvP多人对战"），实际铺设边长运行时由gomokuServerSystem计算。
# ★须为奇数（棋盘才有正中心）；资源环内半径运行时会按实际边长动态抬升，
# 不必为扩容手改（见SpawnAtRing等）
BoardSize = 9

# ---------------------- PvPvP多人对战（乱斗） ----------------------
# 不做黑白两队对抗：每个玩家自成一方（引擎里每人一个棋子值1~FFAMaxPlayers，
# 先连五子的"那个玩家"获胜）。棋石外观按棋子值上色（见StoneNormalNameByValue）。
# 棋盘随人数扩容：2人局=BoardSize基础边长，每多1名玩家边长+2
# （3人11、4人13），开局按在线人数计算。
# FFAMaxPlayers：乱斗最多支持的玩家数（引擎棋子值1~4=黑白蓝绿四色棋石，
# StartLogic里超过这个人数直接不让开局，见startLogicServerSystem.CheckState）。
# ★同时改需同步：gomokuServerSystem的GOMOKU_GOLD（须避开1~FFAMaxPlayers的
# 取值区间）、StoneNormalNameByValue/StoneHardenedNameByValue/PlayerColorDict
# 的条数（都按1~FFAMaxPlayers排）
FFAMaxPlayers = 4
BoardSizePerExtraPlayer = 2

# ---------------------- 棋盘随机化 ----------------------
# True时每局重新生成棋盘形状：中心不动，BoardSize见方范围内按概率随机缺格，
# 越靠边缘缺的概率越大（不是完全随机）。环距 ring = 格到中心的切比雪夫距离
# （0=中心格，half=BoardSize//2=最外环），规则：
#   1. ring <= BoardCenterKeepRadius 的环永远完整（保住棋盘核心）；
#   2. 之外的环缺格概率 = BoardEdgeRemoveChance * (ring/half) ** BoardRemoveFalloff
#      ——中心完好、向边缘平滑升高，最外环恰好等于 BoardEdgeRemoveChance；
#   3. 缺格 = 该格没有基座方块：本局无法落子（右键不到基座），但仍算主盘领地
#      （便携棋盘不能往缺格里铺，扩展格另找空地）；破盘镐拆格同理从形状里除名。
# 每一局开始时基座整层重铺后按新形状重新挖洞（见gomokuServerSystem的
# GenerateBoardCells/CarveBoardHoles）；False = 传统满盘
RandomizeBoard = True
# 最外环的缺格概率（0~1；0=边缘也不缺，等效满盘）
BoardEdgeRemoveChance = 0.5
# 缺格概率随环距升高的幂次（越大越"中心完好、边缘破碎"；1=线性过渡）
BoardRemoveFalloff = 2
# 距中心该环距以内永远完整（1=中心3x3；0=只有中心格必留）
BoardCenterKeepRadius = 1
# 玩家进服后延迟多少秒尝试铺盘（避初始化竞态；0=立即）
BoardBuildDelaySeconds = 1
# 引擎网格边长：主盘9x9 + 便携棋盘扩展格共用一张大网格（以主盘中心为正中心，
# 世界坐标平移映射进引擎，见gomokuServerSystem的WorldToGrid）。
# ★须为奇数且 >= BoardSize；99 = 引擎核心MAX_SIZE上限；也须 <= TickingAreaRadius*16
# （常驻加载区要盖得住整个网格——扩展格落在其中任意处都能落子）
EngineGridSize = 99
# 便携棋盘扩展格距主盘中心的最大距离（格）。★须 < EngineGridSize//2
# 且 < TickingAreaRadius*16，超出的摆放会被拒绝
CellPlaceMaxRadius = 48

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
# 已落子的棋石（颜色=落子方队伍；普通/硬化各有独立贴图——硬化版带金属包边+铆钉标记）。
# 挖掘门控（脚本层，见OnPlayerTryDestroyBlock）：普通棋石须石镐级、硬化棋石须铁镐级、
# 金棋石任何镐都挖不动（只能雷管炸）。高级镐可采低级棋石/矿（等级见PickaxeTierDict）。
# 盘上挖棋石耗时（destroy_time：普通3s/硬化5s）与盘外采同系矿一致（同3s/5s）——
# 棋子改为只产自挖矿后，拆对手的子不再额外收"拆家税"（原为6s/10s刻意加长）。
# 挖掉即销毁无掉落，并释放引擎对应格子
StoneBlackName = "wihzo:gomoku_stone_black"
StoneWhiteName = "wihzo:gomoku_stone_white"
StoneBlackHardenedName = "wihzo:gomoku_stone_black_hardened"
StoneWhiteHardenedName = "wihzo:gomoku_stone_white_hardened"
StoneBlueName = "wihzo:gomoku_stone_blue"
StoneGreenName = "wihzo:gomoku_stone_green"
StoneBlueHardenedName = "wihzo:gomoku_stone_blue_hardened"
StoneGreenHardenedName = "wihzo:gomoku_stone_green_hardened"
StoneGoldName = "wihzo:gomoku_stone_gold"
# 棋子值 -> 棋石方块名（乱斗外观按玩家上色：1黑、2白、3蓝、4绿）。
# 普通与硬化各一张表（硬化版外观同色带金属包边+铆钉标记）。
# 落子/方阵/墨水转化都按落子玩家的棋子值查表取方块（见GetStoneNameForValue）；
# 值越界/未在表里时兜底黑棋石。条数须覆盖1~FFAMaxPlayers，改人数上限时同步
StoneNormalNameByValue = {
	1: StoneBlackName,
	2: StoneWhiteName,
	3: StoneBlueName,
	4: StoneGreenName,
}
StoneHardenedNameByValue = {
	1: StoneBlackHardenedName,
	2: StoneWhiteHardenedName,
	3: StoneBlueHardenedName,
	4: StoneGreenHardenedName,
}
# 已点燃的雷管方块（TNT外观；右键棋盘摆出，BombFuseSeconds秒后引爆，
# 引爆前被挖掉=拆除）。名字须与netease_blocks/下JSON一致
DetonatorBlockName = "wihzo:gomoku_detonator_block"
# 棋石名集合（挖掘时按棋盘格处理；金棋石单独判）。乱斗棋石按棋子值上色
# （黑白蓝绿四色+各自的硬化款，见StoneNormalNameByValue），但归属的事实来源
# 仍是引擎网格里的棋子值——外观颜色只是展示，不参与判定（见HandleInkUse）
StoneBlockNameSet = {
    StoneBlackName, StoneWhiteName, StoneGoldName,
    StoneBlackHardenedName, StoneWhiteHardenedName,
    StoneBlueName, StoneBlueHardenedName,
    StoneGreenName, StoneGreenHardenedName,
}
# 硬化棋石集合（须铁镐级及以上挖掘，其余棋石石镐级即可——见OnPlayerTryDestroyBlock）
HardenedStoneNameSet = {
    StoneBlackHardenedName, StoneWhiteHardenedName,
    StoneBlueHardenedName, StoneGreenHardenedName,
}
# 乱斗模式棋子归属不看方块（方块不携带归属信息），以引擎网格里的棋子值为准
# （见HandleInkUse），故不再需要"棋石名->阵营"映射表

# ---------------------- 自定义物品（名字须与行为包netease_items_beh/、
# 资源包netease_items_res/下的JSON identifier一致） ----------------------
PickaxeStoneName = "wihzo:gomoku_pickaxe_stone"
PickaxeIronName = "wihzo:gomoku_pickaxe_iron"
PickaxeBoardName = "wihzo:gomoku_pickaxe_board"
ExecutionSwordName = "wihzo:execution_sword"
PieceItemNormal = "wihzo:gomoku_piece_normal"
PieceItemHardened = "wihzo:gomoku_piece_hardened"
PieceItemGold = "wihzo:gomoku_piece_gold"
PieceItemSquare = "wihzo:gomoku_piece_square"
PieceItemTrap = "wihzo:gomoku_piece_trap"
InkItemName = "wihzo:gomoku_ink"
DetonatorItemName = "wihzo:gomoku_detonator"
SwapItemName = "wihzo:gomoku_swap"
BoardItemName = "wihzo:gomoku_board"
ReflectPotionItemName = "wihzo:reflect_potion"
SpeedPotionItemName = "wihzo:speed_up"
DizzyHammerItemName = "wihzo:dizzy_hammer"
BrushItemName = "wihzo:gomoku_brush"
BlackHoleItemName = "wihzo:blackhole"
ChaosPotionItemName = "wihzo:chaos_poison"
TimestopItemName = "wihzo:timestop"
ManualItemName = "wihzo:gomoku_manual"

# ---------------------- 道具表 ----------------------
# 所有道具的统一定义，后续开发新道具只加这里，系统按 type 分派行为：
#   name:       短显示名（播报用；物品JSON里的display_name是带说明的详细版）
#   type:       'piece' 棋子 / 'pickaxe' 采集镐 / 'weapon' 武器 / 'ink' 转化墨水 / 'bomb' 爆炸雷管 /
#               'boardpick' 破盘镐 / 'swap' 换位符 / 'board' 便携棋盘 / 'reflect' 反伤药水 /
#               'speed' 加速药水 / 'brush' 笔刷 / 'blackhole' 吞噬黑洞 / 'timestop' 时间停止 /
#               'manual' 玩法说明书
#   consumable: 使用一次即销毁（耐久1）
#   piece 专用:  fromOre 产出该棋子的矿 / wildcard 万能挡子（金棋子，落子不分颜色、只挡线不获胜）/
#               square 方阵棋子（2x2铺子：点击格为左上角，越界/已占格忽略，见HandleSquarePlace）/
#               trap 陷阱棋子（落子外观=己方普通棋石，被挖毁时炸死范围内玩家，见DetonateTrap）
#   pickaxe专用: mineOre 本职对应的矿 / tier 镐等级（高级镐也能采低级矿与普通棋石）
#   weapon 专用: damage 攻击玩家造成的伤害（缺省用DefaultWeaponDamage）
#   ink 专用:    无额外字段（转化目标=右键到的敌方棋石，见HandleInkUse）
#   bomb 专用:   无额外字段（爆炸范围见BombBlastRange，右键棋盘引爆）
#   boardpick专用: 无额外字段（右键拆棋盘基座一格，见HandleBoardPickUse；只拆基座，别的都不响应）
#   swap 专用:   无额外字段（右键与最近的敌方玩家互换位置，见HandleSwapUse）
#   brush 专用:  无额外字段（走到比分文字板附近右键，给自己的系列赛胜场+1，
#               见HandleBrushUse；只能从问号方块开出，见RandomBlockPoolDict）
#   board 专用:  maxUses 可铺的1x1扩展格数（★须与beh JSON的minecraft:max_damage一致——
#               耐久是引擎物品数据，扣减/归零销毁见DamageBoardItem；扩展格与主盘
#               共用引擎网格，上面的子与主盘的子互相连线）
#   reflect专用: 无额外字段（右键激活护盾：下次受到来自其他玩家的真实伤害
#               （攻击或玩家道具）时，全额反弹给伤害来源；坠落等自然伤害/
#               中立来源不触发、护盾保留，见HandleReflectPotionUse/OnDamage）
#   timestop专用:无额外字段（右键冻结除使用者外的全场玩家TimestopFreezeSeconds秒，
#               客户端关移动/跳跃/攻击输入+服务端拦挖掘/落子/道具/拾取，见HandleTimestopUse）
ItemTable = {
	PieceItemNormal: {
		"name": "普通棋子", "type": "piece",
		"fromOre": "wihzo:gomoku_ore_normal",
	},
	PieceItemHardened: {
		"name": "硬化棋子", "type": "piece",
		"hardened": True,  # 落子后用硬化棋石（同色系独立贴图，挖掘耗时更长）
		"fromOre": "wihzo:gomoku_ore_hardened",
	},
	PieceItemGold: {
		"name": "金棋子", "type": "piece", "wildcard": True,
		"fromOre": "wihzo:gomoku_ore_gold",
	},
	PieceItemSquare: {
		"name": "方阵棋子", "type": "piece", "square": True,
	},
	PieceItemTrap: {
		"name": "陷阱棋子", "type": "piece", "trap": True,
	},
	PickaxeStoneName: {
		"name": "石镐", "type": "pickaxe", "consumable": True,
		"tier": 1,
		"mineOre": "wihzo:gomoku_ore_normal",
	},
	PickaxeIronName: {
		"name": "铁镐", "type": "pickaxe", "consumable": True,
		"tier": 2,
		"mineOre": "wihzo:gomoku_ore_hardened",
	},
	PickaxeBoardName: {
		"name": "破盘镐", "type": "boardpick", "consumable": True,
	},
	ExecutionSwordName: {
		"name": "处决剑", "type": "weapon", "consumable": True,
		"damage": 9999,
	},
	InkItemName: {
		"name": "转化墨水", "type": "ink", "consumable": True,
	},
	DetonatorItemName: {
		"name": "爆炸雷管", "type": "bomb", "consumable": True,
	},
	SwapItemName: {
		"name": "换位符", "type": "swap", "consumable": True,
	},
	ReflectPotionItemName: {
		"name": "反伤药水", "type": "reflect", "consumable": True,
	},
	SpeedPotionItemName: {
		"name": "加速药水", "type": "speed", "consumable": True,
	},
	DizzyHammerItemName: {
		"name": "眩晕锤", "type": "weapon", "consumable": True,
		# dizzy=零伤害缴械武器：命中敌方玩家不造成伤害，改为眩晕+掉落全部道具
		# （见OnPlayerAttack的dizzy分支与HandleDizzyHammerHit）；
		# 不写damage（缺省会套DefaultWeaponDamage一击必杀）
		"dizzy": True,
	},
	BrushItemName: {
		"name": "笔刷", "type": "brush", "consumable": True,
	},
	BlackHoleItemName: {
		"name": "吞噬黑洞", "type": "blackhole", "consumable": True,
		# 黑洞专用:无额外字段（右键吞噬棋盘上全部棋子，不分敌我，见HandleBlackholeUse）。
		# 只从问号方块奖励池产出（RandomBlockPoolDict），不进ItemTierDict常规刷新环
	},
	ChaosPotionItemName: {
		"name": "混乱药水", "type": "weapon", "consumable": True,
		# chaos=控制反转武器：命中敌方玩家不造成伤害，改为ChaosPotionConfuseSeconds秒混乱
		# ——前后左右移动反向（客户端把真实输入取负后LockInputVector，按平台分事件/轮询取输入，
		# 见HandleChaosPotionHit与gomokuClientSystem），全屏表现用原版反胃（天旋地转、零伤害）；
		# 不写damage（缺省会套DefaultWeaponDamage一击必杀）
		"chaos": True,
	},
	TimestopItemName: {
		"name": "时间停止", "type": "timestop", "consumable": True,
		# timestop=全局控制道具：右键使用（UseOn/TryUse双入口），除使用者外的全场
		# 玩家冻结TimestopFreezeSeconds秒——移动/跳跃/攻击输入在其客户端关
		# （SetCanMove/SetCanJump/SetCanAttack，视角转动保留），挖掘/落子/道具/
		# 拾取在服务端拦（见各事件入口的IsTimestopFrozen检查）；
		# 只从问号方块奖励池产出（RandomBlockPoolDict），不进ItemTierDict常规刷新环
	},
	BoardItemName: {
		"name": "便携棋盘", "type": "board",
		"maxUses": 2,  # 可铺2格（★与beh JSON的minecraft:max_damage一致）
	},
	ManualItemName: {
		"name": "玩法说明书", "type": "manual",
	},
}

# 雷管专用：爆炸范围 = 以雷管方块为中心的立方体边长（3=3x3x3，各轴向±1），
# 只清范围内的棋石（基座/地形无损，不留坑）；雷管可叠在棋子上方摆放，不替换棋子。
# 引信时长（秒）：摆出雷管方块后等这么久才引爆（给对手挖掉拆除的窗口）
BombBlastRange = 3
BombFuseSeconds = 3
# 引爆时的原生TNT爆炸表现（原版爆炸粒子huge_explosion_emitter + 音效random.explode，
# 纯表现——只播特效，不炸基座/地形，清子逻辑不变）
BombExplosionEffect = True

# 武器没写damage时的兜底伤害
DefaultWeaponDamage = 9999

# 陷阱棋子：棋石被挖毁时的爆炸半径（格，选择器r参数）。只炸玩家不毁棋石/棋盘/地形
# （与雷管正相反：雷管只毁棋不伤人）。★须≥挖掘触手距离（约4格），
# 保证亲手挖陷阱的玩家自己也在爆炸半径内
TrapKillRadius = 4

# 加速药水：使用后给自己提速——引擎移动速度在基础值上提升 SpeedPotionPercent 百分比，
# 持续 SpeedPotionDuration 秒后自动恢复原速；连喝不叠加，只重置持续时间（见HandleSpeedPotionUse）
SpeedPotionPercent = 25     # 提速百分比（25=比原速快25%）
SpeedPotionDuration = 10    # 持续秒数

# 眩晕锤：锤中敌方玩家不造成伤害，但目标被眩晕（移速锁死+反胃+拳头无力）这么
# 多秒、背包道具全部掉在脚下（眩晕期间拾取被拦截，防原地秒捡回去——见
# HandleDizzyHammerHit）。效果时长按整秒生效（引擎AddEffectToEntity只收整秒）
DizzyHammerStunSeconds = 1.5

# 笔刷：走到比分文字板（TextAnchor位置）附近右键，直接给自己的系列赛胜场
# +BrushWinBonus（等于白捡一局胜利），用一次即碎。★唯一获取途径是问号方块
# （见RandomBlockPoolDict的权重，极低概率）——刻意不进ItemTierDict的任何环形
# 刷新池，地上永远不会自然刷出笔刷。
# 可用距离（格）：玩家与ScoreBoardAnchor的三维直线距离须在此以内，否则右键
# 无效且不消耗道具（"必须走到记分牌前"才是这件道具的成本所在）。
# ★ScoreBoardAnchor为None（比分文字板关闭）时笔刷直接失效
BrushUseRadius = 6
# 每次涂抹加多少胜场（1=白捡一局；改大就是白捡多局）
BrushWinBonus = 1

# 混乱药水：砸中敌方玩家后目标进入混乱的时长（秒）——期间前后左右移动反向
# （客户端把真实输入取负后LockInputVector，按平台分事件/轮询取真实输入，
# 见gomokuClientSystem），全屏表现用原版反胃（天旋地转、零伤害）。
# 客户端反向用的是本地时钟，时长与整秒粒度的反胃表现略有出入属正常
ChaosPotionConfuseSeconds = 10

# 时间停止：右键使用后，除使用者外的全场其他玩家冻结这么久（秒）——不能移动/跳跃/
# 攻击（其客户端关输入，见gomokuClientSystem），不能挖掘/落子/用道具/拾取（服务端
# 拦，见各事件入口的IsTimestopFrozen检查），但可以转动视角；使用者本人行动不受影响。
# 效果不跨局（新一局开始全体解冻）；与冻结玩家间的伤害不受影响（冻结只锁操作不锁血）
TimestopFreezeSeconds = 5

# 派生表（由道具表自动生成，勿手改）
# 镐 -> 等级（高级镐可采低级矿与低级棋石）
PickaxeTierDict = {item: cfg["tier"] for item, cfg in ItemTable.iteritems() if cfg["type"] == "pickaxe"}
# 等级 -> 该等级镐的显示名（播报"须用X或更高级的镐"用）
TierPickaxeNameDict = {cfg["tier"]: cfg["name"] for item, cfg in ItemTable.iteritems() if cfg["type"] == "pickaxe"}
# 矿 -> 采集所需最低镐等级（金矿无条目=徒手可挖）
OreMinTierDict = {cfg["mineOre"]: cfg["tier"] for item, cfg in ItemTable.iteritems() if cfg["type"] == "pickaxe"}
# 矿 -> 采到的棋子物品
OrePieceItemDict = {cfg["fromOre"]: item for item, cfg in ItemTable.iteritems() if "fromOre" in cfg}
# 全部棋子物品名集合（背包携带上限的计数范围）
PieceItemNameSet = {item for item, cfg in ItemTable.iteritems() if cfg["type"] == "piece"}

# ---------------------- 背包规则 ----------------------
# 新一局开始时清空全体玩家背包（上一局残留的棋子/道具不留到下一局；存档开着
# keepInventory时上一局的物品会跟人进下一局，这里统一回收）
ClearInventoryOnRoundStart = True
# 玩家携带棋子上限（普通/硬化/金棋子合计；镐/剑等道具不限制）。
# 超限时：捡拾掉落物被拦截（物品留在地上），挖矿被取消（矿留原地、镐不消耗）
MaxCarriedPieces = 2
# 拦截拾取后该掉落物的拾取cd（帧，30帧=1秒；防止玩家站在物品上时每帧重触发事件）
FullPickupDelayFrames = 30
# 节流播报的按(玩家,类型)冷却（秒，防连续触发刷屏；棋子上限/基座防挖提示共用）
ThrottledAnnounceCooldown = 5

# ---------------------- 阵亡与复活 ----------------------
# 原版死亡界面已由WorldMod的immediate_respawn游戏规则关闭（阵亡不弹"是否重生"窗口）：
# 引擎阵亡后自动重生、无需点击。重生后行动封锁这么久（秒）：
# 落子/墨水/雷管/挖矿/拾取/武器攻击全部拦截，每秒聊天框倒计时，
# 期间免疫伤害（防复活点被连杀蹲尸），时间到自动恢复行动。0 = 不封锁（阵亡即满状态回归）
DeathRespawnHoldSeconds = 5
# 引擎复活点 = 棋盘中心 + 此偏移（x, 备用y, z；实际y取地表，查询失败才用备用y）。
# 无床玩家默认在世界出生点重生，本图出生点在远处未加载区块，重生会永远卡在
# "正在重生"——故进服/开局时把每个玩家的复活点设到棋盘外沿（tickingarea常驻
# 加载范围内）。重生落地后LimitedRespawn再传送到队伍复活点，此点只保证重生能完成。
# ★z方向偏移须超出棋盘半边长（实际边长/2），免得重生点落在棋盘上——乱斗模式
# 棋盘随人数扩容，偏移不够时运行时自动外推（见GetEngineRespawnPos），不必手改
RespawnPosOffset = (0, 2, 7)

# ---------------------- 队伍（乱斗模式下仅作基础设施） ----------------------
# 乱斗（PvPvP）不做队伍对抗：TeamMod的2队只保留出生点/传送/计分板等基础设施，
# 棋子归属由GomokuMod自己的逻辑棋子值区分（开局每人分配1~FFAMaxPlayers，
# 见gomokuServerSystem的AssignPieceValues），与队伍无关。
# 队友间伤害已在script_Team的teamConfig打开（canHurtTeammate=True），
# 乱斗下所有人互相均可造成伤害

# 单人调试开关：True时单人落子在两个逻辑棋子值间交替（无视分配表），用于单人
# 验证多方胜负逻辑；正式对战必须为False（按落子玩家的棋子值落子）。
# 金棋子不受影响（本就不分归属）
DebugSoloAlternateSides = False

# 调试聊天命令开关：True时聊天输入 #give <道具名> 可直接领取道具（#give 列出可领道具，
# 拿便携棋盘/处决剑等做验证用）；#chaos [秒] 直接让自己进入混乱状态（单人测视角/移速
# 反向），#unchaos 提前解除；正式对战必须关掉
DebugChatCommands = True

# ---------------------- 资源总量维持 ----------------------
# 每种资源在地图上的存量上限：刷新时先数当前已有的数量——已有 >= 上限就跳过本次刷新，
# 总量维持恒定，玩家采走（存量下降）后才会补刷。
# 矿石计数：开局全环重扫一遍（兼容存档残留），此后每RecountIntervalSeconds秒重扫修正，
# 平时靠 刷出+1 / 挖碎-1 实时维护；
# 物品计数：自维护"在场"数（地上的+背包里未使用的都算在场）——用掉立刻释放空位
# （ConsumeCarriedItem消耗时剔除），到期未使用的按自然消失释放（SpawnItemToLevel
# 只返回True拿不到entityId，掉落物消失无法感知，按登记的到期时刻剔除）。
SpawnMaxCountDict = {
	# 普通矿：黑白两半区合计（每半区常驻约6个）
	"wihzo:gomoku_ore_normal": 12,
	# 硬化矿：中环合计
	"wihzo:gomoku_ore_hardened": 6,
	# 金矿：中环紧贴硬化矿外侧，稀少（普通/硬化棋子物品已不再直刷，
	# 棋子全部产自挖矿——见SpawnConfigList的说明）
	"wihzo:gomoku_ore_gold": 2,
	# 直刷的特殊棋子物品（普通/硬化棋子物品不再直刷；道具不在此表——道具走
	# 分级共用上限，见ItemTierDict）
	# 方阵棋子：一次铺四子的节奏型大件，地图上至多1枚
	PieceItemSquare: 1,
	# 陷阱棋子：阴人专用，地图上至多1枚
	PieceItemTrap: 1,
}
# 矿石全环重扫间隔（秒）：重扫分帧进行，每帧查ScanColumnsPerTick列，避免单tick卡顿
RecountIntervalSeconds = 30
ScanColumnsPerTick = 25
# 掉落物自然消失时间（秒）：物品"在场"计数据此到期释放空位（对齐原版5分钟消失；
# 物品被使用会立刻释放，不等这个时间）
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
	# 金棋子矿：中环硬化矿带内（原在外环25~35格，刻意拉近——金子是万能挡子，
	# 太远没人跑；混在硬化矿里挖着挖着捡到金子也算小惊喜），徒手可挖
	{"type": "ore", "blockName": "wihzo:gomoku_ore_gold", "radius": (16, 20), "angleRange": (0, 360), "interval": 60},
	# ★棋子物品不再直刷（普通/硬化都只能挖对应矿获得）：地上白捡的棋子会让
	# 镐子失去存在意义——想拿子就得先从低级道具环搞到镐
	# 方阵棋子：中环偏外，低频直刷（一次铺四子，节奏价值极高故稀有；无对应矿，只能直刷）
	{"type": "item", "itemName": PieceItemSquare, "radius": (14, 20), "angleRange": (0, 360), "interval": 45},
	# 陷阱棋子：中环偏外，极低频直刷（存在感越低越有效；无对应矿，只能直刷）
	{"type": "item", "itemName": PieceItemTrap, "radius": (14, 20), "angleRange": (0, 360), "interval": 60},
	# 道具（镐/剑/墨水/雷管）不走本表——按等级走ItemTierDict的分级刷新
]

# ---------------------- 道具分级刷新 ----------------------
# 道具（type != 'piece'的物品）按等级分池刷新：每个等级对应一个环——
# 近环刷低级、中环刷中级、远环刷高级（离棋盘越远越值钱，跑得越远投资越大）；
# 到点先查该等级全部道具的"在场"合计（地上+背包未使用，用掉立刻释放），
# 没到TierMaxCountDict上限就掷chance、从池子里等权随机抽一个生成。
# 池内道具不再各自设上限——道具种类越多，池子越丰富，但场上总量恒定。
# 字段：name 播报/日志名 / items 道具池 / radius 刷新环（★内半径须 > BoardSize/2）/
# interval 刷新间隔秒 / chance 每次刷新时刻的兑现概率（缺省必刷）
ItemTierDict = {
	"low": {
		"name": "低级道具",
		"items": [PickaxeStoneName, PickaxeIronName],
		"radius": (5, 10), "interval": 5,
	},
	"mid": {
		"name": "中级道具",
		"items": [InkItemName, DetonatorItemName, PickaxeBoardName, BoardItemName, SpeedPotionItemName, ChaosPotionItemName],
		"radius": (10, 25), "interval": 5,
	},
	"high": {
		"name": "高级道具",
		"items": [ExecutionSwordName, SwapItemName, ReflectPotionItemName, DizzyHammerItemName],
		"radius": (25, 35), "interval": 10,
	},
}
# 各等级道具的在场合计上限（同等级共用一个空位池，谁用掉谁释放）
TierMaxCountDict = {
	"low": 6,
	"mid": 4,
	"high": 3,
}

# ---------------------- 问号方块（随机道具块） ----------------------
# 中环偏外独立刷新的问号方块：任意镐可采（石镐/铁镐皆可，耐久1采一次即碎，
# 与矿石不同——不限定矿种，拿任意镐都行）；徒手/没拿镐也能挖穿但拿不到奖励
# （与矿石"拿错工具白挖"同款原版体验）。采到后从RandomBlockPoolDict
# 加权随机抽一个道具直接发到背包。名字须与netease_blocks/下JSON、
# 资源包terrain_texture.json/blocks.json的注册一致
RandomBlockName = "wihzo:gomoku_block_random"
# 随机奖励池（道具名 -> 权重）：不含棋子——避开棋子携带上限（MaxCarriedPieces）
# 满时抽到棋子无处安放的边界；权重越大越常出，等权就全写一样的数。
# 权重是相对值（抽取时按合计归一化，见DrawRandomBlockReward），故常规道具统一
# 放大到十位数，好让笔刷这种"极低概率"的东西能用权重1表达出约1%的档位。
# 石镐刻意不在池里（权重=0）：镐子走低级道具环常规刷新，问号方块再送会让
# 白捡的镐冲淡"挖矿换子"的动机（玩家要靠环里刷的镐去挖矿）
RandomBlockPoolDict = {
	PickaxeIronName: 20,
	InkItemName: 20,
	DetonatorItemName: 20,
	BoardItemName: 10,
	ExecutionSwordName: 10,
	# 补进问号箱的6件（原先只在分级刷新环出，问号箱抽不到）——权重是
	# 占位默认值，概率自行调配
	PickaxeBoardName: 10,
	SpeedPotionItemName: 10,
	ChaosPotionItemName: 10,
	SwapItemName: 5,
	ReflectPotionItemName: 5,
	DizzyHammerItemName: 5,
	# 笔刷：唯一获取途径，极低概率（1/118 ≈ 0.8%）。白送一局胜场，故刻意做成
	# "开一百个问号方块才见一次"的彩票；调高这个数就是调高出率
	BrushItemName: 1,
	# 吞噬黑洞：全盘清子的大杀器，只走问号方块（权重1=与处决剑并列最稀有档，
	# 不进ItemTierDict常规刷新环——场上只能靠挖问号方块碰运气）
	BlackHoleItemName: 1,
	# 时间停止：5秒全场冻结的大杀器，同黑洞只走问号方块（权重1并列最稀有档）
	TimestopItemName: 1,
}
# 刷新参数（独立于SpawnConfigList/ItemTierDict，自成一条刷新协程）：
# radius 刷新环(内,外半径，格) / interval 刷新间隔(秒) /
# maxCount 场上存量上限（维持总量，走矿石计数oreCountDict+周期重扫） /
# chance 每次刷新时刻的兑现概率（缺省DefaultSpawnChance必刷）
RandomBlockSpawnConfig = {
	"radius": (18, 28),
	"interval": 30,
	"maxCount": 3,
}

# ---------------------- 胜利条件 ----------------------
# 连珠数（几子连珠获胜）
WinRowLength = 5

# ---------------------- 玩家颜色表 ----------------------
# 键 = 本局逻辑棋子值（1~FFAMaxPlayers，开局按人头分配，见AssignPieceValues）——
# 也就是"这一局你是几号玩家"。每人一色，且与棋石方块同色（1黑2白3蓝4绿，
# 见StoneNormalNameByValue）：
#   name  色名（比分行/播报里带一个中文色名，小字看不清颜色时也认得出人）
#   code  聊天框§颜色码（聊天播报用；文字板不吃§码，颜色走rgba）
#   rgba  文字板颜色（RGBA 0~1，引擎TextBoard只收这个格式）
# ★条数须 >= FFAMaxPlayers，否则超出的玩家退回PlayerColorFallback（白）。
# 黑色在文字板上用深灰（纯黑字看不清）、聊天用§8同理；白色与兜底色相同是
# 已知取舍（没分到值的旁观者也是白——反正他本局没有棋子）
PlayerColorDict = {
	1: {"name": "黑", "code": "§8", "rgba": (0.35, 0.35, 0.35, 1.0)},
	2: {"name": "白", "code": "§f", "rgba": (0.95, 0.95, 0.95, 1.0)},
	3: {"name": "蓝", "code": "§9", "rgba": (0.33, 0.55, 1.00, 1.0)},
	4: {"name": "绿", "code": "§a", "rgba": (0.40, 0.90, 0.40, 1.0)},
}
# 没有本局棋子值时（等待阶段/满员旁观）的兜底颜色
PlayerColorFallback = {"name": "白", "code": "§f", "rgba": (1.0, 1.0, 1.0, 1.0)}

# ---------------------- 比分文字板（TextAnchor预设位置） ----------------------
# 比分 = 系列赛胜场：每局连成五子的玩家 +1，跨局累计（不是本局落子数，
# 新一局开始不清零，见gomokuServerSystem的playerWinCountDict）。
# 一行一名玩家，文字用该玩家自己的颜色（PlayerColorDict按棋子值取色）。
#
# 位置 = 编辑器里"TextAnchor"预设的坐标。与BoardCenter同理：不能在运行时读
# db/presets.json——加载世界后引擎会把virtual预设消耗掉并清空该文件，脚本读到的
# 永远是空列表（已实测）。编辑器里移动TextAnchor后把新坐标同步到这里。
# None = 关闭比分文字板
ScoreBoardAnchor = (1868, 65, 589)
# 整列文字板抬高多少格：锚点方块是贴着地面放的（编辑器里点地表放预设），
# 标题直接用锚点高度会把半截字埋进土里，玩家行再往下排就全在地下。
# 抬高后标题=锚点Y+本值，玩家行自标题向下排（人多的局最后一两行可能又
# 接近地面，是已知取舍）。EndLogic的系列赛记分牌立在本列最上方（标题Y
# 再+1.2），改这里记得同步它那边的scoreboardPos
ScoreBoardLiftY = 3.0
# 标题行（永远在最上面，白字）
ScoreBoardTitle = "=== 比分 ==="
ScoreBoardTitleColor = (1.0, 1.0, 1.0, 1.0)
# 文字缩放 (x, y)：引擎SetBoardScale只收两个分量（编辑器TextBoard预设用的是3.0）
ScoreBoardScale = (3.0, 3.0)
# 相邻两行的Y间距（格）：标题在锚点高度+抬高量，第N名玩家往下降 N * 本值。
# ★缩放调大后字更高，行距要跟着加，否则上下行会叠在一起（只能进游戏肉眼调）
ScoreBoardLineHeight = 0.6
# 是否始终面向镜头：True = 从任何方向走过来都读得到字。锚点在森林里、
# 玩家开局就在安全圈四边，固定朝向很容易正好走到板背面看到空白
# （EndLogic的系列赛记分牌同款配置，一起改）
ScoreBoardFaceCamera = True
# 底板颜色（RGBA 0~1）；alpha=0 即透明无底板（同编辑器TextBoard预设）
ScoreBoardBackColor = (0.0, 0.0, 0.0, 0.0)
# 客户端就绪(UiInitFinished)后延迟多少帧建板（30帧=1秒，避初始化竞态）
ScoreBoardCreateDelayFrames = 30
# 场上没有玩家时（服务端还没推过数据/空服）显示的占位行
ScoreBoardWaitingText = "等待对局开始"

# ---------------------- 玩法说明书（进服即发放，右键打开） ----------------------
# 进服（等待阶段，DelayGiveManual延迟1秒）就发一本——等待期即可翻阅；
# 开局/clear清空背包后补发（对局中随时能翻书）。手持右键（含对空气）打开
# 客户端弹窗：gomokuClientSystem收到ManualOpenEvent后PushScreen弹manualUI。
# 客户端注册（对照LimitedRespawn的UI命名方式）
ManualUIName = "gomokuManualUI"
ManualUIPyClsPath = "manualUI.ManualUIScreen"
ManualUIScreenDef = "gomokuManualUI.main"
# 假摇杆HUD（混乱药水手机/触屏模式的移动反向；布局在ui/chaosJoystickUI.json，
# 注册在gomokuClientSystem.OnUiInitFinished，混乱开始时显示、结束隐藏）
ChaosJoystickUIName = "chaosJoystickUI"
ChaosJoystickUIPyClsPath = "chaosJoystickUI.ChaosJoystickScreen"
ChaosJoystickUIScreenDef = "chaosJoystickUI.main"
# 教程文案 ManualTextList 已迁至 messageConfig.py（玩家可见文案统一管理）
