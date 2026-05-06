# Migrazione progressiva Flask + React

## Stato tranche 2026-05-06 - Tranche 4A studio e backup

La terza promozione governata abilita in React full le superfici studio a
rischio medio, mantenendo scritture e operazioni tecniche sui percorsi Flask
legacy:

- `/backup` usa `web/services/react_backup_bridge.py` e
  `GET /api/v1/ui/backup` per KPI, stato ultima copia, storico sicuro e azioni
  legacy; creazione, verifica, download, delete e ripristino restano sulle route
  Flask esistenti.
- `/sito-studio` e `/sito-studio/contatti` usano
  `web/services/react_sito_studio_bridge.py` e gli endpoint
  `GET /api/v1/ui/sito-studio` e
  `GET /api/v1/ui/sito-studio/contatti`, mostrando contenuti, richieste e
  prenotazioni reali senza scritture via fetch.
- `/sito-studio/builder`, `/studio`, `/impostazioni` e
  `/impostazioni?tab=firma` restano legacy, con protezioni esplicite nel gate e
  nella shell.
- `scripts/react-migration/check-tranche-4a-secrets.mjs` verifica che bridge,
  data client e pagine della tranche non serializzino campi riservati nel
  payload React.
- `run-safe-react-migration.mjs --tranche=4a` cattura i contratti legacy,
  rilancia gate/UI/anti-segreti, verifica shell e bypass legacy con Flask
  `test_client`, esegue test/typecheck/build frontend e genera patch separate
  di rollback.

## Stato tranche 2026-05-06 - Tranche 3A amministrazione base

La seconda promozione governata abilita in React full la gestione
amministrativa base, lasciando le scritture sensibili sui POST Flask legacy:

- `/utenti` usa `web/services/react_utenti_bridge.py` e
  `GET /api/v1/ui/utenti` per lista utenti, ruoli, stati, KPI e azioni GET
  sicure; le modifiche e le eliminazioni restano route legacy con
  `?_legacy=1`.
- `GET /utenti/nuovo` viene servita da React con un form standard
  `method="post"` verso `/utenti/nuovo`; non esistono fetch POST o API di
  scrittura nuove, e la password temporanea non viene salvata nello stato
  React.
- `/profili` usa `web/services/react_profili_bridge.py` e
  `GET /api/v1/ui/profili` per matrice ruoli/permessi, override e form legacy
  auditati dove disponibili.
- `/backup` usa `web/services/react_backup_bridge.py` e
  `GET /api/v1/ui/backup` solo come preparazione read-only; il gate mantiene
  `/backup` e tutte le sottoroute in legacy, incluse esecuzione, verifica,
  download, delete e restore.
- `run-safe-react-migration.mjs --tranche=3a` cattura i contratti legacy,
  rilancia gate/UI checks, verifica shell e bypass legacy con Flask
  `test_client`, esegue test/typecheck/build frontend e genera patch separate
  di rollback.

## Stato tranche 2026-05-06 - Tranche 2A read-only

La prima promozione governata abilita in React full solo superfici read-only o a
rischio basso:

- `/statistiche` usa `web/services/react_statistiche_bridge.py` e
  `GET /api/v1/ui/statistiche`, riutilizzando agenda, clienti, fascicoli,
  fatturazione e scadenziario senza introdurre POST nuovi.
- `/audit` e `/registro-attivita` usano `web/services/react_audit_bridge.py`
  e gli endpoint distinti `GET /api/v1/ui/audit` e
  `GET /api/v1/ui/registro-attivita`, mantenendo il permesso legacy
  `audit.leggi`.
- Le pagine dedicate `StatistichePage` e `AuditPage` vivono prima di
  `StudioModulePage`, usano il kit `frontend/src/ui`, stati loading/empty,
  warning tecnici e dati reali, senza Bootstrap nei nuovi TSX e senza mock.
- Il gate rimuove solo `/statistiche`, `/audit` e `/registro-attivita` dai
  blocchi legacy; `?_legacy=1` resta operativo. `/utenti`, `/profili`,
  `/backup`, le aree economiche e quelle telematiche restano bloccate.
- `run-safe-react-migration.mjs --tranche=2a` cattura i contratti legacy,
  rilancia gate/UI checks, verifica la shell con Flask `test_client`, esegue
  test/typecheck/build frontend e genera patch separate di rollback.

## Stato tranche 2026-05-06 - macchina di migrazione governata

La migrazione delle route legacy residue viene governata da una macchina dedicata,
senza sbloccare nuove route nel `react_route_gate` in questa tranche.

- `tools/react-migration/route-manifest.json` censisce le famiglie residue
  amministrazione, studio, economico, mandato, documenti e telematico con stato,
  rischio, target React futuri, bridge/API attesi, contratto legacy e
  `unlockFromGate=false`.
- `scripts/react-migration/audit-react-migration.mjs` legge gate, `App.tsx`,
  `studioModuleData.ts` e `frontend/package.json`, poi produce
  `artifacts/react-migration/route-inventory.json` e `audit.md`.
- `scripts/react-migration/capture-legacy-contracts.py` fotografa il contratto
  HTML legacy con Flask `test_client` su `?_legacy=1`, catturando status, form,
  link, download, Bootstrap e redirect.
- `scripts/react-migration/check-route-gate.mjs` impedisce di dichiarare una
  route sbloccata senza `react_full`, componente dedicato, data client, bridge e
  contratto legacy.
- `scripts/react-migration/check-ui-consistency.mjs` blocca classi Bootstrap nei
  nuovi componenti React, `href="#"`, CDN non consentiti e mock visibili.
- `scripts/react-migration/run-safe-react-migration.mjs` esegue audit, gate,
  consistency, `npm run test`, `npm run typecheck`, `npm run build` e scrive
  report/patch sotto `artifacts/react-migration/`.

Il nuovo kit `frontend/src/ui` fornisce primitive `Page`, `PageHeader`,
`Button`, `Badge`, `Panel`, `KpiCard`, `DataTable`, `FormField`, `EmptyState`,
`LoadingState`, `ActionBar` e `Tabs`, usando solo token `--iu-*` gia' presenti.
Non sostituisce Bootstrap nella shell e non migra route operative: serve a
rendere uniformi le prossime pagine verticali prima della promozione nel gate.

## Stato tranche 2026-05-05 - caricamento progressivo e sincronizzazione

- La Panoramica React legge `/api/v1/ui/dashboard` senza cache busting client-side: il refresh forzato usa solo `refresh=1`, mentre il payload espone metadati tecnici di cache non invasivi.
- La sincronizzazione PEC/email ordinaria parte dopo il primo render tramite `POST /api/v1/ui/dashboard/sync-mailboxes`; il caricamento iniziale resta locale/cache e non esegue IMAP nel builder sincrono.
- Il runtime `web.services.mailbox_sync_runtime` centralizza lock, cooldown, audit e separazione fra `EMAIL_CASELLA_DB` e `EMAIL_ORDINARIA_DB`; le route manuali `/email/sincronizza` e `/email-ordinaria/sincronizza` restano operative come controller sottili.
- `/api/v1/ui/fascicoli` supporta paginazione server-side reale (`page`, `page_size`), filtri (`q`, `type`, `status`, `court`, `alerts_only`) e sort backend, costruendo gli item della sola pagina richiesta.
- Il dettaglio fascicolo mantiene un payload principale leggero e carica documenti, attivita, scadenze, depositi e Regia con endpoint lazy dedicati quando il tab viene aperto.
- La Regia Operativa di fascicolo usa metodi scoped (`preventivi_per_fascicolo`, `conferimenti_per_fascicolo`, `per_fascicolo`) quando disponibili, evitando il caricamento globale non necessario.

## Stato tranche 2026-05-05 - superfici studio operative

- La top bar desktop React e' un centro operativo trasversale: command palette `Ctrl+K`/`Cmd+K`, menu `+ Nuovo` contestuale, pannelli Oggi, Notifiche, Scadenze, Recenti e timer attivita.
- Le nuove superfici leggere leggono solo dati reali da `/api/search/global`, `/api/dashboard/today`, `/api/notifications`, `/api/deadlines/quick-summary`, `/api/recent` e `/api/time-tracking/*`; non esistono fallback demo o `href="#"`.
- Il timer della top bar usa backend tenant-aware e, allo stop, crea una voce timesheet reale collegata a fascicolo/cliente quando indicati.
- `/timesheet` espone shell React, payload `/api/v1/ui/timesheet`, KPI reali, filtri, form nuova attivita, cambio stato e generazione parcella tramite route Flask operative.
- `/cartelle-condivise` espone shell React, payload `/api/v1/ui/cartelle-condivise`, modalita gestore/collaboratore, statistiche privacy e azioni su gestione collaboratori/API esistenti senza mostrare token temporanei.
- `/wizard-pro/`, `/wizard-pro/<id>/step/<n>` e `/wizard-pro/<id>/completo` sono GET React completi; i POST `/wizard-pro/nuovo`, `/wizard-pro/<id>/step/<n>`, `/archivia` ed `/elimina` restano nel blueprint Flask auditato.
- Per queste superfici la vista Jinja resta disponibile solo come fallback tecnico con `?_legacy=1` e non deve comparire nella UI React.

## Regia Operativa nel dettaglio fascicolo

La sezione React `Regia Operativa` e' integrata nel dettaglio fascicolo e legge il payload reale `regia` esposto da `/api/v1/ui/fascicoli/<fascicolo_id>`.

Contratti UI:

- nessun dato demo o hardcoded;
- `mock_fallback=false` nei payload Regia;
- pulsante deposito disabilitato quando il predeposito espone blocchi;
- timeline ricevute visibile solo da repository;
- evidence pack visibile solo quando il repository lo rende disponibile;
- nessuna CTA con `href="#"`.

Le API operative dedicate sono sotto `/api/v1/ui/fascicoli/<fascicolo_id>/regia`, `/checklist`, `/document-slots`, `/predeposito` e `/depositi`.

## Wave Documenti AI Fascicolo

`Documenti AI` e' stato ricondotto a motore interno di indicizzazione Lex: non compare piu' come sezione operativa autonoma nel dettaglio fascicolo e non crea un secondo archivio documentale.

La suite fascicoli mostra invece un box compatto `Indicizzazione Lex` dentro `Documenti fascicolo`: usa payload reali `/api/v1/ui/fascicoli/<fascicolo_id>/lex-indexing`, mantiene `mock_fallback=false`, espone conteggi `ready/queued/indexing/error/stale` e azioni autorizzate `Aggiorna indice` / `Riprova errori`. Upload, import portale e salvataggio editor restano flussi documentali reali del fascicolo e accodano o processano l'indice automatico.

La UI non mostra documenti demo e non introduce una seconda source of truth: storage, estrazione, audit e permessi restano nel dominio backend `pct/document_intelligence`. Le capability avanzate `generate_docx`, `propose_edits` e `compare` restano `false` fino alle tranche MVP 2/3/4 documentate in [DOCUMENTI_AI_FASCICOLO.md](DOCUMENTI_AI_FASCICOLO.md).

## Wave Editor AI Fascicolo

`Generazione atti con Lex` e' integrata nell'editor professionale esistente, non in una pagina separata. La route profonda dell'editor espone nel payload `editorAI` gli endpoint reali per bootstrap, generazione, dettaglio atto AI, proposte modifica ed export.

La UI mostra un pannello compatto `Nuovo atto con Lex` dentro l'editor: sceglie template reali del catalogo atti, istruzioni utente e documenti indicizzati del fascicolo. La generazione crea un documento reale del fascicolo, lo rilegge dal repository editor e poi apre la bozza nell'editor professionale.

Le modifiche successive passano da `Modifiche proposte da Lex`: ogni proposta resta `pending` finche' l'utente non la accetta o rifiuta. L'accettazione aggiorna il documento editor e crea una nuova versione; il rifiuto non muta il contenuto. I dettagli architetturali sono in [EDITOR_AI_FASCICOLO.md](EDITOR_AI_FASCICOLO.md).

## Principio operativo

React diventa la superficie operativa progressiva dell'applicativo, mentre Flask resta backend, source of truth, motore di permessi, tenant, audit e repository. Le scritture sensibili continuano a passare dai servizi Flask gia' auditati fino a quando non esiste una API React equivalente, testata e governata.

La vista Jinja classica non viene eliminata finche' la parita' funzionale non e' verificata. Quando una route GET ufficiale viene promossa a React, la vista classica resta raggiungibile solo come percorso tecnico di assistenza tramite `_legacy=1`; non deve comparire nella UI React come scorciatoia o rollback visibile.

## Pattern OSS adottati come metodo, non come codice

La migrazione progressiva deve seguire il playbook interno [REACT_MIGRATION_PATTERNS_FROM_OSS.md](REACT_MIGRATION_PATTERNS_FROM_OSS.md), ricavato dallo studio temporaneo di Apache Superset, Mattermost e p5.js Web Editor.

Le repo esterne possono essere usate solo come riferimento tecnico per routing, TypeScript incrementale, test, CI e scomposizione dei moduli. Non si importa codice esterno dentro IUSENTRA senza verifica licenza, adattamento al dominio legale e test dedicati.

Ogni pagina deve dichiarare uno stato operativo esplicito:

- `legacy_only`: vista classica completa, nessun React operativo.
- `react_nav_only`: shell/nav React, contenuto operativo classico.
- `react_readonly`: React legge dati reali ma non copre tutte le azioni.
- `react_operational_partial`: React copre azioni reali con limiti documentati.
- `react_operational_complete`: React copre lettura, card, form, download/API, route profonde e test.

Solo `react_operational_complete` puo' essere comunicato come pagina migrata.

## Stato primo blocco React

Il primo blocco e' considerato operativo sulle seguenti superfici:

- Panoramica: `/app-v2`
- Regia Operativa: `/app-v2/regia-operativa`
- Ricerca Studio: `/app-v2/ricerca-studio`
- Agenda: `/app-v2/agenda` e `/app-v2/agenda/nuovo`
- Fascicoli: `/app-v2/fascicoli`, archivio, nuovo/modifica, dettaglio, quadro, editor documento profondo ed export
- Clienti e Anagrafiche: `GET /clienti` e `GET /clienti/nuovo`
- Soggetti e Parti: `GET /soggetti` e `GET /soggetti/nuovo`
- Comunicazioni: `GET /email/`, `GET /messaggi`, `GET /messaggi/nuovo`
- Servizi Telematici: `GET /telematico` e `/app-v2/telematico`, con fallback tecnico `_legacy=1`
- Superfici telematiche di secondo livello: `GET /polisWeb`, `GET /pdp`, `GET /pat`, `GET /sigit`, `GET /tribunali`, `GET /deposito/checklist` e `GET /guida/firma-digitale`, con fallback tecnico `_legacy=1`
- Amministrazione database: `GET /admin/database`, con payload reale, azioni amministrative Flask e fallback tecnico `_legacy=1`

Le pagine del blocco usano dati reali, API bridge sotto `/api/v1/ui/*`, testi visibili in italiano, stati vuoti espliciti e Lex AI contestuale dove previsto. Non sono ammessi mock operativi, dati inventati, profili hardcoded, badge fittizi o copy che presenti la UI React come prototipo temporaneo.

## Contratti API attivi

- `GET /api/v1/ui/bootstrap`
- `GET /api/v1/ui/dashboard`
- `GET /api/v1/ui/agenda`
- `GET /api/v1/ui/fascicoli*`
- `GET /api/v1/ui/fascicoli/<id>/documenti/<id_doc>/editor`
- `GET /api/v1/ui/clienti`
- `GET /api/v1/ui/clienti/nuovo`
- `GET /api/v1/ui/soggetti`
- `GET /api/v1/ui/email`
- `GET /api/v1/ui/messaggi`
- `GET /api/v1/ui/messaggi/nuovo`
- `GET /api/v1/ui/telematico`
- `GET /api/v1/ui/telematico/surface/<surface>`
- `GET /api/v1/ui/privacy/registro`
- `GET /api/v1/ui/admin/database`

I contratti devono dichiarare `mock_fallback=false`. Le superfici che inviano a servizi Flask esistenti dichiarano `writes=operational_routes`.

## Fascicoli: editor documento React

`GET /fascicoli/<id>/documenti/<id_doc>/editor` e' promosso a React con stato `react_operational_complete` per il flusso editor documentale.

- Il payload arriva da `GET /api/v1/ui/fascicoli/<id>/documenti/<id_doc>/editor` e include solo dati reali del fascicolo/documento, capability, endpoint operativi e warning professionali.
- Il contratto dichiara `mock_fallback=false`, `localBundle=true` e `writes=operational_routes`.
- Il contenuto editabile viene letto da `GET /api/editor/<id>/<id_doc>/html` per DOCX, HTML e testo; salvataggio, PDF e DOCX restano sulle route Flask storiche `/salva`, `/pdf` e `/docx`.
- La pagina React non carica TipTap o Mammoth da CDN esterni: toolbar, import locale, ricerca/sostituzione, autosave e stati di salvataggio sono nel bundle Vite.
- La toolbar deve restare comparabile a un editor da studio: stile paragrafo, font, dimensione, interlinea, colori, allineamenti, liste, tabelle, link, ricerca/sostituzione, formato pagina e zoom.
- I PDF devono privilegiare la fedelta visuale: il payload React li marca in sola anteprima nativa, e il backend blocca comunque la conversione quando rileva token `(cid:...)`, stemmi, immagini, riquadri, timbri o testo ruotato/laterale che renderebbero l'HTML diverso dall'originale.
- I documenti firmati `.pdf.p7m` devono restare visualizzabili in anteprima quando il payload CAdES contiene o consente di recuperare un PDF interno.
- La vista Jinja classica resta disponibile solo come fallback tecnico `?_legacy=1`, senza link visibili nella UI utente.

## Servizi telematici: superfici di secondo livello

Le superfici telematiche React sono pagine operative reali, non mock:

- `PolisWeb / PST`, `PDP`, `PAT` e `PTT` filtrano casi, esiti, import incompleti, controlli predeposito ed eventi dal repository telematico reale; su PST la prima azione visibile resta `Importa pratica da PST` e punta al wizard operativo `/portali/pst/acquisizione`.
- `Tribunali / PEC` legge la cache uffici giudiziari reale, espone ricerca e copia PEC, e mantiene le azioni di refresh/report sulle route Flask operative.
- `Checklist deposito` e `Guida firma digitale` salvano solo spunte locali nel browser; le verifiche effettive restano sui servizi Flask e sul Local Signer browser-locale.
- Nessuna superficie scarica autonomamente documenti dai portali o legge HTML dei portali: i collegamenti ufficiali aprono il portale all'utente, mentre l'import resta guidato da file o canali autorizzati.

## Privacy: Registro GDPR

`GET /privacy/registro`, `GET /privacy/registro/nuovo` e l'alias `GET /registro-gdpr` sono promossi a React con stato `react_operational_complete`.

- I dati arrivano dal repository privacy esistente tramite `GET /api/v1/ui/privacy/registro`.
- Il contratto dichiara `mock_fallback=false` e `writes=operational_routes`.
- Il form `Nuovo trattamento` usa il `POST /privacy/registro/nuovo` Flask gia' auditato.
- L'eliminazione usa `POST /privacy/registro/<id>/elimina` e resta quindi protetta da sessione, permessi e audit.
- La vista classica resta disponibile solo come fallback tecnico `?_legacy=1`, senza CTA visibili dalla UI React.
- La pagina espone card operative reali verso audit, clienti, impostazioni e Lex contestuale, oltre a filtri e warning sui campi GDPR essenziali.

## Amministrazione: Gestione Database

`GET /admin/database` e' promosso a React con stato `react_operational_complete`.

- I dati arrivano dal runtime database esistente tramite `GET /api/v1/ui/admin/database`.
- Il contratto dichiara `mock_fallback=false` e `writes=operational_routes`.
- Le azioni React chiamano le route amministrative reali: `GET /admin/database/verifica` per audit in sola lettura, `POST /admin/database/verifica-ripara` per la verifica con riparazione automatica dei problemi referenziali risolvibili, `POST /admin/database/ottimizza`, `POST /admin/database/migra`, `POST /admin/database/attiva-sqlite` e `GET /admin/database/export`.
- La riparazione automatica deve usare solo dati reali: se un riferimento orfano non puo' essere ricollegato a un record univoco, il campo viene scollegato, l'identificativo originale resta nelle note/metadati del record e viene creato un backup JSON prima della scrittura.
- Il profilo utente nella shell React deriva dal profilo reale di sessione (`g.utente_corrente`) e non puo' usare nomi, ruoli, iniziali o badge inventati.
- La vista classica resta disponibile solo come fallback tecnico `?_legacy=1`, senza CTA visibili dalla UI React.

## Comunicazioni: Email PEC e Messaggi

Email PEC e Messaggi sono stati promossi nel primo blocco:

- `GET /email/` serve la shell React Email PEC;
- `GET /messaggi` serve la lista React Messaggi;
- `GET /messaggi/nuovo` serve la composizione React multicanale;
- `POST /messaggi/nuovo` resta sul servizio Flask operativo;
- le azioni PEC restano sui servizi Flask esistenti: sync, auto-esiti, lettura, cestino, ripristino, dettaglio e risposta.
- la Panoramica React (`GET /api/v1/ui/dashboard`) deve usare la stessa casella PEC tenant-aware della pagina `/email/`, ordinare le righe `Ultime PEC ricevute` per data reale decrescente e non filtrare solo su `stato_pct`: le PEC ministeriali prive di esito PCT sono comunque messaggi PEC ricevuti da mostrare fra le ultime.

La sincronizzazione IMAP PEC deve distinguere le cartelle operative:

- `INBOX` -> `INBOX`
- `Sent`, `Sent Items`, `Posta inviata` e alias compatibili -> `INVIATI`
- `Trash`, `Deleted Items`, `Posta eliminata` e alias compatibili -> `CESTINO`

Questa distinzione e' coperta da test per evitare regressioni sulla visibilita' di Inviati e Cestino.

## Design system e performance

- Usare i design token IUSENTRA presenti in `tokens.json`.
- Mantenere testi visibili in italiano.
- Target touch minimo: `44px`.
- Garantire responsive desktop, tablet e mobile.
- Verificare contrasto, focus visibile, heading order, navigazione tastiera e `prefers-reduced-motion`.
- Nessun caricamento esterno non necessario senza consenso.
- Le pagine React del primo blocco sono caricate con code-splitting tramite `React.lazy` e `Suspense`, cosi' il bundle iniziale resta governabile.

## Gate per ogni pagina

- API con dati reali, nessun mock operativo.
- Card e CTA non decorative: ogni card React deve puntare a una route servita, a un download esplicito o a un endpoint/form operativo; sono vietati `#`, `_legacy=1` e link a superfici non migrate nella UI utente.
- UI responsive desktop/tablet/mobile.
- Azioni di scrittura protette da CSRF/sessione, tenant e RBAC.
- Test unitari backend.
- Test frontend: `npm run test`, `npm run typecheck`, `npm run build`.
- Smoke route autenticato su GET ufficiali e API bridge.
- Verifica accessibilita' di base.
- Vista classica disponibile solo come percorso tecnico `_legacy=1`, non come CTA della UI React.
- Documentazione e changelog aggiornati nella stessa tranche.

## Prossime wave

1. Preventivi e Conferimenti.
2. Parcelle, Fatture, Incassi e Pagamenti.
3. Documenti, allegati e upload.
4. Lex AI avanzata.
5. Sito Studio Builder.
6. Firma digitale, Local Signer e portali avanzati.
7. Impostazioni residue e amministrazione avanzata.

Firma digitale, Local Signer e automazioni avanzate dei portali restano in wave dedicate perche' hanno vincoli di compliance, audit, canali separati e conferma consapevole dell'avvocato.

## Comandi di verifica

```powershell
cd D:\legale\IUSENTRA\frontend
npm run test
npm run typecheck
npm run build
```

```powershell
cd D:\legale\IUSENTRA
python -m pytest tests/test_react_shell.py tests/test_email_client.py tests/test_messaggi.py tests/test_web_bootstrap.py -q
```
