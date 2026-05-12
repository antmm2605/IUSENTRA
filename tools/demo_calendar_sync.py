"""Demo eseguibile del motore bidirezionale calendario IUSENTRA."""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pct.agenda import TipoAppuntamento
from pct.calendar_sync_engine import CalendarSyncEngine, PRIVACY_BUSY, PRIVACY_REDUCED, privacy_export_event
from pct.scadenziario import TipoTermine


def _root() -> Path:
    return Path(os.getenv("IUSENTRA_CALENDAR_DEMO_ROOT", "data/demo_calendar_sync")).resolve()


def _engine(root: Path) -> CalendarSyncEngine:
    return CalendarSyncEngine.from_paths(
        agenda_db=str(root / "agenda.json"),
        scadenziario_db=str(root / "scadenze.json"),
        sync_db=str(root / "calendar_sync.json"),
        tenant_id="demo-calendar-sync",
    )


def _connect(engine: CalendarSyncEngine, run_id: str):
    account = engine.repository.upsert_account(
        {
            "tenant_id": engine.tenant_id,
            "provider": "demo",
            "display_name": "Account prova calendario",
            "email": f"prova-{run_id}@iusentra.local",
            "auth_type": "demo",
            "encrypted_credentials": engine.credentials.encrypt({"mode": "demo", "run_id": run_id}),
            "status": "active",
        }
    )
    calendar = engine.repository.upsert_calendar(
        {
            "tenant_id": engine.tenant_id,
            "account_id": account["id"],
            "provider": "demo",
            "provider_calendar_id": f"calendar-{run_id}",
            "name": "Calendario prova bidirezionale",
            "role": "completo",
            "direction": "bidirectional",
            "enabled": True,
            "privacy_level": PRIVACY_REDUCED,
        }
    )
    return account, calendar


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def main() -> int:
    root = _root()
    root.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex[:8]
    engine = _engine(root)
    account, calendar = _connect(engine, run_id)
    provider = engine.providers["demo"]
    start = (datetime.now() + timedelta(days=30, minutes=int(run_id[:2], 16) % 120)).replace(second=0, microsecond=0)

    print("DEMO CALENDAR SYNC IUSENTRA\n")
    _ok("Account demo creato")
    _ok("Calendario demo collegato bidirezionale")

    appointment = None
    for offset in range(0, 24 * 60, 75):
        try:
            appointment = engine.agenda.aggiungi(
                titolo=f"Udienza prova {run_id}",
                tipo=TipoAppuntamento.UDIENZA,
                data_ora=(start + timedelta(minutes=offset)).isoformat(timespec="seconds"),
                durata_minuti=60,
                luogo="Tribunale",
                cliente="Cliente riservato",
                procedimento="RG 100/2026",
                note="Nota riservata non esportata nel livello ridotto",
            )
            break
        except ValueError as exc:
            if "Sovrapposizione" not in str(exc):
                raise
    if appointment is None:
        raise RuntimeError("Nessuno slot libero disponibile per la prova calendario.")
    _ok("Evento IUSENTRA creato")

    pushed = engine.push_local_event("agenda", appointment.id, account["id"], calendar["id"])
    binding = pushed["binding"]
    assert provider.get_event(binding["external_event_id"])
    _ok("Push IUSENTRA -> Demo Calendar")
    _ok("Binding creato")

    provider.update_remote_event(
        binding["external_event_id"],
        {
            "title": f"[UDIENZA] Udienza aggiornata {run_id}",
            "description": "Aggiornamento arrivato dal calendario esterno",
        },
    )
    _ok("Evento remoto demo modificato")
    engine.pull_remote_changes(account["id"], calendar["id"])
    assert engine.agenda.get(appointment.id).titolo == f"Udienza aggiornata {run_id}"
    _ok("Pull Demo Calendar -> IUSENTRA")

    engine.agenda.modifica(appointment.id, titolo=f"Versione IUSENTRA {run_id}")
    provider.update_remote_event(binding["external_event_id"], {"title": f"Versione esterna {run_id}"})
    conflict_report = engine.pull_remote_changes(account["id"], calendar["id"])
    assert conflict_report["conflicts"] >= 1
    _ok("Conflitto locale/remoto rilevato")

    deadline = engine.scadenziario.nuova(
        titolo=f"Scadenza perentoria {run_id}",
        tipo=TipoTermine.TERMINE_PERENTORIO,
        data_scadenza=(start.date() + timedelta(days=10)).isoformat(),
        perentorio=True,
    )
    deadline_push = engine.push_local_event("scadenza", deadline.id, account["id"], calendar["id"])
    provider.delete_remote_event(deadline_push["binding"]["external_event_id"])
    protected = engine.pull_remote_changes(account["id"], calendar["id"])
    assert protected["conflicts"] >= 1
    assert engine.scadenziario.get(deadline.id).stato.value == "APERTO"
    _ok("Scadenza perentoria protetta da cancellazione remota")

    busy = privacy_export_event("agenda", engine.agenda.get(appointment.id), PRIVACY_BUSY)
    assert busy["title"] == "Occupato"
    assert "Cliente" not in busy["description"]
    _ok("Privacy export busy_only verificata")

    print("\nDemo completata con successo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
