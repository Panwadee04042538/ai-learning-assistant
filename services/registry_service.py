# ==========================================
# registry_service.py
# AI Learning Assistant
#
# Student Registry
#
# ผูก Discord user_id เข้ากับรหัสนักเรียน (student_id)
# เก็บเป็น mapping {discord_user_id: student_id} ใน
# data/student_registry.json
# ==========================================

import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

REGISTRY_PATH = os.path.join(
    PROJECT_ROOT,
    "data",
    "student_registry.json"
)


# ==========================================
# Load / Save Registry
# ==========================================

def _load_registry():
    """โหลด mapping {discord_user_id: student_id} จากไฟล์"""

    if not os.path.exists(REGISTRY_PATH):
        return {}

    try:
        with open(
            REGISTRY_PATH,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        if not isinstance(data, dict):
            return {}

        return data

    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def _save_registry(registry):
    """บันทึก mapping ลงไฟล์ สร้างโฟลเดอร์ data/ ให้ถ้ายังไม่มี"""

    os.makedirs(
        os.path.dirname(REGISTRY_PATH),
        exist_ok=True
    )

    with open(
        REGISTRY_PATH,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            registry,
            file,
            ensure_ascii=False,
            indent=2
        )


# ==========================================
# Public API
# ==========================================

def get_student_id(discord_user_id):
    """
    คืนรหัสนักเรียนที่ผูกกับ Discord user_id นี้

    Returns
    -------
    str หรือ None ถ้า user_id นี้ยังไม่ได้ลงทะเบียน
    """

    registry = _load_registry()

    return registry.get(str(discord_user_id))


def is_registered(discord_user_id):
    """True ถ้า Discord user_id นี้ลงทะเบียนไว้แล้ว"""

    return get_student_id(discord_user_id) is not None


def get_all_students():
    """
    คืน mapping ทั้งหมด {discord_user_id: student_id} ที่ลงทะเบียนไว้

    ใช้โดย teacher_dashboard.py เพื่อดูภาพรวมผู้เรียนที่ลงทะเบียนแล้ว
    """

    return dict(_load_registry())


def register_student(discord_user_id, student_id):
    """
    ลงทะเบียน (หรือเปลี่ยนรหัสนักเรียนของ user เดิม)

    Returns
    -------
    True  : ลงทะเบียน/เปลี่ยนรหัสสำเร็จ
    False : รหัสนักเรียนนี้ถูก Discord user_id อื่นลงทะเบียนไปแล้ว
    """

    discord_user_id = str(discord_user_id)
    student_id = str(student_id).strip()

    registry = _load_registry()

    for existing_user_id, existing_student_id in registry.items():

        if (
            existing_student_id == student_id
            and existing_user_id != discord_user_id
        ):
            return False

    registry[discord_user_id] = student_id
    _save_registry(registry)

    return True
