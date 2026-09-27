"""
ทดสอบ model_answer ใน Problem Bank และการส่งต่อเข้าสู่การประเมิน Algorithm

1. ข้อมูลจริงใน data/problem_bank.json: ทุกโจทย์ (P01-P15) ต้องมี
   model_answer ไม่ว่างเปล่า และ P07 ต้องตรงกับเฉลยอ้างอิงที่กำหนดไว้
2. Wiring: _start_problem_algorithm_session (main.py) ต้องเก็บ
   session["model_answer"] จาก problem["model_answer"] และค่านี้ต้องถูก
   ส่งต่อเข้า evaluate_student_response ตอนประเมินคำตอบจริง

วิธีรัน (จากโฟลเดอร์หลักของโปรเจกต์):
    python -m unittest tests.test_model_answer -v
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


P07_MODEL_ANSWER = (
    "1. เริ่มต้น\n"
    "2. total = 0, count = 0\n"
    "3. รับค่า n\n"
    "4. ทำซ้ำขณะ n ≠ -1\n"
    "   4.1 total = total + n\n"
    "   4.2 count = count + 1\n"
    "   4.3 รับค่า n ใหม่\n"
    "5. แสดง total, count\n"
    "6. จบ"
)


class RealProblemBankModelAnswerTest(unittest.TestCase):
    """ตรวจข้อมูลจริงใน data/problem_bank.json โดยตรง ไม่ใช้ข้อมูลจำลอง"""

    @classmethod
    def setUpClass(cls):
        with open(problem_service.PROBLEM_BANK_PATH, encoding="utf-8") as f:
            cls.problems = json.load(f)

    def test_all_15_problems_present(self):
        self.assertEqual(len(self.problems), 15)

    def test_every_problem_has_non_empty_model_answer(self):
        missing = [
            p["id"] for p in self.problems if not (p.get("model_answer") or "").strip()
        ]
        self.assertEqual(
            missing, [],
            f"โจทย์ต่อไปนี้ยังไม่มี model_answer: {missing}",
        )

    def test_p07_model_answer_matches_reference(self):
        p07 = next(p for p in self.problems if p["id"] == "P07")
        self.assertEqual(p07["model_answer"], P07_MODEL_ANSWER)

    def test_get_problem_p07_includes_model_answer(self):
        p07 = problem_service.get_problem("P07")
        self.assertIsNotNone(p07)
        self.assertEqual(p07["model_answer"], P07_MODEL_ANSWER)


SAMPLE_PROBLEMS = [
    {
        "id": "P07",
        "round": 3,
        "lg": ["LG02", "LG03", "LG04"],
        "title": "รวบรวมจำนวนผู้เข้าร่วมกิจกรรม",
        "situation": "สถานการณ์ทดสอบ P07",
        "input": "จำนวนผู้เข้าร่วมของแต่ละห้อง (-1 หมายถึงสิ้นสุด)",
        "process": "รวบรวมจำนวนผู้เข้าร่วมและจำนวนห้อง",
        "output": "จำนวนผู้เข้าร่วมทั้งหมด, จำนวนห้องที่ส่งข้อมูล",
        "model_answer": P07_MODEL_ANSWER,
        "structure": "Repetition",
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
    id = 9401
    bot = False

    def __str__(self):
        return "tester#9401"


class FakeCtx:
    def __init__(self, channel, author):
        self.channel = channel
        self.author = author

    async def send(self, text=None, **kwargs):
        return await self.channel.send(text, **kwargs)


class ModelAnswerWiringTest(unittest.TestCase):
    """ทดสอบด้วยข้อมูลจำลอง (แยกจากข้อมูลจริง) ว่า wiring ทำงานถูกต้อง"""

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
        registry_service.register_student(self.author.id, "S-9401")

    def tearDown(self):
        self.bank_patch.stop()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _answer(self, text):
        msg = FakeMessage(self.author, self.channel, text)
        asyncio.run(main.on_message(msg))

    def test_session_stores_model_answer_after_alg_start(self):
        asyncio.run(main.problem.callback(self.ctx, problem_id="P07"))
        asyncio.run(main.start_algorithm_flow(self.ctx, None))

        session = main.pending_learning_sessions.get(self.author.id)
        self.assertIsNotNone(session)
        self.assertEqual(session["model_answer"], P07_MODEL_ANSWER)

    def test_evaluate_student_response_receives_model_answer(self):
        asyncio.run(main.problem.callback(self.ctx, problem_id="P07"))
        asyncio.run(main.start_algorithm_flow(self.ctx, None))

        # Planning มีข้อเดียว ตอบแล้วไปเขียน Algorithm ทันที
        with patch.object(main, "ask_ai", lambda p: "feedback จำลอง"):
            self._answer("ต้องรับค่าทีละห้องจนกว่าจะพบ -1")

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
            self._answer(
                "1. total=0, count=0 2. รับค่า n 3. ทำซ้ำขณะ n ไม่ใช่ -1 "
                "บวกเข้า total และเพิ่ม count แล้วรับค่าใหม่ 4. แสดง total, "
                "count 5. จบ"
            )

        # evaluate_student_response ถูกเรียกแบบ positional argument จึง
        # ตรวจจาก args ว่ามี model_answer ของ P07 ส่งไปด้วย
        self.assertIn(P07_MODEL_ANSWER, captured["args"])


if __name__ == "__main__":
    unittest.main()
