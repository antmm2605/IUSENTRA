"""Battito dei presidi: dice se i job stanno davvero lavorando.

L'healthcheck del container verificava solo che il processo
``pct.scheduler_worker`` fosse vivo. Un worker vivo che non esegue piu' alcun
presidio — registro studi illeggibile, cursore fermo, job in errore — restava
quindi "healthy" mentre PEC, relata, fascicoli e notifiche tacevano.

Questo modulo legge il registro delle pianificazioni, che e' gia' la fonte
scritta dal listener APScheduler a ogni esecuzione, e ne ricava un esito
verificabile: per ciascun presidio l'ultimo stato, quando e' avvenuto e da quale
riga di registro proviene. Nessun dato viene stimato: se il registro non e'
leggibile lo dichiara.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

DEFAULT_REGISTRY_DB_NAME = "scheduler_registry.sqlite"

# Marcatore di avvio del worker: consente all'healthcheck di distinguere
# "non ha ancora girato" da "non gira piu'".
WORKER_START_MARKER = Path(os.getenv("IUSENTRA_SCHEDULER_START_MARKER", "/tmp/iusentra-scheduler-worker.start"))
WORKER_STARTUP_GRACE_MINUTES = 20

# Presidi che devono girare perche' lo studio veda arrivare il lavoro.
# La tolleranza e' il doppio abbondante della cadenza del job, cosi' un giro
# saltato per carico non fa scattare l'allarme ma due si'.
PRESIDIO_JOBS: tuple[tuple[str, str, int], ...] = (
    ("mailbox_sync_runtime", "Sincronizzazione caselle PEC", 45),
    ("pec_audit_pipeline_workers", "Presidio PEC e scadenze automatiche", 20),
    ("agenda_scadenziario_notifications", "Notifiche agenda e scadenziario", 20),
    ("legal_notification_relata_presidio", "Presidio relata di notifica", 45),
    ("fascicoli_document_economic_presidio", "Presidio documenti fascicolo", 45),
)


def mark_worker_started(now: datetime | None = None) -> None:
    """Registra l'avvio del worker; errori di scrittura non fermano l'avvio."""

    try:
        WORKER_START_MARKER.parent.mkdir(parents=True, exist_ok=True)
        WORKER_START_MARKER.write_text(
            (now or datetime.now(timezone.utc)).isoformat(), encoding="utf-8"
        )
    except OSError:
        return


def worker_startup_grace_active(
    now: datetime | None = None,
    *,
    grace_minutes: int = WORKER_STARTUP_GRACE_MINUTES,
) -> bool:
    """Vero se il worker e' partito da poco e il primo giro puo' non esserci ancora."""

    try:
        avvio = datetime.fromtimestamp(WORKER_START_MARKER.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return False
    return (now or datetime.now(timezone.utc)) - avvio < timedelta(minutes=max(1, int(grace_minutes)))


def _parse_iso(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def presidio_heartbeat(
    registry_repo: Any,
    *,
    now: datetime | None = None,
    jobs: tuple[tuple[str, str, int], ...] = PRESIDIO_JOBS,
) -> dict[str, Any]:
    """Stato dei presidi ricavato dal registro pianificazioni."""

    adesso = now or datetime.now(timezone.utc)
    try:
        latest: Mapping[str, Any] = registry_repo.latest_runs_by_job() or {}
    except Exception as exc:
        return {
            "ok": False,
            "error": f"registro pianificazioni non leggibile: {exc}",
            "source": "registro pianificazioni (scheduler_registry)",
            "presidi": [],
        }

    voci: list[dict[str, Any]] = []
    degradati = 0
    guasti_certi = 0
    for job_id, label, tolleranza_minuti in jobs:
        run = latest.get(job_id) if isinstance(latest, Mapping) else None
        run = run if isinstance(run, Mapping) else {}
        status = str(run.get("status") or "").strip().lower()
        finished_at = _parse_iso(
            run.get("finished_at") or run.get("updated_at") or run.get("started_at") or run.get("created_at")
        )
        eta_minuti = int((adesso - finished_at).total_seconds() // 60) if finished_at else None
        if not run:
            problema = "mai eseguito su questo worker"
        elif status in {"failed", "missed"}:
            problema = f"ultima esecuzione: {status}"
        elif eta_minuti is None:
            problema = "ultima esecuzione senza data registrata"
        elif eta_minuti > tolleranza_minuti:
            problema = f"ultima esecuzione {eta_minuti} minuti fa (tolleranza {tolleranza_minuti})"
        else:
            problema = ""
        if problema:
            degradati += 1
        if status in {"failed", "missed"}:
            guasti_certi += 1
        voci.append(
            {
                "job": job_id,
                "label": label,
                "status": status or "sconosciuto",
                "last_run": finished_at.isoformat() if finished_at else "",
                "minutes_ago": eta_minuti,
                "tolerance_minutes": tolleranza_minuti,
                "problem": problema,
                "message": str(run.get("message") or ""),
                "error": str(run.get("error_message") or ""),
                "source": f"registro pianificazioni — ultima esecuzione del job {job_id}",
            }
        )

    return {
        "ok": degradati == 0,
        "degraded": degradati,
        "hard_failures": guasti_certi,
        "checked": len(voci),
        "source": "registro pianificazioni (scheduler_registry), scritto dal worker a ogni esecuzione",
        "presidi": voci,
    }


def registry_db_path(config: Mapping[str, Any] | None = None) -> Path:
    """Percorso del registro, risolto senza importare il repository.

    L'healthcheck del container gira ogni 30 secondi: importare il repository
    (e con lui mezzo progetto) costerebbe circa un secondo di CPU a giro per
    leggere una riga di SQLite. La risoluzione e' volutamente identica a quella
    di ``pct.scheduler_registry._runtime_registry_db_path``, e un test verifica
    che le due non divergano.
    """

    cfg = dict(config or {})
    esplicito = (
        cfg.get("SCHEDULER_REGISTRY_DB")
        or cfg.get("IUSENTRA_SCHEDULER_REGISTRY_DB")
        or os.getenv("IUSENTRA_SCHEDULER_REGISTRY_DB")
    )
    if esplicito:
        return Path(str(esplicito))
    legal_db = cfg.get("LEGAL_INTELLIGENCE_DB") or os.getenv("LEGAL_INTELLIGENCE_DB")
    if legal_db:
        return Path(str(legal_db)).expanduser().resolve().parent / DEFAULT_REGISTRY_DB_NAME
    if Path("/data").exists():
        return Path("/data/intelligence") / DEFAULT_REGISTRY_DB_NAME
    return Path("intelligence") / DEFAULT_REGISTRY_DB_NAME


class _RegistroSoloLettura:
    """Lettore minimo del registro: solo sqlite3, nessun import di progetto."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def latest_runs_by_job(self) -> dict[str, dict[str, Any]]:
        if not self.db_path.exists():
            raise FileNotFoundError(f"registro assente: {self.db_path}")
        with sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True, timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT r.job_id, r.status, r.finished_at, r.started_at, r.created_at,
                       r.message, r.error_message
                FROM scheduled_job_runs r
                JOIN (
                    SELECT job_id, MAX(id) AS max_id
                    FROM scheduled_job_runs
                    GROUP BY job_id
                ) latest ON latest.max_id = r.id
                """
            ).fetchall()
        return {str(row["job_id"]): dict(row) for row in rows}


def presidio_heartbeat_for_config(config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Battito leggendo il registro dalla configurazione corrente."""

    percorso = registry_db_path(config)
    try:
        return presidio_heartbeat(_RegistroSoloLettura(percorso))
    except Exception as exc:
        return {
            "ok": False,
            "error": f"registro pianificazioni non apribile ({percorso}): {exc}",
            "source": "registro pianificazioni (scheduler_registry)",
            "presidi": [],
        }


def format_heartbeat_lines(report: Mapping[str, Any]) -> list[str]:
    """Righe leggibili per log e healthcheck del container."""

    if report.get("error"):
        return [f"presidi: {report['error']}"]
    righe = []
    for voce in report.get("presidi") or []:
        stato = "ok" if not voce.get("problem") else f"DEGRADATO — {voce['problem']}"
        righe.append(f"{voce['job']}: {stato}")
    return righe


def main(argv: list[str] | None = None) -> int:
    """Healthcheck del container: 0 se i presidi lavorano, 1 se sono fermi."""

    report = presidio_heartbeat_for_config()
    for riga in format_heartbeat_lines(report):
        print(riga)
    if report.get("ok"):
        return 0
    if worker_startup_grace_active() and not report.get("hard_failures"):
        print("presidi: avvio recente del worker, attesa del primo giro")
        return 0
    return 1


if __name__ == "__main__":  # pragma: no cover - entry point del container
    raise SystemExit(main())


__all__ = [
    "PRESIDIO_JOBS",
    "registry_db_path",
    "WORKER_STARTUP_GRACE_MINUTES",
    "mark_worker_started",
    "worker_startup_grace_active",
    "format_heartbeat_lines",
    "presidio_heartbeat",
    "presidio_heartbeat_for_config",
]
