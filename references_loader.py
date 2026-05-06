"""Reference-file loader.

Reads markdown / plain-text files from `references/` and assembles them into a
prompt block appended after the jurisdiction addendum, so the AI treats their
contents as authoritative rules.

Auto-detects every `.md` and `.txt` file in the `references/` folder root:
drop a file in, it gets loaded on the next Run Plan Check. Subdirectories are
skipped (so files in `references/past_projects/` or similar archives won't
load into the prompt).

Files are re-read on every call (no caching) so editing a file shows up on the
next Run Plan Check — no server restart needed.

HTML comments (<!-- ... -->) are stripped before sending to the AI so users
can leave instructional notes inside the seed files freely.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional


REFERENCES_DIR_NAME = "references"

# File extensions auto-loaded as plain text.
_TEXT_EXTENSIONS = {".md", ".txt"}

# Soft cap — files exceeding this in total are loaded but a UI warning is shown.
WORD_BUDGET_SOFT_CAP = 30000


def _strip_html_comments(text: str) -> str:
    """Remove <!-- ... --> blocks from markdown so user notes don't bloat tokens."""
    out_parts: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        start = text.find("<!--", i)
        if start == -1:
            out_parts.append(text[i:])
            break
        out_parts.append(text[i:start])
        end = text.find("-->", start + 4)
        if end == -1:
            # Malformed; skip the rest to be safe
            break
        i = end + 3
    return "".join(out_parts)


def _references_dir(base_dir: Optional[Path] = None) -> Path:
    if base_dir is not None:
        return base_dir
    return Path(__file__).resolve().parent / REFERENCES_DIR_NAME


def _discover_files(refs_dir: Path) -> list[Path]:
    """Return every .md/.txt file in the references directory ROOT (no recursion).

    Sorted so files starting with '_' come first (universal/firm-profile files),
    then alphabetically. Consistent ordering keeps the prompt assembly stable
    across runs.
    """
    if not refs_dir.is_dir():
        return []
    files = [
        p for p in refs_dir.iterdir()
        if p.is_file() and p.suffix.lower() in _TEXT_EXTENSIONS
    ]

    def sort_key(p: Path) -> tuple[int, str]:
        # Underscore-prefixed files first; then alphabetical (case-insensitive)
        underscore_first = 0 if p.name.startswith("_") else 1
        return (underscore_first, p.name.lower())

    return sorted(files, key=sort_key)


def load_references(jurisdiction: str = "", base_dir: Optional[Path] = None) -> dict:
    """Load all reference files from references/ root.

    The `jurisdiction` parameter is accepted for backward compat with the
    earlier API but no longer filters which files load — every .md/.txt file
    in the references/ root loads on every run. The user manages scope by
    moving files in/out of the folder.

    Returns a dict with:
      - block: str  — the full prompt block to append (empty string if no content)
      - files: list of {name, path, words, exists, error?}
      - total_words: int — sum of words across loaded files
      - over_soft_cap: bool — True if total_words exceeds WORD_BUDGET_SOFT_CAP
    """
    refs_dir = _references_dir(base_dir)
    discovered = _discover_files(refs_dir)

    file_infos: list[dict] = []
    parts: list[str] = []

    for path in discovered:
        info: dict = {
            "name": path.name,
            "path": str(path),
            "exists": True,
            "words": 0,
        }
        try:
            raw = path.read_text(encoding="utf-8")
            cleaned = _strip_html_comments(raw).strip()
            info["words"] = len(cleaned.split())
            if cleaned:
                parts.append(f"### From {path.name}\n\n{cleaned}")
        except UnicodeDecodeError:
            info["error"] = "file is not valid UTF-8 text — convert to .md/.txt or save as UTF-8"
        except Exception as exc:
            info["error"] = str(exc)[:200]
        file_infos.append(info)

    if parts:
        block = (
            "## Reference rules — apply these to this drawing\n\n"
            "The following content comes from the project's reference library "
            "(files in the `references/` folder). Treat it as authoritative "
            "guidance for this firm and jurisdiction. When a finding violates "
            "or relates to one of these rules, mention the specific rule (or "
            "its source filename) in the evidence or recommendation.\n\n"
            + "\n\n---\n\n".join(parts)
        )
    else:
        block = ""

    total_words = sum(f["words"] for f in file_infos)

    return {
        "block": block,
        "files": file_infos,
        "total_words": total_words,
        "over_soft_cap": total_words > WORD_BUDGET_SOFT_CAP,
    }


def references_summary_short(refs: dict) -> str:
    """Return a one-line UI string like '3 ref files · 1,234 words' or 'no references'."""
    loaded_count = sum(1 for f in refs.get("files", []) if f.get("exists") and f.get("words", 0) > 0)
    total_words = refs.get("total_words", 0)
    if loaded_count == 0:
        return "no reference files loaded"
    return f"{loaded_count} reference file{'' if loaded_count == 1 else 's'} · {total_words:,} words"
