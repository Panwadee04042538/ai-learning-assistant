# ==============================================
# student_response_service.py
# AI Learning Assistant — Adaptive Evaluation V2
#
# รองรับ:
# - Current Question driven evaluation
# - Expected Learning Evidence
# - Previous Attempt / Learning Progression
# - Conceptual Question detection
# - GOOD / PARTIAL / NEEDS_IMPROVEMENT
# ==============================================

import json
import re


VALID_LEVELS = [
    "GOOD",
    "PARTIAL",
    "NEEDS_IMPROVEMENT"
]

VALID_ACTIONS = [
    "CONTINUE",
    "HINT",
    "EXPLAIN"
]

VALID_RESPONSE_TYPES = [
    "ALGORITHM_ANSWER",
    "CONCEPTUAL_QUESTION"
]


# ==============================================
# HELPERS
# ==============================================

def _clean_json_response(response_text):
    response_text = (response_text or "").strip()

    if response_text.startswith("```json"):
        response_text = response_text[7:]

    elif response_text.startswith("```"):
        response_text = response_text[3:]

    if response_text.endswith("```"):
        response_text = response_text[:-3]

    return response_text.strip()


def _looks_like_conceptual_question(text):
    """
    ตรวจคำตอบที่มีลักษณะเป็นคำถามเพื่อขอความเข้าใจ
    เช่น "แค่ if ไม่พอหรอ", "ทำไมต้องใช้ loop"
    ไม่ถือเป็น Algorithm Answer ที่ต้องตัด attempt
    """
    text = (text or "").strip().lower()

    if not text:
        return False

    question_patterns = [
        r"\?$",
        r"หรอ",
        r"เหรอ",
        r"ไหม",
        r"ทำไม",
        r"เพราะอะไร",
        r"ต้องใช้",
        r"จำเป็น",
        r"ไม่พอ",
        r"พอไหม",
        r"ยังไง",
        r"อย่างไร",
        r"คืออะไร",
    ]

    return any(re.search(pattern, text) for pattern in question_patterns)


# ==============================================
# BUILD EVALUATION PROMPT
# ==============================================

def build_evaluation_prompt(
    learning_goal,
    question,
    student_answer,
    previous_attempts=None,
    expected_evidence=None,
    practice_context=None
):
    previous_attempts = previous_attempts or []
    expected_evidence = expected_evidence or ""

    previous_text = "ไม่มีคำตอบก่อนหน้า"

    if previous_attempts:
        chunks = []

        for item in previous_attempts:
            attempt_no = item.get("attempt", "?")
            answer = item.get("student_answer", "")
            level = item.get("understanding_level", "")
            improvement = item.get("improvement", "")

            chunks.append(
                f"Attempt {attempt_no}\n"
                f"คำตอบ: {answer}\n"
                f"ผลเดิม: {level}\n"
                f"จุดที่ควรพัฒนาเดิม: {improvement}"
            )

        previous_text = "\n\n".join(chunks)

    evidence_text = expected_evidence.strip() if expected_evidence else (
        "ไม่ได้ระบุ Expected Learning Evidence "
        "ให้อนุมานเฉพาะสิ่งที่จำเป็นจากคำถามปัจจุบัน"
    )

    practice_text = practice_context.strip() if practice_context else (
        "ไม่มี Practice Context"
    )

    prompt = f"""
คุณเป็น AI Learning Assistant สำหรับประเมินการเรียนรู้ของนักเรียนอาชีวศึกษา
เรื่องการออกแบบ Algorithm

==================================================
PRIORITY ในการประเมิน
==================================================

ให้พิจารณาตามลำดับนี้:

1. CURRENT LEARNING QUESTION
2. STUDENT ANSWER
3. EXPECTED LEARNING EVIDENCE
4. PREVIOUS ATTEMPTS
5. LEARNING GOAL
6. PRACTICE CONTEXT

คำถามปัจจุบันสำคัญที่สุด

ห้ามถือว่า Learning Goal ทั้งหมดเป็นสิ่งที่นักเรียน
ต้องแสดงให้เห็นในคำตอบเดียว

ห้ามเพิ่มข้อกำหนดที่คำถามไม่ได้ถาม

==================================================
LEARNING GOAL
==================================================

{learning_goal}

==================================================
CURRENT LEARNING QUESTION
==================================================

{question}

==================================================
EXPECTED LEARNING EVIDENCE
==================================================

{evidence_text}

กติกา:
- ใช้เป็นแนวทาง ไม่ใช่ checklist ที่ต้องครบทุกข้อเสมอ
- หากนักเรียนแสดงแกนความเข้าใจที่ถูกต้องแล้ว
  อย่าลดระดับเพียงเพราะรายละเอียดเล็กน้อยยังไม่ครบ
- อย่าสร้างข้อกำหนดใหม่จากความรู้ทั่วไป

==================================================
PRACTICE CONTEXT
==================================================

{practice_text}

หากเป็นโจทย์ฝึก ให้ประเมินว่านักเรียนตอบโจทย์ที่กำหนดจริงหรือไม่
ไม่ใช่ประเมินจาก Algorithm ในอุดมคติที่คุณสร้างขึ้นเอง

==================================================
PREVIOUS ATTEMPTS
==================================================

{previous_text}

กติกาสำคัญสำหรับ Previous Attempts:

- เปรียบเทียบคำตอบปัจจุบันกับคำตอบก่อนหน้า
- ระบุการพัฒนาที่เกิดขึ้นจริง
- หากนักเรียนแก้จุดที่เคยขาดได้แล้ว
  ห้ามบอกว่ายังขาดจุดเดิมซ้ำ
- หากยังขาดจุดเดิม ให้บอกอย่างเฉพาะเจาะจง
- Feedback ต้องสะท้อน Learning Progression
- การเปลี่ยนจาก "ยังไม่มีแนวคิด" เป็น
  "เริ่มมีแนวคิดแต่ยังไม่ละเอียด" ถือเป็นการพัฒนา

==================================================
CURRENT STUDENT ANSWER
==================================================

{student_answer}

==================================================
IMPORTANT: RESPONSE TYPE
==================================================

ให้จำแนกคำตอบก่อนว่าเป็น:

ALGORITHM_ANSWER
= นักเรียนกำลังส่ง Algorithm / ขั้นตอนการแก้ปัญหา

CONCEPTUAL_QUESTION
= นักเรียนกำลังถามเพื่อขอความเข้าใจ
เช่น:
- แค่ if ไม่พอหรอ
- ทำไมต้องใช้ loop
- if กับ loop ต่างกันยังไง

ถ้าเป็น CONCEPTUAL_QUESTION:
- ตอบ "คำถามที่ถูกถาม" โดยตรงเป็นประโยคแรก โดยพูดกับผู้ถามว่า "คุณ" ห้ามใช้คำว่า "นักเรียน"
  ห้ามเริ่มด้วยการชมคำถามหรือสรุปว่าเป็นจุดแข็งแทนคำตอบ
- อธิบายเหตุผลต่อทันที โดยยึดโจทย์ปัจจุบันเป็นบริบทหลัก
  (กรณีนี้คือการตอบคำถามที่ถูกถามตรง ๆ จึงอธิบายได้เต็มที่ ไม่ต้องถามนำ)
- ถ้าถามเปรียบเทียบโครงสร้าง เช่น if กับ loop ให้บอกหน้าที่ของแต่ละโครงสร้างและชี้ว่าในโจทย์นี้ใช้ส่วนไหน เพราะอะไร
- ถ้าคำถามมีรูปแบบ "แค่ X ไม่พอหรอ" ให้ตอบชัดเจนว่า X เพียงพอหรือไม่ และระบุขั้นตอนอื่นที่โจทย์ยังต้องใช้
- ห้ามสร้างเงื่อนไขหรือข้อกำหนดที่ไม่มีในโจทย์
- ไม่ควรตัดสินว่า Algorithm ของนักเรียนผิดเพียงเพราะเขากำลังถาม
- ไม่ควรเพิ่ม attempt
- next_action = EXPLAIN
- understanding_level = PARTIAL
- feedback ต้องเป็นคำอธิบาย ไม่ใช่ feedback เชิงตำหนิ
- ปิดท้ายด้วยคำชวนให้ผู้เรียนกลับไปปรับ Algorithm โดยไม่เฉลย Algorithm ทั้งหมด

==================================================
UNDERSTANDING LEVEL
==================================================

GOOD
ใช้เมื่อ:
- คำตอบตรงคำถาม
- สาระสำคัญถูกต้อง
- แสดงแกนความเข้าใจที่จำเป็น
- ไม่มี misconception สำคัญ

PARTIAL
ใช้เมื่อ:
- เข้าใจบางส่วน
- มีแกนหลักถูกต้อง
- แต่ส่วนสำคัญที่คำถามต้องการยังขาด/ไม่ชัด
- หรือยังไม่ตรงกับโจทย์บางส่วน
- สามารถพัฒนาได้ด้วย Hint

NEEDS_IMPROVEMENT
ใช้เมื่อ:
- ไม่ตอบคำถาม (ไม่เกี่ยวข้องกับคำถามเลย)
- ผิดสาระสำคัญ
- มี misconception สำคัญ
- หรือไม่แสดงความเข้าใจที่จำเป็น

หมายเหตุ: แยกสองกรณีนี้ในการให้ feedback
1. คำตอบไม่เกี่ยวข้องกับคำถามเลย -> บอกตรง ๆ ว่ายังไม่ได้ตอบคำถาม
   แล้วย้ำคำถามปัจจุบันอีกครั้งเพื่อให้ตอบใหม่ ห้ามอธิบายเนื้อหาหรือให้คำใบ้
2. คำตอบเกี่ยวข้องแต่มี misconception -> ห้ามแก้ให้ตรง ๆ
   ให้ถามคำถามที่ชวนตรวจสอบจุดที่เข้าใจผิดนั้นโดยเฉพาะ

==================================================
SPECIAL RULE: PRACTICE
==================================================

หากโจทย์ถาม "หาจำนวนลูกค้าที่มียอดขายเกิน 500 บาท"
อย่าชมการรวมยอดทั้งหมดว่าเป็นคำตอบหลัก
เว้นแต่นักเรียนระบุว่าเป็นส่วนเสริมและไม่ทำให้เป้าหมายหลักผิด

สำหรับโจทย์ที่มีข้อมูลหลายรายการ:
- Loop ใช้สำหรับวนข้อมูลหลายรายการ
- If ใช้ตรวจเงื่อนไขของข้อมูลแต่ละรายการ
แต่จะกล่าวถึงแนวคิดนี้ก็ต่อเมื่อโจทย์ต้องการจริง

==================================================
FEEDBACK
==================================================

หลักการพูดกับผู้เรียน (ใช้กับทุกกรณี ทั้ง ALGORITHM_ANSWER และ CONCEPTUAL_QUESTION):
- เรียกผู้เรียนว่า "คุณ" ห้ามใช้คำว่า "นักเรียน" ในการพูดกับผู้เรียนตรง ๆ
- ห้ามบอกขั้นตอนหรือคำตอบที่ยังขาดโดยตรง ให้ถามคำถามชี้นำ 1 ข้อแทน
  เพื่อให้คุณกลับไปตรวจสอบและมองเห็นจุดนั้นด้วยตนเอง
  (คำถามชี้นำนี้เป็นคำถามเกี่ยวกับ Algorithm ของคุณโดยตรง
  ไม่ใช่คำถามอภิปัญญา/Metacognitive Question)
- ห้ามสร้างคำถามอภิปัญญา (Metacognitive Question) ขึ้นเอง
  คำถามลักษณะนี้ต้องมาจาก QP.xlsx ที่ระบบเลือกให้เท่านั้น
- ถ้าพบความเข้าใจผิด (เช่น สับสนระหว่าง loop กับ condition)
  ห้ามแก้ให้ตรง ๆ ให้ถามคำถามที่ชวนกลับไปตรวจจุดนั้นด้วยตนเอง

feedback:
- สรุปสิ่งที่เข้าใจในคำถามปัจจุบัน โดยพูดกับคุณโดยตรง
- ถ้าเป็น CONCEPTUAL_QUESTION ให้ตอบคำถามนั้นโดยตรง
- ถ้าคำตอบไม่เกี่ยวข้องกับคำถามเลย (และไม่ใช่ CONCEPTUAL_QUESTION):
  บอกตรง ๆ ว่าคำตอบนี้ยังไม่ได้ตอบคำถาม แล้วย้ำคำถามปัจจุบันอีกครั้ง
  เพื่อให้ตอบใหม่ ห้ามอธิบายเนื้อหาหรือให้คำใบ้ในกรณีนี้

strength:
- ระบุสิ่งที่ทำได้จริงในคำตอบเท่านั้น
- ถ้าไม่มีจุดแข็งที่ปรากฏจริงในคำตอบ ให้ตอบเป็นค่าว่าง ""
  ห้ามแต่งจุดแข็งขึ้นมาเอง

improvement:
- ห้ามระบุสิ่งที่ยังขาดโดยตรง ให้ตั้งเป็นคำถามชี้นำ 1 ข้อแทน
  ที่ชวนกลับไปตรวจสอบจุดที่ยังขาดหรือเข้าใจผิดด้วยตนเอง
- ห้ามกล่าวซ้ำสิ่งที่นักเรียนเพิ่งแก้ได้แล้ว
- ห้ามเพิ่มหัวข้อที่โจทย์ไม่ได้ต้องการ
- ถ้าไม่มีจุดที่ต้องพัฒนาจริง ให้ตอบเป็นค่าว่าง ""

==================================================
ADAPTIVE ACTION
==================================================

GOOD -> CONTINUE
PARTIAL -> HINT
NEEDS_IMPROVEMENT -> EXPLAIN

CONCEPTUAL_QUESTION -> EXPLAIN

==================================================
OUTPUT
==================================================

ตอบ JSON เท่านั้น:

{{
    "response_type": "ALGORITHM_ANSWER | CONCEPTUAL_QUESTION",
    "understanding_level": "GOOD | PARTIAL | NEEDS_IMPROVEMENT",
    "feedback": "",
    "strength": "",
    "improvement": "",
    "progress": "",
    "next_action": "CONTINUE | HINT | EXPLAIN"
}}

ห้ามให้คะแนนตัวเลข
ห้ามใช้เปอร์เซ็นต์
ห้ามมี Markdown code fence
ห้ามมีข้อความนอก JSON
"""

    return prompt


# ==============================================
# PARSE LLM RESPONSE
# ==============================================

def parse_evaluation_response(response_text):
    try:
        response_text = _clean_json_response(response_text)
        result = json.loads(response_text)

        understanding_level = result.get(
            "understanding_level",
            "PARTIAL"
        )

        if understanding_level not in VALID_LEVELS:
            understanding_level = "PARTIAL"

        response_type = result.get(
            "response_type",
            "ALGORITHM_ANSWER"
        )

        if response_type not in VALID_RESPONSE_TYPES:
            response_type = "ALGORITHM_ANSWER"

        next_action = result.get(
            "next_action",
            "EXPLAIN"
        )

        if next_action not in VALID_ACTIONS:
            next_action = "EXPLAIN"

        if response_type == "CONCEPTUAL_QUESTION":
            understanding_level = "PARTIAL"
            next_action = "EXPLAIN"

        return {
            "success": True,
            "response_type": response_type,
            "understanding_level": understanding_level,
            "feedback": result.get("feedback", ""),
            "strength": result.get("strength", ""),
            "improvement": result.get("improvement", ""),
            "progress": result.get("progress", ""),
            "next_action": next_action
        }

    except Exception as e:
        return {
            "success": False,
            "error": type(e).__name__,
            "message": str(e),
            "understanding_level": "NEEDS_IMPROVEMENT",
            "response_type": "ALGORITHM_ANSWER",
            "feedback": "ระบบยังไม่สามารถวิเคราะห์คำตอบได้",
            "strength": "",
            "improvement": "",
            "progress": "",
            "next_action": "EXPLAIN"
        }


# ==============================================
# EVALUATE STUDENT RESPONSE
# ==============================================

def evaluate_student_response(
    learning_goal,
    question,
    student_answer,
    llm_function,
    previous_attempts=None,
    expected_evidence=None,
    practice_context=None
):
    """
    Backward compatible:
    4 arguments เดิมยังใช้ได้

    Optional:
    previous_attempts
    expected_evidence
    practice_context
    """

    if not student_answer:
        return {
            "success": False,
            "error": "EMPTY_ANSWER",
            "message": "ไม่พบคำตอบของผู้เรียน"
        }

    student_answer = student_answer.strip()

    # คำถามเชิงแนวคิดไม่ถือเป็นการส่ง Algorithm ใหม่
    # จึงไม่ควรใช้ attempt และควรอธิบายแนวคิดโดยตรง
    if _looks_like_conceptual_question(student_answer):
        prompt = build_evaluation_prompt(
            learning_goal=learning_goal,
            question=question,
            student_answer=student_answer,
            previous_attempts=previous_attempts,
            expected_evidence=expected_evidence,
            practice_context=practice_context
        )
        prompt += """

IMPORTANT RESPONSE-TYPE OVERRIDE:
The student's latest message is a conceptual question.
Do NOT grade it as an Algorithm Answer.
Answer the student's exact question FIRST, then explain why using the current practice problem.
For example, if the student asks "แค่ if ไม่พอหรอ", explicitly state whether if alone is sufficient for THIS problem, then distinguish the role of if from the other required processing steps.
Do not merely praise the question or restate what the student asked.
Do NOT consume an attempt.
Return response_type=CONCEPTUAL_QUESTION and next_action=EXPLAIN.
"""
        try:
            llm_response = llm_function(prompt)
        except Exception as e:
            return {
                "success": False,
                "error": "LLM_ERROR",
                "message": str(e)
            }

        result = parse_evaluation_response(llm_response)
        result["response_type"] = "CONCEPTUAL_QUESTION"
        result["understanding_level"] = "PARTIAL"
        result["next_action"] = "EXPLAIN"
        result["student_answer"] = student_answer
        return result

    if len(student_answer) < 3:
        return {
            "success": True,
            "response_type": "ALGORITHM_ANSWER",
            "understanding_level": "NEEDS_IMPROVEMENT",
            "feedback": "ลองอธิบายเพิ่มเติมอีกนิดนะ 😊",
            "strength": "",
            "improvement": "ลองอธิบายแนวคิดด้วยภาษาของตัวเองเพิ่มเติม",
            "progress": "",
            "next_action": "HINT"
        }

    prompt = build_evaluation_prompt(
        learning_goal=learning_goal,
        question=question,
        student_answer=student_answer,
        previous_attempts=previous_attempts,
        expected_evidence=expected_evidence,
        practice_context=practice_context
    )

    try:
        llm_response = llm_function(prompt)
    except Exception as e:
        return {
            "success": False,
            "error": "LLM_ERROR",
            "message": str(e)
        }

    result = parse_evaluation_response(llm_response)
    result["student_answer"] = student_answer

    return result
