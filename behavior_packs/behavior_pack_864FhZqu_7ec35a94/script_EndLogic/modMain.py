# -*- coding: utf-8 -*-
import mod.client.extraClientApi as clientApi
import config
import editorConfig
import mod.server.extraServerApi as serverApi
from mod.common.mod import Mod


@Mod.Binding(name=config.ModName, version=config.ModVersion)
class EndLogicMod(object):
	def __init__(self):
		pass

	@Mod.InitServer()
	def EndLogicServerInit(self):
		serverApi.RegisterSystem(config.ModName, config.ServerSystemName, editorConfig.scriptFolderName + '.' + config.ServerSystemClsPath)

	@Mod.DestroyServer()
	def EndLogicServerDestroy(self):
		pass

	@Mod.InitClient()
	def EndLogicClientInit(self):
		clientApi.RegisterSystem(config.ModName, config.ClientSystemName, editorConfig.scriptFolderName + '.' + config.ClientSystemClsPath)

	@Mod.DestroyClient()
	def EndLogicClientDestroy(self):
		pass
