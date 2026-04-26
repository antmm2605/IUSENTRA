"""Runtime del Website Studio Legale."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from flask import url_for

from pct.studio_site import clean_text, slugify, truthy
from pct.studio_site_blocks import block_presets, normalize_blocks
from pct.studio_site_theme import (
    DEFAULT_THEME_TEMPLATE,
    build_design_tokens,
    get_theme_template,
    list_theme_templates,
    sanitize_custom_css,
    theme_snapshot,
)
from web.services.studio_site_runtime import (
    audit_studio_site_action,
    get_site_for_current_tenant,
    site_admin_identity_or_403,
    studio_site_repository,
)


DEONTOLOGY_PATTERNS: tuple[tuple[str, str], ...] = (
    ("miglior avvocato", "Evita confronti assoluti o non verificabili."),
    ("vinciamo sempre", "Non promettere esiti giudiziali."),
    ("risultato garantito", "La comunicazione deve restare prudente e informativa."),
    ("gratis senza condizioni", "Chiarisci sempre limiti e condizioni economiche."),
    ("leader assoluto", "Evita claim comparativi non documentati."),
    ("casi vinti", "Non pubblicare casi con dati identificativi o toni promozionali."),
    ("nomi clienti", "Non pubblicare riferimenti a clienti senza base giuridica e consenso."),
)


def _current_operator_label() -> str:
    try:
        user = site_admin_identity_or_403()
        return clean_text(getattr(user, "nome_completo", "") or getattr(user, "username", "")) or "Operatore"
    except Exception:
        return "Operatore"


def _site_home_page(site_id: int) -> dict[str, Any] | None:
    repo = studio_site_repository()
    pages = repo.list_pages(site_id)
    return next((row for row in pages if row.get("is_home")), None) or next(
        (row for row in pages if str(row.get("slug") or "") == "home"),
        None,
    )


def build_builder_payload() -> dict[str, Any]:
    site = get_site_for_current_tenant()
    repo = studio_site_repository()
    site_id = int(site["id"])
    validation = validate_site_builder(site=site)
    return {
        "site": site,
        "theme": theme_snapshot(site),
        "templates": list_theme_templates(),
        "block_presets": block_presets(),
        "pages": repo.list_pages(site_id),
        "articles": repo.list_articles(site_id, limit=8),
        "services": repo.list_services(site_id),
        "professionals": repo.list_professionals(site_id),
        "offices": repo.list_offices(site_id),
        "revisions": repo.list_design_revisions(site_id),
        "validation": validation,
        "public_url": url_for("studio_site_public.home", public_slug=site["public_slug"]),
        "preview_url": url_for("studio_site_builder.preview"),
        "tenant_scope": "studio",
    }


def apply_theme_template(template_code: str) -> dict[str, Any]:
    site = get_site_for_current_tenant()
    repo = studio_site_repository()
    template = get_theme_template(template_code)
    site_id = int(site["id"])
    repo.save_design_revision(
        site_id,
        label=f"Prima del template {template['name']}",
        snapshot=repo.snapshot_site_design(site_id),
        created_by=_current_operator_label(),
    )
    updated = repo.save_site(
        site_id,
        {
            "theme_template": clean_text(template_code) or DEFAULT_THEME_TEMPLATE,
            "theme_variant": "default",
            "design_tokens_json": template.get("tokens") or {},
            "typography_json": {"font_preset": template.get("font_preset") or "system_professional"},
            "layout_json": template.get("layout") or {},
            "effects_json": template.get("effects") or {},
        },
    )
    audit_studio_site_action(
        "sito_studio.applica_template",
        resource_id=str(site_id),
        details=f"Applicato template {template.get('name')}. Il sito resta unico per tenant/studio.",
    )
    return updated or site


def save_design_settings(payload: dict[str, Any]) -> dict[str, Any]:
    site = get_site_for_current_tenant()
    repo = studio_site_repository()
    site_id = int(site["id"])
    template_code = clean_text(payload.get("theme_template") or site.get("theme_template") or DEFAULT_THEME_TEMPLATE)
    tokens = {
        key: clean_text(payload.get(key))
        for key in ("primary", "secondary", "accent", "bg", "surface", "text", "muted", "border")
        if clean_text(payload.get(key))
    }
    typography = {
        "font_preset": clean_text(payload.get("font_preset")) or "system_professional",
        "font_size_base": clean_text(payload.get("font_size_base")) or "16px",
        "line_height": clean_text(payload.get("line_height")) or "1.65",
    }
    computed_tokens = build_design_tokens(template_code, tokens, typography)
    repo.save_design_revision(
        site_id,
        label="Prima delle modifiche design",
        snapshot=repo.snapshot_site_design(site_id),
        created_by=_current_operator_label(),
    )
    updated = repo.save_site(
        site_id,
        {
            "theme_template": template_code,
            "theme_variant": clean_text(payload.get("theme_variant") or "custom"),
            "primary_color": computed_tokens.get("primary"),
            "secondary_color": computed_tokens.get("secondary"),
            "accent_color": computed_tokens.get("accent"),
            "design_tokens_json": computed_tokens,
            "typography_json": typography,
            "layout_json": {
                "container": clean_text(payload.get("container_width")) or computed_tokens.get("container_width"),
                "density": clean_text(payload.get("density") or "standard"),
            },
            "effects_json": {
                "animation": clean_text(payload.get("animation") or "fade-up"),
                "speed": clean_text(payload.get("animation_speed") or computed_tokens.get("animation_speed")),
            },
            "custom_css": sanitize_custom_css(payload.get("custom_css")),
            "cookie_banner_enabled": truthy(payload.get("cookie_banner_enabled")),
            "analytics_enabled": truthy(payload.get("analytics_enabled")),
            "analytics_provider": payload.get("analytics_provider"),
            "analytics_id": payload.get("analytics_id"),
            "privacy_url": payload.get("privacy_url"),
            "cookie_policy_url": payload.get("cookie_policy_url"),
            "accessibility_statement_url": payload.get("accessibility_statement_url"),
            "legal_disclaimer": payload.get("legal_disclaimer"),
        },
    )
    audit_studio_site_action("sito_studio.salva_design", resource_id=str(site_id), details="Design Builder Pro aggiornato.")
    return updated or site


def generate_automatic_site(payload: dict[str, Any]) -> dict[str, Any]:
    site = get_site_for_current_tenant()
    repo = studio_site_repository()
    site_id = int(site["id"])
    template_code = clean_text(payload.get("template") or site.get("theme_template") or DEFAULT_THEME_TEMPLATE)
    template = get_theme_template(template_code)
    site_type = clean_text(payload.get("site_type") or "generalista")
    style = clean_text(payload.get("style") or "sobrio")
    repo.save_design_revision(
        site_id,
        label="Prima della generazione automatica",
        snapshot=repo.snapshot_site_design(site_id),
        created_by=_current_operator_label(),
    )
    apply_theme_template(template_code)
    home_blocks = normalize_blocks(template.get("home_blocks") or [])
    for block in home_blocks:
        if block["type"].startswith("hero"):
            block["title"] = site.get("site_name") or site.get("studio_nome") or "Studio legale"
            block["subtitle"] = site.get("hero_claim") or site.get("site_description") or block.get("subtitle")
        if block["type"] == "practice_areas":
            block["subtitle"] = f"Profilo {site_type}; stile comunicativo {style}. Personalizza i testi prima della pubblicazione."
    home = _site_home_page(site_id)
    if home is not None:
        repo.save_page_blocks(site_id, int(home["id"]), home_blocks)
    else:
        repo.save_page(
            site_id,
            {
                "title": "Home",
                "slug": "home",
                "excerpt": "Pagina iniziale generata dal builder.",
                "body_json": home_blocks,
                "status": "draft",
                "show_in_menu": True,
                "sort_order": 0,
                "is_home": True,
                "seo_title": site.get("site_title") or site.get("site_name"),
                "seo_description": site.get("site_description"),
            },
        )
    _ensure_generated_page(site_id, "Chi siamo", "chi-siamo", "Presentazione dello studio.")
    _ensure_generated_page(site_id, "Aree di attivita", "aree-attivita", "Servizi e ambiti operativi da personalizzare.")
    _ensure_generated_page(site_id, "FAQ", "faq", "Domande frequenti da verificare prima della pubblicazione.", block_type="faq")
    _ensure_generated_page(site_id, "Contatti", "contatti-studio", "Recapiti, sedi e richiesta informazioni.", block_type="contact_form")
    audit_studio_site_action(
        "sito_studio.genera_automaticamente",
        resource_id=str(site_id),
        details=f"Generazione automatica {site_type}/{style}. Nessuna qualifica inventata.",
    )
    return build_builder_payload()


def _ensure_generated_page(site_id: int, title: str, slug: str, excerpt: str, *, block_type: str = "rich_text") -> None:
    repo = studio_site_repository()
    existing = repo.get_page_by_slug(site_id, slug)
    if existing is not None:
        return
    text = (
        "Questa sezione e' stata predisposta automaticamente con testo prudente. "
        "Completa i contenuti con dati reali dello studio prima della pubblicazione."
    )
    repo.save_page(
        site_id,
        {
            "title": title,
            "slug": slug,
            "excerpt": excerpt,
            "body_json": [{"type": block_type, "title": title, "text": text}],
            "status": "draft",
            "show_in_menu": True,
            "sort_order": 30,
            "is_home": False,
            "seo_title": title,
            "seo_description": excerpt,
        },
    )


def save_page_blocks(page_id: int, blocks: Any) -> dict[str, Any]:
    site = get_site_for_current_tenant()
    updated = studio_site_repository().save_page_blocks(int(site["id"]), int(page_id), normalize_blocks(blocks))
    if updated is None:
        raise ValueError("Pagina non trovata per lo studio corrente.")
    return updated


def validate_site_builder(*, site: dict[str, Any] | None = None) -> dict[str, Any]:
    site = site or get_site_for_current_tenant()
    repo = studio_site_repository()
    pages = repo.list_pages(int(site["id"]))
    blocks = []
    for page in pages:
        blocks.extend(normalize_blocks(page.get("body_json") or []))
    return {
        "seo": validate_seo(site, pages),
        "accessibility": validate_accessibility(blocks),
        "privacy": validate_privacy(site),
        "deontology": validate_deontology(blocks),
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
    }


def validate_seo(site: dict[str, Any], pages: list[dict[str, Any]]) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    if not clean_text(site.get("site_title")):
        warnings.append({"severity": "warning", "message": "Titolo SEO del sito mancante."})
    if not clean_text(site.get("site_description")):
        warnings.append({"severity": "warning", "message": "Descrizione SEO del sito mancante."})
    for page in pages:
        if not clean_text(page.get("seo_title")):
            warnings.append({"severity": "info", "message": f"Pagina '{page.get('title')}' senza titolo SEO dedicato."})
        if not clean_text(page.get("seo_description")):
            warnings.append({"severity": "info", "message": f"Pagina '{page.get('title')}' senza descrizione SEO."})
    return warnings


def validate_accessibility(blocks: list[dict[str, Any]]) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    for index, block in enumerate(blocks, start=1):
        if clean_text(block.get("image_url")) and not clean_text(block.get("image_alt")):
            warnings.append({"severity": "warning", "message": f"Blocco {index}: immagine senza testo alternativo."})
        if block.get("type") == "contact_form":
            warnings.append({"severity": "info", "message": "Modulo contatti: verificare sempre label e consenso privacy."})
    return warnings


def validate_privacy(site: dict[str, Any]) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    if truthy(site.get("analytics_enabled")) and not truthy(site.get("cookie_banner_enabled")):
        warnings.append({"severity": "error", "message": "Analytics attivo senza banner cookie/consenso."})
    if truthy(site.get("analytics_enabled")) and not clean_text(site.get("analytics_id")):
        warnings.append({"severity": "warning", "message": "Analytics attivo ma ID configurazione mancante."})
    if not clean_text(site.get("privacy_url")):
        warnings.append({"severity": "warning", "message": "URL privacy policy non indicato."})
    if not clean_text(site.get("cookie_policy_url")) and truthy(site.get("cookie_banner_enabled")):
        warnings.append({"severity": "warning", "message": "Banner cookie attivo ma cookie policy non indicata."})
    return warnings


def validate_deontology(blocks: list[dict[str, Any]]) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    for block in blocks:
        haystack = " ".join(
            clean_text(block.get(key)).lower()
            for key in ("title", "subtitle", "text", "button_text")
        )
        for phrase, reason in DEONTOLOGY_PATTERNS:
            if phrase in haystack:
                warnings.append(
                    {
                        "severity": "warning",
                        "phrase": phrase,
                        "message": reason,
                        "suggestion": "Riformula in modo informativo, prudente e verificabile.",
                    }
                )
    return warnings
