"""Runtime Flask condiviso per il centro notifiche persistente."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable, Mapping
from urllib.parse import quote

from flask import current_app, g, has_app_context

from pct.notifications import NotificationRepository, NotificationService
from pct.notifications.web_push import load_web_push_config
from pct.postgres_runtime_support import resolve_runtime_postgres_dsn
from web.helpers import tenant_corrente
from web.services.notification_presidia_coalescence import (
    coalesce_legal_notification_projections,
    enrich_advanced_projection,
    enrich_legacy_projection,
)


LEGAL_NOTIFICATION_SOURCE_TYPE = "legal_notification_presidio"
LEGAL_NOTIFICATION_TO_NOTIFY_STATUSES = {"da_preparare", "da_firmare", "pronta_invio"}
LEGAL_NOTIFICATION_ACTIONABLE_STATUSES = LEGAL_NOTIFICATION_TO_NOTIFY_STATUSES | {
    "da_acquisire",
    "ricevute_da_completare",
}
LEGAL_NOTIFICATION_ADVANCED_TERMINAL_STATUSES = {
    "CLOSED",
    "NOT_REQUIRED",
    "CANCELLED",
    "LEGACY_ASSUMED_HANDLED",
    "PROOF_DEPOSITED",
}


class NotificationRuntimeUnavailable(RuntimeError):
    """Blocca il job senza fallback quando il backend tenant non è disponibile."""


def current_tenant_id() -> str:
    tenant = tenant_corrente()
    value = (
        getattr(tenant, "id", "") or getattr(tenant, "slug", "") or getattr(g, "tenant_context_slug", "") or "default"
    )
    return str(value or "default").strip()


def current_user_id(user: Any | None = None) -> str:
    current = user if user is not None else g.get("utente_corrente")
    return str(getattr(current, "id", "") or getattr(current, "username", "") or "").strip()


def _runtime_config(config: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    if config is not None:
        return config
    return current_app.config if has_app_context() else {}


def _database_mode_value(database: Any) -> str:
    normalized = getattr(database, "normalized_mode", None)
    if normalized:
        return str(normalized or "").strip().upper()
    return str(getattr(database, "mode", "") or "").strip().upper()


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
    database_config = database or data_paths.get("_TENANT_DATABASE_CONFIG") or cfg.get("TENANT_DATABASE_CONFIG")
    postgres_dsn = resolve_runtime_postgres_dsn(
        database=database_config,
        config=cfg,
        env_url_keys=("IUSENTRA_NOTIFICATIONS_DATABASE_URL", "PCT_NOTIFICATIONS_DATABASE_URL"),
    )
    if _database_mode_value(database_config) == "POSTGRESQL" and not postgres_dsn:
        raise NotificationRuntimeUnavailable("Repository notifiche PostgreSQL non disponibile per il tenant corrente.")
    return db_path, postgres_dsn


def notifications_db_path() -> str:
    paths = getattr(g, "data_paths", {}) or {}
    if getattr(g, "tenant_context_missing", False):
        raise RuntimeError(
            "Contesto studio non disponibile per la richiesta corrente. "
            "Accesso ai dati bloccato per evitare letture cross-studio."
        )
    tenant = tenant_corrente()
    return notification_repository_settings(
        paths,
        database=getattr(tenant, "database", None),
        config=current_app.config,
    )[0]


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
    database_mode = _database_mode_value(database_config)
    if database_config is not None and studio_db_path:
        try:
            from pct.core_storage_backend import build_core_storage_backend

            backend = build_core_storage_backend(database_config, studio_db_path=studio_db_path)
            if backend is not None:
                return backend
        except Exception:
            if database_mode == "POSTGRESQL":
                return None
        if database_mode == "POSTGRESQL":
            return None
    if studio_db_path and Path(studio_db_path).exists():
        try:
            from pct.storage import StudioDB

            return StudioDB.get(studio_db_path)
        except Exception:
            pass
    return None


def _tenant_json_mirror_path(
    paths: Mapping[str, Any],
    key: str,
    default_relative: str,
) -> str:
    """Restituisce un path JSON tenant-aware, senza confonderlo con studio.db.

    I gestori Agenda/Scadenziario usano ``db_path`` come mirror JSON anche
    quando ricevono ``studio_db`` come backend SQL. Se per errore viene passato
    ``studio.db`` anche come mirror, il salvataggio JSON può sovrascrivere la
    fonte SQL del tenant. In quel caso ricaviamo il mirror corretto dalla root
    del tenant e lasciamo ``studio.db`` esclusivamente al backend.
    """

    default_path = Path(default_relative)
    raw = _notification_text(paths.get(key))
    studio_db_raw = _notification_text(paths.get("STUDIO_DB"))
    studio_db_path = Path(studio_db_raw) if studio_db_raw else None
    fallback = (
        studio_db_path.parent / default_path
        if studio_db_path is not None and default_path.suffix.lower() == ".json"
        else default_path
    )
    if not raw:
        return str(fallback)
    candidate = Path(raw)
    try:
        same_as_studio = studio_db_path is not None and candidate.expanduser().resolve(
            strict=False
        ) == studio_db_path.expanduser().resolve(strict=False)
    except Exception:
        same_as_studio = studio_db_path is not None and str(candidate) == str(studio_db_path)
    if same_as_studio or candidate.suffix.lower() != ".json":
        return str(fallback)
    return str(candidate)


def notification_recipients_for_paths(
    paths: Mapping[str, Any],
    *,
    database: Any = None,
) -> list[Any]:
    from pct.auth import GestioneUtenti

    auth_db = str(paths.get("AUTH_DB") or "./auth/utenti.json")
    backend = _core_backend_for_paths(paths, database)
    if _database_mode_value(database or paths.get("_TENANT_DATABASE_CONFIG")) == "POSTGRESQL" and backend is None:
        raise NotificationRuntimeUnavailable(
            "Backend core PostgreSQL non disponibile per i destinatari delle notifiche."
        )
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
    if _database_mode_value(database_config) == "POSTGRESQL" and backend is None:
        raise NotificationRuntimeUnavailable("Backend core PostgreSQL non disponibile per Agenda e Scadenziario.")
    config = _runtime_config()
    notification_repository = build_notification_repository_for_paths(
        paths,
        database=database_config,
        config=config,
    )
    agenda = Agenda(
        db_path=_tenant_json_mirror_path(paths, "AGENDA_DB", "agenda/appuntamenti.json"),
        studio_db=backend,
    )
    scadenziario = GestioneScadenziario(
        db_path=_tenant_json_mirror_path(paths, "SCADENZIARIO_DB", "scadenziario/scadenze.json"),
        studio_db=backend,
    )
    recipients = notification_recipients_for_paths(paths, database=database_config)
    service = NotificationService(
        notification_repository,
        web_push_config=load_web_push_config(config),
    )
    resolved_tenant_id = str(tenant_id or paths.get("_TENANT_NOTIFICATION_ID") or tenant_label or "default").strip()
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
        nome_originale=_notification_text(
            row.get("nome_originale") or row.get("original_filename") or row.get("filename") or name
        ),
        nome_portale=_notification_text(
            row.get("nome_portale") or row.get("portal_name") or row.get("nomePortale") or name
        ),
        tipo=_notification_text(
            row.get("tipo") or row.get("type") or row.get("tipo_documento") or row.get("tipoDocumento")
        ),
        tipo_atto_portale=_notification_text(row.get("tipo_atto_portale") or row.get("tipoAttoPortale")),
        classificazione_portale=_notification_text(
            row.get("classificazione_portale") or row.get("classificazionePortale") or row.get("catalogRole")
        ),
        note=_notification_text(
            row.get("note") or row.get("notes") or row.get("descrizione") or row.get("description")
        ),
        tags=tags,
        percorso=_notification_text(
            row.get("percorso") or row.get("path") or row.get("storage_path") or row.get("file")
        ),
        hash_sha256=_notification_text(row.get("hash_sha256") or row.get("sha256") or row.get("hashSha256")),
        prova_notifica=_notification_bool(row.get("prova_notifica") or row.get("provaNotifica")),
        data_documento=_notification_text(row.get("data_documento") or row.get("dataDocumento") or row.get("date")),
        data_deposito_portale=_notification_text(
            row.get("data_deposito_portale") or row.get("dataDepositoPortale") or row.get("data_deposito")
        ),
        data_notifica=_notification_text(row.get("data_notifica") or row.get("dataNotifica")),
        data_comunicazione_cancelleria=_notification_text(
            row.get("data_comunicazione_cancelleria") or row.get("dataComunicazioneCancelleria")
        ),
        signed_status=row.get("signed_status") or row.get("signedStatus"),
        signed_ui=row.get("signed_ui") or row.get("signedUi"),
        firma_status=row.get("firma_status") or row.get("firmaStatus"),
        firma_esito=row.get("firma_esito") or row.get("firmaEsito"),
        metadati_firma=row.get("metadati_firma") or row.get("metadatiFirma"),
        signature_metadata=row.get("signature_metadata") or row.get("signatureMetadata"),
        signature_status=row.get("signature_status") or row.get("signatureStatus"),
        source_message_id=_notification_text(
            row.get("source_message_id")
            or row.get("sourceMessageId")
            or row.get("pec_message_id")
            or row.get("pec_audit_id")
            or row.get("pec_id")
            or row.get("audit_id")
        ),
    )


def _notification_row_value(row: Any, key: str) -> Any:
    if isinstance(row, Mapping):
        return row.get(key, "")
    try:
        return row[key]
    except Exception:
        return getattr(row, key, "")


def _notification_fascicolo_from_row(row: Any) -> SimpleNamespace:
    raw_documents = (
        _notification_row_value(row, "documenti_json")
        or _notification_row_value(row, "documenti")
        or _notification_row_value(row, "documents")
    )
    docs = [_notification_doc(item, index) for index, item in enumerate(_notification_document_rows(raw_documents))]
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
        oggetto=_notification_text(
            _notification_row_value(row, "oggetto") or _notification_row_value(row, "descrizione") or title
        ),
        nome_cliente=_notification_text(
            _notification_row_value(row, "nome_cliente")
            or _notification_row_value(row, "cliente")
            or _notification_row_value(row, "cliente_nome")
        ),
        parti=_notification_text(_notification_row_value(row, "parti")),
        controparte=_notification_text(_notification_row_value(row, "controparte")),
        ufficio=_notification_text(_notification_row_value(row, "ufficio")),
        numero_rg=_notification_text(_notification_row_value(row, "numero_rg")),
        anno_rg=_notification_text(_notification_row_value(row, "anno_rg")),
        stato=_notification_text(_notification_row_value(row, "stato")),
        documenti=docs,
    )


def _core_fascicolo_rows(
    paths: Mapping[str, Any],
    database: Any = None,
    *,
    fascicolo_ids: Iterable[str] | None = None,
) -> list[Any]:
    backend = _core_backend_for_paths(paths, database)
    if backend is None:
        return []
    selected_ids = tuple(
        sorted({_notification_text(value) for value in (fascicolo_ids or ()) if _notification_text(value)})
    )
    fetchall = getattr(backend, "fetchall_readonly", None)
    if callable(fetchall):
        try:
            # Il job deve leggere i documenti necessari al presidio, ma non gli
            # altri JSON potenzialmente molto grandi del fascicolo. Le colonne
            # sono comuni agli schemi SQLite/PostgreSQL governati.
            sql = (
                "SELECT id, numero AS codice, titolo, oggetto, nome_cliente, "
                "controparte, tribunale AS ufficio, numero_rg, anno_rg, stato, "
                "documenti_json FROM fascicoli"
            )
            params: tuple[Any, ...] = ()
            if selected_ids:
                sql += f" WHERE id IN ({','.join('?' for _ in selected_ids)})"
                params = selected_ids
            return list(fetchall(sql, params))
        except Exception:
            return []
    loader = getattr(backend, "carica_tabella", None)
    if callable(loader):
        try:
            rows = list(loader("fascicoli") or [])
        except Exception:
            return []
        if selected_ids:
            selected = set(selected_ids)
            rows = [row for row in rows if _notification_text(_notification_row_value(row, "id")) in selected]
        return rows
    return []


def _notification_fascicolo_rows(
    paths: Mapping[str, Any],
    database: Any = None,
) -> tuple[int, int, list[Any]]:
    try:
        rows = [
            row
            for row in _core_fascicolo_rows(paths, database)
            if _notification_text(_notification_row_value(row, "id"))
        ]
    except Exception:
        return 0, 0, []
    rows.sort(
        key=lambda row: (
            _notification_text(
                _notification_row_value(row, "titolo")
                or _notification_row_value(row, "nome")
                or _notification_row_value(row, "oggetto")
                or _notification_row_value(row, "id")
            ).casefold(),
            _notification_text(_notification_row_value(row, "id")).casefold(),
        )
    )
    total = len(rows)
    archived_ids = {
        _notification_text(_notification_row_value(row, "id"))
        for row in rows
        if _notification_text(_notification_row_value(row, "stato")).casefold()
        in {"archiviato", "archiviata", "archived"}
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
    priority = (
        "urgent"
        if status == "da_acquisire"
        else "important"
        if status in LEGAL_NOTIFICATION_TO_NOTIFY_STATUSES
        else "normal"
    )
    href = _notification_text(
        payload.get("primaryHref") or payload.get("prepareHref") or f"/fascicoli/{fid}#relata-notifica"
    )
    next_step = _legal_notification_next_step(status)
    body = _notification_text(payload.get("systemNotification")) or next_step
    item = {
        "id": f"legal-notification:{fid}:{status}",
        "fascicoloId": fid,
        "type": LEGAL_NOTIFICATION_SOURCE_TYPE,
        "priority": priority,
        "title": _legal_notification_title(status, fascicolo),
        "message": f"{body} {next_step}".strip(),
        "href": href,
        "actionLabel": _notification_text(payload.get("primaryLabel") or "Apri presidio"),
        "createdAt": "",
    }
    return enrich_legacy_projection(item, fascicolo=fascicolo, payload=payload)


def _pec_audit_db_path_for_paths(paths: Mapping[str, Any]) -> Path | None:
    configured = _notification_text(paths.get("PEC_AUDIT_DB"))
    if configured:
        return Path(configured)
    email_db = _notification_text(paths.get("EMAIL_CASELLA_DB"))
    if email_db:
        return Path(email_db).expanduser().resolve().parent / "pec_audit.sqlite"
    return None


def _advanced_notification_status_to_legacy(status: Any) -> str:
    value = _notification_text(status).upper()
    if value == "ORIGINAL_TO_ACQUIRE":
        return "da_acquisire"
    if value in {
        "DETECTED",
        "NEEDS_REVIEW",
        "ORIGINAL_ACQUIRED",
        "NOTIFICATION_CONFIRMED",
        "RECIPIENTS_TO_VERIFY",
        "READY_FOR_RELATA",
        "LEGACY_REVIEW_REQUIRED",
    }:
        return "da_preparare"
    if value == "RELATA_DRAFTED":
        return "da_firmare"
    if value in {"RELATA_SIGNED", "READY_TO_SEND"}:
        return "pronta_invio"
    if value in {
        "SENT_WAITING_RAC",
        "RAC_RECEIVED",
        "PARTIAL_DELIVERY",
        "DELIVERY_COMPLETE",
        "DELIVERY_FAILED",
        "PROOF_TO_DEPOSIT",
    }:
        return "ricevute_da_completare"
    return ""


def _advanced_legal_notification_title(row: Mapping[str, Any], legacy_status: str) -> str:
    fascicolo_id = _notification_text(row.get("fascicolo_id"), "fascicolo")
    fascicolo_label = _notification_text(row.get("fascicolo_label"))
    target = fascicolo_label or f"Fascicolo {fascicolo_id}"
    notification_case = _notification_text(row.get("notification_case")).casefold()
    advanced_status = _notification_text(row.get("status")).upper()
    if "judgment" in notification_case or "sentenza" in notification_case:
        if advanced_status in {"DETECTED", "NEEDS_REVIEW", "LEGACY_REVIEW_REQUIRED"}:
            return f"Sentenza da valutare per la notifica - {target}"[:220]
        return f"Notifica sentenza da presidiare - {target}"[:220]
    if legacy_status in LEGAL_NOTIFICATION_TO_NOTIFY_STATUSES:
        return f"Notifica legale da presidiare - {target}"[:220]
    return f"Presidio notifica legale - {target}"[:220]


def _advanced_notification_next_step(row: Mapping[str, Any], legacy_status: str) -> str:
    notification_case = _notification_text(row.get("notification_case")).casefold()
    advanced_status = _notification_text(row.get("status")).upper()
    if advanced_status in {"DETECTED", "NEEDS_REVIEW", "LEGACY_REVIEW_REQUIRED"} and (
        "judgment" in notification_case or "sentenza" in notification_case
    ):
        return (
            "Esamina la sentenza e conferma se procedere con la notifica; poi prepara la relata, "
            "verifica i destinatari e conserva le ricevute."
        )
    return _legal_notification_next_step(legacy_status)


def _advanced_notification_fascicolo_labels(
    paths: Mapping[str, Any],
    fascicolo_ids: set[str],
    *,
    database: Any = None,
) -> dict[str, str]:
    if not fascicolo_ids:
        return {}
    labels: dict[str, str] = {}
    for row in _core_fascicolo_rows(paths, database, fascicolo_ids=fascicolo_ids):
        fid = _notification_text(_notification_row_value(row, "id"))
        if fid not in fascicolo_ids:
            continue
        client = _notification_text(
            _notification_row_value(row, "nome_cliente")
            or _notification_row_value(row, "cliente")
            or _notification_row_value(row, "cliente_nome")
        )
        title = _notification_text(_notification_row_value(row, "titolo"))
        if not title:
            title = _notification_text(
                _notification_row_value(row, "nome")
                or _notification_row_value(row, "oggetto")
                or _notification_row_value(row, "descrizione")
            )
        rg_number = _notification_text(_notification_row_value(row, "numero_rg"))
        rg_year = _notification_text(_notification_row_value(row, "anno_rg"))
        rg_label = f"RG {rg_number}/{rg_year}" if rg_number and rg_year else ""
        label = " · ".join(part for part in (client, title, rg_label) if part)
        if fid and label:
            labels[fid] = label
    return labels


def _advanced_notification_repository_for_paths(
    paths: Mapping[str, Any],
    *,
    tenant_id: str,
    database: Any = None,
):
    from pct.pec_notification_presidio import NotificationPresidioRepository

    # I presidi avanzati sono prodotti dal worker PEC nel PEC_AUDIT_DB del
    # tenant. Il backend core/topbar può essere PostgreSQL, ma non cambia la
    # fonte verticale del presidio: usare qui il DSN core leggerebbe un archivio
    # diverso da quello appena scritto dal worker.
    _ = database
    resolved_tenant = _notification_text(tenant_id, "default")
    db_path = _pec_audit_db_path_for_paths(paths)
    if db_path is None:
        raise NotificationRuntimeUnavailable("Percorso PEC_AUDIT_DB non disponibile per il presidio notifiche.")
    if not db_path.exists():
        raise NotificationRuntimeUnavailable("Archivio PEC_AUDIT_DB non disponibile per il presidio notifiche.")
    return NotificationPresidioRepository(db_path, tenant_id=resolved_tenant)


UNLINKED_PEC_ITEM_PREFIX = "pec-da-assegnare"
UNLINKED_PEC_MAX_ITEMS = 50


def _unlinked_pec_items(paths: Mapping[str, Any], *, limit: int = UNLINKED_PEC_MAX_ITEMS) -> list[dict[str, Any]]:
    """PEC lavorate che non hanno trovato un fascicolo: devono restare visibili.

    Senza fascicolo collegato il presidio non crea alcuna voce operativa: la PEC
    risulta ricevuta e lavorata, ma per lo studio non esiste. Succede quando il
    procedimento non è ancora a ruolo nel gestionale o quando il numero di ruolo
    non coincide. Qui la PEC viene esposta come lavoro da assegnare, con i dati
    già estratti dalla pipeline — numero di ruolo, ufficio, oggetto — e con la
    fonte da cui provengono, così l'assegnazione è un gesto solo.
    """

    db_path = _pec_audit_db_path_for_paths(paths)
    if db_path is None or not Path(db_path).exists():
        return []
    righe: list[Any] = []
    try:
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            righe = conn.execute(
                """
                SELECT m.id, m.metadata_json, m.received_at, l.seeds_json, l.status AS link_status
                FROM pec_messages m
                JOIN (
                    SELECT message_id, MAX(created_at) AS ultimo
                    FROM pec_fascicolo_links
                    GROUP BY message_id
                ) ultimo_link ON ultimo_link.message_id = m.id
                JOIN pec_fascicolo_links l
                  ON l.message_id = m.id AND l.created_at = ultimo_link.ultimo
                WHERE TRIM(COALESCE(m.linked_fascicolo_id, '')) = ''
                ORDER BY m.received_at DESC
                LIMIT ?
                """,
                (max(1, int(limit or UNLINKED_PEC_MAX_ITEMS)),),
            ).fetchall()
    except sqlite3.Error as exc:
        # Un errore qui significa che le PEC non collegate restano invisibili:
        # va detto, non ingoiato.
        if has_app_context():
            current_app.logger.warning("PEC non collegate non leggibili da %s: %s", db_path, exc)
        return []

    voci: list[dict[str, Any]] = []
    for riga in righe:
        dati = dict(riga)
        seeds = _notification_json(dati.get("seeds_json"), {})
        seeds = seeds if isinstance(seeds, dict) else {}
        rg = next((_notification_text(value) for value in list(seeds.get("rg") or []) if value), "")
        ufficio = _notification_text(seeds.get("office"))
        intestazioni = _notification_json(dati.get("metadata_json"), {})
        intestazioni = intestazioni.get("headers") if isinstance(intestazioni, dict) else {}
        oggetto = _notification_text(
            (intestazioni or {}).get("subject") if isinstance(intestazioni, dict) else "",
            "PEC senza oggetto",
        )
        dettagli = [pezzo for pezzo in (f"RG: {rg}" if rg else "", f"Ufficio: {ufficio}" if ufficio else "") if pezzo]
        motivo = {
            "nessun_candidato": "nessun fascicolo compatibile",
            "rg_non_sufficiente": "numero di ruolo compatibile ma non sufficiente da solo",
            "proposte": "sono presenti fascicoli candidati da confermare",
        }.get(_notification_text(dati.get("link_status")), "collegamento automatico non riuscito")
        messaggio = " — ".join(
            pezzo
            for pezzo in (
                oggetto,
                ", ".join(dettagli),
                f"Assegnare al fascicolo: {motivo}.",
                "Fonte: presidio PEC, dati estratti dal messaggio e dagli allegati ministeriali.",
            )
            if pezzo
        )
        voci.append(
            {
                "id": f"{UNLINKED_PEC_ITEM_PREFIX}:{_notification_text(dati.get('id'))}",
                "fascicoloId": "",
                "type": LEGAL_NOTIFICATION_SOURCE_TYPE,
                "priority": "important",
                "title": "PEC da assegnare a un fascicolo",
                "message": messaggio,
                "href": "/email?canale=pec",
                "actionLabel": "Apri la PEC",
                "createdAt": _notification_text(dati.get("received_at")),
            }
        )
    return voci


def _advanced_notification_items(
    paths: Mapping[str, Any],
    *,
    tenant_id: str,
    limit: int | None = None,
    presidio_ids: Iterable[str] | None = None,
    database: Any = None,
) -> list[dict[str, Any]]:
    """Legge tutti i presìdi operativi a pagine, senza troncare la sincronizzazione.

    ``limit`` resta disponibile soltanto per i flussi campione che passano una
    selezione esplicita. La materializzazione ordinaria usa invece pagine
    keyset da 200 righe: nessun presidio attivo deve sparire da topbar, Web Push
    o Scadenziario solo perché è meno recente dei primi 200.
    """

    resolved_tenant = _notification_text(tenant_id, "default")
    placeholders = ",".join("?" for _ in LEGAL_NOTIFICATION_ADVANCED_TERMINAL_STATUSES)
    selected_ids = tuple(
        sorted({_notification_text(value) for value in (presidio_ids or ()) if _notification_text(value)})
    )
    id_filter = ""
    if selected_ids:
        id_filter = f" AND p.id IN ({','.join('?' for _ in selected_ids)})"
    requested_limit = None if limit is None else max(0, int(limit))
    if requested_limit == 0:
        return []
    page_size = 200
    repo = _advanced_notification_repository_for_paths(
        paths,
        tenant_id=resolved_tenant,
        database=database,
    )
    rows: list[dict[str, Any]] = []
    try:
        with repo.connection() as conn:
            cursor: tuple[str, str] | None = None
            while True:
                remaining = None if requested_limit is None else requested_limit - len(rows)
                if remaining is not None and remaining <= 0:
                    break
                fetch_limit = page_size if remaining is None else min(page_size, remaining)
                cursor_filter = ""
                params: list[Any] = [
                    resolved_tenant,
                    *sorted(LEGAL_NOTIFICATION_ADVANCED_TERMINAL_STATUSES),
                    *selected_ids,
                ]
                if cursor is not None:
                    cursor_filter = " AND (p.updated_at < ? OR (p.updated_at = ? AND p.id < ?))"
                    params.extend((cursor[0], cursor[0], cursor[1]))
                params.append(fetch_limit)
                page = [
                    repo._row(row)
                    for row in conn.execute(
                        f"""
                    SELECT p.id, p.fascicolo_id, p.source_message_id, p.status, p.priority, p.notification_case,
                           p.detection_reason, p.source_effective_at, p.updated_at,
                           (
                               SELECT d.fascicolo_document_id
                               FROM pec_legal_notification_documents d
                               WHERE d.tenant_id=p.tenant_id
                                 AND d.presidio_id=p.id
                                 AND TRIM(d.fascicolo_document_id)<>''
                               ORDER BY CASE
                                          WHEN d.document_role='portal_original' THEN 0
                                          WHEN d.authoritative THEN 1
                                          ELSE 2
                                        END,
                                        d.created_at DESC,
                                        d.id DESC
                               LIMIT 1
                           ) AS source_document_id,
                           (
                               SELECT d.original_filename
                               FROM pec_legal_notification_documents d
                               WHERE d.tenant_id=p.tenant_id
                                 AND d.presidio_id=p.id
                                 AND TRIM(d.original_filename)<>''
                               ORDER BY CASE
                                          WHEN d.document_role='portal_original' THEN 0
                                          WHEN d.authoritative THEN 1
                                          ELSE 2
                                        END,
                                        d.created_at DESC,
                                        d.id DESC
                               LIMIT 1
                           ) AS source_document_name
                    FROM pec_legal_notification_presidia p
                     WHERE p.tenant_id=?
                       AND p.status NOT IN ({placeholders})
                       {id_filter}
                       {cursor_filter}
                    ORDER BY p.updated_at DESC, p.id DESC
                    LIMIT ?
                    """,
                        tuple(params),
                    ).fetchall()
                ]
                if not page:
                    break
                rows.extend(page)
                if len(page) < fetch_limit:
                    break
                next_cursor = (
                    _notification_text(page[-1].get("updated_at")),
                    _notification_text(page[-1].get("id")),
                )
                if not all(next_cursor) or next_cursor == cursor:
                    break
                cursor = next_cursor
    finally:
        repo.close()
    labels = _advanced_notification_fascicolo_labels(
        paths,
        {_notification_text(row["fascicolo_id"]) for row in rows if _notification_text(row["fascicolo_id"])},
        database=database,
    )
    items: list[dict[str, Any]] = []
    for row in rows:
        data = dict(row)
        data["fascicolo_label"] = labels.get(_notification_text(data.get("fascicolo_id")), "")
        legacy_status = _advanced_notification_status_to_legacy(data.get("status"))
        if legacy_status not in LEGAL_NOTIFICATION_ACTIONABLE_STATUSES:
            continue
        priority_code = _notification_text(data.get("priority")).upper()
        priority = "urgent" if priority_code == "P0" else "important" if priority_code == "P1" else "normal"
        next_step = _advanced_notification_next_step(data, legacy_status)
        reason = _notification_text(data.get("detection_reason")) or "Presidio notifica creato dal controllo PEC."
        presidio_id = _notification_text(data.get("id"))
        item = {
            "id": f"legal-notification-presidio:{presidio_id}:{legacy_status}",
            "fascicoloId": _notification_text(data.get("fascicolo_id")),
            "type": LEGAL_NOTIFICATION_SOURCE_TYPE,
            "priority": priority,
            "title": _advanced_legal_notification_title(data, legacy_status),
            "message": f"{reason} {next_step}".strip(),
            "href": f"/notifiche-legali?presidio={quote(presidio_id)}",
            "actionLabel": "Apri presidio",
            "createdAt": _notification_text(data.get("source_effective_at") or data.get("updated_at")),
            # La sentenza resta nella PEC sorgente fino all'acquisizione dal
            # portale: la scadenza deve quindi conservare il riferimento PEC,
            # senza anticipare un collegamento a un documento del fascicolo.
            "sourceMessageId": _notification_text(data.get("source_message_id")),
            "sourceDocumentId": _notification_text(data.get("source_document_id")),
            # Il viewer già usato dalle altre scadenze PEC può aprire in modo
            # diretto il PDF contenuto nello ZIP solo se riceve il nome
            # dell'allegato auditato, oltre all'identificativo della PEC.
            "sourceDocumentName": _notification_text(data.get("source_document_name")),
        }
        items.append(
            enrich_advanced_projection(
                item,
                notification_case=data.get("notification_case"),
            )
        )
    return items


def _sync_legal_notification_deadlines(
    paths: Mapping[str, Any],
    items: list[dict[str, Any]],
    *,
    database: Any = None,
    reconcile_existing: bool = True,
    reconcile_source_prefixes: Iterable[str] | None = None,
) -> dict[str, int]:
    from datetime import date, datetime

    from pct.scadenziario import GestioneScadenziario, StatoTermine, TipoTermine

    database_config = database or paths.get("_TENANT_DATABASE_CONFIG")
    backend = _core_backend_for_paths(paths, database_config)
    if _database_mode_value(database_config) == "POSTGRESQL" and backend is None:
        raise NotificationRuntimeUnavailable("Backend core PostgreSQL non disponibile per lo Scadenziario notifiche.")
    scadenziario = GestioneScadenziario(
        db_path=_tenant_json_mirror_path(paths, "SCADENZIARIO_DB", "scadenziario/scadenze.json"),
        studio_db=backend,
    )
    active_markers = {f"IUSENTRA_LEGAL_NOTIFICATION:{item['id']}" for item in items}
    scoped_prefixes = tuple(
        sorted(
            {
                _notification_text(value)
                for value in (reconcile_source_prefixes or ())
                if _notification_text(value)
            }
        )
    )

    def _deadline_status(deadline: Any) -> str:
        value = getattr(deadline, "stato", "")
        value = getattr(value, "value", value)
        return _notification_text(value).upper()

    def _deadline_is_operational_open(deadline: Any) -> bool:
        # In IUSENTRA anche SCADUTO resta visibile e operativo finché non è
        # completato/annullato: riconciliare solo APERTO lasciava in pagina il
        # vecchio rumore storico del presidio PEC.
        return _deadline_status(deadline) not in {"COMPLETATO", "ANNULLATO"}

    def _is_legacy_sentence_review_note(note: str) -> bool:
        lowered = note.casefold()
        return (
            "pec_audit:" in lowered
            and "iusentra_legal_notification:" not in lowered
            and "sentenza_da_valutare_per_notifica" in lowered
        )

    def _legacy_sentence_completion_note(note: str) -> str:
        marker = "[Audit IUSENTRA] Storico sentenze PEC riconciliato"
        if marker in note:
            return note
        return (
            f"{note.rstrip()}\n\n"
            f"{marker}: riga automatica storica chiusa perché il pannello Presidi notifiche "
            "pubblica solo i presidi stabili ancora attivi o da confermare; nessun fascicolo "
            "o documento è stato eliminato."
        ).strip()

    existing = []
    for deadline in scadenziario.tutte(solo_aperte=False):
        note = _notification_text(getattr(deadline, "note", ""))
        if "IUSENTRA_LEGAL_NOTIFICATION:" in note:
            existing.append(deadline)
        elif _is_legacy_sentence_review_note(note):
            existing.append(deadline)
    created = 0
    updated = 0
    completed = 0
    by_marker: dict[str, Any] = {}
    for marker in active_markers:
        matches = [deadline for deadline in existing if marker in _notification_text(getattr(deadline, "note", ""))]
        by_marker[marker] = next(
            (deadline for deadline in matches if _deadline_is_operational_open(deadline)), None
        ) or (matches[0] if matches else None)
    today = date.today().isoformat()
    for item in items:
        if item["id"].split(":")[-1] not in LEGAL_NOTIFICATION_TO_NOTIFY_STATUSES:
            continue
        marker = f"IUSENTRA_LEGAL_NOTIFICATION:{item['id']}"
        source_message_id = _notification_text(item.get("sourceMessageId"))
        source_marker = f"PEC_AUDIT:{source_message_id}" if source_message_id else ""
        source_document_name = _notification_text(item.get("sourceDocumentName"))
        source_document_id = _notification_text(item.get("sourceDocumentId"))
        fascicolo_id = _notification_text(item.get("fascicoloId"))
        internal_document_marker = (
            f"PEC_DOCUMENT_PRESIDIO:docpresidio:{fascicolo_id}:{source_document_id}:portal_original:linked"
            if fascicolo_id and source_document_id
            else ""
        )
        source_document_marker = f"Fonte documentale: {source_document_name}" if source_document_name else ""
        note = "\n".join(
            part
            for part in (
                marker,
                internal_document_marker,
                source_marker,
                source_document_marker,
            )
            if part
        )
        current = by_marker.get(marker)
        if current and _deadline_is_operational_open(current):
            scadenziario.aggiorna(
                current.id,
                titolo=_notification_text(item.get("title"), "Notifica da presidiare"),
                descrizione=_notification_text(item.get("message")),
                data_scadenza=today,
                id_fascicolo=fascicolo_id,
                source_event_type=LEGAL_NOTIFICATION_SOURCE_TYPE,
                note=note,
            )
            updated += 1
        else:
            created_deadline = scadenziario.nuova(
                titolo=_notification_text(item.get("title"), "Notifica da presidiare"),
                tipo=TipoTermine.NOTIFICA,
                data_scadenza=today,
                id_fascicolo=fascicolo_id,
                descrizione=_notification_text(item.get("message")),
                note=note,
                source_event_type=LEGAL_NOTIFICATION_SOURCE_TYPE,
                giorni_preavviso=[0],
            )
            by_marker[marker] = created_deadline
            existing.append(created_deadline)
            created += 1
    if reconcile_existing:
        for deadline in existing:
            note = _notification_text(getattr(deadline, "note", ""))
            if scoped_prefixes and not any(prefix in note for prefix in scoped_prefixes):
                continue
            if not _deadline_is_operational_open(deadline):
                continue
            matching_active_marker = next((marker for marker in active_markers if marker in note), "")
            is_active_marker = bool(matching_active_marker)
            is_legacy_sentence_review = _is_legacy_sentence_review_note(note)
            should_complete = (
                (not is_active_marker and "IUSENTRA_LEGAL_NOTIFICATION:" in note)
                or is_legacy_sentence_review
                or (
                    is_active_marker
                    and by_marker.get(matching_active_marker) is not None
                    and getattr(by_marker[matching_active_marker], "id", "") != getattr(deadline, "id", "")
                )
            )
            if should_complete:
                scadenziario.aggiorna(
                    deadline.id,
                    stato=StatoTermine.COMPLETATO,
                    completata_il=datetime.now().isoformat(timespec="seconds"),
                    note=_legacy_sentence_completion_note(note) if is_legacy_sentence_review else note,
                )
                completed += 1
    return {"created": created, "updated": updated, "completed": completed}


def materialize_notification_relata_presidio_for_paths(
    paths: Mapping[str, Any],
    *,
    tenant_label: str,
    tenant_id: str = "",
    presidio_tenant_id: str = "",
    database: Any = None,
) -> dict[str, Any]:
    """Materializza residui notifica fascicoli in topbar, Web Push e scadenziario senza rallentare la UI."""

    from web.services.react_fascicoli_bridge import _notification_relata

    database_config = database or paths.get("_TENANT_DATABASE_CONFIG")
    # Senza backend il presidio leggerebbe zero fascicoli e riporterebbe un
    # "nessuna notifica da fare" indistinguibile dal lavoro svolto: il guasto
    # va dichiarato, non nascosto dietro un conteggio a zero.
    if _core_backend_for_paths(paths, database_config) is None:
        return {
            "ok": False,
            "tenant": _notification_text(tenant_label, "default"),
            "source_of_truth": "core backend fascicoli tenant-aware",
            "error": "archivio fascicoli non raggiungibile (studio.db o database dello studio non disponibile)",
            "total_db": 0,
            "scanned": 0,
            "items": 0,
            "to_notify": 0,
            "recipients": 0,
            "errors": 1,
        }
    total, archived, rows = _notification_fascicolo_rows(paths, database_config)
    legacy_items: list[dict[str, Any]] = []
    status_counts: dict[str, int] = {}
    for row in rows:
        fascicolo = _notification_fascicolo_from_row(row)
        payload = _notification_relata(fascicolo, [])
        status = _notification_text(payload.get("status"), "monitoraggio")
        status_counts[status] = status_counts.get(status, 0) + 1
        item = _legal_notification_item(fascicolo, payload)
        if item:
            legacy_items.append(item)

    resolved_tenant_id = _notification_text(
        tenant_id or paths.get("_TENANT_NOTIFICATION_ID") or tenant_label or "default"
    )
    resolved_presidio_tenant_id = _notification_text(
        presidio_tenant_id or paths.get("_TENANT_PRESIDIO_ID") or tenant_label or tenant_id or "default"
    )
    advanced_items = _advanced_notification_items(
        paths,
        tenant_id=resolved_presidio_tenant_id,
        database=database_config,
    )
    for item in advanced_items:
        legacy_status = item["id"].split(":")[-1]
        status_counts[f"pec:{legacy_status}"] = status_counts.get(f"pec:{legacy_status}", 0) + 1
    items, legacy_coalesced = coalesce_legal_notification_projections(
        legacy_items,
        advanced_items,
    )
    # Le PEC lavorate ma senza fascicolo non hanno un presidio a cui agganciarsi:
    # senza questa riga resterebbero invisibili allo studio pur essendo in archivio.
    unlinked_items = _unlinked_pec_items(paths)
    items = list(items) + unlinked_items
    recipients = notification_recipients_for_paths(paths, database=database_config)
    config = _runtime_config()
    service = NotificationService(
        build_notification_repository_for_paths(paths, database=database_config, config=config),
        web_push_config=load_web_push_config(config),
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
        "source_of_truth": "core backend fascicoli + presidio notifiche repository tenant-aware + notification repository tenant-aware",
        "total_db": total,
        "archived_skipped": archived,
        "scanned": len(rows),
        "items": len(items),
        "legacy_items": len(legacy_items),
        "legacy_coalesced": legacy_coalesced,
        "advanced_items": len(advanced_items),
        "unlinked_pec": len(unlinked_items),
        "to_notify": sum(1 for item in items if item["id"].split(":")[-1] in LEGAL_NOTIFICATION_TO_NOTIFY_STATUSES),
        "recipients": synced_recipients,
        "errors": errors,
        "calendar": calendar_report,
        "status_counts": status_counts,
    }


def materialize_selected_advanced_notification_presidia_for_paths(
    paths: Mapping[str, Any],
    *,
    tenant_label: str,
    presidio_ids: Iterable[str],
    superseded_presidio_ids: Iterable[str] = (),
    redispatch_presidio_ids: Iterable[str] = (),
    tenant_id: str = "",
    presidio_tenant_id: str = "",
    database: Any = None,
) -> dict[str, Any]:
    """Pubblica soltanto i presidi selezionati dopo un evento applicativo.

    Il percorso non effettua scansioni dei fascicoli e non chiude notifiche o
    scadenze non selezionate. La riga operativa dello Scadenziario resta la
    fonte proiettata anche in Agenda: non viene creato un appuntamento parallelo.
    """

    selected_ids = tuple(sorted({_notification_text(value) for value in presidio_ids if _notification_text(value)}))
    superseded_ids = tuple(
        sorted({_notification_text(value) for value in superseded_presidio_ids if _notification_text(value)})
    )
    redispatch_ids = {
        _notification_text(value)
        for value in redispatch_presidio_ids
        if _notification_text(value)
    }
    if not selected_ids:
        return {
            "ok": False,
            "tenant": _notification_text(tenant_label, "default"),
            "items": 0,
            "recipients": 0,
            "errors": 1,
            "calendar": {"created": 0, "updated": 0, "completed": 0},
            "reason": "Nessun presidio selezionato per la pubblicazione campione.",
        }
    database_config = database or paths.get("_TENANT_DATABASE_CONFIG")
    resolved_tenant_id = _notification_text(
        tenant_id or paths.get("_TENANT_NOTIFICATION_ID") or tenant_label or "default"
    )
    resolved_presidio_tenant_id = _notification_text(
        presidio_tenant_id or paths.get("_TENANT_PRESIDIO_ID") or tenant_label or tenant_id or "default"
    )
    advanced_items = _advanced_notification_items(
        paths,
        tenant_id=resolved_presidio_tenant_id,
        presidio_ids=selected_ids,
        limit=len(selected_ids),
        database=database_config,
    )
    selected_fascicolo_ids = {
        _notification_text(item.get("fascicoloId"))
        for item in advanced_items
        if _notification_text(item.get("fascicoloId"))
    }
    legacy_items: list[dict[str, Any]] = []
    if selected_fascicolo_ids:
        from web.services.react_fascicoli_bridge import _notification_relata

        for row in _core_fascicolo_rows(
            paths,
            database_config,
            fascicolo_ids=selected_fascicolo_ids,
        ):
            fascicolo = _notification_fascicolo_from_row(row)
            payload = _notification_relata(fascicolo, [])
            item = _legal_notification_item(fascicolo, payload)
            if item:
                legacy_items.append(item)
    items, legacy_coalesced = coalesce_legal_notification_projections(
        legacy_items,
        advanced_items,
    )
    active_source_ids = {
        _notification_text(item.get("id"))
        for item in items
        if _notification_text(item.get("id"))
    }
    found_presidio_ids = {
        item_id.split(":", 2)[1]
        for item_id in (
            _notification_text(item.get("id")) for item in advanced_items
        )
        if item_id.startswith("legal-notification-presidio:")
    }
    recipients = notification_recipients_for_paths(paths, database=database_config)
    service = NotificationService(
        build_notification_repository_for_paths(paths, database=database_config, config=_runtime_config()),
        web_push_config=load_web_push_config(_runtime_config()),
    )
    synced_recipients = 0
    expired_superseded = 0
    redispatched_pushes = 0
    errors = 0
    for user in recipients:
        try:
            can_read = not hasattr(user, "ha_permesso") or bool(user.ha_permesso("fascicoli.leggi"))
            if not can_read:
                continue
            user_id = _notification_text(getattr(user, "id", "") or getattr(user, "username", ""))
            if not user_id:
                continue
            existing_redispatch = {
                item_id
                for item_id in active_source_ids
                if item_id.startswith("legal-notification-presidio:")
                and item_id.split(":", 2)[1] in redispatch_ids
                and service.repository.get_notification_by_dedupe_key(
                    resolved_tenant_id,
                    user_id,
                    item_id,
                )
                is not None
            }
            service.sync_operational_items(
                tenant_id=resolved_tenant_id,
                user_id=user_id,
                items=items,
                expire_source_types=set(),
            )
            superseded_source_ids = {
                f"legal-notification-presidio:{presidio_id}:{status}"
                for presidio_id in superseded_ids
                for status in LEGAL_NOTIFICATION_ACTIONABLE_STATUSES
            }
            superseded_source_ids.update(
                {
                    f"legal-notification:{fascicolo_id}:{status}"
                    for fascicolo_id in selected_fascicolo_ids
                    for status in LEGAL_NOTIFICATION_ACTIONABLE_STATUSES
                }
            )
            superseded_source_ids.difference_update(active_source_ids)
            expired_superseded += service.repository.expire_notifications_by_source_ids(
                resolved_tenant_id,
                user_id,
                source_type=LEGAL_NOTIFICATION_SOURCE_TYPE,
                source_ids=superseded_source_ids,
            )
            for source_id in existing_redispatch:
                refreshed = service.repository.get_notification_by_dedupe_key(
                    resolved_tenant_id,
                    user_id,
                    source_id,
                )
                if refreshed is not None:
                    summary = service.dispatch_web_push(refreshed)
                    redispatched_pushes += int(summary.attempted or summary.sent or 0)
            synced_recipients += 1
        except Exception:
            errors += 1
    deadline_prefixes = {
        f"IUSENTRA_LEGAL_NOTIFICATION:legal-notification-presidio:{presidio_id}:"
        for presidio_id in {*selected_ids, *superseded_ids}
    }
    deadline_prefixes.update(
        {
            f"IUSENTRA_LEGAL_NOTIFICATION:legal-notification:{fascicolo_id}:"
            for fascicolo_id in selected_fascicolo_ids
        }
    )
    calendar_report = _sync_legal_notification_deadlines(
        paths,
        items,
        database=database_config,
        reconcile_existing=True,
        reconcile_source_prefixes=deadline_prefixes,
    )
    return {
        "ok": errors == 0 and set(selected_ids) == found_presidio_ids,
        "tenant": _notification_text(tenant_label, "default"),
        "source_of_truth": "presidio notifiche repository tenant-aware + notification repository tenant-aware",
        "selected": len(selected_ids),
        "items": len(items),
        "advanced_items": len(advanced_items),
        "legacy_items": len(legacy_items),
        "legacy_coalesced": legacy_coalesced,
        "recipients": synced_recipients,
        "errors": errors,
        "expired_superseded": expired_superseded,
        "redispatched_pushes": redispatched_pushes,
        "calendar": calendar_report,
    }
