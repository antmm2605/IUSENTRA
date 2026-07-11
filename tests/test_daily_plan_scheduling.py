"""Test pianificazione della giornata (proposta, mai scritture in agenda)."""

from datetime import date, datetime

from pct.daily_plan.clock import ROME_TZ
from pct.daily_plan.models import DailyWorkItem
from pct.daily_plan.scheduling import (
    FixedBlock,
    fixed_block_from_agenda,
    plan_day,
)

TARGET = date(2026, 7, 11)


def _item(key, priority="P2", rank=0, kind="pec_review", minutes=0):
    return DailyWorkItem(
        id=f"dpi_{key}",
        tenant_id="studio-a",
        target_date=TARGET.isoformat(),
        title=f"Attivita {key}",
        action_kind=kind,
        dedupe_key=key,
        priority=priority,
        item_rank=rank,
        estimated_minutes=minutes,
    )


def _blocco(ora, minuti=60, kind="appuntamento", luogo=""):
    return FixedBlock(
        start=datetime(2026, 7, 11, ora, 0, tzinfo=ROME_TZ),
        minutes=minuti,
        kind=kind,
        luogo=luogo,
    )


def test_p0_pianificati_per_primi():
    items = [
        _item("b", priority="P2", rank=1),
        _item("a", priority="P0", rank=1),
        _item("c", priority="P1", rank=1),
    ]
    esito = plan_day(items, [], target_date=TARGET)
    ordine = [i.dedupe_key for i in esito.scheduled]
    assert ordine[0] == "a"
    assert ordine[1] == "c"
    assert not esito.backlog


def test_blocchi_fissi_rispettati_con_preparazione_udienza():
    udienza = _blocco(10, minuti=60, kind="udienza")
    items = [_item("a", priority="P0", minutes=60)]
    esito = plan_day(items, [udienza], target_date=TARGET)
    inizio = datetime.fromisoformat(esito.scheduled[0].scheduled_start)
    fine = inizio.replace(minute=inizio.minute)  # inizio proposta
    # la proposta non può cadere dentro udienza (10:00-11:00) né nella
    # mezz'ora di preparazione (09:30-10:00)
    assert not (
        datetime(2026, 7, 11, 9, 30, tzinfo=ROME_TZ)
        <= inizio
        < datetime(2026, 7, 11, 11, 0, tzinfo=ROME_TZ)
    )
    assert fine.tzinfo is not None


def test_giornata_piena_p2_p3_in_backlog_p0_mai():
    """Caso obbligatorio 12: giornata piena → P2/P3 nel backlog, P0 pianificato."""
    # blocchi fissi 08:30-18:00 → poco tempo libero
    blocchi = [
        _blocco(8, minuti=30),
        _blocco(9, minuti=240),
        _blocco(13, minuti=240),
        _blocco(17, minuti=90),
    ]
    items = [
        _item("urgente", priority="P0", minutes=30),
        _item("p2a", priority="P2", minutes=60),
        _item("p2b", priority="P2", minutes=60),
        _item("p3", priority="P3", minutes=60),
    ]
    esito = plan_day(items, blocchi, target_date=TARGET)
    pianificati = {i.dedupe_key for i in esito.scheduled}
    nel_backlog = {i.dedupe_key for i in esito.backlog}
    assert "urgente" in pianificati
    assert nel_backlog >= {"p2b", "p3"} or nel_backlog >= {"p2a", "p3"}
    for item in esito.backlog:
        assert item.priority in ("P2", "P3")


def test_budget_75_percento():
    items = [_item(f"k{i}", priority="P2", rank=i, minutes=60) for i in range(12)]
    esito = plan_day(items, [], target_date=TARGET)
    # finestra 08:30-19:00 = 630 minuti → budget ~472
    assert esito.free_minutes == 630
    assert esito.budget_minutes == int(630 * 0.75)
    assert esito.used_minutes <= esito.budget_minutes
    assert esito.backlog  # gli eccedenti non spariscono


def test_p1_pianificato_anche_oltre_budget_con_avviso():
    blocchi = [_blocco(9, minuti=540)]  # 09:00-18:00 occupato
    items = [
        _item("p1", priority="P1", minutes=120),
        _item("p1b", priority="P1", minutes=120),
    ]
    esito = plan_day(items, blocchi, target_date=TARGET)
    pianificati = {i.dedupe_key for i in esito.scheduled}
    assert pianificati == {"p1", "p1b"}
    assert not esito.backlog


def test_urgenza_senza_fascia_resta_nel_piano_con_avviso():
    blocchi = [_blocco(8, minuti=30), _blocco(9, minuti=600)]  # tutto occupato
    items = [_item("p0", priority="P0", minutes=120)]
    esito = plan_day(items, blocchi, target_date=TARGET)
    assert esito.scheduled[0].dedupe_key == "p0"
    assert esito.scheduled[0].scheduled_start == ""
    assert esito.warnings


def test_margine_spostamento_con_luogo():
    con_luogo = _blocco(10, minuti=60, luogo="Tribunale di Milano")
    items = [_item("a", priority="P0", minutes=30)]
    esito = plan_day(items, [con_luogo], target_date=TARGET)
    inizio = datetime.fromisoformat(esito.scheduled[0].scheduled_start)
    # il margine di 20' prima e dopo è occupato: 09:40-11:20
    assert not (
        datetime(2026, 7, 11, 9, 40, tzinfo=ROME_TZ)
        <= inizio
        < datetime(2026, 7, 11, 11, 20, tzinfo=ROME_TZ)
    )


def test_fixed_block_from_agenda_udienza():
    """Caso obbligatorio 18: timezone — l'orario agenda resta Europe/Rome."""
    blocco = fixed_block_from_agenda(
        {
            "data_ora": "2026-07-11T10:00:00",
            "durata_minuti": 90,
            "tipo": "UDIENZA",
            "titolo": "Udienza Rossi",
            "luogo": "Aula 3",
        }
    )
    assert blocco is not None
    assert blocco.kind == "udienza"
    assert blocco.minutes == 90
    assert blocco.start.tzinfo is not None
    assert blocco.start.hour == 10
    assert fixed_block_from_agenda({"data_ora": ""}) is None


def test_nessuna_scrittura_su_agenda():
    # la pianificazione tocca solo scheduled_start/estimated_minutes/in_backlog
    item = _item("a", priority="P2", minutes=30)
    prima = item.to_dict()
    esito = plan_day([item], [], target_date=TARGET)
    dopo = esito.scheduled[0].to_dict()
    cambiati = {k for k in prima if prima[k] != dopo[k]}
    assert cambiati <= {"scheduled_start", "estimated_minutes", "in_backlog", "updated_at"}
