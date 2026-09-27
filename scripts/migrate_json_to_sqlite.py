# ==========================================
# scripts/migrate_json_to_sqlite.py
#
# นำเข้าข้อมูล JSON เดิมเข้า SQLite (รันครั้งเดียวก่อน deploy)
#
#   learning_logs.json          -> learning_logs
#   data/problem_logs.json      -> problem_logs
#   data/student_registry.json  -> student_registry
#
# วิธีใช้:
#   python scripts/migrate_json_to_sqlite.py
#   DATABASE_PATH=/data/learning_assistant.db python scripts/migrate_json_to_sqlite.py
#
# ถ้าตารางปลายทางมีข้อมูลอยู่แล้ว จะข้ามตารางนั้น (กันนำเข้าซ้ำ)
# ใช้ --force เพื่อลบข้อมูลในตารางแล้วนำเข้าใหม่
# ==========================================

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from storage import db  # noqa: E402


LOGS_JSON = os.path.join(ROOT, "learning_logs.json")
PROBLEM_LOGS_JSON = os.path.join(ROOT, "data", "problem_logs.json")
REGISTRY_JSON = os.path.join(ROOT, "data", "student_registry.json")


def _read_json(path, expected_type):
    if not os.path.exists(path):
        print(f"  ไม่พบไฟล์ {path} — ข้าม")
        return None

    with open(path, encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, expected_type):
        print(f"  {path} มีรูปแบบไม่ถูกต้อง — ข้าม")
        return None

    return data


def _count(table):
    with db.connect() as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def _migrate(table, path, expected_type, load_fn, force):
    print(f"[{table}]")

    data = _read_json(path, expected_type)

    if data is None:
        return

    existing = _count(table)

    if existing and not force:
        print(f"  มีข้อมูลอยู่แล้ว {existing} แถว — ข้าม (ใช้ --force เพื่อนำเข้าใหม่)")
        return

    load_fn(data)
    print(f"  นำเข้า {len(data)} รายการ -> ในตาราง {_count(table)} แถว")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    db.init_db()
    print(f"ฐานข้อมูล: {db.get_db_path()}")

    _migrate("learning_logs", LOGS_JSON, list,
             db.replace_all_learning_logs, args.force)
    _migrate("problem_logs", PROBLEM_LOGS_JSON, list,
             db.replace_all_problem_logs, args.force)
    _migrate("student_registry", REGISTRY_JSON, dict,
             db.replace_registry, args.force)

    print("เสร็จสิ้น")


if __name__ == "__main__":
    main()
