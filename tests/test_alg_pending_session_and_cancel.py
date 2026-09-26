"""
ทดสอบ:
1. !alg ระหว่าง session ที่ยังไม่จบ -> ไม่ reset session เดิม แต่แจ้งเตือน
   แทนว่ามี session ค้างอยู่ ให้ส่ง Algorithm มา หรือพิมพ์ !cancel
2. คำสั่ง !cancel -> ยกเลิก session ค้างอยู่ (บันทึก log เป็น CANCELLED)
   หรือแจ้งว่าไม่มี session ค้างถ้าไม่มี

วิธีรัน (จากโฟลเดอร์หลักของโปรเจกต์):
    python -m unittest tests.test_alg_pending_session_and_cancel -v
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
    id = 7901
    bot = False

    def __str__(self):
        return "tester#7901"


class FakeCtx:
    def __init__(self, channel, author):
        self.channel = channel
        self.author = author

    async def send(self, text=None, **kwargs):
        return await self.channel.send(text, **kwargs)


class PendingSessionAndCancelTest(unittest.TestCase):

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
        main.active_problem_context.clear()

        self.channel = FakeChannel()
        self.author = FakeAuthor()
        self.ctx = FakeCtx(self.channel, self.author)
        registry_service.register_student(self.author.id, "S-7901")

    def tearDown(self):
        self.log_patch.stop()
        self.registry_patch.stop()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _existing_session(self):
        logger.add_learning_log(
            user_id=self.author.id, username=str(self.author), user_question="q"
        )
        logs = logger.load_logs()
        logs[0]["session_id"] = "existing-session"
        logger.save_logs(logs)

        session = {
            "learning_goal": "LG02",
            "question": "โจทย์เดิม",
            "algorithm_question": "โจทย์เดิม",
            "ku_id": "KU01",
            "lg_id": "LG02",
            "question_id": "Q04",
            "qp_id": "QP02",
            "hint_question_id": None,
            "attempt": 1,
            "max_attempts": 3,
            "hint_level": 0,
            "attempt_history": [],
            "qp_responses": [],
            "active_qp": {"question_id": "Q04", "system_question": "คำถามเดิม"},
            "phase": "ALGORITHM_ANSWER",
            "main_question_count": 1,
            "reflection_shown": False,
            "expected_evidence": "",
            "session_id": "existing-session",
        }
        main.pending_learning_sessions[self.author.id] = session
        return session

    # --------------------------------------------------
    # !alg ระหว่าง session ที่ยังไม่จบ
    # --------------------------------------------------

    def test_alg_with_pending_session_does_not_reset_and_warns(self):
        original_session = self._existing_session()

        asyncio.run(
            main.start_algorithm_flow(self.ctx, "ขอถามเรื่องใหม่")
        )

        self.assertIs(
            main.pending_learning_sessions.get(self.author.id),
            original_session,
            "session เดิมต้องไม่ถูก reset/แทนที่",
        )
        self.assertIn("มี session ค้างอยู่", self.channel.sent[-1])
        self.assertIn("!cancel", self.channel.sent[-1])

    def test_alg_with_pending_session_warns_even_with_no_question(self):
        self._existing_session()

        asyncio.run(main.start_algorithm_flow(self.ctx, None))

        self.assertIn("มี session ค้างอยู่", self.channel.sent[-1])
        self.assertNotIn(
            "ลองถามแบบนี้ได้เลย", self.channel.sent[-1],
            "ตอน pending session ต้องเตือนเรื่อง session ค้าง ไม่ใช่ usage help",
        )

    def test_alg_without_pending_session_still_works_normally(self):
        main.active_problem_context[self.author.id] = {
            "id": "P01", "lg": ["LG02"], "situation": "สถานการณ์ทดสอบ",
        }

        asyncio.run(main.start_algorithm_flow(self.ctx, None))

        self.assertIsNotNone(main.pending_learning_sessions.get(self.author.id))
        joined = "\n".join(self.channel.sent)
        self.assertNotIn("มี session ค้างอยู่", joined)

    # --------------------------------------------------
    # !alg โดยไม่มีโจทย์ที่เลือกไว้ผ่าน !problem
    # --------------------------------------------------

    def test_alg_without_active_problem_asks_to_use_problem_or_learn(self):
        asyncio.run(main.start_algorithm_flow(self.ctx, None))

        self.assertIsNone(main.pending_learning_sessions.get(self.author.id))
        sent_message = self.channel.sent[-1]
        self.assertIn("!problem", sent_message)
        self.assertIn("P07", sent_message)
        self.assertIn("!learn", sent_message)

    # --------------------------------------------------
    # !cancel
    # --------------------------------------------------

    def test_cancel_clears_pending_session_and_logs_cancelled(self):
        self._existing_session()

        asyncio.run(main.cancel.callback(self.ctx))

        self.assertIsNone(main.pending_learning_sessions.get(self.author.id))
        self.assertIn("ยกเลิก session เดิมแล้ว", self.channel.sent[-1])

        with open(self.log_path, encoding="utf-8") as f:
            logs = json.load(f)
        self.assertEqual(logs[0]["final_status"], "CANCELLED")

    def test_cancel_with_no_pending_session(self):
        asyncio.run(main.cancel.callback(self.ctx))

        self.assertIn("ไม่มี session ค้างอยู่", self.channel.sent[-1])

    def test_cancel_requires_registration(self):
        os.remove(self.registry_path)

        asyncio.run(main.cancel.callback(self.ctx))

        self.assertIn("ลงทะเบียนก่อนใช้งาน", self.channel.sent[-1])

    def test_alg_works_again_after_cancel(self):
        self._existing_session()
        asyncio.run(main.cancel.callback(self.ctx))

        main.active_problem_context[self.author.id] = {
            "id": "P01", "lg": ["LG02"], "situation": "สถานการณ์ทดสอบ",
        }
        asyncio.run(main.start_algorithm_flow(self.ctx, None))

        session = main.pending_learning_sessions.get(self.author.id)
        self.assertIsNotNone(session)
        self.assertNotEqual(
            session.get("session_id"), "existing-session",
            "หลัง !cancel แล้ว !alg ต้องสร้าง session ใหม่ได้ตามปกติ",
        )


if __name__ == "__main__":
    unittest.main()
