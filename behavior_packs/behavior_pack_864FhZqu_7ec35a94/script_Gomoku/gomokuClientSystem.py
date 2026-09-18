# -*- coding: utf-8 -*-
import mod.client.extraClientApi as clientApi
import config
from mod_log import logger

ClientSystem = clientApi.GetClientSystemCls()


class GomokuClientSystem(ClientSystem):
	"""GomokuMod客户端系统：说明书弹窗。

	script_Gomoku原本纯服务端，本系统只为教程说明书而设——
	服务端ManualOpenEvent（手持说明书右键）-> PushScreen弹出manualUI，
	关闭由窗口内按钮PopScreen。后续若加记分牌/倒计时等客户端UI也挂这里"""

	def __init__(self, namespace, systemName):
		ClientSystem.__init__(self, namespace, systemName)
		self.ListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(),
			"UiInitFinished", self, self.OnUiInitFinished)
		self.ListenForEvent(config.ModName, config.ServerSystemName,
			config.ManualOpenEvent, self, self.OnManualOpen)

	def OnUiInitFinished(self, args):
		# RegisterUI须在引擎UI就绪后调用一次（对照LimitedRespawn客户端写法）；
		# 画布路径 "gomokuManualUI.main" 对应ui/gomokuManualUI.json的namespace与main画布
		clientApi.RegisterUI(config.ModName, config.ManualUIName,
			config.ScriptFolderName + '.' + config.ManualUIPyClsPath, config.ManualUIScreenDef)

	def OnManualOpen(self, args):
		"""服务端请求打开说明书：PushScreen入栈并接管输入，关闭走窗口按钮（PopScreen）。
		首屏渲染不在这里做——PushScreen返回node时控件树可能尚未创建，
		由引擎在就绪后调ManualUIScreen.Create"""
		node = clientApi.PushScreen(config.ModName, config.ManualUIName, None)
		if node is None:
			logger.warning("[Gomoku] 说明书界面创建失败（RegisterUI未执行？）")

	def Destroy(self):
		self.UnListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(),
			"UiInitFinished", self, self.OnUiInitFinished)
		self.UnListenForEvent(config.ModName, config.ServerSystemName,
			config.ManualOpenEvent, self, self.OnManualOpen)
