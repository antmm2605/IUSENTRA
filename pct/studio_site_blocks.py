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
    ("hero_slider", "Hero scorrevole"),
    ("image_text_slider", "Testo e immagini scorrevoli"),
    ("gallery_grid", "Galleria immagini"),
    ("image_text_split", "Immagine e testo"),
    ("logo_strip", "Loghi e appartenenze"),
    ("text_ticker", "Testi scorrevoli"),
    ("featured_services_carousel", "Servizi in evidenza"),
    ("article_carousel", "Articoli in evidenza"),
    ("quote_banner", "Citazione istituzionale"),
    ("contact_cta_split", "Contatto con immagine"),
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
    "hero_slider": {
        "title": "Studio legale",
        "subtitle": "Assistenza professionale con un percorso chiaro e verificabile.",
        "button_text": "Contatta lo studio",
        "style_variant": "slider",
        "items": [
            {
                "title": "Ascolto e metodo",
                "text": "Inquadriamo il caso, i documenti e le priorita operative.",
                "image_url": "",
                "image_alt": "Studio legale con documenti ordinati",
                "button_text": "Richiedi informazioni",
                "button_url": "",
            },
            {
                "title": "Gestione digitale della pratica",
                "text": "Scadenze, documenti e comunicazioni restano organizzati.",
                "image_url": "",
                "image_alt": "Scrivania professionale con fascicolo digitale",
                "button_text": "Prenota un appuntamento",
                "button_url": "",
            },
        ],
    },
    "image_text_slider": {
        "title": "Percorsi di assistenza",
        "subtitle": "Sezioni scorrevoli con testo e immagine.",
        "items": [
            {"title": "Analisi iniziale", "text": "Valutazione dei documenti e dei primi passaggi.", "image_url": "", "image_alt": "Analisi documentale"},
            {"title": "Strategia operativa", "text": "Definizione delle attivita e delle scadenze.", "image_url": "", "image_alt": "Pianificazione legale"},
        ],
    },
    "gallery_grid": {
        "title": "Lo studio",
        "subtitle": "Immagini dello studio o elementi istituzionali generici.",
        "items": [
            {"title": "Sala riunioni", "image_url": "", "image_alt": "Sala riunioni dello studio"},
            {"title": "Biblioteca", "image_url": "", "image_alt": "Biblioteca giuridica"},
            {"title": "Accoglienza", "image_url": "", "image_alt": "Ambiente professionale dello studio"},
        ],
    },
    "image_text_split": {
        "title": "Un metodo ordinato per ogni pratica",
        "text": "La relazione con il cliente viene gestita con passaggi chiari, documenti tracciati e comunicazioni verificabili.",
        "image_url": "",
        "image_alt": "Documenti e agenda di studio",
        "button_text": "Scopri il metodo",
    },
    "logo_strip": {
        "title": "Presidi e strumenti dello studio",
        "items": [
            {"title": "PCT", "text": "Deposito telematico civile"},
            {"title": "PEC", "text": "Comunicazioni e notifiche"},
            {"title": "Agenda", "text": "Scadenze presidiate"},
        ],
    },
    "text_ticker": {
        "title": "Avvisi rapidi",
        "items": [
            {"text": "Prenotazioni su appuntamento"},
            {"text": "Documenti caricabili prima del colloquio"},
            {"text": "Riscontro alle richieste tramite canali ufficiali"},
        ],
    },
    "featured_services_carousel": {
        "title": "Servizi in evidenza",
        "subtitle": "Aree selezionate dallo studio.",
    },
    "article_carousel": {
        "title": "Approfondimenti recenti",
        "subtitle": "Articoli pubblicati dallo studio dopo revisione interna.",
    },
    "quote_banner": {
        "title": "Un approccio prudente e documentato",
        "text": "Ogni pratica richiede ascolto, verifica dei fatti e valutazione delle opzioni concretamente percorribili.",
        "style_variant": "istituzionale",
    },
    "contact_cta_split": {
        "title": "Vuoi parlare con lo studio?",
        "text": "Invia una richiesta con i dati essenziali: lo studio valuterà il primo contatto e ti indicherà i passaggi successivi.",
        "button_text": "Richiedi contatto",
        "image_url": "",
        "image_alt": "Contatto con lo studio legale",
    },
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
