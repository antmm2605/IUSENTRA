"""Copertura dei pannelli pronti per tutti i fascicoli non archiviati.

Dati fittizi (studio.db e registro minimi). Verifica che:
- le impronte calcolate in blocco coincidano con quelle calcolate una alla volta, dopo ogni tipo di modifica;
- l'ordine di preparazione metta prima i fascicoli aperti di recente, poi i termini vicini, poi gli altri;
- la copertura proponga i pannelli dei fascicoli mai aperti, salti quelli già pronti, rimetta per primi i fascicoli
  con una fonte cambiata, riprenda dopo un'interruzione e non ritenti con le stesse fonti un calcolo fallito;
- un UPDATE di una tabella condivisa che non cambia nulla non invalidi i pannelli di tutti i fascicoli.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from pct.pannelli_pronti import impronta as impronta_fonti
from pct.pannelli_pronti.archivio import ArchivioPannelli
from pct.pannelli_pronti.preparazione import prepara_database

ROMA = ZoneInfo("Europe/Rome")
VERSIONE = "prova-copertura"


def _esegui(percorso, sql, parametri=()):
    conn = sqlite3.connect(percorso)
    conn.execute(sql, parametri)
    conn.commit()
    conn.close()


@pytest.fixture()
def studio(tmp_path, monkeypatch):
    from web.services import pannelli_pronti_sfondo as sfondo

    base = tmp_path / "tenants" / "studio-prova"
    (base / "intelligence").mkdir(parents=True)
    studio_db, registro_db = str(base / "studio.db"), str(base / "intelligence" / "registro_letture.db")
    conn = sqlite3.connect(studio_db)
    conn.executescript(
        """
        CREATE TABLE fascicoli (id TEXT PRIMARY KEY, stato TEXT, modificato_il TEXT, dati_json TEXT);
        CREATE TABLE scadenze (id TEXT PRIMARY KEY, id_fascicolo TEXT, stato TEXT, data_scadenza TEXT, dati_json TEXT);
        CREATE TABLE parcelle (id TEXT PRIMARY KEY, id_fascicolo TEXT, dati_json TEXT);
        CREATE TABLE settings_config (section TEXT PRIMARY KEY, dati_json TEXT);
        CREATE TABLE email_mailbox_records (message_key TEXT PRIMARY KEY, read_state TEXT, payload_json TEXT);
        INSERT INTO fascicoli VALUES ('F1','IN_CORSO','2026-11-01','{}'), ('F2','DEFINITO','2026-11-15','{}'),
            ('F3','IN_CORSO','2026-10-01','{}'), ('F4','ARCHIVIATO','2026-11-17','{}'), ('F5','APERTO','2026-09-01','{}');
        INSERT INTO scadenze VALUES ('S1','F3','APERTO','2026-11-25','{}'), ('S2','F2','COMPLETATO','2026-11-20','{}'),
            ('S3','F1','APERTO','2026-10-01','{}');
        INSERT INTO settings_config VALUES ('studio','{"nome":"Studio"}');
        """
    )
    conn.commit()
    conn.close()
    conn = sqlite3.connect(registro_db)
    conn.executescript(
        """
        CREATE TABLE letture_fatti (id TEXT PRIMARY KEY, fascicolo_id TEXT, valore TEXT);
        CREATE TABLE letture_sintesi_fascicolo (id TEXT PRIMARY KEY, fascicolo_id TEXT, stato TEXT,
            prossima_udienza TEXT, aggiornato_il TEXT);
        INSERT INTO letture_sintesi_fascicolo VALUES ('x5','F5','APERTO','2026-11-21',''),
            ('x2','F2','DEFINITO','2026-11-01','');
        """
    )
    conn.commit()
    conn.close()
    for percorso, tabelle in ((studio_db, ("settings_config", "email_mailbox_records")), (registro_db, ())):
        prepara_database(percorso, tabelle_senza_fascicolo=tabelle, backup_dir=tmp_path / "backup", applica=True)
    config = base / "config.json"
    config.write_text("{}", encoding="utf-8")
    fonti = impronta_fonti.FontiTenant(studio_db=studio_db, registro_db=registro_db, file=(str(config),))
    archivio = ArchivioPannelli(base / "intelligence" / "pannelli_pronti.db")
    monkeypatch.setattr(sfondo, "VERSIONE_PANNELLI", VERSIONE)
    return SimpleNamespace(studio_db=studio_db, registro_db=registro_db, fonti=fonti, archivio=archivio, config=config)


def _singola(studio, fid):
    return impronta_fonti.impronta(studio.fonti, fid, generazione=studio.archivio.generazione(fid), versione=VERSIONE)


def _in_blocco(studio, ids=("F1", "F2", "F3", "F5", "MAI")):
    generazioni = studio.archivio.generazioni()
    return impronta_fonti.impronte(studio.fonti, {f: generazioni.get(f, 0) for f in ids}, versione=VERSIONE)


@pytest.mark.parametrize("modifica", [
    lambda s: None,
    lambda s: _esegui(s.studio_db, "INSERT INTO scadenze VALUES ('S9','F1','APERTO','2026-12-01','{}')"),
    lambda s: _esegui(s.studio_db, "UPDATE fascicoli SET dati_json='{\"x\":1}' WHERE id='F2'"),
    lambda s: _esegui(s.studio_db, "INSERT INTO parcelle VALUES ('P1','F3','{}')"),
    lambda s: _esegui(s.studio_db, "UPDATE settings_config SET dati_json='{\"nome\":\"Altro\"}'"),
    lambda s: _esegui(s.studio_db, "INSERT INTO email_mailbox_records VALUES ('m1','letto','{}')"),
    lambda s: _esegui(s.registro_db, "INSERT INTO letture_fatti VALUES ('L1','F5','2026-12-01')"),
    lambda s: s.archivio.invalida_fascicolo("F1"),
    lambda s: s.config.write_text('{"cambiato": 1}', encoding="utf-8"),
])
def test_impronte_in_blocco_uguali_a_quelle_singole(studio, modifica):
    modifica(studio)
    blocco = _in_blocco(studio)
    assert blocco == {f: _singola(studio, f) for f in ("F1", "F2", "F3", "F5", "MAI")}


def test_impronte_in_blocco_uguali_a_quelle_singole_con_l_archivio_pec(studio, tmp_path):
    """Con l'archivio PEC (con o senza trigger) le impronte in blocco restano uguali a quelle singole."""
    from dataclasses import replace

    pec_db = str(tmp_path / "pec_audit.sqlite")
    _esegui(pec_db, "CREATE TABLE pec_messages (id TEXT PRIMARY KEY, linked_fascicolo_id TEXT, subject TEXT)")
    studio.fonti = replace(studio.fonti, pec_db=pec_db)
    for giorno in (True, False):
        singole = {f: impronta_fonti.impronta(studio.fonti, f, generazione=0, versione=VERSIONE, dipende_dal_giorno=giorno)
                   for f in ("F1", "F2")}
        assert impronta_fonti.impronte(studio.fonti, {"F1": 0, "F2": 0}, versione=VERSIONE,
                                       dipende_dal_giorno=giorno) == singole
    prepara_database(pec_db, tabelle_senza_fascicolo=("pec_messages",), backup_dir=tmp_path / "backup", applica=True,
                     sole_tabelle_condivise=True)
    _esegui(pec_db, "INSERT INTO pec_messages VALUES ('M1','F1','x')")
    singole = {f: impronta_fonti.impronta(studio.fonti, f, generazione=0, versione=VERSIONE) for f in ("F1", "F2")}
    assert impronta_fonti.impronte(studio.fonti, {"F1": 0, "F2": 0}, versione=VERSIONE) == singole


def test_impronte_in_blocco_senza_trigger_vuote(tmp_path):
    vuoto = str(tmp_path / "vuoto.db")
    sqlite3.connect(vuoto).close()
    fonti = impronta_fonti.FontiTenant(studio_db=vuoto, registro_db=vuoto)
    assert impronta_fonti.impronte(fonti, {"F1": 0}, versione="x") == {}


def test_update_senza_variazioni_di_una_tabella_condivisa_non_invalida(studio):
    prima = _in_blocco(studio)
    _esegui(studio.studio_db, "UPDATE settings_config SET dati_json=dati_json")
    _esegui(studio.studio_db, "INSERT INTO email_mailbox_records VALUES ('m1','non_letto','{}')")
    dopo_inserimento = _in_blocco(studio)
    assert dopo_inserimento != prima  # un messaggio nuovo è una variazione
    _esegui(studio.studio_db, "UPDATE email_mailbox_records SET read_state='non_letto' WHERE message_key='m1'")
    assert _in_blocco(studio) == dopo_inserimento
    _esegui(studio.studio_db, "UPDATE email_mailbox_records SET read_state='letto' WHERE message_key='m1'")
    assert _in_blocco(studio) != dopo_inserimento


def test_ordine_recenti_termini_vicini_poi_gli_altri_senza_archiviati(studio):
    from web.services.pannelli_pronti_priorita import fascicoli_per_priorita

    adesso = datetime(2026, 11, 18, 10, tzinfo=ROMA)
    # F1 aperto di recente; F3 scadenza aperta il 25/11, F5 udienza il 21/11; F2 udienza passata, scadenza
    # completata; F4 archiviato; la scadenza di F1 è già passata.
    assert fascicoli_per_priorita(studio.fonti, ["F1", "F4"], adesso=adesso) == ["F1", "F5", "F3", "F2"]
    assert fascicoli_per_priorita(studio.fonti, [], adesso=adesso) == ["F5", "F3", "F2", "F1"]


def _profilo(studio, profilo="p1"):
    studio.archivio.registra_richiesta(chiave_voce="seme", fascicolo_id="F1", pannello="quadro",
                                       percorso="/api/v1/ui/fascicoli/F1/quadro", profilo=profilo,
                                       sessione={"user_id": "u1"}, servito=True)


def _salva(studio, voce, impronta):
    from web.services.pannelli_pronti_runtime import _chiave_pannello

    parametri = voce.percorso.partition("?")[2]
    studio.archivio.salva(chiave_voce=_chiave_pannello(voce.fascicolo_id, voce.pannello, parametri, voce.profilo),
                          fascicolo_id=voce.fascicolo_id, pannello=voce.pannello, percorso=voce.percorso,
                          profilo=voce.profilo, impronta=impronta, stato=200, tipo="application/json",
                          corpo=b'{"ok": true}', durata_ms=1)


def _attesa(studio, voce):
    """L'impronta che ``servi`` salva per il pannello: con o senza il giorno e con la revisione del suo motore."""
    from web.services.pannelli_pronti_catalogo import PANNELLI_SENZA_DATA_DI_CONSULTAZIONE, impronta_del_pannello

    generazioni = studio.archivio.generazioni()
    fonti = impronta_fonti.impronte(studio.fonti, {voce.fascicolo_id: generazioni.get(voce.fascicolo_id, 0)},
                                    versione=VERSIONE,
                                    dipende_dal_giorno=voce.pannello not in PANNELLI_SENZA_DATA_DI_CONSULTAZIONE)
    return impronta_del_pannello(voce.pannello, fonti[voce.fascicolo_id])


def _prepara_tutto(studio):
    from web.services.pannelli_pronti_sfondo import copertura

    giri = 0
    while voci := copertura(studio.archivio, studio.fonti, limite=7):
        giri += 1
        assert giri < 200
        for voce in voci:
            _salva(studio, voce, _attesa(studio, voce))
    return giri


def test_copertura_senza_profili_attivi_non_prepara(studio):
    from web.services.pannelli_pronti_sfondo import copertura

    assert copertura(studio.archivio, studio.fonti) == []


def test_copertura_prepara_tutti_i_fascicoli_non_archiviati_e_riprende(studio):
    from web.services.pannelli_pronti_catalogo import PANNELLI, PRIMA_APERTURA
    from web.services.pannelli_pronti_sfondo import copertura

    _profilo(studio)
    primo_lotto = copertura(studio.archivio, studio.fonti, limite=200)
    nomi_prima = {p.nome for p in PRIMA_APERTURA}
    assert {v.fascicolo_id for v in primo_lotto} == {"F1", "F2", "F3", "F5"}
    assert all(v.motivo == "copertura" for v in primo_lotto)
    # Prima la prima apertura di tutti i fascicoli, poi gli altri pannelli.
    posizioni = [v.pannello in nomi_prima for v in primo_lotto]
    assert posizioni == sorted(posizioni, reverse=True)
    assert len(primo_lotto) == 4 * len([p for p in PANNELLI if p.percorso])
    # La forma canonica con parametri (la scheda della guida) si prepara come la chiede l'interfaccia.
    assert {v.percorso for v in primo_lotto if v.pannello == "guida-pratica" and v.fascicolo_id == "F1"} == {
        "/api/v1/ui/fascicoli/F1/guida-pratica?vista=scheda"}

    # Interruzione dopo un lotto: il giro successivo riprende dal primo pannello non pronto.
    for voce in primo_lotto[:5]:
        _salva(studio, voce, _attesa(studio, voce))
    assert copertura(studio.archivio, studio.fonti, limite=1)[0] == primo_lotto[5]
    _prepara_tutto(studio)
    assert copertura(studio.archivio, studio.fonti) == []


def test_al_cambio_di_una_fonte_si_ricalcola_solo_quel_fascicolo_per_primo(studio):
    from web.services.pannelli_pronti_sfondo import copertura

    _profilo(studio)
    _prepara_tutto(studio)
    _esegui(studio.studio_db, "INSERT INTO parcelle VALUES ('P1','F3','{}')")
    voci = copertura(studio.archivio, studio.fonti, limite=500)
    assert voci and {v.fascicolo_id for v in voci} == {"F3"}
    assert all(v.motivo == "fonti cambiate" for v in voci)


def test_una_fonte_condivisa_rimette_in_coda_tutti_ma_prima_quelli_gia_pronti(studio):
    from web.services.pannelli_pronti_sfondo import copertura

    _profilo(studio)
    _prepara_tutto(studio)
    _esegui(studio.studio_db, "UPDATE settings_config SET dati_json='{\"nome\":\"Nuovo\"}'")
    voci = copertura(studio.archivio, studio.fonti, limite=500)
    assert {v.fascicolo_id for v in voci} == {"F1", "F2", "F3", "F5"}


def test_calcolo_fallito_non_si_ritenta_con_le_stesse_fonti(studio):
    from web.services.pannelli_pronti_runtime import _chiave_pannello
    from web.services.pannelli_pronti_sfondo import copertura

    _profilo(studio)
    voce = copertura(studio.archivio, studio.fonti, limite=1)[0]
    attuale = _attesa(studio, voce)
    studio.archivio.segna_tentativo(chiave_voce=_chiave_pannello(voce.fascicolo_id, voce.pannello, "", voce.profilo),
                                    fascicolo_id=voce.fascicolo_id, pannello=voce.pannello, percorso=voce.percorso,
                                    profilo=voce.profilo, impronta=attuale, motivo="risposta 500")
    assert copertura(studio.archivio, studio.fonti, limite=1)[0] != voce
    _esegui(studio.studio_db, "INSERT INTO scadenze VALUES ('S8',?, 'APERTO','2026-12-02','{}')", (voce.fascicolo_id,))
    assert voce.pannello in {v.pannello for v in copertura(studio.archivio, studio.fonti, limite=500)
                             if v.fascicolo_id == voce.fascicolo_id}


def test_varianti_chieste_dall_interfaccia_si_preparano_cosi(studio):
    from web.services.pannelli_pronti_sfondo import copertura

    _profilo(studio)
    for fid in ("F1", "F3"):
        studio.archivio.registra_richiesta(chiave_voce=f"det-{fid}", fascicolo_id=fid, pannello="dettaglio",
                                           percorso=f"/api/v1/ui/fascicoli/{fid}?include=lettura", profilo="p1",
                                           sessione={"user_id": "u1"}, servito=True)
    # Un parametro proprio di un solo fascicolo (il cliente) non si applica agli altri.
    studio.archivio.registra_richiesta(chiave_voce="red", fascicolo_id="F1", pannello="redazione-atti-contesto",
                                       percorso="/api/v1/ui/redazione-atti/fascicoli/F1/contesto?id_cliente=K1",
                                       profilo="p1", sessione={"user_id": "u1"}, servito=True)
    voci = copertura(studio.archivio, studio.fonti, limite=500)
    assert {v.percorso for v in voci if v.fascicolo_id == "F2" and v.pannello == "dettaglio"} == {
        "/api/v1/ui/fascicoli/F2?include=lettura"}
    assert {v.percorso for v in voci if v.fascicolo_id == "F2" and v.pannello == "redazione-atti-contesto"} == {
        "/api/v1/ui/redazione-atti/fascicoli/F2/contesto"}


def test_ricalcolo_si_ferma_se_l_avvocato_aspetta_un_pannello(studio):
    from web.services.pannelli_pronti_sfondo import DaRicalcolare, ricalcola

    chiamate = []

    class Cliente:
        def session_transaction(self):
            raise AssertionError("non deve calcolare")

    app = SimpleNamespace(test_client=lambda: Cliente())
    voci = [DaRicalcolare("F1", "quadro", "/q", "p1", "copertura")]
    esito = ricalcola(app, studio.archivio, voci, interrompi=lambda: chiamate.append(1) or True)
    assert esito == {"calcolati": 0, "non_salvati": 0, "errori": 0} and chiamate == [1]


def test_dettaglio_alla_prima_apertura_senza_la_lettura_incorporata(monkeypatch):
    """La Lettura viaggia nel dettaglio solo se chiesta: la sezione chiusa la chiede dal pronto quando si apre."""
    import json as _json

    from flask import Flask

    from web.services import pannelli_pronti_runtime as runtime
    from web.services import riscontri_processuali_runtime as riscontri
    from web.services import valore_causa_archivio
    from web.services.pannelli_pronti_catalogo import PANNELLI

    dettaglio = next(p for p in PANNELLI if p.nome == "dettaglio")
    lettura = {"intestazione": {"fonte_valore_causa": {}}, "cronologia": ["x" * 1000]}
    monkeypatch.setattr(riscontri, "lettura_consultiva", lambda _fid: dict(lettura))
    monkeypatch.setattr(riscontri, "aggiorna_stato_presidi", lambda *_a: None)
    monkeypatch.setattr(valore_causa_archivio, "valore_iscrizione_corrente", lambda _fid, **_k: {})
    corpo = _json.dumps({"fascicolo": {"id": "F1"}, "profile": []}).encode()
    app = Flask("prova")
    with app.test_request_context("/api/v1/ui/fascicoli/F1?confirm_revision=1"):
        assert "initialLettura" not in _json.loads(runtime._ricomponi(dettaglio, corpo, "F1"))
    with app.test_request_context("/api/v1/ui/fascicoli/F1?include=lettura"):
        assert _json.loads(runtime._ricomponi(dettaglio, corpo, "F1"))["initialLettura"] == lettura
    with app.test_request_context("/api/v1/ui/fascicoli/F1?include=all"):
        assert _json.loads(runtime._ricomponi(dettaglio, corpo, "F1"))["initialLettura"] == lettura


def test_controlli_in_sfondo_usano_solo_indici_senza_leggere_i_payload(studio):
    """Le colonne lette dai controlli stanno dopo ``corpo``: con gli indici di copertura i payload non si leggono."""
    _profilo(studio)
    studio.archivio.prepara_indici()
    conn = sqlite3.connect(studio.archivio.percorso)
    try:
        piani = {
            "stati": "SELECT chiave, fascicolo_id, impronta, tentata, pannello FROM pannelli",
            "varianti": "SELECT pannello, percorso, SUM(richieste) FROM pannelli WHERE profilo='p1' AND richieste>0 "
                        "GROUP BY 1,2 HAVING COUNT(DISTINCT fascicolo_id)>1",
        }
        for nome, sql in piani.items():
            piano = " ".join(str(r[-1]) for r in conn.execute("EXPLAIN QUERY PLAN " + sql))
            assert "COVERING INDEX" in piano, (nome, piano)
    finally:
        conn.close()


def test_ordine_di_calcolo_rispetta_le_dipendenze_del_catalogo():
    from web.services.pannelli_pronti_catalogo import PANNELLI
    from web.services.pannelli_pronti_sfondo import _ORDINE

    for pannello in PANNELLI:
        for fonte in pannello.dipende_da:
            assert _ORDINE[fonte] < _ORDINE[pannello.nome], (fonte, pannello.nome)
