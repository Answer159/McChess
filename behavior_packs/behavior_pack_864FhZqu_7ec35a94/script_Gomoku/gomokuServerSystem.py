# -*- coding: utf-8 -*-
import math
import random
import time

import mod.server.extraServerApi as serverApi
import config
import messageConfig
from mod_log import logger
from coroutineMgrGas import CoroutineMgr
from modCommon.gomokuCore.board import (
	GomokuBoard, PlaceResult,
	EMPTY, BLACK, WHITE,
	STATE_PLAYING, STATE_WON, STATE_DRAW,
)

ServerSystem = serverApi.GetServerSystemCls()

# 金棋子（万能挡子）在引擎中的棋子值：引擎只认BLACK/WHITE参与胜负，
# 第三方值占用格子且不与黑白匹配，天然阻断连线（见PlaceInEngine）。
GOMOKU_GOLD = 3


class GomokuServerSystem(ServerSystem):
	"""五子棋主系统（服务端权威）：棋盘铺设 / 刷资源 / 采集 / 落子

	棋局逻辑（占用/终局/五连/平局）委托给 modCommon.gomokuCore.GomokuBoard：
	主盘（随机形状，中心完整、越靠边缘缺格概率越大，每局重新生成，见GenerateBoardCells）
	与便携棋盘铺的扩展格共用一张大网格引擎（EngineGridSize，以主盘
	中心为正中心），扩展格上的子与主盘的子互相连线、统一判五连。
	本系统只负责 MC 侧——方块事件、物品消耗、命令放块、跨Mod播报。
	引擎坐标 (x=列, y=行)：x = 世界X - 网格西边缘X，y = 世界Z - 网格北边缘Z
	（见WorldToGrid）；可落子的格子 = 主盘本局存在的格子（boardCells，随机形状）
	+ extensionCells扩展格。

	核心交互：
	1. 手持棋子物品右键棋盘基座 -> 落子（颜色=落子方队伍，消耗棋子）
	2. 左键挖棋子矿 -> 采集（需对应镐，走ServerPlayerTryDestroyBlockEvent；镐耐久1采一次即碎；金矿徒手可挖）
	3. 手持处决剑攻击玩家 -> 一击必杀（剑用一次即碎）
	4. 背包规则：新一局开始清空全体背包；棋子携带上限MaxCarriedPieces个（道具不限），
	   超限时拦截拾取（ServerPlayerTryTouchEvent）并取消挖矿（矿留原地、镐不消耗）
	5. 阵亡：WorldMod的immediate_respawn规则关闭原版死亡界面，阵亡者自动重生（引擎复活点
	   被设到棋盘外沿，见SetEngineRespawnPoint——世界出生点在未加载区块，重生会卡死）；
	   重生后行动封锁DeathRespawnHoldSeconds秒（每秒聊天框倒计时，期间免疫伤害/
	   拦截一切交互），时间到自动恢复——见"阵亡与复活"一节
	6. 手持便携棋盘右键棋盘平面或低一层的地面 -> 铺一格1x1棋盘格（与主盘同平面、
	   CellPlaceMaxRadius范围内、不与本局存在的主盘格/已有扩展格重叠——主盘天然
	   缺格里可以补铺，需加入队伍）；
	   每铺一格耐久-1，用完销毁——见HandleCellPlace。扩展格与主盘共用引擎网格，
	   任意格子上连成五子都获胜，全部格子下满才平局

	棋盘位置：主盘以 config.BoardCenter 为中心（唯一事实来源，编辑器里移动棋盘=改这个常量），
	基座 /fill 会覆盖掉Anchor方块本身；资源环（矿/镐/剑）以该中心为圆心按config.SpawnConfigList
	刷新，高度与棋子同一水平面。
	"""

	def __init__(self, namespace, systemName):
		ServerSystem.__init__(self, namespace, systemName)
		self.levelId = serverApi.GetLevelId()
		# 引擎网格：主盘9x9 + 便携棋盘扩展格共用一张大网格（EngineGridSize×EngineGridSize，
		# 以主盘中心为正中心；乱斗模式不强制轮流落子，黑白双方均可随时落子）。
		# 引擎只管落子/五连，"哪些格子可落子"由本层管：主盘81格 + extensionCells扩展格
		self.board = GomokuBoard(config.EngineGridSize, config.EngineGridSize, enforce_turn=False)
		# 便携棋盘铺的扩展格（世界列坐标集合 {(x,z),...}），回合重置时整体拆除
		self.extensionCells = set()
		# 棋盘中心（config.BoardCenter），首次使用时从config取
		self.boardCenter = None
		self.boardBuilt = False
		# 本局主盘实际存在的格子（世界列坐标 {(x,z),...}）：随机化开启时棋盘不再
		# 必然满盘——中心完整、越靠边缘缺格概率越大，每局重新生成（见GenerateBoardCells）。
		# 缺格没有基座方块、无法直接落子，但可被便携棋盘补铺成扩展格（见HandleCellPlace）
		self.boardCells = set()
		self.spawnCoroutines = []
		self.debugPlaceCount = 0
		# 资源存量计数（维持总量，上限见config.SpawnMaxCountDict）：
		#   oreCountDict: 矿名 -> 现存方块数（重扫协程维护 + 刷出+1/挖碎-1 实时加减）
		#   itemExpireDict: 物品名 -> [到期时刻...]（自维护物品"在场"计数——
		#   地上的/背包里未使用的都算在场；用掉立刻释放空位（OnItemConsumed），
		#   到期未使用的按掉落物5分钟自然消失释放，见CountItemEntities）
		self.oreCountDict = {}
		self.itemExpireDict = {}
		self.recountCoroutine = None
		# 陷阱棋子的雷区登记：{(bx, by) 引擎坐标}。落在这些格子上的棋石被挖毁时引爆
		# （只炸玩家不毁棋盘，见DetonateTrap）；外观与普通棋石零差别，雷只存在这里
		self.trapCells = set()
		# 节流播报的上次播报时刻（按(玩家,类型)键，防刷屏）
		self.announceThrottleTime = {}
		# 换位符去重：playerId -> 上次触发时刻（time.time()秒）。换位符有两条入口
		# （指方块右键走ServerItemUseOnEvent、对空气右键走ServerItemTryUseEvent），
		# 同一次点击两个事件可能都到——1秒内只生效一次
		self.swapTriggerTime = {}
		# 转移符护盾登记：{playerId}。激活后下一次受到的真实伤害不落在自己身上，
		# 全额转给最近的敌方玩家（见OnDamage）；触发即失效，新一局开始清空；
		# 与换位符同款双入口（UseOn/TryUse），transferUseTime去重
		self.transferShieldSet = set()
		self.transferUseTime = {}
		# 加速药水登记：speedPotionUseTime右键去重（UseOn/TryUse双入口）；
		# speedPotionBaseDict记录提速前的基础速度（到期恢复/续喝不叠加的基准），
		# speedPotionCoroutineDict持有到期协程（新一瓶顶掉旧的=只重置计时）
		self.speedPotionUseTime = {}
		self.speedPotionBaseDict = {}
		self.speedPotionCoroutineDict = {}
		# 眩晕锤的眩晕登记：playerId -> 眩晕解禁时刻（time.time()秒）。眩晕期间
		# 拦截拾取（见OnPlayerTryTouch）——道具被锤落在脚下，不拦着会原地秒捡回去；
		# 移速锁死等表现由原版效果承担（见HandleDizzyHammerHit），不在这里做
		self.dizzyStunUntilDict = {}
		# 混乱药水的混乱登记：playerId -> 混乱解禁时刻（time.time()秒）。期间客户端
		# 反向其移动输入（W<->S、A<->D，见gomokuClientSystem），全屏表现用原版
		# 反胃（零伤害，无需在OnDamage拦截）。方案演变见HandleChaosPotionHit注释
		self.chaosUntilDict = {}
		# 时间停止的冻结登记：playerId -> 解冻时刻（time.time()秒）。期间该玩家的
		# 挖掘/落子/道具/攻击/拾取全部在服务端拦截（见各事件入口的IsTimestopFrozen），
		# 移动/跳跃/攻击输入由其客户端关闭（TimestopFreezeEvent，见gomokuClientSystem）；
		# timestopUseTime是UseOn/TryUse双入口的1秒去重（同换位符）
		self.timestopFreezeUntilDict = {}
		self.timestopUseTime = {}
		# 说明书打开去重（同双入口问题，见RequestOpenManual）
		self.manualOpenTime = {}
		# 吞噬黑洞右键去重（UseOn/TryUse双入口，与换位符/转移符同款问题）
		self.blackholeUseTime = {}
		# 便携棋盘右键去重（UseOn按住右键会连发使用事件，失败播报会刷屏，
		# 1秒内只处理一次；单入口，无UseOn/TryUse双发问题）
		self.boardPlaceUseTime = {}
		# 阵亡冷却：playerId -> 解禁时刻（time.time()秒）。WorldMod的immediate_respawn规则
		# 使阵亡者不弹原版死亡界面、自动在队伍复活点（棋盘附近）重生；这里封锁其行动到解禁
		# （时长=config.DeathRespawnHoldSeconds，倒计时见RespawnCountdown）
		self.respawnHoldUntilDict = {}
		# 在线玩家集合（OnPlayerAdd/OnDelServerPlayer维护；开局重设全体复活点用）
		self.playerIds = set()
		self.loggedBlockUseEvent = False
		self.loggedItemUseOnEvent = False
		self.loggedCarriedItem = False
		self.loggedTryDestroyEvent = False
		self.ListenEvent()

	def ListenEvent(self):
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
			config.ScriptTickServerEvent, self, self.OnTickServer)
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
			config.AddServerPlayerEvent, self, self.OnPlayerAdd)
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
			config.ServerBlockUseEvent, self, self.OnBlockUse)
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
			config.ServerItemUseOnEvent, self, self.OnItemUseOn)
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
			config.ServerItemTryUseEvent, self, self.OnItemTryUse)
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
			config.ServerPlayerTryDestroyBlockEvent, self, self.OnPlayerTryDestroyBlock)
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
			config.PlayerAttackEntityEvent, self, self.OnPlayerAttack)
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
			config.ServerPlayerTryTouchEvent, self, self.OnPlayerTryTouch)
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
			config.PlayerDieEvent, self, self.OnPlayerDie)
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
			config.DelServerPlayerEvent, self, self.OnDelServerPlayer)
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
			config.DamageEvent, self, self.OnDamage)
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
			config.ServerChatEvent, self, self.OnServerChat)
		self.ListenForEvent(config.StartLogicModName, config.StartLogicServerSystemName,
			config.StartLogicEvent, self, self.OnRoundStart)

	def UnListenEvent(self):
		self.UnDefineEvent(config.GomokuGameResultEvent)
		self.UnListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
			config.ScriptTickServerEvent, self, self.OnTickServer)
		self.UnListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
			config.AddServerPlayerEvent, self, self.OnPlayerAdd)
		self.UnListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
			config.ServerBlockUseEvent, self, self.OnBlockUse)
		self.UnListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
			config.ServerItemUseOnEvent, self, self.OnItemUseOn)
		self.UnListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
			config.ServerItemTryUseEvent, self, self.OnItemTryUse)
		self.UnListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
			config.ServerPlayerTryDestroyBlockEvent, self, self.OnPlayerTryDestroyBlock)
		self.UnListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
			config.PlayerAttackEntityEvent, self, self.OnPlayerAttack)
		self.UnListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
			config.ServerPlayerTryTouchEvent, self, self.OnPlayerTryTouch)
		self.UnListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
			config.PlayerDieEvent, self, self.OnPlayerDie)
		self.UnListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
			config.DelServerPlayerEvent, self, self.OnDelServerPlayer)
		self.UnListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
			config.DamageEvent, self, self.OnDamage)
		self.UnListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
			config.ServerChatEvent, self, self.OnServerChat)
		self.UnListenForEvent(config.StartLogicModName, config.StartLogicServerSystemName,
			config.StartLogicEvent, self, self.OnRoundStart)

	def OnTickServer(self):
		CoroutineMgr.Tick()

	# ---------- 生命周期 ----------

	def OnPlayerAdd(self, args):
		playerId = args.get("id", "-1")
		if playerId == "-1":
			return
		self.playerIds.add(playerId)
		# 无床玩家默认按世界出生点重生，本图出生点在远处未加载区块，重生会卡死
		# 在"正在重生"——进服就把复活点改设到棋盘外沿（见SetEngineRespawnPoint）
		self.SetEngineRespawnPoint(playerId)
		# 说明书等待阶段就发：进服即得（延迟1秒，进服事件时背包组件未必就绪）
		CoroutineMgr.StartCoroutine(self.DelayGiveManual(playerId))
		if not self.boardBuilt:
			# 等待阶段就尝试铺盘；组件/世界可能未就绪，延迟1秒（避初始化竞态）
			CoroutineMgr.StartCoroutine(self.DelayBuildBoard())

	def DelayGiveManual(self, playerId):
		"""进服发说明书（等待阶段就能翻阅）；重连/重复进服时背包已有则不重复发"""
		yield -30
		if playerId in self.playerIds and not self.PlayerHasItem(playerId, config.ManualItemName):
			self.GiveItemToPlayer(playerId, config.ManualItemName)

	def DelayBuildBoard(self):
		yield -config.BoardBuildDelaySeconds * 30
		if not self.boardBuilt:
			self.BuildBoard()

	def OnRoundStart(self, args):
		"""新一轮开始：确保棋盘已铺（等待期失败在此重试），清盘并启动资源刷新"""
		logger.info("[Gomoku] 新一轮开始，重置棋盘")
		# 清空上一局玩家的背包（棋子/道具不留到下一局；keepInventory存档下尤其必要）
		if config.ClearInventoryOnRoundStart:
			self.RunCommand('/clear @a')
			self.Msg('game_start')
		# /clear会把进服发的说明书一并清掉——清完补发（对局中随时能翻书；
		# 发放在等待阶段就做过，见DelayGiveManual，这里只是补回被清空的那本）
		for playerId in self.playerIds:
			self.GiveItemToPlayer(playerId, config.ManualItemName)
		self.announceThrottleTime = {}
		self.respawnHoldUntilDict = {}  # 上一局残留的阵亡冷却不带到下一局
		self.transferShieldSet = set()  # 转移符护盾不跨局（道具都回收了，护盾跟着作废）
		self.ClearAllSpeedBoosts()  # 加速药水效果同理不跨局：全体恢复原速
		self.dizzyStunUntilDict = {}  # 眩晕锤的眩晕同理不跨局
		self.ClearAllChaosEffects()  # 混乱药水的混乱同理不跨局：清登记+通知客户端停手
		self.ClearAllTimestopFreeze()  # 时间停止的冻结同理不跨局：清登记+通知客户端解冻
		# 开局重设一遍全体复活点（进服时设过；对局中入队的玩家兜底）
		for playerId in self.playerIds:
			self.SetEngineRespawnPoint(playerId)
		if not self.boardBuilt:
			self.BuildBoard()
		if self.boardBuilt:
			# 重铺基座层：先整层重铺修复上一局被破盘镐拆掉的格子（/fill默认replace，
			# 对完好的基座无副作用；棋盘上方棋石的清理由ResetBoard负责），再按
			# 新一局的随机形状重新挖缺——每局棋盘形状都不一样（见GenerateBoardCells）
			x1, y1, z1, x2, y2, z2 = self.GetBoardBounds()
			self.RunCommand('/fill {} {} {} {} {} {} {}'.format(x1, y1, z1, x2, y2, z2, config.ChessBaseBlockName))
			self.GenerateBoardCells()
			self.ResetBoard()
			self.CarveBoardHoles()
		# 回合开始时StartLogic会清掉全部掉落物（/kill @e[type=item]），自维护计数同步清零
		self.itemExpireDict = {}
		if not self.spawnCoroutines:
			self.StartSpawners()

	# ---------- 棋盘定位与铺设 ----------

	def EnsureBoardCenter(self):
		"""解析棋盘中心：config.BoardCenter 唯一事实来源（移动棋盘=改config）"""
		if self.boardCenter is None:
			self.boardCenter = config.BoardCenter
			logger.info("[Gomoku] 棋盘中心: {}".format(self.boardCenter))
		return self.boardCenter

	def GetBoardBounds(self):
		"""主盘基座层的 (x1, y, z1, x2, y, z2)"""
		cx, cy, cz = self.EnsureBoardCenter()
		half = config.BoardSize // 2
		return (cx - half, cy, cz - half, cx + half, cy, cz + half)

	def BuildBoard(self):
		"""以Anchor为中心铺设主盘基座（基座 /fill 覆盖掉Anchor方块本身），并清空上方旧棋石。
		先铺满 BoardSize x BoardSize 整层，再按随机形状挖缺格（见GenerateBoardCells）。
		先用tickingarea常驻加载棋盘区域，保证等待阶段（无玩家在附近）也能铺设。
		返回是否铺设成功。"""
		cx, cy, cz = self.EnsureBoardCenter()
		self.RunCommand('/tickingarea circle {} {} {} {}'.format(cx, cz, config.TickingAreaRadius, config.TickingAreaName))
		x1, y1, z1, x2, y2, z2 = self.GetBoardBounds()
		result = self.RunCommand('/fill {} {} {} {} {} {} {}'.format(x1, y1, z1, x2, y2, z2, config.ChessBaseBlockName))
		if not result:
			logger.warning("[Gomoku] 棋盘铺设命令执行失败，开局时将重试")
			return False
		self.boardBuilt = True
		self.GenerateBoardCells()
		self.CarveBoardHoles()
		logger.info("[Gomoku] 棋盘已铺设: {} ~ {}".format((x1, y1, z1), (x2, y2, z2)))
		self.ResetBoard()
		return True

	def GenerateBoardCells(self):
		"""生成本局主盘形状：中心不动，越靠边缘缺格概率越大（不是完全随机）。
		环距 ring = 格到中心的切比雪夫距离（0=中心格，half=最外环）：
		  ring <= BoardCenterKeepRadius 的环永远完整；之外的环缺格概率 =
		  BoardEdgeRemoveChance * (ring/half) ** BoardRemoveFalloff。
		结果存入boardCells（世界列坐标集合）；随机化关闭=满盘不缺格"""
		cx, cy, cz = self.EnsureBoardCenter()
		half = config.BoardSize // 2
		if not config.RandomizeBoard:
			self.boardCells = {(x, z)
				for x in range(cx - half, cx + half + 1)
				for z in range(cz - half, cz + half + 1)}
			return
		cells = set()
		for x in range(cx - half, cx + half + 1):
			for z in range(cz - half, cz + half + 1):
				ring = max(abs(x - cx), abs(z - cz))
				if ring <= config.BoardCenterKeepRadius:
					cells.add((x, z))
					continue
				removeChance = config.BoardEdgeRemoveChance \
					* (float(ring) / half) ** config.BoardRemoveFalloff
				if random.random() >= removeChance:
					cells.add((x, z))
		self.boardCells = cells
		total = config.BoardSize * config.BoardSize
		logger.info("[Gomoku] 本局棋盘形状已生成: {}/{}格 (缺{}格)".format(
			len(cells), total, total - len(cells)))

	def CarveBoardHoles(self):
		"""按boardCells把缺格挖成空气：调用前须刚/fill铺满过整层基座（本方法只挖不铺，
		不管上一局的残格）。逐行把连续缺格段合并成一条/fill air，减少命令数"""
		total = config.BoardSize * config.BoardSize
		if len(self.boardCells) == total:
			return  # 满盘（随机化关闭/本局一格没缺），无需挖
		x1, y1, z1, x2, y2, z2 = self.GetBoardBounds()
		for z in range(z1, z2 + 1):
			runStart = None
			for x in range(x1, x2 + 2):
				missing = x <= x2 and (x, z) not in self.boardCells
				if missing and runStart is None:
					runStart = x
				elif not missing and runStart is not None:
					self.RunCommand('/fill {} {} {} {} {} {} air 0 replace'.format(
						runStart, y1, z, x - 1, y1, z))
					runStart = None

	def ResetBoard(self):
		"""回合重置：主盘清上方棋石并重置引擎；便携棋盘铺的扩展格整体拆除
		（基座+上方棋子一起清掉）——被基座覆盖的原地形无法恢复，
		扩展格不跨局保留，下局玩家重新铺"""
		x1, y1, z1, x2, y2, z2 = self.GetBoardBounds()
		self.RunCommand('/fill {} {} {} {} {} {} air 0 replace'.format(x1, y1 + 1, z1, x2, y1 + 1, z2))
		if self.extensionCells:
			for (x, z) in list(self.extensionCells):
				if (x, z) in self.boardCells:
					# 扩展格可能铺在上一局的缺格上、而该列恰是新一局的主盘格：
					# 拆扩展格须把基座补回（OnRoundStart先整层fill后拆，不补则该格
					# "有名无实"——在boardCells里却没有基座方块，无法右键落子）
					self.RunCommand('/setblock {} {} {} {}'.format(x, y1, z, config.ChessBaseBlockName))
				else:
					self.RunCommand('/setblock {} {} {} air'.format(x, y1, z))
				self.RunCommand('/setblock {} {} {} air'.format(x, y1 + 1, z))
			logger.info("[Gomoku] 扩展格拆除: {}格".format(len(self.extensionCells)))
			self.extensionCells = set()
		self.board.reset(config.EngineGridSize, config.EngineGridSize, enforce_turn=False)
		# 棋盘清空，上一局埋的陷阱全部作废（雷跟着棋局走，不跨局残留）
		self.trapCells = set()

	def IsOnBoard(self, pos):
		"""pos在主盘基座层且该格本局存在（随机形状下边缘可能有缺格，缺格不算在盘上）"""
		x1, y1, z1, x2, y2, z2 = self.GetBoardBounds()
		return x1 <= pos[0] <= x2 and z1 <= pos[2] <= z2 and pos[1] == y1 \
			and (pos[0], pos[2]) in self.boardCells

	def IsPlayableCell(self, pos):
		"""pos是可落子的格子：主盘基座 或 便携棋盘铺的扩展格（基座层同一平面）"""
		if self.IsOnBoard(pos):
			return True
		return pos[1] == self.GetBoardBounds()[1] and (pos[0], pos[2]) in self.extensionCells

	def IsPlayableGridCell(self, gx, gy):
		"""引擎坐标(gx,gy)是否为可落子格：主盘中央BoardSize见方内本局存在的格子
		（随机形状的缺格不可落子——除非上面补铺了扩展格，见HandleCellPlace）或
		便携棋盘扩展格。引擎网格99x99远大于实际可落子区，判断不能只看in_bounds
		（方阵棋子的2x2过滤用这里，否则会把棋子铺到没有基座的空网格上）"""
		r = config.EngineGridSize // 2
		h = config.BoardSize // 2
		cx, cy, cz = self.EnsureBoardCenter()
		col = (gx + (cx - r), gy + (cz - r))
		if r - h <= gx <= r + h and r - h <= gy <= r + h:
			# 中央见方内：本局存在的格子 或 补在缺格上的扩展格（缺格补铺后也有基座可落子）
			return col in self.boardCells or col in self.extensionCells
		return col in self.extensionCells

	def IsStoneSlot(self, pos):
		"""pos在落子层（棋石所在高度=基座层+1；主盘与扩展格同判定）"""
		if pos[1] != self.GetBoardBounds()[1] + 1:
			return False
		x1, y1, z1, x2, y2, z2 = self.GetBoardBounds()
		if x1 <= pos[0] <= x2 and z1 <= pos[2] <= z2:
			return True
		return (pos[0], pos[2]) in self.extensionCells

	def IsBoardColumn(self, x, z):
		"""世界列(x,z)属于主盘或任一扩展格（雷管摆放等"点在棋盘上"的判定）"""
		x1, y1, z1, x2, y2, z2 = self.GetBoardBounds()
		if x1 <= x <= x2 and z1 <= z <= z2:
			return True
		return (x, z) in self.extensionCells

	def IsChessBaseBlock(self, blockName):
		"""blockName是否为棋盘基座。基座标识符是全项目唯一带大写的方块名
		（wihzo:McChess_ChessBase），而引擎返回的方块名一律小写（实测
		GetBlockNew/事件fullName返回wihzo:mcchess_chessbase）——裸字符串比较会
		漏判，这里忽略大小写比较。其余方块标识符均为全小写，不受影响"""
		return isinstance(blockName, basestring) and blockName.lower() == config.ChessBaseBlockName.lower()

	def WorldToGrid(self, pos):
		"""世界坐标 -> 引擎坐标 (x=列, y=行)。引擎网格以主盘中心为正中心的
		EngineGridSize大方格，扩展格/主盘格都平移映射进来"""
		cx, cy, cz = self.EnsureBoardCenter()
		r = config.EngineGridSize // 2
		return pos[0] - (cx - r), pos[2] - (cz - r)

	def GridToWorld(self, gx, gy):
		"""引擎坐标 -> 棋石世界坐标（棋盘平面上方一格）"""
		cx, cy, cz = self.EnsureBoardCenter()
		r = config.EngineGridSize // 2
		return (cx - r + gx, cy + 1, cz - r + gy)

	# ---------- 资源刷新 ----------

	def StartSpawners(self):
		for spawnConfig in config.SpawnConfigList:
			coroutineIter = CoroutineMgr.StartCoroutine(self.DelaySpawn(spawnConfig))
			self.spawnCoroutines.append(coroutineIter)
		# 道具等级池刷新协程（镐/剑/墨水/雷管等，共用等级上限，见ItemTierDict）
		for tierKey, tierCfg in config.ItemTierDict.iteritems():
			coroutineIter = CoroutineMgr.StartCoroutine(self.DelayTierSpawn(tierKey, tierCfg))
			self.spawnCoroutines.append(coroutineIter)
		# 问号方块独立刷新协程（自己的半径/间隔/上限，见RandomBlockSpawnConfig）
		coroutineIter = CoroutineMgr.StartCoroutine(self.DelayRandomBlockSpawn())
		self.spawnCoroutines.append(coroutineIter)
		# 矿石存量重扫协程（只启动一次，跨回合常驻）：开局立即全环数一遍（兼容存档残留的矿），
		# 此后按RecountIntervalSeconds周期重扫修正实时计数的误差
		if self.recountCoroutine is None:
			self.recountCoroutine = CoroutineMgr.StartCoroutine(self.RecountOres())
		logger.info("[Gomoku] 资源刷新已启动，共{}个刷新点+{}个道具等级池+问号方块".format(
			len(config.SpawnConfigList), len(config.ItemTierDict)))

	def DelaySpawn(self, spawnConfig):
		while True:
			yield -spawnConfig['interval'] * 30
			self.SpawnAtRing(spawnConfig)

	def DelayTierSpawn(self, tierKey, tierCfg):
		while True:
			yield -tierCfg['interval'] * 30
			self.SpawnTierItem(tierKey, tierCfg)

	def DelayRandomBlockSpawn(self):
		cfg = config.RandomBlockSpawnConfig
		while True:
			yield -cfg['interval'] * 30
			self.SpawnRandomBlock()

	def SpawnRandomBlock(self):
		"""问号方块刷新（config.RandomBlockSpawnConfig，独立于SpawnConfigList/
		ItemTierDict自成一条协程）：以棋盘中心为圆心在配置环上取点贴地表放置；
		存量走矿石计数oreCountDict（maxCount上限维持总量，挖碎-1/刷出+1，
		周期重扫RecountOres顺带修正）；chance缺省必刷"""
		cfg = config.RandomBlockSpawnConfig
		blockName = config.RandomBlockName
		maxCount = cfg.get('maxCount')
		if maxCount is not None and self.oreCountDict.get(blockName, 0) >= maxCount:
			return  # 存量已满：不补，玩家采走后才会再刷
		if random.random() > cfg.get('chance', config.DefaultSpawnChance):
			return
		cx, cy, cz = self.EnsureBoardCenter()
		inner, outer = cfg['radius']
		angle = math.radians(random.uniform(0, 360))
		radius = random.uniform(inner, outer)
		x = int(cx + radius * math.sin(angle))
		z = int(cz + radius * math.cos(angle))
		surfaceY = self.FindSurfaceY(x, z)
		if surfaceY is None:
			return
		# 该点地表已是问号方块则跳过（避免叠块导致计数与世界不符，与矿石同款）
		try:
			blockInfoComp = serverApi.GetEngineCompFactory().CreateBlockInfo(config.MainDimensionId)
			topDict = blockInfoComp.GetBlockNew((x, surfaceY - 1, z), config.MainDimensionId)
			if topDict and topDict.get('name') == blockName:
				return
		except Exception:
			pass  # 查询失败不拦截刷新，靠重扫修正
		if self.RunCommand('/setblock {} {} {} {}'.format(x, surfaceY, z, blockName)):
			self.oreCountDict[blockName] = self.oreCountDict.get(blockName, 0) + 1
			logger.info("[Gomoku] 问号方块刷新: {} @ {} (存量{}/{})".format(
				blockName, (x, surfaceY, z), self.oreCountDict[blockName], maxCount))

	def SpawnTierItem(self, tierKey, tierCfg):
		"""等级道具刷新（config.ItemTierDict）：到点先查该等级全部道具的"在场"合计
		（TierMaxCountDict等级共用上限，用掉立刻释放空位），没满则掷chance、
		在池内等权随机抽一个道具，在该等级对应的环上取点生成。
		池内道具不设各自上限——道具种类越多只让池子越丰富，场上总量不变"""
		items = tierCfg['items']
		maxCount = config.TierMaxCountDict.get(tierKey)
		if maxCount is not None and sum(self.CountItemEntities(name) for name in items) >= maxCount:
			return  # 该等级在场已满：不补，用掉/到期释放空位后才会再刷
		if random.random() > tierCfg.get('chance', config.DefaultSpawnChance):
			return
		itemName = random.choice(items)
		cx, cy, cz = self.EnsureBoardCenter()
		inner, outer = tierCfg['radius']
		angle = math.radians(random.uniform(0, 360))
		radius = random.uniform(inner, outer)
		x = int(cx + radius * math.sin(angle))
		z = int(cz + radius * math.cos(angle))
		surfaceY = self.FindSurfaceY(x, z)
		if surfaceY is None:
			return
		spawnPos = (x, surfaceY + config.ItemSpawnHeightOffset, z)
		if self.SpawnItemEntity(itemName, config.DefaultSpawnCount, spawnPos):
			logger.info("[Gomoku] {}刷新: {} @ {} (等级存量{}/{})".format(
				tierCfg['name'], itemName, spawnPos,
				sum(self.CountItemEntities(name) for name in items), maxCount))

	def SpawnItemEntity(self, itemName, count, spawnPos):
		"""生成掉落物并登记自维护计数，返回是否成功（棋子直刷/等级道具池共用）。
		键名对照官方模板：自定义物品须用newItemName/newAuxValue（GodChef），
		itemName/auxValue只对原版物品可靠（BedWars全是原版物品）"""
		try:
			itemComp = serverApi.CreateComponent(self.levelId, config.Minecraft, config.ItemComponent)
			result = itemComp.SpawnItemToLevel(
				{"newItemName": itemName, "count": count, "newAuxValue": 0},
				config.MainDimensionId, spawnPos)
			if not result:
				# 回退itemName键再试（不同版本对两种键的支持度不一），仍失败则告警
				result = itemComp.SpawnItemToLevel(
					{"itemName": itemName, "count": count, "auxValue": 0},
					config.MainDimensionId, spawnPos)
			if not result:
				logger.warning("[Gomoku] 物品刷新失败: {} x{} @ {}".format(itemName, count, spawnPos))
				return False
			# 自维护计数：登记到期时刻（对齐掉落物5分钟自然消失，届时自动剔除）
			self.itemExpireDict.setdefault(itemName, []).append(
				time.time() + config.ItemDespawnSeconds)
			return True
		except Exception as e:
			logger.warning("[Gomoku] SpawnItemToLevel 失败: {}".format(e))
			return False

	def SpawnAtRing(self, spawnConfig):
		"""在以棋盘中心（Anchor）为圆心的环形区域内随机取一点刷新：
		先查存量上限（SpawnMaxCountDict，矿=现存方块数/物品=现存掉落物数，
		已有>=上限则跳过本次刷新，维持总量恒定），再按chance掷骰；
		矿石贴该点地表放置（随地形），物品生成在地表上方靠自身重力落地。
		两种类型每次刷新都打log（名称+坐标），便于在控制台核对生成情况"""
		cx, cy, cz = self.boardCenter
		inner, outer = spawnConfig['radius']
		angleMin, angleMax = spawnConfig.get('angleRange', (0, 360))
		angle = math.radians(random.uniform(angleMin, angleMax))
		radius = random.uniform(inner, outer)
		x = int(cx + radius * math.sin(angle))
		z = int(cz + radius * math.cos(angle))
		surfaceY = self.FindSurfaceY(x, z)
		if surfaceY is None:
			return
		if spawnConfig['type'] == 'ore':
			# 方块没有重力，直接贴地表放
			blockName = spawnConfig['blockName']
			maxCount = config.SpawnMaxCountDict.get(blockName)
			if maxCount is not None and self.oreCountDict.get(blockName, 0) >= maxCount:
				return  # 存量已满：不补，玩家采走后才会再刷
			# 该点地表已是同种矿则跳过（避免叠矿导致计数与世界不符）
			try:
				blockInfoComp = serverApi.GetEngineCompFactory().CreateBlockInfo(config.MainDimensionId)
				topDict = blockInfoComp.GetBlockNew((x, surfaceY - 1, z), config.MainDimensionId)
				if topDict and topDict.get('name') == blockName:
					return
			except Exception:
				pass  # 查询失败不拦截刷新，靠重扫修正
			if self.RunCommand('/setblock {} {} {} {}'.format(x, surfaceY, z, blockName)):
				self.oreCountDict[blockName] = self.oreCountDict.get(blockName, 0) + 1
				logger.info("[Gomoku] 矿石刷新: {} @ {} (存量{}/{})".format(
					blockName, (x, surfaceY, z), self.oreCountDict[blockName], maxCount))
		else:
			# 掉落物实体自带重力，悬空生成后自然坠落到地面；count可按条目覆盖，默认走config
			# （生成+登记的公共实现见SpawnItemEntity，等级道具池也走同一个）
			itemName = spawnConfig['itemName']
			count = spawnConfig.get('count', config.DefaultSpawnCount)
			maxCount = config.SpawnMaxCountDict.get(itemName)
			if maxCount is not None and self.CountItemEntities(itemName) >= maxCount:
				return  # 存量已满：不补，玩家捡走/掉落物消失后才会再刷
			# 概率掷骰：chance缺省DefaultSpawnChance=1.0必刷；如0.3=每次刷新时刻只有30%概率真的刷出
			if random.random() > spawnConfig.get('chance', config.DefaultSpawnChance):
				return
			spawnPos = (x, surfaceY + config.ItemSpawnHeightOffset, z)
			if self.SpawnItemEntity(itemName, count, spawnPos):
				logger.info("[Gomoku] 物品刷新: {} x{} @ {} (存量{}/{})".format(
					itemName, count, spawnPos, self.CountItemEntities(itemName), maxCount))

	def CountItemEntities(self, itemName):
		"""数某物品"当前在场（地上+背包里未使用）"的数量（自维护，不依赖引擎实体枚举）。
		总数维持按"使用"计：刷出时登记（见SpawnAtRing），用掉立刻释放（OnItemConsumed），
		到期未使用的按自然消失释放（原版掉落物5分钟消失，登记时对齐了到期时刻）。
		玩家捡走不放空位（东西还在世上）；唯一偏差：囤在背包里超过5分钟不用的，
		到期记录已被剔除，空位会提前释放（轻微多发，可忽略）"""
		now = time.time()
		expires = [t for t in self.itemExpireDict.get(itemName, []) if t > now]
		self.itemExpireDict[itemName] = expires
		return len(expires)

	def OnPlayerTryTouch(self, args):
		"""玩家即将捡起掉落物（ServerPlayerTryTouchEvent）：棋子携带已满则取消拾取，
		物品留在地上等别人来捡；镐/剑等道具不限制。取消后设置拾取cd，
		防止玩家站在物品上时每帧重触发本事件。阵亡冷却中一律不拾取
		（含道具——防止倒计时内跑回尸体把死亡掉落捡回来，冷却形同虚设）"""
		itemDict = args.get('itemDict') or {}
		playerId = args.get('playerId')
		if not playerId:
			return
		if self.IsRespawnHeld(playerId):
			args['cancel'] = True
			args['pickupDelay'] = config.FullPickupDelayFrames
			self.TellRespawnHeld(playerId)
			return
		if self.IsTimestopFrozen(playerId):
			# 时间停止中：一律不许捡——物品留在地上，时间到再捡
			args['cancel'] = True
			args['pickupDelay'] = config.FullPickupDelayFrames
			return
		if time.time() < self.dizzyStunUntilDict.get(playerId, 0):
			# 眩晕锤的眩晕中：一律不许捡（含道具）——缴械掉的物品留在地上等对手来抢
			args['cancel'] = True
			args['pickupDelay'] = config.FullPickupDelayFrames
			return
		if self.GetItemName(itemDict) not in config.PieceItemNameSet:
			return
		if self.CountCarriedPieces(playerId) + itemDict.get('count', 1) > config.MaxCarriedPieces:
			args['cancel'] = True
			args['pickupDelay'] = config.FullPickupDelayFrames
			self.MsgThrottled(playerId, 'pieceCap', 'piece_cap_pickup',
				count=config.MaxCarriedPieces)

	def IterRingColumns(self, cx, cz, inner, outer, angleMin, angleMax):
		"""枚举环形区域内的整数(x,z)列（角度约定与SpawnAtRing一致：0=北/+Z，顺时针）"""
		for x in range(cx - outer, cx + outer + 1):
			for z in range(cz - outer, cz + outer + 1):
				distSq = (x - cx) ** 2 + (z - cz) ** 2
				if distSq < inner * inner or distSq > outer * outer:
					continue
				if angleMax - angleMin < 360:
					angle = math.degrees(math.atan2(x - cx, z - cz)) % 360
					if not (angleMin <= angle <= angleMax):
						continue
				yield x, z

	def RecountOres(self):
		"""矿石存量全环重扫（分帧，每帧ScanColumnsPerTick列避免卡顿）：
		开局立即扫一遍（兼容存档里残留的矿），此后每RecountIntervalSeconds秒扫一遍，
		修正"刷出+1/挖碎-1"实时计数的误差（如爆炸毁矿/事件丢失）。
		同一种矿分布在多个环时逐环累加、扫完一环即生效。"""
		while True:
			blockInfoComp = serverApi.GetEngineCompFactory().CreateBlockInfo(config.MainDimensionId)
			if blockInfoComp is None:
				yield -config.RecountIntervalSeconds * 30
				continue
			cx, cy, cz = self.EnsureBoardCenter()
			passCounts = {}
			scanned = 0
			# 扫描表 = SpawnConfigList里的矿 + 问号方块环（独立刷新条目，合成ore形态一并扫）
			scanConfigs = [c for c in config.SpawnConfigList if c['type'] == 'ore']
			scanConfigs.append({'type': 'ore', 'blockName': config.RandomBlockName,
				'radius': config.RandomBlockSpawnConfig['radius'], 'angleRange': (0, 360)})
			for spawnConfig in scanConfigs:
				blockName = spawnConfig['blockName']
				inner, outer = spawnConfig['radius']
				angleMin, angleMax = spawnConfig.get('angleRange', (0, 360))
				count = 0
				for x, z in self.IterRingColumns(cx, cz, inner, outer, angleMin, angleMax):
					try:
						height = blockInfoComp.GetTopBlockHeight((x, z))
						if height is None:
							continue
						blockDict = blockInfoComp.GetBlockNew((x, height, z), config.MainDimensionId)
						if blockDict and blockDict.get('name') == blockName:
							count += 1
					except Exception:
						continue
					scanned += 1
					if scanned % config.ScanColumnsPerTick == 0:
						yield -1  # 分帧
				passCounts[blockName] = passCounts.get(blockName, 0) + count
				self.oreCountDict[blockName] = passCounts[blockName]
			# 物品存量顺带扫一遍打日志（矿石走实时计数+周期重扫，物品走即时扫描）
			itemNames = set(c['itemName'] for c in config.SpawnConfigList if c['type'] == 'item')
			for tierCfg in config.ItemTierDict.values():
				itemNames.update(tierCfg['items'])
			itemCounts = {name: self.CountItemEntities(name) for name in sorted(itemNames)}
			logger.info("[Gomoku] 存量重扫: 矿石{} 物品{}".format(self.oreCountDict, itemCounts))
			yield -config.RecountIntervalSeconds * 30

	def FindSurfaceY(self, x, z):
		"""取(x,z)处最高非空气方块的上表面高度（含树叶，矿石可能落在树顶）；
		API不可用时退回棋盘平面（基座层Y+偏移），无结果返回None跳过本次刷新"""
		try:
			blockInfoComp = serverApi.GetEngineCompFactory().CreateBlockInfo(config.MainDimensionId)
			height = blockInfoComp.GetTopBlockHeight((x, z))
			if height is not None:
				return height + 1
		except Exception as e:
			logger.warning("[Gomoku] GetTopBlockHeight 不可用，退回棋盘平面: {}".format(e))
			return self.boardCenter[1] + config.ResourceSpawnYOffset
		return None

	# ---------- 交互：落子 / 采集 ----------

	def OnBlockUse(self, args):
		"""右键方块入口：棋盘基座->落子（矿石采集走左键挖掘，见OnPlayerTryDestroyBlock）"""
		if not self.loggedBlockUseEvent:
			# 事件字段以文档为准（blockName/x/y/z/playerId），打印一次原始数据便于核对
			logger.info("[Gomoku] ServerBlockUseEvent raw: {}".format(args))
			self.loggedBlockUseEvent = True
		blockName = args.get('blockName', '')
		pos = (args.get('x'), args.get('y'), args.get('z'))
		playerId = args.get('playerId')
		if None in pos or playerId is None:
			logger.warning("[Gomoku] 方块使用事件字段异常: {}".format(args))
			return
		if self.IsRespawnHeld(playerId):
			self.TellRespawnHeld(playerId)
			return
		if self.IsTimestopFrozen(playerId):
			# 时间停止中：空手右键（含落子入口）一律拦截
			self.TellTimestopFrozen(playerId)
			return
		if self.IsChessBaseBlock(blockName):
			self.HandlePlace(playerId, pos)

	def OnItemUseOn(self, args):
		"""手持物品右键方块的入口（ServerItemUseOnEvent，字段对照官方模板：
		entityId/itemName/auxValue/x/y/z/face）：手持棋子右键棋盘基座 -> 落子。
		实测ServerBlockUseEvent只在空手右键时触发，手持物品须走本事件"""
		if not self.loggedItemUseOnEvent:
			logger.info("[Gomoku] ServerItemUseOnEvent raw: {}".format(args))
			self.loggedItemUseOnEvent = True
		itemName = args.get('itemName', '')
		playerId = args.get('entityId')
		pos = (args.get('x'), args.get('y'), args.get('z'))
		if None in pos or not playerId:
			logger.warning("[Gomoku] 物品使用事件字段异常: {}".format(args))
			return
		if self.IsTimestopFrozen(playerId):
			# 时间停止中：持物右键一律拦截，含说明书（与OnItemTryUse同款——冻结就是冻结，
			# 客户端已关点击输入，这里兜底防绕过）
			self.TellTimestopFrozen(playerId)
			return
		if itemName == config.ManualItemName:
			# 说明书：看教程不算行动，阵亡冷却中照样能翻书（对空气右键走OnItemTryUse，
			# 两条入口同一去处，去重见RequestOpenManual）
			self.RequestOpenManual(playerId)
			return
		if self.IsRespawnHeld(playerId):
			self.TellRespawnHeld(playerId)
			return
		# 只处理棋子/墨水/雷管/破盘镐/换位符/便携棋盘物品：石镐/铁镐/剑等右键无动作
		itemCfg = config.ItemTable.get(itemName)
		if not itemCfg:
			return
		itemType = itemCfg.get('type')
		if itemType == 'ink':
			# 手持墨水右键棋石 -> 转化为己方颜色（目标判定见HandleInkUse）
			self.HandleInkUse(playerId, pos)
			return
		if itemType == 'bomb':
			# 手持雷管右键棋盘（基座或棋石均可）-> 引爆清子（见HandleBombUse）
			self.HandleBombUse(playerId, pos)
			return
		if itemType == 'boardpick':
			# 手持破盘镐右键棋盘基座 -> 拆掉该格（见HandleBoardPickUse）
			self.HandleBoardPickUse(playerId, pos)
			return
		if itemType == 'swap':
			# 手持换位符右键方块 -> 与最近敌方玩家互换位置（对空气右键走OnItemTryUse，
			# 两条入口同一去处，去重见HandleSwapUse）
			self.HandleSwapUse(playerId)
			return
		if itemType == 'transfer':
			# 手持转移符右键 -> 激活伤害转移护盾（对空气右键走OnItemTryUse，
			# 两条入口同一去处，去重见HandleTransferUse）
			self.HandleTransferUse(playerId)
			return
		if itemType == 'speed':
			# 手持加速药水右键 -> 给自己提速（对空气右键走OnItemTryUse，
			# 两条入口同一去处，去重见HandleSpeedPotionUse）
			self.HandleSpeedPotionUse(playerId)
			return
		if itemType == 'blackhole':
			# 手持吞噬黑洞右键 -> 吞噬棋盘上全部棋子（对空气右键走OnItemTryUse，
			# 两条入口同一去处，去重见HandleBlackholeUse）
			self.HandleBlackholeUse(playerId)
			return
		if itemType == 'timestop':
			# 手持时间停止右键 -> 冻结除使用者外的全场玩家（对空气右键走OnItemTryUse，
			# 两条入口同一去处，去重见HandleTimestopUse）
			self.HandleTimestopUse(playerId)
			return
		if itemType == 'board':
			# 手持便携棋盘右键棋盘平面或低一层的地面 -> 铺一格1x1棋盘格（见HandleCellPlace）
			self.HandleCellPlace(playerId, pos)
			return
		if itemType != 'piece':
			return
		# 点击位置须是可落子的格子（主盘基座或扩展格的基座）
		if not self.IsPlayableCell(pos):
			return
		self.HandlePlace(playerId, pos)

	def OnItemTryUse(self, args):
		"""右键尝试使用物品的入口（ServerItemTryUseEvent，字段对照官方GodChef模板：
		playerId/itemDict/cancel，物品名取itemDict['newItemName']）。本事件不依赖
		方块目标——对空气右键也触发，接住换位符和说明书（其余物品须要方块坐标的
		交互都走OnItemUseOn，这里不做通用分派，也不cancel）"""
		playerId = args.get('playerId')
		itemName = (args.get('itemDict') or {}).get('newItemName')
		if not playerId or not itemName:
			logger.warning("[Gomoku] 物品尝试使用事件字段异常: {}".format(args))
			return
		if self.IsTimestopFrozen(playerId):
			# 时间停止中：对空气右键一律拦截（含说明书——冻结就是冻结，5秒后再翻）
			self.TellTimestopFrozen(playerId)
			return
		if itemName == config.ManualItemName:
			# 说明书：看教程不算行动，阵亡冷却中照样能翻书
			self.RequestOpenManual(playerId)
			return
		if itemName == config.SwapItemName:
			if self.IsRespawnHeld(playerId):
				self.TellRespawnHeld(playerId)
				return
			self.HandleSwapUse(playerId)
			return
		if itemName == config.AntiDamageItemName:
			# 转移符与换位符同款双入口：对空气右键只有本事件接得住（见OnItemUseOn注释）
			if self.IsRespawnHeld(playerId):
				self.TellRespawnHeld(playerId)
				return
			self.HandleTransferUse(playerId)
			return
		if itemName == config.SpeedPotionItemName:
			# 加速药水同款双入口：对空气右键只有本事件接得住（见OnItemUseOn注释）
			if self.IsRespawnHeld(playerId):
				self.TellRespawnHeld(playerId)
				return
			self.HandleSpeedPotionUse(playerId)
			return
		if itemName == config.BlackHoleItemName:
			# 吞噬黑洞同款双入口：对空气右键只有本事件接得住（见OnItemUseOn注释）
			if self.IsRespawnHeld(playerId):
				self.TellRespawnHeld(playerId)
				return
			self.HandleBlackholeUse(playerId)
			return
		if itemName == config.TimestopItemName:
			# 时间停止同款双入口：对空气右键只有本事件接得住（见OnItemUseOn注释）
			if self.IsRespawnHeld(playerId):
				self.TellRespawnHeld(playerId)
				return
			self.HandleTimestopUse(playerId)
			return
		# 其他物品的右键不在本事件处理（避免与OnItemUseOn双触发）

	def RequestOpenManual(self, playerId):
		"""通知该玩家的客户端打开说明书弹窗（ManualOpenEvent -> PushScreen，见gomokuClientSystem）。
		同一次右键OnItemUseOn/OnItemTryUse可能都到（同换位符的双入口问题）——
		1秒内只开一次，避免叠出两层窗口"""
		now = time.time()
		if now - self.manualOpenTime.get(playerId, 0) < 1.0:
			return
		self.manualOpenTime[playerId] = now
		data = self.CreateEventData()
		self.NotifyToClient(playerId, config.ManualOpenEvent, data)

	def HandlePlace(self, playerId, pos):
		"""手持棋子物品右键棋盘基座（主盘或扩展格）-> 落子（占用/终局校验与
		胜负判定委托给引擎；扩展格的子与主盘的子互相连线）"""
		carriedItem = self.GetCarriedItemName(playerId)
		side = self.GetPlayerSide(playerId)
		logger.info("[Gomoku] 落子请求: pos={} 手持={} 阵营={}".format(pos, carriedItem, side))
		if not self.IsPlayableCell(pos):
			# 原为静默return，加日志便于排查点击位置和棋盘范围不吻合的情况
			logger.warning("[Gomoku] 落子点不在棋盘上: {} (主盘范围 {})".format(pos, self.GetBoardBounds()))
			return
		if self.board.state != STATE_PLAYING:
			self.MsgThrottled(playerId, 'placeHint', 'game_over')
			return
		bx, by = self.WorldToGrid(pos)
		# 方阵棋子（2x2铺子）：占位规则不同（四格内部分合法即可落），走独立流程
		itemCfg = config.ItemTable.get(carriedItem)
		if itemCfg and itemCfg.get('square'):
			self.HandleSquarePlace(playerId, bx, by, side)
			return
		if self.board.get(bx, by) != EMPTY:
			self.MsgThrottled(playerId, 'placeHint', 'place_occupied')
			return
		if side is None:
			self.MsgThrottled(playerId, 'placeHint', 'place_need_team')
			return
		if config.DebugSoloAlternateSides:
			# 调试模式（config开关）：单人无法测双方，落子黑白交替；金棋子不受影响
			side = 'white' if self.debugPlaceCount % 2 == 0 else 'black'
			self.debugPlaceCount += 1
		if carriedItem is None:
			logger.warning("[Gomoku] 无法读取手持物品，落子中止")
			return
		itemCfg = config.ItemTable.get(carriedItem)
		if not itemCfg or itemCfg['type'] != 'piece':
			# 空手/持非棋子右键基座的引导提示（便携棋盘用完销毁后按住右键会连发
			# 空手使用事件），节流防刷屏
			self.MsgThrottled(playerId, 'placeHint', 'place_hold_piece')
			return
		# 消耗棋子，按队伍颜色落子（金棋子为万能挡子，不分颜色）；
		# 硬化棋子落成硬化棋石——外观与普通棋石同色，但挖掘耗时更长（destroy_time更大）
		if not self.ConsumeCarriedItem(playerId):
			return
		hardened = bool(itemCfg.get('hardened'))
		if itemCfg.get('wildcard'):
			stoneName = config.StoneGoldName
			player = GOMOKU_GOLD
		elif side == 'black':
			stoneName = config.StoneBlackHardenedName if hardened else config.StoneBlackName
			player = BLACK
		else:
			stoneName = config.StoneWhiteHardenedName if hardened else config.StoneWhiteName
			player = WHITE
		stonePos = self.GridToWorld(bx, by)
		self.RunCommand('/setblock {} {} {} {}'.format(stonePos[0], stonePos[1], stonePos[2], stoneName))
		result = self.PlaceInEngine(bx, by, player)
		logger.info("[Gomoku] 落子: {} {} {}".format(stonePos, player, carriedItem))
		if itemCfg.get('trap') and result.ok:
			# 陷阱棋子：落下的普通棋石外观无差别，雷只登记在trapCells（被挖毁时引爆）
			self.trapCells.add((bx, by))
			logger.info("[Gomoku] 陷阱已埋设: 引擎坐标{}".format((bx, by)))
		if result.state == STATE_WON:
			self.OnGameEnd(result.winning_player, result.winning_lines)
		else:
			self.CheckBoardFull()

	def HandleSquarePlace(self, playerId, bx, by, side):
		"""方阵棋子落子：以点击格为2x2左上角，向 +X/+Z 方向铺四枚己方普通棋子。
		越界或已占的格子忽略，只落合法格；四格全不合法则不消耗、播报原因。
		颜色=落子方队伍（与普通棋子一致），消耗一次即铺下全部合法格；
		中途成五/满盘立即结算，剩余格子不再落。方阵棋子占用MaxCarriedPieces一个名额"""
		if side is None:
			self.MsgThrottled(playerId, 'placeHint', 'place_need_team')
			return
		if config.DebugSoloAlternateSides:
			# 调试模式（config开关）：单人无法测双方，落子黑白交替
			side = 'white' if self.debugPlaceCount % 2 == 0 else 'black'
			self.debugPlaceCount += 1
		# 四个目标格（左上/右上/左下/右下），先按 可落子格+空格 过滤
		# （可落子格=主盘9x9或扩展格，见IsPlayableGridCell——引擎网格99x99，
		# 只看in_bounds会把棋子铺到没有基座的空网格上）
		legalCells = []
		for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
			cx, cy = bx + dx, by + dy
			if self.IsPlayableGridCell(cx, cy) and self.board.get(cx, cy) == EMPTY:
				legalCells.append((cx, cy))
		if not legalCells:
			self.MsgThrottled(playerId, 'placeHint', 'place_no_gap')
			return
		if not self.ConsumeCarriedItem(playerId):
			return
		if side == 'black':
			stoneName, player = config.StoneBlackName, BLACK
		else:
			stoneName, player = config.StoneWhiteName, WHITE
		placed = 0
		for cx, cy in legalCells:
			stonePos = self.GridToWorld(cx, cy)
			self.RunCommand('/setblock {} {} {} {}'.format(stonePos[0], stonePos[1], stonePos[2], stoneName))
			result = self.PlaceInEngine(cx, cy, player)
			if not result.ok:
				# 引擎拒收（正常已被前置过滤，竞态兜底）：撤掉刚放的方块
				self.RunCommand('/setblock {} {} {} air'.format(stonePos[0], stonePos[1], stonePos[2]))
				continue
			placed += 1
			logger.info("[Gomoku] 方阵落子: {} {}".format(stonePos, player))
			if result.state == STATE_WON:
				self.OnGameEnd(result.winning_player, result.winning_lines)
				break  # 对局已结束，剩余格子不再落（引擎也会拒绝）
			if result.state == STATE_DRAW:
				self.OnGameEnd(None, [])
				break
		if placed and self.board.state == STATE_PLAYING:
			self.Msg('place_burst_placed', count=placed)

	def PlaceInEngine(self, bx, by, player):
		"""落子写入引擎。金棋子用第三方棋子值占位（不与黑白匹配，天然阻断连线）；
		若金子恰好连成五，引擎会误判终局——用序列化快照恢复到进行中状态。"""
		if player != GOMOKU_GOLD:
			return self.board.place(bx, by, player)
		snapshot = self.board.serialize()
		result = self.board.place(bx, by, player)
		if result.state == STATE_WON:
			snapshot["stones"].append([bx, by, player])
			snapshot["history"].append([bx, by, player])
			self.board = GomokuBoard.deserialize(snapshot)
			result = PlaceResult(True, player=player, state=self.board.state)
		return result

	def CheckBoardFull(self):
		"""落子后查满盘（引擎网格远大于可落子区，引擎的is_full永不触发，平局在这判）：
		主盘本局存在的格子（boardCells，随机形状的缺格/破盘镐拆掉的格不算）全部占满
		-> 扩展格还有空就提示继续；主盘+扩展格全满 -> 平局结算"""
		y1 = self.GetBoardBounds()[1]
		for (x, z) in self.boardCells:
			gx, gy = self.WorldToGrid((x, y1, z))
			if self.board.get(gx, gy) == EMPTY:
				return  # 主盘还有空位，未满
		for (x, z) in self.extensionCells:
			gx, gy = self.WorldToGrid((x, y1, z))
			if self.board.get(gx, gy) == EMPTY:
				self.Msg('place_board_full_extend')
				return
		self.OnGameEnd(None, [])

	def HandleInkUse(self, playerId, pos):
		"""手持墨水右键棋盘上的棋石 -> 转化为己方颜色（墨水耐久1，用一次即碎）。
		只对敌方黑/白棋石生效：金棋子无阵营不可转化，己方棋石无需转化。
		硬化属性保留（墨水只换颜色不换材质）；引擎侧先删旧子再落新子（同格改值），
		转化补齐五连同 normal 落子一样判胜。陷阱雷跟着格子走：被转化的陷阱棋石
		换色后仍是陷阱，挖它照样炸（trapCells不因转化而清）"""
		if not self.IsStoneSlot(pos):
			return  # 点击的不是任何棋盘格的落子层（与HandleStoneBreak同判定）
		if self.board.state != STATE_PLAYING:
			self.MsgThrottled(playerId, 'inkHint', 'game_over')
			return
		side = self.GetPlayerSide(playerId)
		if side is None:
			self.MsgThrottled(playerId, 'inkHint', 'ink_need_team')
			return
		blockName = self.GetBlockName(pos)
		stoneSide = config.StoneSideDict.get(blockName) if blockName else None
		if stoneSide is None:
			return  # 落子层但不是棋石（正常不会有），静默忽略
		if stoneSide == 'gold':
			self.MsgThrottled(playerId, 'inkHint', 'ink_gold_immune')
			return
		if stoneSide == side:
			self.MsgThrottled(playerId, 'inkHint', 'ink_own_piece')
			return
		if not self.ConsumeCarriedItem(playerId):
			return
		# 己方棋石（敌方硬化棋石转化后保留硬化：挖掘更久的属性跟着格子走）
		hardened = blockName in (config.StoneBlackHardenedName, config.StoneWhiteHardenedName)
		if side == 'black':
			stoneName = config.StoneBlackHardenedName if hardened else config.StoneBlackName
			player = BLACK
		else:
			stoneName = config.StoneWhiteHardenedName if hardened else config.StoneWhiteName
			player = WHITE
		bx, by = self.WorldToGrid(pos)
		self.RunCommand('/setblock {} {} {} {}'.format(pos[0], pos[1], pos[2], stoneName))
		# 引擎同步：remove+place（remove失败=计数脱同步，place会自愈补上该格）
		self.board.remove(bx, by)
		result = self.PlaceInEngine(bx, by, player)
		self.Msg('ink_converted', side=config.SideNameDict.get(stoneSide, stoneSide))
		logger.info("[Gomoku] 墨水转化: {} {} -> {} ({})".format(pos, blockName, stoneName, playerId))
		if result.state == STATE_WON:
			self.OnGameEnd(result.winning_player, result.winning_lines)

	def HandleBombUse(self, playerId, pos):
		"""手持爆炸雷管右键棋盘（基座或棋石均可）-> 像原生方块一样贴着点击处
		摆出一个已点燃的雷管方块（TNT外观），BombFuseSeconds秒后引爆（见BombFuse）。
		摆放不替换任何方块：点击列的落子层(y1+1)有棋石 -> 叠在棋石上方(y1+2)；
		空 -> 直接放在落子层。爆炸清以雷管方块为中心的立方体
		（BombBlastRange=3即3x3x3）内的全部棋石，不分敌我、不分颜色
		（金棋子照炸）；只清棋石，基座与地形无损（不留坑）。雷管耐久1"""
		y1 = self.GetBoardBounds()[1]
		if not (self.IsBoardColumn(pos[0], pos[2]) and pos[1] - y1 in (0, 1, 2)):
			return  # 点击目标不在主盘/扩展格上，不响应
		if self.board.state != STATE_PLAYING:
			self.MsgThrottled(playerId, 'bombHint', 'game_over')
			return
		# 摆放位置：优先落子层；该列落子层被棋石占着就叠上去（不替换）
		bombPos = (pos[0], y1 + 1, pos[2])
		if self.GetBlockName(bombPos) in config.StoneBlockNameSet:
			bombPos = (pos[0], y1 + 2, pos[2])
		if self.GetBlockName(bombPos) == config.DetonatorBlockName:
			self.MsgThrottled(playerId, 'bombHint', 'bomb_already_lit')
			return
		if not self.ConsumeCarriedItem(playerId):
			return
		self.RunCommand('/setblock {} {} {} {}'.format(bombPos[0], bombPos[1], bombPos[2], config.DetonatorBlockName))
		self.Msg('bomb_fuse_lit')
		logger.info("[Gomoku] 雷管已放置: {} 点击{} ({})".format(bombPos, pos, playerId))
		CoroutineMgr.StartCoroutine(self.BombFuse(bombPos))

	def BombFuse(self, bombPos):
		"""雷管引信协程：摆出方块后等BombFuseSeconds秒。到点时雷管方块仍在 ->
		引爆：清以雷管为中心的BombBlastRange立方体（3=3x3x3，各轴向±1）内
		的全部棋石+雷管自身，同步释放引擎格；方块没了 -> 被挖掉拆除/
		回合重置清除，静默取消。爆炸只删子不判胜（删子凑不成五连）"""
		yield -config.BombFuseSeconds * 30
		if self.GetBlockName(bombPos) != config.DetonatorBlockName:
			logger.info("[Gomoku] 雷管在引爆前被拆除/清除: {}".format(bombPos))
			return
		# 原生TNT爆炸表现（可配开关）：爆炸粒子+音效，纯特效不影响地形（清子逻辑在下面）
		if config.BombExplosionEffect:
			center = (bombPos[0] + 0.5, bombPos[1] + 0.5, bombPos[2] + 0.5)
			self.RunCommand('/particle minecraft:huge_explosion_emitter {} {} {}'.format(*center))
			self.RunCommand('/playsound random.explode @a {} {} {}'.format(*center))
		removed = 0
		seenNames = set()  # 诊断用：扫描到的方块名（炸空时打日志排查名字不匹配）
		half = config.BombBlastRange // 2
		for dx in range(-half, half + 1):
			for dz in range(-half, half + 1):
				for dy in range(-half, half + 1):
					cellPos = (bombPos[0] + dx, bombPos[1] + dy, bombPos[2] + dz)
					if cellPos == bombPos:
						continue  # 雷管自身最后单独清
					blockName = self.GetBlockName(cellPos)
					if blockName:
						seenNames.add(blockName)
					if blockName not in config.StoneBlockNameSet:
						continue  # 只清棋石：空格/基座/地形/异常查询都不动
					self.RunCommand('/setblock {} {} {} air'.format(*cellPos))
					# 引擎同步：这枚棋石属于主盘还是扩展格都能换算（爆炸范围可能跨到扩展格的棋石）
					if self.IsStoneSlot(cellPos):
						bx, by = self.WorldToGrid(cellPos)
						self.board.remove(bx, by)  # 超界/已空返回not ok，忽略即可
						self.trapCells.discard((bx, by))  # 被炸掉的陷阱棋石=远程拆除，不引爆（链式殉爆不做）
					removed += 1
		self.RunCommand('/setblock {} {} {} air'.format(*bombPos))
		if removed:
			self.Msg('bomb_exploded', count=removed)
		else:
			self.Msg('bomb_exploded_empty')
		logger.info("[Gomoku] 雷管引爆: {} 炸除{}枚 扫描到: {}".format(bombPos, removed, seenNames))

	def HandleBlackholeUse(self, playerId):
		"""吞噬黑洞：右键释放，吞噬棋盘上的全部棋子——不分敌我、不分颜色
		（金棋子照吞），主盘与便携棋盘扩展格上的都算。只清棋石：基座与扩展格
		本身无损，清完仍可继续落子；引擎整盘重置（引擎里只有棋子，reset=全部
		释放），陷阱雷随盘作废（被吞的陷阱棋石=被远程拆除，不引爆）。
		只从问号方块奖励池产出（RandomBlockPoolDict），不进常规刷新环。
		与换位符/转移符同款双入口（指方块右键走OnItemUseOn、对空气右键走
		OnItemTryUse），blackholeUseTime做1秒去重防同次点击双触发。
		耐久1，空盘释放同样消耗（与雷管"炸了个空"同款语义）"""
		now = time.time()
		if now - self.blackholeUseTime.get(playerId, 0) < 1.0:
			return
		self.blackholeUseTime[playerId] = now
		logger.info("[Gomoku] 吞噬黑洞右键: {} 手持={}".format(playerId, self.GetCarriedItemName(playerId)))
		if self.board.state != STATE_PLAYING:
			self.Msg('game_over')
			return
		# 先数棋子（引擎快照，含扩展格上的子）再清——播报用
		stoneCount = len(self.board.serialize().get("stones", []))
		if not self.ConsumeCarriedItem(playerId):
			return
		# 表现：棋盘中心爆炸粒子+音效（纯特效，与雷管引爆同款；地形无损）
		cx, cy, cz = self.EnsureBoardCenter()
		center = (cx + 0.5, cy + 1.5, cz + 0.5)
		self.RunCommand('/particle minecraft:huge_explosion_emitter {} {} {}'.format(*center))
		self.RunCommand('/playsound random.explode @a {} {} {}'.format(*center))
		# 清主盘落子层整层（范围清，破盘镐拆格后的浮空棋石一并带走；基座在下层不动）
		x1, y1, z1, x2, y2, z2 = self.GetBoardBounds()
		self.RunCommand('/fill {} {} {} {} {} {} air 0 replace'.format(x1, y1 + 1, z1, x2, y1 + 1, z2))
		# 清扩展格上方的棋石（基座保留，之后仍可在上面落子）
		for (x, z) in list(self.extensionCells):
			self.RunCommand('/setblock {} {} {} air'.format(x, y1 + 1, z))
		# 引擎整盘重置 + 陷阱雷作废（与ResetBoard同款重置，但不拆扩展格基座）
		self.board.reset(config.EngineGridSize, config.EngineGridSize, enforce_turn=False)
		self.trapCells = set()
		self.Msg('blackhole_opened', count=stoneCount)
		logger.info("[Gomoku] 吞噬黑洞: 清除{}枚棋子 ({})".format(stoneCount, playerId))

	def HandleBoardPickUse(self, playerId, pos):
		"""手持破盘镐右键棋盘基座 -> 拆掉该格基座：本局该格无法落子（没有基座方块可
		右键），格子里的浮空棋石不受影响；新一局开始时基座整层重铺，拆掉的格子自动修复
		（见OnRoundStart）。基座destroy_time=100000，左键长挖到不了挖穿事件，故走
		右键即拆（与墨水/雷管同一条ServerItemUseOnEvent通道——物品不带netease:weapon
		组件，带该组件的工具类物品右键不发使用事件，曾导致本道具右键无效）。
		只能拆基座——右键矿/棋石/地形/已拆的洞一律不响应也不消耗。
		耐久1，拆一次即碎"""
		blockName = self.GetBlockName(pos)
		onBoard = self.IsOnBoard(pos)
		logger.info("[Gomoku] 破盘镐右键: pos={} blockName={} onBoard={}".format(pos, blockName, onBoard))
		if not onBoard or not self.IsChessBaseBlock(blockName):
			# 不在棋盘/不是基座（矿/棋石/地形/已拆的洞）：节流提示，不响应不消耗。
			# 基座比较须忽略大小写：引擎返回wihzo:mcchess_chessbase（全小写），
			# 配置标识符带大写（wihzo:McChess_ChessBase），裸字符串比较会漏判
			self.MsgThrottled(playerId, 'boardPick', 'board_pick_wrong_target')
			return
		if self.board.state != STATE_PLAYING:
			self.MsgThrottled(playerId, 'boardPick', 'board_pick_no_game')
			return
		if not self.ConsumeCarriedItem(playerId):
			return
		self.RunCommand('/setblock {} {} {} air'.format(pos[0], pos[1], pos[2]))
		gx, gy = self.WorldToGrid(pos)
		if self.board.get(gx, gy) == EMPTY:
			# 该格没有浮空棋石：从本局形状里除名——满盘判定不再等这格
			# （它永远填不上了）；有浮空棋石的格保留（那格算已占用）
			self.boardCells.discard((pos[0], pos[2]))
		self.Msg('board_pick_removed')
		logger.info("[Gomoku] 破盘镐拆格: {} ({})".format(pos, playerId))

	def HandleSwapUse(self, playerId):
		"""换位符：与最近的敌方玩家互换位置。触发=手持时右键（单击即可）：
		准星指着方块走ServerItemUseOnEvent、对空气右键走ServerItemTryUseEvent，
		两条入口都到这里，swapTriggerTime去重（同一次点击可能两个事件都到）。
		目标=距离最近的不同阵营玩家（TeamMod缺失/本方无阵营时退化为任意其他玩家）；
		双方坐标先一起读、再一起写，任一侧传送失败则回滚，失败不消耗道具。
		SetPos行为与/tp一致（官方文档），双方都传送成功才用掉换位符"""
		now = time.time()
		if now - self.swapTriggerTime.get(playerId, 0) < 1.0:
			return  # 1秒内已触发过（UseOn与TryUse双事件去重，也防连点）
		self.swapTriggerTime[playerId] = now
		logger.info("[Gomoku] 换位符右键: {} 手持={}".format(playerId, self.GetCarriedItemName(playerId)))
		posCompFactory = serverApi.GetEngineCompFactory()
		myPosComp = posCompFactory.CreatePos(playerId)
		if not myPosComp:
			logger.warning("[Gomoku] 换位失败：创建pos组件失败 {}".format(playerId))
			return
		myPos = myPosComp.GetPos()
		if not myPos:
			self.Msg('swap_fail_no_pos')
			return
		mySide = self.GetPlayerSide(playerId)
		# 挑最近的换位目标：排除自己；排除队友（mySide为None时不过滤，退化处理）
		targetId, targetPos, bestDist = None, None, None
		for pid in serverApi.GetPlayerList():
			if pid == playerId:
				continue
			if mySide is not None and self.GetPlayerSide(pid) == mySide:
				continue
			otherPosComp = posCompFactory.CreatePos(pid)
			otherPos = otherPosComp.GetPos() if otherPosComp else None
			if not otherPos:
				continue
			dist = sum((otherPos[i] - myPos[i]) ** 2 for i in range(3))
			if bestDist is None or dist < bestDist:
				targetId, targetPos, bestDist = pid, otherPos, dist
		if targetId is None:
			self.Msg('swap_fail_no_target')
			return
		# 互换（文档注明在床上时SetPos返回False——任一侧失败都回滚，道具不消耗）
		okA = posCompFactory.CreatePos(playerId).SetPos(targetPos)
		okB = posCompFactory.CreatePos(targetId).SetPos(myPos)
		if not (okA and okB):
			if okA:
				posCompFactory.CreatePos(playerId).SetPos(myPos)  # 回滚：把先传送的人送回原位
			self.Msg('swap_fail_tp')
			logger.warning("[Gomoku] 换位SetPos失败: {}->{} okA={} okB={}".format(playerId, targetId, okA, okB))
			return
		if not self.ConsumeCarriedItem(playerId):
			logger.warning("[Gomoku] 换位成功但道具消耗失败: {}".format(playerId))
		self.Msg('swap_done',
			player=self.GetEntityName(playerId), target=self.GetEntityName(targetId))
		logger.info("[Gomoku] 换位: {} <-> {} (我方原位 {})".format(playerId, targetId, myPos))

	def GetEntityName(self, entityId):
		"""取玩家/生物显示名（播报用）；API异常时回退为实体id"""
		try:
			nameComp = serverApi.GetEngineCompFactory().CreateName(entityId)
			return nameComp.GetName() if nameComp else entityId
		except Exception as e:
			logger.warning("[Gomoku] GetName 失败: {}".format(e))
			return entityId

	def HandleTransferUse(self, playerId):
		"""转移符：右键激活护盾——下一次受到的真实伤害不落在自己身上，全额转给
		最近的敌方玩家（转移逻辑见OnDamage）。触发后护盾消失；护盾不跨局
		（OnRoundStart清空）。与换位符同款双入口（指方块右键走OnItemUseOn、
		对空气右键走OnItemTryUse），transferUseTime做1秒去重防同次点击双触发"""
		now = time.time()
		if now - self.transferUseTime.get(playerId, 0) < 1.0:
			return
		self.transferUseTime[playerId] = now
		logger.info("[Gomoku] 转移符右键: {} 手持={}".format(playerId, self.GetCarriedItemName(playerId)))
		if not self.ConsumeCarriedItem(playerId):
			return
		refreshed = playerId in self.transferShieldSet
		self.transferShieldSet.add(playerId)
		if refreshed:
			self.MsgPlayer(playerId, 'transfer_shield_refreshed')
		else:
			self.MsgPlayer(playerId, 'transfer_shield_active')

	def FindNearestEnemyPlayer(self, playerId):
		"""距playerId最近的不同阵营玩家（TeamMod缺失/本方无阵营时退化为任意其他玩家）；
		跳过阵亡冷却中的玩家（其伤害会被OnDamage清零，转给他们等于白转）；
		场上没有可选目标返回None。换位符的目标挑选同款规则"""
		posCompFactory = serverApi.GetEngineCompFactory()
		myPosComp = posCompFactory.CreatePos(playerId)
		myPos = myPosComp.GetPos() if myPosComp else None
		if not myPos:
			return None
		mySide = self.GetPlayerSide(playerId)
		targetId, bestDist = None, None
		for pid in serverApi.GetPlayerList():
			if pid == playerId or self.IsRespawnHeld(pid):
				continue
			if mySide is not None and self.GetPlayerSide(pid) == mySide:
				continue
			otherPosComp = posCompFactory.CreatePos(pid)
			otherPos = otherPosComp.GetPos() if otherPosComp else None
			if not otherPos:
				continue
			dist = sum((otherPos[i] - myPos[i]) ** 2 for i in range(3))
			if bestDist is None or dist < bestDist:
				targetId, bestDist = pid, dist
		return targetId

	# ---------- 加速药水 ----------

	def HandleSpeedPotionUse(self, playerId):
		"""加速药水：右键给自己提速——引擎移动速度(SPEED属性)在基础值上提升
		config.SpeedPotionPercent 百分比，持续 config.SpeedPotionDuration 秒后
		自动恢复原速（见SpeedBoostExpire）。与换位符/转移符同款双入口
		（指方块右键走OnItemUseOn、对空气右键走OnItemTryUse），speedPotionUseTime
		做1秒去重防同次点击双触发。连喝不叠加：提速幅度始终按第一次喝之前的
		基础值算，只把持续时间重置满（speedPotionCoroutineDict顶掉旧到期协程）"""
		now = time.time()
		if now - self.speedPotionUseTime.get(playerId, 0) < 1.0:
			return
		self.speedPotionUseTime[playerId] = now
		logger.info("[Gomoku] 加速药水右键: {} 手持={}".format(playerId, self.GetCarriedItemName(playerId)))
		attrComp = serverApi.GetEngineCompFactory().CreateAttr(playerId)
		if not attrComp:
			self.MsgPlayer(playerId, 'speed_potion_fail_retry')
			logger.warning("[Gomoku] 创建attr组件失败: {}".format(playerId))
			return
		attrType = serverApi.GetMinecraftEnum().AttrType.SPEED
		refreshed = playerId in self.speedPotionCoroutineDict
		if refreshed:
			# 上一瓶还没到期：沿用其基础值（不叠加），下面只重置计时
			baseValue = self.speedPotionBaseDict.get(playerId, attrComp.GetAttrValue(attrType))
		else:
			baseValue = attrComp.GetAttrValue(attrType)
		if not self.ConsumeCarriedItem(playerId):
			return
		if refreshed:
			CoroutineMgr.StopCoroutine(self.speedPotionCoroutineDict.pop(playerId))
		else:
			self.speedPotionBaseDict[playerId] = baseValue
		# 第3参0=只改当前值不改默认值——阵亡重生后引擎按默认值恢复原速，加速不跨命
		boostedValue = baseValue * (1.0 + config.SpeedPotionPercent / 100.0)
		if not attrComp.SetAttrValue(attrType, boostedValue, 0):
			self.MsgPlayer(playerId, 'speed_potion_fail')
			logger.warning("[Gomoku] SetAttrValue失败: {} base={}".format(playerId, baseValue))
			self.speedPotionBaseDict.pop(playerId, None)
			self.speedPotionCoroutineDict.pop(playerId, None)
			return
		self.speedPotionCoroutineDict[playerId] = CoroutineMgr.StartCoroutine(
			self.SpeedBoostExpire(playerId, baseValue))
		if refreshed:
			self.MsgPlayer(playerId, 'speed_potion_refreshed', seconds=config.SpeedPotionDuration)
		else:
			self.MsgPlayer(playerId, 'speed_potion_active',
				percent=config.SpeedPotionPercent, seconds=config.SpeedPotionDuration)
		logger.info("[Gomoku] 加速药水: {} {}->{} 持续{}秒".format(
			playerId, baseValue, boostedValue, config.SpeedPotionDuration))

	def SpeedBoostExpire(self, playerId, baseValue):
		"""加速药水到期：恢复基础速度。玩家可能已离线（组件创建失败只清登记，
		SendMessageToPlayer自带异常保护）。若期间玩家阵亡重生过，引擎已把速度重置
		回默认值，这里再写回baseValue通常等值无害"""
		yield config.SpeedPotionDuration
		self.speedPotionCoroutineDict.pop(playerId, None)
		self.speedPotionBaseDict.pop(playerId, None)
		attrComp = serverApi.GetEngineCompFactory().CreateAttr(playerId)
		if attrComp:
			attrComp.SetAttrValue(serverApi.GetMinecraftEnum().AttrType.SPEED, baseValue, 0)
		self.MsgPlayer(playerId, 'speed_potion_expired')
		logger.info("[Gomoku] 加速结束，速度已恢复: {}".format(playerId))

	def ClearAllSpeedBoosts(self):
		"""终止所有进行中的加速效果并恢复基础速度（新一局开始时调用：背包已清空、
		道具都作废，加速不该跨局）。玩家已离线时组件创建失败，只清登记"""
		for playerId, coroutine in self.speedPotionCoroutineDict.items():
			CoroutineMgr.StopCoroutine(coroutine)
			baseValue = self.speedPotionBaseDict.get(playerId)
			attrComp = serverApi.GetEngineCompFactory().CreateAttr(playerId)
			if baseValue is not None and attrComp:
				attrComp.SetAttrValue(serverApi.GetMinecraftEnum().AttrType.SPEED, baseValue, 0)
		self.speedPotionCoroutineDict = {}
		self.speedPotionBaseDict = {}

	# ---------- 便携棋盘：铺扩展格 ----------

	def HandleCellPlace(self, playerId, pos):
		"""手持便携棋盘右键方块 -> 在点击列铺一格1x1的棋盘格（基座方块，与主盘同平面），
		之后可像主盘一样在上面落子（扩展格的子与主盘的子互相连线、统一判五连）。
		主盘天然缺格里也可以铺：缺格本局没有基座，补上即成扩展格，与主盘互相连线。
		校验（不满足只提示、不铺也不扣耐久）：
		  1. 高度：点击的方块须是主盘基座层（棋盘平面）或低一层（贴地右键即可——
		     主盘基座本来就比自然地表高一格，新格子铺在基座层高度、正好坐在地面上）；
		  2. 点击列不是本局存在的主盘格（有基座能直接落子，铺了浪费）、也没铺过
		     扩展格（一格只能铺一次）；天然缺格放行；
		  3. 距主盘中心不超过CellPlaceMaxRadius（须在引擎网格与棋盘常驻加载区内）；
		  4. 目标格没有被矿/棋石/雷管/问号方块占着（避免铺格顶掉资源导致计数脱同步）；
		  5. 需已加入队伍（与落子一致）。
		按住右键UseOn会连发使用事件——boardPlaceUseTime做1秒去重，失败播报不刷屏。
		铺一格耐久-1（归零销毁，见DamageBoardItem）；回合重置时扩展格随主盘一起拆除"""
		y1 = self.GetBoardBounds()[1]
		now = time.time()
		if now - self.boardPlaceUseTime.get(playerId, 0) < 1.0:
			return  # 按住右键连发的使用事件，1秒内只处理一次（与换位符等同款去重）
		self.boardPlaceUseTime[playerId] = now
		if pos[1] not in (y1 - 1, y1):
			self.Msg('cell_fail_height')
			return
		if self.board.state != STATE_PLAYING:
			self.Msg('game_over')
			return
		if self.GetPlayerSide(playerId) is None:
			self.Msg('cell_need_team')
			return
		x, z = pos[0], pos[2]
		# 只拦本局存在的主盘格（boardCells里有基座可落子，铺了浪费）；天然缺格放行——
		# 补上基座后进extensionCells，与主盘的子互相连线（缺格=主盘见方内不在boardCells的列）
		if (x, z) in self.boardCells:
			self.Msg('cell_fail_on_board')
			return
		if (x, z) in self.extensionCells:
			self.Msg('cell_fail_duplicate')
			return
		cx, cy, cz = self.EnsureBoardCenter()
		if (x - cx) ** 2 + (z - cz) ** 2 > config.CellPlaceMaxRadius ** 2:
			self.Msg('cell_fail_too_far', radius=config.CellPlaceMaxRadius)
			return
		blockName = self.GetBlockName((x, y1, z))
		if blockName in config.StoneBlockNameSet or blockName in config.OrePieceItemDict \
				or blockName in (config.DetonatorBlockName, config.RandomBlockName):
			self.Msg('cell_fail_occupied')
			return
		if not self.RunCommand('/setblock {} {} {} {}'.format(x, y1, z, config.ChessBaseBlockName)):
			self.Msg('cell_fail_setblock')
			return
		self.extensionCells.add((x, z))
		logger.info("[Gomoku] 扩展格铺设: {} (场上共{}格) ({})".format(
			(x, y1, z), len(self.extensionCells), playerId))
		self.Msg('cell_placed')
		CoroutineMgr.StartCoroutine(self.DamageBoardItem(playerId))

	def DamageBoardItem(self, playerId):
		"""消耗一点便携棋盘耐久。官方备注：使用物品事件里立即写耐久可能失效，
		故延迟几帧再写；这几帧内玩家换了手持则本次不扣（下次摆放再扣）。
		耐久归零 -> 物品用完销毁（走ConsumeCarriedItem，同步释放刷新空位）"""
		yield -5
		if self.GetCarriedItemName(playerId) != config.BoardItemName:
			return
		try:
			itemComp = serverApi.CreateComponent(playerId, config.Minecraft, config.ItemComponent)
			posType = serverApi.GetMinecraftEnum().ItemPosType.CARRIED
			durability = itemComp.GetItemDurability(posType, 0)
			if durability is None:
				# 耐久读不到（接口异常/物品已不在手上）：按用完处理，防止无限白嫖
				logger.warning("[Gomoku] 读取便携棋盘耐久失败，按用完销毁处理")
				self.ConsumeCarriedItem(playerId)
				return
			durability -= 1
			if durability > 0:
				if itemComp.SetItemDurability(posType, 0, durability):
					self.MsgPlayer(playerId, 'board_item_durability', count=durability)
				else:
					logger.warning("[Gomoku] 写回便携棋盘耐久失败（本次摆放不扣耐久）")
			else:
				if self.ConsumeCarriedItem(playerId):
					self.Msg('board_item_used_up')
		except Exception as e:
			logger.warning("[Gomoku] DamageBoardItem 失败: {}".format(e))

	def OnPlayerTryDestroyBlock(self, args):
		"""左键挖掘入口（挖穿前触发）：矿->采集（普通/硬化矿须对应镐级、金矿徒手可挖，
		高级镐也能采低级矿，见PickaxeTierDict）；
		棋盘棋石->普通棋石须石镐级、硬化棋石须铁镐级、金棋石任何镐都挖不动（只能雷管炸）；
		盘上挖掘耗时（6s/10s）均长于盘外采同系矿（3s/5s），由方块destroy_time控制；
		棋盘基座->一律取消挖掘（不依赖destroy_time硬扛，脚本层直接cancel；
		将来实现特殊道具时在此按手持道具放行）。棋子携带已满（MaxCarriedPieces）时
		取消挖掘，矿保留原地、镐不消耗。工具校验采用原版语义——工具不对照样允许挖穿
		（不打断长按连续挖掘），只是拿不到棋子；挖穿后矿不产生原版掉落，棋子由脚本发到
		背包；镐耐久1，采一次即碎。事件字段对照官方模板：fullName/x/y/z/playerId/cancel/spawnResources"""
		if not self.loggedTryDestroyEvent:
			logger.info("[Gomoku] ServerPlayerTryDestroyBlockEvent raw: {}".format(args))
			self.loggedTryDestroyEvent = True
		if self.IsRespawnHeld(args.get('playerId')):
			# 阵亡冷却中：取消挖掘，矿/棋石保留原地
			args['cancel'] = True
			self.TellRespawnHeld(args.get('playerId'))
			return
		if self.IsTimestopFrozen(args.get('playerId')):
			# 时间停止中：取消挖掘，矿/棋石保留原地（客户端已关攻击/破坏输入，兜底）
			args['cancel'] = True
			self.TellTimestopFrozen(args.get('playerId'))
			return
		blockName = args.get('fullName', '')
		if self.IsChessBaseBlock(blockName):
			# 基座不可破坏：脚本直接取消（与棋子上限拦截同款机制，不靠destroy_time限制）
			args['cancel'] = True
			playerId = args.get('playerId')
			if playerId:
				self.MsgThrottled(playerId, 'baseBreak', 'base_break_protected')
			return
		if blockName == config.RandomBlockName:
			# 问号方块：独立于矿石分支（任意镐可采，不限定矿种），见HandleRandomBlockBreak
			self.HandleRandomBlockBreak(args)
			return
		if blockName not in config.OrePieceItemDict:
			if blockName in config.StoneBlockNameSet:
				# 金棋石：任何镐都挖不动（脚本一律取消，与基座同款机制）——
				# 只能靠雷管炸（墨水对金无效，金子无阵营可转化）
				if blockName == config.StoneGoldName:
					args['cancel'] = True
					playerId = args.get('playerId')
					if playerId:
						self.MsgThrottled(playerId, 'goldStone', 'gold_stone_no_pickaxe')
					return
				# 普通棋石须石镐级、硬化棋石须铁镐级（更高级的镐也能挖低级棋石，见PickaxeTierDict；
				# 挖棋石不消耗镐，镐耐久只花在挖矿上）；
				# 盘上挖掘耗时由方块destroy_time控制（6s/10s），均长于盘外采同系矿（3s/5s）
				if blockName in config.HardenedStoneNameSet:
					minTier = 2
				else:
					minTier = 1
				playerId = args.get('playerId')
				carriedTier = config.PickaxeTierDict.get(self.GetCarriedItemName(playerId), 0)
				if playerId and carriedTier < minTier:
					args['cancel'] = True
					self.MsgThrottled(playerId, 'stoneTool', 'stone_tool_wrong_tier',
						pickaxe=config.TierPickaxeNameDict[minTier])
					return
				self.HandleStoneBreak(args)
			elif blockName == config.DetonatorBlockName:
				# 引爆前把雷管方块挖掉=拆除（销毁无掉落）；引信协程到点发现方块没了会自行取消
				args['spawnResources'] = False
				self.Msg('bomb_defused')
			return
		playerId = args.get('playerId')
		if playerId and self.CountCarriedPieces(playerId) >= config.MaxCarriedPieces:
			# 棋子携带已满：取消挖掘（矿留在原地、镐不消耗、存量计数不动）
			args['cancel'] = True
			self.MsgThrottled(playerId, 'pieceCap', 'piece_cap_mine',
				count=config.MaxCarriedPieces)
			return
		# 矿被挖碎（无论工具对错，方块都会消失）：存量计数-1
		self.oreCountDict[blockName] = self.oreCountDict.get(blockName, 0) - 1
		if not playerId:
			return
		# 该矿要求的最低镐等级（金矿无要求，徒手可挖；高级镐可采低级矿，见PickaxeTierDict）
		minTier = config.OreMinTierDict.get(blockName)
		if minTier is not None:
			carriedItem = self.GetCarriedItemName(playerId)
			if carriedItem is None:
				logger.warning("[Gomoku] 无法读取手持物品，按无镐处理")
				carriedItem = ''
			if config.PickaxeTierDict.get(carriedItem, 0) < minTier:
				# 镐等级不够：允许挖穿（保持长按连续挖掘），但没有棋子——原版"徒手挖铁矿"体验
				args['spawnResources'] = False
				self.Msg('mine_wrong_pickaxe', pickaxe=config.TierPickaxeNameDict[minTier])
				return
			# 镐耐久1，采一次即碎
			if not self.ConsumeCarriedItem(playerId):
				return
		# 挖穿：关掉矿的原版掉落，棋子直接发到背包
		args['spawnResources'] = False
		if not self.GiveItemToPlayer(playerId, config.OrePieceItemDict[blockName]):
			# 发放失败（如背包满/物品未注册）：延迟把矿补回去，避免既没矿也没棋子
			pos = (args.get('x'), args.get('y'), args.get('z'))
			CoroutineMgr.StartCoroutine(self.DelayRestoreOre(pos, blockName))
			self.Msg('mine_give_fail')
		else:
			logger.info("[Gomoku] 挖矿采集: {} -> {} @ ({}, {}, {})".format(
				blockName, config.OrePieceItemDict[blockName], args.get('x'), args.get('y'), args.get('z')))

	def HandleStoneBreak(self, args):
		"""棋盘棋石被挖掉（走到这里的都过了门控：普通棋石须石镐级、硬化棋石须铁镐级
		（高级镐通用）、金棋石已被取消）：挖掉即销毁、无掉落，并释放引擎中对应格子（被挖掉的子不再占线）"""
		pos = (args.get('x'), args.get('y'), args.get('z'))
		if None in pos:
			return
		args['spawnResources'] = False  # 策划案：被破坏的棋子一律销毁，不产生掉落
		if not self.IsStoneSlot(pos):
			return  # 不在主盘/扩展格落子层的棋石（正常不会有），仅销毁
		bx, by = self.WorldToGrid(pos)
		# 陷阱棋石：被挖毁时引爆（只炸玩家不毁棋盘），先消费雷再释放引擎格子
		if (bx, by) in self.trapCells:
			self.trapCells.discard((bx, by))
			self.DetonateTrap(pos, args.get('playerId'))
		removeResult = self.board.remove(bx, by)
		if removeResult.ok:
			logger.info("[Gomoku] 棋石被挖除: {} @ 引擎坐标{}".format(args.get('fullName'), (bx, by)))
			self.Msg('mine_stone_removed')

	def DetonateTrap(self, pos, diggerId):
		"""陷阱棋石被挖毁时引爆：炸死以该格为中心、TrapKillRadius半径内的全部玩家
		（含亲手挖它的人，不分敌我——雷管只毁棋不伤人，陷阱正相反只伤人）。
		棋石/棋盘/地形无损（本格棋石照常销毁、引擎格子照常释放，见HandleStoneBreak）。
		受害名单用选择器圈定（CreateEntityComponent需传中心实体，这里传挖雷人），
		逐个KillEntity处决（CreateGame组件，官方文档写法）"""
		selector = '@a[x={},y={},z={},r={}]'.format(pos[0], pos[1], pos[2], config.TrapKillRadius)
		victims = []
		entityComp = serverApi.GetEngineCompFactory().CreateEntityComponent(diggerId) if diggerId else None
		if entityComp:
			victims = entityComp.GetEntitiesBySelector(selector) or []
		killed = 0
		gameComp = serverApi.GetEngineCompFactory().CreateGame(self.levelId)
		for entityId in victims:
			if gameComp and gameComp.KillEntity(entityId):
				killed += 1
		if killed:
			self.Msg('trap_exploded_hit', count=killed)
		else:
			self.Msg('trap_exploded_empty')
		logger.info("[Gomoku] 陷阱引爆: {} 处决{}人".format(pos, killed))

	def DelayRestoreOre(self, pos, blockName):
		"""挖穿事件后再把矿补回原地（事件先于方块真正消失，需延迟几帧）；补回后存量计数+1"""
		yield -10
		if self.RunCommand('/setblock {} {} {} {}'.format(pos[0], pos[1], pos[2], blockName)):
			self.oreCountDict[blockName] = self.oreCountDict.get(blockName, 0) + 1

	def HandleRandomBlockBreak(self, args):
		"""问号方块被挖（任意镐可采，独立于矿石的"一矿一镐"对应）：
		存量计数-1；没拿镐则允许挖穿但拿不到奖励（与矿石"拿错工具白挖"同款体验）；
		拿了任意镐则消耗镐（耐久1采一次即碎），从RandomBlockPoolDict加权随机抽一个
		道具直接发到背包；发放失败（如背包满）延迟把方块补回去，避免既没块也没奖励。
		奖励池不含棋子，无棋子携带上限的边界问题"""
		blockName = config.RandomBlockName
		playerId = args.get('playerId')
		# 块被挖碎（无论工具对错，方块都会消失）：存量计数-1
		self.oreCountDict[blockName] = self.oreCountDict.get(blockName, 0) - 1
		if not playerId:
			return
		carriedItem = self.GetCarriedItemName(playerId)
		itemCfg = config.ItemTable.get(carriedItem) if carriedItem else None
		if not itemCfg or itemCfg.get('type') != 'pickaxe':
			# 没拿镐：允许挖穿（保持长按连续挖掘），但没有奖励
			args['spawnResources'] = False
			self.Msg('random_block_no_pickaxe')
			return
		# 镐耐久1，采一次即碎
		if not self.ConsumeCarriedItem(playerId):
			return
		args['spawnResources'] = False
		rewardName = self.DrawRandomBlockReward()
		if not self.GiveItemToPlayer(playerId, rewardName):
			pos = (args.get('x'), args.get('y'), args.get('z'))
			CoroutineMgr.StartCoroutine(self.DelayRestoreOre(pos, blockName))
			self.Msg('random_block_give_fail')
			return
		rewardCfg = config.ItemTable.get(rewardName, {})
		rewardLabel = rewardCfg.get('name', rewardName)
		if isinstance(rewardLabel, str):
			rewardLabel = rewardLabel.decode('utf-8', 'ignore')  # py2配置里的中文是bytes
		playerName = self.GetPlayerName(playerId) or messageConfig.FALLBACK_PLAYER_NAME
		self.Msg('random_block_opened', player=playerName, item=rewardLabel)
		logger.info("[Gomoku] 问号方块采集: {} @ ({}, {}, {}) 开出{} ({})".format(
			blockName, args.get('x'), args.get('y'), args.get('z'), rewardName, playerId))

	def DrawRandomBlockReward(self):
		"""从问号方块奖励池（RandomBlockPoolDict: 道具名->权重）加权随机抽一个道具"""
		pool = config.RandomBlockPoolDict
		total = sum(pool.itervalues())
		pick = random.uniform(0, total)
		acc = 0
		for itemName, weight in pool.iteritems():
			acc += weight
			if pick < acc:
				return itemName
		return random.choice(pool.keys())  # 浮点边界兜底

	# ---------- 交互：武器 ----------

	def OnPlayerAttack(self, args):
		"""手持武器（道具表type=weapon）攻击玩家 -> 按表内伤害加成，一次性武器随之销毁。
		damage须与isValid成对设置才生效（对照官方PVP模板script_Team的队友免伤写法，
		只设damage引擎会忽略脚本伤害值）"""
		attackerId = args.get('playerId')
		victimId = args.get('victimId')
		if not attackerId or not victimId:
			return
		if self.IsRespawnHeld(attackerId):
			# 阵亡冷却中：无武器加成（伤害本身也被OnDamage清零，此处拦掉剑的消耗误判）
			return
		if self.IsTimestopFrozen(attackerId):
			# 时间停止中：打不出武器效果（客户端已关攻击输入，这里兜底防绕过）；
			# 被冻结的受害者不拦——冻结只锁操作不锁血，照样可以被处决
			return
		if self.IsRespawnHeld(victimId):
			# 目标在阵亡冷却中（免疫伤害）：不施加武器伤害也不消耗剑，别白碎一次性武器
			return
		engineTypeComp = serverApi.CreateComponent(victimId, config.Minecraft, config.EngineTypeComponent)
		if not engineTypeComp or engineTypeComp.GetEngineTypeStr() != 'minecraft:player':
			return
		# 同队免伤（与TeamMod友伤抑制一致；本系统先于/后于TeamMod触发结果都一样：
		# 这里不设9999就不会覆盖TeamMod写下的damage=0，剑也不消耗）
		attackerSide = self.GetPlayerSide(attackerId)
		if attackerSide is not None and attackerSide == self.GetPlayerSide(victimId):
			return
		itemCfg = config.ItemTable.get(self.GetCarriedItemName(attackerId))
		if not itemCfg or itemCfg['type'] != 'weapon':
			return
		if itemCfg.get('dizzy'):
			# 眩晕锤：零伤害（damage=0+isValid成对才生效），改为眩晕+缴械掉落
			# （见HandleDizzyHammerHit）；锤中敌方即碎，同队/冷却目标上面已提前返回
			args['damage'] = 0
			args['isValid'] = 1
			self.HandleDizzyHammerHit(attackerId, victimId)
			if itemCfg.get('consumable') and self.ConsumeCarriedItem(attackerId):
				self.Msg('weapon_dizzy_hit', victim=self.GetEntityName(victimId))
			return
		if itemCfg.get('chaos'):
			# 混乱药水：零伤害（damage=0+isValid成对才生效），改为10秒混乱——
			# 前后左右移动反向+反胃天旋地转（客户端反向输入，见HandleChaosPotionHit）
			# +全屏绿屏；砸中敌方即碎，同队/冷却目标上面已提前返回
			args['damage'] = 0
			args['isValid'] = 1
			self.HandleChaosPotionHit(attackerId, victimId)
			if itemCfg.get('consumable') and self.ConsumeCarriedItem(attackerId):
				self.Msg('weapon_chaos_hit', victim=self.GetEntityName(victimId))
			return
		args['damage'] = itemCfg.get('damage', config.DefaultWeaponDamage)
		args['isValid'] = 1
		if itemCfg.get('consumable') and self.ConsumeCarriedItem(attackerId):
			self.Msg('weapon_execution', weapon=itemCfg['name'])

	# ---------- 眩晕锤 ----------

	def HandleDizzyHammerHit(self, attackerId, victimId):
		"""眩晕锤命中敌方玩家：目标不掉血（OnPlayerAttack里damage=0），但被眩晕
		config.DizzyHammerStunSeconds 秒——原版效果组合：迟缓VII(移速-105%原地
		锁死)+虚弱II(拳头打不出伤害)+反胃(眩晕画面)；同时背包道具全部掉在脚下
		（DropPlayerInventory），眩晕期间拾取被拦截（OnPlayerTryTouch）防止
		原地站桩秒捡回去。效果时长按整秒生效（AddEffectToEntity只收整秒）"""
		stunSeconds = config.DizzyHammerStunSeconds
		effectSeconds = int(round(stunSeconds))
		try:
			effectComp = serverApi.CreateComponent(victimId, config.Minecraft, config.EffectComponent)
			if effectComp:
				effectComp.AddEffectToEntity('slowness', effectSeconds, 6, True)
				effectComp.AddEffectToEntity('weakness', effectSeconds, 1, True)
				effectComp.AddEffectToEntity('nausea', effectSeconds, 0, True)
			else:
				logger.warning("[Gomoku] 创建effect组件失败: {}".format(victimId))
		except Exception as e:
			logger.warning("[Gomoku] 眩晕效果施加失败: {}".format(e))
		self.dizzyStunUntilDict[victimId] = time.time() + stunSeconds
		dropped = self.DropPlayerInventory(victimId)
		logger.info("[Gomoku] 眩晕锤命中: {} -> {} (眩晕{}秒, 掉落{}件)".format(
			attackerId, victimId, stunSeconds, dropped))

	def HandleChaosPotionHit(self, attackerId, victimId, seconds=None):
		"""混乱药水命中敌方玩家：目标不掉血（OnPlayerAttack里damage=0），进入
		config.ChaosPotionConfuseSeconds 秒混乱——前后左右移动反向（不反视角）。
		seconds可覆盖时长（#chaos调试命令用，缺省走配置）。机制：
		  1. 移动反向在客户端：真实输入取负后LockInputVector（W<->S、A<->D对调，
		     引擎原生位移）。输入来源按平台分层（见gomokuClientSystem）：PC键盘=
		     OnKeyPressInGame按键事件、PC手柄=摇杆事件、手机轮盘=逐帧轮询——
		     GetInputVector锁定中只返回回声，逐帧解锁读/重锁会抖动，均试败。
		  2. 全屏表现用原版反胃（nausea）：屏幕天旋地转，零伤害不用拦。
		     曾用中毒（绿屏）但状态效果的伤害不触发DamageEvent、
		     ActorHurtServerEvent的damage又不可修改（见官方文档），拦不掉扣血。
		效果时长按整秒生效（AddEffectToEntity只收整秒）"""
		if seconds is None:
			seconds = config.ChaosPotionConfuseSeconds
		effectSeconds = int(round(seconds))
		try:
			effectComp = serverApi.CreateComponent(victimId, config.Minecraft, config.EffectComponent)
			if effectComp:
				# 反胃=纯视觉天旋地转，无伤害无副作用（眩晕锤用的slowness组合，这里单用）
				effectComp.AddEffectToEntity('nausea', effectSeconds, 0, True)
			else:
				logger.warning("[Gomoku] 创建effect组件失败: {}".format(victimId))
		except Exception as e:
			logger.warning("[Gomoku] 反胃表现施加失败: {}".format(e))
		self.chaosUntilDict[victimId] = time.time() + seconds
		data = self.CreateEventData()
		data['duration'] = seconds
		self.NotifyToClient(victimId, config.ChaosConfuseEvent, data)
		logger.info("[Gomoku] 混乱药水命中: {} -> {} (混乱{}秒, 客户端移动反向)".format(
			attackerId, victimId, seconds))

	def EndChaosEffect(self, playerId):
		"""提前解除某玩家的混乱（#unchaos调试命令 / 新一局开始时用）：
		清混乱登记，并通知其客户端立即停止视角镜像与位移反转
		（ChaosConfuseEvent的duration=0，见gomokuClientSystem）"""
		self.chaosUntilDict.pop(playerId, None)
		data = self.CreateEventData()
		data['duration'] = 0
		self.NotifyToClient(playerId, config.ChaosConfuseEvent, data)

	def ClearAllChaosEffects(self):
		"""终止所有进行中的混乱（新一局开始时调用：背包已清空、道具都作废，
		混乱不该跨局）。逐个走EndChaosEffect：清登记+通知客户端停止视角镜像
		与位移反转（duration=0），观感上混乱随对局结束立即消失"""
		for playerId in list(self.chaosUntilDict.keys()):
			self.EndChaosEffect(playerId)

	# ---------- 时间停止 ----------

	def IsTimestopFrozen(self, playerId):
		"""该玩家是否被时间停止冻结中（登记到期的自然解冻，无需协程清理）"""
		return playerId is not None and time.time() < self.timestopFreezeUntilDict.get(playerId, 0)

	def TellTimestopFrozen(self, playerId):
		"""冻结期间操作被拦截时的个人提示（节流防刷屏，与阵亡冷却提示共用冷却表）"""
		if not playerId:
			return
		key = (playerId, 'timestop')
		now = time.time()
		if now - self.announceThrottleTime.get(key, 0) < config.ThrottledAnnounceCooldown:
			return
		self.announceThrottleTime[key] = now
		remaining = max(1, int(round(self.timestopFreezeUntilDict.get(playerId, 0) - now)))
		self.MsgPlayer(playerId, 'timestop_frozen', seconds=remaining)

	def HandleTimestopUse(self, playerId):
		"""时间停止：右键使用——除使用者外的全场玩家冻结config.TimestopFreezeSeconds秒。
		冻结是双层的：客户端关移动/跳跃/攻击输入（TimestopFreezeEvent ->
		SetCanMove/SetCanJump/SetCanAttack，视角转动保留，见gomokuClientSystem），
		服务端登记timestopFreezeUntilDict并拦截挖掘/落子/道具/攻击/拾取（各事件
		入口的IsTimestopFrozen检查）。冻结不锁血——使用者（和其他未被冻者）照样
		可以处决冻结中的玩家。与换位符同款双入口（指方块右键走OnItemUseOn、
		对空气右键走OnItemTryUse），timestopUseTime做1秒去重防同次点击双触发"""
		now = time.time()
		if now - self.timestopUseTime.get(playerId, 0) < 1.0:
			return
		self.timestopUseTime[playerId] = now
		logger.info("[Gomoku] 时间停止右键: {} 手持={}".format(playerId, self.GetCarriedItemName(playerId)))
		if not self.ConsumeCarriedItem(playerId):
			return
		freezeSeconds = config.TimestopFreezeSeconds
		frozen = []
		for pid in serverApi.GetPlayerList():
			if pid == playerId:
				continue
			self.timestopFreezeUntilDict[pid] = now + freezeSeconds
			frozen.append(pid)
			data = self.CreateEventData()
			data['duration'] = freezeSeconds
			self.NotifyToClient(pid, config.TimestopFreezeEvent, data)
			self.MsgPlayer(pid, 'timestop_you', seconds=freezeSeconds)
		if frozen:
			self.Msg('timestop_announce',
				player=self.GetPlayerName(playerId) or messageConfig.FALLBACK_PLAYER_NAME,
				seconds=freezeSeconds)
		else:
			self.MsgPlayer(playerId, 'timestop_lonely')
		logger.info("[Gomoku] 时间停止: {} 冻结{}人{}秒".format(playerId, len(frozen), freezeSeconds))

	def ClearAllTimestopFreeze(self):
		"""终止所有进行中的时间停止冻结（新一局开始时调用：背包已清空、道具都作废，
		冻结不该跨局）。清登记并逐个通知客户端恢复移动/跳跃/攻击输入
		（TimestopFreezeEvent的duration=0，见gomokuClientSystem）"""
		for playerId in list(self.timestopFreezeUntilDict.keys()):
			self.timestopFreezeUntilDict.pop(playerId, None)
			data = self.CreateEventData()
			data['duration'] = 0
			self.NotifyToClient(playerId, config.TimestopFreezeEvent, data)

	def DropPlayerInventory(self, playerId):
		"""把玩家背包全部物品掉到脚下（眩晕锤的缴械）。只掉INVENTORY 36格
		（已含手持位；装备/副手不动——道具都在背包里）。物品信息字典原样透传
		（getUserData=True读取，保留耐久等状态）；掉落物不登记itemExpireDict——
		它们本来就是被登记过的"在场"物品，只是换了存放位置。返回掉落件数"""
		try:
			posComp = serverApi.GetEngineCompFactory().CreatePos(playerId)
			pos = posComp.GetPos() if posComp else None
			if not pos:
				logger.warning("[Gomoku] 读取被锤者位置失败: {}".format(playerId))
				return 0
			itemComp = serverApi.CreateComponent(playerId, config.Minecraft, config.ItemComponent)
			levelItemComp = serverApi.CreateComponent(self.levelId, config.Minecraft, config.ItemComponent)
			invItems = itemComp.GetPlayerAllItems(
				serverApi.GetMinecraftEnum().ItemPosType.INVENTORY, True) or []
			dropped = 0
			for slot, itemDict in enumerate(invItems):
				if not itemDict:
					continue
				# 掉落物组件用levelId创建（与SpawnItemEntity一致；levelId组件
				# 只管世界侧生成，playerId组件只管背包读写）
				if levelItemComp.SpawnItemToLevel(itemDict, config.MainDimensionId, pos):
					itemComp.SetInvItemNum(slot, 0)
					dropped += 1
				else:
					logger.warning("[Gomoku] 掉落物生成失败: slot={} {}".format(slot, self.GetItemName(itemDict)))
			return dropped
		except Exception as e:
			logger.warning("[Gomoku] DropPlayerInventory 失败: {}".format(e))
			return 0

	# ---------- 阵亡与复活 ----------

	def OnPlayerDie(self, args):
		"""玩家阵亡（处决剑一击必杀等）：WorldMod的immediate_respawn规则使引擎不弹
		原版死亡界面，阵亡者自动在队伍复活点（棋盘附近）重生，无需任何点击。
		这里登记DeathRespawnHoldSeconds的行动封锁并启动倒计时，时间到自动解锁"""
		playerId = args.get('id')
		holdSeconds = config.DeathRespawnHoldSeconds
		if not playerId or holdSeconds <= 0:
			return
		self.respawnHoldUntilDict[playerId] = time.time() + holdSeconds
		self.Msg('death_announce',
			player=self.GetPlayerName(playerId) or messageConfig.FALLBACK_PLAYER_NAME,
			seconds=holdSeconds)
		CoroutineMgr.StartCoroutine(self.RespawnCountdown(playerId))

	def RespawnCountdown(self, playerId):
		"""阵亡冷却倒计时：每秒给阵亡玩家发一条聊天框消息；到点解锁行动并提示复活。
		玩家中途退出时OnDelServerPlayer清掉登记，本协程下一轮自然结束"""
		while True:
			remaining = int(round(self.respawnHoldUntilDict.get(playerId, 0) - time.time()))
			if remaining <= 0:
				break
			self.MsgPlayer(playerId, 'death_countdown', seconds=remaining)
			yield -30
		if playerId in self.respawnHoldUntilDict:
			del self.respawnHoldUntilDict[playerId]
			self.MsgPlayer(playerId, 'death_revived')

	def SendMessageToPlayer(self, playerId, text):
		"""给单个玩家发聊天框消息。官方msg组件直接按playerId发送（原先用/title命令
		实测执行失败——命令解析/对重生流程中的玩家都不可靠，弃用）"""
		try:
			msgComp = serverApi.GetEngineCompFactory().CreateMsg(playerId)
			msgComp.NotifyOneMessage(playerId, text)
		except Exception as e:
			logger.warning("[Gomoku] NotifyOneMessage 失败: {}".format(e))

	def GetPlayerName(self, playerId):
		"""读玩家名（对照EndLogic的nameComp.name写法）；组件不可用返回None"""
		try:
			nameComp = serverApi.CreateComponent(playerId, config.Minecraft, config.NameComponent)
			return nameComp.name if nameComp else None
		except Exception as e:
			logger.warning("[Gomoku] GetPlayerName 失败: {}".format(e))
			return None

	def IsRespawnHeld(self, playerId):
		"""阵亡冷却中（人已重生但行动被封锁，时间到自动解锁）"""
		return time.time() < self.respawnHoldUntilDict.get(playerId, 0)

	def TellRespawnHeld(self, playerId):
		"""冷却期间尝试交互时的个人提示（节流防刷屏，与AnnounceThrottled共用冷却表）"""
		key = (playerId, 'respawnHold')
		now = time.time()
		if now - self.announceThrottleTime.get(key, 0) < config.ThrottledAnnounceCooldown:
			return
		self.announceThrottleTime[key] = now
		remaining = max(1, int(round(self.respawnHoldUntilDict.get(playerId, 0) - now)))
		self.MsgPlayer(playerId, 'death_hold', seconds=remaining)

	def OnDamage(self, args):
		"""阵亡冷却期间免疫一切伤害（防复活点被连杀蹲尸；伤害清零写法对照StartLogic等待区无敌）；
		转移符护盾：受到真实伤害时不落地，本体清零，全额转给最近的敌方玩家
		（Hurt接口，伤害来源/击杀归属沿用本次攻击；环境伤害无来源时归护盾主人）"""
		victimId = args.get('entityId')
		if self.IsRespawnHeld(victimId):
			args['damage'] = 0
			return
		if victimId not in self.transferShieldSet:
			return
		damage = args.get('damage') or 0
		if damage <= 0:
			return  # 没有真实伤害（如队友免伤清零）：护盾保留，等下一次
		targetId = self.FindNearestEnemyPlayer(victimId)
		if targetId is None:
			return  # 场上没有可转移的敌人：护盾保留，本次伤害照常落在自己身上
		# 护盾先失效再转移（若敌人也带护盾，由对方的护盾接手，不会来回弹）
		self.transferShieldSet.discard(victimId)
		args['damage'] = 0
		srcId = args.get('srcId')
		attackerId = srcId if srcId and srcId != '-1' else victimId
		cause = args.get('cause') or 'entity_attack'
		hurtComp = serverApi.GetEngineCompFactory().CreateHurt(targetId)
		if not hurtComp or not hurtComp.Hurt(damage, cause, attackerId, None, True):
			logger.warning("[Gomoku] 转移符伤害转移失败: {} -> {} damage={}".format(victimId, targetId, damage))
			return
		self.Msg('transfer_triggered',
			victim=self.GetPlayerName(victimId) or messageConfig.FALLBACK_PLAYER_NAME,
			damage=int(round(damage)),
			target=self.GetPlayerName(targetId) or messageConfig.FALLBACK_ENEMY_NAME)
		logger.info("[Gomoku] 转移符生效: {} -> {} damage={} cause={} attacker={}".format(
			victimId, targetId, damage, cause, attackerId))

	def OnDelServerPlayer(self, args):
		"""玩家退出：清掉阵亡冷却/转移符护盾/加速药水登记（相关协程下一轮自然结束）"""
		playerId = args.get('id')
		self.respawnHoldUntilDict.pop(playerId, None)
		self.transferShieldSet.discard(playerId)
		self.speedPotionBaseDict.pop(playerId, None)
		self.speedPotionUseTime.pop(playerId, None)
		self.dizzyStunUntilDict.pop(playerId, None)
		self.chaosUntilDict.pop(playerId, None)
		self.timestopFreezeUntilDict.pop(playerId, None)
		self.timestopUseTime.pop(playerId, None)
		oldBoost = self.speedPotionCoroutineDict.pop(playerId, None)
		if oldBoost is not None:
			CoroutineMgr.StopCoroutine(oldBoost)
		self.playerIds.discard(playerId)
		self.manualOpenTime.pop(playerId, None)
		self.blackholeUseTime.pop(playerId, None)
		self.boardPlaceUseTime.pop(playerId, None)

	def SetEngineRespawnPoint(self, playerId):
		"""把玩家的引擎复活点设到棋盘外沿。无床玩家默认在世界出生点重生，本图出生点
		在远处未加载区块，重生会永远卡在"正在重生"（原版死亡界面点"重生"没反应
		也是这个原因）。棋盘外沿在tickingarea常驻加载范围内，引擎重生能立刻落地，
		落地后LimitedRespawn再传送到队伍复活点。官方限制：死亡后不能设置复活点，
		所以进服/开局时设好"""
		try:
			playerComp = serverApi.GetEngineCompFactory().CreatePlayer(playerId)
			result = playerComp.SetPlayerRespawnPos(self.GetEngineRespawnPos(), config.MainDimensionId)
			if result:
				logger.info("[Gomoku] 已设置复活点到棋盘外沿: {}".format(playerId))
			else:
				logger.warning("[Gomoku] 设置引擎复活点失败: {}".format(playerId))
		except Exception as e:
			logger.warning("[Gomoku] SetEngineRespawnPoint 异常: {}".format(e))

	def GetEngineRespawnPos(self):
		"""引擎复活点世界坐标：棋盘南侧外沿（config.RespawnPosOffset），y取实测地表，
		查询失败退回基座层Y+备用偏移"""
		cx, cy, cz = self.EnsureBoardCenter()
		dx, dyFallback, dz = config.RespawnPosOffset
		x, z = cx + dx, cz + dz
		surfaceY = self.FindSurfaceY(x, z)
		return (x, surfaceY if surfaceY is not None else cy + dyFallback, z)

	# ---------- 调试聊天命令 ----------

	def OnServerChat(self, args):
		"""调试命令入口（config.DebugChatCommands开关，正式对战请关掉）：
		聊天输入 #give <道具名> 直接把道具发到自己背包；#give 不带参数列出全部可领道具。
		#chaos [秒] 直接让自己进入混乱状态（不消耗道具、不需要敌方在场，方便单人
		测视角/移速反向）；#unchaos 提前解除自己的混乱。
		命令消息会被cancel，不广播到公屏。道具名用道具表的短名（如 便携棋盘/处决剑）"""
		if not config.DebugChatCommands:
			return
		playerId = args.get('playerId')
		if not playerId:
			return
		message = args.get('message', '')
		if isinstance(message, str):
			message = message.decode('utf-8', 'ignore')  # py2事件里聊天是bytes
		msg = (message or '').strip()
		if not msg.startswith(u'#'):
			return
		args['cancel'] = True
		parts = msg.split()
		if parts[0] == u'#chaos':
			# 调试：直接对自己施加混乱（秒数缺省用配置值，如 #chaos 30）
			seconds = config.ChaosPotionConfuseSeconds
			if len(parts) >= 2:
				try:
					seconds = max(1, int(parts[1]))
				except ValueError:
					pass
			self.HandleChaosPotionHit(playerId, playerId, seconds)
			self.TellToPlayer(playerId, u"§d已进入混乱状态{}秒（视角+移速反向）".format(seconds))
			return
		if parts[0] == u'#unchaos':
			self.EndChaosEffect(playerId)
			self.TellToPlayer(playerId, u"§a混乱已解除（移速/视角恢复）")
			return
		if parts[0] != u'#give':
			self.TellToPlayer(playerId, u"§c未知命令，可用: #give <道具名> / #chaos [秒] / #unchaos")
			return
		if len(parts) < 2:
			names = u'、'.join(cfg['name'].decode('utf-8') for cfg in config.ItemTable.itervalues())
			self.TellToPlayer(playerId, u"§e可领道具: {}".format(names))
			return
		targetName = u' '.join(parts[1:])
		for itemName, itemCfg in config.ItemTable.iteritems():
			if itemCfg['name'].decode('utf-8') == targetName:
				if self.GiveItemToPlayer(playerId, itemName):
					self.TellToPlayer(playerId, u"§a已发放: {} x1".format(targetName))
				else:
					self.TellToPlayer(playerId, u"§c发放失败（背包满?），详情见日志")
				return
		self.TellToPlayer(playerId, u"§c没有这个道具: {}（#give 列出可领道具）".format(targetName))

	def TellToPlayer(self, playerId, text):
		"""给单个玩家发聊天栏消息（/tellraw按名字选目标）。
		text统一按unicode传入，发命令前encode回utf-8字节串（py2引擎命令须str）"""
		name = self.GetPlayerName(playerId)
		if name:
			if isinstance(text, unicode):
				text = text.encode('utf-8')
			self.RunCommand('/tellraw {} {{"rawtext":[{{"text":"{}"}}]}}'.format(name, text))

	# ---------- 胜负播报 ----------

	def OnGameEnd(self, winnerPlayer, winningLines):
		"""对局结束：本地播报 + 通知客户端，并调EndLogic结算本局、重启下一轮。
		winnerPlayer为None表示平局；winningLines为引擎网格坐标，按主盘中心
		换算成世界坐标供客户端高亮。结算走EndLogic.ExternalSettleGame
		（作废定时器+通知胜利+自动重启），不再只调NotifyVictory
		（那只是播报，本局不会结束，超时结算照常触发）"""
		logger.info("[Gomoku] 对局结束: 胜方棋子值={} 连珠线={}".format(winnerPlayer, winningLines))
		if winnerPlayer is None:
			winnerSide = None
			sideText = self.GetText('win_draw_side')
			victoryText = self.GetText('win_draw_announce')
			self.Announce(victoryText)
		else:
			winnerSide = 'black' if winnerPlayer == BLACK else 'white'
			sideText = config.SideNameDict.get(winnerSide, winnerSide)
			victoryText = self.GetText('win_victory_announce', side=sideText)
			self.Announce(victoryText)
		data = self.CreateEventData()
		data['winner'] = winnerSide
		if winnerSide:
			data['text'] = self.GetText('win_result_victory', side=sideText)
		else:
			data['text'] = self.GetText('win_result_end', side=sideText)
		data['winningLines'] = [
			[list(self.GridToWorld(bx, by)) for bx, by in line]
			for line in winningLines
		]
		self.BroadcastToAllClient(config.GomokuGameResultEvent, data)
		# 胜负与平局都要真正结算本局（平局之前没通知EndLogic，会导致满盘后僵到超时）
		endLogicServerSystem = serverApi.GetSystem(config.EndLogicModName, config.EndLogicServerSystemName)
		if endLogicServerSystem:
			# 系列赛记分需要真实队名（"黑方/白方"只是播报别名）：按胜方阵营反查TeamSideDict；
			# 平局（winnerSide为None）与调试模式下无法定位队伍时传None，本局不记胜场
			winnerTeamName = None
			if winnerSide is not None:
				for teamName, side in config.TeamSideDict.iteritems():
					if side == winnerSide:
						winnerTeamName = teamName
						break
			endLogicServerSystem.ExternalSettleGame(sideText, victoryText, None, winnerTeamName)
		else:
			self.Msg('game_no_endlogic')

	# ---------- 跨Mod查询 ----------

	def GetPlayerSide(self, playerId):
		"""通过TeamMod查询玩家队伍，映射到黑白阵营"""
		teamServerSystem = serverApi.GetSystem(config.TeamModName, config.TeamServerSystemName)
		if not teamServerSystem:
			return None
		teamName = teamServerSystem.GetPlayerTeamName(playerId)
		return config.TeamSideDict.get(teamName)

	# ---------- 物品/方块操作（写法均对照官方模板：neteaseBattle的GetPlayerEngineItemData、
	# CustomDimensionTemplate的consumeActiveItem、TutorialGame的SpawnItemToPlayerInv） ----------

	def GetBlockName(self, pos):
		"""查询主世界某坐标的方块名；查询失败返回None（调用方按无信息处理）"""
		try:
			blockInfoComp = serverApi.GetEngineCompFactory().CreateBlockInfo(config.MainDimensionId)
			blockDict = blockInfoComp.GetBlockNew(pos, config.MainDimensionId)
			if blockDict:
				return blockDict.get('name', '')
		except Exception as e:
			logger.warning("[Gomoku] GetBlockName 失败: {}".format(e))
		return None

	def GetCarriedItemName(self, playerId):
		"""读取玩家手持物品名；API不可用返回None，空手返回''"""
		try:
			itemComp = serverApi.CreateComponent(playerId, config.Minecraft, config.ItemComponent)
			carriedItem = itemComp.GetPlayerItem(serverApi.GetMinecraftEnum().ItemPosType.CARRIED, 0)
			if not self.loggedCarriedItem:
				# 打印一次原始数据，便于核对物品名字段（newItemName/itemName/name）
				logger.info("[Gomoku] 手持物品raw: {}".format(carriedItem))
				self.loggedCarriedItem = True
			if carriedItem:
				return self.GetItemName(carriedItem)
			return ''
		except Exception as e:
			logger.warning("[Gomoku] GetCarriedItemName 失败: {}".format(e))
			return None

	def GetItemName(self, itemDict):
		"""从物品信息字典取物品名（官方模板用newItemName，老版本itemName，再兜底name）"""
		return itemDict.get('newItemName') or itemDict.get('itemName') or itemDict.get('name', '')

	def CountCarriedPieces(self, playerId):
		"""统计玩家携带的棋子总数（普通/硬化/金合计）。对照官方TaskChain模板：
		INVENTORY+OFFHAND遍历（INVENTORY已含手持位，不重复计CARRIED），空槽为falsy跳过。
		API异常返回-1表示未知，调用方按不拦截处理（宽松放行，与跨Mod查询的降级风格一致）"""
		try:
			itemComp = serverApi.CreateComponent(playerId, config.Minecraft, config.ItemComponent)
			posType = serverApi.GetMinecraftEnum().ItemPosType
			playerItems = (itemComp.GetPlayerAllItems(posType.INVENTORY) or []) \
				+ (itemComp.GetPlayerAllItems(posType.OFFHAND) or [])
			return sum(item.get('count', 1) for item in playerItems
				if item and self.GetItemName(item) in config.PieceItemNameSet)
		except Exception as e:
			logger.warning("[Gomoku] CountCarriedPieces 失败: {}".format(e))
			return -1

	def PlayerHasItem(self, playerId, itemName):
		"""查玩家背包（含副手）是否已有某物品——说明书进服发放防重复用；
		API异常返回False按"没有"处理（宁可多发一本不可漏发）"""
		try:
			itemComp = serverApi.CreateComponent(playerId, config.Minecraft, config.ItemComponent)
			posType = serverApi.GetMinecraftEnum().ItemPosType
			playerItems = (itemComp.GetPlayerAllItems(posType.INVENTORY) or []) \
				+ (itemComp.GetPlayerAllItems(posType.OFFHAND) or [])
			return any(item and self.GetItemName(item) == itemName for item in playerItems)
		except Exception as e:
			logger.warning("[Gomoku] PlayerHasItem 失败: {}".format(e))
			return False

	def AnnounceThrottled(self, playerId, kind, text):
		"""按(玩家,类型)节流的播报：事件连续触发（站在物品上反复拾取/长按挖基座）也不刷屏"""
		key = (playerId, kind)
		now = time.time()
		if now - self.announceThrottleTime.get(key, 0) < config.ThrottledAnnounceCooldown:
			return
		self.announceThrottleTime[key] = now
		self.Announce(text)

	def ConsumeCarriedItem(self, playerId):
		"""销毁手持物品（镐/剑耐久1、棋子落子/墨水/雷管消耗均走这里）：count-1后写回手持位。
		消耗成功时同步释放该物品的刷新空位——总数维持按"使用"计：地上的/背包里的都算在场，
		只有用掉（这里）或自然消失（见CountItemEntities的到期剔除）才补刷"""
		try:
			itemComp = serverApi.CreateComponent(playerId, config.Minecraft, config.ItemComponent)
			carriedItem = itemComp.GetPlayerItem(serverApi.GetMinecraftEnum().ItemPosType.CARRIED, 0)
			if not carriedItem:
				return False
			itemName = self.GetItemName(carriedItem)
			carriedItem['count'] = carriedItem.get('count', 1) - 1
			if itemComp.SpawnItemToPlayerCarried(carriedItem, playerId):
				self.OnItemConsumed(itemName)
				return True
			return False
		except Exception as e:
			logger.warning("[Gomoku] ConsumeCarriedItem 失败: {}".format(e))
			return False

	def OnItemConsumed(self, itemName):
		"""物品被用掉（耐久1道具使用/棋子落子）时立刻释放一个刷新空位，下个刷新间隔即可补。
		该物品不是刷新器产出（如挖矿发放的棋子）时没有对应记录，跳过即可（不影响计数下限）"""
		if not itemName:
			return
		expires = self.itemExpireDict.get(itemName)
		if expires:
			# 条目之间无差别，移除任意一条=该单位退场
			expires.pop()
			logger.info("[Gomoku] 物品消耗，释放空位: {} (存量{})".format(
				itemName, len(expires)))

	def GiveItemToPlayer(self, playerId, itemName):
		"""将物品给到玩家背包。组件必须用playerId创建（对照官方模板全部用法，
		levelId创建的组件不能往玩家背包发物品）；自定义物品用newItemName键，
		失败回退itemName键（不同版本支持度不一）"""
		try:
			itemComp = serverApi.GetEngineCompFactory().CreateItem(playerId)
			result = itemComp.SpawnItemToPlayerInv(
				{"newItemName": itemName, "count": 1, "newAuxValue": 0}, playerId)
			if not result:
				result = itemComp.SpawnItemToPlayerInv(
					{"itemName": itemName, "count": 1, "auxValue": 0}, playerId)
			if result:
				logger.info("[Gomoku] 发放物品: {} -> 玩家".format(itemName))
			else:
				logger.warning("[Gomoku] 发放物品失败: {}".format(itemName))
			return result
		except Exception as e:
			logger.warning("[Gomoku] GiveItemToPlayer 失败: {}".format(e))
			return False

	def RunCommand(self, commandStr):
		"""执行命令（同步返回结果，便于打印失败）"""
		commandComp = self.CreateComponent(self.levelId, config.Minecraft, config.CommandComponent)
		result = commandComp.SetCommand(commandStr)
		if result is not None and not result:
			logger.warning("[Gomoku] 命令执行失败: {}".format(commandStr))
		return result

	def Announce(self, text):
		"""全服播报（phase2再做action bar/区分玩家提示）"""
		self.RunCommand('/say {}'.format(text))

	def GetText(self, key, **kwargs):
		"""按key取文案模板并填充命名占位符（模板见messageConfig.MESSAGES）。
		供需要把文本传给别处（OnGameEnd的victoryText/客户端事件text）的场合；
		日常播报直接用Msg/MsgPlayer/MsgThrottled。未知key：记日志并返回key
		本身——测试一眼看到漏配，而不是静默丢消息。格式化失败（缺参/占位符
		打错）：记日志退回未填充模板，不让播报路径抛异常影响玩法逻辑"""
		text = messageConfig.MESSAGES.get(key)
		if text is None:
			logger.warning("[Gomoku] 未知文案key: {}".format(key))
			return key
		if kwargs:
			try:
				return text.format(**kwargs)
			except Exception as e:
				logger.warning("[Gomoku] 文案{}格式化失败: {}".format(key, e))
				return text
		return text

	def Msg(self, key, **kwargs):
		"""全服播报（key版）：Announce的文案表入口"""
		self.Announce(self.GetText(key, **kwargs))

	def MsgPlayer(self, playerId, key, **kwargs):
		"""单玩家私聊（key版）：SendMessageToPlayer的文案表入口"""
		self.SendMessageToPlayer(playerId, self.GetText(key, **kwargs))

	def MsgThrottled(self, playerId, kind, key, **kwargs):
		"""节流播报（key版）。kind沿用旧节流桶字符串（'pieceCap'等），与文案key
		解耦：两个pieceCap变体key不同但kind相同，保持"拾取满/采集满共享节流桶"
		的现有行为不变"""
		self.AnnounceThrottled(playerId, kind, self.GetText(key, **kwargs))

	def Update(self):
		pass

	def Destroy(self):
		self.UnListenEvent()
