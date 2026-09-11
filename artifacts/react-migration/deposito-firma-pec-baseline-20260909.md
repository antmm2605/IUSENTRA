# Baseline accettata: deposito, firma e PEC locale

Data: 09/09/2026 19:50 (ora italiana).
L’utente conferma: «tutto ha funzionato con esito positivo» e richiede backup e conservazione del comportamento senza ulteriori modifiche.

Caso verificato dall’utente: fascicolo 06928604, documento D2D334E6, Local Signer 1.6.131. Il monitor SQL ha visto il record FD97ADAA INVIATO alle 19:43:32. La conferma dell’utente riguarda il flusso sul PC del cliente; non viene estesa a una verifica locale 8080 mai eseguita o a tutte le altre funzioni dello studio.

Backup dedicato: /opt/iusentra/backups/deposito-accettato-20260909_195010
App attiva: iusentra-app, immagine r105 con sorgenti e distribuzione Local Signer aggiornati senza riavvio. Salvata anche l’immagine r107, che contiene il pacchetto aggiornato. `runtime-app.tar.zst` contiene i file effettivi di /app del container in uso, esclusi soltanto cache Python; `sources.tar.zst` contiene sorgenti Git e WIP del server, `repository.bundle` conserva la storia Git. I due archivi sono distinti perché il lavoro server-first complessivo non è ancora consolidato in un nuovo commit.

`studio.db.zst` è uno snapshot coerente del database SQLite dello studio, creato tramite il metodo nativo backup_structured e verificato con quick_check. `fascicolo-06928604.tar.zst` conserva i documenti fisici del caso. Sono copie di sicurezza, non file da sostituire alla produzione automaticamente. Non è un backup integrale di tutti i documenti e volumi di tutti gli studi; chiavi e configurazione corrente restano nei loro percorsi operativi. Nessuna password PEC o PIN del PC cliente è stata letta o inclusa appositamente.

Conservare questa baseline fuori dalle normali politiche di retention. `SHA256SUMS` verifica i componenti; `source-manifest.json` contiene le impronte per file. Gli archivi finali vengono impostati in sola lettura e con attributo immutabile sul server; seconda copia su disco D: del PC dell’utente. L’immagine esportata può essere ricaricata con Docker senza ricostruire dipendenze. Il ripristino deve essere una procedura esplicitamente autorizzata: verificare prima impronte e manifest, non inviare PEC, non sovrascrivere dati correnti e non avviare copie applicative parallele. Non usare deploy.sh/reset sul WIP del server.

Regola permanente: - **Flusso deposito/firma/PEC congelato il 09/09/2026:** l’utente ha confermato esito positivo sul PC del cliente con Local Signer 1.6.131 e ha richiesto backup e divieto di ulteriori modifiche. Preservare integralmente rilevamento delle firme esistenti, firma aggiuntiva solo su scelta dell’avvocato, firma multipla, classificazione, PDF/PDF-A, busta, abilitazione invio e SMTP esclusivamente dal PC locale, inclusi AUTH UTF-8 e Message-ID IDNA. Non modificare o rifattorizzare questo comportamento durante altri lavori. Prima di toccare qualsiasi file condiviso consultare `artifacts/react-migration/deposito-firma-pec-baseline-20260909.md` e confrontare le impronte del backup accettato. Il divieto resta valido salvo una futura istruzione esplicita dell’utente che lo sostituisca.


Guardrail tecnici esistenti: 18 test Local Signer PEC superati, incluse serializzazione smtplib reale intercettata senza rete, credenziali UTF-8, Message-ID con nome PC accentato e conservazione degli allegati. Questi test non sostituiscono la prova materiale dell’utente.

Il backup e la conservazione di questo flusso sono separati dal lavoro ancora aperto su lettura unica, OCR, altre pagine e riallineamento GitHub/locale. Non modificare il flusso accettato per completare quel lavoro.

## Verifica finale delle copie — 09/09/2026 20:35

Backup sul server: /opt/iusentra/backups/deposito-accettato-20260909_195010.
Seconda copia: D:/legale/backups/IUSENTRA/deposito-accettato-20260909_195010.
Tutte le 12 impronte elencate in SHA256SUMS coincidono sulla copia locale: 8.816.502.699 byte verificati, oltre al manifesto SHA256SUMS. Snapshot SQLite coerente verificato con quick_check; archivi sorgenti e documenti confrontati file per file. Attributo immutabile confermato sui 13 file server, copia locale in sola lettura con accesso limitato all'utente e SYSTEM. La verifica non ha ripristinato dati sopra la produzione e non costituisce prova di ripristino completo su una nuova macchina.
Il monitor del deposito è sospeso dopo la conferma positiva dell'utente. App unica iusentra-app e worker healthy, readiness pubblica positiva. Nessun ulteriore cambiamento funzionale, invio PEC o riavvio server.
Su richiesta esplicita dell'utente, dopo la verifica delle copie viene avviato lo spegnimento del PC locale. Resta aperto il precedente lavoro composto e il consolidamento locale/GitHub; la baseline accettata è conservata integralmente nel backup e non va modificata.
