# Pipeline PEC audit-grade

Aggiornato: 21 maggio 2026.

## Scopo

La pipeline PEC affianca la casella PEC storica e crea un controllo automatico end-to-end su messaggi, allegati, firme, validazione e collegamento al fascicolo. Il controllo è professionale ma non bloccante: IUSENTRA conserva, segnala e prepara le azioni; la decisione resta all'avvocato.

## Comportamento atteso

Per ogni PEC acquisita il software:

- conserva il MIME originale immutabile come BLOB e ne calcola SHA-256;
- crea `parsed_json` versionato con SHA-256 per ogni versione;
- registra ogni evento in `pec_audit_log` append-only con hash-chain;
- deduplica su `Message-ID` e hash MIME;
- esegue worker asincroni `parse`, `classify`, `ocr`, `signcheck`, `validate`, `link`, `digest`;
- produce un `validation_report` strutturato, non bloccante, con anomalie, basi normative, domande operative e azioni suggerite;
- propone il collegamento al fascicolo con matching multi-seme su RG, parti, ufficio e parole chiave;
- genera digest giornaliero alle 08:00 Europe/Rome.

## Deposito telematico: cosa aspettarsi dopo l'invio

Quando l'avvocato effettua un deposito PCT, IUSENTRA non deve limitarsi a dire "PEC ricevuta". Deve presidiare la sequenza attesa e comunicare lo stato operativo:

| Ordine | PEC/esito atteso | Controllo operativo |
| --- | --- | --- |
| 1 | Accettazione PEC | verifica invio, data/ora, Message-ID e assenza di anomalie di spedizione |
| 2 | Avvenuta consegna PEC | verifica consegna al dominio giustizia, dati di certificazione e momento rilevante per i termini |
| 3 | Esito controlli deposito | legge esito dei controlli automatici su messaggio/busta, warning, errore fatale o atto non conforme |
| 4 | Accettazione o rifiuto deposito | distingue accettazione automatica/manuale, intervento cancelleria e rifiuto; solo qui il deposito può essere comunicato come accettato, dopo controllo del fascicolo |

Il `validation_report.deposit_lifecycle` espone fase riconosciuta, prossime PEC attese, controlli da eseguire e frase operativa per l'avvocato. Se manca l'esito finale, il sistema segnala `pct_deposit_followup_expected` e suggerisce follow-up; se emerge rifiuto o errore critico segnala `pct_deposit_critical_outcome`.

## Lettura semantica e contesti normativi

La funzione `detect_pec_legal_context()` riconosce i principali contesti PEC processuali oggi gestiti:

| Contesto | Indicatori | Comportamento software |
| --- | --- | --- |
| Comunicazione o notificazione di cancelleria PCT | cancelleria, biglietto di cancelleria, D.L. 179/2012, PST | segnala possibile decorrenza termini, verifica ricevute e atto comunicato |
| Deposito telematico civile | deposito telematico, busta, DatiAtto.xml, esito controlli automatici | richiede atto e ricevute, propone fascicolo e controlla esiti successivi |
| Notifica in proprio L. 53/1994 | formula di legge, art. 3-bis, relata, attestazione di conformità | verifica oggetto, atto, relata, ricevute e pubblico elenco |
| Giudice di Pace | Giudice di Pace, G.d.P., notifica, D.L. 179/2012 | segnala notifica giudiziaria, chiede atto, data consegna, RG e termini |
| UNEP | UNEP, ufficiale giudiziario, art. 149-bis c.p.c. | distingue richiesta di notifica e notifica ricevuta, controlla relazione e ricevute |
| PAT | PAT, SIGA, TAR, Consiglio di Stato, D.P.C.M. 40/2016 | verifica ricorso/deposito/comunicazione, messaggio completo e firma |
| PTT | PTT, S.I.Gi.T., Corte di giustizia tributaria, D.M. 163/2013 | verifica ricorso/deposito/comunicazione tributaria e termini fiscali/processuali |
| Penale SNT | SNT, Procura, art. 148/151 c.p.p. | verifica destinatario, ruolo, atto penale e canale SNT |
| PDP/portale penale | portale deposito atti penali, PDP | distingue conferma deposito, errore o richiesta del portale |
| Ricevuta PEC | accettazione, avvenuta consegna, mancata consegna, daticert/postacert | classifica prova PEC e la collega al messaggio originario |
| Domicilio digitale | REGINDE, INI-PEC, INAD, Registro PPAA, art. 16-ter/sexies | segnala fonte dell'indirizzo e coerenza destinatario |

Il parser serializza ogni campo con `value`, `confidence`, `motivation` e `features`. Per esempio una PEC con oggetto `GIUDICE DI PACE - Notificazione ai sensi del D.L. 179/2012` produce evento `notifica_giudice_pace`, warning non bloccante `legal_notice_review_required` e domande operative su atto notificato, data di consegna, RG/fascicolo e termini.

## Specializzazione agente Lex

Lex è informato tramite `pec_audit` in `lex/operational_knowledge/source_registry.py`, agente `pec_audit_controlli` e tool:

- `list_pec_audit_messages`
- `get_pec_audit_message`
- `get_pec_audit_for_email`

Quando interrogato su validità, firme, allegati mancanti, MIME, notifica, cancelleria, Giudice di Pace, PAT, PTT, SNT, PDP, termini o fascicolo, Lex deve:

- leggere la PEC e il controllo audit-grade se presenti;
- distinguere dato certo, dato estratto con confidenza, inferenza normativa e punto da verificare;
- indicare le domande operative prima di proporre azioni;
- proporre salvataggio fascicolo, richiesta allegato mancante o scadenza solo come azione da confermare;
- non inviare, depositare, rispondere o schedulare senza azione esplicita dell'avvocato.

## API

Gli endpoint REST sono sotto `/api/pec/*`:

- `GET /api/pec/messages`
- `GET /api/pec/messages/<message_id>`
- `GET /api/pec/messages/<message_id>/mime`
- `POST /api/pec/fetch`
- `POST /api/pec/workers/run`
- `GET /api/pec/digest`
- `POST /api/pec/digest/run`
- `POST /api/pec/messages/<message_id>/salva-fascicolo`
- `POST /api/pec/messages/<message_id>/richiedi-allegato-mancante`
- `POST /api/pec/messages/<message_id>/schedula-scadenza`
- `POST /api/pec/demo/ingest`

Le API accettano sessione autenticata o API key tenant-aware, non accettano tenant scelti dal client e non espongono credenziali IMAP, path filesystem o contenuto MIME nei JSON.

## Storage

Schema SQLite/PostgreSQL:

- `pct/sql/20260521_pec_audit_pipeline.sql`
- `pct/sql/20260521_pec_audit_pipeline_postgres.sql`

Tabelle principali: `pec_messages`, `pec_parsed_versions`, `pec_attachments`, `pec_validation_reports`, `pec_fascicolo_links`, `pec_jobs`, `pec_digest_runs`, `pec_retention_policies`, `pec_audit_log`.

Retention: policy predefinita `pec-default-10y`, legal hold attivo e azione `review`; la funzione `apply_retention_policy()` produce report e audit, senza cancellare automaticamente dati probatori.

## Fonti ufficiali consultate

- Portale Servizi Telematici, comunicazioni e notificazioni telematiche: https://servizipst.giustizia.it/PST/it/pst_1_7.wp
- Portale Servizi Telematici, deposito telematico di un atto: https://servizipst.giustizia.it/PST/it/pst_1_0.wp?contentId=SPR376&previousPage=pst_1_2
- Specifiche tecniche DGSIA ex art. 34 D.M. 44/2011: https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC382
- Ministero della Giustizia, SNT penale: https://www.giustizia.it/giustizia/it/mg_1_8_1.page?contentId=SDC1116402
- Normattiva, L. 53/1994: https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=094G0076
- Giustizia tributaria, D.M. MEF 163/2013: https://def.giustiziatributaria.gov.it/DocTribFrontend/executePrintArticolo.do?articolo=Articolo+1&codiceOrdinamento=200000100000000&id=%7B8091F315-84CE-435A-A767-319589259DDE%7D
- Normattiva, CAD D.Lgs. 82/2005: https://www.normattiva.it/eli/id/2005/05/16/005G0104
- AgID, D.P.R. 68/2005 PEC: https://www.agid.gov.it/sites/default/files/repository_files/leggi_decreti_direttive/dpr_11-feb-2005_n.68.pdf
- EUR-Lex, regolamento eIDAS 910/2014: https://eur-lex.europa.eu/legal-content/IT/TXT/?uri=CELEX:32014R0910

## Demo locale

Per caricare il dataset sintetico pubblico:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8080/api/pec/demo/ingest
Invoke-RestMethod -Method Get -Uri http://localhost:8080/api/pec/digest
```

Il dataset include cinque PEC: deposito completo, firma invalida, allegati mancanti, EML annidata e notifica Giudice di Pace/D.L. 179/2012 con mittente ambiguo.
