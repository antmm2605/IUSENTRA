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
3. **riallineamento degli articoli** (`tools/normattiva_riallinea.py`, vedi 2.6): corregge solo i documenti divisi male dalla vecchia regola;
4. **integrazione delle leggi ordinarie essenziali** (`tools/normattiva_integra_leggi.py`, vedi sotto): Open Data non le distribuisce;
   il file del repository le inserisce nello stesso formato degli altri atti (idempotente: nessuna modifica se gia' presenti e invariate);
5. **aggiornamento vettori** (`python -m lex.ricerca_giuridica.indice_vettoriale aggiorna --se-disponibile --solo-esistente`):
   vettorizza solo i chunk nuovi o modificati (impronta del testo), al massimo `LEX_VETTORI_NOTTURNO_MASSIMO` (20.000) per notte.
   Se Ollama non risponde, se manca il modello o se l'indice non esiste, il passaggio termina senza errore e la ricerca resta lessicale
   fino alla notte successiva.

Le collezioni scaricate dal PC ma fuori dal set core (storiche, abrogate ecc.) restano nell'archivio ma non sono aggiornate di notte.

### 2.5 Le leggi ordinarie che Open Data non distribuisce

Le collezioni predefinite di Normattiva Open Data sono per tipo di atto (codici, testi unici, decreti legislativi, d.P.R., decreti-legge con
leggi di conversione, leggi costituzionali, leggi delega, di ratifica, di bilancio): **le leggi ordinarie non hanno una collezione**.
Nell'archivio mancavano quindi la Costituzione, la l. 241/1990, la l. 53/1994 (notifiche degli avvocati), la l. 742/1969 (sospensione
feriale), la l. 890/1982, la l. 689/1981, il d.l. 132/2014, la l. 898/1970, lo Statuto dei lavoratori, la l. 604/1966, le leggi sulle
locazioni (392/1978 e 431/1998), la l. 247/2012, la l. 49/2023, la l. 24/2017, il d.P.R. 68/2005, la l. 54/2006, la l. 76/2016,
la l. 104/1992 e il d.P.R. 1199/1971.

Da 2.436.10 i loro testi vigenti (raccolti e controllati il 03-04/10/2026 da edizionieuropee.it e brocardi.it, resi nello stile
di Normattiva; in tutto 30 atti e 1.937 articoli, con lo Statuto del contribuente, la l. 184/1983, la l. 633/1941, la l. 218/1995,
la l. 354/1975, la l. 219/2017, la l. 194/1978, la legge fallimentare, il **GDPR** (Reg. UE 2016/679) e il **Codice deontologico
forense** dal PDF ufficiale del CNF aggiornato al 2026) sono in `lex/normativa/integrazioni/leggi_essenziali.jsonl` e vengono inseriti nell'archivio da:

```bash
# sul server (nel container app o scheduler-worker); il job notturno lo fa da solo dopo l'import Open Data
python tools/normattiva_integra_leggi.py --db /data/normativa/normattiva.sqlite --vettori
python tools/normattiva_integra_leggi.py --db /data/normativa/normattiva.sqlite --verifica
# sul PC (WSL), nell'archivio locale
python tools/normattiva_integra_leggi.py --db ~/iusentra-lex-fonti/normativa/normattiva.sqlite --vettori
```

Collezione `Integrazione leggi essenziali`, vigenza VIGENTE, identita' `atto:<numero>/<anno>` (la Costituzione come codice `costituzione`):
le ricerche "legge 53/1994 art. 3-bis" trovano l'articolo esatto come per i codici. Un atto gia' presente con lo stesso testo viene saltato;
se il file cambia (nuova raccolta), la versione precedente viene sostituita, indice FTS compreso; i vettori dei chunk nuovi li calcola il
passaggio notturno (o subito con `--vettori`). Con un archivio ORIGINALE non fa nulla. Per aggiornare i testi: ricostruire il JSONL
(stesso formato: `chiave, atto, articolo, rubrica, testo "Art. N. (Rubrica). ...", titolo_atto, data_atto, urn`) e rilanciare.

#### Regolamenti UE dalla Gazzetta ufficiale dell'Unione europea (2.436.11)

Nello stesso file, con la stessa integrazione, ci sono 16 regolamenti UE di diritto processuale civile internazionale e
d'uso frequente (892 articoli): Bruxelles I-bis (Reg. UE 1215/2012), controversie di modesta entita' (Reg. CE 861/2007),
ingiunzione di pagamento europea (Reg. CE 1896/2006), titolo esecutivo europeo (Reg. CE 805/2004), sequestro conservativo
su conti bancari (Reg. UE 655/2014), Roma I (Reg. CE 593/2008), Roma II (Reg. CE 864/2007), Bruxelles II-ter
(Reg. UE 2019/1111), Roma III (Reg. UE 1259/2010), successioni (Reg. UE 650/2012), notificazione degli atti
(Reg. UE 2020/1784), assunzione delle prove (Reg. UE 2020/1783), passeggeri aerei (Reg. CE 261/2004), insolvenza
(Reg. UE 2015/848), eIDAS (Reg. UE 910/2014), intelligenza artificiale (Reg. UE 2024/1689).

**Fonte**: Ufficio delle pubblicazioni dell'Unione europea (fonte ufficiale), `https://publications.europa.eu/resource/celex/<CELEX>`
con `Accept: application/xhtml+xml` e `Accept-Language: ita` (XHTML della GUUE in italiano; per gli atti anteriori a maggio 2004
c'e' solo la manifestazione `text/html`). eur-lex.europa.eu risponde con una challenge anti-bot e **non** si usa.
Nel JSONL: `fonte_testo` = `publications.europa.eu (GUUE)`, `url` = URI CELEX effettivamente usato, URN
`urn:nir:unione.europea:regolamento:AAAA-MM-GG;N`, `atto` = `Reg. UE 1215/2012` / `Reg. CE 861/2007` / `Reg. UE 2015/848`
(dal 2015 il numero ufficiale e' anno/numero).

**Versione del testo** (indicata alla fine di `titolo_atto`):

- `[Testo consolidato al GG/MM/AAAA, Ufficio delle pubblicazioni UE]`: per ogni atto si cerca il consolidato piu' recente
  (CELEX `0AAAARNNNN-AAAAMMGG`, elenco dall'endpoint SPARQL ufficiale `publications.europa.eu/webapi/rdf/sparql`); si usa se
  l'URI risponde e la divisione in articoli passa i controlli. I consolidati sono strumenti di documentazione: fanno fede i
  testi pubblicati in GUUE. Gli articoli soppressi non compaiono nel consolidato e quindi non sono nel file (ammessi solo se
  esistono nel testo originale): art. 32 Reg. 805/2004, artt. 17-19 Reg. 910/2014.
- `[Testo originale pubblicato in GUUE: modifiche successive non incluse]`: quando non c'e' un consolidato utilizzabile.
  Al 05/10/2026 vale per Roma II (l'unico consolidato, 02007R0864-20090111, risponde 404) e Roma III (nessun consolidato);
  nessuno dei due ha modifiche successive.

Versioni usate al 05/10/2026: 1215/2012 al 26/02/2015, 861/2007, 1896/2006, 805/2004, 655/2014 e 2020/1784 al 01/05/2025,
593/2008 al 24/07/2008, 2019/1111 al 02/07/2019, 650/2012 al 05/07/2012, 2020/1783 al 02/12/2020, 261/2004 al 17/02/2005,
2015/848 al 06/11/2025, 910/2014 al 18/10/2024, 2024/1689 al 27/07/2026.

**Divisione in articoli** (`lex/normativa/ue_regolamenti.py`): formati GUUE `oj-` (div `art_N`, `oj-ti-art`/`oj-sti-art`, elenchi
in tabelle a due colonne), GUUE vecchio (`ti-art`/`sti-art`), consolidato (`title-article-norm`/`stitle-article-norm`, `.norm`,
elenchi in `div` rientrati o `grid-container`, marcatori `►M1 ▼B ◄` tolti) e HTML semplice (`<p>Articolo N</p><p>Rubrica</p>`).
Esclusi considerando, formula finale, firme, note e allegati. Testo nello stile Normattiva: `Art. N. (Rubrica). 1. ... a) ...`
(numerazione dei paragrafi e lettere conservate, articoli `bis` come `Art. 71-bis.`). Controlli bloccanti: numerazione da 1
all'ultimo «Articolo N» senza buchi, intestazioni trovate = articoli letti, nessun articolo vuoto, nessuna intestazione
d'articolo dentro il testo di un altro, nessun testo duplicato.

**Riconoscimento** (`lex/ricerca_giuridica/testo.py`, `REGOLAMENTI_UE`): ogni regolamento e' un «codice» con etichetta
`Reg. UE 1215/2012 (Bruxelles I-bis)` e alias numerici in tutte le forme («Reg. UE 1215/2012», «regolamento (UE) n. 1215/2012»,
«reg. 848/2015» e «2015/848») e d'uso («Bruxelles I bis», «Roma I/II/III», «Bruxelles II-ter», «regolamento passeggeri»,
«eIDAS», «AI Act», «decreto ingiuntivo europeo», ...). «Roma I» vale solo con la maiuscola nella domanda (non «a Roma i
giudici...»). Le ricerche «art. 7 Reg. UE 1215/2012» o «art. 4 Roma I» trovano l'articolo esatto.

Aggiornamento dei testi (sul PC; la rete del server non serve):

```bash
python tools/ue_regolamenti_scarica.py --cache ~/iusentra-lex-fonti/ue --aggiorna          # scarica, divide, controlla, riscrive il JSONL
python tools/ue_regolamenti_scarica.py --cache ~/iusentra-lex-fonti/ue --offline --solo 32012R1215   # solo dalla cache
python tools/normattiva_integra_leggi.py --db ~/iusentra-lex-fonti/normativa/normattiva.sqlite --vettori
```

Un atto con errori non viene scritto (codice di uscita 1). Dopo il commit del JSONL, il deploy e il job notturno inseriscono
i nuovi testi come per le altre leggi integrate.

### 2.6 Articoli divisi male (riallineamento)

L'importatore divideva il testo in articoli con una regola troppo larga: tagliava sui rimandi interni («dell'art. 2297.»: art. 2317 e
1815 c.c. troncati), non riconosceva «Art. 29 Azione di annullamento» (il c.p.a. finiva dentro pochi articoli), ne' «Art. 183-ter (...)»,
«669-terdecies», «5-bis», «2-ter» (finiti dentro l'articolo base). La nuova divisione (`lex/normativa/articoli_testuali.py`) vale per i nuovi
import; per gli archivi gia' importati:

```bash
python tools/normattiva_riallinea.py --db /data/normativa/normattiva.sqlite --analizza   # resoconto, nessuna modifica
python tools/normattiva_riallinea.py --db /data/normativa/normattiva.sqlite --vettori    # corregge e aggiorna i vettori
```

Tocca solo i documenti con difetti; se i controlli di coerenza non passano (numeri d'articolo persi, testo ridotto) il documento resta com'e'
e compare nel resoconto. Idempotente. Il deploy lo esegue una volta (con copia di sicurezza `normattiva.prima_riallineamento.sqlite` se c'e'
spazio), poi lo ripete il job notturno.

### 2.7 Corte costituzionale: archivio completo delle pronunce e delle massime

Fonte: open data ufficiali della Corte costituzionale, <https://dati.cortecostituzionale.it> («Scarica i dati»).
**Licenza Creative Commons BY-SA 3.0**: l'uso e' libero con **attribuzione** («Fonte: Corte costituzionale,
dati.cortecostituzionale.it») e, se si redistribuiscono i dati rielaborati, con la stessa licenza. Ogni pronuncia nel corpus
rimanda alla scheda ufficiale `https://www.cortecostituzionale.it/scheda-pronuncia/AAAA/N`; la fonte `corte_costituzionale`
del corpus riporta la licenza nelle note.

File usati (zip di zip annuali, tre periodi `1956_1980`, `1981_2000`, `2001_oggi`):

- pronunce JSON: `https://dati.cortecostituzionale.it/opendata/distribuzione/pronunce/P_json<periodo>.zip`
  (`Cc_Opendata_Pronunce_AAAA.json`, cp1252, `elenco_pronunce`: numero, anno, tipologia S/O, date, collegio, relatore,
  presidente, epigrafe, testo, dispositivo, ECLI);
- massime XML: `https://dati.cortecostituzionale.it/opendata/distribuzione/CC_OpenMassime_<periodo>.zip`
  (`Cc_OpenData_Massime_AAAA.xml`, UTF-8: tipologia del giudizio, titolo e testo di ogni massima).

`pct/corte_costituzionale_opendata.py` unisce pronunce e massime per (anno, numero) e scrive nel corpus giurisprudenziale
(`giurisprudenza_corpus.db`, lo stesso che Lex interroga con FTS5): organo «Corte costituzionale», sentenza/ordinanza, numero e anno,
ECLI, relatore, presidente, collegio, date ISO, titolo «Corte costituzionale, sentenza n. X/AAAA», oggetto (tipologia del giudizio),
titoli delle massime, massime ufficiali (anche nella tabella `massime`), dispositivo (`principio_sintetico` ed `esito`, senza formula
d'apertura e firme), testo integrale (epigrafe, testo, dispositivo), stato `verificata`, fonte ufficiale confermata. Scrittura a blocchi
di 500 righe per transazione, chiave ECLI, righe invariate saltate (impronta del contenuto): rilanciarlo non duplica nulla.

```bash
# sul server (container scheduler-worker): scarica e importa nel corpus globale e in quello di ogni studio
python tools/cortecost_importa.py --cartella /data/fonti_ufficiali/cortecost --scarica --tutti-i-tenant
# un corpus preciso, zip gia' scaricati, riepilogo JSON
python tools/cortecost_importa.py --cartella ~/cortecost --db /data/intelligence/giurisprudenza_corpus.db --json
# uno studio: --tenant-dir /data/tenants/<slug>   ·   solo dal 2020: --dal-anno 2020   ·   prova: --dry-run
```

Misurato il 05/10/2026 sul dataset completo (22.395 pronunce: 11.715 sentenze e 10.680 ordinanze; 46.561 massime su 22.313
pronunce): import in un corpus vuoto **circa 5 minuti** (285 s), rilancio senza modifiche circa 1 minuto, corpus di **circa 770 MB**
(testo integrale e indice FTS compresi). Lo spazio vale per ogni corpus: con `--tutti-i-tenant` il globale e ogni studio.

- **Deploy** (`deploy.sh`, passo 7c): una tantum, in background nel worker, solo per i corpus che non hanno ancora registrato l'import
  completo (`importazioni_giurisprudenza`, `cortecost_opendata:completo`); log in `/data/fonti_ufficiali/cortecost/import.log`.
  Se il download non riesce il deploy prosegue e ci riprova il deploy successivo; un import interrotto riparte da capo saltando le righe
  gia' scritte. Un lock nella cartella impedisce due import contemporanei.
- **Settimanale** (job `corte_costituzionale_opendata_weekly`, sabato 04:20; `PCT_CORTECOST_SYNC_GIORNO`, `PCT_CORTECOST_SYNC_ORA`,
  cartella `PCT_CORTECOST_OPENDATA_DIR`): riscarica `2001_oggi` e importa solo anno corrente e precedente (`--anni-recenti 2`).

Per Lex ogni pronuncia e' una fonte giurisprudenziale verificata: intestazione `[n] Corte costituzionale, sentenza n. 6/2025 ·
ECLI:IT:COST:2025:6 · 27/01/2025` (data di deposito) e testo con prima la massima ufficiale, poi il dispositivo, entro i 1.600
caratteri del blocco. La guardia anti-allucinazione riconosce «ordinanza n. X/AAAA» e «Corte cost., sent./ord. n. X/AAAA».

Classifica delle ricerche (`GestioneCorpusGiurisprudenza.cerca_sentenze`): estremi citati nella domanda (ECLI o numero/anno dopo
«sentenza», «ord.», «Corte cost.», «Cass.»; non dopo «legge», «d.lgs.», «art.») in testa; poi i candidati FTS (AND dei termini, poi OR)
riordinati per bm25 relativo e copertura dei termini nei titoli e nelle massime; sentenze della Consulta prima delle ordinanze; pronunce
solo processuali (rinvio, restituzione degli atti, correzione di errore materiale, estinzione) in fondo, salvo domanda esplicita.
Le pronunce di sola inammissibilita' non sono penalizzate: molte sono decisioni con monito di grande rilievo (es. 32 e 33/2021).

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

## Importazione tramite GitHub Actions senza chiave SSH locale

Il workflow manuale `.github/workflows/import-lex-fonti.yml` riusa `HETZNER_SSH_PRIVATE_KEY` e `HETZNER_SSH_KNOWN_HOSTS` del deploy. Il pacchetto e il checksum vengono caricati in una **bozza privata** di release con tag `lex-fonti-transfer-...`, senza includerli nel repository Git. Fornire al workflow tag, nome del file e SHA-256 verificato sul PC. Il job verifica la bozza e i checksum, trasferisce i file con rsync in `/opt/iusentra/import`, esegue prima `--dry-run` e poi lo script canonico `carica_fonti_lex.sh`, che crea il backup e verifica i conteggi e la ricerca. Dopo il controllo health la bozza temporanea viene eliminata; restano il pacchetto locale, la copia server e il backup delle fonti precedenti. In caso di errore la bozza resta disponibile per diagnosi/ripresa. La concorrenza è condivisa con il deploy di produzione per impedire operazioni simultanee. Nessuna chiave privata viene estratta da GitHub.

Il parametro `operation=verify` del workflow esegue solo accesso SSH, conteggi del database nel container, controllo FTS/vettori/ricerca e health dei servizi. Non scarica pacchetti, non importa, non riavvia servizi e non cancella release; gli altri input restano compilabili ma sono ignorati in questa modalità.

## Diagnosi Lex dopo il deploy

Il workflow `deploy-hetzner.yml` accetta `diagnosi_lex=true` per eseguire `deploy/hetzner/diagnosi_lex_domande.py` dentro il container `app` solo dopo CI richiesta superata, deploy riuscito e verifiche post-deploy. Lo script stampa classificazione, percorso, fonti e risultati Normattiva delle sei domande di prova, senza chiamare il modello. I log della step conservano i risultati; il valore predefinito resta `false`.
