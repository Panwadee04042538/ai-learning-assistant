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

import inspect
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

    def test_caps_explanation_to_2_to_3_sentences(self):
        self.assertIn("2-3 sentences", typhoon_service.GROUNDED_ANSWER_INSTRUCTIONS)

    def test_forbids_full_step_by_step_walkthrough_before_question(self):
        text = typhoon_service.GROUNDED_ANSWER_INSTRUCTIONS
        self.assertIn("Do not walk through the full step-by-step analysis", text)
        self.assertIn("its own follow-up question", text)

    def test_goal_is_learner_thinking_not_ready_made_answer(self):
        text = typhoon_service.GROUNDED_ANSWER_INSTRUCTIONS
        self.assertIn("not to hand them a complete, ready-made analysis", text)


class AskGroundedAnswerPromptTest(unittest.TestCase):
    """typhoon_service.ask_grounded_answer: จุดสร้าง prompt จริงก่อนเรียก Typhoon"""

    def setUp(self):
        # อ่านซอร์สของฟังก์ชันตรง ๆ เพื่อตรวจข้อความ prompt โดยไม่เรียก API จริง
        self.source = inspect.getsource(typhoon_service.ask_grounded_answer)

    def test_prompt_limits_explanation_to_2_to_3_sentences(self):
        self.assertIn("ไม่เกิน 2-3 ประโยค", self.source)

    def test_prompt_forbids_full_analysis_before_qp_question(self):
        self.assertIn("ห้ามเฉลยหรือเดินตามขั้นตอนการวิเคราะห์ทั้งหมดจนจบก่อน", self.source)
        self.assertIn("รอให้ระบบถามคำถามต่อจากนี้เอง", self.source)

    def test_prompt_states_goal_is_learner_thinking(self):
        self.assertIn("ให้ผู้เรียนคิดต่อเอง", self.source)
        self.assertIn("ไม่ใช่ได้รับคำตอบสำเร็จรูป", self.source)


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

    def test_clarifies_this_is_algorithm_evaluation_not_planning_qp(self):
        self.assertIn("นี่คือขั้นประเมิน Algorithm ไม่ใช่ Planning QP", self.text)
        self.assertIn("คำถามวางแผน (Planning QP)", self.text)
        self.assertIn("โจทย์ต้องการให้แก้ปัญหาอะไร", self.text)

    def test_forbids_using_planning_qp_as_evaluation_criteria(self):
        self.assertIn("ห้ามนำคำถาม Planning QP มาใช้เป็นเกณฑ์ประเมิน", self.text)

    def test_evaluates_only_algorithm_correctness(self):
        self.assertIn(
            "ให้ประเมินเฉพาะความถูกต้องและความสมบูรณ์ของ Algorithm", self.text
        )

    def test_current_question_labeled_as_algorithm_goal_not_qp_to_answer(self):
        self.assertIn(
            "นี่คือเป้าหมายของ Algorithm ที่ต้องประเมิน", self.text
        )


class BuildEvaluationPromptFiveComponentRuleTest(unittest.TestCase):
    """
    student_response_service.build_evaluation_prompt: เกณฑ์การประเมินแบบ
    "ตรวจสอบ 5 องค์ประกอบหลัก" (เริ่มต้น/Input/Process/Output/จบ) แทนการ
    เปรียบเทียบ model_answer แบบเปอร์เซ็นต์ logic โดยรวม

    Backlog: เด็กส่ง Algorithm ที่ขาดขั้นแสดงผลแต่ Typhoon ให้ GOOD เพราะ
    model_answer comparison แบบ % เดิมไม่ได้บังคับว่าต้องมีขั้นแสดงผลแยก
    ต่างหาก ต้องเปลี่ยนมาตัดสินจากจำนวนองค์ประกอบที่มีครบแทน
    """

    def setUp(self):
        self.model_answer = (
            "1. เริ่มต้น\n2. total = 0, count = 0\n3. รับค่า n\n"
            "4. ทำซ้ำขณะ n ≠ -1\n   4.1 total = total + n\n"
            "   4.2 count = count + 1\n   4.3 รับค่า n ใหม่\n"
            "5. แสดง total, count\n6. จบ"
        )
        self.text = srs.build_evaluation_prompt(
            learning_goal="LG02 — วิเคราะห์ปัญหาก่อนออกแบบ Algorithm",
            question="รวบรวมจำนวนผู้เข้าร่วมกิจกรรม",
            student_answer=(
                "1. เริ่มต้น 2. รับค่า n 3. ทำซ้ำขณะ n ไม่ใช่ -1 บวกเข้า "
                "total และเพิ่ม count แล้วรับค่าใหม่ "
                "4. แสดงผู้เข้าร่วมทั้งหมด และจำนวนห้อง 5. จบ"
            ),
            expected_output="แสดงจำนวนผู้เข้าร่วมทั้งหมดและจำนวนห้อง",
            model_answer=self.model_answer,
        )

    def test_states_all_five_components_with_correct_weight(self):
        self.assertIn(
            "แต่ละข้อมีน้ำหนักเท่ากันข้อละ 20%", self.text
        )
        for component in ["เริ่มต้น", "Input", "Process", "Output", "จบ"]:
            self.assertIn(component, self.text)

    def test_states_the_four_tier_threshold_table(self):
        self.assertIn(
            "ครบ 5/5 หรือ 4/5 (ต้องมีทั้ง Output และจบ) -> GOOD", self.text
        )
        self.assertIn("ครบ 3/5 -> PARTIAL", self.text)
        self.assertIn("ครบ 2/5 หรือน้อยกว่า -> NEEDS_IMPROVEMENT", self.text)

    def test_judges_each_component_by_meaning_not_literal_wording(self):
        self.assertIn(
            "ตัดสินจากความหมาย ไม่ใช่ถ้อยคำ ชื่อตัวแปร หรือรูปแบบการเขียน",
            self.text,
        )
        self.assertIn("total และ count", self.text)
        self.assertIn("แสดง total, count", self.text)

    def test_forbids_downgrading_once_good_threshold_is_met(self):
        self.assertIn(
            "เมื่อครบตามเกณฑ์ GOOD แล้ว (5/5 หรือ 4/5 ที่มี Output กับจบครบ) ห้าม",
            self.text,
        )
        self.assertIn("รูปแบบการเขียน", self.text)
        self.assertIn("สไตล์", self.text)
        self.assertIn("การตั้งชื่อตัวแปร", self.text)

    def test_forbids_previous_attempts_from_changing_component_count(self):
        self.assertIn(
            "ห้ามใช้ Previous Attempts, ความรู้ทั่วไปนอกเหนือจากโจทย์",
            self.text,
        )

    def test_forbids_hunting_for_extra_flaws_after_counting(self):
        self.assertIn(
            "ห้ามวนกลับไปตรวจซ้ำหาข้อบกพร่องเพิ่มเติมอีกหลังจากนับองค์ประกอบ",
            self.text,
        )

    def test_rule_applies_before_previous_partial_results(self):
        self.assertIn(
            "ห้ามมองข้ามแม้ Previous Attempts หรือรอบก่อนหน้าจะเคยได้ PARTIAL มาก่อน",
            self.text,
        )

    def test_output_and_end_are_marked_as_required_in_the_component_list(self):
        self.assertIn("4. Output (required เสมอ)", self.text)
        self.assertIn("5. จบ (required เสมอ)", self.text)

    def test_states_output_and_end_are_required_component(self):
        self.assertIn(
            "Output และจบเป็น required component เสมอ", self.text
        )
        self.assertIn(
            "ต่างจากข้อ 1-3 (เริ่มต้น,\nInput, Process) ที่ขาดได้ 1 ข้อแล้วยังผ่าน",
            self.text,
        )

    def test_missing_output_caps_at_partial_regardless_of_count(self):
        self.assertIn(
            "ถ้าขาด Output -> PARTIAL ไม่ว่าจะครบกี่ข้อ", self.text
        )

    def test_missing_end_caps_at_partial_regardless_of_count(self):
        self.assertIn(
            "ถ้าขาดจบ -> PARTIAL ไม่ว่าจะครบกี่ข้อ", self.text
        )

    def test_four_of_five_only_good_when_output_and_end_present(self):
        self.assertIn(
            "ครบ 5/5 หรือ 4/5 (ต้องมีทั้ง Output และจบ) -> GOOD", self.text
        )

    def test_needs_improvement_exception_when_two_or_fewer_overall(self):
        self.assertIn(
            "ถ้าขาดทั้ง Output และองค์ประกอบอื่นจนนับได้รวม ≤2 ข้อ ให้ใช้",
            self.text,
        )
        self.assertIn(
            "NEEDS_IMPROVEMENT ตามเกณฑ์จำนวนข้อ (แย่กว่า PARTIAL อยู่แล้ว)",
            self.text,
        )


class BuildEvaluationPromptExpectedOutputReferenceTest(unittest.TestCase):
    """
    student_response_service.build_evaluation_prompt: EXPECTED OUTPUT ใช้
    เป็นตัวอ้างอิงสำหรับองค์ประกอบข้อ 4 (Output) เท่านั้น
    """

    def test_includes_expected_output_when_provided(self):
        text = srs.build_evaluation_prompt(
            learning_goal="LG08 — ฝึกออกแบบ Algorithm",
            question="คำนวณค่าบริการสุทธิ",
            student_answer="1. รับค่า 2. คำนวณ 3. จบ",
            expected_output="แสดงค่าบริการสุทธิ",
        )
        self.assertIn("แสดงค่าบริการสุทธิ", text)
        self.assertIn("ตัดสินองค์ประกอบข้อ 4 (Output)", text)

    def test_missing_expected_output_still_states_not_specified(self):
        text = srs.build_evaluation_prompt(
            learning_goal="LG08 — ฝึกออกแบบ Algorithm",
            question="Algorithm คืออะไร?",
            student_answer="เป็นลำดับขั้นตอนในการแก้ปัญหา",
        )
        self.assertIn("ไม่ได้ระบุ Output ที่ต้องแสดงผลชัดเจน", text)


class BuildEvaluationPromptModelAnswerReferenceTest(unittest.TestCase):
    """
    student_response_service.build_evaluation_prompt: model_answer เป็น
    ตัวอ้างอิงเฉพาะองค์ประกอบข้อ 3 (Process) เท่านั้น ไม่ใช่ใช้เทียบทั้ง
    Algorithm แบบเปอร์เซ็นต์เหมือนเดิม
    """

    def test_includes_model_answer_and_scopes_it_to_process_only(self):
        model_answer = (
            "1. เริ่มต้น\n2. total = 0, count = 0\n3. รับค่า n\n"
            "4. ทำซ้ำขณะ n ≠ -1\n   4.1 total = total + n\n"
            "   4.2 count = count + 1\n   4.3 รับค่า n ใหม่\n"
            "5. แสดง total, count\n6. จบ"
        )
        text = srs.build_evaluation_prompt(
            learning_goal="LG02 — วิเคราะห์ปัญหาก่อนออกแบบ Algorithm",
            question="รวบรวมจำนวนผู้เข้าร่วมกิจกรรม",
            student_answer="1. รับค่า 2. คำนวณ 3. แสดง total และ count 4. จบ",
            model_answer=model_answer,
        )
        self.assertIn(model_answer, text)
        self.assertIn(
            "ใช้ Model Answer เป็นตัวอ้างอิงเฉพาะสำหรับองค์ประกอบข้อ 3 (Process)",
            text,
        )
        self.assertIn(
            "ไม่ใช่นำ Algorithm ทั้งฉบับของนักเรียนมาเทียบกับ Model Answer แบบ",
            text,
        )

    def test_missing_model_answer_falls_back_to_inferring_from_question(self):
        text = srs.build_evaluation_prompt(
            learning_goal="LG02 — วิเคราะห์ปัญหาก่อนออกแบบ Algorithm",
            question="Algorithm คืออะไร?",
            student_answer="เป็นลำดับขั้นตอนในการแก้ปัญหา",
        )
        self.assertIn(
            "ไม่ได้ระบุ Model Answer อ้างอิง ให้ประเมินจากเกณฑ์อื่นด้านบนแทน",
            text,
        )
        self.assertIn("ห้ามอนุมาน Model Answer ทั้งฉบับขึ้นเอง", text)


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

    def test_forbids_any_question_in_feedback(self):
        self.assertIn("ห้ามสร้างคำถามใด ๆ ในข้อความ feedback โดยเด็ดขาด", self.text)
        self.assertIn("ห้ามลงท้ายด้วยคำถาม", self.text)

    def test_forbids_question_mark(self):
        self.assertIn('ห้ามใช้เครื่องหมาย "?"', self.text)

    def test_feedback_must_be_statements_only(self):
        self.assertIn("ประโยคบอกเล่า", self.text)

    def test_system_sends_next_question_separately(self):
        self.assertIn("ระบบจะส่งคำถามขั้นถัดไปเองใน", self.text)

    def test_feedback_capped_at_three_sentences(self):
        self.assertIn("ไม่เกิน 3 ประโยค", self.text)


class BuildQpFeedbackPromptEvaluationRuleTest(unittest.TestCase):
    """
    main.build_qp_feedback_prompt: กฎเพิ่มเติมเฉพาะขั้น Evaluation

    Backlog: Typhoon เคยขอให้เด็กยกตัวอย่าง Algorithm ในการตอบ Evaluation
    QP ทั้งที่คำถามขั้นนี้ต้องการแค่ให้เด็กประเมินตัวเองว่าทำได้หรือไม่
    """

    def setUp(self):
        self.qp = {
            "phase": "Evaluation",
            "system_question": "Algorithm ที่คุณส่งไปสามารถแก้ปัญหานี้ได้ครบถ้วนหรือไม่ เพราะอะไร?",
            "question_purpose": "ให้ผู้เรียนประเมินความครบถ้วนถูกต้องของ Algorithm ที่ออกแบบ",
            "expect_input": "ประเมินและอธิบายเหตุผลโดยอ้างอิง Algorithm ที่ส่งไป",
        }
        self.text = main.build_qp_feedback_prompt(
            self.qp, "ได้แล้ว เพราะทดสอบกับตัวอย่างแล้วผลลัพธ์ถูกต้อง", "LG02"
        )

    def test_states_evaluation_only_wants_self_assessment(self):
        self.assertIn(
            "คำถามขั้น Evaluation ต้องการแค่ให้คุณประเมินตัวเองว่าทำได้หรือไม่",
            self.text,
        )

    def test_forbids_asking_for_algorithm_example_or_rewrite(self):
        self.assertIn("ห้ามขอให้ผู้เรียนยกตัวอย่าง Algorithm", self.text)
        self.assertIn("ห้ามขอให้เขียนขั้นตอนใหม่", self.text)

    def test_treats_done_because_answer_as_complete(self):
        self.assertIn('เช่น "ได้แล้ว เพราะ ..."', self.text)
        self.assertIn("ให้ถือว่าตอบครบถ้วนตามที่คำถามต้องการทันที", self.text)
        self.assertIn("ไม่ต้องขอข้อมูลเพิ่มเติมหรือชวนทำอะไรต่ออีก", self.text)

    def test_requires_short_feedback_that_can_end_immediately(self):
        self.assertIn("ไม่เกิน 2-3 ประโยค และจบข้อความ", self.text)
        self.assertIn("ได้เลย ไม่ต้องมีคำชวนต่อท้าย", self.text)

    def test_non_evaluation_phase_does_not_get_evaluation_only_rules(self):
        planning_qp = dict(self.qp, phase="Planning")
        text = main.build_qp_feedback_prompt(
            planning_qp, "ต้องวิเคราะห์ข้อมูลก่อน", "LG02"
        )
        self.assertNotIn(
            "คำถามขั้น Evaluation ต้องการแค่ให้คุณประเมินตัวเองว่าทำได้หรือไม่",
            text,
        )
        self.assertNotIn("ห้ามขอให้ผู้เรียนยกตัวอย่าง Algorithm", text)


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
        self.assertIn("ห้ามชมลอย ๆ", text)
        self.assertIn("QP.xlsx", text)
        self.assertIn("ไม่เกิน 3 ประโยค", text)

    def test_warmup_feedback_prompt_forbids_ending_with_a_question(self):
        text = main.build_lg01_warmup_feedback_prompt(
            self.qp, "เป็นลำดับขั้นตอนการแก้ปัญหา"
        )
        self.assertIn("ไม่ใช่การถามต่อ", text)
        self.assertIn("ห้ามลงท้ายด้วยคำถามใด ๆ ทั้งสิ้น", text)
        self.assertIn('ห้ามใช้เครื่องหมาย "?"', text)
        self.assertIn("ประโยคบอกเล่า", text)

    def test_wrapup_summary_prompt_speaking_principles(self):
        text = main.build_lg01_wrapup_summary_prompt(
            self.qp, "วันนี้เข้าใจเรื่อง Algorithm มากขึ้น"
        )
        self.assertIn('"คุณ"', text)
        self.assertIn('"นักเรียน"', text)
        self.assertIn("ห้ามชมลอย ๆ", text)
        self.assertIn("QP.xlsx", text)
        self.assertIn("ไม่เกิน 3 ประโยค", text)

    def test_wrapup_summary_prompt_forbids_ending_with_a_question(self):
        text = main.build_lg01_wrapup_summary_prompt(
            self.qp, "วันนี้เข้าใจเรื่อง Algorithm มากขึ้น"
        )
        self.assertIn("การสรุปปิดคาบ ไม่ใช่การถามต่อ", text)
        self.assertIn("ห้ามลงท้ายด้วยคำถามใด ๆ ทั้งสิ้น", text)
        self.assertIn('ห้ามใช้เครื่องหมาย "?"', text)
        self.assertIn("ประโยคบอกเล่า", text)


class Lg01WarmupIntroTest(unittest.TestCase):
    """main.LG01_ALGORITHM_INTRO: คำบรรยาย Algorithm ก่อนถามคำถามใน !warmup"""

    def test_intro_explains_algorithm_briefly(self):
        text = main.LG01_ALGORITHM_INTRO
        self.assertIn("อัลกอริทึม (Algorithm) คือ", text)
        # บรรยาย 3-5 ประโยค/ข้อ ไม่ควรยาวเป็นบทความ
        self.assertLess(len(text), 800)


class BuildLearnReflectionPromptTest(unittest.TestCase):
    """
    main.build_learn_reflection_prompt (คำถามสะท้อนคิดของ !learn)

    Backlog: Typhoon เคยสร้างคำถามซับซ้อนเกินไปสำหรับ ปวช.1 เช่น
    "ทำไมการเขียนโปรแกรมแบบ Sequence จึงต้องดำเนินการทีละขั้นตอนจากบนลงล่าง
    โดยไม่มีการเปลี่ยนลำดับหรือตัดสินใจเพิ่มเติม?" ต้องเพิ่มกฎให้คำถามสั้น
    ใช้คำง่าย และห้ามใช้ศัพท์เทคนิคในตัวคำถาม
    """

    def setUp(self):
        self.text = main.build_learn_reflection_prompt(
            question="loop คืออะไร",
            concept_text="loop คือการทำซ้ำตามเงื่อนไขที่กำหนด",
            ai_answer="loop คือการทำงานซ้ำ ๆ จนกว่าเงื่อนไขจะเป็นเท็จ",
        )

    def test_requires_question_to_be_one_short_sentence(self):
        self.assertIn(
            "คำถามต้องสั้นมาก ไม่เกิน 1 ประโยค ห้ามเป็นประโยคซ้อนหลายเงื่อนไข",
            self.text,
        )

    def test_requires_simple_high_school_level_language(self):
        self.assertIn(
            "ใช้คำง่าย ๆ แบบที่ครูถามคุยกับเด็กมัธยมปลาย (ปวช.1) ทั่วไป",
            self.text,
        )
        self.assertIn("ไม่ใช่ภาษาวิชาการหรือภาษาตำรา", self.text)

    def test_requires_asking_about_real_life_observation(self):
        self.assertIn(
            "ให้ถามสิ่งที่ผู้เรียนสังเกตหรือนึกภาพออกได้จากชีวิตจริง",
            self.text,
        )

    def test_forbids_specific_technical_jargon_words(self):
        for banned_word in ["ดำเนินการ", "ลำดับ", "ตัดสินใจเพิ่มเติม"]:
            self.assertIn(banned_word, self.text)
        self.assertIn("ห้ามใช้ศัพท์เทคนิคที่ฟังดูเป็นทางการในตัวคำถาม", self.text)

    def test_includes_good_example_questions(self):
        self.assertIn("ถ้าทำขั้นตอนผิดลำดับ จะเกิดอะไรขึ้น?", self.text)
        self.assertIn("loop ต่างจากการทำงานปกติยังไง?", self.text)

    def test_includes_the_reported_bad_example_as_a_warning(self):
        self.assertIn("ตัวอย่างคำถามที่ห้ามถามแบบนี้", self.text)
        self.assertIn(
            "ทำไมการเขียนโปรแกรมแบบ Sequence จึงต้องดำเนินการทีละขั้นตอน",
            self.text,
        )


if __name__ == "__main__":
    unittest.main()
