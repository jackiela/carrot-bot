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
    handle_buy_glove,
    handle_glove_encyclopedia,
    handle_carrot_info,
    handle_special_carrots,
    handle_open_lucky_bag,
    handle_buy_decoration,
    harvest_loop,
    GLOVE_SHOP,
    DECORATION_SHOP,
    check_and_post_update
)
from utils import get_today
from fortune_data import fortunes
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.wsgi import WSGIMiddleware
from flask import Flask
from datetime import datetime
import threading
import time
import requests
import uvicorn

# ===================== Discord Bot 初始化 =====================
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# ===================== Firebase 初始化 =====================
firebase_json = os.getenv("FIREBASE_CREDENTIAL_JSON")
cred_dict = json.loads(firebase_json)
cred = credentials.Certificate(cred_dict)
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://carrotbot-80059-default-rtdb.asia-southeast1.firebasedatabase.app'
})

# ===================== 使用者資料 =====================
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
    data.setdefault("gloves", [])
    data.setdefault("decorations", [])
    ref.update(data)
    return data, ref

async def check_daily_login_reward(message, user_id, user_data, ref):
    today = get_today()
    if user_data.get("last_login") != today:
        reward = random.randint(1, 5)
        user_data["coins"] += reward
        user_data["last_login"] = today
        ref.update({"coins": user_data["coins"], "last_login": today})
        await message.channel.send(f"🎁 每日登入獎勵：你獲得了 {reward} 金幣！")

# ===================== 指令頻道限制 =====================
COMMAND_CHANNELS = {
    "!運勢": 1421065753595084800,
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
    "!特殊蘿蔔一覽": 1423335407105343589,
    "!胡蘿蔔": 1420254884581867647,
    "!食譜": 1420254884581867647,
    "!種植": 1420254884581867647,
}

# ===================== 田地輔助 =====================
def expected_farm_thread_name(author):
    return f"{author.display_name} 的田地"

def is_in_own_farm_thread(message):
    return isinstance(message.channel, discord.Thread) and message.channel.name == expected_farm_thread_name(message.author)

async def get_or_create_farm_thread(parent_channel, author):
    thread_name = expected_farm_thread_name(author)
    try:
        for t in parent_channel.threads:
            if t.name == thread_name:
                return t
    except Exception:
        pass
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

# ===================== 商店指令 =====================
async def handle_shop(message, user_id, user_data, ref):
    embed = discord.Embed(title="🏪 胡蘿蔔商店", color=discord.Color.orange())
    embed.add_field(name="🧧 開運福袋", value="80 金幣｜隨機獲得金幣 / 肥料 / 裝飾\n使用 `!開運福袋`", inline=False)
    glove_text = "\n".join([f"• {name} — {info['price']} 金幣｜{info['desc']}" for name, info in GLOVE_SHOP.items()])
    embed.add_field(name="🧤 農場手套", value=glove_text + "\n使用 `!購買手套 幸運手套`", inline=False)
    deco_text = "\n".join([f"• {name} — {price} 金幣" for name, price in DECORATION_SHOP.items()])
    embed.add_field(name="🎀 農場裝飾", value=deco_text + "\n使用 `!購買裝飾 花圃`", inline=False)
    embed.set_footer(text=f"💰 你目前擁有 {user_data.get('coins', 0)} 金幣")
    await message.channel.send(embed=embed)

# ===================== Discord 指令分派 =====================
@client.event
async def on_message(message):
    if message.author.bot:
        return
    content = (message.content or "").strip()
    if not content:
        return
    user_id = str(message.author.id)
    username = message.author.display_name
    try:
        user_data, ref = get_user_data(user_id, username)
        await check_daily_login_reward(message, user_id, user_data, ref)
    except Exception as e:
        await message.channel.send("❌ 使用者資料讀取失敗，請稍後再試。")
        print("[Error] get_user_data:", e)
        return

    parts = content.split()
    cmd = parts[0]

    # 指令頻道檢查
    if cmd in COMMAND_CHANNELS:
        allowed_channel = COMMAND_CHANNELS[cmd]
        if message.channel.id != allowed_channel and getattr(message.channel, "parent_id", None) != allowed_channel:
            await message.channel.send(f"⚠️ 這個指令只能在 <#{allowed_channel}> 使用")
            return

    # 農場指令導向子頻道
    farm_cmds = [
        "!種蘿蔔","!收成蘿蔔","!升級土地","!土地進度",
        "!農場總覽","!土地狀態","!商店","!開運福袋",
        "!購買手套","!購買裝飾","!特殊蘿蔔一覽"
    ]
    if any(content.startswith(c) for c in farm_cmds) and not is_in_own_farm_thread(message):
        parent_channel = message.channel.parent if isinstance(message.channel, discord.Thread) else message.channel
        thread = await get_or_create_farm_thread(parent_channel, message.author)
        if not thread:
            await message.channel.send("❌ 無法建立或找到你的田地串（可能缺少權限）。")
            return
        await message.channel.send(f"✅ 我已將你的指令導向田地串：{thread.jump_url}，請在該串使用指令。")
        return

    # 指令執行
    try:
        if cmd == "!運勢":
            await handle_fortune(message, user_id, username, user_data, ref)
        elif cmd == "!拔蘿蔔":
            await handle_pull_carrot(message, user_id, username, user_data, ref)
        elif cmd == "!蘿蔔圖鑑":
            await handle_carrot_encyclopedia(message, user_id, user_data, ref)
        elif cmd == "!蘿蔔排行":
            await handle_carrot_ranking(message, user_id, user_data, ref)
        elif cmd == "!商店":
            await handle_shop(message, user_id, user_data, ref)
        elif cmd == "!開運福袋":
            await handle_open_lucky_bag(message, user_id, user_data, ref)
        elif cmd.startswith("!購買手套") and len(parts) == 2:
            await handle_buy_glove(message, user_id, user_data, ref, parts[1], show_farm_overview)
        elif cmd == "!手套圖鑑":
            await handle_glove_encyclopedia(message, user_id, user_data, ref)
        elif cmd.startswith("!購買裝飾") and len(parts) == 2:
            await handle_buy_decoration(message, user_id, user_data, ref, parts[1])
        elif cmd.startswith("!種蘿蔔") and len(parts) == 2:
            await handle_plant_carrot(message, user_id, user_data, ref, parts[1])
        elif cmd == "!收成蘿蔔":
            await handle_harvest_carrot(message, user_id, user_data, ref)
        elif cmd == "!升級土地":
            await handle_upgrade_land(message, user_id, user_data, ref)
        elif cmd == "!土地進度":
            await handle_land_progress(message, user_id, user_data, ref)
        elif cmd in ["!農場總覽","!土地狀態"]:
            await show_farm_overview(client, message, user_id, user_data, user_ref)
        elif cmd.startswith("!購買肥料") and len(parts) == 2:
            await handle_buy_fertilizer(message, user_id, user_data, ref, parts[1])
        elif cmd.startswith("!給金幣"):
            await handle_give_coins(message, user_id, user_data, ref, parts[1:])
        elif content == "!蘿蔔說明":
            await handle_carrot_info(message, user_id, user_data, ref)
        elif content == "!特殊蘿蔔一覽":
            await handle_special_carrots(message, user_id, user_data, ref)
        elif content == "!胡蘿蔔":
            await handle_carrot_tip(message, user_id, user_data, ref)
        elif content == "!食譜":
            await handle_carrot_recipe(message, user_id, user_data, ref)
        elif content == "!種植":
            await handle_carrot_fact(message, user_id, user_data, ref)
    except Exception as e:
        await message.channel.send("❌ 指令執行發生錯誤，請稍後再試。")
        print("[Error] command execution:", e)

# ===================== Web API + Keep-alive =====================
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "✅ Carrot Bot is alive!"

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
async def web_fortune(user_id: str = None, username: str = None, force_random: bool = False):
    if not user_id or not username:
        return JSONResponse({"status": "error","message":"缺少 user_id 或 username"}, status_code=400)
    today = datetime.now().strftime("%Y-%m-%d")
    seed = str(user_id) + today if not force_random else None
    random.seed(seed)
    key = random.choice(list(fortunes.keys()))
    advice = random.choice(fortunes[key])
    emoji_map = {"紅蘿蔔大吉":"🥕","白蘿蔔中吉":"🌿","紫蘿蔔小吉":"🍆","金蘿蔔吉":"🌟","黑蘿蔔凶":"💀"}
    emoji = emoji_map.get(key,"🥕")
    return {"status":"ok","date":today,"user":username,"fortune":f"{emoji} {key}","advice":advice}

fastapi_app.mount("/", WSGIMiddleware(flask_app))

def start_web():
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(fastapi_app, host="0.0.0.0", port=port)

def keep_alive_loop():
    time.sleep(10)
    while True:
        try:
            port = int(os.environ.get("PORT", 10000))
            local_url = f"http://127.0.0.1:{port}/api/ping"
            requests.get(local_url, timeout=5)
            url = os.environ.get("RENDER_EXTERNAL_URL") or os.environ.get("RAILWAY_STATIC_URL") or "https://carrot-bot.onrender.com"
            if not url.startswith("http"): url = "https://" + url
            requests.get(url, timeout=10)
        except Exception as e:
            print("[KeepAlive] Failed:", e)
        time.sleep(600)

# ===================== 啟動 Discord Bot =====================
TOKEN = os.getenv("DISCORD_TOKEN")

@client.event
async def on_ready():
    print(f"🔧 Bot 已登入：{client.user}")
    
    # 🌟 新增這一行：啟動版本檢查與更新通知
    # 傳入 client (Bot 物件) 和 db (Firebase 參考)
    client.loop.create_task(check_and_post_update(client, db)) 
    
    # 注意：這裡的 harvest_loop 還是由 Bot 的 loop 管理
    client.loop.create_task(harvest_loop(client, db))
    print("🌱 自動收成推播系統已啟動")

def run_bot():
    """在背景執行緒啟動 Discord Bot (會阻塞該執行緒)"""
    client.run(TOKEN)

# ===================== 執行啟動 =====================
if __name__ == '__main__':
    print("Bot 啟動中...")

    # 1. 將 Discord Bot 移到一個新的背景執行緒中執行
    #    Bot 現在是次要任務，讓主執行緒空出來給 Web Server
    threading.Thread(target=run_bot, daemon=True).start()
    
    # 2. 啟動 Keep Alive loop
    threading.Thread(target=keep_alive_loop, daemon=True).start()

    # 3. 讓 Web Server 在主執行緒中啟動並**阻塞**
    #    uvicorn.run() 會在這裡阻塞，讓 Render 偵測到 Port 綁定成功
    print("🌐 啟動 Web 服務 (主執行緒)")
    start_web()
