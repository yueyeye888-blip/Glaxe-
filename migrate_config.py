#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置迁移工具: 从旧的单一配置转换为多目标配置
"""

import json
from pathlib import Path


def migrate_config():
    """将旧的单一Bot配置转换为notify_targets格式"""
    config_path = Path(__file__).parent / "config_files" / "config.json"
    
    if not config_path.exists():
        print("❌ 配置文件不存在:", config_path)
        return
    
    print(f"📂 读取配置: {config_path}")
    with open(config_path, 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    
    # 检查是否已有notify_targets
    if "notify_targets" in cfg:
        print("ℹ️  配置中已存在 notify_targets,无需迁移")
        print(f"   当前有 {len(cfg['notify_targets'])} 个目标")
        
        for i, target in enumerate(cfg["notify_targets"], 1):
            name = target.get("name", f"目标{i}")
            enabled = target.get("enabled", True)
            chat_id = target.get("chat_id", "")
            projects = target.get("projects", [])
            status = "✅" if enabled else "❌"
            
            print(f"   {status} [{i}] {name} -> {chat_id}")
            if projects:
                print(f"        项目过滤: {', '.join(projects)}")
        return
    
    # 获取旧配置
    token = cfg.get("telegram_bot_token", "")
    chat_id = cfg.get("telegram_chat_id", "")
    
    if not token or not chat_id:
        print("❌ 未找到telegram_bot_token或telegram_chat_id,无法迁移")
        return
    
    print("\n📋 当前配置:")
    print(f"   Bot Token: {token[:20]}...")
    print(f"   Chat ID: {chat_id}")
    
    # 创建新的notify_targets配置
    notify_targets = [
        {
            "name": "默认目标",
            "bot_token": token,
            "chat_id": chat_id,
            "enabled": True,
            "projects": []
        }
    ]
    
    # 备份原配置
    backup_path = config_path.with_suffix('.json.backup')
    print(f"\n💾 备份原配置到: {backup_path}")
    with open(backup_path, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    
    # 添加新配置
    cfg["notify_targets"] = notify_targets
    
    # 保存新配置
    print(f"💾 保存新配置...")
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    
    print("\n✅ 迁移完成!")
    print("=" * 60)
    print("新配置已生成,包含以下notify_targets:")
    print(f"  ✅ [1] 默认目标 -> {chat_id}")
    print(f"       项目过滤: 全部")
    print("=" * 60)
    print("\n💡 提示:")
    print("   1. 旧配置已备份,可以随时恢复")
    print("   2. notify_method保持不变")
    print("   3. 旧的telegram_bot_token/telegram_chat_id保留作为兼容")
    print("   4. 可以在notify_targets中添加更多目标")
    print("\n📖 详细说明请查看: docs/notify_targets_config.md")


if __name__ == "__main__":
    migrate_config()
