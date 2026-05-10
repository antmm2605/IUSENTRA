from __future__ import annotations

from datetime import datetime
from typing import Any

from .base import BaseProvider
from lex.contracts import ProviderDraft

try:  # esportato anche per test legacy con monkeypatch
    from lex.tools.studio_data_gateway import build_cliente_answer, find_cliente
except Exception:  # pragma: no cover
    build_cliente_answer = None  # type: ignore[assignment]
    find_cliente = None  # type: ignore[assignment]


def _as_items(evidence: Any) -> list[Any]:
    if isinstance(evidence, dict):
        return list(evidence.get("items") or [])
    return list(getattr(evidence, "items", None) or [])


def _shorten(value: str, limit: int = 220) -> str:
    text = " ".join(str(value or "").split()).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _context_section(context: Any, key: str) -> Any:
    if isinstance(context, dict):
        structured = context.get("structured_context") or {}
        if isinstance(structured, dict) and key in structured:
            return structured.get(key)
        return context.get(key)
    return {}


def _context_dict(context: Any, key: str) -> dict[str, Any]:
    section = _context_section(context, key)
    return dict(section or {}) if isinstance(section, dict) else {}


def _section_rows(context: Any, key: str) -> list[dict[str, Any]]:
    sezioni = _context_section(context, "fascicolo_sezioni") or {}
    if key == "documenti_fascicolo":
        return list(sezioni.get(key) or _context_section(context, "documenti") or [])
    return list(sezioni.get(key) or [])


def _section_count(sezioni: dict[str, Any], key: str, fallback: int = 0) -> int:
    count_map = {
        "attivita_processuali": "attivita",
        "documenti_fascicolo": "documenti",
        "udienze_scadenze": "udienze_scadenze",
        "comunicazioni_cancelleria": "comunicazioni",
        "istanze": "istanze",
    }
    try:
        return int((sezioni.get("counts") or {}).get(count_map.get(key, ""), fallback) or fallback)
    except Exception:
        return fallback


def _row_title(row: dict[str, Any]) -> str:
    return str(
        row.get("titolo")
        or row.get("nome")
        or row.get("tipo_atto")
        or row.get("tipo")
        or "voce senza titolo"
    ).strip()


def _row_when(row: dict[str, Any]) -> str:
    return str(
        row.get("data_ora")
        or row.get("timestamp")
        or row.get("data")
        or row.get("data_documento")
        or row.get("data_caricamento")
        or ""
    ).strip()


def _describe_section_row(row: dict[str, Any]) -> str:
    titolo = _row_title(row)
    quando = _row_when(row)
    stato = str(row.get("stato") or row.get("esito") or row.get("signed_ui") or "").strip()
    parts = [titolo]
    if quando:
        parts.append(_format_dataora_italiana(quando) if "T" in quando else _format_data_italiana(quando))
    if stato:
        parts.append(stato.lower())
    return " - ".join(part for part in parts if part)


def _section_line(label: str, rows: list[dict[str, Any]], count: int) -> str:
    if count <= 0:
        return ""
    previews = [
        _describe_section_row(row)
        for row in rows[:5]
        if _describe_section_row(row)
    ]
    if previews:
        suffix = ""
        if count > len(previews):
            suffix = f" + {count - len(previews)} altre voci censite"
        return f"{label}: {count} voci; campione controllato: {'; '.join(previews)}{suffix}."
    return f"{label}: {count} voci."


def _format_data_italiana(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    normalized = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).strftime("%d/%m/%Y")
    except Exception:
        pass
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%Y %H:%M"):
        try:
            parsed = datetime.strptime(text, pattern)
            return parsed.strftime("%d/%m/%Y")
        except Exception:
            continue
    return text


def _format_dataora_italiana(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    normalized = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).strftime("%d/%m/%Y alle %H:%M")
    except Exception:
        pass
    for pattern in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            parsed = datetime.strptime(text, pattern)
            return parsed.strftime("%d/%m/%Y alle %H:%M")
        except Exception:
            continue
    return _format_data_italiana(text)


def _format_euro(value: Any) -> str:
    try:
        amount = float(value or 0.0)
    except Exception:
        amount = 0.0
    formatted = f"{amount:,.2f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"EUR {formatted}"


def _fascicolo_text(question: str, context: Any, title: str, summary: str) -> str:
    fascicolo = _context_section(context, "fascicolo") or {}
    documenti = list(_context_section(context, "documenti") or [])
    fascicolo_sezioni = dict(_context_section(context, "fascicolo_sezioni") or {})
    fascicolo_intelligence = _context_dict(context, "fascicolo_intelligence")
    conformita_fascicolo = _context_dict(context, "conformita_fascicolo")
    attivita_processuali = _section_rows(context, "attivita_processuali")
    documenti_fascicolo = _section_rows(context, "documenti_fascicolo")
    udienze_scadenze = _section_rows(context, "udienze_scadenze")
    comunicazioni_cancelleria = _section_rows(context, "comunicazioni_cancelleria")
    istanze = _section_rows(context, "istanze")
    agenda = list(_context_section(context, "agenda") or [])
    scadenziario = list(_context_section(context, "scadenziario") or _context_section(context, "scadenze") or [])

    if not fascicolo:
        return (
            "Per aiutarti bene sul fascicolo ho bisogno del riferimento corretto della pratica.\n"
            "Indicami almeno numero di ruolo, cliente oppure apri direttamente il fascicolo da cui vuoi partire.\n"
            "Appena ho il fascicolo giusto, ti restituisco quadro della pratica, documenti utili, scadenze e prossimo passo."
        )

    numero = str(fascicolo.get("numero") or fascicolo.get("id") or "").strip()
    titolo = str(fascicolo.get("titolo") or "").strip()
    oggetto = str(fascicolo.get("oggetto") or "").strip()
    cliente = str(fascicolo.get("cliente") or "").strip()
    controparte = str(fascicolo.get("controparte") or "").strip()
    tribunale = str(fascicolo.get("tribunale") or "").strip()
    stato = str(fascicolo.get("stato") or "").strip()
    prossima_udienza = _format_dataora_italiana(fascicolo.get("data_prossima_udienza"))
    documenti_count = _section_count(
        fascicolo_sezioni,
        "documenti_fascicolo",
        fallback=int(fascicolo.get("documenti_count") or len(documenti_fascicolo) or len(documenti) or 0),
    )

    lines = [
        f"Sto lavorando sul fascicolo {numero or 'senza numero'}{f' - {titolo}' if titolo else ''}.",
    ]
    if oggetto:
        lines.append(f"Oggetto: {oggetto}.")
    if cliente or controparte:
        parties = []
        if cliente:
            parties.append(f"assistito {cliente}")
        if controparte:
            parties.append(f"controparte {controparte}")
        lines.append("Parti rilevanti: " + "; ".join(parties) + ".")
    if tribunale or stato:
        details = []
        if tribunale:
            details.append(f"ufficio {tribunale}")
        if stato:
            details.append(f"stato {stato.lower()}")
        lines.append("Quadro attuale: " + ", ".join(details) + ".")
    if prossima_udienza:
        lines.append(f"Udienza o evento gia' fissato: {prossima_udienza}.")
    if documenti_count:
        lines.append(f"Documenti collegati: {documenti_count}.")
    elif title:
        lines.append(f"Riferimento disponibile: {title}.")
    if fascicolo_sezioni:
        section_lines = [
            _section_line(
                "Attivita' processuali",
                attivita_processuali,
                _section_count(fascicolo_sezioni, "attivita_processuali", fallback=len(attivita_processuali)),
            ),
            _section_line(
                "Documenti fascicolo",
                documenti_fascicolo or documenti,
                _section_count(fascicolo_sezioni, "documenti_fascicolo", fallback=len(documenti_fascicolo or documenti)),
            ),
            _section_line(
                "Udienze e scadenze",
                udienze_scadenze,
                _section_count(fascicolo_sezioni, "udienze_scadenze", fallback=len(udienze_scadenze)),
            ),
            _section_line(
                "Comunicazioni di cancelleria",
                comunicazioni_cancelleria,
                _section_count(fascicolo_sezioni, "comunicazioni_cancelleria", fallback=len(comunicazioni_cancelleria)),
            ),
            _section_line(
                "Istanze",
                istanze,
                _section_count(fascicolo_sezioni, "istanze", fallback=len(istanze)),
            ),
        ]
        lines.extend(line for line in section_lines if line)
    if fascicolo_intelligence:
        presidio = dict(fascicolo_intelligence.get("presidio") or {})
        if str(presidio.get("summary") or "").strip():
            lines.append(f"Presidio pratica: {presidio.get('summary')}.")
        if list(fascicolo_intelligence.get("giurisprudenza") or []):
            lines.append(
                f"Giurisprudenza collegata: {len(list(fascicolo_intelligence.get('giurisprudenza') or []))} riferimenti utili."
            )
    if conformita_fascicolo:
        general = dict(conformita_fascicolo.get("general") or {})
        if general:
            lines.append(
                "Conformita': "
                f"{conformita_fascicolo.get('readiness_label') or general.get('label') or 'Da verificare'} "
                f"({int(general.get('blocking_count') or 0)} blocchi, {int(general.get('warning_count') or 0)} avvisi)."
            )

    prossima_scadenza = next(
        (
            row for row in scadenziario
            if isinstance(row, dict) and (row.get("data") or row.get("data_scadenza") or row.get("scadenza"))
        ),
        None,
    )
    if prossima_scadenza:
        scadenza_data = _format_data_italiana(
            prossima_scadenza.get("data") or prossima_scadenza.get("data_scadenza") or prossima_scadenza.get("scadenza")
        )
        scadenza_titolo = str(
            prossima_scadenza.get("titolo") or prossima_scadenza.get("oggetto") or prossima_scadenza.get("descrizione") or "scadenza aperta"
        ).strip()
        lines.append(f"Scadenza da presidiare: {scadenza_titolo} ({scadenza_data}).")

    prossimo_impegno = next(
        (
            row for row in agenda
            if isinstance(row, dict) and (row.get("data_ora") or row.get("inizio") or row.get("quando"))
        ),
        None,
    )
    if prossimo_impegno:
        agenda_data = _format_dataora_italiana(
            prossimo_impegno.get("data_ora") or prossimo_impegno.get("inizio") or prossimo_impegno.get("quando")
        )
        agenda_titolo = str(
            prossimo_impegno.get("titolo") or prossimo_impegno.get("oggetto") or prossimo_impegno.get("tipo") or "attivita' pianificata"
        ).strip()
        lines.append(f"Attivita' in agenda: {agenda_titolo} ({agenda_data}).")

    haystack = str(question or "").lower()
    intelligent_next_actions = [
        str(item).strip() for item in list(fascicolo_intelligence.get("next_actions") or []) if str(item).strip()
    ]
    if intelligent_next_actions:
        next_step = intelligent_next_actions[0]
    elif "comunicaz" in haystack and comunicazioni_cancelleria:
        next_step = (
            "rivedere subito l'ultima comunicazione di cancelleria e verificare se apre termini, adempimenti o allegati mancanti."
        )
    elif "istanz" in haystack and istanze:
        next_step = "controllare l'istanza piu' recente e verificare esito, documenti collegati e prossima attivita' conseguente."
    elif "document" in haystack and documenti_count:
        next_step = "confermare che siano presenti atto principale, ultimo provvedimento e allegati essenziali richiamati nella richiesta."
    elif "udienz" in haystack and (prossima_udienza or udienze_scadenze):
        next_step = "prepara subito documenti essenziali, note d'udienza e verifiche finali del fascicolo."
    elif prossima_scadenza:
        next_step = "presidiare la scadenza aperta e verificare che il fascicolo abbia gia' atto, allegati e attivita' collegata."
    elif documenti_count == 0:
        next_step = "collegare almeno l'atto principale e il provvedimento piu' recente, cosi' il fascicolo diventa governabile."
    elif stato.upper() in {"DEFINITO", "ARCHIVIATO", "CHIUSO"}:
        next_step = "chiudere il presidio economico e verificare se restano adempimenti finali o archiviazione documentale."
    else:
        next_step = "verificare ultimo provvedimento, prossima attivita' e completezza documentale prima di procedere."
    lines.append(f"Prossimo passo consigliato: {next_step}")

    if summary and summary != "Nessuna evidenza disponibile." and not documenti_count:
        lines.append(f"Sintesi utile gia' disponibile: {summary}")

    return "\n".join(line for line in lines if line)


def _economic_text(question: str, context: Any, title: str, summary: str) -> str:
    economico = _context_dict(context, "economico")
    summary_data = dict(economico.get("summary") or {})
    if summary_data:
        scope = str(economico.get("scope") or "studio").strip() or "studio"
        fascicolo = dict(economico.get("fascicolo") or {})
        preventivi = list(economico.get("preventivi") or [])
        conferimenti = list(economico.get("conferimenti") or [])
        parcelle = list(economico.get("parcelle") or [])
        best_practice = dict(economico.get("best_practice") or {})
        lines = []
        if scope == "fascicolo":
            numero = str(fascicolo.get("numero") or "").strip()
            titolo = str(fascicolo.get("titolo") or "").strip()
            lines.append(
                f"Presidio economico del fascicolo {numero or 'senza numero'}{f' - {titolo}' if titolo else ''}."
            )
        else:
            lines.append("Presidio economico dello studio disponibile.")
        lines.append(
            f"Preventivi {int(summary_data.get('preventivi_count') or 0)}, "
            f"conferimenti {int(summary_data.get('conferimenti_count') or 0)}, "
            f"parcelle {int(summary_data.get('parcelle_count') or 0)}."
        )
        lines.append(
            "Valori: "
            f"preventivato {_format_euro(summary_data.get('totale_preventivato'))}, "
            f"conferito {_format_euro(summary_data.get('totale_conferito'))}, "
            f"fatturato {_format_euro(summary_data.get('totale_fatturato'))}, "
            f"incassato {_format_euro(summary_data.get('totale_incassato'))}, "
            f"saldo aperto {_format_euro(summary_data.get('saldo_aperto'))}."
        )
        if preventivi:
            first = dict(preventivi[0] or {})
            lines.append(
                f"Preventivo principale: {first.get('oggetto') or first.get('numero') or 'n.d.'} "
                f"(stato {str(first.get('stato') or 'n.d.').lower()}, totale {_format_euro(first.get('totale'))})."
            )
        if conferimenti:
            first = dict(conferimenti[0] or {})
            lines.append(
                f"Conferimento: {first.get('oggetto') or first.get('numero') or 'n.d.'} "
                f"(stato {str(first.get('stato') or 'n.d.').lower()}, compenso {_format_euro(first.get('compenso_pattuito'))})."
            )
        if parcelle:
            first = dict(parcelle[0] or {})
            lines.append(
                f"Parcella piu' recente: {first.get('numero') or 'n.d.'} "
                f"(stato {str(first.get('stato') or 'n.d.').lower()}, totale {_format_euro(first.get('totale'))})."
            )
        if best_practice:
            lines.append(
                f"Percorso economico collegato: {best_practice.get('label') or best_practice.get('title') or 'n.d.'}."
            )

        if int(summary_data.get("parcelle_scadute") or 0) > 0:
            next_step = "sollecitare gli incassi scaduti e riallineare subito le parcelle aperte."
        elif int(summary_data.get("preventivi_count") or 0) == 0:
            next_step = "aprire un preventivo guidato collegato alla pratica prima di proseguire."
        elif int(summary_data.get("conferimenti_count") or 0) == 0:
            next_step = "formalizzare il conferimento di incarico partendo dal preventivo gia' disponibile."
        elif int(summary_data.get("parcelle_count") or 0) == 0 and int(summary_data.get("conferimenti_count") or 0) > 0:
            next_step = "valutare se il fascicolo e' maturo per la prima parcella o per un acconto."
        elif float(summary_data.get("saldo_aperto") or 0.0) > 0:
            next_step = "presidiare il saldo aperto e verificare parcelle emesse, incassi e scadenze."
        else:
            next_step = "tenere allineati preventivo, conferimento e fatturazione sullo stesso fascicolo."
        lines.append(f"Prossimo passo consigliato: {next_step}")
        return "\n".join(line for line in lines if line)

    haystack = str(question or "").strip().lower()
    context_line = f"Contesto utile: {title}." if title else ""
    if "preventiv" in haystack:
        lines = [
            "Possiamo partire dal preventivo guidato.",
            context_line,
            "Per chiuderlo bene mi servono questi dati essenziali:",
            "- tipo di pratica o obiettivo dell'incarico;",
            "- cliente gia' censito oppure anagrafica rapida minima;",
            "- valore o scaglione, se la pratica lo richiede;",
            "- fase o attivita' da includere nel compenso;",
            "- eventuali anticipazioni, urgenze o canale online/studio.",
        ]
        if summary and summary != "Nessuna evidenza disponibile.":
            lines.append(f"Dato che ho gia': {summary}")
        lines.append("Se vuoi, dimmi subito oggetto della pratica e tipo di attivita': ti porto sul percorso corretto del preventivo.")
        return "\n".join(line for line in lines if line)
    if "tariffario" in haystack or any(token in haystack for token in ("onorario", "compenso", "scaglione")):
        lines = [
            "Per questa richiesta conviene partire dal tariffario, non da una risposta generica.",
            context_line,
            "Dimmi questi dati e ti do il percorso giusto:",
            "- natura della pratica;",
            "- valore o scaglione, se presente;",
            "- fase o attivita' da parametrizzare;",
            "- eventuale regime fiscale o compenso unico.",
        ]
        if summary and summary != "Nessuna evidenza disponibile.":
            lines.append(f"Riferimento economico disponibile: {summary}")
        lines.append("Appena li ho, posso distinguere tra calcolo tariffario, bozza preventivo o parcella.")
        return "\n".join(line for line in lines if line)
    if any(token in haystack for token in ("fattura", "parcella", "parcelle", "pagamento", "incasso", "saldo")):
        lines = [
            "Qui stiamo parlando di fatturazione o incasso, quindi il punto e' capire in quale stato economico sei.",
            context_line,
            "Verifica con me questi dati:",
            "- preventivo o conferimento di origine;",
            "- imponibile e anticipazioni;",
            "- stato fattura o parcella;",
            "- incasso atteso o gia' registrato.",
        ]
        if summary and summary != "Nessuna evidenza disponibile.":
            lines.append(f"Contesto economico disponibile: {summary}")
        lines.append("Se mi dai il riferimento economico o il cliente, ti dico subito il passo corretto.")
        return "\n".join(line for line in lines if line)
    return (
        "Percorso economico individuato.\n"
        f"{context_line}\n"
        f"Sintesi utile: {summary}\n"
        "Dimmi se vuoi lavorare su preventivo, tariffario, parcella o pagamento e ti porto sul flusso giusto."
    ).strip()


def _operational_text(question: str, context: Any, title: str, summary: str) -> str:
    studio_operativo = _context_dict(context, "studio_operativo")
    fascicolo_intelligence = _context_dict(context, "fascicolo_intelligence")
    fascicolo = _context_dict(context, "fascicolo")
    studio_summary = dict(studio_operativo.get("summary") or {})
    domains = dict(studio_operativo.get("domains") or {})
    actions = list(studio_operativo.get("actions") or [])
    hot_cases = list(studio_operativo.get("fascicoli_hot") or [])
    urgent_deadlines = list(studio_operativo.get("urgent_deadlines") or [])
    upcoming_appointments = list(studio_operativo.get("upcoming_appointments") or [])
    if fascicolo and fascicolo_intelligence:
        lines = [
            f"Cabina operativa del fascicolo {fascicolo.get('numero') or fascicolo.get('id') or 'senza riferimento'}.",
        ]
        presidio = dict(fascicolo_intelligence.get("presidio") or {})
        if str(presidio.get("summary") or "").strip():
            lines.append(f"Stato operativo: {presidio.get('summary')}.")
        if fascicolo_intelligence.get("scadenze_scadute"):
            first = dict(fascicolo_intelligence.get("scadenze_scadute")[0] or {})
            lines.append(
                f"Scadenza scaduta da riallineare: {first.get('titolo') or 'n.d.'} ({_format_data_italiana(first.get('data'))})."
            )
        elif fascicolo_intelligence.get("scadenze"):
            first = dict(fascicolo_intelligence.get("scadenze")[0] or {})
            lines.append(
                f"Prossima scadenza: {first.get('titolo') or 'n.d.'} ({_format_data_italiana(first.get('data'))})."
            )
        if fascicolo_intelligence.get("appuntamenti"):
            first = dict(fascicolo_intelligence.get("appuntamenti")[0] or {})
            lines.append(
                f"Appuntamento o udienza: {first.get('titolo') or 'n.d.'} ({_format_dataora_italiana(first.get('data_ora'))})."
            )
        next_actions = [str(item).strip() for item in list(fascicolo_intelligence.get("next_actions") or []) if str(item).strip()]
        if next_actions:
            lines.append(f"Prossimo passo consigliato: {next_actions[0]}")
        return "\n".join(line for line in lines if line)

    lines = ["Cabina operativa dello studio aggiornata."]
    if studio_summary:
        lines.append(
            f"Oggi abbiamo {int(studio_summary.get('scadenze_urgenti') or 0)} scadenze urgenti, "
            f"{int(studio_summary.get('appuntamenti_orizzonte') or 0)} appuntamenti in orizzonte e "
            f"{int(studio_summary.get('fascicoli_attenzionati') or 0)} fascicoli attenzionati."
        )
    if domains:
        lines.append(
            "Copertura studio: "
            f"{int((domains.get('clienti') or {}).get('total') or 0)} clienti, "
            f"{int((domains.get('soggetti') or {}).get('total') or 0)} soggetti, "
            f"{int((domains.get('fascicoli') or {}).get('total') or 0)} fascicoli, "
            f"{int((domains.get('preventivi') or {}).get('total') or 0)} preventivi, "
            f"{int((domains.get('parcelle') or {}).get('total') or 0)} parcelle."
        )
    if actions:
        first = dict(actions[0] or {})
        lines.append(
            f"Priorita' corrente: {first.get('title') or 'n.d.'}. {first.get('description') or ''}".strip()
        )
    elif urgent_deadlines:
        first = dict(urgent_deadlines[0] or {})
        lines.append(
            f"Termine da presidiare subito: {first.get('titolo') or 'n.d.'} ({_format_data_italiana(first.get('data'))})."
        )
    elif hot_cases:
        first = dict(hot_cases[0] or {})
        lines.append(
            f"Fascicolo da attenzionare: {first.get('titolo') or first.get('numero') or 'n.d.'}."
        )
    elif upcoming_appointments:
        first = dict(upcoming_appointments[0] or {})
        lines.append(
            f"Prossimo impegno: {first.get('titolo') or 'n.d.'} ({_format_dataora_italiana(first.get('data_ora'))})."
        )
    elif title or summary:
        lines.append(f"Evidenza principale: {title or 'n.d.'}. {summary}".strip())
    return "\n".join(line for line in lines if line)


def _compliance_text(question: str, context: Any, title: str, summary: str) -> str:
    compliance = _context_dict(context, "conformita_fascicolo")
    if compliance:
        general = dict(compliance.get("general") or {})
        sections = dict(compliance.get("sections") or {})
        lines = [
            f"Responsabile di conformita': {compliance.get('readiness_label') or compliance.get('summary') or 'verifica disponibile'}.",
        ]
        if general:
            lines.append(
                f"Stato {str(general.get('label') or 'Da verificare').lower()}: "
                f"punteggio {int(general.get('score') or 0)}/100, "
                f"blocchi {int(general.get('blocking_count') or 0)}, "
                f"avvisi {int(general.get('warning_count') or 0)}."
            )
        if sections:
            section_parts = []
            for key in ("processuale", "documentale", "tecnico_pst", "redazionale"):
                section = dict(sections.get(key) or {})
                label = str(section.get("label") or key).strip()
                state = str(section.get("state") or "ok").strip().lower()
                if not label:
                    continue
                section_parts.append(f"{label}: {state}")
            if section_parts:
                lines.append("Aree controllate: " + "; ".join(section_parts) + ".")
        blocking = [str(item.get("title") or "").strip() for item in list(compliance.get("blocking_issues") or []) if str(item.get("title") or "").strip()]
        warning = [str(item.get("title") or "").strip() for item in list(compliance.get("warning_issues") or []) if str(item.get("title") or "").strip()]
        missing_docs = [
            str(item.get("label") or item.get("key") or "").strip()
            for item in list(compliance.get("missing_documents") or [])
            if str(item.get("label") or item.get("key") or "").strip()
        ]
        if blocking:
            lines.append("Blocchi principali: " + "; ".join(blocking[:2]) + ".")
        elif warning:
            lines.append("Verifiche aperte: " + "; ".join(warning[:2]) + ".")
        if missing_docs:
            lines.append("Documenti richiesti mancanti: " + ", ".join(missing_docs[:3]) + ".")
        prepare_gate = dict((compliance.get("action_gates") or {}).get("prepare_deposit") or {})
        if prepare_gate.get("applicable"):
            status = "pronto" if prepare_gate.get("allowed") else "non pronto"
            reason = str(prepare_gate.get("reason") or "").strip()
            lines.append(f"Pre-deposito: {status}. {reason}".strip())
        next_steps = [str(item).strip() for item in list(compliance.get("next_steps") or []) if str(item).strip()]
        if next_steps:
            lines.append(f"Prossimo passo consigliato: {next_steps[0]}")
        return "\n".join(line for line in lines if line)
    return (
        "Esito operativo governato\n"
        f"- Richiesta: {question or 'non specificata'}\n"
        f"- Evidenza principale: {title or 'non disponibile'}\n"
        f"- Osservazione: {summary}\n"
        "- Azione suggerita: eseguire il controllo tecnico o la verifica del fascicolo prima del passo successivo."
    )


def build_sollecito_pagamento_template(context: Any) -> str:
    """Bozza italiana deterministica di sollecito pagamento."""
    from datetime import date as _date
    oggi = _format_data_italiana(_date.today().isoformat())
    controparte = "[Nome e Cognome / Ragione sociale]"
    importo = "[€ importo]"
    scadenza_originale = "[data originale di scadenza]"
    avvocato = "[Studio Legale / Avv. Nome Cognome]"
    if isinstance(context, dict):
        controparte = str(context.get("controparte") or controparte)
        importo = str(context.get("importo") or importo)
        scadenza_originale = str(context.get("scadenza_originale") or scadenza_originale)
        avvocato = str(context.get("avvocato") or avvocato)
    return f"""**BOZZA — SOLLECITO DI PAGAMENTO**

---

{avvocato}
[Via e numero civico dello studio]
[CAP, Città, Provincia]

{oggi}

**Spett.le**
{controparte}
[Indirizzo, CAP, Città]

---

**Oggetto: Sollecito di pagamento** — somma di {importo}

---

Con la presente La sollecitiamo cortesemente a voler provvedere al pagamento della somma di {importo}, il cui versamento era previsto entro il {scadenza_originale}, e che risulta ad oggi ancora non corrisposto.

**La invitiamo pertanto a regolarizzare la Sua posizione entro e non oltre 10 (dieci) giorni** dal ricevimento della presente, accreditando quanto dovuto sul conto indicato di seguito:

> IBAN: [IBAN dello studio/cliente]
> Intestatario: [Nome intestatario]
> Causale: [causale pagamento]

Qualora entro il termine indicato non si provveda al pagamento, saremo costretti ad adottare le misure legali necessarie per il recupero del credito, con aggravio di spese a Suo carico.

Confidiamo in una pronta risposta.

Distinti saluti,

{avvocato}

---
> **Dati da completare prima dell'invio:**
> - Dati completi del destinatario
> - Importo esatto e data di scadenza originale
> - IBAN e causale di pagamento
> - Eventuale riferimento a fattura o contratto"""


def build_pec_formale_template(context: Any) -> str:
    """Bozza italiana deterministica di PEC formale."""
    from datetime import date as _date
    oggi = _format_data_italiana(_date.today().isoformat())
    destinatario = "[nome@pec.destinatario.it]"
    oggetto_pec = "[Oggetto della PEC]"
    corpo = "[Testo del messaggio PEC — DA COMPLETARE]"
    avvocato = "[Studio Legale / Avv. Nome Cognome]"
    if isinstance(context, dict):
        destinatario = str(context.get("destinatario") or destinatario)
        oggetto_pec = str(context.get("oggetto_pec") or oggetto_pec)
        corpo = str(context.get("corpo") or corpo)
        avvocato = str(context.get("avvocato") or avvocato)
    return f"""**BOZZA — PEC FORMALE**

---

**A:** {destinatario}
**Da:** [pec@studiolegale.it]
**Data:** {oggi}
**Oggetto:** {oggetto_pec}

---

Con la presente comunicazione a mezzo PEC si notifica quanto segue:

{corpo}

Per qualsiasi comunicazione relativa alla presente, si prega di rispondere esclusivamente all'indirizzo PEC del mittente.

Distinti saluti,

{avvocato}
[Indirizzo e recapiti dello studio]
[PEC: pec@studiolegale.it]

---
> **Dati da completare prima dell'invio:**
> - Indirizzo PEC del destinatario verificato su INI-PEC o ReGINde
> - Oggetto della PEC (deve descrivere sinteticamente il contenuto)
> - Testo completo del messaggio
> - Allegare documenti pertinenti se necessario"""


def build_lettera_cliente_template(context: Any) -> str:
    """Bozza italiana di lettera informativa al cliente."""
    from datetime import date as _date
    oggi = _format_data_italiana(_date.today().isoformat())
    cliente = "[Nome e Cognome cliente]"
    oggetto = "[oggetto della comunicazione]"
    avvocato = "[Studio Legale / Avv. Nome Cognome]"
    if isinstance(context, dict):
        cliente = str(context.get("cliente") or cliente)
        oggetto = str(context.get("oggetto") or oggetto)
        avvocato = str(context.get("avvocato") or avvocato)
    return f"""**BOZZA — LETTERA INFORMATIVA AL CLIENTE**

---

{avvocato}
[Via e numero civico dello studio]
[CAP, Città, Provincia]
[Tel. — Email — PEC dello studio]

{oggi}

**Gentile**
{cliente}
[Indirizzo]

---

**Oggetto:** {oggetto}

---

Facendo seguito ai recenti contatti e ai colloqui intercorsi, con la presente La informiamo dell'evoluzione della Sua pratica e degli aggiornamenti più rilevanti.

[Testo descrittivo dell'aggiornamento — DA COMPLETARE]

**Prossimi passi:**

1. [Prima azione prevista — DA COMPLETARE]
2. [Eventuale seconda azione — DA COMPLETARE]

Restiamo a Sua disposizione per qualsiasi chiarimento.

Cordiali saluti,

{avvocato}

---
> **Dati da completare prima dell'invio:**
> - Dati completi del cliente
> - Contenuto dell'aggiornamento
> - Prossimi passi concordati"""


def build_contestazione_fattura_template(context: Any) -> str:
    """Bozza italiana di contestazione fattura."""
    from datetime import date as _date
    oggi = _format_data_italiana(_date.today().isoformat())
    fornitore = "[Nome fornitore / Ragione sociale]"
    numero_fattura = "[numero fattura]"
    importo = "[€ importo]"
    motivo = "[motivo della contestazione]"
    avvocato = "[Studio Legale / Avv. Nome Cognome]"
    if isinstance(context, dict):
        fornitore = str(context.get("fornitore") or fornitore)
        numero_fattura = str(context.get("numero_fattura") or numero_fattura)
        importo = str(context.get("importo") or importo)
        motivo = str(context.get("motivo") or motivo)
        avvocato = str(context.get("avvocato") or avvocato)
    return f"""**BOZZA — CONTESTAZIONE FATTURA**

---

{avvocato}
[Via e numero civico dello studio]
[CAP, Città, Provincia]

{oggi}

**Spett.le**
{fornitore}
[Indirizzo]

---

**Oggetto: Contestazione fattura n. {numero_fattura} — importo {importo}**

---

Con la presente, il sottoscritto/la sottoscritta {avvocato} contesta formalmente la fattura n. {numero_fattura} dell'importo di {importo}, in quanto: {motivo}.

**Chiediamo pertanto:**

1. La rettifica o l'annullamento della fattura entro 15 giorni dal ricevimento della presente
2. L'emissione di nota di credito o fattura corretta
3. Eventuale restituzione di quanto già pagato in eccesso

In assenza di riscontro nel termine indicato, saremo costretti ad adire le competenti sedi legali.

Distinti saluti,

{avvocato}

---
> **Dati da completare prima dell'invio:**
> - Dati completi del fornitore
> - Numero e data della fattura contestata
> - Motivazione specifica della contestazione
> - Importo contestato"""


def build_richiesta_documenti_template(context: Any) -> str:
    """Bozza italiana di richiesta documenti."""
    from datetime import date as _date
    oggi = _format_data_italiana(_date.today().isoformat())
    destinatario = "[Nome e Cognome / Ente / Società]"
    documenti = "[elenco dei documenti richiesti]"
    motivo = "[motivo della richiesta]"
    avvocato = "[Studio Legale / Avv. Nome Cognome]"
    if isinstance(context, dict):
        destinatario = str(context.get("destinatario") or destinatario)
        documenti = str(context.get("documenti") or documenti)
        motivo = str(context.get("motivo") or motivo)
        avvocato = str(context.get("avvocato") or avvocato)
    return f"""**BOZZA — RICHIESTA DOCUMENTI**

---

{avvocato}
[Via e numero civico dello studio]
[CAP, Città, Provincia]

{oggi}

**Spett.le / Egregio**
{destinatario}
[Indirizzo]

---

**Oggetto: Richiesta di trasmissione documenti**

---

Con la presente, in qualità di [ruolo/qualifica — DA COMPLETARE], Le chiediamo la trasmissione dei seguenti documenti:

{documenti}

La richiesta è motivata da: {motivo}.

**La invitiamo a trasmettere i documenti richiesti entro 15 (quindici) giorni** dal ricevimento della presente, all'indirizzo email/PEC sotto indicato.

[Email / PEC di destinazione]

In mancanza di riscontro, ci riserviamo di adottare le azioni legali necessarie per ottenere la documentazione.

Distinti saluti,

{avvocato}

---
> **Dati da completare prima dell'invio:**
> - Dati completi del destinatario
> - Elenco preciso dei documenti richiesti
> - Motivazione giuridica della richiesta
> - Indirizzo di trasmissione"""


def build_invito_a_stipula_template(context: Any) -> str:
    """Bozza italiana di invito formale a stipula contratto."""
    from datetime import date as _date
    oggi = _format_data_italiana(_date.today().isoformat())
    destinatario = "[Nome e Cognome / Ragione sociale]"
    tipo_contratto = "[tipo di contratto]"
    data_stipula = "[data proposta per la stipula]"
    avvocato = "[Studio Legale / Avv. Nome Cognome]"
    if isinstance(context, dict):
        destinatario = str(context.get("destinatario") or destinatario)
        tipo_contratto = str(context.get("tipo_contratto") or tipo_contratto)
        data_stipula = str(context.get("data_stipula") or data_stipula)
        avvocato = str(context.get("avvocato") or avvocato)
    return f"""**BOZZA — INVITO FORMALE A STIPULA**

---

{avvocato}
[Via e numero civico dello studio]
[CAP, Città, Provincia]

{oggi}

**Spett.le**
{destinatario}
[Indirizzo]

---

**Oggetto: Invito a stipulare {tipo_contratto}**

---

Con la presente, il sottoscritto/la sottoscritta {avvocato}, in rappresentanza di [Nome cliente — DA COMPLETARE], La invita formalmente a procedere alla stipula del {tipo_contratto} nelle condizioni già concordate tra le parti.

**Si propone la stipula per il giorno {data_stipula}**, presso [luogo — DA COMPLETARE], o in altra data da concordare entro 10 giorni dal ricevimento della presente.

Si allega bozza del contratto per presa visione [se disponibile].

In assenza di riscontro nel termine indicato, il nostro assistito si riserva di revocare la proposta contrattuale e di agire per il risarcimento dei danni eventualmente subiti.

Distinti saluti,

{avvocato}

---
> **Dati da completare prima dell'invio:**
> - Dati del cliente rappresentato
> - Tipo specifico di contratto
> - Data e luogo proposti per la stipula
> - Eventuale allegato bozza contratto"""


def build_riscontro_comunicazione_template(context: Any) -> str:
    """Bozza italiana di riscontro a comunicazione ricevuta."""
    from datetime import date as _date
    oggi = _format_data_italiana(_date.today().isoformat())
    mittente_originale = "[Mittente della comunicazione originale]"
    data_comunicazione = "[data della comunicazione cui si risponde]"
    oggetto_originale = "[oggetto della comunicazione originale]"
    avvocato = "[Studio Legale / Avv. Nome Cognome]"
    if isinstance(context, dict):
        mittente_originale = str(context.get("mittente_originale") or mittente_originale)
        data_comunicazione = str(context.get("data_comunicazione") or data_comunicazione)
        oggetto_originale = str(context.get("oggetto_originale") or oggetto_originale)
        avvocato = str(context.get("avvocato") or avvocato)
    return f"""**BOZZA — RISCONTRO A COMUNICAZIONE**

---

{avvocato}
[Via e numero civico dello studio]
[CAP, Città, Provincia]

{oggi}

**Spett.le / Egregio**
{mittente_originale}
[Indirizzo]

---

**Oggetto: Riscontro alla comunicazione del {data_comunicazione} — {oggetto_originale}**

---

In riscontro alla Sua comunicazione del {data_comunicazione}, con la presente ci premuriamo di rappresentare quanto segue.

[Contenuto della risposta — DA COMPLETARE]

Quanto sopra è precisato a fini di piena chiarezza e senza alcuna rinuncia ai diritti del nostro assistito.

Restiamo a disposizione per eventuali chiarimenti.

Distinti saluti,

{avvocato}

---
> **Dati da completare prima dell'invio:**
> - Dati completi del destinatario
> - Data e contenuto della comunicazione originale
> - Testo della risposta
> - Eventuali documenti da allegare"""


def build_diffida_messa_in_mora_template(context: Any) -> str:
    """Bozza italiana deterministica di diffida e messa in mora.

    Usata come fallback quando il modello AI produce output in inglese.
    Tutti i campi sensibili sono segnaposto in parentesi quadre.
    """
    from datetime import date as _date
    oggi = _format_data_italiana(_date.today().isoformat())
    controparte = "[Nome e Cognome / Ragione sociale della controparte]"
    indirizzo = "[Indirizzo, CAP, Città, Provincia]"
    avvocato = "[Studio Legale / Avv. Nome Cognome]"
    oggetto_credito = "[descrizione del credito/obbligo inademputo]"
    importo = "[€ importo]"
    termine = "[X] giorni"

    if isinstance(context, dict):
        controparte = str(context.get("controparte") or controparte)
        indirizzo = str(context.get("indirizzo_controparte") or indirizzo)
        avvocato = str(context.get("avvocato") or avvocato)
        oggetto_credito = str(context.get("oggetto") or oggetto_credito)
        importo = str(context.get("importo") or importo)
        termine_giorni = context.get("termine_giorni")
        if termine_giorni:
            termine = f"{termine_giorni} giorni"

    return f"""**BOZZA — DIFFIDA E MESSA IN MORA**

---

{avvocato}
[Via e numero civico dello studio]
[CAP, Città, Provincia]
[C.F. / P.IVA dello studio]
[Tel. — Email — PEC dello studio]

{oggi}

**Spett.le**
{controparte}
{indirizzo}

---

**Oggetto: DIFFIDA E MESSA IN MORA** — {oggetto_credito}

---

Con la presente, il sottoscritto/la sottoscritta {avvocato}, in qualità di legale rappresentante / procuratore di [Nome del cliente — da completare], si invita e diffida formalmente la S.V. / codesta Spettabile Società ad adempiere, entro e non oltre {termine} dal ricevimento della presente, all'obbligo di {oggetto_credito}, per un importo complessivo di {importo}.

**Fatto**

[Esporre in modo sintetico e cronologico i fatti rilevanti: rapporto contrattuale, obbligazione assunta, inadempimento verificatosi, eventuali precedenti solleciti già inviati — DA COMPLETARE]

**Diritto**

Ai sensi dell'art. 1219 c.c., la presente lettera costituisce formale messa in mora.
[Se applicabile: richiamare la clausola contrattuale o normativa pertinente — DA COMPLETARE]

**Richiesta formale**

Si diffida la S.V. a:

1. [Prima richiesta specifica — DA COMPLETARE]
2. [Eventuale seconda richiesta — DA COMPLETARE]

il tutto entro il termine perentorio di {termine} dalla ricezione della presente.

**Avvertenza**

in difetto di riscontro positivo nel termine indicato, il sottoscritto / la sottoscritta si riserva di agire in ogni sede competente — civile, penale, amministrativa — con ogni conseguenza di legge, ivi incluse le spese legali.

---

Con osservanza,

{avvocato}

---
> **Dati da completare prima dell'invio:**
> - Nome e dati completi del cliente mittente
> - Dati completi della controparte (CF/PI se società)
> - Descrizione precisa del credito/obbligo inademputo
> - Importo esatto e calcolo interessi moratori (art. 1224 c.c.) se applicabile
> - Termine congruo (solitamente 15–30 giorni)
> - Firma digitale o autografa dell'avvocato
> - Allegati: documenti comprovanti il credito/obbligo"""


def _studio_data_lookup_text(q: str, context: Any) -> str:
    """Ricerca dati cliente/fascicolo nei dati interni dello studio."""
    try:
        if build_cliente_answer is None or find_cliente is None:
            raise RuntimeError("studio_data_gateway non disponibile")
        return build_cliente_answer(find_cliente(q))
    except Exception:
        pass

    find_fascicoli = None
    try:
        from lex.tools.studio_data_gateway import find_cliente as search_cliente, find_fascicoli_by_cliente

        find_fascicoli = find_fascicoli_by_cliente
        matches = search_cliente(q)
    except Exception:
        matches = []

    if not matches:
        nome = q.strip()
        return (
            f"Non ho trovato nessun cliente corrispondente a **{nome}** nell'anagrafica dello studio.\n\n"
            "Se il nome è parziale, prova con cognome e nome separati. "
            "I dati sono ricercati solo nei registri interni dello studio — nessuna fonte esterna viene consultata."
        )

    if len(matches) > 1:
        nomi = [m.nome_completo for m in matches[:5]]
        lista = "\n".join(f"- {n}" for n in nomi)
        return (
            f"Ho trovato {len(matches)} clienti che corrispondono alla ricerca:\n\n{lista}\n\n"
            "Specifica il nome completo per ottenere i dettagli."
        )

    c = matches[0]
    lines = [f"**{c.nome_completo}**"]
    if c.tipo:
        lines.append(f"Tipo: {c.tipo}")
    if c.stato:
        lines.append(f"Stato: {c.stato}")
    if c.codice_fiscale:
        lines.append(f"CF: {c.codice_fiscale}")
    if c.partita_iva:
        lines.append(f"P.IVA: {c.partita_iva}")
    if c.email:
        lines.append(f"Email: {c.email}")
    if c.pec:
        lines.append(f"PEC: {c.pec}")
    if c.telefono:
        lines.append(f"Tel: {c.telefono}")
    if c.indirizzo:
        lines.append(f"Indirizzo: {c.indirizzo}")
    if c.avvocato_referente:
        lines.append(f"Referente: {c.avvocato_referente}")

    try:
        if find_fascicoli is None:
            raise RuntimeError("ricerca fascicoli non disponibile")
        fascicoli = find_fascicoli(c.id, limit=5)
        if fascicoli:
            rgs = [f"RG {f.numero_rg}/{f.anno_rg}" if f.numero_rg else f.titolo for f in fascicoli]
            lines.append(f"Fascicoli ({len(fascicoli)}): {', '.join(rgs)}")
    except Exception:
        if c.n_fascicoli:
            lines.append(f"Fascicoli: {c.n_fascicoli}")

    return "\n".join(lines)


def _generic_operational_text(q: str, context: Any, title: str, summary: str) -> str:
    """Fallback operativo generico — mai espone nomi tecnici interni."""
    if title and summary and summary != "Nessuna evidenza disponibile.":
        return f"{title}\n\n{summary}"
    if title:
        return title
    return (
        "Non ho trovato informazioni sufficienti per rispondere a questa domanda "
        "con i dati disponibili nello studio. Prova a riformulare la richiesta "
        "o indica un fascicolo, un cliente o una scadenza specifica."
    )


class DeterministicProvider(BaseProvider):
    provider_name = "deterministic"

    def generate(self, request, context, evidence, workflow):
        items = _as_items(evidence)
        preview = items[0] if items else None
        title = getattr(preview, "title", "") if preview is not None else ""
        content = getattr(preview, "content", "") if preview is not None else ""
        summary = _shorten(content or "Nessuna evidenza disponibile.")
        q = str(getattr(request, "query", "") or "").strip()

        if workflow in {"next_action", "cabina"}:
            text = _operational_text(q, context, title, summary)
        elif workflow in {"economico"}:
            text = _economic_text(q, context, title, summary)
        elif workflow in {"fascicolo"}:
            text = _fascicolo_text(q, context, title, summary)
        elif workflow in {"telematico_status", "deposito_telematico", "compliance"}:
            text = _compliance_text(q, context, title, summary)
        elif workflow == "studio_data_lookup":
            text = _studio_data_lookup_text(q, context)
        elif workflow in {"drafting_legal_letter", "lettera", "bozza_lettera", "pec_comunicazioni"}:
            q_lower = q.lower()
            if "sollecito" in q_lower and "diffida" not in q_lower:
                text = build_sollecito_pagamento_template(context)
            elif "pec" in q_lower and "diffida" not in q_lower:
                text = build_pec_formale_template(context)
            elif "contestazion" in q_lower:
                text = build_contestazione_fattura_template(context)
            elif "richiesta document" in q_lower or "richiesta dei document" in q_lower:
                text = build_richiesta_documenti_template(context)
            elif "invito" in q_lower and "stipula" in q_lower:
                text = build_invito_a_stipula_template(context)
            elif "riscontro" in q_lower or "risposta a" in q_lower:
                text = build_riscontro_comunicazione_template(context)
            elif "lettera" in q_lower and "cliente" in q_lower:
                text = build_lettera_cliente_template(context)
            else:
                text = build_diffida_messa_in_mora_template(context)
        else:
            text = _generic_operational_text(q, context, title, summary)

        return ProviderDraft(
            text=text,
            metadata={
                "provider": self.provider_name,
                "workflow": workflow,
                "evidence_count": len(items),
                "mode": "fast-path",
            },
        )
