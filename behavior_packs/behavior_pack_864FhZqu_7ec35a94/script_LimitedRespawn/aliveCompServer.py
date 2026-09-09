# -*- coding: utf-8 -*-
import mod.server.extraServerApi as serverApi
ComponentCls = serverApi.GetComponentCls()


class AliveCompServer(ComponentCls):
	def __init__(self, entityId):
		ComponentCls.__init__(self, entityId)
		self.isAlive = True

	def SetAlive(self, isAlive):
		self.isAlive = isAlive

	def GetAlive(self):
		return self.isAlive
