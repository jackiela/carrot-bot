# utils_sanitize.py
# ==========================================================
# 使用者資料防呆模組（自動補齊所有必要欄位）
# ==========================================================

def sanitize_user_data(user_data: dict) -> dict:
    """確保 user_data 中的所有欄位存在與格式正確，不會造成 KeyError"""
    if not isinstance(user_data, dict):
        user_data = {}

    # ==========================
    # 🧤 裝備欄位
    # ==========================
    if not isinstance(user_data.get("gloves"), list):
        user_data["gloves"] = []

    # ==========================
    # 🥕 蘿蔔背包（目前未大量使用，但保留）
    # ==========================
    if not isinstance(user_data.get("carrots"), list):
        user_data["carrots"] = []

    if not isinstance(user_data.get("carrot_pulls"), dict):
        user_data["carrot_pulls"] = {}

    # ==========================
    # 💰 金幣
    # ==========================
    if not isinstance(user_data.get("coins"), int):
        user_data["coins"] = 0

    # ==========================
    # 🧪 肥料（補齊三種）
    # ==========================
    fertilizers = user_data.get("fertilizers")
    if not isinstance(fertilizers, dict):
        fertilizers = {}
    user_data["fertilizers"] = {
        "普通肥料": fertilizers.get("普通肥料", 0),
        "高級肥料": fertilizers.get("高級肥料", 0),
        "神奇肥料": fertilizers.get("神奇肥料", 0),
    }

    # ==========================
    # 🌾 農地資料
    # ==========================
    farm = user_data.get("farm")
    if not isinstance(farm, dict):
        farm = {}

    user_data["farm"] = {
        "status": farm.get("status", None),              # planted / None
        "plant_time": farm.get("plant_time"),
        "harvest_time": farm.get("harvest_time"),
        "fertilizer": farm.get("fertilizer"),
        "land_level": farm.get("land_level", 1),
        "pull_count": farm.get("pull_count", 0),
        "thread_id": farm.get("thread_id"),
    }

    return user_data
