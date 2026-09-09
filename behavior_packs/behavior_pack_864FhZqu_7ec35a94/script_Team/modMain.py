# -*- coding: utf-8 -*-

import mod.client.extraClientApi as clientApi
from . import editorConfig
import mod.server.extraServerApi as serverApi
# 关于MOD开发的基本内容可以先参考TutorialMod
from mod.common.mod import Mod

from mod_log import logger
# 变量的值尽量写在一个config文件中，这里我们写在了teamConfig中
# 这样的好处是，对于字符串变量我们不会打错减少BUG
# DeBug的时候或者修改变量的时候，不用修改每一个使用的地方，只需要修改config文件
from .modCommon import teamConfig


@Mod.Binding(name = teamConfig.ModName, version = teamConfig.ModVersion)
class TeamMod(object):

    def __init__(self):
        logger.info("===== init Team mod =====")

    @Mod.InitServer()
    def TeamServerInit(self):
        logger.info("===== init Team mod server =====")
        serverApi.RegisterSystem(teamConfig.ModName, teamConfig.ServerSystemName, editorConfig.scriptFolderName + '.' + teamConfig.ServerSystemClsPath)

    @Mod.DestroyServer()
    def TeamServerDestroy(self):
        logger.info("===== destroy Team mod server =====")

    @Mod.InitClient()
    def TeamClientInit(self):
        logger.info("===== init Team mod client =====")
        clientApi.RegisterSystem(teamConfig.ModName, teamConfig.ClientSystemName, editorConfig.scriptFolderName + '.' + teamConfig.ClientSystemClsPath)

    @Mod.DestroyClient()
    def TeamClientDestroy(self):
        logger.info("===== destroy Team mod client =====")
