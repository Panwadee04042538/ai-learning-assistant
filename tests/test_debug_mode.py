"""
ทดสอบโหมด DEBUG (config.DEBUG_MODE):

ข้อความที่ส่งไป Discord จากคำสั่ง !learn / start_learn_flow ต้องไม่มี
ข้อมูล debug (Matched Term, Match Type, Score) เมื่อ DEBUG_MODE = False
และต้องมีข้อมูลเหล่านี้เมื่อ DEBUG_MODE = True

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
]


class DebugModeMessageTest(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

        main.pending_learning_sessions.clear()

        self.channel = FakeChannel()
        self.author = FakeAuthor()
        self.ctx = FakeCtx(self.channel, self.author)

        registry_service.register_student(self.author.id, "S-8001")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _ask(self, question):
        with patch.object(
            main, "ask_grounded_answer", lambda q, c: "คำอธิบายจำลอง"
        ), patch.object(
            main, "ask_reflection", lambda p: "คำถามสะท้อนคิดจำลอง"
        ):
            asyncio.run(main.start_learn_flow(self.ctx, question))

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

    def test_knowledge_unit_reference_block_never_shown(self):
        """
        ข้อความ "อ้างอิงเนื้อหาจาก Knowledge Unit" เป็นข้อความซ้ำซ้อนกับ
        ส่วน KU/หัวข้อที่เคยแสดงไว้ด้านบน และไม่ควรแสดงให้ผู้เรียนเห็น
        ไม่ว่า DEBUG_MODE จะเปิดหรือปิดก็ตาม
        """
        for debug_mode in (False, True):
            main.pending_learning_sessions.clear()
            self.channel.sent.clear()

            with patch.object(main, "DEBUG_MODE", debug_mode):
                self._ask("Algorithm คืออะไร")

            joined = "\n".join(self.channel.sent)
            self.assertNotIn("อ้างอิงเนื้อหาจาก Knowledge Unit", joined)

    def test_test_case_mapping_success_never_shown(self):
        """
        "Test Case Mapping Success" เป็นข้อความทดสอบภายในที่ไม่มีประโยชน์
        กับผู้เรียน จึงถูกลบออกทั้งหมด ไม่ใช่แค่ห่อด้วย DEBUG_MODE
        """
        for debug_mode in (False, True):
            main.pending_learning_sessions.clear()
            self.channel.sent.clear()

            with patch.object(main, "DEBUG_MODE", debug_mode):
                self._ask("Algorithm คืออะไร")

            joined = "\n".join(self.channel.sent)
            self.assertNotIn("Test Case Mapping Success", joined)

    def test_knowledge_retrieved_section_never_shown(self):
        """
        เด็กไม่จำเป็นต้องรู้ว่าระบบดึง KU อะไรมา (matching/retrieval เป็น
        กลไกภายใน) จึงต้องไม่มี section "Knowledge Retrieved" (KU id,
        หัวข้อ, Related LG) ในข้อความที่ส่งไป Discord เลย ไม่ว่า DEBUG_MODE
        จะเปิดหรือปิดก็ตาม
        """
        for debug_mode in (False, True):
            main.pending_learning_sessions.clear()
            self.channel.sent.clear()

            # ใช้คำถามที่ map ไป KU ที่มี related_lg (KU11 -> LG04, LG06)
            # เพื่อให้ครอบคลุมทั้ง KU id, หัวข้อ และ Related LG
            with patch.object(main, "DEBUG_MODE", debug_mode):
                self._ask("loop คืออะไร")

            joined = "\n".join(self.channel.sent)
            self.assertNotIn("Knowledge Retrieved", joined)
            self.assertNotIn("หัวข้อ:", joined)
            self.assertNotIn("Related LG", joined)

            # เนื้อหาที่ผู้เรียนควรเห็นจริงยังต้องอยู่ครบ
            self.assertIn("Learning Goal Detected", joined)


if __name__ == "__main__":
    unittest.main()
