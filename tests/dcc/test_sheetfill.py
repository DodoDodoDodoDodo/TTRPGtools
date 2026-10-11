"""Overlay renderer test on a generated blank template (no private assets needed)."""
import io, json

import pytest

pytest.importorskip("reportlab"); pytest.importorskip("pypdf")

from ttrpgtools.dcc import sheetfill


def test_render_pdf_overlays_fields(tmp_path):
    from reportlab.pdfgen import canvas
    from pypdf import PdfReader
    template = tmp_path / "blank.pdf"
    c = canvas.Canvas(str(template), pagesize=(200, 100)); c.drawString(10, 80, "template"); c.showPage(); c.showPage(); c.save()
    layout_path = tmp_path / "blank.json"
    layout_path.write_text(json.dumps({"template": "blank.pdf", "fields": {
        "name": {"page": 0, "x": 10, "y": 50, "w": 60},
        "notes": {"page": 1, "x": 10, "y": 90, "w": 100, "h": 30, "size": 6, "wrap": True},
        "unused": {"page": 0, "x": 0, "y": 0}}}))
    data, mime = sheetfill.render(sheetfill.load_layout(layout_path), {"name": "A very long character name that must shrink", "notes": "word " * 40, "extra": "ignored"})
    assert mime == "application/pdf" and data.startswith(b"%PDF")
    reader = PdfReader(io.BytesIO(data))
    assert len(reader.pages) == 2
    assert "character name" in reader.pages[0].extract_text() and "word" in reader.pages[1].extract_text()


def test_wrap_respects_width():
    lines = sheetfill._wrap("alpha beta gamma delta", 30, 10, lambda t, s: len(t) * 5)
    assert lines == ["alpha", "beta", "gamma", "delta"]
