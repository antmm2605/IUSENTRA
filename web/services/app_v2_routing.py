"""Routing sicuro tra pagine legacy e shell React/App V2.

La fase 4 non forza redirect globali: prepara una mappa esplicita e helper
fail-closed che potranno essere usati pagina per pagina quando il relativo
feature flag sara' acceso.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit, urlunsplit

from web.services.feature_flags import app_v2_route_flag_for_path, is_feature_enabled


SAFE_QUERY_PARAMS = frozenset(
    {
        "page",
        "q",
        "search",
        "filter",
        "sort",
        "tab",
        "view",
        "from",
        "to",
        "status",
        "drawer",
        "section",
        "focus",
    }
)

UNSAFE_QUERY_PARAMS = frozenset(
    {
        "next",
        "return",
        "return_url",
        "redirect",
        "redirect_url",
        "callback",
        "url",
        "target",
        "tenant_id",
        "studio_id",
        "user_id",
        "role",
        "permission",
        "is_admin",
        "debug",
        "token",
        "access_token",
        "api_key",
    }
)

LEGACY_TO_APP_V2_TARGETS: Mapping[str, str] = {
    "/": "/app-v2",
    "/admin/database": "/app-v2/admin/database",
    "/agenda": "/app-v2/agenda",
    "/agenda/nuovo": "/app-v2/agenda/nuovo",
    "/amministrazione": "/app-v2/amministrazione",
    "/audit": "/app-v2/audit",
    "/backup": "/app-v2/backup",
    "/cartelle-condivise": "/app-v2/cartelle-condivise",
    "/clienti": "/app-v2/clienti",
    "/clienti/nuovo": "/app-v2/clienti/nuovo",
    "/compensi-forensi": "/app-v2/compensi-forensi",
    "/deposito/checklist": "/app-v2/deposito/checklist",
    "/documenti": "/app-v2/documenti",
    "/email": "/app-v2/email",
    "/email-ordinaria": "/app-v2/email-ordinaria",
    "/fatturazione": "/app-v2/fatturazione",
    "/fatturazione/nuova": "/app-v2/fatturazione/nuova",
    "/fascicoli": "/app-v2/fascicoli",
    "/fascicoli/archivio": "/app-v2/fascicoli/archivio",
    "/fascicoli/nuovo": "/app-v2/fascicoli/nuovo",
    "/giurisprudenza": "/app-v2/giurisprudenza",
    "/global-search": "/app-v2/global-search",
    "/impostazioni": "/app-v2/impostazioni",
    "/impostazioni-studio": "/app-v2/impostazioni-studio",
    "/impostazioni/calendario": "/app-v2/impostazioni/calendario",
    "/impostazioni/pagamenti": "/app-v2/impostazioni/pagamenti",
    "/incassi-pagamenti": "/app-v2/incassi-pagamenti",
    "/legal-intelligence": "/app-v2/legal-intelligence",
    "/legal-intelligence/mediazione": "/app-v2/legal-intelligence/mediazione",
    "/legal-intelligence/news": "/app-v2/legal-intelligence/news",
    "/messaggi": "/app-v2/messaggi",
    "/messaggi/nuovo": "/app-v2/messaggi/nuovo",
    "/notifiche": "/app-v2/notifiche",
    "/notifiche-legali": "/app-v2/notifiche-legali",
    "/notifiche-whatsapp": "/app-v2/notifiche-whatsapp",
    "/preventivi": "/app-v2/preventivi",
    "/preventivi/conferimento/nuovo": "/app-v2/preventivi/conferimento/nuovo",
    "/preventivi/nuovo": "/app-v2/preventivi/nuovo",
    "/preventivi/wizard": "/app-v2/preventivi/wizard",
    "/privacy/registro": "/app-v2/privacy/registro",
    "/privacy/registro/nuovo": "/app-v2/privacy/registro/nuovo",
    "/profili": "/app-v2/profili",
    "/redazione-atti": "/app-v2/redazione-atti",
    "/regia-operativa": "/app-v2/regia-operativa",
    "/registro-attivita": "/app-v2/registro-attivita",
    "/registro-gdpr": "/app-v2/registro-gdpr",
    "/ricerca-legale": "/app-v2/ricerca-legale",
    "/ricerca-studio": "/app-v2/ricerca-studio",
    "/scadenziario": "/app-v2/scadenziario",
    "/scadenziario/nuova": "/app-v2/scadenziario/nuova",
    "/sincronizzazione-calendari": "/app-v2/sincronizzazione-calendari",
    "/sito-studio": "/app-v2/sito-studio",
    "/sito-studio/builder": "/app-v2/sito-studio/builder",
    "/sito-studio/contatti": "/app-v2/sito-studio/contatti",
    "/sito-studio/redazione-ai": "/app-v2/sito-studio/redazione-ai",
    "/soggetti": "/app-v2/soggetti",
    "/soggetti/nuovo": "/app-v2/soggetti/nuovo",
    "/statistiche": "/app-v2/statistiche",
    "/strumenti-legali": "/app-v2/strumenti-legali",
    "/strumenti-operativi": "/app-v2/strumenti-operativi",
    "/studio": "/app-v2/studio",
    "/tariffario": "/app-v2/tariffario",
    "/template-atti": "/app-v2/template-atti",
    "/template-atti/catalogo": "/app-v2/template-atti/catalogo",
    "/template-atti/editor": "/app-v2/template-atti/editor",
    "/template-atti/editor-libero": "/app-v2/template-atti/editor-libero",
    "/timesheet": "/app-v2/timesheet",
    "/utenti": "/app-v2/utenti",
    "/utenti/nuovo": "/app-v2/utenti/nuovo",
    "/wizard-pro": "/app-v2/wizard-pro",
    "/workspace-intelligente": "/app-v2/workspace-intelligente",
}

_DYNAMIC_TARGET_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^/agenda/([^/]+)$"), "/app-v2/agenda/{0}"),
    (re.compile(r"^/agenda/([^/]+)/modifica$"), "/app-v2/agenda/{0}/modifica"),
    (re.compile(r"^/clienti/([^/]+)$"), "/app-v2/clienti/{0}"),
    (re.compile(r"^/clienti/([^/]+)/modifica$"), "/app-v2/clienti/{0}/modifica"),
    (re.compile(r"^/email/messaggio/([^/]+)$"), "/app-v2/email/messaggio/{0}"),
    (re.compile(r"^/email-ordinaria/messaggio/([^/]+)$"), "/app-v2/email-ordinaria/messaggio/{0}"),
    (re.compile(r"^/fascicoli/([^/]+)$"), "/app-v2/fascicoli/{0}"),
    (
        re.compile(r"^/fascicoli/([^/]+)/documenti/([^/]+)/editor$"),
        "/app-v2/fascicoli/{0}/documenti/{1}/editor",
    ),
    (re.compile(r"^/messaggi/([^/]+)$"), "/app-v2/messaggi/{0}"),
    (re.compile(r"^/preventivi/conferimento/([^/]+)$"), "/app-v2/preventivi/conferimento/{0}"),
    (re.compile(r"^/scadenziario/([^/]+)$"), "/app-v2/scadenziario/{0}"),
    (re.compile(r"^/scadenziario/([^/]+)/modifica$"), "/app-v2/scadenziario/{0}/modifica"),
    (re.compile(r"^/soggetti/([^/]+)$"), "/app-v2/soggetti/{0}"),
    (re.compile(r"^/soggetti/([^/]+)/modifica$"), "/app-v2/soggetti/{0}/modifica"),
)


@dataclass(frozen=True, slots=True)
class AppV2RedirectDecision:
    allowed: bool
    target: str
    flag_key: str
    reason: str


def _contains_control_chars(value: str) -> bool:
    return any(ord(char) < 32 or ord(char) == 127 for char in value)


def is_safe_internal_path(path: str) -> bool:
    """Accetta solo path relativi interni, mai URL assoluti o protocol-relative."""

    raw = str(path or "").strip()
    if not raw or _contains_control_chars(raw) or "\\" in raw:
        return False
    split = urlsplit(raw)
    if split.scheme or split.netloc or not split.path.startswith("/") or split.path.startswith("//"):
        return False
    if split.fragment:
        return False
    decoded_path = unquote(split.path)
    return ".." not in {part.strip() for part in decoded_path.split("/")}


def _normalise_path(path: str, *, lower: bool = True) -> str:
    split = urlsplit(str(path or "/").strip())
    clean = split.path.rstrip("/") or "/"
    if not clean.startswith("/"):
        clean = "/" + clean
    return clean.lower() if lower else clean


def _safe_segment(segment: str) -> str:
    raw = str(segment or "").strip()
    if not raw or _contains_control_chars(raw) or "/" in raw or "\\" in raw or raw in {".", ".."}:
        return ""
    return quote(raw, safe="")


def _iter_query_items(query_args: Mapping[str, Any] | Any | None) -> Iterable[tuple[str, Any]]:
    if not query_args:
        return ()
    if hasattr(query_args, "lists"):
        pairs: list[tuple[str, Any]] = []
        for key, values in query_args.lists():
            for value in values:
                pairs.append((str(key), value))
        return pairs
    if hasattr(query_args, "items"):
        pairs = []
        for key, value in query_args.items():
            if isinstance(value, (list, tuple)):
                pairs.extend((str(key), item) for item in value)
            else:
                pairs.append((str(key), value))
        return pairs
    return ()


def sanitize_query_params(
    query_args: Mapping[str, Any] | Any | None,
    *,
    allowed_query_params: Iterable[str] | None = None,
) -> list[tuple[str, str]]:
    """Preserva solo parametri innocui e non autorizzativi."""

    allowed = {item.lower() for item in (allowed_query_params or SAFE_QUERY_PARAMS)}
    sanitized: list[tuple[str, str]] = []
    for raw_key, raw_value in _iter_query_items(query_args):
        key = str(raw_key or "").strip().lower()
        if not key or key in UNSAFE_QUERY_PARAMS or key not in allowed:
            continue
        value = str(raw_value or "").strip()
        if not value or _contains_control_chars(value):
            continue
        sanitized.append((key, value[:512]))
    return sanitized


def _target_for_legacy_path(legacy_path: str) -> str:
    path = _normalise_path(legacy_path, lower=False)
    lookup_path = path.lower()
    target = LEGACY_TO_APP_V2_TARGETS.get(lookup_path)
    if target:
        return target
    for pattern, template in _DYNAMIC_TARGET_RULES:
        match = pattern.match(lookup_path)
        if not match:
            continue
        original_match = re.match(pattern.pattern, path, re.IGNORECASE)
        groups = original_match.groups() if original_match else match.groups()
        encoded = [_safe_segment(item) for item in groups]
        if all(encoded):
            return template.format(*encoded)
    return ""


def build_app_v2_path(
    legacy_path: str,
    query_args: Mapping[str, Any] | Any | None = None,
    *,
    target: str = "",
    allowed_query_params: Iterable[str] | None = None,
) -> str:
    """Costruisce un target App V2 interno, rimuovendo query non sicure."""

    raw_target = target or _target_for_legacy_path(legacy_path)
    if not raw_target or not is_safe_internal_path(raw_target):
        return ""

    split = urlsplit(raw_target)
    target_pairs = parse_qsl(split.query, keep_blank_values=False)
    target_keys = {key.lower() for key, _value in target_pairs}
    incoming_pairs = [
        (key, value)
        for key, value in sanitize_query_params(query_args, allowed_query_params=allowed_query_params)
        if key not in target_keys
    ]
    query = urlencode(target_pairs + incoming_pairs, doseq=True)
    return urlunsplit(("", "", split.path, query, ""))


def get_legacy_fallback_path(
    legacy_path: str,
    query_args: Mapping[str, Any] | Any | None = None,
    *,
    allowed_query_params: Iterable[str] | None = None,
) -> str:
    """Restituisce il path legacy ripulito per fallback controllati."""

    path = _normalise_path(legacy_path, lower=False)
    if not is_safe_internal_path(path):
        return "/"
    query = urlencode(sanitize_query_params(query_args, allowed_query_params=allowed_query_params), doseq=True)
    return f"{path}?{query}" if query else path


def should_redirect_to_app_v2(
    legacy_path: str,
    query_args: Mapping[str, Any] | Any | None = None,
    *,
    config: Mapping[str, Any] | None = None,
    allowed_query_params: Iterable[str] | None = None,
) -> AppV2RedirectDecision:
    """Decide se un redirect legacy -> App V2 e' consentito.

    Il redirect e' permesso solo quando:
    - il path legacy ha un target esplicito e sicuro;
    - il target resta interno a `/app-v2`;
    - esiste un feature flag App V2 noto;
    - il flag e' attivo nel config/ambiente corrente.
    """

    target = build_app_v2_path(
        legacy_path,
        query_args,
        allowed_query_params=allowed_query_params,
    )
    if not target:
        return AppV2RedirectDecision(False, "", "", "mapping assente o target non sicuro")
    if not (target == "/app-v2" or target.startswith("/app-v2/")):
        return AppV2RedirectDecision(False, "", "", "target fuori dalla shell App V2")
    flag_key = app_v2_route_flag_for_path(target)
    if not flag_key:
        return AppV2RedirectDecision(False, target, "", "feature flag non risolto")
    if not is_feature_enabled(flag_key, config):
        return AppV2RedirectDecision(False, target, flag_key, "feature flag spento")
    return AppV2RedirectDecision(True, target, flag_key, "feature flag attivo")
