import io
import os

PATH = "/opt/GalxeMonitor/combined_app.py"

if not os.path.exists(PATH):
    print("❌ 找不到", PATH)
    raise SystemExit(1)

with io.open(PATH, "r", encoding="utf-8") as f:
    src = f.readlines()

start = None
for i, line in enumerate(src):
    if line.lstrip().startswith("def build_campaign_url"):
        start = i
        break

if start is None:
    print("❌ 文件里没有找到 def build_campaign_url，脚本没有做修改")
    raise SystemExit(1)

end = len(src)
for i in range(start + 1, len(src)):
    stripped = src[i].lstrip()
    if stripped.startswith("def ") or stripped.startswith("class "):
        end = i
        break

new_func = [
"def build_campaign_url(alias, latest):\n",
"    \"\"\"根据 Space alias 和最新活动数据构造 Galxe 活动链接。\n",
"    兼容多种字段名：id / campaignId / hashId / campaign_id / slug / campaignSlug。\n",
"    返回完整 https 链接，避免相对路径跳到你自己的服务器。\n",
"    \"\"\"\n",
"    if not alias or not latest:\n",
"        return None\n",
"\n",
"    def _get(obj, key):\n",
"        if isinstance(obj, dict):\n",
"            return obj.get(key)\n",
"        return getattr(obj, key, None)\n",
"\n",
"    campaign_id = None\n",
"    for key in (\"id\", \"campaignId\", \"hashId\", \"campaign_id\", \"slug\", \"campaignSlug\"):\n",
"        value = _get(latest, key)\n",
"        if value:\n",
"            campaign_id = value\n",
"            break\n",
"\n",
"    if not campaign_id:\n",
"        return None\n",
"\n",
"    # Galxe 目前活动链接形如：https://app.galxe.com/quest/{alias}/{campaign_id}\n",
"    return f\"https://app.galxe.com/quest/{alias}/{campaign_id}\"\n",
"\n",
]

new_src = src[:start] + new_func + src[end:]

backup = PATH + ".bak_links"
with io.open(backup, "w", encoding="utf-8") as f:
    f.writelines(src)

with io.open(PATH, "w", encoding="utf-8") as f:
    f.writelines(new_src)

print(\"✅ 已替换 build_campaign_url，备份存放在:\", backup)
