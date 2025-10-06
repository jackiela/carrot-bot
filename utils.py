# utils.py

import datetime
from pytz import timezone

ADMIN_IDS = ["657882539331158016"]  # ← RIDDLE 的 Discord ID

def is_admin(user_id: str) -> bool:
    return str(user_id) in ADMIN_IDS

# ✅ 管理員 ID 清單（可加入多位）
ADMIN_IDS = [
    "657882539331158016",  # ← RIDDLE 的 Discord ID
    # "其他管理員 ID 可加在這裡"
]

def is_admin(user_id: str) -> bool:
    """判斷是否為管理員"""
    return str(user_id) in ADMIN_IDS

def get_today() -> str:
    """取得台灣當地日期（字串格式 YYYY-MM-DD）"""
    taiwan = timezone("Asia/Taipei")
    return datetime.datetime.now(taiwan).date().isoformat()

def get_now() -> datetime.datetime:
    """取得台灣當地時間（datetime 物件）"""
    taiwan = timezone("Asia/Taipei")
    return datetime.datetime.now(taiwan)

def get_remaining_hours(target_time: datetime.datetime) -> str:
    """計算距離目標時間還有幾小時幾分鐘"""
    now = get_now()
    remaining = target_time - now

    if remaining.total_seconds() <= 0:
        return "✅ 已可執行"

    hours, remainder = divmod(remaining.total_seconds(), 3600)
    minutes = remainder // 60
    return f"還剩 {int(hours)} 小時 {int(minutes)} 分鐘"

def get_carrot_thumbnail(result: str) -> str:
    if result in common_carrots:
        return "https://i.imgur.com/0yKXQ9E.png"  # 普通蘿蔔
    elif result in rare_carrots:
        return "https://i.imgur.com/1gU7ZyE.png"  # 稀有蘿蔔
    elif result in legendary_carrots:
        return "https://i.imgur.com/3zFvKkL.png"  # 傳說蘿蔔
    else:
        return "https://i.imgur.com/4gTqYvE.png"  # 預設：未知或種植提示

def get_fortune_thumbnail(fortune: str) -> str:
    if "大吉" in fortune:
        return "https://i.imgur.com/9ZxJv3M.png"  # 金色符咒風格
    elif "中吉" in fortune:
        return "https://i.imgur.com/8wKXQ9E.png"  # 綠色符咒風格
    elif "小吉" in fortune:
        return "https://i.imgur.com/7gU7ZyE.png"  # 藍色符咒風格
    else:
        return "https://i.imgur.com/6zFvKkL.png"  # 紅色符咒或厄運風格
