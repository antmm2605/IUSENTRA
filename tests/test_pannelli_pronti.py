"""Pannelli pronti: contatori di revisione, impronta delle fonti, archivio e risposta dal salvato.

Dati fittizi: un studio.db e un registro delle letture minimi con le tabelle reali che i pannelli leggono.
Ogni scenario modifica una fonte e verifica che l'impronta cambi (il pannello si ricalcola) e che,
a fonti invariate, il payload salvato sia servito senza ricalcolo.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from flask import Flask, g, jsonify

from pct.pannelli_pronti import impronta as impronta_fonti
from pct.pannelli_pronti import revisioni
from pct.pannelli_pronti.archivio import ArchivioPannelli
from pct.pannelli_pronti.preparazione import prepara_database

ROMA = ZoneInfo("Europe/Rome")


def _studio_db(percorso):
    conn = sqlite3.connect(percorso)
    conn.executescript(
        """
        CREATE TABLE fascicoli (id TEXT PRIMARY KEY, dati_json TEXT, modificato_il TEXT);
        CREATE TABLE scadenze (id TEXT PRIMARY KEY, id_fascicolo TEXT, dati_json TEXT);
        CREATE TABLE appuntamenti (id TEXT PRIMARY KEY, id_fascicolo TEXT, dati_json TEXT);
        CREATE TABLE parcelle (id TEXT PRIMARY KEY, id_fascicolo TEXT, dati_json TEXT);
        CREATE TABLE document_catalog_assignments (id TEXT PRIMARY KEY, tenant_id TEXT, fascicolo_id TEXT, etichetta TEXT);
        CREATE TABLE deposit_sessions (id TEXT PRIMARY KEY, fascicolo_id TEXT, stato TEXT);
        CREATE TABLE ctu_incarichi (id TEXT PRIMARY KEY, fascicolo_id TEXT, stato TEXT);
        CREATE TABLE mediazione_procedimenti (id TEXT PRIMARY KEY, fascicolo_id TEXT, stato TEXT);
        CREATE TABLE email_mailbox_records (id TEXT PRIMARY KEY, dati_json TEXT);
        CREATE TABLE clienti (id TEXT PRIMARY KEY, dati_json TEXT);
        CREATE TABLE transactional_outbox (id TEXT PRIMARY KEY, aggregate_id TEXT);
        CREATE TABLE fascicoli_list_rows (tenant_key TEXT, record_key TEXT, fascicolo_id TEXT);
        INSERT INTO fascicoli VALUES ('F1', '{"documenti": []}', '2026-11-10'), ('F2', '{}', '2026-11-10');
        """
    )
    conn.commit()
    conn.close()


def _registro_db(percorso):
    conn = sqlite3.connect(percorso)
    conn.executescript(
        """
        CREATE TABLE letture_fatti (id TEXT PRIMARY KEY, tenant_id TEXT, fascicolo_id TEXT, campo TEXT, valore TEXT, verifica TEXT);
        CREATE TABLE letture_oggetti (id TEXT PRIMARY KEY, tenant_id TEXT, fascicolo_id TEXT, impronta TEXT);
        CREATE TABLE letture_verifiche_esiti (id TEXT PRIMARY KEY, fascicolo_id TEXT, esito TEXT);
        CREATE TABLE letture_viste (id TEXT PRIMARY KEY, fascicolo_id TEXT, utente_id TEXT, visto_il TEXT);
        CREATE TABLE letture_payload_cache (id TEXT PRIMARY KEY, fascicolo_id TEXT, payload TEXT);
        """
    )
    conn.commit()
    conn.close()


@pytest.fixture()
def studio(tmp_path):
    base = tmp_path / "tenants" / "studio-prova"
    (base / "intelligence").mkdir(parents=True)
    studio_db, registro_db = str(base / "studio.db"), str(base / "intelligence" / "registro_letture.db")
    _studio_db(studio_db)
    _registro_db(registro_db)
    config = base / "config.json"
    config.write_text("{}", encoding="utf-8")
    for percorso, tabelle in ((studio_db, ("email_mailbox_records", "clienti")), (registro_db, ())):
        esito = prepara_database(percorso, tabelle_senza_fascicolo=tabelle, backup_dir=tmp_path / "backup", applica=True)
        assert esito["cambiato"] is True
    fonti = impronta_fonti.FontiTenant(studio_db=studio_db, registro_db=registro_db, file=(str(config),))
    archivio = ArchivioPannelli(base / "intelligence" / "pannelli_pronti.db")
    return SimpleNamespace(base=base, studio_db=studio_db, registro_db=registro_db, config=config, fonti=fonti,
                           archivio=archivio)


def _esegui(percorso, sql, parametri=()):
    conn = sqlite3.connect(percorso)
    conn.execute(sql, parametri)
    conn.commit()
    conn.close()


def _impronta(studio, fascicolo="F1", **extra):
    return impronta_fonti.impronta(studio.fonti, fascicolo, generazione=studio.archivio.generazione(fascicolo),
                                   versione=extra.pop("versione", "2.488.0"), **extra)


def test_preparazione_idempotente_e_backup(studio, tmp_path):
    seconda = prepara_database(studio.studio_db, tabelle_senza_fascicolo=("email_mailbox_records", "clienti"),
                               backup_dir=tmp_path / "backup", applica=True)
    assert seconda["cambiato"] is False
    backup = list((tmp_path / "backup").glob("studio-*/manifest.json"))
    assert len(backup) == 1


def test_senza_preparazione_nessuna_impronta(tmp_path):
    studio_db, registro_db = str(tmp_path / "s.db"), str(tmp_path / "r.db")
    _studio_db(studio_db)
    _registro_db(registro_db)
    fonti = impronta_fonti.FontiTenant(studio_db=studio_db, registro_db=registro_db)
    assert impronta_fonti.impronta(fonti, "F1", generazione=0, versione="x") is None


def test_audit_di_consultazione_non_invalida_la_lettura():
    with sqlite3.connect(":memory:") as conn:
        conn.execute("CREATE TABLE practice_audit_events(fascicolo_id TEXT, event_type TEXT)")
        revisioni.installa(conn)
        iniziale = revisioni.leggi(conn, "F1")
        conn.executemany(
            "INSERT INTO practice_audit_events VALUES ('F1', ?)",
            [(evento,) for evento in ("DOC_VIEWED", "DOC_DOWNLOADED", "DOC_EIDAS_CHECKED")],
        )
        assert revisioni.leggi(conn, "F1") == iniziale

        conn.execute("INSERT INTO practice_audit_events VALUES ('F1', 'ECONOMIC_OVERRIDE')")
        assert revisioni.leggi(conn, "F1")[1] == iniziale[1] + 1
        conn.execute("UPDATE practice_audit_events SET event_type='DOC_VIEWED' WHERE event_type='ECONOMIC_OVERRIDE'")
        assert revisioni.leggi(conn, "F1")[1] == iniziale[1] + 2


def test_salvare_esperienza_conclusa_non_invalida_la_lettura(studio, tmp_path):
    _esegui(studio.registro_db, "CREATE TABLE letture_fascicoli(fascicolo_id TEXT, lettore TEXT, impronta TEXT)")
    prepara_database(studio.registro_db, backup_dir=tmp_path / "backup", applica=True)
    iniziale = _impronta(studio)
    _esegui(studio.registro_db, "INSERT INTO letture_fascicoli VALUES ('F1', 'percorso_concluso', 'v1')")
    _esegui(studio.registro_db, "UPDATE letture_fascicoli SET impronta='v2' WHERE lettore='percorso_concluso'")
    assert _impronta(studio) == iniziale
    _esegui(studio.registro_db, "INSERT INTO letture_fascicoli VALUES ('F1', 'motore_documenti', 'v1')")
    assert _impronta(studio) != iniziale


def test_trigger_per_fascicolo_e_esclusioni(studio):
    conn = sqlite3.connect(studio.studio_db)
    nomi = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
    conn.close()
    assert "pannelli_rev_scadenze_i" in nomi and "pannelli_rev_fascicoli_un" in nomi
    assert not any("transactional_outbox" in n or "fascicoli_list_rows" in n for n in nomi)
    # Un documento spostato a un altro fascicolo cambia entrambi.
    prima_f1, prima_f2 = _impronta(studio, "F1"), _impronta(studio, "F2")
    _esegui(studio.studio_db, "INSERT INTO deposit_sessions VALUES ('D1','F1','bozza')")
    _esegui(studio.studio_db, "UPDATE deposit_sessions SET fascicolo_id='F2' WHERE id='D1'")
    assert _impronta(studio, "F1") != prima_f1 and _impronta(studio, "F2") != prima_f2


@pytest.mark.parametrize("descrizione, database, sql", [
    ("documento caricato (riga del fascicolo)", "studio", "UPDATE fascicoli SET dati_json='{\"documenti\": [1]}' WHERE id='F1'"),
    ("scadenza", "studio", "INSERT INTO scadenze VALUES ('S1','F1','{}')"),
    ("appuntamento", "studio", "INSERT INTO appuntamenti VALUES ('A1','F1','{}')"),
    ("pagamento (parcella)", "studio", "INSERT INTO parcelle VALUES ('P1','F1','{}')"),
    ("voce di catalogo", "studio", "INSERT INTO document_catalog_assignments VALUES ('C1','t','F1','contributo')"),
    ("deposito telematico", "studio", "INSERT INTO deposit_sessions VALUES ('D2','F1','inviato')"),
    ("CTU", "studio", "INSERT INTO ctu_incarichi VALUES ('T1','F1','aperto')"),
    ("mediazione", "studio", "INSERT INTO mediazione_procedimenti VALUES ('M1','F1','aperta')"),
    ("PEC collegata (casella)", "studio", "INSERT INTO email_mailbox_records VALUES ('E1','{}')"),
    ("cliente", "studio", "INSERT INTO clienti VALUES ('K1','{}')"),
    ("lettura nuova (fatto)", "registro", "INSERT INTO letture_fatti VALUES ('L1','t','F1','data','2026-12-01','plausibile')"),
    ("oggetto letto", "registro", "INSERT INTO letture_oggetti VALUES ('O1','t','F1','abc')"),
    ("decisione dell'avvocato", "registro", "INSERT INTO letture_verifiche_esiti VALUES ('V1','F1','confermata')"),
])
def test_ogni_fonte_cambia_l_impronta(studio, descrizione, database, sql):
    prima = _impronta(studio)
    _esegui(studio.studio_db if database == "studio" else studio.registro_db, sql)
    assert _impronta(studio) != prima, descrizione


def test_fonti_non_lette_non_cambiano_l_impronta(studio):
    prima = _impronta(studio)
    _esegui(studio.studio_db, "INSERT INTO transactional_outbox VALUES ('X','case:F1')")
    _esegui(studio.studio_db, "INSERT INTO fascicoli_list_rows VALUES ('t','F1','F1')")
    _esegui(studio.registro_db, "INSERT INTO letture_viste VALUES ('W','F1','u','2026-11-10')")
    _esegui(studio.registro_db, "INSERT INTO letture_payload_cache VALUES ('Y','F1','{}')")
    _esegui(studio.studio_db, "INSERT INTO scadenze VALUES ('S9','F2','{}')")  # altro fascicolo
    assert _impronta(studio) == prima


def test_giorno_versione_generazione_e_file(studio):
    oggi = datetime(2026, 11, 10, 23, 30, tzinfo=ROMA)
    base = _impronta(studio, adesso=oggi)
    assert _impronta(studio, adesso=datetime(2026, 11, 10, 22, 59, tzinfo=ZoneInfo("UTC"))) == base  # 23:59 a Roma
    assert _impronta(studio, adesso=datetime(2026, 11, 11, 0, 1, tzinfo=ROMA)) != base  # cambio del giorno
    assert _impronta(studio, adesso=oggi, versione="2.489.0") != base
    studio.archivio.invalida_fascicolo("F1")
    dopo_scrittura = _impronta(studio, adesso=oggi)
    assert dopo_scrittura != base
    studio.config.write_text('{"cambiato": true}', encoding="utf-8")
    os.utime(studio.config, ns=(1, 2))
    assert _impronta(studio, adesso=oggi) != dopo_scrittura


def test_impronta_ignora_la_creazione_del_wal_vuoto(studio):
    wal = studio.config.with_name(studio.config.name + "-wal")
    prima = _impronta(studio)
    wal.touch()
    assert _impronta(studio) == prima
    wal.write_bytes(b"un frame nuovo")
    assert _impronta(studio) != prima


def test_fonti_studio_coprono_agenda_storica_e_registro_pec(studio, tmp_path):
    from web.services.pannelli_pronti_fonti import TABELLE_STUDIO, file_dello_studio

    _esegui(studio.studio_db, "DROP TABLE appuntamenti")
    _esegui(studio.studio_db, "CREATE TABLE appuntamenti (id TEXT PRIMARY KEY, dati_json TEXT)")
    prepara_database(studio.studio_db, tabelle_senza_fascicolo=TABELLE_STUDIO,
                     backup_dir=tmp_path / "backup", applica=True)
    prima_f1, prima_f2 = _impronta(studio, "F1"), _impronta(studio, "F2")
    _esegui(studio.studio_db, "INSERT INTO appuntamenti VALUES (?, ?)", ("A1", '{"id_fascicolo":"F1"}'))
    assert _impronta(studio, "F1") != prima_f1
    assert _impronta(studio, "F2") == prima_f2

    prima_f1, prima_f2 = _impronta(studio, "F1"), _impronta(studio, "F2")
    _esegui(studio.studio_db, "UPDATE appuntamenti SET dati_json=? WHERE id='A1'", ('{"id_fascicolo":"F2"}',))
    assert _impronta(studio, "F1") != prima_f1
    assert _impronta(studio, "F2") != prima_f2

    prima_f1, prima_f2 = _impronta(studio, "F1"), _impronta(studio, "F2")
    _esegui(studio.studio_db, "INSERT INTO appuntamenti VALUES ('A2', '{}')")
    assert _impronta(studio, "F1") != prima_f1
    assert _impronta(studio, "F2") != prima_f2

    casella = tmp_path / "email" / "casella.json"
    assert file_dello_studio({"EMAIL_CASELLA_DB": casella}) == (str(casella.with_name("pec_audit.sqlite")),)


def test_archivio_salva_e_conteggi(studio):
    archivio = studio.archivio
    archivio.registra_richiesta(chiave_voce="k", fascicolo_id="F1", pannello="quadro", percorso="/q", profilo="p",
                                sessione={"user_id": "u"}, servito=False)
    assert archivio.voce("k").impronta == ""
    archivio.salva(chiave_voce="k", fascicolo_id="F1", pannello="quadro", percorso="/q", profilo="p", impronta="i1",
                   stato=200, tipo="application/json", corpo=b'{"ok": true}', durata_ms=5)
    voce = archivio.voce("k")
    assert (voce.impronta, bytes(voce.corpo)) == ("i1", b'{"ok": true}')
    assert archivio.sessione("p") == {"user_id": "u"}
    assert archivio.fascicoli_aperti_dal(1) == ["F1"]
    assert archivio.conteggi() == {"voci": 1, "pronte": 1, "fascicoli": 1}


def test_servito_dal_salvato_anche_se_la_registrazione_della_visita_e_occupata(studio, app_prova):
    from web.services.pannelli_pronti_runtime import INTESTAZIONE

    app, calcoli = app_prova.app, app_prova.calcoli
    client = app.test_client()
    assert client.get("/f/F1/quadro").headers[INTESTAZIONE] == "calcolato"
    with sqlite3.connect(studio.archivio.percorso) as scrittore:
        scrittore.execute("BEGIN IMMEDIATE")
        risposta = client.get("/f/F1/quadro")
        assert risposta.headers[INTESTAZIONE] == "pronto"
        assert risposta.get_json()["fascicolo"] == "F1"
        assert calcoli["n"] == 1



# ---- risposta dal salvato -----------------------------------------------------------------------------------


@pytest.fixture()
def app_prova(studio, monkeypatch):
    from web.services import pannelli_pronti_runtime as runtime
    from web.services.pannelli_pronti_catalogo import Pannello

    monkeypatch.setattr(runtime, "fonti_per_percorsi", lambda _paths: studio.fonti)
    app = Flask("prova")
    app.secret_key = "prova"
    calcoli = {"n": 0}
    pannello = Pannello("quadro", "quadro", percorso="/f/{fid}/quadro")

    @app.before_request
    def _utente():
        g.utente_corrente = SimpleNamespace(id="u1", ruolo="AVVOCATO", permessi_effettivi=["fascicoli.leggi"],
                                            is_admin=False)
        g.data_paths = {"STUDIO_DB": studio.studio_db}
        g.tenant_context_slug = "studio-prova"

    @app.get("/f/<id_fasc>/quadro")
    def quadro(id_fasc):
        calcoli["n"] += 1
        conn = sqlite3.connect(studio.studio_db)
        scadenze = conn.execute("SELECT COUNT(*) FROM scadenze WHERE id_fascicolo=?", (id_fasc,)).fetchone()[0]
        conn.close()
        return jsonify({"ok": True, "fascicolo": id_fasc, "scadenze": scadenze})

    @app.post("/f/<id_fasc>/attivita")
    def scrivi(id_fasc):
        return jsonify({"ok": True})

    @app.get("/f/<id_fasc>/errore")
    def errore(id_fasc):
        calcoli["n"] += 1
        return jsonify({"ok": False, "errore": "non disponibile"})

    app.view_functions["quadro"] = runtime.pannello_pronto(pannello)(quadro)
    app.view_functions["errore"] = runtime.pannello_pronto(Pannello("errore", "errore"))(errore)
    app.after_request(runtime.invalida_dopo_scrittura)
    return SimpleNamespace(app=app, calcoli=calcoli)


def test_risposta_dal_salvato_e_ricalcolo_quando_cambia_una_fonte(studio, app_prova):
    client = app_prova.app.test_client()
    prima = client.get("/f/F1/quadro")
    assert prima.headers["X-Iusentra-Pannello"] == "calcolato" and app_prova.calcoli["n"] == 1
    seconda = client.get("/f/F1/quadro?_=123")  # anti-cache del browser: stessa chiave
    assert seconda.headers["X-Iusentra-Pannello"] == "pronto" and app_prova.calcoli["n"] == 1
    assert seconda.get_data() == prima.get_data()
    _esegui(studio.studio_db, "INSERT INTO scadenze VALUES ('S1','F1','{}')")
    terza = client.get("/f/F1/quadro")
    assert terza.headers["X-Iusentra-Pannello"] == "calcolato" and json.loads(terza.get_data())["scadenze"] == 1


def test_scrittura_sul_fascicolo_invalida_subito(app_prova):
    client = app_prova.app.test_client()
    client.get("/f/F1/quadro")
    client.post("/f/F1/attivita")
    assert client.get("/f/F1/quadro").headers["X-Iusentra-Pannello"] == "calcolato"
    assert app_prova.calcoli["n"] == 2


def test_errori_non_si_salvano(app_prova):
    client = app_prova.app.test_client()
    client.get("/f/F1/errore")
    client.get("/f/F1/errore")
    assert app_prova.calcoli["n"] == 2


def test_sfondo_trova_le_voci_superate(studio, app_prova):
    from web.services.pannelli_pronti_sfondo import da_ricalcolare

    client = app_prova.app.test_client()
    client.get("/f/F1/quadro")
    superate = [v for v in da_ricalcolare(studio.archivio, studio.fonti) if v.pannello == "quadro"]
    assert superate == []
    _esegui(studio.studio_db, "INSERT INTO parcelle VALUES ('P1','F1','{}')")
    superate = [v for v in da_ricalcolare(studio.archivio, studio.fonti) if v.pannello == "quadro"]
    assert [(v.fascicolo_id, v.motivo) for v in superate] == [("F1", "fonti cambiate")]


def test_apertura_a_freddo_e_aggiornamento_passano_dal_database(studio, app_prova, monkeypatch):
    from flask import session

    from web.services import pannelli_pronti_calcolatore as calcolatore
    from web.services.pannelli_pronti_sfondo import da_ricalcolare, ricalcola

    monkeypatch.setattr(calcolatore, "sveglia_calcolatore", lambda *_: True)

    @app_prova.app.before_request
    def _sessione():
        session["user_id"] = "u1"

    headers = {"X-Iusentra-Preparazione": "sfondo"}
    client = app_prova.app.test_client()
    url = "/f/F1/quadro"

    def prepara():
        voci = [voce for voce in da_ricalcolare(studio.archivio, studio.fonti) if voce.pannello == "quadro"]
        assert len(voci) == 1
        assert ricalcola(app_prova.app, studio.archivio, voci)["calcolati"] == 1

    prima = client.get(url, headers=headers)
    assert prima.status_code == 202 and prima.headers["Retry-After"] == "2"
    assert app_prova.calcoli["n"] == 0
    prepara()
    assert client.get(url, headers=headers).get_json()["scadenze"] == 0
    assert app_prova.calcoli["n"] == 1

    _esegui(studio.studio_db, "INSERT INTO scadenze VALUES ('S1','F1','{}')")
    assert client.get(url, headers=headers).status_code == 202
    assert app_prova.calcoli["n"] == 1
    prepara()
    aggiornata = client.get(url, headers=headers)
    assert aggiornata.headers["X-Iusentra-Pannello"] == "pronto"
    assert aggiornata.get_json()["scadenze"] == 1
    assert app_prova.calcoli["n"] == 2


def test_pannello_in_sfondo_con_archivio_occupato_non_calcola_nella_richiesta(studio, app_prova, monkeypatch):
    from flask import session

    from pct.pannelli_pronti.archivio import ArchivioPannelli
    from web.services import pannelli_pronti_calcolatore as calcolatore

    @app_prova.app.before_request
    def _sessione():
        session["user_id"] = "u1"

    def occupato(*args, **kwargs):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(ArchivioPannelli, "registra_richiesta", occupato)
    monkeypatch.setattr(calcolatore, "sveglia_calcolatore", lambda *_: True)
    risposta = app_prova.app.test_client().get("/f/F1/quadro", headers={"X-Iusentra-Preparazione": "sfondo"})
    assert risposta.status_code == 202 and risposta.headers["Retry-After"] == "2"
    assert app_prova.calcoli["n"] == 0



def test_lettura_consultabile_durante_le_verifiche():
    import json
    from web.services.pannelli_pronti_catalogo import PER_ENDPOINT

    lettura = PER_ENDPOINT["api_v1_react.fascicolo_react_lettura"]
    corpo = json.dumps({"ok": True, "lettura": {"verifiche": {"in_corso": True},
                                                "prossimi_passi": [{"azione": "Verificare la notifica"}]}})
    assert lettura.memorizzabile(corpo.encode())
    assert not lettura.memorizzabile(b'{"ok":false,"errore":"Lettura non disponibile"}')


def test_quadro_salvato_riflette_la_lettura_corrente_senza_ricalcolare_agenda(app_prova, monkeypatch):
    from pct.fascicolo_quadro import riga_notifiche
    from web.services import fascicolo_quadro_runtime as quadro
    from web.services import obblighi_notifica_sintesi
    from web.services import pannelli_pronti_runtime as runtime
    from web.services import riscontri_processuali_runtime as riscontri
    from web.services.pannelli_pronti_catalogo import Pannello

    lettura = {"prossimi_passi": [{"azione": "Verificare la consegna", "norma": "art. 326 c.p.c."}]}
    monkeypatch.setattr(riscontri, "lettura_materializzata", lambda _fid: lettura)
    sintesi = {"obblighi": []}
    monkeypatch.setattr(obblighi_notifica_sintesi, "leggi", lambda _fid: sintesi)
    viste = app_prova.app.view_functions
    chiamate = []

    def vista(id_fasc):
        chiamate.append(id_fasc)
        return jsonify(ok=True, righe=[quadro.prossimo_passo_da_lettura(lettura),
                                          riga_notifiche(None, oggi=datetime.now(ROMA).date())],
                       termini_agenda=[], termini_agenda_versione=2)

    viste["quadro"] = runtime.pannello_pronto(Pannello(
        "quadro", "quadro", ricomponi="quadro_da_lettura",
    ))(vista)
    client = app_prova.app.test_client()
    prima = client.get("/f/F1/quadro")
    assert prima.json["righe"][0]["testo"] == "Verificare la consegna · art. 326 c.p.c."
    assert "termini_agenda" not in prima.json

    lettura["prossimi_passi"] = [{"azione": "Verificare il deposito"}]
    sintesi["obblighi"] = [{"atto": "Sentenza", "stato": "da_verificare"}]
    seconda = client.get("/f/F1/quadro")
    assert seconda.headers["X-Iusentra-Pannello"] == "pronto"
    assert seconda.json["righe"][0]["testo"] == "Verificare il deposito"
    assert seconda.json["righe"][1]["testo"] == "Sentenza: notifica da verificare"
    assert chiamate == ["F1"]



def test_lettura_preparata_dal_ciclo_si_apre_senza_calcolo(app_prova, monkeypatch):
    from flask import session

    from web.blueprints import api_v1_react
    from web.services import pannelli_pronti_runtime as runtime
    from web.services import riscontri_processuali_runtime as riscontri
    from web.services.pannelli_pronti_catalogo import Pannello

    corpo = b'{"ok":true,"lettura":{"prossimi_passi":[{"azione":"Verificare la consegna"}]}}'
    monkeypatch.setattr(api_v1_react, "lettura_preparata", lambda fid: corpo if fid == "F1" else None)
    app = app_prova.app

    @app.before_request
    def _sessione():
        session["user_id"] = "u1"

    @app.get("/f/<id_fasc>/lettura")
    @runtime.pannello_pronto(Pannello("lettura", "lettura", ricomponi="stato_presidi_lettura"))
    def lettura(id_fasc):
        raise AssertionError("La lettura preparata non va ricalcolata.")

    with app.test_client() as client:
        risposta = client.get("/f/F1/lettura", headers={"X-Iusentra-Preparazione": "sfondo"})

    assert risposta.status_code == 200
    assert risposta.headers["X-Iusentra-Pannello"] == "pronto"
    assert risposta.json["lettura"]["prossimi_passi"] == [{"azione": "Verificare la consegna"}]
    with app.test_request_context("/"):
        assert riscontri.lettura_materializzata("F1") == risposta.json["lettura"]


def test_quadro_richiede_lettura_anche_a_pannello_chiuso(studio, app_prova, monkeypatch):
    from flask import session
    from web.services import pannelli_pronti_calcolatore, pannelli_pronti_runtime as runtime
    from web.services.pannelli_pronti_catalogo import Pannello

    sveglie = []
    monkeypatch.setattr(pannelli_pronti_calcolatore, "sveglia_calcolatore", lambda tenant, fid: sveglie.append(fid))
    app = app_prova.app

    @app.before_request
    def _sessione():
        session["user_id"] = "u1"

    @runtime.pannello_pronto(Pannello("quadro", "quadro", ricomponi="quadro_da_lettura"))
    def vista(id_fasc):
        return jsonify(ok=True, righe=[], termini_agenda=[], termini_agenda_versione=2, lettura_mancante=True)

    app.view_functions["quadro"] = vista
    risposta = app.test_client().get("/f/F1/quadro")

    assert risposta.json["lettura_in_preparazione"] is True
    assert "lettura_mancante" not in risposta.json
    assert sveglie == ["F1"]
    assert studio.archivio.fascicoli_in_attesa_di_lettura(minuti=1) == ["F1"]


def test_lettura_conclusa_riprogramma_pannelli_di_un_fascicolo_gia_aperto(studio, app_prova):
    from web.services.pannelli_pronti_sfondo import da_ricalcolare

    app_prova.app.test_client().get("/f/F1/quadro")
    _esegui(studio.archivio.percorso, "UPDATE aperture SET aperto_il='2000-01-01T00:00:00Z'")
    _esegui(studio.registro_db, "INSERT INTO letture_fatti VALUES ('L1','t','F1','data','2026-12-01','plausibile')")

    assert da_ricalcolare(studio.archivio, studio.fonti) == []
    assert not studio.archivio.segnala_fonti_aggiornate("F2")
    assert studio.archivio.segnala_fonti_aggiornate("F1")
    assert any(v.pannello == "quadro" and v.fascicolo_id == "F1"
               for v in da_ricalcolare(studio.archivio, studio.fonti))


def test_lettura_superata_consultabile_con_avviso(app_prova, studio, monkeypatch):
    from flask import session
    from web.blueprints import api_v1_react
    from web.services import pannelli_pronti_calcolatore, pannelli_pronti_runtime as runtime
    from web.services.pannelli_pronti_catalogo import PER_ENDPOINT, Pannello

    monkeypatch.setattr(api_v1_react, "lettura_preparata", lambda _fid: None)
    monkeypatch.setattr(pannelli_pronti_calcolatore, "sveglia_calcolatore", lambda *_: True)
    app = app_prova.app

    @app.before_request
    def _sessione():
        session["user_id"] = "u1"

    @app.get("/f/<id_fasc>/lettura")
    @runtime.pannello_pronto(PER_ENDPOINT["api_v1_react.fascicolo_react_lettura"])
    def vista(id_fasc):
        return jsonify(ok=True, lettura={
            "generata_il": "12/11/2026",
            "prossimi_passi": [{"azione": "Controllare la ricevuta", "norma": "art. 326 c.p.c."}],
        })

    @runtime.pannello_pronto(Pannello("quadro", "quadro", ricomponi="quadro_da_lettura"))
    def quadro(id_fasc):
        return jsonify(ok=True, righe=[], termini_agenda=[], termini_agenda_versione=2, lettura_mancante=True)

    app.view_functions["quadro"] = quadro
    client = app.test_client()
    assert client.get("/f/F1/lettura").headers["X-Iusentra-Pannello"] == "calcolato"
    studio.archivio.invalida_fascicolo("F1")

    risposta = client.get("/f/F1/lettura", headers={"X-Iusentra-Preparazione": "sfondo"})

    assert risposta.headers["X-Iusentra-Pannello"] == "precedente"
    assert risposta.json["lettura"]["generata_il"] == "12/11/2026"
    assert risposta.json["lettura"]["aggiornamento_pendente"] is True
    assert studio.archivio.fascicoli_in_attesa_di_lettura(minuti=1) == ["F1"]

    assert client.get("/f/F1/quadro").json["lettura_in_preparazione"] is True
    quadro_salvato = client.get("/f/F1/quadro").json
    assert quadro_salvato["lettura_precedente"] is True
    assert next(r["testo"] for r in quadro_salvato["righe"] if r["tema"] == "prossimo_passo") == (
        "Controllare la ricevuta · art. 326 c.p.c."
    )
    assert quadro_salvato["lettura_in_preparazione"] is True


def test_ricalcolo_da_apertura_considera_solo_il_fascicolo_richiesto(studio, app_prova, monkeypatch):
    from web.services import pannelli_pronti_sfondo

    client = app_prova.app.test_client()
    for fid in ("F1", "F2"):
        client.get(f"/f/{fid}/quadro")
        studio.archivio.invalida_fascicolo(fid)

    def scansione_non_necessaria(*args, **kwargs):
        raise AssertionError("L'apertura puntuale non deve enumerare i fascicoli")

    monkeypatch.setattr(studio.archivio, "fascicoli_aperti_dal", scansione_non_necessaria)
    monkeypatch.setattr(studio.archivio, "fascicoli_in_attesa_di_lettura", scansione_non_necessaria)
    voci = pannelli_pronti_sfondo.da_ricalcolare(studio.archivio, studio.fonti, fascicolo_richiesto="F2")

    assert {voce.fascicolo_id for voce in voci} == {"F2"}


def test_elenco_documenti_subito_disponibile_e_riusato(studio, app_prova, monkeypatch):
    from flask import session
    from web.services import pannelli_pronti_calcolatore as calcolatore
    from web.services import pannelli_pronti_runtime as runtime
    from web.services.pannelli_pronti_catalogo import Pannello

    def non_accodare(*_):
        pytest.fail("L'elenco documenti deve restare disponibile con il calcolatore occupato.")

    monkeypatch.setattr(calcolatore, "sveglia_calcolatore", non_accodare)
    aperture = []

    @app_prova.app.before_request
    def _sessione():
        session["user_id"] = "u1"

    @app_prova.app.get("/f/<id_fasc>/documenti")
    @runtime.pannello_pronto(Pannello("documenti", "documenti"))
    def documenti(id_fasc):
        aperture.append(id_fasc)
        return {"documents": [{"id": "D1", "name": "atto.pdf"}]}

    client = app_prova.app.test_client()
    headers = {"X-Iusentra-Preparazione": "sfondo"}
    prima = client.get("/f/F1/documenti", headers=headers)
    seconda = client.get("/f/F1/documenti", headers=headers)
    assert prima.status_code == 200
    assert prima.get_json() == seconda.get_json() == {"documents": [{"id": "D1", "name": "atto.pdf"}]}
    assert seconda.headers["X-Iusentra-Pannello"] == "pronto"
    assert aperture == ["F1"]


def test_riscontri_dello_stesso_quadro_condividono_la_revisione_nella_richiesta(studio, app_prova, monkeypatch):
    from web.services import pannelli_pronti_runtime as runtime

    originale = runtime.impronta_fonti.impronta
    letture = []

    def misura(fonti, fascicolo_id, **kwargs):
        letture.append(fascicolo_id)
        return originale(fonti, fascicolo_id, **kwargs)

    monkeypatch.setattr(runtime.impronta_fonti, "impronta", misura)
    with app_prova.app.test_request_context("/f/F1/quadro"):
        contesto = runtime.Contesto(studio.archivio, studio.fonti, "profilo", {})
        prima = runtime.impronta_attuale(contesto, "F1")
        assert prima and runtime.impronta_attuale(contesto, "F1") == prima
    assert letture == ["F1"]


def test_consultazione_pannello_a_freddo_non_installa_schema(studio, monkeypatch):
    from pct.pannelli_pronti import archivio as archivio_modulo

    archivio = studio.archivio
    assert archivio.voce("chiave") is None
    assert archivio.generazione("F1") == 0
    assert not os.path.exists(archivio.percorso)

    archivio.invalida_fascicolo("F1")
    archivio.salva(chiave_voce="chiave", fascicolo_id="F1", pannello="quadro", percorso="/f/F1/quadro",
                   profilo="p", impronta="rev", stato=200, tipo="application/json", corpo=b"{}", durata_ms=1)
    monkeypatch.setattr(archivio_modulo, "_PREPARATI", set())
    with sqlite3.connect(archivio.percorso) as scrittore:
        scrittore.execute("BEGIN IMMEDIATE")
        assert ArchivioPannelli(archivio.percorso).voce("chiave").corpo == b"{}"
        assert ArchivioPannelli(archivio.percorso).generazione("F1") == 1
        assert not archivio_modulo._PREPARATI


def test_quadro_salvato_risponde_prima_di_registrare_la_consultazione(studio, app_prova, monkeypatch):
    from pct.pannelli_pronti.archivio import ArchivioPannelli

    client = app_prova.app.test_client()
    primo = client.get("/f/F1/quadro")
    assert primo.headers["X-Iusentra-Pannello"] == "calcolato"
    primo.close()
    _esegui(studio.archivio.percorso, "UPDATE pannelli SET richiesto_il='2000-01-01'")
    originale = ArchivioPannelli.registra_richiesta
    richieste = []

    def registra(archivio, **dati):
        richieste.append(dati["servito"])
        originale(archivio, **dati)

    monkeypatch.setattr(ArchivioPannelli, "registra_richiesta", registra)
    risposta = client.get("/f/F1/quadro", buffered=False)
    assert risposta.headers["X-Iusentra-Pannello"] == "pronto"
    assert risposta.json["fascicolo"] == "F1"
    assert richieste == []
    risposta.close()
    assert richieste == [True]


def test_quadro_superato_mostra_i_riscontri_correnti_e_accoda_il_ricalcolo(studio, app_prova, monkeypatch):
    from flask import session
    from web.services import pannelli_pronti_calcolatore, pannelli_pronti_runtime as runtime
    from web.services import riscontri_processuali_runtime as riscontri
    from web.services.pannelli_pronti_catalogo import Pannello

    @app_prova.app.before_request
    def sessione():
        session["user_id"] = "u1"

    avvii = []
    monkeypatch.setattr(pannelli_pronti_calcolatore, "sveglia_calcolatore", lambda _, fid: avvii.append(fid))
    monkeypatch.setattr(riscontri, "lettura_consultiva", lambda _: {
        "prossimi_passi": [{"azione": "Verificare la consegna"}],
        "ragionamento": {"versione": "test", "impronta": "test", "conclusioni": [
            {"codice": "termine_impugnazione", "cosa": "Impugnazione della sentenza",
             "termine": {"scadenza": "02/08/2024", "scaduto": True},
             "norme": [{"norma": "art. 327 c.p.c."}]}
        ]},
    })

    @runtime.pannello_pronto(Pannello("quadro", "quadro", ricomponi="quadro_da_lettura"))
    def quadro(id_fasc):
        app_prova.calcoli["n"] += 1
        return jsonify(ok=True, righe=[{"tema": "documenti", "testo": "Conteggio precedente"}],
                       termini_agenda=[], termini_agenda_versione=2)

    app_prova.app.view_functions["quadro"] = quadro
    client = app_prova.app.test_client()
    assert client.get("/f/F1/quadro").status_code == 200
    studio.archivio.invalida_pannelli("F1", ("quadro",))
    risposta = client.get("/f/F1/quadro", headers={"X-Iusentra-Preparazione": "sfondo"})
    assert risposta.headers["X-Iusentra-Pannello"] == "precedente"
    assert risposta.json["quadro_in_aggiornamento"]
    righe = {r["tema"]: r["testo"] for r in risposta.json["righe"]}
    assert righe == {
        "prossimo_passo": "Verificare la consegna",
        "termini": "Impugnazione della sentenza: 02/08/2024 (decorso) · art. 327 c.p.c. Agenda in aggiornamento.",
    }
    assert app_prova.calcoli["n"] == 1
    assert avvii == ["F1"]

    from web.services.pannelli_pronti_sfondo import da_ricalcolare

    coda = da_ricalcolare(studio.archivio, studio.fonti, limite=1, solo_pannelli_prioritari=True)
    assert [(voce.fascicolo_id, voce.pannello) for voce in coda] == [("F1", "quadro")]
