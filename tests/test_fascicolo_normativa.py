"""Icona «Normativa» del fascicolo (richiesta dell'avvocato del 02/11/2026).

Dominio: raggruppamento (procedura, termini aperti, documenti), motivi e fonti
ufficiali senza testi inventati. API: autenticazione, permesso
`fascicoli.leggi`, isolamento fra studi, stato vuoto e testo dall'archivio
Normattiva del server.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from pct.normativa_fascicolo import normativa_del_fascicolo
from pct.normativa_fascicolo.voci import riferimento_archivio
from pct.procedura_fasi.fonti import FONTI

CPC = "urn:nir:stato:regio.decreto:1940-10-28;1443"


def _gruppo(payload, gruppo_id):
    return next(g for g in payload["gruppi"] if g["id"] == gruppo_id)


def _voce(gruppo, norma):
    return next(v for v in gruppo["voci"] if v["norma"] == norma)


def _civile(**extra):
    scadenze = extra.pop("scadenze", [])
    catalogo = extra.pop("catalogo", [])
    nomi = extra.pop("nomi", {})
    fascicolo = {"tipo": "CIVILE", "tipo_procedimento": "Rito ordinario", "tribunale": "Tribunale di Milano", **extra}
    return normativa_del_fascicolo(fascicolo, scadenze=scadenze, catalogo=catalogo, nomi_documenti=nomi)


def test_gruppi_e_procedura_dal_registro_con_fase_e_data():
    payload = _civile()
    assert [g["id"] for g in payload["gruppi"]] == ["procedura", "termini", "documenti"]
    procedura = _gruppo(payload, "procedura")
    voce = _voce(procedura, "art. 171-ter c.p.c.")
    # Rubrica, estratto e URL vengono dal registro, non da testo nuovo.
    assert voce["rubrica"] == FONTI["cpc_171ter"]["titolo"]
    assert voce["estratto"] == FONTI["cpc_171ter"]["estratto"]
    assert voce["url"] == FONTI["cpc_171ter"]["url"]
    assert voce["fonte"] == "Normattiva" and voce["consultataIl"] == "14/09/2026"
    assert any("fase «Memorie integrative»" in motivo for motivo in voce["perche"])
    assert voce["archivio"] == {"urn": CPC, "articolo": "171ter"}
    assert payload["contesto"]["ufficio"] == "Tribunale di Milano"
    assert payload["materie"] == ["Diritto civile", "Procedura civile e ADR"]
    # Ogni voce ha un collegamento ufficiale https.
    assert all(v["url"].startswith("https://") for g in payload["gruppi"] for v in g["voci"])


def test_termini_aperti_portano_norma_e_motivo_con_data():
    payload = _civile(scadenze=[
        {"stato": "APERTO", "tipo": "UDIENZA", "titolo": "Udienza cartolare", "data_scadenza": "2026-12-15", "hearing_mode": "note_scritte"},
        {"stato": "APERTO", "tipo": "IMPUGNAZIONE", "titolo": "Termine lungo per l'appello", "data_scadenza": "2027-03-01T00:00:00+01:00",
         "deadline_profile_code": "CIV_APPELLO_LUNGO"},
        {"stato": "COMPLETATO", "titolo": "Costituzione ex art. 165 c.p.c.", "data_scadenza": "2026-01-10"},
    ])
    termini = _gruppo(payload, "termini")
    norme = [v["norma"] for v in termini["voci"]]
    assert norme == ["art. 127-ter c.p.c.", "art. 327 c.p.c."]
    assert _voce(termini, "art. 127-ter c.p.c.")["perche"] == ["perché: udienza al 15/12/2026 — «Udienza cartolare»"]
    assert _voce(termini, "art. 327 c.p.c.")["perche"] == ["perché: termine aperto al 01/03/2027 — «Termine lungo per l'appello»"]
    assert payload["contesto"]["termini"] == 2


def test_citazione_fuori_registro_solo_collegamento_ufficiale():
    payload = _civile(scadenze=[{"stato": "APERTO", "titolo": "Diffida ex art. 1454 c.c.", "data_scadenza": "2026-12-01"}])
    voce = _gruppo(payload, "termini")["voci"][0]
    assert voce["estratto"] == "" and voce["rubrica"] == ""
    assert voce["url"].startswith("https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1942-03-16;262")
    assert voce["url"].endswith("~art1454")
    assert voce["archivio"]["articolo"] == "1454"


def test_documenti_catalogati_portano_la_norma_del_tipo():
    payload = _civile(
        catalogo=[
            {"status": "proposed", "document_id": "d1", "document_label": "Atto di citazione", "document_nature": "citazione", "document_section": "atti"},
            {"status": "review_required", "document_id": "d2", "document_label": "Atto di citazione", "document_nature": "citazione", "document_section": "atti"},
        ],
        nomi={"d1": "citazione.pdf", "d2": "bozza.pdf"},
    )
    documenti = _gruppo(payload, "documenti")
    voce = _voce(documenti, "c.p.c., art. 163")
    assert voce["perche"] == ["perché: documento «citazione.pdf» nel fascicolo (Atto di citazione)"]
    assert voce["url"].endswith("~art163") and voce["estratto"] == ""
    assert payload["contesto"]["catalogati"] == 1


def test_fascicolo_senza_dati_stato_vuoto_spiegato():
    payload = normativa_del_fascicolo({"tipo": "ALTRO"}, scadenze=[], catalogo=[], nomi_documenti={})
    assert payload["totale"] == 0
    assert [bool(g["vuoto"]) for g in payload["gruppi"]] == [True, True, True]
    assert _gruppo(payload, "termini")["vuoto"] == "Nessun termine o udienza aperti nel fascicolo."
    assert _gruppo(payload, "documenti")["vuoto"] == "Nessun documento nel fascicolo."


@pytest.mark.parametrize("tipo,procedimento,assente", [
    ("PENALE", "", "L. 53/1994, art. 3-bis"),
    ("STRAGIUDIZIALE", "Mediazione", "D.M. 44/2011, art. 13"),
])
def test_rito_senza_canali_estranei(tipo, procedimento, assente):
    payload = normativa_del_fascicolo({"tipo": tipo, "tipo_procedimento": procedimento}, scadenze=[], catalogo=[], nomi_documenti={})
    norme = [v["norma"] for v in _gruppo(payload, "procedura")["voci"]]
    assert norme and assente not in norme


def test_riferimento_archivio_solo_da_normattiva():
    assert riferimento_archivio(f"https://www.normattiva.it/uri-res/N2Ls?{CPC}:1~art127ter") == {"urn": CPC, "articolo": "127ter"}
    assert riferimento_archivio("https://pst.giustizia.it/PST/it/download.page") == {}
    assert riferimento_archivio(f"http://www.normattiva.it/uri-res/N2Ls?{CPC}~art1") == {}


# ── API ──────────────────────────────────────────────────────────────────────

def _archivio(tmp_path: Path) -> Path:
    from lex.normativa.normattiva_importer import ensure_schema

    path = tmp_path / "normativa" / "normattiva.sqlite"
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    ensure_schema(conn)
    doc = conn.execute("INSERT INTO normative_documents (collection_name,urn,titolo,vigenza,imported_at) VALUES (?,?,?,?,?)",
                       ("Lex fonti: codice_procedura_civile", CPC, "Codice di procedura civile", "2026-10-01", "2026-10-02T10:00:00")).lastrowid
    conn.execute("INSERT INTO normative_articles (document_id,article_number,article_text) VALUES (?,?,?)",
                 (doc, "127-ter", "Art. 127-ter. Testo di prova del collaudo, non testo di legge."))
    conn.commit()
    conn.close()
    return path


@pytest.fixture()
def app_normativa(tmp_path, monkeypatch):
    from tests.test_react_shell import _app
    from web.services.fascicolo_normativa_runtime import NORMATIVA_CACHE

    NORMATIVA_CACHE.clear()
    archivio = _archivio(tmp_path)
    monkeypatch.setattr("lex.retrieval.normativa_catalog.consultation_path", lambda general=None: archivio)
    yield _app(tmp_path)
    NORMATIVA_CACHE.clear()


def _nuovo_fascicolo(app, **campi):
    from pct.fascicoli import TipoFascicolo
    from tests.test_react_shell import _fascicoli_repository

    gestore = _fascicoli_repository(app)
    fascicolo = gestore.nuovo("Prova normativa", TipoFascicolo.CIVILE)
    if campi:
        gestore.aggiorna(fascicolo.id, **campi)
    return fascicolo


def test_api_richiede_autenticazione(app_normativa):
    fascicolo = _nuovo_fascicolo(app_normativa)
    with app_normativa.test_client() as client:
        assert client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/normativa").status_code == 401
        assert client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/normativa/testo?urn={CPC}&articolo=127ter").status_code == 401


def test_api_senza_permesso_fascicoli_leggi_403(app_normativa):
    from pct.auth import GestioneUtenti, RuoloUtente

    fascicolo = _nuovo_fascicolo(app_normativa)
    with app_normativa.app_context():
        GestioneUtenti(
            db_path=app_normativa.config["AUTH_DB"], audit_path=app_normativa.config["AUDIT_DB"],
            secret_key=app_normativa.secret_key, bootstrap_admin_password=app_normativa.config["BOOTSTRAP_ADMIN_PASSWORD"],
            bootstrap_admin_credentials_path=app_normativa.config["BOOTSTRAP_ADMIN_CREDENTIALS_PATH"],
        ).crea(username="contabile", password="Contabile123!", ruolo=RuoloUtente.CONTABILE,
               permessi_negati=["fascicoli.leggi"], must_change_password=False)
    with app_normativa.test_client() as client:
        client.post("/login", data={"username": "contabile", "password": "Contabile123!"}, follow_redirects=True)
        risposta = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/normativa")
        testo = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/normativa/testo?urn={CPC}&articolo=127ter")
    assert risposta.status_code == 403 and testo.status_code == 403


def test_api_payload_vuoto_e_fascicolo_inesistente(app_normativa):
    fascicolo = _nuovo_fascicolo(app_normativa)
    headers = {"X-API-Key": "react-test-key"}
    with app_normativa.test_client() as client:
        risposta = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/normativa", headers=headers)
        assente = client.get("/api/v1/ui/fascicoli/non-esiste/normativa", headers=headers)
    assert risposta.status_code == 200
    normativa = risposta.get_json()["normativa"]
    assert normativa["fascicolo"]["id"] == fascicolo.id
    assert _gruppo(normativa, "termini")["vuoto"] == "Nessun termine o udienza aperti nel fascicolo."
    assert _gruppo(normativa, "documenti")["vuoto"] == "Nessun documento nel fascicolo."
    assert assente.status_code == 404


def test_api_termine_aperto_e_testo_dall_archivio(app_normativa):
    from pct.scadenziario import TipoTermine
    from web.helpers import get_scadenziario

    fascicolo = _nuovo_fascicolo(app_normativa, tipo_procedimento="Rito ordinario")
    with app_normativa.app_context():
        get_scadenziario().nuova("Udienza a trattazione scritta", TipoTermine.UDIENZA, "2026-12-15",
                                 id_fascicolo=fascicolo.id, hearing_mode="note_scritte")
    headers = {"X-API-Key": "react-test-key"}
    with app_normativa.test_client() as client:
        normativa = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/normativa", headers=headers).get_json()["normativa"]
        testo = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/normativa/testo?urn={CPC}&articolo=127ter", headers=headers)
        mancante = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/normativa/testo?urn={CPC}&articolo=2", headers=headers)
        non_valido = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/normativa/testo?urn=javascript:alert(1)&articolo=1", headers=headers)
    voce = _voce(_gruppo(normativa, "termini"), "art. 127-ter c.p.c.")
    assert voce["perche"] == ["perché: udienza al 15/12/2026 — «Udienza a trattazione scritta»"]
    assert voce["testoInArchivio"] is True
    assert _voce(_gruppo(normativa, "procedura"), "art. 165 c.p.c.")["testoInArchivio"] is False
    assert testo.status_code == 200
    assert testo.get_json()["testo"] == {"testo": "Art. 127-ter. Testo di prova del collaudo, non testo di legge.",
                                         "versione": "2026-10-01", "importatoIl": "02/10/2026", "atto": "Codice di procedura civile"}
    assert mancante.status_code == 404 and non_valido.status_code == 404


def test_api_isolamento_fra_studi(tmp_path, monkeypatch):
    from pct.fascicoli import TipoFascicolo
    from pct.tenant import GestioneTenant
    from tests.test_web_bootstrap import _cfg_web, _write_studio_config
    from web.app import create_app
    from web.services.fascicolo_normativa_runtime import NORMATIVA_CACHE
    from web.services.tenant_legacy_bootstrap import bootstrap_legacy_tenant_runtime_data

    NORMATIVA_CACHE.clear()
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app({**_cfg_web(tmp_path), "MULTI_TENANT": True, "STORAGE_MODE_DEFAULT": "JSON"})
    manager = GestioneTenant(app.config["TENANTS_REGISTRY"])
    studio_a = manager.crea("Studio Normativa A", "studio-normativa-a")
    studio_b = manager.crea("Studio Normativa B", "studio-normativa-b")
    manager.aggiorna(studio_a.slug, api_key="normativa-a-key")
    manager.aggiorna(studio_b.slug, api_key="normativa-b-key")
    bootstrap_legacy_tenant_runtime_data(app, tenant_slug=studio_a.slug)
    bootstrap_legacy_tenant_runtime_data(app, tenant_slug=studio_b.slug)
    # La pratica nasce nello studio B con il repository della richiesta di B (lo stesso archivio letto dall'API).
    with app.test_request_context("/api/v1/ui/fascicoli", headers={"X-API-Key": "normativa-b-key", "X-Tenant-Slug": studio_b.slug}):
        app.preprocess_request()
        fascicolo_b = app.extensions["core_runtime"]["get_fascicoli"]().nuovo("Pratica Studio B", TipoFascicolo.CIVILE)
    with app.test_client() as client:
        altro_studio = client.get(f"/api/v1/ui/fascicoli/{fascicolo_b.id}/normativa",
                                  headers={"X-API-Key": "normativa-a-key", "X-Tenant-Slug": studio_a.slug})
        stesso_studio = client.get(f"/api/v1/ui/fascicoli/{fascicolo_b.id}/normativa",
                                   headers={"X-API-Key": "normativa-b-key", "X-Tenant-Slug": studio_b.slug})
        # La cache non attraversa gli studi: dopo la lettura di B, A continua a non vederlo.
        di_nuovo = client.get(f"/api/v1/ui/fascicoli/{fascicolo_b.id}/normativa",
                              headers={"X-API-Key": "normativa-a-key", "X-Tenant-Slug": studio_a.slug})
    NORMATIVA_CACHE.clear()
    assert altro_studio.status_code == 404
    assert stesso_studio.status_code == 200
    assert stesso_studio.get_json()["normativa"]["fascicolo"]["id"] == fascicolo_b.id
    assert di_nuovo.status_code == 404


def test_ricerca_limitata_alle_materie_della_pratica(tmp_path):
    from lex.normativa.consultazione import articoli
    from lex.normativa.normattiva_importer import ensure_schema
    from lex.ricerca_giuridica.indice_fts import assicura_schema_fts
    from lex.ricerca_giuridica.testo import testo_indice

    path = tmp_path / "biblioteca.sqlite"
    conn = sqlite3.connect(path)
    ensure_schema(conn)
    assicura_schema_fts(conn)
    for chiave, urn, titolo in (("codice_procedura_civile", CPC, "Codice di procedura civile"),
                                ("codice_penale", "urn:nir:stato:regio.decreto:1930-10-19;1398", "Codice penale")):
        doc = conn.execute("INSERT INTO normative_documents (collection_name,urn,titolo,redazione_id) VALUES (?,?,?,?)",
                           ("Lex fonti: " + chiave, urn, titolo, "2026-10-01")).lastrowid
        art = conn.execute("INSERT INTO normative_articles (document_id,article_number,article_title,article_text) VALUES (?,?,?,?)",
                           (doc, "1", "Termine", "Il termine decorre.")).lastrowid
        chunk = conn.execute("INSERT INTO normative_chunks (document_id,article_id,chunk_key,chunk_text,metadata_json) VALUES (?,?,?,?,?)",
                             (doc, art, f"{chiave}:1", "Il termine decorre.", "{}")).lastrowid
        conn.execute("INSERT INTO normative_fts (rowid,titolo,testo) VALUES (?,?,?)", (chunk, "Termine", testo_indice("Il termine decorre.")))
    conn.commit()
    conn.close()
    tutti = articoli(path, query="termine")
    civili = articoli(path, query="termine", materie=("Procedura civile e ADR",))
    assert tutti["total"] == 2
    assert [r["act_title"] for r in civili["items"]] == ["Codice di procedura civile"]


def test_controllo_archivio_oltre_il_tempo_resta_da_verificare(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import web.services.fascicolo_normativa_runtime as runtime

    archivio = _archivio(tmp_path)
    monkeypatch.setattr(runtime, "_catalogo", lambda fascicolo: [])
    fascicolo = SimpleNamespace(id="F1", titolo="Prova", tipo="CIVILE", tipo_procedimento="Rito ordinario", documenti=[])
    gestore = SimpleNamespace(get=lambda fid: fascicolo if fid == "F1" else None)
    scadenziario = SimpleNamespace(tutte=lambda **kw: [])

    def costruisci():
        return runtime.build_normativa_payload("F1", carica_fascicolo=lambda: gestore,
                                               scadenziario=lambda: scadenziario, archivio_db=lambda: archivio)

    nel_tempo = _voce(_gruppo(costruisci(), "procedura"), "art. 127-ter c.p.c.")
    monkeypatch.setattr(runtime, "_TEMPO_CONTROLLO_ARCHIVIO", -1.0)
    oltre = costruisci()
    assert nel_tempo["testoInArchivio"] is True
    assert _voce(_gruppo(oltre, "procedura"), "art. 127-ter c.p.c.")["testoInArchivio"] is None
    # Senza URN e articolo (specifiche DGSIA) non c'è nulla da cercare: solo il collegamento.
    assert _voce(_gruppo(oltre, "procedura"), "Specifiche tecniche DGSIA 7/8/2024, art. 17")["testoInArchivio"] is False
    assert runtime.build_normativa_payload("ALTRO", carica_fascicolo=lambda: gestore,
                                           scadenziario=lambda: scadenziario, archivio_db=lambda: archivio) is None
