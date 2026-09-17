# -*- coding: utf-8 -*-
"""随机棋盘形状分布模拟（开发工具，不进游戏）：复刻 GenerateBoardCells 的缺格算法，
统计缺格数量分布并打印样例形状，用于调 config 的随机化参数。"""
import random

HALF = 4        # BoardSize // 2
EDGE = 0.5      # BoardEdgeRemoveChance
FALL = 2        # BoardRemoveFalloff
KEEP = 1        # BoardCenterKeepRadius


def gen():
    cells = set()
    for x in range(-HALF, HALF + 1):
        for z in range(-HALF, HALF + 1):
            ring = max(abs(x), abs(z))
            if ring <= KEEP:
                cells.add((x, z))
                continue
            if random.random() >= EDGE * (ring / float(HALF)) ** FALL:
                cells.add((x, z))
    return cells


counts = [len(gen()) for _ in range(2000)]
print("cells min {} max {} avg {:.1f} (of {})".format(
    min(counts), max(counts), sum(counts) / float(len(counts)), 9 * 9))

ring_miss = dict((r, 0) for r in range(HALF + 1))
ring_tot = dict((r, 0) for r in range(HALF + 1))
for _ in range(2000):
    board = gen()
    for x in range(-HALF, HALF + 1):
        for z in range(-HALF, HALF + 1):
            r = max(abs(x), abs(z))
            ring_tot[r] += 1
            if (x, z) not in board:
                ring_miss[r] += 1
for r in sorted(ring_tot):
    print("ring {}: missing {:.1%}".format(r, ring_miss[r] / float(ring_tot[r])))

for sample in range(3):
    print("--- sample {} ---".format(sample + 1))
    b = gen()
    for z in range(-HALF, HALF + 1):
        print("".join("[]" if (x, z) in b else ".." for x in range(-HALF, HALF + 1)))
