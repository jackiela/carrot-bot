from flask import Flask, request
from threading import Thread
from datetime import datetime, timedelta, timezone
import os

app = Flask('')
tz_taiwan = timezone(timedelta(hours=8))
ping_count = 0
last_log_time = None  # 記錄上次 log 時間


@app.route("/", methods=["GET", "HEAD"])
def home():
    global ping_count, last_log_time
    ping_count += 1
    now = datetime.now(tz_taiwan)
    
    # ✅ 只在第一 ping 或相隔超過 30 分鐘時印出
    if ping_count == 1 or not last_log_time or (now - last_log_time).seconds > 1800:
        print(f"[KEEPALIVE] {now.strftime('%Y-%m-%d %H:%M:%S')} - Ping received ({ping_count})")
        last_log_time = now

    return "Bot is alive!", 200


def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


def keep_alive():
    t = Thread(target=run)
    t.start()
