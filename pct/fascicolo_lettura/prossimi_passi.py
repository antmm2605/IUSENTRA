"""I prossimi passaggi, in ordine di urgenza e con la ragione di ciascuno.

Non consigli generici: ogni passo nasce da un fatto del fascicolo — una
scadenza aperta, un deposito non accettato, una notifica senza consegna, un
blocco della regia operativa, un documento da verificare, un'udienza vicina —
e dice da dove viene. I termini richiamati sono quelli di legge, indicati con
la norma, senza calcolare date che il fascicolo non contiene.
"""

from __future__ import annotations

from typing import Any

from ._testo import data_da, data_it, pulisci
from .fase import (
    CODICE_FASE_CHIUSA,
    CODICE_FASE_DECISA,
    CODICE_FASE_ISCRITTA,
    CODICE_FASE_NOTIFICATA,
    CODICE_FASE_PREPARATORIA,
)
from .modello import Passo

GIORNI_PROSSIMI = 30
MASSIMO_PASSI = 8


def prossimi_passi(
    fase_letta: dict[str, Any],
    depositi_letti: dict[str, Any],
    notifiche_lette: dict[str, Any],
    documenti_letti: dict[str, Any],
    scadenze: list[dict[str, Any]],
    conformita: dict[str, Any],
    regia: dict[str, Any],
    economico: dict[str, Any],
    oggi: Any,
) -> list[dict[str, Any]]:
    giorno_oggi = data_da(oggi)
    passi: list[Passo] = []

    # Scadenze: prima le scadute, poi quelle vicine.
    for scadenza in scadenze:
        if pulisci(scadenza.get("stato")).upper() not in {"", "APERTO", "APERTA", "IN_CORSO"}:
            continue
        giorno = data_da(scadenza.get("data"))
        titolo = pulisci(scadenza.get("titolo")) or "scadenza"
        if not giorno or not giorno_oggi:
            continue
        distanza = (giorno - giorno_oggi).days
        if distanza < 0:
            passi.append(Passo(0, f"Chiudere o riallineare la scadenza «{titolo}»", f"scaduta il {data_it(giorno)}", data_it(giorno), "scadenziario"))
        elif distanza <= 7:
            passi.append(Passo(1, f"Adempiere a «{titolo}»", f"scade fra {distanza} giorni", data_it(giorno), "scadenziario"))
        elif distanza <= GIORNI_PROSSIMI:
            passi.append(Passo(2, f"Pianificare «{titolo}»", f"scade il {data_it(giorno)}", data_it(giorno), "scadenziario"))

    # Regia operativa: blocchi e azione indicata.
    for blocco in list(regia.get("blockers") or [])[:3]:
        messaggio = pulisci(blocco.get("suggested_action") or blocco.get("message") or blocco)
        if messaggio:
            passi.append(Passo(0, messaggio, "blocco della regia operativa", "", "regia operativa"))
    azione_regia = pulisci(regia.get("next_action") or regia.get("nextAction"))
    if azione_regia and not any(azione_regia == passo.azione for passo in passi):
        passi.append(Passo(2, azione_regia, "indicazione della regia operativa", "", "regia operativa"))

    # Depositi non perfezionati.
    for deposito in depositi_letti["falliti"]:
        passi.append(Passo(0, f"Ripetere il deposito di «{deposito['atto']}»", f"{deposito['fase']}: {deposito['attesa']}", "", "deposito PCT"))
    for deposito in depositi_letti["in_corso"]:
        passi.append(Passo(1, f"Verificare le ricevute del deposito di «{deposito['atto']}»", f"{deposito['fase']}, {deposito['attesa']}", "", "deposito PCT"))

    # Notifiche aperte o fallite.
    for notifica in notifiche_lette["fallite"]:
        passi.append(Passo(0, f"Rinnovare la notifica di «{notifica['atto']}»", notifica["stato_etichetta"], "", "presidio notifiche"))
    for notifica in notifiche_lette["aperte"]:
        if notifica in notifiche_lette["fallite"]:
            continue
        azione = notifica.get("prossima_azione") or f"Completare la notifica di «{notifica['atto']}»"
        passi.append(Passo(1, f"{azione} («{notifica['atto']}»)", notifica["stato_etichetta"], notifica.get("scadenza", ""), "presidio notifiche"))

    # Conformità.
    for voce in list(conformita.get("blocking_issues") or [])[:3]:
        testo = pulisci(voce.get("message") or voce.get("label") or voce) if isinstance(voce, dict) else pulisci(voce)
        if testo:
            passi.append(Passo(0, f"Risolvere: {testo}", "controllo di conformità bloccante", "", "conformità"))
    for voce in list(conformita.get("missing_documents") or [])[:3]:
        testo = pulisci(voce.get("label") or voce.get("name") or voce) if isinstance(voce, dict) else pulisci(voce)
        if testo:
            passi.append(Passo(2, f"Acquisire il documento mancante: {testo}", "richiesto dal profilo di conformità", "", "conformità"))

    # Fase processuale: gli adempimenti che la legge collega alla fase.
    codice = fase_letta.get("codice")
    if codice == CODICE_FASE_PREPARATORIA and not notifiche_lette["tutte"]:
        passi.append(Passo(2, "Notificare l'atto introduttivo alla controparte", "l'atto risulta redatto ma nessuna notifica è registrata", "", "lettura del fascicolo"))
    if codice == CODICE_FASE_NOTIFICATA and not depositi_letti["tutti"]:
        passi.append(Passo(1, "Iscrivere la causa a ruolo depositando l'atto notificato", "termine di costituzione dell'attore: dieci giorni dalla notifica (art. 165 c.p.c.)", "", "lettura del fascicolo"))
    if codice == CODICE_FASE_ISCRITTA and fase_letta.get("prossima_udienza"):
        passi.append(Passo(2, f"Preparare l'udienza del {fase_letta['prossima_udienza']}", "memorie integrative nei termini di legge prima dell'udienza (art. 171-ter c.p.c.)", fase_letta["prossima_udienza"], "lettura del fascicolo"))
    if codice == CODICE_FASE_DECISA:
        passi.append(Passo(1, "Valutare l'impugnazione o l'esecuzione della sentenza", "termine breve di trenta giorni dalla notifica, termine lungo di sei mesi dalla pubblicazione (artt. 325 e 327 c.p.c.)", "", "lettura del fascicolo"))
    if codice != CODICE_FASE_CHIUSA and fase_letta.get("incoerenze"):
        for incoerenza in fase_letta["incoerenze"]:
            passi.append(Passo(2, incoerenza[:1].upper() + incoerenza[1:], "stato del fascicolo non coerente con gli atti", "", "lettura del fascicolo"))

    # Documenti da verificare o non indicizzati.
    if documenti_letti["da_verificare"]:
        quanti = len(documenti_letti["da_verificare"])
        passi.append(Passo(3, f"Confermare la catalogazione di {quanti} document{'o' if quanti == 1 else 'i'} da verificare", "la lettura del fascicolo è completa solo con tutti i documenti catalogati", "", "catalogazione"))
    if not documenti_letti.get("procura") and documenti_letti["totale"]:
        passi.append(Passo(3, "Verificare la presenza della procura alle liti fra i documenti", "nessun documento è catalogato come procura", "", "catalogazione"))

    # Economico.
    sintesi = dict(economico.get("summary") or {})
    if sintesi:
        if not sintesi.get("totale_conferimenti") and not sintesi.get("totale_preventivi"):
            passi.append(Passo(3, "Formalizzare preventivo e conferimento d'incarico", "nessun preventivo o conferimento risulta collegato (art. 13 L. 247/2012)", "", "economico"))
        elif float(sintesi.get("totale_fatturato") or 0) > float(sintesi.get("totale_incassato") or 0):
            passi.append(Passo(3, "Sollecitare l'incasso delle parcelle emesse", "fatturato superiore all'incassato", "", "economico"))

    passi.sort(key=lambda passo: passo.urgenza)
    visti: set[str] = set()
    unici: list[dict[str, Any]] = []
    for passo in passi:
        chiave = passo.azione.lower()
        if chiave in visti:
            continue
        visti.add(chiave)
        unici.append(passo.come_dizionario())
        if len(unici) >= MASSIMO_PASSI:
            break
    return unici


__all__ = ["GIORNI_PROSSIMI", "MASSIMO_PASSI", "prossimi_passi"]
