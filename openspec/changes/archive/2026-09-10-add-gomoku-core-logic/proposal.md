## Why

这个 MC 模组要加入"在游戏里下五子棋"的玩法。玩法的第一块基石是一套与 MC 引擎完全解耦的五子棋判定逻辑：它能独立单测、能在终端里直接对弈调试，之后才被 serverSystem 包装接入方块事件。先做纯逻辑层可以避免把规则判定和引擎事件耦合在一起返工。

## What Changes

- 新增纯逻辑类 `GomokuBoard`（零 MC 依赖，py2/3 双兼容）：棋盘尺寸设置、落子、删子、回合管理、悔棋、胜负与平局判定、成五连线坐标返回、序列化/反序列化。
- 新增独立调试 REPL（终端 ASCII 棋盘 + 指令交互），以及单测脚本，二者均在本地 Python 直接运行，不依赖 MC。
- 本 change **不包含** serverSystem 整合与方块映射（留作后续 change）。

## Capabilities

### New Capabilities
- `gomoku-core`: 纯五子棋核心逻辑——棋盘管理（尺寸/落子/删子/悔棋/重置）、回合管理、休闲规则胜负判定（5 连及以上成五）、终局状态机（胜负已分后锁定单局）、序列化。
- `gomoku-debug`: 终端调试工具——ASCII 棋盘渲染与指令交互，用于人工验证核心逻辑。

### Modified Capabilities
（无——本仓库尚无任何既有 spec）

## Impact

- 新增目录 `behavior_packs/behavior_pack_864FhZqu_7ec35a94/script_Gomoku/`（遵循模板的 `script_*` 结构，本 change 只放 modCommon 下的核心逻辑，modMain/serverSystem 留到后续 change）。
- 新增仓库根下 `gomoku_dev/` 目录：单测与调试 REPL，通过 `sys.path` 引用核心类，不被 MC 当作 mod 脚本加载。
- 无破坏性变更；不触碰既有 script_* 模块。
