# -*- coding: utf-8 -*-
import mod.client.extraClientApi as clientApi
import config
import editorConfig
import mod.server.extraServerApi as serverApi
from mod.common.mod import Mod


@Mod.Binding(name=config.ModName, version=config.ModVersion)
class LimitedRespawnMod(object):
	def __init__(self):
		pass

	@Mod.InitServer()
	def LimitedRespawnServerInit(self):
		serverApi.RegisterSystem(config.ModName, config.ServerSystemName, editorConfig.scriptFolderName + '.' + config.ServerSystemClsPath)

	@Mod.DestroyServer()
	def LimitedRespawnServerDestroy(self):
		pass

	@Mod.InitClient()
	def LimitedRespawnClientInit(self):
		clientApi.RegisterSystem(config.ModName, config.ClientSystemName, editorConfig.scriptFolderName + '.' + config.ClientSystemClsPath)

	@Mod.DestroyClient()
	def LimitedRespawnClientDestroy(self):
		pass
