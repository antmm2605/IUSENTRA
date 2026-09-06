# Catalogo PST incompleto: Palmi R.G. 1025/2024

## Prova e diagnosi, 05/09/2026

L'avvocato ha confermato che il click diretto apre il PIN. Il rifiuto di
attivazione Windows osservato durante il controllo a distanza non viene quindi
trattato come un difetto riprodotto con click diretto. Nessuna modifica al
consenso Windows, al provider del certificato o alla firma.

Dopo autenticazione, il pannello reale ha restituito 16 atti principali, da
Citazione del 05/09/2024 a Documento del 09/01/2026, senza allegati. Il precedente
inventario dello studio di 51 documenti non viene usato per simulare la risposta.

La copia installata 1.6.116 del backup positivo del 27/08/2026 è stata verificata:
SHA-256 BAD83867C2D1D580CCD1BDC37611C95DE9155974D791AB6903D6CAA51AB5FBA2,
corrispondente a SHA256SUMS.txt. In quella procedura il pannello richiamava
fascicolo-snapshot-job, il cui percorso completo comprendeva il dettaglio degli
atti. L'attuale chiamata condivisa ricerca-snapshot esclude tale recupero quando
single_interactive_batch è vero: la parità tra due richieste ridotte non prova
la parità con l'inventario completo della baseline.

## Correzione mirata in verifica

Si conserva l'endpoint condiviso da Wizard e Fascicolo d'ufficio, il resolver,
il primo lotto ricerca/profilo/sommario e la gestione del certificato. Dopo il
sommario, lo stesso endpoint recupera i dettagli tramite il servizio ufficiale
estraiMasterDetailAtto già implementato e testato nella procedura precedente.
Gli identificativi provengono esclusivamente dalla risposta appena ricevuta.
Non si aggiungono preflight, scraping HTML, invii, firme o nuovi archivi.

Il recupero dettagli è un lotto autenticato successivo al sommario. Non viene
descritto come un unico processo curl: il numero effettivo di richieste PIN
dipende dal provider e deve essere osservato nella nuova prova reale. I cookie
generati nelle consultazioni odierne sono vuoti; non viene riproposto un
recupero solo-cookie destinato a fallire senza autenticazione.

La risposta distingue quanti atti hanno restituito un dettaglio valido. Un
errore ministeriale non deve diventare conferma della completezza del catalogo.
Resta da accettare materialmente l'elenco completo, gli allegati collegati,
copia/originale, download e parità dei due percorsi sulla copia reale 8080.
Non è una consegna conclusa né una prova positiva della patch.

Fonti tecniche: docs/specs/ministero/PST_FASCICOLO_SCHEDE_MINISTERIALI_2026-05-29.md;
WSDL ministeriale A1 v1.52, SICID/BEAFascicoloInformatico-distr.wsdl, operazione
estraiMasterDetailAtto, campi docPrimario e docsSecondari; baseline certificato
PST_LOCAL_SIGNER_BASELINE_CERTIFICATO.md. Nessuna nuova regola normativa.

## Aggiornamento: acquisizione e prova PIN ancora aperte

Il 05/09/2026 il confronto dei log ha distinto due operazioni: recupero del
catalogo (16 atti principali e 35 allegati) e download di dieci PDF sul PC.
Nel corrispondente intervallo non è stata osservata la richiesta di importazione
nel fascicolo sul server. La sola presenza di 51 riferimenti non prova quindi
una nuova acquisizione dei contenuti.

La verifica SQL, fonte operativa del tenant, ha individuato le dieci registrazioni
nel fascicolo corretto `0D4A4802`, ma i file conservati non hanno le impronte dei
PDF scaricati oggi. La differenza copia PDF/originale storico non dimostra da sola
corruzione. Il file storico `Documento_33584995.pdf.p7m`, di 256 byte, richiede
invece un controllo del contenuto e della catena di versioni prima di poterlo
considerare acquisito correttamente. Non è stato cancellato o sostituito.

La diagnosi del codice ha identificato due controlli da correggere insieme:
`OfficeDocumentsPanel` esclude dall'importazione gli elementi riconosciuti per
identificativo come già acquisiti; `_importa_documenti_portale_items` riusa il
record corrispondente senza confrontare il nuovo contenuto con il file fisico.
La correzione di persistenza e la prova reale restano da eseguire.

Su richiesta dell'utente, l'ordine corrente di rilascio è locale reale 8080,
quindi produzione e prova anche del wizard. È stata agganciata la scheda
autenticata nel browser integrato Codex su produzione e osservata la pagina del
fascicolo, compreso il pulsante `Visualizza fascicolo`. Non è stato avviato un
nuovo accesso PST né inserito il PIN: le regole obbligatorie della skill Computer
Use non consentono l'automazione delle finestre di autenticazione. Il passaggio
PIN necessita intervento dell'utente; non viene sostituito con comandi nativi o
modifiche alle protezioni Windows. Nessuna firma o trasmissione eseguita.

Stato: lavoro aperto; acquisizione aggiornata nel fascicolo, catalogazione,
nuova release dell'aggiornamento automatico e stampa non sono accettate con
questa verifica di sola lettura della pagina.

## Riscontro dopo il PIN inserito dall’utente — 05/09/2026

Verificata materialmente la scheda autenticata del browser integrato Codex,
in produzione, fascicolo `0D4A4802`, dopo l’operazione eseguita dall’utente.
Il pannello Fascicolo d’ufficio mostra Tribunale di Palmi, R.G. 1025/2024,
51 documenti selezionabili: 16 atti principali e 35 allegati. Sono nuovamente
presenti, fra gli altri, procura, contratto preliminare, ricevuta CU, visure
catastali e verbale di esito negativo della mediazione.

Prova UI senza trasferimenti: cliccato `Seleziona tutto`, osservati 51
selezionati e `Scarica 51` abilitato; `Acquisisci nuovi` resta disabilitato.
Cliccato quindi `Deseleziona tutto` e verificato il ritorno a zero selezionati.
Nessun nuovo download, importazione, firma o accesso PST avviato da Codex.
Osservati mediante schermata reale anche gli allegati e il fondo del pannello.

La dicitura `51 già acquisiti` non dimostra l’aggiornamento dei file fisici:
nella stessa pagina restano visibili il documento storico da 256 byte e
l’indice Lex del 25/06/2026 22:03. Il log Local Signer dell’operazione delle
17:08:36 (ora italiana) riporta 16 richieste di dettaglio, 35 allegati e un
documento senza dettaglio utile. Pertanto il conteggio visualizzato è
confermato, ma non viene certificata la completezza di tutti i dettagli
ministeriali né una nuova acquisizione dei contenuti sul server.

Questa è una verifica della produzione sulla macchina reale, non una nuova
accettazione locale su 127.0.0.1:8080. Nessun codice applicativo, dato del
fascicolo o pacchetto Local Signer modificato per questo riscontro. Il lavoro
complessivo resta aperto.
