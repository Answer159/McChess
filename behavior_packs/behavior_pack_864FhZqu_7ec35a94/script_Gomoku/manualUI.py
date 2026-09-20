# -*- coding: utf-8 -*-
import mod.client.extraClientApi as clientApi
import messageConfig
from mod_log import logger

ViewBinder = clientApi.GetViewBinderCls()
ViewRequest = clientApi.GetViewViewRequestCls()
ScreenNode = clientApi.GetScreenNodeCls()


class ManualUIScreen(ScreenNode):
	"""说明书窗口：分页教程文本（messageConfig.ManualTextList）。

	控件路径镜像ui/gomokuManualUI.json的manualPanel子树；
	翻页/关闭按钮的$pressed_button_name绑定到下面的回调方法。
	文案改动只须改messageConfig.ManualTextList，本文件与UI JSON不用动"""

	def __init__(self, namespace, name, param):
		ScreenNode.__init__(self, namespace, name, param)
		self.pageIndex = 0

	def Create(self):
		"""引擎生命周期钩子：控件树就绪后调用，首屏渲染放这里。
		（PushScreen返回node时控件往往尚未创建，外部立刻取控件会拿到None）"""
		self.ShowPage(0)

	def ShowPage(self, index):
		"""渲染第index页：正文/页码 + 首末页隐藏对应翻页按钮"""
		pages = messageConfig.ManualTextList
		if not pages:
			return
		self.pageIndex = max(0, min(index, len(pages) - 1))
		textCtrl = self.GetBaseUIControl("/manualPanel/textLabel")
		if textCtrl is None:
			logger.warning("[Gomoku] 说明书控件未找到: /manualPanel/textLabel（UI JSON控件树与路径不匹配?）")
			return
		textCtrl.asLabel().SetText(pages[self.pageIndex])
		self.GetBaseUIControl("/manualPanel/pageLabel").asLabel().SetText(
			"{}/{}".format(self.pageIndex + 1, len(pages)))
		self.SetVisible("/manualPanel/prevButton", self.pageIndex > 0)
		self.SetVisible("/manualPanel/nextButton", self.pageIndex < len(pages) - 1)

	# 按钮绑定：推栈界面须用"按钮id+过滤参数"式（#id 与 UI JSON 的 $pressed_button_name
	# 对应）；%ns.方法名式只在 HUD（CreateUI isHud）界面生效，已实测推栈界面收不到
	@ViewBinder.binding(ViewBinder.BF_ButtonClickUp, '#gomokuManualUI.prev')
	def OnManualPrevPressed(self, args):
		self.ShowPage(self.pageIndex - 1)
		return ViewRequest.Refresh

	@ViewBinder.binding(ViewBinder.BF_ButtonClickUp, '#gomokuManualUI.next')
	def OnManualNextPressed(self, args):
		self.ShowPage(self.pageIndex + 1)
		return ViewRequest.Refresh

	@ViewBinder.binding(ViewBinder.BF_ButtonClickUp, '#gomokuManualUI.close')
	def OnManualClosePressed(self, args):
		clientApi.PopScreen()
		return ViewRequest.Refresh

	@ViewBinder.binding(ViewBinder.BF_ButtonClickUp, '#gomokuManualUI.escClose')
	def OnManualEscClose(self, args):
		"""ESC/手柄退出键关闭（按钮id来自UI JSON里main的button_mappings，须带过滤参数绑定）"""
		clientApi.PopScreen()
		return ViewRequest.Refresh
