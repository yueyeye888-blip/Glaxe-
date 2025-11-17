# -*- coding: utf-8 -*-
"""
自动把 `/api/raw` 路由那一段代码，从文件尾部挪到
`if __name__ == "__main__":` 之前，避免因为主循环阻塞
导致路由注册不到。
"""

import io
import os

PATH = "/opt/GalxeMonitor/combined_app.py"
MARK = "# ===== NTX 扩展：提供统一 JSON 接口 /api/raw ====="
MAIN = 'if __name__ == "__main__"'

def main():
    if not os.path.exists(PATH):
        raise SystemExit("找不到 combined_app.py: %s" % PATH)

    with io.open(PATH, "r", encoding="utf-8") as f:
        text = f.read()

    pos_tail = text.find(MARK)
    if pos_tail == -1:
        raise SystemExit("没有找到标记行：%r，说明之前的 /api/raw 补丁不在这个文件里。" % MARK)

    # 现在的策略：从 MARK 开始到文件末尾，都是我们后加的扩展逻辑
    tail = text[pos_tail:]
    head = text[:pos_tail]

    pos_main = head.find(MAIN)
    if pos_main == -1:
        raise SystemExit("在 head 里没有找到入口标记：%r" % MAIN)

    # 如果 tail 本来就已经在 main 之前，就不动
    if pos_tail < pos_main:
        print("看起来 /api/raw 已经在入口之前，无需调整。")
        return

    new_text = head[:pos_main] + tail + "\n" + head[pos_main:]

    backup_path = PATH + ".bak_api_raw_fix"
    with io.open(backup_path, "w", encoding="utf-8") as f:
        f.write(text)

    with io.open(PATH, "w", encoding="utf-8") as f:
        f.write(new_text)

    print("已完成重排：")
    print(" - 备份原文件到:", backup_path)
    print(" - 将 /api/raw 段移动到入口 %r 之前" % MAIN)

if __name__ == "__main__":
    main()
