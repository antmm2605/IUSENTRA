# Note operative editor professionale

Aggiornato il 05/07/2026.

## Obiettivo

Portare l'editor documenti/template atti a una superficie professionale tipo Word, usabile anche senza partire da un modello precompilato. Il link diretto previsto è `/template-atti/editor`.

## Richieste da preservare

- Visualizzazione pagine tipo Word: pagina 1 staccata da pagina 2, pagine create solo quando il contenuto le richiede.
- Timbro studio ripetuto sulle pagine successive quando il documento prosegue.
- Margini visibili e modificabili, orientamento verticale/orizzontale.
- Font e dimensione applicati solo al testo selezionato, non a tutto il documento.
- Toolbar realmente operativa: grassetto, corsivo, sottolineato, barrato, evidenziazione, allineamenti, liste, rientri, citazione, undo/redo, segnaposto.
- Stampa disponibile dal browser.
- Editor libero apribile senza autocompilazione cliente/fascicolo.
- Italiano visibile, date italiane e timezone `Europe/Rome`.
- Test visivo materiale su `http://127.0.0.1:8080`, con click reali e scroll completo.

## Stato tecnico attuale

- Route editor libero aggiunta: `/template-atti/editor` e alias `/template-atti/editor-libero`.
- Payload dedicato `editor_libero=1` con titolo `Documento libero`.
- Catalogo laterale ripopolato anche se l'archivio template studio è vuoto.
- Toolbar: font size estese `4..28`, stampa, orientamento e margini.
- Segnaposto inglesi principali sostituiti o non usati come fallback visivo.
- Flusso rumoroso a badge rimosso dal canvas.
- Pagine visuali A4 aggiunte con fogli separati, margini tratteggiati, footer pagina e timbro ripetuto.

## Verifiche già eseguite

- `python -m pytest tests/test_template_atti_frontend_contract.py -q`
- `python -m pytest tests/test_template_atti_frontend_contract.py tests/test_template_atti_timbro.py -q`
- `npm run typecheck`
- `npm run build:vite`
- `python -m py_compile web/blueprints/api_v1_react.py web/blueprints/template_atti.py pct/template_atti.py`
- `docker compose up -d --build app`
- `http://127.0.0.1:8080/api/pronto` risponde con timezone `Europe/Rome`.
- Prova reale nel browser integrato su `http://127.0.0.1:8080/template-atti/editor?qa=20260705-final-real`: inserito testo lungo, pagine create solo al bisogno, timbro ripetuto nelle pagine successive, scrittura reale nella pagina successiva e controllo geometrico senza sovrapposizioni timbro/testo.
- Prova reale aggiornata dopo rebuild Docker del 05/07/2026: il bundle usa `TemplateAttiPage-CKytqSlM.css` e le card del catalogo sono alte `88,8px`, senza sovrapposizioni tra titolo, descrizione e badge campi.
- Prova reale aggiornata con 16 paragrafi: 6 pagine create automaticamente, 6 timbri riportati, zero sovrapposizioni tra rettangoli del testo e timbro, circa `92px` liberi tra fondo timbro e primo testo della pagina successiva.
- Prova reale di scrittura nella pagina successiva: click nel corpo della pagina 2 e inserimento testo `SCRITTURA REALE PAGINA 2`, poi ricontrollo senza sovrapposizioni e reload per ripulire il testo di prova.
- Toolbar provata con click reali: grassetto, corsivo, sottolineato, barrato ed evidenziazione si accendono/spengono; allineamenti sinistra/centro/destra/giustifica restano attivi a turno; liste, rientri, citazione, annulla/ripristina e segnaposto rispondono.
- Toolbar ricliccata sul bundle nuovo: grassetto, corsivo, sottolineato, barrato, evidenziazione, allineamenti, liste, rientri, citazione, annulla, ripristina, titoli, paragrafo e segnaposto rispondono con stato visibile.
- Pannelli laterali catalogo/campi provati come collassabili e riapribili.
- Prova reale aggiornata dopo fix editor libero: bundle `TemplateAttiPage-DxrgkqsS.js` / `TemplateAttiPage-DUCULYK4.css`, pagina reale `http://127.0.0.1:8080/template-atti/editor`, header destro `Documento libero`, sottotitolo `Foglio indipendente dai modelli`, nessuna card template attiva, zero gruppi campo template, progress non visibile.
- Placeholder del foglio libero verificato su contenteditable vuoto con HTML interno `<p><br></p>`: testo visibile `Scrivi qui il documento libero. Il timbro studio resta riportato su ogni pagina.`.
- Click reale su card `Invito alla mediazione` dal foglio libero: navigazione a `/template-atti/compila/STR_COM_001`, header `Campi da compilare`, card del modello attiva, 3 gruppi campi e bozza template visibile.
- Click reale su `Editor libero` dalla toolbar: ritorno a `/template-atti/editor`, placeholder visibile, nessun template selezionato.
- Scrittura reale sul foglio libero: click nel corpo documento e digitazione `Prova reale editor libero.`, testo inserito nel contenteditable, placeholder sparito, una pagina e un timbro; reload finale eseguito per ripulire la frase di prova.
- Correzione 05/07/2026: i placeholder principali generati dal frontend sono ora in italiano (`[DESTINATARIO_O_UFFICIO]`, `[TITOLO_ATTO]`, `[CLIENTE_O_MITTENTE]`, `[CONTROPARTE_O_DESTINATARIO]`, `[FATTI]`, `[RICHIESTE_E_CONCLUSIONI]`, `[LUOGO]`, `[DATA_DOCUMENTO]`, `[AVVOCATO]`) mantenendo compatibilità con i token storici inglesi se presenti in vecchie bozze.
- Correzione 05/07/2026: la bozza iniziale non è più identica per tutti i modelli; sono differenziati almeno invito/mediazione, accordo transattivo, appelli civili/amministrativi/lavoro/tributari, appello cautelare, penale e attestazione di conformità/notifica.
- Prova reale 05/07/2026 nel browser integrato su `http://127.0.0.1:8080`: cliccati 10 template dal catalogo (`Invito alla mediazione`, `Accordo Transattivo`, `Appello al Consiglio di Stato`, `Appello Cautelare`, `Appello cautelare penale`, `Appello nel rito lavoro`, `Appello Previdenziale`, `Appello tributario`, `Attestazione di conformità`, `Atto di appello`). Ogni template apre una bozza coerente, nessuna bozza contiene più `[RECIPIENT_OR_COURT]`, `[TITLE]`, `[CLIENT_OR_SENDER]`, `[COUNTERPARTY_OR_RECIPIENT]`, `[FACTS]`, `[REQUESTS_OR_CONCLUSIONS]`, `[PLACE]`, `[DOCUMENT_DATE]` o `[LAWYER]`.
- Prova reale 05/07/2026 sul foglio libero dopo rebuild Docker: incollati 14 paragrafi nel corpo documento, create automaticamente 3 pagine e 3 timbri; pagina 2 e pagina 3 hanno circa 235 px tra fondo timbro e primo testo. Reload finale eseguito e foglio lasciato pulito.

## Blocco aperto

Restano da completare prima della chiusura complessiva:

1. Testare almeno 10 template dal catalogo laterale e annotare i template non utili.
2. Verificare font/size/margini/orientamento su selezioni reali in più punti del documento.
3. Completare commit, push branch gemelli, controlli GitHub/CodeQL e deploy Hetzner.

Finché queste prove estese e i gate di consegna non sono completati, il lavoro resta aperto.
