from flask import Flask, request
from threading import Thread
import requests, time, os

app = Flask('')

# =====================================
# ✅ 基本路由：Render / Railway / UptimeRobot 都能監測
# =====================================
@app.route("/", methods=["GET", "HEAD"])
def home():
    print(f"[KeepAlive] Ping received: {request.method}")
    return "✅ Carrot Bot is alive!", 200


# =====================================
# ✅ 啟動 Flask（Render/Railway 通用）
# =====================================
def run():
    port = int(os.environ.get("PORT", 10000))  # Render 會自動設 PORT=10000
    app.run(host="0.0.0.0", port=port)


# =====================================
# ✅ 定時 Ping 公開網址（防止 Render/Railway 休眠）
# ✅ 並且自 ping 內部 Flask 服務（確認仍在運作）
# =====================================
def keep_alive_loop():
    while True:
        try:
            # 優先使用 Render / Railway 的外部網址
            url = (
                os.environ.get("RENDER_EXTERNAL_URL")
                or os.environ.get("RAILWAY_STATIC_URL")
                or os.environ.get("SELF_URL")  # 可自定義環境變數
                or "https://carrot-bot.onrender.com"  # 預設網址
            )

            # 確保有加上 https://
            if not url.startswith("http"):
                url = "https://" + url

            # 🔹 1️⃣ ping 公開網址
            requests.get(url, timeout=5)
            print(f"[KeepAlive] Pinged {url} ✅")

            # 🔹 2️⃣ ping 本機 Flask（確認內部服務沒掛）
            local_port = int(os.environ.get("PORT", 10000))
            requests.get(f"http://127.0.0.1:{local_port}/", timeout=5)
            print(f"[KeepAlive] Local ping 127.0.0.1:{local_port} ✅")

        except Exception as e:
            print(f"[KeepAlive] Failed: {e}")

        # 每 10 分鐘 ping 一次（600 秒）
        time.sleep(600)


# =====================================
# ✅ 同時啟動 Flask + 防休眠循環
# =====================================
def keep_alive():
    Thread(target=run, daemon=True).start()
    Thread(target=keep_alive_loop, daemon=True).start()
