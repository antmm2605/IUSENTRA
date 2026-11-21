"""Lex senza modello: le domande di diritto senza fatti trovano la norma vigente dalla rubrica ufficiale."""
from __future__ import annotations

import pytest

from lex.harness.http import payload_harness
from lex.harness.rubriche import candidati, disposizione, leggibile, rispondi_da_rubrica

DOMANDA = "Entro quale termine deve costituirsi il convenuto nel rito ordinario? Cita la norma."


@pytest.fixture(autouse=True)
def _senza_archivio_vivo(monkeypatch):
    monkeypatch.setenv("LEX_HARNESS_ARCHIVIO_VIVO", "0")
    monkeypatch.setenv("LEX_HARNESS_GIURISPRUDENZA", "0")


def test_costituzione_del_convenuto_nel_rito_ordinario_e_art_166():
    assert [c.citazione for c in candidati(DOMANDA)] == ["art. 166 c.p.c."]
    esito = rispondi_da_rubrica(DOMANDA, "parere")
    assert esito is not None and esito.norme == ["cpc:166"]
    # Testo vigente dopo il d.lgs. 149/2022: settanta giorni prima dell'udienza di comparizione.
    assert "almeno settanta giorni prima dell'udienza di comparizione" in esito.testo
    assert "normattiva.it" in esito.testo and "28/02/2023" in esito.testo
    assert "AGGIORNAMENTO" not in esito.testo


def test_rito_del_lavoro_sceglie_art_416_e_non_166():
    assert [c.citazione for c in candidati("Entro quale termine deve costituirsi il convenuto nel rito del lavoro?")] \
        == ["art. 416 c.p.c."]


def test_rubrica_non_interamente_richiamata_non_vince():
    # «Costituzione dell'attore» non risponde a una domanda sul convenuto.
    assert "art. 165 c.p.c." not in [c.citazione for c in candidati(DOMANDA)]
    assert candidati("Cosa devo fare?") == []


def test_numeri_e_note_di_normattiva():
    assert leggibile("163bis") == "163-bis" and leggibile("473bis12") == "473-bis.12"
    assert disposizione("Art. 1. Testo ((12)). --------------- AGGIORNAMENTO (12) nota") == "Art. 1. Testo."


def test_payload_harness_risponde_senza_modello():
    payload = payload_harness(DOMANDA, risposta_certa=lambda _d: "")
    assert payload is not None
    assert payload["lex_harness"]["rule"] == "norma_per_rubrica"
    assert "art. 166 c.p.c." in payload["answer"]
    assert any("art. 166" in f["title"] for f in payload["sources"])


def test_articolo_fuori_catalogo_letto_dai_testi_dei_codici_senza_archivio_dal_vivo():
    """Collaudo 21/11: la lettura a freddo dell'art. 416 c.p.c. dall'archivio di 5 GB richiedeva 134 s."""
    import time

    inizio = time.monotonic()
    esito = rispondi_da_rubrica("Entro quale termine deve costituirsi il convenuto nel rito del lavoro?", "termine")
    assert time.monotonic() - inizio < 2
    assert esito is not None and esito.norme == ["cpc:416"]
    assert "almeno dieci giorni prima della udienza" in esito.testo
    assert "~art416" in esito.testo


def test_url_normattiva_come_nell_istantanea():
    from lex.harness.rubriche import url_normattiva

    assert url_normattiva("cpc", "473bis12").endswith("1443~art473bis.12")
    assert url_normattiva("cpc", "163bis").endswith("1443~art163bis")
