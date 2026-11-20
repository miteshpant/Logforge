"""PDF reports keep Unicode text (tenant names, rule titles, case titles in
any script DejaVu covers): when a report has text outside Latin-1, the writer
embeds DejaVu fonts (Identity-H, with a ToUnicode map so text can be copied and
searched). Latin-1 reports keep the small built-in Helvetica path."""
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

import pdf_fonts  # noqa: E402
import reports  # noqa: E402


def report(title):
    now = datetime(2026, 11, 1, tzinfo=timezone.utc)
    return {"title": title, "tenant": title, "period": {"start": "2026-11-01", "end": "2026-11-30", "days": 30},
            "generated_at": now.isoformat(), "sections": [
                {"title": "Alerts", "kind": "table", "columns": ["rule", "count"],
                 "rows": [["Привет мир", 3], ["Zürich", 1]]}]}


def test_the_font_reader_finds_glyphs_and_widths():
    font = pdf_fonts.TrueTypeFont.load("DejaVuSans.ttf")
    assert font.units_per_em == 2048
    a, ya = font.glyph("A"), font.glyph("Я")
    assert a and ya and a != ya
    assert 400 < font.width_1000(a) < 800
    assert font.glyph("\U0001F600") == 0 or isinstance(font.glyph("\U0001F600"), int)


def test_latin1_reports_stay_on_the_builtin_fonts():
    latin = report("Acme")
    latin["sections"][0]["rows"] = [["Zürich", 1]]
    pdf = reports.to_pdf(latin)
    assert b"/Helvetica" in pdf and b"/Type0" not in pdf


def test_unicode_reports_embed_fonts():
    pdf = reports.to_pdf(report("Ωmega Σecurity Ltd"))
    assert b"/Type0" in pdf and b"/Identity-H" in pdf and b"/ToUnicode" in pdf and b"/FontFile2" in pdf


@pytest.mark.skipif(not shutil.which("pdftotext"), reason="pdftotext not installed")
def test_unicode_text_round_trips():
    pdf = reports.to_pdf(report("Ωmega Σecurity Ltd"))
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(pdf)
    try:
        text = subprocess.run(["pdftotext", f.name, "-"], capture_output=True, text=True, check=True).stdout
    finally:
        os.unlink(f.name)
    assert "Ωmega Σecurity Ltd" in text and "Привет мир" in text and "Zürich" in text
