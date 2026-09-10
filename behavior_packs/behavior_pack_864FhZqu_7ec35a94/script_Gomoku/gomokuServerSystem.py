# -*- coding: utf-8 -*-
import math
import random

import mod.server.extraServerApi as serverApi
import config
from mod_log import logger
from coroutineMgrGas import CoroutineMgr

ServerSystem = serverApi.GetServerSystemCls()


class GomokuServerSystem(ServerSystem):
	"""五子棋主系统（服务端权威）：棋盘铺设 / 刷资源 / 采集 / 落子 / 五连判定

	核心交互（均为右键，走ServerBlockUseEvent）：
	1. 手持棋子物品右键棋盘基座 -> 落子（颜色=落子方队伍，消耗棋子）
	2. 手持对应镐右键棋子矿 -> 采集（镐耐久1，采一次即碎，矿消失）
	3. 徒手右键金棋子矿 -> 采集金棋子
	4. 手持处决剑攻击玩家 -> 一击必杀（剑用一次即碎）

	棋盘位置：开局按config.BoardCenter + BoardSize自动铺设，位置精确已知；
	资源环（矿/镐/剑）以棋盘中心为圆心按config.SpawnConfigList刷新。
	"""

	def __init__(self, namespace, systemName):
		ServerSystem.__init__(self, namespace, systemName)
		self.levelId = serverApi.GetLevelId()
		# 棋盘状态 {(x, y, z): 'white'/'black'/'gold'}
		self.boardState = {}
		self.endGameFlag = False
		self.winnerSide = None
		self.boardBuilt = False
		self.spawnCoroutines = []
		self.loggedBlockUseEvent = False
		self.ListenEvent()

	def ListenEvent(self):
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
			config.ScriptTickServerEvent, self, self.OnTickServer)
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
			config.AddServerPlayerEvent, self, self.OnPlayerAdd)
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
			config.ServerBlockUseEvent, self, self.OnBlockUse)
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
			config.PlayerAttackEntityEvent, self, self.OnPlayerAttack)
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
			config.PlayerAttackEntityEvent, self, self.OnPlayerAttack)
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
			self.BuildBoard()
			self.StartSpawners()

	def OnRoundStart(self, args):
		"""新一轮开始：清空棋盘上的棋石、重置状态（基座与刷子保持运行）"""
		logger.info("[Gomoku] 新一轮开始，重置棋盘")
		self.ResetBoard()

	# ---------- 棋盘铺设 ----------

	def GetBoardBounds(self):
		"""棋盘基座层的 (x1, y, z1, x2, y, z2)"""
		cx, cy, cz = config.BoardCenter
		half = config.BoardSize // 2
		return (cx - half, cy, cz - half, cx + half, cy, cz + half)

	def BuildBoard(self):
		"""按配置铺设棋盘基座，并清空上方一层的旧棋石"""
		x1, y1, z1, x2, y2, z2 = self.GetBoardBounds()
		result = self.RunCommand('/fill {} {} {} {} {} {} {}'.format(x1, y1, z1, x2, y2, z2, config.ChessBaseBlockName))
		if result is not None and not result:
			logger.warning("[Gomoku] 棋盘铺设命令执行失败，请检查BoardCenter/BoardSize配置")
		else:
			self.boardBuilt = True
			logger.info("[Gomoku] 棋盘已铺设: {} ~ {}".format((x1, y1, z1), (x2, y2, z2)))
		self.ResetBoard()

	def ResetBoard(self):
		"""清除棋盘上方的全部棋石并重置对局状态"""
		x1, y1, z1, x2, y2, z2 = self.GetBoardBounds()
		self.RunCommand('/fill {} {} {} {} {} {} air 0 replace'.format(x1, y1 + 1, z1, x2, y2 + 1, z2))
		self.boardState = {}
		self.endGameFlag = False
		self.winnerSide = None

	def IsOnBoard(self, pos):
		x1, y1, z1, x2, y2, z2 = self.GetBoardBounds()
		return x1 <= pos[0] <= x2 and z1 <= pos[2] <= z2 and pos[1] == y1

	# ---------- 资源刷新 ----------

	def StartSpawners(self):
		for spawnConfig in config.SpawnConfigList:
			coroutineIter = CoroutineMgr.StartCoroutine(self.DelaySpawn(spawnConfig))
			self.spawnCoroutines.append(coroutineIter)
		logger.info("[Gomoku] 资源刷新已启动，共{}个刷新点".format(len(config.SpawnConfigList)))

	def DelaySpawn(self, spawnConfig):
		while True:
			yield -spawnConfig['interval'] * 30
			self.SpawnAtRing(spawnConfig)

	def SpawnAtRing(self, spawnConfig):
		"""在以棋盘中心为圆心的环形区域内随机取一点，找地表后刷新"""
		cx, cy, cz = config.BoardCenter
		inner, outer = spawnConfig['radius']
		angleMin, angleMax = spawnConfig.get('angleRange', (0, 360))
		angle = math.radians(random.uniform(angleMin, angleMax))
		radius = random.uniform(inner, outer)
		x = int(cx + radius * math.sin(angle))
		z = int(cz + radius * math.cos(angle))
		y = self.FindSurfaceY(x, z)
		if y is None:
			return
		if spawnConfig['type'] == 'ore':
			self.RunCommand('/setblock {} {} {} {}'.format(x, y, z, spawnConfig['blockName']))
		else:
			itemComp = serverApi.CreateComponent(self.levelId, config.Minecraft, config.ItemComponent)
			itemComp.SpawnItemToLevel({"itemName": spawnConfig['itemName'], "count": 1, "auxValue": 0}, 0, (x, y, z))

	def FindSurfaceY(self, x, z):
		"""从ScanMaxY向下找第一个非空气方块，返回其上方一格的y；API不可用时返回兜底高度"""
		try:
			for y in range(config.ScanMaxY, config.ScanMinY, -1):
				blockDict = serverApi.GetBlockInLevel((x, y, z))
				if blockDict and blockDict.get('name', 'minecraft:air') != 'minecraft:air':
					return y + 1
			return None
		except Exception as e:
			logger.warning("[Gomoku] GetBlockInLevel 不可用，使用兜底高度: {}".format(e))
			return config.BoardCenter[1] + config.FallbackSpawnYOffset

	# ---------- 交互：落子 / 采集 ----------

	def OnBlockUse(self, args):
		"""右键方块的统一入口：棋盘基座->落子；棋子矿->采集"""
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
		elif blockName in config.OrePieceItemDict:
			self.HandleHarvest(playerId, pos, blockName)

	def HandlePlace(self, playerId, pos):
		"""手持棋子物品右键棋盘基座 -> 落子"""
		if self.endGameFlag:
			self.Announce("§c对局已结束，请等待下一轮")
			return
		if not self.IsOnBoard(pos):
			return
		stonePos = (pos[0], pos[1] + 1, pos[2])
		if stonePos in self.boardState:
			self.Announce("§c此处已有棋子")
			return
		side = self.GetPlayerSide(playerId)
		if side is None:
			self.Announce("§c落子需要先加入队伍")
			return
		carriedItem = self.GetCarriedItemName(playerId)
		if carriedItem is None:
			logger.warning("[Gomoku] 无法读取手持物品，落子中止")
			return
		if not carriedItem.startswith(config.PieceItemPrefix):
			self.Announce("§c请手持棋子右键棋盘落子")
			return
		# 消耗棋子，按队伍颜色落子（金棋子为万能挡子，不分颜色）
		if not self.ConsumeCarriedItem(playerId):
			return
		if carriedItem == config.PieceItemGold:
			stoneName = config.StoneGoldName
			stoneSide = 'gold'
		elif side == 'black':
			stoneName = config.StoneBlackName
			stoneSide = 'black'
		else:
			stoneName = config.StoneWhiteName
			stoneSide = 'white'
		self.RunCommand('/setblock {} {} {} {}'.format(stonePos[0], stonePos[1], stonePos[2], stoneName))
		self.boardState[stonePos] = stoneSide
		logger.info("[Gomoku] 落子: {} {} {}".format(stonePos, stoneSide, carriedItem))
		winnerSide = self.CheckFiveInRow(stonePos)
		if winnerSide:
			self.OnGameEnd(winnerSide)

	def HandleHarvest(self, playerId, pos, oreName):
		"""右键棋子矿 -> 采集。普通/硬化矿需对应镐（耐久1采一次即碎），金矿徒手可采"""
		carriedItem = self.GetCarriedItemName(playerId)
		if carriedItem is None:
			logger.warning("[Gomoku] 无法读取手持物品，采集中止")
			return
		requiredPickaxe = None
		for pickaxe, ore in config.PickaxeOreDict.iteritems():
			if ore == oreName:
				requiredPickaxe = pickaxe
				break
		if requiredPickaxe is not None:
			# 普通/硬化矿：必须手持对应镐，采集成功后镐销毁（耐久1）
			if carriedItem != requiredPickaxe:
				pickaxeName = requiredPickaxe.split(':')[-1]
				self.Announce("§c采集该矿需要：{}".format(pickaxeName))
				return
			if not self.ConsumeCarriedItem(playerId):
				return
		# TODO(phase2): 携带上限检查（棋子1+道具1）
		self.GiveItemToPlayer(playerId, config.OrePieceItemDict[oreName])
		self.RunCommand('/setblock {} {} {} air 0 replace'.format(pos[0], pos[1], pos[2]))
		logger.info("[Gomoku] 采集: {} -> {}".format(pos, config.OrePieceItemDict[oreName]))

	# ---------- 交互：处决剑 ----------

	def OnPlayerAttack(self, args):
		"""手持处决剑攻击玩家 -> 一击必杀，剑销毁"""
		attackerId = args.get('playerId')
		victimId = args.get('victimId')
		if not attackerId or not victimId:
			return
		engineTypeComp = serverApi.CreateComponent(victimId, config.Minecraft, config.EngineTypeComponent)
		if not engineTypeComp or engineTypeComp.GetEngineTypeStr() != 'minecraft:player':
			return
		carriedItem = self.GetCarriedItemName(attackerId)
		if carriedItem != config.ExecutionSwordName:
			return
		args['damage'] = 9999
		if self.ConsumeCarriedItem(attackerId):
			self.Announce("§c处决剑出鞘！一击必杀！")

	# ---------- 胜负判定 ----------

	def CheckFiveInRow(self, pos):
		"""以刚落的子为中心，沿4条直线检查连珠（金棋子属于任何一方都不匹配，天然阻断连线）"""
		side = self.boardState.get(pos)
		if side not in ('white', 'black'):
			return None
		directions = [
			((1, 0, 0), (-1, 0, 0)),
			((0, 0, 1), (0, 0, -1)),
			((1, 0, 1), (-1, 0, -1)),
			((1, 0, -1), (-1, 0, 1)),
		]
		for dirA, dirB in directions:
			count = 1
			for d in (dirA, dirB):
				x, y, z = pos
				while True:
					x, y, z = x + d[0], y + d[1], z + d[2]
					if self.boardState.get((x, y, z)) == side:
						count += 1
					else:
						break
			if count >= config.WinRowLength:
				return side
		return None

	def OnGameEnd(self, winnerSide):
		"""宣布获胜方：优先复用EndLogic的胜利播报与重启逻辑"""
		self.endGameFlag = True
		self.winnerSide = winnerSide
		sideText = config.SideNameDict.get(winnerSide, winnerSide)
		self.Announce("§6{}§f在棋盘上连成五子，赢得对局！".format(sideText))
		data = self.CreateEventData()
		data['winner'] = winnerSide
		data['text'] = "§6{}§f获得五子棋对局胜利".format(sideText)
		self.BroadcastToAllClient(config.GomokuGameResultEvent, data)
		endLogicServerSystem = serverApi.GetSystem(config.EndLogicModName, config.EndLogicServerSystemName)
		if endLogicServerSystem:
			endLogicServerSystem.NotifyVictory(sideText)
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

	# ---------- 物品/方块操作（对不确定的API做防御，失败时打印日志便于在edit.log中调整） ----------

	def GetCarriedItemName(self, playerId):
		"""读取玩家手持物品名；API不可用返回None"""
		try:
			itemComp = serverApi.CreateComponent(playerId, config.Minecraft, config.ItemComponent)
			carriedItem = itemComp.GetPlayerItem(itemComp.PlayerPosType.CARRIED, 0, True)
			if carriedItem:
				return carriedItem.get('newItemName') or carriedItem.get('itemName') or carriedItem.get('name', '')
			return ''
		except Exception as e:
			logger.warning("[Gomoku] GetCarriedItemName 失败: {}".format(e))
			return None

	def ConsumeCarriedItem(self, playerId):
		"""销毁手持物品（镐/剑耐久1、棋子落子消耗均走这里）"""
		try:
			itemComp = serverApi.CreateComponent(playerId, config.Minecraft, config.ItemComponent)
			itemComp.SetPlayerItem(itemComp.PlayerPosType.CARRIED, 0, None)
			return True
		except Exception as e:
			logger.warning("[Gomoku] ConsumeCarriedItem 失败: {}".format(e))
			return False

	def GiveItemToPlayer(self, playerId, itemName):
		"""将物品给到玩家背包"""
		try:
			posComp = serverApi.CreateComponent(playerId, config.Minecraft, config.PosComponent)
			pos = posComp.GetPos()
			itemComp = serverApi.CreateComponent(playerId, config.Minecraft, config.ItemComponent)
			itemComp.SpawnItemToPlayerInv({"itemName": itemName, "count": 1, "auxValue": 0}, playerId, pos)
			return True
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
