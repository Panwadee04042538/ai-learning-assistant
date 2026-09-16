"""
teacher_dashboard.py — Teacher Dashboard (Backlog #14)

Command-line tool ที่ครูรันแยกต่างหาก ไม่ใช่ส่วนหนึ่งของบอต
อ่านข้อมูลจาก learning_logs.json / data/problem_logs.json /
data/student_registry.json (ผ่าน logger.py และ services/*.py เดิม
เพื่อให้ path ตรงกับที่บอทใช้จริงเสมอ)

วิธีใช้ (รันจากโฟลเดอร์หลักของโปรเจกต์):
    python teacher_dashboard.py summary
    python teacher_dashboard.py at-risk
    python teacher_dashboard.py student <student_id>
    python teacher_dashboard.py export
"""

import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

import argparse
import csv
from collections import Counter, defaultdict

from logger import load_logs, load_problem_logs
from services.registry_service import get_all_students


NO_DATA_MESSAGE = "ยังไม่มีข้อมูล"

HINT_LEVEL_3_VALUES = {3, "3", "Level 3"}

SUMMARY_CSV_PATH = "export_summary.csv"
AT_RISK_CSV_PATH = "export_at_risk.csv"


# ==================================================
# Data Helpers
# ==================================================

def build_student_id_map():
    """{discord_user_id(str): student_id} เฉพาะผู้ที่ลงทะเบียนแล้ว"""
    return {str(k): v for k, v in get_all_students().items()}


def group_logs_by_user(logs):
    grouped = defaultdict(list)
    for log in logs:
        grouped[str(log.get("user_id"))].append(log)
    return grouped


def display_id(user_id, id_map):
    """student_id ถ้าลงทะเบียนแล้ว ไม่งั้นแสดง user_id ดิบพร้อม label"""
    student_id = id_map.get(str(user_id))
    return student_id if student_id else f"(ยังไม่ผูก student_id) user:{user_id}"


def lg_id_of(log):
    return (log.get("learning_goal") or {}).get("lg_id")


# ==================================================
# 1) Class Summary
# ==================================================

def compute_summary(logs, id_map):
    status_counter = Counter(
        (log.get("final_status") or "UNKNOWN") for log in logs
    )

    lg_counter = Counter()
    for log in logs:
        lg_id = lg_id_of(log)
        if lg_id:
            lg_counter[lg_id] += 1

    return {
        "total_students": len(id_map),
        "total_sessions": len(logs),
        "status_counter": status_counter,
        "top_lgs": lg_counter.most_common(3),
    }


def print_summary(logs, id_map):
    print("=== ภาพรวมชั้นเรียน ===")
    print(f"ผู้เรียนที่ลงทะเบียนแล้ว: {len(id_map)} คน")

    if not logs:
        print(NO_DATA_MESSAGE)
        return

    data = compute_summary(logs, id_map)
    total = data["total_sessions"]

    print(f"จำนวน session ทั้งหมด: {total}")
    print()
    print("สัดส่วนสถานะ session:")
    for status, count in data["status_counter"].most_common():
        pct = (count / total * 100) if total else 0
        print(f"  - {status}: {count} ({pct:.1f}%)")

    print()
    print("Learning Goal ที่ถูกฝึกบ่อยที่สุด (Top 3):")
    if not data["top_lgs"]:
        print(f"  {NO_DATA_MESSAGE}")
    else:
        for rank, (lg_id, count) in enumerate(data["top_lgs"], start=1):
            print(f"  {rank}. {lg_id}: {count} ครั้ง")


# ==================================================
# 2) At-Risk Students
# ==================================================

def has_consecutive_max_attempts(sorted_logs, min_streak=2):
    streak = 0
    best = 0
    for log in sorted_logs:
        if log.get("final_status") == "MAX_ATTEMPTS_REACHED":
            streak += 1
            best = max(best, streak)
        else:
            streak = 0
    return best >= min_streak


def hint_level_3_ratio(user_logs):
    total_attempts = 0
    hint3_count = 0

    for log in user_logs:
        total_attempts += len(log.get("student_responses") or [])
        for hint in (log.get("hints_used") or []):
            if hint.get("hint_level") in HINT_LEVEL_3_VALUES:
                hint3_count += 1

    if total_attempts == 0:
        return 0.0

    return hint3_count / total_attempts


def find_at_risk_students(logs, id_map):
    grouped = group_logs_by_user(logs)
    at_risk = []

    for user_id, user_logs in grouped.items():
        sorted_logs = sorted(user_logs, key=lambda l: l.get("timestamp") or "")
        reasons = []
        problem_lgs = set()

        if has_consecutive_max_attempts(sorted_logs):
            reasons.append("MAX_ATTEMPTS_REACHED ติดต่อกัน 2 session ขึ้นไป")
            for log in sorted_logs:
                if log.get("final_status") == "MAX_ATTEMPTS_REACHED":
                    lg_id = lg_id_of(log)
                    if lg_id:
                        problem_lgs.add(lg_id)

        ratio = hint_level_3_ratio(sorted_logs)
        if ratio > 0.5:
            reasons.append(f"ใช้คำใบ้ระดับ 3 เกิน 50% ของการตอบทั้งหมด ({ratio * 100:.0f}%)")
            for log in sorted_logs:
                lg_id = lg_id_of(log)
                if lg_id:
                    problem_lgs.add(lg_id)

        if reasons:
            at_risk.append({
                "student_id": display_id(user_id, id_map),
                "reasons": reasons,
                "lg_ids": sorted(problem_lgs),
            })

    # ลงทะเบียนแล้วแต่ยังไม่มี session เลย
    users_with_sessions = set(grouped.keys())
    for user_id, student_id in id_map.items():
        if user_id not in users_with_sessions:
            at_risk.append({
                "student_id": student_id,
                "reasons": ["ยังไม่มี session เลยทั้งที่ลงทะเบียนแล้ว"],
                "lg_ids": [],
            })

    return at_risk


def print_at_risk(logs, id_map):
    if not logs and not id_map:
        print(NO_DATA_MESSAGE)
        return

    print("=== ผู้เรียนที่ต้องช่วย (At-Risk) ===")

    at_risk = find_at_risk_students(logs, id_map)

    if not at_risk:
        print("ไม่พบผู้เรียนที่ต้องช่วยเหลือเป็นพิเศษในขณะนี้")
        return

    for item in at_risk:
        print(f"- {item['student_id']}")
        for reason in item["reasons"]:
            print(f"    เหตุผล: {reason}")
        if item["lg_ids"]:
            print(f"    LG ที่มีปัญหา: {', '.join(item['lg_ids'])}")


# ==================================================
# 3) Student Detail
# ==================================================

def find_logs_for_student(student_id, logs, id_map):
    reverse_map = {v: k for k, v in id_map.items()}
    target_user_id = reverse_map.get(student_id)

    matched = []
    for log in logs:
        if log.get("student_id") == student_id:
            matched.append(log)
        elif target_user_id and str(log.get("user_id")) == target_user_id:
            matched.append(log)

    return matched


def find_problem_logs_for_student(student_id, problem_logs, id_map):
    reverse_map = {v: k for k, v in id_map.items()}
    target_user_id = reverse_map.get(student_id)

    matched = []
    for entry in problem_logs:
        if entry.get("student_id") == student_id:
            matched.append(entry)
        elif target_user_id and str(entry.get("user_id")) == target_user_id:
            matched.append(entry)

    return matched


def print_student_detail(student_id, logs, problem_logs, id_map):
    print(f"=== รายละเอียดผู้เรียน: {student_id} ===")

    student_logs = find_logs_for_student(student_id, logs, id_map)
    student_problem_logs = find_problem_logs_for_student(
        student_id, problem_logs, id_map
    )

    if not student_logs and not student_problem_logs:
        print(NO_DATA_MESSAGE)
        return

    sorted_logs = sorted(student_logs, key=lambda l: l.get("timestamp") or "")

    print("\n-- ประวัติ session --")
    if not sorted_logs:
        print(f"  {NO_DATA_MESSAGE}")
    else:
        for log in sorted_logs:
            lg = log.get("learning_goal") or {}
            phases = sorted({
                m.get("phase")
                for m in (log.get("metacognitive_responses") or [])
                if m.get("phase")
            })
            print(
                f"  [{log.get('timestamp', '-')}] "
                f"LG: {lg.get('lg_id', '-')} ({lg.get('name', '-')}) "
                f"| Phase: {', '.join(phases) if phases else '-'} "
                f"| สถานะ: {log.get('final_status') or 'IN_PROGRESS'} "
                f"| ระดับความเข้าใจล่าสุด: {log.get('final_understanding_level') or '-'}"
            )

    print("\n-- คำถามอภิปัญญาที่ตอบ --")
    meta_found = False
    for log in sorted_logs:
        lg = log.get("learning_goal") or {}
        for m in (log.get("metacognitive_responses") or []):
            meta_found = True
            print(f"  [{lg.get('lg_id', '-')}] คำถาม: {m.get('system_question', '-')}")
            print(f"    คำตอบ: {m.get('student_answer', '-')}")
            print(
                "    ระดับความเข้าใจของ session นี้: "
                f"{log.get('final_understanding_level') or '-'}"
            )
    if not meta_found:
        print(f"  {NO_DATA_MESSAGE}")

    print("\n-- โจทย์ที่ได้รับ --")
    if not student_problem_logs:
        print(f"  {NO_DATA_MESSAGE}")
    else:
        for entry in sorted(
            student_problem_logs, key=lambda p: p.get("timestamp") or ""
        ):
            print(
                f"  [{entry.get('timestamp', '-')}] "
                f"โจทย์ {entry.get('problem_id', '-')} "
                f"(รอบ {entry.get('round', '-')})"
            )


# ==================================================
# 4) Export CSV
# ==================================================

def compute_student_summaries(logs, id_map):
    grouped = group_logs_by_user(logs)
    all_user_ids = set(grouped.keys()) | set(id_map.keys())

    rows = []
    for user_id in sorted(all_user_ids):
        user_logs = grouped.get(user_id, [])
        status_counter = Counter(log.get("final_status") for log in user_logs)
        lg_ids = sorted({
            lg_id_of(log) for log in user_logs if lg_id_of(log)
        })

        rows.append({
            "student_id": display_id(user_id, id_map),
            "total_sessions": len(user_logs),
            "completed": status_counter.get("COMPLETED", 0),
            "max_attempts_reached": status_counter.get("MAX_ATTEMPTS_REACHED", 0),
            "cancelled": status_counter.get("CANCELLED", 0),
            "lg_ids": lg_ids,
        })

    return rows


def export_summary_csv(logs, id_map, path=SUMMARY_CSV_PATH):
    rows = compute_student_summaries(logs, id_map)

    with open(path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow([
            "student_id", "total_sessions", "COMPLETED",
            "MAX_ATTEMPTS_REACHED", "CANCELLED", "learning_goals"
        ])
        for row in rows:
            writer.writerow([
                row["student_id"],
                row["total_sessions"],
                row["completed"],
                row["max_attempts_reached"],
                row["cancelled"],
                "; ".join(row["lg_ids"]),
            ])

    return rows


def export_at_risk_csv(logs, id_map, path=AT_RISK_CSV_PATH):
    at_risk = find_at_risk_students(logs, id_map)

    with open(path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(["student_id", "reasons", "problem_lg_ids"])
        for item in at_risk:
            writer.writerow([
                item["student_id"],
                "; ".join(item["reasons"]),
                "; ".join(item["lg_ids"]),
            ])

    return at_risk


def run_export(logs, id_map):
    summary_rows = export_summary_csv(logs, id_map)
    at_risk_rows = export_at_risk_csv(logs, id_map)

    print(f"บันทึก {SUMMARY_CSV_PATH} แล้ว ({len(summary_rows)} แถว)")
    print(f"บันทึก {AT_RISK_CSV_PATH} แล้ว ({len(at_risk_rows)} แถว)")


# ==================================================
# CLI Entry Point
# ==================================================

def build_arg_parser():
    parser = argparse.ArgumentParser(
        prog="teacher_dashboard.py",
        description="Teacher Dashboard: ดูข้อมูลการเรียนของผู้เรียน (รันแยกจากบอต)"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("summary", help="ภาพรวมชั้นเรียน")
    subparsers.add_parser("at-risk", help="รายชื่อผู้เรียนที่ต้องช่วย")

    student_parser = subparsers.add_parser(
        "student", help="รายละเอียดผู้เรียนรายคน"
    )
    student_parser.add_argument("student_id")

    subparsers.add_parser("export", help="ส่งออกข้อมูลเป็น CSV")

    return parser


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    logs = load_logs()
    id_map = build_student_id_map()

    if args.command == "summary":
        print_summary(logs, id_map)

    elif args.command == "at-risk":
        print_at_risk(logs, id_map)

    elif args.command == "student":
        problem_logs = load_problem_logs()
        print_student_detail(args.student_id, logs, problem_logs, id_map)

    elif args.command == "export":
        run_export(logs, id_map)


if __name__ == "__main__":
    main()
