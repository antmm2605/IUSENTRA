# Log prove live PST e PEC - 2 giugno 2026

Questo log registra le prove eseguite sulla copia locale e sul Local Signer in
modalità autorizzata. È sanificato: non contiene PIN, token, cookie, sessioni
complete o nominativi delle parti.

## Ambiente

| Voce | Valore |
| --- | --- |
| Repository | `D:\legale\IUSENTRA` |
| Local Signer usato nelle prove live | `tools/local_signer.py` versione `1.6.67` |
| Codice repository dopo allineamento fonti | `tools/local_signer.py` versione `1.6.68` |
| Porta prova | `http://127.0.0.1:27273` |
| Porta installazione stabile rilevata | `http://127.0.0.1:27272` |
| Certificato | Certificato di autenticazione CNS/Aruba selezionato da Windows Certificate Store |
| Regola sicurezza | Nessun PIN salvato; nessuna operazione dispositiva su richieste copie; nessun download documenti avviato nei test di sola mappatura |

## Prove live fascicoli

| Ora indicativa | Registro | Ufficio | Caso | Servizio / namespace | Esito | Evidenza |
| --- | --- | --- | --- | --- | --- | --- |
| sessione precedente | `SICID` / civile ordinario | Palmi `0910011`, PST `0800570094` | `274/2026/CC` | `JPW_SICID` / `urn:CONS-SICC-BE` | OK, 0 fascicoli | Tabella raggiunta; ricerca valida ma nessun fascicolo visibile con quei parametri. |
| sessione precedente | `SIL` / lavoro | Ufficio indicato nel test | `500/2026/LAV` | `JPW_SIL_DISTR`, poi `JPW_SIL` / `urn:CONS-SIL-BE-DISTR` | OK, 0 fascicoli | Tabella lavoro raggiunta; nessun fascicolo visibile con quei parametri. |
| sessione precedente | `SIVG` / volontaria giurisdizione | Ufficio inizialmente provato | `63/2025/VG` | `JPW_SIVG` / `urn:CONS-SIVG-BE` | OK, 0 fascicoli | Tabella raggiunta, ma l'ufficio non era quello corretto del caso indicato. |
| 10:30 circa | `SIVG` / volontaria giurisdizione | Roma `0760010`, PST `0580910098` | `63/2025/VG` | `JPW_SIVG` / `urn:CONS-SIVG-BE` | OK, 1 fascicolo | Fascicolo restituito; sezione valorizzata `PRIMA SEZIONE SEPARAZIONI VOLONTARIA FAMIGLIA`; giudice valorizzato. |
| sessione precedente | `MIN` / minorenni | Ufficio indicato nel test | anno `2026` | `JPW_MIN` / `urn:CONS-MIN-BE` | OK, 0 fascicoli | Tabella raggiunta; nessun fascicolo visibile con quei parametri. |
| sessione precedente | `SIMIN` / minorenni | Ufficio indicato nel test | anno `2026` | `JPW_SIMIN` / `urn:CONS-MIN-BE` | OK, 0 fascicoli | Tabella raggiunta; nessun fascicolo visibile con quei parametri. |
| sessione precedente | `SIECIC` | Ufficio indicato nel test | anno `2026` | `JPW_SIECIC` / `urn:CONS-SIECIC-BE` | Vincolo rispettato | SOAP Fault `Parameter not resolved 'idRuoloJPW'`; nessun ruolo inventato. |
| sessione precedente | `SIGP` / Giudice di Pace | Palmi `0910401`, PST `0800570152` | `2962/2023/GDP` | `JPW_SIGP` / `urn:CONS-SIGP-BE` | OK, 1 fascicolo | Numero ruolo valido restituito; registro portale `GDP`. |
| sessione precedente | Cassazione penale | Cassazione `GLCC`, PST `80417740588` | `12756/2026/CASSPE` | `JPW_CASSPE` / `urn:CONS-CASSPE`, `QP_Ricorsi` | OK, 1 fascicolo | `NRGREALE=202601275600`, ruolo `RICORSO ORDINARIO`, sezione `PRIMA SEZIONE`, iscrizione `2026-04-14`, udienza `2026-07-09`. |
| sessione precedente | Cassazione penale annuale | Cassazione `GLCC`, PST `80417740588` | anno `2026` | `JPW_CASSPE` / `urn:CONS-CASSPE`, `QP_Ricorsi` | OK, 1 fascicolo | Ricerca annuale con `DATAISCR_DA=01/01/2026` e `DATAISCR_AL=31/12/2026`; trovato `12756/2026`. |
| 10:35 circa | `SICID` / civile ordinario | Palmi `0910011`, PST `0800570094` | `1025/2024/CC` | `JPW_SICID` / `urn:CONS-SICC-BE` | OK, 1 fascicolo | Ruolo `ORDINARIO CARTABIA`, stato `PROCEDIMENTO DEFINITO`, iscrizione `2024-09-05`, udienza `2024-12-12`; 3 parti censite. |
| 10:36 circa | `SICID` snapshot | Palmi `0910011`, PST `0800570094` | `1025/2024/CC` | `JPW_SICID` / `urn:CONS-SICC-BE` | OK, 16 documenti catalogo | Snapshot metadati/catalogo riuscito; nessun download documenti avviato in questa prova. |

## Prove live richieste copie

| Ora indicativa | Operazione | Endpoint | Esito | Evidenza |
| --- | --- | --- | --- | --- |
| 10:45 circa | `getServiceNames` su candidate `/servizi/*` e `/pda/pycons/*` non confermate | Proxy `ext`/`pda`, varianti servizio richieste copie | Non usate come endpoint valido | Varianti non documentate: 404 o timeout; nessuna operazione dispositiva inviata. |
| 10:48 circa | `RicercaRichieste` read-only | `https://ext.processotelematico.giustizia.it/pda/pycons/GLRM/JPW_SICID` | OK | Risposta SOAP 200, namespace `urn:RichiestaCopie-consultazioni-distr`, `available=0`: servizio raggiunto, nessuna richiesta copie già presentata o visibile al certificato in quel momento; non è un fault della mappatura. |
| 10:48 circa | `RicercaRichieste` read-only | `https://ext.processotelematico.giustizia.it/pda/pycons/GLRM/JPW_SIECIC` | Non compatibile | SOAP Fault protocollo/deserializzazione; la prova positiva resta su `JPW_SICID`. |

Nota normativa: `Documentazione_servizi_web_v1.69.pdf`, capitolo 4, indica le
richieste copie come servizio ancora non rilasciato e censisce le interrogazioni
read-only `ProfiloRichiesta` e `RicercaRichieste`. Per questo IUSENTRA mantiene
solo mappatura e lettura, senza invio automatico di richieste o pagamenti.

## Prove PEC

| Caso | Esito | Evidenza |
| --- | --- | --- |
| Deposito ricorso per cassazione penale con `1365/2016 RG APP` e `1364/2011 RG NR` da `depositoattipenali.ca.reggiocalabria@giustiziacert.it` | OK | Classificato `cassazione_penale` / `deposito_ricorso_cassazione_penale`; estratti `1365/2016 RG_APP` e `1364/2011 RG_NR`. |
| Oggetto `generale/2016/001365/Corte di Appello ...` da `notifichepenali.ca.reggiocalabria@penale.ptel.giustiziacert.it` | OK | Classificato `deposito_penale_pdp` / `comunicazione_penale_pdp`; estratto `1365/2016 RG_APP`; nessuna scadenza automatica senza contenuto fonte. |
| `12756/2026/PENALE/AVVISO UDIENZA/CASS` | OK su router evento | Registro penale/Cassazione riconosciuto; la lettura fascicolo reale corrispondente è stata provata su `JPW_CASSPE`. |

## Fonti ufficiali web aggiunte alla prova

| Fonte | Esito |
| --- | --- |
| PST `Servizi` | Confermata distinzione area pubblica/riservata e presenza dei servizi `Uffici giudiziari`, consultazioni registri, Cassazione, RegIndE, PDP e richieste visibilità. |
| PST `Uffici giudiziari` civili e penali | Confermati avvisi su uso esclusivo delle PEC e su inefficacia dell'invio PEC penale quando è previsto il deposito tramite portale. |
| PAT Portale dell'Avvocato | Confermati PAdES per moduli/atti e PEC RegIndE; portale operativo `https://pe.prod.cloud.giustizia-amministrativa.it`. |
| MEF / SIGIT | Confermati PTT, deposito ricorsi/appelli, atti successivi, Telecontenzioso, pagamento CUT/pagoPA e area formati documento/firma digitale. |

## Test automatici collegati

| Comando | Esito |
| --- | --- |
| `.venv\Scripts\python.exe -m py_compile tools\local_signer.py pct\pec_legal_workflow.py` | OK |
| `.venv\Scripts\python.exe -m pytest -q tests\test_local_signer.py -k "cassazione or siecic or qbuilder or richieste_copie" --tb=short` | OK, 34/34 |
| `.venv\Scripts\python.exe -m pytest -q tests\test_local_signer.py -k "richieste_copie" --tb=short` | OK, 4/4 |
| `.venv\Scripts\python.exe -m pytest -q tests\test_portali_telematici_matrix.py tests\test_pec_legal_workflow.py --tb=short` | OK, 27/27 |
| `.venv\Scripts\python.exe -m pytest -q tests\test_utf8_integrity.py --tb=short` | OK, 4/4 |
| `.venv\Scripts\python.exe scripts\react-migration\generate_api_contracts.py --check` | OK |
| `.venv\Scripts\python.exe scripts\validate_openapi.py docs\openapi.yaml` | OK |
| `git diff --check` | OK con solo avviso CRLF su `docs/openapi.yaml` |

## Residui non chiusi da dati mancanti

| Area | Stato | Perché non è chiusa live |
| --- | --- | --- |
| Cassazione civile | Mappata e testata automaticamente | Serve un numero ruolo Cassazione civile realmente consultabile dal certificato per prova esatta `QC_Ricorsi`. |
| SIECIC con dettaglio fascicolo | Mappato e protetto | Serve `idRuoloJPW` reale/autorizzato dal portale; il sistema non lo inventa. |
| Richieste copie dispositive | Read-only raggiunto | Non risultavano richieste visibili al certificato; senza richiesta reale non si deve simulare un invio o pagamento. |
