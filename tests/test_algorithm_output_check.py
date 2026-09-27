"""
ทดสอบว่า problem["output"] จาก Problem Bank ถูกส่งเข้า
evaluate_student_response / build_evaluation_prompt จริง เพื่อให้ Typhoon
บังคับกฎ "ขาดขั้นแสดงผล -> PARTIAL ไม่ใช่ GOOD" ได้ถูกต้อง

Backlog: !alg เคยให้ GOOD แม้ Algorithm ขาดขั้น "แสดงผล" ทั้งที่โจทย์ระบุ
Output ชัดเจน เพราะ prompt ไม่เคยส่ง Output ของโจทย์เข้าไปเลย

วิธีรัน (จากโฟลเดอร์หลักของโปรเจกต์):
    python -m unittest tests.test_algorithm_output_check -v
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
import services.problem_service as problem_service  # noqa: E402
import services.registry_service as registry_service  # noqa: E402


SAMPLE_PROBLEMS = [
    {
        "id": "P-LG08",
        "round": 1,
        "lg": ["LG08"],
        "title": "โจทย์ทดสอบ LG08",
        "situation": "คำนวณค่าบริการสุทธิ",
        "input": "ค่าบริการเต็ม",
        "process": "คำนวณส่วนลด",
        "output": "แสดงค่าบริการสุทธิ",
        "structure": "Sequence",
        "buggy_algorithm": None,
        "bug_type": None,
        "bug_location": None,
        "edge_case": None,
    },
]


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
    id = 9101
    bot = False

    def __str__(self):
        return "tester#9101"


class FakeCtx:
    def __init__(self, channel, author):
        self.channel = channel
        self.author = author

    async def send(self, text=None, **kwargs):
        return await self.channel.send(text, **kwargs)


class AlgorithmOutputCheckWiringTest(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.bank_path = os.path.join(self.tmpdir, "problem_bank.json")
        with open(self.bank_path, "w", encoding="utf-8") as file:
            json.dump(SAMPLE_PROBLEMS, file, ensure_ascii=False)

        self.bank_patch = patch.object(
            problem_service, "PROBLEM_BANK_PATH", self.bank_path
        )
        self.bank_patch.start()

        main.pending_learning_sessions.clear()
        main.active_problem_context.clear()

        self.channel = FakeChannel()
        self.author = FakeAuthor()
        self.ctx = FakeCtx(self.channel, self.author)
        registry_service.register_student(self.author.id, "S-9101")

    def tearDown(self):
        self.bank_patch.stop()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _answer(self, text):
        msg = FakeMessage(self.author, self.channel, text)
        asyncio.run(main.on_message(msg))

    def test_session_stores_problem_output_after_alg_start(self):
        asyncio.run(main.problem.callback(self.ctx, problem_id="P-LG08"))
        asyncio.run(main.start_algorithm_flow(self.ctx, None))

        session = main.pending_learning_sessions.get(self.author.id)
        self.assertIsNotNone(session)
        self.assertEqual(session["expected_output"], "แสดงค่าบริการสุทธิ")

    def test_evaluate_student_response_receives_problem_output(self):
        asyncio.run(main.problem.callback(self.ctx, problem_id="P-LG08"))
        asyncio.run(main.start_algorithm_flow(self.ctx, None))

        # Planning มีข้อเดียว ตอบแล้วไปเขียน Algorithm ทันที
        with patch.object(main, "ask_ai", lambda p: "feedback จำลอง"):
            self._answer("ต้องรับค่าบริการแล้วคำนวณส่วนลด")

        captured = {}

        def fake_evaluate(*args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            return {
                "success": True,
                "understanding_level": "GOOD",
                "feedback": "-", "strength": "-", "improvement": "-",
                "next_action": "CONTINUE",
                "response_type": "ALGORITHM_ANSWER",
            }

        with patch.object(main, "evaluate_student_response", fake_evaluate):
            self._answer("1. รับค่าบริการเต็ม 2. คำนวณส่วนลด 3. จบ")

        # ฟังก์ชันเดิมรับ argument เรียงตามตำแหน่ง ไม่ใช่ keyword จึงตรวจจาก args
        self.assertIn("แสดงค่าบริการสุทธิ", captured["args"])


if __name__ == "__main__":
    unittest.main()
