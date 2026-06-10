"""Runtime tenant-aware per worker, digest e acquisizione automatica della pipeline PEC."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from flask import current_app, g, has_app_context

from pct.pec_pipeline import PecAuditRepository


def _path_from_mapping(paths: Mapping[str, Any], key: str, default: str) -> str:
    value = paths.get(key)
    if value:
        return str(value)
    if has_app_context() and current_app.config.get(key):
        return str(current_app.config[key])
    return default


def repository_from_paths(paths: Mapping[str, Any], *, tenant_label: str = "default") -> PecAuditRepository:
    email_db = Path(_path_from_mapping(paths, "EMAIL_CASELLA_DB", "./email/casella.json"))
    audit_db = Path(str(paths.get("PEC_AUDIT_DB") or email_db.parent / "pec_audit.sqlite"))
    return PecAuditRepository(
        audit_db,
        tenant_id="default",
        fascicoli_db_path=_path_from_mapping(paths, "FASCICOLI_DB", "./fascicoli/fascicoli.json"),
        fascicoli_docs_path=_path_from_mapping(paths, "FASCICOLI_DOCS", "./fascicoli/documenti"),
        scadenziario_db_path=_path_from_mapping(paths, "SCADENZIARIO_DB", "./scadenziario/scadenze.json"),
        agenda_db_path=_path_from_mapping(paths, "AGENDA_DB", "./agenda/appuntamenti.json"),
    )


def repository_for_current_request() -> PecAuditRepository:
    paths = getattr(g, "data_paths", {}) if has_app_context() else {}
    return repository_from_paths(paths or {}, tenant_label="default")


def run_workers_for_paths(paths: Mapping[str, Any], *, tenant_label: str, limit: int = 200) -> dict[str, Any]:
    repo = repository_from_paths(paths, tenant_label=tenant_label)
    return repo.run_pending_jobs(limit=limit, actor="scheduler")


def build_digest_for_paths(paths: Mapping[str, Any], *, tenant_label: str, digest_date: str | None = None) -> dict[str, Any]:
    repo = repository_from_paths(paths, tenant_label=tenant_label)
    return repo.build_daily_digest(digest_date=digest_date, actor="scheduler")


def local_email_sort_key(email_obj: Any) -> str:
    return str(
        getattr(email_obj, "timestamp", "")
        or getattr(email_obj, "data", "")
        or getattr(email_obj, "ricevuta_il", "")
        or ""
    )


def email_rilevante_per_presidio_pec(email_obj: Any) -> bool:
    allegati = " ".join(
        str(item.get("nome") or item.get("nome_file") or "")
        for item in list(getattr(email_obj, "allegati", []) or [])
        if isinstance(item, dict)
    ).lower()
    text = " ".join(
        str(value or "")
        for value in (
            getattr(email_obj, "oggetto", ""),
            getattr(email_obj, "mittente", ""),
            getattr(email_obj, "mittente_nome", ""),
            getattr(email_obj, "corpo_testo", ""),
            getattr(email_obj, "stato_pct", ""),
            allegati,
        )
    ).lower()
    status_pct = str(getattr(email_obj, "stato_pct", "") or "").upper()
    message_id = str(getattr(email_obj, "message_id", "") or "").strip()
    origin = str(getattr(email_obj, "origine", "") or "").lower()
    return bool(
        getattr(email_obj, "e_pst", False)
        or message_id
        or status_pct
        or "pec" in origin
        or "posta certificata" in text
        or "giustiziacert" in text
        or "ptel.giustizia" in text
        or "deposito telematico" in text
        or "daticert" in text
        or "postacert" in text
        or any(marker in status_pct for marker in ("WARN", "RIFIUT", "ERRORE", "ACCETT", "CONSEGN", "CONTROLL", "DEPOSIT"))
    )


def read_or_reconstruct_local_mime(gestore: Any, email_obj: Any) -> tuple[bytes, str]:
    raw_mime = gestore.leggi_eml_originale(email_obj)
    if raw_mime:
        return bytes(raw_mime), "originale"
    try:
        from pct.pec_control_tower import _reconstruct_email_archive_mime

        reconstructed = _reconstruct_email_archive_mime(gestore, email_obj)
    except Exception:
        reconstructed = b""
    if reconstructed:
        return bytes(reconstructed), "ricostruito"
    return b"", ""


def _record_auto_acquire_item(
    repo: PecAuditRepository,
    run_id: str,
    *,
    email_id: str,
    message_id: str = "",
    subject: str = "",
    status: str,
    detail: dict[str, Any] | None = None,
) -> None:
    try:
        repo.record_local_acquire_item(
            run_id,
            email_id=email_id,
            message_id=message_id,
            subject=subject,
            status=status,
            detail=detail or {},
        )
    except Exception:
        pass


def acquire_local_pec_for_paths(
    paths: Mapping[str, Any],
    *,
    tenant_label: str,
    batch_size: int = 25,
    scan_limit: int = 400,
) -> dict[str, Any]:
    """Acquisisce nel presidio PEC le email rilevanti non ancora presidiate.

    Versione automatica e a budget del percorso manuale "Acquisisci dal locale":
    legge le email più recenti dell'archivio, salta quelle già presidiate
    (per Message-ID header o per ultimo esito registrato) e ingerisce solo le
    nuove. I job accodati vengono poi lavorati da `run_workers_for_paths`
    (parse, classificazione, validazione con scadenza automatica in
    scadenziario/agenda, collegamento al fascicolo, digest).
    """

    from pct.email_client import GestioneEmailRicevute

    report: dict[str, Any] = {
        "scanned": 0,
        "relevant": 0,
        "ingested": 0,
        "duplicates": 0,
        "skipped_presided": 0,
        "missing_mime": 0,
        "errors": 0,
    }
    email_db = _path_from_mapping(paths, "EMAIL_CASELLA_DB", "./email/casella.json")
    if not Path(email_db).exists():
        return {**report, "skipped": True, "reason": "archivio email assente"}
    repo = repository_from_paths(paths, tenant_label=tenant_label)
    gestore = GestioneEmailRicevute(db_path=email_db)
    emails = sorted(
        gestore._carica().values(),  # noqa: SLF001 - presidio tenant-aware sulla casella locale
        key=local_email_sort_key,
        reverse=True,
    )[: max(1, int(scan_limit or 400))]
    report["scanned"] = len(emails)
    relevant = [item for item in emails if email_rilevante_per_presidio_pec(item)]
    report["relevant"] = len(relevant)
    if not relevant:
        return report
    known_headers = repo.ids_by_header_message_ids(
        str(getattr(item, "message_id", "") or "").strip() for item in relevant
    )
    presided_ids = repo.presided_email_ids(
        str(getattr(item, "id", "") or "") for item in relevant
    )
    candidates: list[Any] = []
    for item in relevant:
        email_id = str(getattr(item, "id", "") or "")
        header = str(getattr(item, "message_id", "") or "").strip()
        if (header and header in known_headers) or (email_id and email_id in presided_ids):
            report["skipped_presided"] += 1
            continue
        candidates.append(item)
        if len(candidates) >= max(1, int(batch_size or 25)):
            break
    if not candidates:
        return report
    run_id = ""
    try:
        run = repo.start_local_acquire_run(
            total_emails=len(candidates), batch_size=len(candidates), actor="scheduler"
        )
        run_id = str(run.get("id") or "")
    except Exception:
        run_id = ""
    for item in candidates:
        email_id = str(getattr(item, "id", "") or "")
        subject = str(getattr(item, "oggetto", "") or "")[:240]
        raw_mime, mime_source = read_or_reconstruct_local_mime(gestore, item)
        if not raw_mime:
            report["missing_mime"] += 1
            _record_auto_acquire_item(repo, run_id, email_id=email_id, subject=subject, status="missing_mime")
            continue
        try:
            result = repo.ingest_mime(
                raw_mime,
                account_email=str(
                    getattr(item, "destinatari", "") or getattr(item, "mittente", "") or "casella PEC locale"
                )[:240],
                folder=str(getattr(item, "cartella", "") or "INBOX"),
                imap_uid=str(getattr(item, "uid_imap", "") or f"auto:{email_id}"),
                actor="scheduler",
            )
            duplicate = bool(result.get("duplicate"))
            report["duplicates" if duplicate else "ingested"] += 1
            _record_auto_acquire_item(
                repo,
                run_id,
                email_id=email_id,
                message_id=str(result.get("id") or ""),
                subject=subject,
                status="duplicate" if duplicate else "ingested",
                detail={"mime_source": mime_source, "origin": "auto"},
            )
        except Exception as exc:
            report["errors"] += 1
            _record_auto_acquire_item(
                repo,
                run_id,
                email_id=email_id,
                subject=subject,
                status="processed",
                detail={"errore": str(exc)[:180], "origin": "auto"},
            )
    if run_id:
        try:
            repo.update_local_acquire_run(
                run_id,
                cursor_index=len(candidates),
                total_emails=len(candidates),
                batch_size=len(candidates),
                deltas={
                    "acquired": int(report["ingested"]) + int(report["duplicates"]),
                    "duplicates": int(report["duplicates"]),
                    "skipped_missing_mime": int(report["missing_mime"]),
                    "errors": int(report["errors"]),
                },
                status="completed",
                payload={"origin": "auto", "tenant_label": tenant_label},
                actor="scheduler",
            )
        except Exception:
            pass
    return report
