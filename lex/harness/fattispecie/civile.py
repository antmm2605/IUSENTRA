"""Fattispecie civili: preliminare e caparra confirmatoria, domande di pagamento, danni da circolazione, comparsa."""
from __future__ import annotations

import re
from datetime import timedelta

from ..comprensione import Comprensione
from ..fatti import Fatti, data_it, euro
from ..modello import Analisi, Punto, Rif
from ..norme import piano
from .. import procedura as P


def _nome(parte, ruolo: str) -> str:
    return parte.nome or f"[{ruolo} da completare]"


# --------------------------------------------------------------------------------------------- caparra e preliminare
def riconosci_caparra(c: Comprensione, f: Fatti) -> int:
    if "caparra" not in piano(f.testo):
        return 0
    return 3 if f.ha("preliminare") or "rogito" in piano(f.testo) else 2


def _diffida(f: Fatti):
    for e in f.eventi:
        t = piano(e.testo)
        if "1454" in t or "diffida" in t:
            giorni = re.search(r"termine di (\d+) giorni", t)
            ricevuta = re.search(r"ricevut\w* il (\d{1,2}/\d{1,2}/\d{4})", t)
            return e, int(giorni.group(1)) if giorni else None, ricevuta.group(1) if ricevuta else ""
    return None, None, ""


def analizza_caparra(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("caparra_confirmatoria", "civile — contratti", modello="CIV_ORD_001",
                forma="atto" if c.tipo == "redazione" else "parere (consulenza)",
                rimedio=("atto di citazione (rito ordinario di cognizione, con valutazione motivata del procedimento "
                         "semplificato) per l'accertamento del legittimo recesso ex art. 1385, comma 2, c.c. e la condanna al "
                         "pagamento del doppio della caparra"))
    caparra = f.importo("caparra")
    prezzo = f.importo("prezzo")
    att, conv = _nome(f.assistita, "parte assistita"), _nome(f.controparte, "controparte")
    acquirente_assistito = "acquirent" in piano(f.assistita.ruolo) or re.search(
        r"(?:mio|mia) client\w*,? (?:il |la )?promissari\w* acquirent|assisto (?:il |la )?promissari\w* acquirent|"
        r"(?:il mio cliente|la mia cliente)[^.]{0,40}promissari\w* acquirent", piano(f.testo)) is not None
    a.capito = [
        f"Parte assistita: {att}{' (' + f.assistita.ruolo + ')' if f.assistita.ruolo else ''}; controparte: {conv}"
        f"{' (' + f.controparte.ruolo + ')' if f.controparte.ruolo else ''}"
        + (f", residente a {f.residenza_convenuto}" if f.residenza_convenuto else "") + ".",
        "Contratto preliminare di compravendita" + (f" di un immobile in {f.luogo_immobile}" if f.luogo_immobile else "")
        + (f", prezzo {euro(prezzo.valore)}" if prezzo else "")
        + (f"; caparra confirmatoria versata {euro(caparra.valore)}" if caparra else "; importo della caparra [da completare]") + ".",
    ]
    for e in f.eventi:
        a.capito.append(e.testo.rstrip(".") + ".")
    if f.ha("no_2932"):
        a.capito.append("Il cliente non vuole l'esecuzione in forma specifica (art. 2932 c.c.): vuole sciogliere il rapporto.")
    a.capito.append("Richiesta: " + ("atto di citazione" if c.tipo == "redazione" else "parere") +
                    " per ottenere il doppio della caparra, con scelta di rito e giudice.")
    if not caparra:
        a.dubbi.append("Manca l'importo della caparra: senza di esso non si calcolano domanda, valore e procedibilità.")
        return a
    doppio = caparra.valore * 2
    a.valore = doppio
    inadempiente_chi_ha_ricevuto = acquirente_assistito
    a.inquadramento = [
        Punto("La somma versata con la qualifica espressa di caparra confirmatoria segue l'art. 1385 c.c.: se inadempiente è "
              "la parte che l'ha ricevuta, l'altra può recedere dal contratto ed esigere il doppio della caparra.",
              [Rif("cc:1385", "esigere il doppio della caparra", "2")]),
        Punto("Recesso e doppio della caparra non richiedono la prova del danno: la caparra ne è la liquidazione "
              "anticipata. Se invece si preferisce chiedere la risoluzione (o l'esecuzione), il risarcimento è regolato "
              "dalle norme generali e va provato; le due strade sono alternative.",
              [Rif("cc:1385", "il risarcimento del danno e regolato dalle norme generali", "3")]),
        Punto("L'inadempimento deve essere imputabile e non di scarsa importanza: qui pesano la mancata comparizione "
              "al rogito fissato (verbale notarile), la diffida rimasta senza risposta e l'offerta dell'immobile a terzi.",
              [Rif("cc:1455", "ha scarsa importanza")]),
    ]
    if re.search(r"rogito fissato entro|stipula entro|entro il \d{1,2}/\d{1,2}/\d{4} presso notaio", piano(f.testo)):
        a.inquadramento.append(Punto(
            "Il termine fissato per il rogito non è qualificato come essenziale nel contratto: non si invoca la risoluzione "
            "per termine essenziale, ma l'inadempimento definitivo dimostrato dalla diffida e dall'offerta a terzi.",
            [Rif("cc:1457", "essenziale nell'interesse dell'altra")]))
    ev, giorni, ricevuta = _diffida(f)
    if ev:
        punto = ("Diffida ad adempiere: il termine non può essere inferiore a quindici giorni; decorso il termine senza "
                 "adempimento il contratto è risoluto di diritto.")
        if giorni and ricevuta:
            from datetime import date as _d
            g, m, y = (int(x) for x in ricevuta.split("/"))
            scadenza = _d(y, m, g) + timedelta(days=giorni)
            punto += (f" Diffida ricevuta il {ricevuta} con termine di {giorni} giorni: termine scaduto il "
                      f"{data_it(scadenza)} senza adempimento.")
        a.inquadramento.append(Punto(punto, [Rif("cc:1454", "essere inferiore a quindici giorni"),
                                             Rif("cc:1454", "risoluto di diritto")]))
        a.dubbi.append("Dopo una diffida ex art. 1454 c.c. rimasta senza esito il contratto è già risolto di diritto: "
                       "prima del deposito va verificato nell'archivio giurisprudenza come la Cassazione tratta la domanda "
                       "del doppio della caparra proposta dopo la risoluzione per diffida (non lo affermo senza una "
                       "pronuncia letta). Per prudenza l'atto propone in via principale il recesso con il doppio e in "
                       "subordine l'accertamento della risoluzione di diritto con la condanna allo stesso importo.")
    a.conclusione = [Punto(
        f"Azione consigliata: domanda di accertamento del legittimo recesso di {att} dal preliminare per inadempimento di "
        f"{conv} e di condanna di {conv} al pagamento di {euro(doppio)} (doppio della caparra di {euro(caparra.valore)}), "
        "oltre interessi legali dalla domanda al saldo, davanti al GIUDICE_COMPETENTE.",
        [Rif("cc:1385", "esigere il doppio della caparra", "2"), Rif("cc:1224", "interessi legali")])]
    if not inadempiente_chi_ha_ricevuto:
        a.dubbi.append("Verifica chi ha versato la caparra e chi è inadempiente: il doppio spetta solo se inadempiente è "
                       "chi l'ha ricevuta; se inadempiente è chi l'ha data, l'altro la trattiene.")
    # Competenza
    a.competenza = P.valore_somma(doppio, interessi_scaduti=False)
    giudice, punti = P.giudice_per_valore(doppio)
    a.competenza += punti
    citta, punti_foro = P.foro_convenuto(f)
    a.competenza += punti_foro
    if giudice:
        a.giudice = P.ufficio(giudice, citta)
    for p in a.conclusione:
        p.testo = p.testo.replace("GIUDICE_COMPETENTE", a.giudice or "giudice competente [da verificare]")
    a.competenza.append(Punto(
        "Se oltre ai € " + f"{doppio:,.0f}".replace(",", ".") + " si chiedessero interessi già maturati prima della domanda "
        "(o danni anteriori), si sommerebbero al capitale: il valore della causa supererebbe € 50.000 e cambierebbe il "
        "quadro della negoziazione assistita (soglia delle somme «non eccedenti»). Chiedendo gli interessi dalla domanda al "
        "saldo il valore resta € 50.000; in ogni caso la soluzione prudente è inviare comunque l'invito alla negoziazione.", [Rif("cpc:10", "gli interessi scaduti, le spese e i danni anteriori alla proposizione si sommano col capitale")]))
    # Procedibilità
    a.procedibilita = P.mediazione_obbligatoria(None)
    a.procedibilita.append(Punto(
        "Dubbio sulla mediazione: la domanda nasce da un preliminare di compravendita immobiliare ma è solo di pagamento "
        "(recesso e doppio della caparra) e non chiede il trasferimento della proprietà (art. 2932 c.c.): non riguarda "
        "«diritti reali», che sono la materia indicata dalla norma. Il dubbio esiste perché il contratto riguarda un "
        "immobile. Soluzione prudente: oltre alla negoziazione assistita, che è obbligatoria, si può depositare anche la "
        "domanda di mediazione; se il giudice ritenesse la materia compresa fra i diritti reali, la mancanza va eccepita o "
        "rilevata entro la prima udienza e il giudice assegna il termine per rimediare.",
        [Rif("dlgs28:5", "diritti reali"), Rif("cc:2932", "sentenza che produca gli effetti del contratto non concluso")]))
    a.procedibilita += P.negoziazione_pagamento(doppio, consumatore=False)
    a.procedibilita.append(Punto(
        "Esclusione per i contratti fra professionisti e consumatori: non applicabile se, come risulta dai fatti, il "
        "promittente venditore vende come privato e non come impresa o professionista.",
        [Rif("dl132:3", "contratti conclusi tra professionisti e consumatori")]))
    a.procedibilita.append(P.improcedibilita_rimedio())
    # Rito
    a.rito = P.rito_ordinario_o_semplificato(documentale=True)
    a.rito.append(Punto(
        "Scelta motivata: la prova è documentale (preliminare, contabile del bonifico, convocazione dal notaio con "
        "ricevuta, verbale di mancata comparizione, diffida con ricevuta, annuncio di vendita): il rito semplificato è "
        "ammissibile e più rapido. L'atto di citazione nel rito ordinario resta preferibile se si prevede che il convenuto "
        "contesti i fatti e serva un'istruzione con testimoni. La bozza che segue è la citazione richiesta.",
        [Rif("cpc:281decies", "fondata su prova documentale")]))
    # Termini
    a.termini = [
        Punto("Tra notificazione della citazione e udienza indicata devono intercorrere termini liberi non minori di "
              "centoventi giorni (centocinquanta se la notificazione si fa all'estero).", [Rif("cpc:163bis", "centoventi giorni")]),
        Punto("L'attore si costituisce entro dieci giorni dalla notificazione; il convenuto almeno settanta giorni prima "
              "dell'udienza; le memorie integrative si depositano almeno quaranta, venti e dieci giorni prima.",
              [Rif("cpc:165", "entro dieci giorni dalla notificazione"), Rif("cpc:166", "settanta giorni prima dell'udienza"),
               Rif("cpc:171ter", "quaranta giorni prima dell'udienza")]),
    ]
    a.termini.append(Punto("Negoziazione assistita: dopo l'invito, la causa si può iniziare se non c'è adesione o c'è "
                           "rifiuto entro trenta giorni dalla ricezione.",
                           [Rif("dl132:3", "entro trenta giorni dalla sua ricezione")]))
    a.cosa_fare = [
        f"Inviare a {conv} (PEC o raccomandata) la dichiarazione di recesso ai sensi dell'art. 1385, comma 2, c.c., con la "
        f"richiesta di pagamento di {euro(doppio)}: fissa la data della mora per gli interessi (il recesso si può "
        "esercitare anche con l'atto introduttivo).",
        f"Inviare l'invito alla convenzione di negoziazione assistita e attendere trenta giorni dalla ricezione "
        "(o il rifiuto o il fallimento della negoziazione).",
        "Raccogliere i documenti da produrre: preliminare (clausola 6), contabile del bonifico, convocazione dal notaio "
        "con ricevuta, verbale di mancata comparizione, diffida con ricevuta, annuncio di vendita a terzi.",
        "Verificare nei registri immobiliari se l'immobile è già stato venduto e valutare una misura cautelare a garanzia "
        "del credito se c'è rischio concreto di dispersione del patrimonio.",
        "Procura alle liti, contributo unificato e notificazione della citazione al convenuto; poi iscrizione a ruolo.",
    ]
    if a.valore:
        cu = _contributo(a.valore)
        if cu:
            a.cosa_fare.append(cu)
    a.dubbi.append("Luogo di conclusione del preliminare [da completare]: serve solo per il foro alternativo dell'art. 20 c.p.c.")
    a.dati_mancanti = ["codice fiscale e PEC del convenuto (pubblici elenchi)", "data di notifica e calendario delle udienze",
                       "procura alle liti"]
    a.avvertenze = ["La data dell'udienza va indicata rispettando i 120 giorni liberi dalla notifica e l'invito a costituirsi "
                    "70 giorni prima, con gli avvertimenti dell'art. 163, comma 3, n. 7, c.p.c.",
                    "Interessi legali sul doppio della caparra dalla domanda al saldo: non quantificati nell'atto."]
    if c.tipo == "redazione":
        from ..bozze import citazione_caparra

        a.bozza = citazione_caparra(f, a, caparra.valore, doppio)
    return a


def _contributo(valore: float) -> str:
    try:
        from pct.strumenti_legali import GestioneStrumentiLegali

        esito = GestioneStrumentiLegali().calcola_contributo_unificato(
            {"cu_categoria": "civile_ordinario", "cu_grado": "primo_grado", "cu_valore": valore})
        totale = esito.get("totale", esito.get("importo", esito.get("contributo")))
        if totale is not None:
            return (f"Contributo unificato per una causa di {euro(valore)} in primo grado: {euro(float(totale))} "
                    "(art. 13 d.P.R. 115/2002, calcolatore di IUSENTRA), più l'anticipazione forfettaria.")
    except Exception:
        return ""
    return ""


# --------------------------------------------------------------------------------------------- pagamento generico
def riconosci_pagamento(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    if not f.importi or f.ha("locazione") or f.ha("lavoro_subordinato") or f.ha("condominio"):
        return 0
    if re.search(r"quale giudice|giudice competente|chi e competente|competen", t):
        return 2
    return 0


def analizza_pagamento(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("competenza_pagamento", "civile — competenza")
    valore = max(i.valore for i in f.importi)
    circ = f.ha("circolazione")
    a.valore = valore
    a.capito = [f"Domanda di {'risarcimento del danno da circolazione' if circ else 'pagamento'} di {euro(valore)}."]
    a.competenza = P.valore_somma(valore)
    giudice, punti = P.giudice_per_valore(valore, circolazione=circ)
    a.competenza += punti
    a.giudice = giudice
    if f.ha("consumatore"):
        a.competenza.append(Punto("Se l'attore è un consumatore e il convenuto un professionista, è inderogabilmente "
                                  "competente il giudice del luogo di residenza o di domicilio del consumatore.",
                                  [Rif("dlgs206:66bis", "residenza o di domicilio del consumatore")]))
    else:
        a.competenza += P.foro_convenuto(f)[1]
    a.procedibilita = []
    if circ:
        a.procedibilita.append(Punto("Negoziazione assistita obbligatoria per la domanda di risarcimento del danno da "
                                     "circolazione di veicoli e natanti, qualunque sia il valore.",
                                     [Rif("dl132:3", "circolazione di veicoli e natanti")]))
    else:
        a.procedibilita += P.negoziazione_pagamento(valore, consumatore=f.ha("consumatore") and f.ha("professionista_impresa"))
    a.conclusione = [Punto(f"Giudice competente: {giudice or '[da verificare]'}" + (
        f", per una domanda di {euro(valore)}." if giudice else "."), punti[0].rif if punti else [])]
    return a


# --------------------------------------------------------------------------------------------- comparsa di risposta
def riconosci_comparsa(c: Comprensione, f: Fatti) -> int:
    return 3 if c.atto == "comparsa di costituzione e risposta" else 0


def analizza_comparsa(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("comparsa_risposta", "civile — difesa del convenuto", modello="CIV_ORD_009")
    a.capito = ["Difesa del convenuto in una causa ordinaria di cognizione: comparsa di costituzione e risposta."]
    a.inquadramento = [
        Punto("Il convenuto si costituisce almeno settanta giorni prima dell'udienza di comparizione depositando la "
              "comparsa.", [Rif("cpc:166", "settanta giorni prima dell'udienza")]),
        Punto("Nella comparsa vanno proposte, a pena di decadenza, le domande riconvenzionali e le eccezioni processuali e "
              "di merito non rilevabili d'ufficio; va dichiarata l'eventuale chiamata del terzo.",
              [Rif("cpc:167", "a pena di decadenza")]),
        Punto("Seguono le memorie integrative almeno quaranta, venti e dieci giorni prima dell'udienza.",
              [Rif("cpc:171ter", "quaranta giorni prima dell'udienza")]),
    ]
    a.conclusione = [Punto("Termine decisivo: costituzione almeno settanta giorni prima dell'udienza indicata nella "
                           "citazione; oltre quel termine si decade da riconvenzionali, chiamata del terzo ed eccezioni "
                           "non rilevabili d'ufficio.", [Rif("cpc:166", "settanta giorni prima dell'udienza"),
                                                         Rif("cpc:167", "a pena di decadenza")])]
    a.cosa_fare = ["Calcolare la data di costituzione dall'udienza indicata nella citazione (70 giorni a ritroso).",
                   "Verificare competenza e condizioni di procedibilità: le eccezioni vanno sollevate nella comparsa tempestiva.",
                   "Raccogliere procura e documenti; preparare le prove per la memoria integrativa n. 2."]
    if c.tipo == "redazione":
        from ..bozze import comparsa_generica

        a.bozza = comparsa_generica(f)
    return a
