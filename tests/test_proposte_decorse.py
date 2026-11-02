"""Proposte di scadenza mai confermate con il termine già decorso (pct.proposte_decorse).

Base normativa: art. 127-ter c.p.c. (opposizione entro cinque giorni, note entro il termine
assegnato); artt. 152-155 c.p.c. (computo e scadenza dei termini, perentorietà).
Date naive e con fuso mescolate come chiede la regola sul fuso Europe/Rome.
"""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

from flask import Flask

from pct.ora_italiana import oggi_roma
from pct.proposte_decorse import (
    AZIONABILE,
    DA_VERIFICARE,
    MARCATORE_DA_VERIFICARE,
    MARCATORE_SUPERATA,
    SUPERATA,
    classifica,
    riconvalida_proposte_decorse,
)
from pct.scadenziario import GestioneScadenziario, StatoTermine, TipoTermine
from web.services.react_scadenziario_bridge import build_react_scadenziario_payload

OGGI = date(2026, 11, 2)


def _manager(tmp_path) -> GestioneScadenziario:
    return GestioneScadenziario(db_path=str(tmp_path / "scadenze.json"))


def _opposizione_127_ter(manager, data_scadenza: str):
    return manager.nuova(
        titolo="Opposizione alla trattazione scritta - RG 123/2026",
        tipo=TipoTermine.IMPUGNAZIONE,  # tipo predefinito delle proposte PEC
        data_scadenza=data_scadenza,
        note="PEC_TERMINE_PROPOSTO:msg-1:CIV_OPPOSIZIONE_127_TER",
        deadline_profile_code="CIV_OPPOSIZIONE_127_TER",
        perentorio=True,
        stato=StatoTermine.BOZZA,
    )


def _note_127_ter(manager, data_scadenza: str):
    return manager.nuova(
        titolo="Deposito note scritte ex art. 127-ter c.p.c.",
        tipo=TipoTermine.TERMINE_PERENTORIO,
        data_scadenza=data_scadenza,
        deadline_profile_code="NOTE_127_TER",
        perentorio=True,
        stato=StatoTermine.BOZZA,
    )


def _appello(manager, data_scadenza: str):
    return manager.nuova(
        titolo="Termine lungo per l'appello - RG 55/2025",
        tipo=TipoTermine.IMPUGNAZIONE,
        data_scadenza=data_scadenza,
        deadline_profile_code="CIV_APPELLO_LUNGO",
        perentorio=True,
        stato=StatoTermine.BOZZA,
    )


def _adempimento(manager, data_scadenza: str):
    return manager.nuova(
        titolo="Verifica data letta nella PEC",
        tipo=TipoTermine.ADEMPIMENTO,
        data_scadenza=data_scadenza,
        stato=StatoTermine.BOZZA,
    )


def test_127_ter_decorsa_si_chiude_come_superata_con_traccia(tmp_path):
    manager = _manager(tmp_path)
    opposizione = _opposizione_127_ter(manager, "2026-06-15")
    note = _note_127_ter(manager, "2026-09-10T09:30:00")  # naive: ora italiana

    esito = riconvalida_proposte_decorse(manager, oggi=OGGI)

    assert esito["superate"] == 2 and esito["da_verificare"] == 0
    for voce in (opposizione, note):
        chiusa = manager.get(voce.id)
        assert chiusa.stato == StatoTermine.ANNULLATO  # record conservato, non cancellato
        assert chiusa.completata_il
        assert f"{MARCATORE_SUPERATA}: Termine decorso senza conferma: proposta superata il 02/11/2026" in chiusa.note
        assert "art. 127-ter c.p.c." in chiusa.note
    assert manager.bozze() == []


def test_impugnazione_decorsa_resta_da_verificare_e_non_azionabile(tmp_path):
    manager = _manager(tmp_path)
    appello = _appello(manager, "2026-07-31T23:59:00+02:00")  # con fuso

    esito = riconvalida_proposte_decorse(manager, oggi=OGGI)

    voce = manager.get(appello.id)
    assert esito == {**esito, "superate": 0, "da_verificare": 1}
    assert voce.stato == StatoTermine.BOZZA
    assert MARCATORE_DA_VERIFICARE in voce.note and "decadenza" in voce.note
    assert classifica(voce, OGGI) == DA_VERIFICARE


def test_proposta_futura_resta_invariata(tmp_path):
    manager = _manager(tmp_path)
    futura = _opposizione_127_ter(manager, (OGGI + timedelta(days=3)).isoformat())
    oggi_stesso = _appello(manager, OGGI.isoformat())  # il termine scade a fine giornata (art. 155 c.p.c.)
    prima = {voce.id: voce.to_dict() for voce in manager.bozze()}

    esito = riconvalida_proposte_decorse(manager, oggi=OGGI)

    assert esito["superate"] == esito["da_verificare"] == 0
    assert {voce.id: voce.to_dict() for voce in manager.bozze()} == prima
    assert classifica(futura, OGGI) == classifica(oggi_stesso, OGGI) == AZIONABILE


def test_date_naive_e_con_fuso_si_leggono_in_ora_italiana():
    # 01/11 alle 23:30 UTC è già il 02/11 in Italia: il termine non è decorso.
    utc_a_cavallo = SimpleNamespace(stato="BOZZA", tipo="ADEMPIMENTO", titolo="Data", note="", perentorio=False,
                                    deadline_profile_code="", data_scadenza="2026-11-01T23:30:00+00:00", legal_due_at="")
    naive_ieri = SimpleNamespace(**{**vars(utc_a_cavallo), "data_scadenza": "2026-11-01T23:30:00"})
    assert classifica(utc_a_cavallo, OGGI) == AZIONABILE
    assert classifica(naive_ieri, OGGI) == SUPERATA


def test_riconvalida_idempotente_e_a_lotti(tmp_path):
    manager = _manager(tmp_path)
    for giorno in range(1, 4):
        _adempimento(manager, f"2026-09-0{giorno}")
    appello = _appello(manager, "2026-08-20")

    primo = riconvalida_proposte_decorse(manager, oggi=OGGI, limite=2)
    secondo = riconvalida_proposte_decorse(manager, oggi=OGGI, limite=2)
    terzo = riconvalida_proposte_decorse(manager, oggi=OGGI, limite=2)

    assert primo["superate"] + primo["da_verificare"] == 2 and primo["restanti"] == 2
    assert secondo["superate"] + secondo["da_verificare"] == 2 and secondo["restanti"] == 0
    assert terzo["superate"] == terzo["da_verificare"] == terzo["restanti"] == 0
    assert manager.get(appello.id).note.count(MARCATORE_DA_VERIFICARE) == 1
    assert [voce.id for voce in manager.bozze()] == [appello.id]


def test_payload_scadenziario_separa_i_termini_decorsi(tmp_path):
    manager = _manager(tmp_path)
    oggi = oggi_roma()
    futura = _adempimento(manager, (oggi + timedelta(days=10)).isoformat())
    _opposizione_127_ter(manager, (oggi - timedelta(days=60)).isoformat())
    appello = _appello(manager, (oggi - timedelta(days=30)).isoformat())

    payload = build_react_scadenziario_payload(
        gestione_scadenziario=manager,
        gestione_fascicoli=SimpleNamespace(get=lambda _id: None),
    )

    assert [row["id"] for row in payload["draftProposals"]] == [futura.id]
    gruppo = payload["expiredProposals"]
    assert gruppo["label"] == "Termini proposti già decorsi — verifica dell'avvocato"
    assert [row["id"] for row in gruppo["items"]] == [appello.id]
    assert gruppo["items"][0]["closeHref"] == f"/scadenziario/{appello.id}/scarta-proposta"
    assert gruppo["items"][0]["tone"] == "warning"


def test_payload_mostra_la_proposta_superata_nello_storico(tmp_path):
    manager = _manager(tmp_path)
    oggi = oggi_roma()
    voce = _opposizione_127_ter(manager, (oggi - timedelta(days=60)).isoformat())
    riconvalida_proposte_decorse(manager, oggi=oggi)

    payload = build_react_scadenziario_payload(
        gestione_scadenziario=manager,
        gestione_fascicoli=SimpleNamespace(get=lambda _id: None),
        query_args={"vista": "tutte"},
    )

    riga = next(row for row in payload["items"] if row["id"] == voce.id)
    assert riga["statusLabel"] == "Proposta superata"
    assert riga["reconciliationReason"].startswith("Termine decorso senza conferma")


def test_topbar_conta_solo_le_proposte_azionabili(monkeypatch):
    from web.services import topbar_operational as topbar

    oggi = oggi_roma()
    righe = [
        SimpleNamespace(id=nome, stato=StatoTermine.BOZZA, tipo=tipo, titolo=titolo, note="", perentorio=perentorio,
                        deadline_profile_code=codice, data_scadenza=giorno, legal_due_at="")
        for nome, tipo, titolo, perentorio, codice, giorno in (
            ("futura", TipoTermine.ADEMPIMENTO, "Data letta", False, "", (oggi + timedelta(days=5)).isoformat()),
            ("opp", TipoTermine.IMPUGNAZIONE, "Opposizione alla trattazione scritta", True, "CIV_OPPOSIZIONE_127_TER",
             f"{(oggi - timedelta(days=90)).isoformat()}T10:00:00+00:00"),
            ("appello", TipoTermine.IMPUGNAZIONE, "Appello", True, "", (oggi - timedelta(days=10)).isoformat()),
        )
    ]
    monkeypatch.setattr(topbar, "_require_any_permission", lambda *_a, **_k: None)
    monkeypatch.setattr(topbar, "get_scadenziario", lambda: SimpleNamespace(tutte=lambda **_k: righe))
    monkeypatch.setattr(topbar, "_case_lookup", lambda: {})
    monkeypatch.setattr(topbar, "_client_lookup", lambda: {})
    monkeypatch.setattr(topbar, "is_legacy_pec_deadline", lambda _s: False)
    monkeypatch.setattr("web.services.scadenze_rapide_letture.aggiungi_letture", lambda *_a, **_k: None)

    with Flask(__name__).test_request_context("/"):
        payload = topbar.quick_deadlines_payload(SimpleNamespace())

    assert payload["summary"]["drafts"] == 1
    assert payload["summary"]["urgent"] == payload["summary"]["overdue"] == 0
