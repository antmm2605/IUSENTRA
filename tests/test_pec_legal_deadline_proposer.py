from __future__ import annotations

from pct.pec_legal_deadline_proposer import load_ruleset, propose_legal_deadline


def test_127_ter_cinque_giorni_dalla_comunicazione():
    r = propose_legal_deadline("Si dispone la trattazione scritta ex art. 127-ter c.p.c.", dies_a_quo_date="2026-03-02")
    assert r["ok"] is True
    assert r["template_code"] == "CIV_OPPOSIZIONE_127_TER"
    assert r["direzione"] == "forward"
    assert r["deadline"] >= "2026-03-07"  # 5 giorni dal 02/03, con eventuale roll a giorno utile
    assert r["human_review_required"] is True


def test_sentenza_a_verbale_429_non_diventa_opposizione_127_ter():
    r = propose_legal_deadline(
        "SENTENZA A VERBALE (art. 127 ter cpc). Il Giudice decide la causa con sentenza "
        "a norma degli artt. 429 e 127ter cpc. Il Giudice, definitivamente decidendo, "
        "condanna il Ministero alle spese con distrazione in favore del procuratore antistatario.",
        dies_a_quo_date="2026-07-16",
    )
    assert r["ok"] is False
    assert r["template_code"] == ""
    assert "notifica sentenza" in r["azione"].lower()
    assert "127-ter" in r["reason"]


def test_171_ter_a_ritroso_prima_dell_udienza():
    r = propose_legal_deadline("Deposito seconda memoria ex art. 171-ter n. 2", dies_a_quo_date="2026-04-20")
    assert r["ok"] is True
    assert r["direzione"] == "backward"
    assert r["deadline"] < "2026-04-20"  # a ritroso, prima dell'udienza


def test_380_bis_quaranta_giorni():
    r = propose_legal_deadline("Proposta di definizione ex art. 380-bis: richiesta di decisione", dies_a_quo_date="2026-03-02")
    assert r["ok"] is True
    assert r["durata"] == 40
    assert r["norma"].startswith("Art. 380-bis")


def test_644_decreto_ingiuntivo_notifica():
    r = propose_legal_deadline("Deposito del decreto ingiuntivo: notificare il decreto", dies_a_quo_date="2026-03-02")
    assert r["ok"] is True
    assert r["template_code"] == "CIV_DI_NOTIFICA_644"
    assert r["durata"] == 60


def test_deposito_sentenza_non_fa_decorrere_termine_breve():
    # La comunicazione di cancelleria non fa decorrere alcun termine (né art. 325, né art. 327):
    # senza la data di deposito nel testo resta un promemoria senza data.
    r = propose_legal_deadline(
        "Comunicazione di deposito sentenza. Termine breve per impugnare.",
        dies_a_quo_date="2026-03-02",
        event_type="deposito_sentenza",
    )
    assert r["ok"] is False and r["human_review_required"] is True
    assert r["norma"] == "Art. 327 c.p.c." and "deadline" not in r
    assert "data di deposito" in r["reason"] and "non dalla comunicazione" in r["reason"]


def test_termine_lungo_dalla_data_di_deposito_non_dalla_comunicazione():
    # 02/03 + 6 mesi = 02/09, + 31 giorni di agosto = sabato 03/10 → lunedì 05/10 (art. 155 c.p.c.).
    for testo in (
        "Si comunica che in data 02/03/2026 è stata depositata la sentenza n. 12/2026.",
        "Comunicazione di cancelleria. Data deposito: 02/03/2026. Sentenza n. 12/2026.",
        "Sentenza pubblicata il 02/03/2026",
    ):
        r = propose_legal_deadline(testo, dies_a_quo_date="2026-04-20", event_type="deposito_sentenza")
        assert r["ok"] is True and r["dies_a_quo_date"] == "2026-03-02", testo
        assert r["deadline"] == "2026-10-05" and "breve" in r["explanation"]


def test_termine_lungo_dalla_data_di_deposito_letta_e_senza_feriale_nel_lavoro():
    letta = propose_legal_deadline("Sentenza n. 45/2026 depositata il 15/03/2026", dies_a_quo_date="2026-03-20",
                                   event_type="deposito_sentenza")
    assert letta["dies_a_quo_date"] == "2026-03-15" and letta["deadline"] == "2026-10-16"
    lavoro = propose_legal_deadline("Sezione lavoro: sentenza depositata il 15/03/2026", dies_a_quo_date="2026-03-20",
                                    event_type="deposito_sentenza")
    assert lavoro["deadline"] == "2026-09-15"
    impossibile = propose_legal_deadline("sentenza depositata il 31/02/2026", dies_a_quo_date="",
                                         event_type="deposito_sentenza")
    assert impossibile is None


def test_assegna_termine_senza_durata_richiede_revisione():
    r = propose_legal_deadline("Il giudice assegna termine per il deposito delle note.", dies_a_quo_date="2026-03-02")
    assert r["ok"] is False
    assert r["human_review_required"] is True


def test_non_riconosciuto_ritorna_none():
    assert propose_legal_deadline("Comunicazione generica senza termini.", dies_a_quo_date="2026-03-02") is None


def test_dies_a_quo_mancante_richiede_revisione():
    r = propose_legal_deadline("Reclamo cautelare ex art. 669-terdecies", dies_a_quo_date="")
    assert r["ok"] is False
    assert r["human_review_required"] is True


def test_ruleset_versionato_ha_fonti():
    rules = load_ruleset()
    assert rules["ambito"] == "civile"
    assert "art_133_cpc" in rules["fonti"]
    assert any(rule["template_code"] == "CIV_MEMORIA_171_TER_2" for rule in rules["regole"])
