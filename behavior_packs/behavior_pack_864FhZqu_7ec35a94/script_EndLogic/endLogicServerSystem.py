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

		# 系列赛（整场多局，如五局三胜）配置与状态
		# 夺冠所需胜场数
		self.matchWinLimit = config.matchWinLimit
		# 各方系列赛胜场数 {记分名: 胜场}。本图乱斗玩法记分名=玩家名（GomokuMod
		# 结算时传入）；其他地图沿用TeamMod队名（见SettleAndRecord的反查路径）
		self.seriesWinDict = {}
		# 总冠军已产生标记（ReStartGame里消费：走整场重置而非系列赛续局）
		self.matchOverFlag = False

	def ListenEvent(self):
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), config.ScriptTickServerEvent, self, self.OnTickServer)
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), config.AddServerPlayerEvent, self, self.OnPlayerAdd)
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), config.PlayerDieEvent, self, self.OnPlayerDie)
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), config.DelServerPlayerEvent, self, self.OnDelServerPlayer)
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), config.EntityRemoveEvent, self, self.OnEntityRemove)

	def UnListenEvent(self):
		self.UnDefineEvent(config.NotifyVictoryEvent)
		self.UnDefineEvent(config.UpdateSeriesScoreEvent)
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
			# 中途进入：补推当前系列赛比分（客户端记分牌若尚未创建会先缓存文案）
			CoroutineMgr.StartCoroutine(self.DelayPushSeriesScore(playerId))

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
		# 统一收尾：记系列赛分->播报->清背包->按系列赛状态重启（与其他结算出口同路径）
		self.SettleAndRecord(victorName, victoryPlayerIdList=self.victoryPlayerIdList)

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
	# 与定时到时结算走同一套结束流程：作废定时器、记系列赛分、通知胜利、按配置清背包、重启下一轮。
	# victorName 播报用胜方名；victoryText 可传完整播报文案（缺省"§6xx§f获得胜利"）；
	# victoryPlayerIdList 可选的获胜玩家列表（供GetVictoryPlayerList查询）；
	# victoryTeamName 系列赛记分用的记分名（本图乱斗=胜者玩家名；缺省时按胜利玩家列表反查；平局均传None）
	def ExternalSettleGame(self, victorName, victoryText=None, victoryPlayerIdList=None, victoryTeamName=None):
		if self.endGameFlag:
			return  # 本局已结算，防重复触发
		self.SettleAndRecord(victorName, victoryText, victoryPlayerIdList, victoryTeamName)

	# 外部加分入口：非对局胜利途径给某记分名加系列赛胜场（GomokuMod的笔刷道具
	# "白捡一局"用，跨Mod直接系统调用）。加分并广播比分；未到夺冠线时当前对局
	# 不受影响；达到matchWinLimit则立即按夺冠收尾——复用SettleAndRecord整条收尾
	# 流程（作废定时器/播报总冠军/按配置清背包/整场重置回大厅重新开始），
	# 不等本局打完；victoryTeamName不传=不再另记一分（本分已由上面加过），
	# endGameFlag防重入保证不会双重重启
	def ExternalAddSeriesWin(self, scoreName, count=1):
		if not scoreName:
			return False
		self.seriesWinDict[scoreName] = self.seriesWinDict.get(scoreName, 0) + count
		logger.info("[Series] 外部加分: {0} +{1} -> {2}".format(scoreName, count, self.seriesWinDict))
		if self.seriesWinDict[scoreName] >= self.matchWinLimit:
			self.matchOverFlag = True
			self.SettleAndRecord(scoreName, "§6{0}§f夺得系列赛总冠军！".format(scoreName))
		else:
			self.BroadcastSeriesScore()
		return True

	# 定时器到时
	def DelayStartClock(self):
		yield -self.clockEndTime * 30
		# 本局已被外部结算（如五子棋连珠）提前结束：超时结算作废
		if self.endGameFlag:
			return
		# 超时一律平局结算（本图结算只有两种：超时平局 / 连珠获胜走ExternalSettleGame），
		# 不再按队伍分数/死亡数评出胜方
		logger.info("=====ClockEnd: 超时平局结算=====")
		# 平局：不记系列赛胜场，统一走收尾（victorName传空串仅作占位，播报用平局文案）
		self.SettleAndRecord('', "§e本局超时，双方平局", None, None)

	# ---------- 系列赛（整场多局） ----------

	# 从获胜玩家列表反查唯一队伍名（系列赛记分用）；平局/无法定位/多队并列返回None
	def ResolveVictoryTeamName(self, victoryPlayerIdList):
		if not (self.teamServerSystem and victoryPlayerIdList):
			return None
		teamSet = set()
		for playerId in victoryPlayerIdList:
			teamName = self.teamServerSystem.GetPlayerTeamName(playerId)
			if teamName:
				teamSet.add(teamName)
		return teamSet.pop() if len(teamSet) == 1 else None

	# 三个结算出口（VictoryJudgeWhenPlayerDie / DelayStartClock / ExternalSettleGame）共用的
	# 统一收尾：作废定时器、记系列赛分、广播比分（驱动记分牌）、播报、按配置清背包、
	# 按系列赛状态分流重启（未夺冠走快速续局，夺冠走整场重置）。
	# victoryTeamName为记分用真实队名；None时按victoryPlayerIdList反查，
	# 仍无法确定（平局/个人模式无队伍）则本局不记胜场。
	def SettleAndRecord(self, victorName, victoryText=None, victoryPlayerIdList=None, victoryTeamName=None):
		if self.endGameFlag:
			return  # 本局已结算，防重复触发
		self.CancelClock()
		self.endGameFlag = True
		self.victoryPlayerIdList = list(victoryPlayerIdList or [])
		# 系列赛记分
		teamName = victoryTeamName if victoryTeamName is not None else self.ResolveVictoryTeamName(self.victoryPlayerIdList)
		championName = None
		if teamName is not None:
			self.seriesWinDict[teamName] = self.seriesWinDict.get(teamName, 0) + 1
			logger.info("[Series] {0} 胜场+1 -> {1}".format(teamName, self.seriesWinDict))
			if self.seriesWinDict[teamName] >= self.matchWinLimit:
				championName = teamName
				self.matchOverFlag = True
		else:
			logger.info("[Series] 本局平局或无法定位队伍，不记胜场")
		# 广播当前比分（驱动客户端记分牌）
		self.BroadcastSeriesScore()
		# 播报（夺冠用总冠军文案，否则沿用调用方文案）
		if championName:
			self.NotifyVictory(championName, "§6{0}§f夺得系列赛总冠军！".format(championName))
		else:
			self.NotifyVictory(victorName, victoryText)
		# 按配置清背包
		if self.clearInvFlag:
			for playerId in self.playerKillNumList:
				comp = self.CreateComponent(playerId, config.Minecraft, 'item')
				for i in xrange(36):
					comp.SetInvItemNum(i, 0)
		# 自动开始下一轮（未夺冠走系列赛续局，夺冠由ReStartGame里走整场重置）
		if self.restartGameFlag:
			CoroutineMgr.StartCoroutine(self.ReStartGame())

	# 构造系列赛比分事件数据（记分牌文案在服务端统一生成，客户端只负责展示）
	# 本图是乱斗玩法（见script_Gomoku）：每个玩家自成一方，系列赛胜场按玩家名记
	# （GomokuMod结算时把胜者玩家名当"队名"传入），记分牌行也按玩家名列——
	# 不再取TeamMod的queueNameDict（那显示的是"火焰使者"这类模板队名）
	def BuildSeriesScoreEvent(self):
		scoreList = []
		for playerId in self.players:
			playerName = self.GetPlayerName(playerId)
			if playerName:
				scoreList.append([playerName, self.seriesWinDict.get(playerName, 0)])
		if len(scoreList) == 2:
			scoreText = "{0} {1} : {2} {3}".format(scoreList[0][0], scoreList[0][1], scoreList[1][1], scoreList[1][0])
		else:
			scoreText = "\n".join("{0} {1}胜".format(name, wins) for name, wins in scoreList)
		scoreText += "\n" + config.SeriesScoreTitleFormat.format(self.matchWinLimit)
		data = self.CreateEventData()
		data["scoreList"] = scoreList
		data["winLimit"] = self.matchWinLimit
		data["text"] = scoreText
		return data

	# 取玩家显示名（记分牌/记分用）；API异常返回None（该玩家不显示行）
	def GetPlayerName(self, playerId):
		try:
			nameComp = serverApi.GetEngineCompFactory().CreateName(playerId)
			return nameComp.GetName() if nameComp else None
		except Exception as e:
			logger.warning("GetPlayerName failed: {0}".format(e))
			return None

	# 广播系列赛当前比分（局结算/夺冠清零后各调用一次，驱动客户端记分牌）
	def BroadcastSeriesScore(self):
		self.BroadcastToAllClient(config.UpdateSeriesScoreEvent, self.BuildSeriesScoreEvent())

	# 当前系列赛比分摘要（队名->胜场），外部查询/调试用
	def GetSeriesScoreSummary(self):
		return dict(self.seriesWinDict)

	# 玩家中途进入时补推当前比分（协程延迟避开客户端初始化竞态）
	def DelayPushSeriesScore(self, playerId):
		yield -30
		if playerId in self.players:
			self.NotifyToClient(playerId, config.UpdateSeriesScoreEvent, self.BuildSeriesScoreEvent())

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
		elif self.matchOverFlag:
			# 总冠军产生：系列赛比分清零、记分牌归零，回大厅完整重置（重新分队/重新确认）
			self.matchOverFlag = False
			self.seriesWinDict = {}
			self.BroadcastSeriesScore()
			self.startLogicServerSystem.ReStartGame()
		else:
			# 系列赛未结束：快速续局，队伍保持不变
			self.startLogicServerSystem.ReStartGameInSeries()
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
