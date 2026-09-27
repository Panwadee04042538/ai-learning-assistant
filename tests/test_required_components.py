"""
ทดสอบ rule-based check ก่อนส่งให้ Typhoon (student_response_service):
Algorithm ต้องมีขั้น "จบ" และขั้นแสดงผล (output) เสมอ ถ้าขาดอย่างใดอย่างหนึ่ง
ต้องได้ PARTIAL ทันทีโดยไม่เรียก Typhoon

วิธีรัน (จากโฟลเดอร์หลักของโปรเจกต์):
    python -m unittest tests.test_required_components -v
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import student_response_service as srs  # noqa: E402


COMPLETE_ANSWER = (
    "1. เริ่มต้น 2. รับค่า n 3. บวกเข้า total 4. แสดง total 5. จบ"
)


class FindMissingRequiredComponentsTest(unittest.TestCase):

    def test_complete_answer_has_nothing_missing(self):
        self.assertEqual(
            srs.find_missing_required_components(COMPLETE_ANSWER), []
        )

    def test_missing_end(self):
        answer = "1. เริ่มต้น 2. รับค่า n 3. บวกเข้า total 4. แสดง total"
        self.assertEqual(
            srs.find_missing_required_components(answer), ["จบ"]
        )

    def test_missing_output(self):
        answer = "1. เริ่มต้น 2. รับค่า n 3. บวกเข้า total 4. จบ"
        self.assertEqual(
            srs.find_missing_required_components(answer), ["output"]
        )

    def test_missing_both(self):
        answer = "1. เริ่มต้น 2. รับค่า n 3. บวกเข้า total"
        self.assertEqual(
            srs.find_missing_required_components(answer), ["จบ", "output"]
        )

    def test_thai_end_synonym_accepted(self):
        answer = "รับค่า n แสดงผลลัพธ์ สิ้นสุด"
        self.assertEqual(srs.find_missing_required_components(answer), [])

    def test_english_keywords_accepted_case_insensitive(self):
        answer = "Start, input n, PRINT total, End"
        self.assertEqual(srs.find_missing_required_components(answer), [])

    def test_english_stop_and_output_accepted(self):
        answer = "read n, output total, stop"
        self.assertEqual(srs.find_missing_required_components(answer), [])

    def test_english_keyword_inside_other_word_does_not_count(self):
        # "send" / "append" มี "end" เป็นส่วนหนึ่งของคำ ไม่ถือว่ามีขั้นจบ
        answer = "send data, append list, แสดง total"
        self.assertEqual(
            srs.find_missing_required_components(answer), ["จบ"]
        )

    def test_empty_answer_misses_both(self):
        self.assertEqual(
            srs.find_missing_required_components(""), ["จบ", "output"]
        )
        self.assertEqual(
            srs.find_missing_required_components(None), ["จบ", "output"]
        )


class CheckRequiredComponentsTest(unittest.TestCase):

    def test_complete_answer_returns_none_to_continue_to_typhoon(self):
        self.assertIsNone(srs.check_required_components(COMPLETE_ANSWER))

    def test_missing_end_returns_partial_with_clear_feedback(self):
        result = srs.check_required_components(
            "1. เริ่มต้น 2. รับค่า n 3. แสดง total"
        )
        self.assertEqual(result["understanding_level"], "PARTIAL")
        self.assertEqual(result["next_action"], "HINT")
        self.assertEqual(
            result["feedback"],
            "อัลกอริทึมยังขาดขั้นจบ" + chr(10) +
            "ลองเพิ่ม 'จบ' เป็นขั้นสุดท้าย ก่อนส่งมาใหม่",
        )

    def test_missing_output_returns_partial_with_clear_feedback(self):
        result = srs.check_required_components(
            "1. เริ่มต้น 2. รับค่า n 3. จบ"
        )
        self.assertEqual(result["understanding_level"], "PARTIAL")
        self.assertEqual(
            result["feedback"],
            "อัลกอริทึมยังขาดขั้นแสดงผล" + chr(10) +
            "ลองเพิ่ม เช่น 'แสดง [ผลลัพธ์]' ก่อนส่งมาใหม่",
        )

    def test_missing_both_lists_output_first_then_end(self):
        result = srs.check_required_components("1. เริ่มต้น 2. รับค่า n")
        self.assertEqual(result["missing_components"], ["จบ", "output"])
        self.assertEqual(
            result["feedback"],
            "อัลกอริทึมยังขาด 2 ขั้นตอนสำคัญ" + chr(10) +
            "• ขาดขั้นแสดงผล — ลองเพิ่ม เช่น 'แสดง [ผลลัพธ์]'" + chr(10) +
            "• ขาดขั้นจบ — ลองเพิ่ม 'จบ' เป็นขั้นสุดท้าย",
        )

    def test_rejection_is_marked_as_not_counting_attempt(self):
        result = srs.check_required_components("รับค่า n")
        self.assertIs(result["counts_attempt"], False)
        self.assertTrue(result["rule_based"])

    def test_result_has_all_keys_main_expects(self):
        result = srs.check_required_components("รับค่า n")
        for key in (
            "success", "response_type", "understanding_level", "feedback",
            "strength", "improvement", "progress", "next_action",
        ):
            self.assertIn(key, result)
        self.assertTrue(result["success"])
        self.assertEqual(result["response_type"], "ALGORITHM_ANSWER")


class EvaluateStudentResponseShortCircuitTest(unittest.TestCase):

    def _llm(self, calls):
        def llm(prompt):
            calls.append(prompt)
            return (
                '{"response_type": "ALGORITHM_ANSWER", '
                '"understanding_level": "GOOD", "feedback": "ดี", '
                '"strength": "", "improvement": "", "progress": "", '
                '"next_action": "CONTINUE"}'
            )
        return llm

    def test_missing_component_does_not_call_typhoon(self):
        calls = []
        result = srs.evaluate_student_response(
            "LG08", "โจทย์", "1. เริ่มต้น 2. รับค่า n 3. บวกเข้า total",
            self._llm(calls),
        )
        self.assertEqual(calls, [])
        self.assertEqual(result["understanding_level"], "PARTIAL")
        self.assertEqual(
            result["student_answer"],
            "1. เริ่มต้น 2. รับค่า n 3. บวกเข้า total",
        )

    def test_complete_answer_is_sent_to_typhoon(self):
        calls = []
        result = srs.evaluate_student_response(
            "LG08", "โจทย์", COMPLETE_ANSWER, self._llm(calls),
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["understanding_level"], "GOOD")

    def test_conceptual_question_still_goes_to_typhoon(self):
        calls = []
        srs.evaluate_student_response(
            "LG08", "โจทย์", "แค่ if ไม่พอหรอ", self._llm(calls),
        )
        self.assertEqual(len(calls), 1)


class SkipRequiredCheckTest(unittest.TestCase):

    def _llm(self, calls):
        def llm(prompt):
            calls.append(prompt)
            return (
                '{"response_type": "ALGORITHM_ANSWER", '
                '"understanding_level": "PARTIAL", "feedback": "x", '
                '"strength": "", "improvement": "", "progress": "", '
                '"next_action": "HINT"}'
            )
        return llm

    def test_skip_sends_incomplete_answer_to_typhoon_and_flags_bypass(self):
        calls = []
        result = srs.evaluate_student_response(
            "LG08", "โจทย์", "1. เริ่มต้น 2. รับค่า n", self._llm(calls),
            skip_required_check=True,
        )
        self.assertEqual(len(calls), 1)
        self.assertTrue(result["rule_check_bypassed"])
        self.assertNotIn("counts_attempt", result)

    def test_skip_with_complete_answer_is_not_flagged_as_bypass(self):
        calls = []
        result = srs.evaluate_student_response(
            "LG08", "โจทย์", COMPLETE_ANSWER, self._llm(calls),
            skip_required_check=True,
        )
        self.assertEqual(len(calls), 1)
        self.assertNotIn("rule_check_bypassed", result)

    def test_default_still_rejects_incomplete_answer(self):
        calls = []
        result = srs.evaluate_student_response(
            "LG08", "โจทย์", "1. เริ่มต้น 2. รับค่า n", self._llm(calls),
        )
        self.assertEqual(calls, [])
        self.assertIs(result["counts_attempt"], False)


class BypassCapTest(unittest.TestCase):
    """ปล่อยผ่าน rule-based แล้ว Typhoon ให้ GOOD แต่ยังขาดขั้นบังคับ -> PARTIAL"""

    INCOMPLETE = "1. เริ่มต้น 2. รับค่า n 3. บวกเข้า total 4. แสดง total"

    def _llm(self, calls, level):
        def llm(prompt):
            calls.append(prompt)
            return (
                '{"response_type": "ALGORITHM_ANSWER", '
                '"understanding_level": "%s", "feedback": "ครบถ้วนดีมาก", '
                '"strength": "ดี", "improvement": "", "progress": "", '
                '"next_action": "CONTINUE"}' % level
            )
        return llm

    def test_prompt_gets_bypass_note_when_still_missing(self):
        calls = []
        srs.evaluate_student_response(
            "LG08", "โจทย์", self.INCOMPLETE, self._llm(calls, "PARTIAL"),
            skip_required_check=True,
        )
        prompt = calls[0]
        self.assertIn("หมายเหตุ: อัลกอริทึมนี้ขาดขั้นบังคับบางอย่าง", prompt)
        self.assertIn("ให้ประเมิน Process และ Logic เท่านั้น", prompt)
        self.assertIn("ผลต้องเป็น PARTIAL เสมอ ไม่ใช่ GOOD", prompt)

    def test_good_is_forced_to_partial_when_end_still_missing(self):
        calls = []
        result = srs.evaluate_student_response(
            "LG08", "โจทย์", self.INCOMPLETE, self._llm(calls, "GOOD"),
            skip_required_check=True,
        )
        self.assertEqual(result["understanding_level"], "PARTIAL")
        self.assertEqual(result["next_action"], "HINT")
        self.assertTrue(result["level_capped"])
        self.assertTrue(result["rule_check_bypassed"])
        self.assertEqual(result["missing_components"], ["จบ"])
        self.assertIn("อัลกอริทึมยังขาดขั้นจบ", result["improvement"])

    def test_good_is_forced_to_partial_when_output_still_missing(self):
        calls = []
        result = srs.evaluate_student_response(
            "LG08", "โจทย์", "1. เริ่มต้น 2. รับค่า n 3. จบ",
            self._llm(calls, "GOOD"), skip_required_check=True,
        )
        self.assertEqual(result["understanding_level"], "PARTIAL")
        self.assertIn("อัลกอริทึมยังขาดขั้นแสดงผล", result["improvement"])

    def test_needs_improvement_is_not_raised_to_partial(self):
        calls = []
        result = srs.evaluate_student_response(
            "LG08", "โจทย์", self.INCOMPLETE,
            self._llm(calls, "NEEDS_IMPROVEMENT"), skip_required_check=True,
        )
        self.assertEqual(result["understanding_level"], "NEEDS_IMPROVEMENT")
        self.assertNotIn("level_capped", result)

    def test_complete_answer_keeps_good_and_gets_no_note(self):
        calls = []
        result = srs.evaluate_student_response(
            "LG08", "โจทย์", COMPLETE_ANSWER, self._llm(calls, "GOOD"),
            skip_required_check=True,
        )
        self.assertEqual(result["understanding_level"], "GOOD")
        self.assertNotIn("ขาดขั้นบังคับบางอย่าง", calls[0])
        self.assertNotIn("level_capped", result)

    def test_normal_path_without_skip_never_gets_the_note(self):
        calls = []
        srs.evaluate_student_response(
            "LG08", "โจทย์", COMPLETE_ANSWER, self._llm(calls, "GOOD"),
        )
        self.assertNotIn("ขาดขั้นบังคับบางอย่าง", calls[0])


if __name__ == "__main__":
    unittest.main()
