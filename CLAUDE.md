# CLAUDE.md — PlanCheck

> Project-level operating instructions for Claude Code sessions opened in this folder. Auto-loaded into every session. Keep updated as conventions change. Read this first.

---

## What PlanCheck is

PlanCheck is a laptop-bound, AI-assisted auditor for residential construction permit drawings. The user uploads one or more PDFs, picks a project jurisdiction, and the tool returns a register of findings — categorised by severity (critical / major / minor / advisory), evidenced, source-tagged to the originating sheet, with severity-coloured pins overlaid on annotated thumbnails. Findings export to CSV and a multi-page PDF report.

**Current target market:** California residential practice (San Jose-based small firm, projects across the Bay Area). Jurisdictional grounding covers California Building Code (CBC), California Residential Code (CRC), Title 24, ADU state law (AB 68 / SB 13 / SB 9), with city-level addenda for San Jose, Santa Clara County, and Saratoga.

**This is an MVP / V1.x stage product.** Single-user, runs on the user's laptop, no auth, no cloud. The user is a non-coder building this for SaaS demos to architects.

---

## Quick start

```
1. Double-click start.bat       (Windows) — auto-launches venv + streamlit
   OR  venv\Scripts\activate && streamlit run app.py

2. Browser opens at http://localhost:8501

3. .env must contain a valid OPENAI_API_KEY (sk-... format)
```

`.env.example` shows the format. `.env` is gitignored — never commit it.

---

## Tech stack (LOCKED — do not bump casually)

| Package | Version | Why pinned |
|---|---|---|
| streamlit | 1.39.0 | Stable; `st.segmented_control` (added 1.40) deliberately not used |
| openai | 1.54.0 | Stable; uses chat.completions API |
| httpx | **0.27.2** | **Compatibility pin.** openai 1.54 passes `proxies=` kwarg; httpx 0.28+ removed it. Bumping httpx breaks every OpenAI call. |
| pymupdf (fitz) | 1.24.10 | PDF text extraction, multi-PDF merge, render-to-image |
| pypdfium2 | 4.30.0 | Page-to-image rendering (faster than fitz for vision payload) |
| pillow | 10.4.0 | Image manipulation, base64 encoding for vision API |
| python-dotenv | 1.0.1 | `.env` loading with override-on-call pattern |
| reportlab | 4.2.5 | PDF report builder |

Bumping any version requires (a) testing every dependent path and (b) confirming the user wants the upgrade. Default = leave them alone.

---

## Module map

| File | Purpose | LOC |
|---|---|---|
| `app.py` | Streamlit UI: upload tray, project metadata inputs, run button + meta line, findings header, severity stats, annotated sheets section, finding cards, CSV+PDF export, About expander, colophon. Heavy CSS (blueprint aesthetic). | ~1,830 |
| `ai_reviewer.py` | OpenAI client setup with `_read_api_key()` (re-reads .env each call). `review_single_page(image, jurisdiction_addendum)` and `review_full_pdf(pdf_bytes, ...)` — accepts addendum string concatenated after `SINGLE_PAGE_REVIEW_PROMPT`. Per-page error tolerance. | ~170 |
| `pdf_processor.py` | `get_pdf_info`, `render_page_to_image`, `merge_pdfs(files)` — multi-file merge via PyMuPDF, returns combined bytes + page_map | ~110 |
| `prompts.py` | `SINGLE_PAGE_REVIEW_PROMPT` (base prompt with `region` field in JSON schema) + `JURISDICTION_PROMPTS` dict (California addenda) | ~75 |
| `references_loader.py` | `load_references(jurisdiction="")` — auto-detects every `.md`/`.txt` in `references/` ROOT (subfolders ignored), strips HTML comments, returns block + file list + word total | ~150 |
| `pin_overlay.py` | `annotate_sheet(image, pins)` — draws severity-coloured numbered pins on a sheet image. 9-zone grid placement. Cluster offset for same-zone pins. | ~160 |
| `pdf_report.py` | `build_report(findings, meta, page_map, ...)` — multi-page PDF: cover + annotated sheets + findings register + disclaimer. Uses ReportLab Platypus. | ~485 |
| `audits_store.py` | Disk persistence — `save_audit(findings_data)`, `load_audit(audit_id)`, `list_audits()`, `delete_audit(id)`. Each audit is one JSON file in `audits/`. Path-traversal protected, atomic writes via `.tmp`-then-rename. Pure functions, no Streamlit dep. | ~195 |
| `text_pass.py` | **Text-extraction pre-pass** (shipped 2026-05-21). `run_text_pass(pdf_bytes)` reads native PDF text via PyMuPDF and runs ~10 high-precision rules over it (PRELIMINARY title-block, wrong-jurisdiction template text, outdated standards, crawlspace ventilation formula, lot number / lot area cross-sheet consistency, missing CRC notes, code-cycle year, AI/template artifacts). Each finding includes `evidence_quote` — the literal PDF string that triggered the rule. **Cannot hallucinate values** because evidence is guaranteed-literal. Wired into `ai_reviewer.review_full_pdf` so its findings appear alongside vision-pass findings; identifiable by `source="text_extraction"` and `rule_id="TEXT-XXX"`. Zero API cost, <1 second runtime. | ~380 |

---

## Folder map

```
Planchecker auditor/
├── CLAUDE.md                           ← this file (auto-loaded by Claude Code)
├── PLAN.md                             ← original MVP build plan (frozen Apr 30; historical reference only — STALE)
├── README.md                           ← user-facing docs (kept current)
├── requirements.txt                    ← locked deps
├── start.bat                           ← Windows launcher
├── .env                                ← OPENAI_API_KEY (gitignored)
├── .env.example                        ← template
├── .gitignore
│
├── app.py / ai_reviewer.py / pdf_processor.py
├── prompts.py / references_loader.py / pin_overlay.py / pdf_report.py
│
├── references/                         ← AUTO-LOADED on every Run Plan Check
│   ├── _general.md                     ← universal drafting rules (US units)
│   ├── general instructions.txt        ← firm profile
│   ├── california_state.md             ← CBC, CRC, Title 24, ADU state law
│   ├── cupertino_rules.md              ← Cupertino Municipal Code amendments (primary — wedge as of 2026-05-21)
│   ├── sj_residential_general.md       ← 26 universal CA residential rules (SJ-RES prefix is historical; rules apply to any CA jurisdiction)
│   └── _deferred/                      ← NOT auto-loaded (loader skips subdirs); pre-wedge jurisdictions preserved here
│       ├── san_jose.md                 ← San Jose Municipal amendments (deferred 2026-05-21)
│       ├── sj_adu_rules.md             ← SJ-ADU-specific rules (deferred 2026-05-21)
│       └── saratoga.md                 ← Saratoga + WUI + Heritage Trees (deferred 2026-05-18)
│
├── past_projects/                      ← NOT auto-loaded (subfolder of project root, NOT inside references/)
│   ├── Burns_Way_QA_QC_Tracker_RevFINAL.txt
│   └── McFarland_QA_QC_Tracker_RevL_FINAL.txt
│
├── audits/                             ← gitignored — one JSON per saved audit
│   └── <project-slug>_<YYYYMMDD-HHMMSS>.json   ← auto-saved on run, re-saved on every edit/resolve/add
│
├── .claude/                            ← Claude Code project-level config
│   └── skills/
│       └── pdf-guide-test/             ← editorial-style PDF guide builder (see "Project-level skills")
│
└── venv/                               ← Python virtual environment (gitignored)
```

---

## Reference system

**Auto-detection:** `references_loader.load_references()` scans `references/` ROOT (no recursion) and loads every `.md` and `.txt` file. The `jurisdiction` parameter is accepted for backward-compat but no longer filters — every file in root loads on every run.

- **To add a rule:** drop a `.md` or `.txt` file into `references/` root. Loaded on next Run Plan Check. No code change. No restart.
- **To pause a file without deleting:** move it to `past_projects/` or any subfolder.
- **HTML comments inside files (`<!-- ... -->`) are stripped** before sending to the AI — leave instructional notes freely.
- **Soft cap:** total content > 30,000 words triggers a UI warning. Token costs rise but it still works.
- **Not yet supported:** `.docx`, `.xlsx`, `.pdf` native parsing. Convert to `.md`/`.txt` first.

---

## Jurisdiction system — Cupertino only (micro-niche, flipped 2026-05-21)

`JURISDICTION_LABELS` (in `app.py`) and `JURISDICTION_PROMPTS` (in `prompts.py`) are **deliberately** out of lockstep:

- `JURISDICTION_LABELS` = `("Cupertino (city + state)",)` — the only option exposed in the new-audit UI.
- `JURISDICTION_PROMPTS` keeps every historical entry ("None", "California", "Saratoga", "Santa Clara County", "San Jose", "Other Bay Area city") so old audits in [audits/](audits/) can still load + render their original jurisdiction. New audits always run under Cupertino.

**Why Cupertino:** Original wedge narrowing on 2026-05-18 was to **San Jose**. On 2026-05-21 the user supplied the first labeled eval dataset (Mann Drive, 10350 Mann Dr, Cupertino R1-10 SFR, 208 hand-labeled findings). When confronted with their own project distribution — "of your last 10 projects, what cities?" — the honest answer was "mostly Cupertino." **The wedge flipped to Cupertino**: it's where the firm's actual project work, eval data, and warm sales pipeline all live. SJ was an aspirational target without data behind it; Cupertino is where the firm actually operates.

**DO NOT re-introduce Indian jurisdictions** (NBC India, Delhi DDA, Haryana HUDA, Punjab Municipal). The pivot from India to California on 2026-05-03 was deliberate. If the user asks for India support back, confirm they want to undo the pivot before doing anything.

**DO NOT re-expand to multi-jurisdiction on a whim.** The narrowing to Cupertino is the deliberate strategic call. If the user asks to add SJ / SCC / Bay Area back, confirm they want to reverse the narrowing — and remind them of the win-the-wedge logic + the project-distribution data that drove the Cupertino choice.

A defensive guard at the top of app.py resets `st.session_state.jurisdiction` to `"Cupertino (city + state)"` if it holds a stale value not in the current `JURISDICTION_LABELS` — keep that guard in place. This also protects loading old audits whose stored jurisdiction string ("San Jose", "Saratoga", "None", etc.) doesn't match the narrowed labels — the audit's original jurisdiction is preserved inside the audit JSON for display purposes; only the new-audit form gets the Cupertino default.

**To later re-expand (when Cupertino is dominated):**
1. Add the label back to `JURISDICTION_LABELS` (app.py)
2. The matching prompt key already exists in `JURISDICTION_PROMPTS` (prompts.py)
3. Move the corresponding city file from `references/_deferred/` back to `references/`
4. Restart Streamlit

## Eval harness — measure recall against labeled drawings

Built 2026-05-21. Lives at [eval/](eval/). Single source of truth for measuring tool performance.

- [eval/eval.py](eval/eval.py) — runner. Flags: `--single <filename>`, `--dry-run`, `--force-rerun`.
- Matcher uses **LLM-as-judge** (one OpenAI call per page-bucket; ~$0.30 total per drawing). Bag-of-words / Jaccard / containment metrics are too brittle for terse-GT-vs-verbose-AI mismatch.
- Audit result is **cached** to `eval/_cache/<basename>.audit.json` after the first run; re-scoring with different matcher / GT / category tweaks is FREE. Use `--force-rerun` only when the prompt has changed and the audit needs a fresh run.
- Ground-truth schema documented at the top of `eval.py` and demonstrated in `eval/_example_ground_truth.json`. Key fields: `sheet_id`, `pages` (list), `category`, `severity`, `description`.
- Page-bridging: `pages` (list) is the primary key; falls back to dynamic `sheet_id → page` bridge from the AI's `facts_per_page` extraction.

**Mann Drive baseline (2026-05-21, pre-Cupertino-flip):** 13.9% recall (29 of 208 GT). Post-Cupertino-flip, expect ~28–32% on the same dataset (Cupertino-specific items now in scope). Re-measure with the new prompt before declaring.

**When user provides more drawings:** drop the PDF into `eval/drawings/<name>.pdf`, ask for page-number mapping for the reviewed sheets, convert the Excel/CSV tracker to ground-truth JSON via the schema, run `python eval/eval.py`.

---

## Streamlit gotchas (the ones that have bitten us)

### Module reimport
Streamlit reruns the script top-to-bottom on every interaction, but does NOT reimport already-imported modules. This means:

- Editing `app.py` → next interaction picks it up
- Editing `ai_reviewer.py`, `prompts.py`, `references_loader.py`, `pin_overlay.py`, `pdf_report.py`, `pdf_processor.py` → **requires full server restart** (Ctrl+C in terminal, relaunch)
- Editing files inside `references/` → picked up next interaction (the loader re-reads files on every call by design)

### `.env` override
`load_dotenv()` does NOT override env vars already set in the process. If Streamlit started before the user filled in `.env`, the placeholder gets cached. The fix is `_read_api_key()` in `ai_reviewer.py` calling `load_dotenv(override=True)` on every call. **Do not break this pattern** — it's why the user can edit `.env` without restarting Streamlit.

### File uploader reset
Streamlit's `st.file_uploader` retains state until its `key` changes. The "Clear and start over" button bumps `st.session_state.uploader_counter`, which is interpolated into the uploader's key (`f"pdf_uploader_{counter}"`), forcing a fresh widget. Don't change that pattern unless you have a better way to reset uploaders.

### Caching with bytes args
`@st.cache_data` hashes positional args. PIL Images and large bytes are slow to hash. Use a leading underscore (`_pdf_bytes`) to tell Streamlit to skip hashing the arg, then provide a separate hashable key (`pdf_hash`).

---

## Annotation pins

Pins are placed on a **3×3 zone grid** (`top-left`, `top-center`, ..., `bottom-right`, plus `full-sheet`), NOT at pixel-precise coordinates. The AI returns a `region` field per finding; `pin_overlay.annotate_sheet()` places pins at the named zone's center.

**Why zones not pixels:** vision LLMs are unreliable at exact bounding boxes (~30–40% error). Confidently-drawn boxes in the wrong place destroy user trust. Zone-level placement is something the AI is reliable at (~85–90%). Architects always cross-reference against the source drawing for exact location anyway.

**Severity → color** (rendered, also matches UI badge palette):

| Severity | Color | Hex |
|---|---|---|
| critical | vermillion | #E8654F |
| major | amber | #F0A060 |
| minor | ochre | #E8C84F |
| advisory | blueprint | #7FCBE3 |

Multiple pins in the same zone get cluster-offset side-by-side so they don't overlap. Pin labels are the `FND-NN` codes that match the finding cards below.

---

## PDF report

Built by `pdf_report.build_report()` using ReportLab Platypus. Structure:

1. **Cover page** — Project metadata table (Project, Architect, Jurisdiction, Set date, Generated, References applied) + severity summary with colored counts + AI disclaimer
2. **Annotated sheets** — Every unique sheet that has findings, rendered at ~120 DPI with all its pins overlaid
3. **Findings register** — Every finding as a row: severity chip, mini annotated thumbnail with pin, FND-NN, source/category header, description, evidence, recommendation
4. **Disclaimer** — AI-generated caveats, pin-precision caveat, jurisdictional grounding caveat, cross-sheet coordination caveat

The report builder takes `annotated_sheet_provider(page_num) -> PIL.Image` and `finding_thumb_provider(page_num) -> PIL.Image` callables so app.py controls the rendering pipeline (and pin overlay) — pdf_report stays decoupled from Streamlit.

---

## CSV export

Built by `_build_findings_csv()` in `app.py`. The CSV is **self-documenting**:

```
Project,<name>
Architect,<firm>
Jurisdiction,<jurisdiction>
Set date,<date>
Generated,<timestamp>
References applied,<filenames> (<word count>)
                                                  ← blank separator
Source File,Page,Severity,Category,Description,Evidence,Recommendation
... data rows ...
```

The metadata header rows make the CSV traceable when emailed to clients or filed in project records.

---

## Out of scope (don't build unless explicitly asked)

These have been deferred deliberately. Don't volunteer them:

- Login / authentication / multi-user
- Cloud deployment, custom domain, HTTPS termination
- Stripe / billing / per-user usage caps
- `.docx` / `.xlsx` / `.pdf` native parsing in references (only `.md` / `.txt` today)
- ChromaDB-based RAG over actual code books (planned for later when reference content exceeds ~30k words)
- Conversational chat module ("Talk to your Virtual Project Architect" — would unlock the role-detection / interview-style protocol from the firm's profile)
- Vaastu Shastra compliance hooks (firm profile mentions it as a regular requirement; not yet wired)
- Pixel-precise bounding boxes on annotations (we tried, AI is unreliable; zones win for now)
- Acknowledge / Dismiss buttons per finding (V1.x candidate)
- AI confidence score per finding (V1.x candidate)
- Cross-discipline / cross-sheet coordination checks
- Spec vs. drawing comparison
- RFI generation
- Multilingual UI

---

## User communication norms

The user is a **non-coder building their first software project**. Adjust accordingly:

- Plain English. No jargon without definition. Define terms on first use.
- Phase gates appreciated — finish a discrete chunk, restart Streamlit, ask the user to verify before moving on.
- Honest tradeoffs over reflexive "yes, go" answers. The user has explicitly said they prefer this style.
- **Pivots are intentional.** When the user makes a directional choice (e.g., the India → California pivot), do not undo it later "to be helpful." Confirm before reversing any deliberate decision.
- **User's choices win over the spec.** When the user picks a name, identifier, or approach that diverges from a planning doc, edit the doc — don't ask them to conform.
- For UI changes, prefer screenshots-for-verification over describing what should appear.
- After substantive code changes, list a clear test sequence the user can follow to verify.
- Never volunteer scope creep. If the user asks for X, give them X. If you see Y is also needed, mention Y and ask before doing it.

---

## Project-level skills

Installed at `.claude/skills/`. Each skill has its own `SKILL.md` declaring trigger phrases and intended use. **Match the user's request to the skill's actual purpose — don't force a skill onto a deliverable it wasn't built for.**

### `pdf-guide-test`

**What it does:** generates editorial-magazine-style PDFs (cream + orange palette, Poppins/Lora type, numbered steps, callout boxes, prompt blocks, inline SVG figures). Built on **WeasyPrint** (HTML+CSS → PDF). Bundled template at `.claude/skills/pdf-guide-test/assets/build_guide_pdf.py`.

**Trigger this skill when the user asks for:**
- "create a guide", "write a guide", "build a guide", "make a guide", "turn this into a guide"
- "cheat sheet for X"
- "walkthrough on X", "tutorial on X", "how-to on X"
- "playbook for X"
- "write this up", "make a resource"
- A client-onboarding primer, a hand-out for new hires, a marketing one-pager — anything magazine-style and shareable

**DO NOT run this skill's WeasyPrint script for plan-check / audit PDFs.** WeasyPrint has external system dependencies (Cairo, Pango, GDK-PixBuf) that are notoriously painful on Windows — ReportLab is pure-Python. If the user wants editorial-style audit PDFs, do it the way `pdf_report.py` already does it (see next section).

### Audit PDFs already borrow this skill's visual language

`pdf_report.py` (ReportLab-based) was rewritten on 2026-05-03 to apply the skill's editorial design tokens to audit reports — cream `#faf9f5` background, near-black `#141413` ink, orange `#d97757` accent (rules + severity bars + small uppercase labels), warm gray `#e8e6dc` callout backgrounds, mid gray `#b0aea5` for captions and footers. Typography uses Helvetica-Bold (Poppins stand-in) for display + Times-Roman/Times-Italic (Lora stand-in) for body.

Structure is unchanged — cover + summary + annotated sheets + findings register + closing — but the visual treatment is editorial: no boxed cells, hairline dividers, severity markers as thin colored bars (not filled badges), callout boxes for the disclaimer, italic signoff at the close. Page size moved from A4 to LETTER to match California permit conventions.

**If the user asks to "use the skill" on an audit PDF**, the correct interpretation is: improve `pdf_report.py`'s borrowed design tokens (palette, typography, spacing). NOT install WeasyPrint and run the skill's script directly. The current ReportLab implementation is the pragmatic answer.

## Collaboration system (Phase 1 — shipped 2026-05-05)

Audits are persisted as JSON in `audits/` and editable by role. Two roles have distinct powers; the others view-only.

### Roles (UI: top-of-page "I AM" dropdown — no auth, honor system)

| Role | Edit AI findings | Add new findings | Resolve findings | View only |
|---|:--:|:--:|:--:|:--:|
| `Principal Architect` | ✓ | ✓ | – | – |
| `Project Architect` | – | – | ✓ | – |
| `Operations Manager` | – | – | – | ✓ |
| `Site Architect / Construction Manager` | – | – | – | ✓ |
| `Office Administration` | – | – | – | ✓ |
| `— (view only)` (default) | – | – | – | ✓ |

Switching role updates the per-card action widgets immediately (Edit button vs. Resolve checkbox vs. nothing).

### Persistence

- Every successful run auto-saves to `audits/<project-slug>_<YYYYMMDD-HHMMSS>.json` via `save_audit()`
- Every Edit / Resolve / Add mutation re-saves to the same file via `_resave_current_audit()` in app.py
- The top-of-page **AUDIT** dropdown lists all saved audits (newest first); picking one loads it back into session_state and re-syncs the project metadata fields
- The **+ Start fresh** button bumps `uploader_counter`, clears findings_data, resets metadata — equivalent to closing and reopening the app

### Each finding gets 9 collaboration fields

`audits_store.normalize_finding()` adds these with safe defaults to every finding (idempotent — works on old audits without these fields):

| Field | Type | Set when |
|---|---|---|
| `resolved` | bool | Project Architect ticks the Resolve checkbox |
| `resolved_by` | str / None | Role string ("Project Architect") at time of tick |
| `resolved_at` | ISO timestamp / None | When the tick happened |
| `edited` | bool | Principal saves the Edit form |
| `edited_by` | str / None | Role string at time of save |
| `edited_at` | ISO timestamp / None | When the edit was saved |
| `manually_added` | bool | Principal authored a new finding via "Add new finding" |
| `added_by` | str / None | Role string at time of add |
| `added_at` | ISO timestamp / None | When the new finding was added |

Visual indicators in the card head:
- `+ ADDED` (italic orange) — `manually_added=True`
- `EDITED` (orange) — `edited=True`
- `✓ RESOLVED` (green) — `resolved=True`

Resolved cards get `opacity: 0.55` and sort to the bottom of their severity bucket.

### Streamlit gotcha — empty f-string substitution + blank line + escaped HTML

When `status_tags_html` was empty AND on its own line in the card-head template, Streamlit's markdown processor saw the blank line as a paragraph break and **escaped the next `<span class="no">` element as literal text**. The fix was to keep `{status_tags_html}` on the same line as the surrounding spans (no blank lines anywhere in the head). **Don't reintroduce blank lines into HTML f-string templates** that get fed to `st.markdown(unsafe_allow_html=True)`.

### Dashboard

Below the severity summary on the findings page:

- **Resolution-progress row** — `RESOLVED · X of N · Y% · ▓▓▓░░░` — green bar fills as Project Architect ticks items off
- **Distribution charts** — Streamlit `st.bar_chart()` (no Altair / no new dependency), severity-color-stacked, horizontal:
  - "By source file" — only in multi-file mode
  - "By category" — code / drawing error / coordination / constructability

Charts wrap in a `try/except` so a chart failure never blocks the rest of the audit from rendering.

## Manual smoke-test workflow

There are **no automated tests.** After any code change in modules that need a restart, the workflow is:

```
1. taskkill //F //IM streamlit.exe //IM python.exe   (or kill specific PIDs)
2. start.bat                                          (relaunches via venv)
3. Refresh the browser tab at http://localhost:8501
4. Drop a small PDF, fill required project metadata, click Run Plan Check
5. Verify findings render, references shown in header, CSV+PDF download work
```

Streamlit running in the background by Claude Code (via `streamlit run --server.headless true`) is fine for development but the user typically launches via `start.bat` themselves. Don't tie production launches to the Claude session lifecycle.

---

## Where different kinds of context live

| Doc | Audience | Lifespan | Role |
|---|---|---|---|
| **CLAUDE.md** (this) | Claude Code sessions, future-you, teammates | Living | Operating manual for the codebase. Auto-loaded. |
| **README.md** | End users, demo audience, customers | Living | How to use the product. |
| **PLAN.md** | Original developer (you, when starting) | **FROZEN Apr 30** — historical artifact, NOT current state | Original MVP build plan. Many non-goals listed there have since been built. Read for history, not as truth. |
| **memory/** under `~/.claude/projects/...` | Single user's machine | Living, but private (doesn't travel) | Strategic context: roadmap, market direction, user preferences |

When CLAUDE.md and a memory note disagree, CLAUDE.md wins (it's the project's source of truth). When CLAUDE.md and PLAN.md disagree, CLAUDE.md wins (PLAN.md is frozen). When CLAUDE.md and the actual code disagree, **the code wins** — and update CLAUDE.md.

---

## Behavioral guidelines

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
