"""
ทดสอบลำดับการเรียนรู้ของบอตแบบออฟไลน์ (ไม่ต่อ Discord / ไม่เรียก AI จริง)

วิธีรัน (จากโฟลเดอร์หลักของโปรเจกต์):
    python -m unittest tests.test_practice_flow -v

ลำดับที่ทดสอบ (!problem แล้วตามด้วย !alg ทำโจทย์จาก Problem Bank):
    !problem P.. -> !alg -> Planning QP (1 ข้อ) -> ส่ง Algorithm (PARTIAL)
    -> ส่ง Algorithm (GOOD) -> Evaluation QP -> จบ Session และบันทึก Log ครบ

หมายเหตุ: โหมด "ขอโจทย์ฝึก" แบบให้ AI แต่งโจทย์ LG08 สด ๆ (is_practice_request)
ถูกตัดออกแล้ว แทนที่ด้วย flow !problem -> !alg นี้
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

# ค่าจำลอง เพื่อให้ import โมดูลได้โดยไม่ต้องมี key จริง
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
        "situation": "สถานการณ์ทดสอบโจทย์ฝึก",
        "input": "ข้อมูลนำเข้าทดสอบ",
        "process": "ประมวลผลทดสอบ",
        "output": "ผลลัพธ์ทดสอบ",
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
    id = 999
    bot = False

    def __str__(self):
        return "tester#0001"


class FakeCtx:
    def __init__(self, channel, author):
        self.channel = channel
        self.author = author

    async def send(self, text=None, **kwargs):
        return await self.channel.send(text, **kwargs)


def fake_ai(prompt):
    return "ข้อความจำลองจาก AI"


class LearningFlowTest(unittest.TestCase):

    def setUp(self):
        # ใช้ไฟล์ log ชั่วคราว ไม่ให้ทับข้อมูลจริง
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.tmpdir, "learning_logs.json")
        self.log_patch = patch.object(logger, "LOG_PATH", self.log_path)
        self.log_patch.start()

        # ใช้ registry ชั่วคราว และลงทะเบียนผู้เรียนจำลองไว้ล่วงหน้า
        # (บอตบังคับ register ก่อนใช้งานทุก entry point)
        self.registry_path = os.path.join(
            self.tmpdir, "student_registry.json"
        )
        self.registry_patch = patch.object(
            registry_service, "REGISTRY_PATH", self.registry_path
        )
        self.registry_patch.start()

        self.bank_path = os.path.join(self.tmpdir, "problem_bank.json")
        with open(self.bank_path, "w", encoding="utf-8") as file:
            json.dump(SAMPLE_PROBLEMS, file, ensure_ascii=False)

        self.bank_patch = patch.object(
            problem_service, "PROBLEM_BANK_PATH", self.bank_path
        )
        self.bank_patch.start()

        self.problem_log_path = os.path.join(self.tmpdir, "problem_logs.json")
        self.problem_log_patch = patch.object(
            logger, "PROBLEM_LOG_PATH", self.problem_log_path
        )
        self.problem_log_patch.start()

        main.pending_learning_sessions.clear()
        main.active_problem_context.clear()

        self.channel = FakeChannel()
        self.author = FakeAuthor()
        self.ctx = FakeCtx(self.channel, self.author)

        registry_service.register_student(self.author.id, "S-0001")

    def tearDown(self):
        self.log_patch.stop()
        self.registry_patch.stop()
        self.bank_patch.stop()
        self.problem_log_patch.stop()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _answer(self, text):
        msg = FakeMessage(self.author, self.channel, text)
        asyncio.run(main.on_message(msg))

    def _session(self):
        return main.pending_learning_sessions.get(self.author.id)

    def test_qp_service_loads_lg08(self):
        for phase in ("Planning", "Monitoring", "Evaluation"):
            qp = main.get_session_qp("LG08", phase)
            self.assertIsNotNone(qp, f"ไม่พบ QP ของ LG08 {phase}")
            self.assertTrue(qp.get("system_question"))
            self.assertTrue(qp.get("question_id", "").startswith("Q"))

    def test_problem_command_sets_active_problem_for_alg(self):
        """!problem <id> ต้องบันทึกโจทย์ไว้ให้ !alg ใช้เริ่ม session ต่อได้"""
        asyncio.run(main.problem.callback(self.ctx, problem_id="P-LG08"))

        stored = main.active_problem_context.get(self.author.id)
        self.assertIsNotNone(stored)
        self.assertEqual(stored["id"], "P-LG08")

    def test_full_problem_bank_flow(self):
        """
        !problem P-LG08 แล้ว !alg เริ่ม Adaptive Learning Session จากโจทย์
        นั้น (แท็ก LG08) มี Planning 1 ข้อ (ถามครั้งเดียวต่อ session),
        Monitoring 1 ข้อ, Evaluation 1 ข้อ ตาม QP.xlsx เส้นทางที่ถูกต้องคือ:

        Planning (1 ข้อ) -> ALGORITHM_ANSWER (PARTIAL + hint เป็น sub-turn)
        -> ALGORITHM_ANSWER (GOOD) -> Evaluation (1 ข้อ) -> จบ Session

        GOOD ข้าม Monitoring ไปหา Evaluation เลย (ต่างจาก
        MAX_ATTEMPTS_REACHED ที่ยังแวะ Monitoring ก่อน ดู
        tests/test_monitoring_after_algorithm.py) แต่ละ transition ต้องส่ง
        feedback กับคำถาม/ขั้นตอนถัดไปแยกคนละข้อความ ไม่ใช่รวมกันในข้อความ
        เดียว
        """
        evaluations = iter([
            {"success": True, "understanding_level": "PARTIAL",
             "feedback": "ยังขาดขั้นตอนแสดงผล", "strength": "มีการรับข้อมูล",
             "improvement": "เพิ่มขั้นตอนแสดงผล", "next_action": "HINT",
             "response_type": "ALGORITHM_ANSWER"},
            {"success": True, "understanding_level": "GOOD",
             "feedback": "ครบถ้วน", "strength": "ลำดับชัดเจน",
             "improvement": "-", "next_action": "COMPLETE",
             "response_type": "ALGORITHM_ANSWER"},
        ])

        with patch.object(main, "ask_ai", fake_ai), \
             patch.object(main, "evaluate_student_response",
                          lambda *a, **k: next(evaluations)):

            asyncio.run(main.problem.callback(self.ctx, problem_id="P-LG08"))
            asyncio.run(main.start_algorithm_flow(self.ctx, None))

            s = self._session()
            self.assertIsNotNone(s)
            self.assertEqual(s["phase"], "PLANNING_QP")
            self.assertEqual(s["problem_id"], "P-LG08")
            self.assertEqual(s["lg_id"], "LG08")
            self.assertIsNotNone(s["session_id"], "ต้องมี Learning Log")
            self.assertIsNone(
                s["hint_question_id"],
                "ยังไม่ตอบ Planning จึงยังไม่ควรมี hint_question_id",
            )
            self.assertEqual(s["main_question_count"], 1)

            # --------------------------------------------------
            # Planning: ถามครั้งเดียว แล้วไปเขียน Algorithm ทันที
            # --------------------------------------------------
            self._answer("ต้องรับคะแนนแล้วคำนวณเกรด")      # ตอบ Planning ข้อเดียว
            s = self._session()
            self.assertEqual(
                s["phase"], "ALGORITHM_ANSWER",
                "Planning มีข้อเดียว ตอบแล้วต้องไปเขียน Algorithm ทันที",
            )
            self.assertEqual(
                s["hint_question_id"], "Q39",
                "ต้องผูก hint_question_id กับ Monitoring ของ LG นี้ไว้ล่วงหน้า "
                "แม้จะยังไม่ถาม Monitoring จริงตอนนี้ก็ตาม",
            )
            self.assertEqual(
                s["main_question_count"], 1,
                "Algorithm ยังไม่ถูกประเมิน จึงยังไม่นับเป็นคำถามหลักข้อใหม่",
            )

            # feedback ของ Planning กับ "ลองทำโจทย์" ต้องแยกคนละข้อความ
            planning_feedback_msg = self.channel.sent[-2]
            algorithm_prompt_msg = self.channel.sent[-1]
            self.assertIn("ข้อความจำลองจาก AI", planning_feedback_msg)
            self.assertNotIn("ลองทำโจทย์", planning_feedback_msg)
            self.assertIn("ลองทำโจทย์", algorithm_prompt_msg)
            self.assertIn("ใส่หมายเลขข้อให้ครบทุกขั้นตอน", algorithm_prompt_msg)
            self.assertIn("1. เริ่มต้น", algorithm_prompt_msg)

            # --------------------------------------------------
            # ALGORITHM_ANSWER: PARTIAL -> hint เป็น sub-turn
            # --------------------------------------------------
            self._answer("1. เริ่ม 2. รับคะแนน 3. จบ")       # PARTIAL
            s = self._session()
            self.assertEqual(
                s["phase"], "ALGORITHM_ANSWER",
                "PARTIAL ต้องเป็น sub-turn ไม่ใช่คำถามใหม่",
            )
            self.assertEqual(s["hint_level"], 1)
            self.assertEqual(s["main_question_count"], 1, "hint ไม่นับเพิ่ม")
            joined = "\n".join(self.channel.sent)
            self.assertIn("คำใบ้", joined)

            # --------------------------------------------------
            # ALGORITHM_ANSWER -> GOOD: ข้าม Monitoring ไปหา Evaluation เลย
            # --------------------------------------------------
            self._answer("1. เริ่ม 2. รับคะแนน 3. คำนวณ 4. แสดงผล 5. จบ")  # GOOD
            s = self._session()
            self.assertEqual(
                s["phase"], "EVALUATION_QP",
                "GOOD ต้องข้าม Monitoring ไปหา Evaluation เลย",
            )
            self.assertEqual(s["main_question_count"], 2)

            good_feedback_msg = self.channel.sent[-2]
            evaluation_question_msg = self.channel.sent[-1]
            self.assertIn("ผลการวิเคราะห์คำตอบ", good_feedback_msg)
            self.assertIn("🪞", evaluation_question_msg)

            self._answer("แก้ปัญหาได้ เพราะทดสอบกับตัวอย่างแล้ว")  # ตอบ Evaluation QP
            self.assertIsNone(self._session(), "Session ต้องถูกปิดเมื่อจบ")

        with open(self.log_path, encoding="utf-8") as f:
            logs = json.load(f)
        self.assertEqual(len(logs), 1)
        log = logs[0]
        self.assertEqual(log["final_status"], "COMPLETED")
        phases = [r["phase"] for r in log.get("metacognitive_responses", [])]
        self.assertEqual(
            phases,
            ["Planning", "Evaluation"],
            "GOOD ข้าม Monitoring ไปเลย จึงเหลือแค่ Planning กับ Evaluation",
        )
        self.assertEqual(len(log.get("hints_used", [])), 1)
        self.assertEqual(len(log.get("student_responses", [])), 2)

    def test_long_message_is_split(self):
        text = ("บรรทัดทดสอบ " * 50 + "\n") * 20
        asyncio.run(main.send_long_message(self.channel, text))
        self.assertGreater(len(self.channel.sent), 1)
        self.assertTrue(all(len(t) <= 2000 for t in self.channel.sent))


if __name__ == "__main__":
    unittest.main()
