from hint_service import get_hint


hint = get_hint("Q27", 1)

if hint:
    print("PASS")
    print("Question:", hint["Question ID"])
    print("LG:", hint["LG ID"])
    print("QP:", hint["QP ID"])
    print("Level:", hint["Hint Level"])
    print("Hint:", hint["Hint Text"])
else:
    print("FAIL")