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
    documenti_count = int(fascicolo.get("documenti_count") or len(documenti) or 0)

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
    if "udienz" in haystack and prossima_udienza:
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
