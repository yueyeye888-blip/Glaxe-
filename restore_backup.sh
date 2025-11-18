#!/bin/bash
# 恢复指定备份文件
# 用途: 从备份文件中恢复项目

set -e

BACKUP_DIR="$HOME/Desktop/GalxeMonitor_Backups"
RESTORE_DIR="/Users/xingxiu/Desktop"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 恢复备份文件"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 检查备份目录
if [ ! -d "$BACKUP_DIR" ]; then
    echo "❌ 备份目录不存在: $BACKUP_DIR"
    exit 1
fi

# 列出所有备份
echo "📂 可用的备份文件:"
ls -lt "$BACKUP_DIR" | grep "GalxeMonitor_.*\.tar\.gz" | nl -w2 -s". " | awk '{print $1". "$10 " (" $6 " " $7 " " $8 ")"}'

echo ""
read -p "请输入要恢复的备份编号 (或输入完整文件名): " selection

# 确定备份文件
if [[ "$selection" =~ ^[0-9]+$ ]]; then
    # 选择编号
    BACKUP_FILE=$(ls -t "$BACKUP_DIR"/GalxeMonitor_*.tar.gz | sed -n "${selection}p")
else
    # 输入文件名
    BACKUP_FILE="$BACKUP_DIR/$selection"
fi

# 检查文件是否存在
if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ 备份文件不存在: $BACKUP_FILE"
    exit 1
fi

echo ""
echo "📦 选择的备份: $(basename $BACKUP_FILE)"
echo ""
read -p "⚠️  确认恢复此备份? 当前项目将被覆盖! (y/N): " confirm

if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "❌ 操作已取消"
    exit 0
fi

echo ""
echo "🔄 开始恢复..."

# 停止服务
echo "🛑 停止现有服务..."
lsof -ti:5001 | xargs kill -9 2>/dev/null || true
sleep 2

# 备份当前版本
CURRENT_BACKUP="$BACKUP_DIR/before_restore_$(date +%Y%m%d_%H%M%S).tar.gz"
if [ -d "/Users/xingxiu/Desktop/Glaxe 项目抓取备份/GalxeMonitor" ]; then
    echo "💾 备份当前版本..."
    cd "/Users/xingxiu/Desktop/Glaxe 项目抓取备份"
    tar -czf "$CURRENT_BACKUP" \
        --exclude='GalxeMonitor/__pycache__' \
        --exclude='GalxeMonitor/logs' \
        --exclude='GalxeMonitor/.git' \
        GalxeMonitor/ 2>/dev/null || true
    echo "✅ 当前版本已备份: $(basename $CURRENT_BACKUP)"
fi

# 删除旧项目
echo "🗑️  删除旧项目..."
rm -rf "/Users/xingxiu/Desktop/Glaxe 项目抓取备份/GalxeMonitor"

# 解压备份
echo "📦 解压备份文件..."
cd "$RESTORE_DIR"
tar -xzf "$BACKUP_FILE"

# 重命名目录
if [ -d "GalxeMonitor" ]; then
    mkdir -p "Glaxe 项目抓取备份"
    mv GalxeMonitor "Glaxe 项目抓取备份/"
fi

echo ""
echo "✅ 恢复完成!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📁 项目位置: /Users/xingxiu/Desktop/Glaxe 项目抓取备份/GalxeMonitor"
echo "💾 当前版本备份: $(basename $CURRENT_BACKUP)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 询问是否启动服务
read -p "🚀 是否立即启动服务? (Y/n): " start_service
if [ "$start_service" != "n" ] && [ "$start_service" != "N" ]; then
    echo ""
    echo "🚀 启动服务..."
    cd "/Users/xingxiu/Desktop/Glaxe 项目抓取备份/GalxeMonitor"
    nohup python3 src/app.py > /dev/null 2>&1 &
    sleep 3
    
    if lsof -ti:5001 > /dev/null 2>&1; then
        echo "✅ 服务启动成功! (端口: 5001)"
        echo "🌐 访问: http://localhost:5001/?pwd=admin"
    else
        echo "❌ 服务启动失败,请检查日志:"
        echo "   tail -f logs/app.log"
    fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
