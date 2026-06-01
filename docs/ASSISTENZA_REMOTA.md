# Assistenza Remota Cliente

## Obiettivo

Il modulo `Assistenza remota` permette al `SUPERADMIN` di piattaforma di aprire una sessione tecnica verso il cliente con:

- condivisione schermo WebRTC;
- microfono opzionale;
- chat tecnica;
- audit completo di sessione;
- consensi espliciti del cliente;
- controllo remoto reale del PC cliente tramite agente locale IUSENTRA Assistenza.

Dal rilascio `2.239.0` la sessione base è pronta al primo avvio: IUSENTRA configura un endpoint STUN predefinito, crea il link cliente firmato, apre la stanza operatore e abilita chat/audit senza richiedere variabili manuali. TURN resta un presidio opzionale per reti difficili.

Il controllo del PC non usa e non deve usare il Local Signer telematico. Il controllo remoto passa dall'agente locale separato `tools/support_remote_agent.py`, esposto solo su `127.0.0.1` e armato solo dopo consenso cliente.

La regola prodotto è ferrea:

- il `SUPERADMIN` può aprire sessioni dalla console piattaforma e prende sempre in carico la stanza operatore;
- lo studio cliente può richiedere assistenza dalle pagine operative senza passare dalla console admin;
- il cliente entra sempre da link firmato, generato dalla console o dalla richiesta autenticata dello studio;
- schermo, audio e controllo del PC richiedono consenso esplicito;
- il controllo del PC parte solo se l'agente locale IUSENTRA Assistenza risponde su `127.0.0.1`.

## Superfici prodotto

- `Piattaforma -> Assistenza remota` -> `/admin/supporto-remoto`
- `Barra studio` -> pulsante `Assistenza`
- `Dashboard studio` -> pulsante `Assistenza remota`, disponibile anche agli utenti dello studio
- `Scheda cliente` -> pulsante `Assistenza cliente`, disponibile anche agli utenti dello studio
- `Dettaglio fascicolo` -> pulsante `Sessione tecnica`, disponibile anche agli utenti dello studio
- `Richiesta studio` -> `/support/studio/sessione`
- `Link cliente` -> `/support/join/<token>`
- `Stanza operatore` -> `/support/operatore/<public_id>`

## Architettura

### Dominio e repository

- `pct/support_remote.py`
  helper di dominio, ICE/TURN, token operatore, story line audit, agente locale e input Windows reale.
- `pct/support_repository.py`
  repository SQL governato per `SQLite` e `PostgreSQL`.
- `pct/sql/20260422_support_remote.sql`
- `pct/sql/20260422_support_remote_postgres.sql`

### Runtime e signaling

- `web/extensions.py`
  inizializza `Sock`.
- `web/services/support_runtime.py`
  autorizzazione operatore e studio, audit, payload sessione, signaling WebSocket.
- `web/services/support_presence.py`
  presenza e relay realtime con Redis pub/sub quando disponibile, con fallback locale per singola istanza.
- `web/services/support_surface.py`
  payload della console admin.

### UI

- `web/templates/admin/support_console.html`
- `web/templates/support/operator_room.html`
- `web/templates/support/customer_room.html`
- `web/static/js/support_console.js`
- `web/static/js/support_launch.js`
- `web/static/js/support_operator_room.js`
- `web/static/js/support_customer_room.js`
- `frontend/src/components/SupportOperatorRoom.tsx`
- `frontend/src/index.css`
- `tools/support_remote_agent.py`
- `tools/avvia_support_remote_agent.bat`

## Storage

Il dominio è piattaforma-first:

- `JSON`: non usato;
- `SQLite`: attivo con `PCT_SUPPORT_DB`;
- `PostgreSQL`: attivo con DSN runtime dedicato.

Percorso locale di default:

```text
/data/support/assistenza_remota.db
```

## Configurazione

Variabili runtime principali:

```env
PCT_SUPPORT_DB=/data/support/assistenza_remota.db
# Default già operativo se non impostato esplicitamente:
PCT_SUPPORT_STUN_URLS=stun:stun.l.google.com:19302
PCT_SUPPORT_TURN_URLS=turn:turn.tuodominio.it:3478?transport=udp,turns:turn.tuodominio.it:5349?transport=tcp
PCT_SUPPORT_TURN_SHARED_SECRET=<secret-lungo-random>
PCT_SUPPORT_TURN_TTL_SECONDS=3600
```

Dal prodotto queste stesse impostazioni sono gestibili anche in:

- `Piattaforma -> Assistenza remota -> Presidio realtime`

Il salvataggio aggiorna subito il runtime applicativo e persiste i valori nel file config piattaforma. Se il campo STUN viene lasciato vuoto, il prodotto mantiene il default pronto all'uso invece di degradare in stato da configurare.

## Nginx e WebSocket

Per funzionare dietro reverse proxy serve il blocco WebSocket dedicato su `/support/ws/`.

La configurazione locale del repo include già:

- `Upgrade`;
- `Connection "upgrade"`;
- timeout lunghi;
- `proxy_buffering off`.

Senza questo blocco la UI si apre ma il signaling non parte.

## HTTPS e browser

La condivisione schermo reale richiede:

- `HTTPS` oppure `localhost`;
- consenso esplicito del cliente;
- browser moderni con `getDisplayMedia()` e `getUserMedia()`.

I data channel WebRTC sono cifrati. Il default STUN consente l'avvio della sessione nella maggior parte degli scenari; `TURN` resta raccomandato per clienti dietro firewall o NAT restrittivi.

La stanza operatore usa la Fullscreen API quando il browser la consente. Se il browser integrato o il contesto locale bloccano la Fullscreen API, viene attivata una modalità schermo pieno nel viewport: area cliente a tutta larghezza e pannello tecnico compatto sotto.

## TURN self-hosted

In produzione è raccomandato `coturn` con secret condiviso tra backend e relay.

Regola operativa:

- almeno un `STUN` è sempre presente grazie al default applicativo;
- `TURN` è raccomandato, non bloccante, per reti con NAT o firewall difficili;
- non distribuire credenziali TURN statiche al browser.

## Audit e consensi

Ogni sessione persiste:

- stato;
- operatore;
- cliente;
- studio e pratica collegati;
- consensi schermo/audio/chat;
- richiesta e approvazione del controllo remoto del PC;
- timeline eventi in `support_event`.

Il registro è leggibile dalla console come storia operativa, non solo come log tecnico.

## Richiesta assistenza dallo studio

Quando l'utente dello studio preme `Assistenza`, IUSENTRA crea una sessione autenticata con contesto tenant, utente, eventuale cliente o fascicolo e audit dell'azione. La stanza cliente viene aperta subito: l'utente conferma i consensi e attende il `SUPERADMIN`, che vede la sessione nella console `/admin/supporto-remoto` e apre la stanza operatore.

Questo flusso non espone la console piattaforma allo studio e non consente allo studio di assumere il ruolo operatore. La richiesta serve solo ad aprire il canale cliente reale e tracciato.

### Notifiche SUPERADMIN e cellulare

Ogni richiesta aperta dal pulsante `Assistenza` crea anche una notifica urgente per il `SUPERADMIN` di piattaforma. La notifica interna appare nella console `/admin/supporto-remoto` e punta direttamente alla sessione da prendere in carico.

Nella stessa console il `SUPERADMIN` può attivare le notifiche sul proprio cellulare. Quando Web Push è configurato sul server e il dispositivo è stato autorizzato, la richiesta arriva anche se app.iusentra.it non è aperto. Il payload esterno resta privacy-safe: mostra solo che è arrivata una richiesta assistenza e lo studio di provenienza; cliente, pratica e note restano visibili solo dopo login dentro IUSENTRA.

La console consente anche di:

- cambiare manualmente lo stato di una sessione;
- cancellare una sessione;
- cancellare le sessioni di prova/test generate dalle verifiche locali.

## Controllo remoto del PC

Flusso:

1. l'operatore entra nella stanza operatore;
2. il cliente entra dal link firmato;
3. l'operatore richiede il controllo del PC;
4. il cliente approva o rifiuta;
5. solo dopo l'approvazione la UI abilita tasti rapidi, testo e comandi mouse;
6. il browser cliente arma l'agente locale su `127.0.0.1`;
7. ogni comando viene inviato via WebSocket, eseguito dall'agente locale e confermato alla stanza operatore.

L'agente accetta comandi solo per sessioni armate con token valido. A fine test o fine sessione va disarmato.

## Verifica reale locale del 1 giugno 2026

Verifica eseguita sulla copia locale reale dell'utente `http://127.0.0.1:8080`, con agente PC separato `python -m pct.support_remote --host 127.0.0.1 --port 27273`.

- richiesta partita dal bottone reale `Assistenza` nella top bar studio su `/fascicoli`;
- richiesta visualizzata in `/admin/supporto-remoto` e presa in carico dal `SUPERADMIN`;
- stanza cliente aperta su `/support/join/<token>` e stanza operatore React su `/support/operatore/<public_id>?token=...`;
- corretto passaggio cliente da `Attendi operatore` a `Avvia assistenza` dopo la presa in carico;
- `Entra` operatore non attiva più la sessione al posto del cliente;
- il cliente avvia la sessione dopo consenso e lo schermo reale del PC viene mostrato all'operatore tramite agente locale;
- muto microfono verificato lato operatore e lato cliente;
- chat bidirezionale verificata con messaggi visibili da entrambe le parti;
- richiesta controllo PC, approvazione cliente e badge finale `Controllo PC attivo`;
- comando remoto reale `Tab` eseguito sul PC cliente e confermato in chat: `PC cliente: comando eseguito (Tab).`;
- fullscreen cliente attivo con chat compatta sotto lo schermo e fullscreen operatore attivo con pannello tecnico compatto.

Problemi trovati durante la prova reale e corretti:

- agente locale vecchio ancora in ascolto su `27273`: riavviato l'agente corrente da `pct.support_remote`;
- polling bloccato quando una finestra non era in primo piano: rimosso il blocco su `document.hidden`;
- avvio sessione lato operatore: impedito, l'avvio resta responsabilità del cliente dopo consenso;
- muto microfono disabilitato se il dispositivo audio è occupato o non leggibile: il consenso resta attivo e il tasto muto resta operativo.

## Verifica reale locale del 31 maggio 2026

Verifica eseguita sulla copia locale reale `http://127.0.0.1:8080`:

- login SUPERADMIN reale su Docker locale;
- creazione sessione reale via `/support/api/session`;
- apertura stanza operatore React su `/support/operatore/<public_id>?token=...`;
- collegamento cliente via link firmato `/support/join/<token>`;
- presenza operatore/cliente propagata su WebSocket anche con app Gunicorn multi-worker;
- richiesta controllo PC;
- approvazione cliente;
- armamento agente locale `IUSENTRA Support Remote Agent` su `127.0.0.1:27273`;
- attivazione schermo pieno operatore con pannello tecnico compatto;
- esecuzione comando reale `Tab` sul PC Windows tramite agente locale;
- conferma visibile in stanza operatore: `Comando PC eseguito` e `PC cliente: comando eseguito (Tab).`;
- console browser senza errori o warning applicativi;
- container `iusentra-app` healthy e `/api/pronto` 200.

## Verifiche minime release

- `python -m pytest tests/test_support_remote.py -q`
- `node --check web/static/js/support_operator_room.js`
- `node --check web/static/js/support_customer_room.js`
- `pnpm --dir frontend exec tsc --noEmit --pretty false`
- `pnpm --dir frontend build:vite`
- `docker compose build app`
- `docker compose up -d --no-deps --force-recreate app`
- `/api/pronto` 200 su `http://127.0.0.1:8080`
- `/admin/supporto-remoto` raggiungibile da `SUPERADMIN`
- `/support/studio/sessione` raggiungibile da utente autenticato dello studio e non da anonimo
- pulsante `Assistenza` visibile nella barra studio e collegato alla stanza cliente
- link cliente pubblico funzionante
- stanza operatore React funzionante
- reverse proxy con WebSocket attivo
