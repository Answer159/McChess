# -*- coding: UTF-8 -*-
# author: lidi01
# date: 2019/10/8
import time


# 这个类的作用是延迟执行给定的函数
# 使用参考每个具体使用的地方，yield 正数为时间，负数为帧数
class CoroutineMgr(object):
    coroutines = {}
    globalEnd = []
    addCoroutines = {}

    @classmethod
    def StartCoroutine(cls, iteration):
        cls.addCoroutines[iteration] = 0
        return iteration

    @classmethod
    def StopCoroutine(cls, iteration):
        cls.globalEnd.append(iteration)

    @classmethod
    def Tick(cls):
        if cls.addCoroutines:
            for c, v in cls.addCoroutines.iteritems():
                cls.coroutines[c] = v
        cls.addCoroutines = {}
        if cls.globalEnd:
            for c in cls.globalEnd:
                if cls.coroutines.get(c):
                    del cls.coroutines[c]
            cls.globalEnd = []
        ended = []
        for c, v in cls.coroutines.iteritems():
            try:
                if v < 0:
                    v += 1
                    cls.coroutines[c] = v
                if v == 0 or (0 < v <= time.time()):
                    newv = c.next()
                    if newv > 0:
                        newv = newv + time.time()
                    cls.coroutines[c] = newv
            except StopIteration:
                ended.append(c)
        for c in ended:
            del cls.coroutines[c]
