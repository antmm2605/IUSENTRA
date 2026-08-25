"""Payload React della pipeline CRM: colonne kanban, conflitti, statistiche."""

from __future__ import annotations

from pct.crm_intake import GestioneCrmIntake, STATI_LEAD
from web.services.react_crm_bridge import build_react_crm_payload


def _crm(tmp_path):
    crm = GestioneCrmIntake(db_path=str(tmp_path / "leads.json"))
    lead = crm.nuovo(denominazione="Rossi Mario", fonte="sito_studio", materia="lavoro", esigenza="Licenziamento")
    crm.verifica_conflitti(lead.id)
    vinto = crm.nuovo(denominazione="Alfa S.r.l.", fonte="passaparola")
    crm.verifica_conflitti(vinto.id)
    crm.cambia_stato(vinto.id, "VINTO")
    perso = crm.nuovo(denominazione="Verdi Anna", fonte="social")
    crm.cambia_stato(perso.id, "PERSO", motivo_perso="tariffa")
    return crm


def test_payload_colonne_e_statistiche(tmp_path):
    crm = _crm(tmp_path)
    payload = build_react_crm_payload(get_crm=lambda: crm)

    assert [c["stato"] for c in payload["columns"]] == list(STATI_LEAD)
    per_stato = {c["stato"]: c["count"] for c in payload["columns"]}
    assert per_stato["NUOVO"] == 1 and per_stato["VINTO"] == 1 and per_stato["PERSO"] == 1
    assert payload["summary"]["totale"] == 3
    assert payload["summary"]["tassoConversione"] == 0.5
    assert payload["contracts"]["mock_fallback"] is False
    assert payload["sourceOfTruth"] == "sqlite"


def test_scheda_lead_completa(tmp_path):
    crm = _crm(tmp_path)
    payload = build_react_crm_payload(get_crm=lambda: crm)
    nuovo = next(c for c in payload["columns"] if c["stato"] == "NUOVO")["leads"][0]

    assert nuovo["denominazione"] == "Rossi Mario"
    assert nuovo["fonteLabel"] == "Sito dello studio"
    assert nuovo["conflitto"]["verificato"] is True
    assert nuovo["conflitto"]["label"] == "Nessun riscontro"
    assert nuovo["actions"]["stato"].endswith("/stato")
    assert nuovo["actions"]["verificaConflitti"].endswith("/verifica-conflitti")
    assert nuovo["actions"]["aggiorna"].endswith("/aggiorna")


def test_lead_non_verificato_segnalato(tmp_path):
    crm = GestioneCrmIntake(db_path=str(tmp_path / "leads.json"))
    crm.nuovo(denominazione="Bianchi Luca")
    payload = build_react_crm_payload(get_crm=lambda: crm)
    lead = payload["columns"][0]["leads"][0]
    assert lead["conflitto"]["verificato"] is False
    assert lead["conflitto"]["label"] == "Verifica da eseguire"
    assert "art" in payload["fonteDeontologica"] or "CDF" in payload["fonteDeontologica"]


def test_payload_non_espone_contatto_protetto_a_utente_non_autorizzato(tmp_path):
    crm = GestioneCrmIntake(db_path=str(tmp_path / "leads.json"))
    lead = crm.nuovo(denominazione="Contatto protetto")
    crm.crea_barriera_riservatezza(
        lead.id,
        motivazione="Trattativa riservata.",
        utenti_autorizzati=["avv.autorizzato"],
        operatore="avv.responsabile",
    )

    hidden = build_react_crm_payload(get_crm=lambda: crm, operatore="avv.estraneo")
    visible = build_react_crm_payload(
        get_crm=lambda: crm,
        operatore="avv.autorizzato",
        utenti_autorizzabili=[{"username": "avv.autorizzato", "label": "Avv. Autorizzato"}],
    )

    assert hidden["summary"]["totale"] == 0
    card = next(column for column in visible["columns"] if column["stato"] == "NUOVO")["leads"][0]
    assert card["barrieraRiservatezza"]["attiva"] is True
    assert card["barrieraRiservatezza"]["utentiAutorizzati"] == ["avv.autorizzato", "avv.responsabile"]
