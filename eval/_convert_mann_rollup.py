"""One-shot converter: Mann_Drive_QA_QC_Tracker_Rev0.xlsx → eval/ground_truth/mann_3.json.

Reads sheet "5. All Findings Rollup" and rewrites each finding into the eval
ground-truth schema. Sheet ID is the primary key (no PDF page mapping yet —
the eval matcher bridges sheet_id ↔ page via facts_per_page from the audit).

Run:
    venv\\Scripts\\python.exe eval/_convert_mann_rollup.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import openpyxl

EVAL_DIR = Path(__file__).resolve().parent
XLSX     = EVAL_DIR / "mann_qa_qc_tracker.xlsx"
OUT_JSON = EVAL_DIR / "ground_truth" / "mann_3.json"

# Severity mapping  (Excel → eval-schema severities)
SEV_MAP = {
    "Hard Stop": "critical",
    "Major":     "major",
    "Moderate":  "minor",
    "Minor":     "advisory",
}

# Category mapping  (Excel → eval-schema categories)
CAT_MAP = {
    "Drafting":            "drawing_error",
    "Notes":               "drawing_error",
    "Calculation":         "drawing_error",
    "Design":              "code",
    "Civil/Grading":       "code",
    "All-Electric/Energy": "code",
    "Tree Protection":     "code",
    "Code-CRC":            "code",
    "Code-CBC":            "code",
    "Cross-Sheet Coord":   "coordination",
    "Easements":           "code",
    "Stormwater/NPDES":    "code",
    "Jurisdictional":     "code",
    "Code-CEC":            "code",
    "Professional":        "code",
    "Code-CALGreen":       "code",
    "Vaastu":              "drawing_error",
    "Code-CMC":            "code",
    "Code-CPC":            "code",
}

SOURCE_RE = re.compile(r"^Internal QA[\s—\-]+(.+)$")

# Sheet ID → PDF page numbers (1-indexed). Provided by the user 2026-05-21
# after they identified the locations directly in the source PDF.
# Where a sheet spans multiple pages, every page is included; the matcher
# accepts a tool finding on ANY of them.
SHEET_TO_PAGES: dict[str, list[int]] = {
    "AG 0.1": [1],
    "AG 0.2": [2],
    "AG 0.3": [3],
    "AA 1.1": [5, 6, 7, 8],
    "AA 1.2": [9],
    "C-1":    [11, 12, 13],
    "Survey": [15],
    "AA 2.1": [16],
    "AA 2.2": [19, 20, 21, 22],
    "AA 2.4": [19, 20, 21, 22],  # interleaved with AA 2.2 per user mapping
}


def main() -> None:
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    rows = list(wb["5. All Findings Rollup"].iter_rows(values_only=True))

    findings_out: list[dict] = []
    skipped = 0
    for r in rows[5:]:
        if not r or not r[1]:
            continue
        n, fid, source, sev_raw, cat_raw, desc, *_ = r
        sev = SEV_MAP.get((sev_raw or "").strip())
        cat = CAT_MAP.get((cat_raw or "").strip(), "drawing_error")
        m = SOURCE_RE.match((source or "").strip())
        sheet_id = m.group(1).strip() if m else (source or "").strip()
        if not desc or not sev:
            skipped += 1
            continue
        pages = SHEET_TO_PAGES.get(sheet_id, [])
        findings_out.append({
            "id": fid,
            "sheet_id": sheet_id,
            "page": pages[0] if pages else None,
            "pages": pages,           # list — matcher accepts a hit on ANY of these
            "severity": sev,
            "category": cat,
            "description": (desc or "").strip(),
            "expected_citation": None,
            "must_catch": sev in ("critical", "major"),
        })

    payload = {
        "drawing": "mann_3.pdf",
        "jurisdiction": "Cupertino, R1-10 (state code applies; municipal items flagged separately)",
        "project_address": "10350 Mann Drive, Cupertino, CA 95014",
        "labeled_by": "Internal QA — see source spreadsheet",
        "labeled_at": "2026-05-21",
        "source_xlsx": "eval/mann_qa_qc_tracker.xlsx",
        "note": (
            "Only 10 of 38 sheets in the drawing index have been reviewed. "
            "Recall is measured against THESE 10 sheets only. AI findings on "
            "unreviewed sheets fall into a separate 'unscored' bucket."
        ),
        "reviewed_sheets": [
            "AG 0.1", "AG 0.2", "AG 0.3",
            "AA 1.1", "AA 1.2",
            "C-1", "Survey",
            "AA 2.1", "AA 2.2", "AA 2.4",
        ],
        "findings": findings_out,
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(findings_out)} findings to {OUT_JSON.relative_to(EVAL_DIR.parent)}")
    if skipped:
        print(f"Skipped {skipped} rows (missing severity or description)")


if __name__ == "__main__":
    main()
