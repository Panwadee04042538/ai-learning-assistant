"""
ทดสอบโหมด DEBUG (config.DEBUG_MODE):

ข้อความที่ส่งไป Discord จากคำสั่ง !alg / start_algorithm_flow ต้องไม่มี
ข้อมูล debug (Matched Term, Match Type, Score, ✅ Test Case Mapping
Success) เมื่อ DEBUG_MODE = False และต้องมีข้อมูลเหล่านี้เมื่อ
DEBUG_MODE = True

วิธีรัน (จากโฟลเดอร์หลักของโปรเจกต์):
    python -m unittest tests.test_debug_mode -v
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
    id = 8001
    bot = False

    def __str__(self):
        return "tester#8001"


class FakeCtx:
    def __init__(self, channel, author):
        self.channel = channel
        self.author = author

    async def send(self, text=None, **kwargs):
        return await self.channel.send(text, **kwargs)


DEBUG_MARKERS = [
    "Matched Term",
    "Match Type",
    "**Score:**",
    "Test Case Mapping Success",
]


class DebugModeMessageTest(unittest.TestCase):

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
        self.author = FakeAuthor()
        self.ctx = FakeCtx(self.channel, self.author)

        registry_service.register_student(self.author.id, "S-8001")

    def tearDown(self):
        self.log_patch.stop()
        self.registry_patch.stop()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _ask(self, question):
        with patch.object(
            main, "ask_grounded_answer", lambda q, c: "คำอธิบายจำลอง"
        ):
            asyncio.run(main.start_algorithm_flow(self.ctx, question))

    def test_debug_markers_hidden_when_debug_mode_off(self):
        with patch.object(main, "DEBUG_MODE", False):
            self._ask("Algorithm คืออะไร")

        joined = "\n".join(self.channel.sent)

        for marker in DEBUG_MARKERS:
            self.assertNotIn(marker, joined, f"ไม่ควรมี '{marker}' เมื่อ DEBUG_MODE=False")

        # เนื้อหาที่ผู้เรียนควรเห็นจริงยังต้องอยู่ครบ
        self.assertIn("Learning Goal Detected", joined)
        self.assertIn("คำอธิบายจำลอง", joined)

    def test_debug_markers_shown_when_debug_mode_on(self):
        with patch.object(main, "DEBUG_MODE", True):
            self._ask("Algorithm คืออะไร")

        joined = "\n".join(self.channel.sent)

        for marker in DEBUG_MARKERS:
            self.assertIn(marker, joined, f"ควรมี '{marker}' เมื่อ DEBUG_MODE=True")

    def test_default_debug_mode_is_off(self):
        self.assertFalse(main.DEBUG_MODE)


if __name__ == "__main__":
    unittest.main()
