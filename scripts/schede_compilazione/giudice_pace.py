"""Schede del giudice di pace (GDP).

Base normativa: artt. 7, 113, 316-322 c.p.c. (procedimento davanti al giudice di pace nelle forme del rito
semplificato dopo il D.Lgs. 149/2022); D.Lgs. 150/2011 artt. 5-7; L. 689/1981 art. 22; Codice della strada
art. 204-bis; D.Lgs. 209/2005 artt. 145 e 148; art. 2054 c.c.
"""
from scripts.schede_compilazione.comuni import (T, A_RITROSO, CC, CPC, FERIALE, IN_AVANTI, SENZA_FERIALE, assistito, avvocato, calcolo, causa_pendente, controparte, data_luogo,
                                                difensore, documento, fatti_documentati, letto, procura)
from scripts.schede_compilazione.costruisci import scheda


def _parti(attore="Ricorrente", convenuto="Resistente"):
    return [difensore(), procura(), data_luogo(), assistito(f"{attore} (anagrafica e codice fiscale)"), controparte(convenuto)]


def _competenza():
    return calcolo("ufficio", "Giudice di pace competente",
                   "competenza per valore secondo i limiti vigenti dell’art. 7 (10.000 euro; 25.000 euro per la circolazione), per materia e per territorio, da confermare",
                   norma=[(CPC, "7", "competenza del giudice di pace")])


def _opposizione(provvedimento, parole, giorni_regola, norme):
    return [documento("provvedimento", f"{provvedimento} impugnato", provvedimento.lower(), parole,
                      se_manca=f"astensione: serve {provvedimento.lower()}"),
            letto("notifica", "Data di notifica o contestazione", "notifica", "relata o verbale", [{"categoria": "prova_notifica"}, {"categoria": "data"}],
                  norma=norme),
            calcolo("termine", "Ultimo giorno per l’opposizione", termine=T("notifica", 30), regola=giorni_regola + ", con sospensione feriale" + IN_AVANTI, norma=norme + [FERIALE]),
            avvocato("motivi", "Motivi di opposizione", "Quali vizi del provvedimento o dell’accertamento fai valere? Con quali prove?"),
            avvocato("sospensione", "Richiesta di sospensione", "Chiedi la sospensione dell’efficacia esecutiva? Per quali gravi e circostanziate ragioni?",
                     obbligatorio=False, norma=[("150/2011", "5", "sospensione dell’efficacia esecutiva")])]


SCHEDE = [
    scheda("GDP_001", "Ricorso davanti al giudice di pace", ["GDP_001", "GDP_002", "GDP_008", "GDP_009"],
           [(CPC, "316", "forma della domanda nel rito semplificato"), (CPC, "281undecies", "ricorso, decreto di fissazione e termini a comparire"),
            (CPC, "318", "contenuto della domanda"), (CPC, "7", "competenza"), (CPC, "113", "pronuncia secondo equità")],
           _parti() + [_competenza(),
            avvocato("domanda", "Oggetto della domanda e valore", "Cosa chiedi e per quale importo?"), fatti_documentati(),
            avvocato("prove", "Mezzi di prova e documenti", "Quali prove e documenti indichi?")],
           [("Fatto", "fatti con date e documenti"), ("Diritto", "norme applicabili o equità sotto i 1.100 euro"), ("Conclusioni", "condanna o accertamento con spese")],
           ["valore oltre la competenza del giudice di pace", "domanda non indicata",
            "si chiede una citazione: per le cause iniziate dal 28/02/2023 la domanda si propone con ricorso, quindi si redige il ricorso"]),

    scheda("GDP_003", "Comparsa di costituzione davanti al giudice di pace", ["GDP_003"],
           [(CPC, "319", "costituzione delle parti"), (CPC, "316", "rito semplificato in quanto compatibile"),
            (CPC, "281undecies", "costituzione almeno dieci giorni prima dell’udienza, a pena di decadenza"), FERIALE],
           _parti("Resistente", "Ricorrente") + [
            documento("ricorso", "Ricorso avversario e decreto di fissazione", "ricorso notificato", ["ricorso", "citazione", "decreto"],
                      se_manca="astensione: serve l’atto introduttivo avversario"),
            letto("udienza", "Udienza fissata", "udienza", "decreto di fissazione", [{"categoria": "data", "campo": "udienza"}]),
            calcolo("termine_costituzione", "Ultimo giorno per costituirsi", termine=T("udienza", 10, ritroso=True), regola="almeno dieci giorni prima dell’udienza, con sospensione feriale" + A_RITROSO,
                    norma=[(CPC, "281undecies", "termine e decadenze"), FERIALE]),
            avvocato("difese", "Difese", "Cosa contesti e cosa riconosci? Proponi domande riconvenzionali, eccezioni non rilevabili d’ufficio o chiamata di terzi?",
                     norma=[(CPC, "281undecies", "decadenze")])],
           [("Difese", "presa di posizione sui fatti, eccezioni e riconvenzionali"), ("Conclusioni", "rigetto con spese")],
           ["atto introduttivo non presente", "termine di costituzione scaduto: riconvenzionali ed eccezioni sono precluse"]),

    scheda("GDP_004", "Opposizione a verbale di violazione del codice della strada", ["GDP_004"],
           [("codice_strada", "204bis", "ricorso al giudice di pace"), ("150/2011", "7", "rito del lavoro, termini, competenza e legittimazione passiva")],
           _parti("Ricorrente (trasgressore o obbligato in solido)", "Prefetto o ente da cui dipende l’organo accertatore (per la polizia locale)") +
           [calcolo("ufficio", "Giudice di pace competente", "giudice di pace del luogo della violazione", norma=[("150/2011", "7", "competenza")])] +
           _opposizione("Verbale di accertamento", ["verbale", "contravvenzione", "multa"],
                        "30 giorni dalla contestazione o notifica (60 se residente all’estero)", [("150/2011", "7", "termine")]),
           [("Motivi", "vizi del verbale e dell’accertamento"), ("Conclusioni", "annullamento del verbale")],
           ["termine per l’opposizione scaduto", "è già stato proposto ricorso al prefetto per lo stesso verbale"]),

    scheda("GDP_005", "Opposizione a ordinanza-ingiunzione e sanzione amministrativa", ["GDP_005", "GDP_006"],
           [("legge_689_1981", "22", "opposizione all’ordinanza-ingiunzione"), ("150/2011", "6", "rito del lavoro, termine e competenza")],
           _parti("Opponente", "Autorità che ha emesso l’ordinanza") +
           [calcolo("ufficio", "Giudice competente", "giudice del luogo della violazione; giudice di pace o tribunale secondo materia e importo",
                    norma=[("150/2011", "6", "competenza")])] +
           _opposizione("Ordinanza-ingiunzione", ["ordinanza", "ingiunzione", "sanzione"],
                        "30 giorni dalla notifica (60 se residente all’estero)", [("150/2011", "6", "termine")]),
           [("Motivi", "vizi dell’ordinanza e del procedimento sanzionatorio"), ("Conclusioni", "annullamento o riduzione della sanzione")],
           ["termine per l’opposizione scaduto", "materia di competenza del tribunale"]),

    scheda("GDP_007", "Ricorso per danni da circolazione stradale", ["GDP_007"],
           [(CC, "2054", "responsabilità nella circolazione dei veicoli"), ("209/2005", "145", "proponibilità dell’azione"),
            ("209/2005", "148", "procedura di risarcimento"), ("209/2005", "144", "litisconsorzio necessario del responsabile"),
            ("209/2005", "149", "indennizzo diretto"), ("dl_132_2014", "3", "negoziazione assistita obbligatoria"), (CPC, "316", "forma della domanda")],
           _parti("Danneggiato", "Responsabile civile e compagnia assicuratrice") + [_competenza(),
            documento("richiesta", "Richiesta di risarcimento all’assicuratore", "raccomandata o PEC di messa in mora",
                      ["richiesta", "risarcimento", "messa in mora", "raccomandata"], norma=[("209/2005", "145", "sessanta o novanta giorni")],
                      se_manca="astensione: senza la richiesta e il decorso del termine l’azione è improponibile"),
            calcolo("proponibilita", "Data da cui l’azione è proponibile", "60 giorni dalla richiesta (90 per danni alla persona)",
                    norma=[("209/2005", "145", "termine di proponibilità")]),
            fatti_documentati("Sinistro: data, luogo, dinamica, danni"),
            avvocato("danni", "Danni e quantificazione", "Quali danni chiedi e con quali documenti? (competenza del giudice di pace fino a 25.000 euro)"),
            documento("negoziazione", "Invito alla negoziazione assistita e suo esito", "invito e verbale di mancato accordo", ["negoziazione"],
                      norma=[("dl_132_2014", "3", "condizione di procedibilità")],
                      se_manca="segnalare che l’azione è improcedibile senza il tentativo di negoziazione assistita"),
            avvocato("procedura", "Risarcimento diretto o ordinario", "Si applica l’indennizzo diretto verso il proprio assicuratore (art. 149) o la procedura ordinaria?",
                     norma=[("209/2005", "149", "indennizzo diretto")])],
           [("Fatto", "dinamica del sinistro con documenti"), ("Diritto", "responsabilità e presunzioni dell’art. 2054 c.c."),
            ("Conclusioni", "condanna in solido al risarcimento")],
           ["richiesta all’assicuratore assente o termine non decorso", "negoziazione assistita non esperita"]),

    scheda("GDP_010", "Istanza di sospensione dell’efficacia esecutiva", ["GDP_010"],
           [("150/2011", "5", "sospensione dell’efficacia esecutiva")],
           [difensore(), data_luogo(), assistito(), controparte(), causa_pendente(),
            avvocato("ragioni", "Gravi e circostanziate ragioni", "Quali gravi e circostanziate ragioni giustificano la sospensione?",
                     norma=[("150/2011", "5", "presupposti")])],
           [("Istanza", "ragioni esplicite della sospensione")], ["ragioni non indicate"]),

    scheda("GDP_011", "Memoria integrativa davanti al giudice di pace", ["GDP_011", "GDP_012"],
           [(CPC, "320", "trattazione della causa"), (CPC, "281duodecies", "memorie su richiesta: fino a 20 giorni più 10 per la prova contraria"),
            (CPC, "321", "decisione")],
           [difensore(), data_luogo(), assistito(), controparte(), causa_pendente(),
            letto("udienza", "Udienza e termini assegnati", "udienza", "verbali", [{"categoria": "data", "campo": "udienza"}]),
            calcolo("termine", "Ultimo giorno per il deposito", "termine perentorio assegnato dal giudice, con sospensione feriale" + IN_AVANTI,
                    norma=[(CPC, "281duodecies", "termini perentori"), FERIALE]),
            avvocato("contenuto", "Contenuto", "Cosa vuoi precisare, quali prove indichi o quali conclusioni rassegni?")],
           [("Memoria", "precisazioni, prove o conclusioni")], ["termini assegnati non noti"]),

    scheda("GDP_013", "Istanza di decisione secondo equità", ["GDP_013"],
           [(CPC, "113", "giudizio di equità entro 1.100 euro")],
           [difensore(), data_luogo(), assistito(), controparte(), causa_pendente(),
            calcolo("valore", "Valore della causa", "valore della domanda non superiore a 1.100 euro, esclusi i contratti per adesione",
                    norma=[(CPC, "113", "limite di valore")])],
           [("Istanza", "presupposti del giudizio di equità")], ["valore superiore a 1.100 euro o contratto concluso mediante moduli"]),

    scheda("GDP_014", "Opposizione a cartella o intimazione per sanzioni amministrative", ["GDP_014", "GDP_015"],
           [("150/2011", "7", "opposizione recuperatoria per verbali del codice della strada non notificati"),
            ("150/2011", "6", "opposizione recuperatoria per ordinanze-ingiunzione"), (CPC, "615", "fatti estintivi successivi al titolo"),
            (CPC, "617", "vizi formali dell’atto, venti giorni"), FERIALE, *SENZA_FERIALE],
           _parti("Opponente", "Ente creditore e agente della riscossione") + [
            documento("atto", "Cartella o intimazione", "cartella di pagamento o intimazione", ["cartella", "intimazione"],
                      se_manca="astensione: serve l’atto opposto"),
            avvocato("natura", "Natura del credito", "La cartella riguarda sanzioni amministrative (non tributi)? Per i tributi è competente il giudice tributario"),
            letto("notifica", "Data di notifica", "notifica", "relata", [{"categoria": "prova_notifica"}, {"categoria": "data"}]),
            avvocato("vizio", "Tipo di vizio",
                     "Il verbale o l’ordinanza non ti erano mai stati notificati (opposizione recuperatoria, 30 giorni), il credito si è estinto dopo (prescrizione: art. 615) o l’atto ha vizi formali (art. 617, 20 giorni)?",
                     norma=[("150/2011", "7", "recuperatoria"), (CPC, "615", "merito"), (CPC, "617", "vizi formali")]),
            calcolo("termine", "Termine e giudice secondo il vizio",
                    "recuperatoria: 30 giorni dalla notifica della cartella, con sospensione feriale, giudice di pace; art. 617: 20 giorni davanti al tribunale del luogo di notifica (Cass. 3582/2022), senza sospensione feriale (Cass. 14972/2015); art. 615: senza termine, giudice per valore, senza sospensione feriale",
                    norma=[("150/2011", "7", "trenta giorni"), FERIALE, (CPC, "617", "venti giorni"), *SENZA_FERIALE])],
           [("Motivi", "vizio indicato con lo strumento corrispondente"), ("Conclusioni", "annullamento o accertamento")],
           ["credito tributario: competente il giudice tributario", "tipo di vizio non indicato",
            "per i vizi formali il termine di venti giorni è scaduto"]),
]
