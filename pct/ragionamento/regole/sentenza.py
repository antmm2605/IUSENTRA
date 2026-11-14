"""Dopo la sentenza della causa: termine per impugnare, passaggio in giudicato, esecuzione contro la P.A.

I calcoli che nascono dalla notifica sono una sola regola del software, `pct/sentenza_notificata.py`:
termine breve di trenta giorni anche per chi notifica (artt. 325 e 326 c.p.c.; nel lavoro ricorso in appello
depositato entro trenta giorni, art. 434, senza sospensione feriale, art. 3 L. 742/1969), passaggio in
giudicato (art. 324 c.p.c.) e centoventi giorni prima del precetto contro l'amministrazione (art. 14 D.L.
669/1996). Qui diventano conclusioni del modello. Senza notifica vale il termine lungo di sei mesi dalla
pubblicazione (art. 327 c.p.c.). Le sentenze di altri procedimenti allegate come precedenti sono atti di
contorno e non arrivano qui (G-8).
"""

from __future__ import annotations

from pct.sentenza_notificata import condanna_al_pagamento, termini_dalla_notifica
from pct.termine_lungo_sentenza import data_pubblicazione as leggi_pubblicazione
from pct.termini_processuali import ItalianDeadlineCalculator

from ..modello import Conclusione, Dubbio, Fonte
from ..norme import norme
from ..notifiche import notifiche_di
from ..testo import data_it, giorno, pulito
from .calcolo import esito
from .contesto import Contesto

def data_pubblicazione(testo: str) -> str:
    # L'intestazione appartiene all'atto esaminato. Le citazioni nella
    # motivazione possono indicare la pubblicazione di altre sentenze.
    pubblicazione = leggi_pubblicazione(testo[:1500], comunicazione=False)
    return pubblicazione.isoformat() if pubblicazione else ""


def _dalla_notifica(ctx: Contesto, fonte: Fonte, base: str, condanna: bool, *, titolo_verificato: bool) -> list[Conclusione]:
    lavoro = ctx.rito.codice == "lavoro"
    esiti: list[Conclusione] = []
    termine_breve = ""
    for calcolo in termini_dalla_notifica(base, lavoro=lavoro, contro_pa=ctx.rito.contro_pa, condanna=condanna and titolo_verificato, oggi=ctx.oggi):
        scadenza = giorno(calcolo.get("deadline"))
        if calcolo["codice"] == "termine_breve_impugnazione":
            termine_breve = scadenza.isoformat() if scadenza else ""
            termine = esito(scadenza, oggi=ctx.oggi, perentorio=True, decorrenza=base, evento="notifica della sentenza",
                            computo=calcolo["formula"], rito=ctx.rito,
                            conseguenze="scaduto il termine senza impugnazione la sentenza passa in giudicato (art. 324 c.p.c.)")
            esiti.append(Conclusione(
                "termine_impugnazione", "Ricorso in appello (deposito) per la parte soccombente" if lavoro else
                "Atto di appello (notifica) per la parte soccombente", fonte,
                norme("cpc_325", "cpc_326", "cpc_434") if lavoro else norme("cpc_325", "cpc_326"),
                "deposito telematico del ricorso in Corte d'appello" if lavoro else "notifica dell'atto di citazione in appello",
                "è il rimedio contro la sentenza; scaduto il termine la sentenza diventa definitiva",
                "non_dovuto", "termine per chi intende impugnare: lo studio ha notificato la sentenza", termine,
                "builtin-tmp-lav-016" if lavoro else "builtin-tmp-imp-001", onerato="tutte_le_parti",
            ))
        elif calcolo["codice"] == "passaggio_in_giudicato":
            maturato = bool(scadenza and scadenza <= ctx.oggi)
            esiti.append(Conclusione(
                "giudicato", "Chiedere alla cancelleria l'attestazione del passaggio in giudicato", fonte, norme("cpc_324", "cc_2909"),
                "istanza alla cancelleria dell'ufficio che ha pronunciato la sentenza", calcolo["formula"],
                "da_fare" if maturato else "non_dovuto", "" if maturato else f"non ancora: il giudicato matura dal {data_it(scadenza)}",
                esito(scadenza, oggi=ctx.oggi, perentorio=None, decorrenza=termine_breve, evento="scadenza del termine breve",
                      computo="giorno successivo alla scadenza del termine breve", rito=ctx.rito,
                      natura="data da cui verificare il giudicato"),
            ))
        elif calcolo["codice"] == "esecuzione_pa_120_giorni" and ctx.posizione == "attiva":
            dopo = bool(scadenza and scadenza < ctx.oggi)
            termine = esito(scadenza, oggi=ctx.oggi, perentorio=None, decorrenza=base, evento="notifica del titolo esecutivo",
                            computo="centoventi giorni dalla notifica del titolo (art. 14 D.L. 669/1996)",
                            conseguenze=calcolo["formula"], natura="attesa minima prima del precetto")
            termine.sospensione_feriale = "non si applica (termine di adempimento dell'amministrazione, non processuale)"
            esiti.append(Conclusione(
                "esecuzione_pa", "Notificare l'atto di precetto all'amministrazione, se non ha pagato", fonte,
                norme("dl669_art14", "cpc_480", "cpc_474", "cpc_475"), "verificare il titolo notificato, in copia attestata conforme o duplicato informatico, e notificare il precetto",
                "prima dei centoventi giorni il precetto è vietato; dopo, se l'amministrazione non ha pagato, è il primo atto "
                "dell'esecuzione forzata (art. 14 D.L. 669/1996; art. 480 c.p.c.)",
                "da_fare" if dopo else "non_dovuto", "" if dopo else f"non ancora: i 120 giorni scadono il {data_it(scadenza)}",
                termine, "builtin-tmp-ese-001",
            ))
    if ctx.rito.contro_pa and condanna and not titolo_verificato and ctx.posizione == "attiva":
        motivo = "Per i 120 giorni occorre provare la notificazione del titolo esecutivo all'amministrazione obbligata."
        esiti.append(Conclusione(
            "esecuzione_pa", "Verificare la notifica del titolo prima del precetto", fonte,
            norme("dl669_art14", "cpc_475"), "controllare la copia conforme o il duplicato, la relata e la consegna",
            "l'attesa minima decorre dalla notifica del titolo esecutivo", "dubbio", motivo,
            dubbi=[Dubbio("notifica_titolo_da_verificare", motivo, "la prova della notificazione del titolo esecutivo", fonte)],
        ))
    return esiti


def conclusioni_sentenza(ctx: Contesto) -> list[Conclusione]:
    risultato: list[Conclusione] = []
    visti: set[str] = set()
    for sentenza in [a for a in ctx.della_causa() if a.sentenza]:
        if sentenza.id in visti:
            continue
        visti.update([sentenza.id, *sentenza.copie])
        pubblicata = giorno(data_pubblicazione(sentenza.testo))
        fonte = Fonte(sentenza.id, sentenza.nome, pulito(sentenza.testo[:300]), pubblicata.isoformat() if pubblicata else sentenza.data)
        candidate = [n for n in notifiche_di(sentenza.id, ctx.notifiche, ctx.atti) if n.data_invio]
        prove = [ctx.consegne_verificate[oid] for oid in (sentenza.id, *sentenza.copie)
                 if oid in ctx.consegne_verificate]
        date_provate = {prova.get("data", "") for prova in prove if prova.get("riferimento")}
        base = next(iter(date_provate)) if len(date_provate) == 1 else ""
        if giorno(base) and giorno(base) <= ctx.oggi and (not pubblicata or giorno(base) >= pubblicata):
            prova = next(p for p in prove if p.get("data") == base and p.get("riferimento"))
            risultato.append(Conclusione(
                "notifica_sentenza", "Notificare la sentenza alla controparte", fonte, norme("cpc_326", "l53_art3bis"),
                "notifica a mezzo PEC con relata (art. 3-bis L. 53/1994)",
                "la notifica fa decorrere il termine breve per impugnare per entrambe le parti (art. 326 c.p.c.)", "fatto",
                f"Consegna verificata del {data_it(base)}, prova {prova['riferimento']}.",
                None, "builtin-tmp-not-003",
                motivo_senza_termine="La data di consegna alimenta la verifica del termine per impugnare.",
            ))
            risultato.extend(_dalla_notifica(
                ctx, fonte, base, condanna_al_pagamento(sentenza.testo),
                titolo_verificato=prova.get("titolo_esecutivo") == "verificato",
            ))
            continue
        invio_storico, data_invio_storico = next(
            (ctx.notifiche_storiche[oid] for oid in (sentenza.id, *sentenza.copie)
             if oid in ctx.notifiche_storiche), ("", ""),
        )
        if candidate or prove or invio_storico:
            motivo = "Manca una consegna univoca con ricevute verificate e correlate alla notifica della sentenza."
            manca = "la ricevuta originale riferita alla sentenza"
            fonte_dubbio = fonte
            testo_dubbio = motivo
            if invio_storico:
                motivo = "Nel fascicolo sono state collegate le ricevute originali all’invio della sentenza."
                testo_dubbio = "La verifica della notifica è ancora da completare."
                manca = "la verifica storica delle revoche e il riscontro della relata e dei domicili digitali"
                atto_invio = ctx.atto(invio_storico)
                if atto_invio:
                    fonte_dubbio = Fonte(atto_invio.id, atto_invio.nome, "Ricevuta di accettazione della notifica", data_invio_storico)
            risultato.append(Conclusione(
                "notifica_sentenza", "Verificare la consegna della notifica della sentenza", fonte,
                norme("cpc_326", "l53_art3bis"), "riscontro della relata e della ricevuta originale per il destinatario",
                "occorre la prova di consegna prima di calcolare il termine breve", "dubbio", motivo,
                motivo_senza_termine="Il termine breve richiede la prova del perfezionamento per il destinatario.",
                dubbi=[Dubbio("consegna_da_verificare", testo_dubbio, manca, fonte_dubbio)],
            ))
        else:
            risultato.append(Conclusione(
                "notifica_sentenza", "Notificare la sentenza per far decorrere il termine breve", fonte, norme("cpc_326", "cpc_327"),
                "notifica a mezzo PEC con relata (art. 3-bis L. 53/1994)",
                "senza notifica la sentenza resta impugnabile per sei mesi dalla pubblicazione (art. 327 c.p.c.)",
                "da_fare", "scelta difensiva: la notifica accorcia il termine per impugnare", None, "builtin-tmp-not-003",
                motivo_senza_termine="La notifica è una scelta difensiva. Il termine per impugnare è valutato a parte.",
            ))
        if pubblicata and pubblicata <= ctx.oggi:
            calcolo = ItalianDeadlineCalculator().calculate(
                pubblicata, 6, direction="forward", period_type="months", suspend_august=ctx.rito.sospensione_feriale,
                ferial_suspension_policy="applies" if ctx.rito.sospensione_feriale else "not_applicable", reference_law="art. 327 c.p.c.")
            lungo = esito(giorno(calcolo.get("deadline")), oggi=ctx.oggi, perentorio=True, decorrenza=pubblicata.isoformat(),
                          evento="pubblicazione della sentenza", rito=ctx.rito,
                          computo="sei mesi dalla pubblicazione (art. 327 c.p.c.), con la proroga dell'art. 155 c.p.c.",
                          conseguenze="scaduto il termine lungo la sentenza passa in giudicato (art. 324 c.p.c.)")
            lavoro = ctx.rito.codice == "lavoro"
            norme_impugnazione = norme("cpc_327", "cpc_324", "cpc_434") if lavoro else norme("cpc_327", "cpc_324")
            come = "Deposito del ricorso in appello presso la Corte d’appello (art. 434 c.p.c.)" if lavoro else "Atto di appello"
            if lungo.scaduto:
                come = "Verificare a registro se risulta un’impugnazione tempestiva."
            risultato.append(Conclusione(
                "termine_impugnazione", "Impugnazione della sentenza (termine lungo)", fonte, norme_impugnazione,
                come, "Il decorso senza impugnazione rileva ai fini del giudicato.", "non_dovuto",
                "termine per chi intende impugnare", lungo, onerato="tutte_le_parti",
            ))
        else:
            motivo = ("La pubblicazione della sentenza va accertata nel registro di cancelleria. "
                      "La data della decisione e un’eventuale bozza in agenda non attestano il deposito.")
            risultato.append(Conclusione(
                "termine_impugnazione", "Verificare la pubblicazione della sentenza per stabilire il termine lungo",
                fonte, norme("cpc_133", "cpc_327"), "verificare la pubblicazione nel registro di cancelleria",
                "dalla pubblicazione decorre il termine lungo per impugnare", "dubbio", motivo,
                onerato="tutte_le_parti",
                motivo_senza_termine="La data ufficiale di deposito è necessaria per il computo.",
                dubbi=[Dubbio("pubblicazione_da_verificare", motivo, "la data ufficiale di pubblicazione della sentenza", fonte)],
            ))
    return risultato


__all__ = ["conclusioni_sentenza", "data_pubblicazione"]
