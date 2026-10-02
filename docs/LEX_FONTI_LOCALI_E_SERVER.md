# Normattiva completo: preparazione sul PC e caricamento sul server

Procedura per scaricare l'archivio Normattiva completo sul PC (Ubuntu in WSL2, GPU RTX 3060, Ollama locale con
`embeddinggemma:300m`), costruire l'indice di ricerca (FTS5 + vettori), impacchettare tutto e caricarlo sul
server di produzione (Hetzner, Docker Compose, dati in `/opt/iusentra/data`). Da quel momento l'aggiornamento
notturno del server prosegue in modo incrementale.

Il PC usa lo **stesso codice del server**: `tools/normattiva_multi_sync.py` (download), `lex/normativa/normattiva_importer.py`
(import), `lex/ricerca_giuridica/` (indice FTS e vettoriale). Cambia solo l'orchestrazione, in
`scripts/lex_normattiva_locale.py`.

## Cosa e' misurato e cosa e' stima

| Dato | Stato |
| --- | --- |
| 189.851 documenti, 800.757 articoli, 639.273 chunk (16/05/2026, 19 ZIP validi su 23 collezioni) | misurato, `docs/CENTRO_FONTI_UFFICIALI_LEX.md` |
| Indice vettoriale: 639.273 x 768 byte (int8) + 20 byte per riga = circa 0,5 GiB | calcolo dal formato (`lex/ricerca_giuridica/indice_vettoriale.py`) |
| ZIP scaricati 1-3 GiB, database SQLite con FTS 3-6 GiB, JSONL circa 1 GiB, pacchetto compresso 2-4 GiB | **stima**, non misurata: dopo il primo giro leggere i valori reali con `du -sh` |
| Download: 20-60 minuti (pausa di 1 s tra le collezioni, dipende dalla rete e dal servizio) | **stima** |
| Import + FTS: 30-90 minuti | **stima** |
| Vettori su RTX 3060: da 2 a 8 ore | **stima**: `vettori --stima` misura la velocita' reale sui tuoi chunk e calcola il tempo |
| Copia sul server: pacchetto / banda di upload | dipende dalla linea |

Spazio libero consigliato in WSL: almeno 25 GiB (ZIP + database + pacchetto). Verificare con `df -h ~`.
Ogni comando controlla lo spazio prima di iniziare.

## Parte 1 - Sul PC (WSL)

### 1.0 Preparazione, una volta sola

```bash
sudo apt update && sudo apt install -y python3-venv zstd git
cd ~ && git clone https://github.com/antmm2605/IUSENTRA.git iusentra   # se non l'hai gia' clonato
cd ~/iusentra && git pull                                               # serve la versione 2.436.0 o successiva
python3 -m venv ~/venv-lex && source ~/venv-lex/bin/activate
pip install lxml requests numpy
ollama pull embeddinggemma:300m                                         # Ollama deve essere acceso (da Windows o da WSL)
```

Se Ollama gira su Windows e non e' raggiungibile da WSL a `127.0.0.1:11434`, indicare l'indirizzo:
`export LEX_EMBED_URL=http://IP_DI_WINDOWS:11434` (nelle impostazioni di Ollama `OLLAMA_HOST=0.0.0.0`).

Tutti i comandi seguenti si lanciano da `~/iusentra` con l'ambiente attivo (`source ~/venv-lex/bin/activate`).
I dati finiscono in `~/iusentra-lex-fonti/` (cambiabile con `--base CARTELLA` o `IUSENTRA_LEX_LOCALE_DIR`).
**Tenere la cartella dati dentro il filesystem Linux (`~`), non in `/mnt/c`**: SQLite e' molto piu' lento su `/mnt/c`.

### 1.1 Scarica

```bash
python scripts/lex_normattiva_locale.py scarica
```

- Scarica **tutte** le collezioni dell'elenco ufficiale (`--download-all-from-api`), vigenza ORIGINALE come il server.
  `--insieme core` scarica solo le 14 collezioni del download notturno.
- Stessi endpoint del server (`api.normattiva.it`, collezioni preconfezionate XML).
- Ripresa: se si interrompe, rilanciare lo stesso comando; le collezioni gia' scaricate e invariate sono saltate.
- Integrita': per ogni ZIP controlla esistenza, dimensione, SHA-256 del manifest e lettura completa dell'archivio;
  gli ZIP danneggiati vengono eliminati e riscaricati (fino a 3 tentativi).
- Il servizio espone 4 collezioni (`Testi Unici`, `Regolamenti ministeriali`, `Regolamenti governativi`,
  `Regolamenti di delegificazione`) che al 16/05/2026 restituivano un flusso vuoto: se compaiono tra le "collezioni senza ZIP"
  e' lo stesso comportamento gia' osservato sul server.

### 1.2 Importa

```bash
python scripts/lex_normattiva_locale.py importa
```

Importa gli ZIP con il nuovo importer (articoli con chiave univoca: si puo' rilanciare senza duplicare) e popola l'indice FTS5.
`--controllo-integrita` esegue anche `PRAGMA integrity_check`; `--ricostruisci-fts` rifa' l'indice FTS da zero.

### 1.3 Vettori

```bash
python scripts/lex_normattiva_locale.py vettori --stima     # misura la velocita' e stampa i tempi, non costruisce
python scripts/lex_normattiva_locale.py vettori             # costruisce (o riprende) l'indice
python scripts/lex_normattiva_locale.py vettori --url http://127.0.0.1:11434,http://127.0.0.1:11435 --paralleli 4
                                                            # piu' istanze Ollama a turno (vedi sotto)
```

Misura su RTX 3060 (ottobre 2026): con `embeddinggemma:300m` la velocita' resta circa 40 chunk/s sia con
`OLLAMA_NUM_PARALLEL` 1 sia con 4 o 6, con la GPU al 50-70%: una singola istanza Ollama non parallelizza gli embedding. Per la costruzione iniziale si possono avviare altre istanze
`ollama serve` su porte diverse con la stessa cartella dei modelli e passarle tutte a `--url` separate da virgola:
le richieste vengono distribuite a turno. Prima di iniziare si controlla che tutte le istanze abbiano lo stesso
digest del modello, altrimenti la costruzione si ferma (non si mescolano vettori di pesi diversi).

- Il checkpoint e' automatico: dopo ogni blocco di 32 chunk l'indice su disco e' valido. Ctrl-C ferma, lo stesso comando riprende.
- `--massimo 100000` costruisce a tappe (utile per spezzare le ore di lavoro).
- Il modello e' `LEX_EMBED_MODEL` (default `embeddinggemma:300m`) e viene registrato nell'indice con la versione dei pesi.
  **Il server deve usare lo stesso modello**: se diverso l'indice viene ignorato con un avviso, la ricerca resta lessicale.
- Lasciare lavorare la GPU: durante la costruzione evitare altri carichi pesanti (giochi, altri modelli in Ollama).

### 1.4 Verifica

```bash
python scripts/lex_normattiva_locale.py verifica
```

Stampa conteggi (documenti, articoli, chunk, chunk nell'indice FTS), data dell'ultimo import e dell'atto piu' recente,
copertura dell'indice vettoriale e tre ricerche: "art. 2043 c.c." (deve restituire l'art. 2043), "presupposti responsabilita'
extracontrattuale", "termine per proporre appello". Esito `OK` solo se FTS e vettori coprono tutti i chunk e le ricerche rispondono.
Con Ollama acceso la ricerca e' ibrida; senza, lessicale (indicato nella riga di ogni ricerca).

### 1.5 Pacchetto

```bash
python scripts/lex_normattiva_locale.py pacchetto
ls -lh ~/iusentra-lex-fonti/pacchetti/
```

Crea `lex-fonti-AAAAMMGG-HHMM.tar.zst` e `lex-fonti-AAAAMMGG-HHMM.tar.zst.sha256` con: database SQLite (con indice FTS), indice
vettoriale, `PACCHETTO.json` (conteggi, modello, data, dimensioni) e `SHA256SUMS` interno. Poi rilegge il pacchetto e ricontrolla tutti i checksum.
Rifiuta di impacchettare un indice vettoriale assente o incompleto (`--senza-vettori`, `--consenti-parziale` per forzare).
Il JSONL dei chunk non e' incluso (il server lo rigenera a ogni import notturno): `--con-jsonl` per aggiungerlo.

## Parte 2 - Sul server

### 2.0 Prerequisiti (una volta sola)

1. Il server deve gia' girare con la versione **2.436.0 o successiva** (importer con upsert, indice FTS, aggiornamento notturno dei vettori):
   `sudo /opt/iusentra/repo/deploy/hetzner/deploy.sh` come di consueto.
2. `zstd` e `python3` installati: `sudo apt install -y zstd python3`.
3. Il modello degli embedding serve anche **sul server**, per trasformare in vettore la domanda dell'avvocato:
   `cd /opt/iusentra/repo && docker compose --env-file /opt/iusentra/.env.hetzner -f deploy/hetzner/docker-compose.hetzner.yml exec ollama ollama pull embeddinggemma:300m`
   (richiede il profilo `ai`). Senza, la ricerca sul server resta lessicale (FTS) e funziona comunque.
4. In `.env.hetzner`: `LEX_EMBED_MODEL=embeddinggemma:300m` (default gia' uguale; vedi `env.hetzner.example`).

### 2.1 Copia dal PC (da WSL)

```bash
ssh UTENTE@SERVER 'sudo mkdir -p /opt/iusentra/import && sudo chown UTENTE /opt/iusentra/import'
P=~/iusentra-lex-fonti/pacchetti/lex-fonti-AAAAMMGG-HHMM.tar.zst
rsync -avP --partial "$P" "$P.sha256" UTENTE@SERVER:/opt/iusentra/import/
```

`rsync --partial` riprende la copia dopo un'interruzione (alternativa: `scp "$P" "$P.sha256" UTENTE@SERVER:/opt/iusentra/import/`).

### 2.2 Prova a secco e caricamento (sul server)

```bash
cd /opt/iusentra/repo/deploy/hetzner
sudo ./carica_fonti_lex.sh --dry-run /opt/iusentra/import/lex-fonti-AAAAMMGG-HHMM.tar.zst   # mostra i passi, non modifica nulla
sudo ./carica_fonti_lex.sh           /opt/iusentra/import/lex-fonti-AAAAMMGG-HHMM.tar.zst
```

Lo script, nell'ordine:

1. verifica lo SHA-256 del pacchetto e legge `PACCHETTO.json`; controlla lo spazio;
2. estrae in una cartella temporanea dentro `/opt/iusentra/data/normativa` (stesso filesystem) e verifica `SHA256SUMS`;
3. imposta proprietario e permessi come `/opt/iusentra/data/normativa`;
4. ferma `scheduler-worker`;
5. crea il backup datato in `/opt/iusentra/backups/fonti_lex_AAAAMMGG-HHMMSS/` (hard link: nessuna copia e nessuno spazio extra se
   sullo stesso disco; altrimenti copia) di database, indice vettoriale ed eventuale JSONL;
6. sostituisce i file con `rename` (atomico) ed elimina i `-wal`/`-shm` del vecchio database;
7. riavvia `scheduler-worker` e `app` (l'`app` va riaperta sul nuovo database; `--non-riavviare-app` per saltarlo);
8. controlla dentro il container: conteggi uguali a quelli del pacchetto, indice FTS completo, ricerca "art. 2043 c.c." che restituisce l'art. 2043, righe dell'indice vettoriale;
9. **se un passo dopo la sostituzione fallisce, ripristina da solo il backup** e riavvia i servizi.

L'`app` viene riavviata per pochi secondi: scegliere un momento in cui lo studio non lavora.

### 2.3 Verifica dopo il caricamento

```bash
cd /opt/iusentra/repo
docker compose --env-file /opt/iusentra/.env.hetzner -f deploy/hetzner/docker-compose.hetzner.yml \
  exec -T scheduler-worker python - --db /data/normativa/normattiva.sqlite < deploy/hetzner/verifica_fonti_lex.py
docker compose --env-file /opt/iusentra/.env.hetzner -f deploy/hetzner/docker-compose.hetzner.yml logs --tail 50 scheduler-worker
```

Poi provare una domanda giuridica da Lex nel browser (es. "Quali sono i presupposti della responsabilita' extracontrattuale?"):
devono comparire come fonti gli articoli del codice civile (art. 2043 c.c.), non template o impostazioni dello studio.

### 2.4 L'aggiornamento notturno dopo il caricamento

Alle 23:00 (`legal_official_archives_daily` in `pct/scheduler.py`) il worker esegue in ordine:

1. download delle collezioni **core** cambiate nella vigenza `IUSENTRA_NORMATTIVA_VIGENZA` (default `VIGENTE`, come il pacchetto del PC;
   confronto con il catalogo Normattiva, le invariate sono saltate);
2. import con upsert dei soli ZIP di quella vigenza (`--solo-vigenza`: gli ZIP ORIGINALE rimasti in `raw/` da prima non entrano nel database): articoli con chiave `normattiva:<sha XML>:art<n>`, quindi nessuna duplicazione; indice FTS aggiornato solo per i chunk nuovi;
3. **aggiornamento vettori** (`python -m lex.ricerca_giuridica.indice_vettoriale aggiorna --se-disponibile --solo-esistente`):
   vettorizza solo i chunk nuovi o modificati (impronta del testo), al massimo `LEX_VETTORI_NOTTURNO_MASSIMO` (20.000) per notte.
   Se Ollama non risponde, se manca il modello o se l'indice non esiste, il passaggio termina senza errore e la ricerca resta lessicale
   fino alla notte successiva.

Le collezioni scaricate dal PC ma fuori dal set core (storiche, abrogate ecc.) restano nell'archivio ma non sono aggiornate di notte.

## Tornare indietro

Backup creato a ogni caricamento: `/opt/iusentra/backups/fonti_lex_AAAAMMGG-HHMMSS/`.

```bash
cd /opt/iusentra/repo/deploy/hetzner
sudo ./carica_fonti_lex.sh --ripristina /opt/iusentra/backups/fonti_lex_AAAAMMGG-HHMMSS
```

Ferma il worker, rimette database e indice vettoriale precedenti (o toglie quelli che prima non esistevano), riavvia. Dopo qualche giorno senza problemi
eliminare la cartella di backup per liberare spazio. Il pacchetto resta in `/opt/iusentra/import/` (si puo' ricaricare).

Se il server aveva un archivio Normattiva con articoli duplicati da vecchi import (prima della 2.436.0), il nuovo importer li rimuove al primo import
(`migra_schema`, eseguita all'apertura del database da parte dell'importer); il pacchetto del PC e' gia' privo di duplicati.

## Aggiornare di nuovo dal PC

Per un nuovo caricamento completo ripetere 1.1-1.5 e 2.1-2.2: `scarica` salta le collezioni invariate, `importa` aggiunge solo il nuovo, `vettori`
calcola solo i chunk nuovi, `pacchetto` produce un nuovo `.tar.zst`.

## Problemi noti

- Vigenza: il pacchetto di ottobre 2026 e' stato scaricato **VIGENTE** (`formatoRichiesta=V`, 22 collezioni, import senza errori) e da
  2.436.8 anche l'aggiornamento notturno scarica e importa VIGENTE. Non mescolare vigenze nello stesso database.
- `api.normattiva.it` non invia il certificato intermedio GlobalSign: Python fallisce con `CERTIFICATE_VERIFY_FAILED`. Da 2.436.8 l'intermedio
  pubblico (`lex/normativa/certificati/`, valido fino al 2029) viene aggiunto alle CA del client Normattiva; la verifica TLS resta attiva.
- I tempi di vettorizzazione dipendono da Ollama e dalla lunghezza dei chunk: i numeri di questo documento sono stime finche' non si esegue `vettori --stima`.
- Se il digest di `embeddinggemma:300m` sul server e' diverso da quello del PC l'aggiornamento notturno rifiuta di mescolare i vettori (log del worker) e la ricerca usa
  l'indice caricato finche' il nome del modello coincide; per riallinearli ricostruire l'indice sul PC con lo stesso modello e ricaricare.
