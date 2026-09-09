# -*- coding: utf-8 -*-

import mod.client.extraClientApi as clientApi

ClientSystem = clientApi.GetClientSystemCls()
from ...modCommon import teamConfig
# 用来打印规范的log
from mod_log import logger
# 用来执行一些延迟函数，yield 负数为帧数，正数为秒数
from ...modClient.clientManager.coroutineMgrGac import CoroutineMgr
from ... import editorConfig


class TeamClientSystem(ClientSystem):

	def __init__(self, namespace, systemName):
		ClientSystem.__init__(self, namespace, systemName)
		self.ListenEvent()
		self.mPlayerId = clientApi.GetLocalPlayerId()
		self.teamUINode = None

	def ListenEvent(self):
		self.ListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(), teamConfig.UiInitFinishedEvent, self, self.OnUIInitFinished)
		self.ListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(), teamConfig.ScriptTickClientEvent, self, self.OnTickClient)
		self.ListenForEvent(teamConfig.ModName, teamConfig.ServerSystemName, teamConfig.UpdateScoreboardEvent, self, self.OnUpdateScoreboard)
		self.ListenForEvent(teamConfig.ModName, teamConfig.ServerSystemName, teamConfig.ShowTeamUIEvent, self, self.OnShowTeamUI)
		self.ListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(), 'AddPlayerEvent', self, self.OnAddPlayer)

	def UnListenEvent(self):
		self.UnListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(), teamConfig.UiInitFinishedEvent, self, self.OnUIInitFinished)
		self.UnListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(), teamConfig.ScriptTickClientEvent, self, self.OnTickClient)
		self.UnListenForEvent(teamConfig.ModName, teamConfig.ServerSystemName, teamConfig.UpdateScoreboardEvent, self, self.OnUpdateScoreboard)
		self.UnListenForEvent(teamConfig.ModName, teamConfig.ServerSystemName, teamConfig.ShowTeamUIEvent, self, self.OnShowTeamUI)
		self.UnListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(), 'AddPlayerEvent', self, self.OnAddPlayer)

	def OnUIInitFinished(self, args):
		clientApi.RegisterUI(teamConfig.ModName, teamConfig.TeamUIName, editorConfig.scriptFolderName + '.' + teamConfig.TeamUIPyClsPath, teamConfig.TeamUIScreenDef)
		clientApi.CreateUI(teamConfig.ModName, teamConfig.TeamUIName, {"isHud": 1})
		self.teamUINode = clientApi.GetUI(teamConfig.ModName, teamConfig.TeamUIName)
		if self.teamUINode:
			self.teamUINode.Init()
		else:
			logger.error("create ui %s failed!" % teamConfig.TeamUIScreenDef)

	# 服务端定义的UpdateScoreboardEvent的回调函数，用于更新各队伍队员在线人数及队伍积分
	def OnUpdateScoreboard(self, args):
		CoroutineMgr.StartCoroutine(self.DelayUpdateScoreboard(args))

	# 防止teamUINode尚未初始化完成就收到更新事件
	def DelayUpdateScoreboard(self, args):
		while self.teamUINode == None:
			yield -30
		self.teamUINode.UpdateScoreboard(args)

	def ShowTeamUI(self, flag):
		if self.teamUINode:
			self.teamUINode.ShowTeamUI(flag)
		else:
			CoroutineMgr.StartCoroutine(self.DelayShowTeamUI(flag))

	def DelayShowTeamUI(self, flag):
		while self.teamUINode == None:
			yield -30
		self.teamUINode.ShowTeamUI(flag)

	def OnShowTeamUI(self, args):
		showFlag = args["showFlag"]
		self.ShowTeamUI(showFlag)

	def OnAddPlayer(self, args):
		data = self.CreateEventData()
		data['id'] = args['id']
		self.NotifyToServer('AddPlayerEvent', data)

	def OnTickClient(self):
		CoroutineMgr.Tick()

	def Update(self):
		pass

	def Destroy(self):
		self.UnDefineEvent('AddPlayerEvent')
		self.UnListenEvent()
