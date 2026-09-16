"""
ทดสอบความแม่นยำการจับคู่คำถาม (Backlog #13):

รัน test_cases.json (42 ข้อ) ผ่านเส้นทางเดียวกับ test_runner.py
(learning_mapping_service.detect_learning_goal + algorithm_service
compare_test_case) แล้วยืนยันว่า:

1. ความแม่นยำโดยรวม >= 35/42 (83%)
2. ข้อที่ยังไม่ผ่านมีเฉพาะกลุ่มที่ถูก flag ว่า "กำกวมจริง" เท่านั้น
   (ข้อความเดียวกันถูกออกแบบให้ตอบถูกได้หลาย LG/Phase พร้อมกัน หรือ
   ต้องอาศัย session state ที่ detect_learning_goal เพียงลำพังไม่มีทาง
   ทราบได้ - ดูรายละเอียดเหตุผลแต่ละข้อในคอมเมนต์ KNOWN_AMBIGUOUS_CASES)
   ถ้ามีข้อ "ใหม่" หลุดมาไม่อยู่ในลิสต์นี้ แปลว่าเกิด regression จริง

วิธีรัน (จากโฟลเดอร์หลักของโปรเจกต์):
    python -m unittest tests.test_retrieval_accuracy -v
"""

import json
import os
import sys
import unittest

# learning_mapping_service.py พิมพ์ emoji ลง stdout ตรง ๆ (เช่น "🎯 LG: ...")
# บน Windows console ถ้า stdout ยังเป็น codepage เดิม (ไม่ใช่ utf-8) จะเกิด
# UnicodeEncodeError ทันที ต้อง reconfigure ก่อน import โมดูลที่ print emoji
# (main.py และ test_runner.py ก็ทำแบบนี้เช่นกัน)
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault("TYPHOON_API_KEY", "test")
os.environ.setdefault("GEMINI_API_KEY", "test")
os.environ.setdefault("DISCORD_TOKEN", "test")

from algorithm_service import analyze_learning_mapping, compare_test_case  # noqa: E402
from learning_mapping_service import detect_learning_goal  # noqa: E402


MINIMUM_PASSING = 35
TOTAL_TEST_CASES = 42

# ทั้ง 5 ข้อนี้ยังไม่ผ่านโดยเจตนา (ห้ามแก้ด้วยการลด threshold หรือขยาย
# pattern จนกว่าครูจะตัดสินใจ เพราะข้อความจริงกำกวม/ต้องอาศัย context):
#
# - TC20 vs TC40: ข้อความ "Algorithm นี้ใช้ได้ไหม" เหมือนกันทุกตัวอักษร
#   แต่ question_bank.json ลงทะเบียนเป็น trigger ของทั้ง Q20 (LG04) และ
#   Q40 (LG08) พร้อมกัน - เป็นความขัดแย้งในข้อมูลต้นทางเอง ไม่ใช่บั๊ก
#   ของระบบจับคู่
# - TC39/TC41/TC42: คำถามขั้น Monitoring/Evaluation ของ LG08 (โหมดฝึก)
#   มีถ้อยคำคล้าย/ซ้ำกับคำถามขั้น Monitoring/Evaluation ของ LG05 และ
#   LG07 มาก (ต่างกันแค่คำเชื่อมเล็กน้อยเช่น "ที่ออกแบบ", "ที่ทำ")
#   ในระบบจริง ผู้เรียนจะไปถึงขั้นเหล่านี้ได้ก็ต่อเมื่ออยู่ใน
#   pending_learning_sessions (LG08 practice mode) อยู่แล้วเท่านั้น
#   ซึ่ง main.py ใช้ session state ตัดสิน ไม่ได้เรียก detect_learning_goal
#   ซ้ำอีกรอบ - การทดสอบนี้เรียก detect_learning_goal("เย็น ๆ")
#   โดยไม่มี session จึงเป็นข้อจำกัดของวิธีทดสอบเอง มากกว่าบั๊กของระบบ
KNOWN_AMBIGUOUS_TEST_IDS = {"TC20", "TC39", "TC40", "TC41", "TC42"}


def _load_test_cases():
    path = os.path.join(ROOT, "test_cases.json")

    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)

    return data["test_cases"]


def _run_all_cases():
    """
    รันทุก test case ผ่านเส้นทางเดียวกับ test_runner.py

    Returns
    -------
    dict {test_id: bool}  True ถ้าผ่านทั้ง KU/LG/QP check
    """

    results = {}

    for test_case in _load_test_cases():
        question = test_case.get("user_input")

        analysis = analyze_learning_mapping(
            question,
            detect_learning_goal
        )

        if not analysis.get("success"):
            results[test_case["test_id"]] = False
            continue

        comparison = compare_test_case(analysis, test_case)
        results[test_case["test_id"]] = comparison["passed"]

    return results


class RetrievalAccuracyTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.results = _run_all_cases()

    def test_total_test_case_count_is_42(self):
        self.assertEqual(len(self.results), TOTAL_TEST_CASES)

    def test_overall_accuracy_meets_minimum_threshold(self):
        passed = sum(1 for ok in self.results.values() if ok)

        self.assertGreaterEqual(
            passed,
            MINIMUM_PASSING,
            f"ความแม่นยำต้อง >= {MINIMUM_PASSING}/{TOTAL_TEST_CASES} "
            f"แต่ได้ {passed}/{TOTAL_TEST_CASES}"
        )

    def test_failures_are_limited_to_known_ambiguous_cases(self):
        """
        ถ้ามีข้อที่ fail นอกเหนือจาก KNOWN_AMBIGUOUS_TEST_IDS แปลว่า
        เกิด regression จริงที่ต้องแก้ ไม่ใช่ความกำกวมที่รู้อยู่แล้ว
        """

        failing_ids = {
            test_id
            for test_id, ok in self.results.items()
            if not ok
        }

        unexpected_failures = failing_ids - KNOWN_AMBIGUOUS_TEST_IDS

        self.assertEqual(
            unexpected_failures,
            set(),
            f"พบข้อที่ fail โดยไม่คาดคิด (นอกเหนือจากข้อที่กำกวมรู้อยู่แล้ว): "
            f"{sorted(unexpected_failures)}"
        )

    def test_known_ambiguous_cases_are_still_the_documented_set(self):
        """
        กันไม่ให้ KNOWN_AMBIGUOUS_TEST_IDS ค้างเป็นข้อมูลเท็จ - ถ้าข้อไหน
        ถูกแก้ไขจนผ่านแล้วจริง ให้เอาออกจากลิสต์ที่ต้องให้ครูตัดสินใจ
        """

        for test_id in KNOWN_AMBIGUOUS_TEST_IDS:
            self.assertIn(test_id, self.results)
            self.assertFalse(
                self.results[test_id],
                f"{test_id} ผ่านแล้ว - ควรเอาออกจาก "
                f"KNOWN_AMBIGUOUS_TEST_IDS ในเทสต์นี้"
            )


if __name__ == "__main__":
    unittest.main()
