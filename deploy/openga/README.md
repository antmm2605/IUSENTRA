# Ricerca OpenGA R6

Il motore restituisce una sola lista di dieci rapporti provvedimento-ricorso. Oggetto ed esito sono metadati ufficiali: non dimostrano motivazioni o principi. Il gestionale richiede una sessione utente; il servizio di inferenza rimane nella rete Docker privata, senza porte pubbliche e senza accesso ai volumi degli studi. Nessun download automatico durante le ricerche.

I dati e i pesi si installano in una nuova cartella versionata. `install.py` verifica pacchetto, file, SQLite e conteggi; conserva lo scope originale e lega la sola copia verificata al percorso immutabile `/catalogo/catalogo.db` del contenitore. Gli originali e i tre corpus Consulta del server non vengono sostituiti. Pesi BAAI/bge-reranker-v2-m3, revisione fissata nel manifesto, Apache-2.0; download solo dalla fonte ufficiale, verifica SHA prima del caricamento.

`Dockerfile` contiene esclusivamente il runtime opzionale di ricerca CPU; il runtime bloccato del gestionale resta separato. I pesi e il catalogo sono montati in sola lettura. Il backend invia soltanto domanda, anni, sede e modalità al motore sullo stesso host: niente documenti, cookie o credenziali. Una ricerca per volta; richieste concorrenti ricevono un avviso. In mancanza del classificatore o degli embedding si conserva l'intera lista lessicale con avviso, senza dichiarare attiva la ricerca semantica.

Le 60 domande usate per sviluppare R6 non sono una validazione indipendente: 58/60 top10 contro 50/60 lessicale originale e 53/60 a parità di filtri. Su 30 domande nuove del 2022, congelate prima della prova a motore invariato: 29/30 contro 27/30, zero perdite osservate. A parità di filtri di sede, la lessicale raggiunge 28/30: il riconoscimento della sede viene applicato anche alla modalità rapida, e il contributo aggiuntivo del percorso completo sul campione è di un caso. Campione costruito da schede note e non rappresentativo di ogni domanda dell'avvocato; dopo questa prova è consumato e non va riutilizzato per rivendicare indipendenza di ulteriori modifiche. Tutti i banchi restano esclusi dal training. Tempi GPU e CPU/server sono prove distinte.

Non attivare l'indice Consulta su corpus diversi: va costruito o riconvalidato sulle fonti effettive del server. La funzione resta opt-in. Il catalogo OpenGA nuovo non attribuisce valore di precedente citabile a dati senza testo.

La prova del contenitore CPU (4 core, 6 GiB di limite, runtime bloccato) ha riprodotto 29/30 contro 27/30 originali: massimo osservato circa 65 secondi, non uno SLA del server. La modalità rapida applica gli stessi filtri di sede senza modelli; quella approfondita è esplicita e usa una sola lista.

## Gate ulteriore prima del collegamento al gestionale

Il campione `benchmark-server-30.json` è congelato prima delle ricerche, con SHA nel protocollo e decisioni disgiunte dai 90 casi già esaminati. Usa 30 sedi e decisioni del 2023: è una prova di reperimento di record noti, non una valutazione universale né giuridica.

L'attivazione esegue sul CPX42 le due ricerche con gli stessi filtri e registra la lista unica top 10, tempi a freddo e a caldo, memoria del processo e del contenitore, cache del classificatore e una ripetizione a caldo. Occorrono un vantaggio stretto della lista ibrida, zero perdite lessicali, zero fallback/errori, stesso processo e un solo caricamento del classificatore. In caso contrario il collegamento del gestionale resta invariato e il rapporto va analizzato senza ritoccare attesi o domande. Non si promettono 3 o 10 secondi prima di misurare il server CPU reale.
