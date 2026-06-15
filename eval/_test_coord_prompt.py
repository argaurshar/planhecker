"""One-shot experiment: re-run coordination_check against cached facts with the
new evidence-string-constrained prompt. Costs ~$0.02. Writes the new
coordination findings to eval/_render_check/new_coord_findings.json.

Usage:
    venv\\Scripts\\python.exe eval/_test_coord_prompt.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from ai_reviewer import coordination_check  # noqa: E402
from prompts import JURISDICTION_PROMPTS  # noqa: E402
from references_loader import load_references  # noqa: E402


def main() -> None:
    cache_path = Path("eval/_cache/mann_3.audit.json")
    if not cache_path.exists():
        print(f"Cache not found at {cache_path}. Run the eval first.")
        return

    data = json.loads(cache_path.read_text(encoding="utf-8"))
    facts_per_page = data.get("facts_per_page", [])
    print(f"Loaded cached facts for {len(facts_per_page)} pages")

    addendum = JURISDICTION_PROMPTS.get("Cupertino (city + state)", "")
    refs = load_references("Cupertino (city + state)")
    if refs.get("block"):
        addendum = addendum + "\n\n" + refs["block"]

    print("Re-running coordination_check with new evidence-string prompt...")
    findings = coordination_check(facts_per_page, jurisdiction_addendum=addendum)
    print(f"Got {len(findings)} coordination findings")

    out_path = Path("eval/_render_check/new_coord_findings.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(findings, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {out_path}")

    # Print summary
    print()
    print("=" * 70)
    print("NEW COORDINATION FINDINGS (with evidence-string constraint)")
    print("=" * 70)
    for i, f in enumerate(findings, 1):
        print(f"\n[{i}] {f.get('severity','?').upper()} — confidence: {f.get('confidence','?')}")
        print(f"    sheets: {f.get('sheets_involved', [])}")
        print(f"    pages:  {f.get('pages_involved', [])}")
        print(f"    desc:   {f.get('description','')}")
        print(f"    A:      {f.get('evidence_a_quote','')}")
        print(f"    B:      {f.get('evidence_b_quote','')}")
        print(f"    full evidence: {f.get('evidence','')}")


if __name__ == "__main__":
    main()
