from __future__ import annotations

from pct.pec_legal_deadline_proposer import load_ruleset, propose_legal_deadline


def test_127_ter_cinque_giorni_dalla_comunicazione():
    r = propose_legal_deadline("Si dispone la trattazione scritta ex art. 127-ter c.p.c.", dies_a_quo_date="2026-03-02")
    assert r["ok"] is True
    assert r["template_code"] == "CIV_OPPOSIZIONE_127_TER"
    assert r["direzione"] == "forward"
    assert r["deadline"] >= "2026-03-07"  # 5 giorni dal 02/03, con eventuale roll a giorno utile
    assert r["human_review_required"] is True


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
    # Regola art. 133/325: dalla sola comunicazione niente termine breve automatico.
    r = propose_legal_deadline(
        "Comunicazione di deposito sentenza. Termine breve per impugnare.",
        dies_a_quo_date="2026-03-02",
        event_type="deposito_sentenza",
    )
    assert r["ok"] is False
    assert r["human_review_required"] is True
    assert "325" in r["reason"] or "133" in r["reason"] or "breve" in r["reason"]


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
