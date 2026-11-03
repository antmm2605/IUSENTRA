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
