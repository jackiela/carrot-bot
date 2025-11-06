from flask import Flask, request
from threading import Thread
import requests, time, os

app = Flask('')

# =====================================
# ✅ 基本首頁路由：Render/UptimeRobot 監測
# =====================================
@app.route("/", methods=["GET", "HEAD"])
def home():
    print(f"[KeepAlive] Ping received: {request.method}")
    return "✅ Carrot Bot is alive!", 200


# =====================================
# ✅ 啟動 Flask（Render / Railway 通用）
# =====================================
def run():
    port = int(os.environ.get("PORT", 10000))  # Render 預設是 10000
    app.run(host="0.0.0.0", port=port)


# =====================================
# ✅ 雙重 Ping（外部網址 + 本機網址）
# =====================================
def keep_alive_loop():
    def do_ping():
        try:
            # 公開網址（Render / Railway）
            url = (
                os.environ.get("RENDER_EXTERNAL_URL")
                or os.environ.get("RAILWAY_STATIC_URL")
                or os.environ.get("SELF_URL")
                or "https://carrot-bot.onrender.com"
            )

            if not url.startswith("http"):
                url = "https://" + url

            # 🌍 外部 Ping（防止 Render 睡眠）
            requests.get(url, timeout=5)
            print(f"[KeepAlive] Pinged {url} ✅")

            # 💻 本機 Ping（確認伺服器運作正常）
            local_port = int(os.environ.get("PORT", 10000))
            local_url = f"http://127.0.0.1:{local_port}/"
            requests.get(local_url, timeout=5)
            print(f"[KeepAlive] Local ping {local_url} ✅")

        except Exception as e:
            print(f"[KeepAlive] Failed: {e}")

    # ⚡ 第一次啟動立即 Ping 一次
    print("[KeepAlive] Performing initial ping...")
    do_ping()

    # ⏱ 每 10 分鐘執行一次
    while True:
        time.sleep(600)
        do_ping()


# =====================================
# ✅ 啟動 Flask + 防休眠線程
# =====================================
def keep_alive():
    Thread(target=run, daemon=True).start()
    Thread(target=keep_alive_loop, daemon=True).start()
