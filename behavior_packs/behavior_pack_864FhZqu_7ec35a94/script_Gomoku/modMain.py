# -*- coding: utf-8 -*-
import mod.client.extraClientApi as clientApi
import mod.server.extraServerApi as serverApi
import mod.client.extraClientApi as clientApi
import config
from mod.common.mod import Mod
from mod_log import logger


@Mod.Binding(name=config.ModName, version=config.ModVersion)
class GomokuMod(object):
	def __init__(self):
		pass

	@Mod.InitServer()
	def GomokuServerInit(self):
		logger.info("===== init Gomoku server =====")
		serverApi.RegisterSystem(config.ModName, config.ServerSystemName,
			config.ScriptFolderName + '.' + config.ServerSystemClsPath)

	@Mod.DestroyServer()
	def GomokuServerDestroy(self):
		pass

	@Mod.InitClient()
	def GomokuClientInit(self):
		logger.info("===== init Gomoku client =====")
		clientApi.RegisterSystem(config.ModName, config.ClientSystemName,
			config.ScriptFolderName + '.' + config.ClientSystemClsPath)

	@Mod.DestroyClient()
	def GomokuClientDestroy(self):
		pass
