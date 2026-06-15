import base64
import io
import json
import os
from typing import Callable, Optional

from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image

from pdf_processor import get_pdf_info, render_page_to_image
from prompts import SINGLE_PAGE_REVIEW_PROMPT, COORDINATION_CHECK_PROMPT
from text_pass import run_text_pass

load_dotenv()

MODEL = "gpt-5.4"
MAX_VISION_DIM = 1568
MAX_PAGES = 100
COST_PER_PAGE_USD = 0.05


def _read_api_key() -> str:
    # Re-read .env on every call with override=True so edits to the file
    # take effect without restarting Streamlit. Without this, the first
    # value loaded at import time (often the 'your_key_here' placeholder)
    # gets cached in os.environ for the life of the process.
    load_dotenv(override=True)
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        # Streamlit Community Cloud has no .env file — the key is supplied via
        # the app's Secrets box (st.secrets). Read it as a fallback. Guarded so
        # non-Streamlit callers (eval harness, scripts) never break.
        try:
            import streamlit as st
            key = (st.secrets.get("OPENAI_API_KEY", "") or "").strip()
        except Exception:
            pass
    return key


def is_api_key_set() -> bool:
    key = _read_api_key()
    return bool(key) and key not in ("your_key_here",)


def _get_client() -> OpenAI:
    key = _read_api_key()
    if not key or key == "your_key_here":
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Open the .env file in your project folder "
            "and replace 'your_key_here' with your real OpenAI API key (starts with sk-), "
            "then restart Streamlit."
        )
    return OpenAI(api_key=key, timeout=120)


def _resize_for_vision(img: Image.Image, max_dim: int = MAX_VISION_DIM) -> Image.Image:
    w, h = img.size
    if max(w, h) <= max_dim:
        return img
    scale = max_dim / max(w, h)
    return img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)


def _img_to_data_url(img: Image.Image, quality: int = 85) -> str:
    if img.mode != "RGB":
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"


def review_single_page(
    image: Image.Image,
    jurisdiction_addendum: str = "",
) -> dict:
    """Send one drawing page to the vision model; return {findings, facts}.

    Returns a dict with two keys:
      - findings: list[dict] — per-page findings (same shape as before)
      - facts:    dict       — structured facts extracted from the page
                               (rooms, dimensions, openings, claims, sheet_id, ...)
                               Used later by coordination_check() to find
                               inconsistencies between sheets.

    If jurisdiction_addendum is non-empty, it is appended to the base prompt
    so the model applies jurisdiction-specific code conventions.

    Retries once on transient failure. Raises RuntimeError on persistent failure
    so the caller can show the user what went wrong.
    """
    client = _get_client()
    sized = _resize_for_vision(image)
    data_url = _img_to_data_url(sized)

    prompt_text = SINGLE_PAGE_REVIEW_PROMPT
    if jurisdiction_addendum:
        prompt_text = prompt_text + "\n\n" + jurisdiction_addendum

    payload = dict(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        response_format={"type": "json_object"},
    )

    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            response = client.chat.completions.create(**payload)
            text = (response.choices[0].message.content or "{}").strip()
            data = json.loads(text)
            findings = data.get("findings", [])
            facts = data.get("facts", {})
            return {
                "findings": findings if isinstance(findings, list) else [],
                "facts": facts if isinstance(facts, dict) else {},
            }
        except json.JSONDecodeError as exc:
            last_exc = RuntimeError(f"Model returned non-JSON: {exc}")
        except Exception as exc:
            last_exc = exc

    raise RuntimeError(f"Plan check failed after retry: {last_exc}") from last_exc


def coordination_check(
    facts_per_page: list[dict],
    jurisdiction_addendum: str = "",
) -> list[dict]:
    """Run a single AI pass that compares facts across all pages.

    facts_per_page is a list of dicts, each shaped like:
        {"page_number": int, "facts": {...}}

    Returns a list of coordination findings, each enriched with:
        page_number = "multiple"
        category = "coordination"
        sheets_involved = [...]  (from the model output)
        pages_involved  = [...]  (from the model output's page_numbers)
        region = "full-sheet"    (so pin overlay treats them as cross-sheet)

    No image input — this is a text-only pass over the structured facts.
    Costs are tiny (~$0.02 per audit). Failures are tolerated — returns [] on
    error rather than raising, because coordination is additive value: a
    failed coordination pass should not block the per-page findings from
    rendering.
    """
    # Nothing to coordinate if fewer than 2 pages of facts
    real_facts = [p for p in facts_per_page if (p.get("facts") or {})]
    if len(real_facts) < 2:
        return []

    client = _get_client()
    prompt_text = COORDINATION_CHECK_PROMPT
    if jurisdiction_addendum:
        prompt_text = prompt_text + "\n\n" + jurisdiction_addendum

    facts_payload = json.dumps(facts_per_page, ensure_ascii=False, indent=2)
    user_message = (
        f"{prompt_text}\n\n"
        f"FACTS PER PAGE (JSON array):\n{facts_payload}"
    )

    payload = dict(
        model=MODEL,
        messages=[{"role": "user", "content": user_message}],
        response_format={"type": "json_object"},
    )

    try:
        response = client.chat.completions.create(**payload)
        text = (response.choices[0].message.content or "{}").strip()
        data = json.loads(text)
        raw_findings = data.get("findings", []) or []
    except Exception:
        return []

    enriched: list[dict] = []
    for f in raw_findings:
        if not isinstance(f, dict):
            continue
        f.setdefault("category", "coordination")
        f.setdefault("region", "full-sheet")
        f["page_number"] = "multiple"
        # Normalise the cross-sheet metadata, defaulting to safe empties.
        sheets = f.get("sheets_involved") or []
        pages = f.get("page_numbers") or []
        f["sheets_involved"] = sheets if isinstance(sheets, list) else []
        f["pages_involved"] = pages if isinstance(pages, list) else []
        # Drop the original key the model emitted to avoid shape confusion
        f.pop("page_numbers", None)
        enriched.append(f)
    return enriched


def review_full_pdf(
    pdf_bytes: bytes,
    progress_callback: Optional[Callable[[int, int, int], None]] = None,
    on_page_start: Optional[Callable[[int, int], None]] = None,
    max_pages: int = MAX_PAGES,
    dpi: int = 150,
    jurisdiction_addendum: str = "",
) -> dict:
    """Review every page of a PDF (capped at max_pages).

    jurisdiction_addendum, if provided, is forwarded to review_single_page so the
    AI applies jurisdiction-specific code conventions on every page.

    on_page_start(current_page, total_to_review) is called BEFORE each page's
    API call begins. Useful for showing a live preview of the sheet being
    reviewed while the (8–18 second) API call is in flight.

    progress_callback is called as f(current_page, total_to_review, running_findings_count)
    after each page is processed (success or failure).

    Returns a dict:
      - findings: combined list (text-pass + per-page AI + cross-sheet coordination),
                  each enriched with 'page_number'. Coordination findings have
                  page_number = "multiple" and sheets_involved / pages_involved.
                  Text-pass findings have source="text_extraction" and an
                  evidence_quote that is guaranteed to appear literally in the PDF.
      - facts_per_page: list of {'page_number': N, 'facts': {...}}
      - text_pass: result dict from text_pass.run_text_pass() with metadata
                   (rule_counts, pages_with_text) for debugging
      - page_errors: list of {'page': N, 'error': str} for pages that failed
      - pages_reviewed: how many pages were actually sent to the model
      - pages_total:    total pages in the source PDF
      - capped:         True if pages_total > max_pages
    """
    info = get_pdf_info(pdf_bytes)
    if info.get("error"):
        raise RuntimeError(f"Could not read PDF: {info['error']}")
    total = info.get("page_count", 0)
    if total <= 0:
        raise RuntimeError("PDF has no readable pages.")

    pages_to_review = min(total, max_pages)
    capped = total > max_pages

    all_findings: list[dict] = []
    facts_per_page: list[dict] = []
    page_errors: list[dict] = []

    # Text-extraction pass — runs FIRST. No API calls; <1 second. Catches
    # findings with literal PDF text evidence (PRELIMINARY title-block labels,
    # wrong-jurisdiction template text, outdated standards, missing CRC notes,
    # crawlspace ventilation formula errors, lot-number / lot-area cross-sheet
    # inconsistencies). All findings have source="text_extraction" and an
    # evidence_quote that is guaranteed to appear literally somewhere in the PDF.
    try:
        text_pass_result = run_text_pass(pdf_bytes)
        all_findings.extend(text_pass_result.get("findings", []))
    except Exception as exc:
        # Text-pass failures must not block the audit
        text_pass_result = {"findings": [], "error": str(exc)[:300]}

    for page_num in range(1, pages_to_review + 1):
        if on_page_start is not None:
            try:
                on_page_start(page_num, pages_to_review)
            except Exception:
                pass
        try:
            img = render_page_to_image(pdf_bytes, page_num, dpi=dpi)
            page_result = review_single_page(img, jurisdiction_addendum=jurisdiction_addendum)
            page_findings = page_result.get("findings", []) if isinstance(page_result, dict) else []
            page_facts = page_result.get("facts", {}) if isinstance(page_result, dict) else {}
            for f in page_findings:
                if isinstance(f, dict):
                    f["page_number"] = page_num
                    all_findings.append(f)
            facts_per_page.append({"page_number": page_num, "facts": page_facts})
        except Exception as exc:
            page_errors.append({"page": page_num, "error": str(exc)[:300]})

        if progress_callback is not None:
            try:
                progress_callback(page_num, pages_to_review, len(all_findings))
            except Exception:
                pass

    # Cross-sheet coordination pass — text-only, ~$0.02. Failures are silent
    # (return [] inside coordination_check); per-page findings always render.
    coordination_findings = coordination_check(
        facts_per_page,
        jurisdiction_addendum=jurisdiction_addendum,
    )
    all_findings.extend(coordination_findings)

    return {
        "findings": all_findings,
        "facts_per_page": facts_per_page,
        "text_pass": text_pass_result,
        "page_errors": page_errors,
        "pages_reviewed": pages_to_review,
        "pages_total": total,
        "capped": capped,
    }
