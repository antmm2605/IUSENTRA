# Prova comparativa OCR - 06/09/2026

Aggiornamento successivo: il benchmark sottostante descrive la prova iniziale, non lo stato corrente. pdf-inspector è ora integrato nella copia Docker locale, con modelli offline verificati, estrazione CAdES, esclusione del testo corrotto e lettura aggiuntiva dei riquadri. Prove UI e stato della consegna in `catalogazione-unica-fonti-2026-09-06.md`; produzione non ancora aggiornata con questa integrazione. Nessun risultato del benchmark costituisce accuratezza universale o promessa di catalogazione perfetta.

## Esito e perimetro

Sono state eseguite prove reali di estrazione su 12 PDF del fascicolo autorizzato di produzione 010701E9 (25 pagine), letti dalla fonte di verità SQLite tenant-aware. Ogni contenuto è stato decifrato in memoria e confrontato con il proprio SHA-256 registrato. Nessuna modifica a documenti, indici, catalogazioni, firme, Local Signer o flussi PST. Non è un collaudo del prodotto integrato: pdf-inspector non è stato collegato alla UI e la sua integrazione è **non verificata su macchina reale**.

Il candidato è più veloce sul campione e presenta miglioramenti documentati di lettura, ma non è un sostituto automatico già accettato. Non è stata misurata un'accuratezza globale del 95% né una catalogazione perfetta.

## Metodo

- Motore corrente: `extract_text_from_document`, estrazione nativa pdfplumber e Tesseract italiano quando richiesto, incluso il controllo già aggiunto per il solo timbro di firma.
- Candidato: pdf-inspector 1.17.0, PDFium native-v7988, ONNX Runtime 1.27.0 e modelli PP-OCRv6 Small. Librerie isolate in `/tmp/iusentra-pdf-inspector-20260906`, senza installazione nell'ambiente Python operativo.
- Download delle librerie verificati con SHA-256 pubblicato; preparazione dei modelli eseguita soltanto su una pagina sintetica priva di dati dello studio. Tutti i documenti reali elaborati con `offline=True`; nessun inoltro a Firecrawl o altri servizi OCR remoti.
- Confronto sequenziale sullo stesso server, una passata per modalità, modelli già scaricati, parametri ordinari dei due motori. I tempi sono esplorativi: non una media statistica né una misura dei tempi UI. Il candidato usa 150 DPI predefiniti per OCR; il motore corrente usa la propria configurazione ordinaria. Prove aggiuntive a 300 DPI riportate separatamente.
- Il numero di caratteri e gli indicatori OCR non sono stati usati come misura di correttezza. Esame visivo materiale di quattro pagine renderizzate dagli originali: procura, relata postale, fattura e intimazione. Non si dichiara una trascrizione manuale completa di tutte le 25 pagine.

## Tempi rilevati

| Documento | Pagine | Attuale, secondi | Candidato automatico, secondi |
|---|---:|---:|---:|
| Ricevuta PEC Documento_33584995 | 2 | 0,187 | 0,004 |
| AttoNonCodificato_33294205 | 1 | 0,130 | 0,023 |
| ProduzioneDocumentiRichiesti_32980252 | 3 | 9,715 | 2,377 |
| Ordinanza_32473463 | 1 | 0,061 | 0,020 |
| Procura | 1 | 6,233 | 2,850 |
| Avviso di ricevimento | 2 | 12,861 | 3,274 |
| Relata postale | 1 | 2,846 | 1,225 |
| Contratto preliminare | 6 | 21,396 | 5,662 |
| Fattura | 1 | 4,446 | 1,339 |
| Lettera 2018 | 2 | 7,144 | 1,845 |
| Lettera 2022 | 2 | 12,806 | 3,708 |
| Visure catastali | 3 | 11,665 | 2,829 |
| **Totale** | **25** | **89,489** | **25,158** |

Il rapporto osservato è circa 3,56 volte; il tempo complessivo è inferiore di circa il 71,9%. Il totale comprende anche il caso con estrazione semanticamente difettosa descritto sotto: velocità e correttezza restano distinte. Entrambi hanno restituito il numero atteso di pagine; questo non certifica completezza di tutti i campi.

## Qualità: miglioramenti osservati

- **Fattura:** il candidato recupera descrizione dei lavori, IVA 22%, imposta € 243,44 e totale € 1.350,00, assenti nel testo del motore corrente. Anche il codice fiscale stampato risulta letto meglio. Il contenuto del documento rimane la fonte: l'OCR non corregge eventuali errori presenti nell'originale.
- **Procura:** il codice fiscale della seconda parte è riprodotto correttamente dal candidato; il testo corrente contiene una lettera aggiuntiva. Il corpo è meno contaminato da caratteri del timbro laterale. Nessuna valutazione automatica della validità della procura o delle firme.
- **Relata:** il candidato ricompone meglio alcune parole spezzate a fine riga e conserva corpo, data e destinatario confrontati con la pagina.
- Le scansioni con timbro testuale sono riconosciute come bisognose di OCR: non viene scambiato il solo timbro per il contenuto del documento.

## Difetti osservati e prova della causa

- **Numero della fattura:** il riquadro `05`, visibile nell'originale, non compare nel testo di entrambi i motori. Il candidato non lo recupera nemmeno a 300 DPI. Non può quindi essere dichiarata estrazione completa della fattura.
- **Firme e segni grafici:** il candidato produce ancora frammenti senza significato, anche caratteri estranei all'italiano, vicino alle firme. Non devono diventare fatti, titoli o motivi di catalogazione.
- **Intimazione AttoNonCodificato:** entrambi i percorsi nativi sono difettosi. Il corrente duplica caratteri; il candidato crea ripetizioni e tabelle inesistenti. Il candidato automatico non richiede OCR su questa pagina; la modalità `force` a 150 e 300 DPI continua a mescolare il livello nativo difettoso con l'OCR (`fused`).
- **Diagnosi dell'intimazione:** elaborando una copia immagine in memoria della pagina originale, senza sostituire né salvare un nuovo documento nel fascicolo, il candidato restituisce un testo leggibile in circa 3,47 secondi. Corpo, data d'udienza, ora e attestazione risultano coerenti con la pagina osservata. Restano piccoli frammenti grafici finali. Questo dimostra la necessità di escludere il livello nativo corrotto, non una soluzione di prodotto già integrata.
- Le verifiche iniziali di parole chiave erano soltanto controlli esplorativi: per esempio l'intimazione riguarda interrogatorio formale, non necessariamente la parola “testi”; una mancata parola attesa dal test non è stata classificata automaticamente come errore OCR.

## Stato operativo e seguito necessario

La candidatura è motivata dai risultati, ma l'adozione richiede selezione verificata delle pagine, esclusione dei livelli testuali corrotti, controlli sui campi brevi/riquadri e separazione tra testo utile e rumore grafico. Il catalogo giuridico resta unico e separato dal punteggio tecnico OCR. Nessun cambio al motore operativo o deploy eseguito per questa prova. `/api/pronto` di produzione risponde `ok: true` dopo i test.

Il primo avvio del solo script di prova si è fermato dopo cinque documenti per assenza di `pdf2image` nella fase di rendering diagnostico; riusato `pypdfium2` già presente, ripresa la prova dai risultati salvati e raggiunti tutti i 12 documenti. Nessun pacchetto aggiunto al runtime operativo per risolvere questo errore.

Metriche grezze: `artifacts/ui-checks/pdf-inspector-comparison-20260906.json`. Script diagnostici in `artifacts/ui-checks/prepare_pdf_inspector_benchmark.py`, `benchmark_pdf_inspector_20260906.py`, `benchmark_pdf_inspector_followup_20260906.py` e `benchmark_pdf_inspector_raster_20260906.py`. Sono artefatti di collaudo, non codice del prodotto.

Fonti tecniche: [repository](https://github.com/firecrawl/pdf-inspector), [API Python](https://github.com/firecrawl/pdf-inspector/blob/main/docs/python.md), [runtime OCR](https://github.com/firecrawl/pdf-inspector/blob/main/docs/ocr-runtime.md). Riferimento ispezionato: commit `636ca1a58bdc1af4cd3fc20b8c1f549a1121cca7`.
