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

    # --- 戰鬥準備 (這裡我幫你對齊了) ---
    buff = user_data.get("active_buff")
    current_player_hp = user_data.get("hp", 100) 
    player_atk = 20 + (user_data.get("level", 1) * 5)
    
    enemy_hp = dungeon["hp"]
    enemy_atk = dungeon["atk"]
    
    # 1. 先處理環境扣血
    if dungeon.get("env") == "heat" and buff != "heat_resist":
        current_player_hp -= 10
        await message.channel.send("🔥 **環境傷害**：你因為酷熱流失了 10 點 HP！")

    log_msg = await message.channel.send(f"⚔️ **與 {dungeon['boss']} 展開激戰...**")
    
    # 2. 戰鬥迴圈
    while enemy_hp > 0 and current_player_hp > 0:
        # 怪物打玩家
        dmg_to_player = 0 if buff == "invincible" else random.randint(enemy_atk - 5, enemy_atk + 5)
        current_player_hp -= dmg_to_player
        
        # 玩家打怪物
        dmg_to_enemy = random.randint(player_atk - 5, player_atk + 5)
        enemy_hp -= dmg_to_enemy
        
        # 更新進度
        status_text = (
            f"💥 {dungeon['boss']} 發動攻擊，你受到 {dmg_to_player} 傷害！\n"
            f"🗡️ 你反擊造成 {dmg_to_enemy} 傷害！\n"
            f"❤️ 你的 HP: {max(0, current_player_hp)} | 👾 怪 HP: {max(0, enemy_hp)}"
        )
        await log_msg.edit(content=status_text)
        
        if current_player_hp <= 0: 
            break
        await asyncio.sleep(1.5) 

    # --- 3. 結算結果 ---
    if enemy_hp <= 0:  # 只要怪物 HP 歸零，就算勝利
        reward = random.randint(*dungeon["reward"])
        if buff == "double_gold": 
            reward *= 2
        
        new_coins = user_data.get("coins", 0) + reward
        
        # 如果勝利但 HP 為 0，顯示慘勝
        msg_title = "🏆 **戰鬥勝利！**" if current_player_hp > 0 else "😫 **慘勝！你與怪物同歸於盡...**"
        
        ref.update({
            "coins": new_coins,
            "hp": max(0, current_player_hp),
            "daily_adv_count": daily_count + 1,
            "active_buff": None,
            "last_regen_time": time.time()
        })
        await message.channel.send(f"{msg_title}\n你獲得了 {reward} 金幣！(剩餘 HP: {max(0, current_player_hp)})")
    else:
        # 真正失敗 (玩家倒下且怪還活著)
        ref.update({
            "hp": 0,
            "daily_adv_count": daily_count + 1,
            "active_buff": None,
            "last_regen_time": time.time()
        })
        await message.channel.send(f"💀 **你倒下了...** 被抬回了農場。")
        
