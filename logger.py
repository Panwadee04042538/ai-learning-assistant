# ==========================================
# logger.py
# AI Learning Assistant
#
# Learning Session Logging
#
# 1 Session
#   ↓
# Create Log
#   ↓
# Student Response
#   ↓
# Evaluation
#   ↓
# Update Log
#   ↓
# Adaptive Learning
#   ↓
# Final Status
# ==========================================

import json
import os

from datetime import datetime
from uuid import uuid4


# ==========================================
# Path
# ==========================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

LOG_PATH = os.path.join(
    BASE_DIR,
    "learning_logs.json"
)


# ==========================================
# Load Existing Logs
# ==========================================

def load_logs():
    """
    โหลดข้อมูล Learning Logs
    """

    if not os.path.exists(LOG_PATH):

        return []


    try:

        with open(
            LOG_PATH,
            "r",
            encoding="utf-8"
        ) as file:

            logs = json.load(file)


            # ป้องกันกรณีข้อมูลไม่ใช่ List

            if not isinstance(logs, list):

                return []


            return logs


    except (
        json.JSONDecodeError,
        FileNotFoundError
    ):

        return []


# ==========================================
# Save Logs
# ==========================================

def save_logs(logs):
    """
    บันทึก Learning Logs
    """

    with open(
        LOG_PATH,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(

            logs,

            file,

            ensure_ascii=False,

            indent=2
        )


# ==========================================
# Create Learning Log
# ==========================================

def add_learning_log(

    user_id,
    username,
    user_question,

    ku_id=None,
    ku_title=None,

    lg_id=None,
    lg_name=None,

    qp_id=None,
    question_id=None,

    system_question=None,

    student_id=None
):
    """
    สร้าง Learning Log ใหม่

    Returns
    -------
    dict
        Learning Log ที่สร้างใหม่
    """


    logs = load_logs()


    # --------------------------------------
    # Create Session ID
    # --------------------------------------

    session_id = str(
        uuid4()
    )


    # --------------------------------------
    # Create Log Entry
    # --------------------------------------

    log_entry = {

        # ----------------------------------
        # Session Information
        # ----------------------------------

        "session_id": session_id,

        "timestamp": datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),

        "last_updated": datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),


        # ----------------------------------
        # User Information
        # ----------------------------------

        "user_id": str(user_id),

        "username": username,

        "student_id": student_id,


        # ----------------------------------
        # Initial Question
        # ----------------------------------

        "user_question": user_question,


        # ----------------------------------
        # Knowledge Unit
        # ----------------------------------

        "knowledge_unit": {

            "ku_id": ku_id,

            "title": ku_title
        },


        # ----------------------------------
        # Learning Goal
        # ----------------------------------

        "learning_goal": {

            "lg_id": lg_id,

            "name": lg_name
        },


        # ----------------------------------
        # Questioning Process
        # ----------------------------------

        "questioning_process": {

            "qp_id": qp_id
        },


        # ----------------------------------
        # Selected Question
        # ----------------------------------

        "selected_question": {

            "question_id": question_id,

            "system_question": system_question
        },


        # ----------------------------------
        # Student Learning Responses
        # ----------------------------------

        "student_responses": [],


        # ----------------------------------
        # Learning Progress
        # ----------------------------------

        "attempt_count": 0,

        "final_status": "IN_PROGRESS",

        "final_understanding_level": None

    }


    # --------------------------------------
    # Save
    # --------------------------------------

    logs.append(
        log_entry
    )

    save_logs(
        logs
    )


    return log_entry


# ==========================================
# Find Learning Log
# ==========================================

def find_learning_log(session_id):
    """
    ค้นหา Learning Log จาก session_id
    """

    logs = load_logs()


    for log in logs:

        if log.get("session_id") == session_id:

            return log


    return None


# ==========================================
# Update Learning Log
# ==========================================

def update_learning_log(

    session_id,

    student_answer=None,

    understanding_level=None,

    feedback=None,

    strength=None,

    improvement=None,

    next_action=None,

    attempt=None,

    final_status=None
):
    """
    อัปเดต Learning Log

    ใช้สำหรับบันทึก:

    - คำตอบของผู้เรียน
    - ระดับความเข้าใจ
    - Feedback
    - Attempt
    - Next Action
    - Final Status
    """


    logs = load_logs()


    updated_log = None


    # --------------------------------------
    # Find Session
    # --------------------------------------

    for log in logs:

        if log.get("session_id") != session_id:

            continue


        # ----------------------------------
        # Update Time
        # ----------------------------------

        log["last_updated"] = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )


        # ----------------------------------
        # Student Response
        # ----------------------------------

        if student_answer is not None:

            response_entry = {

                "timestamp": datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),

                "attempt": attempt,

                "answer": student_answer,

                "understanding_level": understanding_level,

                "feedback": feedback,

                "strength": strength,

                "improvement": improvement,

                "next_action": next_action
            }


            # Ensure student_responses exists

            if "student_responses" not in log:

                log["student_responses"] = []


            log["student_responses"].append(
                response_entry
            )


            # ----------------------------------
            # Update Attempt Count
            # ----------------------------------

            if attempt is not None:

                log["attempt_count"] = attempt


        # ----------------------------------
        # Final Status
        # ----------------------------------

        if final_status is not None:

            log["final_status"] = final_status


            # Save final understanding level

            if understanding_level is not None:

                log[
                    "final_understanding_level"
                ] = understanding_level


        updated_log = log

        break


    # --------------------------------------
    # Save Updated Logs
    # --------------------------------------

    if updated_log is not None:

        save_logs(
            logs
        )


    return updated_log


# ==========================================
# Complete Learning Session
# ==========================================

def complete_learning_session(

    session_id,

    final_status,

    final_understanding_level=None
):
    """
    ปิด Learning Session

    Parameters
    ----------

    session_id : str
        Session ที่ต้องการปิด

    final_status : str

        COMPLETED
        MAX_ATTEMPTS_REACHED
        CANCELLED

    final_understanding_level : str

        GOOD
        PARTIAL
        NEEDS_IMPROVEMENT
    """


    logs = load_logs()


    updated_log = None


    for log in logs:

        if log.get("session_id") != session_id:

            continue


        log["last_updated"] = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )


        log["final_status"] = final_status


        log[
            "final_understanding_level"
        ] = final_understanding_level


        updated_log = log

        break


    if updated_log is not None:

        save_logs(
            logs
        )


    return updated_log


# ==========================================
# Session Events (Metacognition / Hint)
# ==========================================

def _append_session_event(session_id, list_key, entry):
    """
    เพิ่มเหตุการณ์ลงในรายการของ Session ที่กำหนด
    ใช้ร่วมกันระหว่างการบันทึกคำตอบ QP และการใช้คำใบ้
    """

    if not session_id:
        return None

    logs = load_logs()
    updated_log = None
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for log in logs:
        if log.get("session_id") != session_id:
            continue

        entry = dict(entry)
        entry["timestamp"] = now
        log.setdefault(list_key, []).append(entry)
        log["last_updated"] = now
        updated_log = log
        break

    if updated_log:
        save_logs(logs)

    return updated_log


def add_metacognitive_response(
    session_id,
    phase,
    question_id=None,
    qp_id=None,
    system_question=None,
    student_answer=None,
    feedback=None
):
    """
    บันทึกคำตอบของผู้เรียนต่อคำถามอภิปัญญา (QP)
    phase: Planning / Monitoring / Evaluation
    ข้อมูลนี้ใช้วิเคราะห์พฤติกรรมอภิปัญญาของผู้เรียนในงานวิจัย
    """

    return _append_session_event(
        session_id,
        "metacognitive_responses",
        {
            "phase": phase,
            "question_id": question_id,
            "qp_id": qp_id,
            "system_question": system_question,
            "student_answer": student_answer,
            "feedback": feedback,
        }
    )


def add_hint_usage(
    session_id,
    hint_question_id,
    hint_level,
    hint_text,
    attempt=None
):
    """
    บันทึกการใช้คำใบ้แบบลำดับขั้น (Scaffolded Hint)
    """

    return _append_session_event(
        session_id,
        "hints_used",
        {
            "hint_question_id": hint_question_id,
            "hint_level": hint_level,
            "hint_text": hint_text,
            "attempt": attempt,
        }
    )


# ==========================================
# Get User Learning Logs
# ==========================================

def get_user_learning_logs(user_id):
    """
    ดึง Learning Logs ของผู้ใช้
    """

    logs = load_logs()


    user_id = str(
        user_id
    )


    return [

        log

        for log in logs

        if log.get("user_id") == user_id
    ]


# ==========================================
# Get Learning Statistics
# ==========================================

def get_learning_statistics():
    """
    สรุปสถิติ Learning Logs

    ใช้สำหรับ Dashboard
    """


    logs = load_logs()


    total_sessions = len(
        logs
    )


    completed_sessions = 0

    max_attempt_sessions = 0

    in_progress_sessions = 0


    good_count = 0

    partial_count = 0

    needs_improvement_count = 0


    for log in logs:

        # ----------------------------------
        # Final Status
        # ----------------------------------

        status = log.get(
            "final_status"
        )


        if status == "COMPLETED":

            completed_sessions += 1


        elif status == "MAX_ATTEMPTS_REACHED":

            max_attempt_sessions += 1


        elif status == "IN_PROGRESS":

            in_progress_sessions += 1


        # ----------------------------------
        # Final Understanding Level
        # ----------------------------------

        level = log.get(
            "final_understanding_level"
        )


        if level == "GOOD":

            good_count += 1


        elif level == "PARTIAL":

            partial_count += 1


        elif level == "NEEDS_IMPROVEMENT":

            needs_improvement_count += 1


    return {

        "total_sessions": total_sessions,

        "completed_sessions": completed_sessions,

        "max_attempt_sessions": (
            max_attempt_sessions
        ),

        "in_progress_sessions": (
            in_progress_sessions
        ),

        "understanding_levels": {

            "GOOD": good_count,

            "PARTIAL": partial_count,

            "NEEDS_IMPROVEMENT": (
                needs_improvement_count
            )
        }
    }