"""
ทดสอบการข้าม Grounded Answer ใน !learn เมื่อผู้เรียนส่งโจทย์มาวิเคราะห์
(ไม่ใช่คำถามความรู้ทั่วไป)

หมายเหตุ: ตรรกะนี้เดิมอยู่ใน !alg แต่ย้ายไป !learn ทั้งหมดแล้ว เพราะ !alg
ตอนนี้ทำงานเฉพาะกับโจทย์ที่เลือกไว้ผ่าน !problem เท่านั้น ไม่รับคำถามอิสระ

!learn → detect LG → QP เลย (ข้าม grounded answer)
         ยกเว้นคำถามความรู้ทั่วไป เช่น "loop คืออะไร", "if else ใช้ยังไง"
         ที่ยังเรียก Grounded Answer ได้ตามปกติ

วิธีรัน (จากโฟลเดอร์หลักของโปรเจกต์):
    python -m unittest tests.test_grounded_answer_gating -v
"""

import asyncio
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
    id = 7701
    bot = False

    def __str__(self):
        return "tester#7701"


class FakeCtx:
    def __init__(self, channel, author):
        self.channel = channel
        self.author = author

    async def send(self, text=None, **kwargs):
        return await self.channel.send(text, **kwargs)


class IsGeneralKnowledgeQuestionTest(unittest.TestCase):
    """หน่วยทดสอบฟังก์ชันจำแนกคำถามล้วน ๆ ไม่ต้องพึ่ง session/Discord"""

    def test_definition_questions_are_general_knowledge(self):
        for text in ["loop คืออะไร", "Algorithm คืออะไร", "input หมายถึงอะไร"]:
            self.assertTrue(
                main.is_general_knowledge_question(text), text
            )

    def test_usage_questions_are_general_knowledge(self):
        for text in ["if else ใช้ยังไง", "loop ใช้อย่างไร", "ใช้ทำอะไร"]:
            self.assertTrue(
                main.is_general_knowledge_question(text), text
            )

    def test_problem_analysis_questions_are_not_general_knowledge(self):
        for text in [
            "วิเคราะห์โจทย์ยังไง",
            "ช่วยตรวจสอบ Algorithm ให้หน่อย",
            "รับคะแนนสอบ 3 วิชาแล้วหาค่าเฉลี่ย ต้องเขียน Algorithm ยังไง",
        ]:
            self.assertFalse(
                main.is_general_knowledge_question(text), text
            )

    def test_empty_text_is_not_general_knowledge(self):
        self.assertFalse(main.is_general_knowledge_question(""))
        self.assertFalse(main.is_general_knowledge_question(None))


class AlgGroundedAnswerGatingTest(unittest.TestCase):
    """ทดสอบผลจริงเมื่อ !learn ผ่าน start_learn_flow()"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        main.pending_learning_sessions.clear()

        self.channel = FakeChannel()
        self.author = FakeAuthor()
        self.ctx = FakeCtx(self.channel, self.author)
        registry_service.register_student(self.author.id, "S-7701")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _ask(self, question):
        mock_grounded = MagicMock(return_value="คำอธิบายจำลอง")
        mock_reflection = MagicMock(return_value="คำถามสะท้อนคิดจำลอง")
        with patch.object(main, "ask_grounded_answer", mock_grounded), \
             patch.object(main, "ask_reflection", mock_reflection):
            asyncio.run(main.start_learn_flow(self.ctx, question))
        return mock_grounded

    def test_general_knowledge_question_still_calls_grounded_answer(self):
        mock_grounded = self._ask("loop คืออะไร")

        mock_grounded.assert_called_once()
        joined = "\n".join(self.channel.sent)
        self.assertIn("คำอธิบายจำลอง", joined)
        # ต้องไม่มี header "คำอธิบายจาก AI" กำกับไว้ตรง ๆ อีกต่อไป
        self.assertNotIn("คำอธิบายจาก AI", joined)
        # ต้องยังไปต่อที่คำถามสะท้อนคิดตามปกติด้วย ไม่ใช่หยุดแค่ grounded answer
        self.assertIsNotNone(main.pending_learning_sessions.get(self.author.id))

    def test_usage_question_still_calls_grounded_answer(self):
        mock_grounded = self._ask("if else ใช้ยังไง")

        mock_grounded.assert_called_once()
        joined = "\n".join(self.channel.sent)
        self.assertIn("คำอธิบายจำลอง", joined)

    def test_problem_to_analyze_skips_grounded_answer(self):
        mock_grounded = self._ask("วิเคราะห์โจทย์ยังไง")

        mock_grounded.assert_not_called()
        joined = "\n".join(self.channel.sent)
        self.assertNotIn("คำอธิบายจาก AI", joined)
        self.assertNotIn("ยังไม่สามารถสร้างคำอธิบายจาก AI ได้", joined)

        # ต้องยังไปต่อที่คำถามสะท้อนคิดตามที่ต้องการ (ข้าม grounded answer เฉย ๆ)
        session = main.pending_learning_sessions.get(self.author.id)
        self.assertIsNotNone(session)
        self.assertEqual(session["lg_id"], "LG02")
        self.assertTrue(session["is_learn_session"])
        self.assertEqual(
            session["question"], "คำถามสะท้อนคิดจำลอง",
            "คำถามต้องมาจาก Typhoon (ask_reflection) ไม่ใช่ QP.xlsx",
        )
        self.assertIn(
            session["question"], joined,
            "ต้องยังคงถามคำถามสะท้อนคิดตามปกติแม้ข้าม grounded answer",
        )

    def test_algorithm_check_request_skips_grounded_answer(self):
        mock_grounded = self._ask("ช่วยตรวจสอบ Algorithm ให้หน่อย")

        mock_grounded.assert_not_called()
        joined = "\n".join(self.channel.sent)
        self.assertNotIn("คำอธิบายจาก AI", joined)


if __name__ == "__main__":
    unittest.main()
