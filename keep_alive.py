# keep_alive.py
from flask import Flask, request
from threading import Thread
import requests, time, os

app = Flask("keep_alive")

# =====================================
# ✅ 基本首頁路由：給 Render / UptimeRobot Ping 用
# =====================================
@app.route("/", methods=["GET", "HEAD"])
def home():
    print(f"[KeepAlive] Ping received: {request.method}")
    return "✅ Carrot Bot is alive!", 200


# =====================================
# ✅ 啟動 Flask 伺服器
# =====================================
def run():
    port = int(os.environ.get("PORT", 10000))  # Render 預設 10000
    app.run(host="0.0.0.0", port=port)


# =====================================
# ✅ 雙重 Ping（Render 外部網址 + 本機）
# =====================================
def keep_alive_loop():
    def do_ping():
        try:
            # Render 公開網址（可在環境變數設定）
            url = (
                os.environ.get("RENDER_EXTERNAL_URL")
                or os.environ.get("RAILWAY_STATIC_URL")
                or os.environ.get("SELF_URL")
                or "https://carrot-bot.onrender.com"
            )
            if not url.startswith("http"):
                url = "https://" + url

            # 🌍 外部 Ping（防止 Render 自動休眠）
            res = requests.get(url, timeout=10)
            print(f"[KeepAlive] External ping → {url} ✅ ({res.status_code})")

            # 💻 本機 Ping（確認 Flask 正常運作）
            local_port = int(os.environ.get("PORT", 10000))
            local_url = f"http://127.0.0.1:{local_port}/"
            res = requests.get(local_url, timeout=5)
            print(f"[KeepAlive] Local ping → {local_url} ✅ ({res.status_code})")

        except Exception as e:
            print(f"[KeepAlive] Ping failed: {e}")

    # 伺服器啟動後先緩 15 秒
    print("[KeepAlive] Waiting 15s before starting pings...")
    time.sleep(15)
    print("[KeepAlive] Starting ping loop...")

    while True:
        do_ping()
        # 每 10 分鐘 ping 一次（Render 休眠閾值是 15 分鐘）
        time.sleep(600)


# =====================================
# ✅ 啟動 Flask + 防休眠線程
# =====================================
def keep_alive():
    Thread(target=run, daemon=True).start()
    Thread(target=keep_alive_loop, daemon=True).start()
