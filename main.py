import discord
import os
import json
import random
import firebase_admin
import adventure
import asyncio
import sys
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
    check_and_post_update,
    handle_adventure_shop,
    handle_buy_item,
    handle_eat_carrot  # 🌟 確保從 carrot_commands 導入
)
from utils import get_today, get_now, is_admin
from keep_alive import keep_alive
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
    data.setdefault("inventory", {}) # 確保背包存在
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
    "!冒險": 1453283600459104266, 
    "!吃": 1453283600459104266,   
    "!領取物資": 1453283600459104266,
    "!背包": 1453283600459104266,
    "!冒險商店": 1453283600459104266,
    "!購買": 1453283600459104266
}

# ===================== 核心健康檢查 =====================
async def bot_health_check():
    await client.wait_until_ready()
    while not client.is_closed():
        if not client.is_ready():
            print("🚨 [HealthCheck] Discord 連線異常，準備重啟...")
            sys.exit(1)
        await asyncio.sleep(60)

# ===================== 田地輔助 (補回導航邏輯) =====================
def expected_farm_thread_name(author):
    return f"{author.display_name} 的田地"

def is_in_own_farm_thread(message):
    return isinstance(message.channel, discord.Thread) and message.channel.name == expected_farm_thread_name(message.author)

async def get_or_create_farm_thread(parent_channel, author):
    thread_name = expected_farm_thread_name(author)
    try:
        for t in parent_channel.threads:
            if t.name == thread_name: return t
    except: pass
    try:
        new_thread = await parent_channel.create_thread(name=thread_name, type=discord.ChannelType.public_thread, auto_archive_duration=1440)
        await new_thread.send(f"📌 {author.display_name} 的田地已建立！")
        return new_thread
    except: return None

# ===================== Discord 指令分派 =====================
@client.event
async def on_message(message):
    if message.author.bot: return
    content = (message.content or "").strip()
    if not content: return
    
    user_id = str(message.author.id)
    username = message.author.display_name
    
    try:
        user_data, ref = get_user_data(user_id, username)
        # (自動回血與跨天檢查邏輯維持不變...)
        # ...
        await check_daily_login_reward(message, user_id, user_data, ref)
    except Exception as e:
        print(f"❌ 基礎資料處理失敗: {e}")
        return

    parts = content.split()
    cmd = parts[0]
    
    # 1. 指令頻道檢查
    if cmd in COMMAND_CHANNELS:
        allowed_channel = COMMAND_CHANNELS[cmd]
        if message.channel.id != allowed_channel and getattr(message.channel, "parent_id", None) != allowed_channel:
            await message.channel.send(f"⚠️ 這個指令只能在 <#{allowed_channel}> 使用")
            return

    # 2. 🌟 農場指令自動導航 (修正無法使用的問題)
    farm_cmds = ["!種蘿蔔", "!收成蘿蔔", "!升級土地", "!土地進度", "!農場總覽", "!土地狀態", "!購買肥料", "!開運福袋", "!購買手套", "!購買裝飾"]
    if cmd in farm_cmds and not is_in_own_farm_thread(message):
        parent_channel = message.channel.parent if isinstance(message.channel, discord.Thread) else message.channel
        thread = await get_or_create_farm_thread(parent_channel, message.author)
        if thread:
            await message.channel.send(f"✅ 請至您的專屬田地操作：{thread.jump_url}")
            return

    # 3. 執行指令邏輯 (補齊缺失的指令)
    try:
        # --- 冒險與補給 ---
        if cmd == "!冒險":
            dungeon_name = parts[1] if len(parts) > 1 else "新手森林"
            await adventure.start_adventure(message, user_id, user_data, ref, dungeon_name)
        elif cmd == "!吃":
            await handle_eat_carrot(message, user_id, user_data, ref, content[3:].strip())
        elif cmd == "!背包":
            # (此處放原本的背包 Embed 代碼)
            pass 

        # --- 🌟 農場核心指令 (補上這些 handle 才會動) ---
        elif cmd == "!種蘿蔔":
            fertilizer_type = parts[1] if len(parts) > 1 else "普通肥料"
            await handle_plant_carrot(message, user_id, user_data, ref, fertilizer_type)
        elif cmd == "!收成蘿蔔":
            await handle_harvest_carrot(message, user_id, user_data, ref)
        elif cmd == "!購買肥料":
            f_type = parts[1] if len(parts) > 1 else ""
            await handle_buy_fertilizer(message, user_id, user_data, ref, f_type)
        elif cmd == "!土地進度":
            await handle_land_progress(message, user_id, user_data, ref)
        elif cmd == "!升級土地":
            await handle_upgrade_land(message, user_id, user_data, ref)
        elif cmd == "!農場總覽" or cmd == "!土地狀態":
            await show_farm_overview(client, message, user_id, user_data, ref)
        
        # --- 其他功能 ---
        elif cmd == "!運勢": await handle_fortune(message, user_id, username, user_data, ref)
        elif cmd == "!拔蘿蔔": await handle_pull_carrot(message, user_id, username, user_data, ref)
        elif cmd == "!蘿蔔圖鑑": await handle_carrot_encyclopedia(message, user_id, user_data, ref)
        elif cmd == "!開運福袋": await handle_open_lucky_bag(client, message, user_id, user_data, ref)
        elif cmd.startswith("!購買手套"):
            await handle_buy_glove(client, message, user_id, user_data, ref, parts[1] if len(parts)>1 else "", show_farm_overview)
        elif cmd == "!冒險商店": await handle_adventure_shop(message, user_data)
        elif cmd == "!購買": await handle_buy_item(message, user_id, user_data, ref, parts[1] if len(parts)>1 else "")

    except Exception as e:
        await message.channel.send("❌ 指令執行發生錯誤。")
        print(f"[Error] {cmd}: {e}")
        # --- 補回商店與裝飾系統 ---
        elif cmd == "!商店":
            embed = discord.Embed(title="🏪 蘿蔔特種商店", description="請選擇類別：", color=discord.Color.orange())
            embed.add_field(name="🧪 肥料", value="`!購買肥料 [名稱]`", inline=True)
            embed.add_field(name="🧤 手套", value="`!購買手套 [名稱]`", inline=True)
            embed.add_field(name="🏡 裝飾", value="`!裝飾商店` 查看詳情", inline=True)
            await message.channel.send(embed=embed)

        elif cmd == "!裝飾商店":
            embed = discord.Embed(title="🏡 農場裝飾商店", description="裝飾品可美化農場並獲得每日被動收益！", color=discord.Color.blue())
            for name, info in DECORATION_SHOP.items():
                embed.add_field(name=f"{name} ({info['price']} 💰)", value=f"{info['desc']}\n收益：每天 +{info['passive_gold']}", inline=True)
            await message.channel.send(embed=embed)

        elif cmd == "!購買裝飾":
            item_name = parts[1] if len(parts) > 1 else ""
            await handle_buy_decoration(message, user_id, user_data, ref, item_name)

        # --- 補回土地與背包系統 ---
        elif cmd == "!背包":
            inventory = user_data.get("inventory", {})
            if not inventory:
                await message.channel.send("🎒 你的背包空空如也...")
            else:
                embed = discord.Embed(title=f"🎒 {username} 的背包", color=discord.Color.blue())
                items_str = "\n".join([f"• **{name}** x{amt}" for name, amt in inventory.items()])
                embed.description = items_str
                embed.set_footer(text="使用方法：!吃 [名稱]")
                await message.channel.send(embed=embed)

        elif cmd == "!升級土地":
            await handle_upgrade_land(message, user_id, user_data, ref)

async def on_ready():
    print(f"🔧 Bot 已登入：{client.user}")
    # 啟動背景任務
    client.loop.create_task(check_and_post_update(client, db)) 
    client.loop.create_task(harvest_loop(client, db))
    print("🌱 自動收成與公告系統已啟動")
    
async def check_daily_login_reward(message, user_id, user_data, ref):
    today = get_today()
    if user_data.get("last_login") != today:
        reward = random.randint(1, 5)
        # 🌟 加上裝飾品收益
        decorations = user_data.get("decorations", [])
        passive_income = sum(DECORATION_SHOP[d]["passive_gold"] for d in decorations if d in DECORATION_SHOP)
        
        total = reward + passive_income
        user_data["coins"] += total
        user_data["last_login"] = today
        ref.update({"coins": user_data["coins"], "last_login": today})
        msg = f"🎁 每日獎勵：獲得 {reward} 金幣"
        if passive_income > 0: msg += f" + 裝飾收益 {passive_income} 金幣！"
        await message.channel.send(msg)
# ===================== Web 服務與啟動 =====================
flask_app = Flask(__name__)
@flask_app.route("/")
def home(): return f"Carrot Bot: {'🟢 Online' if client.is_ready() else '🔴 Disconnected'}"

fastapi_app = FastAPI()
@fastapi_app.get("/api/ping")
def ping(): return {"status": "ok"}
fastapi_app.mount("/", WSGIMiddleware(flask_app))

def start_web():
    uvicorn.run(fastapi_app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

if __name__ == '__main__':
    threading.Thread(target=lambda: client.run(os.getenv("DISCORD_TOKEN")), daemon=True).start()
    start_web()
