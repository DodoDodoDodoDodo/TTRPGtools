"""Fill a printable character sheet (flat PDF or PNG) by overlaying text.

A layout is a JSON file next to its template:

    {
      "template": "dcc-standard.pdf",         # relative to the layout file
      "origin": "bottom-left",                 # PDF points (reportlab); "top-left" pixels for PNG
      "font": "Helvetica", "size": 9,
      "fields": {
        "name": {"page": 0, "x": 40, "y": 730, "size": 11},
        "str":  {"page": 0, "x": 52, "y": 560, "align": "center"},
        "notes": {"page": 0, "x": 350, "y": 120, "w": 220, "h": 90, "size": 7, "wrap": true}
      }
    }

Field values come from ``values_for``. Unknown fields are ignored so one
layout can name more than a system provides. Coordinates are read off the
grid rendered by ``scripts/sheet_grid.py``.
"""

from __future__ import annotations

import io
import json
from pathlib import Path


def load_layout(path: Path) -> dict:
    layout = json.loads(Path(path).read_text(encoding="utf-8"))
    layout["_dir"] = Path(path).parent
    layout["_template"] = Path(path).parent / layout["template"]
    return layout


def _wrap(text: str, width_pt: float, size: float, measure) -> list[str]:
    lines = []
    for para in str(text).splitlines() or [""]:
        words, cur = para.split(), ""
        for w in words:
            trial = f"{cur} {w}".strip()
            if measure(trial, size) <= width_pt or not cur:
                cur = trial
            else:
                lines.append(cur); cur = w
        lines.append(cur)
    return lines


def render_pdf(layout: dict, values: dict) -> bytes:
    from pypdf import PdfReader, PdfWriter
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.pdfgen import canvas

    reader = PdfReader(str(layout["_template"]))
    font = layout.get("font", "Helvetica")
    default_size = float(layout.get("size", 9))
    overlays = {}
    for name, spec in layout["fields"].items():
        if name not in values or values[name] in (None, ""):
            continue
        page = int(spec.get("page", 0))
        if page not in overlays:
            box = reader.pages[page].mediabox
            buf = io.BytesIO()
            overlays[page] = (buf, canvas.Canvas(buf, pagesize=(float(box.width), float(box.height))))
        _, c = overlays[page]
        size = float(spec.get("size", default_size))
        c.setFont(spec.get("font", font), size)
        text = str(values[name])
        x, y = float(spec["x"]), float(spec["y"])
        if spec.get("wrap"):
            leading = float(spec.get("leading", size * 1.2))
            lines = _wrap(text, float(spec["w"]), size, lambda t, s: stringWidth(t, font, s))
            max_lines = int(float(spec.get("h", 10_000)) // leading) or 1
            for n, line in enumerate(lines[:max_lines]):
                c.drawString(x, y - n * leading, line)
            continue
        if spec.get("w"):  # shrink to fit a single line
            while size > 4 and stringWidth(text, font, size) > float(spec["w"]):
                size -= 0.5
            c.setFont(spec.get("font", font), size)
        align = spec.get("align", "left")
        if align == "center":
            c.drawCentredString(x, y, text)
        elif align == "right":
            c.drawRightString(x, y, text)
        else:
            c.drawString(x, y, text)
    writer = PdfWriter()
    for i, page in enumerate(reader.pages):
        if i in overlays:
            buf, c = overlays[i]
            c.save(); buf.seek(0)
            page.merge_page(PdfReader(buf).pages[0])
        writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def render_png(layout: dict, values: dict) -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    img = Image.open(layout["_template"]).convert("RGB")
    draw = ImageDraw.Draw(img)
    default_size = int(layout.get("size", 24))
    font_path = layout.get("font_file")
    for name, spec in layout["fields"].items():
        if name not in values or values[name] in (None, ""):
            continue
        size = int(spec.get("size", default_size))
        font = ImageFont.truetype(font_path, size) if font_path else ImageFont.load_default(size)
        text = str(values[name])
        x, y = float(spec["x"]), float(spec["y"])
        measure = lambda t, s: draw.textlength(t, font=font)
        if spec.get("wrap"):
            leading = float(spec.get("leading", size * 1.2))
            for n, line in enumerate(_wrap(text, float(spec["w"]), size, measure)[: int(float(spec.get("h", 1e6)) // leading) or 1]):
                draw.text((x, y + n * leading), line, fill="black", font=font)
            continue
        anchor = {"center": "ma", "right": "ra"}.get(spec.get("align", "left"), "la")
        draw.text((x, y), text, fill="black", font=font, anchor=anchor)
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def render(layout: dict, values: dict) -> tuple[bytes, str]:
    if layout["_template"].suffix.lower() == ".pdf":
        return render_pdf(layout, values), "application/pdf"
    return render_png(layout, values), "image/png"


def list_layouts(directory: Path) -> list[Path]:
    return sorted(Path(directory).glob("*.json")) if Path(directory).exists() else []
