# -*- coding: utf-8 -*-
import mod.client.extraClientApi as api
ClientSystem = api.GetClientSystemCls()


class WorldClientSystem(ClientSystem):

	def __init__(self, namespace, systemName):
		ClientSystem.__init__(self, namespace, systemName)
		self.playerId = api.GetLocalPlayerId()
		self.levelId = api.GetLevelId()
		self.ListenForEvent(api.GetEngineNamespace(), api.GetEngineSystemName(), "OnLocalPlayerStopLoading", self, self.OnLocalPlayerStopLoading)

	def OnLocalPlayerStopLoading(self, args):
		args['id'] = args['playerId']
		self.NotifyToServer("OnLoadSuccess", args)
