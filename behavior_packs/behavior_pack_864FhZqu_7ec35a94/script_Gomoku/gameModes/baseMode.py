# -*- coding: utf-8 -*-
# =====================================================================
# 玩法模式基类（模式工厂的抽象产品）
#
# 为什么要有这一层：五子棋本体（棋盘/落子/判胜/道具）是所有模式共用的，
# 模式之间的差异只有很少几处——地形怎么铺、资源刷在哪、能不能放方块、
# 死后在哪重生、每帧要不要检查什么。把这几处抽成钩子，宿主
# gomokuServerSystem 在固定位置调用钩子，模式之间就互不认识、零耦合：
#   - 加一个新模式 = 新增一个 xxxMode.py + 一份 xxxModeConfig.py，
#     再在 modeFactory 里登记一行，宿主不动；
#   - 关掉新模式 = config.GameMode 改回 "classic"，运行时行为与新模式合并前一致。
#
# 约定：钩子的默认实现就是"经典模式"的行为，所以子类只覆盖自己要改的那几个。
# 模式里不要写死数值——常量放各自的 xxxModeConfig.py（本基类只用宿主的 config）。
# =====================================================================
import math
import random

# ★必须显式相对导入：本文件在 script_Gomoku.gameModes 子包里，平级的
# config.py 不在 SDK 的导入搜索路径上——绝对导入 `import config` 会报
# ImportError: No module named config（运行日志已实测，见本地服务端日志）。
# 同款写法见 script_Team 的 modServer/modCommon 结构。
from .. import config


class GameModeBase(object):
	"""玩法模式基类：默认实现 = 经典模式行为，子类按需覆盖。

	钩子清单（宿主调用点见 gomokuServerSystem 同名注释）：
	  OnEnter           模式对象创建后、监听事件之前调用一次
	  OnRoundStart      每局开始（棋盘已重铺、形状已定）后调用
	  OnTick            服务端每帧（OnTickServer）调用
	  OnPlayerAdd       玩家进服
	  OnPlayerRemove    玩家退服
	  OnPlayerDie       玩家阵亡
	  OnExit            系统销毁
	  PickSpawnColumn   资源刷新取点（返回 (x, z) 或 None=本次跳过）
	  CanPlaceBlock     玩家能否在此放置方块（False=拦截）
	  GetRespawnPos     复活点（返回 None = 用宿主默认算法）
	"""

	# 工厂注册键（= config.GameMode 的取值）与中文名（播报/日志用）
	Key = "base"
	Name = "基础模式"
	# 开局模式播报的文案key（messageConfig的mode_段；None=用通用模板
	# mode_round只报模式名）。宿主SwitchGameModeForRound每局播一次，
	# 想让玩家看到本模式的玩法提示就在子类里指一条具体文案
	RoundAnnounceKey = None

	def __init__(self, serverSystem):
		# 反向引用宿主：模式可以用它的公共能力（RunCommand / EnsureBoardCenter /
		# Announce / SendMessageToPlayer / boardSize ...），但宿主只认本基类的钩子
		self.system = serverSystem

	# ---------------------------- 生命周期 ----------------------------

	def OnEnter(self):
		"""模式启用（每次进地图一次）"""
		pass

	def OnRoundStart(self):
		"""每局开始：宿主已经重铺完棋盘基座、随机好缺格，资源刷新还没启动"""
		pass

	def OnTick(self):
		"""服务端每帧。★这里的开销直接乘以帧率，重活务必自己分帧/降频"""
		pass

	def OnPlayerAdd(self, playerId):
		pass

	def OnPlayerRemove(self, playerId):
		pass

	def OnPlayerDie(self, playerId):
		pass

	def OnExit(self):
		pass

	# ---------------------------- 资源刷新 ----------------------------

	def PickSpawnColumn(self, inner, outer, angleMin=0, angleMax=360):
		"""给一次资源刷新挑一列（x, z）。

		默认（经典模式）= 以棋盘中心为圆心，在 [inner, outer] 环、
		[angleMin, angleMax] 扇区里均匀随机取一点——与合并模式框架之前的
		SpawnAtRing/SpawnTierItem/SpawnRandomBlock 完全一致。
		返回 None 表示"本次刷新放弃"（子类用来表达"没有合法落点"）。
		"""
		cx, _, cz = self.system.EnsureBoardCenter()
		inner = self.system.ClampRingInner(inner)
		if outer < inner:
			outer = inner
		angle = math.radians(random.uniform(angleMin, angleMax))
		radius = random.uniform(inner, outer)
		return (int(cx + radius * math.sin(angle)), int(cz + radius * math.cos(angle)))

	# ---------------------------- 建造限制 ----------------------------

	def CanPlaceBlock(self, entityId, x, y, z):
		"""玩家能否在 (x, y, z) 放方块。False = 拦截（提示由模式自己发，
		宿主只负责 cancel）。默认不限制。"""
		return True

	# ---------------------------- 阵亡与复活 ----------------------------

	def GetRespawnPos(self):
		"""模式指定的复活点 (x, y, z)；返回 None = 用宿主默认算法
		（棋盘中心 + config.RespawnPosOffset，见 GetEngineRespawnPos）"""
		return None
