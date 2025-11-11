import datetime
import random
import discord
import asyncio
from firebase_admin import db
from datetime import datetime, timedelta

# ===== 導入自訂工具 =====
from utils import (
    get_today, get_now, get_remaining_hours,
    get_carrot_thumbnail, get_carrot_rarity_color
)
from utils_sanitize import sanitize_user_data
from carrot_data import common_carrots, rare_carrots, legendary_carrots, all_carrots
from fortune_data import fortunes


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
        bonus += 5
    elif fertilizer == "神奇肥料":
        bonus += 15
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
    # --- ✅ 使用者資料防呆，防止型態錯誤導致崩潰 ---
    user_data = sanitize_user_data(user_data)
    
    data = db.reference("/users").get()
    if not data:
        await message.channel.send("📊 目前還沒有任何玩家收集蘿蔔！")
        return

    ranking = sorted(
        data.items(),
        key=lambda x: len(x[1].get("carrots", [])),
        reverse=True
    )

    reply = "🏆 蘿蔔收集排行榜 🥕\n"
    for i, (uid, info) in enumerate(ranking[:5], start=1):
        count = len(info.get("carrots", []))
        reply += f"{i}. {info.get('name', '未知玩家')} — {count}/{len(all_carrots)} 種\n"

    await message.channel.send(reply)

# ===== 胡蘿蔔小知識 =====
async def handle_carrot_fact(message):
    # --- ✅ 使用者資料防呆，防止型態錯誤導致崩潰 ---
    user_data = sanitize_user_data(user_data)
    
    fact = random.choice(carrot_facts)
    await message.channel.send(f"🥕 胡蘿蔔小知識：{fact}")

# ===== 胡蘿蔔料理 =====
async def handle_carrot_recipe(message):
    recipe_name = random.choice(list(recipes.keys()))
    detail = recipes[recipe_name]
    await message.channel.send(
        f"🍴 今日推薦胡蘿蔔料理：**{recipe_name}**\n📖 做法：\n{detail}"
    )

# ===== 種植小貼士 =====
async def handle_carrot_tip(message):
    # --- ✅ 使用者資料防呆，防止型態錯誤導致崩潰 ---
    user_data = sanitize_user_data(user_data)
    
    tip = random.choice(carrot_tips)
    await message.channel.send(f"🌱 胡蘿蔔種植小貼士：{tip}")
    
# ✅ 自動收成提醒
async def schedule_harvest_reminder(user_id, channel, harvest_time):
    # --- ✅ 使用者資料防呆，防止型態錯誤導致崩潰 ---
    user_data = sanitize_user_data(user_data)
    
    now = datetime.now()
    delay = (harvest_time - now).total_seconds()
    if delay > 0:
        await asyncio.sleep(delay)
        await channel.send(f"🥕 <@{user_id}> 你的蘿蔔已成熟，可以收成囉！使用 `!收成蘿蔔`")

# ✅ 種蘿蔔主函式
async def handle_plant_carrot(message, user_id, user_data, ref, fertilizer="普通肥料"):
    # --- ✅ 使用者資料防呆，防止型態錯誤導致崩潰 ---
    user_data = sanitize_user_data(user_data)
    
    current_channel = await ensure_player_thread(message)
    if current_channel is None:
        return

    now = get_now()
    farm = user_data.get("farm", {})
    fertilizers = user_data.get("fertilizers", {})
    land_level = farm.get("land_level", 1)
    pull_count = farm.get("pull_count", 0)

    if farm.get("status") == "planted":
        await current_channel.send("🌱 你已經種了一根蘿蔔，請先收成再種新的一根！")
        return

    if fertilizers.get(fertilizer, 0) <= 0:
        await current_channel.send(
            f"❌ 你沒有 {fertilizer}，請先購買！\n💰 你目前金幣：{user_data.get('coins', 0)}\n🛒 使用 !購買肥料 {fertilizer} 來購買"
        )
        return

    # ✅ 計算收成時間
    harvest_time = now + timedelta(days=1)
    if fertilizer == "神奇肥料":
        harvest_time -= timedelta(hours=6)
    elif fertilizer == "高級肥料":
        harvest_time -= timedelta(hours=2)
    harvest_time -= timedelta(hours=land_level * 2)

    # ✅ 更新資料
    fertilizers[fertilizer] -= 1
    user_data["farm"] = {
        "plant_time": now.isoformat(),
        "harvest_time": harvest_time.isoformat(),
        "status": "planted",
        "fertilizer": fertilizer,
        "land_level": land_level,
        "pull_count": pull_count
    }
    ref.set(user_data)

    # ✅ 顯示冷卻倒數
    remaining = harvest_time - now
    total_hours = remaining.days * 24 + remaining.seconds // 3600
    minutes = (remaining.seconds % 3600) // 60

    await current_channel.send(
        f"🌱 你使用了 {fertilizer} 種下蘿蔔！\n"
        f"📅 預計收成時間：{harvest_time.strftime('%Y-%m-%d %H:%M')}\n"
        f"⏳ 剩餘時間：約 {total_hours} 小時 {minutes} 分鐘\n"
        f"🧪 剩餘 {fertilizer}：{fertilizers[fertilizer]} 個\n"
        f"🏕️ 土地等級 Lv.{land_level}，已縮短 {land_level * 2} 小時"
    )

    # ✅ 啟動收成提醒
    asyncio.create_task(schedule_harvest_reminder(user_id, current_channel, harvest_time))
    
# ===== 收成蘿蔔 =====
async def handle_harvest_carrot(message, user_id, user_data, ref):
    # --- ✅ 使用者資料防呆，防止型態錯誤導致崩潰 ---
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
        await message.channel.send("🪴 你還沒種蘿蔔喔，請先使用 `!種蘿蔔`！")
        return

    harvest_time = parse_datetime(farm["harvest_time"])
    if now < harvest_time:
        time_str = get_remaining_time_str(harvest_time)
        await message.channel.send(f"⏳ 蘿蔔還在努力生長中！{time_str}才能收成喔～")
        return

    fertilizer = farm.get("fertilizer", "普通肥料")
    land_level = farm.get("land_level", 1)
    result, price = pull_carrot_by_farm(fertilizer, land_level)

    new_discovery = False
    user_data.setdefault("carrots", [])
    if result not in user_data["carrots"]:
        user_data["carrots"].append(result)
        new_discovery = True

    user_data["coins"] = user_data.get("coins", 0) + price
    user_data["farm"]["status"] = "harvested"
    user_data["farm"]["pull_count"] = user_data["farm"].get("pull_count", 0) + 1
    ref.set(user_data)

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

    if new_discovery:
        embed.add_field(name="📖 新發現！", value="你的圖鑑新增了一種蘿蔔！", inline=False)

    embed.set_footer(text="📅 收成完成｜可再次種植新蘿蔔 🌱")
    await message.channel.send(embed=embed)

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
async def handle_land_progress(message, user_id, user_data):
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
async def show_farm_overview(message, user_id, user_data):
    # --- ✅ 使用者資料防呆，防止型態錯誤導致崩潰 ---
    user_data = sanitize_user_data(user_data)
    
    from utils import parse_datetime, get_remaining_time_str
    current_channel = await ensure_player_thread(message)
    if current_channel is None:
        return

    farm = user_data.get("farm", {})
    fertilizers = user_data.get("fertilizers", {})
    coins = user_data.get("coins", 0)
    gloves = user_data.get("gloves")
    decorations = user_data.get("decorations")
    lucky_bags = user_data.get("lucky_bag", 0)

    # ✅ 修復格式
    if not isinstance(gloves, list):
        gloves = [gloves] if isinstance(gloves, str) else []
    if not isinstance(decorations, list):
        decorations = [decorations] if isinstance(decorations, str) else []

    fertilizer_used = farm.get("fertilizer", "未使用")
    land_level = farm.get("land_level", 1)
    pull_count = farm.get("pull_count", 0)
    remaining_pulls = max(0, 3 - pull_count)

    status_map = {
        "planted": "🌱 已種植，請等待收成",
        "harvested": "🥕 已收成，可種植新蘿蔔",
        "未種植": "🌾 尚未種植，可開始新的輪作",
    }
    status_text = status_map.get(farm.get("status", "未知"), "未知")

    harvest_display = "未種植"
    harvest_time_str = farm.get("harvest_time")
    if harvest_time_str:
        try:
            harvest_time = parse_datetime(harvest_time_str)
            formatted_time = harvest_time.strftime("%Y/%m/%d %H:%M")
            remaining_str = get_remaining_time_str(harvest_time)
            harvest_display = (
                f"{formatted_time}（✅ 已可收成）"
                if "✅" in remaining_str or "已到時間" in remaining_str
                else f"{formatted_time}（{remaining_str}）"
            )
        except Exception as e:
            harvest_display = f"⚠️ 時間格式錯誤：{e}"

    embed = discord.Embed(
        title="🌾 農場總覽卡",
        description=f"👤 玩家：{message.author.display_name}",
        color=discord.Color.green()
    )
    embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
    embed.add_field(name="🏷️ 土地狀態", value=f"Lv.{land_level} 的土地目前 {status_text}", inline=False)
    embed.add_field(name="🧪 使用肥料", value=fertilizer_used, inline=True)
    embed.add_field(name="⏳ 收成時間", value=harvest_display, inline=True)
    embed.add_field(name="💰 金幣餘額", value=f"{coins} 金幣", inline=False)
    embed.add_field(name="🔁 今日剩餘拔蘿蔔次數", value=f"{remaining_pulls} 次", inline=False)
    embed.add_field(name="─" * 20, value="📦 農場資源狀況", inline=False)

    # ✅ 肥料庫存
    embed.add_field(
        name="🧪 肥料庫存",
        value=(
            f"• 普通肥料：{fertilizers.get('普通肥料', 0)} 個\n"
            f"• 高級肥料：{fertilizers.get('高級肥料', 0)} 個\n"
            f"• 神奇肥料：{fertilizers.get('神奇肥料', 0)} 個"
        ),
        inline=False
    )

    # ✅ 手套效果顯示
    glove_effects = {
        "幸運手套": "🎯 大吉時掉出蘿蔔",
        "農夫手套": "💰 收成金幣 +20%",
        "強化手套": "⏳ 種植時間 -1 小時",
        "神奇手套": "🌟 稀有機率提升"
    }
    if gloves:
        glove_text = "\n".join(f"• {g} — {glove_effects.get(g, '未知效果')}" for g in gloves)
    else:
        glove_text = "尚未擁有任何手套"
    embed.add_field(name="🧤 擁有手套", value=glove_text, inline=False)

    # ✅ 裝飾風格顯示
    decoration_styles = {
        "花圃": "🌸 花園風格",
        "木柵欄": "🪵 鄉村風格",
        "竹燈籠": "🎋 和風夜景",
        "鯉魚旗": "🎏 節慶裝飾",
        "聖誕樹": "🎄 節慶奇蹟"
    }
    if decorations:
        deco_text = "\n".join(f"• {d} — {decoration_styles.get(d, '未知風格')}" for d in decorations)
    else:
        deco_text = "尚未放置任何裝飾"
    embed.add_field(name="🎍 農場裝飾", value=deco_text, inline=False)

    # ✅ 福袋狀態
    embed.add_field(
        name="🧧 開運福袋",
        value=(
            f"你擁有 {lucky_bags} 個，可以使用 !開福袋 來開啟！"
            if lucky_bags > 0
            else "尚未擁有，可以花費 80 金幣購買。"
        ),
        inline=False
    )

    # ✅ 肥料不足提醒
    if sum(fertilizers.get(k, 0) for k in ["普通肥料", "高級肥料", "神奇肥料"]) == 0:
        embed.add_field(
            name="⚠️ 肥料不足",
            value="你目前沒有任何肥料，請使用 !購買肥料 普通肥料 來補充！",
            inline=False
        )

    embed.set_footer(text="📅 每日凌晨重置拔蘿蔔次數與運勢 🌙")
    await current_channel.send(embed=embed)

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

    gloves = user_data.get("gloves")
    if not isinstance(gloves, list):
        gloves = [gloves] if isinstance(gloves, str) else []
    user_data["gloves"] = gloves

    user_data["coins"] -= cost
    if glove_name not in gloves:
        gloves.append(glove_name)

    ref.set(user_data)
        # ✅ 顯示購買成功訊息
    await message.channel.send(f"🧤 你購買了 **{glove_name}**！\n📈 效果：{GLOVE_SHOP[glove_name]['desc']}")
    
    # ✅ 重新讀取最新資料並顯示農場總覽卡
    updated_data = ref.get()
    await show_farm_overview(message, user_id, updated_data)

# 🎍 購買裝飾（購買後自動顯示農場總覽）
async def handle_buy_decoration(message, user_id, user_data, ref, deco_name):
    # --- ✅ 使用者資料防呆，防止型態錯誤導致崩潰 ---
    user_data = sanitize_user_data(user_data)
    
    shop = {
        "花圃": 80,
        "木柵欄": 100,
        "竹燈籠": 150,
        "鯉魚旗": 200,
        "聖誕樹": 250
    }

    if deco_name not in shop:
        await message.channel.send("❌ 沒有這種裝飾！可購買：花圃、木柵欄、竹燈籠、鯉魚旗、聖誕樹")
        return

    cost = shop[deco_name]
    coins = user_data.get("coins", 0)
    if coins < cost:
        await message.channel.send(f"💸 金幣不足！{deco_name} 價格 {cost} 金幣，你目前只有 {coins}")
        return

    user_data["coins"] -= cost
    user_data.setdefault("decorations", [])
    if deco_name not in user_data["decorations"]:
        user_data["decorations"].append(deco_name)
    ref.set(user_data)

    # ✅ 顯示購買成功訊息
    await message.channel.send(f"🎍 你購買了 **{deco_name}**！農場更漂亮了 🌾")

    # ✅ 重新讀取最新資料並顯示農場總覽卡
    updated_data = ref.get()
    await show_farm_overview(message, user_id, updated_data)

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
    await show_farm_overview(message, user_id, updated_data)
# 🏪 商店總覽
async def handle_shop(message):
    # --- ✅ 使用者資料防呆，防止型態錯誤導致崩潰 ---
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

async def handle_give_coins(message, args):
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

async def handle_carrot_info(message):
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
