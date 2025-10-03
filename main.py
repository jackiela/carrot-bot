import discord
import os
import json
import datetime
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
    handle_farm_status,
    handle_buy_fertilizer,
    handle_upgrade_land,
    handle_land_progress,
    handle_resource_status
)

# ===== Discord Bot 初始化 =====
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# ===== Firebase 初始化 =====
firebase_json = os.getenv("FIREBASE_CREDENTIAL_JSON")
cred_dict = json.loads(firebase_json)

cred = credentials.Certificate(cred_dict)
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://carrotbot-80059-default-rtdb.asia-southeast1.firebasedatabase.app'  # ← 改成你的 Firebase 專案網址
})

# ===== 使用者資料讀取與初始化 =====
def get_user_data(user_id, username):
    ref = db.reference(f"/users/{user_id}")
    data = ref.get()
    if not data:
        data = {
            "name": username,
            "carrots": [],
            "last_fortune": "",
            "carrot_pulls": {},
            "coins": 50,
            "fertilizers": {
                "普通肥料": 1,
                "高級肥料": 0,
                "神奇肥料": 0
            },
            "farm": {
                "land_level": 1,
                "pull_count": 0,
                "status": "未種植"
            },
            "welcome_shown": False
        }
        ref.set(data)
    return data, ref

# ===== 指令頻道限制（可自訂）=====
COMMAND_CHANNELS = {
    "!運勢": 1421065753595084800,
    "!拔蘿蔔": 1421518540598411344,
    "!蘿蔔圖鑑": 1421518540598411344,
    "!蘿蔔排行": 1421518540598411344,
    "!種蘿蔔": 1423335407105343589,
    "!收成": 1423335407105343589,
    "!農場狀態": 1423335407105343589,
    "!購買肥料": 1423335407105343589,
    "!升級土地": 1423335407105343589,
    "!土地進度": 1423335407105343589,
    
}

# ===== Bot 指令處理 =====
@client.event
async def on_message(message):
    if message.author.bot:
        return

    user_id = str(message.author.id)
    username = str(message.author.display_name)
    today = datetime.datetime.now().date().isoformat()

    user_data, ref = get_user_data(user_id, username)

    # 👋 歡迎訊息（只在指定頻道顯示一次）
    CARROT_CHANNEL_ID = 1423335407105343589
    if message.channel.id == CARROT_CHANNEL_ID and not user_data["welcome_shown"]:
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

    content = message.content.strip()

    # 頻道限制
    if content in COMMAND_CHANNELS:
        allowed_channel = COMMAND_CHANNELS[content]
        if message.channel.id != allowed_channel:
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
            fertilizer = parts[1]
            await handle_plant_carrot(message, user_id, user_data, ref, fertilizer)
        else:
            await message.channel.send("❓ 請使用正確格式：`!種蘿蔔 普通肥料`")

    elif content == "!收成蘿蔔":
        await handle_harvest_carrot(message, user_id, user_data, ref)

    elif content == "!升級土地":
        await handle_upgrade_land(message, user_id, user_data, ref)

    elif content == "!資源狀態":
        await handle_resource_status(message, user_id, user_data)

    elif content == "!農場狀態":
        await handle_farm_status(message, user_id, user_data)

    elif content == "!土地進度":
        await handle_land_progress(message, user_id, user_data)
        
# ===== 啟動 Bot =====
from keep_alive import keep_alive   # ← 確保有這行
keep_alive()                        # ← 啟動 Flask 假伺服器

TOKEN = os.getenv("DISCORD_TOKEN")
client.run(TOKEN)
