from flask import Flask, request
from threading import Thread
import requests, time, os

app = Flask('')

# 支援 GET 與 HEAD，讓 Render / Railway / UptimeRobot 能正常監測
@app.route("/", methods=["GET", "HEAD"])
def home():
    print(f"[KeepAlive] Ping received: {request.method}")
    return "✅ Carrot Bot is alive!", 200

# =====================================
# ✅ 啟動 Flask（Render/Railway 通用）
# =====================================
def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# =====================================
# ✅ 定時 Ping 公開網址（防休眠）
# =====================================
def keep_alive_loop():
    while True:
        try:
            # 優先使用 Render / Railway 的公網網址環境變數
            url = os.environ.get("RENDER_EXTERNAL_URL") or os.environ.get("RAILWAY_STATIC_URL")

            # 沒有設定時，預設你的 Render 專案網址（請改成你的實際網址）
            if not url:
                url = "https://carrot-bot.onrender.com"

            # 確保有加上 https://
            if not url.startswith("http"):
                url = "https://" + url

            requests.get(f"{url}/api/ping", timeout=5)
            print(f"[KeepAlive] Pinged {url} ✅")
        except Exception as e:
            print(f"[KeepAlive] Ping failed: {e}")

        # 每 10 分鐘 ping 一次
        time.sleep(600)

# =====================================
# ✅ 同時啟動 Flask + 防休眠循環
# =====================================
def keep_alive():
    Thread(target=run, daemon=True).start()
    Thread(target=keep_alive_loop, daemon=True).start()
