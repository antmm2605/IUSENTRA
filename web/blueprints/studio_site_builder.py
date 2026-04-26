"""Blueprint Builder Pro per Sito Studio."""

from __future__ import annotations

from functools import wraps

from flask import Blueprint, jsonify, redirect, render_template, request, url_for, flash

from pct.studio_site_blocks import normalize_blocks
from web.services.studio_site_builder_runtime import (
    apply_theme_template,
    build_builder_payload,
    generate_automatic_site,
    save_design_settings,
    save_page_blocks,
    validate_site_builder,
)
from web.services.studio_site_runtime import site_admin_identity_or_403


studio_site_builder = Blueprint("studio_site_builder", __name__, url_prefix="/sito-studio")


def site_admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        site_admin_identity_or_403()
        return fn(*args, **kwargs)

    return wrapper


@studio_site_builder.get("/builder")
@site_admin_required
def builder():
    return render_template("studio_site/builder.html", payload=build_builder_payload())


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
    updated = save_page_blocks(page_id, blocks)
    return jsonify({"ok": True, "page": updated, "blocks": updated.get("body_json") or []})
