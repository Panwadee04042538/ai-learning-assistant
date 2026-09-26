"""
ทดสอบลำดับการเรียนรู้ของบอตแบบออฟไลน์ (ไม่ต่อ Discord / ไม่เรียก AI จริง)

วิธีรัน (จากโฟลเดอร์หลักของโปรเจกต์):
    python -m unittest tests.test_practice_flow -v

ลำดับที่ทดสอบ (โหมดขอโจทย์ฝึก LG08):
    ขอโจทย์ → Planning QP (1 ข้อ) → ส่ง Algorithm (PARTIAL)
    → Monitoring QP (1 ข้อ) + คำใบ้ → ส่ง Algorithm (GOOD)
    → Evaluation QP → จบ Session และบันทึก Log ครบ
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

        main.pending_learning_sessions.clear()

        self.channel = FakeChannel()
        self.author = FakeAuthor()
        self.ctx = FakeCtx(self.channel, self.author)

        registry_service.register_student(self.author.id, "S-0001")

    def tearDown(self):
        self.log_patch.stop()
        self.registry_patch.stop()
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

    def test_non_practice_question_does_not_start_practice(self):
        """คำถามทั่วไปต้องไม่ถูกบังคับเข้าโหมดโจทย์ฝึก"""
        with patch.object(main, "ask_ai", fake_ai), \
             patch.object(main, "ask_grounded_answer",
                          lambda q, c: "คำอธิบายจำลอง"):
            asyncio.run(main.start_algorithm_flow(self.ctx, "Algorithm คืออะไร"))

        session = self._session()
        if session is not None:
            self.assertFalse(session.get("practice_mode", False))

    def test_full_practice_flow(self):
        """
        LG08 (โหมดฝึก) มี Planning 1 ข้อ (ถามครั้งเดียวต่อ session),
        Monitoring 1 ข้อ, Evaluation 1 ข้อ ตาม QP.xlsx เส้นทางที่ถูกต้องคือ:

        Planning (1 ข้อ) -> ALGORITHM_ANSWER (PARTIAL + hint เป็น sub-turn)
        -> ALGORITHM_ANSWER (GOOD) -> Monitoring (1 ข้อ, หลังเห็น Algorithm
        แล้ว) -> Evaluation (1 ข้อ) -> จบ Session

        Monitoring ต้องถามหลังประเมิน Algorithm แล้วเท่านั้น (ไม่ใช่ก่อนส่ง
        Algorithm เหมือนเดิม) รวมเป็น 3 "คำถามหลัก" ต่อ session:
        Planning / Monitoring / Evaluation แต่ละ transition ต้องส่ง
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

            asyncio.run(main.start_algorithm_flow(self.ctx, "ขอโจทย์ฝึกหน่อย"))
            s = self._session()
            self.assertIsNotNone(s)
            self.assertEqual(s["phase"], "PLANNING_QP")
            self.assertEqual(s["question_id"], "PRACTICE")
            self.assertIsNotNone(s["session_id"], "โหมดฝึกต้องมี Learning Log")
            self.assertIsNone(
                s["hint_question_id"],
                "ยังไม่ตอบ Planning จึงยังไม่ควรมี hint_question_id",
            )
            self.assertNotIn(
                "planning_questions", s,
                "ตัด planning_questions loop ออกแล้ว ไม่ควรมี key นี้อีก",
            )
            self.assertEqual(s["main_question_count"], 1)

            # --------------------------------------------------
            # Planning: ถามครั้งเดียว แล้วไปเขียน Algorithm ทันที
            # (ไม่ใช่ไป Monitoring ก่อนเหมือนเดิม)
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

            # --------------------------------------------------
            # ALGORITHM_ANSWER: PARTIAL -> hint เป็น sub-turn
            # (ต้องไม่แวะ Monitoring ไม่นับเป็นคำถามหลักเพิ่ม)
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
            # ALGORITHM_ANSWER -> GOOD: ต้องไป Monitoring ก่อน Evaluation
            # (Monitoring ย้ายมาอยู่หลังเห็น Algorithm จริงแล้ว)
            # --------------------------------------------------
            self._answer("1. เริ่ม 2. รับคะแนน 3. คำนวณ 4. แสดงผล 5. จบ")  # GOOD
            s = self._session()
            self.assertEqual(
                s["phase"], "MONITORING_QP_POST_ALGORITHM",
                "GOOD ต้องไปตรวจสอบ Algorithm (Monitoring) ก่อน ไม่ใช่ไป "
                "Evaluation ตรง ๆ",
            )
            self.assertEqual(s["main_question_count"], 2)

            # feedback ของผลประเมิน GOOD กับคำถาม Monitoring ต้องแยกคนละข้อความ
            good_feedback_msg = self.channel.sent[-2]
            monitoring_question_msg = self.channel.sent[-1]
            self.assertIn("ผลการวิเคราะห์คำตอบ", good_feedback_msg)
            self.assertIn("🔍", monitoring_question_msg)

            # --------------------------------------------------
            # Monitoring (หลัง Algorithm): ตอบแล้วต้องไป Evaluation ต่อ
            # ไม่ใช่กลับไปเขียน Algorithm ซ้ำ
            # --------------------------------------------------
            self._answer("ตรวจสอบแล้วครบทุกขั้นตอน")        # ตอบ Monitoring
            s = self._session()
            self.assertEqual(s["phase"], "EVALUATION_QP")
            self.assertEqual(s["main_question_count"], 3)

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
            ["Planning", "Monitoring", "Evaluation"],
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
