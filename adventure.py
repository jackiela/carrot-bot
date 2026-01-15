import random
import time
import discord
import asyncio
import io
from datetime import datetime
from utils import get_today, is_admin

# 🌟 重新設計副本與隨機怪物資料
DUNGEONS = {
    "新手森林": {
        "min_lvl": 1,
        "reward": (30, 60),
        "monsters": [
            {"name": "小史萊姆", "hp": 50, "atk": 8, "weight": 60, "desc": "軟趴趴的基礎怪物。"},
            {"name": "大史萊姆", "hp": 90, "atk": 15, "weight": 30, "desc": "森林裡的小霸王，要小心它的撞擊！"},
            {"name": "憤怒的野兔", "hp": 150, "atk": 22, "weight": 10, "is_elite": True, "desc": "【精英】被搶走蘿蔔的兔子，進入了狂暴狀態！"}
        ]
    },
    "幽暗地窟": {
        "min_lvl": 5,
        "reward": (150, 350),
        "monsters": [
            {"name": "腐爛殭屍", "hp": 220, "atk": 30, "weight": 55, "desc": "動作遲緩但力量驚人。"},
            {"name": "骷髏弓箭手", "hp": 280, "atk": 45, "weight": 35, "desc": "躲在暗處放冷箭的卑鄙亡靈。"},
            {"name": "骷髏隊長", "hp": 500, "atk": 65, "weight": 10, "is_elite": True, "desc": "【精英】生前曾是英勇的戰士，守護著地窟。"}
        ]
    },
    "烈日荒漠": {
        "min_lvl": 10,
        "reward": (500, 900),
        "env_effect": "heat",
        "monsters": [
            {"name": "仙人掌怪", "hp": 500, "atk": 55, "weight": 55, "desc": "渾身是刺，不小心碰到會很痛。"},
            {"name": "沙漠毒蠍", "hp": 650, "atk": 80, "weight": 35, "desc": "尾刺帶有劇毒，令人望而生畏。"},
            {"name": "沙漠死神", "hp": 1100, "atk": 110, "weight": 10, "is_elite": True, "desc": "【精英】荒漠的古老支配者，沒人見過它還能活著。"}
        ]
    },
    "熔岩巨塔": {
        "min_lvl": 15,
        "reward": (1200, 2500),
        "monsters": [
            {"name": "小火靈", "hp": 900, "atk": 100, "weight": 50, "desc": "由岩漿組成的靈魂體。"},
            {"name": "熔岩巨人", "hp": 1500, "atk": 140, "weight": 40, "desc": "踏出每一步都會讓大地顫抖。"},
            {"name": "地獄火魔", "hp": 2500, "atk": 200, "weight": 10, "is_elite": True, "desc": "【精英】巨塔的主人，全身燃燒著永恆之火。"}
        ]
    }
}

# 蘿蔔食用效果
CARROT_EFFECTS = {
    "普通蘿蔔": {"hp": 20, "buff": None, "desc": "回復 20 HP"},
    "🥇 黃金蘿蔔": {"hp": 50, "buff": "double_gold", "desc": "回復 50 HP，下場金幣翻倍"},
    "🌈 彩虹蘿蔔": {"hp": 100, "buff": "invincible", "desc": "HP 全滿，下場無敵"},
    "🧊 冰晶蘿蔔": {"hp": 40, "buff": "heat_resist", "desc": "回復 40 HP，獲得【耐熱】效果"}
}

async def admin_reset_player(message, user_id, user_data, ref):
    if not is_admin(str(message.author.id)):
        await message.channel.send("❌ 你沒有權限使用此指令。")
        return

    level = user_data.get("level", 1)
    max_hp = 100 + (level * 10)
    
    ref.update({
        "daily_adv_count": 0,
        "hp": max_hp,
        "last_regen_time": time.time(),
        "last_login_day": get_today(),
        "active_buff": None
    })
    await message.channel.send(f"✅ **管理員操作**：已成功重置 **{message.author.display_name}** 的狀態。")

async def handle_eat_carrot(message, user_id, user_data, ref, carrot_name):
    inventory = user_data.get("inventory", {})
    if inventory.get(carrot_name, 0) <= 0:
        await message.channel.send(f"❌ 你的背包裡沒有 **{carrot_name}**！")
        return

    effect = CARROT_EFFECTS.get(carrot_name)
    if not effect:
        await message.channel.send("❓ 這種蘿蔔不能直接食用。")
        return

    hp = user_data.get("hp", 100)
    max_hp = 100 + (user_data.get("level", 1) * 10)
    
    # 彩虹蘿蔔特殊處理：滿血
    if carrot_name == "🌈 彩虹蘿蔔":
        new_hp = max_hp
    else:
        new_hp = min(max_hp, hp + effect["hp"])
    
    inventory[carrot_name] -= 1
    update_data = {"hp": new_hp, "inventory": inventory, "last_regen_time": time.time()}
    if effect["buff"]:
        update_data["active_buff"] = effect["buff"]

    ref.update(update_data)
    await message.channel.send(f"🍴 {message.author.mention} 吃掉了 **{carrot_name}**！\n❤️ HP: {int(hp)} -> {int(new_hp)}\n✨ 獲得效果: {effect['desc']}")

async def start_adventure(message, user_id, user_data, ref, dungeon_key):
    # 跨天重置
    today = get_today()
    if user_data.get("last_login_day") != today:
        daily_count = 0
        ref.update({"daily_adv_count": 0, "last_login_day": today})
    else:
        daily_count = user_data.get("daily_adv_count", 0)

    if daily_count >= 5:
        await message.channel.send("😫 你今天已經冒險 5 次了，請明天再來！")
        return

    dungeon = DUNGEONS.get(dungeon_key)
    if not dungeon:
        await message.channel.send(f"📍 找不到該地區。可用副本：{ '、'.join(DUNGEONS.keys()) }")
        return

    if user_data.get("level", 1) < dungeon["min_lvl"]:
        await message.channel.send(f"❌ 等級不足！{dungeon_key} 需要 Lv.{dungeon['min_lvl']}")
        return

    # 🌟 1. 隨機抽取怪物
    monsters = dungeon["monsters"]
    monster = random.choices(monsters, weights=[m["weight"] for m in monsters], k=1)[0]
    
    enemy_name = monster["name"]
    enemy_hp = monster["hp"]
    enemy_atk = monster["atk"]
    is_elite = monster.get("is_elite", False)

    # 戰鬥數值準備
    hp = user_data.get("hp", 100)
    buff = user_data.get("active_buff")
    current_player_hp = float(hp)
    player_atk = 20 + (user_data.get("level", 1) * 5)

    # 2. 環境傷害判定
    if dungeon.get("env_effect") == "heat" and buff != "heat_resist":
        current_player_hp -= 15
        await message.channel.send("🔥 **環境傷害**：酷熱讓你流失了 15 點 HP！")

    if current_player_hp <= 10:
        await message.channel.send(f"💀 你的 HP 剩餘 {int(current_player_hp)}，進去會沒命的！")
        return

    await message.channel.send(f"⚔️ 你進入了 **{dungeon_key}**...\n⚠️ 遭遇了 **{enemy_name}**！\n📜 *{monster['desc']}*")
    
    log_msg = await message.channel.send("🔄 戰鬥計算中...")
    player_turn = random.choice([True, False])

    # 3. 戰鬥迴圈
    while enemy_hp > 0 and current_player_hp > 0:
        turn_details = ""
        if player_turn:
            dmg = random.randint(player_atk - 5, player_atk + 5)
            enemy_hp -= dmg
            turn_details = f"🗡️ 你反擊造成 {dmg} 傷害！"
        else:
            dmg = 0 if buff == "invincible" else random.randint(enemy_atk - 5, enemy_atk + 5)
            current_player_hp -= dmg
            turn_details = f"💥 {enemy_name} 攻擊造成 {dmg} 傷害！"
        
        status_text = (
            f"{turn_details}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"❤️ 你的 HP: **{int(max(0, current_player_hp))}**\n"
            f"👾 {enemy_name} HP: **{int(max(0, enemy_hp))}**"
        )
        await log_msg.edit(content=status_text)
        player_turn = not player_turn
        await asyncio.sleep(1.5)

    # 4. 結算
    final_hp = max(0, current_player_hp)
    if enemy_hp <= 0:
        # 獎金加成
        reward_base = random.randint(*dungeon["reward"])
        reward = reward_base * 2 if buff == "double_gold" else reward_base
        
        # 🌟 精英怪特殊掉落
        drop_msg = ""
        if is_elite and random.random() < 0.3: # 30% 機率掉落好物
            inventory = user_data.get("inventory", {})
            rare_carrot = random.choice(["🥇 黃金蘿蔔", "🌈 彩虹蘿蔔", "🧊 冰晶蘿蔔"])
            inventory[rare_carrot] = inventory.get(rare_carrot, 0) + 1
            ref.update({"inventory": inventory})
            drop_msg = f"\n🎁 **額外掉落**：你從精英怪身上搜到了 **{rare_carrot}**！"

        new_coins = user_data.get("coins", 0) + reward
        ref.update({
            "coins": new_coins,
            "hp": final_hp,
            "daily_adv_count": daily_count + 1,
            "active_buff": None,
            "last_regen_time": time.time()
        })
        await message.channel.send(f"🏆 **戰鬥勝利！**\n💰 獲得金幣: `{reward}` (餘額: {new_coins}){drop_msg}")
    else:
        ref.update({
            "hp": 0,
            "daily_adv_count": daily_count + 1,
            "active_buff": None,
            "last_regen_time": time.time()
        })
        await message.channel.send(f"💀 你被 **{enemy_name}** 擊敗了，抬回農場緊急治療...")
