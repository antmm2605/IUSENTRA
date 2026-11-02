# Mappa area FASCICOLI (FAS) — verifica visiva 02/11/2026, produzione 2.476.0

Giri automatici con scritture bloccate (script `app/fas_elenco.js`, `app/fas_dettaglio.js`), PC 1440×900 e telefono 390×844.
Schermate e testi: `scratchpad/app/audit/FAS/` (+ giri PC della sessione principale in `app/audit/<id>/pc`).

## /fascicoli (elenco) — PC e telefono
| elemento | funzioni provate | esito |
|---|---|---|
| Testata | Esporta, Archivio, Nuovo fascicolo | OK |
| 11 indicatori | Attivi, In corso, Da archiviare, Economico, Registrato, Parcelle, Scadenze urgenti (apre lo Scadenziario in finestra), Doppioni, RG da acquisire, Documenti, Comunicazioni — ognuno cliccato | FAS-02 (Parcelle) |
| Riquadro scadenze urgenti | 4 voci + «Visualizza tutte» | FAS-26 |
| Filtri Tipo (11 voci), Stato (7), Ordine (12) | ogni opzione selezionata, righe e prime righe registrate | FAS-23 (Prossima scadenza) |
| Filtri avanzati | schede Pratica / Procedimento / Persone; primo e secondo ordinamento; Contributo, Liquidazione, Parcella (tutte le voci) | OK |
| Viste | Operativa / Economica | FAS-01 (Economica 38–43 s, 502) |
| Modalità | Tabella / Compatta / Schede; Colonne (pannello); Righe; Per pagina | OK su PC; telefono FAS-30 |
| Raggruppa | Gruppo, Stato, Tipo, Ufficio, Anno RG, Responsabile, Nessuno | OK |
| Paginazione | pagina 2 | OK |
| Righe | Apri, Modifica, Deposito*, Notifica*, PDF, Elimina* (*fuori perimetro / scrittura) | colonna scadenza FAS-23 |
| Apertura | 9–13 s fino a rete inattiva (dati in ~3 s) | osservazione |

## /fascicoli/esporta
Formato PDF/CSV, Ricerca, Tipo, Stato, Scarica export, Campi inclusi, Preset rapidi, Fascicoli recenti — FAS-03, FAS-04, FAS-05.

## /fascicoli/archivio
Indicatori Archiviati / ZIP / Esiti (cliccati), ricerca, Azzera filtri, Aggiorna, tabella (Apri, PDF, Elimina*) — OK (28 archiviati; nessuno ZIP disponibile).

## /fascicoli/nuovo (solo apertura)
48 campi del modulo, pratiche collegate (Area / Gruppo / Registro), cliente, controparte, ufficio per Comune — FAS-14 (gruppi).

## Dettaglio fascicolo — 9DC39668, 09E615E6, 06928604, D960FA3E (civile/lavoro), 87E6AAA6 (TAR), 82A8E2BD (GdP), 1D4A95F2 (senza documenti), 9B9DF2A1 (definito), 474D4C13 (aperto, tipo Altro)
PC: tutti; telefono: 9DC39668, 87E6AAA6 (+ 82A8E2BD in coda). Ogni scheda cliccata dalla barra sezioni, pannelli interni aperti.
| scheda / funzione | esito |
|---|---|
| Testata (Fascicoli, Strumenti, PEC, Normativa, Cliente, Soggetti, Modifica, Presidio, Copertina, PDF, PagoPA) | OK; Prossimi impegni FAS-17 |
| Presidio del fascicolo | FAS-07, FAS-08, FAS-09, FAS-20; profilo con alternative incoerenti = difetto noto n. 12; «Rinvio udienza 07/10» = noto n. 11 |
| Conformità e qualità / nav «Controlli» | FAS-10, FAS-11 |
| Lettura del fascicolo e passaggi | «interrotta dopo tre tentativi» = noto n. 3; FAS-27 |
| Anagrafica (profilo, fonte telematica) | FAS-10, FAS-21, FAS-31 |
| Editor e redazione | OK (apertura) |
| Documenti e catalogazione, indice Lex | FAS-06, FAS-18, FAS-19 |
| Comunicazioni e notifica (visualizzazione) | FAS-16, FAS-22; doppioni notifica = noto n. 4 |
| Cronologia | FAS-15 |
| Udienze / scadenze | FAS-17, FAS-25; «termine lungo priorità Bassa» = noto n. 9 |
| Mediazione | OK; FAS-29 (CSS) |
| CTU | OK |
| Audit | FAS-24 |
| Soggetti | parti lette = noto n. 5 |
| Servizi telematici | OK |
| Normativa del fascicolo (finestra) | OK; art. 325 nel rito lavoro = noto n. 6 |
| Cliente / Soggetti (finestre) | OK |
| PagoPA (finestra, nessun invio) | OK |
| /modifica | FAS-13, FAS-14 |
| /copertina | FAS-12 |
| /pdf | OK (200, application/pdf, tutti i 9 fascicoli) |

Errori JS: nessuno. API fallite: solo la vista economica (502). Overflow orizzontale di pagina: 0 ovunque.

---

# Registro difetti — area FASCICOLI (FAS) — verifica visiva 02/11/2026 (produzione 2.476.0)

Schermate: `scratchpad/app/audit/FAS/` (elenco_pc/, <id>_pc/, <id>_tel/). Scritture bloccate in tutti i giri.
Fuori perimetro: deposito, notifiche (flusso), ricerca fascicoli. Difetti già noti (elenco_difetti.md) non ripetuti.

| id | pagina / funzione | formato | descrizione | schermata | gravità | causa nel codice | stato |
|---|---|---|---|---|---|---|---|
| FAS-01 | /fascicoli vista «Economica» | PC/tel | La vista economica impiega 38–43 s per pagina (25 righe), anche ripetuta; nel browser la richiesta finisce in **502** e l'elenco resta «Sincronizzazione fascicoli…». La vista operativa risponde in ~3 s. | elenco_pc/24_vista_Economica.png | alta | `web/services/react_fascicoli_bridge.py` `enrich_economic_list_items` → `payment_summary_for_fascicolo(automatic=True)` rilegge i documenti di ogni fascicolo a ogni richiesta (nessuna cache), più `gf.tutti()` completo | corretto (agente PER: la vista legge solo il consolidato del presidio economico pianificato e i fatti SQL; niente idratazione documenti, Document AI, impronta documentale né automazioni nella richiesta; la prossima data certa resta quella già collaudata nell'archivio delle letture, letta via SQL solo per le righe con documenti) |
| FAS-02 | /fascicoli indicatore «Parcelle» | PC | La card dice «151 fascicoli — **0 da emettere**, 159 bozze», ma il clic filtra «Parcella: da emettere» e le righe mostrano «PARCELLA DA EMETTERE»: il numero 0 conta i documenti-parcella registrati, non i fascicoli con parcella da emettere. Messaggio contraddittorio. | elenco_pc_ind/07_ind_5.png | media | `FascicoliPage.tsx` StatCard «Parcelle» (nota con `invoicesToIssue`) | corretto |
| FAS-03 | /fascicoli/esporta | PC | Sottotitolo «Archivio **repository_reali**» (chiave tecnica). Note delle card sbagliate: «Totali 336 — in archivio» (sono tutti i fascicoli), «Documenti 11659 — conteggio fascicoli». Campo «**Sync** e fonte portale» in inglese. | elenco_pc/41_esporta.png | media | `FascicoliPage.tsx` ExportPage; `react_fascicoli_bridge.py` campi export | corretto |
| FAS-04 | /fascicoli/esporta «Campi inclusi» | PC | Le caselle dei campi si possono spuntare ma non cambiano nulla, e la pagina promette contributo unificato, spese, liquidazione, parcella, totale registrato che il CSV/PDF **non contiene** (il CSV ha 12 colonne anagrafiche). | elenco_pc/41_esporta.png | media | `web/bootstrap/export_routes.py` `/fascicoli/export.csv`; `react_fascicoli_bridge.py` `fields` | corretto (campi = colonne reali, caselle in sola lettura, nuovo preset «CSV economico» → /export/fascicoli.csv che ha davvero le voci economiche) |
| FAS-05 | /fascicoli/esporta filtro «Stato: Da archiviare» | PC | Lo stato derivato «da_archiviare» viene passato come `stato=DA_ARCHIVIARE`: `StatoFascicolo("DA_ARCHIVIARE")` solleva ValueError → CSV **500**, PDF rimanda all'elenco con errore tecnico. | — (analisi codice) | alta | `web/bootstrap/export_routes.py:86-130` | corretto |
| FAS-06 | dettaglio — Documenti e atti | PC/tel | Badge della provenienza documento con chiavi tecniche: «CARICAMENTO_STUDIO» (e altre: APERTURA_FASCICOLO_VELOCE, PEC_CANCELLERIA, NOTIFICA_LEGALE, CTU_LIQUIDAZIONE…). | 9DC39668_tel/15_documenti.png | media | `react_fascicoli_bridge.py` `_source_label_for_document` (ripiego `_text(source)`) | corretto |
| FAS-07 | dettaglio — Presidio del fascicolo | PC/tel | «PERCORSO **WF LAVORO RETRIBUZIONE**»: codice del flusso tecnico mostrato all'avvocato. | 9DC39668_pc/11_presidio-fascicolo.png | bassa | `FascicoliPage.tsx` `regiaWorkflowLabel` | corretto |
| FAS-08 | dettaglio — Presidio, cerchio di completamento | PC/tel | Il testo «3 verifiche superate su 3 · 3 al deposito» esce dal cerchio (nessuno stile per `small`). | v_pc_presidio.png, v_tel_presidio.png | media | `FascicoliPage.css` `.iu-fas-regia__progress` | corretto |
| FAS-09 | dettaglio — Presidio, riquadro «Validazione» | PC/tel | Il paragrafo è senza stile: corpo 16–17 px, più grande di tutto il resto del presidio. | v_pc_presidio.png | bassa | `FascicoliPage.css` (manca `.iu-fas-regia__grid article p`) | corretto |
| FAS-10 | dettaglio — Conformità e qualità / Anagrafica | PC/tel | Voci «Controlli conformita» (senza accento), «Sync portale: **IMPORTATO**» (inglese + enum), in Anagrafica «Fonte portale **IMPORT_PRATICHE**», «Ultimo **sync**», «Stato portale all'acquisizione IMPORTATO», «1 parti». | 9DC39668_pc/22_conformita.txt, 13_profilo.txt | media | `react_fascicoli_bridge.py` `_quality` (riga ~9315), `_profile` (~7709), riepilogo fonte | corretto |
| FAS-11 | dettaglio — nav «Controlli» | PC/tel | Con profilo procedurale da confermare (es. 1D4A95F2) il pannello «Conformità e qualità» non viene disegnato: il collegamento «Controlli 5» della barra sezioni non porta da nessuna parte. Lo stesso accade su tutti i fascicoli quando il Presidio è chiuso: l'ancora #conformita vive dentro il Presidio, disegnato solo da aperto (giri 09E615E6, 9B9DF2A1, D960FA3E, 474D4C13, 87E6AAA6: «SEZIONE ASSENTE #conformita»). | 1D4A95F2_pc/giro.log («SEZIONE ASSENTE #conformita») | media | `FascicoliPage.tsx` `RegiaOperativaSection` ramo `profilo_da_confermare`; `openHashSection`/`lazySectionForDetailHash` | corretto (pannello anche col profilo da confermare; «Controlli» apre il Presidio, attende l'ancora e scorre al riquadro) |
| FAS-12 | /fascicoli/<id>/copertina | PC/tel | «Titolare pratica –» anche se l'avvocato referente è lo studio (in Anagrafica «Avv. Giuseppe Montagnese»); «Stato della pratica IN CORSO» (enum maiuscolo); «Autorita» senza accento; «Registro lavoro» (è il tipo, minuscolo); «**Prossima udienza 07/10/2026**» con data già passata. | 9DC39668_pc/40_copertina.png | media | `web/templates/fascicoli/copertina.html`, `web/bootstrap/fascicoli_management_routes.py` `copertina_fascicolo` | corretto |
| FAS-13 | /fascicoli/<id>/modifica | PC | Apertura lenta: 17–19 s prima che la pagina sia completa (PC e telefono). | 9DC39668_pc/giro.log | media | API `/api/v1/ui/fascicoli/<id>/modifica` 4,2 s e 450 KB (414 KB di uffici giudiziari + 49 KB clienti) e catalogo PST nel bundle | corretto (agente PER: il form riceve solo l'ufficio già scelto; gli altri arrivano su ricerca da /api/v1/ui/uffici-giudiziari/opzioni mentre si scrive; valore inviato invariato = nome ufficio) |
| FAS-14 | /fascicoli/<id>/modifica e /fascicoli/nuovo — «Gruppo» | PC | Elenco gruppi con voci doppie («Cause in materia minorile (14)» e «(36)», «Diritto industriale - vecchio rito» ×2, «Fallimento e procedure concorsuali» ×2, «Opposizione - fase davanti al G.E.» ×2) e voci solo-codice («Gruppo 013», «Gruppo B00»…«Gruppo C16», «Materia/gruppo 108 - da verificare»). | 9DC39668_pc/40_modifica.txt | media | `frontend/src/components/CodiceOggettoPstSearch.tsx` `groupOptions` | corretto per i doppioni (distinti con area e, se serve, codice); aperto per «Gruppo B00…C16 / 013 / 108»: il catalogo ministeriale non ha la descrizione del gruppo, non si inventa |
| FAS-15 | dettaglio — Cronologia (Attività processuali) | PC/tel | Tipi ed esiti in «Title Case» da enum («Iscrizione A Ruolo», «Termine Scadenza», «Ctu», «Sentenza Emessa», «In Attesa», «Non Applicabile»); nelle rilevazioni compaiono identificativi tecnici («Scadenza/agenda collegate: B805D75C», «Operazione eventi-unici-5b77…», «Prove: fat_377d…»). | 9DC39668_pc/17_attivita.txt | bassa | `react_fascicoli_bridge.py` `_option`, `_activity_notes_for_user` | corretto |
| FAS-16 | dettaglio — Comunicazioni e notifica | PC/tel | Stati dei passaggi in Title Case («Da Completare», «In Attesa»); plurali con barra «1 relata/e», «16 documento/i». | 1D4A95F2_pc/16_comunicazioni-notifica.txt | bassa | `react_fascicoli_bridge.py` / `pct/notification_*` (flusso notifiche) | aperto (flusso notifiche fuori perimetro) |
| FAS-17 | dettaglio — Prossimi impegni (testata) | PC | Stessa udienza 13/01/2027 elencata due volte: «Udienza da portale — BASSA» (scadenza) e «Udienza da portale — UDIENZA» (appuntamento). | audit/9B9DF2A1/pc/01_testata.png | media | `frontend/src/components/fascicoli/agendaFascicoloVoci.ts` `vociAgendaFascicolo` (anche 06928604: termine perentorio 04/11/2026 ripetuto come appuntamento «SCADENZA») | corretto |
| FAS-18 | dettaglio — Documenti, «Documenti da verificare» | PC/tel | Errore di indicizzazione con motivo «Causa della precedente lettura non disponibile nel registro.» e pulsante «Riprova errori»: l'avvocato non sa cosa fare. | 9DC39668_tel/15_documenti.png | bassa | `pct/document_intelligence/*` (file di altra correzione) | corretto (RES): motivo per codice in `pct/document_intelligence/motivi_lettura.py` (azione possibile: «Riprova errori», ricaricare il file…), applicato in `indexer.py`, `index_outcomes.py`, `web/services/document_index_outcomes.py`; busta cifrata invariata; test `tests/test_lex_document_source_outcomes.py::test_motivo_errore_lettura_spiega_azione_all_avvocato` |
| FAS-19 | dettaglio — Documenti «R.G. n.d./n.d.» | PC/tel | Fascicolo senza RG: riquadro «Fascicolo d'ufficio» mostra «R.G. n.d./n.d.». | 1D4A95F2_pc/15_documenti.txt | bassa | `FascicoliPage.tsx` riquadro fascicolo d'ufficio | corretto |
| FAS-20 | dettaglio — Presidio con profilo da confermare | PC | Riga «Lavoro e previdenza · **PCT_LAVORO** · SICID» (codice canale). | 1D4A95F2_pc/11_presidio-fascicolo.txt | bassa | componente profilo procedurale (`ProceduralProfileConfirmation`) | corretto (RES): canale con nome del portale (`proceduralChannelLabel` in `FascicoliPage.tsx`, anche in «Canale» del presidio); prova «procedura» dei fatti senza percorso `docs/REGISTRO_LETTURE.md` (`pct/archivio_letture/collaudo.py`; fatti già registrati riletti con il nome in `pct/registro_letture/fatti_repository.py::_prova_leggibile`); test `tests/test_archivio_letture.py` |
| FAS-21 | dettaglio — Anagrafica, «Fonte telematica acquisita» | PC/tel | Date grezze ISO: «2026-06-18T12:30:13.067430», «Data iscrizione 2026-05-12», «Data udienza 2027-01-13» (9B9DF2A1). | 9B9DF2A1_pc/13_profilo.txt | media | `FascicoliPage.tsx` `SourceSnapshotPanel` | corretto (solo ISO convertite; gg/mm/aaaa mai rilette all'americana) |
| FAS-22 | dettaglio — Comunicazioni / Cancelleria, atti importati dal portale | PC/tel | Atti del fascicolo d'ufficio (decreto, biglietto di cancelleria, atti di controparte) marcati «Deposito da verificare — Apri il flusso PEC…» con pulsante «Controlla PEC»; «IDBUSTA __2026-05-27__» e «IDBUSTA COM:2026-06-03:…» (chiavi interne); «Depositato il 27/05/2026 00:00»; «registrato da scheduler - PEC_PCT». | 9B9DF2A1_pc/16_comunicazioni-notifica.txt | media | `FascicoliPage.tsx` `depositPhaseSummary`, `DepositReceiptActions`, `depositMetaLine`, `DepositStateSummary` | corretto |
| FAS-23 | /fascicoli colonna «Prossima scadenza» e ordinamento | PC/tel | Date passate presentate come prossime («Prossima scad. 02/02/2024», «20/04/2023», «10/12/2025»): senza termini aperti si mostrava l'ultima udienza già tenuta; i termini aperti già decorsi non erano distinti. | elenco_pc/15_sel_Ordine_scadenza.txt, v_tel_elenco.png | media | `react_fascicoli_bridge.py` `_next_deadline_date_value`; `FascicoliPage.tsx` celle della colonna | corretto (udienza passata esclusa; termine aperto decorso = «scaduta il …») |
| FAS-24 | dettaglio — Audit (registro operativo) | PC/tel | Messaggi con chiavi: «Slot DOCUMENTI_RETRIBUTIVI collegato…», «Profilo PROC_LAV_RETRIB_001 applicato», «Conferma … del profilo PROC_LAV_RETRIB_001». | 9DC39668_pc/21_audit.txt | bassa | `react_fascicoli_bridge.py` `_audit_trail` (messaggi da `pct/practice_engine/repository.py`) | corretto in visualizzazione (dati di audit invariati) |
| FAS-25 | dettaglio — Udienze/scadenze «date lette» (GdP 82A8E2BD) | PC | Date di pagamento lette come «Termine processuale letto dai documenti»: «Corrispondenza fattura n», «Contributo unificato», «Quietanza CBILL», «Diritti forfettizzati». | audit/82A8E2BD/pc/18_udienze.txt | media | estrazione date dell'archivio letture (`pct/archivio_letture/motore_documenti.py`, file in correzione da altro agente) | corretto (RES): regola «data di un pagamento (avviso, quietanza, bonifico o fattura), non termine processuale» in `pct/archivio_letture/ancoraggio.py::motivo_non_processuale` (prevalgono le parole del processo: udienza, ingiunge, assegna…); riconvalida automatica dei fatti già registrati con `esclusione_data_salvata` sul brano salvato (`fatti_repository.riconvalida_fatti`); verificato sui testi reali dei 4 documenti; test `tests/test_ancoraggio_pagamenti.py` |
| FAS-26 | /fascicoli riquadro «Scadenze aperte scadute e prossimi 7 giorni» | PC/tel | Titolo ripetuto «RG 792/2025 - Rinvio udienza - Rinvio di udienza». | elenco_pc/01_elenco.txt | bassa | `FascicoliPage.tsx` `titoloScadenzaSenzaRipetizioni` | corretto |
| FAS-27 | dettaglio — Lettura (TAR 87E6AAA6) | tel | Nella fonte normativa compare il percorso interno «docs/specs/ministero/fonti_ufficiali/2026-08-24/…pdf (SHA-256 …)». | 87E6AAA6_tel/12_lettura-fascicolo.txt | bassa | `pct/procedura_fasi/fonti*.py` (in correzione da altro agente) | corretto (RES): `verifica` mostrata senza percorso né impronta; la copia conservata passa nei campi non mostrati `copia_conservata`/`impronta_copia` (`pct/procedura_fasi/fonti.py`); test `tests/test_procedura_fasi.py::test_la_verifica_mostrata_non_contiene_percorsi_interni` |
| FAS-28 | /fascicoli elenco (tipo «Altro») | PC/tel | Fascicolo di prova «COLLAUDO TECNICO EDITOR PDF 20261021» (474D4C13) visibile tra le pratiche reali dello studio. | elenco_pc/20_sel_Ordine_stato.txt | bassa | dato di produzione | aperto (eliminazione = scrittura su dati reali: decide l'avvocato) |
| FAS-29 | scheda Mediazione — CSS | PC/tel | Segnalazione del coordinatore: `MediazioneRegistryResponsive.css` e `MediazioneOrganismoDetail.css` usano `--iu-od-*` senza importare il tema. A vista nessuna perdita oggi (il tema arriva da `LegalIntelligencePage.css` nello stesso pacchetto), ma la dipendenza era implicita. | 9DC39668_pc/19_mediazione.png | bassa | i due CSS | corretto (import esplicito del tema) |
| FAS-30 | /fascicoli su telefono | tel | Su telefono i comandi Operativa/Economica, Tabella/Compatta/Schede e «Raggruppa» non sono visibili (solo schede): la vista economica si raggiunge solo dall'indicatore «Economico». | v_tel_elenco.png, run_elenco_tel.log | bassa | `FascicoliPage.css` (barra viste nascosta in mobile) | corretto (RES): menu «Vista» su telefono (Operativa/Economica, Raggruppa, Per pagina; tabella/compatta/colonne non si applicano all'elenco a schede) in `FascicoliPage.tsx` + `FascicoliPage.css`; verificato iniettando CSS/DOM (audit/RES_fas30_menu.png, nessuno scorrimento orizzontale) |
| FAS-31 | dettaglio — Anagrafica di un fascicolo non importato | PC | Riga «Ultimo sync n.d.» anche senza alcun portale (474D4C13). | 474D4C13_pc/13_profilo.txt | bassa | `react_fascicoli_bridge.py` `_profile` | corretto |

## Nota su FAS-01 (vista economica lenta)
`enrich_economic_list_items` chiama per ogni riga `payment_summary_for_fascicolo(automatic=True)`, che legge i documenti
(idratazione degli allegati e ricerca delle sentenze economiche) e applica le automazioni; per 25 righe 38–43 s.
Una cache in memoria non basta (3 worker, prima apertura comunque lenta) e saltare le automazioni cambierebbe i dati:
serve precalcolare il riepilogo economico nello scheduler/archivio letture e leggerlo nell'elenco. Lasciato aperto.

**Aggiornamento (agente PER, 02/11/2026) — FAS-01 e FAS-13 corretti.**
- FAS-01: il precalcolo esiste già: il job pianificato «Presidio fascicoli ed economia»
  (`fascicoli_document_economic_presidio`, ogni 15 min) salva nel fascicolo il marcatore `_presidio_documentale` e i
  fatti economici nell'archivio delle letture; ogni cambio di documento marca il marcatore come superato.
  `enrich_economic_list_items` ora usa per ogni riga `payment_summary_for_fascicolo_fast` (marcatore + fatti SQL +
  parcelle). Rimossi dalla richiesta: idratazione degli allegati (`_idrata_documenti_se_serve`, eliminata),
  `_server_document_ai_documents_for_fascicolo` (costruiva il servizio Document AI per ogni riga),
  `_document_analysis_fingerprint`. La prossima data certa resta letta dall'archivio delle letture (SQL, fatti già
  collaudati), solo per le righe con documenti. Senza consolidamento la riga dice
  «Da controllare» invece di rileggere. Prima (produzione, GET reale): 38,8 s per 25 righe; vista operativa 0,8 s.
  Dopo (locale, 30 fascicoli × 30 documenti): 0,29 s (prima 0,96 s sugli stessi dati), chiamate Python 852k → 411k;
  40×40: < 3 s nel test di tempo.
- FAS-13: prima 450 KB di cui 414 KB per 1.375 uffici (API 2,9–4,2 s; pagina 8,7 s a rete inattiva, 17–19 s nel
  giro). Dopo: il payload porta solo l'ufficio indicato nel fascicolo (< 1 KB) e il collegamento di ricerca; il form
  cerca gli uffici mentre si scrive (≥ 2 lettere, attesa 250 ms, max 30 voci). Il valore inviato resta il nome
  dell'ufficio; codici, PEC e scheda dell'ufficio restano mostrati per l'ufficio scelto.
- Osservazione fuori registro: nella stessa pagina `/api/time-tracking/links?caseId=9dc39668` (barra del timer) ha
  impiegato 4 s e risposto vuoto: l'identificativo arriva in minuscolo e non trova il fascicolo (area barra in alto).

## Riepilogo
Difetti: 31 (alta 2, media 15, bassa 14). Corretti 24 (FAS-14 solo per i doppioni; FAS-01 e FAS-13 dall'agente PER), aperti 7 (FAS-16, 18, 20, 25, 27, 28, 30) più la parte «gruppi senza descrizione» di FAS-14.

## Test eseguiti
- `tests/test_fascicoli_verifica_visiva_fas.py` (nuovo, 8 test) — verdi.
- `tests/test_fascicoli*.py`, `test_fascicolo_detail_ux.py`, `test_fascicolo_agenda_e_normativa_editor.py`, `test_fascicolo_gestione_stato.py`, `test_responsabile_conformita.py`, `test_agenda_fascicolo_defaults.py`: 230 passati, 36 saltati.
- `tests/test_react_shell.py -k "fascicol or export or copertina"`: verdi dopo l'aggiornamento di 2 asserzioni (campi export, data sentenza dei fascicoli definiti). `test_react_fascicoli_api_suite_usa_repository_reali` passa da solo ma fallisce se eseguito insieme a `..._data_sentenza_senza_scadenza_aperta` (riga «Appello civile» con id di un altro test: stato condiviso fra test, non legato a queste modifiche).
- JS: `agenda_fascicolo.test.mjs` (+2 casi), `fascicoli_page_loading`, `fascicolo_document_list`: 29/29. `npm --prefix frontend run typecheck`: verde. Ruff (regole CI): verde.

- RES (02/11/2026) test instabile `test_react_fascicoli_api_suite_usa_repository_reali`: causa la cache dell'elenco fascicoli (`_FASCICOLI_LIST_PAYLOAD_CACHE`, a livello di modulo) con chiave «nome studio + utente + parametri»: due app di test con lo stesso studio si scambiavano l'elenco (riga «Appello civile» di `test_react_fascicoli_bridge_usa_repository_reali`). Corretto: la chiave comprende l'archivio dei fascicoli (`web/blueprints/api_v1_react.py::_fascicoli_list_cache_key`). Verde in sequenza bridge → data sentenza → api suite.
- RES: `test_react_fascicoli_lista_popola_economia_e_scadenza_da_documenti` (vista economica) fallisce anche con le modifiche RES neutralizzate: dipende da modifiche in corso di altri agenti sulla vista Economica (perimetro escluso), lasciato aperto.
