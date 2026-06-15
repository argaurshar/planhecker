"""Text-extraction pre-pass for PlanCheck.

Reads native PDF text via PyMuPDF (fitz) and runs a small set of high-precision
rules over the extracted text. Findings emitted here include the LITERAL string
that triggered the match (`evidence_quote`), so they cannot hallucinate values —
the worst they can do is miss something the rule didn't anticipate.

This pass runs BEFORE the AI vision pass. Most findings here cost zero API calls
and complete in <1 second per PDF.

When to use this pass:
- Cover sheet / general-notes content (rich native text)
- Floor-plan annotation blocks (notes, schedules, calculations)
- Anywhere the architect typed text that the PDF preserves as text

When NOT to use this pass:
- Title-block sheet IDs (often flattened to graphics in CAD exports)
- Dimension callouts on elevations / sections (the VALUES are usually graphics)
- Civil sheets exported as flattened-to-paths PDFs (0 chars of text on most)

The two passes are complementary, not redundant: text-pass for what's in the
PDF as text; vision-pass for what's in the PDF as graphics.
"""

from __future__ import annotations

import io
import re
from typing import Callable

import fitz  # PyMuPDF


# ─────────────────────────────────────────────────────────────────────────────
# Page extraction
# ─────────────────────────────────────────────────────────────────────────────

_SHEET_ID_PATTERNS = [
    r"\b(AG\s*\d+\.\d+)\b",
    r"\b(AA\s*\d+\.\d+)\b",
    r"\b(A3D\s*\d+\.\d+)\b",
    r"\b(AS\s*\d+\.\d+)\b",
    r"\b(PL\s*\d+\.\d+)\b",
    r"\b(MEP\s*\d+\.\d+)\b",
    r"\b(ELEC\s*\d+\.\d+)\b",
    r"\b(HV[-/]?PL\s*\d+\.\d+)\b",
    r"\b(C-\d+)\b",
    r"\b(S-\d+\.?\d*)\b",
]


def _guess_sheet_id(text: str) -> str | None:
    for pat in _SHEET_ID_PATTERNS:
        m = re.search(pat, text)
        if m:
            return re.sub(r"\s+", " ", m.group(1)).strip()
    return None


def extract_pages(pdf_bytes: bytes) -> list[dict]:
    """Return a list of {page_number, text, sheet_id, text_upper} for every page.

    text_upper is the uppercase version for case-insensitive scanning.
    sheet_id is None if no recognisable sheet ID appears in the text.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages: list[dict] = []
    try:
        for i in range(len(doc)):
            text = doc[i].get_text("text") or ""
            pages.append({
                "page_number": i + 1,
                "text": text,
                "text_upper": text.upper(),
                "sheet_id": _guess_sheet_id(text),
            })
    finally:
        doc.close()
    return pages


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _context(text: str, idx: int, before: int = 40, after: int = 60) -> str:
    """Pull a window of text around a match position, collapsed to one line."""
    start = max(0, idx - before)
    end = min(len(text), idx + after)
    return re.sub(r"\s+", " ", text[start:end]).strip()


def _make_finding(
    *,
    page_number: int | str,
    severity: str,
    category: str,
    description: str,
    evidence: str,
    evidence_quote: str,
    recommendation: str,
    rule_id: str,
    pages_involved: list[int] | None = None,
    sheets_involved: list[str] | None = None,
) -> dict:
    out = {
        "severity": severity,
        "category": category,
        "description": description,
        "evidence": evidence,
        "evidence_quote": evidence_quote,
        "recommendation": recommendation,
        "region": "full-sheet",
        "page_number": page_number,
        "rule_id": rule_id,
        "source": "text_extraction",
    }
    if pages_involved is not None:
        out["pages_involved"] = pages_involved
    if sheets_involved is not None:
        out["sheets_involved"] = sheets_involved
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Rules
# ─────────────────────────────────────────────────────────────────────────────

def rule_preliminary_titleblock(pages: list[dict]) -> list[dict]:
    """Flag any sheet where the revision label looks pre-permit.

    Refined to require the bad label NOT be in an exclusion context (a few
    common phrases where these words legitimately appear without indicating
    the title block is preliminary).
    """
    findings = []
    bad_labels = [
        "PRELIMINARY",
        "WORKING LAYOUT",
        "NOT FOR CONSTRUCTION",
        "NOT FINAL",
        "DD SET",
    ]
    # Phrases where bad_labels can legitimately appear (not in title block):
    # - "PRELIMINARY DESIGN GUIDANCE" — product-spec disclaimer
    # - "ARE PRELIMINARY AND SHALL NOT" — note about sprinklers/equipment being preliminary
    # - "DESIGN DEVELOPMENT FOR:" — sometimes a date-label preceding the actual revision
    exclusion_substrings = [
        "PRELIMINARY DESIGN GUIDANCE",
        "PRELIMINARY AND SHALL NOT",
        "PRELIMINARY DESIGN ONLY",
        "ARE PRELIMINARY",
    ]
    for p in pages:
        text_u = p["text_upper"]
        for label in bad_labels:
            idx = text_u.find(label)
            if idx == -1:
                continue
            # Check exclusion context — if the matched window contains any
            # exclusion substring, skip this hit.
            window = text_u[max(0, idx - 30): idx + len(label) + 30]
            if any(excl in window for excl in exclusion_substrings):
                continue
            # Additional filter: if "ISSUED FOR PERMIT" appears in the SAME page
            # AND within 80 chars of the bad-label match, this is likely a
            # date-label confusion (e.g. "DESIGN DEVELOPMENT FOR: 21-05-2026 ISSUED FOR PERMIT").
            # Drop the bad-label match in this case.
            window_wide = text_u[max(0, idx - 100): idx + len(label) + 100]
            if "ISSUED FOR PERMIT" in window_wide:
                continue
            quote = _context(p["text"], idx)
            findings.append(_make_finding(
                page_number=p["page_number"],
                severity="critical",
                category="drawing_error",
                description=f'Revision/title block contains "{label}" — sheet not appropriate for permit submittal',
                evidence=f"Page {p['page_number']}: {quote!r}",
                evidence_quote=label,
                recommendation='Update the revision block to "ISSUED FOR PERMIT" or AHJ-equivalent label before submittal.',
                rule_id="TEXT-PRELIMINARY",
            ))
            break  # one finding per page is enough
    return findings


def rule_crawlspace_ventilation_formula(pages: list[dict]) -> list[dict]:
    """Catch the specific wrong-formula crawlspace ventilation note.

    CRC R408.1 requires 1 sq ft of net free area per 150 sq ft of underfloor area.
    A common drafting error states "1 square inch per 1 square foot" which is
    150x over-stated. Easy to grep for.
    """
    findings = []
    pattern = re.compile(
        r"1\s*(SQUARE INCH|SQ\.?\s*IN(?:CH)?|SI)\s+(?:FOR\s+)?EVERY\s+1\s*(SQUARE FOOT|SQ\.?\s*FT|SF)",
        re.IGNORECASE,
    )
    for p in pages:
        m = pattern.search(p["text"])
        if not m:
            continue
        quote = _context(p["text"], m.start(), before=20, after=60)
        findings.append(_make_finding(
            page_number=p["page_number"],
            severity="major",
            category="code",
            description="Crawlspace ventilation formula stated as 1 SI per 1 SF — wrong; CRC R408.1 requires 1 sq ft of net free area per 150 sq ft of underfloor area",
            evidence=f"Page {p['page_number']}: {quote!r}",
            evidence_quote=m.group(0),
            recommendation="Correct the crawlspace ventilation formula to CRC R408.1 (1 sq ft NFA per 150 sq ft underfloor).",
            rule_id="TEXT-CRAWLSPACE-VENT",
        ))
    return findings


def rule_wrong_city_template_text(pages: list[dict]) -> list[dict]:
    """Flag template-leftover references to a DIFFERENT city than the project's.

    Mann Drive is Cupertino. The drawing set has leftover Sunnyvale references
    in multiple notes. This rule lists common Bay Area cities and flags any
    that aren't the project's jurisdiction. Conservative: only flags
    well-known city names appearing in note-block contexts (not in addresses
    where they might legitimately appear).
    """
    findings = []
    # For now we hardcode "the project is Cupertino" — when the audit ships in
    # production, this should read the selected jurisdiction at runtime.
    target_city = "CUPERTINO"
    wrong_cities = [
        "SUNNYVALE",
        "MOUNTAIN VIEW",
        "PALO ALTO",
        "SAN JOSE",
        "SARATOGA",
        "LOS ALTOS",
        "MENLO PARK",
    ]
    # Phrases where a city name legitimately appears without indicating template leftover —
    # e.g. utility companies serving multiple cities, geographic context refs.
    utility_exclusions = {
        "SAN JOSE": [
            "SAN JOSE WATER COMPANY",
            "SAN JOSE WATER",
            "SAN JOSE/SANTA CLARA",  # regional treatment plant
        ],
        "PALO ALTO": ["PALO ALTO MEDICAL"],
        "MOUNTAIN VIEW": ["MOUNTAIN VIEW WHISMAN", "MOUNTAIN VIEW SCHOOL"],
    }
    for p in pages:
        text_u = p["text_upper"]
        for city in wrong_cities:
            idx = text_u.find(city)
            if idx == -1:
                continue
            window = text_u[max(0, idx - 5): idx + len(city) + 50]
            if any(excl in window for excl in utility_exclusions.get(city, [])):
                continue
            quote = _context(p["text"], idx)
            findings.append(_make_finding(
                page_number=p["page_number"],
                severity="critical",
                category="drawing_error",
                description=f'Wrong-jurisdiction template text: "{city}" referenced on a {target_city.title()} project',
                evidence=f"Page {p['page_number']}: {quote!r}",
                evidence_quote=city,
                recommendation=f"Strip {city.title()} references; ensure all jurisdiction-specific text matches the actual project jurisdiction ({target_city.title()}).",
                rule_id=f"TEXT-WRONG-CITY-{city.replace(' ', '_')}",
            ))
    return findings


def rule_ai_template_artifacts(pages: list[dict]) -> list[dict]:
    """Catch obvious AI-tooling or template artifacts left on the sheet.

    Patterns like "CHANGES AND NOTES" (a common AI-design-tool editing block),
    "POLYLINE" (CAD draftin word that shouldn't appear on a permit sheet),
    "COMES FROM FAX", "[FILL IN]" placeholders, etc.
    """
    findings = []
    artifact_patterns = [
        ("CHANGES AND NOTES", "AI editing block left on sheet"),
        ("COMES FROM FAX", "Template placeholder text"),
        ("POLYLINE", 'CAD term "POLYLINE" should not appear on a permit sheet as text'),
        ("FILL IN HERE", "Placeholder text"),
        ("[INSERT", "Placeholder text"),
        ("[FILL", "Placeholder text"),
        ("TBD - PENDING", 'Sheet has unresolved "TBD - PENDING" text'),
    ]
    for p in pages:
        for marker, desc in artifact_patterns:
            idx = p["text_upper"].find(marker)
            if idx == -1:
                continue
            quote = _context(p["text"], idx)
            findings.append(_make_finding(
                page_number=p["page_number"],
                severity="major",
                category="drawing_error",
                description=f"{desc} (literal text: {marker!r})",
                evidence=f"Page {p['page_number']}: {quote!r}",
                evidence_quote=marker,
                recommendation="Strip the artifact text from the sheet before permit submittal.",
                rule_id=f"TEXT-ARTIFACT-{marker.replace(' ', '_').replace('[', '').strip('-')}",
            ))
    return findings


def rule_outdated_standards(pages: list[dict]) -> list[dict]:
    """Flag references to known-outdated editions of common standards."""
    findings = []
    outdated = [
        ("ACCA MANUAL J-2004", "ACCA Manual J 8th Ed 2016 is current"),
        ("ACCA MANUAL J 2004", "ACCA Manual J 8th Ed 2016 is current"),
        ("MANUAL J-2004", "ACCA Manual J 8th Ed 2016 is current"),
        ("ACCA MANUAL D-2009", "ACCA Manual D 4th Ed 2022 is current"),
        ("ACCA MANUAL D 2009", "ACCA Manual D 4th Ed 2022 is current"),
        ("MANUAL D-2009", "ACCA Manual D 4th Ed 2022 is current"),
        ("ACCA MANUAL S-2004", "ACCA Manual S 2nd Ed 2013 is current"),
        ("ACCA MANUAL S 2004", "ACCA Manual S 2nd Ed 2013 is current"),
        ("MANUAL S-2004", "ACCA Manual S 2nd Ed 2013 is current"),
        ("2006 CA MUTCD", "2023 CA MUTCD is current"),
        ("2006 CALIFORNIA MUTCD", "2023 CA MUTCD is current"),
        ("CALIFORNIA MUTCD 2006", "2023 CA MUTCD is current"),
    ]
    for p in pages:
        for marker, correction in outdated:
            idx = p["text_upper"].find(marker)
            if idx == -1:
                continue
            quote = _context(p["text"], idx)
            findings.append(_make_finding(
                page_number=p["page_number"],
                severity="major",
                category="drawing_error",
                description=f"Outdated standard reference: {marker} ({correction})",
                evidence=f"Page {p['page_number']}: {quote!r}",
                evidence_quote=marker,
                recommendation=f"Update reference to the current edition. {correction}.",
                rule_id=f"TEXT-OUTDATED-{re.sub(r'[^A-Z0-9]', '', marker)}",
            ))
    return findings


def rule_code_cycle_2022_vs_2025(pages: list[dict]) -> list[dict]:
    """Flag if the cover sheet code-cycle reference is 2022 (when 2025 is current).

    CA is on a 3-year code cycle. 2022 was current 2023–2025; 2025 cycle is now
    in effect. Common drafting error to leave 2022 cycle on cover.
    """
    findings = []
    pattern = re.compile(
        r"(20(?:22|25))\s*(?:CBC|CRC|CEC|CMC|CPC|CFC|CALIFORNIA BUILDING CODE|CALIFORNIA RESIDENTIAL CODE)",
        re.IGNORECASE,
    )
    for p in pages:
        for m in pattern.finditer(p["text"]):
            year = m.group(1)
            if year == "2022":
                quote = _context(p["text"], m.start())
                findings.append(_make_finding(
                    page_number=p["page_number"],
                    severity="major",
                    category="code",
                    description="2022 code cycle referenced — verify project is vested to 2022 vs. current 2025 adopted cycle",
                    evidence=f"Page {p['page_number']}: {quote!r}",
                    evidence_quote=m.group(0),
                    recommendation="Update to 2025 code-cycle references, or add an explicit vesting note if the project predates the current cycle's effective date.",
                    rule_id="TEXT-CODE-CYCLE-2022",
                ))
                break  # one per page enough
    return findings


def rule_lot_number_consistency(pages: list[dict]) -> list[dict]:
    """Cross-sheet check for the PROJECT'S lot number specifically.

    Looks only for the highly-specific pattern "LOT [N] OF TRACT" or
    "LOT [N] OF TRACT NO" which is the formal subject-lot reference.
    Ignores generic "LOT 84", "LOT 87" mentions which appear on neighborhood
    survey sheets as labels for adjacent properties.
    """
    pattern = re.compile(
        r"LOT\s*#?\s*(\d{1,4})\s+OF\s+TRACT(?:\s+NO\.?)?\.?\s*(\d{3,4})?",
        re.IGNORECASE,
    )
    per_value: dict[str, set[int]] = {}
    for p in pages:
        for m in pattern.finditer(p["text"]):
            val = m.group(1)
            per_value.setdefault(val, set()).add(p["page_number"])

    if len(per_value) < 2:
        return []

    # Build a single coordination finding citing every distinct lot value
    # for the project (since they should all match).
    ranked = sorted(per_value.items(), key=lambda kv: -len(kv[1]))
    evidence_parts = []
    all_pages = set()
    for v, pns in ranked:
        evidence_parts.append(f'"LOT {v} OF TRACT ..." appears on pages {sorted(pns)}')
        all_pages.update(pns)
    return [_make_finding(
        page_number="multiple",
        severity="critical",
        category="coordination",
        description=f"Project lot number is inconsistent across sheets: {[v for v, _ in ranked]}",
        evidence=" | ".join(evidence_parts),
        evidence_quote=f"Lot values: {[v for v, _ in ranked]}",
        recommendation="Reconcile against the survey's legal description. All sheets must cite the same lot number.",
        rule_id="TEXT-LOT-NUMBER-COORD",
        pages_involved=sorted(all_pages),
    )]


def rule_lot_area_consistency(pages: list[dict]) -> list[dict]:
    """Cross-sheet check: every LOT AREA reference should agree.

    Requires the SF value to be PRECEDED by "LOT AREA" / "LOT SIZE" / similar
    label within a small window. This avoids false positives on building areas,
    impervious-area calcs, room areas, etc.
    """
    # Match: LOT AREA/SIZE/etc. [optional words] [optional :/=] [number] [SF unit]
    label_pattern = re.compile(
        r"(LOT\s+AREA|LOT\s+SIZE|PROPERTY\s+AREA|SITE\s+AREA|TOTAL\s+LOT|NET\s+LOT)\b[^0-9]{0,40}?(\d{1,3}(?:,?\d{3}))\s*(?:S\.?\s*F\.?|SQ\.?\s*FT|SQ\.?\s*FEET)",
        re.IGNORECASE | re.DOTALL,
    )
    per_value: dict[str, set[int]] = {}
    for p in pages:
        for m in label_pattern.finditer(p["text"]):
            raw = m.group(2).replace(",", "")
            try:
                num = int(raw)
            except ValueError:
                continue
            if 1000 <= num <= 1_000_000:
                per_value.setdefault(raw, set()).add(p["page_number"])

    if len(per_value) < 2:
        return []

    # Cluster values within ±50 SF as "essentially the same value" (rounding noise)
    sorted_vals = sorted(per_value.keys(), key=int)
    groups: list[list[str]] = []
    for v in sorted_vals:
        if groups and abs(int(v) - int(groups[-1][0])) <= 50:
            groups[-1].append(v)
        else:
            groups.append([v])
    if len(groups) < 2:
        return []

    evidence_parts = []
    all_pages = set()
    shown_values = []
    for grp in groups:
        pns = sorted({pn for v in grp for pn in per_value[v]})
        values_str = "/".join(grp)
        evidence_parts.append(f"~{grp[0]} SF (variants: {values_str}) appears on pages {pns}")
        all_pages.update(pns)
        shown_values.append(values_str)
    return [_make_finding(
        page_number="multiple",
        severity="major",
        category="coordination",
        description=f"Lot area is inconsistent across sheets: distinct values {shown_values}",
        evidence=" | ".join(evidence_parts),
        evidence_quote=f"Lot area values: {shown_values}",
        recommendation="Survey is authoritative. All sheets must cite the survey's lot area to the exact square foot.",
        rule_id="TEXT-LOT-AREA-COORD",
        pages_involved=sorted(all_pages),
    )]


def rule_wui_status_not_stated(pages: list[dict]) -> list[dict]:
    """Flag if the drawing set never mentions WUI status / Chapter 7A.

    For California projects, WUI status (per CAL FIRE FHSZ map) should be
    explicitly stated on the cover or general-notes sheet. If no page mentions
    WUI, Chapter 7A, R337, or Wildland, the set is incomplete on this required
    item.
    """
    keywords = ["WUI", "WILDLAND", "CHAPTER 7A", "R337", "FHSZ", "FIRE HAZARD SEVERITY"]
    found_anywhere = False
    for p in pages:
        for kw in keywords:
            if kw in p["text_upper"]:
                found_anywhere = True
                break
        if found_anywhere:
            break
    if not found_anywhere:
        return [_make_finding(
            page_number="multiple",
            severity="major",
            category="code",
            description="No WUI / Chapter 7A / Fire Hazard Severity Zone reference anywhere in the drawing set",
            evidence="Searched every page; no keyword from [WUI, Wildland, Chapter 7A, R337, FHSZ, Fire Hazard Severity] found",
            evidence_quote="(absence)",
            recommendation="State WUI status on the cover (per CAL FIRE FHSZ map). If WUI applies, reference Chapter 7A material compliance.",
            rule_id="TEXT-WUI-MISSING",
        )]
    return []


def rule_required_crc_notes_present(pages: list[dict]) -> list[dict]:
    """Flag if specific CRC sections expected on the general-notes sheet are missing.

    Only checks for presence — if the section is referenced anywhere, the rule
    is satisfied. If completely absent, flag.
    """
    required_sections = [
        ("R302.6", "1-hr garage separation"),
        ("R314", "smoke alarms"),
        ("R315", "carbon monoxide alarms"),
        ("R308.4", "safety glazing"),
        ("R319", "address marker"),
    ]
    findings = []
    full_text_upper = "\n".join(p["text_upper"] for p in pages)
    for section, topic in required_sections:
        if section not in full_text_upper:
            findings.append(_make_finding(
                page_number="multiple",
                severity="minor",
                category="code",
                description=f"CRC {section} ({topic}) not referenced anywhere in the drawing set",
                evidence="Searched every page for the literal section number; not found",
                evidence_quote=f"(CRC {section} absent)",
                recommendation=f"Add CRC {section} reference on the general-notes sheet covering {topic}.",
                rule_id=f"TEXT-CRC-MISSING-{section.replace('.', '_')}",
            ))
    return findings


# ─────────────────────────────────────────────────────────────────────────────
# Main entry
# ─────────────────────────────────────────────────────────────────────────────

ALL_RULES: list[Callable[[list[dict]], list[dict]]] = [
    rule_preliminary_titleblock,
    rule_crawlspace_ventilation_formula,
    rule_wrong_city_template_text,
    rule_ai_template_artifacts,
    rule_outdated_standards,
    rule_code_cycle_2022_vs_2025,
    rule_lot_number_consistency,
    rule_lot_area_consistency,
    rule_wui_status_not_stated,
    rule_required_crc_notes_present,
]


def run_text_pass(pdf_bytes: bytes) -> dict:
    """Run all text-extraction rules over a PDF and return findings + metadata.

    Returns:
        {
            "findings": list[dict],          # findings with source="text_extraction"
            "pages_total": int,
            "pages_with_text": int,          # how many pages had any extractable text
            "rule_counts": dict[str, int],   # findings per rule_id (for debugging)
        }
    """
    pages = extract_pages(pdf_bytes)
    pages_with_text = sum(1 for p in pages if len(p["text"].strip()) > 50)

    all_findings: list[dict] = []
    rule_counts: dict[str, int] = {}
    for rule_fn in ALL_RULES:
        rule_findings = rule_fn(pages)
        all_findings.extend(rule_findings)
        for f in rule_findings:
            rid = f.get("rule_id", "unknown")
            rule_counts[rid] = rule_counts.get(rid, 0) + 1

    return {
        "findings": all_findings,
        "pages_total": len(pages),
        "pages_with_text": pages_with_text,
        "rule_counts": rule_counts,
    }


if __name__ == "__main__":
    # Quick CLI: python text_pass.py path/to/drawing.pdf
    import json
    import sys
    if len(sys.argv) < 2:
        print("Usage: python text_pass.py <path-to-pdf>")
        sys.exit(1)
    with open(sys.argv[1], "rb") as f:
        pdf_bytes = f.read()
    result = run_text_pass(pdf_bytes)
    print(f"Pages: {result['pages_total']} (with extractable text: {result['pages_with_text']})")
    print(f"Findings: {len(result['findings'])}")
    print(f"Rule counts: {json.dumps(result['rule_counts'], indent=2)}")
    print()
    for i, f in enumerate(result["findings"], 1):
        print(f"[{i}] {f['severity'].upper()} ({f['rule_id']}) page={f['page_number']}")
        print(f"    {f['description']}")
        print(f"    evidence: {f['evidence'][:120]}")
        print()
