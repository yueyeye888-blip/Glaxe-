#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
给 combined_app.py 增加项目排序逻辑：
- 进行中（有 latest 且未结束）的活动排最前
- 其他有活动记录的排中间
- 无活动 / 拉取失败的排最后
"""

import io
import os
import re

TARGET = "/opt/GalxeMonitor/combined_app.py"

with open(TARGET, "r", encoding="utf-8") as f:
    text = f.read()

# 1. 确保有 import time
if "import time" not in text:
    # 只在第一次出现 import json 后面插入一行
    text = text.replace("import json", "import json\nimport time", 1)

# 2. 插入排序工具函数（如果还没有的话）
if "def _project_sort_key(" not in text:
    marker = "def card_html(p):"
    idx = text.find(marker)
    if idx == -1:
        raise SystemExit("找不到 card_html(p)，补丁无法自动应用。")

    helper = r'''
# === NTX: 项目排序工具 ===

def _safe_int(v, default=0):
    try:
        return int(v)
    except Exception:
        return default


def _project_sort_key(p, now_ts=None):
    """
    返回用于排序的 key：
    group:
      0 = 有 latest 且正在进行（未结束）
      1 = 有 latest 但不在进行中（已结束 / 未开始）
      2 = 没有 latest（暂无活动 / 拉取失败）
    同组内按时间倒序（新的在前），优先用 start，其次 end。
    """
    import time as _t
    if now_ts is None:
        now_ts = int(_t.time())

    latest = (p.get("latest") or {}) if isinstance(p, dict) else {}

    # 兼容各种字段名
    start = latest.get("start_ts") or latest.get("startTime") or latest.get("start_at") or 0
    end   = latest.get("end_ts")   or latest.get("endTime")   or latest.get("end_at")   or 0

    start = _safe_int(start, 0)
    end   = _safe_int(end, 0)

    if latest:
        # 有 latest，判断是否进行中
        if end > now_ts and (start == 0 or start <= now_ts):
            group = 0  # 进行中
        else:
            group = 1  # 有活动，但不在进行中
    else:
        group = 2      # 无活动 / 拉取失败

    main_ts = start or end or 0
    main_ts = _safe_int(main_ts, 0)

    # Python 默认升序，我们用 -main_ts 让时间新的排前面
    name = ""
    if isinstance(p, dict):
        name = (p.get("name") or p.get("alias") or "")
    return (group, -main_ts, name)
'''

    text = text[:idx] + helper + text[idx:]

# 3. 在生成卡片 HTML 的位置，套一层 sorted(...)
pattern = r'(\s*)cards = "".join\(card_html\(p\) for p in projs\)'
m = re.search(pattern, text)
if not m:
    raise SystemExit("找不到 cards = \"\".join(card_html(p) for p in projs) 这一行，补丁无法自动应用。")

indent = m.group(1)  # 保留原来的缩进
replacement = (
    f"{indent}# NTX: 按项目状态 + 时间排序，进行中 / 最新在前\n"
    f"{indent}import time as _t\n"
    f"{indent}now_ts = int(_t.time())\n"
    f"{indent}sorted_projs = sorted(projs, key=lambda p: _project_sort_key(p, now_ts))\n"
    f'{indent}cards = "".join(card_html(p) for p in sorted_projs)'
)

text = re.sub(pattern, replacement, text, count=1)

# 4. 写回文件
backup_path = TARGET + ".bak_sort_auto"
with open(backup_path, "w", encoding="utf-8") as f:
    f.write(text)

os.replace(backup_path, TARGET)
print("✅ 项目排序补丁已应用到", TARGET)
