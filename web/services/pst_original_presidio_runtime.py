"""Collegamento governato degli originali PST ai presidi di notifica legale."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from flask import current_app, g, has_app_context

from pct.pec_notification_presidio import PresidioStatus, canonical_document_identity


_TERMINAL_STATUSES = {
    PresidioStatus.CLOSED.value,
    PresidioStatus.NOT_REQUIRED.value,
    PresidioStatus.CANCELLED.value,
    PresidioStatus.LEGACY_ASSUMED_HANDLED.value,
    PresidioStatus.PROOF_DEPOSITED.value,
}
_ORIGINAL_ACQUIRED_TRANSITION_STATUSES = {
    PresidioStatus.DETECTED.value,
    PresidioStatus.NEEDS_REVIEW.value,
    PresidioStatus.ORIGINAL_TO_ACQUIRE.value,
    PresidioStatus.LEGACY_REVIEW_REQUIRED.value,
}
_CONTAINER_SUFFIXES = (".p7m", ".p7s", ".smime", ".zip")
_PST_SOURCE_MARKERS = (
    "pst:",
    "polisweb",
    "portale servizi",
    "portale telematico",
)
_DECISIVE_DOCUMENT_MARKERS = (
    "sentenza",
    "sentenzadefinitiva",
    "ordinanza",
    "decreto",
    "verbale",
    "provvedimento",
)
_NON_DECISIVE_DOCUMENT_MARKERS = (
    "ricorso",
    "memoria",
    "istanza",
    "comparsa",
    "nota",
    "note",
    "accettazione deposito",
    "esito controlli",
    "ricevuta",
    "conferma pagamento",
)
_NON_PST_SOURCE_MARKERS = (
    "quickorganizer:",
    "documenti_ai:",
    "manual:",
    "upload:",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _field(source: Any, *keys: str) -> Any:
    for key in keys:
        if isinstance(source, Mapping) and key in source:
            value = source.get(key)
        else:
            value = getattr(source, key, None)
        if value not in (None, ""):
            return value
    return ""


def _normalized_document_name(value: Any) -> str:
    name = _text(value).replace("\\", "/").rsplit("/", 1)[-1].casefold()
    changed = True
    while name and changed:
        changed = False
        for suffix in _CONTAINER_SUFFIXES:
            if name.endswith(suffix):
                name = name[: -len(suffix)].rstrip()
                changed = True
                break
    return re.sub(r"[^a-z0-9]+", "", name)


def _is_portal_original(document: Mapping[str, Any]) -> bool:
    mode = _text(document.get("modalita_documento_portale") or document.get("portal_document_mode")).casefold()
    return bool(
        document.get("original_documento_portale")
        or document.get("portal_original")
        or document.get("authoritative")
        or mode == "originale"
    )


def _joined_tags(document: Any) -> str:
    tags = _field(document, "tags")
    if isinstance(tags, (list, tuple, set)):
        return " ".join(_text(item) for item in tags)
    return _text(tags)


def _is_pst_fascicolo_document(document: Any) -> bool:
    portal_document_id = _text(
        _field(document, "id_documento_portale", "portal_document_id", "id_documento")
    )
    portal_reference = _text(_field(document, "id_cat_portale", "id_cat", "msg_id_portale", "msg_id"))
    service = _text(_field(document, "servizio_portale", "fonte_documento")).casefold()
    haystack = " ".join(
        _text(_field(document, key))
        for key in (
            "note",
            "origine",
            "source",
            "nome_originale",
            "nome_portale",
            "classificazione_portale",
            "tipo_atto_portale",
            "id_documento_portale",
            "id_cat_portale",
        )
    ).casefold()
    if any(marker in haystack for marker in _NON_PST_SOURCE_MARKERS):
        return False
    if service in {
        "pst",
        "polisweb",
        "portale_telematico",
        "portale telematico",
    }:
        return True
    if any(marker in haystack for marker in _PST_SOURCE_MARKERS):
        return True
    if portal_document_id.isdigit() or portal_reference.isdigit():
        return True
    return False


def _is_decisive_pst_document(
    document: Any,
    *,
    notification_case: str = "",
    portal_context: Mapping[str, Any] | None = None,
) -> bool:
    haystack = " ".join(
        [
            _text(_field(document, "nome", "filename")),
            _text(_field(document, "nome_originale", "original_filename")),
            _text(_field(document, "nome_portale")),
            _text(_field(document, "tipo", "document_type")),
            _text(_field(document, "tipo_atto_portale", "classificazione_portale")),
            _text(_field(document, "note")),
            _joined_tags(document),
        ]
    ).casefold()
    if not any(marker in haystack for marker in _DECISIVE_DOCUMENT_MARKERS):
        return False
    if any(marker in haystack for marker in _NON_DECISIVE_DOCUMENT_MARKERS):
        return False
    requested_type = _text((portal_context or {}).get("tipo_documento")).casefold()
    if requested_type == "sentenza" or "judgment" in _text(notification_case).casefold():
        return "sentenza" in haystack or "provvedimento" in haystack
    return True


def _fascicolo_document_to_pst_candidate(document: Any) -> dict[str, Any]:
    fascicolo_document_id = _text(_field(document, "id", "documento_id", "fascicolo_document_id"))
    name = _text(
        _field(
            document,
            "nome",
            "nome_originale",
            "nome_portale",
            "original_filename",
            "filename",
        )
    )
    content_sha256 = _text(
        _field(document, "hash_sha256", "hash_contenuto_sha256", "content_sha256", "sha256")
    )
    portal_document_id = _text(
        _field(document, "id_documento_portale", "portal_document_id", "id_documento")
    )
    portal_reference = _text(
        _field(document, "id_cat_portale", "id_cat", "msg_id_portale", "msg_id")
    )
    return {
        "fascicolo_document_id": fascicolo_document_id,
        "documento_id": fascicolo_document_id,
        "id": fascicolo_document_id,
        "nome": name,
        "nome_originale": _text(_field(document, "nome_originale")) or name,
        "original_filename": _text(_field(document, "nome_originale")) or name,
        "hash_sha256": content_sha256,
        "content_sha256": content_sha256,
        "id_documento_portale": portal_document_id,
        "portal_document_id": portal_document_id,
        "id_cat_portale": portal_reference,
        "portal_reference": portal_reference or (
            f"pst:{_text(_field(document, 'servizio_portale'))}:{portal_document_id}"
            if portal_document_id
            else ""
        ),
        "modalita_documento_portale": _text(_field(document, "modalita_documento_portale"))
        or "fascicolo_pst",
        "original_documento_portale": True,
        "portal_original": True,
    }


def _existing_pst_documents_from_fascicolo(
    fascicolo_id: str,
    *,
    notification_case: str = "",
    portal_context: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    identifier = _text(fascicolo_id)
    if not identifier:
        return []
    try:
        from web.helpers import get_fascicoli

        fascicolo = get_fascicoli().get(identifier)
        documents = getattr(fascicolo, "documenti", []) or []
    except Exception:
        return []
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for document in documents[:160]:
        if not _is_pst_fascicolo_document(document):
            continue
        if not _is_decisive_pst_document(
            document,
            notification_case=notification_case,
            portal_context=portal_context,
        ):
            continue
        payload = _fascicolo_document_to_pst_candidate(document)
        key = _text(payload.get("fascicolo_document_id")) or _text(payload.get("portal_document_id"))
        if not key or key in seen:
            continue
        seen.add(key)
        candidates.append(payload)
    return candidates


def _portal_document_payload(document: Mapping[str, Any]) -> dict[str, Any]:
    content_sha256 = _text(
        document.get("hash_sha256") or document.get("content_sha256") or document.get("sha256")
    ).lower()
    portal_document_id = _text(
        document.get("id_documento_portale") or document.get("portal_document_id") or document.get("id_documento")
    )
    portal_reference = _text(
        document.get("portal_reference")
        or document.get("id_cat_portale")
        or document.get("id_cat")
        or document.get("msg_id_portale")
        or document.get("msg_id")
    )
    return {
        "fascicolo_document_id": _text(
            document.get("fascicolo_document_id") or document.get("documento_id") or document.get("id")
        ),
        "document_role": "portal_original",
        "document_version": _text(document.get("document_version") or "1"),
        "outer_sha256": content_sha256,
        "content_sha256": content_sha256,
        "portal_document_id": portal_document_id,
        "portal_reference": portal_reference,
        "original_filename": _text(
            document.get("nome_originale")
            or document.get("original_filename")
            or document.get("nome")
            or document.get("filename")
        ),
        "authoritative": True,
    }


def _target_value(target: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = _text(target.get(key))
        if value:
            return value
    return ""


def _document_matches_target(document: Mapping[str, Any], target: Mapping[str, Any]) -> bool:
    expected_name = _normalized_document_name(_target_value(target, "documento", "nome", "documento_portale"))
    expected_id = _target_value(target, "idDocumento", "id_documento", "portal_document_id")
    expected_hash = _target_value(target, "hash", "sha256").lower()
    if not any((expected_name, expected_id, expected_hash)):
        return True
    names = {
        _normalized_document_name(document.get("nome")),
        _normalized_document_name(document.get("nome_originale")),
        _normalized_document_name(document.get("original_filename")),
    }
    ids = {
        _text(document.get("id_documento_portale")),
        _text(document.get("portal_document_id")),
        _text(document.get("id_documento")),
        _text(document.get("id_cat_portale")),
        _text(document.get("id_cat")),
    }
    hashes = {
        _text(document.get("hash_sha256")).lower(),
        _text(document.get("content_sha256")).lower(),
        _text(document.get("sha256")).lower(),
    }
    return bool(
        (expected_name and expected_name in names)
        or (expected_id and expected_id in ids)
        or (expected_hash and expected_hash in hashes)
    )


def _candidate_documents(repository: Any, presidio_ids: Iterable[str]) -> dict[str, list[dict[str, Any]]]:
    selected = tuple(sorted({_text(value) for value in presidio_ids if _text(value)}))
    grouped = {presidio_id: [] for presidio_id in selected}
    if not selected:
        return grouped
    placeholders = ",".join("?" for _ in selected)
    with repository.connection() as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM pec_legal_notification_documents
            WHERE tenant_id=? AND presidio_id IN ({placeholders})
            ORDER BY authoritative DESC, created_at DESC, id DESC
            """,
            (repository.tenant_id, *selected),
        ).fetchall()
    for raw in rows:
        row = repository._row(raw)
        grouped.setdefault(_text(row.get("presidio_id")), []).append(row)
    return grouped


def _active_presidia(
    repository: Any,
    fascicolo_id: str,
    seed_presidio: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cursor: tuple[str, str] | None = None
    while True:
        page = repository.list_presidia(
            fascicolo_id=fascicolo_id,
            cursor=cursor,
            limit=100,
        )
        rows.extend(repository.get_presidio(item.id) for item in page.items)
        if page.next_cursor is None or page.next_cursor == cursor:
            break
        cursor = page.next_cursor
    if seed_presidio is not None:
        seed = dict(seed_presidio)
        if (
            _text(seed.get("fascicolo_id")) == _text(fascicolo_id)
            and _text(seed.get("status")) not in _TERMINAL_STATUSES
            and all(_text(row.get("id")) != _text(seed.get("id")) for row in rows)
        ):
            rows.insert(0, seed)
    return [row for row in rows if _text(row.get("status")) not in _TERMINAL_STATUSES]


def _candidate_expected_names(documents: Iterable[Mapping[str, Any]]) -> set[str]:
    result: set[str] = set()
    for document in documents:
        if _text(document.get("document_role")) == "portal_original":
            continue
        for key in ("original_filename", "filename", "portal_reference"):
            normalized = _normalized_document_name(document.get(key))
            if normalized:
                result.add(normalized)
    return result


def _select_candidate_and_document(
    candidates: list[dict[str, Any]],
    originals: list[dict[str, Any]],
    documents_by_presidio: Mapping[str, list[dict[str, Any]]],
    target: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str]:
    target_presidio_id = _target_value(target, "presidioId", "presidio_id")
    target_message_id = _target_value(target, "pecId", "pec_id", "source_message_id")
    if target_presidio_id:
        candidates = [row for row in candidates if _text(row.get("id")) == target_presidio_id]
        if not candidates:
            return None, None, "presidio_target_non_appartenente_al_fascicolo"
    if target_message_id:
        candidates = [
            row
            for row in candidates
            if _text(row.get("source_message_id")).strip("<>").casefold() == target_message_id.strip("<>").casefold()
        ]
        if not candidates:
            return None, None, "pec_target_non_appartenente_al_presidio"

    target_has_document_identity = bool(
        _target_value(target, "documento", "nome", "documento_portale")
        or _target_value(target, "idDocumento", "id_documento", "portal_document_id")
        or _target_value(target, "hash", "sha256")
    )
    matching_originals = [row for row in originals if _document_matches_target(row, target)]
    if target_has_document_identity:
        if len(matching_originals) != 1:
            return None, None, "documento_target_non_univoco"
        originals = matching_originals

    if len(candidates) == 1 and len(originals) == 1:
        return candidates[0], originals[0], "correlazione_univoca_fascicolo"

    matches: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for candidate in candidates:
        expected_names = _candidate_expected_names(documents_by_presidio.get(_text(candidate.get("id")), []))
        if not expected_names:
            continue
        for original in originals:
            imported_names = {
                _normalized_document_name(original.get("nome")),
                _normalized_document_name(original.get("nome_originale")),
                _normalized_document_name(original.get("original_filename")),
            }
            if expected_names.intersection(imported_names):
                matches.append((candidate, original))
    unique_matches = {
        (_text(candidate.get("id")), _text(document.get("fascicolo_document_id"))): (candidate, document)
        for candidate, document in matches
    }
    if len(unique_matches) == 1:
        candidate, document = next(iter(unique_matches.values()))
        return candidate, document, "nome_documento_coincidente"
    return None, None, "correlazione_ambigua"


def register_imported_pst_originals(
    repository: Any,
    *,
    fascicolo_id: str,
    imported_documents: Iterable[Mapping[str, Any]],
    actor: str,
    target_document: Mapping[str, Any] | None = None,
    candidate_presidio: Mapping[str, Any] | None = None,
    projector: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Collega un originale importato solo quando fascicolo, presidio e file sono univoci."""

    safe_fascicolo_id = _text(fascicolo_id)
    originals = [dict(row) for row in imported_documents if _is_portal_original(row)]
    originals = [row for row in originals if _text(row.get("fascicolo_document_id") or row.get("id"))]
    report: dict[str, Any] = {
        "ok": True,
        "fascicolo_id": safe_fascicolo_id,
        "originali_valutati": len(originals),
        "collegati": [],
        "saltati": [],
        "materializzazione": {},
    }
    if not safe_fascicolo_id or not originals:
        report["saltati"].append({"reason": "nessun_originale_pst_importato"})
        return report

    candidates = _active_presidia(repository, safe_fascicolo_id, candidate_presidio)
    if not candidates:
        report["saltati"].append({"reason": "nessun_presidio_attivo_nel_fascicolo"})
        return report
    documents_by_presidio = _candidate_documents(
        repository,
        (_text(row.get("id")) for row in candidates),
    )
    candidate, original, correlation_reason = _select_candidate_and_document(
        candidates,
        originals,
        documents_by_presidio,
        dict(target_document or {}),
    )
    if candidate is None or original is None:
        report["ok"] = False
        report["saltati"].append({"reason": correlation_reason})
        return report

    presidio_id = _text(candidate.get("id"))
    document_payload = _portal_document_payload(original)
    identity = canonical_document_identity(document_payload)
    existing_rows = documents_by_presidio.get(presidio_id, [])
    existing_original = next(
        (
            row
            for row in existing_rows
            if _text(row.get("identity_key")) == identity.key
            and _text(row.get("document_role")) == "portal_original"
            and bool(row.get("authoritative"))
            and bool(_text(row.get("fascicolo_document_id")))
        ),
        None,
    )
    linked_document = repository.upsert_document(
        presidio_id,
        {**document_payload, "identity_key": identity.key},
    )
    evidence = {
        "evidence_key": f"pst-portal-original:{identity.key}",
        "evidence_type": "document",
        "source_type": "document",
        "source_id": _text(document_payload.get("fascicolo_document_id")),
        "attachment_sha256": _text(document_payload.get("content_sha256")),
        "text_excerpt": "Documento PST acquisito dal Portale Servizi e collegato al fascicolo.",
        "source_locator": _text(document_payload.get("portal_reference")),
        "confidence": 1.0,
    }
    repository.append_evidence(presidio_id, evidence)

    previous_status = _text(repository.get_presidio(presidio_id).get("status"))
    transition = None
    transition_evidence = {
        "fascicolo_document_id": _text(document_payload.get("fascicolo_document_id")),
        "portal_document_id": _text(document_payload.get("portal_document_id")),
        "portal_reference": _text(document_payload.get("portal_reference")),
        "content_sha256": _text(document_payload.get("content_sha256")),
    }
    transition_status = previous_status
    for _attempt in range(2):
        if transition_status not in _ORIGINAL_ACQUIRED_TRANSITION_STATUSES:
            break
        try:
            transition = repository.transition(
                presidio_id,
                PresidioStatus.ORIGINAL_ACQUIRED,
                actor=_text(actor) or "sistema",
                reason="Documento PST acquisito e collegato al fascicolo.",
                evidence=transition_evidence,
                idempotency_key=f"pst-original-acquired:{identity.key}",
                expected_status=transition_status,
            )
            break
        except ValueError:
            refreshed_status = _text(repository.get_presidio(presidio_id).get("status"))
            if refreshed_status == transition_status:
                raise
            transition_status = refreshed_status
    current_status = _text(repository.get_presidio(presidio_id).get("status"))
    newly_linked = existing_original is None
    report["collegati"].append(
        {
            "presidio_id": presidio_id,
            "fascicolo_document_id": _text(linked_document.get("fascicolo_document_id")),
            "document_role": _text(linked_document.get("document_role")),
            "authoritative": bool(linked_document.get("authoritative")),
            "identity_key": identity.key,
            "correlation_reason": correlation_reason,
            "previous_status": previous_status,
            "status": current_status,
            "transitioned": bool(transition and transition.inserted),
            "newly_linked": newly_linked,
        }
    )
    if projector is not None and (newly_linked or bool(transition and transition.inserted)):
        report["materializzazione"] = projector(
            presidio_ids=[presidio_id],
            redispatch_presidio_ids=[presidio_id] if newly_linked else [],
        )
        report["ok"] = bool(report["materializzazione"].get("ok", False))
    return report


def link_existing_pst_originals_from_fascicolo(
    repository: Any,
    *,
    presidio: Mapping[str, Any],
    actor: str,
    portal_context: Mapping[str, Any] | None = None,
    projector: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Riconcilia un presidio con provvedimenti PST già presenti nel fascicolo.

    Il controllo è volutamente leggero: legge solo il fascicolo già collegato al
    presidio e considera soltanto documenti PST decisori. Non scansiona la casella
    PEC, non apre ZIP/OCR e non sceglie in modo arbitrario se ci sono più
    provvedimenti compatibili.
    """

    fascicolo_id = _text(presidio.get("fascicolo_id"))
    source_message_id = _text(presidio.get("source_message_id"))
    if not fascicolo_id:
        return {
            "ok": True,
            "fascicolo_id": "",
            "originali_valutati": 0,
            "collegati": [],
            "saltati": [{"reason": "presidio_senza_fascicolo"}],
            "materializzazione": {},
        }
    imported_documents = _existing_pst_documents_from_fascicolo(
        fascicolo_id,
        notification_case=_text(presidio.get("notification_case")),
        portal_context=portal_context,
    )
    if not imported_documents:
        return {
            "ok": True,
            "fascicolo_id": fascicolo_id,
            "originali_valutati": 0,
            "collegati": [],
            "saltati": [{"reason": "nessun_provvedimento_pst_decisorio_nel_fascicolo"}],
            "materializzazione": {},
        }
    presidio_id = _text(presidio.get("id"))
    report = register_imported_pst_originals(
        repository,
        fascicolo_id=fascicolo_id,
        imported_documents=imported_documents,
        actor=actor,
        target_document={
            "presidioId": presidio_id,
            "pecId": source_message_id,
        },
        candidate_presidio=presidio,
        projector=projector,
    )
    return report


def link_existing_pst_originals_for_current_tenant(
    repository: Any,
    *,
    presidio: Mapping[str, Any],
    actor: str,
    portal_context: Mapping[str, Any] | None = None,
    paths: Mapping[str, Any] | None = None,
    database: Any = None,
) -> dict[str, Any]:
    """Wrapper Flask per aggiornare anche Agenda/Scadenziario/topbar dopo il link."""

    from web.services.notifications_runtime import (
        current_tenant_id,
        materialize_selected_advanced_notification_presidia_for_paths,
    )

    runtime_paths = dict(paths or (getattr(g, "data_paths", {}) if has_app_context() else {}) or {})
    if not runtime_paths:
        return link_existing_pst_originals_from_fascicolo(
            repository,
            presidio=presidio,
            actor=actor,
            portal_context=portal_context,
            projector=None,
        )

    def _projector(*, presidio_ids: list[str], redispatch_presidio_ids: list[str]) -> dict[str, Any]:
        return materialize_selected_advanced_notification_presidia_for_paths(
            runtime_paths,
            tenant_label=repository.tenant_id,
            tenant_id=current_tenant_id(),
            presidio_tenant_id=repository.tenant_id,
            presidio_ids=presidio_ids,
            superseded_presidio_ids=presidio_ids,
            redispatch_presidio_ids=redispatch_presidio_ids,
            database=database,
        )

    return link_existing_pst_originals_from_fascicolo(
        repository,
        presidio=presidio,
        actor=actor,
        portal_context=portal_context,
        projector=_projector,
    )


def link_imported_pst_originals_for_current_tenant(
    *,
    fascicolo_id: str,
    imported_documents: Iterable[Mapping[str, Any]],
    actor: str,
    target_document: Mapping[str, Any] | None = None,
    paths: Mapping[str, Any] | None = None,
    database: Any = None,
) -> dict[str, Any]:
    """Wrapper Flask tenant-aware usato dal runtime di acquisizione PST."""

    from web.services.notification_presidia_runtime import build_notification_presidio_repository
    from web.services.notifications_runtime import (
        current_tenant_id,
        materialize_selected_advanced_notification_presidia_for_paths,
    )

    repository = build_notification_presidio_repository()
    runtime_paths = dict(paths or (getattr(g, "data_paths", {}) if has_app_context() else {}) or {})
    if not runtime_paths:
        raise RuntimeError("Percorsi tenant non disponibili per materializzare il presidio notifiche.")

    def _projector(*, presidio_ids: list[str], redispatch_presidio_ids: list[str]) -> dict[str, Any]:
        return materialize_selected_advanced_notification_presidia_for_paths(
            runtime_paths,
            tenant_label=repository.tenant_id,
            tenant_id=current_tenant_id(),
            presidio_tenant_id=repository.tenant_id,
            presidio_ids=presidio_ids,
            superseded_presidio_ids=presidio_ids,
            redispatch_presidio_ids=redispatch_presidio_ids,
            database=database,
        )

    try:
        return register_imported_pst_originals(
            repository,
            fascicolo_id=fascicolo_id,
            imported_documents=imported_documents,
            actor=actor,
            target_document=target_document,
            projector=_projector,
        )
    except Exception:
        if has_app_context():
            current_app.logger.exception(
                "Collegamento originale PST al presidio non completato per il fascicolo %s",
                fascicolo_id,
            )
        raise


__all__ = [
    "link_existing_pst_originals_for_current_tenant",
    "link_existing_pst_originals_from_fascicolo",
    "link_imported_pst_originals_for_current_tenant",
    "register_imported_pst_originals",
]
