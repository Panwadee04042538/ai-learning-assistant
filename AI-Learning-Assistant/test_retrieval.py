import json
from difflib import SequenceMatcher


# =========================
# โหลด Knowledge Base
# =========================

with open("knowledge_base/algorithm.json", "r", encoding="utf-8") as file:
    data = json.load(file)


# =========================
# ฟังก์ชันวัดความคล้าย
# =========================

def similarity(a, b):
    return SequenceMatcher(
        None,
        a.lower(),
        b.lower()
    ).ratio()


# =========================
# แยกคำจากคำถาม
# =========================

def tokenize(text):

    # แทนที่เครื่องหมายต่าง ๆ ด้วยช่องว่าง
    for char in ["?", "!", ",", ".", "คือ", "อะไร", "ครับ", "ค่ะ"]:
        text = text.replace(char, " ")

    return text.split()


# =========================
# ค้นหา Knowledge
# Exact + Smart Fuzzy
# =========================

def search_knowledge(question):

    question = question.lower().strip()

    results = []

    # --------------------------------
    # STEP 1: Exact Phrase Matching
    # --------------------------------

    for unit in data["knowledge_units"]:

        search_terms = (
            unit.get("keywords", [])
            + unit.get("retrieval_phrases", [])
        )

        for term in search_terms:

            term = term.lower().strip()

            if term in question:

                results.append({
                    "unit": unit,
                    "score": 1.0,
                    "match_type": "Exact Match",
                    "matched_term": term
                })

                break

    # ถ้าเจอ Exact Match แล้ว
    if results:

        results.sort(
            key=lambda x: x["score"],
            reverse=True
        )

        return results


    # --------------------------------
    # STEP 2: Fuzzy Matching
    # --------------------------------

    question_words = tokenize(question)

    for unit in data["knowledge_units"]:

        search_terms = (
            unit.get("keywords", [])
            + unit.get("retrieval_phrases", [])
        )

        best_score = 0
        best_term = ""

        for term in search_terms:

            term = term.lower().strip()

            # Fuzzy เทียบทีละคำ
            for word in question_words:

                score = similarity(word, term)

                if score > best_score:

                    best_score = score
                    best_term = term

        # Threshold สูงขึ้น
        if best_score >= 0.70:

            results.append({
                "unit": unit,
                "score": best_score,
                "match_type": "Fuzzy Match",
                "matched_term": best_term
            })


    # เรียงคะแนน
    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return results


# =========================
# แสดงผล
# =========================

def show_result(results):

    if not results:

        print("\n❌ ไม่พบข้อมูลที่เกี่ยวข้อง")
        return


    best_result = results[0]

    unit = best_result["unit"]
    score = best_result["score"]

    print("\n" + "=" * 60)

    print("✅ พบข้อมูลที่เกี่ยวข้อง")

    print("=" * 60)

    print(f'\n📚 หัวข้อ: {unit["title"]}')

    print(f'🔍 Matched Term: {best_result["matched_term"]}')

    print(f'🎯 Match Type: {best_result["match_type"]}')

    print(f'📊 Match Score: {score:.2f}')

    print("\n📖 เนื้อหา:")

    print("-" * 60)

    for content in unit.get("concept_content", []):

        print(content["text"])

    print("\n" + "=" * 60)


# =========================
# เริ่มโปรแกรม
# =========================

print("=" * 60)
print("🤖 Algorithm Knowledge Retrieval V2")
print("=" * 60)

question = input("\n💬 พิมพ์คำถาม: ")

results = search_knowledge(question)

show_result(results)