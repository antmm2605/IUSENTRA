"""Precedenti di notifica dello studio come fonte delle proposte (art. 3-bis L. 53/1994)."""

from __future__ import annotations

import json
import sqlite3
from datetime import date

from pct.precedenti_notifica.categorie import (
    AVVOCATURA_STATO,
    SEDE_ISTITUTO_SCOLASTICO,
    categoria_controparte,
    domicilio_da_indirizzo,
    tipo_atto,
)
from pct.precedenti_notifica.regola import AUTOMATICA, CONFLITTO, DA_VERIFICARE, NESSUNO, Precedente, proposta
from web.services import precedenti_notifica_runtime as rt

OGGI = date(2026, 11, 3)
STATO = "presso Avvocatura distrettuale dello Stato di Bari"
SEDE = "presso la sede, in persona del legale rappresentante"


def _p(n: int, domicilio: str, *, consegnata: bool = True, data: str = "2026-05-01", cat: str = "amministrazione_statale") -> Precedente:
    return Precedente(f"F{n}", f"M{n}", data, "ricorso", cat, domicilio, consegnata)


def test_categorie_senza_nomi_ne_indirizzi():
    assert categoria_controparte("Istituto Comprensivo Statale «G. Verdi»") == "istituto_scolastico_statale"
    assert categoria_controparte("Ministero dell'Istruzione e del Merito") == "amministrazione_statale"
    assert categoria_controparte("Scuola paritaria Alfa s.r.l.") == "parte_privata"
    assert domicilio_da_indirizzo("ads.ba@mailcert.avvocaturastato.it") == AVVOCATURA_STATO
    assert domicilio_da_indirizzo("baic80000@pec.istruzione.it") == SEDE_ISTITUTO_SCOLASTICO
    assert tipo_atto(["relata.pdf.p7m", "Ricorso_414.pdf.p7m"]) == "ricorso"


def test_tre_precedenti_concordi_e_consegnati_danno_la_proposta():
    esito = proposta([_p(i, AVVOCATURA_STATO) for i in range(3)], tipo_atto="ricorso",
                     categoria_controparte="amministrazione_statale", presso_normativo=STATO, oggi=OGGI)
    assert esito["stato"] == AUTOMATICA
    assert esito["fonte"] == "Come nelle 3 notifiche precedenti dello studio"
    assert esito["registro_indirizzo"] == "registro_ppaa"  # indirizzo dal pubblico elenco, mai dal precedente
    assert "art. 3-bis" in esito["avvertenza"]
    assert all("indirizzo" not in p for p in esito["precedenti"])


def test_sotto_il_minimo_o_con_discordante_recente_resta_da_verificare():
    due = proposta([_p(1, AVVOCATURA_STATO), _p(2, AVVOCATURA_STATO)], tipo_atto="ricorso",
                   categoria_controparte="amministrazione_statale", presso_normativo=STATO, oggi=OGGI)
    assert due["stato"] == DA_VERIFICARE
    discorde = [_p(i, AVVOCATURA_STATO) for i in range(4)] + [_p(9, "sede_ministero")]
    assert proposta(discorde, tipo_atto="ricorso", categoria_controparte="amministrazione_statale",
                    presso_normativo=STATO, oggi=OGGI)["stato"] in {DA_VERIFICARE, CONFLITTO}


def test_mancate_consegne_non_contano_e_il_fascicolo_corrente_si_esclude():
    precedenti = [_p(i, AVVOCATURA_STATO, consegnata=False) for i in range(5)] + [_p(7, AVVOCATURA_STATO)]
    esito = proposta(precedenti, tipo_atto="ricorso", categoria_controparte="amministrazione_statale",
                     presso_normativo=STATO, fascicolo_id="F7", oggi=OGGI)
    assert esito["stato"] == NESSUNO
    assert esito["mancate_consegne"] == 5


def test_la_norma_prevale_sui_precedenti_e_la_differenza_si_segnala():
    scuole = [_p(i, AVVOCATURA_STATO, cat="istituto_scolastico_statale") for i in range(6)]
    esito = proposta(scuole, tipo_atto="ricorso", categoria_controparte="istituto_scolastico_statale",
                     presso_normativo=SEDE, oggi=OGGI)
    assert esito["stato"] == CONFLITTO
    assert "prevale la norma" in esito["motivo"]
    sede = [_p(i, SEDE_ISTITUTO_SCOLASTICO, cat="istituto_scolastico_statale") for i in range(3)]
    assert proposta(sede, tipo_atto="ricorso", categoria_controparte="istituto_scolastico_statale",
                    presso_normativo=SEDE, oggi=OGGI)["stato"] == AUTOMATICA


def _db(percorso):
    conn = sqlite3.connect(percorso)
    conn.executescript("CREATE TABLE pec_messages (id TEXT, folder TEXT, linked_fascicolo_id TEXT, received_at TEXT, ingested_at TEXT);"
                       "CREATE TABLE pec_parsed_versions (message_id TEXT, version INTEGER, parsed_json TEXT);"
                       "CREATE TABLE pec_fascicolo_links (message_id TEXT, fascicolo_id TEXT, created_at TEXT);")
    oggetto = "notificazione ai sensi della legge n. 53 del 1994"
    invio = {"headers": {"subject": oggetto, "message_id": "<orig@x>"}, "pec_receipt": {}, "attachments": [{"filename": "ricorso.pdf.p7m"}]}
    conn.execute("INSERT INTO pec_messages VALUES ('S','Sent','F1','2026-04-01','2026-04-01')")
    conn.execute("INSERT INTO pec_parsed_versions VALUES ('S',1,?)", (json.dumps(invio),))
    invio["headers"]["to"] = ["a@mailcert.avvocaturastato.it"]
    conn.execute("UPDATE pec_parsed_versions SET parsed_json=? WHERE message_id='S'", (json.dumps(invio),))
    for n, tipo in ((1, "avvenuta-consegna"), (2, "errore-consegna")):
        ric = {"headers": {"subject": "CONSEGNA: " + oggetto}, "attachments": [],
               "pec_receipt": {"type": tipo, "original_message_id": "<orig@x>", "recipient_address": "a@mailcert.avvocaturastato.it" if n == 1 else ""}}
        conn.execute("INSERT INTO pec_messages VALUES (?,?,?,?,?)", (f"R{n}", "INBOX", "F1" if n == 1 else "", "2026-04-02", f"2026-04-0{n}"))
        conn.execute("INSERT INTO pec_fascicolo_links VALUES (?, 'F1', '2026-04-03')", (f"R{n}",))
        conn.execute("INSERT INTO pec_parsed_versions VALUES (?,1,?)", (f"R{n}", json.dumps(ric)))
    conn.commit()
    conn.close()


def test_runtime_legge_le_ricevute_e_non_ricalcola_se_nulla_cambia(tmp_path, monkeypatch):
    percorso = tmp_path / "pec_audit.sqlite"
    _db(percorso)
    controparti = {"F1": "Ministero dell'Istruzione"}
    precedenti = rt.precedenti_memorizzati(percorso, controparti)
    assert [(p.tipo_atto, p.domicilio, p.consegnata) for p in precedenti] == [("ricorso", AVVOCATURA_STATO, True), ("ricorso", AVVOCATURA_STATO, False)]
    assert (tmp_path / "precedenti_notifica.json").exists()
    monkeypatch.setattr(rt, "leggi_precedenti", lambda *a, **k: (_ for _ in ()).throw(AssertionError("ricalcolo")))
    assert rt.precedenti_memorizzati(percorso, controparti) == precedenti


def test_annota_proposte_aggiunge_la_proposta_al_destinatario():
    obblighi = [{"etichetta": "Ricorso ex art. 414 c.p.c.", "documento": "ricorso.pdf",
                 "destinatari": [{"nome": "Ministero dell'Istruzione", "presso": STATO, "fonte": "art. 11 R.D. 1611/1933"}]}]
    rt.annota_proposte(obblighi, [_p(i, AVVOCATURA_STATO) for i in range(3)], fascicolo_id="F99")
    assert obblighi[0]["destinatari"][0]["precedenti"]["stato"] == AUTOMATICA
