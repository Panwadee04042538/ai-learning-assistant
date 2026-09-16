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
# True  : แสดงข้อมูล debug (Matched Term, Score, Match Type,
#         Test Case Mapping Success) ในข้อความที่ส่งไป Discord
# False : ข้อความที่ส่งไป Discord จะไม่มีข้อมูล debug เหล่านี้
#         (log ใน terminal ยังคงแสดงตามปกติ ไม่เกี่ยวข้องกับค่านี้)
# ==========================================

DEBUG_MODE = False
