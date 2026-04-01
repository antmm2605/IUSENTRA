import tempfile
from pathlib import Path

from pct.editor import html_to_pdf
from pct.template_atti import (
    DEFAULT_EDITOR_LAYOUT,
    GestionePreferenzeTemplateAtti,
    normalizza_editor_layout,
    percorso_preferenze_editor,
)


def test_preferenze_editor_salvano_e_resettano_layout():
    with tempfile.TemporaryDirectory() as tmp:
        prefs_path = Path(tmp) / "template_atti" / "editor_layout.json"
        gestore = GestionePreferenzeTemplateAtti(str(prefs_path))

        custom = gestore.salva(
            {
                "font_family": "inter",
                "font_size_pt": 13,
                "line_height": 1.75,
                "margin_left_mm": 28,
                "paragraph_spacing_pt": 10,
            }
        )

        assert custom["font_family"] == "inter"
        assert custom["font_size_pt"] == 13
        assert gestore.carica()["margin_left_mm"] == 28

        ripristinato = gestore.reset()
        assert ripristinato == normalizza_editor_layout(DEFAULT_EDITOR_LAYOUT)
        assert gestore.carica()["font_family"] == DEFAULT_EDITOR_LAYOUT["font_family"]


def test_percorso_preferenze_editor_riusa_cartella_template():
    db_path = str(Path("D:/tmp/hacs/template_atti/templates.json"))
    prefs_path = Path(percorso_preferenze_editor(db_path))
    assert prefs_path.name == "editor_layout.json"
    assert prefs_path.parent.name == "template_atti"


def test_html_to_pdf_accetta_layout_editor_personalizzato():
    pdf_bytes = html_to_pdf(
        "<h1>Atto di prova</h1><p>Testo formattato per verifica.</p>",
        "Atto di prova",
        layout={
            "font_family": "inter",
            "font_size_pt": 11,
            "line_height": 1.6,
            "text_align": "left",
            "margin_left_mm": 26,
            "margin_right_mm": 18,
            "margin_top_mm": 22,
            "margin_bottom_mm": 20,
            "paragraph_spacing_pt": 6,
        },
    )
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500
