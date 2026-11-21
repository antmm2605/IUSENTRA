"""Codici e leggi: catalogo leggero, compresso e con i titoli decodificati (collaudo 21/11/2026)."""
import gzip
import json

from flask import Flask

from lex.normativa.cerdef_catalogo_salvato import CAMPI_ELENCO, elenco_leggero, voce_elenco
from web.blueprints import api_v1_ricerca_legale as modulo

ATTO = {
    "id": 3000000000004, "key": "cerdef_4", "label": "Codice civile", "category": "Codici", "articles": 3262,
    "title": "Regio decreto 262/1942 — Approvazione del testo del Codice civile. Attivit&agrave; d&#39;impresa",
    "materia": "Civile", "tipo": "Codice", "numero": "262", "data_atto": "1942-03-16", "updated_at": "2026-11-13",
    "urn": "urn:nir:stato:regio.decreto:1942-03-16;262", "xml_entry": "x" * 300, "data_pubblicazione": "1942-04-04",
}


def test_voce_leggera_senza_campi_del_lettore_e_con_entita_decodificate():
    voce = voce_elenco(ATTO)
    assert set(voce) == set(CAMPI_ELENCO)
    assert "Attività d'impresa" in voce["title"] and "&agrave;" not in voce["title"]
    assert "urn" not in voce and "xml_entry" not in voce
    assert ATTO["title"].endswith("d&#39;impresa")  # l'originale non si modifica


def test_catalogo_compresso_una_volta_e_riusato():
    app = Flask(__name__)
    atti = [dict(ATTO, id=ATTO["id"] + n) for n in range(500)]
    chiamate = []

    def costruisci():
        chiamate.append(1)
        return {"ok": True, "items": elenco_leggero(atti)}

    with app.test_request_context(headers={"Accept-Encoding": "gzip, br"}):
        prima = modulo._catalogo_compresso("vigenti", atti, costruisci)
        seconda = modulo._catalogo_compresso("vigenti", atti, costruisci)
    assert len(chiamate) == 1
    assert prima.headers["Content-Encoding"] == "gzip"
    corpo = json.loads(gzip.decompress(seconda.get_data()))
    assert len(corpo["items"]) == 500 and "urn" not in corpo["items"][0]
    assert len(seconda.get_data()) < len(json.dumps(corpo)) / 5
    with app.test_request_context():
        semplice = modulo._catalogo_compresso("vigenti", atti, costruisci)
    assert "Content-Encoding" not in semplice.headers and json.loads(semplice.get_data())["ok"] is True
    nuovi = list(atti)
    with app.test_request_context():
        modulo._catalogo_compresso("vigenti", nuovi, costruisci)
    assert len(chiamate) == 2  # catalogo nuovo, risposta nuova


def test_vista_sconosciuta_non_entra_nella_cache():
    import pytest

    app = Flask(__name__)
    with app.test_request_context():
        with pytest.raises(ValueError):
            modulo._catalogo_compresso("vista-inventata-" + "x" * 50, [], lambda: {"ok": True})
    assert set(modulo._CATALOGHI_COMPRESSI) <= modulo._CHIAVI_CATALOGO


def test_il_log_del_tempo_massimo_non_contiene_i_termini_cercati(caplog):
    from lex.tempo_ricerca import RicercaTroppoLunga

    app = Flask(__name__)
    with app.test_request_context("/normativa/articoli?q=Mario+Rossi+risarcimento&article=2043"):
        with caplog.at_level("WARNING"):
            risposta, stato = modulo._ricerca_troppo_lunga(RicercaTroppoLunga(20))
    assert stato == 503
    testo = caplog.text
    assert "Mario" not in testo and "Rossi" not in testo and "2043" not in testo
    assert "article,q" in testo
