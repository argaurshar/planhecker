# Reusable SVG Figures

Three reference infographics you can copy, adapt, and drop inside a `<figure class="figure">...<figcaption>FIG. NN — caption.</figcaption></figure>` block.

Palette (use nothing else):
- `#faf9f5` cream background
- `#141413` near-black outlines and fills
- `#d97757` orange accent
- `#e8e6dc` warm gray surfaces
- `#b0aea5` mid gray (reserve for figcaptions, handled via CSS)

All three are drawn on a viewBox wide enough (~600) that the CSS `.figure svg { max-width: 5.8in }` cap keeps them comfortable on the page.

---

## FIG. 01 — Two views, one folder

Shows two app windows with orange arrows flowing down into a single shared folder. Teaches the core idea that both tools are pointing at the same place on disk.

Use when: explaining integrations, shared data sources, "same files two views" concepts.

```html
<figure class="figure">
  <svg viewBox="0 0 600 340" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#d97757"/>
      </marker>
    </defs>

    <!-- Left app window -->
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

    <!-- Right app window -->
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
  <figcaption>FIG. 01 — Both apps point at the same folder on disk.</figcaption>
</figure>
```

---

## FIG. 02 — Knowledge graph / neuron network

A central orange node surrounded by labeled satellite nodes, connected by thin black synapse lines. Teaches the "your notes form a network" idea.

Use when: explaining second brains, knowledge graphs, how concepts connect, or any "central thing connects to many others" metaphor.

```html
<figure class="figure">
  <svg viewBox="0 0 600 320" xmlns="http://www.w3.org/2000/svg">
    <!-- synapses first so nodes sit on top -->
    <g stroke="#141413" stroke-width="0.7" fill="none" opacity="0.55">
      <line x1="300" y1="160" x2="130" y2="80"/>
      <line x1="300" y1="160" x2="470" y2="80"/>
      <line x1="300" y1="160" x2="90" y2="200"/>
      <line x1="300" y1="160" x2="510" y2="200"/>
      <line x1="300" y1="160" x2="200" y2="270"/>
      <line x1="300" y1="160" x2="400" y2="270"/>
      <line x1="130" y1="80" x2="470" y2="80"/>
      <line x1="90" y1="200" x2="200" y2="270"/>
      <line x1="510" y1="200" x2="400" y2="270"/>
    </g>

    <!-- center -->
    <g>
      <circle cx="300" cy="160" r="32" fill="#d97757" stroke="#141413" stroke-width="1.5"/>
      <text x="300" y="164" text-anchor="middle" font-family="Poppins,Arial" font-size="9" font-weight="600" fill="#faf9f5">CENTER</text>
    </g>

    <!-- satellites (rename labels to taste) -->
    <g font-family="Lora,Georgia" font-size="9" fill="#141413">
      <circle cx="130" cy="80" r="8" fill="#faf9f5" stroke="#141413" stroke-width="1.2"/>
      <text x="130" y="65" text-anchor="middle" font-style="italic">Label A</text>

      <circle cx="470" cy="80" r="8" fill="#faf9f5" stroke="#141413" stroke-width="1.2"/>
      <text x="470" y="65" text-anchor="middle" font-style="italic">Label B</text>

      <circle cx="90" cy="200" r="8" fill="#faf9f5" stroke="#141413" stroke-width="1.2"/>
      <text x="90" y="220" text-anchor="middle" font-style="italic">Label C</text>

      <circle cx="510" cy="200" r="8" fill="#faf9f5" stroke="#141413" stroke-width="1.2"/>
      <text x="510" y="220" text-anchor="middle" font-style="italic">Label D</text>

      <circle cx="200" cy="270" r="8" fill="#faf9f5" stroke="#141413" stroke-width="1.2"/>
      <text x="200" y="290" text-anchor="middle" font-style="italic">Label E</text>

      <circle cx="400" cy="270" r="8" fill="#faf9f5" stroke="#141413" stroke-width="1.2"/>
      <text x="400" y="290" text-anchor="middle" font-style="italic">Label F</text>
    </g>
  </svg>
  <figcaption>FIG. 02 — A central idea connected to everything around it.</figcaption>
</figure>
```

---

## FIG. 03 — Input pills → central processor → output card

Shows source pills on the left flowing into a central dark circle (a process, a schedule, an agent) and out to a styled output card on the right.

Use when: explaining a workflow, a scheduled task, a pipeline, or any "many things go in, one thing comes out" flow.

```html
<figure class="figure">
  <svg viewBox="0 0 600 280" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <marker id="arrow2" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#d97757"/>
      </marker>
    </defs>

    <!-- source pills (rename freely) -->
    <g font-family="Poppins,Arial" font-size="10" font-weight="600">
      <rect x="30" y="40" width="120" height="34" rx="17" fill="#faf9f5" stroke="#141413" stroke-width="1.2"/>
      <text x="90" y="61" text-anchor="middle" fill="#141413">Source A</text>

      <rect x="30" y="122" width="120" height="34" rx="17" fill="#faf9f5" stroke="#141413" stroke-width="1.2"/>
      <text x="90" y="143" text-anchor="middle" fill="#141413">Source B</text>

      <rect x="30" y="204" width="120" height="34" rx="17" fill="#faf9f5" stroke="#141413" stroke-width="1.2"/>
      <text x="90" y="225" text-anchor="middle" fill="#141413">Source C</text>
    </g>

    <g stroke="#d97757" stroke-width="1.5" fill="none">
      <path d="M 150 57 Q 220 57 260 120" marker-end="url(#arrow2)"/>
      <path d="M 150 139 L 260 139" marker-end="url(#arrow2)"/>
      <path d="M 150 221 Q 220 221 260 158" marker-end="url(#arrow2)"/>
    </g>

    <!-- central processor -->
    <g>
      <circle cx="320" cy="140" r="58" fill="#141413" stroke="#d97757" stroke-width="2"/>
      <text x="320" y="130" text-anchor="middle" font-family="Poppins,Arial" font-size="11" font-weight="600" fill="#faf9f5">PROCESS</text>
      <text x="320" y="148" text-anchor="middle" font-family="Lora,Georgia" font-size="9" font-style="italic" fill="#d97757">runs on a schedule</text>
      <text x="320" y="165" text-anchor="middle" font-family="Poppins,Arial" font-size="13" font-weight="600" fill="#faf9f5">6:00 PM</text>
    </g>

    <g stroke="#d97757" stroke-width="1.5" fill="none">
      <path d="M 378 140 L 440 140" marker-end="url(#arrow2)"/>
    </g>

    <!-- output card -->
    <g>
      <rect x="450" y="75" width="130" height="130" rx="4" fill="#e8e6dc" stroke="#141413" stroke-width="1.2"/>
      <rect x="450" y="75" width="130" height="20" rx="4" fill="#141413"/>
      <text x="515" y="89" text-anchor="middle" font-family="Poppins,Arial" font-size="8" font-weight="600" fill="#faf9f5">OUTPUT</text>
      <line x1="462" y1="110" x2="568" y2="110" stroke="#141413" stroke-width="0.6"/>
      <line x1="462" y1="122" x2="555" y2="122" stroke="#141413" stroke-width="0.6"/>
      <line x1="462" y1="134" x2="568" y2="134" stroke="#141413" stroke-width="0.6"/>
      <line x1="462" y1="146" x2="540" y2="146" stroke="#141413" stroke-width="0.6"/>
      <line x1="462" y1="158" x2="568" y2="158" stroke="#141413" stroke-width="0.6"/>
      <line x1="462" y1="170" x2="530" y2="170" stroke="#141413" stroke-width="0.6"/>
      <text x="515" y="200" text-anchor="middle" font-family="Lora,Georgia" font-size="8" font-style="italic" fill="#141413">waiting for you</text>
    </g>
  </svg>
  <figcaption>FIG. 03 — Sources flow in, a single polished output comes out.</figcaption>
</figure>
```

---

## Tips for making new figures

- Start by copying the closest of these three and renaming labels. Don't start from scratch.
- Keep total figure height under ~340 in the viewBox so it never dominates a page.
- Text inside SVGs does not reflow; keep labels short and don't rely on them to carry critical meaning. The figcaption is where the full meaning lives.
- If you need more than ~8 labeled elements, the figure is too busy. Split it or simplify.
