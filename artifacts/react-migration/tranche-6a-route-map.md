# Tranche 6A route map

Data: 2026-05-06
Branch base: claude/legal-electronic-filing-kIxcV

## /fatturazione

- Handler legacy: `web/blueprints/fatturazione.py`
- Funzione: `lista`
- Template: `web/templates/fatturazione/lista.html`
- Repository/manager: `web.helpers.get_fatturazione`, `web.helpers.get_clienti`
- Permessi: sessione Flask richiesta tramite `_richiedi_login`; nessun `ha_permesso` specifico nel legacy.
- Form presenti: filtro GET per anno, stato, cliente, ricerca testuale.
- POST presenti: nessun POST sulla lista.
- Action form: `/fatturazione` con query string.
- Method form: `get`.
- CSRF: non richiesto per filtro GET.
- Download/export: link operativi verso PDF dettaglio e voce export legacy.
- PDF/XML: non generati dalla lista, solo link a route legacy.
- Calcoli fiscali: KPI da `GestioneFatturazione.statistiche(anno)`; nessun calcolo React canonico.
- Provider pagamento: nessuna configurazione provider nella lista.
- Webhook: assenti.
- Dati sensibili: non esposti dal bridge; dati studio fiscali non serializzati.
- Esito: sbloccabile come archivio React read-only con link legacy per dettagli, PDF, XML, export e stati.

## /fatturazione/nuova

- Handler legacy: `web/blueprints/fatturazione.py`
- Funzione: `nuova`
- Template: `web/templates/fatturazione/form.html`
- Repository/manager: `get_clienti`, `get_fascicoli`, `get_fatturazione`, `get_preventivi`
- Permessi: sessione Flask richiesta tramite `_richiedi_login`; nessun `ha_permesso` specifico nel legacy.
- Form presenti: form parcella con cliente, pratica, date, voci, opzioni fiscali, note e campi di contesto.
- POST presenti: `POST /fatturazione/nuova` crea parcella con `GestioneFatturazione.crea`.
- Action form: `/fatturazione/nuova`.
- Method form: `post`.
- CSRF: gestito dal form HTML standard e dal meta CSRF della shell React se presente.
- Download/export: assenti nel GET.
- PDF/XML: assenti nel GET; produzione documentale dopo creazione resta su route legacy.
- Calcoli fiscali: legacy esegue calcolo nel modello `pct.fatturazione.Parcella`; React non replica anteprima o formule.
- Provider pagamento: assenti.
- Webhook: assenti.
- Dati sensibili: il legacy legge dati studio fiscali da config durante il POST; il bridge React non li espone.
- Esito: sbloccabile solo come GET React con `LegacyPostForm` verso il POST legacy.

## /fatturazione/*

- Handler legacy: `web/blueprints/fatturazione.py`
- Funzioni: `da_preventivo`, `dettaglio`, `cambia_stato`, `elimina`, `pdf`, `xml_fattura_pa`, `ajax_fascicoli`
- Template: `fatturazione/dettaglio.html`, output PDF/XML, JSON AJAX.
- Repository/manager: `get_fatturazione`, `get_clienti`, `get_fascicoli`, `get_pagamenti`, `get_preventivi`
- Permessi: sessione Flask richiesta.
- Form presenti: cambio stato, eliminazione, creazione link pagamento e azioni dettaglio.
- POST presenti: stato parcella, eliminazione, creazione link pagamento.
- Action form: `/fatturazione/<id>/stato`, `/fatturazione/<id>/elimina`, `/fatturazione/<id>/link-pagamento`.
- Method form: `post`.
- CSRF: preservato dal legacy.
- Download/export: PDF e XML via route dedicate; CSV su blueprint export.
- PDF/XML: presenti e generati dal legacy.
- Calcoli fiscali: dettaglio e documenti usano il modello backend e generatori esistenti.
- Provider pagamento: link pagamento legacy collegato al pannello provider.
- Webhook: non su dettaglio, ma correlato al dominio pagamenti.
- Dati sensibili: documenti fiscali e dati studio completi restano nel legacy.
- Esito: deve restare legacy; il gate blocca ogni sottopercorso diverso da `/fatturazione/nuova`.

## /incassi-pagamenti

- Handler legacy: `web/blueprints/terminology_aliases.py`
- Funzione: `incassi_pagamenti`
- Template: nessuno; redirect a `/impostazioni/pagamenti`.
- Repository/manager: nel nuovo bridge read-only `get_fatturazione`, `get_pagamenti`, `get_clienti`.
- Permessi: sessione Flask richiesta come legacy.
- Form presenti: nessuno nella route alias.
- POST presenti: nessuno sulla route exact.
- Action form: non applicabile.
- Method form: non applicabile.
- CSRF: non applicabile.
- Download/export: assenti.
- PDF/XML: assenti.
- Calcoli fiscali: KPI incassi letti da statistiche backend; nessuna formula React.
- Provider pagamento: stato aggregato enabled/disabled/label, senza configurazioni.
- Webhook: restano sulle route `/webhooks/*` legacy.
- Dati sensibili: non serializzati; link checkout pubblici non esposti.
- Esito: sbloccabile come dashboard React sicura senza form provider.

## /impostazioni/pagamenti

- Handler legacy: `web/blueprints/pagamenti.py`
- Funzione: `impostazioni_pagamenti`
- Template: `web/templates/pagamenti/impostazioni.html`
- Repository/manager: `web.helpers.get_pagamenti`
- Permessi: sessione Flask richiesta.
- Form presenti: configurazione provider Stripe, PayPal, Satispay, SumUp e bonifico.
- POST presenti: `POST /impostazioni/pagamenti` salva configurazione provider.
- Action form: `/impostazioni/pagamenti`.
- Method form: `post`.
- CSRF: preservato dal legacy.
- Download/export: assenti.
- PDF/XML: assenti.
- Calcoli fiscali: assenti.
- Provider pagamento: configurazioni complete e credenziali operative.
- Webhook: configurazione collegata a `/webhooks/stripe`, `/webhooks/paypal`, `/webhooks/satispay`, `/webhooks/sumup`.
- Dati sensibili: provider, chiavi, credenziali bancarie e webhook.
- Esito: deve restare legacy; React mostra solo link a `/impostazioni/pagamenti?_legacy=1`.

## /preventivi

- Handler legacy: `web/blueprints/preventivi.py`
- Funzione principale: `lista`
- Template: template preventivi e wizard dedicati.
- Repository/manager: `get_preventivi`, `get_clienti`, `get_fascicoli`, servizi workflow commerciale.
- Permessi: sessione Flask richiesta.
- Form presenti: nuovo preventivo, wizard, stati, conferimento, eliminazione e workflow.
- POST presenti: molteplici POST auditati per preventivo e mandato.
- Action form: route sotto `/preventivi/*`.
- Method form: `post`.
- CSRF: preservato dal legacy.
- Download/export: PDF preventivo e documenti collegati.
- PDF/XML: PDF presenti.
- Calcoli fiscali: tariffario, compensi, fasi e conferimento incarico.
- Provider pagamento: collegamenti indiretti al ciclo incasso.
- Webhook: assenti.
- Dati sensibili: dati mandato e preventivi completi.
- Esito: deve restare legacy in questa tranche.

## /compensi-forensi

- Handler legacy: `web/blueprints/terminology_aliases.py`
- Funzione: `compensi_forensi`
- Template: nessuno; redirect a `/tariffario`.
- Repository/manager: motore tariffario tramite route `/tariffario`.
- Permessi: eredita il legacy tariffario.
- Form presenti: sul tariffario.
- POST presenti: sul tariffario.
- Action form: `/tariffario`.
- Method form: `post`.
- CSRF: preservato dal legacy.
- Download/export: generazione preventivo collegata.
- PDF/XML: non direct.
- Calcoli fiscali: motore compensi forensi completo.
- Provider pagamento: assenti.
- Webhook: assenti.
- Dati sensibili: contesto pratica e valori economici.
- Esito: deve restare legacy.

## /tariffario

- Handler legacy: `web/bootstrap/tariffario_routes.py`
- Funzione: `tariffario`
- Template: `web/templates/tariffario.html`
- Repository/manager: `pct.tariffario`, `pct.tariffario_catalogo`, `web.services.tariffario_runtime`
- Permessi: sessione Flask e route legacy.
- Form presenti: calcolo compensi, fasi, valore controversia, parametri e integrazione preventivo.
- POST presenti: calcolo tariffario e generazione flussi collegati.
- Action form: `/tariffario`.
- Method form: `post`.
- CSRF: preservato dal legacy.
- Download/export: collegamenti a preventivo/documenti generati.
- PDF/XML: non direct nella route base.
- Calcoli fiscali: motore D.M. 55 e tabelle normative.
- Provider pagamento: assenti.
- Webhook: assenti.
- Dati sensibili: valori causa, contesto pratica e log calcolo.
- Esito: deve restare legacy; non sostituibile da dashboard React.

## /export/fatturazione.csv

- Handler legacy: `web/blueprints/export_csv.py`
- Funzione: `fatturazione_csv`
- Template: nessuno, response CSV.
- Repository/manager: `get_fatturazione`, `get_clienti`.
- Permessi: sessione Flask richiesta.
- Form presenti: assenti.
- POST presenti: assenti.
- Action form: non applicabile.
- Method form: GET download.
- CSRF: non richiesto.
- Download/export: CSV legacy.
- PDF/XML: assenti.
- Calcoli fiscali: importi gia' presenti nel modello.
- Provider pagamento: assenti.
- Webhook: assenti.
- Dati sensibili: esportazione economica completa.
- Esito: deve restare legacy; il gate non intercetta file `.csv`.
