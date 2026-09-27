"""
ทดสอบ Help Triggers: ข้อความขอความช่วยเหลือของผู้เรียนระหว่างทำ Session
แบ่งเป็น 4 กรณี: STUCK (ติดขัด) / STILL_STUCK (ยังติด) /
ANSWER_REQUEST (ขอเฉลย) / QUIT_REQUEST (ขอจบ)

วิธีรัน (จากโฟลเดอร์หลักของโปรเจกต์):
    python -m unittest tests.test_help_triggers -v
"""

import asyncio
import json
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
from main import detect_help_trigger  # noqa: E402
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
    id = 999
    bot = False

    def __str__(self):
        return "tester#0001"


class DetectHelpTriggerTest(unittest.TestCase):
    """ทดสอบฟังก์ชันตรวจจับข้อความล้วน ๆ ไม่ต้องพึ่ง session"""

    def test_stuck_words(self):
        for text in ["ไม่รู้", "คิดไม่ออก", "ช่วยหน่อย", "ไม่เข้าใจเลย"]:
            self.assertEqual(detect_help_trigger(text), "STUCK", text)

    def test_still_stuck_words(self):
        for text in ["ยังไม่รู้อยู่ดี", "ยังคิดไม่ออกเลย"]:
            self.assertEqual(detect_help_trigger(text), "STILL_STUCK", text)

    def test_answer_request_words(self):
        for text in ["ขอเฉลยเลย", "เขียนให้หน่อยได้ไหม", "บอกคำตอบทีสิ"]:
            self.assertEqual(detect_help_trigger(text), "ANSWER_REQUEST", text)

    def test_quit_request_words(self):
        for text in ["พอแล้ว", "จบได้แล้ว", "เลิกทำแล้ว"]:
            self.assertEqual(detect_help_trigger(text), "QUIT_REQUEST", text)

    def test_normal_answer_is_not_a_trigger(self):
        self.assertIsNone(detect_help_trigger("1. รับค่า 2. คำนวณ 3. แสดงผล"))

    def test_empty_text_is_not_a_trigger(self):
        self.assertIsNone(detect_help_trigger(""))
        self.assertIsNone(detect_help_trigger(None))


class HelpTriggerFlowTest(unittest.TestCase):
    """ทดสอบผลจริงเมื่อข้อความเหล่านี้ผ่าน main.on_message()"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        main.pending_learning_sessions.clear()

        self.channel = FakeChannel()
        self.author = FakeAuthor()
        registry_service.register_student(self.author.id, "S-0002")

        # Session จำลองระหว่างตอบคำถาม Algorithm (มี hint_question_id ของ Q39
        # ซึ่งมีคำใบ้ครบ 3 ระดับใน hint_bank.json)
        main.pending_learning_sessions[self.author.id] = {
            "learning_goal": "LG08 — ฝึกออกแบบ Algorithm จากสถานการณ์",
            "question": "โจทย์ทดสอบ",
            "algorithm_question": "โจทย์ทดสอบ",
            "ku_id": None,
            "lg_id": "LG08",
            "question_id": "PRACTICE",
            "hint_question_id": "Q39",
            "attempt": 1,
            "max_attempts": 3,
            "hint_level": 0,
            "attempt_history": [],
            "qp_responses": [],
            "active_qp": None,
            "phase": "ALGORITHM_ANSWER",
            "reflection_shown": False,
            "expected_evidence": "",
            "session_id": "test-session-1",
            "practice_mode": True,
            "practice_prompt": "โจทย์ทดสอบ",
        }
        logger.add_learning_log(
            user_id=self.author.id,
            username=str(self.author),
            user_question="โจทย์ทดสอบ",
        )
        # เปลี่ยน session_id ของ log ให้ตรงกับ session จำลองด้านบน
        logs = logger.load_logs()
        logs[0]["session_id"] = "test-session-1"
        logger.save_logs(logs)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _send(self, text):
        msg = FakeMessage(self.author, self.channel, text)
        asyncio.run(main.on_message(msg))

    def _session(self):
        return main.pending_learning_sessions.get(self.author.id)

    # --------------------------------------------------
    # 1) STUCK -> ให้คำใบ้ระดับถัดไป ไม่นับ attempt
    # --------------------------------------------------
    def test_stuck_gives_hint_without_consuming_attempt(self):
        attempt_before = self._session()["attempt"]

        self._send("ไม่รู้จะทำยังไง")

        session = self._session()
        self.assertEqual(session["hint_level"], 1)
        self.assertEqual(session["attempt"], attempt_before)
        self.assertIn("คำใบ้ระดับที่ 1", self.channel.sent[-1])

    # --------------------------------------------------
    # 2) STILL_STUCK -> เลื่อนคำใบ้ไปอีกระดับ, level 3 แล้วถามซ้ำ
    # --------------------------------------------------
    def test_still_stuck_escalates_hint_level(self):
        self._send("ไม่รู้จะทำยังไง")           # STUCK -> level 1
        self._send("ยังไม่รู้อยู่ดี")             # STILL_STUCK -> level 2

        session = self._session()
        self.assertEqual(session["hint_level"], 2)
        self.assertIn("คำใบ้ระดับที่ 2", self.channel.sent[-1])

    def test_stuck_at_max_level_repeats_question_instead(self):
        self._send("ไม่รู้")             # level 1
        self._send("ยังไม่รู้")           # level 2
        self._send("ยังคิดไม่ออก")        # level 3
        session = self._session()
        self.assertEqual(session["hint_level"], 3)

        self._send("ยังไม่รู้อีก")        # เกินระดับ 3 แล้ว -> ถามคำถามเดิมซ้ำ
        session = self._session()
        self.assertEqual(session["hint_level"], 3, "ไม่ควรเกินระดับ 3")
        self.assertIn("ลองอ่านคำถามเดิมอีกครั้ง", self.channel.sent[-1])
        self.assertIn("โจทย์ทดสอบ", self.channel.sent[-1])

    # --------------------------------------------------
    # 3) ANSWER_REQUEST -> ห้ามเฉลย ไม่เปลี่ยน Phase
    # --------------------------------------------------
    def test_answer_request_refuses_and_keeps_phase(self):
        phase_before = self._session()["phase"]

        self._send("ขอเฉลยหน่อย")

        session = self._session()
        self.assertEqual(session["phase"], phase_before)
        self.assertIn("เฉลยให้ไม่ได้", self.channel.sent[-1])

    # --------------------------------------------------
    # 4) QUIT_REQUEST -> ถามยืนยันก่อน แล้วค่อยบันทึก CANCELLED
    # --------------------------------------------------
    def test_quit_request_asks_for_confirmation_first(self):
        self._send("พอแล้ว")

        session = self._session()
        self.assertIsNotNone(session, "Session ยังไม่ควรถูกลบจนกว่าจะยืนยัน")
        self.assertTrue(session["awaiting_quit_confirmation"])
        self.assertIn("ยืนยัน", self.channel.sent[-1])

    def test_quit_request_confirmed_cancels_session(self):
        self._send("พอแล้ว")
        self._send("ใช่")

        self.assertIsNone(self._session(), "Session ต้องถูกลบหลังยืนยันจบ")

        logs = logger.load_logs()
        self.assertEqual(logs[0]["final_status"], "CANCELLED")

    def test_quit_request_declined_keeps_session(self):
        self._send("พอแล้ว")
        self._send("ไม่ ขอเรียนต่อ")

        session = self._session()
        self.assertIsNotNone(session, "Session ต้องยังอยู่เมื่อไม่ยืนยัน")
        self.assertFalse(session["awaiting_quit_confirmation"])


if __name__ == "__main__":
    unittest.main()
