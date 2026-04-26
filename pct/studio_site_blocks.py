"""Schema blocchi per il Website Studio Legale."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any


BLOCK_TYPES_PRO: list[tuple[str, str]] = [
    ("hero", "Hero"),
    ("hero_split", "Hero con immagine"),
    ("hero_centered", "Hero centrata"),
    ("trust_bar", "Barra fiducia"),
    ("practice_areas", "Aree di attivita"),
    ("services", "Servizi"),
    ("service_detail", "Dettaglio servizio"),
    ("rich_text", "Testo editoriale"),
    ("feature_grid", "Griglia caratteristiche"),
    ("process_steps", "Processo operativo"),
    ("timeline", "Timeline"),
    ("team", "Professionisti"),
    ("professional_profile", "Profilo professionista"),
    ("latest_articles", "Ultimi articoli"),
    ("legal_news", "News giuridiche"),
    ("faq", "FAQ"),
    ("testimonials_safe", "Testimonianze prudenti"),
    ("stats", "Indicatori"),
    ("cta", "Invito all'azione"),
    ("booking_cta", "Prenotazione"),
    ("contact_form", "Modulo contatti"),
    ("office_map", "Mappa ufficio"),
    ("offices", "Sedi"),
    ("document_checklist", "Checklist documenti"),
    ("legal_tools", "Strumenti legali"),
    ("applications", "Applicazioni"),
    ("newsletter", "Newsletter"),
    ("footer_rich", "Footer ricco"),
    ("privacy_notice", "Avviso privacy"),
]

BLOCK_TYPE_CODES = {code for code, _label in BLOCK_TYPES_PRO}

BLOCK_DEFAULTS: dict[str, dict[str, Any]] = {
    "hero": {
        "title": "Studio legale",
        "subtitle": "Assistenza professionale chiara e organizzata.",
        "button_text": "Contatta lo studio",
        "style_variant": "default",
    },
    "hero_split": {
        "title": "Studio legale",
        "subtitle": "Metodo, ascolto e gestione digitale della pratica.",
        "button_text": "Prenota un appuntamento",
        "style_variant": "split",
    },
    "hero_centered": {
        "title": "Studio legale",
        "subtitle": "Consulenza e difesa con un percorso chiaro.",
        "button_text": "Richiedi informazioni",
        "style_variant": "centered",
    },
    "trust_bar": {
        "title": "Perche scegliere un percorso ordinato",
        "items": [
            {"title": "Metodo", "text": "Analisi iniziale e passaggi chiari."},
            {"title": "Documenti", "text": "Raccolta e verifica delle evidenze."},
            {"title": "Aggiornamenti", "text": "Comunicazioni sullo stato pratica."},
        ],
    },
    "practice_areas": {"title": "Aree di attivita"},
    "services": {"title": "Servizi dello studio"},
    "service_detail": {"title": "Approfondimento servizio"},
    "rich_text": {"title": "Sezione testuale", "text": "Inserisci qui il testo della sezione."},
    "feature_grid": {
        "title": "Punti di forza operativi",
        "items": [
            {"title": "Analisi", "text": "Studio della documentazione."},
            {"title": "Strategia", "text": "Percorso operativo condiviso."},
            {"title": "Presidio", "text": "Monitoraggio di attivita e scadenze."},
        ],
    },
    "process_steps": {
        "title": "Come lavoriamo",
        "items": [
            {"title": "1. Inquadramento", "text": "Raccolta dati e documenti essenziali."},
            {"title": "2. Strategia", "text": "Valutazione delle opzioni praticabili."},
            {"title": "3. Esecuzione", "text": "Gestione della pratica e aggiornamenti."},
        ],
    },
    "timeline": {"title": "Percorso della pratica"},
    "team": {"title": "Professionisti"},
    "professional_profile": {"title": "Profilo professionale"},
    "latest_articles": {"title": "Ultimi articoli"},
    "legal_news": {"title": "Aggiornamenti giuridici"},
    "faq": {
        "title": "Domande frequenti",
        "items": [
            {"title": "Come richiedere un appuntamento?", "text": "Usa il modulo contatti o la prenotazione online."},
            {"title": "Quali documenti servono?", "text": "Porta gli atti principali e una breve cronologia."},
        ],
    },
    "testimonials_safe": {
        "title": "Esperienze e metodo",
        "text": "Usa questa sezione solo con contenuti autorizzati, sobri e non comparativi.",
    },
    "stats": {
        "title": "Indicatori dello studio",
        "items": [
            {"title": "Metodo", "text": "Workflow documentale tracciato"},
            {"title": "Agenda", "text": "Scadenze e appuntamenti presidiati"},
        ],
    },
    "cta": {"title": "Richiedi supporto", "button_text": "Contattaci"},
    "booking_cta": {"title": "Prenota un appuntamento", "button_text": "Apri agenda"},
    "contact_form": {"title": "Contatta lo studio"},
    "office_map": {"title": "Dove siamo"},
    "offices": {"title": "Sedi dello studio"},
    "document_checklist": {"title": "Documenti utili per il primo incontro"},
    "legal_tools": {"title": "Strumenti legali"},
    "applications": {"title": "Applicazioni"},
    "newsletter": {"title": "Ricevi aggiornamenti"},
    "footer_rich": {"title": "Informazioni dello studio"},
    "privacy_notice": {"title": "Privacy e correttezza informativa"},
}


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def block_type_choices() -> list[tuple[str, str]]:
    return list(BLOCK_TYPES_PRO)


def default_block(block_type: Any) -> dict[str, Any]:
    code = clean_text(block_type).lower() or "rich_text"
    if code not in BLOCK_TYPE_CODES:
        code = "rich_text"
    base = {
        "type": code,
        "title": "",
        "subtitle": "",
        "text": "",
        "items": [],
        "image_url": "",
        "image_alt": "",
        "button_text": "",
        "button_url": "",
        "style_variant": "default",
        "background": "default",
        "visibility": {"desktop": True, "tablet": True, "mobile": True},
        "spacing": "standard",
        "alignment": "start",
        "animation": "fade-up",
    }
    base.update(deepcopy(BLOCK_DEFAULTS.get(code) or {}))
    return base


def normalize_block(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return default_block("rich_text")
    code = clean_text(value.get("type")).lower() or "rich_text"
    block = default_block(code)
    for key in (
        "title",
        "subtitle",
        "text",
        "image_url",
        "image_alt",
        "button_text",
        "button_url",
        "style_variant",
        "background",
        "spacing",
        "alignment",
        "animation",
    ):
        if key in value:
            block[key] = clean_text(value.get(key))
    if isinstance(value.get("items"), list):
        block["items"] = [dict(item) for item in value["items"] if isinstance(item, dict)]
    if isinstance(value.get("visibility"), dict):
        block["visibility"] = {
            "desktop": bool(value["visibility"].get("desktop", True)),
            "tablet": bool(value["visibility"].get("tablet", True)),
            "mobile": bool(value["visibility"].get("mobile", True)),
        }
    return block


def normalize_blocks(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            value = json.loads(text)
        except Exception:
            return []
    if not isinstance(value, list):
        return []
    return [normalize_block(item) for item in value if isinstance(item, dict)]


def block_presets() -> list[dict[str, Any]]:
    return [
        {"type": code, "label": label, "defaults": default_block(code)}
        for code, label in BLOCK_TYPES_PRO
    ]
