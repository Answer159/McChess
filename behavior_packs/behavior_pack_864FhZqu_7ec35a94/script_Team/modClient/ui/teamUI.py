# -*- coding: utf-8 -*-

# 从客户端API中拿到我们需要的ViewBinder / ViewRequest / ScreenNode
import mod.client.extraClientApi as clientApi
ViewBinder = clientApi.GetViewBinderCls()
ViewRequest = clientApi.GetViewViewRequestCls()
ScreenNode = clientApi.GetScreenNodeCls()
from mod_log import logger
from ...modCommon import teamConfig


# 所有的UI类需要继承自引擎的ScreenNode类
class TeamUIScreen(ScreenNode):
    def __init__(self, namespace, name, param):
        ScreenNode.__init__(self, namespace, name, param)
        # 当前客户端的玩家Id
        self.mPlayerId = clientApi.GetLocalPlayerId()
        # 队伍数量
        self.queueNum = teamConfig.queueNum
        self.queueColorDict=teamConfig.queueColorDict
        #队伍名称映射
        self.queueNameDict = teamConfig.queueNameDict

    # Create函数是继承自ScreenNode，会在UI创建完成后被调用
    def Create(self):
        #倒计时UI及击败胜利通知UI
        logger.info("===== teamUIScreen Create =====")
        self.messageBG="/messageBG"
        self.scoreBoard=self.messageBG+"/scoreBoard"
        #各个队伍的信息
        self.queuePanelList=[]
        self.queueNameList=[]
        self.queueMemNumList=[]
        self.queueScoreList=[]
        for i in range(5):
            queuePanelPath=self.scoreBoard+"/queue{0}Panel".format(i+1)
            self.queuePanelList.append(queuePanelPath)
            queueNamePath=queuePanelPath+"/queue{0}Name".format(i+1)
            self.queueNameList.append(queueNamePath)
            queueMemNumPath=queuePanelPath+"/queue{0}MemNum".format(i+1)
            self.queueMemNumList.append(queueMemNumPath)
            queueScorePath=queuePanelPath+"/queue{0}Score".format(i+1)
            self.queueScoreList.append(queueScorePath)

    # 界面的一些初始化操作
    def Init(self):
        for queueIndex in range(self.queueNum):
            text = str(self.queueNameDict[queueIndex])
            self.GetBaseUIControl(self.queueNameList[queueIndex]).asLabel().SetText(text)
            color = self.queueColorDict[queueIndex]
            self.SetTextColor(self.queueNameList[queueIndex], color)
            self.SetTextColor(self.queueScoreList[queueIndex], color)
            self.SetTextColor(self.queueMemNumList[queueIndex], color)
        # 隐藏Label界面
        for i in range(self.queueNum,5):
            self.SetVisible(self.queuePanelList[i], False)

    #根据传递进来的信息修改相应的积分
    def UpdateScoreboard(self,args):
        queueScoreList=args["queueScoreList"]
        queuePlayerCount=args["queuePlayerCount"]
        for queueIndex in range(5):
            text=str(queueScoreList[queueIndex])
            self.GetBaseUIControl(self.queueScoreList[queueIndex]).asLabel().SetText(text)
            text = str(queuePlayerCount[queueIndex])
            self.GetBaseUIControl(self.queueMemNumList[queueIndex]).asLabel().SetText(text)

    def ShowTeamUI(self,flag):
        self.SetVisible(self.messageBG,flag)


    # 继承自ScreenNode的方法，会被引擎自动调用，1秒钟30帧
    def Update(self):
        """
        node tick function
        """
        pass
