import base64
import io
import json
import os
from typing import Callable, Optional

from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image

from pdf_processor import get_pdf_info, render_page_to_image
from prompts import SINGLE_PAGE_REVIEW_PROMPT

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
    return (os.getenv("OPENAI_API_KEY") or "").strip()


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
) -> list[dict]:
    """Send one drawing page to GPT-5.4 vision; return a list of finding dicts.

    If jurisdiction_addendum is non-empty, it is appended to the base prompt
    so the model applies jurisdiction-specific code conventions (e.g. NBC India,
    DDA, HUDA, Punjab Municipal byelaws).

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
            return findings if isinstance(findings, list) else []
        except json.JSONDecodeError as exc:
            last_exc = RuntimeError(f"Model returned non-JSON: {exc}")
        except Exception as exc:
            last_exc = exc

    raise RuntimeError(f"Plan check failed after retry: {last_exc}") from last_exc


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
      - findings: combined list, each enriched with 'page_number'
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
    page_errors: list[dict] = []

    for page_num in range(1, pages_to_review + 1):
        if on_page_start is not None:
            try:
                on_page_start(page_num, pages_to_review)
            except Exception:
                pass
        try:
            img = render_page_to_image(pdf_bytes, page_num, dpi=dpi)
            page_findings = review_single_page(img, jurisdiction_addendum=jurisdiction_addendum)
            for f in page_findings:
                if isinstance(f, dict):
                    f["page_number"] = page_num
                    all_findings.append(f)
        except Exception as exc:
            page_errors.append({"page": page_num, "error": str(exc)[:300]})

        if progress_callback is not None:
            try:
                progress_callback(page_num, pages_to_review, len(all_findings))
            except Exception:
                pass

    return {
        "findings": all_findings,
        "page_errors": page_errors,
        "pages_reviewed": pages_to_review,
        "pages_total": total,
        "capped": capped,
    }
