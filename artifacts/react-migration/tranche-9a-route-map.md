# Tranche 9A - Mappa route documentali

Data analisi: 2026-05-06.

Nota operativa: `rg.exe` non era eseguibile nell'ambiente WindowsApps locale (`Accesso negato`), quindi le ricerche richieste sono state replicate con `Get-ChildItem ... | Select-String` sugli stessi perimetri `web`, `pct` e `tests`.

## /template-atti

- Handler legacy: `web/blueprints/template_atti.py::lista`
- Template: `web/templates/template_atti/lista.html`
- Repository/manager: `GestioneTemplateAtti` tramite `_get_gt()`, `pct.template_atti.CATEGORIE`, `pct.compilatore_atti.modelli_per_area`
- Permessi: login Flask tramite `_richiedi_login`; nessun permesso granulare aggiuntivo rilevato
- Form presenti: form POST per copia e cancellazione su card legacy
- POST presenti: si, su `/<id_template>/clona` e `/<id_template>/elimina`
- Action form: `url_for('template_atti.clona', ...)`, `url_for('template_atti.elimina', ...)`
- Method form: `post`
- CSRF: non rilevato token esplicito nel template
- Upload: no nella lista exact
- Download/export/PDF/DOCX: no nella lista exact
- Editor/contentEditable: no nella lista exact
- Template raw/testo atto: non renderizza `corpo`; mostra metadati e descrizioni/note
- AI/Lex/generazione: no nella lista exact
- Checklist deposito: solo collegamenti indiretti di dominio, nessun flusso checklist operativo
- Dati sensibili: metadati template studio; niente segreti o contenuti integrali
- Decisione: sbloccabile solo come dashboard/catalogo React read-only con azioni legacy sicure.

## /template-atti/catalogo

- Handler legacy: `web/blueprints/template_atti.py::catalogo`
- Template: `web/templates/template_atti/catalogo.html`
- Repository/manager: `pct.template_catalog_service.build_template_catalog_page_context`, `pct.compilatore_atti.MODELS`, `get_essential_docs`
- Permessi: login Flask tramite `_richiedi_login`
- Form presenti: copia nel mio studio
- POST presenti: si, form `template_atti.clona`
- Action form: `url_for('template_atti.clona', id_template=t.codice)`
- Method form: `post`
- CSRF: non rilevato token esplicito nel template
- Upload: no
- Download/export/PDF/DOCX: solo metadati di requisito; nessuna produzione file nella route catalogo
- Editor/contentEditable: no
- Template raw/testo atto: no, il catalogo espone metadati, compliance e dati obbligatori
- AI/Lex/generazione: no
- Checklist deposito: solo compliance e controlli deposito come metadati
- Dati sensibili: metadati catalogo, nessun segreto
- Decisione: sbloccabile come catalogo React read-only; copia/editor restano su route legacy.

## /template-atti/nuovo

- Handler legacy: `web/blueprints/template_atti.py::nuovo`
- Template: `web/templates/template_atti/form.html`
- Repository/manager: `GestioneTemplateAtti`
- Permessi: login Flask tramite `_richiedi_login`
- Form presenti: form principale di creazione modello
- POST presenti: si, creazione template con `titolo`, `categoria`, `corpo`, `note`
- Action form: route corrente `/template-atti/nuovo`
- Method form: `post`
- CSRF: non rilevato token esplicito nel template
- Upload: si, import documento verso `/template-atti/api/importa-documento`
- Download/export/PDF/DOCX: importa DOCX/PDF/TXT/HTML e prepara successivi output legacy
- Editor/contentEditable: si, macro editor professionale e preview import con `contenteditable="true"`
- Template raw/testo atto: si, campo `corpo`
- AI/Lex/generazione: no diretto nella route nuovo, ma collegata al sistema editor/generazione legacy
- Checklist deposito: no
- Dati sensibili: contenuto integrale del modello
- Decisione: deve restare legacy.

## /template-atti/*

- Handler legacy: `web/blueprints/template_atti.py` (`scheda`, `modifica`, `clona`, `elimina`, `usa`, `compila`, API editor/import, PDF e assistente)
- Template: `scheda.html`, `form.html`, `usa.html`, `compilatore.html`, `anteprima.html`, `anteprima_compilatore.html`
- Repository/manager: `GestioneTemplateAtti`, `pct.compilatore_atti`, assistente redazionale, servizi PDF/import
- Permessi: login Flask tramite `_richiedi_login`
- Form presenti: modifica, uso template, compilatore guidato, preview PDF, clone/delete
- POST presenti: si, modifica, clone, delete, usa, compila, layout editor, import documento, PDF, assistente
- Action form: route legacy dedicate del blueprint `template_atti`
- Method form: `post`
- CSRF: non rilevato token esplicito nei template analizzati
- Upload: si, import documento e acquisizione immagini
- Download/export/PDF/DOCX: si, PDF e import DOCX/PDF
- Editor/contentEditable: si
- Template raw/testo atto: si, `t.corpo`, testo compilato e anteprime editor
- AI/Lex/generazione: si, assistente redazionale e compilatore
- Checklist deposito: compliance e verifica deposito
- Dati sensibili: contenuti integrali di modelli/atti e dati pratica
- Decisione: ogni sottoroute diversa da `/template-atti/catalogo` resta legacy.

## /redazione-atti

- Handler legacy: `web/blueprints/terminology_aliases.py::redazione_atti`
- Template: nessuno diretto, redirect a `template_atti.lista`
- Repository/manager: indiretti di `/template-atti`
- Permessi: eredita la route destinazione con login Flask
- Form presenti: nessun form nel redirect; la destinazione legacy contiene form clone/delete
- POST presenti: no sulla route alias exact
- Action form: non applicabile sulla route alias
- Method form: non applicabile
- CSRF: non applicabile
- Upload/download/export/editor/contentEditable: no sulla route alias exact
- Template raw/testo atto: no sulla route alias exact
- AI/Lex/generazione: no sulla route alias exact
- Checklist deposito: no sulla route alias exact
- Dati sensibili: no payload proprio
- Decisione: sbloccabile come superficie operativa React controllata che richiama solo metadati e route legacy sicure.

## /redazione-atti/*

- Handler legacy: `web/blueprints/terminology_aliases.py::redazione_atti_catalogo`, `redazione_atti_redigi`
- Template: redirect verso catalogo o compilatore template atti
- Repository/manager: indiretti di `template_atti.catalogo` e `template_atti.compila`
- Permessi: eredita login Flask della destinazione
- Form/POST/editor/generazione: presenti nelle destinazioni legacy, soprattutto compilatore e assistente
- Upload/download/export/PDF/DOCX: presenti nei flussi template/redazione legacy
- Template raw/testo atto: possibile nelle destinazioni
- AI/Lex/generazione: possibile nella redazione guidata legacy
- Decisione: deve restare legacy.

## /checklist

- Handler legacy: `web/bootstrap/checklist_routes.py::checklist_atti`
- Template: `web/templates/checklist/lista.html`
- Repository/manager: `pct.checklist_atti` e helper fascicoli nel wizard collegato
- Permessi: route registrata su app, con superfici operative collegate a fascicolo/sessione
- Form/POST: la dashboard exact e le sottoroute wizard includono upload e POST su `/fascicoli/<id>/wizard/...`
- Upload/download/export: upload documenti nel wizard fascicolo
- Editor/contentEditable/template raw: no sulla dashboard exact
- AI/Lex/generazione/checklist deposito: checklist operative e wizard fascicolo
- Dati sensibili: dati fascicolo e allegati nei flussi collegati
- Decisione: resta legacy.

## /deposito/checklist

- Handler legacy: `web/bootstrap/deposito_routes.py::deposito_checklist`
- Template: `web/templates/deposito_checklist.html`
- Repository/manager: procedure deposito collegate, `get_fascicoli`, validatori deposito e flussi PEC/busta
- Permessi: superficie operativa del deposito telematico
- Form/POST: le route deposito collegate hanno POST su esiti, validazione, generazione busta e invio
- Upload/download/export/PDF/DOCX: generazione/download busta e allegati nei flussi correlati
- Editor/contentEditable: no sulla checklist exact
- AI/Lex/generazione: no diretto, ma collegata a deposito end-to-end
- Checklist deposito: si, route primaria
- Dati sensibili: fascicoli, atti, allegati e dati deposito
- Decisione: resta legacy.

## /giurisprudenza

- Handler legacy: `web/blueprints/giurisprudenza.py::index`
- Template: `web/templates/giurisprudenza/index.html`
- Repository/manager: `get_giurisprudenza`, sync runtime giurisprudenza, tassonomie e fonti
- Permessi: login Flask tramite `_richiedi_login`
- Form/POST: sottoroute `nuova`, `modifica`, `sync`, classificazione e import
- Upload/download/export: raw documents e import nelle sottoroute
- Editor/contentEditable: no sulla index, ma form di scheda sentenza nelle sottoroute
- Template raw/testo atto: testi sentenze/documenti nelle viste dettaglio
- AI/Lex/generazione: classificazione suggerita e workflow fonti
- Checklist deposito: no
- Dati sensibili: fonti, collegamenti pratica e documenti raw
- Decisione: resta legacy.

## /legal-intelligence

- Handler legacy: `web/blueprints/legal_intelligence.py::index`
- Template: `web/templates/legal_intelligence/index.html`
- Repository/manager: `get_legal_intelligence`, `LegalIntelligenceDailyEngine`, pipeline aggiornamenti normativi
- Permessi: login Flask tramite `_richiedi_login`
- Form/POST: monitor, daily sync, approvazione update, rigenerazione indice AI, sync normativo e import mediazione
- Upload/download/export: import registro mediazione e snapshot
- Editor/contentEditable: no sulla index
- Template raw/testo atto: no sulla index, ma diff/news/update nelle sottoroute
- AI/Lex/generazione: indice AI e workflow legal intelligence
- Checklist deposito: no
- Dati sensibili: snapshot studio, portali, agenda, scadenze e aggiornamenti in revisione
- Decisione: resta legacy.
