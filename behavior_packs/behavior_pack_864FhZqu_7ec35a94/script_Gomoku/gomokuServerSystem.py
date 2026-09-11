# -*- coding: utf-8 -*-
import math
import random
import time

import mod.server.extraServerApi as serverApi
import config
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

	棋局逻辑（占用/终局/五连/平局）全部委托给 modCommon.gomokuCore.GomokuBoard：
	本系统只负责 MC 侧——方块事件、物品消耗、命令放块、跨Mod播报。
	引擎坐标 (x=列, y=行) 与世界坐标的映射：x = 世界X - 棋盘X1，y = 世界Z - 棋盘Z1。

	核心交互：
	1. 手持棋子物品右键棋盘基座 -> 落子（颜色=落子方队伍，消耗棋子）
	2. 左键挖棋子矿 -> 采集（需对应镐，走ServerPlayerTryDestroyBlockEvent；镐耐久1采一次即碎；金矿徒手可挖）
	3. 手持处决剑攻击玩家 -> 一击必杀（剑用一次即碎）
	4. 背包规则：新一局开始清空全体背包；棋子携带上限MaxCarriedPieces个（道具不限），
	   超限时拦截拾取（ServerPlayerTryTouchEvent）并取消挖矿（矿留原地、镐不消耗）

	棋盘位置：以 config.BoardCenter 为中心（唯一事实来源，编辑器里移动棋盘=改这个常量），
	基座 /fill 会覆盖掉Anchor方块本身；资源环（矿/镐/剑）以该中心为圆心按config.SpawnConfigList
	刷新，高度与棋子同一水平面。
	"""

	def __init__(self, namespace, systemName):
		ServerSystem.__init__(self, namespace, systemName)
		self.levelId = serverApi.GetLevelId()
		# 乱斗模式不强制轮流落子，黑白双方均可随时落子
		self.board = GomokuBoard(config.BoardSize, config.BoardSize, enforce_turn=False)
		# 棋盘中心（config.BoardCenter），首次使用时从config取
		self.boardCenter = None
		self.boardBuilt = False
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
		# 节流播报的上次播报时刻（按(玩家,类型)键，防刷屏）
		self.announceThrottleTime = {}
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
			config.ServerPlayerTryDestroyBlockEvent, self, self.OnPlayerTryDestroyBlock)
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
			config.PlayerAttackEntityEvent, self, self.OnPlayerAttack)
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
			config.ServerPlayerTryTouchEvent, self, self.OnPlayerTryTouch)
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
			config.ServerPlayerTryDestroyBlockEvent, self, self.OnPlayerTryDestroyBlock)
		self.UnListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
			config.PlayerAttackEntityEvent, self, self.OnPlayerAttack)
		self.UnListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
			config.ServerPlayerTryTouchEvent, self, self.OnPlayerTryTouch)
		self.UnListenForEvent(config.StartLogicModName, config.StartLogicServerSystemName,
			config.StartLogicEvent, self, self.OnRoundStart)

	def OnTickServer(self):
		CoroutineMgr.Tick()

	# ---------- 生命周期 ----------

	def OnPlayerAdd(self, args):
		playerId = args.get("id", "-1")
		if playerId == "-1":
			return
		if not self.boardBuilt:
			# 等待阶段就尝试铺盘；组件/世界可能未就绪，延迟1秒（避初始化竞态）
			CoroutineMgr.StartCoroutine(self.DelayBuildBoard())

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
			self.Announce("§e新对局开始，已清空背包")
		self.announceThrottleTime = {}
		if not self.boardBuilt:
			self.BuildBoard()
		if self.boardBuilt:
			self.ResetBoard()
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
		"""棋盘基座层的 (x1, y, z1, x2, y, z2)"""
		cx, cy, cz = self.EnsureBoardCenter()
		half = config.BoardSize // 2
		return (cx - half, cy, cz - half, cx + half, cy, cz + half)

	def BuildBoard(self):
		"""以Anchor为中心铺设棋盘基座（基座 /fill 覆盖掉Anchor方块本身），并清空上方旧棋石。
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
		logger.info("[Gomoku] 棋盘已铺设: {} ~ {}".format((x1, y1, z1), (x2, y2, z2)))
		self.ResetBoard()
		return True

	def ResetBoard(self):
		"""清除棋盘上方的全部棋石并重置引擎对局"""
		x1, y1, z1, x2, y2, z2 = self.GetBoardBounds()
		self.RunCommand('/fill {} {} {} {} {} {} air 0 replace'.format(x1, y1 + 1, z1, x2, y2 + 1, z2))
		self.board.reset(config.BoardSize, config.BoardSize, enforce_turn=False)

	def IsOnBoard(self, pos):
		x1, y1, z1, x2, y2, z2 = self.GetBoardBounds()
		return x1 <= pos[0] <= x2 and z1 <= pos[2] <= z2 and pos[1] == y1

	def WorldToBoard(self, pos):
		"""世界坐标 -> 引擎坐标 (x=列, y=行)"""
		x1, y1, z1, x2, y2, z2 = self.GetBoardBounds()
		return pos[0] - x1, pos[2] - z1

	def BoardToWorld(self, bx, by):
		"""引擎坐标 -> 棋石世界坐标（基座上方一格）"""
		x1, y1, z1, x2, y2, z2 = self.GetBoardBounds()
		return (x1 + bx, y1 + 1, z1 + by)

	# ---------- 资源刷新 ----------

	def StartSpawners(self):
		for spawnConfig in config.SpawnConfigList:
			coroutineIter = CoroutineMgr.StartCoroutine(self.DelaySpawn(spawnConfig))
			self.spawnCoroutines.append(coroutineIter)
		# 道具等级池刷新协程（镐/剑/墨水/雷管等，共用等级上限，见ItemTierDict）
		for tierKey, tierCfg in config.ItemTierDict.iteritems():
			coroutineIter = CoroutineMgr.StartCoroutine(self.DelayTierSpawn(tierKey, tierCfg))
			self.spawnCoroutines.append(coroutineIter)
		# 矿石存量重扫协程（只启动一次，跨回合常驻）：开局立即全环数一遍（兼容存档残留的矿），
		# 此后按RecountIntervalSeconds周期重扫修正实时计数的误差
		if self.recountCoroutine is None:
			self.recountCoroutine = CoroutineMgr.StartCoroutine(self.RecountOres())
		logger.info("[Gomoku] 资源刷新已启动，共{}个刷新点+{}个道具等级池".format(
			len(config.SpawnConfigList), len(config.ItemTierDict)))

	def DelaySpawn(self, spawnConfig):
		while True:
			yield -spawnConfig['interval'] * 30
			self.SpawnAtRing(spawnConfig)

	def DelayTierSpawn(self, tierKey, tierCfg):
		while True:
			yield -tierCfg['interval'] * 30
			self.SpawnTierItem(tierKey, tierCfg)

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
		防止玩家站在物品上时每帧重触发本事件"""
		itemDict = args.get('itemDict') or {}
		if self.GetItemName(itemDict) not in config.PieceItemNameSet:
			return
		playerId = args.get('playerId')
		if not playerId:
			return
		if self.CountCarriedPieces(playerId) + itemDict.get('count', 1) > config.MaxCarriedPieces:
			args['cancel'] = True
			args['pickupDelay'] = config.FullPickupDelayFrames
			self.AnnounceThrottled(playerId, 'pieceCap',
				"§c棋子携带已达上限{}个，先落子或用掉再拾取".format(config.MaxCarriedPieces))

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
			for spawnConfig in config.SpawnConfigList:
				if spawnConfig['type'] != 'ore':
					continue
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
		if blockName == config.ChessBaseBlockName:
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
		# 只处理棋子/墨水/雷管物品：镐/剑等右键基座无动作
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
		if itemType != 'piece':
			return
		# 点击位置须是棋盘基座（棋盘9x9范围内y=基座层的方块只有基座，直接用范围判定）
		if not self.IsOnBoard(pos):
			return
		self.HandlePlace(playerId, pos)

	def HandlePlace(self, playerId, pos):
		"""手持棋子物品右键棋盘基座 -> 落子（占用/终局校验与胜负判定委托给引擎）"""
		carriedItem = self.GetCarriedItemName(playerId)
		side = self.GetPlayerSide(playerId)
		logger.info("[Gomoku] 落子请求: pos={} 手持={} 阵营={}".format(pos, carriedItem, side))
		if not self.IsOnBoard(pos):
			# 原为静默return，加日志便于排查点击位置和棋盘范围不吻合的情况
			logger.warning("[Gomoku] 落子点不在棋盘上: {} (棋盘范围 {})".format(pos, self.GetBoardBounds()))
			return
		bx, by = self.WorldToBoard(pos)
		if self.board.state != STATE_PLAYING:
			self.Announce("§c对局已结束，请等待下一轮")
			return
		if self.board.get(bx, by) != EMPTY:
			self.Announce("§c此处已有棋子")
			return
		if side is None:
			self.Announce("§c落子需要先加入队伍")
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
			self.Announce("§c请手持棋子右键棋盘落子")
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
		stonePos = self.BoardToWorld(bx, by)
		self.RunCommand('/setblock {} {} {} {}'.format(stonePos[0], stonePos[1], stonePos[2], stoneName))
		result = self.PlaceInEngine(bx, by, player)
		logger.info("[Gomoku] 落子: {} {} {}".format(stonePos, player, carriedItem))
		if result.state == STATE_WON:
			self.OnGameEnd(result.winning_player, result.winning_lines)
		elif result.state == STATE_DRAW:
			self.OnGameEnd(None, [])

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

	def HandleInkUse(self, playerId, pos):
		"""手持墨水右键棋盘上的棋石 -> 转化为己方颜色（墨水耐久1，用一次即碎）。
		只对敌方黑/白棋石生效：金棋子无阵营不可转化，己方棋石无需转化。
		硬化属性保留（墨水只换颜色不换材质）；引擎侧先删旧子再落新子（同格改值），
		转化补齐五连同 normal 落子一样判胜"""
		x1, y1, z1, x2, y2, z2 = self.GetBoardBounds()
		if not (x1 <= pos[0] <= x2 and z1 <= pos[2] <= z2 and pos[1] == y1 + 1):
			return  # 点击的不是棋盘落子层（与HandleStoneBreak同判定）
		if self.board.state != STATE_PLAYING:
			self.Announce("§c对局已结束，请等待下一轮")
			return
		side = self.GetPlayerSide(playerId)
		if side is None:
			self.Announce("§c使用墨水需要先加入队伍")
			return
		blockName = self.GetBlockName(pos)
		stoneSide = config.StoneSideDict.get(blockName) if blockName else None
		if stoneSide is None:
			return  # 落子层但不是棋石（正常不会有），静默忽略
		if stoneSide == 'gold':
			self.Announce("§c金棋子无阵营，墨水对它无效")
			return
		if stoneSide == side:
			self.Announce("§c这是己方棋子，不需要墨水")
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
		bx, by = self.WorldToBoard(pos)
		self.RunCommand('/setblock {} {} {} {}'.format(pos[0], pos[1], pos[2], stoneName))
		# 引擎同步：remove+place（remove失败=计数脱同步，place会自愈补上该格）
		self.board.remove(bx, by)
		result = self.PlaceInEngine(bx, by, player)
		self.Announce("§5一瓶墨水泼下，§6{}§5的一枚棋子被转化了！".format(
			config.SideNameDict.get(stoneSide, stoneSide)))
		logger.info("[Gomoku] 墨水转化: {} {} -> {} ({})".format(pos, blockName, stoneName, playerId))
		if result.state == STATE_WON:
			self.OnGameEnd(result.winning_player, result.winning_lines)
		elif result.state == STATE_DRAW:
			self.OnGameEnd(None, [])

	def HandleBombUse(self, playerId, pos):
		"""手持爆炸雷管右键棋盘（基座或棋石均可）-> 像原生方块一样贴着点击处
		摆出一个已点燃的雷管方块（TNT外观），BombFuseSeconds秒后引爆（见BombFuse）。
		摆放不替换任何方块：点击列的落子层(y1+1)有棋石 -> 叠在棋石上方(y1+2)；
		空 -> 直接放在落子层。爆炸清以雷管方块为中心的立方体
		（BombBlastRange=3即3x3x3）内的全部棋石，不分敌我、不分颜色
		（金棋子照炸）；只清棋石，基座与地形无损（不留坑）。雷管耐久1"""
		x1, y1, z1, x2, y2, z2 = self.GetBoardBounds()
		if not (x1 <= pos[0] <= x2 and z1 <= pos[2] <= z2 and pos[1] in (y1, y1 + 1, y1 + 2)):
			return  # 点击目标不在棋盘上，不响应
		if self.board.state != STATE_PLAYING:
			self.Announce("§c对局已结束，请等待下一轮")
			return
		# 摆放位置：优先落子层；该列落子层被棋石占着就叠上去（不替换）
		bombPos = (pos[0], y1 + 1, pos[2])
		if self.GetBlockName(bombPos) in config.StoneBlockNameSet:
			bombPos = (pos[0], y1 + 2, pos[2])
		if self.GetBlockName(bombPos) == config.DetonatorBlockName:
			self.Announce("§c这里已经有一根点燃的雷管了")
			return
		if not self.ConsumeCarriedItem(playerId):
			return
		self.RunCommand('/setblock {} {} {} {}'.format(bombPos[0], bombPos[1], bombPos[2], config.DetonatorBlockName))
		self.Announce("§c引信已点燃，快跑！")
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
					bx, by = self.WorldToBoard(cellPos)
					self.board.remove(bx, by)  # 超界/已空返回not ok，忽略即可
					removed += 1
		self.RunCommand('/setblock {} {} {} air'.format(*bombPos))
		if removed:
			self.Announce("§c轰！爆炸雷管炸掉了{}枚棋子".format(removed))
		else:
			self.Announce("§e轰！爆炸雷管炸了个空（范围内没有棋子）")
		logger.info("[Gomoku] 雷管引爆: {} 炸除{}枚 扫描到: {}".format(bombPos, removed, seenNames))

	def OnPlayerTryDestroyBlock(self, args):
		"""左键挖掘入口（挖穿前触发）：矿->采集（普通/硬化矿需对应镐，金矿徒手可挖）；
		棋盘棋石->挖掉即销毁并释放引擎格子（普通3秒/硬化10秒由方块destroy_time控制）；
		棋盘基座->一律取消挖掘（不依赖destroy_time硬扛，脚本层直接cancel；
		将来实现特殊道具时在此按手持道具放行）。棋子携带已满（MaxCarriedPieces）时
		取消挖掘，矿保留原地、镐不消耗。工具校验采用原版语义——工具不对照样允许挖穿
		（不打断长按连续挖掘），只是拿不到棋子；挖穿后矿不产生原版掉落，棋子由脚本发到
		背包；镐耐久1，采一次即碎。事件字段对照官方模板：fullName/x/y/z/playerId/cancel/spawnResources"""
		if not self.loggedTryDestroyEvent:
			logger.info("[Gomoku] ServerPlayerTryDestroyBlockEvent raw: {}".format(args))
			self.loggedTryDestroyEvent = True
		blockName = args.get('fullName', '')
		if blockName == config.ChessBaseBlockName:
			# 基座不可破坏：脚本直接取消（与棋子上限拦截同款机制，不靠destroy_time限制）
			args['cancel'] = True
			playerId = args.get('playerId')
			if playerId:
				self.AnnounceThrottled(playerId, 'baseBreak', "§c棋盘基座无法被破坏")
			return
		if blockName not in config.OrePieceItemDict:
			if blockName in config.StoneBlockNameSet:
				self.HandleStoneBreak(args)
			elif blockName == config.DetonatorBlockName:
				# 引爆前把雷管方块挖掉=拆除（销毁无掉落）；引信协程到点发现方块没了会自行取消
				args['spawnResources'] = False
				self.Announce("§e一枚雷管被及时拆除了")
			return
		playerId = args.get('playerId')
		if playerId and self.CountCarriedPieces(playerId) >= config.MaxCarriedPieces:
			# 棋子携带已满：取消挖掘（矿留在原地、镐不消耗、存量计数不动）
			args['cancel'] = True
			self.AnnounceThrottled(playerId, 'pieceCap',
				"§c棋子携带已达上限{}个，先落子或用掉再采集".format(config.MaxCarriedPieces))
			return
		# 矿被挖碎（无论工具对错，方块都会消失）：存量计数-1
		self.oreCountDict[blockName] = self.oreCountDict.get(blockName, 0) - 1
		if not playerId:
			return
		# 反查该矿要求的镐（金矿无要求，徒手可挖）
		requiredPickaxe = None
		for pickaxe, ore in config.PickaxeOreDict.iteritems():
			if ore == blockName:
				requiredPickaxe = pickaxe
				break
		if requiredPickaxe is not None:
			carriedItem = self.GetCarriedItemName(playerId)
			if carriedItem is None:
				logger.warning("[Gomoku] 无法读取手持物品，按无镐处理")
				carriedItem = ''
			if carriedItem != requiredPickaxe:
				# 没拿对应的镐：允许挖穿（保持长按连续挖掘），但没有棋子——原版"徒手挖铁矿"体验
				args['spawnResources'] = False
				self.Announce("§c矿挖碎了，但没有{}，棋子没有掉落".format(config.ItemTable[requiredPickaxe]['name']))
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
			self.Announce("§c棋子发放失败，矿稍后还原，请联系开发者查日志")
		else:
			logger.info("[Gomoku] 挖矿采集: {} -> {} @ ({}, {}, {})".format(
				blockName, config.OrePieceItemDict[blockName], args.get('x'), args.get('y'), args.get('z')))

	def HandleStoneBreak(self, args):
		"""棋盘棋石被挖掉（普通/硬化/gold同规则）：挖掉即销毁、无掉落，
		并释放引擎中对应格子（被挖掉的子不再占线）；硬化棋石挖掘更久，由方块destroy_time控制"""
		pos = (args.get('x'), args.get('y'), args.get('z'))
		if None in pos:
			return
		args['spawnResources'] = False  # 策划案：被破坏的棋子一律销毁，不产生掉落
		x1, y1, z1, x2, y2, z2 = self.GetBoardBounds()
		if not (x1 <= pos[0] <= x2 and z1 <= pos[2] <= z2 and pos[1] == y1 + 1):
			return  # 不在棋盘落子层的棋石（正常不会有），仅销毁
		bx, by = self.WorldToBoard(pos)
		removeResult = self.board.remove(bx, by)
		if removeResult.ok:
			logger.info("[Gomoku] 棋石被挖除: {} @ 引擎坐标{}".format(args.get('fullName'), (bx, by)))
			self.Announce("§e棋盘上一枚棋子被挖掉了")

	def DelayRestoreOre(self, pos, blockName):
		"""挖穿事件后再把矿补回原地（事件先于方块真正消失，需延迟几帧）；补回后存量计数+1"""
		yield -10
		if self.RunCommand('/setblock {} {} {} {}'.format(pos[0], pos[1], pos[2], blockName)):
			self.oreCountDict[blockName] = self.oreCountDict.get(blockName, 0) + 1

	# ---------- 交互：武器 ----------

	def OnPlayerAttack(self, args):
		"""手持武器（道具表type=weapon）攻击玩家 -> 按表内伤害加成，一次性武器随之销毁。
		damage须与isValid成对设置才生效（对照官方PVP模板script_Team的队友免伤写法，
		只设damage引擎会忽略脚本伤害值）"""
		attackerId = args.get('playerId')
		victimId = args.get('victimId')
		if not attackerId or not victimId:
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
		args['damage'] = itemCfg.get('damage', config.DefaultWeaponDamage)
		args['isValid'] = 1
		if itemCfg.get('consumable') and self.ConsumeCarriedItem(attackerId):
			self.Announce("§c{}出鞘！一击必杀！".format(itemCfg['name']))

	# ---------- 胜负播报 ----------

	def OnGameEnd(self, winnerPlayer, winningLines):
		"""对局结束：本地播报 + 通知客户端，并调EndLogic结算本局、重启下一轮。
		winnerPlayer为None表示平局；winningLines转世界坐标供客户端高亮。
		结算走EndLogic.ExternalSettleGame（作废定时器+通知胜利+自动重启），
		不再只调NotifyVictory（那只是播报，本局不会结束，超时结算照常触发）"""
		logger.info("[Gomoku] 对局结束: 胜方棋子值={} 连珠线={}".format(winnerPlayer, winningLines))
		if winnerPlayer is None:
			winnerSide = None
			sideText = "平局"
			self.Announce("§e棋盘已满，双方平局！")
			victoryText = "§e棋盘已满，双方平局！"
		else:
			winnerSide = 'black' if winnerPlayer == BLACK else 'white'
			sideText = config.SideNameDict.get(winnerSide, winnerSide)
			self.Announce("§6{}§f在棋盘上连成五子，赢得对局！".format(sideText))
			victoryText = "§6{}§f在棋盘上连成五子，赢得对局！".format(sideText)
		data = self.CreateEventData()
		data['winner'] = winnerSide
		data['text'] = "§6{}§f{}".format(sideText, "获得五子棋对局胜利" if winnerSide else "结束五子棋对局")
		data['winningLines'] = [
			[list(self.BoardToWorld(bx, by)) for bx, by in line]
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
			self.Announce("§e未找到EndLogic组件，仅做本地播报")

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

	def Update(self):
		pass

	def Destroy(self):
		self.UnListenEvent()
