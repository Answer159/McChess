# -*- coding: utf-8 -*-
import config
import editorConfig
import mod.server.extraServerApi as serverApi
from coroutineMgrGas import CoroutineMgr
from mod.server.serverEvent import ServerEvent

ServerSystem = serverApi.GetServerSystemCls()


class LimitedRespawnServerSystem(ServerSystem):
	def __init__(self, namespace, systemName):
		super(LimitedRespawnServerSystem, self).__init__(namespace, systemName)
		self.playerRespawnTime = {}
		self.resetEvent = config.ResetTimingOption[config.ResetTimingSelection]['event']
		self.resetSystem = config.ResetTimingOption[config.ResetTimingSelection]['system']
		self.resetNamespace = config.ResetTimingOption[config.ResetTimingSelection]['namespace']
		self.respawnTime = config.RespawnTime
		comp = self.CreateComponent(-1, 'Editor', 'Alive')
		if not comp:
			self.RegisterComponent('Editor', 'Alive', editorConfig.scriptFolderName + '.aliveCompServer.AliveCompServer')
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), ServerEvent.PlayerDieEvent, self, self.OnPlayerDie)
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), "PlayerRespawnFinishServerEvent", self, self.onPlayerRespawnFinishServerEvent)
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), ServerEvent.AddServerPlayerEvent, self, self.OnAddServerPlayer)
		self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), ServerEvent.DelServerPlayerEvent, self, self.OnDelServerPlayer)
		self.ListenForEvent(self.resetNamespace, self.resetSystem, self.resetEvent, self, self.OnReset)
		self.ListenForEvent(config.ModName, config.ClientSystemName, "OnLoadSuccess", self, self.OnLoadSuccess)

	def OnLoadSuccess(self, args):
		self.NotifyUIDataToClient(args['id'])

	def OnPlayerDie(self, args):
		playerId = args['id']
		if self.playerRespawnTime[playerId] <= 0:
			data = self.CreateEventData()
			data['isAlive'] = False
			self.BroadcastEvent('PlayerAliveStateChanged', data)
			aliveComp = serverApi.CreateComponent(playerId, 'Editor', 'Alive')
			aliveComp.SetAlive(False)

	def OnReset(self, args=None):
		for k in self.playerRespawnTime:
			self.playerRespawnTime[k] = self.respawnTime
			self.NotifyUIDataToClient(k)
			aliveComp = serverApi.CreateComponent(k, 'Editor', 'Alive')
			aliveComp.SetAlive(True)
			data = self.CreateEventData()
			data['isAlive'] = True
			self.BroadcastEvent('PlayerAliveStateChanged', data)

	def onPlayerRespawnFinishServerEvent(self, args):
		playerId = args['playerId']
		posComp = serverApi.CreateComponent(playerId, config.Minecraft, "pos")
		if self.playerRespawnTime[playerId] > 0:
			self.playerRespawnTime[playerId] -= 1
			position = self.GetRespawnPoint(playerId)
		else:
			position = config.DefaultRespawnPoint
		if position:
			posComp.SetPos((position[0] + 0.5, position[1] + 2, position[2] + 0.5))
		self.NotifyUIDataToClient(playerId)

	def GetRespawnPoint(self, playerId):
		if config.RespawnPointSelection == 3:  # 队伍复活点
			system = serverApi.GetSystem("TeamMod", "TeamServerSystem")
			if system:
				teamName = system.GetPlayerTeamName(playerId)
				if teamName:
					return config.teamPosDict[teamName]
				else:
					print 'error: team name is none, set respawn point failed'
					return
		pointOption = config.RespawnPointOption[config.RespawnPointSelection]
		point = pointOption.get('value', None)
		if point:
			if isinstance(point, list):
				from random import randint
				index = randint(0, len(point) - 1)
				return point[index]
			return point
		else:
			system = serverApi.GetSystem(pointOption['namespace'], pointOption['system'])
			if system is None:
				print 'system not found:', pointOption['system']
				return
			method = getattr(system, pointOption['method'])
			if method is None:
				print 'method not found:', pointOption['method']
				return
			point = method(playerId)
			return point

	def OnAddServerPlayer(self, args):
		playerId = args['id']
		if playerId not in self.playerRespawnTime:
			self.playerRespawnTime[playerId] = self.respawnTime
			aliveComp = serverApi.CreateComponent(playerId, 'Editor', 'Alive')
			aliveComp.SetAlive(True)
			if len(self.playerRespawnTime) == 1:
				self.OnReset()

	def OnDelServerPlayer(self, args):
		playerId = args['id']
		if playerId in self.playerRespawnTime:
			del self.playerRespawnTime[playerId]

	def Update(self):
		CoroutineMgr.Tick()

	def NotifyUIDataToClient(self, playerId):
		data = self.CreateEventData()
		data['data'] = self.playerRespawnTime[playerId]
		self.NotifyToClient(playerId, config.UpdateUIEvent, data)

	def Destroy(self):
		self.UnListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), "PlayerRespawnFinishServerEvent", self, self.onPlayerRespawnFinishServerEvent)
		self.UnListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), ServerEvent.AddServerPlayerEvent, self, self.OnAddServerPlayer)
		self.UnListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), ServerEvent.DelServerPlayerEvent, self, self.OnDelServerPlayer)
		self.UnListenForEvent(self.resetNamespace, self.resetSystem, self.resetEvent, self, self.OnReset)

