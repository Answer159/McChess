# -*- coding: utf-8 -*-
import math

import mod.client.extraClientApi as clientApi
import config
from mod_log import logger

ScreenNode = clientApi.GetScreenNodeCls()
ViewBinder = clientApi.GetViewBinderCls()
ViewRequest = clientApi.GetViewViewRequestCls()

# 兜底尺寸（px，与ui/chaosJoystickUI.json的默认保持一致）——正常情况底盘会
# 按原生摇杆的实际区域放置（见PlaceJoyAtNative），这些只在读不到原生区域时用
CHAOS_JOY_FRAME_SIZE = 140.0
CHAOS_JOY_KNOB_SIZE = 64.0
CHAOS_JOY_RADIUS = 40.0
# 摇杆头占底盘的比例（原生摇杆的观感比例）
CHAOS_JOY_KNOB_RATIO = 0.46
# 可见底盘占原生摇杆触控热区的比例——MoveStickBtn区域是热区（比可见圆环大一圈），
# 底盘贴满热区会显大；触摸按钮仍占满热区（点击范围=原生），只有可见部分缩放。
# ★观感偏大就调小、偏小就调大（0.6~0.8之间微调）
CHAOS_JOY_VISUAL_RATIO = 0.7


class ChaosJoystickScreen(ScreenNode):
	"""混乱药水的假摇杆HUD（手机/触屏模式的移动反向）。

	虚拟摇杆没有输入事件、GetInputVector锁定中只返回回声、逐帧解锁又把轮盘
	输入清零——手机端没有任何旁路能拿到真实输入（见gomokuClientSystem的
	方案演变）。干脆自造摇杆：
	  位置与大小：GetOriginAreaOffset读原生摇杆（MoveStickBtn）的实际区域，
	  底盘/摇杆头精确贴上去（含玩家自定义布局）——须在HideMoveGui隐藏原生
	  摇杆之前读（隐藏后可能返回全零）；读不到时退回JSON里的默认位置。
	  触摸：isSwallow按钮自收（原生隐藏后原位置不再响应，让位）。
	  输入：拖动向量=触点-底盘中心（固定摇杆，与原版一致），取负后直接
	  LockInputVector——输入源完全在自己手里，引擎回声/清零问题都不存在。

	触摸事件的两级来源（F11鼠标模拟的TouchMove不触发，实测TouchDown来Move不来）：
	  真触屏：SetButtonTouchMoveCallback回调（带TouchPosX/Y）；
	  F11/兜底：按住期间由gomokuClientSystem每帧轮询GetTouchPos。
	  两条路共用HandleDrag（幂等方向计算），互不冲突；拖动结束由
	  TapOrHoldReleaseClientEvent（松手，移动端/F11都有）与TouchUp回调兜底。

	视觉也表达"反了"：摇杆头显示在拖动方向关于底盘中心的镜像点——
	玩家看到的摇杆头位置就是实际移动方向。
	控件路径镜像ui/chaosJoystickUI.json的joyPanel子树。"""

	def __init__(self, namespace, name, param):
		ScreenNode.__init__(self, namespace, name, param)
		self.enabled = False
		self.dragging = False    # 按住拖动中（TouchDown置位，抬手/解除复位）
		self.anchorPos = None    # 拖动方向基准=底盘中心（固定摇杆）
		self.frameCenter = None  # 底盘中心屏幕坐标（PlaceJoyAtNative算）
		self.frameSize = None    # 底盘尺寸 (w, h)
		self.knobSize = None     # 摇杆头尺寸 (w, h)
		self.joyRadius = CHAOS_JOY_RADIUS  # 摇杆头活动半径（按底盘尺寸算）

	def Create(self):
		"""引擎生命周期钩子：控件树就绪后挂触摸回调。isSwallow=True——
		按钮区域的触摸被吞掉（镜头转向等不响应），盖住底盘下的原生输入"""
		try:
			btn = self.GetBaseUIControl("/joyPanel/touch").asButton()
			btn.AddTouchEventParams({"isSwallow": True})
			btn.SetButtonTouchDownCallback(self.OnTouchDown)
			btn.SetButtonTouchMoveCallback(self.OnTouchMove)
			btn.SetButtonTouchUpCallback(self.OnTouchUp)
			btn.SetButtonTouchCancelCallback(self.OnTouchUp)
			btn.SetButtonScreenExitCallback(self.OnTouchUp)
		except Exception as e:
			logger.warning("[Gomoku] 假摇杆初始化失败: {}".format(e))
		self.SetChaos(False)

	def PlaceJoyAtNative(self):
		"""把假摇杆贴到原生摇杆的实际位置/大小上。
		GetOriginAreaOffset读MoveStickBtn的区域（xMin,yMin,xMax,yMax，屏幕
		左上角原点，含玩家的自定义布局）——底盘铺满整个原生摇杆区、摇杆头
		按比例放中心。读不到（全零/异常）时退回JSON默认位置（GetGlobalPosition
		+兜底常量）。必须在HideMoveGui之前调用"""
		try:
			area = clientApi.GetOriginAreaOffset(
				clientApi.GetMinecraftEnum().OriginGUIName.MoveStickBtn)
			if area and len(area) >= 4 and (area[2] > area[0] or area[3] > area[1]):
				xMin, yMin, xMax, yMax = area[0], area[1], area[2], area[3]
				fw, fh = xMax - xMin, yMax - yMin
				self.ApplyJoyLayout((xMin, yMin), (fw, fh))
				logger.info("[Gomoku] 假摇杆已对齐原生摇杆区域: {}".format(area))
				return
		except Exception as e:
			logger.warning("[Gomoku] 读取原生摇杆区域失败: {}".format(e))
		# 兜底：JSON默认位置（GetGlobalPosition取px坐标，尺寸用兜底常量）
		try:
			frame = self.GetBaseUIControl("/joyPanel/frame")
			pos = frame.GetGlobalPosition() if frame else None
			if pos and len(pos) >= 2:
				self.ApplyJoyLayout((pos[0], pos[1]),
					(CHAOS_JOY_FRAME_SIZE, CHAOS_JOY_FRAME_SIZE))
				return
		except Exception as e:
			logger.warning("[Gomoku] 读取假摇杆默认位置失败: {}".format(e))
		# 全都失败：只记中心为未知（OnTouchDown会退回用触点当基准）
		self.frameCenter = None
		self.framePos = None

	def ApplyJoyLayout(self, areaTopLeft, areaSize):
		"""按给定的原生摇杆热区布置三层控件：
		触摸按钮=整个热区（点击范围与原生一致）；可见底盘=热区中心按
		CHAOS_JOY_VISUAL_RATIO缩放（热区比可见圆环大一圈，贴满会显大）；
		摇杆头=底盘的CHAOS_JOY_KNOB_RATIO，居中"""
		areaW, areaH = float(areaSize[0]), float(areaSize[1])
		areaCenter = (areaTopLeft[0] + areaW / 2.0, areaTopLeft[1] + areaH / 2.0)
		# 可见底盘：热区按比例缩放、居中
		self.frameSize = (areaW * CHAOS_JOY_VISUAL_RATIO, areaH * CHAOS_JOY_VISUAL_RATIO)
		frameTopLeft = (areaCenter[0] - self.frameSize[0] / 2.0,
			areaCenter[1] - self.frameSize[1] / 2.0)
		self.knobSize = (self.frameSize[0] * CHAOS_JOY_KNOB_RATIO,
			self.frameSize[1] * CHAOS_JOY_KNOB_RATIO)
		self.frameCenter = areaCenter  # 拖动方向基准=热区中心（=可见底盘中心）
		# 摇杆头活动半径：从中心到环边的行程（(底盘-摇杆头)/2）
		self.joyRadius = max(10.0, (self.frameSize[0] - self.knobSize[0]) / 2.0)
		try:
			frame = self.GetBaseUIControl("/joyPanel/frame")
			if frame:
				frame.SetSize(self.frameSize)
				frame.SetPosition(frameTopLeft)
			knob = self.GetBaseUIControl("/joyPanel/knob")
			if knob:
				knob.SetSize(self.knobSize)
				knob.SetPosition((self.frameCenter[0] - self.knobSize[0] / 2.0,
					self.frameCenter[1] - self.knobSize[1] / 2.0))
			# 触摸按钮罩住整个原生热区（不多扩——原生热区本身已留了余量）
			touch = self.GetBaseUIControl("/joyPanel/touch")
			if touch:
				touch.SetSize((areaW, areaH))
				touch.SetPosition(areaTopLeft)
		except Exception as e:
			logger.warning("[Gomoku] 假摇杆布局应用失败: {}".format(e))

	def SetChaos(self, enabled):
		"""混乱开始/结束时由gomokuClientSystem调用：显示/隐藏假摇杆，并同步
		隐藏/恢复原生左下移动按钮（clientApi.HideMoveGui——隐藏后原位置点击
		不响应，真摇杆彻底让位）。启用时先把假摇杆贴到原生摇杆的实际位置
		（须在读区域之后、隐藏之前，见PlaceJoyAtNative），再锁零向量——
		其余输入一概无效，只有本摇杆能动；结束时输入解锁由客户端系统的
		ChaosStop统一负责（UnlockInputVector）"""
		self.enabled = enabled
		self.SetVisible("/joyPanel/frame", enabled)
		self.SetVisible("/joyPanel/knob", enabled)
		self.SetVisible("/joyPanel/touch", enabled)
		if enabled:
			self.PlaceJoyAtNative()
		try:
			clientApi.HideMoveGui(enabled)
		except Exception as e:
			logger.warning("[Gomoku] 原生移动按钮显隐失败: {}".format(e))
		if enabled:
			self.LockJoyInput(0.0, 0.0)
		else:
			self.anchorPos = None
			self.dragging = False

	# 点击绑定（HUD的%ns式，对照skillUI写法）：common.button模板需要
	# $pressed_button_name，绑到这；移动逻辑走Touch回调/轮询（带坐标）
	@ViewBinder.binding(ViewBinder.BF_ButtonClickUp, '%chaosJoystickUI.OnJoyPressed')
	def OnJoyPressed(self, args):
		return ViewRequest.Refresh

	def OnTouchDown(self, args):
		"""手指按下：开始拖动。固定摇杆——方向基准取底盘中心（不是落点），
		底盘本身不动；取不到中心时兜底用落点"""
		if not self.enabled:
			return
		x, y = args.get('TouchPosX'), args.get('TouchPosY')
		if x is None or y is None:
			return
		self.dragging = True
		self.anchorPos = self.frameCenter if self.frameCenter else (x, y)
		self.UpdateKnob(0.0, 0.0)

	def OnTouchMove(self, args):
		"""拖动（真触屏的TouchMove回调；F11鼠标模拟不触发——见PollDrag兜底）"""
		if not self.enabled or self.anchorPos is None:
			return
		x, y = args.get('TouchPosX'), args.get('TouchPosY')
		if x is None or y is None:
			return
		self.HandleDrag(x, y)

	def PollDrag(self):
		"""轮询兜底拖动（TouchMove在F11鼠标模拟下不触发，只有真触屏才可靠）：
		由gomokuClientSystem的OnScriptTickClient在按住期间每帧调用，
		读GetTouchPos当当前触点"""
		if not self.enabled or not self.dragging:
			return
		try:
			pos = clientApi.GetTouchPos()
		except Exception:
			return
		if not pos or len(pos) < 2:
			return
		self.HandleDrag(pos[0], pos[1])

	def HandleDrag(self, x, y):
		"""拖动处理（TouchMove回调与PollDrag共用）：方向=当前触点-底盘中心。
		输入向量(左,前)：拖上(dy<0)=前+、拖右(dx>0)=左-；反转=锁其负值
		（W<->S、A<->D对调）。LockInputVector只认方向（单位向量），幅度无效"""
		if self.anchorPos is None:
			return
		dx, dy = x - self.anchorPos[0], y - self.anchorPos[1]
		dist = math.sqrt(dx * dx + dy * dy)
		if dist < 1e-4:
			self.LockJoyInput(0.0, 0.0)
			self.UpdateKnob(0.0, 0.0)
			return
		nx, ny = dx / dist, dy / dist
		left, forward = -nx, -ny
		self.LockJoyInput(-left, -forward)
		# 摇杆头镜像显示：拖动反方向的钳制偏移
		ratio = min(1.0, dist / self.joyRadius)
		self.UpdateKnob(-nx * ratio * self.joyRadius, -ny * ratio * self.joyRadius)

	def OnTouchUp(self, args):
		"""手指抬起（触摸回调路径）：走统一收尾"""
		if not self.enabled:
			return
		self.EndDrag()

	def EndDrag(self):
		"""拖动结束的统一收尾（TouchUp回调 / TapOrHoldReleaseClientEvent /
		混乱解除共用）：锁零向量（站定），摇杆头回底盘中心"""
		self.dragging = False
		self.anchorPos = None
		self.LockJoyInput(0.0, 0.0)
		self.UpdateKnob(0.0, 0.0)

	def LockJoyInput(self, left, forward):
		"""把(左,前)输入向量锁进引擎（混乱期间持续覆盖，本类自管，无回声问题）"""
		localId = clientApi.GetLocalPlayerId()
		if not localId:
			return
		try:
			motionComp = clientApi.GetEngineCompFactory().CreateActorMotion(localId)
			if motionComp:
				motionComp.LockInputVector((left, forward))
		except Exception as e:
			logger.warning("[Gomoku] 假摇杆输入锁定失败: {}".format(e))

	def UpdateKnob(self, mx, my):
		"""摇杆头画在底盘中心+(mx,my)处（mx/my=镜像偏移，px）"""
		knob = self.GetBaseUIControl("/joyPanel/knob")
		if knob and self.frameCenter and self.knobSize:
			knob.SetPosition((self.frameCenter[0] - self.knobSize[0] / 2.0 + mx,
				self.frameCenter[1] - self.knobSize[1] / 2.0 + my))
