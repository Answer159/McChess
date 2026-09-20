# -*- coding: utf-8 -*-
# =====================================================================
# 模式工厂：把 config.GameMode 这个字符串变成一个模式对象。
#
# 宿主（gomokuServerSystem）只认识 CreateGameMode 和 baseMode.GameModeBase 的
# 钩子，不认识任何具体模式——所以：
#   新增一个模式 = 写 xxxMode.py（继承 GameModeBase）+ xxxModeConfig.py，
#                  再在下面 GameModeClsDict 里登记一行，宿主零改动；
#   切换模式     = 改 config.GameMode，重进地图生效；
#   写错模式名   = 记一条警告并退回经典模式（不让整局崩掉）。
# =====================================================================
# ★必须显式相对导入：本包是 script_Gomoku.gameModes 子包，宿主的 config.py
# 和本包的兄弟模块都不在 SDK 的绝对导入搜索路径上——`import config` 会报
# ImportError: No module named config，整个 Gomoku 服务端系统随之加载失败
# （棋盘不生成、复活点不设置，2026-09-18 20:14 起本地服务端日志实测）。
# 同款写法见 script_Team 的 modServer/modCommon 结构。
from .. import config
from .baseMode import GameModeBase
from .classicMode import ClassicMode
from .trapMode import TrapMode

from mod_log import logger

# 模式注册表：config.GameMode 的取值 -> 模式类
GameModeClsDict = {
	ClassicMode.Key: ClassicMode,
	TrapMode.Key: TrapMode,
}

# 配置写错/缺省时用哪个模式
DefaultModeKey = ClassicMode.Key


def GetGameModeKey():
	"""当前配置的模式键（config 里没写 GameMode 时按经典模式）"""
	return getattr(config, 'GameMode', DefaultModeKey) or DefaultModeKey


def CreateGameMode(serverSystem, modeKey=None):
	"""造一个模式对象。任何异常都退回经典模式——模式是玩法增强，
	不该因为一个新模式有毛病就让五子棋本体打不了"""
	key = modeKey or GetGameModeKey()
	modeCls = GameModeClsDict.get(key)
	if modeCls is None:
		logger.warning("[Gomoku] 未知的玩法模式 '{}'，可选: {}；已退回 {}".format(
			key, list(GameModeClsDict.keys()), DefaultModeKey))
		modeCls = GameModeClsDict[DefaultModeKey]
	try:
		return modeCls(serverSystem)
	except Exception as e:
		logger.error("[Gomoku] 玩法模式 '{}' 创建失败({})，已退回基础行为".format(key, e))
		return GameModeBase(serverSystem)
