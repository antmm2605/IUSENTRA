"""Regressione dei tempi della ricerca legale (LEX-01).

Profilazione sul server del 03/11/2026: «Cassazione prescrizione» 182 s, di cui 159 s nella ricerca in cache
dell'allegato ufficiale, che scandiva ricorsivamente anche la cartella degli studi; il vettore della domanda
calcolato due volte (archivio generale e biblioteca, ~4 s ciascuno); 8-10 s di riepiloghi che non dipendono
dalla domanda ricalcolati a ogni ricerca.
"""

from __future__ import annotations

import time

import numpy as np

from lex.ricerca_giuridica import embedding as emb
from pct import legal_update_web_verification as verification
from web.services import react_legal_intelligence_bridge as bridge
from tests.test_react_legal_intelligence_search import _Manager, _Pipeline, _Repository, _Rows

URL = "https://www.cortedicassazione.it/resources/cms/documents/Nota_Spoglio_RG_1_2026.pdf"


def test_cache_allegati_non_scandisce_le_cartelle_degli_studi(tmp_path, monkeypatch):
    # Dimensione realistica: migliaia di documenti dello studio sotto tenants/.
    studio = tmp_path / "tenants" / "studio" / "fascicoli"
    for cartella in range(40):
        sotto = studio / f"f{cartella}"
        sotto.mkdir(parents=True)
        for numero in range(100):
            (sotto / f"doc{numero}.pdf").write_bytes(b"x")
    (studio / "f0" / "Nota_Spoglio_RG_1_2026.pdf").write_bytes(b"%PDF-1.7 documento dello studio")
    ufficiali = tmp_path / "fonti_ufficiali" / "raw" / "cassazione"
    ufficiali.mkdir(parents=True)
    (ufficiali / "Nota_Spoglio_RG_1_2026.pdf").write_bytes(b"%PDF-1.7 fonte ufficiale")
    monkeypatch.delenv("IUSENTRA_LEGAL_VERIFICATION_DOWNLOAD_CACHE_DIR", raising=False)
    monkeypatch.delenv("IUSENTRA_LEGAL_DOWNLOAD_CACHE_DIR", raising=False)
    monkeypatch.setenv("PCT_DATA_ROOT", str(tmp_path))

    visitate = []
    originale = type(tmp_path).rglob

    def rglob_spia(self, pattern, *args, **kwargs):
        visitate.append(self.name)
        return originale(self, pattern, *args, **kwargs)

    monkeypatch.setattr(type(tmp_path), "rglob", rglob_spia)
    inizio = time.perf_counter()
    contenuto, _tipo = verification._load_cached_download(URL, max_bytes=1024 * 1024)
    durata = time.perf_counter() - inizio

    assert contenuto == b"%PDF-1.7 fonte ufficiale"
    assert "tenants" not in visitate
    assert durata < 1.0


def test_cache_allegati_percorso_diretto_senza_scansione(tmp_path, monkeypatch):
    diretto = tmp_path / "downloads" / "cassazione"
    diretto.mkdir(parents=True)
    (diretto / "Nota_Spoglio_RG_1_2026.pdf").write_bytes(b"%PDF diretto")
    monkeypatch.setenv("IUSENTRA_LEGAL_VERIFICATION_DOWNLOAD_CACHE_DIR", str(tmp_path / "downloads"))
    monkeypatch.delenv("PCT_DATA_ROOT", raising=False)

    def vietata(self, *args, **kwargs):
        raise AssertionError("con il file nel percorso diretto non serve scandire")

    monkeypatch.setattr(type(tmp_path), "rglob", vietata)
    assert verification._load_cached_download(URL, max_bytes=1024)[0] == b"%PDF diretto"


class _EmbedderLento:
    modello = "modello-prova-lex01"
    dimensioni = 4

    def __init__(self):
        self.chiamate = 0

    def embed(self, testi):
        self.chiamate += 1
        return np.ones((len(testi), 4), dtype=np.float32)


def test_vettore_domanda_calcolato_una_volta_per_i_due_archivi():
    embedder = _EmbedderLento()
    generale, biblioteca = emb.EmbedderDomande(embedder), emb.EmbedderDomande(embedder)
    domanda = "Cassazione prescrizione LEX-01"
    assert generale.vettore(domanda).shape == (4,)
    assert biblioteca.vettore(domanda).shape == (4,)
    assert embedder.chiamate == 1


def _payload(conteggio, scope, q):
    def fascicoli():
        conteggio["fascicoli"] += 1
        return _Rows()

    return bridge.build_react_legal_intelligence_payload(
        get_legal_intelligence=lambda: _Manager(),
        get_legal_update_pipeline=lambda: _Pipeline(_Repository()),
        get_fascicoli=fascicoli,
        get_clienti=lambda: _Rows(),
        get_agenda=lambda: _Rows(),
        get_scadenziario=lambda: _Rows(),
        page="ricerca-legale",
        query={"q": q},
        config={},
        base_cache_scope=scope,
    )


def test_riepiloghi_indipendenti_dalla_domanda_riusati_fra_ricerche(monkeypatch):
    monkeypatch.setattr(bridge, "_public_search_records", lambda q, w: ([], False))
    monkeypatch.setattr(bridge, "_official_archive_records", lambda w, q: [])
    bridge._BASE_CACHE.clear()
    conteggio = {"fascicoli": 0}
    scope = ("ricerca-legale", "studio-prova", "ctx", (("normativa", 1),))
    primo = _payload(conteggio, scope, "mediazione obbligatoria")
    secondo = _payload(conteggio, scope, "usura bancaria tasso soglia")
    assert conteggio["fascicoli"] == 1
    assert [m["id"] for m in primo["metrics"]] == [m["id"] for m in secondo["metrics"]]
    # Senza chiave (revisione non leggibile) si ricalcola sempre.
    _payload(conteggio, None, "mediazione obbligatoria")
    _payload(conteggio, ("altro-studio",), "mediazione obbligatoria")
    assert conteggio["fascicoli"] == 3
    bridge._BASE_CACHE.clear()
