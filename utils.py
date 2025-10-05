# utils.py

ADMIN_IDS = ["657882539331158016"]  # ← 換成你自己的 ID

def is_admin(user_id: str) -> bool:
    return str(user_id) in ADMIN_IDS
