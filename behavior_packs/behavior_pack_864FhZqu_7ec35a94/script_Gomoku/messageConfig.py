# -*- coding: utf-8 -*-
# =====================================================================
# GomokuMod 玩家可见文案统一管理 —— 全服播报(Announce族)/单人私聊(SendMessageToPlayer)
# 的全部模板都在这里。gomokuServerSystem 只引用语义key（见Msg/MsgPlayer/
# MsgThrottled/GetText），改文案只动本文件。
# 本文件是纯文案表：只允许str字面量/dict/list与两个兜底名常量，禁止import任何
# ModSDK模块（gomoku_dev的校验脚本要脱离游戏直接import本文件）。
# 模板占位符一律用命名占位符（{count}而非{}），调用侧传同名kwargs。
# 注意：py2 str字面量（utf-8字节串），不用u前缀——与Announce/SendMessageToPlayer
# 通道一致；调试命令的7条TellToPlayer（unicode通道）不收在本表。
# =====================================================================

MESSAGES = {
	# ---- 对局流程（game_） ----
	'game_start': "§e新对局开始，已清空背包",
	'game_over': "§c对局已结束，请等待下一轮",
	'game_no_endlogic': "§e未找到EndLogic组件，仅做本地播报",

	# ---- 玩法模式（mode_；每局开局播报本局模式，见SwitchGameModeForRound。
	# 模式自报RoundAnnounceKey选具体条目，没报的用mode_round通用模板兜底） ----
	'mode_round': "§e本局玩法模式：§6{name}§e！",
	'mode_round_classic': "§e本局模式：§6经典模式§e——原生地形自由跑图，道具照常在环形区域刷新",
	'mode_round_trap': "§e本局模式：§6陷阱模式§e——地面看着都一样，只有通往道具点的路是安全的，踩错一格脚下就是岩浆！看清脚下再跑",

	# ---- 落子（place_；校验失败类均为节流播报 kind='placeHint'） ----
	'place_occupied': "§c此处已有棋子",
	'place_need_team': "§c落子需要先加入队伍",
	'place_hold_piece': "§c请手持棋子右键棋盘落子",
	'place_no_gap': "§c2x2范围内没有可落子的空格",
	'place_burst_placed': "§e方阵棋子铺下了{count}枚棋子",
	'place_board_full_extend': "§e主棋盘已经下满了，扩展格里还能继续落子！",

	# ---- 墨水（ink_；校验失败类均为节流播报 kind='inkHint'） ----
	'ink_need_team': "§c使用墨水需要先加入队伍",
	'ink_own_piece': "§c这是己方棋子，不需要墨水",
	'ink_converted': "§5一瓶墨水泼下，§6{side}§5的一枚棋子被转化了！",

	# ---- 爆炸雷管（bomb_） ----
	'bomb_already_lit': "§c这里已经有一根点燃的雷管了",  # 节流kind='bombHint'
	'bomb_fuse_lit': "§c引信已点燃，快跑！",
	'bomb_exploded': "§c轰！爆炸雷管炸掉了{count}枚棋子",
	'bomb_exploded_empty': "§e轰！爆炸雷管炸了个空（范围内没有棋子）",
	'bomb_defused': "§e一枚雷管被及时拆除了",

	# ---- 吞噬黑洞（blackhole_） ----
	'blackhole_opened': "§5吞噬黑洞展开！棋盘上的§e{count}§5枚棋子被吞得一干二净（不分敌我）",

	# ---- 破盘镐（board_pick_） ----
	'board_pick_wrong_target': "§c破盘镐只能右键棋盘基座来拆格",  # 节流kind='boardPick'
	'board_pick_no_game': "§c对局未在进行中，破盘镐没有目标（新一局基座会重铺）",  # 节流kind='boardPick'（与wrong_target同桶）
	'board_pick_removed': "§c破盘镐拆掉了一格棋盘基座，该格本局无法落子（新一局自动修复）",

	# ---- 换位符（swap_） ----
	'swap_fail_no_pos': "§c换位失败：无法读取你的位置",
	'swap_fail_no_target': "§c换位失败：场上没有可交换的敌方玩家",
	'swap_fail_tp': "§c换位失败：对方暂时无法被传送",
	'swap_done': "§d移形换位：{player} 与 {target} 互换了位置！",

	# ---- 转移符（transfer_） ----
	'transfer_shield_refreshed': "§d转移符护盾已刷新：下次受到的伤害将转给敌人",
	'transfer_shield_active': "§d转移符护盾已激活：下次受到的伤害将转给敌人",
	'transfer_triggered': "§d转移符生效！{victim}§d受到的§e{damage}点§d伤害转给了{target}§d！",

	# ---- 加速药水（speed_potion_，均为单玩家私信） ----
	'speed_potion_fail_retry': "§c加速药水未能生效，请重试",
	'speed_potion_fail': "§c加速药水未能生效",
	'speed_potion_refreshed': "§b加速效果已刷新：再持续{seconds}秒",
	'speed_potion_active': "§b加速药水生效：移动速度提升{percent}%，持续{seconds}秒",
	'speed_potion_expired': "§b加速药水效果已结束",

	# ---- 便携棋盘（cell_铺格 / board_item_耐久） ----
	'cell_fail_height': "§c摆放失败：只能在与初始棋盘齐平或低一层的地面上摆放",
	'cell_need_team': "§c摆放棋盘格需要先加入队伍",
	'cell_fail_on_board': "§c摆放失败：这里已经在主棋盘上了",
	'cell_fail_duplicate': "§c摆放失败：这里已经铺过一格棋盘了",
	'cell_fail_too_far': "§c摆放失败：离初始棋盘太远了（{radius}格以内才行）",
	'cell_fail_occupied': "§c摆放失败：这个位置被占着（矿/棋子/道具方块），先清理再铺",
	'cell_fail_setblock': "§c棋盘格铺设失败，请换个位置再试",
	'cell_placed': "§e一格新的棋盘铺好了！可以在上面落子",
	'board_item_durability': "§e便携棋盘剩余耐久: {count}次",  # 单玩家私信
	'board_item_used_up': "§e便携棋盘用完了，随一阵青烟散去",

	# ---- 采集与棋石（含节流类，kind沿用旧节流桶字符串） ----
	'piece_cap_pickup': "§c棋子携带已达上限{count}个，先落子或用掉再拾取",  # kind='pieceCap'
	'piece_cap_mine': "§c棋子携带已达上限{count}个，先落子或用掉再采集",   # kind='pieceCap'（与拾取共享节流桶）
	'base_break_protected': "§c棋盘基座无法被破坏",            # kind='baseBreak'
	'stone_tool_wrong_tier': "§c这枚棋石须用{pickaxe}（或更高级的镐）挖掘",   # kind='stoneTool'
	'mine_wrong_pickaxe': "§c矿挖碎了，但没有{pickaxe}（或更高级的镐），棋子没有掉落",
	'mine_give_fail': "§c棋子发放失败，矿稍后还原，请联系开发者查日志",
	'mine_stone_removed': "§e棋盘上一枚棋子被挖掉了",
	'trap_exploded_hit': "§c轰！陷阱棋石爆炸了！§f炸倒了{count}名玩家",
	'trap_exploded_empty': "§c轰！陷阱棋石爆炸了！§f没有玩家在范围内",
	'random_block_no_pickaxe': "§c问号方块挖碎了，但需要手持镐采集才能开出道具",
	'random_block_give_fail': "§c道具发放失败，问号方块稍后还原，请联系开发者查日志",
	'random_block_opened': "§6{player}§e从问号方块里开出了§6{item}§e！",

	# ---- 武器（weapon_） ----
	'weapon_dizzy_hit': "§d眩晕锤碎裂！{victim}§d被砸得眼冒金星，道具散落一地！",
	'weapon_chaos_hit': "§d混乱药水泼洒！{victim}§d中了混乱，前后左右全反了！",
	'weapon_execution': "§c{weapon}出鞘！一击必杀！",

	# ---- 时间停止（timestop_） ----
	'timestop_frozen': "§c时间停止中，§e{seconds}§c秒后恢复行动",  # 单玩家私信，自带节流
	'timestop_you': "§d你被时间停止了：§e{seconds}§d秒内无法行动（可以转视角）",  # 单玩家私信
	'timestop_announce': "§d§l时间停止！§r§d{player}冻结了全场{seconds}秒",
	'timestop_lonely': "§e场上没有其他玩家，时间停止了寂寞（道具已消耗）",  # 单玩家私信

	# ---- 阵亡与复活（death_） ----
	'death_announce': "§c{player}阵亡！§e{seconds}§c秒后在棋盘附近复活",
	'death_countdown': "§c阵亡冷却 §e{seconds}§c秒后恢复行动",  # 单玩家私信（倒计时）
	'death_revived': "§a已复活，行动恢复",                      # 单玩家私信
	'death_hold': "§c阵亡冷却中，§e{seconds}§c秒后恢复行动",     # 单玩家私信，自带节流

	# ---- 胜负与平局（win_） ----
	'win_draw_side': "平局",  # sideText，传给EndLogic.ExternalSettleGame
	'win_draw_announce': "§e棋盘已满，双方平局！",
	'win_victory_announce': "§6{side}§f在棋盘上连成五子，赢得对局！",
	'win_result_victory': "§6{side}§f获得五子棋对局胜利",  # 发客户端GomokuGameResultEvent
	'win_result_end': "§6{side}§f结束五子棋对局",           # 同上（平局路径）
}

# 兜底名（GetPlayerName失败时的替身；GetEntityName的兜底是实体id，不走这里）
FALLBACK_PLAYER_NAME = "玩家"
FALLBACK_ENEMY_NAME = "敌方玩家"

# ---------------------- 玩法说明书（进服即发放，右键打开） ----------------------
# 教程文案：每个元素一页（\n换行，§颜色代码可用）。只改文案不用动UI与逻辑
# （客户端manualUI按页渲染，见gomokuClientSystem的ManualOpenEvent）。
ManualTextList = [
	"§l§e■ 玩法目标\n"
	"§r§f黑白双方分别向棋盘上落子，横、竖、斜任意方向\n"
	"§f先连成 §e五子 §f的队伍立即获胜！\n\n"
	"§f棋盘每局随机形状，棋子只能落在棋盘上\n\n"
	"§f一局限时8分钟，到时间未分胜负则双方平局。\n"
    "总游戏为 §e5局3胜制\n",
	"§l§e■ 采集\n"
	"§r§f棋子是采集来的，不在背包里凭空产生：\n\n"
	"§f普通棋子矿（近环）——须持 §b石镐 §f或更高级镐挖\n"
	"§f硬化棋子矿（中环）——须持 §b铁镐 §f挖，落子更难被拆\n"
	"§f金矿（高级道具环）——徒手速挖，挖碎得普通棋子\n"
	"§f使用镐采集§d问号方块 可以获得随机道具\n"
	"§f（有极小几率开出§5吞噬黑洞§f或§5时间停止§f）\n"
	"§c注意：棋子最多同时携带2个，背包中持有2子时无法获得更多棋子哦",
	"§l§e■ 落子与拆子\n"
	"§r§f手持棋子右键棋盘基座即可落子（颜色=你的队伍）。\n\n"
	"§f特殊棋子：\n"
	"§f  §d方阵棋子 §f——一次铺下2x2四枚己方棋子\n"
	"§f  §d陷阱棋子 §f——外观与普通棋子完全相同，\n"
	"§f  被对手挖毁的瞬间炸死周围的人\n\n"
	"§f盘上的棋子可以拆除，普通棋子须使用石镐、硬化须使用铁镐\n"
	"§f（高级镐通用，都能挖低级棋子），\n"
	"§f但是在盘上挖子比采集棋子慢得多而且不会获得棋子",
	"§l§e■ 道具：中环\n"
	"§r§d转化墨水 §f——右键敌方棋子，变成己方颜色\n"
	"§d爆炸雷管 §f——右键棋盘摆出，3秒后引爆，\n"
	"§f  炸掉3x3范围内的全部棋子（不管敌我）；\n"
	"§f  引信期间可被挖掉拆除\n"
	"§d破盘镐 §f——右键拆掉棋盘基座一格\n"
	"§d便携棋盘 §f——右键铺一格新棋盘格（耐久2次），\n"
	"§f  新格与主盘互相连线，也能补进主盘缺格\n"
	"§d加速药水 §f——右键喝下，10秒内移速+25%；\n"
	"§f  连续使用只刷新持续时间\n"
	"§d混乱药水 §f——砸中敌方玩家：对方10秒内前后左右反向，\n"
	"§f  且天旋地转；砸中即碎\n",
	"§l§e■ 道具：远环\n"
	"§r§d处决剑 §f——攻击玩家一击必杀（用一次即碎），\n"
	"§f  死者会掉落全部携带物品\n"
	"§d换位符 §f——右键与最近的敌方玩家互换位置，无距离限制\n"
	"§d转移符 §f——右键激活护盾：下一次受到的伤害不落己身，全额转给最近的敌人\n"
	"§d眩晕锤 §f——命中目标后，使目标眩晕1.5秒，且背包道具全部掉在脚下\n"
	"§f越好的道具刷新在棋盘越远处\n"
	"§l§5■ 道具：问号方块限定\n"
	"§r§5吞噬黑洞 §f——右键释放，吞噬棋盘上的§e全部棋子§f（不分敌我），\n"
	"§f  棋盘基座无损，清空后仍可继续落子；用一次即碎\n"
	"§r§5时间停止 §f——右键使用，除你以外的§e全部玩家§f（含队友）\n"
	"§f  冻结5秒：不能动、不能挖、不能落子用道具，\n"
	"§f  只能干瞪眼转视角；用一次即碎\n"
	"§f  两者都只能从§d问号方块§f中极小几率开出\n",
	"§l§e■ 阵亡规则\n"
	"§r§f死亡后会自动在棋盘附近复活。\n\n"
	"§7—— 祝武运昌隆 ——",
]
