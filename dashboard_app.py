# ==========================================
# dashboard_app.py
# AI Learning Assistant — Teacher Dashboard (Flask web version)
#
# เว็บแอปสำหรับครู อ่านข้อมูลจากแหล่งเดียวกับ teacher_dashboard.py (CLI
# เดิม) ผ่าน logger.py / services/registry_service.py ตรง ๆ และใช้ฟังก์ชัน
# คำนวณจาก teacher_dashboard.py ซ้ำ (ไม่ได้แก้ไขไฟล์นั้นเลย) เพื่อให้ผลลัพธ์
# ตรงกับคำสั่ง CLI เดิมเสมอ
#
# รัน (จากโฟลเดอร์หลักของโปรเจกต์):
#     python dashboard_app.py
# ==========================================

import csv
import io
import os
from collections import Counter

from flask import Flask, Response, render_template

from logger import load_logs
import teacher_dashboard as td


app = Flask(__name__)

RECENT_LOGS_LIMIT = 10
TOP_LEARN_QUESTIONS_LIMIT = 10


# ==========================================
# Data Helpers
# ==========================================

def _final_status(log):
    """Session ที่ไม่เคยถูกปิดยังไม่มี final_status เลย ถือเป็น IN_PROGRESS"""
    return log.get("final_status") or "IN_PROGRESS"


def _lg_stats(logs):
    counter = Counter()
    names = {}

    for log in logs:
        lg = log.get("learning_goal") or {}
        lg_id = lg.get("lg_id")
        if not lg_id:
            continue
        counter[lg_id] += 1
        if lg.get("name"):
            names[lg_id] = lg.get("name")

    return [
        {"id": lg_id, "name": names.get(lg_id, "-"), "count": count}
        for lg_id, count in counter.most_common()
    ]


def _ku_stats(logs):
    counter = Counter()
    names = {}

    for log in logs:
        ku = log.get("knowledge_unit") or {}
        ku_id = ku.get("ku_id")
        if not ku_id:
            continue
        counter[ku_id] += 1
        if ku.get("title"):
            names[ku_id] = ku.get("title")

    return [
        {"id": ku_id, "name": names.get(ku_id, "-"), "count": count}
        for ku_id, count in counter.most_common()
    ]


def _recent_logs(logs, limit=RECENT_LOGS_LIMIT):
    return sorted(
        logs,
        key=lambda log: log.get("timestamp") or "",
        reverse=True
    )[:limit]


def top_learn_questions(logs, limit=TOP_LEARN_QUESTIONS_LIMIT):
    """
    หัวข้อที่เด็กถามบ่อยผ่าน !learn เรียงจากจำนวนครั้งมากไปน้อย
    ครูใช้ดูว่าเนื้อหาไหนเด็กยังไม่เข้าใจ (ถามซ้ำ ๆ)
    """
    counter = Counter(
        log.get("user_question", "").strip()
        for log in logs
        if log.get("is_learn_session") and log.get("user_question")
    )

    return [
        {"question": question, "count": count}
        for question, count in counter.most_common(limit)
    ]


def build_dashboard_context(logs=None, id_map=None):
    logs = load_logs() if logs is None else logs
    id_map = td.build_student_id_map() if id_map is None else id_map

    status_counter = Counter(_final_status(log) for log in logs)
    understanding_counter = Counter(
        log.get("final_understanding_level") for log in logs
    )

    lg_ids = {
        (log.get("learning_goal") or {}).get("lg_id")
        for log in logs
    }
    lg_ids.discard(None)

    return {
        "total_students": len(id_map),
        "total_sessions": len(logs),
        "total_attempts": sum(
            log.get("attempt_count") or 0 for log in logs
        ),
        "total_lg": len(lg_ids),

        "completed_sessions": status_counter.get("COMPLETED", 0),
        "max_attempt_sessions": status_counter.get(
            "MAX_ATTEMPTS_REACHED", 0
        ),
        "in_progress_sessions": status_counter.get("IN_PROGRESS", 0),

        "good_count": understanding_counter.get("GOOD", 0),
        "partial_count": understanding_counter.get("PARTIAL", 0),
        "needs_improvement_count": understanding_counter.get(
            "NEEDS_IMPROVEMENT", 0
        ),

        "lg_stats": _lg_stats(logs),
        "ku_stats": _ku_stats(logs),
        "recent_logs": _recent_logs(logs),
        "top_learn_questions": top_learn_questions(logs),
    }


# ==========================================
# CSV Export Helpers
# ==========================================

def _csv_download(rows, header, row_to_cells, filename):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    for row in rows:
        writer.writerow(row_to_cells(row))

    # BOM นำหน้า (utf-8-sig) เพื่อให้ Excel เปิดภาษาไทยได้ถูกต้อง
    # เหมือนไฟล์ที่ export_summary_csv/export_at_risk_csv เขียนลงดิสก์
    csv_text = "﻿" + buffer.getvalue()

    return Response(
        csv_text,
        mimetype="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )


def _summary_csv_response(logs, id_map):
    rows = td.compute_student_summaries(logs, id_map)
    return _csv_download(
        rows,
        ["student_id", "total_sessions", "COMPLETED",
         "MAX_ATTEMPTS_REACHED", "CANCELLED", "learning_goals"],
        lambda row: [
            row["student_id"],
            row["total_sessions"],
            row["completed"],
            row["max_attempts_reached"],
            row["cancelled"],
            "; ".join(row["lg_ids"]),
        ],
        "export_summary.csv",
    )


def _at_risk_csv_response(logs, id_map):
    rows = td.find_at_risk_students(logs, id_map)
    return _csv_download(
        rows,
        ["student_id", "reasons", "problem_lg_ids"],
        lambda item: [
            item["student_id"],
            "; ".join(item["reasons"]),
            "; ".join(item["lg_ids"]),
        ],
        "export_at_risk.csv",
    )


# ==========================================
# Routes
# ==========================================

@app.route("/")
def dashboard():
    return render_template("dashboard.html", **build_dashboard_context())


@app.route("/export")
def export_index():
    """หน้ารวมลิงก์ดาวน์โหลด CSV ทั้ง 2 ไฟล์ เหมือนคำสั่ง `export` เดิม"""
    return (
        "<h1>Export</h1>"
        "<ul>"
        '<li><a href="/export/summary.csv">ดาวน์โหลด Summary CSV</a></li>'
        '<li><a href="/export/at-risk.csv">ดาวน์โหลด At-Risk CSV</a></li>'
        "</ul>"
    )


@app.route("/export/summary.csv")
def export_summary():
    logs = load_logs()
    id_map = td.build_student_id_map()
    return _summary_csv_response(logs, id_map)


@app.route("/export/at-risk.csv")
def export_at_risk():
    logs = load_logs()
    id_map = td.build_student_id_map()
    return _at_risk_csv_response(logs, id_map)


if __name__ == "__main__":
    # Railway ส่งพอร์ตมาทาง $PORT และต้อง bind 0.0.0.0
    # debug เปิดได้เฉพาะตอนพัฒนา: FLASK_DEBUG=1
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG") == "1"
    )
