#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试Telegram通知功能
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from app import send_telegram, build_notify_text, load_config
from datetime import datetime, timedelta

def test_notification(chat_id=None):
    """发送测试通知"""
    cfg = load_config()
    
    # 如果提供了chat_id则更新配置
    if chat_id:
        cfg['telegram_chat_id'] = chat_id
        print(f"📝 使用 Chat ID: {chat_id}")
    
    # 模拟3种不同状态的活动
    test_cases = [
        {
            "name": "测试项目 - 未开始",
            "alias": "test-upcoming",
            "latest": {
                "name": "春季任务大礼包",
                "startTime": str(int((datetime.now() + timedelta(days=1)).timestamp() * 1000)),
                "endTime": str(int((datetime.now() + timedelta(days=30)).timestamp() * 1000)),
            },
            "url": "https://app.galxe.com/quest/test/GC123"
        },
        {
            "name": "测试项目 - 进行中",
            "alias": "test-ongoing",
            "latest": {
                "name": "每日签到任务",
                "startTime": str(int((datetime.now() - timedelta(days=1)).timestamp() * 1000)),
                "endTime": str(int((datetime.now() + timedelta(days=15)).timestamp() * 1000)),
            },
            "url": "https://app.galxe.com/quest/test/GC456"
        },
        {
            "name": "测试项目 - 即将结束",
            "alias": "test-ending",
            "latest": {
                "name": "限时冲刺活动",
                "startTime": str(int((datetime.now() - timedelta(days=10)).timestamp() * 1000)),
                "endTime": str(int((datetime.now() + timedelta(days=2)).timestamp() * 1000)),
            },
            "url": "https://app.galxe.com/quest/test/GC789"
        }
    ]
    
    print("=" * 60)
    print("📤 开始发送测试通知...")
    print("=" * 60)
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n[{i}/3] 发送: {test['name']}")
        text = build_notify_text(test['name'], test['alias'], test['latest'], test['url'])
        send_telegram(cfg, text)
        print("✅ 已发送")
    
    print("\n" + "=" * 60)
    print("✅ 测试完成! 请检查Telegram是否收到3条消息")
    print("=" * 60)


if __name__ == "__main__":
    # 如果提供了参数,则使用参数作为chat_id
    chat_id = sys.argv[1] if len(sys.argv) > 1 else None
    test_notification(chat_id)
