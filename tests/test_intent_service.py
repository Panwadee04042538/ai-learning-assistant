"""
ทดสอบ intent_service.py: การ map คำถามไปยัง Learning Goal (LG)

เดิม "ทำไมต้องใช้ Decision" ไม่ถูก map ไป LG ใดเลยผ่าน intent_service
(ตกไปที่ retrieval fallback แทน เพราะคำว่า "decision" ไม่อยู่ใน pattern
ของ LG06 ทั้งที่ "loop"/"sequence"/"selection" อยู่แล้ว) และ
"ออกแบบ Algorithm จากสถานการณ์" ก็ไม่ถูก map ไป LG08 เพราะไม่มี pattern
รองรับคำว่า "จากสถานการณ์" เลย

เทสต์นี้ยืนยันว่า:
1. "ทำไมต้องใช้ Decision/Loop/Sequence" -> LG05 หรือ LG06
2. "ออกแบบ Algorithm จาก..." -> LG08

วิธีรัน (จากโฟลเดอร์หลักของโปรเจกต์):
    python -m unittest tests.test_intent_service -v
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from intent_service import detect_intent  # noqa: E402


class StructureQuestionsMapToLg05OrLg06Test(unittest.TestCase):
    """คำถามเชิงแนวคิดเกี่ยวกับโครงสร้าง (ทำไมต้องใช้ Decision/Loop/
    Sequence) ต้อง map ไป LG05 หรือ LG06 ไม่ใช่ตกไปที่อื่นหรือไม่ map เลย"""

    def _assert_lg05_or_lg06(self, question):
        result = detect_intent(question)
        self.assertIsNotNone(result, f"ควร map ได้: {question}")
        self.assertIn(
            result["lg_id"], {"LG05", "LG06"},
            f"{question} -> {result['lg_id']} (ควรเป็น LG05 หรือ LG06)",
        )

    def test_why_use_decision(self):
        for text in ["ทำไมต้องใช้ Decision", "ทำไมถึงต้องใช้ Decision"]:
            self._assert_lg05_or_lg06(text)

    def test_why_use_loop(self):
        for text in ["ทำไมต้องใช้ Loop", "ทำไมถึงต้องใช้ Loop"]:
            self._assert_lg05_or_lg06(text)

    def test_why_use_sequence(self):
        for text in ["ทำไมต้องใช้ Sequence", "ทำไมถึงต้องใช้ Sequence"]:
            self._assert_lg05_or_lg06(text)

    def test_why_use_thai_structure_terms(self):
        for text in ["ทำไมต้องใช้เงื่อนไข", "ทำไมต้องใช้ทำซ้ำ", "ทำไมต้องใช้การวนซ้ำ"]:
            self._assert_lg05_or_lg06(text)


class DesignFromScenarioMapsToLg08Test(unittest.TestCase):
    """'ออกแบบ Algorithm จาก...' ต้อง map ไป LG08 (ฝึก/ประยุกต์จาก
    สถานการณ์) ไม่ใช่ไปที่อื่นหรือไม่ map เลย"""

    def test_design_algorithm_from_scenario(self):
        for text in [
            "ออกแบบ Algorithm จากสถานการณ์",
            "ช่วยออกแบบ Algorithm จากสถานการณ์นี้หน่อย",
            "อยากออกแบบอัลกอริทึมจากสถานการณ์จริง",
        ]:
            result = detect_intent(text)
            self.assertIsNotNone(result, f"ควร map ได้: {text}")
            self.assertEqual(result["lg_id"], "LG08", text)


if __name__ == "__main__":
    unittest.main()
