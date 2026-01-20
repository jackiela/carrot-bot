import os
import json
import datetime
import random
import discord
import asyncio
import io
from datetime import datetime, timezone, timedelta
from firebase_admin import db
from firebase_init import get_user_ref
# ===== 導入自訂工具 =====
from utils import (
    get_today, get_now, get_remaining_hours,
    get_carrot_thumbnail, get_carrot_rarity_color, 
    get_decoration_thumbnail
)
from utils_sanitize import sanitize_user_data
from carrot_data import common_carrots, rare_carrots, legendary_carrots, all_carrots, recipes, carrot_tips, carrot_facts
from fortune_data import fortunes


# ===== 範例：取得某個使用者資料 =====
# user_ref = get_user_ref(user_id)
# user_data = user_ref.get() or {}

def get_user_ref(user_id):
    """取得使用者資料的 Firebase 參考，若不存在會自動建立"""
    return db.reference(f"users/{user_id}")

def get_all_users_ref():
    """取得所有使用者資料的 Firebase 參考"""
    return db.reference("/")

# 💰 裝飾品被動金幣收益（每日 Coins/Day）
# 數值已調整以符合每日的期望收益
DECORATION_PASSIVE_BONUS = {
    "花圃": 5,   # 每日 5 金幣
    "木柵欄": 10,  # 每日 10 金幣
    "竹燈籠": 15,  # 每日 15 金幣
    "鯉魚旗": 20, # 每日 20 金幣
    "聖誕樹": 25  # 每日 25 金幣
}



# 📌 請設定您的版本號和頻道 ID
# 假設這是您修復 bug (2.0.1) 和修復 Port 衝突 (2.0.2) 之後的下一個版本
CURRENT_VERSION = "2.0.5" 
# ⚠️ 請替換成您實際要發布「更新通知」的頻道 ID！
UPDATE_CHANNEL_ID = 1428618044992913448

async def check_and_post_update(bot: discord.Client, db_module):
    """檢查版本並發布更新日誌"""
    try:
        # 1. 取得 Firebase 記錄的上次版本
        # ⚠️ 使用傳入的 db_module 存取 Firebase
        # 注意：路徑從 /bot_config/last_version 改為 /bot_status/last_posted_version 更通用
        version_ref = db_module.reference("/bot_status/last_posted_version")
        last_version = version_ref.get()
        
        # 2. 比較版本號
        if last_version != CURRENT_VERSION:
            
            # --- 版本更新內容 (這次的主要更新內容) ---
            update_notes = [
                f"**🚀 胡蘿蔔機器人更新至 {CURRENT_VERSION} 囉！**",
           "### 🐛 系統修復",
            "• **【修復】** 修正了「農場總覽」在擁有裝飾品時會導致指令崩潰的問題。",
            "• **【優化】** 提升了圖片載入的穩定性。",
            "",
            "✨ 祝大家種植愉快！輸入 `!農場總覽` 查看新收益！"
            ]
            # --- 結束更新日誌 ---

             # 3. 發送更新通知
            channel = bot.get_channel(UPDATE_CHANNEL_ID)
            if not channel:
                 channel = await bot.fetch_channel(UPDATE_CHANNEL_ID)
                 
            if channel:
                # 🌟 修正點：先發送一個帶有 @everyone 的簡短訊息
                try:
                    await channel.send(f"@everyone 📢 **胡蘿蔔農場更新至 V{CURRENT_VERSION} 囉！** 🚀 點擊查看新功能和修復內容：")
                except Exception as e:
                    print(f"[WARN] 無法發送 @everyone 提及: {e}")
                
                # 接著發送詳細的 Embed
                embed = discord.Embed(
                    title=f"📢 機器人更新通知 {CURRENT_VERSION}",
                    description="\n".join(update_notes),
                    color=discord.Color.blue()
                )
                embed.set_footer(text=f"上次版本: {last_version or '2.0.4'}")
                await channel.send(embed=embed)
                await channel.send("="*20) # 方便區隔
                
                # 4. 更新 Firebase 紀錄的版本號
                version_ref.set(CURRENT_VERSION)
            else:
                print(f"[WARN] 無法找到 ID 為 {UPDATE_CHANNEL_ID} 的更新通知頻道。")

        else:
            print(f"[INFO] 當前版本 {CURRENT_VERSION} 與上次紀錄版本一致，不發布通知。")

    except Exception as e:
        print(f"[ERROR] 版本檢查與更新發布失敗: {e}")
        

    # ===== 蘿蔔占卜 =====

async def handle_fortune(message, user_id, username, user_data, ref, force=False):
    from utils import get_fortune_thumbnail
    # --- ✅ 使用者資料防呆，防止型態錯誤導致崩潰 ---
    user_data = sanitize_user_data(user_data)
        
    today = get_today()
    last_fortune_date = user_data.get("last_fortune_date")
    is_admin = message.author.guild_permissions.administrator

    if not force and last_fortune_date == today and not is_admin:
        await message.channel.send("🔒 你今天已抽過運勢囉，明天再來吧！")
        return

    fortune = random.choice(list(fortunes.keys()))
    advice = random.choice(fortunes[fortune])
    reward = random.randint(
        *(12, 15) if "大吉" in fortune else
        (8, 11) if "中吉" in fortune else
        (4, 7) if "小吉" in fortune else
        (1, 3) if "吉" in fortune else
        (0, 0)
    )

    user_data["coins"] = user_data.get("coins", 0) + reward
    user_data["last_fortune"] = fortune
    user_data["last_fortune_date"] = today

    extra_text = ""
    if "大吉" in fortune and isinstance(user_data.get("gloves"), list) and "幸運手套" in user_data["gloves"]:
        extra_carrot = random.choice(common_carrots)
        user_data.setdefault("carrots", [])
        user_data["carrots"].append(extra_carrot)
        extra_text = f"🧤 幸運手套發揮作用！你額外獲得一根 {extra_carrot} 🥕"

    ref.set(user_data)

    emoji_map = {
        "大吉": "🎯", "中吉": "🍀", "小吉": "🌤", "吉": "🥕", "凶": "💀"
    }
    emoji = next((v for k, v in emoji_map.items() if k in fortune), "")
    fortune_display = f"{emoji} {fortune}"

    embed = discord.Embed(
        title=f"🎴 今日運勢：{fortune_display}",
        description=advice,
        color=discord.Color.orange() if "大吉" in fortune else
              discord.Color.green() if "中吉" in fortune else
              discord.Color.blue() if "小吉" in fortune else
              discord.Color.yellow() if "吉" in fortune else
              discord.Color.red()
    )
    embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
    embed.set_thumbnail(url=get_fortune_thumbnail(fortune))
    embed.set_footer(text=f"📅 {today}｜🌙 過了晚上十二點可以再抽一次")

    embed.add_field(name="💰 金幣獎勵", value=f"你獲得了 {reward} 金幣！" if reward > 0 else "明天再接再厲！", inline=False)
    if extra_text:
        embed.add_field(name="🧤 幸運加成", value=extra_text, inline=False)

    await message.channel.send(embed=embed)
    

# ===== 拔蘿蔔 (雙軌並行版：圖鑑不變 + 背包簡化) =====
async def handle_pull_carrot(message, user_id, username, user_data, ref):
    # --- ✅ 使用者資料防呆 ---
    user_data = sanitize_user_data(user_data)
    
    today = get_today()
    pulls = user_data.get("carrot_pulls", {})
    today_pulls = pulls.get(today, 0)

    # ===== 拔取次數上限檢查 =====
    if today_pulls >= 3:
        embed = discord.Embed(
            title="🔒 拔蘿蔔次數已達上限",
            description="今天已拔過三次蘿蔔囉，請明天再來！",
            color=discord.Color.red()
        )
        embed.set_footer(text=f"📅 {today}｜🌙 晚上十二點過後可再拔")
        await message.channel.send(embed=embed)
        return

    # ===== 特殊池判定 =====
    gloves = user_data.get("gloves", [])
    if isinstance(gloves, int): gloves = []
    elif isinstance(gloves, str): gloves = [gloves]

    land_level = user_data.get("farm", {}).get("land_level", 1)
    pool_type = "normal"

    if "神奇手套" in gloves and random.random() < 0.2:
        pool_type = "special"
    elif land_level >= 4 and random.random() < 0.1:
        pool_type = "special"

    # ===== 抽卡邏輯 =====
    raw_result = ""
    if pool_type == "special":
        # 特殊池的名稱通常比較短，直接設定
        raw_result = random.choices(
            ["🌈 彩虹蘿蔔", "🥇 黃金蘿蔔", "🍀 幸運蘿蔔", "🧊 冰晶蘿蔔"],
            weights=[0.4, 0.3, 0.2, 0.1]
        )[0]
    else:
        # 從 carrot_data.py 抽出的原話，例如："你拔到了一根搞笑蘿蔔 🤡"
        raw_result = pull_carrot()

    # 🌟 核心簡化過濾器 (為了背包使用)
    clean_name = raw_result.replace("你拔到了一根", "").replace("你拔到了", "").replace("！", "").strip()

    # ===== 更新資料 (圖鑑用 raw_result / 背包用 clean_name) =====
    
    # 1. 更新圖鑑 (保持舊有的長句子，確保舊進度不壞掉)
    user_data.setdefault("carrots", [])
    is_new = raw_result not in user_data["carrots"]
    if is_new:
        user_data["carrots"].append(raw_result)

    # 2. 🌟 存入背包 (使用簡短乾淨的 clean_name)
    inventory = user_data.setdefault("inventory", {})
    inventory[clean_name] = inventory.get(clean_name, 0) + 1

    # 3. 更新拔取次數
    user_data["carrot_pulls"][today] = today_pulls + 1
    user_data["carrot_pulls"]["last_pool"] = pool_type

    remaining = 2 - today_pulls

    # ===== 蘿蔔事件觸發 (維持原邏輯) =====
    triggered_event = None
    event_roll = random.random()
    now = datetime.now()
    if land_level >= 5 and event_roll < 0.1:
        triggered_event = random.choice(["神秘訪客", "蘿蔔大逃亡", "蘿蔔爆彈", "鳥群來襲", "蘿蔔占卜師", "蘿蔔金幣雨", "冰封蘿蔔"])
        # ... (事件代碼省略，請保留您原本的事件效果實作) ...

    # ===== 更新 Firebase =====
    ref.set(user_data)

    # ===== 結果 Embed 顯示 =====
    color = get_carrot_rarity_color(clean_name)
    embed = discord.Embed(
        title="💪 拔蘿蔔結果",
        description=f"✨ **{raw_result}**", # 顯示原話增加演出感
        color=color
    )
    embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
    embed.set_thumbnail(url=get_carrot_thumbnail(clean_name))
    
    # 圖鑑狀態
    embed.add_field(
        name="📖 圖鑑狀態",
        value="✨ **發現新物種！**" if is_new else "📘 圖鑑已記錄",
        inline=True
    )
    
    # 🎒 背包狀態 (強調簡化後的名稱)
    embed.add_field(
        name="🎒 背包存儲",
        value=f"已存入道具：`{clean_name}`\n目前持有：**{inventory[clean_name]}** 個",
        inline=True
    )

    embed.add_field(name="🔁 今日剩餘", value=f"{remaining} 次", inline=False)

    if pool_type == "special":
        embed.add_field(name="🎯 運氣不錯", value="你進入了特殊池，這根蘿蔔品質很高！", inline=False)

    if triggered_event:
        embed.add_field(name="🎉 突發事件", value=f"剛才發生了「{triggered_event}」！", inline=False)

    embed.set_footer(text=f"💡 使用指令：!吃 {clean_name}")
    
    await message.channel.send(embed=embed)
    
    # ===== 蘿蔔圖鑑 =====
async def handle_carrot_encyclopedia(message, user_id, user_data, ref):
    """📖 顯示蘿蔔圖鑑進度"""
    # --- ✅ 使用者資料防呆，防止型態錯誤導致崩潰 ---
    user_data = sanitize_user_data(user_data)

    collected = user_data.get("carrots", [])
    if not collected:
        embed = discord.Embed(
            title="📖 蘿蔔圖鑑",
            description="你的圖鑑還是空的，快去拔蘿蔔吧！🌱",
            color=discord.Color.light_gray()
        )
        embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
        await message.channel.send(embed=embed)
        return

    # --- 📊 統計 ---
    total = len(all_carrots)
    progress = len(collected)
    common_count = len([c for c in collected if c in common_carrots])
    rare_count = len([c for c in collected if c in rare_carrots])
    legendary_count = len([c for c in collected if c in legendary_carrots])

    # --- 🌈 進度條 ---
    bar_length = 20
    filled_length = int(progress / total * bar_length)
    progress_bar = "█" * filled_length + "░" * (bar_length - filled_length)

    # --- 🧡 Embed 設定 ---
    embed = discord.Embed(
        title="📖 蘿蔔圖鑑進度",
        description=f"{progress}/{total} 種\n{progress_bar}",
        color=discord.Color.orange()
    )
    embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)

    embed.add_field(
        name="🌿 普通蘿蔔",
        value=f"{common_count}/{len(common_carrots)} 種",
        inline=True
    )
    embed.add_field(
        name="🌸 稀有蘿蔔",
        value=f"{rare_count}/{len(rare_carrots)} 種",
        inline=True
    )
    embed.add_field(
        name="🌟 傳說蘿蔔",
        value=f"{legendary_count}/{len(legendary_carrots)} 種",
        inline=True
    )

    # --- 🥕 已收集清單 ---
    collected_list = "\n".join([f"・{c}" for c in collected])
    if len(collected_list) > 1024:
        collected_list = collected_list[:1020] + "..."

    embed.add_field(
        name="📚 已收集的蘿蔔",
        value=collected_list,
        inline=False
    )

    embed.set_footer(text="快去收集更多蘿蔔來完成圖鑑吧！")

    await message.channel.send(embed=embed)

# ===== 蘿蔔排行榜 =====
async def handle_carrot_ranking(message):
    # 從 Firebase 取得所有玩家資料
    data = db.reference("/users").get()

    if not data:
        await message.channel.send("📊 目前還沒有任何玩家收集蘿蔔！")
        return

    # 排行資料整理
    ranking = sorted(
        data.items(),
        key=lambda x: len(x[1].get("carrots", [])),
        reverse=True
    )

    total_carrots = len(all_carrots)

    reply = "🏆 **蘿蔔收集排行榜** 🥕\n"

    for i, (uid, info) in enumerate(ranking[:5], start=1):
        player_name = info.get("name", "未知玩家")
        count = len(info.get("carrots", []))
        reply += f"{i}. {player_name} — {count}/{total_carrots} 種\n"

    await message.channel.send(reply)


# ===== 胡蘿蔔小知識 =====
async def handle_carrot_fact(message, user_id, user_data, ref):
    # --- ✅ 使用者資料防呆，防止型態錯誤導致崩潰 ---
    user_data = sanitize_user_data(user_data)
    
    fact = random.choice(carrot_facts)
    await message.channel.send(f"🥕 胡蘿蔔小知識：{fact}")

# ===== 胡蘿蔔料理 =====
async def handle_carrot_recipe(message, user_id, user_data, ref):
    recipe_name = random.choice(list(recipes.keys()))
    detail = recipes[recipe_name]
    await message.channel.send(
        f"🍴 今日推薦胡蘿蔔料理：**{recipe_name}**\n📖 做法：\n{detail}"
    )

# ===== 種植小貼士 =====
async def handle_carrot_tip(message, user_id, user_data, ref):
    # --- ✅ 使用者資料防呆，防止型態錯誤導致崩潰 ---
    user_data = sanitize_user_data(user_data)
    
    tip = random.choice(carrot_tips)
    await message.channel.send(f"🌱 胡蘿蔔種植小貼士：{tip}")

# ======================================
# ✅ 通用輔助：確認玩家是否在自己的田地
# ======================================
async def ensure_player_thread(message, user_data=None):
    """
    確保使用者在自己的田地串中使用指令；
    若不在，則自動建立新串或提示跳轉。
    """
    # --- 安全檢查 ---
    if user_data:
        user_data = sanitize_user_data(user_data)

    expected_name = f"{message.author.display_name} 的田地"
    current_channel = message.channel

    # 🔎 取得父頻道（避免 Thread 時出錯）
    parent_channel = current_channel.parent if isinstance(current_channel, discord.Thread) else current_channel

    # 🔍 嘗試尋找現有田地串（含封存）
    target_thread = next((t for t in parent_channel.threads if t.name == expected_name), None)
    if not target_thread:
        async for t in parent_channel.archived_threads(limit=None):
            if t.name == expected_name:
                target_thread = t
                break

    # 🧭 若目前不是在自己的田地串
    if not isinstance(current_channel, discord.Thread) or current_channel.name != expected_name:
        if target_thread:
            await message.channel.send(f"⚠️ 請在你的田地串中使用此指令：{target_thread.jump_url}")
            return None
        new_thread = await parent_channel.create_thread(
            name=expected_name,
            type=discord.ChannelType.public_thread,
            auto_archive_duration=1440
        )
        await new_thread.send(f"📌 已為你建立田地串，請在此使用指令！")
        return new_thread

    return current_channel


def pull_carrot():
    roll = random.randint(1, 100)
    if roll <= 70:
        return random.choice(common_carrots)
    elif roll <= 95:
        return random.choice(rare_carrots)
    else:
        return random.choice(legendary_carrots)

def pull_carrot_by_farm(fertilizer="普通肥料", land_level=1):
    base_roll = random.randint(1, 100)
    bonus = 0
    if fertilizer == "高級肥料":
        # 從 5 調整為 10
        bonus += 10 
    elif fertilizer == "神奇肥料":
        bonus += 20
    if land_level >= 3:
        bonus += (land_level - 2) * 5

    roll = base_roll + bonus
    reward_ranges = {
        "common": (5, 10),
        "rare": (20, 40),
        "legendary": (100, 200)
    }

    if roll <= 70:
        return random.choice(common_carrots), random.randint(*reward_ranges["common"])
    elif roll <= 95:
        return random.choice(rare_carrots), random.randint(*reward_ranges["rare"])
    else:
        return random.choice(legendary_carrots), random.randint(*reward_ranges["legendary"])
        
        
# --- 種蘿蔔主函式 (優化版) ---
async def handle_plant_carrot(message, user_id, user_data, ref=None, fertilizer="普通肥料"):
    # --- ✅ 使用者資料防呆與環境檢查 ---
    user_data = sanitize_user_data(user_data)

    current_channel = await ensure_player_thread(message)
    if current_channel is None:
        return

    # --- Firebase 自動建立 ref ---
    if ref is None:
        # 假設您的 utils 有 get_user_ref，若無則改用 db.reference
        from firebase_admin import db
        ref = db.reference(f"/users/{user_id}")

    # --- 時區統一（台灣）---
    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz)

    farm = user_data.get("farm", {})
    fertilizers = user_data.get("fertilizers", {})
    land_level = farm.get("land_level", 1)
    pull_count = farm.get("pull_count", 0)
    gloves = user_data.get("gloves", [])

    # --- 1. 狀態檢查 ---
    if farm.get("status") == "planted":
        await current_channel.send("🌱 你已經種了一根蘿蔔，請先收成再種新的！")
        return

    # --- 2. 肥料檢查 ---
    if fertilizers.get(fertilizer, 0) <= 0:
        await current_channel.send(
            f"❌ 你沒有 {fertilizer}\n💰 目前金幣：{user_data.get('coins', 0)}"
        )
        return

    # --- 3. 收成時間計算 ---
    base_hours = 24
    fertilizer_bonus = {"神奇肥料": -8, "高級肥料": -4, "普通肥料": 0}.get(fertilizer, 0)
    land_bonus = land_level * -2

    glove_effects = {
        "幸運手套": "🎯 大吉時掉出蘿蔔",
        "農夫手套": "💰 收成金幣 +20%",
        "強化手套": "⏳ 種植時間 -1 小時",
        "神奇手套": "🌟 稀有機率提升"
    }

    glove_bonus = 0
    glove_display_list = []

    if "強化手套" in gloves:
        glove_bonus -= 1
        glove_display_list.append(glove_effects["強化手套"])

    for g in gloves:
        if g != "強化手套":
            # 避免重複添加相同描述
            desc = glove_effects.get(g, g)
            if desc not in glove_display_list:
                glove_display_list.append(desc)

    if not glove_display_list:
        glove_display_list.append("無（沒有手套效果）")

    glove_display_text = "\n".join(glove_display_list)

    # 計算總時長並確保最少 1 小時
    total_hours = max(1, base_hours + fertilizer_bonus + land_bonus + glove_bonus)
    harvest_time = now + timedelta(hours=total_hours)

    # --- 4. 更新本地資料數據 ---
    fertilizers[fertilizer] -= 1
    
    new_farm_data = {
        "plant_time": now.isoformat(),
        "harvest_time": harvest_time.isoformat(),
        "status": "planted",
        "fertilizer": fertilizer,
        "land_level": land_level,
        "pull_count": pull_count,
        "thread_id": current_channel.id,
        "reminded": False
    }

    # --- 5. 🌟 安全寫入 Firebase (使用 update 避免覆蓋) ---
    # 我們只更新 farm 與 fertilizers 兩個欄位，保留其他資料(如 HP)
    ref.update({
        "farm": new_farm_data,
        "fertilizers": fertilizers
    })

    # --- 6. 建立 Embed 顯示 ---
    remaining = harvest_time - now
    left_hours = remaining.days * 24 + remaining.seconds // 3600
    minutes = (remaining.seconds % 3600) // 60

    embed = discord.Embed(
        title="🌱 成功種下蘿蔔！",
        description=f"你使用 **{fertilizer}** 種下了一根蘿蔔！準備等待收成吧！",
        color=discord.Color.green()
    )
    # 建議更換為您自己的圖案 URL
    embed.set_thumbnail(url="https://jackiela.github.io/carrot-bot/images/plant.png")
    
    embed.add_field(name="📅 預計收成時間", value=f"**{harvest_time.strftime('%Y-%m-%d %H:%M')}**", inline=False)
    embed.add_field(name="⏳ 剩餘時間", value=f"**約 {left_hours} 小時 {minutes} 分鐘**", inline=False)

    # 時間縮減細節
    shorten_lines = []
    if fertilizer_bonus != 0: shorten_lines.append(f"🧪 {fertilizer}：`-{abs(fertilizer_bonus)} 小時`")
    if land_bonus != 0: shorten_lines.append(f"🏕️ 土地 Lv.{land_level}：`-{abs(land_bonus)} 小時`")
    if glove_bonus != 0: shorten_lines.append(f"🧤 強化手套：`-{abs(glove_bonus)} 小時`")

    total_short = abs(fertilizer_bonus + land_bonus + glove_bonus)
    shorten_text = "\n".join(shorten_lines) if shorten_lines else "（無縮時加成）"

    embed.add_field(name=f"✂ 時間縮減（共 `{total_short}` 小時）", value=shorten_text, inline=False)
    embed.add_field(name="🧪 肥料庫存", value=f"{fertilizer}：剩餘 **{fertilizers[fertilizer]}** 個", inline=True)
    embed.add_field(name="🧤 目前生效手套", value=glove_display_text, inline=True)
    embed.set_footer(text="提示：收成時間到後，請輸入 !收成蘿蔔")

    await current_channel.send(embed=embed)
    
# =========================================
# 自動收成提醒與裝飾品金幣發放
# =========================================
# 確保您在檔案頂部有匯入：
# from datetime import datetime, timezone, timedelta
# from firebase_admin import db
# from utils import get_now, parse_datetime (假設這兩個 helper 函式已定義)

async def harvest_loop(bot, db_module):
    print("[INFO] harvest_loop 啟動")
    # 🌟 確保匯入 timedelta
    from datetime import timedelta 
    from utils import get_now, parse_datetime

    await bot.wait_until_ready()

    while not bot.is_closed():
        try:
            # 取得所有使用者
            ref = db_module.reference("/users")
            all_users = ref.get()

            if not all_users:
                await asyncio.sleep(60)
                continue

            now = get_now()

            for user_id, user_data in all_users.items():
                if not isinstance(user_data, dict):
                    continue
                
                # --- 💰 邏輯 A: 裝飾品收益 ---
                last_update_str = user_data.get("last_passive_coin_update")
                
                if not last_update_str:
                    # 如果從未領過，從 1 天前開始算 (即補償 1 天)
                    last_update = now - timedelta(days=1) 
                else:
                    try:
                        last_update = parse_datetime(last_update_str)
                    except:
                        last_update = now - timedelta(days=1)

                time_elapsed = now - last_update
                days_elapsed = time_elapsed.total_seconds() / 86400.0
                
                # 滿足門檻 (約 23 小時)
                if days_elapsed >= 0.958:
                    full_days_to_award = min(int(days_elapsed), 3) 
                    
                    total_daily_rate = 0
                    decorations = user_data.get("decorations", [])
                    # 這裡確保 DECORATION_PASSIVE_BONUS 在 carrot_commands.py 有定義
                    for deco in decorations:
                        total_daily_rate += DECORATION_PASSIVE_BONUS.get(deco, 0)
                    
                    total_daily_rate = min(total_daily_rate, 50)
                    coins_gained = full_days_to_award * total_daily_rate
                    
                    if coins_gained > 0:
                        current_coins = user_data.get("coins", 0)
                        final_gain = min(coins_gained, 150)
                        
                        user_ref = db_module.reference(f"/users/{user_id}")
                        # 🌟 建議更新方式：先算好新金幣，再一次 update
                        user_ref.update({
                            "coins": current_coins + final_gain,
                            "last_passive_coin_update": now.isoformat() 
                        })
                        print(f"[PASSIVE] {user_id} 獲得 {final_gain} 金幣")
                    else:
                        # 沒錢也要更新時間，避免下次重複掃描
                        db_module.reference(f"/users/{user_id}").update({
                            "last_passive_coin_update": now.isoformat()
                        })
                        
                # -----------------------------------
                # 🥕 邏輯 B: 蘿蔔收成提醒 (原功能)
                # -----------------------------------
                farm = user_data.get("farm", {})
                harvest_time_str = farm.get("harvest_time")
                thread_id = farm.get("thread_id")
                status = farm.get("status")
                is_reminded = farm.get("reminded", False)

                if not harvest_time_str or not thread_id or status != "planted" or is_reminded:
                    continue

                try:
                    harvest_time = parse_datetime(harvest_time_str)
                except Exception as e:
                    print(f"[WARN] harvest_time 解析失敗 ({user_id}): {e}")
                    continue

                # 到時間 → 發送提醒
                if now >= harvest_time:
                    thread = bot.get_channel(thread_id)
                    
                    if not thread:
                        try:
                            thread = await bot.fetch_channel(thread_id)
                        except:
                            pass

                    if thread:
                        try:
                            await thread.send(
                                f"🥕 <@{user_id}> 你的蘿蔔成熟啦！快來使用 `!收成蘿蔔` 🌾"
                            )
                            print(f"[SUCCESS] 已發送提醒給 {user_id}")
                        except Exception as e:
                            print(f"[ERROR] Thread 發送失敗 ({user_id}): {e}")
                    
                    # 標記為「已提醒」
                    farm["reminded"] = True
                    db_module.reference(f"/users/{user_id}/farm").update({"reminded": True})


        except Exception as e:
            print(f"[ERROR] harvest_loop 主體錯誤：{e}")

        await asyncio.sleep(60) # 每 60 秒掃描一次

# ===== 收成蘿蔔（修正版：收成進背包 + 雙軌制） =====
async def handle_harvest_carrot(message, user_id, user_data, ref):
    # --- ✅ 使用者資料防呆 ---
    user_data = sanitize_user_data(user_data)
    
    from utils import get_now, parse_datetime, get_remaining_time_str, get_carrot_thumbnail, get_carrot_rarity_color
    current_channel = await ensure_player_thread(message)
    if current_channel is None:
        return

    expected_thread_name = f"{message.author.display_name} 的田地"
    if current_channel.name != expected_thread_name:
        await message.channel.send("⚠️ 此指令僅能在你自己的田地串中使用！")
        return

    now = get_now()
    farm = user_data.get("farm", {})
    if farm.get("status") != "planted":
        await current_channel.send("🪴 你還沒種蘿蔔喔，請先使用 `!種蘿蔔`！")
        return

    harvest_time = parse_datetime(farm["harvest_time"])
    if now < harvest_time:
        time_str = get_remaining_time_str(harvest_time)
        await current_channel.send(f"⏳ 蘿蔔還在努力生長中！{time_str}才能收成喔～")
        return

    fertilizer = farm.get("fertilizer", "普通肥料")
    land_level = farm.get("land_level", 1)
    gloves = user_data.get("gloves", [])

    # ------ 1. 抽取收成結果 ------
    # 使用你現有的 pull_carrot_by_farm 函式
    raw_result, base_price = pull_carrot_by_farm(fertilizer, land_level)
    
    # 🌟 名稱簡化處理 (用於背包輸入：例如將「你拔到了一根普通紅蘿蔔」變成「普通紅蘿蔔 🍠」)
    # 這裡建議你的 pull_carrot 系統返回的 result 帶有 Emoji，我們去除引導語
    clean_name = raw_result.replace("你收成了一根", "").replace("你拔到了一根", "").replace("！", "").strip()

    # ------ 2. 雙軌制邏輯：進背包 vs 換金幣 ------
    inventory = user_data.setdefault("inventory", {})
    coins = user_data.get("coins", 0)
    harvest_msg = ""
    
    # 判斷是否為「大額價值物品」(例如黃金、鑽石、彩虹類)
    # 若價值超過 100 金幣，視為貴重品自動賣出；其餘存入背包作為消耗品
    is_valuable = any(k in clean_name for k in ["黃金", "鑽石", "彩虹", "傳說"])
    
    if is_valuable:
        coins += base_price
        harvest_msg = f"💰 **貴重物品自動賣出**：獲得了 `{base_price}` 金幣！"
    else:  # <--- 檢查這一行，前面必須是 4 的倍數個空格
        # 這裡也要縮進 8 個空格
        amount = random.randint(1, 3) 
        inventory[clean_name] = inventory.get(clean_name, 0) + amount
        harvest_msg = f"🎒 **成功收成**：獲得了 `{amount}` 根 **{clean_name}**，已存入背包！"

    # ------ 3. 手套額外金幣加成 (保留金幣加成作為額外津貼) ------
    bonus_coins = 0
    glove_text_list = []
    for glove in gloves:
        if glove == "幸運手套":
            bonus_coins += 5
            glove_text_list.append("🧤 幸運手套：額外貼補 +5 金幣")
        elif glove == "黃金手套":
            bonus_coins += 10
            glove_text_list.append("🧤 黃金手套：額外貼補 +10 金幣")

    coins += bonus_coins

    # ------ 4. 圖鑑與資料更新 ------
    new_discovery = False
    carrots_collection = user_data.setdefault("carrots", [])
    if raw_result not in carrots_collection:
        carrots_collection.append(raw_result)
        new_discovery = True

    # 更新狀態為 harvested 並清空土地
    user_data["coins"] = coins
    user_data["inventory"] = inventory
    user_data["farm"]["status"] = "harvested" # 或 "none" 視你的 main 邏輯而定
    user_data["farm"]["pull_count"] = user_data["farm"].get("pull_count", 0) + 1
    
    ref.update({
        "coins": coins,
        "inventory": inventory,
        "farm": user_data["farm"],
        "carrots": carrots_collection
    })

    # ------ 5. 建立嵌入訊息 ------
    color = get_carrot_rarity_color(raw_result)
    embed = discord.Embed(
        title="🌾 收成成功！",
        description=f"你成功收成了 **{raw_result}**\n\n{harvest_msg}",
        color=color
    )
    embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
    embed.set_thumbnail(url=get_carrot_thumbnail(raw_result))
    
    if bonus_coins > 0:
        embed.add_field(name="💰 額外收入", value=f"{bonus_coins} 金幣", inline=True)
    
    embed.add_field(name="🧪 使用肥料", value=fertilizer, inline=True)
    embed.add_field(name="🌾 土地等級", value=f"Lv.{land_level}", inline=True)

    if glove_text_list:
        embed.add_field(name="🧤 手套效果", value="\n".join(glove_text_list), inline=False)

    if new_discovery:
        embed.add_field(name="📖 新發現！", value="你的圖鑑新增了一種蘿蔔！", inline=False)

    embed.set_footer(text="📅 收成完成｜現在可以再次種植新蘿蔔 🌱")
    await current_channel.send(embed=embed)

# ===================== 1. 購買肥料 (修正版) =====================
async def handle_buy_fertilizer(message, user_id, user_data, ref, f_type):
    prices = {"普通肥料": 10, "高級肥料": 30, "神奇肥料": 100}
    if f_type not in prices:
        await message.channel.send("❓ 請輸入正確的肥料名稱：`普通肥料`、`高級肥料` 或 `神奇肥料`")
        return

    price = prices[f_type]
    coins = user_data.get("coins", 0)

    if coins < price:
        await message.channel.send(f"❌ 金幣不足！購買 {f_type} 需要 {price} 金幣。")
        return

    # 更新金幣與肥料數量
    user_data["coins"] -= price
    fertilizers = user_data.get("fertilizers", {"普通肥料": 0, "高級肥料": 0, "神奇肥料": 0})
    fertilizers[f_type] = fertilizers.get(f_type, 0) + 1

    ref.update({
        "coins": user_data["coins"],
        "fertilizers": fertilizers
    })

    await message.channel.send(f"✅ 購買成功！獲得了 1 個 {f_type} (剩餘金幣: {user_data['coins']})")


# ===== 升級土地 =====
async def handle_upgrade_land(message, user_id, user_data, ref):
    # --- ✅ 使用者資料防呆，防止型態錯誤導致崩潰 ---
    user_data = sanitize_user_data(user_data)
    
    farm = user_data.setdefault("farm", {})
    coins = user_data.get("coins", 0)
    level = farm.get("land_level", 1)

    if level >= 5:
        await message.channel.send("🏔️ 土地已達最高等級 Lv.5！")
        return

    cost = level * 100
    if coins < cost:
        await message.channel.send(f"💸 升級需要 {cost} 金幣，你目前只有 {coins} 金幣")
        return

    user_data["coins"] -= cost
    farm["land_level"] = level + 1
    ref.set(user_data)

    await message.channel.send(f"🛠️ 土地成功升級至 Lv.{level + 1}，花費 {cost} 金幣")

# ===== 土地進度查詢（新版 Embed） =====
async def handle_land_progress(message, user_id, user_data, ref):
    # --- ✅ 使用者資料防呆，防止型態錯誤導致崩潰 ---
    user_data = sanitize_user_data(user_data)
    
    farm = user_data.get("farm", {})
    land_level = farm.get("land_level", 1)
    pull_count = farm.get("pull_count", 0)

    upgrade_thresholds = {1: 10, 2: 30, 3: 60, 4: 100}
    next_level = land_level + 1

    if land_level >= 5:
        embed = discord.Embed(
            title="🏔️ 土地已達最高等級",
            description="你的土地已升級至 Lv.5，無需再升級！",
            color=discord.Color.gold()
        )
        embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
        await message.channel.send(embed=embed)
        return

    required = upgrade_thresholds.get(land_level, 999)
    remaining = required - pull_count
    progress_percent = min(int((pull_count / required) * 100), 100)

    # 等級效果說明
    effect_text = {
        2: "⏳ 收成時間 -2 小時",
        3: "🍀 稀有機率 +5%",
        4: "🎁 解鎖特殊蘿蔔池",
        5: "🌟 蘿蔔事件機率提升"
    }.get(next_level, "未知")

    embed = discord.Embed(
        title="📈 土地升級進度",
        color=discord.Color.green()
    )
    embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)

    embed.add_field(name="🏷️ 當前等級", value=f"Lv.{land_level}", inline=True)
    embed.add_field(name="🎯 下一等級", value=f"Lv.{next_level}", inline=True)
    embed.add_field(name="🥕 拔蘿蔔次數", value=f"{pull_count}/{required} 次", inline=False)
    embed.add_field(name="📊 進度條", value=f"[{'■' * (progress_percent // 10)}{'□' * (10 - progress_percent // 10)}] {progress_percent}%", inline=False)
    embed.add_field(name="🎁 升級後效果", value=effect_text, inline=False)
    embed.set_footer(text="繼續努力拔蘿蔔吧！每拔一次都能增加進度 🌱")

    await message.channel.send(embed=embed)

# ===== 農場總覽卡（多圖修正版）=====
async def show_farm_overview(bot, message, user_id, user_data, ref):
    import io 
    import discord
    import random
    from datetime import datetime
    from utils_sanitize import sanitize_user_data
    from utils import get_now, parse_datetime, get_remaining_time_str, get_decoration_thumbnail
    
    bot_client = bot
    user_data = sanitize_user_data(user_data)
    
    # 確保進入田地執行緒
    from carrot_commands import ensure_player_thread
    current_channel = await ensure_player_thread(message)
    if current_channel is None: return

    # --- 1. 讀取與處理資料 ---
    farm = user_data.get("farm", {})
    coins = user_data.get("coins", 0)
    fertilizers = user_data.get("fertilizers", {})
    gloves = user_data.get("gloves", [])
    # 🌟 這裡改成直接從 ref 抓最新的，避免傳入舊資料
    latest_db_data = ref.get() or {}
    decorations = latest_db_data.get("decorations", [])
    lucky_bags = user_data.get("lucky_bag", 0)
    daily_pulls = user_data.get("daily_pulls", 0)
    
    GLOVE_DESC = {
        "農夫手套": "收成金幣 +20%",
        "強化手套": "種植時間 -1 小時",
        "神奇手套": "稀有機率提升",
        "幸運手套": "大吉時掉出蘿蔔"
    }

    land_level = farm.get("land_level", 1)
    status = farm.get("status", "未種植")
    status_map = {"planted": "🌱 已種植，請等待收成", "harvested": "🥕 已收成，等待拔出"}
    status_text = status_map.get(status, "🌾 未種植")

    time_info = "尚未種植"
    if status == "planted" and "harvest_time" in farm:
        try:
            h_time = parse_datetime(farm["harvest_time"])
            now = get_now()
            time_str = h_time.strftime("%Y/%m/%d %H:%M")
            if h_time > now:
                remaining = get_remaining_time_str(h_time)
                time_info = f"{time_str}（還剩 {remaining}）"
            else:
                time_info = f"{time_str}（**已可收成！**）"
        except:
            time_info = "時間資料錯誤"

    # --- 2. 建立 Embed 內容 ---
    embed = discord.Embed(
        title="🌾 農場總覽卡",
        description=f"👤 玩家：**{message.author.display_name}**",
        color=discord.Color.green()
    )

    embed.add_field(name="🏷️ 土地狀態", value=f"Lv.{land_level} 的土地目前 {status_text}", inline=False)
    embed.add_field(name="🧪 使用肥料", value=farm.get("fertilizer", "未使用"), inline=True)
    embed.add_field(name="⏱️ 收成時間", value=time_info, inline=True)
    embed.add_field(name="💰 金幣餘額", value=f"{coins} 金幣", inline=True)
    embed.add_field(name="🧧 今日剩餘拔蘿蔔次數", value=f"{5 - daily_pulls} 次", inline=True)
    embed.add_field(name="────────────────────", value="**📦 農場資源狀況**", inline=False)

    f_items = [f"• {k}：{v} 個" for k, v in fertilizers.items() if v > 0]
    embed.add_field(name="🧪 肥料庫存", value="\n".join(f_items) if f_items else "• 暫無肥料", inline=True)
    
    g_items = [f"• {g} — {GLOVE_DESC.get(g, '基本款')}" for g in (gloves if isinstance(gloves, list) else [])]
    embed.add_field(name="🧤 擁有手套", value="\n".join(g_items) if g_items else "• 暫無手套", inline=False)

    d_items = [f"• {d}" for d in (decorations if isinstance(decorations, list) else [])]
    embed.add_field(name="🎍 農場裝飾", value="\n".join(d_items) if d_items else "• 暫無裝飾", inline=True)
    
    lb_text = f"{lucky_bags} 個" if lucky_bags > 0 else "尚未擁有"
    embed.add_field(name="🧧 開運福袋", value=lb_text, inline=True)
    embed.set_footer(text="📅 每日凌晨重置拔蘿蔔次數與運勢 🌙")

    # 發送 Embed
    await current_channel.send(embed=embed)

# --- 3. 處理所有裝飾圖片實況 (診斷強化版) ---
    if decorations and bot_client:
        files = []
        import aiohttp
        async with aiohttp.ClientSession() as session:
            # 確保清單格式正確
            deco_list = list(decorations) if isinstance(decorations, (list, dict)) else []
            if isinstance(decorations, dict):
                deco_list = list(decorations.values())

            print(f"🔍 [STEP 1] 開始處理清單: {deco_list}")

            for index, d in enumerate(deco_list):
                # 🌟 這裡增加 URL 檢查
                url = get_decoration_thumbnail(d)
                print(f"🔍 [STEP 2] 裝飾品: {d}, 取得的 URL: {url}")
                
                if not url or not url.startswith("http"):
                    print(f"❌ [STEP 3] {d} 的 URL 無效，跳過。")
                    continue
                
                try:
                    async with session.get(url, timeout=10) as resp:
                        if resp.status == 200:
                            img_data = await resp.read()
                            filename = f"deco_{index}_{random.randint(1000,9999)}.png"
                            files.append(discord.File(fp=io.BytesIO(img_data), filename=filename))
                            print(f"✅ [STEP 4] 成功下載圖片: {d}")
                        else:
                            print(f"❌ [STEP 4] 下載 {d} 失敗，HTTP 狀態碼: {resp.status}")
                except Exception as e:
                    print(f"💥 [ERROR] 下載 {d} 時發生崩潰: {str(e)}")

        if files:
            print(f"📦 [FINISH] 準備發送 {len(files)} 張圖片到 Discord")
            await current_channel.send(content="🎍 **農場裝飾實況：**", files=files)

# ===== 賣出蘿蔔 =====

async def handle_sell_carrot(message, user_id, user_data, ref, args):
    """
    處理賣出蘿蔔的功能：根據稀有度定價
    用法：!賣出 普通蘿蔔 5
    """
    if not args:
        await message.channel.send("❓ 請輸入要賣出的蘿蔔名稱。例如：`!賣出 普通蘿蔔` 或 `!賣出 普通蘿蔔 5`")
        return

    # 解析參數
    item_name = args[0]
    try:
        amount_to_sell = int(args[1]) if len(args) > 1 else 1
    except ValueError:
        await message.channel.send("❌ 數量請輸入數字喔！")
        return

    if amount_to_sell <= 0:
        await message.channel.send("❌ 數量必須大於 0！")
        return

    inventory = user_data.get("inventory", {})
    
    # 檢查背包是否有該物品
    if item_name not in inventory or inventory[item_name] < amount_to_sell:
        await message.channel.send(f"❌ 你的背包裡沒有足夠的 **{item_name}** 喔！")
        return

    # --- 💰 稀有度定價表 ---
    # 【等級 1：普通型】(5~8 金幣)
    common_price = {
        "普通蘿蔔": 5,
        "愛跳舞的蘿蔔": 6,
        "愛裝年輕的蘿蔔": 6,
        "胖胖蘿蔔": 7,
        "長腿蘿蔔": 7
    }
    
    # 【等級 2：稀有型】(15~25 金幣)
    rare_price = {
        "老爺爺蘿蔔": 15,
        "忍者蘿蔔": 18,
        "發光蘿蔔": 20,
        "冰晶蘿蔔": 25,
        "黃金蘿蔔": 30
    }
    
    # 【等級 3：傳說型】(50+ 金幣)
    legend_price = {
        "彩虹蘿蔔": 50,
        "惡魔蘿蔔": 66,
        "天使蘿蔔": 88,
        "宇宙傳說蘿蔔": 100
    }

    # 判定價格 (優先找各表，都沒有則預設 5)
    if item_name in legend_price:
        price_per_unit = legend_price[item_name]
        rarity_tag = "【✨ 傳說】"
    elif item_name in rare_price:
        price_per_unit = rare_price[item_name]
        rarity_tag = "【⭐ 稀有】"
    else:
        price_per_unit = common_price.get(item_name, 5)
        rarity_tag = "【🍀 普通】"

    total_earned = price_per_unit * amount_to_sell

    # 更新資料庫數據
    inventory[item_name] -= amount_to_sell
    if inventory[item_name] <= 0:
        del inventory[item_name]
        
    current_coins = user_data.get("coins", 0)
    new_coins = current_coins + total_earned

    # 回寫 Firebase
    ref.update({
        "inventory": inventory,
        "coins": new_coins
    })

    # 顯示漂亮的成交訊息
    embed = discord.Embed(title="💰 交易成功", color=discord.Color.green())
    embed.description = (
        f"賣出了 {rarity_tag} **{item_name}** x{amount_to_sell}\n"
        f"獲得金幣：`{total_earned}` 💰\n"
        f"目前持有的金幣：`{new_coins}` 💰"
    )
    await message.channel.send(embed=embed)
    
# ===== 健康檢查 =====
async def handle_health_check(message):
    # --- ✅ 使用者資料防呆，防止型態錯誤導致崩潰 ---
    user_data = sanitize_user_data(user_data)
    
    from utils import get_today, get_fortune_thumbnail, get_carrot_thumbnail, get_carrot_rarity_color
    today = get_today()
    is_admin = message.author.guild_permissions.administrator
    if not is_admin:
        await message.channel.send("🚫 此指令僅限管理員使用。")
        return

    checks = {
        "📦 fortunes 是否載入": {
            "ok": "fortunes" in globals(),
            "fix": "請確認你有 from fortune_data import fortunes"
        },
        "🧠 get_fortune_thumbnail 是否可用": {
            "ok": callable(get_fortune_thumbnail),
            "fix": "請確認 utils.py 有定義該函式，並已匯入"
        },
        "🥕 get_carrot_thumbnail 是否可用": {
            "ok": callable(get_carrot_thumbnail),
            "fix": "請確認 utils.py 有定義該函式，並已匯入"
        },
        "🎨 get_carrot_rarity_color 是否可用": {
            "ok": callable(get_carrot_rarity_color),
            "fix": "請確認 utils.py 有定義該函式，並已匯入"
        },
        "📚 蘿蔔資料是否載入": {
            "ok": "common_carrots" in globals(),
            "fix": "請確認你有 from carrot_data import common_carrots 等"
        }
    }

    embed = discord.Embed(
        title="🩺 系統健康檢查",
        description="以下是目前功能掛載狀態：",
        color=discord.Color.green() if all(c["ok"] for c in checks.values()) else discord.Color.red()
    )
    embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
    embed.set_footer(text=f"📅 {today}｜🔁 每次重啟後可重新檢查")

    for name, result in checks.items():
        status = "✅ 正常" if result["ok"] else f"❌ 錯誤\n🛠 {result['fix']}"
        embed.add_field(name=name, value=status, inline=False)

    await message.channel.send(embed=embed)

# 🧤 手套商店資料
GLOVE_SHOP = {
    "幸運手套": {"price": 100, "desc": "抽到大吉時額外掉出一根蘿蔔"},
    "農夫手套": {"price": 150, "desc": "收成時金幣 +20%"},
    "強化手套": {"price": 200, "desc": "種植時間 -1 小時"},
    "神奇手套": {"price": 500, "desc": "收成時有機率獲得稀有蘿蔔"}
}

# 🎍 裝飾商店資料
DECORATION_SHOP = {
    "花圃": 80,
    "木柵欄": 100,
    "竹燈籠": 150,
    "鯉魚旗": 200,
    "聖誕樹": 250
}

# 🧤 購買手套
async def handle_buy_glove(bot, message, user_id, user_data, ref, glove_name, show_farm_callback):
    if glove_name not in GLOVE_SHOP:
        await message.channel.send("❌ 沒有這種手套！可購買：" + "、".join(GLOVE_SHOP.keys()))
        return

    cost = GLOVE_SHOP[glove_name]["price"]
    coins = user_data.get("coins", 0)
    if coins < cost:
        await message.channel.send(f"💸 金幣不足！需要 {cost} 金幣，你目前只有 {coins}")
        return

    # ---------------------------------------
    # 🧤 方案 A：強制統一為 list 型態
    # ---------------------------------------
    gloves = user_data.get("gloves", [])

    # 若以前寫入錯誤 → 自動修正
    if isinstance(gloves, str):  
        gloves = [gloves]
    elif not isinstance(gloves, list):
        gloves = []

    user_data["gloves"] = gloves  # 強制寫回標準格式

    # 扣錢
    user_data["coins"] -= cost

    # 加入手套，避免重複
    if glove_name not in gloves:
        gloves.append(glove_name)

    # 寫回資料庫
    ref.set(user_data)

    # 顯示購買成功訊息
    await message.channel.send(
        f"🧤 你購買了 **{glove_name}**！\n"
        f"📈 效果：{GLOVE_SHOP[glove_name]['desc']}"
    )
    
    # 更新並顯示農場總覽卡
    await show_farm_callback(bot, message, user_id, updated_data, ref)

# 🎍 購買裝飾（購買後自動顯示農場總覽）
# 🌟 修正點 1：參數補上 ref，並統一使用 decoration_name
async def handle_buy_decoration(bot, message, user_id, user_data, ref, decoration_name):
    import discord
    from utils_sanitize import sanitize_user_data
    from utils import get_decoration_thumbnail
    
    user_data = sanitize_user_data(user_data)

    shop = {
        "花圃": 80,
        "木柵欄": 100,
        "竹燈籠": 150,
        "鯉魚旗": 200,
        "聖誕樹": 250
    }

    # 🌟 修正點 2：將 deco_name 全部統一為 decoration_name
    if decoration_name not in shop:
        await message.channel.send(
            f"❌ 沒有「{decoration_name}」這種裝飾！\n可購買：花圃、木柵欄、竹燈籠、鯉魚旗、聖誕樹"
        )
        return

    cost = shop[decoration_name]
    coins = user_data.get("coins", 0)

    if coins < cost:
        await message.channel.send(
            f"💸 金幣不足！\n{decoration_name} 價格 **{cost}** 金幣，你目前只有 **{coins}**"
        )
        return

    # 取得現有裝飾清單
    user_decorations = user_data.get("decorations", [])
    if not isinstance(user_decorations, list):
        user_decorations = []

    # 防止重複購買
    if decoration_name in user_decorations:
        await message.channel.send(f"⚠️ 你已經擁有 **{decoration_name}** 了！")
        return

    # 🌟 執行購買扣款
    new_coins = coins - cost
    user_decorations.append(decoration_name)
    
    # 更新本地資料與資料庫
    user_data["coins"] = new_coins
    user_data["decorations"] = user_decorations
    ref.set(user_data)

    # --- 🎨 購買成功 Embed --- 
    embed = discord.Embed(
        title="🎍 裝飾購買成功！",
        description=f"你購入了 **{decoration_name}**！農場變得更漂亮了 🌾",
        color=discord.Color.green()
    )
    
    # 顯示裝飾圖片 
    embed.set_thumbnail(url=get_decoration_thumbnail(decoration_name))    

    embed.add_field(
        name="💰 剩餘金幣",
        value=f"{new_coins} 金幣",
        inline=False
    )

    await message.channel.send(embed=embed) 

    # --- 🌾 顯示農場總覽 ---
    # 🌟 修正點 3：呼叫總覽時帶上 bot，確保圖片能顯示
    updated_data = ref.get()
    await show_farm_overview(bot, message, user_id, updated_data, ref)


# 🧧 開運福袋（含特效與農場總覽）
async def handle_open_lucky_bag(bot, message, user_id, user_data, ref):
    # --- ✅ 使用者資料防呆，防止型態錯誤導致崩潰 ---
    user_data = sanitize_user_data(user_data)
    
    cost = 80
    coins = user_data.get("coins", 0)
    if coins < cost:
        await message.channel.send(f"💸 金幣不足！開運福袋需要 {cost} 金幣，你目前只有 {coins}")
        return

    user_data["coins"] -= cost
    reward_type = random.choice(["coins", "fertilizer", "decoration"])
    msg = ""
    effect = ""
    color = discord.Color.orange()

    if reward_type == "coins":
        reward = random.randint(20, 120)
        user_data["coins"] += reward
        msg = f"💰 你獲得了 {reward} 金幣！"
        if reward >= 100:
            effect = "✨ 超大筆金幣入袋！"
            color = discord.Color.gold()
    elif reward_type == "fertilizer":
        fertilizer_type = random.choice(["普通肥料", "高級肥料", "神奇肥料"])
        user_data.setdefault("fertilizers", {})
        user_data["fertilizers"][fertilizer_type] = user_data["fertilizers"].get(fertilizer_type, 0) + 1
        msg = f"🧪 你獲得了 1 個 {fertilizer_type}！"
        if fertilizer_type == "神奇肥料":
            effect = "🌟 神奇肥料降臨！收成機率大提升！"
            color = discord.Color.purple()
        elif fertilizer_type == "高級肥料":
            effect = "🔸 高級肥料入手，收成時間縮短！"
            color = discord.Color.blue()
    else:
        decorations = ["花圃", "木柵欄", "竹燈籠", "鯉魚旗", "聖誕樹"]
        deco = random.choice(decorations)
        user_data.setdefault("decorations", [])
        if deco not in user_data["decorations"]:
            user_data["decorations"].append(deco)
            msg = f"🎍 你獲得了新的裝飾 **{deco}**！"
            if deco == "聖誕樹":
                effect = "🎄 節慶奇蹟！聖誕樹閃耀登場！"
                color = discord.Color.green()
        else:
            user_data["coins"] += 50
            msg = f"🎁 抽到重複裝飾，轉換為 50 金幣 💰"

    ref.set(user_data)

    embed = discord.Embed(
        title="🧧 開運福袋結果",
        description=msg,
        color=color
    )
    embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
    if effect:
        embed.add_field(name="🎉 特殊效果", value=effect, inline=False)
    embed.set_footer(text="📦 福袋獎勵已加入農場資源")

    await message.channel.send(embed=embed)

    # ✅ 顯示最新農場總覽卡
    updated_data = ref.get()
    await show_farm_overview(bot, message, user_id, updated_data, ref)
    
# 🏪 商店總覽
async def handle_shop(message, user_id, user_data, ref):
    user_data = sanitize_user_data(user_data)
    
    text = (
        "🏪 **農場商店**\n\n"
        "🧤 手套：\n"
        "  • 幸運手套 — 100 金幣（大吉時額外掉出一根蘿蔔）\n"
        "  • 農夫手套 — 150 金幣（收成金幣 +20%）\n"
        "  • 強化手套 — 200 金幣（種植時間 -1 小時）\n"
        "  • 神奇手套 — 500 金幣（稀有蘿蔔機率上升）\n\n"
        "🎍 裝飾：\n"
        "  • 花圃（80）• 木柵欄（100）• 竹燈籠（150）• 鯉魚旗（200）• 聖誕樹（250）\n\n"
        "🧧 其他：\n"
        "  • 開運福袋 — 80 金幣（隨機獎勵）\n\n"
        "📜 使用方式：\n"
        "`!購買手套 幸運手套`\n"
        "`!購買裝飾 花圃`\n"
        "`!開福袋`"
    )
    await message.channel.send(text)



    # ===== 給金幣 =====

def ref_lookup(user_id):
    return db.reference(f"/users/{user_id}")

def log_ref():
    return db.reference("/logs/coin_give")

async def handle_give_coins(message, user_id, user_data, ref, args):
    if not message.author.guild_permissions.administrator:
        await message.channel.send("🚫 此指令僅限管理員使用。")
        return

    giver_id = str(message.author.id)
    giver_name = message.author.display_name
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 給自己
    if len(args) == 1:
        try:
            amount = int(args[0])
        except ValueError:
            await message.channel.send("❌ 金幣數量必須是整數。")
            return

        ref = ref_lookup(giver_id)
        user_data = ref.get()
        user_data["coins"] = user_data.get("coins", 0) + amount
        ref.set(user_data)

        log_ref().push({
            "giver_id": giver_id,
            "giver_name": giver_name,
            "target_id": giver_id,
            "target_name": giver_name,
            "amount": amount,
            "timestamp": timestamp,
            "type": "self"
        })

        await message.channel.send(f"💰 已成功給予你 {amount} 金幣！目前餘額：{user_data['coins']} 金幣")
        return

    # 給其他人
    elif len(args) == 2:
        mention = args[0]
        try:
            amount = int(args[1])
        except ValueError:
            await message.channel.send("❌ 金幣數量必須是整數。")
            return

        if not mention.startswith("<@") or not mention.endswith(">"):
            await message.channel.send("❌ 請使用 @玩家 來指定對象。")
            return

        target_id = mention.replace("<@", "").replace("!", "").replace(">", "")
        ref = ref_lookup(target_id)
        user_data = ref.get()
        user_data["coins"] = user_data.get("coins", 0) + amount
        ref.set(user_data)

        log_ref().push({
            "giver_id": giver_id,
            "giver_name": giver_name,
            "target_id": target_id,
            "target_name": f"<@{target_id}>",
            "amount": amount,
            "timestamp": timestamp,
            "type": "admin"
        })

        await message.channel.send(f"💰 已成功給予 <@{target_id}> {amount} 金幣！目前餘額：{user_data['coins']} 金幣")
        return

    else:
        await message.channel.send("❌ 指令格式錯誤。請使用：`!給金幣 數量` 或 `!給金幣 @玩家 數量`")

# 🧤 手套圖鑑
async def handle_glove_encyclopedia(message):
    # --- ✅ 使用者資料防呆，防止型態錯誤導致崩潰 ---
    user_data = sanitize_user_data(user_data)
    
    gloves = {
        "幸運手套": "大吉時可多拔一根蘿蔔。",
        "農夫手套": "收成金幣 +20%。",
        "強化手套": "種植時間縮短 1 小時。",
        "神奇手套": "提升稀有蘿蔔機率。",
    }

    embed = discord.Embed(
        title="🧤 手套圖鑑",
        description="這裡列出所有可收集的手套與其效果：",
        color=discord.Color.orange()
    )

    for name, desc in gloves.items():
        embed.add_field(name=name, value=desc, inline=False)

    await message.channel.send(embed=embed)

    # ===== 蘿蔔系統說明 =====

async def handle_carrot_info(message, user_id, user_data, ref):
    # --- ✅ 使用者資料防呆，防止型態錯誤導致崩潰 ---
    user_data = sanitize_user_data(user_data)
    
    embed = discord.Embed(
        title="🥕 蘿蔔系統說明",
        description="探索蘿蔔世界的各種機制與驚喜！",
        color=discord.Color.orange()
    )
    embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)

    embed.add_field(
        name="🔁 每日拔蘿蔔次數",
        value="每天最多拔 3 次蘿蔔，午夜過後重置次數。使用 !拔蘿蔔 進行抽卡。",
        inline=False
    )

    embed.add_field(
        name="🎯 特殊蘿蔔池",
        value=(
            "特殊蘿蔔池是一種稀有抽卡機制，抽出稀有蘿蔔的機率大幅提升！\n"
            "✅ 觸發條件：\n"
            "• 使用「神奇手套」時有 20% 機率進入\n"
            "• 土地等級達 Lv.4 以上時有機率進入\n"
            "• 特殊活動期間（如節慶）強制啟用\n"
            "🎁 特殊池中可能抽到：彩虹蘿蔔、黃金蘿蔔、幸運蘿蔔等稀有品種"
        ),
        inline=False
    )

    embed.add_field(
        name="🌟 蘿蔔事件",
        value=(
            "土地等級達 Lv.5 後，每次拔蘿蔔有機率觸發特殊事件。\n"
            "目前已知事件包括：\n"
            "• 🎁 神秘訪客：贈送金幣與肥料\n"
            "• 🐰 蘿蔔大逃亡：蘿蔔逃走，需花金幣追回\n"
            "• 💥 蘿蔔爆彈：肥料被炸光\n"
            "• 🐦 鳥群來襲：收成延後\n"
            "• 🔮 蘿蔔占卜師：預言下一次抽卡結果\n"
            "• 🪙 金幣雨：拔出稀有蘿蔔時獲得額外金幣\n"
            "• 🧊 冰封蘿蔔：冬季限定，品質提升但收成延後"
        ),
        inline=False
    )

    embed.add_field(
        name="📈 土地等級影響",
        value=(
            "土地可升級至 Lv.5，等級越高影響越大：\n"
            "• Lv.2：收成時間 -2 小時\n"
            "• Lv.3：拔出稀有蘿蔔機率 +5%\n"
            "• Lv.4：解鎖特殊蘿蔔池\n"
            "• Lv.5：蘿蔔事件機率提升"
        ),
        inline=False
    )

    embed.add_field(
        name="📖 圖鑑與收藏",
        value="每種蘿蔔只會收藏一次，抽到新蘿蔔會自動加入圖鑑。使用 !蘿蔔圖鑑 查看收藏進度。",
        inline=False
    )

    embed.set_footer(text="🌱 使用 !土地進度 查看升級進度｜📘 使用 !拔蘿蔔 開始抽卡")
    await message.channel.send(embed=embed)


# ===== 特殊蘿蔔池一覽（含機率） =====

async def handle_special_carrots(message, user_id, user_data, ref):
    user_data = sanitize_user_data(user_data)

    # 蘿蔔列表與機率（可隨時調整）
    special_carrots = [
        {"name": "🌈 彩虹蘿蔔", "rarity": "極稀有", "effect": "色彩繽紛的傳說級蘿蔔，收藏價值極高。", "chance": "1%"},
        {"name": "🥇 黃金蘿蔔", "rarity": "稀有", "effect": "閃閃發亮的金色蘿蔔，象徵財富與幸運。", "chance": "5%"},
        {"name": "🍀 幸運蘿蔔", "rarity": "稀有", "effect": "拔出後當日金幣獲得量 +20%。", "chance": "10%"},
        {"name": "🧊 冰晶蘿蔔", "rarity": "季節限定", "effect": "冬季限定出現，外觀晶瑩剔透。", "chance": "3%"},
    ]

    embed = discord.Embed(
        title=f"🎯 {message.author.display_name} 的特殊蘿蔔池一覽",
        description=f"以下是目前可從特殊蘿蔔池中抽出的稀有蘿蔔與其特色及出現機率：",
        color=discord.Color.purple()
    )
    embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)

    for carrot in special_carrots:
        embed.add_field(
            name=f"{carrot['name']} ({carrot['rarity']})",
            value=f"{carrot['effect']}\n🎲 機率：{carrot['chance']}",
            inline=False
        )

    embed.add_field(
        name="🎯 如何進入特殊蘿蔔池？",
        value=(
            "• 使用「神奇手套」時有 20% 機率進入\n"
            "• 土地等級達 Lv.4 以上時有機率進入\n"
            "• 特殊活動期間（如節慶）強制啟用\n"
            "• 進入後會顯示「🎯 特殊蘿蔔池」提示"
        ),
        inline=False
    )

    embed.set_footer(text="📘 使用 !拔蘿蔔 開始抽卡｜📖 使用 !蘿蔔圖鑑 查看收藏進度")
    await message.channel.send(embed=embed)
    
async def handle_eat_carrot(message, user_id, user_data, ref, item_name):
    """處理吃蘿蔔邏輯：支援模糊匹配，不輸入 Emoji 也能吃"""
    if not item_name:
        await message.channel.send("❓ 你想吃什麼？請輸入名稱，例如：`!吃 搞笑蘿蔔` 或 `!吃 搞笑蘿蔔 🤡`")
        return

    inventory = user_data.get("inventory", {})
    
    # 🌟 核心：搜尋匹配的物品名稱 (包含模糊搜尋)
    target_key = None
    
    # 1. 先試試看完全匹配 (包含玩家手打 Emoji 的情況)
    if item_name in inventory:
        target_key = item_name
    else:
        # 2. 模糊匹配：檢查輸入的文字是否在背包項目的名稱裡
        for key in inventory.keys():
            if item_name in key:
                target_key = key
                break

    # 檢查是否找到物品
    if not target_key or inventory[target_key] <= 0:
        await message.channel.send(f"❌ 你的背包裡沒有「{item_name}」喔！")
        return

    # 3. 定義效果 (使用 target_key 來判定，確保包含 Emoji 也能判斷關鍵字)
    hp_gain = 20      # 基礎補血量
    active_buff = None
    effect_desc = "這是一根普通的蘿蔔，咬起來脆脆的。"

    # 🌟 關鍵字判定系統
    if any(k in target_key for k in ["金", "幸運", "鑽石", "錢"]):
        hp_gain = 50
        active_buff = "double_gold"
        effect_desc = "這味道...是金錢的氣息！下一場冒險金幣收益翻倍！"
    
    elif any(k in target_key for k in ["彩虹", "王者", "神", "星辰", "宇宙", "傳說"]):
        hp_gain = 100
        active_buff = "invincible"
        effect_desc = "強大的能量湧入全身！下一場冒險你將進入【無敵】狀態！"
        
    elif any(k in target_key for k in ["冰", "雪", "冷", "海洋", "泡泡", "霜"]):
        hp_gain = 40
        active_buff = "heat_resist"
        effect_desc = "全身感到透心涼！獲得【耐熱】效果，無視沙漠扣血。"

    elif any(k in target_key for k in ["壞掉", "發霉", "乾掉", "枯萎"]):
        hp_gain = 5
        effect_desc = "嘔...味道不太對勁，勉強恢復了一點體力。"

    # 4. 計算並更新資料
    current_hp = user_data.get("hp", 100)
    level = user_data.get("level", 1)
    max_hp = 100 + (level * 10)
    new_hp = min(max_hp, current_hp + hp_gain)

    # 扣除物資 (使用找到的 target_key)
    inventory[target_key] -= 1
    if inventory[target_key] <= 0:
        del inventory[target_key]

    # 更新到資料庫
    update_payload = {
        "inventory": inventory,
        "hp": new_hp,
        "active_buff": active_buff
    }
    ref.update(update_payload)

    # 5. 回傳訊息 (Embed 顯示完整的 target_key 名稱)
    embed = discord.Embed(
        title="🍴 享用蘿蔔",
        description=f"你吃掉了 **{target_key}**",
        color=discord.Color.green()
    )
    embed.add_field(name="❤️ 體力恢復", value=f"{int(current_hp)} ➔ **{int(new_hp)}**", inline=True)
    if active_buff:
        embed.add_field(name="✨ 獲得狀態", value=f"`{active_buff}`", inline=True)
    embed.set_footer(text=effect_desc)
    
    await message.channel.send(embed=embed)

# ===== 冒險商店 =====

ADVENTURE_ITEMS = {
    "體力藥水": {"price": 30, "hp": 50, "desc": "立即回復 50 點 HP"},
    "抗熱噴霧": {"price": 50, "buff": "heat_resist", "desc": "獲得下一場【耐熱】效果"},
    "守護卷軸": {"price": 80, "buff": "invincible", "desc": "獲得下一場【無敵】狀態"},
    "幸運餅乾": {"price": 100, "buff": "double_gold", "desc": "獲得下一場【金幣翻倍】"}
}

async def handle_adventure_shop(message, user_data):
    """顯示冒險商店選單"""
    coins = user_data.get("coins", 0)
    embed = discord.Embed(
        title="🛒 冒險者補給站", 
        description="買點東西再出發吧！\n使用指令：`!購買 [商品名稱]`\n*(注意：Buff 類商品僅能維持下一場冒險)*", 
        color=discord.Color.green()
    )
    
    for name, info in ADVENTURE_ITEMS.items():
        embed.add_field(name=f"{name} (`{info['price']}` 💰)", value=info['desc'], inline=True)
        
    embed.set_footer(text=f"💰 您目前持有：{coins} 金幣")
    await message.channel.send(embed=embed)

async def handle_buy_item(message, user_id, user_data, ref, item_name):
    """處理購買邏輯"""
    if not item_name:
        await message.channel.send("❓ 請輸入要購買的商品名稱，例如：`!購買 體力藥水`")
        return

    if item_name not in ADVENTURE_ITEMS:
        await message.channel.send(f"❌ 商店沒有賣「{item_name}」喔！請檢查名稱是否正確。")
        return

    item = ADVENTURE_ITEMS[item_name]
    current_coins = user_data.get("coins", 0)

    if current_coins < item["price"]:
        await message.channel.send(f"❌ 金幣不足！你還差 `{item['price'] - current_coins}` 💰")
        return

    # 準備更新資料
    new_coins = current_coins - item["price"]
    update_data = {"coins": new_coins}

    # 處理立即生效 (HP) 或 Buff
    response_msg = ""
    if "hp" in item:
        max_hp = 100 + (user_data.get("level", 1) * 10)
        old_hp = user_data.get("hp", 100)
        new_hp = min(max_hp, old_hp + item["hp"])
        update_data["hp"] = new_hp
        response_msg = f"✅ 購買成功！喝下{item_name}，HP 回復至 `{int(new_hp)}`。"
    else:
        update_data["active_buff"] = item["buff"]
        response_msg = f"✅ 購買成功！獲得 **{item_name}** 效果，將於下一場冒險自動生效。"

    ref.update(update_data)
    await message.channel.send(f"{message.author.mention} {response_msg}\n💰 剩餘金幣：`{new_coins}`")

async def handle_bag(message, user_id, user_data):
    """
    顯示 2.0 版完整背包：包含血量條、紅綠方塊冒險次數、金幣與物資清單
    """
    username = message.author.display_name
    coins = user_data.get("coins", 0)
    inventory = user_data.get("inventory", {})
    
    # --- 冒險與血量狀態 ---
    level = user_data.get("level", 1)
    max_hp = 100 + (level - 1) * 10
    hp = user_data.get("hp", max_hp)
    
    # 製作血量條 (10格)
    bar_length = 10
    filled_blocks = max(0, min(bar_length, int((hp / max_hp) * bar_length)))
    hp_bar = "❤️" * filled_blocks + "🤍" * (bar_length - filled_blocks)
    
    # --- 冒險次數 (紅綠方塊) ---
    adv_data = user_data.get("adventure", {})
    adv_count = adv_data.get("count", 0)  # 已使用的次數
    max_adv = 5
    
    # 已過變紅 (adv_count)，剩下為綠 (max_adv - adv_count)
    adv_icons = "🟥" * adv_count + "🟩" * (max_adv - adv_count)

    embed = discord.Embed(
        title=f"🎒 {username} 的背包",
        color=discord.Color.blue()
    )

    # --- 📊 目前狀態 ---
    status_value = (
        f"💰 持有的金幣: `{coins}`\n"
        f"❤️ 生命值: `{hp} / {max_hp}`\n"
        f"{hp_bar}\n"
        f"✨ 生效中狀態: `無`"
    )
    embed.add_field(name="📊 目前狀態", value=status_value, inline=False)

    # --- ⚔️ 今日冒險次數 ---
    # 顯示格式：(已用/總共) 紅紅綠綠綠
    embed.add_field(name="⚔️ 今日冒險次數", value=f"({adv_count}/{max_adv})\n{adv_icons}", inline=False)

    # --- 🎒 儲藏物資 ---
    if not inventory:
        inv_text = "目前儲藏室空空如也..."
    else:
        # 過濾數量大於 0 的物品，並排序
        items = [f"• {name}: `{count}` 個" for name, count in inventory.items() if count > 0]
        inv_text = "\n".join(items) if items else "目前儲藏室空空如也..."
    
    embed.add_field(name="📦 儲藏物資", value=inv_text, inline=False)

    embed.set_footer(text="💡 使用 !吃 [蘿蔔名稱] 來回復體力\n💡 購買商店 Buff 後會直接顯示在狀態欄中")
    
    await message.channel.send(embed=embed)
