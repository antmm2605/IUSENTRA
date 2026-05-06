# Tranche 5A - Mappa route legacy

Data analisi: 2026-05-06
Branch base: claude/legal-electronic-filing-kIxcV

## Metodo

Comandi richiesti eseguiti prima degli edit:

```bash
git status --short
node scripts/react-migration/audit-react-migration.mjs
python scripts/react-migration/capture-legacy-contracts.py /studio /amministrazione /impostazioni /impostazioni-studio /impostazioni/calendario /impostazioni/pagamenti /sincronizzazione-calendari
```

`rg.exe` non era eseguibile sul workspace Windows (`Accesso negato`). La ricerca e' stata ripetuta con `Get-ChildItem` e `Select-String` sugli stessi perimetri `web`, `pct`, `tests`, usando i pattern richiesti.

## /studio

- Handler legacy: `web/blueprints/terminology_aliases.py`
- Funzione: `studio`
- Decorator: `@terminology_aliases.get("/studio")`
- Template usato: nessuno diretto; redirect 302 a `telematico_dashboard`, che rende `web/templates/telematico_dashboard.html`
- Repository/manager usati: alias senza repository diretto; il target usa `get_telematico`, `get_fascicoli`, backfill e status runtime telematico
- Permessi richiesti: nessun controllo RBAC diretto sull'alias; accesso autenticato tramite stack Flask/gate
- Form presenti: nessuno sull'alias
- POST presenti: nessuno sull'alias
- Action dei form: non applicabile
- Method dei form: non applicabile
- CSRF: non applicabile sull'alias
- Download/export presenti: nessuno sull'alias
- Azioni distruttive presenti: nessuna sull'alias
- Dati sensibili presenti: il target telematico mostra stato canali e import, per questo la 5A non replica il target
- Configurazioni sensibili presenti: potenziali configurazioni telematiche nel target, non lette dal bridge 5A
- Decisione: sbloccabile solo come hub React sicuro exact `/studio`, senza scritture e senza sostituire la cabina telematica; ogni subpath `/studio/*` resta legacy

## /amministrazione

- Handler legacy: `web/blueprints/terminology_aliases.py`
- Funzione: `amministrazione`
- Decorator: `@terminology_aliases.get("/amministrazione")`
- Template usato: nessuno diretto; redirect 302 a `/utenti`, che rende `web/templates/auth/utenti.html`
- Repository/manager usati: alias senza repository diretto; il target usa `get_utenti()` / `GestioneUtenti`
- Permessi richiesti: il target `/utenti` richiede `utenti.leggi`
- Form presenti: nessuno sull'alias
- POST presenti: nessuno sull'alias
- Action dei form: non applicabile
- Method dei form: non applicabile
- CSRF: non applicabile sull'alias
- Download/export presenti: nessuno sull'alias
- Azioni distruttive presenti: nessuna sull'alias; le route utente di dettaglio restano legacy
- Dati sensibili presenti: gestione utenti e permessi; la 5A espone solo metriche aggregate e link operativi
- Configurazioni sensibili presenti: nessuna configurazione tecnica
- Decisione: sbloccabile come hub React exact `/amministrazione`, vincolato a `utenti.leggi`; ogni subpath `/amministrazione/*` resta legacy

## /impostazioni

- Handler legacy: `web/blueprints/impostazioni.py`
- Funzione: `index`
- Decorator: `@impostazioni.route("/impostazioni", methods=["GET", "POST"])`
- Template usato: `web/templates/impostazioni/index.html`
- Repository/manager usati: `pct.config_studio.GestioneConfigStudio`, runtime Flask config, scheduler, runtime AI locale
- Permessi richiesti: login richiesto da `_richiedi_login`; nessun unlock React in questa tranche
- Form presenti: dati studio, PEC, firma digitale, SMTP, WhatsApp, scheduler, AI locale
- POST presenti: si', POST `/impostazioni`
- Action dei form: `/impostazioni` con tab di configurazione
- Method dei form: POST
- CSRF: template legacy protetto dal flusso Flask esistente
- Download/export presenti: pagina download Local Signer nel tab firma
- Azioni distruttive presenti: sovrascrittura configurazioni tecniche e credenziali
- Dati sensibili presenti: credenziali PEC/SMTP, chiavi firma, credenziali WhatsApp, configurazione AI e scheduler
- Configurazioni sensibili presenti: PEC, SMTP, firma digitale, AI locale, scheduler, canali comunicazione
- Decisione: resta legacy; React non espone endpoint, bridge operativo o salvataggi

## /impostazioni-studio

- Handler legacy: `web/blueprints/terminology_aliases.py`
- Funzione: `impostazioni_studio`
- Decorator: `@terminology_aliases.get("/impostazioni-studio")`
- Template usato: nessuno diretto; redirect a `/impostazioni`
- Repository/manager usati: nessuno diretto; target `GestioneConfigStudio`
- Permessi richiesti: login tramite target
- Form presenti: quelli di `/impostazioni`
- POST presenti: nessuno sull'alias; target POST legacy
- Action dei form: `/impostazioni`
- Method dei form: POST nel target
- CSRF: target legacy
- Download/export presenti: target firma
- Azioni distruttive presenti: target salva configurazioni tecniche
- Dati sensibili presenti: quelli del target impostazioni
- Configurazioni sensibili presenti: PEC, SMTP, firma digitale, AI locale, scheduler
- Decisione: resta legacy

## /impostazioni/calendario

- Handler legacy: `web/bootstrap/calendar_routes.py`
- Funzione: `impostazioni_calendario`
- Decorator: `@app.route("/impostazioni/calendario")`
- Template usato: `web/templates/impostazioni/calendario.html`
- Repository/manager usati: `get_calendar_sync()`, `get_agenda()`, `pct.cal_token`
- Permessi richiesti: route registrata nel runtime Flask autenticato; nessun unlock React in questa tranche
- Form presenti: rigenerazione collegamento, profili calendario esterno, sync/toggle/elimina profili
- POST presenti: `/impostazioni/calendario/rigenera`, `/impostazioni/calendario/profili`, `/impostazioni/calendario/profili/<id>/sync`, `/toggle`, `/elimina`
- Action dei form: route calendario legacy sopra elencate
- Method dei form: POST
- CSRF: gestito dal template legacy
- Download/export presenti: feed `.ics` agenda/scadenze/completo
- Azioni distruttive presenti: rigenera collegamento, elimina profilo, toggle profilo
- Dati sensibili presenti: collegamenti feed e sorgenti calendario esterno
- Configurazioni sensibili presenti: sincronizzazione calendari e sorgenti esterne
- Decisione: resta legacy

## /impostazioni/pagamenti

- Handler legacy: `web/blueprints/pagamenti.py`
- Funzione: `impostazioni_pagamenti`
- Decorator: `@pagamenti.route("/impostazioni/pagamenti", methods=["GET", "POST"])`
- Template usato: `web/templates/pagamenti/impostazioni.html`
- Repository/manager usati: `web.helpers.get_pagamenti()` / `pct.pagamenti.GestionePagamenti`
- Permessi richiesti: login richiesto da `_richiedi_login`
- Form presenti: Stripe, PayPal, Satispay, SumUp, bonifico
- POST presenti: si', POST `/impostazioni/pagamenti`
- Action dei form: `/impostazioni/pagamenti`
- Method dei form: POST
- CSRF: gestito dal template legacy
- Download/export presenti: nessuno nella pagina impostazioni
- Azioni distruttive presenti: modifica provider e webhook di pagamento
- Dati sensibili presenti: chiavi provider, credenziali webhook, dati bancari riservati
- Configurazioni sensibili presenti: provider pagamento e bonifico
- Decisione: resta legacy

## /sincronizzazione-calendari

- Handler legacy: `web/blueprints/terminology_aliases.py`
- Funzione: `sincronizzazione_calendari`
- Decorator: `@terminology_aliases.get("/sincronizzazione-calendari")`
- Template usato: nessuno diretto; redirect a `/impostazioni/calendario`
- Repository/manager usati: nessuno diretto; target `get_calendar_sync()`
- Permessi richiesti: login tramite target
- Form presenti: quelli di `/impostazioni/calendario`
- POST presenti: nessuno sull'alias; target POST legacy
- Action dei form: route calendario legacy
- Method dei form: POST nel target
- CSRF: target legacy
- Download/export presenti: feed `.ics` nel target
- Azioni distruttive presenti: rigenerazione collegamento, toggle/elimina profili nel target
- Dati sensibili presenti: collegamenti feed e sorgenti calendario esterno
- Configurazioni sensibili presenti: sincronizzazione calendari
- Decisione: resta legacy
