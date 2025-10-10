import discord
import os
import json
import random
import firebase_admin
from firebase_admin import credentials, db
from keep_alive import keep_alive

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

# ===== 使用者資料讀取與補齊 =====
def get_user_data(user_id, username):
    ref = db.reference(f"/users/{user_id}")
    data = ref.get() or {}

    data.setdefault("name", username)
    data.setdefault("carrots", [])
    data.setdefault("last_fortune", "")
    data.setdefault("carrot_pulls", {})
    data.setdefault("coins", 50)
    data.setdefault("fertilizers", {
        "普通肥料": 1,
        "高級肥料": 0,
        "神奇肥料": 0
    })
    data.setdefault("farm", {
        "land_level": 1,
        "pull_count": 0,
        "status": "未種植"
    })
    data.setdefault("welcome_shown", False)
    data.setdefault("last_login", "")
    ref.set(data)
    return data, ref

# ===== 每日登入獎勵 =====
async def check_daily_login_reward(message, user_id, user_data, ref):
    today = get_today()
    last_login = user_data.get("last_login", "")
    if last_login == today:
        return
    reward = random.randint(1, 5)
    user_data["coins"] += reward
    user_data["last_login"] = today
    ref.set(user_data)
    await message.channel.send(
        f"🎁 每日登入獎勵：你獲得了 {reward} 金幣！\n"
        f"🆔 玩家 ID：`{user_data['name']}`"
    )

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
}

# ===== Bot 指令處理 =====
@client.event
async def on_message(message):
    if message.author.bot:
        return

    user_id = str(message.author.id)
    username = str(message.author.display_name)
    content = message.content.strip()
    today = get_today()

    user_data, ref = get_user_data(user_id, username)
    await check_daily_login_reward(message, user_id, user_data, ref)

    # ===== 管理員指令 =====
    if content == "!重置運勢":
        if not is_admin(user_id):
            await message.channel.send("⛔ 你沒有權限使用此指令。")
            return
        user_data["last_fortune"] = ""
        ref.set(user_data)
        await message.channel.send("✅ 已重置你的運勢紀錄，現在可以重新抽運勢！")
        return

    elif content == "!debug":
        if not is_admin(user_id):
            await message.channel.send("⛔ 你沒有權限使用此指令。")
            return
        await message.channel.send(
            f"🧪 Debug 資料：\n"
            f"👤 玩家：{username}\n"
            f"📅 last_fortune：{user_data.get('last_fortune')}\n"
            f"💰 金幣：{user_data.get('coins')}\n"
            f"🧪 肥料：{json.dumps(user_data.get('fertilizers'), ensure_ascii=False)}"
        )
        return

    elif content == "!debug時間" and is_admin(user_id):
        await message.channel.send(
            f"🕒 台灣時間：{get_now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"📅 今日日期：{get_today()}"
        )
        return

    # ===== 歡迎訊息 =====
    CARROT_CHANNEL_ID = 1423335407105343589
    if message.channel.id == CARROT_CHANNEL_ID and not user_data.get("welcome_shown", False):
        await message.channel.send(
            f"👋 歡迎加入胡蘿蔔農場，{user_data['name']}！\n"
            f"你目前擁有：\n"
            f"💰 金幣：{user_data['coins']}\n"
            f"🧪 普通肥料：{user_data['fertilizers']['普通肥料']} 個\n"
            f"🌱 使用 !種蘿蔔 普通肥料 開始種植吧！"
        )
        user_data["welcome_shown"] = True
        user_data["last_fortune"] = today
        ref.set(user_data)

    # ===== 頻道限制判斷 =====
    if content in COMMAND_CHANNELS:
        allowed_channel = COMMAND_CHANNELS[content]
        parent_id = getattr(message.channel, "parent_id", None)
        is_allowed = (
            message.channel.id == allowed_channel or
            parent_id == allowed_channel
        )
        if not is_allowed:
            await message.channel.send(f"⚠️ 這個指令只能在 <#{allowed_channel}> 或其討論串中使用")
            return

    # ===== 指令分派 =====
    
    if content.startswith("!健康檢查"):
        await handle_health_check(message)
    
    if content.startswith("!種蘿蔔"):
        parts = content.split()
        if len(parts) == 2:
            await handle_plant_carrot(message, user_id, user_data, ref, parts[1])
        else:
            await message.channel.send("❓ 請使用正確格式：`!種蘿蔔 普通肥料`")

    elif content.startswith("!購買肥料"):
        parts = content.split()
        if len(parts) == 2:
            await handle_buy_fertilizer(message, user_id, user_data, ref, parts[1])
        else:
            await message.channel.send("❓ 請使用正確格式：`!購買肥料 普通肥料`")

    elif content == "!收成蘿蔔":
        await handle_harvest_carrot(message, user_id, user_data, ref)

    elif content == "!升級土地":
        await handle_upgrade_land(message, user_id, user_data, ref)

    elif content in ["!土地狀態", "!農場狀態"]:
        await message.channel.send("📦 此指令已整合為 `!農場總覽`\n請改用 !農場總覽 查看完整土地與農場資訊！")

    elif content == "!資源狀態":
        await handle_resource_status(message, user_id, user_data)

    elif content == "!土地進度":
        await handle_land_progress(message, user_id, user_data)

    elif content == "!農場總覽":
        await show_farm_overview(message, user_id, user_data)

    elif content == "!運勢":
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

    elif content == "!debug指令" and is_admin(user_id):
        await message.channel.send(
            "**🧪 指令掛載狀態檢查**\n"
            "📦 Discord 指令：\n"
            "　✅ !運勢　✅ !拔蘿蔔　✅ !種蘿蔔　✅ !收成蘿蔔\n"
            "　✅ !購買肥料　✅ !升級土地　✅ !土地進度　✅ !農場總覽\n"
            "　✅ !蘿蔔圖鑑　✅ !蘿蔔排行　✅ !胡蘿蔔　✅ !食譜　✅ !種植\n"
            "🔧 管理員指令：\n"
            "　✅ !重置運勢　✅ !debug　✅ !debug時間　✅ !debug指令\n"
            "🌐 Flask 路由：\n"
            "　✅ /upload-cookie　✅ /routes　✅ /status\n"
            "🕒 時區判斷：使用 get_today() / `get_now()`（台灣時間）\n"
            "📦 Firebase：已初始化，使用 /users/{user_id} 儲存資料\n"
            "🧠 utils.py：已整合 `is_admin`、`get_today`、`get_now`、`get_remaining_hours`\n"
        )

# ===== HTTP API（給前端呼叫抽運勢）=====
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import threading
import uvicorn
from datetime import datetime
import asyncio

app = FastAPI()

@app.get("/api/fortune")
async def api_fortune(user_id: str = None, username: str = None):
    """
    前端呼叫範例：
    GET https://carrot-bot-1.onrender.com/api/fortune?user_id=123&username=Tom
    """
    if not user_id or not username:
        return JSONResponse({"status": "error", "message": "缺少 user_id 或 username"}, status_code=400)

    # 讀取使用者資料
    user_data, ref = get_user_data(user_id, username)

    # 模擬 Discord message 物件
    class DummyAuthor:
        def __init__(self, name):
            self.display_name = name
            self.guild_permissions = type("Perm", (), {"administrator": False})()
            self.display_avatar = type("Avatar", (), {"url": "https://cdn.discordapp.com/embed/avatars/0.png"})()

    class DummyChannel:
        async def send(self, msg=None, embed=None):
            return  # 可改成同步發送至 Discord 頻道（可選）

    class DummyMessage:
        def __init__(self, name):
            self.author = DummyAuthor(name)
            self.channel = DummyChannel()

    message = DummyMessage(username)

    # 執行原本的運勢邏輯
    try:
        await handle_fortune(message, user_id, username, user_data, ref)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

    # 回傳結果
    new_data = ref.get()
    today = get_today()

    return {
        "status": "ok",
        "date": today,
        "user": username,
        "fortune": new_data.get("last_fortune", "未知"),
        "coins": new_data.get("coins", 0)
    }

# ===== 啟動 FastAPI 在背景執行 =====
def start_fastapi():
    port = int(os.environ.get("PORT", 3000))  # ✅ 改為 Render 專用 PORT
    uvicorn.run(app, host="0.0.0.0", port=port)

threading.Thread(target=start_fastapi, daemon=True).start()

# ===== 假 Web Server（支援 Render 免費 Web Service）=====
keep_alive()

# ===== 啟動 Bot =====
TOKEN = os.getenv("DISCORD_TOKEN")
client.run(TOKEN)

