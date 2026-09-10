# -*- coding: utf-8 -*-
import mod.server.extraServerApi as serverApi
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
