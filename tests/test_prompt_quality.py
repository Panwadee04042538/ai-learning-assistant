"""
ทดสอบคุณภาพ "หลักการพูด" ของ system prompt / prompt builder ที่ส่งให้ AI
(Backlog #3)

เทสต์กลุ่มนี้ตรวจสอบว่า "ข้อความ instruction" ที่ส่งให้ ask_ai / ask_evaluation
(Typhoon) มีหลักการต่อไปนี้ครบตามที่กำหนด ไม่ใช่การเทสต์ผลลัพธ์จาก AI จริง ๆ:

1. ห้ามบอกขั้นตอนหรือคำตอบที่ขาดโดยตรง ให้ถามนำ 1 ข้อแทน
2. ชมเฉพาะสิ่งที่ปรากฏในคำตอบจริง ถ้าไม่มีให้เว้นว่าง
3. ถ้าคำตอบไม่ได้ตอบคำถาม ให้บอกตรง ๆ แล้วถามซ้ำ ไม่ใช่ให้คำใบ้ทันที
4. ถ้าพบความเข้าใจผิด ให้ถามให้ตรวจจุดนั้น
5. พูดกับผู้เรียนด้วย "คุณ" ไม่ใช่ "นักเรียน"
6. คำถามอภิปัญญาต้องมาจาก QP.xlsx เท่านั้น ห้าม AI สร้างขึ้นเองแบบ free-form

วิธีรัน (จากโฟลเดอร์หลักของโปรเจกต์):
    python -m unittest tests.test_prompt_quality -v
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault("TYPHOON_API_KEY", "test")
os.environ.setdefault("GEMINI_API_KEY", "test")
os.environ.setdefault("DISCORD_TOKEN", "test")

import main  # noqa: E402
import typhoon_service  # noqa: E402
import student_response_service as srs  # noqa: E402


# คำที่ต้องไม่ถูกใช้เป็นการเรียกผู้เรียนตรง ๆ (อนุญาตได้เฉพาะกรณีคำประสม
# เช่น "รหัสนักเรียน" หรือบรรยายกลุ่มผู้เรียนแบบบุคคลที่สาม
# เช่น "นักเรียนระดับอาชีวศึกษา" ซึ่งเทสต์นี้ไม่ครอบคลุมเพราะเป็น
# instruction ไปยัง AI ไม่ใช่ข้อความที่ AI ควรพูดกับผู้เรียนตรง ๆ)
DIRECT_ADDRESS_HINT = "คุณ"


class InstructionTextTestCase(unittest.TestCase):
    """Helper assertions ที่ใช้ซ้ำในหลายเทสต์"""

    def assert_forbids_free_form_metacognition(self, text):
        self.assertIn(
            "QP.xlsx", text,
            "instruction ควรระบุว่าคำถามอภิปัญญาต้องมาจาก QP.xlsx"
        )
        self.assertIn(
            "ห้ามสร้างคำถาม", text,
            "instruction ควรห้าม AI สร้างคำถามอภิปัญญาขึ้นเอง"
        )

    def assert_addresses_learner_as_khun(self, text):
        self.assertIn(
            '"คุณ"', text,
            'instruction ควรกำหนดให้เรียกผู้เรียนว่า "คุณ"'
        )
        self.assertIn(
            "นักเรียน", text,
            'instruction ควรกล่าวถึง "นักเรียน" เป็นคำที่ห้ามใช้เรียกตรง ๆ'
        )


class TyphoonGeneralInstructionsTest(InstructionTextTestCase):
    """typhoon_service.GENERAL_INSTRUCTIONS (system prompt ของ ask_ai)"""

    def test_has_speaking_principles_section(self):
        self.assertIn(
            "Speaking principles", typhoon_service.GENERAL_INSTRUCTIONS
        )

    def test_addresses_learner_as_khun_not_nakrian(self):
        text = typhoon_service.GENERAL_INSTRUCTIONS
        self.assertIn('"คุณ"', text)
        self.assertIn('"นักเรียน"', text)

    def test_forbids_stating_missing_step_directly(self):
        text = typhoon_service.GENERAL_INSTRUCTIONS
        self.assertIn("Do not state a missing step", text)
        self.assertIn("guiding question", text)

    def test_forbids_inventing_praise(self):
        text = typhoon_service.GENERAL_INSTRUCTIONS
        self.assertIn("leave that", text)
        self.assertIn("inventing praise", text)

    def test_forbids_free_form_metacognitive_question(self):
        text = typhoon_service.GENERAL_INSTRUCTIONS
        self.assertIn("QP.xlsx", text)
        self.assertIn("Never invent your own metacognitive", text)


class TyphoonGroundedAnswerInstructionsTest(unittest.TestCase):

    def test_addresses_learner_as_khun_not_nakrian(self):
        text = typhoon_service.GROUNDED_ANSWER_INSTRUCTIONS
        self.assertIn('"คุณ"', text)
        self.assertIn('"นักเรียน"', text)


class TyphoonEvaluationInstructionsTest(InstructionTextTestCase):
    """typhoon_service.EVALUATION_INSTRUCTIONS (system prompt ของ ask_evaluation)"""

    def setUp(self):
        self.text = typhoon_service.EVALUATION_INSTRUCTIONS

    def test_addresses_learner_as_khun_not_nakrian(self):
        self.assertIn('"คุณ"', self.text)
        self.assertIn('"นักเรียน"', self.text)

    def test_partial_asks_guiding_question_instead_of_stating_gap(self):
        self.assertIn("ask ONE guiding question", self.text)

    def test_needs_improvement_distinguishes_unrelated_vs_misconception(self):
        self.assertIn("unrelated", self.text)
        self.assertIn("repeat the current question", self.text)
        self.assertIn("misconception", self.text)
        self.assertIn("re-check that specific point", self.text)

    def test_misconception_example_loop_vs_condition(self):
        self.assertIn("loop", self.text)
        self.assertIn("condition", self.text)

    def test_strength_must_be_empty_when_nothing_genuine(self):
        self.assertIn("STRENGTH", self.text)
        self.assertIn('empty string ""', self.text)
        self.assertIn("Do not invent", self.text)

    def test_forbids_free_form_metacognitive_question(self):
        self.assertIn("QP.xlsx", self.text)
        self.assertIn("Never invent your own metacognitive", self.text)


class BuildEvaluationPromptTest(InstructionTextTestCase):
    """student_response_service.build_evaluation_prompt (prompt จริงที่ใช้ประเมิน
    คำตอบ Algorithm ของผู้เรียน)"""

    def setUp(self):
        self.text = srs.build_evaluation_prompt(
            learning_goal="LG08 — ฝึกออกแบบ Algorithm",
            question="Algorithm คืออะไร?",
            student_answer="เป็นลำดับขั้นตอนในการแก้ปัญหา",
        )

    def test_addresses_learner_as_khun_not_nakrian(self):
        self.assert_addresses_learner_as_khun(self.text)

    def test_forbids_stating_missing_step_directly(self):
        self.assertIn("ห้ามบอกขั้นตอนหรือคำตอบที่ยังขาดโดยตรง", self.text)
        self.assertIn("คำถามชี้นำ", self.text)

    def test_strength_must_be_empty_when_nothing_genuine(self):
        self.assertIn('ให้ตอบเป็นค่าว่าง ""', self.text)
        self.assertIn("ห้ามแต่งจุดแข็งขึ้นมาเอง", self.text)

    def test_improvement_asks_guiding_question_instead_of_stating_gap(self):
        self.assertIn("ห้ามระบุสิ่งที่ยังขาดโดยตรง", self.text)
        self.assertIn("ตั้งเป็นคำถามชี้นำ", self.text)

    def test_unrelated_answer_gets_told_directly_and_re_asked(self):
        self.assertIn("คำตอบนี้ยังไม่ได้ตอบคำถาม", self.text)
        self.assertIn("ย้ำคำถามปัจจุบันอีกครั้ง", self.text)

    def test_misconception_must_be_checked_not_corrected_directly(self):
        self.assertIn("ห้ามแก้ให้ตรง ๆ", self.text)
        self.assertIn("loop", self.text)
        self.assertIn("condition", self.text)

    def test_forbids_free_form_metacognitive_question(self):
        self.assert_forbids_free_form_metacognition(self.text)


class BuildQpFeedbackPromptTest(unittest.TestCase):
    """main.build_qp_feedback_prompt (feedback ของคำตอบ QP metacognition)"""

    def setUp(self):
        self.qp = {
            "phase": "Evaluation",
            "system_question": "Algorithm คืออะไร?",
            "question_purpose": "ตรวจความเข้าใจพื้นฐาน",
            "expect_input": "คำอธิบายเกี่ยวกับลำดับขั้นตอน",
        }
        self.text = main.build_qp_feedback_prompt(
            self.qp, "เป็นลำดับขั้นตอนการแก้ปัญหา", "LG01"
        )

    def test_addresses_learner_as_khun_not_nakrian(self):
        self.assertIn('"คุณ"', self.text)
        self.assertIn('"นักเรียน"', self.text)

    def test_forbids_stating_missing_step_directly(self):
        self.assertIn("ห้ามชี้หรือเฉลยจุดที่ควรตรวจสอบโดยตรง", self.text)
        self.assertIn("ถามคำถามชี้นำ", self.text)

    def test_skips_praise_when_nothing_genuine(self):
        self.assertIn("ถ้าไม่มีจุดที่ทำได้ดีจริง ให้ข้ามส่วนนี้ไปเลย", self.text)
        self.assertIn("ห้ามชมลอย ๆ", self.text)

    def test_misconception_must_be_checked_not_corrected_directly(self):
        self.assertIn("ห้ามแก้ให้ตรง ๆ", self.text)
        self.assertIn("loop", self.text)
        self.assertIn("condition", self.text)

    def test_forbids_free_form_metacognitive_question(self):
        self.assertIn("QP.xlsx", self.text)
        self.assertIn("ห้ามสร้างคำถาม Metacognition ใหม่", self.text)

    def test_limits_to_at_most_one_question(self):
        self.assertIn("ถามได้ 1 ข้อเท่านั้น", self.text)
        self.assertIn("ห้ามถามมากกว่า 1 ข้อ", self.text)

    def test_guiding_question_must_be_the_final_sentence(self):
        self.assertIn("ประโยคสุดท้ายเพียงประโยคเดียว", self.text)

    def test_feedback_capped_at_three_sentences(self):
        self.assertIn("ไม่เกิน 3 ประโยค", self.text)


class Lg01WarmupWrapupPromptTest(unittest.TestCase):
    """main.build_lg01_warmup_feedback_prompt / build_lg01_wrapup_summary_prompt"""

    def setUp(self):
        self.qp = {
            "phase": "Evaluation",
            "system_question": "Algorithm คืออะไร?",
        }

    def test_warmup_feedback_prompt_speaking_principles(self):
        text = main.build_lg01_warmup_feedback_prompt(
            self.qp, "เป็นลำดับขั้นตอนการแก้ปัญหา"
        )
        self.assertIn('"คุณ"', text)
        self.assertIn('"นักเรียน"', text)
        self.assertIn("ห้ามเฉลยตรง ๆ", text)
        self.assertIn("ถามคำถามชี้นำ", text)
        self.assertIn("ห้ามชมลอย ๆ", text)
        self.assertIn("QP.xlsx", text)
        self.assertIn("ไม่เกิน 3 ประโยค", text)

    def test_wrapup_summary_prompt_speaking_principles(self):
        text = main.build_lg01_wrapup_summary_prompt(
            self.qp, "วันนี้เข้าใจเรื่อง Algorithm มากขึ้น"
        )
        self.assertIn('"คุณ"', text)
        self.assertIn('"นักเรียน"', text)
        self.assertIn("ห้ามชมลอย ๆ", text)
        self.assertIn("QP.xlsx", text)
        self.assertIn("ไม่เกิน 3 ประโยค", text)


class Lg01WarmupIntroTest(unittest.TestCase):
    """main.LG01_ALGORITHM_INTRO: คำบรรยาย Algorithm ก่อนถามคำถามใน !warmup"""

    def test_intro_explains_algorithm_briefly(self):
        text = main.LG01_ALGORITHM_INTRO
        self.assertIn("Algorithm คือ", text)
        # บรรยาย 3-5 ประโยค/ข้อ ไม่ควรยาวเป็นบทความ
        self.assertLess(len(text), 800)


if __name__ == "__main__":
    unittest.main()
