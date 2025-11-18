#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 Telegram 通知功能(支持多Bot多群组)
"""

import sys
from pathlib import Path

# 添加 src 目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from app import send_telegram, load_config, build_notify_text
from datetime import datetime, timedelta


def test_notification():
    """测试多种状态的通知"""
    cfg = load_config()
    
    # 检查配置
    notify_targets = cfg.get("notify_targets", [])
    old_token = cfg.get("telegram_bot_token")
    old_chat_id = cfg.get("telegram_chat_id")
    
    if not notify_targets and not (old_token and old_chat_id):
        print("❌ 未配置Telegram通知目标")
        print("请在config.json中配置 notify_targets 或 telegram_bot_token/telegram_chat_id")
        return
    
    if notify_targets:
        print(f"📋 配置了 {len(notify_targets)} 个通知目标:")
        for i, target in enumerate(notify_targets, 1):
            name = target.get("name", f"目标{i}")
            enabled = target.get("enabled", True)
            chat_id = target.get("chat_id", "")
            projects = target.get("projects", [])
            status = "✅" if enabled else "❌"
            
            print(f"  {status} [{i}] {name} -> {chat_id}")
            if projects:
                print(f"       项目过滤: {', '.join(projects)}")
            else:
                print(f"       项目过滤: 全部")
    else:
        print(f"📋 使用旧配置: {old_chat_id}")
    
    print("\n开始测试...")
    print("=" * 50)
    
    # 测试用例1: 未开始的活动
    print("\n[1/3] 测试未开始的活动...")
    latest1 = {
        "name": "测试项目 - 未开始",
        "status": "Active",
        "startTime": int((datetime.now() + timedelta(hours=2)).timestamp()),
        "endTime": int((datetime.now() + timedelta(days=7)).timestamp()),
    }
    text1 = build_notify_text("测试项目", "test_project", latest1, "https://app.galxe.com/quest/test")
    send_telegram(cfg, text1, "test_project")
    print("✅ 已发送")
    
    # 测试用例2: 进行中的活动
    print("\n[2/3] 测试进行中的活动...")
    latest2 = {
        "name": "测试项目 - 进行中",
        "status": "Active",
        "startTime": int((datetime.now() - timedelta(hours=1)).timestamp()),
        "endTime": int((datetime.now() + timedelta(days=3)).timestamp()),
    }
    text2 = build_notify_text("测试项目", "test_project", latest2, "https://app.galxe.com/quest/test")
    send_telegram(cfg, text2, "test_project")
    print("✅ 已发送")
    
    # 测试用例3: 即将结束的活动
    print("\n[3/3] 测试即将结束的活动...")
    latest3 = {
        "name": "测试项目 - 即将结束",
        "status": "Active",
        "startTime": int((datetime.now() - timedelta(days=5)).timestamp()),
        "endTime": int((datetime.now() + timedelta(hours=6)).timestamp()),
    }
    text3 = build_notify_text("测试项目", "test_project", latest3, "https://app.galxe.com/quest/test")
    send_telegram(cfg, text3, "test_project")
    print("✅ 已发送")
    
    print("\n" + "=" * 50)
    print("✅ 测试完成! 请检查Telegram是否收到3条消息")


if __name__ == "__main__":
    test_notification()
