# -*- coding: utf-8 -*-
"""五子棋核心逻辑终端调试 REPL（零 MC 依赖，py2/3 双兼容）。

运行: python gomoku_dev/gomoku_debug.py
指令: p x y [b|w]  落子（缺省当前执子方）
      r x y        删子
      u            悔棋
      s            显示棋盘
      reset [w h]  重置（可选新尺寸，默认 15x15）
      t            切换轮次强制开关（自对弈调试用）
      h            帮助
      q            退出
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PACK_ROOT = os.path.join(_HERE, "..", "behavior_packs", "behavior_pack_864FhZqu_7ec35a94")
sys.path.insert(0, os.path.abspath(_PACK_ROOT))

from script_Gomoku.modCommon.gomokuCore.board import (  # noqa: E402
    BLACK, WHITE, EMPTY, STATE_PLAYING, STATE_WON, STATE_DRAW, GomokuBoard,
)

# py2/3 input 兼容
try:
    _input = raw_input  # noqa: F821  (py2)
except NameError:
    _input = input

_CHAR = {BLACK: "X", WHITE: "O", EMPTY: "."}
_NAME = {BLACK: "黑(X)", WHITE: "白(O)"}
_REASON_TEXT = {
    "out_of_bounds": "坐标越界",
    "occupied": "该位置已有棋子",
    "empty": "该位置没有棋子",
    "game_over": "对局已结束，输入 reset 开新局",
    "not_your_turn": "不是该方回合",
    "no_history": "没有可撤销的落子",
    "invalid_size": "非法棋盘尺寸",
}

USAGE = """指令:
  p x y [b|w]  落子（缺省当前执子方）   r x y  删子
  u            悔棋                     s      显示棋盘
  reset [w h]  重置棋盘（可选新尺寸）   t      切换轮次强制
  h            帮助                     q      退出"""


def render(board):
    """ASCII 渲染棋盘：X=黑 O=白 .=空，左上角为 (0,0)。"""
    lines = []
    col_header = " " * 3 + "".join("%-3d" % x for x in range(board.width))
    lines.append(col_header.rstrip())
    for y in range(board.height):
        row = "%-3d" % y
        for x in range(board.width):
            row += "%-3s" % _CHAR[board.get(x, y)]
        lines.append(row.rstrip())
    return "\n".join(lines)


def status_line(board):
    if board.state == STATE_WON:
        return "对局结束: %s 获胜" % _NAME[board.winner]
    if board.state == STATE_DRAW:
        return "对局结束: 平局"
    turn = "轮到 %s" % _NAME[board.current_player]
    if not board.enforce_turn:
        turn += "（轮次强制已关闭）"
    return turn


def _parse_int(text, what):
    try:
        return int(text)
    except ValueError:
        print("错误: %s 需要整数，收到 %r" % (what, text))
        return None


def _parse_player(text):
    if text in ("b", "black", "1"):
        return BLACK
    if text in ("w", "white", "2"):
        return WHITE
    print("错误: 棋子颜色用 b 或 w，收到 %r" % (text,))
    return None


def _fmt_lines(lines):
    return " ; ".join(" ".join("(%d,%d)" % cell for cell in line) for line in lines)


def handle_command(board, line):
    """处理一条指令。返回 (board, quit)。"""
    parts = line.split()
    if not parts:
        return board, False
    cmd = parts[0].lower()

    if cmd == "q":
        return board, True

    if cmd == "h":
        print(USAGE)

    elif cmd == "s":
        print(render(board))
        print(status_line(board))

    elif cmd == "p":
        if len(parts) not in (3, 4):
            print("用法: p x y [b|w]")
            return board, False
        x = _parse_int(parts[1], "x")
        y = _parse_int(parts[2], "y")
        if x is None or y is None:
            return board, False
        player = None
        if len(parts) == 4:
            player = _parse_player(parts[3])
            if player is None:
                return board, False
        result = board.place(x, y, player)
        if result.ok:
            print(render(board))
            if result.state == STATE_WON:
                print("*** %s 五连获胜! 连线: %s ***"
                      % (_NAME[result.winning_player], _fmt_lines(result.winning_lines)))
            elif result.state == STATE_DRAW:
                print("*** 棋盘已满，平局 ***")
            else:
                print(status_line(board))
        else:
            print("落子失败: %s" % _REASON_TEXT.get(result.reason, result.reason))

    elif cmd == "r":
        if len(parts) != 3:
            print("用法: r x y")
            return board, False
        x = _parse_int(parts[1], "x")
        y = _parse_int(parts[2], "y")
        if x is None or y is None:
            return board, False
        result = board.remove(x, y)
        if result.ok:
            print(render(board))
            print("已删除 (%d,%d) 的棋子，%s" % (x, y, status_line(board)))
        else:
            print("删子失败: %s" % _REASON_TEXT.get(result.reason, result.reason))

    elif cmd == "u":
        result = board.undo()
        if result.ok:
            print(render(board))
            print("已撤销 %s 在 (%d,%d) 的落子，%s"
                  % (_NAME[result.move[2]], result.move[0], result.move[1], status_line(board)))
        else:
            print("悔棋失败: %s" % _REASON_TEXT.get(result.reason, result.reason))

    elif cmd == "reset":
        width = height = 15
        if len(parts) == 3:
            width = _parse_int(parts[1], "宽")
            height = _parse_int(parts[2], "高")
            if width is None or height is None:
                return board, False
        elif len(parts) not in (1, 3):
            print("用法: reset [w h]")
            return board, False
        try:
            board.reset(width, height)
        except ValueError:
            print("重置失败: %s（宽高须为 5-99 的整数）" % _REASON_TEXT["invalid_size"])
            return board, False
        print(render(board))
        print("已重置为 %dx%d，%s" % (board.width, board.height, status_line(board)))

    elif cmd == "t":
        board.enforce_turn = not board.enforce_turn
        print("轮次强制已%s" % ("开启" if board.enforce_turn else "关闭"))

    else:
        print("未知指令: %r（输入 h 查看帮助）" % (line,))

    return board, False


def main():
    board = GomokuBoard()
    print("五子棋核心逻辑调试器")
    print(USAGE)
    print(render(board))
    print(status_line(board))
    while True:
        try:
            line = _input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        board, quit_requested = handle_command(board, line)
        if quit_requested:
            break


if __name__ == "__main__":
    main()
