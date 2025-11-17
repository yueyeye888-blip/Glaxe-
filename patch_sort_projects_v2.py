#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
覆盖 combined_app.py 中的 _project_sort_key：
只做一件事：有 latest 的排前面，没 latest 的排后面。
同组内按 name/alias 排序。
"""

import io
import os
import re

TARGET = "/opt/GalxeMonitor/combined_app.py"

with open(TARGET, "r", encoding="utf-8") as f:
    text = f.read()

pattern = r"def _project_sort_key\(.*?^def card_html\(p\):"
m = re.search(pattern, text, flags=re.S | re.M)

if not m:
    raise SystemExit("❌ 没有找到 _project_sort_key 定义，说明之前那版排序函数还没插进去。")

new_helper = r'''
def _project_sort_key(p, now_ts=None):
    """
    极简版排序：
    group:
      0 = 有 latest（说明最近拉取到了活动）
      1 = 没有 latest（暂无活动 / 拉取失败）
    同组内按 name/alias 排序。
    """
    latest = {}
    if isinstance(p, dict):
        latest = p.get("latest") or {}

    has_latest = 1 if latest else 0  # 有 latest → 1，没 latest → 0
    # 我们希望“有 latest”排前面，所以 group = 1 - has_latest
    group = 1 - has_latest

    name = ""
    if isinstance(p, dict):
        name = (p.get("name") or p.get("alias") or "")

    return (group, str(name))
    
def card_html(p):
'''

# 用新 helper + 原来的 card_html 开头替换老的 helper 段
text = re.sub(pattern, new_helper, text, count=1, flags=re.S | re.M)

backup_path = TARGET + ".bak_sort_v2"
with open(backup_path, "w", encoding="utf-8") as f:
    f.write(text)

os.replace(backup_path, TARGET)
print("✅ 已覆盖 _project_sort_key，排序规则：有 latest 的在前，没有 latest 的在后。")
