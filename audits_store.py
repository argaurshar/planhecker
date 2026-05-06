"""Audit persistence — save / load / list audits as JSON files on disk.

Pure functions, no Streamlit dependency. Each audit becomes a single JSON
file in `audits/` (auto-created on first save). The file holds everything
needed to re-render the audit later: project metadata, every finding
(including any Principal edits, manually-added findings, and resolved-marks
from the Project Architect), page errors, and the source-file page map.

Mirrors the pattern of `references_loader.py` — pure functions taking file
paths, easy to test, no global state.
"""

from __future__ import annotations

import io
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image as _PILImageModule  # noqa: F401


AUDITS_DIR_NAME = "audits"
ASSETS_SUFFIX = "_assets"


# ════════════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════════════

def _audits_dir(base: Optional[Path] = None) -> Path:
    """Resolve the audits/ directory next to this module unless overridden."""
    if base is not None:
        return base
    return Path(__file__).resolve().parent / AUDITS_DIR_NAME


def _slugify(text: str, max_len: int = 40) -> str:
    """File-safe lowercase kebab-ish slug. Empty input → 'untitled'."""
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", (text or "").strip()).strip("-").lower()
    if not cleaned:
        return "untitled"
    return cleaned[:max_len].rstrip("-") or "untitled"


def _make_audit_id(project_name: str, when: Optional[datetime] = None) -> str:
    """Build a unique-ish audit_id: <project-slug>_<YYYYMMDD-HHMMSS>."""
    when = when or datetime.now()
    return f"{_slugify(project_name)}_{when.strftime('%Y%m%d-%H%M%S')}"


def _safe_path_for(audit_id: str, base: Path) -> Path:
    """Reject any audit_id that tries to escape the audits/ directory."""
    safe_id = re.sub(r"[^a-zA-Z0-9_-]+", "-", audit_id).strip("-")
    if not safe_id:
        raise ValueError("audit_id is empty after sanitization")
    return base / f"{safe_id}.json"


# ════════════════════════════════════════════════════════════════════════════
# Public API
# ════════════════════════════════════════════════════════════════════════════

def save_audit(
    findings_data: dict,
    audits_dir: Optional[Path] = None,
    audit_id: Optional[str] = None,
) -> str:
    """Serialize findings_data to a JSON file and return the audit_id.

    If audit_id is supplied, it overwrites the existing file with that id
    (this is how edits / resolved-marks are persisted — re-save under the
    same id). If omitted, a new id is generated from project_name + now.
    """
    base = _audits_dir(audits_dir)
    base.mkdir(parents=True, exist_ok=True)

    project_name = (findings_data.get("project_name") or "").strip()
    if audit_id is None:
        audit_id = _make_audit_id(project_name)

    payload = dict(findings_data)  # shallow copy — don't mutate caller's dict
    payload["audit_id"] = audit_id
    payload["saved_at"] = datetime.now().isoformat(timespec="seconds")

    target = _safe_path_for(audit_id, base)
    # Write to a temp file then atomically rename, so an interrupted save
    # never leaves a half-written JSON behind that crashes the loader.
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(target)
    return audit_id


def load_audit(audit_id: str, audits_dir: Optional[Path] = None) -> Optional[dict]:
    """Read an audit JSON by id. Returns None if it doesn't exist or is malformed."""
    base = _audits_dir(audits_dir)
    try:
        target = _safe_path_for(audit_id, base)
    except ValueError:
        return None
    if not target.is_file():
        return None
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def list_audits(
    audits_dir: Optional[Path] = None,
    limit: int = 25,
) -> list[dict]:
    """Return a summary of every saved audit, newest first.

    Each entry: {audit_id, project_name, jurisdiction, saved_at,
    total_findings, resolved_count}. Files that fail to parse are skipped
    silently (corrupted file shouldn't break the picker UI).
    """
    base = _audits_dir(audits_dir)
    if not base.is_dir():
        return []

    summaries: list[dict] = []
    for path in base.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        findings = data.get("findings") or []
        summaries.append({
            "audit_id":        data.get("audit_id") or path.stem,
            "project_name":    data.get("project_name") or "—",
            "jurisdiction":    data.get("jurisdiction") or "None",
            "saved_at":        data.get("saved_at") or "",
            "total_findings":  len(findings),
            "resolved_count":  sum(1 for f in findings if f.get("resolved")),
        })

    # Newest first by saved_at; fall back to filename if missing
    summaries.sort(key=lambda s: s["saved_at"], reverse=True)
    return summaries[:limit]


def delete_audit(audit_id: str, audits_dir: Optional[Path] = None) -> bool:
    """Remove the JSON file (and any saved page-image assets) for audit_id.

    Returns True if the JSON file existed and was removed. The asset folder
    is best-effort: failures there don't downgrade the return value.
    """
    base = _audits_dir(audits_dir)
    try:
        target = _safe_path_for(audit_id, base)
    except ValueError:
        return False

    # Best-effort: remove any saved page renders alongside the JSON.
    try:
        assets = audit_assets_dir(audit_id, audits_dir)
        if assets.is_dir():
            shutil.rmtree(assets, ignore_errors=True)
    except ValueError:
        pass

    if target.is_file():
        try:
            target.unlink()
            return True
        except OSError:
            return False
    return False


# ════════════════════════════════════════════════════════════════════════════
# Per-audit page-image assets
#
# Each audit can persist rendered page images (JPEGs) into a sibling folder
# named "<audit_id>_assets/" so review mode can re-render the annotated sheets
# section + per-finding thumbnails without forcing the user to re-upload the
# original PDF. Pin coordinates are deterministic from each finding's `region`
# field, so we don't need to save annotation overlays — just the clean page
# renders. Pins are reapplied on load via pin_overlay.annotate_sheet().
# ════════════════════════════════════════════════════════════════════════════

def audit_assets_dir(audit_id: str, audits_dir: Optional[Path] = None) -> Path:
    """Return the assets folder path for audit_id (does not create it).

    Reuses the same path-traversal guard as the JSON file path. Raises
    ValueError if the id sanitizes to an empty string.
    """
    base = _audits_dir(audits_dir)
    safe_id = re.sub(r"[^a-zA-Z0-9_-]+", "-", audit_id).strip("-")
    if not safe_id:
        raise ValueError("audit_id is empty after sanitization")
    return base / f"{safe_id}{ASSETS_SUFFIX}"


def _page_image_path(audit_id: str, page_num: int, audits_dir: Optional[Path]) -> Path:
    if not isinstance(page_num, int) or page_num < 0:
        raise ValueError(f"page_num must be a non-negative int, got {page_num!r}")
    return audit_assets_dir(audit_id, audits_dir) / f"page_{page_num}.jpg"


def save_page_image(
    audit_id: str,
    page_num: int,
    image,
    audits_dir: Optional[Path] = None,
    quality: int = 85,
) -> Optional[Path]:
    """Save a PIL.Image as JPEG into the audit's assets folder.

    page_num is the 0-indexed page number used everywhere else in
    findings_data. Creates the assets folder if missing. Atomic write via
    .tmp-then-rename so an interrupted save can't leave a half-written file.
    Returns the saved path on success, or None if the input wasn't a usable
    image (we deliberately don't raise — image persistence is best-effort and
    must never block an audit run from completing).
    """
    try:
        target = _page_image_path(audit_id, page_num, audits_dir)
    except ValueError:
        return None

    target.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Convert to RGB for JPEG (handles RGBA / palette / 1-bit inputs)
        if hasattr(image, "mode") and image.mode != "RGB":
            image = image.convert("RGB")
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=quality, optimize=True)
        tmp = target.with_suffix(".jpg.tmp")
        tmp.write_bytes(buf.getvalue())
        tmp.replace(target)
        return target
    except (OSError, ValueError, AttributeError):
        return None


def load_page_image(
    audit_id: str,
    page_num: int,
    audits_dir: Optional[Path] = None,
):
    """Load a saved page image as a PIL.Image, or return None if missing.

    None is returned for any failure (file missing, decode error, PIL not
    importable). Callers fall back to a placeholder so legacy audits saved
    before this phase shipped continue to render cleanly.
    """
    try:
        target = _page_image_path(audit_id, page_num, audits_dir)
    except ValueError:
        return None
    if not target.is_file():
        return None
    try:
        from PIL import Image  # local import — keep this module pure when unused
        img = Image.open(target)
        img.load()  # force read so the file handle can close
        return img
    except Exception:
        return None


def has_page_image(
    audit_id: str,
    page_num: int,
    audits_dir: Optional[Path] = None,
) -> bool:
    """Cheap existence check — does the JPEG for this page exist on disk?"""
    try:
        return _page_image_path(audit_id, page_num, audits_dir).is_file()
    except ValueError:
        return False


# ════════════════════════════════════════════════════════════════════════════
# Schema helper — call this on every finding before save AND after load,
# so any older audits get the new fields with safe defaults.
# ════════════════════════════════════════════════════════════════════════════

_FINDING_DEFAULTS: dict = {
    "resolved":       False,
    "resolved_by":    None,
    "resolved_at":    None,
    "edited":         False,
    "edited_by":      None,
    "edited_at":      None,
    "manually_added": False,
    "added_by":       None,
    "added_at":       None,
    # Phase 3 — assignment of an edit / new finding to a teammate.
    # assigned_to is the role label string (e.g. "Structure Engineer") or
    # None when no one is assigned. assigned_by + assigned_at record who
    # made the assignment and when, so the assigned person can see context.
    "assigned_to":    None,
    "assigned_by":    None,
    "assigned_at":    None,
}


def normalize_finding(finding: dict) -> dict:
    """Return a copy of finding with collaboration fields filled in.

    Idempotent: applying multiple times yields the same result. Use this
    when loading an audit (older files predating these fields work cleanly)
    and when adding a brand-new finding.
    """
    out = dict(finding)
    for key, default in _FINDING_DEFAULTS.items():
        out.setdefault(key, default)
    return out


def normalize_findings_data(findings_data: dict) -> dict:
    """Apply normalize_finding() to every finding in a findings_data dict."""
    out = dict(findings_data)
    out["findings"] = [normalize_finding(f) for f in (findings_data.get("findings") or [])]
    return out
