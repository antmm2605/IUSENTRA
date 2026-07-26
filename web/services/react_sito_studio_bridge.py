"""Bridge operativo per le superfici React del Sito Studio."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable

from web.services.studio_site_runtime import (
    approve_booking_request_for_current_site,
    audit_studio_site_action,
    build_studio_site_dashboard_payload,
    create_lead_cliente_from_submission,
    get_site_for_current_tenant,
    reject_booking_request_for_current_site,
    studio_site_repository,
)


Loader = Callable[[], Any]


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any, limit: int = 0) -> str:
    text = " ".join(str(value or "").split())
    if limit and len(text) > limit:
        return text[: limit - 1].rstrip() + "..."
    return text


def _bool(value: Any) -> bool:
    return bool(value)


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _can(user: Any, permission: str) -> bool:
    checker = getattr(user, "ha_permesso", None)
    return bool(callable(checker) and checker(permission))


def _tone_for_status(status: str) -> str:
    clean = status.lower()
    if clean in {"published", "active", "approved", "ok", "visible", "cliente_collegato"}:
        return "success"
    if clean in {"pending", "draft", "bozza", "nuovo"}:
        return "warning"
    if clean in {"rejected", "inactive", "error"}:
        return "danger"
    return "neutral"


def _contracts(route: str, *, writes: str) -> dict[str, Any]:
    name = _frontend_route_contract_name(route)
    contract = {
        "mock_fallback": False,
        "writes": writes,
        "route_owner": "react_shell",
        "operational": True,
        "legacy_contract": f"artifacts/react-migration/legacy-contracts/{name}.json",
    }
    if route == "/sito-studio":
        contract.update({"builder": "react_operativo", "publishing": "azioni_protette"})
    else:
        contract.update({"notifications": "legacy_protected", "automation": "legacy_protected"})
    return contract


def _frontend_route_contract_name(route: str) -> str:
    return route.strip("/").replace("/", "__").replace(":", "_") or "root"


def _metric(metric_id: str, label: str, value: Any, note: str, tone: str = "neutral") -> dict[str, Any]:
    return {"id": metric_id, "label": label, "value": value, "note": note, "tone": tone}


def _action(action_id: str, label: str, href: str, tone: str = "neutral", *, protected: bool = False) -> dict[str, Any]:
    return {
        "id": action_id,
        "label": label,
        "href": href,
        "method": "GET",
        "tone": tone,
        "protected": protected,
        "legacy_fallback": protected and "_legacy=1" in href,
    }


def _article_route(article_id: int | str = ":id") -> str:
    return f"/sito-studio/articoli/{article_id}/modifica"


def _article_status_label(status: str) -> str:
    return {
        "draft": "Bozza",
        "published": "Pubblicato",
        "archived": "Archiviato",
    }.get(status.lower(), status or "Bozza")


def _article_public_href(site: dict[str, Any], article: dict[str, Any]) -> str:
    public_slug = _text(site.get("public_slug"))
    slug = _text(article.get("slug"))
    if not public_slug or not slug:
        return ""
    return f"/web/{public_slug}/articoli/{slug}"


def _body_json_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value or [], ensure_ascii=False, indent=2)


def _body_plain_text(value: Any) -> str:
    blocks = value if isinstance(value, list) else []
    parts: list[str] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        title = _text(block.get("title"))
        text = str(block.get("text") or "").strip()
        if title and title not in parts:
            parts.append(title)
        if text:
            parts.append(text)
    return "\n\n".join(parts)


def _article_item(site: dict[str, Any], article: dict[str, Any]) -> dict[str, Any]:
    status = _text(article.get("status") or "draft")
    return {
        "id": str(_int(article.get("id"))),
        "title": _text(article.get("title"), 220),
        "slug": _text(article.get("slug")),
        "excerpt": _text(article.get("excerpt"), 800),
        "coverUrl": _text(article.get("cover_url")),
        "category": _text(article.get("category"), 120),
        "tagsCsv": _text(article.get("tags_csv"), 260),
        "authorName": _text(article.get("author_name"), 160),
        "bodyJsonText": _body_json_text(article.get("body_json")),
        "bodyText": _body_plain_text(article.get("body_json")),
        "status": status,
        "statusLabel": _article_status_label(status),
        "statusTone": _tone_for_status(status),
        "publishedAt": _text(article.get("published_at")),
        "updatedAt": _text(article.get("updated_at") or article.get("created_at")),
        "seoTitle": _text(article.get("seo_title"), 220),
        "seoDescription": _text(article.get("seo_description"), 320),
        "publicHref": _article_public_href(site, article),
    }


def _article_form_payload(payload: dict[str, Any], current: dict[str, Any] | None = None) -> dict[str, Any]:
    allowed = {
        "title",
        "slug",
        "excerpt",
        "cover_url",
        "coverUrl",
        "category",
        "tags_csv",
        "tagsCsv",
        "author_name",
        "authorName",
        "body_json",
        "bodyJsonText",
        "status",
        "published_at",
        "publishedAt",
        "seo_title",
        "seoTitle",
        "seo_description",
        "seoDescription",
    }
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ValueError(f"Campi non ammessi: {', '.join(unknown)}.")

    title = _text(payload.get("title"))
    if not title:
        raise ValueError("Titolo articolo richiesto.")

    status = _text(payload.get("status") or (current or {}).get("status") or "draft").lower()
    if status not in {"draft", "published", "archived"}:
        raise ValueError("Stato articolo non ammesso.")

    body_json = payload.get("body_json", payload.get("bodyJsonText", (current or {}).get("body_json", [])))
    if isinstance(body_json, str):
        try:
            parsed = json.loads(body_json or "[]")
        except json.JSONDecodeError as exc:
            raise ValueError("Contenuto articolo non leggibile: controlla il formato dei blocchi.") from exc
        body_json = parsed

    if not isinstance(body_json, list):
        raise ValueError("Il contenuto articolo deve essere una lista di blocchi.")

    def field(name: str, *aliases: str) -> str:
        for key in (name, *aliases):
            if key in payload:
                value = str(payload.get(key) or "")
                return value if value else " "
        if current is not None:
            return str(current.get(name) or "")
        return " "

    return {
        "title": title,
        "slug": _text(payload.get("slug")) if "slug" in payload else str((current or {}).get("slug") or ""),
        "excerpt": field("excerpt"),
        "cover_url": field("cover_url", "coverUrl"),
        "category": field("category"),
        "tags_csv": field("tags_csv", "tagsCsv"),
        "author_name": field("author_name", "authorName"),
        "body_json": body_json,
        "status": status,
        "published_at": field("published_at", "publishedAt"),
        "seo_title": field("seo_title", "seoTitle"),
        "seo_description": field("seo_description", "seoDescription"),
    }


def _site_summary(site: dict[str, Any], public_url: str) -> dict[str, Any]:
    return {
        "id": _int(site.get("id")),
        "tenantSlug": _text(site.get("tenant_slug")),
        "studioName": _text(site.get("studio_nome")),
        "siteName": _text(site.get("site_name")),
        "publicSlug": _text(site.get("public_slug")),
        "title": _text(site.get("site_title")),
        "description": _text(site.get("site_description"), 360),
        "claim": _text(site.get("hero_claim"), 180),
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


def _page(row: dict[str, Any], kind: str) -> dict[str, Any]:
    row_id = _int(row.get("id"))
    status = _text(row.get("status") or ("visible" if _bool(row.get("is_visible")) else "hidden"))
    title = _text(row.get("title") or row.get("full_name") or row.get("name"))
    subtitle = _text(row.get("excerpt") or row.get("short_description") or row.get("role_title") or row.get("city"), 180)
    return {
        "id": str(row_id),
        "kind": kind,
        "title": title,
        "subtitle": subtitle,
        "status": status,
        "statusTone": _tone_for_status(status),
        "meta": [
            {"label": "Slug", "value": _text(row.get("slug"))},
            {"label": "Categoria", "value": _text(row.get("category"))},
            {"label": "Menu", "value": "visibile" if _bool(row.get("show_in_menu")) else ""},
            {"label": "Aggiornato", "value": _text(row.get("updated_at") or row.get("created_at"))},
        ],
    }


def _contact(row: dict[str, Any]) -> dict[str, Any]:
    contact_id = _int(row.get("id"))
    lead_id = _text(row.get("lead_cliente_id"))
    status = "cliente_collegato" if lead_id else "nuovo"
    return {
        "id": str(contact_id),
        "fullName": _text(row.get("full_name"), 140),
        "email": _text(row.get("email"), 180),
        "phone": _text(row.get("phone"), 60),
        "subject": _text(row.get("subject"), 180),
        "message": _text(row.get("message"), 700),
        "createdAt": _text(row.get("created_at")),
        "status": status,
        "statusLabel": "Cliente collegato" if lead_id else "Da gestire",
        "statusTone": _tone_for_status(status),
        "leadClienteId": lead_id,
        "clientHref": f"/clienti/{lead_id}" if lead_id else "",
        "actions": {
            "canLinkClient": not bool(lead_id),
            "linkEndpoint": f"/api/v1/ui/sito-studio/contatti/{contact_id}/collega" if contact_id and not lead_id else "",
        },
    }


def _booking(row: dict[str, Any]) -> dict[str, Any]:
    booking_id = _int(row.get("id"))
    status = _text(row.get("status") or "pending")
    requested = " ".join(part for part in [_text(row.get("requested_date")), _text(row.get("requested_time"))] if part)
    return {
        "id": str(booking_id),
        "customerName": _text(row.get("customer_name"), 140),
        "email": _text(row.get("customer_email"), 180),
        "phone": _text(row.get("customer_phone"), 60),
        "subject": _text(row.get("subject"), 180),
        "notes": _text(row.get("notes"), 700),
        "requestedAt": requested,
        "createdAt": _text(row.get("created_at")),
        "officeName": _text(row.get("office_name")),
        "status": status,
        "statusLabel": {"pending": "In attesa", "approved": "Approvata", "rejected": "Rifiutata"}.get(status, status),
        "statusTone": _tone_for_status(status),
        "agendaEventId": _text(row.get("agenda_event_id")),
        "actions": {
            "canUpdateStatus": status == "pending",
            "statusEndpoint": f"/api/v1/ui/sito-studio/prenotazioni/{booking_id}/stato" if booking_id and status == "pending" else "",
        },
    }


def _safe_clients(get_clienti: Loader | None, current_user: Any) -> list[dict[str, str]]:
    if get_clienti is None or not _can(current_user, "clienti.leggi"):
        return []
    try:
        manager = get_clienti()
        rows = manager.tutti() if callable(getattr(manager, "tutti", None)) else []
        return [
            {
                "id": _text(getattr(row, "id", "")),
                "label": _text(getattr(row, "nome_completo", "")) or _text(getattr(row, "ragione_sociale", "")),
            }
            for row in list(rows)[:80]
            if _text(getattr(row, "id", ""))
        ]
    except Exception:
        return []


def _safe_matters(get_fascicoli: Loader | None, current_user: Any) -> list[dict[str, str]]:
    if get_fascicoli is None or not _can(current_user, "fascicoli.leggi"):
        return []
    try:
        manager = get_fascicoli()
        rows = manager.tutti() if callable(getattr(manager, "tutti", None)) else []
        return [
            {
                "id": _text(getattr(row, "id", "")),
                "label": _text(getattr(row, "oggetto", "")) or _text(getattr(row, "numero_ruolo", "")),
            }
            for row in list(rows)[:80]
            if _text(getattr(row, "id", ""))
        ]
    except Exception:
        return []


def _base_dashboard() -> dict[str, Any]:
    return build_studio_site_dashboard_payload()


def build_react_sito_studio_payload(
    *,
    contacts_only: bool = False,
    current_user: Any = None,
    get_clienti: Loader | None = None,
    get_fascicoli: Loader | None = None,
) -> dict[str, Any]:
    if contacts_only:
        return build_react_sito_contatti_payload(
            current_user=current_user,
            get_clienti=get_clienti,
            get_fascicoli=get_fascicoli,
        )

    dashboard = _base_dashboard()
    site = dashboard.get("site") or {}
    stats = dashboard.get("stats") or {}
    site_summary = _site_summary(site, _text(dashboard.get("public_url")))
    pages = (
        [_page(row, "page") for row in dashboard.get("pages", [])]
        + [_page(row, "article") for row in dashboard.get("articles", [])]
        + [_page(row, "service") for row in dashboard.get("services", [])]
        + [_page(row, "professional") for row in dashboard.get("professionals", [])]
        + [_page(row, "office") for row in dashboard.get("offices", [])]
    )
    warnings = [
        {"code": "editor_sito_operativo", "message": "Editor sito, pagine, redazione assistita e pubblicazione sono disponibili nei percorsi dedicati."},
        {"code": "notifiche_non_introdotte", "message": "Questo cruscotto non invia email, SMS o WhatsApp e non crea automazioni."},
        *[
            {"code": "sito_studio", "message": _text(message)}
            for message in dashboard.get("warnings", [])
            if _text(message)
        ],
    ]
    return {
        "ok": True,
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": _contracts("/sito-studio", writes="none"),
        "site": site_summary,
        "pages": pages,
        "metrics": [
            _metric("pages", "Pagine", _int(stats.get("pages")), "Pagine pubbliche sicure", "primary"),
            _metric("articles", "Articoli", _int(stats.get("articles")), "Contenuti editoriali", "info"),
            _metric("contacts", "Contatti", _int(stats.get("contact_submissions")), "Richieste ricevute", "warning" if _int(stats.get("contact_submissions")) else "neutral"),
            _metric("bookings", "Prenotazioni in attesa", _int(stats.get("pending_booking_requests")), "Richieste appuntamento da presidiare", "warning" if _int(stats.get("pending_booking_requests")) else "success"),
            _metric("services", "Servizi", _int(stats.get("services")), "Servizi pubblicabili", "neutral"),
        ],
        "preview": {
            "href": site_summary["publicUrl"],
            "label": "Apri anteprima pubblica" if site_summary["publicUrl"] else "Anteprima non disponibile",
            "safe": bool(site_summary["publicUrl"]),
        },
        "actions": [
            _action("contatti", "Apri contatti sito", "/sito-studio/contatti", "primary"),
            _action("public", "Apri sito pubblico", site_summary["publicUrl"], "success") if site_summary["publicUrl"] else _action("public-disabled", "Sito pubblico non disponibile", "/sito-studio", "neutral"),
            _action("builder", "Apri editor sito", "/sito-studio/builder", "primary"),
            _action("redazione-ai", "Apri Redazione AI", "/sito-studio/redazione-ai", "primary"),
            _action("recupero", "Percorso di recupero", "/sito-studio?_legacy=1", "neutral", protected=True),
        ],
        "legacy_routes": [
            _action("recupero", "Percorso di recupero", "/sito-studio?_legacy=1", "neutral", protected=True),
        ],
        "warnings": warnings,
    }


def build_react_sito_contatti_payload(
    *,
    current_user: Any = None,
    get_clienti: Loader | None = None,
    get_fascicoli: Loader | None = None,
) -> dict[str, Any]:
    dashboard = _base_dashboard()
    site = dashboard.get("site") or {}
    site_summary = _site_summary(site, _text(dashboard.get("public_url")))
    public_slug = site_summary["publicSlug"]
    public_site_url = site_summary["publicUrl"] or (f"/web/{public_slug}/" if public_slug else "")
    contacts = [_contact(row) for row in dashboard.get("contact_submissions", [])]
    bookings = [_booking(row) for row in dashboard.get("booking_requests", [])]
    can_manage = _can(current_user, "admin.configura") if current_user is not None else True
    actions = {
        "canRead": True,
        "canUpdateStatus": False,
        "canArchive": False,
        "canAddNote": False,
        "canAssign": False,
        "canLinkClient": can_manage,
        "canLinkMatter": False,
        "canUpdateBookingStatus": can_manage,
        "unsupportedReason": "Sono abilitate le azioni sicure gia collegate: creazione cliente, collegamento cliente e approvazione o rifiuto prenotazioni.",
        "rollback": {
            "label": "Percorso di recupero",
            "href": "/sito-studio/contatti?_legacy=1",
            "method": "GET",
            "legacy_fallback": True,
        },
    }
    return {
        "ok": True,
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": _contracts("/sito-studio/contatti", writes="json_api"),
        "entrypoints": {
            "publicSite": public_site_url,
            "publicContact": f"/web/{public_slug}/contatti" if public_slug else public_site_url,
            "publicBooking": f"/web/{public_slug}/prenota" if public_slug else "",
            "dashboard": "/sito-studio",
        },
        "contacts": contacts,
        "bookings": bookings,
        "statuses": [
            {"value": "nuovo", "label": "Da gestire", "mutable": False},
            {"value": "cliente_collegato", "label": "Cliente collegato", "mutable": False},
            {"value": "pending", "label": "Prenotazione in attesa", "mutable": True},
            {"value": "approved", "label": "Prenotazione approvata", "mutable": True},
            {"value": "rejected", "label": "Prenotazione rifiutata", "mutable": True},
        ],
        "assignees": [],
        "clients": _safe_clients(get_clienti, current_user),
        "matters": _safe_matters(get_fascicoli, current_user),
        "actions": actions,
        "warnings": [
            {"code": "azioni_contatto_limitate", "message": "Questa scheda consente collegamento cliente e gestione prenotazioni. Note interne, assegnazione e archiviazione saranno abilitate in una fase successiva."},
            {"code": "notifiche_non_introdotte", "message": "Le azioni React non inviano email, SMS o WhatsApp e non creano automazioni."},
        ],
    }


def _find_contact(submission_id: int) -> tuple[int, Any, dict[str, Any] | None]:
    site = get_site_for_current_tenant()
    repo = studio_site_repository()
    site_id = int(site["id"])
    rows = repo.list_contact_submissions(site_id, limit=1000)
    row = next((item for item in rows if _int(item.get("id")) == int(submission_id)), None)
    return site_id, repo, row


def _mutation_error(message: str, field: str = "form") -> dict[str, Any]:
    return {"ok": False, "message": message, "errors": {field: message}, "item": None}


def update_react_sito_contatto_status(_id_contatto: str, _payload: dict[str, Any]) -> dict[str, Any]:
    return _mutation_error("Cambio stato contatto non disponibile nel percorso corrente.", "status")


def archive_react_sito_contatto(_id_contatto: str, _payload: dict[str, Any]) -> dict[str, Any]:
    return _mutation_error("Archiviazione contatto non disponibile nel percorso corrente.", "archive")


def add_react_sito_contatto_note(_id_contatto: str, _payload: dict[str, Any]) -> dict[str, Any]:
    return _mutation_error("Nota interna contatto non disponibile nel percorso corrente.", "note")


def assign_react_sito_contatto(_id_contatto: str, _payload: dict[str, Any]) -> dict[str, Any]:
    return _mutation_error("Assegnazione contatto non disponibile nel percorso corrente.", "assignee")


def link_react_sito_contatto(id_contatto: str, payload: dict[str, Any], *, get_clienti: Loader | None = None) -> dict[str, Any]:
    allowed = {"mode", "cliente_id"}
    unknown = sorted(set(payload) - allowed)
    if unknown:
        return _mutation_error(f"Campi non ammessi: {', '.join(unknown)}.", "form")
    contact_id = _int(id_contatto)
    if contact_id <= 0:
        return _mutation_error("Identificativo contatto non valido.", "id_contatto")
    site_id, repo, submission = _find_contact(contact_id)
    if submission is None:
        return _mutation_error("Richiesta contatto non trovata.", "id_contatto")
    existing = _text(submission.get("lead_cliente_id"))
    if existing:
        return {"ok": True, "message": "Cliente gia' collegato alla richiesta.", "errors": {}, "item": _contact(submission)}
    cliente_id = _text(payload.get("cliente_id"))
    if cliente_id:
        if get_clienti is not None:
            manager = get_clienti()
            if callable(getattr(manager, "get", None)) and manager.get(cliente_id) is None:
                return _mutation_error("Cliente indicato non trovato.", "cliente_id")
        repo.update_contact_submission_lead(site_id, contact_id, cliente_id)
        audit_studio_site_action(
            "sito_studio.collega_cliente",
            resource_id=str(contact_id),
            details=f"Cliente {cliente_id} collegato alla richiesta contatto {contact_id}.",
        )
        rows = repo.list_contact_submissions(site_id, limit=1000)
        updated = next((item for item in rows if _int(item.get("id")) == contact_id), submission)
        return {"ok": True, "message": "Cliente collegato alla richiesta.", "errors": {}, "item": _contact(updated)}
    mode = _text(payload.get("mode") or "create_lead")
    if mode != "create_lead":
        return _mutation_error("Azione di collegamento non supportata.", "mode")
    try:
        lead_id = create_lead_cliente_from_submission(submission)
    except ValueError:
        return _mutation_error("Cliente potenziale non creato.", "cliente")
    repo.update_contact_submission_lead(site_id, contact_id, lead_id)
    audit_studio_site_action(
        "sito_studio.crea_lead_cliente",
        resource_id=str(contact_id),
        details=f"Cliente potenziale {lead_id} creato dalla richiesta contatto {contact_id}.",
    )
    rows = repo.list_contact_submissions(site_id, limit=1000)
    updated = next((item for item in rows if _int(item.get("id")) == contact_id), submission)
    return {"ok": True, "message": "Cliente potenziale creato e collegato.", "errors": {}, "item": _contact(updated)}


def update_react_sito_booking_status(id_prenotazione: str, payload: dict[str, Any]) -> dict[str, Any]:
    allowed = {"status"}
    unknown = sorted(set(payload) - allowed)
    if unknown:
        return _mutation_error(f"Campi non ammessi: {', '.join(unknown)}.", "form")
    booking_id = _int(id_prenotazione)
    status = _text(payload.get("status")).lower()
    if booking_id <= 0:
        return _mutation_error("Identificativo prenotazione non valido.", "id_prenotazione")
    if status not in {"approved", "rejected"}:
        return _mutation_error("Stato prenotazione non ammesso.", "status")
    try:
        updated = approve_booking_request_for_current_site(booking_id) if status == "approved" else reject_booking_request_for_current_site(booking_id)
    except ValueError:
        return _mutation_error("Prenotazione non aggiornabile.", "status")
    return {
        "ok": True,
        "message": "Prenotazione aggiornata.",
        "errors": {},
        "item": _booking(updated or {}),
    }


def build_react_sito_articolo_modifica_payload(article_id: int) -> dict[str, Any]:
    site = get_site_for_current_tenant()
    repo = studio_site_repository()
    site_id = int(site["id"])
    article = repo.get_article(site_id, int(article_id))
    route = _article_route(":id")
    if article is None:
        return {
            "ok": False,
            "notFound": True,
            "source": "repository_reali",
            "generated_at": _iso_now(),
            "contracts": _contracts(route, writes="json_api"),
            "site": _site_summary(site, ""),
            "article": None,
            "statuses": [],
            "actions": {
                "dashboard": "/sito-studio",
                "redazioneAi": "/sito-studio/redazione-ai",
                "saveEndpoint": "",
                "publicPreview": "",
                "rollback": {
                    "label": "Percorso di recupero",
                    "href": f"{_article_route(article_id)}?_legacy=1",
                    "method": "GET",
                    "legacy_fallback": True,
                },
            },
            "warnings": [{"code": "articolo", "message": "Articolo non trovato nel sito dello studio corrente."}],
        }
    public_href = _article_public_href(site, article)
    return {
        "ok": True,
        "notFound": False,
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": _contracts(route, writes="json_api"),
        "site": _site_summary(site, ""),
        "article": _article_item(site, article),
        "statuses": [
            {"value": "draft", "label": "Bozza", "tone": "warning"},
            {"value": "published", "label": "Pubblicato", "tone": "success"},
            {"value": "archived", "label": "Archiviato", "tone": "neutral"},
        ],
        "actions": {
            "dashboard": "/sito-studio",
            "redazioneAi": "/sito-studio/redazione-ai",
            "saveEndpoint": f"/api/v1/ui/sito-studio/articoli/{int(article_id)}/modifica",
            "publicPreview": public_href,
            "rollback": {
                "label": "Percorso di recupero",
                "href": f"{_article_route(article_id)}?_legacy=1",
                "method": "GET",
                "legacy_fallback": True,
            },
        },
        "warnings": [],
    }


def update_react_sito_articolo(article_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    site = get_site_for_current_tenant()
    repo = studio_site_repository()
    site_id = int(site["id"])
    current = repo.get_article(site_id, int(article_id))
    if current is None:
        return {
            "ok": False,
            "message": "Articolo non trovato nel sito dello studio corrente.",
            "errors": {"article": "Articolo non trovato."},
            "payload": build_react_sito_articolo_modifica_payload(article_id),
        }
    try:
        clean_payload = _article_form_payload(payload, current)
    except ValueError as exc:
        return {
            "ok": False,
            "message": str(exc),
            "errors": {"form": str(exc)},
            "payload": build_react_sito_articolo_modifica_payload(article_id),
        }

    updated = repo.save_article(site_id, clean_payload, article_id=int(article_id))
    audit_studio_site_action(
        "sito_studio.aggiorna_articolo",
        resource_id=str(article_id),
        details=f"Articolo {article_id} aggiornato dal percorso React Sito Studio.",
    )
    return {
        "ok": True,
        "message": "Articolo aggiornato.",
        "errors": {},
        "item": _article_item(site, updated),
        "payload": build_react_sito_articolo_modifica_payload(article_id),
    }


def build_react_sito_studio_error_payload(message: str = "Sito Studio non disponibile.") -> dict[str, Any]:
    return {
        "ok": False,
        "source": "errore_controllato",
        "generated_at": _iso_now(),
        "contracts": _contracts("/sito-studio", writes="none"),
        "site": {},
        "pages": [],
        "metrics": [],
        "preview": {},
        "actions": [],
        "legacy_routes": [],
        "warnings": [{"code": "sito_studio_errore", "message": message}],
    }
