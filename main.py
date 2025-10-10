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
    handle_resource_status,
    show_farm_overview
)
from utils import is_admin, get_today, get_now

# ========== Discord Bot 初始化 ==========
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# ========== Firebase 初始化 ==========
firebase_json = os.getenv("FIREBASE_CREDENTIAL_JSON")
cred_dict = json.loads(firebase_json)
cred = credentials.Certificate(cred_dict)
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://carrotbot-80059-default-rtdb.asia-southeast1.firebasedatabase.app'
})

# ========== 使用者資料 ==========
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
    ref.set(data)
    return data, ref

# ========== 每日登入獎勵 ==========
async def check_daily_login_reward(message, user_id, user_data, ref):
    today = get_today()
    if user_data.get("last_login") == today:
        return
    reward = random.randint(1, 5)
    user_data["coins"] += reward
    user_data["last_login"] = today
    ref.set(user_data)
    await message.channel.send(f"🎁 每日登入獎勵：你獲得了 {reward} 金幣！\n🆔 玩家 ID：`{user_data['name']}`")

# ========== 指令頻道限制 ==========
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
}

# ========== Bot 指令處理 ==========
@client.event
async def on_message(message):
    if message.author.bot:
        return

    user_id = str(message.author.id)
    username = str(message.author.display_name)
    content = message.content.strip()
    user_data, ref = get_user_data(user_id, username)

    await check_daily_login_reward(message, user_id, user_data, ref)

    # 歡迎訊息
    CARROT_CHANNEL_ID = 1423335407105343589
    if message.channel.id == CARROT_CHANNEL_ID and not user_data.get("welcome_shown", False):
        await message.channel.send(
            f"👋 歡迎加入胡蘿蔔農場，{username}！\n"
            f"💰 金幣：{user_data['coins']}\n🧪 普通肥料：{user_data['fertilizers']['普通肥料']} 個\n🌱 使用 `!種蘿蔔 普通肥料` 開始種植吧！"
        )
        user_data["welcome_shown"] = True
        ref.set(user_data)

    # 頻道限制檢查
    if content in COMMAND_CHANNELS:
        allowed_channel = COMMAND_CHANNELS[content]
        if message.channel.id != allowed_channel and getattr(message.channel, "parent_id", None) != allowed_channel:
            await message.channel.send(f"⚠️ 這個指令只能在 <#{allowed_channel}> 使用")
            return

    # 指令分派
    if content == "!運勢":
        await handle_fortune(message, user_id, username, user_data, ref)
    elif content == "!拔蘿蔔":
        await handle_pull_carrot(message, user_id, username, user_data, ref)
    elif content == "!蘿蔔圖鑑":
        await handle_carrot_encyclopedia(message, user_id, user_data)
    elif content == "!蘿蔔排行":
        await handle_carrot_ranking(message)
    elif content == "!胡蘿蔔":
        await handle_carrot_fact(message)
    elif content == "!食譜":
        await handle_carrot_recipe(message)
    elif content == "!種植":
        await handle_carrot_tip(message)
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
    elif content == "!資源狀態":
        await handle_resource_status(message, user_id, user_data)

# ==========================================================
# Flask + FastAPI 整合（防休眠 + 提供 /api/fortune + /api/ping）
# ==========================================================
from flask import Flask
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.wsgi import WSGIMiddleware
import uvicorn
import threading
import time
import requests

flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "✅ Carrot Bot is alive and running on Railway."

fastapi_app = FastAPI()

@fastapi_app.get("/api/ping")
def ping():
    return {"status": "ok"}

# ✅ 改良後的 /api/fortune（正確運勢 + emoji + 建議）
@fastapi_app.get("/api/fortune")
async def api_fortune(user_id: str = None, username: str = None):
    if not user_id or not username:
        return JSONResponse({"status": "error", "message": "缺少 user_id 或 username"}, status_code=400)

    try:
        from fortune_data import fortunes  # 載入運勢資料
        today = get_today()
        fortune_type = random.choice(list(fortunes.keys()))
        advice = random.choice(fortunes[fortune_type])

        # 金幣獎勵範圍
        reward_ranges = {
            "大吉": (12, 15),
            "中吉": (8, 11),
            "小吉": (4, 7),
            "吉": (1, 3),
            "凶": (0, 0),
        }
        min_r, max_r = next((v for k, v in reward_ranges.items() if k in fortune_type), (0, 0))
        reward = random.randint(min_r, max_r)

        user_data, ref = get_user_data(user_id, username)
        user_data["last_fortune"] = fortune_type
        user_data["coins"] = user_data.get("coins", 0) + reward
        ref.set(user_data)

        emoji_map = {
            "大吉": "🎯",
            "中吉": "🍀",
            "小吉": "🌤",
            "吉": "🥕",
            "凶": "💀"
        }
        emoji = next((v for k, v in emoji_map.items() if k in fortune_type), "")
        fortune_display = f"{emoji} {fortune_type}"

        return {
            "status": "ok",
            "date": today,
            "user": username,
            "fortune": fortune_display,
            "advice": advice,
            "reward": reward,
            "coins": user_data["coins"]
        }

    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

fastapi_app.mount("/", WSGIMiddleware(flask_app))

def start_web():
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(fastapi_app, host="0.0.0.0", port=port)

# ✅ 修正版 keep-alive：自動補 https:// 避免 Invalid URL
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

# 啟動 Thread
threading.Thread(target=start_web, daemon=False).start()
threading.Thread(target=keep_alive_loop, daemon=False).start()

# ==========================================================
# 啟動 Discord Bot
# ==========================================================
TOKEN = os.getenv("DISCORD_TOKEN")
client.run(TOKEN)
