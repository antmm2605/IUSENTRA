# Knowledge base operativa per agenti AI - IUSENTRA

## Scopo

Questo documento aiuta Codex, Claude e altri agenti AI a orientarsi nella repository IUSENTRA prima di modificare codice, UI, deploy, CI, storage, Lex AI o flussi telematici.

Non sostituisce `AGENTS.md`: lo completa con una mappa documentale piu' estesa.

Non contiene segreti, token, password, PIN, chiavi private o dati reali di studio.

## Branch operativo

- Branch operativo richiesto per questa tranche: `claude/legal-electronic-filing-kIxcV`.
- Branch gemello da mantenere sincronizzato: `Codex/legal-electronic-filing-kIxcV`.
- Non creare branch temporanei.
- Prima di chiudere un lavoro, verificare che i due branch locali e remoti puntino allo stesso commit quando il task prevede commit/push.

## Ordine di priorita' delle fonti

Quando piu' fonti danno indicazioni diverse, seguire questo ordine:

1. richiesta corrente dell'utente;
2. `AGENTS.md`;
3. documenti tecnici in `docs/`;
4. specifiche in `docs/specs/ministero/`;
5. procedure operative in `ops/`;
6. deploy in `deploy/hetzner/`;
7. CI e automazioni in `.github/`;
8. codice esistente e test;
9. fonti ufficiali esterne, solo quando il dato non e' gia' certo nella repository.

## `docs/`

`docs/` e' la fonte interna principale per prodotto, architettura e comportamento atteso.

Prima di modificare un dominio applicativo, cercare in `docs/` i riferimenti pertinenti. In particolare:

- PRD, roadmap e documentazione funzionale;
- architettura e modularizzazione;
- storage matrix e migrazioni;
- sicurezza, hardening, osservabilita' e audit;
- pack architecture;
- Lex AI, RAG, fonti e qualita';
- governance prodotto;
- UI, React/app-v2 e design token;
- deploy e release.

Documenti spesso rilevanti:

- `docs/ARCHITETTURA.md`;
- `docs/STORAGE_MATRIX.md`;
- `docs/PACK_ARCHITECTURE.md`;
- `docs/DEPLOY.md`;
- `docs/DEPLOY_HETZNER_CPX42.md`;
- `docs/LEX_SOURCE_POLICY_SYSTEM.md`;
- `docs/LEX_AI_QUALITY.md`;
- `docs/LEX_GATEWAY.md`;
- `docs/REACT_MIGRATION_MASTER_PLAN.md`;
- `docs/OBSERVABILITY_AUDIT_PRODUCT.md`;
- `docs/E2E_TESTING_MATRIX.md`.

## `docs/specs/ministero/`

`docs/specs/ministero/` contiene specifiche e asset tecnici ministeriali versionati.

Consultarla sempre quando il lavoro riguarda:

- PCT, PST, PolisWeb;
- PDP Penale;
- PAT/SIGA;
- PTT/SIGIT, se presente nel perimetro;
- SIGP/Giudice di Pace;
- DatiAtto.xml, busta telematica e indici;
- firme digitali, CAdES/PAdES, PEC e ricevute;
- XML, XSD, DTD, WSDL e cataloghi servizi;
- AttoPrincipale, Procura, allegati, ricevute e vincoli ministeriali.

Regola: non inventare endpoint, campi XML, vincoli o norme. Se una specifica non chiarisce il caso, distinguere nel codice e nella documentazione tra dato certo, prassi locale, fallback prudente e punto da verificare.

## `deploy/hetzner/`

`deploy/hetzner/` e' il profilo operativo per produzione o fallback governato su VPS Linux Hetzner.

Consultarlo per lavori su:

- VPS Linux;
- Docker Compose;
- PostgreSQL e Redis;
- volumi `/data`;
- backup e restore;
- hardening;
- Caddy, reverse proxy, HTTPS/TLS;
- monitoraggio e stato servizi;
- procedure server-side.

File chiave:

- `deploy/hetzner/README.md`;
- `deploy/hetzner/docker-compose.hetzner.yml`;
- `deploy/hetzner/deploy.sh`;
- `deploy/hetzner/backup.sh`;
- `deploy/hetzner/restore_data.sh`;
- `deploy/hetzner/env.hetzner.example`;
- `deploy/hetzner/Caddyfile`.

## `.github/`

`.github/` governa workflow GitHub Actions, template e automazioni.

Consultarla quando il lavoro riguarda:

- CI;
- lint e syntax check;
- pytest;
- coverage;
- quality gate;
- CodeQL;
- dependency review;
- sicurezza supply-chain;
- automazioni di sincronizzazione branch;
- template issue/PR.

Regola: non disattivare workflow, non rimuovere controlli e non abbassare soglie per far passare una patch. Se un controllo deve cambiare, documentare motivo tecnico, impatto e presidio equivalente o migliore.

## `ops/`

`ops/` contiene runbook e procedure operative.

Consultarla quando il lavoro riguarda:

- deploy operativo;
- manutenzione;
- incident response;
- troubleshooting;
- restore;
- monitoraggio;
- verifiche post-release;
- checklist di rilascio.

Se una procedura operativa manca, non inventare passaggi irreversibili: documentare il limite e proporre una procedura prudente, verificabile e rollback-safe.

## Comportamento richiesto per telematico

Quando il task tocca telematico, deposito, portali, PEC, firme o conformita':

- leggere `AGENTS.md`;
- leggere i documenti pertinenti in `docs/`;
- leggere `docs/specs/ministero/`;
- individuare codice e test collegati;
- evitare scraping HTML non autorizzato dei portali;
- non salvare PIN, credenziali CNS/CIE/SPID o sessioni portale nel cloud;
- mantenere gli artefatti runtime sotto data root scrivibile e tenant-aware;
- mantenere la vista documenti a buste quando prevista;
- usare warning professionali e configurabili se un dato non e' certo;
- aggiornare test e documentazione quando cambia il comportamento reale.

## Comportamento richiesto per Lex AI/RAG

Quando il task tocca Lex AI, assistente fascicolo, RAG, retrieval, fonti o risposte assistite:

- consultare la documentazione Lex in `docs/`;
- non introdurre limiti fissi che tagliano documenti o sezioni;
- fornire a Lex l'inventario completo del fascicolo quando risponde sul fascicolo;
- distinguere fatti certi, inferenze, lacune, fallback e suggerimenti;
- non presentare output AI non verificato come verita' certa;
- preservare guardrail, fonti, confidence e revisione umana;
- aggiungere test anti-regressione quando cambia retrieval, indicizzazione o contesto.

## Comportamento richiesto per UI React/app-v2

Quando il task tocca UI React, Flask, Jinja, template, route o pagine app-v2:

- consultare `docs/`, i componenti esistenti e, se utile, `tools/open-design-support/`;
- mantenere microcopy in italiano;
- usare formati data/ora italiani tramite filtri condivisi;
- garantire responsive desktop, tablet e mobile;
- collegare nuove pagine a menu, route, API e fallback necessari;
- evitare placeholder visibili e card decorative senza azioni reali;
- mantenere coerenza con Bootstrap, design token e pattern esistenti;
- verificare stati vuoti, loading, errore, successo e permesso negato.

## Comportamento richiesto per storage/tenant

Quando il task tocca dati, tenant, JSON, SQLite, SQL o PostgreSQL:

- consultare `docs/STORAGE_MATRIX.md` e architettura storage;
- non introdurre fallback silenziosi;
- non salvare dati runtime in path repository;
- usare percorsi scrivibili, tenant-aware e coerenti con Docker/Railway/Hetzner;
- mantenere parita' JSON / SQLite / PostgreSQL dove prevista;
- aggiornare repository, migrazioni, test e documentazione;
- distinguere backend selezionato, backend effettivo e fallback governato.

## Comportamento richiesto per deploy/Hetzner

Quando il task tocca produzione, Hetzner, Docker, PostgreSQL, volumi, backup o restore:

- consultare `docs/DEPLOY.md`, `docs/DEPLOY_HETZNER_CPX42.md`, `deploy/hetzner/` e `ops/`;
- non salvare segreti nel repository;
- non inserire dati studio nel Product Pack;
- creare backup prima di deploy reali quando il runtime o i dati sono coinvolti;
- documentare rollback e verifiche post-deploy;
- verificare log, stato servizi, route principali e persistenza;
- mantenere separati Product Pack, Studio Local Pack e Update Pack.

Per modifiche solo documentali o tooling non avviare deploy applicativo, salvo richiesta esplicita dell'utente.

## Comportamento richiesto per CI/test/coverage

Quando il task tocca `.github/`, test, coverage o quality gate:

- consultare workflow e documentazione CI;
- non disattivare job per far passare una patch;
- non abbassare soglie coverage senza motivazione documentata e approvazione esplicita;
- non marcare test critici come `skip` per nascondere regressioni;
- aggiornare test quando cambia comportamento reale;
- distinguere gate minimo verde dal target utente del 100% coverage critica;
- confrontare ogni numero di qualita' con la baseline certa piu' recente.

## Checklist finale anti-regressione

Prima di dichiarare concluso un task, l'agente deve verificare:

- branch corretto e nessun branch temporaneo creato;
- `AGENTS.md` letto e rispettato;
- documentazione pertinente consultata;
- nessun vincolo esistente indebolito;
- nessun segreto o dato studio reale aggiunto;
- nessuna dipendenza runtime aggiunta senza autorizzazione;
- nessun file protetto modificato fuori scope;
- test o controlli pertinenti eseguiti;
- quality gate Codex eseguito quando il task riguarda tooling/documentazione agenti;
- commit in italiano quando richiesto;
- branch gemelli sincronizzati quando viene eseguito push;
- eventuali limiti residui dichiarati chiaramente nel report finale.
