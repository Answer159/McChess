# -*- coding: utf-8 -*-
import mod.client.extraClientApi as api
import worldConfig
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
		# 本地加载完成后再藏：HUD此时已就绪。服务端SetDisableHunger已把饥饿
		# 机制屏蔽，这里把显示也收掉（想恢复显示改worldConfig.hideHungerGui）
		if worldConfig.hideHungerGui:
			api.HideHungerGui(True)
