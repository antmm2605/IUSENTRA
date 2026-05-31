# Assistenza Remota Cliente

## Obiettivo

Il modulo `Assistenza remota` permette al `SUPERADMIN` di piattaforma di aprire una sessione tecnica verso il cliente con:

- condivisione schermo WebRTC
- microfono opzionale
- chat tecnica cifrata
- audit completo di sessione
- consensi espliciti del cliente
- aggancio governato a un controllo remoto avanzato esterno

Dal rilascio `2.239.0` la sessione base è pronta al primo avvio: IUSENTRA
configura un endpoint STUN predefinito, crea il link cliente firmato, apre la
stanza operatore e abilita chat/audit senza richiedere variabili manuali.
TURN e controllo remoto avanzato esterno restano presidi opzionali per reti
difficili o strumenti di desktop-control già scelti dallo studio.

La regola prodotto è ferrea:

- la sessione nasce sempre da `SUPERADMIN`
- il cliente entra solo da link firmato
- schermo, audio e controllo avanzato richiedono consenso esplicito
- il controllo avanzato non parte mai se `SUPPORT_ADVANCED_URL_TEMPLATE` non è configurato

## Superfici prodotto

- `Piattaforma -> Assistenza remota` -> `/admin/supporto-remoto`
- `Dashboard studio` -> pulsante `Assistenza remota`
- `Scheda cliente` -> pulsante `Assistenza cliente`
- `Dettaglio fascicolo` -> pulsante `Sessione tecnica`
- `Link cliente` -> `/support/join/<token>`
- `Stanza operatore` -> `/support/operatore/<public_id>`

## Architettura

### Dominio e repository

- `pct/support_remote.py`
  helper di dominio, ICE/TURN, token operatore, story line audit, URL controllo avanzato
- `pct/support_repository.py`
  repository SQL governato per `SQLite` e `PostgreSQL`
- `pct/sql/20260422_support_remote.sql`
- `pct/sql/20260422_support_remote_postgres.sql`

### Runtime e signaling

- `web/extensions.py`
  inizializza `Sock`
- `web/services/support_runtime.py`
  autorizzazione `SUPERADMIN`, audit, payload sessione, signaling WebSocket
- `web/services/support_presence.py`
  presenza in memoria per singola istanza
- `web/services/support_surface.py`
  payload della console admin

### UI

- `web/templates/admin/support_console.html`
- `web/templates/support/operator_room.html`
- `web/templates/support/customer_room.html`
- `web/static/js/support_console.js`
- `web/static/js/support_launch.js`
- `web/static/js/support_operator_room.js`
- `web/static/js/support_customer_room.js`
- `web/static/scss/pages/_support-remote.scss`

## Storage

Il dominio è piattaforma-first:

- `JSON`: non usato
- `SQLite`: attivo con `PCT_SUPPORT_DB`
- `PostgreSQL`: attivo con DSN runtime dedicato

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
PCT_SUPPORT_ADVANCED_URL_TEMPLATE=https://support.tuodominio.it/advanced/{public_id}
```

Dal prodotto queste stesse impostazioni sono gestibili anche in:

- `Piattaforma -> Assistenza remota -> Presidio realtime`

Il salvataggio aggiorna subito il runtime applicativo e persiste i valori nel
file config piattaforma. Se il campo STUN viene lasciato vuoto, il prodotto
mantiene il default pronto all'uso invece di degradare in stato da configurare.

## Nginx e WebSocket

Per funzionare dietro reverse proxy serve il blocco WebSocket dedicato su `/support/ws/`.

La configurazione locale del repo include già:

- `Upgrade`
- `Connection "upgrade"`
- timeout lunghi
- `proxy_buffering off`

Senza questo blocco la UI si apre ma il signaling non parte.

## HTTPS e browser

La condivisione schermo reale richiede:

- `HTTPS` oppure `localhost`
- consenso esplicito del cliente
- browser moderni con `getDisplayMedia()` e `getUserMedia()`

I data channel WebRTC sono cifrati. Il default STUN consente l'avvio della
sessione nella maggior parte degli scenari; `TURN` resta raccomandato per
clienti dietro firewall o NAT restrittivi.

## TURN self-hosted

In produzione è raccomandato `coturn` con secret condiviso tra backend e relay.

Regola operativa:

- almeno un `STUN` è sempre presente grazie al default applicativo
- `TURN` è raccomandato, non bloccante, per reti con NAT o firewall difficili
- non distribuire credenziali TURN statiche al browser

## Audit e consensi

Ogni sessione persiste:

- stato
- operatore
- cliente
- studio e pratica collegati
- consensi schermo/audio/chat
- richiesta e approvazione del controllo avanzato
- timeline eventi in `support_event`

Il registro è leggibile dalla console come storia operativa, non solo come log tecnico.

## Controllo remoto avanzato

Il modulo non reimplementa il desktop control nel browser. L'aggancio è previsto tramite:

- `SUPPORT_ADVANCED_URL_TEMPLATE`

Flusso:

1. l'operatore richiede l'escalation
2. il cliente approva o rifiuta
3. solo dopo l'approvazione compare il pulsante per aprire lo strumento esterno

Se il template non è configurato, l'escalation viene bloccata con messaggio esplicito.

## Limite attuale

La presenza realtime è in memoria processo:

- va bene per singola istanza o ambiente locale
- per multi-worker/multi-nodo servirà una futura estrazione su `Redis pub/sub`

Il resto del modulo è già separato in modo da poter spostare solo questo layer senza riscrivere UI, repository o policy.

## Verifiche minime release

- `pytest tests/test_support_remote.py`
- `python tools/check_repo_governance.py`
- `docker compose build --no-cache`
- `docker compose up -d --force-recreate`
- `/admin/supporto-remoto` raggiungibile da `SUPERADMIN`
- stato console `Pronta per assistenza immediata`
- link cliente pubblico funzionante
- reverse proxy con WebSocket attivo
