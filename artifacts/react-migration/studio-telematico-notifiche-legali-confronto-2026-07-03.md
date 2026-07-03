# Confronto notifiche legali Studio Telematico / IUSENTRA - 03/07/2026

## Scopo

Analisi end-to-end campo per campo del flusso notifiche legali a mezzo PEC, confrontando la struttura osservata nel decompilato Studio Telematico con il flusso IUSENTRA React/API/SQL. Il confronto resta documentale e tecnico: nessun riferimento a Studio Telematico o ad alias tecnici deve essere mostrato nella UI utente.

## Fonti esaminate

- Decompilato locale Studio Telematico:
  - `SoggettoNotificato.cs`
  - `SoggettiNotificatiList.cs`
  - `Allegato.cs`
  - `AllegatoTipo.cs`
  - `FormQualeAllegato.cs`
  - `FormMain.cs`
  - `SchedaNotifica.cs`
  - `SchedaDocumento.cs`
  - `SchedaEmailRicevute.cs`
  - `BrowserForm.cs`
  - `FormTipoNotificaUNEP.cs`
  - `FormDepositaConSoftwareEsterno.cs`
  - `NotificaEsito.cs`
  - campi tabella `TAVOLA` collegati a data/tipo notifica, ricevuta raccomandata e identificativo notifica
- IUSENTRA:
  - `pct/notifiche_legali.py`
  - `pct/notification_proof_matrix.py`
  - `pct/sql/20260602_notification_proof_matrix.sql`
  - `pct/sql/20260602_notification_proof_matrix_postgres.sql`
  - `web/services/react_notifiche_legali_bridge.py`
  - `frontend/src/components/NotificheLegaliPage.tsx`
  - `tests/test_notifiche_legali.py`
  - `tests/test_procedure_lifecycle_repository.py`
- Fonti ufficiali ricontrollate:
  - Normattiva, L. 53/1994, art. 3-bis e art. 3-ter.
  - Ministero della giustizia, specifiche tecniche DGSIA 7 agosto 2024 ex art. 34 D.M. 44/2011.
  - Normattiva, D.M. Giustizia 3 aprile 2013 n. 48, ricevuta completa ex D.P.R. 68/2005.
  - Normattiva, D.L. 179/2012, pubblici elenchi e INI-PEC.
  - Ministero della giustizia/PST, XSD UNEP pubblicati il 06/11/2024 e messi in esercizio il 18/11/2024.
  - Normattiva, artt. 137-149 c.p.c. e art. 149 c.p.c. per notifiche tramite ufficiale giudiziario e servizio postale.

## Matrice campo per campo

| Studio Telematico | Significato operativo | IUSENTRA | Esito |
| --- | --- | --- | --- |
| `SoggettoNotificato.CodiceFiscale` | Identifica il soggetto notificato anche quando si collegano le ricevute. | `destinatario_cf`, `codice_fiscale_piva`, `notification_recipients.recipient_tax_code`. | Allineato; aggiunto blocco sulla prova deposito se manca il dato. |
| `SoggettoNotificato.IndirizzoPec` | PEC destinatario collegata alla notifica e alle ricevute. | `destinatario_pec`, `pec`, `notification_recipients.recipient_address`. | Allineato; aggiunto blocco sulla prova deposito se manca il dato. |
| `SoggettoNotificato.PubblicoElenco` / `NOMI.PubblicoElenco` | Pubblico elenco da cui è estratta la PEC. | `fonte_pec_destinatario`, `recipient_address_source`, `PUBLIC_PEC_REGISTERS`. | Allineato; aggiunti alias letterali Studio: `INIPEC-professionisti`, `RegistroImprese`, `RegInde`, `IPA`, `altro`. |
| `Allegato.Tipo = NotificaAccettazione` | Ricevuta di accettazione in originale `.eml`/`.msg`. | `notification_receipts.receipt_type=ACCETTAZIONE`, evidence role `RICEVUTA_ACCETTAZIONE`, controllo `.eml/.msg`. | Allineato. |
| `Allegato.Tipo = NotificaConsegna` | Ricevuta di avvenuta consegna in originale `.eml`/`.msg`. | `notification_receipts.receipt_type=AVVENUTA_CONSEGNA`, evidence role `RICEVUTA_AVVENUTA_CONSEGNA`, richiesta ricevuta completa. | Allineato. |
| Campi obbligatori ricevuta in `FormQualeAllegato` | Per accettazione/consegna Studio richiede codice fiscale, PEC e pubblico elenco. | `validate_deposit_notification_proof` ora richiede gli stessi dati per ogni destinatario collegato alle ricevute. | Gap corretto. |
| `Allegato.BreveDescrizioneContenutoDocumento` | Descrizione breve dell'atto notificato quando il flusso è notifica via PEC. | `documenti[].descrizione`, `descrizione_documento`, relazioni e manifest allegati. | Allineato. |
| `Allegato.FirmaAllegato` | Stato firma allegato/relata. | `relata_firmata`, `notification_relata.signature_status`, piano firma Local Signer. | Allineato; IUSENTRA è più restrittivo sulla relata separata firmata. |
| `Allegato.SoggettiNotificatiList` | Relazione atto/ricevute/destinatari. | `notification_recipients`, `notification_evidence_links`, `recipient_id` su ricevute e riferimenti deposito. | Allineato e più strutturato. |
| `Allegato.AllegatoConformeList` e origine documento | Origine e attestazione conformità. | `DOCUMENT_ORIGIN_LABELS`, `conformity_attestations`, attestazioni in relata. | Allineato. |
| `TESTI.LastNotificaID` | Chiave di correlazione tra atto, firma e ricevute. | `notification_cases.case_uid`, `notification_case_id`, `proof_bundle_id`, evidence links. | Allineato e più robusto. |
| Oggetto PEC L. 53/1994 | Oggetto vincolato della notifica. | `LEGAL_NOTIFICATION_SUBJECT` e blocco `L53_SUBJECT_REQUIRED`. | Allineato. |
| Area notifiche non perfezionate PST | Flusso area web per mancata consegna imputabile al destinatario. | `prepare_pst_failed_notification_workflow`. | Allineato come workflow manuale governato. |
| Tipi UNEP | Richieste UNEP, pagamenti, notifiche ed esecuzioni. | Catalogo deposito separato e tab React `UNEP` in `/notifiche-legali`. | Allineato come canale autonomo, senza dichiararlo prova PEC L. 53. |
| `FormTipoNotificaUNEP` | Scelta del tipo notifica UNEP: mani, posta, estero o telematica; data notifica precetto obbligatoria quando il campo è attivo. | `validate_unep_notification_request`, API `/api/v1/ui/notifiche-legali/unep`, tabella `notification_unep_requests`, campi tipo, ufficio, destinatario, recapito, precetto, spese, atto, richiesta/relata e ricevuta pagamento. | Gap corretto nel pannello React notifiche come flusso separato. |
| `TAVOLA.DataNotifica`, `TipoNotifica`, `DataRicevutaRaccomandata`, `NotificaID` | Tracciamento notifiche non PEC/raccomandata e relativo identificativo. | `validate_non_pec_notification_tracking`, API `/api/v1/ui/notifiche-legali/non-pec`, tabella `notification_non_pec_tracks`, campi data notifica, tipo, ricevuta raccomandata, identificativo, prova documentale e canale. | Gap corretto nel pannello React notifiche come tracciamento non PEC. |
| `NotificaEsito` | Esiti fatturazione elettronica/SdI. | Flussi SdI e PEC commerciale separati. | Non pertinente al pannello notifiche legali PEC. |

## Esito del controllo completo del perimetro

Il pannello PEC/notifiche legali L. 53 è stato controllato end-to-end sui campi che Studio Telematico usa per collegare notifica, destinatario, atto, relata, ricevuta di accettazione, ricevuta di consegna e prova deposito. Su questo perimetro i gap rilevati sono stati corretti in codice, SQL, React e test.

Il controllo esteso del decompilato ha trovato anche aree laterali:

- UNEP, governato da un flusso proprio con tipo notifica, eventuale data notifica precetto, spese e ricevute;
- tracciamento non PEC/raccomandata tramite campi `TAVOLA`;
- esiti SdI, che non sono notifiche legali PEC.

Queste aree non devono essere confuse con la prova PEC L. 53. Dopo la tranche aggiuntiva, IUSENTRA le espone nello stesso pannello React come flussi distinti: `UNEP` per richiesta/notifica tramite ufficio NEP e `Non PEC` per tracciamento raccomandata, ufficiale giudiziario, consegna a mani, estero o altro canale non PEC.

## Correzioni applicate

- `pct/notifiche_legali.py`
  - normalizzazione alias pubblici elenchi provenienti dal decompilato;
  - prova deposito bloccata se le ricevute non sono collegate a codice fiscale/partita IVA, PEC e pubblico elenco del destinatario;
  - validatore UNEP con tipo notifica, ufficio NEP, destinatario, recapito, eventuale precetto, spese, atto, richiesta/relata e ricevuta pagamento;
  - validatore non PEC con data notifica, tipo, identificativo, raccomandata, cronologico, consegna a mani, estero e prova documentale.
- `frontend/src/components/NotificheLegaliPage.tsx`
  - nella prova deposito vengono inviati anche codice fiscale/partita IVA, PEC ed elenco pubblico;
  - aggiunte card e tab `UNEP` e `Non PEC`, con precompilazione da pratica, documento e destinatario;
  - i pulsanti `Controlla richiesta UNEP` e `Controlla notifica non PEC` invocano API reali, non azioni finte;
  - la UI resta neutra: nessun riferimento a Studio Telematico e nessun alias tecnico visibile;
  - le etichette visibili usano formulazioni operative, non nomi del software confrontato.
- `web/blueprints/api_v1_react.py` e `web/services/react_notifiche_legali_bridge.py`
  - esposti tipi, passaggi guidati e endpoint reali per UNEP e non PEC.
- `pct/sql/20260602_notification_proof_matrix.sql`
  - aggiunte tabelle SQLite `notification_unep_requests` e `notification_non_pec_tracks`.
- `pct/sql/20260602_notification_proof_matrix_postgres.sql`
  - aggiunto guard PostgreSQL equivalente al presidio SQLite;
  - aggiunte tabelle PostgreSQL `notification_unep_requests` e `notification_non_pec_tracks`.
- `tests/test_notifiche_legali.py`
  - test alias pubblici elenchi Studio/IUSENTRA;
  - test blocco prova deposito senza metadati destinatario;
  - test validazione UNEP completa e bloccata;
  - test tracciamento non PEC/raccomandata completo e bloccato;
  - test API React catalogo, endpoint UNEP e endpoint non PEC;
  - test esistenti aggiornati con destinatario completo.
- `tests/test_procedure_lifecycle_repository.py`
  - test parità SQLite/PostgreSQL anche sulle nuove tabelle.

## Test eseguiti

- `python -m pytest tests\test_notifiche_legali.py tests\test_procedure_lifecycle_repository.py -q` -> passato.
- `npm --prefix frontend run typecheck` -> passato.
- `npm --prefix frontend run test:app-v2` -> passato.
- `python -m pytest tests\test_utf8_integrity.py -q` -> passato.
- `git diff --check` -> passato.

## Stato verifica reale

Verifica produzione autenticata eseguita su `https://app.iusentra.it/notifiche-legali` con browser reale visibile e utente amministratore. Il server Hetzner è stato verificato sul commit distribuito, container applicativo unico `iusentra-app` healthy, `/api/pronto` `ok=true`, versione `2.253.163`, fuso `Europe/Rome`.

Controllo visivo e funzionale eseguito:

- tab `Notifica ex L. 53/1994`: campi pratica, destinatari, documenti, modello relata, dati avvocato/destinatario, verifica PEC con data/ora italiana, bozza relata, firma relata, approvazione finale, `Controlla relata` e `Invia PEC` con blocchi espliciti;
- tab `Deposito prova notifica`: campi atto notificato, relata firmata, PEC inviata, ricevute, destinatario e ricevuta completa; `Controlla prova deposito` produce blocchi documentali e ricevute mancanti;
- tab `UNEP`: tipo notifica, ufficio NEP, destinatario, indirizzo/comune, precetto, spese, atto, richiesta/relata, ricevuta pagamento; `Controlla richiesta UNEP` produce verifiche normative con stati `bloccante` e `superato`;
- tab `Non PEC`: data notifica, identificativo, destinatario, atto, raccomandata, spedizione, ricezione/giacenza, prova documentale; `Controlla notifica non PEC` produce blocchi specifici senza trattare il canale come PEC L. 53;
- tab `Comunica al cliente`: modelli cliente separati, oggetto e corpo ordinari, nessuna relata generata; il primo controllo visuale ha mostrato che il risultato non veniva portato in vista come negli altri tab, quindi la versione `2.253.164` aggiunge lo scroll automatico al pannello esito per tutti i controlli;
- pulsanti superiori reali verificati: `PEC studio` apre `Componi PEC`, `Comunica al cliente` apre `Componi email ordinaria`, `Controlli deposito` apre `Controlli Atti`.

Controllo payload produzione eseguito dopo deploy: `/api/v1/ui/notifiche-legali` non contiene `QuickOrganizer`, `Studio Telematico`, `DatiAtto.xml` o `TAVOLA`; anche le risposte di validazione per `notifica`, `comunicazione-cliente`, `prova-deposito`, `unep`, `non-pec` e `area-web-pst` restituiscono blocchi controllati senza diciture tecniche vietate.

## Correzione payload UI - 2026-07-03, versione 2.253.163

Durante la prova autenticata su `https://app.iusentra.it/notifiche-legali` il pannello visibile non mostrava riferimenti tecnici, ma il payload JSON dell'API conteneva ancora diciture storiche non destinate alla UI. La correzione applicata in `web/services/react_notifiche_legali_bridge.py`, `web/blueprints/api_v1_react.py` e `frontend/src/components/NotificheLegaliPage.tsx` filtra ricorsivamente il payload del pannello, il payload documenti pratica e le risposte dei controlli operativi.

Guardrail eseguiti prima del deploy:

- `python -m pytest tests\test_notifiche_legali.py -q` -> passato;
- `npm --prefix frontend run typecheck` -> passato;
- `python -m pytest tests\test_regia_ui_react.py::test_ui_notifiche_relata_firma_solo_con_prova_tecnica -q` -> passato;
- `python -m pytest tests\test_react_shell.py::test_react_comunicazioni_email_messaggi_collegate_nav_e_shell -q` -> passato;
- `python -m pytest tests\test_react_shell.py::test_import_studio_telematico_react_pubblica_exe_e_barra_avanzamento -q` -> passato;
- `python -m pytest tests\test_react_shell.py::test_react_telematico_bridge_payload_minimo -q` -> passato;
- `python -m pytest tests\test_utf8_integrity.py -q` -> passato;
- `npm --prefix frontend run build` -> passato;
- `git diff --check` -> passato.

## Correzione feedback esito - 2026-07-03, versione 2.253.164

Durante la prova produzione il pulsante `Prepara comunicazione` del percorso cliente inviava la richiesta ma non portava automaticamente in vista il pannello di esito. La correzione applicata in `frontend/src/components/NotificheLegaliPage.tsx` usa ora un helper unico `scrollResultIntoView()` richiamato dopo ogni `setResult(response)`, così tutti i pulsanti di controllo mostrano feedback immediato nello stesso pannello laterale.

Guardrail aggiunti/eseguiti:

- `python -m pytest tests\test_notifiche_legali.py -q` -> passato;
- `npm --prefix frontend run typecheck` -> passato;
- `npm --prefix frontend run build` -> passato;
- `python scripts\react-migration\generate_api_contracts.py --check` -> passato;
- `python scripts\validate_openapi.py docs\openapi.yaml` -> passato.

Stato da completare: commit, push dei branch gemelli, deploy Hetzner della versione `2.253.164` e nuova prova produzione del tab cliente dopo deploy.
