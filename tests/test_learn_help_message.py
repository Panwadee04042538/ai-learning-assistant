"""
ทดสอบ help message ของ !learn เมื่อพิมพ์โดยไม่มีข้อความต่อท้าย

!learn รับช่วงต่อจาก !alg ในการถามคำถามอิสระ/ความรู้ทั่วไป เพราะ !alg
ตอนนี้ทำงานเฉพาะกับโจทย์ที่เลือกไว้ผ่าน !problem เท่านั้น ไม่รับคำถาม
อิสระอีกต่อไป

วิธีรัน (จากโฟลเดอร์หลักของโปรเจกต์):
    python -m unittest tests.test_learn_help_message -v
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
    id = 7801
    bot = False

    def __str__(self):
        return "tester#7801"


class FakeCtx:
    def __init__(self, channel, author):
        self.channel = channel
        self.author = author

    async def send(self, text=None, **kwargs):
        return await self.channel.send(text, **kwargs)


class LearnHelpMessageTest(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        main.pending_learning_sessions.clear()

        self.channel = FakeChannel()
        self.author = FakeAuthor()
        self.ctx = FakeCtx(self.channel, self.author)
        registry_service.register_student(self.author.id, "S-7801")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    EXPECTED_EXAMPLES = [
        "!learn ทำไมต้องวิเคราะห์โจทย์ก่อนเขียนอัลกอริทึม?",
        "!learn loop กับ if ต่างกันยังไง?",
        "!learn จะรู้ได้ยังไงว่าโจทย์นี้ต้องใช้การวนซ้ำ?",
        "!learn ขั้นตอนแรกของการออกแบบอัลกอริทึมคืออะไร?",
    ]

    def test_learn_with_no_question_shows_usage_examples(self):
        asyncio.run(main.start_learn_flow(self.ctx, None))

        self.assertEqual(len(self.channel.sent), 1)
        sent_message = self.channel.sent[0]

        self.assertIn("ลองถามแบบนี้ได้เลย", sent_message)
        for example in self.EXPECTED_EXAMPLES:
            self.assertIn(example, sent_message)

        # ไม่ควรเริ่ม session ใด ๆ เมื่อยังไม่มีคำถามจริง
        self.assertIsNone(main.pending_learning_sessions.get(self.author.id))

    def test_learn_with_blank_whitespace_question_shows_usage_examples(self):
        asyncio.run(main.start_learn_flow(self.ctx, "   "))

        sent_message = self.channel.sent[0]
        self.assertIn("ลองถามแบบนี้ได้เลย", sent_message)

    def test_learn_command_callback_with_no_argument(self):
        asyncio.run(main.learn.callback(self.ctx, question=None))

        sent_message = self.channel.sent[0]
        self.assertIn("ลองถามแบบนี้ได้เลย", sent_message)

    def test_unregistered_learner_still_sees_registration_gate_first(self):
        # registration ถูกเช็คก่อนทุก entry point ของ !learn (ตามดีไซน์เดิม)
        # แม้เป็นแค่การขอดู usage help ก็ยังต้องลงทะเบียนก่อน
        registry_service._save_registry({})

        asyncio.run(main.start_learn_flow(self.ctx, None))

        sent_message = self.channel.sent[0]
        self.assertIn("ลงทะเบียนก่อนใช้งาน", sent_message)
        self.assertNotIn("ลองถามแบบนี้ได้เลย", sent_message)


if __name__ == "__main__":
    unittest.main()
