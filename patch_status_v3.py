from pathlib import Path
import re

FILE = Path("combined_app.py")
BACKUP = Path("combined_app.py.bak_status_v3")

src = FILE.read_text(encoding="utf-8")

# 新的状态函数（完整替换）
new_func = """
def _build_status(latest):
    \"\"\"根据 startTime / endTime 计算状态：未开始 / 进行中 / 已结束 / 未知。\"\"\"
    if not latest:
        return "🟠 未知"

    now = datetime.utcnow().replace(tzinfo=timezone.utc)
    start = _parse_ts(latest.get("startTime"))
    end = _parse_ts(latest.get("endTime"))

    if start and now < start:
        return "⏳ 未开始"
    if end and now > end:
        return "🔴 已结束"
    if start and (not end or start <= now <= end):
        return "✅ 进行中"

    return "🟠 未知"
"""

# 用正则替换整个函数
patched = re.sub(
    r"def _build_status[\s\S]*?return \"未知\"",
    new_func,
    src
)

if patched == src:
    print("⚠️ 补丁未生效，可能已经打过或代码不匹配")
else:
    BACKUP.write_text(src, encoding="utf-8")
    FILE.write_text(patched, encoding="utf-8")
    print("✅ 状态颜色补丁应用成功，备份文件：", BACKUP)
