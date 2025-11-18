# Galxe Quest Monitor

一个基于 Galxe Open API 的项目任务监控工具,支持实时跟踪任务状态、管理多个项目、以及多渠道通知推送。

📚 **[快速使用指南](docs/QUICK_START.md)** | 📖 **[多Bot多群组配置](docs/notify_targets_config.md)**

## 功能特性

- 🎯 **实时监控**: 通过 Galxe Open API 实时获取任务数据
- 📊 **现代化界面**: 卡片式布局,展示任务开始/结束时间和活动状态
- 🔧 **项目管理**: 支持单个添加、批量导入、删除项目
- 📢 **多渠道推送**: 支持 Telegram 和 Discord 通知
- 🤖 **多Bot多群组**: 支持配置多个Telegram Bot和多个群组
- 🎛️ **灵活过滤**: 可按项目分配不同的通知目标
- 💾 **数据持久化**: 自动保存配置和监控状态

## 项目结构

```
GalxeMonitor/
├── src/                      # 源代码
│   ├── app.py               # 主应用程序（Flask）
│   ├── galxe_crawler.py     # Galxe 爬虫模块
│   └── utils/               # 工具函数
├── config_files/            # 配置文件
│   └── config.json          # 应用配置
├── static/                  # 静态资源（CSS、JS）
├── templates/               # HTML 模板
├── data/                    # 数据存储
│   └── monitor_state.json   # 监控状态
├── logs/                    # 日志文件
├── tests/                   # 测试文件
├── docs/                    # 文档
├── requirements.txt         # Python 依赖
├── .gitignore              # Git 忽略规则
└── README.md               # 本文件
```

## 快速开始

### 前置要求

- Python 3.6+
- pip

### 安装

1. 克隆项目
```bash
git clone git@github.com:yourusername/Glaxe-.git
cd Glaxe-
```

2. 创建虚拟环境
```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# 或
venv\Scripts\activate     # Windows
```

3. 安装依赖
```bash
pip install -r requirements.txt
```

### 配置

编辑 `config_files/config.json`：

### 配置示例

#### 基础配置

```json
{
  "webui_port": 5001,
  "webui_password": "your_password",
  "notify_method": "telegram",
  "telegram_bot_token": "YOUR_BOT_TOKEN",
  "telegram_chat_id": "YOUR_CHAT_ID",
  "discord_webhook_url": "",
  "projects": [
    {"name": "Project Name", "alias": "alias", "category": "trending"}
  ]
}
```

#### 多Bot多群组配置(推荐)

```json
{
  "webui_port": 5001,
  "webui_password": "your_password",
  "notify_method": "telegram",
  "notify_targets": [
    {
      "name": "主群组",
      "bot_token": "BOT_TOKEN_1",
      "chat_id": "-1001234567890",
      "enabled": true,
      "projects": []
    },
    {
      "name": "VIP群",
      "bot_token": "BOT_TOKEN_2",
      "chat_id": "-1009876543210",
      "enabled": true,
      "projects": ["bnbchain", "Galxe"]
    }
  ],
  "projects": [
    {"name": "Project Name", "alias": "alias", "category": "trending"}
  ]
}
```

📖 **详细配置说明**: [docs/notify_targets_config.md](docs/notify_targets_config.md)

### 配置迁移

如果你已有旧的单一Bot配置,可以使用迁移工具快速转换:

```bash
python3 migrate_config.py
```

这会自动:
- 备份原配置
- 生成notify_targets配置
- 保留旧配置作为兼容

### 运行

```bash
python src/app.py
```

访问 `http://localhost:5001` 打开 Web 界面。

## API 配置

### 环境变量

创建 `.env` 文件（可选）：

```
FLASK_ENV=development
GALXE_API_URL=https://graphigo.prd.galaxy.eco/query
```

## 使用说明

### 基础功能

- **添加项目**: 在 Web UI 中输入项目名称和别名
- **查看任务**: 实时显示正在进行的任务卡片
- **设置通知**: 配置 Telegram 或 Discord 推送
- **管理状态**: 自动保存并恢复监控状态

### Telegram配置

#### 1. 获取Bot Token

1. 在Telegram中搜索 @BotFather
2. 发送 `/newbot` 创建新Bot
3. 获取Bot Token(格式: `123456:ABC-DEF...`)

#### 2. 获取Chat ID

**方法1: 使用自动脚本(推荐)**

```bash
python3 get_group_id.py
```

按照提示:
1. 将Bot添加到群组
2. 在群组中发送任意消息
3. 脚本自动显示所有Chat ID

**方法2: 手动获取**

1. 将Bot添加到群组
2. 在群组发送消息
3. 访问: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. 找到 `"chat":{"id":-1234567890}` 字段

#### 3. 测试通知

```bash
python3 test_notification.py
```

发送3条测试消息验证配置。

### 多Bot多群组使用场景

#### 场景1: 推送到多个群组

所有项目同时推送到中文群和英文群:

```json
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
```

#### 场景2: 按项目分组推送

重点项目推送到VIP群,其他推送到普通群:

```json
"notify_targets": [
  {
    "name": "VIP群",
    "bot_token": "BOT_TOKEN",
    "chat_id": "-1001111111111",
    "enabled": true,
    "projects": ["bnbchain", "Galxe", "layerzero"]
  },
  {
    "name": "普通群",
    "bot_token": "BOT_TOKEN",
    "chat_id": "-1002222222222",
    "enabled": true,
    "projects": []
  }
]
```

#### 场景3: 使用多个Bot

避免单个Bot请求限制:

```json
"notify_targets": [
  {
    "name": "群组A",
    "bot_token": "BOT1_TOKEN",
    "chat_id": "-1001111111111",
    "enabled": true
  },
  {
    "name": "群组B",
    "bot_token": "BOT2_TOKEN",
    "chat_id": "-1002222222222",
    "enabled": true
  }
]
```

### 工具脚本

| 脚本 | 用途 |
|------|------|
| `test_notification.py` | 测试Telegram通知 |
| `get_group_id.py` | 获取群组Chat ID |
| `migrate_config.py` | 配置迁移工具 |

## 开发

### 代码风格

遵循 PEP 8 标准。安装 linter：

```bash
pip install flake8
flake8 src/
```

### 运行测试

```bash
python -m pytest tests/
```

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

## 联系方式

如有问题，请通过 GitHub Issues 联系。
