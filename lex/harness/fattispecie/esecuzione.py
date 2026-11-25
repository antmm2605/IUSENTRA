"""Esecuzione forzata: opposizione a precetto, termini del precetto, pagamento parziale, precetto inefficace."""
from __future__ import annotations

import re

from ..comprensione import Comprensione
from ..fatti import Fatti, data_it, euro
from ..modello import Analisi, Punto, Rif
from ..norme import piano
from .. import procedura as P
from ..termini import data_breve, termine
from .strumenti import data_di, data_dopo, forma, importi_in, frase


def _precetto_notificato(f: Fatti):
    return (data_dopo(f, r"precetto (?:notificat\w*|e stato notificat\w*)") or data_di(f, r"precett\w*.{0,80}notificat")
            or data_dopo(f, r"notificat\w* (?:il )?(?:precetto|titolo e precetto)") or data_di(f, r"notific\w*.{0,90}precett"))


# ------------------------------------------------------------------------------------------ opposizione a precetto
def riconosci_opposizione_precetto(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    # La posizione della parte assistita decide: il creditore procedente non si oppone al proprio precetto.
    ruolo = piano(f.assistita.ruolo)
    if re.search(r"creditor|procedent|intimant", ruolo):
        return 0
    if "precett" not in t:
        return 0
    contesta = re.search(r"opposizion|oppor|saldat|pagat\w* (?:tutto|integralmente)|gia (?:stato )?pagat|quietanz|transazion|transattiv|non (?:e|era) dovut|"
                         r"prescritt|estint|contest", t)
    # Il debitore che ha ricevuto il precetto e chiede come reagire («ci hanno notificato», «mi è arrivato»).
    destinatario = re.search(r"(?:ci|mi|gli|le) (?:hanno|ha) notificat|(?:ci|mi|gli|le) (?:e|sono) arrivat|abbiamo ricevuto|ho ricevuto|"
                             r"ha ricevuto|ricevuto un precetto", t)
    return 4 if contesta and (c.atto == "opposizione a precetto" or destinatario
                              or re.search(r"\bopponente\b|\bopposto\b|debitor\w* (?:intimat|esecutat)", t)
                              or re.search(r"debitor|intimat|opponent|esecutat", ruolo)) else 0


def analizza_opposizione_precetto(c: Comprensione, f: Fatti) -> Analisi:
    t = piano(f.testo)
    a = Analisi("opposizione_precetto", "esecuzione", modello="ESE_019", forma=forma(c))
    notifica = _precetto_notificato(f)
    m = re.search(r"totale indicato nel precetto[^0-9]{0,20}([\d.]+(?:,\d+)?)\s*euro", t)
    valore = float(m.group(1).replace(".", "").replace(",", ".")) if m else None
    pagato = sum(importi_in(frase(f, r"bonific")) or [0]) or None
    pignoramento_eseguito = not re.search(r"nessun pignoramento|non (?:e stato )?eseguit\w* (?:alcun )?pignoramento", t)
    citta = f.residenza_convenuto or (re.search(r"residenza dell opponente\s*:?\s*([a-z]+)", t) or [None, ""])[1].title()
    a.capito = [f"Precetto notificato il {data_it(notifica)} a {f.assistita.nome or '[debitore]'} da "
                f"{f.controparte.nome or '[creditore]'}" + (f" per {euro(valore)}" if valore else "") +
                "; il debito risulta estinto per transazione e pagamenti quietanzati" +
                ("; nessun pignoramento eseguito." if not pignoramento_eseguito else ".")]
    a.rimedio = ("atto di citazione in opposizione a precetto (art. 615, comma 1, c.p.c.) con istanza di sospensione "
                 "dell'efficacia esecutiva del titolo per gravi motivi")
    giudice, punti = P.giudice_per_valore(valore) if valore else ("", [])
    a.giudice = P.ufficio(giudice, citta) if giudice else "giudice del luogo dell'esecuzione"
    a.inquadramento = [
        Punto("Quando si contesta il diritto di procedere a esecuzione forzata e l'esecuzione non è ancora iniziata, si "
              "propone opposizione al precetto con citazione davanti al giudice competente per materia o valore e per "
              "territorio; concorrendo gravi motivi il giudice sospende su istanza di parte l'efficacia esecutiva del titolo.",
              [Rif("cpc:615", "non e ancora iniziata"), Rif("cpc:615", "gravi motivi")]),
        Punto("Il diritto di procedere è contestato per fatti estintivi successivi al titolo: la transazione, con cui le "
              "parti con reciproche concessioni prevengono o pongono fine a una lite, e il pagamento integrale, provato dalla "
              "quietanza rilasciata dal creditore.", [Rif("cc:1965", "reciproche concessioni"), Rif("cc:1199", "quietanza")]),
        Punto("Se il creditore ha agito senza la normale prudenza si può chiedere la condanna per responsabilità aggravata.",
              [Rif("cpc:96", "normale prudenza")]),
    ]
    a.competenza = punti + [Punto("Per le opposizioni all'esecuzione è competente per territorio il giudice del luogo "
                                  "dell'esecuzione" + (f" ({citta})" if citta else "") + ".",
                                  [Rif("cpc:27", "luogo dell'esecuzione")])]
    a.procedibilita = [Punto("Né negoziazione assistita né mediazione: la negoziazione obbligatoria non si applica «nei "
                             "procedimenti di opposizione o incidentali di cognizione relativi all'esecuzione forzata» (art. 3, "
                             "comma 3, lett. c), d.l. 132/2014) e lo stesso esclude la mediazione obbligatoria (art. 5, comma 6, "
                             "lett. e), d.lgs. 28/2010).",
                             [Rif("dl132:3", "procedimenti di opposizione o incidentali di cognizione relativi all'esecuzione forzata", "3"),
                              Rif("dlgs28:5", "procedimenti di opposizione o incidentali di cognizione relativi all'esecuzione forzata", "6")])]
    a.rito = [Punto("Opposizione all'esecuzione proposta prima dell'inizio dell'esecuzione: atto di citazione con i requisiti "
                    "dell'art. 163 c.p.c.", [Rif("cpc:615", "con citazione"), Rif("cpc:163", "citazione a comparire a udienza fissa")])]
    if notifica:
        dieci = termine("ESE_PRECETTO_ADEMPIMENTO_10GG", notifica)
        a.termini = [Punto(f"Precetto notificato il {data_breve(notifica)}: il termine per adempiere di dieci giorni scade "
                           f"{data_breve(dieci)}; da quel momento il creditore può iniziare l'esecuzione.",
                           [Rif("cpc:480", "termine non minore di dieci giorni"), Rif("cpc:482", "dieci giorni dalla notificazione")])]
        if dieci <= f.oggi:
            a.avvertenze.append(f"Il termine del precetto scade il {data_it(dieci)} (oggi {data_it(f.oggi)}): da subito il "
                                "creditore può pignorare, quindi opposizione e istanza di sospensione vanno depositate con urgenza.")
    a.termini.append(Punto("L'opposizione all'esecuzione non è soggetta al termine di venti giorni previsto per l'opposizione "
                           "agli atti esecutivi, che riguarda solo la regolarità formale di titolo e precetto.",
                           [Rif("cpc:617", "venti giorni")]))
    a.avvertenze.append("Se nel frattempo viene eseguito il pignoramento, l'opposizione si propone con ricorso al giudice "
                        "dell'esecuzione (art. 615, comma 2, c.p.c.) e la sospensione si chiede ai sensi dell'art. 624 c.p.c.")
    a.conclusione = [Punto(f"Citazione in opposizione a precetto davanti al {a.giudice}, con istanza di sospensione "
                           "dell'efficacia esecutiva del titolo per gravi motivi (prova documentale piena dell'estinzione e "
                           "imminenza dell'esecuzione); nel merito accertare che il creditore non ha diritto di procedere"
                           + (f" (pagati {euro(pagato)} in esecuzione della transazione)" if pagato else "") + ".",
                           [Rif("cpc:615", "gravi motivi"), Rif("cpc:27", "luogo dell'esecuzione")])]
    a.dati_mancanti = ["poteri del procuratore speciale che ha firmato la quietanza (quietanza e transazione)",
                       "codice fiscale e PEC del creditore opposto"]
    if c.tipo == "redazione":
        from ..bozze import ricorso_generico

        a.bozza = ricorso_generico(
            "Atto di citazione in opposizione a precetto (art. 615, comma 1, c.p.c.) con istanza di sospensione", a.giudice, f,
            "accertamento dell'insussistenza del diritto di procedere a esecuzione forzata e sospensione dell'efficacia esecutiva",
            ["Il credito portato dal titolo è estinto per la transazione e per il pagamento integrale quietanzato "
             "(artt. 1965 e 1199 c.c.).", "Gravi motivi per la sospensione: prova documentale piena dell'estinzione e "
             "imminenza del pignoramento, perché il termine del precetto è scaduto (art. 615, comma 1, c.p.c.).",
             "Responsabilità aggravata del creditore che minaccia l'esecuzione senza la normale prudenza (art. 96 c.p.c.)."],
            "in via cautelare, sospendere l'efficacia esecutiva del titolo; nel merito, accertare che l'opposta non ha diritto "
            "di procedere a esecuzione forzata e dichiarare privo di effetti il precetto; condannare l'opposta alle spese e "
            "ai sensi dell'art. 96 c.p.c.", "titolo, precetto, accordo transattivo, contabili dei bonifici, quietanza.",
            "artt. 615, 27 e 163 c.p.c.")
    return a


# ------------------------------------------------------------------------------------------ termini del precetto
def riconosci_termini_precetto(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    if "precett" not in t or riconosci_opposizione_precetto(c, f):
        return 0
    return 4 if re.search(r"pignor|valido|efficac|paga solo|pagamento parziale|acconto|notificat", t) else 3


def analizza_termini_precetto(c: Comprensione, f: Fatti) -> Analisi:
    t = piano(f.testo)
    a = Analisi("precetto", "esecuzione", modello="ESE_001", forma=forma(c))
    notifica = _precetto_notificato(f)
    m = re.search(r"precett\w*[^.]{0,80}?per\s+(?:euro\s*)?([\d.]+(?:,\d+)?)", t)
    intimato = float(m.group(1).replace(".", "").replace(",", ".")) if m else None
    x = frase(f, r"bonific|vers\w* \d|acconto|pagat\w* \d")
    pagato = importi_in(x)[0] if importi_in(x) else None
    nessun_pignoramento = re.search(r"non e stato notificato alcun atto di pignoramento|nessun pignoramento|"
                                    r"non (?:e stato )?(?:ancora )?eseguit", t) is not None
    a.inquadramento = [
        Punto("Il precetto è l'intimazione di adempiere entro un termine non minore di dieci giorni; non si può iniziare "
              "l'esecuzione prima che sia decorso il termine indicato nel precetto, salvo autorizzazione all'esecuzione "
              "immediata per pericolo nel ritardo.", [Rif("cpc:480", "termine non minore di dieci giorni"),
                                                      Rif("cpc:482", "pericolo nel ritardo")]),
        Punto("Il precetto diventa inefficace se entro novanta giorni dalla notificazione non è iniziata l'esecuzione; "
              "l'esecuzione inizia con il pignoramento.", [Rif("cpc:481", "novanta giorni")]),
    ]
    if notifica:
        dieci = termine("ESE_PRECETTO_ADEMPIMENTO_10GG", notifica)
        novanta = termine("ESE_PRECETTO_EFFICACIA_90GG", notifica)
        a.termini = [
            Punto(f"Precetto notificato il {data_breve(notifica)}: il termine dilatorio di dieci giorni scade "
                  f"{data_breve(dieci)}; si può pignorare dal giorno successivo.", [Rif("cpc:482", "dieci giorni dalla notificazione")]),
            Punto(f"Il pignoramento va eseguito entro {data_breve(novanta)} (novanta giorni dalla notificazione), a pena di "
                  "inefficacia del precetto.", [Rif("cpc:481", "novanta giorni")]),
        ]
        if novanta < f.oggi and nessun_pignoramento:
            a.rimedio = "rinnovare il precetto (notificarne uno nuovo) e poi procedere al pignoramento"
            a.avvertenze.append(f"Il precetto notificato il {data_it(notifica)} è divenuto inefficace il {data_it(novanta)}: "
                                f"oggi ({data_it(f.oggi)}) non si può pignorare in forza di esso. Occorre notificare un "
                                "nuovo precetto per il residuo e attendere il nuovo termine di dieci giorni.")
            a.conclusione = [Punto("Precetto inefficace: va rinnovato prima di qualunque pignoramento; il nuovo precetto "
                                   "va limitato al residuo effettivamente dovuto.", [Rif("cpc:481", "novanta giorni")])]
        else:
            a.rimedio = ("pignoramento (presso terzi del conto corrente, dei beni mobili registrati) in forza del titolo e del "
                         "precetto già notificati, per il residuo")
            a.conclusione = [Punto(f"Si può pignorare dal giorno successivo al {data_it(dieci)} e fino al {data_it(novanta)}.",
                                   [Rif("cpc:482", "dieci giorni dalla notificazione"), Rif("cpc:481", "novanta giorni")])]
    if pagato and intimato:
        a.inquadramento.append(Punto(
            "Il pagamento parziale non invalida il precetto ma riduce il credito: senza il consenso del creditore il "
            "debitore non può imputarlo al capitale anziché a interessi e spese, e il pagamento in conto di capitale e "
            "interessi va imputato prima agli interessi.", [Rif("cc:1194", "senza il consenso del creditore")]))
        a.conclusione.append(Punto(f"Residuo da recuperare: {euro(intimato)} intimati meno {euro(pagato)} pagati = "
                                   f"{euro(intimato - pagato)}, oltre gli interessi successivi e le spese di esecuzione.",
                                   [Rif("cc:1194", "prima agli interessi")]))
        a.avvertenze.append("Il pagamento parziale va dichiarato negli atti esecutivi, per evitare un'opposizione "
                            "all'esecuzione sulla parte già pagata (art. 615 c.p.c.).")
    if re.search(r"accetta il pagamento e l imputazione|accetta\w* l imputazione", t):
        a.inquadramento.append(Punto("L'imputazione indicata dal debitore e accettata dal creditore vincola le parti: il "
                                     "pagamento si imputa come dichiarato.", [Rif("cc:1193", "dichiarare")]))
        mcap = re.search(r"(?:euro\s*)?([\d.]+)\s*(?:euro\s*)?a titolo di capitale", t)
        macc = re.search(r"euro\s*([\d.]+)\s*acconto capitale", t)
        if mcap and macc:
            residuo = float(mcap.group(1).replace(".", "")) - float(macc.group(1).replace(".", ""))
            a.conclusione.append(Punto(f"Residuo capitale per il nuovo precetto: {euro(residuo)}, oltre interessi; le spese "
                                       "di lite pagate non vanno più intimate.", [Rif("cc:1193", "dichiarare")]))
            a.avvertenze.append("Il nuovo precetto non va fatto per l'intero importo originario: intimare somme già pagate "
                                "espone a opposizione e a condanna alle spese.")
    if re.search(r"conto corrente|banca", t):
        a.cosa_fare.append("Pignoramento presso terzi del conto corrente, con atto notificato al terzo e al debitore (art. 543 c.p.c.).")
    if re.search(r"autovettura|autoveicol|automobile", t):
        a.cosa_fare.append("Pignoramento dell'autovettura nelle forme dei beni mobili registrati (art. 521-bis c.p.c.).")
    a.cosa_fare.append("Se servono altri beni, istanza di ricerca telematica dei beni da pignorare (art. 492-bis c.p.c.).")
    a.giudice = "ufficiale giudiziario e giudice dell'esecuzione del tribunale del luogo dei beni o della residenza del debitore"
    a.dati_mancanti = ["banca presso cui è acceso il conto e dati del bene da pignorare", "residenza del debitore"]
    if c.tipo == "redazione":
        from ..bozze import ricorso_generico

        a.bozza = ricorso_generico("Atto di precetto (art. 480 c.p.c.)", "", f, "intimazione di pagamento in forza di titolo esecutivo",
                                   ["Titolo esecutivo: [da completare].", "Somme dovute: [da completare]."],
                                   "si intima di pagare entro dieci giorni dalla notificazione.", "titolo esecutivo.",
                                   "artt. 479 e 480 c.p.c.")
    return a



# ------------------------------------------------------------------- pignoramento presso terzi
def riconosci_pignoramento_terzi(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    if re.search(r"terzo proprietari|opposizione di terzo|619|tesoreria|dello stato\b|amministrazion|ipotec", t) or "precett" in t:
        return 0
    return 6 if re.search(r"pignor", t) and re.search(r"stipendi|salari|\bpension|conto corrent|presso terzi|datore di lavoro|"
                                                     r"\bterzo\b|banca|crediti del debitore|canoni di locazione", t) and not re.search(
        r"492[- ]bis|ricerca (?:telematica )?(?:dei )?beni|scopr|dove lavora", t) else 0


def analizza_pignoramento_terzi(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("pignoramento_terzi", "esecuzione — pignoramento presso terzi", modello="ESE_001", forma=forma(c))
    a.capito = ["Pignoramento di crediti del debitore verso terzi (stipendio, pensione, conto corrente)."]
    a.rimedio = "atto di pignoramento presso terzi notificato al terzo e al debitore, dopo titolo e precetto"
    a.conclusione = [
        Punto("Il pignoramento di crediti del debitore verso terzi si esegue con atto notificato al terzo e al debitore.",
              [Rif("cpc:543", "si esegue mediante atto notificato al terzo e al debitore")]),
        Punto("Stipendi e salari dovuti da privati si pignorano nella misura di un quinto per ogni credito diverso dagli "
              "alimentari; per il concorso di più cause il pignoramento non può superare la metà.",
              [Rif("cpc:545", "possono essere pignorate nella misura di un quinto"),
               Rif("cpc:545", "non puo' estendersi oltre alla meta'")]),
        Punto("Prima del pignoramento servono la notificazione del titolo esecutivo e il precetto, con termine non minore di "
              "dieci giorni.", [Rif("cpc:479", "notificazione del titolo esecutivo"), Rif("cpc:480", "non minore di dieci giorni")]),
    ]
    a.dati_mancanti.append("datore di lavoro o banca del debitore (terzo pignorato)")
    return a


# ------------------------------------------------------------------- ricerca telematica dei beni
def riconosci_ricerca_beni(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    return 7 if re.search(r"492[- ]bis|ricerca (?:telematica|con modalita telematiche) (?:dei )?beni|ricerca dei beni|"
                          r"cerca\w* (?:i |dei )?beni|quali conti|che conti|banche dati|"
                          r"scopr\w* (?:dove lavora|i beni|i conti|che beni|quali beni)|anagrafe tributaria|banche dati[^?]{0,40}debitor|"
                          r"archivio dei rapporti finanziari", t) else 0


def analizza_ricerca_beni(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("ricerca_beni", "esecuzione — ricerca telematica dei beni", forma=forma(c))
    a.capito = ["Il creditore vuole individuare beni, conti o datore di lavoro del debitore da pignorare."]
    a.rimedio = "istanza di ricerca telematica dei beni da pignorare all'ufficiale giudiziario (art. 492-bis c.p.c.)"
    a.conclusione = [
        Punto("Su istanza del creditore munito di titolo esecutivo e di precetto, l'ufficiale giudiziario del tribunale del luogo "
              "di residenza, domicilio, dimora o sede del debitore procede alla ricerca telematica dei beni da pignorare.",
              [Rif("cpc:492bis", "Su istanza del creditore munito del titolo esecutivo e del precetto"),
               Rif("cpc:492bis", "procede alla ricerca con modalita' telematiche dei beni da pignorare")]),
        Punto("L'istanza non può essere proposta prima che sia decorso il termine del precetto, e deve indicare l'indirizzo di "
              "posta elettronica ordinaria e la PEC del difensore.",
              [Rif("cpc:492bis", "L'istanza non puo' essere proposta prima che sia decorso il termine di cui all'articolo 482"),
               Rif("cpc:492bis", "indirizzo di posta elettronica ordinaria del difensore")]),
    ]
    return a
