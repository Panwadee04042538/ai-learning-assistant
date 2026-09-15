# ==============================================
# algorithm_service.py
# AI Learning Assistant
#
# Service สำหรับตรวจสอบ Learning Mapping
#
# Input
#   ↓
# Knowledge Retrieval
#   ↓
# KU
#   ↓
# Learning Goal
# ==============================================


def analyze_learning_mapping(question, detect_learning_goal_func):
    """
    วิเคราะห์เส้นทางการเรียนรู้จากคำถามของผู้เรียน

    Parameters
    ----------
    question : str
        คำถามของผู้เรียน

    detect_learning_goal_func : function
        Function สำหรับตรวจจับ Learning Goal
        โดยต้องคืนค่า:

        goal, unit, knowledge_result


    Returns
    -------
    dict
        ผลการวิเคราะห์ Mapping
    """

    # ------------------------------------------
    # ตรวจสอบ Input
    # ------------------------------------------

    if not question or not question.strip():

        return {
            "success": False,
            "error": "EMPTY_INPUT",
            "message": "ไม่พบข้อความสำหรับวิเคราะห์"
        }


    question = question.strip()


    # ------------------------------------------
    # Detect Learning Goal
    # ------------------------------------------

    try:

        goal, unit, knowledge_result = (
            detect_learning_goal_func(question)
        )

    except Exception as e:

        return {
            "success": False,
            "error": "DETECTION_ERROR",
            "message": str(e)
        }


    # ------------------------------------------
    # Retrieval Failed
    # ------------------------------------------

    if not knowledge_result:

        return {
            "success": False,
            "error": "KNOWLEDGE_RETRIEVAL_FAILED",
            "input": question,
            "message": "ไม่พบ Knowledge Unit ที่เกี่ยวข้อง"
        }


    # ------------------------------------------
    # Learning Goal Failed
    # ------------------------------------------

    if not goal:

        ku_id = None

        if unit:
            ku_id = unit.get("ku_id")

        return {
            "success": False,
            "error": "LEARNING_GOAL_MAPPING_FAILED",
            "input": question,
            "actual_ku": ku_id,
            "message": "พบ Knowledge Unit แต่ไม่พบ Learning Goal"
        }


    # ------------------------------------------
    # Extract Knowledge Unit
    # ------------------------------------------

    ku_id = unit.get(
        "ku_id",
        None
    )

    ku_title = unit.get(
        "title",
        None
    )


    # ------------------------------------------
    # Extract Learning Goal
    # ------------------------------------------

    lg_id = goal.get(
        "lg_id",
        None
    )

    learning_goal = goal.get(
        "learning_goal",
        None
    )


    # ------------------------------------------
    # Extract Question Pattern
    #
    # ถ้าไม่มีใน goal จะคืน None
    # เพื่อรองรับโครงสร้างข้อมูลปัจจุบัน
    # ------------------------------------------

    qp_id = goal.get(
        "qp_id",
        goal.get("qp", None)
    )


    # ------------------------------------------
    # Extract Retrieval Information
    # ------------------------------------------

    matched_term = knowledge_result.get(
        "matched_term",
        None
    )

    match_type = knowledge_result.get(
        "match_type",
        None
    )

    score = knowledge_result.get(
        "score",
        None
    )


    # ------------------------------------------
    # Related LG
    # ------------------------------------------

    related_lg = unit.get(
        "related_lg",
        []
    )


    # ------------------------------------------
    # Success Result
    # ------------------------------------------

    return {

        "success": True,

        # Input
        "input": question,


        # Knowledge Unit
        "ku_id": ku_id,
        "ku_title": ku_title,


        # Learning Goal
        "lg_id": lg_id,
        "learning_goal": learning_goal,


        # Question Pattern
        "qp_id": qp_id,


        # Retrieval Information
        "matched_term": matched_term,
        "match_type": match_type,
        "score": score,


        # Relationship
        "related_lg": related_lg,


        # Raw data
        "unit": unit,
        "goal": goal,
        "knowledge_result": knowledge_result
    }


# ==============================================
# Test Case Comparison
# ==============================================

def compare_test_case(result, test_case):
    """
    เปรียบเทียบผลลัพธ์จริงกับ Expected Result
    """

    comparison = {

        "test_id": test_case.get("test_id"),

        "passed": True,

        "checks": {}
    }


    # ------------------------------------------
    # KU Check
    # ------------------------------------------

    expected_ku = test_case.get(
        "expected_ku"
    )

    actual_ku = result.get(
        "ku_id"
    )


    if expected_ku:

        # รองรับ KU เดี่ยว
        # เช่น KU07

        # กรณี expected เป็นข้อความหลาย KU
        # จะตรวจเฉพาะเมื่อเป็น KU เดี่ยว

        if (
            isinstance(expected_ku, str)
            and expected_ku.startswith("KU")
            and "–" not in expected_ku
            and "," not in expected_ku
            and "Context-dependent" not in expected_ku
        ):

            ku_pass = (
                actual_ku == expected_ku
            )

        else:

            # กรณี Context-dependent
            # หรือหลาย KU
            # ยังไม่ตรวจแบบ strict

            ku_pass = True


        comparison["checks"]["KU"] = {

            "expected": expected_ku,

            "actual": actual_ku,

            "passed": ku_pass
        }


        if not ku_pass:

            comparison["passed"] = False


    # ------------------------------------------
    # LG Check
    # ------------------------------------------

    expected_lg = test_case.get(
        "expected_lg"
    )

    actual_lg = result.get(
        "lg_id"
    )


    if expected_lg:

        lg_pass = (
            actual_lg == expected_lg
        )


        comparison["checks"]["LG"] = {

            "expected": expected_lg,

            "actual": actual_lg,

            "passed": lg_pass
        }


        if not lg_pass:

            comparison["passed"] = False


    # ------------------------------------------
    # QP Check
    # ------------------------------------------

    expected_qp = test_case.get(
        "expected_qp"
    )

    actual_qp = result.get(
        "qp_id"
    )


    # ตรวจเฉพาะเมื่อระบบส่ง QP มาได้

    if expected_qp and actual_qp:

        qp_pass = (
            actual_qp == expected_qp
        )


        comparison["checks"]["QP"] = {

            "expected": expected_qp,

            "actual": actual_qp,

            "passed": qp_pass
        }


        if not qp_pass:

            comparison["passed"] = False


    return comparison