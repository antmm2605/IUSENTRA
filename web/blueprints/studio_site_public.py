from __future__ import annotations

from pathlib import Path

from flask import Blueprint, abort, flash, g, jsonify, redirect, render_template, request, send_from_directory, url_for

from web.services.studio_site_runtime import (
    build_public_site_payload,
    site_assets_dir,
    studio_site_repository,
    validate_public_booking_payload,
    validate_public_contact_payload,
)


studio_site_public = Blueprint("studio_site_public", __name__, url_prefix="/web")


def _preview_allowed(site: dict) -> bool:
    if site.get("is_published"):
        return True
    user = getattr(g, "utente_corrente", None)
    if user is None:
        return False
    if getattr(user, "is_superadmin", False):
        return True
    return bool(getattr(user, "ha_permesso", lambda _perm: False)("admin.configura"))


def _public_payload_or_404(public_slug: str) -> dict:
    site = studio_site_repository().get_site_by_public_slug(public_slug)
    if site is None or not site.get("is_active"):
        abort(404, description="Sito studio non trovato.")
    preview_allowed = _preview_allowed(site)
    payload = build_public_site_payload(public_slug, include_drafts=preview_allowed)
    if not preview_allowed:
        abort(404, description="Sito studio non pubblicato.")
    return payload


@studio_site_public.get("/<public_slug>/")
def home(public_slug: str):
    payload = _public_payload_or_404(public_slug)
    if payload.get("home_page") is None:
        abort(404, description="Home page del sito non configurata.")
    return render_template("studio_site/public_home.html", payload=payload, page=payload["home_page"])


@studio_site_public.get("/<public_slug>/pagina/<page_slug>")
def page_detail(public_slug: str, page_slug: str):
    payload = _public_payload_or_404(public_slug)
    page = studio_site_repository().get_page_by_slug(int(payload["site"]["id"]), page_slug, published_only=not _preview_allowed(payload["site"]))
    if page is None:
        abort(404, description="Pagina non trovata.")
    return render_template("studio_site/public_page.html", payload=payload, page=page)


@studio_site_public.get("/<public_slug>/articoli")
def articles(public_slug: str):
    payload = _public_payload_or_404(public_slug)
    return render_template("studio_site/public_articles.html", payload=payload)


@studio_site_public.get("/<public_slug>/articoli/<article_slug>")
def article_detail(public_slug: str, article_slug: str):
    payload = _public_payload_or_404(public_slug)
    article = studio_site_repository().get_article_by_slug(
        int(payload["site"]["id"]),
        article_slug,
        published_only=not _preview_allowed(payload["site"]),
    )
    if article is None:
        abort(404, description="Articolo non trovato.")
    return render_template("studio_site/public_article_detail.html", payload=payload, article=article)


@studio_site_public.get("/<public_slug>/contatti")
def contacts(public_slug: str):
    payload = _public_payload_or_404(public_slug)
    return render_template("studio_site/public_contact.html", payload=payload)


@studio_site_public.post("/<public_slug>/contatti")
def submit_contact(public_slug: str):
    payload = _public_payload_or_404(public_slug)
    try:
        data = validate_public_contact_payload(request.form.to_dict())
        studio_site_repository().create_contact_submission(int(payload["site"]["id"]), data)
        flash("Richiesta inviata correttamente allo studio.", "success")
    except Exception as exc:
        flash(f"Invio richiesta non riuscito: {exc}", "danger")
    return redirect(url_for("studio_site_public.contacts", public_slug=public_slug))


@studio_site_public.get("/<public_slug>/prenota")
def booking(public_slug: str):
    payload = _public_payload_or_404(public_slug)
    if not payload.get("booking_enabled"):
        flash("Agenda appuntamenti non ancora attiva sul sito studio.", "warning")
        return redirect(url_for("studio_site_public.home", public_slug=public_slug))
    return render_template("studio_site/public_booking.html", payload=payload)


@studio_site_public.post("/<public_slug>/prenota")
def submit_booking(public_slug: str):
    payload = _public_payload_or_404(public_slug)
    if not payload.get("booking_enabled"):
        flash("Agenda appuntamenti non ancora attiva sul sito studio.", "warning")
        return redirect(url_for("studio_site_public.home", public_slug=public_slug))
    try:
        data = validate_public_booking_payload(payload["site"], request.form.to_dict())
        studio_site_repository().create_booking_request(int(payload["site"]["id"]), data)
        flash("Richiesta appuntamento registrata. Lo studio la confermera dopo il controllo interno.", "success")
    except Exception as exc:
        flash(f"Richiesta appuntamento non riuscita: {exc}", "danger")
    return redirect(url_for("studio_site_public.booking", public_slug=public_slug))


@studio_site_public.get("/<public_slug>/api/slot-disponibili")
def public_slots_api(public_slug: str):
    payload = _public_payload_or_404(public_slug)
    if not payload.get("booking_enabled"):
        return jsonify({"ok": True, "slots": []})
    office_id = request.args.get("office_id", type=int)
    requested_date = str(request.args.get("data") or "").strip()
    slots = studio_site_repository().available_slots(int(payload["site"]["id"]), requested_date, office_id=office_id)
    return jsonify({"ok": True, "slots": slots})


@studio_site_public.get("/<public_slug>/strumenti-legali")
def legal_tools(public_slug: str):
    payload = _public_payload_or_404(public_slug)
    if not payload["site"].get("show_legal_tools"):
        abort(404)
    return render_template("studio_site/public_legal_tools.html", payload=payload)


@studio_site_public.get("/<public_slug>/applicazioni")
def applications(public_slug: str):
    payload = _public_payload_or_404(public_slug)
    if not payload["site"].get("show_applications"):
        abort(404)
    return render_template("studio_site/public_applications.html", payload=payload)


@studio_site_public.get("/<public_slug>/news-giuridiche")
def legal_news(public_slug: str):
    payload = _public_payload_or_404(public_slug)
    if not payload["site"].get("show_legal_news"):
        abort(404)
    return render_template("studio_site/public_legal_news.html", payload=payload)


@studio_site_public.get("/<public_slug>/assets/<path:filename>")
def asset(public_slug: str, filename: str):
    directory = site_assets_dir(public_slug)
    target = (directory / filename).resolve()
    if directory not in target.parents and directory != target.parent:
        abort(404)
    if not target.is_file():
        abort(404)
    return send_from_directory(str(directory), Path(filename).name)
