"""Schede del diritto di famiglia e dei minori (FAM).

Base normativa: rito unificato artt. 473-bis ss. c.p.c. (D.Lgs. 149/2022 e correttivo D.Lgs. 164/2024); artt. 143-158,
316-337-octies e 342-bis/342-ter c.c.; L. 898/1970 sul divorzio; art. 6 D.L. 132/2014 (negoziazione assistita).
Sospensione feriale: si applica ai termini del rito unificato, anche quando si discute del mantenimento del coniuge
o dei figli o dell’assegno divorzile (Cass. SU 13 maggio 2024 n. 12946); restano escluse le cause di soli alimenti
e quelle dichiarate urgenti (art. 92 ord. giud.). Il passaporto del minore è regolato dalla L. 1185/1967.
"""
from scripts.schede_compilazione.comuni import (CC, CPC, FERIALE, SENZA_FERIALE, T, assistito, avvocato, calcolo, causa_pendente,
                                                controparte, data_luogo, difensore, documento, fatti_documentati, procura, udienza,
                                                ufficio_da_adire)
from scripts.schede_compilazione.costruisci import scheda

L898 = "legge_898_1970"
COMPETENZA = [(CPC, "473bis.11", "competenza del tribunale del luogo di residenza abituale del minore o del convenuto")]
DISCUSSA = "; con sospensione feriale anche per il mantenimento di coniuge e figli (Cass. SU 12946/2024), salvo dichiarazione d’urgenza o cause di soli alimenti"


def _parti(ric="Ricorrente", res="Resistente"):
    return [difensore(), procura(), data_luogo(), assistito(ric), controparte(res)]


def _figli():
    return avvocato("figli", "Figli: nomi, età, residenza abituale ed esigenze", "Quali figli ci sono, quanti anni hanno, dove vivono abitualmente e con chi?",
                    norma=[(CC, "337ter", "affidamento condiviso e mantenimento"), (CPC, "473bis.12", "indicazione dei figli nel ricorso")],
                    se_manca="chiedere i dati dei figli: senza non si redigono domande su affidamento e mantenimento")


def _redditi():
    return documento("redditi", "Dichiarazioni dei redditi degli ultimi tre anni e documentazione patrimoniale",
                     "dichiarazioni dei redditi, estratti conto, titolarità di beni", ["redditi", "730", "unico", "cud", "estratto"],
                     norma=[(CPC, "473bis.12", "deposito obbligatorio con domande economiche")],
                     se_manca="segnalare che con domande economiche il deposito è obbligatorio")


def _piano():
    return avvocato("piano", "Piano genitoriale", "Impegni e attività dei figli: scuola, percorso educativo, attività extrascolastiche, frequentazioni, vacanze",
                    norma=[(CPC, "473bis.12", "piano genitoriale con domande sui figli minori")])


def _violenza():
    return avvocato("violenza", "Allegazioni di violenza domestica o di genere", "Ci sono allegazioni di violenza domestica o di genere, procedimenti penali o ordini di protezione?",
                    obbligatorio=False, norma=[(CPC, "473bis.40", "disposizioni speciali in caso di violenza"), (CPC, "473bis.42", "procedimento")])


def _termini_giudiziale():
    return [udienza("Prima udienza fissata dal decreto"),
            calcolo("notifica", "Ultimo giorno per notificare ricorso e decreto", termine=T("udienza", 61, ritroso=True, liberi=True),
                    regola="almeno 60 giorni liberi prima dell’udienza (esclusi il giorno della notifica e quello dell’udienza)" + DISCUSSA, norma=[(CPC, "473bis.14", "notifica del ricorso"), FERIALE]),
            calcolo("costituzione", "Termine per la costituzione del resistente", termine=T("udienza", 30, ritroso=True),
                    regola="almeno 30 giorni prima dell’udienza" + DISCUSSA, norma=[(CPC, "473bis.16", "costituzione del convenuto"), FERIALE]),
            calcolo("memorie", "Memorie integrative prima dell’udienza",
                    "ricorrente entro 20 giorni, resistente entro 10, ricorrente entro 5 giorni prima dell’udienza; termini perentori",
                    norma=[(CPC, "473bis.17", "ulteriori difese")])]


def _negoziazione_familiare():
    return avvocato("negoziazione", "Via della negoziazione assistita", "Le parti vogliono concludere con negoziazione assistita invece del ricorso?",
                    obbligatorio=False, norma=[("dl_132_2014", "6", "negoziazione assistita in materia familiare")])


SCHEDE = [
    scheda("FAM_001", "Ricorso congiunto per separazione consensuale o divorzio congiunto", ["FAM_001", "FAM_003"],
           [(CPC, "473bis.51", "procedimento su domanda congiunta"), (CC, "158", "separazione consensuale"), (CC, "155", "provvedimenti per i figli"),
            (L898, "3", "casi di divorzio e termini dalla separazione"), *COMPETENZA],
           [difensore(), procura("serve la procura di entrambi i coniugi, anche con un solo difensore comune"), data_luogo(),
            assistito("Primo coniuge"), assistito("Secondo coniuge", nome="coniuge2"),
            documento("matrimonio", "Estratto per riassunto dell’atto di matrimonio", "estratto dell’atto di matrimonio", ["matrimonio", "estratto"],
                      se_manca="chiedere l’estratto dell’atto di matrimonio"),
            documento("separazione", "Provvedimento di separazione con data di comparizione", "sentenza o omologa di separazione", ["separazione", "omologa"],
                      obbligatorio=False, norma=[(L898, "3", "sei mesi dalla comparizione nella consensuale, dodici nella giudiziale")],
                      se_manca="per il divorzio: astensione se non è documentata la separazione con decorso dei termini"),
            _figli(), _redditi(),
            avvocato("condizioni", "Condizioni concordate", "Affidamento, collocamento, frequentazioni, assegni, casa familiare, spese straordinarie e rapporti patrimoniali",
                     norma=[(CPC, "473bis.51", "contenuto delle condizioni"), (CC, "337sexies", "assegnazione della casa familiare")]),
            avvocato("cumulo", "Cumulo di separazione e divorzio", "Si chiede anche il divorzio nello stesso ricorso (possibile, ma procedibile solo dopo i termini)?",
                     obbligatorio=False, norma=[(CPC, "473bis.49", "cumulo delle domande")]),
            _negoziazione_familiare(), ufficio_da_adire(COMPETENZA)],
           [("Ricorso", "parti, matrimonio, figli, condizioni concordate e richiesta di omologa o di sentenza"), ("Allegati", "documenti reddituali e patrimoniali")],
           ["accordo non raggiunto su tutti i punti", "divorzio senza separazione documentata o prima dei termini dell’art. 3 L. 898/1970", "procura di un solo coniuge"]),

    scheda("FAM_002", "Ricorso per separazione giudiziale o divorzio giudiziale", ["FAM_002", "FAM_004"],
           [(CPC, "473bis.12", "forma e contenuto del ricorso"), (CPC, "473bis.14", "decreto e notifica"), (CPC, "473bis.17", "memorie"),
            (CC, "151", "separazione giudiziale"), (CC, "156", "assegno di mantenimento al coniuge"), (L898, "3", "casi di divorzio"),
            (L898, "5", "assegno divorzile"), *COMPETENZA],
           _parti() + [documento("matrimonio", "Estratto per riassunto dell’atto di matrimonio", "estratto dell’atto di matrimonio", ["matrimonio"],
                                 se_manca="chiedere l’estratto dell’atto di matrimonio"),
                       fatti_documentati("Fatti che rendono intollerabile la convivenza o presupposti del divorzio"),
                       _figli(), _redditi(), _piano(), _violenza(),
                       avvocato("domande", "Domande", "Addebito, affidamento, collocamento, assegni per coniuge e figli, casa familiare, provvedimenti provvisori",
                                norma=[(CC, "151", "addebito"), (CC, "337ter", "affidamento e mantenimento"), (CPC, "473bis.22", "provvedimenti temporanei e urgenti")]),
                       ufficio_da_adire(COMPETENZA), *_termini_giudiziale()],
           [("Fatti", "storia della coppia, figli, situazione economica con documenti"), ("Diritto", "norme sulle domande proposte"),
            ("Conclusioni", "domande principali e provvisorie"), ("Mezzi di prova", "prove documentali e indicazione dei mezzi")],
           ["mancano gli estremi del matrimonio", "domande economiche senza documenti reddituali", "divorzio prima dei termini dell’art. 3 L. 898/1970"]),

    scheda("FAM_005", "Ricorso per modifica delle condizioni di separazione, divorzio o sui figli", ["FAM_005", "FAM_006", "FAM_009", "FAM_011"],
           [(CPC, "473bis.29", "revisione dei provvedimenti per giustificati motivi sopravvenuti"), (CC, "156", "modifica dell’assegno di separazione"),
            (L898, "9", "revisione delle condizioni di divorzio"), (CC, "337quinquies", "revisione delle disposizioni sui figli"), *COMPETENZA],
           _parti() + [documento("provvedimento", "Provvedimento di cui si chiede la modifica", "sentenza, decreto o omologa precedente",
                                 ["sentenza", "omologa", "decreto"], se_manca="astensione: serve il provvedimento da modificare"),
                       avvocato("sopravvenienze", "Fatti nuovi sopravvenuti", "Quali fatti sono cambiati dopo il provvedimento (redditi, lavoro, convivenze, esigenze dei figli)?",
                                norma=[(CPC, "473bis.29", "giustificati motivi sopravvenuti")]),
                       _redditi(), _figli(), ufficio_da_adire(COMPETENZA), *_termini_giudiziale()],
           [("Fatti", "confronto tra la situazione del provvedimento e quella attuale"), ("Conclusioni", "nuove condizioni richieste")],
           ["provvedimento non presente", "nessun fatto sopravvenuto indicato: si chiederebbe un riesame non ammesso"]),

    scheda("FAM_007", "Ricorso per affidamento, frequentazione e mantenimento dei figli nati fuori dal matrimonio", ["FAM_007", "FAM_008"],
           [(CPC, "473bis.12", "ricorso"), (CC, "316", "responsabilità genitoriale"), (CC, "337ter", "affidamento e mantenimento"),
            (CC, "337sexies", "casa familiare"), *COMPETENZA],
           _parti() + [_figli(), documento("nascita", "Atti di nascita o riconoscimento dei figli", "estratto di nascita", ["nascita", "riconoscimento"],
                                           se_manca="chiedere l’atto di nascita con il riconoscimento"),
                       _redditi(), _piano(), _violenza(),
                       avvocato("domande", "Domande", "Affidamento, collocamento, calendario di frequentazione, assegno, spese straordinarie, casa familiare",
                                norma=[(CC, "337ter", "contenuto dei provvedimenti")]),
                       ufficio_da_adire(COMPETENZA), *_termini_giudiziale()],
           [("Fatti", "nascita, convivenza o cessazione, abitudini dei figli"), ("Conclusioni", "regime di affidamento e mantenimento")],
           ["filiazione non documentata"]),

    scheda("FAM_010", "Ricorso per il mantenimento del figlio maggiorenne", ["FAM_010"],
           [(CC, "337septies", "figli maggiorenni non autosufficienti"), (CPC, "473bis.12", "ricorso"), *COMPETENZA],
           _parti() + [avvocato("legittimato", "Chi agisce", "Agisce il figlio maggiorenne o il genitore convivente?",
                                norma=[(CC, "337septies", "versamento diretto al figlio")]),
                       avvocato("autosufficienza", "Percorso di studio o lavoro del figlio", "Età, studi in corso, ricerca di lavoro e ragioni della mancata autosufficienza",
                                norma=[(CC, "337septies", "non autosufficienza economica")]),
                       _redditi(), ufficio_da_adire(COMPETENZA), *_termini_giudiziale()],
           [("Fatti", "età, studi o ricerca di lavoro, redditi"), ("Conclusioni", "assegno e modalità di versamento")],
           ["nessun elemento sulla mancata autosufficienza"]),

    scheda("FAM_012", "Ricorso sulla responsabilità genitoriale (limitazione o decadenza)", ["FAM_012", "FAM_013"],
           [(CC, "330", "decadenza dalla responsabilità genitoriale"), ("318/1942", "38", "competenza del tribunale per i minorenni salvo giudizio di separazione o divorzio pendente"), (CC, "333", "condotta pregiudizievole"), (CPC, "473bis.12", "ricorso"),
            (CPC, "473bis.8", "curatore speciale del minore"), *COMPETENZA],
           _parti() + [_figli(), fatti_documentati("Condotte pregiudizievoli con date, documenti, relazioni dei servizi"), _violenza(),
                       avvocato("provvedimenti", "Provvedimenti richiesti", "Limitazione, decadenza, allontanamento del genitore o del minore, affidamento ai servizi",
                                norma=[(CC, "330", "allontanamento"), (CC, "333", "provvedimenti convenienti")]),
                       ufficio_da_adire(COMPETENZA), *_termini_giudiziale()],
           [("Fatti", "condotte e pregiudizio per il minore con le fonti"), ("Conclusioni", "provvedimenti e nomina del curatore speciale")],
           ["fatti non documentati"]),

    scheda("FAM_014", "Ricorso per autorizzazione ad atti di straordinaria amministrazione per il minore", ["FAM_014"],
           [(CC, "320", "atti eccedenti l’ordinaria amministrazione: giudice tutelare"), ("318/1942", "45", "competenza del giudice tutelare"),
            (CPC, "737", "rito camerale"), (CPC, "739", "reclamo entro dieci giorni")],
           [difensore(), procura(), data_luogo(), assistito("Genitori ricorrenti"), _figli(),
            avvocato("atto", "Atto da autorizzare e utilità per il minore", "Quale atto (vendita, acquisto, mutuo, transazione, accettazione di eredità) e perché è utile o necessario per il minore?",
                     norma=[(CC, "320", "necessità o utilità evidente")]),
            documento("perizia", "Stima o documenti dell’affare", "perizia, preliminare, proposta", ["perizia", "stima", "preliminare"], obbligatorio=False)],
           [("Ricorso", "atto, utilità evidente e reimpiego delle somme; alternativa dell’autorizzazione notarile (art. 21 D.Lgs. 149/2022)")], ["utilità per il minore non indicata"]),

    scheda("FAM_015", "Istanza di provvedimenti indifferibili o temporanei e urgenti", ["FAM_015"],
           [(CPC, "473bis.15", "provvedimenti indifferibili prima dell’udienza"), (CPC, "473bis.22", "provvedimenti temporanei e urgenti"), *SENZA_FERIALE],
           _parti() + [causa_pendente(), _figli(),
                       avvocato("pregiudizio", "Pregiudizio imminente e irreparabile", "Quale pregiudizio rischiano i figli o la parte se si attende l’udienza?",
                                norma=[(CPC, "473bis.15", "pregiudizio imminente e irreparabile")]),
                       avvocato("misure", "Misure richieste", "Quali provvedimenti si chiedono subito (collocamento, assegno, casa, divieti)?")],
           [("Istanza", "pregiudizio, urgenza e misure richieste")], ["urgenza non indicata"]),

    scheda("FAM_016", "Memoria nel procedimento unitario di famiglia", ["FAM_016"],
           [(CPC, "473bis.16", "costituzione del convenuto"), (CPC, "473bis.17", "ulteriori difese"), FERIALE],
           _parti("Parte assistita", "Controparte") + [causa_pendente(), udienza(),
                       avvocato("quale", "Quale memoria", "Comparsa di costituzione o memoria dell’art. 473-bis.17 (prima, seconda o terza)?",
                                norma=[(CPC, "473bis.17", "termini differenziati")]),
                       calcolo("costituzione", "Ultimo giorno per la costituzione", termine=T("udienza", 30, ritroso=True),
                               regola="almeno 30 giorni prima dell’udienza" + DISCUSSA, norma=[(CPC, "473bis.16", "costituzione")]),
                       calcolo("memoria_20", "Prima memoria del ricorrente", termine=T("udienza", 20, ritroso=True),
                               regola="entro 20 giorni prima dell’udienza" + DISCUSSA, norma=[(CPC, "473bis.17", "prima memoria")]),
                       calcolo("memoria_10", "Memoria del resistente", termine=T("udienza", 10, ritroso=True),
                               regola="entro 10 giorni prima dell’udienza" + DISCUSSA, norma=[(CPC, "473bis.17", "seconda memoria")]),
                       calcolo("memoria_5", "Ultima memoria del ricorrente", termine=T("udienza", 5, ritroso=True),
                               regola="entro 5 giorni prima dell’udienza" + DISCUSSA, norma=[(CPC, "473bis.17", "terza memoria")]),
                       _redditi()],
           [("Difese", "risposta ai fatti avversari, domande ed eccezioni consentite nella memoria"), ("Prove", "mezzi di prova")],
           ["udienza non nota", "memoria fuori termine: segnalare la decadenza"]),

    scheda("FAM_017", "Istanze istruttorie per il minore: CTU, ascolto e curatore speciale", ["FAM_017", "FAM_018", "FAM_019"],
           [(CPC, "473bis.25", "consulenza tecnica"), (CPC, "473bis.4", "ascolto del minore"), (CPC, "473bis.5", "modalità dell’ascolto"),
            (CPC, "473bis.8", "curatore speciale"), (CPC, "473bis.6", "rifiuto del minore di incontrare il genitore")],
           _parti("Parte assistita", "Controparte") + [causa_pendente(), _figli(),
                       avvocato("istanza", "Istanza e ragioni", "Si chiede CTU, ascolto del minore o nomina del curatore speciale, e perché?",
                                norma=[(CPC, "473bis.4", "ascolto del minore che ha compiuto dodici anni o capace di discernimento"),
                                       (CPC, "473bis.8", "casi di nomina del curatore speciale")]),
                       avvocato("quesiti", "Quesiti per il consulente", "Quali quesiti si propongono?", obbligatorio=False)],
           [("Istanza", "ragioni dell’istanza e quesiti o modalità")], ["causa non pendente"]),

    scheda("FAM_020", "Ricorso per ordini di protezione contro gli abusi familiari e allontanamento", ["FAM_020", "FAM_021"],
           [(CPC, "473bis.69", "ordini di protezione"),
            (CPC, "473bis.70", "contenuto"), (CPC, "473bis.71", "procedimento"), *SENZA_FERIALE],
           _parti() + [fatti_documentati("Condotte di grave pregiudizio con date, referti, denunce"), _violenza(), _figli(),
                       avvocato("misure", "Misure richieste", "Allontanamento dalla casa, divieto di avvicinamento a luoghi indicati, assegno, intervento dei servizi",
                                norma=[(CPC, "473bis.70", "misure e durata fino a un anno")])],
           [("Fatti", "condotte e pregiudizio con documenti"), ("Conclusioni", "ordine di protezione, durata e misure")],
           ["nessun fatto di grave pregiudizio documentato"]),

    scheda("FAM_022", "Accordo di negoziazione assistita familiare o modifica consensuale", ["FAM_022", "FAM_023"],
           [("dl_132_2014", "6", "negoziazione assistita in materia di separazione, divorzio e modifica"), (CC, "337ter", "figli"), (L898, "9", "modifica")],
           [difensore(), procura("ogni parte deve avere il proprio avvocato"), data_luogo(), assistito("Parte assistita"), controparte("Altra parte"), _figli(), _redditi(),
            avvocato("condizioni", "Condizioni dell’accordo", "Contenuto concordato su figli, assegni, casa e patrimonio",
                     norma=[("dl_132_2014", "6", "contenuto e trasmissione")]),
            calcolo("trasmissione", "Trasmissione al pubblico ministero e all’ufficiale di stato civile",
                    "al procuratore della Repubblica per il nulla osta o l’autorizzazione (con figli minori o non autosufficienti); poi all’ufficiale di stato civile entro 10 giorni",
                    norma=[("dl_132_2014", "6", "nulla osta, autorizzazione e trasmissione")])],
           [("Accordo", "premesse, condizioni, dichiarazioni degli avvocati sul tentativo di conciliazione")],
           ["parti assistite da un unico avvocato", "accordo incompleto"]),

    scheda("FAM_024", "Istanza per passaporto del minore o trasferimento di residenza in caso di disaccordo", ["FAM_024", "FAM_025"],
           [(CC, "316", "contrasto tra genitori su questioni di particolare importanza"), (CC, "337ter", "decisioni di maggiore interesse"),
            ("legge_1185_1967", "3", "passaporto del minore: assenso dei genitori o, in difetto, autorizzazione del giudice tutelare"),
            ("legge_1185_1967", "3bis", "inibitoria del rilascio o dell’uso del passaporto"), (CPC, "473bis.12", "ricorso"), *COMPETENZA],
           _parti() + [_figli(),
                       avvocato("questione", "Questione e motivi", "Passaporto o trasferimento: dove, perché, con quali effetti su scuola e frequentazioni con l’altro genitore?",
                                norma=[(CC, "337ter", "residenza abituale e istruzione decise di comune accordo")]),
                       avvocato("dissenso", "Dissenso dell’altro genitore", "L’altro genitore ha negato l’assenso? Con quali motivi?"),
                       calcolo("ufficio_passaporto", "Giudice per il passaporto", "senza l’assenso dell’altro genitore decide il giudice tutelare del luogo di residenza del minore; se è pendente un giudizio di famiglia, il giudice di quel giudizio",
                               norma=[("legge_1185_1967", "3", "autorizzazione del giudice tutelare"), *COMPETENZA])],
           [("Ricorso", "interesse del minore e ragioni del disaccordo")], ["assenso dell’altro genitore già presente: il ricorso non serve"]),
]
