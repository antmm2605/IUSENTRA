"""Bridge JSON reale per Cartelle Condivise React."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from pct.condivisione import RuoloCondivisione
from web.services.ui_localization import format_date


ROLE_LABELS = {
    RuoloCondivisione.LETTURA.value: "Lettura",
    RuoloCondivisione.SCRITTURA.value: "Scrittura",
    RuoloCondivisione.GESTORE.value: "Gestore",
}

ROLE_TONES = {
    RuoloCondivisione.LETTURA.value: "info",
    RuoloCondivisione.SCRITTURA.value: "primary",
    RuoloCondivisione.GESTORE.value: "warning",
}


def _safe_text(value: Any, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "").strip()


def _days_to(value: str) -> int | None:
    raw = _safe_text(value)
    if not raw:
        return None
    try:
        return (datetime.fromisoformat(raw[:10]).date() - datetime.now().date()).days
    except ValueError:
        return None


def _client_payload(cliente: Any | None, fallback_id: str = "") -> dict[str, str]:
    client_id = _safe_text(getattr(cliente, "id", "") or fallback_id)
    return {
        "id": client_id,
        "name": _safe_text(getattr(cliente, "nome_completo", ""), "Cliente non disponibile" if not client_id else client_id),
        "type": _enum_value(getattr(cliente, "tipo", "")),
        "href": f"/clienti/{client_id}" if client_id else "",
        "collaboratorsHref": f"/clienti/{client_id}/collaboratori" if client_id else "",
    }


def _access_payload(accesso: Any) -> dict[str, Any]:
    role = _enum_value(getattr(accesso, "ruolo", RuoloCondivisione.LETTURA.value)) or RuoloCondivisione.LETTURA.value
    deadline = _safe_text(getattr(accesso, "data_scadenza", ""))
    days = getattr(accesso, "giorni_alla_scadenza", None)
    if days is None:
        days = _days_to(deadline)
    expired = bool(getattr(accesso, "is_scaduto", False))
    expiring = days is not None and 0 <= int(days) <= 7
    return {
        "idUser": _safe_text(getattr(accesso, "id_utente", "")),
        "username": _safe_text(getattr(accesso, "username", "")),
        "name": _safe_text(getattr(accesso, "nome_completo", "") or getattr(accesso, "username", ""), "Collaboratore"),
        "role": role,
        "roleLabel": ROLE_LABELS.get(role, role),
        "roleTone": ROLE_TONES.get(role, "neutral"),
        "sharedBy": _safe_text(getattr(accesso, "condiviso_da", "")),
        "sharedAt": _safe_text(getattr(accesso, "data_condivisione", "")),
        "sharedAtLabel": format_date(getattr(accesso, "data_condivisione", "")),
        "deadline": deadline,
        "deadlineLabel": format_date(deadline) if deadline else "Nessuna scadenza",
        "daysToDeadline": days,
        "expired": expired,
        "expiring": expiring,
        "notes": _safe_text(getattr(accesso, "note", "")),
        "tags": list(getattr(accesso, "tags", []) or []),
    }


def _link_payload(link: Any) -> dict[str, Any]:
    return {
        "id": _safe_text(getattr(link, "id", "")),
        "role": _enum_value(getattr(link, "ruolo", "")),
        "roleLabel": ROLE_LABELS.get(_enum_value(getattr(link, "ruolo", "")), _enum_value(getattr(link, "ruolo", ""))),
        "expiresAt": _safe_text(getattr(link, "scade_il", "")),
        "expiresLabel": format_date(getattr(link, "scade_il", "")),
        "createdBy": _safe_text(getattr(link, "creato_da", "")),
        "oneShot": bool(getattr(link, "monouso", False)),
        "description": _safe_text(getattr(link, "descrizione", "")),
    }


def _folder_payload(cliente: Any, accessi: list[Any], links: list[Any]) -> dict[str, Any]:
    role_counts: dict[str, int] = {}
    access_payloads = [_access_payload(accesso) for accesso in accessi]
    for accesso in access_payloads:
        role_counts[accesso["role"]] = role_counts.get(accesso["role"], 0) + 1
    client = _client_payload(cliente)
    return {
        "client": client,
        "collaboratorsCount": len(access_payloads),
        "accesses": access_payloads,
        "roleCounts": role_counts,
        "expiredCount": sum(1 for item in access_payloads if item["expired"]),
        "expiringCount": sum(1 for item in access_payloads if item["expiring"]),
        "activeLinks": [_link_payload(link) for link in links],
        "openHref": client["href"],
        "manageHref": client["collaboratorsHref"],
    }


def _received_folder_payload(cliente: Any | None, accesso: Any, fallback_id: str) -> dict[str, Any]:
    client = _client_payload(cliente, fallback_id)
    access = _access_payload(accesso)
    return {
        "client": client,
        "access": access,
        "openHref": "" if access["expired"] else client["href"],
        "manageHref": client["collaboratorsHref"] if access["role"] in {RuoloCondivisione.SCRITTURA.value, RuoloCondivisione.GESTORE.value} else "",
    }


def _received_matter_payload(fascicolo: Any | None, cliente: Any | None, accesso: Any, fallback_id: str) -> dict[str, Any]:
    matter_id = _safe_text(getattr(fascicolo, "id", "") or fallback_id)
    return {
        "id": matter_id,
        "title": _safe_text(getattr(fascicolo, "titolo", ""), "Fascicolo condiviso" if not matter_id else matter_id),
        "number": _safe_text(getattr(fascicolo, "numero", "")),
        "client": _client_payload(cliente, _safe_text(getattr(fascicolo, "id_cliente", ""))),
        "access": _access_payload(accesso),
        "href": f"/fascicoli/{matter_id}" if matter_id else "",
    }


def build_react_condivisioni_payload(
    *,
    get_condivisioni: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_fascicoli: Callable[[], Any],
    current_user: Any,
) -> dict[str, Any]:
    condivisioni = get_condivisioni()
    clienti_manager = get_clienti()
    fascicoli_manager = get_fascicoli()
    user_id = _safe_text(getattr(current_user, "id", ""))
    has_permission = getattr(current_user, "ha_permesso", lambda _permission: False)
    is_manager = bool(has_permission("clienti.leggi"))
    stats = condivisioni.statistiche()

    try:
        clienti = clienti_manager.tutti(stato=None)
    except TypeError:
        clienti = clienti_manager.tutti()

    managed_folders: list[dict[str, Any]] = []
    if is_manager:
        for cliente in clienti:
            client_id = _safe_text(getattr(cliente, "id", ""))
            accessi = list(condivisioni.collaboratori_di(client_id))
            links = list(condivisioni.link_attivi_per_cliente(client_id))
            if accessi or links:
                managed_folders.append(_folder_payload(cliente, accessi, links))

    received_folders = [
        _received_folder_payload(clienti_manager.get(id_cliente), accesso, id_cliente)
        for id_cliente, accesso in condivisioni.cartelle_condivise_con(user_id)
        if clienti_manager.get(id_cliente)
    ]

    received_matters = []
    for id_fascicolo, accesso in condivisioni.fascicoli_condivisi_con(user_id):
        fascicolo = fascicoli_manager.get(id_fascicolo)
        cliente = clienti_manager.get(getattr(fascicolo, "id_cliente", "")) if fascicolo else None
        received_matters.append(_received_matter_payload(fascicolo, cliente, accesso, id_fascicolo))

    warnings: list[dict[str, Any]] = []
    if int(stats.get("accessi_scaduti") or 0):
        warnings.append({"tone": "danger", "label": "Accessi scaduti", "count": int(stats.get("accessi_scaduti") or 0)})
    if int(stats.get("accessi_in_scadenza_7gg") or 0):
        warnings.append({"tone": "warning", "label": "Accessi in scadenza", "count": int(stats.get("accessi_in_scadenza_7gg") or 0)})
    elevated = int((stats.get("per_ruolo") or {}).get(RuoloCondivisione.SCRITTURA.value, 0)) + int((stats.get("per_ruolo") or {}).get(RuoloCondivisione.GESTORE.value, 0))
    if elevated:
        warnings.append({"tone": "primary", "label": "Ruoli scrittura/gestore", "count": elevated})
    if int(stats.get("link_temporanei_attivi") or 0):
        warnings.append({"tone": "orange", "label": "Link temporanei attivi", "count": int(stats.get("link_temporanei_attivi") or 0)})

    return {
        "source": "repository_reali",
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "contracts": {
            "mock_fallback": False,
            "writes": "operational_routes",
            "route_owner": "react_shell",
        },
        "mode": "gestore" if is_manager else "collaboratore",
        "permissions": {
            "canReadClients": is_manager,
            "canWriteClients": bool(has_permission("clienti.scrivi")),
            "canCleanExpired": bool(has_permission("utenti.scrivi")),
        },
        "stats": {
            "sharedFolders": int(stats.get("cartelle_condivise") or 0),
            "totalAccesses": int(stats.get("accessi_totali") or 0),
            "expiredAccesses": int(stats.get("accessi_scaduti") or 0),
            "expiring7Days": int(stats.get("accessi_in_scadenza_7gg") or 0),
            "activeTemporaryLinks": int(stats.get("link_temporanei_attivi") or 0),
            "sharedMatters": int(stats.get("fascicoli_condivisi") or 0),
            "perRole": dict(stats.get("per_ruolo") or {}),
        },
        "managedFolders": managed_folders,
        "receivedFolders": received_folders,
        "receivedMatters": received_matters,
        "warnings": warnings,
        "roleOptions": [{"value": role.value, "label": ROLE_LABELS[role.value], "tone": ROLE_TONES[role.value]} for role in RuoloCondivisione],
        "actions": {
            "clients": "/clienti",
            "audit": "/audit",
            "gdpr": "/privacy/registro",
            "cleanupExpired": "/api/v1/condivisioni/pulizia-scaduti",
            "statistics": "/api/v1/condivisioni/statistiche",
            "lex": "/lex?context=cartelle-condivise",
        },
        "emptyStates": {
            "noManagedFolders": not managed_folders,
            "noReceivedFolders": not received_folders,
            "noExpiringAccesses": not int(stats.get("accessi_in_scadenza_7gg") or 0),
        },
    }
