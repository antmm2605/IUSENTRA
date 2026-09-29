"""Dati PagoPA dall'anagrafica del tenant, senza creare avvisi o pagamenti."""

from __future__ import annotations


def dati_precompilazione(fascicolo, cliente, avvisi):
    """Le proposte restano modificabili nel modulo ufficiale prima dell'invio."""
    pending = [a for a in avvisi if not a.get("documento_id")]
    avviso = pending[0] if len(pending) == 1 else {}
    return {
        "nominativoPagatore": str(getattr(cliente, "nome_completo", "") or ""),
        "codiceFiscale": str(getattr(cliente, "identificativo_fiscale", "") or ""),
        "codiceFiscalePagatore": str(avviso.get("codice_fiscale_debitore") or ""),
        "crs": str(avviso.get("numero_avviso") or ""),
        "importoContributo": _importo_contributo(fascicolo),
    }


def _importo_contributo(fascicolo) -> str:
    """Il contributo unificato ancora da versare, come proposta per l'avviso; vuoto se esente o già pagato."""
    voce = dict((getattr(fascicolo, "pagamenti", {}) or {}).get("contributo_unificato") or {})
    if voce.get("pagato") or voce.get("previsto") is False or str(voce.get("status") or "") in {"pagato", "non_previsto"}:
        return ""
    try:
        importo = float(voce.get("importo"))
    except (TypeError, ValueError):
        return ""
    return f"{importo:.2f}" if importo > 0 else ""
