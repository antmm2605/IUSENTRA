# Tranche 7A - Route map preventivi e incarichi

Data: 2026-05-06

Nota preflight: `rg.exe` non e' eseguibile nell'ambiente locale per errore `Accesso negato`; la ricerca richiesta e' stata eseguita con `Select-String` su `web`, `pct` e `tests`.

## Superficie

- Tipo superficie: archivio economico/mandato, app UI operativa.
- Target React 7A: `/preventivi`, `/preventivi/nuovo`, `/preventivi/conferimento/nuovo`.
- Skill/direzione UI: prodotto gestionale per studio legale, densita operativa, dati reali, nessun template SaaS generico, nessun dato demo.
- Fonte primaria: route legacy Flask e repository reali; React resta un layer GET/read-only e form HTML standard verso POST legacy.

## /preventivi

- Handler legacy: `web/blueprints/preventivi.py`
- Funzione: `lista`
- Decorator: `@preventivi.route("/", methods=["GET"])`, `@_richiedi_login`
- Template: `web/templates/preventivi/lista.html`
- Manager/repository: `_get_gp()` / `web.helpers.get_preventivi`, `get_clienti()`
- Permessi: login richiesto; nessun permesso granulare aggiuntivo rilevato nel handler.
- Form presenti: filtro archivio, `method="get"`.
- POST presenti: no.
- Action form: query corrente.
- CSRF: non richiesto per GET.
- Download/export: non nella lista; link a dettagli e wizard.
- Documenti: non generati nella lista.
- Calcoli compensi: no, ma il legacy chiama `gp.aggiorna_scaduti()` e aggiorna stati scaduti.
- Wizard: link a `/preventivi/wizard`.
- Generazione fascicolo/parcella: no.
- Dati sensibili: cliente, fascicolo, importi e stati; nessun dato bancario o credenziale.
- Decisione: sbloccabile come archivio/lista React read-only. Il bridge non deve chiamare `aggiorna_scaduti()` per non modificare stati.

## /preventivi/nuovo

- Handler legacy: `web/blueprints/preventivi.py`
- Funzione: `nuovo_preventivo`
- Decorator: `@preventivi.route("/nuovo", methods=["GET", "POST"])`, `@preventivi.route("/nuovo/<id_cliente>", methods=["GET", "POST"])`, `@_richiedi_login`
- Template GET: `web/templates/preventivi/form_preventivo.html`
- Manager/repository: `get_clienti()`, `_get_gp()`, `get_fascicoli()`, `gp.crea_preventivo(...)`
- Permessi: login richiesto; nessun permesso granulare aggiuntivo rilevato nel handler.
- Form presenti: `id="formPreventivo"`, `method="post"`, senza action esplicita.
- POST presenti: si, legacy.
- Action form: route corrente; per React usare `/preventivi/nuovo`.
- CSRF: nessun campo CSRF esplicito rilevato nel template; `LegacyPostForm` aggiunge il token meta se disponibile.
- Campi POST principali: `id_cliente`, `oggetto`, `voce_descr[]`, `voce_importo[]`, `voce_tipo[]`, `valore_controversia`, `tipo_compenso`, `tariffa_oraria`, `ore_stimate`, `fasi_incluse[]`, `applica_cassa`, `applica_iva`, `anticipazioni_art15`, `note`, `id_fascicolo`, `data_emissione`, `data_scadenza`, `complessita`, campi compenso a tempo e clausole.
- Download/export: no nel GET form.
- Documenti: no nel GET form.
- Calcoli compensi: il POST delega al backend; il template contiene JavaScript di supporto non canonico.
- Wizard: link a `/preventivi/wizard`.
- Generazione fascicolo/parcella: no nel POST di nuovo preventivo.
- Dati sensibili: importi e riferimenti pratica; nessun segreto.
- Decisione: sbloccabile solo come GET React con form HTML standard verso POST legacy. Nessun fetch POST, nessun calcolo React.

## /preventivi/conferimento/nuovo

- Handler legacy: `web/blueprints/preventivi.py`
- Funzione: `nuovo_conferimento`
- Decorator: `@preventivi.route("/conferimento/nuovo", methods=["GET", "POST"])`, `@preventivi.route("/conferimento/nuovo/<id_cliente>", methods=["GET", "POST"])`, `@_richiedi_login`
- Template GET: `web/templates/preventivi/form_conferimento.html`
- Manager/repository: `get_clienti()`, `_get_gp()`, `get_fascicoli()`, `gp.crea_conferimento(...)`
- Permessi: login richiesto; nessun permesso granulare aggiuntivo rilevato nel handler.
- Form presenti: `id="formConferimento"`, `method="post"`, senza action esplicita.
- POST presenti: si, legacy.
- Action form: route corrente; per React usare `/preventivi/conferimento/nuovo`.
- CSRF: nessun campo CSRF esplicito rilevato nel template; `LegacyPostForm` aggiunge il token meta se disponibile.
- Campi POST principali: `id_cliente`, `oggetto`, `avvocato_referente`, `compenso_pattuito`, `tariffa_oraria`, `quota_palmario_pct`, `id_preventivo`, `id_fascicolo`, `apri_fascicolo_guidato`, tipo pratica, compenso a tempo e clausole.
- Download/export: no nel GET form.
- Documenti: no nel GET form.
- Calcoli compensi: no in React; eventuali importi sono letti o inviati al POST legacy.
- Wizard: no, ma puo derivare da preventivo generato da wizard legacy.
- Generazione fascicolo/parcella: il POST puo aprire flusso guidato fascicolo; resta legacy.
- Dati sensibili: incarico, cliente, fascicolo e importi; nessun segreto.
- Decisione: sbloccabile solo come GET React con form HTML standard verso POST legacy.

## /preventivi/wizard

- Handler legacy: `web/blueprints/preventivi.py`
- Funzioni: `wizard`, `wizard_calcola`, `wizard_genera`
- Template: `web/templates/preventivi/wizard.html`
- Manager/repository: `pct.motore_preventivo`, `pct.tariffario`, `get_clienti()`, `get_fascicoli()`, `get_preventivi()`
- Permessi: login richiesto.
- Form presenti: `method="post" action="{{ url_for('preventivi.wizard_genera') }}"`.
- POST presenti: si, `/preventivi/wizard/genera`.
- Download/export: no diretto; genera oggetti che possono produrre documenti su dettagli legacy.
- Calcoli compensi: si, via `/preventivi/wizard/calcola` e motore backend.
- Wizard: si, completo.
- Generazione fascicolo/parcella: generazione preventivo/conferimento e apertura fascicolo guidata.
- Dati sensibili: dati pratica, cliente, importi e log economico.
- Decisione: resta legacy operational.

## /preventivi/p/* e /preventivi/conferimento/*

- Handler legacy: `web/blueprints/preventivi.py`
- Funzioni principali: `dettaglio_preventivo`, `cambia_stato_preventivo`, `workflow_invia_cliente`, `workflow_accetta_studio`, `elimina_preventivo`, `pdf_preventivo`, `dettaglio_conferimento`, `cambia_stato_conferimento`, `workflow_firma_conferimento_studio`, `elimina_conferimento`, `pdf_conferimento`
- Template: `preventivi/dettaglio_preventivo.html`, `preventivi/dettaglio_conferimento.html`
- POST presenti: stati, workflow, eliminazione.
- Action POST: route legacy specifiche.
- CSRF: non rilevato nei template dettaglio; resta competenza legacy.
- Download/export: si.
- Documenti: stampe e documenti prodotti da route legacy.
- Calcoli compensi: log e tracciabilita presenti nel dettaglio.
- Generazione fascicolo/parcella: collegamenti e conversioni presenti.
- Decisione: resta legacy operational; React 7A puo solo linkare i dettagli con `?_legacy=1`.

## /compensi-forensi

- Handler legacy: `web/blueprints/terminology_aliases.py`
- Funzione: `compensi_forensi`
- Comportamento: redirect a `/tariffario`.
- Permessi: eredita il flusso legacy target.
- Decisione: resta legacy operational; nessun bridge React operativo.

## /tariffario

- Handler legacy: `web/bootstrap/tariffario_routes.py`
- Funzione: `tariffario`
- Decorator: `@app.route("/tariffario", methods=["GET", "POST"])`
- Template: `web/templates/tariffario.html`
- Manager/repository: `pct.tariffario`, `pct.tariffario_catalogo`, `web.services.tariffario_runtime`, tabelle normative.
- Permessi: route legacy non intercettata da React; accesso come da app storica.
- Form presenti: form POST calcolo.
- POST presenti: si.
- Download/export: non target 7A.
- Documenti: puo preparare link verso wizard/precompilazioni, non sostituito.
- Calcoli compensi: si, motore completo.
- Decisione: resta legacy operational.
