"""Schede del processo tributario (TRI).

Base normativa: Testo unico della giustizia tributaria D.Lgs. 175/2024 (in vigore dal 1° gennaio 2026, riproduce il
D.Lgs. 546/1992); D.P.R. 600/1973 e 602/1973; D.Lgs. 218/1997 (accertamento con adesione). Il reclamo-mediazione
(art. 17-bis D.Lgs. 546/1992) è abrogato dal D.Lgs. 220/2023 per gli atti notificati dal 4 gennaio 2024.
La sospensione feriale si applica ai termini processuali tributari, compreso il termine per ricorrere; i termini
«liberi» escludono sia il giorno iniziale sia quello finale e si calcolano con un giorno in più.
"""
from scripts.schede_compilazione.comuni import (CPC, FERIALE, IN_AVANTI, T, assistito, avvocato, calcolo, causa_pendente, controparte,
                                                data_luogo, difensore, documento, letto, lex, procura)
from scripts.schede_compilazione.costruisci import scheda

TU = "175/2024"
COMPETENZA = [(TU, "48", "corte di giustizia tributaria di primo grado nella cui circoscrizione ha sede l’ente impositore o l’agente della riscossione")]


def _parti(ric="Contribuente", res="Ente impositore o agente della riscossione"):
    return [difensore(), procura(), data_luogo(), assistito(ric), controparte(res)]


def _atto(descr="atto impugnato con relata o avviso di ricevimento"):
    return [documento("atto", "Atto impugnato", descr, ["avviso", "cartella", "intimazione", "accertamento", "ingiunzione", "fermo", "ipoteca", "diniego"],
                      norma=[(TU, "65", "atti impugnabili")], se_manca="astensione: serve l’atto impugnato"),
            letto("notifica", "Data di notifica dell’atto", "notifica", "relata o ricevuta di consegna",
                  [{"categoria": "data", "campo": "notifica"}, {"categoria": "prova_notifica"}], se_manca="chiedere la data di notifica: il termine decorre da lì")]


def _ricorso():
    return [calcolo("termine", "Ultimo giorno per notificare il ricorso", termine=T("notifica", 60),
                    regola="60 giorni dalla notifica dell’atto, con sospensione feriale; +90 giorni se è stata presentata istanza di accertamento con adesione" + IN_AVANTI,
                    norma=[(TU, "67", "sessanta giorni"), FERIALE, ("218/1997", "6", "sospensione per l’adesione")]),
            avvocato("motivi", "Motivi", "Vizi formali (notifica, motivazione, decadenza, firma) e di merito; i motivi non proposti ora non si aggiungono dopo, salvo motivi aggiunti",
                     norma=[(TU, "64", "contenuto del ricorso a pena di inammissibilità"), (TU, "70", "motivi aggiunti")]),
            avvocato("valore", "Valore della lite", "Imposta contestata al netto di interessi e sanzioni (o sanzioni se sole), per il contributo e il giudice monocratico",
                     norma=[(TU, "49", "giudice monocratico fino a 10.000 euro, escluso il valore indeterminabile"), (TU, "57", "assistenza tecnica")]),
            calcolo("ufficio", "Corte competente", "corte di giustizia tributaria di primo grado della sede dell’ente impositore o dell’agente della riscossione", norma=COMPETENZA),
            calcolo("costituzione", "Deposito del ricorso notificato", "entro 30 giorni dalla notifica del ricorso, a pena di inammissibilità, con sospensione feriale",
                    norma=[(TU, "68", "costituzione del ricorrente")])]


SCHEDE = [
    scheda("TRI_001", "Ricorso tributario contro atti impositivi e della riscossione",
           ["TRI_001", "TRI_011", "TRI_012", "TRI_013", "TRI_014", "TRI_015", "TRI_016", "TRI_017", "TRI_018"],
           [(TU, "64", "ricorso"), (TU, "65", "atti impugnabili"), (TU, "66", "proposizione"), (TU, "67", "termine"), (TU, "68", "costituzione"),
            ("600/1973", "42", "motivazione dell’avviso di accertamento"), ("600/1973", "43", "termini di decadenza dell’accertamento"),
            ("602/1973", "25", "cartella"), ("602/1973", "50", "intimazione"), ("602/1973", "77", "ipoteca"), ("602/1973", "86", "fermo"), FERIALE],
           _parti() + _atto() + [
               avvocato("tipo", "Tipo di atto e tributo", "Avviso di accertamento, cartella, intimazione, fermo, ipoteca, IMU, TARI o altro tributo locale? Con quale annualità?",
                        norma=[(TU, "65", "elenco degli atti")]),
               avvocato("prodromici", "Atti presupposti notificati", "Per cartelle e atti della riscossione: gli atti presupposti sono stati notificati? Se no, si impugnano insieme",
                        obbligatorio=False, norma=[(TU, "65", "vizi propri e atti presupposti")]),
               *_ricorso()],
           [("Fatto", "atto, notifica, pretesa"), ("Motivi", "vizi dell’atto con norme"), ("Conclusioni", "annullamento e spese"),
            ("Istanze", "sospensione e trattazione in pubblica udienza se richieste")],
           ["atto o notifica non presenti", "termine di 60 giorni già scaduto", "atto non impugnabile (es. comunicazione bonaria)"]),

    scheda("TRI_002", "Reclamo-mediazione tributaria (istituto abrogato)", ["TRI_002"],
           [(TU, "64", "ricorso"), (TU, "67", "termine per ricorrere")],
           _parti() + _atto() + [lex("abrogato", "Avviso", "segnalare che il reclamo-mediazione è abrogato per gli atti notificati dal 4 gennaio 2024: proporre il ricorso ordinario o l’istanza di autotutela")],
           [("Avviso", "istituto abrogato e alternativa")], ["atto notificato dopo il 3 gennaio 2024: usare il ricorso"]),

    scheda("TRI_003", "Appello tributario e controdeduzioni", ["TRI_003", "TRI_004"],
           [(TU, "104", "mezzi di impugnazione"), (TU, "105", "termini"), (TU, "107", "forma dell’appello"), (TU, "108", "controdeduzioni e appello incidentale"),
            (TU, "110", "eccezioni non riproposte"), (TU, "111", "domande ed eccezioni nuove"), (CPC, "327", "decadenza semestrale"), FERIALE],
           _parti("Appellante o appellato", "Controparte") + [
               documento("sentenza", "Sentenza di primo grado", "sentenza", ["sentenza"], se_manca="astensione: serve la sentenza"),
               letto("notifica", "Notifica della sentenza", "notifica", "relata", [{"categoria": "data", "campo": "notifica"}, {"categoria": "prova_notifica"}], obbligatorio=False),
               calcolo("termine_breve", "Appello dalla notifica", termine=T("notifica", 60), regola="60 giorni dalla notifica della sentenza, con sospensione feriale" + IN_AVANTI,
                       norma=[(TU, "105", "sessanta giorni")]),
               calcolo("termine_lungo", "Appello senza notifica", termine=T("provvedimento", mesi=6), regola="6 mesi dalla pubblicazione, con sospensione feriale" + IN_AVANTI,
                       norma=[(CPC, "327", "sei mesi")]),
               avvocato("motivi", "Motivi specifici", "Capi impugnati e critiche specifiche; nell’appellato, eccezioni da riproporre",
                        norma=[(TU, "107", "motivi specifici"), (TU, "110", "riproposizione")]),
               calcolo("controdeduzioni", "Costituzione dell’appellato", "entro 60 giorni dalla notifica dell’appello, con sospensione feriale", norma=[(TU, "108", "controdeduzioni"), (TU, "69", "modi e termini della costituzione")])],
           [("Motivi", "censure per capo"), ("Conclusioni", "riforma o conferma")], ["sentenza non presente", "termini scaduti"]),

    scheda("TRI_005", "Memorie, documenti e istanze in corso di causa tributaria", ["TRI_005", "TRI_007", "TRI_008", "TRI_009", "TRI_010"],
           [(TU, "80", "documenti e memorie"), (TU, "82", "pubblica udienza"), (TU, "70", "documenti e motivi aggiunti"), FERIALE],
           _parti("Parte assistita", "Controparte") + [causa_pendente(),
               letto("udienza", "Data di trattazione", "udienza", "avviso di trattazione", [{"categoria": "data", "campo": "udienza"}],
                     se_manca="chiedere la data di trattazione"),
               calcolo("documenti", "Ultimo giorno per depositare documenti", termine=T("udienza", 21, ritroso=True),
                       regola="20 giorni liberi prima della trattazione", norma=[(TU, "80", "documenti")]),
               calcolo("memorie", "Ultimo giorno per le memorie illustrative", termine=T("udienza", 11, ritroso=True),
                       regola="10 giorni liberi prima della trattazione; nello stesso termine l’istanza di pubblica udienza notificata alle parti",
                       norma=[(TU, "80", "memorie"), (TU, "82", "istanza di pubblica udienza")]),
               calcolo("repliche", "Repliche (solo camera di consiglio)", termine=T("udienza", 6, ritroso=True),
                       regola="5 giorni liberi prima della camera di consiglio", norma=[(TU, "80", "repliche")]),
               avvocato("istanza", "Atto richiesto", "Memoria, nota di deposito, istanza di pubblica udienza, rinvio o motivi aggiunti (entro 60 giorni dal deposito dei documenti che li giustificano)?",
                        norma=[(TU, "70", "motivi aggiunti")])],
           [("Atto", "contenuto secondo l’istanza")], ["data di trattazione non nota"]),

    scheda("TRI_006", "Istanza di sospensione dell’atto impugnato", ["TRI_006"],
           [(TU, "96", "sospensione dell’atto impugnato"), (TU, "106", "provvedimenti sull’esecuzione provvisoria in appello")],
           _parti() + [causa_pendente(),
               avvocato("fumus", "Fondatezza del ricorso", "Quali motivi rendono probabile l’accoglimento?"),
               avvocato("danno", "Danno grave e irreparabile", "Quali conseguenze patrimoniali concrete provoca la riscossione?", norma=[(TU, "96", "danno grave e irreparabile")])],
           [("Istanza", "fumus, periculum e richiesta di sospensione")], ["ricorso non ancora proposto"]),

    scheda("TRI_019", "Ricorso contro il diniego, anche tacito, di rimborso", ["TRI_019"],
           [(TU, "65", "rifiuto espresso o tacito della restituzione"), (TU, "67", "ricorso dopo novanta giorni dalla domanda"), FERIALE],
           _parti() + [
               documento("istanza", "Istanza di rimborso con prova della presentazione", "istanza di rimborso", ["rimborso", "istanza"],
                         se_manca="astensione: serve l’istanza di rimborso"),
               avvocato("diniego", "Diniego espresso o silenzio", "C’è un diniego espresso (60 giorni dalla notifica) o il silenzio dopo 90 giorni?",
                        norma=[(TU, "67", "termini")]),
               *_ricorso()[1:]],
           [("Ricorso", "pagamento, istanza, diniego e motivi")], ["istanza di rimborso tardiva rispetto ai termini di legge"]),

    scheda("TRI_020", "Conciliazione tributaria", ["TRI_020"],
           [(TU, "99", "conciliazione fuori udienza"), (TU, "100", "conciliazione in udienza"), (TU, "102", "definizione e sanzioni ridotte")],
           _parti() + [causa_pendente(),
               avvocato("proposta", "Proposta di conciliazione", "Importi di imposta, interessi e sanzioni ridotte e modalità di pagamento", norma=[(TU, "102", "pagamento")])],
           [("Istanza", "accordo e richiesta di definizione")], ["causa non pendente"]),
]
