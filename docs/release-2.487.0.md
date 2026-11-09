# IUSENTRA 2.487.0 — Allineamento al server, commi non numerati, Corte costituzionale e giustizia amministrativa nella ricerca

## Allineamento al server
- **Contenuto.** La versione comprende tutto `main` del server fino al commit 5b73253: versioni da 2.480.10 a
  2.480.17 e consolidamento dell'import delle regole del pilota di Caddy.
- **Unione con il lavoro locale.** È unita al lavoro locale 2.484.0–2.486.0.
- **Numero di ruolo scritto per esteso.** È stato corretto da entrambe le parti e restano tutte e due le regole:
  - quella del server legge «n. 2539, del Ruolo Generale … dell'anno 2025»;
  - quella locale legge «iscritta al n. …» e «n. 2539/2025 del Ruolo Generale».
- **Test.** I test del server e quelli locali passano insieme.

## Commi non numerati
Negli atti più vecchi (es. D.P.R. 633/1972) i commi non hanno numero. Nell'archivio Normattiva i capoversi sono fusi e
la norma citata mostrava l'articolo intero.
- **Fonte del comma.** Ora il comma si legge dai capoversi dell'XML ufficiale da cui è stato importato l'atto
  (`pct/normattiva_commi_xml.py`). Il rientro d'inizio comma si ricava dall'impaginazione dell'atto; lettere e numeri
  restano nel loro comma; intestazione e note di aggiornamento sono escluse.
- **Esempio.** Art. 6, terzo comma, D.P.R. 633/1972: «Le prestazioni di servizi si considerano effettuate all'atto del
  pagamento del corrispettivo».
- **Avviso.** La scheda dichiara che il comma è stato individuato dall'XML.
- **Copertura.** Gli XML ufficiali sono sul PC per il 99,9% degli atti in archivio (`IUSENTRA_NORMATTIVA_RAW_DIR` per
  una cartella diversa).

## Correzioni della norma citata
- L'intestazione «Art. 2.» non è più scambiata per il comma 2.
- Fra articoli con lo stesso numero (articolo principale e articoli degli allegati) vale il principale.
- La scelta per gruppi di commi resta solo per le partizioni «(commi 101-150)».

## Altre corti nella ricerca
- **Corte costituzionale.** Le pronunce e le massime (22.414 pronunce) sono già nell'archivio giurisprudenza dello
  studio; ora la ricerca le consulta.
- **TAR e Consiglio di Stato.** Si consultano dal catalogo OpenGA: solo estremi, oggetto ed esito; il testo si apre
  sul sito ufficiale.
- **Tempi e guasti.** Ogni fonte ha un tempo massimo breve. Se non risponde, la ricerca prosegue con le altre e lo
  dice (`web/services/ricerca_legale_altre_corti.py`).

## Catalogo: dati riallineati, regole invariate
- **47 proposte rilette.** Erano classificate come contributo unificato con regole superate; sono state rilette con la
  rilettura puntuale, con traccia di audit.
- **3 PEC corrette.** Erano PEC di deposito telematico classificate come «ricevuta del contributo», fra cui Alessi RG
  821/2024; sono state corrette con nota, perché le PEC non si rileggono dall'archivio.
- **Regola non modificata.** Una modifica alla regola è stata provata e scartata dopo la misura sui documenti reali,
  che indicava voci peggiori.

## Scheduler: lettura delle spese in tempo lineare e guardiano
- **Blocco dell'08/11.** Un'espressione regolare non lineare nella lettura delle spese della sentenza
  (`pct/percorso_pratica/esito.py`) aveva fermato lo scheduler per oltre 90 minuti. Il dispositivo si legge ora al
  massimo per 6.000 caratteri e le frasi si dividono in tempo lineare.
- **Guardiano** (`pct/scheduler_guardiano.py`): un lavoro scrive un battito ogni 30 s; un processo separato chiude il
  worker se il battito è fermo da oltre 15 minuti e Docker lo riavvia (`init: true` nei compose).

## Termini e scadenze
- **Decorrenza in agosto** (art. 1 L. 742/1969): se il termine inizia durante la sospensione, l'inizio slitta al
  31/08 (deposito 10/08/2026 → termine lungo 01/03/2027); regola unica in `pct/termini_mesi.py`.
- **Lavoro e previdenza** (art. 3 L. 742/1969): i preset di «Nuova scadenza» non applicano la sospensione feriale.
- **Conclusionali e repliche** (art. 189 c.p.c. vigente): 30 e 15 giorni prima dell'udienza, a ritroso; l'art. 190
  resta solo per i procedimenti col rito previgente.
- **Termine lungo dalla pubblicazione** (art. 327 e 133 c.p.c.): la data in calce vale solo con lettura in udienza
  documentata (art. 429 e 281-sexies c.p.c.); altrimenti deposito o comunicazione, con avviso «da verificare».
- **Lavoro notturno** `aggiorna_scadute` con esiti veri; timesheet sui minuti effettivi; piano «Oggi» con le attività
  economiche senza termine perentorio al massimo in P2; note 127-ter senza doppio appuntamento.

## Economia e fatture
- **Proforma** con serie propria «PF-anno/n»; la serie fiscale conta solo fatture e note di credito; alla conversione
  la fattura prende numero e data del giorno (art. 21 D.P.R. 633/1972).
- **Regime dello studio** (`pct/fatturazione_regime.py`): RF19/RF02 senza IVA né ritenuta (art. 1 c. 58 e 67
  L. 190/2014); RF01 con ritenuta del 20% solo se paga un sostituto (Ris. AdE 35/E/2019).
- **Bollo € 2 secondo legge** (art. 13 Tariffa D.P.R. 642/1972, D.M. 17/06/2014) in tutti i punti di creazione,
  esclusioni solo con fonte (Guida AdE 2024); sulla proforma «da applicare in fattura».
- **Contributo unificato**: opposizione a decreto ingiuntivo a metà (art. 13 c. 3), giudice di pace indeterminabile
  € 237, procedimenti art. 473-bis.47 € 98; esente o prenotato a debito non blocca il deposito.
- **Conto economico**: spese liquidate in sentenza lette dall'archivio delle letture (es. € 250 distratte, art. 93
  c.p.c.), «spese compensate» (art. 92), anticipazione forfettaria € 27 (art. 30 D.P.R. 115/2002) da confermare,
  accessori senza IVA nel regime forfetario; fascicolo letto per chiave (1,8 s → 0,2 s).
- **Proforma dalla sentenza**: si prepara dalla sentenza letta; le verifiche sulle ricevute non bloccano più.
- **Script** `scripts/riallinea_proforma_regime_20261108.py` per le proforma salvate con IVA in regime forfetario.

## PEC, udienze e notifiche
- **Note in sostituzione d'udienza** (art. 127-ter c.p.c.) come termine perentorio, con bozza dell'opposizione.
- **Udienze superate** chiuse con traccia solo con PEC certificata ed evento in Comunicazione.xml; altrimenti proposta.
- **Ricevute** che non creano udienze; notifiche L. 53/1994 riconosciute in tutte le forme; termini solo della parte
  assistita.
- **Parti degli atti**: una strada dell'indirizzo («via Pietro Nenni, rappresentata…») non è più il nome della parte
  (discordanze di nome false).

## Depositi telematici
- **Ricevute collegate al deposito** solo per Message-ID/IdMsgMitt (art. 196-sexies disp. att. c.p.c.); mittente letto
  dall'indirizzo effettivo, «Per conto di» solo dal gestore, anomalie e intestazioni ripetute respinte, esiti del
  Ministero solo con il messaggio dell'ufficio. Su decisione dell'avvocato la firma del gestore non si legge.
- **Riesame in sola lettura** dei 30 depositi segnati «consegnati» il 12/10 (`scripts/riesame_stati_depositi_senza_ricevuta.py`).
- **Ricevute anche dall'archivio PEC del software** (`pct/ricevute_deposito_archivio.py`): se la casella non le ha più
  (cancellate per spazio), il controllo dei depositi le cerca in `pec_audit.sqlite` dal deposito più vecchio in attesa
  (al massimo 180 giorni), con gli stessi controlli delle PEC lette via IMAP. Prova sui dati reali in sola lettura:
  le 8 RdAC conservate dei depositi del 12/10 si ritrovano per Message-ID; 0,4 s con gli indici del presidio.

## Archivio delle sentenze (lavoro di acquisizione delle fonti, 08-09/11)

- La lettura delle pagine PDF è serializzata e libera ogni immagine dopo l'uso: più pagine lette insieme non bloccano più il lettore.
- Ogni provvedimento mostra la data di decisione quando manca quella di deposito, con l'etichetta giusta («Deposito» o «Decisione»).
- Atti CeRDEF già conservati in Normattiva consultabili dalla ricerca normativa, in sola lettura dall'indice `IUSENTRA_BIBLIOTECA_CERDEF_INDICE` (`lex/normativa/cerdef_biblioteca.py`).
- Edizione archiviata di Normattiva collegata agli atti CeRDEF, attiva solo se configurati `IUSENTRA_BIBLIOTECA_CERDEF_ARCHIVIO` e `IUSENTRA_BIBLIOTECA_CERDEF_INDICE_ARCHIVIO` (altrimenti non compare).
- Corpus pubblico dei soli provvedimenti ufficiali (Corte costituzionale, giustizia tributaria, Corte di giustizia UE, CEDU, Corte dei conti), in sola lettura da `IUSENTRA_CORPUS_PUBBLICO_DIRECTORY` (`web/services/giurisprudenza_public_corpus.py`), con la richiesta di ricerca separata in `frontend/src/corpusSearchRequest.ts`.

## Lex, ricerca e guide
- Guardia anti-invenzione con «Cass. 22222/2023» e Sezioni Unite; decreti ministeriali aperti per estremi.
- Percorso dopo la sentenza per giurisdizione e grado (civile, lavoro, TAR, tributario, penale); fase «Processo
  estinto» (artt. 181, 307, 310 c.p.c.; appello contro l'ordinanza del giudice monocratico, Cass. 29852/2022).
- 10 schede della guida corrette sul testo vigente; ricorso semplificato art. 281-undecies al posto del 702-bis.
- Profilo «Esecuzione forzata» dal codice oggetto PST ufficiale delle esecuzioni.

## Notizie utili
- 14 fonti ufficiali (Gazzetta Ufficiale, Corte costituzionale tramite GU, EUR-Lex, CGUE, CEDU, Agenzia Entrate,
  INPS, Garante, Ministero della Giustizia, PST, CNF, Cassa Forense, Cassazione), lavoro ogni 30 minuti, rilevanza
  giuridica con comunicati di servizio nascosti, collegamento ai fascicoli dalle norme citate negli atti
  (lettore «Norme citate negli atti»), norme e prassi inoltrate alla revisione degli aggiornamenti legali.

## Sicurezza e permessi
- Clienti e cartelle secondo `clienti.leggi` e condivisioni; archiviazione e riapertura dei fascicoli solo con
  `fascicoli.archivia`; secondo fattore con tentativi contati sul server; deleghe senza escalation di permessi;
  CSV dell'audit protetto dalle formule; backup giornaliero cifrato nel registro; menu filtrato per permessi.

## Velocità
- Presidio del fascicolo: una sola scrittura per apertura e solo del fascicolo (15-18 s → 3 s).

## Test
- Suite complementare (944 file mai eseguiti) eseguita per intero; corretti i test superati dalle regole vigenti.
- Moduli riportati entro i limiti di struttura: presidio (`riepilogo_economico.py`, `inserimento.py`) e rotte di
  gestione dei fascicoli (`web/services/fascicolo_controparte_modulo.py`); prova intermittente sulle scadenze corretta.
