# ==========================================
# registry_service.py
# AI Learning Assistant
#
# Student Registry
#
# ผูก Discord user_id เข้ากับรหัสนักเรียน (student_id)
# เก็บเป็น mapping {discord_user_id: student_id} ใน
# ตาราง student_registry ใน SQLite
# ==========================================

from storage import db


# ==========================================
# Load / Save Registry (SQLite)
# ==========================================

def _load_registry():
    """โหลด mapping {discord_user_id: student_id} จากฐานข้อมูล"""

    return db.load_registry()


def _save_registry(registry):
    """แทนที่ mapping ทั้งหมดในฐานข้อมูล"""

    db.replace_registry(registry)


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

    return db.register(discord_user_id, student_id)
