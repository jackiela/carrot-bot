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
    show_farm_overview,
    handle_give_coins,
    handle_buy_glove,  # ✅ 新增匯入
    handle_glove_encyclopedia
)
from utils import is_admin, get_today, get_now
from fortune_data import fortunes
from fastapi.responses import JSONResponse
from datetime import datetime

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
    data.setdefault("gloves", [])  # ✅ 建議改為 list 型別
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
    "!收成蘿蔔": 1423335407105343589,
    "!升級土地": 1423335407105343589,
    "!土地進度": 1423335407105343589,
    "!土地狀態": 1423335407105343589,
    "!農場總覽": 1423335407105343589,
    "!購買肥料": 1423335407105343589,
    "!商店": 1423335407105343589,
    "!開運福袋": 1423335407105343589,
    "!購買手套": 1423335407105343589,
    "!購買裝飾": 1423335407105343589,
}

# ===== 田地輔助 =====
def expected_farm_thread_name(author):
    return f"{author.display_name} 的田地"

def is_in_own_farm_thread(message):
    return isinstance(message.channel, discord.Thread) and message.channel.name == expected_farm_thread_name(message.author)

async def get_or_create_farm_thread(parent_channel, author):
    thread_name = expected_farm_thread_name(author)
    existing = None
    try:
        for t in parent_channel.threads:
            if t.name == thread_name:
                existing = t
                break
    except Exception:
        pass
    if existing:
        return existing
    try:
        new_thread = await parent_channel.create_thread(
            name=thread_name,
            type=discord.ChannelType.public_thread,
            auto_archive_duration=1440
        )
        await new_thread.send(f"📌 {author.display_name} 的田地已建立，歡迎在此管理你的農場！")
        return new_thread
    except Exception:
        return None

# ===== 商店指令 =====
async def handle_shop(message, user_data, ref):
    embed = discord.Embed(title="🏪 胡蘿蔔商店", color=discord.Color.orange())
    embed.add_field(name="🧧 開運福袋", value="80 金幣｜隨機獲得金幣 / 肥料 / 裝飾", inline=False)
    embed.add_field(name="🧤 農場手套", value="可購買：幸運手套、農夫手套、強化手套、神奇手套\n使用 `!購買手套 幸運手套`", inline=False)
    embed.add_field(name="🎀 農場裝飾", value="100 金幣｜讓你的農場更漂亮", inline=False)
    embed.set_footer(text=f"💰 你目前擁有 {user_data['coins']} 金幣")
    await message.channel.send(embed=embed)

# ===== 指令分派 =====
@client.event
async def on_message(message):
    if message.author.bot:
        return

    user_id = str(message.author.id)
    username = message.author.display_name
    content = message.content.strip()

    user_data, ref = get_user_data(user_id, username)
    await check_daily_login_reward(message, user_id, user_data, ref)

    if content.split()[0] in COMMAND_CHANNELS:
        allowed_channel = COMMAND_CHANNELS[content.split()[0]]
        if message.channel.id != allowed_channel and getattr(message.channel, "parent_id", None) != allowed_channel:
            await message.channel.send(f"⚠️ 這個指令只能在 <#{allowed_channel}> 使用")
            return

    farm_cmds = [
        "!種蘿蔔", "!收成蘿蔔", "!升級土地", "!土地進度",
        "!農場總覽", "!土地狀態", "!商店", "!開運福袋",
        "!購買手套", "!購買裝飾"
    ]
    if any(content.startswith(cmd) for cmd in farm_cmds):
        if not is_in_own_farm_thread(message):
            parent_channel = message.channel.parent if isinstance(message.channel, discord.Thread) else message.channel
            thread = await get_or_create_farm_thread(parent_channel, message.author)
            if not thread:
                await message.channel.send("❌ 無法建立或找到你的田地串（可能缺少權限）。")
                return
            class _Msg:
                def __init__(self, author, channel):
                    self.author = author
                    self.channel = channel
            fake_msg = _Msg(message.author, thread)
            await show_farm_overview(fake_msg, user_id, user_data)
            await message.channel.send(f"✅ 我已在你的田地串發送農場總覽：{thread.jump_url}")
            return

    # ===== 指令邏輯 =====
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
    elif content.startswith("!購買手套"):
        parts = content.split()
        if len(parts) == 2:
        await handle_buy_glove(message, user_id, user_data, ref, parts[1])
    else:
        await message.channel.send("❓ 指令格式錯誤，請使用：`!購買手套 幸運手套`")
    elif content == "!手套圖鑑":
        await handle_glove_encyclopedia(message)  
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
    elif content in ["!農場總覽", "!土地狀態"]:
        await show_farm_overview(message, user_id, user_data)
    elif content.startswith("!購買肥料"):
        parts = content.split()
        if len(parts) == 2:
            await handle_buy_fertilizer(message, user_id, user_data, ref, parts[1])
        else:
            await message.channel.send("❓ 指令格式錯誤，請使用：`!購買肥料 普通肥料` 或 `!購買肥料 高級肥料`")
    elif content.startswith("!給金幣"):
        args = content.split()[1:]
        await handle_give_coins(message, args)

# ==========================================================
# Flask + FastAPI 整合（防休眠 + Fortune API）
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

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@fastapi_app.get("/api/ping")
def ping():
    return {"status": "ok"}

@fastapi_app.get("/api/web_fortune")
async def web_fortune(
    user_id: str = None,
    username: str = None,
    force_random: bool = False
):
    if not user_id or not username:
        return JSONResponse({"status": "error", "message": "缺少 user_id 或 username"}, status_code=400)

    today = datetime.now().strftime("%Y-%m-%d")

    # 🌟 根據是否有 force_random 參數決定抽籤方式
    if not force_random:
        # 每人每天固定籤
        seed = str(user_id) + today
        random.seed(seed)
    else:
        # 每次重新隨機
        random.seed()

    # 🍀 從 fortune_data.py 抽籤
    fortune_key = random.choice(list(fortunes.keys()))
    advice = random.choice(fortunes[fortune_key])

    emoji_map = {
        "紅蘿蔔大吉": "🥕",
        "白蘿蔔中吉": "🌿",
        "紫蘿蔔小吉": "🍆",
        "金蘿蔔吉": "🌟",
        "黑蘿蔔凶": "💀"
    }
    emoji = emoji_map.get(fortune_key, "🥕")

    return {
        "status": "ok",
        "date": today,
        "user": username,
        "fortune": f"{emoji} {fortune_key}",
        "advice": advice
    }

fastapi_app.mount("/", WSGIMiddleware(flask_app))


def start_web():
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(fastapi_app, host="0.0.0.0", port=port)

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
