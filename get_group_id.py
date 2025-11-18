#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
获取Telegram群组的Chat ID
"""

import requests
import json
import os

# 加载配置
config_path = os.path.join(os.path.dirname(__file__), 'config_files', 'config.json')
with open(config_path, 'r', encoding='utf-8') as f:
    cfg = json.load(f)

token = cfg.get('telegram_bot_token')

print("=" * 60)
print("📱 获取Telegram Chat ID")
print("=" * 60)
print()
print("请按以下步骤操作:")
print("1. 将Bot添加到您的群组")
print("2. 在群组中发送任意消息(如 /start 或 hello)")
print("3. 等待几秒后按回车...")
print()
input("按回车继续...")

# 获取更新
url = f"https://api.telegram.org/bot{token}/getUpdates"
response = requests.get(url, timeout=10)

if response.status_code == 200:
    data = response.json()
    
    if data['ok'] and data['result']:
        print("\n✅ 找到以下对话:\n")
        
        chats = {}
        for update in data['result']:
            if 'message' in update:
                chat = update['message']['chat']
                chat_id = chat['id']
                
                if chat_id not in chats:
                    chats[chat_id] = chat
        
        # 显示所有找到的聊天
        for i, (chat_id, chat) in enumerate(chats.items(), 1):
            print(f"[{i}] Chat ID: {chat_id}")
            print(f"    类型: {chat['type']}")
            if 'title' in chat:
                print(f"    群组名: {chat['title']}")
            if 'username' in chat:
                print(f"    用户名: @{chat['username']}")
            if 'first_name' in chat:
                print(f"    名字: {chat['first_name']}")
            print()
        
        # 获取最新的chat_id
        if chats:
            latest_chat_id = list(chats.keys())[-1]
            latest_chat = chats[latest_chat_id]
            
            print("=" * 60)
            print(f"💡 建议使用最新的 Chat ID: {latest_chat_id}")
            if 'title' in latest_chat:
                print(f"   群组名: {latest_chat['title']}")
            print("=" * 60)
            print()
            
            # 询问是否更新配置
            answer = input("是否更新配置文件? (y/n): ").strip().lower()
            if answer == 'y':
                cfg['telegram_chat_id'] = str(latest_chat_id)
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(cfg, f, indent=2, ensure_ascii=False)
                print(f"✅ 配置已更新! Chat ID: {latest_chat_id}")
                print()
                print("现在可以运行测试: python3 test_notification.py")
    else:
        print("⚠️  没有找到任何消息")
        print("请确保:")
        print("1. Bot已被添加到群组")
        print("2. 在群组中发送了至少一条消息")
        print("3. Bot Token正确")
else:
    print(f"❌ 请求失败: {response.status_code}")
    print(response.text)
