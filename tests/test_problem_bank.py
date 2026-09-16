"""
ทดสอบระบบคลังปัญหา (Problem Bank):

1. services/problem_service.py: get_problem / get_problems_by_round /
   format_problem_message (รวมโจทย์รอบ 4 ที่มี buggy_algorithm)
2. คำสั่ง !problem (main.py): บังคับ register ก่อนใช้งาน, รหัสโจทย์ไม่มี,
   รหัสโจทย์ถูกต้อง (ส่งข้อความ + บันทึก log)

วิธีรัน (จากโฟลเดอร์หลักของโปรเจกต์):
    python -m unittest tests.test_problem_bank -v
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
from services.problem_service import (  # noqa: E402
    get_problem,
    get_problems_by_round,
    format_problem_message,
)
from services.registry_service import register_student  # noqa: E402


SAMPLE_PROBLEMS = [
    {
        "id": "P01",
        "round": 1,
        "lg": ["LG02", "LG03", "LG04"],
        "title": "ชุดของขวัญปฐมนิเทศ",
        "situation": "สถานการณ์ทดสอบ P01",
        "input": "จำนวนชุดของขวัญ",
        "process": "คำนวณจำนวนสิ่งของ",
        "output": "จำนวนสิ่งของทั้งหมด",
        "structure": "Sequence",
        "buggy_algorithm": None,
        "bug_type": None,
        "bug_location": None,
        "edge_case": None
    },
    {
        "id": "P04",
        "round": 2,
        "lg": ["LG02", "LG03", "LG04"],
        "title": "ค่าใช้บริการห้องพิมพ์",
        "situation": "สถานการณ์ทดสอบ P04",
        "input": "จำนวนหน้า, ราคาต่อหน้า",
        "process": "คำนวณค่าบริการและส่วนลด",
        "output": "ค่าบริการสุทธิ",
        "structure": "Decision",
        "buggy_algorithm": None,
        "bug_type": None,
        "bug_location": None,
        "edge_case": "20 หน้าพอดี"
    },
    {
        "id": "P10",
        "round": 4,
        "lg": ["LG05", "LG07"],
        "title": "ตรวจสอบการคำนวณค่าส่งพัสดุ",
        "situation": "สถานการณ์ทดสอบ P10",
        "input": "น้ำหนักพัสดุ",
        "process": "ตรวจสอบเงื่อนไขน้ำหนักแล้วกำหนดค่าจัดส่ง",
        "output": "ค่าจัดส่ง",
        "structure": "Decision",
        "buggy_algorithm": (
            "1. เริ่มต้น\n"
            "2. รับค่า weight\n"
            "3. ถ้า weight < 2\n"
            "      shipping = 40\n"
            "   มิฉะนั้น\n"
            "      shipping = 60\n"
            "4. แสดงค่า shipping\n"
            "5. สิ้นสุด"
        ),
        "bug_type": "เงื่อนไขผิด",
        "bug_location": "บรรทัดที่ 3 ใช้ < แทน ≤",
        "edge_case": "weight = 2"
    }
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
    def __init__(self, user_id):
        self.id = user_id
        self.bot = False

    def __str__(self):
        return f"tester#{self.id}"


class FakeCtx:
    def __init__(self, channel, author):
        self.channel = channel
        self.author = author

    async def send(self, text=None, **kwargs):
        return await self.channel.send(text, **kwargs)


class ProblemServiceTest(unittest.TestCase):
    """งานที่ 1: services/problem_service.py ล้วน ๆ ไม่ผ่าน Discord"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.bank_path = os.path.join(self.tmpdir, "problem_bank.json")

        with open(self.bank_path, "w", encoding="utf-8") as file:
            json.dump(SAMPLE_PROBLEMS, file, ensure_ascii=False)

        self.bank_patch = patch.object(
            problem_service, "PROBLEM_BANK_PATH", self.bank_path
        )
        self.bank_patch.start()

    def tearDown(self):
        self.bank_patch.stop()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_get_problem_found(self):
        found = get_problem("P01")

        self.assertIsNotNone(found)
        self.assertEqual(found["title"], "ชุดของขวัญปฐมนิเทศ")

    def test_get_problem_case_insensitive(self):
        found = get_problem("p01")

        self.assertIsNotNone(found)
        self.assertEqual(found["id"], "P01")

    def test_get_problem_not_found_returns_none(self):
        self.assertIsNone(get_problem("P99"))
        self.assertIsNone(get_problem(""))
        self.assertIsNone(get_problem(None))

    def test_get_problems_by_round(self):
        round1 = get_problems_by_round(1)

        self.assertEqual(len(round1), 1)
        self.assertEqual(round1[0]["id"], "P01")

    def test_get_problems_by_round_no_match_returns_empty_list(self):
        self.assertEqual(get_problems_by_round(99), [])

    def test_format_problem_message_contains_core_fields(self):
        message = format_problem_message(get_problem("P04"))

        self.assertIn("P04", message)
        self.assertIn("ค่าใช้บริการห้องพิมพ์", message)
        self.assertIn("สถานการณ์ทดสอบ P04", message)
        self.assertIn("จำนวนหน้า, ราคาต่อหน้า", message)
        self.assertIn("คำนวณค่าบริการและส่วนลด", message)
        self.assertIn("ค่าบริการสุทธิ", message)
        self.assertIn("Decision", message)

    def test_format_problem_message_round4_shows_buggy_algorithm(self):
        message = format_problem_message(get_problem("P10"))

        self.assertIn("weight < 2", message)
        # bug_type / bug_location ต้องไม่ถูกเฉลยในข้อความที่ส่งให้ผู้เรียน
        self.assertNotIn("เงื่อนไขผิด", message)
        self.assertNotIn("บรรทัดที่ 3", message)

    def test_format_problem_message_round1_has_no_buggy_algorithm_section(self):
        message = format_problem_message(get_problem("P01"))

        self.assertNotIn("Algorithm ที่ต้องตรวจสอบ", message)

    def test_format_problem_message_none_returns_error_text(self):
        self.assertIn("ไม่พบ", format_problem_message(None))


class ProblemCommandTest(unittest.TestCase):
    """งานที่ 2: คำสั่ง !problem ผ่าน main.py"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

        self.bank_path = os.path.join(self.tmpdir, "problem_bank.json")
        with open(self.bank_path, "w", encoding="utf-8") as file:
            json.dump(SAMPLE_PROBLEMS, file, ensure_ascii=False)

        self.bank_patch = patch.object(
            problem_service, "PROBLEM_BANK_PATH", self.bank_path
        )
        self.bank_patch.start()

        self.registry_path = os.path.join(
            self.tmpdir, "student_registry.json"
        )
        self.registry_patch = patch.object(
            registry_service, "REGISTRY_PATH", self.registry_path
        )
        self.registry_patch.start()

        self.problem_log_path = os.path.join(
            self.tmpdir, "problem_logs.json"
        )
        self.problem_log_patch = patch.object(
            logger, "PROBLEM_LOG_PATH", self.problem_log_path
        )
        self.problem_log_patch.start()

        self.channel = FakeChannel()
        self.author = FakeAuthor(7001)
        self.ctx = FakeCtx(self.channel, self.author)

    def tearDown(self):
        self.bank_patch.stop()
        self.registry_patch.stop()
        self.problem_log_patch.stop()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _problem(self, problem_id):
        asyncio.run(main.problem.callback(self.ctx, problem_id=problem_id))

    def test_problem_blocked_when_not_registered(self):
        self._problem("P01")

        self.assertIn("ลงทะเบียนก่อนใช้งาน", self.channel.sent[-1])
        self.assertFalse(os.path.exists(self.problem_log_path))

    def test_problem_unknown_id_shows_error_with_range_hint(self):
        register_student(self.author.id, "S-7001")

        self._problem("P99")

        self.assertIn("ไม่พบโจทย์", self.channel.sent[-1])
        self.assertIn("P01-P15", self.channel.sent[-1])
        self.assertFalse(os.path.exists(self.problem_log_path))

    def test_problem_valid_id_sends_message_and_logs(self):
        register_student(self.author.id, "S-7001")

        self._problem("P01")

        self.assertIn("ชุดของขวัญปฐมนิเทศ", self.channel.sent[-1])

        with open(self.problem_log_path, encoding="utf-8") as file:
            logs = json.load(file)

        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["problem_id"], "P01")
        self.assertEqual(logs[0]["round"], 1)
        self.assertEqual(logs[0]["student_id"], "S-7001")
        self.assertEqual(logs[0]["user_id"], str(self.author.id))

    def test_problem_missing_id_prompts_usage(self):
        register_student(self.author.id, "S-7001")

        self._problem(None)

        self.assertIn("ระบุรหัสโจทย์", self.channel.sent[-1])
        self.assertFalse(os.path.exists(self.problem_log_path))


if __name__ == "__main__":
    unittest.main()
