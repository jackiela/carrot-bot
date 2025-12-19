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
                embed.set_footer(text=f"上次版本: {last_version or 'N/A'}")
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
    

# ===== 拔蘿蔔 =====
async def handle_pull_carrot(message, user_id, username, user_data, ref):
    # --- ✅ 使用者資料防呆，防止型態錯誤導致崩潰 ---
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

    # ===== 特殊蘿蔔池判定 =====
    gloves = user_data.get("gloves", [])

    # 🩹 安全保護：確保 gloves 一定是 list
    if isinstance(gloves, int):
        gloves = []  # 兼容舊資料結構（有些帳號手套是數字）
    elif isinstance(gloves, str):
        gloves = [gloves]

    land_level = user_data.get("farm", {}).get("land_level", 1)
    pool_type = "normal"

    # 🎯 特殊池機率（含神奇手套特效）
    if "神奇手套" in gloves and random.random() < 0.2:
        pool_type = "special"
    elif land_level >= 4 and random.random() < 0.1:
        pool_type = "special"

    # ===== 抽卡邏輯 =====
    if pool_type == "special":
        result = random.choices(
            ["彩虹蘿蔔", "黃金蘿蔔", "幸運蘿蔔", "冰晶蘿蔔"],
            weights=[0.4, 0.3, 0.2, 0.1]
        )[0]
    else:
        result = pull_carrot()

    # ===== 更新資料 =====
    user_data.setdefault("carrots", [])
    is_new = result not in user_data["carrots"]
    if is_new:
        user_data["carrots"].append(result)

    user_data.setdefault("carrot_pulls", {})
    user_data["carrot_pulls"][today] = today_pulls + 1
    user_data["carrot_pulls"]["last_pool"] = pool_type

    remaining = 2 - today_pulls

    # ===== 蘿蔔事件觸發 =====
    triggered_event = None
    event_roll = random.random()
    now = datetime.now()

    if land_level >= 5 and event_roll < 0.1:
        triggered_event = random.choice([
            "神秘訪客", "蘿蔔大逃亡", "蘿蔔爆彈", "鳥群來襲",
            "蘿蔔占卜師", "蘿蔔金幣雨", "冰封蘿蔔"
        ])

        # 各事件效果 ============================
        if triggered_event == "神秘訪客":
            bonus = random.choice(["普通肥料", "高級肥料", "裝飾"])
            user_data["coins"] = user_data.get("coins", 0) + 20
            await message.channel.send(f"🎁 神秘訪客出現！你獲得了 20 金幣與一份 {bonus}！")

        elif triggered_event == "蘿蔔大逃亡":
            user_data["coins"] = max(user_data.get("coins", 0) - 10, 0)
            await message.channel.send("🐰 蘿蔔大逃亡！你花了 10 金幣追回它。")

        elif triggered_event == "蘿蔔爆彈":
            ferts = user_data.get("fertilizers", {})
            if ferts:
                unlucky = random.choice(list(ferts.keys()))
                ferts[unlucky] = 0
                await message.channel.send(f"💥 蘿蔔爆彈引爆！你的「{unlucky}」肥料被炸光了！")

        elif triggered_event == "鳥群來襲":
            farm = user_data.get("farm", {})
            if farm.get("status") == "planted":
                old_time = datetime.fromisoformat(farm["harvest_time"])
                farm["harvest_time"] = (old_time + timedelta(hours=2)).isoformat()
                await message.channel.send("🐦 鳥群來襲！你的蘿蔔收成時間延後了 2 小時。")

        elif triggered_event == "蘿蔔占卜師":
            prediction = random.choice(["普通蘿蔔", "大蘿蔔", "幸運蘿蔔", "壞運蘿蔔"])
            await message.channel.send(f"🔮 蘿蔔占卜師預言：你下一次可能會拔出「{prediction}」！")

        elif triggered_event == "蘿蔔金幣雨":
            user_data["coins"] = user_data.get("coins", 0) + 50
            await message.channel.send("🪙 蘿蔔金幣雨降臨！你獲得了額外 50 金幣！")

        elif triggered_event == "冰封蘿蔔":
            if now.month in [12, 1, 2]:
                farm = user_data.get("farm", {})
                if farm.get("status") == "planted":
                    old_time = datetime.fromisoformat(farm["harvest_time"])
                    farm["harvest_time"] = (old_time + timedelta(hours=6)).isoformat()
                    farm["frosted"] = True
                    await message.channel.send("🧊 冰封蘿蔔出現！雖然收成延後，但品質更佳！")

    # ===== 更新 Firebase / DB =====
    ref.set(user_data)

    # ===== 結果 Embed =====
    color = get_carrot_rarity_color(result)
    embed = discord.Embed(
        title="💪 拔蘿蔔結果",
        description=f"你拔出了：**{result}**",
        color=color
    )
    embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
    embed.set_thumbnail(url=get_carrot_thumbnail(result))
    embed.set_footer(text=f"📅 {today}｜🌙 晚上十二點過後可再拔")

    embed.add_field(
        name="📖 新發現！" if is_new else "📘 已收藏",
        value="你的圖鑑新增了一種蘿蔔！" if is_new else "這種蘿蔔你已經擁有囉！",
        inline=False
    )
    embed.add_field(name="🔁 今日剩餘次數", value=f"{remaining} 次", inline=True)

    if pool_type == "special":
        embed.add_field(name="🎯 特殊蘿蔔池", value="你進入了特殊蘿蔔池，抽出稀有蘿蔔的機率大幅提升！", inline=False)

    if triggered_event:
        embed.add_field(name="🎉 事件觸發", value=f"你觸發了「{triggered_event}」事件！", inline=False)

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
    
        
# --- 種蘿蔔主函式 ---
async def handle_plant_carrot(message, user_id, user_data, ref=None, fertilizer="普通肥料"):

    # --- 保證 user_data 必備欄位存在（避免 ref.set() 覆蓋資料時缺欄位）---
    user_data = sanitize_user_data(user_data)

    current_channel = await ensure_player_thread(message)
    if current_channel is None:
        return

    # --- Firebase 自動建立 ref ---
    if ref is None:
        ref = get_user_ref(user_id)

    # --- 時區統一（台灣）---
    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz)

    farm = user_data.get("farm", {})
    fertilizers = user_data.get("fertilizers", {})
    land_level = farm.get("land_level", 1)
    pull_count = farm.get("pull_count", 0)
    gloves = user_data.get("gloves", [])

    # --- 已種過 ---
    if farm.get("status") == "planted":
        await current_channel.send("🌱 你已經種了一根蘿蔔，請先收成再種新的！")
        return

    # --- 肥料不足 ---
    if fertilizers.get(fertilizer, 0) <= 0:
        await current_channel.send(
            f"❌ 你沒有 {fertilizer}\n💰 金幣：{user_data.get('coins', 0)}"
        )
        return

   # --- 收成時間計算 ---
    base_hours = 24
    # 從 -2 調整為 -4
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
            glove_display_list.append(glove_effects.get(g, g))

    if not glove_display_list:
        glove_display_list.append("無（沒有手套效果）")

    glove_display_text = "\n".join(glove_display_list)

    total_hours = base_hours + fertilizer_bonus + land_bonus + glove_bonus

    # --- 確保至少 1 小時（避免未來土地太強變成 0 小時收成）---
    total_hours = max(1, total_hours)

    harvest_time = now + timedelta(hours=total_hours)

    # --- 扣肥料 ---
    fertilizers[fertilizer] = fertilizers.get(fertilizer, 0) - 1
    user_data["fertilizers"] = fertilizers

    # --- 更新 farm 資料 ---
    farm.update({
        "plant_time": now.isoformat(),
        "harvest_time": harvest_time.isoformat(),
        "status": "planted",
        "fertilizer": fertilizer,
        "land_level": land_level,
        "pull_count": pull_count,
        "thread_id": message.channel.id,
        "reminded": False  # <--- 🔥 加入這一行
    })

    user_data["farm"] = farm

    # --- 寫入 Firebase（✔ 安全）---
    ref.set(user_data)

    # --- 顯示剩餘時間 ---
    remaining = harvest_time - now
    left_hours = remaining.days * 24 + remaining.seconds // 3600
    minutes = (remaining.seconds % 3600) // 60

    embed = discord.Embed(
        title="🌱 成功種下蘿蔔！",
        description=f"你使用 **{fertilizer}** 種下了一根蘿蔔！準備等待收成吧！",
        color=discord.Color.green()
    )
    embed.set_thumbnail(url="https://jackiela.github.io/carrot-bot/images/plant.png")
    embed.add_field(name="📅 預計收成時間", value=f"**{harvest_time.strftime('%Y-%m-%d %H:%M')}**", inline=False)
    embed.add_field(name="⏳ 剩餘時間", value=f"**約 {left_hours} 小時 {minutes} 分鐘**", inline=False)

    # --- 時間縮減顯示 ---
    shorten_lines = []
    if fertilizer_bonus != 0:
        shorten_lines.append(f"🧪 {fertilizer}：`-{abs(fertilizer_bonus)} 小時`")
    if land_bonus != 0:
        shorten_lines.append(f"🏕️ 土地 Lv.{land_level}：`-{abs(land_bonus)} 小時`")
    if glove_bonus != 0:
        shorten_lines.append(f"🧤 強化手套：`-{abs(glove_bonus)} 小時`")

    total_short = abs(fertilizer_bonus + land_bonus + glove_bonus)
    shorten_text = "\n".join(shorten_lines) if shorten_lines else "（無縮時加成）"

    embed.add_field(name=f"✂ 時間縮減（共 `{total_short}` 小時）", value=shorten_text, inline=False)

    embed.add_field(name="🧪 肥料庫存", value=f"{fertilizer}：剩餘 **{fertilizers[fertilizer]}** 個", inline=False)
    embed.add_field(name="🧤 手套", value=glove_display_text, inline=False)
    embed.set_footer(text="你可以隨時使用：!收成蘿蔔")

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
    # 這裡的 tz 必須與 get_now/parse_datetime 函式中使用的時區一致，
    # 確保所有時間戳記都基於台灣時區。
    tz_taipei = timezone(timedelta(hours=8)) 
    from utils import get_now, parse_datetime # 假設這些函式已匯入

    await bot.wait_until_ready()  # 確保機器人準備好

    while not bot.is_closed():
        try:
            ref = db_module.reference("/users")
            all_users = ref.get()

            if not all_users:
                await asyncio.sleep(60)
                continue

            now = get_now() # 使用統一的 get_now() 確保時區一致

            for user_id, user_data in all_users.items():
                if not isinstance(user_data, dict):
                    continue
                
                # -----------------------------------
                # 💰 邏輯 A: 裝飾品被動金幣生成 (每日計算)
                # -----------------------------------
                
                # 1. 取得上次更新時間
                last_update_str = user_data.get("last_passive_coin_update")
                
                # 首次啟動：設置為 1 天前
                if not last_update_str:
                    last_update = now - timedelta(days=1) 
                else:
                    try:
                        last_update = parse_datetime(last_update_str)
                    except Exception:
                        last_update = now - timedelta(days=1)

                # 2. 計算時間差（天數）
                time_elapsed = now - last_update
                days_elapsed = time_elapsed.total_seconds() / 86400.0
                
                # 如果經過時間不到 23 小時 (約 0.958 天)，跳過金幣計算
                if days_elapsed >= 0.958:
                    
                    # 3. 計算總收益率 (Coins/Day)
                    total_daily_rate = 0
                    decorations = user_data.get("decorations", [])
                    
                    for deco in decorations:
                        total_daily_rate += DECORATION_PASSIVE_BONUS.get(deco, 0)
                    
                    # 4. 計算總共獲得金幣
                    full_days_to_award = int(days_elapsed)
                    coins_gained = full_days_to_award * total_daily_rate
                    
                    if coins_gained > 0:
                        # 5. 更新金幣和時間戳
                        current_coins = user_data.get("coins", 0)
                        new_coins = current_coins + coins_gained
                        
                        user_ref = db_module.reference(f"/users/{user_id}")
                        new_last_update = last_update + timedelta(days=full_days_to_award)
                        
                        user_ref.update({
                            "coins": new_coins,
                            "last_passive_coin_update": new_last_update.isoformat() 
                        })
                        
                        print(f"[PASSIVE] User {user_id} gained {coins_gained} coins from decorations ({full_days_to_award} full days). New total: {new_coins}")
                    
                    # 即使沒有收益，如果時間差已經超過 1 天，也應該更新時間戳
                    elif full_days_to_award > 0:
                        user_ref = db_module.reference(f"/users/{user_id}")
                        new_last_update = last_update + timedelta(days=full_days_to_award)
                        user_ref.update({
                            "last_passive_coin_update": new_last_update.isoformat()
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

    
# ===== 收成蘿蔔（修正版：肥料 + 手套效果） =====
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

    # ------ 計算手套金幣加成 ------
    bonus_coins = 0
    glove_text_list = []

    for glove in gloves:
        if glove == "幸運手套":
            bonus_coins += 5  # 每個幸運手套 +5 金幣
            glove_text_list.append("🧤 幸運手套：額外 +5 金幣")
        elif glove == "黃金手套":
            bonus_coins += 10  # 黃金手套 +10 金幣
            glove_text_list.append("🧤 黃金手套：額外 +10 金幣")

    # ------ 計算肥料與土地影響（已有 pull_carrot_by_farm 函式可用） ------
    result, base_price = pull_carrot_by_farm(fertilizer, land_level)
    price = base_price + bonus_coins

    # ------ 新發現圖鑑 ------
    new_discovery = False
    user_data.setdefault("carrots", [])
    if result not in user_data["carrots"]:
        user_data["carrots"].append(result)
        new_discovery = True

    # ------ 更新使用者資料 ------
    user_data["coins"] = user_data.get("coins", 0) + price
    user_data["farm"]["status"] = "harvested"
    user_data["farm"]["pull_count"] = user_data["farm"].get("pull_count", 0) + 1
    ref.set(user_data)

    # ------ 建立嵌入訊息 ------
    color = get_carrot_rarity_color(result)
    embed = discord.Embed(
        title="🌾 收成成功！",
        description=f"你成功收成了一根 **{result}** 🥕",
        color=color
    )
    embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
    embed.set_thumbnail(url=get_carrot_thumbnail(result))
    embed.add_field(name="💰 獲得金幣", value=f"{price} 金幣", inline=True)
    embed.add_field(name="🧪 使用肥料", value=fertilizer, inline=True)
    embed.add_field(name="🌾 土地等級", value=f"Lv.{land_level}", inline=True)

    if glove_text_list:
        embed.add_field(name="🧤 手套效果", value="\n".join(glove_text_list), inline=False)

    if new_discovery:
        embed.add_field(name="📖 新發現！", value="你的圖鑑新增了一種蘿蔔！", inline=False)

    embed.set_footer(text="📅 收成完成｜可再次種植新蘿蔔 🌱")
    await current_channel.send(embed=embed)

# ===== 購買肥料 =====
async def handle_buy_fertilizer(message, user_id, user_data, ref, fertilizer):
    # --- ✅ 使用者資料防呆，防止型態錯誤導致崩潰 ---
    user_data = sanitize_user_data(user_data)
    
    prices = {
        "普通肥料": 10,
        "高級肥料": 30,
        "神奇肥料": 100
    }

    if fertilizer not in prices:
        await message.channel.send("❌ 肥料種類錯誤，只能購買：普通肥料、高級肥料、神奇肥料")
        return

    coins = user_data.get("coins", 0)
    cost = prices[fertilizer]
    if coins < cost:
        await message.channel.send(f"💸 金幣不足！{fertilizer} 價格為 {cost} 金幣，你目前只有 {coins} 金幣")
        return

    user_data.setdefault("fertilizers", {})
    user_data["fertilizers"][fertilizer] = user_data["fertilizers"].get(fertilizer, 0) + 1
    user_data["coins"] -= cost
    ref.set(user_data)

    embed = discord.Embed(
        title="🛒 購買成功",
        description=f"你購買了 1 個 **{fertilizer}**",
        color=discord.Color.blue()
    )
    embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
    embed.add_field(name="💰 花費金幣", value=f"{cost} 金幣", inline=True)
    embed.add_field(name="💰 剩餘金幣", value=f"{user_data['coins']} 金幣", inline=True)
    embed.add_field(name="🧪 肥料庫存", value=f"{fertilizer}：{user_data['fertilizers'][fertilizer]} 個", inline=False)

    await message.channel.send(embed=embed)


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

# ===== 農場總覽卡（Embed 顯示）=====
async def show_farm_overview(message, user_id, user_data, ref):
    # 內部匯入確保工具可用
    from utils_sanitize import sanitize_user_data
    from utils import parse_datetime, get_remaining_time_str, get_decoration_thumbnail
    import io
    import discord

    # 🌟 修正點 A：使用最穩定的方式獲取 Bot Client 實體
    # 統一變數名稱為 bot_client
    try:
        bot_client = message._state.client
    except AttributeError:
        # 備用方案：如果上述路徑失敗，嘗試從 channel 取得
        bot_client = message.channel._state.client
    
    user_data = sanitize_user_data(user_data)
    
    current_channel = await ensure_player_thread(message)
    if current_channel is None:
        return

    # --- 資料讀取與防呆 ---
    farm = user_data.get("farm", {})
    fertilizers = user_data.get("fertilizers", {})
    coins = user_data.get("coins", 0)
    gloves = user_data.get("gloves", [])
    decorations = user_data.get("decorations", [])
    lucky_bags = user_data.get("lucky_bag", 0)

    if not isinstance(gloves, list): gloves = []
    if not isinstance(decorations, list): decorations = []

    fertilizer_used = farm.get("fertilizer", "未使用")
    land_level = farm.get("land_level", 1)
    pull_count = farm.get("pull_count", 0)
    remaining_pulls = max(0, 3 - pull_count)

    # --- 狀態與時間 ---
    status_map = {"planted": "🌱 已種植", "harvested": "🥕 已收成", "未種植": "🌾 未種植"}
    status_text = status_map.get(farm.get("status", "未知"), "未知")

    # --- Embed 製作 ---
    embed = discord.Embed(
        title="🌾 農場總覽卡",
        description=f"👤 玩家：{message.author.display_name}",
        color=discord.Color.green()
    )
    embed.add_field(name="🏷️ 土地狀態", value=f"Lv.{land_level} {status_text}", inline=True)
    embed.add_field(name="💰 金幣餘額", value=f"{coins} 金幣", inline=True)
    embed.add_field(name="🧪 使用肥料", value=fertilizer_used, inline=False)
    
    # 倉庫摘要
    repo_text = (
        f"🧪 肥料：{sum(fertilizers.values()) if isinstance(fertilizers, dict) else 0}\n"
        f"🧤 手套：{len(gloves)} 件\n"
        f"🧧 福袋：{lucky_bags} 個"
    )
    embed.add_field(name="📦 農場資源", value=repo_text, inline=False)

    if decorations:
        embed.add_field(name="🎍 已放置裝飾", value=", ".join(decorations), inline=False)

    embed.set_footer(text="📅 每日凌晨重置次數 🌙")

    # 1. 先發送 Embed
    await current_channel.send(embed=embed)

    # 2. 🌟 修正點 B：下載圖片邏輯 🌟
    if decorations:
        files = []
        for d in decorations:
            url = get_decoration_thumbnail(d)
            try:
                # 使用剛才定義的 bot_client
                async with bot_client.http._HTTPClient__session.get(url) as resp:
                    if resp.status == 200:
                        img_bytes = await resp.read()
                        files.append(discord.File(
                            fp=io.BytesIO(img_bytes),
                            filename=f"deco_{d}.png"
                        ))
            except Exception as e:
                print(f"[DEBUG] 圖片下載失敗 ({d}): {e}")

        if files:
            # 異步發送圖片，不影響主 Embed
            await current_channel.send(content="🎍 **農場裝飾實況：**", files=files)



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
async def handle_buy_glove(message, user_id, user_data, ref, glove_name, show_farm_overview):
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
    await show_farm_overview(message, user_id, user_data, ref)

# 🎍 購買裝飾（購買後自動顯示農場總覽）
async def handle_buy_decoration(message, user_id, user_data, ref, deco_name):
    user_data = sanitize_user_data(user_data)

    shop = {
        "花圃": 80,
        "木柵欄": 100,
        "竹燈籠": 150,
        "鯉魚旗": 200,
        "聖誕樹": 250
    }

    if deco_name not in shop:
        await message.channel.send(
            "❌ 沒有這種裝飾！\n可購買：花圃、木柵欄、竹燈籠、鯉魚旗、聖誕樹"
        )
        return

    cost = shop[deco_name]
    coins = user_data.get("coins", 0)

    if coins < cost:
        await message.channel.send(
            f"💸 金幣不足！\n{deco_name} 價格 **{cost}** 金幣，你目前只有 **{coins}**"
        )
        return

    user_data["coins"] = coins - cost
    user_data.setdefault("decorations", [])

    # 防止重複購買
    if deco_name in user_data["decorations"]:
        await message.channel.send(f"你已經擁有 **{deco_name}** 了！")
        return

    user_data["decorations"].append(deco_name)
    ref.set(user_data)

    # --- 🎨 購買成功 Embed --- 
    embed = discord.Embed(
        title="🎍 裝飾購買成功！",
        description=f"你購入了 **{deco_name}**！農場變得更漂亮了 🌾",
        color=discord.Color.green()
    )
    # 🌟 顯示裝飾圖片 
    embed.set_thumbnail(url=get_decoration_thumbnail(deco_name))    

    embed.add_field(
        name="💰 剩餘金幣",
        value=f"{user_data['coins']} 金幣",
        inline=False
    )

    await message.channel.send(embed=embed) 
    # 🌾 顯示農場總覽 updated_data = ref.get() 
    await show_farm_overview(message, user_id, updated_data, ref) # 👈 這裡調用 show_farm_overview


# 🧧 開運福袋（含特效與農場總覽）
async def handle_open_lucky_bag(message, user_id, user_data, ref):
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
    await show_farm_overview(message, user_id, updated_data, ref)
    
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
