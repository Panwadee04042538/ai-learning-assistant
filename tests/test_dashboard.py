"""
ทดสอบ teacher_dashboard.py (Backlog #14)

เทสต์ด้วยข้อมูล mock ที่สร้างขึ้นเอง ไม่ใช่การอ่านไฟล์ learning_logs.json /
data/problem_logs.json / data/student_registry.json จริง เพราะฟังก์ชัน
คำนวณหลัก (compute_*, find_*) รับ logs / id_map เป็นพารามิเตอร์ตรง ๆ
ส่วน CLI (main) เท่านั้นที่โหลดไฟล์จริงผ่าน logger.py / registry_service.py

วิธีรัน (จากโฟลเดอร์หลักของโปรเจกต์):
    python -m unittest tests.test_dashboard -v
"""

import csv
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault("TYPHOON_API_KEY", "test")
os.environ.setdefault("GEMINI_API_KEY", "test")
os.environ.setdefault("DISCORD_TOKEN", "test")

import teacher_dashboard as td  # noqa: E402


def log(
    user_id,
    lg_id=None,
    lg_name="",
    final_status=None,
    final_understanding_level=None,
    timestamp="2026-01-01 00:00:00",
    student_id=None,
    student_responses=None,
    hints_used=None,
    metacognitive_responses=None,
):
    return {
        "session_id": f"session-{user_id}-{timestamp}",
        "timestamp": timestamp,
        "user_id": str(user_id),
        "username": f"user{user_id}",
        "student_id": student_id,
        "learning_goal": {"lg_id": lg_id, "name": lg_name} if lg_id else {},
        "final_status": final_status,
        "final_understanding_level": final_understanding_level,
        "student_responses": student_responses or [],
        "hints_used": hints_used or [],
        "metacognitive_responses": metacognitive_responses or [],
    }


class SummaryTest(unittest.TestCase):

    def test_empty_logs_prints_no_data_message(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            td.print_summary([], {})

        self.assertIn(td.NO_DATA_MESSAGE, buf.getvalue())

    def test_counts_registered_students_and_sessions(self):
        logs = [
            log("1", lg_id="LG01", final_status="COMPLETED"),
            log("1", lg_id="LG01", final_status="MAX_ATTEMPTS_REACHED"),
            log("2", lg_id="LG02", final_status="COMPLETED"),
        ]
        id_map = {"1": "S-001", "2": "S-002"}

        data = td.compute_summary(logs, id_map)

        self.assertEqual(data["total_students"], 2)
        self.assertEqual(data["total_sessions"], 3)
        self.assertEqual(data["status_counter"]["COMPLETED"], 2)
        self.assertEqual(data["status_counter"]["MAX_ATTEMPTS_REACHED"], 1)

    def test_top_3_learning_goals(self):
        logs = (
            [log("1", lg_id="LG01")] * 5
            + [log("1", lg_id="LG02")] * 3
            + [log("1", lg_id="LG03")] * 2
            + [log("1", lg_id="LG04")] * 1
        )

        data = td.compute_summary(logs, {})

        top_ids = [lg_id for lg_id, _ in data["top_lgs"]]
        self.assertEqual(top_ids, ["LG01", "LG02", "LG03"])

    def test_missing_final_status_counted_as_unknown(self):
        logs = [log("1", lg_id="LG01", final_status=None)]

        data = td.compute_summary(logs, {})

        self.assertEqual(data["status_counter"]["UNKNOWN"], 1)


class AtRiskTest(unittest.TestCase):

    def test_no_logs_and_no_registry_prints_no_data_message(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            td.print_at_risk([], {})

        self.assertIn(td.NO_DATA_MESSAGE, buf.getvalue())

    def test_flags_two_consecutive_max_attempts(self):
        logs = [
            log("1", lg_id="LG01", final_status="MAX_ATTEMPTS_REACHED",
                timestamp="2026-01-01 10:00:00"),
            log("1", lg_id="LG02", final_status="MAX_ATTEMPTS_REACHED",
                timestamp="2026-01-01 11:00:00"),
        ]

        at_risk = td.find_at_risk_students(logs, {"1": "S-001"})

        self.assertEqual(len(at_risk), 1)
        self.assertEqual(at_risk[0]["student_id"], "S-001")
        self.assertTrue(
            any("ติดต่อกัน" in r for r in at_risk[0]["reasons"])
        )
        self.assertEqual(at_risk[0]["lg_ids"], ["LG01", "LG02"])

    def test_single_max_attempts_not_flagged_by_that_rule(self):
        logs = [
            log("1", lg_id="LG01", final_status="MAX_ATTEMPTS_REACHED"),
            log("1", lg_id="LG01", final_status="COMPLETED",
                timestamp="2026-01-01 12:00:00"),
        ]

        at_risk = td.find_at_risk_students(logs, {"1": "S-001"})

        self.assertEqual(at_risk, [])

    def test_flags_over_50_percent_hint_level_3_usage(self):
        logs = [
            log(
                "1", lg_id="LG05",
                student_responses=[{"attempt": 1}, {"attempt": 2}],
                hints_used=[
                    {"hint_level": 3}, {"hint_level": 3}, {"hint_level": 1}
                ],
            ),
        ]

        at_risk = td.find_at_risk_students(logs, {"1": "S-001"})

        self.assertEqual(len(at_risk), 1)
        self.assertTrue(
            any("คำใบ้ระดับ 3" in r for r in at_risk[0]["reasons"])
        )
        self.assertEqual(at_risk[0]["lg_ids"], ["LG05"])

    def test_50_percent_exactly_is_not_flagged(self):
        logs = [
            log(
                "1", lg_id="LG05",
                student_responses=[{"attempt": 1}, {"attempt": 2}],
                hints_used=[{"hint_level": 3}],
            ),
        ]

        at_risk = td.find_at_risk_students(logs, {"1": "S-001"})

        self.assertEqual(at_risk, [])

    def test_flags_registered_student_with_no_sessions(self):
        id_map = {"1": "S-001", "2": "S-002"}
        logs = [log("1", lg_id="LG01", final_status="COMPLETED")]

        at_risk = td.find_at_risk_students(logs, id_map)

        self.assertEqual(len(at_risk), 1)
        self.assertEqual(at_risk[0]["student_id"], "S-002")
        self.assertIn(
            "ยังไม่มี session เลยทั้งที่ลงทะเบียนแล้ว", at_risk[0]["reasons"]
        )

    def test_no_matches_prints_friendly_message_not_no_data(self):
        logs = [log("1", lg_id="LG01", final_status="COMPLETED")]
        buf = io.StringIO()
        with redirect_stdout(buf):
            td.print_at_risk(logs, {"1": "S-001"})

        output = buf.getvalue()
        self.assertNotIn(td.NO_DATA_MESSAGE, output)
        self.assertIn("ไม่พบผู้เรียนที่ต้องช่วยเหลือ", output)


class StudentDetailTest(unittest.TestCase):

    def test_unknown_student_prints_no_data_message(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            td.print_student_detail("S-GHOST", [], [], {})

        self.assertIn(td.NO_DATA_MESSAGE, buf.getvalue())

    def test_finds_logs_via_registry_mapping(self):
        logs = [log("1", lg_id="LG01", final_status="COMPLETED")]
        id_map = {"1": "S-001"}

        matched = td.find_logs_for_student("S-001", logs, id_map)

        self.assertEqual(len(matched), 1)

    def test_finds_logs_via_direct_student_id_field(self):
        logs = [log("1", lg_id="LG01", student_id="S-999")]

        matched = td.find_logs_for_student("S-999", logs, {})

        self.assertEqual(len(matched), 1)

    def test_prints_session_history_metacognitive_qa_and_problems(self):
        logs = [
            log(
                "1", lg_id="LG01", lg_name="Algorithm พื้นฐาน",
                final_status="COMPLETED",
                final_understanding_level="GOOD",
                metacognitive_responses=[{
                    "phase": "Evaluation",
                    "system_question": "Algorithm คืออะไร?",
                    "student_answer": "ลำดับขั้นตอนการแก้ปัญหา",
                    "feedback": "ตอบได้ตรงประเด็น",
                }],
            ),
        ]
        problem_logs = [
            {"student_id": "S-001", "problem_id": "P01", "round": 1,
             "timestamp": "2026-01-01 09:00:00"},
        ]
        id_map = {"1": "S-001"}

        buf = io.StringIO()
        with redirect_stdout(buf):
            td.print_student_detail("S-001", logs, problem_logs, id_map)

        output = buf.getvalue()
        self.assertIn("LG01", output)
        self.assertIn("Evaluation", output)
        self.assertIn("Algorithm คืออะไร?", output)
        self.assertIn("ลำดับขั้นตอนการแก้ปัญหา", output)
        self.assertIn("P01", output)


class ExportCsvTest(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_export_summary_csv_has_expected_columns_and_rows(self):
        logs = [
            log("1", lg_id="LG01", final_status="COMPLETED"),
            log("1", lg_id="LG02", final_status="MAX_ATTEMPTS_REACHED"),
            log("2", lg_id="LG01", final_status="CANCELLED"),
        ]
        id_map = {"1": "S-001", "2": "S-002"}
        path = os.path.join(self.tmpdir, "summary.csv")

        rows = td.export_summary_csv(logs, id_map, path)

        self.assertEqual(len(rows), 2)

        with open(path, encoding="utf-8-sig", newline="") as f:
            csv_rows = list(csv.DictReader(f))

        self.assertEqual(len(csv_rows), 2)
        row_by_id = {r["student_id"]: r for r in csv_rows}

        self.assertEqual(row_by_id["S-001"]["total_sessions"], "2")
        self.assertEqual(row_by_id["S-001"]["COMPLETED"], "1")
        self.assertEqual(row_by_id["S-001"]["MAX_ATTEMPTS_REACHED"], "1")
        self.assertEqual(row_by_id["S-001"]["learning_goals"], "LG01; LG02")

        self.assertEqual(row_by_id["S-002"]["CANCELLED"], "1")

    def test_export_at_risk_csv_writes_reasons(self):
        logs = [
            log("1", lg_id="LG01", final_status="MAX_ATTEMPTS_REACHED",
                timestamp="2026-01-01 10:00:00"),
            log("1", lg_id="LG01", final_status="MAX_ATTEMPTS_REACHED",
                timestamp="2026-01-01 11:00:00"),
        ]
        id_map = {"1": "S-001"}
        path = os.path.join(self.tmpdir, "at_risk.csv")

        rows = td.export_at_risk_csv(logs, id_map, path)

        self.assertEqual(len(rows), 1)

        with open(path, encoding="utf-8-sig", newline="") as f:
            csv_rows = list(csv.DictReader(f))

        self.assertEqual(len(csv_rows), 1)
        self.assertEqual(csv_rows[0]["student_id"], "S-001")
        self.assertIn("ติดต่อกัน", csv_rows[0]["reasons"])
        self.assertEqual(csv_rows[0]["problem_lg_ids"], "LG01")

    def test_export_with_empty_logs_still_writes_header_only(self):
        path = os.path.join(self.tmpdir, "empty.csv")

        rows = td.export_summary_csv([], {}, path)

        self.assertEqual(rows, [])
        with open(path, encoding="utf-8-sig", newline="") as f:
            csv_rows = list(csv.DictReader(f))
        self.assertEqual(csv_rows, [])


if __name__ == "__main__":
    unittest.main()
