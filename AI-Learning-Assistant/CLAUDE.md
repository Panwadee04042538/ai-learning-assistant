# AI Learning Assistant — ผู้ช่วยอัจฉริยะเสริมสร้างทักษะการออกแบบโปรแกรมตามหลักอภิปัญญา

โปรเจกต์วิทยานิพนธ์ ป.โท (มจพ.) ผู้ใช้คือนักเรียน ปวช. วิชา 21910-1003
หน่วยการเรียน: การออกแบบอัลกอริทึม ผังงาน รหัสเทียม

## หลักการที่ห้ามละเมิด
- บอตต้องไม่ให้คำตอบ/Algorithm สำเร็จรูป ใช้คำถามชี้นำ คำใบ้แบบลำดับขั้น และ feedback
- คำถามอภิปัญญา (QP) ต้องมาจาก `QP.xlsx` เท่านั้น ห้ามให้ AI แต่งคำถามอภิปัญญาเอง
- คำใบ้ต้องมาจาก `knowledge_base/hint_bank.json` (3 ระดับต่อ Question ID)
- ทุกการโต้ตอบที่เป็นข้อมูลวิจัยต้องบันทึกผ่าน `logger.py`
  (student_responses, metacognitive_responses, hints_used, final_status)
- ข้อความตอบนักเรียนเป็นภาษาไทย ระดับอาชีวศึกษา

## เทคโนโลยี
- Python 3.13, discord.py (prefix `!`), python-dotenv
- LLM: Typhoon ผ่าน OpenAI SDK (`typhoon_service.py`)
  หมายเหตุ: ชื่อฟังก์ชันยังเป็น `ask_gemini` เพื่อความเข้ากันได้
  ส่วน `controllers/*` ยัง import จาก `gemini_service.py`
- ข้อมูล: `QP.xlsx`, `question_bank.json`, `knowledge_base/*.json`, `learning_logs.json`
- Dashboard ครู: Flask (`teacher_dashboard.py`, `templates/dashboard.html`)

## ไฟล์หลัก
- `main.py` บอต Discord และ state machine ของ session
  phase: PLANNING_QP → ALGORITHM_ANSWER → MONITORING_QP → ALGORITHM_ANSWER → EVALUATION_QP
- `qp_service.py` โหลด QP.xlsx (แถวหัวข้อ LG จะถูกข้าม)
- `hint_service.py` ดึงคำใบ้ตาม Question ID + ระดับ
- `student_response_service.py` ให้ AI ประเมินคำตอบ (GOOD / PARTIAL / NEEDS_IMPROVEMENT)
- `retrieval_service.py`, `intent_service.py`, `learning_goal_service.py` จับคู่คำถามกับ LG/KU

## คำสั่ง
- รันบอต: `python main.py`
- รัน dashboard: `python teacher_dashboard.py`
- ทดสอบ flow แบบออฟไลน์: `python -m unittest tests.test_learning_flow -v`
- ตรวจ QP.xlsx: `python qp_service.py`

## ข้อตกลง
- แก้โค้ดแล้วต้องรัน `tests.test_learning_flow` ให้ผ่านก่อน commit
- ห้ามแก้ `.env` และห้ามพิมพ์ค่า key ออกหน้าจอ
