# -*- coding: utf-8 -*-
import mod.client.extraClientApi as clientApi
import config
import editorConfig
from mod.client.clientEvent import ClientEvent

ClientSystem = clientApi.GetClientSystemCls()


class LimitedRespawnClientSystem(ClientSystem):
	def __init__(self, namespace, systemName):
		ClientSystem.__init__(self, namespace, systemName)
		self._uiNode = None
		self.UIDataChanged = False
		self.UIData = None
		self.ListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(), ClientEvent.UiInitFinished, self, self.OnUIInitFinished)
		self.ListenForEvent(config.ModName, config.ServerSystemName, config.UpdateUIEvent, self, self.OnUpdateUI)
		self.ListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(), 'OnLocalPlayerStopLoading', self, self.OnLocalPlayerStopLoading)

	def Destroy(self):
		self.UnListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(), ClientEvent.UiInitFinished, self, self.OnUIInitFinished)
		self.UnListenForEvent(config.ModName, config.ServerSystemName, config.UpdateUIEvent, self, self.OnUpdateUI)
		self.UnListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(), 'OnLocalPlayerStopLoading', self, self.OnLocalPlayerStopLoading)

	def OnLocalPlayerStopLoading(self, args):
		args['id'] = args['playerId']
		self.NotifyToServer("OnLoadSuccess", args)

	def OnUIInitFinished(self, args):
		clientApi.RegisterUI(config.ModName, config.UIName, editorConfig.scriptFolderName + '.' + config.UIPyClsPath, config.UIScreenDef)
		clientApi.CreateUI(config.ModName, config.UIName, {"isHud": 1})
		self._uiNode = clientApi.GetUI(config.ModName, config.UIName)

	def Update(self):
		if self._uiNode and self.UIDataChanged:
			self.UIDataChanged = False
			self._uiNode.UpdateUI(self.UIData)

	def OnUpdateUI(self, args):
		self.UIData = args["data"]
		self.UIDataChanged = True
