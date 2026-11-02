"""Prestazioni delle pagine lente rilevate nella verifica visiva (registro PER).

FAS-01: la vista «Economica» dell'elenco fascicoli legge solo dati consolidati.
FAS-13: la modifica del fascicolo non scarica l'intero registro degli uffici.
ADM-29: cabina telematica e pagina database non rifanno il lavoro a ogni apertura.
"""
from __future__ import annotations

import time

from pct.fascicoli import Documento, TipoDocumento, TipoFascicolo
from tests.test_applicazioni import _crea_operatore, _login
from tests.test_react_shell import _app
from web.blueprints import api_v1_react
from web.helpers import get_fascicoli
from web.services import react_fascicoli_bridge

HEADERS = {"X-API-Key": "react-test-key"}


def _seed_con_documenti(app, totale: int = 30, documenti: int = 25) -> list[str]:
    ids = []
    with app.app_context():
        gf = get_fascicoli()
        for indice in range(totale):
            creato = gf.nuovo(
                f"Pratica economica {indice:02d}",
                TipoFascicolo.CIVILE,
                nome_cliente=f"Cliente {indice:02d}",
                tribunale="Tribunale di Milano",
                numero_rg=str(2000 + indice),
                anno_rg=2026,
            )
            fascicolo = gf.get(creato.id)
            for numero in range(documenti):
                fascicolo.documenti.append(Documento(
                    id=f"{creato.id}-d{numero}",
                    nome=f"atto_{numero}.pdf",
                    tipo=TipoDocumento.ATTO_GIUDIZIARIO,
                    percorso=f"{creato.id}/atto_{numero}.pdf",
                    dimensione_bytes=1000 + numero,
                    hash_sha256=f"{indice:04d}{numero:060d}",
                    note="Ricevuta contributo unificato",
                ))
            ids.append(creato.id)
        gf._salva()
    return ids


def _vietato(nome):
    def _fallisce(*_args, **_kwargs):
        raise AssertionError(f"La vista economica dell'elenco non deve chiamare {nome}.")
    return _fallisce


def test_fas01_vista_economica_non_legge_documenti_ne_automazioni(tmp_path, monkeypatch):
    app = _app(tmp_path)
    _seed_con_documenti(app, totale=30, documenti=25)
    api_v1_react._clear_fascicoli_list_payload_cache()
    for nome in (
        "payment_summary_for_fascicolo",
        "_document_analysis_fingerprint",
        "_document_analysis_state",
        "_server_document_ai_documents_for_fascicolo",
        "_economic_analysis_documents_for_fascicolo",
        "_automatic_payment_sources_for_fascicolo",
    ):
        monkeypatch.setattr(react_fascicoli_bridge, nome, _vietato(nome))

    with app.test_client() as client:
        risposta = client.get("/api/v1/ui/fascicoli?page=1&page_size=25&sort=recenti&view=economica", headers=HEADERS)

    payload = risposta.get_json()
    assert risposta.status_code == 200
    assert len(payload["items"]) == 25
    for riga in payload["items"]:
        analisi = riga["paymentSummary"]["analysis"]
        # Senza consolidamento del presidio la riga lo dichiara, non lo rifa'.
        assert analisi["status"] in {"da_analizzare", "da_rianalizzare", "aggiornato", "aggiornato_con_rilievi"}
        assert riga["paymentSummary"]["items"]["contributo_unificato"]["kind"] == "contributo_unificato"


def test_fas01_scadenza_dall_archivio_solo_per_righe_con_documenti(tmp_path, monkeypatch):
    app = _app(tmp_path)
    con_documenti = set(_seed_con_documenti(app, totale=3, documenti=2))
    with app.app_context():
        get_fascicoli().nuovo("Pratica senza documenti", TipoFascicolo.CIVILE, nome_cliente="Cliente vuoto",
                              tribunale="Tribunale di Milano", numero_rg="5", anno_rg=2026)
    api_v1_react._clear_fascicoli_list_payload_cache()
    interrogati = []
    originale = react_fascicoli_bridge._automatic_next_deadline_from_documents

    def registra(fascicolo):
        interrogati.append(fascicolo.id)
        return originale(fascicolo)

    monkeypatch.setattr(react_fascicoli_bridge, "_automatic_next_deadline_from_documents", registra)
    with app.test_client() as client:
        risposta = client.get("/api/v1/ui/fascicoli?page=1&page_size=25&sort=recenti&view=economica", headers=HEADERS)
    assert risposta.status_code == 200
    # L'archivio delle letture (SQL) si consulta solo dove ci sono documenti.
    assert set(interrogati) == con_documenti


def test_fas01_tempo_vista_economica_sotto_soglia(tmp_path):
    app = _app(tmp_path)
    _seed_con_documenti(app, totale=40, documenti=40)
    api_v1_react._clear_fascicoli_list_payload_cache()
    with app.test_client() as client:
        inizio = time.perf_counter()
        risposta = client.get("/api/v1/ui/fascicoli?page=1&page_size=25&sort=recenti&view=economica", headers=HEADERS)
        durata = time.perf_counter() - inizio
    assert risposta.status_code == 200
    assert durata < 3.0, f"Vista economica in {durata:.2f} s (soglia 3 s)"


def test_fas13_modifica_fascicolo_porta_solo_l_ufficio_scelto(tmp_path):
    app = _app(tmp_path)
    with app.app_context():
        creato = get_fascicoli().nuovo(
            "Pratica da modificare", TipoFascicolo.CIVILE, nome_cliente="Cliente modifica",
            tribunale="Tribunale di Milano", numero_rg="77", anno_rg=2026,
        )
    with app.test_client() as client:
        risposta = client.get(f"/api/v1/ui/fascicoli/{creato.id}/modifica", headers=HEADERS)
    payload = risposta.get_json()
    assert risposta.status_code == 200
    assert [ufficio["value"] for ufficio in payload["judicialOffices"]] == ["Tribunale di Milano"]
    assert payload["judicialOffices"][0]["pec"]
    assert payload["judicialOfficesSearch"] == "/api/v1/ui/uffici-giudiziari/opzioni"
    # Il registro intero pesava ~414 KB: ora l'ufficio scelto occupa meno di 1 KB.
    assert len(risposta.get_data()) < 60_000


def test_fas13_ricerca_uffici_restituisce_le_voci_del_form(tmp_path):
    app = _app(tmp_path)
    with app.test_client() as client:
        risposta = client.get("/api/v1/ui/uffici-giudiziari/opzioni?q=tribunale%20milano", headers=HEADERS)
        vuota = client.get("/api/v1/ui/uffici-giudiziari/opzioni?q=", headers=HEADERS)
        limitata = client.get("/api/v1/ui/uffici-giudiziari/opzioni?q=di&limit=500", headers=HEADERS)
    voci = risposta.get_json()["items"]
    assert risposta.status_code == 200
    assert "Tribunale di Milano" in [voce["value"] for voce in voci]
    voce = next(voce for voce in voci if voce["value"] == "Tribunale di Milano")
    assert set(voce) >= {"value", "label", "code", "ministerialCode", "district", "pec", "kind"}
    assert vuota.get_json()["items"] == []
    assert len(limitata.get_json()["items"]) == 60


def test_fas13_ricerca_uffici_richiede_accesso(tmp_path):
    app = _app(tmp_path)
    with app.test_client() as client:
        risposta = client.get("/api/v1/ui/uffici-giudiziari/opzioni?q=milano")
    assert risposta.status_code in {401, 403}


def _conta_chiamate(monkeypatch, modulo, nome):
    contatore = {"n": 0}
    originale = getattr(modulo, nome)

    def contato(*args, **kwargs):
        contatore["n"] += 1
        return originale(*args, **kwargs)

    monkeypatch.setattr(modulo, nome, contato)
    return contatore


def test_adm29_telematico_senza_utente_non_riusa(tmp_path):
    app = _app(tmp_path)
    api_v1_react._TELEMATICO_PAYLOAD_CACHE.clear()
    with app.test_client() as client:
        client.get("/api/v1/ui/telematico", headers=HEADERS)
        seconda = client.get("/api/v1/ui/telematico", headers=HEADERS)
    # Chiave d'accesso tecnica: nessun contesto utente, nessun riuso.
    assert seconda.headers["X-IUSENTRA-Cache"] == "MISS"


def test_adm29_telematico_riusa_solo_costruzioni_riuscite_e_invalida_sui_cambi(tmp_path, monkeypatch):
    app = _app(tmp_path)
    api_v1_react._TELEMATICO_PAYLOAD_CACHE.clear()
    costruzioni = _conta_chiamate(monkeypatch, api_v1_react, "build_react_telematico_payload")
    _crea_operatore(app)
    with app.test_client() as client:
        _login(client)
        prima = client.get("/api/v1/ui/telematico")
        seconda = client.get("/api/v1/ui/telematico")
        assert prima.status_code == seconda.status_code == 200
        assert prima.headers["X-IUSENTRA-Cache"] == "MISS"
        assert seconda.headers["X-IUSENTRA-Cache"] == "HIT"
        assert seconda.get_data() == prima.get_data()
        assert costruzioni["n"] == 1
        # Un nuovo fascicolo cambia la revisione: la cabina si ricostruisce.
        with app.app_context():
            get_fascicoli().nuovo("Pratica nuova", TipoFascicolo.CIVILE, nome_cliente="Cliente nuovo",
                                  tribunale="Tribunale di Milano", numero_rg="9", anno_rg=2026)
        terza = client.get("/api/v1/ui/telematico")
        assert terza.headers["X-IUSENTRA-Cache"] == "MISS"
        assert costruzioni["n"] == 2
    api_v1_react._TELEMATICO_PAYLOAD_CACHE.clear()


def test_adm29_telematico_con_sorgente_in_errore_non_resta_in_cache(tmp_path, monkeypatch):
    app = _app(tmp_path)
    api_v1_react._TELEMATICO_PAYLOAD_CACHE.clear()

    def guasto():
        raise RuntimeError("archivio non leggibile")

    monkeypatch.setattr(api_v1_react, "get_legal_intelligence", guasto)
    _crea_operatore(app)
    with app.test_client() as client:
        _login(client)
        prima = client.get("/api/v1/ui/telematico")
        seconda = client.get("/api/v1/ui/telematico")
    assert prima.status_code == seconda.status_code == 200
    assert seconda.headers["X-IUSENTRA-Cache"] == "MISS"
    assert len(api_v1_react._TELEMATICO_PAYLOAD_CACHE) == 0


def test_adm29_statistiche_database_ricalcolate_solo_se_i_file_cambiano(tmp_path, monkeypatch):
    import sqlite3

    from web.services import admin_database_statistics_cache as cache

    db_path = tmp_path / "studio.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE fascicoli (id TEXT)")
        conn.execute("INSERT INTO fascicoli VALUES ('a')")
    audit_path = tmp_path / "audit.json"
    audit_path.write_text('[{"azione": "login", "username": "avv", "timestamp": "2026-11-02T10:00:00"}]', encoding="utf-8")

    class Database:
        percorsi = {"audit": str(audit_path)}
        conteggi = {"sqlite": 0, "uso": 0}

        def statistiche_sqlite(self, path):
            self.conteggi["sqlite"] += 1
            with sqlite3.connect(path) as conn:
                return {"esiste": True, "tabelle": {"fascicoli": conn.execute("SELECT COUNT(*) FROM fascicoli").fetchone()[0]}}

        def analisi_uso(self):
            self.conteggi["uso"] += 1
            return {"disponibile": True, "totale_eventi": 1}

    database = Database()
    cache._cache.clear()
    assert cache.sqlite_statistics(database, str(db_path))["tabelle"]["fascicoli"] == 1
    assert cache.sqlite_statistics(database, str(db_path))["tabelle"]["fascicoli"] == 1
    assert cache.usage_statistics(database)["totale_eventi"] == 1
    assert cache.usage_statistics(database)["totale_eventi"] == 1
    assert database.conteggi == {"sqlite": 1, "uso": 1}
    with sqlite3.connect(db_path) as conn:
        conn.execute("INSERT INTO fascicoli VALUES ('b')")
    assert cache.sqlite_statistics(database, str(db_path))["tabelle"]["fascicoli"] == 2
    audit_path.write_text("[]", encoding="utf-8")
    cache.usage_statistics(database)
    assert database.conteggi == {"sqlite": 2, "uso": 2}
    cache._cache.clear()
