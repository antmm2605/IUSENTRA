"""PEC con ordine di notifica ma senza fascicolo collegato: proposta in BOZZA da lavorare.

Il presidio delle notifiche L. 53/1994 nasce solo su un fascicolo: senza collegamento non si crea
un presidio orfano. Fino al 09/11/2026 la PEC veniva però scartata in silenzio («fascicolo non
collegato, presidio non creato») e l'avvocato non vedeva l'ordine del giudice.

Si usa il meccanismo già esistente delle proposte di scadenza in BOZZA (come
``pct/scadenze_proposte_pec``): la proposta compare nella coda «Proposte» dello scadenziario anche
senza fascicolo, non entra in agenda, notifiche o conteggi operativi e l'avvocato la conferma o la
scarta. Quando la PEC viene collegata il presidio si rimaterializza e la proposta si chiude da sola.

Base normativa: L. 53/1994, art. 3-bis (notifica a mezzo PEC dell'avvocato); art. 415, commi 4-5,
c.p.c. (ricorso e decreto notificati a cura dell'attore entro dieci giorni dalla pronuncia del
decreto); art. 435, commi 2-3, c.p.c. (appello: dieci giorni dal deposito del decreto, decorrenti
dalla comunicazione secondo Corte cost. 15/1977); art. 281-undecies c.p.c. (procedimento
semplificato). La data della proposta è solo un promemoria di verifica a dieci giorni dalla
ricezione della PEC, non un termine di legge: il termine effettivo si legge nel provvedimento e si
calcola nel presidio dopo il collegamento. Nessun invio automatico.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from pct.ora_italiana import giorno_italiano, oggi_roma

MARCATORE = "PROPOSTA_NOTIFICA_SENZA_FASCICOLO"
PROFILO = "PEC_PROPOSTA_NOTIFICA"
GIORNI_VERIFICA = 10
_RG_RE = re.compile(r"\b(\d{1,7})/(\d{4})(?:/[A-Z]{2,5})?\b", re.I)


def _clean(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split()).strip()[:limit].strip()


def marcatore(message_id: str) -> str:
    return f"{MARCATORE}:{_clean(message_id, 160)}"


def numero_ruolo(understanding: dict[str, Any], subject: str = "") -> str:
    """RG letto dal JSON V2 o, in mancanza, dall'oggetto della PEC di cancelleria."""

    procedimento = understanding.get("procedimento") if isinstance(understanding.get("procedimento"), dict) else {}
    numero = _clean(procedimento.get("rg_numero"), 12)
    anno = _clean(procedimento.get("rg_anno"), 4)
    if numero and anno:
        return f"{numero}/{anno}"
    oggetto = subject or _clean((understanding.get("message") or {}).get("subject_normalized"), 240)
    trovato = _RG_RE.search(oggetto or "")
    return f"{trovato.group(1)}/{trovato.group(2)}" if trovato else ""


def campi_proposta(
    *,
    message_id: str,
    understanding: dict[str, Any],
    candidate: dict[str, Any],
    received_at: str,
    oggi: date | None = None,
) -> dict[str, Any] | None:
    """Campi per ``GestioneScadenziario.nuova``; ``None`` se la verifica sarebbe già decorsa."""

    try:
        ricevuta = date.fromisoformat(giorno_italiano(received_at)[:10])
    except ValueError:
        ricevuta = oggi or oggi_roma()
    verifica = ricevuta + timedelta(days=GIORNI_VERIFICA)
    if verifica < (oggi or oggi_roma()):
        return None
    rg = numero_ruolo(understanding)
    procedimento = understanding.get("procedimento") if isinstance(understanding.get("procedimento"), dict) else {}
    ufficio = _clean(procedimento.get("ufficio"), 120)
    riferimento = " ".join(part for part in (f"RG {rg}" if rg else "", ufficio) if part) or "della PEC"
    estratto = _clean(candidate.get("text_excerpt"), 360)
    return {
        "titolo": f"PEC con ordine di notifica: crea o collega il fascicolo {riferimento}"[:180],
        "data_scadenza": verifica.isoformat(),
        "descrizione": (
            "Il provvedimento ricevuto via PEC ordina al difensore di notificare (L. 53/1994, art. 3-bis; "
            "artt. 415, commi 4-5, 435 e 281-undecies c.p.c.), ma la PEC non è collegata a un fascicolo: "
            "il presidio della notifica non è stato aperto. Creare o collegare il fascicolo dalla PEC; "
            "il presidio nasce al collegamento. La data è un promemoria di verifica a dieci giorni dalla "
            "ricezione, non il termine di legge, che si legge nel provvedimento."
        ),
        "note": "\n".join(
            (
                marcatore(message_id),
                f"Regola: {_clean(candidate.get('rule_id'), 80) or '-'} ({_clean(candidate.get('rulepack_version'), 60) or '-'})",
                f"Ricevuta il: {ricevuta.strftime('%d/%m/%Y')}",
                "Proposta in bozza: revisione dell'avvocato obbligatoria, nessun invio automatico.",
            )
        ),
        "id_fascicolo": "",
        "source_event_type": "legal_notification_order_unlinked",
        "source_event_at": _clean(received_at, 40),
        "deadline_profile_code": PROFILO,
        "source_snippet": estratto,
        "source_snippet_label": "Ordine di notifica",
        "source_document_name": _clean(candidate.get("source_file"), 160) or "allegato PEC",
        "source_message_id": _clean(message_id, 160),
        "source_confidence": float(candidate.get("confidence") or 0.0),
    }


def proponi_collegamento(
    manager: Any,
    *,
    message_id: str,
    understanding: dict[str, Any],
    candidate: dict[str, Any],
    received_at: str,
    responsabile: str = "",
    oggi: date | None = None,
) -> dict[str, Any]:
    """Crea una sola proposta per PEC (idempotente sul marcatore, anche dopo conferma o scarto)."""

    from pct.scadenziario import StatoTermine, TipoTermine

    chiave = marcatore(message_id)
    for voce in manager.tutte(solo_aperte=False):
        if chiave in str(getattr(voce, "note", "") or ""):
            return {"created": False, "id": str(getattr(voce, "id", "")), "motivo": "proposta già registrata"}
    campi = campi_proposta(
        message_id=message_id, understanding=understanding, candidate=candidate, received_at=received_at, oggi=oggi,
    )
    if campi is None:
        return {"created": False, "id": "", "motivo": "verifica già decorsa: proposta non creata"}
    voce = manager.nuova(
        titolo=campi.pop("titolo"),
        tipo=TipoTermine.ADEMPIMENTO,
        data_scadenza=campi.pop("data_scadenza"),
        id_fascicolo=campi.pop("id_fascicolo"),
        descrizione=campi.pop("descrizione"),
        note=campi.pop("note"),
        id_utente_responsabile=responsabile,
        stato=StatoTermine.BOZZA,
        **campi,
    )
    return {"created": True, "id": str(getattr(voce, "id", "")), "motivo": "proposta creata"}


def chiudi_dopo_collegamento(manager: Any, *, message_id: str, fascicolo_id: str, attore: str = "") -> int:
    """Collegata la PEC e aperto il presidio, la proposta ha esaurito il suo scopo: si scarta con motivo."""

    from pct.scadenziario import StatoTermine

    chiave = marcatore(message_id)
    chiuse = 0
    for voce in list(manager.tutte(solo_aperte=False)):
        if getattr(voce, "stato", None) != StatoTermine.BOZZA or chiave not in str(getattr(voce, "note", "") or ""):
            continue
        manager.scarta_bozza(
            str(getattr(voce, "id", "")),
            motivo=f"PEC collegata al fascicolo {fascicolo_id}: presidio della notifica aperto.",
            attore=attore,
        )
        chiuse += 1
    return chiuse


__all__ = [
    "GIORNI_VERIFICA", "MARCATORE", "PROFILO", "campi_proposta", "chiudi_dopo_collegamento", "marcatore",
    "numero_ruolo", "proponi_collegamento",
]
