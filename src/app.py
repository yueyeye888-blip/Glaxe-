#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
NTX Quest Radar V4.0 - 优化版
基于 Galxe Open API 的项目任务监控工具
"""

import json
import os
import threading
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List

import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# =============== 初始化日志系统 ===============

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(__file__), '../logs/app.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# =============== 加载环境变量 ===============

load_dotenv()

# =============== 路径配置 ===============

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config_files", "config.json")
STATE_PATH = os.path.join(ROOT, "data", "monitor_state.json")
LOGS_DIR = os.path.join(ROOT, "logs")
OPENAPI_URL = "https://graphigo.prd.galaxy.eco/query"

# 创建必要的目录
os.makedirs(os.path.join(ROOT, "config_files"), exist_ok=True)
os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

# =============== 全局状态 ===============

monitor_state = {"last_loop": "", "projects": []}
last_notified = {}  # alias -> last campaign id

# =============== 配置管理 ===============

def load_state():
    """加载监控状态"""
    try:
        if os.path.exists(STATE_PATH):
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"加载状态失败: {e}")
    return {"last_loop": "", "projects": []}

def ensure_config():
    """确保配置文件存在，不存在则创建默认配置"""
    if not os.path.exists(CONFIG_PATH):
        cfg = {
            "webui_port": 5001,
            "webui_password": os.getenv("WEBUI_PASSWORD", "admin"),
            "notify_method": "none",
            "telegram_bot_token": "",
            "telegram_chat_id": "",
            "discord_webhook_url": "",
            "projects": [
                {"name": "BNB Chain", "alias": "bnbchain", "category": "trending"},
                {"name": "Galxe Official", "alias": "Galxe", "category": "trending"},
                {"name": "OKX Web3", "alias": "okxweb3", "category": "trending"},
            ],
        }
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        logger.info(f"已创建默认配置文件: {CONFIG_PATH}")


def load_config() -> dict:
    """加载配置文件"""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"加载配置失败: {e}")
        return {}


def save_config(cfg: dict):
    """保存配置文件"""
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        logger.info("配置已保存")
    except Exception as e:
        logger.error(f"保存配置失败: {e}")


def write_state(state: dict):
    """写入监控状态"""
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"写入状态文件失败: {e}")


def load_initial_state() -> dict:
    """启动时加载监控状态"""
    try:
        if os.path.exists(STATE_PATH):
            with open(STATE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"加载状态文件失败: {e}")
    
    # 如果状态文件不存在,从配置文件生成初始状态
    logger.info("状态文件不存在,从配置文件生成初始状态")
    cfg = load_config()
    projects = []
    for p in cfg.get("projects", []):
        projects.append({
            "name": p.get("name", p.get("alias")),
            "alias": p.get("alias"),
            "category": p.get("category", "custom"),
            "latest": None,
            "url": "#"
        })
    return {"last_loop": "等待首次监控循环...", "projects": projects}


# =============== OpenAPI 查询 ===============

QUERY_LATEST_SAFE = """
query LatestSafe($alias:String!){
  space(alias:$alias){
    id
    name
    alias
    campaigns(input:{}){
      list{
        id
        name
        createdAt
        startTime
        endTime
      }
    }
  }
}
"""


def fetch_latest(alias: str) -> Optional[Dict]:
    """从 Galxe Open API 获取最新活动"""
    try:
        r = requests.post(
            OPENAPI_URL,
            json={"query": QUERY_LATEST_SAFE, "variables": {"alias": alias}},
            timeout=15,
        )
        data = r.json()
        
        if "errors" in data:
            logger.error(f"OpenAPI 错误 [{alias}]: {data['errors']}")
            return None

        space = data.get("data", {}).get("space")
        if not space:
            logger.warning(f"Space 不存在: {alias}")
            return None

        lst = space.get("campaigns", {}).get("list", [])
        latest = lst[0] if lst else None
        return {"space": space, "latest": latest}
        
    except Exception as e:
        logger.error(f"请求失败 [{alias}]: {e}")
        return None


def extract_campaign_id(latest: Optional[Dict]) -> Optional[str]:
    """提取活动 ID"""
    if not latest:
        return None
    
    for key in ("id", "campaignId", "campaignID", "hashId", "slug"):
        if isinstance(latest, dict):
            val = latest.get(key)
        else:
            val = getattr(latest, key, None)
        if val:
            return str(val)
    return None


def build_campaign_url(alias: str, latest: Optional[Dict]) -> Optional[str]:
    """构建活动链接"""
    if not alias or not latest:
        return None
    cid = extract_campaign_id(latest)
    if not cid:
        return None
    return f"https://app.galxe.com/quest/{alias}/{cid}"


# =============== 时间处理 ===============

def parse_timestamp(t) -> Optional[datetime]:
    """统一解析时间戳/ISO 字符串为 UTC datetime"""
    if not t:
        return None
    
    if isinstance(t, datetime):
        if t.tzinfo is None:
            return t.replace(tzinfo=timezone.utc)
        return t.astimezone(timezone.utc)
    
    try:
        # 数字时间戳
        if isinstance(t, (int, float)):
            ts = float(t)
        elif isinstance(t, str):
            s = t.strip()
            if s.isdigit():
                ts = float(s)
            else:
                # ISO 字符串
                if s.endswith("Z"):
                    s = s.replace("Z", "+00:00")
                dt = datetime.fromisoformat(s)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
        else:
            return None
        
        # 处理毫秒级时间戳
        if ts > 1e12:
            ts = ts / 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc)
        
    except Exception as e:
        logger.debug(f"时间解析失败: {t} - {e}")
        return None


def format_time(t) -> str:
    """格式化时间为北京时间字符串"""
    if not t:
        return "-"
    
    CST = timezone(timedelta(hours=8))
    dt = parse_timestamp(t)
    
    if dt:
        return dt.astimezone(CST).strftime("%Y-%m-%d %H:%M:%S")
    return str(t)


def format_time_utc8(utc_str: str) -> str:
    """将 UTC 时间字符串转换为 UTC+8"""
    if not utc_str:
        return ""
    try:
        dt_utc = datetime.fromisoformat(utc_str.replace('Z', '+00:00'))
        utc8 = dt_utc.astimezone(timezone(timedelta(hours=8)))
        return utc8.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return utc_str


# =============== 状态判定 ===============

def build_status(latest: Optional[Dict]) -> str:
    """
    根据 startTime/endTime 计算活动状态
    
    返回：
    - ⏳ 未开始
    - ✅ 进行中
    - 🔴 已结束
    - ⚪ 未知
    """
    if not latest:
        return "⚪ 未知"
    
    now = datetime.now(timezone.utc)
    start = parse_timestamp(latest.get("startTime"))
    end = parse_timestamp(latest.get("endTime"))
    
    # 未开始
    if start and now < start:
        return "⏳ 未开始"
    
    # 进行中
    if start and (not end or now <= end):
        return "✅ 进行中"
    
    # 已结束
    if end and now > end:
        return "🔴 已结束"
    
    return "⚪ 未知"


def get_status_group(project: dict) -> int:
    """
    获取状态分组用于排序
    
    0 - 未开始
    1 - 进行中
    2 - 未知
    3 - 已结束
    4 - 暂无活动（排最后）
    """
    latest = project.get("latest")
    
    # 没有活动的项目排在最后
    if not latest:
        return 4
    
    status = build_status(latest) or ""
    
    if "未开始" in status or "⏳" in status:
        return 0
    if "进行中" in status or "✅" in status:
        return 1
    if "未知" in status or "⚪" in status:
        return 2
    if "已结束" in status or "🔴" in status:
        return 3
    return 4


def sort_projects(projects: List[dict]) -> List[dict]:
    """
    统一的项目排序逻辑
    
    排序规则：
    1. 按状态分组（未开始 > 进行中 > 未知 > 已结束）
    2. trending 优先于 custom
    3. startTime 倒序
    4. 名称字母序
    """
    def sort_key(p):
        group = get_status_group(p)
        trending_rank = 0 if p.get("category") == "trending" else 1
        
        # 获取时间戳
        latest = p.get("latest") or {}
        ts = 0
        try:
            ts = int(latest.get("startTime") or latest.get("createdAt") or 0)
        except Exception:
            ts = 0
        
        name = (p.get("name") or "").lower()
        
        return (group, trending_rank, -ts, name)
    
    return sorted(projects, key=sort_key)


# =============== 通知推送 ===============

def build_notify_text(project_name: str, alias: str, latest: Dict, url: Optional[str]) -> str:
    """构建通知消息文本"""
    title = (latest or {}).get("name") or "(无标题活动)"
    start = format_time(latest.get("startTime")) if latest else "-"
    end = format_time(latest.get("endTime")) if latest else "-"
    status = build_status(latest)
    
    # 状态图标
    status_icon = "⏳" if "未开始" in status else "✅" if "进行中" in status else "🔴"
    
    message = f"""
🔔 <b>NTX Quest Radar - 新活动通知</b>

{status_icon} 状态: <b>{status}</b>
📊 项目: <b>{project_name}</b>
🆔 Alias: <code>{alias}</code>
📢 活动: <b>{title}</b>

⏰ 开始: {start}
⏰ 结束: {end}

🔗 <a href="{url}">立即参与</a>
    """.strip()
    
    return message


def send_telegram_to_target(token: str, chat_id: str, text: str) -> bool:
    """发送消息到指定的Telegram目标"""
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            logger.info(f"✅ Telegram 通知已发送到 {chat_id}")
            return True
        else:
            error_msg = response.json().get("description", "未知错误")
            logger.error(f"❌ Telegram 推送失败 [{response.status_code}]: {error_msg}")
            logger.error(f"   Chat ID: {chat_id}")
            return False
    except Exception as e:
        logger.error(f"❌ Telegram 推送异常: {e}")
        return False


def send_telegram(cfg: dict, text: str, project_alias: str = None):
    """发送 Telegram 通知(支持多Bot多群组)"""
    # 获取通知目标列表
    notify_targets = cfg.get("notify_targets", [])
    
    # 如果没有配置notify_targets,使用旧的单一配置(向后兼容)
    if not notify_targets:
        token = cfg.get("telegram_bot_token") or ""
        chat_id = cfg.get("telegram_chat_id") or ""
        if token and chat_id:
            send_telegram_to_target(token, chat_id, text)
        return
    
    # 遍历所有通知目标
    sent_count = 0
    for target in notify_targets:
        # 检查是否启用
        if not target.get("enabled", True):
            continue
        
        # 检查项目过滤(如果指定了projects列表)
        target_projects = target.get("projects", [])
        if target_projects and project_alias:
            if project_alias not in target_projects:
                continue
        
        token = target.get("bot_token")
        chat_id = target.get("chat_id")
        
        if token and chat_id:
            if send_telegram_to_target(token, chat_id, text):
                sent_count += 1
    
    if sent_count > 0:
        logger.info(f"📤 共推送到 {sent_count} 个目标")


def send_discord(cfg: dict, text: str):
    """发送 Discord 通知"""
    webhook = cfg.get("discord_webhook_url") or ""
    
    if not webhook:
        return
    
    try:
        requests.post(webhook, json={"content": text}, timeout=10)
        logger.info("Discord 通知已发送")
    except Exception as e:
        logger.error(f"Discord 推送失败: {e}")


def should_notify(latest: Dict) -> bool:
    """判断是否应该推送通知
    
    推送条件:
    1. 活动未开始 或 正在进行中
    2. 活动结束时间在未来60天内
    3. 活动未结束
    """
    if not latest:
        return False
    
    now = datetime.now(timezone.utc)
    
    # 检查活动时间
    start_ts = latest.get("startTime")
    end_ts = latest.get("endTime")
    
    if not start_ts or not end_ts:
        return False
    
    try:
        start_time = datetime.fromtimestamp(int(start_ts) / 1000, timezone.utc)
        end_time = datetime.fromtimestamp(int(end_ts) / 1000, timezone.utc)
    except:
        return False
    
    # 条件1: 活动不能已经结束
    if now > end_time:
        logger.debug(f"跳过推送 - 活动已结束")
        return False
    
    # 条件2: 结束时间不能太遥远(60天后)
    days_until_end = (end_time - now).days
    if days_until_end > 60:
        logger.debug(f"跳过推送 - 活动结束时间太远({days_until_end}天后)")
        return False
    
    # 条件3: 开始时间不能太早(超过30天前开始的不推送)
    if now > start_time:
        days_since_start = (now - start_time).days
        if days_since_start > 30:
            logger.debug(f"跳过推送 - 活动开始时间太久({days_since_start}天前)")
            return False
    
    return True


def send_notifications(cfg: dict, project_name: str, alias: str, latest: Dict, url: Optional[str]):
    """发送通知（支持 Telegram/Discord）"""
    method = (cfg.get("notify_method") or "none").lower()
    
    if method == "none":
        return
    
    # 检查是否应该推送
    if not should_notify(latest):
        logger.info(f"⏭️  跳过推送 [{project_name}] - 不符合推送条件")
        return
    
    text = build_notify_text(project_name, alias, latest, url)
    
    if method in ("telegram", "both"):
        send_telegram(cfg, text, alias)
    if method in ("discord", "both"):
        send_discord(cfg, text)


# =============== 监控主循环 ===============

def monitor_loop():
    """后台监控循环"""
    global monitor_state, last_notified
    first_loop = True
    
    logger.info("监控循环已启动")
    
    while True:
        try:
            cfg = load_config()
            out = []
            
            for p in cfg.get("projects", []):
                alias = p.get("alias")
                name = p.get("name", alias)
                cat = p.get("category", "custom")
                
                info = fetch_latest(alias)
                latest = info["latest"] if info else None
                url = build_campaign_url(alias, latest)
                
                out.append({
                    "name": name,
                    "alias": alias,
                    "category": cat,
                    "latest": latest,
                    "url": url,
                })
                
                # 检查是否有新活动需要通知
                cid = extract_campaign_id(latest)
                if not first_loop and cid and latest:
                    prev = last_notified.get(alias)
                    if prev != cid:
                        send_notifications(cfg, name, alias, latest, url)
                        last_notified[alias] = cid
            
            monitor_state["last_loop"] = datetime.utcnow().isoformat() + "Z"
            monitor_state["projects"] = out
            write_state(monitor_state)
            
            first_loop = False
            logger.info(f"监控循环完成，共 {len(out)} 个项目")
            
        except Exception as e:
            logger.error(f"监控循环异常: {e}")
        
        time.sleep(30)  # 30秒一次


def start_monitor():
    """启动监控线程"""
    t = threading.Thread(target=monitor_loop, daemon=True)
    t.start()
    logger.info("后台监控线程已启动")


# =============== Web UI ===============

app = Flask(__name__)


def card_html(p: dict) -> str:
    """生成项目卡片 HTML"""
    latest = p.get("latest")
    url = p.get("url") or "#"
    cat = p.get("category", "custom")
    tag = "🔥 Trending" if cat == "trending" else "⭐ Custom"
    
    if latest:
        title = latest.get("name") or "(无标题活动)"
        start = format_time(latest.get("startTime"))
        end = format_time(latest.get("endTime"))
        status = build_status(latest)
        
        # 根据状态设置 CSS 类
        if "进行中" in status:
            css = "pill-running"
        elif "未知" in status:
            css = "pill-unknown"
        elif "未开始" in status:
            css = "pill-upcoming"
        elif "已结束" in status:
            css = "pill-ended"
        else:
            css = "pill-active"
        
        return f"""
        <div class="card">
          <div class="card-header">
            <div>
              <div class="card-title">{p['name']}</div>
              <div class="card-sub">@{p['alias']} · {tag}</div>
            </div>
            <div class="pill {css}">{status}</div>
          </div>
          <div class="card-body">
            <div class="activity-title">
              <span>最新活动：</span>
              <a href="{url}" target="_blank">{title}</a>
            </div>
            <div class="activity-meta">
              <div>开始时间：{start}</div>
              <div>结束时间：{end}</div>
            </div>
          </div>
        </div>
        """
    else:
        return f"""
        <div class="card">
          <div class="card-header">
            <div>
              <div class="card-title">{p['name']}</div>
              <div class="card-sub">@{p['alias']} · {tag}</div>
            </div>
            <div class="pill pill-empty">暂无活动</div>
          </div>
          <div class="card-body">
            <div class="activity-title">当前没有可见活动或拉取失败。</div>
          </div>
        </div>
        """


@app.route("/")
def index():
    """主页 - 活动监控"""
    cfg = load_config()
    pwd = request.args.get("pwd", "")
    
    if pwd != cfg.get("webui_password"):
        return "Unauthorized", 401
    
    q = (request.args.get("q") or "").lower()
    cat = (request.args.get("cat") or "all").lower()
    
    projs = monitor_state.get("projects", [])
    
    # 搜索过滤
    if q:
        projs = [p for p in projs if q in p.get("name", "").lower() or q in p.get("alias", "").lower()]
    
    # 分类过滤
    if cat in ("custom", "trending"):
        projs = [p for p in projs if p.get("category") == cat]
    
    # 排序
    sorted_projs = sort_projects(projs)
    cards = "".join(card_html(p) for p in sorted_projs)
    last = monitor_state.get("last_loop", "")
    last_utc8 = format_time_utc8(last)
    
    active_all = "active" if cat == "all" else ""
    active_custom = "active" if cat == "custom" else ""
    active_trending = "active" if cat == "trending" else ""
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>NTX Quest Radar 控制台</title>
      <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
          background: #020617;
          color: #e5e7eb;
          font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;
        }}
        .shell {{
          min-height: 100vh;
          background: radial-gradient(circle at top left,#0b1120 0,#020617 45%);
        }}
        .container {{
          max-width: 1100px;
          margin: 0 auto;
          padding: 20px 16px 40px;
        }}
        .top-nav {{
          display:flex;
          justify-content:space-between;
          align-items:center;
          margin-bottom:12px;
        }}
        .brand {{
          font-size:20px;
          font-weight:600;
        }}
        .brand span {{
          font-size:11px;
          color:#9ca3af;
          margin-left:6px;
        }}
        .nav-links a {{
          font-size:13px;
          margin-left:10px;
          color:#9ca3af;
          text-decoration:none;
          padding:4px 10px;
          border-radius:999px;
          border:1px solid transparent;
        }}
        .nav-links a.active {{
          color:#e5e7eb;
          border-color:#1d4ed8;
          background:#1d4ed833;
        }}
        .subtitle {{
          font-size:13px;
          color: #9ca3af;
          margin-bottom: 14px;
        }}
        .controls-bar {{
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 20px;
          margin-bottom: 24px;
        }}
        .search-form {{
          display: flex;
          gap: 10px;
          align-items: center;
          flex: 1;
          max-width: 420px;
        }}
        .search-input-wrapper {{
          display: flex;
          align-items: center;
          gap: 10px;
          flex: 1;
          background: rgba(17, 24, 39, 0.6);
          border: 1px solid rgba(96, 165, 250, 0.15);
          border-radius: 8px;
          padding: 10px 12px;
        }}
        .search-input-wrapper input {{
          flex: 1;
          background: transparent;
          border: none;
          color: #e5e7eb;
          outline: none;
          font-size: 13px;
        }}
        .search-form button {{
          padding: 10px 16px;
          border-radius: 8px;
          border: 1px solid rgba(96, 165, 250, 0.2);
          background: rgba(96, 165, 250, 0.08);
          color: #60a5fa;
          font-weight: 500;
          font-size: 13px;
          cursor: pointer;
        }}
        .filters {{
          display: flex;
          gap: 8px;
        }}
        .filter-tag {{
          font-size: 13px;
          padding: 8px 12px;
          border-radius: 6px;
          border: 1px solid rgba(96, 165, 250, 0.2);
          color: #94a3b8;
          text-decoration: none;
        }}
        .filter-tag.active {{
          background: linear-gradient(135deg, rgba(6, 182, 212, 0.2) 0%, rgba(96, 165, 250, 0.15) 100%);
          border-color: rgba(96, 165, 250, 0.3);
          color: #60a5fa;
          font-weight: 500;
        }}
        .btn-manage {{
          font-size: 13px;
          padding: 10px 16px;
          border-radius: 8px;
          background: linear-gradient(135deg, #06b6d4 0%, #0ea5e9 100%);
          color: #fff;
          text-decoration: none;
          font-weight: 500;
        }}
        .grid {{
          display: grid;
          grid-template-columns: repeat(auto-fit,minmax(260px,1fr));
          gap: 14px;
        }}
        .card {{
          background: radial-gradient(circle at top left,#111827 0,#020617 55%);
          border-radius: 14px;
          border: 1px solid #111827;
          padding: 12px 14px;
          box-shadow: 0 10px 25px rgba(0,0,0,0.45);
        }}
        .card-header {{
          display:flex;
          justify-content:space-between;
          align-items:center;
          margin-bottom:8px;
        }}
        .card-title {{
          font-size:15px;
          font-weight:600;
        }}
        .card-sub {{
          font-size:11px;
          color:#9ca3af;
          margin-top:2px;
        }}
        .pill {{
          border-radius:999px;
          padding:3px 8px;
          font-size:11px;
          border:1px solid;
        }}
        .pill-running {{
          background:#16a34a33;
          border-color:#22c55e;
          color:#bbf7d0;
        }}
        .pill-upcoming {{
          background:#64748b33;
          border-color:#64748b;
          color:#e5e7eb;
        }}
        .pill-ended {{
          background:#dc262633;
          border-color:#dc2626;
          color:#fecaca;
        }}
        .pill-unknown {{
          background:#f9731633;
          border-color:#f97316;
          color:#fed7aa;
        }}
        .pill-empty {{
          background:#33415555;
          border-color:#64748b;
          color:#e5e7eb;
        }}
        .activity-title {{
          font-size:13px;
          margin-bottom:4px;
        }}
        .activity-title a {{
          color:#60a5fa;
          text-decoration:none;
        }}
        .activity-title a:hover {{
          text-decoration:underline;
        }}
        .activity-meta {{
          font-size:11px;
          color:#9ca3af;
        }}
        @media (max-width:768px) {{
          .controls-bar {{
            flex-direction: column;
            gap: 12px;
          }}
          .search-form {{
            max-width: 100%;
          }}
        }}
      </style>
    </head>
    <body>
      <div class="shell">
        <div class="container">
          <div class="top-nav">
            <div class="brand">
              NTX Quest Radar
              <span>OpenAPI · V4.0</span>
            </div>
            <div class="nav-links">
              <a href="/?pwd={pwd}" class="active">活动监控</a>
              <a href="/manage?pwd={pwd}">项目管理</a>
            </div>
          </div>

          <div class="subtitle">
            最后刷新：{last_utc8}
          </div>

          <div class="controls-bar">
            <form class="search-form" method="GET" action="/">
              <input type="hidden" name="pwd" value="{pwd}">
              <div class="search-input-wrapper">
                <input type="text" name="q" placeholder="搜索项目…" value="{q}">
              </div>
              <button type="submit">搜索</button>
            </form>

            <div class="filters">
              <a href="/?pwd={pwd}&cat=all" class="filter-tag {active_all}">全部</a>
              <a href="/?pwd={pwd}&cat=custom" class="filter-tag {active_custom}">自定义</a>
              <a href="/?pwd={pwd}&cat=trending" class="filter-tag {active_trending}">热度Top</a>
            </div>

            <a href="/manage?pwd={pwd}" class="btn-manage">项目管理</a>
          </div>

          <div class="grid">
            {cards or '<div style="color:#9ca3af;font-size:13px;">当前没有任何项目。</div>'}
          </div>
        </div>
      </div>
    </body>
    </html>
    """
    return html


@app.route("/manage")
def manage():
    """项目管理页面"""
    cfg = load_config()
    pwd = request.args.get("pwd", "")
    
    if pwd != cfg.get("webui_password"):
        return "Unauthorized", 401
    
    rows = ""
    for i, p in enumerate(cfg.get("projects", [])):
        name = p.get("name", "")
        alias = p.get("alias", "")
        cat = p.get("category", "custom")
        rows += f"<tr><td>{i}</td><td>{name}</td><td>{alias}</td><td>{cat}</td></tr>"
    
    if not rows:
        rows = '<tr><td colspan="4">暂无项目，请在上方操作面板中添加。</td></tr>'
    
    method = (cfg.get("notify_method") or "none").lower()
    discord = cfg.get("discord_webhook_url", "")
    
    sel_none = "selected" if method == "none" else ""
    sel_tg = "selected" if method == "telegram" else ""
    sel_dc = "selected" if method == "discord" else ""
    sel_both = "selected" if method == "both" else ""
    
    # 生成notify_targets列表HTML
    notify_targets = cfg.get("notify_targets", [])
    if notify_targets:
        targets_html = '<div style="margin-top:8px;">'
        for i, target in enumerate(notify_targets):
            name = target.get("name", f"目标{i+1}")
            bot_token = target.get("bot_token", "")[:20] + "..."
            chat_id = target.get("chat_id", "")
            enabled = target.get("enabled", True)
            projects = target.get("projects", [])
            status_icon = "✅" if enabled else "❌"
            status_text = "启用" if enabled else "禁用"
            projects_text = ", ".join(projects[:3]) if projects else "全部项目"
            if len(projects) > 3:
                projects_text += f" +{len(projects)-3}个"
            
            targets_html += f'''
              <div style="padding:12px;margin-bottom:8px;background:rgba(17,24,39,0.5);border-radius:6px;border:1px solid rgba(96,165,250,0.2);">
                <div style="display:flex;align-items:center;justify-content:space-between;">
                  <div style="flex:1;">
                    <div style="font-weight:bold;margin-bottom:4px;">{status_icon} {name}</div>
                    <div style="font-size:0.85em;color:#9ca3af;">
                      <span>Token: {bot_token}</span> | 
                      <span>Chat ID: {chat_id}</span> | 
                      <span>过滤: {projects_text}</span> | 
                      <span style="color:{'#10b981' if enabled else '#ef4444'};">{status_text}</span>
                    </div>
                  </div>
                  <form method="POST" action="/delete_notify_target" style="margin:0;">
                    <input type="hidden" name="pwd" value="{pwd}">
                    <input type="hidden" name="index" value="{i}">
                    <button type="submit" class="btn" style="background:#ef4444;padding:6px 12px;" onclick="return confirm('确认删除该推送目标?')">删除</button>
                  </form>
                </div>
              </div>
            '''
        targets_html += '</div>'
    else:
        targets_html = '<div style="padding:12px;color:#9ca3af;background:rgba(17,24,39,0.3);border-radius:6px;margin-top:8px;">💡 暂无推送目标,请添加第一个</div>'
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>NTX Quest Radar · 项目管理</title>
      <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
          background: #020617;
          color: #e5e7eb;
          font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;
        }}
        .shell {{
          min-height: 100vh;
          background: radial-gradient(circle at top right, #0f172a 0%, #020617 40%, #000 100%);
        }}
        .container {{
          max-width: 960px;
          margin: 0 auto;
          padding: 20px 16px 40px;
        }}
        .top-nav {{
          display:flex;
          justify-content:space-between;
          align-items:center;
          margin-bottom:12px;
        }}
        .brand {{
          font-size:20px;
          font-weight:600;
        }}
        .brand span {{
          font-size:11px;
          color:#9ca3af;
          margin-left:6px;
        }}
        .nav-links a {{
          font-size:13px;
          margin-left:10px;
          color:#9ca3af;
          text-decoration:none;
          padding:4px 10px;
          border-radius:999px;
          border:1px solid transparent;
        }}
        .nav-links a.active {{
          color:#e5e7eb;
          border-color:#1d4ed8;
          background:#1d4ed833;
        }}
        .subtitle {{
          font-size:13px;
          color: #9ca3af;
          margin-bottom: 14px;
        }}
        .card {{
          background: linear-gradient(135deg, rgba(17, 24, 39, 0.8) 0%, rgba(2, 6, 23, 0.95) 100%);
          border-radius: 12px;
          border: 1px solid rgba(96, 165, 250, 0.1);
          padding: 14px 16px 16px;
          margin-bottom: 14px;
        }}
        .card-header {{
          display:flex;
          justify-content:space-between;
          align-items:center;
          margin-bottom:10px;
        }}
        .card-title {{
          font-size:15px;
          font-weight:600;
        }}
        .pill-back {{
          border-radius:999px;
          padding:4px 10px;
          font-size:12px;
          border:1px solid #374151;
          background:#020617;
          color:#e5e7eb;
          text-decoration:none;
        }}
        table {{
          width: 100%;
          border-collapse: collapse;
          font-size: 13px;
        }}
        th, td {{
          border-bottom: 1px solid #1f2937;
          padding: 6px 8px;
          text-align: left;
        }}
        th {{
          font-weight:500;
          color:#9ca3af;
          background:#020617;
        }}
        .form-row {{
          display:flex;
          flex-wrap:wrap;
          gap:8px;
          align-items:center;
          margin-top:8px;
        }}
        .form-row label {{
          font-size:12px;
          color:#9ca3af;
        }}
        .form-row input, .form-row textarea, .form-row select {{
          background:#020617;
          border-radius:8px;
          border:1px solid #1f2937;
          padding:6px 10px;
          color:#e5e7eb;
          font-size:12px;
        }}
        .form-row textarea {{
          width:100%;
          min-height:70px;
          font-family:monospace;
        }}
        .btn {{
          border-radius:999px;
          border:1px solid #4b5563;
          background:#111827;
          color:#e5e7eb;
          padding:6px 12px;
          font-size:12px;
          cursor:pointer;
        }}
        .btn-primary {{
          background:#10b981;
          border-color:#10b981;
          color:#022c22;
          font-weight:600;
        }}
        .hint {{
          font-size:11px;
          color:#9ca3af;
          margin-top:4px;
        }}
      </style>
    </head>
    <body>
      <div class="shell">
        <div class="container">
          <div class="top-nav">
            <div class="brand">
              NTX Quest Radar
              <span>项目管理</span>
            </div>
            <div class="nav-links">
              <a href="/?pwd={pwd}">活动监控</a>
              <a href="/manage?pwd={pwd}" class="active">项目管理</a>
            </div>
          </div>

          <div class="subtitle">
            在这里快速增删你要监控的 Galxe Space，并配置通知方式。
          </div>

          <div class="card">
            <div class="card-header">
              <div class="card-title">操作面板</div>
              <a class="pill-back" href="/?pwd={pwd}">← 返回监控首页</a>
            </div>

            <form method="GET" action="/add">
              <input type="hidden" name="pwd" value="{pwd}">
              <div class="form-row">
                <label>名称</label>
                <input name="name" placeholder="例如：BNB Chain">
                <label>Alias</label>
                <input name="alias" placeholder="例如：bnbchain">
                <label>分类</label>
                <input name="category" value="custom" placeholder="custom 或 trending">
                <button type="submit" class="btn btn-primary">添加单个项目</button>
              </div>
              <div class="hint">Alias 通常可以从 Space URL 中看到（app.galxe.com/quest/&lt;alias&gt;）。</div>
            </form>

            <form method="POST" action="/add_bulk" style="margin-top:12px;">
              <input type="hidden" name="pwd" value="{pwd}">
              <div class="form-row">
                <label>批量导入</label>
                <textarea name="bulk" placeholder="每行一个，支持三种格式：
1) alias
2) name,alias
3) name,alias,category"></textarea>
                <button type="submit" class="btn">批量导入</button>
              </div>
            </form>

            <form method="GET" action="/delete" style="margin-top:12px;">
              <input type="hidden" name="pwd" value="{pwd}">
              <div class="form-row">
                <label>删除项目（按索引）</label>
                <input name="idx" placeholder="在下方表格中查看索引">
                <button type="submit" class="btn">删除</button>
              </div>
            </form>

            <form method="POST" action="/save_notify" style="margin-top:16px;">
              <input type="hidden" name="pwd" value="{pwd}">
              <div class="form-row">
                <label>通知方式</label>
                <select name="notify_method">
                  <option value="none" {sel_none}>none（不推送）</option>
                  <option value="telegram" {sel_tg}>telegram</option>
                  <option value="discord" {sel_dc}>discord</option>
                  <option value="both" {sel_both}>both（TG + Discord）</option>
                </select>
                <button type="submit" class="btn btn-primary">保存通知配置</button>
                <a class="btn" href="/notify_test?pwd={pwd}">发送测试通知</a>
              </div>
              <div class="form-row">
                <label>Discord Webhook URL</label>
                <input style="flex:1;min-width:260px;" name="discord_webhook_url" value="{discord}" placeholder="https://discord.com/api/webhooks/...">
              </div>
            </form>

            <h3 style="margin-top:24px;margin-bottom:12px;color:#60a5fa;">📱 Telegram 推送目标</h3>
            {targets_html}

            <form method="POST" action="/add_notify_target" style="margin-top:16px;padding:16px;background:rgba(96,165,250,0.05);border-radius:8px;">
              <input type="hidden" name="pwd" value="{pwd}">
              <div style="margin-bottom:12px;font-weight:bold;color:#60a5fa;">➕ 添加新的推送目标</div>
              <div class="form-row">
                <label>名称</label>
                <input name="name" placeholder="例如: VIP群" required style="flex:0.5;">
                <label>Bot Token</label>
                <input name="bot_token" placeholder="123456:ABC-DEF..." required style="flex:1;">
              </div>
              <div class="form-row">
                <label>Chat ID</label>
                <input name="chat_id" placeholder="-1001234567890" required style="flex:0.5;">
                <label>项目过滤</label>
                <input name="projects" placeholder="留空=全部, 或填: bnbchain,Galxe" style="flex:1;">
              </div>
              <div class="form-row">
                <label>状态</label>
                <select name="enabled" style="flex:0.3;">
                  <option value="true">启用</option>
                  <option value="false">禁用</option>
                </select>
                <button type="submit" class="btn btn-primary" style="margin-left:auto;">添加目标</button>
              </div>
            </form>
          </div>

          <div class="card">
            <div class="card-header">
              <div class="card-title">当前已监控项目</div>
            </div>
            <div style="overflow-x:auto;">
              <table>
                <tr><th>索引</th><th>名称</th><th>Alias</th><th>分类</th></tr>
                {rows}
              </table>
            </div>
          </div>
        </div>
      </div>
    </body>
    </html>
    """
    return html


@app.route("/add")
def add():
    """添加单个项目"""
    cfg = load_config()
    pwd = request.args.get("pwd", "")
    
    if pwd != cfg.get("webui_password"):
        return "Unauthorized", 401
    
    name = (request.args.get("name") or "").strip()
    alias = (request.args.get("alias") or "").strip()
    category = (request.args.get("category") or "custom").strip() or "custom"
    
    if not name or not alias:
        return "缺少 name 或 alias"
    
    cfg.setdefault("projects", []).append({
        "name": name,
        "alias": alias,
        "category": category
    })
    save_config(cfg)
    logger.info(f"已添加项目: {name} (@{alias})")
    
    return f"添加成功：{name} ({alias}) [{category}] · <a href='/?pwd={pwd}'>返回首页</a>"


@app.route("/add_bulk", methods=["GET", "POST"])
def add_bulk():
    """批量添加项目"""
    cfg = load_config()
    pwd = request.values.get("pwd", "")
    
    if pwd != cfg.get("webui_password"):
        return "Unauthorized", 401
    
    text = (request.values.get("bulk") or "").strip()
    if not text:
        return f"未收到任何内容 · <a href='/manage?pwd={pwd}'>返回管理页面</a>"
    
    lines = text.splitlines()
    added = 0
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        
        parts = [x.strip() for x in line.split(",") if x.strip()]
        
        if len(parts) == 1:
            alias = parts[0]
            name = alias
            category = "custom"
        elif len(parts) == 2:
            name, alias = parts
            category = "custom"
        else:
            name, alias, category = parts[0], parts[1], parts[2] or "custom"
        
        cfg.setdefault("projects", []).append({
            "name": name,
            "alias": alias,
            "category": category
        })
        added += 1
    
    save_config(cfg)
    logger.info(f"批量添加完成，共 {added} 个项目")
    
    return f"批量添加完成，共添加 {added} 个项目。<a href='/?pwd={pwd}'>返回首页</a>"


@app.route("/delete")
def delete():
    """删除项目"""
    cfg = load_config()
    pwd = request.args.get("pwd", "")
    
    if pwd != cfg.get("webui_password"):
        return "Unauthorized", 401
    
    idx = request.args.get("idx") or ""
    try:
        i = int(idx)
    except Exception:
        return "idx 必须是整数"
    
    lst = cfg.get("projects", [])
    if 0 <= i < len(lst):
        removed = lst.pop(i)
        save_config(cfg)
        logger.info(f"已删除项目: {removed.get('name')} (@{removed.get('alias')})")
        return f"已删除：{removed.get('name')} ({removed.get('alias')}) · <a href='/?pwd={pwd}'>返回首页</a>"
    else:
        return "索引超出范围"


@app.route("/save_notify", methods=["POST"])
def save_notify():
    """保存通知配置"""
    cfg = load_config()
    pwd = request.form.get("pwd", "")
    
    if pwd != cfg.get("webui_password"):
        return "Unauthorized", 401
    
    method = (request.form.get("notify_method") or "none").lower()
    discord = request.form.get("discord_webhook_url") or ""
    
    cfg["notify_method"] = method
    cfg["discord_webhook_url"] = discord
    save_config(cfg)
    
    logger.info(f"通知配置已更新: {method}")
    return f"通知配置已保存（当前：{method}）。<a href='/manage?pwd={pwd}'>返回管理页面</a>"


@app.route("/add_notify_target", methods=["POST"])
def add_notify_target():
    """添加Telegram推送目标"""
    cfg = load_config()
    pwd = request.form.get("pwd", "")
    
    if pwd != cfg.get("webui_password"):
        return "Unauthorized", 401
    
    name = request.form.get("name", "").strip()
    bot_token = request.form.get("bot_token", "").strip()
    chat_id = request.form.get("chat_id", "").strip()
    projects_str = request.form.get("projects", "").strip()
    enabled = request.form.get("enabled", "true") == "true"
    
    if not name or not bot_token or not chat_id:
        return "❌ 名称、Bot Token和Chat ID不能为空。<a href='/manage?pwd={pwd}'>返回</a>"
    
    # 解析projects
    projects = [p.strip() for p in projects_str.split(",") if p.strip()] if projects_str else []
    
    # 添加到notify_targets
    if "notify_targets" not in cfg:
        cfg["notify_targets"] = []
    
    cfg["notify_targets"].append({
        "name": name,
        "bot_token": bot_token,
        "chat_id": chat_id,
        "enabled": enabled,
        "projects": projects
    })
    
    save_config(cfg)
    logger.info(f"已添加推送目标: {name} -> {chat_id}")
    
    return f"✅ 已添加推送目标: {name}。<a href='/manage?pwd={pwd}'>返回管理页面</a>"


@app.route("/delete_notify_target", methods=["POST"])
def delete_notify_target():
    """删除Telegram推送目标"""
    cfg = load_config()
    pwd = request.form.get("pwd", "")
    
    if pwd != cfg.get("webui_password"):
        return "Unauthorized", 401
    
    index = int(request.form.get("index", -1))
    
    if "notify_targets" not in cfg or index < 0 or index >= len(cfg["notify_targets"]):
        return "❌ 无效的索引。<a href='/manage?pwd={pwd}'>返回</a>"
    
    deleted = cfg["notify_targets"].pop(index)
    save_config(cfg)
    
    logger.info(f"已删除推送目标: {deleted.get('name', '未命名')}")
    return f"✅ 已删除推送目标: {deleted.get('name', '未命名')}。<a href='/manage?pwd={pwd}'>返回管理页面</a>"


@app.route("/notify_test")
def notify_test():
    """测试通知"""
    cfg = load_config()
    pwd = request.args.get("pwd", "")
    
    if pwd != cfg.get("webui_password"):
        return "Unauthorized", 401
    
    method = (cfg.get("notify_method") or "none").lower()
    if method == "none":
        return f"当前 notify_method=none，未发送通知。<a href='/manage?pwd={pwd}'>返回管理页面</a>"
    
    text = "【NTX Quest Radar】这是一条测试通知，用于验证 Telegram / Discord 配置是否正常。"
    
    if method in ("telegram", "both"):
        send_telegram(cfg, text, None)
    if method in ("discord", "both"):
        send_discord(cfg, text)
    
    logger.info(f"已发送测试通知: {method}")
    return f"已按当前通知方式 ({method}) 发送一条测试消息。<a href='/manage?pwd={pwd}'>返回管理页面</a>"


@app.route("/raw")
@app.route("/api/raw")
def api_raw():
    """JSON API 接口"""
    cfg = load_config()
    pwd = request.args.get("pwd", "")
    
    if pwd != cfg.get("webui_password"):
        return jsonify({"error": "unauthorized"}), 401
    
    return jsonify(monitor_state)


# =============== 主函数 ===============

if __name__ == "__main__":
    # 初始化
    ensure_config()
    cfg = load_config()
    
    # 加载历史状态
    monitor_state = load_initial_state()
    
    logger.info("=== NTX Quest Radar V4.0（优化版） ===")
    logger.info(f"Web UI 密码: {cfg.get('webui_password')}")
    logger.info(f"访问: http://localhost:{cfg['webui_port']}/?pwd={cfg['webui_password']}")
    
    # 启动后台监控
    start_monitor()
    
    # 启动 Web 服务
    app.run(
        host="0.0.0.0",
        port=cfg["webui_port"],
        debug=False,
        threaded=True
    )
