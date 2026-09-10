# -*- coding: utf-8 -*-
"""GomokuBoard 单测（unittest，py2/3 兼容，覆盖 specs/gomoku-core 每个 scenario）。

运行: python gomoku_dev/test_board.py
"""

import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_PACK_ROOT = os.path.join(_HERE, "..", "behavior_packs", "behavior_pack_864FhZqu_7ec35a94")
sys.path.insert(0, os.path.abspath(_PACK_ROOT))

from script_Gomoku.modCommon.gomokuCore.board import (  # noqa: E402
    EMPTY, BLACK, WHITE,
    STATE_PLAYING, STATE_WON, STATE_DRAW,
    ERR_INVALID_SIZE, ERR_OUT_OF_BOUNDS, ERR_OCCUPIED, ERR_EMPTY,
    ERR_GAME_OVER, ERR_NOT_YOUR_TURN, ERR_NO_HISTORY,
    GomokuBoard,
)


class TestInitAndSize(unittest.TestCase):
    """棋盘初始化与尺寸设置。"""

    def test_default_board(self):
        b = GomokuBoard()
        self.assertEqual((b.width, b.height), (15, 15))
        self.assertEqual(b.state, STATE_PLAYING)
        self.assertEqual(b.current_player, BLACK)
        self.assertTrue(b.is_full() is False)
        for y in range(15):
            for x in range(15):
                self.assertEqual(b.get(x, y), EMPTY)

    def test_non_square_board(self):
        b = GomokuBoard(9, 15)
        self.assertEqual((b.width, b.height), (9, 15))
        for y in range(15):
            for x in range(9):
                self.assertEqual(b.get(x, y), EMPTY)
        self.assertIsNone(b.get(9, 0))  # 越界

    def test_invalid_size_rejected(self):
        for w, h in [(3, 15), (100, 15), (15, 4), (15, 100), (0, 0), (-5, 15)]:
            self.assertRaises(ValueError, GomokuBoard, w, h)

    def test_reset_midgame_with_new_size(self):
        b = GomokuBoard()
        b.place(7, 7)
        b.place(8, 8)
        b.reset(10, 10)
        self.assertEqual((b.width, b.height), (10, 10))
        self.assertEqual(b.state, STATE_PLAYING)
        self.assertEqual(b.current_player, BLACK)
        for y in range(10):
            for x in range(10):
                self.assertEqual(b.get(x, y), EMPTY)

    def test_reset_invalid_size_keeps_game(self):
        b = GomokuBoard()
        b.place(7, 7)
        self.assertRaises(ValueError, b.reset, 3, 3)
        self.assertEqual((b.width, b.height), (15, 15))
        self.assertEqual(b.get(7, 7), BLACK)


class TestPlace(unittest.TestCase):
    """落子。"""

    def test_legal_place(self):
        b = GomokuBoard()
        r = b.place(7, 7)
        self.assertTrue(r.ok)
        self.assertIsNone(r.reason)
        self.assertEqual(b.get(7, 7), BLACK)

    def test_place_on_occupied_fails(self):
        b = GomokuBoard()
        b.place(7, 7)
        r = b.place(7, 7)
        self.assertFalse(r.ok)
        self.assertEqual(r.reason, ERR_OCCUPIED)
        self.assertEqual(b.get(7, 7), BLACK)

    def test_place_out_of_bounds_fails(self):
        b = GomokuBoard()
        for x, y in [(-1, 0), (0, -1), (15, 0), (0, 15), (99, 99)]:
            r = b.place(x, y)
            self.assertFalse(r.ok)
            self.assertEqual(r.reason, ERR_OUT_OF_BOUNDS)
        self.assertTrue(b.is_full() is False)

    def test_place_after_win_fails(self):
        b = GomokuBoard()
        _win_horizontal(b)
        r = b.place(0, 14)
        self.assertFalse(r.ok)
        self.assertEqual(r.reason, ERR_GAME_OVER)


class TestTurnManagement(unittest.TestCase):
    """回合管理。"""

    def test_alternating_players(self):
        b = GomokuBoard()
        self.assertEqual(b.current_player, BLACK)
        r1 = b.place(7, 7)  # 黑
        r2 = b.place(8, 8)  # 白
        self.assertTrue(r1.ok and r2.ok)
        self.assertEqual(r1.player, BLACK)
        self.assertEqual(r2.player, WHITE)
        self.assertEqual(b.current_player, BLACK)

    def test_wrong_turn_rejected(self):
        b = GomokuBoard()
        b.place(7, 7)  # 黑落子，轮到白
        r = b.place(8, 8, BLACK)
        self.assertFalse(r.ok)
        self.assertEqual(r.reason, ERR_NOT_YOUR_TURN)
        self.assertEqual(b.get(8, 8), EMPTY)

    def test_enforce_turn_off_allows_consecutive(self):
        b = GomokuBoard()
        b.enforce_turn = False
        r1 = b.place(7, 7, BLACK)
        r2 = b.place(8, 8, BLACK)
        self.assertTrue(r1.ok and r2.ok)
        r3 = b.place(9, 9, BLACK)  # 连续第三次
        self.assertTrue(r3.ok)


class TestRemove(unittest.TestCase):
    """删子。"""

    def test_remove_existing_stone(self):
        b = GomokuBoard()
        b.place(7, 7)   # 黑
        b.place(8, 8)   # 白，轮到黑
        r = b.remove(7, 7)
        self.assertTrue(r.ok)
        self.assertEqual(b.get(7, 7), EMPTY)
        # 删子不算一手，不改执子方
        self.assertEqual(b.current_player, BLACK)

    def test_remove_empty_fails(self):
        b = GomokuBoard()
        r = b.remove(7, 7)
        self.assertFalse(r.ok)
        self.assertEqual(r.reason, ERR_EMPTY)

    def test_remove_out_of_bounds_fails(self):
        b = GomokuBoard()
        r = b.remove(-1, 0)
        self.assertFalse(r.ok)
        self.assertEqual(r.reason, ERR_OUT_OF_BOUNDS)

    def test_remove_after_win_fails(self):
        b = GomokuBoard()
        _win_horizontal(b)
        r = b.remove(0, 0)
        self.assertFalse(r.ok)
        self.assertEqual(r.reason, ERR_GAME_OVER)


class TestWinDetection(unittest.TestCase):
    """胜负判定（休闲规则）。"""

    def test_horizontal_five_wins(self):
        b = GomokuBoard()
        r = _win_horizontal(b)
        self.assertEqual(b.state, STATE_WON)
        self.assertEqual(b.winner, WHITE)
        self.assertEqual(r.winning_player, WHITE)
        self.assertEqual(r.winning_lines, [[(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)]])

    def test_vertical_five_wins(self):
        b = GomokuBoard(enforce_turn=False)
        for y in range(5):
            b.place(3, y, BLACK)
        self.assertEqual(b.state, STATE_WON)
        self.assertEqual(b.winner, BLACK)
        self.assertEqual(b.winning_lines, [[(3, 0), (3, 1), (3, 2), (3, 3), (3, 4)]])

    def test_diagonal_five_wins(self):
        b = GomokuBoard(enforce_turn=False)
        for i in range(5):
            b.place(5 + i, 5 + i, BLACK)
        self.assertEqual(b.state, STATE_WON)
        self.assertEqual(b.winning_lines,
                         [[(5, 5), (6, 6), (7, 7), (8, 8), (9, 9)]])

    def test_anti_diagonal_five_wins(self):
        b = GomokuBoard(enforce_turn=False)
        for i in range(5):
            b.place(4 + i, 8 - i, WHITE)
        self.assertEqual(b.state, STATE_WON)
        self.assertEqual(b.winner, WHITE)
        self.assertEqual(b.winning_lines,
                         [[(4, 8), (5, 7), (6, 6), (7, 5), (8, 4)]])

    def test_overline_six_wins(self):
        b = GomokuBoard(enforce_turn=False)
        # 先布 5 子留缺口，最后一子填 (5,5) 时形成 6 连长连
        for x, y in [(2, 2), (3, 3), (4, 4), (6, 6), (7, 7)]:
            b.place(x, y, BLACK)
        r = b.place(5, 5, BLACK)
        self.assertEqual(b.state, STATE_WON)
        # 长连返回全部 6 子
        self.assertEqual(r.winning_lines,
                         [[(2, 2), (3, 3), (4, 4), (5, 5), (6, 6), (7, 7)]])

    def test_four_in_row_does_not_win(self):
        b = GomokuBoard(enforce_turn=False)
        for i in range(4):
            b.place(i, 0, BLACK)
        self.assertEqual(b.state, STATE_PLAYING)

    def test_double_direction_win_returns_both_lines(self):
        b = GomokuBoard(enforce_turn=False)
        # 以 (7,7) 为交叉点：横向 (8..11,7) 4 子 + 斜向 (3,3)..(6,6) 4 子
        for x in range(8, 12):
            b.place(x, 7, BLACK)
        for i in range(3, 7):
            b.place(i, i, BLACK)
        r = b.place(7, 7, BLACK)  # 一子双五
        self.assertEqual(b.state, STATE_WON)
        self.assertEqual(b.winner, BLACK)
        lines = r.winning_lines
        self.assertEqual(len(lines), 2)
        self.assertIn([(3, 3), (4, 4), (5, 5), (6, 6), (7, 7)], lines)
        self.assertIn([(7, 7), (8, 7), (9, 7), (10, 7), (11, 7)], lines)

    def test_full_board_without_five_is_draw(self):
        # 5x5 填满且任何行/列/对角线都非单色（无五连）→ 平局
        b = GomokuBoard(5, 5, enforce_turn=False)
        for y in range(5):
            for x in range(5):
                player = BLACK if y % 2 == 0 else WHITE
                if x == 4:
                    player = WHITE if y % 2 == 0 else BLACK
                r = b.place(x, y, player)
                self.assertTrue(r.ok)
        self.assertEqual(b.state, STATE_DRAW)
        self.assertEqual(b.winner, EMPTY)


class TestTerminalLock(unittest.TestCase):
    """终局锁定。"""

    def test_all_ops_rejected_after_win(self):
        b = GomokuBoard()
        _win_horizontal(b)
        self.assertEqual(b.place(0, 14).reason, ERR_GAME_OVER)
        self.assertEqual(b.remove(0, 0).reason, ERR_GAME_OVER)
        self.assertEqual(b.undo().reason, ERR_GAME_OVER)

    def test_all_ops_rejected_after_draw(self):
        b = GomokuBoard(5, 5, enforce_turn=False)
        _fill_without_win(b)
        self.assertEqual(b.state, STATE_DRAW)
        self.assertEqual(b.place(0, 0).reason, ERR_GAME_OVER)  # 已占用位置也被终局拦截
        self.assertEqual(b.remove(0, 0).reason, ERR_GAME_OVER)
        self.assertEqual(b.undo().reason, ERR_GAME_OVER)

    def test_reset_after_terminal_starts_new_game(self):
        b = GomokuBoard()
        _win_horizontal(b)
        b.reset()
        self.assertEqual(b.state, STATE_PLAYING)
        self.assertEqual(b.current_player, BLACK)
        self.assertTrue(b.place(7, 7).ok)


class TestUndo(unittest.TestCase):
    """悔棋。"""

    def test_undo_last_move(self):
        b = GomokuBoard()
        b.place(7, 7)  # 黑
        b.place(8, 8)  # 白，轮到黑
        r = b.undo()
        self.assertTrue(r.ok)
        self.assertEqual(r.move, (8, 8, WHITE))
        self.assertEqual(b.get(8, 8), EMPTY)
        # 执子方回退为被撤销那手的落子方
        self.assertEqual(b.current_player, WHITE)

    def test_undo_on_empty_board_fails(self):
        b = GomokuBoard()
        r = b.undo()
        self.assertFalse(r.ok)
        self.assertEqual(r.reason, ERR_NO_HISTORY)

    def test_undo_after_remove(self):
        # 落子 A、落子 B、删除 B 后悔棋：撤销的是 B 那一手，位置已空仍为空
        b = GomokuBoard()
        b.place(7, 7)  # A 黑
        b.place(8, 8)  # B 白
        self.assertTrue(b.remove(8, 8).ok)
        r = b.undo()
        self.assertTrue(r.ok)
        self.assertEqual(r.move, (8, 8, WHITE))
        self.assertEqual(b.get(8, 8), EMPTY)
        self.assertEqual(b.current_player, WHITE)
        # A 仍在棋盘
        self.assertEqual(b.get(7, 7), BLACK)


class TestSerialize(unittest.TestCase):
    """状态序列化。"""

    def test_roundtrip_midgame(self):
        b = GomokuBoard()
        b.place(7, 7)
        b.place(8, 8)
        b.place(7, 8)
        b.remove(7, 8)  # 删子不入历史但改变棋盘
        data = b.serialize()
        for value in _iter_simple(data):
            self.assertIsInstance(value, (int, str, bool, list, dict),
                                  "serialize 含非简单类型: %r" % (value,))
        b2 = GomokuBoard.deserialize(data)
        self.assertEqual((b2.width, b2.height), (b.width, b.height))
        self.assertEqual(b2.state, b.state)
        self.assertEqual(b2.current_player, b.current_player)
        self.assertEqual(b2.enforce_turn, b.enforce_turn)
        for y in range(b.height):
            for x in range(b.width):
                self.assertEqual(b2.get(x, y), b.get(x, y))
        # 被删的子不复活，落子历史保留（可继续悔棋）
        self.assertEqual(b2.get(7, 8), EMPTY)
        r = b2.undo()
        self.assertTrue(r.ok)
        self.assertEqual(r.move, (7, 8, BLACK))

    def test_roundtrip_terminal_state(self):
        b = GomokuBoard()
        _win_horizontal(b)
        data = b.serialize()
        b2 = GomokuBoard.deserialize(data)
        self.assertEqual(b2.state, STATE_WON)
        self.assertEqual(b2.winner, WHITE)
        self.assertEqual(b2.winning_lines, b.winning_lines)
        self.assertEqual(b2.place(0, 14).reason, ERR_GAME_OVER)


# ---------- 辅助 ----------

_BLACK_DECOYS = [(0, 10), (1, 11), (2, 10), (3, 11), (4, 10)]  # 非共线，不干扰胜负


def _win_horizontal(b):
    """黑 5 手非共线干扰 + 白在 (0..4, 0) 连成横向五。返回成五那一手的结果。"""
    for i in range(4):
        b.place(*_BLACK_DECOYS[i])  # 黑
        b.place(i, 0)               # 白
    b.place(*_BLACK_DECOYS[4])  # 黑
    return b.place(4, 0)  # 白，第 5 子成五


def _fill_without_win(b):
    """把 5x5 棋盘填满且无任何五连（配合 enforce_turn=False 的顺序落子）。"""
    for y in range(5):
        for x in range(5):
            player = BLACK if y % 2 == 0 else WHITE
            if x == 4:
                player = WHITE if y % 2 == 0 else BLACK
            b.place(x, y, player)


def _iter_simple(data):
    """展开 dict/list，产出所有叶子值。"""
    if isinstance(data, dict):
        for value in data.values():
            for leaf in _iter_simple(value):
                yield leaf
    elif isinstance(data, list):
        for value in data:
            for leaf in _iter_simple(value):
                yield leaf
    else:
        yield data


if __name__ == "__main__":
    unittest.main(verbosity=2)
