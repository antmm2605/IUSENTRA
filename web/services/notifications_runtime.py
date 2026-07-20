"""Runtime Flask condiviso per il centro notifiche persistente."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

from flask import current_app, g, has_app_context

from pct.notifications import NotificationRepository, NotificationService
from pct.notifications.web_push import load_web_push_config
from pct.postgres_runtime_support import resolve_runtime_postgres_dsn
from web.helpers import tenant_corrente


LEGAL_NOTIFICATION_SOURCE_TYPE = "legal_notification_presidio"
LEGAL_NOTIFICATION_TO_NOTIFY_STATUSES = {"da_preparare", "da_firmare", "pronta_invio"}
LEGAL_NOTIFICATION_ACTIONABLE_STATUSES = LEGAL_NOTIFICATION_TO_NOTIFY_STATUSES | {"da_acquisire", "ricevute_da_completare"}


def current_tenant_id() -> str:
    tenant = tenant_corrente()
    value = (
        getattr(tenant, "id", "")
        or getattr(tenant, "slug", "")
        or getattr(g, "tenant_context_slug", "")
        or "default"
    )
    return str(value or "default").strip()


def current_user_id(user: Any | None = None) -> str:
    current = user if user is not None else g.get("utente_corrente")
    return str(getattr(current, "id", "") or getattr(current, "username", "") or "").strip()


def _runtime_config(config: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    if config is not None:
        return config
    return current_app.config if has_app_context() else {}


def notification_repository_settings(
    paths: Mapping[str, Any] | None = None,
    *,
    database: Any = None,
    config: Mapping[str, Any] | None = None,
) -> tuple[str, str]:
    """Risolve backend e path con lo stesso contratto per API e scheduler."""

    data_paths = paths or {}
    cfg = _runtime_config(config)
    configured = str(data_paths.get("NOTIFICATIONS_DB") or cfg.get("NOTIFICATIONS_DB") or "").strip()
    if configured:
        db_path = configured
    else:
        fallback = Path(str(data_paths.get("NOTIFICHE_LOG") or cfg.get("NOTIFICHE_LOG") or "./notifiche/log.json"))
        db_path = str(fallback.with_name("notifications.db"))
    postgres_dsn = resolve_runtime_postgres_dsn(
        database=database or data_paths.get("_TENANT_DATABASE_CONFIG"),
        config=cfg,
        env_url_keys=("IUSENTRA_NOTIFICATIONS_DATABASE_URL", "PCT_NOTIFICATIONS_DATABASE_URL"),
    )
    return db_path, postgres_dsn


def notifications_db_path() -> str:
    paths = getattr(g, "data_paths", {}) or {}
    if getattr(g, "tenant_context_missing", False):
        raise RuntimeError(
            "Contesto studio non disponibile per la richiesta corrente. "
            "Accesso ai dati bloccato per evitare letture cross-studio."
        )
    return notification_repository_settings(paths, config=current_app.config)[0]


def build_notification_repository_for_paths(
    paths: Mapping[str, Any] | None = None,
    *,
    database: Any = None,
    config: Mapping[str, Any] | None = None,
) -> NotificationRepository:
    db_path, postgres_dsn = notification_repository_settings(
        paths,
        database=database,
        config=config,
    )
    cache_key = f"{db_path}|{postgres_dsn}"
    if has_app_context():
        cache = current_app.extensions.setdefault("notification_repositories", {})
        repo = cache.get(cache_key)
        if isinstance(repo, NotificationRepository):
            return repo
    repo = NotificationRepository(db_path, postgres_dsn=postgres_dsn)
    if has_app_context():
        current_app.extensions["notification_repositories"][cache_key] = repo
    return repo


def build_notification_repository() -> NotificationRepository:
    paths = getattr(g, "data_paths", {}) or {}
    if getattr(g, "tenant_context_missing", False):
        notifications_db_path()
    tenant = tenant_corrente()
    return build_notification_repository_for_paths(
        paths,
        database=getattr(tenant, "database", None),
        config=current_app.config,
    )


def build_notification_service() -> NotificationService:
    return NotificationService(
        build_notification_repository(),
        web_push_config=load_web_push_config(current_app.config),
    )


def _core_backend_for_paths(paths: Mapping[str, Any], database: Any = None):
    studio_db_path = str(paths.get("STUDIO_DB") or "").strip()
    database_config = database or paths.get("_TENANT_DATABASE_CONFIG")
    if database_config is not None and studio_db_path:
        try:
            from pct.core_storage_backend import build_core_storage_backend

            backend = build_core_storage_backend(database_config, studio_db_path=studio_db_path)
            if backend is not None:
                return backend
        except Exception:
            pass
    if studio_db_path and Path(studio_db_path).exists():
        try:
            from pct.storage import StudioDB

            return StudioDB.get(studio_db_path)
        except Exception:
            pass
    return None


def notification_recipients_for_paths(
    paths: Mapping[str, Any],
    *,
    database: Any = None,
) -> list[Any]:
    from pct.auth import GestioneUtenti

    auth_db = str(paths.get("AUTH_DB") or "./auth/utenti.json")
    backend = _core_backend_for_paths(paths, database)
    if not Path(auth_db).exists() and backend is None:
        return []
    audit_db = str(paths.get("AUDIT_DB") or "./auth/audit.json")
    secret = str(current_app.config.get("SECRET_KEY") or "scheduler") if has_app_context() else "scheduler"
    gestore = GestioneUtenti(
        db_path=auth_db,
        audit_path=audit_db,
        secret_key=secret,
        crea_admin_se_vuoto=False,
        studio_db=backend,
    )
    return list(gestore.tutti(solo_attivi=True))


def materialize_agenda_scadenziario_notifications_for_paths(
    paths: Mapping[str, Any],
    *,
    tenant_label: str,
    tenant_id: str = "",
    database: Any = None,
) -> dict[str, Any]:
    """Materializza centro notifiche e push senza dipendere dall'apertura UI."""

    from pct.agenda import Agenda
    from pct.scadenziario import GestioneScadenziario
    from web.services.topbar_operational import agenda_scadenziario_notification_items

    database_config = database or paths.get("_TENANT_DATABASE_CONFIG")
    backend = _core_backend_for_paths(paths, database_config)
    agenda = Agenda(
        db_path=str(paths.get("AGENDA_DB") or "./agenda/appuntamenti.json"),
        studio_db=backend,
    )
    scadenziario = GestioneScadenziario(
        db_path=str(paths.get("SCADENZIARIO_DB") or "./scadenziario/scadenze.json"),
        studio_db=backend,
    )
    recipients = notification_recipients_for_paths(paths, database=database_config)
    config = _runtime_config()
    service = NotificationService(
        build_notification_repository_for_paths(paths, database=database_config, config=config),
        web_push_config=load_web_push_config(config),
    )
    resolved_tenant_id = str(
        tenant_id
        or paths.get("_TENANT_NOTIFICATION_ID")
        or tenant_label
        or "default"
    ).strip()
    report = {
        "ok": True,
        "tenant": str(tenant_label or "default"),
        "source_of_truth": "notification repository SQLite/PostgreSQL tenant-aware",
        "recipients": 0,
        "items": 0,
        "errors": 0,
    }
    for user in recipients:
        try:
            can_agenda = not hasattr(user, "ha_permesso") or bool(user.ha_permesso("agenda.leggi"))
            can_scadenziario = not hasattr(user, "ha_permesso") or bool(user.ha_permesso("scadenziario.leggi"))
            if not can_agenda and not can_scadenziario:
                continue
            user_id = str(getattr(user, "id", "") or getattr(user, "username", "") or "").strip()
            if not user_id:
                continue
            items = agenda_scadenziario_notification_items(
                agenda,
                scadenziario,
                include_agenda=can_agenda,
                include_scadenziario=can_scadenziario,
            )
            service.sync_operational_items(
                tenant_id=resolved_tenant_id,
                user_id=user_id,
                items=items,
                expire_source_types={"deadline", "hearing", "task"},
            )
            report["recipients"] += 1
            report["items"] += len(items)
        except Exception:
            report["errors"] += 1
    report["ok"] = report["errors"] == 0
    return report


def _notification_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _notification_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _notification_text(value).casefold() in {"1", "true", "vero", "si", "sì", "yes"}


def _notification_json(value: Any, default: Any) -> Any:
    if isinstance(value, (list, dict)):
        return value
    raw = _notification_text(value)
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def _notification_document_rows(value: Any) -> list[dict[str, Any]]:
    raw = _notification_json(value, [])
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        for key in ("documenti", "documents", "items", "rows", "data"):
            rows = raw.get(key)
            if isinstance(rows, list):
                return [item for item in rows if isinstance(item, dict)]
    return []


def _notification_doc(row: Mapping[str, Any], index: int) -> SimpleNamespace:
    name = _notification_text(
        row.get("nome")
        or row.get("name")
        or row.get("filename")
        or row.get("safe_filename")
        or row.get("nome_originale")
        or row.get("original_filename")
        or f"Documento {index + 1}"
    )
    tags = row.get("tags") or row.get("etichette") or []
    if isinstance(tags, str):
        tags = [tags]
    if not isinstance(tags, list):
        tags = []
    return SimpleNamespace(
        id=_notification_text(row.get("id") or row.get("documento_id") or row.get("uuid") or f"doc-{index + 1}"),
        nome=name,
        nome_originale=_notification_text(row.get("nome_originale") or row.get("original_filename") or row.get("filename") or name),
        nome_portale=_notification_text(row.get("nome_portale") or row.get("portal_name") or row.get("nomePortale") or name),
        tipo=_notification_text(row.get("tipo") or row.get("type") or row.get("tipo_documento") or row.get("tipoDocumento")),
        tipo_atto_portale=_notification_text(row.get("tipo_atto_portale") or row.get("tipoAttoPortale")),
        classificazione_portale=_notification_text(row.get("classificazione_portale") or row.get("classificazionePortale") or row.get("catalogRole")),
        note=_notification_text(row.get("note") or row.get("notes") or row.get("descrizione") or row.get("description")),
        tags=tags,
        percorso=_notification_text(row.get("percorso") or row.get("path") or row.get("storage_path") or row.get("file")),
        hash_sha256=_notification_text(row.get("hash_sha256") or row.get("sha256") or row.get("hashSha256")),
        prova_notifica=_notification_bool(row.get("prova_notifica") or row.get("provaNotifica")),
        data_documento=_notification_text(row.get("data_documento") or row.get("dataDocumento") or row.get("date")),
        data_deposito_portale=_notification_text(row.get("data_deposito_portale") or row.get("dataDepositoPortale") or row.get("data_deposito")),
        data_notifica=_notification_text(row.get("data_notifica") or row.get("dataNotifica")),
        data_comunicazione_cancelleria=_notification_text(row.get("data_comunicazione_cancelleria") or row.get("dataComunicazioneCancelleria")),
        signed_status=row.get("signed_status") or row.get("signedStatus"),
        signed_ui=row.get("signed_ui") or row.get("signedUi"),
        firma_status=row.get("firma_status") or row.get("firmaStatus"),
        firma_esito=row.get("firma_esito") or row.get("firmaEsito"),
        metadati_firma=row.get("metadati_firma") or row.get("metadatiFirma"),
        signature_metadata=row.get("signature_metadata") or row.get("signatureMetadata"),
        signature_status=row.get("signature_status") or row.get("signatureStatus"),
    )


def _notification_row_value(row: sqlite3.Row, key: str) -> Any:
    try:
        return row[key]
    except Exception:
        return ""


def _notification_fascicolo_from_row(row: sqlite3.Row) -> SimpleNamespace:
    docs = [
        _notification_doc(item, index)
        for index, item in enumerate(_notification_document_rows(_notification_row_value(row, "documenti_json")))
    ]
    title = _notification_text(
        _notification_row_value(row, "titolo")
        or _notification_row_value(row, "nome")
        or _notification_row_value(row, "oggetto")
        or _notification_row_value(row, "id")
    )
    return SimpleNamespace(
        id=_notification_text(_notification_row_value(row, "id")),
        codice=_notification_text(_notification_row_value(row, "codice")),
        titolo=title,
        nome=title,
        oggetto=_notification_text(_notification_row_value(row, "oggetto") or _notification_row_value(row, "descrizione") or title),
        nome_cliente=_notification_text(_notification_row_value(row, "nome_cliente") or _notification_row_value(row, "cliente")),
        parti=_notification_text(_notification_row_value(row, "parti")),
        controparte=_notification_text(_notification_row_value(row, "controparte")),
        ufficio=_notification_text(_notification_row_value(row, "ufficio")),
        numero_rg=_notification_text(_notification_row_value(row, "numero_rg")),
        anno_rg=_notification_text(_notification_row_value(row, "anno_rg")),
        stato=_notification_text(_notification_row_value(row, "stato")),
        documenti=docs,
    )


def _notification_fascicolo_rows(studio_db_path: str) -> tuple[int, int, list[sqlite3.Row]]:
    db_path = Path(studio_db_path)
    if not db_path.exists():
        return 0, 0, []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(fascicoli)").fetchall()}
        wanted = [
            "id",
            "codice",
            "titolo",
            "nome",
            "oggetto",
            "descrizione",
            "cliente",
            "nome_cliente",
            "parti",
            "controparte",
            "ufficio",
            "numero_rg",
            "anno_rg",
            "stato",
            "documenti_json",
        ]
        selected = [column for column in wanted if column in columns]
        if "id" not in selected or "documenti_json" not in selected:
            return 0, 0, []
        order_columns = [column for column in ("titolo", "nome", "oggetto", "id") if column in columns]
        order_by = f"COALESCE({', '.join(order_columns)})" if len(order_columns) > 1 else order_columns[0]
        rows = list(conn.execute(f"SELECT {', '.join(selected)} FROM fascicoli ORDER BY {order_by}"))
    finally:
        conn.close()
    total = len(rows)
    archived_ids = {
        _notification_text(_notification_row_value(row, "id"))
        for row in rows
        if _notification_text(_notification_row_value(row, "stato")).casefold() in {"archiviato", "archiviata", "archived"}
    }
    visible = [row for row in rows if _notification_text(_notification_row_value(row, "id")) not in archived_ids]
    return total, len(archived_ids), visible


def _legal_notification_next_step(status: str) -> str:
    return {
        "da_acquisire": "Acquisire il provvedimento indicato dalla PEC/portale prima di preparare la relata.",
        "da_preparare": "Preparare la relata di notifica con i dati del fascicolo e del documento da notificare.",
        "da_firmare": "Firmare digitalmente la relata già presente, poi procedere alla revisione/invio.",
        "pronta_invio": "Revisionare e inviare la notifica dal PC dell'avvocato tramite canale locale autorizzato.",
        "ricevute_da_completare": "Collegare RAC/RdAC o prova deposito: non è una nuova notifica da inviare.",
    }.get(status, "Nessuna azione di notifica residua.")


def _legal_notification_title(status: str, fascicolo: Any) -> str:
    label = _notification_text(getattr(fascicolo, "titolo", "")) or _notification_text(getattr(fascicolo, "id", ""))
    if status in LEGAL_NOTIFICATION_TO_NOTIFY_STATUSES:
        return f"Notifica da presidiare - {label}"[:220]
    return f"Presidio notifica - {label}"[:220]


def _legal_notification_item(fascicolo: Any, payload: Mapping[str, Any]) -> dict[str, Any] | None:
    status = _notification_text(payload.get("status"))
    if status not in LEGAL_NOTIFICATION_ACTIONABLE_STATUSES:
        return None
    fid = _notification_text(getattr(fascicolo, "id", ""))
    if not fid:
        return None
    priority = "urgent" if status == "da_acquisire" else "important" if status in LEGAL_NOTIFICATION_TO_NOTIFY_STATUSES else "normal"
    href = _notification_text(payload.get("primaryHref") or payload.get("prepareHref") or f"/fascicoli/{fid}#relata-notifica")
    next_step = _legal_notification_next_step(status)
    body = _notification_text(payload.get("systemNotification")) or next_step
    return {
        "id": f"legal-notification:{fid}:{status}",
        "type": LEGAL_NOTIFICATION_SOURCE_TYPE,
        "priority": priority,
        "title": _legal_notification_title(status, fascicolo),
        "message": f"{body} {next_step}".strip(),
        "href": href,
        "actionLabel": _notification_text(payload.get("primaryLabel") or "Apri presidio"),
        "createdAt": "",
    }


def _sync_legal_notification_deadlines(paths: Mapping[str, Any], items: list[dict[str, Any]], *, database: Any = None) -> dict[str, int]:
    from datetime import date, datetime

    from pct.scadenziario import GestioneScadenziario, StatoTermine, TipoTermine

    database_config = database or paths.get("_TENANT_DATABASE_CONFIG")
    backend = _core_backend_for_paths(paths, database_config)
    scadenziario = GestioneScadenziario(
        db_path=str(paths.get("SCADENZIARIO_DB") or "./scadenziario/scadenze.json"),
        studio_db=backend,
    )
    active_markers = {f"IUSENTRA_LEGAL_NOTIFICATION:{item['id']}" for item in items}
    existing = []
    for deadline in scadenziario.tutte(solo_aperte=False):
        note = _notification_text(getattr(deadline, "note", ""))
        if "IUSENTRA_LEGAL_NOTIFICATION:" in note:
            existing.append(deadline)
    created = 0
    updated = 0
    completed = 0
    by_marker = {
        marker: next((deadline for deadline in existing if marker in _notification_text(getattr(deadline, "note", ""))), None)
        for marker in active_markers
    }
    today = date.today().isoformat()
    for item in items:
        if item["id"].split(":")[-1] not in LEGAL_NOTIFICATION_TO_NOTIFY_STATUSES:
            continue
        marker = f"IUSENTRA_LEGAL_NOTIFICATION:{item['id']}"
        note = f"{marker}\n{_notification_text(item.get('message'))}"
        current = by_marker.get(marker)
        if current and getattr(current, "stato", None) == StatoTermine.APERTO:
            scadenziario.aggiorna(
                current.id,
                titolo=_notification_text(item.get("title"), "Notifica da presidiare"),
                descrizione=_notification_text(item.get("message")),
                data_scadenza=today,
                source_event_type=LEGAL_NOTIFICATION_SOURCE_TYPE,
                note=note,
            )
            updated += 1
        else:
            scadenziario.nuova(
                titolo=_notification_text(item.get("title"), "Notifica da presidiare"),
                tipo=TipoTermine.NOTIFICA,
                data_scadenza=today,
                descrizione=_notification_text(item.get("message")),
                note=note,
                source_event_type=LEGAL_NOTIFICATION_SOURCE_TYPE,
                giorni_preavviso=[0],
            )
            created += 1
    for deadline in existing:
        note = _notification_text(getattr(deadline, "note", ""))
        if getattr(deadline, "stato", None) == StatoTermine.APERTO and not any(marker in note for marker in active_markers):
            scadenziario.aggiorna(
                deadline.id,
                stato=StatoTermine.COMPLETATO,
                completata_il=datetime.now().isoformat(timespec="seconds"),
            )
            completed += 1
    return {"created": created, "updated": updated, "completed": completed}


def materialize_notification_relata_presidio_for_paths(
    paths: Mapping[str, Any],
    *,
    tenant_label: str,
    tenant_id: str = "",
    database: Any = None,
) -> dict[str, Any]:
    """Materializza residui notifica fascicoli in topbar, Web Push e scadenziario senza rallentare la UI."""

    from web.services.react_fascicoli_bridge import _notification_relata

    studio_db = _notification_text(paths.get("STUDIO_DB"))
    total, archived, rows = _notification_fascicolo_rows(studio_db)
    items: list[dict[str, Any]] = []
    status_counts: dict[str, int] = {}
    for row in rows:
        fascicolo = _notification_fascicolo_from_row(row)
        payload = _notification_relata(fascicolo, [])
        status = _notification_text(payload.get("status"), "monitoraggio")
        status_counts[status] = status_counts.get(status, 0) + 1
        item = _legal_notification_item(fascicolo, payload)
        if item:
            items.append(item)

    database_config = database or paths.get("_TENANT_DATABASE_CONFIG")
    recipients = notification_recipients_for_paths(paths, database=database_config)
    config = _runtime_config()
    service = NotificationService(
        build_notification_repository_for_paths(paths, database=database_config, config=config),
        web_push_config=load_web_push_config(config),
    )
    resolved_tenant_id = _notification_text(
        tenant_id
        or paths.get("_TENANT_NOTIFICATION_ID")
        or tenant_label
        or "default"
    )
    synced_recipients = 0
    errors = 0
    for user in recipients:
        try:
            can_read = not hasattr(user, "ha_permesso") or bool(user.ha_permesso("fascicoli.leggi"))
            if not can_read:
                continue
            user_id = _notification_text(getattr(user, "id", "") or getattr(user, "username", ""))
            if not user_id:
                continue
            service.sync_operational_items(
                tenant_id=resolved_tenant_id,
                user_id=user_id,
                items=items,
                expire_source_types={LEGAL_NOTIFICATION_SOURCE_TYPE},
            )
            synced_recipients += 1
        except Exception:
            errors += 1
    calendar_report = _sync_legal_notification_deadlines(paths, items, database=database_config)
    return {
        "ok": errors == 0,
        "tenant": _notification_text(tenant_label, "default"),
        "source_of_truth": "studio.db fascicoli.documenti_json + notification repository tenant-aware",
        "total_db": total,
        "archived_skipped": archived,
        "scanned": len(rows),
        "items": len(items),
        "to_notify": sum(1 for item in items if item["id"].split(":")[-1] in LEGAL_NOTIFICATION_TO_NOTIFY_STATUSES),
        "recipients": synced_recipients,
        "errors": errors,
        "calendar": calendar_report,
        "status_counts": status_counts,
    }
