"""Bridge read-only per le superfici React del Sito Studio."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from web.services.studio_site_runtime import build_studio_site_dashboard_payload


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    return bool(value)


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _tone_for_status(status: str) -> str:
    clean = status.lower()
    if clean in {"published", "active", "approved", "ok"}:
        return "success"
    if clean in {"pending", "draft", "bozza"}:
        return "warning"
    if clean in {"rejected", "inactive", "error"}:
        return "danger"
    return "neutral"


def _site_summary(site: dict[str, Any], public_url: str) -> dict[str, Any]:
    return {
        "id": _int(site.get("id")),
        "tenantSlug": _text(site.get("tenant_slug")),
        "studioName": _text(site.get("studio_nome")),
        "siteName": _text(site.get("site_name")),
        "publicSlug": _text(site.get("public_slug")),
        "title": _text(site.get("site_title")),
        "description": _text(site.get("site_description")),
        "claim": _text(site.get("hero_claim")),
        "contactEmail": _text(site.get("contact_email")),
        "contactPhone": _text(site.get("contact_phone")),
        "address": _text(site.get("address")),
        "city": _text(site.get("city")),
        "province": _text(site.get("province")),
        "zipCode": _text(site.get("zip_code")),
        "published": _bool(site.get("is_published")),
        "active": _bool(site.get("is_active")),
        "updatedAt": _text(site.get("updated_at")),
        "publicUrl": _text(public_url),
        "showLegalTools": _bool(site.get("show_legal_tools")),
        "showApplications": _bool(site.get("show_applications")),
        "showLegalNews": _bool(site.get("show_legal_news")),
    }


def _page(row: dict[str, Any]) -> dict[str, Any]:
    row_id = _int(row.get("id"))
    status = _text(row.get("status") or "draft")
    return {
        "id": str(row_id),
        "kind": "page",
        "title": _text(row.get("title")),
        "subtitle": _text(row.get("excerpt")),
        "status": status,
        "statusTone": _tone_for_status(status),
        "href": f"/sito-studio/pagine/{row_id}/modifica?_legacy=1" if row_id else "",
        "meta": [
            {"label": "Slug", "value": _text(row.get("slug"))},
            {"label": "Menu", "value": "visibile" if _bool(row.get("show_in_menu")) else "nascosta"},
            {"label": "Home", "value": "si" if _bool(row.get("is_home")) else "no"},
        ],
    }


def _article(row: dict[str, Any]) -> dict[str, Any]:
    row_id = _int(row.get("id"))
    status = _text(row.get("status") or "draft")
    return {
        "id": str(row_id),
        "kind": "article",
        "title": _text(row.get("title")),
        "subtitle": _text(row.get("excerpt")),
        "status": status,
        "statusTone": _tone_for_status(status),
        "href": f"/sito-studio/articoli/{row_id}/modifica?_legacy=1" if row_id else "",
        "meta": [
            {"label": "Categoria", "value": _text(row.get("category"))},
            {"label": "Autore", "value": _text(row.get("author_name"))},
            {"label": "Pubblicato", "value": _text(row.get("published_at") or row.get("created_at"))},
        ],
    }


def _service(row: dict[str, Any]) -> dict[str, Any]:
    row_id = _int(row.get("id"))
    return {
        "id": str(row_id),
        "kind": "service",
        "title": _text(row.get("title")),
        "subtitle": _text(row.get("short_description")),
        "status": "visible" if _bool(row.get("is_visible")) else "hidden",
        "statusTone": "success" if _bool(row.get("is_visible")) else "neutral",
        "href": f"/sito-studio/servizi/{row_id}/modifica?_legacy=1" if row_id else "",
        "meta": [{"label": "Ordine", "value": _text(row.get("sort_order"))}],
    }


def _professional(row: dict[str, Any]) -> dict[str, Any]:
    row_id = _int(row.get("id"))
    return {
        "id": str(row_id),
        "kind": "professional",
        "title": _text(row.get("full_name")),
        "subtitle": _text(row.get("role_title")),
        "status": "visible" if _bool(row.get("is_visible")) else "hidden",
        "statusTone": "success" if _bool(row.get("is_visible")) else "neutral",
        "href": f"/sito-studio/professionisti/{row_id}/modifica?_legacy=1" if row_id else "",
        "meta": [
            {"label": "Email", "value": _text(row.get("email"))},
            {"label": "Telefono", "value": _text(row.get("phone"))},
        ],
    }


def _office(row: dict[str, Any]) -> dict[str, Any]:
    row_id = _int(row.get("id"))
    city = " ".join(part for part in [_text(row.get("zip_code")), _text(row.get("city")), _text(row.get("province"))] if part)
    return {
        "id": str(row_id),
        "kind": "office",
        "title": _text(row.get("name")),
        "subtitle": city,
        "status": "primary" if _bool(row.get("is_primary")) else "secondary",
        "statusTone": "primary" if _bool(row.get("is_primary")) else "neutral",
        "href": f"/sito-studio/sedi/{row_id}/modifica?_legacy=1" if row_id else "",
        "meta": [
            {"label": "Indirizzo", "value": _text(row.get("address"))},
            {"label": "Email", "value": _text(row.get("email"))},
            {"label": "Telefono", "value": _text(row.get("phone"))},
        ],
    }


def _contact(row: dict[str, Any]) -> dict[str, Any]:
    row_id = _int(row.get("id"))
    lead_id = _text(row.get("lead_cliente_id"))
    return {
        "id": str(row_id),
        "kind": "contact",
        "title": _text(row.get("full_name")),
        "subtitle": _text(row.get("subject")) or "Richiesta contatto",
        "status": "cliente collegato" if lead_id else "da gestire",
        "statusTone": "success" if lead_id else "warning",
        "href": f"/clienti/{lead_id}" if lead_id else "",
        "meta": [
            {"label": "Email", "value": _text(row.get("email"))},
            {"label": "Telefono", "value": _text(row.get("phone"))},
            {"label": "Messaggio", "value": _text(row.get("message"))},
            {"label": "Data", "value": _text(row.get("created_at"))},
        ],
        "forms": [] if lead_id else [
            {
                "id": f"contatto_{row_id}_cliente",
                "title": "Crea cliente potenziale",
                "description": "Invio standard verso la route legacy auditata.",
                "action": f"/sito-studio/contatti/{row_id}/crea-cliente",
                "method": "POST",
                "submitLabel": "Crea cliente",
                "enabled": bool(row_id),
                "fields": [],
            }
        ],
    }


def _booking(row: dict[str, Any]) -> dict[str, Any]:
    row_id = _int(row.get("id"))
    status = _text(row.get("status") or "pending")
    pending = status.lower() == "pending"
    return {
        "id": str(row_id),
        "kind": "booking",
        "title": _text(row.get("customer_name")),
        "subtitle": _text(row.get("subject")) or "Prenotazione appuntamento",
        "status": status,
        "statusTone": _tone_for_status(status),
        "href": "/sito-studio/prenotazioni?_legacy=1",
        "meta": [
            {"label": "Email", "value": _text(row.get("customer_email"))},
            {"label": "Telefono", "value": _text(row.get("customer_phone"))},
            {"label": "Data", "value": " ".join(part for part in [_text(row.get("requested_date")), _text(row.get("requested_time"))] if part)},
            {"label": "Sede", "value": _text(row.get("office_name"))},
        ],
        "forms": [] if not pending else [
            {
                "id": f"prenotazione_{row_id}_approva",
                "title": "Approva prenotazione",
                "description": "Sincronizza tramite POST legacy.",
                "action": f"/sito-studio/prenotazioni/{row_id}/approva",
                "method": "POST",
                "submitLabel": "Approva",
                "enabled": bool(row_id),
                "fields": [],
            },
            {
                "id": f"prenotazione_{row_id}_rifiuta",
                "title": "Rifiuta prenotazione",
                "description": "Aggiorna lo stato tramite POST legacy.",
                "action": f"/sito-studio/prenotazioni/{row_id}/rifiuta",
                "method": "POST",
                "submitLabel": "Rifiuta",
                "enabled": bool(row_id),
                "fields": [],
            },
        ],
    }


def _metric(metric_id: str, label: str, value: Any, note: str, tone: str = "neutral") -> dict[str, Any]:
    return {"id": metric_id, "label": label, "value": value, "note": note, "tone": tone}


def _section(section_id: str, title: str, items: list[dict[str, Any]], empty: str) -> dict[str, Any]:
    return {"id": section_id, "title": title, "kind": "summary", "items": items, "emptyMessage": empty}


def _contracts(route: str) -> dict[str, Any]:
    name = route.strip("/").replace("/", "__") or "root"
    return {
        "mock_fallback": False,
        "writes": "legacy_routes",
        "route_owner": "react_shell",
        "legacy_contract": f"artifacts/react-migration/legacy-contracts/{name}.json",
    }


def _base_payload(route: str, dashboard: dict[str, Any]) -> dict[str, Any]:
    site = dashboard.get("site") or {}
    stats = dashboard.get("stats") or {}
    site_summary = _site_summary(site, _text(dashboard.get("public_url")))
    records = (
        [_page(row) for row in dashboard.get("pages", [])]
        + [_article(row) for row in dashboard.get("articles", [])]
        + [_service(row) for row in dashboard.get("services", [])]
        + [_professional(row) for row in dashboard.get("professionals", [])]
        + [_office(row) for row in dashboard.get("offices", [])]
    )

    return {
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": _contracts(route),
        "site": site_summary,
        "metrics": [
            _metric("pages", "Pagine", _int(stats.get("pages")), "Pagine del sito", "primary"),
            _metric("articles", "Articoli", _int(stats.get("articles")), "Contenuti editoriali", "info"),
            _metric("contacts", "Contatti", _int(stats.get("contact_submissions")), "Richieste ricevute", "warning" if _int(stats.get("contact_submissions")) else "neutral"),
            _metric("bookings", "Prenotazioni", _int(stats.get("pending_booking_requests")), "Richieste in attesa", "warning" if _int(stats.get("pending_booking_requests")) else "success"),
        ],
        "sections": [
            _section(
                "status",
                "Stato pubblicazione",
                [
                    {"id": "active", "label": "Sito", "value": "attivo" if site_summary["active"] else "disattivo", "note": "Flag operativo", "tone": "success" if site_summary["active"] else "warning"},
                    {"id": "published", "label": "Pubblicazione", "value": "pubblicato" if site_summary["published"] else "bozza", "note": "Visibilita pubblica", "tone": "success" if site_summary["published"] else "warning"},
                    {"id": "public", "label": "URL pubblico", "value": site_summary["publicUrl"], "note": "Anteprima reale", "tone": "primary" if site_summary["publicUrl"] else "neutral"},
                ],
                "Stato sito non disponibile.",
            ),
            _section(
                "catalog",
                "Catalogo contenuti",
                [
                    {"id": "services", "label": "Servizi", "value": _int(stats.get("services")), "note": "Servizi pubblicabili", "tone": "primary"},
                    {"id": "professionals", "label": "Professionisti", "value": _int(stats.get("professionals")), "note": "Profili studio", "tone": "primary"},
                    {"id": "offices", "label": "Sedi", "value": _int(stats.get("offices")), "note": "Sedi e recapiti", "tone": "primary"},
                ],
                "Catalogo non configurato.",
            ),
        ],
        "records": records,
        "actions": [
            {"id": "builder", "label": "Apri Builder Pro legacy", "href": "/sito-studio/builder?_legacy=1", "method": "GET", "tone": "primary"},
            {"id": "settings", "label": "Impostazioni sito legacy", "href": "/sito-studio/impostazioni?_legacy=1", "method": "GET", "tone": "neutral"},
            {"id": "contacts", "label": "Richieste contatto", "href": "/sito-studio/contatti", "method": "GET", "tone": "warning"},
            {"id": "bookings", "label": "Prenotazioni legacy", "href": "/sito-studio/prenotazioni?_legacy=1", "method": "GET", "tone": "neutral"},
            {"id": "public", "label": "Apri sito pubblico", "href": site_summary["publicUrl"], "method": "GET", "tone": "success"},
        ],
        "forms": [],
        "warnings": [
            {"code": "builder_legacy", "message": "Builder, pubblicazione avanzata e asset restano sulle route legacy in questa tranche."},
            *[
                {"code": "sito_studio", "message": _text(message)}
                for message in dashboard.get("warnings", [])
                if _text(message)
            ],
        ],
    }


def build_react_sito_studio_payload(*, contacts_only: bool = False) -> dict[str, Any]:
    dashboard = build_studio_site_dashboard_payload()
    route = "/sito-studio/contatti" if contacts_only else "/sito-studio"
    payload = _base_payload(route, dashboard)

    contact_records = [_contact(row) for row in dashboard.get("contact_submissions", [])]
    booking_records = [_booking(row) for row in dashboard.get("booking_requests", [])]
    if contacts_only:
        payload["records"] = contact_records + booking_records
        payload["actions"] = [
            {"id": "dashboard", "label": "Torna al Sito Studio", "href": "/sito-studio", "method": "GET", "tone": "neutral"},
            {"id": "contacts-legacy", "label": "Apri contatti legacy", "href": "/sito-studio/contatti?_legacy=1", "method": "GET", "tone": "primary"},
            {"id": "bookings-legacy", "label": "Apri prenotazioni legacy", "href": "/sito-studio/prenotazioni?_legacy=1", "method": "GET", "tone": "warning"},
        ]
        payload["warnings"].append(
            {"code": "gestione_legacy", "message": "Conversione contatti e gestione prenotazioni inviano form standard alle route legacy."}
        )
    else:
        payload["records"] = payload["records"] + contact_records[:4] + booking_records[:4]
    return payload


def build_react_sito_studio_error_payload(message: str = "Sito Studio non disponibile.") -> dict[str, Any]:
    return {
        "source": "errore_controllato",
        "generated_at": _iso_now(),
        "contracts": _contracts("/sito-studio"),
        "site": {},
        "metrics": [],
        "sections": [],
        "records": [],
        "actions": [{"id": "legacy", "label": "Apri Sito Studio legacy", "href": "/sito-studio?_legacy=1", "method": "GET", "tone": "neutral"}],
        "forms": [],
        "warnings": [{"code": "sito_studio_errore", "message": message}],
    }
