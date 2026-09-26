"""
ทดสอบการจัดลำดับคำถามภายใน session (Session Pacing):

1. ขั้น Planning มีคำถามเดียวต่อ session ตอบแล้วไปขั้นถัดไปทันที
   (feedback กับคำถาม/ขั้นตอนถัดไปต้องแยกคนละข้อความ ไม่รวมกัน)
2. LG ที่ไม่มีขั้น Planning (LG05/LG07) ต้องเริ่ม session ที่ Monitoring
   ทันที พร้อมข้อความ context อธิบายว่าไม่มีขั้นวางแผน
3. งบคำถามหลัก 3 ข้อต่อ session (Planning/Monitoring/Evaluation) --
   คำใบ้และการส่งซ้ำระหว่าง ALGORITHM_ANSWER เป็น sub-turn ไม่นับเพิ่ม
   และไม่ถาม Monitoring ซ้ำระหว่าง retry

วิธีรัน (จากโฟลเดอร์หลักของโปรเจกต์):
    python -m unittest tests.test_session_pacing -v
"""

import asyncio
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
import main    # noqa: E402
import services.registry_service as registry_service  # noqa: E402


class FakeMessage:
    def __init__(self, author, channel, content=""):
        self.author = author
        self.channel = channel
        self.content = content

    async def delete(self):
        pass


class FakeChannel:
    def __init__(self):
        self.sent = []

    async def send(self, text=None, **kwargs):
        self.sent.append(text or "")
        return FakeMessage(None, self, text)


class FakeAuthor:
    def __init__(self, user_id):
        self.id = user_id
        self.bot = False

    def __str__(self):
        return f"tester#{self.id}"


class FakeCtx:
    def __init__(self, channel, author):
        self.channel = channel
        self.author = author

    async def send(self, text=None, **kwargs):
        return await self.channel.send(text, **kwargs)


class BaseSessionTest(unittest.TestCase):
    """เตรียม log แยกจากไฟล์จริง และช่วยส่งข้อความจำลอง"""

    NEXT_ID = 9001

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.tmpdir, "learning_logs.json")
        self.log_patch = patch.object(logger, "LOG_PATH", self.log_path)
        self.log_patch.start()

        self.registry_path = os.path.join(
            self.tmpdir, "student_registry.json"
        )
        self.registry_patch = patch.object(
            registry_service, "REGISTRY_PATH", self.registry_path
        )
        self.registry_patch.start()

        main.pending_learning_sessions.clear()

        self.channel = FakeChannel()
        self.author = FakeAuthor(BaseSessionTest.NEXT_ID)
        BaseSessionTest.NEXT_ID += 1
        self.ctx = FakeCtx(self.channel, self.author)
        registry_service.register_student(self.author.id, "S-0004")

    def tearDown(self):
        self.log_patch.stop()
        self.registry_patch.stop()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _answer(self, text):
        msg = FakeMessage(self.author, self.channel, text)
        asyncio.run(main.on_message(msg))

    def _session(self):
        return main.pending_learning_sessions.get(self.author.id)


class PlanningSingleQuestionTest(BaseSessionTest):
    """งานที่ 1: ขั้น Planning มีคำถามเดียวต่อ session แล้วไป Evaluation
    ทันที (เฉพาะ LG08 เท่านั้นที่ยังมีขั้นเขียน/ส่ง Algorithm ต่อ LG อื่น
    ข้าม ALGORITHM_ANSWER ไปเลย)"""

    def test_lg02_planning_asks_one_question_then_goes_straight_to_evaluation(self):
        # LG02 มีคำถาม Planning หลายข้อใน QP.xlsx (Q04, Q05, Q06) แต่ session
        # ต้องถามแค่ข้อแรกแล้วไป Evaluation ทันที ไม่ถามต่อทีละข้อ และไม่ต้อง
        # เขียน Algorithm เลย (เฉพาะ LG08 เท่านั้นที่มีขั้นเขียน Algorithm)
        with patch.object(main, "ask_grounded_answer", lambda q, c: "mock"), \
             patch.object(main, "ask_ai", lambda p: "mock feedback"):

            asyncio.run(
                main.start_algorithm_flow(self.ctx, "วิเคราะห์โจทย์ยังไง")
            )

            s = self._session()
            self.assertEqual(s["lg_id"], "LG02")
            self.assertEqual(s["phase"], "PLANNING_QP")
            self.assertNotIn(
                "planning_questions", s,
                "ตัด planning_questions loop ออกแล้ว ไม่ควรมี key นี้อีก",
            )
            self.assertEqual(s["main_question_count"], 1)
            planning_question_id = s["active_qp"]["question_id"]
            self.assertTrue(planning_question_id)

            # ตอบคำถาม Planning ข้อเดียว -> ต้องไป Evaluation ทันที
            # (LG02 ไม่ใช่ LG08 จึงไม่ต้องเขียน Algorithm)
            self._answer("โจทย์ต้องการคำนวณเกรด")
            s = self._session()
            self.assertEqual(
                s["phase"], "EVALUATION_QP",
                "LG อื่นนอกจาก LG08 หลังตอบ Planning ต้องไป Evaluation เลย "
                "ไม่ต้องเขียน Algorithm",
            )
            self.assertEqual(s["main_question_count"], 2)

            metacog_phases = [r["phase"] for r in s["qp_responses"]]
            self.assertEqual(metacog_phases, ["PLANNING_QP"])

            # feedback กับคำถาม Evaluation ต้องแยกคนละข้อความ ไม่รวมกัน
            feedback_msg = self.channel.sent[-2]
            evaluation_question_msg = self.channel.sent[-1]
            self.assertIn("mock feedback", feedback_msg)
            self.assertNotIn("🪞", feedback_msg)
            self.assertIn("🪞", evaluation_question_msg)
            self.assertNotIn("mock feedback", evaluation_question_msg)

            # ตอบ Evaluation แล้วต้องจบ session เลย ไม่มีขั้น Algorithm/
            # Monitoring เข้ามาเกี่ยวข้องสำหรับ LG นี้
            self._answer("แก้ปัญหาได้ เพราะทดสอบกับตัวอย่างแล้ว")
            self.assertIsNone(self._session(), "Session ต้องถูกปิดเมื่อจบ")


class NoPlanningStartsAtMonitoringTest(BaseSessionTest):
    """งานที่ 2: LG05/LG07 ไม่มีขั้น Planning ต้องเริ่มที่ Monitoring
    พร้อมข้อความ context"""

    def _assert_starts_at_monitoring_with_context(self, question, expected_lg):
        with patch.object(main, "ask_grounded_answer", lambda q, c: "mock"):
            asyncio.run(main.start_algorithm_flow(self.ctx, question))

        s = self._session()
        self.assertIsNotNone(s, f"ควรสร้าง session จากคำถาม: {question}")
        self.assertEqual(s["lg_id"], expected_lg)
        self.assertEqual(s["phase"], "MONITORING_QP")
        self.assertNotIn("planning_questions", s)
        self.assertIsNotNone(s["hint_question_id"])
        self.assertEqual(s["main_question_count"], 1)

        sent_message = self.channel.sent[-1]
        self.assertIn(
            "ไม่มีขั้นวางแผน",
            sent_message,
            "ต้องมีข้อความ context อธิบายว่าไม่มีขั้นวางแผนก่อนถามคำถาม Monitoring",
        )

    def test_lg05_starts_at_monitoring_with_context(self):
        self._assert_starts_at_monitoring_with_context(
            "ช่วยตรวจสอบ Algorithm ให้หน่อย", "LG05"
        )

    def test_lg07_starts_at_monitoring_with_context(self):
        self._assert_starts_at_monitoring_with_context(
            "ควรปรับปรุง Algorithm นี้อย่างไร", "LG07"
        )


class MainQuestionBudgetTest(BaseSessionTest):
    """งานที่ 3: งบคำถามหลัก 3 ข้อต่อ session
    hint/ส่งซ้ำเป็น sub-turn ไม่นับเพิ่ม และไม่ถาม Monitoring ซ้ำ"""

    def _make_algorithm_answer_session(self):
        """จำลอง session ที่ผ่านขั้น Planning + Monitoring มาแล้ว
        (main_question_count=2) กำลังรอคำตอบ Algorithm ข้อแรก"""
        main.pending_learning_sessions[self.author.id] = {
            "learning_goal": "LG02",
            "question": "โจทย์ทดสอบ",
            "algorithm_question": "โจทย์ทดสอบ",
            "ku_id": "KU01",
            "lg_id": "LG02",
            "question_id": "Q07",
            "qp_id": "QP02",
            "hint_question_id": "Q07",
            "attempt": 1,
            "max_attempts": 3,
            "hint_level": 0,
            "attempt_history": [],
            "qp_responses": [
                {"question_id": "Q04", "qp_id": "QP02", "phase": "PLANNING_QP"},
                {"question_id": "Q05", "qp_id": "QP02", "phase": "PLANNING_QP"},
                {"question_id": "Q06", "qp_id": "QP02", "phase": "PLANNING_QP"},
                {"question_id": "Q07", "qp_id": "QP02", "phase": "MONITORING_QP"},
            ],
            "active_qp": None,
            "phase": "ALGORITHM_ANSWER",
            "main_question_count": 2,
            "reflection_shown": False,
            "expected_evidence": "",
            "session_id": "test-budget-session",
        }
        logger.add_learning_log(
            user_id=self.author.id, username=str(self.author), user_question="q"
        )
        logs = logger.load_logs()
        logs[0]["session_id"] = "test-budget-session"
        logger.save_logs(logs)

    def test_partial_retry_is_subturn_and_stays_within_budget(self):
        self._make_algorithm_answer_session()

        partial_result = {
            "success": True, "understanding_level": "PARTIAL",
            "feedback": "ยังไม่ครบ", "strength": "เริ่มได้ดี",
            "improvement": "เพิ่มการตรวจสอบ", "next_action": "HINT",
            "response_type": "ALGORITHM_ANSWER",
        }

        with patch.object(main, "evaluate_student_response",
                           lambda *a, **k: partial_result):
            self._answer("1. รับค่า 2. คำนวณ")

        s = self._session()
        self.assertEqual(
            s["phase"], "ALGORITHM_ANSWER",
            "PARTIAL ต้องเป็น sub-turn อยู่ใน ALGORITHM_ANSWER ไม่ใช่ Monitoring ใหม่",
        )
        self.assertEqual(s["hint_level"], 1)
        self.assertEqual(
            s["main_question_count"], 2,
            "hint/ส่งซ้ำต้องไม่ทำให้ main_question_count เพิ่ม",
        )

        # ยังไม่มี qp_responses ใหม่ที่เป็น Monitoring เพิ่มขึ้น
        monitoring_entries = [
            r for r in s["qp_responses"] if r.get("phase") == "MONITORING_QP"
        ]
        self.assertEqual(
            len(monitoring_entries), 1,
            "ต้องมี Monitoring เพียง 1 ข้อเท่านั้นตลอด session แม้ retry หลายครั้ง",
        )

    def test_good_on_first_try_skips_retry_and_goes_to_evaluation(self):
        self._make_algorithm_answer_session()

        good_result = {
            "success": True, "understanding_level": "GOOD",
            "feedback": "ถูกต้อง", "strength": "ครบถ้วน",
            "improvement": "-", "next_action": "COMPLETE",
            "response_type": "ALGORITHM_ANSWER",
        }

        with patch.object(main, "evaluate_student_response",
                           lambda *a, **k: good_result):
            self._answer("1. รับค่า 2. คำนวณ 3. แสดงผล")

        s = self._session()
        self.assertEqual(
            s["phase"], "EVALUATION_QP",
            "GOOD ตั้งแต่ครั้งแรกต้องข้ามขั้นตรวจสอบซ้ำไป Evaluation เลย",
        )
        self.assertEqual(s["hint_level"], 0, "ไม่ควรมีการให้คำใบ้เมื่อ GOOD ตั้งแต่ครั้งแรก")
        self.assertEqual(s["main_question_count"], 3)

    def test_repeated_partial_attempts_never_exceed_three_main_questions(self):
        self._make_algorithm_answer_session()

        partial_result = {
            "success": True, "understanding_level": "PARTIAL",
            "feedback": "ยังไม่ครบ", "strength": "-",
            "improvement": "ลองอีกครั้ง", "next_action": "HINT",
            "response_type": "ALGORITHM_ANSWER",
        }

        with patch.object(main, "evaluate_student_response",
                           lambda *a, **k: partial_result):
            self._answer("คำตอบครั้งที่ 1")
            self._answer("คำตอบครั้งที่ 2")

        s = self._session()
        # max_attempts=3: attempt เพิ่มจาก 1 -> 3 แล้ว (ยังไม่เกิน)
        self.assertEqual(s["phase"], "ALGORITHM_ANSWER")
        self.assertEqual(s["main_question_count"], 2)
        self.assertLessEqual(s["main_question_count"], 3)

        with patch.object(main, "evaluate_student_response",
                           lambda *a, **k: partial_result):
            self._answer("คำตอบครั้งที่ 3 (เกิน max_attempts)")

        s = self._session()
        self.assertEqual(
            s["phase"], "EVALUATION_QP",
            "เกิน max_attempts แล้วต้องไป Evaluation เพื่อปิด session",
        )
        self.assertEqual(s["main_question_count"], 3)


if __name__ == "__main__":
    unittest.main()
