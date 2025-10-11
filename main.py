import discord
import os
import json
import random
import firebase_admin
from firebase_admin import credentials, db
from carrot_commands import (
    handle_fortune,
    handle_pull_carrot,
    handle_carrot_encyclopedia,
    handle_carrot_ranking,
    handle_carrot_fact,
    handle_carrot_recipe,
    handle_carrot_tip,
    handle_plant_carrot,
    handle_harvest_carrot,
    handle_buy_fertilizer,
    handle_upgrade_land,
    handle_land_progress,
    show_farm_overview
)
from utils import is_admin, get_today, get_now
from fortune_data import fortunes

# ===== Discord Bot 初始化 =====
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# ===== Firebase 初始化 =====
firebase_json = os.getenv("FIREBASE_CREDENTIAL_JSON")
cred_dict = json.loads(firebase_json)
cred = credentials.Certificate(cred_dict)
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://carrotbot-80059-default-rtdb.asia-southeast1.firebasedatabase.app'
})

# ===== 使用者資料 =====
def get_user_data(user_id, username):
    ref = db.reference(f"/users/{user_id}")
    data = ref.get() or {}
    data.setdefault("name", username)
    data.setdefault("carrots", [])
    data.setdefault("last_fortune", "")
    data.setdefault("carrot_pulls", {})
    data.setdefault("coins", 50)
    data.setdefault("fertilizers", {"普通肥料": 1, "高級肥料": 0, "神奇肥料": 0})
    data.setdefault("farm", {"land_level": 1, "pull_count": 0, "status": "未種植"})
    data.setdefault("welcome_shown", False)
    data.setdefault("last_login", "")
    data.setdefault("gloves", 0)
    data.setdefault("decorations", [])
    ref.set(data)
    return data, ref


# ===== 每日登入獎勵 =====
async def check_daily_login_reward(message, user_id, user_data, ref):
    today = get_today()
    if user_data.get("last_login") == today:
        return
    reward = random.randint(1, 5)
    user_data["coins"] += reward
    user_data["last_login"] = today
    ref.set(user_data)
    await message.channel.send(f"🎁 每日登入獎勵：你獲得了 {reward} 金幣！")


# ===== 指令頻道限制 =====
COMMAND_CHANNELS = {
    "!運勢": 1421065753595084800,
    "!重製運勢": 1421065753595084800,
    "!debug": 1421065753595084800,
    "!拔蘿蔔": 1421518540598411344,
    "!蘿蔔圖鑑": 1421518540598411344,
    "!蘿蔔排行": 1421518540598411344,
    "!種蘿蔔": 1423335407105343589,
    "!收成": 1423335407105343589,
    "!收成蘿蔔": 1423335407105343589,
    "!農場狀態": 1423335407105343589,
    "!購買肥料": 1423335407105343589,
    "!升級土地": 1423335407105343589,
    "!土地進度": 1423335407105343589,
    "!土地狀態": 1423335407105343589,
    "!商店": 1423335407105343589,
    "!開運福袋": 1423335407105343589,
    "!購買手套": 1423335407105343589,
    "!購買裝飾": 1423335407105343589,
}

# ===== 自己田地判定 =====
def is_in_own_farm_thread(message):
    expected = f"{message.author.display_name} 的田地"
    return isinstance(message.channel, discord.Thread) and message.channel.name == expected


# ===== 商店指令 =====
async def handle_shop(message, user_data, ref):
    embed = discord.Embed(title="🏪 胡蘿蔔商店", color=discord.Color.orange())
    embed.add_field(name="🧧 開運福袋", value="80 金幣｜隨機獲得金幣 / 肥料 / 裝飾", inline=False)
    embed.add_field(name="🧤 農場手套", value="150 金幣｜抽到大吉時掉出一根額外蘿蔔", inline=False)
    embed.add_field(name="🎀 農場裝飾", value="100 金幣｜讓你的農場更漂亮", inline=False)
    embed.set_footer(text=f"💰 你目前擁有 {user_data['coins']} 金幣")
    await message.channel.send(embed=embed)


# ===== 開運福袋 =====
async def handle_lucky_bag(message, user_data, ref):
    cost = 80
    if user_data["coins"] < cost:
        await message.channel.send("💸 金幣不足，無法購買開運福袋！")
        return

    user_data["coins"] -= cost
    reward_type = random.choice(["coins", "fertilizer", "decoration"])
    result = ""

    if reward_type == "coins":
        gain = random.randint(30, 100)
        user_data["coins"] += gain
        result = f"💰 {gain} 金幣"
    elif reward_type == "fertilizer":
        user_data["fertilizers"]["普通肥料"] += 1
        result = "🧪 普通肥料 x1"
    else:
        decor = random.choice(["蘿蔔風鈴", "小木牌", "田園花圈"])
        user_data["decorations"].append(decor)
        result = f"🎀 {decor}"

    ref.set(user_data)
    await message.channel.send(f"🧧 你開啟了開運福袋，獲得：{result}！")


# ===== 購買手套 =====
async def handle_buy_gloves(message, user_data, ref):
    cost = 150
    if user_data["coins"] < cost:
        await message.channel.send("💸 金幣不足，無法購買手套！")
        return
    user_data["coins"] -= cost
    user_data["gloves"] += 1
    ref.set(user_data)
    await message.channel.send("🧤 購買成功！你的手套 +1，在抽到大吉時會掉出一根額外蘿蔔！")


# ===== 購買裝飾 =====
async def handle_buy_decoration(message, user_data, ref):
    cost = 100
    if user_data["coins"] < cost:
        await message.channel.send("💸 金幣不足，無法購買裝飾！")
        return
    decor = random.choice(["南瓜燈", "木柵欄", "胡蘿蔔旗子", "花園石板"])
    user_data["coins"] -= cost
    user_data["decorations"].append(decor)
    ref.set(user_data)
    await message.channel.send(f"🎀 恭喜獲得新的農場裝飾：{decor}！")


# ===== Discord Bot 指令處理 =====
@client.event
async def on_message(message):
    if message.author.bot:
        return

    user_id = str(message.author.id)
    username = message.author.display_name
    content = message.content.strip()

    user_data, ref = get_user_data(user_id, username)
    await check_daily_login_reward(message, user_id, user_data, ref)

    # ✅ 頻道限制
    if content.split()[0] in COMMAND_CHANNELS:
        allowed_channel = COMMAND_CHANNELS[content.split()[0]]
        if message.channel.id != allowed_channel and getattr(message.channel, "parent_id", None) != allowed_channel:
            await message.channel.send(f"⚠️ 這個指令只能在 <#{allowed_channel}> 使用")
            return

    # ✅ 田地限定指令
    farm_cmds = ["!種蘿蔔", "!收成蘿蔔", "!升級土地", "!土地進度", "!農場總覽", "!商店", "!開運福袋", "!購買手套", "!購買裝飾"]
    if any(content.startswith(cmd) for cmd in farm_cmds):
        if not is_in_own_farm_thread(message):
            await message.channel.send("⚠️ 此指令僅能在你自己的田地串中使用！")
            return

    # ===== 指令分派 =====
    if content == "!運勢":
        await handle_fortune(message, user_id, username, user_data, ref)
    elif content == "!拔蘿蔔":
        await handle_pull_carrot(message, user_id, username, user_data, ref)
    elif content == "!蘿蔔圖鑑":
        await handle_carrot_encyclopedia(message, user_id, user_data)
    elif content == "!蘿蔔排行":
        await handle_carrot_ranking(message)
    elif content == "!商店":
        await handle_shop(message, user_data, ref)
    elif content == "!開運福袋":
        await handle_lucky_bag(message, user_data, ref)
    elif content == "!購買手套":
        await handle_buy_gloves(message, user_data, ref)
    elif content == "!購買裝飾":
        await handle_buy_decoration(message, user_data, ref)
    elif content.startswith("!種蘿蔔"):
        parts = content.split()
        if len(parts) == 2:
            await handle_plant_carrot(message, user_id, user_data, ref, parts[1])
        else:
            await message.channel.send("❓ 格式錯誤：`!種蘿蔔 普通肥料`")
    elif content == "!收成蘿蔔":
        await handle_harvest_carrot(message, user_id, user_data, ref)
    elif content == "!升級土地":
        await handle_upgrade_land(message, user_id, user_data, ref)
    elif content == "!土地進度":
        await handle_land_progress(message, user_id, user_data)
    elif content == "!農場總覽":
        await show_farm_overview(message, user_id, user_data)
    elif content.startswith("!購買肥料"):
        parts = content.split()
        if len(parts) == 2:
            await handle_buy_fertilizer(message, user_id, user_data, ref, parts[1])
        else:
            await message.channel.send("❓ 指令格式錯誤，請使用：`!購買肥料 普通肥料` 或 `!購買肥料 高級肥料`")


# ==========================================================
# Flask + FastAPI 整合（防休眠 + /api/fortune + CORS）
# ==========================================================
from flask import Flask
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.wsgi import WSGIMiddleware
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import threading
import time
import requests

flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "✅ Carrot Bot is alive and running on Railway."

fastapi_app = FastAPI()

# ✅ 啟用 CORS
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 你可改成 ["https://tom-omega.github.io"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@fastapi_app.get("/api/ping")
def ping():
    return {"status": "ok"}


@fastapi_app.get("/api/fortune")
async def api_fortune(user_id: str = None, username: str = None):
    if not user_id or not username:
        return JSONResponse({"status": "error", "message": "缺少 user_id 或 username"}, status_code=400)

    user_data, ref = get_user_data(user_id, username)

    class DummyAuthor:
        def __init__(self, name):
            self.display_name = name
            self.guild_permissions = type("Perm", (), {"administrator": False})()
            self.display_avatar = type("Avatar", (), {"url": "https://cdn.discordapp.com/embed/avatars/0.png"})()

    class DummyChannel:
        async def send(self, msg=None, embed=None):
            return

    class DummyMessage:
        def __init__(self, name):
            self.author = DummyAuthor(name)
            self.channel = DummyChannel()

    message = DummyMessage(username)
    try:
        await handle_fortune(message, user_id, username, user_data, ref)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

    new_data = ref.get()
    fortune_text = new_data.get("last_fortune", "未知")

    # 從 fortune_data 抓出對應的建議
    matched_fortune = None
    for key in fortunes.keys():
        if key in fortune_text:
            matched_fortune = key
            break

    advice = random.choice(fortunes[matched_fortune]) if matched_fortune else "今天胡蘿蔔靜靜地守護你 🍃"

    emoji_map = {
        "大吉": "🎯",
        "中吉": "🍀",
        "小吉": "🌤",
        "吉": "🥕",
        "凶": "💀"
    }
    emoji = next((v for k, v in emoji_map.items() if k in fortune_text), "")

    return {
        "status": "ok",
        "date": get_today(),
        "user": username,
        "fortune": f"{emoji} {fortune_text}",
        "advice": advice
    }


fastapi_app.mount("/", WSGIMiddleware(flask_app))

# 啟動 Web Server
def start_web():
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(fastapi_app, host="0.0.0.0", port=port)

# ✅ KeepAlive（避免 Railway 休眠）
def keep_alive_loop():
    while True:
        try:
            url = os.environ.get("RAILWAY_STATIC_URL", "https://carrot-bot-production.up.railway.app")
            if url and not url.startswith("http"):
                url = "https://" + url
            requests.get(f"{url}/api/ping", timeout=5)
            print("[KeepAlive] Pinged self successfully ✅")
        except Exception as e:
            print("[KeepAlive] Failed:", e)
        time.sleep(600)

threading.Thread(target=start_web, daemon=False).start()
threading.Thread(target=keep_alive_loop, daemon=False).start()

# ==========================================================
# 啟動 Discord Bot
# ==========================================================
TOKEN = os.getenv("DISCORD_TOKEN")
client.run(TOKEN)
