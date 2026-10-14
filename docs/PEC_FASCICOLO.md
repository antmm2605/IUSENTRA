# PEC del fascicolo

La vista usa l'identificativo del fascicolo e i collegamenti SQL persistiti dal presidio PEC. Il solo numero R.G. nel testo non attribuisce un messaggio alla pratica. Il tenant corrente e il permesso di lettura del fascicolo vengono verificati prima di mostrare i dati.

Il comando nel fascicolo e nel pannello rapido apre tutte le cartelle. Cambiando tra ricevute, inviate e cestino, cercando nel contenuto o passando a un'altra pagina, il filtro della pratica resta attivo. Conteggi e selezioni usano lo stesso perimetro; la consultazione non scrive nuovi collegamenti né modifica messaggi, decisioni o depositi.

Le PEC del registro che non hanno una copia nella casella conservano la cartella realmente registrata. La lettura attraversa tutte le pagine SQL della pratica, anche oltre duecento messaggi. Un errore del registro nel percorso del fascicolo non viene trasformato in una casella vuota.

Gli EML importati e conservati tra i documenti del fascicolo restano accessibili in un elenco richiudibile, con apertura nel lettore interno condiviso. La loro presenza nel catalogo documentale non inventa una cartella IMAP, una nuova associazione automatica o una prova di pagamento. Il file originale resta preservato; Atto.enc non viene decifrato dalla vista.

## Stato del collaudo

Candidata 2.437.27 in preparazione. Guardrail su registri controllati, cartelle, conteggi, paginazione oltre duecento messaggi, tenant, permessi e selezione SQLite/PostgreSQL positivi. Il confronto del codice dimostra che nel repository PEC è cambiata soltanto la query di consultazione dei messaggi; i metodi di deposito, firma e SMTP sono preservati.

Prova materiale sulla copia Docker reale 127.0.0.1:8080: il comando nel fascicolo controllato apre la finestra della pratica; ricevute, inviate e cestino mostrano un messaggio ciascuna e tre in totale. Ricerca e cambi cartella conservano il fascicolo. I tre originali EML sono nell'elenco richiudibile; l'originale inviato si apre nel lettore interno con grassetto e accenti, senza l'istruzione XML spuria nel corpo. Provati scorrimento, chiusura, riapertura e contenuto a larghezze effettive di 771 e 389 pixel: nessun overflow orizzontale; nella vista stretta la lettura si apre con ritorno all'elenco. Corretti il singolare «1 messaggio» e il contesto nel collegamento «Apri cartella».

I messaggi sono fixture esplicite, senza trasmissione reale né prova di associazione automatica. La ripetizione conserva gli stessi tre identificativi di messaggio e documento; i quattro documenti precedenti restano presenti. Backup coerenti delle due basi SQLite effettive del tenant conservati fuori Git. La query della pratica usa l'indice esistente e ha letto due righe in 0,008 secondi; la vista non consulta preliminarmente gli header di tutte le PEC estranee. Le richieste UI osservate conservano stati di caricamento e risposta senza errori; i tempi complessivi variano con le lavorazioni locali concorrenti.

Durante la preparazione delle fixture sono emerse contese SQLite nelle scritture: il processo scheduler manteneva letture sul medesimo registro. Dopo il riallineamento locale la ripetizione è riuscita; questo non dimostra la rimozione della causa del precedente blocco. La diagnosi della concorrenza del servizio resta un punto esplicito dell'incarico generale, con tracce esterne conservate.

Provato anche il caso negativo nel browser reale: una pratica inesistente mostra «Fascicolo non trovato» e indicatori non disponibili, senza conteggi zero fittizi. Corretto e riprovato il titolo di stato, che ora mostra «Fascicolo non disponibile» dopo l'errore, anziché mantenere un caricamento già terminato. Il deploy della prima candidata è stato annullato per includere questa correzione; i controlli remoti e il deploy devono riferirsi al commit successivo.

CI e deploy della candidata restano da concludere. Il collaudo descritto non chiude l'incarico generale.
