# -*- coding: utf-8 -*-

import mod.server.extraServerApi as serverApi
from ...modCommon import teamConfig
# 用来打印规范格式的log
from mod_log import logger
# 用来执行一些延迟函数
from ...modServer.serverManager.coroutineMgrGas import CoroutineMgr
import random

ServerSystem = serverApi.GetServerSystemCls()


class TeamServerSystem(ServerSystem):
	def __init__(self, namespace, systemName):
		ServerSystem.__init__(self, namespace, systemName)
		# 队伍分配方式选项（RandomAllocation代表随机分配队伍，MinmunAllocation代表加入人数最少的队伍）
		self.allocationMethodDict = {"RandomAllocation": self.RandomAllocation, "MinmunAllocation": self.MinmunAllocation}
		self.allocationMethod = teamConfig.allocationMethod
		# 积分获得方式
		self.queueKillScore = teamConfig.queueKillScore
		# 队伍名称映射
		self.queueNameDict = teamConfig.queueNameDict
		# 队伍数量
		self.queueNum = teamConfig.queueNum
		# 每队人数上限
		self.queueTopNumList = teamConfig.queueTopNumList
		# 游戏总人数（游戏人数达到此数游戏才会开始）
		self.playerFinalNum = 0
		# 是否可伤害队友
		self.canHurtTeammate = teamConfig.canHurtTeammate
		for i in range(self.queueNum):
			self.playerFinalNum += self.queueTopNumList[i]

		# 动态数据
		# 当前在线玩家数量
		self.playerNum = 0
		# 每队当前在线玩家数量
		self.queuePlayerCount = [0, 0, 0, 0, 0]
		# 当局队伍及在队伍中的玩家信息
		self.queueAllocationInfo = {i: [] for i in range(self.queueNum)}
		# 玩家id到队伍id的映射表
		self.playerQueueMap = {}
		# 各个队伍的积分统计列表
		self.queueScoreList = [0, 0, 0, 0, 0]
		self.players = {}

		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), teamConfig.ScriptTickServerEvent, self, self.OnTickServer)
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), teamConfig.AddServerPlayerEvent, self, self.OnPlayerAdd)
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), teamConfig.PlayerAttackEntityEvent, self, self.OnPlayerAttack)
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), teamConfig.DelServerPlayerEvent, self, self.OnDelServerPlayer)
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), teamConfig.MobDieEvent, self, self.OnMobDie)
		self.ListenForEvent(teamConfig.ModName, teamConfig.ClientSystemName, 'AddPlayerEvent', self, self.OnClientAddPlayer)

	def OnClientAddPlayer(self, args):
		CoroutineMgr.StartCoroutine(self.DelayUpdatePlayerPrefix())

	def OnTickServer(self):
		CoroutineMgr.Tick()

	def GetPlayerTeamName(self, playerId):
		if playerId is None:
			return None
		if playerId not in self.playerQueueMap:
			return None
		return self.queueNameDict[self.playerQueueMap[playerId]]

	def OnPlayerAdd(self, data):
		playerId = data.get("id", "-1")
		self.players[playerId] = True
		if playerId == "-1":
			return
		else:
			# 如果有开始游戏组件将玩家则不做处理
			startLogicServerSystem = serverApi.GetSystem('StartLogicMod', teamConfig.StartLogicServerSystemName)
			if startLogicServerSystem is None:
				self.QueueAllocation(playerId)
			# 在这里处理游戏开始逻辑
			if self.playerNum == self.playerFinalNum:
				logger.info("===== 游戏即将开始 =====")
		CoroutineMgr.StartCoroutine(self.DelayUpdatePlayerPrefix())

	# 为玩家分配队伍
	def QueueAllocation(self, playerId):
		if self.playerNum < self.playerFinalNum:
			self.playerNum += 1
			if self.allocationMethod in self.allocationMethodDict:
				# 根据所选择的分队模式为玩家进行分队
				queueIndex = self.allocationMethodDict[self.allocationMethod](playerId)
				# 更新每队的队伍信息及玩家动态数据相关信息
				self.queuePlayerCount[queueIndex] += 1
				self.playerQueueMap[playerId] = queueIndex
			else:
				logger.info("===== 队伍分配方式参数错误，注意查看teamConfig.AllocationMethod =====")
		else:
			logger.info("===== 各个队伍人数已达到上限 =====")
		CoroutineMgr.StartCoroutine(self.DelayUpdateScoreboard())

	# 随机分配队伍
	def RandomAllocation(self, playerId):
		randomList = []
		for i in range(self.queueNum):
			if len(self.queueAllocationInfo[i]) < self.queueTopNumList[i]:
				randomList.append(i)
		queueIndex = random.randint(0, len(randomList) - 1)
		self.queueAllocationInfo[queueIndex].append(playerId)
		logger.info(self.queueAllocationInfo)
		return queueIndex

	# 分配到人数最少的队伍，队伍人数相同时，按队伍序号小的优先级高
	def MinmunAllocation(self, playerId):
		minMemberNum = 1000
		minQueueIndex = -1
		for queueIndex in range(self.queueNum):
			if len(self.queueAllocationInfo[queueIndex]) < self.queueTopNumList[queueIndex]:
				if minMemberNum >= len(self.queueAllocationInfo[queueIndex]):
					minMemberNum = len(self.queueAllocationInfo[queueIndex])
					minQueueIndex = queueIndex
		self.queueAllocationInfo[minQueueIndex].append(playerId)
		logger.info(self.queueAllocationInfo)
		return minQueueIndex

	def DelayUpdatePlayerPrefix(self):
		yield -90
		for playerId, queueIndex in self.playerQueueMap.iteritems():
			comp = self.CreateComponent(playerId, "Minecraft", "name")
			comp.SetPlayerPrefixAndSuffixName('<{}>'.format(teamConfig.queueNameDict[queueIndex]), serverApi.GenerateColor(['RED', 'GREEN', 'BLUE', 'YELLOW', 'PURPLE'][queueIndex]), '', '')
		for playerId in self.players:
			if playerId not in self.playerQueueMap:
				comp = self.CreateComponent(playerId, "Minecraft", "name")
				comp.SetPlayerPrefixAndSuffixName('', '', '', '')

	# 当玩家离开
	def OnDelServerPlayer(self, args):
		playerId = args["id"]
		if playerId in self.players:
			del self.players[playerId]
		if playerId in self.playerQueueMap:
			queueIndex = self.playerQueueMap[playerId]
			self.playerNum -= 1
			self.queuePlayerCount[queueIndex] -= 1
			self.queueAllocationInfo[queueIndex].remove(playerId)
			self.playerQueueMap.pop(playerId)
			self.UpdateScoreboard()
		logger.info("OnDelServerPlayer,playerId={0}".format(playerId))

	# 当玩家进入时，防止因客戶端尚未完成初始化，就通知消息失败，故延迟发送消息
	def DelayUpdateScoreboard(self):
		yield -60
		self.UpdateScoreboard()

	# 通知客户端更新Scoreboard界面
	def UpdateScoreboard(self):
		scoreboardInfo = self.CreateEventData()
		scoreboardInfo["queueScoreList"] = self.queueScoreList
		scoreboardInfo["queuePlayerCount"] = self.queuePlayerCount
		self.BroadcastToAllClient(teamConfig.UpdateScoreboardEvent, scoreboardInfo)

	# 系统PlayerAttackEntityEvent的回调函数，当玩家攻击时触发
	def OnPlayerAttack(self, args):
		attackerId = args["playerId"]
		victimId = args["victimId"]
		# 队友免伤害
		if not self.canHurtTeammate and victimId in self.playerQueueMap and attackerId in self.playerQueueMap and self.playerQueueMap[attackerId] == self.playerQueueMap[victimId]:
			args["damage"] = 0
			args["isValid"] = 1

	# 系统MobDieEvent的回调函数，当生物死亡时触发（包括玩家死亡、村民死亡）
	def OnMobDie(self, args):
		victimId = args["id"]
		# 若玩家从高空掉落或被怪物打死不进行统分
		attackerId = args["attacker"]
		victimIdentifier = self.CreateComponent(victimId, "Minecraft", "engineType").GetEngineTypeStr()
		if attackerId in self.playerQueueMap:
			attackerQueueIndex = self.playerQueueMap[attackerId]
			# 若死者是玩家则在PlayerDieEvent回调函数中进行处理，若死者是怪物
			if victimIdentifier in self.queueKillScore[attackerQueueIndex].keys():
				scoreInterval = self.queueKillScore[attackerQueueIndex][victimIdentifier]
				self.queueScoreList[attackerQueueIndex] += scoreInterval
				# UI的更新
				self.UpdateScoreboard()

	# 接口
	def ReQueueAllocation(self, playerList):
		# 动态数据重置
		# 当前在线玩家数量
		self.playerNum = 0
		# 每队当前在线玩家数量
		self.queuePlayerCount = [0, 0, 0, 0, 0]
		# 当局队伍及在队伍中的玩家信息
		self.queueAllocationInfo = {i: [] for i in range(self.queueNum)}
		# 玩家id到队伍id的映射表
		self.playerQueueMap = {}
		# 各个队伍的积分统计列表
		self.queueScoreList = [0, 0, 0, 0, 0]
		for player in playerList:
			self.QueueAllocation(player)
		CoroutineMgr.StartCoroutine(self.DelayUpdatePlayerPrefix())

	def ShowTeamUI(self, flag):
		teamUIInfo = self.CreateEventData()
		teamUIInfo["showFlag"] = flag
		self.BroadcastToAllClient(teamConfig.ShowTeamUIEvent, teamUIInfo)

	def GetPlayerQueueMap(self):
		return self.playerQueueMap

	def GetPlayerQueueNameByPlayerId(self, playerId):
		if playerId in self.playerQueueMap:
			queueIndex = self.playerQueueMap[playerId]
			if queueIndex < len(self.queueNameDict):
				return self.queueNameDict[queueIndex]
		return ""

	def GetQueueScoreList(self):
		queueScoreList = {}
		for i in range(self.queueNum):
			queueScoreList[self.queueNameDict[i]] = self.queueScoreList[i]
		return queueScoreList

	def GetQueuePlayerCountInfo(self):
		data = {"queuePlayerCount": self.queuePlayerCount[:self.queueNum], "queueNameDict": self.queueNameDict[:self.queueNum]}
		return data

	def GetQueueNameInfo(self):
		data = {"queueNameDict": self.queueNameDict[:self.queueNum]}
		return data

	# 设置玩家死亡
	def SetPlayerOffQueue(self, playerId):
		if playerId in self.playerQueueMap:
			queueIndex = self.playerQueueMap[playerId]
			self.queuePlayerCount[queueIndex] -= 1
			self.UpdateScoreboard()
			return True
		else:
			return False

	def Update(self):
		pass

	def Destroy(self):
		self.UnDefineEvent(teamConfig.UpdateScoreboardEvent)
		self.UnDefineEvent(teamConfig.ShowTeamUIEvent)
		self.UnListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), teamConfig.ScriptTickServerEvent, self, self.OnTickServer)
		self.UnListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), teamConfig.AddServerPlayerEvent, self, self.OnPlayerAdd)
		self.UnListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), teamConfig.PlayerAttackEntityEvent, self, self.OnPlayerAttack)
		self.UnListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), teamConfig.DelServerPlayerEvent, self, self.OnDelServerPlayer)
		self.UnListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), teamConfig.MobDieEvent, self, self.OnMobDie)
		self.UnListenForEvent(teamConfig.ModName, teamConfig.ClientSystemName, 'AddPlayerEvent', self, self.OnClientAddPlayer)
