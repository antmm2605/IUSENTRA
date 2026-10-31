"""Dalla PEC letta al termine della notifica ricevuta, nella forma del proponente dei termini legali.

Adattatore fra il motore PEC (`pct.pec_pipeline.build_validation_report`) e il dominio
(`pct.notifiche_ricevute`): riconosce la notifica L. 53/1994 arrivata da un altro difensore
nella casella dello studio e calcola col motore unico (`pct.termini_processuali`) il primo
termine dell'atto notificato. Senza questo passaggio un decreto ingiuntivo notificato
attivava la regola delle comunicazioni di cancelleria (art. 644, dalla comunicazione).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable

from pct.notifiche_ricevute import direzione_notifica, oggetto_di_notifica_l53, termini_da_notifica_ricevuta
from pct.pec_legal_deadline_proposer import is_labour_matter
from pct.termini_processuali import ItalianDeadlineCalculator


def _dizionario(valore: Any) -> dict[str, Any]:
    return valore if isinstance(valore, dict) else {}


def _notifica_ricevuta(parsed: dict[str, Any]) -> bool:
    headers, casella = _dizionario(parsed.get("headers")), _dizionario(parsed.get("casella"))
    if not oggetto_di_notifica_l53(str(headers.get("subject") or "")):
        return False
    return direzione_notifica(
        casella=str(casella.get("account_email") or ""), mittente=str(headers.get("from") or ""),
        cartella=str(casella.get("folder") or ""),
    ) == "ricevuta"


def proposta_notifica_ricevuta(
    parsed: dict[str, Any], *, attachment_names: Iterable[str] = (), consegna_iso: str = "",
) -> dict[str, Any] | None:
    """Proposta di termine legale per la notifica ricevuta; None se la PEC non è una notifica ricevuta."""
    parsed = _dizionario(parsed)
    if not _notifica_ricevuta(parsed):
        return None
    oggetto = str(_dizionario(parsed.get("headers")).get("subject") or "")
    testo = f"{oggetto}\n{_dizionario(parsed.get('body')).get('text') or ''}"
    non_riconosciuto = {
        "ok": False, "human_review_required": True,
        "reason": "Notifica L. 53/1994 ricevuta: atto notificato o data di consegna da verificare per il termine.",
    }
    try:
        consegna = datetime.fromisoformat(str(consegna_iso or "").replace("Z", "+00:00"))
    except ValueError:
        return non_riconosciuto
    proposte = termini_da_notifica_ricevuta(testo, consegna=consegna, nomi_allegati=list(attachment_names))
    if not proposte:
        return non_riconosciuto
    prima = proposte[0]
    lavoro = is_labour_matter(oggetto, testo)
    esito = ItalianDeadlineCalculator().calculate(
        date.fromisoformat(prima["dies_a_quo_date"]), int(prima["duration_value"]), direction=prima["direction"],
        suspend_august=not lavoro, reference_law=prima["norma"],
    )
    return {
        "ok": True,
        "deadline": esito["deadline"],
        "raw_deadline": esito["rawDeadline"],
        "tipo": "perentorio",
        "azione": prima["deadline_type"],
        "norma": prima["norma"],
        "template_code": f"NOTIFICA_RICEVUTA_{prima['codice_termine'].upper()}",
        "dies_a_quo_type": prima["dies_a_quo_type"],
        "dies_a_quo_date": prima["dies_a_quo_date"],
        "durata": prima["duration_value"],
        "unita": "days",
        "direzione": prima["direction"],
        "steps": esito.get("steps") or [],
        "explanation": prima["evidence"][0]["text"],
        "confidence": 0.85,
        "human_review_required": True,
        "altri_termini": proposte[1:],
    }


__all__ = ["proposta_notifica_ricevuta"]
