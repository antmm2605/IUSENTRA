"""Procedimento monitorio: dal decreto ingiuntivo al precetto, senza udienze se non c'è opposizione (G-10).

- il decreto ingiuntivo diventa inefficace se non è notificato entro sessanta giorni dalla pronuncia
  (art. 644 c.p.c.);
- dalla notifica decorrono i quaranta giorni per l'opposizione (art. 641 c.p.c.);
- senza opposizione il giudice, su istanza del ricorrente, dichiara esecutivo il decreto (art. 647 c.p.c.);
- con il decreto esecutivo si notifica il precetto (art. 480 c.p.c.), che perde efficacia se entro novanta giorni
  non inizia l'esecuzione (art. 481 c.p.c.).
Il decreto è «dello studio» quando nomina come difensore del ricorrente un avvocato dello studio.
"""

from __future__ import annotations

import re

from ..modello import Conclusione, Dubbio, Fonte
from ..norme import norme
from ..notifiche import notifiche_di
from ..testo import data_it, date_nel_testo, giorno, pulito, semplice
from .calcolo import in_avanti
from .contesto import Contesto


def _decreto(ctx: Contesto):
    candidati = [a for a in ctx.della_causa() if a.autore == "giudice" and "decreto ingiuntivo" in semplice(a.etichetta)]
    return min(candidati, key=lambda a: a.data or "9999") if candidati else None


def decreto_esecutivo(ctx: Contesto, decreto=None):
    decreto = decreto or _decreto(ctx)
    if decreto is None or not decreto.data:
        return None
    return next((
        a for a in ctx.della_causa()
        if a.id != decreto.id and a.autore == "giudice" and a.natura == "provvedimento"
        and a.data and a.data >= decreto.data
        and re.search(r"\bdichiara\s+esecutiv[oa]\s+il\s+decreto\s+ingiuntivo\b", semplice(a.testo))
    ), None)


def _atto_con(ctx: Contesto, *parole: str):
    return next((a for a in ctx.della_causa() if all(p in semplice(f"{a.etichetta} {a.nome}") for p in parole)), None)


def istanza_esecutorieta(ctx: Contesto):
    return next((a for a in ctx.della_causa() if a.natura == "istanza"
                 and ("647" in a.etichetta or "esecutor" in semplice(a.nome))), None)


def _giorni_opposizione(testo: str) -> int | None:
    parole = {"dieci": 10, "venti": 20, "trenta": 30, "quaranta": 40,
              "cinquanta": 50, "sessanta": 60, "novanta": 90, "centoventi": 120}
    trovati = set()
    for m in re.finditer(r"\b(?:entro|nel termine(?: perentorio)? di)\s+(\d{1,3}|"
                         + "|".join(parole) + r")\s+giorni\s+dalla\s+notif", semplice(testo)):
        valore = m.group(1)
        trovati.add(int(valore) if valore.isdigit() else parole[valore])
    return next(iter(trovati)) if len(trovati) == 1 else None


def decorrenze_incoerenti(ctx: Contesto) -> list[tuple[str, str, Fonte]]:
    """Date di decorrenza scritte in un'istanza ex art. 647 anteriori al decreto."""
    if ctx.rito.codice != "monitorio":
        return []
    decreto = _decreto(ctx)
    pronuncia = giorno(decreto.data) if decreto else None
    if pronuncia is None:
        return []
    esiti = {}
    for atto in ctx.della_causa():
        if atto.natura != "istanza" or "esecutor" not in semplice(atto.nome + " " + atto.etichetta):
            continue
        for data in re.finditer(r"\bdecorrent[ei]\s+dal(?:la)?\s+", atto.testo, re.IGNORECASE):
            segmento = atto.testo[data.end():data.end() + 16]
            date = date_nel_testo(segmento)
            if date and date[0][0] == 0 and date[0][2] < pronuncia:
                letta = date[0][2].isoformat()
                fonte = Fonte(atto.id, atto.nome, pulito(atto.testo[data.start():data.end() + date[0][1]]), atto.data)
                esiti.setdefault(letta, (letta, pronuncia.isoformat(), fonte))
    return list(esiti.values())


def conclusioni_monitorio(ctx: Contesto) -> list[Conclusione]:
    if ctx.rito.codice != "monitorio":
        return []
    decreto = _decreto(ctx)
    if decreto is None:
        return []
    pronuncia = giorno(decreto.data)
    fonte = Fonte(decreto.id, decreto.nome, pulito(decreto.testo[:400]), decreto.data)
    esito: list[Conclusione] = []
    ricorsi = [a for a in ctx.della_causa() if a.natura == "atto_principale"
               and "decreto ingiuntivo" in semplice(a.etichetta)]
    tracce = notifiche_di(decreto.id, ctx.notifiche, ctx.atti)
    tracce += [n for a in ricorsi for n in notifiche_di(a.id, ctx.notifiche, ctx.atti)]
    prova_decreto = ctx.consegne_verificate.get(decreto.id) or {}
    data_consegna = giorno(prova_decreto.get("data"))
    riferimento = prova_decreto.get("riferimento")
    prova_congiunta = bool(
        riferimento and data_consegna and pronuncia and pronuncia <= data_consegna <= ctx.oggi
        and len(ricorsi) == 1 and ctx.consegne_verificate.get(ricorsi[0].id) == prova_decreto
    )
    da_verificare = bool(tracce or prova_decreto)
    dubbi = []
    if da_verificare and not prova_congiunta:
        dubbi.append(Dubbio("consegna_monitorio_da_verificare", "È presente una traccia della notifica.",
                            "la prova di consegna che collega sia il ricorso sia il decreto al destinatario", fonte))
    if not prova_congiunta:
        dubbi.append(Dubbio("destinazione_monitorio_da_verificare", "La destinazione determina il termine di notifica.",
                            "il luogo di notificazione dell'ingiunzione per applicare l'art. 644 c.p.c.", fonte))
    esito.append(Conclusione(
        "notifica_decreto_ingiuntivo", "Verificare la notifica di ricorso e decreto ingiuntivo" if da_verificare and not prova_congiunta
        else "Notificare il ricorso e il decreto ingiuntivo al debitore", fonte, norme("cpc_643", "cpc_644", "l53_art3bis"),
        "notifica a mezzo PEC con relata quando applicabile, oppure tramite ufficiale giudiziario",
        "il decreto perde efficacia se non notificato nei termini dell'art. 644 c.p.c.",
        "fatto" if prova_congiunta else "dubbio" if da_verificare else "da_fare",
        f"Consegna verificata del {data_it(prova_decreto['data'])}, prova {riferimento}." if prova_congiunta else "",
        None, "builtin-tmp-not-003", dubbi=dubbi,
        motivo_senza_termine="Consegna verificata. Il computo della tempestività richiede la destinazione e la prova lato mittente."
        if prova_congiunta else "",
    ))
    giorni = _giorni_opposizione(decreto.testo)
    opposizione = in_avanti(
        data_consegna, giorni, rito=ctx.rito, oggi=ctx.oggi, perentorio=True, evento="consegna di ricorso e decreto",
        norma="art. 641 c.p.c.", conseguenze="verificare se è stata proposta opposizione e se il giudice ha dichiarato l'esecutorietà",
    ) if prova_congiunta and giorni else None
    istanza = istanza_esecutorieta(ctx)
    esecutorieta = decreto_esecutivo(ctx, decreto)
    fonte_istanza = Fonte(istanza.id, istanza.nome, pulito(istanza.testo[:400]), istanza.data) if istanza else fonte
    verifica_opposizione = Dubbio(
        "opposizione_da_verificare", "Occorre accertare lo stato dell'opposizione e dell'istanza.",
        "il termine indicato dal decreto, la notifica completa e l'esito del registro di cancelleria", fonte_istanza,
    )
    stato = "fatto" if esecutorieta else "non_dovuto" if opposizione and not opposizione.scaduto and not istanza else "dubbio"
    esito.append(Conclusione(
        "esecutorieta_647", "Verificare i presupposti per chiedere l'esecutorietà del decreto ingiuntivo",
        fonte_istanza, norme("cpc_641", "cpc_647"),
        "consultare il registro e, se ne ricorrono i presupposti, depositare istanza ex art. 647 c.p.c.",
        "il giudice decide sull'esecutorietà dopo aver verificato i presupposti dell'art. 647 c.p.c.",
        stato, f"Provvedimento «{esecutorieta.nome}»" if esecutorieta else
        "Il termine per l'opposizione è in corso." if stato == "non_dovuto" else verifica_opposizione.testo,
        opposizione, dubbi=[verifica_opposizione] if stato == "dubbio" else [],
        motivo_senza_termine="L'esecutorietà è documentata dal provvedimento del giudice." if esecutorieta else "",
    ))
    precetto = _atto_con(ctx, "precetto")
    if istanza or esecutorieta:
        fonte_titolo = (Fonte(esecutorieta.id, esecutorieta.nome, pulito(esecutorieta.testo[:400]), esecutorieta.data)
                        if esecutorieta else fonte)
        dubbio = Dubbio("titolo_esecutivo_da_verificare", "L'istanza chiede l'esecutorietà del decreto.",
                        "il provvedimento che dichiara esecutivo il decreto", fonte)
        esito.append(Conclusione(
            "precetto", "Preparare la notifica del precetto con il decreto ingiuntivo esecutivo" if esecutorieta
            else "Verificare il titolo esecutivo prima di preparare il precetto", fonte_titolo,
            norme("cpc_480", "cpc_481", "cpc_474"),
            "notifica del precetto al debitore, a mezzo PEC quando applicabile o tramite ufficiale giudiziario",
            "il precetto intima il pagamento ed è il presupposto dell'esecuzione forzata",
            "dubbio" if not esecutorieta or precetto else "da_fare",
            f"Precetto presente nel fascicolo, verificare la prova di notifica: «{precetto.nome}»" if precetto
            else "Il provvedimento dichiara esecutivo il decreto." if esecutorieta else dubbio.testo,
            None, "builtin-tmp-ese-001", dubbi=[] if esecutorieta else [dubbio],
        ))
    return esito


__all__ = ["conclusioni_monitorio"]
