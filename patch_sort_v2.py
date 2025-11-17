import pathlib
import sys

ROOT = pathlib.Path("/opt/GalxeMonitor")
TARGET = ROOT / "combined_app.py"
BACKUP = ROOT / "combined_app.py.bak_sort_v2"

src = TARGET.read_text(encoding="utf-8")
lines = src.splitlines(keepends=True)

idx = None
for i, line in enumerate(lines):
    if 'cards = ""' in line and "card_html(p) for p in projs" in line:
        idx = i
        break

if idx is None:
    print("❌ 没能找到生成卡片的那一行（cards = ... projs）")
    sys.exit(1)

insert_block = '''\
    # === NTX 自定义排序：进行中 / 最新活动优先 ===
    def _ntx_sort_key(p):
        status = (p.get("latest_status") or "").strip()

        # 排序等级：数值越小越靠前
        # 0：进行中 / 有最新活动
        # 1：已结束
        # 2：暂无活动 / 抓取失败 / 未知
        rank = 2
        if "进行中" in status or "最新活动" in status:
            rank = 0
        elif "已结束" in status:
            rank = 1

        latest = p.get("latest") or {}

        def _to_int(v):
            try:
                return int(v)
            except:
                return 0

        start_ts = _to_int(latest.get("startTime"))
        created_ts = _to_int(latest.get("createdAt"))
        ts = max(start_ts, created_ts)

        # 按 (rank, -ts) 排序：先按状态，再按时间从新到旧
        return (rank, -ts)

    sorted_projs = sorted(projs, key=_ntx_sort_key)
'''

# 在 cards 那一行之前插入排序块
lines.insert(idx, insert_block)

# 把原来的 cards 行改成使用 sorted_projs
original_line = lines[idx + 1]  # 插入后，原行往后挪了一位
if "sorted_projs" not in original_line:
    lines[idx + 1] = original_line.replace(
        "cards = \"\".join(card_html(p) for p in projs)",
        "cards = \"\".join(card_html(p) for p in sorted_projs)"
    )

new_src = "".join(lines)

BACKUP.write_text(src, encoding="utf-8")
TARGET.write_text(new_src, encoding="utf-8")
print("✅ 成功：已插入 NTX 排序逻辑，备份文件：", BACKUP.name)
