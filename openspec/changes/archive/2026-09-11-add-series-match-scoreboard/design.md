# 设计:系列赛与记分牌

## Context

现有结算链路(见 proposal):EndLogic 的三个结算出口各自重复"播报 → 清背包 → 重启"收尾;重启统一走 `EndLogic.ReStartGame`(协程等 `restartGameTime` 秒)→ `StartLogic.ReStartGame()` → state 0 回大厅 → 重新确认 → `CheckState` 里 state 2→3 时 `ReQueueAllocation` 重新分队 → `StartGame()` 广播 `StartLogicEvent` 并传送。TeamMod 的 `queueScoreList` 是每局内击杀分,每局随 `ReQueueAllocation` 清零。约束:mods 之间禁止 import,只允许 `GetSystem` 直呼(带 None 防御)或事件;`editorConfig.py` 由 MCStudio 生成不可手改,手写配置只能落在 `config.py` 默认值层;一切行为只能在 MCStudio 运行地图后经 `edit.log` 验证。

## Goals / Non-Goals

**Goals:**
- 系列赛状态与记分、局间快速开局(队伍保持)、总冠军流程,全部落在现有 mod 结构内
- 记分牌用官方客户端 TextBoard API,服务端只广播数据
- 三个结算出口收敛为一条记分/重启路径,消掉现有三段重复收尾

**Non-Goals:**
- 不做个人模式的系列赛记分(仅队伍模式)
- 不持久化系列赛比分到存档——服务器/地图重启后系列赛从 0:0 重新开始(记分牌是运行时对象,天然如此)
- 不做 TextBoard 与实体的绑定(静态坐标足够;绑定留作后续增强)
- 不动 `gomokuCore` 与其单测

## Decisions

### 1. 系列赛状态放 EndLogicMod

`endLogicServerSystem` 新增 `seriesWinDict`(key=TeamMod 队名)与 `matchWinLimit`。
**理由**:EndLogic 已是结算协调者,三出口都在它手里;TeamMod 的分数是局内语义且每局清零,新 mod 则要反向拦截 EndLogic 的重启链,徒增耦合。**替代方案否决**:新 mod(需拦截重启,违反简单性)、放进 TeamMod(队伍数据语义混淆)。

### 2. 结算出口收敛到一个收尾方法

`VictoryJudgeWhenPlayerDie` / `DelayStartClock` / `ExternalSettleGame` 现各自复制"清背包+重启"尾段,统一改为调用 `SettleAndRecord(victoryTeamName, victoryText, victoryPlayerIdList, isDraw)`:
1. `endGameFlag=True`、`CancelClock()`(现各出口已有)
2. 平局(`victoryTeamName=None`)不记分;否则 `seriesWinDict[teamName] += 1`
3. 广播 `UpdateSeriesScoreEvent`(含各队比分与 `matchWinLimit`)
4. 达标 → 总冠军播报文案、`seriesWinDict` 清零、标记整场重置;未达标 → 标记快速续局
5. `NotifyVictory` + 清背包
6. 协程等 `restartGameTime` 秒后按 4 的标记走快速续局或整场重置

### 3. 记分 key 用真实队名,`ExternalSettleGame` 加可选参数

`ExternalSettleGame(self, victorName, victoryText=None, victoryPlayerIdList=None, victoryTeamName=None)`——新增第 4 参数,现调用方兼容。GomokuMod 的 `OnGameEnd` 已通过 `GetPlayerSide` 走 TeamMod 查队名,改为同时传真实队名;超时/仅剩一队两条路径在结算处本就有 `victoryQueueNameList` / `GetPlayerTeamName` 可用。**理由**:现在传给 `ExternalSettleGame` 的 victorName 是"黑方/白方"显示别名,不能当 key。

### 4. 快速开局:StartLogic 增加系列赛续局入口

`StartLogicServerSystem` 新增 `ReStartGameInSeries()`,由 EndLogic 在局间(未产生总冠军)调用,替代原 `ReStartGame()`:
- `playerEnsureDict` 重建为当前在线玩家全集(处理局间离开/新进的玩家)
- 不调用 `ReQueueAllocation`(队伍保持),但调用 TeamMod 的分数清零接口(见决策 5)
- 玩家传送到各自队伍出生点(复用 `StartGame` 的 `posOption==1` 传送段)
- `state=3`,广播 `StartLogicEvent`,并通知 EndLogic `ReSetDynamicData()+StartClock()`(镜像 `StartGame` 的收尾)
**理由**:`CheckState` 的状态机与大厅确认语义只服务"新一场",续局绕过它最直接;`StartLogicEvent` 是下游(Gomoku `ResetBoard`、Skill/LimitedRespawn)的唯一开局信号,保持它即保住下游兼容。

### 5. TeamMod 加只清分的公开方法

快速续局不复用 `ReQueueAllocation`(它会重新分掉队伍),TeamMod 新增 `ResetQueueScore()` 只清 `queueScoreList` 并刷新 scoreboard UI。StartLogic 直呼(带 None 防御),不违反 mod 隔离。

### 6. 记分牌:客户端 TextBoard,世界坐标,不绑实体

EndLogic clientSystem 在 `UiInitFinished` 后(协程延迟几帧躲 UI 未就绪竞态,仓库既有套路)用 `clientApi.GetEngineCompFactory().CreateTextBoard(levelId)`:
`CreateTextBoardInWorld(初始文案, 白色, 透明底(0,0,0,0), faceCamera=False)` + `SetBoardScale` + `SetBoardPos(config.scoreboardPos)`。
更新:监听 `UpdateSeriesScoreEvent` → `SetText(boardId, 格式化文案)`(文案含各队名+胜场,如 `"红队 1 : 0 蓝队\n五局三胜"`)。服务端在 `OnPlayerAdd` 时 `NotifyToClient` 补推当前比分(覆盖中途进入与重进重连)。
**理由**:TextBoard 是唯一受支持的世界内大字方案(官方文档+审核白名单);原版告示牌 `SetSignBlockText` 虽然服务端直写更简单,但木牌尺寸太小,用户明确要大屏。**替代方案否决**:告示牌(尺寸)、编辑器预设(文字不可运行时改,已验证无脚本接口)。

### 7. 配置全部走 config.py 手写默认

`script_EndLogic/config.py` 新增:`matchWinLimit=3`、`scoreboardPos`、`scoreboardScale`、记分牌文案格式。**理由**:editorConfig 由 MCStudio 生成,新 key 只有在编辑器组件模板补字段后才会写入;且现有 `restartGameTime`(读)/`reStartGameTime`(写)拼写不一致的坑说明手写层是可靠层。

## Risks / Trade-offs

- [快速续局绕过 CheckState,自建玩家字典可能与 StartLogic 内部状态不一致] → `ReStartGameInSeries` 只用 `self.players`(StartLogic 自己维护的在线全集)重建 `playerEnsureDict`/`playerAliveDict`,不引入外部状态;实现后第一轮测试重点覆盖"局间退出/加入"。
- [TextBoard `\n` 换行、字数上限未验证(文档未写)] → 实现前先在游戏里用一个最小脚本验证多行显示,不行就拆成两块板(比分/赛制各一)。
- [记分牌是客户端对象,重进/换维度后丢失或过期] → 服务端补推当前比分 + `UiInitFinished`/`OnLoadSuccess` 重建,与现有 UI 生命周期事件同源。
- [三出口收敛属于对结算核心的手术,改坏会影响现有单局结算] → 收敛方法保持三个出口原判定逻辑不动,只动尾段;MCStudio 运行验证超时/仅剩一队/连珠三条路径。
- [整场重启时 seriesWinDict 清零与记分牌归零的时序不同步] → 清零后主动广播一次 `UpdateSeriesScoreEvent`,不依赖客户端自行重置。
- [无法 shell 验证] → 所有验收经 MCStudio 运行 + `edit.log`,任务里逐条列出观察点。

## Open Questions

- 记分牌最终视觉(坐标微调、缩放、单块/两块、要不要每队一块彩色板)在游戏内调,不影响结构。
- 场地里已摆的 TextBoard 预设(`db/presets.json` 里那个"HI")是否删除——建议删,坐标抄进 config 后它已无用。
- 总冠军后的整场重置是否要一个比 `restartGameTime` 更长的庆祝间隔(如 10 秒)——实现时一行配置的事,默认先用现值。
