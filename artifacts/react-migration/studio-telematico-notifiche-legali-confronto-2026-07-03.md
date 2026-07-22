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

## Attestazione cumulativa sul modello dello studio - 13/07/2026

Il confronto è stato esteso alla generazione dell'attestazione di conformità per più copie. La regola operativa resta quella ricostruita per il flusso notifiche: l'avvocato sceglie i documenti, il software distingue l'origine, produce una sola attestazione cumulativa nella relata e non dichiara conformi originali informatici o file già firmati quando non ricorre il presupposto.

Il documento Word ora deriva direttamente dal modello consegnato dallo studio, con SHA-256 identico tra fonte e copia applicativa. La compilazione modifica soltanto `word/document.xml`, rimuove le evidenziazioni usate come marcatori e preserva byte per byte stili, numerazione, relazioni, geometria e restante pacchetto Word. Il report completo, comprensivo di campi, fonti, test e prova materiale locale, è in `artifacts/notifiche-legali/attestazione-conformita-unica-2026-07-13.md`.

La UI continua a non mostrare nomi del software confrontato o dettagli del decompilato. Nessuna PEC o notifica reale è stata inviata durante la prova.

## Consolidamento ReGIndE e firma locale - 16/07/2026

Il confronto operativo è stato approfondito sul tratto che precede la firma e l'invio:

- selezione della pratica e preselezione assistita di avvocato, parte rappresentata, destinatario e registro;
- verifica distinta di notificante e destinatario sul pubblico elenco effettivamente mostrato;
- ricerca ReGIndE per indirizzo PEC, gestione di più recapiti e ruoli e conservazione dell'evidenza;
- riallineamento del codice fiscale ammesso solo per il destinatario e solo quando la risposta autorevole corrisponde alla PEC interrogata;
- unico inserimento PIN nel comando di firma, con uso locale per verifica e firma e cancellazione immediata dalla pagina;
- relata firmata salvata nel fascicolo prima dell'approvazione finale;
- approvazione finale mantenuta come scelta esclusiva dell'avvocato;
- invio PEC reale escluso dai test e sempre affidato alla macchina locale.

La superficie React usa testi operativi neutri e non espone il nome, gli alias o i dettagli tecnici del software confrontato. I test coprono anche il divieto di correggere automaticamente l'identità del notificante e la necessità di interrogare il registro coerente con il destinatario selezionato.

Esiti tecnici: `314` test mirati superati, build React superata, asset sotto `500.000` byte, Local Signer `1.6.92` con token e certificato di firma rilevati, copia locale e produzione healthy. La conformità crittografica finale resta aperta fino alla prova materiale con click reale e apertura della relata firmata; questi esiti non costituiscono conferma preventiva dell'accettazione di una specifica notifica o di un deposito da parte dell'ufficio.

## Riesame completo delle relate e dei destinatari multipli - 22/07/2026

### Difetto riprodotto

Sul caso reale `RG 1428/2026` la UI mostrava un solo destinatario nei campi principali, mentre il payload React conteneva più destinatari e il piano backend dichiarava più PEC. La prova tecnica ha confermato un falso verde sostanziale: il piano conservava due destinatari, ma anteprima, relata, PDF, validazione dell'override, log e audit utilizzavano soltanto `context.destinatario`.

La causa era in `pct/notifiche_legali.py`: `_build_context()` ignorava `payload.destinatari[]`. Inoltre, la data/ora PEC mostrata era il timestamp più recente fra notificante e tutti i destinatari, non la verifica appartenente alla singola identità PEC.

### Modello reale dello studio

Il file `D:\marco non codex ad utilizzare\relata\modello da seguire realata.docx` è stato letto strutturalmente. Contiene la relazione ex art. 3-bis L. 53/1994 per `RG 1428/2026`, l'avvocato Giuseppe Montagnese, l'assistita Maria Romeo, due destinatari completi (Avvocatura Distrettuale dello Stato di Reggio Calabria con ReGIndE e Ministero dell'Istruzione e del Merito con IPA), ricorso, procura, attestazione, decreto di fissazione udienza e relata, con natura/origine differenziata, procedimento, firma e identificativo notifica.

L'ambiente non disponeva di LibreOffice: struttura e testo sono stati estratti senza modificare il DOCX, ma non viene dichiarata una verifica visuale del documento renderizzato.

### Fasi ricostruite dal decompilato

Il programma confrontato usa un generatore compositivo, non un testo immutabile:

1. selezione documento e controllo PDF (`FormMain.cs:12638-12698`, `32431-32490`);
2. origine come originale dell'avvocato, duplicato informatico, scansione analogica o copia dal fascicolo (`FormQualeAllegato.cs:147-189`, `714-756`; `AllegatoTipo.cs:3-30`);
3. controllo di ogni destinatario, codice fiscale, PEC, elenco e parte rappresentata (`FormSentMailBee.cs:15593-15613`, `19583-19795`);
4. composizione dinamica di documenti, attestazioni, procedimento e destinatari (`FormSentMailBee.cs:15587-15979`);
5. anteprima modificabile: ogni modifica ricrea il PDF, richiede nuova firma e sostituisce il precedente (`SchedaNotifica.cs:79-156`, `470`; `FormSentMailBee.cs:15931-15953`);
6. preparazione di oggetto, allegati, firma e invio (`FormSentMailBee.cs:15720-15787`, `7177-7355`);
7. salvataggio e riconciliazione di inviata, RAC, RdAC/MDC tramite identificativo e PEC (`FormSentMailBee.cs:6896-6955`, `8094-8281`);
8. UNEP a mani, posta, estero o telematica resta distinto (`FormTipoNotificaUNEP.cs:54-187`; `FormSentMailBee.cs:31075-31436`).

Il catalogo IUSENTRA contiene 40 record: 32 relate e 8 documenti/workflow. Le varianti base/origine, ruolo destinatario, caso processuale e controllo/prova devono alimentare un solo compilatore governato; non possono essere menu contraddittori che lasciano invariata l'anteprima.

### Riscontro sui fascicoli del tenant Montagnese

Audit in sola lettura sul database tenant di produzione:

- 352 documenti relata in 279 fascicoli;
- 290 firmati;
- 267 con metadati originali di notifica;
- 3 con un destinatario, 210 con due, 52 con tre e 2 con quattro destinatari;
- 61 copie depositate/restituite;
- 955 attestazioni in 272 fascicoli.

Il dato dimostra la prassi operativa dello studio, ma non è presentato come pronuncia giudiziale di conformità.

### Fonti ufficiali, distinte dalla prassi

- L. 53/1994, art. 3-bis: pubblici elenchi, oggetto prescritto, relata separata firmata e dati del procedimento. Fonte ufficiale: <https://def.giustiziatributaria.gov.it/DocTribFrontend/executePrintArticolo.do?articolo=Articolo+3+bis&codiceOrdinamento=0000000000000039999900002000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000&id=%7B88A389EC-3C9E-4B8F-8C9C-BE0C3DAB28D4%7D>.
- Specifiche DGSIA 2 agosto 2024, artt. 26-27: formati, RAC/RdAC per ogni destinatario e attestazioni riferite alle copie. Fonte: <https://ca-salerno.giustizia.it/cmsresources/cms/documents/Provvedimento_DGSIA_del_02.08.2024.pdf>.
- L. 53/1994, art. 9: deposito e prova. Fonte ufficiale: <https://def.giustiziatributaria.gov.it/DocTribFrontend/executePrintArticolo.do?articolo=Articolo+9&codiceOrdinamento=0000000000000090000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000&id=%7B88A389EC-3C9E-4B8F-8C9C-BE0C3DAB28D4%7D>.
- Artt. 196-octies e 196-undecies disp. att. c.p.c.: attestazione delle copie estratte dal fascicolo o allegate alle comunicazioni e inserimento nella relazione quando destinate alla notifica.

Indirizzo/sede e data/ora della consultazione dell'elenco sono mantenuti come identificazione e audit professionale, non descritti come requisiti universali del comma 5 senza fonte specifica. Il vecchio avviso Acrobat/P7M non viene copiato come obbligo normativo.

### Correzione unificata realizzata

- `context.destinatari[]` conserva identità stabile, nome, codice fiscale/P. IVA, ruolo, parte rappresentata, PEC, elenco, timestamp e digest della prova specifica; il singolare resta alias di compatibilità;
- ogni destinatario usa soltanto la propria verifica PEC;
- il token sicuro `{{ destinatari_righe }}` rende l'elenco completo; un modello personalizzato plurimo senza il token viene bloccato;
- ruolo, registro, campi del caso, compatibilità e prova PEC sono controllati per ogni destinatario;
- la bozza manuale non può eliminare un destinatario o i suoi dati obbligatori;
- log, audit e piano di invio sono plurali e ogni PEC pianificata possiede identità e `messageId` distinti;
- il caso processuale aggiunge le proprie clausole anche con modello base esplicito;
- React lega l'anteprima al payload completo, annulla risposte obsolete, ricalcola dopo 250 ms, mostra modello/caso applicati e invalida bozza/firma dopo variazioni;
- la UI mostra tutti i destinatari e il numero di PEC distinte.

### Guardrail eseguiti

- `python -m pytest tests/test_notifiche_legali.py -q -x` -> superato;
- 7/7 test specifici multi-destinatario -> superati;
- typecheck React e 13 controlli mirati dell'anteprima -> superati nella tranche frontend;
- `git diff --check` -> superato sul perimetro dei test.

La prova browser reale in produzione e locale, la generazione/apertura PDF e il blocco precedente all'invio restano obbligatori prima della chiusura. Nessuna PEC reale è stata inviata.
