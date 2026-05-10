# Migrazione progressiva Flask + React

## Stato tranche 2026-05-10 - Hotfix contributo unificato Preventivo guidato 2.214.4

Questa tranche chiude il disallineamento segnalato dall'utente nel Preventivo guidato:

- il pannello `Spese vive suggerite` non mostra piu' `Contributo Unificato (indicativo)`, ma la dicitura pulita `Contributo Unificato`;
- dopo il calcolo del wizard React, le pratiche civili di cognizione ordinaria usano ora il contributo unificato coerente con valore e grado della pratica, invece del vecchio importo fisso storico;
- aggiunti test di regressione sul catalogo `Atto di citazione` e sul calcolo wizard per il caso `EUR 10.000 -> EUR 237,00`.

## Stato tranche 2026-05-10 - Eliminazione clienti e soggetti 2.214.2

Questa tranche risponde alla richiesta di ripristinare l'eliminazione operativa
nelle anagrafiche React senza tornare a form legacy:

- `/clienti` espone di nuovo il tasto `Elimina` nelle azioni riga e nelle card
  mobile, con selezione multipla visibile e azione `Elimina selezione`.
- `/soggetti` adotta lo stesso pattern operativo: checkbox su tabella e mobile,
  azione singola `Elimina` e cancellazione multipla dalla toolbar contestuale.
- I payload React di clienti e soggetti includono ora `deleteHref`, mantenendo
  coerenza con i percorsi operativi Flask gia' esistenti.
- Gli endpoint `POST /api/v1/ui/clienti/delete` e
  `POST /api/v1/ui/soggetti/delete` eseguono la cancellazione reale lato studio
  e restituiscono esito JSON al client React.
- Verifiche mirate locali: TypeScript e build Vite verdi; pytest mirati sulla
  cancellazione clienti/soggetti verdi; il gate `check-react-contracts` resta
  da riallineare su un'asserzione storica del Tariffario non collegata a questa
  tranche.

## Stato tranche 2026-05-10 - Performance Tariffario e Preventivo guidato 2.214.1

Questa tranche risponde alla richiesta di velocizzare `/tariffario` e
`/preventivi/wizard` e di rendere raggiungibile il preventivo guidato da
`/preventivi/`:

- `/preventivi/` espone la voce primaria `Preventivo guidato` verso
  `/preventivi/wizard`, anche nello stato vuoto dell'archivio.
- Il bootstrap React del tariffario non invia piu' il catalogo pratiche completo
  con regole e riferimenti normativi pesanti: le opzioni necessarie alla UI
  restano disponibili, mentre i calcoli continuano a usare il motore Python.
- Il bootstrap React del preventivo guidato non duplica piu' `catalog.grouped`,
  non invia righe tassonomiche integrali non usate al primo render e conserva
  solo regole/pratiche compatte sufficienti a filtro, scelta e calcolo.
- Le righe tariffarie derivate sono memorizzate in cache applicativa, evitando
  la ricostruzione ripetuta del catalogo DM 55/DM 147 a ogni apertura pagina.
- Il riepilogo in tempo reale del Tariffario e' tornato sticky su desktop: la
  colonna laterale segue lo scroll dei parametri di calcolo, mentre sotto
  1040px torna nel flusso normale per non comprimere la UI mobile.
- Baseline locale post-fix: `/api/v1/ui/tariffario` 416 KB / 66 ms e
  `/api/v1/ui/preventivi/wizard` 705 KB / 47 ms, contro baseline pre-fix di
  circa 3,87 MB / 30 s e 4,62 MB / 30 s.
- Test mirati aggiunti per bloccare regressioni di payload e link al preventivo
  guidato; verifica browser desktop/tablet/mobile confermata per lo sticky del
  riepilogo e per l'apertura del wizard.

## Stato tranche 2026-05-10 - Pulizia testi visibili e dettagli email React 2.214.0

Questa tranche risponde alla richiesta utente di non mostrare piu' messaggi da
sviluppatore in nessuna scheda operativa e completa i dettagli email indicati:

- La shell React applica una guardia visibile sui testi e sugli attributi
  utente (`title`, `aria-label`, `placeholder`, `alt`) per sostituire termini
  tecnici con lingua da studio legale. La stessa guardia e' caricata anche nei
  template Flask tramite `web/static/js/iusentra-visible-text-guard.js`.
- I termini da non mostrare allo studio includono `Impeccable / Open Design`,
  `Dati applicativi`, `React`, `Flask`, `backend`, `frontend`, `payload`,
  `runtime`, `json_api`, `provider`, `webhook`, `endpoint`, `legacy`,
  `undefined`, `null`, `demo`, `sample` e `repository`.
- `/email/messaggio/<id>` e `/email-ordinaria/messaggio/<id>` sono servite
  dalla pagina React `EmailPecPage`, alimentate da endpoint JSON dedicati e
  complete di metadati operativi, allegati, corpo messaggio e azioni sicure.
- `Redazione Atti` resta su una sola pagina React e include produzione atti,
  template disponibili, compilazione assistita e anteprima operativa, senza
  spostare l'utente su testi o percorsi tecnici.
- `Template Atti`, `Ricerca Legale`, `News`, `Archivio Giurisprudenza`,
  `Statistiche`, `Strumenti Forensi` e `Strumenti Operativi` usano dettaglio in
  pagina, card compatte operative e testi coerenti al design system.
- Browser reale su Docker locale 2.214.0: desktop e mobile per le pagine
  richieste, piu' `/admin/database`, risultano con `#root` React presente,
  nessun overflow orizzontale e nessuno dei termini tecnici vietati nel testo
  visibile.
- Gate confermati: `npm run typecheck`, `npm test`, `npm run build`, route
  gate, full-react contract, no-fake React full, pytest mirati email/React,
  packaging/release readiness, Docker no-cache e readiness locale 2.214.0.

## Stato tranche 2026-05-09 - Pagine operative richieste full React 2.213.0

Questa tranche risponde al controllo utente sul perimetro completo delle pagine
operative IUSENTRA e rende piu' evidente la migrazione React:

- Hotfix Sito Studio/Contatti/Nav: `/sito-studio/contatti` ora resta una
  dashboard React operativa anche quando non ci sono ancora richieste o
  prenotazioni. Mostra ingressi pubblici, modulo contatti, prenotazione, sito
  pubblico, pannelli `Richieste contatto` e `Prenotazioni` con stati vuoti
  specifici, senza lo stato vuoto globale che faceva sembrare la pagina non
  funzionante.
- La sidebar React ora tiene aperta una sola cartella operativa: la sezione
  attiva resta aperta durante la navigazione interna, per esempio `Studio` resta
  aperto su `Statistiche`; quando l'utente seleziona `Fascicoli`, si chiude
  `Studio` e resta aperto solo `Fascicoli`.
- Verifica browser locale su `localhost:8080`: `Contatti Sito Studio` mostra
  `Ingressi pubblici`, `Richieste contatto`, `Prenotazioni`, link pubblici e
  nessun testo tecnico vietato; `Statistiche` mantiene aperto `STUDIO`; il
  passaggio a `Fascicoli` mantiene aperto solo `FASCICOLI`.
- il manifest React e i gate includono le route richieste come
  `react_operational_full` quando esiste una superficie React governata, con
  alias espliciti per Panoramica, Regia Operativa, Ricerca Studio, Agenda,
  Fascicoli, Clienti/Soggetti, Comunicazioni, Scadenze, Preparazione Udienza,
  Studio, Fatturazione, Preventivi, Compensi, Redazione Atti, Statistiche,
  Ricerca Legale, Giurisprudenza, Strumenti, Sito Studio, Amministrazione,
  Utenti, Profili, Registro Attivita, Database e Registro GDPR.
- `frontend/src/formSubmit.ts` e `frontend/src/components/JsonPostForm.tsx`
  centralizzano i submit React con `fetch`, CSRF/sessione, feedback visibile e
  redirect controllato; i componenti full React non devono piu' contenere form
  HTML `method="post"` nel flusso operativo.
- Sono stati convertiti i salvataggi principali di Nuovo Cliente/Soggetto,
  Nuovo Appuntamento, Messaggi/SMS-WA, Nuova Scadenza, Registro GDPR, Agenda,
  Timesheet, Email PEC/ordinaria, Fascicoli e Preparazione Udienza Guidata
  dashboard/step/riepilogo.
- I blueprint Flask collegati restituiscono JSON quando la richiesta arriva da
  React/XHR, mantenendo compatibilita' con redirect e route esistenti.
- Le pagine del perimetro richiesto sono state ripulite dai testi tecnici
  visibili (`backend`, `legacy`, `payload`, `runtime`, `json_api`, `route
  Flask`, `Rollback tecnico`): il linguaggio deve restare operativo per studio
  legale e i fallback devono chiamarsi `Percorso di recupero`.
- Gate confermati in corso tranche: `node frontend/scripts/check-react-contracts.mjs`,
  `node scripts/react-migration/check-full-react-route-contract.mjs` e
  `npm --prefix frontend run typecheck`.
- Restano obbligatori prima della chiusura release: build Vite finale, smoke
  browser desktop/tablet/mobile, Docker locale no-cache/health, commit/push
  branch gemelli e deploy Hetzner verificato.

## Stato tranche 2026-05-09 - Controlli Atti e Strumenti full React 2.210.0

Questa tranche rimuove tre eccezioni `legacy_operational` rimaste sulle voci
richieste dall'utente e le porta nella shell React governata:

- `/deposito/checklist` e' `react_operational_full` nel manifest e apre
  `TelematicoSurfacePage` con payload reale
  `/api/v1/ui/telematico/surface/checklist`; restano legacy solo eventuali
  sottopercorsi non ricostruiti, download o workflow tecnici.
- `/strumenti-legali` e `/strumenti-operativi` sono `react_operational_full`
  nel manifest, aprono `StudioModulePage` e leggono rispettivamente
  `/api/v1/ui/studio-modules/strumenti-forensi` e
  `/api/v1/ui/studio-modules/strumenti-operativi`.
- `web/bootstrap/react_route_gate.py`, `web/blueprints/react_shell.py` e
  `frontend/src/App.tsx` non devono piu' deviare queste route esatte verso la
  vista classica; `?_legacy=1` resta disponibile come fallback storico.
- I gate `check-react-contracts` e `check-route-gate` devono bloccare regressioni
  verso legacy, controllare manifest/contratti e preservare protezioni per
  subpath non migrati.
- La grafica resta vincolata a `docs/UI_DESIGN_SYSTEM.md`: card operative
  compatte, icone Lucide, testi italiani, stati vuoti/errore/successo, nessun
  dato demo e layout responsive senza spazio morto.
- Il titolo visibile della rotta `/deposito/checklist` e' `Controlli Atti`; la
  dicitura `Checklist deposito` resta solo come contesto/azione dove utile.
- Verifica browser reale eseguita con Chrome su desktop 1440x900, tablet
  834x1112 e mobile 390x844 per `/deposito/checklist`, `/strumenti-legali` e
  `/strumenti-operativi`: shell React presente, nessun overflow orizzontale,
  azioni/card operative visibili e nessun testo tecnico `payload`, `backend`,
  `frontend`, `runtime`, `json_api`, `undefined`, `null`, `todo` o `sample`.

## Stato tranche 2026-05-09 - Impostazioni full React 2.209.0

Questa tranche porta le impostazioni operative principali fuori dal template
storico e dentro una superficie React completa, mantenendo le scritture sensibili
nei servizi applicativi:

- `/impostazioni` e `/impostazioni-studio` sono `react_operational_full` nel
  manifest e vengono servite dalla shell React; `/impostazioni/pagamenti`,
  `/notifiche`, `/notifiche-whatsapp`, `/backup`, `/impostazioni/calendario`
  e `/sincronizzazione-calendari` sono alias React della stessa pagina
  Impostazioni.
- Il bridge `web/services/react_impostazioni_bridge.py` espone Dati Studio, PEC,
  Firma Digitale, Email SMTP, WhatsApp, Scheduler, AI Locale, Pagamenti,
  Notifiche, Backup e Calendari tramite `/api/v1/ui/impostazioni`, con
  salvataggi JSON/multipart per singola sezione, audit e permessi coerenti con
  il dominio.
- Password, token e chiavi salvate non vengono riesposte in chiaro dal server:
  React mostra solo stato/placeholder; l'icona occhio permette di controllare il
  nuovo valore digitato prima del salvataggio.
- La scheda Email SMTP conserva l'aiuto operativo per Gmail/Google Workspace:
  sotto `Password email` chiarisce che serve la password per le app Google e
  collega la pagina ufficiale di generazione.
- La firma digitale usa il browser per verificare IUSENTRA Local Signer su
  `127.0.0.1:27272`, accetta `token_probe_fresh` e conserva i download installer.
- AI Locale dispone di stato e bootstrap JSON dedicati, ma la verifica utente
  finale deve passare dal PC in uso tramite IUSENTRA Local Signer: React chiama
  `/ai/status` e `/ai/bootstrap` sul companion locale, mostra `Prepara AI
  locale`, lascia i modelli in scelta automatica e spiega che IUSENTRA controlla
  RAM/spazio/profilo hardware prima di scegliere i modelli.
- La shell React carica anche `web/static/js/react-ai-local-guard.js` per
  proteggere asset React gia' compilati: eventuali vecchie chiamate
  `/api/v1/ui/impostazioni/ai/status` e `/api/v1/ui/impostazioni/ai/bootstrap`
  vengono instradate al Local Signer del browser, non usate come fonte finale
  server/cloud.
- I gate anti-mascheramento classificano le route AI Locale come full React
  senza bridge fittizi e `tests/test_impostazioni_ai_locale_react.py` blocca
  regressioni su Local Signer, messaggi operativi e scelta automatica modelli.
- Pagamenti usa `web/services/react_impostazioni_payments.py` per leggere e
  salvare configurazione canali, bonifico, chiavi riservate e stato link senza
  riesporre segreti; l'utente vede linguaggio operativo, non `provider`,
  `webhook`, `legacy` o codici interni.
- Notifiche usa `web/services/react_impostazioni_notifications.py` e gli endpoint
  `/api/v1/ui/impostazioni/notifiche/*` per preparare link WhatsApp, inviare
  messaggi/promemoria e aggiornare il registro da dati reali di clienti e agenda.
- Backup usa `web/services/react_impostazioni_backup.py` per mostrare copia,
  verifica, download protetto e permessi dentro la scheda Impostazioni, mentre
  `/backup` resta un alias della stessa esperienza.
- Calendari usa `web/services/react_impostazioni_calendar.py` e gli endpoint
  `/api/v1/ui/impostazioni/calendari/*` per link riservati, profili calendario,
  sincronizzazione manuale, rigenerazione link e audit.
- Il menu React sposta Notifiche, Pagamenti, Backup e Sincronizzazione Calendari
  nel gruppo `Impostazioni`, fuori dal gruppo `Studio`, cosi' la navigazione
  riflette il modello unico richiesto.

## Stato tranche 2026-05-09 - Statistiche full React 2.208.0

Questa tranche chiude il bridge reale residuo su `/statistiche` senza toccare
aree sensibili o portali:

- `tools/react-migration/route-manifest.json` promuove `/statistiche` a
  `react_operational_full` con `writes=none`, dati JSON reali e
  `unlockFromGate=true`.
- `web/services/react_statistiche_bridge.py` non restituisce piu' azioni
  `?_legacy=1` nemmeno nel payload di errore controllato; la pagina puo'
  soltanto riprovare la lettura React.
- I gate anti-mascheramento devono classificare 27 route full reali e 0 bridge
  residui; le route legacy restano quelle ad alto rischio per segreti, export,
  documenti, impostazioni e portali telematici.

## Stato tranche 2026-05-08 - Design system IUSENTRA shadcn/lucide 2.198.121

Questa tranche integra la base grafica governata per rendere le superfici React
piu' professionali senza promuovere nuove route e senza sostituire logiche
backend:

- `frontend/components.json`, `frontend/src/components/ui/*` e
  `frontend/src/lib/utils.ts` introducono shadcn/ui su Vite/React con alias
  `@/*`, primitive Radix e classi componibili.
- `frontend/src/design/iusentraTokens.ts` e
  `frontend/src/styles/iusentra-design-system.css` definiscono palette blu
  notte, oro tenue, grigi neutri, superfici operative, focus ring, stati e
  mappa Lucide per le aree legali.
- `frontend/src/components/iusentra/*` aggiunge componenti riutilizzabili per
  shell, sidebar, top bar, header, metriche, action card, badge, stati vuoti,
  form section, pannelli collassabili, data table shell, icone e Lex floating
  button.
- I wrapper storici `frontend/src/ui/*`, la dashboard condivisa e i layout
  esistenti vengono normalizzati verso il nuovo sistema mantenendo i contratti
  statici usati dai gate React.
- La guida operativa vive in `docs/UI_DESIGN_SYSTEM.md` e descrive librerie,
  struttura, token, icone, pattern pagina, form, toolbar, accessibilita e divieti
  per evitare template, dati demo o componenti duplicati.

## Stato tranche 2026-05-08 - Architettura Full React governata 2.198.120

Questa tranche crea la base governata della migrazione Full React senza
dichiarare complete le route che restano bridge o legacy:

- `artifacts/react-migration/full-react-audit.*` censisce 53 route del manifest
  con stato reale, componenti React, bridge backend, endpoint JSON, presenza di
  `_legacy=1`, POST HTML, dati mock/demo, rischio e workspace di destinazione.
- `tools/react-migration/route-manifest.json` dichiara `workspaceTarget` per
  ogni route censita; gli stati esistenti non vengono promossi se manca parita'
  operativa.
- `frontend/src/app`, `frontend/src/shell`, `frontend/src/api` e
  `frontend/src/features/*` introducono la grammatica Full React: route
  applicative, shell unica, client API JSON/CSRF centralizzato e workspace
  consolidati che riusano i data client esistenti invece di duplicare logiche
  backend.
- `frontend/src/theme/legal-ui.css` e le primitive in `frontend/src/ui/*`
  aggiungono layout, card operative, filtri, drawer, modali, stati, pannelli e
  sticky action bar tokenizzati per la UI legale professionale.
- I runner `scripts/react-migration/run-full-react-migration.mjs` e
  `scripts/react-migration/run-legal-ui-checks.mjs` aggregano i nuovi gate
  anti-mascheramento, anti-mock, anti-logica canonica frontend, responsive e
  anti-Bootstrap primario.

## Stato tranche 2026-05-07 - Parti 22A-25A economico, tariffario e audit operativi 2.198.118

Le Parti 22A-25A chiudono il blocco economico principale e portano audit e
registro attivita a superfici React pienamente operative senza spostare logiche
canoniche nel frontend:

- `/incassi-pagamenti` usa `GET /api/v1/ui/incassi-pagamenti` e le azioni JSON
  supportate per registrare incassi manuali, aggiornare stati, collegare fatture
  e recuperare link pagamento solo tramite backend. Provider, webhook e
  configurazioni riservate restano legacy/backend; React vede solo stato pubblico.
- `/compensi-forensi` legge parametri reali e invia il calcolo a
  `POST /api/v1/ui/compensi-forensi/calcola`; DM55, risultato economico, logica
  fiscale e creazione preventivo restano backend o azioni esplicitamente
  supportate.
- `/tariffario` legge versioni, aree, fasi, voci e scaglioni dal backend e usa
  `POST /api/v1/ui/tariffario/calcola` quando il calcolo e disponibile; nessuna
  formula, scaglione o tabella canonica viene duplicata in React.
- `/audit` e `/registro-attivita` usano payload reali da
  `GET /api/v1/ui/audit` e `GET /api/v1/ui/registro-attivita`, dettaglio sicuro
  via `GET /api/v1/ui/audit/<id_evento>` e payload sanificati dal bridge.
- I fallback `?_legacy=1` restano solo rollback tecnici o impostazioni provider
  legacy; le sottoroute `/incassi-pagamenti/*`, `/compensi-forensi/*` e
  `/tariffario/*` restano legacy/protette dal gate.

## Stato tranche 2026-05-07 - Parti 18A-21A preventivi e fatturazione operative 2.198.114

Le Parti 18A-21A completano le superfici operative mandato/economico gia'
avviate dopo `/fatturazione/nuova`:

- `/preventivi/nuovo` usa `GET /api/v1/ui/preventivi/nuovo` e
  `POST /api/v1/ui/preventivi/nuovo`; React raccoglie clienti, fascicoli,
  voci e opzioni fiscali come input, mentre calcolo canonico, parametri
  forensi, numerazione e persistenza restano in `GestionePreventivi`.
- `/preventivi/conferimento/nuovo` usa
  `GET/POST /api/v1/ui/preventivi/conferimento/nuovo`, precompila da
  `id_preventivo` quando presente e conserva generazione documento, firme e
  apertura fascicolo nei workflow backend/legacy.
- `/preventivi` usa `GET /api/v1/ui/preventivi`,
  `GET /api/v1/ui/preventivi/<id_preventivo>` e
  `POST /api/v1/ui/preventivi/<id_preventivo>/stato` per archivio reale,
  dettaglio sintetico e cambio stato supportato; archivia/annulla/duplica
  restano disabilitate se non esiste una semantica legacy sicura.
- `/fatturazione` usa `GET /api/v1/ui/fatturazione`,
  `GET /api/v1/ui/fatturazione/<id_documento>` e POST JSON per stato,
  annulla e segna pagata. PDF, XML, export e calcoli fiscali canonici restano
  backend/legacy; React non usa fetch blob o generazione documenti.
- Tutte le CTA `_legacy=1` rimaste sono confinate a `Rollback tecnico`; il
  gate continua a proteggere `/preventivi/*` non autorizzati,
  `/preventivi/wizard` resta invariato e `/fatturazione/*` diverso da
  `/fatturazione/nuova` resta legacy/protetto.

## Stato tranche 2026-05-07 - Parte 17A fatturazione nuova operativa 2.198.110

La Parte 17A promuove `/fatturazione/nuova` da `react_bridge` a
`react_operational_full` senza sbloccare dettagli, modifica, PDF, XML, export,
provider pagamenti o webhook:

- `GET /api/v1/ui/fatturazione/nuova` espone clienti, fascicoli, default del
  form, opzioni fiscali e contratto `writes=json_api`,
  `canonical_calculation=backend`, `operational=true`, senza mock fallback.
- `POST /api/v1/ui/fatturazione/nuova` accetta solo JSON, usa
  CSRF/sessione, permesso `fatturazione.scrivi`, validazione backend,
  rifiuto di campi ignoti e degli importi canonici inviati dal frontend.
- Il salvataggio riusa `GestioneFatturazione.crea()` e `VoceParcella`; React
  invia solo voci/opzioni e non calcola totali fiscali, PDF, XML o export.
- `LegacyPostForm` e CTA legacy primarie sono rimossi dal flusso principale;
  `/fatturazione/nuova?_legacy=1` resta solo nel pannello `Rollback tecnico`.
- `/fatturazione` puo' restare `react_bridge`, mentre `/fatturazione/*` resta
  `legacy_operational` e protetto dal gate con eccezione solo per
  `/fatturazione/nuova`.

## Stato tranche 2026-05-07 - Parte 16A backup operativo 2.198.109

La Parte 16A promuove `/backup` da `react_bridge` a
`react_operational_full` mantenendo protette tutte le sottoroute `/backup/*`:

- `GET /api/v1/ui/backup` espone stato backup reale, lista copie, stato
  integrita, permessi operativi e contratto `writes=json_api`,
  `operational=true`, `restore_migrated=false`, senza path assoluti,
  contenuto file, stack trace o segreti.
- `POST /api/v1/ui/backup/crea` crea una copia tramite `GestioneBackup`,
  non accetta destinazioni o path dal frontend, richiede CSRF/sessione e
  permesso `backup.esegui`, registra audit `backup.crea` e restituisce solo
  metadati sicuri.
- `POST /api/v1/ui/backup/verifica` richiama la verifica integrita del
  repository legacy, richiede CSRF/sessione e `backup.esegui`, registra audit
  `backup.verifica` e non restituisce hash o percorsi file.
- `BackupPage` rimuove `LegacyPostForm` dal flusso principale, usa
  `createBackup()` e `verifyBackupIntegrity()`, mostra loading, saving,
  success, error, validazione, empty state, permessi e filtri locali sui dati
  gia ricevuti.
- Il download resta un link backend sicuro verso la route esistente; restore
  e delete non sono migrati in React e il fallback `/backup?_legacy=1` resta
  solo nel pannello `Rollback tecnico`.

## Stato tranche 2026-05-07 - Parte 14A utenti operativi 2.198.108

La Parte 14A promuove `/utenti` da `react_operational_partial` a
`react_operational_full` senza sbloccare sottoroute utenti ulteriori:

- `GET /api/v1/ui/utenti` espone utenti reali, ruoli gestibili, stato account,
  metriche, permessi operativi e contratto `writes=json_api`, senza
  `password_hash`, reset token, segreti TOTP o dati di sessione.
- `POST /api/v1/ui/utenti/<id>/stato`, `/ruolo`, `/reset-password` e
  `/profilo` applicano `_richiedi_auth`, CSRF browser, permesso
  `utenti.scrivi`, validazione JSON, blocchi su `SUPERADMIN`, ultimo
  amministratore e auto-disabilitazione, e audit dedicato nel manager utenti.
- `frontend/src/components/UtentiPage.tsx` usa ricerca/filtro client-side sui
  dati gia ricevuti e azioni inline/modali leggere via API JSON per profilo
  minimo, ruolo, stato account e credenziale temporanea; `LegacyPostForm` e
  CTA primarie `?_legacy=1` sono assenti.
- `/utenti?_legacy=1` resta disponibile solo come `Rollback tecnico`;
  `/utenti/nuovo` resta `react_operational_full` e le altre route
  `/utenti/*` restano protette dal gate finche' non avranno UI React reale.

## Stato tranche 2026-05-07 - Parte 13A profili operativi 2.198.107

La Parte 13A promuove `/profili` da `react_bridge` a
`react_operational_full` senza modificare il modello RBAC esistente:

- `GET /api/v1/ui/profili` espone ruoli gestibili, catalogo permessi, matrice
  ruolo-permesso e override utente reali, senza password, hash o dati di
  sessione.
- `POST /api/v1/ui/profili` salva gli override utente tramite
  `GestioneUtenti.aggiorna_permessi`, con `_richiedi_auth`, CSRF browser,
  permesso `utenti.scrivi`, validazione JSON, blocco SUPERADMIN tenant e audit
  `utenti.aggiorna_permessi`.
- `frontend/src/components/ProfiliPage.tsx` non usa piu' `LegacyPostForm` nel
  flusso principale: la UI mostra loading, dirty state, saving, success,
  errori di validazione, permesso negato, stato vuoto, matrice reale e rollback
  legacy solo nel pannello `Rollback tecnico`.
- Il manifest dichiara `/profili` come `react_operational_full` con
  `writes=json_api`; `?_legacy=1` resta disponibile solo come fallback tecnico.

## Stato tranche 2026-05-07 - Parte 12A anti-mascheramento 2.198.106

La Parte 12A cambia la definizione di migrazione React: una pagina non puo'
essere dichiarata pienamente operativa se il flusso principale torna a template
Flask, CTA `?_legacy=1`, `LegacyPostForm` o POST legacy.

- `tools/react-migration/route-manifest.json` usa ora gli stati
  `react_shell`, `react_bridge`, `react_operational_partial`,
  `react_operational_full` e `legacy_operational`; `react_full` resta
  deprecato e non viene piu' usato per superfici mascherate.
- `scripts/react-migration/audit-anti-mascheramento.mjs` censisce link
  legacy, form legacy, bridge con scritture legacy, API mancanti e stati UI,
  generando report JSON/Markdown in `artifacts/react-migration/`.
- `scripts/react-migration/check-no-fake-react-full.mjs` blocca manifest e
  gate quando una route piena dipende ancora da legacy per il flusso primario.
- Il pilota `/utenti/nuovo` usa React controllato e
  `POST /api/v1/ui/utenti/nuovo`, con `_richiedi_auth`, permesso
  `utenti.scrivi`, CSRF/sessione, audit e risposta JSON senza password.
- I fallback `?_legacy=1` restano solo rollback tecnici non primari; le route
  ancora bridge/shell restano dichiarate come tali fino a API JSON complete,
  permessi, stati UI e test dedicati.

## Stato tranche 2026-05-07 - Legal knowledge React read-only 2.198.105

La decima promozione governata abilita le superfici di consultazione giuridica
senza spostare import, classificazione, testo integrale, approvazione contenuti
o AI fuori dalle route Flask legacy:

- `/giurisprudenza` usa `web/services/react_giurisprudenza_bridge.py` e
  `GET /api/v1/ui/giurisprudenza` per KPI, fonti, filtri e metadati di
  provvedimenti/sentenze gia presenti nel repository.
- `/legal-intelligence`, `/legal-intelligence/news`,
  `/legal-intelligence/mediazione` e `/ricerca-legale` usano
  `web/services/react_legal_intelligence_bridge.py` e endpoint GET dedicati
  per dashboard monitor, news pubblicate, registro mediazione e hub di ricerca
  legale, senza fetch esterno o pipeline nuova.
- Restano legacy `/giurisprudenza/nuova`, `/giurisprudenza/*`,
  `/legal-intelligence/*` diverso da news/mediazione, `/ricerca-legale/*`,
  `/checklist` e `/deposito/checklist`.
- Impeccable / Open Design aggiunge token legal knowledge `--iu-od-source-*`
  e utility `iu-od-source-card`, `iu-od-source-badge`,
  `iu-od-evidence-panel`, `iu-od-inference-warning` e
  `iu-od-legal-list`, distinguendo fonte, metadato, warning, inferenza e
  azioni legacy senza dipendenze grafiche.
- `run-safe-react-migration.mjs --tranche=10a` cattura contratti legacy,
  rilancia gate/UI, anti-segreti, anti-fetch esterno, anti-generazione AI,
  anti-documento raw, Open Design, test Flask, `npm run test`, typecheck e
  build, poi genera patch di rollback separate.

## Stato tranche 2026-05-07 - Tariffario console operativa 2.198.102

La tranche `2.198.102` rifinisce `/tariffario` come console economica
professionale:

- gli avvisi tecnici di bootstrap e le KPI statistiche non vengono piu'
  renderizzati sopra il workspace operativo;
- il `Riepilogo in tempo reale` diventa il pannello sticky dedicato su desktop,
  con totale, forbice minimo/base/massimo e azioni principali nello stesso
  punto di lavoro;
- il risultato viene aggiornato automaticamente con debounce tramite
  `POST /api/v1/ui/tariffario/calcola`, continuando a usare solo il motore
  Python canonico per formule, importi e logica tariffaria.

## Stato tranche 2026-05-06 - Tariffario console operativa 2.198.97

La superficie exact `/tariffario` resta React sui GET ufficiali e mantiene il
fallback tecnico `?_legacy=1`, ma non e' piu' una semplice consultazione:

- `web/services/react_tariffario_bridge.py` espone catalogo, stato iniziale,
  risultato, profilo attivo, audit, tabelle, riferimenti, canali fatturazione e
  CTA precompilate usando dati reali da repository e servizi esistenti.
- `POST /api/v1/ui/tariffario/calcola` aggiorna il quadro operativo con il
  motore Python (`calcola_compenso`, `motore_preventivo`, mediazione D.M.
  150/2023, spese vive e voci manuali), senza spostare formule o valori
  normativi nel frontend.
- `frontend/src/components/TariffarioPage.tsx` organizza la pagina come console
  a due colonne con hero, KPI, parametri, accordion, risultato tabellare,
  riepilogo economico, profilo attivo e supporto normativo collassabile.
- I gate Tranche 8A anti-segreti, anti-calcolo compensi e anti-produzione
  documentale restano attivi: React invia parametri e riceve risultati, ma non
  contiene formule tariffarie, fiscali o documentali canoniche.

## Stato tranche 2026-05-06 - Tranche 9A template e redazione atti

La promozione governata abilita le superfici documentali di ingresso in React
senza spostare editor, redazione guidata, produzione file o workflow AI fuori
dalle route Flask legacy:

- `/template-atti` usa `web/services/react_template_atti_bridge.py` e
  `GET /api/v1/ui/template-atti` per dashboard catalogo, KPI reali,
  categorie, materie, canali e link sicuri.
- `/template-atti/catalogo` usa lo stesso bridge e
  `GET /api/v1/ui/template-atti/catalogo` per consultare il catalogo reale,
  metadati template, compliance e variabili solo come nomi/metadati.
- `/redazione-atti` usa `web/services/react_redazione_atti_bridge.py` e
  `GET /api/v1/ui/redazione-atti` per quadro operativo, workflow disponibili,
  fonti collegate come metadati e azioni verso template, fascicoli, preventivi
  e checklist legacy.
- `/template-atti/nuovo`, `/template-atti/*`, `/redazione-atti/*`,
  `/checklist`, `/deposito/checklist`, `/giurisprudenza`,
  `/legal-intelligence` e `/ricerca-legale` restano legacy con protezioni
  esplicite nel gate e nella shell.
- Impeccable / Open Design resta interno: token CSS documentali `--iu-od-doc-*`,
  utility `iu-*`, nessuna dipendenza grafica, nessun CDN e check dedicato.
- `run-safe-react-migration.mjs --tranche=9a` cattura i contratti legacy,
  rilancia gate/UI, anti-segreti, anti-contenuto integrale, anti-redazione
  automatica, anti-produzione file, Open Design, test Flask,
  test/typecheck/build frontend e patch separate di rollback.

## Stato tranche 2026-05-06 - Tranche 8A compensi e tariffario sicuri

La settima promozione governata abilita le superfici economiche exact di
consultazione compensi/tariffario in React senza spostare formule forensi,
produzione documentale o workflow mandato fuori dalle route Flask legacy:

- `/compensi-forensi` usa `web/services/react_compensi_forensi_bridge.py` e
  `GET /api/v1/ui/compensi-forensi` per KPI reali, aree disponibili, profili e
  regole lette dal backend, link sicuri verso tariffario, preventivi e vista
  legacy tecnica.
- `/tariffario` usa `web/services/react_tariffario_bridge.py` e
  `GET /api/v1/ui/tariffario` per consultare profili, regole, riferimenti,
  audit e form HTML `method="post"` verso la route Flask esistente; il calcolo
  resta nel backend storico.
- `/compensi-forensi/*`, `/tariffario/*`,
  `/preventivi/*`, `/fatturazione/*`, `/template-atti` e `/redazione-atti`
  restano legacy con protezioni esplicite nel gate e nella shell.
- I token `frontend/src/theme/impeccable-open-design.css` e il contratto
  `frontend/src/ui/openDesign.ts` applicano una disciplina Open Design
  auditabile senza dipendenze runtime, CDN o design system esterni.
- `scripts/react-migration/check-tranche-8a-secrets.mjs`,
  `scripts/react-migration/check-tranche-8a-no-compensi-logic.mjs`,
  `scripts/react-migration/check-tranche-8a-no-document-generation.mjs` e
  `scripts/react-migration/check-tranche-8a-open-design.mjs` bloccano
  serializzazione di campi riservati, logica compensi frontend, generazione
  documentale e regressioni visuali fuori dai token `iu-*`.
- `run-safe-react-migration.mjs --tranche=8a` cattura i contratti legacy,
  rilancia gate/UI/anti-segreti/anti-calcolo/anti-documenti/Open Design,
  verifica shell e bypass legacy con Flask `test_client`, esegue
  test/typecheck/build frontend e genera patch separate di rollback.

## Stato tranche 2026-05-06 - Tranche 8A compensi e tariffario sicuri

La settima promozione governata abilita due superfici economiche exact in
React senza spostare formule, wizard, log economici o produzione documentale
fuori dalle route Flask legacy:

- `/compensi-forensi` usa `web/services/react_compensi_forensi_bridge.py` e
  `GET /api/v1/ui/compensi-forensi` per KPI reali quando disponibili, aree di
  calcolo lette dal backend, profili/regole sicuri e link a tariffario,
  preventivi e wizard legacy.
- `/tariffario` usa `web/services/react_tariffario_bridge.py` e
  `GET /api/v1/ui/tariffario` per aree tariffarie, voci/regole provenienti dal
  backend e un form React che invia con submit HTML standard alla route Flask
  `/tariffario`.
- `/compensi-forensi/*`, `/tariffario/*`,
  `/preventivi/*`, `/fatturazione/*`, `/template-atti` e `/redazione-atti`
  restano legacy con protezioni esplicite nel gate e nella shell.
- `frontend/src/theme/impeccable-open-design.css` e
  `frontend/src/ui/openDesign.ts` introducono solo token/contratto interno
  Impeccable / Open Design, senza dipendenze nuove, CDN, classi Bootstrap o
  colori hardcoded nei TSX.
- `scripts/react-migration/check-tranche-8a-secrets.mjs`,
  `scripts/react-migration/check-tranche-8a-no-compensi-logic.mjs`,
  `scripts/react-migration/check-tranche-8a-no-document-generation.mjs` e
  `scripts/react-migration/check-tranche-8a-open-design.mjs` bloccano
  serializzazione di campi riservati, logica compensi frontend, generazione
  documentale e regressioni grafiche della tranche.
- `run-safe-react-migration.mjs --tranche=8a` cattura i contratti legacy,
  rilancia gate/UI/anti-segreti/anti-calcolo/anti-documenti/Open Design,
  verifica shell e bypass legacy con Flask `test_client`, esegue
  test/typecheck/build frontend e genera patch separate di rollback.

## Stato tranche 2026-05-06 - Tranche 7A mandato sicuro

La sesta promozione governata abilita il blocco mandato exact in React senza
spostare calcoli, wizard, documenti o cambi di stato fuori dalle route Flask
legacy:

- `/preventivi` usa `web/services/react_preventivi_bridge.py` e
  `GET /api/v1/ui/preventivi` per KPI reali, archivio preventivi/conferimenti,
  stati, cliente, fascicolo, importi gia' presenti nel modello e link legacy
  sicuri.
- `/preventivi/nuovo` usa lo stesso bridge e
  `GET /api/v1/ui/preventivi/nuovo`, ma il submit resta un form HTML
  `method="post"` verso la route legacy auditata; il motore economico resta nel
  backend storico.
- `/preventivi/conferimento/nuovo` usa
  `GET /api/v1/ui/preventivi/conferimento/nuovo`, con form React verso il POST
  legacy; firme, stati, produzione documenti e apertura fascicolo restano nel
  workflow Flask.
- `/preventivi/wizard` e' promosso in React full tramite
  `web/services/react_preventivo_wizard_bridge.py` e gli endpoint
  `/api/v1/ui/preventivi/wizard`, `/calculate` e `/create`; i dettagli
  `/preventivi/*` restano legacy con protezioni esplicite nel gate e nella shell.
  La tranche `2.198.100` porta riepilogo e riferimenti nella colonna sinistra,
  mantiene classificazione operativa/tassonomia come metadati silenziosi,
  aggiunge il pulsante reale `Aggiungi voce area pratica` e compatta lo sticky
  footer su desktop e mobile, protegge i profili solo a `Compenso unico` da
  bozze a zero e vincola il conferimento alla previa accettazione cliente del
  preventivo senza spostare formule economiche nel frontend.
  La tranche `2.198.101` rende il flag `Compenso unico` una scelta effettiva:
  acceso calcola la voce unica, spento calcola le sole fasi selezionate
  dall'avvocato con riparto operativo tracciato quando la tabella ministeriale
  espone solo l'importo unico; le voci area pratica aggiunte entrano tutte
  nella bozza con compenso e spese, non soltanto l'ultima pratica attiva.
- `scripts/react-migration/check-tranche-7a-secrets.mjs`,
  `scripts/react-migration/check-tranche-7a-no-compensi-logic.mjs` e
  `scripts/react-migration/check-tranche-7a-no-document-generation.mjs`
  bloccano serializzazione di campi riservati, logica compensi frontend e
  produzione documentale nella nuova superficie.
- `run-safe-react-migration.mjs --tranche=7a` cattura i contratti legacy,
  rilancia gate/UI/anti-segreti/anti-calcolo/anti-documenti, verifica shell e
  bypass legacy con Flask `test_client`, esegue test/typecheck/build frontend e
  genera patch separate di rollback.

## Stato tranche 2026-05-06 - Tranche 6A economico sicuro

La quinta promozione governata abilita il primo blocco economico exact in React
senza spostare calcoli fiscali, documenti o provider fuori dalle route Flask
legacy:

- `/fatturazione` usa `web/services/react_fatturazione_bridge.py` e
  `GET /api/v1/ui/fatturazione` per KPI reali, archivio parcelle/fatture,
  stati, clienti, importi gia' presenti nel modello e link legacy sicuri.
- `/fatturazione/nuova` usa lo stesso bridge e
  `GET /api/v1/ui/fatturazione/nuova` piu'
  `POST /api/v1/ui/fatturazione/nuova`: il submit React e' JSON-only,
  validato dal backend e salvato tramite il manager fatturazione esistente.
  Il calcolo canonico resta nel backend storico.
- `/incassi-pagamenti` usa `web/services/react_incassi_pagamenti_bridge.py` e
  `GET /api/v1/ui/incassi-pagamenti` per importi aggregati, stato provider in
  forma sicura e collegamenti a configurazione provider legacy.
- `/fatturazione/*` diverso da `/fatturazione/nuova`, PDF, XML, export CSV, `/impostazioni/pagamenti`,
  `/preventivi`, `/compensi-forensi` e `/tariffario` restano legacy con
  protezioni esplicite nel gate e nella shell.
- `scripts/react-migration/check-tranche-6a-secrets.mjs` e
  `scripts/react-migration/check-tranche-6a-no-fiscal-logic.mjs` bloccano
  serializzazione di campi riservati e logica fiscale canonica nel frontend.
- `run-safe-react-migration.mjs --tranche=6a` cattura i contratti legacy,
  rilancia gate/UI/anti-segreti/anti-calcolo, verifica shell e bypass legacy
  con Flask `test_client`, esegue test/typecheck/build frontend e genera patch
  separate di rollback.

## Stato tranche 2026-05-08 - Tranche 26A/27A regia studio, amministrazione e sito

La tranche anti-mascheramento 26A/27A promuove gli hub direzionali e il Sito
Studio a `react_operational_full` senza sbloccare impostazioni, builder o
portali:

- `/studio` usa `GET /api/v1/ui/studio` con contratto `writes=none`,
  `operational=true` e `secrets_exposed=false`; mostra KPI reali, sessione,
  salute backup/sito/economico/documentale, route React operative e route
  legacy protette.
- `/amministrazione` usa `GET /api/v1/ui/amministrazione`, richiede
  `utenti.leggi` e mostra utenti, profili, audit, sicurezza aggregata, moduli
  amministrativi operativi e impostazioni legacy protette.
- `/sito-studio` usa `GET /api/v1/ui/sito-studio` con `writes=none` per stato
  sito reale, contenuti pubblici sicuri, KPI contatti/prenotazioni e anteprima
  pubblica sicura.
- `/sito-studio/contatti` usa `GET /api/v1/ui/sito-studio/contatti` e POST
  JSON solo per azioni legacy realmente supportate: collegamento cliente e
  aggiornamento stato prenotazione. Stato contatto, archiviazione, note,
  assegnazione e collegamento fascicolo restano disabilitati quando il backend
  legacy non li supporta.
- `/studio/*`, `/amministrazione/*`, `/sito-studio/builder`,
  `/sito-studio/*` ulteriori, `/impostazioni*` e
  `/sincronizzazione-calendari` restano protetti dal gate.
- I check dedicati sono
  `check-tranche-26a-studio-amministrazione-operational.mjs`,
  `check-tranche-26a-no-settings-secret-leak.mjs`,
  `check-tranche-26a-studio-amministrazione-api.py`,
  `check-tranche-27a-sito-studio-operational.mjs`,
  `check-tranche-27a-no-sito-secret-leak.mjs` e
  `check-tranche-27a-sito-studio-api.py`.

## Stato tranche 2026-05-06 - Tranche 5A hub studio e amministrazione

La quarta promozione governata abilita due hub direzionali React exact senza
sbloccare configurazioni o route operative ad alto rischio:

- `/studio` usa `web/services/react_studio_bridge.py` e
  `GET /api/v1/ui/studio` per KPI sicuri, profilo sessione, stato moduli gia'
  migrati e collegamenti a backup, sito studio, statistiche, utenti, profili,
  audit e impostazioni legacy.
- `/amministrazione` usa `web/services/react_amministrazione_bridge.py` e
  `GET /api/v1/ui/amministrazione`, mantenendo il vincolo legacy
  `utenti.leggi` e mostrando solo metriche aggregate, stato permessi,
  collegamenti amministrativi e warning.
- `/studio/*` e `/amministrazione/*` restano legacy; `/impostazioni`,
  `/impostazioni-studio`, `/impostazioni/calendario`,
  `/impostazioni/pagamenti`, `/impostazioni?tab=firma` e
  `/sincronizzazione-calendari` restano bloccate nel gate e nella shell.
- `scripts/react-migration/check-tranche-5a-secrets.mjs` verifica che bridge,
  data client e pagine della tranche non serializzino campi riservati nel
  payload React.
- `run-safe-react-migration.mjs --tranche=5a` cattura i contratti legacy,
  rilancia gate/UI/anti-segreti, verifica shell e bypass legacy con Flask
  `test_client`, esegue test/typecheck/build frontend e genera patch separate
  di rollback.

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
