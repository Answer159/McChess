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

# Client System（说明书弹窗，见gomokuClientSystem.py；modMain的InitClient注册）
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
PlayerDieEvent = "PlayerDieEvent"
DelServerPlayerEvent = "DelServerPlayerEvent"
DamageEvent = "DamageEvent"
#  Custom（服务端广播给所有客户端，供后续五子棋UI监听）
GomokuGameResultEvent = "GomokuGameResultEvent"
#  Custom（服务端 -> 客户端：请求打开说明书弹窗）
ManualOpenEvent = "GomokuManualOpenEvent"

# 跨Mod事件/系统名（★改=对应Mod的config同步改，且事件名是字符串字面量广播，需全局搜）
StartLogicModName = "StartLogicMod"
StartLogicServerSystemName = "StartLogicServerSystem"
StartLogicEvent = "StartLogicEvent"
EndLogicModName = "EndLogicMod"
EndLogicServerSystemName = "EndLogicServerSystem"
TeamModName = "TeamMod"
TeamServerSystemName = "TeamServerSystem"

# ---------------------- 棋盘 ----------------------
# 棋盘中心（唯一事实来源）。编辑器里移动棋盘后，把Anchor新坐标同步到这里即可。
# 注意：不能在运行时读 db/presets.json 取Anchor坐标——游戏加载世界后引擎会把
# virtual预设消耗掉（落成方块后清空该文件），脚本读到的永远是空列表（已实测）；
# ModSDK也没有查询预设坐标的API，Anchor方块本体又是普通泥土无法扫描识别。
BoardCenter = (1871, 62, 556)
# 棋盘边长（格数），实际铺设为 BoardSize x BoardSize 的基座方阵（随机化开启时
# 是最大范围，边缘会随机缺格，见下方"棋盘随机化"），基座层会覆盖掉Anchor方块
# ★须为奇数（棋盘才有正中心）；改动后资源环最小内半径须 > BoardSize/2，否则物品会掉在棋盘上
BoardSize = 9

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
# 挖掘门控（脚本层，见OnPlayerTryDestroyBlock）：普通棋石须石镐、硬化棋石须铁镐、
# 金棋石任何镐都挖不动（只能雷管炸）。
# 盘上挖棋石耗时（destroy_time：普通6s/硬化10s）刻意长于盘外采同系矿（3s/5s）——
# 拆对手的子比抢矿更费时，削弱互相拆家的收益。
# 挖掉即销毁无掉落，并释放引擎对应格子
StoneBlackName = "wihzo:gomoku_stone_black"
StoneWhiteName = "wihzo:gomoku_stone_white"
StoneBlackHardenedName = "wihzo:gomoku_stone_black_hardened"
StoneWhiteHardenedName = "wihzo:gomoku_stone_white_hardened"
StoneGoldName = "wihzo:gomoku_stone_gold"
# 已点燃的雷管方块（TNT外观；右键棋盘摆出，BombFuseSeconds秒后引爆，
# 引爆前被挖掉=拆除）。名字须与netease_blocks/下JSON一致
DetonatorBlockName = "wihzo:gomoku_detonator_block"
# 全部棋石方块集合（挖掘时按棋盘格处理）
StoneBlockNameSet = {
    StoneBlackName, StoneWhiteName, StoneGoldName,
    StoneBlackHardenedName, StoneWhiteHardenedName,
}
# 棋石名 -> 所属阵营（墨水转化用：判断右键到的是敌方的子还是己方的子）
StoneSideDict = {
    StoneBlackName: "black", StoneBlackHardenedName: "black",
    StoneWhiteName: "white", StoneWhiteHardenedName: "white",
    StoneGoldName: "gold",
}

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
AntiDamageItemName = "wihzo:anti_damage"
SpeedPotionItemName = "wihzo:speed_up"
DizzyHammerItemName = "wihzo:dizzy_hammer"
ManualItemName = "wihzo:gomoku_manual"

# ---------------------- 道具表 ----------------------
# 所有道具的统一定义，后续开发新道具只加这里，系统按 type 分派行为：
#   name:       短显示名（播报用；物品JSON里的display_name是带说明的详细版）
#   type:       'piece' 棋子 / 'pickaxe' 采集镐 / 'weapon' 武器 / 'ink' 转化墨水 / 'bomb' 爆炸雷管 /
#               'boardpick' 破盘镐 / 'swap' 换位符 / 'board' 便携棋盘 / 'manual' 玩法说明书 /
#               'transfer' 转移符 / 'speed' 加速药水
#   consumable: 使用一次即销毁（耐久1）
#   piece 专用:  fromOre 产出该棋子的矿 / wildcard 万能挡子（金棋子，落子不分颜色、只挡线不获胜）/
#               square 方阵棋子（2x2铺子：点击格为左上角，越界/已占格忽略，见HandleSquarePlace）/
#               trap 陷阱棋子（落子外观=己方普通棋石，被挖毁时炸死范围内玩家，见DetonateTrap）
#   pickaxe专用: mineOre 能采集的矿（各挖各的）
#   weapon 专用: damage 攻击玩家造成的伤害（缺省用DefaultWeaponDamage）
#   ink 专用:    无额外字段（转化目标=右键到的敌方棋石，见HandleInkUse）
#   bomb 专用:   无额外字段（爆炸范围见BombBlastRange，右键棋盘引爆）
#   boardpick专用: 无额外字段（右键拆棋盘基座一格，见HandleBoardPickUse；只拆基座，别的都不响应）
#   swap 专用:   无额外字段（右键与最近的敌方玩家互换位置，见HandleSwapUse）
#   board 专用:  maxUses 可铺的1x1扩展格数（★须与beh JSON的minecraft:max_damage一致——
#               耐久是引擎物品数据，扣减/归零销毁见DamageBoardItem；扩展格与主盘
#               共用引擎网格，上面的子与主盘的子互相连线）
#   transfer专用: 无额外字段（右键激活护盾：下次受到的真实伤害不落在自己身上，
#               全额转给最近的敌方玩家，见HandleTransferUse/OnDamage）
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
		"mineOre": "wihzo:gomoku_ore_normal",
	},
	PickaxeIronName: {
		"name": "铁镐", "type": "pickaxe", "consumable": True,
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
	AntiDamageItemName: {
		"name": "转移符", "type": "transfer", "consumable": True,
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

# 派生表（由道具表自动生成，勿手改）
# 镐 -> 可采集的矿
PickaxeOreDict = {item: cfg["mineOre"] for item, cfg in ItemTable.iteritems() if cfg["type"] == "pickaxe"}
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
# ★z方向偏移须超出棋盘半边长（BoardSize/2），免得重生点落在棋盘上
RespawnPosOffset = (0, 2, 7)

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

# 调试聊天命令开关：True时聊天输入 #give <道具名> 可直接领取道具（#give 列出可领道具，
# 拿便携棋盘/处决剑等做验证用）；正式对战必须关掉
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
	# 金矿：外环守卫区，极稀少
	"wihzo:gomoku_ore_gold": 2,
	# 直刷棋子物品（道具不在此表——道具走分级共用上限，见ItemTierDict）
	PieceItemNormal: 5,
	PieceItemHardened: 3,
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
	# 金棋子矿：外环守卫区（跑一趟=离开战场很久），徒手可挖
	{"type": "ore", "blockName": "wihzo:gomoku_ore_gold", "radius": (25, 35), "angleRange": (0, 360), "interval": 60},
	# 普通棋子物品：近环高频直刷
	{"type": "item", "itemName": PieceItemNormal, "radius": (5, 9), "angleRange": (0, 360), "interval": 3},
	# 硬化棋子物品：中环直接掉落
	{"type": "item", "itemName": PieceItemHardened, "radius": (9, 14), "angleRange": (0, 360), "interval": 15},
	# 方阵棋子：中环偏外，低频直刷（一次铺四子，节奏价值极高故稀有）
	{"type": "item", "itemName": PieceItemSquare, "radius": (14, 20), "angleRange": (0, 360), "interval": 45},
	# 陷阱棋子：中环偏外，极低频直刷（存在感越低越有效）
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
		"items": [InkItemName, DetonatorItemName, PickaxeBoardName, BoardItemName, SpeedPotionItemName],
		"radius": (10, 25), "interval": 5,
	},
	"high": {
		"name": "高级道具",
		"items": [ExecutionSwordName, SwapItemName, AntiDamageItemName, DizzyHammerItemName],
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
# 满时抽到棋子无处安放的边界；权重越大越常出，等权就全写一样的数
RandomBlockPoolDict = {
	PickaxeStoneName: 3,
	PickaxeIronName: 2,
	InkItemName: 2,
	DetonatorItemName: 2,
	BoardItemName: 1,
	ExecutionSwordName: 1,
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

# ---------------------- 玩法说明书（进服即发放，右键打开） ----------------------
# 进服（等待阶段，DelayGiveManual延迟1秒）就发一本——等待期即可翻阅；
# 开局/clear清空背包后补发（对局中随时能翻书）。手持右键（含对空气）打开
# 客户端弹窗：gomokuClientSystem收到ManualOpenEvent后PushScreen弹manualUI。
# 客户端注册（对照LimitedRespawn的UI命名方式）
ManualUIName = "gomokuManualUI"
ManualUIPyClsPath = "manualUI.ManualUIScreen"
ManualUIScreenDef = "gomokuManualUI.main"
# 教程文案：每个元素一页（\n换行，§颜色代码可用）。只改文案不用动UI与逻辑
ManualTextList = [
	"§l§e■ 玩法目标\n"
	"§r§f黑白双方分别向棋盘上落子，横、竖、斜任意方向\n"
	"§f先连成 §e五子 §f的队伍立即获胜！\n\n"
	"§f棋盘每局随机形状，棋子只能落在棋盘上\n\n"
	"§f一局限时8分钟，到时间未分胜负则双方平局。\n",
    "总游戏为5局3胜制\n",
	"§l§e■ 采集\n"
	"§r§f棋子是采集来的，不在背包里凭空产生：\n\n"
	"§f普通棋子矿（近环）——须持 §b石镐 §f挖\n"
	"§f硬化棋子矿（中环）——须持 §b铁镐 §f挖，落子更难被拆\n"
	"§f金棋子矿（远环）——徒手可挖\n"
	"§f使用镐采集§d问号方块 可以获得随机道具\n"
	"§c注意：棋子最多同时携带2个，背包中持有2子时无法获得更多棋子哦",
	"§l§e■ 落子与拆子\n"
	"§r§f手持棋子右键棋盘基座即可落子（颜色=你的队伍）。\n\n"
	"§f特殊棋子：\n"
	"§f  §d方阵棋子 §f——一次铺下2x2四枚己方棋子\n"
	"§f  §d陷阱棋子 §f——外观与普通棋子完全相同，\n"
	"§f  被对手挖毁的瞬间炸死周围的人\n\n"
	"§f盘上的棋子可以拆除，普通棋子须使用石镐、硬化须使用铁镐，\n"
	"§f但是在盘上挖子比采集棋子慢得多而且不会获得棋子",
	"§l§e■ 道具：中环\n"
	"§r§d转化墨水 §f——右键敌方棋子，变成己方颜色\n"
	"§d爆炸雷管 §f——右键棋盘摆出，3秒后引爆，\n"
	"§f  炸掉3x3范围内的全部棋子（不管敌我）；\n"
	"§f  引信期间可被挖掉拆除\n"
	"§d破盘镐 §f——右键拆掉棋盘基座一格\n"
	"§d便携棋盘 §f——右键铺一格新棋盘格（耐久2次），\n"
	"§f  新格也能与主盘互相连线哦\n",
	"§l§e■ 道具：远环\n"
	"§r§d处决剑 §f——攻击玩家一击必杀（用一次即碎），\n"
	"§f  死者会掉落全部携带物品\n"
	"§d换位符 §f——右键与最近的\n"
	"§f  敌方玩家互换位置，无距离限制\n\n"
	"§f越好的道具刷新在棋盘越远处\n",
	"§l§e■ 阵亡规则\n"
	"§r§f死亡后会自动在棋盘附近复活。\n\n"
	"§7—— 祝武运昌隆 ——",
]

# ---------------------- 比分记分牌（告示牌） ----------------------
# 比分告示牌的世界坐标列表：编辑器里摆好告示牌后把坐标填进来（空列表=功能关闭）。
# 与BoardCenter同理：运行时读不到预设坐标，只能走config常量；牌须是原版告示牌方块
# （standing_sign/wall_sign均可），坐标=告示牌方块本身所在的格子。
# 所有牌显示同一内容：黑方/白方跨局累计胜场。计分就存在牌面文本里（随世界存档持久，
# 重进服务器不清零）；第一块牌被拆掉或文本被改坏（解析不出数字）则从0:0重新计。
# 临时改分=直接改牌面文字，保持"黑方 N 胜"格式即可被读回
ScoreSignPosList = []
