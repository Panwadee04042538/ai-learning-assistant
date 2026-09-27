"""
ทดสอบ flow แบบง่ายของ !learn แบบครบวงจร (ไม่ต่อ Discord / ไม่เรียก AI จริง):

    !learn คำถาม -> detect LG + Grounded Answer -> Typhoon สร้างคำถาม
    สะท้อนคิด 1 ข้อ -> ผู้เรียนตอบ -> ประเมินความเข้าใจสั้น ๆ -> จบทันที

!learn ต้องไม่มี hint, ไม่มีขั้นส่ง Algorithm, ไม่มี Evaluation QP,
ไม่มี max attempts และไม่มี phase ใด ๆ ทั้งสิ้น ต่างจาก session ของ
!alg/!problem ที่ยังใช้กลไกเหล่านี้อยู่ตามปกติ

วิธีรัน (จากโฟลเดอร์หลักของโปรเจกต์):
    python -m unittest tests.test_learn_simple_flow -v
"""

import asyncio
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

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
    id = 8501
    bot = False

    def __str__(self):
        return "tester#8501"


class FakeCtx:
    def __init__(self, channel, author):
        self.channel = channel
        self.author = author

    async def send(self, text=None, **kwargs):
        return await self.channel.send(text, **kwargs)


class LearnSimpleFlowTest(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        main.pending_learning_sessions.clear()

        self.channel = FakeChannel()
        self.author = FakeAuthor()
        self.ctx = FakeCtx(self.channel, self.author)
        registry_service.register_student(self.author.id, "S-8501")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _start(self, question):
        with patch.object(
            main, "ask_grounded_answer",
            MagicMock(return_value="loop คือการทำซ้ำ")
        ), patch.object(
            main, "ask_reflection",
            MagicMock(return_value="คุณคิดว่า loop ใช้ตอนไหนได้บ้าง")
        ):
            asyncio.run(main.start_learn_flow(self.ctx, question))

    def _answer(self, text):
        msg = FakeMessage(self.author, self.channel, text)
        asyncio.run(main.on_message(msg))

    def test_session_has_no_algorithm_or_phase_fields(self):
        """session ของ !learn ต้องไม่มี hint/Algorithm/Evaluation/phase ใด ๆ"""
        self._start("loop คืออะไร")

        session = main.pending_learning_sessions.get(self.author.id)
        self.assertIsNotNone(session)
        self.assertTrue(session["is_learn_session"])

        for field in (
            "phase", "active_qp", "hint_question_id", "hint_level",
            "attempt", "max_attempts", "attempt_history", "qp_responses",
            "main_question_count", "reflection_shown", "qp_id",
            "question_id", "algorithm_question",
        ):
            self.assertNotIn(
                field, session,
                f"session ของ !learn ต้องไม่มี field '{field}' แบบ !alg/!problem",
            )

    def test_grounded_answer_has_no_header(self):
        self._start("loop คืออะไร")

        joined = "\n".join(self.channel.sent)
        self.assertIn("loop คือการทำซ้ำ", joined)
        self.assertNotIn("คำอธิบายจาก AI", joined)

    def test_full_round_trip_ends_immediately_with_feedback(self):
        self._start("loop คืออะไร")
        self.assertIsNotNone(main.pending_learning_sessions.get(self.author.id))

        with patch.object(
            main, "ask_ai",
            MagicMock(return_value="คุณอธิบายการทำซ้ำได้ถูกต้อง")
        ):
            self._answer("loop คือการทำงานซ้ำจนกว่าจะครบเงื่อนไข")

        joined = "\n".join(self.channel.sent)
        self.assertIn("คุณอธิบายการทำซ้ำได้ถูกต้อง", joined)
        self.assertIn("จบการเรียนรู้ครั้งนี้แล้ว", joined)

        # จบทันทีหลังตอบข้อเดียว ไม่มีคำถามขั้นถัดไปหรือ hint ใด ๆ ต่อ
        self.assertIsNone(main.pending_learning_sessions.get(self.author.id))
        self.assertNotIn("คำใบ้", joined)
        self.assertNotIn("ลองทำโจทย์", joined)

        logs = logger.load_logs()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["final_status"], "COMPLETED")
        responses = logs[0].get("metacognitive_responses", [])
        self.assertEqual(len(responses), 1)
        self.assertEqual(responses[0]["phase"], "REFLECTION")

    def test_answer_feedback_error_falls_back_gracefully(self):
        self._start("loop คืออะไร")

        def boom(prompt):
            raise RuntimeError("API down")

        with patch.object(main, "ask_ai", boom):
            self._answer("ไม่แน่ใจ")

        joined = "\n".join(self.channel.sent)
        self.assertIn("จบการเรียนรู้ครั้งนี้แล้ว", joined)
        self.assertIsNone(main.pending_learning_sessions.get(self.author.id))


if __name__ == "__main__":
    unittest.main()
