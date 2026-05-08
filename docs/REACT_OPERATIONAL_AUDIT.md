# Audit operativo migrazione React

Data: 2026-05-01

## Criterio di accettazione

Una route non viene considerata migrata solo perche' apre la shell React. Per
essere dichiarata operativa deve avere:

- UI React basata sui token e sui componenti condivisi;
- route GET reale servita senza 404/500;
- API o repository reali per leggere i dati applicativi;
- form o azioni collegati a route operative esistenti, non a link fittizi;
- test di regressione su route, API e card;
- nessun link visibile verso `?_legacy=1`.

## Aggiornamento 2026-05-08 - Regia studio, amministrazione e Sito Studio

Le route `/studio`, `/amministrazione`, `/sito-studio` e
`/sito-studio/contatti` sono state promosse a `react_operational_full`:

- `/studio` e `/amministrazione` sono read-only (`writes=none`) e leggono solo
  aggregati sicuri via `GET /api/v1/ui/studio` e
  `GET /api/v1/ui/amministrazione`.
- `/sito-studio` resta read-only per dashboard, contenuti pubblici sicuri,
  KPI e anteprima pubblica; builder/editor/pubblicazione restano legacy
  protetti.
- `/sito-studio/contatti` usa JSON API per le azioni legacy supportate:
  collegamento cliente e stato prenotazione. Le azioni non supportate dal
  backend legacy sono esposte come disabilitate, non emulate.
- Nessuna pagina usa `LegacyPostForm`, CTA legacy primaria, storage browser,
  fetch esterni o rendering HTML raw.
- `/impostazioni*`, `/sincronizzazione-calendari`, `/studio/*`,
  `/amministrazione/*` e `/sito-studio/builder` restano protetti dal gate.

## Aggiornamento 2026-05-07 - Nuova fatturazione operativa

La route `/fatturazione/nuova` e' stata promossa a
`react_operational_full` con contratto anti-mascheramento dedicato:

- `GET /api/v1/ui/fatturazione/nuova` legge clienti, fascicoli, default,
  opzioni fiscali e azioni dal backend reale.
- `POST /api/v1/ui/fatturazione/nuova` e' JSON-only, protetto da
  CSRF/sessione e permesso `fatturazione.scrivi`, con validazione backend e
  audit `fatturazione.crea`.
- Il salvataggio usa `GestioneFatturazione.crea()`; il frontend non determina
  importi fiscali canonici e non genera PDF, XML o export.
- Il fallback `?_legacy=1` resta solo nella sezione `Rollback tecnico`;
  `/fatturazione/*` diverso da `/fatturazione/nuova` resta legacy operativo.

## Aggiornamento 2026-05-07 - Backup operativo

La route `/backup` e' stata promossa a `react_operational_full` con contratto
anti-mascheramento dedicato:

- `GET /api/v1/ui/backup` legge stato, lista copie, configurazione e integrita
  dal manager backup reale.
- `POST /api/v1/ui/backup/crea` e `POST /api/v1/ui/backup/verifica` usano API
  JSON con CSRF/sessione, permesso `backup.esegui`, validazione e audit.
- `BackupPage` usa `createBackup()` e `verifyBackupIntegrity()`; non usa
  `LegacyPostForm`, non fa fetch blob e non usa `URL.createObjectURL`.
- Il download resta link backend sicuro su route esistente; restore e delete
  restano legacy/protetti e non vengono esposti come flussi React.
- Il manifest dichiara `/backup` `react_operational_full`, mentre il gate
  continua a proteggere `/backup/*`.

## Verticale chiusa in questa tranche

### Portali telematici: acquisizione guidata

La route `/portali/<portale>/acquisizione` ora resta nella shell React e mostra
un wizard operativo per PST, PDP, PAT e PTT.

Il wizard React chiama gli endpoint Flask gia' presenti:

- `GET /api/portali/<portale>/acquisizione/status`
- `POST /api/portali/<portale>/acquisizione/search`
- `POST /api/portali/<portale>/acquisizione/preview`
- `POST /api/portali/<portale>/acquisizione/analyze`
- `POST /api/portali/<portale>/acquisizione/import`
- `POST /api/portali/<portale>/acquisizione/importa-payload`

La UI non promette scraping o download autonomo dai portali. L'acquisizione
usa file selezionati dall'utente, payload autorizzati o Local Signer quando
disponibile. Per PST resta esplicito il default della copia di consultazione.

### Preventivi e conferimenti

Il runtime React del modulo `Preventivi e Incarichi` ora gestisce anche route
profonde come:

`/preventivi/conferimento/nuovo/<id_cliente>?id_preventivo=<id>&from_page=preventivo`

Il form React precompila:

- cliente;
- fascicolo;
- preventivo collegato;
- oggetto incarico;
- avvocato referente;
- numero iscrizione albo;
- Ordine degli Avvocati.

Le scritture restano sul POST operativo `/preventivi/conferimento/nuovo`.

### Timesheet

Il runtime React del modulo Timesheet espone form reale verso
`POST /timesheet/nuovo`, con cliente, fascicolo, minuti, valore orario e
fatturabilita'.

### Firma documento fascicolo

La route profonda `/fascicoli/<id>/documenti/<id_doc>/firma` apre la UI React
operativa invece di restituire `405 Method Not Allowed`.

Il flusso React espone:

- stato documento e verifica firme da `/api/fascicoli/<id>/documenti/<id_doc>/info-firma`;
- anteprima e download del documento;
- firma tramite Local Signer sul PC dell'avvocato (`127.0.0.1:27272`);
- caricamento manuale del file firmato verso `POST /fascicoli/<id>/documenti/<id_doc>/firma`;
- avviso forte se il documento risulta gia' firmato.

Il pannello Local Signer distingue il servizio raggiungibile dal token PKCS#11:
se `token[]` e' vuoto ma il ping espone `token_probe_fresh[]`, la UI mostra
che il token e' stato rilevato dal probe fresco e propone il riavvio del
Local Signer, invece di degradare a "Local Signer non rilevato". In questo
stato non viene chiesto il PIN e la firma non e' abilitata: il PIN compare solo
quando il token principale e' presente in `token[]`.
L'azione di riavvio usa il protocollo registrato `iusentra-local-signer://restart`
come link diretto, mostra all'utente la richiesta di conferma del browser e
riverifica automaticamente lo stato per riallineare il processo locale.

La pagina React mantiene anche la configurazione della firma visibile gia'
disponibile nelle viste classiche: modalita' laterale, basso sinistra o basso
destra, luogo firma ricavato dalle impostazioni studio e passaggio del payload
`visible_signature_mode` / `visible_signature_place` al Local Signer.
La coccarda usata nella firma visibile e' un PNG trasparente incorporato nel
render PDF; i testi delle tre posizioni sono distanziati dal timbro e il flusso
browser e' stato verificato selezionando realmente tutte le modalita'.

Aggiornamento 2026-05-03: la verifica non si limita piu' al payload del browser.
La posizione scelta nella UI React viene salvata sul documento firmato e la route
di anteprima dei `.p7m` detached rilegge quella posizione prima di ristampare il
PDF. Il test `test_visualizza_documento_p7m_usa_posizione_firma_visibile_salvata_nel_pdf`
renderizza la pagina PDF finale e controlla pixel su laterale, basso sinistra e
basso destra. Local Signer include `reportlab`, necessario al timbro visibile
con coccarda PNG trasparente.

### Editor documento fascicolo

Aggiornamento 2026-05-05: la route profonda
`/fascicoli/<id>/documenti/<id_doc>/editor` apre una pagina React dedicata e non
cade piu' sul dettaglio fascicolo generico.

Il payload operativo e' `GET /api/v1/ui/fascicoli/<id>/documenti/<id_doc>/editor`
e contiene metadati reali, capability, endpoint dell'editor esistente e
`mock_fallback=false`. Il contenuto viene letto da
`GET /api/editor/<id>/<id_doc>/html`; salvataggio, export PDF ed export DOCX
restano sulle route Flask gia' protette e auditabili.

La pagina React monta toolbar, area `contentEditable`, autosave, import locale,
ricerca/sostituzione, statistiche, pannelli metadati e Lex contestuale dal
bundle locale Vite. Il vecchio editor Jinja e' rimasto solo come fallback
tecnico `?_legacy=1` e non e' piu' necessario caricare librerie da `https://esm.sh`
per visualizzare l'editor nella route ufficiale.

Aggiornamento 2026-05-05, versione 2.198.62: la toolbar dell'editor espone
font, dimensione testo, interlinea, formato pagina e zoom con controlli
governati dal bundle React. Le scelte di font/dimensione/interlinea vengono
applicate al testo selezionato oppure, se non c'e' selezione, al documento
intero e quindi entrano nell'HTML salvato dalle route Flask operative.

Lo stesso aggiornamento impedisce di mostrare in editor estrazioni PDF
inaffidabili con token `(cid:...)`: il backend prova PyMuPDF/OCR e, se il testo
resta non affidabile, restituisce `editor_disabled=true`; la UI apre uno stato
bloccato con anteprima originale e senza salvataggio inline. La visualizzazione
dei documenti firmati `.pdf.p7m`, incluso `attoACQ.pdf.p7m`, usa l'estrazione
CAdES condivisa e mantiene l'anteprima PDF inline.

Aggiornamento 2026-05-05, versione 2.198.63: i PDF giudiziari con layout
complesso non vengono piu' trattati come testo editabile. Se il backend rileva
stemmi, immagini, riquadri, timbri, testo ruotato/laterale o altri elementi che
rendono non fedele la ricostruzione HTML, restituisce
`editor_disabled_reason=layout PDF complesso`; la route React mostra l'anteprima
nativa del PDF dentro l'editor e blocca il salvataggio inline. Anche il payload
React marca i PDF come `editable=false`, cosi' il documento resta uguale
all'originale e l'editing resta riservato a DOCX, HTML e testo.

Aggiornamento successivo 2026-05-03: la modalita' laterale viene renderizzata
con bordo destro controllato e testo verticale generato per la prova
`firma_visibile_laterale.pdf`. La regressione e' presidiata dai test di layout
laterale e dalla verifica pixel della preview `.p7m`.

Aggiornamento 2026-05-04: la firma visibile laterale viene applicata a tutte le
pagine del PDF. Il testo usa 8 pt fissi, margine destro di 3 mm e campi
`Firmato Da`, `Emesso Da` e `Serial#`; la coccarda resta in fondo pagina con
margine destro di 1 mm e distanza di 2 mm dal testo. Le superfici React e Jinja
espongono anche `Luogo firma` e la scelta tra data e ora, sola data o nessuna
data nel timbro, propagando `visible_signature_datetime_mode` a Local Signer
`1.6.25` e al backend.

### Fascicolo React: regressioni operative presidiate

Sempre dal 2026-05-03 la pagina React del fascicolo espone nuovamente le
funzioni professionali che erano gia' presenti nella vista classica:

- anteprima documento in modal interna IUSENTRA, senza aprire Acrobat come
  applicazione esterna;
- caricamento documento e import portale via AJAX con refresh dei dati, senza
  ricaricare tutta la pratica;
- eliminazione documento e fascicolo con dialog React, non con conferma nativa
  del browser;
- eliminazione fascicolo disponibile anche nella colonna `Azioni` della lista
  fascicoli e dell'archivio, tramite `deleteHref` reale e POST AJAX;
- barra rapida con `Quadro intelligente AI`, `Editor professionale`,
  `Compilatore atti` e `Elimina fascicolo`;
- icone distinte per editor documento e firma digitale, cosi' i comandi non
  risultano ambigui.

La vecchia pagina standalone `/lex` non e' piu' una superficie funzionale:
i link React del modulo aprono il widget flottante tramite `#lex` e il backend
risponde `410 Gone` a qualunque visita manuale o bookmark storico della pagina.
Il floating icon resta l'unica assistenza contestuale, senza riaprire la pagina
di prova.

La testata del dettaglio evita doppioni consecutivi: il pannello `Quadro
intelligente AI` espone solo l'accesso al quadro completo, mentre
`Editor professionale`, `Compilatore atti` ed `Elimina fascicolo` restano nella
barra strumenti.

La rifirma non e' consentita in modo silenzioso: se il documento e' gia'
firmato, frontend e backend richiedono conferma esplicita `confirm_resign=1`.

### Amministrazione database

La route `/admin/database` ora apre una pagina React operativa con payload
reale da `GET /api/v1/ui/admin/database`.

La pagina React legge statistiche, moduli monitorati, snapshot SQLite e analisi
uso dal runtime database esistente. Le azioni restano sulle route Flask gia'
protette da sessione, permessi e audit:

- `GET /admin/database/verifica`
- `POST /admin/database/ottimizza`
- `POST /admin/database/migra`
- `POST /admin/database/attiva-sqlite`
- `GET /admin/database/export`

La shell React usa il profilo reale di sessione per nome, username, ruolo e
iniziali. Se un dato non arriva dal profilo, repository, API o configurazione
reale, non viene mostrato come dato applicativo.

## Gate anti-regressione aggiunti

Sono stati aggiunti test per impedire regressioni su:

- endpoint del wizard portale raggiungibili e JSON;
- card Studio con href interni raggiungibili senza 404/500;
- route profonde Preventivi/Conferimento con prefill da query e path;
- supporto frontend a campi `hidden`, `checkbox`, `file` ed `enctype`;
- passaggio di `path` e query string dal client React al bridge runtime.
- deep-link firma documento, Local Signer locale, upload manuale e guardia
  anti-rifirma con conferma esplicita.
- `/admin/database` React, payload reale, azioni database operative, profilo
  utente da sessione e assenza di dati inventati in sidebar, notifiche e
  recenti.

## Comandi di verifica

```bash
cd D:\legale\IUSENTRA\frontend
npm run test
npm run typecheck
npm run build

cd D:\legale\IUSENTRA
python -m pytest tests/test_react_shell.py -q
python -m pytest tests/test_web_bootstrap.py -q
```

## Nota di metodo

La migrazione completa deve proseguire con la stessa regola: pagina per pagina,
card per card, nessuna card decorativa, nessun link fittizio, nessuna route
React dichiarata completa se il relativo flusso operativo non esegue davvero
API, form, repository o download previsti.
