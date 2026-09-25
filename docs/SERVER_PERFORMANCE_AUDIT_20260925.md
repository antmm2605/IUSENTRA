# Audit prestazioni e resilienza server — 25/09/2026

## Stato del lavoro

Questo documento fotografa le verifiche eseguite sul nodo Hetzner CPX42 e le
modifiche predisposte localmente. Su richiesta dell'utente, **commit, push e
deploy sono stati sospesi** fino al via libera esplicito alla release, ricevuto
il 25/09/2026. La versione di rilascio è la 2.401.3, successiva alla 2.401.2
già creata dall'utente.

Il flusso deposito, firma e PEC congelato il 09/09/2026 non è stato modificato.

## Risultati misurati

- Host: 8 vCPU AMD EPYC, circa 15 GiB RAM, circa 5,8 GiB disponibili durante
  il controllo, carico medio inferiore a 2 e assenza di pressione I/O.
- Disco: 301 GiB totali, 76 GiB liberi dopo la pulizia, utilizzo al 75%.
- Swap: non configurata. Non è un collo di bottiglia corrente, ma resta un
  rischio di resilienza per picchi simultanei di app, scheduler e AI locale.
- Applicazione: quattro worker web; il servizio è healthy e `/api/pronto`
  risponde in pochi millisecondi dal nodo.
- AI locale: `qwen3:4b` usa circa 4,5 GiB di RAM con contesto 8192; CPU quasi
  inattiva fuori dalle richieste. Sono installati anche `gemma3:1b`,
  `minicpm-v4.6:1b` ed `embeddinggemma:300m`.
- Database di ricerca globale: circa 1,15 GiB e 14.801 righe indicizzate.

## Collo di bottiglia corretto

La ricerca della barra superiore impiegava diversi secondi perché ogni
richiesta:

1. inizializzava tutti i repository applicativi dello studio;
2. rieseguiva il DDL SQLite e FTS anche su un indice già pronto.

Le modifiche predisposte fanno interrogare direttamente l'indice quando è
popolato e verificano lo schema con `sqlite_master`, eseguendo il DDL soltanto
se manca davvero un oggetto.

La stessa correzione è stata applicata temporaneamente al solo codice del
container di produzione, senza modificare volumi o dati. Sul database reale,
dieci ricerche consecutive hanno registrato:

- mediana: 295,9 ms;
- massimo osservato: 300,8 ms;
- risultato: 20 righe;
- miglioramento: oltre 20 volte rispetto ai circa 6,8 secondi misurati prima
  della seconda correzione.

La patch nel container è temporanea e verrà sostituita dalla release
versionata dopo il via libera al deploy.

## Presidio OCR riallineato

La metrica interna segnalava 29 job OCR falliti. La causa è stata verificata
sulla fonte SQL:

- 28 job legacy erano privi del proprietario tenant, ma il documento corrente,
  il registro delle letture e la cache consentivano una riconciliazione certa;
- 1 job era un artefatto sintetico di test con percorso `x`, hash `nuovo`,
  percorsi temporanei pytest e nessuna corrispondenza in un fascicolo reale.

È stata applicata la procedura tenant-aware già presente nel prodotto, con
backup SQLite preventivo, verifica delle impronte e audit. Il record sintetico
è stato conservato e marcato come superato con evidenza auditata, non
cancellato. Stato finale:

- 484 completati;
- 26 riconciliati;
- 3 superati;
- 0 falliti e 0 in coda;
- 29 righe di audit di riconciliazione;
- `PRAGMA quick_check`: `ok`;
- metriche live: `iusentra_health_status 1`, `iusentra_alerts_total 0`.

È inoltre predisposta una correzione a `core/metrics.py`: il formato Prometheus
legge ora le chiavi reali `in_coda` ed `errori`, mantenendo gli alias inglesi.

## Spazio e backup

Sono stati conservati esclusivamente:

- ultimo backup strutturato verificato:
  `iusentra-structured-20260925_072848_881584`, circa 14 GiB;
- backup del deposito accettato:
  `deposito-accettato-20260909_195010`, circa 8,3 GiB.

Le vecchie immagini IUSENTRA, le cache di build rigenerabili e gli snapshot
temporanei non operativi sono stati rimossi senza toccare volumi, database,
documenti, PEC o dati tenant. Lo script di backup strutturato mantiene già una
sola istantanea tramite `--retention-count 1`.

## Configurazione predisposta, non ancora distribuita

- Driver log Docker `local` con rotazione a 10 MiB e tre file per servizio.
- Caddy aggiornato da 2.8 a 2.11.4 e blocco pubblico di `/metrics`; Prometheus
  continua a interrogare direttamente il servizio applicativo sulla rete
  Docker.
- Servizi WORM e PostgreSQL audit su rete Docker interna; app e worker
  mantengono l'accesso necessario tramite doppia rete.
- Ollama senza funzioni cloud, massimo due modelli residenti, una generazione
  parallela, coda massima 32 e contesto 8192. Due modelli evitano il reload tra
  assistente interattivo e catalogazione, mentre la singola generazione evita
  picchi di memoria.
- Asset statici instradati da Caddy verso un processo separato dai worker
  Gunicorn. Il processo usa la stessa immagine immutabile dell'app, gira come
  utente non privilegiato con filesystem in sola lettura ed è verificato da
  healthcheck; una build fallita non può mescolare frontend nuovo e backend
  precedente.
- Configurazione Compose validata con tutti i profili attivi.

## Rischi e interventi di manutenzione

1. Il kernel installato è precedente al candidato disponibile e il sistema
   segnala un riavvio richiesto. Aggiornamento e riavvio vanno eseguiti soltanto
   in una finestra concordata, mai durante l'operatività dello studio.
2. Docker Engine e Compose hanno aggiornamenti disponibili. Vanno aggiornati
   con verifica preventiva e successivo controllo di tutti i container.
3. Non è presente swap. È opportuno predisporre una swap file limitata e con
   bassa `vm.swappiness` come protezione da picchi, senza considerarla RAM
   aggiuntiva per il dimensionamento ordinario.
4. MinIO OSS installato appartiene alla linea finale archiviata e ricade
   nell'avviso GHSA-hv4r-mvr4-25vw. Non è esposto tramite porte host; la rete
   interna predisposta riduce ulteriormente la superficie, ma non sostituisce
   una decisione sul runtime WORM supportato e una prova di ripristino.
5. Il journal di sistema occupa circa 2,5 GiB. Va impostata una retention
   esplicita dopo aver verificato il periodo probatorio richiesto dai log.
6. Alcune API parziali del fascicolo costruiscono ancora sezioni non richieste.
   Il miglioramento deve avvenire con test di parità perché lo stesso builder
   condivide dati con il flusso deposito congelato.

## Fonti tecniche

- Docker, configurazione driver di log:
  https://docs.docker.com/engine/logging/configure/
- Docker, driver `local` e rotazione:
  https://docs.docker.com/engine/logging/drivers/local/
- Caddy 2.11.4:
  https://github.com/caddyserver/caddy/releases/tag/v2.11.4
- Ollama, parametri di concorrenza e modelli caricati:
  https://docs.ollama.com/faq
- Avviso MinIO GHSA-hv4r-mvr4-25vw:
  https://github.com/minio/minio/security/advisories/GHSA-hv4r-mvr4-25vw
- Hetzner, backup e volumi:
  https://docs.hetzner.com/cloud/servers/backups-snapshots/overview/

## Gate prima della chiusura

Dopo il via libera dell'utente occorrono ancora: test completi, prova reale sulla copia locale
`127.0.0.1:8080`, commit e push dei branch gemelli, gate GitHub verdi, deploy
Hetzner, pulizia immagini, verifica di un solo container applicativo
`iusentra-app`, controllo di `/api/pronto`, metriche non pubbliche e prova
visibile delle prestazioni.
