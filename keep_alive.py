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

            # 改成 ping "/"，因為你沒有 /api/ping 這條路由
            requests.get(url, timeout=5)
            print(f"[KeepAlive] Pinged {url} ✅")
        except Exception as e:
            print(f"[KeepAlive] Ping failed: {e}")

        # 每 10 分鐘 ping 一次（600 秒）
        time.sleep(600)


# =====================================
# ✅ 同時啟動 Flask + 防休眠循環
# =====================================
def keep_alive():
    Thread(target=run, daemon=True).start()
    Thread(target=keep_alive_loop, daemon=True).start()
