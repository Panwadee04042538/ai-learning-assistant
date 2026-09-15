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
