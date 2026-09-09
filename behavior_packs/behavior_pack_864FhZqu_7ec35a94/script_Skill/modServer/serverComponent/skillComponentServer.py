# -*- coding: UTF-8 -*-
# author: lidi01
# date: 2019/10/11

import mod.server.extraServerApi as serverApi
ServerComponentCls = serverApi.GetComponentCls()


class SkillComponentServer(ServerComponentCls):
    def __init__(self, entityId):
        ServerComponentCls.__init__(self, entityId)
        self.muuid = -1

    @property
    def uuid(self):
        return self.muuid

    @uuid.setter
    def uuid(self, val):
        self.muuid = val
