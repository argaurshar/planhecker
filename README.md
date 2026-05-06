# PlanCheck

An AI-assisted auditor for construction permit drawings. Drop in one or more PDFs, fill in project context (project name, architect, jurisdiction), and receive a register of issues an attentive plan reviewer would flag — categorised, evidenced, exportable.

Configured for **California residential practice** out of the box — California Building Code (CBC), California Residential Code (CRC), Title 24, state ADU law (AB 68 / SB 13 / SB 9), with city-level options for **San Jose, Santa Clara County, Saratoga**, and other Bay Area jurisdictions. The AI is told to cite specific code sections where confident and to flag items that need AHJ verification.

---

## How to run

### The easy way (Windows)

1. Double-click **`start.bat`** in this folder.
2. A black terminal window opens and shows a few startup lines.
3. Your browser should open automatically at <http://localhost:8501>.
4. If the browser does not open, copy that URL and paste it into your browser yourself.

### The terminal way (any OS)

1. Open a terminal in this folder.
2. Activate the Python virtual environment:
   - **Windows:** `venv\Scripts\activate`
   - **Mac / Linux:** `source venv/bin/activate`
3. Run: `streamlit run app.py`
4. Browser opens automatically.

---

## Roles + collaborative review

PlanCheck supports a small-team review workflow. The **I AM** dropdown at the top of the page sets your role for the session:

| Role | What they can do |
|---|---|
| **Principal Architect** | Edit any AI finding (severity, description, evidence, recommendation); add brand-new findings the AI missed |
| **Project Architect** | Tick findings as **Resolved** as the field rectifies them |
| Operations Manager · Site Architect · Office Admin · — (view only) | Read-only: see all findings + status tags, no edit/resolve |

There's no login — it's an honor system. Anyone at the keyboard can switch roles freely. The role distinction shapes what action widgets appear under each finding card.

## Audit persistence

Every successful audit auto-saves to `audits/<project-slug>_<date-time>.json` on this machine. Every Edit / Resolve / Add re-saves to the same file. To pick up a past audit, use the **AUDIT** dropdown at the top of the page — it lists all saved audits, newest first. Click **+ Start fresh** to clear everything and start a brand-new audit.

The `audits/` folder is gitignored (audits are per-machine state — not shareable via git).

## How to use

1. Pick your role from the **I AM** dropdown at the top.
2. Drag one or more construction PDFs onto the **Drawing Tray** (or click *Browse Files*).
   - **Single PDF:** behaves exactly as a normal upload.
   - **Multiple PDFs:** they are merged in the order you drop them in. An **Intake Order** list shows the merge sequence so you can verify it. Each finding is later tagged with the **source file + page within that file**, not the merged page number.
2. Fill in the **Project details** below the upload tray:
   - **Project name** (required) — e.g. "14251 Burns Way Residence"
   - **Architect / firm** (optional)
   - **Jurisdiction** (required) — pick one of:
     - *None* (generic review, default)
     - *California (state — CBC + CRC + Title 24)*
     - *San Jose (city + state)*
     - *Santa Clara County (county + state)*
     - *Saratoga (city + state)*
     - *Other Bay Area city (verify locally)*
   - **Drawing set date**
3. Click **Run Plan Check**. The button stays disabled until project name + jurisdiction are filled. The label tells you how many sheets will be reviewed.
4. Watch the progress bar advance. A 50-page set takes roughly 5 to 15 minutes.
5. When the run finishes:
   - **Resolution-progress bar** below the severity counts shows how many findings have been ticked off as resolved.
   - **Distribution charts** (severity-stacked horizontal bars) show findings by source file (multi-file mode) and by category (code / drawing error / coordination / constructability).
   - Findings appear below, sorted by severity, with a thumbnail of the sheet they came from.
   - **As Principal Architect**, each finding has an **Edit** button below it (opens an inline form) and a **+ Add new finding** button sits above the stack to author a finding the AI missed.
   - **As Project Architect**, each finding has a **Resolved** checkbox below it. Ticking fades the card to ~55% opacity, adds a green ✓ RESOLVED tag in the header, and sorts the resolved finding to the bottom of its severity bucket.
   - All changes (edits, new findings, resolves) save to disk immediately — refresh the browser and they're still there.
   - The findings header shows the jurisdiction context the AI was given.
   - In multi-file mode each finding card shows the source filename + page within that file (e.g. `structural.pdf p.04`).
   - **Annotated sheets** appear above the findings list — every unique sheet that has issues, rendered larger with severity-colored numbered pins (red = critical, orange = major, yellow = minor, blue = advisory). Pins are placed in a 3×3 grid zone (top-left, center, bottom-right, etc.) so you can see at a glance where issues cluster.
   - Each finding card now shows the same annotated thumbnail with all of that sheet's pins — find the matching `FND-NN` number on the pin and on the card.
   - Use the **Filter by severity** pills (All / Critical / Major / Minor / Advisory) to narrow the list.
   - Click **Download CSV** to save all findings as a spreadsheet. The CSV begins with project metadata header rows (Project, Architect, Jurisdiction, Set date, Generated timestamp) before the findings table — making each export self-documenting when emailed.
   - Click **Download PDF report** to build a multi-page deliverable with: cover page (project metadata + severity summary), an Annotated Sheets section (each unique sheet with pins, rendered large), a Findings Register (every finding with its thumbnail, severity badge, evidence, and recommendation), and a disclaimer page. This is the artifact you forward to clients, structural consultants, and junior staff. Takes 10–30 seconds to generate for a 30–50 finding set.
6. To audit a different drawing, click **Clear and start over** at the bottom of the page.

### Notes on pin placement (annotation accuracy)

- Pins are **zone-level**, not pixel-precise. The AI is reliable at saying "this issue is in the top-right corner" but not at giving exact coordinates.
- A pin placed in `bottom-center` means the issue is somewhere in the bottom-center cell of a 3×3 grid laid over the sheet — it's a navigation aid, not a precise marker.
- Multiple pins in the same zone get clustered side-by-side so they don't overlap.
- If the AI doesn't return a region (rare), the pin defaults to the center of the sheet.
- Always verify against the source drawing for exact location.

### Notes on multi-file uploads

- Files are merged in upload order. If you need a specific order, drop them in that order.
- The 100-sheet cap applies to the merged total. Three 40-page PDFs = 120 sheets, of which only the first 100 will be reviewed.
- Total upload size is capped at 200 MB (Streamlit default).
- A file that fails to merge (corrupted or password-protected) is skipped with a red notice; the rest are still merged and reviewed.

### Notes on jurisdiction selection

- *None* runs the generic prompt. The AI uses general observation-based reasoning, jurisdiction-agnostic.
- *California (state)* and any of the city/county options tell the AI to apply CBC, CRC, Title 24, ADU state law (AB 68 / SB 13 / SB 9), and the relevant local amendments — and to cite specific code sections where confident.
- This is **prompt-level grounding** plus **reference-file grounding**, not direct retrieval from the actual code text. The AI does not open the CBC PDF; it relies on its training knowledge plus whatever you put in `references/`. For specific code citations, verify against the actual code book before acting.
- Code cycle reminder: California is on a 3-year cycle (currently 2022 / 2025). Many AHJs allow vesting to the prior cycle if the application was filed before the new cycle's effective date — verify in writing.

## Reference rules — `references/` folder

The tool consults a folder of markdown / text files on every Run Plan Check. You can edit these files directly with any text editor (Notepad, VS Code) — no code change required. The contents are appended to the AI prompt so the AI applies *your firm's* rules, not just its training knowledge.

```
Planchecker auditor/
├── references/                       ← every .md/.txt here loads on every run
│   ├── _general.md                   ← universal drafting / title-block rules
│   ├── general instructions.txt      ← firm profile (San Jose CA practice)
│   ├── california_state.md           ← CBC, CRC, Title 24, ADU state law
│   ├── san_jose.md                   ← San Jose Municipal amendments
│   └── saratoga.md                   ← City of Saratoga + WUI + heritage trees
└── past_projects/                    ← archives — NOT loaded into the prompt
    ├── Burns_Way_QA_QC_Tracker_RevFINAL.txt
    └── McFarland_QA_QC_Tracker_RevL_FINAL.txt
```

### How files are loaded

- **Every `.md` and `.txt` file in `references/` ROOT loads on every Run Plan Check.** Drop a new file in, it gets used. No filename mapping — file naming is up to you.
- **Subfolders are ignored.** Move a file into `past_projects/` (or any subfolder) to take it out of the loop without deleting it.
- Files are re-read on every run, so editing a file shows up on the next Run Plan Check **— no server restart needed.**

### How to edit

1. Open the relevant file in any text editor (right-click → Open with → Notepad).
2. Add, remove, or modify rules. Plain English or markdown — both work.
3. Save the file.
4. The next time you click Run Plan Check, the new content is applied automatically.

### What gets shown to the user

- Above the Run button: `References: 5 reference files · 2,300 words` — preview of what will be applied
- After the run, in the findings header: `REFERENCES APPLIED · 5 FILES · 2,300 WORDS · _GENERAL.MD, GENERAL INSTRUCTIONS.TXT, CALIFORNIA_STATE.MD, SAN_JOSE.MD, SARATOGA.MD`
- In the CSV header rows: `References applied,_general.md, general instructions.txt, california_state.md, san_jose.md, saratoga.md (2,300 words)`
- On the PDF report cover: same `References applied` row

### Limits

- Total content is appended to every page's API call, so longer reference files cost more tokens. Keep total content under ~30,000 words per run; the tool shows a soft-cap warning above that.
- HTML comments (`<!-- ... -->`) are stripped before sending to the AI, so you can keep instructional notes inside the files freely.
- The seed values are illustrative — verify them against your authoritative source (the actual CBC, CRC, Title 24, San Jose Municipal Code, Saratoga Article 15, etc.) before relying on findings that cite specific values.
- `.docx`, `.xlsx`, and `.pdf` are NOT yet auto-parsed. Convert to `.md`/`.txt` first, or paste the content into a `.md` file. (Native parsing is on the roadmap.)

### When to graduate to RAG (V1.2 roadmap)

If you want to drop in entire code book PDFs (e.g. all of CBC + CRC + Title 24 = hundreds of thousands of words), reference files won't scale — you'd hit token cost issues. At that point, we add ChromaDB-based retrieval-augmented generation: the tool indexes your code PDFs once, then per-page review retrieves only the most relevant snippets.

---

## How to stop

Close the browser tab — the app keeps running in the background.

To stop it completely:

1. Click into the black terminal window.
2. Press **Ctrl + C**.
3. The window will return to a normal prompt. You can now close it.

---

## Setting your OpenAI API key

The app needs an OpenAI API key to call GPT-5.4 vision.

1. Get a key from <https://platform.openai.com/api-keys> (you must have credit on the account).
2. Open the file **`.env`** in this folder with any text editor (Notepad is fine).
3. Replace `your_key_here` with your real key. The line should look like:
   ```
   OPENAI_API_KEY=sk-proj-yourActualKeyHere...
   ```
4. Save the file.
5. If the app is already running, just refresh the browser tab — the key is re-read automatically.
6. The red "OpenAI key not set" banner should disappear.

The `.env` file is **never** uploaded anywhere. It stays on your laptop. Do not share it.

---

## Known limits

- **100 sheets max per upload.** Larger sets are silently truncated to the first 100 to keep run times predictable. Split the set if you need to audit the rest.
- **8 to 18 seconds per sheet.** Slower for dense drawings, faster for simple ones. Patience is normal.
- **Jurisdictional grounding is prompt-level only.** Selecting *Delhi (DDA + NBC India)* tells the AI to apply NBC + DDA conventions, but the AI is not retrieving the actual NBC or DDA text. Verify any specific code citations against the real code book.
- **Cross-discipline coordination is not checked.** The AI reviews each sheet in isolation; it does not catch column mismatches between architectural and structural sheets.
- **Findings are AI-generated.** Always verify before acting. This tool is a fast second pair of eyes, not a replacement for a qualified plan reviewer.

---

## Project files

```
Planchecker auditor/
├── PLAN.md                  master build plan (read first)
├── README.md                this file
├── .env                     your OpenAI API key (never share)
├── .env.example             template — safe to share
├── .gitignore
├── requirements.txt         Python dependencies
├── start.bat                Windows one-click launcher
├── app.py                   Streamlit UI (entry point)
├── pdf_processor.py         PDF reading, page rendering, multi-file merge
├── ai_reviewer.py           AI vision calls + multi-page loop + jurisdiction wiring
├── prompts.py               base prompt + jurisdiction addenda
├── pin_overlay.py           pin/marker rendering on sheet images (severity colors, 3x3 zones)
├── pdf_report.py            multi-page PDF report builder (cover + annotated sheets + register)
└── venv/                    Python virtual environment (do not commit)
```

---

## Troubleshooting

**"OPENAI KEY NOT SET" banner shows even after I edited `.env`.**
The Streamlit server cached the old environment when it started. Close the terminal window (Ctrl + C), then double-click `start.bat` again. Future edits to `.env` are picked up automatically without needing a restart.

**`Client.__init__() got an unexpected keyword argument 'proxies'`**
Means the `httpx` library got upgraded past 0.27. Fix from a terminal in this folder:
```
venv\Scripts\activate
pip install httpx==0.27.2
```
Then restart the app.

**The browser does not open automatically.**
Open it yourself and go to <http://localhost:8501>.

**Run Plan Check button is greyed out.**
Your API key is missing or still set to `your_key_here`. See the "Setting your OpenAI API key" section above.

**A sheet errored out during the run.**
A red banner lists the affected sheets. The rest of the run continues. Check that the PDF page is not corrupted; a re-upload often fixes transient errors.

**The output looks generic or doesn't reference the codes I expect.**
You probably ran with *Jurisdiction: None*. Set jurisdiction to *California (state)* or one of the city/county options before clicking Run — the AI will then be told to apply CBC, CRC, Title 24, ADU state law, and (for city options) the relevant local amendments. Observation-based findings (missing dimensions, unlabeled rooms, missing schedules) are valid in any jurisdiction regardless.

---

## What is NOT in this build (planned for later)

- **V1.2 — RAG over real code books** (NBC India, DDA, HUDA, Punjab byelaws) so findings cite real, retrieved code sections instead of relying on prompt-level grounding
- **Acknowledge / Dismiss** buttons per finding (so users can mark false positives and exclude them from the PDF report)
- **AI confidence scores** per finding (so users can prioritize high-confidence items)
- **Cloud deploy + login + per-user usage limits + Stripe billing** (the actual SaaS layer)
- Cross-discipline coordination checking
- Spec vs. drawing comparison
- RFI generation
- Multilingual UI (Hindi, Punjabi)
- Pixel-precise bounding boxes on annotations (current approach uses 3×3 zones, which the AI handles reliably; pixel boxes are unreliable enough today that they often hurt more than help)

If you want any of these, run a few real audits with the current build first so we know which next features matter most.
