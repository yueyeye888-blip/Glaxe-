# 多Bot多群组配置说明

## 功能介绍

新版本支持配置多个Telegram Bot和多个群组,实现灵活的通知分发策略:

- 同一消息推送到多个群组
- 不同项目推送到不同群组
- 使用多个Bot账号分散请求
- 每个目标独立开关控制

## 配置结构

### 新格式(推荐)

在 `config.json` 中添加 `notify_targets` 数组:

```json
{
  "notify_method": "telegram",
  "notify_targets": [
    {
      "name": "主群组",
      "bot_token": "8331180504:AAFU-JyITKlfH7mvqrz5tspcvS2VTseW0yI",
      "chat_id": "-1002512291367",
      "enabled": true,
      "projects": []
    },
    {
      "name": "测试群",
      "bot_token": "另一个Bot的Token",
      "chat_id": "-1234567890",
      "enabled": true,
      "projects": ["bnbchain", "Galxe"]
    },
    {
      "name": "备用Bot",
      "bot_token": "备用Bot的Token",
      "chat_id": "-1002512291367",
      "enabled": false,
      "projects": []
    }
  ],
  "projects": [...]
}
```

### 旧格式(向后兼容)

如果没有配置 `notify_targets`,系统会使用旧的单一配置:

```json
{
  "notify_method": "telegram",
  "telegram_bot_token": "8331180504:AAFU-JyITKlfH7mvqrz5tspcvS2VTseW0yI",
  "telegram_chat_id": "-1002512291367",
  "projects": [...]
}
```

## 字段说明

### notify_targets 数组

每个目标对象包含以下字段:

| 字段 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| `name` | string | 否 | 目标名称(仅用于识别) |
| `bot_token` | string | **是** | Telegram Bot API Token |
| `chat_id` | string | **是** | 群组/频道/私聊的Chat ID |
| `enabled` | boolean | 否 | 是否启用(默认true) |
| `projects` | array | 否 | 项目白名单,为空则推送所有项目 |

### projects 过滤规则

- **空数组 `[]`**: 推送所有项目
- **指定项目**: 只推送列表中的项目(使用项目alias匹配)
- 示例:
  ```json
  "projects": ["bnbchain", "Galxe", "layerzero"]
  ```

## 使用场景

### 场景1: 推送到多个群组

所有项目同时推送到多个群组:

```json
"notify_targets": [
  {
    "name": "中文群",
    "bot_token": "Bot1Token",
    "chat_id": "-1001234567890",
    "enabled": true,
    "projects": []
  },
  {
    "name": "English Group",
    "bot_token": "Bot1Token",
    "chat_id": "-1009876543210",
    "enabled": true,
    "projects": []
  }
]
```

### 场景2: 不同项目推送到不同群组

重点项目推送到VIP群,其他推送到普通群:

```json
"notify_targets": [
  {
    "name": "VIP群",
    "bot_token": "Bot1Token",
    "chat_id": "-1001111111111",
    "enabled": true,
    "projects": ["bnbchain", "Galxe", "layerzero"]
  },
  {
    "name": "普通群",
    "bot_token": "Bot1Token",
    "chat_id": "-1002222222222",
    "enabled": true,
    "projects": []
  }
]
```

### 场景3: 使用多个Bot分散请求

避免单个Bot请求过多:

```json
"notify_targets": [
  {
    "name": "群组A",
    "bot_token": "Bot1Token",
    "chat_id": "-1001111111111",
    "enabled": true
  },
  {
    "name": "群组B",
    "bot_token": "Bot2Token",
    "chat_id": "-1002222222222",
    "enabled": true
  }
]
```

### 场景4: 灵活开关控制

临时禁用某个目标:

```json
"notify_targets": [
  {
    "name": "主群",
    "bot_token": "BotToken",
    "chat_id": "-1001234567890",
    "enabled": true
  },
  {
    "name": "测试群",
    "bot_token": "BotToken",
    "chat_id": "-1009876543210",
    "enabled": false
  }
]
```

## 获取Chat ID

### 方法1: 使用自动脚本(推荐)

```bash
python3 get_group_id.py
```

按照提示操作:
1. 将Bot添加到群组
2. 在群组中发送任意消息
3. 脚本会自动显示所有可用的Chat ID

### 方法2: 手动获取

1. 将Bot添加到群组
2. 在群组中发送消息: `/start` 或 任意文字
3. 访问: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. 找到 `"chat":{"id":-1234567890}` 字段

## 测试通知

### 方法1: 使用测试脚本

```bash
python3 test_notification.py
```

会发送3条测试消息验证配置是否正确。

### 方法2: Web界面测试

访问管理页面: `http://服务器IP:5001/manage?pwd=YOUR_PASSWORD`

点击"发送测试通知"按钮。

## 日志查看

所有推送记录会写入日志:

```bash
tail -f logs/app.log
```

成功推送:
```
✅ Telegram 通知已发送到 -1002512291367
📤 共推送到 3 个目标
```

失败信息:
```
❌ Telegram 推送失败 [400]: Bad Request: chat not found
   Chat ID: -1001234567890
```

## 注意事项

1. **Bot权限**: 确保Bot已加入目标群组且有发消息权限
2. **Chat ID格式**: 群组ID以 `-100` 开头,如 `-1002512291367`
3. **Token安全**: 不要将Token提交到公开代码仓库
4. **请求限制**: Telegram API限制为每秒30条消息
5. **项目别名**: `projects` 字段使用的是项目的 `alias` (如 "bnbchain"),不是项目名称

## 配置示例

完整配置文件示例:

```json
{
  "notify_method": "telegram",
  "notify_targets": [
    {
      "name": "测试1群组",
      "bot_token": "8331180504:AAFU-JyITKlfH7mvqrz5tspcvS2VTseW0yI",
      "chat_id": "-1002512291367",
      "enabled": true,
      "projects": []
    }
  ],
  "projects": [
    {
      "alias": "bnbchain",
      "enabled": true
    }
  ]
}
```

## 迁移指南

### 从旧配置迁移

1. 保留原有的 `telegram_bot_token` 和 `telegram_chat_id` (向后兼容)
2. 添加新的 `notify_targets` 配置
3. 系统会优先使用 `notify_targets`,如果为空则使用旧配置
4. 测试无误后,可以删除旧字段

### 示例迁移

旧配置:
```json
{
  "telegram_bot_token": "123456:ABC",
  "telegram_chat_id": "-1001234567890"
}
```

新配置:
```json
{
  "notify_targets": [
    {
      "name": "主群",
      "bot_token": "123456:ABC",
      "chat_id": "-1001234567890",
      "enabled": true,
      "projects": []
    }
  ]
}
```
