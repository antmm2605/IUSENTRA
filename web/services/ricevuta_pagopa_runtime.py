"""Riconoscimento della ricevuta telematica pagoPA caricata nel fascicolo.

Il pagamento del contributo unificato avviene sul portale ufficiale con
l'autenticazione dell'avvocato: il gestionale non paga e non scarica nulla
(regole del Portale Servizi Telematici). Quello che puo' fare e' riconoscere la
ricevuta che l'avvocato riporta nel fascicolo. La logica sta qui, fra i servizi
applicativi, non nel modulo di wiring delle rotte.

Base normativa: art. 4 c. 9 D.L. 193/2009 (pagamento telematico del contributo
unificato); D.P.R. 115/2002 art. 13.
"""

from __future__ import annotations

from typing import Any

from flask import current_app


def registra_ricevuta_pagopa(gestore: Any, id_fasc: str, documento: Any, nome: str, contenuto: bytes) -> int:
    """Se il file caricato e' una Ricevuta Telematica pagoPA, registra il pagamento.

    Il pagamento avviene sul portale ufficiale con l'autenticazione
    dell'avvocato (regole PST: nessun download autonomo). Quello che il
    gestionale puo' fare e' riconoscere la ricevuta che l'avvocato riporta nel
    fascicolo, verificarla secondo lo schema ministeriale
    ``PagamentiTelematiciGiustizia`` e annotare il versamento sul contributo
    unificato.

    Fail-closed: si registra il pagamento solo quando l'esito della ricevuta e'
    «eseguito». Una ricevuta con esito diverso resta agli atti con la sua nota,
    ma non fa risultare pagato nulla. Restituisce 1 se ha registrato, 0
    altrimenti.

    Base normativa: art. 4 c.9 D.L. 193/2009; D.P.R. 115/2002 art. 13.
    """
    try:
        from pct.pagamenti_giustizia import nota_ricevuta, riconosci_ricevuta_caricata
    except Exception:  # pragma: no cover - dipendenze del runtime
        return 0
    rt = riconosci_ricevuta_caricata(nome, contenuto)
    if rt is None:
        return 0
    avviso_riuso = _avviso_riuso(gestore, id_fasc, rt)
    try:
        note = "\n".join(filter(None, [str(getattr(documento, "note", "") or ""), nota_ricevuta(rt), avviso_riuso]))
        gestore.aggiorna_documento_metadati(id_fasc, getattr(documento, "id", ""), note=note)
    except Exception:
        current_app.logger.info("Ricevuta pagoPA riconosciuta ma nota non aggiornata su %s", id_fasc)
    if not getattr(rt, "pagamento_eseguito", False):
        return 0
    try:
        fascicolo = gestore.get(id_fasc)
        pagamenti = dict(getattr(fascicolo, "pagamenti", {}) or {})
        pagamenti["contributo_unificato"] = {
            "kind": "contributo_unificato", "status": "pagato", "previsto": True, "pagato": True,
            "importo": float(rt.importo_totale), "valuta": "EUR",
            "data_pagamento": str(rt.data_esito_pagamento or rt.data_ricevuta or ""),
            "documento_fonte": nome, "documento_id": getattr(documento, "id", ""),
            "origine": "Ricevuta telematica pagoPA caricata nel fascicolo",
            "updated_by": "IUSENTRA automatico",
            "note": f"Versamento provato dalla ricevuta telematica (IUV {rt.iuv or 'n.d.'}).",
            "iuv": str(rt.iuv or ""),
        }
        if avviso_riuso:
            pagamenti["contributo_unificato"]["avviso_riuso"] = avviso_riuso
        gestore.aggiorna(id_fasc, pagamenti=pagamenti)
    except Exception:
        current_app.logger.exception("Registrazione del pagamento pagoPA non riuscita su %s", id_fasc)
        return 0
    return 1


def _avviso_riuso(gestore: Any, id_fasc: str, rt: Any) -> str:
    """Avviso (mai blocco) se lo stesso IUV risulta già usato in un altro fascicolo dello studio."""
    try:
        from pct.pagamenti_giustizia_registro import avviso_riuso, usi_altrove

        return avviso_riuso(usi_altrove(gestore.tutti(archiviati=True), str(getattr(rt, "iuv", "") or ""), escludi=id_fasc))
    except Exception:
        current_app.logger.info("Controllo di riuso della ricevuta pagoPA non disponibile su %s", id_fasc)
        return ""


__all__ = ["registra_ricevuta_pagopa"]
