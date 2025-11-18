# 快速使用指南

## 🚀 5分钟快速上手

### 1. 配置Telegram Bot

```bash
# 获取群组Chat ID
python3 get_group_id.py
```

### 2. 配置迁移(如果有旧配置)

```bash
# 自动转换为多目标配置
python3 migrate_config.py
```

### 3. 测试通知

```bash
# 发送3条测试消息
python3 test_notification.py
```

### 4. 启动服务

```bash
# 后台运行
nohup python3 src/app.py > /dev/null 2>&1 &

# 查看日志
tail -f logs/app.log
```

### 5. 访问Web界面

```
http://服务器IP:5001
```

---

## 📋 常用配置模板

### 单群组配置

最简单的配置,推送到一个群组:

```json
{
  "notify_method": "telegram",
  "notify_targets": [
    {
      "name": "主群组",
      "bot_token": "YOUR_BOT_TOKEN",
      "chat_id": "YOUR_CHAT_ID",
      "enabled": true,
      "projects": []
    }
  ]
}
```

### 多群组配置

推送到多个群组(相同Bot):

```json
{
  "notify_method": "telegram",
  "notify_targets": [
    {
      "name": "中文群",
      "bot_token": "BOT_TOKEN",
      "chat_id": "-1001111111111",
      "enabled": true,
      "projects": []
    },
    {
      "name": "English Group",
      "bot_token": "BOT_TOKEN",
      "chat_id": "-1002222222222",
      "enabled": true,
      "projects": []
    }
  ]
}
```

### 分组推送配置

VIP项目推送到VIP群,其他推送到普通群:

```json
{
  "notify_method": "telegram",
  "notify_targets": [
    {
      "name": "VIP群",
      "bot_token": "BOT_TOKEN",
      "chat_id": "-1001111111111",
      "enabled": true,
      "projects": ["bnbchain", "Galxe", "layerzero", "arbitrum"]
    },
    {
      "name": "普通群",
      "bot_token": "BOT_TOKEN",
      "chat_id": "-1002222222222",
      "enabled": true,
      "projects": []
    }
  ]
}
```

> **提示**: VIP群只接收指定项目,普通群接收所有项目(包括VIP项目)

### 多Bot配置

使用不同Bot推送到不同群组:

```json
{
  "notify_method": "telegram",
  "notify_targets": [
    {
      "name": "群组A",
      "bot_token": "BOT1_TOKEN",
      "chat_id": "-1001111111111",
      "enabled": true,
      "projects": []
    },
    {
      "name": "群组B",
      "bot_token": "BOT2_TOKEN",
      "chat_id": "-1002222222222",
      "enabled": true,
      "projects": []
    }
  ]
}
```

### 混合配置

复杂场景:VIP群(Bot1) + 普通群(Bot2) + 测试群(禁用):

```json
{
  "notify_method": "telegram",
  "notify_targets": [
    {
      "name": "VIP群",
      "bot_token": "BOT1_TOKEN",
      "chat_id": "-1001111111111",
      "enabled": true,
      "projects": ["bnbchain", "Galxe"]
    },
    {
      "name": "普通群",
      "bot_token": "BOT2_TOKEN",
      "chat_id": "-1002222222222",
      "enabled": true,
      "projects": []
    },
    {
      "name": "测试群",
      "bot_token": "BOT1_TOKEN",
      "chat_id": "-1003333333333",
      "enabled": false,
      "projects": []
    }
  ]
}
```

---

## 🛠️ 常见问题

### Q: 如何获取Chat ID?

**A**: 运行 `python3 get_group_id.py`,按照提示操作:
1. 将Bot添加到群组
2. 在群组中发送任意消息
3. 脚本自动显示Chat ID

### Q: projects字段如何填写?

**A**: 使用项目的 `alias` 字段,而不是 `name`:
- ✅ 正确: `"projects": ["bnbchain", "Galxe"]`
- ❌ 错误: `"projects": ["BNB Chain", "Galxe Official"]`

### Q: 如何临时禁用某个目标?

**A**: 设置 `"enabled": false`:
```json
{
  "name": "测试群",
  "enabled": false
}
```

### Q: 如何验证配置是否正确?

**A**: 运行测试脚本:
```bash
python3 test_notification.py
```

### Q: 为什么群组收不到消息?

**A**: 检查:
1. Bot是否已加入群组
2. Bot是否有发消息权限
3. Chat ID是否正确(群组ID以 `-100` 开头)
4. `enabled` 是否为 `true`

### Q: 旧配置会失效吗?

**A**: 不会。系统保持向后兼容:
- 如果有 `notify_targets`,优先使用
- 如果没有 `notify_targets`,使用旧的 `telegram_bot_token`/`telegram_chat_id`

### Q: 如何从旧配置迁移?

**A**: 运行迁移工具:
```bash
python3 migrate_config.py
```
会自动备份并转换配置。

---

## 📊 推送规则说明

### 什么情况会推送?

- ✅ **未开始的活动**: 开始时间在未来
- ✅ **进行中的活动**: 当前时间在活动期间内
- ❌ **已结束的活动**: 结束时间已过
- ❌ **远期活动**: 开始时间在60天后
- ❌ **老旧活动**: 开始时间在30天前

### 推送时机

- 首次检测到新活动时推送
- 重启服务后不会重复推送已知活动
- 状态保存在 `data/monitor_state.json`

---

## 📖 进阶文档

- [完整配置说明](docs/notify_targets_config.md)
- [项目结构说明](README.md#项目结构)

---

## 💡 使用技巧

### 技巧1: 分优先级推送

将重点项目推送到多个群组:

```json
"notify_targets": [
  {
    "name": "VIP群",
    "projects": ["bnbchain", "Galxe"]
  },
  {
    "name": "普通群",
    "projects": []
  }
]
```

VIP群只收重点项目,普通群收所有项目。

### 技巧2: 测试新群组

添加新群组时先设置 `enabled: false`,测试成功后再启用:

```json
{
  "name": "新群组",
  "enabled": false
}
```

### 技巧3: 查看推送日志

实时查看推送情况:

```bash
tail -f logs/app.log | grep "Telegram"
```

成功推送:
```
✅ Telegram 通知已发送到 -1002512291367
📤 共推送到 3 个目标
```

### 技巧4: 快速切换Bot

将多个Bot配置好,通过 `enabled` 开关快速切换:

```json
"notify_targets": [
  {
    "name": "Bot1",
    "bot_token": "TOKEN1",
    "enabled": true
  },
  {
    "name": "Bot2-备用",
    "bot_token": "TOKEN2",
    "enabled": false
  }
]
```

---

## 🎯 总结

**最简单的使用方式**:
1. 运行 `python3 migrate_config.py` 迁移配置
2. 运行 `python3 test_notification.py` 测试
3. 启动服务即可

**需要多群组?**
- 在 `notify_targets` 数组中添加新目标即可

**需要分组推送?**
- 在目标中设置 `projects` 数组即可

**更多详情**: [docs/notify_targets_config.md](docs/notify_targets_config.md)
