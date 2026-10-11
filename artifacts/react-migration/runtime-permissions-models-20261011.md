# Accesso CTU, PAT, PDP e modelli — 11/10/2026

Risultato richiesto: ripristinare sul server le superfici segnalate, conservando i dati e i flussi di firma/invio congelati. L'incarico generale resta aperto.

## Causa materialmente riscontrata

Browser reale produzione, studio Giuseppe Montagnese: CTU rispondeva 503 perché il processo uid 100/gid 101 non poteva leggere il marcatore SQL, creato root con permessi 600. PAT non poteva leggere pat_formweb.json (root 600); il repository workflow.db era root 644 dentro una directory root 755. Stesso difetto di proprietà nei file PDP. Il secondo studio ha lo stesso problema nel registro delle letture. I file erano stati creati quando il runtime o le procedure amministrative operavano come root; non è dimostrato quale singolo comando abbia creato ciascun file.

Il catalogo comune aveva un difetto distinto: il lettore tentava PRAGMA journal_mode=WAL su un database amministrativo protetto. GET /api/editor/modelli-personali falliva 503; una selezione vecchia conservata nella UI non dimostrava disponibilità e il comando di compilazione restava disabilitato.

## Ripristino operativo circoscritto

Ripristinati proprietari uid 100/gid 101 di venti percorsi esplicitamente elencati dei due studi: directory runtime CTU/telematico/penale, marcatori necessari, database e sidecar attivi, archivio PAT e lock, registro delle letture del secondo studio. Nessun chmod globale, scansione documentale, cancellazione, sostituzione di database o ripristino di dati storici. Manifest prima/dopo con permessi e SHA256: /opt/iusentra/backups/runtime-permissions-20261011. Tutte le impronte dei file confrontati sono rimaste uguali durante questa operazione; gli originali e i backup precedenti sono preservati.

Prova materiale produzione dopo la riparazione: PAT mostra undici fascicoli; nel fascicolo amministrativo 1CD1BDCC il pannello presenta procedimento, parte, dieci documenti, dati mancanti e comandi. Nel fascicolo 31344D72 CTU apre Nuovo incarico con campi, date e calcolo assistito; annullato senza registrare un incarico fittizio. PDP apre il riepilogo, ma questo studio non ha fascicoli penali: questa osservazione non prova preparazione, salvataggio o deposito penale completo. Nessun invio o firma eseguito.

## Correzione primaria del catalogo comune

Il repository condiviso è ora aperto esplicitamente in sola lettura: SQLite mode=ro/query_only, senza DDL, mkdir o cambi di journal; PostgreSQL senza inizializzazione schema e con sessione readonly. I repository personali rimangono scrivibili. La pubblicazione amministrativa SQLite usa DELETE, per evitare che il lettore debba creare sidecar WAL nella directory protetta. Non rendere il catalogo comune scrivibile dall'app per mascherare l'errore. Il catalogo già pubblicato richiede backup coerente e normalizzazione del journal prima della prova finale del nuovo lettore sul server.

Dodici guardrail repository/API positivi, inclusa compilazione distinta per due studi con lettore readonly, rifiuto di scritture e impronta/journal immutati dopo la lettura. Ruff positivo. Browser reale 8080 sul candidato: Usa modello carica il catalogo comune senza errore in un nuovo editor del tenant tecnico. Nessun fascicolo selezionabile in quel tenant: questa prova dimostra il caricamento, non una nuova compilazione o salvataggio.

Rilascio 2.437.8 in corso: non ancora verifica definitiva del catalogo in produzione né chiusura della preparazione udienza e dell'incarico generale. Le future migrazioni dei dati tenant devono essere eseguite con l'identità applicativa, verificata nel container, e con controllo dei permessi dei marcatori e delle directory; la pubblicazione amministrativa di piattaforma resta separata e protetta.
