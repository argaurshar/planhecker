# PLAN.md — Master Build Instructions for Claude Code

> **Instructions to Claude Code:** This file is the single source of truth for this project. Read it fully before doing anything. Execute the phases in order. Do not skip steps. Do not add features that are not in this plan. When a phase is complete, confirm with the user before moving to the next phase. If the user asks for something outside this plan, gently remind them this is the MVP scope and ask if they want to extend the plan or stay focused.

---

## 1. Project Overview

**Product name:** PlanCheck Lite (working title, can change later)

**One-line description:** A tool that runs on my laptop where I upload one construction PDF and get back a list of issues the AI found.

**Goal of this MVP:** Prove that an AI plan-check tool gives me useful findings on real permit sets I have already submitted. Build the absolute simplest version that works. No login, no payment, no fancy UI, no database, no cloud hosting. Just a webpage that opens on my laptop, accepts a PDF, and shows findings.

**Success criteria:**

1. I can run one command in the terminal and a webpage opens
2. I can drag-and-drop a PDF into the page
3. Within 2 to 5 minutes, a list of findings appears
4. Each finding has: severity, page number, short description, evidence
5. I can copy the findings list out of the page

**Non-goals (do NOT build any of this in MVP):**

- User accounts or login
- Payments or pricing
- Multiple users or teams
- Database (no Postgres, no Supabase, no Firebase)
- Saving past projects (each upload is fresh)
- Email notifications
- Code library (IBC, CBC, Title 24 ingestion)
- Cross-discipline coordination logic
- Procore or Autodesk integration
- A landing page or marketing site
- Mobile responsiveness
- Dark mode
- Custom branding or logos
- Production deployment

If the user asks for any of the above during MVP, respond: "That's a great V1 feature. Let's finish the MVP first and add it later."

---

## 2. Tech Stack (LOCKED — do not change)

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | Best PDF and AI library support |
| UI framework | Streamlit | Single-file web UI, built-in file upload |
| PDF parsing | PyMuPDF (fitz) | Best PDF library for vector + raster |
| Page-to-image | pypdfium2 | Fast rendering for vision API |
| AI model | OpenAI GPT-5.4 via OpenAI Python SDK | Vision + long context |
| Env vars | python-dotenv | Load API key from `.env` file |
| Dependency mgmt | requirements.txt | Standard, simple |

**Do not introduce:** React, Next.js, FastAPI, Flask, Docker, Postgres, Redis, Celery, AWS, or any other framework. We add complexity later only when needed.

---

## 3. Prerequisites the User Must Have Before Starting

Before Claude Code does anything, confirm the user has all of these. If any are missing, walk them through installing each one:

- [ ] Python 3.11 or newer installed (`python --version` in terminal)
- [ ] A code editor open (VS Code or Cursor) showing the project folder
- [ ] An OpenAI API key from https://platform.openai.com
- [ ] At least $10 of credits on the OpenAI account
- [ ] A test PDF on their computer (a real construction drawing set, ideally 20 to 100 pages)

Do not proceed to Phase 1 until all five are confirmed.

---

## 4. Folder Structure (target)

By end of MVP, the project folder should look exactly like this:

```
Planchecker auditor/
├── PLAN.md                  (this file)
├── README.md                (how to run the app)
├── .env                     (contains ANTHROPIC_API_KEY, never commit)
├── .env.example             (template for .env, safe to share)
├── .gitignore
├── requirements.txt
├── app.py                   (the Streamlit app, main entry point)
├── pdf_processor.py         (functions for PDF reading)
├── ai_reviewer.py           (functions for calling Claude)
├── prompts.py               (AI prompt templates)
└── sample_findings.json     (example output format reference)
```

Keep it flat. No subfolders for MVP.

---

## 5. Phased Build Plan

Each phase has: goal, tasks, acceptance test. Do not start the next phase until the user confirms the current phase passes its acceptance test.

---

### PHASE 1 — Project skeleton (target time: 1 to 2 hours)

**Goal:** A folder, a virtual environment, dependencies installed, an empty Streamlit app that opens in the browser and says "Hello PlanCheck."

**Tasks:**

1. Confirm we are already inside the project folder `Planchecker auditor` (the user has already created it)
2. Create a Python virtual environment: `python -m venv venv`
3. Activate it (Windows: `venv\Scripts\activate`, Mac/Linux: `source venv/bin/activate`)
4. Create `requirements.txt` with these exact lines:
   ```
   streamlit==1.39.0
   openai==1.54.0
   pymupdf==1.24.10
   pypdfium2==4.30.0
   python-dotenv==1.0.1
   pillow==10.4.0
   ```
5. Run `pip install -r requirements.txt`
6. Create `.env.example` with `OPENAI_API_KEY=your_key_here`
7. Create `.env` and put the user's real key in it
8. Create `.gitignore` with: `.env`, `venv/`, `__pycache__/`, `*.pyc`, `.DS_Store`
9. Create `app.py` with a minimal Streamlit page:
   ```python
   import streamlit as st
   st.set_page_config(page_title="PlanCheck Lite", layout="wide")
   st.title("PlanCheck Lite")
   st.write("Hello PlanCheck. Upload a PDF to begin.")
   ```
10. Run `streamlit run app.py`

**Acceptance test:** A browser tab opens at http://localhost:8501 and shows the title "PlanCheck Lite" and the text "Hello PlanCheck."

**Stop here and confirm with user before continuing.**

---

### PHASE 2 — PDF upload and page rendering (target time: 2 to 4 hours)

**Goal:** User can upload a PDF, the app shows page count, the first 3 pages render as images on screen.

**Tasks:**

1. In `app.py`, add a `st.file_uploader` accepting only PDFs
2. Create `pdf_processor.py` with two functions:
   - `get_pdf_info(pdf_bytes) -> dict` — returns total page count, file size, and any title block text from page 1
   - `render_page_to_image(pdf_bytes, page_number, dpi=150) -> PIL.Image` — renders a single page using pypdfium2
3. In `app.py`, when a file is uploaded:
   - Read the bytes
   - Show the page count
   - Display the first 3 pages as images using `st.image`
   - Add a button "Run Review" (it can do nothing for now)
4. Add a sidebar section showing: filename, file size in MB, page count

**Important:** Do NOT save the PDF to disk. Keep everything in memory using `pdf_bytes`. This avoids file path issues and is more secure.

**Acceptance test:** User uploads a real 50-page construction PDF. Within 10 seconds the page count shows, file size shows, and the first 3 pages render visibly. The "Run Review" button is visible but does nothing.

**Stop here and confirm with user before continuing.**

---

### PHASE 3 — Single-page AI review (target time: 3 to 5 hours)

**Goal:** When the user clicks "Run Review," the app sends ONE page (the first page) to Claude with vision and gets back findings.

**Tasks:**

1. Create `prompts.py` with one prompt constant:
   ```python
   SINGLE_PAGE_REVIEW_PROMPT = """
   You are a senior architect and plan checker reviewing a construction drawing.
   Review the provided drawing page and identify potential issues.

   Look for:
   - Code compliance concerns (egress, ADA, fire ratings, exhaust, lighting)
   - Drawing errors (missing dimensions, conflicting callouts, missing labels)
   - Coordination issues visible on this page
   - Constructability concerns

   For each issue found, return STRICTLY JSON in this format:
   {
     "findings": [
       {
         "severity": "critical | major | minor | advisory",
         "category": "code | drawing_error | coordination | constructability",
         "description": "One-sentence description of the issue",
         "evidence": "What you see on the drawing that supports this finding",
         "recommendation": "What the architect should do about it"
       }
     ]
   }

   Rules:
   - Return only JSON, no other text
   - If you find no issues, return {"findings": []}
   - Do not invent code section numbers. If you cite a code, only cite codes you are 100% sure exist
   - Be specific. "Missing dimension" is not enough. Say which wall and what dimension is missing
   """
   ```

2. Create `ai_reviewer.py` with:
   - `review_single_page(image: PIL.Image) -> list[dict]` — calls OpenAI with the image + prompt, parses JSON, returns findings list
   - Use the OpenAI Python SDK with `model="gpt-5.4"`
   - Convert the PIL image to base64 and pass it as an `image_url` data URL in the chat message content
   - Wrap in try/except so a failed page returns `[]` not a crash

3. In `app.py`, wire up the "Run Review" button:
   - On click, render page 1 as image
   - Call `review_single_page` on it
   - Show a spinner while running
   - Display findings in a clean format below the page image

4. Display findings as a simple list with colored badges for severity:
   - Red badge for critical
   - Orange for major
   - Yellow for minor
   - Gray for advisory

**Acceptance test:** User uploads a real PDF, clicks Run Review, waits 30 to 60 seconds, sees a list of findings about page 1 with severities, descriptions, and evidence. At least one finding must look reasonable to the user.

**Stop here and confirm with user before continuing.**

---

### PHASE 4 — Multi-page review with progress (target time: 4 to 6 hours)

**Goal:** Review every page of the PDF, show progress, collect all findings into one list.

**Tasks:**

1. In `ai_reviewer.py`, add `review_full_pdf(pdf_bytes, progress_callback) -> list[dict]`:
   - Loop over every page
   - Render each page to image
   - Call `review_single_page` on each
   - Add `page_number` field to each finding
   - Call `progress_callback(current, total)` after each page
   - Return combined findings list

2. In `app.py`:
   - Add a `st.progress` bar
   - When user clicks Run Review, run `review_full_pdf` with a callback that updates the progress bar
   - Show estimated cost: pages × $0.05 (rough estimate, update later)
   - After done, show total findings count and a summary by severity

3. Add severity filter buttons at the top of the findings list:
   - All / Critical / Major / Minor / Advisory
   - Filter the displayed list when clicked

4. Add an "Export to CSV" button:
   - Use pandas (add to requirements.txt) or csv module
   - Download all findings as a CSV file

**Important:** Add a hard cap of 100 pages for MVP. If the PDF has more, show a warning and only review the first 100. We don't want a $50 surprise on a 500-page set.

**Acceptance test:** User uploads a 50-page real PDF, clicks Run Review, sees the progress bar advance, gets a list of findings spanning multiple pages within 5 to 15 minutes. They can filter by severity and download a CSV.

**Stop here and confirm with user before continuing.**

---

### PHASE 5 — Polish and ship to laptop (target time: 2 to 3 hours)

**Goal:** Fix the rough edges so this feels like a tool, not a prototype. Write a README so the user remembers how to run it tomorrow.

**Tasks:**

1. Add error handling in `app.py`:
   - If no API key set, show a clear error in red
   - If PDF is corrupted or unreadable, show a friendly message
   - If a page fails AI review, show "Page X skipped due to error" but don't crash the whole run

2. Add a "Clear and start over" button that resets the upload

3. Show the PDF page thumbnail next to each finding so the user can see what the AI was looking at

4. Add a basic "About this tool" expandable section at the bottom explaining what the tool does and its limitations

5. Write `README.md`:
   ```
   # PlanCheck Lite

   ## How to run

   1. Open terminal in this folder
   2. Activate venv: `venv\Scripts\activate` (Windows) or `source venv/bin/activate` (Mac)
   3. Run: `streamlit run app.py`
   4. Browser opens automatically
   5. Drag PDF in, click Run Review, wait

   ## How to stop
   Press Ctrl+C in the terminal.

   ## Known limits
   - Max 100 pages per PDF
   - Costs roughly $0.05 per page in API fees
   - First 30 seconds per page is normal
   - Findings are AI-generated, always verify before acting
   ```

6. Test the full flow end-to-end on three different real PDFs:
   - A small ADU permit set (10 to 30 pages)
   - A medium SFR remodel (50 to 80 pages)
   - A SB9 split with site plan (mix of disciplines)

**Acceptance test:** User can close the terminal, come back tomorrow, follow the README, and have the app running again in under 60 seconds. Three real PDFs each produce useful findings.

**MVP is complete after Phase 5.**

---

## 6. Validation Checklist (before declaring MVP done)

Walk through this list with the user. Every box must be checked.

- [ ] App opens at localhost:8501 from a single command
- [ ] PDF upload works for files up to 100 pages and 50 MB
- [ ] First-page preview renders within 5 seconds of upload
- [ ] "Run Review" button triggers a multi-page AI scan with visible progress
- [ ] Findings show severity, page number, description, evidence, recommendation
- [ ] Findings can be filtered by severity
- [ ] CSV export downloads a working file
- [ ] App handles errors without crashing (test by uploading a non-PDF and a 0-page PDF)
- [ ] User has run the app on at least 3 real PDFs and reviewed the findings
- [ ] User can confirm the findings include at least one issue they consider valuable

If even one box is unchecked, fix it before moving to V1 planning.

---

## 7. Known Issues and How to Handle Them

These will come up. Tell Claude Code to handle them this way:

| Issue | Fix |
|---|---|
| API key not set | Show a red error, point user to `.env.example` |
| PDF too large (>100 pages) | Refuse with a clear message, suggest splitting |
| Streamlit reruns the whole script on every interaction | Use `st.session_state` to cache PDF bytes and findings |
| GPT-5.4 returns text instead of JSON | Use `response_format={"type": "json_object"}` and re-prompt if needed |
| Image too large for API | Resize to max 1568 pixels on long edge before sending |
| OpenAI SDK timeout | Set timeout to 120 seconds, retry once on failure |
| User wants to add login | Refuse politely. Login is V1, not MVP |
| User wants cloud deploy | Refuse politely. Local laptop only for MVP |

---

## 8. Cost Estimate

For the user's planning:

- Phase 1 to 5 build cost: $5 to $20 in API testing
- Each full review of a 50-page PDF: roughly $2 to $5 in API fees
- Each full review of a 200-page PDF: roughly $8 to $20

Tell the user to budget $50 of API credits for the build phase plus $20 for ongoing testing.

---

## 9. After MVP — What's Next (do NOT build any of this yet)

Capture these for V1 conversation later:

- Login and saved projects (Supabase auth + Postgres)
- Spec vs drawing comparison (upload two PDFs)
- Code library upload (custom city codes)
- Findings management (assign, status, comments)
- Web hosting (Vercel + Railway)
- Stripe payments
- Re-run on revised drawings with diff
- RFI generation

---

## 10. Communication Rules with User

While executing this plan, Claude Code should:

- Explain every command before running it
- After each phase, summarize what was built and what to test
- Use plain English. Avoid jargon. If a term must be used, define it in one sentence
- When errors happen, paste the error and explain what it means before fixing
- Never assume the user knows what a "package" or "import" or "endpoint" is. Define on first use
- Confirm with the user after each phase before moving on
- Track progress visibly. End each session with: "Completed: X. Next: Y."

---

## 11. Getting Started — First Message to Claude Code

When the user opens Claude Code for the first time in their project folder, they should paste this message:

> Read PLAN.md fully. Do not start coding yet. First, walk me through the Prerequisites section and confirm I have everything I need. Once confirmed, we begin Phase 1. Stop after each phase and wait for my confirmation before moving on. Explain everything in plain English because I'm not a coder.

---

End of PLAN.md
