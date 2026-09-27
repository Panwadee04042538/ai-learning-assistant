# ==========================================
# problem_service.py
# AI Learning Assistant
#
# Problem Bank (คลังปัญหา)
#
# โหลดโจทย์ PBL จาก data/problem_bank.json และช่วยจัดรูปแบบ
# ข้อความสำหรับส่งใน Discord
# ==========================================

import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

PROBLEM_BANK_PATH = os.path.join(
    PROJECT_ROOT,
    "data",
    "problem_bank.json"
)


# ==========================================
# Load Problem Bank
# ==========================================

def _load_problems():
    """โหลดรายการโจทย์ทั้งหมดจากไฟล์"""

    if not os.path.exists(PROBLEM_BANK_PATH):
        return []

    try:
        with open(
            PROBLEM_BANK_PATH,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        if not isinstance(data, list):
            return []

        return data

    except (json.JSONDecodeError, FileNotFoundError):
        return []


# ==========================================
# Public API
# ==========================================

def get_problem(problem_id):
    """
    คืนโจทย์ที่ตรงกับรหัสที่ระบุ

    Parameters
    ----------
    problem_id : str
        รหัสโจทย์ เช่น "P01" (ไม่สนตัวพิมพ์เล็ก/ใหญ่)

    Returns
    -------
    dict หรือ None ถ้าไม่พบโจทย์รหัสนี้
    """

    if not problem_id:
        return None

    target_id = str(problem_id).strip().upper()

    for problem in _load_problems():

        if str(problem.get("id", "")).strip().upper() == target_id:
            return problem

    return None


def get_problems_by_round(round_number):
    """
    คืนรายการโจทย์ทั้งหมดในรอบที่ระบุ

    Returns
    -------
    list[dict]
    """

    try:
        target_round = int(round_number)
    except (TypeError, ValueError):
        return []

    return [
        problem
        for problem in _load_problems()
        if problem.get("round") == target_round
    ]


def format_problem_message(problem):
    """
    จัดรูปแบบโจทย์ให้พร้อมส่งใน Discord (markdown + emoji)

    ไม่แสดงส่วน Process ให้ผู้เรียนเห็น (แม้ข้อมูลนี้จะยังอยู่ใน problem
    object ตามเดิม เพื่อให้ระบบประเมิน Algorithm ใช้ได้) เพราะ Process
    คือคำตอบของขั้นตอนที่ผู้เรียนต้องคิดเอง ผู้เรียนเห็นแค่สถานการณ์/
    Input/Output/โครงสร้าง Algorithm

    สำหรับโจทย์รอบ 4 (มี buggy_algorithm) จะแสดง Algorithm
    ที่มีจุดผิดให้ผู้เรียนตรวจสอบด้วย โดยไม่เฉลย bug_type/
    bug_location เพราะผู้เรียนต้องหาจุดผิดด้วยตนเอง
    """

    if not problem:
        return "❌ ไม่พบข้อมูลโจทย์"

    problem_id = problem.get("id", "-")
    title = problem.get("title", "-")
    situation = problem.get("situation", "-")
    input_text = problem.get("input", "-")
    output_text = problem.get("output", "-")
    structure = problem.get("structure", "-")

    message = (
        f"## 📘 {problem_id} — {title}\n\n"
        "### 📖 สถานการณ์\n"
        f"{situation}\n\n"
        "### 📥 Input\n"
        f"{input_text}\n\n"
        "### 📤 Output\n"
        f"{output_text}\n\n"
        "### 🧩 โครงสร้างอัลกอริทึม (Algorithm)\n"
        f"{structure}"
    )

    buggy_algorithm = problem.get("buggy_algorithm")

    if buggy_algorithm:
        message += (
            "\n\n### 🐞 อัลกอริทึม (Algorithm) ที่ต้องตรวจสอบ\n"
            f"```\n{buggy_algorithm}\n```\n"
            "ลองตรวจสอบว่าอัลกอริทึม (Algorithm) นี้มีจุดผิดตรงไหน "
            "แล้วเสนอวิธีแก้ไข"
        )

    return message
