# -*- coding: utf-8 -*-

from mod.client.ui.screenNode import ScreenNode


class LimitedRespawnUIScreen(ScreenNode):
	def __init__(self, namespace, name, param):
		ScreenNode.__init__(self, namespace, name, param)

	def Create(self):
		self.panel = "/mainPanel"
		self.right = self.panel + "/rightLabel"
		self.GetBaseUIControl(self.right).asLabel().SetText("x ui")

	def UpdateUI(self, data):
		self.GetBaseUIControl(self.right).asLabel().SetText("x " + str(data))
