# Fase 8 — Intake, Entity Graph e compliance

Data: 25/08/2026 (Europe/Rome)
Ambiente di accettazione locale: `http://127.0.0.1:8080`
Stato: implementazione e prove locali documentate, rilascio remoto da eseguire sul commit della fase.

## Risultato operativo

La CRM usa il linguaggio dello studio legale: `Acquisizione e apertura incarichi`, con le colonne `Primo contatto`, `Istruttoria iniziale`, `Conferimento da valutare`, `Preventivo e incarico`, `Non conferiti` e `Incarico conferito`. Il contatto tecnico di collaudo non è stato conservato.

Per ogni lead sono ora disponibili una barriera informativa persistente, il relativo audit e la segregazione reale degli accessi. La barriera è attiva con criterio deny-by-default: è visibile solo all'operatore che l'ha istituita e ai professionisti scelti espressamente. La creazione, modifica e revoca richiedono una motivazione e producono un evento audit/outbox. Un operatore non autorizzato non riceve il lead nel payload React e non può raggiungere le API CRM collegate.

La barriera non equivale a una clearance sul conflitto di interessi e non sostituisce l'astensione o la decisione professionale. La UI lo dichiara espressamente.

La presentazione dei documenti in Fascicolo mostra inoltre etichette leggibili, ad esempio `Comunicazione / ricevuta` e `Provvedimento - decreto`, invece degli enum tecnici. Classificazione, evidenze, fonti e confidenza restano dati separati e verificabili.

## Modello, sicurezza e parità dati

Le migrazioni SQLite e PostgreSQL introducono le tabelle tenant-aware:

- `ethical_walls`;
- `ethical_wall_members`;
- `ethical_wall_audit`.

Le rotte JSON applicano il resolver di accesso prima di leggere o mutare un lead. Il bridge React elimina dal payload i record protetti per l'operatore non autorizzato. Gli eventi usano l'outbox transazionale; il mirror JSON resta un mirror controllato e non sostituisce `studio.db` o PostgreSQL.

## Fonti e limiti giuridici

- [Codice deontologico forense, art. 24, conflitto di interessi](https://codicedeontologico-cnf.it/voci/art-24-cdf-conflitto-di-interessi/).
- [Corte di cassazione, rassegna marzo 2021](https://www.cortedicassazione.it/resources/cms/documents/RASSEGNA_MARZO_2021.pdf).
- [Garante per la protezione dei dati personali, misure di sicurezza](https://www.garanteprivacy.it/temi/cybersecurity/misure-di-sicurezza).

Lo screening AML interroga la lista consolidata UE una volta e svolge il confronto localmente: nessun nominativo dello studio viene trasmesso al provider. Per il collaudo è stata registrata la versione `Wed, 05 Aug 2026 14:50:10 GMT`, hash SHA-256 `0c83e632fea7709d9c75bdd1deb4fa50782a93d2c99459f01c7a7a2d873c79c9`, esito `NESSUN_RISCONTRO`. L'assenza di riscontro non sostituisce valutazione, identificazione del titolare effettivo, PEP, KYC o riesame professionale. Se una fonte non è disponibile, il sistema rende esplicito l'esito e richiede riesame, senza conferme silenziose.

## Prove eseguite

Guardrail automatici eseguiti con esito positivo:

- `python -m compileall -q pct/crm_intake.py web/bootstrap/crm_routes.py web/services/react_crm_bridge.py`;
- `pnpm --dir frontend exec tsc --noEmit --pretty false`;
- `pnpm --dir frontend build`;
- `python -m pytest tests/test_aml_screening.py tests/test_antiriciclaggio.py tests/test_crm_intake.py tests/test_crm_routes.py tests/test_react_crm_bridge.py tests/test_tenant_isolation_runtime.py tests/test_react_shell.py -q --tb=short`;
- `git diff --check`.

Prova materiale eseguita dopo ricostruzione Docker della copia locale e risposta positiva di `/api/pronto`:

1. In CRM è stato creato un contatto strettamente di collaudo, è stata istituita una barriera con un professionista autorizzato, sono stati aperti i controlli di gestione e la barriera è stata revocata con motivazione. I messaggi di successo e i controlli visibili sono stati osservati nella UI.
2. Il contatto, la barriera, il relativo audit, outbox, nodo del grafo e i due mirror JSON sono stati poi eliminati in modo mirato; una verifica SQL e dei mirror ha confermato zero occorrenze residue.
3. La CRM ricaricata non mostra il contatto di collaudo né la voce tecnica `QA Persistenza Fase 8`; il titolo e la disposizione delle sei colonne sono leggibili senza overflow orizzontale a 1.329 px.
4. Il Fascicolo `DC5BF1DB` è stato percorso nella sezione Documenti: le etichette sono leggibili, il lettore interno ha aperto un documento P7M e il click reale su `Scarica` ha prodotto il messaggio `Download avviato`.
5. Sono stati verificati layout senza overflow su desktop, tablet e mobile; i controlli principali della CRM restano raggiungibili e non sovrapposti.

Non sono stati inviati PEC, depositi, notifiche o comunicazioni reali durante questa prova.

## File principali

- `pct/crm_intake.py`
- `pct/sql/20260824_crm_intake.sql`
- `pct/sql/20260824_crm_intake_postgres.sql`
- `web/bootstrap/crm_routes.py`
- `web/services/react_crm_bridge.py`
- `frontend/src/crmData.ts`
- `frontend/src/components/CrmPage.tsx`
- `frontend/src/components/CrmPage.css`
- `web/services/react_fascicoli_bridge.py`
- `tests/test_crm_intake.py`
- `tests/test_crm_routes.py`
- `tests/test_react_crm_bridge.py`

## Chiusura della fase

Restano parte della chiusura il commit dei file elencati, il push dei due branch gemelli, il deploy Hetzner sullo stesso commit e la verifica del container applicativo unico e dell'health endpoint pubblico. La fase successiva non viene dichiarata avviata come consegnata finché questi passaggi non sono registrati.
