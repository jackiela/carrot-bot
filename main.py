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


# ==========================================================
# Flask + FastAPI 整合（防休眠 + 提供 /api/fortune + /api/ping）
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
from fortune_data import fortunes  # ✅ 新增匯入運勢資料


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

    # 從 Firebase 取最新資料
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
        "advice": advice,  # ✅ 新增今日建議
        "coins": new_data.get("coins", 0)
    }

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
