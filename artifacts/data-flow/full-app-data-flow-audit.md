# Audit operativo dati, tenant, React e sottomenu

Data: 2026-06-14.

Questo report documenta il controllo richiesto su tutto l'applicativo come sistema unico: menu, sottomenu, alias visibili, route React, API, tenant, JSON, SQLite, PostgreSQL e repository dedicati.

## Perimetro coperto dal contratto

Il contratto applicativo vive in `pct/data_flow_contract.py` e copre:

- Panoramica;
- Regia Operativa;
- Ricerca Studio;
- Agenda con `Calendario`, `Nuovo Appuntamento`, `Timesheet`;
- Fascicoli con `Tutti i Fascicoli`, `Nuovo Fascicolo`, `Archivio` e `Prepara deposito`;
- Clienti e Anagrafiche con `Anagrafica`, `Nuovo Cliente`, `Cartelle Condivise`, `Portale Clienti`;
- Soggetti e Parti;
- Comunicazioni con `Email PEC`, alias `PEC`, `Notifiche legali`, alias `L.53`, `Email ordinaria`, alias `SMTP`, `Messaggi`, `Nuovo SMS/WA`;
- Scadenze e Termini;
- Servizi Telematici;
- Studio con `Studio`, `Parcelle e Fatture`, `Preventivi e Incarichi`, `Compensi Forensi`, `Documenti`, `Redazione Atti`, `Statistiche`, `Ricerca Legale`, `Legal Skills`, `Regia Agentica`, `Archivio Giurisprudenza`, `Strumenti Forensi`, `Strumenti Operativi`;
- Sito Studio;
- Impostazioni;
- Amministrazione;
- topbar operativa.

Ogni area dichiara route React, voci di menu, API, path tenant-aware, JSON storici, tabelle SQLite, tabelle PostgreSQL o repository esterni. Se una nuova funzione non entra in questo schema, va considerata non governata.

## Riparazione database tenant locale

Tenant controllato: `tenant-8bf98719c459`.

Diagnosi iniziale:

- SQLite apriva `studio.db`, ma l'indice FTS `search_documenti` produceva errore `database disk image is malformed`.
- Il mirror rigenerabile `moduli_json_records` era da controllare prima di riallineare i JSON tenant-aware.

Riparazione consentita:

- `moduli_json_records`: eliminato e ricostruito solo se richiesto con `--repair-json-mirror`.
- `search_documenti`: eliminato e ricostruito solo se richiesto con `--repair-search-index`.
- `VACUUM` usato sul database locale quando l'indice FTS impediva la ricreazione delle shadow table.

Dati principali non toccati:

- fascicoli;
- clienti;
- agenda;
- scadenze;
- messaggi;
- documenti del fascicolo;
- comunicazioni.

Esito del controllo successivo senza riparazione:

- `PRAGMA quick_check`: `ok`;
- `clienti`: 12 record leggibili;
- `fascicoli`: 7 record leggibili;
- `appuntamenti`: 390 record leggibili;
- `scadenze`: 235 record leggibili;
- `messaggi`: 1 record leggibile;
- `moduli_dati`: 42 record leggibili;
- `moduli_json_records`: 3734 record leggibili;
- `search_documenti`: indice leggibile, schema corretto, 0 record indicizzati.

## Comandi registrati

```powershell
python scripts\audit_data_flow_contract.py --registry data\tenants.json --repair-json-mirror --repair-search-index --json
python scripts\audit_data_flow_contract.py --registry data\tenants.json --json
python -m py_compile scripts\audit_data_flow_contract.py pct\data_flow_contract.py pct\storage_migration.py pct\storage_migration_full.py pct\storage_postgres.py
python -m pytest tests\test_data_flow_contract.py tests\test_storage_postgres_migration.py::test_migrate_core_storage_to_postgres_produce_report_consistente tests\test_topbar_operational_api.py::test_topbar_today_notifications_deadlines_recent_and_timer tests\test_topbar_operational_api.py::test_topbar_react_traccia_recenti_sulle_rotte_profonde tests\test_support_remote.py::test_support_remote_studio_user_can_request_assistance_from_studio tests\test_studio_voice_assistant.py::test_studio_voice_assistant_file_senza_mojibake_e_collegato -q
node frontend\scripts\check-react-contracts.mjs
node scripts\react-migration\check-route-gate.mjs
pnpm --filter @iusentra/studio typecheck
python tools\sync_packaging_files.py --check
git diff --check
```

Esito tecnico: i comandi sopra sono passati nella copia locale.

## Topbar Recenti e ricerche 2.253.25

Decisione operativa: non aggiungere una quarta icona simile nella topbar. L'icona esistente `Recenti` diventa `Recenti e ricerche`, con badge unico e pannello diviso in:

- `Elementi aperti`: fascicoli, clienti e documenti tracciati dalle route profonde;
- `Ricerche recenti`: query realmente usate dalla ricerca globale della topbar.

Flusso dati:

- inserimento: selezione di un risultato nella ricerca globale React della topbar;
- API: `POST /api/recent/search` per la query e `POST /api/recent` per l'elemento aperto;
- proprietario: utente autenticato nello studio corrente;
- storage: sessione utente, come per gli elementi recenti già esistenti, senza creare JSON runtime aggiuntivi;
- UI: `TopBarRecentItems` mostra badge `totalCount = elementi aperti + ricerche recenti`;
- route di apertura: ogni ricerca punta a `/global-search?q=...`;
- guardrail: `tests/test_topbar_operational_api.py` verifica API, deduplica e conteggio; `tests/test_data_flow_contract.py` verifica il contratto topbar.

Comandi eseguiti:

```powershell
python -m py_compile web\services\topbar_recent.py web\blueprints\topbar.py pct\data_flow_contract.py
python -m pytest tests\test_topbar_operational_api.py tests\test_data_flow_contract.py::test_topbar_operativa_resta_collegata_a_dati_reali_e_testi_professionali -q
pnpm --filter @iusentra/studio typecheck
pnpm --filter @iusentra/studio build
python -m pytest tests\test_react_asset_retention.py -q --tb=short
docker compose build --no-cache app scheduler-worker ocr-worker
docker compose up -d --force-recreate app scheduler-worker ocr-worker
```

Esito tecnico: guardrail verdi, build Vite riuscita, retention asset React verde, Docker locale reale healthy e `/api/pronto` su `2.253.25`.

Verifica reale su macchina locale:

- browser: Google Chrome installato `C:/Program Files/Google/Chrome/Application/chrome.exe`, visibile;
- URL: `http://127.0.0.1:8080`;
- flusso: login reale, `/studio`, ricerca topbar `RG`, click sul risultato `RG 2026/003 Moscato Marco - Appello civile`, apertura `/fascicoli/8804C177`, ritorno a `/studio`, click su `Recenti e ricerche`;
- payload: `/api/recent` ha restituito `items=1`, `searches=1`, `totalCount=2`;
- UI osservata: badge topbar `2`, pannello con `ELEMENTI APERTI` e fascicolo `Moscato Marco - Appello civile`, sezione `RICERCHE RECENTI` con query `RG` e `18 risultati`;
- console: nessun errore applicativo rilevante;
- screenshot: `C:\Users\antmm\AppData\Local\Temp\iusentra-topbar-recenti-ricerche.png`.

## Verifica reale Studio e topbar 2.253.24

Eseguita su macchina reale locale dell'utente, con Google Chrome installato e visibile, URL `http://127.0.0.1:8080`, Docker ricostruito no-cache e `/api/pronto` alla versione `2.253.24`.

Route Studio aperte e scrollate:

- `/studio`;
- `/fatturazione`;
- `/preventivi`;
- `/compensi-forensi`;
- `/documenti`;
- `/redazione-atti`;
- `/statistiche`;
- `/ricerca-legale`;
- `/legal-skills`;
- `/workflow-agents`;
- `/giurisprudenza`;
- `/strumenti-legali`;
- `/strumenti-operativi`.

Esito osservato:

- tutte le route hanno `#root` React presente;
- nessuna route Studio è finita su `?_legacy=1`;
- la sidebar Studio mostra tutte le 13 sottovoci operative;
- `Legal Skills` e `Regia Agentica` aprono superfici React reali con dati/azioni, non fallback;
- `/studio` mostra dati reali del tenant: fascicoli, clienti, operatori, backup e presidi economici;
- i pannelli topbar `Voce Studio`, `Timer attività`, data italiana, `Scadenze rapide`, `Ultimi elementi aperti`, `Notifiche operative` e `Nuovo` reagiscono nel browser reale;
- `Assistenza remota` crea realmente una sessione protetta e la sessione di test è stata chiusa tramite API come `Chiusa`;
- corretto e verificato microcopy topbar con accenti italiani: `Timer attività`, `Avvia attività`, `Tipo attività`, `Nuova attività`.

Nota di controllo: il token `null` intercettato su `/fatturazione` era un falso positivo dentro la parola `Annullata`; non c'è un valore `null` visibile come testo tecnico.

## Stato non dichiarabile come chiuso per tutto l'applicativo

Verificato su macchina reale: perimetro Studio e topbar, come sezione sopra.

Ancora non dichiarabile come chiuso al 100% per tutto l'applicativo: non è stata completata nello stesso giro la prova materiale di tutte le altre macro-aree e sottomenu (`Agenda`, `Fascicoli`, `Comunicazioni`, `Scadenze`, `Servizi Telematici`, `Impostazioni`, `Amministrazione`, ecc.). I test automatici attestano il contratto dati e route, ma non sostituiscono l'accettazione visiva completa richiesta dall'utente.
