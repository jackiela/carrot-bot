import datetime
import random
import discord
from firebase_admin import db
from utils import get_today, get_now, get_remaining_hours, get_carrot_thumbnail, get_carrot_rarity_color
from carrot_data import common_carrots, rare_carrots, legendary_carrots, all_carrots
from fortune_data import fortunes
from datetime import datetime

# ✅ 通用工具：確認玩家是否在自己的田地
async def ensure_player_thread(message):
    expected_name = f"{message.author.display_name} 的田地"
    current_channel = message.channel

    parent_channel = current_channel.parent if isinstance(current_channel, discord.Thread) else current_channel
    target_thread = next((t for t in parent_channel.threads if t.name == expected_name), None)

    if not target_thread:
        async for t in parent_channel.archived_threads(limit=None):
            if t.name == expected_name:
                target_thread = t
                break

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
    today = get_today()
    pulls = user_data.get("carrot_pulls", {})
    today_pulls = pulls.get(today, 0)

    if today_pulls >= 3:
        embed = discord.Embed(
            title="🔒 拔蘿蔔次數已達上限",
            description="今天已拔過三次蘿蔔囉，請明天再來！",
            color=discord.Color.red()
        )
        embed.set_footer(text=f"📅 {today}｜🌙 晚上十二點過後可再拔")
        await message.channel.send(embed=embed)
        return

    result = pull_carrot()
    is_new = result not in user_data.get("carrots", [])
    remaining = 2 - today_pulls

    user_data.setdefault("carrots", [])
    if is_new:
        user_data["carrots"].append(result)

    user_data.setdefault("carrot_pulls", {})
    user_data["carrot_pulls"][today] = today_pulls + 1
    ref.set(user_data)

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
    embed.add_field(name="🔁 今日剩餘次數", value=f"{remaining} 次", inline=False)

    await message.channel.send(embed=embed)
    
    # ===== 蘿蔔圖鑑 =====
async def handle_carrot_encyclopedia(message, user_id, user_data):
    collected = user_data.get("carrots", [])
    if not collected:
        await message.channel.send("📖 你的圖鑑還是空的，快去拔蘿蔔吧！")
        return

    total = len(all_carrots)
    progress = len(collected)

    common_count = len([c for c in collected if c in common_carrots])
    rare_count = len([c for c in collected if c in rare_carrots])
    legendary_count = len([c for c in collected if c in legendary_carrots])

    reply = f"📖 你的蘿蔔圖鑑：{progress}/{total} 種\n"
    reply += f"🔹 普通：{common_count}/{len(common_carrots)} 種\n"
    reply += f"🔸 稀有：{rare_count}/{len(rare_carrots)} 種\n"
    reply += f"🌟 傳說：{legendary_count}/{len(legendary_carrots)} 種\n\n"
    reply += "你已收集到的蘿蔔：\n" + "\n".join(collected)

    await message.channel.send(reply)

# ===== 蘿蔔排行榜 =====
async def handle_carrot_ranking(message):
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
    tip = random.choice(carrot_tips)
    await message.channel.send(f"🌱 胡蘿蔔種植小貼士：{tip}")
    # ===== 種蘿蔔 =====
async def handle_plant_carrot(message, user_id, user_data, ref, fertilizer="普通肥料"):
    from utils import get_now
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
            f"❌ 你沒有 {fertilizer}，請先購買！\n💰 你目前金幣：{user_data.get('coins', 0)}\n🛒 使用 !購買肥料 普通肥料 來購買"
        )
        return

    harvest_time = now + datetime.timedelta(days=1)
    if fertilizer == "神奇肥料":
        harvest_time -= datetime.timedelta(hours=6)
    elif fertilizer == "高級肥料":
        harvest_time -= datetime.timedelta(hours=2)
    harvest_time -= datetime.timedelta(hours=land_level * 2)

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
    await current_channel.send(
        f"🌱 你使用了 {fertilizer} 種下蘿蔔，預計收成時間：{harvest_time.strftime('%Y-%m-%d %H:%M')}"
    )

# ===== 收成蘿蔔 =====
async def handle_harvest_carrot(message, user_id, user_data, ref):
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

# 🧤 購買手套（購買後自動顯示農場總覽，含手套效果）
async def handle_buy_glove(message, user_id, user_data, ref, glove_name):
    glove_shop = {
        "幸運手套": {"price": 100, "desc": "抽到大吉時額外掉出一根蘿蔔"},
        "農夫手套": {"price": 150, "desc": "收成時金幣 +20%"},
        "強化手套": {"price": 200, "desc": "種植時間 -1 小時"},
        "神奇手套": {"price": 500, "desc": "收成時有機率獲得稀有蘿蔔"}
    }

    if glove_name not in glove_shop:
        await message.channel.send("❌ 沒有這種手套！可購買：幸運手套、農夫手套、強化手套、神奇手套")
        return

    cost = glove_shop[glove_name]["price"]
    coins = user_data.get("coins", 0)
    if coins < cost:
        await message.channel.send(f"💸 金幣不足！需要 {cost} 金幣，你目前只有 {coins}")
        return

    # ✅ 修正手套欄位格式
    gloves = user_data.get("gloves")
    if not isinstance(gloves, list):
        gloves = [gloves] if isinstance(gloves, str) else []
    user_data["gloves"] = gloves

    # ✅ 加入手套
    user_data["coins"] -= cost
    if glove_name not in gloves:
        gloves.append(glove_name)

    ref.set(user_data)

    # ✅ 顯示購買成功訊息
    await message.channel.send(f"🧤 你購買了 **{glove_name}**！\n📈 效果：{glove_shop[glove_name]['desc']}")

    # ✅ 重新讀取最新資料並顯示農場總覽卡
    updated_data = ref.get()
    await show_farm_overview(message, user_id, updated_data)

# 🎍 購買裝飾（購買後自動顯示農場總覽）
async def handle_buy_decoration(message, user_id, user_data, ref, deco_name):
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
