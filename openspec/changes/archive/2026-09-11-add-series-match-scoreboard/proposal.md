# 系列赛(五局三胜)与场地记分牌

## Why

当前地图的结算粒度是"单局":EndLogic 每次结算(超时/仅剩一队/五子连珠)后播报胜者并自动重开下一局,局与局之间没有任何跨局数据。对 2+ 队伍的对战玩法来说缺少"系列赛"概念——玩家无法围绕"先赢 N 局拿下整场"来打,场地里也看不到总比分。这次在现有单局结算链路之上垫一层可配置的系列赛(如五局三胜),并在场地里用一块世界内记分牌实时展示各队胜场数。

## What Changes

- **系列赛状态**:EndLogicMod 新增按真实队名记胜场的系列赛数据(`seriesWinDict`)与可配置的夺冠所需胜场数(`matchWinLimit`,默认 3)。
- **结算收敛**:三个结算出口(超时结算、仅剩一队、Gomoku 的 `ExternalSettleGame`)统一收敛到同一段收尾逻辑:记分 → 判断是否产生总冠军 → 广播比分。
- **平局**:平局(超时并列、棋盘下满)双方均不记胜场,直接进入下一局。
- **快速开局**:系列赛未结束时,局与局之间不再回大厅重新确认、重新 `ReQueueAllocation` 分队——**队伍跨局保持不变**;`StartLogicEvent` 照常广播(下游 Gomoku 重置棋盘、Skill/LimitedRespawn 重新武装不受影响)。总冠军产生后才彻底回大厅(state 0),此后重新分队、重新确认。
- **总冠军流程**:某队达到 `matchWinLimit` 后播报总冠军,系列赛比分清零,记分牌归零,回大厅重开整场。
- **记分牌**:客户端用官方 TextBoard API(`mod.client.component.textBoardCompClient`,在审核白名单内)在世界固定坐标创建大字记分牌:透明底、白色文字、不跟随镜头、支持换行;服务端广播比分事件驱动 `SetText` 更新,玩家中途进入时补推当前比分。
- **结算调用方适配**:GomokuMod 调用 `ExternalSettleGame` 时改传真实队名(新增可选参数 `victoryTeamName`),现在传的"黑方/白方"显示别名不能作为记分 key。
- **BREAKING(仅 mod 间接口,无外部影响)**:`EndLogicServerSystem.ExternalSettleGame` 增加可选参数,现有调用兼容。

## Capabilities

### New Capabilities
- `series-match`: 系列赛层——跨局胜场计分、可配置夺冠胜场数、平局不记分、局间快速开局(队伍保持)、总冠军判定与整场重置。
- `match-scoreboard`: 场地记分牌——客户端 TextBoard 展示系列赛比分,服务端比分变化驱动更新,中途加入的玩家能看到当前比分。

### Modified Capabilities
<!-- 现有 gomoku-core / gomoku-debug 均为与引擎解耦的核心逻辑 spec,其需求不受本变更影响。 -->

## Impact

- `behavior_packs/.../script_EndLogic/`:`config.py`(新增 `matchWinLimit`、记分牌坐标/文案参数)、`endLogicServerSystem.py`(系列赛状态、结算收敛、快速开局触发、总冠军流程、比分广播)、`endLogicClientSystem.py`(TextBoard 创建/更新/重连重建)。
- `behavior_packs/.../script_StartLogic/`:`startLogicServerSystem.py` 新增"系列赛续局"入口——跳过确认与重新分队、直接进入 state 3 并广播 `StartLogicEvent`。
- `behavior_packs/.../script_Gomoku/`:`gomokuServerSystem.py` 的 `OnGameEnd` 结算调用补传真实队名。
- 不改动:TeamMod(队伍逻辑本身不变)、SkillMod、ResourcePointMod、WorldMod、LimitedRespawnMod、资源包 JSON、`gomokuCore`(核心逻辑与其 32 项单测零改动)。
- 已知坑位(实现时注意):`config.py` 读取 `restartGameTime` 而 editorConfig 写入 `reStartGameTime`,两者拼写不一致导致编辑器值不生效——新增配置项沿用 config.py 手写默认即可,不走 editorConfig。
- 无法在 shell 中验证,所有行为须在 MCStudio 运行地图后观察 `edit.log`;TextBoard 为纯客户端对象,需覆盖断线重连/重进场景。
