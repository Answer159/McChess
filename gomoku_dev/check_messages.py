# -*- coding: utf-8 -*-
"""文案key校验：gomokuServerSystem 的 Msg/MsgPlayer/MsgThrottled/GetText 调用点
与 messageConfig.MESSAGES 的双向一致性检查（py3 ast 静态解析，不执行游戏代码）。

检查项：
  1. 调用了但字典没有的key（打错/漏配）
  2. 字典有但没人引用的key（调用点漏改）
  3. 模板占位符 {name} 与调用点 kwargs 名不匹配（缺参/多参）
  4. 含占位符的模板试填不抛异常
  5. 残留的 self.Announce(<字面量>) 直接调用（改完后应只剩传变量的两处OnGameEnd）
  6. 残留的 SendMessageToPlayer(<字面量>)（OnGameEnd之外应只剩原语本体）

运行: python gomoku_dev/check_messages.py   （退出码非0=有错误）
"""

import ast
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PACK_ROOT = os.path.abspath(os.path.join(_HERE, "..", "behavior_packs", "behavior_pack_864FhZqu_7ec35a94"))
sys.path.insert(0, _PACK_ROOT)

from script_Gomoku import messageConfig  # noqa: E402

SERVER_PY = os.path.join(_PACK_ROOT, "script_Gomoku", "gomokuServerSystem.py")

# key版辅助方法 -> key参数的位置（Msg/MsgPlayer: 第1参；MsgThrottled: 第3参；GetText: 第1参）
KEY_METHODS = {"Msg": 0, "MsgPlayer": 1, "MsgThrottled": 2, "GetText": 0}

PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def collect_calls(tree):
    """遍历AST，返回 [(方法名, key, kwargs名列表, 行号)]；key非常量则记None。
    跳过Msg/MsgPlayer/MsgThrottled/GetText四个辅助方法自身定义内部的调用
    （它们把key当变量转发给GetText，属正常实现而非调用点）"""
    found = []
    for func in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        if func.name in KEY_METHODS:
            continue
        for node in ast.walk(func):
            if not isinstance(node, ast.Call):
                continue
            func_attr = node.func
            if not (isinstance(func_attr, ast.Attribute) and isinstance(func_attr.value, ast.Name)
                    and func_attr.value.id == "self"):
                continue
            name = func_attr.attr
            if name not in KEY_METHODS:
                continue
            argIdx = KEY_METHODS[name]
            if len(node.args) <= argIdx:
                continue
            keyArg = node.args[argIdx]
            key = keyArg.value if isinstance(keyArg, ast.Constant) and isinstance(keyArg.value, str) else None
            kwargs = sorted(k.arg for k in node.keywords)
            found.append((name, key, kwargs, node.lineno))
    return found


def collect_literal_announces(tree):
    """self.Announce/SendMessageToPlayer 带字符串字面量的直接调用（应已被改光）"""
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name)
                and func.value.id == "self"):
            continue
        if func.attr not in ("Announce", "SendMessageToPlayer"):
            continue
        if node.args and isinstance(node.args[-1], ast.Constant) and isinstance(node.args[-1].value, str):
            found.append((func.attr, node.args[-1].value, node.lineno))
    return found


def main():
    # Windows控制台默认gbk，中文诊断信息会变乱码
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    with open(SERVER_PY, "rb") as f:
        tree = ast.parse(f.read(), filename=SERVER_PY)

    calls = collect_calls(tree)
    problems = []

    # 1/2. key 双向对照
    used_keys = set()
    for name, key, kwargs, lineno in calls:
        if key is None:
            problems.append("L{}: self.{} 的key不是字符串常量，无法静态校验".format(lineno, name))
            continue
        used_keys.add(key)
        if key not in messageConfig.MESSAGES:
            problems.append("L{}: self.{}('{}') —— 字典里没有这个key".format(lineno, name, key))
    for key in sorted(messageConfig.MESSAGES):
        if key not in used_keys:
            problems.append("MESSAGES['{}'] 定义了但没有任何调用点引用".format(key))

    # 3/4. 占位符与kwargs对照 + 试填
    for name, key, kwargs, lineno in calls:
        if key is None or key not in messageConfig.MESSAGES:
            continue
        template = messageConfig.MESSAGES[key]
        placeholders = sorted(set(PLACEHOLDER_RE.findall(template)))
        if set(placeholders) != set(kwargs):
            missing = [p for p in placeholders if p not in kwargs]
            extra = [k for k in kwargs if k not in placeholders]
            detail = ""
            if missing:
                detail += " 缺参数: {}".format(missing)
            if extra:
                detail += " 多参数: {}".format(extra)
            problems.append("L{}: {}('{}'){} —— 模板占位符{}".format(
                lineno, name, key, detail, placeholders))
        try:
            template.format(**{p: "x" for p in placeholders})
        except Exception as e:
            problems.append("MESSAGES['{}'] 试填失败: {}".format(key, e))

    # 5/6. 残留字面量
    for attr, text, lineno in collect_literal_announces(tree):
        problems.append("L{}: self.{}(\"{}...\") 仍是字面量直接调用，应改用Msg/MsgPlayer"
                        .format(lineno, attr, text[:30]))

    if problems:
        print("[check_messages] {} 个问题:".format(len(problems)))
        for p in problems:
            print("  " + p)
        sys.exit(1)
    print("[check_messages] OK: {} 条调用点 / {} 条文案全部对齐，无残留字面量".format(
        len(calls), len(messageConfig.MESSAGES)))


if __name__ == "__main__":
    main()
