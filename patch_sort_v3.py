from pathlib import Path
import re

FILE = Path("combined_app.py")
BACKUP = Path("combined_app.py.bak_sort_v3")

src = FILE.read_text(encoding="utf-8")

# 新排序映射
new_map = """
        status_score = {
            "✅ 进行中": 0,
            "🟠 未知": 1,
            "⏳ 未开始": 2,
            "🔴 已结束": 3,
        }.get(status, 99)
"""

patched = re.sub(
    r"status_score\s*=\s*\{[\s\S]*?\}\.get\(status, 99\)",
    new_map,
    src
)

if patched == src:
    print("⚠️ 补丁未生效，可能已经存在或未找到替换段落")
else:
    BACKUP.write_text(src, encoding="utf-8")
    FILE.write_text(patched, encoding="utf-8")
    print("✅ 排序逻辑补丁应用成功，备份：", BACKUP)
