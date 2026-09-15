import json

from config import QUESTION_BANK_PATH


# ==========================================
# Load Question Bank
# ==========================================


def load_question_bank():

    try:

        with open(
            QUESTION_BANK_PATH,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

            return data.get(
                "question_bank",
                []
            )

    except FileNotFoundError:

        print(
            f"❌ Question Bank not found: "
            f"{QUESTION_BANK_PATH}"
        )

        return []

    except json.JSONDecodeError as e:

        print(
            f"❌ Question Bank JSON Error: {e}"
        )

        return []


# ==========================================
# Parse Related KU
# ==========================================

def parse_related_ku(value):
    """
    Normalize related_ku into a list of KU IDs.

    Supported formats:
        KU10
        KU09, KU10, KU11
        KU08-KU11
        KU08–KU11
        KU08–KU11 (Algorithm Knowledge Scope)
    """
    if not value:
        return []

    text = str(value).strip().upper()

    # Normalize dash variants.
    text = (
        text
        .replace("–", "-")
        .replace("—", "-")
    )

    # Only the first line is relevant.
    text = text.split("\n")[0].strip()

    results = []

    # Split comma-separated entries.
    parts = [
        part.strip()
        for part in text.split(",")
        if part.strip()
    ]

    for part in parts:

        # Remove parenthetical descriptions, e.g.
        # "KU08-KU11 (Algorithm Knowledge Scope)"
        part = part.split("(")[0].strip()

        # Handle ranges such as KU08-KU11.
        if "-" in part:
            start, end = (
                item.strip()
                for item in part.split("-", 1)
            )

            start = start.split()[0]
            end = end.split()[0]

            if (
                start.startswith("KU")
                and end.startswith("KU")
                and len(start) == 4
                and len(end) == 4
                and start[2:].isdigit()
                and end[2:].isdigit()
            ):
                start_num = int(start[2:])
                end_num = int(end[2:])

                step = 1 if end_num >= start_num else -1

                for number in range(
                    start_num,
                    end_num + step,
                    step
                ):
                    ku_id = f"KU{number:02d}"

                    if ku_id not in results:
                        results.append(ku_id)

                continue

        # Handle a single KU.
        candidate = part.split()[0] if part.split() else ""

        if (
            candidate.startswith("KU")
            and len(candidate) == 4
            and candidate[2:].isdigit()
        ):
            if candidate not in results:
                results.append(candidate)

    return results


# ==========================================
# Find Questions by LG
# ==========================================

def get_questions_by_lg(lg_id):

    question_bank = load_question_bank()

    return [

        question

        for question in question_bank

        if question.get("lg_id") == lg_id

    ]


# ==========================================
# Find Questions by KU
# ==========================================

def get_questions_by_ku(ku_id):
    question_bank = load_question_bank()
    matched_questions = []

    target_ku = str(ku_id).strip().upper()

    for question in question_bank:

        question_ku = question.get(
            "related_ku",
            ""
        )

        ku_list = parse_related_ku(
            question_ku
        )

        if target_ku in ku_list:
            matched_questions.append(
                question
            )

    return matched_questions



# ==========================================
# Find Questions by LG + KU
# ==========================================

def get_questions_by_lg_and_ku(
    lg_id,
    ku_id
):
    question_bank = load_question_bank()
    matched_questions = []

    target_lg = str(lg_id).strip().upper()
    target_ku = str(ku_id).strip().upper()

    for question in question_bank:

        question_lg = str(
            question.get(
                "lg_id",
                ""
            )
        ).strip().upper()

        if question_lg != target_lg:
            continue

        question_ku = question.get(
            "related_ku",
            ""
        )

        ku_list = parse_related_ku(
            question_ku
        )

        if target_ku in ku_list:
            matched_questions.append(
                question
            )

    return matched_questions



# ==========================================
# Get Question for Learning
# ==========================================

def get_question_for_learning(
    lg_id,
    ku_id=None,
    user_input=None
):

    # --------------------------------------
    # Priority 1
    # Match LG + KU
    # --------------------------------------

    if ku_id:

        questions = get_questions_by_lg_and_ku(
            lg_id,
            ku_id
        )

    else:

        questions = get_questions_by_lg(
            lg_id
        )


    # --------------------------------------
    # No Question Found
    # --------------------------------------

    if not questions:

        print(
            "\n========== QUESTION NOT FOUND =========="
        )

        print(
            f"LG       : {lg_id}"
        )

        print(
            f"KU       : {ku_id}"
        )

        print(
            f"User Input: {user_input}"
        )

        print(
            "========================================\n"
        )

        return None


    # --------------------------------------
    # Trigger Matching
    # --------------------------------------

    if user_input:

        user_input_lower = user_input.lower()

        best_question = None
        best_score = 0


        for question in questions:

            triggers = question.get(
                "triggers",
                []
            )


            for trigger in triggers:

                if not trigger:
                    continue

                trigger_lower = trigger.lower().strip()


                # --------------------------------------
                # Exact Match
                # --------------------------------------

                if trigger_lower == user_input_lower:

                    print(
                        f"[QUESTION MATCH] "
                        f"Exact → "
                        f"{question.get('question_id')}"
                    )

                    return question


                # --------------------------------------
                # Partial Match
                # --------------------------------------

                if trigger_lower in user_input_lower:

                    score = len(trigger_lower)


                    if score > best_score:

                        best_score = score

                        best_question = question


        # --------------------------------------
        # Return Best Matched Question
        # --------------------------------------

        if best_question:

            print(
                f"[QUESTION MATCH] "
                f"Partial → "
                f"{best_question.get('question_id')} "
                f"(score={best_score})"
            )

            return best_question


    # --------------------------------------
    # Fallback
    # --------------------------------------

    fallback_question = questions[0]

    print(
        f"[QUESTION MATCH] "
        f"Fallback → "
        f"{fallback_question.get('question_id')}"
    )

    return fallback_question