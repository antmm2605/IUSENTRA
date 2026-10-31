"""Termine lungo art. 327 c.p.c.: decorre dal deposito della sentenza, mai dalla comunicazione (31/10/2026)."""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from types import SimpleNamespace

import pytest

from pct.scadenziario import GestioneScadenziario, StatoTermine
from pct.termine_lungo_sentenza import (
    completa_termini_lunghi,
    data_pubblicazione,
    data_pubblicazione_da_fatti,
    numero_sentenza,
    proponi_termine_lungo,
)
from web.services import termine_lungo_runtime
from web.services.termine_lungo_runtime import comunicazioni_deposito_sentenza, completa_termini_lunghi_runtime

OGGI = date(2026, 4, 10)


@pytest.fixture
def scadenziario(tmp_path):
    return GestioneScadenziario(str(tmp_path / "scadenze.json"))


def _fatto(valore, contesto, *, campo="deposito", categoria="data", verifica="plausibile"):
    return SimpleNamespace(categoria=categoria, campo=campo, valore=valore, contesto=contesto, verifica=verifica)


@pytest.mark.parametrize("testo, atteso", [
    ("Si comunica che in data 02/03/2026 è stata depositata la sentenza n. 12/2026.", date(2026, 3, 2)),
    ("Comunicazione di cancelleria. Data deposito: 02/03/2026.", date(2026, 3, 2)),
    ("Sentenza n. 12/2026 pubbl. il 02/03/2026 RG n. 456/2025", date(2026, 3, 2)),
    ("Sentenza depositata il 31/02/2026", None),
    ("Comunicazione di deposito sentenza.", None),
    ("Sentenza pubblicata il 02/03/2026; sentenza pubblicata il 05/03/2026", None),
])
def test_data_di_deposito_dalla_comunicazione(testo, atteso):
    assert data_pubblicazione(testo) == atteso


def test_negli_atti_allegati_vale_solo_la_data_legata_alla_sentenza():
    atto = "Il ricorso depositato il 10/01/2025 ... Sentenza n. 12/2026 pubbl. il 02/03/2026"
    assert data_pubblicazione(atto, comunicazione=False) == date(2026, 3, 2)
    assert data_pubblicazione("Il ricorso depositato il 10/01/2025", comunicazione=False) is None


def test_numero_della_sentenza():
    assert numero_sentenza("Deposito della sentenza n. 12 / 2026") == "12/2026"
    assert numero_sentenza("Comunicazione generica") == ""


def test_data_dai_documenti_del_fascicolo_solo_se_univoca():
    fatti = [
        _fatto("2026-03-02", "Sentenza n. 12/2026 pubbl. il 02/03/2026", campo="provvedimento"),
        _fatto("2025-06-10", "Sentenza n. 99/2025 depositata il 10/06/2025 (primo grado)"),
        _fatto("2026-05-01", "Udienza del 01/05/2026", campo="udienza"),
        _fatto("2026-01-01", "Sentenza depositata il 01/01/2026", verifica="respinto"),
        _fatto("non-data", "Sentenza depositata"),
        _fatto("2026-02-02", "Sentenza depositata", categoria="importo"),
        _fatto("2026-02-03", "ricorso depositato il 03/02/2026"),
    ]
    assert data_pubblicazione_da_fatti(fatti, numero="12/2026") == date(2026, 3, 2)
    # Due sentenze, nessun numero: non si sceglie.
    assert data_pubblicazione_da_fatti(fatti) is None
    # Numero non trovato fra i fatti: si guardano tutte, ancora ambigue.
    assert data_pubblicazione_da_fatti(fatti, numero="7/2026") is None
    assert data_pubblicazione_da_fatti(fatti[:1]) == date(2026, 3, 2)


def test_bozza_dal_deposito_con_feriale_e_senza_doppioni(scadenziario):
    creata = proponi_termine_lungo(
        scadenziario, fascicolo_id="F-1", comunicazione_id="PEC-1", testo="Sentenza n. 12/2026 del Tribunale",
        pubblicazione=date(2026, 3, 2), lavoro=False, oggi=OGGI, origine="prova",
    )
    assert creata is True
    (scadenza,) = scadenziario.tutte(solo_aperte=False)
    # 02/03 + 6 mesi = 02/09, + 31 giorni di agosto = sabato 03/10 → lunedì 05/10 (art. 155 c.p.c.).
    assert scadenza.data_scadenza == "2026-10-05" and scadenza.stato == StatoTermine.BOZZA
    assert scadenza.titolo.startswith("Appello") and "12/2026" in scadenza.titolo
    assert "SENTENZA_327:PEC-1" in scadenza.note and scadenza.data_decorrenza == "2026-03-02"
    assert proponi_termine_lungo(
        scadenziario, fascicolo_id="F-1", comunicazione_id="PEC-1", testo="", pubblicazione=date(2026, 3, 2),
        lavoro=False, oggi=OGGI, origine="prova",
    ) is False


def test_lavoro_senza_feriale_corte_appello_e_termine_scaduto(scadenziario):
    assert proponi_termine_lungo(
        scadenziario, fascicolo_id="F-2", comunicazione_id="PEC-2", testo="Corte d'Appello di Roma, sezione lavoro",
        pubblicazione=date(2026, 3, 2), lavoro=True, oggi=OGGI, origine="prova",
    ) is True
    (scadenza,) = scadenziario.tutte(solo_aperte=False, id_fascicolo="F-2")
    assert scadenza.data_scadenza == "2026-09-02" and scadenza.titolo.startswith("Ricorso per cassazione")
    assert proponi_termine_lungo(
        scadenziario, fascicolo_id="F-3", comunicazione_id="PEC-3", testo="", pubblicazione=date(2025, 1, 2),
        lavoro=False, oggi=OGGI, origine="prova",
    ) is False


def test_giro_dalla_comunicazione_o_dai_documenti_del_fascicolo(scadenziario):
    fatti = {"F-2": [_fatto("2026-03-15", "Sentenza n. 7/2026 depositata il 15/03/2026")]}
    comunicazioni = [
        {"id": "PEC-1", "fascicolo_id": "F-1", "testo": "Sentenza n. 12/2026 depositata il 02/03/2026"},
        {"id": "PEC-2", "fascicolo_id": "F-2", "testo": "Deposito della sentenza n. 7/2026"},
        {"id": "PEC-3", "fascicolo_id": "F-3", "testo": "Deposito sentenza"},
        {"id": "PEC-4", "fascicolo_id": "", "testo": "Sentenza depositata il 02/03/2026"},
    ]
    esito = completa_termini_lunghi(comunicazioni, scadenziario, lambda fid: fatti.get(fid, []), oggi=OGGI)
    assert esito == {"proposte": 2, "senza_data": 1}
    dal_fascicolo = scadenziario.tutte(solo_aperte=False, id_fascicolo="F-2")[0]
    # 15/03 + 6 mesi = 15/09, + 31 giorni di agosto = venerdì 16/10.
    assert dal_fascicolo.data_scadenza == "2026-10-16" and "documenti del fascicolo" in dal_fascicolo.note


def _db_pec(path, *, evento="deposito_sentenza", fascicolo="F-1", ricevuta="2026-03-03T10:00:00"):
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE pec_messages (id TEXT, tenant_id TEXT, linked_fascicolo_id TEXT, metadata_json TEXT, received_at TEXT);"
        "CREATE TABLE pec_parsed_versions (message_id TEXT, version INTEGER, parsed_json TEXT);"
        "CREATE TABLE pec_legal_events (message_id TEXT, tenant_id TEXT, primary_event TEXT);"
    )
    parsed = {"headers": {"subject": "Deposito sentenza - Sezione Lavoro"},
              "body": {"text": "Sentenza n. 12/2026 depositata il 02/03/2026"}}
    conn.execute("INSERT INTO pec_messages VALUES ('PEC-1','t',?,?,?)",
                 (fascicolo, json.dumps({"headers": {"subject": "x"}}), ricevuta))
    conn.execute("INSERT INTO pec_parsed_versions VALUES ('PEC-1',1,?)", (json.dumps(parsed),))
    conn.execute("INSERT INTO pec_legal_events VALUES ('PEC-1','t',?)", (evento,))
    conn.execute("INSERT INTO pec_messages VALUES ('PEC-2','t','F-9','{\"headers\": {\"subject\": \"Deposito\"}}',?)",
                 (ricevuta,))
    conn.execute("INSERT INTO pec_parsed_versions VALUES ('PEC-2',1,'non json')")
    conn.execute("INSERT INTO pec_legal_events VALUES ('PEC-2','t',?)", (evento,))
    conn.commit()
    conn.close()


def test_runtime_legge_le_comunicazioni_in_sola_lettura(tmp_path, scadenziario, monkeypatch):
    db = tmp_path / "pec_audit.sqlite"
    _db_pec(db)
    comunicazioni = comunicazioni_deposito_sentenza(db, oggi=OGGI)
    assert [c["id"] for c in comunicazioni] == ["PEC-1", "PEC-2"]
    assert comunicazioni[0]["lavoro"] is True and comunicazioni[1]["testo"].startswith("Deposito")
    monkeypatch.setattr(termine_lungo_runtime, "_fatti_del_fascicolo", lambda fid: [])
    assert completa_termini_lunghi_runtime(db, scadenziario, oggi=OGGI) == {"proposte": 1, "senza_data": 1}
    assert scadenziario.tutte(solo_aperte=False)[0].data_scadenza == "2026-09-02"
    # Fuori finestra, altri eventi o archivio assente: nessuna proposta.
    vecchio = tmp_path / "vecchio.sqlite"
    _db_pec(vecchio, ricevuta="2025-01-01T10:00:00")
    assert comunicazioni_deposito_sentenza(vecchio, oggi=OGGI) == []
    assert completa_termini_lunghi_runtime(None, scadenziario, oggi=OGGI) == {"proposte": 0, "senza_data": 0}
    assert completa_termini_lunghi_runtime(tmp_path / "manca.sqlite", scadenziario, oggi=OGGI)["proposte"] == 0
    rotto = tmp_path / "rotto.sqlite"
    rotto.write_text("non è sqlite")
    assert "errore" in completa_termini_lunghi_runtime(rotto, scadenziario, oggi=OGGI)


def test_fatti_del_fascicolo_dall_archivio_o_vuoti(monkeypatch):
    from web.services import archivio_letture_runtime

    monkeypatch.setattr(archivio_letture_runtime, "fatti_fascicolo", lambda fascicolo, **filtri: [fascicolo.id, filtri])
    assert termine_lungo_runtime._fatti_del_fascicolo("F-1") == ["F-1", {"categoria": "data"}]

    def guasto(fascicolo, **filtri):
        raise RuntimeError("archivio non disponibile")

    monkeypatch.setattr(archivio_letture_runtime, "fatti_fascicolo", guasto)
    assert termine_lungo_runtime._fatti_del_fascicolo("F-1") == []


def test_il_numero_della_sentenza_con_abbreviazione_non_nasconde_la_data_di_pubblicazione():
    from datetime import date

    from pct.termine_lungo_sentenza import data_pubblicazione

    assert data_pubblicazione("Sentenza n. 700/2026 pubblicata il 02/10/2026", comunicazione=False) == date(2026, 10, 2)
    assert data_pubblicazione("sentenza nr. 12/2025 depositata in cancelleria il 3.4.2025", comunicazione=False) == date(2025, 4, 3)
    assert data_pubblicazione("Sentenza. Ricorso depositato il 01/01/2026", comunicazione=False) is None
