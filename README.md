# Galxe Quest Monitor

一个基于 Galxe Open API 的项目任务监控工具，支持实时跟踪任务状态、管理多个项目、以及发送通知推送。

## 功能特性

- 🎯 **实时监控**: 通过 Galxe Open API 实时获取任务数据
- 📊 **现代化界面**: 卡片式布局，展示任务开始/结束时间和活动状态
- 🔧 **项目管理**: 支持单个添加、批量导入、删除项目
- 📢 **消息推送**: 支持 Telegram 和 Discord 通知
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

```json
{
  "webui_port": 5001,
  "webui_password": "your_password",
  "notify_method": "none",
  "telegram_bot_token": "",
  "telegram_chat_id": "",
  "discord_webhook_url": "",
  "projects": [
    {"name": "Project Name", "alias": "alias", "category": "trending"}
  ]
}
```

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

- **添加项目**: 在 Web UI 中输入项目名称和别名
- **查看任务**: 实时显示正在进行的任务卡片
- **设置通知**: 配置 Telegram 或 Discord 推送
- **管理状态**: 自动保存并恢复监控状态

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
