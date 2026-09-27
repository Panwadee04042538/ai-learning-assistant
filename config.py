# ==========================================
# config.py
# AI Learning Assistant
#
# Shared path constants
# ==========================================

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

QUESTION_BANK_PATH = os.path.join(
    BASE_DIR,
    "knowledge_base",
    "question_bank.json"
)

# ==========================================
# Debug Mode
#
# True  : แสดงข้อมูล debug (Matched Term, Score, Match Type)
#         ในข้อความที่ส่งไป Discord
# False : ข้อความที่ส่งไป Discord จะไม่มีข้อมูล debug เหล่านี้
#         (log ใน terminal ยังคงแสดงตามปกติ ไม่เกี่ยวข้องกับค่านี้)
# ==========================================

# ตั้งผ่านตัวแปรแวดล้อม DEBUG_MODE=True/False (ค่าเริ่มต้น False)
DEBUG_MODE = os.environ.get("DEBUG_MODE", "False").strip().lower() in (
    "1", "true", "yes"
)

# ==========================================
# Typhoon API — max_tokens ต่อประเภทคำตอบ
#
# ป้องกันไม่ให้ response ถูกตัดกลางประโยค (Finish reason: length)
# ==========================================

MAX_TOKENS_EXPLANATION = 2048  # คำอธิบายเนื้อหา เช่น Grounded Knowledge, โจทย์ฝึก, AI Completion
MAX_TOKENS_FEEDBACK = 1024     # feedback/สรุปสั้น ๆ เช่น QP feedback, evaluation, reflection, summary
