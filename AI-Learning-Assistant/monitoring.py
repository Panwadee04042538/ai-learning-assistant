class MonitoringSession:

    def __init__(self, topic):

        self.topic = topic.lower()
        self.attempts = []

    # ==========================
    # เพิ่ม Submission
    # ==========================

    def add_submission(self, submission):

        self.attempts.append({
            "submission": submission,
            "feedback": None
        })

    # ==========================
    # เพิ่ม Feedback
    # ==========================

    def add_feedback(self, feedback):

        if self.attempts:

            self.attempts[-1]["feedback"] = feedback

    # ==========================
    # จำนวนครั้งที่ส่ง
    # ==========================

    def get_attempt_count(self):

        return len(self.attempts)

    # ==========================
    # ประวัติการส่งทั้งหมด
    # ==========================

    def get_history(self):

        return self.attempts

    # ==========================
    # Prompt
    # ==========================

    def build_prompt(self):

        # -----------------------------------
        # Guideline ตามหัวข้อ
        # -----------------------------------

        if self.topic == "algorithm":

            guideline = """
คุณกำลังประเมินผลงานในหัวข้อ Algorithm

โปรดประเมินเฉพาะ

- ความถูกต้องของลำดับขั้นตอน
- ความครบถ้วนของเงื่อนไข
- ความถูกต้องของตรรกะ
- ความชัดเจนของขั้นตอนการทำงาน

ห้ามประเมิน

- รูปแบบการเขียน Pseudocode
- Syntax ของภาษาโปรแกรม
- รูปแบบ Flowchart

หากผู้เรียนใช้คำว่า if, else หรือภาษาอังกฤษ
ให้ประเมินเฉพาะตรรกะของอัลกอริทึม
ห้ามแนะนำให้เปลี่ยนเป็น Pseudocode
"""

        elif self.topic == "pseudocode":

            guideline = """
คุณกำลังประเมินผลงานในหัวข้อ Pseudocode

โปรดประเมิน

- รูปแบบการเขียน Pseudocode
- ความสม่ำเสมอของคำสั่ง
- การจัดรูปแบบ
- ความถูกต้องของตรรกะ

ห้ามประเมินเรื่อง Flowchart
"""

        elif self.topic == "flowchart":

            guideline = """
คุณกำลังประเมินผลงานในหัวข้อ Flowchart

โปรดประเมิน

- ความถูกต้องของสัญลักษณ์
- ทิศทางลูกศร
- ลำดับการทำงาน
- ความถูกต้องของตรรกะ

ห้ามประเมินรูปแบบ Pseudocode
"""

        else:

            guideline = ""

        # -----------------------------------
        # Prompt
        # -----------------------------------

        prompt = f"""
คุณคือ AI Learning Assistant

หัวข้อการเรียน : {self.topic}

ผู้เรียนกำลังอยู่ในขั้น Monitoring

{guideline}

ต่อไปนี้คือประวัติการส่งผลงานทั้งหมด

"""

        for i, attempt in enumerate(self.attempts, start=1):

            prompt += f"""

=====================================

ครั้งที่ {i}

ผลงาน

{attempt["submission"]}

"""

            if attempt["feedback"]:

                prompt += f"""

Feedback ก่อนหน้า

{attempt["feedback"]}

"""

        prompt += """

=====================================

โปรดทำหน้าที่เป็นโค้ช (Coach)

ห้ามเฉลยคำตอบทั้งหมด

หากผู้เรียนทำผิด
ให้ใช้คำถามชี้นำและ Hint
เพื่อให้ผู้เรียนคิดและแก้ไขด้วยตนเอง

ให้ตอบตามหัวข้อดังนี้

1. สิ่งที่ผู้เรียนทำได้ดี

2. จุดที่ควรปรับปรุง

3. เปรียบเทียบกับการส่งครั้งก่อน
(หากเป็นครั้งแรกให้ระบุว่าเป็นการส่งครั้งแรก)

4. Hint เพื่อให้ผู้เรียนคิดต่อ
(ห้ามเฉลยคำตอบทั้งหมด)

5. ถามคำถามชี้นำเพิ่มเติม

ตอบเป็นภาษาไทย
"""

        return prompt