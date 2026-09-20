# -*- coding: utf-8 -*-

import mod.client.extraClientApi as clientApi
import config
import editorConfig
from coroutineMgrGac import CoroutineMgr

from mod_log import logger

ClientSystem = clientApi.GetClientSystemCls()


class EndLogicClientSystem(ClientSystem):
	def __init__(self, namespace, systemName):
		ClientSystem.__init__(self, namespace, systemName)
		self.ListenEvent()
		self.endLogicUINode = None
		self.restartGameFlag = config.restartGameFlag
		self.restartGameTime = config.restartGameTime
		# 系列赛记分牌（TextBoard为纯客户端对象，重进地图后重建）
		self.seriesBoardId = None
		self.seriesScoreText = config.SeriesBoardInitText

	def ListenEvent(self):
		self.ListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(), config.UiInitFinishedEvent, self, self.OnUIInitFinished)
		# self.ListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(), config.ScriptTickClientEvent, self, self.OnTickClient)
		self.ListenForEvent(config.ModName, config.ServerSystemName, config.NotifyVictoryEvent, self, self.OnNotifyVictoryEvent)
		self.ListenForEvent(config.ModName, config.ServerSystemName, config.UpdateSeriesScoreEvent, self, self.OnUpdateSeriesScore)

	def UnListenEvent(self):
		self.UnListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(), config.UiInitFinishedEvent, self, self.OnUIInitFinished)
		# self.UnListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(), config.ScriptTickClientEvent, self, self.OnTickClient)
		self.UnListenForEvent(config.ModName, config.ServerSystemName, config.NotifyVictoryEvent, self, self.OnNotifyVictoryEvent)
		self.UnListenForEvent(config.ModName, config.ServerSystemName, config.UpdateSeriesScoreEvent, self, self.OnUpdateSeriesScore)

	def OnUIInitFinished(self, args):
		logger.info("OnUIInitFinished : %s", args)
		clientApi.RegisterUI(config.ModName, config.EndLogicUIName, editorConfig.scriptFolderName + '.' + config.EndLogicUIPyClsPath, config.EndLogicUIScreenDef)
		clientApi.CreateUI(config.ModName, config.EndLogicUIName, {"isHud": 1})
		self.endLogicUINode = clientApi.GetUI(config.ModName, config.EndLogicUIName)
		if self.endLogicUINode:
			self.endLogicUINode.Init()
		else:
			logger.error("create ui %s failed!" % config.EndLogicUIName)
		# 场地记分牌：延迟创建避开初始化竞态（服务端补推可能早于面板创建，文案先缓存）
		CoroutineMgr.StartCoroutine(self.DelayCreateSeriesBoard())

	# ---------- 系列赛记分牌（官方TextBoard客户端组件，文字随服务端广播更新） ----------

	# 创建场地记分牌：透明底、白字、始终面向镜头（森林里从任何方向都读得到）
	def DelayCreateSeriesBoard(self):
		yield -30
		comp = clientApi.GetEngineCompFactory().CreateTextBoard(clientApi.GetLevelId())
		if self.seriesBoardId:
			comp.RemoveTextBoard(self.seriesBoardId)
			self.seriesBoardId = None
		boardId = comp.CreateTextBoardInWorld(
			self.seriesScoreText, tuple(config.SeriesBoardTextColor), (0, 0, 0, 0),
			config.SeriesBoardFaceCamera)
		if boardId:
			self.seriesBoardId = boardId
			comp.SetBoardScale(boardId, tuple(config.scoreboardScale))
			comp.SetBoardPos(boardId, tuple(config.scoreboardPos))
			logger.info("series scoreboard created at %s", config.scoreboardPos)
		else:
			logger.error("create series scoreboard failed!")

	# 服务端广播/补推系列赛比分 -> 更新记分牌文字（面板尚未创建时先缓存文案）
	def OnUpdateSeriesScore(self, args):
		text = args.get("text", "")
		if not text:
			return
		self.seriesScoreText = text
		if self.seriesBoardId:
			comp = clientApi.GetEngineCompFactory().CreateTextBoard(clientApi.GetLevelId())
			comp.SetText(self.seriesBoardId, text)

	def OnNotifyVictoryEvent(self, args):
		if config.showEndNotifyUIFlag:
			text = args["text"]
			self.endLogicUINode.ShowNotifyPanel(text)
			if self.restartGameFlag:
				CoroutineMgr.StartCoroutine(self.DelayHideNotifyPanel())

	def DelayHideNotifyPanel(self):
		yield -self.restartGameTime * 30
		self.endLogicUINode.HideNotifyPanel()

	def Update(self):
		CoroutineMgr.Tick()

	def Destroy(self):
		logger.info("===== EndLogic Client System Destroy =====")
		self.UnListenEvent()
