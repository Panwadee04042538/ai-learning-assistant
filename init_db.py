import sqlite3
import os

# ==========================
# สร้างโฟลเดอร์ database
# ==========================

os.makedirs("database", exist_ok=True)

DB_PATH = "database/learning.db"

conn = sqlite3.connect(DB_PATH)

cursor = conn.cursor()

# ==========================
# ตารางผู้ใช้งาน
# ==========================

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    discord_id TEXT UNIQUE NOT NULL,

    username TEXT NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

)
""")

# ==========================
# ตาราง Session
# ==========================

cursor.execute("""
CREATE TABLE IF NOT EXISTS sessions (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    user_id INTEGER NOT NULL,

    topic TEXT NOT NULL,

    phase TEXT NOT NULL,

    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    end_time TIMESTAMP,

    status TEXT DEFAULT 'IN_PROGRESS',

    FOREIGN KEY(user_id) REFERENCES users(id)

)
""")

# ==========================
# ตารางคำถาม-คำตอบ
# ==========================

cursor.execute("""
CREATE TABLE IF NOT EXISTS responses (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    session_id INTEGER NOT NULL,

    question_no INTEGER,

    question TEXT,

    answer TEXT,

    response_time REAL,

    FOREIGN KEY(session_id) REFERENCES sessions(id)

)
""")

# ==========================
# ตาราง Feedback
# ==========================

cursor.execute("""
CREATE TABLE IF NOT EXISTS feedback (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    session_id INTEGER NOT NULL,

    feedback TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(session_id) REFERENCES sessions(id)

)
""")

# ==========================
# บันทึกข้อมูล
# ==========================

conn.commit()

conn.close()

print("===================================")
print("✅ Database Created Successfully")
print(f"📂 {DB_PATH}")
print("===================================")