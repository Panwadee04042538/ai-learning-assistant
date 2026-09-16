"""
ทดสอบคำสั่ง !warmup และ !wrapup (Backlog #8)

LG01 มีเฉพาะขั้น Evaluation ใน QP.xlsx จึงใช้เป็นจุดเปิดคาบ (!warmup)
และปิดคาบ (!wrapup) แทนกิจกรรมหลัก

!warmup: บรรยายสั้น ๆ เรื่อง Algorithm ก่อน แล้วค่อยถามคำถามเช็คความเข้าใจ
         จาก QP.xlsx ของ LG01
!wrapup: ถามคำถามสะท้อนคิดจาก QP.xlsx ของ LG01 (ข้อที่ต่างจาก warmup ถ้าเป็นไปได้)
         แล้วสรุปสั้น ๆ ว่าเรียนรู้อะไรจากคาบนี้

วิธีรัน (จากโฟลเดอร์หลักของโปรเจกต์):
    python -m unittest tests.test_warmup_wrapup -v
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
    id = 8801
    bot = False

    def __str__(self):
        return "tester#8801"


class FakeCtx:
    def __init__(self, channel, author):
        self.channel = channel
        self.author = author

    async def send(self, text=None, **kwargs):
        return await self.channel.send(text, **kwargs)


class WarmupWrapupTest(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

        self.log_path = os.path.join(self.tmpdir, "learning_logs.json")
        self.log_patch = patch.object(logger, "LOG_PATH", self.log_path)
        self.log_patch.start()

        self.registry_path = os.path.join(
            self.tmpdir, "student_registry.json"
        )
        self.registry_patch = patch.object(
            registry_service, "REGISTRY_PATH", self.registry_path
        )
        self.registry_patch.start()

        main.pending_learning_sessions.clear()
        main.lg01_opening_history.clear()

        self.channel = FakeChannel()
        self.author = FakeAuthor()
        self.ctx = FakeCtx(self.channel, self.author)

        registry_service.register_student(self.author.id, "S-8801")

    def tearDown(self):
        self.log_patch.stop()
        self.registry_patch.stop()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _warmup(self):
        asyncio.run(main.warmup.callback(self.ctx))

    def _wrapup(self):
        asyncio.run(main.wrapup.callback(self.ctx))

    def _reply(self, text):
        msg = FakeMessage(self.author, self.channel, text)
        asyncio.run(main.on_message(msg))

    def _session(self):
        return main.pending_learning_sessions.get(self.author.id)

    # --------------------------------------------------
    # Registration gate
    # --------------------------------------------------

    def test_warmup_blocked_when_not_registered(self):
        # ล้าง registry เพื่อทดสอบผู้เรียนที่ยังไม่ลงทะเบียน
        os.remove(self.registry_path)

        self._warmup()

        self.assertIn("ลงทะเบียนก่อนใช้งาน", self.channel.sent[-1])
        self.assertIsNone(self._session())

    def test_wrapup_blocked_when_not_registered(self):
        os.remove(self.registry_path)

        self._wrapup()

        self.assertIn("ลงทะเบียนก่อนใช้งาน", self.channel.sent[-1])
        self.assertIsNone(self._session())

    # --------------------------------------------------
    # !warmup: บรรยายก่อน -> ถามคำถามจาก QP.xlsx
    # --------------------------------------------------

    def test_warmup_describes_algorithm_before_asking(self):
        self._warmup()

        sent = self.channel.sent[-1]
        intro_pos = sent.find("Algorithm คือ")
        question_pos = sent.find(
            self._session()["active_qp"]["system_question"]
        )

        self.assertNotEqual(intro_pos, -1, "ต้องมีคำบรรยายเรื่อง Algorithm")
        self.assertNotEqual(question_pos, -1, "ต้องมีคำถามเช็คความเข้าใจ")
        self.assertLess(
            intro_pos, question_pos,
            "ต้องบรรยายก่อนแล้วค่อยถาม ไม่ใช่ถามก่อนแล้วค่อยบรรยาย"
        )

    def test_warmup_creates_session_from_lg01_evaluation_qp(self):
        self._warmup()

        session = self._session()
        self.assertIsNotNone(session)
        self.assertEqual(session["phase"], "LG01_WARMUP_QP")
        self.assertEqual(session["lg_id"], "LG01")
        self.assertEqual(session["active_qp"]["phase"], "Evaluation")

    def test_warmup_logs_start(self):
        self._warmup()

        with open(self.log_path, encoding="utf-8") as f:
            logs = json.load(f)

        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["learning_goal"]["lg_id"], "LG01")

    def test_warmup_reply_gives_short_feedback_and_closes_session(self):
        self._warmup()

        with patch.object(main, "ask_ai", lambda prompt: "สะท้อนคำตอบแบบสั้น ๆ"):
            self._reply("Algorithm คือลำดับขั้นตอนการแก้ปัญหา")

        self.assertIsNone(
            self._session(), "Session ต้องถูกลบหลังตอบคำถาม warmup แล้ว"
        )

        joined = "\n".join(self.channel.sent)
        self.assertIn("สะท้อนคำตอบแบบสั้น ๆ", joined)
        self.assertIn("เริ่มคาบเรียน", joined)

        with open(self.log_path, encoding="utf-8") as f:
            logs = json.load(f)
        self.assertEqual(logs[0]["final_status"], "COMPLETED")

    # --------------------------------------------------
    # !wrapup: ถามคำถามสะท้อนคิด -> สรุปสิ่งที่เรียนรู้
    # --------------------------------------------------

    def test_wrapup_creates_session_from_lg01_evaluation_qp(self):
        self._wrapup()

        session = self._session()
        self.assertIsNotNone(session)
        self.assertEqual(session["phase"], "LG01_WRAPUP_QP")
        self.assertEqual(session["lg_id"], "LG01")
        self.assertEqual(session["active_qp"]["phase"], "Evaluation")

    def test_wrapup_prefers_a_different_question_than_warmup(self):
        self._warmup()
        warmup_question_id = self._session()["active_qp"]["question_id"]

        # !warmup ปิด session ของตัวเองไปแล้วหลังตอบ แต่ประวัติคำถามที่ใช้
        # ยังถูกเก็บไว้ให้ !wrapup อ้างอิง
        with patch.object(main, "ask_ai", lambda prompt: "สะท้อนคำตอบแบบสั้น ๆ"):
            self._reply("Algorithm คือลำดับขั้นตอนการแก้ปัญหา")

        self._wrapup()
        wrapup_question_id = self._session()["active_qp"]["question_id"]

        self.assertNotEqual(
            warmup_question_id, wrapup_question_id,
            "ควรใช้คำถามข้อที่ต่างจาก warmup ถ้าเป็นไปได้"
        )

    def test_wrapup_logs_start(self):
        self._wrapup()

        with open(self.log_path, encoding="utf-8") as f:
            logs = json.load(f)

        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["learning_goal"]["lg_id"], "LG01")

    def test_wrapup_reply_gives_summary_and_closes_session(self):
        self._wrapup()

        with patch.object(main, "ask_ai", lambda prompt: "สรุปสิ่งที่เรียนรู้แบบสั้น ๆ"):
            self._reply("วันนี้เข้าใจเรื่อง Algorithm มากขึ้น")

        self.assertIsNone(
            self._session(), "Session ต้องถูกลบหลังตอบคำถาม wrapup แล้ว"
        )

        joined = "\n".join(self.channel.sent)
        self.assertIn("สรุปสิ่งที่เรียนรู้แบบสั้น ๆ", joined)
        self.assertIn("สรุปการเรียนรู้", joined)

        with open(self.log_path, encoding="utf-8") as f:
            logs = json.load(f)
        self.assertEqual(logs[0]["final_status"], "COMPLETED")


if __name__ == "__main__":
    unittest.main()
