from pathlib import Path

TARGET = Path("/opt/GalxeMonitor/combined_app.py")
BACKUP = TARGET.with_name("combined_app.py.bak_ntx_sort2")

src = TARGET.read_text(encoding="utf-8")

line_cards = 'cards = "".join(card_html(p) for p in sorted_projs)'

if line_cards not in src:
    print("❌ 没找到 cards = ...sorted_projs 这一行，当前文件和预期不一致。")
    raise SystemExit(1)

if "sorted_projs =" in src and "key=_ntx_sort_key" in src:
    print("✅ 看起来排序逻辑已经存在，无需重复打补丁。")
    raise SystemExit(0)

print("📦 备份原文件 ->", BACKUP.name)
BACKUP.write_text(src, encoding="utf-8")

insert_block = """
    # NTX 自定义排序：将进行中 > 即将开始 > 已结束 > 无活动，
    # 同组内 Trending 项目优先，其次按时间排序。
    sorted_projs = sorted(
        projs,
        key=_ntx_sort_key,
    )
"""

src = src.replace(line_cards, insert_block + "    " + line_cards)

if "_ntx_sort_key(" not in src:
    helper = """

def _ntx_sort_key(p):
    import time
    latest = p.get("latest") or {}
    start = latest.get("startTime") or 0
    end = latest.get("endTime") or 0
    status = (latest.get("status") or "").lower()
    now = int(time.time())

    # 默认：无活动
    group = 3
    score = 0

    if latest:
        # 粗暴兜底：先按 status 字符串判断，再按时间判断
        if status in ("ongoing", "running"):
            group = 0
            score = - (end or start or 0)  # 越晚结束越靠前
        elif status in ("upcoming", "not_started"):
            group = 1
            score = start or 0            # 越早开始越靠前
        else:
            # 结束的：用开始时间倒序，最近结束的在前
            group = 2
            score = - (start or 0)

        # 如果没提供 status，就用时间简单判断一下
        if status == "" and (start and end):
            if start <= now <= end:
                group = 0
                score = -end
            elif start > now:
                group = 1
                score = start
            else:
                group = 2
                score = -start

    # Trending 项目优先：0=trending, 1=custom
    is_trending = 0 if p.get("category") == "trending" else 1
    name = p.get("name", "")

    # 排序优先级：
    # 1) group（进行中/未开始/已结束/无活动）
    # 2) 是否 trending
    # 3) 时间 score
    # 4) 名字，保证结果稳定
    return (group, is_trending, score, name)
"""
    src += helper

TARGET.write_text(src, encoding="utf-8")
print("✅ 成功：已插入 NTX 排序逻辑，备份文件：", BACKUP.name)
