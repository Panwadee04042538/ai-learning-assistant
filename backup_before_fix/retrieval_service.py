import json
import os
from difflib import SequenceMatcher


class RetrievalService:
    """
    Knowledge Retrieval Service

    V3:
    - Exact Match
    - Specificity Priority
    - Fuzzy Match
    - Optional KU Filtering
    """

    def __init__(self):

        base_dir = os.path.dirname(
            os.path.abspath(__file__)
        )

        json_path = os.path.join(
            base_dir,
            "knowledge_base",
            "algorithm_v3.json"
        )

        with open(
            json_path,
            "r",
            encoding="utf-8"
        ) as file:

            self.data = json.load(file)

        self.knowledge_units = self.data.get(
            "knowledge_units",
            []
        )

    # ==========================================
    # Similarity
    # ==========================================

    @staticmethod
    def similarity(a, b):

        return SequenceMatcher(
            None,
            a.lower(),
            b.lower()
        ).ratio()

    # ==========================================
    # Tokenize
    # ==========================================

    @staticmethod
    def tokenize(text):

        text = text.lower()

        stop_words = [
            "คืออะไร",
            "คือ",
            "อะไร",
            "ครับ",
            "ค่ะ",
            "คะ",
            "หน่อย",
            "?",
            "!",
            ",",
            "."
        ]

        for word in stop_words:

            text = text.replace(
                word,
                " "
            )

        return text.split()

    # ==========================================
    # Normalize KU IDs
    # ==========================================

    @staticmethod
    def normalize_ku_ids(allowed_ku_ids):

        if not allowed_ku_ids:
            return None

        result = []

        for ku_id in allowed_ku_ids:

            if ku_id is None:
                continue

            ku_id = str(
                ku_id
            ).strip().upper()

            if (
                ku_id
                and ku_id not in result
            ):

                result.append(
                    ku_id
                )

        return result

    # ==========================================
    # Filter Knowledge Units
    # ==========================================

    def filter_knowledge_units(
        self,
        allowed_ku_ids=None
    ):

        allowed_ku_ids = (
            self.normalize_ku_ids(
                allowed_ku_ids
            )
        )

        # ไม่มี filter → ใช้ทั้งหมด
        if not allowed_ku_ids:

            return self.knowledge_units

        return [
            unit
            for unit in self.knowledge_units
            if str(
                unit.get(
                    "ku_id",
                    ""
                )
            ).strip().upper()
            in allowed_ku_ids
        ]

    # ==========================================
    # Search Knowledge
    # ==========================================

    def search(
        self,
        question,
        allowed_ku_ids=None
    ):

        question = (
            question
            .lower()
            .strip()
        )

        # --------------------------------------
        # เลือก Knowledge Units ที่ใช้ค้น
        # --------------------------------------

        knowledge_units = (
            self.filter_knowledge_units(
                allowed_ku_ids
            )
        )

        exact_results = []

        # ------------------------------------------
        # STEP 1: Exact Match
        # ------------------------------------------

        for unit in knowledge_units:

            search_terms = (
                unit.get(
                    "keywords",
                    []
                )
                +
                unit.get(
                    "retrieval_phrases",
                    []
                )
            )

            for term in search_terms:

                term = (
                    str(term)
                    .lower()
                    .strip()
                )

                if (
                    term
                    and term in question
                ):

                    exact_results.append({

                        "unit": unit,

                        "score": 1.0,

                        "match_type":
                            "Exact Match",

                        "matched_term":
                            term
                    })

                    break

        # ------------------------------------------
        # STEP 1.1
        # Specificity Priority
        # ------------------------------------------

        if exact_results:

            exact_results.sort(

                key=lambda x: (

                    len(
                        x["matched_term"]
                    ),

                    self._specificity_score(
                        x["matched_term"]
                    )
                ),

                reverse=True
            )

            return exact_results

        # ------------------------------------------
        # STEP 2: Fuzzy Match
        # ------------------------------------------

        question_words = (
            self.tokenize(
                question
            )
        )

        fuzzy_results = []

        for unit in knowledge_units:

            search_terms = (
                unit.get(
                    "keywords",
                    []
                )
                +
                unit.get(
                    "retrieval_phrases",
                    []
                )
            )

            best_score = 0

            best_term = ""

            for term in search_terms:

                term = (
                    str(term)
                    .lower()
                    .strip()
                )

                for word in question_words:

                    score = self.similarity(
                        word,
                        term
                    )

                    if score > best_score:

                        best_score = score

                        best_term = term

            # ----------------------------------
            # Threshold
            # ----------------------------------

            if best_score >= 0.70:

                fuzzy_results.append({

                    "unit": unit,

                    "score": round(
                        best_score,
                        2
                    ),

                    "match_type":
                        "Fuzzy Match",

                    "matched_term":
                        best_term
                })

        fuzzy_results.sort(

            key=lambda x: x["score"],

            reverse=True
        )

        return fuzzy_results

    # ==========================================
    # Specificity Score
    # ==========================================

    @staticmethod
    def _specificity_score(term):

        term = (
            term
            .lower()
            .strip()
        )

        specific_terms = {

            "loop": 100,

            "selection": 100,

            "sequence": 100,

            "if": 100,

            "ทำซ้ำ": 100,

            "วนซ้ำ": 100,

            "เงื่อนไข": 100
        }

        return specific_terms.get(
            term,
            0
        )

    # ==========================================
    # Get Best Result
    # ==========================================

    def get_best_match(
        self,
        question,
        allowed_ku_ids=None
    ):

        results = self.search(

            question,

            allowed_ku_ids=
                allowed_ku_ids
        )

        if not results:

            print(
                "\n========== RETRIEVAL =========="
            )

            print(
                f"Question: {question}"
            )

            print(
                f"Allowed KU: "
                f"{allowed_ku_ids}"
            )

            print(
                "Result: NOT FOUND"
            )

            print(
                "===============================\n"
            )

            return None

        # --------------------------------------
        # Best Result
        # --------------------------------------

        best_result = results[0]

        unit = best_result["unit"]

        print(
            "\n========== RETRIEVAL RESULT =========="
        )

        print(
            f"Question: {question}"
        )

        print(
            f"Allowed KU: {allowed_ku_ids}"
        )

        print(
            f"KU: {unit.get('ku_id')}"
        )

        print(
            f"Matched Term: "
            f"{best_result.get('matched_term')}"
        )

        print(
            f"Match Type: "
            f"{best_result.get('match_type')}"
        )

        print(
            f"Score: "
            f"{best_result.get('score')}"
        )

        print(
            "=======================================\n"
        )

        # สำคัญมาก:
        # คืนค่าเป็น wrapper แบบเดิม
        return best_result


# ==========================================
# Test Service Directly
# ==========================================

if __name__ == "__main__":

    retrieval = RetrievalService()

    print("=" * 60)

    print(
        "🤖 Algorithm Retrieval Service V3"
    )

    print("=" * 60)

    while True:

        question = input(
            "\n💬 พิมพ์คำถาม "
            "(พิมพ์ exit เพื่อออก): "
        )

        if question.lower() == "exit":

            break

        result = (
            retrieval.get_best_match(
                question
            )
        )

        if result:

            unit = result["unit"]

            print(
                "\n✅ พบข้อมูล"
            )

            print(
                f"📚 KU: "
                f"{unit.get('ku_id')}"
            )

            print(
                f"📖 หัวข้อ: "
                f"{unit.get('title')}"
            )

            print(
                f"🔍 Matched Term: "
                f"{result['matched_term']}"
            )

            print(
                f"🎯 Match Type: "
                f"{result['match_type']}"
            )

            print(
                f"📊 Score: "
                f"{result['score']}"
            )

        else:

            print(
                "\n❌ ไม่พบข้อมูล"
            )