import base64
import csv
import hashlib
import html
import io
import re
from datetime import datetime
from io import StringIO

import streamlit as st
from PIL import Image

from ai_reviewer import (
    COST_PER_PAGE_USD,
    MAX_PAGES,
    is_api_key_set,
    review_full_pdf,
    review_single_page,
)
from audits_store import (
    has_page_image,
    list_audits,
    load_audit,
    load_page_image,
    normalize_findings_data,
    save_audit,
    save_page_image,
)
from pdf_processor import get_pdf_info, merge_pdfs, render_page_to_image
from pdf_report import build_report
from pin_overlay import annotate_sheet, encode_jpeg_data_url, normalize_region, normalize_severity
from prompts import JURISDICTION_PROMPTS
from references_loader import load_references, references_summary_short

st.set_page_config(
    page_title="PlanCheck",
    page_icon="◐",
    layout="wide",
    initial_sidebar_state="collapsed",
)


@st.cache_data(show_spinner=False)
def _cached_pdf_info(pdf_hash: str, _pdf_bytes: bytes):
    return get_pdf_info(_pdf_bytes)


@st.cache_data(show_spinner="Merging files…")
def _cached_merge(combined_hash: str, _file_inputs: list) -> dict:
    """Merge multiple PDFs; cached on the combined hash so the work happens once."""
    return merge_pdfs(_file_inputs)


@st.cache_data(show_spinner=False)
def _cached_thumb_url(pdf_hash: str, _pdf_bytes: bytes, page_num: int, max_dim: int = 280) -> str:
    """Render a small page thumbnail and return it as a base64 data URL.

    Cached so that 50 findings on 10 unique pages produce only 10 renders.
    """
    img = render_page_to_image(_pdf_bytes, page_num, dpi=72)
    if img.mode != "RGB":
        img = img.convert("RGB")
    w, h = img.size
    if max(w, h) > max_dim:
        scale = max_dim / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=72, optimize=True)
    return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"


@st.cache_data(show_spinner=False)
def _cached_annotated_thumb_url(
    pdf_hash: str,
    _pdf_bytes: bytes,
    page_num: int,
    pins: tuple,           # tuple of (label, region, severity) tuples — must be hashable for cache key
    max_dim: int = 280,
) -> str:
    """Render a small thumbnail of a page with all its pins overlaid.

    Pins are passed as a tuple-of-tuples so Streamlit can hash them for the cache
    key (lists of dicts are not hashable). The same sheet with the same set of pins
    is cached and reused across all finding cards on that sheet.
    """
    img = render_page_to_image(_pdf_bytes, page_num, dpi=72)
    pin_dicts = [{"label": p[0], "region": p[1], "severity": p[2]} for p in pins]
    annotated = annotate_sheet(img, pin_dicts) if pin_dicts else img
    if annotated.mode != "RGB":
        annotated = annotated.convert("RGB")
    w, h = annotated.size
    if max(w, h) > max_dim:
        scale = max_dim / max(w, h)
        annotated = annotated.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    return encode_jpeg_data_url(annotated, quality=78)


@st.cache_data(show_spinner=False)
def _cached_annotated_sheet_url(
    pdf_hash: str,
    _pdf_bytes: bytes,
    page_num: int,
    pins: tuple,
    max_dim: int = 1100,
) -> str:
    """Render a larger annotated sheet for the 'Annotated Sheets' overview section."""
    img = render_page_to_image(_pdf_bytes, page_num, dpi=120)
    pin_dicts = [{"label": p[0], "region": p[1], "severity": p[2]} for p in pins]
    annotated = annotate_sheet(img, pin_dicts) if pin_dicts else img
    if annotated.mode != "RGB":
        annotated = annotated.convert("RGB")
    w, h = annotated.size
    if max(w, h) > max_dim:
        scale = max_dim / max(w, h)
        annotated = annotated.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    return encode_jpeg_data_url(annotated, quality=82)


def _pins_for_page(findings: list[dict], page_num: int) -> tuple:
    """Build a hashable tuple of (label, region, severity) for every finding on page_num.

    The label is the FND-NN code that matches the finding card. Pins are sorted
    by their finding index so the cache key is stable across reruns.
    """
    pins = []
    for idx, f in enumerate(findings, 1):
        if f.get("page_number") != page_num:
            continue
        label = f"{idx:02d}"
        region = normalize_region(f.get("region"))
        severity = normalize_severity(f.get("severity"))
        pins.append((label, region, severity))
    return tuple(pins)


def _page_sort_value(page_number) -> tuple[int, int]:
    """Sortable scalar for finding.page_number.

    Per-sheet findings (int page_number) sort by their page; cross-sheet
    coordination findings (page_number == "multiple") sort to the end of their
    severity bucket. Without this, the sort raises TypeError when comparing
    int vs str.
    """
    if isinstance(page_number, int):
        return (0, page_number)
    return (1, 0)


def _cross_sheet_badge_html(finding: dict) -> str:
    """Return the badge HTML for a cross-sheet coordination finding.

    Uses sheets_involved if the model populated them; falls back to a generic
    'CROSS-SHEET' label otherwise. Empty string for non-coordination findings.
    """
    if finding.get("page_number") != "multiple":
        return ""
    sheets = finding.get("sheets_involved") or []
    label = " ↔ ".join(str(s) for s in sheets if s) if sheets else "CROSS-SHEET"
    return f'<span class="badge cross">↔ {html.escape(label)}</span>'


# ────────────────────────────────────────────────────────────────────────
# Review-mode renderers (Phase 2)
#
# When loading a past audit from disk, pdf_bytes is unavailable. Instead we
# read the JPEG renders saved alongside the audit JSON in `<id>_assets/` and
# apply pin overlays on the fly. Cache key uses (audit_id, page_num, pins)
# — bytes don't enter the function signature, so Streamlit can hash it.
# Returns "" if no saved image exists (legacy audits saved before Phase 2).
# ────────────────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def _cached_review_thumb_url(
    audit_id: str,
    page_num: int,           # 1-indexed (matches finding.page_number)
    pins: tuple,
    max_dim: int = 280,
) -> str:
    img = load_page_image(audit_id, page_num - 1)
    if img is None:
        return ""
    pin_dicts = [{"label": p[0], "region": p[1], "severity": p[2]} for p in pins]
    annotated = annotate_sheet(img, pin_dicts) if pin_dicts else img
    if annotated.mode != "RGB":
        annotated = annotated.convert("RGB")
    w, h = annotated.size
    if max(w, h) > max_dim:
        scale = max_dim / max(w, h)
        annotated = annotated.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    return encode_jpeg_data_url(annotated, quality=78)


@st.cache_data(show_spinner=False)
def _cached_review_sheet_url(
    audit_id: str,
    page_num: int,           # 1-indexed
    pins: tuple,
    max_dim: int = 1100,
) -> str:
    img = load_page_image(audit_id, page_num - 1)
    if img is None:
        return ""
    pin_dicts = [{"label": p[0], "region": p[1], "severity": p[2]} for p in pins]
    annotated = annotate_sheet(img, pin_dicts) if pin_dicts else img
    if annotated.mode != "RGB":
        annotated = annotated.convert("RGB")
    w, h = annotated.size
    if max(w, h) > max_dim:
        scale = max_dim / max(w, h)
        annotated = annotated.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    return encode_jpeg_data_url(annotated, quality=82)


SEVERITIES = ("critical", "major", "minor", "advisory")
FILTER_LABELS = ("All", "Critical", "Major", "Minor", "Advisory")

JURISDICTION_LABELS = ("Cupertino (city + state)",)

# Roles defined in references/general instructions.txt — used by the role-selector
# at the top of the page. "—" means no role chosen (read-only mode for everyone).
ROLE_LABELS = (
    "— (view only)",
    "Principal Architect",
    "Project Architect",
    "Structure Engineer",
    "Site Architect / Construction Manager",
    "Operations Manager",
    "Office Administration",
)
ROLE_NONE = ROLE_LABELS[0]
ROLE_PRINCIPAL = "Principal Architect"
ROLE_PROJECT = "Project Architect"

# Assignment dropdown options — everyone EXCEPT the "view only" sentinel.
# "Unassigned" lets Principal explicitly clear an existing assignment.
ASSIGN_UNASSIGNED = "— Unassigned"
ROLE_ASSIGNABLE = (ASSIGN_UNASSIGNED, *ROLE_LABELS[1:])


def _normalize_severity(s: str) -> str:
    s = (s or "").strip().lower()
    return s if s in SEVERITIES else "advisory"


def _safe_filename_stem(name: str) -> str:
    stem = name.rsplit(".", 1)[0] if "." in name else name
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", stem).strip("-")
    return cleaned or "plancheck"


def _resave_current_audit() -> None:
    """Persist any edits/resolves to the JSON file backing the current audit.

    Silent on failure — disk being unwritable shouldn't break the UI.
    Called from edit/resolve/add handlers so every mutation is durable.
    """
    fd = st.session_state.get("findings_data")
    audit_id = st.session_state.get("current_audit_id")
    if not fd or not audit_id:
        return
    try:
        save_audit(fd, audit_id=audit_id)
    except Exception:
        pass


# ─── Phase 1 Gate 2 — finding mutation callbacks ───────────────────────────
# All take a 1-based original_idx (the FND-NN number) and operate on
# findings_data["findings"][idx-1] in place. Each calls _resave_current_audit()
# so changes survive a browser refresh.

def _toggle_resolved(idx: int) -> None:
    """Project Architect ticked/unticked the Resolve checkbox on FND-{idx}."""
    fd = st.session_state.get("findings_data")
    if not fd or idx <= 0 or idx > len(fd.get("findings", [])):
        return
    f = fd["findings"][idx - 1]
    new_state = bool(st.session_state.get(f"resolve_{idx}"))
    f["resolved"] = new_state
    if new_state:
        f["resolved_by"] = st.session_state.get("current_role") or "—"
        f["resolved_at"] = datetime.now().isoformat(timespec="seconds")
    else:
        f["resolved_by"] = None
        f["resolved_at"] = None
    _resave_current_audit()


def _start_editing(idx: int) -> None:
    st.session_state["editing_idx"] = idx
    st.session_state["adding_finding"] = False  # close add form if open


def _cancel_edit() -> None:
    st.session_state["editing_idx"] = None


def _save_edit(idx: int, new_severity: str, new_description: str,
               new_evidence: str, new_recommendation: str,
               assigned_to: str | None = None) -> None:
    """Apply Principal's edits to FND-{idx} and persist to disk.

    assigned_to is one of the role labels, ASSIGN_UNASSIGNED, or None to
    leave the existing assignment alone (rarely useful — callers always
    pass a value from the dropdown).
    """
    fd = st.session_state.get("findings_data")
    if not fd or idx <= 0 or idx > len(fd.get("findings", [])):
        return
    f = fd["findings"][idx - 1]
    f["severity"] = new_severity
    f["description"] = new_description.strip()
    f["evidence"] = new_evidence.strip()
    f["recommendation"] = new_recommendation.strip()
    f["edited"] = True
    f["edited_by"] = st.session_state.get("current_role") or "—"
    f["edited_at"] = datetime.now().isoformat(timespec="seconds")
    if assigned_to is not None:
        if assigned_to == ASSIGN_UNASSIGNED:
            # Principal explicitly cleared the assignment.
            if f.get("assigned_to"):
                f["assigned_to"] = None
                f["assigned_by"] = None
                f["assigned_at"] = None
        elif assigned_to != f.get("assigned_to"):
            f["assigned_to"] = assigned_to
            f["assigned_by"] = st.session_state.get("current_role") or "—"
            f["assigned_at"] = datetime.now().isoformat(timespec="seconds")
    _resave_current_audit()
    st.session_state["editing_idx"] = None


def _start_adding() -> None:
    st.session_state["adding_finding"] = True
    st.session_state["editing_idx"] = None  # close any open edit


def _cancel_add() -> None:
    st.session_state["adding_finding"] = False


def _save_new_finding(severity: str, category: str, description: str,
                      evidence: str, recommendation: str,
                      page_number: int, region: str,
                      assigned_to: str | None = None) -> None:
    """Append a Principal-authored finding to the audit and persist.

    assigned_to is the role label of the teammate this finding is directed
    at (or ASSIGN_UNASSIGNED / None for no assignment).
    """
    fd = st.session_state.get("findings_data")
    if not fd:
        return
    _now = datetime.now().isoformat(timespec="seconds")
    _author = st.session_state.get("current_role") or "—"
    _assigned = (
        assigned_to if assigned_to and assigned_to != ASSIGN_UNASSIGNED else None
    )
    new_finding = {
        "severity":       severity,
        "category":       category,
        "description":    description.strip(),
        "evidence":       evidence.strip(),
        "recommendation": recommendation.strip(),
        "page_number":    int(page_number) if page_number else 1,
        "region":         region,
        "manually_added": True,
        "added_by":       _author,
        "added_at":       _now,
        "edited":         False,
        "edited_by":      None,
        "edited_at":      None,
        "resolved":       False,
        "resolved_by":    None,
        "resolved_at":    None,
        "assigned_to":    _assigned,
        "assigned_by":    _author if _assigned else None,
        "assigned_at":    _now if _assigned else None,
    }
    fd["findings"].append(new_finding)
    _resave_current_audit()
    st.session_state["adding_finding"] = False


def _truncate_filename(name: str, max_len: int = 28) -> str:
    if len(name) <= max_len:
        return name
    stem, _, ext = name.rpartition(".")
    if not ext or len(ext) > 5:
        return name[: max_len - 1] + "…"
    keep = max_len - len(ext) - 2
    return stem[:keep] + "…." + ext


def _source_for_page(
    page_num: int,
    page_map: list | None,
    fallback_filename: str,
) -> tuple[str, int]:
    """Return (source_filename, page_in_source) for a 1-based page number.

    If page_map is None (single-file upload), the fallback filename is used and
    the page number passes through unchanged. If page_map is set, the lookup
    yields the original file + original page within that file.
    """
    if page_map and 0 < page_num <= len(page_map):
        entry = page_map[page_num - 1]
        return entry.get("source_file", fallback_filename), entry.get("page_in_source", page_num)
    return fallback_filename, page_num


def _build_findings_csv(
    findings: list[dict],
    page_map: list | None,
    fallback_filename: str,
    meta: dict | None = None,
) -> str:
    buf = StringIO()
    writer = csv.writer(buf, lineterminator="\n")

    # Self-describing metadata header (Week 1 — Deliverable 2f, +references)
    meta = meta or {}
    if meta:
        writer.writerow(["Project", meta.get("project_name", "")])
        writer.writerow(["Architect", meta.get("architect", "")])
        writer.writerow(["Jurisdiction", meta.get("jurisdiction", "")])
        writer.writerow(["Set date", meta.get("set_date", "")])
        writer.writerow(["Generated", meta.get("generated_at", "")])
        ref_files = meta.get("references_files") or []
        ref_words = meta.get("references_word_count", 0)
        if ref_files:
            writer.writerow([
                "References applied",
                f"{', '.join(ref_files)} ({ref_words:,} words)",
            ])
        else:
            writer.writerow(["References applied", "none"])
        writer.writerow([])  # blank separator row

    writer.writerow([
        "Source File",
        "Page",
        "Severity",
        "Category",
        "Description",
        "Evidence",
        "Recommendation",
    ])
    for f in findings:
        page_num = f.get("page_number")
        src_file, src_page = _source_for_page(
            page_num if isinstance(page_num, int) else 0,
            page_map,
            fallback_filename,
        )
        writer.writerow([
            src_file,
            src_page,
            _normalize_severity(f.get("severity")),
            (f.get("category") or "").strip(),
            (f.get("description") or "").strip(),
            (f.get("evidence") or "").strip(),
            (f.get("recommendation") or "").strip(),
        ])
    return buf.getvalue()


st.markdown(
    """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,400;0,9..144,500;0,9..144,700;1,9..144,400;1,9..144,500&family=IBM+Plex+Sans:wght@300;400;500;600&family=JetBrains+Mono:wght@300;400;500;700&display=swap" rel="stylesheet">

<style>
  :root {
    --ink: #EFE6D2;
    --ink-dim: #B7AE9A;
    --paper: #0B1B2D;
    --paper-2: #13283F;
    --blueprint: #7FCBE3;
    --blueprint-dim: #3D8DAA;
    --vermillion: #E8654F;
    --amber: #F0A060;
    --ochre: #E8C84F;
    --rule: rgba(127, 203, 227, 0.14);
    --rule-strong: rgba(127, 203, 227, 0.28);
  }

  html, body, .stApp, [class*="css"] {
    background: var(--paper) !important;
    color: var(--ink) !important;
    font-family: 'IBM Plex Sans', sans-serif !important;
  }

  #MainMenu, footer, header[data-testid="stHeader"] { display: none !important; }
  .stDeployButton, div[data-testid="stToolbar"] { display: none !important; }

  .stApp::before, .stApp::after { content: none !important; display: none !important; }

  .main .block-container { position: relative; z-index: 1; padding-top: 1.2rem; max-width: 1280px; }

  /* Title block */
  .titleblock {
    display: grid; grid-template-columns: auto auto auto auto auto 1fr auto;
    border-top: 1px solid var(--rule-strong); border-bottom: 1px solid var(--rule-strong);
    padding: 14px 0; margin-bottom: 56px;
    font-family: 'JetBrains Mono', monospace; font-size: 11px; letter-spacing: 0.12em;
    text-transform: uppercase; color: var(--ink-dim);
  }
  .titleblock .cell { border-right: 1px solid var(--rule); padding: 0 22px; }
  .titleblock .cell:first-child { padding-left: 0; }
  .titleblock .cell.spacer { border-right: none; }
  .titleblock .cell:last-child { text-align: right; border-right: none; color: var(--blueprint); }
  .titleblock .label { display: block; font-size: 9px; color: var(--ink-dim); opacity: 0.6; margin-bottom: 4px; letter-spacing: 0.18em; }
  .titleblock .val { display: block; color: var(--ink); font-weight: 500; }

  /* Hero */
  .hero {
    display: grid; grid-template-columns: 1fr 240px; gap: 80px; align-items: end;
    padding: 24px 0 56px 0; border-bottom: 1px solid var(--rule); margin-bottom: 48px;
    animation: rise 0.9s cubic-bezier(0.16, 1, 0.3, 1) both;
  }
  @keyframes rise { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: translateY(0); } }
  .hero h1 {
    font-family: 'Fraunces', serif; font-variation-settings: "opsz" 144, "SOFT" 30;
    font-size: clamp(56px, 9vw, 132px); font-weight: 400; line-height: 0.92;
    letter-spacing: -0.025em; color: var(--ink); margin: 0 0 24px 0;
  }
  .hero h1 em { font-style: italic; color: var(--blueprint); font-variation-settings: "opsz" 144, "SOFT" 100; }
  .hero p.lead { font-family: 'IBM Plex Sans', sans-serif; font-size: 18px; line-height: 1.55; color: var(--ink-dim); max-width: 560px; margin: 0; }
  .hero .stamp {
    border: 1px solid var(--blueprint-dim); padding: 14px 18px 18px 18px;
    font-family: 'JetBrains Mono', monospace; font-size: 10px; text-transform: uppercase;
    letter-spacing: 0.16em; color: var(--blueprint); transform: rotate(-1.5deg);
    box-shadow: 4px 4px 0 var(--paper-2);
  }
  .hero .stamp .big {
    display: block; font-family: 'Fraunces', serif; font-size: 44px; line-height: 1;
    letter-spacing: -0.02em; color: var(--ink); margin: 8px 0 0 0;
    font-weight: 500; font-style: italic;
  }

  /* API key banner */
  .api-banner {
    display: flex; gap: 18px; align-items: flex-start;
    padding: 16px 22px; border: 1px dashed var(--vermillion);
    background: rgba(232, 101, 79, 0.06); margin: 0 0 32px 0;
    animation: rise 0.6s cubic-bezier(0.16, 1, 0.3, 1) both;
  }
  .api-banner .icon { color: var(--vermillion); font-size: 26px; font-family: 'Fraunces', serif; line-height: 1; padding-top: 2px; }
  .api-banner .ttl {
    font-family: 'JetBrains Mono', monospace; font-size: 11px; text-transform: uppercase;
    letter-spacing: 0.18em; color: var(--vermillion); margin-bottom: 6px; font-weight: 500;
  }
  .api-banner .body { font-family: 'IBM Plex Sans', sans-serif; font-size: 14px; color: var(--ink); line-height: 1.5; }
  .api-banner code { font-family: 'JetBrains Mono', monospace; font-size: 12px; background: rgba(127, 203, 227, 0.1); color: var(--blueprint); padding: 2px 6px; border-radius: 0; }

  /* Intake header */
  .intake-header { display: flex; align-items: baseline; gap: 24px; margin-bottom: 18px; border-bottom: 1px solid var(--rule); padding-bottom: 14px; }
  .intake-header .num { font-family: 'JetBrains Mono', monospace; font-size: 10px; text-transform: uppercase; letter-spacing: 0.18em; color: var(--blueprint); }
  .intake-header .ttl { font-family: 'Fraunces', serif; font-size: 24px; font-weight: 500; color: var(--ink); letter-spacing: -0.01em; }
  .intake-header .copy { margin-left: auto; font-family: 'Fraunces', serif; font-style: italic; font-size: 14px; color: var(--ink-dim); }

  /* File uploader styling */
  [data-testid="stFileUploader"] { margin-bottom: 12px; }
  [data-testid="stFileUploader"] section[data-testid="stFileUploaderDropzone"] {
    border: 1px dashed var(--blueprint-dim) !important;
    background: rgba(13, 27, 45, 0.45) !important;
    background-image: repeating-linear-gradient(45deg, transparent 0 18px, rgba(127, 203, 227, 0.04) 18px 19px) !important;
    border-radius: 0 !important; padding: 56px 32px !important;
    transition: border-color 0.3s, background 0.3s;
  }
  [data-testid="stFileUploader"] section[data-testid="stFileUploaderDropzone"]:hover {
    border-color: var(--blueprint) !important; background: rgba(127, 203, 227, 0.04) !important;
  }
  [data-testid="stFileUploaderDropzoneInstructions"] span,
  [data-testid="stFileUploader"] section span {
    font-family: 'Fraunces', serif !important; font-style: italic !important;
    font-size: 18px !important; color: var(--ink) !important;
  }
  [data-testid="stFileUploader"] small,
  [data-testid="stFileUploaderDropzoneInstructions"] small {
    color: var(--ink-dim) !important; font-family: 'JetBrains Mono', monospace !important;
    font-size: 10px !important; text-transform: uppercase !important;
    letter-spacing: 0.18em !important; font-style: normal !important;
  }
  [data-testid="stFileUploader"] section button {
    background: transparent !important; border: 1px solid var(--blueprint) !important;
    color: var(--blueprint) !important; font-family: 'JetBrains Mono', monospace !important;
    font-size: 11px !important; text-transform: uppercase !important;
    letter-spacing: 0.18em !important; padding: 8px 18px !important;
    border-radius: 0 !important; font-weight: 500 !important; transition: all 0.2s;
    box-shadow: none !important;
  }
  [data-testid="stFileUploader"] section button:hover {
    background: var(--blueprint) !important; color: var(--paper) !important;
  }
  [data-testid="stFileUploaderFile"], [data-testid="stFileUploadedFile"] {
    background: rgba(127, 203, 227, 0.06) !important; border: 1px solid var(--rule-strong) !important;
    border-radius: 0 !important; padding: 10px 14px !important;
  }
  [data-testid="stFileUploaderFile"] *, [data-testid="stFileUploadedFile"] * {
    color: var(--ink) !important; font-family: 'IBM Plex Sans', sans-serif !important;
  }

  /* Session strip (Phase 1) — role selector + audit picker at top of page */
  .session-strip-btn-spacer {
    /* Pushes the "Start fresh" button down so its top edge aligns with the
       selectbox value rows (which sit below their labels). */
    height: 28px;
  }
  .session-strip-rule {
    border-bottom: 1px solid var(--rule);
    margin: 12px 0 28px 0;
  }

  /* Project-details inputs (Week 1 — Deliverable 2c) */
  div[data-testid="stTextInput"] label,
  div[data-testid="stSelectbox"] label,
  div[data-testid="stDateInput"] label {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 9px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.18em !important;
    color: var(--ink-dim) !important;
    opacity: 0.7;
    margin-bottom: 4px !important;
  }
  div[data-testid="stTextInput"] input,
  div[data-testid="stDateInput"] input {
    background: rgba(13, 27, 45, 0.45) !important;
    color: var(--ink) !important;
    border: 1px solid var(--rule-strong) !important;
    border-radius: 0 !important;
    font-family: 'IBM Plex Sans', sans-serif !important;
    font-size: 14px !important;
    padding: 10px 12px !important;
    box-shadow: none !important;
  }
  div[data-testid="stTextInput"] input::placeholder {
    color: var(--ink-dim) !important;
    opacity: 0.5;
    font-style: italic;
  }
  div[data-testid="stTextInput"] input:focus,
  div[data-testid="stDateInput"] input:focus {
    border-color: var(--blueprint) !important;
    box-shadow: none !important;
    outline: none !important;
  }
  /* Selectbox closed display — outer container background + border */
  div[data-testid="stSelectbox"] > div[data-baseweb="select"] > div {
    background: rgba(13, 27, 45, 0.45) !important;
    border: 1px solid var(--rule-strong) !important;
    border-radius: 0 !important;
    min-height: 42px !important;
    padding: 4px 12px !important;
  }
  /* Force every nested element inside the selectbox to have generous line-height
     so descenders ('y', 'p', 'g') in the selected value never clip. BaseWeb's
     default line-height of 1 was the actual culprit. */
  div[data-testid="stSelectbox"] [data-baseweb="select"] * {
    line-height: 1.5 !important;
    overflow: visible !important;
  }
  /* The selected-value text element itself — generous vertical room */
  div[data-testid="stSelectbox"] [data-baseweb="select"] [data-testid="stSelectboxVirtualDropdown"],
  div[data-testid="stSelectbox"] [data-baseweb="select"] [class*="ValueContainer"],
  div[data-testid="stSelectbox"] [data-baseweb="select"] [class*="SingleValue"] {
    min-height: 26px !important;
    padding-top: 2px !important;
    padding-bottom: 2px !important;
  }
  div[data-testid="stSelectbox"] [data-baseweb="select"] * {
    color: var(--ink) !important;
    font-family: 'IBM Plex Sans', sans-serif !important;
    font-size: 14px !important;
  }
  /* Date-input calendar icon */
  div[data-testid="stDateInput"] svg { fill: var(--blueprint) !important; }

  /* Intake titleblock */
  .intake-block {
    display: grid; grid-template-columns: 2fr 1fr 1fr 1fr 1fr;
    border-top: 1px solid var(--blueprint-dim); border-bottom: 1px solid var(--blueprint-dim);
    padding: 18px 0; margin: 32px 0 28px 0;
    font-family: 'JetBrains Mono', monospace; font-size: 11px;
    letter-spacing: 0.12em; text-transform: uppercase;
    animation: rise 0.6s cubic-bezier(0.16, 1, 0.3, 1) both;
  }
  .intake-block .cell { border-right: 1px solid var(--rule); padding: 0 22px; }
  .intake-block .cell:first-child { padding-left: 0; }
  .intake-block .cell:last-child { border-right: none; padding-right: 0; }
  .intake-block .label { display: block; font-size: 9px; color: var(--ink-dim); opacity: 0.7; margin-bottom: 5px; letter-spacing: 0.18em; }
  .intake-block .val { display: block; color: var(--ink); font-weight: 500; }
  .intake-block .val.lg { font-family: 'Fraunces', serif; font-size: 18px; font-weight: 500; letter-spacing: -0.01em; text-transform: none; }
  .intake-block .val.cyan { color: var(--blueprint); }

  /* st.button (Run Plan Check) — cyan filled, with stamp shadow */
  .stButton button,
  [data-testid="stButton"] button,
  button[kind="primary"],
  button[kind="secondary"] {
    background: var(--blueprint) !important;
    background-color: var(--blueprint) !important;
    color: var(--paper) !important;
    border: 1px solid var(--blueprint) !important;
    border-radius: 0 !important;
    padding: 14px 32px !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 12px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.2em !important;
    font-weight: 500 !important;
    box-shadow: 4px 4px 0 var(--paper-2) !important;
    transition: all 0.18s !important;
  }
  .stButton button:hover,
  [data-testid="stButton"] button:hover {
    background: var(--paper) !important;
    color: var(--blueprint) !important;
    box-shadow: 6px 6px 0 var(--paper-2) !important;
    transform: translate(-2px, -2px);
  }
  .stButton button:active,
  [data-testid="stButton"] button:active {
    transform: translate(0, 0);
    box-shadow: 0 0 0 var(--paper-2) !important;
  }
  .stButton button:disabled,
  [data-testid="stButton"] button:disabled {
    opacity: 0.35 !important;
    cursor: not-allowed !important;
    transform: none !important;
    box-shadow: 4px 4px 0 var(--paper-2) !important;
  }

  /* Section heading */
  .section-head {
    display: flex; justify-content: space-between; align-items: baseline;
    border-bottom: 1px solid var(--rule); padding-bottom: 14px; margin: 48px 0 28px 0;
  }
  .section-head h3 { font-family: 'Fraunces', serif; font-size: 24px; font-weight: 500; color: var(--ink); margin: 0; letter-spacing: -0.01em; }
  .section-head .tag { font-family: 'JetBrains Mono', monospace; font-size: 11px; text-transform: uppercase; letter-spacing: 0.16em; color: var(--ink-dim); }

  /* Annotated sheets (findings overview) */
  .annotated-grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
    gap: 22px; margin-bottom: 40px;
  }
  .annotated-card {
    border: 1px solid var(--rule-strong); background: var(--paper-2);
    display: flex; flex-direction: column;
    animation: rise 0.6s cubic-bezier(0.16, 1, 0.3, 1) both;
  }
  .annotated-card:nth-child(2) { animation-delay: 0.06s; }
  .annotated-card:nth-child(3) { animation-delay: 0.12s; }
  .annotated-card:nth-child(4) { animation-delay: 0.18s; }
  .annotated-head {
    padding: 10px 14px; border-bottom: 1px solid var(--rule);
    display: flex; justify-content: space-between; align-items: baseline;
    font-family: 'JetBrains Mono', monospace; font-size: 10px;
    text-transform: uppercase; letter-spacing: 0.16em; color: var(--ink);
  }
  .annotated-head .annotated-name  { color: var(--ink); }
  .annotated-head .annotated-count { color: var(--blueprint); }
  .annotated-image {
    background: #FAF6EA; padding: 14px;
    flex: 1; display: flex; align-items: center; justify-content: center;
    min-height: 220px;
  }
  .annotated-image img { display: block; width: 100%; height: auto; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.18); }
  .annotated-image.fail {
    background: var(--paper-2); color: var(--vermillion);
    font-family: 'JetBrains Mono', monospace; font-size: 11px;
    padding: 32px; text-align: center;
  }
  .annotated-foot {
    padding: 10px 14px; border-top: 1px solid var(--rule);
    font-family: 'JetBrains Mono', monospace; font-size: 9px;
    text-transform: uppercase; letter-spacing: 0.16em;
    color: var(--ink-dim); display: flex; flex-wrap: wrap; gap: 12px;
  }
  .sev-dot {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 0;
  }
  .sev-dot::before {
    content: ""; display: inline-block;
    width: 8px; height: 8px; border-radius: 50%;
  }
  .sev-vermillion::before { background: var(--vermillion); }
  .sev-amber::before      { background: var(--amber); }
  .sev-ochre::before      { background: var(--ochre); }
  .sev-blueprint::before  { background: var(--blueprint); }
  .sev-vermillion { color: var(--vermillion); }
  .sev-amber      { color: var(--amber); }
  .sev-ochre      { color: var(--ochre); }
  .sev-blueprint  { color: var(--blueprint); }

  /* ─── Findings ──────────────────────────────────────── */
  .findings-summary {
    display: grid; grid-template-columns: repeat(4, 1fr);
    border: 1px solid var(--rule-strong); margin-bottom: 28px;
    animation: rise 0.6s cubic-bezier(0.16, 1, 0.3, 1) both;
  }
  .findings-summary .stat { padding: 22px 24px; border-right: 1px solid var(--rule); display: flex; flex-direction: column; gap: 6px; }
  .findings-summary .stat:last-child { border-right: none; }
  .findings-summary .stat .num { font-family: 'Fraunces', serif; font-size: 42px; font-weight: 500; line-height: 1; letter-spacing: -0.02em; }
  .findings-summary .stat .lbl { font-family: 'JetBrains Mono', monospace; font-size: 10px; text-transform: uppercase; letter-spacing: 0.2em; color: var(--ink-dim); }
  .findings-summary .stat.critical .num { color: var(--vermillion); }
  .findings-summary .stat.major .num    { color: var(--amber); }
  .findings-summary .stat.minor .num    { color: var(--ochre); }
  .findings-summary .stat.advisory .num { color: var(--blueprint); }

  /* Phase 1 Gate 3 — Resolution-progress row + Dashboard charts */
  .resolution-row {
    display: grid;
    grid-template-columns: 110px 110px 60px 1fr;
    align-items: center;
    gap: 18px;
    padding: 14px 22px;
    border: 1px solid var(--rule-strong);
    border-top: none;
    margin: -28px 0 28px 0;
    background: rgba(110, 192, 123, 0.04);
  }
  .resolution-row .lbl {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px; text-transform: uppercase; letter-spacing: 0.2em;
    color: #6EC07B;
  }
  .resolution-row .count {
    font-family: 'Fraunces', serif;
    font-size: 22px; font-weight: 500;
    color: var(--ink);
    letter-spacing: -0.01em;
  }
  .resolution-row .count .of {
    font-size: 11px; color: var(--ink-dim); font-weight: 400; font-style: italic;
    margin: 0 4px;
  }
  .resolution-row .pct {
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px; color: #6EC07B; font-weight: 500;
    letter-spacing: 0.06em; text-align: right;
  }
  .resolution-row .bar {
    height: 6px; background: rgba(127, 203, 227, 0.08);
    position: relative;
    border: 1px solid var(--rule);
  }
  .resolution-row .bar-fill {
    height: 100%;
    background: #6EC07B;
    transition: width 0.4s cubic-bezier(0.16, 1, 0.3, 1);
  }

  /* Section labels above dashboard charts */
  .dashboard-head {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px; text-transform: uppercase; letter-spacing: 0.22em;
    color: var(--blueprint);
    margin: 18px 0 8px 0;
    padding-top: 14px;
    border-top: 1px solid var(--rule);
  }
  .dashboard-subhead {
    font-family: 'JetBrains Mono', monospace;
    font-size: 9px; text-transform: uppercase; letter-spacing: 0.18em;
    color: var(--ink-dim);
    margin: 14px 0 4px 0;
  }

  .findings-stack { display: flex; flex-direction: column; gap: 16px; margin-bottom: 56px; }
  .finding {
    border: 1px solid var(--rule-strong); background: rgba(19, 40, 63, 0.92);
    border-left-width: 4px; animation: rise 0.5s cubic-bezier(0.16, 1, 0.3, 1) both;
  }
  .finding-critical { border-left-color: var(--vermillion); }
  .finding-major    { border-left-color: var(--amber); }
  .finding-minor    { border-left-color: var(--ochre); }
  .finding-advisory { border-left-color: var(--blueprint-dim); }

  .finding-head {
    display: flex; gap: 16px; align-items: center;
    padding: 14px 22px; border-bottom: 1px solid var(--rule);
    font-family: 'JetBrains Mono', monospace; font-size: 10px;
    text-transform: uppercase; letter-spacing: 0.18em;
  }
  .badge { padding: 4px 10px; border: 1px solid; font-weight: 500; }
  .badge-critical { color: var(--vermillion); border-color: var(--vermillion); background: rgba(232, 101, 79, 0.06); }
  .badge-major    { color: var(--amber);     border-color: var(--amber);     background: rgba(240, 160, 96, 0.06); }
  .badge-minor    { color: var(--ochre);     border-color: var(--ochre);     background: rgba(232, 200, 79, 0.06); }
  .badge-advisory { color: var(--blueprint); border-color: var(--blueprint); background: rgba(127, 203, 227, 0.06); }
  .badge.cross    { color: var(--blueprint); border-color: var(--blueprint-dim); background: rgba(127, 203, 227, 0.08); letter-spacing: 0.16em; }
  .finding-head .cat { color: var(--ink-dim); }
  .finding-head .no  { margin-left: auto; color: var(--ink-dim); }

  .finding-body { padding: 18px 22px 22px 22px; }
  .finding-body .desc { font-family: 'IBM Plex Sans', sans-serif; font-size: 15px; line-height: 1.55; color: var(--ink); margin: 0 0 14px 0; }
  .finding-body .kv { margin-top: 14px; padding-top: 14px; border-top: 1px dashed var(--rule); }
  .finding-body .kv .k {
    font-family: 'JetBrains Mono', monospace; font-size: 9px;
    text-transform: uppercase; letter-spacing: 0.2em; color: var(--blueprint);
    display: block; margin-bottom: 6px;
  }
  .finding-body .kv .v { font-family: 'IBM Plex Sans', sans-serif; font-size: 13px; color: var(--ink-dim); margin: 0; line-height: 1.5; }

  /* Phase 1 Gate 2 — collaboration status tags (added/edited/resolved) */
  .status-tag {
    display: inline-block;
    padding: 3px 9px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.18em;
    border: 1px solid;
    margin-left: 4px;
  }
  .status-tag.added    { color: var(--amber); border-color: var(--amber); background: rgba(240, 160, 96, 0.06); font-style: italic; }
  .status-tag.edited   { color: var(--amber); border-color: var(--amber); background: rgba(240, 160, 96, 0.06); }
  .status-tag.resolved { color: #6EC07B; border-color: #6EC07B; background: rgba(110, 192, 123, 0.06); }
  .status-tag.assigned { color: var(--blueprint); border-color: var(--blueprint); background: rgba(127, 203, 227, 0.06); }
  .status-tag.foryou   {
    color: #1a1a1a; background: var(--blueprint); border-color: var(--blueprint);
    font-weight: 700; box-shadow: 0 0 0 1px rgba(127, 203, 227, 0.4);
  }

  /* Resolved cards visually fade so unresolved items pop */
  .finding.resolved {
    opacity: 0.55;
    transition: opacity 0.18s ease-in-out;
  }
  .finding.resolved:hover { opacity: 0.95; }

  /* "For you" — current role matches the finding's assigned_to. Cyan accent
     bar on the left and a subtle glow so the card pops from the stack. */
  .finding.foryou {
    border-left-color: var(--blueprint);
    border-left-width: 4px;
    box-shadow: 0 0 0 1px rgba(127, 203, 227, 0.20), 0 1px 3px rgba(0, 0, 0, 0.12);
  }

  /* Edit-mode card gets an orange left border swap to signal it's mutable */
  .finding.editing {
    border-left-color: var(--amber);
    border-left-width: 4px;
  }
  .finding.editing .finding-head .no { color: var(--amber); }

  /* Form labels above add/edit form widgets */
  .form-eyebrow {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.22em;
    color: var(--amber);
    margin: 0 0 10px 0;
  }

  .empty-findings {
    border: 1px dashed var(--rule-strong); padding: 32px; text-align: center;
    margin-bottom: 56px;
  }
  .empty-findings .ttl { font-family: 'Fraunces', serif; font-style: italic; font-size: 22px; color: var(--blueprint); margin-bottom: 6px; }
  .empty-findings .sub { font-family: 'IBM Plex Sans', sans-serif; font-size: 13px; color: var(--ink-dim); }

  /* Page badge inside finding head */
  .finding-head .pg {
    color: var(--blueprint);
    border: 1px solid var(--blueprint-dim);
    padding: 3px 9px; letter-spacing: 0.18em;
  }
  /* Source-file badge (multi-file mode) — shows filename + page within source */
  .finding-head .src {
    color: var(--ink);
    border: 1px solid var(--rule-strong);
    background: rgba(127, 203, 227, 0.04);
    padding: 3px 9px; letter-spacing: 0.14em;
    text-transform: none;
    font-style: italic;
  }
  .finding-head .src .src-page { color: var(--blueprint); margin-left: 6px; font-style: normal; letter-spacing: 0.18em; }

  /* Intake-order list (multi-file) */
  .intake-order {
    border: 1px solid var(--rule);
    margin: -8px 0 28px 0;
    animation: rise 0.5s cubic-bezier(0.16, 1, 0.3, 1) both;
  }
  .intake-order .head {
    display: flex; justify-content: space-between; align-items: center;
    padding: 10px 18px; border-bottom: 1px solid var(--rule);
    background: rgba(127, 203, 227, 0.04);
    font-family: 'JetBrains Mono', monospace; font-size: 10px;
    text-transform: uppercase; letter-spacing: 0.18em;
  }
  .intake-order .head .ttl  { color: var(--blueprint); }
  .intake-order .head .copy { color: var(--ink-dim); font-style: italic; text-transform: none; letter-spacing: 0; font-family: 'Fraunces', serif; font-size: 12px; }
  .intake-order .row {
    display: grid; grid-template-columns: 36px 1fr 90px 80px 80px;
    align-items: center; gap: 14px;
    padding: 10px 18px; border-bottom: 1px dashed var(--rule);
    font-family: 'JetBrains Mono', monospace; font-size: 11px;
    color: var(--ink); letter-spacing: 0.06em;
  }
  .intake-order .row:last-child { border-bottom: none; }
  .intake-order .row .idx { color: var(--blueprint); }
  .intake-order .row .name { font-family: 'IBM Plex Sans', sans-serif; font-size: 13px; color: var(--ink); letter-spacing: 0; }
  .intake-order .row .pages, .intake-order .row .size, .intake-order .row .stat { color: var(--ink-dim); text-transform: uppercase; letter-spacing: 0.16em; font-size: 10px; }
  .intake-order .row .stat.ok    { color: var(--blueprint); }
  .intake-order .row .stat.fail  { color: var(--vermillion); }

  /* Cap-warning + page-skip notices */
  .notice {
    display: flex; gap: 16px; align-items: flex-start;
    padding: 14px 22px; margin: 0 0 24px 0;
    border: 1px dashed var(--amber); background: rgba(240, 160, 96, 0.06);
    animation: rise 0.5s cubic-bezier(0.16, 1, 0.3, 1) both;
  }
  .notice .icon { color: var(--amber); font-family: 'Fraunces', serif; font-size: 22px; line-height: 1; padding-top: 1px; }
  .notice .ttl  { font-family: 'JetBrains Mono', monospace; font-size: 11px; text-transform: uppercase; letter-spacing: 0.18em; color: var(--amber); margin-bottom: 4px; font-weight: 500; }
  .notice .body { font-family: 'IBM Plex Sans', sans-serif; font-size: 13px; color: var(--ink); line-height: 1.5; }
  .notice.skip   { border-color: var(--vermillion); background: rgba(232, 101, 79, 0.06); }
  .notice.skip .icon, .notice.skip .ttl { color: var(--vermillion); }

  /* Filter + Export bar */
  .filter-bar-head {
    display: flex; justify-content: space-between; align-items: baseline;
    border-top: 1px solid var(--rule); padding: 18px 0 10px 0; margin-top: 8px;
  }
  .filter-bar-head .lbl { font-family: 'JetBrains Mono', monospace; font-size: 10px; text-transform: uppercase; letter-spacing: 0.2em; color: var(--ink-dim); }
  .filter-bar-head .lbl.cyan { color: var(--blueprint); }

  /* Export row label sits above the CSV/PDF download buttons */
  .export-row-head {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.2em;
    color: var(--ink-dim);
    text-align: right;
    margin: 18px 0 6px 0;
    padding-top: 14px;
    border-top: 1px solid var(--rule);
  }

  /* st.radio horizontal (severity filter) — styled as pill row */
  div[data-testid="stRadio"] { margin: 4px 0 18px 0; }
  div[data-testid="stRadio"] > label { display: none !important; }
  div[data-testid="stRadio"] [role="radiogroup"] {
    gap: 0 !important; border: 1px solid var(--rule-strong);
    background: rgba(19, 40, 63, 0.4); display: inline-flex; flex-wrap: wrap;
    padding: 0 !important;
  }
  div[data-testid="stRadio"] [role="radiogroup"] > label {
    background: transparent !important;
    border-right: 1px solid var(--rule) !important;
    margin: 0 !important; padding: 10px 22px !important;
    font-family: 'JetBrains Mono', monospace !important; font-size: 11px !important;
    text-transform: uppercase !important; letter-spacing: 0.18em !important;
    color: var(--ink-dim) !important; transition: all 0.15s !important;
    cursor: pointer; min-height: 0 !important;
  }
  div[data-testid="stRadio"] [role="radiogroup"] > label:last-child { border-right: none !important; }
  div[data-testid="stRadio"] [role="radiogroup"] > label:hover {
    color: var(--ink) !important; background: rgba(127, 203, 227, 0.04) !important;
  }
  /* Hide the actual radio circle */
  div[data-testid="stRadio"] [role="radiogroup"] > label > div:first-child { display: none !important; }
  div[data-testid="stRadio"] [role="radiogroup"] > label > div:last-child { color: inherit !important; }
  div[data-testid="stRadio"] [role="radiogroup"] > label > div:last-child p {
    margin: 0 !important; color: inherit !important;
    font-family: 'JetBrains Mono', monospace !important; font-size: 11px !important;
    text-transform: uppercase !important; letter-spacing: 0.18em !important;
  }
  /* Selected pill: blueprint background, paper text */
  div[data-testid="stRadio"] [role="radiogroup"] > label:has(input:checked) {
    background: var(--blueprint) !important; color: var(--paper) !important;
    font-weight: 500 !important;
  }

  /* st.download_button — match outline-blueprint look */
  [data-testid="stDownloadButton"] button {
    background: transparent !important;
    color: var(--blueprint) !important;
    border: 1px solid var(--blueprint) !important;
    padding: 10px 22px !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 11px !important; text-transform: uppercase !important;
    letter-spacing: 0.2em !important; font-weight: 500 !important;
    border-radius: 0 !important; box-shadow: none !important;
    transition: all 0.18s !important;
  }
  [data-testid="stDownloadButton"] button:hover {
    background: var(--blueprint) !important; color: var(--paper) !important;
    transform: translate(-1px, -1px); box-shadow: 3px 3px 0 var(--paper-2) !important;
  }

  /* Finding-card body with thumbnail (Phase 5) */
  .finding-body.with-thumb {
    display: grid; grid-template-columns: 220px 1fr; gap: 24px;
    align-items: start;
  }
  .thumb-col { display: flex; flex-direction: column; gap: 8px; }
  .thumb-frame {
    border: 1px solid var(--rule-strong); background: #FAF6EA;
    padding: 8px; line-height: 0;
  }
  .thumb-frame img { width: 100%; height: auto; display: block; box-shadow: 0 1px 2px rgba(0, 0, 0, 0.18); }
  .thumb-cap {
    font-family: 'JetBrains Mono', monospace; font-size: 9px;
    color: var(--ink-dim); letter-spacing: 0.18em;
    text-transform: uppercase; text-align: center;
  }
  .thumb-fail {
    border: 1px dashed var(--rule); background: rgba(19, 40, 63, 0.4);
    padding: 18px 12px; text-align: center;
    font-family: 'JetBrains Mono', monospace; font-size: 9px;
    color: var(--ink-dim); letter-spacing: 0.18em;
  }
  .text-col { min-width: 0; }
  .text-col .desc { margin-top: 0; }

  /* Clear-and-start-over zone — muted outline button (Phase 5) */
  #clear-zone-anchor + div .stButton button {
    background: transparent !important;
    color: var(--ink-dim) !important;
    border: 1px solid var(--rule-strong) !important;
    box-shadow: none !important;
    padding: 10px 22px !important;
    font-size: 10px !important;
    letter-spacing: 0.22em !important;
  }
  #clear-zone-anchor + div .stButton button:hover {
    background: rgba(232, 101, 79, 0.08) !important;
    color: var(--vermillion) !important;
    border-color: var(--vermillion) !important;
    transform: none;
    box-shadow: none !important;
  }

  /* About-this-tool expander (Phase 5) */
  [data-testid="stExpander"] {
    border: 1px solid var(--rule-strong) !important;
    border-radius: 0 !important;
    background: rgba(19, 40, 63, 0.92);
    margin: 40px 0 24px 0;
  }
  [data-testid="stExpander"] details summary,
  [data-testid="stExpander"] summary {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 11px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.2em !important;
    color: var(--blueprint) !important;
    padding: 16px 22px !important;
  }
  [data-testid="stExpanderDetails"] {
    padding: 4px 26px 22px 26px !important;
  }
  [data-testid="stExpanderDetails"] p {
    font-family: 'IBM Plex Sans', sans-serif !important;
    font-size: 14px !important;
    line-height: 1.65 !important;
    color: var(--ink) !important;
  }
  [data-testid="stExpanderDetails"] strong { color: var(--blueprint); }
  [data-testid="stExpanderDetails"] ul { color: var(--ink); padding-left: 20px; }
  [data-testid="stExpanderDetails"] li {
    font-family: 'IBM Plex Sans', sans-serif !important;
    font-size: 14px !important; line-height: 1.6 !important;
    margin-bottom: 4px !important;
  }
  [data-testid="stExpanderDetails"] hr {
    border: none; border-top: 1px solid var(--rule);
    margin: 16px 0;
  }

  /* Live preview during audit — sheet currently being reviewed (~8–18s per page) */
  .live-preview {
    display: grid; grid-template-columns: 220px 1fr; gap: 22px;
    align-items: center;
    padding: 18px;
    border: 1px solid var(--blueprint-dim);
    background: rgba(127, 203, 227, 0.04);
    margin: 18px 0 14px 0;
    animation: rise 0.4s cubic-bezier(0.16, 1, 0.3, 1) both, breathe 2.4s ease-in-out infinite;
  }
  @keyframes breathe {
    0%   { box-shadow: 0 0 0 0 rgba(127, 203, 227, 0.0), inset 0 0 0 1px rgba(127, 203, 227, 0.0); border-color: var(--rule-strong); }
    50%  { box-shadow: 0 0 16px 0 rgba(127, 203, 227, 0.18), inset 0 0 0 1px rgba(127, 203, 227, 0.16); border-color: var(--blueprint); }
    100% { box-shadow: 0 0 0 0 rgba(127, 203, 227, 0.0), inset 0 0 0 1px rgba(127, 203, 227, 0.0); border-color: var(--rule-strong); }
  }
  .live-preview-frame {
    background: #FAF6EA; padding: 10px;
    border: 1px solid var(--rule-strong);
    line-height: 0;
    position: relative;
    overflow: hidden;
  }
  .live-preview-frame img { width: 100%; height: auto; display: block; box-shadow: 0 1px 2px rgba(0, 0, 0, 0.18); }
  /* A scanning line that sweeps top-to-bottom across the sheet, like a copier head */
  .live-preview-frame::after {
    content: ""; position: absolute; left: 0; right: 0; top: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent 0%, var(--blueprint) 50%, transparent 100%);
    box-shadow: 0 0 8px var(--blueprint);
    animation: scan 2.6s ease-in-out infinite;
    opacity: 0.85;
  }
  @keyframes scan {
    0%   { top: 0%; opacity: 0; }
    10%  { opacity: 0.85; }
    90%  { opacity: 0.85; }
    100% { top: 100%; opacity: 0; }
  }
  .live-preview-fallback {
    width: 100%; aspect-ratio: 3/4;
    display: flex; align-items: center; justify-content: center;
    color: var(--ink-dim);
    font-family: 'JetBrains Mono', monospace; font-size: 10px;
    text-transform: uppercase; letter-spacing: 0.18em;
  }
  .live-preview-meta { display: flex; flex-direction: column; gap: 8px; }
  .live-preview-eyebrow {
    font-family: 'JetBrains Mono', monospace; font-size: 9px;
    text-transform: uppercase; letter-spacing: 0.22em;
    color: var(--blueprint); opacity: 0.85;
  }
  .live-preview-title {
    font-family: 'Fraunces', serif; font-size: 22px;
    font-weight: 500; color: var(--ink); letter-spacing: -0.01em;
    line-height: 1.15;
  }
  .live-preview-progress {
    font-family: 'JetBrains Mono', monospace; font-size: 10px;
    text-transform: uppercase; letter-spacing: 0.18em;
    color: var(--ink-dim); margin-top: 4px;
  }

  /* st.progress (run-time progress bar) */
  div[data-testid="stProgress"] { margin: 18px 0 22px 0; }
  div[data-testid="stProgress"] > div > div > div {
    background: var(--paper-2) !important; border: 1px solid var(--rule-strong) !important;
    border-radius: 0 !important; height: 10px !important;
  }
  div[data-testid="stProgress"] > div > div > div > div {
    background: var(--blueprint) !important; border-radius: 0 !important;
  }
  div[data-testid="stProgress"] p {
    font-family: 'JetBrains Mono', monospace !important; font-size: 10px !important;
    text-transform: uppercase !important; letter-spacing: 0.18em !important;
    color: var(--ink-dim) !important;
  }

  /* Build register sheet */
  .sheet { border: 1px solid var(--rule-strong); padding: 28px 32px; background: rgba(19, 40, 63, 0.92); margin: 56px 0 24px 0; animation: rise 1s 0.2s cubic-bezier(0.16, 1, 0.3, 1) both; }
  .sheet-head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 18px; padding-bottom: 14px; border-bottom: 1px solid var(--rule); }
  .sheet-head h2 { font-family: 'Fraunces', serif; font-size: 26px; font-weight: 500; margin: 0; color: var(--ink); letter-spacing: -0.01em; }
  .sheet-head .sheet-no { font-family: 'JetBrains Mono', monospace; font-size: 11px; text-transform: uppercase; letter-spacing: 0.16em; color: var(--ink-dim); }

  .phase-row { display: grid; grid-template-columns: 28px 64px 1fr 110px; gap: 18px; align-items: center; padding: 14px 0; border-bottom: 1px dashed var(--rule); }
  .phase-row:last-child { border-bottom: none; }
  .phase-row .tri { font-family: 'Fraunces', serif; font-size: 16px; font-weight: 500; }
  .phase-row .tri.done { color: var(--blueprint); }
  .phase-row .tri.now  { color: var(--vermillion); }
  .phase-row .tri.next { color: var(--ink-dim); opacity: 0.5; }
  .phase-row .num { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--ink-dim); letter-spacing: 0.16em; }
  .phase-row .label { font-family: 'IBM Plex Sans', sans-serif; font-size: 14px; color: var(--ink); }
  .phase-row .label .sub { font-size: 12px; color: var(--ink-dim); margin-left: 8px; }
  .phase-row .status { font-family: 'JetBrains Mono', monospace; font-size: 10px; text-transform: uppercase; letter-spacing: 0.18em; text-align: right; }
  .phase-row .status.done { color: var(--blueprint); }
  .phase-row .status.now  { color: var(--vermillion); }
  .phase-row .status.next { color: var(--ink-dim); opacity: 0.6; }

  .colophon { margin-top: 56px; padding-top: 18px; border-top: 1px solid var(--rule); font-family: 'JetBrains Mono', monospace; font-size: 10px; text-transform: uppercase; letter-spacing: 0.18em; color: var(--ink-dim); display: flex; justify-content: space-between; flex-wrap: wrap; gap: 12px; }
  .colophon .vermillion { color: var(--vermillion); }
</style>
""",
    unsafe_allow_html=True,
)


if "uploader_counter" not in st.session_state:
    st.session_state.uploader_counter = 0

# Project-metadata defaults (Week 1 — Deliverable 2)
for _key, _default in (
    ("project_name", ""),
    ("architect", ""),
    ("jurisdiction", "Cupertino (city + state)"),
    ("set_date", datetime.now().date()),
    # Phase 1 collaboration features — role + persistence
    ("current_role", ROLE_NONE),
    ("current_audit_id", None),
    # Phase 1 Gate 2 — UI mode flags for edit / add
    ("editing_idx", None),       # 1-based index of finding currently in edit mode (or None)
    ("adding_finding", False),   # True if the "Add new finding" form is open
):
    if _key not in st.session_state:
        st.session_state[_key] = _default

# Defensive: if a stale session holds a jurisdiction value that no longer
# exists in JURISDICTION_LABELS (e.g. after the SJ micro-niche narrowing),
# reset to SJ so st.selectbox doesn't error on mount.
if st.session_state.jurisdiction not in JURISDICTION_LABELS:
    st.session_state.jurisdiction = "Cupertino (city + state)"

# Same defensive reset for current_role
if st.session_state.current_role not in ROLE_LABELS:
    st.session_state.current_role = ROLE_NONE


def _project_display_name(max_len: int = 28) -> str:
    name = (st.session_state.get("project_name") or "").strip()
    if not name:
        return "untitled"
    return name if len(name) <= max_len else name[: max_len - 1].rstrip() + "…"


def _jurisdiction_label() -> str:
    j = st.session_state.get("jurisdiction") or "None"
    return j if j != "None" else "No jurisdiction set"


today = datetime.now().strftime("%d %b %Y").upper()


# ─── Session strip (role selector + audit picker) — Phase 1 ────────────────
# Renders at the very top of the page so the user sets context first.
# Role choice gates Edit / Resolve / Add actions on each finding card later on.
# Audit picker loads any previously-saved audit JSON from audits/ folder.

_OPTION_CURRENT = "__current__"


def _format_audit_option(option_value: str) -> str:
    """Render an audit_id as a human-readable label for the picker dropdown."""
    if option_value == _OPTION_CURRENT:
        return "Current session"
    summary = next(
        (a for a in st.session_state.get("_audits_summary_cache", [])
         if a["audit_id"] == option_value),
        None,
    )
    if not summary:
        return option_value
    saved = (summary.get("saved_at") or "")[:16].replace("T", " ")
    counts = f'{summary["total_findings"]} findings'
    if summary.get("resolved_count"):
        counts += f' · {summary["resolved_count"]} resolved'
    return f'{summary["project_name"]}  ·  {saved}  ·  {counts}'


def _on_audit_pick():
    """Callback: load the picked audit into session_state and reset the project fields."""
    pick = st.session_state.get("audit_picker")
    if not pick or pick == _OPTION_CURRENT:
        return
    loaded = load_audit(pick)
    if not loaded:
        return
    fd = normalize_findings_data(loaded)
    st.session_state["findings_data"] = fd
    st.session_state["current_audit_id"] = pick
    # Sync the metadata input fields with the loaded audit
    st.session_state.project_name = loaded.get("project_name", "") or ""
    st.session_state.architect = loaded.get("architect", "") or ""
    j = loaded.get("jurisdiction", "Cupertino (city + state)") or "Cupertino (city + state)"
    st.session_state.jurisdiction = j if j in JURISDICTION_LABELS else "Cupertino (city + state)"
    sd = loaded.get("set_date")
    if sd:
        try:
            st.session_state.set_date = datetime.fromisoformat(sd).date()
        except (ValueError, TypeError):
            pass


def _start_new_audit():
    """Callback: full fresh start — clear findings, reset metadata, force a new file uploader."""
    st.session_state["findings_data"] = None
    st.session_state["current_audit_id"] = None
    st.session_state.uploader_counter = st.session_state.get("uploader_counter", 0) + 1
    st.session_state.project_name = ""
    st.session_state.architect = ""
    st.session_state.jurisdiction = "Cupertino (city + state)"
    st.session_state.set_date = datetime.now().date()
    # Force the audit picker back to "Current session"
    st.session_state["audit_picker"] = _OPTION_CURRENT


# Build the picker options on every script run (cheap — just disk listing)
_audits_summaries = list_audits(limit=25)
st.session_state["_audits_summary_cache"] = _audits_summaries
_audit_options = [_OPTION_CURRENT] + [a["audit_id"] for a in _audits_summaries]

# Initialize the picker key if missing; default = whatever audit is currently loaded,
# or Current session if none. Defensive against stale ids.
_default_pick = st.session_state.get("current_audit_id") or _OPTION_CURRENT
if _default_pick not in _audit_options:
    _default_pick = _OPTION_CURRENT
if "audit_picker" not in st.session_state:
    st.session_state["audit_picker"] = _default_pick

_strip_col_role, _strip_col_audit, _strip_col_btn = st.columns([2, 4, 1.4])
with _strip_col_role:
    st.selectbox(
        "I AM",
        options=ROLE_LABELS,
        key="current_role",
        help="Pick the role that matches your work on this audit. Principal Architect can edit findings and add new ones; Project Architect ticks rectified items.",
    )
with _strip_col_audit:
    st.selectbox(
        "AUDIT",
        options=_audit_options,
        key="audit_picker",
        format_func=_format_audit_option,
        on_change=_on_audit_pick,
        help="Pick a saved audit to view/continue, or stay on Current session to run a new one.",
    )
with _strip_col_btn:
    st.markdown('<div class="session-strip-btn-spacer"></div>', unsafe_allow_html=True)
    st.button(
        "+ Start fresh",
        key="session_strip_new",
        on_click=_start_new_audit,
        help="Clear findings, metadata, and the upload tray to start a brand-new audit.",
    )

st.markdown('<div class="session-strip-rule"></div>', unsafe_allow_html=True)


_tb_project = html.escape(_project_display_name(max_len=22))
_tb_architect = html.escape((st.session_state.get("architect") or "").strip()[:22] or "—")
_tb_jurisdiction = st.session_state.get("jurisdiction") or "None"
_tb_jurisdiction_short = "—" if _tb_jurisdiction == "None" else _tb_jurisdiction.split(" (")[0]
_tb_jurisdiction_short = html.escape(_tb_jurisdiction_short[:22])
_tb_set_date = st.session_state.get("set_date")
_tb_set_date_str = _tb_set_date.strftime("%d %b %Y").upper() if _tb_set_date else today

st.markdown(
    f"""
<div class="titleblock">
  <div class="cell"><span class="label">Project</span><span class="val">{_tb_project}</span></div>
  <div class="cell"><span class="label">Architect</span><span class="val">{_tb_architect}</span></div>
  <div class="cell"><span class="label">Jurisdiction</span><span class="val">{_tb_jurisdiction_short}</span></div>
  <div class="cell"><span class="label">Set Date</span><span class="val">{_tb_set_date_str}</span></div>
</div>

<div class="hero">
  <div>
    <h1>Plan<em>Check</em>.</h1>
    <p class="lead">An AI-assisted auditor for construction permit drawings. Drop in a sheet set; receive a register of the issues an attentive plan reviewer would flag — categorised, evidenced, exportable.</p>
  </div>
  <div class="stamp">
    Project
    <span class="big">{_tb_project}</span>
  </div>
</div>
""",
    unsafe_allow_html=True,
)


api_ok = is_api_key_set()
if not api_ok:
    st.markdown(
        """
<div class="api-banner">
  <span class="icon">⚠</span>
  <div>
    <div class="ttl">OpenAI key not set · plan check disabled</div>
    <div class="body">Open <code>.env</code> in your project folder and replace <code>your_key_here</code> with your real OpenAI API key (starts with <code>sk-</code>). Save the file. The Run Plan Check button will activate on the next interaction — you may need to reload this tab.</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

st.markdown(
    """
<div class="intake-header">
  <span class="num">Project context</span>
  <span class="ttl">Set details first</span>
</div>
""",
    unsafe_allow_html=True,
)
meta_c1, meta_c2, meta_c3, meta_c4 = st.columns([2, 2, 2, 1])
with meta_c1:
    st.text_input(
        "Project name",
        key="project_name",
        placeholder="e.g. 14251 Burns Way Residence",
        help="Required. Appears in the title block, CSV header, and PDF report.",
    )
with meta_c2:
    st.text_input(
        "Architect / firm",
        key="architect",
        placeholder="e.g. Bella Casa Builders",
        help="Optional.",
    )
with meta_c3:
    st.selectbox(
        "Jurisdiction",
        options=JURISDICTION_LABELS,
        key="jurisdiction",
        help="PlanCheck is currently scoped to Cupertino. Audit applies CBC + CRC + Title 24 + Cupertino Municipal Code amendments (CMC §19.28, §14.18, §16.54). Other Bay Area jurisdictions deferred to a later phase.",
    )
with meta_c4:
    st.date_input(
        "Drawing set date",
        key="set_date",
        help="The date stamped on this revision of the drawings.",
    )


st.markdown(
    """
<div class="intake-header" style="margin-top: 32px;">
  <span class="num">Intake</span>
  <span class="ttl">Drawing Tray</span>
</div>
""",
    unsafe_allow_html=True,
)


uploaded_files = st.file_uploader(
    "PDF intake",
    type=["pdf"],
    accept_multiple_files=True,
    label_visibility="collapsed",
    help="Drop one or more construction PDFs here. Multiple files merge in upload order. Stays in memory only — never written to disk.",
    key=f"pdf_uploader_{st.session_state.uploader_counter}",
)


if uploaded_files:
    file_inputs = [
        {"filename": f.name, "bytes": f.getvalue()}
        for f in uploaded_files
    ]
    is_multi = len(file_inputs) > 1
    combined_hash = hashlib.md5(
        b"".join(fi["bytes"] for fi in file_inputs)
    ).hexdigest()

    if is_multi:
        merge_result = _cached_merge(combined_hash, file_inputs)
        pdf_bytes = merge_result["merged_bytes"]
        page_map = merge_result["page_map"]
        per_file_info = merge_result["per_file_info"]
        merge_errors = merge_result["errors"]
        primary_filename = f"{len(file_inputs)} files"
    else:
        pdf_bytes = file_inputs[0]["bytes"]
        page_map = None
        per_file_info = [{
            "filename": file_inputs[0]["filename"],
            "size_bytes": len(pdf_bytes),
            "page_count": 0,  # filled by get_pdf_info below
            "error": None,
        }]
        merge_errors = []
        primary_filename = file_inputs[0]["filename"]

    pdf_hash = combined_hash
    info = _cached_pdf_info(pdf_hash, pdf_bytes) if pdf_bytes else {
        "page_count": 0, "size_mb": 0, "error": "No mergeable PDF content."
    }

    # Fill in page_count for the single-file case so per_file_info is consistent
    if not is_multi and info.get("page_count", 0) > 0:
        per_file_info[0]["page_count"] = info["page_count"]

    if info.get("error") or info.get("page_count", 0) == 0:
        st.error(f"Could not read PDF — {info.get('error') or 'no readable pages'}")
        if merge_errors:
            for err in merge_errors:
                st.error(err)
    else:
        page_count = info["page_count"]
        size_mb = info["size_mb"]
        filename = primary_filename
        display_name = filename if len(filename) <= 42 else filename[:39] + "..."

        if is_multi:
            file_count = len(file_inputs)
            ok_count = sum(1 for pf in per_file_info if pf["error"] is None and pf["page_count"] > 0)
            total_input_size_mb = round(
                sum(pf["size_bytes"] for pf in per_file_info) / (1024 * 1024), 2
            )
            st.markdown(
                f"""
<div class="intake-block">
  <div class="cell"><span class="label">Files</span><span class="val lg">{file_count} merged</span></div>
  <div class="cell"><span class="label">Sheets</span><span class="val cyan">{page_count}</span></div>
  <div class="cell"><span class="label">Size</span><span class="val">{total_input_size_mb} MB</span></div>
  <div class="cell"><span class="label">Loaded</span><span class="val">{datetime.now().strftime("%H:%M:%S")}</span></div>
  <div class="cell"><span class="label">Status</span><span class="val cyan">{ok_count}/{file_count} OK</span></div>
</div>
""",
                unsafe_allow_html=True,
            )

            order_rows = []
            for idx, pf in enumerate(per_file_info, 1):
                stat_class = "ok" if pf["error"] is None and pf["page_count"] > 0 else "fail"
                stat_text = "MERGED" if pf["error"] is None and pf["page_count"] > 0 else "SKIPPED"
                pf_size_mb = round(pf["size_bytes"] / (1024 * 1024), 2)
                pf_pages = pf["page_count"]
                pf_pages_text = f"{pf_pages} sheet{'' if pf_pages == 1 else 's'}" if pf_pages else "—"
                order_rows.append(f"""
<div class="row">
  <span class="idx">{idx:02d}</span>
  <span class="name">{html.escape(_truncate_filename(pf['filename'], 60))}</span>
  <span class="pages">{pf_pages_text}</span>
  <span class="size">{pf_size_mb} MB</span>
  <span class="stat {stat_class}">{stat_text}</span>
</div>
""")
            st.markdown(
                f"""
<div class="intake-order">
  <div class="head">
    <span class="ttl">Intake order · {file_count} files</span>
  </div>
  {"".join(order_rows)}
</div>
""",
                unsafe_allow_html=True,
            )

            if merge_errors:
                first_err = html.escape(merge_errors[0])
                more = f" (+{len(merge_errors) - 1} more)" if len(merge_errors) > 1 else ""
                st.markdown(
                    f"""
<div class="notice skip">
  <span class="icon">!</span>
  <div>
    <div class="ttl">{len(merge_errors)} file{"" if len(merge_errors) == 1 else "s"} could not be merged</div>
    <div class="body">{first_err}{more}. The remaining files were merged and can still be reviewed.</div>
  </div>
</div>
""",
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                f"""
<div class="intake-block">
  <div class="cell"><span class="label">File</span><span class="val lg">{html.escape(display_name)}</span></div>
  <div class="cell"><span class="label">Pages</span><span class="val cyan">{page_count}</span></div>
  <div class="cell"><span class="label">Size</span><span class="val">{size_mb} MB</span></div>
  <div class="cell"><span class="label">Loaded</span><span class="val">{datetime.now().strftime("%H:%M:%S")}</span></div>
  <div class="cell"><span class="label">Status</span><span class="val cyan">Ready</span></div>
</div>
""",
                unsafe_allow_html=True,
            )

        # Multi-page run parameters
        capped = page_count > MAX_PAGES
        pages_to_review = min(page_count, MAX_PAGES)
        # Rough wall-clock estimate: 8s/page lower bound, 18s/page upper bound
        est_low_min = max(1, round(pages_to_review * 8 / 60))
        est_high_min = max(2, round(pages_to_review * 18 / 60))

        if capped:
            st.markdown(
                f"""
<div class="notice">
  <span class="icon">!</span>
  <div>
    <div class="ttl">Sheet count exceeds review cap</div>
    <div class="body">This set has <strong>{page_count}</strong> sheets. To keep runs predictable, only the first <strong>{MAX_PAGES}</strong> will be reviewed. Split the set or remove non-critical sheets to audit the rest.</div>
  </div>
</div>
""",
                unsafe_allow_html=True,
            )

        # Project-metadata gating (Week 1 — Deliverable 2d)
        _project_filled = bool((st.session_state.get("project_name") or "").strip())
        _jurisdiction_chosen = (st.session_state.get("jurisdiction") or "None") != "None"
        metadata_ok = _project_filled and _jurisdiction_chosen

        if pages_to_review == 1:
            btn_label = "Run Plan Check on Sheet 1"
        elif capped:
            btn_label = f"Run Plan Check on first {MAX_PAGES} of {page_count} Sheets"
        else:
            btn_label = f"Run Plan Check on All {page_count} Sheets"

        col_btn, col_meta = st.columns([1, 2])
        with col_btn:
            run_clicked = st.button(
                btn_label,
                type="primary",
                disabled=(not api_ok) or (not metadata_ok),
            )
        with col_meta:
            sheet_word = "sheet" if pages_to_review == 1 else "sheets"
            time_text = f"~{est_low_min}–{est_high_min} min" if pages_to_review > 1 else "~30–60 sec"
            if not api_ok:
                ctx_text = "AI plan check · disabled until OpenAI key is set in .env"
            elif not metadata_ok:
                missing = []
                if not _project_filled:
                    missing.append("Project name")
                if not _jurisdiction_chosen:
                    missing.append("Jurisdiction")
                ctx_text = f"Enter {' and '.join(missing)} above to enable the run"
            else:
                ctx_text = f"AI plan check · {pages_to_review} {sheet_word} · {time_text}"

            # Pre-run references line — what will be applied if Run is clicked
            try:
                _preview_refs = load_references(st.session_state.get("jurisdiction", "None"))
                _ref_summary = references_summary_short(_preview_refs)
                _ref_warn = " · over soft cap" if _preview_refs.get("over_soft_cap") else ""
                ref_line_html = (
                    f'<div style="font-family: \'JetBrains Mono\', monospace; font-size: 10px; '
                    f'text-transform: uppercase; letter-spacing: 0.18em; color: var(--blueprint); '
                    f'padding-top: 6px;">References: {html.escape(_ref_summary)}{_ref_warn}</div>'
                )
            except Exception:
                ref_line_html = ""

            st.markdown(
                f"""
<div style="font-family: 'JetBrains Mono', monospace; font-size: 10px; text-transform: uppercase; letter-spacing: 0.18em; color: var(--ink-dim); padding-top: 22px;">
  {html.escape(ctx_text)}
</div>
{ref_line_html}
""",
                unsafe_allow_html=True,
            )

        if run_clicked:
            preview_slot = st.empty()
            progress_slot = st.empty()
            try:
                progress_widget = progress_slot.progress(
                    0.0, text=f"Preparing review of {pages_to_review} sheet{'' if pages_to_review == 1 else 's'}…"
                )

                def _on_page_start(current: int, total: int) -> None:
                    """Render the sheet about to be reviewed so the user has visual context during the wait."""
                    try:
                        thumb_url = _cached_thumb_url(pdf_hash, pdf_bytes, current, max_dim=420)
                    except Exception:
                        thumb_url = ""
                    if is_multi and page_map:
                        src_file, src_page = _source_for_page(current, page_map, primary_filename)
                        src_label = f"{html.escape(_truncate_filename(src_file, 40))} · P.{src_page:02d}"
                    else:
                        src_label = f"Sheet {current:02d}"
                    img_html = (
                        f'<img src="{thumb_url}" alt="Sheet {current}" />'
                        if thumb_url else
                        '<div class="live-preview-fallback">Rendering preview…</div>'
                    )
                    preview_slot.markdown(
                        f"""
<div class="live-preview">
  <div class="live-preview-frame">{img_html}</div>
  <div class="live-preview-meta">
    <div class="live-preview-eyebrow">AI is now reviewing</div>
    <div class="live-preview-title">{src_label}</div>
    <div class="live-preview-progress">Sheet {current} of {total} · this typically takes 8 to 18 seconds…</div>
  </div>
</div>
""",
                        unsafe_allow_html=True,
                    )
                    progress_widget.progress(
                        max((current - 1) / total, 0.001),
                        text=f"Reading sheet {current} of {total} · sending to AI vision…",
                    )

                def _on_progress(current: int, total: int, found_so_far: int) -> None:
                    pct = current / total if total else 1.0
                    progress_widget.progress(
                        min(pct, 1.0),
                        text=f"Reviewed {current} of {total} sheet{'' if total == 1 else 's'} · {found_so_far} finding{'' if found_so_far == 1 else 's'} so far",
                    )

                _jurisdiction = st.session_state.get("jurisdiction", "None")
                _jurisdiction_addendum = JURISDICTION_PROMPTS.get(_jurisdiction, "")
                _refs = load_references(_jurisdiction)
                # Combine: jurisdictional context first, then user-editable rules.
                _full_addendum = _jurisdiction_addendum
                if _refs["block"]:
                    _full_addendum = (
                        _full_addendum + "\n\n" + _refs["block"]
                        if _full_addendum else _refs["block"]
                    )
                result = review_full_pdf(
                    pdf_bytes,
                    progress_callback=_on_progress,
                    on_page_start=_on_page_start,
                    max_pages=MAX_PAGES,
                    jurisdiction_addendum=_full_addendum,
                )
                preview_slot.empty()
                progress_slot.empty()

                _meta_at_run = {
                    "project_name": st.session_state.get("project_name", ""),
                    "architect": st.session_state.get("architect", ""),
                    "jurisdiction": st.session_state.get("jurisdiction", "None"),
                    "set_date": st.session_state.get("set_date").isoformat() if st.session_state.get("set_date") else "",
                    "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "references_files": [
                        f["name"] for f in _refs["files"]
                        if f.get("exists") and f.get("words", 0) > 0
                    ],
                    "references_word_count": _refs["total_words"],
                }
                _new_findings_data = normalize_findings_data({
                    "hash": pdf_hash,
                    "findings": result["findings"],
                    "page_errors": result["page_errors"],
                    "pages_reviewed": result["pages_reviewed"],
                    "pages_total": result["pages_total"],
                    "capped": result["capped"],
                    "page_map": page_map,
                    "primary_filename": primary_filename,
                    "is_multi": is_multi,
                    "error": None,
                    "ts": datetime.now().strftime("%H:%M:%S"),
                    **_meta_at_run,
                })
                # Phase 1: auto-save to audits/ folder. Failures are silent so
                # an unwritable disk doesn't kill the run — findings still render.
                try:
                    _new_audit_id = save_audit(_new_findings_data)
                    st.session_state["current_audit_id"] = _new_audit_id
                except Exception:
                    _new_audit_id = None

                # Phase 2: persist a JPEG render per finding-bearing page so
                # review mode can re-show annotated sheets + thumbnails without
                # re-uploading the source PDF. Best-effort — silent on failure.
                # NOTE: findings store 1-indexed page_number; render_page_to_image
                # is also 1-indexed, but save_page_image is 0-indexed (matches
                # the on-disk filename `page_<N>.jpg` where N starts at 0).
                if _new_audit_id:
                    try:
                        _pages_with_findings = sorted({
                            int(f["page_number"])
                            for f in _new_findings_data["findings"]
                            if isinstance(f.get("page_number"), int) and f["page_number"] >= 1
                        })
                        for _page_num_1idx in _pages_with_findings:
                            try:
                                _page_img = render_page_to_image(pdf_bytes, _page_num_1idx, dpi=120)
                                save_page_image(_new_audit_id, _page_num_1idx - 1, _page_img)
                            except Exception:
                                continue
                    except Exception:
                        pass

                st.session_state["findings_data"] = _new_findings_data
            except Exception as exc:
                preview_slot.empty()
                progress_slot.empty()
                _meta_at_run = {
                    "project_name": st.session_state.get("project_name", ""),
                    "architect": st.session_state.get("architect", ""),
                    "jurisdiction": st.session_state.get("jurisdiction", "None"),
                    "set_date": st.session_state.get("set_date").isoformat() if st.session_state.get("set_date") else "",
                    "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "references_files": [],
                    "references_word_count": 0,
                }
                st.session_state["findings_data"] = {
                    "hash": pdf_hash,
                    "findings": [],
                    "page_errors": [],
                    "pages_reviewed": 0,
                    "pages_total": page_count,
                    "capped": capped,
                    "page_map": page_map,
                    "primary_filename": primary_filename,
                    "is_multi": is_multi,
                    "error": str(exc),
                    "ts": datetime.now().strftime("%H:%M:%S"),
                    **_meta_at_run,
                }

        # Render previously-loaded findings (persists across reruns within the same upload)
        fd = st.session_state.get("findings_data")
        if fd and fd.get("hash") == pdf_hash:
            if fd.get("error"):
                st.markdown(
                    f"""
<div class="section-head">
  <h3>Findings</h3>
  <span class="tag" style="color: var(--vermillion);">RUN FAILED · {fd["ts"]}</span>
</div>
<div class="api-banner">
  <span class="icon">!</span>
  <div>
    <div class="ttl">Plan check could not complete</div>
    <div class="body">{html.escape(fd["error"])}</div>
  </div>
</div>
""",
                    unsafe_allow_html=True,
                )
            else:
                findings = fd["findings"]
                page_errors = fd.get("page_errors", [])
                pages_reviewed = fd.get("pages_reviewed", 0)
                pages_total = fd.get("pages_total", pages_reviewed)

                sev_counts = {s: 0 for s in SEVERITIES}
                for f in findings:
                    sev_counts[_normalize_severity(f.get("severity"))] += 1

                scope_text = (
                    f"{pages_reviewed} OF {pages_total} SHEET{'' if pages_total == 1 else 'S'}"
                    if pages_total != pages_reviewed
                    else f"{pages_reviewed} SHEET{'' if pages_reviewed == 1 else 'S'}"
                )

                _fd_jurisdiction = fd.get("jurisdiction") or "None"
                _fd_jur_label = "No jurisdiction set" if _fd_jurisdiction == "None" else _fd_jurisdiction
                _fd_refs = fd.get("references_files") or []
                _fd_ref_words = fd.get("references_word_count", 0)
                if _fd_refs:
                    _ref_caption = f"REFERENCES APPLIED · {len(_fd_refs)} FILE{'' if len(_fd_refs) == 1 else 'S'} · {_fd_ref_words:,} WORDS · " + ", ".join(_fd_refs).upper()
                else:
                    _ref_caption = "REFERENCES APPLIED · NONE"
                st.markdown(
                    f"""
<div class="section-head">
  <h3>Findings</h3>
  <span class="tag">AI PLAN CHECK · {html.escape(_fd_jur_label.upper())} · {fd["ts"]} · {scope_text} · {len(findings)} ITEM{"" if len(findings) == 1 else "S"}</span>
</div>
<div style="font-family: 'JetBrains Mono', monospace; font-size: 10px; text-transform: uppercase; letter-spacing: 0.18em; color: var(--blueprint); margin: -22px 0 24px 0; padding-bottom: 12px; border-bottom: 1px dashed var(--rule);">
  {html.escape(_ref_caption)}
</div>

<div class="findings-summary">
  <div class="stat critical"><span class="num">{sev_counts['critical']}</span><span class="lbl">Critical</span></div>
  <div class="stat major"><span class="num">{sev_counts['major']}</span><span class="lbl">Major</span></div>
  <div class="stat minor"><span class="num">{sev_counts['minor']}</span><span class="lbl">Minor</span></div>
  <div class="stat advisory"><span class="num">{sev_counts['advisory']}</span><span class="lbl">Advisory</span></div>
</div>
""",
                    unsafe_allow_html=True,
                )

                # ─── Phase 1 Gate 3 — Resolution-progress row ──────────────
                # Shown only when there's at least one finding. Green bar fills
                # left-to-right as the Project Architect ticks items off.
                _total_for_progress = len(findings)
                _resolved_count = sum(1 for _f in findings if _f.get("resolved"))
                if _total_for_progress > 0:
                    _resolved_pct = round(_resolved_count / _total_for_progress * 100)
                    st.markdown(
                        f"""
<div class="resolution-row">
  <span class="lbl">RESOLVED</span>
  <span class="count">{_resolved_count} <span class="of">of</span> {_total_for_progress}</span>
  <span class="pct">{_resolved_pct}%</span>
  <div class="bar"><div class="bar-fill" style="width:{_resolved_pct}%"></div></div>
</div>
""",
                        unsafe_allow_html=True,
                    )

                # ─── Phase 1 Gate 3 — Distribution charts ───────────────────
                # Two stacked bar charts (severity-colored) using Streamlit's
                # built-in st.bar_chart — no new dependencies. Only the source-file
                # chart is meaningful in multi-file mode; the category chart always
                # shows.
                if findings:
                    try:
                        import altair as _alt
                        import pandas as _pd

                        _chart_rows_cat = []
                        _chart_rows_src = []
                        for _f in findings:
                            _sev = _normalize_severity(_f.get("severity"))
                            _cat_label = (_f.get("category") or "—").replace("_", " ").title()
                            _chart_rows_cat.append({"key": _cat_label, "severity": _sev})
                            if fd.get("is_multi"):
                                _pn = _f.get("page_number")
                                _pm = fd.get("page_map") or []
                                if isinstance(_pn, int) and 0 < _pn <= len(_pm):
                                    _src = _pm[_pn - 1].get("source_file", primary_filename)
                                else:
                                    _src = primary_filename or "—"
                                _chart_rows_src.append({"key": _truncate_filename(_src, 28), "severity": _sev})

                        st.markdown(
                            '<div class="dashboard-head">DISTRIBUTION</div>',
                            unsafe_allow_html=True,
                        )

                        # Explicit severity → color mapping. Using Altair (not st.bar_chart)
                        # so we can SORT the legend by severity instead of alphabetically —
                        # otherwise the legend swaps "advisory" with "critical" etc.
                        _sev_domain = ["critical", "major", "minor", "advisory"]
                        _sev_range  = ["#E8654F", "#F0A060", "#E8C84F", "#7FCBE3"]

                        def _stacked_bar(rows: list[dict], chart_height: int):
                            if not rows:
                                return None
                            _df = _pd.DataFrame(rows)
                            return (
                                _alt.Chart(_df).mark_bar().encode(
                                    y=_alt.Y(
                                        "key:N",
                                        title=None,
                                        sort=_alt.EncodingSortField(
                                            field="key", op="count", order="descending",
                                        ),
                                        axis=_alt.Axis(
                                            labelColor="#EFE6D2",
                                            labelFontSize=11,
                                            labelLimit=200,
                                            domain=False,
                                            ticks=False,
                                        ),
                                    ),
                                    x=_alt.X(
                                        "count():Q",
                                        title=None,
                                        axis=_alt.Axis(
                                            labelColor="#B7AE9A",
                                            labelFontSize=10,
                                            domain=False,
                                            grid=True,
                                            gridColor="rgba(127, 203, 227, 0.10)",
                                            tickCount=6,
                                        ),
                                    ),
                                    color=_alt.Color(
                                        "severity:N",
                                        scale=_alt.Scale(domain=_sev_domain, range=_sev_range),
                                        sort=_sev_domain,
                                        legend=_alt.Legend(
                                            title=None, orient="bottom",
                                            labelColor="#EFE6D2", labelFontSize=11,
                                            symbolStrokeWidth=0, symbolSize=120,
                                        ),
                                    ),
                                    order=_alt.Order(
                                        "severity_order:Q",
                                        sort="ascending",
                                    ),
                                )
                                .transform_calculate(
                                    severity_order="indexof(['critical','major','minor','advisory'], datum.severity)"
                                )
                                .properties(height=chart_height, background="transparent")
                                .configure_view(strokeWidth=0)
                            )

                        if fd.get("is_multi") and _chart_rows_src:
                            _unique_src = len({r["key"] for r in _chart_rows_src})
                            _src_chart = _stacked_bar(
                                _chart_rows_src,
                                max(140, 32 * _unique_src + 80),
                            )
                            if _src_chart is not None:
                                st.markdown(
                                    '<div class="dashboard-subhead">By source file</div>',
                                    unsafe_allow_html=True,
                                )
                                st.altair_chart(_src_chart, use_container_width=True)

                        if _chart_rows_cat:
                            _unique_cat = len({r["key"] for r in _chart_rows_cat})
                            _cat_chart = _stacked_bar(
                                _chart_rows_cat,
                                max(140, 32 * _unique_cat + 80),
                            )
                            if _cat_chart is not None:
                                st.markdown(
                                    '<div class="dashboard-subhead">By category</div>',
                                    unsafe_allow_html=True,
                                )
                                st.altair_chart(_cat_chart, use_container_width=True)
                    except Exception as _chart_exc:
                        # Charts are nice-to-have — never let them block the rest of the audit
                        st.markdown(
                            f'<div class="dashboard-head" style="color: var(--ink-dim); opacity: 0.5;">'
                            f'distribution charts unavailable ({html.escape(str(_chart_exc)[:80])})'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                if page_errors:
                    if fd.get("is_multi"):
                        skipped_pages = ", ".join(
                            f"{_truncate_filename(_source_for_page(pe['page'], fd.get('page_map'), fd.get('primary_filename') or '')[0], 24)} P.{_source_for_page(pe['page'], fd.get('page_map'), fd.get('primary_filename') or '')[1]:02d}"
                            for pe in page_errors
                        )
                    else:
                        skipped_pages = ", ".join(str(pe["page"]) for pe in page_errors)
                    first_error = html.escape(page_errors[0]["error"])
                    skip_word = "sheet" if len(page_errors) == 1 else "sheets"
                    st.markdown(
                        f"""
<div class="notice skip">
  <span class="icon">!</span>
  <div>
    <div class="ttl">{len(page_errors)} {skip_word} skipped due to errors</div>
    <div class="body">Sheet{"" if len(page_errors) == 1 else "s"} {skipped_pages} could not be reviewed and are not included in the findings below. First error: <em>{first_error}</em></div>
  </div>
</div>
""",
                        unsafe_allow_html=True,
                    )

                if not findings:
                    st.markdown(
                        """
<div class="empty-findings">
  <div class="ttl">"No issues flagged across this set."</div>
  <div class="sub">Either this drawing is unusually clean, or the sheets do not contain the kind of detail the model can audit. Try another set.</div>
</div>
""",
                        unsafe_allow_html=True,
                    )
                else:
                    # Annotated Sheets overview — every unique sheet that has findings,
                    # rendered larger with all its severity-colored pins.
                    pages_with_findings: list[int] = []
                    seen_pages: set[int] = set()
                    for f in findings:
                        pn = f.get("page_number")
                        if isinstance(pn, int) and pn > 0 and pn not in seen_pages:
                            seen_pages.add(pn)
                            pages_with_findings.append(pn)
                    pages_with_findings.sort()

                    if pages_with_findings:
                        st.markdown(
                            f"""
<div class="section-head" style="margin-top: 8px;">
  <h3>Annotated sheets</h3>
  <span class="tag">{len(pages_with_findings)} SHEET{"" if len(pages_with_findings) == 1 else "S"} WITH FINDINGS · PINS COLOURED BY SEVERITY</span>
</div>
""",
                            unsafe_allow_html=True,
                        )

                        annotated_cards = ['<div class="annotated-grid">']
                        for pn in pages_with_findings:
                            page_pins = _pins_for_page(findings, pn)
                            try:
                                sheet_url = _cached_annotated_sheet_url(
                                    pdf_hash, pdf_bytes, pn, page_pins
                                )
                                img_block = f'<div class="annotated-image"><img src="{sheet_url}" alt="Sheet {pn} annotated" /></div>'
                            except Exception as exc:
                                img_block = f'<div class="annotated-image fail">Render failed: {html.escape(str(exc)[:120])}</div>'

                            # Severity breakdown for this sheet
                            sev_for_page = {s: 0 for s in SEVERITIES}
                            for f in findings:
                                if f.get("page_number") == pn:
                                    sev_for_page[_normalize_severity(f.get("severity"))] += 1
                            sev_dots = []
                            sev_dot_classes = {"critical": "vermillion", "major": "amber", "minor": "ochre", "advisory": "blueprint"}
                            for s in SEVERITIES:
                                if sev_for_page[s] > 0:
                                    sev_dots.append(
                                        f'<span class="sev-dot sev-{sev_dot_classes[s]}">{sev_for_page[s]} {s.title()}</span>'
                                    )
                            sev_html = " · ".join(sev_dots) if sev_dots else ""

                            # Source-aware title
                            if fd.get("is_multi"):
                                src_file, src_page = _source_for_page(
                                    pn, fd.get("page_map"), fd.get("primary_filename") or "",
                                )
                                head_left = f"{html.escape(_truncate_filename(src_file, 28))} · P.{src_page:02d}"
                            else:
                                head_left = f"SHT {pn:02d}"

                            n_findings_here = sum(1 for f in findings if f.get("page_number") == pn)
                            annotated_cards.append(
                                f"""
<div class="annotated-card">
  <div class="annotated-head">
    <span class="annotated-name">{head_left}</span>
    <span class="annotated-count">{n_findings_here} FINDING{"" if n_findings_here == 1 else "S"}</span>
  </div>
  {img_block}
  <div class="annotated-foot">{sev_html}</div>
</div>
"""
                            )
                        annotated_cards.append("</div>")
                        st.markdown("\n".join(annotated_cards), unsafe_allow_html=True)

                    # Filter row (full width)
                    st.markdown(
                        f"""
<div class="filter-bar-head">
  <span class="lbl cyan">Filter by severity</span>
  <span class="lbl">{len(findings)} total finding{"" if len(findings) == 1 else "s"}</span>
</div>
""",
                        unsafe_allow_html=True,
                    )
                    filter_choice = st.radio(
                        "Severity filter",
                        options=list(FILTER_LABELS),
                        index=0,
                        horizontal=True,
                        label_visibility="collapsed",
                        key=f"sev_filter_{pdf_hash[:8]}",
                    )
                    # Export row (right-aligned on its own line below the filter)
                    st.markdown(
                        '<div class="export-row-head">EXPORT</div>',
                        unsafe_allow_html=True,
                    )
                    _, col_export_csv, col_export_pdf = st.columns([3, 1.5, 1.5])
                    _meta_for_export = {
                        "project_name": fd.get("project_name", ""),
                        "architect": fd.get("architect", ""),
                        "jurisdiction": fd.get("jurisdiction", ""),
                        "set_date": fd.get("set_date", ""),
                        "generated_at": fd.get("generated_at", ""),
                        "references_files": fd.get("references_files") or [],
                        "references_word_count": fd.get("references_word_count", 0),
                    }
                    _ts_stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                    _export_stem = _safe_filename_stem(filename)

                    with col_export_csv:
                        csv_text = _build_findings_csv(
                            findings,
                            fd.get("page_map"),
                            fd.get("primary_filename") or filename,
                            meta=_meta_for_export,
                        )
                        st.download_button(
                            label="Download CSV",
                            data=csv_text,
                            file_name=f"plancheck_{_export_stem}_{_ts_stamp}.csv",
                            mime="text/csv",
                            key=f"dl_csv_{pdf_hash[:8]}",
                        )

                    with col_export_pdf:
                        # Build PIL.Image providers backed by the on-disk PDF bytes
                        # and the existing pin tuples. Lazy lambdas so the heavy
                        # rendering only happens when ReportLab actually requests
                        # an image during build_report.
                        def _annotated_sheet_for_pdf(page_num: int):
                            page_pins = _pins_for_page(findings, page_num)
                            pin_dicts = [{"label": p[0], "region": p[1], "severity": p[2]} for p in page_pins]
                            img = render_page_to_image(pdf_bytes, page_num, dpi=120)
                            return annotate_sheet(img, pin_dicts) if pin_dicts else img

                        def _finding_thumb_for_pdf(page_num: int):
                            page_pins = _pins_for_page(findings, page_num)
                            pin_dicts = [{"label": p[0], "region": p[1], "severity": p[2]} for p in page_pins]
                            img = render_page_to_image(pdf_bytes, page_num, dpi=72)
                            return annotate_sheet(img, pin_dicts) if pin_dicts else img

                        if st.button(
                            "Download PDF report",
                            key=f"dl_pdf_btn_{pdf_hash[:8]}",
                            help="Builds a multi-page PDF with cover, annotated sheets, findings register, and disclaimer. Takes a few seconds for large sets.",
                        ):
                            with st.spinner("Building PDF report…"):
                                try:
                                    pdf_bytes_report = build_report(
                                        findings=findings,
                                        meta=_meta_for_export,
                                        page_map=fd.get("page_map"),
                                        fallback_filename=fd.get("primary_filename") or filename,
                                        annotated_sheet_provider=_annotated_sheet_for_pdf,
                                        finding_thumb_provider=_finding_thumb_for_pdf,
                                    )
                                    st.session_state[f"pdf_report_{pdf_hash[:8]}"] = pdf_bytes_report
                                except Exception as exc:
                                    st.error(f"PDF generation failed: {exc}")

                        _pdf_bytes_cached = st.session_state.get(f"pdf_report_{pdf_hash[:8]}")
                        if _pdf_bytes_cached:
                            st.download_button(
                                label="Save PDF",
                                data=_pdf_bytes_cached,
                                file_name=f"plancheck_{_export_stem}_{_ts_stamp}.pdf",
                                mime="application/pdf",
                                key=f"dl_pdf_save_{pdf_hash[:8]}",
                            )

                    active_filter = (filter_choice or "All").lower()
                    severity_order = {"critical": 0, "major": 1, "minor": 2, "advisory": 3}
                    indexed = list(enumerate(findings, 1))
                    if active_filter != "all":
                        indexed = [
                            (idx, f) for (idx, f) in indexed
                            if _normalize_severity(f.get("severity")) == active_filter
                        ]
                    sorted_findings = sorted(
                        indexed,
                        key=lambda pair: (
                            severity_order.get(_normalize_severity(pair[1].get("severity")), 99),
                            1 if pair[1].get("resolved") else 0,  # resolved sinks to bottom of bucket
                            _page_sort_value(pair[1].get("page_number")),
                            pair[0],
                        ),
                    )

                    _role = st.session_state.get("current_role", ROLE_NONE)
                    _is_principal = _role == ROLE_PRINCIPAL
                    _is_project_arch = _role == ROLE_PROJECT

                    # Add-new-finding section (Principal only) — sits above the stack
                    if _is_principal:
                        if st.session_state.get("adding_finding"):
                            with st.form("add_finding_form", clear_on_submit=True):
                                st.markdown('<div class="form-eyebrow">+ NEW FINDING</div>', unsafe_allow_html=True)
                                _add_c1, _add_c2 = st.columns([1, 1])
                                with _add_c1:
                                    _add_severity = st.selectbox("Severity", list(SEVERITIES), index=1, key="add_severity")
                                with _add_c2:
                                    _add_category = st.selectbox(
                                        "Category",
                                        ["code", "drawing_error", "coordination", "constructability"],
                                        key="add_category",
                                    )
                                _add_desc = st.text_area("Description (one sentence)", key="add_desc", height=70)
                                _add_evidence = st.text_area("Evidence (what you see on the drawing)", key="add_evidence", height=70)
                                _add_rec = st.text_area("Recommendation (what the architect should do)", key="add_rec", height=70)
                                _add_p1, _add_p2 = st.columns([1, 1])
                                with _add_p1:
                                    _add_page = st.number_input(
                                        "Sheet number",
                                        min_value=1,
                                        max_value=max(1, fd.get("pages_total", 1)),
                                        value=1,
                                        step=1,
                                        key="add_page",
                                    )
                                with _add_p2:
                                    _add_region = st.selectbox(
                                        "Pin location (3×3 zone)",
                                        ["top-left", "top-center", "top-right",
                                         "center-left", "center", "center-right",
                                         "bottom-left", "bottom-center", "bottom-right",
                                         "full-sheet"],
                                        index=4,
                                        key="add_region",
                                    )
                                _add_assign = st.selectbox(
                                    "Assign to",
                                    list(ROLE_ASSIGNABLE),
                                    index=0,
                                    key="add_assign",
                                    help="Direct this finding at a teammate. They'll see an 'ASSIGNED · …' tag on the card and a 'For you' highlight when their role is selected.",
                                )
                                _add_save_col, _add_cancel_col, _spacer = st.columns([1, 1, 4])
                                with _add_save_col:
                                    _add_save = st.form_submit_button("Save finding", type="primary")
                                with _add_cancel_col:
                                    _add_cancel = st.form_submit_button("Cancel")
                                if _add_save and (_add_desc or "").strip():
                                    _save_new_finding(
                                        _add_severity, _add_category,
                                        _add_desc, _add_evidence, _add_rec,
                                        int(_add_page), _add_region,
                                        assigned_to=_add_assign,
                                    )
                                    st.rerun()
                                elif _add_cancel:
                                    _cancel_add()
                                    st.rerun()
                        else:
                            st.markdown('<div id="add-finding-anchor"></div>', unsafe_allow_html=True)
                            if st.button("+  Add new finding", key="add_finding_btn", on_click=_start_adding):
                                pass

                    if not sorted_findings:
                        st.markdown(
                            f"""
<div class="empty-findings">
  <div class="ttl">"No {html.escape(active_filter)} findings."</div>
  <div class="sub">Switch the filter back to All to see every finding.</div>
</div>
""",
                            unsafe_allow_html=True,
                        )
                    else:
                        # Per-finding render: HTML card → optional Streamlit widgets below.
                        # Each finding is its own block so widgets sit immediately under their card.
                        for original_idx, f in sorted_findings:
                            sev = _normalize_severity(f.get("severity"))
                            cat = (f.get("category") or "—").replace("_", " ").upper()
                            desc = html.escape(f.get("description") or "(no description)")
                            evidence = html.escape(f.get("evidence") or "—")
                            recommendation = html.escape(f.get("recommendation") or "—")
                            page_num = f.get("page_number")
                            if page_num == "multiple":
                                # Cross-sheet coordination finding — no single page; no thumb.
                                page_badge = _cross_sheet_badge_html(f)
                                thumb_caption = ""
                            elif fd.get("is_multi") and isinstance(page_num, int) and page_num > 0:
                                src_file, src_page = _source_for_page(
                                    page_num, fd.get("page_map"), fd.get("primary_filename") or "",
                                )
                                page_badge = (
                                    f'<span class="badge src">{html.escape(_truncate_filename(src_file, 32))}'
                                    f'<span class="src-page">P.{src_page:02d}</span></span>'
                                )
                                thumb_caption = f"{_truncate_filename(src_file, 22)} · P.{src_page:02d}"
                            else:
                                page_badge = (
                                    f'<span class="badge pg">SHT {page_num:02d}</span>'
                                    if isinstance(page_num, int) and page_num > 0
                                    else ""
                                )
                                thumb_caption = (
                                    f"SHT {page_num:02d} · context"
                                    if isinstance(page_num, int) and page_num > 0
                                    else ""
                                )

                            # Page thumbnail with pin overlay — graceful fallback
                            thumb_html = ""
                            if isinstance(page_num, int) and page_num > 0:
                                try:
                                    page_pins = _pins_for_page(findings, page_num)
                                    if page_pins:
                                        thumb_url = _cached_annotated_thumb_url(
                                            pdf_hash, pdf_bytes, page_num, page_pins
                                        )
                                    else:
                                        thumb_url = _cached_thumb_url(pdf_hash, pdf_bytes, page_num)
                                    pin_count_caption = (
                                        f" · {len(page_pins)} pin{'' if len(page_pins) == 1 else 's'}"
                                        if page_pins else ""
                                    )
                                    thumb_html = f"""
<div class="thumb-col">
  <div class="thumb-frame"><img src="{thumb_url}" alt="Sheet {page_num}" /></div>
  <div class="thumb-cap">{html.escape(thumb_caption)}{pin_count_caption}</div>
</div>"""
                                except Exception:
                                    thumb_html = """
<div class="thumb-col">
  <div class="thumb-fail">Preview unavailable</div>
</div>"""

                            body_class = "finding-body with-thumb" if thumb_html else "finding-body"
                            text_open = '<div class="text-col">' if thumb_html else ""
                            text_close = "</div>" if thumb_html else ""

                            # Status tags (resolved / edited / added / assigned) appear in the card header
                            status_tags = []
                            if f.get("manually_added"):
                                status_tags.append('<span class="status-tag added">+ ADDED</span>')
                            if f.get("edited"):
                                status_tags.append('<span class="status-tag edited">EDITED</span>')
                            if f.get("resolved"):
                                status_tags.append('<span class="status-tag resolved">✓ RESOLVED</span>')
                            _assigned_to = f.get("assigned_to")
                            _is_for_me = bool(_assigned_to and _assigned_to == _role and _role != ROLE_NONE)
                            if _assigned_to:
                                if _is_for_me:
                                    status_tags.append('<span class="status-tag foryou">★ FOR YOU</span>')
                                else:
                                    status_tags.append(
                                        f'<span class="status-tag assigned">→ ASSIGNED · {html.escape(_assigned_to.upper())}</span>'
                                    )
                            status_tags_html = " ".join(status_tags)

                            resolved_class = " resolved" if f.get("resolved") else ""
                            foryou_class = " foryou" if _is_for_me else ""

                            # If this finding is in edit mode (Principal clicked Edit on it),
                            # replace the card body with an inline edit form. The card head
                            # stays so the user knows which finding they're editing.
                            if st.session_state.get("editing_idx") == original_idx and _is_principal:
                                # Render the head + form (no body).
                                # IMPORTANT: status_tags_html on the same line as the cat span — a blank line
                                # would make Streamlit's markdown parser escape the trailing <span class="no">.
                                st.markdown(f"""
<div class="finding finding-{sev} editing">
  <div class="finding-head">
    <span class="badge badge-{sev}">{sev.upper()}</span>
    {page_badge}
    <span class="cat">{html.escape(cat)}</span> {status_tags_html} <span class="no">EDITING FND-{original_idx:02d}</span>
  </div>
</div>
""", unsafe_allow_html=True)
                                with st.form(f"edit_form_{original_idx}", clear_on_submit=False):
                                    _edit_severity = st.selectbox(
                                        "Severity",
                                        list(SEVERITIES),
                                        index=list(SEVERITIES).index(sev),
                                        key=f"edit_severity_{original_idx}",
                                    )
                                    _edit_desc = st.text_area(
                                        "Description",
                                        value=f.get("description", "") or "",
                                        height=80,
                                        key=f"edit_desc_{original_idx}",
                                    )
                                    _edit_evidence = st.text_area(
                                        "Evidence",
                                        value=f.get("evidence", "") or "",
                                        height=80,
                                        key=f"edit_evidence_{original_idx}",
                                    )
                                    _edit_rec = st.text_area(
                                        "Recommendation",
                                        value=f.get("recommendation", "") or "",
                                        height=80,
                                        key=f"edit_rec_{original_idx}",
                                    )
                                    _current_assignee = f.get("assigned_to") or ASSIGN_UNASSIGNED
                                    _assign_idx = (
                                        list(ROLE_ASSIGNABLE).index(_current_assignee)
                                        if _current_assignee in ROLE_ASSIGNABLE else 0
                                    )
                                    _edit_assign = st.selectbox(
                                        "Assign to",
                                        list(ROLE_ASSIGNABLE),
                                        index=_assign_idx,
                                        key=f"edit_assign_{original_idx}",
                                        help="Direct this finding at a teammate. They'll see an 'ASSIGNED · …' tag on the card and a 'For you' highlight when their role is selected.",
                                    )
                                    _save_col, _cancel_col, _ = st.columns([1, 1, 4])
                                    with _save_col:
                                        _save_btn = st.form_submit_button("Save changes", type="primary")
                                    with _cancel_col:
                                        _cancel_btn = st.form_submit_button("Cancel")
                                    if _save_btn:
                                        _save_edit(
                                            original_idx, _edit_severity, _edit_desc,
                                            _edit_evidence, _edit_rec,
                                            assigned_to=_edit_assign,
                                        )
                                        st.rerun()
                                    elif _cancel_btn:
                                        _cancel_edit()
                                        st.rerun()
                            else:
                                # Normal card render.
                                # IMPORTANT: status_tags_html on the same line as the cat span — a blank line
                                # would make Streamlit's markdown parser escape the trailing <span class="no">.
                                st.markdown(f"""
<div class="finding finding-{sev}{resolved_class}{foryou_class}">
  <div class="finding-head">
    <span class="badge badge-{sev}">{sev.upper()}</span>
    {page_badge}
    <span class="cat">{html.escape(cat)}</span> {status_tags_html} <span class="no">FND-{original_idx:02d}</span>
  </div>
  <div class="{body_class}">
    {thumb_html}
    {text_open}
    <p class="desc">{desc}</p>
    <div class="kv">
      <span class="k">Evidence</span>
      <p class="v">{evidence}</p>
    </div>
    <div class="kv">
      <span class="k">Recommendation</span>
      <p class="v">{recommendation}</p>
    </div>
    {text_close}
  </div>
</div>
""", unsafe_allow_html=True)

                                # Action row below the card — Edit (Principal) or Resolve (Project Architect)
                                if _is_principal:
                                    _edit_col, _spacer = st.columns([1, 6])
                                    with _edit_col:
                                        st.button(
                                            "✎  Edit",
                                            key=f"edit_btn_{original_idx}",
                                            on_click=_start_editing,
                                            args=(original_idx,),
                                        )
                                elif _is_project_arch:
                                    st.checkbox(
                                        "Resolved" if not f.get("resolved") else "Resolved ✓",
                                        value=bool(f.get("resolved")),
                                        key=f"resolve_{original_idx}",
                                        on_change=_toggle_resolved,
                                        args=(original_idx,),
                                    )

        # Clear-and-start-over (Phase 5) — resets the uploader by bumping its key
        st.markdown('<div id="clear-zone-anchor"></div>', unsafe_allow_html=True)
        if st.button("◯  Clear and start over", key="clear_btn"):
            st.session_state.uploader_counter += 1
            st.session_state.pop("findings_data", None)
            # Reset project metadata (Week 1 — Deliverable 2g)
            st.session_state.project_name = ""
            st.session_state.architect = ""
            st.session_state.jurisdiction = "Cupertino (city + state)"
            st.session_state.set_date = datetime.now().date()
            for k in list(st.session_state.keys()):
                if k.startswith("sev_filter_") or k.startswith("dl_csv_"):
                    del st.session_state[k]
            st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# Review mode — past audit loaded but source PDF not uploaded.
# Renders findings text + dashboard + edit/resolve/add UI without thumbnails.
# Skips annotated-sheets section and PDF-report download (both require pdf_bytes
# for image rendering). User sees a small banner explaining this.
# ════════════════════════════════════════════════════════════════════════════
_rv_fd = st.session_state.get("findings_data")
_rv_audit_id = st.session_state.get("current_audit_id")
if (not uploaded_files) and _rv_fd and _rv_audit_id and not _rv_fd.get("error"):
    findings = _rv_fd.get("findings") or []
    _rv_page_map = _rv_fd.get("page_map")
    _rv_primary = _rv_fd.get("primary_filename") or "(unknown)"
    _rv_is_multi = bool(_rv_fd.get("is_multi"))
    pdf_hash = _rv_fd.get("hash", _rv_audit_id)  # used for widget keys

    # Banner: explain the limited mode
    _rv_total = len(findings)
    _rv_resolved = sum(1 for _f in findings if _f.get("resolved"))

    # Phase 2: detect whether saved page renders exist for this audit. Pages
    # are 1-indexed in findings; on disk they're 0-indexed.
    _rv_unique_pages: list[int] = []
    _seen_pages: set[int] = set()
    for _f in findings:
        _pn = _f.get("page_number")
        if isinstance(_pn, int) and _pn > 0 and _pn not in _seen_pages:
            _seen_pages.add(_pn)
            _rv_unique_pages.append(_pn)
    _rv_unique_pages.sort()
    _rv_pages_with_images = [
        pn for pn in _rv_unique_pages if has_page_image(_rv_audit_id, pn - 1)
    ]
    _rv_has_assets = len(_rv_pages_with_images) > 0

    if _rv_has_assets:
        # Modern audit (Phase 2+) — JPEGs saved alongside JSON. Visuals work.
        st.markdown(
            f"""
<div class="notice" style="margin-top: 24px;">
  <span class="icon">◐</span>
  <div>
    <div class="ttl">Reviewing past audit — <strong>{html.escape(_rv_audit_id)}</strong></div>
    <div class="body">Annotated sheets and per-finding thumbnails are loaded from disk; edits and resolve-marks save back automatically.
    Re-upload the source PDF (was <strong>{html.escape(_rv_primary)}</strong>) into the Drawing Tray above only if you want the PDF report download.</div>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )
    else:
        # Legacy audit (saved before Phase 2) — no JPEGs on disk.
        st.markdown(
            f"""
<div class="notice" style="margin-top: 24px;">
  <span class="icon">!</span>
  <div>
    <div class="ttl">Reviewing past audit — limited mode (legacy audit, no saved page renders)</div>
    <div class="body">You picked <strong>{html.escape(_rv_audit_id)}</strong> from the AUDIT dropdown.
    Findings, edits, and resolve-marks all work below.
    <strong>This audit was saved before visual persistence shipped, so annotated sheets and thumbnails are unavailable</strong>
    — re-upload the source PDF (was <strong>{html.escape(_rv_primary)}</strong>) into the Drawing Tray above to regenerate them, or re-run the audit to bake them in.</div>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )

    # ─── Findings header + REFERENCES APPLIED caption ─────────────────────
    _rv_jurisdiction = _rv_fd.get("jurisdiction") or "None"
    _rv_jur_label = "No jurisdiction set" if _rv_jurisdiction == "None" else _rv_jurisdiction
    _rv_refs = _rv_fd.get("references_files") or []
    _rv_ref_words = _rv_fd.get("references_word_count", 0)
    if _rv_refs:
        _rv_ref_caption = f"REFERENCES APPLIED · {len(_rv_refs)} FILE{'' if len(_rv_refs) == 1 else 'S'} · {_rv_ref_words:,} WORDS · " + ", ".join(_rv_refs).upper()
    else:
        _rv_ref_caption = "REFERENCES APPLIED · NONE"

    _rv_pages_reviewed = _rv_fd.get("pages_reviewed", 0)
    _rv_pages_total = _rv_fd.get("pages_total", _rv_pages_reviewed)
    _rv_scope = (
        f"{_rv_pages_reviewed} OF {_rv_pages_total} SHEET{'' if _rv_pages_total == 1 else 'S'}"
        if _rv_pages_total != _rv_pages_reviewed
        else f"{_rv_pages_reviewed} SHEET{'' if _rv_pages_reviewed == 1 else 'S'}"
    )

    _rv_sev_counts = {s: 0 for s in SEVERITIES}
    for _f in findings:
        _rv_sev_counts[_normalize_severity(_f.get("severity"))] += 1

    st.markdown(
        f"""
<div class="section-head">
  <h3>Findings</h3>
  <span class="tag">AI PLAN CHECK · {html.escape(_rv_jur_label.upper())} · {_rv_fd.get("ts", "")} · {html.escape(_rv_scope)} · {_rv_total} ITEM{"" if _rv_total == 1 else "S"}</span>
</div>
<div style="font-family: 'JetBrains Mono', monospace; font-size: 10px; text-transform: uppercase; letter-spacing: 0.18em; color: var(--blueprint); margin: -22px 0 24px 0; padding-bottom: 12px; border-bottom: 1px dashed var(--rule);">
  {html.escape(_rv_ref_caption)}
</div>

<div class="findings-summary">
  <div class="stat critical"><span class="num">{_rv_sev_counts['critical']}</span><span class="lbl">Critical</span></div>
  <div class="stat major"><span class="num">{_rv_sev_counts['major']}</span><span class="lbl">Major</span></div>
  <div class="stat minor"><span class="num">{_rv_sev_counts['minor']}</span><span class="lbl">Minor</span></div>
  <div class="stat advisory"><span class="num">{_rv_sev_counts['advisory']}</span><span class="lbl">Advisory</span></div>
</div>
""",
        unsafe_allow_html=True,
    )

    # ─── Resolution-progress row ──────────────────────────────────────────
    if _rv_total > 0:
        _rv_pct = round(_rv_resolved / _rv_total * 100)
        st.markdown(
            f"""
<div class="resolution-row">
  <span class="lbl">RESOLVED</span>
  <span class="count">{_rv_resolved} <span class="of">of</span> {_rv_total}</span>
  <span class="pct">{_rv_pct}%</span>
  <div class="bar"><div class="bar-fill" style="width:{_rv_pct}%"></div></div>
</div>
""",
            unsafe_allow_html=True,
        )

    # ─── Distribution charts (works without PDF) ──────────────────────────
    if findings:
        try:
            import altair as _alt
            import pandas as _pd
            _rv_chart_cat = []
            _rv_chart_src = []
            for _f in findings:
                _sev = _normalize_severity(_f.get("severity"))
                _cat_label = (_f.get("category") or "—").replace("_", " ").title()
                _rv_chart_cat.append({"key": _cat_label, "severity": _sev})
                if _rv_is_multi:
                    _pn = _f.get("page_number")
                    _pm = _rv_page_map or []
                    if isinstance(_pn, int) and 0 < _pn <= len(_pm):
                        _src = _pm[_pn - 1].get("source_file", _rv_primary)
                    else:
                        _src = _rv_primary
                    _rv_chart_src.append({"key": _truncate_filename(_src, 28), "severity": _sev})

            st.markdown('<div class="dashboard-head">DISTRIBUTION</div>', unsafe_allow_html=True)

            _sev_dom = ["critical", "major", "minor", "advisory"]
            _sev_rng = ["#E8654F", "#F0A060", "#E8C84F", "#7FCBE3"]

            def _rv_stacked_bar(rows, h):
                if not rows:
                    return None
                _df = _pd.DataFrame(rows)
                return (
                    _alt.Chart(_df).mark_bar().encode(
                        y=_alt.Y("key:N", title=None,
                                 sort=_alt.EncodingSortField(field="key", op="count", order="descending"),
                                 axis=_alt.Axis(labelColor="#EFE6D2", labelFontSize=11, labelLimit=200, domain=False, ticks=False)),
                        x=_alt.X("count():Q", title=None,
                                 axis=_alt.Axis(labelColor="#B7AE9A", labelFontSize=10, domain=False, grid=True,
                                                gridColor="rgba(127, 203, 227, 0.10)", tickCount=6)),
                        color=_alt.Color("severity:N",
                                         scale=_alt.Scale(domain=_sev_dom, range=_sev_rng),
                                         sort=_sev_dom,
                                         legend=_alt.Legend(title=None, orient="bottom",
                                                            labelColor="#EFE6D2", labelFontSize=11,
                                                            symbolStrokeWidth=0, symbolSize=120)),
                        order=_alt.Order("severity_order:Q", sort="ascending"),
                    )
                    .transform_calculate(severity_order="indexof(['critical','major','minor','advisory'], datum.severity)")
                    .properties(height=h, background="transparent")
                    .configure_view(strokeWidth=0)
                )

            if _rv_is_multi and _rv_chart_src:
                _u = len({r["key"] for r in _rv_chart_src})
                _c = _rv_stacked_bar(_rv_chart_src, max(140, 32 * _u + 80))
                if _c is not None:
                    st.markdown('<div class="dashboard-subhead">By source file</div>', unsafe_allow_html=True)
                    st.altair_chart(_c, use_container_width=True)
            if _rv_chart_cat:
                _u = len({r["key"] for r in _rv_chart_cat})
                _c = _rv_stacked_bar(_rv_chart_cat, max(140, 32 * _u + 80))
                if _c is not None:
                    st.markdown('<div class="dashboard-subhead">By category</div>', unsafe_allow_html=True)
                    st.altair_chart(_c, use_container_width=True)
        except Exception as _exc:
            st.markdown(
                f'<div class="dashboard-head" style="color: var(--ink-dim); opacity: 0.5;">'
                f'distribution charts unavailable ({html.escape(str(_exc)[:80])})</div>',
                unsafe_allow_html=True,
            )

    # ─── Annotated sheets section (Phase 2 — only if saved JPEGs exist) ──
    if _rv_has_assets and _rv_pages_with_images:
        st.markdown(
            f"""
<div class="section-head" style="margin-top: 8px;">
  <h3>Annotated sheets</h3>
  <span class="tag">{len(_rv_pages_with_images)} SHEET{"" if len(_rv_pages_with_images) == 1 else "S"} WITH FINDINGS · PINS COLOURED BY SEVERITY</span>
</div>
""",
            unsafe_allow_html=True,
        )
        _rv_annotated_cards = ['<div class="annotated-grid">']
        _rv_dot_classes = {"critical": "vermillion", "major": "amber", "minor": "ochre", "advisory": "blueprint"}
        for _pn in _rv_pages_with_images:
            _rv_pins = _pins_for_page(findings, _pn)
            try:
                _rv_sheet_url = _cached_review_sheet_url(_rv_audit_id, _pn, _rv_pins)
                if _rv_sheet_url:
                    _rv_img_block = f'<div class="annotated-image"><img src="{_rv_sheet_url}" alt="Sheet {_pn} annotated" /></div>'
                else:
                    _rv_img_block = '<div class="annotated-image fail">Saved render unavailable for this sheet.</div>'
            except Exception as _exc:
                _rv_img_block = f'<div class="annotated-image fail">Render failed: {html.escape(str(_exc)[:120])}</div>'

            _rv_sev_for_page = {s: 0 for s in SEVERITIES}
            for _f in findings:
                if _f.get("page_number") == _pn:
                    _rv_sev_for_page[_normalize_severity(_f.get("severity"))] += 1
            _rv_sev_dots = [
                f'<span class="sev-dot sev-{_rv_dot_classes[s]}">{_rv_sev_for_page[s]} {s.title()}</span>'
                for s in SEVERITIES if _rv_sev_for_page[s] > 0
            ]
            _rv_sev_html = " · ".join(_rv_sev_dots) if _rv_sev_dots else ""

            if _rv_is_multi:
                _rv_src_file, _rv_src_page = _source_for_page(_pn, _rv_page_map, _rv_primary)
                _rv_head_left = f"{html.escape(_truncate_filename(_rv_src_file, 28))} · P.{_rv_src_page:02d}"
            else:
                _rv_head_left = f"SHT {_pn:02d}"
            _rv_n_here = sum(1 for _f in findings if _f.get("page_number") == _pn)
            _rv_annotated_cards.append(
                f"""
<div class="annotated-card">
  <div class="annotated-head">
    <span class="annotated-name">{_rv_head_left}</span>
    <span class="annotated-count">{_rv_n_here} FINDING{"" if _rv_n_here == 1 else "S"}</span>
  </div>
  {_rv_img_block}
  <div class="annotated-foot">{_rv_sev_html}</div>
</div>
"""
            )
        _rv_annotated_cards.append("</div>")
        st.markdown("\n".join(_rv_annotated_cards), unsafe_allow_html=True)

    # ─── Filter pills + CSV download (no PDF report in review mode) ───────
    if findings:
        st.markdown(
            f"""
<div class="filter-bar-head">
  <span class="lbl cyan">Filter by severity</span>
  <span class="lbl">{_rv_total} total finding{"" if _rv_total == 1 else "s"}</span>
</div>
""",
            unsafe_allow_html=True,
        )
        _rv_filter = st.radio(
            "Severity filter",
            options=list(FILTER_LABELS),
            index=0, horizontal=True, label_visibility="collapsed",
            key=f"rv_sev_filter_{pdf_hash[:8]}",
        )
        st.markdown('<div class="export-row-head">EXPORT</div>', unsafe_allow_html=True)
        _, _rv_col_csv, _ = st.columns([3, 1.5, 1.5])
        _rv_meta_for_export = {
            "project_name": _rv_fd.get("project_name", ""),
            "architect": _rv_fd.get("architect", ""),
            "jurisdiction": _rv_fd.get("jurisdiction", ""),
            "set_date": _rv_fd.get("set_date", ""),
            "generated_at": _rv_fd.get("generated_at", ""),
            "references_files": _rv_fd.get("references_files") or [],
            "references_word_count": _rv_fd.get("references_word_count", 0),
        }
        with _rv_col_csv:
            _rv_csv = _build_findings_csv(
                findings, _rv_page_map, _rv_primary, meta=_rv_meta_for_export,
            )
            st.download_button(
                label="Download CSV",
                data=_rv_csv,
                file_name=f"plancheck_{_safe_filename_stem(_rv_primary)}_{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv",
                mime="text/csv",
                key=f"rv_dl_csv_{pdf_hash[:8]}",
            )

        # ─── Add new finding (Principal only) ──────────────────────────────
        _rv_role = st.session_state.get("current_role", ROLE_NONE)
        _rv_is_principal = _rv_role == ROLE_PRINCIPAL
        _rv_is_project = _rv_role == ROLE_PROJECT

        if _rv_is_principal:
            if st.session_state.get("adding_finding"):
                with st.form("rv_add_finding_form", clear_on_submit=True):
                    st.markdown('<div class="form-eyebrow">+ NEW FINDING</div>', unsafe_allow_html=True)
                    _rva_c1, _rva_c2 = st.columns([1, 1])
                    with _rva_c1:
                        _rva_severity = st.selectbox("Severity", list(SEVERITIES), index=1, key="rv_add_severity")
                    with _rva_c2:
                        _rva_category = st.selectbox(
                            "Category", ["code", "drawing_error", "coordination", "constructability"],
                            key="rv_add_category",
                        )
                    _rva_desc = st.text_area("Description (one sentence)", key="rv_add_desc", height=70)
                    _rva_evidence = st.text_area("Evidence", key="rv_add_evidence", height=70)
                    _rva_rec = st.text_area("Recommendation", key="rv_add_rec", height=70)
                    _rva_p1, _rva_p2 = st.columns([1, 1])
                    with _rva_p1:
                        _rva_page = st.number_input(
                            "Sheet number", min_value=1, max_value=max(1, _rv_pages_total),
                            value=1, step=1, key="rv_add_page",
                        )
                    with _rva_p2:
                        _rva_region = st.selectbox(
                            "Pin location (3×3 zone)",
                            ["top-left", "top-center", "top-right",
                             "center-left", "center", "center-right",
                             "bottom-left", "bottom-center", "bottom-right",
                             "full-sheet"],
                            index=4, key="rv_add_region",
                        )
                    _rva_assign = st.selectbox(
                        "Assign to",
                        list(ROLE_ASSIGNABLE),
                        index=0,
                        key="rv_add_assign",
                        help="Direct this finding at a teammate. They'll see an 'ASSIGNED · …' tag on the card and a 'For you' highlight when their role is selected.",
                    )
                    _rva_save_col, _rva_cancel_col, _ = st.columns([1, 1, 4])
                    with _rva_save_col:
                        _rva_save = st.form_submit_button("Save finding", type="primary")
                    with _rva_cancel_col:
                        _rva_cancel = st.form_submit_button("Cancel")
                    if _rva_save and (_rva_desc or "").strip():
                        _save_new_finding(
                            _rva_severity, _rva_category,
                            _rva_desc, _rva_evidence, _rva_rec,
                            int(_rva_page), _rva_region,
                            assigned_to=_rva_assign,
                        )
                        st.rerun()
                    elif _rva_cancel:
                        _cancel_add()
                        st.rerun()
            else:
                if st.button("+  Add new finding", key="rv_add_finding_btn", on_click=_start_adding):
                    pass

        # ─── Findings list (text-only, with edit/resolve UI) ──────────────
        _rv_severity_order = {"critical": 0, "major": 1, "minor": 2, "advisory": 3}
        _rv_active_filter = (_rv_filter or "All").lower()
        _rv_indexed = list(enumerate(findings, 1))
        if _rv_active_filter != "all":
            _rv_indexed = [
                (idx, f) for (idx, f) in _rv_indexed
                if _normalize_severity(f.get("severity")) == _rv_active_filter
            ]
        _rv_sorted = sorted(
            _rv_indexed,
            key=lambda pair: (
                _rv_severity_order.get(_normalize_severity(pair[1].get("severity")), 99),
                1 if pair[1].get("resolved") else 0,
                _page_sort_value(pair[1].get("page_number")),
                pair[0],
            ),
        )

        if not _rv_sorted:
            st.markdown(
                f"""
<div class="empty-findings">
  <div class="ttl">"No {html.escape(_rv_active_filter)} findings."</div>
  <div class="sub">Switch the filter back to All to see every finding.</div>
</div>
""",
                unsafe_allow_html=True,
            )
        else:
            for original_idx, f in _rv_sorted:
                sev = _normalize_severity(f.get("severity"))
                cat = (f.get("category") or "—").replace("_", " ").upper()
                desc = html.escape(f.get("description") or "(no description)")
                evidence = html.escape(f.get("evidence") or "—")
                recommendation = html.escape(f.get("recommendation") or "—")
                page_num = f.get("page_number")
                if page_num == "multiple":
                    # Cross-sheet coordination finding — no single page.
                    page_badge = _cross_sheet_badge_html(f)
                elif _rv_is_multi and isinstance(page_num, int) and page_num > 0:
                    src_file, src_page = _source_for_page(page_num, _rv_page_map, _rv_primary)
                    page_badge = (
                        f'<span class="badge src">{html.escape(_truncate_filename(src_file, 32))}'
                        f'<span class="src-page">P.{src_page:02d}</span></span>'
                    )
                else:
                    page_badge = (
                        f'<span class="badge pg">SHT {page_num:02d}</span>'
                        if isinstance(page_num, int) and page_num > 0 else ""
                    )

                # Status tags (resolved / edited / added / assigned)
                status_tags = []
                if f.get("manually_added"):
                    status_tags.append('<span class="status-tag added">+ ADDED</span>')
                if f.get("edited"):
                    status_tags.append('<span class="status-tag edited">EDITED</span>')
                if f.get("resolved"):
                    status_tags.append('<span class="status-tag resolved">✓ RESOLVED</span>')
                _rv_assigned_to = f.get("assigned_to")
                _rv_is_for_me = bool(_rv_assigned_to and _rv_assigned_to == _rv_role and _rv_role != ROLE_NONE)
                if _rv_assigned_to:
                    if _rv_is_for_me:
                        status_tags.append('<span class="status-tag foryou">★ FOR YOU</span>')
                    else:
                        status_tags.append(
                            f'<span class="status-tag assigned">→ ASSIGNED · {html.escape(_rv_assigned_to.upper())}</span>'
                        )
                status_tags_html = " ".join(status_tags)
                resolved_class = " resolved" if f.get("resolved") else ""
                foryou_class = " foryou" if _rv_is_for_me else ""

                # Edit-mode replaces the card
                if st.session_state.get("editing_idx") == original_idx and _rv_is_principal:
                    st.markdown(f"""
<div class="finding finding-{sev} editing">
  <div class="finding-head">
    <span class="badge badge-{sev}">{sev.upper()}</span>
    {page_badge}
    <span class="cat">{html.escape(cat)}</span> {status_tags_html} <span class="no">EDITING FND-{original_idx:02d}</span>
  </div>
</div>
""", unsafe_allow_html=True)
                    with st.form(f"rv_edit_form_{original_idx}", clear_on_submit=False):
                        _rve_severity = st.selectbox(
                            "Severity", list(SEVERITIES),
                            index=list(SEVERITIES).index(sev),
                            key=f"rv_edit_severity_{original_idx}",
                        )
                        _rve_desc = st.text_area("Description", value=f.get("description", "") or "",
                                                 height=80, key=f"rv_edit_desc_{original_idx}")
                        _rve_ev = st.text_area("Evidence", value=f.get("evidence", "") or "",
                                               height=80, key=f"rv_edit_ev_{original_idx}")
                        _rve_rec = st.text_area("Recommendation", value=f.get("recommendation", "") or "",
                                                height=80, key=f"rv_edit_rec_{original_idx}")
                        _rve_current_assignee = f.get("assigned_to") or ASSIGN_UNASSIGNED
                        _rve_assign_idx = (
                            list(ROLE_ASSIGNABLE).index(_rve_current_assignee)
                            if _rve_current_assignee in ROLE_ASSIGNABLE else 0
                        )
                        _rve_assign = st.selectbox(
                            "Assign to",
                            list(ROLE_ASSIGNABLE),
                            index=_rve_assign_idx,
                            key=f"rv_edit_assign_{original_idx}",
                            help="Direct this finding at a teammate. They'll see an 'ASSIGNED · …' tag on the card and a 'For you' highlight when their role is selected.",
                        )
                        _rve_save_c, _rve_cancel_c, _ = st.columns([1, 1, 4])
                        with _rve_save_c:
                            _rve_save = st.form_submit_button("Save changes", type="primary")
                        with _rve_cancel_c:
                            _rve_cancel = st.form_submit_button("Cancel")
                        if _rve_save:
                            _save_edit(original_idx, _rve_severity, _rve_desc, _rve_ev, _rve_rec,
                                       assigned_to=_rve_assign)
                            st.rerun()
                        elif _rve_cancel:
                            _cancel_edit()
                            st.rerun()
                else:
                    # Normal card render — Phase 2: try saved JPEG first, fall
                    # back to the legacy placeholder if no asset on disk.
                    _rv_thumb_html = ""
                    if isinstance(page_num, int) and page_num > 0 and has_page_image(_rv_audit_id, page_num - 1):
                        try:
                            _rv_page_pins = _pins_for_page(findings, page_num)
                            _rv_thumb_url = _cached_review_thumb_url(_rv_audit_id, page_num, _rv_page_pins)
                            if _rv_thumb_url:
                                if _rv_is_multi:
                                    _rv_src_file_t, _rv_src_page_t = _source_for_page(page_num, _rv_page_map, _rv_primary)
                                    _rv_thumb_caption = f"{_truncate_filename(_rv_src_file_t, 22)} · P.{_rv_src_page_t:02d}"
                                else:
                                    _rv_thumb_caption = f"SHT {page_num:02d} · context"
                                _rv_pin_count = (
                                    f" · {len(_rv_page_pins)} pin{'' if len(_rv_page_pins) == 1 else 's'}"
                                    if _rv_page_pins else ""
                                )
                                _rv_thumb_html = f"""
<div class="thumb-col">
  <div class="thumb-frame"><img src="{_rv_thumb_url}" alt="Sheet {page_num}" /></div>
  <div class="thumb-cap">{html.escape(_rv_thumb_caption)}{_rv_pin_count}</div>
</div>"""
                        except Exception:
                            _rv_thumb_html = ""

                    if not _rv_thumb_html:
                        _rv_thumb_html = """
<div class="thumb-col">
  <div class="thumb-fail">No saved render for this sheet — re-upload PDF or re-run audit</div>
</div>"""

                    st.markdown(f"""
<div class="finding finding-{sev}{resolved_class}{foryou_class}">
  <div class="finding-head">
    <span class="badge badge-{sev}">{sev.upper()}</span>
    {page_badge}
    <span class="cat">{html.escape(cat)}</span> {status_tags_html} <span class="no">FND-{original_idx:02d}</span>
  </div>
  <div class="finding-body with-thumb">
    {_rv_thumb_html}
    <div class="text-col">
    <p class="desc">{desc}</p>
    <div class="kv">
      <span class="k">Evidence</span>
      <p class="v">{evidence}</p>
    </div>
    <div class="kv">
      <span class="k">Recommendation</span>
      <p class="v">{recommendation}</p>
    </div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

                    if _rv_is_principal:
                        _rve_col, _ = st.columns([1, 6])
                        with _rve_col:
                            st.button("✎  Edit", key=f"rv_edit_btn_{original_idx}",
                                      on_click=_start_editing, args=(original_idx,))
                    elif _rv_is_project:
                        st.checkbox(
                            "Resolved" if not f.get("resolved") else "Resolved ✓",
                            value=bool(f.get("resolved")),
                            key=f"rv_resolve_{original_idx}",
                            on_change=_toggle_resolved, args=(original_idx,),
                        )


# About PlanCheck — always visible
with st.expander("About PlanCheck · what it does and what it does not"):
    st.markdown(
        """
**PlanCheck** is an AI-assisted auditor for construction permit drawings. Upload a PDF (or several), pick the jurisdiction, and receive a register of findings — categorised by severity, with evidence, recommendation, and a thumbnail of the sheet each finding came from.

**What it does well**

- Spots obvious drawing problems: missing dimensions, unlabeled rooms, missing door/window schedules, conflicting callouts
- Flags universal good-practice issues that apply in any project
- The audit is currently scoped to Cupertino — applies CBC, CRC, Title 24, ADU state law (AB 68 / SB 13 / SB 9 etc.), AND Cupertino Municipal Code amendments (CMC §19.28 zoning / §14.18 Heritage Trees / §16.54 reach code) — and cites specific code sections where confident
- Acts as a fast second pair of eyes before submission, plan-check resubmittal, or AHJ comment response

**Reference rules — your editable rule library**

The `references/` folder in the project contains markdown / text files (`_general.md`, `general instructions.txt`, `california_state.md`, `cupertino_rules.md`, `sj_residential_general.md`, plus anything else you drop in). You can edit them directly in Notepad / VS Code. The contents are appended to every plan-check prompt so the AI applies *your* firm's rules, not just its training knowledge.

- **All `.md` and `.txt` files in `references/` root are auto-loaded on every run** — drop a new file in, it gets used; move a file to a subfolder (e.g. `past_projects/`), it stops being used
- The findings header tells you which files were applied on each run
- The CSV and PDF report include the list of reference files applied — making each export auditable
- HTML comments inside the files are stripped before sending to the AI, so you can leave instructional notes freely

**What it does NOT do**

- Check against the *full text* of any specific code book — the AI uses general training knowledge plus jurisdictional context, not retrieved code sections (that capability is on the V1.2 roadmap)
- Cross-reference between disciplines (architecture vs. structural vs. MEP)
- Verify or cite specific code sections — by design, the AI omits citations rather than guess
- Catch issues only visible across multiple sheets (e.g., column mismatches between architectural and structural sheets)

---

**How to read findings**

- **Critical** — the kind of issue that would stop a permit at intake
- **Major** — likely to be raised in plan review and require correction
- **Minor** — recommended improvements; correction expected but not always required
- **Advisory** — observations for consideration

**Speed & limits**

- Roughly 8–18 seconds per sheet depending on complexity
- Capped at 100 sheets per upload to keep run times predictable
- Your PDFs are processed in memory and never written to disk

---

**Important.** Findings are AI-generated. Always verify before acting on them in any submission. The tool is a fast second pair of eyes, not a replacement for a qualified plan reviewer or architect.
"""
    )


st.markdown(
    """
<div class="colophon">
  <span>PlanCheck · AI-assisted plan review</span>
  <span>Findings are AI-generated — verify before acting.</span>
</div>
""",
    unsafe_allow_html=True,
)
