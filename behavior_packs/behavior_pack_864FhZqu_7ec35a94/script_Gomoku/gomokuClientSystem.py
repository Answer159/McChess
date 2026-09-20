# -*- coding: utf-8 -*-

import mod.client.extraClientApi as clientApi
import config
from coroutineMgrGac import CoroutineMgr

from mod_log import logger

ClientSystem = clientApi.GetClientSystemCls()


class GomokuClientSystem(ClientSystem):
	"""五子棋客户端系统：目前只负责比分文字板（立在编辑器TextAnchor预设的位置）。

	为什么要有客户端系统：TextBoard（世界里的文字板）是纯客户端组件，服务端
	没有这套API——想把比分立在场地里，只能由客户端建板。
	为什么一行一块板：引擎里一块板只有一个文字颜色，而需求是"每个玩家的分数用
	自己的颜色"，所以拆成标题一块 + 每名玩家一块，自上而下按
	config.ScoreBoardLineHeight递减Y摆放（文字板也不确定吃不吃§颜色码，颜色
	统一走SetBoardTextColor，不写§码）。
	文字内容与颜色全部由服务端排好推过来（config.GomokuScoreBoardEvent，见
	服务端BuildScoreBoardData），这里只做建板/改字/改色/回收。
	板是客户端本地对象，不随存档持久——重进地图会重建，进来后主动向服务端
	索要一次当前比分（config.GomokuScoreRequestEvent）。
	"""

	def __init__(self, namespace, systemName):
		ClientSystem.__init__(self, namespace, systemName)
		# 标题行的板id（建好后不再变）
		self.titleBoardId = None
		# 玩家行的板id，按行序（第i个 = 锚点下方第i+1行）
		self.rowBoardIds = []
		# 最近一次收到的比分行 [[整行文字, RGBA], ...]；板还没建好时先缓存文案
		self.scoreRows = []
		self.boardsCreated = False
		self.ListenEvent()

	def ListenEvent(self):
		self.ListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(),
			config.UiInitFinishedEvent, self, self.OnUIInitFinished)
		self.ListenForEvent(config.ModName, config.ServerSystemName,
			config.GomokuScoreBoardEvent, self, self.OnScoreBoardUpdate)

	def UnListenEvent(self):
		self.UnDefineEvent(config.GomokuScoreRequestEvent)
		self.UnListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(),
			config.UiInitFinishedEvent, self, self.OnUIInitFinished)
		self.UnListenForEvent(config.ModName, config.ServerSystemName,
			config.GomokuScoreBoardEvent, self, self.OnScoreBoardUpdate)

	# ---------- 比分文字板 ----------

	def OnUIInitFinished(self, args):
		"""客户端就绪：延迟建板（此刻levelId/维度可能还没就绪，与EndLogic的系列赛
		记分牌同款避竞态写法），建好后主动索要当前比分"""
		if not config.ScoreBoardAnchor:
			return  # 锚点为None = 比分文字板功能关闭
		CoroutineMgr.StartCoroutine(self.DelayCreateScoreBoard())

	def DelayCreateScoreBoard(self):
		yield -config.ScoreBoardCreateDelayFrames
		self.CreateTitleBoard()
		self.boardsCreated = True
		# 服务端可能已经推过一轮（缓存在scoreRows里），先按现有数据铺一次
		self.RefreshScoreBoard()
		# 再主动要一次：晚进服/重连的玩家不必等到下一局结算才看到比分
		data = self.CreateEventData()
		data['playerId'] = clientApi.GetLocalPlayerId()
		self.NotifyToServer(config.GomokuScoreRequestEvent, data)

	def GetTextBoardComp(self):
		return clientApi.GetEngineCompFactory().CreateTextBoard(clientApi.GetLevelId())

	def GetRowPos(self, index):
		"""第index行的世界坐标（index=0是标题行）：锚点方块中心上方
		ScoreBoardLiftY 格（锚点贴地，直接用锚点高度会把字埋进土里），
		每往下一行降config.ScoreBoardLineHeight格"""
		x, y, z = config.ScoreBoardAnchor
		return (x + 0.5, y + config.ScoreBoardLiftY - index * config.ScoreBoardLineHeight, z + 0.5)

	def CreateBoard(self, comp, text, rgba, index):
		"""建一块板并摆到第index行；创建失败返回None（调用方停止继续建，
		免得后面的板与行序错位）"""
		boardId = comp.CreateTextBoardInWorld(text, tuple(rgba),
			tuple(config.ScoreBoardBackColor), config.ScoreBoardFaceCamera)
		if not boardId:
			logger.error("[Gomoku] 比分文字板创建失败: 第{}行".format(index))
			return None
		comp.SetBoardScale(boardId, tuple(config.ScoreBoardScale))
		comp.SetBoardPos(boardId, self.GetRowPos(index))
		return boardId

	def CreateTitleBoard(self):
		comp = self.GetTextBoardComp()
		if self.titleBoardId:
			comp.RemoveTextBoard(self.titleBoardId)
			self.titleBoardId = None
		self.titleBoardId = self.CreateBoard(comp, config.ScoreBoardTitle,
			config.ScoreBoardTitleColor, 0)
		if self.titleBoardId:
			logger.info("[Gomoku] 比分文字板已创建于 {}".format(config.ScoreBoardAnchor))

	def RefreshScoreBoard(self):
		"""按最近一次比分数据刷新玩家行：行数没变就只改字改色（不重建板，避免
		每次结算闪一下）；行数变了才补建新板/回收多出来的板（人少了不能让上一
		局的行留在场上）"""
		comp = self.GetTextBoardComp()
		rows = self.scoreRows
		if not rows:
			rows = [[config.ScoreBoardWaitingText, config.PlayerColorFallback["rgba"]]]
		for index, row in enumerate(rows):
			text, rgba = row[0], tuple(row[1])
			if index < len(self.rowBoardIds):
				boardId = self.rowBoardIds[index]
				comp.SetText(boardId, text)
				comp.SetBoardTextColor(boardId, rgba)
				continue
			boardId = self.CreateBoard(comp, text, rgba, index + 1)
			if not boardId:
				break
			self.rowBoardIds.append(boardId)
		for boardId in self.rowBoardIds[len(rows):]:
			comp.RemoveTextBoard(boardId)
		del self.rowBoardIds[len(rows):]

	def OnScoreBoardUpdate(self, args):
		"""服务端广播/补推比分 -> 刷新文字板（板还没建好时先缓存，建好后自动补上）"""
		rows = args.get('rows')
		if rows is None:
			return
		self.scoreRows = rows
		if self.boardsCreated:
			self.RefreshScoreBoard()

	def RemoveAllBoards(self):
		try:
			comp = self.GetTextBoardComp()
			if self.titleBoardId:
				comp.RemoveTextBoard(self.titleBoardId)
			for boardId in self.rowBoardIds:
				comp.RemoveTextBoard(boardId)
		except Exception as e:
			logger.warning("[Gomoku] 回收比分文字板失败: {}".format(e))
		self.titleBoardId = None
		self.rowBoardIds = []
		self.boardsCreated = False

	def Update(self):
		CoroutineMgr.Tick()

	def Destroy(self):
		logger.info("===== Gomoku Client System Destroy =====")
		self.RemoveAllBoards()
		self.UnListenEvent()
