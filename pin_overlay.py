"""Pin overlay helpers — draw numbered, severity-colored markers on rendered drawing pages.

Each "pin" represents one finding's approximate location on a sheet, placed in
one of nine 3x3 grid zones (or center for full-sheet findings). Pins carry the
finding's FND-NN label and are colored by severity so architects can scan a
sheet and immediately see issue density and seriousness.
"""

import io

from PIL import Image, ImageDraw, ImageFont


_REGION_TO_FRACTION = {
    "top-left":      (1 / 6, 1 / 6),
    "top-center":    (3 / 6, 1 / 6),
    "top-right":     (5 / 6, 1 / 6),
    "center-left":   (1 / 6, 3 / 6),
    "center":        (3 / 6, 3 / 6),
    "center-right":  (5 / 6, 3 / 6),
    "bottom-left":   (1 / 6, 5 / 6),
    "bottom-center": (3 / 6, 5 / 6),
    "bottom-right":  (5 / 6, 5 / 6),
    "full-sheet":    (3 / 6, 3 / 6),
}

# RGB tuples matching the blueprint UI palette
_SEVERITY_COLORS = {
    "critical": (232, 101, 79),
    "major":    (240, 160, 96),
    "minor":    (232, 200, 79),
    "advisory": (127, 203, 227),
}

VALID_REGIONS = tuple(_REGION_TO_FRACTION.keys())


def normalize_region(region) -> str:
    """Map any value to a valid region key. Falls back to 'center'."""
    if region is None:
        return "center"
    r = str(region).strip().lower()
    return r if r in _REGION_TO_FRACTION else "center"


def normalize_severity(sev) -> str:
    s = (sev or "").strip().lower()
    return s if s in _SEVERITY_COLORS else "advisory"


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    """Try common system fonts; fall back to PIL's bitmap default."""
    for candidate in (
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        try:
            return ImageFont.truetype(candidate, size=size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


def annotate_sheet(image: Image.Image, pins: list[dict]) -> Image.Image:
    """Draw severity-colored numbered pins on a copy of `image`.

    Each pin dict needs:
      - label:    str — short text drawn inside the pin (e.g. '07')
      - region:   str — one of VALID_REGIONS (invalid values fall back to 'center')
      - severity: str — one of critical/major/minor/advisory

    Multiple pins in the same region are offset in a small cluster so they don't
    overlap. Pins are clamped to stay fully inside the image.

    Returns a NEW PIL.Image (RGB). Does not modify the input.
    """
    if image.mode != "RGB":
        image = image.convert("RGB")
    annotated = image.copy()
    draw = ImageDraw.Draw(annotated, "RGBA")

    w, h = annotated.size
    pin_radius = max(14, min(w, h) // 28)
    font = _load_font(int(pin_radius * 1.05))

    # Group pins by region for cluster layout
    by_region: dict[str, list[dict]] = {}
    for pin in pins:
        region = normalize_region(pin.get("region"))
        by_region.setdefault(region, []).append(pin)

    for region, region_pins in by_region.items():
        fx, fy = _REGION_TO_FRACTION[region]
        center_x = int(fx * w)
        center_y = int(fy * h)
        n = len(region_pins)

        for i, pin in enumerate(region_pins):
            # Cluster offset: 3-wide grid pattern centered on the region
            col = (i % 3) - 1
            row = (i // 3) - (n // 6)
            offset = pin_radius * 2.6
            cx = int(center_x + col * offset)
            cy = int(center_y + (row * offset if n > 3 else 0))

            # Clamp inside image bounds
            margin = pin_radius + 4
            cx = max(margin, min(w - margin, cx))
            cy = max(margin, min(h - margin, cy))

            severity = normalize_severity(pin.get("severity"))
            color = _SEVERITY_COLORS[severity]

            # White ring for contrast against any drawing background
            ring_r = pin_radius + 4
            draw.ellipse(
                (cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r),
                fill=(255, 255, 255, 235),
                outline=(11, 27, 45, 255),
                width=2,
            )
            # Severity-colored disc
            draw.ellipse(
                (cx - pin_radius, cy - pin_radius, cx + pin_radius, cy + pin_radius),
                fill=color + (255,),
                outline=(255, 255, 255, 255),
                width=2,
            )

            # Centered label
            label = str(pin.get("label", "?"))
            try:
                bbox = draw.textbbox((0, 0), label, font=font)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
                ty_offset = bbox[1]
            except AttributeError:
                tw, th = font.getsize(label)
                ty_offset = 0
            draw.text(
                (cx - tw // 2, cy - th // 2 - ty_offset),
                label,
                fill=(255, 255, 255, 255),
                font=font,
                stroke_width=1,
                stroke_fill=(11, 27, 45, 220),
            )

    return annotated


def encode_jpeg_data_url(image: Image.Image, quality: int = 78) -> str:
    """Convenience: encode a PIL image as a base64 JPEG data URL."""
    import base64
    if image.mode != "RGB":
        image = image.convert("RGB")
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=quality, optimize=True)
    return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"
