# Compilatore: archivio Word nativo e PDF

## Perimetro e relazioni EXTRACTED

- `web/blueprints/template_atti.py::_importa_compilazione_editor_professionale` passa la bozza e il controllo normativo a `pct/template_atti_lex_service.py::create_editor_draft`.
- Il servizio costruisce il contenuto mediante il builder esistente, esclude i nodi tecnici CSS/script dal corpo Word e usa `pct/editor.py::html_to_docx`. Archivia i byte DOCX cifrati nel repository del fascicolo, conservando provenienza e audit.
- Il writer Word rispetta i ritorni di riga HTML nei paragrafi giustificati attraverso `doNotExpandShiftReturn`; una fonte con `text-align-last:justify` mantiene la richiesta esplicita di espansione.
- L'esportazione PDF continua a usare `pct/editor_export.py::esporta_documento_editor` e il salvataggio governato di `web/bootstrap/editor_finalize_routes.py`.

## Prove e difetti corretti

64 test mirati del gate normativo, writer DOCX ed export RTF superati; prova aggiuntiva della richiesta esplicita di espansione superata. Il nuovo test verifica contenitore ZIP Word, testo, grassetto, allineamento e assenza delle regole CSS nel corpo. Nessun documento storico convertito o eliminato.

Browser reale su `127.0.0.1:8080`, fascicolo controllato `C729BD2B`: compilazione normale di `LAV_RIC_001`, salvataggio DOCX, riapertura nell'editor, controllo visivo e scorrimento fino alla chiusura. Prima prova: le regole CSS di stampa apparivano nel testo Word; corretto e ripetuto il salvataggio. Seconda bozza `A68753C7` riaperta come DOCX, senza quel testo tecnico.

L'esportazione PDF aveva incontrato un lock storico locale di proprietà root: corretto esclusivamente il proprietario di quel file, senza rimuovere il lock o modificare i dati. La stessa richiesta ha poi prodotto `F117F9BD`. Il confronto visivo ha rilevato righe brevi dilatate nel PDF: correzione del writer condiviso, nuova esportazione `DD64A59C`, apertura nel lettore interno e scorrimento delle due pagine fino alla firma. Le intestazioni IN DIRITTO / RICHIESTE E CONCLUSIONI / MEZZI ISTRUTTORI E DOCUMENTI risultano compatte, senza la precedente dilatazione.

Le fonti di collaudo restano bozze con avvertenza normativa e segnaposti: questa verifica non ne certifica il contenuto giuridico. Non sono stati eseguiti firma, deposito o invio PEC. Non è una prova di parità grafica universale per tutti i documenti.

## CI Lex: causa e presidio

Run `39612934117`, SHA `aeb61282d544b8acde17922b29c5861f760bbf53`: nessuna riga precedentemente coperta persa; la rimozione di tre istruzioni coperte nella normalizzazione URL modifica il rapporto da 29039/35406 a 29036/35403. Soglie e gate invariati. Aggiunte prove del warmup: indisponibilità temporanea, recupero sul medesimo modello e nessun contatto senza modello selezionato. Esito remoto del nuovo commit ancora da verificare.

## Lavori distinti ancora aperti

PDFCraftTool/pdfcraft non è incluso in questo rilascio. Analisi REA 6.5.0 dei tre file d'ingresso alla revisione `0503080d60a337e40cc9888a749890ff49ed6b11`, evidenza `ev_38d6fa6ec72cac108326206c9a6f2fe843bca5f3608f0ff71955ee059b82dfa0`, conservata fuori dal prodotto. Il callback di salvataggio upstream comunica nome/dimensione dopo un download; non persiste nel repository del fascicolo. Integrazione, compatibilità della licenza AGPL e provenienza del motore WASM, salvataggio autenticato/versionato e accettazione reale restano da completare. Non confondere questo progetto con `storytold/pdfcraft`.

Offline e sincronizzazione PC-online rimangono un incarico distinto e non concluso. Deploy Lex v3 e importazione normativa successiva richiedono ancora l'esito positivo dei gate remoti.
