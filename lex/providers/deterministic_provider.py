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
    preview = _describe_section_row(rows[0]) if rows else ""
    if preview:
        return f"{label}: {count} voci; ultima o prossima rilevante {preview}."
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


def _fascicolo_text(question: str, context: Any, title: str, summary: str) -> str:
    fascicolo = _context_section(context, "fascicolo") or {}
    documenti = list(_context_section(context, "documenti") or [])
    fascicolo_sezioni = dict(_context_section(context, "fascicolo_sezioni") or {})
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
    if "comunicaz" in haystack and comunicazioni_cancelleria:
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


def _economic_text(question: str, title: str, summary: str) -> str:
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
            text = (
                "Quadro operativo sintetico\n"
                f"- Richiesta: {q or 'non specificata'}\n"
                f"- Evidenza principale: {title or 'non disponibile'}\n"
                f"- Sintesi: {summary}\n"
                "- Azione suggerita: aprire il modulo contestuale e verificare le criticita prima di proseguire."
            )
        elif workflow in {"economico"}:
            text = _economic_text(q, title, summary)
        elif workflow in {"fascicolo"}:
            text = _fascicolo_text(q, context, title, summary)
        elif workflow in {"telematico_status", "compliance"}:
            text = (
                "Esito operativo governato\n"
                f"- Richiesta: {q or 'non specificata'}\n"
                f"- Evidenza principale: {title or 'non disponibile'}\n"
                f"- Osservazione: {summary}\n"
                "- Azione suggerita: eseguire il controllo tecnico o la verifica del fascicolo prima del passo successivo."
            )
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
