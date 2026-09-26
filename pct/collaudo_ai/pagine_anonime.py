"""Trenta pagine italiane anonimizzate, con i valori veri noti.

Ogni pagina riproduce la forma di un documento che arriva allo studio
(sentenza, decreto ingiuntivo, verbale, nota spese, ricevuta, F24, relata,
contratto, fattura…) con nomi, numeri e importi inventati. Per ogni pagina
sono noti i valori numerici veri: date, importi, numeri (ruolo, sentenza,
decreto, protocollo). Servono a misurare il cancello di ancoraggio stadio per
stadio, come propone Reducto («From Ingestion to Agents»):

- **lettura**: il valore vero è davvero nel testo letto? Alcune pagine
  portano gli errori tipici del riconoscimento ottico (``l2/03/2026``,
  ``1.234,S6``): lì un valore giusto non è nel testo, e un blocco del cancello
  è un errore di lettura, non del cancello;
- **estrazione**: quanti valori veri propone il modello;
- **cancello**: quanti valori inventati passano (obiettivo: nessuno) e quanti
  valori veri, presenti nel testo, vengono bloccati a torto (obiettivo: meno
  del 2%).

Le tabelle sono scritte come le restituisce oggi l'estrazione lineare di un
PDF (celle di una riga separate da spazi): è il caso da cui nasce la doppia
rappresentazione delle tabelle.
"""

from __future__ import annotations

from dataclasses import dataclass, field

DATA = "data"
IMPORTO = "importo"
NUMERO = "numero"


@dataclass(frozen=True)
class Valore:
    tipo: str  # data | importo | numero
    valore: str  # forma canonica: AAAA-MM-GG, 1234.56, 1234/2026 o sole cifre
    descrizione: str
    # Il riconoscimento ottico ha guastato il valore: nel testo non c'è così.
    lettura_corrotta: bool = False


@dataclass(frozen=True)
class Pagina:
    id: str
    tipo: str
    testo: str
    valori: tuple[Valore, ...] = field(default_factory=tuple)


def _v(tipo: str, valore: str, descrizione: str, corrotta: bool = False) -> Valore:
    return Valore(tipo, valore, descrizione, corrotta)


PAGINE: tuple[Pagina, ...] = (
    Pagina("p01", "sentenza (dispositivo)", """TRIBUNALE ORDINARIO DI BARI
SEZIONE LAVORO
Sentenza n. 345/2026 pubbl. il 23/09/2026
RG n. 1234/2025
REPUBBLICA ITALIANA
IN NOME DEL POPOLO ITALIANO
Il Tribunale, in funzione di giudice del lavoro, nella persona della dott.ssa Maria Bianchi,
ha pronunciato la seguente SENTENZA nella causa iscritta al n. 1234/2025 R.G.
P.Q.M.
condanna la Edilnova S.r.l. al pagamento in favore di Ferraro Lucia della somma di € 12.450,00,
oltre interessi legali dal 15/03/2024 al saldo;
condanna la convenuta alla rifusione delle spese di lite, che liquida in € 3.200,00 per compensi,
oltre spese generali al 15%, IVA e CPA come per legge, ed € 259,00 per esborsi.
Bari, 23/09/2026""", (
        _v(NUMERO, "345/2026", "numero della sentenza"), _v(DATA, "2026-09-23", "pubblicazione"),
        _v(NUMERO, "1234/2025", "numero di ruolo"), _v(IMPORTO, "12450.00", "condanna"),
        _v(DATA, "2024-03-15", "decorrenza interessi"), _v(IMPORTO, "3200.00", "compensi liquidati"),
        _v(IMPORTO, "259.00", "esborsi"),
    )),
    Pagina("p02", "decreto ingiuntivo", """TRIBUNALE DI TRANI
Decreto ingiuntivo n. 812/2026
R.G. n. 2210/2026
Il Giudice, letto il ricorso depositato il 02/07/2026 da Immobiliare Sole S.r.l.,
INGIUNGE
a De Santis Giovanni di pagare alla ricorrente, entro quaranta giorni dalla notifica,
la somma di euro 8.975,40 per canoni non corrisposti, oltre interessi dal 01/01/2026,
nonché le spese del procedimento che liquida in € 540,00 per compensi ed € 145,50 per esborsi.
Avverte l'ingiunto che nel termine suddetto può proporre opposizione.
Trani, 18 luglio 2026""", (
        _v(NUMERO, "812/2026", "numero del decreto"), _v(NUMERO, "2210/2026", "numero di ruolo"),
        _v(DATA, "2026-07-02", "deposito del ricorso"), _v(IMPORTO, "8975.40", "somma ingiunta"),
        _v(DATA, "2026-01-01", "decorrenza interessi"), _v(IMPORTO, "540.00", "compensi"),
        _v(IMPORTO, "145.50", "esborsi"), _v(DATA, "2026-07-18", "data del decreto"),
    )),
    Pagina("p03", "verbale di udienza", """TRIBUNALE ORDINARIO DI BARI - SEZIONE II CIVILE
Verbale dell'udienza del 17/09/2026
Procedimento n. 1500/2025 R.G.
Sono comparsi l'Avv. Marco Rinaldi per l'attrice e l'Avv. Paolo Greco per la convenuta.
Il Giudice, sentite le parti, rinvia la causa all'udienza del 14/01/2027 ore 10:30 per la precisazione
delle conclusioni, assegnando termine fino al 30/11/2026 per il deposito di note.
Il Giudice dott. Luca Rossi""", (
        _v(DATA, "2026-09-17", "udienza tenuta"), _v(NUMERO, "1500/2025", "numero di ruolo"),
        _v(DATA, "2027-01-14", "udienza di rinvio"), _v(DATA, "2026-11-30", "termine note"),
    )),
    Pagina("p04", "nota spese (tabella)", """NOTA SPESE - causa Ferraro / Edilnova - R.G. 1234/2025
Voce Importo
Fase di studio € 1.215,00
Fase introduttiva € 777,00
Fase istruttoria € 1.680,00
Fase decisionale € 2.025,00
Totale compensi € 5.697,00
Spese generali 15% € 854,55
Cassa avvocati 4% € 262,06
Totale € 6.813,61
Bari, 25/09/2026""", (
        _v(NUMERO, "1234/2025", "numero di ruolo"), _v(IMPORTO, "1215.00", "fase di studio"),
        _v(IMPORTO, "777.00", "fase introduttiva"), _v(IMPORTO, "1680.00", "fase istruttoria"),
        _v(IMPORTO, "2025.00", "fase decisionale"), _v(IMPORTO, "5697.00", "totale compensi"),
        _v(IMPORTO, "854.55", "spese generali"), _v(IMPORTO, "262.06", "cassa avvocati"),
        _v(IMPORTO, "6813.61", "totale"), _v(DATA, "2026-09-25", "data"),
    )),
    Pagina("p05", "ricevuta pagoPA contributo unificato", """RICEVUTA DI PAGAMENTO pagoPA
Ente creditore: Ministero della Giustizia
Causale: Contributo unificato - Tribunale di Bari
Importo pagato: 259,00 EUR
Data e ora dell'operazione: 12/05/2026 11:42:10
Codice avviso: 3012 3456 7890 1234 56
Identificativo univoco versamento (IUV): 01234567890123456
Esito: pagamento eseguito""", (
        _v(IMPORTO, "259.00", "contributo unificato"), _v(DATA, "2026-05-12", "data del pagamento"),
        _v(NUMERO, "301234567890123456", "codice avviso"), _v(NUMERO, "01234567890123456", "IUV"),
    )),
    Pagina("p06", "relata di notifica PEC", """RELATA DI NOTIFICA A MEZZO POSTA ELETTRONICA CERTIFICATA
ai sensi dell'art. 3-bis della legge n. 53 del 1994
Io sottoscritto Avv. Marco Rinaldi, difensore di Ferraro Lucia,
ho notificato l'atto di citazione relativo alla causa R.G. n. 1234/2025
alla Edilnova S.r.l. all'indirizzo edilnova@pec.example, estratto dal registro INI-PEC in data 20/09/2026.
La notifica si è perfezionata per il destinatario il 21/09/2026 alle ore 09:14.
Bari, 21/09/2026""", (
        _v(NUMERO, "1234/2025", "numero di ruolo"), _v(DATA, "2026-09-20", "estrazione INI-PEC"),
        _v(DATA, "2026-09-21", "perfezionamento"),
    )),
    Pagina("p07", "modello F24 (OCR)", """MODELLO F24 - SEZIONE ERARIO
codice tributo anno di riferimento importi a debito versati
1990 2025 l.250,00
1991 2025 125,O0
SALDO FINALE € 1.375,00
Data del versamento 16/O6/2026
Codice fiscale: FRRLCU80A41A662X""", (
        _v(IMPORTO, "1250.00", "tributo 1990", corrotta=True), _v(IMPORTO, "125.00", "tributo 1991", corrotta=True),
        _v(IMPORTO, "1375.00", "saldo finale"), _v(DATA, "2026-06-16", "data del versamento", corrotta=True),
    )),
    Pagina("p08", "contratto di locazione", """CONTRATTO DI LOCAZIONE AD USO ABITATIVO (L. 431/1998)
Tra Immobiliare Sole S.r.l., locatore, e De Santis Giovanni, conduttore,
si conviene: il contratto ha durata di anni quattro a decorrere dal 01/02/2024
e scadenza il 31/01/2028. Il canone annuo è di € 9.600,00, da corrispondere in rate mensili
anticipate di € 800,00 entro il giorno 5 di ciascun mese. Deposito cauzionale € 2.400,00.
Registrato presso l'Agenzia delle Entrate il 15/02/2024 al n. 4512 serie 3T.""", (
        _v(DATA, "2024-02-01", "decorrenza"), _v(DATA, "2028-01-31", "scadenza"),
        _v(IMPORTO, "9600.00", "canone annuo"), _v(IMPORTO, "800.00", "rata mensile"),
        _v(IMPORTO, "2400.00", "deposito cauzionale"), _v(DATA, "2024-02-15", "registrazione"),
        _v(NUMERO, "4512", "numero di registrazione"),
    )),
    Pagina("p09", "atto di precetto", """ATTO DI PRECETTO
Immobiliare Sole S.r.l., in forza del decreto ingiuntivo n. 812/2026 emesso dal Tribunale di Trani
il 18/07/2026, munito di formula esecutiva e notificato il 29/07/2026,
INTIMA a De Santis Giovanni di pagare entro dieci giorni:
sorte capitale € 8.975,40
interessi al 30/09/2026 € 212,18
spese liquidate nel decreto € 685,50
spese e compensi del precetto € 318,00
TOTALE € 10.191,08""", (
        _v(NUMERO, "812/2026", "numero del decreto"), _v(DATA, "2026-07-18", "data del decreto"),
        _v(DATA, "2026-07-29", "notifica del decreto"), _v(IMPORTO, "8975.40", "sorte capitale"),
        _v(DATA, "2026-09-30", "interessi al"), _v(IMPORTO, "212.18", "interessi"),
        _v(IMPORTO, "685.50", "spese liquidate"), _v(IMPORTO, "318.00", "spese del precetto"),
        _v(IMPORTO, "10191.08", "totale"),
    )),
    Pagina("p10", "decreto di liquidazione CTU (tabella)", """TRIBUNALE DI BARI - R.G. n. 1500/2025
DECRETO DI LIQUIDAZIONE DEL COMPENSO AL CONSULENTE TECNICO
Il Giudice, vista l'istanza depositata il 10/09/2026 dall'Ing. Carlo Neri, liquida:
onorario (art. 11 D.M. 30/05/2002) 1.850,00
maggiorazione 20% 370,00
spese documentate 214,60
totale 2.434,60
oltre IVA e contributo previdenziale, ponendo il pagamento a carico provvisorio della parte attrice.
Bari, 19/09/2026""", (
        _v(NUMERO, "1500/2025", "numero di ruolo"), _v(DATA, "2026-09-10", "deposito istanza"),
        _v(IMPORTO, "1850.00", "onorario"), _v(IMPORTO, "370.00", "maggiorazione"),
        _v(IMPORTO, "214.60", "spese documentate"), _v(IMPORTO, "2434.60", "totale"),
        _v(DATA, "2026-09-19", "data del decreto"),
    )),
    Pagina("p11", "fattura del fornitore", """FATTURA N. 58/2026 del 24/09/2026
Copisteria Centro di Rossi Anna - P.IVA 01234567890
Servizi di copia e fascicolazione atti
Imponibile € 100,00
IVA 22% € 22,00
Totale documento € 122,00
Scadenza pagamento: 24/10/2026""", (
        _v(NUMERO, "58/2026", "numero della fattura"), _v(DATA, "2026-09-24", "data della fattura"),
        _v(NUMERO, "01234567890", "partita IVA"), _v(IMPORTO, "100.00", "imponibile"),
        _v(IMPORTO, "22.00", "IVA"), _v(IMPORTO, "122.00", "totale"), _v(DATA, "2026-10-24", "scadenza"),
    )),
    Pagina("p12", "ordinanza ex art. 127-ter", """TRIBUNALE ORDINARIO DI BARI
R.G. n. 2210/2026
Il Giudice, visto l'art. 127-ter c.p.c., dispone che l'udienza del 05/11/2026 sia sostituita
dal deposito di note scritte, da depositarsi entro il 29/10/2026.
Si comunichi. Bari, 22/09/2026""", (
        _v(NUMERO, "2210/2026", "numero di ruolo"), _v(DATA, "2026-11-05", "udienza sostituita"),
        _v(DATA, "2026-10-29", "termine note"), _v(DATA, "2026-09-22", "data dell'ordinanza"),
    )),
    Pagina("p13", "estratto conto (tabella, OCR)", """ESTRATTO CONTO AL 30/06/2026
Data Descrizione Dare Avere
03/06/2026 Bonifico canone giugno 800,00
05/06/2026 Commissioni 2,5O
18/06/2026 Pagamento F24 1.375,00
Saldo finale 4.12l,35""", (
        _v(DATA, "2026-06-30", "data dell'estratto"), _v(DATA, "2026-06-03", "bonifico"),
        _v(IMPORTO, "800.00", "bonifico"), _v(DATA, "2026-06-05", "commissioni"),
        _v(IMPORTO, "2.50", "commissioni", corrotta=True), _v(DATA, "2026-06-18", "F24"),
        _v(IMPORTO, "1375.00", "F24"), _v(IMPORTO, "4121.35", "saldo", corrotta=True),
    )),
    Pagina("p14", "lettera di diffida", """Bari, 10 settembre 2026
Raccomandata A/R
Spett.le Edilnova S.r.l.
Oggetto: diffida ad adempiere - contratto di appalto del 12/03/2025
Per conto della mia assistita Ferraro Lucia La diffido a completare i lavori entro quindici giorni
dal ricevimento della presente e a restituire l'acconto di € 4.500,00 versato il 20/03/2025.
Avv. Marco Rinaldi""", (
        _v(DATA, "2026-09-10", "data della lettera"), _v(DATA, "2025-03-12", "data del contratto"),
        _v(IMPORTO, "4500.00", "acconto"), _v(DATA, "2025-03-20", "versamento dell'acconto"),
    )),
    Pagina("p15", "comunicazione di cancelleria", """Tribunale Ordinario di Bari
Numero di Ruolo generale: 312/2026
Giudice: ROSSI LUCA
Oggetto: FISSAZIONE UDIENZA
Descrizione: UDIENZA FISSATA IL 03/12/2026 10:00.
Notificato alla PEC / in cancelleria il 24/09/2026 09:12""", (
        _v(NUMERO, "312/2026", "numero di ruolo"), _v(DATA, "2026-12-03", "udienza"),
        _v(DATA, "2026-09-24", "notifica"),
    )),
    Pagina("p16", "sentenza TAR (estratto)", """REPUBBLICA ITALIANA
Il Tribunale Amministrativo Regionale per la Puglia (Sezione Seconda)
ha pronunciato la presente SENTENZA sul ricorso numero di registro generale 812 del 2026,
proposto da Ferraro Lucia contro Comune di Molfetta,
per l'annullamento del provvedimento prot. n. 45123 del 22/06/2026.
Così deciso in Bari nella camera di consiglio del giorno 16 settembre 2026.
Condanna il Comune al pagamento delle spese, liquidate in € 2.000,00 oltre accessori.""", (
        _v(NUMERO, "812/2026", "numero di registro generale"), _v(NUMERO, "45123", "protocollo"),
        _v(DATA, "2026-06-22", "data del provvedimento"), _v(DATA, "2026-09-16", "camera di consiglio"),
        _v(IMPORTO, "2000.00", "spese"),
    )),
    Pagina("p17", "verbale di conciliazione", """VERBALE DI CONCILIAZIONE IN SEDE SINDACALE (art. 411 c.p.c.)
In data 08/09/2026 le parti, Ferraro Lucia ed Edilnova S.r.l., conciliano la controversia:
la società corrisponderà alla lavoratrice la somma lorda di € 6.300,00 a titolo di incentivo all'esodo,
in tre rate di € 2.100,00 con scadenza 30/09/2026, 31/10/2026 e 30/11/2026.""", (
        _v(DATA, "2026-09-08", "conciliazione"), _v(IMPORTO, "6300.00", "somma"),
        _v(IMPORTO, "2100.00", "rata"), _v(DATA, "2026-09-30", "prima rata"),
        _v(DATA, "2026-10-31", "seconda rata"), _v(DATA, "2026-11-30", "terza rata"),
    )),
    Pagina("p18", "visura camerale", """VISURA ORDINARIA SOCIETA' DI CAPITALE
EDILNOVA S.R.L.
Numero REA: BA - 512345
Codice fiscale e n. iscr. al Registro Imprese: 07654321098
Capitale sociale: euro 50.000,00 interamente versato
Data atto di costituzione: 14/04/2011
Data iscrizione: 02/05/2011""", (
        _v(NUMERO, "512345", "numero REA"), _v(NUMERO, "07654321098", "codice fiscale"),
        _v(IMPORTO, "50000.00", "capitale sociale"), _v(DATA, "2011-04-14", "costituzione"),
        _v(DATA, "2011-05-02", "iscrizione"),
    )),
    Pagina("p19", "procura alle liti", """PROCURA ALLE LITI
Io sottoscritta Ferraro Lucia, nata a Bari il 01/01/1980, C.F. FRRLCU80A41A662X,
delego a rappresentarmi e difendermi nel giudizio R.G. n. 1234/2025 l'Avv. Marco Rinaldi.
Bari, 15 gennaio 2025""", (
        _v(DATA, "1980-01-01", "data di nascita"), _v(NUMERO, "1234/2025", "numero di ruolo"),
        _v(DATA, "2025-01-15", "data della procura"),
    )),
    Pagina("p20", "prospetto interessi (tabella)", """PROSPETTO DEGLI INTERESSI LEGALI
Capitale € 12.450,00 dal 15/03/2024
Periodo Tasso Giorni Interessi
15/03/2024 - 31/12/2024 2,50% 292 249,02
01/01/2025 - 31/12/2025 2,00% 365 249,00
01/01/2026 - 30/09/2026 1,60% 273 148,99
Totale interessi € 647,01""", (
        _v(IMPORTO, "12450.00", "capitale"), _v(DATA, "2024-03-15", "decorrenza"),
        _v(IMPORTO, "249.02", "interessi 2024"), _v(IMPORTO, "249.00", "interessi 2025"),
        _v(IMPORTO, "148.99", "interessi 2026"), _v(IMPORTO, "647.01", "totale interessi"),
        _v(DATA, "2026-09-30", "fine periodo"),
    )),
    Pagina("p21", "avviso di pagamento (OCR)", """AVVISO DI PAGAMENTO
Agenzia delle Entrate-Riscossione
Cartella n. 014 2026 00012345 67 notificata il 2l/05/2026
Importo da pagare entro 60 giorni: € 3.4I8,20
Scadenza: 20/07/2026""", (
        _v(DATA, "2026-05-21", "notifica", corrotta=True), _v(IMPORTO, "3418.20", "importo", corrotta=True),
        _v(DATA, "2026-07-20", "scadenza"),
    )),
    Pagina("p22", "comparsa di costituzione (intestazione)", """TRIBUNALE ORDINARIO DI BARI
R.G. n. 1500/2025 - G.I. dott. Luca Rossi - udienza del 17/09/2026
COMPARSA DI COSTITUZIONE E RISPOSTA
per Edilnova S.r.l. (C.F. 07654321098), in persona del legale rappresentante,
contro Ferraro Lucia. Valore della causa: € 25.000,00.""", (
        _v(NUMERO, "1500/2025", "numero di ruolo"), _v(DATA, "2026-09-17", "udienza"),
        _v(NUMERO, "07654321098", "codice fiscale"), _v(IMPORTO, "25000.00", "valore della causa"),
    )),
    Pagina("p23", "ricevuta di accettazione deposito", """ACCETTAZIONE: DEPOSITO TELEMATICO - MEMORIA - Tribunale Ordinario di Bari
Il giorno 24/09/2026 alle ore 10:58:00 il messaggio è stato accettato dal sistema.
Identificativo messaggio: opec21001.20260924105800.00001.1.1@pec.aruba.example
Dimensione della busta: 2.431.522 byte""", (
        _v(DATA, "2026-09-24", "accettazione"), _v(NUMERO, "2431522", "dimensione"),
    )),
    Pagina("p24", "parcella proforma (tabella)", """PROFORMA N. 12/2026 del 25/09/2026
Descrizione Imponibile
Compenso professionale 2.000,00
Spese generali 15% 300,00
CPA 4% 92,00
Imponibile IVA 2.392,00
IVA 22% 526,24
Totale 2.918,24
Ritenuta d'acconto 20% -460,00
Netto a pagare 2.458,24""", (
        _v(NUMERO, "12/2026", "numero della proforma"), _v(DATA, "2026-09-25", "data"),
        _v(IMPORTO, "2000.00", "compenso"), _v(IMPORTO, "300.00", "spese generali"),
        _v(IMPORTO, "92.00", "CPA"), _v(IMPORTO, "2392.00", "imponibile"), _v(IMPORTO, "526.24", "IVA"),
        _v(IMPORTO, "2918.24", "totale"), _v(IMPORTO, "460.00", "ritenuta"), _v(IMPORTO, "2458.24", "netto"),
    )),
    Pagina("p25", "atto di citazione (vocatio)", """ATTO DI CITAZIONE
Ferraro Lucia CITA Edilnova S.r.l. a comparire dinanzi al Tribunale di Bari, giudice designando,
all'udienza del giorno 25 gennaio 2027, ore di rito, con invito a costituirsi nel termine di settanta giorni
prima dell'udienza indicata ai sensi e nelle forme stabilite dall'art. 166 c.p.c.
Valore della causa: € 18.000,00. Contributo unificato: € 264,00.""", (
        _v(DATA, "2027-01-25", "udienza di comparizione"), _v(IMPORTO, "18000.00", "valore"),
        _v(IMPORTO, "264.00", "contributo unificato"),
    )),
    Pagina("p26", "decreto di fissazione udienza (lavoro)", """TRIBUNALE DI BARI - SEZIONE LAVORO
R.G. n. 1234/2025
Il Giudice, letto il ricorso depositato il 15/12/2025, fissa per la discussione
l'udienza del 12/02/2026 ore 09:30, assegnando al ricorrente termine di dieci giorni per la notifica.""", (
        _v(NUMERO, "1234/2025", "numero di ruolo"), _v(DATA, "2025-12-15", "deposito ricorso"),
        _v(DATA, "2026-02-12", "udienza di discussione"),
    )),
    Pagina("p27", "verbale di pignoramento", """UFFICIO NOTIFICAZIONI ESECUZIONI E PROTESTI
Verbale di pignoramento mobiliare del 06/10/2026, cron. n. 7788
Su istanza di Immobiliare Sole S.r.l., in forza del precetto notificato il 15/09/2026,
per il credito di € 10.191,08 oltre spese, l'Ufficiale Giudiziario ha sottoposto a pignoramento
beni stimati in € 3.200,00.""", (
        _v(DATA, "2026-10-06", "pignoramento"), _v(NUMERO, "7788", "cronologico"),
        _v(DATA, "2026-09-15", "notifica del precetto"), _v(IMPORTO, "10191.08", "credito"),
        _v(IMPORTO, "3200.00", "stima dei beni"),
    )),
    Pagina("p28", "istanza di liquidazione patrocinio a spese dello Stato", """ISTANZA DI LIQUIDAZIONE - PATROCINIO A SPESE DELLO STATO (artt. 82 e 130 D.P.R. 115/2002)
Ammissione con delibera del Consiglio dell'Ordine del 11/03/2025, n. 2025/0456
Procedimento R.G. n. 2210/2026 definito con sentenza n. 345/2026
Compenso richiesto secondo D.M. 55/2014: € 3.420,00, ridotto di un terzo (art. 130): € 2.280,00.""", (
        _v(DATA, "2025-03-11", "delibera di ammissione"), _v(NUMERO, "20250456", "numero della delibera"),
        _v(NUMERO, "2210/2026", "numero di ruolo"), _v(NUMERO, "345/2026", "numero della sentenza"),
        _v(IMPORTO, "3420.00", "compenso richiesto"), _v(IMPORTO, "2280.00", "compenso ridotto"),
    )),
    Pagina("p29", "nota di iscrizione a ruolo", """NOTA DI ISCRIZIONE A RUOLO GENERALE DEGLI AFFARI CONTENZIOSI CIVILI
Ufficio: Tribunale Ordinario di Bari
Attore: Ferraro Lucia (C.F. FRRLCU80A41A662X)
Convenuto: Edilnova S.r.l. (C.F. 07654321098)
Valore dichiarato: € 18.000,00
Contributo unificato versato: € 264,00 - Anticipazioni forfettarie: € 27,00
Data di notifica della citazione: 21/09/2026""", (
        _v(NUMERO, "07654321098", "codice fiscale"), _v(IMPORTO, "18000.00", "valore"),
        _v(IMPORTO, "264.00", "contributo unificato"), _v(IMPORTO, "27.00", "anticipazioni"),
        _v(DATA, "2026-09-21", "notifica della citazione"),
    )),
    Pagina("p30", "accordo di rateizzazione (tabella)", """PIANO DI RATEIZZAZIONE DEL DEBITO
Debito complessivo: € 4.500,00
Rata Scadenza Importo
1 31/10/2026 1.500,00
2 30/11/2026 1.500,00
3 31/12/2026 1.500,00
Firmato a Bari il 26/09/2026""", (
        _v(IMPORTO, "4500.00", "debito"), _v(DATA, "2026-10-31", "prima rata"),
        _v(DATA, "2026-11-30", "seconda rata"), _v(DATA, "2026-12-31", "terza rata"),
        _v(IMPORTO, "1500.00", "rata"), _v(DATA, "2026-09-26", "firma"),
    )),
)


__all__ = ["DATA", "IMPORTO", "NUMERO", "PAGINE", "Pagina", "Valore"]
