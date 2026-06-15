# Cupertino-specific residential rules (deferred — not auto-loaded)

<!--
This file lives in references/_deferred/ which the loader skips. It is
preserved for the eventual Cupertino expansion phase, after the SJ wedge
is dominated. To re-activate:

  1. Move this file to references/ root (drop the _deferred/ prefix).
  2. Add "Cupertino (city + state)" to JURISDICTION_LABELS in app.py.
  3. Ensure JURISDICTION_PROMPTS in prompts.py has a Cupertino addendum
     (or use the SJ one with CMC overlay).
  4. Restart Streamlit.

Source: rules SJ-CUP-001 through SJ-CUP-007 distilled from the
10350 Mann Drive QA/QC pre-submittal review (208 findings).
-->


## SJ-CUP-001 — Cupertino R1-10 zone setbacks
- **Citation**: Cupertino Municipal Code §19.28.060
- **Applies to**: Single-family residential in R1-10 zone
- **Severity**: critical
- **Visual cue**: Site plan setback dimensions; cover sheet zoning summary
- **Rule**: R1-10 minimum setbacks: front 20'-0" (interior R1), each side 5'-0" ground floor / 10'-0" total combined, rear per CMC table. Verify against the current CMC chapter for any side- or front-setback exceptions (corner lots, etc.).
- **Failure pattern**: Designer uses SJ setbacks (different) or quotes "Per Santa Clara County" (also wrong for incorporated Cupertino).
- **Recommendation**: Always cite "CMC §19.28.060" for R1-10 setbacks; do not generalize as "Per Santa Clara".


## SJ-CUP-002 — Cupertino max building height (R1)
- **Citation**: Cupertino Municipal Code §19.28.060
- **Applies to**: Single-family residential in R1 zones
- **Severity**: critical
- **Visual cue**: Elevations; cover sheet zoning summary
- **Rule**: Maximum building height for SFR in R1 zones is 30'-0" per CMC §19.28.060. Height is measured per CMC's height-measurement definition (usually from average natural grade — verify current).
- **Failure pattern**: Designer cites a different height limit (SJ uses different rules), or doesn't dimension height in elevations.
- **Recommendation**: Dimension max-height in all four elevations from average natural grade.


## SJ-CUP-003 — Cupertino max lot coverage (R1-10)
- **Citation**: Cupertino Municipal Code §19.28.060
- **Applies to**: Single-family residential in R1-10 zone
- **Severity**: major
- **Visual cue**: Cover sheet zoning summary; lot-coverage calc on AA 2.2
- **Rule**: Maximum lot coverage in R1-10 is 45% of lot area. Lot-coverage calc must be shown with: lot area, footprint area, percentage, governing limit.
- **Failure pattern**: Lot coverage calc missing or uses wrong lot area (see SJ-RES-007).
- **Recommendation**: Show calc explicitly: lot area × 0.45 = max footprint; proposed footprint ÷ lot area = proposed %.


## SJ-CUP-004 — Cupertino daylight plane measured from property line
- **Citation**: Cupertino Municipal Code §19.28.060
- **Applies to**: SFR in R1 zones
- **Severity**: major
- **Visual cue**: Daylight plane line drawn on AA 1.1; setback origin
- **Rule**: Daylight plane is measured FROM THE PROPERTY LINE per CMC §19.28.060, not from the building face or from a setback line. Confirm the angle and starting height per current CMC table.
- **Failure pattern**: Daylight plane drawn from the wrong origin (setback line instead of property line), or starting height is wrong.
- **Recommendation**: Verify against the current CMC table at every project — Cupertino has tweaked the daylight plane formula several times.


## SJ-CUP-005 — Cupertino Heritage Tree Ordinance
- **Citation**: Cupertino Municipal Code §14.18
- **Applies to**: Any project with trees on the site
- **Severity**: major
- **Visual cue**: Site plan tree symbols + diameters; arborist report
- **Rule**: Heritage trees under CMC §14.18 require a separate permit process. Protected species and trunk-diameter thresholds are listed in the ordinance — verify against the current version. Removal of a heritage tree requires a separate application; replacement trees may be required.
- **Failure pattern**: Designer treats heritage trees as ordinary trees, omits the heritage permit reference, or doesn't flag the trunk diameter against the heritage threshold.
- **Recommendation**: For every tree shown on the survey, check trunk diameter against the CMC §14.18 heritage threshold. If at or above, file the separate heritage permit application.


## SJ-CUP-006 — Cupertino all-electric reach code
- **Citation**: Cupertino Municipal Code §16.54 (verify current section; older section 16.32 was suspended)
- **Applies to**: New single-family residential construction
- **Severity**: critical
- **Visual cue**: Cover sheet code-basis block; mechanical/plumbing/electrical specs; gas-related callouts
- **Rule**: Cupertino requires new SFR to be all-electric (no gas appliances or gas piping). Verify the current applicable section number — section 16.32 was suspended at one point and the current mandate is in 16.54.100 or its successor. Cite the CURRENT in-force section.
- **Failure pattern**: Code notes cite a suspended section number; or drawings show gas appliances (fireplace, tankless water heater, range, dryer hookup) on a project subject to all-electric.
- **Recommendation**: Verify the current section number with Cupertino Planning before submittal. Audit every mechanical / plumbing / electrical spec for gas references; all must be electric.


## SJ-CUP-007 — Cupertino construction hours
- **Citation**: Cupertino Municipal Code noise ordinance (verify current section)
- **Applies to**: Construction-hours note on general-notes sheet
- **Severity**: major
- **Visual cue**: Construction-hours note text
- **Rule**: Construction hours in Cupertino are restricted by the municipal noise ordinance — verify the current allowable hours for weekdays, Saturdays, and Sundays/holidays. Cupertino's hours may differ from neighboring cities.
- **Failure pattern**: Designer carries forward another city's construction-hours note (Sunnyvale, SJ, Mountain View — all different from Cupertino).
- **Recommendation**: Verify current allowable hours with Cupertino PW; cite the specific CMC noise-ordinance section in the note.
