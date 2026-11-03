# Collaudo dei motori di lettura — registro (03/11/2026)

Fotografia INVENTARIO (sola lettura) in produzione, commit server 9456e703d. Run GitHub Actions: 41614468036 (prima), 41614839599 (cause errori eventi), 41615432587 (diagnosi contesto). Log in scratchpad/collaudo/run1..3/log.txt. Studio_1 = studio principale (336 fascicoli, 11.962 documenti, 173 PEC collegate, 743 allegati PEC); studio_2 = 0 fascicoli.
Fascicolo di collaudo: 474D4C13 «COLLAUDO TECNICO EDITOR PDF 20261021», studio_1, senza cliente, 3 documenti, 0 documenti di prova → accettato.

| Motore | Inventario (studio_1) | Non rilegge | Incrementale | Errori | A vista | Esito |
|---|---|---|---|---|---|---|
| Sentenza e preparazione archivio (`sentenza_da_archiviare`) | 12.705 oggetti: 12.233 letti (tutti versione precedente), 471 da leggere, 256 fermi >24h, 1 errore; ultima lettura 08/10; 0 letture in 24h | da lanciare (GIRI) | da lanciare | da lanciare | da fare | DIFETTO D3: nessuno scrive più questo lettore |
| Sentenza e definizione (`proposta_definizione`) | 11.962: 7.072 letti, 4.669 da leggere (4.631 fermi >24h), 221 non leggibili; 7.293 letture in 24h | da lanciare | da lanciare | da lanciare | da fare | arretrato in recupero |
| Testo e ricerca (`ocr`) | 11.962: 183 letti, 11.776 da leggere, 3 errori; ultima 13/10; coda OCR: 572 completati, 3 falliti, 0 aperti >24h | da lanciare | da lanciare | da lanciare | da fare | DIFETTO D4: legge solo i caricamenti manuali |
| Indice documentale | 11.962: 857 letti, 11.087 da leggere, 18 errori (15 >24h); 75 in 24h | da lanciare | da lanciare | da lanciare | da fare | arretrato grande |
| Catalogo dal contenuto | 11.962: 4.821 letti, 7.141 da leggere; 559 in 24h | da lanciare | da lanciare | da lanciare | da fare | arretrato in recupero |
| Assistente locale (`rag_locale`) | 11.962: 2.454 letti, 1.001 non leggibili, 8.507 da leggere; 459 in 24h | da lanciare | da lanciare | da lanciare | da fare | arretrato |
| Presidio PEC (`presidio_pec`) | 743 allegati: 47 letti, 696 da leggere; ultima 16/09; presidio audit: 6.405/6.429 allegati con testo | — | — | — | da fare | DIFETTO D3 (scrittore mai chiamato) |
| Presidio economico | 319 fascicoli con documenti: 317 aggiornati, 2 mai letti | da lanciare | da lanciare | — | da fare | buono |
| Proforma automatica | 319: 104 aggiornati, 210 mai letti, 5 impronta superata; ultima 08/10 | da lanciare | da lanciare | — | da fare | DIFETTO D3 (scrive solo se crea proforma) |
| Motore documenti (archivio) | 11.962: 7.372 letti, 4.589 da leggere (4.551 fermi >24h), 1 non leggibile; 848 in 24h | da lanciare | da lanciare | da lanciare | da fare | arretrato, vedi D2 |
| Scadenze dai PDF | 11.962: 0 letti mai | — | — | — | da fare | DIFETTO D3 (legge solo all'anteprima Scadenziario) |
| Motore PEC (archivio) | 916 (PEC+allegati): 709 letti, 207 da leggere (185 non ancora censiti, 22 fermi >24h) | da lanciare | — | — | da fare | quasi completo |
| Recupero PEC→fascicolo | 173 PEC collegate, 173 completate, 0 salvati: tutte scartate «ricevuta_deposito_telematico» | da lanciare | — | — | da fare | DA VERIFICARE (atteso dalle correzioni del prossimo deploy) |
| Sincronizzazione caselle | casella studio_1: INBOX 989, presidio 1.931 messaggi, 0 INBOX mai esaminati; studio_2: INBOX 585, presidio 445, **258 INBOX mai esaminati** | da lanciare | — | — | da fare | DIFETTO D5 (studio_2) |
| Presidio PEC audit (lavori) | studio_1: ~89 lavori falliti per fase (classify 77, link 89, ocr 89, signcheck 89, validate 90); 0 in coda >24h | — | — | — | — | errori permanenti da esaminare |
| Presidio notifiche (numeri) | ultimo giro: scanned 308, items 66, to_notify 16, errori 0 | da lanciare | — | — | altro agente | ok |
| Coda eventi del registro | 196 pending, 140 idle, 2 running; 24h: 93 riusciti, 612 falliti, 497 scaduti (lease); 196 fascicoli senza riga di sintesi | — | — | — | — | DIFETTI D1, D2 |

## Difetti
- D1 — Eventi di fascicoli inesistenti ripetuti senza fine: 612 fallimenti in 24h «Fascicolo accodato non disponibile» su soli 2 fascicoli (studio_1) + 3 (studio_2, che ha 0 fascicoli ma 101 documenti ancora censiti). Diagnosi (run 41615432587): contesto del thread corretto (studio presente, SQLite, 336 fascicoli caricati), i fascicoli non esistono. Causa: `web/services/archivio_letture_runtime.py:1272` solleva errore → evento ritentato e ripreso da `riprendi_letture_ferme`. Correzione proposta: fascicolo inesistente = evento concluso con riuscito e oggetti del registro segnati non presenti. NON applicata: il file è in modifica da un altro agente.
- D2 — 497 eventi scaduti per lease in 24h («non ha concluso entro il tempo previsto»), giro riuscito più lungo 1.096 s: le letture lunghe superano la prenotazione.
- D3 — Lettori censiti in `pct/registro_letture/lettori.py` che nessuno scrive più (o scrive solo in casi particolari): `sentenza_da_archiviare` (`web/services/sentenza_archiviazione_runtime.py` mai importato), `presidio_pec` (`_sincronizza_presidio_pec`, `web/services/registro_letture_runtime.py:379`, mai chiamata), `scadenze_pdf` (solo dall'anteprima Scadenziario), `proforma_automatica` (`web/services/react_fascicoli_bridge.py:5037`, segna solo se crea la proforma). Falsano «da leggere» e la riga di sintesi (20.517 oggetti da leggere dichiarati). Decisione: togliere dal censimento o farli scrivere.
- D4 — `ocr` scritto solo da `pct/ocr_worker.py:75` per documenti accodati al caricamento manuale; i documenti importati (portale, PEC) non entrano mai in coda.
- D5 — studio_2: 258 messaggi INBOX mai esaminati dal presidio PEC.

## Correzioni (03/11/2026, pubblicate sul ramo di sessione, da verificare dopo il deploy)
- D1 — `web/services/archivio_letture_runtime.py`: fascicolo inesistente → eccezione dedicata `_FascicoloInesistente`; evento concluso come riuscito, oggetti segnati non presenti (`chiudi_oggetti_fascicolo_inesistente`). Test `tests/test_collaudo_correzioni.py::test_d1_*`.
- D2 — stesso file: nei passi finali del giro (discordanze, notifiche, esiti, Lettura, verifiche) la prenotazione si proroga prima di ognuno. I turni a budget (SECONDI_PER_TURNO 600 s < prenotazione 1.800 s) e le scadenze da riavvio non contate come tentativo erano già nel codice: i 497 «scaduti» portano il testo della versione precedente alla 2.477.0. Test `test_d2_*`.
- D3 — `pct/registro_letture/lettori.py`: tolti dal censimento `presidio_pec` (lo stesso lavoro lo fa motore_pec) e `sentenza_da_archiviare` (lo fa proposta_definizione); `scadenze_pdf` e `proforma_automatica` diventano `su_richiesta` e `repository.stato_fascicolo` non conta come arretrato ciò che non hanno mai toccato. Tolta la funzione morta `_sincronizza_presidio_pec`. Test `test_d3_*`.
- D4 — nuovo `web/services/ocr_da_archivio.py`, chiamato a ogni giro di `leggi_fascicolo`: OCR chiuso come «non necessario» dove il motore documenti ha già un testo; i documenti senza testo vanno nella coda OCR una sola volta. Test `test_d4_*`.
- D5 — `web/services/pec_pipeline_runtime.py`: con la casella nel database dello studio, l'impronta dell'archivio veniva dalla data di `casella.json`, che non cambia più. Così il presidio saltava «archivio invariato» o «archivio email assente». Ora l'impronta si prende dal catalogo SQL. Causa probabile, ricavata dal codice. Il prossimo INVENTARIO la conferma con `pec.acquisizione_cursore`. Test `test_d5_*`.

# Collaudo dopo il deploy 2.478.0 (03/11/2026, pomeriggio)

Run (workflow «Collaudo dei motori di lettura»): INVENTARIO 41638886653 (main) e 41647635328 / 41652997627 (ramo di sessione, con diagnosi); GIRI 41639119354; INCREMENTALE+PULIZIA 41647324039 (interrotta: il kernel ha ucciso il processo delle pianificazioni per memoria esaurita dell'host, OOM delle 13:47 UTC, riavvio automatico) e 41649057713 (riuscita); ERRORI 41653028100; PULIZIA 41655456853. Log in scratchpad/collaudo/{inv2,giri,incr2,err,pul,inv4}/log.txt. Schermate in scratchpad/app/audit/COLLAUDO_MOTORI/.

## Confronto con la fotografia del mattino (studio_1)
| Voce | Mattino | Dopo 2.478.0 | Esito |
|---|---|---|---|
| OCR letti / da leggere | 183 / 11.776 | 730 / 11.229 (547 letture in 24 h) | D4 attivo: scende a ogni giro di fascicolo |
| Errori «Fascicolo accodato non disponibile» | 612 in 24 h | 0 nelle ultime 2 ore (i 610 del giorno sono tutti precedenti al deploy) | D1 risolto; i 3 eventi abbandonati dello studio_2 si chiuderanno alla ripresa notturna |
| Eventi scaduti (lease) | 497 in 24 h | 2 | D2 risolto |
| Lettori tolti (presidio_pec, sentenza_da_archiviare) | presenti | assenti | D3 ok |
| Scadenze dai PDF | 11.962 «da leggere» | 0 da leggere, 11.962 «non richiesti» | D3 ok |
| Proforma | 210 «mai letti» | 210 «non pertinenti», 5 da rileggere | D3 ok |
| Motore documenti letti / da leggere | 7.372 / 4.589 | 8.086 / 3.875 | arretrato in calo |
| Sentenza e definizione | 7.072 letti | 10.850 letti (rilettura per versione nuova, una volta) | ok |
| Studio_2 PEC pertinenti mai esaminate | 258 | 258 (tutte con Message-ID, da 10/2025 a 10/2026) | D5 non risolto dalla 2.478 → corretto ora (riconciliazione), da verificare al prossimo deploy |

## Righe per motore (aggiornamento)
| Motore | Non rilegge (GIRI) | Incrementale | Errori | A vista | Esito |
|---|---|---|---|---|---|
| Motore documenti | giro 2 archivio: avviati 0, trovati 0 | aggiunta: letto solo il documento nuovo, 0 altri riletti; modifica: nuova impronta letta, 0 altri; rimozione: registro e sintesi allineati (4→5→4) | guasto «non_leggibile» con motivo, buono letto, pannello mostra l'errore (errori 1); dopo la sostituzione letto e pannello «tutto letto» | 9DC39668 e 9B9DF2A1 PC+tel: nessun errore JS/API, nessuno sfondamento; fascicolo di prova ok | OK, ma D7 |
| Testo e ricerca (OCR) | — | documento caricato: OCR «errore» | stesso errore sul buono | — | D8 corretto |
| Sentenza e definizione | scritture continue = rilettura della versione nuova (letti versione precedente 6.276) | non_leggibile corretto (documento non è una sentenza) | idem | — | OK |
| Presidio economico | 2 giri non confrontabili (il primo oltre 25 min, il secondo ha ripreso lo stesso run) ; analisi 25 per giro su 185 in attesa | — | — | — | arretrato a lotti |
| Presidio PEC (lavori) | giri 1 e 2: 0 lavori | — | — | — | OK |
| Sincronizzazione caselle | giro 2 saltato (pausa di 180 s) | — | — | — | OK |
| Presidio notifiche | **giro 2 rifà tutto**: scanned 308, items 116 come il giro 1 | — | — | catena a vista dell'altro agente | D6 corretto |

## Nuovi difetti e correzioni (ramo di sessione)
- D6 — Presidio notifiche che non si ferma mai: l'impronta «PEC senza fascicolo» era vuota perché in `pec_source_revisions` c'è una riga non inizializzata per l'etichetta «studio»; l'ha creata il primo INVENTARIO di questo collaudo (09:50, etichetta sbagliata per il flusso PEC→fascicolo, già corretta nello script). Correzione robusta in `web/services/notifications_runtime.py` (`_impronta_pec_senza_fascicolo`): ignora le righe non inizializzate di etichette senza messaggi. Test `test_d6_*`.
- D7 (aperto, serve una decisione) — Un documento caricato dall'avvocato aspetta in coda dietro tutti gli eventi in attesa (186 pending, servizio per data, 2 letture alla volta): in 6 minuti non era ancora letto; l'ha letto il giro sincrono del collaudo. Proposta: priorità agli eventi da caricamento/PEC (colonna di priorità in `letture_eventi`, migrazione SQLite/PostgreSQL gemella).
- D8 — Ogni OCR di un documento cifrato finiva in «errore: Impronta OCR diversa dalla fonte corrente del fascicolo» e il testo non alimentava l'archivio: `registra_lettura_ocr_nell_archivio` confrontava l'impronta del file cifrato con quella in chiaro. Corretto in `web/services/archivio_letture_runtime.py`. Test `test_d8_*`.
- D5 bis — Studio_2: 258 PEC pertinenti mai esaminate con cursore «arretrato completo». Aggiunta la riconciliazione in `acquire_local_pec_for_paths` (`web/services/pec_pipeline_runtime.py`): senza messaggi nuovi si prendono le PEC pertinenti senza alcun esito di acquisizione; il salto «archivio invariato» vale solo dopo una riconciliazione vuota. Test `test_d5_riconciliazione_*`.
- UI — «132 da leggere» accanto a «Tutto letto e collaudato»: la sintesi ora dice «132 letture in attesa in N motori» (`SintesiRegistroCard.tsx`, `lettureFascicolo.ts`, test JS). Bundle non ricompilato.
- Notato (perimetro notifiche, altro agente): su 9DC39668 tra le «prove di notifica» compaiono .eml estranei («Richiesta pagamento annualità…»).
- Memoria dell'host al limite (15,6 GB, 13,1 GB usati, swap 6,4 GB; OOM di llama-server alle 13:22 e del processo delle pianificazioni alle 13:47).

## Stato del fascicolo di prova
474D4C13: dopo PULIZIA 0 documenti di collaudo, né nel fascicolo né nel cestino; restano i 3 documenti originali del collaudo editor.

## D7 e prove di notifica (03/11/2026, sera, ramo di sessione)
- D7 corretto: colonna `priorita` in `letture_eventi`, gemella in `pct/sql/20260915_registro_letture.sql` e `_postgres.sql` (con `ALTER … ADD COLUMN IF NOT EXISTS` per PostgreSQL e aggiunta automatica per i registri SQLite esistenti). Gli eventi nati da un'azione dell'avvocato (documento caricato/modificato/rimosso, PEC collegata, «Leggi i nuovi») passano davanti; con due o più posti uno va sempre all'evento più vecchio, e la priorità vale una sola prenotazione. Test `test_d7_*` (ordine, parità schema, registro esistente).
- Prove di notifica estranee (9DC39668): `pct/obblighi_notifica_atto.py` `_prove` accettava come prova della notifica dell'atto la sola ricevuta di consegna di qualsiasi PEC del fascicolo («CONSEGNA: Richiesta pagamento…eml»). Ora una prova non legata all'atto vale solo con relata o con l'oggetto «notificazione ai sensi della legge n. 53 del 1994» (art. 3-bis L. 53/1994). Test `test_ricevuta_di_una_pec_qualsiasi_*`.
