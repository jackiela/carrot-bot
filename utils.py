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
