"""
ตรวจสอบ QP.xlsx ผ่าน qp_service.py

เดิมไฟล์นี้เป็นสำเนาของ qp_service เวอร์ชันใหม่ (v2)
ตอนนี้ v2 ถูกย้ายไปแทนที่ qp_service.py แล้ว ไฟล์นี้จึงเหลือไว้สำหรับตรวจข้อมูล
"""

from qp_service import QPService

if __name__ == "__main__":
    service = QPService()
    report = service.validate()

    print(f"โหลดคำถาม QP ได้ {report['question_count']} ข้อ "
          f"(ข้ามแถวหัวข้อ {report['ignored_header_rows']} แถว)")

    for lg, phases in report["count_by_lg_phase"].items():
        print(f"  {lg}: {phases}")

    problems = {
        k: report[k]
        for k in ("duplicate_question_ids", "missing_lg",
                  "missing_phase", "missing_system_question")
        if report[k]
    }
    print("\n✅ ข้อมูลครบถ้วน" if not problems else f"\n⚠️ พบปัญหา: {problems}")
