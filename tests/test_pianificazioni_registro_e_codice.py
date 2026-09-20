"""Il registro delle pianificazioni e il codice devono dire lo stesso orario.

Lo scheduler non legge il `CronTrigger` scritto in `pct/scheduler.py`: legge
la riga in `scheduled_jobs`, che nasce dal template del registro. E
`upsert_default_jobs` non riscrive mai hour/minute di una riga gia'
esistente — aggiorna nome, famiglia e descrizione, non l'orario.

Ne segue una trappola vera, in cui siamo gia' caduti nella 2.331.0: si
cambia il `CronTrigger`, la modifica passa la CI, il deploy va a buon fine,
e in produzione il job continua a girare con l'orario di prima senza che
niente lo segnali. L'unico canale che aggiorna le righe esistenti e'
`_SYSTEM_CRON_MIGRATIONS`.

Questi controlli tengono allineate le tre cose: il trigger nel codice, il
template nel registro e la migrazione che porta li' le righe gia' scritte.
"""

from __future__ import annotations

import ast
from pathlib import Path

from pct.scheduler_registry import SchedulerRegistryRepository, default_scheduler_templates

SORGENTE_SCHEDULER = Path(__file__).resolve().parents[1] / "pct" / "scheduler.py"


def _campo(valore: object) -> str:
    """Un campo cron confrontabile: `3`, `"3"` e `None` non sono tre cose diverse."""
    return str(valore if valore is not None else "").strip()


def trigger_dichiarati_nel_codice() -> dict[str, dict[str, str]]:
    """Gli orari scritti nei decoratori `@scheduler.scheduled_job(CronTrigger(...))`.

    Solo quelli con valori letterali: i quattro job che leggono l'orario
    dalla configurazione dello studio non hanno un orario fisso da
    confrontare, e vanno lasciati fuori invece che indovinati.
    """
    # utf-8-sig: il file ha il BOM, e senza toglierlo ast non lo legge.
    albero = ast.parse(SORGENTE_SCHEDULER.read_text(encoding="utf-8-sig"))
    trovati: dict[str, dict[str, str]] = {}
    for nodo in ast.walk(albero):
        for decoratore in getattr(nodo, "decorator_list", []) or []:
            if not isinstance(decoratore, ast.Call):
                continue
            funzione = decoratore.func
            if not (isinstance(funzione, ast.Attribute) and funzione.attr == "scheduled_job"):
                continue
            job_id = next(
                (
                    k.value.value
                    for k in decoratore.keywords
                    if k.arg == "id" and isinstance(k.value, ast.Constant)
                ),
                None,
            )
            trigger = decoratore.args[0] if decoratore.args else None
            if not (
                job_id
                and isinstance(trigger, ast.Call)
                and getattr(trigger.func, "id", "") == "CronTrigger"
            ):
                continue
            campi: dict[str, str] = {}
            letterale = True
            for chiave in trigger.keywords:
                if isinstance(chiave.value, ast.Constant):
                    campi[str(chiave.arg)] = _campo(chiave.value.value)
                else:
                    letterale = False
            if letterale:
                trovati[str(job_id)] = campi
    return trovati


def test_il_lettore_dei_trigger_trova_davvero_qualcosa():
    """Un controllo che non confronta niente passerebbe sempre."""

    trigger = trigger_dichiarati_nel_codice()

    assert len(trigger) >= 30, f"letti solo {len(trigger)} trigger: il lettore si e' rotto"
    assert "lex_sentenza_economia_auto" in trigger


def test_ogni_orario_nel_codice_esiste_uguale_nel_registro():
    """Se divergono, in produzione vale il registro e il codice mente."""

    trigger = trigger_dichiarati_nel_codice()
    divergenze = []
    confrontati = 0
    for template in default_scheduler_templates({}):
        if template.trigger_kind != "cron" or template.key not in trigger:
            continue
        confrontati += 1
        nel_codice = trigger[template.key]
        atteso = (
            _campo(nel_codice.get("hour")),
            _campo(nel_codice.get("minute")),
            _campo(nel_codice.get("day_of_week")),
        )
        nel_registro = (
            _campo(template.hour),
            _campo(template.minute),
            _campo(template.day_of_week),
        )
        if atteso != nel_registro:
            divergenze.append(f"{template.key}: codice {atteso} != registro {nel_registro}")

    assert confrontati >= 30, f"confrontati solo {confrontati} template"
    assert not divergenze, (
        "Orari diversi fra pct/scheduler.py e il template del registro.\n"
        + "\n".join(divergenze)
        + "\n\nIn produzione vale il registro: allinea il template e aggiungi la "
        "voce in _SYSTEM_CRON_MIGRATIONS, altrimenti le righe gia' scritte "
        "restano all'orario vecchio."
    )


def test_ogni_migrazione_porta_a_un_orario_che_esiste_nel_registro():
    """Una migrazione verso un orario che nessun template prevede e' un refuso."""

    per_chiave = {t.key: t for t in default_scheduler_templates({})}
    sbagliate = []
    for job_id, _oh, _om, ora_nuova, minuto_nuovo in SchedulerRegistryRepository._SYSTEM_CRON_MIGRATIONS:
        template = per_chiave.get(job_id)
        if template is None:
            sbagliate.append(f"{job_id}: nessun template con questa chiave")
            continue
        destinazione = (_campo(ora_nuova), _campo(minuto_nuovo))
        nel_registro = (_campo(template.hour), _campo(template.minute))
        if destinazione != nel_registro:
            sbagliate.append(f"{job_id}: migrazione verso {destinazione}, template {nel_registro}")

    assert not sbagliate, "Migrazioni che puntano a un orario diverso dal template:\n" + "\n".join(
        sbagliate
    )


def test_nessuna_migrazione_parte_dall_orario_di_arrivo():
    """Una migrazione da X a X non converge: gira a vuoto a ogni riavvio."""

    inutili = [
        job_id
        for job_id, oh, om, nh, nm in SchedulerRegistryRepository._SYSTEM_CRON_MIGRATIONS
        if (_campo(oh), _campo(om)) == (_campo(nh), _campo(nm))
    ]

    assert not inutili, f"Migrazioni che non cambiano niente: {inutili}"


def test_le_sentenze_lex_girano_una_volta_a_notte():
    """La 2.331.0 voleva questo, e per un commit non e' successo.

    Il giro ogni dieci minuti costava 144 ricognizioni al giorno per
    concluderne zero: adesso il lavoro parte all'arrivo dei documenti, e
    resta solo la ricognizione di sicurezza notturna.
    """

    template = {t.key: t for t in default_scheduler_templates({})}["lex_sentenza_economia_auto"]

    assert (_campo(template.hour), _campo(template.minute)) == ("3", "25")
    assert trigger_dichiarati_nel_codice()["lex_sentenza_economia_auto"] == {
        "hour": "3",
        "minute": "25",
    }
    partenze = {
        (_campo(om))
        for job_id, _oh, om, _nh, _nm in SchedulerRegistryRepository._SYSTEM_CRON_MIGRATIONS
        if job_id == "lex_sentenza_economia_auto"
    }
    assert partenze == {"7-57/10", "*/10"}, (
        "Le righe scritte con gli orari vecchi devono arrivare tutte a 03:25."
    )
