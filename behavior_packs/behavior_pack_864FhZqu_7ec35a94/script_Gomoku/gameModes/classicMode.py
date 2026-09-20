# -*- coding: utf-8 -*-
# =====================================================================
# 经典模式：原样保留合并模式框架之前的全部行为——地形用地图原生地形、
# 资源在环形区域随机刷、方块随处可放、复活点走宿主默认算法。
# 一行覆盖都没有，就是"基类默认实现 = 经典行为"这条约定的体现。
# =====================================================================
from .baseMode import GameModeBase

from mod_log import logger


class ClassicMode(GameModeBase):
	Key = "classic"
	Name = "经典模式"

	def OnEnter(self):
		logger.info("[Gomoku] 玩法模式: {}".format(self.Name))
