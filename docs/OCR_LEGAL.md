# OCR Legal-Grade IUSENTRA

Data: 24 maggio 2026.

## Obiettivo

Il flusso OCR legal-grade legge documenti di fascicolo, allegati PEC, ZIP e payload P7M senza sovrascrivere il file originale. Ogni esecuzione produce evidenze tracciabili: testo originale, testo corretto solo con regole deterministiche, token con coordinate, metriche, riepilogo regex, audit append-only e hash concatenati.

## Flusso

1. Ingest: accetta PDF, TIFF, JPEG, PNG, ZIP e P7M. Gli ZIP vengono estratti in modo sicuro e ogni contenuto supportato viene processato; i P7M vengono aperti tramite l'ispettore CAdES locale quando il payload è disponibile.
2. Normalizzazione: il raw blob e ogni pagina rasterizzata hanno SHA-256. I nomi file sono sanificati e ogni run usa UUID v4.
3. Pre-processing: rasterizzazione PDF, conversione immagini in scala di grigio, contrasto adattivo, denoise, binarizzazione e split leggero delle immagini a due pagine.
4. OCR router: `OcrEngine.run(pages)` restituisce token, testo pagina, versione engine e lingua. Il primario predefinito è Tesseract locale; il fallback locale è `native-text-fallback`. Engine cloud sono ammessi solo se la policy tenant non è `local-first`.
5. Post-OCR: calcola `avg_confidence`, `pct_tokens_<0.75`, `pct_tokens_<0.50`, anomalie layout, correzioni deterministiche e regex obbligatorie.
6. QC: fallback se `avg_confidence < 0.85` o `pct_tokens_<0.75 > 10`. Revisione umana se `avg_confidence < 0.70`, `pct_tokens_<0.50 > 5`, layout critico o campi obbligatori falliti dopo due tentativi.
7. Storage: JSON evidenza, raw/text/page artifacts, audit JSONL append-only, chain hash e merkle giornaliero.
8. Integrazione: EvidenceReady, notifica all'avvocato per date/adempimenti o revisione richiesta, salvataggio OCR accanto al documento, HIL UI e Lex/RAG solo con token sopra soglia.

## Identità Fascicolo-Cliente

L'abbinamento automatico a un fascicolo richiede almeno numero RG e segnale identitario del cliente: nome/cognome o codice fiscale coerente. Se un documento cita una parte diversa dal cliente del fascicolo, oppure il codice fiscale non coincide, il match diventa `needs_manual_match` e Lex non indicizza il documento fino alla revisione. Questa regola impedisce che dati di un cliente entrino nella conoscenza operativa di un altro fascicolo.

## Regex Pack

Le regole vivono in `legal_regex/` e sono versionate con `LEGAL_REGEX_PACK_VERSION`.

Campi minimi:

- codice fiscale persona fisica con checksum italiano;
- numero RG in varianti civili/tributarie comuni;
- PEC RFC-like con domini PEC/giustizia;
- date italiane e ISO, con blocco delle `data atto` future;
- importi con separatori italiani.

Il post-correction non usa modelli generativi: ogni modifica è una regola deterministica con `rule_id`, motivo, timestamp e autore.

## CLI

Esecuzione reale:

```powershell
python -m pct.cli ocr run .\documento.pdf --tenant=studio-1 --report
```

Script operativo equivalente:

```powershell
python scripts\run_legal_ocr.py .\documento.pdf --tenant studio-1 --storage-root .\data\legal_document_evidence\legal_ocr_cli
```

Output sintetico: numero evidenze, engine selezionato, confidenza media, necessità HIL, path evidenza, path testo OCR e proposte di notifica.

## HIL UI

La pagina Documenti AI mostra:

- token sotto 0.75 evidenziati;
- campi obbligatori validati o falliti;
- motivo della revisione;
- suggerimenti deterministici applicabili con pulsante;
- cronologia correzioni append-only.

L'applicazione di una correzione non modifica l'evidenza originale: aggiunge una voce firmata alla storia di revisione.

## Lex/RAG

Lex indicizza il documento singolo o tutto il fascicolo solo se:

- il documento è validato;
- l'abbinamento fascicolo-cliente non ha conflitti;
- il testo deriva da OCR legal-grade o overlay OCR approvato.

L'export Lex include solo token con confidenza almeno 0.75 e registra quante porzioni sono state escluse come fragili.

## Limiti

- ABBYY e provider cloud sono implementabili tramite la stessa interfaccia `OcrEngine`, ma non vengono chiamati se il tenant è local-first.
- Il fallback cloud va abilitato esplicitamente per tenant e deve essere coperto da consenso e audit.
- La verifica giuridica del contenuto resta responsabilità professionale: il sistema prepara evidenze, alert e revisione, senza sostituire il controllo dell'avvocato.

## Motore unico di lettura (2.315.0)

Dal 14/09/2026 esiste un solo motore di lettura del testo, `legal_ocr/motore`, usato da
tutti i punti del gestionale che leggono immagini o PDF scansionati: riconoscimento nel
fascicolo e nell'editor professionale (`web/services/document_ocr*.py`), indice di ricerca
(`pct/ocr.py`, worker OCR), Document AI (`pct/document_intelligence/extraction.py`), editor
(`pct/editor.py`), Lex (`lex/tools/_doc_extractor.py`), pipeline probatoria
(`legal_ocr/engines.py`), presidio PEC (`pct/pec_ocr_pipeline.py`), etichette delle notifiche
legali, campi in riquadro del PDF inspector.

| Modulo | Ruolo |
|---|---|
| `legal_ocr/motore/runtime.py` | Percorso di Tesseract, dizionari, lingua; `OMP_THREAD_LIMIT=1` (un thread per processo, parallelismo per pagina/configurazione) |
| `legal_ocr/motore/immagine.py` | Raddrizzamento, luce uniforme, ritaglio del bordo, densità 300-400 dpi, binarizzazione Otsu per le copie sbiadite, zone grafiche |
| `legal_ocr/motore/lettura.py` | Strategia: prima passata `--psm 6`; se confidenza ≥ 0,90 e testo sufficiente ci si ferma; altrimenti `psm 4/3/11` in parallelo; poi la pagina binarizzata; PDF ricercabile con la configurazione vincente |
| `legal_ocr/motore/consenso.py` | Secondo lettore PDF Inspector (PP-OCR ONNX, `/opt/iusentra/ocr/models` o `IUSENTRA_PDF_OCR_MODEL_DIR`), in parallelo; sostituisce solo le parole con confidenza Tesseract < 0,85 quando la sua pagina ha confidenza ≥ 0,90 e la riga è la stessa; `IUSENTRA_OCR_SECONDO_LETTORE=0` lo disattiva |
| `legal_ocr/motore/pagina.py` | Il percorso completo: lettura, consenso, impaginazione (`page_layout`), formato (`formato`), correzioni del formulario, riferimenti giuridici |
| `legal_ocr/motore/testo.py` | Solo testo: `testo_da_immagine`, `testo_da_immagine_bytes`, `testo_da_pdf` (nativo dove affidabile, ottico altrove) |
| `legal_ocr/motore/provisioning.py` | Dizionario `ita.traineddata` (tessdata_fast 4.1.0) scaricato e verificato con SHA-256 se manca; `IUSENTRA_OCR_AUTOPROVISION=0` lo disattiva; Windows: `scripts/installa_tesseract_windows.ps1` |
| `legal_ocr/formulario/` | Formulario legale di post-lettura: caratteri, abbreviazioni, punteggiatura, cifre, numeri romani, euro, accenti, marcatori degli elenchi; ogni regola con id, etichetta e motivo |

Misure locali su pagina A4 sintetica a 300 dpi (Tesseract 5.3, un thread): circa 1 s per
passata, lettura al 100% su testo pulito e al 99,95% su pagina ruotata di 1,5° e sfocata;
PDF Inspector al 99,7-100% in 1-1,3 s a 150 dpi. Le misure si ripetono con
`tests/test_document_ocr.py::test_ocr_reale_in_italiano_produce_pdf_a4_ricercabile` e con lo
script di benchmark riportato nel changelog 2.315.0.

## Confusioni tipiche dichiarate (2.316.0)

Le confusioni del lettore ottico stanno in una tabella sola,
`legal_ocr/formulario/confusioni.py`: lettere lette al posto delle cifre
(O/o→0, I/l/|/Ì→1, Z→2, S→5, B→8; con struttura certa anche D/Q→0, G→6, T→7,
q/g→9) e cifre lette al posto delle lettere (0→O, 1→I, 2→Z, 5→S, 6→G, 8→B). Le
regole che la usano correggono solo dove la forma dice che cosa deve esserci:

| Regola | Struttura |
|---|---|
| `num.data.v1`, `num.data_iso.v1` | date giorno/mese/anno e anno-mese-giorno |
| `num.data_estesa.v1` | «1O rnarzo 2O26» → 10 marzo 2026: giorno e anno a cifre, mese letto male o abbreviato riportato al nome, «primo»/«1º» → 1 |
| `num.ora.v1` | «ore 9.30» → ore 9:30 |
| `num.sequenza.v1`, `num.riferimento.v1`, `num.anno.v1` | importi, numeri di ruolo, anni, cifre dopo art./n./co. |
| `conf.codice_fiscale.v1`, `conf.codice_fiscale_nudo.v1` | sedici caratteri nelle posizioni lettera/cifra del codice fiscale, accettati solo se il carattere di controllo torna |
| `conf.partita_iva.v1`, `conf.cap.v1`, `conf.iban.v1`, `conf.numero_ruolo.v1` | undici cifre dopo P.IVA, cinque cifre del CAP davanti alla località, IBAN italiano nella sua struttura, numero e anno dopo R.G. |
| `conf.parola.v1` | «R0MA», «MILAN0», «Mi1ano»: cifre dentro una parola; l'uno maiuscolo (I o L?) solo con il lessico degli atti («TRIBUNA1E» → TRIBUNALE) |

Le date lette passano poi alla verifica del registro delle letture
(`docs/REGISTRO_LETTURE.md`): calendario, orizzonte del fascicolo, coerenza con
la PEC o con il portale, giorno e mese invertiti.
