# Full React Audit IUSENTRA

Generato: 2026-05-09T17:09:00+02:00

Aggiornamento 2026-05-16T17:40:00+02:00: registri mediazione interni 2.243.4.
`/ricerca-legale/mediazione` e `/legal-intelligence/mediazione` sono confermate
come superfici React operative: la pagina espone 3.035 record ministeriali
importati, non una lista di link. Il contratto anti-mascheramento e' rafforzato
dal test che impedisce la deduplica delle righe per URL ufficiale; la verifica
API autenticata restituisce 3.038 schede totali. Browser Chrome CDP su
desktop/tablet/mobile: 6/6 OK, zero form POST HTML, zero overflow e zero testo
tecnico vietato.

Aggiornamento 2026-05-15T14:30:00+02:00: hotfix cartella cliente 2.237.5.
Audit anti-mascheramento esteso alla rotta `/clienti/<id>/cartella`: il
manifest la dichiara full React, i gate rifiutano regressioni a fallback
classico e il contratto legacy documenta la normalizzazione di `_legacy=1`.
La verifica browser su Docker locale ha osservato il redirect 302 da
`/clienti/2B6E3D22/cartella?_legacy=1` a `/clienti/2B6E3D22/cartella`, shell
React presente, zero form POST HTML, zero overflow orizzontale e zero termini
tecnici vietati nel testo visibile.

Aggiornamento 2026-05-14T23:10:00+02:00: modulo notifiche legali 2.236.0.
Audit anti-mascheramento esteso a notifiche e deposito prova: il vecchio
`pct/notifica.py` non puo' piu' inviare PEC con oggetto generico; il profilo
deposito non ricade su `portal_upload`; il registry procedimenti distingue
SICID, SIECIC, SIGP, UNEP, PAT, PTT/SIGIT e PDP; PTT applica 10 MB/50 MB/50
file/100 caratteri. La UI React mostra esiti e pacchetto prova invece di
lasciare il click senza fase operativa; la selezione multipla dei documenti
della pratica alimenta automaticamente l'elenco allegati della relata. Verifica
browser isolata e Docker locale 2.236.0 completati senza eseguire backup.

Aggiornamento 2026-05-14T10:05:00+02:00: fase react 13 `fasereact`
2.234.0. L'audit smoke distingue ora controlli passati, falliti, saltati e
bloccati. L'orchestrator fase 13 non maschera l'assenza di credenziali: auth,
RBAC, tenant e download documento test restano `BLOCKED` quando mancano env o
ID sintetici. I report JSON redigono password, token e API key; lo staging
workflow carica artifact sanitizzati e usa `--suite post-deploy --read-only`.

Audit anti-mascheramento: nessuna suite autenticata viene dichiarata completa
senza profili smoke; nessuna PEC, push, upload o modifica ruolo viene eseguita
nel post-deploy read-only. Le failure critiche restano `FAIL` e causano exit
non-zero. Docker locale 2.234.0 conferma immagine, runtime e readiness senza
committare dati runtime rigenerati dai container. Il deploy Hetzner del commit
`85d7617549c0695ffd3f41447d0b2c86524766aa` ha confermato la stessa versione
runtime e gli stessi esiti smoke read-only in produzione.

Aggiornamento 2026-05-14T09:30:00+02:00: fase react 12 `fasereact`
2.233.0. L'audit documentale ha chiuso i vuoti di handover: indice ufficiale,
architettura corrente, App V2, troubleshooting, risk register, osservabilita,
database/migrazioni, release notes e prossime PR. La policy sicurezza e la
contribuzione ora richiamano RBAC backend autoritativo, isolamento tenant
fail-closed, no PII/segreti, branch ammessi e deploy/smoke governati.

Audit anti-mascheramento: i documenti ribadiscono che Storybook/VRT non sono
presenti, che gli smoke autenticati richiedono secrets dedicate e che le aree
`partial`, `blocked` o `complete_unverified` non possono essere dichiarate
complete. Il drift su `docs/api-contracts.md` e' stato risolto aggiornando il
generatore invece di mantenere una modifica manuale.

Aggiornamento 2026-05-14T07:10:00+02:00: fase react 11 `fasereact`
2.232.0. L'audit CI/CD App V2 e' ora verificabile in `docs/ci-cd-gates.md`:
ogni workflow ha trigger, job, comando, classificazione bloccante/manuale,
artifact, secrets richiesti, required checks consigliati e gap residui.
`tests/test_ci_cd_gates_phase11.py` blocca regressioni su main CI, smoke
staging, security supply chain e documentazione test plan.

Audit anti-mascheramento: Storybook/VRT restano non dichiarati perche' non
esiste comando reale; smoke autenticati restano manuali e falliscono se si
richiedono credenziali mancanti; GitHub Actions non vengono dichiarate verdi
prima dell'esecuzione remota dopo push. Nessun segreto e' stato aggiunto ai
workflow.

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

## Aggiornamento fase 14 - 2026-05-14

La fase 14 ha rieseguito i gate anti-regressione di chiusura senza promuovere
nuove route. `tools/check_repo_governance.py` inizialmente segnalava due moduli
bootstrap Fascicoli oltre budget e un marker mojibake letterale in
`pct/email_client.py`; i problemi sono stati corretti con estrazioni modulari e
escape Unicode, poi ritestati con governance, py_compile, Ruff, flake8, test
mirati Fascicoli/Documenti/PolisWeb e smoke Docker locale.

Risultato finale locale: GO WITH WARNINGS, nessuna failure critica residua.
Warning residui: smoke autenticati senza profili dedicati, VRT/Storybook
assenti, `gitleaks` locale non installato e GitHub Actions remote da confermare
dopo push.

## Aggiornamento 2.236.3 - 2026-05-14

Nuove superfici confermate React operative: `/profilo` e `/agenda/importa`.
Superfici gia' React corrette senza regressione di status: `/agenda/nuovo`,
`/clienti`, `/soggetti`, `/fascicoli`, `/email/scrivi`,
`/email-ordinaria/scrivi`, `/scadenziario`, `/impostazioni?tab=ai`,
`/portali/pdp/acquisizione`, `/pat` e `/sigit`.

Controlli anti-mascheramento: nessun link primario `_legacy=1`, nessun form POST
HTML nel flusso principale React toccato, dati cliente/fascicolo da API reali,
storage allegati email sotto path tenant-aware, testo visibile ripulito da
`repository_reali` e termini tecnici vietati nel perimetro verificato. Il
dettaglio scadenziario resta nella stessa esperienza React e mostra azioni
operative dopo URL `/scadenziario/<id>?vista=tutte`.

## Aggiornamento 2.236.6 - 2026-05-15

`/strumenti-legali` resta `react_operational_full` ma il suo contenuto e' stato
riallineato al contratto prodotto: non solo card, ma catalogo completo e calcoli
eseguibili in React. Il payload `strumenti-forensi` include 70 funzioni di
catalogo, 20 moduli calcolabili, campi dinamici e collegamento a
`/api/v1/ui/strumenti-legali/<tool_id>`.

Controlli anti-mascheramento: il flusso principale non usa form POST HTML, non
mostra fallback demo, non espone termini tecnici vietati e restituisce risultati
realmente calcolati in pagina. Browser reale desktop/tablet/mobile confermato su
`Calcolo Interessi di Mora` con risultato, metriche e tabella dei segmenti.

## Aggiornamento 2.237.0 - 2026-05-15

`/legal-skills` entra nel perimetro governato React con superficie dedicata,
lazy route, feature flag default-off e API JSON tenant-aware. La pagina non usa
form POST HTML, non mostra dati demo e non espone terminologia tecnica; esito,
citazioni, confidenza, nota revisore e blocco export restano visibili quando
rilevanti.

Controlli anti-mascheramento: route gate e shell React servono la pagina nuova,
le API `/api/v1/legal-skills/*` bloccano parametri riservati dal client, i seed
pack sono read-only e custom skill/scheduled agent restano spenti salvo flag. Il
browser audit finale su `/legal-skills` desktop/mobile e' verde dopo correzione
del 404 iniziale.

## Aggiornamento 2.237.1 - 2026-05-15

La fase AI Legal 2 non cambia la semantica del motore, ma rende esplicito il
contratto delle pagine richieste: profilo pratica, intervista cold-start,
esecuzione skill, dettaglio run e coda revisore. Tutte le pagine sono route React
governate dal prefisso `/legal-skills`, protette dai flag esistenti e senza
payload client con identificativi tenant/studio.

Controlli anti-mascheramento: i wrapper rimandano a componenti operativi gia'
collegati ad API reali, il gate statico ne verifica presenza e aggancio alla
shell, e lo smoke HTTP anonimo conferma che le route fase 2 non cadono in 404.

## Aggiornamento 2.238.1 - 2026-05-15

Lo stato "Legal Skills non attivo" non deve piu' comparire per uno studio senza
override manuale: i flag base e le route React di Legal Skills sono stati
promossi a default-on. La protezione resta sul perimetro sensibile: trust layer,
custom skill e agenti schedulati rimangono default-off e richiedono attivazione
esplicita.

Controlli anti-mascheramento: le API catalogo continuano a usare pack seed reali
e RBAC/tenant isolation; il test di regressione conferma catalogo e profilo
disponibili con default standard e blocco `feature_disabled` per scheduled/trust
senza opt-in.

Verifica visuale finale: il catalogo non interroga gli agenti schedulati quando
il relativo flag resta spento, il manifest Supertonic opzionale risponde come
disabilitato e Chrome CDP autenticato su `/legal-skills` desktop/mobile passa
senza errori console, redirect login, overflow, form POST HTML o testi tecnici.

## Aggiornamento 2.239.1 - 2026-05-15

Il builder Sito Studio non e' piu' una superficie semplificata: `/sito-studio/builder`
usa un'esperienza React full con pannello stretto, tab verticali e preview live
dominante. La pagina non espone dati demo o fallback mascherati; salva e legge
stato reale tramite le API del builder e del sito pubblico.

Controlli anti-mascheramento: le azioni di pagine, blocchi, media, tema,
conformita', AI e pubblicazione passano da endpoint esistenti; il sito pubblico
riceve font, dimensioni, colori, layout ed effetti dal tema salvato; i soli tag
rich text ammessi sono filtrati dal backend. L'audit CDP conferma footer live,
menu tablet/mobile, resize pannello, effetti, font, colori, toolbar testo e
allineamenti funzionanti.

## Aggiornamento 2.239.2 - 2026-05-16

`/legal-intelligence/mediazione` resta React full e ora mostra accessi ufficiali
distinti per Registro Organismi di Mediazione, Elenco Enti per la Mediazione ed
Elenco Formatori per la Mediazione. I record sono generati dal bridge backend,
puntano ai servizi ministeriali `mediazione.giustizia.it`, sono marcati come
fonte ufficiale e vengono riusati da `/ricerca-legale` come evidenze locali
governate.

Controlli anti-mascheramento: nessun dato demo, nessun fetch esterno forzato,
nessuna CTA `_legacy=1` e nessun termine tecnico visibile introdotto. Test
mirato `tests/test_react_legal_intelligence_search.py` verde con 4/4 casi.
Docker locale no-cache e deploy Hetzner CPX42 confermati su versione `2.239.2`,
con `/api/pronto` pubblico verde e cron backup non aggiornato.

## Aggiornamento 2.239.3 - 2026-05-16

`/legal-intelligence/` non e' piu' una seconda vista generica di ricerca: diventa
`Osservatorio Legale`, con mappa fonti/news/registri, percorso operativo e
schede governate. `/ricerca-legale` costruisce risultati consultabili dentro
IUSENTRA, con estratto fonte, contesto, uso pratico, attendibilita' e ricerca
collegata.

Controlli anti-mascheramento: il bridge espone campi contestuali reali
(`sourceExcerpt`, `sourceContext`, `practicalUse`, `reliabilityNote`,
`followUpQuery`), la UI usa `Leggi contesto` come azione primaria e la fonte
originale resta controllo finale. Nessun dato demo, nessun `_legacy=1`, nessun
form POST HTML e nessun testo tecnico vietato nel perimetro.

Verifica visuale finale: Chrome CDP autenticato desktop/mobile su
`/legal-intelligence`, `/legal-intelligence/mediazione`, `/ricerca-legale` e
`/ricerca-legale?q=mediazione`, 8/8 controlli OK senza overflow, redirect login,
console error o testo tecnico visibile. Report:
`artifacts/react-migration/visual-2.239.3-legal-intelligence-context/visual-load-audit.md`.
Deploy Hetzner CPX42 verificato sul commit pushato: cron backup non aggiornato,
container healthy e `/api/pronto` pubblico pronto su `2.239.3`.
