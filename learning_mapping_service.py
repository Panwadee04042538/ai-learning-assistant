import json
import os
import re

from retrieval_service import RetrievalService
from learning_goal_service import LearningGoalService
from intent_service import detect_intent


class LearningMappingService:

    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))

        self.question_bank_path = os.path.join(
            self.base_dir,
            "knowledge_base",
            "question_bank.json"
        )

        self.retrieval_service = RetrievalService()
        self.learning_goal_service = LearningGoalService()

        self.question_bank = self.load_question_bank()

    # =========================================================
    # LOAD QUESTION BANK
    # =========================================================
    def load_question_bank(self):
        try:
            with open(
                self.question_bank_path,
                "r",
                encoding="utf-8"
            ) as f:
                data = json.load(f)

            # รองรับทั้ง
            # {"questions": [...]}
            # {"question_bank": [...]}
            # และ list โดยตรง
            if isinstance(data, list):
                return data

            if isinstance(data, dict):

                if isinstance(data.get("questions"), list):
                    return data["questions"]

                if isinstance(data.get("question_bank"), list):
                    return data["question_bank"]

            print("⚠️ ไม่พบรายการคำถามใน question_bank.json")
            return []

        except FileNotFoundError:
            print(
                f"❌ ไม่พบไฟล์ Question Bank: "
                f"{self.question_bank_path}"
            )
            return []

        except json.JSONDecodeError as e:
            print(
                f"❌ question_bank.json ไม่ใช่ JSON ที่ถูกต้อง: {e}"
            )
            return []

        except Exception as e:
            print(
                f"❌ เกิดข้อผิดพลาดในการโหลด Question Bank: {e}"
            )
            return []

    # =========================================================
    # PARSE RELATED KU
    # =========================================================
    def parse_related_ku(self, value):
        """
        รองรับรูปแบบ เช่น

        KU01
        KU01, KU02, KU03
        KU01–KU06
        KU01-KU06
        KU01 – KU06
        """

        if value is None:
            return []

        text = str(value).strip().upper()

        # ถ้ามีข้อความหลังบรรทัดใหม่ ให้เอาเฉพาะบรรทัดแรก
        text = text.split("\n")[0].strip()

        if not text:
            return []

        # normalize dash
        text = (
            text
            .replace("–", "-")
            .replace("—", "-")
        )

        results = []

        # แยกด้วย comma
        parts = [
            part.strip()
            for part in text.split(",")
            if part.strip()
        ]

        for part in parts:

            # ---------------------------------------------
            # กรณี KU01-KU06 (อาจมีข้อความอื่นต่อท้าย เช่น
            # "KU01-KU06 หรือ KU01 (LG02 Knowledge Scope)")
            # ---------------------------------------------
            range_match = re.search(
                r"KU(\d+)\s*-\s*KU(\d+)",
                part
            )

            if range_match:

                start_num = int(range_match.group(1))
                end_num = int(range_match.group(2))

                if start_num <= end_num:

                    for number in range(
                        start_num,
                        end_num + 1
                    ):
                        ku_id = f"KU{number:02d}"

                        if ku_id not in results:
                            results.append(ku_id)

                # ข้อความส่วนที่เหลือหลัง range
                # อาจมี KU เดี่ยวเพิ่มเติม เช่น "หรือ KU01"
                part = part[range_match.end():]

            # ---------------------------------------------
            # กรณี KU เดี่ยว (รองรับหลายรายการในข้อความเดียว)
            # ---------------------------------------------
            for ku_id in re.findall(r"KU\d+", part):

                ku_id = f"KU{int(ku_id[2:]):02d}"

                if ku_id not in results:
                    results.append(ku_id)

        return results

    # =========================================================
    # GET ALLOWED KU FOR LG
    # =========================================================
    def get_allowed_ku_for_lg(self, lg_id):
        """
        ใช้ Question Bank เป็นตัวกำหนด
        ว่า LG นี้สามารถเชื่อมกับ KU ใดได้บ้าง

        สำคัญ:
        ไม่ใช้ related_lg จาก algorithm_v3.json
        เป็นตัวตัดสินเส้นทาง LG → KU
        """

        if not lg_id:
            return []

        lg_id = str(lg_id).strip().upper()

        allowed_ku_ids = []

        for question in self.question_bank:

            question_lg = str(
                question.get("lg_id", "")
            ).strip().upper()

            if question_lg != lg_id:
                continue

            related_ku = question.get(
                "related_ku",
                ""
            )

            ku_ids = self.parse_related_ku(
                related_ku
            )

            for ku_id in ku_ids:

                if ku_id not in allowed_ku_ids:
                    allowed_ku_ids.append(ku_id)

        return allowed_ku_ids

    # =========================================================
    # GET UNIT
    # =========================================================
    def get_unit_from_result(self, knowledge_result):
        """
        ดึงข้อมูล Unit จาก Retrieval Result
        """

        if not knowledge_result:
            return None

        # รองรับทั้ง retrieval_service (คืน "unit")
        # และโครงสร้างอื่นที่อาจคืน "knowledge_unit"
        if isinstance(
            knowledge_result,
            dict
        ):

            for key in ("unit", "knowledge_unit"):

                if isinstance(
                    knowledge_result.get(key),
                    dict
                ):
                    return knowledge_result[key]

            return knowledge_result

        return None

    # =========================================================
    # DETECT LEARNING GOAL
    # =========================================================
    def detect_learning_goal(self, question):

        if not question:
            return None

        question = str(question).strip()

        if not question:
            return None

        # =====================================================
        # 1. INTENT FIRST
        # =====================================================
        intent_result = None

        try:
            intent_result = detect_intent(
                question
            )
        except Exception as e:
            print(
                f"⚠️ Intent detection error: {e}"
            )

        goal = None

        if intent_result:

            intent_lg_id = intent_result.get(
                "lg_id"
            )

            if intent_lg_id:

                try:
                    goal = (
                        self.learning_goal_service
                        .get_learning_goal_by_id(
                            intent_lg_id
                        )
                    )
                except Exception as e:
                    print(
                        f"⚠️ Learning Goal lookup error: {e}"
                    )

        # =====================================================
        # 2. ถ้าได้ LG จาก Intent
        #    ให้หา KU ที่ Question Bank อนุญาต
        # =====================================================
        allowed_ku_ids = []

        if goal:

            lg_id = goal.get("lg_id")

            allowed_ku_ids = (
                self.get_allowed_ku_for_lg(
                    lg_id
                )
            )

            print(
                f"🎯 LG: {lg_id}"
                f" | Allowed KU: {allowed_ku_ids}"
            )

        # =====================================================
        # 3. RETRIEVAL
        # =====================================================
        knowledge_result = None

        try:

            if allowed_ku_ids:

                knowledge_result = (
                    self.retrieval_service
                    .get_best_match(
                        question,
                        allowed_ku_ids=allowed_ku_ids
                    )
                )

            else:

                # ถ้าไม่สามารถกำหนด KU
                # ให้ใช้ Retrieval เดิม
                knowledge_result = (
                    self.retrieval_service
                    .get_best_match(
                        question
                    )
                )

        except Exception as e:

            print(
                f"❌ Retrieval error: {e}"
            )

        # =====================================================
        # 4. GET UNIT
        # =====================================================
        unit = self.get_unit_from_result(
            knowledge_result
        )

        # =====================================================
        # 5. ถ้า Retrieval ไม่เจอ
        #    อย่าปล่อยให้ระบบพัง
        # =====================================================
        if not unit:

            print(
                f"⚠️ ไม่พบ Knowledge Unit"
                f" | Question: {question}"
                f" | LG: "
                f"{goal.get('lg_id') if goal else None}"
                f" | Allowed KU: {allowed_ku_ids}"
            )

            # ถ้ามี LG อยู่แล้ว
            # ยังคืน LG กลับไปได้
            # เพื่อให้ Question Service
            # สามารถหา QP จาก LG ได้
            return {
                "learning_goal": goal,
                "unit": None,
                "knowledge_result": None,
                "intent_result": intent_result,
                "learning_goal_id": (
                    goal.get("lg_id")
                    if goal
                    else None
                ),
                "ku_id": None,
                "allowed_ku_ids": allowed_ku_ids
            }

        # =====================================================
        # 6. GET KU ID
        # =====================================================
        ku_id = unit.get(
            "ku_id"
        )

        # =====================================================
        # 7. ถ้าไม่มี LG จาก Intent
        #    ลองหา LG จาก Unit
        # =====================================================
        if not goal:

            related_lg = unit.get(
                "related_lg"
            )

            if related_lg:

                try:

                    goal = (
                        self.learning_goal_service
                        .get_learning_goal_by_id(
                            related_lg
                        )
                    )

                except Exception as e:

                    print(
                        f"⚠️ Learning Goal fallback error: {e}"
                    )

        # =====================================================
        # 8. RESULT
        # =====================================================
        result = {
            "learning_goal": goal,
            "unit": unit,
            "knowledge_result": knowledge_result,
            "intent_result": intent_result,
            "learning_goal_id": (
                goal.get("lg_id")
                if goal
                else None
            ),
            "ku_id": ku_id,
            "allowed_ku_ids": allowed_ku_ids
        }

        print(
            f"✅ Learning Mapping"
            f" | LG: {result['learning_goal_id']}"
            f" | KU: {ku_id}"
        )

        return result


# =============================================================
# GLOBAL SERVICE INSTANCE
# =============================================================
learning_mapping_service = LearningMappingService()


def detect_learning_goal(question):
    result = learning_mapping_service.detect_learning_goal(question)
    return (
        result.get("learning_goal"),
        result.get("unit"),
        result.get("knowledge_result"),
    )