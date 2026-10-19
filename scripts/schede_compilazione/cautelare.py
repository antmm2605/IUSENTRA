"""Schede dei procedimenti cautelari e possessori (CAU).

Base normativa: artt. 669-bis e seguenti, 670, 671, 688, 696, 696-bis, 700, 703 c.p.c.; artt. 1137, 1168-1172,
2378, 2905 c.c., nel testo vigente al 19/10/2026.
"""
from scripts.schede_compilazione.comuni import (CC, CPC, FERIALE, IN_AVANTI, SENZA_FERIALE, assistito, avvocato, calcolo, causa_pendente, controparte, data_luogo,
                                                difensore, documento, fatti_documentati, lex, letto, procura)
from scripts.schede_compilazione.costruisci import scheda

_PROCEDIMENTO = [(CPC, "669bis", "forma della domanda"), (CPC, "669ter", "competenza ante causam"),
                 (CPC, "669sexies", "procedimento"), (CPC, "669octies", "provvedimento e inizio del merito")]


def _ricorso(attore="Ricorrente", convenuto="Resistente"):
    return [difensore(), procura(), data_luogo(), assistito(f"{attore} (anagrafica e codice fiscale)"), controparte(convenuto),
            calcolo("ufficio", "Giudice competente", "giudice competente per il merito o, in corso di causa, quello della causa",
                    norma=[(CPC, "669ter", "competenza ante causam")]), fatti_documentati()]


def _fumus_periculum(periculum_norma):
    return [avvocato("diritto_cautelato", "Diritto da tutelare", "Quale diritto vuoi tutelare e con quale azione di merito (facoltativa dopo un provvedimento anticipatorio)?",
                     norma=[(CPC, "669octies", "merito facoltativo per i provvedimenti anticipatori")]),
            avvocato("periculum", "Pericolo nel ritardo", "Quale pregiudizio grave e concreto deriverebbe dall’attesa del giudizio ordinario? Con quali prove?",
                     norma=periculum_norma)]


SCHEDE = [
    scheda("CAU_001", "Ricorso cautelare atipico ex art. 700 c.p.c.", ["CAU_001", "CAU_016", "CAU_017"],
           [(CPC, "700", "provvedimenti d’urgenza"), *_PROCEDIMENTO],
           _ricorso() + _fumus_periculum([(CPC, "700", "pregiudizio imminente e irreparabile")]) + [
            avvocato("provvedimento", "Provvedimento richiesto", "Quale provvedimento concreto chiedi al giudice?"),
            avvocato("sussidiarieta", "Assenza di una misura tipica", "Esiste un rimedio cautelare tipico (sequestro, azione possessoria, denuncia) per lo stesso scopo?",
                     norma=[(CPC, "700", "fuori dei casi regolati nelle sezioni precedenti")]),
            avvocato("inaudita", "Richiesta senza contraddittorio", "Chiedi il decreto senza sentire la controparte? Perché la convocazione pregiudicherebbe l’attuazione?",
                     obbligatorio=False, norma=[(CPC, "669sexies", "decreto inaudita altera parte")])],
           [("Fatto", "fatti con date e documenti"), ("Fumus", "probabile fondatezza del diritto con le norme"),
            ("Periculum", "pregiudizio imminente e irreparabile"), ("Conclusioni", "provvedimento richiesto")],
           ["pregiudizio non indicato o solo economico e riparabile", "esiste una misura cautelare tipica applicabile (sussidiarietà dell’art. 700)"]),

    scheda("CAU_002", "Reclamo cautelare", ["CAU_002"],
           [(CPC, "669terdecies", "reclamo al collegio e termine di quindici giorni"), *SENZA_FERIALE],
           [difensore(), procura(), data_luogo(), assistito("Reclamante"), controparte("Reclamato"), causa_pendente(),
            documento("ordinanza", "Ordinanza cautelare reclamata", "ordinanza che concede o nega la misura", ["ordinanza", "provvedimento"],
                      se_manca="astensione: serve il provvedimento da reclamare"),
            letto("comunicazione", "Data di pronuncia in udienza, comunicazione o notifica", "comunicazione", "PEC di cancelleria",
                  [{"categoria": "data"}, {"categoria": "prova_notifica"}], norma=[(CPC, "669terdecies", "decorrenza")]),
            calcolo("termine", "Ultimo giorno per il reclamo", "15 giorni dalla pronuncia in udienza, dalla comunicazione o dalla notifica se anteriore, senza sospensione feriale" + IN_AVANTI,
                    norma=[(CPC, "669terdecies", "termine perentorio"), *SENZA_FERIALE]),
            avvocato("motivi", "Motivi di reclamo", "Quali errori contesti all’ordinanza?")],
           [("Motivi", "censure all’ordinanza, una per motivo"), ("Conclusioni", "riforma del provvedimento")],
           ["termine di quindici giorni scaduto", "ordinanza non presente",
            "si vuole reclamare il decreto emesso senza contraddittorio: prima va confermato o revocato all’udienza fissata"]),

    scheda("CAU_003", "Memoria del resistente nel procedimento cautelare", ["CAU_003"],
           [(CPC, "669sexies", "contraddittorio nel procedimento cautelare")],
           [difensore(), procura(), data_luogo(), assistito("Resistente"), controparte("Ricorrente"), causa_pendente(),
            documento("ricorso", "Ricorso cautelare e decreto di fissazione", "ricorso e decreto", ["ricorso", "decreto"],
                      se_manca="astensione: serve il ricorso avversario"),
            letto("udienza", "Udienza fissata", "udienza", "decreto di fissazione", [{"categoria": "data", "campo": "udienza"}]),
            avvocato("difese", "Difese", "Cosa contesti su diritto e pericolo nel ritardo?")],
           [("Difese", "insussistenza del fumus e del periculum"), ("Conclusioni", "rigetto con spese")],
           ["ricorso avversario non presente"]),

    scheda("CAU_004", "Istanza di provvedimento senza contraddittorio", ["CAU_004"],
           [(CPC, "669sexies", "decreto senza convocazione della controparte")],
           [difensore(), data_luogo(), assistito(), controparte(), causa_pendente(),
            avvocato("ragioni", "Perché la convocazione pregiudicherebbe la misura", "Perché sentire prima la controparte renderebbe inutile il provvedimento?",
                     norma=[(CPC, "669sexies", "pregiudizio dall’attuazione")])],
           [("Istanza", "ragioni dell’urgenza estrema")], ["ragioni non indicate"]),

    scheda("CAU_005", "Ricorso per sequestro conservativo", ["CAU_005"],
           [(CPC, "671", "sequestro conservativo"), (CC, "2905", "sequestro conservativo a garanzia del credito"), *_PROCEDIMENTO,
            (CPC, "675", "esecuzione entro trenta giorni"), *SENZA_FERIALE],
           _ricorso("Creditore ricorrente", "Debitore resistente") + [
            avvocato("credito", "Credito da garantire e prova", "Qual è il credito, a quanto ammonta e con quali documenti lo provi?",
                     norma=[(CPC, "671", "creditore")]),
            avvocato("garanzia", "Timore di perdere la garanzia", "Quali fatti fanno temere che il debitore disperda i beni?",
                     norma=[(CPC, "671", "fondato timore di perdere la garanzia")]),
            avvocato("beni", "Beni da sequestrare", "Su quali beni chiedi il sequestro e fino a quale importo?", obbligatorio=False),
            calcolo("termini_successivi", "Termini dopo la concessione",
                    "esecuzione entro 30 giorni dalla pronuncia, senza sospensione feriale; causa di merito entro 60 giorni se non già pendente, calcolati per prudenza senza sospensione feriale (la scadenza più vicina: iniziare il merito prima non è mai tardivo)",
                    norma=[(CPC, "675", "trenta giorni"), (CPC, "669octies", "sessanta giorni")])],
           [("Fatto", "credito e condotte del debitore"), ("Diritto", "presupposti dell’art. 671 c.p.c."), ("Conclusioni", "autorizzazione al sequestro fino all’importo")],
           ["credito non documentato", "nessun elemento sul pericolo di dispersione"]),

    scheda("CAU_006", "Ricorso per sequestro giudiziario", ["CAU_006"],
           [(CPC, "670", "sequestro giudiziario"), *_PROCEDIMENTO, *SENZA_FERIALE],
           _ricorso() + [
            avvocato("controversia", "Controversia sulla proprietà o sul possesso", "Qual è la controversia sulla proprietà o sul possesso del bene?",
                     norma=[(CPC, "670", "controversia sulla proprietà o sul possesso")]),
            avvocato("opportunita", "Opportunità della custodia", "Perché è opportuno affidare il bene a un custode?", norma=[(CPC, "670", "custodia o gestione temporanea")])],
           [("Fatto", "bene e controversia"), ("Diritto", "presupposti dell’art. 670 c.p.c."), ("Conclusioni", "sequestro e nomina del custode")],
           ["controversia sulla proprietà o sul possesso non indicata"]),

    scheda("CAU_007", "Ricorso per accertamento tecnico preventivo", ["CAU_007", "CAU_008", "CAU_009"],
           [(CPC, "696", "accertamento tecnico e ispezione giudiziale"), (CPC, "696bis", "consulenza tecnica preventiva ai fini della composizione della lite"),
            (CPC, "693", "competenza"), ("legge_24_2017", "8", "consulenza preventiva come condizione di procedibilità nella responsabilità sanitaria"),
            ("28/2010", "5", "mediazione obbligatoria nelle materie indicate")],
           [difensore(), procura(), data_luogo(), assistito(), controparte(),
            calcolo("ufficio", "Giudice competente", "giudice competente per il merito; in caso di eccezionale urgenza, quello del luogo in cui deve eseguirsi la prova",
                    norma=[(CPC, "693", "competenza")]),
            avvocato("materia", "Materia della lite", "Si tratta di responsabilità sanitaria? (la consulenza preventiva è condizione di procedibilità)", obbligatorio=False,
                     norma=[("legge_24_2017", "8", "tentativo obbligatorio di conciliazione")]),
            avvocato("tipo", "Accertamento con urgenza o consulenza conciliativa", "Chiedi l’accertamento urgente (art. 696) o la consulenza preventiva conciliativa (art. 696-bis)?",
                     norma=[(CPC, "696", "urgenza"), (CPC, "696bis", "anche senza urgenza")]),
            avvocato("oggetto", "Stato dei luoghi o fatti da accertare", "Cosa deve accertare il consulente e perché?"),
            lex("quesiti", "Quesiti proposti", "proporre quesiti specifici al consulente", norma=[(CPC, "696bis", "quesiti")]),
            fatti_documentati()],
           [("Fatto", "situazione da accertare"), ("Istanza", "ragioni dell’accertamento e quesiti")],
           ["per l’art. 696 non è indicata l’urgenza", "oggetto dell’accertamento non indicato"]),

    scheda("CAU_010", "Ricorso possessorio di reintegrazione o manutenzione", ["CAU_010", "CAU_011"],
           [(CC, "1168", "azione di reintegrazione"), (CC, "1170", "azione di manutenzione"), (CPC, "703", "procedimento possessorio"),
            (CPC, "21", "foro del luogo del fatto"), (CPC, "705", "divieto di proporre il giudizio petitorio"), *SENZA_FERIALE],
           [difensore(), procura(), data_luogo(), assistito("Ricorrente (possessore)"), controparte("Autore dello spoglio o della molestia"),
            calcolo("ufficio", "Giudice competente", "tribunale del luogo in cui è avvenuto il fatto", norma=[(CPC, "21", "competenza"), (CPC, "703", "procedimento")]),
            avvocato("possesso", "Possesso e sua durata", "Da quando e come il cliente possiede il bene? Per la manutenzione servono: immobile o universalità di mobili, possesso ultrannuale, continuo, non interrotto, non violento né clandestino",
                     norma=[(CC, "1170", "presupposti della manutenzione")]),
            letto("spoglio", "Data dello spoglio o della molestia", "data_spoglio", "denunce, fotografie, comunicazioni", [{"categoria": "data"}, {"categoria": "evento"}],
                  norma=[(CC, "1168", "entro l’anno dallo spoglio"), (CC, "1170", "entro l’anno dalla turbativa")]),
            calcolo("termine", "Scadenza dell’anno", "un anno dallo spoglio o dalla turbativa (dalla scoperta se clandestino); termine di decadenza che non si sospende",
                    norma=[(CC, "1168", "termine annuale"), (CC, "1170", "termine annuale")]),
            fatti_documentati()],
           [("Fatto", "possesso, spoglio o molestia con date; la fase di merito si chiede entro 60 giorni dal provvedimento (art. 703)"), ("Diritto", "presupposti degli artt. 1168 o 1170 c.c."),
            ("Conclusioni", "reintegrazione o cessazione delle molestie")],
           ["anno dallo spoglio o dalla turbativa già decorso", "data dello spoglio non nota"]),

    scheda("CAU_015", "Ricorso cautelare in materia societaria", ["CAU_015"],
           [(CC, "2378", "sospensione delle delibere impugnate"), (CC, "2409", "denunzia di gravi irregolarità: procedimento camerale"),
            (CPC, "737", "forma camerale della denunzia dell’art. 2409"), (CPC, "700", "tutela atipica residuale"), *_PROCEDIMENTO],
           _ricorso("Socio o società ricorrente", "Società o amministratori") + [
            avvocato("misura", "Misura richiesta e rimedio tipico", "Chiedi la sospensione di una delibera (art. 2378), un controllo giudiziario per gravi irregolarità (art. 2409) o una misura atipica (art. 700)?",
                     norma=[(CC, "2378", "sospensione"), (CC, "2409", "denunzia al tribunale"), (CPC, "700", "residualità")]),
            avvocato("legittimazione", "Legittimazione e quote", "Il cliente ha le quote o la qualità richieste per la misura scelta?",
                     norma=[(CC, "2378", "qualità del socio per l’impugnazione")]),
            avvocato("periculum", "Pericolo nel ritardo", "Per le misure cautelari (2378 e 700): quale pregiudizio grave deriverebbe dall’attesa? Per la denunzia dell’art. 2409 non serve: è un ricorso camerale",
                     obbligatorio=False)],
           [("Fatto", "vicende societarie con documenti"), ("Diritto", "presupposti della misura scelta"), ("Conclusioni", "misura richiesta")],
           ["misura non indicata", "legittimazione del cliente non verificata"]),

    scheda("CAU_012", "Denuncia di nuova opera o di danno temuto", ["CAU_012", "CAU_013"],
           [(CC, "1171", "denunzia di nuova opera"), (CC, "1172", "denunzia di danno temuto"), (CPC, "688", "procedimento di denuncia"), *SENZA_FERIALE],
           [difensore(), procura(), data_luogo(), assistito("Ricorrente (proprietario o possessore)"), controparte(),
            calcolo("ufficio", "Giudice competente", "tribunale del luogo in cui è stata intrapresa l’opera o si trova la cosa",
                    norma=[(CPC, "688", "competenza"), (CPC, "21", "foro del luogo")]),
            avvocato("pericolo", "Opera o pericolo di danno", "Quale opera nuova (iniziata da meno di un anno e non terminata) o quale pericolo di danno grave e prossimo?",
                     norma=[(CC, "1171", "opera non terminata e non decorso l’anno"), (CC, "1172", "pericolo di danno grave e prossimo")]),
            fatti_documentati()],
           [("Fatto", "opera o situazione di pericolo con date"), ("Conclusioni", "sospensione dell’opera o misure per ovviare al pericolo")],
           ["opera già terminata o iniziata da più di un anno"]),

    scheda("CAU_014", "Istanza di sospensione della delibera impugnata", ["CAU_014"],
           [(CC, "1137", "impugnazione delle deliberazioni dell’assemblea di condominio entro trenta giorni"),
            (CC, "2377", "annullabilità delle delibere societarie e termine di novanta giorni"),
            (CC, "2378", "istanza di sospensione con l’impugnazione"), ("28/2010", "5", "mediazione obbligatoria in materia condominiale"),
            ("318/1942", "71quater", "controversie condominiali soggette a mediazione")],
           [difensore(), procura(), data_luogo(), assistito(), controparte("Condominio o società"),
            documento("delibera", "Delibera impugnata", "verbale di assemblea", ["verbale", "delibera", "assemblea"],
                      se_manca="astensione: serve la delibera"),
            avvocato("tipo", "Delibera condominiale o societaria", "Si tratta di una delibera di condominio o di società?",
                     norma=[(CC, "1137", "condominio"), (CC, "2378", "società")]),
            avvocato("motivi", "Vizi della delibera e pregiudizio", "Quali vizi ha la delibera e quale pregiudizio deriverebbe dalla sua esecuzione?"),
            letto("data_delibera", "Data della delibera o della sua comunicazione", "data_delibera", "verbale e comunicazione", [{"categoria": "data"}]),
            calcolo("termine_impugnazione", "Termine per impugnare",
                    "condominio: 30 giorni dalla delibera per i presenti o dalla comunicazione per gli assenti, con sospensione feriale; la domanda di mediazione impedisce la decadenza; società: 90 giorni secondo l’art. 2377" + IN_AVANTI,
                    norma=[(CC, "1137", "trenta giorni"), FERIALE, ("28/2010", "8", "effetti della domanda di mediazione sulla decadenza"), (CC, "2377", "novanta giorni")]),
            avvocato("impugnazione", "Impugnazione proposta o da proporre", "La sospensione si chiede con l’atto di impugnazione o in un giudizio già pendente? Per il condominio è stata avviata la mediazione?",
                     norma=[(CC, "2378", "istanza con l’impugnazione"), ("28/2010", "5", "mediazione")])],
           [("Istanza", "vizi della delibera e gravi motivi per sospenderla")],
           ["delibera non presente", "termine per impugnare scaduto"]),
]
