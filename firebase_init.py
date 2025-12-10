import firebase_admin
from firebase_admin import credentials, db
import os

# 初始化 Firebase（避免重複初始化）
def init_firebase():
    if not firebase_admin._apps:
        cred_path = os.path.join(os.getcwd(), "firebase_key.json")
        cred = credentials.Certificate(cred_path)

        firebase_admin.initialize_app(cred, {
            "databaseURL": "https://carrotbot-80059-default-rtdb.asia-southeast1.firebasedatabase.app"
        })

# 獲取某個玩家資料路徑
def get_user_ref(user_id: str):
    init_firebase()
    return db.reference(f"/users/{user_id}")

# 獲取全部玩家資料
def get_all_users_ref():
    init_firebase()
    return db.reference("/users")
