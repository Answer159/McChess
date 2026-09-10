## Context

MC 模组（网易 MC Studio，Python 2.7 脚本运行时）要加入五子棋玩法。已有 mod 模块均为 `script_*/modServer/serverSystem` 直接继承引擎 System 类，逻辑与引擎耦合，无法脱离 MC 单测。本 change 只做纯逻辑层与调试工具（见 proposal.md），为后续 serverSystem 整合提供可单测的内核。规格见 `specs/gomoku-core/spec.md` 与 `specs/gomoku-debug/spec.md`。

## Goals / Non-Goals

**Goals:**
- 单文件核心类 `GomokuBoard`，零 MC import，py2/3 双兼容（不用 f-string、类型注解、dataclass；`class Foo(object)` 显式继承）
- 行为完全由 spec 的状态机约束：`PLAYING -> WON(player)/DRAW`，终局锁定
- 结果对象携带错误原因与成五连线坐标，方便 MC 层直接消费
- 本地 Python 3 即可跑单测与终端调试

**Non-Goals:**
- 不做 serverSystem、modMain 注册、方块坐标映射（后续 change）
- 不做禁手（正规连珠规则）、计时、AI 对手
- 不做多局积分/房间管理——一局就是一个 `GomokuBoard` 实例

## Decisions

### D1: 单文件纯逻辑类，放在 modCommon 下
位置 `script_Gomoku/modCommon/gomokuCore/board.py`。modCommon 是模板中放共享逻辑的既定位置；MC 端后续可 `from ...modCommon.gomokuCore.board import GomokuBoard` 相对导入，本地端通过 `sys.path` 加 `script_Gomoku` 包导入。不做包内 `__init__` 重导出以外的任何 MC 假设。

### D2: 棋盘用一维 list[int] 存，dict 存稀疏棋子更省内存但一维数组更快更简单
`self._grid = [0] * (width * height)`，0=空、1=先手（黑）、2=后手（白）。备选是 `dict[(x,y) -> player]` 稀疏存储——大棋盘下省内存，但越界判断、序列化、渲染都要额外处理，收益对这个规模（≤99x99）不重要。选一维数组。

### D3: 增量胜负判定，只查新子 4 条线
落子成功后从 `(x, y)` 出发沿 4 个方向双向延伸计数，≥5 即胜。收集所有成五线（spec 要求双向同时成五时全部返回）。不实现全盘重判——终局锁定保证删子永不发生在已判胜负之后，对局中删子不影响任何已存在的胜负状态（因为还没产生）。

### D4: 结果对象用轻量类而非异常
`PlaceResult` / `RemoveResult` / `UndoResult` 各为一个小类（`ok`, `reason`, 及 `winning_player` / `winning_lines` 等字段）。备选是抛异常——在游戏逻辑里"落子非法"是常态而非异常（玩家手滑很正常），用返回值让调用方免 try/except。不引入 dataclass（py2 兼容）。

### D5: 落子历史只记落子，不记删子
`self._history` 为 `[(x, y, player), ...]`，悔棋弹栈。删子直接改 grid 不入历史（spec 已定：删子不算一手、悔棋不恢复删子）。悔棋直接从历史重放对应格子置空并回退执子方，O(1)。

### D6: 序列化用简单类型 dict
`serialize() -> dict` 含 `width/height/grid(压缩为棋子坐标列表即可反推)/current_player/state/winner/history`。用坐标列表而非整个 grid 数组，存档体积小。`GomokuBoard.deserialize(data)` 类方法重建。

### D7: 调试 REPL 与单测放在仓库根 `gomoku_dev/`，不进 behavior_packs
MC Studio 会把 behavior_packs 里的 py 当 mod 脚本扫描，调试/测试文件混进去有被加载的风险。`gomoku_dev/` 通过 `sys.path.insert` 指向 `script_Gomoku` 的父目录来 import。REPL 用 `input()` 循环，py2 下 `raw_input` / py3 下 `input` 做兼容 shim。单测用标准库 `unittest`（py2/3 均内置），不引入 pytest 依赖。

### D8: 错误原因用模块级常量字符串
`ERR_OUT_OF_BOUNDS = "out_of_bounds"` 等，成功/失败与原因码分离。MC 层可据常量映射中文提示；终端层直接打印。

## Risks / Trade-offs

- [py2 兼容写法在 py3 下偶有坑（`input`/整数除法/`dict.iteritems`）] → 单测同时在本机 py3 全量跑；代码里只用两边语义一致的子集，REPL 单独做 input shim
- [一维数组 O(w*h) 内存，99x99 上限 ≈ 9801 int] → 可忽略，不缓解
- [删子不入历史导致"落子A、删A、悔棋"会把 A 的格子再置空一次] → 置空操作幂等，无实际影响；单测覆盖该场景
- [后续 serverSystem 可能需要"按方块坐标查询所在棋盘/格子"的映射] → 属于 MC 层职责，核心类只认抽象 (x, y)，接口边界已在 design 固化，扩展不破坏

## Migration Plan

纯新增，无存量迁移。回滚 = 删除 `script_Gomoku/` 与 `gomoku_dev/` 两个目录。
