"""Contesto consultivo e governabile di Lex per i moduli dello studio."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from flask import current_app, g

from pct.applicazioni_catalogo import cerca_applicazioni, catalogo_applicazioni
from pct.config_studio import GestioneConfigStudio
from pct.fatturazione import GestioneFatturazione
from pct.legal_intelligence import FONTI_UFFICIALI, fonti_per_query, motori_per_query
from pct.preventivi import GestionePreventivi
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
    get_clienti,
    get_fascicoli,
    get_giurisprudenza,
    get_legal_intelligence,
    get_scadenziario,
    get_soggetti,
)
from web.services.assistente_live_web import build_live_official_web_context
from web.services.local_ai_runtime import get_local_ai_service


_DEFAULT_WEB_SOURCE_IDS: tuple[str, ...] = (
    "pst_giustizia",
    "normattiva",
    "cassazione",
    "agenzia_entrate",
)


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


def _load_studio_config() -> Any | None:
    try:
        return GestioneConfigStudio(current_app.config["STUDIO_CONFIG"]).config
    except Exception:
        return None


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
        f"Denominazione studio: {_clean_spaces(getattr(studio, 'nome', 'Studio Legale PCT')) or 'Studio Legale PCT'}.",
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


def _clienti_lines(question: str) -> tuple[list[str], list[dict[str, Any]]]:
    gestore = get_clienti()
    all_rows = gestore.tutti()
    stats = gestore.statistiche()
    matches = gestore.cerca(question) if _clean_spaces(question) else []
    selected = matches[:4] if matches else all_rows[:4]
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
    sources = [
        _source(
            f"Cliente - {row.nome_completo}",
            f"Tipo: {getattr(getattr(row, 'tipo', None), 'value', '')}. Stato: {getattr(getattr(row, 'stato', None), 'value', '')}. Referente: {row.avvocato_referente or 'n.d.'}.",
            source_id=f"cliente:{row.id}",
            title=row.nome_completo,
        )
        for row in selected
    ]
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
    terms = _query_terms(question)
    selected = _select_ranked(
        rows,
        lambda row: _score_parts(
            terms,
            getattr(row, "titolo", ""),
            getattr(row, "categoria", ""),
            getattr(row, "area", ""),
            getattr(row, "descrizione", ""),
            getattr(row, "note", ""),
        ),
        limit=4,
    )
    lines = [f"Template atti: {len(rows)} modelli disponibili tra builtin e personalizzati."]
    if selected:
        lines.append(
            "Template utili: "
            + "; ".join(
                _truncate(
                    f"{row.titolo} ({row.area or row.categoria or 'area n.d.'})",
                    100,
                )
                for row in selected
            )
            + "."
        )
    sources = [
        _source(
            f"Template atti - {row.titolo}",
            f"Area: {row.area or 'n.d.'}. Categoria: {row.categoria or 'n.d.'}. Descrizione: {row.descrizione or row.note or 'Template operativo disponibile.'}",
            source_id=f"template:{row.id}",
            title=row.titolo,
        )
        for row in selected
    ]
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
    gestore = GestionePreventivi(_cfg_data_path("PREVENTIVI_DB") or "./preventivi/preventivi.json")
    preventivi = gestore.tutti_preventivi()
    conferimenti = gestore.tutti_conferimenti()
    terms = _query_terms(question)
    selected = _select_ranked(
        preventivi,
        lambda row: _score_parts(terms, row.numero, row.oggetto, row.area_pratica, row.tipo_procedimento, row.note),
        limit=4,
    )
    lines = [
        f"Preventivi: {len(preventivi)} preventivi e {len(conferimenti)} conferimenti di incarico archiviati.",
    ]
    if selected:
        lines.append(
            "Preventivi rilevanti: "
            + "; ".join(
                _truncate(
                    f"{row.numero} - {row.oggetto} ({getattr(getattr(row, 'stato', None), 'value', '') or 'stato n.d.'})",
                    110,
                )
                for row in selected
            )
            + "."
        )
    sources = [
        _source(
            f"Preventivo - {row.numero}",
            f"Oggetto: {row.oggetto}. Stato: {getattr(getattr(row, 'stato', None), 'value', '') or 'n.d.'}. Procedimento: {row.tipo_procedimento or 'n.d.'}.",
            source_id=f"preventivo:{row.id}",
            title=row.numero,
        )
        for row in selected
    ]
    return lines, sources


def _fatturazione_lines(question: str) -> tuple[list[str], list[dict[str, Any]]]:
    gestore = GestioneFatturazione(_cfg_data_path("FATTURAZIONE_DB") or "./fatturazione/parcelle.json")
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


def _ricerca_legale_lines(question: str) -> tuple[list[str], list[dict[str, Any]]]:
    intelligence = get_legal_intelligence()
    engine_ids = motori_per_query(question)
    source_ids = fonti_per_query(question)
    if not source_ids:
        source_ids = list(_DEFAULT_WEB_SOURCE_IDS)
    if not engine_ids:
        engine_ids = ["fonti_ufficiali", "procedurale_telematico"]

    motori = {row["id"]: row for row in intelligence.catalogo_motori()}
    lines = [
        "Ricerca legale: Lex puo' suggerire fonti ufficiali, motori interni e piste di verifica, ma non decide l'interpretazione finale.",
        "Motori pertinenti: " + ", ".join(
            motori.get(engine_id, {}).get("short_name") or engine_id for engine_id in engine_ids[:4]
        ) + ".",
    ]
    selected_sources: list[dict[str, Any]] = []
    for source_id in source_ids[:5]:
        source = FONTI_UFFICIALI.get(source_id)
        if not source:
            continue
        selected_sources.append(
            _source(
                f"Fonte ufficiale - {source.nome}",
                f"Area: {source.area}. Capacita: {source.capability}. URL: {source.official_url}",
                source_id=f"fonte:{source.id}",
                title=source.nome,
            )
        )
    if selected_sources:
        lines.append(
            "Fonti ufficiali suggerite: "
            + "; ".join(source["title"] for source in selected_sources)
            + "."
        )
    return lines, selected_sources


def _archivio_sentenze_lines(question: str) -> tuple[list[str], list[dict[str, Any]]]:
    gestore = get_giurisprudenza()
    stats = gestore.statistiche()
    rows = gestore.cerca(q=question)[:4] if _clean_spaces(question) else gestore.cerca()[:4]
    lines = [
        f"Archivio sentenze: {stats.get('totale_sentenze', 0)} provvedimenti indicizzati, {stats.get('fonti_attive', 0)} fonti attive.",
    ]
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
    sources = [
        _source(
            f"Archivio sentenze - {row.get('titolo') or row.get('organo_giudicante') or 'Pronuncia'}",
            f"Area: {row.get('area') or 'n.d.'}. Branca: {row.get('branca') or 'n.d.'}. Sintesi: {row.get('sintesi') or row.get('massima') or 'Provvedimento disponibile in archivio.'}",
            source_id=f"sentenza:{row.get('id') or row.get('hash') or idx}",
            title=row.get("titolo") or row.get("organo_giudicante") or "Pronuncia",
        )
        for idx, row in enumerate(rows)
    ]
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
    rows = cerca_applicazioni(q=question) if _clean_spaces(question) else catalogo_applicazioni()
    selected = rows[:5]
    lines = [f"Applicazioni e moduli: {len(catalogo_applicazioni())} voci nel catalogo operativo HACS."]
    if selected:
        lines.append(
            "Applicazioni utili: "
            + "; ".join(
                _truncate(
                    f"{row.get('title')} ({row.get('section_title') or row.get('workspace_kind') or 'modulo'})",
                    100,
                )
                for row in selected
            )
            + "."
        )
    sources = [
        _source(
            f"Applicazione - {row.get('title')}",
            f"Sezione: {row.get('section_title') or row.get('workspace_kind') or 'n.d.'}. Modalita: {row.get('access_mode') or 'n.d.'}. Stato: {row.get('status_label') or row.get('status') or 'n.d.'}.",
            source_id=f"applicazione:{row.get('id')}",
            title=str(row.get("title") or "Applicazione"),
        )
        for row in selected
    ]
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
    lines = ["RAG documentale locale: supporto disponibile sui documenti gia' indicizzati quando HACS gira sullo stesso host dei dati."]
    if rows:
        lines.append(
            "Documenti indicizzati pertinenti: "
            + "; ".join(_truncate(row.get("citation") or row.get("title") or "Documento", 110) for row in rows)
            + "."
        )
    else:
        lines.append("Nessun documento indicizzato pertinente rilevato per questa domanda.")
    return lines, rows[:4]


def build_lex_studio_context(question: str) -> dict[str, Any]:
    q = _clean_spaces(question)
    sections: list[str] = [
        "Lex deve restare sempre consultivo, non decisionale, e formulare solo suggerimenti, ipotesi operative, check-list, rischi e prossimi passi.",
        "Se manca il contesto o serve una verifica aggiornata sul web, Lex deve dirlo chiaramente e indicare le fonti ufficiali web piu' adatte senza inventare.",
    ]
    sources: list[dict[str, Any]] = []
    priority_sources: list[dict[str, Any]] = []
    live_source_ids: list[str] = []

    _append_section(sections, "Profilo studio", _studio_profile_lines())

    for title, builder in [
        ("Impostazioni studio", _settings_studio_lines),
        ("PEC e canali email", _pec_lines),
        ("Quadro operativo", _operational_lines),
        ("Fascicoli", lambda: _fascicoli_lines(q)),
        ("Clienti", lambda: _clienti_lines(q)),
        ("Agenda", lambda: _agenda_lines(q)),
        ("Soggetti", lambda: _soggetti_lines(q)),
        ("Scadenziario", lambda: _scadenziario_lines(q)),
        ("Template atti", lambda: _template_atti_lines(q)),
        ("Tariffario", lambda: _tariffario_lines(q)),
        ("Preventivi", lambda: _preventivi_lines(q)),
        ("Fatturazione", lambda: _fatturazione_lines(q)),
        ("Ricerca legale e fonti web", lambda: _ricerca_legale_lines(q)),
        ("Verifica live fonti ufficiali web", lambda: (
            lambda payload: (
                payload.get("lines") or [],
                payload.get("sources") or [],
            )
        )(build_live_official_web_context(q))),
        ("Archivio sentenze", lambda: _archivio_sentenze_lines(q)),
        ("Strumenti legali", lambda: _strumenti_legali_lines(q)),
        ("Applicazioni", lambda: _applicazioni_lines(q)),
        ("RAG documentale locale", lambda: _document_rag_lines(q)),
    ]:
        try:
            lines, section_sources = builder()
        except Exception as exc:
            current_app.logger.exception("Errore contesto Lex per sezione %s: %s", title, exc)
            lines, section_sources = ([f"{title}: contesto non disponibile in questo momento."], [])
        _append_section(sections, title, lines)
        if title == "Verifica live fonti ufficiali web":
            priority_sources.extend(section_sources or [])
        else:
            sources.extend(section_sources or [])

        if title == "Verifica live fonti ufficiali web":
            try:
                live_source_ids = [
                    str(item.get("id") or "").replace("live-web:", "").strip()
                    for item in section_sources or []
                    if str(item.get("id") or "").startswith("live-web:")
                ]
            except Exception:
                live_source_ids = []

    deduped_sources: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for row in [*priority_sources, *sources]:
        identifier = str(row.get("id") or row.get("citation") or "").strip()
        if not identifier or identifier in seen_ids:
            continue
        seen_ids.add(identifier)
        deduped_sources.append(row)

    return {
        "prompt_block": "\n".join(sections).strip(),
        "sources": deduped_sources[:24],
        "citations": [row.get("citation") for row in deduped_sources[:24] if row.get("citation")],
        "engine_ids": motori_per_query(q),
        "source_ids": list(dict.fromkeys([*fonti_per_query(q), *live_source_ids])),
    }
