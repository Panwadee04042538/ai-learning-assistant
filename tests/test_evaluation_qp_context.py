"""
ทดสอบว่า Evaluation QP ของ !alg session (มาจาก !problem + !alg) ถามเกี่ยวกับ
Algorithm ที่นักเรียนเพิ่งส่งไปจริง ไม่ใช่คำถามที่ยังพูดถึงขั้นก่อนออกแบบ
Algorithm (เช่น "พร้อมนำไปออกแบบ Algorithm หรือไม่")

Backlog: LG02 เป็น Learning Goal หลัก (lg_tags[0]) ของโจทย์ส่วนใหญ่ใน
Problem Bank (P01-P09, P13-P15) และ Evaluation phase ของทุก session ที่ใช้
!problem + !alg จะถูกถามหลังจากนักเรียนส่ง Algorithm แล้วเท่านั้น (ดู
pick_initial_session_phase_and_qp / _get_next_qp_after_algorithm ใน
main.py) แต่คำถาม Evaluation เดิมของ LG02 (Q09) ในไฟล์ QP.xlsx ถูกเขียน
ขึ้นสำหรับบริบท "ก่อน" ออกแบบ Algorithm (LG02 = วิเคราะห์ปัญหาก่อนออกแบบ
Algorithm) ทำให้ไม่ตรงบริบทเมื่อถูกใช้จริงหลังส่ง Algorithm

วิธีรัน (จากโฟลเดอร์หลักของโปรเจกต์):
    python -m unittest tests.test_evaluation_qp_context -v
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
from qp_service import get_qp_by_lg  # noqa: E402


# วลีเดิมที่ผิดบริบท: ถามว่า "พร้อม...ไปออกแบบ Algorithm" ทั้งที่ Algorithm
# ถูกส่งไปแล้วก่อนถึงขั้น Evaluation เสมอในทุก session ของ !problem + !alg
STALE_PRE_DESIGN_PHRASES = ["พร้อม", "ไปออกแบบ Algorithm"]


class Lg02EvaluationQuestionTextTest(unittest.TestCase):
    """ตรวจข้อความ Evaluation QP ของ LG02 ใน QP.xlsx โดยตรง"""

    def setUp(self):
        questions = get_qp_by_lg("LG02")
        evaluation_questions = [
            q for q in questions if q.get("phase") == "Evaluation"
        ]
        self.assertEqual(
            len(evaluation_questions), 1,
            "คาดว่า LG02 มี Evaluation QP ข้อเดียวตาม QP.xlsx",
        )
        self.qp = evaluation_questions[0]

    def test_no_longer_asks_readiness_to_design_algorithm(self):
        text = self.qp["system_question"]
        self.assertFalse(
            all(phrase in text for phrase in STALE_PRE_DESIGN_PHRASES),
            f"Evaluation QP ของ LG02 ยังถามว่าพร้อมไปออกแบบ Algorithm "
            f"หรือไม่ ทั้งที่ Algorithm ถูกส่งไปแล้ว: {text!r}",
        )

    def test_references_the_submitted_algorithm(self):
        text = self.qp["system_question"]
        self.assertIn(
            "Algorithm", text,
            "Evaluation QP ของ LG02 ควรอ้างอิงถึง Algorithm ที่ส่งไปตรง ๆ",
        )


SAMPLE_PROBLEMS = [
    {
        "id": "P-LG02",
        "round": 1,
        "lg": ["LG02", "LG03", "LG04"],
        "title": "โจทย์ทดสอบ LG02",
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
    id = 9301
    bot = False

    def __str__(self):
        return "tester#9301"


class FakeCtx:
    def __init__(self, channel, author):
        self.channel = channel
        self.author = author

    async def send(self, text=None, **kwargs):
        return await self.channel.send(text, **kwargs)


def fake_ai(prompt):
    return "ข้อความจำลองจาก AI"


class ProblemBankEvaluationPhaseEndToEndTest(unittest.TestCase):
    """
    จำลองรอบ !problem P-LG02 -> !alg (LG02 คือ lg_tags[0] เหมือนโจทย์ส่วน
    ใหญ่ใน Problem Bank จริง) จนถึงขั้น Evaluation แล้วตรวจข้อความคำถามที่
    ส่งจริงให้ผู้เรียนเห็น
    """

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
        registry_service.register_student(self.author.id, "S-9301")

    def tearDown(self):
        self.bank_patch.stop()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _answer(self, text):
        msg = FakeMessage(self.author, self.channel, text)
        asyncio.run(main.on_message(msg))

    def test_evaluation_question_shown_after_good_algorithm_matches_context(self):
        good_result = {
            "success": True, "understanding_level": "GOOD",
            "feedback": "ครบถ้วน", "strength": "ลำดับชัดเจน",
            "improvement": "-", "next_action": "COMPLETE",
            "response_type": "ALGORITHM_ANSWER",
        }

        with patch.object(main, "ask_ai", fake_ai), \
             patch.object(main, "evaluate_student_response",
                          lambda *a, **k: good_result):

            asyncio.run(main.problem.callback(self.ctx, problem_id="P-LG02"))
            asyncio.run(main.start_algorithm_flow(self.ctx, None))

            s = main.pending_learning_sessions.get(self.author.id)
            self.assertEqual(s["lg_id"], "LG02")
            self.assertEqual(s["phase"], "PLANNING_QP")

            self._answer("ต้องวิเคราะห์ข้อมูลนำเข้าก่อน")   # ตอบ Planning
            self._answer("1. รับค่า 2. คำนวณ 3. แสดงผล")     # Algorithm -> GOOD

        s = main.pending_learning_sessions.get(self.author.id)
        self.assertEqual(
            s["phase"], "EVALUATION_QP",
            "GOOD ต้องข้าม Monitoring ไปหา Evaluation เลย",
        )

        evaluation_question = s["active_qp"]["system_question"]
        joined = "\n".join(self.channel.sent)
        self.assertIn(evaluation_question, joined)

        self.assertFalse(
            all(phrase in evaluation_question
                for phrase in STALE_PRE_DESIGN_PHRASES),
            "คำถาม Evaluation ที่ส่งจริงยังถามว่าพร้อมไปออกแบบ Algorithm "
            "หรือไม่ ทั้งที่ Algorithm ถูกส่งและประเมินไปแล้ว",
        )
        self.assertIn("Algorithm", evaluation_question)


if __name__ == "__main__":
    unittest.main()
