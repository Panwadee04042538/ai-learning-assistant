class EvaluationSession:

    def __init__(self, topic, goal_id=None, qp=None):
        self.topic = topic.lower()
        self.goal_id = goal_id
        self.qp = qp

        self.answers = []
        self.current = 0

        self.questions = self._get_questions()

    # ==========================
    # คำถาม Evaluation
    # ==========================

    def _get_questions(self):

    # ==========================================
    # Algorithm - LG01
    # ==========================================
        if self.topic == "algorithm" and self.goal_id == "LG01":
            return [
            "ลองสรุปด้วยคำของตัวเองว่าอัลกอริทึม (Algorithm) คืออะไร "
            "และอัลกอริทึม (Algorithm) ที่ดีควรมีลักษณะอย่างไร?"
        ]

    # ==========================================
    # Algorithm - LG02
    # ==========================================
        elif self.topic == "algorithm" and self.goal_id == "LG02":
            return [
            "การวิเคราะห์โจทย์ก่อนออกแบบอัลกอริทึม (Algorithm) "
            "ช่วยให้คุณเข้าใจปัญหาและเตรียมข้อมูลได้ดีขึ้นอย่างไร?"
        ]

    # ==========================================
    # Algorithm - LG03
    # ==========================================
        elif self.topic == "algorithm" and self.goal_id == "LG03":
            return [
            "แนวทางที่คุณกำหนดไว้สามารถแก้ปัญหาตามโจทย์ได้อย่างไร?"
        ]

    # ==========================================
    # Algorithm - LG04
    # ==========================================
        elif self.topic == "algorithm" and self.goal_id == "LG04":
            return [
            "การจัดลำดับขั้นตอนที่คุณออกแบบ "
            "ช่วยให้อัลกอริทึม (Algorithm) ทำงานได้ถูกต้องอย่างไร?"
        ]

    # ==========================================
    # Algorithm - LG05
    # ==========================================
        elif self.topic == "algorithm" and self.goal_id == "LG05":
            return [
            "จากการทดลองและตรวจสอบอัลกอริทึม (Algorithm) "
            "คุณคิดว่าอัลกอริทึม (Algorithm) นี้ถูกต้องและครอบคลุมโจทย์แล้วหรือไม่ "
            "เพราะอะไร?"
        ]

    # ==========================================
    # Algorithm - LG06
    # ==========================================
        elif self.topic == "algorithm" and self.goal_id == "LG06":
            return [
            "จากโครงสร้างที่คุณเลือก เช่น รูปแบบลำดับขั้นตอน (Sequence), Selection หรือ Loop "
            "คุณคิดว่าโครงสร้างนั้นเหมาะกับโจทย์หรือไม่ เพราะอะไร?"
        ]

    # ==========================================
    # Algorithm - LG07
    # ==========================================
        elif self.topic == "algorithm" and self.goal_id == "LG07":
            return [
            "จากการตรวจสอบอัลกอริทึม (Algorithm) "
            "คุณพบจุดที่ควรปรับปรุงตรงไหน และการปรับปรุงนั้นช่วยให้อัลกอริทึม (Algorithm) ดีขึ้นอย่างไร?"
        ]

    # ==========================================
    # Algorithm - LG08
    # ==========================================
        elif self.topic == "algorithm" and self.goal_id == "LG08":
            return [
            "จากโจทย์ที่คุณฝึกออกแบบ "
            "คุณคิดว่าอัลกอริทึม (Algorithm) ที่สร้างขึ้นสามารถแก้ปัญหาได้ครบถ้วนหรือไม่ "
            "และมีส่วนใดที่ควรปรับปรุงอีกหรือไม่?"
        ]

    # ==========================================
    # Pseudocode
    # ==========================================
        elif self.topic == "pseudocode":
            return [
            "Pseudocode คืออะไร?",
            "Pseudocode มีประโยชน์อย่างไรในการออกแบบโปรแกรม?",
            "คุณจะเขียน Pseudocode ให้มีลำดับขั้นตอนที่ชัดเจนได้อย่างไร?"
        ]

    # ==========================================
    # Flowchart
    # ==========================================
        elif self.topic == "flowchart":
            return [
            "Flowchart คืออะไร?",
            "สัญลักษณ์พื้นฐานของ Flowchart มีอะไรบ้าง?",
            "คุณจะตรวจสอบความถูกต้องของลำดับการทำงานใน Flowchart ได้อย่างไร?"
        ]

        return []

    # ==========================
    # คำถามปัจจุบัน
    # ==========================

    def get_current_question(self):

        if self.current < len(self.questions):

            return self.questions[self.current]

        return None

    # ==========================
    # เพิ่มคำตอบ
    # ==========================

    def add_answer(self, answer):

        self.answers.append(answer)

        self.current += 1

    # ==========================
    # ตรวจสอบว่าทำครบหรือยัง
    # ==========================

    def is_finished(self):

        return self.current >= len(self.questions)

    # ==========================
    # ผลการทำ Evaluation
    # ==========================

    def get_result(self):

        return {
            "topic": self.topic,
            "questions": self.questions,
            "answers": self.answers
        }

    # ==========================
    # สร้าง Prompt สำหรับ AI
    # ==========================

    def build_prompt(self):

        prompt = f"""
คุณคือ AI Learning Assistant

ผู้เรียนกำลังทำ Evaluation

หัวข้อการเรียน : {self.topic}

คำถามและคำตอบของผู้เรียนมีดังนี้

"""

        for i, (question, answer) in enumerate(
            zip(self.questions, self.answers),
            start=1
        ):

            prompt += f"""
ข้อ {i}

คำถาม:
{question}

คำตอบของผู้เรียน:
{answer}

"""

        prompt += """
=====================================

โปรดประเมินความเข้าใจของผู้เรียน

โดยพิจารณาจากคำตอบที่ผู้เรียนให้มา

ให้ประเมินดังนี้

1. ระดับความเข้าใจของผู้เรียน

2. สิ่งที่ผู้เรียนเข้าใจได้ดี

3. สิ่งที่ผู้เรียนยังเข้าใจไม่ชัดเจน

4. จุดที่ควรพัฒนาต่อ

5. สรุปผลการประเมิน

ตอบเป็นภาษาไทย

ห้ามสร้างคำตอบที่ผู้เรียนไม่ได้ให้ไว้
และห้ามสรุปว่าผู้เรียนเข้าใจในเรื่องที่ไม่มีหลักฐานจากคำตอบ
"""

        return prompt