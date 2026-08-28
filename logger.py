import os
import json
from datetime import datetime

LOG_DIR = "logs"

# สร้างโฟลเดอร์ถ้ายังไม่มี
os.makedirs(LOG_DIR, exist_ok=True)


def save_log(user_id, username, topic, result):

    filepath = os.path.join(LOG_DIR, f"{user_id}.json")

    # ถ้ามีไฟล์อยู่แล้ว
    if os.path.exists(filepath):

        with open(filepath, "r", encoding="utf-8") as f:
            logs = json.load(f)

    else:

        logs = []

    log = {
        "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "username": username,
        "topic": topic,
        "questions": result["questions"],
        "answers": result["answers"]
    }

    logs.append(log)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(
            logs,
            f,
            ensure_ascii=False,
            indent=4
        )