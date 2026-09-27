"""
ทดสอบระบบลงทะเบียนนักเรียน (Student Registry):

1. services/registry_service.py: register_student / get_student_id /
   is_registered
2. คำสั่ง !register (main.py): ลงทะเบียนใหม่, ลงทะเบียนซ้ำรหัสเดิม,
   ขอเปลี่ยนรหัส (ต้องยืนยันก่อน), รหัสซ้ำกับ user อื่น
3. บังคับลงทะเบียนก่อนใช้งาน: !alg (ผ่าน start_algorithm_flow) และ
   ข้อความ plain text ทั่วไป (ผ่าน on_message)
   (!alg ต้องมีโจทย์ที่เลือกไว้ผ่าน !problem ก่อน จึงจำลองด้วยการตั้งค่า
   main.active_problem_context ตรง ๆ แทนการเรียก !problem จริง)

วิธีรัน (จากโฟลเดอร์หลักของโปรเจกต์):
    python -m unittest tests.test_registry -v
"""

import asyncio
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch, AsyncMock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault("TYPHOON_API_KEY", "test")
os.environ.setdefault("GEMINI_API_KEY", "test")
os.environ.setdefault("DISCORD_TOKEN", "test")

import logger  # noqa: E402
import main    # noqa: E402
import services.registry_service as registry_service  # noqa: E402
from services.registry_service import (  # noqa: E402
    get_student_id,
    is_registered,
    register_student,
)


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


class RegistryServiceTest(unittest.TestCase):
    """งานที่ 3: helper functions ล้วน ๆ ไม่ผ่าน Discord"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_get_student_id_returns_none_when_not_registered(self):
        self.assertIsNone(get_student_id(111))
        self.assertFalse(is_registered(111))

    def test_register_creates_file_and_folder_if_missing(self):
        self.assertEqual(registry_service.get_all_students(), {})

        ok = register_student(111, "S-1001")

        self.assertTrue(ok)
        self.assertEqual(registry_service.get_all_students(), {"111": "S-1001"})
        self.assertEqual(get_student_id(111), "S-1001")
        self.assertTrue(is_registered(111))

    def test_register_same_user_can_change_student_id(self):
        register_student(111, "S-1001")
        ok = register_student(111, "S-2002")

        self.assertTrue(ok)
        self.assertEqual(get_student_id(111), "S-2002")

    def test_register_duplicate_student_id_for_other_user_fails(self):
        register_student(111, "S-1001")
        ok = register_student(222, "S-1001")

        self.assertFalse(ok)
        # user 222 ต้องไม่ถูกบันทึกว่าลงทะเบียนแล้ว
        self.assertIsNone(get_student_id(222))
        # user 111 ยังคงมีรหัสเดิมอยู่ ไม่ถูกกระทบ
        self.assertEqual(get_student_id(111), "S-1001")


class RegisterCommandTest(unittest.TestCase):
    """งานที่ 1: คำสั่ง !register ผ่าน main.py"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        main.pending_registration_changes.clear()

        self.channel = FakeChannel()
        self.author = FakeAuthor(5001)
        self.ctx = FakeCtx(self.channel, self.author)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _register(self, student_id):
        asyncio.run(main.register.callback(self.ctx, student_id=student_id))

    def _reply(self, text):
        msg = FakeMessage(self.author, self.channel, text)
        asyncio.run(main.on_message(msg))

    def test_register_new_student_succeeds(self):
        self._register("12345")

        self.assertEqual(get_student_id(self.author.id), "12345")
        self.assertIn("ลงทะเบียนสำเร็จ", self.channel.sent[-1])

    def test_register_same_code_again_is_a_no_op(self):
        self._register("12345")
        self._register("12345")

        self.assertEqual(get_student_id(self.author.id), "12345")
        self.assertIn("ไว้แล้ว", self.channel.sent[-1])

    def test_register_change_requires_confirmation(self):
        self._register("12345")
        self._register("67890")

        # ยังไม่เปลี่ยนจนกว่าจะยืนยัน
        self.assertEqual(get_student_id(self.author.id), "12345")
        self.assertIn("ยืนยันเพื่อเปลี่ยน", self.channel.sent[-1])
        self.assertIn(self.author.id, main.pending_registration_changes)

        self._reply("ยืนยัน")

        self.assertEqual(get_student_id(self.author.id), "67890")
        self.assertNotIn(self.author.id, main.pending_registration_changes)

    def test_register_change_declined_keeps_old_code(self):
        self._register("12345")
        self._register("67890")
        self._reply("ไม่เอา")

        self.assertEqual(get_student_id(self.author.id), "12345")
        self.assertNotIn(self.author.id, main.pending_registration_changes)

    def test_register_duplicate_student_id_shows_error(self):
        other = FakeAuthor(5002)
        register_student(other.id, "99999")

        self._register("99999")

        self.assertIsNone(get_student_id(self.author.id))
        self.assertIn("ติดต่อครู", self.channel.sent[-1])


class RegistrationRequiredTest(unittest.TestCase):
    """งานที่ 2: บังคับ register ก่อนใช้งานทุก entry point"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        main.pending_learning_sessions.clear()
        main.pending_registration_changes.clear()
        main.active_problem_context.clear()

        self.channel = FakeChannel()
        self.author = FakeAuthor(6001)
        self.ctx = FakeCtx(self.channel, self.author)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_alg_blocked_when_not_registered(self):
        with patch.object(main, "ask_grounded_answer", lambda q, c: "mock"):
            asyncio.run(
                main.start_algorithm_flow(self.ctx, "Algorithm คืออะไร")
            )

        self.assertIsNone(main.pending_learning_sessions.get(self.author.id))
        self.assertIn("ลงทะเบียนก่อนใช้งาน", self.channel.sent[-1])
        self.assertIn("!register", self.channel.sent[-1])

    def test_alg_works_after_registering(self):
        register_student(self.author.id, "S-6001")
        main.active_problem_context[self.author.id] = {
            "id": "P01", "lg": ["LG02"], "situation": "สถานการณ์ทดสอบ",
        }

        asyncio.run(main.start_algorithm_flow(self.ctx, None))

        self.assertIsNotNone(main.pending_learning_sessions.get(self.author.id))

    def test_plain_message_blocked_when_not_registered(self):
        msg = FakeMessage(self.author, self.channel, "สวัสดีครับ")
        asyncio.run(main.on_message(msg))

        self.assertIn("ลงทะเบียนก่อนใช้งาน", self.channel.sent[-1])

    def test_register_command_itself_is_never_blocked(self):
        msg = FakeMessage(self.author, self.channel, "!register 12345")

        # !register ต้องผ่านไปยัง bot.process_commands ตามปกติ โดยไม่ถูก
        # gate ข้อความ "กรุณาลงทะเบียนก่อนใช้งาน" สกัดไว้ก่อน
        with patch.object(
            main.bot, "process_commands", new=AsyncMock()
        ) as mock_process_commands:
            asyncio.run(main.on_message(msg))

        mock_process_commands.assert_awaited_once_with(msg)
        self.assertEqual(
            self.channel.sent, [],
            "!register ต้องไม่ถูกกันด้วยข้อความบังคับลงทะเบียน",
        )

    def test_learning_log_records_student_id(self):
        register_student(self.author.id, "S-6001")
        main.active_problem_context[self.author.id] = {
            "id": "P01", "lg": ["LG02"], "situation": "สถานการณ์ทดสอบ",
        }

        asyncio.run(main.start_algorithm_flow(self.ctx, None))

        logs = logger.load_logs()

        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["student_id"], "S-6001")
        self.assertEqual(logs[0]["user_id"], str(self.author.id))


if __name__ == "__main__":
    unittest.main()
