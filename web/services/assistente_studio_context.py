"""Contesto consultivo e governabile di Lex per i moduli dello studio."""

from __future__ import annotations

from datetime import datetime, timedelta
import re
from typing import Any

from flask import current_app, g

from lex.research import build_request_profile_prompt, classify_request
from lex.research.query_helpers import extract_entity_hint, is_exact_legal_reference_query
from lex.research.source_policy import evaluate_source_row, summarize_evaluated_sources
from pct.config_studio import GestioneConfigStudio
from pct.legal_intelligence import fonti_per_query, motori_per_query
from pct.portale import GestionePortale
from pct.runtime_env import is_managed_cloud_runtime
from pct.strumenti_legali import GestioneStrumentiLegali
from pct.tariffario import (
    tutte_le_complessita,
    tutte_le_fasi,
    tutte_le_materie,
    tutti_i_gradi,
)
from pct.template_atti import GestioneTemplateAtti
from web.helpers import (
    get_agenda,
    get_applicazioni_repository,
    get_clienti,
    get_fatturazione,
    get_fascicoli,
    get_giurisprudenza,
    get_legal_intelligence,
    get_preventivi,
    get_scadenziario,
    get_soggetti,
)
from web.services.assistente_context_cache import (
    build_file_fingerprint,
    cached_compute,
    question_signature,
)
from web.services.assistente_competencies import (
    build_competence_context_hints,
    resolve_competence_labels,
    resolve_competence_section_titles,
)
from web.services.assistente_conversation_focus import resolve_conversation_focus
from web.services.assistente_execution_policy import build_execution_policy
from lex.guards.legal_reference_guard import (
    build_case_law_guard_prompt,
    collect_verified_legal_references,
)
from web.services.assistente_live_web import build_live_official_web_context
from lex.memory.web_execution import is_web_execution_request
from lex.providers.local_ai_service import get_local_ai_service
from web.services.legal_update_surface import build_legal_update_pipeline_runtime


_DEFAULT_WEB_SOURCE_IDS: tuple[str, ...] = (
    "pst_giustizia",
    "normattiva",
    "cassazione",
    "agenzia_entrate",
)

_DEFAULT_DETAIL_SECTION_TITLES: tuple[str, ...] = (
    "Fascicoli",
    "Clienti",
    "Agenda",
    "Scadenziario",
    "Template atti",
)

_CHAT_DETAIL_SECTION_TITLES: tuple[str, ...] = (
    "Fascicoli",
    "Clienti",
    "Agenda",
    "Scadenziario",
)

_SECTION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Centro Servizi Telematici": ("pst", "polisweb", "pdp", "pat", "ptt", "sigit", "telematico", "deposito", "busta", "pec", "wsdl", "xsd", "reginde"),
    "Fascicoli": ("fascicolo", "fascicoli", "rg", "pratica", "causa", "giudice", "udienza"),
    "Clienti": ("cliente", "clienti", "assistito", "anagrafica", "anagrafiche"),
    "Agenda": ("agenda", "appuntamento", "calendario", "riunione", "udienza", "promemoria"),
    "Soggetti": ("soggetto", "soggetti", "parte", "parti", "difensore", "codifensore", "domiciliatario"),
    "Scadenziario": ("scadenza", "scadenze", "termine", "termini", "promemoria", "attivita"),
    "Template atti": ("template", "atto", "atti", "ricorso", "comparsa", "citazione", "bozza"),
    "Tariffario": ("tariffa", "tariffario", "compenso", "onorario", "parametri", "parcella"),
    "Preventivi": ("preventivo", "preventivi", "offerta", "incarico"),
    "Fatturazione": ("fattura", "fatturazione", "parcella", "saldo", "pagamento"),
    "Aggiornamenti legali": ("aggiornamento", "aggiornamenti", "novita", "news giuridiche", "gazzetta", "normattiva", "eur-lex", "cassazione", "corte costituzionale", "prassi"),
    "Ricerca legale e fonti web": ("norma", "normativa", "legge", "decreto", "articolo", "aggiornata", "fonte"),
    "Archivio sentenze": ("sentenza", "sentenze", "massima", "giurisprudenza", "cassazione", "tar", "cds"),
    "Strumenti legali": ("strumento", "strumenti", "interessi", "contributo", "pignoramento", "credito", "ctu"),
    "Applicazioni": ("applicazione", "applicazioni", "modulo", "moduli", "workspace"),
    "RAG documentale locale": ("documento", "documenti", "allegato", "allegati", "pdf", "verbale"),
}

_LIVE_WEB_KEYWORDS: tuple[str, ...] = (
    "aggiorn",
    "oggi",
    "corrente",
    "ultima",
    "ultime",
    "recent",
    "norma",
    "normativa",
    "legge",
    "decreto",
    "ministero",
    "pst",
    "pdp",
    "pat",
    "pec",
    "cassazione",
    "tar",
    "consiglio di stato",
    "agenzia entrate",
)

_CONTEXT_CACHE_VERSION = "lex-context-v2"
_BASE_SECTION_TITLES: frozenset[str] = frozenset(
    {"Impostazioni studio", "PEC e canali email", "Quadro operativo"}
)
_SECTION_CACHE_TTLS: dict[str, int] = {
    "Impostazioni studio": 180,
    "PEC e canali email": 180,
    "Quadro operativo": 90,
    "Centro Servizi Telematici": 180,
    "Fascicoli": 90,
    "Clienti": 90,
    "Agenda": 60,
    "Soggetti": 90,
    "Scadenziario": 60,
    "Template atti": 180,
    "Tariffario": 300,
    "Preventivi": 90,
    "Fatturazione": 90,
    "Aggiornamenti legali": 120,
    "Ricerca legale e fonti web": 180,
    "Archivio sentenze": 120,
    "Strumenti legali": 180,
    "Applicazioni": 300,
    "RAG documentale locale": 45,
    "Verifica live fonti ufficiali web": 300,
}
_SECTION_DEPENDENCY_KEYS: dict[str, tuple[str, ...]] = {
    "Impostazioni studio": ("STUDIO_CONFIG",),
    "PEC e canali email": ("STUDIO_CONFIG",),
    "Quadro operativo": ("CLIENTI_DB", "FASCICOLI_DB", "AGENDA_DB", "SCADENZIARIO_DB"),
    "Centro Servizi Telematici": ("LEGAL_INTELLIGENCE_DB",),
    "Fascicoli": ("FASCICOLI_DB",),
    "Clienti": ("CLIENTI_DB",),
    "Agenda": ("AGENDA_DB",),
    "Soggetti": ("SOGGETTI_DB", "SOGGETTI_PARTI_DB"),
    "Scadenziario": ("SCADENZIARIO_DB",),
    "Template atti": ("TEMPLATE_ATTI_DB",),
    "Preventivi": ("PREVENTIVI_DB",),
    "Fatturazione": ("FATTURAZIONE_DB",),
    "Aggiornamenti legali": ("LEGAL_UPDATES_DB", "LEGAL_INTELLIGENCE_DB"),
    "Ricerca legale e fonti web": ("LEGAL_INTELLIGENCE_DB", "NORMATIVE_TABLES_DB"),
    "Archivio sentenze": ("GIURISPRUDENZA_DB",),
    "Strumenti legali": ("NORMATIVE_TABLES_DB",),
    "Applicazioni": ("STUDIO_CONFIG",),
    "RAG documentale locale": ("LOCAL_AI_DB",),
}


def _cfg_data_path(key: str) -> str:
    paths = getattr(g, "data_paths", {}) or {}
    return str(paths.get(key) or current_app.config.get(key) or "").strip()


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _truncate(value: Any, limit: int = 180) -> str:
    text = _clean_spaces(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _query_terms(question: str) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for raw in str(question or "").lower().replace("/", " ").replace("-", " ").split():
        term = "".join(ch for ch in raw if ch.isalnum())
        if len(term) < 3 or term in seen:
            continue
        seen.add(term)
        terms.append(term)
    return terms


def _score_parts(terms: list[str], *parts: Any) -> int:
    haystack = _clean_spaces(" ".join(str(part or "") for part in parts)).lower()
    if not haystack or not terms:
        return 0
    return sum(1 for term in terms if term in haystack)


def _select_ranked(rows: list[Any], score_fn, limit: int = 4) -> list[Any]:
    scored: list[tuple[int, int, Any]] = []
    for index, row in enumerate(rows):
        score = int(score_fn(row) or 0)
        scored.append((score, -index, row))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    relevant = [row for score, _index, row in scored if score > 0][:limit]
    if relevant:
        return relevant
    return rows[:limit]


def _source(citation: str, text: str, *, source_id: str = "", title: str = "") -> dict[str, Any]:
    return {
        "id": source_id or citation.lower().replace(" ", "-"),
        "title": title or citation,
        "citation": citation,
        "text": _truncate(text, 420),
    }


def _append_section(
    sections: list[str],
    title: str,
    lines: list[str],
) -> None:
    content = [line for line in lines if _clean_spaces(line)]
    if not content:
        return
    sections.extend(
        [
            "",
            f"=== {title.upper()} ===",
            *content,
        ]
    )


def _keyword_score(question: str, keywords: tuple[str, ...]) -> int:
    haystack = _clean_spaces(question).lower()
    if not haystack:
        return 0
    return sum(1 for keyword in keywords if keyword and keyword in haystack)


def _contains_query_token(question: str, token: str) -> bool:
    haystack = _clean_spaces(question).lower()
    needle = _clean_spaces(token).lower()
    if not haystack or not needle:
        return False
    if len(needle) <= 4 and needle.isalpha():
        return re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", haystack) is not None
    return needle in haystack


def _select_detail_sections(question: str) -> set[str]:
    text = _clean_spaces(question).lower()
    if not text:
        return set(_DEFAULT_DETAIL_SECTION_TITLES)

    scored = [
        (title, _keyword_score(text, keywords))
        for title, keywords in _SECTION_KEYWORDS.items()
    ]
    selected = [title for title, score in scored if score > 0]
    if not selected:
        return set(_DEFAULT_DETAIL_SECTION_TITLES)

    selected.sort(key=lambda title: _keyword_score(text, _SECTION_KEYWORDS.get(title, ())), reverse=True)
    return set(selected[:5])


def _select_detail_sections_for_chat(question: str) -> set[str]:
    text = _clean_spaces(question).lower()
    if not text:
        return set(_CHAT_DETAIL_SECTION_TITLES)

    scored = [
        (title, _keyword_score(text, keywords))
        for title, keywords in _SECTION_KEYWORDS.items()
        if title != "Ricerca legale e fonti web"
    ]
    selected = [title for title, score in scored if score > 0]
    if not selected:
        return set(_CHAT_DETAIL_SECTION_TITLES)

    selected.sort(key=lambda title: _keyword_score(text, _SECTION_KEYWORDS.get(title, ())), reverse=True)
    return set(selected[:4])


def _should_include_live_web(question: str, *, chat_mode: bool = False) -> bool:
    text = _clean_spaces(question).lower()
    if not text:
        return False
    if chat_mode and is_web_execution_request(text):
        return True
    if chat_mode:
        if any(
            _contains_query_token(text, phrase)
            for phrase in (
                "cerca sul web",
                "sul web",
                "fonte ufficiale",
                "fonti ufficiali",
                "verifica la normativa",
                "verifica normativa",
                "verifica la legge",
                "aggiornamento",
                "aggiornata",
                "aggiornato",
                "ultima sentenza",
                "ultime sentenze",
                "ultima normativa",
                "ultime novita",
                "oggi",
            )
        ):
            return True
        has_recency = any(_contains_query_token(text, token) for token in ("ultima", "ultime", "recente", "recenti", "oggi"))
        has_legal_lookup = any(
            _contains_query_token(text, token)
            for token in ("sentenza", "sentenze", "normativa", "legge", "decreto", "provvedimento", "massima")
        )
        return has_recency and has_legal_lookup
    return any(_contains_query_token(text, keyword) for keyword in _LIVE_WEB_KEYWORDS)


def _dedupe_sources(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for row in rows:
        identifier = str(row.get("id") or row.get("citation") or "").strip()
        if not identifier or identifier in seen_ids:
            continue
        seen_ids.add(identifier)
        deduped.append(row)
    return deduped


def _is_generic_local_source(source_id: str) -> bool:
    source_id = str(source_id or "").strip().lower()
    return source_id.startswith("studio:") or source_id in {
        "agenda:prossimi",
        "scadenziario:imminenti",
        "tariffario:parametri",
    }


def _has_specific_local_context(rows: list[dict[str, Any]]) -> bool:
    for row in rows:
        source_id = str(row.get("id") or "").strip()
        if not source_id:
            continue
        if source_id.startswith("live-web:"):
            continue
        if _is_generic_local_source(source_id):
            continue
        return True
    return False


def _is_operational_only_query(question: str) -> bool:
    text = _clean_spaces(question).lower()
    if not text:
        return False
    operational_keywords = (
        "udienza",
        "udienze",
        "agenda",
        "appuntamento",
        "appuntamenti",
        "scadenza",
        "scadenze",
        "fascicolo",
        "fascicoli",
        "cliente",
        "clienti",
        "preventivo",
        "preventivi",
        "fattura",
        "fatture",
        "parcella",
        "parcelle",
    )
    legal_web_keywords = (
        "norma",
        "normativa",
        "legge",
        "decreto",
        "sentenza",
        "sentenze",
        "cassazione",
        "tar",
        "consiglio di stato",
        "eur-lex",
        "curia",
        "mediazione",
        "pec",
        "firma",
        "pst",
        "pdp",
        "pat",
        "reginde",
    )
    has_operational = any(_contains_query_token(text, token) for token in operational_keywords)
    has_legal_web = any(_contains_query_token(text, token) for token in legal_web_keywords)
    return has_operational and not has_legal_web


def _is_exact_legal_reference_query(text: str) -> bool:
    """True se la query contiene un riferimento esatto a sentenza/ordinanza con numero."""
    return is_exact_legal_reference_query(text)


def _should_force_web_fallback(
    question: str,
    *,
    local_sources: list[dict[str, Any]],
    chat_mode: bool,
) -> bool:
    text = _clean_spaces(question).lower()
    if not text:
        return False
    if chat_mode and _is_operational_only_query(text):
        return False

    # Se è un riferimento legale esatto (sentenza n. XXXX) → web obbligatorio
    # anche se esiste contesto locale (es. fascicolo), perché la fonte ufficiale
    # deve essere verificata su cortedicassazione.it o normattiva.it
    if _is_exact_legal_reference_query(text):
        legal_triggers_exact = ("sentenza", "ordinanza", "decreto", "massima", "cassazione")
        if any(_contains_query_token(text, token) for token in legal_triggers_exact):
            return True

    if _has_specific_local_context(local_sources):
        return False

    legal_triggers = (
        "norma",
        "normativa",
        "legge",
        "decreto",
        "sentenza",
        "sentenze",
        "cassazione",
        "tar",
        "consiglio di stato",
        "giurisprudenza",
        "massima",
        "pec",
        "firma",
        "pst",
        "pdp",
        "pat",
        "reginde",
        "mediazione",
        "fatturapa",
        "agenzia entrate",
        "ultima",
        "ultime",
        "oggi",
        "aggiornato",
        "aggiornata",
        "aggiornamento",
    )
    return any(_contains_query_token(text, token) for token in legal_triggers)


def _load_studio_config() -> Any | None:
    try:
        return GestioneConfigStudio(current_app.config["STUDIO_CONFIG"]).config
    except Exception:
        return None


def _tenant_scope() -> str:
    tenant = getattr(g, "tenant", None)
    return _clean_spaces(getattr(tenant, "slug", "")) or "default"


def _section_dependency_paths(title: str) -> list[str]:
    return [
        path
        for key in _SECTION_DEPENDENCY_KEYS.get(title, ())
        if (path := _cfg_data_path(key))
    ]


def _section_query_signature(title: str, question: str) -> str:
    if title in _BASE_SECTION_TITLES:
        return "__base__"
    return question_signature(question, limit=10)


def _cached_section_payload(title: str, question: str, builder) -> tuple[list[str], list[dict[str, Any]]]:
    fingerprint = build_file_fingerprint(_section_dependency_paths(title))
    payload = cached_compute(
        "lex-section",
        (
            _CONTEXT_CACHE_VERSION,
            _tenant_scope(),
            title,
            _section_query_signature(title, question),
            fingerprint,
        ),
        _SECTION_CACHE_TTLS.get(title, 90),
        lambda: (
            lambda lines, section_sources: {
                "lines": lines or [],
                "sources": section_sources or [],
            }
        )(*builder()),
    )
    return list(payload.get("lines") or []), list(payload.get("sources") or [])


def _format_date_italian(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    for sample in (text[:19], text[:10], text):
        try:
            parsed = datetime.fromisoformat(sample)
            return parsed.strftime("%d/%m/%Y %H:%M") if len(sample) > 10 else parsed.strftime("%d/%m/%Y")
        except ValueError:
            continue
    return text


def _studio_profile_lines() -> list[str]:
    config = _load_studio_config()
    studio_name = current_app.config.get("STUDIO_NOME") or "Studio Legale"
    avvocato = current_app.config.get("STUDIO_AVVOCATO") or ""
    city = ""
    province = ""
    if config and getattr(config, "studio", None):
        city = _clean_spaces(getattr(config.studio, "city", ""))
        province = _clean_spaces(getattr(config.studio, "province", ""))
        avvocato = avvocato or _clean_spaces(getattr(config.studio, "avvocato", ""))

    location = ", ".join(part for part in [city, province] if part)
    lines = [f"Studio: {studio_name}."]
    if avvocato:
        lines.append(f"Referente professionale: {avvocato}.")
    if location:
        lines.append(f"Presidio territoriale: {location}.")
    lines.append(
        "Lex puo' suggerire su fascicoli, clienti, agenda, scadenziario, documenti, template atti, tariffario, preventivi, fatturazione, ricerca legale, archivio sentenze, strumenti legali e applicazioni."
    )
    lines.append(
        "Lex opera solo come assistente consultivo: non prende decisioni, non autorizza atti, non sostituisce il professionista e non esegue azioni autonome."
    )
    return lines


def _settings_studio_lines() -> tuple[list[str], list[dict[str, Any]]]:
    config = _load_studio_config()
    studio = getattr(config, "studio", None)
    if not studio:
        return (
            ["Impostazioni studio non disponibili in questo momento."],
            [],
        )

    address = _clean_spaces(getattr(studio, "indirizzo", ""))
    city = _clean_spaces(getattr(studio, "city", ""))
    province = _clean_spaces(getattr(studio, "province", ""))
    full_address = ", ".join(part for part in [address, city, province] if part)
    phone = _clean_spaces(getattr(studio, "telefono", ""))
    email = _clean_spaces(getattr(studio, "email", ""))
    website = _clean_spaces(getattr(studio, "sito_web", ""))
    vat = _clean_spaces(getattr(studio, "piva", ""))
    tax_code = _clean_spaces(getattr(studio, "cf", ""))

    lines = [
        f"Denominazione studio: {_clean_spaces(getattr(studio, 'nome', 'IUSENTRA')) or 'IUSENTRA'}.",
    ]
    if full_address:
        lines.append(f"Sede operativa: {full_address}.")
    if phone or email:
        recapiti = []
        if phone:
            recapiti.append(f"telefono {phone}")
        if email:
            recapiti.append(f"email {email}")
        lines.append("Recapiti studio: " + ", ".join(recapiti) + ".")
    if website:
        lines.append(f"Sito web studio: {website}.")
    if vat or tax_code:
        fiscal = []
        if vat:
            fiscal.append(f"P.IVA {vat}")
        if tax_code:
            fiscal.append(f"CF {tax_code}")
        lines.append("Dati fiscali studio: " + ", ".join(fiscal) + ".")

    sources = [
        _source(
            "Impostazioni studio",
            " ".join(lines),
            source_id="studio:impostazioni",
            title="Impostazioni studio",
        )
    ]
    return lines, sources


def _pec_lines() -> tuple[list[str], list[dict[str, Any]]]:
    config = _load_studio_config()
    pec = getattr(config, "pec", None)
    smtp = getattr(config, "smtp", None)
    if not pec and not smtp:
        return (
            ["Configurazione PEC e canali email non disponibile in questo momento."],
            [],
        )

    lines: list[str] = []
    if pec:
        pec_address = _clean_spaces(getattr(pec, "indirizzo", ""))
        if pec_address:
            lines.append(f"PEC studio configurata: {pec_address}.")
        else:
            lines.append("PEC studio non ancora configurata.")
        pec_mode = "SSL attivo" if bool(getattr(pec, "use_ssl", False)) else "SSL disattivo"
        lines.append(
            "Canale PEC: "
            f"SMTP {getattr(pec, 'smtp_host', '') or 'n.d.'}:{getattr(pec, 'smtp_port', '') or 'n.d.'}, "
            f"IMAP {getattr(pec, 'imap_host', '') or 'n.d.'}:{getattr(pec, 'imap_port', '') or 'n.d.'}, "
            f"{pec_mode}."
        )
        if _clean_spaces(getattr(pec, "password", "")):
            lines.append("Password PEC configurata e protetta: mai riportata nel contesto di Lex.")

    if smtp:
        smtp_host = _clean_spaces(getattr(smtp, "host", ""))
        smtp_from = _clean_spaces(getattr(smtp, "from_address", "")) or _clean_spaces(getattr(smtp, "username", ""))
        if smtp_host or smtp_from:
            tls_mode = "TLS attivo" if bool(getattr(smtp, "use_tls", False)) else "TLS disattivo"
            lines.append(
                "Email SMTP studio: "
                f"host {smtp_host or 'n.d.'}:{getattr(smtp, 'port', '') or 'n.d.'}, "
                f"mittente {smtp_from or 'n.d.'}, "
                f"{tls_mode}."
            )

    sources = [
        _source(
            "PEC e canali email",
            " ".join(lines),
            source_id="studio:pec",
            title="PEC e canali email",
        )
    ]
    return lines, sources


def _operational_lines() -> tuple[list[str], list[dict[str, Any]]]:
    sources: list[dict[str, Any]] = []
    clienti_stats = get_clienti().statistiche()
    fascicoli = get_fascicoli().tutti()
    agenda = get_agenda()
    scadenziario = get_scadenziario()
    now = datetime.now()
    upcoming_apps = [row for row in agenda.tutti() if row.data_ora_dt >= now][:5]
    urgent_deadlines = scadenziario.imminenti(7)[:5]

    lines = [
        f"Clienti censiti: {clienti_stats.get('totale', 0)}.",
        f"Fascicoli aperti: {len(fascicoli)}.",
        f"Appuntamenti imminenti 7 giorni: {len(upcoming_apps)}.",
        f"Scadenze imminenti 7 giorni: {len(urgent_deadlines)}.",
    ]
    if upcoming_apps:
        preview = "; ".join(
            f"{row.titolo} ({_format_date_italian(row.data_ora)})"
            for row in upcoming_apps[:3]
        )
        lines.append(f"Agenda prossima: {preview}.")
        sources.append(
            _source(
                "Agenda studio",
                preview,
                source_id="agenda:prossimi",
                title="Agenda imminente",
            )
        )
    if urgent_deadlines:
        preview = "; ".join(
            f"{row.titolo} ({_format_date_italian(row.data_scadenza)})"
            for row in urgent_deadlines[:3]
        )
        lines.append(f"Scadenze presidiate: {preview}.")
        sources.append(
            _source(
                "Scadenziario studio",
                preview,
                source_id="scadenziario:imminenti",
                title="Scadenze imminenti",
            )
        )
    return lines, sources


def _extract_entity_hint_from_question(question: str) -> dict[str, str]:
    """Estrae CF, PIVA, email dalla domanda per ricerca mirata del cliente."""
    return extract_entity_hint(question)


def _clienti_lines(question: str) -> tuple[list[str], list[dict[str, Any]]]:
    gestore = get_clienti()
    all_rows = gestore.tutti()
    stats = gestore.statistiche()

    # Entity extraction: priorità a CF/PIVA/email se presenti nella domanda
    hints = _extract_entity_hint_from_question(question)
    matched_by_entity: list[Any] = []
    if hints["codice_fiscale"]:
        matched_by_entity = [r for r in all_rows if getattr(r, "codice_fiscale", "").upper() == hints["codice_fiscale"]]
    elif hints["partita_iva"]:
        matched_by_entity = [r for r in all_rows if getattr(r, "partita_iva", "") == hints["partita_iva"]]
    elif hints["email"]:
        matched_by_entity = [
            r for r in all_rows
            if hints["email"] in (getattr(getattr(r, "recapiti", None), "email", "") or "").lower()
            or hints["email"] in (getattr(getattr(r, "recapiti", None), "pec", "") or "").lower()
        ]

    if matched_by_entity:
        selected = matched_by_entity[:8]
    else:
        text_matches = gestore.cerca(question) if _clean_spaces(question) else []
        selected = text_matches[:8] if text_matches else all_rows[:8]

    lines = [
        f"Anagrafica clienti: {stats.get('totale', len(all_rows))} soggetti censiti, {stats.get('con_procedimenti_attivi', 0)} con procedimenti attivi.",
    ]
    if selected:
        lines.append(
            "Clienti rilevanti: "
            + "; ".join(
                _truncate(
                    f"{row.nome_completo} ({getattr(getattr(row, 'stato', None), 'value', '') or 'stato n.d.'})",
                    90,
                )
                for row in selected
            )
            + "."
        )
    sources = []
    for row in selected:
        rec = getattr(row, "recapiti", None)
        email_val = getattr(rec, "email", "") or ""
        pec_val = getattr(rec, "pec", "") or ""
        telefono_val = getattr(rec, "telefono", "") or ""
        cf_val = getattr(row, "codice_fiscale", "") or ""
        piva_val = getattr(row, "partita_iva", "") or ""
        referente = row.avvocato_referente or "n.d."
        tipo_val = getattr(getattr(row, "tipo", None), "value", "") or ""
        stato_val = getattr(getattr(row, "stato", None), "value", "") or ""
        text_parts = [
            f"Tipo: {tipo_val}." if tipo_val else "",
            f"Stato: {stato_val}." if stato_val else "",
            f"Referente: {referente}.",
            f"CF: {cf_val}." if cf_val else "",
            f"P.IVA: {piva_val}." if piva_val else "",
            f"Email: {email_val}." if email_val else "",
            f"PEC: {pec_val}." if pec_val else "",
            f"Tel: {telefono_val}." if telefono_val else "",
        ]
        source_text = " ".join(p for p in text_parts if p)
        sources.append(
            _source(
                f"Cliente - {row.nome_completo}",
                source_text,
                source_id=f"cliente:{row.id}",
                title=row.nome_completo,
            )
        )
    return lines, sources


def _fascicoli_lines(question: str) -> tuple[list[str], list[dict[str, Any]]]:
    gestore = get_fascicoli()
    rows = gestore.cerca(question) if _clean_spaces(question) else gestore.tutti()
    selected = rows[:4]
    lines = [f"Fascicoli gestiti: {len(gestore.tutti())} attivi in archivio operativo."]
    if selected:
        lines.append(
            "Fascicoli rilevanti: "
            + "; ".join(
                _truncate(
                    f"{row.titolo} (RG {row.numero_rg or '-'}{('/' + str(row.anno_rg)) if getattr(row, 'anno_rg', None) else ''}, {getattr(getattr(row, 'stato', None), 'value', '') or 'stato n.d.'})",
                    110,
                )
                for row in selected
            )
            + "."
        )
    sources = [
        _source(
            f"Fascicolo - {row.titolo}",
            f"RG {row.numero_rg or '-'}{('/' + str(row.anno_rg)) if getattr(row, 'anno_rg', None) else ''}. Tribunale: {row.tribunale or 'n.d.'}. Oggetto: {row.oggetto or 'n.d.'}.",
            source_id=f"fascicolo:{row.id}",
            title=row.titolo,
        )
        for row in selected
    ]
    return lines, sources


def _agenda_lines(question: str) -> tuple[list[str], list[dict[str, Any]]]:
    agenda = get_agenda()
    now = datetime.now()
    horizon = now.date() + timedelta(days=21)
    all_rows = [row for row in agenda.tutti() if row.data_ora_dt.date() <= horizon]
    terms = _query_terms(question)
    selected = _select_ranked(
        all_rows,
        lambda row: _score_parts(terms, row.titolo, row.note, row.cliente, row.procedimento, row.tribunale),
        limit=4,
    )
    lines = [
        f"Agenda: {agenda.statistiche().get('totale', len(agenda.tutti()))} appuntamenti totali, {len(all_rows)} nei prossimi 21 giorni.",
    ]
    if selected:
        lines.append(
            "Appuntamenti utili: "
            + "; ".join(
                _truncate(
                    f"{row.titolo} il {_format_date_italian(row.data_ora)} con {row.cliente or 'cliente n.d.'}",
                    110,
                )
                for row in selected
            )
            + "."
        )
    sources = [
        _source(
            f"Agenda - {row.titolo}",
            f"Quando: {_format_date_italian(row.data_ora)}. Luogo: {row.luogo or 'n.d.'}. Cliente: {row.cliente or 'n.d.'}. Procedimento: {row.procedimento or 'n.d.'}.",
            source_id=f"agenda:{row.id}",
            title=row.titolo,
        )
        for row in selected
    ]
    return lines, sources


def _soggetti_lines(question: str) -> tuple[list[str], list[dict[str, Any]]]:
    gestore = get_soggetti()
    all_rows = gestore.tutti()
    selected = gestore.cerca(q=question)[:4] if _clean_spaces(question) else all_rows[:4]
    lines = [f"Soggetti e parti del procedimento: {len(all_rows)} anagrafiche disponibili."]
    if selected:
        lines.append(
            "Soggetti rilevanti: "
            + "; ".join(
                _truncate(
                    f"{row.nome_completo} ({getattr(getattr(row, 'tipo', None), 'value', '') or row.qualifica or 'qualifica n.d.'})",
                    100,
                )
                for row in selected
            )
            + "."
        )
    sources = [
        _source(
            f"Soggetto - {row.nome_completo}",
            f"Tipo: {getattr(getattr(row, 'tipo', None), 'value', '') or 'n.d.'}. Qualifica: {row.qualifica or 'n.d.'}. Identificativo: {row.identificativo or 'n.d.'}.",
            source_id=f"soggetto:{row.id}",
            title=row.nome_completo,
        )
        for row in selected
    ]
    return lines, sources


def _scadenziario_lines(question: str) -> tuple[list[str], list[dict[str, Any]]]:
    gestore = get_scadenziario()
    stats = gestore.statistiche()
    rows = gestore.imminenti(14)
    terms = _query_terms(question)
    selected = _select_ranked(
        rows,
        lambda row: _score_parts(terms, row.titolo, row.descrizione, row.judicial_office_name),
        limit=4,
    )
    lines = [
        f"Scadenziario: {stats.get('aperte', 0)} scadenze aperte, {stats.get('critiche', 0)} critiche, {stats.get('imminenti_7gg', 0)} nei prossimi 7 giorni.",
    ]
    if selected:
        lines.append(
            "Scadenze rilevanti: "
            + "; ".join(
                _truncate(
                    f"{row.titolo} ({_format_date_italian(row.data_scadenza)})",
                    100,
                )
                for row in selected
            )
            + "."
        )
    sources = [
        _source(
            f"Scadenza - {row.titolo}",
            f"Data: {_format_date_italian(row.data_scadenza)}. Tipo: {getattr(getattr(row, 'tipo', None), 'value', '') or 'n.d.'}. Priorita: {getattr(getattr(row, 'priorita', None), 'value', '') or 'n.d.'}.",
            source_id=f"scadenza:{row.id}",
            title=row.titolo,
        )
        for row in selected
    ]
    return lines, sources


def _template_atti_lines(question: str) -> tuple[list[str], list[dict[str, Any]]]:
    gestore = GestioneTemplateAtti(_cfg_data_path("TEMPLATE_ATTI_DB") or "./template_atti/templates.json")
    rows = gestore.tutti()
    repo_stats = gestore.statistiche_repository()
    selection = gestore.select_best_templates(question or "atto", limit=3)
    best = selection.get("best_template") or {}
    alternatives = list(selection.get("alternatives") or [])
    lines = [
        (
            f"Template atti: {len(rows)} modelli disponibili tra builtin e personalizzati. "
            f"Repository strutturato: {repo_stats.get('template_repository', 0)} template, "
            f"{repo_stats.get('template_fields', 0)} campi guidati, "
            f"{repo_stats.get('template_checks', 0)} controlli."
        ),
    ]
    if best:
        lines.append(
            "Template consigliato: "
            + _truncate(
                f"{best.get('titolo')} ({best.get('area') or best.get('categoria') or 'area n.d.'}; "
                f"{best.get('fase') or 'fase n.d.'}; {best.get('canale_telematico') or 'canale n.d.'})",
                180,
            )
            + "."
        )
        fields = list(best.get("campi_guidati") or [])
        if fields:
            lines.append(
                "Campi da completare: "
                + ", ".join(
                    _truncate(field.get("label") or field.get("name") or "campo", 42)
                    for field in fields[:5]
                )
                + "."
            )
        attachments = list(best.get("allegati_obbligatori") or [])
        if attachments:
            lines.append(
                "Allegati richiesti: "
                + ", ".join(
                    _truncate(item.get("nome") or "allegato", 44)
                    for item in attachments[:4]
                )
                + "."
            )
        checks = list(best.get("controlli_conformita") or [])
        if checks:
            lines.append(
                "Controlli di conformita: "
                + "; ".join(
                    _truncate(item.get("testo") or "controllo", 90)
                    for item in checks[:3]
                )
                + "."
            )
        bindings = list(best.get("bindings") or [])
        if bindings:
            lines.append(
                "Compilatore collegato: "
                + ", ".join(
                    _truncate(item.get("binding_value") or item.get("label") or "binding", 40)
                    for item in bindings[:2]
                )
                + "."
            )
    if alternatives:
        lines.append(
            "Alternative vicine: "
            + "; ".join(
                _truncate(
                    f"{row.get('titolo')} ({row.get('profilo_deposito') or row.get('fase') or 'variante'})",
                    100,
                )
                for row in alternatives
            )
            + "."
        )
    source_rows = [best] if best else []
    source_rows.extend(alternatives)
    sources = []
    for row in source_rows:
        if not row:
            continue
        fields = list(row.get("campi_guidati") or [])
        attachments = list(row.get("allegati_obbligatori") or [])
        checks = list(row.get("controlli_conformita") or [])
        bindings = list(row.get("bindings") or [])
        text_parts = [
            f"Area: {row.get('area') or 'n.d.'}.",
            f"Categoria: {row.get('categoria') or 'n.d.'}.",
            f"Fase: {row.get('fase') or 'n.d.'}.",
            f"Canale: {row.get('canale_telematico') or 'n.d.'}.",
            f"Profilo deposito: {row.get('profilo_deposito') or 'n.d.'}.",
            f"Descrizione: {row.get('descrizione') or row.get('note') or 'Template operativo disponibile.'}",
        ]
        if fields:
            text_parts.append(
                "Campi guidati: "
                + ", ".join(
                    _truncate(field.get("label") or field.get("name") or "campo", 32)
                    for field in fields[:5]
                )
                + "."
            )
        if attachments:
            text_parts.append(
                "Allegati: "
                + ", ".join(
                    _truncate(item.get("nome") or "allegato", 32)
                    for item in attachments[:4]
                )
                + "."
            )
        if checks:
            text_parts.append(
                "Check: "
                + "; ".join(
                    _truncate(item.get("testo") or "controllo", 72)
                    for item in checks[:3]
                )
                + "."
            )
        if bindings:
            text_parts.append(
                "Binding: "
                + ", ".join(
                    _truncate(item.get("binding_value") or item.get("label") or "binding", 30)
                    for item in bindings[:2]
                )
                + "."
            )
        source_row = _source(
            f"Template atti - {row.get('titolo')}",
            " ".join(text_parts),
            source_id=f"template:{row.get('template_id')}",
            title=row.get("titolo") or "Template atto",
        )
        source_row["template_fields"] = fields
        source_row["template_checks"] = checks
        source_row["template_required_attachments"] = attachments
        source_row["template_bindings"] = bindings
        source_row["template_id"] = row.get("template_id") or ""
        source_row["template_match_score"] = int(row.get("match_score") or 0)
        sources.append(source_row)
    return lines, sources


def _tariffario_lines(question: str) -> tuple[list[str], list[dict[str, Any]]]:
    materie = [str(item.value) for item in tutte_le_materie()]
    gradi = [str(item.value) for item in tutti_i_gradi()]
    fasi = [str(item.value) for item in tutte_le_fasi()]
    complessita = [str(item.value) for item in tutte_le_complessita()]
    terms = _query_terms(question)
    selected_materie = _select_ranked(materie, lambda row: _score_parts(terms, row), limit=5)
    lines = [
        "Tariffario: supporto consultivo su compensi e parametri forensi, senza determinazione automatica finale.",
        f"Materie disponibili: {', '.join(selected_materie or materie[:5])}.",
        f"Gradi: {', '.join(gradi[:4])}. Fasi: {', '.join(fasi[:5])}. Complessita: {', '.join(complessita[:3])}.",
    ]
    sources = [
        _source(
            "Tariffario forense",
            "Lex puo' suggerire impostazione di materia, grado, fasi e complessita, ma il compenso finale resta sempre da validare dal professionista.",
            source_id="tariffario:parametri",
            title="Parametri tariffario",
        )
    ]
    return lines, sources


def _preventivi_lines(question: str) -> tuple[list[str], list[dict[str, Any]]]:
    gestore = get_preventivi()
    payload = gestore.repository_payload()
    stats = gestore.statistiche_repository()
    selection = gestore.select_best_preventivi_runtime(question, limit=3)
    practice_selection = gestore.select_best_pratiche_preventivo(question, limit=3)
    rules = list(payload.get("rules") or [])
    formula_rules = [row for row in rules if _clean_spaces(row.get("category")) == "formula"]
    workflow_rules = [row for row in rules if _clean_spaces(row.get("category")) == "workflow"]
    field_labels = {
        row.get("field_name"): row.get("label") or row.get("field_name")
        for row in (payload.get("field_map") or {}).get("preventivo", [])
    }
    conferimenti_by_preventivo = {
        _clean_spaces(row.get("id_preventivo")): row
        for row in (payload.get("conferimenti") or [])
        if _clean_spaces(row.get("id_preventivo"))
    }
    best = selection.get("best_preventivo")
    practice = practice_selection.get("best_practice")
    lines = [
        "Repository preventivi strutturato: "
        f"{stats.get('preventivi_workflow_states', 0)} stati workflow, "
        f"{stats.get('preventivi_field_map', 0)} campi mappati, "
        f"{stats.get('preventivi_rules', 0)} regole deterministiche, "
        f"{stats.get('preventivi_practice_catalog', 0)} pratiche wizard, "
        f"{stats.get('preventivi_records', 0)} preventivi runtime e "
        f"{stats.get('conferimenti_records', 0)} conferimenti runtime."
    ]
    if formula_rules:
        lines.append(
            "Regola di calcolo: "
            + "; ".join(
                _truncate(
                    f"{row.get('title')}: {row.get('formula') or row.get('operational_text')}",
                    120,
                )
                for row in formula_rules[:3]
            )
            + "."
        )
    if workflow_rules:
        preventivo_vs_conferimento = next(
            (
                row
                for row in workflow_rules
                if _clean_spaces(row.get("rule_code")) == "workflow_preventivo_conferimento"
            ),
            None,
        )
        if preventivo_vs_conferimento:
            lines.append("Distinzione operativa: " + _truncate(preventivo_vs_conferimento.get("operational_text"), 180) + ".")
    if best:
        conferimento = conferimenti_by_preventivo.get(_clean_spaces(best.get("preventivo_id")))
        lines.append(
            "Preventivo rilevante: "
            + _truncate(
                f"{best.get('numero')} - {best.get('oggetto')} "
                f"({best.get('stato') or 'n.d.'}, canale {best.get('workflow_channel_label') or 'Studio'})",
                140,
            )
            + "."
        )
        if _clean_spaces(best.get("wizard_step_label")):
            lines.append(f"Step wizard consigliato: {best.get('wizard_step_label')}.")
        missing_labels = [
            field_labels.get(item, item)
            for item in (best.get("campi_mancanti") or [])
            if _clean_spaces(field_labels.get(item, item))
        ]
        if missing_labels:
            lines.append("Campi mancanti: " + "; ".join(_truncate(item, 90) for item in missing_labels[:5]) + ".")
        warnings = [row for row in (best.get("warning") or []) if _clean_spaces(row)]
        if warnings:
            lines.append("Warning operativi: " + "; ".join(_truncate(item, 110) for item in warnings[:4]) + ".")
        if _clean_spaces(best.get("next_action")):
            lines.append(f"Prossima azione: {best.get('next_action')}.")
        if conferimento:
            lines.append(
                "Conferimento collegato: "
                + _truncate(
                    f"{conferimento.get('numero')} "
                    f"({conferimento.get('stato') or 'n.d.'}, canale {conferimento.get('workflow_channel_label') or 'Studio'})",
                    140,
                )
                + "."
            )
    if practice:
        lines.append(
            "Pratica del wizard utile: "
            + _truncate(
                f"{practice.get('label')} ({practice.get('wizard_area') or practice.get('area')}, "
                f"compenso default {practice.get('tipo_compenso_default') or 'n.d.'})",
                150,
            )
            + "."
        )
        if _clean_spaces(practice.get("when_to_use")):
            lines.append("Quando usarla: " + _truncate(practice.get("when_to_use"), 180) + ".")
    sources = [
        _source(
            "Repository preventivi",
            (
                f"Stati workflow: {stats.get('preventivi_workflow_states', 0)}. "
                f"Campi: {stats.get('preventivi_field_map', 0)}. "
                f"Regole: {stats.get('preventivi_rules', 0)}. "
                f"Pratiche wizard: {stats.get('preventivi_practice_catalog', 0)}."
            ),
            source_id="preventivi:repository",
            title="Repository preventivi",
        )
    ]
    if best:
        row = _source(
            f"Preventivo - {best.get('numero')}",
            (
                f"Oggetto: {best.get('oggetto')}. Stato: {best.get('stato') or 'n.d.'}. "
                f"Procedimento: {best.get('tipo_procedimento') or 'n.d.'}. "
                f"Step: {best.get('wizard_step_label') or 'n.d.'}. "
                f"Prossima azione: {best.get('next_action') or 'n.d.'}."
            ),
            source_id=f"preventivo:{best.get('preventivo_id')}",
            title=str(best.get("numero") or "Preventivo"),
        )
        row["preventivo_state"] = best.get("stato") or ""
        row["workflow_channel"] = best.get("workflow_channel") or ""
        row["wizard_step"] = best.get("wizard_step") or ""
        row["wizard_step_label"] = best.get("wizard_step_label") or ""
        row["campi_mancanti"] = list(best.get("campi_mancanti") or [])
        row["warnings"] = list(best.get("warning") or [])
        row["next_action"] = best.get("next_action") or ""
        row["totale"] = float(best.get("totale") or 0.0)
        row["imponibile"] = float(best.get("imponibile") or 0.0)
        row["preventivi_rules"] = rules
        row["preventivi_field_map"] = list((payload.get("field_map") or {}).get("preventivo", []))
        row["preventivi_formula_rules"] = formula_rules
        row["preventivi_workflow_rules"] = workflow_rules
        row["conferimento_collegato"] = conferimenti_by_preventivo.get(_clean_spaces(best.get("preventivo_id"))) or {}
        sources.append(row)
    if practice:
        row = _source(
            f"Pratica preventivo - {practice.get('label')}",
            (
                f"Area: {practice.get('wizard_area') or practice.get('area')}. "
                f"Base normativa: {practice.get('base_normativa') or 'n.d.'}. "
                f"Uso tipico: {practice.get('when_to_use') or practice.get('summary') or 'n.d.'}."
            ),
            source_id=f"preventivo-practice:{practice.get('practice_id')}",
            title=str(practice.get("label") or "Pratica preventivo"),
        )
        row["workflow_steps"] = list(payload.get("wizard_steps") or [])
        row["normative_references"] = list(practice.get("normative_references") or [])
        row["checklist"] = list(practice.get("checklist") or [])
        row["regole_tariffarie"] = list(practice.get("regole_tariffarie") or [])
        sources.append(row)
    return lines, sources


def _fatturazione_lines(question: str) -> tuple[list[str], list[dict[str, Any]]]:
    gestore = get_fatturazione()
    rows = gestore.tutte()
    stats = gestore.statistiche()
    terms = _query_terms(question)
    selected = _select_ranked(
        rows,
        lambda row: _score_parts(terms, row.numero, row.note, row.tipo_procedimento, row.area_pratica),
        limit=4,
    )
    lines = [
        f"Fatturazione: {stats.get('totale_emesse', 0)} parcelle emesse, {stats.get('totale_pagate', 0)} pagate, {stats.get('totale_in_attesa', 0)} in attesa.",
    ]
    if selected:
        lines.append(
            "Parcelle rilevanti: "
            + "; ".join(
                _truncate(
                    f"{row.numero} ({getattr(getattr(row, 'stato', None), 'value', '') or 'stato n.d.'}, totale {getattr(row, 'totale', 0.0):.2f} euro)",
                    110,
                )
                for row in selected
            )
            + "."
        )
    sources = [
        _source(
            f"Parcella - {row.numero}",
            f"Stato: {getattr(getattr(row, 'stato', None), 'value', '') or 'n.d.'}. Emessa il {_format_date_italian(row.data_emissione)}. Totale: {getattr(row, 'totale', 0.0):.2f} euro.",
            source_id=f"parcella:{row.id}",
            title=row.numero,
        )
        for row in selected
    ]
    return lines, sources


def _telematico_lines(question: str) -> tuple[list[str], list[dict[str, Any]]]:
    intelligence = get_legal_intelligence()
    route = intelligence.resolve_telematico_route(question)
    stats = intelligence.statistiche_telematico_repository()
    source_rows = list(route.get("source_rows") or [])
    capability_rows = list(route.get("capability_rows") or [])
    action_rows = list(route.get("action_rows") or [])
    rule_rows = list(route.get("rule_rows") or [])
    monitoring_rows = list(route.get("monitoring_rows") or [])
    xsd_rows = list(route.get("xsd_rows") or [])
    wsdl_rows = list(route.get("wsdl_rows") or [])
    snapshot = dict(route.get("catalog_snapshot") or {})
    lines = [
        (
            "Repository telematico strutturato: "
            f"{stats.get('telematico_methods_repository', 0)} metodi ufficiali, "
            f"{stats.get('telematico_wsdl_modules_repository', 0)} moduli WSDL, "
            f"{stats.get('telematico_xsd_channels_repository', 0)} canali XSD, "
            f"{stats.get('telematico_capabilities_repository', 0)} capability, "
            f"{stats.get('telematico_actions_repository', 0)} azioni operative."
        ),
        "Centro Servizi Telematici: Lex usa catalogo tecnico, monitoraggio ufficiale e capability reali prima di spiegare il passo operativo.",
        "Routing telematico: " + _truncate(route.get("reason") or "routing telematico repository", 180) + ".",
    ]
    if snapshot:
        lines.append(
            _truncate(
                "Catalogo PST: "
                f"versione {snapshot.get('catalog_version') or 'n.d.'}; "
                f"schemi {snapshot.get('schema_version') or 'n.d.'}; "
                f"documentazione servizi web {snapshot.get('pst_webservices_doc_version') or 'n.d.'}; "
                f"busta massima {snapshot.get('busta_max_mb') or 'n.d.'} MB.",
                220,
            )
        )
    if capability_rows:
        lines.append(
            "Capability rilevanti: "
            + "; ".join(
                _truncate(
                    f"{row.get('label')} ({row.get('channel') or 'canale n.d.'}; {row.get('support_level') or 'supporto n.d.'})",
                    105,
                )
                for row in capability_rows[:4]
            )
            + "."
        )
    if action_rows:
        lines.append(
            "Azioni disponibili: "
            + "; ".join(_truncate(row.get("label") or row.get("action_id"), 105) for row in action_rows[:4])
            + "."
        )
    if monitoring_rows:
        lines.append(
            "Stato monitoraggio telematico: "
            + "; ".join(
                _truncate(
                    f"{row.get('nome') or row.get('source_id')} ({row.get('status') or 'n.d.'}, {row.get('detected_version') or row.get('detected_status') or 'stato n.d.'})",
                    110,
                )
                for row in monitoring_rows[:4]
            )
            + "."
        )
    elif xsd_rows or wsdl_rows:
        labels = [row.get("label") for row in xsd_rows[:2] if row.get("label")] + [row.get("label") for row in wsdl_rows[:2] if row.get("label")]
        if labels:
            lines.append("Cataloghi tecnici pertinenti: " + "; ".join(_truncate(label, 100) for label in labels) + ".")
    if rule_rows:
        lines.append(
            "Regole tecniche attive: "
            + "; ".join(_truncate(row.get("rule_text") or row.get("rule_id"), 120) for row in rule_rows[:4])
            + "."
        )
    sources = [
        _source(
            "Repository telematico",
            (
                f"Metodi: {stats.get('telematico_methods_repository', 0)}. "
                f"Canali XSD: {stats.get('telematico_xsd_channels_repository', 0)}. "
                f"Capability: {stats.get('telematico_capabilities_repository', 0)}. "
                f"Azioni: {stats.get('telematico_actions_repository', 0)}."
            ),
            source_id="telematico:repository",
            title="Repository telematico",
        )
    ]
    for row in source_rows[:4]:
        source = _source(
            f"Fonte telematica - {row.get('nome') or row.get('source_id')}",
            (
                f"Area: {row.get('area') or 'n.d.'}. "
                f"Motore: {row.get('motore') or 'n.d.'}. "
                f"Connector: {row.get('connector_kind') or 'n.d.'}. "
                f"Capacita: {row.get('capability') or 'n.d.'}."
            ),
            source_id=f"telematico-fonte:{row.get('source_id') or ''}",
            title=row.get("nome") or row.get("source_id") or "Fonte telematica",
        )
        source["official_url"] = row.get("official_url") or ""
        source["monitor_url"] = row.get("monitor_url") or ""
        sources.append(source)
    for row in action_rows[:3]:
        action = _source(
            f"Azione telematica - {row.get('label') or row.get('action_id')}",
            (
                f"Canale: {row.get('channel') or 'n.d.'}. "
                f"Fonte di verita: {row.get('source_of_truth') or 'n.d.'}. "
                f"Note: {row.get('notes') or 'Azione disponibile nel repository telematico.'}"
            ),
            source_id=f"telematico-azione:{row.get('action_id') or ''}",
            title=row.get("label") or row.get("action_id") or "Azione telematica",
        )
        action["requires_certificate"] = bool(row.get("requires_certificate"))
        action["handoff_required"] = bool(row.get("handoff_required"))
        sources.append(action)
    return lines, sources


def _load_legal_portali() -> list[Any]:
    try:
        gestore = GestionePortale(
            db_path=current_app.config.get("PORTALE_DB", "./portale/portali.json"),
            uploads_dir=current_app.config.get("PORTALE_UPLOADS", "./portale/uploads"),
        )
        return list(gestore.tutti(includi_inattivi=False) or [])
    except Exception:
        return []


def _legal_dashboard_headline(intelligence) -> dict[str, Any]:
    try:
        snapshot = intelligence.build_dashboard_snapshot(
            fascicoli=get_fascicoli().tutti(archiviati=True),
            clienti=get_clienti().tutti(),
            appuntamenti=get_agenda().tutti(),
            scadenze=get_scadenziario().tutte(),
            portali=_load_legal_portali(),
        )
    except Exception:
        return {}
    return dict(snapshot.get("headline") or {})


def _ricerca_legale_lines(question: str) -> tuple[list[str], list[dict[str, Any]]]:
    intelligence = get_legal_intelligence()
    route = intelligence.resolve_lex_legal_route(question)
    stats = intelligence.statistiche_repository()
    headline = _legal_dashboard_headline(intelligence)
    engine_rows = list(route.get("engine_rows") or [])
    source_rows = list(route.get("source_rows") or [])
    monitoring_rows = list(route.get("monitoring_rows") or [])
    alert_rows = list(route.get("alert_rows") or [])
    monitoring_by_source = {row.get("source_id"): row for row in monitoring_rows}
    lines = [
        (
            "Repository legale strutturato: "
            f"{stats.get('legal_sources_repository', 0)} fonti ufficiali, "
            f"{stats.get('legal_engines_repository', 0)} motori legali, "
            f"{stats.get('legal_keyword_to_engine', 0)} regole keyword→motore, "
            f"{stats.get('legal_keyword_to_source', 0)} regole keyword→fonte, "
            f"{stats.get('legal_operational_repository', 0)} regole operative."
        ),
        "Ricerca legale: Lex usa motori, fonti ufficiali, monitoraggio e audit come base deterministica prima della sintesi del modello.",
        "Routing deterministico: " + _truncate(route.get("reason") or "routing repository legale", 180) + ".",
    ]
    if headline:
        lines.insert(
            1,
            (
                "Cockpit Motori Legali: "
                f"{headline.get('motori_attivi', 0)} motori attivi, "
                f"{headline.get('fonti_aggiornate', 0)} fonti aggiornate su {headline.get('fonti_monitorate', 0)}, "
                f"{headline.get('alert_totali', 0)} alert aperti, "
                f"{headline.get('audit_recenti', 0)} audit recenti, "
                f"{headline.get('tabelle_normative', 0)} tabelle normative, "
                f"{headline.get('tabelle_da_validare', 0)} da verificare, "
                f"{headline.get('riferimenti_normativi', 0)} riferimenti ufficiali."
            ),
        )
    if engine_rows:
        lines.append(
            "Motori pertinenti: "
            + ", ".join(_truncate(row.get("short_name") or row.get("nome") or row.get("engine_id"), 80) for row in engine_rows[:4])
            + "."
        )
    if source_rows:
        lines.append(
            "Fonti ufficiali prioritarie: "
            + "; ".join(_truncate(row.get("nome") or row.get("source_id"), 90) for row in source_rows[:5])
            + "."
        )
    if monitoring_rows:
        lines.append(
            "Stato monitoraggio: "
            + "; ".join(
                _truncate(
                    f"{row.get('nome') or row.get('source_id')} ({row.get('freshness') or 'n.d.'}, {row.get('status') or 'n.d.'})",
                    100,
                )
                for row in monitoring_rows[:4]
            )
            + "."
        )
    if alert_rows:
        lines.append(
            "Alert collegati: "
            + "; ".join(_truncate(row.get("title") or row.get("alert_type"), 110) for row in alert_rows[:3])
            + "."
        )
    sources = [
        _source(
            "Repository legale",
            (
                f"Motori: {stats.get('legal_engines_repository', 0)}. "
                f"Fonti: {stats.get('legal_sources_repository', 0)}. "
                f"Routing keyword: {stats.get('legal_keyword_to_engine', 0)} motori / "
                f"{stats.get('legal_keyword_to_source', 0)} fonti."
            ),
            source_id="legal-intelligence:repository",
            title="Repository legale",
        )
    ]
    if headline:
        dashboard_source = _source(
            "Dashboard Motori Legali",
            (
                f"Motori attivi: {headline.get('motori_attivi', 0)}. "
                f"Fonti aggiornate: {headline.get('fonti_aggiornate', 0)} su {headline.get('fonti_monitorate', 0)}. "
                f"Alert aperti: {headline.get('alert_totali', 0)}. "
                f"Audit recenti: {headline.get('audit_recenti', 0)}. "
                f"Tabelle normative: {headline.get('tabelle_normative', 0)}. "
                f"Da verificare: {headline.get('tabelle_da_validare', 0)}. "
                f"Riferimenti ufficiali: {headline.get('riferimenti_normativi', 0)}."
            ),
            source_id="legal-intelligence:dashboard-headline",
            title="Dashboard Motori Legali",
        )
        dashboard_source["headline"] = headline
        sources.append(dashboard_source)
    for row in source_rows[:5]:
        source_id = row.get("source_id") or ""
        monitoring = monitoring_by_source.get(source_id, {})
        source = _source(
            f"Fonte ufficiale - {row.get('nome')}",
            (
                f"Area: {row.get('area') or 'n.d.'}. "
                f"Motore: {row.get('motore') or 'n.d.'}. "
                f"Capacita: {row.get('capability') or 'n.d.'}. "
                f"Stato: {monitoring.get('status') or 'n.d.'} / {monitoring.get('freshness') or 'n.d.'}."
            ),
            source_id=f"fonte:{source_id}",
            title=row.get("nome") or source_id,
        )
        source["official_url"] = row.get("official_url") or ""
        source["monitor_url"] = row.get("monitor_url") or ""
        source["motore_id"] = row.get("motore") or ""
        source["freshness"] = monitoring.get("freshness") or ""
        source["status"] = monitoring.get("status") or ""
        source["detected_version"] = monitoring.get("detected_version") or ""
        source["warning"] = monitoring.get("warning") or ""
        sources.append(source)
    return lines, sources


def _aggiornamenti_legali_lines(question: str) -> tuple[list[str], list[dict[str, Any]]]:
    pipeline = build_legal_update_pipeline_runtime()
    snapshot = pipeline.dashboard_snapshot()
    headline = dict(snapshot.get("headline") or {})
    sources_rows = list(snapshot.get("sources") or [])
    lex_rows = pipeline.repository.search_lex_sources(question, limit=6)
    structured_total = (
        int(headline.get("published_normative") or 0)
        + int(headline.get("published_jurisprudence") or 0)
        + int(headline.get("published_prassi") or 0)
    )
    lines = [
        (
            "Aggiornamenti legali condivisi: "
            f"{headline.get('sources', 0)} fonti attive, "
            f"{headline.get('raw_documents', 0)} documenti grezzi, "
            f"{headline.get('analyses', 0)} analisi AI, "
            f"{headline.get('review_pending', 0)} review pendenti, "
            f"{headline.get('published_news', 0)} news pubblicate, "
            f"{structured_total} elementi in archivio strutturato."
        ),
        "Lex AI legge gli aggiornamenti da legal_updates.db; export JSON e mirror legacy non sono fonte operativa del contesto.",
    ]
    if sources_rows:
        lines.append(
            "Fonti monitorate: "
            + "; ".join(
                _truncate(
                    f"{row.get('name') or row.get('code')} ({row.get('category') or 'categoria n.d.'}, trust {row.get('trust_class') or 'n.d.'})",
                    110,
                )
                for row in sources_rows[:5]
            )
            + "."
        )
    if lex_rows:
        lines.append(
            "Aggiornamenti pertinenti: "
            + "; ".join(
                _truncate(
                    f"{row.get('title')} ({row.get('entity_type') or row.get('type')}, {row.get('published_at') or 'data n.d.'})",
                    125,
                )
                for row in lex_rows
            )
            + "."
        )
    else:
        lines.append("Nessun aggiornamento SQL pubblicato pertinente alla richiesta; Lex deve dichiarare la lacuna invece di inventare contenuti.")

    sources = [
        _source(
            "Update Intelligence SQL",
            (
                f"Fonti attive: {headline.get('sources', 0)}. "
                f"Documenti grezzi: {headline.get('raw_documents', 0)}. "
                f"Analisi AI: {headline.get('analyses', 0)}. "
                f"Review pendenti: {headline.get('review_pending', 0)}. "
                f"News pubblicate: {headline.get('published_news', 0)}. "
                f"Archivio strutturato: {structured_total}."
            ),
            source_id="legal-updates:dashboard",
            title="Aggiornamenti legali SQL",
        )
    ]
    sources[0]["type"] = "legal_updates"
    sources[0]["repository"] = "legal_updates_sql"
    sources[0]["db_path"] = pipeline.repository.db_path
    sources[0]["trust_class"] = "B"
    sources[0]["source_level"] = 2
    for row in lex_rows:
        source_row = _source(
            f"Aggiornamento legale - {row.get('title')}",
            row.get("excerpt") or row.get("content") or "",
            source_id=str(row.get("id") or ""),
            title=str(row.get("title") or "Aggiornamento legale"),
        )
        source_row.update(row)
        source_row["text"] = row.get("excerpt") or row.get("content") or source_row.get("text") or ""
        sources.append(source_row)
    return lines, sources


def _archivio_sentenze_lines(question: str) -> tuple[list[str], list[dict[str, Any]]]:
    gestore = get_giurisprudenza()
    stats = gestore.statistiche()
    route = {}
    if hasattr(gestore, "resolve_lex_giurisprudenza_route"):
        try:
            route = gestore.resolve_lex_giurisprudenza_route(question) or {}
        except Exception:
            route = {}
    rows = list(route.get("archive_rows") or [])
    if not rows:
        rows = gestore.cerca(q=question)[:4] if _clean_spaces(question) else gestore.cerca()[:4]
    corpus_rows = list(route.get("corpus_rows") or [])
    if not corpus_rows:
        corpus_rows = (
            gestore.cerca_corpus_professionale(q=question, limit=4)
            if _clean_spaces(question)
            else gestore.cerca_corpus_professionale(limit=4)
        )
    repo_stats = {}
    if hasattr(gestore, "statistiche_repository"):
        try:
            repo_stats = gestore.statistiche_repository() or {}
        except Exception:
            repo_stats = {}
    lines = [
        (
            f"Archivio sentenze: {stats.get('totale_sentenze', 0)} provvedimenti indicizzati, "
            f"{stats.get('fonti_attive', 0)} fonti attive. "
            f"Corpus professionale: {stats.get('corpus_sentenze', 0)} schede strutturate."
        ),
        (
            f"Repository giurisprudenza: {repo_stats.get('giurisprudenza_sources_repository', 0)} fonti, "
            f"{repo_stats.get('giurisprudenza_taxonomy_repository', 0)} nodi tassonomici e "
            f"{repo_stats.get('giurisprudenza_sync_registry', 0)} stati sync."
            if repo_stats
            else "Motore giurisprudenziale: prima corpus professionale verificabile, poi fonti e sync ufficiali."
        ),
    ]
    preferred_area = _clean_spaces(route.get("preferred_area_title"))
    preferred_branch = _clean_spaces(route.get("preferred_branch_title"))
    preferred_subbranch = _clean_spaces(route.get("preferred_subbranch_title"))
    source_rows = list(route.get("source_rows") or [])
    sync_rows = list(route.get("sync_rows") or [])
    if preferred_area or source_rows:
        route_bits = []
        if preferred_area:
            route_bits.append(f"area {preferred_area}")
        if preferred_branch:
            route_bits.append(f"branca {preferred_branch}")
        if preferred_subbranch:
            route_bits.append(f"sottobranca {preferred_subbranch}")
        if source_rows:
            route_bits.append(
                "fonti preferite "
                + ", ".join(_clean_spaces(row.get("nome")) for row in source_rows[:3] if _clean_spaces(row.get("nome")))
            )
        route_mode = _clean_spaces(route.get("route_mode"))
        if route_mode:
            route_bits.append(f"modalita {route_mode}")
        if route_bits:
            lines.append("Routing giurisprudenza: " + "; ".join(route_bits) + ".")
    if sync_rows:
        lines.append(
            "Stato fonti giurisprudenziali: "
            + "; ".join(
                _truncate(
                    f"{row.get('source_name') or row.get('source_id')}: {row.get('last_status') or 'n.d.'}",
                    90,
                )
                for row in sync_rows[:3]
            )
            + "."
        )
    if rows:
        lines.append(
            "Sentenze utili: "
            + "; ".join(
                _truncate(
                    f"{row.get('titolo') or row.get('organo_giudicante') or 'Pronuncia'} ({row.get('grado') or row.get('area') or 'classificazione n.d.'})",
                    110,
                )
                for row in rows
              )
              + "."
          )
    if corpus_rows:
        lines.append(
            "Corpus giurisprudenziale verificabile: "
            + "; ".join(
                _truncate(
                    (
                        f"{row.get('titolo') or row.get('organo_giudicante') or 'Pronuncia'} "
                        f"({row.get('stato_verifica') or 'da verificare'})"
                    ),
                    120,
                )
                for row in corpus_rows
            )
            + "."
        )
    sources = []
    seen_source_ids: set[str] = set()
    repository_source = _source(
        "Repository giurisprudenza",
        (
            f"Corpus strutturato: {stats.get('corpus_sentenze', 0)} schede. "
            f"Fonti repository: {repo_stats.get('giurisprudenza_sources_repository', 0) if repo_stats else len(source_rows)}. "
            f"Routing: {route.get('reason') or 'corpus-first'}."
        ),
        source_id="giurisprudenza:repository",
        title="Repository giurisprudenza",
    )
    repository_source["route_mode"] = route.get("route_mode") or "corpus_professionale"
    sources.append(repository_source)
    for idx, source_info in enumerate(source_rows):
        source_row = _source(
            f"Fonte giurisprudenza - {source_info.get('nome') or source_info.get('source_id') or 'Fonte'}",
            (
                f"Giurisdizione: {source_info.get('giurisdizione') or 'n.d.'}. "
                f"Accesso: {source_info.get('access_mode') or 'n.d.'}. "
                f"Sync: {source_info.get('sync_mode') or 'n.d.'}. "
                f"Copertura: {source_info.get('coverage') or 'n.d.'}."
            ),
            source_id=f"giurisprudenza-fonte:{source_info.get('source_id') or idx}",
            title=source_info.get("nome") or source_info.get("source_id") or "Fonte giurisprudenziale",
        )
        source_row["official_url"] = source_info.get("official_url") or ""
        source_row["search_url"] = source_info.get("search_url") or ""
        source_row["access_mode"] = source_info.get("access_mode") or ""
        source_row["sync_mode"] = source_info.get("sync_mode") or ""
        source_row["supports_auto_sync"] = bool(source_info.get("supports_auto_sync"))
        source_row["judgment_count"] = int(source_info.get("judgment_count") or 0)
        source_row["route_bias"] = source_info.get("route_bias") or ""
        source_row_id = str(source_row.get("id") or "")
        if source_row_id in seen_source_ids:
            continue
        seen_source_ids.add(source_row_id)
        sources.append(source_row)
    for idx, row in enumerate(corpus_rows):
        full_record = gestore.scheda_corpus_professionale(row.get("id"))
        if not full_record:
            continue
        source_row = _source(
            f"Corpus sentenze - {full_record.get('titolo') or full_record.get('organo_giudicante') or 'Pronuncia'}",
            (
                f"Organo: {full_record.get('organo_giudicante') or 'n.d.'}. "
                f"Sezione: {full_record.get('sezione') or 'n.d.'}. "
                f"Principio: {full_record.get('principio_sintetico') or full_record.get('massima_ufficiale') or full_record.get('abstract') or 'Pronuncia strutturata nel corpus giurisprudenziale.'}"
            ),
            source_id=f"corpus-sentenza:{full_record.get('id') or idx}",
            title=full_record.get("titolo") or full_record.get("organo_giudicante") or "Pronuncia",
        )
        source_row["official_url"] = (
            full_record.get("url_pagina_ufficiale")
            or full_record.get("url_pdf_ufficiale")
            or ""
        )
        source_row["url_pagina_ufficiale"] = full_record.get("url_pagina_ufficiale") or ""
        source_row["url_pdf_ufficiale"] = full_record.get("url_pdf_ufficiale") or ""
        source_row["stato_verifica_fonte"] = full_record.get("stato_verifica") or "da_verificare"
        source_row["verified_reference"] = gestore.riferimento_professionale_verificato(full_record.get("id"))
        source_row["downloadable_pdf"] = gestore.pdf_professionale_disponibile(full_record.get("id"))
        source_row["pdf_ufficiale_presente"] = bool(full_record.get("pdf_ufficiale_presente"))
        source_row["ecli"] = full_record.get("ecli") or ""
        source_row["organo_giudicante"] = full_record.get("organo_giudicante") or ""
        source_row["numero_provvedimento"] = full_record.get("numero_sentenza") or ""
        source_row["anno"] = full_record.get("anno_sentenza") or ""
        source_row_id = str(source_row.get("id") or "")
        if source_row_id in seen_source_ids:
            continue
        seen_source_ids.add(source_row_id)
        sources.append(source_row)
    for idx, row in enumerate(rows):
        official_url = (
            row.get("url_pagina_ufficiale")
            or row.get("url_pdf_ufficiale")
            or row.get("url_origine")
            or ""
        )
        source_row = _source(
            f"Archivio sentenze - {row.get('titolo') or row.get('organo_giudicante') or 'Pronuncia'}",
            (
                f"Area: {row.get('area') or 'n.d.'}. "
                f"Branca: {row.get('branca') or 'n.d.'}. "
                f"Sintesi: {row.get('sintesi') or row.get('massima') or 'Provvedimento disponibile in archivio.'}"
            ),
            source_id=f"sentenza:{row.get('id') or row.get('hash') or idx}",
            title=row.get("titolo") or row.get("organo_giudicante") or "Pronuncia",
        )
        source_row["official_url"] = official_url
        source_row["url_pagina_ufficiale"] = row.get("url_pagina_ufficiale") or official_url
        source_row["url_pdf_ufficiale"] = row.get("url_pdf_ufficiale") or ""
        source_row["stato_verifica_fonte"] = row.get("stato_verifica_fonte") or "da_verificare"
        source_row["verified_reference"] = (
            row.get("stato_verifica_fonte") in {"verificata", "parzialmente_verificata"}
            and bool(official_url or row.get("ecli"))
        )
        source_row["downloadable_pdf"] = bool(row.get("pdf_ufficiale_presente")) and bool(
            row.get("url_pdf_ufficiale")
        )
        source_row["pdf_ufficiale_presente"] = bool(row.get("pdf_ufficiale_presente"))
        source_row["ecli"] = row.get("ecli") or ""
        source_row["organo_giudicante"] = row.get("organo_giudicante") or ""
        source_row["numero_provvedimento"] = row.get("numero_provvedimento") or ""
        source_row["anno"] = row.get("anno") or ""
        source_row_id = str(source_row.get("id") or "")
        if source_row_id in seen_source_ids:
            continue
        seen_source_ids.add(source_row_id)
        sources.append(source_row)
    return lines, sources


def _strumenti_legali_lines(question: str) -> tuple[list[str], list[dict[str, Any]]]:
    gestore = GestioneStrumentiLegali(normative_db_path=_cfg_data_path("NORMATIVE_TABLES_DB") or "./intelligence/tabelle_normative.json")
    rows = list(gestore.catalogo_moduli())
    terms = _query_terms(question)
    selected = _select_ranked(
        rows,
        lambda row: _score_parts(terms, row.get("title"), row.get("subtitle"), row.get("categoria")),
        limit=5,
    )
    lines = [f"Strumenti legali: {len(rows)} moduli di calcolo e supporto operativo disponibili."]
    if selected:
        lines.append(
            "Moduli utili: "
            + "; ".join(
                _truncate(f"{row.get('title')} ({row.get('categoria')})", 90)
                for row in selected
            )
            + "."
        )
    sources = [
        _source(
            f"Strumento legale - {row.get('title')}",
            f"Categoria: {row.get('categoria')}. Dettaglio: {row.get('subtitle')}.",
            source_id=f"strumento:{row.get('id')}",
            title=str(row.get("title") or "Strumento"),
        )
        for row in selected
    ]
    return lines, sources


def _applicazioni_lines(question: str) -> tuple[list[str], list[dict[str, Any]]]:
    repository = get_applicazioni_repository()
    route = repository.resolve_workspace_for_request(question, limit=5)
    stats = repository.storage_stats()
    best = dict(route.get("best_app") or {})
    candidates = list(route.get("candidate_apps") or [])
    related = list(route.get("related_apps") or [])
    lines = [
        (
            "Workspace registry applicazioni: "
            f"{stats.get('applicazioni_catalog_repository', 0)} moduli, "
            f"{stats.get('applicazioni_sections_repository', 0)} sezioni, "
            f"{stats.get('applicazioni_status_repository', 0)} stati, "
            f"{stats.get('applicazioni_access_repository', 0)} modalita di accesso, "
            f"{stats.get('applicazioni_featured_repository', 0)} voci di primo piano."
        ),
        "Applicazioni: Lex usa il registro workspace del gestionale per scegliere modulo, accesso diretto o guidato e alternative correlate prima di spiegare il percorso.",
        "Routing workspace: " + _truncate(route.get("reason") or "registro applicazioni disponibile", 180) + ".",
    ]
    if best:
        lines.append(
            "Modulo consigliato: "
            + _truncate(
                f"{best.get('title')} ({best.get('section_title') or 'modulo'}, {best.get('access_mode_label') or best.get('access_mode') or 'n.d.'}, stato {best.get('status_label') or best.get('status') or 'n.d.'})",
                160,
            )
            + "."
        )
        if _clean_spaces(route.get("next_action")):
            lines.append("Prossima azione: " + _truncate(route.get("next_action"), 180) + ".")
    if candidates:
        lines.append(
            "Applicazioni candidate: "
            + "; ".join(
                _truncate(
                    f"{row.get('title')} ({row.get('section_title') or row.get('workspace_kind_label') or 'modulo'})",
                    100,
                )
                for row in candidates[:4]
            )
            + "."
        )
    if related:
        lines.append(
            "Alternative correlate: "
            + "; ".join(_truncate(row.get("title") or row.get("app_id"), 95) for row in related[:4])
            + "."
        )
    sources = [
        _source(
            "Repository applicazioni",
            (
                f"Catalogo: {stats.get('applicazioni_catalog_repository', 0)}. "
                f"Sezioni: {stats.get('applicazioni_sections_repository', 0)}. "
                f"Modalita: {stats.get('applicazioni_access_repository', 0)}. "
                f"Primo piano: {stats.get('applicazioni_featured_repository', 0)}."
            ),
            source_id="applicazioni:repository",
            title="Repository applicazioni",
        )
    ]
    if best:
        source = _source(
            f"Applicazione - {best.get('title')}",
            (
                f"Sezione: {best.get('section_title') or 'n.d.'}. "
                f"Modalita: {best.get('access_mode_label') or best.get('access_mode') or 'n.d.'}. "
                f"Stato: {best.get('status_label') or best.get('status') or 'n.d.'}. "
                f"Endpoint: {best.get('endpoint') or 'n.d.'}."
            ),
            source_id=f"applicazione:{best.get('app_id') or ''}",
            title=str(best.get("title") or "Applicazione"),
        )
        source["endpoint"] = best.get("endpoint") or ""
        source["params"] = dict(best.get("params") or {})
        source["access_mode"] = best.get("access_mode") or ""
        source["requires_guided_flow"] = bool(best.get("requires_guided_flow"))
        source["requires_cliente"] = bool(best.get("requires_cliente"))
        source["requires_fascicolo"] = bool(best.get("requires_fascicolo"))
        source["requires_telematic_context"] = bool(best.get("requires_telematic_context"))
        source["capabilities"] = list(best.get("capabilities") or [])
        source["blocked_if"] = list(best.get("blocked_if") or [])
        sources.append(source)
    for row in related[:3]:
        related_source = _source(
            f"Applicazione correlata - {row.get('title')}",
            (
                f"Sezione: {row.get('section_title') or 'n.d.'}. "
                f"Modalita: {row.get('access_mode_label') or row.get('access_mode') or 'n.d.'}. "
                f"Endpoint: {row.get('endpoint') or 'n.d.'}."
            ),
            source_id=f"applicazione-correlata:{row.get('app_id') or ''}",
            title=str(row.get("title") or "Applicazione correlata"),
        )
        related_source["endpoint"] = row.get("endpoint") or ""
        related_source["params"] = dict(row.get("params") or {})
        sources.append(related_source)
    return lines, sources


def _document_rag_lines(question: str) -> tuple[list[str], list[dict[str, Any]]]:
    if is_managed_cloud_runtime():
        return (
            [
                "RAG documentale locale: in ambiente cloud gestito il retrieval dei documenti del cliente resta demandato al companion locale sul dispositivo o a installazioni self-hosted.",
            ],
            [],
        )
    try:
        rows = get_local_ai_service().hybrid_search(question, top_k=4)
    except Exception:
        rows = []
    lines = ["RAG documentale locale: supporto disponibile sui documenti gia' indicizzati quando IUSENTRA gira sullo stesso host dei dati."]
    if rows:
        lines.append(
            "Documenti indicizzati pertinenti: "
            + "; ".join(_truncate(row.get("citation") or row.get("title") or "Documento", 110) for row in rows)
            + "."
        )
    else:
        lines.append("Nessun documento indicizzato pertinente rilevato per questa domanda.")
    return lines, rows[:4]


def build_lex_studio_context(
    question: str,
    *,
    mode: str = "default",
    messages: list[dict[str, object]] | None = None,
) -> dict[str, Any]:
    q = _clean_spaces(question)
    chat_mode = str(mode or "").strip().lower() == "chat"
    focus = resolve_conversation_focus(q, messages=messages) if chat_mode else {}
    effective_question = _clean_spaces(str(focus.get("effective_question") or q))
    if not effective_question:
        effective_question = q
    request_profile = classify_request(effective_question, requested_mode=mode)
    sections: list[str] = [
        "Lex deve restare sempre consultivo, non decisionale, e formulare solo suggerimenti, ipotesi operative, check-list, rischi e prossimi passi.",
        "Se manca il contesto o serve una verifica aggiornata sul web, Lex deve dirlo chiaramente e indicare le fonti ufficiali web piu' adatte senza inventare.",
        build_request_profile_prompt(request_profile),
    ]
    focus_label = _clean_spaces(focus.get("focus_label"))
    research_strategy = _clean_spaces(focus.get("research_strategy"))
    web_execution_requested = bool(focus.get("web_execution_requested"))
    competence_labels = resolve_competence_labels(effective_question, limit=3)
    competence_hints = build_competence_context_hints(effective_question, limit=2)
    competence_section_titles = set(resolve_competence_section_titles(effective_question, limit=3, max_sections=6))
    if chat_mode and focus_label:
        sections.append(
            f"Per questa richiesta resta focalizzata su {focus_label} e non allargare la risposta alla panoramica generale dello studio salvo richiesta esplicita."
        )
    if competence_labels:
        sections.append(
            "Competenze IUSENTRA coinvolte: " + ", ".join(competence_labels) + "."
        )
    sections.extend(competence_hints)
    if chat_mode and research_strategy == "auto_narrow_recent_civil_case_law":
        sections.append(
            "Ricerca ampia su sentenze civili: Lex deve partire dalle pronunce civili piu' recenti e rilevanti, con priorita' alla Cassazione e alle fonti ufficiali disponibili, senza chiedere subito di restringere la materia."
        )
    if chat_mode and web_execution_requested:
        sections.append(
            "L'utente ha chiesto una verifica web operativa: Lex deve prendere in carico la ricerca, usare il tema gia' emerso nella conversazione e riportare direttamente i risultati rilevanti."
        )
    sources: list[dict[str, Any]] = []
    priority_sources: list[dict[str, Any]] = []
    live_source_ids: list[str] = []
    selected_detail_titles = (
        set(focus.get("section_titles") or ())
        if chat_mode and focus.get("section_titles")
        else (_select_detail_sections_for_chat(effective_question) if chat_mode else _select_detail_sections(effective_question))
    )
    selected_detail_titles = set(selected_detail_titles) | competence_section_titles
    if request_profile.intent == "normativa":
        selected_detail_titles.add("Ricerca legale e fonti web")
        selected_detail_titles.add("Aggiornamenti legali")
    if request_profile.intent == "giurisprudenza":
        selected_detail_titles.add("Archivio sentenze")
        selected_detail_titles.add("Aggiornamenti legali")
    if request_profile.intent in {"bozza_atto", "bozza_lettera"}:
        selected_detail_titles.add("Template atti")
    include_live_web = (
        bool(focus.get("include_live_web"))
        if chat_mode and focus.get("topic")
        else _should_include_live_web(effective_question, chat_mode=chat_mode)
    )

    if not chat_mode or focus.get("has_explicit_overview") or any(title in _BASE_SECTION_TITLES for title in selected_detail_titles):
        _append_section(sections, "Profilo studio", _studio_profile_lines())

    always_specs = [
        ("Impostazioni studio", _settings_studio_lines),
        ("PEC e canali email", _pec_lines),
        ("Quadro operativo", _operational_lines),
    ]
    detail_specs = [
        ("Centro Servizi Telematici", lambda: _telematico_lines(effective_question)),
        ("Fascicoli", lambda: _fascicoli_lines(effective_question)),
        ("Clienti", lambda: _clienti_lines(effective_question)),
        ("Agenda", lambda: _agenda_lines(effective_question)),
        ("Soggetti", lambda: _soggetti_lines(effective_question)),
        ("Scadenziario", lambda: _scadenziario_lines(effective_question)),
        ("Template atti", lambda: _template_atti_lines(effective_question)),
        ("Tariffario", lambda: _tariffario_lines(effective_question)),
        ("Preventivi", lambda: _preventivi_lines(effective_question)),
        ("Fatturazione", lambda: _fatturazione_lines(effective_question)),
        ("Aggiornamenti legali", lambda: _aggiornamenti_legali_lines(effective_question)),
        ("Ricerca legale e fonti web", lambda: _ricerca_legale_lines(effective_question)),
        ("Archivio sentenze", lambda: _archivio_sentenze_lines(effective_question)),
        ("Strumenti legali", lambda: _strumenti_legali_lines(effective_question)),
        ("Applicazioni", lambda: _applicazioni_lines(effective_question)),
        ("RAG documentale locale", lambda: _document_rag_lines(effective_question)),
    ]
    if chat_mode:
        all_specs = [*always_specs, *detail_specs]
        section_plan = [
            (title, builder)
            for title, builder in all_specs
            if title in selected_detail_titles
        ]
    else:
        section_plan = list(always_specs)
        section_plan.extend(
            (title, builder)
            for title, builder in detail_specs
            if title in selected_detail_titles
        )
    for title, builder in section_plan:
        try:
            lines, section_sources = _cached_section_payload(title, effective_question, builder)
        except Exception as exc:
            current_app.logger.exception("Errore contesto Lex per sezione %s: %s", title, exc)
            lines, section_sources = ([f"{title}: contesto non disponibile in questo momento."], [])
        _append_section(sections, title, lines)
        sources.extend(section_sources or [])

    local_sources = _dedupe_sources(sources)
    force_web_fallback = web_execution_requested or _should_force_web_fallback(
        effective_question,
        local_sources=local_sources,
        chat_mode=chat_mode,
    )

    if include_live_web or force_web_fallback:
        try:
            payload = build_live_official_web_context(
                effective_question,
                force=force_web_fallback,
            )
            lines = list(payload.get("lines") or [])
            web_sources = list(payload.get("sources") or [])
            if web_execution_requested and lines:
                lines = [
                    "Richiesta web presa in carico: Lex integra direttamente con fonti ufficiali live pertinenti.",
                    *lines,
                ]
            elif force_web_fallback and lines:
                lines = [
                    "Il contesto interno non offre riferimenti sufficienti su questa richiesta. Lex integra con fonti ufficiali live mirate.",
                    *lines,
                ]
            _append_section(sections, "Verifica live fonti ufficiali web", lines)
            priority_sources.extend(web_sources)
            live_source_ids = list(payload.get("source_ids") or [])
        except Exception as exc:
            current_app.logger.exception("Errore fallback web Lex: %s", exc)

    deduped_sources = _dedupe_sources([*priority_sources, *local_sources])
    evaluated_sources = [
        evaluate_source_row(
            row,
            area=request_profile.area,
            mode=request_profile.source_mode,
        )
        for row in deduped_sources
    ]
    evaluated_sources.sort(
        key=lambda row: (
            float(row.get("source_policy_score") or 0.0),
            float(row.get("score") or 0.0),
            1 if row.get("verified_reference") else 0,
        ),
        reverse=True,
    )
    deduped_sources = evaluated_sources
    source_policy_summary = summarize_evaluated_sources(
        evaluated_sources,
        area=request_profile.area,
        area_confidence=request_profile.area_confidence,
        mode=request_profile.source_mode,
        require_primary=request_profile.source_mode == "strict",
    )
    policy_lines = [
        f"Intento: {request_profile.intent_label}.",
        f"Area: {request_profile.area} (confidenza {request_profile.area_confidence:.2f}).",
        f"Modalita fonti: {request_profile.source_mode}.",
        source_policy_summary.reasoning,
        *list(source_policy_summary.warnings),
    ]
    _append_section(sections, "Policy fonti e affidabilita", policy_lines)
    legal_dashboard_headline = {}
    for row in evaluated_sources:
        if row.get("id") == "legal-intelligence:dashboard-headline":
            legal_dashboard_headline = dict(row.get("headline") or {})
            break
    verified_legal_references = collect_verified_legal_references(evaluated_sources)
    execution_policy = build_execution_policy(
        question=effective_question,
        focus_topic=_clean_spaces(focus.get("topic")),
        verified_legal_references=verified_legal_references,
        web_execution_requested=bool(web_execution_requested),
    )
    if execution_policy.prompt_block:
        _append_section(
            sections,
            "Policy esecutiva Lex",
            execution_policy.prompt_block.splitlines(),
        )
    legal_reference_guard_prompt = build_case_law_guard_prompt(
        effective_question,
        evaluated_sources,
    )
    if legal_reference_guard_prompt:
        _append_section(
            sections,
            "Affidabilita' riferimenti legali",
            legal_reference_guard_prompt.splitlines(),
        )

    answer_guardrail_message = ""
    if source_policy_summary.block_unverified_answer:
        if request_profile.intent == "normativa":
            answer_guardrail_message = (
                "Non ho ancora una base primaria sufficiente per darti una risposta normativa forte. "
                "Posso aiutarti a circoscrivere il punto o cercare una fonte ufficiale piu' mirata."
            )
        elif request_profile.intent == "giurisprudenza":
            answer_guardrail_message = (
                "Non ho ancora una pronuncia o una base giurisprudenziale verificata abbastanza forte per risponderti in modo affidabile. "
                "Meglio fermarsi qui e cercare una fonte ufficiale piu' precisa."
            )
        else:
            answer_guardrail_message = (
                "La base documentale disponibile non e' ancora sufficiente per una risposta affidabile. "
                "Meglio chiarire il perimetro o integrare con fonti piu' forti."
            )

    legal_route = get_legal_intelligence().resolve_lex_legal_route(effective_question)

    return {
        "prompt_block": "\n".join(sections).strip(),
        "sources": deduped_sources[:10 if chat_mode else 12],
        "citations": [
            row.get("citation")
            for row in deduped_sources[:10 if chat_mode else 12]
            if row.get("citation")
        ],
        "engine_ids": list(legal_route.get("engine_ids") or motori_per_query(effective_question)),
        "source_ids": list(
            dict.fromkeys(
                [
                    *(legal_route.get("source_ids") or fonti_per_query(effective_question)),
                    *live_source_ids,
                ]
            )
        ),
        "legal_route_scope": _clean_spaces(legal_route.get("route_scope")),
        "legal_route_reason": _clean_spaces(legal_route.get("reason")),
        "focus_label": focus_label,
        "focus_topic": _clean_spaces(focus.get("topic")),
        "competence_labels": competence_labels,
        "research_strategy": research_strategy,
        "effective_question": effective_question,
        "web_fallback_used": bool(force_web_fallback),
        "web_execution_requested": bool(web_execution_requested),
        "verified_legal_references": verified_legal_references[:4],
        "legal_reference_guard_active": bool(legal_reference_guard_prompt),
        "execution_policy": execution_policy.to_dict(),
        "legal_dashboard_headline": legal_dashboard_headline,
        "request_profile": request_profile.to_dict(),
        "source_policy_summary": source_policy_summary.to_dict(),
        "source_mode": request_profile.source_mode,
        "answer_guardrail_message": answer_guardrail_message,
    }


def warm_lex_studio_context(*, question: str = "", context_label: str = "") -> dict[str, Any]:
    """Pre-riscalda il contesto studio di Lex per accorciare il tempo alla prima risposta."""
    seed = _clean_spaces(question) or _clean_spaces(context_label)
    return build_lex_studio_context(seed, mode="chat")
