# Sincronizzazione live — incarico aperto

Perimetro: tutto IUSENTRA, menu e sottomenu, procedure, funzioni e task; aree di lavoro, editor, lettore e acquisizione documenti inclusi.

## Prova realmente eseguita in produzione

08/10/2026, circa 17:42, browser reale visibile. Fascicolo C3565650 e scheda cliente E9D48E57, senza cambio di identità o documento.

1. Aperta la cartella cliente nel fascicolo mediante «Visualizza cliente nel fascicolo».
2. Cliccata «Modifica anagrafica»: seconda area di lavoro aperta nel medesimo contesto.
3. Nella scheda autonoma, modificata soltanto la grafia dell'ente da «Comune di Vicenza» a «Comune di VICENZA» e cliccato «Salva modifiche».
4. Osservato «Modifiche salvate». Nell'area di lavoro già aperta, il campo è passato automaticamente a «Comune di VICENZA», senza ricaricamento manuale.
5. Nell'area di lavoro, ripristinata «Comune di Vicenza» e cliccato «Salva modifiche». Osservati caricamento e «Modifiche salvate».
6. La scheda autonoma già aperta ha mostrato automaticamente la grafia originale ripristinata.

Immagine: `live-sync-anagrafica-server-20261008.png`. Nessuna firma, invio o modifica di dati fiscali eseguita. La bozza locale non è stata confusa con il salvataggio SQL.

Il nuovo segnale legge soltanto piccoli contatori SQL del tenant: i riscontri server di questa prova sono richieste da 165 byte, circa 13–22 ms. Il controllo ha intervallo di due secondi: non equivale a una connessione push istantanea. I contatori precedentemente in memoria non erano condivisi tra processi.

## Difetti trovati e interventi ancora da accettare

- Il modulo soggetto azzerava i campi non salvati quando arrivava un aggiornamento. Applicata localmente la stessa fusione a tre versioni del cliente, con confronto esplicito dei conflitti; prova reale e pubblicazione ancora da eseguire.
- La pagina PEC ascolta solo aggiornamenti provenienti da altre viste: il segnale SQL deve dichiarare la provenienza remota anche nella radice. Correttivo locale scritto, non ancora accettato nel browser.
- Richiesta live senza limite temporale: aggiunto limite di dieci secondi e ripresa governata; prova reale dell'interruzione ancora da eseguire.
- Permesso privacy inesistente: riallineato localmente al permesso nativo `utenti.leggi` del registro trattamenti; isolamento e prova autorizzazioni ancora da eseguire.
- Il caricamento automatico può ancora nascondere errori tramite alcuni loader: occorre correggere la gestione primaria e renderne osservabile l'esito.
- Il manager clienti sostituiva l'intera tabella durante ogni salvataggio. Corretto il percorso SQL nativo: scrive soltanto le righe effettivamente modificate, confronta la versione SQL letta dal manager prima della scrittura e respinge esplicitamente un aggiornamento concorrente obsoleto. Nessuna cancellazione e reinserimento delle altre schede. Correzione installata sul server con backup e ricaricamento dei worker, senza riavvio del container applicativo.
- Ripetuta materialmente la prova di variazione della sola grafia dell'ente rilasciante e ripristino della grafia originale: salvataggio e propagazione osservati nelle viste reali. Tre guardrail SQLite positivi: aggiornamenti di clienti distinti conservati; conflitto sul medesimo cliente respinto senza avanzamento del contatore; collegamento al fascicolo preservato e una sola invalidazione di riga.
- Restano da estendere le scritture puntuali agli altri manager, verificare PostgreSQL e garantire anche la versione vista dal browser e l'atomicità dell'intero modulo: il controllo SQL del manager non sostituisce questi requisiti. Non dichiarare ancora accettata la concorrenza globale multiutente.

## Copertura non ancora accettata

Inventario statico: `live-sync-surface-inventory-20261008.json`, esteso dai 122 nomi iniziali a tutti i 497 componenti TSX sotto `frontend/src`, incluse le implementazioni nelle feature e i wrapper; 466 dichiarazioni di tabelle includendo le migrazioni SQL native e 43 chiamate di scrittura tabella da ricostruire. È un censimento di codice, non un elenco di flussi accettati o di sole pagine operative. Ogni riga resta non verificata finché non ha percorso fonte → scrittura SQL → segnale → API → vista e prova materiale. Mancano ancora copertura completa dei repository modulari, email, impostazioni, stati dei job, documenti/editor, lettori e funzioni amministrative; controlli PostgreSQL, tenant/RBAC, concorrenza, connessione interrotta e conservazione delle bozze; copia reale 8080, consolidamento dei due branch e deploy finale sul medesimo commit.

## Riscontro dell'elenco moduli inviato dall'utente

Fonte fornita: riepilogo dei 78 mirror del 08/10/2026 17:58. Aperta personalmente la pagina reale `/admin/database`, che conferma gli stessi stati. La fonte SQL operativa dichiarata è `/data/tenants/studio-legale-giuseppe-montagnese/studio.db`.

Riscontro puntuale con connessione SQLite `mode=ro` e `query_only=ON`, senza lettura dei documenti né modifiche: clienti 267, fascicoli 335, CRM 0, verifiche antiriciclaggio 0, righe `fascicolo_documenti_ai` 111.804, atti `fascicolo_editor_ai_atti` 1, righe caselle email 5.014. I contatori sono righe SQL, non attestazioni di correttezza del contenuto, numero di documenti originali o accettazione funzionale.

La pagina mostrava 265 clienti nel mirror, e «Non trovato» per i mirror Documenti AI ed Editor AI: questo non dimostra l'assenza delle rispettive tabelle SQL. Aggiunta al candidato una colonna separata per il repository operativo, usando le statistiche SQL native già raccolte, preservando il vero stato del mirror. Per moduli senza corrispondenza provata resta un messaggio esplicito di verifica; nessun avviso nascosto e nessuna ricostruzione cieca dei JSON. Pubblicazione e prova materiale del candidato in corso. Prima nota e azioni workflow richiedono ancora ricostruzione della fonte nativa, non creazione di file vuoti per togliere l'avviso.

I guardrail tecnici positivi non chiudono l'incarico. Nessuna dichiarazione di sincronizzazione globale completata.

## Prova materiale Database, 18:27–18:30

Server: ricerca Clienti, visti 267 record SQL e 265 nel mirror, tutte le colonne leggibili. Il preset della rail sovrascriveva la prima regola; corretto il selettore effettivo e il minimo di altezza che lasciava grandi vuoti nei risultati filtrati. Locale reale 8080 aggiornato con backup delle sorgenti e del manifest, HUP e app healthy/API pronto 2.436.12: ricerca Clienti mostra 26 SQL contro 24 nel mirror del tenant locale. Tab porta al filtro Stato; scroll fino al fondo mostra Analisi uso e Accessi collegati. Screenshot server e locale salvati. Nessun comando di riparazione, migrazione o ottimizzazione avviato per questa prova. Hover e responsive non verificati.

Audit JSON: vedere direct-json-storage-review-20261008.md. La corrispondenza SQL dei singoli moduli resta da completare: non assumere che tutti i JSON siano mirror soltanto perché il profilo studio è SQL.
