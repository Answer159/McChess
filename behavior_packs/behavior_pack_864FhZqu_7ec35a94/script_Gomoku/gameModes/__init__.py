# -*- coding: utf-8 -*-
# 玩法模式包：一个模式一个文件，全部实现 baseMode.GameModeBase 的钩子。
# 宿主（gomokuServerSystem）只通过 modeFactory.CreateGameMode 拿到一个模式对象，
# 再按钩子调用——加/删模式不需要改宿主一行代码。
