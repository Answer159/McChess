# -*- coding: utf-8 -*-

import editorConfig
import mod.client.extraClientApi as clientApi
import mod.server.extraServerApi as serverApi
from mod.common.mod import Mod

from .modCommon import skillModConfig


@Mod.Binding(name=skillModConfig.ModName, version=skillModConfig.ModVersion)
class SkillMod(object):

    def __init__(self):
        print "===== init skill mod ====="

    @Mod.InitServer()
    def skillServerInit(self):
        print "===== init skill server system ====="
        serverApi.RegisterComponent(skillModConfig.ModName, skillModConfig.ServerSkillComponent, editorConfig.scriptFolderName + '.' + skillModConfig.ServerSkillCompClsPath)
        serverApi.RegisterSystem(skillModConfig.ModName, skillModConfig.ServerSystemName, editorConfig.scriptFolderName + '.' + skillModConfig.ServerSystemClsPath)

    @Mod.DestroyServer()
    def skillServerDestroy(self):
        print "===== destroy skill server system ====="

    @Mod.InitClient()
    def skillClientInit(self):
        print "===== init skill client system ====="
        clientApi.RegisterComponent(skillModConfig.ModName, skillModConfig.ClientSkillComponent, editorConfig.scriptFolderName + '.' + skillModConfig.ClientSkillCompClsPath)
        clientApi.RegisterSystem(skillModConfig.ModName, skillModConfig.ClientSystemName, editorConfig.scriptFolderName + '.' + skillModConfig.ClientSystemClsPath)

    @Mod.DestroyClient()
    def skillClientDestroy(self):
        print "===== destroy skill client system ====="
