#!/usr/bin/env bash
set -e

BASE_DIR="/opt/GalxeMonitor"
BACKUP_DIR="$BASE_DIR/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

mkdir -p "$BACKUP_DIR"

echo "📦 正在备份 Galxe 监控程序到: $BACKUP_DIR"

# 备份主程序
if [ -f "$BASE_DIR/combined_app.py" ]; then
  cp "$BASE_DIR/combined_app.py" "$BACKUP_DIR/combined_app.py.$TIMESTAMP.bak"
  echo "✅ combined_app.py -> $BACKUP_DIR/combined_app.py.$TIMESTAMP.bak"
fi

# 备份配置文件
if [ -f "$BASE_DIR/config.json" ]; then
  cp "$BASE_DIR/config.json" "$BACKUP_DIR/config.json.$TIMESTAMP.bak"
  echo "✅ config.json     -> $BACKUP_DIR/config.json.$TIMESTAMP.bak"
fi

# 备份 systemd service 文件（如果存在）
SERVICE_FILE="/etc/systemd/system/galxe-monitor.service"
if [ -f "$SERVICE_FILE" ]; then
  sudo cp "$SERVICE_FILE" "$BACKUP_DIR/galxe-monitor.service.$TIMESTAMP.bak"
  echo "✅ galxe-monitor.service -> $BACKUP_DIR/galxe-monitor.service.$TIMESTAMP.bak"
fi

echo "🎉 备份完成！"
