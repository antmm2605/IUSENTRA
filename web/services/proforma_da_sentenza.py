"""Proforma per le spese liquidate in sentenza: la base è il dispositivo già letto, i controlli quelli che servono.

Il controllo economico segna «da confermare» una voce anche per ragioni che non toccano l'importo della proforma:
nel fascicolo Alessi (RG 2539/2025, collaudo 08/11/2026) la liquidazione del giudice restava sospesa perché nelle
ricevute di notifica il codice fiscale della parte non era confrontabile, e «Prepara la proforma» rispondeva 409 pur
avendo la sentenza della causa liquidato € 250,00 distratti al difensore (art. 93 c.p.c.).

Qui si separano i due controlli:
- bloccano la proforma solo le voci che ne danno l'importo (parcella; liquidazione del giudice quando è quella la
  base) e solo se l'importo stesso è in discussione;
- se la base è la sentenza della causa letta dal motore documenti (``pct/archivio_letture/spese_sentenza.py``),
  le verifiche pendenti su altri documenti restano da fare ma non impediscono la proforma, che resta una bozza da
  rivedere (avviso di parcella: la fattura si emette al pagamento, art. 6, terzo comma, D.P.R. 633/1972).
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

ETICHETTE = {"parcella": "Parcella", "liquidazione_giudice": "Liquidazione del giudice"}


def base_dalla_sentenza_letta(fascicolo: Any) -> tuple[float | None, str]:
    """L'importo liquidato dalla sentenza della causa in favore del cliente o del difensore, con la fonte."""
    from web.services.fascicolo_conto_economico_runtime import (
        crediti_da_sentenza,
        crediti_dalle_sentenze_lette,
        sentenze_dall_archivio,
    )

    try:
        crediti_registrati = crediti_da_sentenza(str(fascicolo.id))
    except Exception:
        crediti_registrati = []
    try:
        crediti = [voce for voce in crediti_registrati if voce.get("confermato") and voce.get("fonti")]
        if not crediti:
            crediti = crediti_dalle_sentenze_lette(sentenze_dall_archivio(fascicolo))
    except Exception:
        return None, ""
    importi = {round(float(c["importo"]), 2) for c in crediti if c.get("importo")}
    if len(importi) != 1 or len({bool(c.get("distrazione")) for c in crediti}) != 1:
        return None, ""  # nessuna o più sentenze con importi diversi: decide l'avvocato
    credito = next(c for c in crediti if c.get("importo"))
    documento = next((f.get("label") for f in credito.get("fonti") or [] if f.get("label")), "sentenza della causa")
    importo = importi.pop()
    return importo, fonte_importo(importo, bool(credito.get("distrazione")), documento)


def fonte_importo(importo: float, distratte: bool, documento: str) -> str:
    distrazione = " distratte (art. 93 c.p.c.)" if distratte else ""
    euro = f"{importo:,.2f}".replace(",", "§").replace(".", ",").replace("§", ".")
    return f"spese liquidate in sentenza € {euro}{distrazione}, oltre accessori ({documento})"[:120]


def proforma_della_liquidazione(
    parcelle: Iterable[Any], *, evento: Mapping[str, Any], documento: str, id_cliente: str,
) -> Any | None:
    """Riconosce una proforma già creata dal Conto economico sulla stessa fonte e lo stesso credito."""
    from pct.proforma_unica import superata

    importo = round(float(evento.get("amount") or 0), 2)
    tipo = evento.get("event_type")
    if not documento or not id_cliente or importo <= 0 or tipo not in {
        "apri_credito_cliente", "apri_credito_avvocato_antistatario",
    }:
        return None
    fonte = fonte_importo(importo, tipo == "apri_credito_avvocato_antistatario", documento)
    if not fonte.endswith(f"({documento})"):
        return None
    suffisso = f"Base di calcolo: {fonte}."
    for p in parcelle:
        dati = p.dati_personalizzati or {}
        stato = getattr(p.stato, "value", p.stato)
        if (
            p.origine == "controllo_economico_fascicolo" and p.id_cliente == id_cliente
            and stato == "BOZZA" and not superata(p)
            and (dati.get("document") or {}).get("documento_operativo") == "PROFORMA"
            and dati.get("event_id") in (None, "", evento.get("id"))
            and p.note.endswith(suffisso) and round(p.totale_competenze, 2) == importo
        ):
            return p
    return None


def voci_che_bloccano(items: Mapping[str, Mapping[str, Any]], *, base_da_sentenza: bool) -> list[str]:
    """Le voci da confermare prima della proforma, con il motivo; vuoto se la proforma si può preparare."""
    bloccanti = []
    for voce in ("parcella", "liquidazione_giudice"):
        item = items.get(voce) or {}
        if not item.get("richiedeConferma"):
            continue
        if voce == "liquidazione_giudice" and base_da_sentenza:
            continue  # l'importo viene dal dispositivo letto: le verifiche su altri documenti non lo toccano
        motivo = next((str(m) for m in item.get("verificheMancanti") or [] if str(m).strip()), "importo da confermare")
        bloccanti.append(f"{ETICHETTE[voce]}: {motivo}")
    return bloccanti


__all__ = ["base_dalla_sentenza_letta", "voci_che_bloccano"]
