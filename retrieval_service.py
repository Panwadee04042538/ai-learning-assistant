import json
import os
from difflib import SequenceMatcher


class RetrievalService:
    """
    Knowledge Retrieval Service
    V2: Exact Match + Fuzzy Match
    """

    def __init__(self):
        # หา path ของ algorithm.json โดยอิงจากตำแหน่งไฟล์นี้
        base_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(base_dir, "knowledge_base", "algorithm.json")

        with open(json_path, "r", encoding="utf-8") as file:
            self.data = json.load(file)

        self.knowledge_units = self.data.get("knowledge_units", [])


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

        # ตัดคำทั่วไปที่ไม่ช่วยในการค้นหา
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
            text = text.replace(word, " ")

        return text.split()


    # ==========================================
    # Search Knowledge
    # ==========================================

    def search(self, question):

        question = question.lower().strip()

        exact_results = []

        # ------------------------------------------
        # STEP 1: Exact Match
        # ------------------------------------------

        for unit in self.knowledge_units:

            search_terms = (
                unit.get("keywords", [])
                + unit.get("retrieval_phrases", [])
            )

            for term in search_terms:

                term = term.lower().strip()

                if term and term in question:

                    exact_results.append({
                        "unit": unit,
                        "score": 1.0,
                        "match_type": "Exact Match",
                        "matched_term": term
                    })

                    break

        # ถ้าเจอ Exact Match
        if exact_results:
            return exact_results


        # ------------------------------------------
        # STEP 2: Fuzzy Match
        # ------------------------------------------

        question_words = self.tokenize(question)

        fuzzy_results = []

        for unit in self.knowledge_units:

            search_terms = (
                unit.get("keywords", [])
                + unit.get("retrieval_phrases", [])
            )

            best_score = 0
            best_term = ""

            for term in search_terms:

                term = term.lower().strip()

                for word in question_words:

                    score = self.similarity(word, term)

                    if score > best_score:
                        best_score = score
                        best_term = term

            # Threshold
            if best_score >= 0.70:

                fuzzy_results.append({
                    "unit": unit,
                    "score": round(best_score, 2),
                    "match_type": "Fuzzy Match",
                    "matched_term": best_term
                })

        fuzzy_results.sort(
            key=lambda x: x["score"],
            reverse=True
        )

        return fuzzy_results


    # ==========================================
    # Get Best Result
    # ==========================================

    def get_best_match(self, question):

        results = self.search(question)

        if not results:
            return None

        return results[0]


# ==========================================
# Test Service Directly
# ==========================================

if __name__ == "__main__":

    retrieval = RetrievalService()

    print("=" * 60)
    print("🤖 Algorithm Retrieval Service V2")
    print("=" * 60)

    while True:

        question = input("\n💬 พิมพ์คำถาม (พิมพ์ exit เพื่อออก): ")

        if question.lower() == "exit":
            break

        result = retrieval.get_best_match(question)

        if result:

            unit = result["unit"]

            print("\n✅ พบข้อมูล")
            print(f"📚 KU: {unit.get('ku_id')}")
            print(f"📖 หัวข้อ: {unit.get('title')}")
            print(f"🔍 Matched Term: {result['matched_term']}")
            print(f"🎯 Match Type: {result['match_type']}")
            print(f"📊 Score: {result['score']}")

        else:
            print("\n❌ ไม่พบข้อมูล")