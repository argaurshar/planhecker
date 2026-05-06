# Editorial guide PDF template.
#
# To build a new guide:
#   1. Copy this file to your working directory (don't edit the skill copy).
#   2. Change OUT to your desired PDF path.
#   3. Edit the cover fields (wordmark, eyebrow, h1, subtitle, byline values).
#   4. Replace the body sections with your guide content.
#   5. Add or remove figures. See figures.md next to this file for reusable SVGs.
#   6. Run: python build_guide_pdf.py
#
# Design rules are in SKILL.md. Short version:
#   palette = cream #faf9f5, black #141413, orange #d97757, warm gray #e8e6dc, mid gray #b0aea5
#   Poppins for display/headers, Lora for body.
#   Orange is an accent, never a fill.
#
# Requires: pip install weasyprint

from weasyprint import HTML, CSS

# Set this to your target PDF output path.
OUT = "your-guide-title.pdf"

html = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Your Guide Title</title>
</head>
<body>

<!-- =========================================================
     COVER PAGE
     Replace the wordmark, eyebrow, title, subtitle, and byline.
     ========================================================= -->
<section class="cover">
  <div class="cover-top">
    <div class="wordmark">Your Brand or Project</div>
    <div class="doc-type">Guide &middot; No. 01</div>
  </div>

  <div class="cover-middle">
    <div class="eyebrow">A short, italicized tagline</div>
    <h1>The Guide<br>Title</h1>
    <div class="rule"></div>
    <div class="subtitle">One or two sentence subtitle that tells the reader exactly what they'll walk away with. Keep it concrete and specific.</div>
  </div>

  <div class="cover-bottom">
    <div class="byline-col">
      <div class="byline-label">Written by</div>
      <div class="byline-value">Author Name</div>
    </div>
    <div class="byline-col">
      <div class="byline-label">Published</div>
      <div class="byline-value">Month Year</div>
    </div>
    <div class="byline-col">
      <div class="byline-label">Community</div>
      <div class="byline-value">your-link.com</div>
    </div>
  </div>
</section>

<!-- =========================================================
     CONTENT
     This is where the guide body lives. The sections below
     demonstrate every component the stylesheet supports:
       - h2 section headers
       - paragraphs + bold
       - callout box
       - figures (SVG inline)
       - numbered steps
       - prompt blocks (copy-paste)
       - tools section
       - checklist
       - signoff

     Delete the example content, keep the component markup.
     ========================================================= -->
<section class="content">

<h2>Section One: The Problem</h2>
<p>Open with the pain point your guide solves. Keep it short and concrete. The reader should recognize themselves in the first paragraph and think "yes, that's me."</p>

<p>Follow up with a one sentence promise of what this guide will do for them. Something like: by the end of this guide, you'll have <b>the thing they want</b> up and running in under fifteen minutes.</p>

<div class="callout">
  <div class="callout-title">The big idea</div>
  <div class="callout-body">Use callouts to summarize the core concept of a section in one or two sentences. They break up long stretches of prose and give the reader a moment to land.</div>
</div>

<figure class="figure">
  <svg viewBox="0 0 600 340" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#d97757"/>
      </marker>
    </defs>

    <!-- Left window -->
    <g>
      <rect x="40" y="40" width="200" height="120" rx="6" fill="#faf9f5" stroke="#141413" stroke-width="1.5"/>
      <rect x="40" y="40" width="200" height="22" rx="6" fill="#141413"/>
      <circle cx="52" cy="51" r="3" fill="#d97757"/>
      <circle cx="62" cy="51" r="3" fill="#faf9f5"/>
      <circle cx="72" cy="51" r="3" fill="#faf9f5"/>
      <text x="140" y="55" text-anchor="middle" font-family="Poppins,Arial" font-size="10" font-weight="600" fill="#faf9f5">APP ONE</text>
      <line x1="60" y1="85" x2="220" y2="85" stroke="#e8e6dc" stroke-width="1.5"/>
      <line x1="60" y1="100" x2="200" y2="100" stroke="#e8e6dc" stroke-width="1.5"/>
      <line x1="60" y1="115" x2="210" y2="115" stroke="#e8e6dc" stroke-width="1.5"/>
      <line x1="60" y1="130" x2="180" y2="130" stroke="#e8e6dc" stroke-width="1.5"/>
    </g>

    <!-- Right window -->
    <g>
      <rect x="360" y="40" width="200" height="120" rx="6" fill="#faf9f5" stroke="#141413" stroke-width="1.5"/>
      <rect x="360" y="40" width="200" height="22" rx="6" fill="#141413"/>
      <circle cx="372" cy="51" r="3" fill="#d97757"/>
      <circle cx="382" cy="51" r="3" fill="#faf9f5"/>
      <circle cx="392" cy="51" r="3" fill="#faf9f5"/>
      <text x="460" y="55" text-anchor="middle" font-family="Poppins,Arial" font-size="10" font-weight="600" fill="#faf9f5">APP TWO</text>
    </g>

    <!-- Arrows down -->
    <g stroke="#d97757" stroke-width="1.5" fill="none">
      <path d="M 140 170 L 140 210 L 260 210 L 260 240" marker-end="url(#arrow)"/>
      <path d="M 460 170 L 460 210 L 340 210 L 340 240" marker-end="url(#arrow)"/>
    </g>

    <!-- Shared folder -->
    <g>
      <path d="M 220 250 L 260 250 L 275 264 L 380 264 L 380 312 L 220 312 Z" fill="#e8e6dc" stroke="#141413" stroke-width="1.5"/>
      <text x="300" y="292" text-anchor="middle" font-family="Poppins,Arial" font-size="11" font-weight="600" fill="#141413">Shared folder</text>
      <text x="300" y="305" text-anchor="middle" font-family="Lora,Georgia" font-size="8" font-style="italic" fill="#141413">one place, two views</text>
    </g>
  </svg>
  <figcaption>FIG. 01 &mdash; A short caption that explains what the figure is showing.</figcaption>
</figure>

<h2>Section Two: The Setup</h2>
<p>Use this section to walk the reader through the setup. Numbered steps work best. Keep each step to one sentence of instruction plus one or two of explanation.</p>

<div class="step">
  <div class="step-num">1</div>
  <div class="step-content">
    <div class="step-title">The first thing to do</div>
    <div class="step-body">A one sentence instruction. Follow with a short explanation of why this step matters.</div>
  </div>
</div>

<div class="step">
  <div class="step-num">2</div>
  <div class="step-content">
    <div class="step-title">The next thing to do</div>
    <div class="step-body">Keep the instructions tight. Assume the reader is smart but new to this topic.</div>
  </div>
</div>

<div class="step">
  <div class="step-num">3</div>
  <div class="step-content">
    <div class="step-title">The third thing to do</div>
    <div class="step-body">If a step has a prompt, put it right after the step. See below.</div>
  </div>
</div>

<div class="prompt">
  <div class="prompt-label">PROMPT 1 / SHORT DESCRIPTION</div>
  <div class="prompt-body">Prompt blocks are for content you want the reader to copy and paste. The dark background signals "this is a thing to grab." Write prompts in plain language, first person if that fits the voice of the guide.</div>
</div>

<div class="step">
  <div class="step-num">4</div>
  <div class="step-content">
    <div class="step-title">The last thing to do</div>
    <div class="step-body">End the setup section feeling like the reader just completed something real.</div>
  </div>
</div>

<h2>Section Three: Why This Works</h2>
<p>After the setup, explain the payoff. What does the reader now have that they didn't before? What can they do with it? Keep the tone confident and concrete.</p>

<p>This is also a good spot for a second figure if the payoff benefits from a visual. See figures.md for three reference SVGs you can adapt.</p>

<h2>Tools You'll Need</h2>
<div class="tools">
  <div class="tool">
    <div class="tool-name">Tool One</div>
    <div class="tool-meta">Free / tool-one.com</div>
    <div class="tool-desc">One sentence on what the tool does and why it matters for this setup.</div>
  </div>
  <div class="tool">
    <div class="tool-name">Tool Two</div>
    <div class="tool-meta">Free or paid / tool-two.com</div>
    <div class="tool-desc">Keep tool descriptions short. The reader can click through if they want more.</div>
  </div>
</div>

<h2>Do This Today</h2>
<p>Close with a short action checklist. Pick three concrete things the reader can do in the next fifteen minutes. Don't list ten. Three is the sweet spot.</p>
<ol class="checklist">
  <li>The smallest possible first action.</li>
  <li>The action that gets them halfway there.</li>
  <li>The action that finishes it.</li>
</ol>
<p>If the reader does these three things, they'll already have most of the value of this guide.</p>

<div class="signoff">
  <div class="signoff-text">Talk soon,</div>
  <div class="signoff-name">Author</div>
</div>

</section>

</body>
</html>
"""

css = """
@page {
  size: Letter;
  margin: 0.95in 0.95in 1.1in 0.95in;
  background: #faf9f5;
  @bottom-center {
    content: "Your Guide Title   \\2022   Author Name   \\2022   " counter(page);
    font-family: 'Lora', 'Georgia', serif;
    font-size: 9pt;
    color: #b0aea5;
  }
}

@page :first {
  margin: 0;
  @bottom-center { content: ""; }
}

* { box-sizing: border-box; }

html, body { background: #faf9f5; }

body {
  font-family: 'Lora', 'Georgia', serif;
  color: #141413;
  font-size: 11pt;
  line-height: 1.65;
  margin: 0;
  padding: 0;
}

/* COVER */
.cover {
  page: cover;
  width: 8.5in;
  height: 11in;
  background: #faf9f5;
  color: #141413;
  position: relative;
  page-break-after: always;
  padding: 0.95in 0.95in 0.95in 0.95in;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.cover-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 0.75pt solid #141413;
  padding-bottom: 14pt;
}
.wordmark {
  font-family: 'Poppins', 'Arial', sans-serif;
  font-size: 10pt;
  font-weight: 600;
  letter-spacing: 0.5pt;
  color: #141413;
}
.doc-type {
  font-family: 'Lora', 'Georgia', serif;
  font-style: italic;
  font-size: 10pt;
  color: #141413;
}

.cover-middle {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  max-width: 6.2in;
}
.eyebrow {
  font-family: 'Lora', 'Georgia', serif;
  font-style: italic;
  font-size: 13pt;
  color: #d97757;
  margin-bottom: 18pt;
}
.cover h1 {
  font-family: 'Poppins', 'Arial', sans-serif;
  font-size: 76pt;
  line-height: 0.95;
  font-weight: 600;
  margin: 0 0 26pt 0;
  letter-spacing: -2pt;
  color: #141413;
}
.rule {
  width: 0.6in;
  height: 3pt;
  background: #d97757;
  margin: 0 0 22pt 0;
}
.subtitle {
  font-family: 'Lora', 'Georgia', serif;
  font-size: 14pt;
  line-height: 1.55;
  color: #141413;
  max-width: 5.5in;
  font-weight: 400;
}

.cover-bottom {
  display: flex;
  justify-content: flex-start;
  gap: 0.55in;
  border-top: 0.75pt solid #141413;
  padding-top: 14pt;
}
.byline-col { min-width: 1.6in; }
.byline-label {
  font-family: 'Poppins', 'Arial', sans-serif;
  font-size: 8pt;
  letter-spacing: 1pt;
  text-transform: uppercase;
  color: #b0aea5;
  margin-bottom: 3pt;
}
.byline-value {
  font-family: 'Lora', 'Georgia', serif;
  font-size: 11pt;
  color: #141413;
}

/* CONTENT */
.content { padding-top: 0.1in; }

h2 {
  font-family: 'Poppins', 'Arial', sans-serif;
  font-size: 20pt;
  font-weight: 600;
  color: #141413;
  margin: 30pt 0 12pt 0;
  padding-bottom: 8pt;
  border-bottom: 0.75pt solid #141413;
  letter-spacing: -0.5pt;
}

p {
  margin: 0 0 11pt 0;
  font-family: 'Lora', 'Georgia', serif;
  color: #141413;
}

b, strong { color: #141413; font-weight: 700; }

/* CALLOUT */
.callout {
  background: #e8e6dc;
  border-left: 3pt solid #d97757;
  padding: 14pt 18pt;
  margin: 16pt 0;
}
.callout-title {
  font-family: 'Poppins', 'Arial', sans-serif;
  font-size: 8pt;
  font-weight: 600;
  letter-spacing: 1.5pt;
  text-transform: uppercase;
  color: #d97757;
  margin-bottom: 5pt;
}
.callout-body {
  font-family: 'Lora', 'Georgia', serif;
  font-size: 11pt;
  color: #141413;
  line-height: 1.6;
}

/* STEPS */
.step {
  display: flex;
  align-items: flex-start;
  margin: 0;
  padding: 12pt 0;
  border-bottom: 0.5pt solid #e8e6dc;
}
.step:last-of-type { border-bottom: none; }

.step-num {
  font-family: 'Poppins', 'Arial', sans-serif;
  width: 28pt;
  font-weight: 600;
  font-size: 16pt;
  color: #d97757;
  margin-right: 14pt;
  flex-shrink: 0;
  line-height: 1;
  padding-top: 2pt;
}
.step-content { flex: 1; }
.step-title {
  font-family: 'Poppins', 'Arial', sans-serif;
  font-size: 12pt;
  font-weight: 600;
  color: #141413;
  margin-bottom: 3pt;
}
.step-body {
  font-family: 'Lora', 'Georgia', serif;
  font-size: 11pt;
  color: #141413;
  line-height: 1.55;
}

/* PROMPTS */
.prompt {
  background: #141413;
  color: #faf9f5;
  padding: 16pt 20pt;
  margin: 16pt 0;
  border-left: 3pt solid #d97757;
}
.prompt-label {
  font-family: 'Poppins', 'Arial', sans-serif;
  font-size: 8pt;
  font-weight: 600;
  letter-spacing: 2pt;
  color: #d97757;
  margin-bottom: 8pt;
  text-transform: uppercase;
}
.prompt-body {
  font-family: 'Lora', 'Georgia', serif;
  font-size: 11pt;
  line-height: 1.6;
  color: #faf9f5;
  font-style: italic;
}

/* TOOLS */
.tools { margin: 12pt 0; }
.tool {
  border-top: 0.5pt solid #e8e6dc;
  padding: 12pt 0;
}
.tool:last-child { border-bottom: 0.5pt solid #e8e6dc; }
.tool-name {
  font-family: 'Poppins', 'Arial', sans-serif;
  font-size: 13pt;
  font-weight: 600;
  color: #141413;
}
.tool-meta {
  font-family: 'Lora', 'Georgia', serif;
  font-size: 10pt;
  color: #d97757;
  font-style: italic;
  margin: 2pt 0 4pt 0;
}
.tool-desc {
  font-family: 'Lora', 'Georgia', serif;
  font-size: 11pt;
  color: #141413;
}

/* CHECKLIST */
.checklist {
  padding-left: 0;
  list-style: none;
  counter-reset: item;
  margin: 12pt 0;
}
.checklist li {
  counter-increment: item;
  padding: 10pt 0 10pt 36pt;
  position: relative;
  font-family: 'Lora', 'Georgia', serif;
  font-size: 11pt;
  border-bottom: 0.5pt solid #e8e6dc;
  color: #141413;
}
.checklist li:first-child { border-top: 0.5pt solid #e8e6dc; }
.checklist li::before {
  content: counter(item, decimal-leading-zero);
  position: absolute;
  left: 0;
  top: 10pt;
  font-family: 'Poppins', 'Arial', sans-serif;
  color: #d97757;
  font-weight: 600;
  font-size: 11pt;
}

/* SIGNOFF */
.signoff {
  margin-top: 28pt;
  padding-top: 18pt;
  border-top: 0.75pt solid #141413;
}
.signoff-text {
  font-family: 'Lora', 'Georgia', serif;
  font-style: italic;
  font-size: 12pt;
  color: #141413;
}
.signoff-name {
  font-family: 'Poppins', 'Arial', sans-serif;
  font-size: 16pt;
  font-weight: 600;
  color: #141413;
  margin-top: 4pt;
}

.pagebreak { page-break-after: always; }

/* FIGURES */
.figure {
  margin: 22pt 0;
  padding: 14pt 0 0 0;
  text-align: center;
  page-break-inside: avoid;
}
.figure svg {
  width: 100%;
  max-width: 5.8in;
  height: auto;
}
.figure figcaption {
  font-family: 'Lora', 'Georgia', serif;
  font-style: italic;
  font-size: 9pt;
  color: #b0aea5;
  margin-top: 10pt;
  letter-spacing: 0.2pt;
}
"""

HTML(string=html).write_pdf(OUT, stylesheets=[CSS(string=css)])
print(f"Wrote {OUT}")
