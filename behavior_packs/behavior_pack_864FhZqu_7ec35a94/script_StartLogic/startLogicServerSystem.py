# -*- coding: utf-8 -*-

import mod.server.extraServerApi as serverApi
import config
from mod_log import logger
from coroutineMgrGas import CoroutineMgr
ServerSystem = serverApi.GetServerSystemCls()


class StartLogicServerSystem(ServerSystem):
	def __init__(self, namespace, systemName):
		ServerSystem.__init__(self, namespace, systemName)
		logger.info("===== Server Listen =====")
		self.levelId = serverApi.GetLevelId()
		self.ListenEvent()
		#配置数据
		# 玩家等待坐标
		self.startGameWaitPos = tuple(config.startGameWaitPos)
		# 最低开局玩家人数
		self.gameMinPlayerNum = config.gameMinPlayerNum
		# 是否自动开始游戏标志
		self.autoStartFlag = config.autoStartFlag
		# 是否清除掉落物标志
		self.clearDropsFlag = config.clearDropsFlag
		self.countDownTime = 0
		self.startNum = 0
		self.state = 0
		self.players = {}
		self.playerAliveDict = {}
		self.playerEnsureDict = {}
		self.startGameCoroutineIter = None

	# 在类初始化的时候开始监听
	def ListenEvent(self):
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), config.AddServerPlayerEvent, self, self.OnPlayerAdd)
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), config.DelServerPlayerEvent, self, self.OnDelServerPlayer)
		self.ListenForEvent(config.ModName, config.ClientSystemName, config.EnsureJoinGameEvent, self, self.OnPlayerEnsureJoinGame)
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), "PlayerDieEvent", self, self.OnPlayerDie)
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), "PlayerRespawnFinishServerEvent", self, self.onPlayerRespawnFinishServerEvent)
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), "DamageEvent", self, self.OnDamage)
		self.ListenForEvent(config.ModName, config.ClientSystemName, 'OnLoadSuccess', self, self.OnLoadSuccess)
		self.ListenForEvent(config.ModName, config.ClientSystemName, 'UiInitFinished', self, self.OnUiInitFinished)

	# 在Destroy中调用反注册一些事件
	def UnListenEvent(self):
		self.UnDefineEvent(config.UpdateUIEvent)
		self.UnDefineEvent(config.StartLogicEvent)
		self.UnListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), config.AddServerPlayerEvent, self, self.OnPlayerAdd)
		self.UnListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), config.DelServerPlayerEvent, self, self.OnDelServerPlayer)
		self.UnListenForEvent(config.ModName, config.ClientSystemName, config.EnsureJoinGameEvent, self, self.OnPlayerEnsureJoinGame)
		self.UnListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), "PlayerDieEvent", self, self.OnPlayerDie)
		self.UnListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), "PlayerRespawnFinishServerEvent", self, self.onPlayerRespawnFinishServerEvent)
		self.UnListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), "DamageEvent", self, self.OnDamage)
		self.UnListenForEvent(config.ModName, config.ClientSystemName, 'OnLoadSuccess', self, self.OnLoadSuccess)
		self.UnListenForEvent(config.ModName, config.ClientSystemName, 'UiInitFinished', self, self.OnUiInitFinished)

	def CheckState(self):
		lastState = -1
		while lastState != self.state:
			lastState = self.state
			if self.state == 0:  # 等待阶段
				if len(self.playerAliveDict) >= self.gameMinPlayerNum:
					self.state = 1
					self.playerEnsureDict = {}
					self.startNum = len(self.players)
			if self.state == 1:  # 确认阶段
				self.startNum = max(self.startNum, len(self.players))
				if self.autoStartFlag:  # 自动确认
					for k in self.playerAliveDict.keys():
						self.playerEnsureDict[k] = True
				if len(self.playerAliveDict) < self.startNum:  # 人突然不够了
					self.state = 0
					self.CheckState()
				elif len(self.playerEnsureDict) >= self.startNum:  # 确认人数够了
					self.state = 2
					self.countDownTime = int(config.countDownTime * 30)
			if self.state == 2:  # 倒计时阶段
				if self.countDownTime <= 0:
					self.state = 3
					TeamServerSystem = serverApi.GetSystem(config.TeamModName, config.TeamServerSystemName)
					if TeamServerSystem:
						TeamServerSystem.ReQueueAllocation(list(self.playerEnsureDict.keys()))
						TeamServerSystem.ShowTeamUI(True)
					self.StartGame()
				else:
					if len(self.playerAliveDict) < self.startNum or len(self.playerEnsureDict) < self.startNum:  # 人突然不够了
						self.state = 0
			if self.state == 3:  # 游戏中
				pass

	def getPlayerEnsure(self):
		return self.playerEnsureDict

	def BroadcastData(self):
		self.CheckState()
		data = self.CreateEventData()
		data['playerAlive'] = self.playerAliveDict
		data['playerEnsure'] = self.playerEnsureDict
		data['state'] = self.state
		data['countDownTime'] = self.countDownTime
		data['startNum'] = self.startNum
		print 'broadcast_data', data
		self.BroadcastToAllClient(config.UpdateUIEvent, data)

	def OnPlayerAdd(self, data):
		playerId = data.get("id", '')
		if playerId:
			self.players[playerId] = True
			self.playerAliveDict[playerId] = True
		self.BroadcastData()

	def OnDelServerPlayer(self, args):
		playerId = args["id"]
		del self.players[playerId]
		if playerId in self.playerAliveDict:
			del self.playerAliveDict[playerId]
		if playerId in self.playerEnsureDict:
			del self.playerEnsureDict[playerId]
		self.BroadcastData()

	def OnPlayerDie(self, data):
		playerId = data['id']
		if playerId in self.playerAliveDict:
			del self.playerAliveDict[playerId]
		if self.state != 3 and playerId in self.playerEnsureDict:
			del self.playerEnsureDict[playerId]
		self.BroadcastData()

	def onPlayerRespawnFinishServerEvent(self, data):
		playerId = data['playerId']
		self.playerAliveDict[playerId] = True
		if playerId not in self.playerEnsureDict:
			self.SetPlayerInitPos(playerId)
		self.BroadcastData()

	def OnDamage(self, data):
		entityId = data['entityId']
		if entityId not in self.playerAliveDict:
			return
		posComp = self.CreateComponent(entityId, "Minecraft", "pos")
		pos = posComp.GetPos()
		if self.invincible(pos):
			data['damage'] = 0

	def invincible(self, pos, startPoint=None, endPoint=None):
		if pos is None:
			return False
		if startPoint is None:
			startPoint = config.startPoint
		if endPoint is None:
			endPoint = config.endPoint
		for i in range(len(pos)):
			upperBound = max(startPoint[i], endPoint[i]) + 1
			lowerBound = min(startPoint[i], endPoint[i]) - 1
			value = pos[i]
			if i == 1:
				value -= 2
			value = int(value)
			if value < lowerBound or value > upperBound:
				return False
		return True

	def isInside(self, pos, startPoint=None, endPoint=None):
		if pos is None:
			return False
		if startPoint is None:
			startPoint = config.startPoint
		if endPoint is None:
			endPoint = config.endPoint
		for i in range(len(pos)):
			upperBound = max(startPoint[i], endPoint[i])
			lowerBound = min(startPoint[i], endPoint[i])
			value = pos[i]
			if i == 1:
				value -= 2
			value = int(value)
			if value < lowerBound or value > upperBound:
				return False
		return True

	def getRandomPoint(self, startPoint=None, endPoint=None):
		from random import randint
		if startPoint is None:
			startPoint = config.startPoint
		if endPoint is None:
			endPoint = config.endPoint
		deltaX = endPoint[0] - startPoint[0]
		deltaY = endPoint[1] - startPoint[1]
		deltaZ = endPoint[2] - startPoint[2]
		dx = randint(min(0, abs(deltaX)), max(0, abs(deltaX)))
		dy = randint(min(0, abs(deltaY)), max(0, abs(deltaY)))
		dz = randint(min(0, abs(deltaZ)), max(0, abs(deltaZ)))
		point = [
			min(startPoint[0], endPoint[0]) + dx,
			min(startPoint[1], endPoint[1]) + dy,
			min(startPoint[2], endPoint[2]) + dz
		]
		return tuple(point)

	def OnLoadSuccess(self, args):
		playerId = args["id"]
		self.SetPlayerInitPos(playerId)
		TeamServerSystem = serverApi.GetSystem(config.TeamModName, config.TeamServerSystemName)
		if TeamServerSystem:
			TeamServerSystem.ShowTeamUI(False)
		self.BroadcastData()

	def OnUiInitFinished(self, args):
		TeamServerSystem = serverApi.GetSystem(config.TeamModName, config.TeamServerSystemName)
		if TeamServerSystem:
			TeamServerSystem.ShowTeamUI(False)
		self.BroadcastData()

	def SetPlayerInitPos(self, playerId):
		posComp = self.CreateComponent(playerId, "Minecraft", "pos")
		pos = posComp.GetPos()
		if self.isInside(pos):
			return
		pos = self.getRandomPoint()
		posComp.SetPos((pos[0], pos[1] + 2, pos[2]))

	def OnPlayerEnsureJoinGame(self, args):
		if self.state == 0 or self.state == 3:
			return
		playerId = args["playerId"]
		self.playerEnsureDict[playerId] = True
		self.BroadcastData()

	def StartGame(self):
		self.BroadcastEvent(config.StartLogicEvent, self.CreateEventData())  # 其他系统需要的事件
		# 如果有结束游戏组件将结束组件数据重置
		endLogicServerSystem = serverApi.GetSystem(config.EndLogicModName, config.EndLogicServerSystemName)
		if endLogicServerSystem:
			endLogicServerSystem.ReSetDynamicData()
			endLogicServerSystem.StartClock()
		TeamServerSystem = serverApi.GetSystem(config.TeamModName, config.TeamServerSystemName)
		if TeamServerSystem is None:
			logger.info("===== Get TeamServerSystem Fail=====")
		else:
			TeamServerSystem.ReQueueAllocation(list(self.playerEnsureDict.keys()))
			TeamServerSystem.ShowTeamUI(True)
		# 设置开始游戏位置
		playerList = []
		if self.autoStartFlag:
			playerList = list(self.playerAliveDict.keys())
		else:
			playerList = list(self.playerEnsureDict.keys())
		if config.posOption == 1:  # 根据队伍设置传送点
			if TeamServerSystem:
				for player in playerList:
					teamName = TeamServerSystem.GetPlayerTeamName(player)
					if teamName:
						pos = list(config.teamPosDict[teamName])
						pos[1] += 2
						posComp = self.CreateComponent(player, "Minecraft", "pos")
						posComp.SetPos(tuple(pos))
						logger.info("set team pos: %s, %s", player, str(pos))
		else:  # 随机列表
			if config.randomPointList:
				from random import randint
				for player in playerList:
					i = randint(0, len(config.randomPointList) - 1)
					pos = config.randomPointList[i]
					posComp = self.CreateComponent(player, "Minecraft", "pos")
					posComp.SetPos((pos[0], pos[1] + 2, pos[2]))
					logger.info("set random pos: %s, %s", player, str(pos))
		# 清除掉落物
		if self.clearDropsFlag:
			commandComp = self.CreateComponent(serverApi.GetLevelId(), config.Minecraft, config.CommandComponent)
			commandComp.command = "/kill @e[type=item]"
			self.NeedsUpdate(commandComp)

	def GetGameStartState(self):
		return self.state == 3

	def ReStartGame(self):
		TeamServerSystem = serverApi.GetSystem(config.TeamModName, config.TeamServerSystemName)
		if TeamServerSystem:
			TeamServerSystem.ShowTeamUI(False)
		for player in self.players:
			self.SetPlayerInitPos(player)
		self.state = 0
		self.playerEnsureDict = {}
		self.BroadcastData()

	def Update(self):
		CoroutineMgr.Tick()
		if self.state == 2:
			if self.countDownTime >= 0 and self.countDownTime % 30 == 0:
				self.BroadcastData()
			self.countDownTime -= 1

	def Destroy(self):
		self.UnListenEvent()
