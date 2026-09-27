# ==========================================
# storage/db.py
# AI Learning Assistant
#
# SQLite storage (แทนไฟล์ JSON เดิม) สำหรับ deploy บน Railway
#
# Tables
#   learning_logs    : Learning Session (เดิม learning_logs.json)
#   problem_logs     : ประวัติการรับโจทย์จาก !problem (เดิม data/problem_logs.json)
#   student_registry : Discord user_id -> student_id (เดิม data/student_registry.json)
#
# ตำแหน่งไฟล์: ตัวแปรแวดล้อม DATABASE_PATH
#   (บน Railway ให้ชี้ไปที่ Volume เช่น /data/learning_assistant.db)
#   ถ้าไม่ตั้ง ใช้ data/learning_assistant.db
#
# หมายเหตุ: ไม่ตั้งชื่อแพ็กเกจ database/ เพราะชนกับ database.py เดิม
# ==========================================

import json
import os
import sqlite3
import threading

from contextlib import contextmanager


BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

DEFAULT_DB_PATH = os.path.join(
    BASE_DIR,
    "data",
    "learning_assistant.db"
)

# path ที่ init_db() แล้ว เพื่อไม่ต้องสร้าง table ซ้ำทุกครั้งที่เชื่อมต่อ
_initialized = set()
_init_lock = threading.Lock()


def get_db_path():
    """ตำแหน่งไฟล์ฐานข้อมูล อ่านทุกครั้งเพื่อให้เทสต์เปลี่ยนได้"""

    return os.environ.get("DATABASE_PATH") or DEFAULT_DB_PATH


# ==========================================
# Schema
# ==========================================

SCHEMA = """
CREATE TABLE IF NOT EXISTS learning_logs (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id                TEXT,
    timestamp                 TEXT,
    last_updated              TEXT,
    user_id                   TEXT,
    username                  TEXT,
    student_id                TEXT,
    user_question             TEXT,
    is_learn_session          INTEGER,
    ku_id                     TEXT,
    ku_title                  TEXT,
    lg_id                     TEXT,
    lg_name                   TEXT,
    qp_id                     TEXT,
    question_id               TEXT,
    system_question           TEXT,
    attempt_count             INTEGER,
    final_status              TEXT,
    final_understanding_level TEXT,
    student_responses         TEXT,
    metacognitive_responses   TEXT,
    hints_used                TEXT,
    extra                     TEXT
);
CREATE INDEX IF NOT EXISTS idx_learning_logs_session
    ON learning_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_learning_logs_user
    ON learning_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_learning_logs_student
    ON learning_logs(student_id);

CREATE TABLE IF NOT EXISTS problem_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT,
    user_id     TEXT,
    username    TEXT,
    student_id  TEXT,
    problem_id  TEXT,
    round       INTEGER,
    extra       TEXT
);
CREATE INDEX IF NOT EXISTS idx_problem_logs_user
    ON problem_logs(user_id);

CREATE TABLE IF NOT EXISTS student_registry (
    discord_user_id TEXT PRIMARY KEY,
    student_id      TEXT NOT NULL UNIQUE
);
"""


def init_db(path=None):
    """สร้าง tables ถ้ายังไม่มี (เรียกซ้ำได้)"""

    path = path or get_db_path()

    directory = os.path.dirname(path)

    if directory:
        os.makedirs(directory, exist_ok=True)

    conn = sqlite3.connect(path)

    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)
        conn.commit()

    finally:
        conn.close()

    with _init_lock:
        _initialized.add(path)


@contextmanager
def connect():
    """
    เปิด connection พร้อม transaction: commit เมื่อสำเร็จ, rollback เมื่อ error
    BEGIN IMMEDIATE เพื่อกัน read-modify-write ชนกัน
    """

    path = get_db_path()

    if path not in _initialized:
        init_db(path)

    conn = sqlite3.connect(
        path,
        timeout=30,
        isolation_level=None
    )
    conn.row_factory = sqlite3.Row

    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.execute("COMMIT")

    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise

    finally:
        conn.close()


# ==========================================
# JSON helpers
# ==========================================

def _dumps(value):
    return json.dumps(value, ensure_ascii=False)


def _loads(text, default):
    if text is None:
        return default

    return json.loads(text)


# ==========================================
# learning_logs  (dict <-> row)
# ==========================================

# key ของ log ที่แยกเป็นคอลัมน์ / คอลัมน์ JSON  ที่เหลือเก็บใน extra
_KNOWN_KEYS = {
    "session_id", "timestamp", "last_updated", "user_id", "username",
    "student_id", "user_question", "is_learn_session",
    "knowledge_unit", "learning_goal", "questioning_process",
    "selected_question", "student_responses", "attempt_count",
    "final_status", "final_understanding_level",
    "metacognitive_responses", "hints_used",
}


def _log_to_params(log):
    ku = log.get("knowledge_unit") or {}
    lg = log.get("learning_goal") or {}
    qp = log.get("questioning_process") or {}
    sq = log.get("selected_question") or {}

    is_learn = log.get("is_learn_session")

    extra = {
        k: v for k, v in log.items() if k not in _KNOWN_KEYS
    }

    return {
        "session_id": log.get("session_id"),
        "timestamp": log.get("timestamp"),
        "last_updated": log.get("last_updated"),
        "user_id": log.get("user_id"),
        "username": log.get("username"),
        "student_id": log.get("student_id"),
        "user_question": log.get("user_question"),
        "is_learn_session": None if is_learn is None else int(bool(is_learn)),
        "ku_id": ku.get("ku_id"),
        "ku_title": ku.get("title"),
        "lg_id": lg.get("lg_id"),
        "lg_name": lg.get("name"),
        "qp_id": qp.get("qp_id"),
        "question_id": sq.get("question_id"),
        "system_question": sq.get("system_question"),
        "attempt_count": log.get("attempt_count"),
        "final_status": log.get("final_status"),
        "final_understanding_level": log.get("final_understanding_level"),
        "student_responses": _dumps(log.get("student_responses", [])),
        "metacognitive_responses": (
            _dumps(log["metacognitive_responses"])
            if "metacognitive_responses" in log else None
        ),
        "hints_used": (
            _dumps(log["hints_used"]) if "hints_used" in log else None
        ),
        "extra": _dumps(extra) if extra else None,
    }


def _row_to_log(row):
    log = {
        "session_id": row["session_id"],
        "timestamp": row["timestamp"],
        "last_updated": row["last_updated"],
        "user_id": row["user_id"],
        "username": row["username"],
        "student_id": row["student_id"],
        "user_question": row["user_question"],
        "is_learn_session": (
            None if row["is_learn_session"] is None
            else bool(row["is_learn_session"])
        ),
        "knowledge_unit": {
            "ku_id": row["ku_id"],
            "title": row["ku_title"],
        },
        "learning_goal": {
            "lg_id": row["lg_id"],
            "name": row["lg_name"],
        },
        "questioning_process": {
            "qp_id": row["qp_id"],
        },
        "selected_question": {
            "question_id": row["question_id"],
            "system_question": row["system_question"],
        },
        "student_responses": _loads(row["student_responses"], []),
        "attempt_count": row["attempt_count"] or 0,
        "final_status": row["final_status"],
        "final_understanding_level": row["final_understanding_level"],
    }

    # ฟิลด์ที่มีเฉพาะบาง session
    if row["metacognitive_responses"] is not None:
        log["metacognitive_responses"] = _loads(
            row["metacognitive_responses"], []
        )

    if row["hints_used"] is not None:
        log["hints_used"] = _loads(row["hints_used"], [])

    log.update(_loads(row["extra"], {}))

    return log


_LOG_COLUMNS = [
    "session_id", "timestamp", "last_updated", "user_id", "username",
    "student_id", "user_question", "is_learn_session", "ku_id", "ku_title",
    "lg_id", "lg_name", "qp_id", "question_id", "system_question",
    "attempt_count", "final_status", "final_understanding_level",
    "student_responses", "metacognitive_responses", "hints_used", "extra",
]

_INSERT_LOG = (
    "INSERT INTO learning_logs ({}) VALUES ({})".format(
        ", ".join(_LOG_COLUMNS),
        ", ".join(":" + c for c in _LOG_COLUMNS),
    )
)

_UPDATE_LOG = (
    "UPDATE learning_logs SET {} WHERE id = :_id".format(
        ", ".join("{0} = :{0}".format(c) for c in _LOG_COLUMNS)
    )
)


def list_learning_logs():
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM learning_logs ORDER BY id"
        ).fetchall()

    return [_row_to_log(r) for r in rows]


def insert_learning_log(log):
    with connect() as conn:
        conn.execute(_INSERT_LOG, _log_to_params(log))


def get_learning_log(session_id):
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM learning_logs WHERE session_id = ? "
            "ORDER BY id LIMIT 1",
            (session_id,)
        ).fetchone()

    return _row_to_log(row) if row else None


def modify_learning_log(session_id, mutate):
    """
    โหลด log ของ session_id → mutate(log) แก้ dict ในที่ → บันทึกกลับ
    ทั้งหมดอยู่ใน transaction เดียว

    Returns
    -------
    dict หรือ None ถ้าไม่พบ session
    """

    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM learning_logs WHERE session_id = ? "
            "ORDER BY id LIMIT 1",
            (session_id,)
        ).fetchone()

        if row is None:
            return None

        log = _row_to_log(row)
        mutate(log)

        params = _log_to_params(log)
        params["_id"] = row["id"]
        conn.execute(_UPDATE_LOG, params)

    return log


def replace_all_learning_logs(logs):
    """แทนที่ learning_logs ทั้งตาราง (ใช้ตอน migrate / เทสต์)"""

    with connect() as conn:
        conn.execute("DELETE FROM learning_logs")

        for log in logs:
            conn.execute(_INSERT_LOG, _log_to_params(log))


# ==========================================
# problem_logs
# ==========================================

_PROBLEM_KEYS = {
    "timestamp", "user_id", "username", "student_id", "problem_id", "round"
}


def _problem_params(entry):
    extra = {
        k: v for k, v in entry.items() if k not in _PROBLEM_KEYS
    }

    return (
        entry.get("timestamp"),
        entry.get("user_id"),
        entry.get("username"),
        entry.get("student_id"),
        entry.get("problem_id"),
        entry.get("round"),
        _dumps(extra) if extra else None,
    )


_INSERT_PROBLEM = (
    "INSERT INTO problem_logs "
    "(timestamp, user_id, username, student_id, problem_id, round, extra) "
    "VALUES (?, ?, ?, ?, ?, ?, ?)"
)


def list_problem_logs():
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM problem_logs ORDER BY id"
        ).fetchall()

    result = []

    for row in rows:
        entry = {
            "timestamp": row["timestamp"],
            "user_id": row["user_id"],
            "username": row["username"],
            "student_id": row["student_id"],
            "problem_id": row["problem_id"],
            "round": row["round"],
        }
        entry.update(_loads(row["extra"], {}))
        result.append(entry)

    return result


def insert_problem_log(entry):
    with connect() as conn:
        conn.execute(_INSERT_PROBLEM, _problem_params(entry))


def replace_all_problem_logs(entries):
    with connect() as conn:
        conn.execute("DELETE FROM problem_logs")

        for entry in entries:
            conn.execute(_INSERT_PROBLEM, _problem_params(entry))


# ==========================================
# student_registry
# ==========================================

def load_registry():
    """คืน {discord_user_id: student_id}"""

    with connect() as conn:
        rows = conn.execute(
            "SELECT discord_user_id, student_id FROM student_registry"
        ).fetchall()

    return {r["discord_user_id"]: r["student_id"] for r in rows}


def register(discord_user_id, student_id):
    """
    บันทึกการลงทะเบียน (ผู้ใช้เดิมเปลี่ยนรหัสได้)

    Returns
    -------
    False ถ้า student_id นี้ถูก Discord user_id อื่นใช้แล้ว
    """

    with connect() as conn:
        taken = conn.execute(
            "SELECT 1 FROM student_registry "
            "WHERE student_id = ? AND discord_user_id != ?",
            (student_id, discord_user_id)
        ).fetchone()

        if taken:
            return False

        conn.execute(
            "INSERT INTO student_registry (discord_user_id, student_id) "
            "VALUES (?, ?) "
            "ON CONFLICT(discord_user_id) "
            "DO UPDATE SET student_id = excluded.student_id",
            (discord_user_id, student_id)
        )

    return True


def replace_registry(mapping):
    with connect() as conn:
        conn.execute("DELETE FROM student_registry")

        conn.executemany(
            "INSERT INTO student_registry (discord_user_id, student_id) "
            "VALUES (?, ?)",
            [(str(k), str(v)) for k, v in mapping.items()]
        )
