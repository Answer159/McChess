# -*- coding: utf-8 -*-
"""gomokuCore 包：纯五子棋核心逻辑（零 MC 依赖）。"""

from .board import (
    EMPTY, BLACK, WHITE,
    STATE_PLAYING, STATE_WON, STATE_DRAW,
    ERR_INVALID_SIZE, ERR_OUT_OF_BOUNDS, ERR_OCCUPIED, ERR_EMPTY,
    ERR_GAME_OVER, ERR_NOT_YOUR_TURN, ERR_NO_HISTORY,
    GomokuBoard, PlaceResult, RemoveResult, UndoResult,
)
