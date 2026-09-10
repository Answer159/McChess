# -*- coding: utf-8 -*-
"""纯五子棋核心逻辑（零 MC 依赖，py2/3 双兼容）。

状态机: PLAYING -> WON(player) / DRAW，终局锁定，唯一出口是 reset()。
规则为休闲规则：4 个方向上 5 连及以上（含长连）即获胜。
坐标为 0-indexed 抽象坐标 (x, y)，x 为列、y 为行；与 MC 方块坐标的映射由上层负责。
"""

# 棋子
EMPTY = 0
BLACK = 1  # 先手
WHITE = 2  # 后手

# 对局状态
STATE_PLAYING = "playing"
STATE_WON = "won"
STATE_DRAW = "draw"

# 棋盘尺寸限制
MIN_SIZE = 5
MAX_SIZE = 99

# 错误原因码（上层可据此映射提示文案）
ERR_INVALID_SIZE = "invalid_size"
ERR_OUT_OF_BOUNDS = "out_of_bounds"
ERR_OCCUPIED = "occupied"
ERR_EMPTY = "empty"
ERR_GAME_OVER = "game_over"
ERR_NOT_YOUR_TURN = "not_your_turn"
ERR_NO_HISTORY = "no_history"

# 胜负判定的 4 个方向：横、竖、两条斜线
_DIRECTIONS = ((1, 0), (0, 1), (1, 1), (1, -1))


class PlaceResult(object):
    """落子结果。ok 为 True 时 reason 为 None。"""

    def __init__(self, ok, reason=None, player=None, state=None,
                 winning_player=None, winning_lines=None):
        self.ok = ok
        self.reason = reason
        self.player = player
        self.state = state
        # 成五时：获胜方与所有成五连线（每条线为坐标列表，供 MC 端高亮）
        self.winning_player = winning_player
        self.winning_lines = winning_lines or []

    def __repr__(self):
        if self.ok:
            return "PlaceResult(ok=True, player=%r, state=%r)" % (self.player, self.state)
        return "PlaceResult(ok=False, reason=%r)" % (self.reason,)


class RemoveResult(object):
    """删子结果。"""

    def __init__(self, ok, reason=None):
        self.ok = ok
        self.reason = reason

    def __repr__(self):
        if self.ok:
            return "RemoveResult(ok=True)"
        return "RemoveResult(ok=False, reason=%r)" % (self.reason,)


class UndoResult(object):
    """悔棋结果。ok 为 True 时 move 为被撤销的 (x, y, player)。"""

    def __init__(self, ok, reason=None, move=None):
        self.ok = ok
        self.reason = reason
        self.move = move

    def __repr__(self):
        if self.ok:
            return "UndoResult(ok=True, move=%r)" % (self.move,)
        return "UndoResult(ok=False, reason=%r)" % (self.reason,)


class GomokuBoard(object):
    """五子棋棋盘：落子 / 删子 / 悔棋 / 胜负判定 / 序列化。"""

    def __init__(self, width=15, height=15, enforce_turn=True):
        self._enforce_turn = True
        self.reset(width, height, enforce_turn=enforce_turn)

    # ---------- 属性 ----------

    @property
    def width(self):
        return self._width

    @property
    def height(self):
        return self._height

    @property
    def state(self):
        return self._state

    @property
    def winner(self):
        return self._winner

    @property
    def current_player(self):
        return self._current_player

    @property
    def enforce_turn(self):
        return self._enforce_turn

    @enforce_turn.setter
    def enforce_turn(self, value):
        self._enforce_turn = bool(value)

    # ---------- 棋盘管理 ----------

    def reset(self, width=None, height=None, enforce_turn=None):
        """重置棋盘开新局。不传尺寸则沿用当前尺寸；尺寸非法时抛 ValueError。"""
        if width is None:
            width = self._width
        if height is None:
            height = self._height
        self._validate_size(width, height)
        self._width = width
        self._height = height
        self._grid = [EMPTY] * (width * height)
        self._history = []  # [(x, y, player), ...] 只记落子，不记删子
        self._state = STATE_PLAYING
        self._winner = EMPTY
        self._winning_lines = []
        self._current_player = BLACK
        if enforce_turn is not None:
            self._enforce_turn = bool(enforce_turn)

    @staticmethod
    def _validate_size(width, height):
        for name, value in (("width", width), ("height", height)):
            if not isinstance(value, int) or isinstance(value, bool) \
                    or value < MIN_SIZE or value > MAX_SIZE:
                raise ValueError("%s: %r (%s)" % (ERR_INVALID_SIZE, value, name))

    def in_bounds(self, x, y):
        return 0 <= x < self._width and 0 <= y < self._height

    def get(self, x, y):
        """返回 (x, y) 处棋子；越界返回 None。"""
        if not self.in_bounds(x, y):
            return None
        return self._grid[y * self._width + x]

    def is_full(self):
        return EMPTY not in self._grid

    def stones(self):
        """返回全部棋子 [(x, y, player), ...]，按落子顺序。"""
        return list(self._history)

    def _is_playing(self):
        return self._state == STATE_PLAYING

    # ---------- 落子 / 删子 / 悔棋 ----------

    def place(self, x, y, player=None):
        """在 (x, y) 落子。player 缺省为当前执子方。"""
        if player is None:
            player = self._current_player
        if not self._is_playing():
            return PlaceResult(False, ERR_GAME_OVER, player=player, state=self._state)
        if not self.in_bounds(x, y):
            return PlaceResult(False, ERR_OUT_OF_BOUNDS, player=player, state=self._state)
        if self._grid[y * self._width + x] != EMPTY:
            return PlaceResult(False, ERR_OCCUPIED, player=player, state=self._state)
        if self._enforce_turn and player != self._current_player:
            return PlaceResult(False, ERR_NOT_YOUR_TURN, player=player, state=self._state)

        self._grid[y * self._width + x] = player
        self._history.append((x, y, player))

        lines = self._check_win_at(x, y)
        if lines:
            self._state = STATE_WON
            self._winner = player
            self._winning_lines = lines
            return PlaceResult(True, player=player, state=self._state,
                               winning_player=player, winning_lines=lines)
        if self.is_full():
            self._state = STATE_DRAW
            return PlaceResult(True, player=player, state=self._state)

        self._current_player = WHITE if player == BLACK else BLACK
        return PlaceResult(True, player=player, state=self._state)

    def remove(self, x, y):
        """删除 (x, y) 处棋子（对应挖掉棋子方块的玩法）。删子不算一手，不改执子方。"""
        if not self._is_playing():
            return RemoveResult(False, ERR_GAME_OVER)
        if not self.in_bounds(x, y):
            return RemoveResult(False, ERR_OUT_OF_BOUNDS)
        if self._grid[y * self._width + x] == EMPTY:
            return RemoveResult(False, ERR_EMPTY)
        self._grid[y * self._width + x] = EMPTY
        return RemoveResult(True)

    def undo(self):
        """撤销最近一手落子，执子方回退。删子不产生历史，不会被悔棋恢复。"""
        if not self._is_playing():
            return UndoResult(False, ERR_GAME_OVER)
        if not self._history:
            return UndoResult(False, ERR_NO_HISTORY)
        x, y, player = self._history.pop()
        self._grid[y * self._width + x] = EMPTY
        self._current_player = player
        return UndoResult(True, move=(x, y, player))

    # ---------- 胜负判定 ----------

    def _check_win_at(self, x, y):
        """增量判定：只查经过 (x, y) 的 4 条线。返回所有成五连线（坐标列表）。"""
        player = self._grid[y * self._width + x]
        lines = []
        for dx, dy in _DIRECTIONS:
            cells = [(x, y)]
            for sign in (1, -1):
                cx, cy = x + dx * sign, y + dy * sign
                while self.in_bounds(cx, cy) \
                        and self._grid[cy * self._width + cx] == player:
                    cells.append((cx, cy))
                    cx += dx * sign
                    cy += dy * sign
            if len(cells) >= 5:
                cells.sort()
                lines.append(cells)
        return lines

    @property
    def winning_lines(self):
        """终局成五连线（每条为坐标列表）；未终局时为空。"""
        return [list(line) for line in self._winning_lines]

    # ---------- 序列化 ----------

    def serialize(self):
        """序列化为简单类型 dict（可写入门数据），可用 deserialize 无损恢复。

        注意 stones（棋盘现状，按坐标扫描）与 history（落子历史，用于悔棋）分开存：
        被删除的棋子不在棋盘上但仍在历史里，二者不能互相推导。
        """
        stones = []
        for y in range(self._height):
            for x in range(self._width):
                player = self._grid[y * self._width + x]
                if player != EMPTY:
                    stones.append([x, y, player])
        return {
            "version": 1,
            "width": self._width,
            "height": self._height,
            "current_player": self._current_player,
            "enforce_turn": self._enforce_turn,
            "state": self._state,
            "winner": self._winner,
            "stones": stones,
            "history": [list(move) for move in self._history],
            "winning_lines": [[list(cell) for cell in line] for line in self._winning_lines],
        }

    @classmethod
    def deserialize(cls, data):
        """从 serialize() 的数据恢复对局。"""
        board = cls(data["width"], data["height"])
        board._enforce_turn = bool(data.get("enforce_turn", True))
        for x, y, player in data.get("stones", []):
            board._grid[y * board._width + x] = player
        board._history = [tuple(move) for move in data.get("history", [])]
        board._state = data.get("state", STATE_PLAYING)
        board._winner = data.get("winner", EMPTY)
        board._winning_lines = [tuple(map(tuple, line)) for line in data.get("winning_lines", [])]
        board._current_player = data.get("current_player", BLACK)
        return board
