# -*- coding: utf-8 -*-
import mod.client.extraClientApi as clientApi
import editorConfig
import mod.server.extraServerApi as serverApi
import worldConfig
from mod.common.mod import Mod


@Mod.Binding(name=worldConfig.ModName, version=worldConfig.ModVersion)
class WorldMod(object):
	def __init__(self):
		print "===== init world mod ====="

	@Mod.InitServer()
	def WorldServerInit(self):
		serverApi.RegisterSystem(worldConfig.ModName, worldConfig.WorldServerSystem, self.getFolderName() + '.' + worldConfig.WorldServerSystemClsPath)

	@Mod.DestroyServer()
	def WorldServerDestroy(self):
		pass

	@Mod.InitClient()
	def WorldClientInit(self):
		clientApi.RegisterSystem(worldConfig.ModName, worldConfig.WorldClientSystem, self.getFolderName() + '.' + worldConfig.WorldClientSystemClsPath)

	@Mod.DestroyClient()
	def WorldClientDestroy(self):
		pass

	def getFolderName(self):
		return editorConfig.scriptFolderName
