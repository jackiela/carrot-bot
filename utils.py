import datetime
import discord
from pytz import timezone
from carrot_data import common_carrots, rare_carrots, legendary_carrots, all_carrots
from fortune_data import fortunes

# ✅ 台灣時區物件（共用）
tz_taipei = timezone("Asia/Taipei")

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
    return datetime.datetime.now(tz_taipei).date().isoformat()

def get_now() -> datetime.datetime:
    """取得台灣當地時間（datetime 物件）"""
    return datetime.datetime.now(tz_taipei)

def parse_datetime(iso_str: str) -> datetime.datetime:
    """解析 ISO 字串為 datetime，並轉換為台灣時區"""
    dt = datetime.datetime.fromisoformat(iso_str)
    return dt.astimezone(tz_taipei)

def get_remaining_time_str(target: datetime.datetime) -> str:
    """回傳人類友善的倒數格式（還剩 X 小時 Y 分鐘）"""
    now = get_now()
    target = target.astimezone(tz_taipei)
    delta = target - now
    total_seconds = int(delta.total_seconds())

    if total_seconds <= 0:
        return "✅ 已可執行"

    hours, remainder = divmod(total_seconds, 3600)
    minutes = remainder // 60

    parts = []
    if hours > 0:
        parts.append(f"{hours} 小時")
    if minutes > 0:
        parts.append(f"{minutes} 分鐘")

    return "還剩 " + " ".join(parts)

def get_remaining_hours(target: datetime.datetime) -> int:
    """回傳剩餘小時數（可用於條件判斷）"""
    now = get_now()
    target = target.astimezone(tz_taipei)
    delta = target - now
    total_seconds = int(delta.total_seconds())
    return max(0, total_seconds // 3600)

def get_carrot_thumbnail(result: str) -> str:
    """根據蘿蔔種類回傳 GitHub Pages 上的縮圖網址"""
    base_url = "https://jackiela.github.io/carrot-bot/images"

    if result in common_carrots:
        return f"{base_url}/common.png"  # 普通蘿蔔
    elif result in rare_carrots:
        return f"{base_url}/rare.png"    # 稀有蘿蔔
    elif result in legendary_carrots:
        return f"{base_url}/legendary.png"  # 傳說蘿蔔
    else:
        return f"{base_url}/default.png"  # 預設：未知或種植提示

def get_carrot_rarity_color(result: str) -> discord.Color:
    """根據拔蘿蔔稀有度回傳 Embed 顏色"""
    if result in legendary_carrots:
        return discord.Color.gold()
    elif result in rare_carrots:
        return discord.Color.purple()
    elif result in common_carrots:
        return discord.Color.dark_gray()
    else:
        return discord.Color.light_gray()

def get_fortune_thumbnail(fortune: str) -> str:
    """根據運勢回傳對應符咒縮圖網址"""
    if "大吉" in fortune:
        return "https://i.imgur.com/9ZxJv3M.png"  # 金色符咒風格
    elif "中吉" in fortune:
        return "https://i.imgur.com/8wKXQ9E.png"  # 綠色符咒風格
    elif "小吉" in fortune:
        return "https://i.imgur.com/7gU7ZyE.png"  # 藍色符咒風格
    else:
        return "https://i.imgur.com/6zFvKkL.png"  # 紅色符咒或厄運風格
