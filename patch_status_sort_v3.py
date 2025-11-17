from pathlib import Path
import shutil, re

PATH = Path("combined_app.py")
BACKUP = Path("combined_app.py.bak_status_v3")

print("🔍 开始应用状态颜色和排序补丁...")

src = PATH.read_text(encoding="utf-8")

# ======================
# 1. 修改状态颜色（CSS）
# ======================
css_old = r"""\.pill-active """
css_new = r""".pill-active {color:#33ff99;} /* 进行中：绿色 */
.pill-unknown {color:#ffaa33;} /* 未知：橙色 */
.pill-upcoming {color:#66aaff;} /* 未开始：蓝色 */
.pill-ended {color:#ff6666;} /* 已结束：红色 */
"""

if "pill-unknown" not in src:
    src = src.replace("""<style>""", """<style>
.pill-active {color:#33ff99;} /* 进行中：绿色 */
.pill-unknown {color:#ffaa33;} /* 未知：橙色 */
.pill-upcoming {color:#66aaff;} /* 未开始：蓝色 */
.pill-ended {color:#ff6666;} /* 已结束：红色 */
""")

# ======================
# 2. 修改 _build_status()
# ======================
find_status = "_build_status(latest):"
if find_status in src:
    new_block = """def _build_status(latest):
    \"\"\"统一返回带 css class 的状态\"\"\"
    if not latest:
        return ("未知", "pill-unknown")

    now = datetime.utcnow().replace(tzinfo=timezone.utc)
    start = _parse_ts(latest.get("startTime"))
    end = _parse_ts(latest.get("endTime"))

    if start and now < start:
        return ("⏳ 未开始", "pill-upcoming")
    if end and now > end:
        return ("⚠️ 已结束", "pill-ended")
    if start and (not end or start <= now <= end):
        return ("✅ 进行中", "pill-active")
    return ("未知", "pill-unknown")
"""
    # 替换整个函数
    src = re.sub(r"def _build_status.*?return \"未知\"", new_block, src, flags=re.S)

# ======================
# 3. 给排序逻辑增加优先级
# ======================
sort_key_old = r"lambda p: p.get\(\"latest\"\)"
if "status_priority" not in src:
    sort_patch = """
    # 状态排序优先级
    status_priority = {
        "pill-active": 1,     # 进行中（排最前）
        "pill-unknown": 2,    # 未知（橙色）
        "pill-upcoming": 3,   # 未开始
        "pill-ended": 4       # 已结束（排最后）
    }

    def _sort_key(p):
        latest = p.get("latest")
        if not latest:
            return (999, 0)
        status, css = _build_status(latest)
        return (status_priority.get(css, 999), 0)
"""

    # 插入排序函数
    src = src.replace("app = Flask(__name__)", sort_patch + "\napp = Flask(__name__)")

# 替换卡片渲染处，加入 css class
if "{status}" in src:
    src = src.replace("""<div class="pill """, """<div class="pill {css} """)

    src = src.replace("status=status,", "status=status, css=css,")

# ======================
# 写入补丁结果
# ======================
BACKUP.write_text(src, encoding="utf-8")
PATH.write_text(src, encoding="utf-8")

print("✅ 补丁已应用，备份文件：", BACKUP)
