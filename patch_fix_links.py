import io, os

TARGET = "/opt/GalxeMonitor/combined_app.py"

if not os.path.exists(TARGET):
    print("❌ combined_app.py 不存在:", TARGET)
    raise SystemExit(1)

with open(TARGET, "r", encoding="utf-8") as f:
    lines = f.readlines()

start = None
end = None

for i, line in enumerate(lines):
    if line.strip().startswith("def build_campaign_url"):
        start = i
        break

if start is None:
    print("❌ 找不到 build_campaign_url() 函数，无法修复")
    raise SystemExit(1)

for i in range(start + 1, len(lines)):
    if lines[i].startswith("def ") or lines[i].startswith("class "):
        end = i
        break

if end is None:
    end = len(lines)

new_func = [
"def build_campaign_url(alias, latest):\n",
"    \"\"\"V3.5 正确活动链接：\n",
"    https://app.galxe.com/quest/{alias}/{campaign_id}\n",
"    兼容 id / campaignID / hashId / slug 字段\n",
"    \"\"\"\n",
"    if not latest:\n",
"        return None\n",
"\n",
"    def gx(obj, key):\n",
"        if isinstance(obj, dict): return obj.get(key)\n",
"        return getattr(obj, key, None)\n",
"\n",
"    cid = None\n",
"    for k in (\"id\", \"campaignId\", \"hashId\", \"slug\", \"campaignID\"):\n",
"        v = gx(latest, k)\n",
"        if v:\n",
"            cid = v\n",
"            break\n",
"\n",
"    if not cid:\n",
"        return None\n",
"\n",
"    return f\"https://app.galxe.com/quest/{alias}/{cid}\"\n",
"\n",
]

backup = TARGET + ".bak_link_patch"
with open(backup, "w", encoding="utf-8") as f:
    f.writelines(lines)

with open(TARGET, "w", encoding="utf-8") as f:
    f.writelines(lines[:start] + new_func + lines[end:])

print(\"✅ 活动链接已修复！所有链接将使用： https://app.galxe.com/quest/{alias}/{campaign} 形式\")
print(\"📦 旧版本已备份：\", backup)
