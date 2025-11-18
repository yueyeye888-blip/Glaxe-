#!/bin/bash
# NTX Quest Radar 一键部署脚本（适用于阿里云/Ubuntu/Debian）

set -e

echo "=== NTX Quest Radar 部署脚本 ==="
echo ""

# 检测系统
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
else
    echo "无法检测操作系统"
    exit 1
fi

echo "检测到系统: $OS"

# 1. 安装 Python 3.8+
echo ""
echo "[1/7] 检查 Python 环境..."
if ! command -v python3 &> /dev/null; then
    echo "正在安装 Python3..."
    if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
        sudo apt update
        sudo apt install -y python3 python3-pip python3-venv
    elif [ "$OS" = "centos" ] || [ "$OS" = "rhel" ]; then
        sudo yum install -y python3 python3-pip
    fi
fi

python3 --version

# 2. 创建虚拟环境
echo ""
echo "[2/7] 创建 Python 虚拟环境..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate

# 3. 安装依赖
echo ""
echo "[3/7] 安装 Python 依赖包..."
pip install -r requirements.txt

# 4. 创建必要目录
echo ""
echo "[4/7] 创建目录结构..."
mkdir -p logs
mkdir -p data
mkdir -p config_files

# 5. 初始化配置文件
echo ""
echo "[5/7] 初始化配置..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "已创建 .env 文件，请编辑填入真实配置"
fi

if [ ! -f "config_files/config.json" ]; then
    echo "首次运行将自动生成 config.json"
fi

# 6. 创建 systemd 服务
echo ""
echo "[6/7] 配置 systemd 服务..."

SERVICE_FILE="/etc/systemd/system/galxe-monitor.service"
WORK_DIR=$(pwd)
USER=$(whoami)

sudo tee $SERVICE_FILE > /dev/null <<EOF
[Unit]
Description=NTX Quest Radar - Galxe Monitor Service
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$WORK_DIR
Environment="PATH=$WORK_DIR/venv/bin"
ExecStart=$WORK_DIR/venv/bin/python src/app_clean.py
Restart=always
RestartSec=10
StandardOutput=append:$WORK_DIR/logs/service.log
StandardError=append:$WORK_DIR/logs/service_error.log

[Install]
WantedBy=multi-user.target
EOF

echo "systemd 服务文件已创建: $SERVICE_FILE"

# 7. 启动服务
echo ""
echo "[7/7] 启动服务..."
sudo systemctl daemon-reload
sudo systemctl enable galxe-monitor
sudo systemctl start galxe-monitor

echo ""
echo "=== 部署完成！ ==="
echo ""
echo "服务状态: sudo systemctl status galxe-monitor"
echo "查看日志: sudo journalctl -u galxe-monitor -f"
echo "停止服务: sudo systemctl stop galxe-monitor"
echo "重启服务: sudo systemctl restart galxe-monitor"
echo ""
echo "请编辑 .env 文件填入真实配置，然后重启服务："
echo "  nano .env"
echo "  sudo systemctl restart galxe-monitor"
echo ""
echo "默认访问地址: http://localhost:5001/?pwd=admin"
echo "（强烈建议修改默认密码！）"
