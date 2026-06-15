# San Jose ADU rules — curated audit library

<!--
HOW TO USE THIS FILE

This file is auto-loaded into every audit prompt (no restart needed).
Each rule below is fed to the AI as authoritative SJ ADU guidance.

Rule schema — copy this block when adding a new rule:

## SJ-ADU-XXX — Short rule title
- **Citation**: code section(s)
- **Applies to**: which ADU types / zones / conditions
- **Severity**: critical | major | minor | advisory
- **Visual cue**: where on the drawing the AI should look
- **Rule**: the enforceable rule, in plain English
- **Failure pattern**: how architects typically get this wrong (firm history)
- **Recommendation**: what to do about it

Tips for high-recall rules:
- ONE rule per ## block. Smaller rules are caught more reliably than long ones.
- "Visual cue" tells the AI WHERE to look (which sheet type / which region).
- "Failure pattern" is your firm's gold — what you've seen go wrong on real projects.
  This is what separates this tool from a generic AI-with-codebook.
- Cite a specific code section only if you've verified it exists in the current cycle.

Target: 30 curated SJ ADU rules. Start with the ~10 highest-volume corrections
your firm sees from SJ Planning, then expand. Re-run eval/eval.py after each
batch to measure recall improvement.
-->


## SJ-ADU-001 — Detached ADU height measured from natural grade
- **Citation**: SJ Municipal Code §20.30.040(D); CA Gov Code §65852.2(a)(1)(D)
- **Applies to**: Detached ADUs in R-1, R-2, R-M zones
- **Severity**: critical
- **Visual cue**: Elevations on all four sides — look for the height annotation and the reference line it's measured from. The grade reference is usually labeled "NATURAL GRADE", "EXISTING GRADE", or "FINISHED GRADE".
- **Rule**: Detached single-story ADU shall not exceed 16 ft from **natural grade** to top of roof. (18 ft if within 4 ft of side/rear setback; up to 25 ft if attached to primary residence and matches its height.)
- **Failure pattern**: Architects sometimes measure from finished grade (post-cut/fill) instead of natural grade, which can hide a 1–2 ft height violation. Or measure to mid-point of roof instead of top of roof. Or omit the grade reference entirely.
- **Recommendation**: State height in every elevation; explicitly label which grade is being measured from. If the lot was graded, show natural grade as a dashed line for comparison.


## SJ-ADU-002 — ADU rear/side setback minimum
- **Citation**: SJ Municipal Code §20.30.040(C); CA Gov Code §65852.2(a)(1)(D)
- **Applies to**: Detached and converted ADUs in all residential zones
- **Severity**: critical
- **Visual cue**: Site plan — look for setback dimensions from rear and each side property line to the nearest face of the ADU wall.
- **Rule**: State-mandated ADU setbacks are 4 ft minimum from side and rear property lines. The city CANNOT require more for a state-mandated ADU. Front setback follows the underlying zone for the primary residence.
- **Failure pattern**: Older drawings carry over pre-AB 68 setbacks (5 ft or zone-based) and trigger an unnecessary correction. Or the setback is measured from the wrong reference (fence line vs. property line).
- **Recommendation**: Dimension all setbacks from property line (not fence, curb, or building face of primary). Include a note on the site plan: "ADU setbacks per CA state ADU law — 4 ft side/rear minimum, exempt from underlying zone setbacks."


<!--
Add more rules below using the schema. Each starts with `## SJ-ADU-NNN — title`.

Areas to cover (priority order based on typical SJ Planning correction patterns):
1. ADU floor area limits (1,200 sf state ceiling; SJ may further limit by lot size)
2. JADU rules (≤ 500 sf, owner-occupancy, shared/efficiency kitchen)
3. Parking — no replacement required per AB 68
4. Egress — bedroom EERO size + sill height (CRC R310)
5. Ceiling heights — habitable spaces 7 ft min (CRC R305)
6. Stair geometry — risers ≤ 7.75", treads ≥ 10" (CRC R311.7)
7. Smoke + CO alarms — locations per CRC R314 / R315
8. Title 24 — CF-1R compliance form attached/referenced
9. Solar PV — new ADUs over X sf trigger Title 24 §10-115 (verify current edition)
10. Stormwater — impervious area calc for projects ≥ 2,500 sf disturbance
11. Heritage Trees — SJMC §13.28 protection requirements
12. Hillside lots — slope analysis required ≥ 10% slope
13. Fire — sprinklers required when primary has them; verify per SJ Fire requirements
14. Utility connections — separate vs. shared with primary
15. Permit drawings — minimum sheet set + scale standards
... continue.
-->
