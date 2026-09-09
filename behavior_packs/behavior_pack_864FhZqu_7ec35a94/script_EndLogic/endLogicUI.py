# -*- coding: utf-8 -*-

# 从客户端API中拿到我们需要的ViewBinder / ViewRequest / ScreenNode
import mod.client.extraClientApi as clientApi
from mod_log import logger
ViewBinder = clientApi.GetViewBinderCls()
ViewRequest = clientApi.GetViewViewRequestCls()
ScreenNode = clientApi.GetScreenNodeCls()


# 所有的UI类需要继承自引擎的ScreenNode类
class EndLogicUIScreen(ScreenNode):
	def __init__(self, namespace, name, param):
		ScreenNode.__init__(self, namespace, name, param)
		# 当前客户端的玩家Id
		self.mPlayerId = clientApi.GetLocalPlayerId()

	# Create函数是继承自ScreenNode，会在UI创建完成后被调用
	def Create(self):
		logger.info("===== EndLogicUIScreen Create =====")
		#罗盘图片
		self.notifyPanel = "/notifyPanel"
		#指针图片
		self.notifyLabel = self.notifyPanel + "/notifyLabel"

	# 界面的一些初始化操作
	def Init(self):
		self.SetVisible(self.notifyPanel, False)

	def ShowNotifyPanel(self, text):
		self.GetBaseUIControl(self.notifyLabel).asLabel().SetText(text)
		self.SetVisible(self.notifyPanel, True)

	def HideNotifyPanel(self):
		self.SetVisible(self.notifyPanel, False)

	def Update(self):
		pass
