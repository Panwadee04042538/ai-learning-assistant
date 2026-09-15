"""
ทดสอบลำดับการเรียนรู้ของบอตแบบออฟไลน์ (ไม่ต่อ Discord / ไม่เรียก AI จริง)

วิธีรัน (จากโฟลเดอร์หลักของโปรเจกต์):
    python -m unittest tests.test_practice_flow -v

ลำดับที่ทดสอบ (โหมดขอโจทย์ฝึก LG08):
    ขอโจทย์ → Planning QP → ส่ง Algorithm (PARTIAL)
    → Monitoring QP + คำใบ้ → ส่ง Algorithm (GOOD)
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
        main.pending_learning_sessions.clear()

        self.channel = FakeChannel()
        self.author = FakeAuthor()
        self.ctx = FakeCtx(self.channel, self.author)

    def tearDown(self):
        self.log_patch.stop()
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
            self.assertIsNotNone(s["session_id"], "โหมดฝึกต้องมี Learning Log")
            self.assertIsNotNone(s["hint_question_id"])

            self._answer("ต้องรับคะแนนแล้วคำนวณเกรด")      # ตอบ Planning QP
            self.assertEqual(self._session()["phase"], "ALGORITHM_ANSWER")

            self._answer("1. เริ่ม 2. รับคะแนน 3. จบ")       # PARTIAL
            s = self._session()
            self.assertEqual(s["phase"], "MONITORING_QP")
            self.assertEqual(s["hint_level"], 1)
            self.assertTrue(s.get("pending_hint_text"))

            self._answer("ขาดขั้นตอนแสดงผล")                 # ตอบ Monitoring QP
            joined = "\n".join(self.channel.sent)
            self.assertIn("คำใบ้", joined)

            self._answer("1. เริ่ม 2. รับคะแนน 3. คำนวณ 4. แสดงผล 5. จบ")  # GOOD
            self.assertEqual(self._session()["phase"], "EVALUATION_QP")

            self._answer("แก้ปัญหาได้ เพราะทดสอบกับตัวอย่างแล้ว")  # ตอบ Evaluation QP
            self.assertIsNone(self._session(), "Session ต้องถูกปิดเมื่อจบ")

        with open(self.log_path, encoding="utf-8") as f:
            logs = json.load(f)
        self.assertEqual(len(logs), 1)
        log = logs[0]
        self.assertEqual(log["final_status"], "COMPLETED")
        phases = [r["phase"] for r in log.get("metacognitive_responses", [])]
        self.assertEqual(phases, ["Planning", "Monitoring", "Evaluation"])
        self.assertEqual(len(log.get("hints_used", [])), 1)
        self.assertEqual(len(log.get("student_responses", [])), 2)

    def test_long_message_is_split(self):
        text = ("บรรทัดทดสอบ " * 50 + "\n") * 20
        asyncio.run(main.send_long_message(self.channel, text))
        self.assertGreater(len(self.channel.sent), 1)
        self.assertTrue(all(len(t) <= 2000 for t in self.channel.sent))


if __name__ == "__main__":
    unittest.main()
