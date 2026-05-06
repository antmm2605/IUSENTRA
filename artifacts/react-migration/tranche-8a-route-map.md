# Tranche 8A - Route map legacy

## Nota strumenti

`rg` non e stato utilizzabile nella sessione locale per errore di accesso negato su `rg.exe`; l'analisi e stata completata con `Select-String` su `web`, `pct` e `tests`, piu lettura diretta dei file handler e template.

## `/compensi-forensi`

- File handler legacy: `web/blueprints/terminology_aliases.py`.
- Handler: `compensi_forensi`.
- Template usato: nessuno; redirect a endpoint `tariffario`.
- Repository/manager usati: nessuno diretto.
- Permessi richiesti: sessione autenticata implicita come per la superficie destinazione; nessun helper granulare trovato.
- Form presenti: no.
- POST presenti: no.
- Action form: non applicabile.
- Method form: non applicabile.
- CSRF: non applicabile.
- Download/export: no.
- PDF/DOCX: no.
- Formule/calcoli: no.
- Wizard: no.
- Generazione preventivo: no.
- Integrazione fatturazione: no.
- Dati sensibili: no.
- Decisione: sbloccabile come GET React exact con link e dati read-only; ogni sottopercorso resta legacy.

## `/tariffario`

- File handler legacy: `web/bootstrap/tariffario_routes.py`.
- Handler: `tariffario`.
- Template usato: `web/templates/tariffario.html`.
- Repository/manager usati: `pct.tariffario`, `pct.tariffario_catalogo`, `pct.motore_preventivo`, `web.services.tariffario_runtime`, `web.helpers.get_normative_tables`.
- Permessi richiesti: sessione autenticata; nessun helper granulare dedicato rilevato.
- Form presenti: si, `id="tariffarioForm"`.
- POST presenti: si, `@app.route("/tariffario", methods=["GET", "POST"])`.
- Action form: assente nel template, quindi POST alla route corrente `/tariffario`.
- Method form: `post`.
- CSRF: nessun campo CSRF esplicito rilevato nel contratto legacy.
- Download/export: link e integrazioni restano legacy se presenti nel risultato.
- PDF/DOCX: eventuali stampe/documenti restano nei workflow storici.
- Formule/calcoli: presenti nel backend legacy con `calcola_compenso`, `motore_calcola`, accessori, spese e riepilogo economico.
- Wizard: integrazione verso wizard preventivi esistente.
- Generazione preventivo: collegamento legacy tramite URL precompilati, non React.
- Integrazione fatturazione: presente nei canali legacy.
- Dati sensibili: nessun segreto serializzato nella nuova API; i bridge espongono solo campi whitelisted.
- Decisione: sbloccabile solo come GET React exact con form HTML verso POST legacy; ogni sottopercorso resta legacy.

## `/preventivi/wizard`

- File handler legacy: `web/blueprints/preventivi.py`.
- Handler: `wizard`, con endpoint AJAX/POST collegati `wizard_calcola` e `wizard_genera`.
- Template usato: `web/templates/preventivi/wizard.html`.
- Repository/manager usati: preventivi, clienti, fascicoli, motore preventivo e tariffario.
- Permessi richiesti: sessione autenticata e policy legacy esistente.
- Form presenti: si.
- POST presenti: si, generazione preventivo e azioni correlate.
- Action form: route wizard legacy.
- Method form: `post`.
- CSRF: gestito dal flusso legacy.
- Download/export: possibili nei workflow collegati.
- PDF/DOCX: produzione documenti collegata al legacy.
- Formule/calcoli: presenti e non migrati.
- Wizard: presente.
- Generazione preventivo: presente.
- Integrazione fatturazione: collegata a conversioni e parcelle legacy.
- Dati sensibili: dati mandato e cliente, non serializzati nella tranche.
- Decisione: deve restare legacy.

## `/preventivi/*`

- File handler legacy: `web/blueprints/preventivi.py`.
- Handler: dettaglio, modifica, stato, documenti, conferimenti, conversioni.
- Template usato: template in `web/templates/preventivi/`.
- Repository/manager usati: preventivi, clienti, fascicoli, fatturazione, documenti.
- Permessi richiesti: policy legacy esistente.
- Form presenti: si.
- POST presenti: si.
- Action form: route preventivi legacy.
- Method form: `post`.
- CSRF: gestito dal flusso legacy.
- Download/export: si, ove previsto.
- PDF/DOCX: si, ove previsto.
- Formule/calcoli: collegate al motore backend.
- Wizard: collegato.
- Generazione preventivo: si.
- Integrazione fatturazione: si.
- Dati sensibili: dati cliente, mandato, fascicolo.
- Decisione: resta legacy salvo `/preventivi`, `/preventivi/nuovo`, `/preventivi/conferimento/nuovo` gia migrati nella 7A.

## `/fatturazione/*`

- File handler legacy: `web/blueprints/fatturazione.py`.
- Handler: dettaglio, modifica, export, incassi e documenti.
- Template usato: template fatturazione legacy.
- Repository/manager usati: fatturazione, clienti, preventivi, pagamenti.
- Permessi richiesti: policy legacy esistente.
- Form presenti: si.
- POST presenti: si.
- Download/export: si.
- PDF/DOCX/XML: si.
- Formule/calcoli: presenti nel backend legacy.
- Wizard/generazione preventivo: collegamenti economici storici.
- Integrazione fatturazione: core della route.
- Dati sensibili: dati economici e fiscali.
- Decisione: resta legacy.

## `/template-atti`

- File handler legacy: blueprint template atti, raggiunto anche dagli alias in `web/blueprints/terminology_aliases.py`.
- Handler: lista/catalogo/compila secondo blueprint legacy.
- Template usato: template atti legacy.
- Repository/manager usati: repository template e documenti.
- Permessi richiesti: policy legacy esistente.
- Form presenti: si.
- POST presenti: si.
- Download/export: possibile.
- PDF/DOCX: produzione documentale legacy.
- Formule/calcoli: no economico, ma generazione documento.
- Wizard: redazione/compilazione guidata.
- Generazione preventivo: no.
- Integrazione fatturazione: no diretta.
- Dati sensibili: contenuti atti e fascicoli.
- Decisione: resta legacy.

## `/redazione-atti`

- File handler legacy: `web/blueprints/terminology_aliases.py`.
- Handler: `redazione_atti`, `redazione_atti_catalogo`, `redazione_atti_redigi`.
- Template usato: template atti della destinazione `template_atti`.
- Repository/manager usati: repository template/documenti tramite destinazione.
- Permessi richiesti: policy legacy esistente.
- Form presenti: nella destinazione legacy.
- POST presenti: nella destinazione legacy.
- Download/export: possibile nella destinazione legacy.
- PDF/DOCX: produzione documentale legacy.
- Formule/calcoli: no economico.
- Wizard: compilazione/redazione guidata.
- Generazione preventivo: no.
- Integrazione fatturazione: no diretta.
- Dati sensibili: contenuti atti e fascicoli.
- Decisione: resta legacy.
