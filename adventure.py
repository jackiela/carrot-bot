import random
import discord
import asyncio
import io
from datetime import datetime

# 副本資料設定
DUNGEONS = {
    "新手森林": {
        "min_lvl": 1, "hp": 60, "atk": 8, "reward": (30, 60), 
        "boss": "大史萊姆", "desc": "適合熱身的地方。"
    },
    "幽暗地窟": {
        "min_lvl": 5, "hp": 200, "atk": 25, "reward": (150, 350), 
        "boss": "骷髏隊長", "desc": "陰暗潮濕，怪物成群。"
    },
    "烈日荒漠": {
        "min_lvl": 10, "hp": 450, "atk": 50, "reward": (500, 900), 
        "boss": "沙漠死神", "desc": "酷熱難耐，沒冰晶蘿蔔會中暑！",
        "env_effect": "heat" # 環境效果：酷熱
    },
    "熔岩巨塔": {
        "min_lvl": 15, "hp": 1000, "atk": 90, "reward": (1200, 2500), 
        "boss": "地獄火魔", "desc": "岩漿橫流，考驗你的防禦力。"
    }
}

# 蘿蔔食用效果
CARROT_EFFECTS = {
    "普通蘿蔔": {"hp": 20, "buff": None, "desc": "回復 20 HP"},
    "🥇 黃金蘿蔔": {"hp": 50, "buff": "double_gold", "desc": "回復 50 HP，下場金幣翻倍"},
    "🌈 彩虹蘿蔔": {"hp": 100, "buff": "invincible", "desc": "HP 全滿，下場無敵"},
    "🧊 冰晶蘿蔔": {"hp": 40, "buff": "heat_resist", "desc": "回復 40 HP，獲得【耐熱】效果"}
}

async def handle_eat_carrot(message, user_id, user_data, ref, carrot_name):
    inventory = user_data.get("inventory", {})
    if inventory.get(carrot_name, 0) <= 0:
        await message.channel.send(f"❌ 你的背包裡沒有 **{carrot_name}**！")
        return

    effect = CARROT_EFFECTS.get(carrot_name)
    if not effect:
        await message.channel.send("❓ 這種蘿蔔不能直接食用。")
        return

    # 計算 HP
    hp = user_data.get("hp", 100)
    max_hp = 100 + (user_data.get("level", 1) * 10)
    new_hp = min(max_hp, hp + effect["hp"])
    
    # 扣除道具並加 Buff
    inventory[carrot_name] -= 1
    update_data = {"hp": new_hp, "inventory": inventory}
    if effect["buff"]:
        update_data["active_buff"] = effect["buff"]

    ref.update(update_data)
    await message.channel.send(f"🍴 {message.author.mention} 吃掉了 **{carrot_name}**！\n❤️ HP: {hp} -> {new_hp}\n✨ 獲得效果: {effect['desc']}")

async def start_adventure(message, user_id, user_data, ref, dungeon_key):
    # 檢查冒險次數
    daily_count = user_data.get("daily_adv_count", 0)
    if daily_count >= 5:
        await message.channel.send("😫 你今天已經冒險 5 次了，請明天再來！")
        return

    # 檢查 HP
    hp = user_data.get("hp", 100)
    if hp <= 10:
        await message.channel.send(f"💀 你的 HP 只有 {hp}，進去就是送死！快去吃蘿蔔。")
        return

    # 檢查副本
    dungeon = DUNGEONS.get(dungeon_key)
    if not dungeon:
        list_str = "、".join(DUNGEONS.keys())
        await message.channel.send(f"📍 找不到該地區。可用副本：{list_str}")
        return

    # 等級檢查
    if user_data.get("level", 1) < dungeon["min_lvl"]:
        await message.channel.send(f"❌ 等級不足！需要 Lv.{dungeon['min_lvl']}")
        return

    # --- 戰鬥準備 ---
    buff = user_data.get("active_buff")
    player_atk = 15 + (user_data.get("level", 1) * 3)
    enemy_hp = dungeon["hp"]
    enemy_atk = dungeon["atk"]
    
    # 環境影響邏輯
    env_msg = ""
    if dungeon.get("env_effect") == "heat" and buff != "heat_resist":
        enemy_atk += 10
        env_msg = "🔥 這裡太熱了，你的動作變得遲鈍，怪物傷害增加！\n"

    # 戰鬥過程
    msg = await message.channel.send(f"⚔️ **進入 {dungeon_key}**...\n{env_msg}🎲 戰鬥模擬中...")
    
    rounds = 0
    while enemy_hp > 0 and hp > 0 and rounds < 5:
        dmg = random.randint(player_atk-5, player_atk+10)
        enemy_hp -= dmg
        if enemy_hp <= 0: break
        
        e_dmg = 0 if buff == "invincible" else random.randint(enemy_atk-5, enemy_atk+5)
        hp -= e_dmg
        rounds += 1
        await asyncio.sleep(1)

    # --- 結算 ---
    if hp > 0:
        reward = random.randint(*dungeon["reward"])
        if buff == "double_gold": reward *= 2
        new_coins = user_data.get("coins", 0) + reward
        new_exp = user_data.get("exp", 0) + 25
        
        embed = discord.Embed(title="🏆 冒險勝利！", color=discord.Color.gold())
        embed.description = f"你擊敗了 **{dungeon['boss']}**！\n💰 獲得金幣: {reward}\n✨ 獲得經驗: 25"
        ref.update({"coins": new_coins, "exp": new_exp, "hp": hp, "daily_adv_count": daily_count + 1, "active_buff": None})
    else:
        embed = discord.Embed(title="💀 冒險失敗", description="你被打到昏迷，被好心人抬回農場...", color=discord.Color.red())
        ref.update({"hp": 0, "daily_adv_count": daily_count + 1, "active_buff": None})

    await message.channel.send(embed=embed)
