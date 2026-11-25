"""Verifiche dei collegamenti e dei ripieghi dei motori Lex, senza rete."""

from __future__ import annotations

import io
from importlib import import_module
import json
import re

from lex.conoscenza.citazioni import modello_citazione
from lex.harness import giurisprudenza, http, norme, registro_norme, scrittura
from lex.harness.comprensione import comprendi
from lex.harness.fatti import leggi_fatti
from lex.harness.fattispecie import amministrativo
from lex.strumenti import normalizzazione


def test_norma_dal_catalogo_locale_mantiene_ancora_data_e_provenienza(tmp_path, monkeypatch):
    from web.services import ricerca_legale_norma_citata as ricerca

    chiave = "cpc:416"
    percorso = tmp_path / "biblioteca.sqlite"
    url = "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1940-10-28;1443~art416"
    testo = "Il convenuto si costituisce almeno dieci giorni prima della udienza."
    scheda = {
        "normaCitata": True,
        "officialContext": testo,
        "sourceHref": url,
        "title": "Costituzione del convenuto",
        "approvalTone": "success",
        "operationalChecks": ["Testo acquisito con aggiornamento del 25/11/2026"],
    }

    def lettura(percorso_richiesto, estremi):
        assert percorso_richiesto == percorso and estremi
        return scheda

    monkeypatch.setenv("PCT_NORMATTIVA_DB", str(percorso))
    monkeypatch.setenv("LEX_HARNESS_ARCHIVIO_VIVO", "1")
    monkeypatch.setattr(norme, "_istantanea", dict)
    monkeypatch.setattr(norme, "_CACHE_VIVO", {})
    monkeypatch.setattr(ricerca, "norma_citata", lettura)

    norma = norme.testo_norma(chiave)
    assert norma and norma.vigente and norma.url == url and norma.aggiornamento == "25/11/2026"
    assert norma.origine == "archivio dal vivo" and norma.testo == testo
    assert norme.comma_con(chiave, "almeno dieci giorni") == testo
    assert norme.comma_con(chiave, "almeno dieci giorni", massimo=24).endswith("…")
    assert norme.comma_con(chiave, "una frase assente") == ""
    assert norme.comma_con("articolo ignoto", "testo") == ""


def test_archivi_giurisprudenziali_indipendenti(monkeypatch):
    cassazione = object()
    nativo = object()
    monkeypatch.setattr("pct.sentenzeweb_corpus.configured_corpus", lambda: cassazione)
    monkeypatch.setattr("web.helpers.get_giurisprudenza_corpus_readonly", lambda: nativo)
    assert [corpus for _, corpus in giurisprudenza.archivi()] == [cassazione, nativo]

    def indisponibile():
        raise OSError("Indice in manutenzione")

    monkeypatch.setattr("pct.sentenzeweb_corpus.configured_corpus", indisponibile)
    assert [corpus for _, corpus in giurisprudenza.archivi()] == [nativo]


def test_stesura_ollama_usa_il_modello_locale_configurato(monkeypatch):
    url = "http://127.0.0.1:11434"
    monkeypatch.setenv("OLLAMA_URL", url)

    def rispondi(richiesta, timeout):
        dati = json.loads(richiesta.data)
        assert richiesta.full_url == url + "/api/chat"
        assert dati["model"] == "iusentra-lex:9b" and dati["stream"] is False
        assert dati["messages"][-1]["content"] == "Riformula il passaggio verificato"
        assert timeout == 3
        return io.BytesIO(json.dumps({"message": {"content": "Passaggio riformulato"}}).encode())

    monkeypatch.setattr(scrittura.urllib.request, "urlopen", rispondi)
    assert scrittura._chiama("ollama:iusentra-lex:9b", "Riformula il passaggio verificato", 3) == "Passaggio riformulato"


def test_registro_procedurale_segnala_estratto_assente(monkeypatch):
    fonti = import_module("pct.procedura_fasi.fonti")

    norma = norme.testo_norma("cpc:416")
    assert norma and norma.url
    frase = "Estratto di prova che non compare nel testo vigente."
    monkeypatch.setattr(fonti, "FONTI", {"convenuto": {"url": norma.url, "estratto": frase}})
    esito = registro_norme.estratti_non_letterali()
    assert esito == [{"id": "convenuto", "norma": "cpc:416", "assenti": [frase.rstrip(".")]}]


def test_silenzio_amministrativo_chiede_le_date_necessarie():
    domanda = "Per il silenzio della pubblica amministrazione sulla mia istanza, posso presentare ricorso al TAR?"
    comprensione = comprendi(domanda)
    fatti = leggi_fatti(domanda)
    assert amministrativo.riconosci_silenzio(comprensione, fatti) > 0
    esito = amministrativo.analizza_silenzio(comprensione, fatti)
    assert esito.regola == "silenzio"
    assert any("data dell'istanza" in dato for dato in esito.dati_mancanti)
    assert {r.chiave for punto in esito.conclusione for r in punto.rif} == {"cpa:31", "cpa:117"}


def test_lessico_non_disponibile_non_altera_le_richieste(monkeypatch):
    from legal_ocr.lessico import italiano

    def indisponibile(*args):
        raise OSError("Dizionario non disponibile")

    monkeypatch.setattr(italiano, "conosce", indisponibile)
    monkeypatch.setattr(italiano, "vocabolario_completo", indisponibile)
    normalizzazione._corretta.cache_clear()
    try:
        richiesta = "Ho saltato la scadenza della quarta PEC"
        assert normalizzazione.correggi_refusi(richiesta) == richiesta
    finally:
        normalizzazione._corretta.cache_clear()


def test_harness_non_inventa_esito_se_manca_la_comprensione(monkeypatch):
    def indisponibile(_):
        raise ValueError("Richiesta non interpretabile")

    monkeypatch.setattr(http, "comprendi", indisponibile)
    assert http.payload_harness("Che termine si applica?") is None


def test_citazione_distingue_i_codici_e_richiede_l_atto():
    pattern = modello_citazione("art. 416 c.p.c.")
    assert pattern and re.search(pattern, "articolo 416 del codice di procedura civile", re.I)
    assert not re.search(pattern, "articolo 416 del codice penale", re.I)
    assert modello_citazione("art. 416") is None
