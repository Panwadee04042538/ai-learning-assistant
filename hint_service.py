import json
import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HINT_BANK_PATH = os.path.join(
    BASE_DIR,
    "knowledge_base",
    "hint_bank.json"
)


def load_hint_bank():
    """Load hint data from hint_bank.json."""
    if not os.path.exists(HINT_BANK_PATH):
        return []

    try:
        with open(
            HINT_BANK_PATH,
            "r",
            encoding="utf-8"
        ) as file:
            data = json.load(file)

        if isinstance(data, list):
            return data

        return []

    except (
        json.JSONDecodeError,
        FileNotFoundError
    ):
        return []


HINT_BANK = load_hint_bank()


def get_hint(question_id, hint_level):
    """
    Get a specific hint by Question ID and Hint Level.

    Example:
        get_hint("Q27", 1)
    """

    question_id = str(question_id).strip()

    if isinstance(hint_level, int):
        hint_level = f"Level {hint_level}"
    else:
        hint_level = str(hint_level).strip()

        if hint_level.isdigit():
            hint_level = f"Level {hint_level}"

    for hint in HINT_BANK:
        if (
            hint.get("Question ID") == question_id
            and hint.get("Hint Level") == hint_level
        ):
            return hint

    return None


def get_hints_for_question(question_id):
    """Get all progressive hints for one question."""

    question_id = str(question_id).strip()

    return [
        hint
        for hint in HINT_BANK
        if hint.get("Question ID") == question_id
    ]