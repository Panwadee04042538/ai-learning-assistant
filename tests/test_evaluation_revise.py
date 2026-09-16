"""
ทดสอบการขอย้อนกลับจากขั้นประเมิน (Evaluation -> Monitoring):

หลังบอตส่งคำถามประเมิน (phase EVALUATION_QP) ผู้เรียนสามารถขอย้อนกลับไป
แก้ Algorithm ได้ 1 ครั้งต่อ session ด้วยคำเช่น "ขอแก้ไข" / "ย้อนกลับ" /
"แก้คำตอบ" trigger นี้ต้องไม่ทำงานนอก phase EVALUATION_QP และต้อง
เช็คก่อน Help Triggers เดิมเสมอ

วิธีรัน (จากโฟลเดอร์หลักของโปรเจกต์):
    python -m unittest tests.test_evaluation_revise -v
"""

import asyncio
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault("TYPHOON_API_KEY", "test")
os.environ.setdefault("GEMINI_API_KEY", "test")
os.environ.setdefault("DISCORD_TOKEN", "test")

import logger  # noqa: E402
import main    # noqa: E402
from main import detect_revise_trigger  # noqa: E402
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
    id = 8501
    bot = False

    def __str__(self):
        return "tester#8501"


class DetectReviseTriggerTest(unittest.TestCase):
    """ทดสอบฟังก์ชันตรวจจับข้อความล้วน ๆ ไม่ต้องพึ่ง session"""

    def test_revise_words(self):
        for text in ["ขอแก้ไขหน่อย", "ขอย้อนกลับไปแก้", "แก้คำตอบใหม่"]:
            self.assertTrue(detect_revise_trigger(text), text)

    def test_normal_answer_is_not_a_trigger(self):
        self.assertFalse(detect_revise_trigger("1. รับค่า 2. คำนวณ 3. แสดงผล"))

    def test_help_trigger_words_are_not_revise_triggers(self):
        # ต้องไม่ชนกับ Help Triggers เดิม
        for text in ["ไม่รู้", "ยังไม่รู้", "ขอเฉลย", "พอแล้ว"]:
            self.assertFalse(detect_revise_trigger(text), text)

    def test_empty_text_is_not_a_trigger(self):
        self.assertFalse(detect_revise_trigger(""))
        self.assertFalse(detect_revise_trigger(None))


class RevisePhaseGateTest(unittest.TestCase):
    """
    ทดสอบว่า trigger นี้ทำงานเฉพาะตอน phase EVALUATION_QP เท่านั้น
    โดย patch handler ทั้งสองฝั่งไว้ ไม่ต้องเรียก AI จริง
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

        self.registry_path = os.path.join(
            self.tmpdir, "student_registry.json"
        )
        self.registry_patch = patch.object(
            registry_service, "REGISTRY_PATH", self.registry_path
        )
        self.registry_patch.start()

        main.pending_learning_sessions.clear()

        self.channel = FakeChannel()
        self.author = FakeAuthor()
        registry_service.register_student(self.author.id, "S-8501")

    def tearDown(self):
        self.registry_patch.stop()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _base_session(self, phase):
        return {
            "learning_goal": "LG08 — ฝึกออกแบบ Algorithm จากสถานการณ์",
            "question": "โจทย์ทดสอบ",
            "algorithm_question": "โจทย์ทดสอบ",
            "ku_id": None,
            "lg_id": "LG08",
            "question_id": "PRACTICE",
            "hint_question_id": None,
            "attempt": 1,
            "max_attempts": 3,
            "hint_level": 0,
            "attempt_history": [],
            "qp_responses": [],
            "active_qp": {"system_question": "คำถามประเมิน"},
            "phase": phase,
            "reflection_shown": False,
            "expected_evidence": "",
            "session_id": "test-session-revise",
            "practice_mode": True,
            "practice_prompt": "โจทย์ทดสอบ",
        }

    def _send(self, text):
        msg = FakeMessage(self.author, self.channel, text)
        asyncio.run(main.on_message(msg))

    def test_revise_trigger_calls_handler_when_phase_is_evaluation(self):
        main.pending_learning_sessions[self.author.id] = (
            self._base_session("EVALUATION_QP")
        )

        with patch.object(
            main, "handle_revise_request", new=AsyncMock()
        ) as mock_handler, patch.object(
            main, "handle_qp_response", new=AsyncMock()
        ) as mock_qp:
            self._send("ขอแก้ไข")

        mock_handler.assert_awaited_once()
        mock_qp.assert_not_awaited()

    def test_revise_words_in_other_phase_do_not_call_revise_handler(self):
        main.pending_learning_sessions[self.author.id] = (
            self._base_session("MONITORING_QP")
        )

        with patch.object(
            main, "handle_revise_request", new=AsyncMock()
        ) as mock_handler, patch.object(
            main, "handle_qp_response", new=AsyncMock()
        ) as mock_qp:
            self._send("ขอแก้ไข")

        mock_handler.assert_not_awaited()
        mock_qp.assert_awaited_once()


class ReviseRequestFlowTest(unittest.TestCase):
    """ทดสอบผลจริงของ handle_revise_request ผ่าน main.on_message()"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

        self.registry_path = os.path.join(
            self.tmpdir, "student_registry.json"
        )
        self.registry_patch = patch.object(
            registry_service, "REGISTRY_PATH", self.registry_path
        )
        self.registry_patch.start()

        main.pending_learning_sessions.clear()

        self.channel = FakeChannel()
        self.author = FakeAuthor()
        registry_service.register_student(self.author.id, "S-8501")

        main.pending_learning_sessions[self.author.id] = {
            "learning_goal": "LG08 — ฝึกออกแบบ Algorithm จากสถานการณ์",
            "question": "โจทย์ทดสอบ",
            "algorithm_question": "โจทย์ทดสอบ",
            "ku_id": None,
            "lg_id": "LG08",
            "question_id": "PRACTICE",
            "hint_question_id": None,
            "attempt": 1,
            "max_attempts": 3,
            "hint_level": 0,
            "attempt_history": [],
            "qp_responses": [],
            "active_qp": {"system_question": "คำถามประเมิน"},
            "phase": "EVALUATION_QP",
            "reflection_shown": False,
            "expected_evidence": "",
            "session_id": "test-session-revise",
            "practice_mode": True,
            "practice_prompt": "โจทย์ทดสอบ",
        }

    def tearDown(self):
        self.registry_patch.stop()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _send(self, text):
        msg = FakeMessage(self.author, self.channel, text)
        asyncio.run(main.on_message(msg))

    def _session(self):
        return main.pending_learning_sessions.get(self.author.id)

    def test_first_revise_request_returns_to_monitoring(self):
        self._send("ขอแก้ไข")

        session = self._session()
        self.assertEqual(session["phase"], "MONITORING_QP")
        self.assertTrue(session["has_returned"])
        self.assertIn("กลับไปแก้ Algorithm ได้ 1 ครั้ง", self.channel.sent[-1])

    def test_second_revise_request_is_blocked(self):
        self._send("ขอแก้ไข")   # ครั้งที่ 1: สำเร็จ, phase -> MONITORING_QP

        # จำลองว่ากลับมาถึงขั้นประเมินอีกครั้งหลังแก้ไขแล้ว
        session = self._session()
        session["phase"] = "EVALUATION_QP"

        self._send("ย้อนกลับ")  # ครั้งที่ 2: ต้องถูกบล็อก

        session = self._session()
        self.assertEqual(
            session["phase"], "EVALUATION_QP",
            "ครั้งที่ 2 ต้องไม่เปลี่ยน phase อีก",
        )
        self.assertIn(
            "ย้อนกลับได้แค่ 1 ครั้งต่อ session แล้วค่อยส่งคำตอบสุดท้าย",
            self.channel.sent[-1],
        )


if __name__ == "__main__":
    unittest.main()
