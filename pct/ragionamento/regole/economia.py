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

from pct.contributo_dovuto import VOLONTARIA, categoria, confronta, contributo_dovuto
from pct.contributo_esenzioni import confronto_esente, descrizione_codice, esenzione_volontaria
from pct.formatting import format_euro_it
from pct.percorso_pratica.giurisdizioni import AMMINISTRATIVO, giurisdizione_e_grado
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


_RE_INCARICO = re.compile(
    r"\bprocura\s+(?:alle\s+liti|speciale|generale)\b|\b(?:giusta|in\s+virt[uù]\s+della|come\s+da)\s+procura\b|"
    r"\bprocura\s+(?:in\s+calce|a\s+margine|allegata|in\s+atti)\b|\bmandato\s+(?:alle\s+liti|difensivo|professionale)\b|"
    r"\bconferimento\s+(?:dell['’]\s*)?incarico\b|\bdifensore\s+per\s+mandato\b", re.I)


def incarico_conferito(ctx: Contesto) -> dict[str, str] | None:
    """La prova che il cliente ha conferito l'incarico allo studio: la procura alle liti (art. 83 c.p.c.) o il mandato.

    La procura nel fascicolo o richiamata nell'atto dello studio («rappresentata e difesa … con procura allegata»)
    prova il conferimento dell'incarico; resta distinto il patto scritto sul compenso, che l'art. 13, comma 2,
    L. 247/2012 vuole «di regola» per iscritto.
    """
    for atto in ctx.atti:
        if atto.natura == "procura" or re.search(r"\bprocura\b|\bmandato\b|incarico", semplice(atto.etichetta)):
            return {"oggetto_id": atto.id, "nome": atto.nome, "prova": f"procura alle liti «{atto.nome}»"}
    for atto in ctx.atti:
        if atto.dello_studio and atto.testo and (m := _RE_INCARICO.search(atto.testo)):
            return {"oggetto_id": atto.id, "nome": atto.nome,
                    "prova": f"«{pulito(atto.testo[max(0, m.start() - 60):m.end() + 40])}» in «{atto.nome}»"}
    return None


def conclusioni_economia(ctx: Contesto, pagamenti: list[dict[str, Any]], parcelle: list[dict[str, Any]]) -> tuple[list[Conclusione], dict[str, Any]]:
    from ..atti import priorita_fonte_sentenza
    from .sentenza import data_pubblicazione

    risultato, liquidazioni, visti = [], [], set()
    atti = sorted(ctx.della_causa(), key=priorita_fonte_sentenza)
    for atto in atti:
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
        liquidazioni.append({"atto": atto.id, "copie": list(atto.copie), "nome": atto.nome, **letta, "incassato": incassato})
        if ctx.posizione != "attiva":
            continue
        data_fonte = (data_pubblicazione(atto.testo) if atto.sentenza else "") or atto.data
        risultato.append(Conclusione(
            "spese_liquidate", f"Riscuotere le spese liquidate dal giudice: {format_euro_it(letta['compensi'])} di compensi"
            + (f" e {format_euro_it(letta['esborsi'])} di spese" if letta["esborsi"] else "") + (" oltre accessori di legge" if letta["accessori"] else ""),
            Fonte(atto.id, atto.nome, letta["brano"], data_fonte),
            norme("cpc_641_spese") if decreto else norme("cpc_91") + (norme("cpc_93") if letta["distrazione"] else []),
            "richiesta di pagamento alla controparte e, se non paga, esecuzione con il titolo",
            f"il provvedimento ne ingiunge o ne condanna il pagamento: la somma spetta {beneficiario}",
            "fatto" if incassato else "da_fare", riscontro if incassato else
            "nessuna prova d'incasso nel fascicolo (art. 2697 c.c.)", None, "", onerato="noi",
            motivo_senza_termine="Il sollecito di pagamento va distinto dai termini di prescrizione e di esecuzione.",
        ))
    return risultato, {"liquidazioni": liquidazioni, "incarico": incarico_conferito(ctx)}


def _confronto_contributo(ctx: Contesto, fatti: list[dict[str, Any]], pagamenti: list[dict[str, Any]]):
    """Categoria, dovuto, importi versati letti e confronto (regola unica di `pct/contributo_dovuto`)."""
    cat = categoria(area=ctx.rito.area, padre=ctx.rito.padre, tipo_fascicolo=ctx.fascicolo.get("tipo"))
    valore = float(ctx.fascicolo.get("valore_causa") or 0) or None
    dovuto = contributo_dovuto(cat, valore, giudice_pace="giudice di pace" in semplice(ctx.ufficio)) if cat else None
    versati = [float(f["valore"]) for f in fatti if f.get("campo") == "contributo_unificato" and f.get("categoria") == "importo"
               and f.get("verifica") in {"verificata", "plausibile", "corretta"} and str(f.get("valore") or "").replace(".", "").isdigit()]
    versati += [float(p["importo"]) for p in pagamenti if p.get("voce") == "contributo_unificato" and p.get("importo")]
    if cat == VOLONTARIA:
        # Prima dell'art. 13, comma 1, lett. b): le esenzioni dell'art. 10 D.P.R. 115/2002 e dell'art. 46-bis disp. att.
        # c.c. per l'oggetto del procedimento (regola unica di pct/contributo_esenzioni).
        testi = [a.testo for a in ctx.atti if a.testo and (a.natura in {"atto_principale", "istanza"} and a.appartenenza == "causa"
                                                           or re.search(r"ricors|istanz", semplice(a.nome)))]
        esenzione = esenzione_volontaria(codice_oggetto=ctx.rito.codice_oggetto,
                                         descrizione=descrizione_codice(ctx.rito.codice_oggetto), testi=testi)
        if esenzione:
            return cat, None, versati, confronto_esente(esenzione, versati)
    esito = confronta(versati, dovuto, cat=cat) if cat else {"esito": "indeterminato", "dettaglio": ""}
    return cat, dovuto, versati, esito


def _conclusione_esente(confronto: dict[str, Any], fonte: Fonte) -> Conclusione:
    """Processo esente per legge: nessun versamento del contributo; resta solo il dubbio vero, se c'è."""
    norma = str(confronto.get("norma") or "")
    regole = norme("dpr115_art10", "dpr115_art30") + (norme("dispattcc_46bis") if "46-bis" in norma else [])
    dubbio = str(confronto.get("dubbio") or "")
    anticipazione = ("versati € 27 = anticipazione forfettaria dovuta (art. 30), corretto"
                     if confronto.get("anticipazione") == "dovuta" and confronto.get("versato") else "")
    cosa = f"Contributo unificato non dovuto ({norma})" + (f"; {anticipazione}" if anticipazione else "")
    if "art. 10, comma 6" in dubbio:
        cosa += ": nell'atto introduttivo manca la dichiarazione della ragione dell'esenzione (art. 10, comma 6)"
    elif dubbio:
        cosa += f": {dubbio}"
    dubbi = [Dubbio("esenzione_da_completare", dubbio[:1].upper() + dubbio[1:] + ".",
                    "la dichiarazione della ragione dell'esenzione nelle conclusioni dell'atto introduttivo o la ricevuta "
                    "dell'anticipazione forfettaria", fonte)] if dubbio else []
    return Conclusione(
        "contributo_unificato", cosa, fonte, regole,
        "nessun versamento del contributo: l'esenzione si dichiara nelle conclusioni dell'atto introduttivo "
        "(art. 10, comma 6, D.P.R. 115/2002); se manca, la si integra con una nota depositata nel fascicolo",
        f"{confronto.get('motivo')}: il processo non è soggetto al contributo unificato",
        "dubbio" if dubbi else "non_dovuto", str(confronto.get("dettaglio") or ""), onerato="noi", dubbi=dubbi,
        motivo_senza_termine="Processo esente: nessun termine di pagamento.",
    )


def _integrazione_contributo(ctx: Contesto, esito: dict[str, Any], fonte: Fonte, *, gia_depositato: bool) -> Conclusione:
    """Versato meno del dovuto, con rito e valore certi: il dubbio concreto, con dovuto e versato (art. 13 D.P.R. 115/2002).

    Il versamento di € 27 è l'anticipazione forfettaria dell'art. 30, non il contributo. Il fascicolo può non contenere
    la ricevuta del contributo: per questo è un dubbio, non un ordine di pagare. Se il contributo manca davvero,
    l'ufficio procede con l'invito al pagamento o con l'iscrizione a ruolo, con interessi e sanzione (artt. 16 e 248).
    """
    from pct.contributo_dovuto import ANTICIPAZIONE_FORFETTARIA, NORMA_ANTICIPAZIONE

    dovuto, versato = float(esito["dovuto"]), float(esito.get("versato") or 0)
    solo27 = versato == 0 and ANTICIPAZIONE_FORFETTARIA in {round(float(v), 2) for v in esito.get("letti") or ()}
    versato_testo = (f"risultano versati {format_euro_it(ANTICIPAZIONE_FORFETTARIA)}, che sono l'anticipazione forfettaria "
                     f"({NORMA_ANTICIPAZIONE}), non il contributo" if solo27
                     else "nel fascicolo non c'è la ricevuta del versamento" if versato == 0
                     else f"risultano versati {format_euro_it(versato)}")
    differenza = round(dovuto - versato, 2)
    da_fare = (f"versare l'integrazione di {format_euro_it(differenza)}" if versato else f"versare {format_euro_it(differenza)}")
    alternative = "o depositare la ricevuta del contributo, se già versato"
    if ctx.rito.codice == "lavoro" or semplice(ctx.fascicolo.get("tipo")) in {"lavoro", "previdenza"}:
        alternative += ", o l'autocertificazione di esenzione per reddito (art. 9, comma 1-bis, D.P.R. 115/2002)"
    cosa = f"Contributo unificato: dovuti {format_euro_it(dovuto)} ({esito.get('norma')}), {versato_testo}: {da_fare} {alternative}"
    perche = ("il contributo omesso o insufficiente è riscosso dall'ufficio con invito al pagamento o iscrizione a ruolo, "
              "con gli interessi legali e la sanzione (artt. 16 e 248 D.P.R. 115/2002)" if gia_depositato else
              "il contributo si versa con il deposito dell'atto introduttivo (art. 13 D.P.R. 115/2002)")
    dubbio = Dubbio("contributo_insufficiente", f"Dovuti {format_euro_it(dovuto)}, {versato_testo}.",
                    "la ricevuta del contributo unificato o il titolo di esenzione dichiarato nelle conclusioni", fonte)
    return Conclusione(
        "contributo_unificato", cosa, fonte, norme("dpr115_art13", "dpr115_art30", "dpr115_art16", "dpr115_art248"),
        "versamento con pagoPA della differenza e deposito telematico della ricevuta nel fascicolo",
        perche, "dubbio", esito.get("dettaglio") or "", onerato="noi", dubbi=[dubbio],
        motivo_senza_termine="Nessun termine assegnato: l'invito al pagamento dell'ufficio assegna un mese (art. 248 D.P.R. 115/2002).",
    )


def _contributo_dal_presidio(ctx: Contesto, esito: dict[str, Any], fatti: list[dict[str, Any]] | None = None,
                             pagamenti: list[dict[str, Any]] | None = None) -> Conclusione | None:
    codice = esito.get("codice")
    if not codice:
        return None
    if esito.get("esenzioneLegge") or ctx.rito.codice == "volontaria_giurisdizione":
        _cat, _dovuto, versati, confronto = _confronto_contributo(ctx, fatti or [], pagamenti or [])
        if confronto.get("esito") == "esente_per_legge":
            documento = esito.get("documento") or {}
            oid = str(documento.get("id") or "")
            atto = ctx.atto(oid)
            fonte = Fonte(oid or "economia", str(documento.get("nome") or "Contributo unificato"),
                          ", ".join(f"€ {v:.2f}" for v in sorted(set(versati))) or "nessuna ricevuta letta",
                          atto.data if atto else "", "documento" if oid else "economia")
            return _conclusione_esente(confronto, fonte)
    if codice == "da_verificare" and ctx.posizione == "attiva":
        # Il presidio non ha deciso: il rito certo e le ricevute lette decidono con la regola del dovuto.
        _cat, _dovuto, versati, confronto = _confronto_contributo(ctx, fatti or [], pagamenti or [])
        if confronto.get("esito") == "insufficiente" and confronto.get("dovuto"):
            documento = esito.get("documento") or {}
            oid = str(documento.get("id") or "")
            atto = ctx.atto(oid)
            fonte = Fonte(oid or "economia", str(documento.get("nome") or "Contributo unificato"),
                          ", ".join(f"€ {v:.2f}" for v in sorted(set(versati))), atto.data if atto else "",
                          "documento" if oid else "economia")
            gia = any(d.accettato for d in ctx.depositi) or bool(ctx.della_causa())
            return _integrazione_contributo(ctx, {**confronto, "letti": versati}, fonte, gia_depositato=gia)
    documento = esito.get("documento") or {}
    oid = str(documento.get("id") or "")
    atto = ctx.atto(oid)
    dettaglio = str(esito.get("dettaglio") or "")
    fonte = Fonte(oid or "economia", str(documento.get("nome") or "Conto economico"),
                  dettaglio, atto.data if atto else "", "documento" if oid else "economia")
    stato = {"pagato": "fatto", "esente": "non_dovuto", "non_dovuto": "non_dovuto"}.get(codice, "dubbio")
    da_versare = (codice == "da_pagare" and ctx.posizione == "attiva"
                  and not any(d.accettato for d in ctx.depositi)
                  and semplice(ctx.fascicolo.get("stato")) not in {"definito", "chiuso", "archiviato"})
    if da_versare:
        stato = "da_fare"
    importo = esito.get("importoLabel") or ""
    etichetta = str(esito["etichetta"]).lower()
    titolo = f"Contributo unificato: {etichetta}" + (f" ({importo})" if importo else "")
    via = "Versare con pagoPA e allegare la ricevuta al deposito." if da_versare else "Aprire il riscontro e le fonti del Conto economico."
    regole = norme("dpr115_art9") if "art. 9" in str(esito.get("norma") or "") else norme("dpr115_art13")
    dubbi = []
    if stato == "dubbio":
        prova = str(esito.get("ruoloFonti") or "ricevuta o titolo di esenzione")
        dubbi.append(Dubbio("contributo_da_riscontrare", dettaglio, prova, fonte))
    return Conclusione(
        "contributo_unificato", titolo, fonte, regole, via,
        "Il riscontro dipende dalle fonti del fascicolo e dal regime applicabile al deposito.",
        stato, dettaglio, onerato="noi" if ctx.posizione == "attiva" else "ignoto", dubbi=dubbi,
        motivo_senza_termine="La voce descrive il versamento o l'esenzione. Un termine autonomo richiede un atto che lo assegni.",
    )


def conclusione_contributo(ctx: Contesto, fatti: list[dict[str, Any]], pagamenti: list[dict[str, Any]],
                           *, stato_condiviso: dict[str, Any] | None = None) -> Conclusione | None:
    """Il contributo unificato dovuto per rito e valore e il confronto con il versato (G-16).

    Regola unica: `pct/contributo_dovuto` (art. 13, commi 1 e 3, D.P.R. 115/2002; il versamento di € 27 è
    l'anticipazione forfettaria dell'art. 30, non il contributo). Esenzione per reddito nelle controversie di
    lavoro: art. 9, comma 1-bis, D.P.R. 115/2002, se l'autocertificazione è stata letta.
    """
    posizione_da_verificare = ctx.posizione == "ignota" and ctx.rito.codice == "volontaria_giurisdizione"
    if ctx.posizione != "attiva" and not posizione_da_verificare:
        return None
    if stato_condiviso is not None:
        return _contributo_dal_presidio(ctx, stato_condiviso, fatti, pagamenti)
    cat, dovuto, versati, esito = _confronto_contributo(ctx, fatti, pagamenti)
    if esito.get("esito") == "esente_per_legge":
        return _conclusione_esente(esito, Fonte("economia", "Contributo unificato", ", ".join(
            f"€ {v:.2f}" for v in sorted(set(versati))) or "nessuna ricevuta letta", "", "economia"))
    esente = any(f.get("campo") == "esenzione_cu_dichiarata" and f.get("verifica") in {"verificata", "corretta"} for f in fatti)
    fonte = Fonte("economia", "Contributo unificato", ", ".join(f"€ {v:.2f}" for v in sorted(set(versati))) or "nessuna ricevuta letta",
                  "", "economia")
    giurisdizione, _ = giurisdizione_e_grado(tipo=ctx.fascicolo.get("tipo", ""), ufficio=ctx.ufficio)
    if not cat and giurisdizione == AMMINISTRATIVO:
        motivo = "Per il ricorso al TAR occorre la ricevuta associata al procedimento oppure la prova di esenzione."
        return Conclusione(
            "contributo_unificato", "Riscontrare il contributo unificato nel fascicolo PAT", fonte,
            norme("dpr115_art13", "dpr115_art9"),
            "Consultare in PAT il deposito del ricorso e la relativa quietanza, dichiarazione di esenzione o richiesta della segreteria.",
            "L’importo dipende dal rito e la prova identifica l’eventuale versamento o esenzione. "
            "Per l’ottemperanza il riferimento ordinario è il comma 6-bis, lett. a), dell’art. 13.",
            "dubbio", motivo, onerato="noi", motivo_senza_termine="Un termine di pagamento richiede un atto che lo assegni.",
            dubbi=[Dubbio("contributo_pat_da_riscontrare", motivo, "quietanza, prova di esenzione o avviso della segreteria", fonte)],
        )
    if cat == "lavoro" and esente and not versati:
        return Conclusione("contributo_unificato", "Contributo unificato non dovuto: esenzione per reddito dichiarata", fonte,
                           norme("dpr115_art9"), "dichiarazione di esenzione nelle conclusioni del ricorso",
                           "nelle controversie di lavoro il contributo non è dovuto sotto la soglia di reddito", "non_dovuto",
                           "autocertificazione dell'esenzione letta negli atti")
    stato = {"coincide": "fatto", "insufficiente": "da_fare"}.get(esito["esito"], "dubbio")
    importo = esito.get("dovuto") or (dovuto.importo if dovuto else None)
    gia_depositato = any(d.accettato for d in ctx.depositi) or semplice(ctx.fascicolo.get("stato")) in {"definito", "chiuso", "archiviato"}
    azione_pagamento = stato == "da_fare" and bool(importo) and not gia_depositato
    if stato == "fatto":
        cosa = f"Contributo unificato versato ({format_euro_it(importo)})"
    elif azione_pagamento:
        cosa = f"Versare il contributo unificato dovuto ({format_euro_it(importo)})"
    elif stato == "da_fare" and importo and versati:
        cosa = f"Verificare la differenza sul contributo unificato ({format_euro_it(importo)} dovuti)"
        stato = "dubbio"
    else:
        cosa = "Riscontrare il contributo unificato"
        stato = "dubbio"
    dubbi = [] if stato != "dubbio" else [Dubbio("contributo_indeterminato", "Il contributo dovuto non si può stabilire con certezza "
             "per questo rito o valore." if not cat else "Il versamento o l’esenzione non risultano riscontrati.",
             "la ricevuta, il titolo di esenzione o un avviso di pagamento riferito al procedimento", fonte)]
    if posizione_da_verificare:
        importo_atteso = f" per il rito ({format_euro_it(importo)})" if importo else ""
        return Conclusione(
            "contributo_unificato", f"Verificare il contributo unificato{importo_atteso}", fonte,
            norme("dpr115_art13", "dpr115_art30"), "controllo del ricorso introduttivo e della ricevuta pagoPA",
            "occorre riscontrare chi ha depositato il ricorso e per quale voce è stato eseguito il versamento",
            "dubbio", esito.get("dettaglio") or "Versamento del contributo da riscontrare.", onerato="ignoto",
            dubbi=[Dubbio("contributo_onerato_ignoto", "Non è accertato chi ha depositato il ricorso.",
                          "l'atto introduttivo e la ricevuta del contributo unificato", fonte)],
        )
    return Conclusione("contributo_unificato", cosa, fonte, norme("dpr115_art13", "dpr115_art30"),
                       "pagamento con pagoPA e deposito della ricevuta con l’atto introduttivo" if azione_pagamento
                       else "aprire la ricevuta originale o riscontrare il titolo di esenzione o un avviso di pagamento",
                       "il contributo è collegato al deposito del ricorso e all’effettiva situazione di versamento o esenzione",
                       stato, esito.get("dettaglio") or "", None, "", onerato="noi", dubbi=dubbi)


__all__ = ["conclusione_contributo", "conclusioni_economia", "liquidazione"]
