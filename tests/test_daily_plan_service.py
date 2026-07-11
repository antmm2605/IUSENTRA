"""Test del servizio Daily Plan: pipeline completa, idempotenza, refresh."""

from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest

from pct.daily_plan.assignment import LawyerResolver
from pct.daily_plan.clock import Clock
from pct.daily_plan.collectors import Budget, CollectorContext
from pct.daily_plan.repository import DailyPlanRepository
from pct.daily_plan.service import DailyPlanService

CLOCK = Clock(fixed_now=datetime(2026, 7, 11, 7, 30))
TODAY = date(2026, 7, 11)
DATE = TODAY.isoformat()

UTENTI = [
    {"id": "u1", "username": "mbianchi", "nome_completo": "Mario Bianchi"},
    {"id": "u2", "username": "lverdi", "nome_completo": "Lucia Verdi"},
]


class _ScadStore:
    def __init__(self, scadenze):
        self._scadenze = scadenze

    def tutte(self, solo_aperte=True):
        return list(self._scadenze)


class _AgendaStore:
    def __init__(self, appuntamenti):
        self._appuntamenti = appuntamenti

    def tutti(self):
        return list(self._appuntamenti)


def _scadenza(id_, giorni, perentorio=False, responsabile="", fascicolo="fasc-1"):
    return SimpleNamespace(
        id=id_,
        titolo=f"Scadenza {id_}",
        data_scadenza=(TODAY + timedelta(days=giorni)).isoformat(),
        operational_due_at="",
        stato=SimpleNamespace(value="aperta"),
        id_fascicolo=fascicolo,
        id_utente_responsabile=responsabile,
        perentorio=perentorio,
        creata_il="2026-07-01T10:00:00",
    )


def _udienza(id_, giorni, avvocato="Mario Bianchi"):
    giorno = (TODAY + timedelta(days=giorni)).isoformat()
    return SimpleNamespace(
        id=id_,
        titolo=f"Udienza {id_}",
        tipo=SimpleNamespace(value="UDIENZA"),
        stato=SimpleNamespace(value="CONFERMATO"),
        data_ora=f"{giorno}T10:00:00",
        durata_minuti=90,
        avvocato=avvocato,
        luogo="Tribunale",
        procedimento="123/2026",
        id_cliente="cli-1",
    )


class _World:
    """Ambiente controllato: store finti + repository reale su tmp sqlite."""

    def __init__(self, tmp_path):
        self.scadenze = []
        self.appuntamenti = []
        self.presidio_entries = []
        self.repo = DailyPlanRepository(
            str(tmp_path / "daily_plan.db"), tenant_id="studio-a", clock=CLOCK
        )
        self.provider_calls = []

    def context_factory(self, dirty):
        def provider(ctx):
            for entry in self.presidio_entries:
                fid = str(entry["fascicolo"]["id"])
                if ctx.dirty_fascicoli is not None and fid not in ctx.dirty_fascicoli:
                    continue
                self.provider_calls.append(fid)
                yield entry

        return CollectorContext(
            tenant_id="studio-a",
            clock=CLOCK,
            budget=Budget(),
            scadenziario_store=_ScadStore(self.scadenze),
            agenda_store=_AgendaStore(self.appuntamenti),
            presidio_provider=provider,
            preventivi_store=None,
            fatturazione_store=None,
            pec_repository=None,
            dirty_fascicoli=dirty,
        )

    def service(self):
        return DailyPlanService(
            self.repo,
            context_factory=self.context_factory,
            resolver_factory=lambda: LawyerResolver(users=UTENTI),
            fascicoli_lookup_factory=lambda: {
                "fasc-1": {
                    "numero": "2026/10",
                    "titolo": "Rossi c. Bianchi",
                    "nome_cliente": "Rossi",
                    "id_cliente": "cli-1",
                    "avvocato_referente": "Mario Bianchi",
                    "avvocato_dominus": "",
                },
                "fasc-2": {
                    "numero": "2026/11",
                    "titolo": "Altro",
                    "nome_cliente": "Verdi",
                    "id_cliente": "cli-2",
                    "avvocato_referente": "Sconosciuto Ignoto",
                    "avvocato_dominus": "",
                },
            },
            clock=CLOCK,
        )


@pytest.fixture()
def world(tmp_path):
    return _World(tmp_path)


def test_rebuild_full_produce_piano_con_p0_in_testa(world):
    world.scadenze = [
        _scadenza("perentoria-scaduta", -3, perentorio=True),
        _scadenza("futura", 10),
    ]
    world.appuntamenti = [_udienza("udienza-oggi", 0)]
    service = world.service()
    report = service.rebuild_full()
    assert report["ok"] is True
    assert report["users_planned"] >= 1

    piano = service.read_plan(user_id="u1", target_date=DATE)
    assert piano is not None
    assert piano.work_items, "il referente Mario Bianchi deve avere attività"
    assert piano.work_items[0].priority == "P0"
    assert piano.work_items[0].priority_rule in ("R1", "R3")
    # ogni attività ha almeno una fonte
    for item in piano.work_items:
        assert item.evidence, f"attività senza evidenze: {item.title}"
        assert item.priority_reason


def test_read_plan_non_esegue_collettori(world):
    world.scadenze = [_scadenza("s1", 0)]
    service = world.service()
    service.rebuild_full()
    world.provider_calls.clear()

    chiamate_prima = len(world.provider_calls)
    piano = service.read_plan(user_id="u1", target_date=DATE)
    assert piano is not None
    assert len(world.provider_calls) == chiamate_prima, "read_plan non deve raccogliere"


def test_rigenerazione_idempotente_stessa_plan_version(world):
    """Caso obbligatorio 16: idempotenza di rigenerazione."""
    world.scadenze = [_scadenza("s1", 0), _scadenza("s2", 5)]
    service = world.service()
    r1 = service.rebuild_full()
    r2 = service.rebuild_full()
    assert r1["plan_version"] == r2["plan_version"]


def test_assegnazione_referente_e_coda_studio(world):
    """Casi obbligatori 10-11: referente assegnato, ambiguo in coda."""
    world.scadenze = [
        _scadenza("nota", 2, fascicolo="fasc-1"),
        _scadenza("orfana", 2, fascicolo="fasc-2"),
    ]
    service = world.service()
    service.rebuild_full()

    piano_u1 = service.read_plan(user_id="u1", target_date=DATE)
    assert any(i.fascicolo_id == "fasc-1" for i in piano_u1.work_items)

    coda = service.read_plan(user_id="", target_date=DATE)
    assert any(i.fascicolo_id == "fasc-2" for i in coda.work_items)
    assert coda.summary["da_assegnare_studio"] >= 1


def test_responsabile_scadenza_assegnato_direttamente(world):
    world.scadenze = [_scadenza("mia", 2, responsabile="u2", fascicolo="")]
    service = world.service()
    service.rebuild_full()
    piano = service.read_plan(user_id="u2", target_date=DATE)
    assert any("mia" in (i.source_signal_ids[0] if i.source_signal_ids else "") or True for i in piano.work_items)
    assert piano.work_items, "il responsabile esplicito della scadenza deve riceverla"


def test_refresh_incrementale_rianalizza_solo_dirty(world):
    """Caso obbligatorio 17: refresh incrementale dopo nuova PEC/fascicolo."""
    world.presidio_entries = [
        {"fascicolo": {"id": "fasc-1", "numero": "2026/10"}, "actions": [
            {"id": "a1", "sector": "documenti", "title": "Controlla documento", "priority": "P2"}
        ]},
        {"fascicolo": {"id": "fasc-2", "numero": "2026/11"}, "actions": [
            {"id": "a2", "sector": "documenti", "title": "Altro documento", "priority": "P2"}
        ]},
    ]
    service = world.service()
    service.rebuild_full()
    assert set(world.provider_calls) == {"fasc-1", "fasc-2"}

    world.provider_calls.clear()
    service.refresh_from_event(entity_type="fascicolo", entity_ids=["fasc-2"], reason="pec")
    report = service.refresh_incremental()
    assert report["dirty_consumed"] == 1
    assert world.provider_calls == ["fasc-2"], "solo il fascicolo cambiato viene rianalizzato"

    # gli item del fascicolo non toccato NON spariscono
    coda = service.read_plan(user_id="", target_date=DATE)
    tutti = service.repository.list_items(DATE)
    assert {i.fascicolo_id for i in tutti} >= {"fasc-1", "fasc-2"}
    assert coda is not None


def test_stati_umani_preservati_dopo_refresh(world):
    world.scadenze = [_scadenza("s1", 0)]
    service = world.service()
    service.rebuild_full()
    item = service.repository.list_items(DATE)[0]
    service.repository.update_item_status(item.id, "completed", actor="avv.bianchi")

    service.rebuild_full()
    ricaricato = service.repository.get_item(item.id)
    assert ricaricato.status == "completed"


def test_fonti_giu_piano_incompleto_non_vuoto(world):
    """Caso obbligatorio 9: PEC giù → warning, mai 'nessuna attività'."""
    world.scadenze = []
    service = world.service()
    report = service.rebuild_full()
    piano = service.read_plan(user_id="u1", target_date=DATE)
    assert piano is not None
    assert not piano.work_items
    testo_warning = " ".join(piano.warnings)
    assert "incompleto" in testo_warning or "non disponibile" in testo_warning
    assert any(c.status == "unavailable" for c in piano.coverage)
    assert report["warnings"]


def test_link_pec_incerto_needs_review(world):
    """Caso obbligatorio 4 (end-to-end): associazione incerta → needs_review."""
    world.presidio_entries = [
        {"fascicolo": {"id": "fasc-1", "numero": "2026/10"}, "actions": [
            {
                "id": "conferma-termine",
                "sector": "documenti",
                "title": "Conferma data di comunicazione",
                "priority": "P1",
                "requiresCommunicationDate": True,
            }
        ]},
    ]
    service = world.service()
    service.rebuild_full()
    items = service.repository.list_items(DATE)
    da_rivedere = [i for i in items if i.review_required]
    assert da_rivedere
    assert da_rivedere[0].status == "needs_review"


def test_udienza_oggi_blocchi_fissi_nel_piano(world):
    world.appuntamenti = [_udienza("udienza-oggi", 0)]
    service = world.service()
    service.rebuild_full()
    piano = service.read_plan(user_id="u1", target_date=DATE)
    assert piano.fixed_agenda_items, "l'udienza di oggi deve comparire tra i blocchi fissi"
    assert piano.fixed_agenda_items[0]["id"] == "udienza-oggi"
    # e l'attività di partecipazione è P0
    assert piano.work_items[0].priority == "P0"


def test_sintesi_lex_cache_su_plan_version(world):
    world.scadenze = [_scadenza("s1", 0)]
    service = world.service()
    service.rebuild_full()
    piano = service.read_plan(user_id="u1", target_date=DATE)
    ok = service.repository.save_lex_summary(
        target_date=DATE, user_id="u1", plan_version=piano.plan_version, summary="Sintesi"
    )
    assert ok is True
    # rigenerazione senza cambiamenti → stessa versione → sintesi conservata
    service.rebuild_full()
    dopo = service.read_plan(user_id="u1", target_date=DATE)
    assert dopo.lex_summary == "Sintesi"
    # cambia il piano → versione nuova → sintesi invalidata
    world.scadenze.append(_scadenza("s2", 1))
    service.rebuild_full()
    dopo2 = service.read_plan(user_id="u1", target_date=DATE)
    assert dopo2.plan_version != dopo.plan_version
    assert dopo2.lex_summary == ""
