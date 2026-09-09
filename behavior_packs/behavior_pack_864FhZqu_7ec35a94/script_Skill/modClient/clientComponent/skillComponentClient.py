# -*- coding: UTF-8 -*-
# author: lidi01
# date: 2019/10/9

# 获取客户端Component的基类
import mod.client.extraClientApi as clientApi

from mod_log import logger
from ...modCommon import skillModConfig

ComponentCls = clientApi.GetComponentCls()


class SkillComponentClient(ComponentCls):
    def __init__(self, entityId):
        ComponentCls.__init__(self, entityId)
        # 记录当前添加技能的技能ID
        self.mSKillDict = {}
        # 记录技能的上次施放时间、技能状态、是否释放
        self.mSkillInfo = {}
        self.reset()

    @property
    def skill(self):
        return self.mSkillInfo

    @skill.setter
    def skill(self, val):
        skillNum = val.get("skillNum", -1)
        if skillNum == -1 or skillNum > 2:
            logger.error(">>>>>>>>>>>>>>>> ERROR: skill not exist <<<<<<<<<<<<<<<")
            return
        skillReleaseTime = val.get("time", -1)
        if skillReleaseTime != -1 and isinstance(skillReleaseTime, (int, float)):
            self.mSkillInfo[skillNum]["lastReleaseTime"] = skillReleaseTime
        skillState = val.get("state", -1)
        if skillState != -1:
            self.mSkillInfo[skillNum]["state"] = skillState
        skillRelease = val.get("release", -1)
        if skillRelease != -1:
            self.mSkillInfo[skillNum]["release"] = skillRelease

    @property
    def skillDict(self):
        return self.mSKillDict

    @skillDict.setter
    def skillDict(self, val):
        skillNum = val.get("skillNum", -1)
        if skillNum == -1 or skillNum > 2:
            logger.error(">>>>>>>>>>>>>>>> ERROR: skill not exist <<<<<<<<<<<<<<<")
            return
        uuid = val.get("uuid", -1)
        if uuid != -1:
            self.skillDict[skillNum] = uuid

    def reset(self):
        self.mSKillDict = {
            skillModConfig.FirstSkill: -1,
            skillModConfig.SecondSkill: -1,
            skillModConfig.ThirdSkill: -1
        }
        self.mSkillInfo = {
            skillModConfig.FirstSkill: {
                "lastReleaseTime": 0,
                "state": skillModConfig.StateNotCD,
                "release": False,
            },
            skillModConfig.SecondSkill: {
                "lastReleaseTime": 0,
                "state": skillModConfig.StateNotCD,
                "release": False,
            },
            skillModConfig.ThirdSkill: {
                "lastReleaseTime": 0,
                "state": skillModConfig.StateNotCD,
                "release": False,
            }
        }
