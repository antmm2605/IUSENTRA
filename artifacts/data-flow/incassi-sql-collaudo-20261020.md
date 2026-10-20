# Incassi SQL — collaudo del 20/10/2026

Stato: aperto. Rilascio candidato 2.442.0, non ancora distribuito su Hetzner.

## Prova sulla copia reale

Browser visibile su `http://127.0.0.1:8080/fatturazione/`, normali comandi dell'interfaccia. Cliente e fascicolo sintetici già esistenti: Presidi Collaudo, COLLAUDO NETTO, R.G. 987654/2026. Nessun pagamento esterno, invio SdI, firma o PEC.

- Creata proforma 2026/008, identificativo `8732f8f3-a191-43b0-be34-e98038129b58`, totale € 1.196,00, usando le opzioni fiscali native.
- Registrato acconto in contanti di € 400,00: incasso parziale, residuo € 796,00, documento ancora proforma in bozza. Chiusura e riapertura del dettaglio conservano il movimento.
- Registrato saldo su conto corrente di € 796,00: incassato € 1.196,00, residuo zero, senza emissione automatica.
- Stornato il saldo con motivazione: incasso originale conservato e movimento contrario separato. Incassato € 400,00, residuo € 796,00. Il filtro Bonifico registrato torna a zero; il metodo previsto nel documento non è una prova di bonifico.
- Richiesta emissione attraverso il comando esplicito nativo. Il canale browser della prima scheda si è bloccato sulla conferma; una nuova scheda autenticata mostra il documento emesso e la medesima cronologia degli incassi. Non è stata ripetuta l'emissione.
- Creata proforma sintetica 2026/009, identificativo `58ceb893-fbb3-4e31-b088-9ea4735a01c3`, totale € 1,20, per verificare la correzione del rientro dopo salvataggio. Il dettaglio mantiene `embed=source`: nessuna seconda navigazione principale nel contenuto della finestra.

I documenti e i movimenti sintetici sono esplicitamente annotati come collaudo. Non cancellare la loro cronologia per simulare assenza di operazioni.

## Difetti individuati e correzioni

Il rientro automatico dalla creazione perdeva la modalità incorporata, inserendo una seconda cornice applicativa nella finestra. Riutilizzato il resolver condiviso delle finestre, con confine di origine e conservazione dell'identificativo. Un collegamento non ammesso lascia esplicito che il salvataggio è avvenuto e l'apertura automatica non è consentita.

Il modulo ripeteva due spiegazioni del calcolo con un grande stato vuoto e dettagli tecnici. Sostituiti da una sola nota compatta in italiano; nessun calcolo fiscale alternativo nel browser.

## Controlli e limiti

- Preparazione SQL esplicita con backup coerenti per tre tenant; impronte dei dati originali concordanti prima e dopo la preparazione.
- Immagine nativa del commit 23c1dcdf47 confrontata con 14.478 file, pacchetti Python e sistema operativo. La successiva correzione visiva è stata applicata alla copia reale per la prova: serve ancora consolidarla nell'immagine immutabile finale.
- Controlli mirati di finestre e comandi incassi: 29 casi superati; build e controllo delle sorgenti pubblicate superati (746 sorgenti, 291 asset); contratti React superati.
- Prima nota e pagina Incassi e pagamenti mostrano gli stessi tre movimenti e il residuo di € 796,00. La bozza non salvata nell'editor è ancora identica: 13 parole, 95 caratteri.
- Nel browser a larghezza tablet verificati campi, totali e comandi; a larghezza mobile verificati apertura del dettaglio dalla pagina Incassi, selezione della scheda e scorrimento della cronologia. Corrette le etichette compresse delle schede con una riga scorrevole e target di almeno 44 pixel. Aggiunto spazio finale al corpo scorrevole per i comandi delle finestre: quest'ultima correzione richiede ancora riscontro nell'immagine finale.
- Durante l'aggiornamento diagnostico degli asset, una riapertura ha mostrato «Pagina non avviata»; il comando visibile Ricarica ha ripristinato pagina e dettaglio, con dati preservati. Il canale non ha conservato errori di console: la causa non è provata. Va ripetuta la navigazione nell'immagine finale, senza pubblicazione parziale dei file.
- Restano immagine finale, verifica dello spazio finale mobile, conferma del fascicolo collegato, CI, push, deploy e pulizia conclusiva.
- Le conferme dei gestori sono provate con risposte controllate e schema delle fonti; non è stato effettuato un pagamento reale presso un gestore. Una data non dimostrata resta tale.
- Nessuna conclusione di copertura dell'intera procedura economica o degli altri incarichi aperti deriva da questo singolo collaudo.
