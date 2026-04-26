"""Motore temi e design token per Sito Studio Builder Pro."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any


DEFAULT_THEME_TEMPLATE = "classic_legal"

FONT_PRESETS: dict[str, dict[str, str]] = {
    "system_professional": {
        "label": "System Professional",
        "heading": "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
        "body": "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    },
    "serif_elegant": {
        "label": "Serif Elegant",
        "heading": "Georgia, 'Times New Roman', serif",
        "body": "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    },
    "modern_sans": {
        "label": "Modern Sans",
        "heading": "'Aptos Display', 'Segoe UI', sans-serif",
        "body": "'Aptos', 'Segoe UI', sans-serif",
    },
    "editorial_legal": {
        "label": "Editorial Legal",
        "heading": "'Palatino Linotype', Palatino, Georgia, serif",
        "body": "Georgia, 'Times New Roman', serif",
    },
    "compact_business": {
        "label": "Compact Business",
        "heading": "'Segoe UI Semibold', 'Segoe UI', sans-serif",
        "body": "'Segoe UI', sans-serif",
    },
}

DESIGN_TOKEN_DEFAULTS: dict[str, str] = {
    "primary": "#1a2744",
    "secondary": "#0f172a",
    "accent": "#b8860b",
    "bg": "#f6f7fb",
    "surface": "#ffffff",
    "text": "#111827",
    "muted": "#64748b",
    "border": "#dbe3ef",
    "radius_sm": "0.55rem",
    "radius_md": "1rem",
    "radius_lg": "1.55rem",
    "shadow_sm": "0 0.35rem 1rem rgba(15, 23, 42, 0.08)",
    "shadow_md": "0 1rem 2.4rem rgba(15, 23, 42, 0.12)",
    "shadow_lg": "0 1.7rem 4rem rgba(15, 23, 42, 0.18)",
    "font_heading": FONT_PRESETS["system_professional"]["heading"],
    "font_body": FONT_PRESETS["system_professional"]["body"],
    "font_size_base": "16px",
    "line_height": "1.65",
    "container_width": "1180px",
    "section_padding": "5rem",
    "card_padding": "1.6rem",
    "button_radius": "999px",
    "animation_speed": "220ms",
}


def _block(block_type: str, **payload: Any) -> dict[str, Any]:
    row = {
        "type": block_type,
        "title": "",
        "subtitle": "",
        "text": "",
        "items": [],
        "image_url": "",
        "button_text": "",
        "button_url": "",
        "style_variant": "default",
        "background": "default",
        "visibility": {"desktop": True, "tablet": True, "mobile": True},
        "spacing": "standard",
        "animation": "fade-up",
    }
    row.update(payload)
    return row


def _home_blocks(tone: str) -> list[dict[str, Any]]:
    return [
        _block(
            "hero_split",
            title="Studio legale",
            subtitle="Assistenza chiara, metodo e presenza digitale per ogni fase della pratica.",
            button_text="Richiedi un appuntamento",
            style_variant=tone,
        ),
        _block(
            "trust_bar",
            title="Metodo professionale",
            items=[
                {"title": "Ascolto", "text": "Inquadramento iniziale ordinato."},
                {"title": "Strategia", "text": "Percorso operativo e documentale."},
                {"title": "Aggiornamenti", "text": "Comunicazioni chiare sullo stato pratica."},
            ],
        ),
        _block("practice_areas", title="Aree di attivita"),
        _block("process_steps", title="Come lavoriamo"),
        _block("team", title="Professionisti"),
        _block("booking_cta", title="Prenota un confronto", button_text="Apri agenda"),
        _block("contact_form", title="Contatta lo studio"),
    ]


THEME_TEMPLATES: dict[str, dict[str, Any]] = {
    "classic_legal": {
        "name": "Classic Legal",
        "description": "Istituzionale, sobrio e leggibile, pensato per studi generalisti.",
        "category": "istituzionale",
        "preview": "classic_legal",
        "tokens": {
            "primary": "#1a2744",
            "secondary": "#0f172a",
            "accent": "#b8860b",
            "bg": "#f7f8fb",
            "surface": "#ffffff",
        },
        "font_preset": "system_professional",
        "layout": {"hero": "split", "density": "standard", "header": "sticky"},
        "effects": {"animation": "fade-up", "speed": "220ms"},
        "home_blocks": _home_blocks("classic"),
        "recommended_sections": ["home", "lo-studio", "aree-attivita", "contatti"],
        "recommended_cta": "Prenota un appuntamento",
        "deontological_notes": ["Evitare promesse di risultato e confronti con altri studi."],
    },
    "boutique_elegante": {
        "name": "Boutique elegante",
        "description": "Premium, editoriale e caldo, adatto a studi boutique.",
        "category": "premium",
        "preview": "boutique_elegante",
        "tokens": {
            "primary": "#2b2118",
            "secondary": "#5a4635",
            "accent": "#c59b61",
            "bg": "#fbf7f0",
            "surface": "#fffdf8",
            "radius_lg": "1.9rem",
        },
        "font_preset": "serif_elegant",
        "layout": {"hero": "centered", "density": "airy", "header": "minimal"},
        "effects": {"animation": "soft-reveal", "speed": "260ms"},
        "home_blocks": _home_blocks("boutique"),
        "recommended_sections": ["home", "profilo", "servizi", "contatti"],
        "recommended_cta": "Fissa un primo colloquio",
        "deontological_notes": ["Usare tono sobrio anche con visual premium."],
    },
    "corporate_premium": {
        "name": "Corporate Premium",
        "description": "Strutturato, con servizi, KPI, team e sedi in evidenza.",
        "category": "corporate",
        "preview": "corporate_premium",
        "tokens": {
            "primary": "#12325a",
            "secondary": "#07111f",
            "accent": "#2aa8a1",
            "bg": "#eef3f8",
            "surface": "#ffffff",
        },
        "font_preset": "modern_sans",
        "layout": {"hero": "split", "density": "compact", "header": "full"},
        "effects": {"animation": "slide-up", "speed": "200ms"},
        "home_blocks": _home_blocks("corporate"),
        "recommended_sections": ["home", "servizi", "team", "sedi", "articoli"],
        "recommended_cta": "Parla con lo studio",
        "deontological_notes": ["I dati numerici devono essere verificabili."],
    },
    "digital_modern": {
        "name": "Digital Modern",
        "description": "Moderno, con gradienti leggeri e card dinamiche.",
        "category": "digitale",
        "preview": "digital_modern",
        "tokens": {
            "primary": "#0b3b75",
            "secondary": "#102033",
            "accent": "#00a6a6",
            "bg": "#f1f8ff",
            "surface": "#ffffff",
        },
        "font_preset": "modern_sans",
        "layout": {"hero": "split", "density": "standard", "header": "floating"},
        "effects": {"animation": "fade-up", "speed": "180ms"},
        "home_blocks": _home_blocks("digital"),
        "recommended_sections": ["home", "strumenti", "prenota", "contatti"],
        "recommended_cta": "Avvia la richiesta",
        "deontological_notes": ["Non presentare automazioni come sostitutive della valutazione legale."],
    },
    "penalista": {
        "name": "Penalista",
        "description": "Scuro, serio e orientato a urgenze e difesa.",
        "category": "specialistico",
        "preview": "penalista",
        "tokens": {
            "primary": "#111827",
            "secondary": "#020617",
            "accent": "#d6a34a",
            "bg": "#10151f",
            "surface": "#182133",
            "text": "#f8fafc",
            "muted": "#cbd5e1",
            "border": "#334155",
        },
        "font_preset": "compact_business",
        "layout": {"hero": "split", "density": "compact", "header": "sticky"},
        "effects": {"animation": "fade-up", "speed": "200ms"},
        "home_blocks": _home_blocks("penalista"),
        "recommended_sections": ["home", "urgenze", "difesa", "contatti"],
        "recommended_cta": "Richiedi contatto riservato",
        "deontological_notes": ["Evitare frasi allarmistiche o garanzie sull'esito."],
    },
    "civilista": {
        "name": "Civilista",
        "description": "Equilibrato per civile, famiglia, lavoro e contratti.",
        "category": "specialistico",
        "preview": "civilista",
        "tokens": {
            "primary": "#24466f",
            "secondary": "#19314f",
            "accent": "#6b8f71",
            "bg": "#f4f7f4",
            "surface": "#ffffff",
        },
        "font_preset": "system_professional",
        "layout": {"hero": "split", "density": "standard", "header": "sticky"},
        "effects": {"animation": "fade-up", "speed": "220ms"},
        "home_blocks": _home_blocks("civilista"),
        "recommended_sections": ["home", "aree-civili", "faq", "contatti"],
        "recommended_cta": "Racconta il tuo caso",
        "deontological_notes": ["Descrivere servizi senza creare aspettative di risultato."],
    },
    "tributario": {
        "name": "Tributario",
        "description": "Tecnico, chiaro su scadenze, accertamenti e contenzioso.",
        "category": "specialistico",
        "preview": "tributario",
        "tokens": {
            "primary": "#17324d",
            "secondary": "#0f2438",
            "accent": "#d9902f",
            "bg": "#f7f5f0",
            "surface": "#ffffff",
        },
        "font_preset": "compact_business",
        "layout": {"hero": "split", "density": "compact", "header": "sticky"},
        "effects": {"animation": "fade-up", "speed": "200ms"},
        "home_blocks": _home_blocks("tributario"),
        "recommended_sections": ["home", "contenzioso-tributario", "scadenze", "contatti"],
        "recommended_cta": "Analizza l'atto ricevuto",
        "deontological_notes": ["Distinguere sempre informazione generale e consulenza sul caso."],
    },
    "amministrativo": {
        "name": "Amministrativo",
        "description": "Istituzionale per TAR, appalti, PA, urbanistica e accesso agli atti.",
        "category": "istituzionale",
        "preview": "amministrativo",
        "tokens": {
            "primary": "#203354",
            "secondary": "#111827",
            "accent": "#8c6d31",
            "bg": "#f4f6f8",
            "surface": "#ffffff",
        },
        "font_preset": "editorial_legal",
        "layout": {"hero": "centered", "density": "standard", "header": "formal"},
        "effects": {"animation": "fade-up", "speed": "240ms"},
        "home_blocks": _home_blocks("amministrativo"),
        "recommended_sections": ["home", "appalti", "tar", "pa", "contatti"],
        "recommended_cta": "Richiedi valutazione documentale",
        "deontological_notes": ["Evitare toni promozionali incompatibili con servizi verso PA."],
    },
}


CSS_TOKEN_MAP = {
    "primary": "--site-primary",
    "secondary": "--site-secondary",
    "accent": "--site-accent",
    "bg": "--site-bg",
    "surface": "--site-surface",
    "text": "--site-text",
    "muted": "--site-muted",
    "border": "--site-border",
    "radius_sm": "--site-radius-sm",
    "radius_md": "--site-radius-md",
    "radius_lg": "--site-radius-lg",
    "shadow_sm": "--site-shadow-sm",
    "shadow_md": "--site-shadow-md",
    "shadow_lg": "--site-shadow-lg",
    "font_heading": "--site-font-heading",
    "font_body": "--site-font-body",
    "font_size_base": "--site-font-size-base",
    "line_height": "--site-line-height",
    "container_width": "--site-container-width",
    "section_padding": "--site-section-padding",
    "card_padding": "--site-card-padding",
    "button_radius": "--site-button-radius",
    "animation_speed": "--site-animation-speed",
}


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _json_load(value: Any, default: Any) -> Any:
    if isinstance(value, (dict, list)):
        return deepcopy(value)
    text = str(value or "").strip()
    if not text:
        return deepcopy(default)
    try:
        return json.loads(text)
    except Exception:
        return deepcopy(default)


def normalize_hex_color(value: Any, fallback: str) -> str:
    text = clean_text(value)
    if re.fullmatch(r"#[0-9A-Fa-f]{6}", text):
        return text.lower()
    return fallback


def normalize_font_preset(value: Any) -> str:
    code = clean_text(value).lower() or "system_professional"
    return code if code in FONT_PRESETS else "system_professional"


def get_theme_template(code: Any) -> dict[str, Any]:
    key = clean_text(code).lower() or DEFAULT_THEME_TEMPLATE
    return deepcopy(THEME_TEMPLATES.get(key) or THEME_TEMPLATES[DEFAULT_THEME_TEMPLATE])


def list_theme_templates() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for code, payload in THEME_TEMPLATES.items():
        item = deepcopy(payload)
        item["code"] = code
        rows.append(item)
    return rows


def build_design_tokens(template_code: Any, overrides: Any = None, typography: Any = None) -> dict[str, str]:
    template = get_theme_template(template_code)
    tokens = deepcopy(DESIGN_TOKEN_DEFAULTS)
    tokens.update(template.get("tokens") or {})
    tokens.update(_json_load(overrides, {}))
    typo = _json_load(typography, {})
    font_preset = normalize_font_preset(typo.get("font_preset") or template.get("font_preset"))
    tokens["font_heading"] = clean_text(typo.get("font_heading")) or FONT_PRESETS[font_preset]["heading"]
    tokens["font_body"] = clean_text(typo.get("font_body")) or FONT_PRESETS[font_preset]["body"]
    for key in ("primary", "secondary", "accent", "bg", "surface", "text", "muted", "border"):
        tokens[key] = normalize_hex_color(tokens.get(key), DESIGN_TOKEN_DEFAULTS[key])
    for key in ("font_size_base", "line_height", "container_width", "section_padding", "card_padding"):
        if clean_text(typo.get(key)):
            tokens[key] = clean_text(typo.get(key))
    return {key: clean_text(value) for key, value in tokens.items()}


def css_variables_from_tokens(tokens: dict[str, Any]) -> str:
    rows = []
    for key, var_name in CSS_TOKEN_MAP.items():
        value = clean_text(tokens.get(key) or DESIGN_TOKEN_DEFAULTS.get(key) or "")
        if value:
            rows.append(f"{var_name}: {value};")
    return " ".join(rows)


def sanitize_custom_css(value: Any, *, limit: int = 12000) -> str:
    css = str(value or "")[:limit]
    forbidden = ("<", ">", "@import", "javascript:", "expression(", "behavior:")
    lowered = css.lower()
    if any(token in lowered for token in forbidden):
        return ""
    return css


def theme_snapshot(site: dict[str, Any]) -> dict[str, Any]:
    template_code = clean_text(site.get("theme_template")) or DEFAULT_THEME_TEMPLATE
    typography = _json_load(site.get("typography_json"), {})
    tokens = build_design_tokens(template_code, site.get("design_tokens_json"), typography)
    return {
        "template": get_theme_template(template_code),
        "template_code": template_code,
        "tokens": tokens,
        "css_variables": css_variables_from_tokens(tokens),
        "typography": typography,
        "layout": _json_load(site.get("layout_json"), {}),
        "effects": _json_load(site.get("effects_json"), {}),
        "custom_css": sanitize_custom_css(site.get("custom_css")),
    }
