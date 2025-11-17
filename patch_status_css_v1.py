from pathlib import Path

PATH = Path("combined_app.py")
BACKUP = Path("combined_app.py.bak_status_css_v1")

print("🔍 读取 combined_app.py ...")
src = PATH.read_text(encoding="utf-8")

# 1. 修改 card_html：按状态选 css class
old_block = '        status = _build_status(latest)\n'
if old_block not in src:
    print("❌ 没找到 'status = _build_status(latest)'，不改 card_html 部分。")
else:
    new_block = '''        status = _build_status(latest)
        if "进行中" in status:
            css = "pill-running"
        elif "未知" in status:
            css = "pill-unknown"
        elif "未开始" in status:
            css = "pill-upcoming"
        elif "已结束" in status:
            css = "pill-ended"
        else:
            css = "pill-active"
'''
    src = src.replace(old_block, new_block)

# 2. 修改卡片 HTML：使用 {css}
old_html = '<div class="pill pill-active">{status}</div>'
if old_html in src:
    src = src.replace(old_html, '<div class="pill {css}">{status}</div>')
else:
    print("⚠️ 没找到 pill-active 那一行，可能之前已经改过。")

# 3. 把 css=css 传入 format()
old_fmt = '              status=status,\n'
if old_fmt in src:
    src = src.replace(old_fmt, '              status=status,\n              css=css,\n')
else:
    print("⚠️ 没找到 format 里的 status=status，可能已经改过。")

# 4. 在 <style> 结束前追加 CSS 定义
marker = '</style>'
extra_css = '''
  .pill-running {           /* 进行中：绿色 */
    background: rgba(46, 204, 113, 0.12);
    color: #2ecc71;
  }
  .pill-unknown {           /* 未知：橙色 */
    background: rgba(243, 156, 18, 0.12);
    color: #f39c12;
  }
  .pill-upcoming {          /* 未开始：蓝色 */
    background: rgba(52, 152, 219, 0.12);
    color: #3498db;
  }
  .pill-ended {             /* 已结束：红色 */
    background: rgba(231, 76, 60, 0.12);
    color: #e74c3c;
  }
'''
if marker in src and "pill-running" not in src:
    src = src.replace(marker, extra_css + "\n" + marker)
else:
    print("ℹ️ 看起来 CSS 已经有自定义状态，或没找到 </style>。")

# 5. 写入备份和新文件
BACKUP.write_text(src, encoding="utf-8")
PATH.write_text(src, encoding="utf-8")

print("✅ 已写入修改，备份文件：", BACKUP)
