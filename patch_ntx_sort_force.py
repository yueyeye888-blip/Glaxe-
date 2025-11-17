from pathlib import Path
import re

TARGET = Path("/opt/GalxeMonitor/combined_app.py")
BACKUP = TARGET.with_suffix(".py.bak_ntxsort_force")

src = TARGET.read_text(encoding="utf-8")

pattern = (
    r"    sorted_projs\s*=\s*sorted\([\s\S]*?\)\s*\n"
    r"\s*cards = \"\".join\(card_html\(p\) for p in sorted_projs\)"
)

if not re.search(pattern, src, re.MULTILINE | re.DOTALL):
    print("❌ 没找到原来的 sorted_projs 排序代码，先发我 combined_app.py 里 index() 那一段给我看。")
else:
    BACKUP.write_text(src, encoding="utf-8")

    replacement = '''
    def _ntx_status_group(p):
        latest = p.get("latest") or {}
        status = _build_status(latest) or ""
        if "进行中" in status:
            return 0
        if ("未开始" in status) or ("即将开始" in status):
            return 1
        if "已结束" in status or "结束" in status:
            return 2
        return 3

    sorted_projs = sorted(
        projs,
        key=lambda p: (
            _ntx_status_group(p),
            0 if p.get("category") == "trending" else 1,
            -int((p.get("latest") or {}).get("startTime") or 0),
            p.get("name", "").lower(),
        ),
    )
    cards = "".join(card_html(p) for p in sorted_projs)'''.lstrip("\n")

    new_src, n = re.subn(
        pattern,
        replacement,
        src,
        flags=re.MULTILINE | re.DOTALL,
    )

    if n == 0:
        print("❌ 替换失败，没有任何位置被修改。")
    else:
        TARGET.write_text(new_src, encoding="utf-8")
        print("✅ 已强制替换排序逻辑，备份文件：", BACKUP.name)
