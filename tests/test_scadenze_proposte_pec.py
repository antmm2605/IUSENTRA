"""Proposte di scadenza in BOZZA dalle date lette nei provvedimenti PEC.

Copre il ciclo completo richiesto dal principio fail-closed: la data letta ma
non promossa dalla matrice PEC diventa una proposta in BOZZA con il passaggio
fonte citato; la bozza resta fuori dalle viste operative finche' l'avvocato
non la conferma (BOZZA -> APERTO) o la scarta con motivo (BOZZA -> ANNULLATO).
"""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

from pct.pec_pipeline import PecAuditRepository
from pct.scadenze_proposte_pec import (
    MAX_PROPOSTE_PER_MESSAGGIO,
    bozza_marker,
    bozza_scadenza_fields,
    select_draft_candidates,
)
from pct.scadenziario import GestioneScadenziario, StatoTermine, TipoTermine
from web.services.react_scadenziario_bridge import build_react_scadenziario_payload

TODAY = date(2026, 8, 12)


def _candidate(day: str, *, confidence: float = 0.7, label: str = "", context: str = "contesto") -> dict:
    return {
        "date": day,
        "raw_date": day,
        "label": label or "Data letta",
        "source": "Provvedimento.pdf",
        "context": context,
        "confidence": confidence,
    }


# --- Selezione candidati ---------------------------------------------------------


def test_select_draft_candidates_tiene_solo_date_future_non_classificate():
    future = (TODAY + timedelta(days=10)).isoformat()
    past = (TODAY - timedelta(days=3)).isoformat()
    classified = (TODAY + timedelta(days=20)).isoformat()

    def classify(item: dict) -> str:
        return "udienza" if item.get("date") == classified else ""

    selected = select_draft_candidates(
        [_candidate(past), _candidate(future), _candidate(classified)],
        today=TODAY,
        classify=classify,
    )

    assert [item["date"] for item in selected] == [future]


def test_select_draft_candidates_deduplica_per_giorno_ed_esclude_date_gia_promosse():
    day = (TODAY + timedelta(days=5)).isoformat()
    excluded = (TODAY + timedelta(days=8)).isoformat()

    selected = select_draft_candidates(
        [
            _candidate(day, confidence=0.5, context="debole"),
            _candidate(day, confidence=0.9, context="forte"),
            _candidate(excluded),
        ],
        today=TODAY,
        classify=lambda item: "",
        exclude_dates={excluded},
    )

    assert len(selected) == 1
    assert selected[0]["context"] == "forte"


def test_select_draft_candidates_applica_il_tetto_per_messaggio():
    candidates = [
        _candidate((TODAY + timedelta(days=index + 1)).isoformat())
        for index in range(MAX_PROPOSTE_PER_MESSAGGIO + 3)
    ]

    selected = select_draft_candidates(candidates, today=TODAY, classify=lambda item: "")

    assert len(selected) == MAX_PROPOSTE_PER_MESSAGGIO


def test_bozza_scadenza_fields_porta_marcatore_e_snippet():
    day = (TODAY + timedelta(days=9)).isoformat()
    fields = bozza_scadenza_fields(
        _candidate(day, confidence=0.74, label="deposito", context="deposito atti entro la data indicata"),
        subject="Comunicazione di cancelleria RG 123/2026",
        event_type="comunicazione_cancelleria",
        message_id="msg-777",
        source_event_at="2026-08-10T09:00:00",
        fascicolo_id="F1",
    )

    assert bozza_marker("msg-777", day) in fields["note"]
    assert "revisione professionale obbligatoria" in fields["note"]
    assert fields["source_snippet"] == "deposito atti entro la data indicata"
    assert fields["source_snippet_label"] == "deposito"
    assert fields["source_document_name"] == "Provvedimento.pdf"
    assert fields["source_message_id"] == "msg-777"
    assert fields["source_confidence"] == 0.74
    assert fields["deadline_profile_code"] == "PEC_PROPOSTA_DATA"
    assert fields["data_scadenza"] == day
    assert "Comunicazione di cancelleria RG 123/2026" in fields["titolo"]


# --- Ciclo BOZZA nello scadenziario ----------------------------------------------


def _manager(tmp_path) -> GestioneScadenziario:
    return GestioneScadenziario(db_path=str(tmp_path / "scadenze.json"))


def _nuova_bozza(manager: GestioneScadenziario, *, giorni: int = 12):
    return manager.nuova(
        titolo="Verifica data letta nella PEC",
        tipo=TipoTermine.ADEMPIMENTO,
        data_scadenza=(TODAY + timedelta(days=giorni)).isoformat(),
        note="PEC_AUDIT:msg-1 PROPOSTA_DATA_PEC:2026-08-24",
        stato=StatoTermine.BOZZA,
        source_snippet="si rinvia ogni valutazione alla data del 24/08/2026",
        source_message_id="msg-1",
    )


def test_bozza_esclusa_dalle_viste_operative_e_presente_nella_coda(tmp_path):
    manager = _manager(tmp_path)
    bozza = _nuova_bozza(manager)

    assert all(item.id != bozza.id for item in manager.tutte(solo_aperte=True))
    assert [item.id for item in manager.bozze()] == [bozza.id]


def test_conferma_bozza_promuove_ad_aperto(tmp_path):
    manager = _manager(tmp_path)
    bozza = _nuova_bozza(manager)

    confermata = manager.conferma_bozza(bozza.id, attore="avv.rossi")

    assert confermata.stato == StatoTermine.APERTO
    assert "Proposta confermata" in confermata.note
    assert any(item.id == bozza.id for item in manager.tutte(solo_aperte=True))
    try:
        manager.conferma_bozza(bozza.id)
        raise AssertionError("una scadenza gia' confermata non e' riconfermabile")
    except ValueError:
        pass


def test_scarta_bozza_annulla_con_motivo(tmp_path):
    manager = _manager(tmp_path)
    bozza = _nuova_bozza(manager)

    scartata = manager.scarta_bozza(bozza.id, motivo="data riferita a controparte", attore="avv.rossi")

    assert scartata.stato == StatoTermine.ANNULLATO
    assert "Motivo: data riferita a controparte" in scartata.note
    assert not manager.bozze()
    assert all(item.id != bozza.id for item in manager.tutte(solo_aperte=True))


def test_bozza_sopravvive_al_reload_del_manager(tmp_path):
    manager = _manager(tmp_path)
    bozza = _nuova_bozza(manager)

    riletto = GestioneScadenziario(db_path=str(tmp_path / "scadenze.json"))

    ricaricata = riletto.get(bozza.id)
    assert ricaricata is not None
    assert ricaricata.stato == StatoTermine.BOZZA
    assert ricaricata.source_snippet.startswith("si rinvia")


# --- Cablaggio pipeline PEC ------------------------------------------------------


def _repo_with_stub_detail(tmp_path, procedural_dates, *, hearing_due: str = ""):
    repo = PecAuditRepository(
        tmp_path / "pec_audit.sqlite",
        tenant_id="default",
        scadenziario_db_path=tmp_path / "scadenziario" / "scadenze.json",
    )
    detail = {
        "parsed": {
            "headers": {"subject": "Comunicazione di cancelleria RG 55/2026"},
            "fields": {"data_consegna": {"value": "2026-08-10T09:00:00"}},
            "procedural_dates": procedural_dates,
        },
        "validation_report": {
            "event_type": "comunicazione_cancelleria",
            "deadline_proposal": {
                "status": "review_required",
                "auto_create": False,
                "due_date": hearing_due,
                "source_event_type": "comunicazione_cancelleria",
                "source_event_at": "2026-08-10T09:00:00",
            },
            "hearing_proposals": [],
        },
        "message": {"linked_fascicolo_id": "FASC-9"},
    }
    repo.get_message_detail = lambda message_id: detail  # type: ignore[method-assign]
    return repo


def test_create_draft_date_proposals_crea_bozze_idempotenti(tmp_path):
    future = (date.today() + timedelta(days=15)).isoformat()
    repo = _repo_with_stub_detail(tmp_path, [_candidate(future, context="si riserva di decidere entro la data indicata")])

    first = repo.create_draft_date_proposals("msg-42", actor="pytest")
    second = repo.create_draft_date_proposals("msg-42", actor="pytest")

    assert first["created"] == 1
    assert second["created"] == 0
    manager = GestioneScadenziario(db_path=str(tmp_path / "scadenziario" / "scadenze.json"))
    bozze = manager.bozze()
    assert len(bozze) == 1
    assert bozze[0].stato == StatoTermine.BOZZA
    assert bozze[0].id_fascicolo == "FASC-9"
    assert bozze[0].source_message_id == "msg-42"
    assert bozze[0].source_snippet == "si riserva di decidere entro la data indicata"
    assert bozza_marker("msg-42", future) in bozze[0].note
    assert not manager.tutte(solo_aperte=True)


def test_create_draft_date_proposals_esclude_date_gia_promosse(tmp_path):
    promoted = (date.today() + timedelta(days=6)).isoformat()
    repo = _repo_with_stub_detail(tmp_path, [_candidate(promoted)], hearing_due=promoted)

    result = repo.create_draft_date_proposals("msg-43", actor="pytest")

    assert result["created"] == 0


# --- Payload React ---------------------------------------------------------------


def test_payload_scadenziario_espone_coda_proposte_e_non_le_conta_tra_le_aperte(tmp_path):
    manager = _manager(tmp_path)
    manager.nuova(
        titolo="Scadenza operativa reale",
        tipo=TipoTermine.ADEMPIMENTO,
        data_scadenza=(TODAY + timedelta(days=3)).isoformat(),
    )
    bozza = _nuova_bozza(manager)

    payload = build_react_scadenziario_payload(
        gestione_scadenziario=manager,
        gestione_fascicoli=SimpleNamespace(get=lambda _id: None),
    )

    assert all(row["id"] != bozza.id for row in payload["items"])
    proposte = payload["draftProposals"]
    assert [row["id"] for row in proposte] == [bozza.id]
    assert proposte[0]["sourceSnippet"].startswith("si rinvia")
    assert proposte[0]["confirmHref"] == f"/scadenziario/{bozza.id}/conferma-proposta"
    assert proposte[0]["discardHref"] == f"/scadenziario/{bozza.id}/scarta-proposta"
    assert proposte[0]["statusLabel"] == "Proposta da confermare"
    assert all(facet["value"] != StatoTermine.BOZZA.value for facet in payload["facets"]["statuses"])
