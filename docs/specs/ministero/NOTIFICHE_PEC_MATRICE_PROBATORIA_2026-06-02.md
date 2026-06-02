# Matrice probatoria obbligatoria per PEC, notifiche e deposito prova

Data consultazione e salvataggio fonti: 2 giugno 2026.

Questo documento governa il controllo runtime introdotto in
`pct/notification_proof_matrix.py`. La regola base è fail-closed:
`proof_bundle_id` è solo un identificativo di contenitore e non prova nulla da
solo. La validazione deve attraversare il grafo probatorio:

`notification_events -> notification_cases -> notification_recipients -> notification_receipts`

e, per le prove documentali:

`notification_proof_bundles -> notification_evidence_links -> evidence_documents`

Ogni evidenza collegata deve appartenere allo stesso fascicolo e deve avere hash
SHA-256 valido. Se la prova è annidata in un bundle o in riferimenti hashati, il
software deve dereferenziare i link e verificare ruolo, hash, destinatario,
ricevuta e stato, non limitarsi alla stringa dell'ID.

## Fonti ufficiali salvate

| Fonte | Snapshot locale | Regola usata dal software |
| --- | --- | --- |
| PST, Specifiche tecniche ex art. 34 D.M. 44/2011, provvedimento DGSIA 7 agosto 2024, rettifiche 16 settembre 2024 e 30 ottobre 2024 | `docs/specs/ministero/fonti_ufficiali/2026-06-02/pst-specifiche-tecniche-dm44-2024.html`; PDF locali `Specifiche_Tecniche_DGSIA_DM44_2011_2024_08_07.pdf`, `Specifiche_Tecniche_DGSIA_DM44_2011_Rettifica_2024_09_16.pdf`, `Specifiche_Tecniche_DGSIA_DM44_2011_Rettifica_2024_10_30.pdf` | Notifiche avvocati, allegazione ricevute, DatiAtto.xml, attestazione di conformità e canali tecnici PST. |
| L. 53/1994 | `docs/specs/ministero/fonti_ufficiali/2026-06-02/normattiva-legge-53-1994.html` | Notifica a mezzo PEC/recapito certificato, pubblici elenchi, perfezionamento e deposito delle ricevute. |
| D.P.R. 68/2005 | `docs/specs/ministero/fonti_ufficiali/2026-06-02/normattiva-dpr-68-2005-pec.html` | Messaggio PEC, dati di certificazione, ricevuta di accettazione, ricevuta di avvenuta consegna e log. |
| D.M. 2 novembre 2005, regole tecniche PEC | `docs/specs/ministero/fonti_ufficiali/2026-06-02/gazzetta-dm-pec-2005.html` | Formazione, trasmissione e validazione anche temporale della PEC e delle ricevute. |
| CAD, art. 48 | `docs/specs/ministero/fonti_ufficiali/2026-06-02/normattiva-cad-art-48.html` | Comunicazioni con ricevuta di invio e ricevuta di consegna tramite PEC o soluzioni qualificate. |
| ReGIndE PST | `docs/specs/ministero/fonti_ufficiali/2026-06-02/pst-reginde.html` | Domicilio PEC dei soggetti abilitati esterni e fonte per soggetti censiti nel processo telematico. |
| INI-PEC | `docs/specs/ministero/fonti_ufficiali/2026-06-02/registroimprese-inipec.html`; `mimit-inipec-pec.html` | Domicili digitali PEC di imprese e professionisti. |
| INAD | `docs/specs/ministero/fonti_ufficiali/2026-06-02/agid-inad.html` | Domicilio digitale di persone fisiche, professionisti non ordinistici ed enti privati non iscritti in INI-PEC. |
| XSD UNEP | `docs/specs/ministero/XSD PLO118 FASE2 per SW House/schema/atti-unep.xsd`; `docs/specs/ministero/fonti_ufficiali/2026-06-02/pst-unep-xsd.html` | RichiestaParte, canale UNEP e tracciati tecnici per richieste notifiche/esecuzioni. |
| XSD allegati PCT | `docs/specs/ministero/parte/base_v20/tipi-allegati.xsd` e versioni precedenti | Riferimenti ad attestazione di conformità, ricevuta di accettazione e ricevuta di avvenuta consegna negli allegati. |

## Matrice delle fasi obbligatorie

| Fase | Dati minimi | Validazioni | Blocchi | Prove collegate | Stati ammessi |
| --- | --- | --- | --- | --- | --- |
| Caso notifica | `fascicolo_id`, `notification_event_id`, tipo notifica, atto, eventuale obbligo collegato | Il caso deve essere univoco, tenant-aware e coerente con l'evento notifica | Stato prova senza caso, atto o fascicolo coerente | Audit `notification_case_create/update`; atto notificato | `DRAFT`, `READY`, `SENT`, `DELIVERY_RECEIVED`, `PROOF_COMPLETE`, `ERROR`, `NEEDS_REVIEW` |
| Destinatario | Nome o denominazione, codice fiscale se disponibile, indirizzo PEC/domicilio digitale, fonte, tipo soggetto | Validazione destinatario-per-destinatario; fonte tra ReGIndE, INI-PEC, INAD o manuale con review tracciata | `READY` senza indirizzo/fonte; manuale senza review; fonte incompatibile con soggetto quando nota | `notification_recipients`, `notification_recipient_address_checks`, snapshot/hash della fonte se disponibile | `ADDRESS_PENDING`, `ADDRESS_VERIFIED`, `READY`, `SENT`, `ACCEPTANCE_RECEIVED`, `DELIVERY_RECEIVED`, `PROOF_COMPLETE`, `REMEDIATION_REQUIRED`, `NEEDS_REVIEW` |
| Atto notificato | Documento informatico, identificativo atto, hash, origine, eventuale conformità | Per notifiche avvocato l'atto originale informatico deve essere PDF/PDF-A da documento testuale quando applicabile; scansioni e copie richiedono attestazione se dovuta | Atto assente, hash mancante, origine non classificata o attestazione dovuta non presente | Evidence role `ATTO_NOTIFICATO`; eventuale `conformity_attestations` | `VERIFIED`, `NEEDS_REVIEW`, `ERROR` |
| Relata | Relata separata o relazione UNEP, documento firmato, atto e destinatario correlati | Firma digitale o firma elettronica qualificata quando richiesta; relazione collegata all'atto e al destinatario | Relata assente, firma mancante, documento non correlato, relazione UNEP non verificata | `notification_relata`, evidence role `RELATA`, audit | `VERIFIED`, `PARSED_UNVERIFIED`, `MISSING_SIGNATURE`, `MISSING_DOCUMENT`, `NEEDS_REVIEW`, `ERROR` |
| Messaggio PEC inviato | Message-ID, mittente, destinatari, oggetto, EML originale, hash corpo, allegati | Message-ID presente; EML originale conservato; hash SHA-256; destinatari coerenti con la matrice | PEC inviata non conservata, Message-ID mancante, hash non valido, destinatario incoerente | `notification_messages`, evidence role `PEC_INVIATA` | `PARSED`, `VERIFIED`, `NEEDS_REVIEW`, `ERROR` |
| Ricevuta di accettazione | EML originale, daticert XML se disponibile, receipt message id, original message id, destinatario, timestamp, hash | Ricevuta-per-ricevuta; `receipt_type=ACCETTAZIONE`, `verification_status=VERIFIED`, `correlation_status=CORRELATED`, hash valido | Manca la ricevuta per un destinatario; mismatch Message-ID; mismatch destinatario; hash non valido | `notification_receipts`, evidence role `RICEVUTA_ACCETTAZIONE` | `VERIFIED`, `PARSED_UNVERIFIED`, `MISMATCH_MESSAGE_ID`, `MISMATCH_RECIPIENT`, `WRONG_FASCICOLO`, `WRONG_NOTIFICATION`, `DUPLICATE`, `NEEDS_REVIEW`, `ERROR` |
| Ricevuta di avvenuta consegna | EML originale, daticert XML, postacert/originale allegato quando disponibile, receipt message id, destinatario, timestamp, hash | `receipt_type=AVVENUTA_CONSEGNA`, verifica e correlazione positive per lo stesso destinatario | Manca RdAC per anche un solo destinatario; ricevuta breve/sintetica non accettata come completa quando il deposito richiede completa; mismatch o duplicato | `notification_receipts`, evidence role `RICEVUTA_AVVENUTA_CONSEGNA` | stessi stati della ricevuta di accettazione |
| Anomalie e ricevute negative | Mancata accettazione, mancata consegna, errore, anomalia, avviso, causa se nota | Le ricevute negative sono prove di evento, non prova positiva di notifica; richiedono remediation | Passaggio a `PROOF_ACQUIRED` o `PROOF_DEPOSITED` se esiste ricevuta negativa verificata non rimediata | `notification_receipts`, `notification_delivery_attempts`, audit remediation | `REMEDIATION_REQUIRED`, `NEEDS_REVIEW`, `ERROR`, `CANCELLED` |
| Attestazione di conformità | Documento attestato, nome file, descrizione sintetica, documento attestazione, firma, destinazione | Se separata deve essere PDF e firmata; se destinata alla notifica gli elementi entrano nella relata quando previsto | Copia notificata senza attestazione dovuta; attestazione senza documento o nome file | `conformity_attestations`, evidence role collegato, audit | `VERIFIED`, `NEEDS_REVIEW`, `ERROR` |
| Bundle probatorio | `bundle_id`, tipo bundle, ruoli richiesti, link a evidenze, hash dei documenti | Tutti i ruoli richiesti presenti; ogni link `VERIFIED`; evidenza stesso fascicolo; hash SHA-256; destinatari e ricevute completi | `proof_bundle_id` assente, non presente in `notification_proof_bundles`, link non verificato, hash non valido, ruolo mancante | `notification_proof_bundles`, `notification_evidence_links`, `evidence_documents` | `DRAFT`, `PARTIAL`, `VERIFIED`, `NEEDS_REVIEW`, `ERROR` |
| Deposito prova | DatiAtto.xml, busta, ricevuta deposito, esito ufficio, riferimenti DatiAtto per ogni destinatario/ricevuta | `PROOF_DEPOSITED` richiede `OFFICE_ACCEPTED`; riferimenti DatiAtto verificati per RAC e RdAC di ogni destinatario | Deposito senza DatiAtto, senza busta, senza esito ufficio, senza riferimenti per ricevuta | `notification_proof_deposits`, `notification_dati_atto_receipt_refs`, evidence roles deposito | `DRAFT`, `READY`, `SIGNED`, `PACKAGE_VALIDATED`, `SENT`, `PEC_ACCEPTED`, `PEC_DELIVERED`, `OFFICE_ACCEPTED`, `OFFICE_REJECTED`, `TECHNICAL_ERROR`, `NEEDS_REVIEW` |
| Audit | Prima/dopo, sorgente, attore, motivazione blocco, hash evento | Ogni mutazione critica produce audit; i dati sensibili sono sanificati prima dell'hash | Mutazione protetta senza sorgente validata o senza token repository | `procedure_audit_log` | `notification_create`, `notification_update`, `notification_update_blocked`, `notification_evidence_link`, `notification_proof_deposit_add` |

## Regole runtime inderogabili

- `PROOF_ACQUIRED` è ammesso solo con bundle tipo `NOTIFICA_AVVOCATO_PEC`,
  `NOTIFICA_UNEP` o equivalente verificato, con atto, relata, PEC inviata, RAC e
  RdAC per ogni destinatario.
- `PROOF_DEPOSIT_REQUIRED` conserva la stessa prova positiva della notifica e
  indica che serve il successivo deposito della prova.
- `PROOF_DEPOSITED` è ammesso solo con bundle tipo `DEPOSITO_PROVA_NOTIFICA`,
  DatiAtto.xml, busta deposito, ricevuta deposito e esito ufficio accettato.
- Ogni destinatario non cancellato deve avere RAC e RdAC verificate e correlate.
- Ogni ricevuta negativa verificata blocca la prova positiva finché non esiste
  remediation professionale tracciata e nuovo esito coerente.
- La ricevuta non può essere validata solo per contenuto testuale: deve restare
  collegata a EML/XML originale, Message-ID e hash.
- L'aggiornamento diretto SQL di `notification_events` è bloccato: il trigger
  accetta solo transizioni validate dal repository e bundle presenti in
  `notification_proof_bundles`.
- Le fonti ufficiali sono registrate in
  `docs/specs/ministero/fonti_ufficiali/registro_fonti_ufficiali_2026-06-02.json`.

## Limiti prudenziali

Il software non invia PEC reali, non esegue scraping massivo di pubblici elenchi
e non conserva credenziali, PIN, token o sessioni portale. Quando la fonte non
permette una regola certa, il flusso produce `NEEDS_REVIEW` o
`REMEDIATION_REQUIRED` e non inventa automatismi.
