"""
ทดสอบว่าผลจาก rule-based check (ขาดขั้น "จบ"/ขั้นแสดงผล -> PARTIAL ทันที
โดยไม่เรียก Typhoon) "ไม่นับ attempt" เพราะยังไม่ได้ประเมิน Logic จริง
เด็กจะได้ไม่โดน MAX_ATTEMPTS_REACHED จากการแค่ลืมขั้นบังคับ ส่วนคำตอบที่
ผ่าน rule-based แล้วและถูก Typhoon ประเมินจริงต้องนับ attempt ตามปกติ

ใช้ evaluate_student_response ตัวจริง (ไม่ mock) และให้ ask_evaluation
(Typhoon) ล้มทันทีถ้าถูกเรียกในเทสต์ที่ต้องเป็น rule-based ล้วน ๆ

วิธีรัน (จากโฟลเดอร์หลักของโปรเจกต์):
    python -m unittest tests.test_rule_based_attempts -v
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
    id = 9701
    bot = False

    def __str__(self):
        return "tester#9701"


def typhoon_must_not_be_called(prompt):
    raise AssertionError("rule-based check ต้องไม่เรียก Typhoon")


# ขาดทั้งขั้น "จบ" และขั้นแสดงผล -> rule-based PARTIAL
INCOMPLETE_ANSWER = "1. เริ่มต้น 2. รับค่า n 3. บวกเข้า total"


class _SessionTestBase(unittest.TestCase):
    """session จำลองที่รอคำตอบ Algorithm (max_attempts=2)"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.eval_patch = patch.object(
            main, "ask_evaluation", typhoon_must_not_be_called
        )
        self.eval_patch.start()

        main.pending_learning_sessions.clear()

        self.channel = FakeChannel()
        self.author = FakeAuthor()
        registry_service.register_student(self.author.id, "S-9701")

        main.pending_learning_sessions[self.author.id] = {
            "learning_goal": "LG02",
            "question": "โจทย์ทดสอบ",
            "algorithm_question": "โจทย์ทดสอบ",
            "ku_id": "KU01",
            "lg_id": "LG02",
            "question_id": "Q04",
            "qp_id": "QP02",
            "hint_question_id": "Q07",
            "attempt": 1,
            "max_attempts": 2,
            "hint_level": 0,
            "attempt_history": [],
            "qp_responses": [
                {"question_id": "Q04", "qp_id": "QP02", "phase": "PLANNING_QP"},
            ],
            "active_qp": None,
            "phase": "ALGORITHM_ANSWER",
            "main_question_count": 1,
            "reflection_shown": False,
            "expected_evidence": "",
            "session_id": "test-rule-based-attempts",
        }
        logger.add_learning_log(
            user_id=self.author.id, username=str(self.author),
            user_question="q",
        )
        logs = logger.load_logs()
        logs[0]["session_id"] = "test-rule-based-attempts"
        logger.save_logs(logs)

    def tearDown(self):
        self.eval_patch.stop()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _answer(self, text):
        msg = FakeMessage(self.author, self.channel, text)
        asyncio.run(main.on_message(msg))

    def _session(self):
        return main.pending_learning_sessions.get(self.author.id)


class RuleBasedRejectionDoesNotCountAttemptTest(_SessionTestBase):
    def test_rejection_does_not_increment_attempt(self):
        self._answer(INCOMPLETE_ANSWER)

        s = self._session()
        self.assertEqual(s["attempt"], 1)
        self.assertEqual(s["phase"], "ALGORITHM_ANSWER")

    def test_rejection_does_not_touch_history_or_hints(self):
        self._answer(INCOMPLETE_ANSWER)

        s = self._session()
        self.assertEqual(s["attempt_history"], [])
        self.assertEqual(s["hint_level"], 0)

    def test_rejection_does_not_increase_logged_attempt_count(self):
        self._answer(INCOMPLETE_ANSWER)

        logs = logger.load_logs()
        self.assertEqual(logs[0]["attempt_count"], 0)
        # แต่ยังบันทึกคำตอบไว้ให้ครูเห็นได้
        self.assertEqual(len(logs[0]["student_responses"]), 1)

    def test_feedback_tells_what_is_missing_and_that_it_does_not_count(self):
        self._answer(INCOMPLETE_ANSWER)

        joined = "\n".join(self.channel.sent)
        self.assertIn("ขาด 2 ขั้นตอนสำคัญ", joined)
        self.assertIn("ขาดขั้นแสดงผล", joined)
        self.assertIn("ขาดขั้นจบ", joined)
        self.assertIn("ยังไม่นับเป็นครั้งที่ตอบ", joined)

    def test_many_rejections_never_reach_max_attempts(self):
        for _ in range(5):
            self._answer(INCOMPLETE_ANSWER)

        s = self._session()
        self.assertIsNotNone(s, "session ต้องไม่ถูกปิดเพราะลืมขั้นบังคับ")
        self.assertEqual(s["attempt"], 1)
        self.assertEqual(s["phase"], "ALGORITHM_ANSWER")
        self.assertNotIn("pending_final_status", s)


class TyphoonEvaluatedAnswerStillCountsAttemptTest(_SessionTestBase):
    """คำตอบที่ผ่าน rule-based แล้วถูก Typhoon ประเมินจริง ต้องนับ attempt"""

    COMPLETE_ANSWER = (
        "1. เริ่มต้น 2. รับค่า n 3. บวกเข้า total 4. แสดง total 5. จบ"
    )

    def setUp(self):
        super().setUp()
        self.eval_patch.stop()
        self.typhoon_calls = []

        def partial_llm(prompt):
            self.typhoon_calls.append(prompt)
            return (
                '{"response_type": "ALGORITHM_ANSWER", '
                '"understanding_level": "PARTIAL", "feedback": "ยังไม่ครบ", '
                '"strength": "", "improvement": "ลองอีกครั้ง", '
                '"progress": "", "next_action": "HINT"}'
            )

        self.eval_patch = patch.object(main, "ask_evaluation", partial_llm)
        self.eval_patch.start()

    def test_typhoon_evaluated_partial_increments_attempt(self):
        self._answer(self.COMPLETE_ANSWER)

        self.assertEqual(len(self.typhoon_calls), 1)
        s = self._session()
        self.assertEqual(s["attempt"], 2)
        self.assertEqual(len(s["attempt_history"]), 1)

    def test_rejections_then_real_evaluations_reach_max_attempts(self):
        # ตีกลับหลายรอบก่อน ไม่นับ
        self._answer(INCOMPLETE_ANSWER)
        self._answer(INCOMPLETE_ANSWER)
        self.assertEqual(self._session()["attempt"], 1)

        # Typhoon ประเมินจริง 2 รอบ (max_attempts=2) ถึงจะเข้า MAX_ATTEMPTS
        self._answer(self.COMPLETE_ANSWER)
        self.assertEqual(self._session()["attempt"], 2)

        self._answer(self.COMPLETE_ANSWER)
        s = self._session()
        self.assertEqual(s["pending_final_status"], "MAX_ATTEMPTS_REACHED")


class RuleRejectionCeilingTest(_SessionTestBase):
    """ถูกตีกลับครบ 3 ครั้งแล้ว ครั้งที่ 4 ปล่อยผ่านไปให้ Typhoon ประเมิน"""

    COMPLETE_ANSWER = (
        "1. เริ่มต้น 2. รับค่า n 3. บวกเข้า total 4. แสดง total 5. จบ"
    )

    def setUp(self):
        super().setUp()
        self.eval_patch.stop()
        self.typhoon_calls = []

        def partial_llm(prompt):
            self.typhoon_calls.append(prompt)
            return (
                '{"response_type": "ALGORITHM_ANSWER", '
                '"understanding_level": "PARTIAL", "feedback": "ยังไม่ครบ", '
                '"strength": "", "improvement": "ลองอีกครั้ง", '
                '"progress": "", "next_action": "HINT"}'
            )

        self.eval_patch = patch.object(main, "ask_evaluation", partial_llm)
        self.eval_patch.start()

    def test_rejection_count_increments_each_time(self):
        self._answer(INCOMPLETE_ANSWER)
        self.assertEqual(self._session()["rule_rejection_count"], 1)
        self._answer(INCOMPLETE_ANSWER)
        self.assertEqual(self._session()["rule_rejection_count"], 2)
        self.assertEqual(self.typhoon_calls, [])

    def test_first_three_rejected_without_calling_typhoon(self):
        for _ in range(3):
            self._answer(INCOMPLETE_ANSWER)

        self.assertEqual(self.typhoon_calls, [])
        self.assertEqual(self._session()["rule_rejection_count"], 3)
        self.assertEqual(self._session()["attempt"], 1)

    def test_fourth_incomplete_submission_goes_to_typhoon(self):
        for _ in range(3):
            self._answer(INCOMPLETE_ANSWER)

        self._answer(INCOMPLETE_ANSWER)

        self.assertEqual(len(self.typhoon_calls), 1)
        joined = "\n".join(self.channel.sent)
        self.assertIn("ลองให้ระบบช่วยวิเคราะห์เพิ่มเติมให้นะ", joined)

    def test_bypassed_evaluation_counts_attempt(self):
        for _ in range(3):
            self._answer(INCOMPLETE_ANSWER)

        self._answer(INCOMPLETE_ANSWER)

        s = self._session()
        self.assertEqual(s["attempt"], 2)
        self.assertEqual(len(s["attempt_history"]), 1)

    def test_bypass_stays_active_and_does_not_loop_back_to_rejection(self):
        for _ in range(3):
            self._answer(INCOMPLETE_ANSWER)

        self._answer(INCOMPLETE_ANSWER)
        self._answer(INCOMPLETE_ANSWER)

        self.assertEqual(len(self.typhoon_calls), 2)

    def test_no_notice_before_ceiling_is_reached(self):
        self._answer(INCOMPLETE_ANSWER)

        joined = "\n".join(self.channel.sent)
        self.assertNotIn("ลองให้ระบบช่วยวิเคราะห์เพิ่มเติมให้นะ", joined)

    def test_complete_answer_resets_rejection_count(self):
        self._answer(INCOMPLETE_ANSWER)
        self._answer(INCOMPLETE_ANSWER)
        self.assertEqual(self._session()["rule_rejection_count"], 2)

        self._answer(self.COMPLETE_ANSWER)

        self.assertEqual(self._session()["rule_rejection_count"], 0)
        joined = "\n".join(self.channel.sent)
        self.assertNotIn("ลองให้ระบบช่วยวิเคราะห์เพิ่มเติมให้นะ", joined)

    def test_complete_answer_after_ceiling_shows_no_notice(self):
        for _ in range(3):
            self._answer(INCOMPLETE_ANSWER)
        self.channel.sent.clear()

        self._answer(self.COMPLETE_ANSWER)

        joined = "\n".join(self.channel.sent)
        self.assertNotIn("ลองให้ระบบช่วยวิเคราะห์เพิ่มเติมให้นะ", joined)
        self.assertEqual(len(self.typhoon_calls), 1)


class BypassedGoodIsCappedEndToEndTest(_SessionTestBase):
    """ปล่อยผ่านครั้งที่ 4 แล้ว Typhoon ให้ GOOD แต่ยังขาด "จบ" ต้องไม่จบ session"""

    NO_END = "1. เริ่มต้น 2. รับค่า n 3. บวกเข้า total 4. แสดง total"

    def setUp(self):
        super().setUp()
        self.eval_patch.stop()

        def good_llm(prompt):
            return (
                '{"response_type": "ALGORITHM_ANSWER", '
                '"understanding_level": "GOOD", "feedback": "ครบถ้วน", '
                '"strength": "ดี", "improvement": "", "progress": "", '
                '"next_action": "CONTINUE"}'
            )

        self.eval_patch = patch.object(main, "ask_evaluation", good_llm)
        self.eval_patch.start()

    def test_good_from_typhoon_is_treated_as_partial_after_bypass(self):
        for _ in range(3):
            self._answer(self.NO_END)

        self._answer(self.NO_END)

        s = self._session()
        # GOOD จะข้ามไป Evaluation QP (phase เปลี่ยน) แต่ต้องยังเป็น PARTIAL:
        # ยังอยู่ขั้นเขียน Algorithm, นับ attempt และให้ hint
        self.assertEqual(s["phase"], "ALGORITHM_ANSWER")
        self.assertEqual(s["attempt"], 2)
        self.assertEqual(s["attempt_history"][0]["understanding_level"], "PARTIAL")
        joined = chr(10).join(self.channel.sent)
        self.assertIn("ลองให้ระบบช่วยวิเคราะห์เพิ่มเติมให้นะ", joined)
        self.assertIn("อัลกอริทึมยังขาดขั้นจบ", joined)


if __name__ == "__main__":
    unittest.main()
