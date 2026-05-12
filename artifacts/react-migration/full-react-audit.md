# Full React Audit IUSENTRA

Generato: 2026-05-09T17:09:00+02:00

Aggiornamento 2026-05-12T18:05:00+02:00: `Impostazioni > Notifiche` mantiene
il perimetro React operativo e aggiunge controlli PWA/Web Push reali: nessuna
richiesta permesso al caricamento, pulsanti espliciti per attivare, disattivare
e testare il dispositivo, utility `frontend/src/lib/pushNotifications.ts` con
registrazione `/sw.js` e API Flask tenant-aware. Il testo visibile resta
orientato allo studio e non espone endpoint, chiavi o dettagli tecnici.

Aggiornamento 2026-05-12T17:50:00+02:00: `/notifiche-legali` resta
`react_operational_full` e aggiunge API JSON dedicate per anteprima relata
compilata e salvataggio bozza relata. Le bozze sono tenant-aware e non vengono
incluse in `modelliRelata`; il catalogo cliente e' distinto dal catalogo relata
L. 53/1994 e non contiene oggetto legale o generazione relata. Nessun form POST
HTML, `LegacyPostForm`, CTA classica primaria o dato dimostrativo introdotto.

Aggiornamento 2026-05-12T22:05:00+02:00: `Impostazioni -> Calendari`
resta nel perimetro React operativo e aggiunge collegamento account,
calendari, conflitti e sync manuale tramite API JSON Flask. Nessun token o
password viene esposto al frontend; il pannello non usa form POST HTML,
`LegacyPostForm` o chiamate dirette ai servizi calendario esterni.

Aggiornamento 2026-05-12T20:30:00+02:00: `/notifiche-legali` resta
`react_operational_full` e aggiunge anteprima modello, catalogo modelli
navigabile, editor modelli personalizzati, endpoint JSON dedicato
`/api/v1/ui/notifiche-legali/modelli-relata` e campi automatici IUSENTRA
inseribili nel testo. Il componente continua a non usare form POST HTML,
`LegacyPostForm` o CTA primaria classica; deposito prova e comunicazione
cliente hanno selettori pratica/documento/cliente collegati ai dati reali.

Aggiornamento 2026-05-12T11:25:00+02:00: `/notifiche-legali` censita come
`react_operational_full`, con componente `NotificheLegaliPage`, data client
`notificheLegaliData`, bridge `react_notifiche_legali_bridge.py` e contratto
legacy dedicato. La route non usa `LegacyPostForm`, non contiene form POST HTML
e non offre CTA primaria `?_legacy=1`; le azioni sono endpoint JSON governati
per notifica L. 53, comunicazione cliente e prova deposito.
Aggiornamento 2026-05-11T17:30:00+02:00: `/fascicoli/nuovo` resta
`react_operational_full` e rafforza il flusso principale senza fallback legacy:
API JSON reale con clienti, soggetti e autorita' giudiziarie, validazioni
server-side per Fascicolo Veloce, messaggi JSON chiari e redirect automatico al
deposito assistito. Nessun `LegacyPostForm`, nessun form POST HTML React e
nessun dato demo introdotto.

Aggiornamento 2026-05-11T11:00:00+02:00: `/documenti` promossa a
`react_operational_full`. Il manifest corrente conta 86 route nel gate
anti-mascheramento; la route usa `StudioModulePage`, bridge
`react_studio_module_bridge.py`, contratto legacy dedicato e API JSON reale
`/api/v1/ui/studio-modules/documenti`. Browser Docker locale desktop/tablet/mobile
confermato senza overflow, errori console o testi tecnici visibili.

Aggiornamento 2026-05-10T00:15:00+02:00: il manifest corrente conta 85 route
nel gate anti-mascheramento, con 0 `LegacyPostForm`, 0 form POST HTML React,
0 bridge con scritture legacy e 0 status `react_full` deprecati. Le nuove route
di dettaglio PEC/email ordinaria sono servite dalla pagina React email. La
verifica browser Docker 2.214.0 ha coperto desktop/mobile sulle pagine richieste
dall'utente e su `/admin/database`, senza termini tecnici visibili e senza
overflow orizzontale.

## Sintesi

- Route censite: 57
- Stati manifest: react_operational_full=37, react_operational_partial=1, react_bridge=0, legacy_operational=19
- Classificazione anti-mascheramento reale: react_operational_full=38, legacy_operational=19
- Route bridge azzerate nel manifest: 8 -> 0
- CTA `?_legacy=1` complessive rilevate dal gate: 80
- CTA `?_legacy=1` primarie nelle route promosse in questa fase: 0
- Route con LegacyPostForm: 0
- Route con form HTML POST React: 0
- Route full con dati mock/demo: 0
- Bridge con `writes=legacy_routes`: 0
- Template Jinja censiti: 258
- Template Jinja UI primaria: 130
- Template Jinja fallback tecnico: 36

## Route Promosse

| Route | Stato precedente | Stato nuovo | Verifica |
| --- | --- | --- | --- |
| `/template-atti` | react_bridge | react_operational_full | lettura JSON reale, scritture none, nessuna CTA legacy primaria |
| `/template-atti/catalogo` | react_bridge | react_operational_full | catalogo metadati reale, filtri React, scritture none |
| `/redazione-atti` | react_bridge | react_operational_full | quadro operativo React read-only, azioni primarie React |
| `/giurisprudenza` | react_bridge | react_operational_full | archivio metadati/fonte React, nessun fetch esterno |
| `/legal-intelligence` | react_bridge | react_operational_full | dashboard fonti React, nessuna generazione React |
| `/legal-intelligence/news` | react_bridge | react_operational_full | news backend reali con fonte e stato |
| `/legal-intelligence/mediazione` | react_bridge | react_operational_full | registro mediazione backend, stato fonte visibile |
| `/ricerca-legale` | react_bridge | react_operational_full | alias React verso Legal Intelligence senza pipeline nuova |
| `/statistiche` | react_operational_partial | react_operational_full | dashboard read-only su repository reali, nessun fallback legacy nel payload React |
| `/deposito/checklist` | legacy_operational | react_operational_full | Controlli Atti in `TelematicoSurfacePage`, API reale `/api/v1/ui/telematico/surface/checklist`, nessun testo tecnico vietato in UI |
| `/strumenti-legali` | legacy_operational | react_operational_full | Strumenti Forensi in `StudioModulePage`, API reale `/api/v1/ui/studio-modules/strumenti-forensi`, azioni operative senza form POST HTML |
| `/strumenti-operativi` | legacy_operational | react_operational_full | Strumenti Operativi in `StudioModulePage`, API reale `/api/v1/ui/studio-modules/strumenti-operativi`, azioni operative senza form POST HTML |
| `/documenti` | assente / 404 | react_operational_full | Documenti in `StudioModulePage`, API reale `/api/v1/ui/studio-modules/documenti`, azioni verso fascicoli, catalogo atti, redazione e ricerca documentale |
| `/notifiche-legali` | assente | react_operational_full | Workflow dedicato in `NotificheLegaliPage`, API reale `/api/v1/ui/notifiche-legali`, separazione notifica L. 53 / prova deposito / comunicazione cliente |

## Route Non Promosse

- `/preventivi/wizard`: resta `react_operational_partial` nel manifest per cautela sui sottopercorsi e sui fallback tecnici, pur risultando operativo nel controllo anti-mascheramento.
- Route impostazioni sensibili: restano legacy per PEC, firma, Local Signer, OAuth e segreti non esponibili.
- Route wildcard economiche/documentali: restano legacy per dettaglio, export, PDF, DOCX, XML e download governati.
- Route telematiche `/polisWeb`, `/pdp`, `/pat`, `/sigit`, `/sigp`, `/portali/*`: restano legacy per conformita portali, sessioni, certificati, Local Connector e divieto di scraping.

## Componenti E Dati

- Componenti IUSENTRA aggiunti: loading/error/success/retry, skeleton, wizard stepper, compliance panel, document status badge, channel card, message list, LexPanel.
- Registry icone aggiunto: `frontend/src/design/icons.tsx`.
- Client API consolidati/re-export: documents, telematico, comunicazioni, lex, legalIntelligence, templates.
- Source registry compliance aggiunto: `pct/data/legal_sources_registry.json`.

## Gate

- `node scripts/react-migration/run-full-react-migration.mjs`: verde dopo promozione.
- `check-no-primary-legacy-links`: verde.
- `check-no-mock-data-full-react`: verde.
- `check-full-react-route-contract`: verde.

Questo audit sostituisce la tabella storica precedente. Il dettaglio macchina corrente e' in `artifacts/react-migration/anti-mascheramento-audit.json`.
