# Deploy บน Railway

รันทั้งหมดใน **service เดียว** ผ่าน [start.sh](start.sh) (ดู [Procfile](Procfile))

- `python dashboard_app.py &` : Teacher Dashboard (Flask, ฟังพอร์ต `$PORT`) รันเบื้องหลัง
- `exec python main.py` : Discord bot เป็นโปรเซสหลัก ถ้า bot จบ container จะจบและ Railway restart ให้

ข้อมูลทั้งหมดเก็บใน SQLite ไฟล์เดียว (`DATABASE_PATH`) ซึ่งอยู่ใน Volume ของ service นี้
(Volume ใช้ร่วมกันข้าม service ไม่ได้ จึงต้องรวมเป็น service เดียว)
ถ้า dashboard จบเอง bot ยังทำงานต่อ แต่ dashboard จะไม่ถูก restart จนกว่าจะ redeploy

## 1. เตรียม repo

1. ตรวจว่า `.gitignore` กันไฟล์ข้อมูลและ secret ไว้แล้ว
   (`learning_logs.json`, `data/*.json` ที่เป็นข้อมูลผู้เรียน, `*.db`, `.env`)
2. `.env`, `learning_logs.json` และ `database/learning.db` ถูกลบออกจากประวัติ git
   ทั้งหมดแล้ว (`git filter-repo`) และไม่ถูก track อีก (อยู่ใน `.gitignore`)
   ถ้าเคยแชร์ไฟล์เหล่านี้ไปทางอื่น (zip/backup) ให้เปลี่ยน token/API key ทั้งหมด
3. Push ขึ้น GitHub แล้วสร้าง Project ใน Railway → *Deploy from GitHub repo*

## 2. Mount Volume

1. เปิด service → **Settings → Volumes → New Volume**
   (หรือ `Ctrl+K` / Command Palette → "Create Volume")
2. Mount path: `/data`
3. Redeploy หลังเพิ่ม Volume

ถ้าไม่ mount Volume ไฟล์ SQLite จะหายทุกครั้งที่ deploy ใหม่

## 3. ตั้ง Environment Variables

Service → **Variables**

| ชื่อ | ค่า |
|---|---|
| `DATABASE_PATH` | `/data/learning_assistant.db` |
| `DISCORD_TOKEN` | token ของ Discord bot |
| `TYPHOON_API_KEY` | API key ของ Typhoon |
| `DEBUG_MODE` | `False` |
| `GEMINI_API_KEY` | (ถ้าใช้ `gemini_service.py`) |

`PORT` Railway ตั้งให้เอง ไม่ต้องกำหนด

## 4. รัน migration ครั้งแรก

สคริปต์ [scripts/migrate_json_to_sqlite.py](scripts/migrate_json_to_sqlite.py)
อ่าน `learning_logs.json`, `data/problem_logs.json`, `data/student_registry.json`
แล้วนำเข้า SQLite (ตารางที่มีข้อมูลอยู่แล้วจะถูกข้าม ใช้ `--force` เพื่อนำเข้าใหม่)

เพราะไฟล์ JSON ถูก `.gitignore` จึงไม่อยู่บน Railway
วิธีที่แนะนำ: **migrate ในเครื่อง แล้วนำไฟล์ `.db` ขึ้น Volume**

```
# 1) ในเครื่อง: สร้างไฟล์ .db จาก JSON
set DATABASE_PATH=migrated.db          (PowerShell: $env:DATABASE_PATH="migrated.db")
python scripts/migrate_json_to_sqlite.py

# 2) อัปโหลด migrated.db ไปที่ /data/learning_assistant.db บน Railway
#    เช่นผ่าน Railway CLI:  railway ssh   แล้วส่งไฟล์เข้าไป
#    (ตรวจวิธีอัปโหลดไฟล์เข้า Volume ล่าสุดในเอกสาร Railway)
```

ถ้าไม่ต้องการข้อมูลเก่า ข้ามขั้นนี้ได้ ตารางจะถูกสร้างอัตโนมัติเมื่อ bot เริ่มทำงาน

ตรวจผล:
```
railway ssh
python -c "from logger import load_logs; print(len(load_logs()))"
```

## 5. ตรวจสอบหลัง deploy

- Logs ของ worker ไม่มี error `DISCORD_TOKEN` / `TYPHOON_API_KEY`
- bot ตอบใน Discord และ `!register` ทำงาน
- เปิด public domain ของ web แล้วเห็น dashboard
- Redeploy หนึ่งครั้ง แล้วข้อมูลยังอยู่ (ยืนยันว่า Volume ทำงาน)

## รันในเครื่อง

```
pip install -r requirements.txt
python main.py             # bot
python dashboard_app.py    # dashboard ที่ http://localhost:5000
python -m pytest tests -q
```
ถ้าไม่ตั้ง `DATABASE_PATH` จะใช้ `data/learning_assistant.db`
