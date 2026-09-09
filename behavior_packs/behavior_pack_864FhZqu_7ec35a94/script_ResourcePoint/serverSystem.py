# -*- coding: utf-8 -*-
import random
import mod.server.extraServerApi as serverApi
import config
from mod_log import logger
from coroutineMgrGas import CoroutineMgr
ServerSystem = serverApi.GetServerSystemCls()


class ResourcePointServerSystem(ServerSystem):
	def __init__(self, namespace, systemName):
		ServerSystem.__init__(self, namespace, systemName)
		self.ListenEvent()
		self.resourceList = config.resourceList
		self.resourceStartPointList = config.resourceStartPointList
		self.resourceEndPointList = config.resourceEndPointList
		self.resourceIntervalList = config.resourceIntervalList
		self.resourceCountList = config.resourceCountList
		self.playerNum = 0
		self.coroutineIter = []

	def ListenEvent(self):
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), config.AddServerPlayerEvent, self, self.OnPlayerAdd)

	def UnListenEvent(self):
		self.UnListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), config.AddServerPlayerEvent, self, self.OnPlayerAdd)

	def Update(self):
		CoroutineMgr.Tick()

	def OnPlayerAdd(self, data):
		playerId = data.get("id", "-1")
		if playerId == "-1":
			return
		else:
			self.playerNum += 1
			if self.playerNum == 1:
				self.GenerateResources()

	# 生成资源
	def GenerateResources(self):
		for i in range(len(self.resourceList)):
			coroutineIter = CoroutineMgr.StartCoroutine(self.DelayGenerateResources(i))
			self.coroutineIter.append(coroutineIter)

	# 每隔一段时间生成给定资源
	def DelayGenerateResources(self, index):
		while True:
			yield -self.resourceIntervalList[index] * 30
			item = self.resourceList[index]
			itemCount = self.resourceCountList[index]
			pos = []
			for i in range(3):
				minValue = min(self.resourceStartPointList[index][i], self.resourceEndPointList[index][i])
				maxValue = max(self.resourceStartPointList[index][i], self.resourceEndPointList[index][i])
				value = random.randint(minValue, maxValue)
				pos.append(value)
			if item and itemCount and item[0]:
				data = {"itemName": item[0], "count": itemCount, "auxValue": item[1]}
				self.GenerateItem(data, pos)

	# 在世界给定位置处生成1个给定资源
	def GenerateItem(self, itemDict, pos):
		comp = serverApi.CreateComponent(serverApi.GetLevelId(), config.Minecraft, config.ItemComponent)
		comp.SpawnItemToLevel(itemDict, 0, tuple(pos))

	# 清除生成的物品
	def ClearResources(self):
		commandComp = self.CreateComponent(serverApi.GetLevelId(), config.Minecraft, config.CommandComponent)
		commandComp.command = "/kill @e[type=item]"
		self.NeedsUpdate(commandComp)

	# 停止继续生成物品
	def StopGenerateResources(self):
		for coroutineIter in self.coroutineIter:
			CoroutineMgr.StopCoroutine(coroutineIter)
		self.coroutineIter = []

	# 在清除该system的时候调用取消监听事件
	def Destroy(self):
		self.UnListenEvent()
