"""Test collettori del piano del giorno (fonti materializzate, fail-soft)."""

from datetime import date, datetime, timedelta
from types import SimpleNamespace

from pct.daily_plan.clock import Clock
from pct.daily_plan.collectors import (
    AgendaCollector,
    Budget,
    CasePresidioCollector,
    CollectorContext,
    EconomicSignalCollector,
    PecSignalCollector,
    ScadenzarioCollector,
    build_coverage_report,
)
from pct.daily_plan.collectors.base import CollectorResult
from pct.daily_plan.models import SourceCoverage

CLOCK = Clock(fixed_now=datetime(2026, 7, 11, 8, 0))
TODAY = date(2026, 7, 11)


def _ctx(**overrides):
    base = dict(tenant_id="studio-a", clock=CLOCK, budget=Budget())
    base.update(overrides)
    return CollectorContext(**base)


# ──────────────────────────────────────────────
# Scadenziario
# ──────────────────────────────────────────────

class _ScadStore:
    def __init__(self, scadenze):
        self._scadenze = scadenze

    def tutte(self, solo_aperte=True):
        return list(self._scadenze)


def _scadenza(id_, giorni, perentorio=False, stato="aperta"):
    return SimpleNamespace(
        id=id_,
        titolo=f"Scadenza {id_}",
        data_scadenza=(TODAY + timedelta(days=giorni)).isoformat(),
        operational_due_at="",
        stato=SimpleNamespace(value=stato),
        id_fascicolo="fasc-1",
        id_utente_responsabile="",
        perentorio=perentorio,
        creata_il="2026-07-01T10:00:00",
    )


def test_scadenziario_collector_include_arretrate():
    """Caso obbligatorio 19: termini arretrati non esclusi."""
    ctx = _ctx(scadenziario_store=_ScadStore([
        _scadenza("scaduta", -10, perentorio=True),
        _scadenza("oggi", 0),
        _scadenza("lontana", 30),
    ]))
    result = ScadenzarioCollector().collect(ctx)
    ids = {s.source_id for s in result.signals}
    assert "scaduta" in ids and "oggi" in ids
    assert "lontana" not in ids  # oltre l'orizzonte dei 14 giorni
    perentoria = next(s for s in result.signals if s.source_id == "scaduta")
    assert perentoria.peremptory is True
    assert perentoria.metadata["scadenziario_id"] == "scaduta"
    assert result.coverage.status == "complete"


def test_scadenziario_collector_store_assente():
    result = ScadenzarioCollector().collect(_ctx())
    assert result.coverage.status == "unavailable"
    assert result.signals == []


def test_scadenziario_collector_usa_orizzonte_della_data_selezionata():
    planning_day = TODAY + timedelta(days=2)
    ctx = _ctx(
        planning_date=planning_day,
        scadenziario_store=_ScadStore([_scadenza("entro-orizzonte", 16)]),
    )

    result = ScadenzarioCollector().collect(ctx)

    assert [signal.source_id for signal in result.signals] == ["entro-orizzonte"]


# ──────────────────────────────────────────────
# Agenda
# ──────────────────────────────────────────────

class _AgendaStore:
    def __init__(self, appuntamenti):
        self._appuntamenti = appuntamenti

    def tutti(self):
        return list(self._appuntamenti)


def _appuntamento(id_, giorni, ora="10:00", tipo="UDIENZA", avvocato="Avv. Bianchi", durata=60):
    giorno = (TODAY + timedelta(days=giorni)).isoformat()
    return SimpleNamespace(
        id=id_,
        titolo=f"Evento {id_}",
        tipo=SimpleNamespace(value=tipo),
        stato=SimpleNamespace(value="CONFERMATO"),
        data_ora=f"{giorno}T{ora}:00",
        durata_minuti=durata,
        avvocato=avvocato,
        luogo="",
        procedimento="123/2026",
        id_cliente="cli-1",
    )


def test_agenda_collector_udienze_e_blocchi_fissi():
    ctx = _ctx(agenda_store=_AgendaStore([
        _appuntamento("udienza-oggi", 0),
        _appuntamento("udienza-domani", 1),
        _appuntamento("riunione-oggi", 0, ora="15:00", tipo="RIUNIONE"),
        _appuntamento("udienza-lontana", 10),
    ]))
    result = AgendaCollector().collect(ctx)
    kinds = {s.source_id: s.kind for s in result.signals}
    assert kinds.get("udienza-oggi") == "hearing_attend"
    assert kinds.get("udienza-domani") == "hearing_attend"
    assert "udienza-lontana" not in kinds  # oltre la finestra di preparazione
    # blocchi fissi: tutti gli impegni di oggi
    fissi = {e["id"] for e in result.fixed_agenda}
    assert fissi == {"udienza-oggi", "riunione-oggi"}
    udienza = next(s for s in result.signals if s.source_id == "udienza-oggi")
    assert udienza.metadata["agenda_id"] == "udienza-oggi"
    assert udienza.metadata["agenda_avvocato"] == "Avv. Bianchi"


def test_agenda_collector_conflitti():
    ctx = _ctx(agenda_store=_AgendaStore([
        _appuntamento("a", 0, ora="10:00", tipo="RIUNIONE", durata=120),
        _appuntamento("b", 0, ora="11:00", tipo="RIUNIONE"),
    ]))
    result = AgendaCollector().collect(ctx)
    conflitti = [s for s in result.signals if s.kind == "calendar_conflict"]
    assert len(conflitti) == 1
    assert conflitti[0].priority_hint == "P1"


def test_agenda_collector_usa_la_data_selezionata():
    planning_day = TODAY + timedelta(days=2)
    ctx = _ctx(
        planning_date=planning_day,
        agenda_store=_AgendaStore([
            _appuntamento("oggi", 0),
            _appuntamento("dopodomani", 2),
            _appuntamento("successiva", 3),
        ]),
    )

    result = AgendaCollector().collect(ctx)

    assert {entry["id"] for entry in result.fixed_agenda} == {"dopodomani"}
    assert {signal.source_id for signal in result.signals} == {
        "dopodomani",
        "successiva",
    }
    selected = next(signal for signal in result.signals if signal.source_id == "dopodomani")
    assert selected.blocking is True
    assert "giorno selezionato" in selected.reason


# ──────────────────────────────────────────────
# PEC
# ──────────────────────────────────────────────

class _FakePecRepo:
    def __init__(self):
        self.deadlines = []
        self.hearings = []
        self.payments = []
        self.messages = []

    def list_legal_deadlines_since(self, since="", limit=500):
        return list(self.deadlines)

    def list_legal_hearings_since(self, since="", limit=500):
        return list(self.hearings)

    def list_legal_payments_since(self, since="", limit=500):
        return list(self.payments)

    def list_messages_to_presidiate(self, since="", limit=300):
        return list(self.messages)

    def daily_plan_watermark(self):
        return "2026-07-11T07:00:00"


def test_pec_collector_termine_candidato_da_confermare():
    repo = _FakePecRepo()
    repo.deadlines = [
        {
            "id": "dl-1",
            "message_id": "msg-1",
            "received_at": "2026-07-10T17:42:00",
            "dies_a_quo_date": "2026-07-10",
            "norm_ref": "art. 183 c.p.c.",
            "peremptory": 1,
            "deterministic_status": "needs_review",
            "scadenziario_id": "",
            "human_review_required": 1,
            "event_confidence": 0.8,
            "linked_fascicolo_id": "fasc-1",
            "linked_fascicolo_score": 0.9,
        }
    ]
    result = PecSignalCollector().collect(_ctx(pec_repository=repo))
    sig = next(s for s in result.signals if s.kind == "pec_deadline")
    assert sig.metadata["needs_review"] is True
    assert sig.peremptory is True
    assert "decorrenza" in sig.reason
    assert result.coverage.status == "complete"
    assert result.watermark == "2026-07-11T07:00:00"


def test_pec_collector_link_debole_marcato():
    repo = _FakePecRepo()
    repo.deadlines = [
        {
            "id": "dl-2",
            "message_id": "msg-2",
            "dies_a_quo_date": "2026-07-10",
            "deterministic_status": "ok",
            "scadenziario_id": "sc-9",
            "human_review_required": 0,
            "event_confidence": 0.9,
            "linked_fascicolo_id": "fasc-1",
            "linked_fascicolo_score": 0.4,  # sotto soglia
        }
    ]
    result = PecSignalCollector().collect(_ctx(pec_repository=repo))
    sig = result.signals[0]
    assert sig.metadata.get("fascicolo_match") == "weak"


def test_pec_collector_messaggi_da_presidiare():
    repo = _FakePecRepo()
    repo.messages = [
        {
            "id": "msg-3",
            "received_at": "2026-07-11T06:00:00",
            "quality_status": "rosso",
            "signature_status": "valida",
            "linked_fascicolo_id": "fasc-1",
        },
        {
            "id": "msg-4",
            "received_at": "2026-07-11T06:30:00",
            "quality_status": "verde",
            "signature_status": "valida",
            "linked_fascicolo_id": "",
        },
    ]
    result = PecSignalCollector().collect(_ctx(pec_repository=repo))
    per_id = {s.source_id: s for s in result.signals}
    assert per_id["msg-3"].blocking is True
    assert per_id["msg-4"].metadata.get("needs_review") is True
    assert "non associata" in per_id["msg-4"].title.lower()


def test_pec_collector_udienza_remota_senza_link():
    repo = _FakePecRepo()
    repo.hearings = [
        {
            "id": "h-1",
            "message_id": "msg-5",
            "hearing_date": "2026-07-12",
            "mode": "remota",
            "link": "",
            "agenda_id": "app-7",
            "human_review_required": 0,
            "event_confidence": 0.85,
            "linked_fascicolo_id": "fasc-1",
            "linked_fascicolo_score": 0.9,
        }
    ]
    result = PecSignalCollector().collect(_ctx(pec_repository=repo))
    kinds = [s.kind for s in result.signals]
    assert "hearing_attend" in kinds
    assert "hearing_link_missing" in kinds
    udienza = next(s for s in result.signals if s.kind == "hearing_attend")
    assert udienza.metadata["agenda_id"] == "app-7"


def test_pec_collector_repo_non_disponibile():
    """Caso obbligatorio 9: repository PEC non disponibile → copertura, non vuoto."""
    result = PecSignalCollector().collect(_ctx(pec_repository=None))
    assert result.coverage.status == "unavailable"

    class _Rotto:
        def list_legal_deadlines_since(self, *a, **k):
            raise RuntimeError("db corrotto")

    result = PecSignalCollector().collect(_ctx(pec_repository=_Rotto()))
    assert result.coverage.status == "unavailable"


# ──────────────────────────────────────────────
# Presidio fascicoli
# ──────────────────────────────────────────────

def test_case_collector_trasforma_azioni_presidio():
    def provider(ctx):
        yield {
            "fascicolo": {
                "id": "fasc-1",
                "numero": "2026/10",
                "avvocato_referente": "Avv. Bianchi",
            },
            "actions": [
                {
                    "id": "doc-termine",
                    "sector": "documenti",
                    "title": "Verifica termine dal decreto",
                    "reason": "Il decreto contiene un termine da confermare.",
                    "priority": "P1",
                    "blocking": False,
                    "dateIso": "2026-07-12",
                    "href": "/fascicoli/fasc-1",
                    "legalBasis": "art. 127-ter c.p.c.",
                    "requiresCommunicationDate": True,
                }
            ],
        }

    result = CasePresidioCollector().collect(_ctx(presidio_provider=provider))
    sig = result.signals[0]
    assert sig.kind == "document_review"
    assert sig.priority_hint == "P1"
    assert sig.metadata["needs_review"] is True
    assert sig.metadata["base_normativa"] == "art. 127-ter c.p.c."
    assert sig.metadata["fascicolo_referente"] == "Avv. Bianchi"


def test_case_collector_budget_fascicoli():
    def provider(ctx):
        for i in range(10):
            yield {"fascicolo": {"id": f"f{i}"}, "actions": [{"id": "a", "sector": "documenti", "title": "x"}]}

    ctx = _ctx(presidio_provider=provider, budget=Budget(max_fascicoli=3))
    result = CasePresidioCollector().collect(ctx)
    assert len(result.signals) == 3
    assert result.truncated is True
    assert result.coverage.status == "stale"


def test_case_collector_filtra_dirty():
    """Refresh incrementale: rianalizza solo i fascicoli cambiati."""
    def provider(ctx):
        for fid in ("f1", "f2", "f3"):
            if ctx.dirty_fascicoli is not None and fid not in ctx.dirty_fascicoli:
                continue
            yield {"fascicolo": {"id": fid}, "actions": [{"id": "a", "sector": "pec", "title": "x"}]}

    ctx = _ctx(presidio_provider=provider, dirty_fascicoli={"f2"})
    result = CasePresidioCollector().collect(ctx)
    assert [s.fascicolo_id for s in result.signals] == ["f2"]


# ──────────────────────────────────────────────
# Economico
# ──────────────────────────────────────────────

class _PrevStore:
    def __init__(self, preventivi):
        self._preventivi = preventivi

    def tutti_preventivi(self):
        return list(self._preventivi)

    def tutti_conferimenti(self):
        return []


class _FattStore:
    def __init__(self, parcelle):
        self._parcelle = parcelle

    def tutte(self):
        return list(self._parcelle)


def test_economic_collector_bozze_e_insoluti():
    preventivi = _PrevStore([
        SimpleNamespace(
            id="p1", numero="2026/1", stato=SimpleNamespace(value="INVIATO"),
            inviato_cliente_il="2026-06-20", data_emissione="2026-06-20",
            id_fascicolo="", id_cliente="cli-1",
        )
    ])
    parcelle = _FattStore([
        SimpleNamespace(
            id="pa1", numero="2026/5", stato=SimpleNamespace(value="BOZZA"),
            id_fascicolo="fasc-1", id_cliente="cli-1", data_scadenza=None,
        ),
        SimpleNamespace(
            id="pa2", numero="2026/6", stato=SimpleNamespace(value="EMESSA"),
            id_fascicolo="fasc-1", id_cliente="cli-1", data_scadenza="2026-06-01",
        ),
    ])
    ctx = _ctx(preventivi_store=preventivi, fatturazione_store=parcelle)
    result = EconomicSignalCollector().collect(ctx)
    kinds = {s.source_id: s.kind for s in result.signals}
    assert kinds["p1"] == "quote_followup"
    assert kinds["pa1"] == "invoice_draft_needed"
    assert kinds["pa2"] == "payment_review"


# ──────────────────────────────────────────────
# Copertura / salute fonti
# ──────────────────────────────────────────────

def test_coverage_report_fonte_non_disponibile_genera_warning():
    """Caso obbligatorio 8-9: fonte giù → warning esplicito, non silenzio."""
    results = [
        CollectorResult(
            source_type="pec",
            coverage=SourceCoverage(source_type="pec", status="unavailable", note="giù"),
        ),
        CollectorResult(
            source_type="agenda",
            coverage=SourceCoverage(source_type="agenda", status="complete"),
        ),
    ]
    coverage, warnings = build_coverage_report(results, clock=CLOCK)
    assert any("non disponibile" in w for w in warnings)
    assert any(c.status == "unavailable" for c in coverage)


def test_coverage_report_watermark_vecchio_diventa_stale():
    """Caso obbligatorio 8: calendario non sincronizzato → warning copertura."""
    results = [
        CollectorResult(
            source_type="agenda",
            coverage=SourceCoverage(source_type="agenda", status="complete"),
        )
    ]
    watermarks = {"agenda": {"last_success_at": "2026-07-01T00:00:00"}}
    coverage, warnings = build_coverage_report(results, watermarks=watermarks, clock=CLOCK)
    assert coverage[0].status == "stale"
    assert warnings
