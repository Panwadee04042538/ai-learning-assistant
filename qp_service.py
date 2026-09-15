"""
qp_service.py
------------
QP (Question Prompt) service for the AI Learning Assistant.

Source of truth:
    QP.xlsx

Responsibilities:
    - Load QP questions from Excel
    - Filter QP by Learning Goal (LG)
    - Filter QP by Phase
    - Filter QP by LG + Phase
    - Retrieve a specific QP by Q ID
    - Support the existing QP structure without inventing new questions
    - Provide deterministic selection for use by the learning session

Expected Phase values:
    Planning
    Monitoring
    Evaluation

Reflection is intentionally NOT generated here because the current QP
source does not define a Reflection phase. A future Reflection QP can be
added to the Excel source and this service will be able to retrieve it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import re

try:
    import pandas as pd
except ImportError:
    pd = None


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_QP_FILE = BASE_DIR / "QP.xlsx"

# Keep aliases centralized so main.py can use either English or Thai labels.
PHASE_ALIASES = {
    "planning": "Planning",
    "plan": "Planning",
    "วางแผน": "Planning",
    "การวางแผน": "Planning",

    "monitoring": "Monitoring",
    "monitor": "Monitoring",
    "ตรวจสอบ": "Monitoring",
    "การตรวจสอบ": "Monitoring",

    "evaluation": "Evaluation",
    "evaluate": "Evaluation",
    "ประเมิน": "Evaluation",
    "การประเมิน": "Evaluation",

    "reflection": "Reflection",
    "สะท้อน": "Reflection",
    "สะท้อนคิด": "Reflection",
}


def _clean(value: Any) -> str:
    """Convert a cell value to a normalized string."""
    if value is None:
        return ""
    return str(value).strip()


def _normalize_phase(value: Any) -> str:
    """Normalize Phase values while preserving the workbook's terminology."""
    text = _clean(value)
    if not text:
        return ""

    key = re.sub(r"\s+", " ", text).strip().lower()
    return PHASE_ALIASES.get(key, text)


def _normalize_lg(value: Any) -> str:
    """
    Normalize LG values.

    Accepts:
        LG08
        lg08
        LG08 — ฝึกออกแบบ...
        LG08 - ฝึกออกแบบ...
    """
    text = _clean(value)
    if not text:
        return ""

    match = re.search(r"\bLG\s*0*(\d+)\b", text, flags=re.IGNORECASE)
    if match:
        return f"LG{int(match.group(1)):02d}"

    return text


def _normalize_qid(value: Any) -> str:
    """Normalize Q IDs such as Q01 / q1 / Q001."""
    text = _clean(value)
    if not text:
        return ""

    match = re.search(r"\bQ\s*0*(\d+)\b", text, flags=re.IGNORECASE)
    if match:
        return f"Q{int(match.group(1)):02d}"

    return text


def _find_column(columns: List[str], candidates: List[str]) -> Optional[str]:
    """Find a workbook column using exact, then case-insensitive matching."""
    for candidate in candidates:
        if candidate in columns:
            return candidate

    lowered = {c.lower(): c for c in columns}
    for candidate in candidates:
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]

    return None


class QPService:
    """Service for retrieving QP questions from QP.xlsx."""

    def __init__(self, qp_file: str | Path = DEFAULT_QP_FILE):
        self.qp_file = Path(qp_file)
        self.questions: List[Dict[str, Any]] = []
        self.columns: List[str] = []
        self.column_map: Dict[str, Optional[str]] = {}
        self._load()

    def _load(self) -> None:
        if not self.qp_file.exists():
            raise FileNotFoundError(
                f"ไม่พบไฟล์ QP: {self.qp_file}\n"
                "กรุณาวาง QP.xlsx ไว้ในโฟลเดอร์เดียวกับ qp_service.py"
            )

        if pd is None:
            raise ImportError(
                "ต้องติดตั้ง pandas และ openpyxl ก่อนใช้งาน qp_service.py"
            )

        df = pd.read_excel(self.qp_file)
        df = df.dropna(how="all")

        self.columns = [str(c).strip() for c in df.columns]

        # The service is deliberately flexible about column names.
        self.column_map = {
            "qid": _find_column(
                self.columns,
                ["Q ID", "QID", "Question ID", "Question_ID", "ID", "Q"],
            ),
            "lg": _find_column(
                self.columns,
                ["LG", "Learning Goal", "Learning_Goal", "LearningGoal"],
            ),
            "phase": _find_column(
                self.columns,
                ["Phase", "phase"],
            ),
            "question": _find_column(
                self.columns,
                ["Question", "คำถาม", "QP", "Prompt", "Question Text", "System Question"],
            ),
            "related_ku": _find_column(
                self.columns,
                ["Related KU", "Related_KU", "KU", "Knowledge Unit"],
            ),
        }

        if not self.column_map["qid"]:
            raise ValueError(
                f"ไม่พบคอลัมน์ Q ID ใน QP.xlsx\n"
                f"คอลัมน์ที่พบ: {self.columns}"
            )

        if not self.column_map["question"]:
            raise ValueError(
                f"ไม่พบคอลัมน์คำถามใน QP.xlsx\n"
                f"คอลัมน์ที่พบ: {self.columns}"
            )

        for _, row in df.iterrows():
            raw = {str(k).strip(): v for k, v in row.to_dict().items()}

            qid = _normalize_qid(raw.get(self.column_map["qid"], ""))
            question = _clean(raw.get(self.column_map["question"], ""))

            # Ignore blank / non-question rows.
            if not qid or not question:
                continue

            lg_raw = raw.get(self.column_map["lg"], "") if self.column_map["lg"] else ""
            phase_raw = (
                raw.get(self.column_map["phase"], "")
                if self.column_map["phase"]
                else ""
            )
            ku_raw = (
                raw.get(self.column_map["related_ku"], "")
                if self.column_map["related_ku"]
                else ""
            )

            item = {
                "qid": qid,
                "lg": _normalize_lg(lg_raw),
                "lg_raw": _clean(lg_raw),
                "phase": _normalize_phase(phase_raw),
                "question": question,
                "related_ku": _clean(ku_raw),
            }

            # Keep any extra workbook columns available without making
            # downstream code depend on them.
            for key, value in raw.items():
                if key not in item:
                    item[key] = "" if value is None else value

            self.questions.append(item)

        # Stable ordering: Q01, Q02, ... Q42.
        self.questions.sort(
            key=lambda x: int(re.search(r"\d+", x["qid"]).group())
            if re.search(r"\d+", x["qid"])
            else 9999
        )

    # ------------------------------------------------------------------
    # Basic retrieval
    # ------------------------------------------------------------------

    def all_questions(self) -> List[Dict[str, Any]]:
        """Return all loaded QP questions."""
        return list(self.questions)

    def get_by_qid(self, qid: str) -> Optional[Dict[str, Any]]:
        """Return one QP by ID, e.g. Q39."""
        target = _normalize_qid(qid)

        for item in self.questions:
            if item["qid"] == target:
                return dict(item)

        return None

    # ------------------------------------------------------------------
    # LG / Phase retrieval
    # ------------------------------------------------------------------

    def get_by_lg(
        self,
        lg_id: str,
        phase: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return QP questions for an LG, optionally restricted by Phase."""
        target_lg = _normalize_lg(lg_id)
        target_phase = _normalize_phase(phase) if phase else None

        results = [
            dict(item)
            for item in self.questions
            if item["lg"] == target_lg
            and (target_phase is None or item["phase"] == target_phase)
        ]

        return results

    def get_by_phase(self, phase: str) -> List[Dict[str, Any]]:
        """Return all QP questions for a Phase."""
        target_phase = _normalize_phase(phase)

        return [
            dict(item)
            for item in self.questions
            if item["phase"] == target_phase
        ]

    def get_by_lg_phase(
        self,
        lg_id: str,
        phase: str,
    ) -> List[Dict[str, Any]]:
        """
        Main API for the AI Learning Assistant.

        Example:
            qp_service.get_by_lg_phase("LG08", "Planning")
        """
        return self.get_by_lg(lg_id, phase)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def select_qp(
        self,
        lg_id: str,
        phase: str,
        qid: Optional[str] = None,
        exclude_qids: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Select one QP deterministically.

        Priority:
            1. Explicit qid, if supplied and belongs to LG + Phase
            2. First eligible QP not in exclude_qids

        This intentionally does NOT randomly generate a question.
        The QP.xlsx remains the source of truth.
        """
        candidates = self.get_by_lg_phase(lg_id, phase)

        if qid:
            target = _normalize_qid(qid)
            for item in candidates:
                if item["qid"] == target:
                    return item
            return None

        excluded = {
            _normalize_qid(x)
            for x in (exclude_qids or [])
            if _normalize_qid(x)
        }

        for item in candidates:
            if item["qid"] not in excluded:
                return item

        return None

    def select_next_qp(
        self,
        lg_id: str,
        phase: str,
        used_qids: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Select the next unused QP for LG + Phase."""
        return self.select_qp(
            lg_id=lg_id,
            phase=phase,
            exclude_qids=used_qids,
        )

    # ------------------------------------------------------------------
    # Utility / diagnostics
    # ------------------------------------------------------------------

    def count_by_lg_phase(self) -> Dict[str, Dict[str, int]]:
        """Return a compact LG -> Phase -> count summary."""
        result: Dict[str, Dict[str, int]] = {}

        for item in self.questions:
            lg = item["lg"] or "(no LG)"
            phase = item["phase"] or "(no Phase)"

            result.setdefault(lg, {})
            result[lg][phase] = result[lg].get(phase, 0) + 1

        return result

    def validate(self) -> Dict[str, Any]:
        """
        Basic diagnostic report.

        This does not alter the workbook and does not invent missing data.
        """
        qids = [x["qid"] for x in self.questions]
        duplicate_qids = sorted(
            {qid for qid in qids if qids.count(qid) > 1}
        )

        missing_lg = [x["qid"] for x in self.questions if not x["lg"]]
        missing_phase = [x["qid"] for x in self.questions if not x["phase"]]

        return {
            "file": str(self.qp_file),
            "question_count": len(self.questions),
            "duplicate_qids": duplicate_qids,
            "missing_lg": missing_lg,
            "missing_phase": missing_phase,
            "phases": sorted(
                {x["phase"] for x in self.questions if x["phase"]}
            ),
            "count_by_lg_phase": self.count_by_lg_phase(),
        }


# ----------------------------------------------------------------------
# Module-level convenience API
# ----------------------------------------------------------------------

_default_service: Optional[QPService] = None


def get_qp_service(qp_file: str | Path = DEFAULT_QP_FILE) -> QPService:
    """Return a cached default QPService."""
    global _default_service

    requested = Path(qp_file)

    if _default_service is None or _default_service.qp_file != requested:
        _default_service = QPService(requested)

    return _default_service


def get_qp_by_qid(qid: str) -> Optional[Dict[str, Any]]:
    return get_qp_service().get_by_qid(qid)


def get_qp_by_lg(lg_id: str) -> List[Dict[str, Any]]:
    return get_qp_service().get_by_lg(lg_id)


def get_qp_by_phase(phase: str) -> List[Dict[str, Any]]:
    return get_qp_service().get_by_phase(phase)


def get_qp_by_lg_phase(
    lg_id: str,
    phase: str,
) -> List[Dict[str, Any]]:
    return get_qp_service().get_by_lg_phase(lg_id, phase)


def select_qp(
    lg_id: str,
    phase: str,
    qid: Optional[str] = None,
    exclude_qids: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    return get_qp_service().select_qp(
        lg_id=lg_id,
        phase=phase,
        qid=qid,
        exclude_qids=exclude_qids,
    )


if __name__ == "__main__":
    service = QPService()

    print("=" * 60)
    print("QP Service Diagnostic")
    print("=" * 60)
    print(f"File: {service.qp_file}")
    print(f"Questions loaded: {len(service.questions)}")
    print(f"Phases: {sorted({q['phase'] for q in service.questions})}")
    print()

    print("LG + Phase counts:")
    for lg, phases in service.count_by_lg_phase().items():
        print(f"  {lg}: {phases}")

    print()
    print("Example: LG08 + Planning")
    for q in service.get_by_lg_phase("LG08", "Planning"):
        print(f"  {q['qid']}: {q['question']}")

    print()
    print("Example: LG08 + Monitoring")
    for q in service.get_by_lg_phase("LG08", "Monitoring"):
        print(f"  {q['qid']}: {q['question']}")

    print()
    print("Validation:")
    print(service.validate())
