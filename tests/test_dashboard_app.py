"""
ทดสอบ dashboard_app.py (Flask web version ของ Teacher Dashboard)

ไม่แตะ teacher_dashboard.py เดิม — dashboard_app.py ต้องเรียกใช้ฟังก์ชัน
คำนวณจากไฟล์นั้นซ้ำ (compute_student_summaries, find_at_risk_students,
build_student_id_map) เพื่อให้ผลลัพธ์ตรงกับคำสั่ง CLI เดิมเสมอ

วิธีรัน (จากโฟลเดอร์หลักของโปรเจกต์):
    python -m unittest tests.test_dashboard_app -v
"""

import csv
import io
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault("TYPHOON_API_KEY", "test")
os.environ.setdefault("GEMINI_API_KEY", "test")
os.environ.setdefault("DISCORD_TOKEN", "test")

import logger  # noqa: E402
import dashboard_app  # noqa: E402
import services.registry_service as registry_service  # noqa: E402


def log(
    user_id,
    lg_id=None,
    lg_name="",
    ku_id=None,
    ku_title="",
    final_status=None,
    final_understanding_level=None,
    attempt_count=0,
    user_question="",
    is_learn_session=False,
    timestamp="2026-01-01 00:00:00",
    username=None,
):
    return {
        "session_id": f"session-{user_id}-{timestamp}",
        "timestamp": timestamp,
        "user_id": str(user_id),
        "username": username or f"user{user_id}",
        "user_question": user_question,
        "is_learn_session": is_learn_session,
        "knowledge_unit": {"ku_id": ku_id, "title": ku_title} if ku_id else {},
        "learning_goal": {"lg_id": lg_id, "name": lg_name} if lg_id else {},
        "final_status": final_status,
        "final_understanding_level": final_understanding_level,
        "attempt_count": attempt_count,
    }


class DashboardContextTest(unittest.TestCase):
    """ทดสอบฟังก์ชันคำนวณ context ล้วน ๆ ไม่ต้องพึ่ง Flask request"""

    def test_empty_logs_gives_zeroed_context(self):
        ctx = dashboard_app.build_dashboard_context(logs=[], id_map={})

        self.assertEqual(ctx["total_students"], 0)
        self.assertEqual(ctx["total_sessions"], 0)
        self.assertEqual(ctx["total_attempts"], 0)
        self.assertEqual(ctx["total_lg"], 0)
        self.assertEqual(ctx["completed_sessions"], 0)
        self.assertEqual(ctx["max_attempt_sessions"], 0)
        self.assertEqual(ctx["in_progress_sessions"], 0)
        self.assertEqual(ctx["good_count"], 0)
        self.assertEqual(ctx["partial_count"], 0)
        self.assertEqual(ctx["needs_improvement_count"], 0)
        self.assertEqual(ctx["lg_stats"], [])
        self.assertEqual(ctx["ku_stats"], [])
        self.assertEqual(ctx["recent_logs"], [])
        self.assertEqual(ctx["top_learn_questions"], [])

    def test_counts_students_sessions_and_attempts(self):
        logs = [
            log("1", final_status="COMPLETED", attempt_count=2),
            log("1", final_status="MAX_ATTEMPTS_REACHED", attempt_count=3),
            log("2", final_status="COMPLETED", attempt_count=1),
        ]
        id_map = {"1": "S-001", "2": "S-002"}

        ctx = dashboard_app.build_dashboard_context(logs=logs, id_map=id_map)

        self.assertEqual(ctx["total_students"], 2)
        self.assertEqual(ctx["total_sessions"], 3)
        self.assertEqual(ctx["total_attempts"], 6)

    def test_session_status_breakdown(self):
        logs = [
            log("1", final_status="COMPLETED"),
            log("1", final_status="COMPLETED"),
            log("1", final_status="MAX_ATTEMPTS_REACHED"),
            log("1", final_status=None),  # ยังไม่มี final_status -> IN_PROGRESS
        ]

        ctx = dashboard_app.build_dashboard_context(logs=logs, id_map={})

        self.assertEqual(ctx["completed_sessions"], 2)
        self.assertEqual(ctx["max_attempt_sessions"], 1)
        self.assertEqual(ctx["in_progress_sessions"], 1)

    def test_understanding_level_breakdown(self):
        logs = [
            log("1", final_understanding_level="GOOD"),
            log("1", final_understanding_level="GOOD"),
            log("1", final_understanding_level="PARTIAL"),
            log("1", final_understanding_level="NEEDS_IMPROVEMENT"),
        ]

        ctx = dashboard_app.build_dashboard_context(logs=logs, id_map={})

        self.assertEqual(ctx["good_count"], 2)
        self.assertEqual(ctx["partial_count"], 1)
        self.assertEqual(ctx["needs_improvement_count"], 1)

    def test_lg_and_ku_stats_counted_and_sorted_desc(self):
        logs = (
            [log("1", lg_id="LG01", lg_name="Algorithm พื้นฐาน",
                  ku_id="KU01", ku_title="ความหมาย Algorithm")] * 3
            + [log("1", lg_id="LG02", lg_name="วิเคราะห์ปัญหา",
                    ku_id="KU02", ku_title="การวิเคราะห์")] * 1
        )

        ctx = dashboard_app.build_dashboard_context(logs=logs, id_map={})

        self.assertEqual(
            ctx["lg_stats"],
            [
                {"id": "LG01", "name": "Algorithm พื้นฐาน", "count": 3},
                {"id": "LG02", "name": "วิเคราะห์ปัญหา", "count": 1},
            ],
        )
        self.assertEqual(
            ctx["ku_stats"],
            [
                {"id": "KU01", "name": "ความหมาย Algorithm", "count": 3},
                {"id": "KU02", "name": "การวิเคราะห์", "count": 1},
            ],
        )
        self.assertEqual(ctx["total_lg"], 2)

    def test_recent_logs_returns_latest_10_sorted_desc(self):
        logs = [
            log("1", timestamp=f"2026-01-{day:02d} 00:00:00")
            for day in range(1, 16)
        ]

        ctx = dashboard_app.build_dashboard_context(logs=logs, id_map={})

        self.assertEqual(len(ctx["recent_logs"]), 10)
        self.assertEqual(
            ctx["recent_logs"][0]["timestamp"], "2026-01-15 00:00:00"
        )
        self.assertEqual(
            ctx["recent_logs"][-1]["timestamp"], "2026-01-06 00:00:00"
        )

    def test_top_learn_questions_only_counts_is_learn_session(self):
        logs = [
            log("1", user_question="loop คืออะไร", is_learn_session=True),
            log("2", user_question="loop คืออะไร", is_learn_session=True),
            log("1", user_question="if คืออะไร", is_learn_session=True),
            # !alg session ที่ไม่ใช่ !learn ต้องไม่ถูกนับ แม้มี user_question
            log("1", user_question="loop คืออะไร", is_learn_session=False),
        ]

        ctx = dashboard_app.build_dashboard_context(logs=logs, id_map={})

        self.assertEqual(
            ctx["top_learn_questions"],
            [
                {"question": "loop คืออะไร", "count": 2},
                {"question": "if คืออะไร", "count": 1},
            ],
        )

    def test_top_learn_questions_capped_at_10(self):
        logs = [
            log(str(i), user_question=f"คำถามที่ {i}", is_learn_session=True)
            for i in range(15)
        ]

        ctx = dashboard_app.build_dashboard_context(logs=logs, id_map={})

        self.assertEqual(len(ctx["top_learn_questions"]), 10)


class DashboardRouteTest(unittest.TestCase):
    """ทดสอบ route จริงผ่าน Flask test client"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        registry_service.register_student(1, "S-001")

        logger.save_logs([
            log("1", lg_id="LG01", lg_name="Algorithm พื้นฐาน",
                ku_id="KU01", ku_title="ความหมาย Algorithm",
                final_status="COMPLETED",
                final_understanding_level="GOOD"),
            log("1", user_question="loop คืออะไร", is_learn_session=True),
            log("1", user_question="loop คืออะไร", is_learn_session=True),
        ])

        self.client = dashboard_app.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_index_renders_ok_with_stats(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        self.assertIn("Teacher Dashboard", html)
        self.assertIn("Algorithm พื้นฐาน", html)
        self.assertIn("หัวข้อที่เด็กถามบ่อย", html)
        self.assertIn("loop คืออะไร", html)
        self.assertIn("2 ครั้ง", html)

    def test_index_shows_empty_state_when_no_learn_questions(self):
        logger.save_logs([
            log("1", lg_id="LG01", final_status="COMPLETED"),
        ])

        response = self.client.get("/")
        html = response.get_data(as_text=True)

        self.assertIn("ยังไม่มีข้อมูลคำถามจาก !learn", html)

    def test_export_index_links_to_both_csv_downloads(self):
        response = self.client.get("/export")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("/export/summary.csv", html)
        self.assertIn("/export/at-risk.csv", html)

    def test_export_summary_csv_downloads_correct_rows(self):
        response = self.client.get("/export/summary.csv")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.content_type)
        self.assertIn(
            "attachment", response.headers.get("Content-Disposition", "")
        )

        text = response.get_data(as_text=True).lstrip("﻿")
        rows = list(csv.DictReader(io.StringIO(text)))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["student_id"], "S-001")
        self.assertEqual(rows[0]["total_sessions"], "3")
        self.assertEqual(rows[0]["COMPLETED"], "1")

    def test_export_at_risk_csv_downloads_correct_rows(self):
        logger.save_logs([
            log("1", final_status="MAX_ATTEMPTS_REACHED",
                timestamp="2026-01-01 10:00:00"),
            log("1", final_status="MAX_ATTEMPTS_REACHED",
                timestamp="2026-01-01 11:00:00"),
        ])

        response = self.client.get("/export/at-risk.csv")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.content_type)

        text = response.get_data(as_text=True).lstrip("﻿")
        rows = list(csv.DictReader(io.StringIO(text)))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["student_id"], "S-001")
        self.assertIn("ติดต่อกัน", rows[0]["reasons"])


if __name__ == "__main__":
    unittest.main()
