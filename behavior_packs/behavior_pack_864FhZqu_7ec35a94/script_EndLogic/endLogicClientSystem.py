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

	def ListenEvent(self):
		self.ListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(), config.UiInitFinishedEvent, self, self.OnUIInitFinished)
		# self.ListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(), config.ScriptTickClientEvent, self, self.OnTickClient)
		self.ListenForEvent(config.ModName, config.ServerSystemName, config.NotifyVictoryEvent, self, self.OnNotifyVictoryEvent)

	def UnListenEvent(self):
		self.UnListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(), config.UiInitFinishedEvent, self, self.OnUIInitFinished)
		# self.UnListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(), config.ScriptTickClientEvent, self, self.OnTickClient)
		self.ListenForEvent(config.ModName, config.ServerSystemName, config.NotifyVictoryEvent, self, self.OnNotifyVictoryEvent)

	def OnUIInitFinished(self, args):
		logger.info("OnUIInitFinished : %s", args)
		clientApi.RegisterUI(config.ModName, config.EndLogicUIName, editorConfig.scriptFolderName + '.' + config.EndLogicUIPyClsPath, config.EndLogicUIScreenDef)
		clientApi.CreateUI(config.ModName, config.EndLogicUIName, {"isHud": 1})
		self.endLogicUINode = clientApi.GetUI(config.ModName, config.EndLogicUIName)
		if self.endLogicUINode:
			self.endLogicUINode.Init()
		else:
			logger.error("create ui %s failed!" % config.EndLogicUIName)

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
