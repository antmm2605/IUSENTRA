"""Lettore React dei provvedimenti: payload JSON uniformi e pagine Jinja eliminate."""

from __future__ import annotations

from pathlib import Path

from web.services.lettore_sentenze import payload_corpus, payload_sentenzeweb, payload_testo_ufficiale, payload_traduzione

RADICE = Path(__file__).resolve().parents[1]


def test_payload_corpus_e_sentenzeweb():
    corpus = payload_corpus({
        "title": "Curia C-1/26", "authority": "Corte di giustizia", "section": "Prima", "date": "2026-10-14",
        "date_label": "Deposito", "blocks": [{"kind": "heading", "text": "Motivi", "anchor": "sezione-0"},
                                             {"kind": "paragraph", "text": "Testo"}],
        "text_source_official": True, "text_source_url": "https://curia.europa.eu/x", "sha256": "a" * 64,
        "documents": [{"language": "fr"}], "status": "source_notice",
    })
    assert corpus["righe"] == ["Corte di giustizia · Sezione Prima · Deposito 14/10/2026"]
    assert corpus["provenienza"] == "Testo archiviato dalla fonte ufficiale"
    assert corpus["blocchi"][0] == {"tipo": "titolo", "testo": "Motivi", "ancora": "sezione-0"}
    assert any("oscuramento" in avviso for avviso in corpus["avvisi"])
    assert any("Lingua del documento conservato: fr" in avviso for avviso in corpus["avvisi"])
    sentenzeweb = payload_sentenzeweb({"number": "123", "year": 2026, "authority": "Cassazione", "section": "3",
                                       "date": "2026-10-14", "text_source_url": "javascript:alert(1)", "blocks": []})
    assert sentenzeweb["titolo"] == "Cassazione 123/2026"
    assert sentenzeweb["fonteUrl"] == ""


def test_payload_traduzione_e_testo_ufficiale():
    traduzione = payload_traduzione({"titolo": "T", "parti": [{"originale": "a", "traduzione": "b", "avviso": ""}],
                                     "source_language": "de", "avvisi": 2, "originale_url": "https://x.test/"})
    assert traduzione["originaleUrl"] == ""
    assert traduzione["parti"][0]["traduzione"] == "b"
    assert any("2 passaggi" in avviso for avviso in traduzione["avvisi"])
    ufficiale = payload_testo_ufficiale({"testo": "Primo\n\n Secondo ", "raw_sha256": "b" * 64,
                                         "provenienza": {"url": "https://mdp.giustizia-amministrativa.it/x", "versione": "01/01/2023"}})
    assert [blocco["testo"] for blocco in ufficiale["blocchi"]] == ["Primo", "Secondo"]
    assert ufficiale["fonteUrl"].startswith("https://mdp.giustizia-amministrativa.it/")


def test_lettori_jinja_eliminati_e_shell_senza_dati():
    for nome in ("corpus_lettore.html", "traduzione_lettore.html", "sentenzeweb_lettore.html", "testo_ufficiale.html"):
        assert not (RADICE / "web/templates/giurisprudenza" / nome).exists(), nome
    shell = (RADICE / "web/templates/lettore_sentenza_shell.html").read_text(encoding="utf-8")
    assert 'id="lettore-sentenza-root"' in shell and "documento" not in shell
    componente = (RADICE / "frontend/src/components/LettoreSentenzaApp.tsx").read_text(encoding="utf-8")
    assert "dangerouslySetInnerHTML" not in componente and "innerHTML" not in componente


def test_lettore_usa_ingresso_indipendente_con_manifest(monkeypatch, tmp_path):
    import json

    from web.blueprints import react_shell
    from web.services.lettore_sentenze import _asset_lettore

    assets = tmp_path / ".vite"
    assets.mkdir()
    manifest = assets / "manifest.json"
    monkeypatch.setattr(react_shell, "_react_static_dir", lambda: tmp_path)
    app = {"index.html": {"file": "assets/studio.js", "isEntry": True}}
    manifest.write_text(json.dumps(app), encoding="utf-8")
    assert _asset_lettore() == {"ready": False}

    manifest.write_text(json.dumps({
        **app,
        "src/lettoreSentenzaEntry.tsx": {
            "file": "assets/lettore.js", "isEntry": True,
            "imports": ["_react.js"], "css": ["assets/lettore.css"],
        },
        "_react.js": {"file": "assets/react.js"},
    }), encoding="utf-8")
    assert _asset_lettore() == {
        "ready": True,
        "entry": "/static/react/assets/lettore.js",
        "css": ["/static/react/assets/lettore.css"],
        "preload_js": ["/static/react/assets/react.js"],
    }
