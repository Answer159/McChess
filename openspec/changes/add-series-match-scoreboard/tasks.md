# 任务:系列赛与记分牌

验证说明:本项目无 shell 测试,所有"验证"指在 MCStudio 运行地图并观察游戏内行为与 `D:\MCStudioDownload\work\editor\edit.log`;gomokuCore 相关单测(`gomoku_dev/test_board.py`)不应受影响,收尾跑一次确认仍 32 项通过。

## 1. 前置验证

- [ ] 1.1 在 MCStudio 模型/脚本里最小验证 TextBoard 多行显示:`CreateTextBoardInWorld("红队 1 : 0 蓝队\n五局三胜", ...)` 能否换行、观察文字大小,记录结论到 edit.log;不支持换行则记下,后续任务按"比分/赛制两块板"实现
- [x] 1.2 跑 `python gomoku_dev/test_board.py`(任意 Python),确认基线 32 项单测通过,作为不受本变更影响的锚点

## 2. 服务端系列赛状态(EndLogicMod)

- [x] 2.1 `script_EndLogic/config.py` 新增 `matchWinLimit = 3`、`scoreboardPos`、`scoreboardScale`、记分牌文案格式常量;确认这些 key 不与 editorConfig.dataDict 键冲突(编辑器不提供,手写默认即生效)
- [x] 2.2 `endLogicServerSystem.py` 新增 `seriesWinDict` 初始状态、队名→显示名辅助,以及 `GetSeriesScoreSummary()`(供补推);验证:logger.info 打印初始比分(代码完成,进游戏观察 edit.log 待做)
- [x] 2.3 实现收尾收敛方法 `SettleAndRecord(victoryTeamName, victoryText, victoryPlayerIdList)`:记分(队名 None 为平局不记)、广播 `UpdateSeriesScoreEvent`、达标判断与清零、总冠军/续局标记;验证:单元逻辑用 print 自检后进游戏看日志(代码完成,进游戏观察待做)
- [x] 2.4 三个出口(`VictoryJudgeWhenPlayerDie`、`DelayStartClock`、`ExternalSettleGame`)改为调用收敛方法,替换重复尾段;`ExternalSettleGame` 增加 `victoryTeamName` 可选参数;验证:进游戏分别触发超时与连珠结算,edit.log 显示两次比分广播、无报错(代码完成,进游戏观察待做)
- [x] 2.5 `OnPlayerAdd` 时 `NotifyToClient` 补推当前比分;验证:中途进图后客户端收到(见任务 4.3 的日志)(代码完成,进游戏观察待做)

## 3. 快速续局与整场重置(StartLogic + TeamMod + Gomoku)

- [x] 3.1 TeamMod `teamServerSystem` 新增 `ResetQueueScore()`(只清 `queueScoreList` 并刷 scoreboard),StartLogic/Gomoku 不动它;验证:直呼后 UI 计分归零(代码完成,进游戏观察待做)
- [x] 3.2 `startLogicServerSystem.py` 新增 `ReStartGameInSeries()`:以当前在线全集重建 ensure/alive 字典、不 `ReQueueAllocation`、传队伍出生点、`state=3`、广播 `StartLogicEvent`、通知 EndLogic 重置与开钟;验证:连赢两局,第二局队伍与第一局相同、棋盘已重置、无需大厅确认(代码完成,进游戏观察待做)
- [x] 3.3 `endLogicServerSystem.ReStartGame` 按标记分流:未产生总冠军走 `ReStartGameInSeries`,产生总冠军走现有 `ReStartGame()`(state 0,后续重新分队);验证:夺冠后下一场重新分队且比分 0:0(代码完成,进游戏观察待做)
- [x] 3.4 `script_Gomoku/gomokuServerSystem.py` 的 `OnGameEnd`:调用 `ExternalSettleGame` 时补传真实队名(经 `GetPlayerTeamName`),平局传 None;验证:黑方连珠后 edit.log 记到该队名胜场+1(代码完成,进游戏观察待做;实现为经 TeamSideDict 反查队名,winnerPlayer 是棋子值非玩家id)
- [ ] 3.5 边界验证:局间退出一名玩家后下一局正常开局;平局(棋盘下满)后双方比分不变直接续局

## 4. 客户端记分牌(TextBoard)

- [x] 4.1 `endLogicClientSystem.py` 实现记分牌生命周期:`UiInitFinished` 后协程延迟创建 TextBoard(透明底、白字、faceCamera=False、`SetBoardScale`/`SetBoardPos` 用 config),保存 boardId;验证:进图后场地坐标出现初始比分(代码完成,进游戏观察待做)
- [x] 4.2 监听 `UpdateSeriesScoreEvent` → `SetText(boardId, 格式化比分)`;验证:一局结束后所有客户端记分牌同步更新(多开两个客户端观察)(代码完成,进游戏观察待做)
- [x] 4.3 接收服务端补推:中途进入/重进地图的玩家,记分牌重建并显示当前比分;验证:比分 1:0 时重进,显示 1:0 而非 0:0(代码完成,进游戏观察待做;文案缓存于 seriesScoreText,面板创建时带上)
- [x] 4.4 总冠军产生后记分牌归零(依赖服务端清零后的主动广播);验证:夺冠后新一场显示 0:0(代码完成,进游戏观察待做)

## 5. 收尾验收

- [ ] 5.1 三条结算路径(超时/仅剩一队/连珠)+ 平局的回归:各触发一次,edit.log 无异常、比分与重启路径符合 specs/series-match
- [ ] 5.2 删除场景中的 TextBoard 预设(编辑器操作,坐标已抄入 config),确认记分牌不受影响
- [x] 5.3 复跑 `gomoku_dev/test_board.py` 确认 32 项通过;git diff 复查只涉及 script_EndLogic / script_StartLogic / script_Team / script_Gomoku 四个文件夹(已验证:32 项 OK,diff 恰为四个文件夹 6 个文件)
