# Mappa — catena delle notifiche legali (03/11/2026)

EXTRACTED = letto nel codice; INFERRED = dedotto, da verificare.

## 1. Chi decide se la notifica è prevista

Due motori distinti, che non si parlano direttamente.

### 1a. Dagli atti del fascicolo — «Notifiche richieste dagli atti»
- `pct/obblighi_notifica.py:78` `REGOLE`: tabella regola → etichetta del catalogo documentale → norma.
  - lavoro_415 (art. 415 cc. 4,5,7; 417-bis c.p.c.), semplificato_281undecies (art. 281-undecies), decreto_ingiuntivo_644 (artt. 643, 644),
    citazione_163bis (art. 163-bis), opposizione_di_645 (artt. 641, 645), sfratto_660 (art. 660), precetto_480 (artt. 479-482),
    ricorso_tar_41 (artt. 41, 45 c.p.a.; art. 11 R.D. 1611/1933), ottemperanza_114 (artt. 114, 45 c.p.a.),
    appello_civile_325 (artt. 325, 327, 330 c.p.c.), appello_cds_92 (artt. 92, 94 c.p.a.),
    sentenza_notifica_breve (artt. 285, 325, 326 c.p.c.; facoltativa).
  - Solo se l'atto è dello studio (`solo_se_nostro`), altrimenti «da verificare» (`:367-372`). Termini con
    `pct.termini_processuali.ItalianDeadlineCalculator` (`:399-426`), mai inventati: se manca la data → `dati_mancanti`.
- `web/services/obblighi_notifica_runtime.py:77` `raccogli()`: documenti (catalogo), parti, date e prove dall'archivio delle letture
  (nessuna rilettura). `:156` `obblighi_fascicolo()` aggiunge le verifiche dell'avvocato (`verifiche_per_atto`).
- `pct/obblighi_notifica_atto.py:103` `una_voce_per_atto()`: copie riunite, prove dell'atto (art. 3-bis c. 3 e art. 9 L. 53/1994),
  fase superata (sentenza/udienza tenuta/fascicolo definito).
- NON coperti dalle regole: ordinanze e decreti del giudice diversi dal DI (es. ordinanza che ordina l'integrazione del
  contraddittorio, art. 102 c.p.c.; decreto ex art. 669-sexies) — questi passano solo dal presidio PEC (1b). Art. 133 c.p.c.
  (comunicazione vs notifica) NON è citato nel codice: la distinzione è resa dalla regola `communication_only` (1b).

### 1b. Dalla PEC dell'ufficio — «Presidi notifiche» (/notifiche-legali)
- `pct/data/legal_notification_detection_rules_v1.json` + `pct/legal_notification_rulepack.py:665` `detect_notification_candidates`,
  chiamato da `pct/pec_legal_event_understanding.py:1322`. Regole: `explicit_order` («ordina/dispone … notific», L. 53/1994 art. 3-bis,
  artt. 137-149 c.p.c.), `judgment_to_notify_review` / `sentenza_verbale_429_review` (valutazione strategica sentenza),
  `communication_only` e `comunicazione_xml_office_negative` (comunicazione di cancelleria ≠ notifica), ricevute RAC/RdAC/mancata consegna.
  Regime temporale: `legal_regimes` (art. 147 c.p.c.; art. 16-septies D.L. 179/2012 storico; Corte cost. 75/2019).
- Persistenza: tabella `pec_legal_notification_presidia` (`pct/pec_notification_presidio/repository*.py`).
- Euristica parallela per il pannello del fascicolo: `pct/notifiche_legali.py:2095` `office_notification_evidence_from_pec`
  (`_email_requests_notification` `:1944`: parole «notifica/relata/termine breve» + «sentenza/ordinanza/decreto…»).

## 2. A chi
- Obblighi: `pct/obblighi_notifica.py:275` `_destinatario` — Stato → Avvocatura distrettuale (art. 11 R.D. 1611/1933, art. 144; nel lavoro
  art. 415 c. 7); altre PA → sede/legale rappresentante (artt. 144 c. 2, 145); presso difensore costituito (artt. 170, 285, 330);
  altrimenti PEC da pubblici elenchi (art. 3-bis L. 53/1994; art. 16-ter D.L. 179/2012). Parti da `pct/archivio_letture/parti_fascicolo.parti_lette`
  o, in mancanza, `fascicolo.controparte`.
- Operazione di notifica: `web/services/react_notifiche_legali_bridge.py:876` `_recipient_from_subject` (soggetti del fascicolo),
  `:852` PEC nelle note dei documenti; registri `pct/notifiche_legali.py:64` `PUBLIC_PEC_REGISTERS` (ReGIndE, INI-PEC, Registro Imprese,
  Registro PP.AA., INAD, ANPR non valido) con capacità `:74`; la fonte è solo «suggerita» finché l'avvocato non registra la verifica
  (`build_public_register_confirmation_evidence` `:1080`; controllo `:1195-1215`). ReGIndE via servizio autenticato PST.

## 3. Chi prepara gli atti
- `pct/notifiche_legali.py`: `select_relata_template` `:3797`, `render_relata` `:5319`, `generate_relata_pdf_bytes` `:5669`,
  `build_attestazione_conformita_payload` (art. 196-undecies disp. att.), `build_notification_attachment_manifest` `:2813`,
  `build_notification_signature_plan` `:3129` (firma solo della relata, CAdES/PAdES), `build_notification_send_plan` `:3219`
  (oggetto «notificazione ai sensi della legge n. 53 del 1994», .eml), `validate_legal_notification` `:5026` (fail-closed).
- Atto dell'avvocato: firma (PIN del dispositivo), conferma dell'invio dal PC (invio PEC locale), scelta dei destinatari, verifica
  nel pubblico elenco. Il provvedimento scaricato non viene rifirmato.
- `pct/notifica.py`: legacy, ogni chiamata produttiva solleva `LegacyNotificaTelematicaDeprecata`.

## 4. Ricevute e chiusura
- `pct/notification_proof_matrix.py:226` `validate_notification_proof_bundle` (stati PROOF_ACQUIRED/DEPOSIT_REQUIRED/DEPOSITED con
  ricevute per destinatario, relata, hash, audit).
- Presidio PEC: `pct/pec_notification_presidio/receipt_policy.py`, `receipt_reconciliation.py`, `reconciler.py`.
- Obblighi: chiusura solo con prova verificata dell'atto e di tutti i destinatari (`pct/obblighi_notifica.py:332`), altrimenti motivo
  (`:342`: manca RdAC, relata non confermata, destinatari non nominati).
- Pannello «Comunicazioni e notifica»: `web/services/react_fascicoli_bridge.py:7883` `_notification_relata` (scala di stati da nome file
  + archivio: da_acquisire → prova_depositata).

## 5. Scrittura e non-ripetizione
- Job `legal_notification_relata_presidio` (`pct/scheduler.py:1652`, ogni 15 min) → `web/services/notifications_runtime.py:1502`;
  si ferma se l'impronta non cambia (`pct/impronta_notifiche_legali.py`). Scrive proiezioni in topbar/Web Push/scadenziario.
- Obblighi: calcolati a richiesta (API `web/blueprints/api_v1_react.py:9845`), non salvati; leggono solo l'archivio.
  Le scadenze entrano una volta sola con marcatore `OBBLIGO_NOTIFICA:` (`obblighi_notifica_runtime.py:207`), chiamato
  dalla lettura in sfondo (`web/services/archivio_letture_runtime.py:1023`).
- UI: fascicolo → Lettura → «Notifiche richieste dagli atti» (`frontend/src/components/fascicoli/ObblighiNotificaSection.tsx`),
  «Comunicazioni e notifica» (`FascicoliPage.tsx`, sezione #comunicazioni-notifica), /notifiche-legali (Presidi + Operazioni).

## 6. Errori
- Il job registra l'errore nel report (`errors`, log `[scheduler] Presidio relata/notifiche fascicoli fallito`) e prosegue al giro dopo;
  l'impronta non si salva se il giro fallisce (giro di troppo, mai notifica persa).
- `_allinea_obblighi_notifica` cattura l'eccezione e la scrive nel report di lettura (`archivio_letture_runtime.py:879`), il resto della catena prosegue.
- API: errore → `{"ok": false, "errore": "Obblighi di notifica non disponibili."}`; presidi → 503 con messaggio italiano.
- L'invio è fail-closed (`validate_legal_notification`): codici `RELATA_FIRMATA_REQUIRED`, `PEC_DESTINATARIO_FONTE_REQUIRED`…; li risolve l'avvocato.

## Pagine verificate a vista (sola lettura, nessuna scrittura bloccata necessaria)
| Pagina | PC | Telefono | Esito |
|---|---|---|---|
| /notifiche-legali → Presidi (10 code) | sì | sì | apertura 34 s; code OK; 502 su «Da esaminare» (NOT-06) |
| /notifiche-legali → Operazioni di notifica | sì | sì | chiavi tecniche registri (NOT-02, corretto) |
| 9DC39668 Notifiche richieste + Comunicazioni | sì | – | coerenti (notificato / prova depositata) |
| 09131014 | sì | sì | contraddizione (NOT-01, corretto); nomi troncati (NOT-05) |
| 795C50AC | sì | sì | «Notificato» falso (NOT-03, corretto); prova raccolta falsa (NOT-07) |
| B9EEA6CE, EFBE9117 | sì (API) | – | sentenza notificata ancora «Facoltativa» (NOT-04, corretto se l'archivio ha la relata) |
| FE336495 | API | – | doppia voce sentenza, una del 2020 (NOT-08) |
Schermate: scratchpad/app/audit/NOTIFICHE/{pc,tel,pcf,telf}/

---

# Registro difetti — NOTIFICHE (03/11/2026)

| Id | Pagina/funzione | Formato | Descrizione | Gravità | Causa | Stato |
|---|---|---|---|---|---|---|
| NOT-01 | Fascicolo 09131014 «Notifiche richieste» vs «Comunicazioni e notifica» | PC/tel | Ricorso lavoro + decreto «Da notificare» mentre il pannello accanto dice «Prova notifica depositata» (relata separata, RAC, RdAC, deposito prova presenti). Schermate pcf/09131014_obblighi.png, pcf/09131014_comunicazioni.png | alta | `pct/obblighi_notifica_atto.py` usava le prove «non collegate» solo a fase superata; `web/services/obblighi_notifica_runtime.py:69` scartava la relata catalogata senza letture (`_prove` richiede relata/consegna) | corretto: relata separata → «Da verificare» con la relata citata, mai «Notificato» (test `test_relata_separata_nel_fascicolo_non_lascia_il_ricorso_da_notificare`, `test_relata_catalogata_senza_letture_resta_una_relata_non_verificata`) |
| NOT-02 | /notifiche-legali → Operazioni di notifica, riga «Controparte personalmente: …» | PC/tel | Chiavi tecniche `inad, ini_pec, registro_imprese, registro_ppaa, altro_pubblico_elenco` in UI | bassa | `frontend/src/components/NotificheLegaliPage.tsx:4804` `allowedRegisters.join` | corretto: etichette da `registriPec` (typecheck ok; bundle da ricompilare dalla sessione principale) |
| NOT-03 | Fascicolo 795C50AC «Notifiche richieste» | PC/tel | Ricorso lavoro con decreto di fissazione presente risulta «Notificato» citando come prova le ricevute di una diffida stragiudiziale (PEC «Carta del docente») e «Nel fascicolo c'è la sentenza»: la sentenza è un precedente del 2020 in un fascicolo RG 2026. Rischio: notifica omessa. pcf/795C50AC_obblighi.png | alta | `web/services/obblighi_notifica_runtime.py` contesto `sentenze` contava ogni «Sentenza» del catalogo → `fase_superata` | corretto: sentenza datata prima dell'anno di iscrizione a ruolo esclusa dalla fase (test `test_sentenza_anteriore_all_anno_del_ruolo_non_supera_la_fase`). Resta da verificare a vista dopo il deploy (se l'archivio legge un'udienza già tenuta, la fase resta superata) |
| NOT-04 | Fascicoli B9EEA6CE, EFBE9117 «Notifiche richieste» | API | Sentenza con copia «originale notificato» e relata: voce «Facoltativa: decisione del difensore» | media | `pct/obblighi_notifica_atto.py` saltava ogni controllo delle prove per le regole facoltative | corretto: con prova nella copia della sentenza → «Da verificare» (chi ha notificato, data, termine breve artt. 325/326). Efficace solo se l'archivio ha letto la relata in quella copia (INFERRED) |
| NOT-05 | Destinatari in «Notifiche richieste» (09131014, 795C50AC) | PC | Nomi di istituti troncati («Istituto Superiore “A presso la sede…») | media | estrazione parti (`pct/archivio_letture/estrazione_parti.py`), probabile taglio su «“A. Nome”» (INFERRED) — area Lettura | aperto: fuori dalla catena notifiche, da correggere nell'estrazione parti |
| NOT-06 | /notifiche-legali → Presidi | PC/tel | Apertura 34 s; API `/presidi` 28-91 s; un 502 su «Da esaminare» → «Caricamento non riuscito». pc/10_Da_esaminare.png | alta | `web/services/notification_presidia_payloads.py:345` per ogni riga `_practice_payload` (carica il fascicolo) e `termine_per_presidio` (scadenziario per fascicolo) (INFERRED, non profilato sul server) | aperto: serve profilazione sul server prima di cambiare |
| NOT-07 | Fascicolo 795C50AC «Comunicazioni e notifica» | PC | «Prova notifica raccolta: notifica già inviata» basata su RAC/RdAC di una PEC stragiudiziale (oggetto non L. 53) | alta | `web/services/react_fascicoli_bridge.py:7946` usa i tipi rac/rdac dell'archivio senza controllare l'oggetto L. 53 (art. 3-bis c. 4) | aperto: correzione possibile (richiedere contesto L. 53 per rac/rdac letti dall'archivio) ma rischia di scartare ricevute vere con nome generico; serve verifica sui dati reali |
| NOT-08 | Fascicolo FE336495 «Notifiche richieste» | API | Due voci «Notificare sentenza» facoltative; una è un precedente (nome «Sentenza_Tribunale_Vicenza_20-04-2023», data letta 2020-04-08) | media | catalogo documentale: precedente catalogato «Sentenza» e data letta incoerente col nome | aperto: area catalogo/pertinenza documentale |
| NOT-09 | Destinatari istituti scolastici statali | PC | Gli istituti scolastici sono indicati «presso la sede, legale rappresentante (art. 144 c. 2, 145)» insieme al MIM presso l'Avvocatura | da decidere | `pct/obblighi_notifica.py:46` `_PA` riconosce «istituto» come PA non statale; nel progetto non c'è una fonte registrata sulle istituzioni scolastiche | aperto: scelta normativa dell'avvocato (nessuna fonte certa nel progetto) |
| NOT-10 | /notifiche-legali → Presidi | API | Stesso documento PEC con due presidi aperti (explicit_order + judgment_to_notify_review) per B9EEA6CE e FE336495; filtro canale con «Non PEC» due volte | bassa | regole del rulepack non terminali; `CHANNEL_LABELS` con `non_pec` e `nonpec` | filtro canale corretto (`repository_queries.py` alias non_pec/nonpec, opzione unica in `notification_presidia_payloads.py`; test `test_filtro_canale_non_pec_comprende_i_due_alias`); i due presìdi per lo stesso documento restano aperti: sono due regole diverse, da decidere |
| NOT-11 | Presidi B9EEA6CE, EFBE9117 | API | Presidio PEC «Rilevato / Esamina» sulla sentenza mentre nel fascicolo c'è la sentenza «originale notificato» e lo stato è «da archiviare» | media | riconciliazione presidio PEC con le prove del fascicolo (`pct/pec_notification_presidio/reconciler.py`) non chiude il caso sentenza | aperto: richiede decisione (chi ha notificato) |


Aggiornamento 03/11: script `deploy/hetzner/profila_notifiche.py` e workflow `.github/workflows/profila-notifiche.yml` pubblicati sul ramo claude/stoic-goldberg-q1m88y (commit 841feb5); avvio rifiutato da GitHub (404: un workflow nuovo si avvia a mano solo se esiste sul ramo predefinito). NOT-06, NOT-07, NOT-11 restano aperti in attesa delle misure.
