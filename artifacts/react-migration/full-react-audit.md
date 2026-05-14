# Full React Audit IUSENTRA

Generato: 2026-05-09T17:09:00+02:00

Aggiornamento 2026-05-14T02:35:00+02:00: fase react 10 `fasereact`
2.231.0. L'audit test App V2 ora espone piano, inventario e matrice per route,
ruoli, tenant, feature flag, backend, frontend, RBAC, contratti e smoke. Le
righe `tested` sono riservate alle route P0/P1 gia' `react_operational_full`;
`partial`, `pending` e `blocked` restano stati non conclusivi.

Audit anti-mascheramento: `scripts/smoke_app_v2_all.py` non stampa segreti e
non trasforma credenziali mancanti in esito verde. Il piano dichiara
esplicitamente che non esistono runner component/VRT frontend nel repo e che la
copertura UI resta quella governata dai gate statici e browser smoke
documentati.

Aggiornamento 2026-05-14T00:15:00+02:00: fase react 9 `fasereact`
2.230.0. L'audit UI regression App V2 e' ora esplicito e verificabile:
Storybook non viene introdotto perche' la repository non ha infrastruttura
esistente; VRT non viene dichiarata attiva. Entrambi i gap sono documentati in
`docs/ui-regression-and-storybook.md` e bloccati dal gate
`scripts/validate_ui_coverage.py` se venissero presentati come pronti senza
asset reali.

Audit anti-mascheramento: fixture sicure solo con domini `example.invalid`,
segreti mascherati e nessun IP/chiave reale; ogni route P0/P1
`react_operational_full` deve avere copertura `ui_tested`, stati `default`,
`loading`, `empty`, `error`, `forbidden`, `flag-off`, `readonly`, riferimento
al componente e ai gate. Le superfici non full restano escluse dal verde UI
completo.

Aggiornamento 2026-05-13T23:59:00+02:00: fase react 8 `fasereact`
2.229.0. Il registro requisiti per area/workflow App V2 e' ora generato in
`docs/app-v2-area-requirements.md` e collega ogni area alle route censite, ai
P0/P1/P2/P3, ai permessi, ai rischi tenant/PII e ai gate minimi.

Audit anti-mascheramento: un'area puo' essere `complete_tested` solo se tutte
le route collegate sono `react_operational_full` e ha workflow P0/P1 censiti;
Telematico resta `blocked` per i workflow ministeriali non parificati. Lo smoke
`scripts/smoke_app_v2_workflows.py` non usa segreti hardcoded: senza variabili
ambiente elenca i workflow e registra che l'esecuzione autenticata non e'
avvenuta, evitando dichiarazioni verdi non supportate.

Aggiornamento 2026-05-13T23:55:00+02:00: fase react 7 `fasereact`
2.228.0. L'audit App V2 registra ora un presidio frontend fail-closed:
permessi effettivi nel bootstrap, menu sperimentale filtrato da flag/RBAC,
stato flag-off senza fetch pagina e 404 sicura per percorsi non censiti. Il
gate `check-app-v2-frontend` confronta sorgenti, documenti, manifest e OpenAPI
prima della build.

Le route legacy o `react_operational_partial` restano esplicitamente
`pending`/`partial` nel registro fase 7; nessuna pagina viene mascherata come
full React senza API, stati UI, RBAC, browser smoke e test parificati.

Aggiornamento 2026-05-13T23:05:00+02:00: fase react 5 `fasereact`
2.226.0. Il perimetro backend React e' ora censito in
`docs/backend-endpoint-security-map.md`. Il guardrail
`backend_security_control_param` impedisce mass assignment di tenant, studio,
user, token/API key e redirect liberi, lasciando ai controlli dominio i campi
amministrativi legittimi come ruoli, permessi e chiavi provider specifiche.

Audit denial: `policy_denied.backend_security`, warning applicativo senza
valori sensibili e risposta JSON controllata. Gate: auth decorator su tutte le
API React censite, 400 su tenant/studio forzati, 401 anonimo preservato e filtri
operativi normali non bloccati.

Aggiornamento 2026-05-13T22:05:00+02:00: fase react 4 `fasereact`
2.225.0. Il routing legacy -> App V2 e' governato da helper fail-closed,
feature flag canonici e mappa generata. Nessun redirect automatico e' stato
attivato in produzione durante questa fase: i template legacy restano fallback
finche' non esiste parita' verificata e rollout esplicito.

Audit anti-mascheramento routing: target solo interni `/app-v2`, query sicure
whitelistate, query rischiose scartate, deep link parametrico non promosso se
non ha regola dedicata, mapping backend censito in
`docs/legacy-to-app-v2-routing-map.md` e smoke anonimo che distingue login
same-origin da open redirect reale. I gate dedicati sono registrati verdi in
`pytest-confirmed-ok.md`.

Aggiornamento 2026-05-13T21:20:00+02:00: fase react 2 `fasereact`
2.223.0. Il perimetro App V2 e' ora censito in
`docs/app-v2-page-registry.md`, rigenerabile e verificabile via
`scripts/react-migration/generate_app_v2_page_registry.py --check`.

Il registro espone anche rischi tenant/PII e permessi attesi per pagina. Le
route non full non sono state mascherate come complete: restano backlog P0/P1
con blocchi dichiarati e test mancanti espliciti.

Aggiornamento 2026-05-13T20:45:00+02:00: fase react 1 `fasereact`
2.222.0. Le capability App V2 non ancora promosse sono ora fail-closed per
default tramite feature flag documentati e auditabili. Il controllo e' limitato
alle route sperimentali `/app-v2/*`, cosi' i percorsi React ufficiali non
subiscono regressioni.

Web Push e' governato da `notifications.mobilePush`: quando il flag e' spento
la UI non invoca subscribe/test e il backend risponde con errore controllato,
senza esporre dettagli tecnici o chiavi riservate. Il payload flag pubblico e'
disponibile solo tramite endpoint autenticato e bootstrap shell.

Aggiornamento 2026-05-13T13:32:00+02:00: tranche 2.220.0 audit gate React
reale. Le route `/scadenziario/:id` e `/sito-studio/builder` sono ora
`react_operational_full` con GET ordinario servito dalla shell React e fallback
`?_legacy=1` preservato. `/scadenziario/:id/modifica` e
`/sito-studio/redazione-ai` sono `react_operational_partial` perche' conservano
azioni operative da completare prima della piena parificazione.

Il gate e' stato reso fail-closed per sottopercorsi: scadenziario accetta solo
lista, nuovo, dettaglio e modifica, lasciando fuori export, PDF, eliminazione,
completamento e bulk; sito studio accetta solo root, contatti, builder e
redazione assistita. `Template Atti` e' stato ripulito dai form HTML nel
componente full e l'audit anti-mascheramento conta 98 route, zero
`LegacyPostForm`, zero form POST HTML React e zero status `react_full`
deprecati.

Verifica browser reale aggiunta il 2026-05-13: Playwright Python con Chrome
locale, login utente reale e viewport desktop/mobile conferma shell operativa
su `/sito-studio/builder`, `/scadenziario/<id>`,
`/scadenziario/<id>/modifica` e `/sito-studio/redazione-ai`; nessun errore
console, nessun overflow orizzontale e nessun termine tecnico vietato visibile.

Aggiornamento 2026-05-13T18:20:00+02:00: `Impostazioni > Notifiche` resta nel
perimetro React operativo e rafforza la diagnosi Web Push senza introdurre form
POST HTML, `LegacyPostForm` o dati dimostrativi. Il pannello distingue server
non configurato, utente non amministratore, browser non supportato, permesso
bloccato e subscription attiva. I dettagli tecnici sensibili restano nel
payload diagnostico autenticato e nei comandi server; la chiave privata non
viene mai inviata al frontend.

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
| `/template-atti/compila/<codice>` | legacy/Jinja | react_operational_full | Compilatore atti in `TemplateAttiPage`, API reale `/api/v1/ui/template-atti/compila/<codice>`, selezione cliente/pratica, prefill IUSENTRA, presidio Cartabia/deposito e POST finale verso editor professionale |

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

Aggiornamento 2026-05-13: il compilatore Template Atti e' stato verificato con browser Playwright su `AMM_RIC_001`. La shell React e' visibile, il vecchio compilatore e' assente, le note dei campi mancanti sono italiane e leggibili, e il pannello normativo non espone oggetti tecnici o dizioni da sviluppatore.

Aggiornamento 2026-05-13 fase react 5: `docs/backend-endpoint-security-map.md`
censisce le API React e il guardrail `backend_security_control_param` impedisce
parametri client per tenant, studio, user, token/API key e redirect liberi. I
test fase 5 confermano auth su tutte le route API React censite e nessun eco di
valori sensibili nei denial.

Aggiornamento 2026-05-13 fase react 6: `docs/openapi.yaml` e
`docs/api-endpoint-contract-map.md` contrattualizzano 182 endpoint React API con
RBAC, tenant scope, feature flag quando presente, error schema e stato provider.
La provider verification conferma 401 reale su tutti gli endpoint, 27 risposte
200 rappresentative P0/P1 e il 400 del guardrail sicurezza backend.

Questo audit sostituisce la tabella storica precedente. Il dettaglio macchina corrente e' in `artifacts/react-migration/anti-mascheramento-audit.json`.
