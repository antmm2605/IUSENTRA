"""L'economia della causa letta dagli atti del giudice: spese liquidate e loro incasso.

- il decreto ingiuntivo liquida le spese e le competenze e ne ingiunge il pagamento (art. 641, terzo comma,
  c.p.c.; G-14); la sentenza condanna il soccombente alle spese e ne liquida l'ammontare (art. 91 c.p.c.) e,
  se il difensore lo chiede, le distrae in suo favore (art. 93 c.p.c.);
- la somma liquidata è un credito finché non c'è la prova dell'incasso (art. 2697 c.c.; G-4): l'automatismo che
  scrive «pagato» non è una prova.
Le sentenze di altri procedimenti (atti di contorno) non portano crediti della causa (G-8).
"""

from __future__ import annotations

import re
from typing import Any

from pct.contributo_dovuto import categoria, confronta, contributo_dovuto
from pct.incasso_provato import pagamento_provato, pagato_deciso_dall_avvocato
from pct.spese_liquidate_provvedimento import spese_liquidate

from ..modello import Conclusione, Dubbio, Fonte
from ..norme import norme
from ..testo import data_it, giorno, pulito, semplice
from .contesto import Contesto

def liquidazione(testo: str) -> dict[str, Any] | None:
    """Compensi ed esborsi liquidati: regola unica di `pct/spese_liquidate_provvedimento.spese_liquidate`."""
    letta = spese_liquidate(testo)
    if not letta:
        return None
    dispositivo = re.split(r"P\.?\s*Q\.?\s*M\.?", str(testo or ""))[-1]
    # la distrazione chiesta dal difensore (art. 93 c.p.c.) può stare nella frase dopo la liquidazione
    distrazione = bool(letta.get("distrazione")) or bool(re.search(r"\bdistra(?:e|endo|tt[aei]|rsi|zione)\b|antistatari", dispositivo, re.I))
    return {**letta, "compensi": float(letta.get("compensi") or 0), "esborsi": float(letta.get("esborsi") or 0),
            "distrazione": distrazione, "brano": pulito(letta.get("brano"))[:300]}


def riscontro_incasso(voce: dict[str, Any], parcelle: list[dict[str, Any]]) -> str:
    if semplice(voce.get("stato")) != "pagato":
        return ""
    prova = pulito(voce.get("prova_incasso"))
    if prova:
        return f"Prova d'incasso {prova}"
    collegata = pulito(voce.get("proforma_id"))
    if collegata and any(pulito(p.get("id")) == collegata and semplice(p.get("stato")) == "pagata"
                         and giorno(p.get("data_pagamento")) for p in parcelle):
        return f"Incasso registrato sul documento economico {collegata}"
    if pagamento_provato(voce):
        return "Prova di pagamento verificata nel presidio economico"
    if pagato_deciso_dall_avvocato({"updated_by": voce.get("autore"), "history": voce.get("storico")}):
        quando = data_it(voce.get("data"))
        return f"Pagamento registrato dall'avvocato il {quando}" if quando else "Pagamento registrato dall'avvocato"
    return ""


def conclusioni_economia(ctx: Contesto, pagamenti: list[dict[str, Any]], parcelle: list[dict[str, Any]]) -> tuple[list[Conclusione], dict[str, Any]]:
    risultato, liquidazioni, visti = [], [], set()
    for atto in ctx.della_causa():
        if atto.autore != "giudice" or atto.id in visti:
            continue
        visti.update([atto.id, *atto.copie])
        letta = liquidazione(atto.testo)
        if not letta:
            continue
        decreto = "decreto ingiuntivo" in semplice(atto.etichetta)
        riscontri = [riscontro_incasso(p, parcelle) for p in pagamenti
                     if p.get("voce") == "liquidazione_giudice"
                     and pulito(p.get("documento_id") or p.get("documento")).removeprefix("document_id:") in {atto.id, *atto.copie}]
        riscontro = next((prova for prova in riscontri if prova), "")
        incassato = ctx.posizione == "attiva" and bool(riscontro)
        beneficiario = "all'avvocato antistatario (art. 93 c.p.c.)" if letta["distrazione"] else "al cliente"
        liquidazioni.append({"atto": atto.id, "nome": atto.nome, **letta, "incassato": incassato})
        if ctx.posizione != "attiva":
            continue
        risultato.append(Conclusione(
            "spese_liquidate", f"Riscuotere le spese liquidate dal giudice: € {letta['compensi']:.2f} di compensi"
            + (f" ed € {letta['esborsi']:.2f} di spese" if letta["esborsi"] else "") + (" oltre accessori di legge" if letta["accessori"] else ""),
            Fonte(atto.id, atto.nome, letta["brano"], atto.data),
            norme("cpc_641_spese") if decreto else norme("cpc_91") + (norme("cpc_93") if letta["distrazione"] else []),
            "richiesta di pagamento alla controparte e, se non paga, esecuzione con il titolo",
            f"il provvedimento ne ingiunge o ne condanna il pagamento: la somma spetta {beneficiario}",
            "fatto" if incassato else "da_fare", riscontro if incassato else
            "nessuna prova d'incasso nel fascicolo (art. 2697 c.c.)", None, "", onerato="noi",
            motivo_senza_termine="Il sollecito di pagamento va distinto dai termini di prescrizione e di esecuzione.",
        ))
    return risultato, {"liquidazioni": liquidazioni}


def conclusione_contributo(ctx: Contesto, fatti: list[dict[str, Any]], pagamenti: list[dict[str, Any]]) -> Conclusione | None:
    """Il contributo unificato dovuto per rito e valore e il confronto con il versato (G-16).

    Regola unica: `pct/contributo_dovuto` (art. 13, commi 1 e 3, D.P.R. 115/2002; il versamento di € 27 è
    l'anticipazione forfettaria dell'art. 30, non il contributo). Esenzione per reddito nelle controversie di
    lavoro: art. 9, comma 1-bis, D.P.R. 115/2002, se l'autocertificazione è stata letta.
    """
    posizione_da_verificare = ctx.posizione == "ignota" and ctx.rito.codice == "volontaria_giurisdizione"
    if ctx.posizione != "attiva" and not posizione_da_verificare:
        return None
    cat = categoria(area=ctx.rito.area, padre=ctx.rito.padre, tipo_fascicolo=ctx.fascicolo.get("tipo"))
    valore = float(ctx.fascicolo.get("valore_causa") or 0) or None
    dovuto = contributo_dovuto(cat, valore, giudice_pace="giudice di pace" in semplice(ctx.ufficio)) if cat else None
    versati = [float(f["valore"]) for f in fatti if f.get("campo") == "contributo_unificato" and f.get("categoria") == "importo"
               and f.get("verifica") in {"verificata", "plausibile", "corretta"} and str(f.get("valore") or "").replace(".", "").isdigit()]
    versati += [float(p["importo"]) for p in pagamenti if p.get("voce") == "contributo_unificato" and p.get("importo")]
    esente = any(f.get("campo") == "esenzione_cu_dichiarata" and f.get("verifica") in {"verificata", "corretta"} for f in fatti)
    fonte = Fonte("economia", "Contributo unificato", ", ".join(f"€ {v:.2f}" for v in sorted(set(versati))) or "nessuna ricevuta letta",
                  "", "economia")
    if cat == "lavoro" and esente:
        return Conclusione("contributo_unificato", "Contributo unificato non dovuto: esenzione per reddito dichiarata", fonte,
                           norme("dpr115_art9"), "dichiarazione di esenzione nelle conclusioni del ricorso",
                           "nelle controversie di lavoro il contributo non è dovuto sotto la soglia di reddito", "non_dovuto",
                           "autocertificazione dell'esenzione letta negli atti")
    esito = confronta(versati, dovuto, cat=cat) if cat else {"esito": "indeterminato", "dettaglio": ""}
    stato = {"coincide": "fatto", "insufficiente": "da_fare"}.get(esito["esito"], "dubbio")
    importo = esito.get("dovuto") or (dovuto.importo if dovuto else None)
    cosa = f"Versare il contributo unificato dovuto (€ {importo:.2f})" if importo else "Versare il contributo unificato dovuto"
    dubbi = [] if stato != "dubbio" else [Dubbio("contributo_indeterminato", "Il contributo dovuto non si può stabilire con certezza "
             "per questo rito o valore." if not cat else "Il versato non corrisponde a un importo previsto per il rito.",
             "il valore della causa dichiarato nell'atto introduttivo (art. 14 D.P.R. 115/2002)" if cat else
             "la regola del contributo per i processi esecutivi (art. 13, comma 2) nel calcolo del dovuto", fonte)]
    if posizione_da_verificare:
        importo_atteso = f" per il rito (€ {importo:.2f})" if importo else ""
        return Conclusione(
            "contributo_unificato", f"Verificare il contributo unificato{importo_atteso}", fonte,
            norme("dpr115_art13", "dpr115_art30"), "controllo del ricorso introduttivo e della ricevuta pagoPA",
            "occorre riscontrare chi ha depositato il ricorso e per quale voce è stato eseguito il versamento",
            "dubbio", esito.get("dettaglio") or "Versamento del contributo da riscontrare.", onerato="ignoto",
            dubbi=[Dubbio("contributo_onerato_ignoto", "Non è accertato chi ha depositato il ricorso.",
                          "l'atto introduttivo e la ricevuta del contributo unificato", fonte)],
        )
    return Conclusione("contributo_unificato", cosa, fonte, norme("dpr115_art13", "dpr115_art30"),
                       "pagamento con pagoPA e deposito della ricevuta con l'atto introduttivo",
                       "senza il contributo l'ufficio procede al recupero con sanzioni (artt. 16 e 248 D.P.R. 115/2002)",
                       stato, esito.get("dettaglio") or "", None, "", onerato="noi", dubbi=dubbi)


__all__ = ["conclusione_contributo", "conclusioni_economia", "liquidazione"]
