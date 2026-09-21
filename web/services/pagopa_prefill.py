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
    }
