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
        from pct.contributo_quote import quote_della_ricevuta

        quote = quote_della_ricevuta(contenuto, rt.importo_totale)
        fascicolo = gestore.get(id_fasc)
        pagamenti = dict(getattr(fascicolo, "pagamenti", {}) or {})
        pagamenti["contributo_unificato"] = voce_contributo_da_ricevuta(
            pagamenti.get("contributo_unificato"), rt, quote, nome=nome, documento_id=str(getattr(documento, "id", "") or ""),
        )
        if avviso_riuso:
            pagamenti["contributo_unificato"]["avviso_riuso"] = avviso_riuso
        gestore.aggiorna(id_fasc, pagamenti=pagamenti)
    except Exception:
        current_app.logger.exception("Registrazione del pagamento pagoPA non riuscita su %s", id_fasc)
        return 0
    return 1


def voce_contributo_da_ricevuta(precedente: Any, rt: Any, quote: Any, *, nome: str, documento_id: str) -> dict[str, Any]:
    """La voce del contributo unificato dopo una ricevuta: solo la quota del contributo (art. 13 D.P.R. 115/2002),
    l'anticipazione forfettaria dell'art. 30 a parte, e le ricevute di un pagamento frazionato sommate per IUV."""
    precedente = dict(precedente) if isinstance(precedente, dict) else {}
    ricevute = [r for r in list(precedente.get("ricevute") or []) if isinstance(r, dict) and r.get("iuv") != str(rt.iuv or "")]
    if not ricevute and precedente.get("iuv") and precedente.get("iuv") != str(rt.iuv or ""):
        ricevute = [{"iuv": precedente.get("iuv"), "contributo": float(precedente.get("importo") or 0),
                     "art_30": float(precedente.get("art_30") or 0), "documento_id": precedente.get("documento_id", ""),
                     "data": precedente.get("data_pagamento", "")}]
    ricevute.append({"iuv": str(rt.iuv or ""), "contributo": float(quote.contributo), "art_30": float(quote.art_30),
                     "documento_id": documento_id, "data": str(rt.data_esito_pagamento or rt.data_ricevuta or "")})
    contributo = round(sum(r["contributo"] for r in ricevute), 2)
    nota = f"Versamento provato dalla ricevuta telematica (IUV {rt.iuv or 'n.d.'})."
    if quote.errore:
        nota += f" Da verificare: {quote.errore}"
    return {
        "kind": "contributo_unificato", "status": "pagato" if contributo > 0 else "da_verificare", "previsto": True,
        "pagato": contributo > 0, "importo": contributo, "art_30": round(sum(r["art_30"] for r in ricevute), 2),
        "valuta": "EUR", "data_pagamento": ricevute[-1]["data"], "documento_fonte": nome, "documento_id": documento_id,
        "origine": "Ricevuta telematica pagoPA caricata nel fascicolo", "updated_by": "IUSENTRA automatico",
        "note": nota, "iuv": str(rt.iuv or ""), "ricevute": ricevute,
    }


def _avviso_riuso(gestore: Any, id_fasc: str, rt: Any) -> str:
    """Avviso (mai blocco) se lo stesso IUV risulta già usato in un altro fascicolo dello studio."""
    try:
        from pct.pagamenti_giustizia_registro import avviso_riuso, usi_altrove

        return avviso_riuso(usi_altrove(gestore.tutti(archiviati=True), str(getattr(rt, "iuv", "") or ""), escludi=id_fasc))
    except Exception:
        current_app.logger.info("Controllo di riuso della ricevuta pagoPA non disponibile su %s", id_fasc)
        return ""


__all__ = ["registra_ricevuta_pagopa", "voce_contributo_da_ricevuta"]
