# -*- coding: utf-8 -*-

import mod.client.extraClientApi as clientApi
from mod.client.clientEvent import ClientEvent
from mod.client.system.clientSystem import ClientSystem

from ... import editorConfig
from mod_log import logger
from ...modClient.clientManager.coroutineMgrGac import CoroutineMgr
from ...modCommon import skillModConfig


class SkillClientSystem(ClientSystem):

    def __init__(self, namespace, systemName):
        ClientSystem.__init__(self, namespace, systemName)
        self.mSkillUINode = None
        self.mPlayerId = clientApi.GetLocalPlayerId()
        # 用于保存在击中后需要释放的实体
        self.mHitDestroyIdList = {}
        self.ListenEvent()

    # 监听引擎和服务端脚本的事件
    def ListenEvent(self):
        self.ListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(),
                            ClientEvent.UiInitFinished, self, self.OnUIInitFinished)
        self.ListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(),
                            ClientEvent.OnScriptTickClient, self, self.OnTickClient)
        self.ListenForEvent(skillModConfig.ModName, skillModConfig.ServerSystemName,
                            skillModConfig.ProjectileFlyFrameEvent, self, self.OnProjectileFlyFrame)
        self.ListenForEvent(skillModConfig.ModName, skillModConfig.ServerSystemName,
                            skillModConfig.ProjectileHitEvent, self, self.OnProjectileHit)
        self.ListenForEvent(skillModConfig.ModName, skillModConfig.ServerSystemName,
                            skillModConfig.InitSkillUIEvent, self, self.OnInitSkillUI)
        self.ListenForEvent(skillModConfig.ModName, skillModConfig.ServerSystemName,
                            skillModConfig.HideSkillUIEvent, self, self.OnHideSkillUI)

    # 取消监听引擎和服务端脚本事件
    def UnListenEvent(self):
        self.UnDefineEvent(skillModConfig.SkillReleaseEvent)
        self.UnListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(),
                              ClientEvent.UiInitFinished, self, self.OnUIInitFinished)
        self.UnListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(),
                              ClientEvent.OnScriptTickClient, self, self.OnTickClient)
        self.UnListenForEvent(skillModConfig.ModName, skillModConfig.ServerSystemName,
                              skillModConfig.ProjectileFlyFrameEvent, self, self.OnProjectileFlyFrame)
        self.UnListenForEvent(skillModConfig.ModName, skillModConfig.ServerSystemName,
                              skillModConfig.ProjectileHitEvent, self, self.OnProjectileHit)
        self.UnListenForEvent(skillModConfig.ModName, skillModConfig.ServerSystemName,
                              skillModConfig.InitSkillUIEvent, self, self.OnInitSkillUI)
        self.UnListenForEvent(skillModConfig.ModName, skillModConfig.ServerSystemName,
                              skillModConfig.HideSkillUIEvent, self, self.OnHideSkillUI)

    # 监听引擎ScriptTickClientEvent事件，引擎会执行该tick回调，1秒钟30帧
    def OnTickClient(self):
        """
        Driven by event, One tick way
        """
        CoroutineMgr.Tick()

    # 被引擎直接执行的父类的重写函数，引擎会执行该Update回调，1秒钟30帧
    def Update(self):
        """
        Driven by system manager, Two tick way
        """
        # 更新技能状态
        self.UpdateSkillData()

    def UpdateSkillData(self):
        skillComp = clientApi.GetComponent(self.mPlayerId, skillModConfig.ModName, skillModConfig.ClientSkillComponent)
        if skillComp is None:
            return
        skillInfo = skillComp.skill
        skillDict = skillComp.skillDict
        for skillNum in skillInfo:
            if skillInfo[skillNum].get("release", False):
                uuid = skillDict[skillNum]
                skillInfo = self.CreateEventData()
                skillInfo["uuid"] = uuid
                skillInfo["playerId"] = self.mPlayerId
                self.NotifyToServer(skillModConfig.SkillReleaseEvent, skillInfo)
                skillComp.skill = {
                    "skillNum": skillNum,
                    "release": False
                }
                break

    def OnInitSkillUI(self, data):
        print "===== start init skillUI ======="
        self.mSkillUINode.InitSkillUI(data)

    def OnHideSkillUI(self, data):
        print "===== hide SkillUI ====="
        self.mSkillUINode.HideSkillUI()

    # 在弹射物开始飞的时候，给弹射物绑定上特效
    def OnProjectileFlyFrame(self, data):
        logger.info("======== OnProjectileFlyFrame: %s ==========", data)
        bindId = data.get("bindId", "-1")
        sfxPath = data.get("sfxPath", "") + ".json"
        particleEntityId = None
        frameEntityId = None
        try:
            frameEntityId = self.CreateEngineSfxFromEditor(sfxPath, tuple(data["pos"]))
        except Exception as e:
            print e
        if not frameEntityId:
            try:
                particleEntityId = self.CreateEngineParticle(sfxPath, tuple(data["pos"]))
            except Exception as e:
                print e
        print('particleEntityId', particleEntityId)
        print('frameEntityId', frameEntityId)
        if particleEntityId:
            entityBindComp = self.CreateComponent(particleEntityId, skillModConfig.Minecraft, skillModConfig.ParticleBindComponent)
            entityBindComp.Bind(bindId, (0, 0, 0), (0, 0, 0))
            particleControlComp = self.CreateComponent(particleEntityId, skillModConfig.Minecraft, skillModConfig.ParticleCtrlComponent)
            particleControlComp.Play()
        if frameEntityId:
            # 创建特效SFX实体绑定在弹射物上
            entityBindComp = self.CreateComponent(frameEntityId, skillModConfig.Minecraft, skillModConfig.FrameAniBindComponent)
            entityBindComp.Bind(bindId, (0, 0, 0), (0, 0, 0))
            frameAniControlComp = self.CreateComponent(frameEntityId, skillModConfig.Minecraft, skillModConfig.FrameAniCtrlComponent)
            frameAniControlComp.Play()
        # 将特效实体Id保存在self.mHitDestroyIdList中，后续更新中会清除
        bindList = self.mHitDestroyIdList.setdefault(bindId, [])
        bindList.append(frameEntityId)

    # 当弹射物射中后，服务端通知客户端并返回一些数据后删除绑定特效
    def OnProjectileHit(self, data):
        logger.info("=========== OnProjectileHit %s =============", data)
        projectileId = data.get("projectileId", "-1")
        # 在每次射中后删除绑定在弹射物上的特效
        destroyList = self.mHitDestroyIdList.get(projectileId, None)
        if destroyList:
            for entityId in destroyList:
                self.DestroyEntity(entityId)

    def Destroy(self):
        self.UnListenEvent()

    def OnUIInitFinished(self, args):
        print "OnUIInitFinished ", args
        clientApi.RegisterUI(skillModConfig.ModName, skillModConfig.SkillUIName, editorConfig.scriptFolderName + '.' + skillModConfig.SkillUIPyClsPath,
                             skillModConfig.SkillUIScreenDef)
        clientApi.CreateUI(skillModConfig.ModName, skillModConfig.SkillUIName, {"isHud": 1})
        self.mSkillUINode = clientApi.GetUI(skillModConfig.ModName, skillModConfig.SkillUIName)
        if not self.mSkillUINode:
            print "create skill ui failed!!!"
        else:
            print "congratulation!!!"
            eventData = self.CreateEventData()
            eventData["playerId"] = self.mPlayerId
            self.NotifyToServer(skillModConfig.GetTeamNameEvent, eventData)
