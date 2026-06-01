# PWA e Web Push Notifications

## Obiettivo

IUSENTRA puo' affiancare al centro notifiche interno un canale Web Push per mobile e tablet, senza app nativa. L'utente resta dentro la web app: se il dispositivo supporta Web Push e ha concesso il consenso, gli avvisi importanti possono arrivare anche quando la scheda di IUSENTRA non e' aperta.

Il sistema e' composto da:

- centro notifiche persistente tenant-aware e user-aware;
- subscription Web Push per dispositivo e utente autenticato;
- Service Worker PWA con scope root;
- pannello React in `Impostazioni > Notifiche` per attivazione, disattivazione e test;
- invio push privacy-safe per eventi importanti o urgenti.

## Notifiche interne e Web Push

Le notifiche interne restano quelle mostrate nella top bar e nel gestionale. Contengono i dettagli operativi visibili dopo login: scadenze, udienze, PEC, depositi, documenti e fatture.

Le Web Push sono solo un richiamo esterno al gestionale. Non devono contenere nomi cliente, codici fiscali, RG, controparti, importi o descrizioni riservate. Il payload inviato al browser contiene solo testo generico, priorita, tipo, `href` sicuro e identificativo notifica.

Per le richieste di assistenza remota il payload puo' indicare lo studio di provenienza, cosi' il `SUPERADMIN` capisce subito quale studio richiede intervento. Cliente, pratica, RG e note operative restano nel centro notifiche interno e nella console autenticata.

Se Web Push non e' configurato o il browser non lo supporta, il centro notifiche interno continua a funzionare.

## Prerequisiti

- HTTPS valido in produzione. I browser moderni richiedono un contesto sicuro per Service Worker e Push API.
- Variabili VAPID configurate in ambiente.
- Utente autenticato in IUSENTRA.
- Consenso esplicito dell'utente dal pulsante in `Impostazioni > Notifiche`.
- Browser/dispositivo compatibile.

In sviluppo locale, `localhost` puo' registrare il Service Worker, ma la ricezione push reale dipende dal browser e dalle chiavi configurate.

## Configurazione VAPID

Variabili ambiente:

```bash
IUSENTRA_WEB_PUSH_ENABLED=1
IUSENTRA_VAPID_PUBLIC_KEY=<chiave pubblica VAPID>
IUSENTRA_VAPID_PRIVATE_KEY=<chiave privata VAPID>
IUSENTRA_VAPID_SUBJECT=mailto:admin@example.com
```

Default consigliato nei template deploy:

```bash
IUSENTRA_WEB_PUSH_ENABLED=0
IUSENTRA_VAPID_PUBLIC_KEY=
IUSENTRA_VAPID_PRIVATE_KEY=
IUSENTRA_VAPID_SUBJECT=mailto:admin@example.com
```

Le chiavi reali non vanno mai salvate nel repository.

Generare una coppia VAPID fuori dal repository dei segreti:

```bash
python tools/generate_vapid_keys.py --subject mailto:admin@example.com
```

Il comando stampa righe ambiente compatibili con `pywebpush`:

```bash
IUSENTRA_WEB_PUSH_ENABLED=1
IUSENTRA_VAPID_PUBLIC_KEY=...
IUSENTRA_VAPID_PRIVATE_KEY=...
IUSENTRA_VAPID_SUBJECT=mailto:admin@example.com
```

`IUSENTRA_VAPID_PRIVATE_KEY` e' un segreto: va copiato solo nell'ambiente del server o nel secret manager operativo, mai in commit, ticket o screenshot condivisi.

Per verificare la configurazione senza stampare la chiave privata:

```bash
python -m pct.notifications.web_push_diagnostics
```

## Configurazione Hetzner

Sul server CPX42 usare gli script del profilo `deploy/hetzner`:

```bash
cd /opt/iusentra/repo
bash deploy/hetzner/configure_web_push.sh
IUSENTRA_SKIP_BACKUP_CRON=1 bash deploy/hetzner/deploy.sh
bash deploy/hetzner/verify_web_push.sh
```

`configure_web_push.sh` legge `/opt/iusentra/.env.hetzner`, crea il file dal template se manca, genera chiavi VAPID se non presenti, abilita `IUSENTRA_WEB_PUSH_ENABLED=1` e imposta un subject sicuro. Nei log normali non stampa mai la chiave privata; `--print-secrets` va usato solo in debug manuale e con console protetta.
`IUSENTRA_SKIP_BACKUP_CRON=1` evita di aggiornare la pianificazione backup durante questo deploy operativo; rimuovere la variabile quando si vuole mantenere la procedura standard.

`verify_web_push.sh` controlla le variabili ambiente e, se il container app e' raggiungibile, esegue anche la diagnostica backend con `load_web_push_config`.

Opzioni utili:

```bash
bash deploy/hetzner/configure_web_push.sh --force
bash deploy/hetzner/configure_web_push.sh --env-file /percorso/.env
bash deploy/hetzner/verify_web_push.sh --env-file /percorso/.env
```

## API

Tutte le API richiedono autenticazione:

| Metodo | Route | Scopo |
| --- | --- | --- |
| `GET` | `/api/push/public-key` | Restituisce la chiave pubblica VAPID o indica che il canale non e' configurato |
| `POST` | `/api/push/subscribe` | Salva o aggiorna la subscription del dispositivo corrente |
| `DELETE` | `/api/push/subscribe` | Revoca la subscription del dispositivo o dell'endpoint inviato |
| `POST` | `/api/push/test` | Crea una notifica interna di test e prova l'invio Web Push |

Gli endpoint applicano isolamento tenant/utente: una subscription viene letta, aggiornata o revocata solo per lo studio e l'utente correnti.

## Storage

Il repository notifiche usa il database tenant-aware `NOTIFICATIONS_DB`, con default locale `notifications/notifications.db` sotto il data root del tenant.

Sono disponibili gli schemi:

- `pct/sql/20260512_notifications.sql`
- `pct/sql/20260512_notifications_postgres.sql`

Tabelle principali:

- `notifications`
- `push_subscriptions`
- `notification_preferences`
- `notification_deliveries`

Le notifiche usano `dedupe_key` per evitare duplicati e ridurre lo spam.

## Service Worker e manifest

IUSENTRA espone:

- `/sw.js`
- `/manifest.webmanifest`

Il Service Worker ascolta `push`, mostra la notifica con `registration.showNotification` e gestisce `notificationclick`. Al click apre o focalizza IUSENTRA sull'`href` sicuro ricevuto; se manca, usa `/app-v2`.

## Limiti Android, iOS e iPadOS

Android con Chrome, Edge o browser compatibili supporta Web Push PWA in modo ordinario quando l'utente autorizza le notifiche.

Su iPhone e iPad, il supporto dipende dalla versione del sistema e dalle regole del browser. In molti casi la web app deve essere aggiunta alla schermata Home prima che le notifiche siano disponibili. Se il browser non espone `ServiceWorker`, `PushManager` o `Notification`, la UI mostra stato non supportato e non chiede permessi.

IUSENTRA non chiede mai il permesso notifiche al caricamento della pagina: la richiesta parte solo dal click esplicito dell'utente.

## Privacy

Payload Web Push ammessi:

- `IUSENTRA: evento urgente da verificare.`
- `Hai una nuova notifica importante nel gestionale.`
- `E' disponibile una nuova notifica su IUSENTRA.`
- `Richiesta assistenza da <nome studio>.`

Payload vietati:

- nome cliente;
- codice fiscale;
- RG;
- controparte;
- oggetto PEC dettagliato;
- descrizione fascicolo;
- importi specifici;
- dati personali, professionali riservati o giudiziari.

I dettagli restano disponibili solo dopo login dentro IUSENTRA.

## Test manuale

1. Configurare le variabili VAPID e avviare IUSENTRA su HTTPS.
2. Accedere con un utente reale.
3. Da utente loggato aprire `https://DOMINIO/api/push/public-key`.
4. Verificare che risponda con `ok: true`, `configured: true` e `publicKey` valorizzata. La risposta non deve contenere mai la chiave privata.
5. Aprire `Impostazioni > Notifiche`.
6. Verificare lo stato del dispositivo.
7. Premere `Attiva notifiche su questo dispositivo`.
8. Confermare il permesso del browser.
9. Premere `Invia notifica di test`.
10. Chiudere la scheda o mettere il browser in background.
11. Generare un evento importante o urgente, oppure ripetere il test.
12. Cliccare la notifica e verificare che IUSENTRA apra o focalizzi `/app-v2` o la route operativa indicata.

## Troubleshooting

- `Da configurare` o `Sistema notifiche non ancora configurato sul server`: eseguire `bash deploy/hetzner/configure_web_push.sh`, poi `IUSENTRA_SKIP_BACKUP_CRON=1 bash deploy/hetzner/deploy.sh` e `bash deploy/hetzner/verify_web_push.sh`.
- `/api/push/public-key` restituisce `configured: false`: leggere `diagnostics.missing` per individuare se manca abilitazione, public key, private key o subject.
- Il pulsante di attivazione e' disabilitato: browser non supportato, canale non configurato o permesso bloccato.
- Permesso bloccato: riabilitare le notifiche dalle impostazioni del browser o del sistema operativo.
- Test non ricevuto ma notifica interna creata: controllare subscription attiva, HTTPS, Service Worker e log applicativi.
- Endpoint scaduto o non valido: IUSENTRA disabilita la subscription e l'utente deve riattivarla dal dispositivo.
- iOS/iPadOS: aggiungere IUSENTRA alla schermata Home e verificare che il sistema sia aggiornato.

## Fallback futuri

Il motore e' progettato per canali futuri:

- `internal`
- `web_push`
- `email`
- `whatsapp`
- `sms`

IUSENTRA ha gia' moduli WhatsApp/Twilio. In una tranche successiva potranno essere usati come fallback per eventi critici, con consenso e preferenze dedicate, mantenendo gli stessi vincoli privacy del payload Web Push.
