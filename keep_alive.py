from flask import Flask, request
from threading import Thread

app = Flask('')

# 支援 GET 與 HEAD，讓 UptimeRobot 免費方案能正常判斷
@app.route("/", methods=["GET", "HEAD"])
def home():
    print(f"Ping received: {request.method}")  # Debug log，方便在 Render Logs 看到
    return "Bot is alive!", 200

def run():
    # Render 會自動提供 PORT 環境變數，預設 fallback 8080
    import os
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()
