# Legal UI coherence report

Generato: 2026-05-08T10:03:02.066Z

Aggiornamento 2026-05-10: per la tranche 2.214.0 sono stati verificati in
browser Docker locale Redazione Atti, Template Atti, Statistiche, Ricerca
Legale, News, Archivio Giurisprudenza, Strumenti Forensi, Strumenti Operativi,
Controlli Atti, Sito Studio Contatti, dettagli email PEC/ordinaria e Database.
Le superfici usano card operative compatte, dettaglio in pagina, testi italiani
per lo studio e nessuna dicitura tecnica visibile tra quelle vietate.

Aggiornamento 2026-05-11: `/fascicoli/nuovo` 2.216.0 usa pannelli
collassabili coerenti con la shell IUSENTRA, `Pratiche collegate` nel blocco
iniziale sotto `Personalizzabile`, `Fascicolo Veloce` con multicaricamento
documenti/email EML e titolo utente `Presidio deposito assistito` al posto di
diciture tecniche. Browser Docker desktop/tablet/mobile: nessun overflow,
nessun errore console e nessun termine tecnico vietato visibile.

Aggiornamento 2026-05-11: `/fascicoli/nuovo` 2.216.5 mantiene la stessa
grafica IUSENTRA e rende il flusso veloce piu' guidato: selezione cliente con
scheda di riepilogo reale, soggetto controparte gia' censito, inserimento
controparte con identificativo richiesto, creazione facoltativa della scheda
soggetto e campo `Autorita' giudiziaria` alimentato dal registro uffici. I
messaggi di blocco usano linguaggio operativo per lo studio e il salvataggio
veloce apre il deposito assistito.

## Componenti UI creati

- IconButton
- Card
- ActionCard
- CompactCard
- Workspace
- WorkspaceHeader
- WorkspaceGrid
- SplitLayout
- ThreeColumnLayout
- FourColumnLayout
- Drawer
- Modal
- Accordion
- ResponsiveTable
- FilterBar
- AdvancedFilters
- SearchInput
- Select
- DateField
- TextField
- TextArea
- StatusBadge
- LegalStatusBadge
- Timeline
- ErrorState
- PermissionDeniedState
- Toast
- ConfirmDialog
- StickyActionBar
- QuickActionBar
- DetailPanel
- SummaryPanel
- NextActionPanel
- InlineAlert

## Workspace aggiornati

- regia
- fascicoli
- anagrafiche
- agenda
- mandato
- documenti
- telematico
- comunicazioni
- amministrazione
- lex

## Layout e filtri

- shell desktop/tablet/mobile
- split layout
- three column layout
- four column layout
- responsive grid
- sticky action bar
- drawer/mobile bottom navigation

Filtri avanzati: FilterBar, AdvancedFilters, SearchInput, Select, DateField
Card operative: ActionCard, CompactCard, KpiCard esistente, DetailPanel, SummaryPanel, NextActionPanel

## Test

- python -m pytest -q: timeout - Interrotto dal timeout locale dopo circa 45 minuti; nessun verde completo dichiarabile.
- npm test: passed - Contratti React verificati.
- npm run typecheck: passed - tsc --noEmit completato.
- npm run build: passed - Vite build completata; asset generati in web/static/react.
- node scripts/react-migration/run-full-react-migration.mjs: passed - Audit, anti-mascheramento e check Full React passati.
- node scripts/react-migration/run-legal-ui-checks.mjs: passed - Check UI legale, responsive e anti-Bootstrap passati.

## Rischi residui

- python -m pytest -q non completato entro timeout
- frontend/src/App.tsx resta monolitico e va spezzato in tranche successive
- alcune route restano legacy_operational per scelta del manifest e per workflow profondi/documentali/telematici ancora non ricostruiti
- verifica browser visuale eseguita il 2026-05-09 sulle route promosse `/deposito/checklist`, `/strumenti-legali` e `/strumenti-operativi` in desktop/tablet/mobile; nessun testo tecnico visibile tra `payload`, `backend`, `frontend`, `runtime`, `json_api`, `undefined`, `null`, `todo`, `sample`
