# Primo percorso offline sicuro — 11 ottobre 2026

Stato: implementazione in revisione, non verificata sulla macchina reale dello studio.
Nessun archivio reale consultato. Nessun deploy autorizzato o avviato.

## Risultato osservabile e perimetro

Da Impostazioni, «Computer autorizzati e lavoro offline» apre una superficie React
separata. Un utente attivo registra esplicitamente il browser del computer,
prova il possesso della sua chiave P-256 e fa confrontare il codice completo
all’amministratore dello stesso studio. Solo dopo l’approvazione e una richiesta
firmata riceve dati per il vault locale. Il MAC non è raccolto né usato.

Il primo dominio è costituito da **note personali collegate al fascicolo**, con
allegati TXT fino a 64 KB. Titolo fino a 200 caratteri, nota fino a 32000,
fino a 1000 note per identità inclusi i tombstone. Ogni nota mantiene il
fascicolo proprietario; non modifica i documenti originari, i presìdi o i flussi
firma/deposito/PEC. Non replica ancora clienti, agenda, PEC, PDF o l’intero
archivio e non abilita firme, invii o depositi offline.

I primi 100 fascicoli in ordine di numero sono selezionabili nel percorso
pilota. Le note già presenti possono comunque essere lette tramite il delta.
Una nota con una modifica in attesa non può essere modificata una seconda
volta finché quel comando non è confermato o riconciliato. Il testo in editor
rimane una bozza; solo «Conserva modifica sul computer» lo aggiunge alla coda.

## Dati e autorizzazioni

- Tabelle `offline_state`, `offline_devices`, `offline_challenges`,
  `offline_notes`, `offline_commands`, `offline_audit` nel SQL dello studio.
- Migrazioni esplicite SQLite/PostgreSQL gemelle in `pct/sql/20261011_offline*`;
  integrate nei bootstrap dei due backend, nessun fallback JSON.
- Tutte le query includono studio; dispositivi e note includono l’identità.
  Le note sono personali: due avvocati non ricevono le note reciproche.
- Sessione IUSENTRA attiva e `fascicoli.leggi` necessari a ogni API;
  `fascicoli.scrivi` e presenza del fascicolo necessari alle modifiche.
- Approvazione solo per AMMINISTRATORE con `utenti.scrivi`; il proprietario
  può revocare la propria credenziale. Revoca irreversibile: per cambiare o
  recuperare una chiave si revoca il vecchio dispositivo e si registra e
  approva una nuova credenziale. Nessuna chiave privata è consegnata al server.
- DDL solo nel bootstrap/migrazione, non nel repository di una GET.
  La feature è disattivata per default: `IUSENTRA_OFFLINE_ENABLED=1` o
  `OFFLINE_WORKSPACE_ENABLED=True` la abilita esplicitamente nell’installazione.
- Challenge di 120 secondi, casuali, monouso, con studio, identità, dispositivo,
  generazione e hash dell’intento. Firma ECDSA P-256/SHA-256 in formato P1363.
- Approvazione, revoca, prova, scritture e sync hanno audit SQL nella stessa
  transazione dell’effetto. La regia audit esistente riceve anche le azioni
  amministrative. Non si registrano testo delle note o contenuti degli allegati.

## Archivio locale e limiti della garanzia

La chiave privata WebCrypto è non esportabile e conservata in IndexedDB.
Il vault è separato per studio, identità e dispositivo. Note, allegati, coda,
versioni, avanzamento e autorizzazione offline vengono cifrati con AES-256-GCM;
IV casuale per ogni salvataggio e contesto del vault come additional authenticated
data. La chiave del vault viene derivata dalla frase locale con PBKDF2-SHA-256,
600000 iterazioni e salt casuale. La frase non viene inviata al server né salvata.

Registrare un computer conserva soltanto metadati e credenziale; non scarica
l’archivio. Dati e coda arrivano solo dopo un aggiornamento firmato approvato.
Una transazione IndexedDB conferma insieme coda, dati, cursor e autorizzazione.
Web Locks consentono una sola scheda operativa per archivio; l’area si blocca
dopo cinque minuti di inattività. Lo sblocco online verifica nuovamente sessione,
identità e approvazione prima di mostrare i dati; offline verifica la scadenza.

**Questa è un’identità del profilo browser, non un’attestazione hardware.** Una
chiave non esportabile impedisce l’esportazione ordinaria tramite WebCrypto, ma
non dimostra TPM o computer fisico e non protegge da compromissione del browser,
XSS nello stesso origin, copia del profilo da un amministratore del sistema,
frase debole o dispositivo sbloccato. È necessario proteggere account OS e disco.
Nessuna copia deve essere installata su una postazione condivisa senza approvazione.

La revoca impedisce immediatamente nuove challenge e ogni sync, anche se una
challenge era stata emessa prima della revoca. Alla riconnessione il client
collaborante elimina il vault se il server nega l’accesso. Un computer realmente
scollegato non può conoscere la revoca: la sua precedente autorizzazione scade
entro 24 ore (config `OFFLINE_LEASE_SECONDS`, intervallo 300–86400 secondi).
Il controllo dell’orologio rileva arretramenti rispetto all’ultimo salvataggio,
ma non è un orologio hardware affidabile né una cancellazione remota garantita.
Un utente che controlla browser/codice e possiede la frase può aggirare controlli
client; per una garanzia hardware occorre un companion con TPM/Keychain e
politica OS, da integrare separatamente. Nessuna promessa di revoca istantanea
senza rete o distruzione delle copie già esportate.

La dimenticanza della frase non consente recupero dal server delle modifiche
mai sincronizzate. Una copia locale può essere rimossa esplicitamente dalla UI;
la conferma segnala la perdita delle modifiche pendenti.

## Sincronizzazione e conflitti

Il server SQL resta autorevole. Una sequenza per studio serializza revoche,
consumo delle prove e scritture. Ogni comando contiene UUID, nota e versione
base. Una ricevuta persistente rende il retry dopo risposta persa idempotente;
lo stesso comando con contenuto diverso viene rifiutato. Batch invalidi o
non autorizzati vengono annullati per intero. Il delta paginato restituisce
solo note proprie autorizzate e tombstone, dopo il cursor confermato.

Una versione concorrente produce un conflitto conservato nella coda cifrata:
la UI mostra bozza locale e versione server. «Usa la versione del server»
scarta il comando; «Proponi la mia versione» crea un nuovo comando con la
versione corrente, ancora soggetto a controllo concorrente. Una nota eliminata
non viene resuscitata: si può copiare la bozza in una nuova nota. Il manifest
`authorized_ids` rimuove le copie locali divenute inaccessibili. La riconnessione
avvia il recupero, con massimo 20 pagine per ciclo e ripresa dal cursor salvato.

## Postazioni online e cache

Il service worker conserva esclusivamente un’allowlist di asset pubblici:
pagina offline, icone e HTML/JS/CSS generici della nuova area. Non conserva
API, HTML autenticato, note o allegati. La shell pubblica non contiene studio,
identità, token o dati prerenderizzati. Cache HTTP autenticate: `private,
no-store`; asset statici pubblici mantengono la propria politica per le prestazioni.

`offline-browser-memory.js` mantiene in RAM le memorie riservate già individuate
(bozze anagrafiche, ricerche recenti, note/profilo vocale, feedback, conversazione
Lex, cronologia acquisizioni, comandi CTU, contributo unificato). Le API
Storage conservano il comportamento nella scheda, mentre le copie in chiaro
note vengono rimosse. Preferenze grafiche e credenziali di autenticazione
mantengono il ciclo esistente. Il vault cifrato è il solo percorso persistente
per i dati del dominio offline. Il cambio pagina può perdere una bozza ordinaria
non salvata: viene offerta l’avvertenza browser di uscita. Questa modifica alla
persistenza è intenzionale per le postazioni temporanee; l’archivio completo
online resta sul server.

Questo controllo riguarda le memorie censite nel codice e le risposte servite
dopo l’aggiornamento. Non impedisce download espliciti, screenshot, software
malevolo o copie esterne. Le cache di vecchie versioni richiedono verifica sul
computer reale; non si dichiara bonifica universale di tutti i browser.

## Prove e stato della consegna

Guardrail tecnici locali: 13 test Python del dominio/API e 7 test JavaScript;
2 test della regia live esistente; build con Vite 8.2.2, React/ReactDOM 19.2.8;
lint mirato, governance, sincronizzazione manifest e baseline Python 3.12.
Test packaging: versioni allineate; aperta una discordanza preesistente della
lista extras PDF, non modificata in questo intervento.

Diagnostica browser sintetica con Chromium headless 133: registrazione,
confronto codice e approvazione, archivio IndexedDB realmente cifrato, scrittura
senza rete, riapertura offline, recupero online, revoca e rimozione, layout
1280/768/390 pixel. Non costituisce accettazione reale dell’utente.

Parità dello schema verificata staticamente. Suite eseguibile anche su
PostgreSQL 16 tramite `OFFLINE_TEST_DSN`, limitata a un DB disposable chiamato
`offline_synthetic`; workflow dedicato PR. Prova PostgreSQL locale non effettuata:
il runtime non dispone di un servizio non-root utilizzabile. Non sostituire
questa lacuna con una dichiarazione di parità operativa accettata.

```bash
python -m pytest tests/test_offline_sync.py tests/test_offline_api.py -q
node --test tests/js/offline_crypto.test.mjs
npm --prefix frontend run build:offline
node tests/offline_browser_synthetic.mjs
```

La diagnostica browser usa solo `tests/offline_synthetic_server.py` con database
in memoria e porta 18080. Non aprire archivi dello studio per questi test. Il
collaudo finale resta da eseguire su `localhost:8080` della macchina reale,
con studi, utenti e documenti di test autorizzati, compresi due browser/computer,
scadenza e revoca offline, concorrenza, permessi e prestazioni delle pagine.

Pubblicazione su branch dedicato e PR in bozza, perché i due branch operativi
attivano `.github/workflows/deploy-hetzner.yml` al push. È una deroga necessaria
alle regole repository sui branch gemelli per rispettare il divieto esplicito
corrente di deploy automatico. Non modificare o disabilitare i gate/deploy per
aggirare il divieto. Niente merge/auto-merge, deploy, accesso al VPS o agli archivi.
