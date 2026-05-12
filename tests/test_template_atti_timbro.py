from pathlib import Path

from pct.studio_timbro import StudioTimbro
from pct.compilatore_atti import render_compiled_act


def test_timbro_layout_strict_top_left_non_centrato():
    timbro = StudioTimbro.from_payload(
        {
            "studio_nome": "Studio Legale Test",
            "professionista_nome": "Avv. Test",
            "pec": "studio@example.test",
            "layout_posizione": "top_center",
            "layout_allineamento": "center",
        }
    )

    payload = timbro.to_payload()
    assert payload["layout_posizione"] == "top_left"
    assert payload["layout_allineamento"] == "left"
    assert all(line["align"] == "left" for line in timbro.to_lines())
    assert "text-align: left" in timbro.to_html()
    assert "text-align: center" not in timbro.to_html()
    assert timbro.to_docx_header()["position"] == "top_left"
    assert timbro.to_docx_header()["alignment"] == "left"


def test_timbro_inserito_prima_del_titolo_atto_e_senza_dati_hardcoded():
    timbro = StudioTimbro.from_payload({"studio_nome": "Studio Dinamico", "professionista_nome": "Avv. Dinamico"})
    rendered = render_compiled_act(
        "CIV_CIT_001",
        {
            "_studio_timbro": timbro.to_payload(),
            "recipient_or_court": "Tribunale di Test",
            "client_or_sender": "Cliente Test",
            "counterparty_or_recipient": "Controparte Test",
            "lawyer": "Avv. Dinamico",
            "subject": "Domanda di test",
            "facts": "Fatti di test",
            "requests_or_conclusions": "Conclusioni di test",
            "document_date": "2026-05-12",
        },
    )

    assert rendered.splitlines()[0] == "STUDIO DINAMICO"
    assert rendered.index("STUDIO DINAMICO") < rendered.index("TRIBUNALE DI TEST")
    searched = [
        path
        for root in ("pct", "web", "frontend/src", "scripts")
        for path in Path(root).rglob("*")
        if path.is_file() and path.suffix in {".py", ".ts", ".tsx", ".html", ".css", ".md"}
    ]
    assert not any("Montagnese" in path.read_text(encoding="utf-8", errors="ignore") for path in searched)
