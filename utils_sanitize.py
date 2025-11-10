# utils_sanitize.py
# ==========================================================
# ✅ 使用者資料防呆模組（確保資料欄位格式正確）
# ==========================================================

def sanitize_user_data(user_data: dict) -> dict:
    """確保 user_data 中的關鍵欄位型態正確"""
    if not isinstance(user_data, dict):
        user_data = {}

    if not isinstance(user_data.get("gloves", []), list):
        user_data["gloves"] = []

    if not isinstance(user_data.get("carrots", []), list):
        user_data["carrots"] = []

    if not isinstance(user_data.get("carrot_pulls", {}), dict):
        user_data["carrot_pulls"] = {}

    if not isinstance(user_data.get("farm", {}), dict):
        user_data["farm"] = {"land_level": 1, "status": "idle"}

    if not isinstance(user_data.get("coins", 0), int):
        user_data["coins"] = 0

    if not isinstance(user_data.get("fertilizers", {}), dict):
        user_data["fertilizers"] = {}

    return user_data
