from __future__ import annotations

from datetime import datetime
from typing import Any

from .base import BaseProvider
from lex.contracts import ProviderDraft


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

Con la presente, il sottoscritto/la sottoscritta {avvocato}, in qualità di legale rappresentante / procuratore di [Nome del cliente — da completare], con la presente **Si invita e diffida formalmente** la S.V. / codesta Spettabile Società ad adempiere, entro e non oltre {termine} dal ricevimento della presente, all'obbligo di {oggetto_credito}, per un importo complessivo di {importo}.

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

In difetto di riscontro positivo nel termine indicato, il sottoscritto / la sottoscritta si riserva di agire in ogni sede competente — civile, penale, amministrativa — con ogni conseguenza di legge, ivi incluse le spese legali.

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
        elif workflow in {"telematico_status", "compliance"}:
            text = _compliance_text(q, context, title, summary)
        elif workflow in {"drafting_legal_letter", "lettera", "bozza_lettera"}:
            text = build_diffida_messa_in_mora_template(context)
        else:
            text = (
                f"Risposta deterministica per workflow '{workflow}'.\n"
                f"Evidenza principale: {title or 'non disponibile'}\n"
                f"Sintesi: {summary}"
            )

        return ProviderDraft(
            text=text,
            metadata={
                "provider": self.provider_name,
                "workflow": workflow,
                "evidence_count": len(items),
                "mode": "fast-path",
            },
        )
