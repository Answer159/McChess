# -*- coding: utf-8 -*-

import mod.server.extraServerApi as serverApi
import config
from mod_log import logger
from coroutineMgrGas import CoroutineMgr

ServerSystem = serverApi.GetServerSystemCls()


class EndLogicServerSystem(ServerSystem):
	def __init__(self, namespace, systemName):
		ServerSystem.__init__(self, namespace, systemName)
		logger.info("===== Server Listen =====")
		self.ListenEvent()
		# 开始游戏组件，在第一个玩家进入时获取
		self.startLogicServerSystem = None
		# 队伍组件，在第一个玩家进入时获取
		self.teamServerSystem = None

		# 查询的字典
		# 结束判断条件列表
		self.endConditionTypeList = config.endConditionTypeList
		self.endJudgeConditionList = config.endJudgeConditionList
		# 胜利判断条件列表
		self.victoryJudgeConditionList = config.victoryJudgeConditionList

		# 配置的数据
		self.victoryJudgeConditionKey = tuple(config.victoryJudgeConditionKey)
		self.victoryJudgeConditionValue = config.victoryJudgeConditionValue
		self.clockEndTime = config.clockEndTime
		self.restartGameFlag = config.restartGameFlag
		self.clearInvFlag = config.clearInvFlag
		self.restartGameTime = config.restartGameTime
		self.endWaitPos = tuple(config.endWaitPos)

		# 动态数据
		# 玩家死亡次数统计
		self.playerDeathNumList = {}
		# 玩家杀人次数统计
		self.playerKillNumList = {}
		self.endGameFlag = False
		self.victoryPlayerIdList = []
		# 定时结算协程句柄（用于外部结算时作废未到点的定时器）
		self.clockCoroutine = None
		# 最终 boss 死亡统计
		self.finalBossDieCount = 0
		self.players = set()

	def ListenEvent(self):
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), config.ScriptTickServerEvent, self, self.OnTickServer)
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), config.AddServerPlayerEvent, self, self.OnPlayerAdd)
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), config.PlayerDieEvent, self, self.OnPlayerDie)
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), config.DelServerPlayerEvent, self, self.OnDelServerPlayer)
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), config.EntityRemoveEvent, self, self.OnEntityRemove)

	def UnListenEvent(self):
		self.UnDefineEvent(config.NotifyVictoryEvent)
		self.UnListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), config.ScriptTickServerEvent, self, self.OnTickServer)
		self.UnListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), config.AddServerPlayerEvent, self, self.OnPlayerAdd)
		self.UnListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), config.PlayerDieEvent, self, self.OnPlayerDie)
		self.UnListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), config.DelServerPlayerEvent, self, self.OnDelServerPlayer)

	def OnTickServer(self):
		CoroutineMgr.Tick()

	def Update(self):
		pass

	# 直接系统调用，监听事件参数可能会调整
	def CapitalDestroy(self):
		self.endGameFlag = True
		self.finalBossDieCount = 0
		self.NotifyVictory('{}和它的手下们'.format(config.finalBossName))

	def OnEntityRemove(self, data):
		# data --> {'id' }
		# logger.info("OnEntityRemove: {}".format(data))
		if self.victoryJudgeConditionKey == ("player", "capitalCondition"):
			comp = serverApi.CreateComponent(data['id'], config.Minecraft, config.EngineTypeComponent)
			mType = comp.GetEngineTypeStr()
			if mType == config.finalBossType:
				self.finalBossDieCount += 1
			if self.finalBossDieCount >= config.finalBossCount:
				self.endGameFlag = True
				self.finalBossDieCount = 0
				# 进入结束游戏流程
				self.NotifyVictory('玩家')

	# 由于 DestroyEntity 无法触发 OnMobDie，所以需要在给个接口外部调用来直接设置boss
	# 不过使用 EntityRemoveEvent 就不需要了
	def OnMobDestroy(self, entityId, entityType):
		pass
	# 	if self.victoryJudgeConditionKey == ("player", "capitalCondition"):
	# 		logger.info("[OnMobDestroy] {}".format(entityType))
	# 		if entityType == config.finalBossType:
	# 			self.finalBossDieCount += 1
	# 		if self.finalBossDieCount >= config.finalBossCount:
	# 			self.endGameFlag = True
	# 			self.finalBossDieCount = 0
	# 			# 进入结束游戏流程
	# 			self.NotifyVictory('玩家')

	# AddServerPlayerEvent的回调函数，在服务器端加入玩家的时候被调用
	def OnPlayerAdd(self, data):
		logger.info("OnPlayerAdd : %s", data)
		playerId = data.get("id", "-1")
		if playerId == "-1":
			return
		else:
			self.players.add(playerId)
			if len(self.playerKillNumList) == 0:
				self.FirstPlayerEnter()
			self.playerDeathNumList[playerId] = 0
			self.playerKillNumList[playerId] = 0

	def FirstPlayerEnter(self):
		# 获取开始游戏组件
		self.startLogicServerSystem = serverApi.GetSystem(config.StartLogicModName, config.StartLogicServerSystemName)
		# 获取队伍组件
		self.teamServerSystem = serverApi.GetSystem(config.TeamModName, config.TeamServerSystemName)
		# 如果不存在开始游戏组件
		if self.startLogicServerSystem is None:
			# 如果结束判断条件是定时结束
			if self.victoryJudgeConditionKey[1] == self.endJudgeConditionList[0]:
				self.StartClock()

	def OnDelServerPlayer(self, args):
		playerId = args["id"]
		if playerId in self.players:
			self.players.remove(playerId)
		# 如果结束方式不是个人+定时+击杀次数最多(即在这种方式下即便玩家离开，仍保留玩家数据，但只要玩家杀人数也足够多，也可能获胜)
		if self.victoryJudgeConditionValue != self.victoryJudgeConditionList[(self.endConditionTypeList[0], self.endJudgeConditionList[0])][1]:
			self.playerKillNumList.pop(playerId)
			self.playerDeathNumList.pop(playerId)
		# 如果是达成胜利条件
		if self.victoryJudgeConditionKey[1] == self.endJudgeConditionList[1]:
			# 如果不存在开始游戏组件
			if self.startLogicServerSystem is None:
				self.VictoryJudgeWhenPlayerDie()
			else:
				# 如果游戏已经开始
				if self.startLogicServerSystem.GetGameStartState():
					self.VictoryJudgeWhenPlayerDie()

	# 系统PlayerDieEvent的回调函数，当玩家死亡时触发
	def OnPlayerDie(self, args):
		victimId = args["id"]
		attackerId = args["attacker"]
		# 玩家死亡次数统计
		self.playerDeathNumList[victimId] += 1
		# 若玩家从高空掉落不进行UI播报
		if attackerId in self.playerKillNumList:
			# 对攻击者杀死次数进行统计
			self.playerKillNumList[attackerId] += 1
		# 如果是达成胜利条件
		if self.victoryJudgeConditionKey[1] == self.endJudgeConditionList[1]:
			# 如果不存在开始游戏组件
			if self.startLogicServerSystem is None:
				CoroutineMgr.StartCoroutine(self.DelayVictoryJudge())
			else:
				# 如果游戏已经开始
				if self.startLogicServerSystem.GetGameStartState():
					CoroutineMgr.StartCoroutine(self.DelayVictoryJudge())

	def DelayVictoryJudge(self):
		yield -3
		self.VictoryJudgeWhenPlayerDie()

	def isAlive(self, playerId):
		if playerId not in self.players:
			return False
		aliveComp = self.CreateComponent(playerId, 'Editor', 'Alive')
		if aliveComp is None or aliveComp.GetAlive():
			return True
		return False

	# 对是否达成胜利条件进行判断
	def VictoryJudgeWhenPlayerDie(self):
		victorName = ""
		# 如果是个人+达成胜利条件
		players = self.playerDeathNumList
		if self.startLogicServerSystem:
			players = self.startLogicServerSystem.getPlayerEnsure()
		if self.victoryJudgeConditionKey == (self.endConditionTypeList[0], self.endJudgeConditionList[1]):
			# 如果是仅剩一人
			if self.victoryJudgeConditionValue == self.victoryJudgeConditionList[self.victoryJudgeConditionKey][0]:
				livePlayerNum = 0
				livePlayerId = -1
				for playerId in players:
					if self.isAlive(playerId):
						livePlayerNum += 1
						livePlayerId = playerId
				print 'check one alive:', livePlayerNum, livePlayerId
				if livePlayerNum <= 1:
					nameComp = self.CreateComponent(livePlayerId, config.Minecraft, config.NameComponent)
					victorName = nameComp.name
					self.victoryPlayerIdList.append(livePlayerId)
				else:
					return
			else:
				logger.info("Use victoryJudgeConditionValue Error")
				return
		# 如果是队伍+达成胜利条件
		elif self.victoryJudgeConditionKey == (self.endConditionTypeList[1], self.endJudgeConditionList[1]):
			# 如果是仅剩一支队伍
			if self.victoryJudgeConditionValue == self.victoryJudgeConditionList[self.victoryJudgeConditionKey][0]:
				# 如果存在队伍组件
				if self.teamServerSystem:
					teamDict = {}
					teamPlayer = []
					for playerId in players:
						if not self.isAlive(playerId):
							continue
						teamName = self.teamServerSystem.GetPlayerTeamName(playerId)
						if teamName:
							teamDict[teamName] = True
							victorName = teamName
							teamPlayer.append(playerId)
					print 'check one team alive:', teamDict, teamPlayer
					if len(teamDict) == 1:
						for playerId in teamPlayer:
							self.victoryPlayerIdList.append(playerId)
					else:
						# 不只一个队伍存活
						return
				else:
					logger.info("Get teamServerSystem Fail")
					return
			else:
				logger.info("Use victoryJudgeConditionValue Error")
				return
		# 如果是个人加塔防组件血量
		elif self.victoryJudgeConditionKey == (self.endConditionTypeList[0], self.endJudgeConditionList[1]):
			pass
		else:
			logger.info("Use VictoryJudgeWhenPlayerDie Error")
			return
		self.endGameFlag = True
		# 进行通知
		self.NotifyVictory(victorName)
		if self.clearInvFlag:
			for playerId in self.playerKillNumList:
				comp = self.CreateComponent(playerId, config.Minecraft, 'item')
				for i in xrange(36):
					comp.SetInvItemNum(i, 0)
		# 自动开始下一轮
		if self.restartGameFlag:
			CoroutineMgr.StartCoroutine(self.ReStartGame())

	# 开启定时器
	def StartClock(self):
		# 如果结束判断条件是定时结束(防止外部调用时没有条件判断)
		print('endLogicServerSystem.StartClock')
		if self.victoryJudgeConditionKey[1] == self.endJudgeConditionList[0]:
			# 上一轮遗留的定时协程先作废，避免双计时
			self.CancelClock()
			self.clockCoroutine = CoroutineMgr.StartCoroutine(self.DelayStartClock())

	# 作废未到点的定时结算协程（外部结算提前结束时调用，避免超时结算二次触发）
	def CancelClock(self):
		if self.clockCoroutine is not None:
			CoroutineMgr.StopCoroutine(self.clockCoroutine)
			self.clockCoroutine = None

	# 外部结算入口：玩法组件（如五子棋GomokuMod连珠获胜）达成胜利条件后直接系统调用，
	# 与定时到时结算走同一套结束流程：作废定时器、通知胜利、按配置清背包、重启下一轮。
	# victorName 播报用胜方名；victoryText 可传完整播报文案（缺省"§6xx§f获得胜利"）；
	# victoryPlayerIdList 可选的获胜玩家列表（供GetVictoryPlayerList查询）
	def ExternalSettleGame(self, victorName, victoryText=None, victoryPlayerIdList=None):
		if self.endGameFlag:
			return  # 本局已结算，防重复触发
		self.CancelClock()
		self.endGameFlag = True
		self.victoryPlayerIdList = list(victoryPlayerIdList or [])
		self.NotifyVictory(victorName, victoryText)
		if self.clearInvFlag:
			for playerId in self.playerKillNumList:
				comp = self.CreateComponent(playerId, config.Minecraft, 'item')
				for i in xrange(36):
					comp.SetInvItemNum(i, 0)
		# 自动开始下一轮（与定时结算一致，由restartGameFlag控制）
		if self.restartGameFlag:
			CoroutineMgr.StartCoroutine(self.ReStartGame())

	# 定时器到时
	def DelayStartClock(self):
		yield -self.clockEndTime * 30
		# 本局已被外部结算（如五子棋连珠）提前结束：超时结算作废
		if self.endGameFlag:
			return
		# 超时一律平局结算（本图结算只有两种：超时平局 / 连珠获胜走ExternalSettleGame），
		# 不再按队伍分数/死亡数评出胜方
		logger.info("=====ClockEnd: 超时平局结算=====")
		self.endGameFlag = True
		self.victoryPlayerIdList = []
		self.NotifyVictory('', "§e本局超时，双方平局")
		if self.clearInvFlag:
			for playerId in self.playerKillNumList:
				comp = self.CreateComponent(playerId, config.Minecraft, 'item')
				for i in xrange(36):
					comp.SetInvItemNum(i, 0)
		# 自动开始下一轮
		if self.restartGameFlag:
			CoroutineMgr.StartCoroutine(self.ReStartGame())

	# 通知胜利信息（victoryText可传完整播报文案，缺省"§6xx§f获得胜利"——平局等特殊文案走这）
	def NotifyVictory(self, victoryName, victoryText=None):
		logger.info("=================victoryName={0}============".format(victoryName))
		text = victoryText if victoryText is not None else "§6{0}§f获得胜利".format(victoryName)
		textInfo = self.CreateEventData()
		textInfo["text"] = text
		if self.startLogicServerSystem:
			playerEnsure = self.startLogicServerSystem.getPlayerEnsure()
			for player in playerEnsure:
				self.NotifyToClient(player, config.NotifyVictoryEvent, textInfo)
		else:
			self.BroadcastToAllClient(config.NotifyVictoryEvent, textInfo)
		self.BroadcastEvent(config.NotifyVictoryEvent, textInfo)

	# 重设动态数据
	def ReSetDynamicData(self):
		for player in self.playerDeathNumList:
			self.playerDeathNumList[player] = 0
			self.playerKillNumList[player] = 0

	# 重新开始游戏
	def ReStartGame(self):
		yield -self.restartGameTime * 30
		# 防御：重启时若还有遗留的定时协程一并作废
		self.CancelClock()
		self.endGameFlag = False
		self.victoryPlayerIdList = []
		self.ReSetDynamicData()
		if self.startLogicServerSystem is None:
			# 如果结束判断条件是定时结束
			if self.victoryJudgeConditionKey[1] == self.endJudgeConditionList[0]:
				self.StartClock()
		else:
			# 如果有开始组件
			self.startLogicServerSystem.ReStartGame()
		logger.info("=================ReStartGame============")

	def GetVictoryPlayerList(self):
		return self.victoryPlayerIdList

	def GetGameEndState(self):
		return self.endGameFlag

	def StartEndGame(self, showStr):
		pass

	# 在清除该system的时候调用取消监听事件
	def Destroy(self):
		logger.info("===== EndLogic Server System Destroy =====")
		self.UnListenEvent()
