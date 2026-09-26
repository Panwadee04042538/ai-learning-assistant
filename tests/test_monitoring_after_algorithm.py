"""
ทดสอบลำดับ Phase ใหม่ใน handle_qp_response (main.py):

เดิม: PLANNING_QP ตอบแล้ว -> Monitoring QP ทันที -> ค่อยส่ง Algorithm
ใหม่: PLANNING_QP ตอบแล้ว -> ส่ง Algorithm ทันที -> ประเมิน Algorithm
      -> ถ้า GOOD หรือ MAX_ATTEMPTS_REACHED -> Monitoring QP
      ("ลองตรวจสอบ Algorithm ที่เขียน...") -> Evaluation QP

เทสต์นี้เน้นกรณีที่ tests/test_practice_flow.py และ
tests/test_session_pacing.py ยังไม่ครอบคลุม:

1. MAX_ATTEMPTS_REACHED (ไม่ใช่แค่ GOOD) ก็ต้องแวะ Monitoring ก่อน
   Evaluation เหมือนกัน
2. LG ที่ไม่มีขั้น Planning (เช่น LG05) ตอบ Monitoring ไปแล้วตอนเริ่ม
   session (ก่อนส่ง Algorithm) ต้องไม่ถูกถาม Monitoring ซ้ำอีกรอบหลัง
   ประเมิน Algorithm

วิธีรัน (จากโฟลเดอร์หลักของโปรเจกต์):
    python -m unittest tests.test_monitoring_after_algorithm -v
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

    NEXT_ID = 9501

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
        registry_service.register_student(self.author.id, "S-9501")

    def tearDown(self):
        self.log_patch.stop()
        self.registry_patch.stop()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _answer(self, text):
        msg = FakeMessage(self.author, self.channel, text)
        asyncio.run(main.on_message(msg))

    def _session(self):
        return main.pending_learning_sessions.get(self.author.id)


class MaxAttemptsReachedGoesToMonitoringTest(BaseSessionTest):
    """MAX_ATTEMPTS_REACHED ต้องแวะ Monitoring ก่อน Evaluation เหมือน GOOD"""

    def _make_algorithm_answer_session(self):
        """จำลอง session ที่ตอบ Planning ไปแล้ว (main_question_count=1)
        กำลังรอคำตอบ Algorithm ครั้งแรก ยังไม่เคยถาม Monitoring"""
        main.pending_learning_sessions[self.author.id] = {
            "learning_goal": "LG02",
            "question": "โจทย์ทดสอบ",
            "algorithm_question": "โจทย์ทดสอบ",
            "ku_id": "KU01",
            "lg_id": "LG02",
            "question_id": "Q04",
            "qp_id": "QP02",
            "hint_question_id": "Q07",
            "attempt": 1,
            "max_attempts": 2,
            "hint_level": 0,
            "attempt_history": [],
            "qp_responses": [
                {"question_id": "Q04", "qp_id": "QP02", "phase": "PLANNING_QP"},
            ],
            "active_qp": None,
            "phase": "ALGORITHM_ANSWER",
            "main_question_count": 1,
            "reflection_shown": False,
            "expected_evidence": "",
            "session_id": "test-max-attempts-session",
        }
        logger.add_learning_log(
            user_id=self.author.id, username=str(self.author), user_question="q"
        )
        logs = logger.load_logs()
        logs[0]["session_id"] = "test-max-attempts-session"
        logger.save_logs(logs)

    def test_max_attempts_reached_goes_to_monitoring_then_evaluation(self):
        self._make_algorithm_answer_session()

        partial_result = {
            "success": True, "understanding_level": "PARTIAL",
            "feedback": "ยังไม่ครบ", "strength": "-",
            "improvement": "ลองอีกครั้ง", "next_action": "HINT",
            "response_type": "ALGORITHM_ANSWER",
        }

        with patch.object(main, "evaluate_student_response",
                           lambda *a, **k: partial_result):
            self._answer("คำตอบครั้งที่ 1")   # attempt 1 -> 2 (ยังไม่เกิน max_attempts=2)

        s = self._session()
        self.assertEqual(s["phase"], "ALGORITHM_ANSWER")

        with patch.object(main, "evaluate_student_response",
                           lambda *a, **k: partial_result):
            self._answer("คำตอบครั้งที่ 2 (เกิน max_attempts)")

        s = self._session()
        self.assertEqual(
            s["phase"], "MONITORING_QP_POST_ALGORITHM",
            "MAX_ATTEMPTS_REACHED ต้องแวะ Monitoring ก่อน Evaluation "
            "เหมือนกับ GOOD เพราะยังไม่เคยถาม Monitoring มาก่อน",
        )
        self.assertEqual(s["pending_final_status"], "MAX_ATTEMPTS_REACHED")

        # ตอบ Monitoring แล้วต้องไป Evaluation ต่อ และปิด session ด้วย
        # สถานะ MAX_ATTEMPTS_REACHED ที่ค้างไว้ (ไม่ใช่ COMPLETED)
        self._answer("ตรวจสอบแล้ว")
        s = self._session()
        self.assertEqual(s["phase"], "EVALUATION_QP")

        self._answer("แก้ปัญหาได้บางส่วน")
        self.assertIsNone(self._session())

        with open(self.log_path, encoding="utf-8") as f:
            import json
            logs = json.load(f)
        self.assertEqual(logs[0]["final_status"], "MAX_ATTEMPTS_REACHED")


class NoPlanningLgDoesNotAskMonitoringTwiceTest(BaseSessionTest):
    """LG05/LG07 ตอบ Monitoring ไปแล้วก่อนส่ง Algorithm ต้องไม่ถูกถามซ้ำ"""

    def test_lg05_good_after_initial_monitoring_skips_straight_to_evaluation(self):
        with patch.object(main, "ask_grounded_answer", lambda q, c: "mock"):
            asyncio.run(
                main.start_algorithm_flow(
                    self.ctx, "ช่วยตรวจสอบ Algorithm ให้หน่อย"
                )
            )

        s = self._session()
        self.assertEqual(s["lg_id"], "LG05")
        self.assertEqual(s["phase"], "MONITORING_QP")

        # ตอบ Monitoring ข้อแรก (ก่อนส่ง Algorithm) -> ไปเขียน Algorithm
        self._answer("ตรวจสอบทีละขั้นตอนก่อนสรุปผล")
        s = self._session()
        self.assertEqual(s["phase"], "ALGORITHM_ANSWER")

        good_result = {
            "success": True, "understanding_level": "GOOD",
            "feedback": "ถูกต้อง", "strength": "ครบถ้วน",
            "improvement": "-", "next_action": "COMPLETE",
            "response_type": "ALGORITHM_ANSWER",
        }
        with patch.object(main, "evaluate_student_response",
                           lambda *a, **k: good_result):
            self._answer("1. รับค่า 2. ตรวจสอบ 3. แสดงผล")

        s = self._session()
        self.assertEqual(
            s["phase"], "EVALUATION_QP",
            "Monitoring ตอบไปแล้วตอนเริ่ม session จึงไม่ควรถูกถามซ้ำ "
            "หลังประเมิน Algorithm อีกรอบ",
        )

        metacog_phases = [r["phase"] for r in s["qp_responses"]]
        self.assertEqual(
            metacog_phases.count("MONITORING_QP")
            + metacog_phases.count("MONITORING_QP_POST_ALGORITHM"),
            1,
            "ต้องมี Monitoring แค่ครั้งเดียวตลอด session",
        )


if __name__ == "__main__":
    unittest.main()
