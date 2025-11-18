#!/bin/bash
# 一键备份脚本
# 用途: 备份完整的项目代码和配置文件

set -e

BACKUP_DIR="$HOME/Desktop/GalxeMonitor_Backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="GalxeMonitor_${TIMESTAMP}"
PROJECT_DIR="/Users/xingxiu/Desktop/Glaxe 项目抓取备份/GalxeMonitor"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 开始备份 GalxeMonitor 项目"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 创建备份目录
mkdir -p "$BACKUP_DIR"

# 进入项目目录
cd "$PROJECT_DIR"

# 获取当前Git版本
GIT_COMMIT=$(git log -1 --format="%h - %s" 2>/dev/null || echo "未知版本")
echo "📌 当前版本: $GIT_COMMIT"

# 创建临时目录
TEMP_DIR=$(mktemp -d)
cp -r "$PROJECT_DIR" "$TEMP_DIR/GalxeMonitor"

# 压缩备份(排除不必要的文件)
cd "$TEMP_DIR"
tar -czf "$BACKUP_DIR/${BACKUP_NAME}.tar.gz" \
    --exclude='GalxeMonitor/__pycache__' \
    --exclude='GalxeMonitor/**/__pycache__' \
    --exclude='GalxeMonitor/logs/*.log' \
    --exclude='GalxeMonitor/.git' \
    --exclude='GalxeMonitor/venv' \
    --exclude='GalxeMonitor/nohup.out' \
    GalxeMonitor/

# 清理临时目录
rm -rf "$TEMP_DIR"

# 获取备份大小
BACKUP_SIZE=$(du -h "$BACKUP_DIR/${BACKUP_NAME}.tar.gz" | cut -f1)

echo ""
echo "✅ 备份完成!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📁 备份位置: $BACKUP_DIR"
echo "📦 文件名称: ${BACKUP_NAME}.tar.gz"
echo "📏 文件大小: $BACKUP_SIZE"
echo "📌 Git版本: $GIT_COMMIT"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "💡 提示:"
echo "   恢复备份: tar -xzf $BACKUP_DIR/${BACKUP_NAME}.tar.gz"
echo "   查看备份: ls -lh $BACKUP_DIR"
echo ""

# 列出最近5个备份
echo "📂 最近的备份文件:"
ls -lt "$BACKUP_DIR" | grep "GalxeMonitor_" | head -5 | awk '{print "   " $9 " (" $5 ")"}'
echo ""

# 清理超过10个的旧备份
BACKUP_COUNT=$(ls -1 "$BACKUP_DIR" | grep "GalxeMonitor_" | wc -l)
if [ $BACKUP_COUNT -gt 10 ]; then
    echo "🧹 清理旧备份(保留最新10个)..."
    ls -t "$BACKUP_DIR"/GalxeMonitor_*.tar.gz | tail -n +11 | xargs rm -f
    echo "✅ 清理完成"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
