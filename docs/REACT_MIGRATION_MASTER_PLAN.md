# Migrazione progressiva Flask + React

## Principio operativo

La migrazione a React non sostituisce la UI Jinja in blocco. Flask resta backend,
source of truth, motore di permessi, tenant, audit e repository. React entra come
shell separata su `/app-v2` e ogni pagina viene attivata solo dopo parità
funzionale verificata.

Regola di rilascio: una pagina React può sostituire la pagina storica solo se
supera API reali, test backend, test frontend, test responsive desktop/tablet/mobile,
accessibilità, tenant/RBAC e rollback immediato.

## Fase 0 - Baseline

- Inventariare route Jinja, blueprint, API, menu e flussi critici.
- Salvare screenshot baseline per desktop `1440px`, tablet `768px`, mobile `390px`.
- Eseguire smoke test autenticati su Panoramica, Regia Operativa, Ricerca Studio,
  Fascicoli, Scadenziario, Preventivi, Fatturazione, Servizi Telematici, Lex e
  Impostazioni.
- Bloccare l'uso di dati demo nella shell React.

## Fase 1 - Shell dormiente

- Integrare `frontend/` con Vite, React e TypeScript.
- Servire la build sotto `web/static/react`.
- Esporre `/app-v2` senza modificare le route esistenti.
- Esporre API ponte sotto `/api/v1/ui/*`, protette da sessione o API key.
- Mantenere tutti i flag di sostituzione route a `false`.

## Fase 2 - API contract

Ogni pagina React deve avere prima un contratto API stabile:

- `GET /api/v1/ui/bootstrap`
- `GET /api/v1/ui/dashboard`
- API dominio per fascicoli, clienti, scadenze, documenti, preventivi, parcelle,
  pagamenti, telematico, Lex e impostazioni.

React non legge file JSON e non accede direttamente allo storage. Tutto passa da
servizi Flask già tenant-aware.

## Fase 3 - Design system

- Usare i design token IUSENTRA già presenti in `tokens.json`.
- Mantenere testi visibili in italiano.
- Target touch minimo: `44px`.
- Verificare contrasto, focus visibile, heading order, navigazione tastiera e
  `prefers-reduced-motion`.
- Nessun caricamento esterno non necessario senza consenso.

### Stato Panoramica `/app-v2`

La prima pagina React usa la shell enterprise collegata a `/api/v1/ui/dashboard`:

- sidebar desktop con navigazione lunga scrollabile e drawer sotto `980px`;
- topbar con ricerca, azioni rapide e comandi principali;
- token CSS e TypeScript per colori, spacing, radius, shadow e typography;
- componenti riusabili `Panel`, `KpiCard`, `DossierCard`, `SourceCard`, `Badge`
  e `Button`;
- array dati separati in `frontend/src/data.ts` per KPI, agenda, operativita',
  fascicoli, fonti, scadenze, economia e suggerimenti Lex;
- niente mock operativo: le sezioni leggono i dati reali disponibili e usano
  stati vuoti espliciti quando il repository non contiene record.

### Stato Ricerca Studio `/app-v2/ricerca-studio`

La seconda pagina React e' una route separata dalla Panoramica e riusa la shell
globale senza annidarsi nel contenuto dashboard:

- dati collegati all'indice reale `/api/global-search`;
- filtri per fascicoli, clienti, scadenze, documenti, comunicazioni, economia e
  telematico;
- stato indice con totale elementi, FTS5 e ultimo sync;
- azione `Reindicizza` collegata al backend esistente;
- anteprima risultato con azioni contestuali `Apri`, `Chiedi a Lex`, `Vai al
  fascicolo` e `Copia link`;
- shortcut `Ctrl/Cmd + K`, `Esc`, frecce e `Invio`;
- nessun `mockResults` nella pagina React.

### Stato Regia Operativa `/app-v2/regia-operativa`

La Regia Operativa e' una pagina React autonoma, collegata alla voce primaria
della nav e separata dalla Panoramica:

- usa i dati reali già esposti dal bridge dashboard;
- mostra azioni operative, agenda da presidiare, fascicoli prioritari,
  comunicazioni recenti e suggerimenti Lex;
- mantiene il link alla regia storica `/workspace-intelligente` come versione
  completa e fallback operativo;
- non reinserisce pannelli di regia dentro la Panoramica React.

### Stato Agenda `/app-v2/agenda`

La pagina Agenda React e' collegata alla nav della shell, ma non sostituisce la
pagina storica `/agenda`:

- dati reali da `/api/v1/ui/agenda`, normalizzati da agenda e scadenziario;
- contratto in sola lettura con `mock_fallback=false` e route storiche ancora attive
  per dettagli, creazione, import ed export;
- filtri per tipologia, ricerca testuale, vista giorno/settimana/mese
  e KPI su oggi, settimana, udienze, scadenze e alert;
- calendario responsive con slot orari cliccabili in giorno/settimana, griglia
  mese cliccabile e drag & drop con salvataggio sugli appuntamenti agenda reali
  tramite `/api/agenda/<id>/sposta`;
- briefing operativo, salute sincronizzazione calendari e widget Lex
  trascinabile e apribile anche su mobile;
- collegamento nav su `/app-v2/agenda` per ogni accesso React alla pagina.

### Stato Nuovo Appuntamento `/app-v2/agenda/nuovo`

La pagina React di creazione appuntamento resta separata dall'Agenda e usa il
backend storico come punto di scrittura:

- salvataggio nativo su `POST /agenda/nuovo`, senza nuova API obbligatoria;
- precompilazione da query `data`, `ora`, `id_cliente` e `from_cliente`;
- autocomplete clienti da `/api/clienti` e dettaglio cliente da
  `/api/clienti/<id_cliente>`;
- normalizzazione del codice fiscale in maiuscolo;
- preset rapidi per udienza, consultazione, riunione, deposito, scadenza e
  altro, chip uffici giudiziari, anteprima e checklist qualita';
- controllo sovrapposizioni su `/api/agenda`;
- Lex AI contestuale con icona flottante, posizione persistita e azione
  `Completa titolo`.

### Stato Fascicoli `/app-v2/fascicoli`

La pagina Fascicoli React resta in sola lettura e non sostituisce ancora le route storiche:

- dati da `/api/v1/ui/fascicoli`, normalizzati dai repository reali fascicoli e scadenziario;
- KPI su attivi, in corso, da archiviare, archiviati, prossime scadenze e documenti da classificare;
- ricerca, filtri per tipo/stato, filtri avanzati per ufficio, alert e ordinamento;
- tabella desktop e card mobile responsive, con azioni Apri/Modifica sulle route storiche;
- pannello operativo con controlli qualità, alert, integrazioni telematiche e Lex AI trascinabile.


### Stato Fascicoli Suite `/app-v2/fascicoli`

La suite Fascicoli React ricostruisce le superfici storiche senza sostituire ancora le route Jinja:

- `Tutti i Fascicoli`, con KPI, ricerca, filtri tipo/stato, filtri avanzati, scadenze imminenti, tabella desktop e card mobile;
- `Nuovo Fascicolo` e `Modifica`, con gli stessi campi del form storico: dati principali, parti, ufficio, RG, anno, sezione, giudice, valore, workflow preventivo/conferimento, avvocati, note e contesto correzione;
- `Archivio`, con ricerca, esito, data archiviazione, ZIP, dettaglio e ripristino;
- `Apri Fascicolo`, con cabina completa: profilo, documenti, import portale, attività, udienze/scadenze, depositi/cancelleria, istanze, avanzamento, gestione stato, definizione, archiviazione, ripristino, PDF, ZIP, economico, conformita, telematico, cliente e soggetti;
- `Esporta`, con builder per PDF/CSV, preset e collegamenti ai PDF singoli;
- Lex AI flottante e trascinabile in ogni superficie della suite.

Tutte le azioni di scrittura restano instradate alle route Flask storiche già auditate, mentre le API React `/api/v1/ui/fascicoli*` sono in sola lettura e consapevoli di tenant e sessione.

## Fase 4 - Ordine di migrazione

1. Panoramica e shell globale.
2. Ricerca Studio.
3. Regia Operativa.
4. Agenda.
5. Nuovo Appuntamento.
6. Scadenziario.
7. Clienti e Anagrafiche.
8. Fascicoli in sola lettura.
9. Documenti e upload.
10. Preventivi e Conferimenti.
11. Parcelle, Fatture, Incassi e Pagamenti.
12. Lex AI.
13. Sito Studio Builder.
14. Servizi Telematici, PDP/PST/PAT/PTT, Local Signer e PEC.
15. Admin e Impostazioni.

Le aree telematiche e di firma restano ultime perché hanno vincoli di compliance,
Local Signer, audit, canali separati e conferma consapevole dell'avvocato.

## Gate per ogni pagina

- API con dati reali, nessun mock operativo.
- UI in sola lettura prima delle azioni di scrittura.
- Azioni di scrittura protette da CSRF/sessione, tenant e RBAC.
- Test unitari backend.
- Test frontend `npm run test`, `npm run typecheck`, `npm run build`.
- Test e2e/smoke desktop, tablet e mobile.
- Verifica accessibilità.
- Flag di rollback.
- Documentazione aggiornata.

## Rollback

Le route Jinja storiche restano sempre disponibili. Lo switch a React avviene solo
via feature flag e può essere disattivato senza migrazione dati.

## Comandi

```powershell
cd D:\legale\IUSENTRA\frontend
npm ci
npm run test
npm run typecheck
npm run build
```

```powershell
cd D:\legale\IUSENTRA
python -m pytest tests/test_react_shell.py -q
```
