# -*- coding: utf-8 -*-

import config
import editorConfig
import mod.server.extraServerApi as serverApi
# 关于MOD开发的基本内容可以先参考TutorialMod
from mod.common.mod import Mod


@Mod.Binding(name=config.ModName, version=config.ModVersion)
class ResourcePointMod(object):
	@Mod.InitServer()
	def ResourcePointServerInit(self):
		serverApi.RegisterSystem(config.ModName, config.ServerSystemName, editorConfig.scriptFolderName + '.' + config.ServerSystemClsPath)

	@Mod.DestroyServer()
	def ResourcePointServerDestroy(self):
		pass

	@Mod.InitClient()
	def ResourcePointClientInit(self):
		pass

	@Mod.DestroyClient()
	def ResourcePointClientDestroy(self):
		pass
