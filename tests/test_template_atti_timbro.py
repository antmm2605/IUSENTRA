from pathlib import Path
from types import SimpleNamespace

from pct.studio_timbro import StudioTimbro, default_timbro_payload
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
    assert timbro.to_docx_header()["repeat_on_each_page"] is True
    assert timbro.to_stamp_placement()["repeat_on_each_page"] is True
    assert timbro.to_stamp_placement()["align_within_box"] == "center"


def test_timbro_non_duplica_citta_gia_presente_nell_indirizzo():
    timbro = StudioTimbro.from_payload(
        {
            "studio_nome": "Studio Legale Montagnese",
            "professionista_nome": "Avv. Roberto Montagnese",
            "indirizzo_riga": "Via NINO BIXIO 4, 89029 - TAURIANOVA (RC)",
            "cap_citta_provincia": "TAURIANOVA (RC)",
        }
    )

    address_lines = [line["text"] for line in timbro.to_lines() if line["source"] == "indirizzo"]
    assert address_lines == ["Via NINO BIXIO 4, 89029 - TAURIANOVA (RC)"]


def test_timbro_usa_solo_qualifica_professionale_e_non_fallback_ordine():
    config_studio = SimpleNamespace(
        studio=SimpleNamespace(
            nome="Studio Test",
            avvocato="Avv. Test",
            qualifica_professionale="",
            ordine_avvocati="Ordine degli Avvocati di Test",
            numero_iscrizione_albo="123",
            indirizzo="Via Roma 1",
            city="Palmi",
            province="RC",
            telefono="",
            cf="",
            piva="",
            email="",
            sito_web="",
        ),
        pec=SimpleNamespace(indirizzo=""),
    )

    payload = default_timbro_payload(config_studio=config_studio)
    timbro = StudioTimbro.from_payload(payload)

    assert payload["qualifiche_professionali"] == ""
    assert all(line["source"] != "qualifiche_professionali" for line in timbro.to_lines())
    assert "Ordine degli Avvocati" not in timbro.to_text()


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


def test_pdf_timbro_usa_callback_prima_e_pagine_successive(monkeypatch):
    from pct.editor import html_to_pdf
    from pct import legal_layout_profiles

    calls = {"pages": 0}

    def fake_callback(stamp, layout_profile=None, layout=None):
        def draw(canvas, doc):
            calls["pages"] += 1

        return draw

    monkeypatch.setattr(legal_layout_profiles, "make_pdf_stamp_callback", fake_callback)
    timbro = StudioTimbro.from_payload({"studio_nome": "Studio Dinamico", "professionista_nome": "Avv. Dinamico"})
    html = "".join(f"<p>Riga {index}: {'contenuto ' * 24}</p>" for index in range(260))

    pdf_bytes = html_to_pdf(html, "Atto multipagina", studio_timbro=timbro)

    assert pdf_bytes.startswith(b"%PDF")
    assert calls["pages"] >= 3
