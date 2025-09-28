import discord
import random
import os
import json

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# ===== 運勢資料 =====
fortunes = {
    "紅蘿蔔大吉": [
        "今天胡蘿蔔能量滿滿，出門記得微笑！",
        "幸運之神在你身邊，多把握機會。",
        "適合嘗試新事物，會有意外驚喜！",
        "別怕困難，你的胡蘿蔔盾牌很堅固！",
        "今天分享胡蘿蔔，會收穫友誼。",
        "一杯紅蘿蔔汁，為你帶來滿滿元氣！",
        "努力將會開花結果，就像田裡的胡蘿蔔。"
    ],
    "白蘿蔔中吉": [
        "今天適合低調，慢慢耕耘會更好。",
        "謹慎選擇方向，胡蘿蔔會替你照路。",
        "保持耐心，事情會逐漸改善。",
        "適合跟朋友分享你的想法。",
        "今天記得保持微笑，白蘿蔔能量會守護你。",
        "小心花錢，但也別忘了犒賞自己。",
        "保持良好睡眠，白蘿蔔能量幫你充電！"
    ],
    "紫蘿蔔小吉": [
        "今天會遇到小挑戰，別慌，慢慢解決。",
        "不妨吃點胡蘿蔔料理，轉換心情。",
        "朋友可能需要你的幫助，伸出援手吧。",
        "今天適合靜下來思考。",
        "別太在意小失誤，明天會更好。",
        "努力後要記得休息，才有力氣拔蘿蔔！",
        "小心言語，避免不必要的誤會。"
    ],
    "金蘿蔔平吉": [
        "今天一切普通，但胡蘿蔔會帶來驚喜。",
        "別忘了補充能量，一杯果汁剛剛好。",
        "平凡的一天，也可能很幸福。",
        "安安穩穩，其實也是一種福氣。",
        "今天適合規劃未來的小目標。",
        "試著做點家務，生活會更順利。",
        "別小看平凡，這是積蓄力量的時刻。"
    ],
    "黑蘿蔔凶": [
        "今天胡蘿蔔有點萎縮，小心行事。",
        "別太衝動，三思而後行。",
        "避免與人爭吵，容易造成誤會。",
        "今天適合低調，別逞強。",
        "小心花錢，容易有破財風險。",
        "不如多吃點胡蘿蔔，補充正能量！",
        "保持冷靜，困難終會過去。"
    ]
}

# ===== 胡蘿蔔食譜（30 種） =====
recipes = {
    "胡蘿蔔炒蛋": "材料：胡蘿蔔1根、雞蛋2顆、蔥花少許。\n做法：胡蘿蔔切絲快炒，加入打散的蛋液翻炒，最後撒上蔥花即可。",
    "胡蘿蔔燉牛肉": "材料：牛腩500g、胡蘿蔔2根、洋蔥1顆、薑片3片。\n做法：牛肉汆燙去血水，與胡蘿蔔、洋蔥、薑片一起放入鍋中，加水與醬油小火燉2小時。",
    "胡蘿蔔排骨湯": "材料：排骨500g、胡蘿蔔2根、薑片3片、鹽適量。\n做法：排骨汆燙後與胡蘿蔔、薑片一起煮1小時，最後加鹽調味。",
    "胡蘿蔔燉飯": "材料：米2杯、胡蘿蔔1根、洋蔥半顆、雞高湯500ml。\n做法：炒香洋蔥與胡蘿蔔，加入米與高湯，小火燉煮至米粒熟透。",
    "胡蘿蔔濃湯": "材料：胡蘿蔔2根、馬鈴薯1顆、洋蔥半顆、牛奶200ml。\n做法：蔬菜切塊煮軟後打成泥，加入牛奶煮滾即可。",
    "胡蘿蔔燉雞": "材料：雞腿肉500g、胡蘿蔔2根、薑片3片、米酒1大匙。\n做法：雞肉炒香後加入胡蘿蔔與水，小火燉煮40分鐘。",
    "胡蘿蔔煎餅": "材料：胡蘿蔔絲1杯、麵粉半杯、雞蛋1顆、鹽少許。\n做法：混合成糊狀，平底鍋煎至兩面金黃。",
    "胡蘿蔔炒飯": "材料：白飯1碗、胡蘿蔔丁半杯、雞蛋1顆、蔥花少許。\n做法：先炒蛋，再加入胡蘿蔔與白飯拌炒，最後加鹽調味。",
    "胡蘿蔔蔬菜沙拉": "材料：胡蘿蔔絲、黃瓜片、生菜、沙拉醬。\n做法：所有蔬菜拌勻，淋上沙拉醬即可。",
    "胡蘿蔔雞肉捲": "材料：雞胸肉片、胡蘿蔔條、鹽、黑胡椒。\n做法：雞肉片包入胡蘿蔔條，煎熟後切段。",
    "胡蘿蔔蒸糕": "材料：胡蘿蔔泥1杯、低筋麵粉1杯、糖50g、泡打粉1小匙。\n做法：混合後倒入模具，蒸20分鐘。",
    "胡蘿蔔餅乾": "材料：胡蘿蔔泥100g、低筋麵粉200g、奶油100g、糖50g。\n做法：混合成麵糰，壓模後烤15分鐘。",
    "胡蘿蔔咖哩": "材料：胡蘿蔔2根、馬鈴薯1顆、洋蔥1顆、咖哩塊。\n做法：炒香蔬菜後加水煮軟，加入咖哩塊拌勻。",
    "胡蘿蔔漢堡排": "材料：絞肉300g、胡蘿蔔絲半杯、洋蔥末半顆、麵包粉2大匙。\n做法：混合後捏成餅狀，煎熟即可。",
    "胡蘿蔔炆豬肉": "材料：五花肉300g、胡蘿蔔2根、醬油2大匙、冰糖少許。\n做法：炒香五花肉，加入胡蘿蔔與調味料，小火炆煮40分鐘。",
    "胡蘿蔔涼拌絲": "材料：胡蘿蔔絲1杯、蒜末、醋、糖、鹽。\n做法：胡蘿蔔絲燙熟後冰鎮，加入調味料拌勻。",
    "胡蘿蔔燴豆腐": "材料：豆腐1塊、胡蘿蔔絲半杯、蔥花。\n做法：炒香胡蘿蔔，加入豆腐與醬油水燴煮。",
    "胡蘿蔔煎餃": "材料：餃子皮、胡蘿蔔絲、豬絞肉、蔥花。\n做法：包餃子後煎至底部金黃，加水燜熟。",
    "胡蘿蔔馬芬蛋糕": "材料：胡蘿蔔絲1杯、低筋麵粉200g、糖80g、雞蛋2顆、泡打粉1小匙。\n做法：混合後倒入模具，烤20分鐘。",
    "胡蘿蔔奶昔": "材料：胡蘿蔔1根、牛奶200ml、蜂蜜1大匙。\n做法：全部放入果汁機打勻即可。",
    "胡蘿蔔炒青椒": "材料：胡蘿蔔絲、青椒絲、蒜末。\n做法：熱鍋爆香蒜末，加入胡蘿蔔與青椒快炒。",
    "胡蘿蔔炒花椰菜": "材料：胡蘿蔔片、花椰菜小朵、蒜末。\n做法：先炒胡蘿蔔，再加入花椰菜拌炒。",
    "胡蘿蔔滷肉": "材料：絞肉300g、胡蘿蔔丁1杯、醬油2大匙、冰糖少許。\n做法：炒香絞肉，加入胡蘿蔔與調味料，小火滷煮。",
    "胡蘿蔔煎蛋捲": "材料：雞蛋3顆、胡蘿蔔絲半杯、鹽少許。\n做法：蛋液加入胡蘿蔔絲，煎成蛋捲。",
    "胡蘿蔔烤雞翅": "材料：雞翅6隻、胡蘿蔔片、醬油、蜂蜜。\n做法：雞翅醃料後與胡蘿蔔片一起烤20分鐘。",
    "胡蘿蔔麻糬": "材料：糯米粉200g、胡蘿蔔泥100g、糖30g。\n做法：混合後搓成小球，蒸熟即可。",
    "胡蘿蔔蝦仁炒飯": "材料：白飯1碗、胡蘿蔔丁半杯、蝦仁100g、雞蛋1顆。\n做法：先炒蝦仁，再加入胡蘿蔔與白飯拌炒。",
    "胡蘿蔔豆漿": "材料：胡蘿蔔1根、黃豆100g、水500ml。\n做法：黃豆泡水後與胡蘿蔔一起打漿，煮熟即可。",
    "胡蘿蔔燕麥粥": "材料：燕麥片50g、胡蘿蔔絲半杯、水400ml。\n做法：燕麥與胡蘿蔔一起煮至濃稠。",
    "胡蘿蔔起司焗飯": "材料：白飯1碗、胡蘿蔔丁半杯、起司絲100g、奶油少許。\n做法：白飯與胡蘿蔔拌炒後放入烤盤，撒上起司烤至金黃。"
}

# ===== 胡蘿蔔知識 =====
carrot_facts = [
    "胡蘿蔔富含β-胡蘿蔔素，有助於保護視力。",
    "古代人相信胡蘿蔔能帶來好運。",
    "紫色胡蘿蔔在中世紀比橘色胡蘿蔔更常見。",
    "胡蘿蔔其實原本是紫色或白色的，後來才培育出橘色。",
    "吃太多胡蘿蔔，皮膚可能會變成橘色喔！"
]

# ===== 胡蘿蔔種植小貼士 =====
carrot_tips = [
    "胡蘿蔔喜歡疏鬆的土壤，避免石頭阻礙生長。",
    "保持土壤濕潤，但不要積水。",
    "胡蘿蔔需要陽光充足，適合種在日照充足的位置。",
    "適合在春季或秋季播種。",
    "定期間苗，避免胡蘿蔔擠在一起。"
]

# ===== 拔蘿蔔遊戲（60 種，含稀有度） =====
common_carrots = [
    "你拔到了一根普通的紅蘿蔔 🍠",
    "你拔到了一根小小的白蘿蔔 🥕",
    "你拔到了一根壞掉的黑蘿蔔 😱",
    "你拔到了一根可愛的迷你胡蘿蔔 🐇",
    "你拔到了一根搞笑蘿蔔 🤡",
    "你拔到了一根逃跑蘿蔔 🏃‍♂️",
    "你拔到了一根老爺爺蘿蔔 👴",
    "你拔到了一根發霉的蘿蔔 🦠",
    "你拔到了一根彎曲的蘿蔔 🌀",
    "你拔到了一根泥巴蘿蔔 🪱",
    "你拔到了一根半截蘿蔔 ✂️",
    "你拔到了一根空心蘿蔔 🕳️",
    "你拔到了一根皺巴巴蘿蔔 🧻",
    "你拔到了一根發芽蘿蔔 🌱",
    "你拔到了一根乾掉的蘿蔔 ☀️",
    "你拔到了一根笑臉蘿蔔 😀",
    "你拔到了一根哭泣蘿蔔 😭",
    "你拔到了一根打瞌睡的蘿蔔 😴",
    "你拔到了一根打結蘿蔔 🔗",
    "你拔到了一根兩頭蘿蔔 🔀",
    "你拔到了一根長腳蘿蔔 🦵",
    "你拔到了一根長手蘿蔔 ✋",
    "你拔到了一根長耳朵蘿蔔 🐰",
    "你拔到了一根長尾巴蘿蔔 🦊",
    "你拔到了一根長鼻子蘿蔔 🤥",
    "你拔到了一根長眼睛蘿蔔 👀",
    "你拔到了一根長舌頭蘿蔔 👅",
    "你拔到了一根翻滾的蘿蔔 🔄",
    "你拔到了一根卡住的蘿蔔 🪤",
]

rare_carrots = [
    "你拔到了一根會發光的螢光蘿蔔 💡",
    "你拔到了一根會唱歌的音樂蘿蔔 🎶",
    "你拔到了一根彩虹蘿蔔 🌈",
    "你拔到了一根冰雪蘿蔔 ❄️",
    "你拔到了一根火山蘿蔔 🌋",
    "你拔到了一根懸浮蘿蔔 🪄",
    "你拔到了一根武士蘿蔔 ⚔️",
    "你拔到了一根雷神蘿蔔 🔨",
    "你拔到了一根雷電蘿蔔 ⚡",
    "你拔到了一根海洋蘿蔔 🌊",
    "你拔到了一根天使蘿蔔 😇",
    "你拔到了一根惡魔蘿蔔 😈",
    "你拔到了一根機械蘿蔔 🤖",
    "你拔到了一根智慧蘿蔔 🧠",
    "你拔到了一根占卜蘿蔔 🔮",
    "你拔到了一根戀愛蘿蔔 💘",
    "你拔到了一根香氣蘿蔔 🌸",
    "你拔到了一根遊戲蘿蔔 🎮",
    "你拔到了一根火箭蘿蔔 🚀",
    "你拔到了一根變異蘿蔔 🌀",
]

legendary_carrots = [
    "你拔到了一根巨大的金胡蘿蔔！✨",
    "你拔到了一根鑽石蘿蔔 💎",
    "你拔到了一根會噴火的龍蘿蔔 🐉",
    "你拔到了一根王者蘿蔔 👑",
    "你拔到了一根星辰蘿蔔 🌟",
    "你拔到了一根宇宙蘿蔔 🌌",
    "你拔到了一根神聖蘿蔔 🕊️",
    "你拔到了一根幻影蘿蔔 👻",
    "你拔到了一根永恆蘿蔔 ⏳",
    "你拔到了一根幸運蘿蔔 🍀",
]

all_carrots = common_carrots + rare_carrots + legendary_carrots

# ===== JSON 存檔函式 =====
DATA_FILE = "carrot_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ===== 抽卡函式 =====
def pull_carrot():
    roll = random.randint(1, 100)
    if roll <= 70:
        return random.choice(common_carrots)
    elif roll <= 95:
        return random.choice(rare_carrots)
    else:
        return random.choice(legendary_carrots)

# ===== Bot 指令 =====
@client.event
async def on_ready():
    if not hasattr(client, 'already_ready'):
        print(f"✅ 已登入為 {client.user}")
        client.already_ready = True

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    content = message.content.strip()
    user_id = str(message.author.id)
    username = str(message.author.display_name)
    data = load_data()
    
# ===== 指令對應頻道 =====
COMMAND_CHANNELS = {
    "!運勢": 1421065753595084800,       # 運勢頻道 ID
    "!拔蘿蔔": 1421518540598411344,     # 遊戲頻道 ID
    "!蘿蔔圖鑑": 1421518540598411344,   # 同遊戲頻道
    "!蘿蔔排行": 1421518540598411344    # 同遊戲頻道
}

# ===== 頻道限制 =====
if content in COMMAND_CHANNELS:
    allowed_channel = COMMAND_CHANNELS[content]
    if message.channel.id != allowed_channel:
        return   # 頻道不對就忽略   
        
    if content == "!運勢":
        print("DEBUG: 這應該是第一次")   # ✅ 要縮排 4 個空格
        fortune = random.choice(list(fortunes.keys()))
        advice = random.choice(fortunes[fortune])
        await message.channel.send(f"🎯 你的今日運勢是：**{fortune}**\n💡 建議：{advice}")
        return

    elif content == "!胡蘿蔔":
        fact = random.choice(carrot_facts)
        await message.channel.send(f"🥕 胡蘿蔔小知識：{fact}")
        return

    elif content == "!食譜":
        recipe_name = random.choice(list(recipes.keys()))   # 隨機挑一個食譜名稱
        detail = recipes[recipe_name]                       # 取出對應的做法
        await message.channel.send(
            f"🍴 今日推薦胡蘿蔔料理：**{recipe_name}**\n📖 做法：\n{detail}"
        )
        return
   
    elif content == "!種植":
        tip = random.choice(carrot_tips)
        await message.channel.send(f"🌱 胡蘿蔔種植小貼士：{tip}")
        return

    elif content == "!拔蘿蔔":
        result = pull_carrot()
        await message.channel.send(f"💪 {result}")

        if user_id not in data:
            data[user_id] = {"name": username, "carrots": []}
        if result not in data[user_id]["carrots"]:
            data[user_id]["carrots"].append(result)
            await message.channel.send("📖 新發現！你的圖鑑新增了一種蘿蔔！")

        save_data(data)
        return

    elif content == "!蘿蔔圖鑑":
        if user_id not in data or not data[user_id]["carrots"]:
            await message.channel.send("📖 你的圖鑑還是空的，快去拔蘿蔔吧！")
            return

        collected = data[user_id]["carrots"]
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
        return

    elif content == "!蘿蔔排行":
        if not data:
            await message.channel.send("📊 目前還沒有任何玩家收集蘿蔔！")
            return

        ranking = sorted(
            data.items(),
            key=lambda x: len(x[1]["carrots"]),
            reverse=True
        )

        reply = "🏆 蘿蔔收集排行榜 🥕\n"
        for i, (uid, info) in enumerate(ranking[:5], start=1):
            count = len(info["carrots"])
            reply += f"{i}. {info['name']} — {count}/{len(all_carrots)} 種\n"

        await message.channel.send(reply)
        return

# ===== 啟動 Bot =====
from keep_alive import keep_alive   # ← 確保有這行
keep_alive()                        # ← 啟動 Flask 假伺服器

TOKEN = os.getenv("DISCORD_TOKEN")
client.run(TOKEN)
