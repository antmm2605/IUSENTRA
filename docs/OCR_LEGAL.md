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
