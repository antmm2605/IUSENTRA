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

import re

from pct.percorso_pratica.esito import codice_esito_dispositivo, dispositivo, improcedibile_per_interesse
from pct.percorso_pratica.giurisdizioni import AMMINISTRATIVO, CIVILE, IMPUGNAZIONI_PER_GRADO, PRIMO, giurisdizione_e_grado
from pct.riconvalida_termine_lungo import CODICE_TERMINE_LUNGO, DALLA_DECISIONE, MARCATORE_PEC, NON_CERTA
from pct.sentenza_notificata import condanna_al_pagamento, termini_dalla_notifica
from pct.termine_lungo_sentenza import data_decisione, data_pubblicazione as leggi_pubblicazione
from pct.termine_lungo_sentenza import data_pubblicazione_pat
from pct.termini_processuali import ItalianDeadlineCalculator

from ..modello import Conclusione, Dubbio, Fonte
from ..norme import norme
from ..notifiche import notifiche_di
from ..testo import data_it, giorno, pulito
from .calcolo import esito, in_avanti
from .contesto import Contesto

def data_pubblicazione(testo: str) -> str:
    # L'intestazione appartiene all'atto esaminato. Le citazioni nella
    # motivazione possono indicare la pubblicazione di altre sentenze.
    pubblicazione = leggi_pubblicazione(testo[:1500], comunicazione=False)
    return pubblicazione.isoformat() if pubblicazione else ""


def termini_lunghi_prudenziali(atti, documenti, scadenze) -> dict[str, str]:
    """Riusa il termine già in Agenda se la bozza e la sentenza hanno la stessa PEC fonte."""
    origini = {doc["id"]: doc.get("pec_origine") for doc in documenti if doc.get("id")}
    bozze = [s for s in scadenze if s.get("deadline_profile_code") == CODICE_TERMINE_LUNGO
             and s.get("stato") == "BOZZA" and NON_CERTA in (s.get("note") or "")]
    esiti = {}
    for atto in atti:
        if not atto.sentenza or atto.appartenenza != "causa":
            continue
        pec = origini.get(atto.id)
        if not pec or not pec.startswith("pec_"):
            continue
        decisione = data_decisione(atto.testo)
        if not decisione:
            continue
        marcatore = f"{MARCATORE_PEC}{pec}:{CODICE_TERMINE_LUNGO}"
        scadenze_lette = {
            s["data"] for s in bozze if s.get("source_message_id") == pec and giorno(s.get("data"))
            and giorno(s.get("data_decorrenza")) == decisione and marcatore in (s.get("note") or "").splitlines()
            and f"{DALLA_DECISIONE} decisione={decisione.isoformat()}:" in (s.get("note") or "")
        }
        if len(scadenze_lette) == 1:
            esiti[atto.id] = scadenze_lette.pop()
    return esiti


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


_ORDINE_OTTEMPERANZA = re.compile(
    r"\bordina\s+all[’']amministrazione\b[^;]{0,240}\b(?:dare\s+esecuzione|ottemperare)\b"
    r"[^;]{0,240}\b(?:entro\s+il|nel)\s+termine\s+di\s+(?P<giorni>[1-9]\d{0,2})(?:\s*\([^)]{1,24}\))?"
    r"\s+giorni\b[^;]{0,160}\b(?:comunicazione\s+(?:o|ovvero)\s+notificazione|notificazione\s+(?:o|ovvero)\s+comunicazione)\b[^;]{0,80}",
    re.IGNORECASE,
)


def _appello_ottemperanza(sentenza, fonte: Fonte, ctx: Contesto) -> Conclusione | None:
    intestazione = pulito(sentenza.testo[:4500])
    epigrafe = re.split(r"\bVist[ioe]\s+(?:il\s+ricorso|gli\s+atti|l['’]atto)\b", intestazione, maxsplit=1, flags=re.I)[0]
    if not re.search(r"\bsul ricorso\b.*?\bper\s+l['’]\s*ottemperanza\b", epigrafe, re.I):
        return None
    if re.search(r"\bper\s+l['’]\s*annullamento\b", epigrafe, re.I):
        return None
    pubblicazione = (giorno(getattr(sentenza, "pubblicazione_pat", "")) or data_pubblicazione_pat(sentenza.testo)
                     or giorno(data_pubblicazione(sentenza.testo)))
    if not pubblicazione or pubblicazione > ctx.oggi:
        return None
    fonte = Fonte(fonte.oggetto_id, fonte.nome, fonte.brano, pubblicazione.isoformat(), fonte.tipo)
    calcolo = ItalianDeadlineCalculator().calculate(
        pubblicazione, 3, direction="forward", period_type="months",
        suspend_august=True, ferial_suspension_policy="applies", reference_law="artt. 87, 92 e 54 c.p.a.",
    )
    termine = esito(
        giorno(calcolo.get("deadline")), oggi=ctx.oggi, perentorio=True,
        decorrenza=pubblicazione.isoformat(), evento="pubblicazione della sentenza nel registro TAR",
        computo="tre mesi dalla pubblicazione nel giudizio di ottemperanza, con sospensione feriale",
        conseguenze="Per impugnare occorre notificare il ricorso in appello entro il termine applicabile.",
    )
    termine.sospensione_feriale = "si applica (art. 54, comma 2, c.p.a., dal 1° al 31 agosto)"
    if termine.scaduto:
        termine.rimedi = "Verificare a registro le impugnazioni. L’errore scusabile si valuta ai sensi dell’art. 37 c.p.a."
    date_notifiche = {
        data for oid in (sentenza.id, *sentenza.copie)
        if (prova := ctx.consegne_verificate.get(oid)) and prova.get("riferimento")
        and (data := giorno(prova.get("data"))) and pubblicazione <= data <= ctx.oggi
    }
    cosa = "Valutare l’appello in ottemperanza (limite dalla pubblicazione)"
    motivo = ("Verificare l’interesse concreto del cliente e controllare nel registro PAT se una notifica valida "
              "ha fatto decorrere prima il termine breve di trenta giorni.")
    if len(date_notifiche) == 1:
        notifica = next(iter(date_notifiche))
        breve = in_avanti(notifica, 30, rito=ctx.rito, oggi=ctx.oggi, perentorio=True,
                          evento="notifica verificata della sentenza", norma="artt. 87 e 92 c.p.a.", feriale=True)
        if breve.scadenza < termine.scadenza:
            breve.sospensione_feriale = termine.sospensione_feriale
            breve.conseguenze = termine.conseguenze
            breve.rimedi = "Verificare a registro le impugnazioni e l’eventuale errore scusabile (art. 37 c.p.a.)." if breve.scaduto else ""
            termine = breve
            cosa = "Valutare l’appello in ottemperanza (termine dalla notifica)"
        motivo = ("Verificare l’interesse concreto del cliente e le eventuali impugnazioni. "
                  "La scadenza considera il termine più vicino tra pubblicazione e notifica verificata.")
    return Conclusione(
        "termine_impugnazione", cosa, fonte, norme("cpa_100", "cpa_89", "cpa_92", "cpa_87", "cpa_54"),
        "Verificare nel registro PAT le notifiche, le eventuali impugnazioni e l’interesse concreto del cliente.",
        "Nel giudizio di ottemperanza il termine lungo è di tre mesi dalla pubblicazione.",
        "dubbio", motivo, termine, onerato="tutte_le_parti",
        dubbi=[Dubbio("verifica_appello_ottemperanza", motivo, "il riscontro nel registro PAT e l’interesse a impugnare", fonte)],
    )


def _sentenza_amministrativa(sentenza, fonte: Fonte, *, grado: str, ctx: Contesto) -> list[Conclusione]:
    rimedio = IMPUGNAZIONI_PER_GRADO[(AMMINISTRATIVO, grado)][0]
    mezzo = "cpa_100" if grado == PRIMO else "cpa_110"
    esito_dispositivo = dispositivo(sentenza.testo)
    appello_ottemperanza = _appello_ottemperanza(sentenza, fonte, ctx) if grado == PRIMO else None
    ordine = _ORDINE_OTTEMPERANZA.search(esito_dispositivo)
    if (grado == PRIMO and ctx.posizione == "attiva" and ordine and "ottemperanza" in sentenza.testo[:2000].casefold()
            and codice_esito_dispositivo(esito_dispositivo) == "accoglimento"):
        clausola = ordine.group().strip(" .")
        fonte_ordine = Fonte(sentenza.id, sentenza.nome, clausola, fonte.data)
        giorni = ordine["giorni"]
        motivo = f"Il TAR assegna all’Amministrazione {giorni} giorni dalla comunicazione o notificazione della sentenza."
        identificativi = {sentenza.id, *sentenza.copie}
        spedizioni = [(oid, prova) for oid, prova in ctx.prove_notifiche_storiche.items()
                      if identificativi.intersection(prova["documenti_allegati"])]
        distinta = {}
        riscontro = ""
        verifica = "Verificare la decorrenza prevista dal dispositivo e l’eventuale esecuzione."
        if len(spedizioni) == 1:
            invio, prova = spedizioni[0]
            consegne = prova["consegne"]
            date_consegna = sorted({str(r.get("data") or "")[:10] for r in consegne
                                   if giorno(str(r.get("data") or "")[:10])})
            distinta = {"invio_id": invio, "accettazione_id": prova["accettazione_id"],
                        "consegne_ids": [r["documento_id"] for r in consegne]}
            if date_consegna:
                motivo += f" Ricevute PEC della sentenza del {', '.join(map(data_it, date_consegna))}."
            riscontro = "Invio e ricevute correlate al documento per impronta."
            verifica = ("Riscontrare il recapito all’Amministrazione obbligata, la validità della notifica, "
                        "l’eventuale comunicazione del TAR e l’esecuzione dell’ordine.")
        if re.search(r"\bnomina\b[^;]{0,100}\bcommissario\s+ad\s+acta\b", esito_dispositivo, re.IGNORECASE):
            motivo += " In caso di inadempimento, verificare l’attivazione del commissario ad acta nominato."
        return [
            Conclusione("verifica_ottemperanza", "Riscontrare l’esecuzione ordinata dal TAR",
                        fonte_ordine, norme("cpa_114", "l53_art3bis") if distinta else norme("cpa_114"),
                        verifica,
                        motivo, "dubbio", riscontro, onerato="noi",
                        motivo_senza_termine="La data di decorrenza dell’ordine è ancora da riscontrare.",
                        dubbi=[Dubbio("decorrenza_esecuzione_tar", f"{motivo} {verifica}",
                                     "la prova della decorrenza e il riscontro dell’esecuzione", fonte_ordine)],
                        prova_notifica=distinta),
            appello_ottemperanza or Conclusione("termine_impugnazione", "Valutare un eventuale interesse residuo a impugnare",
                        fonte_ordine, norme(mezzo, "cpa_89", "cpa_92", "cpa_87"),
                        "Esaminare gli eventuali capi sfavorevoli del dispositivo",
                        "Il ricorso è accolto. L’impugnazione richiede un interesse concreto.",
                        "non_dovuto", "Il dispositivo accoglie il ricorso del cliente."),
        ]
    if improcedibile_per_interesse(esito_dispositivo):
        fonte_esito = Fonte(sentenza.id, sentenza.nome, pulito(esito_dispositivo)[:400], fonte.data)
        return [Conclusione(
            "esito_rito", "Improcedibilità per sopravvenuto difetto di interesse", fonte_esito, norme("cpa_35"),
            "Conservare la sentenza e il riscontro dell’adempimento, se acquisito al fascicolo.",
            "Il TAR ha chiuso il giudizio in rito. L’interesse residuo dipende dalla situazione concreta documentata.",
            "fatto", "Dispositivo letto nella sentenza del fascicolo.",
            motivo_senza_termine="La pronuncia in rito non accerta da sola l’esecuzione del titolo.",
        ), appello_ottemperanza or Conclusione(
            "termine_impugnazione", "Valutare l’impugnazione solo se rimane un interesse concreto",
            fonte_esito, norme(mezzo, "cpa_89", "cpa_92", "cpa_87"),
            "Aprire il registro PAT del fascicolo e verificare pubblicazione, notificazione e rito applicabile.",
            "Il termine decorre dalla fonte prevista dal codice del processo amministrativo.",
            "dubbio", "Una pronuncia in rito richiede una valutazione dell’utilità concreta di impugnare.",
            motivo_senza_termine="Il termine va ancorato alla pubblicazione o alla notifica provata della sentenza del TAR.",
            dubbi=[Dubbio("decorrenza_impugnazione_pat", "Controllare il termine anche dopo l’improcedibilità.",
                          "la pubblicazione o la prova della notifica, e il rito applicabile", fonte_esito)],
        )]
    if appello_ottemperanza:
        return [appello_ottemperanza]
    motivo = "Il computo richiede la pubblicazione in segreteria, la notifica eventualmente perfezionata e il rito applicabile."
    return [Conclusione(
        "termine_impugnazione", rimedio["rimedio"], fonte, norme(mezzo, "cpa_89", "cpa_92", "cpa_87"),
        "Verificare nel registro PAT gli estremi di pubblicazione e nella relata la notificazione della sentenza.",
        "Il codice del processo amministrativo distingue termine breve, termine lungo e riti con termini abbreviati.",
        "dubbio", motivo, onerato="tutte_le_parti", motivo_senza_termine=motivo,
        dubbi=[Dubbio("decorrenza_impugnazione_pat", motivo, "la fonte di decorrenza e il rito del provvedimento", fonte)],
    )]


def conclusioni_sentenza(ctx: Contesto) -> list[Conclusione]:
    from ..atti import priorita_fonte_sentenza

    risultato: list[Conclusione] = []
    visti: set[str] = set()
    for sentenza in sorted((a for a in ctx.della_causa() if a.sentenza), key=priorita_fonte_sentenza):
        if sentenza.id in visti:
            continue
        visti.update([sentenza.id, *sentenza.copie])
        pubblicata = giorno(data_pubblicazione(sentenza.testo))
        fonte = Fonte(sentenza.id, sentenza.nome, pulito(sentenza.testo[:300]), pubblicata.isoformat() if pubblicata else sentenza.data)
        giurisdizione, grado = giurisdizione_e_grado(
            tipo=ctx.fascicolo.get("tipo", ""), ufficio=ctx.ufficio,
            rito=ctx.fascicolo.get("rito", ""), sentenza=sentenza.testo[:500],
        )
        if giurisdizione == AMMINISTRATIVO:
            risultato.extend(_sentenza_amministrativa(sentenza, fonte, grado=grado, ctx=ctx))
            continue
        if (giurisdizione, grado) != (CIVILE, PRIMO):
            continue
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
        lungo = None
        if pubblicata and pubblicata <= ctx.oggi:
            calcolo = ItalianDeadlineCalculator().calculate(
                pubblicata, 6, direction="forward", period_type="months", suspend_august=ctx.rito.sospensione_feriale,
                ferial_suspension_policy="applies" if ctx.rito.sospensione_feriale else "not_applicable", reference_law="art. 327 c.p.c.")
            lungo = esito(giorno(calcolo.get("deadline")), oggi=ctx.oggi, perentorio=True, decorrenza=pubblicata.isoformat(),
                          evento="pubblicazione della sentenza", rito=ctx.rito,
                          computo="sei mesi dalla pubblicazione (art. 327 c.p.c.), con la proroga dell'art. 155 c.p.c.",
                          conseguenze="Il decorso senza impugnazione rileva ai fini del giudicato (art. 324 c.p.c.).")
        invio_storico, data_invio_storico = next(
            (ctx.notifiche_storiche[oid] for oid in (sentenza.id, *sentenza.copie)
             if oid in ctx.notifiche_storiche), ("", ""),
        )
        condanna_pa = ctx.rito.contro_pa and ctx.posizione == "attiva" and condanna_al_pagamento(sentenza.testo)
        if lungo and lungo.scaduto:
            risultato.append(Conclusione(
                "notifica_sentenza", "Notifica ai fini del termine breve", fonte,
                norme("cpc_326", "cpc_327"), "Conservare le ricevute e la relata eventualmente acquisite.",
                "Il termine lungo è già decorso. Una notifica eseguita ora non riapre il termine ordinario.",
                "non_dovuto", "Consegna non attestata dalle fonti disponibili. Riscontro storico consultabile in Comunicazioni.",
                motivo_senza_termine="Il termine lungo già calcolato resta nei riscontri.",
            ))
            if condanna_pa:
                motivo = "Per l’esecuzione occorrono la prova della notificazione del titolo all’amministrazione obbligata e il riscontro dell’adempimento."
                risultato.append(Conclusione(
                    "esecuzione_pa", "Verificare la notifica del titolo e l’adempimento prima del precetto",
                    fonte, norme("dl669_art14", "cpc_475"),
                    "Aprire le ricevute PEC del titolo e i riscontri di incasso o adempimento.",
                    "I 120 giorni decorrono dalla notifica del titolo esecutivo.", "dubbio", motivo,
                    dubbi=[Dubbio("notifica_titolo_da_verificare", motivo, "la prova della notifica del titolo e dello stato dell’adempimento", fonte)],
                ))
        elif candidate or prove or invio_storico:
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
        if lungo:
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
            prudenziale = next((ctx.termini_lunghi_prudenziali[oid] for oid in (sentenza.id, *sentenza.copie)
                                if oid in ctx.termini_lunghi_prudenziali), "")
            motivo = ("Reperire nel registro telematico la data di pubblicazione della sentenza.")
            riferimenti = ("cpc_133", "cpc_327")
            if ctx.rito.codice == "lavoro":
                motivo += " Nel rito del lavoro vale anche il verbale firmato che documenta la lettura del dispositivo e della motivazione."
                riferimenti += ("cpc_429",)
            if prudenziale:
                motivo = f"Agenda: {data_it(prudenziale)} come data prudenziale dalla decisione. {motivo}"
            risultato.append(Conclusione(
                "termine_impugnazione", "Verificare la pubblicazione della sentenza per stabilire il termine lungo",
                fonte, norme(*riferimenti), "verificare la pubblicazione nel registro di cancelleria",
                "dalla pubblicazione decorre il termine lungo per impugnare", "dubbio", motivo,
                onerato="tutte_le_parti",
                motivo_senza_termine="La data ufficiale di deposito è necessaria per il computo.",
                dubbi=[Dubbio("pubblicazione_da_verificare", motivo, "la data ufficiale di pubblicazione della sentenza", fonte)],
            ))
    return risultato


__all__ = ["conclusioni_sentenza", "data_pubblicazione", "termini_lunghi_prudenziali"]
