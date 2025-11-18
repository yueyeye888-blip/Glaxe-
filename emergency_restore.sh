#!/bin/bash
# 紧急恢复脚本
# 用途: 快速恢复到最新稳定版本

set -e

PROJECT_DIR="/Users/xingxiu/Desktop/Glaxe 项目抓取备份/GalxeMonitor"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚨 紧急恢复 - 恢复到最新稳定版本"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 询问确认
read -p "⚠️  此操作将丢弃所有未提交的修改,确认继续? (y/N): " confirm
if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "❌ 操作已取消"
    exit 0
fi

echo ""
echo "🔄 开始恢复..."

# 进入项目目录
cd "$PROJECT_DIR"

# 停止服务
echo "🛑 停止现有服务..."
lsof -ti:5001 | xargs kill -9 2>/dev/null || true
sleep 2

# 显示当前状态
echo ""
echo "📊 当前状态:"
git status --short

# 丢弃所有本地修改
echo ""
echo "🔄 丢弃本地修改..."
git reset --hard HEAD
git clean -fd

# 拉取最新代码
echo ""
echo "⬇️  拉取最新代码..."
git pull origin main

# 显示当前版本
echo ""
echo "✅ 恢复完成!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
GIT_COMMIT=$(git log -1 --format="%h - %s")
echo "📌 当前版本: $GIT_COMMIT"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 询问是否重启服务
read -p "🚀 是否立即启动服务? (Y/n): " start_service
if [ "$start_service" != "n" ] && [ "$start_service" != "N" ]; then
    echo ""
    echo "🚀 启动服务..."
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
echo "💡 提示:"
echo "   查看日志: tail -f logs/app.log"
echo "   停止服务: lsof -ti:5001 | xargs kill -9"
echo "   查看版本: git log --oneline"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
