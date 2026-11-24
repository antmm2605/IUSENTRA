"""Cautelare (sequestro conservativo), opposizione al verbale del codice della strada, disconoscimento di paternità,
chiamato all'eredità nel possesso dei beni."""
from __future__ import annotations

import re

from ..comprensione import Comprensione
from ..fatti import Fatti, data_it, euro
from ..modello import Analisi, Punto, Rif
from ..norme import piano
from .. import procedura as P
from ..termini import data_breve, termine, termine_anni, termine_giorni, termine_mesi, tocca_agosto
from .strumenti import data_di, data_dopo, date_in, forma, frase, importi_in


# ------------------------------------------------------------------- sequestro conservativo ottenuto
def riconosci_sequestro(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    return 5 if re.search(r"sequestro conservativo|ottenuto il sequestro", t) and re.search(r"accogliment|ottenuto|autorizza", t) else 0


def analizza_sequestro(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("sequestro_conservativo", "cautelare", modello="CAU_005", forma=forma(c))
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
        ese = termine("LEX_CAU_ESECUZIONE_675", pronuncia)
        mer = termine("CIV_MERITO_669_OCTIES", pronuncia)
        if tocca_agosto(pronuncia, mer):
            a.dubbi.append("Il termine per il merito attraversa agosto: l'applicazione della sospensione feriale al termine "
                           "dell'art. 669-octies va verificata sulla giurisprudenza prima di contare su giorni in più.")
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
        a.procedibilita = [Punto(f"Per la domanda di merito di pagamento di somme non eccedenti {euro(P.soglia_negoziazione() or 0)} serve l'invito alla "
                                 "negoziazione assistita: va inviato subito, senza ritardare l'inizio del merito; la "
                                 "negoziazione non impedisce i provvedimenti cautelari.",
                                 [Rif("dl132:3", "pagamento a qualsiasi titolo di somme non eccedenti"),
                                  Rif("dl132:3", "provvedimenti urgenti e cautelari")])]
    a.dati_mancanti = ["data esatta di ricezione della PEC di comunicazione dell'ordinanza"]
    return a


# ------------------------------------------------------------------- verbale del codice della strada non contestato
def riconosci_verbale_cds(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    if re.search(r"ricorso al prefetto|ricorrere al prefetto|al prefetto", t) and not re.search(r"giudice di pace|opposizion|meglio|oppure|o il", t):
        return 0
    return 5 if re.search(r"autovelox|verbale n\.|multa|codice della strada|rilevamento della velocita|eccesso di velocita|"
                          r"limite di velocita|semaforo rosso|divieto di sosta|\bztl\b|infrazione stradal|verbale (?:di|per) "
                          r"(?:contestazione|violazione|eccesso|sosta|accertamento)", t) and re.search(
        r"ricorso|opposizion|giudice di pace", t) else 0


def analizza_verbale_cds(c: Comprensione, f: Fatti) -> Analisi:
    t = piano(f.testo)
    a = Analisi("opposizione_verbale_cds", "giudice di pace — codice della strada", modello="GDP_004", forma=forma(c))
    accertamento = data_di(f, r"accerta|rilevamento")
    spedizione = data_di(f, r"consegna all ufficio postale|spedit|consegnat\w* (?:all|per la notifica)")
    notifica = (data_dopo(f, r"(?:verbale |e )notificat\w*(?: a [a-z]+ [a-z]+)?(?: a mezzo [a-z]+)?(?: il)?")
                or data_di(f, r"e notificato|notificat\w* a [a-z]+ [a-z]+ a mezzo", ultima=True))
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
        ric = termine("CDS_RICORSO_GDP_30GG", notifica)
        a.termini.append(Punto(f"Verbale notificato il {data_breve(notifica)}: ricorso al giudice di pace entro {data_breve(ric)} "
                               "(termine processuale: sospensione feriale e proroga del sabato e dei festivi).",
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
    a.inquadramento.append(Punto(
        "In alternativa al giudice di pace, se non si è pagato in misura ridotta, si può proporre ricorso al prefetto del luogo "
        "della violazione entro sessanta giorni dalla contestazione o dalla notificazione, presentandolo all'organo accertatore "
        "o inviandolo con raccomandata o PEC. Le due strade sono alternative: scelta l'una, l'altra non è più percorribile per "
        "lo stesso verbale.",
        [Rif("dlgs285:203", "nel termine di giorni sessanta dalla contestazione o dalla notificazione"),
         Rif("dlgs285:203", "possono proporre ricorso al prefetto del luogo della commessa violazione")]))
    if re.search(r"prefett", t):
        a.rimedio += "; in alternativa, ricorso al prefetto entro sessanta giorni (art. 203 cod. strada)"
    return a


# ------------------------------------------------------------------- disconoscimento di paternità
def riconosci_disconoscimento(c: Comprensione, f: Fatti) -> int:
    return 5 if re.search(r"disconosciment", piano(f.testo)) else 0


def analizza_disconoscimento(c: Comprensione, f: Fatti) -> Analisi:
    t = piano(f.testo)
    a = Analisi("disconoscimento_paternita", "famiglia", forma=forma(c))
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
    m_figlio = re.search(r"(?:il|la) figli[oa] ([A-ZÀ-Ý][a-zà-ÿ]+)", f.testo)
    figlio = m_figlio.group(1) if m_figlio else ""
    a.inquadramento.append(Punto(
        "Il presunto padre, la madre e il figlio sono litisconsorti necessari; se una parte è minore, l'azione si propone in "
        "contraddittorio con un curatore nominato dal giudice.",
        [Rif("cc:247", "litisconsorti necessari"), Rif("cc:247", "curatore nominato dal giudice")]))
    a.avvertenze = [f"Il figlio minore{(' ' + figlio) if figlio else ''} è litisconsorte necessario: il ricorso va proposto anche "
                    "nei suoi confronti, con la richiesta di nomina di un curatore speciale (art. 247 c.c.)."]
    a.dati_mancanti = ["codici fiscali e dati anagrafici completi delle parti e del minore", "copia del test genetico e del messaggio"]
    if c.tipo == "redazione":
        from ..bozze import DA, ricorso_generico

        a.bozza = ricorso_generico(
            "Ricorso per disconoscimento di paternità (artt. 243-bis e 244 c.c.; art. 473-bis.12 c.p.c.)", a.giudice, f,
            "accertamento che il ricorrente non è padre del minore",
            ["Il ricorrente ha ignorato l'adulterio fino all'esito del test genetico: l'azione è tempestiva (art. 244 c.c.).",
             "La prova è data dal test genetico e dall'ammissione scritta della moglie (art. 243-bis c.c.).",
             "Competenza: tribunale della residenza abituale del minore (art. 473-bis.11 c.p.c.); nomina di un curatore speciale."],
            "accertare e dichiarare che il ricorrente non è padre del minore; ordinare le annotazioni allo stato civile; "
            "nominare un curatore speciale del minore.", "atto di nascita, test genetico, messaggio, certificato di residenza.",
            "artt. 473-bis ss. c.p.c.; art. 247 c.c.",
            altre_parti=[f"{figlio or 'il figlio minore'}, minore, nato il {data_it(nascita) if nascita else DA}, rappresentato da "
                         "un curatore speciale da nominare (art. 247 c.c.) – litisconsorte necessario –"])
    return a


# ------------------------------------------------------------------- chiamato all'eredità nel possesso dei beni
def riconosci_eredita_possesso(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    if not (re.search(r"eredit|rinuncia all eredita|chiamat", t) and re.search(r"debiti|rinunci", t)):
        return 0
    # La regola è quella del chiamato nel possesso dei beni (art. 485 c.c.): senza possesso rispondono rinuncia e beneficio
    # d'inventario.
    return 5 if re.search(r"possess|\bchiamat|abit\w* (?:nella|la) casa|vive nella casa|ha le chiavi|chiavi|"
                          r"usat[oa] (?:il|la|i|le)|conto (?:del|corrente del) defunt|gestisc|incassat|ritirat|preso (?:i|il|la)", t) else 0


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


# ------------------------------------------------------------------- sequestro conservativo da chiedere prima della causa
_SEQ_CHIESTO = (r"sequestr|blocc\w* (?:\w+ ){0,3}(?:beni|conto|conti|immobil|somme|casa|quot|appartament|auto)|congel\w* "
                r"(?:\w+ ){0,3}(?:beni|conto|conti|somme)|mettere al sicuro (?:il|la nostra|il nostro) credit")
_PERICOLO = (r"vend|alien|svuot|dissip|trasferi|intest|cede|cessione|donaz|don\w+ (?:la|il|i|le) |fondo patrimonial|trust|"
             r"espatri|trasferirsi all estero|garanzia del (?:suo |mio |nostro )?credito|prelev|sottrar|disfa|liquidando|"
             r"chiudendo (?:i|il) cont|svend")
_SEQ_ALTRO = (r"ordinanza|ottenuto il sequestro|accolto|accoglimento|concesso il sequestro|autorizzato il sequestro|sequestro "
              r"(?:penale|preventivo|probatorio|giudiziario)|gia (?:eseguito|disposto)")


def riconosci_sequestro_ante_causam(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    if re.search(_SEQ_ALTRO, t) or not re.search(_SEQ_CHIESTO, t) or not re.search(_PERICOLO, t):
        return 0
    return 6 if f.importi or re.search(r"credit|debit|prestit|fattur|ci deve|gli deve|le deve|mi deve", t) else 0


def analizza_sequestro_ante_causam(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("sequestro_ante_causam", "cautelare", modello="CAU_005", forma=forma(c))
    t = piano(f.testo)
    valore = max((i.valore for i in f.importi), default=None)
    a.valore = valore
    pericolo = frase(f, _PERICOLO)
    a.capito = ["Credito" + (f" di {euro(valore)}" if valore else " [importo da completare]") + " da tutelare prima della "
                "causa di merito con il sequestro conservativo dei beni del debitore."]
    if pericolo:
        a.capito.append("Pericolo indicato: " + pericolo.strip().rstrip(".") + ".")
    a.rimedio = ("ricorso per sequestro conservativo ante causam al giudice competente per il merito; poi esecuzione entro "
                 "trenta giorni e inizio del merito nel termine perentorio")
    a.inquadramento = [
        Punto("Il sequestro conservativo può essere autorizzato su istanza del creditore che ha fondato timore di perdere la "
              "garanzia del proprio credito, su beni mobili o immobili del debitore o su somme e cose a lui dovute, nei limiti "
              "in cui la legge ne permette il pignoramento.",
              [Rif("cpc:671", "fondato timore di perdere la garanzia del proprio credito"),
               Rif("cpc:671", "nei limiti in cui la legge ne permette il pignoramento")]),
        Punto("Occorrono quindi due requisiti da provare nel ricorso: la probabile esistenza del credito (fumus boni iuris) "
              "e il fondato timore di perderne la garanzia (periculum in mora), da dimostrare con fatti concreti come "
              "vendite, donazioni o svuotamento dei conti, non con il solo inadempimento.",
              [Rif("cpc:671", "fondato timore di perdere la garanzia del proprio credito")]),
    ]
    a.rito = [Punto("La domanda cautelare si propone con ricorso.", [Rif("cpc:669bis", "La domanda si propone con ricorso")])]
    a.competenza = [Punto("Prima dell'inizio della causa di merito, la domanda si propone al giudice competente a conoscere "
                          "del merito.", [Rif("cpc:669ter", "Prima dell'inizio della causa di merito la domanda si propone "
                                                            "al giudice competente a conoscere del merito")])]
    giudice = "Tribunale"
    if valore:
        merito, punti = P.giudice_per_valore(valore)
        a.competenza += punti
        if merito == "Giudice di pace":
            a.competenza.append(Punto(
                "Se il merito spetta al giudice di pace, la domanda cautelare va comunque al tribunale: l'art. 669-ter, "
                "comma 2, c.p.c. lo dice con riferimento al conciliatore, l'ufficio poi sostituito dal giudice di pace.",
                [Rif("cpc:669ter", "Se competente per la causa di merito e' il conciliatore, la domanda si propone al tribunale")]))
    citta, punti_foro = P.foro_convenuto(f)
    a.competenza += punti_foro
    a.giudice = P.ufficio(giudice, citta) if citta else "Tribunale competente per territorio sul merito"
    a.procedibilita = [Punto("Mediazione e negoziazione assistita, anche dove sono condizioni di procedibilità del merito, non "
                             "impediscono di chiedere e ottenere subito i provvedimenti cautelari.",
                             [Rif("dlgs28:5", "non preclude in ogni caso la concessione dei provvedimenti urgenti e cautelari"),
                              Rif("dl132:3", "non preclude la concessione di provvedimenti urgenti e cautelari")])]
    a.termini = [
        Punto("Il provvedimento che autorizza il sequestro perde efficacia se non è eseguito entro trenta giorni dalla pronuncia.",
              [Rif("cpc:675", "trenta giorni dalla pronuncia")]),
        Punto("Se il sequestro è concesso prima della causa, l'ordinanza fissa un termine perentorio non superiore a sessanta "
              "giorni per iniziare il merito; se non lo fissa, il merito va iniziato entro sessanta giorni, che decorrono dalla "
              "pronuncia in udienza o altrimenti dalla comunicazione. Se il merito non inizia in tempo il sequestro perde "
              "efficacia.",
              [Rif("cpc:669octies", "termine perentorio non superiore a sessanta giorni"),
               Rif("cpc:669octies", "dalla sua comunicazione"), Rif("cpc:669novies", "perde la sua efficacia")]),
    ]
    a.conclusione = [Punto(f"Ricorso per sequestro conservativo ante causam al {a.giudice}"
                           + (f" a tutela del credito di {euro(valore)}" if valore else "")
                           + ", con la prova del credito e dei fatti che fanno temere la perdita della garanzia; ottenuto il "
                           "provvedimento, eseguirlo entro trenta giorni e iniziare il merito entro il termine fissato o, in "
                           "mancanza, entro sessanta giorni.",
                           [Rif("cpc:671", "fondato timore di perdere la garanzia del proprio credito"),
                            Rif("cpc:669ter", "giudice competente a conoscere del merito"),
                            Rif("cpc:675", "trenta giorni dalla pronuncia"), Rif("cpc:669octies", "sessanta giorni")])]
    a.cosa_fare = ["Raccogliere la prova scritta del credito (contratto, fatture, riconoscimenti di debito).",
                   "Documentare il pericolo: visure, atti di vendita o donazione, annunci, estratti dei conti.",
                   "Indicare i beni da sequestrare e il loro valore, entro l'importo del credito.",
                   "Preparare subito l'atto di merito, e se serve l'invito alla negoziazione o la mediazione, per non "
                   "perdere il termine di sessanta giorni."]
    if not re.search(r"immobil|conto|cont[io] corrent|auto|quot|stipendi|beni", t):
        a.dati_mancanti.append("beni del debitore da sottoporre a sequestro")
    if not citta:
        a.dati_mancanti.append("residenza o sede del debitore (competenza per territorio)")
    if c.tipo == "redazione":
        from ..bozze import ricorso_generico

        a.bozza = ricorso_generico(
            "Ricorso per sequestro conservativo ante causam (artt. 669-bis, 669-ter e 671 c.p.c.)", a.giudice, f,
            "autorizzazione al sequestro conservativo dei beni del debitore",
            ["Credito del ricorrente: " + (euro(valore) if valore else "[da completare]") + ", fondato su [titolo da completare].",
             "Fondato timore di perdere la garanzia del credito: " + (pericolo.strip() if pericolo else "[fatti da completare]") + ".",
             "Beni da sottoporre a sequestro: [da completare], nei limiti in cui la legge ne permette il pignoramento."],
            "autorizzare il sequestro conservativo dei beni mobili e immobili del resistente e delle somme e cose a lui "
            "dovute fino alla concorrenza di " + (euro(valore) if valore else "[importo]") + ", fissando il termine per "
            "l'inizio del giudizio di merito; con vittoria di spese.", "titolo del credito, documenti sul pericolo.",
            "artt. 669-bis, 669-ter, 669-octies e 671 c.p.c.")
    return a
