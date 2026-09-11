"""Un evento, una attività: casi reali di doppioni del Piano del giorno.

Riproduce i doppioni osservati in produzione l'11/09/2026:
- «Deposito note scritte ex art. 127-ter c.p.c.» ×3 sullo stesso fascicolo,
  letto da più copie del decreto e salvato con identificativi posizionali;
- «Opposizione alla trattazione scritta» ×2 dalla stessa comunicazione di
  cancelleria registrata due volte nello scadenziario.
"""

from datetime import timedelta

from pct.daily_plan.correlation import correlate
from pct.daily_plan.deduplication import build_dedupe_key, merge_signals
from pct.daily_plan.models import DailyWorkItem, OperationalSignal, SignalEvidence
from tests.test_daily_plan_service import CLOCK, DATE, TODAY, _scadenza, _World

TITOLO = "Deposito note scritte ex art. 127-ter c.p.c."
TERMINE = (TODAY + timedelta(days=2)).isoformat()


def _azione(indice: int, documento: str) -> dict:
    return {
        "id": f"documenti-note_127_ter-{indice}",
        "sector": "documenti",
        "title": TITOLO,
        "reason": "Il decreto fissa la sostituzione dell'udienza con note scritte.",
        "priority": "P0",
        "peremptory": True,
        "blocking": True,
        "dateIso": TERMINE,
        "href": "/fascicoli/fasc-1#udienze",
        "source": f"{documento}.pdf",
        "evidence": f"{documento}.pdf",
        "documentId": documento,
        "sourceHref": f"/fascicoli/fasc-1/documenti/{documento}/visualizza",
        "legalBasis": "127-bis / 127-ter c.p.c.",
    }


def _presidio(*azioni: dict) -> dict:
    return {
        "fascicolo": {"id": "fasc-1", "numero": "2026/10", "avvocato_referente": "Mario Bianchi"},
        "actions": list(azioni),
        "complete": True,
    }


def _segnale_storico(indice: int, **overrides) -> OperationalSignal:
    """Segnale come lo salvava la versione precedente del collettore."""
    action_id = f"documenti-note_127_ter-{indice}"
    base = dict(
        id=f"sig_case_fasc-1_{action_id}",
        tenant_id="studio-a",
        source_type="case_presidio",
        source_id=f"fasc-1:{action_id}",
        kind="document_review",
        title=TITOLO,
        dedupe_key=build_dedupe_key(
            "studio-a", "fasc-1", "document_review", f"presidio:fasc-1:{action_id}", TERMINE
        ),
        fascicolo_id="fasc-1",
        due_at=TERMINE,
        priority_hint="P0",
        peremptory=True,
        blocking=True,
        confidence=0.8,
        metadata={"sector": "documenti", "fascicolo_referente": "Mario Bianchi"},
        evidence=[SignalEvidence(source_type="case_presidio", source_id=f"fasc-1:{action_id}", label="C")],
    )
    base.update(overrides)
    return OperationalSignal(**base)


def _attivita_note(world: _World) -> list[DailyWorkItem]:
    return [i for i in world.repo.list_items(DATE) if i.title == TITOLO]


def test_tre_copie_del_decreto_diventano_una_attivita_con_tre_fonti(tmp_path):
    world = _World(tmp_path)
    world.presidio_entries = [_presidio(_azione(3, "DOC-A"), _azione(4, "DOC-B"), _azione(5, "DOC-C"))]
    world.service().rebuild_full()

    attivita = _attivita_note(world)
    assert len(attivita) == 1
    assert len(attivita[0].evidence) == 3
    assert {e.href for e in attivita[0].evidence} == {
        f"/fascicoli/fasc-1/documenti/{doc}/visualizza" for doc in ("DOC-A", "DOC-B", "DOC-C")
    }
    assert "3 documenti" in attivita[0].reason


def test_adempimenti_diversi_o_date_diverse_restano_separati(tmp_path):
    world = _World(tmp_path)
    altra_data = dict(_azione(1, "DOC-B"), dateIso=(TODAY + timedelta(days=9)).isoformat())
    altro_titolo = dict(_azione(2, "DOC-C"), id="documenti-costituzione_resistente-2", title="Verifica costituzione resistente")
    world.presidio_entries = [_presidio(_azione(0, "DOC-A"), altra_data, altro_titolo)]
    world.service().rebuild_full()
    assert len([i for i in world.repo.list_items(DATE) if i.fascicolo_id == "fasc-1"]) == 3


def test_copie_gia_salvate_si_fondono_subito_e_conservano_la_decisione(tmp_path):
    world = _World(tmp_path)
    storici = [_segnale_storico(i) for i in (3, 4, 5)]
    world.repo.upsert_signals(storici)
    world.repo.replace_items_for_date(
        DATE,
        [
            DailyWorkItem(
                id="", tenant_id="studio-a", target_date=DATE, title=TITOLO,
                action_kind="document_review", dedupe_key=sig.dedupe_key,
                assigned_user_id="u1", source_signal_ids=[sig.id], status="proposed",
            )
            for sig in storici
        ],
        plan_version="v0",
    )
    for item in world.repo.list_items(DATE):
        world.repo.update_item_status(item.id, "completed", actor="Mario Bianchi")

    # refresh incrementale senza rilettura del fascicolo: i vecchi segnali
    # restano salvati ma devono già produrre UNA attività
    world.service().refresh_incremental()
    attivita = _attivita_note(world)
    assert len(attivita) == 1
    assert attivita[0].status == "completed"


def test_copia_ancora_aperta_non_chiude_l_attivita_unificata(tmp_path):
    world = _World(tmp_path)
    storici = [_segnale_storico(i) for i in (3, 4)]
    world.repo.upsert_signals(storici)
    world.repo.replace_items_for_date(
        DATE,
        [
            DailyWorkItem(
                id="", tenant_id="studio-a", target_date=DATE, title=TITOLO,
                action_kind="document_review", dedupe_key=sig.dedupe_key,
                assigned_user_id="u1", source_signal_ids=[sig.id],
            )
            for sig in storici
        ],
        plan_version="v0",
    )
    prima = world.repo.list_items(DATE)[0]
    world.repo.update_item_status(prima.id, "completed", actor="Mario Bianchi")

    world.service().refresh_incremental()
    attivita = _attivita_note(world)
    assert len(attivita) == 1
    assert attivita[0].status != "completed"


def test_rilettura_del_fascicolo_chiude_i_segnali_con_identificativi_superati(tmp_path):
    world = _World(tmp_path)
    world.repo.upsert_signals([_segnale_storico(i) for i in (3, 4, 5)])
    world.presidio_entries = [_presidio(_azione(0, "DOC-A"), _azione(1, "DOC-B"))]
    world.repo.mark_dirty("fascicolo", ["fasc-1"], reason="documenti aggiornati")

    world.service().refresh_incremental()

    attivi = world.repo.list_active_signals(source_type="case_presidio", fascicolo_id="fasc-1")
    assert len(attivi) == 1
    assert len(_attivita_note(world)) == 1


def test_lettura_parziale_del_fascicolo_non_chiude_segnali(tmp_path):
    world = _World(tmp_path)
    world.repo.upsert_signals([_segnale_storico(3)])
    world.presidio_entries = [dict(_presidio(), complete=False)]
    world.repo.mark_dirty("fascicolo", ["fasc-1"], reason="catalogo non leggibile")

    world.service().refresh_incremental()
    assert len(world.repo.list_active_signals(source_type="case_presidio", fascicolo_id="fasc-1")) == 1


def _scadenza_da_pec(id_, pec, fascicolo="fasc-1", titolo="Opposizione alla trattazione scritta ex art. 127-ter c.p.c."):
    base = _scadenza(id_, 1, perentorio=True, fascicolo=fascicolo)
    base.titolo = titolo
    base.source_event_type = "comunicazione_cancelleria"
    base.source_event_at = "2026-07-09T10:15:00+02:00"
    base.note = f"PEC_AUDIT:{pec}"
    return base


def test_stessa_comunicazione_registrata_due_volte_una_sola_scadenza_nel_piano(tmp_path):
    world = _World(tmp_path)
    world.scadenze = [_scadenza_da_pec("sc-1", "pec_a"), _scadenza_da_pec("sc-2", "pec_b")]
    world.service().rebuild_full()
    opposizioni = [i for i in world.repo.list_items(DATE) if i.title.startswith("Opposizione")]
    assert len(opposizioni) == 1
    assert {e.source_id for e in opposizioni[0].evidence} == {"sc-1", "sc-2"}


def test_scadenze_senza_fascicolo_da_pec_diverse_restano_distinte(tmp_path):
    world = _World(tmp_path)
    world.scadenze = [
        _scadenza_da_pec("r-1", "pec_accettazione", fascicolo="", titolo="Presidio ricevute PEC da completare"),
        _scadenza_da_pec("r-2", "pec_consegna", fascicolo="", titolo="Presidio ricevute PEC da completare"),
    ]
    world.service().rebuild_full()
    ricevute = [i for i in world.repo.list_items(DATE) if i.title == "Presidio ricevute PEC da completare"]
    assert len(ricevute) == 2


def test_scadenze_manuali_con_stesso_titolo_non_vengono_fuse():
    manuali = [
        OperationalSignal(
            id=f"sig_sc_{sid}", tenant_id="studio-a", source_type="scadenziario", source_id=sid,
            kind="deadline_fulfill", title="Deposito memoria", dedupe_key="", fascicolo_id="fasc-1",
            due_at="2026-07-15", metadata={"scadenziario_id": sid},
        )
        for sid in ("m-1", "m-2")
    ]
    assert len(merge_signals(correlate(manuali, clock=CLOCK))) == 2
