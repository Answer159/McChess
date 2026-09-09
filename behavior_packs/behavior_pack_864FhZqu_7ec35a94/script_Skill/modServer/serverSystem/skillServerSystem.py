# -*- coding: UTF-8 -*-
# author: lidi01
# date: 2019/10/8
import mod.server.extraServerApi as serverApi

from ...modCommon import skillModConfig
from mod_log import logger
from ...modServer.serverManager.coroutineMgrGas import CoroutineMgr

ServerSystem = serverApi.GetServerSystemCls()


class SkillServerSystem(ServerSystem):
    def __init__(self, namespace, systemName):
        ServerSystem.__init__(self, namespace, systemName)
        logger.info("===== Server Listen =====")
        self.ListenEvent()

    # 在类初始化的时候开始监听
    def ListenEvent(self):
        # 服务端脚本自定义了2个事件，用于通知所有的监听了这个事件的客户端
        # ProjectileFlyFrameEvent 用于通知客户端在射击时给弹射物绑定特效
        # ProjectileHitEvent 用于通知客户端弹射物击中了目标并返回给客户端一些击中信息
        # InitSkillUIEvent 用于通知客户端初始化技能UI
        # HideSkillUIEvent 用于通知客户端隐藏技能UI
        # 服务器端脚本监听了引擎的2个事件，分别为  ScriptTickServerEvent / ProjectileDoHitEffectEvent
        # 具体每个事件的详细事件data可以参考《MODSDK文档》
        self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
                            skillModConfig.ScriptTickServerEvent, self, self.OnTickServer)
        self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
                            skillModConfig.ProjectileDoHitEffectEvent, self, self.OnProjectileHit)
        # 服务端脚本监听了客户端自定义的事件 SkillReleaseEvent 和 GetTeamNameEvent
        self.ListenForEvent(skillModConfig.ModName, skillModConfig.ClientSystemName,
                            skillModConfig.SkillReleaseEvent, self, self.OnSkillRelease)
        self.ListenForEvent(skillModConfig.ModName, skillModConfig.ClientSystemName,
                            skillModConfig.GetTeamNameEvent, self, self.OnGetTeamName)
        self.ListenForEvent(skillModConfig.StartLogicModName, skillModConfig.StartLogicServerSystemName,
                            skillModConfig.StartGameEvent, self, self.ShowSkillUI)
        self.ListenForEvent(skillModConfig.EndLogicModName, skillModConfig.EndLogicServerSystemName,
                            skillModConfig.EndGameEvent, self, self.HideSkillUI)

    # 在Destroy中调用反注册一些事件
    def UnListenEvent(self):
        # 取消自定义的3个事件
        self.UnDefineEvent(skillModConfig.ProjectileFlyFrameEvent)
        self.UnDefineEvent(skillModConfig.ProjectileHitEvent)
        # 取消监听2个系统事件
        self.UnListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
                              skillModConfig.ScriptTickServerEvent, self, self.OnTickServer)
        self.UnListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
                              skillModConfig.ProjectileDoHitEffectEvent, self, self.OnProjectileHit)
        # 取消监听客户端自定义事件
        self.UnListenForEvent(skillModConfig.ModName, skillModConfig.ClientSystemName,
                              skillModConfig.SkillReleaseEvent, self, self.OnSkillRelease)
        self.UnListenForEvent(skillModConfig.ModName, skillModConfig.ClientSystemName,
                              skillModConfig.GetTeamNameEvent, self, self.OnGetTeamName)
        self.UnListenForEvent(skillModConfig.StartLogicModName, skillModConfig.StartLogicServerSystemName,
                              skillModConfig.StartGameEvent, self, self.ShowSkillUI)
        self.UnListenForEvent(skillModConfig.EndLogicModName, skillModConfig.EndLogicServerSystemName,
                              skillModConfig.EndGameEvent, self, self.HideSkillUI)

    # ScriptTickServerEvent的回调函数，会在引擎tick的时候调用，1秒30帧（被调用30次）
    def OnTickServer(self):
        """
        Driven by event, One tick way
        """
        CoroutineMgr.Tick()

    # 这个Update函数是基类的方法，同样会在引擎tick的时候被调用，1秒30帧（被调用30次）
    def Update(self):
        """
        Driven by system manager, Two tick way
        """
        pass

    # 技能释放
    def OnSkillRelease(self, data):
        playerId = data.get("playerId", "-1")
        logger.info("===========Skill released by playerId: %s ==========" % playerId)
        uuid = data.get("uuid", -1)
        if uuid not in skillModConfig.SkillConfigs.keys():
            logger.info("=========== Skill Not Exist =============")
        skillType = skillModConfig.SkillConfigs[uuid].get("skillType")
        if skillType == skillModConfig.LaunchProjectileType:
            self.ShootProjectileSkill(data)
        elif skillType == skillModConfig.AddBuffType:
            self.AddBuffSkill(data)
        else:
            logger.info("=========== SkillType Not Exist ============")

    # 发射弹射物技能
    def ShootProjectileSkill(self, data):
        playerId = data.get("playerId", "-1")
        logger.info("Shoot playerId: %s" % playerId)
        # 获取弹射技能配置参数
        uuid = data.get("uuid", -1)
        projectileParams = skillModConfig.SkillConfigs[uuid]["projectileParams"]
        logger.info("========= get skill params success ========")
        # 获取弹射物速度及重力
        projectileVelocity = projectileParams.get("velocity", 2)
        projectileGravity = projectileParams.get("gravity", 0.05)
        # 获取玩家位置及旋转
        playerPosComp = self.GetComponent(playerId, skillModConfig.Minecraft, skillModConfig.PosComponent)
        playerRotComp = self.GetComponent(playerId, skillModConfig.Minecraft, skillModConfig.RotComponent)
        projectileId = self.CreateEngineBullet(playerId, serverApi.GetMinecraftEnum().EntityType.Arrow,
                                               playerPosComp.pos, serverApi.GetDirFromRot(playerRotComp.rot),
                                               projectileVelocity, projectileGravity, 0)
        skillComp = self.CreateComponent(projectileId, skillModConfig.ModName, skillModConfig.ServerSkillComponent)
        skillComp.uuid = uuid
        logger.info("========= create projectile success ========")
        # 创建事件数据data
        frameInfo = self.CreateEventData()
        # 给事件数据data赋值
        frameInfo["bindId"] = projectileId
        frameInfo["sfxPath"] = projectileParams.get("sfx")
        frameInfo["pos"] = playerPosComp.pos
        # 广播ProjectileFlyFrameEvent弹射物飞行这个事件通知客户端让客户端给弹射物绑上特效
        self.BroadcastToAllClient(skillModConfig.ProjectileFlyFrameEvent, frameInfo)

    # 添加buff技能
    def AddBuffSkill(self, data):
        playerId = data.get("playerId", "-1")
        logger.info("AddBuff playerId: %s" % playerId)
        # 获取弹射技能配置参数
        uuid = data.get("uuid", -1)
        addBuffParams = skillModConfig.SkillConfigs[uuid]["addBuffParams"]
        buffParams = addBuffParams.get("buff")
        effectiveTarget = addBuffParams.get("effectiveTarget")
        buffType = buffParams.get("buffType")
        buffPower = buffParams.get("buffPower")
        buffDuration = buffParams.get("buffDuration")
        logger.info("========= get buff params success ========")
        if buffType == "none":
            return
        if effectiveTarget == skillModConfig.PlayerTarget:
            logger.info("============== Try TO Add %s To All Players ==============" % (buffType))
            commandComp = self.CreateComponent(serverApi.GetLevelId(), "Minecraft", "command")
            commandStr = "/effect @a %s %s %s" % (buffType, buffDuration, buffPower)
            commandComp.SetCommand(commandStr, playerId)
            return
        teamServerSystem = serverApi.GetSystem(skillModConfig.TeamModName, skillModConfig.TeamServerSystemName)
        if teamServerSystem is None:
            logger.warning("============= get teamComp failed ============")
            # 没有接入队伍组件时下面部分代码用于测试，只有当目标为自己时可用
            if effectiveTarget == skillModConfig.SelfTarget:
                self.AddBuffToTarget(playerId, buffType, buffPower, buffDuration)
        else:
            playerQueueMap = teamServerSystem.GetPlayerQueueMap()
            teamIndex = playerQueueMap[playerId]
            if effectiveTarget == skillModConfig.SelfTarget:
                self.AddBuffToTarget(playerId, buffType, buffPower, buffDuration)
            elif effectiveTarget == skillModConfig.TeamTarget:
                for targetId, teamNum in playerQueueMap.items():
                    if teamNum == teamIndex:
                        self.AddBuffToTarget(targetId, buffType, buffPower, buffDuration)
            elif effectiveTarget == skillModConfig.TeammateTarget:
                for targetId, teamNum in playerQueueMap.items():
                    if teamNum == teamIndex and targetId != playerId:
                        self.AddBuffToTarget(targetId, buffType, buffPower, buffDuration)
            elif effectiveTarget == skillModConfig.NonTeammateTarget:
                for targetId, teamNum in playerQueueMap.items():
                    if teamNum != teamIndex:
                        self.AddBuffToTarget(targetId, buffType, buffPower, buffDuration)
            else:
                for targetId in playerQueueMap.values():
                    self.AddBuffToTarget(targetId, buffType, buffPower, buffDuration)

    # 为目标添加状态
    def AddBuffToTarget(self, targetId, buffType, buffPower, buffDuration):
        logger.info("============== Try TO Add %s To 【%s】==============" % (buffType, targetId))
        comp = self.CreateComponent(targetId, "Minecraft", "effect")
        comp.AddEffectToEntity(buffType, buffDuration, buffPower, True)

    # ProjectileDoHitEffectEvent的回调事件，在抛射物击中的时候被调用
    def OnProjectileHit(self, data):
        logger.info("=====================  Projectile hit ======================")
        projectileId = data.get("id", "-1")
        skillComp = self.GetComponent(projectileId, skillModConfig.ModName, skillModConfig.ServerSkillComponent)
        logger.info("========== get skillComp success ===========")
        uuid = skillComp.uuid
        skillParams = skillModConfig.SkillConfigs[uuid].get("projectileParams")
        if skillParams is None:
            logger.info("========== get skillParams failed ===========")
            return
        targetType = data.get("hitTargetType", "")
        targetId = data.get("targetId", "")
        srcId = data.get("srcId", "")
        logger.info("============ hit targetType is : %s ==================" % targetType)
        if targetType == "BLOCK" and skillParams["effectiveTarget"] == skillModConfig.BlockTarget:
            params = skillParams.get("blockParams")
            params["x"] = data.get("blockPosX", 0)
            params["y"] = data.get("blockPosY", 0)
            params["z"] = data.get("blockPosZ", 0)
            self.HitBlock(params, srcId)
        elif targetType != "BLOCK" and skillParams["effectiveTarget"] != skillModConfig.BlockTarget:
            params = skillParams.get("nonBlockParams")
            self.HitNonBlock(params, targetId, srcId, skillParams["effectiveTarget"])
        hitInfo = self.CreateEventData()
        hitInfo["projectileId"] = projectileId
        hitInfo["targetId"] = targetId
        hitInfo["targeType"] = targetType
        # 广播给客户端子弹射中事件，参数是hitInfo
        self.BroadcastToAllClient(skillModConfig.ProjectileHitEvent, hitInfo)
        # 在弹射物射中后将弹射物实体清除掉
        self.DestroyEntity(projectileId)

    def OnGetTeamName(self, data):
        startLogicServerSystem = serverApi.GetSystem(skillModConfig.StartLogicModName, skillModConfig.StartLogicServerSystemName)
        if startLogicServerSystem:
            print "========== startLogic exists, wait for start event to show skillUI =========="
            return
        self.ShowSkillUI(data)

    def ShowSkillUI(self, data):
        playerId = data.get("playerId", "-1")
        teamServerSystem = serverApi.GetSystem(skillModConfig.TeamModName, skillModConfig.TeamServerSystemName)
        if not teamServerSystem:
            logger.info("============= get teamServerSystem failed ============")
            data["playerQueueMap"] = {}
            data["queueNameDict"] = []
        else:
            data["playerQueueMap"] = teamServerSystem.playerQueueMap
            data["queueNameDict"] = teamServerSystem.queueNameDict
        self.NotifyToClient(playerId, skillModConfig.InitSkillUIEvent, data)

    def HideSkillUI(self, data):
        playerId = data.get("playerId", "-1")
        self.NotifyToClient(playerId, skillModConfig.HideSkillUIEvent, data)

    def HitNonBlock(self, params, targetId, playerId, effectiveTarget):
        damage = 0
        buffParams = params.get("buff")
        if buffParams is None:
            return
        engineTypeComp = self.CreateComponent(targetId, "Minecraft", "engineType")
        entityType = engineTypeComp.GetEngineType()
        # 所有实体
        if effectiveTarget == skillModConfig.AllTarget:
            damage = params.get("damage", 0)
            self.AddBuffToTarget(targetId, buffParams.get("buffType"),
                                 buffParams.get("buffPower"), buffParams.get("buffDuration"))
        else:
            if entityType == serverApi.GetMinecraftEnum().EntityType.Player:
                # 玩家：所有玩家
                if effectiveTarget == skillModConfig.PlayerTarget:
                    logger.info("======= hit player ======")
                    damage = params.get("damage", 0)
                    self.AddBuffToTarget(targetId, buffParams.get("buffType"),
                                         buffParams.get("buffPower"), buffParams.get("buffDuration"))
                else:
                    teamServerSystem = serverApi.GetSystem(skillModConfig.TeamModName, skillModConfig.TeamServerSystemName)
                    # 队伍组件存在且目标非自身进入下面分支
                    if teamServerSystem and playerId != targetId:
                        playerQueueMap = teamServerSystem.GetPlayerQueueMap()
                        playerTeamIndex = playerQueueMap[playerId]
                        targetTeamIndex = playerQueueMap[targetId]
                        # 队友：同一队伍的玩家，自己除外
                        if effectiveTarget == skillModConfig.TeammateTarget and playerTeamIndex == targetTeamIndex:
                            logger.info("======= hit teammate =======")
                            damage = params.get("damage", 0)
                            if not teamServerSystem.canHurtTeammate:
                                damage = 0
                            self.AddBuffToTarget(targetId, buffParams.get("buffType"),
                                                 buffParams.get("buffPower"), buffParams.get("buffDuration"))
                        # 非队友：不同队伍的玩家
                        elif effectiveTarget == skillModConfig.NonTeammateTarget and playerTeamIndex != targetTeamIndex:
                            logger.info("======= hit other team player ======")
                            damage = params.get("damage", 0)
                            self.AddBuffToTarget(targetId, buffParams.get("buffType"),
                                                 buffParams.get("buffPower"), buffParams.get("buffDuration"))
            else:
                # 生物：所有非玩家的实体
                if effectiveTarget == skillModConfig.NonPlayerEntityTarget:
                    logger.info("======= hit other team player ======")
                    damage = params.get("damage", 0)
                    if entityType != serverApi.GetMinecraftEnum().EntityType.Player:
                        self.AddBuffToTarget(
                            targetId,
                            buffParams.get("buffType"),
                            buffParams.get("buffPower"),
                            buffParams.get("buffDuration")
                        )
        comp = self.CreateComponent(targetId, skillModConfig.Minecraft, "hurt")
        comp.SetHurtByEntity(playerId, damage, False)

    def HitBlock(self, params, playerId):
        logger.info("=============== hit block =================")
        replaceBlockType = params["replaceBlock"][0]
        if params.get("destroyBlock"):
            handleType = "destroy"
        else:
            handleType = "replace"
        commandComp = self.CreateComponent(serverApi.GetLevelId(), skillModConfig.Minecraft, "command")
        commandStr = "/setblock %s %s %s %s 0 %s" % (params["x"], params["y"], params["z"],
                                                     replaceBlockType, handleType)
        commandComp.SetCommand(commandStr, playerId)

    # 在清楚该system的时候调用取消监听事件
    def Destroy(self):
        self.UnListenEvent()
