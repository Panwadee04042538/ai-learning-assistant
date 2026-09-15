import json
import os
import re
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
        """
        Search Knowledge Units within the allowed scope.

        Retrieval strategy V3.1
        1) Exact phrase match
        2) Exact keyword match
        3) Phrase similarity (whole question vs retrieval phrase)
        4) Token similarity
        5) Return only results above threshold

        IMPORTANT:
        - allowed_ku_ids is a hard boundary.
        - Do not fall back to unrelated KUs when a scope is supplied.
        """

        question = (
            str(question)
            .lower()
            .strip()
        )

        if not question:
            return []

        knowledge_units = (
            self.filter_knowledge_units(
                allowed_ku_ids
            )
        )

        # ------------------------------------------
        # Helpers
        # ------------------------------------------
        def clean(text):
            text = str(text).lower().strip()
            text = re.sub(r"\\s+", " ", text)
            return text

        def phrase_similarity(a, b):
            """
            Similarity between the full question and a knowledge phrase.
            Gives natural-language questions a chance even when they do not
            contain an exact keyword.
            """
            a = clean(a)
            b = clean(b)

            if not a or not b:
                return 0.0

            # Direct containment is stronger than generic similarity.
            if b in a:
                return 1.0

            # Compare the phrase against the question and its local windows.
            best = SequenceMatcher(None, a, b).ratio()

            q_words = self.tokenize(a)
            p_words = self.tokenize(b)

            if p_words and q_words:
                p_len = len(p_words)

                # Sliding window helps phrases such as
                # "เริ่มเขียน Algorithm ยังไง" match a KU phrase
                # without rewarding unrelated words in the question.
                for size in range(
                    max(1, p_len - 1),
                    min(len(q_words), p_len + 2) + 1
                ):
                    for i in range(0, len(q_words) - size + 1):
                        window = " ".join(
                            q_words[i:i + size]
                        )
                        score = SequenceMatcher(
                            None,
                            window,
                            b
                        ).ratio()
                        best = max(best, score)

            return best

        # ------------------------------------------
        # STEP 1: Exact phrase / keyword match
        # ------------------------------------------
        exact_results = []

        for unit in knowledge_units:
            search_terms = (
                unit.get("keywords", [])
                +
                unit.get("retrieval_phrases", [])
            )

            for term in search_terms:
                term = clean(term)

                if term and term in question:
                    exact_results.append({
                        "unit": unit,
                        "score": 1.0,
                        "match_type": "Exact Match",
                        "matched_term": term
                    })
                    break

        if exact_results:
            exact_results.sort(
                key=lambda x: (
                    len(x["matched_term"]),
                    self._specificity_score(
                        x["matched_term"]
                    )
                ),
                reverse=True
            )
            return exact_results

        # ------------------------------------------
        # STEP 2: Phrase-level fuzzy match
        # ------------------------------------------
        phrase_results = []

        for unit in knowledge_units:
            search_terms = (
                unit.get("retrieval_phrases", [])
                +
                unit.get("keywords", [])
            )

            best_score = 0.0
            best_term = ""

            for term in search_terms:
                term = clean(term)

                if not term:
                    continue

                score = phrase_similarity(
                    question,
                    term
                )

                if score > best_score:
                    best_score = score
                    best_term = term

            # Higher threshold for generic single-word keywords.
            # Lower threshold is allowed for meaningful multi-word phrases.
            word_count = len(
                self.tokenize(best_term)
            )

            threshold = (
                0.62
                if word_count >= 2
                else 0.78
            )

            if best_score >= threshold:
                phrase_results.append({
                    "unit": unit,
                    "score": round(best_score, 2),
                    "match_type": "Fuzzy Match",
                    "matched_term": best_term
                })

        if phrase_results:
            phrase_results.sort(
                key=lambda x: (
                    x["score"],
                    len(
                        self.tokenize(
                            x["matched_term"]
                        )
                    ),
                    self._specificity_score(
                        x["matched_term"]
                    )
                ),
                reverse=True
            )
            return phrase_results

        return []

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