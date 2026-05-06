"""PDF report builder for PlanCheck — editorial design language.

Visual design is borrowed from the `pdf-guide-test` skill (cream background,
orange accent, near-black ink, warm gray callouts, Helvetica/Times stand-ins
for the skill's Poppins/Lora typography). Document genre stays the same:
technical inspection report (cover + annotated sheets + findings register
+ disclaimer), not an editorial guide.

Engine is ReportLab — no WeasyPrint dependency, no Windows install pain.

Public API unchanged: app.py calls `build_report(...)` with the same kwargs.
"""

from __future__ import annotations

import io
from typing import Callable, Optional

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    Flowable,
    HRFlowable,
    Image as RLImage,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


# ─── Editorial palette (from the pdf-guide-test skill) ──────────────────────
CREAM     = colors.HexColor("#faf9f5")  # page background
INK       = colors.HexColor("#141413")  # primary text
ACCENT    = colors.HexColor("#d97757")  # orange — accent only, never fill
WARM_GRAY = colors.HexColor("#e8e6dc")  # callout backgrounds, hairline rows
MID_GRAY  = colors.HexColor("#b0aea5")  # captions, footers, secondary text

# ─── Severity palette (kept functional; tuned to read on cream) ─────────────
CRITICAL = colors.HexColor("#C24A38")
MAJOR    = colors.HexColor("#D8853D")
MINOR    = colors.HexColor("#B89535")  # slightly deeper ochre for cream legibility
ADVISORY = colors.HexColor("#7B7468")  # warm gray-brown (replaces blue; clashes with cream)

SEVERITY_COLOR = {
    "critical": CRITICAL,
    "major":    MAJOR,
    "minor":    MINOR,
    "advisory": ADVISORY,
}

# Typography — built-in ReportLab fonts as stand-ins for skill's Poppins + Lora
FONT_DISPLAY  = "Helvetica-Bold"   # Poppins SemiBold equivalent
FONT_DISPLAY_REG = "Helvetica"     # Poppins regular equivalent
FONT_BODY     = "Times-Roman"      # Lora regular equivalent
FONT_ITALIC   = "Times-Italic"     # Lora italic
FONT_BOLD     = "Times-Bold"       # Lora bold (used sparingly)


# ════════════════════════════════════════════════════════════════════════════
# Styles
# ════════════════════════════════════════════════════════════════════════════

def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()

    return {
        # Cover wordmark + doc-type (top bar)
        "wordmark": ParagraphStyle(
            "Wordmark", parent=base["BodyText"],
            fontName=FONT_DISPLAY, fontSize=10, leading=12,
            textColor=INK,
        ),
        "doctype": ParagraphStyle(
            "DocType", parent=base["BodyText"],
            fontName=FONT_ITALIC, fontSize=10, leading=12,
            textColor=INK, alignment=2,  # right-aligned
        ),

        # Cover middle: eyebrow / display title / subtitle
        "eyebrow": ParagraphStyle(
            "Eyebrow", parent=base["BodyText"],
            fontName=FONT_ITALIC, fontSize=12, leading=14,
            textColor=ACCENT, spaceAfter=14,
        ),
        "cover_h1": ParagraphStyle(
            "CoverH1", parent=base["BodyText"],
            fontName=FONT_DISPLAY, fontSize=46, leading=46,
            textColor=INK, spaceAfter=0,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle", parent=base["BodyText"],
            fontName=FONT_BODY, fontSize=12.5, leading=17,
            textColor=INK, spaceAfter=4,
        ),

        # Cover bottom: byline columns
        "byline_label": ParagraphStyle(
            "BylineLabel", parent=base["BodyText"],
            fontName=FONT_DISPLAY, fontSize=7.5, leading=10,
            textColor=MID_GRAY, spaceAfter=2,
        ),
        "byline_value": ParagraphStyle(
            "BylineValue", parent=base["BodyText"],
            fontName=FONT_BODY, fontSize=10.5, leading=13,
            textColor=INK,
        ),

        # Section header (h2 with bottom hairline)
        "h2": ParagraphStyle(
            "H2", parent=base["BodyText"],
            fontName=FONT_DISPLAY, fontSize=20, leading=22,
            textColor=INK, spaceBefore=10, spaceAfter=2,
        ),

        # Body
        "body": ParagraphStyle(
            "Body", parent=base["BodyText"],
            fontName=FONT_BODY, fontSize=10.5, leading=14.5,
            textColor=INK, spaceAfter=4,
        ),
        "body_italic": ParagraphStyle(
            "BodyItalic", parent=base["BodyText"],
            fontName=FONT_ITALIC, fontSize=10.5, leading=14.5,
            textColor=INK, spaceAfter=4,
        ),

        # Caption (italic, mid-gray) — for figure-style captions and meta lines
        "caption": ParagraphStyle(
            "Caption", parent=base["BodyText"],
            fontName=FONT_ITALIC, fontSize=9, leading=12,
            textColor=MID_GRAY, spaceAfter=2,
        ),

        # Editorial labels (small uppercase Helvetica-Bold, accent-colored)
        "label_orange": ParagraphStyle(
            "LabelOrange", parent=base["BodyText"],
            fontName=FONT_DISPLAY, fontSize=7.5, leading=10,
            textColor=ACCENT, spaceAfter=2,
        ),
        "label_gray": ParagraphStyle(
            "LabelGray", parent=base["BodyText"],
            fontName=FONT_DISPLAY, fontSize=7.5, leading=10,
            textColor=MID_GRAY, spaceAfter=2,
        ),
        "label_ink": ParagraphStyle(
            "LabelInk", parent=base["BodyText"],
            fontName=FONT_DISPLAY, fontSize=8, leading=10,
            textColor=INK, spaceAfter=2,
        ),

        # Source/category line on each finding (small ink)
        "finding_meta": ParagraphStyle(
            "FindingMeta", parent=base["BodyText"],
            fontName=FONT_DISPLAY, fontSize=8.5, leading=11,
            textColor=INK, spaceAfter=2,
        ),

        # Severity label below the colored bar
        "sev_label_critical": ParagraphStyle(
            "SevLabelCritical", parent=base["BodyText"],
            fontName=FONT_DISPLAY, fontSize=7.5, leading=10,
            textColor=CRITICAL, spaceAfter=0,
        ),
        "sev_label_major": ParagraphStyle(
            "SevLabelMajor", parent=base["BodyText"],
            fontName=FONT_DISPLAY, fontSize=7.5, leading=10,
            textColor=MAJOR, spaceAfter=0,
        ),
        "sev_label_minor": ParagraphStyle(
            "SevLabelMinor", parent=base["BodyText"],
            fontName=FONT_DISPLAY, fontSize=7.5, leading=10,
            textColor=MINOR, spaceAfter=0,
        ),
        "sev_label_advisory": ParagraphStyle(
            "SevLabelAdvisory", parent=base["BodyText"],
            fontName=FONT_DISPLAY, fontSize=7.5, leading=10,
            textColor=ADVISORY, spaceAfter=0,
        ),

        # Signoff (italic Times over display name)
        "signoff_text": ParagraphStyle(
            "SignoffText", parent=base["BodyText"],
            fontName=FONT_ITALIC, fontSize=12, leading=14,
            textColor=INK, spaceAfter=2,
        ),
        "signoff_name": ParagraphStyle(
            "SignoffName", parent=base["BodyText"],
            fontName=FONT_DISPLAY, fontSize=15, leading=18,
            textColor=INK, spaceAfter=0,
        ),
    }


# ════════════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════════════

def _normalize_severity(s) -> str:
    s = (s or "").strip().lower()
    return s if s in SEVERITY_COLOR else "advisory"


def _escape(text) -> str:
    """Escape XML/HTML metacharacters for ReportLab Paragraph."""
    if text is None:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _pil_to_flowable(
    img: PILImage.Image,
    width_mm: float,
    max_height_mm: Optional[float] = None,
) -> RLImage:
    """Convert a PIL.Image into a ReportLab Image flowable, scaled to width."""
    if img.mode != "RGB":
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=82, optimize=True)
    buf.seek(0)
    iw, ih = img.size
    target_w = width_mm * mm
    target_h = target_w * (ih / iw)
    if max_height_mm is not None and target_h > max_height_mm * mm:
        target_h = max_height_mm * mm
        target_w = target_h * (iw / ih)
    return RLImage(buf, width=target_w, height=target_h)


class _AccentBar(Flowable):
    """A thin horizontal accent bar — the skill's signature visual element.

    Used on the cover (orange under the title) and as the severity marker
    above each finding's label.
    """
    def __init__(self, color, width_pt: float, height_pt: float):
        super().__init__()
        self._color = color
        self._w = width_pt
        self._h = height_pt

    def wrap(self, *_):
        return (self._w, self._h)

    def draw(self):
        self.canv.setFillColor(self._color)
        self.canv.rect(0, 0, self._w, self._h, fill=1, stroke=0)


def _hairline(width_pt: float = 0.5, color=WARM_GRAY) -> HRFlowable:
    """A thin horizontal rule. Defaults match the skill's hairline (0.5pt warm gray)."""
    return HRFlowable(
        width="100%", thickness=width_pt, color=color,
        spaceBefore=0, spaceAfter=0, lineCap="butt",
    )


def _h2_with_rule(text: str, styles: dict) -> list:
    """Section header: large display text + 0.75pt black bottom rule (skill pattern)."""
    return [
        Paragraph(text, styles["h2"]),
        Spacer(1, 4),
        _hairline(width_pt=0.75, color=INK),
        Spacer(1, 8),
    ]


def _severity_marker(sev: str, styles: dict) -> Table:
    """The skill's signature severity marker: 2.5pt colored bar above tiny uppercase label.

    Replaces the old filled-box badge. More editorial — feels like a pull-quote
    accent rather than a stamp.
    """
    color = SEVERITY_COLOR[sev]
    style_key = f"sev_label_{sev}"
    label_style = styles.get(style_key, styles["sev_label_advisory"])

    table = Table(
        [
            ["", ""],  # row 0: bar
            [Paragraph(sev.upper(), label_style), ""],  # row 1: label text
        ],
        colWidths=[24 * mm, 0],
        rowHeights=[2.2, None],
    )
    table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (0, 0), color),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING",   (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
        ("TOPPADDING",   (0, 1), (0, 1), 4),
    ]))
    return table


# ════════════════════════════════════════════════════════════════════════════
# Page-template callbacks (cream background + footer)
# ════════════════════════════════════════════════════════════════════════════

def _paint_cream_background(canvas, doc):
    """Paint the entire page cream BEFORE content renders. Without this, ReportLab
    defaults to white, which is the #1 reason the previous PDF looked generic."""
    canvas.saveState()
    pw, ph = doc.pagesize
    canvas.setFillColor(CREAM)
    canvas.rect(0, 0, pw, ph, fill=1, stroke=0)
    canvas.restoreState()


def _make_first_page_handler():
    def handler(canvas, doc):
        # Cover page: cream background, NO footer.
        _paint_cream_background(canvas, doc)
    return handler


def _make_later_page_handler(project_name: str):
    safe_proj = project_name if project_name else "untitled"
    if len(safe_proj) > 36:
        safe_proj = safe_proj[:35] + "…"

    def handler(canvas, doc):
        _paint_cream_background(canvas, doc)
        canvas.saveState()
        canvas.setFont(FONT_ITALIC, 8.5)
        canvas.setFillColor(MID_GRAY)
        pw, _ph = doc.pagesize
        canvas.drawString(
            0.95 * inch, 0.55 * inch,
            f"PlanCheck   ·   Plan Review   ·   {safe_proj}   ·   AI-generated, verify before acting",
        )
        canvas.drawRightString(
            pw - 0.95 * inch, 0.55 * inch,
            f"{doc.page}",
        )
        canvas.restoreState()
    return handler


# ════════════════════════════════════════════════════════════════════════════
# Public API
# ════════════════════════════════════════════════════════════════════════════

def build_report(
    findings: list[dict],
    meta: dict,
    page_map: list | None,
    fallback_filename: str,
    annotated_sheet_provider: Optional[Callable[[int], PILImage.Image]] = None,
    finding_thumb_provider: Optional[Callable[[int], PILImage.Image]] = None,
) -> bytes:
    """Build a multi-page editorial PDF report and return its bytes.

    Public signature unchanged from the previous (blueprint-styled) builder
    so app.py call site is untouched.

    annotated_sheet_provider(page_num) -> PIL.Image
        Larger annotated render of a sheet with all its pins. None to skip.

    finding_thumb_provider(page_num) -> PIL.Image
        Smaller annotated thumbnail per finding row. None to skip.
    """
    s = _styles()
    buf = io.BytesIO()

    project_name = meta.get("project_name") or "Untitled Project"
    architect_name = meta.get("architect") or "—"
    jurisdiction = meta.get("jurisdiction") or "None"
    set_date = meta.get("set_date") or "—"
    generated_at = meta.get("generated_at") or "—"

    doc = SimpleDocTemplate(
        buf,
        pagesize=LETTER,
        leftMargin=0.95 * inch,
        rightMargin=0.95 * inch,
        topMargin=0.95 * inch,
        bottomMargin=1.05 * inch,
        title=f"PlanCheck — {project_name}",
        author="PlanCheck",
    )

    flow: list = []

    # ─────────────────────────────────────────────────────────────────────
    # COVER PAGE (editorial magazine layout)
    # ─────────────────────────────────────────────────────────────────────

    # Top bar: wordmark | doc-type with bottom hairline
    cover_top = Table(
        [[Paragraph("PlanCheck", s["wordmark"]),
          Paragraph(f"Plan Review · {set_date}", s["doctype"])]],
        colWidths=[doc.width / 2, doc.width / 2],
    )
    cover_top.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LINEBELOW", (0, 0), (-1, -1), 0.75, INK),
    ]))
    flow.append(cover_top)

    # Vertical spacer to push middle content down (rough vertical centering)
    flow.append(Spacer(1, 1.4 * inch))

    # Middle: eyebrow → display title → orange accent bar → subtitle
    flow.append(Paragraph(
        f'<i>An AI-assisted plan review · {jurisdiction}</i>',
        s["eyebrow"],
    ))
    flow.append(Paragraph(_escape(project_name), s["cover_h1"]))
    flow.append(Spacer(1, 18))
    flow.append(_AccentBar(ACCENT, width_pt=0.7 * inch, height_pt=3))
    flow.append(Spacer(1, 18))

    sev_counts = {sev: 0 for sev in SEVERITY_COLOR}
    for f in findings:
        sev_counts[_normalize_severity(f.get("severity"))] += 1
    total_findings = len(findings)

    flow.append(Paragraph(
        f"Generated for <b>{_escape(architect_name)}</b> on {_escape(generated_at)}. "
        f"<b>{total_findings}</b> finding{'' if total_findings == 1 else 's'} flagged across "
        f"the submitted drawing set.",
        s["subtitle"],
    ))

    # Vertical spacer to push byline strip to the bottom
    flow.append(Spacer(1, 1.6 * inch))

    # Bottom: byline strip with top hairline (3 columns)
    ref_files = meta.get("references_files") or []
    refs_short = (
        f"{len(ref_files)} file{'' if len(ref_files) == 1 else 's'}"
        if ref_files else "none"
    )

    byline_table = Table(
        [
            [
                Paragraph("Project", s["byline_label"]),
                Paragraph("Architect", s["byline_label"]),
                Paragraph("Generated", s["byline_label"]),
                Paragraph("Reference rules", s["byline_label"]),
            ],
            [
                Paragraph(_escape(project_name), s["byline_value"]),
                Paragraph(_escape(architect_name), s["byline_value"]),
                Paragraph(_escape(generated_at), s["byline_value"]),
                Paragraph(_escape(refs_short), s["byline_value"]),
            ],
        ],
        colWidths=[doc.width / 4] * 4,
    )
    byline_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEABOVE", (0, 0), (-1, 0), 0.75, INK),
    ]))
    flow.append(byline_table)
    flow.append(PageBreak())

    # ─────────────────────────────────────────────────────────────────────
    # SUMMARY PAGE (severity counts, callout)
    # ─────────────────────────────────────────────────────────────────────

    flow.extend(_h2_with_rule("Summary", s))

    flow.append(Paragraph(
        f"<b>{total_findings}</b> finding{'' if total_findings == 1 else 's'} across the submitted drawing set, "
        f"sorted below by severity. Each finding includes the source sheet, evidence, "
        f"and a recommended action.",
        s["body"],
    ))
    flow.append(Spacer(1, 14))

    # Severity score row — numbers in severity color above small labels in mid-gray.
    # Hairline rules above and below. No grid borders.
    # Row heights are deliberately generous to avoid the 36pt numerals clipping the labels.
    sev_table = Table(
        [
            [
                str(sev_counts["critical"]),
                str(sev_counts["major"]),
                str(sev_counts["minor"]),
                str(sev_counts["advisory"]),
            ],
            ["CRITICAL", "MAJOR", "MINOR", "ADVISORY"],
        ],
        colWidths=[doc.width / 4] * 4,
        rowHeights=[58, 18],
    )
    sev_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), FONT_DISPLAY),
        ("FONTSIZE", (0, 0), (-1, 0), 36),
        ("FONTNAME", (0, 1), (-1, 1), FONT_DISPLAY),
        ("FONTSIZE", (0, 1), (-1, 1), 7.5),
        ("TEXTCOLOR", (0, 1), (-1, 1), MID_GRAY),
        ("TEXTCOLOR", (0, 0), (0, 0), CRITICAL),
        ("TEXTCOLOR", (1, 0), (1, 0), MAJOR),
        ("TEXTCOLOR", (2, 0), (2, 0), MINOR),
        ("TEXTCOLOR", (3, 0), (3, 0), ADVISORY),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, 0), "TOP"),
        ("VALIGN", (0, 1), (-1, 1), "MIDDLE"),
        ("LINEABOVE", (0, 0), (-1, 0), 0.5, WARM_GRAY),
        ("LINEBELOW", (0, 1), (-1, 1), 0.5, WARM_GRAY),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, 0), 10),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
        ("TOPPADDING", (0, 1), (-1, 1), 0),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 0),
    ]))
    flow.append(sev_table)
    flow.append(Spacer(1, 18))

    # Callout: AI-generated reminder
    flow.extend(_callout(
        title="THE BIG IDEA",
        body=("These findings are generated by an AI vision model. Treat the report as a "
              "fast second pair of eyes — credible, often correct, but always to be verified "
              "against the source drawings and the applicable code books before acting."),
        styles=s,
    ))

    # ─────────────────────────────────────────────────────────────────────
    # PROJECT METADATA STRIP (replaces the old metadata table on cover)
    # ─────────────────────────────────────────────────────────────────────
    flow.append(Spacer(1, 18))
    flow.append(Paragraph("PROJECT", s["label_orange"]))
    flow.append(Spacer(1, 4))

    refs_full = (
        f"{', '.join(ref_files)} ({meta.get('references_word_count', 0):,} words)"
        if ref_files else "none"
    )
    meta_rows = [
        ["Project name",     project_name],
        ["Architect / firm", architect_name],
        ["Jurisdiction",     jurisdiction],
        ["Drawing set date", set_date],
        ["Generated",        generated_at],
        ["References",       refs_full],
    ]
    meta_table = Table(
        [
            [Paragraph(label.upper(), s["byline_label"]),
             Paragraph(_escape(value), s["byline_value"])]
            for label, value in meta_rows
        ],
        colWidths=[1.6 * inch, doc.width - 1.6 * inch],
    )
    meta_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, WARM_GRAY),
    ]))
    flow.append(meta_table)

    # ─────────────────────────────────────────────────────────────────────
    # ANNOTATED SHEETS SECTION
    # ─────────────────────────────────────────────────────────────────────

    pages_with_findings: list[int] = []
    seen = set()
    for f in findings:
        pn = f.get("page_number")
        if isinstance(pn, int) and pn > 0 and pn not in seen:
            seen.add(pn)
            pages_with_findings.append(pn)
    pages_with_findings.sort()

    if pages_with_findings and annotated_sheet_provider is not None:
        flow.append(PageBreak())
        flow.extend(_h2_with_rule("Annotated sheets", s))
        flow.append(Paragraph(
            f"{len(pages_with_findings)} sheet{'' if len(pages_with_findings) == 1 else 's'} "
            "with findings. Pins are colored by severity (red = critical, orange = major, "
            "yellow = minor, gray = advisory). Pin locations are zone-level; "
            "verify exact location against the source drawings.",
            s["caption"],
        ))
        flow.append(Spacer(1, 12))

        for i, pn in enumerate(pages_with_findings):
            try:
                img = annotated_sheet_provider(pn)
                if img is None:
                    continue

                if page_map and 0 < pn <= len(page_map):
                    src = page_map[pn - 1]
                    head_main = src.get("source_file", fallback_filename)
                    head_sub = f"p.{src.get('page_in_source', pn):02d}"
                else:
                    head_main = f"Sheet {pn:02d}"
                    head_sub = ""
                n_here = sum(1 for f in findings if f.get("page_number") == pn)

                # Header row: filename in bold + page in italic + finding count in mid gray
                head_table = Table(
                    [[
                        Paragraph(
                            f'<b>{_escape(head_main)}</b>'
                            + (f' &nbsp;·&nbsp; <i>{head_sub}</i>' if head_sub else ''),
                            s["finding_meta"],
                        ),
                        Paragraph(
                            f'{n_here} finding{"" if n_here == 1 else "s"}',
                            s["caption"],
                        ),
                    ]],
                    colWidths=[doc.width * 0.65, doc.width * 0.35],
                )
                head_table.setStyle(TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                    ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.5, WARM_GRAY),
                ]))

                block = [
                    head_table,
                    Spacer(1, 8),
                    _pil_to_flowable(img, width_mm=160, max_height_mm=185),
                ]
                flow.append(KeepTogether(block))
                if i < len(pages_with_findings) - 1:
                    flow.append(Spacer(1, 18))
            except Exception:
                continue

    # ─────────────────────────────────────────────────────────────────────
    # FINDINGS REGISTER
    # ─────────────────────────────────────────────────────────────────────

    flow.append(PageBreak())
    flow.extend(_h2_with_rule("Findings register", s))
    flow.append(Paragraph(
        f"All {total_findings} finding{'' if total_findings == 1 else 's'}, sorted by severity. "
        "Each entry includes the source sheet, evidence, and a suggested action. "
        "FND-NN labels match the pin numbers on the annotated sheets.",
        s["caption"],
    ))
    flow.append(Spacer(1, 12))

    severity_order = {"critical": 0, "major": 1, "minor": 2, "advisory": 3}
    indexed = list(enumerate(findings, 1))
    indexed.sort(key=lambda pair: (
        severity_order.get(_normalize_severity(pair[1].get("severity")), 99),
        pair[1].get("page_number", 0),
        pair[0],
    ))

    for idx, f in indexed:
        sev = _normalize_severity(f.get("severity"))
        cat = (f.get("category") or "—").replace("_", " ").upper()
        page_num = f.get("page_number")
        if page_map and isinstance(page_num, int) and 0 < page_num <= len(page_map):
            src = page_map[page_num - 1]
            src_label = f'{src.get("source_file", fallback_filename)} · p.{src.get("page_in_source", page_num):02d}'
        elif isinstance(page_num, int):
            src_label = f"Sheet {page_num:02d}"
        else:
            src_label = "—"

        # Thumbnail (or em-dash if not available)
        try:
            thumb_img = (
                finding_thumb_provider(page_num)
                if (finding_thumb_provider is not None and isinstance(page_num, int))
                else None
            )
        except Exception:
            thumb_img = None
        thumb_flow = (
            _pil_to_flowable(thumb_img, width_mm=38, max_height_mm=42)
            if thumb_img is not None
            else Paragraph("—", s["caption"])
        )

        # Left column: severity marker + thumbnail + FND-NN
        left_col = [
            _severity_marker(sev, s),
            Spacer(1, 6),
            thumb_flow,
            Spacer(1, 4),
            Paragraph(f'FND-{idx:02d}', s["caption"]),
        ]

        # Right column: source/category meta line + description + EVIDENCE / RECOMMENDATION
        right_col = [
            Paragraph(
                f'<b>{_escape(src_label)}</b>'
                f' &nbsp;<font color="#b0aea5">·</font>&nbsp; '
                f'<font color="#b0aea5">{_escape(cat)}</font>',
                s["finding_meta"],
            ),
            Spacer(1, 4),
            Paragraph(_escape(f.get("description") or "—"), s["body"]),
            Spacer(1, 6),
            Paragraph("EVIDENCE", s["label_orange"]),
            Paragraph(_escape(f.get("evidence") or "—"), s["body"]),
            Spacer(1, 4),
            Paragraph("RECOMMENDATION", s["label_orange"]),
            Paragraph(_escape(f.get("recommendation") or "—"), s["body"]),
        ]

        row_table = Table(
            [[left_col, right_col]],
            colWidths=[1.8 * inch, doc.width - 1.8 * inch],
        )
        row_table.setStyle(TableStyle([
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
            ("RIGHTPADDING",  (1, 0), (1, -1), 0),
            ("TOPPADDING",    (0, 0), (-1, -1), 14),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
            ("LINEBELOW",     (0, 0), (-1, -1), 0.5, WARM_GRAY),
        ]))
        flow.append(KeepTogether(row_table))

    # ─────────────────────────────────────────────────────────────────────
    # CLOSING / DISCLAIMER PAGE
    # ─────────────────────────────────────────────────────────────────────

    flow.append(PageBreak())
    flow.extend(_h2_with_rule("About this report", s))

    flow.append(Paragraph(
        "This report was produced by <b>PlanCheck</b>, an AI-assisted plan review tool. "
        "An AI vision model examines each drawing sheet, identifies potential issues — "
        "missing dimensions, unlabeled rooms, code-compliance concerns, drafting errors, "
        "constructability and coordination items — and returns a structured register of "
        "findings.",
        s["body"],
    ))
    flow.append(Paragraph(
        "Findings are generated quickly and consistently, which makes the tool a useful "
        "second pair of eyes before a permit submittal, a plan-check resubmittal, or an "
        "AHJ comment-response cycle. They are <b>not</b> a substitute for a licensed "
        "professional's judgment.",
        s["body"],
    ))

    flow.append(Spacer(1, 14))

    # Limitations callout
    flow.extend(_callout(
        title="IMPORTANT LIMITATIONS",
        body=(
            "<b>Verify before acting.</b> Findings are AI-generated. Always verify "
            "against the source drawings and applicable code books before incorporating "
            "any item into a submittal or comment response.<br/><br/>"
            "<b>Pins are zone-level, not pixel-precise.</b> Pin locations on annotated sheets "
            "indicate approximate 3×3 grid zones. Use the annotated thumbnails as a "
            "navigation aid; consult the source drawings for exact location.<br/><br/>"
            "<b>Code grounding is prompt-level.</b> Jurisdictional context (CBC, CRC, Title 24, "
            "state ADU law, plus city/county amendments) is applied via the AI's training "
            "knowledge augmented by the project's reference library. The tool does not "
            "retrieve actual code text. Verify any specific code section the AI cites against "
            "the source code book before relying on it.<br/><br/>"
            "<b>Cross-sheet coordination is not checked.</b> Issues only visible across "
            "multiple sheets (e.g., column mismatches between architectural and structural "
            "sheets) fall outside the tool's current scope."
        ),
        styles=s,
    ))

    flow.append(Spacer(1, 24))

    # Editorial signoff
    flow.append(_hairline(width_pt=0.75, color=INK))
    flow.append(Spacer(1, 14))
    flow.append(Paragraph("Reviewed and packaged by,", s["signoff_text"]))
    flow.append(Paragraph("PlanCheck", s["signoff_name"]))
    flow.append(Spacer(1, 6))
    flow.append(Paragraph(f"Generated {_escape(generated_at)}", s["caption"]))

    # Build with cream background on every page + footer on non-cover pages
    doc.build(
        flow,
        onFirstPage=_make_first_page_handler(),
        onLaterPages=_make_later_page_handler(project_name),
    )
    return buf.getvalue()


# ════════════════════════════════════════════════════════════════════════════
# Component helpers (kept local — used only by build_report)
# ════════════════════════════════════════════════════════════════════════════

def _callout(title: str, body: str, styles: dict) -> list:
    """Editorial callout: warm-gray background, orange left border, small uppercase title.

    Replicates the skill's `.callout` pattern. Returns a list of flowables (the
    callout itself + a trailing spacer) so the caller can `flow.extend(...)`.
    """
    inner = Table(
        [
            [Paragraph(title, styles["label_orange"])],
            [Paragraph(body, styles["body"])],
        ],
        colWidths=["100%"],
    )
    inner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), WARM_GRAY),
        ("LEFTPADDING", (0, 0), (-1, -1), 16),
        ("RIGHTPADDING", (0, 0), (-1, -1), 16),
        ("TOPPADDING", (0, 0), (0, 0), 12),
        ("BOTTOMPADDING", (0, 0), (0, 0), 4),
        ("TOPPADDING", (0, 1), (0, 1), 0),
        ("BOTTOMPADDING", (0, 1), (0, 1), 14),
        ("LINEBEFORE", (0, 0), (0, -1), 3, ACCENT),
    ]))
    return [inner, Spacer(1, 4)]
