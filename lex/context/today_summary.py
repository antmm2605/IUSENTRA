from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from flask import current_app

from pct.legal_intelligence import motori_per_query
from web.services import assistente_studio_context as studio_context


_TODAY_OVERVIEW_QUERY = (
    "oggi quadro operativo studio agenda scadenze fascicoli clienti soggetti comunicazioni "
    "pec impostazioni sincronizzazione fatturazione preventivi pagamenti tariffario template atti "
    "catalogo atti ricerca legale archivio sentenze strumenti legali applicazioni"
)

_TODAY_SECTION_FACTORIES: tuple[tuple[str, Callable[[str], Callable[[], tuple[list[str], list[dict[str, Any]]]]]], ...] = (
    ("Quadro operativo", lambda question: studio_context._operational_lines),
    ("Agenda", lambda question: lambda: studio_context._agenda_lines(question)),
    ("Scadenziario", lambda question: lambda: studio_context._scadenziario_lines(question)),
    ("Fascicoli", lambda question: lambda: studio_context._fascicoli_lines(question)),
    ("Clienti", lambda question: lambda: studio_context._clienti_lines(question)),
    ("Soggetti", lambda question: lambda: studio_context._soggetti_lines(question)),
    ("PEC e canali email", lambda question: studio_context._pec_lines),
    ("Fatturazione", lambda question: lambda: studio_context._fatturazione_lines(question)),
    ("Preventivi", lambda question: lambda: studio_context._preventivi_lines(question)),
    ("Tariffario", lambda question: lambda: studio_context._tariffario_lines(question)),
    ("Template atti", lambda question: lambda: studio_context._template_atti_lines(question)),
    ("Applicazioni", lambda question: lambda: studio_context._applicazioni_lines(question)),
    ("Ricerca legale e fonti web", lambda question: lambda: studio_context._ricerca_legale_lines(question)),
    ("Archivio sentenze", lambda question: lambda: studio_context._archivio_sentenze_lines(question)),
    ("Strumenti legali", lambda question: lambda: studio_context._strumenti_legali_lines(question)),
    ("Impostazioni studio", lambda question: studio_context._settings_studio_lines),
)


def build_today_operational_summary(*, question: str = "") -> dict[str, Any]:
    effective_question = studio_context._clean_spaces(question) or "oggi cosa dobbiamo fare"
    section_query = studio_context._clean_spaces(f"{effective_question} {_TODAY_OVERVIEW_QUERY}")
    today_label = datetime.now().strftime("%d/%m/%Y")
    sections: list[str] = [
        f"Lex sta preparando il quadro operativo della giornata del {today_label}.",
        "Apri con un riepilogo professionale di oggi, ordinato per priorita' immediate e prossime attivita'.",
        "La risposta deve toccare, se ci sono dati utili, scadenze urgenti, udienze e agenda, fascicoli attivi, clienti e soggetti rilevanti, comunicazioni e PEC, fatturazione, preventivi, pagamenti, template e catalogo atti, ricerca legale, archivio sentenze, strumenti legali, impostazioni operative e sincronizzazioni.",
        "Se un'area oggi non mostra elementi utili, dichiaralo in una riga e passa oltre senza riempitivi.",
    ]
    sources: list[dict[str, Any]] = []

    for title, factory in _TODAY_SECTION_FACTORIES:
        try:
            lines, section_sources = studio_context._cached_section_payload(title, section_query, factory(section_query))
        except Exception as exc:
            current_app.logger.exception("Errore overview giornaliera Lex per sezione %s: %s", title, exc)
            lines, section_sources = ([f"{title}: contesto non disponibile in questo momento."], [])
        studio_context._append_section(sections, title, lines)
        sources.extend(section_sources or [])

    deduped_sources = studio_context._dedupe_sources(sources)
    selected_sources = deduped_sources[:14]
    return {
        "prompt_block": "\n".join(sections).strip(),
        "sources": selected_sources,
        "citations": [row.get("citation") for row in selected_sources if row.get("citation")],
        "engine_ids": motori_per_query(section_query),
        "source_ids": [str(row.get("id") or "").strip() for row in selected_sources if str(row.get("id") or "").strip()],
        "focus_label": "quadro operativo di oggi",
        "focus_topic": "today_operational_overview",
        "effective_question": effective_question,
        "web_fallback_used": False,
        "web_execution_requested": False,
        "lead_text": "Ti faccio subito il quadro operativo di oggi.",
    }


__all__ = ["build_today_operational_summary"]
