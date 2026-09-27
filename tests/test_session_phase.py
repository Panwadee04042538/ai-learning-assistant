"""
ทดสอบว่า session ใหม่ที่เกิดจากคำสั่ง !alg (ทำโจทย์จาก Problem Bank)
เริ่มต้นที่ Phase ที่ถูกต้องตามดีไซน์ของ LG ที่แท็กไว้กับโจทย์นั้น ๆ

บั๊กเดิม: start_algorithm_flow() hardcode ให้ session ใหม่ทุกตัว
เริ่มที่ Phase=Evaluation เสมอ ไม่ว่า LG นั้นจะถูกออกแบบให้มี
Planning/Monitoring ก่อนหรือไม่ (ดู main.py: pick_initial_session_phase_and_qp)

วิธีรัน (จากโฟลเดอร์หลักของโปรเจกต์):
    python -m unittest tests.test_session_phase -v
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
import main  # noqa: E402
from qp_service import get_qp_by_lg  # noqa: E402
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
    id = 555
    bot = False

    def __str__(self):
        return "tester#0002"


class FakeCtx:
    def __init__(self, channel, author):
        self.channel = channel
        self.author = author

    async def send(self, text=None, **kwargs):
        return await self.channel.send(text, **kwargs)


class InitialSessionPhaseTest(unittest.TestCase):
    """ทดสอบ pick_initial_session_phase_and_qp() ล้วน ๆ ไม่ต้องพึ่ง Discord"""

    def test_lg_with_planning_starts_at_planning(self):
        # LG02 ถูกออกแบบให้มีครบ Planning -> Monitoring -> Evaluation
        self.assertTrue(main._lg_has_phase_by_design("LG02", "Planning"))

        phase, qp = main.pick_initial_session_phase_and_qp("LG02")

        self.assertEqual(phase, "Planning")
        self.assertIsNotNone(qp)
        self.assertEqual(qp.get("lg_id"), "LG02")

    def test_lg_without_planning_falls_back_in_order(self):
        # LG01 ถูกออกแบบให้มีเฉพาะขั้น Evaluation (ไม่มี Planning/Monitoring)
        self.assertFalse(main._lg_has_phase_by_design("LG01", "Planning"))
        self.assertFalse(main._lg_has_phase_by_design("LG01", "Monitoring"))
        self.assertTrue(main._lg_has_phase_by_design("LG01", "Evaluation"))

        phase, qp = main.pick_initial_session_phase_and_qp("LG01")

        self.assertEqual(phase, "Evaluation")
        self.assertIsNotNone(qp)

    def test_lg_missing_designed_planning_data_logs_warning(self):
        # จำลองกรณี LG02 ถูกออกแบบให้มี Planning แต่คำถาม Planning
        # ทั้งหมดถูก exclude ไปหมด (เสมือนข้อมูลขาดหาย) -> ต้อง fallback
        # ไป Monitoring และพิมพ์ Warning ออกมา
        planning_qids = [
            q["question_id"]
            for q in get_qp_by_lg("LG02")
            if q.get("phase") == "Planning"
        ]

        with patch("builtins.print") as mock_print:
            phase, qp = main.pick_initial_session_phase_and_qp(
                "LG02", exclude_question_ids=planning_qids
            )

        self.assertEqual(phase, "Monitoring")

        warned = any(
            "SESSION PHASE WARNING" in str(call.args[0])
            for call in mock_print.call_args_list
        )
        self.assertTrue(warned, "ควร log warning เมื่อ Planning ที่ควรมีกลับหาไม่พบ")


class StartAlgorithmFlowPhaseTest(unittest.TestCase):
    """ทดสอบผ่าน start_algorithm_flow() จริง (เหมือน !alg แต่ไม่ต่อ Discord)"""

    def setUp(self):
        # ใช้ไฟล์ log ชั่วคราว ไม่ให้ทับ learning_logs.json ตัวจริง
        self.tmpdir = tempfile.mkdtemp()
        main.pending_learning_sessions.clear()
        main.active_problem_context.clear()
        self.channel = FakeChannel()
        self.author = FakeAuthor()
        self.ctx = FakeCtx(self.channel, self.author)
        registry_service.register_student(self.author.id, "S-0003")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _session(self):
        return main.pending_learning_sessions.get(self.author.id)

    def test_new_session_starts_at_planning_for_lg02_tagged_problem(self):
        """
        โจทย์ที่แท็ก LG02 (ซึ่งมีขั้น Planning ตามดีไซน์) ต้องสร้าง
        session ใหม่ที่ phase == PLANNING_QP ไม่ใช่ EVALUATION_QP
        (นี่คือ regression test ของบั๊กที่ session ใหม่เริ่มผิด Phase)
        """
        main.active_problem_context[self.author.id] = {
            "id": "P-LG02", "lg": ["LG02"], "situation": "สถานการณ์ทดสอบ",
        }

        asyncio.run(main.start_algorithm_flow(self.ctx, None))

        session = self._session()
        self.assertIsNotNone(session, "ควรมี session ใหม่ถูกสร้างขึ้น")
        self.assertEqual(session["lg_id"], "LG02")
        self.assertEqual(
            session["phase"],
            "PLANNING_QP",
            "Session ใหม่ของ LG ที่มีขั้น Planning ต้องเริ่มที่ PLANNING_QP",
        )

    def test_new_session_for_lg_without_planning(self):
        """
        โจทย์ที่แท็ก LG01 (มีเฉพาะขั้น Evaluation ตามดีไซน์) ควรเริ่มที่
        EVALUATION_QP ได้ตามปกติ เพราะไม่มี Planning/Monitoring ให้เริ่ม
        """
        main.active_problem_context[self.author.id] = {
            "id": "P-LG01", "lg": ["LG01"], "situation": "สถานการณ์ทดสอบ",
        }

        asyncio.run(main.start_algorithm_flow(self.ctx, None))

        session = self._session()
        self.assertIsNotNone(session)
        self.assertEqual(session["lg_id"], "LG01")
        self.assertEqual(session["phase"], "EVALUATION_QP")


if __name__ == "__main__":
    unittest.main()
