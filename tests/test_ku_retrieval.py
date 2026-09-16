"""
ทดสอบการเพิ่ม KU12-14 เข้าระบบ (Backlog #12):

1. KU12/13/14 โหลดจาก knowledge_base/algorithm_v3.json ได้ถูกต้อง
2. main.get_allowed_ku_ids_for_lg() รวม KU ใหม่ในแต่ละ LG ที่เกี่ยวข้อง
   (LG05 -> KU12, LG07 -> KU13, LG08 -> KU14) โดยอ่านจาก
   knowledge_base/question_bank.json
3. keyword ของ KU12/13/14 ค้นหาเจอจริงผ่าน retrieval_service

วิธีรัน (จากโฟลเดอร์หลักของโปรเจกต์):
    python -m unittest tests.test_ku_retrieval -v
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault("TYPHOON_API_KEY", "test")
os.environ.setdefault("GEMINI_API_KEY", "test")
os.environ.setdefault("DISCORD_TOKEN", "test")

import main  # noqa: E402
from retrieval_service import RetrievalService  # noqa: E402


class KU12To14LoadTest(unittest.TestCase):
    """KU12/13/14 ต้องโหลดเข้าระบบได้ถูกต้องจาก algorithm_v3.json"""

    @classmethod
    def setUpClass(cls):
        cls.retrieval = RetrievalService()
        cls.by_id = {
            unit["ku_id"]: unit for unit in cls.retrieval.knowledge_units
        }

    def test_total_ku_count_is_14(self):
        self.assertEqual(len(self.retrieval.knowledge_units), 14)

    def test_ku12_ku13_ku14_are_loaded(self):
        for ku_id in ("KU12", "KU13", "KU14"):
            self.assertIn(ku_id, self.by_id, f"{ku_id} ต้องถูกโหลดเข้าระบบ")

    def test_ku12_schema_fields(self):
        ku = self.by_id["KU12"]

        self.assertEqual(ku["topic_id"], "2.12")
        self.assertEqual(
            ku["title"], "การตรวจสอบความถูกต้องของอัลกอริทึม"
        )
        self.assertEqual(ku["related_lg"], ["LG05"])
        self.assertEqual(ku["examples"], [])
        self.assertGreater(len(ku["concept_content"]), 0)
        self.assertIn("keywords", ku)
        self.assertIn("retrieval_phrases", ku)

    def test_ku13_schema_fields(self):
        ku = self.by_id["KU13"]

        self.assertEqual(ku["topic_id"], "2.13")
        self.assertEqual(ku["related_lg"], ["LG07"])
        self.assertEqual(ku["examples"], [])
        self.assertGreater(len(ku["concept_content"]), 0)

    def test_ku14_schema_fields(self):
        ku = self.by_id["KU14"]

        self.assertEqual(ku["topic_id"], "2.14")
        self.assertEqual(ku["related_lg"], ["LG08"])
        self.assertEqual(ku["examples"], [])
        self.assertGreater(len(ku["concept_content"]), 0)


class AllowedKuIncludesNewKuTest(unittest.TestCase):
    """get_allowed_ku_ids_for_lg ต้องรวม KU ใหม่ในแต่ละ LG ที่เกี่ยวข้อง"""

    def test_lg05_includes_ku12(self):
        allowed = main.get_allowed_ku_ids_for_lg("LG05")

        self.assertIn("KU12", allowed)
        # ต้องยังคง KU เดิม (KU08-KU11) อยู่ครบ ไม่ถูกทับ
        for ku_id in ("KU08", "KU09", "KU10", "KU11"):
            self.assertIn(ku_id, allowed)

    def test_lg07_includes_ku13(self):
        allowed = main.get_allowed_ku_ids_for_lg("LG07")

        self.assertIn("KU13", allowed)

    def test_lg08_includes_ku14(self):
        allowed = main.get_allowed_ku_ids_for_lg("LG08")

        self.assertIn("KU14", allowed)


class NewKuKeywordRetrievalTest(unittest.TestCase):
    """keyword ของ KU12/13/14 ต้องค้นหาเจอจริงผ่าน retrieval_service"""

    @classmethod
    def setUpClass(cls):
        cls.retrieval = RetrievalService()

    def _best_ku_id(self, question):
        result = self.retrieval.get_best_match(question)
        return result["unit"]["ku_id"] if result else None

    def test_trace_table_keyword_matches_ku12(self):
        self.assertEqual(
            self._best_ku_id("อยากรู้เรื่อง trace table"), "KU12"
        )
        self.assertEqual(
            self._best_ku_id("การตรวจสอบความถูกต้อง คืออะไร"), "KU12"
        )

    def test_infinite_loop_keyword_matches_ku13(self):
        self.assertEqual(
            self._best_ku_id("วนซ้ำไม่สิ้นสุด แก้ยังไง"), "KU13"
        )
        self.assertEqual(
            self._best_ku_id("debugging คืออะไร"), "KU13"
        )

    def test_situation_design_keyword_matches_ku14(self):
        self.assertEqual(
            self._best_ku_id("อยากฝึกออกแบบอัลกอริทึมจากสถานการณ์"), "KU14"
        )
        self.assertEqual(
            self._best_ku_id("Input Process Output คืออะไร"), "KU14"
        )


if __name__ == "__main__":
    unittest.main()
