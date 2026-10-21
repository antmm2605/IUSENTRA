"""Schede su responsabilità civile, proprietà intellettuale e dati personali (RCD, IPD, PRI).

Base normativa: artt. 2043-2059 c.c.; codice delle assicurazioni D.Lgs. 209/2005 (artt. 145-149); L. 24/2017
(responsabilità sanitaria, tentativo obbligatorio ex art. 696-bis c.p.c.); artt. 114-127 codice del consumo (prodotti
difettosi); codice della proprietà industriale D.Lgs. 30/2005; L. 633/1941 (diritto d’autore); D.Lgs. 70/2003
(servizi della società dell’informazione); Reg. UE 2016/679 e D.Lgs. 196/2003. Le richieste stragiudiziali non
hanno sospensione feriale; le azioni giudiziali seguono le regole ordinarie.
"""
from scripts.schede_compilazione.comuni import (CC, CPC, SENZA_FERIALE, assistito, avvocato, calcolo, controparte, data_luogo, difensore,
                                                documento, fatti_documentati, lex, procura, ufficio_da_adire)
from scripts.schede_compilazione.costruisci import scheda

CDA = "209/2005"
CONS = "codice_consumo"
GDPR = "reg_ue_2016_679"
PRIV = "codice_privacy"
CPI = "30/2005"
LDA = "legge_633_1941"


def _lettera(ric="Danneggiato", res="Responsabile"):
    return [difensore(), data_luogo(), assistito(ric), controparte(res)]


def _danni():
    return [fatti_documentati("Fatto, date, luoghi, testimoni e documenti"),
            avvocato("danni", "Danni", "Danni patrimoniali (spese, mancati guadagni) e non patrimoniali (biologico con percentuale, morale) con documenti",
                     norma=[(CC, "2056", "valutazione dei danni"), (CC, "2059", "danni non patrimoniali")])]


def _privacy(diritto):
    return [difensore(), data_luogo(), assistito("Interessato"), controparte("Titolare del trattamento"),
            avvocato("trattamento", "Trattamento contestato", "Quali dati, quale trattamento, da quando, con quali prove?"),
            avvocato("richiesta", "Diritto esercitato", diritto)]


SCHEDE = [
    # ---------------- Responsabilità civile
    scheda("RCD_001", "Richiesta stragiudiziale di risarcimento e responsabilità speciali",
           ["RCD_001", "RCD_006", "RCD_007", "RCD_008", "RCD_009", "RCD_011", "RCD_012"],
           [(CC, "2043", "fatto illecito"), (CC, "2051", "cose in custodia"), (CC, "1218", "responsabilità contrattuale del professionista"),
            (CC, "2236", "colpa grave nei problemi tecnici di speciale difficoltà"), (CONS, "114", "responsabilità del produttore"),
            (CONS, "126", "decadenza dopo dieci anni dalla messa in circolazione"), (CC, "2947", "prescrizione quinquennale"), (CC, "1219", "mora")],
           _lettera() + _danni() + [
               avvocato("titolo", "Titolo della responsabilità", "Custodia, professionista, prodotto difettoso, infiltrazioni, diffamazione o lesione della reputazione?"),
               lex("rimozione", "Contenuti online", "per diffamazione o reputazione online, chiedere anche la rimozione dei contenuti con gli indirizzi URL")],
           [("Lettera", "fatto, responsabilità, danni, richiesta, termine")], ["fatto non documentato"]),

    scheda("RCD_002", "Atto di citazione per risarcimento danni e sinistro stradale", ["RCD_002", "RCD_003"],
           [(CC, "2043", "fatto illecito"), (CC, "2054", "circolazione di veicoli"), (CDA, "145", "proponibilità dopo sessanta o novanta giorni"),
            (CDA, "148", "richiesta di risarcimento"), (CDA, "144", "azione diretta"), (CDA, "149", "indennizzo diretto: azione contro il proprio assicuratore"), ("dl_132_2014", "3", "negoziazione assistita obbligatoria")],
           [difensore(), procura(), data_luogo(), assistito("Danneggiato"), controparte("Responsabile e assicuratore")] + _danni() + [
               documento("richiesta", "Richiesta all’assicuratore con ricevuta", "richiesta di risarcimento", ["richiesta", "raccomandata", "pec"],
                         obbligatorio=False, se_manca="per i sinistri stradali: l’azione è improponibile senza la richiesta e il decorso di 60 o 90 giorni"),
               avvocato("sinistro", "Sinistro stradale", "È un sinistro stradale? Danni a cose (60 giorni) o a persone (90 giorni)? Negoziazione assistita esperita?",
                        obbligatorio=False, norma=[(CDA, "145", "termini di proponibilità")]),
               ufficio_da_adire([(CPC, "7", "competenza del giudice di pace per i sinistri fino al limite di valore"), (CPC, "20", "foro dell’obbligazione")])],
           [("Fatto", "dinamica e danni"), ("Diritto", "responsabilità"), ("Conclusioni", "condanna")], ["richiesta all’assicuratore mancante nei sinistri stradali"]),

    scheda("RCD_004", "Responsabilità sanitaria: richiesta, diffida, ATP e consulenza preventiva", ["RCD_004", "RCD_005", "RCD_013", "RCD_014"],
           [("legge_24_2017", "7", "responsabilità della struttura e dell’esercente"), ("legge_24_2017", "8", "tentativo obbligatorio di conciliazione"),
            ("legge_24_2017", "12", "azione diretta contro l’assicuratore"), ("legge_24_2017", "13", "comunicazione all’esercente"),
            (CPC, "696bis", "consulenza tecnica preventiva ai fini della composizione della lite"), (CPC, "696", "accertamento tecnico preventivo")],
           _lettera("Paziente o congiunti", "Struttura sanitaria") + [procura()] + _danni() + [
               documento("cartella", "Cartella clinica e referti", "cartella clinica", ["cartella", "referto"], se_manca="chiedere la cartella clinica alla struttura"),
               avvocato("atto", "Atto", "Richiesta stragiudiziale, diffida, ricorso per consulenza preventiva o ATP?"),
               calcolo("giudizio", "Termine dopo la consulenza", "il giudizio di merito si introduce entro 90 giorni dal deposito della relazione o dalla scadenza del termine di sei mesi; contare i 90 giorni senza sospensione feriale. Se il termine è superato la domanda resta proponibile ma perde gli effetti di quella proposta con la consulenza (Cass. 15594/2025)",
                       norma=[("legge_24_2017", "8", "novanta giorni")])],
           [("Atto", "fatti clinici, danno, quesiti al consulente")], ["cartella clinica non disponibile"]),

    scheda("RCD_010", "Richiesta danni per ritardo volo o trasporto", ["RCD_010"],
           [("reg_ue_2004_261", "7", "compensazione"), ("reg_ue_2004_261", "6", "ritardo"), (CC, "1681", "responsabilità del vettore")],
           _lettera("Passeggero", "Vettore") + [
               documento("biglietto", "Biglietto e prova del ritardo", "carta d’imbarco", ["biglietto", "imbarco"], se_manca="chiedere biglietto e carta d’imbarco"),
               avvocato("ritardo", "Ritardo e distanza", "Ore di ritardo all’arrivo e distanza della tratta", norma=[("reg_ue_2004_261", "7", "importi per fasce di distanza")])],
           [("Richiesta", "volo, ritardo, compensazione e danni ulteriori")], ["ritardo inferiore a tre ore all’arrivo"]),

    scheda("RCD_015", "Messa in mora dell’assicurazione", ["RCD_015"],
           [(CDA, "148", "termini per l’offerta"), (CC, "1219", "mora"), (CC, "1917", "assicurazione della responsabilità civile")],
           _lettera("Danneggiato", "Impresa di assicurazione") + _danni() + [
               avvocato("sinistro", "Numero di sinistro e richiesta già inviata", "Estremi del sinistro e della richiesta, termini scaduti per l’offerta",
                        norma=[(CDA, "148", "trenta, sessanta o novanta giorni")])],
           [("Lettera", "sinistro, termini scaduti, richiesta")], ["richiesta originaria non inviata"]),

    # ---------------- Proprietà intellettuale e contenuti online
    scheda("IPD_001", "Diffide su marchi, diritto d’autore, immagini, contraffazione e concorrenza sleale online",
           ["IPD_001", "IPD_002", "IPD_003", "IPD_004", "IPD_005", "IPD_006", "IPD_009", "IPD_014", "IPD_015"],
           [(CPI, "20", "diritti del titolare del marchio"), (CPI, "22", "nomi a dominio"), (CPI, "133", "tutela cautelare dei nomi a dominio"),
            (LDA, "12", "diritti di utilizzazione economica"), (LDA, "96", "ritratto"), (CC, "2598", "concorrenza sleale"), (CC, "10", "abuso dell’immagine"),
            (CC, "1218", "inadempimento di licenze e accordi di riservatezza")],
           _lettera("Titolare del diritto", "Contraffattore o utilizzatore") + [
               documento("titolo", "Titolo del diritto", "registrazione del marchio, opera, contratto di licenza o NDA", ["marchio", "registrazione", "licenza", "riservatezza"],
                         se_manca="chiedere la prova della titolarità"),
               fatti_documentati("Violazioni con indirizzi, date e copie conservate"),
               avvocato("richiesta", "Richiesta", "Cessazione, rimozione, ritiro, trasferimento del dominio, risarcimento o penale")],
           [("Diffida", "diritto, violazione, richiesta, termine")], ["titolarità non provata"]),

    scheda("IPD_007", "Richiesta di rimozione, deindicizzazione e diffida al provider", ["IPD_007", "IPD_008", "IPD_010", "IPD_011"],
           [("reg_ue_2022_2065", "6", "responsabilità dell’hosting"), ("reg_ue_2022_2065", "8", "assenza dell’obbligo generale di sorveglianza"), ("reg_ue_2022_2065", "16", "segnalazione dei contenuti illegali"), (GDPR, "17", "diritto alla cancellazione"),
            (CC, "2043", "fatto illecito")],
           _lettera("Interessato", "Gestore o provider") + [
               fatti_documentati("Contenuti con indirizzi URL, date e copie"),
               avvocato("fondamento", "Fondamento", "Diffamazione, dati non più pertinenti (deindicizzazione), violazione di diritti?")],
           [("Richiesta", "contenuti, ragioni, richiesta, termine")], ["indirizzi URL non indicati"]),

    scheda("IPD_012", "Azione cautelare inibitoria e richiesta danni in materia di proprietà intellettuale", ["IPD_012", "IPD_013"],
           [(CPI, "131", "inibitoria"), (CPI, "129", "descrizione e sequestro"), (CPI, "125", "risarcimento e retroversione degli utili"), (LDA, "156", "inibitoria"),
            (LDA, "158", "risarcimento"), (CPI, "120", "competenza delle sezioni specializzate"), ("dlgs_168_2003", "3", "sezioni specializzate in materia di impresa"), *SENZA_FERIALE],
           [difensore(), procura(), data_luogo(), assistito("Titolare"), controparte("Contraffattore"),
            documento("titolo", "Titolo del diritto", "registrazione o prova della titolarità", ["registrazione", "marchio", "brevetto"], se_manca="astensione: serve il titolo"),
            fatti_documentati("Violazioni e prove"),
            avvocato("misure", "Misure o danni", "Inibitoria, descrizione, sequestro (urgenti, senza sospensione feriale) o azione di merito per i danni (con sospensione feriale)?")],
           [("Ricorso o citazione", "titolo, violazione, urgenza o danno, misure")], ["titolo non presente"]),

    # ---------------- Privacy
    scheda("PRI_001", "Esercizio dei diritti dell’interessato", ["PRI_001", "PRI_002", "PRI_009"],
           [(GDPR, "15", "accesso"), (GDPR, "16", "rettifica"), (GDPR, "17", "cancellazione"), (GDPR, "12", "risposta entro un mese, prorogabile di due"),
            (GDPR, "77", "reclamo al Garante")],
           _privacy("Accesso, rettifica, cancellazione, limitazione, portabilità od opposizione?") + [
               calcolo("termine", "Termine di risposta del titolare", "un mese dal ricevimento, prorogabile di due mesi con motivazione", norma=[(GDPR, "12", "termine")])],
           [("Richiesta", "identificazione, diritto, dati, termine")], ["identità dell’interessato non verificabile"]),

    scheda("PRI_003", "Diffide su trattamento illecito, marketing, profilazione, controlli sul lavoro", ["PRI_003", "PRI_005", "PRI_007", "PRI_008", "PRI_011"],
           [(GDPR, "6", "liceità"), (GDPR, "21", "opposizione al marketing"), (GDPR, "22", "decisioni automatizzate e profilazione"), (PRIV, "130", "comunicazioni indesiderate"),
            ("legge_300_1970", "4", "impianti di controllo a distanza"), (PRIV, "114", "garanzie sul controllo a distanza")],
           _privacy("Cessazione del trattamento, opposizione, cancellazione, risarcimento?"),
           [("Diffida", "trattamento, norme violate, richiesta, termine")], ["trattamento non descritto"]),

    scheda("PRI_004", "Riscontro del titolare a un’istanza dell’interessato", ["PRI_004"],
           [(GDPR, "12", "modalità e termini"), (GDPR, "15", "contenuto dell’accesso")],
           [difensore(), data_luogo(), assistito("Titolare del trattamento"), controparte("Interessato"),
            documento("istanza", "Istanza ricevuta", "istanza dell’interessato", ["istanza", "richiesta"], se_manca="astensione: serve l’istanza"),
            avvocato("risposta", "Risposta", "Dati trattati, finalità, destinatari, conservazione, eventuali limiti motivati")],
           [("Riscontro", "risposta per punti nel termine")], ["istanza non presente"]),

    scheda("PRI_006", "Richiesta di risarcimento per illecito trattamento o violazione dei dati", ["PRI_006", "PRI_010"],
           [(GDPR, "82", "risarcimento"), (GDPR, "33", "notifica della violazione al Garante entro 72 ore"), (GDPR, "34", "comunicazione all’interessato"),
            (PRIV, "152", "competenza del tribunale")],
           _privacy("Risarcimento, informazioni sulla violazione, misure adottate?") + [
               avvocato("danno", "Danno", "Danno materiale o immateriale, con prove", norma=[(GDPR, "82", "danno")])],
           [("Richiesta", "violazione, danno, richiesta")], ["danno non allegato"]),
]
