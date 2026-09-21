# Copia della versione corretta del server — 21/09/2026

Riferimento vincolante confermato dall'utente: il codice effettivamente in esecuzione
sul server. Ritirata la precedente proposta di sostituire sei file con la copia locale.
Non sono ammesse eccezioni basate su un elenco di impronte per sostituire gli hotfix:
il controllo confronta la release con i sorgenti e gli asset effettivi del server.

Esportazione da `iusentra-app`, senza volumi o credenziali:
`/opt/iusentra/backups/codice-pre-deploy-20260921_194245/runtime-progetto.tar.gz`.
SHA-256: `686d14a54da70690553ed40440c2cbfa354ff2f3b00f7bb6ea5a07acb225f247`.
Copia locale e manifest in `D:/legale/backups/IUSENTRA/codice-pre-deploy-20260921_194245`.
Il backup della copia locale precedente è `locale-prima-copia-server.tar.gz`.

Verificati 4.644 file esportati. Copiati i sorgenti in uso e tutti i 547 asset React.
I 284 asset locali assenti dal server sono stati prima archiviati e poi rimossi dal
bundle locale, evitando un insieme misto. Le sole differenze aggiunte alla copia
server riguardano versione di rilascio, documentazione e protezioni del deploy.
Non sono state introdotte modifiche funzionali al codice del server.

Il Dockerfile distribuisce i bundle React e CSS copiati dal server, senza sostituirli
con compilazioni differenti. Gli stage di compilazione restano disponibili come
controllo tecnico; per future modifiche UI il bundle va compilato e provato prima del
commit. Il deploy confronta anche gli asset modificati nel container con quelli Git.

I due deploy precedenti sono stati annullati. Il percorso di rilascio è unico,
protetto da lock, controllo del branch, discendenza dei commit e verifica del runtime
prima e dopo la build. Nessun reset distruttivo, cancellazione dati o riparazione
massiva è prevista. Il codice dello script occasionale di riconciliazione viene
conservato come sul server e non viene eseguito dal deploy.

Verifiche mirate: 37 test deploy/CI/packaging/retention superati; Ruff e compilazione Python
superati. Il confronto SHA-256 locale con il manifest del server non rileva differenze
funzionali (esclusi i soli file metadata e harness documentati).

Build locale senza cache eseguita; app, scheduler e OCR healthy sulla porta 8080.
Verificate le impronte di 4.639 file funzionali anche nel container locale: nessuna
differenza rispetto al server. Nel browser reale sono stati aperti il documento
importato e Panoramica, con click di navigazione e scroll; nessuna firma o PEC inviata.
Questa prova riguarda il riallineamento e non certifica nuovamente tutte le funzioni.

Stato della chiusura: commit/push, CI e deploy da verificare.

La verifica preventiva ha recuperato anche `pct/scheduler_health.py` dal worker
server: conteneva la gestione delle pianificazioni sospese e la chiusura delle
connessioni SQLite, assenti nella copia del container web. Il file è copiato
integralmente dal worker, senza riscritture; entrambe le versioni sono nel backup.
Il test mirato `test_scheduler_health_schedule_state.py` è superato (1 test).

I test successivi al codice server sono riallineati al comportamento richiesto:
identificativo QuickOrganizer storico conservato, riferimento PST nel proprio
campo; PDF esterno in sola consultazione con azione di anteprima nativa.
Restano attivi tutti i controlli su identità, permessi e anteprima. Nessun cambio
funzionale è stato introdotto per soddisfare aspettative dei test locali.
