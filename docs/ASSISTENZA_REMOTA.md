# Assistenza remota cliente

## Obiettivo

Il modulo `Assistenza remota` permette al `SUPERADMIN` di piattaforma di assistere uno studio cliente con:

- condivisione schermo reale dal browser, senza installare nulla;
- microfono opzionale via WebRTC;
- chat tecnica;
- audit della sessione e dei consensi;
- controllo remoto del PC cliente tramite Local Signer IUSENTRA già installato nello studio, oppure tramite agente dedicato se presente.

La regola prodotto è questa: il cliente vede e approva, l'operatore assiste. Il cliente non deve guardare un secondo monitor dentro la pagina, perché sta già vedendo il proprio desktop; la stanza cliente mostra solo consensi, stato sessione, microfono, chiusura e chat tecnica.

## Superfici prodotto

- `Piattaforma -> Assistenza remota` -> `/admin/supporto-remoto`
- topbar studio -> pulsante `Assistenza`
- richiesta studio autenticata -> `/support/studio/sessione`
- link cliente firmato -> `/support/join/<token>`
- stanza operatore -> `/support/operatore/<public_id>`

La topbar React invia lo stesso contesto della vecchia topbar: nome ed email utente, studio, route corrente, eventuale pratica/cliente e note operative. La richiesta apre la stanza cliente firmata e il `SUPERADMIN` prende in carico la sessione dalla console.

## Schermo e microfono senza installazione

La condivisione schermo parte prima dal browser cliente:

1. il cliente preme `Avvia assistenza`;
2. il browser chiede quale schermo o finestra condividere con `getDisplayMedia()`;
3. il video viaggia via WebRTC;
4. la stanza operatore riceve la traccia con `pc.ontrack` e la mostra nell'area cliente.

Il microfono usa `getUserMedia({ audio: true })` solo se il cliente lascia attivo il consenso audio. Se il browser o il sistema negano il microfono, la sessione continua senza audio e la UI mostra un messaggio operativo non bloccante.

Requisiti browser:

- HTTPS in produzione oppure `localhost`/`127.0.0.1` in locale;
- browser moderno con `getDisplayMedia()` e `getUserMedia()`;
- consenso esplicito del cliente.

## Controllo remoto del PC

Il controllo completo del mouse e della tastiera non passa dal video WebRTC: passa da un servizio locale in loopback, armato solo dopo consenso.

Ordine di rilevamento lato cliente:

1. agente dedicato `IUSENTRA Assistenza` su `http://127.0.0.1:27273`;
2. Local Signer su `http://127.0.0.1:27272/support`.

Il Local Signer dalla versione `1.6.72` espone:

- `GET /support/status`
- `POST /support/arm`
- `POST /support/disarm`
- `POST /support/screenshot`
- `POST /support/execute`

La state machine è token-based:

- l'operatore richiede il controllo PC;
- il cliente approva;
- la pagina cliente arma il Local Signer o l'agente con `session_id` e token;
- ogni comando operatore deve avere sessione armata e token valido;
- a fine sessione il controllo viene disarmato.

Comandi supportati:

- click sinistro;
- click destro;
- doppio click;
- testo;
- tasti rapidi;
- tasti direzionali e operativi esposti in stanza operatore.

Sicurezza:

- solo loopback `127.0.0.1`;
- CORS limitato agli origin IUSENTRA autorizzati;
- token errato rifiutato con `400`;
- origin non consentita rifiutata con `403`;
- nessun controllo PC senza consenso cliente.

## Aggiornamento automatico Local Signer

Il comportamento corretto è automatico:

1. la pagina cliente e il monitor globale provano il Local Signer su `27272`;
2. se la versione è vecchia o manca `/support/status`, chiamano `/update`;
3. se il servizio si riavvia, la pagina attende che `ping` e `/support/status` tornino pronti;
4. solo se il servizio non è installato o non può auto-aggiornarsi viene mostrato il pacchetto manuale.

Il vecchio banner `Installazione Local Signer richiesta` non deve più comparire come primo passo quando un Local Signer raggiungibile può aggiornarsi. Se il servizio è spento o assente, il testo visibile è operativo: `Local Signer non raggiungibile`, con indicazione che IUSENTRA ha già tentato avvio e aggiornamento automatico.

Nota importante: i Local Signer `1.6.68` non avevano le rotte `/support/*`. In quel caso `/support/status` rispondeva `404` e il cliente vedeva il blocco su `Failed to fetch` o `Not found`. Il pacchetto `1.6.72` include `local_signer_mod/support_agent.py` e risolve il problema.

## Packaging Local Signer

Il pacchetto Windows deve restare nel formato certificato già stabilito:

- builder nativo IExpress da `tools/build_local_signer_windows_exe.ps1`;
- file pubblico `SetupLocalSigner-<versione>.exe`;
- alias stabile `SetupLocalSigner.exe`;
- avvio installer con `powershell.exe -NoProfile -ExecutionPolicy Bypass -File installa_local_signer_locale.ps1`;
- file principali copiati dal CAB locale;
- nessun PyInstaller, NSIS o zip autoestraente.

Dal pacchetto `1.6.72` sono obbligatori:

- `local_signer.py`;
- `local_ai_host_bridge.py`;
- `lex_document_context.py`;
- `visible_signature.py`;
- `requirements_local_signer.txt`;
- `uffici_ministero.json`;
- `uffici_pst_pubblici.json`;
- `local_signer_mod/__init__.py`;
- `local_signer_mod/ai_cache.py`;
- `local_signer_mod/ai_handlers.py`;
- `local_signer_mod/pec_bridge.py`;
- `local_signer_mod/security.py`;
- `local_signer_mod/server_bootstrap.py`;
- `local_signer_mod/support_agent.py`.

## Stabilità sessione

La sessione usa:

- WebSocket per signaling e comandi;
- polling di stato come rete di sicurezza;
- nessun blocco su `document.hidden`, così cliente e operatore restano aggiornati anche se una finestra non è in primo piano;
- keep-alive HTTP del Local Signer chiuso per evitare richieste pendenti dal browser;
- conferme comando in chat tecnica.

Se il WebRTC non può partire perché il cliente nega il prompt schermo, la chat resta attiva e il controllo PC può essere armato solo se il cliente approva esplicitamente.

## Verifica reale locale dell'11 giugno 2026

Verifica eseguita sulla copia Docker reale dell'utente `http://127.0.0.1:8080`, versione app `2.251.38`, Local Signer `1.6.72` sulla porta reale `27272`.

Esiti:

- `docker compose up -d --build app scheduler-worker ocr-worker`: container `app`, `scheduler` e `ocr` healthy;
- `GET http://127.0.0.1:8080/api/pronto`: `ok=true`, versione `2.251.38`;
- stanza operatore su `/support/operatore/<public_id>`: renderizzata senza errori console, controlli `Richiedi controllo PC`, `Microfono`, `Muta microfono`, `Schermo intero` presenti;
- stanza cliente su `/support/join/<token>`: nessuna card/monitor scuro di anteprima cliente, consensi schermo/microfono/chat presenti, chat tecnica presente, nessun `Failed to fetch`;
- bootstrap cliente: `localSignerBase=http://127.0.0.1:27272`, `localSignerLatestVersion=1.6.72`;
- pagina studio dopo aggiornamento Local Signer: nessun banner `Installazione Local Signer richiesta`, nessun errore console, nessuna `Pagina temporaneamente non disponibile`;
- Local Signer installato: `GET /ping?light=1` risponde `versione=1.6.72`;
- Local Signer assistenza: `GET /support/status` risponde `IUSENTRA Assistenza (Local Signer)`;
- controllo PC: `/support/arm` OK, `/support/execute` in dry-run OK, token errato `400`, origin non consentita `403`, `/support/disarm` OK.

Limite della prova locale: il browser integrato non ha accettato prompt fisici di condivisione schermo/microfono durante la verifica automatizzata. Sono stati verificati presenza UI, codice WebRTC, assenza errori e disponibilità browser dove accessibile; la cattura audio/video completa resta da confermare con due browser reali e consenso esplicito al prompt.

## Gate minimi prima del rilascio

- `python -m py_compile web/blueprints/react_shell.py web/blueprints/studio_site.py tools/local_signer.py local_signer_mod/support_agent.py tools/dist/local_signer.py tools/dist/local_signer_mod/support_agent.py`
- `node --check web/static/js/local-signer-monitor.js`
- `node --check web/static/js/support_customer_room.js`
- `python -m pytest -q tests/test_support_remote.py`
- `python -m pytest -q tests/test_web_bootstrap.py::test_local_signer_monitor_globale_verifica_versione_e_installer`
- `python -m pytest -q tests/test_build_dist.py tests/test_local_signer.py`
- `pnpm --filter @iusentra/studio build`
- `docker compose up -d --build app scheduler-worker ocr-worker`
- `GET http://127.0.0.1:8080/api/pronto`
- browser reale su `127.0.0.1:8080`: stanza cliente, stanza operatore e pagina studio senza errori console.
