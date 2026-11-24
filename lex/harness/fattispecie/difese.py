"""Regole per chi subisce l'iniziativa dell'altra parte, dove il lato cambia davvero rimedio, termine o giudice.

- datore di lavoro che riceve l'impugnazione del licenziamento o il ricorso del lavoratore (art. 416 c.p.c.; artt. 6
  l. 604/1966 e 6 d.lgs. 23/2015);
- condominio (amministratore) convenuto o chiamato in mediazione da un condomino (artt. 1131 c.c. e 5 d.lgs. 28/2010);
- responsabile del sinistro stradale a cui il danneggiato chiede i danni (artt. 1913 e 1917 c.c., art. 144 d.lgs.
  209/2005);
- venditore professionista a cui il consumatore chiede i rimedi per il difetto di conformità (artt. 134 e 135-bis
  d.lgs. 206/2005);
- locatore a cui l'ex conduttore chiede le somme pagate oltre il canone registrato (art. 13 l. 431/1998, artt. 2964 e
  2969 c.c.).

Il lato si legge con lato.py (FAMIGLIE e RUOLI): una regola di difesa risponde solo quando il racconto dice che la parte
assistita è quella che subisce.

Parole dei ruoli, che entrano così nel lessico del correttore dei refusi (normalizzazione.lessico) e non vengono «corrette»
in parole vicine: lavoratore, lavoratrice, dipendente, operaio, operaia, cameriere, cameriera, commesso, commessa,
impiegato, impiegata, apprendista, autista, magazziniere, badante, titolare, datore, datrice, condomino, condomina,
amministratore, inquilino, inquilina, conduttore, conduttrice, proprietario, proprietaria, locatore, locatrice, venditore,
rivenditore, negozio, concessionario, consumatore, consumatrice, danneggiato, danneggiata, tamponato, tamponata,
responsabile.
"""
from __future__ import annotations

import re
from datetime import timedelta

from ..comprensione import Comprensione
from ..fatti import Fatti
from ..lato import PASSIVO, lato_della_parte
from ..modello import Analisi, Punto, Rif
from ..norme import piano
from ..termini import data_breve, termine_giorni, termine_mesi
from .strumenti import data_di, data_dopo, forma, importi_in, frase


def _subisce(f: Fatti, fam: str) -> bool:
    return lato_della_parte(f.testo, fam) == PASSIVO


# ------------------------------------------------------------------- datore di lavoro
def riconosci_difesa_datore(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    if not re.search(r"licenzi|ricorso[^.]{0,40}(?:lavoro|lavorat|dipendent)|giudice del lavoro|differenze retributiv|"
                     r"straordinari|tfr|mansioni|demansionament", t):
        return 0
    if re.search(r"appell|sentenza|cassazion|secondo grado|reclamo|respint|rigettat|accolt", t):
        return 0                                     # impugnazioni della decisione: regole dell'appello
    return 8 if _subisce(f, "lavoro") else 0


def analizza_difesa_datore(c: Comprensione, f: Fatti) -> Analisi:
    t = piano(f.testo)
    a = Analisi("difesa_datore_lavoro", "lavoro — difesa del datore", forma=forma(c))
    udienza = data_dopo(f, r"udienza(?: di discussione)?(?: fissata)?(?: al| per il| il)?")
    ricorso = bool(re.search(r"ricorso|giudice del lavoro|tribunale[^.]{0,30}lavoro|udienza", t))
    a.capito = ["Assisto il datore di lavoro: il lavoratore " + ("ha proposto ricorso al giudice del lavoro"
                                                                  if ricorso else "ha impugnato il licenziamento")
                + (f", udienza il {udienza.strftime('%d/%m/%Y')}" if udienza else "") + "."]
    a.giudice = "tribunale in funzione di giudice del lavoro"
    if ricorso:
        a.rimedio = "memoria difensiva di costituzione del convenuto nel rito del lavoro (art. 416 c.p.c.)"
        a.conclusione = [Punto(
            "Il datore convenuto si costituisce almeno dieci giorni prima dell'udienza depositando una memoria difensiva, "
            "nella quale propone, a pena di decadenza, le domande riconvenzionali e le eccezioni processuali e di merito "
            "non rilevabili d'ufficio.",
            [Rif("cpc:416", "Il convenuto deve costituirsi almeno dieci giorni prima della udienza"),
             Rif("cpc:416", "a pena di decadenza, le eventuali domande in via riconvenzionale")])]
        a.inquadramento = [Punto(
            "Nella stessa memoria va presa posizione precisa sui fatti affermati dal lavoratore, non con una contestazione "
            "generica, e vanno indicati a pena di decadenza i mezzi di prova, depositando subito i documenti.",
            [Rif("cpc:416", "non limitata ad una generica contestazione"),
             Rif("cpc:416", "i documenti che deve contestualmente depositare")])]
        if udienza:
            limite = udienza - timedelta(days=10)
            a.termini = [Punto(f"Udienza del {udienza.strftime('%d/%m/%Y')}: costituzione con la memoria al più tardi il "
                               f"{limite.strftime('%d/%m/%Y')} (dieci giorni prima).",
                               [Rif("cpc:416", "almeno dieci giorni prima della udienza")])]
            a.avvertenze.append("Consiglio operativo: il termine si conta a ritroso dall'udienza; se l'ultimo giorno cade "
                                "di sabato o festivo, depositare il giorno lavorativo precedente.")
        else:
            a.dati_mancanti.append("data dell'udienza fissata nel decreto (per il termine di costituzione)")
    else:
        a.rimedio = ("verifica della tempestività dell'impugnazione e valutazione dell'offerta di conciliazione; difesa "
                     "nel giudizio se il lavoratore deposita il ricorso")
        a.conclusione = [Punto(
            "L'impugnazione stragiudiziale è efficace se fatta entro sessanta giorni dalla comunicazione scritta del "
            "licenziamento, e perde efficacia se entro i successivi centottanta giorni il lavoratore non deposita il ricorso "
            "o non chiede il tentativo di conciliazione o l'arbitrato.",
            [Rif("l604:6", "entro sessanta giorni dalla ricezione della sua comunicazione in forma scritta"),
             Rif("l604:6", "L'impugnazione e' inefficace se non e' seguita, entro il successivo termine di centottanta giorni")])]
        lettera = data_di(f, r"impugn|lettera|contesta")
        if lettera:
            a.termini = [Punto(f"Impugnazione del {lettera.strftime('%d/%m/%Y')}: il ricorso o la richiesta di conciliazione "
                               f"devono seguire entro {data_breve(termine_giorni(lettera, 180, sostanziale=True))}; "
                               "altrimenti l'impugnazione è inefficace.",
                               [Rif("l604:6", "entro il successivo termine di centottanta giorni")])]
        a.inquadramento = [Punto(
            "Per i lavoratori soggetti al d.lgs. 23/2015 il datore può offrire, entro i termini dell'impugnazione "
            "stragiudiziale e in una sede protetta, una somma esente pari a una mensilità per anno di servizio (da tre a "
            "ventisette); l'accettazione estingue il rapporto e vale come rinuncia all'impugnazione.",
            [Rif("dlgs23:6", "entro i termini di impugnazione stragiudiziale del licenziamento"),
             Rif("dlgs23:6", "non inferiore a tre e non superiore a ventisette mensilita"),
             Rif("dlgs23:6", "rinuncia alla impugnazione del licenziamento")])]
        a.avvertenze.append(Punto(
            "Se arriva il ricorso, la memoria difensiva va depositata almeno dieci giorni prima dell'udienza, con tutte le "
            "eccezioni e le prove a pena di decadenza.",
            [Rif("cpc:416", "almeno dieci giorni prima della udienza")]))
    a.competenza = [Punto("Sulle controversie di lavoro decide il tribunale in funzione di giudice del lavoro.",
                          [Rif("cpc:413", "tribunale in funzione di giudice del lavoro")])]
    a.cosa_fare = ["Raccogliere lettera di licenziamento con prova della consegna, contestazioni disciplinari, buste paga, "
                   "contratto e data di assunzione (per il regime di tutela applicabile).",
                   "Verificare le date: ricezione del licenziamento, impugnazione, deposito del ricorso.",
                   "Valutare con il cliente una conciliazione in sede protetta prima dell'udienza."]
    a.dati_mancanti += ["data di assunzione e dimensioni dell'azienda (regime di tutela)", "motivo del licenziamento"]
    return a


# ------------------------------------------------------------------- condominio convenuto
def riconosci_difesa_condominio(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    if "condomin" not in t or not re.search(r"impugn|citat|citazion|mediazion|causa|ricorso|delibera", t):
        return 0
    return 8 if _subisce(f, "condominio") else 0


def analizza_difesa_condominio(c: Comprensione, f: Fatti) -> Analisi:
    t = piano(f.testo)
    a = Analisi("difesa_condominio", "condominio — difesa del condominio", forma=forma(c))
    mediazione = "mediazion" in t
    a.capito = ["Assisto il condominio (amministratore): un condomino ha avviato " +
                ("la mediazione" if mediazione else "la causa") + " contro il condominio."]
    a.rimedio = ("partecipazione alla mediazione e costituzione in giudizio per il condominio, con notizia immediata "
                 "all'assemblea quando la lite esce dalle attribuzioni dell'amministratore")
    a.giudice = "tribunale del luogo dell'edificio (o giudice di pace per valore)"
    a.conclusione = [Punto(
        "L'amministratore può essere convenuto in giudizio per qualunque azione sulle parti comuni; se la citazione esorbita "
        "dalle sue attribuzioni deve darne senza indugio notizia all'assemblea, altrimenti può essere revocato e risponde "
        "dei danni.",
        [Rif("cc:1131", "Puo' essere convenuto in giudizio per qualunque azione concernente le parti comuni"),
         Rif("cc:1131", "tenuto a darne senza indugio notizia all'assemblea dei condomini")])]
    a.procedibilita = [Punto("Il condominio è materia di mediazione obbligatoria: la mediazione è condizione di "
                             "procedibilità della domanda del condomino.",
                             [Rif("dlgs28:5", "condominio"), Rif("dlgs28:5", "condizione di procedibilita' della domanda")])]
    if re.search(r"delibera", t):
        a.inquadramento = [Punto(
            "Per l'impugnazione di una delibera va controllato subito il termine di trenta giorni (dalla deliberazione per "
            "dissenzienti e astenuti, dalla comunicazione per gli assenti): se è decorso, la decadenza va eccepita.",
            [Rif("cc:1137", "termine perentorio di trenta giorni"), Rif("cc:2969", "non puo' essere rilevata d'ufficio")])]
    a.cosa_fare = ["Convocare l'assemblea per informarla e per deliberare sulla partecipazione alla mediazione e sulla "
                   "difesa in giudizio, con il conferimento dell'incarico al difensore.",
                   "Raccogliere verbale della delibera impugnata, convocazione con prova del ricevimento, regolamento.",
                   "Verificare data della delibera, presenza o assenza del condomino e data della comunicazione del verbale."]
    a.dati_mancanti = ["verbale della delibera e data della comunicazione al condomino", "data del primo incontro di mediazione"]
    return a


# ------------------------------------------------------------------- responsabile del sinistro stradale
def riconosci_sinistro_responsabile(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    if not re.search(r"tamponat|sinistro|incidente|urtat|investit", t):
        return 0
    return 8 if _subisce(f, "sinistro") else 0


def analizza_sinistro_responsabile(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("sinistro_responsabile", "responsabilità civile auto — difesa del responsabile", forma=forma(c))
    d_sin = data_di(f, r"tamponat|sinistro|incidente|urtat|investit")
    richiesti = importi_in(frase(f, r"chied|pretend|danni"))
    a.capito = ["Assisto il conducente ritenuto responsabile del sinistro" +
                (f" del {d_sin.strftime('%d/%m/%Y')}" if d_sin else "") + ": il danneggiato chiede il risarcimento"
                + (f" ({richiesti[0]:,.0f} euro)".replace(",", ".") if richiesti else "") + "."]
    a.rimedio = ("avviso del sinistro alla propria assicurazione, che gestisce la richiesta; nessun pagamento diretto "
                 "senza l'assicuratore")
    a.giudice = "giudice di pace o tribunale per valore, se il danneggiato agisce"
    a.conclusione = [
        Punto("L'assicurato deve dare avviso del sinistro all'assicuratore entro tre giorni dal fatto o da quando ne ha avuto "
              "conoscenza.", [Rif("cc:1913", "entro tre giorni da quello in cui il sinistro si e' verificato")]),
        Punto("Nell'assicurazione della responsabilità civile l'assicuratore deve tenere indenne l'assicurato di quanto deve "
              "pagare al terzo; se il danneggiato cita l'assicurato, questi può chiamare in causa l'assicuratore.",
              [Rif("cc:1917", "l'assicuratore e' obbligato a tenere indenne l'assicurato"),
               Rif("cc:1917", "L'assicurato, convenuto dal danneggiato, puo' chiamare in causa l'assicuratore")]),
    ]
    a.inquadramento = [Punto(
        "Il danneggiato ha azione diretta contro l'assicuratore del responsabile; nel giudizio il responsabile del danno "
        "deve essere chiamato anche lui.",
        [Rif("dlgs209:144", "ha azione diretta per il risarcimento del danno"),
         Rif("dlgs209:144", "il responsabile del danno")])]
    if d_sin:
        a.termini = [Punto(f"Sinistro del {d_sin.strftime('%d/%m/%Y')}: l'avviso all'assicuratore andava dato entro tre "
                           f"giorni; se non è stato fatto, farlo subito e conservarne la prova.",
                           [Rif("cc:1913", "entro tre giorni")])]
    a.cosa_fare = ["Inviare subito alla propria compagnia la denuncia del sinistro (modulo CAI se compilato) e la lettera "
                   "ricevuta dal danneggiato.", "Non riconoscere la responsabilità né pagare direttamente senza "
                   "l'assicuratore.", "Se arriva una citazione, consegnarla alla compagnia e valutare la chiamata in causa."]
    a.dati_mancanti = ["compagnia e numero di polizza", "modulo CAI o dinamica del sinistro", "data della richiesta ricevuta"]
    return a


# ------------------------------------------------------------------- venditore professionista
def riconosci_garanzia_venditore(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    if not re.search(r"difett|non funzion|rott|guast|non raffredd|non si accende|perde|smesso di funzionare|sostitu|ripar|"
                     r"garanzia|conformita|rimborso", t):
        return 0
    return 8 if _subisce(f, "garanzia") else 0


def analizza_garanzia_venditore(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("garanzia_venditore", "consumo — difesa del venditore", forma=forma(c))
    vendita = data_di(f, r"vendut|consegnat|acquistat|comprat")
    a.capito = ["Assisto il venditore professionista: un consumatore chiede i rimedi per un difetto di conformità del bene"
                + (f" venduto il {vendita.strftime('%d/%m/%Y')}" if vendita else "") + "."]
    a.rimedio = ("riscontro al consumatore con il rimedio dovuto (ripristino della conformità con riparazione o "
                 "sostituzione, poi riduzione del prezzo o risoluzione) e regresso verso il fornitore responsabile")
    a.giudice = "foro del consumatore, se la lite arriva in giudizio"
    a.conclusione = [
        Punto("Per il difetto di conformità il consumatore ha diritto al ripristino della conformità, a una riduzione "
              "proporzionale del prezzo o alla risoluzione del contratto, alle condizioni di legge.",
              [Rif("dlgs206:135bis", "il consumatore ha diritto al ripristino della conformita")]),
        Punto("Il venditore finale che ha soddisfatto il consumatore può agire in regresso, entro un anno dall'esecuzione "
              "della prestazione, contro chi nella catena distributiva è responsabile del difetto.",
              [Rif("dlgs206:134", "puo' agire in regresso, entro un anno dall'esecuzione della prestazione")]),
    ]
    if vendita:
        a.termini = [Punto(f"Il regresso verso il fornitore si conta dall'esecuzione del rimedio (riparazione o sostituzione): "
                           f"eseguito il rimedio, l'azione va proposta entro un anno.",
                           [Rif("dlgs206:134", "entro un anno dall'esecuzione della prestazione")])]
    a.cosa_fare = ["Verificare la data di consegna del bene e quando è comparso il difetto.",
                   "Proporre per iscritto il rimedio (riparazione o sostituzione) e conservare la prova dell'esecuzione.",
                   "Comunicare subito il difetto al fornitore o al produttore e conservare la documentazione per il regresso."]
    a.dati_mancanti = ["data di consegna", "data di comparsa del difetto e descrizione", "fattura di acquisto dal fornitore"]
    return a


# ------------------------------------------------------------------- locatore e canone oltre quello registrato
def riconosci_locatore_canone_nero(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    if not (re.search(r"in nero|non registrat|extra canone|oltre (?:al|il) canone|maggior canone|canone superiore", t)
            and re.search(r"restitu|indietro|riavere|rimborso", t)):
        return 0
    return 8 if _subisce(f, "canone") else 0


def analizza_locatore_canone_nero(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("locatore_canone_nero", "locazione — difesa del locatore", forma=forma(c))
    riconsegna = data_di(f, r"riconsegn|chiavi|rilasciat")
    a.capito = ["Assisto il locatore: l'ex conduttore chiede la restituzione delle somme pagate oltre il canone registrato."]
    a.rimedio = ("verifica della decadenza semestrale dalla riconsegna e, se maturata, eccezione di decadenza nella "
                 "mediazione e nel giudizio; altrimenti valutazione di un accordo")
    a.giudice = "tribunale del luogo dell'immobile, dopo la mediazione obbligatoria"
    a.conclusione = [
        Punto("Il patto sul canone superiore a quello registrato è nullo e il conduttore può chiedere la restituzione, ma con "
              "azione proponibile nel termine di sei mesi dalla riconsegna dell'immobile.",
              [Rif("l431:13", "superiore a quello risultante dal contratto scritto e registrato"),
               Rif("l431:13", "sei mesi dalla riconsegna")]),
        Punto("La decadenza non può essere rilevata d'ufficio dal giudice: va eccepita dal locatore.",
              [Rif("cc:2969", "La decadenza non puo' essere rilevata d'ufficio dal giudice")]),
    ]
    a.procedibilita = [Punto("La locazione è materia di mediazione obbligatoria.", [Rif("dlgs28:5", "locazione")])]
    if riconsegna:
        lim = termine_mesi(riconsegna, 6, sostanziale=True)
        scaduto = f.oggi > lim
        a.termini = [Punto(f"Riconsegna del {riconsegna.strftime('%d/%m/%Y')}: i sei mesi scadono il {data_breve(lim)}"
                           + ("; il termine è scaduto: se l'azione (o la domanda di mediazione comunicata) non è arrivata "
                              "prima, si eccepisce la decadenza." if scaduto else
                              "; il termine è ancora aperto per il conduttore."),
                           [Rif("l431:13", "sei mesi dalla riconsegna")])]
    else:
        a.dati_mancanti.append("data di riconsegna dell'immobile")
    a.avvertenze.append(Punto("La domanda di mediazione comunicata al locatore impedisce la decadenza per una sola volta: "
                              "conta la data in cui è pervenuta.",
                              [Rif("dlgs28:8", "impedisce la decadenza per una sola volta")]))
    a.cosa_fare = ["Ricostruire la data di riconsegna delle chiavi (verbale o messaggi) e quella della richiesta ricevuta.",
                   "Raccogliere contratto registrato e ricevute dei pagamenti."]
    return a
