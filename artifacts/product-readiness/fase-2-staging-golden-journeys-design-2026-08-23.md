# Fase 2 — Staging e golden journeys: disegno esecutivo

**Stato:** implementata e sottoposta ad audit automatico completo; nessuna capability P0 promossa a verificata.

**Data:** 23/08/2026, Europe/Rome.

**Dipendenze verificate:** Fase 0 e Fase 1 sul commit `9d3207bced4ac12a8b49fb19f97d190a9aaf1d4c`, con copia Docker locale e Hetzner healthy.

## Obiettivo delimitato

La Fase 2 rende ripetibile l'accettazione dei quindici percorsi P0. Non dichiara operativi PEC, firma, deposito, pagamenti, SdI o altri provider: prepara tenant sintetici, ruoli, dati controllati, esecuzioni automatiche, evidenze e rollback affinché tali prove possano essere eseguite senza contaminare dati o credenziali reali.

Il risultato è un **registro eseguibile dei golden journey**, non un nuovo menu e non una seconda dashboard. Il Product Readiness Center della Fase 1 continua a essere la superficie di lettura delle capability e conserva lo stato `Da verificare` finché non esiste l'evidenza richiesta per ogni singolo flusso.

## Evidenze iniziali e gap misurati

| Area | Evidenza presente | Limite da chiudere in Fase 2 |
| --- | --- | --- |
| Golden path | `pct/golden_paths.py` censisce sei suite aggregate e salva un report | Non rappresenta tutti i 15 percorsi P0, né fixture, ruoli, provider e rollback per journey. |
| Tenant e migrazione | Esistono test reali JSON → SQLite e rollback tenant | Mancano un contratto sintetico permanente A/B e una matrice multi-ruolo riusabile. |
| Smoke | Gli script App V2 controllano route, contratti, tenant e ruoli quando le credenziali sono disponibili | Gli smoke HTTP non sono una prova completa di journey, browser, accessibilità e rollback. |
| Browser e accessibilità | Vitest browser/Storybook usa Playwright; CI esegue contratti, build e Storybook | Le prove vanno collegate ai journey senza trasformare test headless in prova utente finale. |
| Prove reali | Fase 1 è stata provata materialmente sul browser locale | Le capability P0 non sono state ancora provate una a una con dati controllati. |

## Decisioni architetturali

1. **Fixture isolata e reversibile.** I tenant sintetici vivono esclusivamente sotto una root dedicata `data/golden-journeys/` oppure in una root temporanea fornita dai test. Non possono usare una root tenant reale, né credenziali, PEC, certificati, documenti o database degli studi.
2. **Dati di test deterministici.** Il seed definisce tenant A e B, profili amministratore, operatore e sola lettura, un cliente per tenant, un fascicolo, un documento PDF, ZIP, XML ed EML controllati, una PEC/ricevuta e dati economici non fiscali. I nomi, indirizzi e identificativi sono chiaramente sintetici.
3. **Fonte di verità controllata.** Le fixture usano SQLite tramite il normale contratto tenant; il manifest JSON è soltanto descrizione/versione del seed. Nessun nuovo JSON diventa fonte operativa del prodotto.
4. **Nessun provider mascherato.** PEC, firma, deposito, ricevute, SdI e pagamento usano fixture e dry-run interni nella Fase 2. Il report registra `provider=non_eseguito`; la verifica autorizzata di provider resta nelle fasi funzionali competenti.
5. **Runner unico e osservabile.** Ogni journey ha ID stabile, capacità collegate, ruoli ammessi, fixture richieste, selector Pytest, categoria browser, livello provider e rollback. Il runner persiste JSON e Markdown con durata, risultato e riferimento ai test.
6. **Rollback sicuro.** Il runner scrive in una singola directory di run e produce manifest di creazione. Il rollback è esplicito, rifiuta path esterni alla root dedicata e non elimina mai volumi, database o documenti applicativi reali.
7. **Nessuna regressione di UI.** La Fase 2 non modifica la shell React né introduce una seconda console. I dati del catalogo restano disponibili al Product Readiness Center già verificato; eventuali nuove visualizzazioni saranno progettate e approvate in una fase che richieda un cambiamento UX.

## Contratto dei quindici journey

| ID | Percorso | Fixture/ruoli | Guardrail automatico | Provider |
| --- | --- | --- | --- | --- |
| `lead-conflitto-cliente` | Lead → controllo conflitto → cliente | A/B, amministratore e operatore | anagrafiche, ricerca, tenant isolation | non applicabile |
| `cliente-preventivo-conferimento` | Cliente → preventivo → accettazione → mandato | A, amministratore/operatore | preventivi, conferimento, audit | non applicabile |
| `conferimento-fascicolo-procedura` | Conferimento → fascicolo → procedura iniziale | A, operatore | workflow commerciale e fascicoli | non applicabile |
| `pec-scadenza` | PEC ricevuta → fascicolo → proposta scadenza | A/B, operatore | PEC, scadenziario, isolamento | dry-run soltanto |
| `atto-firma-predeposito` | Atto → allegati → firma → predeposito | A, operatore | deposito guidato e busta | Local Signer non eseguito |
| `deposito-ricevute` | Deposito → ricevute → riconciliazione | A, operatore | timeline deposito e ricevute | canary non eseguito |
| `notifica-relata` | Notifica L. 53 → relata → invio locale → prova | A, operatore | notifiche, audit e lettore | canary non eseguito |
| `udienza-esito` | Udienza → note/esito → attività e termini | A, operatore | agenda, scadenziario e Regia | non applicabile |
| `timesheet-fattura-incasso` | Timesheet → parcella → fattura → incasso | A, amministratore/operatore | calcoli, permessi e saldo | pagamento/SdI non eseguiti |
| `documento-lex-export` | Documento → Lex → fonti → revisione → export | A, operatore | ACL documento e approvazione | AI locale controllata |
| `portale-firma-pagamento` | Invito portale → upload → firma → messaggio → pagamento | A/B, portale/operatore | token e isolamento | firma/pagamento non eseguiti |
| `migrazione-cutover-rollback` | SQLite → PostgreSQL → confronto → rollback | tenant migrazione sintetico | parità, snapshot e rollback | non applicabile |
| `backup-restore` | Backup → perdita simulata → restore verificato | tenant backup sintetico | backup/restore e integrità | non applicabile |
| `tenant-a-versus-b` | Accesso A a B negato e auditato | A/B, amministratore | RBAC, IDOR e audit | non applicabile |
| `readonly-write-denied` | Sola lettura tenta modifica, negata e auditata | A, sola lettura | RBAC write denial e audit | non applicabile |

## Matrice di prova della fase

| Requisito | Evidenza obbligatoria |
| --- | --- |
| Catalogo | 15 ID univoci, stabili e tutti collegati a capability, fixture, ruoli, test e rollback. |
| Fixture | Seed A/B ripetibile, senza segreti, con SQLite e contenuti documentali controllati. |
| Tenant/RBAC | Test A contro B e sola lettura contro scrittura, con audit o messaggio fail-closed. |
| Automazione | Runner esegue le 15 suite, persiste report JSON/Markdown e fallisce al primo journey non verde. |
| Browser/a11y/VRT | I guardrail Playwright/Storybook, axe e visual audit restano parte della pipeline; non sono sostitutivi della prova materiale. |
| Osservabilità | Report per journey con durata, selector, fixture, browser/provider status, path artefatto e rollback. |
| Performance | L'esecuzione non è caricata nel bootstrap React o nella route utente; nessuna scansione ricorsiva o provider call a runtime. |
| Reale locale | Docker `127.0.0.1:8080` healthy, browser visibile, click e scroll sul perimetro amministrativo invariato; i journey sensibili restano `Da verificare` finché non si eseguono le prove materiali indicate. |

## Sequenza di implementazione

1. Aggiungere catalogo, fixture e validazione di isolamento/rollback in moduli backend puri.
2. Collegare catalogo e runner al comando esistente dei golden path, preservando compatibilità con i sei path storici.
3. Aggiungere test unitari, fixture SQLite, tenant/RBAC e contratti del report, poi eseguire le suite mirate.
4. Integrare documentazione e generatori, senza promuovere lo stato delle capability.
5. Ricostruire Docker locale, eseguire proof reale del perimetro esposto, controllare performance e audit.
6. Bump di versione, commit, push gemello, CI, deploy Hetzner e verifica indipendente di SHA/container/HTTPS.

## Implementazione realizzata e audit del 23/08/2026

Il catalogo eseguibile risiede in `pct/golden_journeys.py`; dichiara esattamente quindici ID P0 stabili, fixture richieste, ruoli, selector Pytest, stato del provider e perimetro di rollback. Il comando `pct.cli golden-journey` prepara esclusivamente una root chiamata `data/golden-journeys`, esegue una journey alla volta e salva un report JSON/Markdown. Se una sola journey non è verde, il comando termina con codice non zero: non è possibile usare il report come falso verde.

La fixture `run-f2-c` ha creato tenant A e B tramite il normale contratto `GestioneTenant`, SQLite come `source_of_truth`, ruoli amministratore/avvocato/praticante, documenti controllati PDF/ZIP/XML/EML e manifest senza password persistite. Il rollback ha rimosso soltanto le run precedenti `run-f2-a` e `run-f2-b`, dopo controllo di root, marker e manifest; nessun archivio applicativo è stato toccato.

L'audit completo `run-f2-c`, concluso alle 19:18 del 23/08/2026, ha dato **15/15 journey passate, 0 fallite, 0 non eseguite**. L'evidenza generata è `data/golden-journeys/reports/golden_journeys_20260823_191851.json` (output runtime ignorato dal repository). Sono state eseguite le suite dei percorsi cliente/conflitto, preventivo/conferimento, fascicolo, PEC/scadenze, deposito e ricevute, notifiche/relata, agenda, fatturazione, Lex, portale, migrazione, backup, isolamento tenant e sola lettura.

Durante l'audit sono emerse e sono state corrette tre cause di regressione:

1. Il nodo `Anagrafica` di una busta `DatiAtto` v6 non veniva normalizzato allo schema v7 richiesto: ora la normalizzazione è ricorsiva e limita la conversione al namespace ministeriale dell'atto.
2. La lettura delle PEC non collegate lasciava un handle SQLite aperto su Windows: la chiusura esplicita impedisce che il file `PEC_AUDIT_DB` resti bloccato durante una rotazione controllata.
3. Il confronto JSON→SQLite trattava una proiezione SQL derivata (`profilo_deposito`) come perdita dati e applicava la normalizzazione a una sola fonte: ora la normalizzazione è simmetrica, senza ignorare alcun dato operativo.

I test aggiunti coprono catalogo/fixture/rollback, fallimento CLI, normalizzazione della busta e confronto mirror/SQL. Il runner rimane esterno al bootstrap React e non introduce route, chiamate provider, scansioni runtime o superfici UI nuove. Il Product Readiness Center espone l'audit automatico Fase 2 come guardrail completato, ma conserva per ogni capability lo stato `Da verificare` fino alla rispettiva prova browser e provider autorizzata.

## Rischi e risoluzioni

* **Rischio di contaminazione:** root di fixture separata, nomi sintetici e blocco path esterni.
* **Rischio falso-verde:** i risultati automatici diventano evidenza CI soltanto; browser/provider mantengono stato esplicito separato.
* **Rischio lentezza:** il runner non si avvia in bootstrap o UI; è CLI/test-only e produce report fuori dal percorso utente.
* **Rischio regressione dei golden path storici:** compatibilità conservata e test di regressione del catalogo esistente.
* **Rischio di provider reale:** nessuna chiamata provider è implementata nella fase; il report lo dichiara apertamente.

## Prova materiale locale — build 2.278.70

Il 23/08/2026 alle 19:52 Europe/Rome la copia Docker reale su `http://127.0.0.1:8080` è stata ricostruita senza cache. Tutti i container del profilo locale erano healthy e `/api/pronto` ha restituito `versione=2.278.70`.

Nel browser integrato reale sono stati verificati il caricamento completo della pagina **Prontezza prodotto**, gli avvisi di verità, le 17 capability ancora dichiarate `Da verificare`, lo scorrimento dall'inizio al fondo, l'apertura e il focus visibile del dettaglio **Autenticazione e cambio tenant**, nonché il click materiale su **Torna ad amministrazione** con arrivo alla pagina amministrativa. La navigazione responsive è stata controllata anche a 768 px con apertura e chiusura del menu mobile tramite click reale; il layout ha mantenuto controlli e testi leggibili.

Lo smoke prestazionale locale ha misurato `startup_ms=1782`, `runtime_metrics_ms=78`, `login_ms=0` e `health_ms=0`: nessun peggioramento rispetto al baseline iniziale di 1894,72 ms. L'evidenza runtime è `data/golden-journeys/reports/fase-2-performance-local-2.278.70.json` (ignorata dal repository perché contiene artefatti locali).
