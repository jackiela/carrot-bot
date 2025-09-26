import discord
import random
import os

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
recipes = [
    "胡蘿蔔炒蛋", "胡蘿蔔燉牛肉", "胡蘿蔔排骨湯", "胡蘿蔔燉飯", "胡蘿蔔濃湯",
    "胡蘿蔔燉雞", "胡蘿蔔煎餅", "胡蘿蔔炒飯", "胡蘿蔔蔬菜沙拉", "胡蘿蔔雞肉捲",
    "胡蘿蔔蒸糕", "胡蘿蔔烤餅乾", "胡蘿蔔咖哩", "胡蘿蔔漢堡排", "胡蘿蔔炆豬肉",
    "胡蘿蔔涼拌絲", "胡蘿蔔燴豆腐", "胡蘿蔔煎餃", "胡蘿蔔馬芬蛋糕", "胡蘿蔔奶昔",
    "胡蘿蔔炒青椒", "胡蘿蔔炒花椰菜", "胡蘿蔔滷肉", "胡蘿蔔煎蛋捲", "胡蘿蔔烤雞翅",
    "胡蘿蔔麻糬", "胡蘿蔔蝦仁炒飯", "胡蘿蔔豆漿", "胡蘿蔔燕麥粥", "胡蘿蔔起司焗飯"
]

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

# ===== 小遊戲：拔蘿蔔 =====
carrot_game = [
    "你拔到了一根巨大的金胡蘿蔔！✨",
    "你拔到了一根普通的紅蘿蔔 🍠",
    "你拔到了一根小小的白蘿蔔 🥕",
    "你拔到了一根壞掉的黑蘿蔔 😱",
    "你拔到了一根可愛的迷你胡蘿蔔 🐇"
]

# ===== Bot 指令 =====
@client.event
async def on_ready():
    print(f'已登入為 {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    content = message.content.strip()

    if content == "!運勢":
        fortune = random.choice(list(fortunes.keys()))
        advice = random.choice(fortunes[fortune])
        await message.channel.send(f"🎯 你的今日運勢是：**{fortune}**\n💡 建議：{advice}")

    elif content == "!胡蘿蔔":
        fact = random.choice(carrot_facts)
        await message.channel.send(f"🥕 胡蘿蔔小知識：{fact}")

    elif content == "!食譜":
        recipe = random.choice(recipes)
        await message.channel.send(f"🍴 今日推薦胡蘿蔔料理：{recipe}")

    elif content == "!種植":
        tip = random.choice(carrot_tips)
        await message.channel.send(f"🌱 胡蘿蔔種植小貼士：{tip}")

    elif content == "!拔蘿蔔":
        result = random.choice(carrot_game)
        await message.channel.send(f"💪 {result}")

# ===== 啟動 Bot =====
TOKEN = os.getenv("DISCORD_TOKEN")
client.run(TOKEN)
