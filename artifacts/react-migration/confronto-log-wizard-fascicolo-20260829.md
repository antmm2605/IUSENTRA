# Confronto tecnico PST — Wizard e Fascicolo d’ufficio

**Data:** 29/08/2026 · fuso Europe/Rome
**Scopo:** confrontare il lotto PST del Wizard e quello del pannello Fascicolo d’ufficio sul medesimo fascicolo, senza deduzioni dalla sola UI.

## Contratto comune da verificare

| Voce | Wizard | Fascicolo d’ufficio |
| --- | --- | --- |
| Endpoint | `POST /pst/ricerca-snapshot` | `POST /pst/ricerca-snapshot` |
| Consultazione | `search_only=false`, `include_full_snapshot=true` | `search_only=false`, `include_full_snapshot=true` |
| Interazione | un solo lotto locale autenticato | un solo lotto locale autenticato |
| Codice UI Vicenza | `0640011` | `0640011` |
| Codice PST di protocollo | `0241160092` | `0241160092` |
| Servizio PST | `JPW_SICID` | `JPW_SICID` |
| Tabella civile | `SICID_CONTENZIOSO_CIVILE` | `SICID_CONTENZIOSO_CIVILE` |
| Certificato/PIN | una finestra nativa per operazione | una finestra nativa per operazione |

`0241160092` è la conversione di protocollo del codice operativo `0640011`; non è un secondo ufficio né una sostituzione del valore mostrato nella UI.

## Evidenza registrata prima del riallineamento

| Esecuzione | Avvio | Fine | Parametri comuni rilevati | Esito PST |
| --- | --- | --- | --- | --- |
| Fascicolo d’ufficio | 21:55:20 | 21:58:22 | `0640011 → 0241160092`, `JPW_SICID` | HTTP 502 nelle richieste 4 e 6; SOAP Fault `IDATTO` nella richiesta 7 |
| Wizard | 22:02:56 | 22:05:18 | `0640011 → 0241160092`, `JPW_SICID` | HTTP 502 nella richiesta 5; SOAP Fault `IDATTO` nella richiesta 7 |

Questi dati non sono ancora prova di parità: i fallimenti sono avvenuti in fasi diverse e la risposta ministeriale non ha restituito un catalogo completo.

## Divergenza eliminata dal pannello

La richiesta iniziale del pannello includeva identificativi storici (`id_fascicolo`, `sub_procedimento`, `id_dfa`, `id_ruolo_jpw`) non presenti nel lotto iniziale del Wizard positivo. Sono stati rimossi dalla richiesta iniziale del pannello. Il Wizard è stato ripristinato byte per byte dalla copia positiva; il Local Signer non è stato modificato in questa verifica.

## Protocollo della prova comparativa

1. Ricaricare la pagina locale una volta.
2. Avviare il Wizard con ufficio, R.G., anno e ruolo identici al caso del pannello.
3. Inserire il PIN soltanto nella finestra nativa eventualmente richiesta.
4. Registrare dal log: payload normalizzato, numero delle fasi, durata, risposta, catalogo e numero documenti.
5. Ripetere nel Fascicolo d’ufficio con lo stesso caso e confrontare riga per riga.

L’accettazione richiede catalogo completo visibile, stessa richiesta normalizzata e una sola richiesta PIN per ogni operazione avviata. Fino a tale prova su `localhost:8080`, il riallineamento non è verificato su macchina reale.

## Esecuzione Wizard — 29/08/2026 22:16–22:17

| Campo | Valore rilevato |
| --- | --- |
| Caso eseguito | Tribunale di Venezia, R.G. 1084/2026, ruolo AVV |
| Codice UI | `0620010` |
| Codice PST di protocollo | `0270420098` |
| Servizio e tabella | `JPW_SICID` |
| Durata osservata | 41 secondi |
| Esito | SOAP Fault `IDATTO` nella richiesta 7; il PST non ha restituito un fascicolo |

L’esito “Nessun fascicolo trovato con questi filtri” visualizzato nel Wizard è coerente con questa risposta. Non è però confrontabile con il Fascicolo d’ufficio di Vicenza (`0640011`), perché ufficio e codice PST sono diversi. La prova comparativa resta da eseguire sullo stesso caso Vicenza.

## Esecuzione Wizard comparativa — 29/08/2026 22:19–22:20

| Campo | Valore rilevato |
| --- | --- |
| Caso eseguito | Tribunale di Vicenza, R.G. 1084/2026, ruolo AVV |
| Codice UI | `0640011` |
| Codice PST di protocollo | `0241160092` |
| Servizio e tabella | `JPW_SICID` |
| Avvio e durata | 22:19:28; 51 secondi |
| Esito | SOAP Fault `IDATTO` nella richiesta 7; nessun catalogo e nessun documento restituiti |
| UI osservata | “Nessun fascicolo trovato con questi filtri.” |

Il contratto iniziale del Wizard è corretto per il caso Vicenza. L’esito non consente ancora il confronto funzionale con il pannello: anche il pannello dovrà essere eseguito con gli stessi dati e il suo log dovrà essere registrato prima di qualunque modifica ulteriore.

## Causa verificata e ripristino dal backup

Il confronto riga per riga ha isolato una regressione nel wrapper comune `fascicolo-snapshot-job`:

| Voce | Backup positivo | Runtime precedente al ripristino |
| --- | --- | --- |
| Gestore chiamato dal job | `_pst_fascicolo_snapshot` | `_pst_ricerca_snapshot` |
| Catalogo completato con InfoFascicolo, pagine e allegati | sì | non garantito |
| Coerenza con il test positivo dei 30 documenti | sì | no |

Il nucleo `_pst_ricerca_snapshot` e il recupero `_pst_carica_infofascicolo_web` erano già identici al backup. La divergenza era nei due wrapper asincroni del job, non nel componente Wizard.

Sono stati ripristinati dal backup positivo, senza modificare `TelematicoSurfacePage.tsx`, i soli metodi `_pst_run_fascicolo_snapshot_job` e `_pst_start_fascicolo_snapshot_job` in sorgente, copia `tools/dist` e Local Signer installato. Le impronte dei due metodi coincidono ora tra backup, sorgente, distribuzione e runtime:

- `a1f808aef78ed08d25eaa35aee7c25dd34cc0320951ac4d9c1cbc5ba9940feb9`
- `dc404b6aed3d5606aa4594b37e77b9e981372e4831ef421157aa109f9a6f06a1`

Il Local Signer `1.6.124` è stato riavviato in background alle 22:37:19; il ping leggero è riuscito ed è presente una sola istanza `python.exe`. Nessuna richiesta PST è stata avviata durante il ripristino.

Sintassi delle tre copie e i due guardrail mirati sul lotto unico/resolver sono passati. Il controllo completo di allineamento della distribuzione non è ancora superato, perché `tools/dist/local_signer.py` differisce più ampiamente dal sorgente; non sono stati generati pacchetti, eseguiti deploy o dichiarata la distribuzione valida.

La prossima prova reale deve essere eseguita sul Wizard con Vicenza `0640011`, R.G. `1084/2026`, ruolo `AVV`, e poi sul Fascicolo d’ufficio con gli stessi dati. Solo i due nuovi log potranno confermare se il catalogo completo torna a essere restituito.

## Seconda deviazione rimossa dal gestore del lotto

Il controllo successivo ha rilevato che anche `_pst_fascicolo_snapshot` differiva dal backup positivo. Nel runtime precedente al ripristino erano state inserite la chiamata `_prepare_windows_foreground_for_pst(data)` e callback di avanzamento direttamente nel gestore PST. Tali istruzioni non erano presenti nel test positivo e si eseguivano prima della richiesta autenticata.

Il metodo è stato ripristinato integralmente dal backup in sorgente, copia `tools/dist` e Local Signer installato. La nuova impronta comune è:

- `cceba3dd9a4e695373d9e3ed52c852e3dcc0911bdc6253536a4faaecbbb1bc91`

Dopo il ripristino il Local Signer `1.6.124` è stato riavviato in background alle 22:48:20. Il ping leggero è riuscito ed è presente una sola istanza. Nessuna richiesta PST è stata generata dal ripristino.

Il prossimo test non usa più i wrapper o il gestore divergenti: per Wizard e Fascicolo d’ufficio la catena verificata contro il backup è ora `fascicolo-snapshot-job` → `_pst_fascicolo_snapshot` → `_pst_ricerca_snapshot` → `_pst_carica_infofascicolo_web`.

## Ripristino integrale della copia positiva — 29/08/2026 23:09

Su richiesta esplicita è stato eseguito un **copia-incolla dal backup positivo** `pst-wizard-office-documents-positive-20260827-020909`, senza introdurre altra logica PST.

Sono byte-identici al backup: registro uffici, dati ministeriali, `local_signer.py`, helper Windows, bridge HTTP, copia `tools/dist`, `web/app.py`, route fascicoli e i test di procedura registrati nel backup. Gli hash verificati coincidono per tutti gli otto file operativi principali, inclusi `tools/local_signer.py` (`BAD838…`), `tools/local_signer_windows_http.ps1` (`3555…`), `web/app.py` e `web/bootstrap/fascicoli_document_routes.py`.

La copia installata del Local Signer è stata riallineata dai file `installed-local-signer` del backup e riavviata senza avviare una richiesta PST: risponde su `127.0.0.1:27272`, versione riportata `1.6.116`, una sola istanza attiva, certificato CNS rilevato e nessuna sessione PIN/PST aperta.

Sono stati invece **preservati** e non sovrascritti i componenti React correnti richiesti dall’utente: `TelematicoSurfacePage.tsx`, `OfficeDocumentsPanel.tsx`, `FascicoliPage.tsx`, `FascicoliPage.css` e `localSignerForeground.ts`. Le aggiunte di avanzamento e messaggi utente restano quindi fuori dal rollback del motore PST.

La copia Docker reale `localhost:8080` è stata ricreata una sola volta per caricare il ripristino: unico container `iusentra-app`, healthy, creato alle 23:09, con `/api/pronto` positivo. Non sono stati rimossi volumi o dati, non è stato generato alcun pacchetto e non è stato eseguito deploy remoto.

La sintassi Python del perimetro ripristinato è valida. Resta obbligatoria una nuova prova reale visibile con il caso Vicenza prima di dichiarare il flusso nuovamente operativo: questo ripristino non ha avviato il PST e non costituisce ancora una prova funzionale positiva.

### Esito guardrail automatico dopo il ripristino

Il test `test_fascicolo_snapshot_job_delega_al_wizard_con_lotto_unico`, anch’esso copiato dal backup, non passa con il `local_signer.py` dello stesso backup: il test pretende `_pst_ricerca_snapshot`, mentre il codice positivo ripristinato delega a `_pst_fascicolo_snapshot`. Non è stata fatta alcuna modifica per mascherare l’incoerenza o far risultare verde il test, perché avrebbe alterato di nuovo la copia positiva. La verifica funzionale resta quindi esclusivamente la prova reale su `localhost:8080` con PIN dell’utente.

## Prova locale dopo l’allineamento al server — 30/08/2026 00:52

La copia Docker locale usa l’immagine esatta del server `sha256:45f77d81e4e75d5d534521fcfd7da6e954337bd24315d06d8a2a79cfb2832f16`; il container `iusentra-app` è `healthy` e l’endpoint locale di disponibilità risponde correttamente. L’immagine precedente è conservata nel tag `iusentra-app:local-before-server-align-20260830`; il mount `data` dello studio non è stato toccato.

Durante la prova reale del Wizard per Tribunale di Vicenza, R.G. 1084/2026, ruolo AVV, il Local Signer ha registrato una sola richiesta `POST /pst/ricerca-snapshot` con codice UI `0640011` risolto nel codice PST `0241160092`. Il profilo del fascicolo è Lavoro e la tabella effettiva `JPW_SIL_DISTR` è coerente: la baseline positiva documenta espressamente `LAV → JPW_SIL_DISTR` come stesso percorso delle consultazioni reali riuscite. `JPW_SICID` è il default generale dell’ufficio, non il servizio da imporre per un fascicolo Lavoro.

L’utente ha osservato il completamento operativo della consultazione e l’avvio del lotto unico di download documenti. Nessuna seconda richiesta PST o PIN è stata aperta da Codex durante il monitoraggio. Resta da acquisire nel log l’esito finale numerico del lotto quando la UI lo mostra.
