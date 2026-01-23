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
    handle_fortune, handle_pull_carrot, handle_carrot_encyclopedia,
    handle_carrot_ranking, handle_carrot_fact, handle_carrot_recipe,
    handle_carrot_tip, handle_plant_carrot, handle_harvest_carrot,
    handle_buy_fertilizer, handle_upgrade_land, handle_land_progress,
    show_farm_overview, handle_give_coins, handle_buy_glove,
    handle_glove_encyclopedia, handle_carrot_info, handle_special_carrots,
    handle_open_lucky_bag, handle_buy_decoration, harvest_loop,
    GLOVE_SHOP, DECORATION_SHOP, check_and_post_update,
    handle_adventure_shop, handle_buy_item, handle_eat_carrot, 
    handle_bag, handle_sell_carrot
)
from utils import get_today, get_now, is_admin
from fastapi import FastAPI
from fastapi.middleware.wsgi import WSGIMiddleware
from flask import Flask
import threading
import uvicorn

# ===================== Discord Bot 初始化 =====================
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# ===================== Firebase 初始化 =====================
firebase_json = os.getenv("FIREBASE_CREDENTIAL_JSON")
if firebase_json:
    cred_dict = json.loads(firebase_json)
    cred = credentials.Certificate(cred_dict)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://carrotbot-80059-default-rtdb.asia-southeast1.firebasedatabase.app'
        })

# ===================== 使用者資料 =====================
def get_user_data(user_id, username):
    ref = db.reference(f"/users/{user_id}")
    data = ref.get() or {}
    data.setdefault("name", username)
    data.setdefault("carrots", [])
    data.setdefault("coins", 50)
    data.setdefault("fertilizers", {"普通肥料": 1, "高級肥料": 0, "神奇肥料": 0})
    data.setdefault("farm", {"land_level": 1, "pull_count": 0, "status": "未種植"})
    data.setdefault("last_login", "")
    data.setdefault("gloves", [])
    data.setdefault("decorations", [])
    data.setdefault("inventory", {})
    ref.update(data)
    return data, ref

async def check_daily_login_reward(message, user_id, user_data, ref):
    today = get_today()
    if user_data.get("last_login") != today:
        # 🎁 明天開始，每天只給固定隨機金幣
        reward = random.randint(5, 15)
        
        user_data["coins"] = user_data.get("coins", 0) + reward
        user_data["last_login"] = today
        
        # 更新資料庫
        ref.update({
            "coins": user_data["coins"], 
            "last_login": today
        })
        
        await message.channel.send(f"🎁 每日獎勵：獲得 `{reward}` 金幣！")

# ===================== 指令頻道限制 =====================
COMMAND_CHANNELS = {
    "!運勢": 1421065753595084800, "!拔蘿蔔": 1421518540598411344,
    "!蘿蔔圖鑑": 1421518540598411344, "!蘿蔔排行": 1421518540598411344,
    "!種蘿蔔": 1423335407105343589, "!收成蘿蔔": 1423335407105343589,
    "!升級土地": 1423335407105343589, "!土地進度": 1423335407105343589,
    "!土地狀態": 1423335407105343589, "!農場總覽": 1423335407105343589,
    "!購買肥料": 1423335407105343589, "!商店": 1423335407105343589,
    "!開運福袋": 1423335407105343589, "!購買手套": 1423335407105343589,
    "!購買裝飾": 1423335407105343589, "!特殊蘿蔔一覽": 1423335407105343589,
    "!冒險": 1453283600459104266, "!吃": 1453283600459104266,   
    "!背包": 1453283600459104266, "!冒險商店": 1453283600459104266,
    "!購買": 1453283600459104266, "!賣出": 1423335407105343589,
    "!倉庫": 1423335407105343589
}

# ===================== 輔助函數 =====================
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

# ===================== 事件處理 =====================
@client.event
async def on_ready():
    print(f"✅ Bot 已登入：{client.user}")
    client.loop.create_task(check_and_post_update(client, db)) 
    client.loop.create_task(harvest_loop(client, db))
    print("🌱 背景任務啟動完成")

@client.event
async def on_message(message):
    if message.author.bot: return
    content = (message.content or "").strip()
    if not content: return
    
    user_id = str(message.author.id)
    username = message.author.display_name
    
    try:
        user_data, ref = get_user_data(user_id, username)
        await check_daily_login_reward(message, user_id, user_data, ref)
    except Exception as e:
        print(f"❌ 基礎資料處理失敗: {e}")
        return

    parts = content.split()
    cmd = parts[0]
    
    if cmd in COMMAND_CHANNELS:
        allowed = COMMAND_CHANNELS[cmd]
        if message.channel.id != allowed and getattr(message.channel, "parent_id", None) != allowed:
            await message.channel.send(f"⚠️ 指令只能在 <#{allowed}> 使用")
            return

    farm_cmds = ["!種蘿蔔", "!收成蘿蔔", "!升級土地", "!土地進度", "!農場總覽", "!土地狀態", "!購買肥料", "!購買手套", "!購買裝飾", "!開運福袋"]
    if cmd in farm_cmds and not is_in_own_farm_thread(message):
        parent = message.channel.parent if isinstance(message.channel, discord.Thread) else message.channel
        thread = await get_or_create_farm_thread(parent, message.author)
        if thread:
            await message.channel.send(f"✅ 請至您的田地操作：{thread.jump_url}")
            return

    try:
        # --- 冒險與補給 ---
        if cmd == "!冒險":
            await adventure.start_adventure(message, user_id, user_data, ref, parts[1] if len(parts)>1 else "新手森林")
        elif cmd == "!吃":
            await handle_eat_carrot(message, user_id, user_data, ref, " ".join(parts[1:]))
        elif cmd == "!背包":
            await handle_bag(message, user_id, user_data, user_ref)
        
        # --- 農場指令 ---
        elif cmd == "!種蘿蔔":
            await handle_plant_carrot(message, user_id, user_data, ref, parts[1] if len(parts)>1 else "普通肥料")
        elif cmd == "!收成蘿蔔":
            await handle_harvest_carrot(message, user_id, user_data, ref)
        elif cmd == "!升級土地":
            await handle_upgrade_land(message, user_id, user_data, ref)
        elif cmd == "!土地進度":
            await handle_land_progress(message, user_id, user_data, ref)
        elif cmd in ["!農場總覽", "!土地狀態", "!倉庫"]:
            await show_farm_overview(client, message, user_id, user_data, ref)
        elif cmd == "!賣出":
            # parts[1:] 會抓到 ["普通蘿蔔", "5"] 這樣的參數
            await handle_sell_carrot(message, user_id, user_data, ref, parts[1:])
            
        # --- 商店系統 (整合 2.0 介面) ---
        elif cmd == "!商店":
            coins = user_data.get("coins", 0)
            embed = discord.Embed(title="🏪 胡蘿蔔商店", color=discord.Color.orange())
            
            embed.add_field(
                name="🎁 開運福袋", 
                value="**80 金幣**｜隨機獲得金幣 / 肥料 / 裝飾\n使用指令：`!開運福袋`", 
                inline=False
            )
            
            glove_text = (
                "• **幸運手套** — 100 💰｜大吉時額外掉出一根蘿蔔\n"
                "• **農夫手套** — 150 💰｜收成時金幣 +20%\n"
                "• **強化手套** — 200 💰｜種植時間 -1 小時\n"
                "• **神奇手套** — 500 💰｜收成時有機率獲得稀有蘿蔔\n"
                "指令：`!購買手套 [名稱]`"
            )
            embed.add_field(name="🧤 農場手套", value=glove_text, inline=False)
            
            decor_text = (
                "• **花圃** — 80 💰\n"
                "• **木柵欄** — 100 💰\n"
                "• **竹燈籠** — 150 💰\n"
                "• **鯉魚旗** — 200 💰\n"
                "• **聖誕樹** — 250 💰\n"
                "指令：`!購買裝飾 [名稱]`"
            )
            embed.add_field(name="🏡 農場裝飾", value=decor_text, inline=False)
            
            embed.set_footer(text=f"💰 您目前擁有 {coins} 金幣")
            await message.channel.send(embed=embed)

        elif cmd == "!開運福袋":
            await handle_open_lucky_bag(client, message, user_id, user_data, ref)
        elif cmd == "!購買手套":
            await handle_buy_glove(client, message, user_id, user_data, ref, parts[1] if len(parts)>1 else "", show_farm_overview)
        elif cmd == "!購買裝飾":
            await handle_buy_decoration(message, user_id, user_data, ref, parts[1] if len(parts)>1 else "")
        elif cmd == "!購買肥料":
            await handle_buy_fertilizer(message, user_id, user_data, ref, parts[1] if len(parts)>1 else "")

        # --- 其他基礎指令 ---
        elif cmd == "!運勢": await handle_fortune(message, user_id, username, user_data, ref)
        elif cmd == "!拔蘿蔔": await handle_pull_carrot(message, user_id, username, user_data, ref)
        elif cmd == "!蘿蔔圖鑑": await handle_carrot_encyclopedia(message, user_id, user_data, ref)
        elif cmd == "!冒險商店": await handle_adventure_shop(message, user_data)
        elif cmd == "!購買": await handle_buy_item(message, user_id, user_data, ref, parts[1] if len(parts)>1 else "")

    except Exception as e:
        print(f"❌ 指令執行錯誤 {cmd}: {e}")
        await message.channel.send("❌ 執行指令時發生預期外的錯誤。")

# ===================== Web 啟動 =====================
from flask import Flask, request, jsonify
from flask_cors import CORS  # 👈 解決網頁跨網域連線問題
from carrot_commands import fortunes # 👈 引入你的占卜文字字典

flask_app = Flask(__name__)
CORS(flask_app) # 👈 允許網頁端存取 API

@flask_app.route("/")
def home(): 
    return "🟢 Carrot Bot Online"

# 🔮 專為網頁設計的純占卜路由
@flask_app.route("/api/web_fortune", methods=['GET'])
def web_fortune():
    try:
        # 1. 從 carrot_commands.py 的 fortunes 字典中隨機挑選等級 (大吉/中吉/...)
        fortune_levels = list(fortunes.keys())
        if not fortune_levels:
            raise ValueError("fortunes dictionary is empty")
            
        random_level = random.choice(fortune_levels)
        
        # 2. 從該等級的清單中隨機挑選一句建議文字
        random_advice = random.choice(fortunes[random_level])
        
        # 3. 回傳給網頁 (不涉及金幣、不存入資料庫)
        return jsonify({
            "status": "success",
            "fortune": random_level,
            "advice": random_advice
        })
    except Exception as e:
        print(f"❌ Web API 錯誤: {e}")
        return jsonify({
            "status": "error", 
            "message": "祭壇感應中斷，請確認後端資料結構"
        }), 500

fastapi_app = FastAPI()
fastapi_app.mount("/", WSGIMiddleware(flask_app))

if __name__ == '__main__':
    # 啟動 Discord Bot
    token = os.getenv("DISCORD_TOKEN")
    if token:
        threading.Thread(target=lambda: client.run(token), daemon=True).start()
    
    # 啟動 Web 伺服器 (包含 Flask 與 FastAPI)
    uvicorn.run(fastapi_app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
