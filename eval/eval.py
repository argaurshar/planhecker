"""PlanCheck — eval harness for measuring recall + precision on a labeled set.

USAGE
-----
1. Put real San Jose drawing PDFs into  eval/drawings/
2. For each drawing, hand-label its ground-truth errors as JSON in
   eval/ground_truth/<same-basename>.json  using the schema below.
3. Run:    python eval/eval.py
   or:     python eval/eval.py --single burns_way_adu.pdf
   or:     python eval/eval.py --dry-run    (no API calls; just validates schema + counts)

Costs roughly $0.05 per page audited. A 10-drawing × 5-page run is ~$2.50.

GROUND-TRUTH JSON SCHEMA
------------------------
{
  "drawing": "burns_way_adu.pdf",
  "jurisdiction": "San Jose (city + state)",
  "labeled_by": "Senior architect name or initials",
  "labeled_at": "2026-05-18",
  "findings": [
    {
      "id": "GT-001",
      "page": 2,
      "sheet_id": "A1.1",
      "severity": "critical",
      "category": "code",
      "description": "Height measured from finished grade instead of natural grade",
      "expected_citation": "SJ-ADU-001",
      "must_catch": true
    }
  ]
}

`page` is 1-indexed and matches the page number in the merged PDF.
`category` must be one of: code | drawing_error | coordination | constructability.
`severity` must be one of: critical | major | minor | advisory.
`must_catch=true` items count toward critical recall (a separate metric).

MATCH LOGIC
-----------
A tool finding matches a ground-truth finding when:
  - same page_number  (or both have page_number = "multiple" for coordination)
  - same category
  - description Jaccard similarity (over normalised word sets) >= 0.30

This is intentionally lenient at the MVP stage. Tighten as the eval set grows
and prompts mature.

OUTPUT
------
Per drawing: recall, precision, F1, list of misses, list of false positives.
Aggregate:   recall/precision/F1 across all drawings + per-category breakdown.
Exit code:   0 always (this is a measurement tool, not a CI gate — yet).
"""

from __future__ import annotations

import argparse
import json
import re
import string
import sys
from pathlib import Path
from typing import Optional

# Make project root importable so we can use ai_reviewer / prompts / etc.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from ai_reviewer import review_full_pdf, _get_client, MODEL  # noqa: E402
from prompts import JURISDICTION_PROMPTS  # noqa: E402
from references_loader import load_references  # noqa: E402


EVAL_DIR = Path(__file__).resolve().parent
DRAWINGS_DIR = EVAL_DIR / "drawings"
GROUND_TRUTH_DIR = EVAL_DIR / "ground_truth"
CACHE_DIR = EVAL_DIR / "_cache"

VALID_SEVERITIES = {"critical", "major", "minor", "advisory"}
VALID_CATEGORIES = {"code", "drawing_error", "coordination", "constructability"}

# Asymmetric similarity: what fraction of GT keywords appear in the tool description?
# Better than Jaccard for our case because GT findings are terse (5-8 words) while
# AI findings are verbose (20-30 words). Jaccard punishes verbosity unfairly.
MATCH_CONTAINMENT_THRESHOLD = 0.40
# GT findings with fewer than this many distinct content words are skipped from
# matching (too short — anything would match). Their misses are reported separately.
MIN_GT_KEYWORDS = 3


# ─────────────────────────────────────────────────────────────────────────────
# Ground-truth loading + validation
# ─────────────────────────────────────────────────────────────────────────────

def _load_ground_truth(gt_path: Path) -> dict:
    raw = json.loads(gt_path.read_text(encoding="utf-8"))
    findings = raw.get("findings", [])
    if not isinstance(findings, list):
        raise ValueError(f"{gt_path.name}: 'findings' must be a list")
    for i, f in enumerate(findings):
        if not isinstance(f, dict):
            raise ValueError(f"{gt_path.name}: finding[{i}] must be an object")
        for required in ("id", "page", "category", "description"):
            if required not in f:
                raise ValueError(f"{gt_path.name}: finding[{i}] missing '{required}'")
        if f["category"] not in VALID_CATEGORIES:
            raise ValueError(
                f"{gt_path.name}: finding[{i}] category {f['category']!r} not in "
                f"{sorted(VALID_CATEGORIES)}"
            )
        if "severity" in f and f["severity"] not in VALID_SEVERITIES:
            raise ValueError(
                f"{gt_path.name}: finding[{i}] severity {f['severity']!r} not in "
                f"{sorted(VALID_SEVERITIES)}"
            )
    return raw


def _enumerate_eval_set() -> list[tuple[Path, Path]]:
    """Return [(drawing_path, ground_truth_path), ...] for every PDF that has a label file."""
    if not DRAWINGS_DIR.is_dir():
        return []
    pairs: list[tuple[Path, Path]] = []
    for pdf in sorted(DRAWINGS_DIR.glob("*.pdf")):
        gt = GROUND_TRUTH_DIR / f"{pdf.stem}.json"
        if not gt.is_file():
            print(f"  ! skipping {pdf.name} — no ground-truth file at {gt.name}")
            continue
        pairs.append((pdf, gt))
    return pairs


# ─────────────────────────────────────────────────────────────────────────────
# Matching tool-findings against ground-truth findings
# ─────────────────────────────────────────────────────────────────────────────

_PUNCT_TABLE = str.maketrans("", "", string.punctuation)
_STOPWORDS = {
    "the", "a", "an", "of", "and", "or", "for", "to", "is", "in", "on", "at",
    "with", "by", "as", "be", "this", "that", "it", "its", "from", "must",
    "should", "shall", "may", "not", "no",
}


def _normalize_words(text: str) -> set[str]:
    s = (text or "").lower().translate(_PUNCT_TABLE)
    return {w for w in s.split() if w and w not in _STOPWORDS and len(w) > 1}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _containment(gt_words: set[str], tool_words: set[str]) -> float:
    """Fraction of GT keywords that appear in the tool description.

    Asymmetric — designed for terse GT vs. verbose AI prose. A high containment
    score means 'the AI mentioned the key concepts the architect wrote down',
    regardless of whether the AI added a lot of additional context.
    """
    if not gt_words:
        return 0.0
    return len(gt_words & tool_words) / len(gt_words)


def _normalize_sheet_id(sid) -> str:
    """Lowercase, strip, collapse internal whitespace so 'AA 1.1' and 'aa 1.1' match."""
    return re.sub(r"\s+", " ", str(sid or "").strip().lower())


def _build_sheet_to_pages(facts_per_page: list[dict]) -> dict[str, list[int]]:
    """From the audit's facts_per_page, build {normalized_sheet_id: [page_numbers]}.

    Multiple pages may map to the same sheet_id (rare — usually a per-page
    title-block mistake on the architect's side, but the eval should be tolerant).
    """
    out: dict[str, list[int]] = {}
    for entry in facts_per_page or []:
        pn = entry.get("page_number")
        facts = entry.get("facts") or {}
        sid = facts.get("sheet_id")
        if isinstance(pn, int) and pn > 0 and sid:
            key = _normalize_sheet_id(sid)
            out.setdefault(key, []).append(pn)
    return out


def _same_locus(tool_page, gt_page, gt_pages, gt_sheet_id, sheet_to_pages) -> bool:
    """Whether a tool finding and a GT finding refer to the same locus.

    Resolution order (any one is sufficient):
      1. GT has an explicit page list and tool's page is in it.
      2. GT has a single numeric page and tool's page matches.
      3. GT has a sheet_id and the AI extracted a matching sheet_id from tool's page.
      4. Both sides are coordination ("multiple").
    """
    # 1. Explicit page-list match (preferred — survives when AI fails to extract sheet_id)
    if gt_pages and isinstance(tool_page, int) and tool_page in gt_pages:
        return True
    # 2. Single-page numeric match
    if isinstance(tool_page, int) and isinstance(gt_page, int) and tool_page == gt_page:
        return True
    # 3. Dynamic sheet_id bridge from facts_per_page
    if gt_sheet_id:
        target_pages = sheet_to_pages.get(_normalize_sheet_id(gt_sheet_id), [])
        if isinstance(tool_page, int) and tool_page in target_pages:
            return True
    # 4. Cross-sheet coordination
    if isinstance(tool_page, str) and tool_page.lower().startswith("mult"):
        if isinstance(gt_page, str) and gt_page.lower().startswith("mult"):
            return True
    return False


def _llm_judge_page_matches(gt_for_page: list[dict], tool_for_page: list[dict], page_label: str) -> dict[int, int]:
    """Use the LLM to identify GT↔tool matches on a single page.

    Returns {gt_idx_in_input: tool_idx_in_input} for confident matches.
    One API call per page-bucket; designed to be cheap.

    Cost: ~$0.01-$0.03 per call (text-only, gpt vision model). With 10 reviewed
    sheets in the Mann set, total judge cost = ~$0.30.

    Failure-tolerant: returns {} if the call fails or the model returns
    malformed output. Caller treats unmatched as misses.
    """
    if not gt_for_page or not tool_for_page:
        return {}

    # Build the prompt
    gt_block = "\n".join(
        f"  G{i}: [{g.get('category','?')}/{g.get('severity','?')}] {g.get('description','').strip()}"
        for i, g in enumerate(gt_for_page)
    )
    tool_block = "\n".join(
        f"  T{i}: [{t.get('category','?')}/{t.get('severity','?')}] {(t.get('description') or '').strip()}"
        for i, t in enumerate(tool_for_page)
    )
    prompt = f"""You are matching plan-check findings between two sources for the same drawing page.

LIST G — ground-truth findings written by a senior architect:
{gt_block}

LIST T — findings flagged by an AI plan-check tool:
{tool_block}

Identify pairs (G_i, T_j) that describe the SAME plan-check issue. Two findings match if:
- They reference the same defect, missing item, or coordination problem on this sheet
- One could be a paraphrase or expansion of the other
- They concern the same scope (same room, same dimension, same note, etc.)

Do NOT match items that are merely on the same general topic but describe different defects.
Each G can match at most one T, and vice versa.

Return STRICTLY JSON:
{{
  "matches": [
    {{"g": 0, "t": 3, "confidence": "high|medium|low"}},
    ...
  ]
}}

Only include matches you are confident in (medium or high). If no matches, return {{"matches": []}}.
"""

    try:
        client = _get_client()
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content or "{}")
        matches = data.get("matches", [])
        result: dict[int, int] = {}
        for m in matches:
            if not isinstance(m, dict):
                continue
            if (m.get("confidence") or "low").lower() == "low":
                continue
            g, t = m.get("g"), m.get("t")
            if isinstance(g, int) and isinstance(t, int) and 0 <= g < len(gt_for_page) and 0 <= t < len(tool_for_page):
                # First match wins (model already de-dupes but defensive)
                if g not in result and t not in result.values():
                    result[g] = t
        return result
    except Exception as exc:
        print(f"  ! judge call failed for {page_label}: {exc}")
        return {}


def _match_findings(
    tool_findings: list[dict],
    gt_findings: list[dict],
    facts_per_page: list[dict] | None = None,
    use_llm_judge: bool = True,
) -> dict:
    """Greedy-match every GT finding to the best unmatched tool finding.

    Returns: {
        'matched_pairs': [(gt, tool, score), ...],
        'missed_gt': [gt, ...],
        'false_positive_tool': [tool, ...],
    }
    """
    sheet_to_pages = _build_sheet_to_pages(facts_per_page or [])

    if use_llm_judge:
        return _match_findings_with_judge(tool_findings, gt_findings, sheet_to_pages)

    # Lexical fallback path — kept for debugging / offline runs
    available_tool = list(range(len(tool_findings)))
    matched_pairs: list[tuple[dict, dict, float]] = []
    missed: list[dict] = []

    for gt in gt_findings:
        gt_words = _normalize_words(gt.get("description", ""))
        gt_cat = gt.get("category")
        gt_sheet_id = gt.get("sheet_id")
        gt_pages = gt.get("pages") or []
        if len(gt_words) < MIN_GT_KEYWORDS:
            missed.append(gt)
            continue
        best_idx: Optional[int] = None
        best_score = 0.0
        for idx in available_tool:
            tf = tool_findings[idx]
            cat_match = tf.get("category") == gt_cat
            if not _same_locus(tf.get("page_number"), gt.get("page"), gt_pages, gt_sheet_id, sheet_to_pages):
                continue
            raw_score = _containment(gt_words, _normalize_words(tf.get("description", "")))
            score = raw_score if cat_match else raw_score * 0.80
            if score >= MATCH_CONTAINMENT_THRESHOLD and score > best_score:
                best_idx = idx
                best_score = score
        if best_idx is not None:
            matched_pairs.append((gt, tool_findings[best_idx], best_score))
            available_tool.remove(best_idx)
        else:
            missed.append(gt)

    false_positives = [tool_findings[i] for i in available_tool]
    return {
        "matched_pairs": matched_pairs,
        "missed_gt": missed,
        "false_positive_tool": false_positives,
    }


def _match_findings_with_judge(
    tool_findings: list[dict],
    gt_findings: list[dict],
    sheet_to_pages: dict[str, list[int]],
) -> dict:
    """Group findings by page-bucket and use the LLM judge to find matches.

    A 'page bucket' is the set of pages a GT finding could live on (its pages list).
    Two GT findings share a bucket if their pages-lists are identical. This keeps
    judge calls small and avoids cross-contamination between unrelated sheets.
    """
    # Index GT findings by their pages-list (as a sortable tuple)
    gt_buckets: dict[tuple[int, ...], list[int]] = {}
    for gi, gt in enumerate(gt_findings):
        pages = tuple(sorted(gt.get("pages") or []))
        if not pages:
            # Cross-sheet (page="multiple") and unscoped GT findings → "all" bucket
            pages = ("multiple",) if (gt.get("page") == "multiple") else ()
        gt_buckets.setdefault(pages, []).append(gi)

    matched_pairs: list[tuple[dict, dict, float]] = []
    matched_tool_idxs: set[int] = set()
    matched_gt_idxs: set[int] = set()

    for pages_key, gt_indices in gt_buckets.items():
        if not pages_key:
            continue  # no pages — skip
        if pages_key == ("multiple",):
            # Coordination bucket — tool findings with page_number="multiple"
            tool_indices = [ti for ti, tf in enumerate(tool_findings)
                            if tf.get("page_number") == "multiple" and ti not in matched_tool_idxs]
            page_label = "cross-sheet"
        else:
            tool_indices = [ti for ti, tf in enumerate(tool_findings)
                            if isinstance(tf.get("page_number"), int)
                            and tf.get("page_number") in pages_key
                            and ti not in matched_tool_idxs]
            page_label = f"page{'s' if len(pages_key) > 1 else ''} {','.join(str(p) for p in pages_key)}"

        if not tool_indices:
            continue

        gt_for_bucket = [gt_findings[gi] for gi in gt_indices]
        tool_for_bucket = [tool_findings[ti] for ti in tool_indices]
        print(f"  judging {page_label}: {len(gt_for_bucket)} GT × {len(tool_for_bucket)} tool", flush=True)
        pairs = _llm_judge_page_matches(gt_for_bucket, tool_for_bucket, page_label)

        for local_g, local_t in pairs.items():
            global_g = gt_indices[local_g]
            global_t = tool_indices[local_t]
            if global_g in matched_gt_idxs or global_t in matched_tool_idxs:
                continue
            matched_pairs.append((gt_findings[global_g], tool_findings[global_t], 1.0))
            matched_gt_idxs.add(global_g)
            matched_tool_idxs.add(global_t)

    missed = [gt_findings[gi] for gi in range(len(gt_findings)) if gi not in matched_gt_idxs]
    false_positives = [tool_findings[ti] for ti in range(len(tool_findings)) if ti not in matched_tool_idxs]

    return {
        "matched_pairs": matched_pairs,
        "missed_gt": missed,
        "false_positive_tool": false_positives,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Metrics
# ─────────────────────────────────────────────────────────────────────────────

def _metrics_from_match(match_result: dict, total_tool: int, total_gt: int) -> dict:
    tp = len(match_result["matched_pairs"])
    fn = len(match_result["missed_gt"])
    fp = len(match_result["false_positive_tool"])
    recall = tp / total_gt if total_gt else 0.0
    precision = tp / total_tool if total_tool else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "tp": tp, "fn": fn, "fp": fp,
        "recall": recall, "precision": precision, "f1": f1,
    }


def _category_breakdown(match_results: list[dict], gt_findings_all: list[dict],
                        tool_findings_all: list[dict]) -> dict:
    """Per-category recall/precision across all drawings."""
    by_cat: dict[str, dict] = {}
    for cat in VALID_CATEGORIES:
        gt_for_cat = [f for f in gt_findings_all if f.get("category") == cat]
        tool_for_cat = [f for f in tool_findings_all if f.get("category") == cat]
        tp = 0
        for r in match_results:
            for gt, _tf, _s in r["matched_pairs"]:
                if gt.get("category") == cat:
                    tp += 1
        recall = tp / len(gt_for_cat) if gt_for_cat else None
        precision = tp / len(tool_for_cat) if tool_for_cat else None
        by_cat[cat] = {
            "tp": tp,
            "total_gt": len(gt_for_cat),
            "total_tool": len(tool_for_cat),
            "recall": recall,
            "precision": precision,
        }
    return by_cat


# ─────────────────────────────────────────────────────────────────────────────
# Main run loop
# ─────────────────────────────────────────────────────────────────────────────

def _pct(x: Optional[float]) -> str:
    if x is None:
        return "  —  "
    return f"{x*100:5.1f}%"


def _short(text: str, max_len: int = 70) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


def _cache_path_for(pdf: Path) -> Path:
    return CACHE_DIR / f"{pdf.stem}.audit.json"


def _load_or_run_audit(pdf: Path, addendum: str, force_rerun: bool) -> dict:
    """Audit result cache.

    First run: invokes review_full_pdf (paid OpenAI call), writes the full result
    to eval/_cache/<basename>.audit.json, returns the dict.

    Subsequent runs: loads from cache (free, instant). This lets us iterate on
    the matcher / GT JSON / matcher thresholds without paying for re-audits.
    Pass force_rerun=True to bypass the cache.
    """
    cache_path = _cache_path_for(pdf)
    if not force_rerun and cache_path.exists():
        print(f"  (cache hit — loading audit from {cache_path.relative_to(EVAL_DIR.parent)})")
        return json.loads(cache_path.read_text(encoding="utf-8"))

    pdf_bytes = pdf.read_bytes()
    result = review_full_pdf(pdf_bytes, jurisdiction_addendum=addendum)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  (audit cached → {cache_path.relative_to(EVAL_DIR.parent)})")
    return result


def run(single: Optional[str] = None, dry_run: bool = False, force_rerun: bool = False) -> None:
    pairs = _enumerate_eval_set()
    if single is not None:
        pairs = [p for p in pairs if p[0].name == single]
        if not pairs:
            print(f"No eval pair found for {single!r}. "
                  f"Available: {[p[0].name for p in _enumerate_eval_set()]}")
            return

    if not pairs:
        print("No eval pairs found.")
        print(f"  Add drawings to:    {DRAWINGS_DIR}")
        print(f"  Add ground truth to: {GROUND_TRUTH_DIR}")
        print("  See the docstring at the top of this file for the JSON schema.")
        return

    # In dry-run mode just validate ground truth and exit
    if dry_run:
        print(f"DRY RUN — found {len(pairs)} eval pair(s):")
        for pdf, gt in pairs:
            try:
                data = _load_ground_truth(gt)
                print(f"  ✓ {pdf.name}  ({len(data.get('findings', []))} GT findings)")
            except Exception as exc:
                print(f"  ✗ {pdf.name}  — {exc}")
        return

    # Pick the jurisdiction addendum — single-jurisdiction project
    addendum = JURISDICTION_PROMPTS.get("Cupertino (city + state)", "")
    refs = load_references("Cupertino (city + state)")
    if refs.get("block"):
        addendum = addendum + "\n\n" + refs["block"]

    all_match_results: list[dict] = []
    all_gt: list[dict] = []
    all_tool: list[dict] = []

    for pdf, gt_path in pairs:
        print(f"\n── {pdf.name} ──")
        try:
            gt_data = _load_ground_truth(gt_path)
        except Exception as exc:
            print(f"  ✗ ground-truth invalid: {exc}")
            continue
        gt_findings = gt_data.get("findings", [])

        try:
            result = _load_or_run_audit(pdf, addendum, force_rerun=force_rerun)
            tool_findings = result.get("findings", [])
            facts_per_page = result.get("facts_per_page", [])
        except Exception as exc:
            print(f"  ✗ audit failed: {exc}")
            continue

        match = _match_findings(tool_findings, gt_findings, facts_per_page=facts_per_page)
        metrics = _metrics_from_match(match, len(tool_findings), len(gt_findings))

        print(f"  GT findings: {len(gt_findings):>3}   |   Tool findings: {len(tool_findings):>3}")
        print(f"  TP={metrics['tp']}  FN={metrics['fn']}  FP={metrics['fp']}")
        print(f"  Recall: {_pct(metrics['recall'])}   Precision: {_pct(metrics['precision'])}   F1: {metrics['f1']:.2f}")

        if match["missed_gt"]:
            print("  Missed (GT not caught by tool):")
            for gt in match["missed_gt"]:
                print(f"    - {gt.get('id', '?')}  p{gt.get('page','?')} "
                      f"{gt.get('category','?'):<14}  {_short(gt.get('description',''))}")
        if match["false_positive_tool"]:
            print("  False positives (tool flagged, not in GT):")
            for tf in match["false_positive_tool"][:10]:  # cap to top 10
                print(f"    - p{tf.get('page_number','?')}  "
                      f"{tf.get('category','?'):<14}  {_short(tf.get('description',''))}")
            extra = len(match["false_positive_tool"]) - 10
            if extra > 0:
                print(f"    … and {extra} more")

        all_match_results.append(match)
        all_gt.extend(gt_findings)
        all_tool.extend(tool_findings)

    # ─── Aggregate ───
    print("\n══════ AGGREGATE ══════")
    agg = {
        "tp": sum(len(r["matched_pairs"]) for r in all_match_results),
        "fn": sum(len(r["missed_gt"]) for r in all_match_results),
        "fp": sum(len(r["false_positive_tool"]) for r in all_match_results),
    }
    tot_gt = len(all_gt)
    tot_tool = len(all_tool)
    recall = agg["tp"] / tot_gt if tot_gt else 0.0
    precision = agg["tp"] / tot_tool if tot_tool else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    print(f"  Drawings: {len(all_match_results)}  |  GT: {tot_gt}  |  Tool: {tot_tool}")
    print(f"  TP={agg['tp']}  FN={agg['fn']}  FP={agg['fp']}")
    print(f"  Recall: {_pct(recall)}   Precision: {_pct(precision)}   F1: {f1:.2f}")

    breakdown = _category_breakdown(all_match_results, all_gt, all_tool)
    print("\n  By category:")
    print(f"  {'category':<18} {'GT':>4} {'tool':>5} {'TP':>4}   {'recall':>7} {'prec':>7}")
    for cat, m in breakdown.items():
        print(f"  {cat:<18} {m['total_gt']:>4} {m['total_tool']:>5} {m['tp']:>4}   "
              f"{_pct(m['recall']):>7} {_pct(m['precision']):>7}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Eval PlanCheck against labeled ground-truth")
    parser.add_argument("--single", help="Run only one drawing by filename (e.g. burns_way_adu.pdf)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate ground-truth files without running the audit")
    parser.add_argument("--force-rerun", action="store_true",
                        help="Ignore the audit cache and re-run the OpenAI audit (costs ~$0.05/page).")
    args = parser.parse_args()
    run(single=args.single, dry_run=args.dry_run, force_rerun=args.force_rerun)


if __name__ == "__main__":
    main()
