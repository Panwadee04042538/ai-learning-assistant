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
# RULE-BASED REQUIRED COMPONENT CHECK
# ==============================================

REQUIRED_KEYWORDS = {
    "จบ": ["จบ", "สิ้นสุด", "end", "End", "stop", "Stop"],
    "output": [
        "แสดง", "print", "output", "แสดงผล", "แสดงค่า", "แสดงผลลัพธ์"
    ],
}

MISSING_COMPONENT_NAMES = {
    "จบ": "จบ",
    "output": "แสดงผล",
}

# ตัวอย่างที่แนะนำให้เด็กเพิ่ม (ขาดข้อเดียว)
MISSING_COMPONENT_HINTS = {
    "จบ": "'จบ' เป็นขั้นสุดท้าย",
    "output": "เช่น 'แสดง [ผลลัพธ์]'",
}

# ลำดับแสดงเมื่อขาดทั้งสองข้อ: แสดงผลก่อน แล้วค่อยจบ
MISSING_COMPONENT_DISPLAY_ORDER = ["output", "จบ"]

BYPASS_PROMPT_NOTE = """

หมายเหตุ: อัลกอริทึมนี้ขาดขั้นบังคับบางอย่าง
ให้ประเมิน Process และ Logic เท่านั้น
ผลต้องเป็น PARTIAL เสมอ ไม่ใช่ GOOD
"""


def build_missing_components_feedback(missing):
    """
    สร้างข้อความบอกเด็กว่าขาดขั้นบังคับอะไร (missing = รายชื่อ component
    ที่ขาด เช่น ["จบ"], ["output"], ["จบ", "output"])
    """
    if len(missing) == 1:
        name = missing[0]
        return (
            f"อัลกอริทึมยังขาดขั้น{MISSING_COMPONENT_NAMES[name]}\n"
            f"ลองเพิ่ม {MISSING_COMPONENT_HINTS[name]} ก่อนส่งมาใหม่"
        )

    lines = ["อัลกอริทึมยังขาด 2 ขั้นตอนสำคัญ"]

    for name in MISSING_COMPONENT_DISPLAY_ORDER:
        if name in missing:
            lines.append(
                f"• ขาดขั้น{MISSING_COMPONENT_NAMES[name]} — "
                f"ลองเพิ่ม {MISSING_COMPONENT_HINTS[name]}"
            )

    return "\n".join(lines)


def _contains_keyword(text, keyword):
    """
    คำภาษาอังกฤษต้องเป็นคำเดี่ยว ๆ (ไม่ใช่ส่วนหนึ่งของคำอื่น เช่น "send",
    "append" ไม่ถือว่ามี "end") และไม่สนตัวพิมพ์เล็ก/ใหญ่ ส่วนคำไทยเช็คแบบ
    substring เพราะภาษาไทยไม่มีช่องว่างคั่นระหว่างคำ
    """
    if keyword.isascii():
        pattern = rf"(?<![A-Za-z]){re.escape(keyword)}(?![A-Za-z])"
        return re.search(pattern, text, flags=re.IGNORECASE) is not None

    return keyword in text


def find_missing_required_components(student_answer):
    """คืนรายชื่อ component ที่ขาด (จบ / output) เรียงตามลำดับ [] ถ้าครบ"""
    text = student_answer or ""

    return [
        component
        for component, keywords in REQUIRED_KEYWORDS.items()
        if not any(_contains_keyword(text, kw) for kw in keywords)
    ]


def check_required_components(student_answer):
    """
    Rule-based check ก่อนส่งให้ Typhoon: Algorithm ต้องมีขั้น "จบ" และขั้น
    แสดงผล (output) เสมอ

    Returns
    -------
    dict หรือ None
        ถ้าขาดอย่างใดอย่างหนึ่ง คืนผลประเมิน PARTIAL ทันทีพร้อม feedback
        ที่ระบุว่าขาดอะไร (ไม่ต้องส่งให้ Typhoon) ถ้าครบทั้งสอง คืน None
        เพื่อให้ไปประเมิน Process ต่อตามปกติ

        ผลที่ถูกตีกลับนี้ "ไม่นับ attempt" (counts_attempt=False) เพราะ
        เด็กยังไม่ได้ถูกประเมิน Logic จริง ๆ แค่แจ้งให้เพิ่มขั้นที่ขาดก่อน
        main.py ต้องไม่เพิ่ม attempt / ไม่ให้ hint / ไม่ใส่ attempt_history
    """
    missing = find_missing_required_components(student_answer)

    if not missing:
        return None

    return {
        "success": True,
        "response_type": "ALGORITHM_ANSWER",
        "understanding_level": "PARTIAL",
        "feedback": build_missing_components_feedback(missing),
        "strength": "",
        "improvement": "",
        "progress": "",
        "next_action": "HINT",
        "missing_components": missing,
        "rule_based": True,
        "counts_attempt": False,
    }


# ==============================================
# BUILD EVALUATION PROMPT
# ==============================================

def build_evaluation_prompt(
    learning_goal,
    question,
    student_answer,
    previous_attempts=None,
    expected_evidence=None,
    practice_context=None,
    expected_output=None,
    model_answer=None
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

    output_text = expected_output.strip() if expected_output else (
        "ไม่ได้ระบุ Output ที่ต้องแสดงผลชัดเจน"
    )

    model_answer_text = model_answer.strip() if model_answer else (
        "ไม่ได้ระบุ Model Answer อ้างอิง ให้ประเมินจากเกณฑ์อื่นด้านบนแทน"
    )

    prompt = f"""
คุณเป็น AI Learning Assistant สำหรับประเมินการเรียนรู้ของนักเรียนอาชีวศึกษา
เรื่องการออกแบบ Algorithm

==================================================
บริบทสำคัญ: นี่คือขั้นประเมิน Algorithm ไม่ใช่ Planning QP
==================================================

ขั้นตอนนี้คือการประเมิน Algorithm ที่นักเรียนเขียนขึ้นจริง ไม่ใช่การตอบ
คำถามวางแผน (Planning QP) เช่น "โจทย์ต้องการให้แก้ปัญหาอะไร" ซึ่งเป็น
คนละขั้นตอนกันและถูกตอบแยกไปแล้วก่อนหน้านี้

ให้ประเมินเฉพาะความถูกต้องและความสมบูรณ์ของ Algorithm ที่ส่งมาเทียบกับ
เป้าหมายของโจทย์เท่านั้น

ห้ามนำคำถาม Planning QP มาใช้เป็นเกณฑ์ประเมิน และห้ามตัดสินว่าคำตอบผิด
เพียงเพราะไม่ได้ตอบคำถามวางแผนนั้นซ้ำอีกครั้ง

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
(นี่คือเป้าหมายของ Algorithm ที่ต้องประเมิน ไม่ใช่คำถาม Planning QP
ที่ต้องตอบเป็นข้อความซ้ำ)

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
EXPECTED OUTPUT (จากโจทย์)
==================================================

{output_text}

ใช้ข้อความนี้เป็นตัวอ้างอิงว่า Output ที่โจทย์ต้องการคืออะไร สำหรับ
ตัดสินองค์ประกอบข้อ 4 (Output) ในหัวข้อ "เกณฑ์การประเมิน: ตรวจสอบ
5 องค์ประกอบหลัก" ด้านล่าง

==================================================
MODEL ANSWER (เฉลยอ้างอิงสำหรับระบบ ไม่ใช่คำตอบตายตัวที่ต้องเขียนตาม)
==================================================

{model_answer_text}

ใช้ Model Answer เป็นตัวอ้างอิงเฉพาะสำหรับองค์ประกอบข้อ 3 (Process)
ว่าโจทย์นี้ต้องมีการประมวลผลแบบใดบ้าง (คำนวณ/ตรวจเงื่อนไข/วนซ้ำ) เท่านั้น
ไม่ใช่นำ Algorithm ทั้งฉบับของนักเรียนมาเทียบกับ Model Answer แบบ
เปอร์เซ็นต์อีกต่อไป การตัดสิน understanding_level ให้ใช้เกณฑ์ 5
องค์ประกอบในหัวข้อถัดไปเท่านั้น ถ้าไม่ได้ระบุ Model Answer ไว้ (ข้อความ
ด้านบนบอกว่าไม่ได้ระบุ) ให้อนุมาน Process ที่จำเป็นจากคำถามปัจจุบันแทน
ห้ามอนุมาน Model Answer ทั้งฉบับขึ้นเอง

==================================================
เกณฑ์การประเมิน: ตรวจสอบ 5 องค์ประกอบหลัก (บังคับใช้เสมอ)
==================================================
(กฎนี้ใช้ตัดสินก่อนเสมอเมื่อ response_type = ALGORITHM_ANSWER
ห้ามมองข้ามแม้ Previous Attempts หรือรอบก่อนหน้าจะเคยได้ PARTIAL มาก่อน)

ตรวจ Algorithm ที่นักเรียนส่งมาว่ามีองค์ประกอบต่อไปนี้ครบกี่ข้อ จาก 5 ข้อ
แต่ละข้อมีน้ำหนักเท่ากันข้อละ 20%:

1. เริ่มต้น — มีขั้นเริ่มต้นชัดเจน (เช่น "เริ่มต้น", "Start")
2. Input — มีการรับค่า/ข้อมูลนำเข้า
3. Process — มีการประมวลผลตามที่โจทย์ต้องการ (คำนวณ/ตรวจเงื่อนไข/วนซ้ำ
   ขึ้นอยู่กับโจทย์ว่าต้องการแบบใด ใช้ MODEL ANSWER ด้านบนเป็นตัวอ้างอิง
   ว่าโจทย์นี้ต้องมี Process แบบใดบ้าง)
4. Output (required เสมอ) — มีการแสดงผลลัพธ์ตรง "ความหมาย" กับ
   EXPECTED OUTPUT ด้านบน
5. จบ (required เสมอ) — มีขั้นสิ้นสุดชัดเจน (เช่น "จบ", "สิ้นสุด", "End")

วิธีตัดสิน "ความหมาย" ของแต่ละองค์ประกอบ:
- ตัดสินจากความหมาย ไม่ใช่ถ้อยคำ ชื่อตัวแปร หรือรูปแบบการเขียน ถ้า
  นักเรียนเขียนด้วยคำพูดของตนเองแต่ความหมายตรงกับองค์ประกอบนั้น ให้
  ถือว่ามีองค์ประกอบนั้นครบแล้ว เช่น องค์ประกอบ Output ที่โจทย์ระบุว่า
  "แสดงยอดขายรวม" นักเรียนเขียนว่า "แสดงยอดขายทั้งหมด" หรือ "แสดง
  total และ count" กับ "แสดง total, count" ถือว่าเป็นองค์ประกอบ Output
  เดียวกัน
- ให้ถือว่าขาดองค์ประกอบใดก็ต่อเมื่อไม่มีขั้นตอนนั้นเลย หรือสิ่งที่เขียน
  คนละเรื่องกับองค์ประกอบนั้นจริง ๆ เท่านั้น ไม่ใช่เพราะถ้อยคำต่างจาก
  โจทย์หรือ Model Answer

Output และจบเป็น required component เสมอ ต่างจากข้อ 1-3 (เริ่มต้น,
Input, Process) ที่ขาดได้ 1 ข้อแล้วยังผ่าน นับจำนวนองค์ประกอบที่มีครบ
(0-5 ข้อ) แล้วใช้กฎนี้ตัดสิน understanding_level โดยตรง ตามลำดับนี้
ห้ามใช้เกณฑ์อื่นมาลดหรือเพิ่มระดับอีก:

- ถ้าขาด Output -> PARTIAL ไม่ว่าจะครบกี่ข้อ (แม้ครบ 4/5 หรือ 5/5
  ในองค์ประกอบอื่นก็ตาม ห้ามให้ GOOD เด็ดขาด)
- ถ้าขาดจบ -> PARTIAL ไม่ว่าจะครบกี่ข้อ (แม้ครบ 4/5 หรือ 5/5
  ในองค์ประกอบอื่นก็ตาม ห้ามให้ GOOD เด็ดขาด)
- ครบ 5/5 หรือ 4/5 (ต้องมีทั้ง Output และจบ) -> GOOD
- ครบ 3/5 -> PARTIAL
- ครบ 2/5 หรือน้อยกว่า -> NEEDS_IMPROVEMENT

ข้อยกเว้น: ถ้าขาดทั้ง Output และองค์ประกอบอื่นจนนับได้รวม ≤2 ข้อ ให้ใช้
NEEDS_IMPROVEMENT ตามเกณฑ์จำนวนข้อ (แย่กว่า PARTIAL อยู่แล้ว) ไม่ใช่
PARTIAL จากกฎขาด Output/จบด้านบน

ห้ามเด็ดขาด:
- เมื่อครบตามเกณฑ์ GOOD แล้ว (5/5 หรือ 4/5 ที่มี Output กับจบครบ) ห้าม
  หาเหตุผลอื่นเพิ่มเติมมาลดระดับเป็น PARTIAL อีก แม้จะยังพอมองเห็นจุดที่
  ทำให้ดีขึ้นได้อีก (เช่น รูปแบบการเขียน ความละเอียดของคำอธิบาย สไตล์
  การตั้งชื่อตัวแปร) เพราะสิ่งเหล่านี้ไม่ใช่ 1 ใน 5 องค์ประกอบข้างต้น
- ห้ามใช้ Previous Attempts, ความรู้ทั่วไปนอกเหนือจากโจทย์, หรือ
  รายละเอียดปลีกย่อยที่โจทย์ไม่ได้ระบุ มาเป็นเหตุผลเพิ่มหรือลดจำนวน
  องค์ประกอบที่นับได้
- ห้ามวนกลับไปตรวจซ้ำหาข้อบกพร่องเพิ่มเติมอีกหลังจากนับองค์ประกอบและ
  ตัดสินระดับตามกฎด้านบนแล้ว การประเมินต้องหยุดที่ระดับนั้นทันที

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
    practice_context=None,
    expected_output=None,
    model_answer=None,
    skip_required_check=False
):
    """
    Backward compatible:
    4 arguments เดิมยังใช้ได้

    Optional:
    previous_attempts
    expected_evidence
    practice_context
    expected_output: Output ของโจทย์ (เช่น problem["output"] จาก Problem
        Bank) ใช้ตัดสินองค์ประกอบ "Output" ซึ่งเป็น required component
        เสมอ (ขาดไม่ได้ ไม่ว่าองค์ประกอบอื่นจะครบกี่ข้อ ดูรายละเอียดใน
        build_evaluation_prompt)
    model_answer: เฉลยอ้างอิง (เช่น problem["model_answer"] จาก Problem
        Bank) ใช้เป็นตัวอ้างอิงเฉพาะองค์ประกอบ "Process" เท่านั้น การ
        ตัดสิน understanding_level ใช้จำนวนองค์ประกอบหลักที่ครบ (5 ข้อ)
        ไม่ใช่เปอร์เซ็นต์เทียบกับ Model Answer ทั้งฉบับอีกต่อไป: Output
        และจบเป็น required เสมอ (ขาดข้อใดข้อหนึ่ง = PARTIAL สูงสุด ไม่ว่า
        จะครบกี่ข้อ) ส่วนเริ่มต้น/Input/Process ขาดได้ 1 ข้อแล้วยังผ่าน
        5/5 -> GOOD, 4/5 ที่มี Output+จบครบ -> GOOD, 3/5 -> PARTIAL,
        ≤2/5 -> NEEDS_IMPROVEMENT ดูรายละเอียดใน build_evaluation_prompt
    skip_required_check: True = ข้าม rule-based check (ขาดขั้น "จบ"/ขั้น
        แสดงผล) แล้วส่งให้ Typhoon ประเมินเลย ใช้เมื่อเด็กถูกตีกลับซ้ำเกินเพดาน
        ถ้ายังขาดขั้นบังคับอยู่ผลจะมี rule_check_bypassed=True
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
            practice_context=practice_context,
            expected_output=expected_output,
            model_answer=model_answer
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

    # Rule-based check: ขาดขั้น "จบ" หรือขั้นแสดงผล -> PARTIAL ทันที
    # ไม่ต้องส่งให้ Typhoon ตัดสิน
    rule_check_bypassed = False
    missing_components = []

    if skip_required_check:
        missing_components = find_missing_required_components(student_answer)
        rule_check_bypassed = bool(missing_components)
    else:
        rule_based_result = check_required_components(student_answer)

        if rule_based_result is not None:
            rule_based_result["student_answer"] = student_answer
            return rule_based_result

    prompt = build_evaluation_prompt(
        learning_goal=learning_goal,
        question=question,
        student_answer=student_answer,
        previous_attempts=previous_attempts,
        expected_evidence=expected_evidence,
        practice_context=practice_context,
        expected_output=expected_output,
        model_answer=model_answer
    )

    if rule_check_bypassed:
        prompt += BYPASS_PROMPT_NOTE

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

    if rule_check_bypassed:
        result["rule_check_bypassed"] = True
        result["missing_components"] = missing_components

        # "จบ"/แสดงผลเป็น required เสมอ แม้ปล่อยผ่านให้ Typhoon แล้ว
        # ถ้า Typhoon ให้ GOOD ทั้งที่ยังขาด ต้องบังคับเป็น PARTIAL
        if result.get("understanding_level") == "GOOD":
            result["understanding_level"] = "PARTIAL"
            result["next_action"] = "HINT"
            result["level_capped"] = True

            missing_feedback = build_missing_components_feedback(
                missing_components
            )
            existing = (result.get("improvement") or "").strip()
            result["improvement"] = (
                f"{existing}\n{missing_feedback}".strip()
            )

    return result
