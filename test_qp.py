"""
qp_service_v2.py
QP service for the AI Learning Assistant.

QP.xlsx is the source of truth.
Actual columns:
Question ID, LG ID, QP ID, Related KU,
Example User Input / Trigger, Phase, System Question,
Question Purpose, Expect Input.

The workbook contains LG header rows. Questions inherit the most recent
LG header when their own LG ID cell is blank.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import re
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_QP_FILE = BASE_DIR / "QP.xlsx"

PHASE_ALIASES = {
    "planning": "Planning", "plan": "Planning",
    "วางแผน": "Planning", "การวางแผน": "Planning",
    "monitoring": "Monitoring", "monitor": "Monitoring",
    "ตรวจสอบ": "Monitoring", "การตรวจสอบ": "Monitoring",
    "evaluation": "Evaluation", "evaluate": "Evaluation",
    "ประเมิน": "Evaluation", "การประเมิน": "Evaluation",
    "reflection": "Reflection", "สะท้อน": "Reflection",
    "สะท้อนคิด": "Reflection",
}

def _clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text

def _normalize_phase(value: Any) -> str:
    text = _clean(value)
    if not text:
        return ""
    return PHASE_ALIASES.get(text.lower(), text)

def _normalize_id(value: Any, prefix: str) -> str:
    text = _clean(value)
    if not text:
        return ""
    m = re.search(rf"\b{re.escape(prefix)}\s*0*(\d+)\b",
                  text, flags=re.IGNORECASE)
    return f"{prefix}{int(m.group(1)):02d}" if m else text

def _normalize_lg_id(value: Any) -> str:
    return _normalize_id(value, "LG")

def _find_column(columns: List[str], candidates: List[str]) -> Optional[str]:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    lowered = {c.lower(): c for c in columns}
    for candidate in candidates:
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]
    return None

class QPService:
    def __init__(self, qp_file: str | Path = DEFAULT_QP_FILE):
        self.qp_file = Path(qp_file)
        self.questions: List[Dict[str, Any]] = []
        self.columns: List[str] = []
        self.column_map: Dict[str, Optional[str]] = {}
        self.duplicate_question_ids: List[str] = []
        self.source_row_count = 0
        self.ignored_header_rows = 0
        self._load()

    def _load(self) -> None:
        if not self.qp_file.exists():
            raise FileNotFoundError(
                f"ไม่พบไฟล์ QP: {self.qp_file}\n"
                "วาง QP.xlsx ไว้ในโฟลเดอร์เดียวกับ qp_service.py"
            )

        df = pd.read_excel(self.qp_file).dropna(how="all")
        self.source_row_count = len(df)
        self.columns = [str(c).strip() for c in df.columns]

        self.column_map = {
            "question_id": _find_column(
                self.columns, ["Question ID", "Question_ID", "Q ID", "QID"]),
            "lg_id": _find_column(
                self.columns, ["LG ID", "LG_ID", "LG", "Learning Goal"]),
            "qp_id": _find_column(
                self.columns, ["QP ID", "QP_ID", "QP"]),
            "related_ku": _find_column(
                self.columns, ["Related KU", "Related_KU", "KU", "Knowledge Unit"]),
            "trigger": _find_column(
                self.columns,
                ["Example User Input / Trigger", "Example User Input/Trigger",
                 "Trigger", "Example User Input"]),
            "phase": _find_column(self.columns, ["Phase", "phase"]),
            "system_question": _find_column(
                self.columns, ["System Question", "Question", "คำถาม", "Prompt"]),
            "question_purpose": _find_column(
                self.columns, ["Question Purpose", "Purpose"]),
            "expect_input": _find_column(
                self.columns, ["Expect Input", "Expected Input", "Expect_Input"]),
        }

        required = ["question_id", "qp_id", "phase", "system_question"]
        missing = [k for k in required if not self.column_map[k]]
        if missing:
            raise ValueError(
                "QP.xlsx ขาดคอลัมน์ที่จำเป็น: "
                + ", ".join(missing)
                + f"\nคอลัมน์ที่พบ: {self.columns}"
            )

        current_lg_id = ""

        for excel_row, (_, row) in enumerate(df.iterrows(), start=2):
            raw = {str(k).strip(): v for k, v in row.to_dict().items()}

            raw_lg = _clean(raw.get(self.column_map["lg_id"], "")
                             if self.column_map["lg_id"] else "")
            raw_qid = _clean(raw.get(self.column_map["question_id"], "")
                              if self.column_map["question_id"] else "")

            # Detect LG headers anywhere in the row.
            row_text = " | ".join(_clean(v) for v in raw.values() if _clean(v))
            header_match = re.search(r"\bLG\s*0*(\d+)\b", row_text,
                                     flags=re.IGNORECASE)

            # An explicit LG ID cell or a header row updates inherited LG.
            explicit_lg = _normalize_lg_id(raw_lg)
            if explicit_lg:
                current_lg_id = explicit_lg

            question_id = _normalize_id(raw_qid, "Q")

            # Header/non-question row: ignore it as a question.
            if not question_id:
                if header_match:
                    current_lg_id = f"LG{int(header_match.group(1)):02d}"
                self.ignored_header_rows += 1
                continue

            if header_match and not explicit_lg:
                current_lg_id = f"LG{int(header_match.group(1)):02d}"

            qp_id = _normalize_id(
                raw.get(self.column_map["qp_id"], "")
                if self.column_map["qp_id"] else "", "QP")
            phase = _normalize_phase(
                raw.get(self.column_map["phase"], "")
                if self.column_map["phase"] else "")
            system_question = _clean(
                raw.get(self.column_map["system_question"], "")
                if self.column_map["system_question"] else "")

            if not system_question:
                continue

            item = {
                "question_id": question_id,
                "lg_id": explicit_lg or current_lg_id,
                "qp_id": qp_id,
                "related_ku": _clean(
                    raw.get(self.column_map["related_ku"], "")
                    if self.column_map["related_ku"] else ""),
                "trigger": _clean(
                    raw.get(self.column_map["trigger"], "")
                    if self.column_map["trigger"] else ""),
                "phase": phase,
                "system_question": system_question,
                "question_purpose": _clean(
                    raw.get(self.column_map["question_purpose"], "")
                    if self.column_map["question_purpose"] else ""),
                "expect_input": _clean(
                    raw.get(self.column_map["expect_input"], "")
                    if self.column_map["expect_input"] else ""),
                "source_row": excel_row,
            }

            # Preserve other source columns.
            for key, value in raw.items():
                if key not in item:
                    item[key] = "" if pd.isna(value) else value

            self.questions.append(item)

        self._refresh_duplicates()

    def _refresh_duplicates(self) -> None:
        counts: Dict[str, int] = {}
        for q in self.questions:
            counts[q["question_id"]] = counts.get(q["question_id"], 0) + 1
        self.duplicate_question_ids = sorted(
            qid for qid, count in counts.items() if count > 1)

    def all_questions(self) -> List[Dict[str, Any]]:
        return [dict(q) for q in self.questions]

    def get_by_question_id(self, question_id: str) -> Optional[Dict[str, Any]]:
        target = _normalize_id(question_id, "Q")
        for q in self.questions:
            if q["question_id"] == target:
                return dict(q)
        return None

    def get_by_qp_id(self, qp_id: str) -> List[Dict[str, Any]]:
        target = _normalize_id(qp_id, "QP")
        return [dict(q) for q in self.questions if q["qp_id"] == target]

    def get_by_lg(self, lg_id: str, phase: Optional[str] = None) -> List[Dict[str, Any]]:
        target_lg = _normalize_lg_id(lg_id)
        target_phase = _normalize_phase(phase) if phase else None
        return [
            dict(q) for q in self.questions
            if q["lg_id"] == target_lg
            and (target_phase is None or q["phase"] == target_phase)
        ]

    def get_by_phase(self, phase: str) -> List[Dict[str, Any]]:
        target = _normalize_phase(phase)
        return [dict(q) for q in self.questions if q["phase"] == target]

    def get_by_lg_phase(self, lg_id: str, phase: str) -> List[Dict[str, Any]]:
        return self.get_by_lg(lg_id, phase)

    def select_qp(
        self,
        lg_id: str,
        phase: str,
        question_id: Optional[str] = None,
        exclude_question_ids: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        candidates = self.get_by_lg_phase(lg_id, phase)

        if question_id:
            target = _normalize_id(question_id, "Q")
            for q in candidates:
                if q["question_id"] == target:
                    return q
            return None

        excluded = {
            _normalize_id(x, "Q")
            for x in (exclude_question_ids or [])
        }
        for q in candidates:
            if q["question_id"] not in excluded:
                return q
        return None

    def select_next_qp(
        self,
        lg_id: str,
        phase: str,
        used_question_ids: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        return self.select_qp(lg_id, phase, exclude_question_ids=used_question_ids)

    def count_by_lg_phase(self) -> Dict[str, Dict[str, int]]:
        result: Dict[str, Dict[str, int]] = {}
        for q in self.questions:
            lg = q["lg_id"] or "(no LG)"
            phase = q["phase"] or "(no Phase)"
            result.setdefault(lg, {})
            result[lg][phase] = result[lg].get(phase, 0) + 1
        return result

    def validate(self) -> Dict[str, Any]:
        return {
            "file": str(self.qp_file),
            "source_rows": self.source_row_count,
            "ignored_header_rows": self.ignored_header_rows,
            "question_count": len(self.questions),
            "duplicate_question_ids": self.duplicate_question_ids,
            "missing_lg": [q["question_id"] for q in self.questions if not q["lg_id"]],
            "missing_phase": [q["question_id"] for q in self.questions if not q["phase"]],
            "missing_system_question": [
                q["question_id"] for q in self.questions if not q["system_question"]],
            "phases": sorted({q["phase"] for q in self.questions if q["phase"]}),
            "count_by_lg_phase": self.count_by_lg_phase(),
        }


_default_service: Optional[QPService] = None

def get_qp_service(qp_file: str | Path = DEFAULT_QP_FILE) -> QPService:
    global _default_service
    requested = Path(qp_file)
    if _default_service is None or _default_service.qp_file != requested:
        _default_service = QPService(requested)
    return _default_service

def get_qp_by_question_id(question_id: str):
    return get_qp_service().get_by_question_id(question_id)

def get_qp_by_qp_id(qp_id: str):
    return get_qp_service().get_by_qp_id(qp_id)

def get_qp_by_lg(lg_id: str):
    return get_qp_service().get_by_lg(lg_id)

def get_qp_by_phase(phase: str):
    return get_qp_service().get_by_phase(phase)

def get_qp_by_lg_phase(lg_id: str, phase: str):
    return get_qp_service().get_by_lg_phase(lg_id, phase)

def select_qp(
    lg_id: str,
    phase: str,
    question_id: Optional[str] = None,
    exclude_question_ids: Optional[List[str]] = None,
):
    return get_qp_service().select_qp(
        lg_id, phase, question_id, exclude_question_ids)

if __name__ == "__main__":
    service = QPService()
    print("=" * 70)
    print("QP Service v2 Diagnostic")
    print("=" * 70)
    print(f"File: {service.qp_file}")
    print(f"Source rows: {service.source_row_count}")
    print(f"Ignored LG/header rows: {service.ignored_header_rows}")
    print(f"Questions loaded: {len(service.questions)}")
    print(f"Duplicate Question IDs: {service.duplicate_question_ids}")
    print()
    print("LG + Phase counts:")
    for lg, phases in service.count_by_lg_phase().items():
        print(f"  {lg}: {phases}")

    for phase in ("Planning", "Monitoring", "Evaluation"):
        print(f"\nExample: LG08 + {phase}")
        for q in service.get_by_lg_phase("LG08", phase):
            print(
                f"  {q['question_id']} | {q['qp_id']} | "
                f"{q['system_question']}"
            )

    print("\nValidation:")
    print(service.validate())
