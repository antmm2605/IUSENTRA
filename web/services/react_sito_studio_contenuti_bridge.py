"""Contenuti del sito dello studio per la shell React: servizi, professionisti, sedi, orari.

Sostituisce i moduli storici `/sito-studio/<raccolta>/nuovo` e
`/sito-studio/<raccolta>/<id>/modifica`. Ogni raccolta dichiara i propri campi
una volta sola (qui), con i controlli: il modulo React li mostra, l'API li
valida e il repository li salva (`pct/studio_site_repository.py`).

Le regole dell'agenda definiscono gli orari prenotabili dal sito pubblico: un
orario che finisce prima di iniziare o una durata fuori misura renderebbero la
prenotazione impossibile o ingannevole, quindi si rifiutano.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from pct.studio_site import WEEKDAY_LABELS, normalize_hex_color


@dataclass(frozen=True)
class Campo:
    name: str
    label: str
    kind: str = "text"  # text | textarea | number | email | url | checkbox | time | office | weekday | color
    required: bool = False
    help: str = ""
    default: Any = ""
    max_length: int = 0


@dataclass(frozen=True)
class Raccolta:
    key: str
    label: str
    singular: str
    title_field: str
    list_method: str
    get_method: str
    save_method: str
    delete_method: str
    id_keyword: str
    fields: tuple[Campo, ...] = field(default_factory=tuple)


RACCOLTE: dict[str, Raccolta] = {
    "servizi": Raccolta(
        "servizi", "Servizi", "servizio", "title", "list_services", "get_service", "save_service", "delete_service", "service_id",
        (
            Campo("title", "Titolo", required=True, max_length=160),
            Campo("slug", "Indirizzo (slug)", help="Lascia vuoto per ricavarlo dal titolo.", max_length=120),
            Campo("icon", "Icona", max_length=60),
            Campo("sort_order", "Ordine", "number", default="0"),
            Campo("short_description", "Descrizione breve", "textarea", max_length=400),
            Campo("long_description", "Descrizione completa", "textarea", max_length=8000),
            Campo("is_visible", "Visibile sul sito", "checkbox", default=True),
        ),
    ),
    "professionisti": Raccolta(
        "professionisti", "Professionisti", "professionista", "full_name", "list_professionals", "get_professional", "save_professional", "delete_professional", "professional_id",
        (
            Campo("full_name", "Nome e cognome", required=True, max_length=160),
            Campo("role_title", "Ruolo", max_length=160),
            Campo("email", "Email", "email", max_length=200),
            Campo("phone", "Telefono", max_length=40),
            Campo("photo_url", "Foto (indirizzo)", "url", max_length=500),
            Campo("sort_order", "Ordine", "number", default="0"),
            Campo("bio", "Presentazione", "textarea", max_length=8000),
            Campo("is_visible", "Visibile sul sito", "checkbox", default=True),
        ),
    ),
    "sedi": Raccolta(
        "sedi", "Sedi", "sede", "name", "list_offices", "get_office", "save_office", "delete_office", "office_id",
        (
            Campo("name", "Nome della sede", required=True, max_length=160),
            Campo("address", "Indirizzo", max_length=240),
            Campo("zip_code", "CAP", max_length=10),
            Campo("city", "Città", max_length=120),
            Campo("province", "Provincia", max_length=4),
            Campo("phone", "Telefono", max_length=40),
            Campo("email", "Email", "email", max_length=200),
            Campo("map_url", "Mappa (indirizzo)", "url", max_length=500),
            Campo("opening_hours", "Orari di apertura", "textarea", max_length=1000),
            Campo("is_primary", "Sede principale", "checkbox", default=False),
            Campo("is_visible", "Visibile sul sito", "checkbox", default=True),
        ),
    ),
    "regole-agenda": Raccolta(
        "regole-agenda", "Orari prenotabili", "orario", "weekday", "list_booking_rules", "get_booking_rule", "save_booking_rule", "delete_booking_rule", "rule_id",
        (
            Campo("office_id", "Sede", "office", required=True),
            Campo("weekday", "Giorno", "weekday", required=True, default="0"),
            Campo("start_time", "Dalle", "time", required=True, default="09:00"),
            Campo("end_time", "Alle", "time", required=True, default="13:00"),
            Campo("slot_minutes", "Durata di un appuntamento (minuti)", "number", required=True, default="30"),
            Campo("max_requests_per_slot", "Richieste per fascia", "number", required=True, default="1"),
            Campo("is_active", "Attivo", "checkbox", default=True),
        ),
    ),
}

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_ORA = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _t(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _t(value).lower() in {"1", "true", "on", "yes", "si", "sì"}


def raccolta(chiave: str) -> Raccolta | None:
    return RACCOLTE.get(_t(chiave).lower())


def _schema(r: Raccolta, sedi: list[dict[str, Any]]) -> list[dict[str, Any]]:
    schema = []
    for campo in r.fields:
        voce: dict[str, Any] = {
            "name": campo.name, "label": campo.label, "kind": campo.kind, "required": campo.required,
            "help": campo.help, "maxLength": campo.max_length,
        }
        if campo.kind == "office":
            voce["options"] = [{"value": str(s.get("id")), "label": _t(s.get("name")) or f"Sede {s.get('id')}"} for s in sedi]
        if campo.kind == "weekday":
            voce["options"] = [{"value": str(numero), "label": etichetta} for numero, etichetta in WEEKDAY_LABELS.items()]
        schema.append(voce)
    return schema


def _titolo(r: Raccolta, riga: dict[str, Any], sedi: dict[str, str]) -> str:
    if r.key == "regole-agenda":
        giorno = WEEKDAY_LABELS.get(int(riga.get("weekday") or 0), "")
        sede = sedi.get(str(riga.get("office_id")), "")
        return f"{giorno} {_t(riga.get('start_time'))}-{_t(riga.get('end_time'))}" + (f" · {sede}" if sede else "")
    return _t(riga.get(r.title_field)) or f"{r.singular.capitalize()} {riga.get('id')}"


def _valori(r: Raccolta, riga: dict[str, Any] | None) -> dict[str, Any]:
    valori: dict[str, Any] = {}
    for campo in r.fields:
        grezzo = (riga or {}).get(campo.name, campo.default) if riga else campo.default
        valori[campo.name] = _bool(grezzo) if campo.kind == "checkbox" else _t(grezzo)
    return valori


def elenco(repository: Any, site_id: int, chiave: str) -> tuple[dict[str, Any], int]:
    r = raccolta(chiave)
    if r is None:
        return {"ok": False, "message": "Sezione del sito non riconosciuta."}, 404
    righe = getattr(repository, r.list_method)(site_id) or []
    sedi = repository.list_offices(site_id) or []
    nomi_sedi = {str(s.get("id")): _t(s.get("name")) for s in sedi}
    return {
        "ok": True,
        "collection": {"key": r.key, "label": r.label, "singular": r.singular},
        "collections": [{"key": c.key, "label": c.label, "href": f"/sito-studio/{c.key}"} for c in RACCOLTE.values()],
        "fields": _schema(r, sedi),
        "defaults": _valori(r, None),
        "items": [
            {
                "id": str(riga.get("id")),
                "title": _titolo(r, riga, nomi_sedi),
                "visible": _bool(riga.get("is_active" if r.key == "regole-agenda" else "is_visible", True)),
                "values": _valori(r, riga),
                "editHref": f"/sito-studio/{r.key}/{riga.get('id')}/modifica",
            }
            for riga in righe
        ],
        "needsOffice": r.key == "regole-agenda" and not sedi,
    }, 200


def _valida(r: Raccolta, payload: dict[str, Any], sedi: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, str]]:
    ammessi = {c.name for c in r.fields}
    errori: dict[str, str] = {k: "Campo non previsto." for k in payload if k not in ammessi}
    pulito: dict[str, Any] = {}
    for campo in r.fields:
        grezzo = payload.get(campo.name, campo.default)
        if campo.kind == "checkbox":
            pulito[campo.name] = _bool(grezzo)
            continue
        valore = _t(grezzo)
        if campo.max_length and len(valore) > campo.max_length:
            errori[campo.name] = f"Massimo {campo.max_length} caratteri."
        if campo.required and not valore:
            errori[campo.name] = "Campo obbligatorio."
        elif valore and campo.kind == "email" and not _EMAIL.match(valore):
            errori[campo.name] = "Indirizzo email non valido."
        elif valore and campo.kind == "url" and not valore.startswith(("https://", "http://", "/")):
            errori[campo.name] = "Indica un indirizzo che inizia con https://."
        elif valore and campo.kind == "time" and not _ORA.match(valore):
            errori[campo.name] = "Orario nel formato hh:mm."
        elif campo.kind in {"number", "weekday", "office"} and valore and not valore.lstrip("-").isdigit():
            errori[campo.name] = "Valore numerico non valido."
        pulito[campo.name] = valore
    if r.key == "regole-agenda" and not errori:
        if pulito["office_id"] not in {str(s.get("id")) for s in sedi}:
            errori["office_id"] = "Sede non trovata."
        if not 0 <= int(pulito["weekday"]) <= 6:
            errori["weekday"] = "Giorno non valido."
        if pulito["end_time"] <= pulito["start_time"]:
            errori["end_time"] = "L'orario di fine deve seguire quello di inizio."
        if not 5 <= int(pulito["slot_minutes"]) <= 480:
            errori["slot_minutes"] = "Durata fra 5 e 480 minuti."
        if not 1 <= int(pulito["max_requests_per_slot"]) <= 50:
            errori["max_requests_per_slot"] = "Da 1 a 50 richieste per fascia."
    return pulito, errori


def salva(repository: Any, site_id: int, chiave: str, payload: dict[str, Any], *, item_id: str = "") -> tuple[dict[str, Any], int]:
    r = raccolta(chiave)
    if r is None:
        return {"ok": False, "message": "Sezione del sito non riconosciuta."}, 404
    if item_id:
        if not _t(item_id).isdigit() or getattr(repository, r.get_method)(site_id, int(item_id)) is None:
            return {"ok": False, "message": f"{r.singular.capitalize()} non trovato."}, 404
    sedi = repository.list_offices(site_id) or []
    pulito, errori = _valida(r, payload or {}, sedi)
    if errori:
        return {"ok": False, "message": "Controlla i campi evidenziati.", "errors": errori}, 400
    salvato = getattr(repository, r.save_method)(site_id, pulito, **({r.id_keyword: int(item_id)} if item_id else {}))
    return {
        "ok": True,
        "message": f"{r.singular.capitalize()} salvato.",
        "item": {"id": str((salvato or {}).get("id") or item_id)},
        "redirect_href": f"/sito-studio/{r.key}",
    }, 200


def elimina(repository: Any, site_id: int, chiave: str, item_id: str) -> tuple[dict[str, Any], int]:
    r = raccolta(chiave)
    if r is None or not _t(item_id).isdigit():
        return {"ok": False, "message": "Elemento non trovato."}, 404
    if getattr(repository, r.get_method)(site_id, int(item_id)) is None:
        return {"ok": False, "message": f"{r.singular.capitalize()} non trovato."}, 404
    if r.key == "sedi" and any(str(regola.get("office_id")) == str(item_id) for regola in (repository.list_booking_rules(site_id) or [])):
        return {"ok": False, "message": "La sede ha orari prenotabili: eliminali o spostali prima di eliminare la sede."}, 409
    getattr(repository, r.delete_method)(site_id, int(item_id))
    return {"ok": True, "message": f"{r.singular.capitalize()} eliminato.", "redirect_href": f"/sito-studio/{r.key}"}, 200


IMPOSTAZIONI: tuple[Campo, ...] = (
    Campo("studio_nome", "Nome dello studio", required=True, max_length=160),
    Campo("site_name", "Nome del sito", max_length=160),
    Campo("public_slug", "Indirizzo pubblico (/web/…)", help="Lettere minuscole, numeri e trattini.", max_length=80),
    Campo("site_title", "Titolo delle pagine", max_length=160),
    Campo("site_description", "Descrizione per i motori di ricerca", "textarea", max_length=360),
    Campo("hero_claim", "Frase principale", max_length=180),
    Campo("contact_email", "Email di contatto", "email", max_length=200),
    Campo("contact_phone", "Telefono", max_length=40),
    Campo("whatsapp_number", "WhatsApp", max_length=40),
    Campo("address", "Indirizzo", max_length=240),
    Campo("zip_code", "CAP", max_length=10),
    Campo("city", "Città", max_length=120),
    Campo("province", "Provincia", max_length=4),
    Campo("footer_text", "Testo a piè di pagina", "textarea", max_length=360),
    Campo("facebook_url", "Facebook", "url", max_length=300),
    Campo("instagram_url", "Instagram", "url", max_length=300),
    Campo("linkedin_url", "LinkedIn", "url", max_length=300),
    Campo("primary_color", "Colore principale", "color", default="#1d4ed8"),
    Campo("secondary_color", "Colore secondario", "color", default="#0f172a"),
    Campo("accent_color", "Colore di risalto", "color", default="#16a34a"),
    Campo("privacy_url", "Informativa privacy (indirizzo)", "url", max_length=300),
    Campo("cookie_policy_url", "Cookie policy (indirizzo)", "url", max_length=300),
    Campo("accessibility_statement_url", "Dichiarazione di accessibilità (indirizzo)", "url", max_length=300),
    Campo("legal_disclaimer", "Avvertenze legali", "textarea", max_length=500),
    Campo("analytics_provider", "Servizio di statistiche", max_length=60),
    Campo("analytics_id", "Identificativo delle statistiche", max_length=80),
    Campo("is_published", "Sito pubblicato", "checkbox"),
    Campo("is_active", "Sito attivo", "checkbox", default=True),
    Campo("show_legal_tools", "Mostra gli strumenti legali", "checkbox"),
    Campo("show_applications", "Mostra le applicazioni", "checkbox"),
    Campo("show_legal_news", "Mostra le news giuridiche", "checkbox"),
    Campo("cookie_banner_enabled", "Banner dei cookie", "checkbox", default=True),
    Campo("analytics_enabled", "Statistiche di visita", "checkbox"),
)

_COLORE = re.compile(r"^#[0-9a-fA-F]{6}$")


def impostazioni(site: dict[str, Any]) -> dict[str, Any]:
    r = Raccolta("impostazioni", "Impostazioni", "impostazioni", "site_name", "", "", "", "", "", IMPOSTAZIONI)
    return {
        "ok": True,
        "fields": _schema(r, []),
        "values": _valori(r, site),
        "publicUrl": _t(site.get("public_url")),
    }


def salva_impostazioni(repository: Any, site: dict[str, Any], payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    r = Raccolta("impostazioni", "Impostazioni", "impostazioni", "site_name", "", "", "", "", "", IMPOSTAZIONI)
    payload = dict(payload or {})
    colori = {k: _t(payload.get(k)) for k in ("primary_color", "secondary_color", "accent_color")}
    pulito, errori = _valida(r, payload, [])
    for chiave, valore in colori.items():
        if valore and not _COLORE.match(valore):
            errori[chiave] = "Colore nel formato #rrggbb."
        pulito[chiave] = normalize_hex_color(valore, _t(site.get(chiave)) or next(c.default for c in IMPOSTAZIONI if c.name == chiave))
    if pulito.get("analytics_enabled") and not pulito.get("cookie_banner_enabled"):
        # Statistiche di terze parti senza consenso: vietate dalle Linee guida
        # cookie del Garante per la protezione dei dati personali (10/06/2021).
        errori["analytics_enabled"] = "Le statistiche di visita richiedono il banner dei cookie (Linee guida del Garante privacy, 10/06/2021)."
    if errori:
        return {"ok": False, "message": "Controlla i campi evidenziati.", "errors": errori}, 400
    aggiornato = repository.save_site(int(site["id"]), pulito) or site
    return {"ok": True, "message": "Impostazioni del sito salvate.", "values": _valori(r, aggiornato), "publicUrl": _t(aggiornato.get("public_url"))}, 200


def crea_bozza_articolo(repository: Any, site_id: int, payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Una bozza di articolo con il solo titolo: il testo si scrive nell'editor dell'articolo."""
    titolo = _t((payload or {}).get("title"))
    if not titolo:
        return {"ok": False, "message": "Indica il titolo dell'articolo.", "errors": {"title": "Campo obbligatorio."}}, 400
    if len(titolo) > 200:
        return {"ok": False, "message": "Titolo troppo lungo.", "errors": {"title": "Massimo 200 caratteri."}}, 400
    articolo = repository.save_article(site_id, {"title": titolo, "author_name": _t((payload or {}).get("author_name"))[:160], "status": "draft", "body_json": "[]"}) or {}
    ident = _t(articolo.get("id"))
    return {"ok": True, "message": "Bozza creata.", "item": {"id": ident}, "redirect_href": f"/sito-studio/articoli/{ident}/modifica"}, 200


__all__ = ["IMPOSTAZIONI", "RACCOLTE", "elenco", "elimina", "crea_bozza_articolo", "impostazioni", "raccolta", "salva", "salva_impostazioni"]
