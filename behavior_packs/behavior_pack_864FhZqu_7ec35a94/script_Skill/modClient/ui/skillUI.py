# -*- coding: utf-8 -*-

import time

import mod.client.extraClientApi as clientApi

from mod_log import logger
from ...modClient.clientManager.coroutineMgrGac import CoroutineMgr
from ...modCommon import skillModConfig

ViewBinder = clientApi.GetViewBinderCls()
ViewRequest = clientApi.GetViewViewRequestCls()
ScreenNode = clientApi.GetScreenNodeCls()


class SkillUIScreen(ScreenNode):

    def __init__(self, namespace, name, param):
        ScreenNode.__init__(self, namespace, name, param)
        self.mText = "Hello World!"
        self.mTextLabelPath = "/hint_label"
        self.mButtonPath = ["/skill_panel1", "/skill_panel2", "/skill_panel3"]
        self.mPlayerId = clientApi.GetLocalPlayerId()
        # 用于记录技能CD提示次数，当最后一次提示倒计时结束后将提示清除
        self.mShowTime = 0
        # 用于记录button_bg的大小
        self.mButtonBgSize = None
        # 用于记录button_mask的初始边长
        self.mButtonMaskLength = None
        # 用于记录button_mask相对于skillPanel的位置
        self.mButtonMaskPos = None

    # 初始化技能按钮
    def InitSkillUI(self, data):
        """
        传入玩家队伍信息，并初始化技能UI
        :param data: 包括队伍分配信息
        :return:
        """
        logger.info("======== playerId is : %s, start InitSkillUI =========" % self.mPlayerId)
        teamIndex = data["playerQueueMap"].get(self.mPlayerId, -1)
        if teamIndex == -1 or teamIndex >= len(data["queueNameDict"]):
            teamName = ""
        else:
            teamName = data["queueNameDict"][teamIndex]
        cnt = 0
        skillComp = clientApi.GetComponent(self.mPlayerId, skillModConfig.ModName,
                                           skillModConfig.ClientSkillComponent)
        if skillComp is None:
            skillComp = clientApi.CreateComponent(self.mPlayerId, skillModConfig.ModName,
                                                  skillModConfig.ClientSkillComponent)
        skillComp.reset()
        skillDict = skillComp.skillDict
        for skillConfig in skillModConfig.SkillConfigs.values():
            if cnt >= 3:
                break
            uuid = skillConfig.get("uuid", "")
            # 同id技能已添加，继续遍历
            if uuid in skillDict.values() or uuid == "":
                continue
            owner = skillConfig.get("owner", "")
            logger.info("uuid is : %s, owner : %s" % (uuid, owner))
            if owner == "_all" or owner == teamName:
                self.SetSprite(self.mButtonPath[cnt] + "/button/default", skillConfig["skillIcon"])
                self.SetSprite(self.mButtonPath[cnt] + "/button/hover", skillConfig["skillIcon"])
                self.SetSprite(self.mButtonPath[cnt] + "/button/pressed", skillConfig["skillIcon"])
                self.SetVisible(self.mButtonPath[cnt], True)
                skillComp.skillDict = {
                    "skillNum": cnt,
                    "uuid": uuid
                }
                cnt += 1
        while cnt < 3:
            self.SetVisible(self.mButtonPath[cnt], False)
            cnt += 1

    def HideSkillUI(self):
        self.SetVisible(self.mButtonPath[0], False)
        self.SetVisible(self.mButtonPath[1], False)
        self.SetVisible(self.mButtonPath[2], False)

    # 继承自ScreenNode的方法，会被引擎自动调用，1秒钟30帧
    def Update(self):
        """
        node tick function
        """
        self.UpdateUI()

    def UpdateUI(self):
        skillComp = clientApi.GetComponent(self.mPlayerId, skillModConfig.ModName, skillModConfig.ClientSkillComponent)
        if skillComp is None:
            return
        skillInfo = skillComp.skill
        skillDict = skillComp.skillDict
        nowTime = time.time()
        if self.mShowTime == 0:
            self.GetBaseUIControl(self.mTextLabelPath).asLabel().SetText("")
        for skillNum in skillInfo.keys():
            uuid = skillDict[skillNum]
            if uuid == -1:
                continue
            skillCD = skillModConfig.SkillConfigs[uuid]["skillCD"]
            interval = nowTime - skillInfo[skillNum]["lastReleaseTime"]
            if skillInfo[skillNum]["state"] == skillModConfig.StateCD:
                if skillCD - interval < 0:
                    skillComp.skill = {
                        "skillNum": skillNum,
                        "state": skillModConfig.StateNotCD
                    }
                    self.SkillChangeState(skillNum, skillModConfig.StateNotCD)
                else:
                    if skillCD == 0:
                        continue
                    width = self.mButtonMaskLength
                    height = self.mButtonMaskLength * ((skillCD - interval) / skillCD)
                    posX = self.mButtonMaskPos[0] + (self.mButtonBgSize[0] - width) / 2
                    posY = self.mButtonMaskPos[1] + (self.mButtonBgSize[1] - height)
                    self.SetPosition(self.mButtonPath[skillNum] + "/button_mask", (posX, posY))
                    self.GetBaseUIControl(self.mButtonPath[skillNum] + "/button_mask").SetSize((width, height))
                    self.GetBaseUIControl(self.mButtonPath[skillNum] + "/button/button_label").\
                        asLabel().SetText("%.1f" % (skillCD - interval))
        return ViewRequest.Refresh | ViewRequest.Exit

    @ViewBinder.binding(ViewBinder.BF_ButtonClickUp)
    def OnSkillUIButton1Pressed(self, args):
        print "OnSkillUIButton1Pressed: ", args
        self.ReleaseSkill(skillModConfig.FirstSkill)
        return ViewRequest.Refresh | ViewRequest.Exit

    @ViewBinder.binding(ViewBinder.BF_ButtonClickUp)
    def OnSkillUIButton2Pressed(self, args):
        print "OnSkillUIButton2Pressed: ", args
        self.ReleaseSkill(skillModConfig.SecondSkill)
        return ViewRequest.Refresh | ViewRequest.Exit

    @ViewBinder.binding(ViewBinder.BF_ButtonClickUp)
    def OnSkillUIButton3Pressed(self, args):
        print "OnSkillUIButton3Pressed: ", args
        self.ReleaseSkill(skillModConfig.ThirdSkill)
        return ViewRequest.Refresh | ViewRequest.Exit

    def ReleaseSkill(self, skillNum):
        skillComp = clientApi.GetComponent(self.mPlayerId, skillModConfig.ModName, skillModConfig.ClientSkillComponent)
        releaseTime = time.time()
        skillInfo = skillComp.skill
        if skillInfo[skillNum]["state"] == skillModConfig.StateNotCD:
            skillComp.skill = {
                "skillNum": skillNum,
                "time": releaseTime,
                "state": skillModConfig.StateCD,
                "release": True
            }
            self.SkillChangeState(skillNum, skillModConfig.StateCD)
        else:
            CoroutineMgr.StartCoroutine(self.SkillCDHint())

    def SkillCDHint(self):
        hintStr = "技能尚未冷却，无法使用"
        self.GetBaseUIControl(self.mTextLabelPath).asLabel().SetText(hintStr)
        self.mShowTime += 1
        yield skillModConfig.HintShowTime
        self.mShowTime -= 1

    def SkillChangeState(self, skillNum, newState):
        if newState == skillModConfig.StateCD:
            self.mButtonBgSize = self.GetBaseUIControl(self.mButtonPath[0] + "/button_bg").GetSize()
            if self.mButtonBgSize[0] > self.mButtonBgSize[1]:
                self.mButtonMaskLength = self.mButtonBgSize[1]
            else:
                self.mButtonMaskLength = self.mButtonBgSize[0]
            self.mButtonMaskPos = self.GetBaseUIControl(self.mButtonPath[0] + "/button_bg").GetPosition()
            posX = self.mButtonMaskPos[0] + (self.mButtonBgSize[0] - self.mButtonMaskLength) / 2
            posY = self.mButtonMaskPos[1] + (self.mButtonBgSize[1] - self.mButtonMaskLength) / 2
            self.SetVisible(self.mButtonPath[skillNum] + "/button_mask", True)
            self.GetBaseUIControl(self.mButtonPath[skillNum] + "/button_mask").\
                SetSize((self.mButtonMaskLength, self.mButtonMaskLength))
            self.SetPosition(self.mButtonPath[skillNum] + "/button_mask", (posX, posY))
        else:
            self.GetBaseUIControl(self.mButtonPath[skillNum] + "/button/button_label").\
                asLabel().SetText("")
            self.SetVisible(self.mButtonPath[skillNum] + "/button_mask", False)
        return ViewRequest.Refresh | ViewRequest.Exit
