#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Galxe Space 批量解析工具（从本地种子列表读取，而不是全网爬虫）

用法：
1. 编辑 tools/space_seeds.txt，填入你要监控的 Space 链接或别名（每行一个）。
2. 运行：python tools/galxe_crawler.py
3. 生成 tools/spaces_bulk.json
4. 再运行：python tools/merge_spaces_config.py 导入到 config.json
"""

import os
import re
import time
import json
from typing import List, Dict, Optional, Set

import requests

# ========= 可配置参数区域 =========

# 种子列表文件路径
TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
SEED_FILE = os.path.join(TOOLS_DIR, "space_seeds.txt")

# 输出文件路径
OUTPUT_FILE = os.path.join(TOOLS_DIR, "spaces_bulk.json")

# 请求 Space 详情页之间的间隔（秒）
SPACE_PAGE_INTERVAL = 3

# HTTP 请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; GalxeMonitorSeedResolver/1.0; +https://example.com)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "close",
}

# ========= 工具函数 =========

def load_seed_aliases(path: str) -> List[str]:
    """
    从 space_seeds.txt 读取 Space 别名/链接，解析出 alias 列表。
    """
    if not os.path.exists(path):
        print(f"[ERROR] 未找到种子文件: {path}")
        return []

    aliases: Set[str] = set()

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw or raw.startswith("#"):
                continue

            # 如果是 URL，从路径中提取 alias
            if raw.startswith("http://") or raw.startswith("https://"):
                # 例如 https://app.galxe.com/quest/SpaceandTimeDB/GCxwBtKJXi
                m = re.search(r"galxe\.com/(?:quest/)?([A-Za-z0-9_-]+)", raw)
                if m:
                    alias = m.group(1)
                    aliases.add(alias)
                else:
                    print(f"[WARN] 无法从 URL 中解析 alias: {raw}")
            else:
                # 否则直接当作 alias
                aliases.add(raw)

    alias_list = sorted(list(aliases))
    print(f"[INFO] 共从 {path} 解析出 {len(alias_list)} 个去重后的 Space 别名。")
    return alias_list


def fetch_space_id_by_alias(alias: str) -> Optional[int]:
    """
    访问 Space 页面，尝试解析 spaceId。
    注意：这依赖对方前端结构，如果将来改版，可能需要调整正则。
    """
    # 目前 Space 页面常见路径是 https://app.galxe.com/quest/{alias}
    url_candidates = [
        f"https://app.galxe.com/quest/{alias}",
        f"https://galxe.com/{alias}",  # 兼容老路径
    ]

    for url in url_candidates:
        print(f"[INFO] 请求 Space 详情页: {url}")
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            if resp.status_code != 200:
                print(f"[WARN] Space {alias} 页面状态码: {resp.status_code} ({url})")
                continue

            text = resp.text

            # 尝试匹配 "spaceId": 82200
            m = re.search(r'"spaceId"\s*:\s*(\d+)', text)
            if m:
                sid = int(m.group(1))
                print(f"[INFO] alias={alias} 解析到 spaceId={sid}")
                return sid

            # 兜底：匹配 "id": 82200, "spaceUrl": "Alias"
            pattern = r'"id"\s*:\s*(\d+)\s*,\s*"spaceUrl"\s*:\s*"' + re.escape(alias) + r'"'
            m2 = re.search(pattern, text)
            if m2:
                sid = int(m2.group(1))
                print(f"[INFO] alias={alias} 通过兜底规则解析到 spaceId={sid}")
                return sid

            print(f"[WARN] 未在 {url} 页面中找到 spaceId 字段。")

        except Exception as e:
            print(f"[ERROR] 请求 Space {alias} 详情页失败 ({url}): {e}")

    return None


def main():
    aliases = load_seed_aliases(SEED_FILE)
    if not aliases:
        print("[ERROR] 别名列表为空，请先编辑 tools/space_seeds.txt 填入 Space。")
        return

    results: List[Dict] = []

    total = len(aliases)
    for idx, alias in enumerate(aliases, start=1):
        print(f"[INFO] [{idx}/{total}] 解析 Space: {alias}")
        space_id = fetch_space_id_by_alias(alias)
        result = {
            "space_id": space_id,
            "alias": alias,
            "name": alias,
            "tags": ["seed_list"],
        }
        results.append(result)
        time.sleep(SPACE_PAGE_INTERVAL)

    data = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "source": "space_seeds.txt",
        "spaces": results,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[INFO] 解析结束，共生成 {len(results)} 条记录。")
    print(f"[INFO] 已将结果写入: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
