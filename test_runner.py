# ==============================================
# test_runner.py
# AI Learning Assistant
#
# Automated Test Runner
#
# ทำหน้าที่:
# 1. โหลด Test Cases
# 2. รัน Learning Mapping Test
# 3. เปรียบเทียบ Expected / Actual
# 4. แสดงผลใน Terminal
# 5. Export ผลลัพธ์เป็น CSV
# ==============================================


import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

import json
import csv
from datetime import datetime


from algorithm_service import (
    analyze_learning_mapping,
    compare_test_case
)

from learning_mapping_service import (
    detect_learning_goal
)


# ==============================================
# CONFIG
# ==============================================

TEST_CASE_FILE = "test_cases.json"

RESULT_FILE = "test_results.csv"


# ==============================================
# LOAD TEST CASES
# ==============================================

def load_test_cases():

    try:

        with open(
            TEST_CASE_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)


        # --------------------------------------
        # รองรับ JSON หลายรูปแบบ
        # --------------------------------------

        if isinstance(data, list):

            return data


        if isinstance(data, dict):

            # กรณีมี key test_cases
            if "test_cases" in data:

                return data["test_cases"]


            # กรณีมี key tests
            if "tests" in data:

                return data["tests"]


        print("❌ ไม่พบ Test Cases ใน JSON")

        return []


    except FileNotFoundError:

        print(
            f"❌ ไม่พบไฟล์ {TEST_CASE_FILE}"
        )

        return []


    except json.JSONDecodeError as e:

        print(
            f"❌ JSON Format Error: {e}"
        )

        return []


# ==============================================
# GET QUESTION
# ==============================================

def get_question(test_case):

    """
    รองรับชื่อ field หลายแบบ
    """

    return (

        test_case.get("question")

        or test_case.get("input")

        or test_case.get("user_input")

        or ""
    )


# ==============================================
# GET ERROR TYPE
# ==============================================

def get_error_type(result):

    """
    ระบุประเภทของปัญหา
    """

    if not result:

        return "UNKNOWN_ERROR"


    if not result.get("success"):

        return result.get(
            "error",
            "SYSTEM_ERROR"
        )


    return ""


# ==============================================
# BUILD CSV ROW
# ==============================================

def build_csv_row(
    test_case,
    result,
    comparison,
    status,
    error_type="",
    error_message=""
):

    # ------------------------------------------
    # Expected
    # ------------------------------------------

    expected_ku = test_case.get(
        "expected_ku",
        ""
    )

    expected_lg = test_case.get(
        "expected_lg",
        ""
    )

    expected_qp = test_case.get(
        "expected_qp",
        ""
    )


    # ------------------------------------------
    # Actual
    # ------------------------------------------

    actual_ku = ""

    actual_lg = ""

    actual_qp = ""


    if result:

        actual_ku = result.get(
            "ku_id",
            ""
        ) or ""

        actual_lg = result.get(
            "lg_id",
            ""
        ) or ""

        actual_qp = result.get(
            "qp_id",
            ""
        ) or ""


    # ------------------------------------------
    # Check Result
    # ------------------------------------------

    ku_result = ""

    lg_result = ""

    qp_result = ""


    if comparison:

        checks = comparison.get(
            "checks",
            {}
        )


        if "KU" in checks:

            ku_result = (

                "PASS"

                if checks["KU"].get("passed")

                else "FAIL"
            )


        if "LG" in checks:

            lg_result = (

                "PASS"

                if checks["LG"].get("passed")

                else "FAIL"
            )


        if "QP" in checks:

            qp_result = (

                "PASS"

                if checks["QP"].get("passed")

                else "FAIL"
            )


    # ------------------------------------------
    # CSV Row
    # ------------------------------------------

    return {

        "Test_ID": test_case.get(
            "test_id",
            ""
        ),

        "Question": get_question(
            test_case
        ),

        # Expected
        "Expected_KU": expected_ku,
        "Expected_LG": expected_lg,
        "Expected_QP": expected_qp,

        # Actual
        "Actual_KU": actual_ku,
        "Actual_LG": actual_lg,
        "Actual_QP": actual_qp,

        # Individual Results
        "KU_Result": ku_result,
        "LG_Result": lg_result,
        "QP_Result": qp_result,

        # Final Status
        "Status": status,

        # Error
        "Error_Type": error_type,
        "Error_Message": error_message
    }


# ==============================================
# EXPORT CSV
# ==============================================

def export_csv(results):

    if not results:

        print(
            "⚠️ ไม่มีผลลัพธ์สำหรับ Export"
        )

        return


    fieldnames = [

        "Test_ID",

        "Question",

        "Expected_KU",
        "Actual_KU",
        "KU_Result",

        "Expected_LG",
        "Actual_LG",
        "LG_Result",

        "Expected_QP",
        "Actual_QP",
        "QP_Result",

        "Status",

        "Error_Type",
        "Error_Message"
    ]


    try:

        with open(
            RESULT_FILE,
            "w",
            newline="",
            encoding="utf-8-sig"
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=fieldnames
            )


            writer.writeheader()


            writer.writerows(
                results
            )


        print()

        print(
            "📁 CSV Export Success!"
        )

        print(
            f"📄 File: {RESULT_FILE}"
        )


    except Exception as e:

        print()

        print(
            "❌ CSV Export Failed"
        )

        print(
            f"Error: {type(e).__name__}: {e}"
        )


# ==============================================
# PRINT TEST RESULT
# ==============================================

def print_result(
    test_case,
    result,
    comparison,
    status,
    error_type="",
    error_message=""
):

    print()

    print(
        "=" * 55
    )


    print(
        f"🧪 {test_case.get('test_id', 'UNKNOWN')}"
    )


    print(
        f"💬 Question: {get_question(test_case)}"
    )


    print(
        "-" * 55
    )


    # ------------------------------------------
    # Expected
    # ------------------------------------------

    print("📌 EXPECTED")

    print(
        f"KU: {test_case.get('expected_ku', '-')}"
    )

    print(
        f"LG: {test_case.get('expected_lg', '-')}"
    )

    print(
        f"QP: {test_case.get('expected_qp', '-')}"
    )


    # ------------------------------------------
    # Actual
    # ------------------------------------------

    if result:

        print()

        print("📌 ACTUAL")

        print(
            f"KU: {result.get('ku_id', '-')}"
        )

        print(
            f"LG: {result.get('lg_id', '-')}"
        )

        print(
            f"QP: {result.get('qp_id', '-')}"
        )


    # ------------------------------------------
    # Status
    # ------------------------------------------

    print()

    if status == "PASS":

        print("✅ RESULT: PASS")


    elif status == "FAIL":

        print("❌ RESULT: FAIL")


    else:

        print("⚠️ RESULT: SYSTEM ERROR")

        print(
            f"Error Type: {error_type}"
        )

        print(
            f"Error Message: {error_message}"
        )


    print(
        "=" * 55
    )


# ==============================================
# RUN TESTS
# ==============================================

def run_tests():

    print()

    print(
        "=" * 55
    )

    print(
        "🚀 AI LEARNING ASSISTANT TEST RUNNER"
    )

    print(
        "=" * 55
    )


    # ------------------------------------------
    # Load Test Cases
    # ------------------------------------------

    test_cases = load_test_cases()


    if not test_cases:

        return


    print()

    print(
        f"📋 Total Test Cases: {len(test_cases)}"
    )


    # ------------------------------------------
    # Statistics
    # ------------------------------------------

    total_tests = len(test_cases)

    passed = 0

    failed = 0

    system_errors = 0


    # ------------------------------------------
    # CSV Results
    # ------------------------------------------

    csv_results = []


    # ==========================================
    # RUN EACH TEST
    # ==========================================

    for test_case in test_cases:


        question = get_question(
            test_case
        )


        # --------------------------------------
        # Empty Question
        # --------------------------------------

        if not question:

            system_errors += 1


            status = "SYSTEM_ERROR"

            error_type = "EMPTY_QUESTION"

            error_message = (
                "ไม่พบคำถามใน Test Case"
            )


            csv_results.append(

                build_csv_row(
                    test_case=test_case,
                    result=None,
                    comparison=None,
                    status=status,
                    error_type=error_type,
                    error_message=error_message
                )
            )


            print_result(
                test_case,
                None,
                None,
                status,
                error_type,
                error_message
            )


            continue


        # ======================================
        # ANALYZE LEARNING MAPPING
        # ======================================

        try:

            result = analyze_learning_mapping(

                question,

                detect_learning_goal
            )


        except Exception as e:

            system_errors += 1


            status = "SYSTEM_ERROR"

            error_type = type(e).__name__

            error_message = str(e)


            csv_results.append(

                build_csv_row(
                    test_case=test_case,
                    result=None,
                    comparison=None,
                    status=status,
                    error_type=error_type,
                    error_message=error_message
                )
            )


            print_result(
                test_case,
                None,
                None,
                status,
                error_type,
                error_message
            )


            continue


        # ======================================
        # SYSTEM ERROR FROM SERVICE
        # ======================================

        if not result.get("success"):


            system_errors += 1


            status = "SYSTEM_ERROR"

            error_type = result.get(
                "error",
                "SYSTEM_ERROR"
            )

            error_message = result.get(
                "message",
                ""
            )


            csv_results.append(

                build_csv_row(
                    test_case=test_case,
                    result=result,
                    comparison=None,
                    status=status,
                    error_type=error_type,
                    error_message=error_message
                )
            )


            print_result(
                test_case,
                result,
                None,
                status,
                error_type,
                error_message
            )


            continue


        # ======================================
        # COMPARE TEST CASE
        # ======================================

        comparison = compare_test_case(
            result,
            test_case
        )


        # --------------------------------------
        # PASS / FAIL
        # --------------------------------------

        if comparison.get("passed"):

            passed += 1

            status = "PASS"

        else:

            failed += 1

            status = "FAIL"


        # --------------------------------------
        # Add CSV Result
        # --------------------------------------

        csv_results.append(

            build_csv_row(
                test_case=test_case,
                result=result,
                comparison=comparison,
                status=status
            )
        )


        # --------------------------------------
        # Print Result
        # --------------------------------------

        print_result(
            test_case,
            result,
            comparison,
            status
        )


    # ==========================================
    # EXPORT CSV
    # ==========================================

    export_csv(
        csv_results
    )


    # ==========================================
    # FINAL SUMMARY
    # ==========================================

    print()

    print(
        "=" * 55
    )

    print(
        "📊 FINAL TEST SUMMARY"
    )

    print(
        "=" * 55
    )

    print()

    print(
        f"Total Tests : {total_tests}"
    )

    print(
        f"Passed      : {passed} ✅"
    )

    print(
        f"Failed      : {failed} ❌"
    )

    print(
        f"System Error: {system_errors} ⚠️"
    )


    # ------------------------------------------
    # Success Rate
    # ------------------------------------------

    if total_tests > 0:

        success_rate = (

            passed / total_tests
        ) * 100

    else:

        success_rate = 0


    print()

    print(
        f"Success Rate: {success_rate:.2f}%"
    )


    print()

    print(
        "=" * 55
    )

    print(
        "🏁 TEST COMPLETED"
    )

    print(
        "=" * 55
    )


# ==============================================
# MAIN
# ==============================================

if __name__ == "__main__":

    run_tests()