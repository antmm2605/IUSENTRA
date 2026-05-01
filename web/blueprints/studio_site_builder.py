"""Blueprint Builder Pro per Sito Studio."""

from __future__ import annotations

from functools import wraps

from flask import Blueprint, jsonify, redirect, render_template, request, url_for, flash

from pct.studio_site_blocks import normalize_blocks
from web.services.studio_site_ai_runtime import (
    create_article_draft_from_job,
    generate_ai_article_job,
    generate_article_cover,
    publish_ai_article,
)
from web.services.studio_site_assets import delete_builder_asset, save_builder_asset
from web.services.studio_site_builder_runtime import (
    apply_theme_template,
    build_builder_payload,
    generate_automatic_site,
    publish_page_blocks,
    restore_design_revision,
    save_design_settings,
    save_page_blocks,
    validate_site_builder,
)
from web.services.studio_site_runtime import get_site_for_current_tenant, site_admin_identity_or_403, studio_site_repository
from web.blueprints.react_shell import render_react_shell_response


studio_site_builder = Blueprint("studio_site_builder", __name__, url_prefix="/sito-studio")


def site_admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        site_admin_identity_or_403()
        return fn(*args, **kwargs)

    return wrapper


def _richiede_vista_classica() -> bool:
    return request.args.get("_legacy") == "1"


@studio_site_builder.get("/builder")
@site_admin_required
def builder():
    if not _richiede_vista_classica():
        return render_react_shell_response("sito-studio/builder")

    return render_template(
        "studio_site/builder.html",
        payload=build_builder_payload(page_id=request.args.get("page_id", type=int)),
    )


@studio_site_builder.post("/builder/applica-template")
@site_admin_required
def apply_template():
    json_payload = request.get_json(silent=True) if request.is_json else {}
    template_code = str((json_payload or {}).get("template_code") or request.form.get("template_code") or "").strip()
    if not template_code:
        template_code = str(request.form.get("theme_template") or "").strip()
    updated = apply_theme_template(template_code)
    if request.is_json:
        return jsonify({"ok": True, "site": updated, "payload": build_builder_payload()})
    flash("Template grafico applicato al sito unico dello studio.", "success")
    return redirect(url_for("studio_site_builder.builder"))


@studio_site_builder.post("/builder/salva-design")
@site_admin_required
def save_design():
    payload = request.get_json(silent=True) if request.is_json else dict(request.form)
    updated = save_design_settings(payload or {})
    if request.is_json:
        return jsonify({"ok": True, "site": updated, "validation": validate_site_builder(site=updated)})
    flash("Design e impostazioni privacy salvati.", "success")
    return redirect(url_for("studio_site_builder.builder"))


@studio_site_builder.post("/builder/genera-automaticamente")
@site_admin_required
def generate_auto():
    payload = request.get_json(silent=True) if request.is_json else dict(request.form)
    result = generate_automatic_site(payload or {})
    if request.is_json:
        return jsonify({"ok": True, "payload": result})
    flash("Sito generato in bozza. Completa e verifica i contenuti prima della pubblicazione.", "success")
    return redirect(url_for("studio_site_builder.builder"))


@studio_site_builder.post("/builder/valida")
@site_admin_required
def validate_builder():
    if request.is_json or "application/json" in str(request.headers.get("Accept") or ""):
        return jsonify({"ok": True, "validation": validate_site_builder()})
    flash("Validazione SEO, accessibilita, privacy e deontologia completata.", "success")
    return redirect(url_for("studio_site_builder.builder"))


@studio_site_builder.get("/preview")
@site_admin_required
def preview():
    payload = build_builder_payload()
    public_url = payload.get("public_url") or "/"
    return render_template("studio_site/preview.html", payload=payload, public_url=public_url)


@studio_site_builder.get("/api/theme-presets")
@site_admin_required
def theme_presets_api():
    payload = build_builder_payload()
    return jsonify({"ok": True, "templates": payload["templates"], "active": payload["site"].get("theme_template")})


@studio_site_builder.get("/api/block-presets")
@site_admin_required
def block_presets_api():
    payload = build_builder_payload()
    return jsonify({"ok": True, "blocks": payload["block_presets"]})


@studio_site_builder.post("/api/pages/<int:page_id>/blocks")
@site_admin_required
def save_page_blocks_api(page_id: int):
    payload = request.get_json(silent=True) or {}
    blocks = normalize_blocks(payload.get("blocks") or request.form.get("body_json") or [])
    try:
        updated = save_page_blocks(page_id, blocks)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": True, "message": "Bozza pagina salvata.", "page": updated, "blocks": updated.get("body_json") or []})


@studio_site_builder.get("/api/pages/<int:page_id>/blocks")
@site_admin_required
def get_page_blocks_api(page_id: int):
    site = get_site_for_current_tenant()
    page = studio_site_repository().get_page(int(site["id"]), int(page_id))
    if page is None:
        return jsonify({"ok": False, "error": "Pagina non trovata."}), 404
    return jsonify({"ok": True, "page": page, "blocks": page.get("body_json") or []})


@studio_site_builder.post("/api/pages/<int:page_id>/publish")
@site_admin_required
def publish_page_blocks_api(page_id: int):
    payload = request.get_json(silent=True) or {}
    blocks = normalize_blocks(payload.get("blocks") or [])
    try:
        updated = publish_page_blocks(page_id, blocks)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": True, "message": "Modifiche pubblicate sul sito.", "page": updated})


@studio_site_builder.post("/api/revisions/<int:revision_id>/restore")
@site_admin_required
def restore_revision_api(revision_id: int):
    snapshot = restore_design_revision(revision_id)
    return jsonify({"ok": True, "message": "Revisione ripristinata.", "snapshot": snapshot, "payload": build_builder_payload()})


@studio_site_builder.get("/api/assets")
@site_admin_required
def list_assets_api():
    site = get_site_for_current_tenant()
    return jsonify({"ok": True, "assets": studio_site_repository().list_assets(int(site["id"]), limit=200)})


@studio_site_builder.post("/api/assets/upload")
@site_admin_required
def upload_asset_api():
    site = get_site_for_current_tenant()
    try:
        asset = save_builder_asset(site, request.files.get("file"), payload=request.form.to_dict())
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": True, "message": "Immagine caricata nella libreria.", "asset": asset})


@studio_site_builder.delete("/api/assets/<int:asset_id>")
@site_admin_required
def delete_asset_api(asset_id: int):
    site = get_site_for_current_tenant()
    try:
        delete_builder_asset(site, asset_id)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": True, "message": "Immagine eliminata dalla libreria."})


@studio_site_builder.get("/redazione-ai")
@site_admin_required
def ai_redazione():
    site = get_site_for_current_tenant()
    repo = studio_site_repository()
    return render_template(
        "studio_site/redazione_ai.html",
        site=site,
        jobs=repo.list_ai_article_jobs(int(site["id"]), limit=20),
        articles=repo.list_articles(int(site["id"]), limit=20),
    )


@studio_site_builder.post("/redazione-ai/articolo/genera")
@site_admin_required
def ai_generate_article():
    try:
        job = generate_ai_article_job(request.get_json(silent=True) if request.is_json else request.form.to_dict())
    except Exception as exc:
        if request.is_json:
            return jsonify({"ok": False, "error": str(exc)}), 400
        flash(f"Generazione articolo non riuscita: {exc}", "danger")
        return redirect(url_for("studio_site_builder.ai_redazione"))
    if request.is_json:
        return jsonify({"ok": True, "job": job})
    flash("Bozza articolo AI generata. Revisiona il contenuto prima di creare l'articolo.", "success")
    return redirect(url_for("studio_site_builder.ai_redazione"))


@studio_site_builder.post("/redazione-ai/articolo/<int:job_id>/crea-bozza")
@site_admin_required
def ai_create_draft(job_id: int):
    try:
        article = create_article_draft_from_job(job_id)
    except Exception as exc:
        if request.is_json:
            return jsonify({"ok": False, "error": str(exc)}), 400
        flash(f"Creazione bozza non riuscita: {exc}", "danger")
        return redirect(url_for("studio_site_builder.ai_redazione"))
    if request.is_json:
        return jsonify({"ok": True, "article": article})
    flash("Articolo creato in bozza. Pubblicazione ancora manuale.", "success")
    return redirect(url_for("studio_site.edit_article_form", article_id=article["id"]))


@studio_site_builder.post("/redazione-ai/articolo/<int:article_id>/genera-immagine")
@site_admin_required
def ai_generate_image(article_id: int):
    try:
        result = generate_article_cover(article_id)
    except Exception as exc:
        if request.is_json:
            return jsonify({"ok": False, "error": str(exc)}), 400
        flash(f"Generazione immagine non riuscita: {exc}", "danger")
        return redirect(url_for("studio_site_builder.ai_redazione"))
    if request.is_json:
        return jsonify({"ok": True, **result})
    flash("Immagine associata all'articolo come asset del sito.", "success")
    return redirect(url_for("studio_site.edit_article_form", article_id=article_id))


@studio_site_builder.post("/redazione-ai/articolo/<int:article_id>/pubblica")
@site_admin_required
def ai_publish_article(article_id: int):
    try:
        article = publish_ai_article(article_id)
    except Exception as exc:
        if request.is_json:
            return jsonify({"ok": False, "error": str(exc)}), 400
        flash(f"Pubblicazione non riuscita: {exc}", "danger")
        return redirect(url_for("studio_site_builder.ai_redazione"))
    if request.is_json:
        return jsonify({"ok": True, "article": article})
    flash("Articolo pubblicato dopo conferma manuale.", "success")
    return redirect(url_for("studio_site.edit_article_form", article_id=article_id))


@studio_site_builder.get("/redazione-ai/job/<int:job_id>")
@site_admin_required
def ai_job_detail(job_id: int):
    site = get_site_for_current_tenant()
    job = studio_site_repository().get_ai_article_job(int(site["id"]), int(job_id))
    if job is None:
        return jsonify({"ok": False, "error": "Lavoro AI non trovato."}), 404
    return jsonify({"ok": True, "job": job})
