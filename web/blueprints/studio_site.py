from __future__ import annotations

from functools import wraps

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from pct.studio_site import BLOCK_TYPES, WEEKDAY_LABELS, normalize_hex_color
from pct.studio_site_blocks import block_presets
from web.services.studio_site_runtime import (
    ALLOWED_SITE_IMAGE_EXTENSIONS,
    approve_booking_request_for_current_site,
    audit_studio_site_action,
    build_studio_site_dashboard_payload,
    create_lead_cliente_from_submission,
    get_site_for_current_tenant,
    reject_booking_request_for_current_site,
    save_site_asset,
    site_admin_identity_or_403,
    studio_site_repository,
)
from web.blueprints.react_shell import render_react_shell_response


studio_site = Blueprint("studio_site", __name__, url_prefix="/sito-studio")


def site_admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        site_admin_identity_or_403()
        return fn(*args, **kwargs)

    return wrapper


def _site_id() -> int:
    return int(get_site_for_current_tenant()["id"])


def _richiede_vista_classica() -> bool:
    return request.args.get("_legacy") == "1"


def _redirect_dashboard(anchor: str = ""):
    if anchor:
        return redirect(url_for("studio_site.dashboard", _anchor=anchor))
    return redirect(url_for("studio_site.dashboard"))


def _bool_from_form(name: str, default: bool = False) -> bool:
    raw = request.form.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "on", "yes", "si"}


def _service_payload_from_form() -> dict[str, object]:
    return {
        "title": request.form.get("title", ""),
        "slug": request.form.get("slug", ""),
        "icon": request.form.get("icon", ""),
        "sort_order": request.form.get("sort_order", "0"),
        "short_description": request.form.get("short_description", ""),
        "long_description": request.form.get("long_description", ""),
        "is_visible": _bool_from_form("is_visible"),
    }


def _professional_payload_from_form() -> dict[str, object]:
    return {
        "full_name": request.form.get("full_name", ""),
        "role_title": request.form.get("role_title", ""),
        "email": request.form.get("email", ""),
        "phone": request.form.get("phone", ""),
        "sort_order": request.form.get("sort_order", "0"),
        "photo_url": request.form.get("photo_url", ""),
        "bio": request.form.get("bio", ""),
        "is_visible": _bool_from_form("is_visible"),
    }


def _office_payload_from_form() -> dict[str, object]:
    return {
        "name": request.form.get("name", ""),
        "email": request.form.get("email", ""),
        "address": request.form.get("address", ""),
        "zip_code": request.form.get("zip_code", ""),
        "city": request.form.get("city", ""),
        "province": request.form.get("province", ""),
        "phone": request.form.get("phone", ""),
        "map_url": request.form.get("map_url", ""),
        "opening_hours": request.form.get("opening_hours", ""),
        "is_primary": _bool_from_form("is_primary"),
        "is_visible": _bool_from_form("is_visible"),
    }


def _booking_rule_payload_from_form() -> dict[str, object]:
    return {
        "office_id": request.form.get("office_id", ""),
        "weekday": request.form.get("weekday", ""),
        "start_time": request.form.get("start_time", ""),
        "end_time": request.form.get("end_time", ""),
        "slot_minutes": request.form.get("slot_minutes", "30"),
        "max_requests_per_slot": request.form.get("max_requests_per_slot", "1"),
        "is_active": _bool_from_form("is_active"),
    }


@studio_site.get("/")
@site_admin_required
def dashboard():
    if not _richiede_vista_classica():
        return render_react_shell_response("sito-studio")
    payload = build_studio_site_dashboard_payload()
    return render_template("studio_site/dashboard.html", payload=payload, weekday_labels=WEEKDAY_LABELS)


@studio_site.get("/api/slot-disponibili")
@site_admin_required
def slots_api():
    site = get_site_for_current_tenant()
    office_id = request.args.get("office_id", type=int)
    requested_date = str(request.args.get("data") or "").strip()
    slots = studio_site_repository().available_slots(int(site["id"]), requested_date, office_id=office_id)
    return jsonify({"ok": True, "slots": slots})


@studio_site.get("/impostazioni")
@site_admin_required
def settings_form():
    return render_template("studio_site/settings_form.html", site=get_site_for_current_tenant())


@studio_site.post("/impostazioni")
@site_admin_required
def save_settings():
    site = get_site_for_current_tenant()
    repo = studio_site_repository()
    payload = {
        "studio_nome": request.form.get("studio_nome", ""),
        "site_name": request.form.get("site_name", ""),
        "public_slug": request.form.get("public_slug", ""),
        "site_title": request.form.get("site_title", ""),
        "site_description": request.form.get("site_description", ""),
        "hero_claim": request.form.get("hero_claim", ""),
        "contact_email": request.form.get("contact_email", ""),
        "contact_phone": request.form.get("contact_phone", ""),
        "whatsapp_number": request.form.get("whatsapp_number", ""),
        "address": request.form.get("address", ""),
        "city": request.form.get("city", ""),
        "province": request.form.get("province", ""),
        "zip_code": request.form.get("zip_code", ""),
        "footer_text": request.form.get("footer_text", ""),
        "facebook_url": request.form.get("facebook_url", ""),
        "instagram_url": request.form.get("instagram_url", ""),
        "linkedin_url": request.form.get("linkedin_url", ""),
        "primary_color": normalize_hex_color(request.form.get("primary_color"), str(site.get("primary_color") or "#1d4ed8")),
        "secondary_color": normalize_hex_color(request.form.get("secondary_color"), str(site.get("secondary_color") or "#0f172a")),
        "accent_color": normalize_hex_color(request.form.get("accent_color"), str(site.get("accent_color") or "#16a34a")),
        "is_published": _bool_from_form("is_published"),
        "is_active": _bool_from_form("is_active"),
        "show_legal_tools": _bool_from_form("show_legal_tools"),
        "show_applications": _bool_from_form("show_applications"),
        "show_legal_news": _bool_from_form("show_legal_news"),
        "cookie_banner_enabled": _bool_from_form("cookie_banner_enabled"),
        "analytics_enabled": _bool_from_form("analytics_enabled"),
        "analytics_provider": request.form.get("analytics_provider", ""),
        "analytics_id": request.form.get("analytics_id", ""),
        "privacy_url": request.form.get("privacy_url", ""),
        "cookie_policy_url": request.form.get("cookie_policy_url", ""),
        "accessibility_statement_url": request.form.get("accessibility_statement_url", ""),
        "legal_disclaimer": request.form.get("legal_disclaimer", ""),
    }
    updated = repo.save_site(int(site["id"]), payload)
    audit_studio_site_action(
        "sito_studio.aggiorna_impostazioni",
        resource_id=str(site["id"]),
        details=f"{site_admin_identity_or_403().username} ha aggiornato le impostazioni del sito studio.",
    )
    flash("Impostazioni sito studio aggiornate.", "success")
    return render_template("studio_site/settings_form.html", site=updated)


@studio_site.post("/assets")
@site_admin_required
def upload_asset():
    site = get_site_for_current_tenant()
    field_name = str(request.form.get("field_name") or "").strip().lower()
    if field_name not in {"logo_url", "favicon_url"}:
        flash("Campo asset non valido.", "danger")
        return _redirect_dashboard("branding")
    file_storage = request.files.get("file")
    if file_storage is None:
        flash("Seleziona un file immagine.", "danger")
        return _redirect_dashboard("branding")
    try:
        asset_url = save_site_asset(site, file_storage, kind="logo" if field_name == "logo_url" else "favicon")
        studio_site_repository().save_site(int(site["id"]), {field_name: asset_url})
        audit_studio_site_action(
            "sito_studio.carica_asset",
            resource_id=str(site["id"]),
            details=f"Caricato asset {field_name}. Formati ammessi: {', '.join(sorted(ALLOWED_SITE_IMAGE_EXTENSIONS))}.",
        )
        flash("Asset caricato e associato al sito.", "success")
    except Exception as exc:
        flash(f"Caricamento asset non riuscito: {exc}", "danger")
    return _redirect_dashboard("branding")


def _render_content_form(
    *,
    mode: str,
    title: str,
    endpoint: str,
    item: dict | None = None,
    item_type: str = "page",
):
    return render_template(
        "studio_site/content_form.html",
        mode=mode,
        title=title,
        endpoint=endpoint,
        item=item or {},
        item_type=item_type,
        block_types=BLOCK_TYPES,
        block_presets=block_presets(),
    )


@studio_site.get("/pagine/nuova")
@site_admin_required
def new_page_form():
    return _render_content_form(mode="new", title="Nuova pagina", endpoint=url_for("studio_site.create_page"), item_type="page")


@studio_site.post("/pagine/nuova")
@site_admin_required
def create_page():
    site = get_site_for_current_tenant()
    studio_site_repository().save_page(
        int(site["id"]),
        {
            "title": request.form.get("title", ""),
            "slug": request.form.get("slug", ""),
            "excerpt": request.form.get("excerpt", ""),
            "body_json": request.form.get("body_json", "[]"),
            "status": request.form.get("status", "draft"),
            "show_in_menu": _bool_from_form("show_in_menu"),
            "sort_order": request.form.get("sort_order", "0"),
            "is_home": _bool_from_form("is_home"),
            "seo_title": request.form.get("seo_title", ""),
            "seo_description": request.form.get("seo_description", ""),
        },
    )
    flash("Pagina salvata.", "success")
    return _redirect_dashboard("contenuti")


@studio_site.get("/pagine/<int:page_id>/modifica")
@site_admin_required
def edit_page_form(page_id: int):
    item = studio_site_repository().get_page(_site_id(), page_id)
    if item is None:
        flash("Pagina non trovata.", "warning")
        return _redirect_dashboard("contenuti")
    return _render_content_form(
        mode="edit",
        title="Modifica pagina",
        endpoint=url_for("studio_site.update_page", page_id=page_id),
        item=item,
        item_type="page",
    )


@studio_site.post("/pagine/<int:page_id>/modifica")
@site_admin_required
def update_page(page_id: int):
    studio_site_repository().save_page(
        _site_id(),
        {
            "title": request.form.get("title", ""),
            "slug": request.form.get("slug", ""),
            "excerpt": request.form.get("excerpt", ""),
            "body_json": request.form.get("body_json", "[]"),
            "status": request.form.get("status", "draft"),
            "show_in_menu": _bool_from_form("show_in_menu"),
            "sort_order": request.form.get("sort_order", "0"),
            "is_home": _bool_from_form("is_home"),
            "seo_title": request.form.get("seo_title", ""),
            "seo_description": request.form.get("seo_description", ""),
        },
        page_id=page_id,
    )
    flash("Pagina aggiornata.", "success")
    return _redirect_dashboard("contenuti")


@studio_site.post("/pagine/<int:page_id>/elimina")
@site_admin_required
def delete_page(page_id: int):
    page = studio_site_repository().get_page(_site_id(), page_id)
    if page and page.get("is_home"):
        flash("La home del sito non puo' essere eliminata.", "danger")
        return _redirect_dashboard("contenuti")
    studio_site_repository().delete_page(_site_id(), page_id)
    flash("Pagina eliminata.", "success")
    return _redirect_dashboard("contenuti")


@studio_site.get("/articoli/nuovo")
@site_admin_required
def new_article_form():
    return _render_content_form(mode="new", title="Nuovo articolo", endpoint=url_for("studio_site.create_article"), item_type="article")


@studio_site.post("/articoli/nuovo")
@site_admin_required
def create_article():
    studio_site_repository().save_article(
        _site_id(),
        {
            "title": request.form.get("title", ""),
            "slug": request.form.get("slug", ""),
            "excerpt": request.form.get("excerpt", ""),
            "cover_url": request.form.get("cover_url", ""),
            "category": request.form.get("category", ""),
            "tags_csv": request.form.get("tags_csv", ""),
            "author_name": request.form.get("author_name", ""),
            "body_json": request.form.get("body_json", "[]"),
            "status": request.form.get("status", "draft"),
            "published_at": request.form.get("published_at", ""),
            "seo_title": request.form.get("seo_title", ""),
            "seo_description": request.form.get("seo_description", ""),
        },
    )
    flash("Articolo salvato.", "success")
    return _redirect_dashboard("articoli")


@studio_site.get("/articoli/<int:article_id>/modifica")
@site_admin_required
def edit_article_form(article_id: int):
    item = studio_site_repository().get_article(_site_id(), article_id)
    if item is None:
        flash("Articolo non trovato.", "warning")
        return _redirect_dashboard("articoli")
    return _render_content_form(
        mode="edit",
        title="Modifica articolo",
        endpoint=url_for("studio_site.update_article", article_id=article_id),
        item=item,
        item_type="article",
    )


@studio_site.post("/articoli/<int:article_id>/modifica")
@site_admin_required
def update_article(article_id: int):
    studio_site_repository().save_article(
        _site_id(),
        {
            "title": request.form.get("title", ""),
            "slug": request.form.get("slug", ""),
            "excerpt": request.form.get("excerpt", ""),
            "cover_url": request.form.get("cover_url", ""),
            "category": request.form.get("category", ""),
            "tags_csv": request.form.get("tags_csv", ""),
            "author_name": request.form.get("author_name", ""),
            "body_json": request.form.get("body_json", "[]"),
            "status": request.form.get("status", "draft"),
            "published_at": request.form.get("published_at", ""),
            "seo_title": request.form.get("seo_title", ""),
            "seo_description": request.form.get("seo_description", ""),
        },
        article_id=article_id,
    )
    flash("Articolo aggiornato.", "success")
    return _redirect_dashboard("articoli")


@studio_site.post("/articoli/<int:article_id>/elimina")
@site_admin_required
def delete_article(article_id: int):
    studio_site_repository().delete_article(_site_id(), article_id)
    flash("Articolo eliminato.", "success")
    return _redirect_dashboard("articoli")


def _render_collection_form(*, title: str, endpoint: str, item: dict | None, item_type: str):
    return render_template(
        "studio_site/collection_form.html",
        title=title,
        endpoint=endpoint,
        item=item or {},
        item_type=item_type,
        weekday_labels=WEEKDAY_LABELS,
        offices=studio_site_repository().list_offices(_site_id()),
    )


@studio_site.get("/servizi/nuovo")
@site_admin_required
def new_service_form():
    return _render_collection_form(title="Nuovo servizio", endpoint=url_for("studio_site.create_service"), item=None, item_type="service")


@studio_site.post("/servizi/nuovo")
@site_admin_required
def create_service():
    studio_site_repository().save_service(_site_id(), _service_payload_from_form())
    flash("Servizio salvato.", "success")
    return _redirect_dashboard("servizi")


@studio_site.get("/servizi/<int:service_id>/modifica")
@site_admin_required
def edit_service_form(service_id: int):
    item = studio_site_repository().get_service(_site_id(), service_id)
    if item is None:
        flash("Servizio non trovato.", "warning")
        return _redirect_dashboard("servizi")
    return _render_collection_form(title="Modifica servizio", endpoint=url_for("studio_site.update_service", service_id=service_id), item=item, item_type="service")


@studio_site.post("/servizi/<int:service_id>/modifica")
@site_admin_required
def update_service(service_id: int):
    studio_site_repository().save_service(_site_id(), _service_payload_from_form(), service_id=service_id)
    flash("Servizio aggiornato.", "success")
    return _redirect_dashboard("servizi")


@studio_site.post("/servizi/<int:service_id>/elimina")
@site_admin_required
def delete_service(service_id: int):
    studio_site_repository().delete_service(_site_id(), service_id)
    flash("Servizio eliminato.", "success")
    return _redirect_dashboard("servizi")


@studio_site.get("/professionisti/nuovo")
@site_admin_required
def new_professional_form():
    return _render_collection_form(title="Nuovo professionista", endpoint=url_for("studio_site.create_professional"), item=None, item_type="professional")


@studio_site.post("/professionisti/nuovo")
@site_admin_required
def create_professional():
    studio_site_repository().save_professional(_site_id(), _professional_payload_from_form())
    flash("Professionista salvato.", "success")
    return _redirect_dashboard("team")


@studio_site.get("/professionisti/<int:professional_id>/modifica")
@site_admin_required
def edit_professional_form(professional_id: int):
    item = studio_site_repository().get_professional(_site_id(), professional_id)
    if item is None:
        flash("Professionista non trovato.", "warning")
        return _redirect_dashboard("team")
    return _render_collection_form(title="Modifica professionista", endpoint=url_for("studio_site.update_professional", professional_id=professional_id), item=item, item_type="professional")


@studio_site.post("/professionisti/<int:professional_id>/modifica")
@site_admin_required
def update_professional(professional_id: int):
    studio_site_repository().save_professional(_site_id(), _professional_payload_from_form(), professional_id=professional_id)
    flash("Professionista aggiornato.", "success")
    return _redirect_dashboard("team")


@studio_site.post("/professionisti/<int:professional_id>/elimina")
@site_admin_required
def delete_professional(professional_id: int):
    studio_site_repository().delete_professional(_site_id(), professional_id)
    flash("Professionista eliminato.", "success")
    return _redirect_dashboard("team")


@studio_site.get("/sedi/nuova")
@site_admin_required
def new_office_form():
    return _render_collection_form(title="Nuova sede", endpoint=url_for("studio_site.create_office"), item=None, item_type="office")


@studio_site.post("/sedi/nuova")
@site_admin_required
def create_office():
    studio_site_repository().save_office(_site_id(), _office_payload_from_form())
    flash("Sede salvata.", "success")
    return _redirect_dashboard("sedi")


@studio_site.get("/sedi/<int:office_id>/modifica")
@site_admin_required
def edit_office_form(office_id: int):
    item = studio_site_repository().get_office(_site_id(), office_id)
    if item is None:
        flash("Sede non trovata.", "warning")
        return _redirect_dashboard("sedi")
    return _render_collection_form(title="Modifica sede", endpoint=url_for("studio_site.update_office", office_id=office_id), item=item, item_type="office")


@studio_site.post("/sedi/<int:office_id>/modifica")
@site_admin_required
def update_office(office_id: int):
    studio_site_repository().save_office(_site_id(), _office_payload_from_form(), office_id=office_id)
    flash("Sede aggiornata.", "success")
    return _redirect_dashboard("sedi")


@studio_site.post("/sedi/<int:office_id>/elimina")
@site_admin_required
def delete_office(office_id: int):
    studio_site_repository().delete_office(_site_id(), office_id)
    flash("Sede eliminata.", "success")
    return _redirect_dashboard("sedi")


@studio_site.get("/regole-agenda/nuova")
@site_admin_required
def new_booking_rule_form():
    return _render_collection_form(title="Nuova regola agenda", endpoint=url_for("studio_site.create_booking_rule"), item=None, item_type="booking_rule")


@studio_site.post("/regole-agenda/nuova")
@site_admin_required
def create_booking_rule():
    studio_site_repository().save_booking_rule(_site_id(), _booking_rule_payload_from_form())
    flash("Regola agenda salvata.", "success")
    return _redirect_dashboard("agenda")


@studio_site.get("/regole-agenda/<int:rule_id>/modifica")
@site_admin_required
def edit_booking_rule_form(rule_id: int):
    item = studio_site_repository().get_booking_rule(_site_id(), rule_id)
    if item is None:
        flash("Regola agenda non trovata.", "warning")
        return _redirect_dashboard("agenda")
    return _render_collection_form(title="Modifica regola agenda", endpoint=url_for("studio_site.update_booking_rule", rule_id=rule_id), item=item, item_type="booking_rule")


@studio_site.post("/regole-agenda/<int:rule_id>/modifica")
@site_admin_required
def update_booking_rule(rule_id: int):
    studio_site_repository().save_booking_rule(_site_id(), _booking_rule_payload_from_form(), rule_id=rule_id)
    flash("Regola agenda aggiornata.", "success")
    return _redirect_dashboard("agenda")


@studio_site.post("/regole-agenda/<int:rule_id>/elimina")
@site_admin_required
def delete_booking_rule(rule_id: int):
    studio_site_repository().delete_booking_rule(_site_id(), rule_id)
    flash("Regola agenda eliminata.", "success")
    return _redirect_dashboard("agenda")


@studio_site.get("/prenotazioni")
@site_admin_required
def booking_requests():
    payload = build_studio_site_dashboard_payload()
    return render_template("studio_site/booking_requests.html", payload=payload)


@studio_site.post("/prenotazioni/<int:booking_request_id>/approva")
@site_admin_required
def approve_booking_request(booking_request_id: int):
    try:
        approve_booking_request_for_current_site(booking_request_id)
        flash("Prenotazione approvata e sincronizzata in agenda.", "success")
    except Exception as exc:
        flash(f"Approvazione prenotazione non riuscita: {exc}", "danger")
    return redirect(url_for("studio_site.booking_requests"))


@studio_site.post("/prenotazioni/<int:booking_request_id>/rifiuta")
@site_admin_required
def reject_booking_request(booking_request_id: int):
    try:
        reject_booking_request_for_current_site(booking_request_id)
        flash("Prenotazione rifiutata.", "warning")
    except Exception as exc:
        flash(f"Rifiuto prenotazione non riuscito: {exc}", "danger")
    return redirect(url_for("studio_site.booking_requests"))


@studio_site.get("/contatti")
@site_admin_required
def contact_submissions():
    if not _richiede_vista_classica():
        return render_react_shell_response("sito-studio/contatti")

    payload = build_studio_site_dashboard_payload()
    return render_template("studio_site/contact_submissions.html", payload=payload)


@studio_site.post("/contatti/<int:submission_id>/crea-cliente")
@site_admin_required
def create_client_from_contact(submission_id: int):
    site = get_site_for_current_tenant()
    repo = studio_site_repository()
    site_id = int(site["id"])
    rows = repo.list_contact_submissions(site_id, limit=1000)
    submission = next((r for r in rows if int(r.get("id") or 0) == submission_id), None)
    if submission is None:
        flash("Richiesta contatto non trovata.", "warning")
        return redirect(url_for("studio_site.contact_submissions"))
    if submission.get("lead_cliente_id"):
        flash("Cliente potenziale già creato per questa richiesta.", "info")
        return redirect(url_for("cartella_cliente", id_cliente=submission["lead_cliente_id"]))
    try:
        cliente_id = create_lead_cliente_from_submission(submission)
        repo.update_contact_submission_lead(site_id, submission_id, cliente_id)
        audit_studio_site_action(
            "sito_studio.crea_lead_cliente",
            resource_id=str(submission_id),
            details=f"Cliente potenziale {cliente_id} creato dalla richiesta contatto {submission_id}.",
        )
        flash("Cliente potenziale creato con successo.", "success")
        return redirect(url_for("cartella_cliente", id_cliente=cliente_id))
    except Exception as exc:
        flash(f"Creazione cliente non riuscita: {exc}", "danger")
    return redirect(url_for("studio_site.contact_submissions"))
