#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# NTX Quest Radar V4.0
# - 使用 Galxe Open API
# - 卡片只显示：开始时间 / 结束时间 / 活动状态（未开始 / 进行中 / 已结束）
# - 删除“创建时间”显示，避免无意义的 "-"
# - 顶部导航 + 更现代的卡片布局
# - 支持项目管理（单个添加 / 批量导入 / 删除）
# - 支持 Telegram / Discord 推送 + 测试通知

import json
import os
import threading
import time
from datetime import datetime, timezone, timedelta

import requests
from flask import Flask, request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config_files", "config.json")
STATE_PATH = os.path.join(ROOT, "data", "monitor_state.json")
OPENAPI_URL = "https://graphigo.prd.galaxy.eco/query"

last_notified = {}  # alias -> last campaign id


# =============== 配置管理 ===============

def ensure_config():
    if not os.path.exists(CONFIG_PATH):
        cfg = {
            "webui_port": 5001,
            "webui_password": "admin",
            "notify_method": "none",          # none / telegram / discord / both
            "telegram_bot_token": "",
            "telegram_chat_id": "",
            "discord_webhook_url": "",
            "projects": [
                {"name": "BNB Chain", "alias": "bnbchain", "category": "trending"},
                {"name": "Galxe Official", "alias": "Galxe", "category": "trending"},
                {"name": "OKX Web3", "alias": "okxweb3", "category": "trending"},
                {"name": "Zaiffer Quest", "alias": "Zaiffer", "category": "trending"},
            ],
        }
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def write_state(state):
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print("[写入 monitor_state.json 失败]:", e)


# =============== OpenAPI ===============

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


def fetch_latest(alias):
    try:
        r = requests.post(
            OPENAPI_URL,
            json={"query": QUERY_LATEST_SAFE, "variables": {"alias": alias}},
            timeout=15,
        )
        data = r.json()
        if "errors" in data:
            print("[OpenAPI 错误]", alias, data["errors"])
            return None

        space = data.get("data", {}).get("space")
        if not space:
            return None

        lst = space.get("campaigns", {}).get("list", [])
        latest = lst[0] if lst else None
        return {"space": space, "latest": latest}
    except Exception as e:
        print("[请求失败]", alias, e)
        return None


def _extract_campaign_id(latest):
    if not latest:
        return None

    def gx(obj, key):
        if isinstance(obj, dict):
            return obj.get(key)
        return getattr(obj, key, None)

    for k in ("id", "campaignId", "campaignID", "hashId", "slug"):
        v = gx(latest, k)
        if v:
            return v
    return None


def build_campaign_url(alias, latest):
    if not alias or not latest:
        return None
    cid = _extract_campaign_id(latest)
    if not cid:
        return None
    # 使用 /quest/alias/campaignId 格式，规避 404
    return "https://app.galxe.com/quest/{}/{}".format(alias, cid)


# =============== 时间与状态处理 ===============

def _fmt_time(t):
    """把时间戳 / ISO 字符串转成 北京时间，可读格式。"""
    if not t:
        return "-"

    CST = timezone(timedelta(hours=8))

    # 直接是 datetime
    if isinstance(t, datetime):
        return t.astimezone(CST).strftime("%Y-%m-%d %H:%M:%S")

    # 数字（时间戳）
    try:
        if isinstance(t, (int, float)):
            ts = float(t)
        elif isinstance(t, str):
            s = t.strip()
            if s.isdigit():
                ts = float(s)
            else:
                # 尝试当 ISO 格式解析
                try:
                    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
                    return dt.astimezone(CST).strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    return s
        else:
            return str(t)

        if ts > 1e12:  # 毫秒级
            ts = ts / 1000.0
        dt = datetime.fromtimestamp(ts, tz=CST)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(t)


def _parse_ts(t):
    """把各种时间形式统一成 UTC datetime，失败返回 None。"""
    if not t:
        return None
    if isinstance(t, datetime):
        if t.tzinfo is None:
            return t.replace(tzinfo=timezone.utc)
        return t.astimezone(timezone.utc)
    try:
        if isinstance(t, (int, float)):
            ts = float(t)
        elif isinstance(t, str):
            s = t.strip()
            if s.isdigit():
                ts = float(s)
            else:
                # ISO
                try:
                    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt.astimezone(timezone.utc)
                except Exception:
                    return None
        else:
            return None

        if ts > 1e12:
            ts = ts / 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except Exception:
        return None



def _build_status(latest):
    """根据 startTime / endTime 计算状态：未开始 / 进行中 / 已结束 / 未知。"""
    if not latest:
        return "🟠 未知"

    now = datetime.utcnow().replace(tzinfo=timezone.utc)
    start = _parse_ts(latest.get("startTime"))
    end = _parse_ts(latest.get("endTime"))

    if start and now < start:
        return "⏳ 未开始"
    if end and now > end:
        return "🔴 已结束"
    if start and (not end or start <= now <= end):
        return "✅ 进行中"

    return "🟠 未知"


    now = datetime.utcnow().replace(tzinfo=timezone.utc)
    start = _parse_ts(latest.get("startTime"))
    end = _parse_ts(latest.get("endTime"))

    if start and now < start:
        return "⏳ 未开始"
    if end and now > end:
        return "⚠️ 已结束"
    if start and (not end or start <= now <= end):
        return "✅ 进行中"
    return "未知"


# =============== 推送通知 ===============

def _build_notify_text(project_name, alias, latest, url):
    title = (latest or {}).get("name") or "(无标题活动)"
    start = _fmt_time(latest.get("startTime")) if latest else "-"
    end = _fmt_time(latest.get("endTime")) if latest else "-"
    status = _build_status(latest)

    lines = [
        "【NTX Quest Radar】发现新活动",
        "项目：{} (@{})".format(project_name, alias),
        "活动：{}".format(title),
        "状态：{}".format(status),
        "开始时间：{}".format(start),
        "结束时间：{}".format(end),
        "链接：{}".format(url or "-"),
    ]
    return "\n".join(lines)


def send_telegram(cfg, text):
    token = cfg.get("telegram_bot_token") or ""
    chat_id = cfg.get("telegram_chat_id") or ""
    if not token or not chat_id:
        return
    try:
        url = "https://api.telegram.org/bot{}/sendMessage".format(token)
        requests.post(url, data={"chat_id": chat_id, "text": text}, timeout=10)
    except Exception as e:
        print("[Telegram 推送失败]", e)


def send_discord(cfg, text):
    webhook = cfg.get("discord_webhook_url") or ""
    if not webhook:
        return
    try:
        requests.post(webhook, json={"content": text}, timeout=10)
    except Exception as e:
        print("[Discord 推送失败]", e)


def send_notifications(cfg, project_name, alias, latest, url):
    method = (cfg.get("notify_method") or "none").lower()
    if method == "none":
        return
    text = _build_notify_text(project_name, alias, latest, url)
    if method in ("telegram", "both"):
        send_telegram(cfg, text)
    if method in ("discord", "both"):
        send_discord(cfg, text)


# =============== 监控主循环 ===============

# 初始化监控状态，启动时从文件加载
def _load_initial_state():
    import os, json
    try:
        if os.path.exists(STATE_PATH):
            with open(STATE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {"last_loop": "", "projects": []}

def format_time_utc8(utc_str):
    """将 UTC 时间转换为 UTC+8 格式"""
    if not utc_str:
        return ""
    try:
        from datetime import datetime, timedelta, timezone
        dt_utc = datetime.fromisoformat(utc_str.replace('Z', '+00:00'))
        utc8 = dt_utc.astimezone(timezone(timedelta(hours=8)))
        return utc8.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return utc_str

monitor_state = _load_initial_state()


def monitor_loop():
    global monitor_state, last_notified
    first_loop = True

    while True:
        cfg = load_config()
        out = []

        for p in cfg.get("projects", []):
            alias = p.get("alias")
            name = p.get("name", alias)
            cat = p.get("category", "custom")

            info = fetch_latest(alias)
            latest = info["latest"] if info else None
            url = build_campaign_url(alias, latest)

            out.append(
                {
                    "name": name,
                    "alias": alias,
                    "category": cat,
                    "latest": latest,
                    "url": url,
                }
            )

            cid = _extract_campaign_id(latest)
            if not first_loop and cid and latest:
                prev = last_notified.get(alias)
                if prev != cid:
                    send_notifications(cfg, name, alias, latest, url)
                    last_notified[alias] = cid

        monitor_state["last_loop"] = datetime.utcnow().isoformat() + "Z"
        monitor_state["projects"] = out
        write_state(monitor_state)

        first_loop = False
        time.sleep(20)


# =============== Web UI ===============

app = Flask(__name__)


def card_html(p):
    latest = p.get("latest")
    url = p.get("url") or "#"
    cat = p.get("category", "custom")
    tag = "🔥 Trending" if cat == "trending" else "⭐ Custom"

    if latest:
        title = latest.get("name") or "(无标题活动)"
        start = _fmt_time(latest.get("startTime"))
        end = _fmt_time(latest.get("endTime"))
        status = _build_status(latest)
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

        return """
        <div class="card">
          <div class="card-header">
            <div>
              <div class="card-title">{name}</div>
              <div class="card-sub">@{alias} · {tag}</div>
            </div>
            <div class="pill">{status}</div>
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
        """.format(
            name=p["name"],
            alias=p["alias"],
            tag=tag,
            url=url,
            title=title,
            start=start,
            end=end,
            status=status,
        )
    else:
        return """
        <div class="card">
          <div class="card-header">
            <div>
              <div class="card-title">{name}</div>
              <div class="card-sub">@{alias} · {tag}</div>
            </div>
            <div class="pill pill-empty">暂无活动</div>
          </div>
          <div class="card-body">
            <div class="activity-title">当前没有可见活动或拉取失败。</div>
          </div>
        </div>
        """.format(
            name=p["name"],
            alias=p["alias"],
            tag=tag,
        )


@app.route("/")
def index():
    cfg = load_config()
    pwd = request.args.get("pwd", "")
    if pwd != cfg.get("webui_password"):
        return "Unauthorized", 401

    q = (request.args.get("q") or "").lower()
    cat = (request.args.get("cat") or "all").lower()

    projs = monitor_state.get("projects", [])

    if q:
        filtered = []
        for p in projs:
            if q in (p.get("name", "").lower()) or q in (p.get("alias", "").lower()):
                filtered.append(p)
        projs = filtered

    if cat in ("custom", "trending"):
        projs = [p for p in projs if p.get("category") == cat]

    # === NTX 自定义排序：进行中 / 有效活动在前，已结束和无效在后 ===
    def _ntx_sort_key(p):
        # 直接从 latest 计算状态，不依赖 latest_status 字段
        latest = p.get("latest") or {}
        status = _build_status(latest) if latest else ""

        # 按状态分层，排序顺序：
        # 0: 未开始
        # 1: 进行中
        # 2: 未知
        # 3: 已结束
        # 4: 暂无活动 / 拉取失败 / 其它异常
        rank = 4
        if not latest or "暂无活动" in status or "拉取失败" in status or "抓取失败" in status:
            rank = 4
        elif "已结束" in status or "🔴" in status:
            rank = 3
        elif "未知" in status or "🟠" in status:
            rank = 2
        elif "进行中" in status or "✅" in status or "有最新活动" in status or "最新活动" in status:
            rank = 1
        elif "未开始" in status or "⏳" in status or "即将开始" in status:
            rank = 0
        else:
            rank = 4

        latest = p.get("latest") or {}
        # Galxe 返回的一般是秒级时间戳，这里统一成 int 方便比较
        def _to_int(v):
            try:
                return int(v)
            except Exception:
                return 0

        start_ts = _to_int(latest.get("startTime") or 0)
        created_ts = _to_int(latest.get("createdAt") or 0)
        # 时间越新越靠前，所以取负数
        ts = max(start_ts, created_ts)

        return (rank, -ts)

    def _ntx_status_group(p):
        latest = p.get("latest") or {}
        status = _build_status(latest) or ""
        # 排序顺序：0-未开始 1-进行中 2-未知 3-已结束 4-暂无活动
        if not latest:
            return 4  # 暂无活动
        if "未开始" in status or "⏳" in status or "即将开始" in status:
            return 0
        if "进行中" in status or "✅" in status:
            return 1
        if "未知" in status or "🟠" in status:
            return 2
        if "已结束" in status or "🔴" in status or "结束" in status:
            return 3
        return 4  # 其他视为暂无活动

    sorted_projs = sorted(
        projs,
        key=lambda p: (
            _ntx_status_group(p),
            0 if p.get("category") == "trending" else 1,
            -int((p.get("latest") or {}).get("startTime") or 0),
            p.get("name", "").lower(),
        ),
    )
    cards = "".join(card_html(p) for p in sorted_projs)
    last = monitor_state.get("last_loop", "")
    last_utc8 = format_time_utc8(last)

    active_all = "active" if cat == "all" else ""
    active_custom = "active" if cat == "custom" else ""
    active_trending = "active" if cat == "trending" else ""

    html = """
    <html>
    <head>
      <meta charset="utf-8" />
      <title>NTX Quest Radar 控制台</title>
      <style>
        body {{
          margin: 0;
          padding: 0;
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
        .top-bar {{
          display: flex;
          flex-direction: column;
          gap: 16px;
          margin-bottom: 20px;
          padding: 16px 20px;
          background: linear-gradient(135deg, rgba(15, 23, 42, 0.6) 0%, rgba(2, 6, 23, 0.8) 100%);
          border: 1px solid rgba(96, 165, 250, 0.1);
          border-radius: 12px;
          box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
          backdrop-filter: blur(10px);
        }}
        
        .search-wrapper {{
          flex: 1;
          max-width: 400px;
        }}
        
        .search-box {{
          display: flex;
          gap: 8px;
          align-items: center;
        }}
        
        .search-box input {{
          flex: 1;
          background: rgba(17, 24, 39, 0.8);
          border-radius: 8px;
          border: 1px solid rgba(96, 165, 250, 0.2);
          padding: 10px 14px;
          color: #e5e7eb;
          outline: none;
          font-size: 13px;
          transition: all 0.3s ease;
        }}
        
        .search-box input:focus {{
          border-color: rgba(96, 165, 250, 0.4);
          background: rgba(17, 24, 39, 1);
          box-shadow: 0 0 12px rgba(96, 165, 250, 0.2);
        }}
        
        .search-box input::placeholder {{
          color: #64748b;
        }}
        
        .search-box button {{
          padding: 10px 16px;
          border-radius: 8px;
          border: 1px solid rgba(96, 165, 250, 0.3);
          background: linear-gradient(135deg, rgba(96, 165, 250, 0.1) 0%, rgba(6, 182, 212, 0.05) 100%);
          color: #60a5fa;
          cursor: pointer;
          font-weight: 500;
          font-size: 13px;
          transition: all 0.3s ease;
        }}
        
        .search-box button:hover {{
          background: linear-gradient(135deg, rgba(96, 165, 250, 0.2) 0%, rgba(6, 182, 212, 0.1) 100%);
          border-color: rgba(96, 165, 250, 0.4);
        }}
        
        .controls-group {{
          display: flex;
          gap: 20px;
          align-items: center;
          flex-wrap: wrap;
        }}
        
        .filter-section {{
          display: flex;
          gap: 10px;
          align-items: center;
        }}
        
        .filter-label {{
          font-size: 13px;
          color: #94a3b8;
          font-weight: 500;
        }}
        
        .filters {{
          display: flex;
          gap: 6px;
        }}
        
        .filter-btn {{
          font-size: 13px;
          padding: 8px 12px;
          border-radius: 6px;
          border: 1px solid rgba(96, 165, 250, 0.2);
          color: #94a3b8;
          text-decoration: none;
          transition: all 0.3s ease;
          cursor: pointer;
        }}
        
        .filter-btn:hover {{
          border-color: rgba(96, 165, 250, 0.3);
          background: rgba(96, 165, 250, 0.05);
          color: #60a5fa;
        }}
        
        .filter-btn.active {{
          background: linear-gradient(135deg, rgba(6, 182, 212, 0.3) 0%, rgba(96, 165, 250, 0.2) 100%);
          border-color: rgba(96, 165, 250, 0.4);
          color: #60a5fa;
          font-weight: 500;
        }}
        
        .actions {{
          display: flex;
          gap: 8px;
        }}
        
        .btn-primary {{
          display: inline-flex;
          align-items: center;
          gap: 6px;
          font-size: 13px;
          padding: 10px 14px;
          border-radius: 8px;
          border: 1px solid transparent;
          background: linear-gradient(135deg, #06b6d4 0%, #0ea5e9 100%);
          color: #fff;
          text-decoration: none;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.3s ease;
          box-shadow: 0 4px 12px rgba(6, 181, 212, 0.3);
        }}
        
        .btn-primary:hover {{
          box-shadow: 0 6px 20px rgba(6, 181, 212, 0.4);
          transform: translateY(-2px);
        }}
        .grid {{
          display: grid;
          grid-template-columns: repeat(auto-fit,minmax(260px,1fr));
          gap: 14px;
          margin-top: 10px;
        }}
        .card {{
          background: radial-gradient(circle at top left,#111827 0,#020617 55%);
          border-radius: 14px;
          border: 1px solid #111827;
          padding: 12px 14px 12px;
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
          border:1px solid #22c55e;
        }}
        .pill-active {{
          background:#16a34a33;
          border-color:#22c55e;
          color:#bbf7d0;
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
        @media (max-width:640px) {{
          .top-bar {{
            flex-direction:column;
            align-items:flex-start;
          }}
          .top-nav {{
            flex-direction:column;
            align-items:flex-start;
            gap:4px;
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

          <div class="top-bar">
            <div class="search-wrapper">
              <form class="search-box" method="GET" action="/">
                <input type="hidden" name="pwd" value="{pwd}">
                <input type="text" name="q" placeholder="🔍 搜索项目…" value="{q}">
                <button type="submit">搜索</button>
              </form>
            </div>

            <div class="controls-group">
              <div class="filter-section">
                <span class="filter-label">分类：</span>
                <div class="filters">
                  <a href="/?pwd={pwd}&cat=all" class="filter-btn {active_all}">全部</a>
                  <a href="/?pwd={pwd}&cat=custom" class="filter-btn {active_custom}">自定义</a>
                  <a href="/?pwd={pwd}&cat=trending" class="filter-btn {active_trending}">热度Top</a>
                </div>
              </div>

              <div class="actions">
                <a href="/manage?pwd={pwd}" class="btn-primary">⚙️ 项目管理</a>
              </div>
            </div>
          </div>

          <div class="grid">
            {cards}
          </div>

        </div>
      </div>
    </body>
    </html>
    """.format(
        last_utc8=last_utc8,
        pwd=cfg["webui_password"],
        q=q,
        active_all=active_all,
        active_custom=active_custom,
        active_trending=active_trending,
        cards=cards
        or '<div style="color:#9ca3af;font-size:13px;">当前没有任何项目。</div>',
    )
    return html


@app.route("/manage")
def manage():
    cfg = load_config()
    pwd = request.args.get("pwd", "")
    if pwd != cfg.get("webui_password"):
        return "Unauthorized", 401

    rows = ""
    for i, p in enumerate(cfg.get("projects", [])):
        name = p.get("name", "")
        alias = p.get("alias", "")
        cat = p.get("category", "custom")
        rows += "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            i, name, alias, cat
        )

    if not rows:
        rows = '<tr><td colspan="4">暂无项目，请在上方操作面板中添加。</td></tr>'

    method = (cfg.get("notify_method") or "none").lower()
    tg_bot = cfg.get("telegram_bot_token", "")
    tg_chat = cfg.get("telegram_chat_id", "")
    discord = cfg.get("discord_webhook_url", "")

    sel_none = "selected" if method == "none" else ""
    sel_tg = "selected" if method == "telegram" else ""
    sel_dc = "selected" if method == "discord" else ""
    sel_both = "selected" if method == "both" else ""

    html = """
    <html>
    <head>
      <meta charset="utf-8" />
      <title>NTX Quest Radar · 项目管理</title>
      <style>
        body {{
          margin: 0;
          padding: 0;
          background: #020617;
          color: #e5e7eb;
          font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;
        }}
        .shell {{
          min-height: 100vh;
          background: radial-gradient(circle at top right, #0f172a 0%, #020617 40%, #000 100%);
          position: relative;
        }}
        
        .shell::before {{
          content: '';
          position: fixed;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          background: radial-gradient(circle at 20% 50%, rgba(6, 182, 212, 0.05) 0%, transparent 50%);
          pointer-events: none;
          z-index: 0;
        }}
        .container {{
          max-width: 960px;
          margin: 0 auto;
          padding: 20px 16px 40px;
          position: relative;
          z-index: 1;
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
        a {{ color:#60a5fa; text-decoration:none; }}
        a:hover {{ text-decoration:underline; }}
        .card {{
          background: linear-gradient(135deg, rgba(17, 24, 39, 0.8) 0%, rgba(2, 6, 23, 0.95) 100%);
          border-radius: 12px;
          border: 1px solid rgba(96, 165, 250, 0.1);
          padding: 14px 16px 16px;
          box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6), inset 0 1px 0 rgba(96, 165, 250, 0.1);
          margin-bottom: 14px;
          transition: all 0.3s ease;
          backdrop-filter: blur(10px);
        }}
        
        .card:hover {{
          border-color: rgba(96, 165, 250, 0.2);
          box-shadow: 0 12px 40px rgba(6, 182, 212, 0.15), inset 0 1px 0 rgba(96, 165, 250, 0.15);
          transform: translateY(-2px);
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
          white-space: nowrap;
        }}
        th {{
          font-weight:500;
          color:#9ca3af;
          background:#020617;
        }}
        tr:hover td {{
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
        .form-row input, .form-row textarea {{
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
        .form-row select {{
          background:#020617;
          border-radius:8px;
          border:1px solid #1f2937;
          padding:6px 10px;
          color:#e5e7eb;
          font-size:12px;
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
        @media (max-width:640px) {{
          .form-row {{
            flex-direction:column;
            align-items:flex-start;
          }}
          .top-nav {{
            flex-direction:column;
            align-items:flex-start;
            gap:4px;
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

        <!-- 顶部操作面板 -->
        <div class="card">
          <div class="card-header">
            <div class="card-title">操作面板</div>
            <a class="pill-back" href="/?pwd={pwd}">← 返回监控首页</a>
          </div>

          <!-- 单个添加 -->
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
            <div class="hint">Alias 通常可以从 Space URL 中看到（app.galxe.com/space/&lt;alias&gt;）。</div>
          </form>

          <!-- 批量导入 -->
          <form method="POST" action="/add_bulk" style="margin-top:12px;">
            <input type="hidden" name="pwd" value="{pwd}">
            <div class="form-row">
              <label>批量导入</label>
              <textarea name="bulk" placeholder="每行一个：支持三种格式：
1) alias
2) name,alias
3) name,alias,category（如：BNB Chain,bnbchain,trending）"></textarea>
              <button type="submit" class="btn">批量导入</button>
            </div>
            <div class="hint">
              示例：<br>
              <code>bnbchain</code><br>
              <code>Arbitrum,arbitrum</code><br>
              <code>OKX Web3,okxweb3,trending</code>
            </div>
          </form>

          <!-- 删除项目 -->
          <form method="GET" action="/delete" style="margin-top:12px;">
            <input type="hidden" name="pwd" value="{pwd}">
            <div class="form-row">
              <label>删除项目（按索引）</label>
              <input name="idx" placeholder="在下方表格中查看索引，例如：0">
              <button type="submit" class="btn">删除</button>
            </div>
            <div class="hint">删除后会立即保存，无需重启程序。</div>
          </form>

          <!-- 通知配置 -->
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
              <label>Telegram Bot Token</label>
              <input name="telegram_bot_token" value="{tg_bot}" placeholder="形如：123456:ABC-DEF...">
              <label>Telegram Chat ID</label>
              <input name="telegram_chat_id" value="{tg_chat}" placeholder="你的 chat id">
            </div>
            <div class="form-row">
              <label>Discord Webhook URL</label>
              <input style="flex:1;min-width:260px;" name="discord_webhook_url" value="{discord}" placeholder="https://discord.com/api/webhooks/...">
            </div>
            <div class="hint">
              说明：通知方式可选 none / telegram / discord / both。建议先保存配置，然后点击“发送测试通知”确认是否能收到消息。
            </div>
          </form>
        </div>

        <!-- 当前项目列表 -->
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
    """.format(
        rows=rows,
        pwd=cfg["webui_password"],
        sel_none=sel_none,
        sel_tg=sel_tg,
        sel_dc=sel_dc,
        sel_both=sel_both,
        tg_bot=tg_bot,
        tg_chat=tg_chat,
        discord=discord,
    )
    return html


@app.route("/add")
def add():
    cfg = load_config()
    pwd = request.args.get("pwd", "")
    if pwd != cfg.get("webui_password"):
        return "Unauthorized", 401

    name = (request.args.get("name") or "").strip()
    alias = (request.args.get("alias") or "").strip()
    category = (request.args.get("category") or "custom").strip() or "custom"

    if not name or not alias:
        return "缺少 name 或 alias"

    cfg.setdefault("projects", []).append(
        {"name": name, "alias": alias, "category": category}
    )
    save_config(cfg)
    return "添加成功：{} ({}) [{}] · <a href='/?pwd={}'>返回首页</a>".format(
        name, alias, category, cfg["webui_password"]
    )


@app.route("/add_bulk", methods=["GET", "POST"])
def add_bulk():
    cfg = load_config()
    pwd = request.values.get("pwd", "")
    if pwd != cfg.get("webui_password"):
        return "Unauthorized", 401

    text = (request.values.get("bulk") or "").strip()
    if not text:
        return "未收到任何内容 · <a href='/manage?pwd={}'>返回管理页面</a>".format(
            cfg["webui_password"]
        )

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

        cfg.setdefault("projects", []).append(
            {"name": name, "alias": alias, "category": category}
        )
        added += 1

    save_config(cfg)
    return "批量添加完成，共添加 {} 个项目。<a href='/?pwd={}'>返回首页</a>".format(
        added, cfg["webui_password"]
    )


@app.route("/delete")
def delete():
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
        return "已删除：{} ({}) · <a href='/?pwd={}'>返回首页</a>".format(
            removed.get("name"), removed.get("alias"), cfg["webui_password"]
        )
    else:
        return "索引超出范围"


@app.route("/save_notify", methods=["POST"])
def save_notify():
    cfg = load_config()
    pwd = request.form.get("pwd", "")
    if pwd != cfg.get("webui_password"):
        return "Unauthorized", 401

    method = (request.form.get("notify_method") or "none").lower()
    tg_bot = request.form.get("telegram_bot_token") or ""
    tg_chat = request.form.get("telegram_chat_id") or ""
    discord = request.form.get("discord_webhook_url") or ""

    cfg["notify_method"] = method
    cfg["telegram_bot_token"] = tg_bot
    cfg["telegram_chat_id"] = tg_chat
    cfg["discord_webhook_url"] = discord
    save_config(cfg)

    return "通知配置已保存（当前：{}）。<a href='/manage?pwd={}'>返回管理页面</a>".format(
        method, cfg["webui_password"]
    )


@app.route("/notify_test")
def notify_test():
    cfg = load_config()
    pwd = request.args.get("pwd", "")
    if pwd != cfg.get("webui_password"):
        return "Unauthorized", 401

    method = (cfg.get("notify_method") or "none").lower()
    if method == "none":
        return "当前 notify_method=none，未发送通知。请先在管理页修改为 telegram/discord/both。<a href='/manage?pwd={}'>返回管理页面</a>".format(
            cfg["webui_password"]
        )

    text = "【NTX Quest Radar】这是一条测试通知，用于验证 Telegram / Discord 配置是否正常。"
    if method in ("telegram", "both"):
        send_telegram(cfg, text)
    if method in ("discord", "both"):
        send_discord(cfg, text)

    return "已按当前通知方式 ({}) 发送一条测试消息。<a href='/manage?pwd={}'>返回管理页面</a>".format(
        method, cfg["webui_password"]
    )


@app.route("/raw")
def raw():
    cfg = load_config()
    pwd = request.args.get("pwd", "")
    if pwd != cfg.get("webui_password"):
        return "Unauthorized", 401

    return app.response_class(
        response=json.dumps(monitor_state, indent=2, ensure_ascii=False),
        mimetype="application/json",
    )


def start_monitor():
    t = threading.Thread(target=monitor_loop, daemon=True)
    t.start()


if __name__ == "__main__":
    os.makedirs(ROOT, exist_ok=True)
    ensure_config()
    cfg = load_config()

    print("=== NTX Quest Radar V4.0（UI + 时间显示优化版） ===")
    print("Web UI 密码:", cfg.get("webui_password"))
    print("访问: http://服务器IP:{}/?pwd={}".format(cfg["webui_port"], cfg["webui_password"]))

    # 禁用后台监控线程（API 可能不可用），直接使用文件中的数据
    # start_monitor()
    app.run(host="0.0.0.0", port=cfg["webui_port"], debug=False)

# ===== NTX 扩展：提供统一 JSON 接口 /api/raw =====
# 说明：
# - 前端只调用 /api/raw?pwd=admin
# - 不再依赖 /?raw=1 避免返回 HTML 的问题

try:
    from flask import request
except ImportError:
    # 如果前面已经 import 过，就忽略这里
    pass


@app.route("/api/raw")
def api_raw():
    """给 NTX QUEST RADAR 使用的 JSON 输出。"""
    pwd = (request.args.get("pwd") or "").strip()
    try:
        expected = config.data.get("webui_password", "")
    except Exception:
        expected = ""

    if expected and pwd != expected:
        return jsonify({"error": "unauthorized"}), 401

    # 直接复用全局 monitor_state（之前版本里已经在不断刷新）
    try:
        global monitor_state
        if isinstance(monitor_state, dict) and monitor_state:
            return jsonify(monitor_state)
    except Exception:
        pass

    # 兜底：避免 500，至少给一个空结构
    return jsonify({"projects": [], "last_loop": None})

# ======================================
# 活动状态归一 & Space 排序工具函数（NTX Quest Radar）
# ======================================
from datetime import datetime, timezone

# 状态权重：数值越小优先级越高
STATUS_WEIGHT = {
    "ongoing": 0,   # 进行中
    "upcoming": 1,  # 即将开始
    "unknown": 2,   # 未知（你首页的橙色）
    "ended": 3,     # 已结束（红色）
    "error": 4,     # 拉取失败
}

def get_status_weight(status: str) -> int:
    """
    根据状态字符串返回排序用的权重。
    未知状态默认当成 unknown。
    """
    if not status:
        return STATUS_WEIGHT["unknown"]
    return STATUS_WEIGHT.get(status, STATUS_WEIGHT["unknown"])


def _to_datetime(value):
    """
    尝试把各种格式的时间转换成带 tz 的 datetime:
    - int/float: 认为是秒级时间戳
    - str: 尝试按 ISO8601 解析
    解析失败返回 None
    """
    if value is None:
        return None

    # 数字时间戳
    if isinstance(value, (int, float)):
        try:
            # 兼容毫秒级：大于 10^12 基本可以认为是毫秒
            if value > 10**12:
                value = value / 1000.0
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except Exception:
            return None

    # 字符串时间
    if isinstance(value, str):
        try:
            # 兼容结尾 Z
            if value.endswith("Z"):
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            # 没有 tz 信息的，一律当成 UTC
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None

    return None


def normalize_campaign_status(status_raw=None, start_time=None, end_time=None) -> str:
    """
    把活动状态归一成：
    - ongoing   进行中
    - upcoming  未开始
    - ended     明确结束
    - unknown   无法判断 / 取数失败 / 没活动

    关键原则：❗只有在“明确知道已结束”的情况下才标记 ended，
    否则一律 unknown，避免大量误判为已结束。
    """
    # 先看原始状态（如果 Galxe 有返回）
    if isinstance(status_raw, str):
        sr = status_raw.lower()
        if any(k in sr for k in ["ongoing", "active", "running", "live"]):
            return "ongoing"
        if any(k in sr for k in ["upcoming", "not_started", "pending"]):
            return "upcoming"
        if any(k in sr for k in ["ended", "expired", "closed", "finished"]):
            return "ended"

    # 再用时间判断
    st = _to_datetime(start_time)
    et = _to_datetime(end_time)
    now = datetime.now(timezone.utc)

    # 有结束时间且明确早于现在 → ended
    if et is not None and et < now:
        return "ended"

    # 有开始时间但晚于现在 → upcoming
    if st is not None and st > now:
        return "upcoming"

    # 有开始时间且（没有结束时间 或 结束时间晚于现在）→ ongoing
    if st is not None and (et is None or et >= now):
        return "ongoing"

    # 其它情况一律 unknown（宁可未知，也不要误判结束）
    return "unknown"


def sort_spaces_for_frontend(spaces: list) -> list:
    """
    对 Space 列表做统一排序：
    1）按状态权重：
        ongoing > upcoming > unknown > ended > error
    2）同一状态内按时间倒序：
        - 优先用 last_campaign_time
        - 其次用 updated_at
        - 都没有时当 0 处理
    说明：不修改原列表，返回一个新列表。
    """

    def _ts(v):
        # 支持 int/float/str，统一转成时间戳（秒）
        dt = _to_datetime(v)
        if dt is None:
            return 0
        return int(dt.timestamp())

    def _key(s):
        status = s.get("status") or "unknown"
        weight = get_status_weight(status)

        # 你这里字段名如果不同，可以按自己实际字段改：
        ts_raw = (
            s.get("last_campaign_time")
            or s.get("latest_campaign_time")
            or s.get("updated_at")
            or 0
        )
        ts = _ts(ts_raw)

        # 注意：时间倒序 ⇒ 用负号
        return (weight, -ts)

    return sorted(spaces, key=_key)


# ======================================
# 活动状态归一 & Space 排序工具函数（NTX Quest Radar）
# ======================================
from datetime import datetime, timezone

STATUS_WEIGHT = {
    "ongoing": 0,
    "upcoming": 1,
    "unknown": 2,
    "ended": 3,
    "error": 4,
}

def get_status_weight(status: str) -> int:
    if not status:
        return STATUS_WEIGHT["unknown"]
    return STATUS_WEIGHT.get(status, STATUS_WEIGHT["unknown"])

def _to_datetime(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            if value > 10**12:
                value = value / 1000.0
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except:
            return None
    if isinstance(value, str):
        try:
            if value.endswith("Z"):
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except:
            return None
    return None

def normalize_campaign_status(status_raw=None, start_time=None, end_time=None):
    if isinstance(status_raw, str):
        sr = status_raw.lower()
        if any(k in sr for k in ["ongoing", "active", "running", "live"]):
            return "ongoing"
        if any(k in sr for k in ["upcoming", "pending", "not_started"]):
            return "upcoming"
        if any(k in sr for k in ["ended", "expired", "closed"]):
            return "ended"

    st = _to_datetime(start_time)
    et = _to_datetime(end_time)
    now = datetime.now(timezone.utc)

    if et is not None and et < now:
        return "ended"
    if st is not None and st > now:
        return "upcoming"
    if st is not None and (et is None or et >= now):
        return "ongoing"

    return "unknown"

def sort_spaces_for_frontend(spaces: list) -> list:
    def _ts(v):
        dt = _to_datetime(v)
        return int(dt.timestamp()) if dt else 0

    def _key(s):
        weight = get_status_weight(s.get("status"))
        ts_raw = (
            s.get("last_campaign_time")
            or s.get("updated_at")
            or 0
        )
        return (weight, -_ts(ts_raw))

    return sorted(spaces, key=_key)


# ======================================
# 重写 Space 状态构建逻辑补丁
# 这个方法会被你现有代码调用
# ======================================
def build_space_status(space, campaign):
    """
    统一给 space 设置 status & last_campaign_time
    """
    if not campaign:
        space["latest_campaign"] = None
        space["status"] = "unknown"
        space["last_campaign_time"] = None
        return space

    space["latest_campaign"] = campaign
    space["status"] = normalize_campaign_status(
        status_raw=campaign.get("status"),
        start_time=campaign.get("start_time") or campaign.get("startTime"),
        end_time=campaign.get("end_time") or campaign.get("endTime"),
    )

    space["last_campaign_time"] = (
        campaign.get("end_time")
        or campaign.get("endTime")
        or campaign.get("start_time")
        or campaign.get("startTime")
    )

    return space


# ======================================
# API 输出前全局排序补丁
# ======================================
from flask import after_this_request

@app.after_request
def apply_space_sorting(response):
    """
    自动检查返回是否包含 space 列表，
    如果是，则按 NTX 排序规则排序：
    ongoing > upcoming > unknown > ended
    """
    try:
        data = response.get_json()
        if isinstance(data, dict) and "spaces" in data:
            spaces = data["spaces"]
            if isinstance(spaces, list):
                data["spaces"] = sort_spaces_for_frontend(spaces)
                response.set_data(json.dumps(data, ensure_ascii=False))
    except Exception as e:
        print("Sort patch error:", e)

    return response


# ==== 覆盖 _build_status，修正状态判定逻辑 ====
def _build_status(latest):
    """
    根据 startTime / endTime 计算状态：未开始 / 进行中 / 已结束 / 未知（新版，避免误判）
    关键原则：宁可判成“未知”，也不要乱判“已结束”。
    """
    if not latest:
        return "🟠 未知"

    # 兼容多种字段命名：startTime / start_time, endTime / end_time
    now = datetime.utcnow().replace(tzinfo=timezone.utc)
    start = _parse_ts(latest.get("startTime") or latest.get("start_time"))
    end = _parse_ts(latest.get("endTime") or latest.get("end_time"))

    # 1️⃣ 未开始：有开始时间且在未来
    if start and now < start:
        return "⏳ 未开始"

    # 2️⃣ 进行中：有开始时间，且（没有结束时间 或 结束时间在未来）
    if start and (not end or now <= end):
        return "✅ 进行中"

    # 3️⃣ 已结束：有结束时间且在过去
    if end and now > end:
        return "🔴 已结束"

    # 4️⃣ 其它所有情况（时间缺失 / 解析失败等）一律标为“未知”
    return "🟠 未知"


# ==== 再次覆盖 _build_status，调整状态图标以修正排序顺序 ====
def _build_status(latest):
    """
    根据 startTime / endTime 计算状态：未开始 / 进行中 / 已结束 / 未知（排序友好版）

    目标排序（按状态字符串默认排序时）：
      ⏳ 未开始
      ✅ 进行中
      ⚪ 未知   ← 要排在 🔴 已结束 前面
      🔴 已结束
    """
    if not latest:
        return "⚪ 未知"

    # 兼容多种字段命名：startTime / start_time, endTime / end_time
    now = datetime.utcnow().replace(tzinfo=timezone.utc)
    start = _parse_ts(latest.get("startTime") or latest.get("start_time"))
    end = _parse_ts(latest.get("endTime") or latest.get("end_time"))

    # 未开始：有开始时间且在未来
    if start and now < start:
        return "⏳ 未开始"

    # 进行中：有开始时间，且（没有结束时间 或 结束时间在未来）
    if start and (not end or now <= end):
        return "✅ 进行中"

    # 已结束：有结束时间且在过去
    if end and now > end:
        return "🔴 已结束"

    # 其它所有情况一律未知（宁可未知，也不要乱判已结束）
    return "⚪ 未知"


# ==== 覆盖 _ntx_status_group：调整排序优先级 ====
def _ntx_status_group(p):
    """
    根据状态分组排序优先级：
      0 - 进行中
      1 - 未开始 / 即将开始
      2 - 未知（⚪ / 🟠）
      3 - 已结束
      4 - 其它异常
    """
    latest = p.get("latest") or {}
    status = _build_status(latest) or ""

    if "进行中" in status:
        return 0
    if ("未开始" in status) or ("即将开始" in status):
        return 1
    if "未知" in status:
        return 2
    if "已结束" in status or "结束" in status:
        return 3
    return 4


# ==== 最终覆盖 _build_status：兼顾视觉 + 排序（未知排在已结束前） ====
def _build_status(latest):
    """
    根据 startTime / endTime 计算状态：未开始 / 进行中 / 已结束 / 未知（排序友好最终版）

    视觉展示：
      ⏳ 未开始
      ✅ 进行中
      🔴 已结束
      ⚪ 未知 · 即将开始

    排序逻辑（由 _ntx_status_group 决定）：
      0 - 包含“进行中”的状态
      1 - 包含“未开始”或“即将开始”的状态
      2 - 包含“已结束”/“结束”的状态
      3 - 其它（不会命中）
    """
    if not latest:
        # 同时包含“未知”和“即将开始”，
        # CSS 会命中“未知”，排序会命中“即将开始”（组 1，排在已结束前）
        return "⚪ 未知 · 即将开始"

    now = datetime.utcnow().replace(tzinfo=timezone.utc)
    start = _parse_ts(latest.get("startTime") or latest.get("start_time"))
    end = _parse_ts(latest.get("endTime") or latest.get("end_time"))

    # 未开始
    if start and now < start:
        return "⏳ 未开始"

    # 进行中
    if start and (not end or now <= end):
        return "✅ 进行中"

    # 已结束
    if end and now > end:
        return "🔴 已结束"

    # 其它不确定情况，当成“未知 · 即将开始”
    return "⚪ 未知 · 即将开始"


# ==== NTX 全局排序补丁：接管项目列表的 sorted 行为 ====
import builtins as _ntx_builtins
_original_sorted = _ntx_builtins.sorted

def sorted(iterable, key=None, reverse=False):
    """
    NTX Patch:
      - 对“Galxe Space 项目列表”（元素为 dict，且包含 alias/category/latest 字段）
        应用自定义排序规则：
          1. 按状态分组：进行中 > 未开始/即将开始 > 未知 > 已结束 > 其它
          2. 同组内：trending 在前，custom 在后
          3. 再按 startTime 倒序
          4. 再按名称字母序
      - 对其它类型的数据，完全保持原生 sorted 行为不变。
    """
    try:
        # 先把 iterable 拷成列表，避免多次遍历导致问题
        it = list(iterable)

        # 判定是不是“项目列表”：第一个元素是 dict，且包含几个关键字段
        if it and isinstance(it[0], dict) and {"alias", "category", "latest"} <= set(it[0].keys()):
            def _project_key(p):
                latest = p.get("latest") or {}
                status = _build_status(latest) or ""

                # 1️⃣ 按状态分组
                if "进行中" in status:
                    group = 0
                elif ("未开始" in status) or ("即将开始" in status):
                    group = 1
                elif "未知" in status:
                    group = 2
                elif "已结束" in status or "结束" in status:
                    group = 3
                else:
                    group = 4

                # 2️⃣ trending 优先
                trending_rank = 0 if p.get("category") == "trending" else 1

                # 3️⃣ 按 startTime 倒序
                latest_ts = 0
                try:
                    latest_ts = int((latest.get("startTime") or 0) or 0)
                except Exception:
                    latest_ts = 0

                # 4️⃣ 名称字母序
                name = (p.get("name") or "").lower()

                return (group, trending_rank, -latest_ts, name)

            return _original_sorted(it, key=_project_key, reverse=False)

        # 非项目列表 → 原样走系统 sorted
        return _original_sorted(it, key=key, reverse=reverse)

    except Exception:
        # 出现任何异常都兜底回原生行为，避免影响其它逻辑
        return _original_sorted(iterable, key=key, reverse=reverse)


# ==== NTX 最终排序补丁：全局接管项目列表的排序逻辑 ====
import builtins as _ntx_builtins

# 保存原始 sorted
_ntx_original_sorted = _ntx_builtins.sorted

def _ntx_is_project_list(it):
    """
    判断 iterable 是否为 Galxe 项目列表：
    元素为 dict 且包含 alias / category / latest 字段
    """
    if not it:
        return False
    first = it[0]
    return isinstance(first, dict) and all(
        k in first for k in ("alias", "category", "latest")
    )

def _ntx_project_sort_key(p):
    """
    项目列表排序规则：
      0 - 未开始 / 即将开始
      1 - 进行中
      2 - 未知
      3 - 已结束
      4 - 其它异常
    同组内：
      - trending 在前
      - startTime 越新越靠前
      - 名称字母序
    """
    latest = p.get("latest") or {}
    status = _build_status(latest) or ""

    # 状态分组：你说“未开始 / 即将开始应该排第 1”，所以放在 group 0
    if ("未开始" in status) or ("即将开始" in status):
        group = 0
    elif "进行中" in status:
        group = 1
    elif "未知" in status:
        group = 2
    elif "已结束" in status or "结束" in status:
        group = 3
    else:
        group = 4

    # trending 优先
    trending_rank = 0 if p.get("category") == "trending" else 1

    # 时间：startTime / createdAt 越新越靠前
    ts = 0
    try:
        ts = int(
            (latest.get("startTime")
             or latest.get("createdAt")
             or 0)
            or 0
        )
    except Exception:
        ts = 0

    name = (p.get("name") or "").lower()

    return (group, trending_rank, -ts, name)

def _ntx_sorted(iterable, key=None, reverse=False):
    """
    新的全局 sorted：
      - 如果是项目列表 → 使用 _ntx_project_sort_key
      - 其它情况 → 完全走原始 sorted 行为
    """
    try:
        it = list(iterable)
    except TypeError:
        # 不可多次遍历的，直接走原始 sorted
        return _ntx_original_sorted(iterable, key=key, reverse=reverse)

    if _ntx_is_project_list(it):
        return _ntx_original_sorted(it, key=_ntx_project_sort_key, reverse=False)

    # 非项目列表，保持原样
    return _ntx_original_sorted(it, key=key, reverse=reverse)

# 覆盖内建 sorted
_ntx_builtins.sorted = _ntx_sorted
# 覆盖模块级 sorted（index 里的 sorted() 也会用这个）
sorted = _ntx_sorted


# ==== NTX 首页重写：接管排序 & 渲染逻辑 ====

def _ntx_sort_projects(projs):
    """
    统一排序规则：
      0 - 未开始 / 即将开始
      1 - 进行中
      2 - 未知
      3 - 已结束
      4 - 其它异常
    同组内：
      - trending 在前
      - startTime 越新越靠前
      - 名称字母序
    """
    def _key(p):
        latest = p.get("latest") or {}
        status = _build_status(latest) or ""

        # 状态分组：你说“未开始/即将开始应该排第 1”，所以放在 group 0
        if ("未开始" in status) or ("即将开始" in status):
            group = 0
        elif "进行中" in status:
            group = 1
        elif "未知" in status:
            group = 2
        elif "已结束" in status or "结束" in status:
            group = 3
        else:
            group = 4

        # trending 优先
        trending_rank = 0 if p.get("category") == "trending" else 1

        # 时间：startTime / createdAt 越新越靠前
        ts = 0
        try:
            ts = int(
                (latest.get("startTime")
                 or latest.get("createdAt")
                 or 0)
                or 0
            )
        except Exception:
            ts = 0

        name = (p.get("name") or "").lower()

        return (group, trending_rank, -ts, name)

    return sorted(projs, key=_key)


def _ntx_index_override():
    """
    新首页逻辑：
      - 校验密码
      - 处理搜索 q / 分类 cat
      - 使用 _ntx_sort_projects 排序
      - 用原来的 card_html 生成卡片
    """
    cfg = load_config()
    pwd = request.args.get("pwd", "")
    if pwd != cfg.get("webui_password"):
        return "Unauthorized", 401

    q = (request.args.get("q") or "").lower()
    cat = (request.args.get("cat") or "all").lower()

    projs = monitor_state.get("projects", []) or []

    # 搜索过滤
    if q:
        filtered = []
        for p in projs:
            if q in (p.get("name", "").lower()) or q in (p.get("alias", "").lower()):
                filtered.append(p)
        projs = filtered

    # 分类过滤
    if cat in ("custom", "trending"):
        projs = [p for p in projs if p.get("category") == cat]

    # 统一排序
    sorted_projs = _ntx_sort_projects(projs)
    cards = "".join(card_html(p) for p in sorted_projs)
    last = monitor_state.get("last_loop", "")
    last_utc8 = format_time_utc8(last)

    active_all = "active" if cat == "all" else ""
    active_custom = "active" if cat == "custom" else ""
    active_trending = "active" if cat == "trending" else ""

    html = f"""
    <html>
    <head>
      <meta charset="utf-8" />
      <title>NTX Quest Radar 控制台</title>
      <style>
        body {{
          margin: 0;
          padding: 0;
          background: #020617;
          color: #e5e7eb;
          font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;
        }}
        .shell {{
          min-height: 100vh;
          background: radial-gradient(circle at top left,#0b1120 0,#020617 45%);
        }}
        .header {{
          padding: 16px 24px;
          display: flex;
          justify-content: space-between;
          align-items: center;
          border-bottom: 1px solid #1f2937;
        }}
        .title {{
          font-size: 20px;
          font-weight: 600;
        }}
        .tabs {{
          display: flex;
          gap: 12px;
        }}
        .tab {{
          padding: 6px 12px;
          border-radius: 999px;
          border: 1px solid #4b5563;
          font-size: 13px;
          cursor: pointer;
          text-decoration: none;
          color: #9ca3af;
        }}
        .tab.active {{
          background: #f97316;
          border-color: #f97316;
          color: #0b1120;
        }}
        .main {{
          padding: 16px 24px 32px 24px;
        }}
        .grid {{
          display: grid;
          grid-template-columns: repeat(auto-fill,minmax(260px,1fr));
          gap: 16px;
        }}
        .card {{
          background: #020617;
          border-radius: 16px;
          border: 1px solid #1f2937;
          padding: 12px 14px 14px 14px;
        }}
        .card-header {{
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 8px;
        }}
        .card-title {{
          font-size: 15px;
          font-weight: 600;
        }}
        .card-sub {{
          font-size: 12px;
          color: #9ca3af;
          margin-top: 2px;
        }}
        .pill {{
          padding: 4px 10px;
          border-radius: 999px;
          font-size: 12px;
          border: 1px solid #4b5563;
          background: #020617;
        }}
        .pill-running {{
          border-color: #22c55e;
          color: #bbf7d0;
          background: rgba(34,197,94,0.1);
        }}
        .pill-upcoming {{
          border-color: #6b7280;
          color: #d1d5db;
          background: rgba(107,114,128,0.1);
        }}
        .pill-ended {{
          border-color: #fb7185;
          color: #fecaca;
          background: rgba(248,113,113,0.08);
        }}
        .pill-unknown {{
          border-color: #f97316;
          color: #fed7aa;
          background: rgba(249,115,22,0.08);
        }}
        .pill-empty {{
          border-style: dashed;
          color: #6b7280;
        }}
        .activity-title {{
          font-size: 13px;
          margin-bottom: 6px;
        }}
        .activity-title a {{
          color: #60a5fa;
          text-decoration: none;
        }}
        .activity-title a:hover {{
          text-decoration: underline;
        }}
        .activity-meta {{
          font-size: 12px;
          color: #9ca3af;
        }}
        .footer {{
          padding: 8px 24px 16px 24px;
          font-size: 12px;
          color: #6b7280;
        }}
      </style>
    </head>
    <body>
      <div class="shell">
        <div class="header">
          <div class="title">NTX Quest Radar 控制台</div>
          <div class="tabs">
            <a class="tab {active_all}" href="/?pwd={pwd}&cat=all">全部</a>
            <a class="tab {active_trending}" href="/?pwd={pwd}&cat=trending">Trending</a>
            <a class="tab {active_custom}" href="/?pwd={pwd}&cat=custom">Custom</a>
          </div>
        </div>
        <div class="main">
          <div class="grid">
            {cards}
          </div>
        </div>
        <div class="footer">
          最近一次轮询：{last}
        </div>
      </div>
    </body>
    </html>
    """
    return html


# 用新的首页逻辑替换原来的 index 视图
try:
    app.view_functions["index"] = _ntx_index_override
except Exception as e:
    print("NTX index override failed:", e)


# ==== NTX V4 专用首页：/v4，采用新的排序逻辑 ====

def _ntx_sort_projects_v4(projs):
    """
    V4 页面专用排序规则：
      0 - 未开始 / 即将开始
      1 - 进行中
      2 - 未知
      3 - 已结束
      4 - 其它异常
    同组内：
      - trending 在前
      - startTime 越新越靠前
      - 名称字母序
    """
    def _key(p):
        latest = p.get("latest") or {}
        status = _build_status(latest) or ""

        # 状态分组：你要求“未开始/即将开始”优先
        if ("未开始" in status) or ("即将开始" in status):
            group = 0
        elif "进行中" in status:
            group = 1
        elif "未知" in status:
            group = 2
        elif "已结束" in status or "结束" in status:
            group = 3
        else:
            group = 4

        trending_rank = 0 if p.get("category") == "trending" else 1

        ts = 0
        try:
            ts = int(
                (latest.get("startTime")
                 or latest.get("createdAt")
                 or 0)
                or 0
            )
        except Exception:
            ts = 0

        name = (p.get("name") or "").lower()

        return (group, trending_rank, -ts, name)

    return sorted(projs, key=_key)


@app.route("/v4")
def index_v4():
    """
    新版活动监控页面（/v4）：
      - 使用 _ntx_sort_projects_v4 排序
      - UI 基本沿用原来的 OpenAPI · V4.0 风格
    """
    cfg = load_config()
    pwd = request.args.get("pwd", "")
    if pwd != cfg.get("webui_password"):
        return "Unauthorized", 401

    q = (request.args.get("q") or "").lower()
    cat = (request.args.get("cat") or "all").lower()

    projs = monitor_state.get("projects", []) or []

    # 搜索过滤
    if q:
        filtered = []
        for p in projs:
            if q in (p.get("name", "").lower()) or q in (p.get("alias", "").lower()):
                filtered.append(p)
        projs = filtered

    # 分类过滤
    if cat in ("custom", "trending"):
        projs = [p for p in projs if p.get("category") == cat]

    # 排序（V4 专用逻辑）
    sorted_projs = _ntx_sort_projects_v4(projs)
    cards = "".join(card_html(p) for p in sorted_projs)
    last = monitor_state.get("last_loop", "")
    last_utc8 = format_time_utc8(last)

    active_all = "active" if cat == "all" else ""
    active_custom = "active" if cat == "custom" else ""
    active_trending = "active" if cat == "trending" else ""

    html = f"""
    <html>
    <head>
      <meta charset="utf-8" />
      <title>NTX Quest Radar 控制台 · V4</title>
      <style>
        body {{
          margin: 0;
          padding: 0;
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
        .top-bar {{
          display: flex;
          flex-direction: column;
          gap: 16px;
          margin-bottom: 20px;
          padding: 16px 20px;
          background: linear-gradient(135deg, rgba(15, 23, 42, 0.6) 0%, rgba(2, 6, 23, 0.8) 100%);
          border: 1px solid rgba(96, 165, 250, 0.1);
          border-radius: 12px;
          box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
          backdrop-filter: blur(10px);
        }}
        
        .search-wrapper {{
          flex: 1;
          max-width: 400px;
        }}
        
        .search-box {{
          display: flex;
          gap: 8px;
          align-items: center;
        }}
        
        .search-box input {{
          flex: 1;
          background: rgba(17, 24, 39, 0.8);
          border-radius: 8px;
          border: 1px solid rgba(96, 165, 250, 0.2);
          padding: 10px 14px;
          color: #e5e7eb;
          outline: none;
          font-size: 13px;
          transition: all 0.3s ease;
        }}
        
        .search-box input:focus {{
          border-color: rgba(96, 165, 250, 0.4);
          background: rgba(17, 24, 39, 1);
          box-shadow: 0 0 12px rgba(96, 165, 250, 0.2);
        }}
        
        .search-box input::placeholder {{
          color: #64748b;
        }}
        
        .search-box button {{
          padding: 10px 16px;
          border-radius: 8px;
          border: 1px solid rgba(96, 165, 250, 0.3);
          background: linear-gradient(135deg, rgba(96, 165, 250, 0.1) 0%, rgba(6, 182, 212, 0.05) 100%);
          color: #60a5fa;
          cursor: pointer;
          font-weight: 500;
          font-size: 13px;
          transition: all 0.3s ease;
        }}
        
        .search-box button:hover {{
          background: linear-gradient(135deg, rgba(96, 165, 250, 0.2) 0%, rgba(6, 182, 212, 0.1) 100%);
          border-color: rgba(96, 165, 250, 0.4);
        }}
        
        .controls-group {{
          display: flex;
          gap: 20px;
          align-items: center;
          flex-wrap: wrap;
        }}
        
        .filter-section {{
          display: flex;
          gap: 10px;
          align-items: center;
        }}
        
        .filter-label {{
          font-size: 13px;
          color: #94a3b8;
          font-weight: 500;
        }}
        
        .filters {{
          display: flex;
          gap: 6px;
        }}
        
        .filter-btn {{
          font-size: 13px;
          padding: 8px 12px;
          border-radius: 6px;
          border: 1px solid rgba(96, 165, 250, 0.2);
          color: #94a3b8;
          text-decoration: none;
          transition: all 0.3s ease;
          cursor: pointer;
        }}
        
        .filter-btn:hover {{
          border-color: rgba(96, 165, 250, 0.3);
          background: rgba(96, 165, 250, 0.05);
          color: #60a5fa;
        }}
        
        .filter-btn.active {{
          background: linear-gradient(135deg, rgba(6, 182, 212, 0.3) 0%, rgba(96, 165, 250, 0.2) 100%);
          border-color: rgba(96, 165, 250, 0.4);
          color: #60a5fa;
          font-weight: 500;
        }}
        
        .actions {{
          display: flex;
          gap: 8px;
        }}
        
        .btn-primary {{
          display: inline-flex;
          align-items: center;
          gap: 6px;
          font-size: 13px;
          padding: 10px 14px;
          border-radius: 8px;
          border: 1px solid transparent;
          background: linear-gradient(135deg, #06b6d4 0%, #0ea5e9 100%);
          color: #fff;
          text-decoration: none;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.3s ease;
          box-shadow: 0 4px 12px rgba(6, 181, 212, 0.3);
        }}
        
        .btn-primary:hover {{
          box-shadow: 0 6px 20px rgba(6, 181, 212, 0.4);
          transform: translateY(-2px);
        }}
        .grid {{
          display: grid;
          grid-template-columns: repeat(auto-fit,minmax(260px,1fr));
          gap: 14px;
          margin-top: 10px;
        }}
        .card {{
          background: radial-gradient(circle at top left,#111827 0,#020617 55%);
          border-radius: 14px;
          border: 1px solid #111827;
          padding: 12px 14px 12px;
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
          border:1px solid #22c55e;
        }}
        .pill-active {{
          background:#16a34a33;
          border-color:#22c55e;
          color:#bbf7d0;
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
        @media (max-width:640px) {{
          .top-bar {{
            flex-direction:column;
            align-items:flex-start;
          }}
          .top-nav {{
            flex-direction:column;
            align-items:flex-start;
            gap:4px;
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
              <a href="/v4?pwd={pwd}" class="active">活动监控</a>
              <a href="/manage?pwd={pwd}">项目管理</a>
            </div>
          </div>

          <div class="subtitle">
            最后刷新：{last_utc8}
          </div>

          <div class="top-bar">
            <form class="search-box" method="GET" action="/v4">
              <input type="hidden" name="pwd" value="{pwd}">
              <input type="text" name="q" placeholder="搜索 Space 名称或 alias…" value="{q}">
              <button type="submit">搜索</button>
            </form>

            <div class="filters">
              <a href="/v4?pwd={pwd}&cat=all" class="{active_all}">全部</a>
              <a href="/v4?pwd={pwd}&cat=custom" class="{active_custom}">自定义</a>
              <a href="/v4?pwd={pwd}&cat=trending" class="{active_trending}">热度Top</a>
            </div>

            <div class="actions">
              <a href="/manage?pwd={pwd}" class="primary">项目管理</a>
            </div>
          </div>

          <div class="grid">
            {cards}
          </div>

        </div>
      </div>
    </body>
    </html>
    """
    return html


# ==== 产品化顶部版本的 V4 首页：重写 /v4 视图 ====
@app.route("/v4")
def index_v4():
    cfg = load_config()
    pwd = request.args.get("pwd", "")
    if pwd != cfg.get("webui_password"):
        return "Unauthorized", 401

    q = (request.args.get("q") or "").lower()
    cat = (request.args.get("cat") or "all").lower()

    projs = monitor_state.get("projects", []) or []

    # 搜索过滤
    if q:
        filtered = []
        for p in projs:
            if q in (p.get("name", "").lower()) or q in (p.get("alias", "").lower()):
                filtered.append(p)
        projs = filtered

    # 分类过滤
    if cat in ("custom", "trending"):
        projs = [p for p in projs if p.get("category") == cat]

    # 排序（先用你现在的逻辑，有需要我们后面再细调）
    try:
        sorted_projs = _ntx_sort_projects_v4(projs)
    except Exception:
        sorted_projs = projs

    cards = "".join(card_html(p) for p in sorted_projs)
    last = monitor_state.get("last_loop", "")
    last_utc8 = format_time_utc8(last)

    active_all = "active" if cat == "all" else ""
    active_custom = "active" if cat == "custom" else ""
    active_trending = "active" if cat == "trending" else ""

    html = f"""
    <html>
    <head>
      <meta charset="utf-8" />
      <title>NTX Quest Radar · OpenAPI V4</title>
      <style>
        body {{
          margin: 0;
          padding: 0;
          background: #020617;
          color: #e5e7eb;
          font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;
        }}
        .shell {{
          min-height: 100vh;
          background: radial-gradient(circle at top left,#0b1120 0,#020617 45%);
        }}
        .container {{
          max-width: 1180px;
          margin: 0 auto;
          padding: 20px 20px 40px;
        }}

        /* ===== 顶部产品区 ===== */
        .app-header {{
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          gap: 16px;
          margin-bottom: 18px;
        }}
        .app-brand {{
          display: flex;
          gap: 12px;
          align-items: center;
        }}
        .app-logo {{
          width: 40px;
          height: 40px;
          border-radius: 999px;
          background: radial-gradient(circle at 30% 20%,#34d399 0,#059669 40%,#022c22 100%);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 16px;
          font-weight: 700;
          letter-spacing: .5px;
        }}
        .app-logo span {{
          transform: translateY(1px);
        }}
        .app-title-row {{
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 4px;
        }}
        .app-title {{
          font-size: 20px;
          font-weight: 600;
        }}
        .app-version {{
          font-size: 11px;
          padding: 2px 8px;
          border-radius: 999px;
          border: 1px solid #1d4ed8;
          background: #1d4ed822;
          color: #bfdbfe;
        }}
        .app-subline {{
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
          font-size: 11px;
          color: #9ca3af;
        }}
        .app-badge {{
          padding: 2px 8px;
          border-radius: 999px;
          border: 1px solid #1f2937;
          background: #020617;
        }}
        .app-badge.green {{
          border-color:#16a34a;
          background:#16a34a22;
          color:#bbf7d0;
        }}
        .app-badge.outline {{
          border-style: dashed;
          color:#9ca3af;
        }}

        .app-meta {{
          display: flex;
          flex-direction: column;
          align-items: flex-end;
          gap: 6px;
          font-size: 12px;
          color:#9ca3af;
        }}
        .app-meta-row {{
          display:flex;
          gap:10px;
          align-items:center;
        }}
        .dot {{
          width:8px;
          height:8px;
          border-radius:999px;
          display:inline-block;
          margin-right:4px;
        }}
        .dot.green {{
          background:#22c55e;
          box-shadow:0 0 0 4px rgba(34,197,94,0.18);
        }}
        .app-meta code {{
          padding:2px 6px;
          border-radius:6px;
          background:#020617;
          border:1px solid #1f2937;
          color:#e5e7eb;
          font-size:11px;
        }}
        .app-nav-links {{
          display:flex;
          gap:8px;
        }}
        .app-nav-links a {{
          font-size:12px;
          padding:4px 10px;
          border-radius:999px;
          border:1px solid #334155;
          text-decoration:none;
          color:#9ca3af;
        }}
        .app-nav-links a.active {{
          background:#2563eb;
          border-color:#2563eb;
          color:#e5e7eb;
        }}

        /* ===== 顶部工具条（搜索 + 筛选） ===== */
        .top-bar {{
          display: flex;
          flex-wrap: wrap;
          gap: 10px;
          align-items: center;
          margin-bottom: 18px;
        }}
        .pill-info {{
          border-radius: 999px;
          padding: 4px 12px;
          font-size: 12px;
          border: 1px solid #1f2937;
          background:#020617;
          color:#9ca3af;
        }}
        .pill-info strong {{
          color:#e5e7eb;
        }}
        .search-box {{
          display:flex;
          align-items:center;
        }}
        .search-box input {{
          background: #020617;
          border-radius: 999px;
          border: 1px solid #1f2937;
          padding: 6px 12px;
          color: #e5e7eb;
          outline: none;
          min-width: 220px;
        }}
        .search-box button {{
          margin-left: 6px;
          border-radius: 999px;
          border: 1px solid #374151;
          background: #111827;
          color: #e5e7eb;
          padding: 6px 12px;
          cursor: pointer;
          font-size: 13px;
        }}
        .filters {{
          display:flex;
          gap:6px;
        }}
        .filters a {{
          font-size: 13px;
          padding: 4px 10px;
          border-radius: 999px;
          border: 1px solid #1f2937;
          color: #9ca3af;
          text-decoration: none;
        }}
        .filters a.active {{
          background: #2563eb;
          border-color: #2563eb;
          color: #e5e7eb;
        }}
        .actions a {{
          font-size: 12px;
          padding: 5px 10px;
          border-radius: 999px;
          border: 1px solid #4b5563;
          color: #e5e7eb;
          text-decoration: none;
        }}
        .actions a.primary {{
          background:#10b981;
          border-color:#10b981;
          color:#022c22;
          font-weight:600;
        }}

        /* ===== 卡片区域 ===== */
        .grid {{
          display: grid;
          grid-template-columns: repeat(auto-fit,minmax(260px,1fr));
          gap: 14px;
          margin-top: 8px;
        }}
        .card {{
          background: radial-gradient(circle at top left,#111827 0,#020617 55%);
          border-radius: 14px;
          border: 1px solid #111827;
          padding: 12px 14px 12px;
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
          border:1px solid #22c55e;
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

        @media (max-width:640px) {{
          .app-header {{
            flex-direction:column;
            align-items:flex-start;
          }}
          .app-meta {{
            align-items:flex-start;
          }}
          .top-bar {{
            flex-direction:column;
            align-items:flex-start;
          }}
        }}
      </style>
    </head>
    <body>
      <div class="shell">
        <div class="container">

          <div class="app-header">
            <div class="app-brand">
              <div class="app-logo-wrapper">
                <div class="app-logo"><span>◆</span></div>
                <div>
                  <div class="app-title-row">
                    <span class="app-title">NTX Quest Radar</span>
                    <span class="app-version">v4.0</span>
                  </div>
                  <div class="app-subline">Quest Monitoring Platform</div>
                </div>
              </div>
            </div>
            <div class="app-status-section">
              <div class="status-indicator">
                <div class="status-badge online">
                  <span class="status-dot"></span>
                  <span class="status-text">运行正常</span>
                </div>
                <div class="status-info">
                  <div class="info-item">
                    <span class="info-label">最后刷新</span>
                    <span class="info-value">{last_utc8}</span>
                  </div>
                  <div class="info-item">
                    <span class="info-label">访问密钥</span>
                    <code class="key-display">{pwd}</code>
                  </div>
                </div>
              </div>
              <div class="nav-tabs">
                <a href="/v4?pwd={pwd}" class="nav-tab">
                  <span class="tab-icon">📊</span>活动监控
                </a>
                <a href="/manage?pwd={pwd}" class="nav-tab active">
                  <span class="tab-icon">⚙️</span>项目管理
                </a>
              </div>
            </div>
          </div>

          <div class="top-bar">
            <div class="pill-info">Space 监控总数：<strong>{len(projs)}</strong></div>

            <form class="search-box" method="GET" action="/v4">
              <input type="hidden" name="pwd" value="{pwd}">
              <input type="text" name="q" placeholder="搜索 Space 名称或 alias…" value="{q}">
              <button type="submit">搜索</button>
            </form>

            <div class="filters">
              <a href="/v4?pwd={pwd}&cat=all" class="{active_all}">全部</a>
              <a href="/v4?pwd={pwd}&cat=custom" class="{active_custom}">自定义</a>
              <a href="/v4?pwd={pwd}&cat=trending" class="{active_trending}">热度Top</a>
            </div>

            <div class="actions">
              <a href="/manage?pwd={pwd}" class="primary" target="_blank">打开项目管理</a>
            </div>
          </div>

          <div class="grid">
            {cards}
          </div>

        </div>
      </div>
    </body>
    </html>
    """
    return html

