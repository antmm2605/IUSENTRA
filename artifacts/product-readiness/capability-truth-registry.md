# Capability Truth Registry — P0

Versione registro: `2026.08.23.2`. Fonte autorevole: catalogo Python versionato.

Questo documento non attesta che una capability sia completa. Una prova non eseguita resta visibile come tale.

## Riepilogo

| Capability | Stato | Owner | Route | API | Storage | Ultimo smoke |
| --- | --- | --- | --- | --- | --- | --- |
| Autenticazione e cambio tenant | Da verificare | Identità e sicurezza | /login | /api/v1/ui/sessione e bootstrap | GestioneUtenti + audit tenant-aware (SQLite/PostgreSQL) | Audit automatico Fase 2 completato: prova browser e provider ancora richiesta |
| Apertura cliente | Da verificare | Anagrafiche | /clienti | /api/v1/ui/clienti | GestioneClienti tenant-aware; SQLite/PostgreSQL con mirror governato | Audit automatico Fase 2 completato: prova browser e provider ancora richiesta |
| Controllo conflitto | Da verificare | Anagrafiche e fascicoli | /ricerca-studio | /api/v1/ui/ricerca-studio | Repository clienti/fascicoli tenant-aware | Audit automatico Fase 2 completato: prova browser e provider ancora richiesta |
| Preventivo | Da verificare | Commerciale | /preventivi | /api/v1/ui/preventivi | Repository preventivi tenant-aware; SQLite/PostgreSQL | Audit automatico Fase 2 completato: prova browser e provider ancora richiesta |
| Mandato e conferimento | Da verificare | Commerciale | /preventivi/conferimento/nuovo | /api/v1/ui/preventivi/conferimento/nuovo | Repository conferimenti tenant-aware; SQLite/PostgreSQL | Audit automatico Fase 2 completato: prova browser e provider ancora richiesta |
| Fascicolo | Da verificare | Fascicoli | /fascicoli | /api/v1/ui/fascicoli | GestioneFascicoli + filesystem tenant-aware; metadati SQLite/PostgreSQL | Audit automatico Fase 2 completato: prova browser e provider ancora richiesta |
| Attività operative | Da verificare | Regia Operativa | /regia-operativa | /api/v1/ui/regia-operativa | Repository operativi tenant-aware | Audit automatico Fase 2 completato: prova browser e provider ancora richiesta |
| Documento e lettore interno | Da verificare | Documenti | /documenti | /api/v1/ui/documenti | Filesystem documentale tenant-aware + metadati fascicolo | Audit automatico Fase 2 completato: prova browser e provider ancora richiesta |
| PEC | Da verificare | Comunicazioni | /email | /api/v1/ui/email | Repository PEC tenant-aware; credenziali solo sul PC locale | Audit automatico Fase 2 completato: prova browser e provider ancora richiesta |
| Scadenza e termini | Da verificare | Programmazione | /scadenziario | /api/v1/ui/scadenziario | GestioneScadenziario tenant-aware; SQLite/PostgreSQL | Audit automatico Fase 2 completato: prova browser e provider ancora richiesta |
| Deposito telematico | Da verificare | Telematico | /fascicoli/:id/deposito/prepara | /api/v1/ui/fascicoli/:id/depositi/* | Fascicolo tenant-aware + repository deposito/audit | Audit automatico Fase 2 completato: prova browser e provider ancora richiesta |
| Ricevute telematiche | Da verificare | Telematico | /telematico | /api/v1/ui/fascicoli/:id/depositi/:depositoId/timeline | Repository deposito/audit tenant-aware | Audit automatico Fase 2 completato: prova browser e provider ancora richiesta |
| Fattura | Da verificare | Economico | /fatturazione | /api/v1/ui/fatturazione | Repository parcelle tenant-aware; SQLite/PostgreSQL | Audit automatico Fase 2 completato: prova browser e provider ancora richiesta |
| Pagamento e incasso | Da verificare | Economico | /incassi-pagamenti | /api/v1/ui/incassi-pagamenti | Repository pagamenti tenant-aware; SQLite/PostgreSQL | Audit automatico Fase 2 completato: prova browser e provider ancora richiesta |
| Portale cliente | Da verificare | Portale | /app/portale-clienti | /api/v1/ui/client-portal/dashboard | Repository portale tenant-aware; SQLite/PostgreSQL | Audit automatico Fase 2 completato: prova browser e provider ancora richiesta |
| Audit | Da verificare | Sicurezza | /audit | /api/v1/ui/audit | audit_log tenant-aware; SQLite/PostgreSQL | Audit automatico Fase 2 completato: prova browser e provider ancora richiesta |
| Chiusura fascicolo | Da verificare | Fascicoli | /fascicoli/:id | /api/v1/ui/fascicoli/:id | GestioneFascicoli tenant-aware; filesystem + SQLite/PostgreSQL metadati | Audit automatico Fase 2 completato: prova browser e provider ancora richiesta |

## Autenticazione e cambio tenant

| Campo | Valore |
| --- | --- |
| Stato | Da verificare — RBAC e isolamento sono censiti; resta richiesta la prova browser multi-ruolo e multi-tenant. |
| Versione | 2026.08.23.2 |
| Owner | Identità e sicurezza |
| Feature flag | routes.appV2.amministrazione |
| Route | /login |
| API | /api/v1/ui/sessione e bootstrap |
| Backend | pct.auth + shell React |
| Operazioni | accesso, chiusura sessione, cambio tenant autorizzato |
| Permessi | sessione autenticata |
| Storage | GestioneUtenti + audit tenant-aware (SQLite/PostgreSQL) |
| Ambiente locale | Non ancora verificato per questa capability |
| Produzione | Non ancora verificato per questa capability |
| Dipendenze | sessione, RBAC, tenant proprietario |
| Limitazioni | Nessuna promozione senza prova multi-ruolo e multi-tenant. |
| Rollback | Commit applicativo precedente e ricreazione Docker governata. |
| Incidenti | Nessun feed incidenti collegato al registro |
| Prossima azione | Eseguire matrice login/cambio tenant con quattro ruoli. |
| Test associati | tests/test_auth.py, tests/test_web_bootstrap.py |

| Prova | Stato | Riferimento | Nota |
| --- | --- | --- | --- |
| Test associati censiti; esito corrente da registrare | riferimento_disponibile | Inventario test della capability | Il registro non trasforma un file di test in un PASS senza esecuzione corrente. |
| Prova browser non ancora registrata | non_eseguito | Fase 2 — golden journeys | La presenza della UI non equivale a una prova reale sulla copia locale. |
| Nessun provider esterno necessario | non_applicabile | n.d. | n.d. |

## Apertura cliente

| Campo | Valore |
| --- | --- |
| Stato | Da verificare — Superficie React censita; manca prova reale per ruoli e tenant separati. |
| Versione | 2026.08.23.2 |
| Owner | Anagrafiche |
| Feature flag | routes.appV2.clienti |
| Route | /clienti |
| API | /api/v1/ui/clienti |
| Backend | web.services.react_clienti_bridge |
| Operazioni | ricerca, apertura scheda, consultazione cartella |
| Permessi | clienti.leggi |
| Storage | GestioneClienti tenant-aware; SQLite/PostgreSQL con mirror governato |
| Ambiente locale | Non ancora verificato per questa capability |
| Produzione | Non ancora verificato per questa capability |
| Dipendenze | anagrafiche, fascicoli |
| Limitazioni | Dati e permessi devono restare del tenant corrente. |
| Rollback | Commit applicativo precedente e ricreazione Docker governata. |
| Incidenti | Nessun feed incidenti collegato al registro |
| Prossima azione | Golden journey apertura cliente e controllo isolamento. |
| Test associati | tests/test_web_bootstrap.py |

| Prova | Stato | Riferimento | Nota |
| --- | --- | --- | --- |
| Test associati censiti; esito corrente da registrare | riferimento_disponibile | Inventario test della capability | Il registro non trasforma un file di test in un PASS senza esecuzione corrente. |
| Prova browser non ancora registrata | non_eseguito | Fase 2 — golden journeys | La presenza della UI non equivale a una prova reale sulla copia locale. |
| Nessun provider esterno necessario | non_applicabile | n.d. | n.d. |

## Controllo conflitto

| Campo | Valore |
| --- | --- |
| Stato | Da verificare — Il percorso e il perimetro dati sono censiti; il criterio di conflitto richiede prova e fixture dedicate. |
| Versione | 2026.08.23.2 |
| Owner | Anagrafiche e fascicoli |
| Feature flag | Nessun flag dedicato censito |
| Route | /ricerca-studio |
| API | /api/v1/ui/ricerca-studio |
| Backend | Ricerca Studio e repository tenant-aware |
| Operazioni | ricerca nominativi, segnalazione potenziale conflitto |
| Permessi | clienti.leggi, fascicoli.leggi |
| Storage | Repository clienti/fascicoli tenant-aware |
| Ambiente locale | Non ancora verificato per questa capability |
| Produzione | Non ancora verificato per questa capability |
| Dipendenze | ricerca studio, anagrafiche, fascicoli |
| Limitazioni | Non sostituisce la valutazione professionale del conflitto. |
| Rollback | Commit applicativo precedente e ripristino dei dati di fixture. |
| Incidenti | Nessun feed incidenti collegato al registro |
| Prossima azione | Definire fixture conflitto positiva, negativa e cross-tenant. |
| Test associati | tests/test_global_search.py |

| Prova | Stato | Riferimento | Nota |
| --- | --- | --- | --- |
| Test associati censiti; esito corrente da registrare | riferimento_disponibile | Inventario test della capability | Il registro non trasforma un file di test in un PASS senza esecuzione corrente. |
| Prova browser non ancora registrata | non_eseguito | Fase 2 — golden journeys | La presenza della UI non equivale a una prova reale sulla copia locale. |
| Nessun provider esterno necessario | non_applicabile | n.d. | n.d. |

## Preventivo

| Campo | Valore |
| --- | --- |
| Stato | Da verificare — La superficie React e le API sono censite; serve E2E con dati sintetici e ruoli. |
| Versione | 2026.08.23.2 |
| Owner | Commerciale |
| Feature flag | routes.appV2.preventivi |
| Route | /preventivi |
| API | /api/v1/ui/preventivi |
| Backend | web.services.react_preventivi_bridge |
| Operazioni | creazione, calcolo, stato, apertura fascicolo |
| Permessi | preventivi.leggi, preventivi.scrivi |
| Storage | Repository preventivi tenant-aware; SQLite/PostgreSQL |
| Ambiente locale | Non ancora verificato per questa capability |
| Produzione | Non ancora verificato per questa capability |
| Dipendenze | compensi forensi, clienti, fascicoli |
| Limitazioni | Importi, calcolo e audit vanno provati dal backend canonico. |
| Rollback | Commit applicativo precedente e rollback stato documentato. |
| Incidenti | Nessun feed incidenti collegato al registro |
| Prossima azione | Golden journey preventivo da cliente a fascicolo. |
| Test associati | tests/test_preventivi_wizard.py |

| Prova | Stato | Riferimento | Nota |
| --- | --- | --- | --- |
| Test associati censiti; esito corrente da registrare | riferimento_disponibile | Inventario test della capability | Il registro non trasforma un file di test in un PASS senza esecuzione corrente. |
| Prova browser non ancora registrata | non_eseguito | Fase 2 — golden journeys | La presenza della UI non equivale a una prova reale sulla copia locale. |
| Nessun provider esterno necessario | non_applicabile | n.d. | n.d. |

## Mandato e conferimento

| Campo | Valore |
| --- | --- |
| Stato | Da verificare — Il percorso è censito; firma, dati obbligatori e passaggio a fascicolo attendono prova integrata. |
| Versione | 2026.08.23.2 |
| Owner | Commerciale |
| Feature flag | routes.appV2.preventivi |
| Route | /preventivi/conferimento/nuovo |
| API | /api/v1/ui/preventivi/conferimento/nuovo |
| Backend | Bridge preventivi/conferimenti |
| Operazioni | creazione conferimento, stato, apertura fascicolo |
| Permessi | preventivi.leggi, preventivi.scrivi |
| Storage | Repository conferimenti tenant-aware; SQLite/PostgreSQL |
| Ambiente locale | Non ancora verificato per questa capability |
| Produzione | Non ancora verificato per questa capability |
| Dipendenze | preventivi, fascicoli, audit |
| Limitazioni | Non certifica la validità giuridica del mandato senza verifica dei requisiti. |
| Rollback | Commit applicativo precedente e rollback stato documentato. |
| Incidenti | Nessun feed incidenti collegato al registro |
| Prossima azione | Golden journey conferimento con controllo audit e permessi. |
| Test associati | tests/test_preventivi_conferimento_route.py |

| Prova | Stato | Riferimento | Nota |
| --- | --- | --- | --- |
| Test associati censiti; esito corrente da registrare | riferimento_disponibile | Inventario test della capability | Il registro non trasforma un file di test in un PASS senza esecuzione corrente. |
| Prova browser non ancora registrata | non_eseguito | Fase 2 — golden journeys | La presenza della UI non equivale a una prova reale sulla copia locale. |
| Nessun provider esterno necessario | non_applicabile | n.d. | n.d. |

## Fascicolo

| Campo | Valore |
| --- | --- |
| Stato | Da verificare — La UI React è censita; fixture e verifica di apertura multi-ruolo sono previste nella Fase 2. |
| Versione | 2026.08.23.2 |
| Owner | Fascicoli |
| Feature flag | routes.appV2.fascicoli |
| Route | /fascicoli |
| API | /api/v1/ui/fascicoli |
| Backend | web.services.react_fascicoli_bridge |
| Operazioni | lista, creazione, apertura workspace, archivio |
| Permessi | fascicoli.leggi, fascicoli.scrivi |
| Storage | GestioneFascicoli + filesystem tenant-aware; metadati SQLite/PostgreSQL |
| Ambiente locale | Non ancora verificato per questa capability |
| Produzione | Non ancora verificato per questa capability |
| Dipendenze | clienti, documenti, deposito |
| Limitazioni | Il lettore e gli allegati richiedono prove formato per formato. |
| Rollback | Commit applicativo precedente; nessuna cancellazione dei dati tenant. |
| Incidenti | Nessun feed incidenti collegato al registro |
| Prossima azione | Golden journey fascicolo nuovo/aperto con tenant A/B. |
| Test associati | tests/test_fascicoli.py, tests/test_web_bootstrap.py |

| Prova | Stato | Riferimento | Nota |
| --- | --- | --- | --- |
| Test associati censiti; esito corrente da registrare | riferimento_disponibile | Inventario test della capability | Il registro non trasforma un file di test in un PASS senza esecuzione corrente. |
| Prova browser non ancora registrata | non_eseguito | Fase 2 — golden journeys | La presenza della UI non equivale a una prova reale sulla copia locale. |
| Nessun provider esterno necessario | non_applicabile | n.d. | n.d. |

## Attività operative

| Campo | Valore |
| --- | --- |
| Stato | Da verificare — Le attività sono censite come superficie React; serve prova delle azioni collegate e dello stato vuoto. |
| Versione | 2026.08.23.2 |
| Owner | Regia Operativa |
| Feature flag | routes.appV2.regiaOperativa |
| Route | /regia-operativa |
| API | /api/v1/ui/regia-operativa |
| Backend | Bridge Regia Operativa |
| Operazioni | lettura attività, prioritizzazione, apertura contesto |
| Permessi | fascicoli.leggi |
| Storage | Repository operativi tenant-aware |
| Ambiente locale | Non ancora verificato per questa capability |
| Produzione | Non ancora verificato per questa capability |
| Dipendenze | agenda, scadenziario, fascicoli |
| Limitazioni | Il registro non inferisce la completezza delle singole attività. |
| Rollback | Commit applicativo precedente e ricreazione Docker governata. |
| Incidenti | Nessun feed incidenti collegato al registro |
| Prossima azione | Golden journey attività da apertura a contesto collegato. |
| Test associati | tests/test_regia_ui_react.py |

| Prova | Stato | Riferimento | Nota |
| --- | --- | --- | --- |
| Test associati censiti; esito corrente da registrare | riferimento_disponibile | Inventario test della capability | Il registro non trasforma un file di test in un PASS senza esecuzione corrente. |
| Prova browser non ancora registrata | non_eseguito | Fase 2 — golden journeys | La presenza della UI non equivale a una prova reale sulla copia locale. |
| Nessun provider esterno necessario | non_applicabile | n.d. | n.d. |

## Documento e lettore interno

| Campo | Valore |
| --- | --- |
| Stato | Da verificare — Il lettore interno è requisito primario; la matrice PDF/ZIP/XML/EML/DOCX/P7M deve essere provata realmente. |
| Versione | 2026.08.23.2 |
| Owner | Documenti |
| Feature flag | routes.appV2.documenti |
| Route | /documenti |
| API | /api/v1/ui/documenti |
| Backend | Bridge documenti e preview tenant-aware |
| Operazioni | elenco, preview interna, download autorizzato |
| Permessi | documenti.leggi |
| Storage | Filesystem documentale tenant-aware + metadati fascicolo |
| Ambiente locale | Non ancora verificato per questa capability |
| Produzione | Non ancora verificato per questa capability |
| Dipendenze | fascicoli, PEC, preview firmata |
| Limitazioni | Nessun formato non supportato deve aprire un fallback esterno silenzioso. |
| Rollback | Commit applicativo precedente, senza toccare volumi documentali. |
| Incidenti | Nessun feed incidenti collegato al registro |
| Prossima azione | Golden journey lettore con almeno PDF, ZIP e un formato non PDF. |
| Test associati | tests/test_signed_attachment_preview.py |

| Prova | Stato | Riferimento | Nota |
| --- | --- | --- | --- |
| Test associati censiti; esito corrente da registrare | riferimento_disponibile | Inventario test della capability | Il registro non trasforma un file di test in un PASS senza esecuzione corrente. |
| Prova browser non ancora registrata | non_eseguito | Fase 2 — golden journeys | La presenza della UI non equivale a una prova reale sulla copia locale. |
| Nessun provider esterno necessario | non_applicabile | n.d. | n.d. |

## PEC

| Campo | Valore |
| --- | --- |
| Stato | Da verificare — La UI è censita; l'invio operativo deve restare locale e richiede tenant sintetico/canary non distruttivo. |
| Versione | 2026.08.23.2 |
| Owner | Comunicazioni |
| Feature flag | routes.appV2.email |
| Route | /email |
| API | /api/v1/ui/email |
| Backend | web.services.react_email_bridge + Local Signer |
| Operazioni | lettura, preview, preparazione invio locale, ricevute |
| Permessi | pec.leggi, pec.scrivi |
| Storage | Repository PEC tenant-aware; credenziali solo sul PC locale |
| Ambiente locale | Non ancora verificato per questa capability |
| Produzione | Non ancora verificato per questa capability |
| Dipendenze | Local Signer, casella PEC, lettore documenti |
| Limitazioni | Il server non invia PEC operative; nessuna prova provider è registrata in Fase 1. |
| Rollback | Commit precedente e mantenimento dei dati/credenziali locali. |
| Incidenti | Nessun feed incidenti collegato al registro |
| Prossima azione | Golden journey PEC con sandbox o canary non distruttivo. |
| Test associati | tests/test_email_client.py |

| Prova | Stato | Riferimento | Nota |
| --- | --- | --- | --- |
| Test associati censiti; esito corrente da registrare | riferimento_disponibile | Inventario test della capability | Il registro non trasforma un file di test in un PASS senza esecuzione corrente. |
| Prova browser non ancora registrata | non_eseguito | Fase 2 — golden journeys | La presenza della UI non equivale a una prova reale sulla copia locale. |
| Verifica provider non ancora registrata | da_verificare | Fase 2 — tenant sintetico e canary non distruttivo | n.d. |

## Scadenza e termini

| Campo | Valore |
| --- | --- |
| Stato | Da verificare — La correzione Fase 0 è provata; il journey P0 completo con ruoli, date e collegamenti resta da eseguire. |
| Versione | 2026.08.23.2 |
| Owner | Programmazione |
| Feature flag | routes.appV2.scadenziario |
| Route | /scadenziario |
| API | /api/v1/ui/scadenziario |
| Backend | web.services.react_scadenziario_bridge |
| Operazioni | lista, creazione, calcolo, promemoria |
| Permessi | scadenze.leggi, scadenze.scrivi |
| Storage | GestioneScadenziario tenant-aware; SQLite/PostgreSQL |
| Ambiente locale | Non ancora verificato per questa capability |
| Produzione | Non ancora verificato per questa capability |
| Dipendenze | agenda, fascicoli, calendario |
| Limitazioni | Date e orari visibili devono restare Europe/Rome; nessuna data raw in UI. |
| Rollback | Commit applicativo precedente e ricreazione Docker governata. |
| Incidenti | Nessun feed incidenti collegato al registro |
| Prossima azione | Golden journey scadenza, calcolo e collegamento fascicolo. |
| Test associati | tests/test_scadenziario.py, tests/test_react_scadenziario_additions.py |

| Prova | Stato | Riferimento | Nota |
| --- | --- | --- | --- |
| Test associati censiti; esito corrente da registrare | riferimento_disponibile | Inventario test della capability | Il registro non trasforma un file di test in un PASS senza esecuzione corrente. |
| Prova browser non ancora registrata | non_eseguito | Fase 2 — golden journeys | La presenza della UI non equivale a una prova reale sulla copia locale. |
| Nessun provider esterno necessario | non_applicabile | n.d. | n.d. |

## Deposito telematico

| Campo | Valore |
| --- | --- |
| Stato | Da verificare — Non è dichiarato completo: requisiti ministeriali, firma multipla, ricevute e invio locale richiedono prove reali. |
| Versione | 2026.08.23.2 |
| Owner | Telematico |
| Feature flag | Nessun flag dedicato censito |
| Route | /fascicoli/:id/deposito/prepara |
| API | /api/v1/ui/fascicoli/:id/depositi/* |
| Backend | Bridge fascicoli/deposito + Local Signer |
| Operazioni | classificazione, indice, firma, preparazione busta, invio locale |
| Permessi | fascicoli.leggi, fascicoli.scrivi, pec.scrivi |
| Storage | Fascicolo tenant-aware + repository deposito/audit |
| Ambiente locale | Non ancora verificato per questa capability |
| Produzione | Non ancora verificato per questa capability |
| Dipendenze | Local Signer, PEC locale, PST/portale, fascicoli |
| Limitazioni | Assenza di requisito ministeriale blocca solo il deposito valido con messaggio esplicito. |
| Rollback | Commit precedente; nessun invio server-side e nessuna cancellazione delle prove. |
| Incidenti | Nessun feed incidenti collegato al registro |
| Prossima azione | Prova senza invio, firma multipla reale e canary conforme. |
| Test associati | tests/test_deposito.py, tests/test_deposito_guidato.py |

| Prova | Stato | Riferimento | Nota |
| --- | --- | --- | --- |
| Test associati censiti; esito corrente da registrare | riferimento_disponibile | Inventario test della capability | Il registro non trasforma un file di test in un PASS senza esecuzione corrente. |
| Prova browser non ancora registrata | non_eseguito | Fase 2 — golden journeys | La presenza della UI non equivale a una prova reale sulla copia locale. |
| Verifica provider non ancora registrata | da_verificare | Fase 2 — tenant sintetico e canary non distruttivo | n.d. |

## Ricevute telematiche

| Campo | Valore |
| --- | --- |
| Stato | Da verificare — La persistenza e la timeline sono censite; servono fixture e prova reale del ciclo ricevuta. |
| Versione | 2026.08.23.2 |
| Owner | Telematico |
| Feature flag | Nessun flag dedicato censito |
| Route | /telematico |
| API | /api/v1/ui/fascicoli/:id/depositi/:depositoId/timeline |
| Backend | Repository deposito e bridge fascicoli |
| Operazioni | importazione, timeline, evidence pack, consultazione |
| Permessi | fascicoli.leggi, fascicoli.scrivi |
| Storage | Repository deposito/audit tenant-aware |
| Ambiente locale | Non ancora verificato per questa capability |
| Produzione | Non ancora verificato per questa capability |
| Dipendenze | deposito, PEC, lettore documenti |
| Limitazioni | Una ricevuta non può essere registrata come esito reale senza fonte verificabile. |
| Rollback | Commit precedente e conservazione delle evidenze del fascicolo. |
| Incidenti | Nessun feed incidenti collegato al registro |
| Prossima azione | Golden journey importazione e lettura ricevuta controllata. |
| Test associati | tests/test_deposito_guidato.py, tests/test_regia_deposito_receipts.py |

| Prova | Stato | Riferimento | Nota |
| --- | --- | --- | --- |
| Test associati censiti; esito corrente da registrare | riferimento_disponibile | Inventario test della capability | Il registro non trasforma un file di test in un PASS senza esecuzione corrente. |
| Prova browser non ancora registrata | non_eseguito | Fase 2 — golden journeys | La presenza della UI non equivale a una prova reale sulla copia locale. |
| Verifica provider non ancora registrata | da_verificare | Fase 2 — tenant sintetico e canary non distruttivo | n.d. |

## Fattura

| Campo | Valore |
| --- | --- |
| Stato | Da verificare — La superficie React e le API sono censite; emissione, firma e canali esterni attendono prove per ruoli. |
| Versione | 2026.08.23.2 |
| Owner | Economico |
| Feature flag | routes.appV2.fatturazione |
| Route | /fatturazione |
| API | /api/v1/ui/fatturazione |
| Backend | web.services.react_fatturazione_bridge |
| Operazioni | creazione, calcolo backend, stato, preparazione XML |
| Permessi | fatturazione.leggi, fatturazione.scrivi |
| Storage | Repository parcelle tenant-aware; SQLite/PostgreSQL |
| Ambiente locale | Non ancora verificato per questa capability |
| Produzione | Non ancora verificato per questa capability |
| Dipendenze | clienti, pagamenti, SdI, PEC locale |
| Limitazioni | Importi visibili devono restare in formato euro italiano. |
| Rollback | Commit precedente e rollback stato senza eliminare documenti fiscali. |
| Incidenti | Nessun feed incidenti collegato al registro |
| Prossima azione | Golden journey fattura con calcolo, permessi e prova non distruttiva. |
| Test associati | tests/test_fatturazione.py |

| Prova | Stato | Riferimento | Nota |
| --- | --- | --- | --- |
| Test associati censiti; esito corrente da registrare | riferimento_disponibile | Inventario test della capability | Il registro non trasforma un file di test in un PASS senza esecuzione corrente. |
| Prova browser non ancora registrata | non_eseguito | Fase 2 — golden journeys | La presenza della UI non equivale a una prova reale sulla copia locale. |
| Verifica provider non ancora registrata | da_verificare | Fase 2 — tenant sintetico e canary non distruttivo | n.d. |

## Pagamento e incasso

| Campo | Valore |
| --- | --- |
| Stato | Da verificare — Il percorso è censito; riconciliazione, permessi e collegamento documento vanno provati con dati sintetici. |
| Versione | 2026.08.23.2 |
| Owner | Economico |
| Feature flag | routes.appV2.incassiPagamenti |
| Route | /incassi-pagamenti |
| API | /api/v1/ui/incassi-pagamenti |
| Backend | web.services.react_incassi_pagamenti_bridge |
| Operazioni | registrazione incasso, stato, collegamento fattura |
| Permessi | fatturazione.leggi, fatturazione.scrivi |
| Storage | Repository pagamenti tenant-aware; SQLite/PostgreSQL |
| Ambiente locale | Non ancora verificato per questa capability |
| Produzione | Non ancora verificato per questa capability |
| Dipendenze | fatturazione, provider pagamento |
| Limitazioni | Nessun esito provider è dichiarato senza prova corrente. |
| Rollback | Commit precedente e rollback di stato auditato. |
| Incidenti | Nessun feed incidenti collegato al registro |
| Prossima azione | Golden journey incasso, collegamento e lettura saldo. |
| Test associati | tests/test_portale_economici.py |

| Prova | Stato | Riferimento | Nota |
| --- | --- | --- | --- |
| Test associati censiti; esito corrente da registrare | riferimento_disponibile | Inventario test della capability | Il registro non trasforma un file di test in un PASS senza esecuzione corrente. |
| Prova browser non ancora registrata | non_eseguito | Fase 2 — golden journeys | La presenza della UI non equivale a una prova reale sulla copia locale. |
| Verifica provider non ancora registrata | da_verificare | Fase 2 — tenant sintetico e canary non distruttivo | n.d. |

## Portale cliente

| Campo | Valore |
| --- | --- |
| Stato | Da verificare — Il contratto React è censito; inviti, token hashati e isolamento richiedono prova end-to-end dedicata. |
| Versione | 2026.08.23.2 |
| Owner | Portale |
| Feature flag | routes.appV2.clientPortal |
| Route | /app/portale-clienti |
| API | /api/v1/ui/client-portal/dashboard |
| Backend | web.services.react_client_portal_bridge |
| Operazioni | dashboard studio, inviti, chat, documenti, appuntamenti |
| Permessi | portale_clienti.leggi, portale_clienti.scrivi |
| Storage | Repository portale tenant-aware; SQLite/PostgreSQL |
| Ambiente locale | Non ancora verificato per questa capability |
| Produzione | Non ancora verificato per questa capability |
| Dipendenze | identità, documenti, fascicoli |
| Limitazioni | Token e dati personali non sono esposti dal registro. |
| Rollback | Commit precedente; i token non vengono rigenerati dal rollback del registro. |
| Incidenti | Nessun feed incidenti collegato al registro |
| Prossima azione | Golden journey invito, accesso e isolamento tenant. |
| Test associati | tests/test_client_portal_api.py, tests/test_client_portal_access.py |

| Prova | Stato | Riferimento | Nota |
| --- | --- | --- | --- |
| Test associati censiti; esito corrente da registrare | riferimento_disponibile | Inventario test della capability | Il registro non trasforma un file di test in un PASS senza esecuzione corrente. |
| Prova browser non ancora registrata | non_eseguito | Fase 2 — golden journeys | La presenza della UI non equivale a una prova reale sulla copia locale. |
| Nessun provider esterno necessario | non_applicabile | n.d. | n.d. |

## Audit

| Campo | Valore |
| --- | --- |
| Stato | Da verificare — La superficie è censita; occorre acquisire una prova che ogni P0 scriva l'evento atteso senza dati sensibili. |
| Versione | 2026.08.23.2 |
| Owner | Sicurezza |
| Feature flag | routes.appV2.audit |
| Route | /audit |
| API | /api/v1/ui/audit |
| Backend | web.services.react_audit_bridge |
| Operazioni | lista, filtro, dettaglio redatto, export autorizzato |
| Permessi | audit.leggi |
| Storage | audit_log tenant-aware; SQLite/PostgreSQL |
| Ambiente locale | Non ancora verificato per questa capability |
| Produzione | Non ancora verificato per questa capability |
| Dipendenze | RBAC, tutti i flussi P0 |
| Limitazioni | Il registro non sostituisce gli eventi audit del tenant. |
| Rollback | Commit precedente e conservazione immutabile degli eventi audit. |
| Incidenti | Nessun feed incidenti collegato al registro |
| Prossima azione | Matrice audit P0 con verifica redazione e permessi. |
| Test associati | tests/test_audit_routes.py |

| Prova | Stato | Riferimento | Nota |
| --- | --- | --- | --- |
| Test associati censiti; esito corrente da registrare | riferimento_disponibile | Inventario test della capability | Il registro non trasforma un file di test in un PASS senza esecuzione corrente. |
| Prova browser non ancora registrata | non_eseguito | Fase 2 — golden journeys | La presenza della UI non equivale a una prova reale sulla copia locale. |
| Nessun provider esterno necessario | non_applicabile | n.d. | n.d. |

## Chiusura fascicolo

| Campo | Valore |
| --- | --- |
| Stato | Da verificare — Il percorso è registrato, ma requisiti di chiusura, allegati e audit devono essere provati senza perdere dati. |
| Versione | 2026.08.23.2 |
| Owner | Fascicoli |
| Feature flag | routes.appV2.fascicoli |
| Route | /fascicoli/:id |
| API | /api/v1/ui/fascicoli/:id |
| Backend | Bridge fascicoli e repository stato |
| Operazioni | verifica requisiti, archiviazione, consultazione storico |
| Permessi | fascicoli.leggi, fascicoli.scrivi |
| Storage | GestioneFascicoli tenant-aware; filesystem + SQLite/PostgreSQL metadati |
| Ambiente locale | Non ancora verificato per questa capability |
| Produzione | Non ancora verificato per questa capability |
| Dipendenze | fascicoli, documenti, audit, fatturazione |
| Limitazioni | La chiusura non può mascherare dati, ricevute o obblighi ancora aperti. |
| Rollback | Commit precedente e ripristino stato senza rimuovere documenti tenant. |
| Incidenti | Nessun feed incidenti collegato al registro |
| Prossima azione | Golden journey requisiti, chiusura, storico e controllo accessi. |
| Test associati | tests/test_fascicoli.py, tests/test_fascicoli_pagination.py |

| Prova | Stato | Riferimento | Nota |
| --- | --- | --- | --- |
| Test associati censiti; esito corrente da registrare | riferimento_disponibile | Inventario test della capability | Il registro non trasforma un file di test in un PASS senza esecuzione corrente. |
| Prova browser non ancora registrata | non_eseguito | Fase 2 — golden journeys | La presenza della UI non equivale a una prova reale sulla copia locale. |
| Nessun provider esterno necessario | non_applicabile | n.d. | n.d. |
