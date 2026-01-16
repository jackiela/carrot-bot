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

# ===================== Discord 指令分派 =====================
@client.event
async def on_message(message):
    if message.author.bot: return
    content = (message.content or "").strip()
    if not content: return
    
    user_id = str(message.author.id)
    username = message.author.display_name
    
    # 1. 基礎資料讀取與自動回血
    try:
        user_data, ref = get_user_data(user_id, username)
        
        # 跨天檢查
        today_str = get_today()
        if user_data.get("last_login_day") != today_str:
            user_data["daily_adv_count"] = 0
            user_data["last_login_day"] = today_str
            ref.update({"daily_adv_count": 0, "last_login_day": today_str})

        # 自動回血邏輯
        current_time = time.time()
        last_regen = user_data.get("last_regen_time", current_time)
        hp = user_data.get("hp", 100)
        max_hp = 100 + (user_data.get("level", 1) * 10)

        if hp < max_hp:
            elapsed = current_time - last_regen
            regen_amount = elapsed * (max_hp / 86400)
            if regen_amount >= 0.1:
                new_hp = min(max_hp, hp + regen_amount)
                user_data["hp"] = new_hp
                user_data["last_regen_time"] = current_time
                ref.update({"hp": new_hp, "last_regen_time": current_time})
        
        await check_daily_login_reward(message, user_id, user_data, ref)
    except Exception as e:
        print(f"❌ 基礎資料處理失敗: {e}")
        return

    # 2. 指令解析與頻道限制
    parts = content.split()
    cmd = parts[0]
    
    if cmd in COMMAND_CHANNELS:
        allowed_channel = COMMAND_CHANNELS[cmd]
        if message.channel.id != allowed_channel and getattr(message.channel, "parent_id", None) != allowed_channel:
            await message.channel.send(f"⚠️ 這個指令只能在 <#{allowed_channel}> 使用")
            return

    # 3. 執行指令邏輯
    try:
        # --- 冒險與背包系統 ---
        if cmd == "!冒險":
            dungeon_name = parts[1] if len(parts) > 1 else "新手森林"
            await adventure.start_adventure(message, user_id, user_data, ref, dungeon_name)
        
        elif cmd == "!吃":
            # 🌟 整合：呼叫 carrot_commands 裡的 handle_eat_carrot
            item_name = content[3:].strip() 
            await handle_eat_carrot(message, user_id, user_data, ref, item_name)

        elif cmd == "!背包":
            # (此處保留你原本長長的背包 Embed 顯示邏輯)
            inventory = user_data.get("inventory", {})
            hp_display = int(user_data.get("hp", 100))
            max_hp = 100 + (user_data.get("level", 1) * 10)
            coins = user_data.get("coins", 0)
            active_buff = user_data.get("active_buff")
            buff_map = {"double_gold": "🎒 幸運餅乾", "invincible": "🛡️ 守護卷軸", "heat_resist": "❄️ 抗熱噴霧"}
            current_buff_text = buff_map.get(active_buff, "無")
            adv_count = user_data.get("daily_adv_count", 0)
            
            embed = discord.Embed(title=f"🎒 {username} 的背包", color=discord.Color.blue())
            status_text = f"💰 **金幣**: `{coins}`\n❤️ **生命值**: {hp_display} / {max_hp}\n✨ **狀態**: `{current_buff_text}`"
            embed.add_field(name="📊 目前狀態", value=status_text, inline=False)
            
            item_list = [f"• **{n}**: {c} 個" for n, c in inventory.items() if c > 0]
            embed.add_field(name="🥕 儲藏物資", value="\n".join(item_list) if item_list else "空空如也", inline=False)
            await message.channel.send(embed=embed)

        elif cmd == "!領取物資":
            test_inventory = {"普通蘿蔔 🍠": 10, "🥇 黃金蘿蔔": 5, "🧊 冰晶蘿蔔": 2}
            ref.update({"inventory": test_inventory, "hp": 100})
            await message.channel.send("🎁 測試物資已發放！")

        # --- 農場與功能性指令 ---
        elif cmd == "!運勢": await handle_fortune(message, user_id, username, user_data, ref)
        elif cmd == "!拔蘿蔔": await handle_pull_carrot(message, user_id, username, user_data, ref)
        elif cmd == "!蘿蔔圖鑑": await handle_carrot_encyclopedia(message, user_id, user_data, ref)
        elif cmd == "!收成蘿蔔": await handle_harvest_carrot(message, user_id, user_data, ref)
        elif cmd == "!農場總覽" or cmd == "!土地狀態": await show_farm_overview(client, message, user_id, user_data, ref)
        elif cmd == "!冒險商店": await handle_adventure_shop(message, user_data)
        elif cmd == "!購買": await handle_buy_item(message, user_id, user_data, ref, parts[1] if len(parts)>1 else "")
        # ... (其餘指令如 !種蘿蔔, !升級土地 等請按此格式繼續列出)

    except Exception as e:
        await message.channel.send("❌ 指令執行發生錯誤。")
        print(f"[Error] {cmd}: {e}")

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
