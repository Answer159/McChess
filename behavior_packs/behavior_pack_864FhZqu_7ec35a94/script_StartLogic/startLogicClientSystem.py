# -*- coding: utf-8 -*-

import mod.client.extraClientApi as clientApi
import config
import editorConfig
from coroutineMgrGac import CoroutineMgr

from mod_log import logger

ClientSystem = clientApi.GetClientSystemCls()


class StartLogicClientSystem(ClientSystem):
	def __init__(self, namespace, systemName):
		ClientSystem.__init__(self, namespace, systemName)
		self.mPlayerId = clientApi.GetLocalPlayerId()
		self.startLogicUINode = None
		self.ListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(), config.UiInitFinishedEvent, self, self.OnUIInitFinished)
		self.ListenForEvent(config.ModName, config.ServerSystemName, config.UpdateUIEvent, self, self.OnUpdateUI)
		self.ListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(), "OnLocalPlayerStopLoading", self, self.OnLocalPlayerStopLoading)

	def OnLocalPlayerStopLoading(self, args):
		args['id'] = args['playerId']
		self.NotifyToServer("OnLoadSuccess", args)

	def OnUIInitFinished(self, args):
		clientApi.RegisterUI(config.ModName, config.StartLogicUIName, editorConfig.scriptFolderName + '.' + config.StartLogicUIPyClsPath, config.StartLogicUIScreenDef)
		clientApi.CreateUI(config.ModName, config.StartLogicUIName, {"isHud": 1})
		self.startLogicUINode = clientApi.GetUI(config.ModName, config.StartLogicUIName)
		if self.startLogicUINode:
			self.startLogicUINode.Init()
		else:
			logger.error("create ui %s failed!" % config.StartLogicUIScreenDef)
		self.NotifyToServer("UiInitFinished", args)

	def OnUpdateUI(self, args):
		CoroutineMgr.StartCoroutine(self.DelayUpdateUI(args))

	def DelayUpdateUI(self, args):
		while self.startLogicUINode is None:
			yield - 30
		self.startLogicUINode.UpdateUI(args)

	def Update(self):
		CoroutineMgr.Tick()

	def ClickStart(self):
		data = self.CreateEventData()
		data["playerId"] = self.mPlayerId
		self.NotifyToServer(config.EnsureJoinGameEvent, data)

	def Destroy(self):
		self.UnDefineEvent('OnLoadSuccess')
		self.UnDefineEvent(config.EnsureJoinGameEvent)
		self.UnListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(), config.UiInitFinishedEvent, self, self.OnUIInitFinished)
		self.UnListenForEvent(config.ModName, config.ServerSystemName, config.UpdateUIEvent, self, self.OnUpdateUI)
		self.UnListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(), "OnLocalPlayerStopLoading", self, self.OnLocalPlayerStopLoading)
