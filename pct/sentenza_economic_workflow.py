"""Workflow economico della sentenza: trigger PEC automatico e generazione parcella.

Due passi, entrambi prudenti:
- il trigger da PEC decide *se* far partire l'audit (solo `deposito_sentenza`), mai
  scrive nulla di definitivo — l'audit resta in anteprima (`to_review`);
- la generazione parcella avviene SOLO su un credito gia' **confermato** dall'avvocato
  (regola #4: mai parcella definitiva senza conferma).

Dominio puro (niente Flask): la parcella si crea tramite un `GestioneFatturazione`
iniettato con `origine="sentenza"`, riusando il modello fiscale esistente.
"""

from __future__ import annotations

from typing import Any

from pct.fatturazione import VoceParcella

_CREDIT_EVENTS = {"apri_credito_cliente", "apri_credito_avvocato_antistatario"}


def should_trigger_economic_audit(classification: dict[str, Any]) -> bool:
    """True solo se la PEC e' un deposito di sentenza (art. 133 c.p.c. lato cancelleria)."""

    return str((classification or {}).get("event_type") or "") == "deposito_sentenza"


def genera_parcella_da_credito(
    *,
    evento: dict[str, Any],
    fascicolo: Any,
    fatturazione: Any,
    creato_da: str = "",
    audit_id: str = "",
) -> dict[str, Any]:
    """Trasforma un credito da spese liquidate CONFERMATO in una parcella (origine=sentenza)."""

    event_type = str(evento.get("event_type") or "")
    if event_type not in _CREDIT_EVENTS:
        return {"ok": False, "code": "not_a_credit", "message": "L'evento non e' un credito da spese liquidate."}
    if str(evento.get("status") or "") != "confirmed":
        # Regola #4: mai parcella definitiva da sentenza senza conferma avvocato.
        return {"ok": False, "code": "not_confirmed", "message": "Conferma il credito prima di generare la parcella."}
    amount = float(evento.get("amount") or 0.0)
    if amount <= 0:
        return {"ok": False, "code": "no_amount", "message": "Importo non disponibile: verifica il capo spese in sentenza."}

    beneficiario = str(evento.get("beneficiary_type") or "")
    descrizione = (
        "Spese distratte ex art. 93 c.p.c."
        if beneficiario == "avvocato"
        else "Spese liquidate ex art. 91 c.p.c."
    )
    voce = VoceParcella(descrizione=f"{descrizione} (da sentenza)", prezzo_unitario=amount, tipo="SPESE")
    parcella = fatturazione.crea(
        str(getattr(fascicolo, "id_cliente", "") or ""),
        [voce],
        creato_da=creato_da,
        id_fascicolo=str(getattr(fascicolo, "id", "") or "") or None,
        origine="sentenza",
        dati_personalizzati={
            "sentenza_economic_audit_id": audit_id,
            "beneficiario_credito": beneficiario,
            "event_id": str(evento.get("id", "") or ""),
        },
    )
    return {"ok": True, "parcella": parcella}


__all__ = ["should_trigger_economic_audit", "genera_parcella_da_credito"]
