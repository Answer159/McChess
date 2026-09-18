# -*- coding: utf-8 -*-
import time

import mod.client.extraClientApi as clientApi
import config
from mod_log import logger

ClientSystem = clientApi.GetClientSystemCls()

# 移动键码 -> 输入向量 (left, forward)（KeyBoardType枚举，见ModSDK文档；
# OnKeyPressInGame的key参数是str）。W/A/S/D与方向键都认。
# 局限：只认默认键位——玩家改键后映射不到（改键绑定走OnCustomKeyChangedEvent，暂不处理）
CHAOS_MOVE_KEYS = {
	87: (0, 1),   # W 前进
	38: (0, 1),   # ↑
	83: (0, -1),  # S 后退
	40: (0, -1),  # ↓
	65: (1, 0),   # A 左移
	37: (1, 0),   # ←
	68: (-1, 0),  # D 右移
	39: (-1, 0),  # →
}


class GomokuClientSystem(ClientSystem):
	"""GomokuMod客户端系统：说明书弹窗 + 混乱药水的视角/移动反向。

	script_Gomoku原本纯服务端，说明书是本系统最初的职责——
	服务端ManualOpenEvent（手持说明书右键）-> PushScreen弹出manualUI，
	关闭由窗口内按钮PopScreen。后续若加记分牌/倒计时等客户端UI也挂这里。

	混乱药水的移动反向只能做在客户端（服务端改不了玩家输入）：
	服务端ChaosConfuseEvent（混乱药水命中本客户端玩家，见HandleChaosPotionHit）
	-> 记录到期时刻，此后把真实输入向量(左,前)取负LockInputVector
	（W<->S、A<->D对调，位移=输入*相机朝向，输入取负则W朝屏幕外走）。
	只反移动、不反视角（实测镜像视角的方案被否）。
	真实输入的来源按平台分层（GetInputVector在锁定中只返回锁定回声而非真实
	按键——实测按住W读数仍为(0,0)；逐帧解锁读/逐帧重锁都会让引擎反复读到
	交替输入，人原地疯狂抖动；负移速被引擎钳成0、客户端PosComponent没有
	SetPos——全部试败，事件驱动是正解）：
	  PC键盘：OnKeyPressInGame维护按住键集合，键一变才锁；
	  PC手柄：OnGamepadStickClientEvent摇杆一动才锁；
	  手机/触屏模式（含PC按F11的鼠标模拟触屏）：自造假摇杆HUD（见chaosJoystickUI）
	  ——大号isSwallow触摸按钮盖住真摇杆区域自收触摸，输入向量自己算自己锁，
	  彻底绕开轮盘无事件/GetInputVector回声/解锁清零三个死结。
	到期/提前解除走ChaosStop统一收尾（务必解锁输入）

	时间停止的输入冻结同样只能做在客户端（时间停止道具右键，见服务端
	HandleTimestopUse）：服务端TimestopFreezeEvent -> 记录到期时刻并用
	operationComp关本地输入——SetCanMove/SetCanJump/SetCanAttack（PC键鼠
	与触屏全屏蔽移动/跳跃/攻击与破坏，SetCanMove(False)还顺带清掉按住的
	输入向量，立即停下）；视角转动不关（被冻住也能干瞪眼）。只在开始/结束
	各设一次、不逐帧重设；到期走OnScriptTickClient的本地时钟TimestopStop
	恢复（务必恢复，否则输入会一直关着）。挖掘/落子/道具/拾取的拦截在
	服务端（IsTimestopFrozen），客户端这层是体验、服务端是权威兜底"""

	def __init__(self, namespace, systemName):
		ClientSystem.__init__(self, namespace, systemName)
		self.ListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(),
			"UiInitFinished", self, self.OnUiInitFinished)
		self.ListenForEvent(config.ModName, config.ServerSystemName,
			config.ManualOpenEvent, self, self.OnManualOpen)
		self.ListenForEvent(config.ModName, config.ServerSystemName,
			config.ChaosConfuseEvent, self, self.OnChaosConfuse)
		self.ListenForEvent(config.ModName, config.ServerSystemName,
			config.TimestopFreezeEvent, self, self.OnTimestopFreeze)
		self.ListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(),
			config.ScriptTickClientEvent, self, self.OnScriptTickClient)
		self.ListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(),
			config.OnKeyPressInGameEvent, self, self.OnKeyPressInGame)
		self.ListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(),
			config.GamepadStickClientEvent, self, self.OnGamepadStick)
		# 屏幕点击松手（移动端/F11触发）：假摇杆拖动的结束信号（TouchUp在
		# F11鼠标模拟下不可靠，见chaosJoystickUI的PollDrag注释）
		self.ListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(),
			config.TapOrHoldReleaseClientEvent, self, self.OnTapRelease)
		# 混乱药水：到期时刻（本地时钟；0=未混乱）、真实输入向量(left,forward)、
		# 按住键集合与上一帧设定yaw基准（移动反向+视角左右反向用，见类docstring）；
		# chaosJoyNode=假摇杆HUD节点（触屏模式用，OnUiInitFinished创建）
		self.chaosUntil = 0.0
		self.chaosInputVec = (0.0, 0.0)
		self.chaosHeldKeys = set()
		self.chaosLastYaw = None
		self.chaosJoyNode = None
		# 时间停止：解冻时刻（本地时钟；0=未冻结）。冻结期间本地移动/跳跃/攻击
		# 输入被关（见OnTimestopFreeze），到期OnScriptTickClient自动恢复
		self.timestopUntil = 0.0

	def OnUiInitFinished(self, args):
		# RegisterUI须在引擎UI就绪后调用一次（对照LimitedRespawn客户端写法）；
		# 画布路径 "gomokuManualUI.main" 对应ui/gomokuManualUI.json的namespace与main画布
		clientApi.RegisterUI(config.ModName, config.ManualUIName,
			config.ScriptFolderName + '.' + config.ManualUIPyClsPath, config.ManualUIScreenDef)
		# 假摇杆HUD（混乱药水手机/触屏模式的移动反向）：常驻创建、默认隐藏，
		# 混乱开始时SetChaos(True)显示（见chaosJoystickUI.py）
		clientApi.RegisterUI(config.ModName, config.ChaosJoystickUIName,
			config.ScriptFolderName + '.' + config.ChaosJoystickUIPyClsPath, config.ChaosJoystickUIScreenDef)
		clientApi.CreateUI(config.ModName, config.ChaosJoystickUIName, {"isHud": 1})
		self.chaosJoyNode = clientApi.GetUI(config.ModName, config.ChaosJoystickUIName)

	def IsTouchMode(self):
		"""触屏控制模式：手机平台，或PC按F11进"鼠标模拟触屏"（虚拟摇杆此时
		才出现，GetPlatform仍返回0——用IsTouchWithMouse区分，方便PC上测试）"""
		try:
			return clientApi.GetPlatform() != 0 or clientApi.IsTouchWithMouse()
		except Exception:
			return False

	def OnManualOpen(self, args):
		"""服务端请求打开说明书：PushScreen入栈并接管输入，关闭走窗口按钮（PopScreen）。
		首屏渲染不在这里做——PushScreen返回node时控件树可能尚未创建，
		由引擎在就绪后调ManualUIScreen.Create"""
		node = clientApi.PushScreen(config.ModName, config.ManualUIName, None)
		if node is None:
			logger.warning("[Gomoku] 说明书界面创建失败（RegisterUI未执行？）")

	# ---------- 混乱药水 ----------

	def OnChaosConfuse(self, args):
		"""服务端通知本客户端玩家被混乱（混乱药水命中/#chaos调试命令）：记录到期
		时刻，播种当前真实输入并立即反向锁定；此后移动输入按平台分流维护
		（见OnScriptTickClient/OnKeyPressInGame/OnGamepadStick）。
		连中两瓶只重置时长；duration=0 = 服务端要求立即解除（#unchaos/新一局开始）"""
		try:
			duration = float(args.get('duration', 0))
		except (TypeError, ValueError):
			duration = 0.0
		if duration <= 0:
			self.ChaosStop()
			return
		self.chaosUntil = time.time() + duration
		self.chaosHeldKeys = set()
		self.chaosLastYaw = None  # 下一帧先取基准，不从旧视角跳变
		self.chaosInputVec = (0.0, 0.0)
		if self.IsTouchMode():
			# 触屏模式：假摇杆接管移动（见chaosJoystickUI）——轮盘无输入事件、
			# GetInputVector锁定中只有回声、逐帧解锁又清零输入，旁路全堵死，
			# 只能自造摇杆自己收触摸。键盘播种/事件路径不参与
			if self.chaosJoyNode:
				self.chaosJoyNode.SetChaos(True)
			logger.info("[Gomoku] 混乱开始（触屏）：假摇杆接管移动，视角左右反向{}秒".format(duration))
			return
		# PC键鼠：播种——命中瞬间玩家可能正按着键，按键事件只报"变化"拿不到存量，
		# 此刻还没锁过、GetInputVector读的就是真实值（锁定后只会返回回声）
		try:
			localId = clientApi.GetLocalPlayerId()
			if localId:
				motionComp = clientApi.GetEngineCompFactory().CreateActorMotion(localId)
				if motionComp:
					motionComp.UnlockInputVector()  # 清掉可能残留的旧锁再读
					vec = motionComp.GetInputVector()
					if vec and len(vec) >= 2:
						self.chaosInputVec = (vec[0], vec[1])
						# 按近似阈值把存量向量还原成键位（对角=两键同按）
						if vec[0] > 0.5:
							self.chaosHeldKeys.add(65)   # A
						elif vec[0] < -0.5:
							self.chaosHeldKeys.add(68)  # D
						if vec[1] > 0.5:
							self.chaosHeldKeys.add(87)  # W
						elif vec[1] < -0.5:
							self.chaosHeldKeys.add(83)  # S
					self.LockChaosInput()
		except Exception as e:
			logger.warning("[Gomoku] 混乱开始播种输入失败: {}".format(e))
		logger.info("[Gomoku] 混乱开始：视角+移动反向{}秒".format(duration))

	def ChaosStop(self):
		"""混乱结束/提前解除的统一收尾：清状态并解锁移动输入——必须解锁，
		否则玩家的方向键会一直被锁在最后一次反向值上"""
		self.chaosUntil = 0.0
		self.chaosInputVec = (0.0, 0.0)
		self.chaosHeldKeys = set()
		self.chaosLastYaw = None
		if self.chaosJoyNode:
			self.chaosJoyNode.SetChaos(False)  # 收起假摇杆（触屏模式）
		try:
			localId = clientApi.GetLocalPlayerId()
			if localId:
				motionComp = clientApi.GetEngineCompFactory().CreateActorMotion(localId)
				if motionComp:
					motionComp.UnlockInputVector()
			logger.info("[Gomoku] 混乱结束，视角与移动已恢复正常")
		except Exception as e:
			logger.warning("[Gomoku] 解除混乱失败: {}".format(e))

	def LockChaosInput(self):
		"""把当前真实输入向量(左,前)取负锁进引擎（W<->S、A<->D对调，位移=输入*相机
		朝向，输入取负则W朝屏幕外走）。只在输入变化时调用（事件驱动/轮询检测到变化），
		不逐帧重锁——反复Lock会与引擎输入采样打架（实测人原地疯狂抖动）"""
		localId = clientApi.GetLocalPlayerId()
		if not localId:
			return
		try:
			motionComp = clientApi.GetEngineCompFactory().CreateActorMotion(localId)
			if motionComp:
				motionComp.LockInputVector((-self.chaosInputVec[0], -self.chaosInputVec[1]))
		except Exception as e:
			logger.warning("[Gomoku] 混乱输入锁定失败: {}".format(e))

	def OnKeyPressInGame(self, args):
		"""键盘按下/弹起（引擎事件；key/isDown参数是str）：混乱期间维护WASD/方向键
		按住状态，键一变就按新状态反向锁输入。真实按键只能从这拿——GetInputVector
		在锁定中只返回锁定回声（实测按住W读数仍为(0,0)）"""
		if self.chaosUntil <= 0:
			return
		if self.IsTouchMode():
			return  # 触屏模式：移动由假摇杆接管（见chaosJoystickUI），键盘不参与
		try:
			key = int(args.get('key'))
			isDown = str(args.get('isDown')) == '1'
		except (TypeError, ValueError):
			return
		if key not in CHAOS_MOVE_KEYS:
			return
		if isDown:
			self.chaosHeldKeys.add(key)
		else:
			self.chaosHeldKeys.discard(key)
		left = sum(CHAOS_MOVE_KEYS[k][0] for k in self.chaosHeldKeys)
		forward = sum(CHAOS_MOVE_KEYS[k][1] for k in self.chaosHeldKeys)
		# 对角（两键同按）归一化——引擎把输入向量按单位向量用（见LockInputVector文档）
		mag = (left * left + forward * forward) ** 0.5
		if mag > 1e-6:
			left, forward = left / mag, forward / mag
		if (left, forward) != self.chaosInputVec:
			self.chaosInputVec = (left, forward)
			self.LockChaosInput()

	def OnGamepadStick(self, args):
		"""手柄摇杆事件（x从左到右-1~1，y从下到上-1~1；摇杆归位也会触发一次0,0）：
		混乱期间摇杆一动就按反向锁输入。注意输入向量第一项是"向左"的量，
		摇杆x=+1（推右）对应左=-x"""
		if self.chaosUntil <= 0:
			return
		if self.IsTouchMode():
			return  # 触屏模式：移动由假摇杆接管（见chaosJoystickUI），手柄不参与
		x, y = args.get('x', 0.0), args.get('y', 0.0)
		vec = (-x, y)
		if vec != self.chaosInputVec:
			self.chaosInputVec = vec
			self.LockChaosInput()

	# ---------- 时间停止 ----------

	def OnTimestopFreeze(self, args):
		"""服务端通知本客户端玩家被时间停止（时间停止道具右键/#调试）：记录到期
		时刻并关掉本地移动/跳跃/攻击输入（见SetTimestopControls；视角转动保留）。
		连吃两次只重置时长；duration=0 = 服务端要求立即解冻（新一局开始）"""
		try:
			duration = float(args.get('duration', 0))
		except (TypeError, ValueError):
			duration = 0.0
		if duration <= 0:
			self.TimestopStop()
			return
		self.timestopUntil = time.time() + duration
		self.SetTimestopControls(False)
		logger.info("[Gomoku] 时间停止开始：输入冻结{}秒（可转视角）".format(duration))

	def SetTimestopControls(self, enabled):
		"""开关本地玩家的移动/跳跃/攻击输入（时间停止用，operationComp按文档
		传levelId创建）。SetCanMove(False)会顺带清掉当前输入向量——按着前进键
		也会立即停下（见控制组件文档），正好是"冻结"的表现"""
		try:
			operationComp = clientApi.GetEngineCompFactory().CreateOperation(clientApi.GetLevelId())
			if operationComp:
				operationComp.SetCanMove(enabled)
				operationComp.SetCanJump(enabled)
				operationComp.SetCanAttack(enabled)
		except Exception as e:
			logger.warning("[Gomoku] 时间停止开关输入失败: {}".format(e))

	def TimestopStop(self):
		"""时间停止结束/提前解除的统一收尾：恢复移动/跳跃/攻击输入——必须恢复，
		否则玩家的输入会一直关着（连聊天外的一切操作都动不了）"""
		if self.timestopUntil <= 0:
			return
		self.timestopUntil = 0.0
		self.SetTimestopControls(True)
		logger.info("[Gomoku] 时间停止结束，输入已恢复")

	def OnScriptTickClient(self, args=None):
		"""每帧回调。时间停止到期检查（本地时钟到期自动恢复输入，见TimestopStop）；
		混乱期间的职责见下方正文（到期走ChaosStop统一收尾）：视角左右反向——
		只镜像yaw（鼠标向左转视角向右、向反向转同样角度），pitch上下不动。
		实现：当前yaw与上一帧设定值的差=本帧鼠标水平增量，按相反方向设回
		（纯镜像无跳变）；SetRot的pitch参数原样透传引擎现值。
		移动反向不在这里做：PC键鼠走事件驱动（OnKeyPressInGame/OnGamepadStick），
		触屏模式由假摇杆HUD接管（见chaosJoystickUI）"""
		if self.timestopUntil > 0 and time.time() >= self.timestopUntil:
			self.TimestopStop()
		if self.chaosUntil <= 0:
			return
		if time.time() >= self.chaosUntil:
			self.ChaosStop()
			return
		localId = clientApi.GetLocalPlayerId()
		if not localId:
			return
		# ---- 1. 视角左右反向 ----
		try:
			rotComp = clientApi.GetEngineCompFactory().CreateRot(localId)
			rot = rotComp.GetRot() if rotComp else None
			if rot and len(rot) >= 2:
				pitch, yaw = rot[0], rot[1]
				if self.chaosLastYaw is None:
					# 首帧只记基准不动视角，避免从混乱前的旧值跳变
					self.chaosLastYaw = yaw
				else:
					# 本帧鼠标水平增量（yaw跨±180°环绕取最短差）
					dYaw = (yaw - self.chaosLastYaw + 180.0) % 360.0 - 180.0
					# 反向设回：yaw向鼠标转动的相反方向转同样角度，pitch透传不动
					newYaw = (self.chaosLastYaw - dYaw) % 360.0
					if rotComp.SetRot((pitch, newYaw)):
						self.chaosLastYaw = newYaw
					else:
						self.chaosLastYaw = yaw  # 写失败以引擎现值当基准
		except Exception as e:
			logger.warning("[Gomoku] 混乱视角镜像失败: {}".format(e))
			self.chaosLastYaw = None
		# ---- 2. 移动输入反向 ----
		# 触屏模式：假摇杆HUD接管（chaosJoystickUI）。TouchMove在F11鼠标模拟下
		# 不触发（实测TouchDown来、Move不来），按住期间这里每帧轮询GetTouchPos
		# 兜底（真触屏的TouchMove回调与轮询共用HandleDrag，互不冲突）；
		# PC键鼠：键盘/手柄走事件驱动（OnKeyPressInGame/OnGamepadStick），
		# 本帧循环不做输入轮询——逐帧解锁会清掉轮盘输入、逐帧重锁会抖动，均已试败
		if self.chaosJoyNode and self.chaosJoyNode.dragging:
			self.chaosJoyNode.PollDrag()

	def OnTapRelease(self, args):
		"""屏幕点击松手（移动端/F11触发）：假摇杆拖动结束——TouchUp回调
		在F11下未必可靠，这里是权威结束信号（不判断args，无参数）"""
		if self.chaosJoyNode and self.chaosJoyNode.dragging:
			self.chaosJoyNode.EndDrag()

	def Destroy(self):
		# 时间停止若还在冻结中，先恢复输入再拆监听——否则输入会一直关着
		self.TimestopStop()
		self.UnListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(),
			"UiInitFinished", self, self.OnUiInitFinished)
		self.UnListenForEvent(config.ModName, config.ServerSystemName,
			config.ManualOpenEvent, self, self.OnManualOpen)
		self.UnListenForEvent(config.ModName, config.ServerSystemName,
			config.ChaosConfuseEvent, self, self.OnChaosConfuse)
		self.UnListenForEvent(config.ModName, config.ServerSystemName,
			config.TimestopFreezeEvent, self, self.OnTimestopFreeze)
		self.UnListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(),
			config.ScriptTickClientEvent, self, self.OnScriptTickClient)
		self.UnListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(),
			config.OnKeyPressInGameEvent, self, self.OnKeyPressInGame)
		self.UnListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(),
			config.TapOrHoldReleaseClientEvent, self, self.OnTapRelease)
		self.UnListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(),
			config.GamepadStickClientEvent, self, self.OnGamepadStick)
