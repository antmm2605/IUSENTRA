"""Cautelare (sequestro conservativo), opposizione al verbale del codice della strada, disconoscimento di paternità,
chiamato all'eredità nel possesso dei beni."""
from __future__ import annotations

import re

from ..comprensione import Comprensione
from ..fatti import Fatti, data_it, euro
from ..modello import Analisi, Punto, Rif
from ..norme import piano
from .. import procedura as P
from ..termini import data_breve, termine_anni, termine_giorni, termine_mesi
from .strumenti import data_di, date_in, forma, frase, importi_in


# ------------------------------------------------------------------- sequestro conservativo ottenuto
def riconosci_sequestro(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    return 5 if re.search(r"sequestro conservativo|ottenuto il sequestro", t) and re.search(r"accogliment|ottenuto|autorizza", t) else 0


def analizza_sequestro(c: Comprensione, f: Fatti) -> Analisi:
    t = piano(f.testo)
    a = Analisi("sequestro_conservativo", "cautelare", forma=forma(c))
    x = frase(f, r"ordinanza di accoglimento|accoglimento")
    pronuncia = (date_in(x) or [None])[0]
    fuori_udienza = "fuori udienza" in piano(x)
    prestito = (importi_in(frase(f, r"presta")) or [None])[0]
    restituito = (importi_in(frase(f, r"restituisce")) or [0])[0]
    a.rimedio = ("eseguire il sequestro entro trenta giorni dalla pronuncia e iniziare il giudizio di merito entro sessanta "
                 "giorni dalla comunicazione dell'ordinanza")
    a.giudice = "ufficiale giudiziario per l'esecuzione; tribunale per il merito"
    a.inquadramento = [
        Punto("Il provvedimento che autorizza il sequestro perde efficacia se non è eseguito entro trenta giorni dalla pronuncia.",
              [Rif("cpc:675", "trenta giorni dalla pronuncia")]),
        Punto("Se il giudice non ha fissato il termine, la causa di merito deve essere iniziata entro il termine perentorio di "
              "sessanta giorni, che decorre dalla pronuncia se avvenuta in udienza o altrimenti dalla comunicazione; se il "
              "merito non inizia in tempo il provvedimento perde efficacia.",
              [Rif("cpc:669octies", "sessanta giorni"), Rif("cpc:669octies", "dalla sua comunicazione"),
               Rif("cpc:669novies", "perde la sua efficacia")]),
    ]
    if pronuncia:
        ese = termine_giorni(pronuncia, 30, sospensione_feriale=False)
        mer = termine_giorni(pronuncia, 60, sospensione_feriale=False)
        a.termini = [Punto(f"Esecuzione del sequestro entro {data_breve(ese)} (trenta giorni dalla pronuncia"
                           + (", che per l'ordinanza fuori udienza coincide con il deposito" if fuori_udienza else "") + ").",
                           [Rif("cpc:675", "trenta giorni dalla pronuncia")]),
                     Punto(f"Inizio del giudizio di merito entro {data_breve(mer)} (sessanta giorni dalla comunicazione del "
                           f"{data_it(pronuncia)}; non dall'esecuzione).", [Rif("cpc:669octies", "sessanta giorni")])]
        a.avvertenze.append(f"Eseguire «con calma a gennaio» farebbe perdere il sequestro: va eseguito entro il "
                            f"{ese.strftime('%d/%m/%Y')}; e i sessanta giorni per il merito non decorrono dall'esecuzione ma dalla "
                            "comunicazione dell'ordinanza.")
    residuo = (prestito - restituito) if prestito else None
    if residuo:
        a.conclusione = [Punto(f"Credito residuo da far valere nel merito: {euro(prestito)} prestati meno {euro(restituito)} "
                               f"restituiti = {euro(residuo)}.", [Rif("cc:1193", "dichiarare")])]
        a.procedibilita = [Punto("Per la domanda di merito di pagamento di somme non eccedenti 50.000 euro serve l'invito alla "
                                 "negoziazione assistita: va inviato subito, senza ritardare l'inizio del merito; la "
                                 "negoziazione non impedisce i provvedimenti cautelari.",
                                 [Rif("dl132:3", "pagamento a qualsiasi titolo di somme non eccedenti"),
                                  Rif("dl132:3", "provvedimenti urgenti e cautelari")])]
    a.dati_mancanti = ["data esatta di ricezione della PEC di comunicazione dell'ordinanza"]
    return a


# ------------------------------------------------------------------- verbale del codice della strada non contestato
def riconosci_verbale_cds(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    return 5 if re.search(r"autovelox|verbale n\.|multa|codice della strada|rilevamento della velocita", t) and re.search(
        r"ricorso|opposizion|giudice di pace", t) else 0


def analizza_verbale_cds(c: Comprensione, f: Fatti) -> Analisi:
    t = piano(f.testo)
    a = Analisi("opposizione_verbale_cds", "giudice di pace — codice della strada", forma=forma(c))
    accertamento = data_di(f, r"accerta|rilevamento")
    spedizione = data_di(f, r"consegna all ufficio postale|spedit|consegnat\w* (?:all|per la notifica)")
    notifica = data_di(f, r"e notificato|notificat\w* a [a-z]+ [a-z]+ a mezzo")
    comune = (re.search(r"territorio del comune di ([a-z ]+?)(?:,|\.| un )", t) or [None, ""])[1].strip().title()
    sanzione = (importi_in(frase(f, r"sanzione")) or [None])[0]
    a.rimedio = "ricorso in opposizione al verbale di accertamento al giudice di pace (art. 204-bis cod. strada e art. 7 d.lgs. 150/2011)"
    a.giudice = P.ufficio("Giudice di pace", comune) if comune else "giudice di pace del luogo della violazione"
    a.inquadramento = [
        Punto("Se la violazione non è contestata immediatamente, il verbale deve essere notificato entro novanta giorni "
              "dall'accertamento al proprietario risultante dal P.R.A.; altrimenti l'obbligo di pagare si estingue per chi non "
              "ha ricevuto la notificazione nel termine.", [Rif("dlgs285:201", "entro novanta giorni dall'accertamento")]),
        Punto("L'opposizione si propone davanti al giudice di pace del luogo della violazione, con il rito del lavoro, entro "
              "trenta giorni dalla notificazione del verbale, a pena di inammissibilità.",
              [Rif("dlgs150:7", "luogo in cui e' stata commessa la violazione"), Rif("dlgs150:7", "entro trenta giorni"),
               Rif("dlgs150:7", "rito del lavoro"), Rif("dlgs285:204bis", "autorita' giudiziaria ordinaria")]),
    ]
    if accertamento:
        lim = termine_giorni(accertamento, 90, sostanziale=True)
        tardivo = bool(spedizione and spedizione > lim)
        a.termini.append(Punto(f"Accertamento del {data_it(accertamento)}: notificazione entro {data_breve(lim)}; il verbale è "
                               f"stato consegnato per la notifica il {data_it(spedizione)}: " + ("TARDIVO." if tardivo else "in termine."),
                               [Rif("dlgs285:201", "entro novanta giorni dall'accertamento")]))
        if tardivo:
            a.conclusione.append(Punto("Motivo principale: notificazione oltre i novanta giorni, con proprietario identificabile al "
                                       "P.R.A. fin dal giorno dell'accertamento e nessun motivo di ritardo indicato nel verbale: "
                                       "il verbale va annullato" + (f" (sanzione {euro(sanzione)})" if sanzione else "") + ".",
                                       [Rif("dlgs285:201", "entro novanta giorni dall'accertamento")]))
    if notifica:
        ric = termine_giorni(notifica, 30, sospensione_feriale=False)
        a.termini.append(Punto(f"Verbale notificato il {data_breve(notifica)}: ricorso al giudice di pace entro {data_breve(ric)}.",
                               [Rif("dlgs150:7", "entro trenta giorni")]))
    a.avvertenze = ["Non pagare e non proporre ricorso al prefetto: il ricorso al giudice di pace è inammissibile se è stato "
                    "presentato prima ricorso al prefetto."]
    a.dati_mancanti = ["codice fiscale della ricorrente", "copia del verbale e della relata di notifica"]
    if c.tipo == "redazione":
        from ..bozze import ricorso_generico

        a.bozza = ricorso_generico(
            "Ricorso in opposizione a verbale di accertamento (art. 204-bis d.lgs. 285/1992 e art. 7 d.lgs. 150/2011)", a.giudice,
            f, "annullamento del verbale e della sanzione",
            ["Tardività della notificazione: il verbale è stato spedito oltre i novanta giorni dall'accertamento, con "
             "proprietaria identificabile al P.R.A. dal giorno della violazione e senza motivi di ritardo (art. 201 d.lgs. 285/1992).",
             "Tempestività del ricorso: proposto entro trenta giorni dalla notificazione (art. 7 d.lgs. 150/2011)."],
            "annullare il verbale e dichiarare estinta l'obbligazione di pagamento; con vittoria di spese.",
            "verbale, busta e relata di notifica, visura P.R.A.", "art. 7 d.lgs. 150/2011")
    return a


# ------------------------------------------------------------------- disconoscimento di paternità
def riconosci_disconoscimento(c: Comprensione, f: Fatti) -> int:
    return 5 if re.search(r"disconosciment", piano(f.testo)) else 0


def analizza_disconoscimento(c: Comprensione, f: Fatti) -> Analisi:
    t = piano(f.testo)
    a = Analisi("disconoscimento_paternita", "famiglia", modello="FAM_016", forma=forma(c))
    nascita = data_di(f, r"\bnasce\b|nascita")
    conoscenza = data_di(f, r"test genetico|esito|scopre|apprende")
    m_luogo = re.search(r"vive con la madre a ([a-z]+)", t)
    luogo = m_luogo.group(1).title() if m_luogo else ""
    a.rimedio = "ricorso per disconoscimento di paternità (artt. 243-bis e 244 c.c.; art. 473-bis.12 c.p.c.)"
    a.giudice = P.ufficio("Tribunale", luogo) if luogo else "tribunale della residenza abituale del minore"
    a.inquadramento = [
        Punto("L'azione di disconoscimento della paternità del figlio nato nel matrimonio spetta al marito, che può provare "
              "che il figlio non è suo con ogni mezzo.", [Rif("cc:243bis", "disconoscimento")]),
        Punto("Il marito propone l'azione entro un anno dalla nascita; se prova di aver ignorato l'adulterio della moglie al "
              "tempo del concepimento, il termine decorre dal giorno in cui ne ha avuto conoscenza; in ogni caso non oltre cinque "
              "anni dalla nascita.", [Rif("cc:244", "un anno"), Rif("cc:244", "ne ha avuto conoscenza"), Rif("cc:244", "cinque anni")]),
    ]
    a.rito = [Punto("Si procede con ricorso nel rito per le persone, i minorenni e le famiglie; è competente il tribunale del "
                    "luogo di residenza abituale del minore.", [Rif("cpc:473bis12", "si propone con ricorso"),
                                                               Rif("cpc:473bis11", "residenza abituale")])]
    if conoscenza:
        lim = termine_anni(conoscenza, 1)
        a.termini.append(Punto(f"Conoscenza dell'adulterio (prudenzialmente la data del test, {data_it(conoscenza)}): azione "
                               f"entro {data_breve(lim)}.", [Rif("cc:244", "un anno")]))
    if nascita:
        a.termini.append(Punto(f"Limite massimo: cinque anni dalla nascita del {data_it(nascita)}, cioè "
                               f"{data_breve(termine_anni(nascita, 5))}.", [Rif("cc:244", "cinque anni")]))
    a.avvertenze = ["Il figlio minore è parte necessaria: per lui va nominato un curatore speciale."]
    a.dati_mancanti = ["codici fiscali e dati anagrafici completi delle parti e del minore", "copia del test genetico e del messaggio"]
    if c.tipo == "redazione":
        from ..bozze import ricorso_generico

        a.bozza = ricorso_generico(
            "Ricorso per disconoscimento di paternità (artt. 243-bis e 244 c.c.; art. 473-bis.12 c.p.c.)", a.giudice, f,
            "accertamento che il ricorrente non è padre del minore",
            ["Il ricorrente ha ignorato l'adulterio fino all'esito del test genetico: l'azione è tempestiva (art. 244 c.c.).",
             "La prova è data dal test genetico e dall'ammissione scritta della moglie (art. 243-bis c.c.).",
             "Competenza: tribunale della residenza abituale del minore (art. 473-bis.11 c.p.c.); nomina di un curatore speciale."],
            "accertare e dichiarare che il ricorrente non è padre del minore; ordinare le annotazioni allo stato civile; "
            "nominare un curatore speciale del minore.", "atto di nascita, test genetico, messaggio, certificato di residenza.",
            "artt. 473-bis ss. c.p.c.")
    return a


# ------------------------------------------------------------------- chiamato all'eredità nel possesso dei beni
def riconosci_eredita_possesso(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    return 5 if re.search(r"eredit|rinuncia all eredita|chiamat", t) and re.search(r"debiti|rinunci", t) else 0


def analizza_eredita_possesso(c: Comprensione, f: Fatti) -> Analisi:
    t = piano(f.testo)
    a = Analisi("chiamato_nel_possesso", "successioni", forma="parere (consulenza)")
    morte = data_di(f, r"\bmuore\b|deced")
    possesso = bool(re.search(r"conviveva|continua ad abitar|detiene le chiavi|possesso", t))
    inventario = not re.search(r"non ha redatto inventario|senza inventario|nessun inventario", t)
    attivo = sum(importi_in(frase(f, r"attivo ereditario")) or [0])
    debiti = sum(importi_in(frase(f, r"crediti verso la defunta|debiti[^.]{0,40}euro")) or [0])
    a.inquadramento = [
        Punto("Il chiamato che a qualsiasi titolo è nel possesso di beni ereditari deve fare l'inventario entro tre mesi "
              "dall'apertura della successione o dalla notizia; trascorso il termine senza inventario è considerato erede "
              "puro e semplice.", [Rif("cc:485", "tre mesi"), Rif("cc:485", "erede puro e semplice")]),
        Punto("La rinuncia all'eredità si fa con dichiarazione davanti a notaio o al cancelliere, ma non produce effetti per "
              "chi è già erede puro e semplice; il termine decennale per accettare non è più rilevante.",
              [Rif("cc:519", "notaio"), Rif("cc:480", "dieci anni")]),
    ]
    if morte and possesso and not inventario:
        lim = termine_mesi(morte, 3, sostanziale=True)
        a.termini = [Punto(f"Apertura della successione il {data_it(morte)} con il chiamato già nel possesso: inventario entro "
                           f"{data_breve(lim)}, termine scaduto senza inventario.", [Rif("cc:485", "tre mesi")])]
        a.rimedio = ("parere: il chiamato nel possesso è divenuto erede puro e semplice per mancato inventario; la rinuncia "
                     "dal notaio non è più efficace; gestione stragiudiziale dei debiti")
        a.giudice = "nessuno: tutela stragiudiziale verso i creditori"
        a.conclusione = [Punto("Il cliente risponde dei debiti anche oltre l'attivo: va informato per iscritto; si verificano titolo, "
                               "importo e prescrizione dei crediti e si tratta un saldo e stralcio commisurato all'attivo.",
                               [Rif("cc:485", "erede puro e semplice")])]
        a.avvertenze = ["La rinuncia richiesta non produrrebbe effetti: va detto espressamente al cliente."]
    if attivo or debiti:
        a.conclusione.append(Punto(f"Attivo ereditario {euro(attivo)}; debiti comunicati {euro(debiti)}; eccedenza dei debiti "
                                   f"sull'attivo {euro(debiti - attivo)}.", [Rif("cc:485", "erede puro e semplice")]))
    a.dati_mancanti = ["contratti di finanziamento e piani di ammortamento", "eventuali polizze assicurative sui finanziamenti"]
    return a
