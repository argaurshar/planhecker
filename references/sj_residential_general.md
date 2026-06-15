# Universal CA residential rules — non-ADU (additions, remodels, new SFR)

<!--
NOTE — file name and "SJ-RES" prefix are HISTORICAL.

This file was created when the tool was scoped to San Jose. The tool was
flipped to Cupertino on 2026-05-21 (firm's actual project work is mostly
Cupertino, not SJ). The rules in this file are UNIVERSAL CA residential
patterns — they apply to Cupertino (current wedge), San Jose (deferred),
Saratoga (deferred), and any other CA jurisdiction. The SJ-RES-NNN prefix
is preserved to avoid breaking references in commit history; it does NOT
mean these are SJ-only rules.

For Cupertino-specific rules (CMC §19.28, §14.18, §16.54), see cupertino_rules.md.
For pure code-of-conduct rules, see _general.md and california_state.md.

RULE SCHEMA — every rule below uses this structure:

## SJ-RES-XXX — Short rule title
- **Citation**: code section(s)
- **Applies to**: which project types / zones / conditions
- **Severity**: critical | major | minor | advisory
- **Visual cue**: where on the drawing the AI should look
- **Rule**: the enforceable rule, in plain English
- **Failure pattern**: how architects typically get this wrong (firm history)
- **Recommendation**: what to do about it

Many of these rules are UNIVERSAL CA residential — they apply to any
jurisdiction in California, not just SJ. They're collected here because the
tool is currently SJ-narrowed. When the tool re-expands, these rules continue
to apply to the new jurisdictions without modification.

Source for the bulk of rules SJ-RES-002 through SJ-RES-026: the
10350 Mann Drive (Cupertino) QA/QC pre-submittal review — 208 findings,
208/10 sheets, distilled into recurring patterns.
-->


## SJ-RES-001 — Front setback measured from property line, not back-of-curb
- **Citation**: SJ Municipal Code §20.30.030; underlying zone setback table
- **Applies to**: All residential new construction, additions, and front-yard accessory structures
- **Severity**: critical
- **Visual cue**: Site plan — look for the front setback dimension and verify what reference line it's measured to.
- **Rule**: All zone setbacks are measured from the **property line**, not from the back-of-curb, back-of-sidewalk, or building face of adjacent properties. The property line is typically 5–8 ft behind the curb depending on the right-of-way.
- **Failure pattern**: Architects (especially less experienced ones) measure setbacks from the curb because that's what's most visible during a site visit. Sometimes off by 6–10 ft, which triggers a major correction or even a redesign.
- **Recommendation**: Always show the property line clearly on the site plan as a heavy solid line, distinct from the curb (typically a thinner line). Reference a recent survey if available.


## SJ-RES-002 — Title block must say "ISSUED FOR PERMIT" on permit submittal
- **Citation**: AHJ submittal completeness checklist; no specific code section
- **Applies to**: Every sheet on a permit submittal
- **Severity**: critical
- **Visual cue**: Title block / revision block in lower-right corner of each sheet — read the issue/revision label.
- **Rule**: Every sheet must show "ISSUED FOR PERMIT" (or AHJ-equivalent permit-stage label) in the revision block. "PRELIMINARY SET", "WORKING LAYOUT", "DESIGN DEVELOPMENT", or "NOT FOR CONSTRUCTION" stamps must be removed before submittal.
- **Failure pattern**: Designers forget to update the issue stamp from the design-development phase. Plan-check rejects on completeness without even reviewing content.
- **Recommendation**: Audit every sheet's revision block as a final pre-submittal check. The AI tool should flag any sheet where the revision label contains "PRELIMINARY", "WORKING", "NOT FINAL", or "DD-".


## SJ-RES-003 — Code cycle on cover sheet matches the current adopted cycle
- **Citation**: CBC, CRC, CEC, CMC, CPC, CFC, CALGreen — current adopted cycle (California is on a 3-year cycle)
- **Applies to**: Cover sheet; general-notes sheets
- **Severity**: critical
- **Visual cue**: Cover sheet code block; general-notes header references
- **Rule**: The code-cycle year stated on the cover (and any general-notes sheet) must match the cycle currently adopted by the AHJ at the time of submittal. Vesting to a prior cycle is sometimes allowed if the application predates the new cycle's effective date — but it must be explicitly stated and dated.
- **Failure pattern**: Stale templates list the previous cycle (e.g. "2022 CBC" when 2025 is now adopted). Cover says one year, individual notes sheets say another — both flagged.
- **Recommendation**: Update the code-cycle reference on every sheet in the set, not just the cover. If vesting to a prior cycle intentionally, add a "VESTED TO 2022 CYCLE PER APPLICATION DATE [date]" note.


## SJ-RES-004 — Referenced industry standards must be current editions
- **Citation**: ACCA Manual J / D / S; CA MUTCD; 2025 CALGreen tables; CEC editions
- **Applies to**: General-notes and technical-notes sheets; mechanical/energy specs
- **Severity**: major
- **Visual cue**: Notes referencing standards by edition year (e.g. "ACCA Manual J-2004", "2006 CA MUTCD")
- **Rule**: Every cited standard must reference its current edition. Common current editions to verify: ACCA Manual J 8th Ed (2016), ACCA Manual D 4th Ed (2022), ACCA Manual S 2nd Ed (2013), CA MUTCD 2023, current CALGreen / CEC / T24 cycle.
- **Failure pattern**: Office templates carry forward outdated edition years for 10+ years. Plan-check flags them.
- **Recommendation**: Maintain a single "current editions" reference list at the office. Update once per year. Search the drawing set for any standard reference and verify against the list.


## SJ-RES-005 — Strip AI / software template artifacts from drawings
- **Citation**: AHJ submittal completeness; no specific code section
- **Applies to**: Every drawing sheet
- **Severity**: critical
- **Visual cue**: Notes blocks, schedules, marker text; anything that looks like un-customized template content
- **Rule**: Drawings must contain no software-template artifacts: CSV references, "polyline" terms, "[FILL IN HERE]" placeholders, "APN comes from fax", AI editing blocks ("CHANGES AND NOTES"), duplicate text blocks from copy-paste, or template tutorial text.
- **Failure pattern**: AutoCAD / Revit / AI design tools leave template scaffolding in the output. Designer doesn't notice; plan-check does.
- **Recommendation**: Final pre-submittal pass: search every sheet for template phrases. Common offenders: "CSV", "polyline", "fill in", "tutorial", "[insert]", "comes from fax", "CHANGES AND NOTES".


## SJ-RES-006 — No leftover jurisdiction template text from other cities
- **Citation**: AHJ-specific compliance (construction hours, URLs, permits)
- **Applies to**: Cover sheet, general-notes sheets, any sheet with city-specific references
- **Severity**: critical
- **Visual cue**: URLs, contact phone numbers, construction-hours notes, encroachment-permit references, addresses on cover
- **Rule**: All jurisdiction-specific text (city name, construction hours per local noise ordinance, permit-counter URLs, AHJ contacts, fee-schedule references) must reflect the ACTUAL project jurisdiction. No leftover text from prior-project templates (e.g. "Sunnyvale" references on a San Jose project, "Cupertino" references on a Santa Clara project).
- **Failure pattern**: Architects template-from a prior project in a different city and forget to update jurisdiction-specific notes. Plan-check immediately flags it.
- **Recommendation**: At pre-submittal, search every sheet for the names of OTHER cities the firm has worked in. Anything matching another city is suspect.


## SJ-RES-007 — Cross-sheet consistency: lot area must agree everywhere
- **Citation**: Implicit completeness; survey is authoritative
- **Applies to**: Cover sheet, AA 2.1 (existing/demo), AA 2.2 (proposed plot), survey
- **Severity**: critical
- **Visual cue**: Lot area callouts (in SF) on each of: cover, AA 2.1, AA 2.2, survey title block
- **Rule**: The lot area value must be identical across all sheets that state it. The survey is the authoritative source; all other sheets must match the survey, to the exact square foot.
- **Failure pattern**: Designer uses a rounded lot area on the cover (e.g. 10,884) while the survey shows the precise value (10,882). Each derivative calculation (FAR, lot coverage, max GFA) then propagates the error.
- **Recommendation**: Pull lot area from the most recent survey only. Update every sheet's reference. If lot area changes (lot-line adjustment, new survey), re-run all derivative zoning calcs.


## SJ-RES-008 — Cross-sheet consistency: setback dimensions agree everywhere
- **Citation**: Implicit completeness; underlying zone setback table
- **Applies to**: Cover sheet, AA 1.1 (daylight plane), AA 2.2 (proposed plot)
- **Severity**: critical
- **Visual cue**: Setback dimensions (front, rear, each side) called out on each sheet
- **Rule**: Setback dimensions on the cover sheet, AA 1.1 (daylight plane), and AA 2.2 (proposed plot) must agree to the inch. Discrepancies between sheets are a coordination-pass red flag.
- **Failure pattern**: Cover sheet quotes a round-number setback (7'-6") while the actual proposed plot shows fractional values (18'-11", 23'-2 1/4"). The discrepancy means either the cover is wrong, the plot is wrong, or the designer didn't reconcile them.
- **Recommendation**: Setbacks should be calculated once (from the proposed plot) and copied to every other sheet that mentions them.


## SJ-RES-009 — Cross-sheet consistency: FFL, pad elevation, and grade references must reconcile
- **Citation**: Implicit completeness; survey/civil benchmarks are authoritative
- **Applies to**: AA 1.1 (sections/elevations), AA 2.2 (proposed plot), C-1 (civil grading), Survey
- **Severity**: major
- **Visual cue**: Finish Floor Level (FFL), pad elevation, top-of-curb (TC), top-of-walk references on each sheet
- **Rule**: Finish-floor level (FFL), pad elevation, and any "subfloor above curb" claim must reconcile across architectural and civil sheets. The civil benchmark is authoritative; architectural sheets must tie to it.
- **Failure pattern**: AA 1.1 says "subfloor 15-3/4" above curb", AA 2.2 says "FFL 313.75", C-1 says "FF 313.50". The numbers don't add up because they were drawn separately and never cross-checked.
- **Recommendation**: Set one FFL value in coordination with civil before drawing elevations. Use the same value everywhere. State the datum (NAVD88 or assumed) on the cover sheet.


## SJ-RES-010 — Cross-sheet consistency: room and patio area dimensions agree across plans
- **Citation**: Implicit completeness
- **Applies to**: Cover sheet area summary, AA 2.2 (plot plan), AA 2.4 (floor plan)
- **Severity**: major
- **Visual cue**: Patio / porch / garage / room area tables on cover; same areas on AA 2.2 / AA 2.4
- **Rule**: Areas declared on the cover sheet's project-summary table must match the values shown on AA 2.2 (plot plan) and AA 2.4 (floor plan). Same value, same component, every sheet.
- **Failure pattern**: Covered porch shows 819 SF on cover, 1,019 SF on AA 2.2, 928 SF on AA 2.4. Three different values for the same component.
- **Recommendation**: Have a single source-of-truth area table (typically AA 2.4). All other sheets cite that source verbatim. Re-verify after any plan revision.


## SJ-RES-011 — Easements on survey must appear on architectural plans
- **Citation**: Implicit completeness; survey is authoritative
- **Applies to**: Site plan, plot plan, civil sheets
- **Severity**: major
- **Visual cue**: Easement notations on survey; corresponding marks on AA 2.1 / AA 2.2 / C-1
- **Rule**: Every easement shown on the survey (Public Utility Easement, Storm Drain Easement, Sanitary Sewer Easement, Access Easement, etc.) must appear on the architectural site/plot plans AND civil sheets, dimensioned and labeled by type.
- **Failure pattern**: Survey shows a 2'×30' Access Easement on the west side; the architectural plans don't acknowledge it. Plan-check catches it; if construction is in the easement, it's a redesign.
- **Recommendation**: Transcribe easements directly from the survey to the architectural site plan. Use the survey's notation conventions; don't paraphrase.


## SJ-RES-012 — Master abbreviation list includes every abbreviation used in the set
- **Citation**: Implicit completeness
- **Applies to**: General-notes / abbreviations sheet (typically AG 0.2 equivalent)
- **Severity**: minor
- **Visual cue**: Abbreviations list on the general-notes sheet; abbreviations used on survey, site plan, civil
- **Rule**: The master abbreviations list must include every abbreviation used anywhere in the drawing set. Sheet-specific abbreviation lists (e.g. on the survey) must either match the master or be merged into it.
- **Failure pattern**: Survey uses TC, EP, LIP, BSL, AD, GS without defining them; AA 2.1 uses PUE, SDE, SSE without defining them; the master abbreviations list (AG 0.2) doesn't include any of them.
- **Recommendation**: Aggregate abbreviations from survey + civil + architectural into a single master list. Cross-check at pre-submittal that no abbreviation appears in the drawings but not in the master.


## SJ-RES-013 — Cover sheet uses legal description (Lot/Tract/Map), not street address
- **Citation**: AHJ submittal completeness
- **Applies to**: Cover sheet project-info block
- **Severity**: critical
- **Visual cue**: "Lot Number" / "Legal Description" / "APN" fields on cover
- **Rule**: The Lot Number field on the cover sheet must reference the legal description (e.g. "Lot 88, Tract 1647, Map Book 68 Pg 8"), not the street address. The APN must also be present.
- **Failure pattern**: Designer uses the street address (e.g. "10350") as the Lot Number because it's what's most familiar. Plan-check rejects on submittal completeness.
- **Recommendation**: Pull legal description from the deed or title report. Show legal description AND APN AND street address — they're three different fields.


## SJ-RES-014 — Designer license: non-architects cannot use "Architect" title
- **Citation**: CA Business & Professions Code §5536.22
- **Applies to**: Cover sheet designer block; revision block; title block
- **Severity**: major
- **Visual cue**: Designer name + credentials; title block "Architect" references
- **Rule**: If the drawing preparer is NOT a licensed architect (CA license number visible), the title "Architect" cannot appear in the project team block, revision block, or anywhere implying the preparer is an architect. "Designer", "Draftsperson", or "Building Designer" is acceptable.
- **Failure pattern**: Non-licensed designer carries forward an "Architect:" label from a template. Plan-check (or in worst case, the Architects Board) flags it.
- **Recommendation**: Audit the cover sheet and title block for the word "Architect". If the preparer doesn't hold a CA architecture license, replace with "Designer" or the appropriate title.


## SJ-RES-015 — WUI (Wildland-Urban Interface) status must be verified and stated
- **Citation**: CBC Chapter 7A / CRC R337; CAL FIRE Fire Hazard Severity Zone (FHSZ) map
- **Applies to**: Cover sheet; technical-notes sheets; material specifications
- **Severity**: major
- **Visual cue**: Cover sheet "WUI Status" field; material-spec sheets for compliant assemblies
- **Rule**: Cover sheet must state whether the project is inside a Wildland-Urban Interface zone (per CAL FIRE FHSZ map). If WUI applies, all exterior assemblies (roofing, siding, eaves, vents, decking, glazing) must comply with CBC Chapter 7A / CRC R337.
- **Failure pattern**: Cover says "WUI: TBD" or omits it entirely. Material specs don't reference Chapter 7A even when WUI applies.
- **Recommendation**: Look up the project address on the CAL FIRE FHSZ map (https://osfm.fire.ca.gov/fhsz/). State WUI status explicitly on cover. If WUI applies, every exterior assembly note must reference its 7A compliance class.


## SJ-RES-016 — Mandatory CRC compliance notes on general-notes sheet
- **Citation**: CRC R302.6, R314, R315, R308.4, R408, R807, R319, Chapter 7A
- **Applies to**: General-notes sheet (AG 0.2 equivalent)
- **Severity**: major
- **Visual cue**: CRC notes block on the general-notes sheet
- **Rule**: The general-notes sheet must include compliance notes for: R302.6 (1-hr garage separation), R314 (smoke alarm locations), R315 (CO alarm locations), R308.4 (safety glazing), R408 (crawlspace ventilation + access), R807 (attic access), R319 (address numerals), and Chapter 7A (WUI) if applicable.
- **Failure pattern**: Templates from older projects miss one or more of these. Plan-check requires every one.
- **Recommendation**: Maintain a "current CRC notes" reference at the office; copy verbatim to every project.


## SJ-RES-017 — Crawlspace ventilation per CRC R408.1
- **Citation**: CRC R408.1; R408.4 (access panel)
- **Applies to**: Foundation plan; crawlspace ventilation calc notes
- **Severity**: major
- **Visual cue**: Crawlspace ventilation calculation note; vent opening callouts
- **Rule**: Crawlspace under-floor ventilation must provide minimum 1 sq ft of net free area per 150 sq ft of under-floor area (CRC R408.1, before vapor retarder reduction). Access panel min 18"×24" per R408.4.
- **Failure pattern**: Drawings cite "1 SF per 1 SF" (a typo), or omit the calc entirely. Plan-check requires the math shown.
- **Recommendation**: Show the calc: under-floor area × (1/150) = required net free area, then list vent sizes that add up to that area. Access panel location must be shown on plan.


## SJ-RES-018 — Building height explicitly dimensioned in elevations from natural grade
- **Citation**: Underlying zone max-height limit; natural-grade definition per CRC
- **Applies to**: Elevations on all four sides
- **Severity**: major
- **Visual cue**: Height dimensions on each elevation; grade reference labels
- **Rule**: Building height must be explicitly dimensioned in EVERY elevation, measured from natural grade to the topmost point. The grade reference must be labeled "NATURAL GRADE" (not "FINISHED GRADE"). Ridge and plate heights both dimensioned.
- **Failure pattern**: Height is implied by elevation but not dimensioned, or measured from finished grade (which hides 1–2 ft of cut/fill). Or only one elevation dimensions it.
- **Recommendation**: Dimension max-height on every elevation. Show natural grade as a separate dashed line if site was graded.


## SJ-RES-019 — Demolition scope must include scope list + hazmat + utility-disconnect plan
- **Citation**: BAAQMD asbestos rules; PG&E disconnect procedure; AHJ demolition permit
- **Applies to**: Demolition sheet (AA 2.1 equivalent) for any project demolishing an existing structure
- **Severity**: major
- **Visual cue**: Demolition sheet notes block; sheet content
- **Rule**: A demolition sheet must include: (a) itemized scope of what's being removed, (b) hazmat / asbestos / lead-paint survey reference, (c) utility disconnect plan (water, sewer, gas, electric). Pre-1980 structures trigger BAAQMD asbestos/dust control notes regardless of survey result.
- **Failure pattern**: Demo sheet shows "EXISTING TO BE REMOVED" hatching but no scope list, no hazmat survey, no disconnect plan. Plan-check (and PG&E coordination) requires all three.
- **Recommendation**: Standard demolition-note block at the office: scope list as a numbered table, asbestos survey clause for pre-1980, utility disconnect with PG&E ticket number space.


## SJ-RES-020 — MRP C.3 stormwater for projects ≥ 2,500 sf impervious creation/replacement
- **Citation**: Municipal Regional Permit C.3 (MRP3); SCVURPPP
- **Applies to**: Any project creating or replacing ≥ 2,500 sq ft of impervious area
- **Severity**: major
- **Visual cue**: Impervious-area calculation on cover or AA 2.2; civil C-1 stormwater notes
- **Rule**: Projects creating or replacing 2,500 sq ft or more of impervious area must address MRP C.3 stormwater requirements: impervious-area calc, treatment measures (bioretention, swale, dry well), hydromodification analysis if applicable. Erosion and sediment control during construction must be specified.
- **Failure pattern**: Impervious-area calc shows ≥ 2,500 sf but no C.3 measures or erosion control referenced. Plan-check refers to public works for stormwater compliance.
- **Recommendation**: Calculate impervious area early (existing vs proposed). If ≥ 2,500 sf, engage civil for C.3 measures; if borderline, design to stay under 2,500 sf if practical.


## SJ-RES-021 — All trees on survey must be addressed (protection or removal permit)
- **Citation**: SJMC 13.28 Heritage Tree Ordinance (or local equivalent); arborist report
- **Applies to**: Any project with trees on the survey
- **Severity**: major
- **Visual cue**: Survey tree symbols + diameters; site plan tree-protection fencing; arborist report
- **Rule**: Every tree shown on the survey must be addressed somewhere in the drawings: trees being RETAINED need protection fencing locations on the grading/site plan; trees being REMOVED need a Tree Removal Permit reference. Heritage species (oak, redwood per SJMC 13.28) must be flagged regardless of size.
- **Failure pattern**: Survey shows a 30" oak; the architectural set silently ignores it. Plan-check, urban forestry, and (if heritage) the city's heritage tree board all flag this.
- **Recommendation**: Cross-reference survey trees against the site plan one-by-one. For each: state "RETAIN — protection fencing at dripline" or "REMOVE — Tree Removal Permit application #___".


## SJ-RES-022 — Survey is authoritative; civil + architectural reissued AFTER survey is final
- **Citation**: AHJ submittal completeness; coordination convention
- **Applies to**: Project sequencing; revision-block dates
- **Severity**: critical
- **Visual cue**: Revision-block dates on survey vs civil vs architectural sheets
- **Rule**: The survey is the authoritative geometric source. Civil grading and architectural site plans must be issued or re-issued WITH OR AFTER the survey date. A civil sheet dated before the survey indicates the civil was drawn against stale or assumed information.
- **Failure pattern**: Civil dated 1-30-2026 with a survey dated 3-3-2026 — civil was drawn before the survey was complete. All civil dimensions are suspect.
- **Recommendation**: Sequence: survey first, then civil + architectural. If revisions occur, all downstream sheets re-issued with updated date.


## SJ-RES-023 — Elevation datum (NAVD88 or assumed) stated explicitly; benchmarks tie
- **Citation**: Survey conventions; civil benchmark practice
- **Applies to**: Survey title block; cover sheet datum note; civil benchmarks
- **Severity**: minor
- **Visual cue**: Datum notation on survey + civil; benchmark elevation values
- **Rule**: Survey and civil must state the elevation datum (NAVD88 preferred; "assumed datum" only if FEMA / floodplain is verified not applicable). Architectural grade references (FFL, pad, TC) must tie back to a numbered civil benchmark.
- **Failure pattern**: Survey uses "assumed datum 311.80" with no FEMA verification; architectural sheets quote elevations with no benchmark reference. Floodplain status uncheckable.
- **Recommendation**: Use NAVD88 by default. If the lot is near a FEMA flood zone, NAVD88 is required to determine BFE compliance.


## SJ-RES-024 — Project-type-specific notes must match actual project scope
- **Citation**: Implicit completeness
- **Applies to**: General notes; insulation notes; garage notes
- **Severity**: critical
- **Visual cue**: Notes referencing "ADU", "2nd floor", "habitable space above", "JADU" on a single-story SFR project
- **Rule**: Notes referencing project types or features that aren't in the scope (e.g. "ADU" notes on a project with no ADU, "2nd floor insulation" on a single-story project, "habitable space above garage" on a single-story) must be stripped or marked N/A.
- **Failure pattern**: Templates from prior multi-story or ADU projects leave behind notes that don't apply. Plan-check is confused about scope.
- **Recommendation**: At pre-submittal, search notes for "ADU", "JADU", "second floor", "2nd floor", "above" if single-story. Strip irrelevant ones.


## SJ-RES-025 — All-electric panel sizing: 200A often insufficient with EV + electric tankless WH
- **Citation**: CEC Article 220 (load calculations); SJ all-electric reach code SJMC §17.84
- **Applies to**: Electrical plan; new construction subject to reach code
- **Severity**: major
- **Visual cue**: Panel-size note on cover, electrical plan, or MEP; electric water heater + EV charger spec
- **Rule**: All-electric homes with an electric tankless water heater (typical draw 150–180 A momentary) AND a Level 2 EV charger (40–80 A) typically require a 400 A service or 200 A with EV load management. A flat "200 A panel" note without a load calc is insufficient.
- **Failure pattern**: Designer carries forward 200 A panel from a gas-appliance template into an all-electric project. Plan-check or electrical inspector flags inadequate service.
- **Recommendation**: Run CEC Article 220 load calc before spec'ing panel size. Document the load calc on the electrical sheet.


## SJ-RES-026 — Construction hours and AHJ contact info match the actual jurisdiction
- **Citation**: SJMC §20.84 (noise ordinance); city-specific noise ordinance
- **Applies to**: General-notes sheet; cover sheet contact block
- **Severity**: major
- **Visual cue**: Construction-hours note; PW contact info; encroachment permit references
- **Rule**: Construction-hours note must reflect the actual project city's noise ordinance (San Jose: M-F 7-7, Sat 9-7, no Sun; verify current). AHJ contacts, URLs, and encroachment-permit references must point to the actual jurisdiction's PW/Planning department.
- **Failure pattern**: Office template carries forward another city's construction hours, URLs, or permit-counter references. Plan-check flags wrong-city contacts immediately.
- **Recommendation**: Maintain a single source of "current jurisdiction notes" per city the office works in. Verify against the city's current ordinance once per year.


<!--
Remaining priority areas to add (not yet captured from the Mann Drive dataset):
- FAR calculation breakdown (which areas count: covered porches > 6 ft deep, mezzanines, attics ≥ 5 ft head height)
- Daylight plane lines drawn from correct setback origin
- T24 energy compliance forms (CF-1R for new construction, CF-2R for additions over X sf)
- Solar PV requirement for new SFR per Title 24
- Bedroom EERO sizing (CRC R310)
- Stair geometry, guardrail heights, handrail location (CRC R311/R312)
- Bathroom ventilation: mechanical exhaust where no operable window (CRC R303.3)
- Kitchen exhaust hood requirements
- Foundation: soils report triggers, expansive soils
- Address marker visibility (R319) — height, contrast, illumination
-->
