# -*- coding: utf-8 -*-
# =====================================================================
# 陷阱模式（config.GameMode = "trap"）
#
# 玩法：地面完全不动——不整平、不铺伪装层，保留地图原地形（本图陷阱区
# 地表本来就是基岩，挖不动，不存在"挖土打洞绕过雷区"）。陷阱只是脚本
# 数据：棋盘外围两圈（SafeRingWidth）是安全区；再往外随机撒若干"道具
# 生成点"，每个生成点向棋盘安全区长一条安全路。路上的格子是安全的，
# 路外的格子是陷阱——踩上去脚下的地表方块临时换成岩浆、掉血、被弹回
# 上一个踩过的安全格；LavaRestoreSeconds 秒后复原成触发前记下的原方块
# （这格仍然是陷阱，只是又看不出来了）。
# 资源（棋子矿/棋子/道具/问号方块）只刷在安全格上，安全区里一律不刷；
# 陷阱格所在的整条竖列禁止放任何方块（不许搭桥铺路过雷区）。
#
# 与宿主的接口只有 baseMode.GameModeBase 的那几个钩子，数值全在
# trapModeConfig.py——本文件不写死任何可调参数。
# =====================================================================
import math
import random
import time

import mod.server.extraServerApi as serverApi

# ★全部改成显式相对导入：本包是 script_Gomoku.gameModes 子包，宿主的
# config.py / coroutineMgrGas.py、本包的兄弟模块都不在 SDK 的绝对导入
# 搜索路径上，绝对导入会 ImportError（运行日志已实测）。
# 同款写法见 script_Team 的 modServer/modCommon 结构。
from .. import config
from ..coroutineMgrGas import CoroutineMgr
from .baseMode import GameModeBase
from . import trapModeConfig as trapConfig

from mod_log import logger


class TrapMode(GameModeBase):
	Key = "trap"
	Name = "陷阱模式"
	# 开局播报带踩雷警示（文案见messageConfig的mode_段；以前这句写死在
	# OnRoundStart里，现在统一由宿主SwitchGameModeForRound播）
	RoundAnnounceKey = "mode_round_trap"

	def __init__(self, serverSystem):
		GameModeBase.__init__(self, serverSystem)
		# 每列立足面高度缓存 {(x, z): surfaceY}（原地形有起伏，没有统一的
		# "整平层Y"了；查询走宿主 FindSurfaceY，OnRoundStart 清空重记）
		self.surfaceDict = {}
		# 安全区半边长 = 棋盘半边长 + SafeRingWidth（棋盘随人数扩容，每局重算）
		self.safeHalf = 0
		# 陷阱区内踩了不触发陷阱的安全格（路径格+生成点格；安全圈不在内，另行兜底）
		self.safeCells = set()
		# 陷阱格（踩上去要命的那些）。★注意别与宿主的 self.trapCells 搞混：
		# 那个是"陷阱棋子"道具的雷区，两件事完全无关
		self.trapCells = set()
		# 本局的道具生成点 [(x, z), ...]
		self.spawnPoints = []
		# 环距 -> 该环距上的安全格列表（资源刷新按环取点用，开局算好省得每次筛）
		self.safeByRing = {}
		# 每名玩家最后一次站稳的安全格（踩雷后弹回这里）
		self.lastSafeCellDict = {}
		# 正在冒岩浆、等着复原的格子（防同一格重复起协程）
		self.pendingLavaCells = set()
		# 冒岩浆的格 -> 触发前那格地表的原方块名（复原时换回去用）
		self.lavaOrigBlockDict = {}
		# 刷新落点的实心过滤缓存 {(x, z): bool}：该列地表能不能刷东西。
		# FindSurfaceY 含树叶，不过滤的话矿石/道具会刷在树冠顶上够不着；
		# 一格一局只查一次，OnRoundStart 清空重记
		self.spawnableGroundDict = {}
		# 提示节流：playerId -> 上次提示的时刻
		self.tipTimeDict = {}
		self.tickCounter = 0
		# 局号：每局+1。复原协程醒来时核对，防上一局的协程误收新一局的岩浆格
		self.roundEpoch = 0
		# 地形与路径是否已生成（没生成前一切判定都不生效，避免开局竞态误伤）
		self.built = False

	# ---------------------------- 生命周期 ----------------------------

	def OnEnter(self):
		logger.info("[Gomoku] 玩法模式: {}（陷阱区半边长{}格、安全圈{}圈）".format(
			self.Name, trapConfig.AreaRadius, trapConfig.SafeRingWidth))

	def OnRoundStart(self):
		"""每局重掷：宿主已经把棋盘基座整层重铺、随机好缺格，这里先把上一局
		残留的岩浆复原掉，再重新撒生成点、长路径。地面原样不动（不整平
		不铺面），陷阱/安全全在脚本数据里"""
		self.built = False
		self.roundEpoch += 1
		# 不再整平重铺，残留的岩浆必须显式收回（此时surfaceDict还是旧缓存，
		# 正好用来定位上一局的地表）；收完再清缓存进新局
		self.RestoreAllLava()
		self.surfaceDict = {}
		self.spawnableGroundDict = {}
		self.lastSafeCellDict = {}
		self.tipTimeDict = {}
		cx, cy, cz = self.system.EnsureBoardCenter()
		boardHalf = self.system.boardSize // 2
		self.safeHalf = boardHalf + max(1, trapConfig.SafeRingWidth)
		if self.safeHalf >= trapConfig.AreaRadius:
			logger.warning("[Gomoku] 陷阱模式：安全圈({})已盖满陷阱区({})，本局没有陷阱格".format(
				self.safeHalf, trapConfig.AreaRadius))
		self.GeneratePaths(cx, cz)
		self.built = True
		logger.info("[Gomoku] 陷阱模式已布好：生成点{}个 / 安全格{}个 / 陷阱格{}个".format(
			len(self.spawnPoints), len(self.safeCells), len(self.trapCells)))
		# 模式播报由宿主统一做（SwitchGameModeForRound -> messageConfig的
		# mode_round_trap，RoundAnnounceKey指过去）
		# 开局落位：等StartLogic把玩家摆到队伍落点后，再把全体拉进安全圈
		CoroutineMgr.StartCoroutine(self.DelayRoundStartTeleport(self.roundEpoch))

	def OnPlayerAdd(self, playerId):
		self.lastSafeCellDict.pop(playerId, None)
		# 进图默认落点（世界出生点）在远处未加载区块：等玩家就绪后，离棋盘
		# 还很远就拉进安全圈（等待区/队伍落点不受影响，阈值见JoinTeleportRing）
		CoroutineMgr.StartCoroutine(self.DelayJoinTeleport(playerId))

	def OnPlayerRemove(self, playerId):
		self.lastSafeCellDict.pop(playerId, None)
		self.tipTimeDict.pop(playerId, None)

	def OnPlayerDie(self, playerId):
		"""阵亡：清掉"上一个安全格"（否则复活后第一次踩雷会被弹回死亡现场），
		并在引擎重生流程走完后把人拉到棋盘边的安全区"""
		self.lastSafeCellDict.pop(playerId, None)
		CoroutineMgr.StartCoroutine(self.TeleportAfterRespawn(playerId))

	def TeleportAfterRespawn(self, playerId):
		yield -trapConfig.RespawnTeleportDelayFrames
		cell = self.GetSafeCell()
		if self.SetFootPos(playerId, self.CellFootPos(cell)):
			self.lastSafeCellDict[playerId] = cell

	def DelayJoinTeleport(self, playerId):
		"""进图落位：延迟读坐标（刚进服可能还没就绪），离棋盘超过
		JoinTeleportRing 才拉——等待区/队伍落点都在阈值内，不会被误拉"""
		yield -trapConfig.JoinTeleportDelayFrames
		footPos = self.GetFootPos(playerId)
		if not footPos:
			return
		cx, _, cz = self.system.EnsureBoardCenter()
		cell = (int(math.floor(footPos[0])), int(math.floor(footPos[2])))
		if self.Ring(cx, cz, cell[0], cell[1]) <= trapConfig.JoinTeleportRing:
			return
		self.TeleportToSafeRing(playerId)

	def DelayRoundStartTeleport(self, epoch):
		"""开局落位：StartLogic先按队伍落点传送（都在陷阱区外），之后把全体
		拉进棋盘安全圈。局号对不上=期间又重开了一局，这趟别再传（新一局
		会自己再拉一次）"""
		yield -trapConfig.RoundStartTeleportDelayFrames
		if epoch != self.roundEpoch:
			return
		for playerId in list(self.system.playerIds):
			self.TeleportToSafeRing(playerId)

	def TeleportToSafeRing(self, playerId):
		"""把玩家传到安全圈外沿的一格上（安全区内任何格都不是陷阱），
		并记成他的"最近安全格"——踩雷弹回有落点"""
		cell = self.PickSafeRingCell()
		if self.SetFootPos(playerId, self.CellFootPos(cell)):
			self.lastSafeCellDict[playerId] = cell
			logger.info("[Gomoku] 陷阱模式：玩家已落位安全圈 {}".format(cell))

	def PickSafeRingCell(self):
		"""安全圈外沿一圈上随机一格（每人分开站，不叠在同一个点上）"""
		cx, _, cz = self.system.EnsureBoardCenter()
		h = self.safeHalf or (self.system.boardSize // 2 + max(1, trapConfig.SafeRingWidth))
		side = random.randint(0, 3)
		off = random.randint(-h, h)
		if side == 0:
			return (cx + off, cz - h)
		if side == 1:
			return (cx + off, cz + h)
		if side == 2:
			return (cx - h, cz + off)
		return (cx + h, cz + off)

	def OnExit(self):
		self.built = False
		self.RestoreAllLava()

	# ---------------------------- 地面：按列取地表 ----------------------------

	def GetSurfaceY(self, cell):
		"""该列的立足面高度（最高非空气方块的上表面，含树叶）。原地形有起伏，
		没有统一的地层Y，一切高度判定（踩雷高度带/岩浆摆放/弹回落点/生成点
		标记）都按列查地表；结果本局内缓存。查询失败返回None（调用方各自兜底）"""
		if cell not in self.surfaceDict:
			self.surfaceDict[cell] = self.system.FindSurfaceY(cell[0], cell[1])
		return self.surfaceDict[cell]

	def GetGroundBlockName(self, cell, surfaceY):
		"""该列地表方块名（触发岩浆前先记下来，复原时换回去）。
		查询失败退回 RestoreFallbackBlockName（本图陷阱区地表本来就是基岩）"""
		try:
			blockInfoComp = serverApi.GetEngineCompFactory().CreateBlockInfo(
				config.MainDimensionId)
			blockDict = blockInfoComp.GetBlockNew(
				(cell[0], surfaceY - 1, cell[1]), config.MainDimensionId)
			if blockDict and blockDict.get('name'):
				return blockDict.get('name')
		except Exception as e:
			logger.warning("[Gomoku] 查地表方块失败 {}: {}".format(cell, e))
		return trapConfig.RestoreFallbackBlockName

	def IsSpawnableGround(self, cell):
		"""该列地表是不是"实心可站"的地面：树叶（树冠）、树干、水面这类
		顶上站不住/够不着的列不算——FindSurfaceY 含树叶，不过滤的话矿石和
		道具会刷在树顶上，玩家根本拿不到。结果按格缓存（一格一局只查一次，
		查询走 GetGroundBlockName，失败退基岩=算实心，与本图地面一致）"""
		if cell in self.spawnableGroundDict:
			return self.spawnableGroundDict[cell]
		ok = False
		surfaceY = self.GetSurfaceY(cell)
		if surfaceY is not None:
			name = self.GetGroundBlockName(cell, surfaceY)
			if name and not any(word in name for word in trapConfig.NonGroundBlockKeywords):
				ok = True
		self.spawnableGroundDict[cell] = ok
		return ok

	# ---------------------------- 路径生成 ----------------------------

	def Ring(self, cx, cz, x, z):
		"""切比雪夫环距（= 方形圈的圈号，与棋盘随机化用的是同一套距离）"""
		return max(abs(x - cx), abs(z - cz))

	def GeneratePaths(self, cx, cz):
		"""先撒生成点，再一条一条长路；剩下的格子全是陷阱。

		顺序刻意是"先路后陷阱"（而不是先随机陷阱再挖路）：这样哪些格子是安全的
		由路径唯一决定，资源刷新只要在安全格里取点就绝不会刷到陷阱上。
		"""
		R = trapConfig.AreaRadius
		self.spawnPoints = self.PickSpawnPoints(cx, cz)
		solid = set()
		for point in self.spawnPoints:
			solid.update(self.BuildPath(point, cx, cz))
		if trapConfig.PathWidth > 1:
			solid = self.WidenPath(solid)
		# 只保留陷阱区内、安全区外的格子：安全区本来就是安全的，不进这张表
		# （资源不刷在安全区 = 需求里明确的"棋盘安全区不要生成任何棋子和道具"）
		self.safeCells = set(
			cell for cell in solid
			if self.safeHalf < self.Ring(cx, cz, cell[0], cell[1]) <= R)
		self.trapCells = set()
		self.safeByRing = {}
		for x in range(cx - R, cx + R + 1):
			for z in range(cz - R, cz + R + 1):
				ring = self.Ring(cx, cz, x, z)
				if ring <= self.safeHalf:
					continue
				cell = (x, z)
				if cell in self.safeCells:
					self.safeByRing.setdefault(ring, []).append(cell)
				else:
					self.trapCells.add(cell)

	def PickSpawnPoints(self, cx, cz):
		"""在指定环距带里随机挑 SpawnPointCount 个互相间隔够远的生成点。
		候选先打乱再按间距筛选——放不下就少放几个，不做重试循环（不会卡住）"""
		lo, hi = trapConfig.SpawnPointRadiusRange
		lo = max(int(lo), self.safeHalf + 1)
		hi = min(int(hi), trapConfig.AreaRadius)
		if hi < lo:
			hi = lo
		candidates = []
		for x in range(cx - hi, cx + hi + 1):
			for z in range(cz - hi, cz + hi + 1):
				if lo <= self.Ring(cx, cz, x, z) <= hi:
					candidates.append((x, z))
		if not candidates:
			return []
		random.shuffle(candidates)
		gap = max(0, trapConfig.SpawnPointMinGap)
		points = []
		for cell in candidates:
			if len(points) >= trapConfig.SpawnPointCount:
				break
			tooClose = False
			for other in points:
				if max(abs(cell[0] - other[0]), abs(cell[1] - other[1])) < gap:
					tooClose = True
					break
			if not tooClose:
				points.append(cell)
		if not points:
			points.append(candidates[0])
		return points

	def PickEntryCell(self, sx, sz, cx, cz):
		"""路的另一端：安全区边界上、朝着生成点那一侧的一格（沿边随机偏移，
		免得每条路都从正中间接进来）"""
		h = self.safeHalf
		dx, dz = sx - cx, sz - cz
		if abs(dx) >= abs(dz):
			return (cx + (h if dx >= 0 else -h), cz + random.randint(-h, h))
		return (cx + random.randint(-h, h), cz + (h if dz >= 0 else -h))

	def BuildPath(self, start, cx, cz):
		"""从生成点走一条格路到安全区边界。

		走法：每步只往目标方向走一格（单调，所以必然收敛），并粘着上一步的轴——
		只有 random() < PathTurnChance 时才换轴，于是路是几段直线拼起来的折线
		（拐弯少、好认），而不是每步乱扭的锯齿。
		"""
		x, z = start
		ex, ez = self.PickEntryCell(x, z, cx, cz)
		cells = set()
		cells.add((x, z))
		axis = None
		# 步数上限：单调走法最多 |dx|+|dz| 步，留一倍余量防意外死循环
		guard = 4 * trapConfig.AreaRadius + 8
		while (x, z) != (ex, ez) and guard > 0:
			guard -= 1
			needX, needZ = ex - x, ez - z
			if needX and needZ:
				if axis is None or random.random() < trapConfig.PathTurnChance:
					axis = 'x' if random.random() < 0.5 else 'z'
			elif needX:
				axis = 'x'
			else:
				axis = 'z'
			if axis == 'x' and needX == 0:
				axis = 'z'
			elif axis == 'z' and needZ == 0:
				axis = 'x'
			if axis == 'x':
				x += 1 if needX > 0 else -1
			else:
				z += 1 if needZ > 0 else -1
			cells.add((x, z))
		return cells

	def WidenPath(self, cells):
		"""按 PathWidth 加宽路径（切比雪夫膨胀）。有效宽度只能是奇数：
		宽度2会被当成1、宽度4当成3（膨胀半径 = (PathWidth-1)//2）"""
		radius = (trapConfig.PathWidth - 1) // 2
		if radius <= 0:
			return cells
		widened = set()
		for x, z in cells:
			for dx in range(-radius, radius + 1):
				for dz in range(-radius, radius + 1):
					widened.add((x + dx, z + dz))
		return widened

	# ---------------------------- 每帧：踩雷检查 ----------------------------

	def OnTick(self):
		if not self.built or not self.trapCells:
			return
		self.tickCounter += 1
		if self.tickCounter % max(1, trapConfig.CheckIntervalFrames) != 0:
			return
		for playerId in list(self.system.playerIds):
			try:
				self.CheckPlayer(playerId)
			except Exception as e:
				logger.warning("[Gomoku] 陷阱检查异常 {}: {}".format(playerId, e))

	def CheckPlayer(self, playerId):
		"""看这名玩家脚下那一格：是陷阱格就触发，是安全格就记成最近的安全落点"""
		footPos = self.GetFootPos(playerId)
		if not footPos:
			return
		x, y, z = footPos
		cell = (int(math.floor(x)), int(math.floor(z)))
		cx, _, cz = self.system.EnsureBoardCenter()
		if self.Ring(cx, cz, cell[0], cell[1]) > trapConfig.AreaRadius:
			return  # 跑出陷阱区了（原生地形），本模式不管
		# 只认站在这一列地表上的人：飞在上空/挖到地下的都不算踩上来。
		# TriggerMaxHeight=1.6 高于原版跳跃峰值(约1.25)，所以蹦跳也躲不过陷阱
		surfaceY = self.GetSurfaceY(cell)
		if surfaceY is None:
			return
		if abs(y - surfaceY) > trapConfig.TriggerMaxHeight:
			return
		if cell in self.trapCells:
			self.TriggerTrap(playerId, cell)
		else:
			self.lastSafeCellDict[playerId] = cell

	def TriggerTrap(self, playerId, cell):
		"""踩中陷阱：脚下的地表方块临时换成岩浆 -> 掉血 -> 弹回上一个安全格"""
		if self.system.IsRespawnHeld(playerId):
			return  # 复活封锁期免疫（与宿主的伤害免疫口径一致）
		x, z = cell
		if cell not in self.pendingLavaCells:
			surfaceY = self.GetSurfaceY(cell)
			if surfaceY is None:
				pass  # 地表都查不到就不起岩浆，伤害与弹回照常
			else:
				self.pendingLavaCells.add(cell)
				# 先记下原方块再换岩浆，复原时换回去（查询失败退基岩）
				self.lavaOrigBlockDict[cell] = self.GetGroundBlockName(cell, surfaceY)
				self.system.RunCommand('/setblock {} {} {} {}'.format(
					x, surfaceY - 1, z, trapConfig.LavaBlockName))
				CoroutineMgr.StartCoroutine(self.RestoreLava(cell, self.roundEpoch))
		if trapConfig.StepDamage > 0:
			try:
				hurtComp = serverApi.GetEngineCompFactory().CreateHurt(playerId)
				# cause=lava：死亡播报与掉进岩浆一致。伤害来源不是玩家，
				# 所以反伤药水刻意不会对陷阱触发——踩雷是自己的锅
				hurtComp.Hurt(trapConfig.StepDamage, 'lava', None, None, False)
			except Exception as e:
				logger.warning("[Gomoku] 陷阱伤害失败: {}".format(e))
		target = self.lastSafeCellDict.get(playerId)
		if target is None:
			target = self.GetSafeCell()  # 没走过安全格（例如刚被传送进来）就回安全区
		self.SetFootPos(playerId, self.CellFootPos(target))
		self.Tip(playerId, "§c脚下是陷阱！§f已被弹回上一处安全地面")

	def RestoreLava(self, cell, epoch):
		"""岩浆 LavaRestoreSeconds 秒后复原成触发前的原方块——这格仍然是
		陷阱，只是重新伪装好了（下一个人照样会踩）。epoch=触发时的局号：
		醒来时对不上（已重开一局）就不管，新一局同格的岩浆归新协程管"""
		yield -int(trapConfig.LavaRestoreSeconds * 30)
		# 局号对不上/不在pending里=已被RestoreAllLava提前收回或换了新局，别再写
		if epoch != self.roundEpoch or cell not in self.pendingLavaCells:
			return
		self.pendingLavaCells.discard(cell)
		origName = self.lavaOrigBlockDict.pop(cell, trapConfig.RestoreFallbackBlockName)
		surfaceY = self.GetSurfaceY(cell)
		if surfaceY is None:
			return
		self.system.RunCommand('/setblock {} {} {} {}'.format(
			cell[0], surfaceY - 1, cell[1], origName))

	def RestoreAllLava(self):
		"""把还亮着的岩浆格全部复原成原方块并清空登记。以前整平重铺会顺手
		盖掉残留岩浆；现在地面一格都不动，重开一局/退出模式前必须显式收回，
		否则那格岩浆会永久留在场上。用surfaceDict的旧缓存定位地表（岩浆
		替换不改变列高，旧值仍然准确）"""
		for cell in list(self.pendingLavaCells):
			surfaceY = self.GetSurfaceY(cell)
			origName = self.lavaOrigBlockDict.pop(cell, trapConfig.RestoreFallbackBlockName)
			if surfaceY is not None:
				self.system.RunCommand('/setblock {} {} {} {}'.format(
					cell[0], surfaceY - 1, cell[1], origName))
		self.pendingLavaCells = set()
		self.lavaOrigBlockDict = {}

	# ---------------------------- 建造限制 ----------------------------

	def CanPlaceBlock(self, entityId, x, y, z):
		"""陷阱格所在的整条竖列都禁止放方块（不限高度）——否则搭一条方块桥
		就能无视整片雷区，路径也就没有意义了。路径格/安全区/陷阱区外照常。"""
		if not self.built:
			return True
		if (x, z) not in self.trapCells:
			return True
		# 提示只发给玩家：非玩家实体（发射器、村民之类）没有聊天框，发了只会刷警告
		if entityId in self.system.playerIds:
			self.Tip(entityId, "§c脚下这格是陷阱，放不了方块")
		return False

	# ---------------------------- 资源刷新取点 ----------------------------

	def MapRing(self, inner, outer):
		"""把主 config 的环半径映射成陷阱区里的环距带 [lo, hi]。

		陷阱区只有 AreaRadius 格，而主 config 的外环远到 35 格——直接夹住会让
		中环和外环全挤在最外圈，距离即价格的层次就没了。所以按比例把
		SpawnRadiusSourceRange 整段压缩进 [安全圈外沿+1, AreaRadius]。
		"""
		nearest, far = self.safeHalf + 1, trapConfig.AreaRadius
		if far < nearest:
			far = nearest
		if not trapConfig.RemapSpawnRadius:
			return (max(int(inner), nearest), max(min(int(outer), far), nearest))
		lo0, hi0 = trapConfig.SpawnRadiusSourceRange
		span = float(hi0 - lo0)

		def remap(r):
			t = 0.0 if span <= 0 else (r - lo0) / span
			t = max(0.0, min(1.0, t))
			return int(round(nearest + t * (far - nearest)))

		lo, hi = remap(inner), remap(outer)
		if hi < lo:
			hi = lo
		return (lo, hi)

	def PickSpawnColumn(self, inner, outer, angleMin=0, angleMax=360):
		"""陷阱模式的资源落点：只在安全格（=路径格）里选，且该列地表必须
		实心可站（树叶/树干/水面不算——不然东西刷在树顶上够不着）。

		做法：环半径重映射成环距带 -> 取该带上的安全格 -> 按 angleRange 扇区过滤
		（黑白半区那套切法照旧生效）-> 实心地面过滤 -> 随机一格。带上没有安全格
		就退到全部安全格，过滤后一个能用的都没有才返回 None（宿主会跳过这次刷新）。
		全程零重试循环。
		"""
		if not self.built or not self.safeCells:
			return None
		lo, hi = self.MapRing(inner, outer)
		candidates = []
		for ring in range(lo, hi + 1):
			candidates.extend(self.safeByRing.get(ring, ()))
		if not candidates:
			candidates = list(self.safeCells)
		if angleMax - angleMin < 360:
			sector = [cell for cell in candidates if self.InSector(cell, angleMin, angleMax)]
			if sector:
				candidates = sector
		if trapConfig.SpawnRequireSolidGround:
			candidates = [cell for cell in candidates if self.IsSpawnableGround(cell)]
		if not candidates:
			return None
		return random.choice(candidates)

	def InSector(self, cell, angleMin, angleMax):
		"""这格在不在 [angleMin, angleMax] 扇区里（角度与宿主取点一致：0=北、顺时针）"""
		cx, _, cz = self.system.EnsureBoardCenter()
		dx, dz = cell[0] - cx, cell[1] - cz
		if dx == 0 and dz == 0:
			return True
		angle = math.degrees(math.atan2(dx, dz)) % 360
		lo, hi = angleMin % 360, angleMax % 360
		if lo <= hi:
			return lo <= angle <= hi
		return angle >= lo or angle <= hi

	# ---------------------------- 复活点 ----------------------------

	def GetSafeCell(self):
		"""棋盘外沿安全圈里的一格（永远安全，绝不可能是陷阱）。方向沿用
		config.RespawnPosOffset 的正负号，距离压到安全圈外沿上"""
		cx, _, cz = self.system.EnsureBoardCenter()
		safeHalf = self.safeHalf or (self.system.boardSize // 2 + max(1, trapConfig.SafeRingWidth))
		dx, _, dz = config.RespawnPosOffset
		if abs(dz) >= abs(dx):
			offZ = safeHalf if dz >= 0 else -safeHalf
			offX = max(-safeHalf, min(safeHalf, dx))
		else:
			offX = safeHalf if dx >= 0 else -safeHalf
			offZ = max(-safeHalf, min(safeHalf, dz))
		return (cx + offX, cz + offZ)

	def CellFootPos(self, cell):
		"""格 -> 站上去的脚底坐标（格中心、该列地表上表面；查询失败退回
		棋盘基座层Y+FallbackFootYOffset，与站上棋盘齐平）"""
		surfaceY = self.GetSurfaceY(cell)
		if surfaceY is None:
			surfaceY = self.system.EnsureBoardCenter()[1] + trapConfig.FallbackFootYOffset
		return (cell[0] + 0.5, surfaceY, cell[1] + 0.5)

	def GetRespawnPos(self):
		"""引擎复活点 = 安全圈里那一格（SetPlayerRespawnPos 要整数方块坐标）"""
		x, y, z = self.CellFootPos(self.GetSafeCell())
		return (int(x), int(y), int(z))

	# ---------------------------- 小工具 ----------------------------

	def GetFootPos(self, playerId):
		try:
			return serverApi.GetEngineCompFactory().CreatePos(playerId).GetFootPos()
		except Exception as e:
			logger.warning("[Gomoku] GetFootPos 失败: {}".format(e))
			return None

	def SetFootPos(self, playerId, footPos):
		try:
			return serverApi.GetEngineCompFactory().CreatePos(playerId).SetFootPos(footPos)
		except Exception as e:
			logger.warning("[Gomoku] SetFootPos 失败: {}".format(e))
			return False

	def Tip(self, playerId, text):
		"""按 TipCooldownSeconds 节流的单人提示（踩雷/禁止放置都会连触发，
		不节流会刷满聊天框）"""
		now = time.time()
		if now - self.tipTimeDict.get(playerId, 0) < trapConfig.TipCooldownSeconds:
			return
		self.tipTimeDict[playerId] = now
		self.system.SendMessageToPlayer(playerId, text)
