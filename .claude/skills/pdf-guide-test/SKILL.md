---
name: pdf-guide-test
description: Turn any written guide, cheat sheet, playbook, walkthrough, tutorial, or how-to into a polished editorial-style PDF. Ships with a default warm editorial look (cream/black/orange palette, Poppins + Lora type, numbered steps, copy-paste prompt blocks, callouts, inline SVG figures) that you can override with your own brand colors, fonts, or voice. Trigger phrases include "create a guide", "write a guide", "build a guide", "make a guide", "turn this into a guide", "cheat sheet for", "walkthrough on", "setup guide for", "how-to on", "playbook for", "tutorial on", "write this up", "make a resource". Skip only for short posts, slide decks, or when the user explicitly wants docx or plain markdown.
---

# PDF Guide

This skill turns a written guide (setup walkthrough, cheat sheet, playbook, etc.) into a polished PDF with an editorial magazine look. Use it whenever the output is a standalone, shareable document that someone will download, read, and keep.

## Customizing for your brand

The defaults below give you a warm editorial look out of the box. Override any of it by telling Claude:
- **Colors:** "Use my brand colors — navy #0a2540 and gold #c6a656"
- **Fonts:** "Use Georgia for body and Helvetica Bold for headings"
- **Voice:** "Write it in a formal corporate tone" (overrides the casual default)
- **Cover style:** "No magazine cover, just start with the content"

If you don't specify, it uses the defaults.

## Default output look

A letter-size PDF with:

- **Cover page**: cream background (#faf9f5), top wordmark rule, large Poppins display title, orange accent bar, italic Lora subtitle, three-column byline at the bottom (Written by / Published / Community or similar). No images, no gradients. Editorial, not deck-y.
- **Interior pages**: cream background, Lora body, Poppins section headers underlined in black, orange (#d97757) accents, page footer in the margin.
- **Callout box**: light gray (#e8e6dc) background, orange left border, tiny orange uppercase label.
- **Numbered step rows**: large orange Poppins numerals next to Poppins titles and Lora body copy, separated by thin gray hairlines. No circle backgrounds.
- **Prompt blocks**: near-black background (#141413), cream italic Lora body, orange uppercase label, orange left border. Designed to be copy-pasted.
- **Tools section**: hairline-separated rows with tool name in Poppins, italic orange meta line, Lora description.
- **Checklist**: zero-padded decimal numbers (01, 02, 03) in orange, hairline rows.
- **Signoff**: italic "Talk soon," (or similar) over a Poppins display name.
- **Inline SVG figures** (optional but encouraged): drawn in the same palette with `FIG. NN` italic captions in muted gray.

## How to build a new guide

The skill bundles a template Python script at `assets/build_guide_pdf.py` that uses WeasyPrint. The workflow:

1. **Copy the template** into your working directory. Never edit the skill copy in place.
2. **Fill in the content**: cover fields (eyebrow, title, subtitle, byline values, doc number), then the HTML body (sections, callouts, steps, prompts, tools, checklist, signoff).
3. **Swap the palette/fonts** at the top of the script if the user gave you brand overrides.
4. **Add figures where they teach something** that text alone can't. Don't decorate, illustrate. Good triggers: a relationship between two things, a flow across time, a concept that benefits from a metaphor. If a figure wouldn't earn its space, skip it.
5. **Set the OUT path** at the top of the script to your desired output file.
6. **Run the script**: `python build_guide_pdf.py`
7. **Preview** with `pdftoppm -png -r 90 <pdf> prev` and open the PNGs to sanity-check layout. Check the cover, any figure page, and at least one content page before handing off.

The template is self-contained. The only system dependency is WeasyPrint (`pip install weasyprint`).

## Default design choices

These make it feel like an editorial magazine piece rather than a generic report. Keep them unless the user asks to change one.

- **Default palette**: `#faf9f5` cream, `#141413` near-black, `#d97757` orange accent, `#e8e6dc` light warm gray, `#b0aea5` mid gray (footers, figcaptions). Swap the accent and/or background if the user has brand colors.
- **Default typography**: Poppins (600) for display/headers/labels, Lora for all body copy and anything italic. Georgia/Arial are the fallbacks. Swap if requested.
- **Hairlines over boxes**: section headers get a single 0.75pt underline, step rows and checklist items use 0.5pt dividers. Avoid heavy rounded card containers; they make it look like a template.
- **Accent is an accent, not a fill**: the accent color lives in the header bar, step numbers, prompt labels/borders, and the `.rule` div. Never flood large areas with accent.
- **Prompt blocks are dark on cream**: the near-black prompt background is intentional — it flags copy-paste content without shouting.
- **Generous whitespace**: 0.95in page margins, 30pt space above h2, 22pt around figures. Let the page breathe.

## Default voice inside the guide

The PDF should read like a friend walking someone through a setup, not a corporate whitepaper. If the user asks for a more formal or technical tone, switch.

- Casual, friendly, explain-to-a-friend tone.
- Short paragraphs. Plain English. No jargon without a definition.
- Address the reader directly ("you").
- If prompts are included, quote them verbatim so readers can copy-paste.

## Figure guidelines

Figures are inline SVG inside `<figure class="figure">` with a `<figcaption>FIG. NN &mdash; short caption.</figcaption>`. See `assets/figures.md` for three reusable reference SVGs (two-apps-one-folder / central node with satellites / sources to processor to output) that you can adapt. When drawing new ones:

- Use the active palette (defaults or the user's brand colors).
- Draw with thin strokes (1 to 1.5pt). Prefer outlines over fills except for emphasis nodes.
- Keep viewBoxes around 600 wide. The CSS caps rendered width to 5.8in so they never dominate the page.
- Label everything in the display font for UI/labels and italic serif for asides.
- Captions start with `FIG. NN &mdash;` and the main meaning lives in the caption, since SVG text does not reflow.

## When NOT to use this skill

- Short posts, announcements, and social content. Those stay as markdown.
- Slide decks. Use a slides/slide-deck skill instead.
- Internal notes or scratch work. PDF is for polished, shareable deliverables.
- Anything the user wants to edit themselves afterwards. PDFs are hard to edit; offer a docx or markdown version instead.

## Output

Write the final PDF to the user's working/output folder with a descriptive kebab-case filename (e.g. `your-guide-title.pdf`), then share it back with a link so they can open or attach it in one click.
