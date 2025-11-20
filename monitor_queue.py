#!/usr/bin/env python3
"""
GalxeMonitor 推送队列系统 - 实时监控脚本
用于观察队列变化、推送动作等
"""

import paramiko
import time
import json
from datetime import datetime

class MonitorViewer:
    def __init__(self, host, username, password):
        self.host = host
        self.username = username
        self.password = password
        self.ssh = None
        self.last_queue_size = 0
        self.last_log_pos = 0
        
    def connect(self):
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(self.host, username=self.username, password=self.password)
        print("✅ 已连接到服务器")
        
    def disconnect(self):
        if self.ssh:
            self.ssh.close()
            
    def get_queue_size(self):
        """获取当前队列大小"""
        stdin, stdout, stderr = self.ssh.exec_command(
            'wc -l /root/GalxeMonitor/data/push_queue.json 2>/dev/null | awk "{print $1}" || echo "0"'
        )
        try:
            return int(stdout.read().decode().strip())
        except:
            return 0
            
    def get_process_info(self):
        """获取进程信息"""
        stdin, stdout, stderr = self.ssh.exec_command(
            'ps aux | grep "python3 src/app.py" | grep -v grep | awk "{print \\"PID:\\", $2, \\"Memory:\\", $6\\" KB\\"}" || echo "❌ 未运行"'
        )
        return stdout.read().decode().strip()
        
    def get_recent_logs(self, lines=20):
        """获取最新日志"""
        stdin, stdout, stderr = self.ssh.exec_command(
            f'tail -{lines} /root/GalxeMonitor/logs/app.log 2>/dev/null'
        )
        return stdout.read().decode()
        
    def display_status(self):
        """显示当前状态"""
        print(f"\n{'='*70}")
        print(f"🔍 监控时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}")
        
        # 进程状态
        print(f"\n📊 进程状态:")
        print(f"  {self.get_process_info()}")
        
        # 队列大小
        queue_size = self.get_queue_size()
        trend = "📈" if queue_size > self.last_queue_size else ("📉" if queue_size < self.last_queue_size else "➡️")
        print(f"\n📋 队列大小: {queue_size} 行 {trend}")
        if self.last_queue_size > 0:
            change = queue_size - self.last_queue_size
            print(f"  变化: {change:+d} (相比上次)")
        self.last_queue_size = queue_size
        
        # 服务器资源
        stdin, stdout, stderr = self.ssh.exec_command(
            'free -h | grep Mem | awk "{printf \\"  内存: %s/%s (%.1f%%) \\\\n\\", $3, $2, ($3/$2)*100}"'
        )
        print(f"\n💾 服务器资源:")
        print(f"{stdout.read().decode().strip()}")
        
        # 最新日志
        print(f"\n📝 最近日志 (最后10行):")
        logs = self.get_recent_logs(10)
        if logs:
            for line in logs.strip().split('\n')[-10:]:
                if line.strip():
                    # 只显示包含关键信息的行
                    if any(kw in line for kw in ['推送', '队列', '启动', 'ERROR', '📌', '📤']):
                        # 截断长行
                        line = line[:85]
                        print(f"  {line}")
        
        print(f"\n{'='*70}\n")
        
    def continuous_monitor(self, interval=60):
        """持续监控"""
        print(f"🚀 开始实时监控 (每 {interval} 秒更新一次)")
        print("按 Ctrl+C 停止...\n")
        
        try:
            while True:
                self.display_status()
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n❌ 监控已停止")
            
    def quick_check(self):
        """快速检查"""
        print("\n⚡ 快速检查")
        print(f"{'='*70}")
        
        # 1. 进程
        stdin, stdout, stderr = self.ssh.exec_command('ps aux | grep "python3 src/app.py" | grep -v grep | wc -l')
        running = int(stdout.read().decode().strip())
        print(f"1. 进程运行中: {'✅ 是' if running > 0 else '❌ 否'}")
        
        # 2. 队列文件
        stdin, stdout, stderr = self.ssh.exec_command('test -f /root/GalxeMonitor/data/push_queue.json && echo "1" || echo "0"')
        exists = int(stdout.read().decode().strip())
        print(f"2. 队列文件存在: {'✅ 是' if exists else '❌ 否'}")
        
        # 3. 日志文件
        stdin, stdout, stderr = self.ssh.exec_command('test -f /root/GalxeMonitor/logs/app.log && echo "1" || echo "0"')
        log_exists = int(stdout.read().decode().strip())
        print(f"3. 日志文件存在: {'✅ 是' if log_exists else '❌ 否'}")
        
        # 4. 队列处理器
        stdin, stdout, stderr = self.ssh.exec_command('grep "推送队列处理器已启动" /root/GalxeMonitor/logs/app.log | wc -l')
        startup = int(stdout.read().decode().strip())
        print(f"4. 队列处理器启动过: {'✅ 是' if startup > 0 else '❌ 否'}")
        
        # 5. 当前队列大小
        queue_size = self.get_queue_size()
        print(f"5. 当前队列大小: {queue_size} 行")
        
        print(f"{'='*70}\n")
        
        return all([running, exists, log_exists, startup])

def main():
    import sys
    
    # 配置
    HOST = '47.76.90.4'
    USERNAME = 'root'
    PASSWORD = 'Yry20021002.'
    
    viewer = MonitorViewer(HOST, USERNAME, PASSWORD)
    
    try:
        viewer.connect()
        
        if len(sys.argv) > 1 and sys.argv[1] == 'quick':
            # 快速检查模式
            viewer.quick_check()
        else:
            # 连续监控模式
            viewer.continuous_monitor(interval=60)
            
    finally:
        viewer.disconnect()

if __name__ == '__main__':
    main()
