# Programma strategico di implementazione IUSENTRA

**Stato:** Fase 0 verificata localmente — commit, push e deploy Hetzner in corso; Fasi 1–14 bloccate fino al rilascio della Fase 0
**Redatto il:** 23/08/2026 10:52 Europe/Rome
**Branch e baseline di riferimento:** `Codex/legal-electronic-filing-kIxcV` — `68ab5ea3a483d46d0d70ab2a386a6ebf9afd959b`
**Input integrale analizzato:** `C:\Users\antmm\.codex\attachments\f388a497-f14b-4d2a-87b1-a5bfe01a8eff\pasted-text.txt`
**SHA-256 dell'input:** `72475D1C62D516EB431736926A2EA384D7EC2C616E1C41FEEFEDC7E9C3313B8F`

## 1. Mandato e criterio direttivo

Il mandato non è aggiungere pagine o strumenti isolati. È trasformare l'ampia superficie esistente in un prodotto legale italiano coerente, verificabile, sicuro e semplice da usare: il **Sistema Operativo verificabile del Fascicolo Legale**.

**Invariante non negoziabile:** nessuna fase può introdurre regressioni. Un comportamento già corretto è un contratto da preservare e non può cambiare indirettamente per effetto di refactor, migrazione, ottimizzazione, design o nuova funzione. Un cambiamento intenzionale richiede motivazione, migrazione esplicita e nuova prova di accettazione; non può mascherare una perdita di capacità esistente.

Ogni fascicolo deve poter rispondere con prove ai cinque quesiti operativi:

1. In quale stato procedurale si trova?
2. Qual è la prossima azione corretta e sicura?
3. Quali prerequisiti, documenti o autorizzazioni mancano?
4. Quali rischi procedurali, telematici, economici e di compliance sono presenti?
5. Quali documenti, eventi e fonti ufficiali giustificano la risposta?

Il fascicolo è quindi il centro operativo. `Lex Oggi` indica le priorità personali; `Regia Studio` governa le eccezioni dell'organizzazione; Lex ricerca, spiega e propone; l'Amministrazione configura. Nessun nuovo hub o menu deve duplicare queste responsabilità.

## 2. Analisi consolidata della richiesta

### 2.1 Diagnosi strategica

L'input contiene due analisi compatibili. Entrambe convergono su quattro fatti:

* IUSENTRA è già una piattaforma ampia, telematic-first, multi-tenant e ricca di domini; il rischio principale è la frammentazione, non la mancanza di funzioni.
* Il vantaggio difendibile non è replicare un generico SaaS internazionale: è unire processo telematico italiano, fascicolo, prova, fonti, economia, audit e AI governata in una sola esperienza.
* Prima del nuovo valore commerciale occorre trasformare le dichiarazioni di maturità in evidenza tecnica e materiale: contratto, RBAC/tenant, browser reale, provider, telemetria e rollback.
* Le azioni legali critiche restano deterministicamente governate e umane: Lex può spiegare, confrontare, proporre e redigere bozze; non può inviare, firmare, depositare, modificare termini o emettere movimenti economici senza policy, validazione, idempotenza e approvazione esplicita.

Il posizionamento da perseguire è:

> Il sistema operativo verificabile dello studio legale italiano: telematic-first, local-first, AI-assisted e human-controlled.

### 2.2 Evidenze del repository da rispettare

La base reale contiene già presidî importanti: React/Flask modularizzato, RBAC e tenant fail-closed, audit, storage SQL/mirror, Legal Skills/Lex, Local Signer, processi telematici, report visuali e test estesi. Esistono inoltre artefatti di maturità e un modulo di Product Governance.

Il piano non assume tuttavia che una funzione sia pronta solo perché esistono codice, test o un report storico. La maturità è dimostrata solo dalla prova corrente prevista nel Capability Truth Registry.

Al momento della pianificazione la worktree non è pulita. Sono presenti modifiche e file non tracciati in particolare su Telematico, Scadenziario, bridge React e prototipi `pct/telematico_truth_registry.py` e `pct/guardiano_scadenze.py`, con i rispettivi test. Non sono stati creati né alterati da questa pianificazione e non sono considerati accettati. La prima fase dovrà censirli, attribuirli, confrontarli con il piano e decidere esplicitamente se integrarli, spezzarli o scartarli senza sovrascrivere lavoro esistente.

### 2.3 Vincoli di architettura non negoziabili

* Restare un **modular monolith**. Estrarre processi solo per OCR/ingestion, scheduler-job, inference AI, ricerca, connettori, conversioni o firma locale quando il contratto e l'ownership lo giustificano; non introdurre microservizi prematuri.
* SQLite è la fonte autorevole dell'edizione locale, PostgreSQL di quella cloud/enterprise; JSON rimane solo bootstrap, import/export, configurazione versionata o mirror rigenerabile. I documenti vivono in object/file storage con metadati SQL; Redis serve solo cache, lock e code.
* Ogni record business è tenant-aware; nessuna lettura/scrittura aggira servizi, repository, RBAC, audit o path tenant-aware. In multi-studio il contesto mancante fallisce chiuso.
* Regole procedurali, documentali e termini sono versionati. Un fascicolo già aperto continua ad applicare la versione assegnata finché una migrazione approvata non ne modifica esplicitamente lo stato.
* Le azioni esterne sono idempotenti, correlate e pubblicate tramite transactional outbox. Ogni evento include tenant, aggregate, versione, attore, correlation/causation ID, payload minimizzato e policy di retention.
* L'OpenAPI è il contratto pubblico; da esso si genera e versiona il client TypeScript. Ogni feature React usa API JSON reali, non form legacy o dati demo.
* Ogni superficie ha owner, flag, permessi, telemetria, errore comprensibile, rollback e documentazione; tutto il testo resta in italiano e date/orari in `Europe/Rome`.

### 2.4 Valore di mercato e differenziatori

| Differenziatore | Decisione di prodotto |
| --- | --- |
| Affidabilità telematica | Sentinella Telematica, preflight, macchina a stati, ricevute, riconciliazione e prova WORM. |
| Rischio professionale | Guardiano Scadenze con fonti, regole, riconciliazione e revisione obbligatoria. |
| Fascicolo | Gemello Operativo con prossima azione sicura, stato, rischi, prove, economia e audit. |
| AI legale | Lex matter-native, citazioni verificabili, fonti contrarie, benchmark e approvazione umana. |
| Prova digitale | DMS e Fascicolo Probatorio: versione, provenienza, hash, chain of custody, fatti e contraddizioni. |
| Adozione | Intake unico, Client Experience OS, PWA, Migration Factory, API e pacchetti commerciali. |

### 2.5 Funzioni espressamente escluse finché non maturano le fondamenta

Non verranno avviati chatbot separati, calcolatori isolati, nuove route senza maturità misurabile, menu di primo livello duplicativi, nuovi repository JSON operativi, microservizi, app mobile nativa, invii PEC/depositi/firme autonomi o scritture AI senza approvazione. Storybook/Chromatic, se già presenti, diventeranno prove di release e non semplici dipendenze.

## 3. Matrice completa dei requisiti da implementare

| Macroarea | Requisiti mantenuti nel programma |
| --- | --- |
| Verità di prodotto | Capability Truth/Product Readiness Center: modulo, route, owner, flag, API, storage, permessi, test, ultimo smoke, ambiente, dipendenze, limiti, rollback, incidenti e versione; documentazione/menu/changelog generati dal registro. |
| Release e qualità | Staging con tenant sintetici e ruoli completi; golden journeys; browser desktop/tablet/mobile; accessibilità WCAG 2.2 AA; visual regression; sicurezza, performance, restore, monitoraggio e prove provider. |
| Dati | Inventario scritture, gateway repository, migrazione SQLite/PostgreSQL, shadow-read, dual-write temporaneo, riconciliazione, cutover per dominio, eliminazione fallback; Data Consistency Center e transactional outbox. |
| Fascicolo e procedure | Gemello Operativo, header decisionale, prossima azione sicura, quadro intelligente, tab non duplicati; procedure, versioni, fasi, transizioni, requisiti, decisioni, rischi, fonti e approvazioni. |
| Telematico | Centro Affidabilità e Sentinella: fonti ufficiali, schema/versione, provider health, preflight, firma/certificati/hash, idempotenza, coda/retry/circuit breaker, stati, ricevute, incident ledger, dry-run, Update Pack, canary e rollback. |
| Scadenze | Guardiano: confronto PEC/ricevute/provvedimenti/portali/documenti/calendari/manuale/calcolatore, fonti, regole, sospensioni, responsabile, revisione, reminder ed evidence pack. |
| Intake e CRM | Lead, qualificazione, conflitto, KYC, questionario, documenti, preventivo, mandato, firma, fondo spese, apertura fascicolo e workflow senza reinserimenti; moduli, appuntamenti, pipeline e conversione. |
| Entity Graph e compliance | Persone/società/alias/identificativi/relazioni; match esatto-fuzzy, explanation e clearance; Ethical Walls; AML con PEP, sanzioni, titolare effettivo, fonti vive, snapshot, hash e riesame. |
| Comunicazioni | Modello conversazione-messaggio-canale-partecipante-allegato-ricevuta-fascicolo; PEC, email, portale, SMS/WhatsApp autorizzati, inbox condivisa, deduplica, associazione, SLA, attività ed audit. |
| DMS e redazione | Versioning, provenienza, lock, compare, OCR, ricerca, redaction, antivirus, retention, legal hold, ACL, condivisione, watermark, hash, chain of custody, bundle e indice; round-trip DOCX; template governati. |
| Economia | Engagement, fee plan, budget, timesheet, spese, fondi, fatture, incassi, allocazioni, collection e snapshot; WIP, forecast, margini, scostamenti, fondi e credito a rischio. |
| Portale e mobilità | Client Experience dall'intake alla chiusura, stato comprensibile, richieste, firma, pagamenti e deleghe; PWA con modalità udienza offline, cifratura, sincronizzazione, revoca e notifiche non sensibili. |
| Integrazioni e migrazione | OpenAPI/SDK/OAuth/webhook firmati/idempotenza/rate limit/scopes/sandbox; M365, Google, calendari, PEC, firma, pagamenti, contabilità, KYC e registri autorizzati; Migration Factory con dry-run, mapping, deduplica, report, accettazione, cutover e rollback. |
| Lex e AI governance | Registro modelli/prompt/retriever/fonti/policy/dati/consenso/retention/incidente; disclosure e revisore; golden dataset; Lex matter-native, approval queue, citazioni a livello di affermazione, fonti contrarie, benchmark, analisi multidocumento. |
| Prova e conoscenza | Fascicolo Probatorio, matrice fatti-domande-prove-contraddizioni, Case Context Graph, cockpit udienza, motore d'impatto normativo e procedurale, knowledge management e pacchetti verticali. |
| Regia e BI | Regia per eccezioni, non dashboard decorative; metriche operative, economiche, qualitative e AI; Studio Profitability Twin e simulazioni. |
| Enterprise e mercato | Passkey, device/session management, OIDC, SAML, SCIM, ethical walls, DLP, BYOK, legal hold, resilienza, multi-sede, marketplace, SLA, Migration Factory, edizioni Solo/Studio/Enterprise/Sovereign. |

## 4. Piano in fasi, dipendenze e output

Ogni fase è autonoma, con una sola uscita ammessa: tutte le voci della matrice di accettazione della fase sono soddisfatte. Non si apre la fase successiva mentre l'attuale risulta anche solo parzialmente aperta.

| Fase | Risultato concreto | Dipende da | Ambito tecnico essenziale |
| --- | --- | --- | --- |
| 0 — Baseline governata | Inventario riproducibile di repository, worktree, versioni, route, storage, prove esistenti e gap; classificazione dei diff già presenti. | Nessuna | Registro di partenza, ADR, decisioni di ownership e nessuna sovrascrittura. **Verificata localmente; rilascio remoto in corso.** |
| 1 — Capability Truth | Registro generato e Product Readiness Center iniziale per tutte le superfici P0. | 0 | Modello di capability, raccolta prove CI/browser/provider, API e vista React amministrativa; stato menu e documentazione generati. |
| 2 — Staging e golden journeys | Tenant sintetici permanenti, osservabilità e i 15 percorsi critici automatizzati e realmente eseguibili. | 1 | Fixture tenant A/B, ruoli, dati telematici/PEC/documenti, Playwright/axe/VRT, database reale, rollback e monitoraggio. |
| 3 — Storage e outbox | Una fonte autorevole per ogni dominio P0 e nessun fallback silenzioso. | 0–2 | Inventario, migrazioni SQLite/PostgreSQL, repository, shadow-read/dual-write, riconciliazione, Data Consistency Center, outbox idempotente. |
| 4 — Shell, design system e Fascicoli | Workspace Fascicolo modulare e veloce, con navigazione Oggi–Regia–Fascicolo–Lex coerente. | 1–3 | Scorporo progressivo di `FascicoliPage.tsx`/`App.tsx`, query per feature, componenti accessibili, code splitting, budget prestazionali. |
| 5 — Sentinella e affidabilità telematica | Depositi/notifiche governati da capability, fonti ufficiali, preflight, stati e riconciliazione. | 1–4 | Monitor fonti/XSD, diff e impatto, Update Pack, provider health, evidence WORM, dry-run, idempotenza, retry e rollback. |
| 6 — Guardiano Scadenze | Termine critico spiegabile, riconciliato, assegnato e verificabile. | 2–5 | Normalizzazione fonti, regole deterministiche versionate, conflitti e doppia verifica, evidence pack; nessuna modifica autonoma del termine. |
| 7 — Gemello e motore procedurale | Il fascicolo governa fase, requisiti, prossima azione, rischi e decisioni. | 3–6 | Entità `procedure_*`, `matter_*`, source snapshot e approval; pacchetti verticali iniziali e migrazioni governate. |
| 8 — Intake, Entity Graph e compliance | Dal lead al fascicolo senza reinserimenti; conflitto e AML provabili. | 3, 7 | Entità/relazioni, screening, clearance, Ethical Wall, provider, evidence, KYC e rinnovi. |
| 9 — Comunicazioni, DMS ed editor | Comunicazioni e documenti diventano oggetti del fascicolo con prova, versioni e redazione professionale. | 3, 7–8 | Modello omnicanale, DMS, document viewer, DOCX round-trip, template governance e ACL. |
| 10 — Economia, portale e PWA | Ciclo economico e cliente connessi al fascicolo, anche in mobilità controllata. | 7–9 | Economic Command Center, portale, firma/pagamento, PWA udienza, time capture propositivo e privacy. |
| 11 — Integration Hub e Migration Factory | Adozione e integrazione sicure, versionate e reversibili. | 3, 8–10 | OAuth/scopes/webhook/SDK/sandbox; import, mapping, dry-run, hash, quantità, approvazione e rollback. |
| 12 — Lex verificabile e AI governance | AI contestuale, misurata, tracciata e sempre soggetta a revisione umana. | 1–3, 7–10 | Registro AI, disclosure, policy tenant, evaluation framework, claim-level citations, multi-document review e approval queue. |
| 13 — Prova, udienza, impatto e regia | Grafi di prove e conoscenza, cockpit udienza, impatto normativo, workflow/verticali e BI azionabile. | 5–7, 9, 12 | Evidence graph, normative change impact, Regia eccezioni, analytics/forecast e workflow designer. |
| 14 — Enterprise e scala commerciale | Sicurezza enterprise, edizioni, SLA, marketplace e operatività multi-sede. | 1–13 | SSO/SCIM/passkey, DLP/BYOK/legal hold, HA/restore, trust center, prezzi/edizioni e partner ecosystem. |

## 5. Metodo di implementazione applicato a ogni fase

1. **Analisi perimetrale.** Prima del codice: documenti della repository, fonti ufficiali aggiornate, API/componenti/repository esistenti, dati, permessi, sicurezza, performance e rischio di regressione. Per telematico e AI le fonti normative vengono salvate e versionate con data, ambito e limite.
2. **Contratto e modello.** ADR conciso, schema dati SQLite/PostgreSQL, tenant ownership, migrazione, eventi/outbox, OpenAPI, permessi, capability/flag, policy di rollback e Definition of Done della singola fase.
3. **Implementazione verticale minima.** Dominio → repository → servizio → API JSON → client React → route/menu → audit/telemetria. Nessun percorso primario legacy, demo, mock permanente o fallback invisibile.
4. **Guardrail automatici.** Test unitari, property-based quando esistono regole, contratti, integrazione SQLite/PostgreSQL, tenant/RBAC/IDOR, provider simulator, UI, accessibilità, performance e regressione mirata; ogni nuovo test resta shardabile entro cinque minuti.
5. **Prova materiale locale.** Docker reale aggiornato e healthy su `http://127.0.0.1:8080`; browser visibile autenticato; click, input, salvataggio, risultati, scroll completo, desktop/tablet/mobile, hover, focus tastiera, stati loading/error/success/disabled e nessun testo o dato tecnico esposto.
6. **Prova esterna lecita.** Per PEC/firma/portali/KYC/pagamenti si usa prima sandbox o caso di prova autorizzato, senza dati fittizi spacciati per reali né operazioni giuridiche irreversibili. Se è richiesta una prova provider e non è possibile eseguirla lecitamente, la fase resta aperta e viene riportata come `non verificata con provider`.
7. **Audit e rilascio.** Report con requisiti, file, fonti, evidenze, risultati, limiti, performance e rollback. Se la fase modifica prodotto: bump SemVer nei quattro file prescritti, commit, push dei branch gemelli, Docker locale no-cache, prova reale, deploy Hetzner, unico container `iusentra-app`, health e pulizia cache secondo `AGENTS.md`.

## 6. Regola del “100%” richiesta

Per evitare un falso verde, **“audit al 100%”** significa che il 100% delle voci obbligatorie della matrice di accettazione della fase ha evidenza corrente `PASS`; non indica arbitrariamente il 100% di line coverage dell'intero repository.

La coverage critica resta un indicatore distinto soggetto ai gate e al target del repository. Non verrà mai dichiarata al 100% finché il relativo report combinato non lo dimostra. Analogamente, una fase con test automatici verdi ma senza prova browser reale, o senza prova provider richiesta, rimane formalmente aperta.

### Matrice di accettazione obbligatoria di ogni fase

| Controllo | Evidenza richiesta per `PASS` |
| --- | --- |
| Copertura requisiti | Ogni requisito assegnato alla fase è tracciato a codice, API, dati, test e report; nessun requisito è omesso o spostato senza motivazione scritta. |
| Architettura e dati | Tenant, RBAC, schema SQLite/PostgreSQL, repository, migrazione, mirror e outbox sono verificati dove pertinenti; nessun fallback silenzioso. |
| Regole e fonti | Regola deterministica/versionata, fonti ufficiali salvate quando necessarie, limiti espliciti, policy di approvazione e idempotenza per azioni esterne. |
| Frontend | React reale con dati/API reali, italiano, data/ora Europe/Rome, importi italiani, accessibilità e stati completi. |
| Test automatici | Tutti i test mirati previsti passano; typecheck, lint, contratti, integrazione, RBAC, test UI, VRT/axe/performance e guardrail richiesti passano senza skip artificiosi. |
| Prova reale | Browser autentico su `127.0.0.1:8080`, click materiali e scroll completo su desktop, tablet e mobile; esiti osservati e riproducibili nel report. |
| Servizi esterni | Provider/sandbox/caso autorizzato provato quando fa parte della fase; errori, retry, riconciliazione e rollback verificati. |
| Prestazioni e sicurezza | Nessuna regressione rispetto alla baseline misurata; controlli autorizzativi, input, upload, segreti, audit e osservabilità pertinenti superati. |
| Documentazione e rilascio | Documentazione, capability registry, changelog/report e, per modifiche di prodotto, versione/push/deploy/health allineati. |

Una singola voce `FAIL`, `BLOCKED` o `NON VERIFICATA` impedisce sia la dicitura “fase completata” sia l'avvio della fase successiva.

### Contratto anti-regressione per ciascuna fase

Prima del primo diff, la fase congela route e API coinvolte, contratto dati, tenant e permessi, dati di prova, casi di regressione, prestazioni misurate e percorso browser reale. Ogni modifica è classificata come necessaria al requisito o estranea; quella estranea non entra nel rilascio. Alla chiusura si rieseguono la baseline e i nuovi test, comprese superfici correlate, ruoli e tenant interessati. Un solo comportamento prima funzionante che fallisca, rallenti oltre soglia o perda dati, accessibilità, audit, permessi o chiarezza UI riapre la fase fino a correzione e ripetizione integrale della matrice.

## 7. Golden journeys da completare nella fase 2 e rieseguire quando toccati

1. Lead → conflitto → cliente.
2. Cliente → preventivo → accettazione → conferimento.
3. Conferimento → fascicolo → procedura iniziale.
4. PEC ricevuta → associazione fascicolo → proposta e conferma scadenza.
5. Atto → allegati → firma → predeposito.
6. Deposito → ricevute → esito → riconciliazione.
7. Notifica L. 53 → relata → firma → invio locale → ricevute → prova fascicolo.
8. Udienza → preparazione → note/esito → attività e scadenze successive.
9. Timesheet → parcella → fattura → incasso/allocazione.
10. Documento → Lex → fonti → revisione → export.
11. Invito portale → upload → firma → messaggio → pagamento.
12. Migrazione SQLite → PostgreSQL → confronto → rollback.
13. Backup → perdita simulata → restore verificato.
14. Utente tenant A → tentativo di accesso tenant B negato e auditato.
15. Utente readonly → tentativo di modifica negato e auditato.

## 8. Baseline normativa e di mercato da verificare a ogni fase interessata

Le fonti dell'allegato non saranno mai usate come regola immutabile senza verifica. Alla data della pianificazione risultano confermati dalle fonti primarie consultate:

* gli obblighi di trasparenza dell'articolo 50 AI Act sono applicabili dal 02/08/2026, con indicazioni della Commissione su interazione con sistemi AI e contenuti generati/manipolati;
* la legge italiana 23/09/2025, n. 132 disciplina principi e deleghe in materia di AI e richiama trasparenza, sicurezza, riservatezza e conformità al diritto UE;
* il PST continua a pubblicare aggiornamenti ufficiali delle specifiche tecniche e degli XSD; il monitoraggio della Sentinella deve quindi basarsi solo su sorgenti ufficiali versionate, non su scraping o assunzioni.

Per ogni scelta normativa, telematica, AI, privacy, conservazione, firma, PEC o antiriciclaggio, la fase competente registrerà fonte primaria, data di consultazione, ambito, versione, test e comportamento prudente.

## 9. Decisione operativa immediata

Questo documento costituisce il registro di lavoro richiesto. Con l'autorizzazione dell'utente è stata eseguita la **Fase 0 — Baseline governata**: nessuna nuova area di prodotto è stata introdotta; sono stati corretti esclusivamente un orario non valido pubblicato dalla UI e un bootstrap diagnostico improprio. Il relativo audit locale è nel file `fase-0-baseline-2026-08-23.md`; la Fase 1 resta bloccata fino a commit, push gemello e deploy Hetzner verificato sullo stesso commit.
