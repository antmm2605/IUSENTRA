from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors

from pct.pdf_style import PDF_TABLE_HEADER_BACKGROUND, PDF_TABLE_HEADER_TEXT, pdf_table_header_style


def test_pdf_table_header_style_unico_chiaro() -> None:
    commands = pdf_table_header_style()

    assert ("BACKGROUND", (0, 0), (-1, 0), colors.white) in commands
    assert PDF_TABLE_HEADER_BACKGROUND == colors.white
    assert PDF_TABLE_HEADER_TEXT.hexval().lower() == "0x111827"


def test_generatori_pdf_non_reintroducono_header_tabella_scuro() -> None:
    checked = [
        Path("web/blueprints/fatturazione.py"),
        Path("web/blueprints/preventivi.py"),
        Path("web/notifiche.py"),
        Path("web/template_atti.py"),
        Path("pct/reports.py"),
        Path("pct/editor.py"),
        Path("web/services/pdp_penale_runtime.py"),
    ]
    blocked_fragments = [
        '("BACKGROUND", (0, 0), (-1, 0), PRIMARY)',
        '("TEXTCOLOR",  (0, 0), (-1, 0), colors.white)',
        '("BACKGROUND",   (0, 0), (-1, 0), BLU_SCURO)',
        '("TEXTCOLOR",    (0, 0), (-1, 0), BIANCO)',
        '("BACKGROUND",(0, 0), (-1, 0),  colors.HexColor("#f0f0f0"))',
        '("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke)',
    ]

    for path in checked:
        source = path.read_text(encoding="utf-8")
        assert "pdf_table_header_style" in source
        for fragment in blocked_fragments:
            assert fragment not in source


def test_pdf_fatturazione_non_espone_data_utc_visibile() -> None:
    source = Path("web/blueprints/fatturazione.py").read_text(encoding="utf-8")

    assert "Data UTC:" not in source
    assert "Data e ora italiana:" in source
    assert "Data: {p.data_emissione}" not in source
    assert "Scadenza: {p.data_scadenza}" not in source
    assert "pagamento entro il <b>{p.data_scadenza}</b>" not in source
    assert "format_date_it" in source
    assert "format_datetime_it" in source
