"""Dominio e helper del modulo Sito Studio."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from markupsafe import Markup, escape

from pct.applicazioni_catalogo import applicazioni_primo_piano
from pct.config_studio import ConfigDatiStudio
from pct.studio_site_blocks import BLOCK_TYPES_PRO
from pct.strumenti_legali import GestioneStrumentiLegali


RESERVED_PAGE_SLUGS = {
    "articoli",
    "prenota",
    "contatti",
    "strumenti-legali",
    "applicazioni",
    "news-giuridiche",
    "api",
    "assets",
}

BLOCK_TYPES: list[tuple[str, str]] = BLOCK_TYPES_PRO

WEEKDAY_LABELS = {
    0: "Lunedi",
    1: "Martedi",
    2: "Mercoledi",
    3: "Giovedi",
    4: "Venerdi",
    5: "Sabato",
    6: "Domenica",
}

DEFAULT_PRIMARY_COLOR = "#1d4ed8"
DEFAULT_SECONDARY_COLOR = "#0f172a"
DEFAULT_ACCENT_COLOR = "#16a34a"
DEFAULT_COVER_IMAGE = "https://images.unsplash.com/photo-1521791136064-7986c2920216?auto=format&fit=crop&w=1200&q=80"


@dataclass(frozen=True)
class StudioSiteProfile:
    tenant_slug: str
    studio_nome: str
    avvocato: str
    indirizzo: str
    citta: str
    provincia: str
    cap: str
    telefono: str
    email: str
    sito_web: str
    descrizione: str


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return clean_text(value).lower() in {"1", "true", "yes", "si", "s", "on"}


def slugify(value: Any) -> str:
    text = clean_text(value).lower()
    replacements = {
        "à": "a",
        "á": "a",
        "â": "a",
        "ä": "a",
        "è": "e",
        "é": "e",
        "ê": "e",
        "ë": "e",
        "ì": "i",
        "í": "i",
        "î": "i",
        "ï": "i",
        "ò": "o",
        "ó": "o",
        "ô": "o",
        "ö": "o",
        "ù": "u",
        "ú": "u",
        "û": "u",
        "ü": "u",
    }
    for raw, plain in replacements.items():
        text = text.replace(raw, plain)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "studio-legale"


def normalize_page_slug(slug: str, *, is_home: bool) -> str:
    normalized = slugify(slug)
    if is_home:
        return "home"
    if normalized in RESERVED_PAGE_SLUGS:
        return f"{normalized}-pagina"
    return normalized or "pagina"


def normalize_hex_color(value: Any, fallback: str) -> str:
    text = clean_text(value)
    if re.fullmatch(r"#[0-9A-Fa-f]{6}", text):
        return text.lower()
    return fallback


def parse_blocks(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        rows: list[dict[str, Any]] = []
        for item in raw:
            if isinstance(item, dict):
                rows.append(dict(item))
        return rows
    if isinstance(raw, str):
        text = clean_text(raw)
        if not text:
            return []
        try:
            payload = json.loads(text)
        except Exception:
            return []
        return parse_blocks(payload)
    return []


def nl2html(text: str) -> Markup:
    normalized = clean_text(text)
    if not normalized:
        return Markup("")
    paragraphs: list[Markup] = []
    for paragraph in str(text or "").strip().split("\n\n"):
        lines = [escape(line) for line in paragraph.splitlines()]
        paragraphs.append(Markup("<p>%s</p>") % Markup("<br>").join(lines))
    return Markup("").join(paragraphs)


def derive_site_studio_repository_db_path(anchor_path: str) -> str:
    target = Path(str(anchor_path or "./data/config/studio.json")).resolve()
    if target.suffix:
        parent = target.parent
        if parent.name.lower() == "config":
            root = parent.parent / "site_studio"
        elif target.name.lower() == "studio.db":
            root = parent / "site_studio"
        else:
            root = parent / "site_studio"
    else:
        root = target / "site_studio"
    root.mkdir(parents=True, exist_ok=True)
    return str(root / "site_studio.db")


def studio_site_profile_from_config(
    studio: ConfigDatiStudio | None,
    *,
    tenant_slug: str,
    fallback_name: str = "",
) -> StudioSiteProfile:
    cfg = studio or ConfigDatiStudio()
    studio_nome = clean_text(cfg.nome) or clean_text(fallback_name) or "Studio legale"
    citta = clean_text(cfg.city)
    provincia = clean_text(cfg.province)
    avvocato = clean_text(cfg.avvocato)
    tagline_parts = [
        part
        for part in (
            avvocato,
            f"Studio con sede a {citta}" if citta else "",
        )
        if part
    ]
    descrizione = (
        " - ".join(tagline_parts)
        or "Consulenza, assistenza e organizzazione digitale professionale per privati e imprese."
    )
    return StudioSiteProfile(
        tenant_slug=clean_text(tenant_slug).lower() or "studio-locale",
        studio_nome=studio_nome,
        avvocato=avvocato,
        indirizzo=clean_text(cfg.indirizzo),
        citta=citta,
        provincia=provincia,
        cap="",
        telefono=clean_text(cfg.telefono),
        email=clean_text(cfg.email),
        sito_web=clean_text(cfg.sito_web),
        descrizione=descrizione,
    )


def default_site_payload(profile: StudioSiteProfile) -> dict[str, Any]:
    public_slug = slugify(profile.studio_nome)
    footer_lines = [
        profile.studio_nome,
        clean_text(" ".join(part for part in (profile.indirizzo, profile.citta, profile.provincia) if part)),
        profile.telefono,
        profile.email,
    ]
    footer_text = " • ".join([line for line in footer_lines if line])
    return {
        "tenant_slug": profile.tenant_slug,
        "studio_nome": profile.studio_nome,
        "site_name": profile.studio_nome,
        "public_slug": public_slug,
        "site_title": profile.studio_nome,
        "site_description": profile.descrizione,
        "hero_claim": profile.descrizione,
        "logo_url": "",
        "favicon_url": "",
        "primary_color": DEFAULT_PRIMARY_COLOR,
        "secondary_color": DEFAULT_SECONDARY_COLOR,
        "accent_color": DEFAULT_ACCENT_COLOR,
        "contact_email": profile.email,
        "contact_phone": profile.telefono,
        "whatsapp_number": "",
        "address": profile.indirizzo,
        "city": profile.citta,
        "province": profile.provincia,
        "zip_code": profile.cap,
        "footer_text": footer_text,
        "facebook_url": "",
        "instagram_url": "",
        "linkedin_url": "",
        "show_legal_tools": False,
        "show_applications": False,
        "show_legal_news": False,
        "is_published": False,
        "is_active": True,
        "theme_template": "classic_legal",
        "theme_variant": "default",
        "design_tokens_json": {},
        "typography_json": {},
        "layout_json": {},
        "effects_json": {},
        "custom_css": "",
        "cookie_banner_enabled": False,
        "analytics_enabled": False,
        "analytics_provider": "",
        "analytics_id": "",
        "seo_json": {},
        "legal_disclaimer": (
            "Le informazioni pubblicate hanno carattere generale e non sostituiscono "
            "la consulenza professionale sul caso concreto."
        ),
        "privacy_url": "",
        "cookie_policy_url": "",
        "accessibility_statement_url": "",
    }


def default_page_seed(profile: StudioSiteProfile, public_slug: str) -> list[dict[str, Any]]:
    return [
        {
            "kind": "page",
            "title": "Home",
            "slug": "home",
            "excerpt": "Pagina iniziale del sito studio.",
            "status": "published",
            "show_in_menu": True,
            "sort_order": 0,
            "is_home": True,
            "body_json": [
                {
                    "type": "hero",
                    "title": profile.studio_nome,
                    "subtitle": profile.descrizione,
                    "button_text": "Prenota un appuntamento",
                    "button_url": f"/web/{public_slug}/prenota",
                    "image_url": "",
                },
                {
                    "type": "rich_text",
                    "title": "Lo studio",
                    "text": (
                        f"{profile.studio_nome} offre assistenza e consulenza professionale con "
                        "un presidio digitale chiaro, rapido e verificabile."
                    ),
                },
                {
                    "type": "booking_cta",
                    "title": "Prenota un incontro con lo studio",
                    "text": "Richiedi una consulenza o un primo colloquio direttamente dal sito dello studio.",
                    "button_text": "Richiedi appuntamento",
                },
                {
                    "type": "contact_form",
                    "title": "Contatta lo studio",
                },
            ],
        },
        {
            "kind": "page",
            "title": "Lo studio",
            "slug": "lo-studio",
            "excerpt": "Presentazione dello studio e dei professionisti.",
            "status": "published",
            "show_in_menu": True,
            "sort_order": 10,
            "is_home": False,
            "body_json": [
                {
                    "type": "rich_text",
                    "title": "Chi siamo",
                    "text": (
                        f"{profile.studio_nome} accompagna clienti e imprese con consulenza, "
                        "difesa e organizzazione documentale digitale."
                    ),
                },
                {
                    "type": "team",
                    "title": "Professionisti",
                },
            ],
        },
        {
            "kind": "page",
            "title": "Contatti",
            "slug": "contatti-studio",
            "excerpt": "Contatti, sedi e appuntamenti.",
            "status": "published",
            "show_in_menu": True,
            "sort_order": 20,
            "is_home": False,
            "body_json": [
                {
                    "type": "office_map",
                    "title": "Dove siamo",
                },
                {
                    "type": "contact_form",
                    "title": "Richiedi informazioni",
                },
                {
                    "type": "booking_cta",
                    "title": "Prenota un appuntamento",
                    "text": "Compila il modulo e scegli una fascia disponibile.",
                    "button_text": "Apri agenda appuntamenti",
                },
            ],
        },
    ]


def default_service_seed() -> list[dict[str, Any]]:
    return [
        {
            "title": "Consulenza e pareri",
            "slug": "consulenza-e-pareri",
            "short_description": "Pareri, strategie e assistenza continuativa per privati e imprese.",
            "long_description": "Analisi del caso, strategia operativa e presidio documentale lungo tutta la pratica.",
            "icon": "bi-chat-left-text",
            "sort_order": 0,
            "is_visible": True,
        },
        {
            "title": "Contenzioso e difesa giudiziale",
            "slug": "contenzioso-e-difesa-giudiziale",
            "short_description": "Gestione del fascicolo, udienze, deposito telematico e workflow documentale.",
            "long_description": "Presidio completo del fascicolo, monitor scadenze, atti, allegati e adempimenti telematici.",
            "icon": "bi-briefcase",
            "sort_order": 10,
            "is_visible": True,
        },
        {
            "title": "Contratti e compliance",
            "slug": "contratti-e-compliance",
            "short_description": "Redazione, revisione contratti e supporto operativo per adempimenti normativi.",
            "long_description": "Assistenza su contratti, risk review, procedure interne e presidio delle fonti rilevanti.",
            "icon": "bi-file-earmark-text",
            "sort_order": 20,
            "is_visible": True,
        },
    ]


def default_article_seed(profile: StudioSiteProfile) -> list[dict[str, Any]]:
    author_name = profile.avvocato or profile.studio_nome
    return [
        {
            "title": "Come prepararsi al primo incontro con il proprio legale",
            "slug": "come-prepararsi-al-primo-incontro",
            "excerpt": "Documenti, obiettivi e informazioni utili per rendere subito operativo il primo confronto con lo studio.",
            "cover_url": DEFAULT_COVER_IMAGE,
            "category": "Approfondimenti",
            "tags_csv": "prima consulenza,documenti,organizzazione",
            "author_name": author_name,
            "body_json": [
                {
                    "type": "rich_text",
                    "title": "Documenti essenziali",
                    "text": (
                        "Porta con te i documenti principali, una cronologia sintetica dei fatti "
                        "e le domande che vuoi chiarire fin dal primo incontro."
                    ),
                },
                {
                    "type": "cta",
                    "title": "Vuoi un appuntamento?",
                    "text": "Dal sito puoi richiedere una consulenza con data e fascia oraria.",
                    "button_text": "Prenota ora",
                    "button_url": "",
                },
            ],
            "status": "published",
            "published_at": date.today().isoformat(),
            "seo_title": "Prima consulenza legale: come prepararsi",
            "seo_description": "Guida pratica ai documenti e alle informazioni utili per il primo incontro con lo studio.",
        }
    ]


def default_professional_seed(profile: StudioSiteProfile) -> dict[str, Any] | None:
    if not profile.avvocato:
        return None
    return {
        "full_name": profile.avvocato,
        "role_title": "Avvocato",
        "bio": (
            f"{profile.avvocato} coordina l'attivita dello studio, la relazione con i clienti "
            "e l'impostazione strategica dei fascicoli."
        ),
        "photo_url": "",
        "email": profile.email,
        "phone": profile.telefono,
        "sort_order": 0,
        "is_visible": True,
    }


def default_office_seed(profile: StudioSiteProfile) -> dict[str, Any] | None:
    if not any((profile.indirizzo, profile.citta, profile.telefono, profile.email)):
        return None
    return {
        "name": "Sede principale",
        "address": profile.indirizzo,
        "city": profile.citta,
        "province": profile.provincia,
        "zip_code": profile.cap,
        "lat": "",
        "lng": "",
        "phone": profile.telefono,
        "email": profile.email,
        "opening_hours": "Lunedi - Venerdi: su appuntamento",
        "map_url": "",
        "is_primary": True,
        "is_visible": True,
    }


def booking_slots_for_date(
    rules: list[dict[str, Any]],
    requests: list[dict[str, Any]],
    *,
    requested_date_iso: str,
    office_id: int | None = None,
) -> list[dict[str, Any]]:
    if not requested_date_iso:
        return []
    try:
        requested_date = date.fromisoformat(requested_date_iso)
    except ValueError:
        return []

    slots: list[dict[str, Any]] = []
    weekday = requested_date.weekday()
    daily_rules = [
        row
        for row in rules
        if int(row.get("weekday") or -1) == weekday
        and truthy(row.get("is_active", True))
        and (office_id is None or int(row.get("office_id") or 0) == int(office_id))
    ]
    if not daily_rules:
        return []

    booked: dict[tuple[int, str], int] = {}
    for row in requests:
        if clean_text(row.get("requested_date")) != requested_date_iso:
            continue
        if clean_text(row.get("status")).lower() not in {"pending", "approved"}:
            continue
        key = (int(row.get("office_id") or 0), clean_text(row.get("requested_time")))
        booked[key] = booked.get(key, 0) + 1

    for rule in daily_rules:
        try:
            current = datetime.combine(
                requested_date,
                time.fromisoformat(clean_text(rule.get("start_time")) or "09:00"),
            )
            end_dt = datetime.combine(
                requested_date,
                time.fromisoformat(clean_text(rule.get("end_time")) or "18:00"),
            )
        except ValueError:
            continue
        slot_minutes = max(15, int(rule.get("slot_minutes") or 30))
        max_requests = max(1, int(rule.get("max_requests_per_slot") or 1))
        office_pk = int(rule.get("office_id") or 0)
        while current + timedelta(minutes=slot_minutes) <= end_dt:
            hhmm = current.strftime("%H:%M")
            key = (office_pk, hhmm)
            if booked.get(key, 0) < max_requests:
                slots.append(
                    {
                        "office_id": office_pk,
                        "date": requested_date_iso,
                        "time": hhmm,
                        "label": f"{hhmm} • {slot_minutes} minuti",
                        "slot_minutes": slot_minutes,
                    }
                )
            current += timedelta(minutes=slot_minutes)
    slots.sort(key=lambda row: (row["office_id"], row["time"]))
    return slots


def public_legal_tools_catalog(*, limit: int = 6, normative_db_path: str = "") -> list[dict[str, Any]]:
    gestore = GestioneStrumentiLegali(normative_db_path or "./intelligence/tabelle_normative.json")
    rows = []
    for item in gestore.catalogo_moduli()[:limit]:
        rows.append(
            {
                "id": clean_text(item.get("id")),
                "title": clean_text(item.get("title")),
                "subtitle": clean_text(item.get("subtitle")),
                "icon": clean_text(item.get("icon")) or "bi-tools",
                "category": clean_text(item.get("categoria")),
            }
        )
    return rows


def public_applications_catalog(*, limit: int = 6) -> list[dict[str, Any]]:
    rows = []
    for item in applicazioni_primo_piano(limit=limit):
        rows.append(
            {
                "id": clean_text(item.get("id")),
                "title": clean_text(item.get("title")),
                "summary": clean_text(item.get("summary")),
                "section_title": clean_text(item.get("section_title")),
                "icon": clean_text(item.get("icon")) or "bi-grid-1x2",
                "badge": clean_text(item.get("status_label") or item.get("status")),
            }
        )
    return rows
