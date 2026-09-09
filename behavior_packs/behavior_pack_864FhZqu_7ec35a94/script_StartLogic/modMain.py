# -*- coding: utf-8 -*-
import mod.client.extraClientApi as clientApi
import config
import editorConfig
import mod.server.extraServerApi as serverApi
from mod.common.mod import Mod

from mod_log import logger


@Mod.Binding(name=config.ModName, version=config.ModVersion)
class StartLogicMod(object):
	def __init__(self):
		pass

	@Mod.InitServer()
	def StartLogicServerInit(self):
		logger.info("===== init StartLogic server =====")
		serverApi.RegisterSystem(config.ModName, config.ServerSystemName, editorConfig.scriptFolderName + '.' + config.ServerSystemClsPath)

	@Mod.DestroyServer()
	def StartLogicServerDestroy(self):
		pass

	@Mod.InitClient()
	def StartLogicClientInit(self):
		logger.info("===== init StartLogic client =====")
		clientApi.RegisterSystem(config.ModName, config.ClientSystemName, editorConfig.scriptFolderName + '.' + config.ClientSystemClsPath)

	@Mod.DestroyClient()
	def StartLogicClientDestroy(self):
		pass
