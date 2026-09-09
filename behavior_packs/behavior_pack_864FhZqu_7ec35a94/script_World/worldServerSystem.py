# -*- coding: utf-8 -*-
import mod.server.extraServerApi as serverApi
import worldConfig
from .coroutineMgrGas import CoroutineMgr
ServerSystem = serverApi.GetServerSystemCls()


class WorldServerSystem(ServerSystem):
	def __init__(self, namespace, systemName):
		ServerSystem.__init__(self, namespace, systemName)
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), "LoadServerAddonScriptsAfter", self, self.OnLoadServerAddonScriptsAfter)
		self.ListenForEvent(worldConfig.ModName, worldConfig.WorldClientSystem, 'OnLoadSuccess', self, self.OnLoadSuccess)
		self.done = False

	def OnLoadSuccess(self, args):
		CoroutineMgr.StartCoroutine(self.SetAll())

	def Update(self, *args):
		CoroutineMgr.Tick()

	def OnLoadServerAddonScriptsAfter(self, args):
		pass

	def SetAll(self):
		self.done = True
		gameComp = self.CreateComponent(serverApi.GetLevelId(), "Minecraft", "game")
		gameComp.SetGameRulesInfo(worldConfig.gameRuleDict)
		gameComp.fixTime = worldConfig.fixTime
		self.NeedsUpdate(gameComp)
		yield 2
		command = self.CreateComponent(serverApi.GetLevelId(), "Minecraft", "command")
		commandStr = '/gamemode ' + str(worldConfig.gameMode) + ' @a'
		result = command.SetCommand(commandStr)
		print(commandStr, result)
		commandStr = '/difficulty ' + str(worldConfig.gameDifficulty)
		result = command.SetCommand(commandStr)
		print(commandStr, result)

		if worldConfig.storyline:
			storylineComp = self.CreateComponent(serverApi.GetLevelId(), "Minecraft", "storyline")
			storylineComp.etsPathsToMod = {worldConfig.storyline: worldConfig.compPath}
			self.NeedsUpdate(storylineComp)

	def Destroy(self):
		pass
