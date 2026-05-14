# Legal UI coherence report

Generato: 2026-05-08T10:03:02.066Z

Aggiornamento 2026-05-14: `/notifiche-legali` 2.236.0 rende visibile la fase
operativa dopo `Controlla relata`, `Controlla prova deposito` e `Prepara
comunicazione`. Il pannello esito mostra blocchi, file previsti, pacchetto
prova con SHA-256 e testo generato; la selezione documenti dal fascicolo e'
multi-scelta e alimenta automaticamente l'elenco allegati della relata. I nuovi
campi obbligatori restano presentati in linguaggio da studio legale, senza
termini da sviluppatore.

Aggiornamento 2026-05-12: `Template Atti` 2.218.0 espone catalogo e
compilatore come superfici operative governate: filtri per stato Cartabia,
area processuale, dati completi/incompleti e canale, chip di precompilazione,
preview timbro studio e dettaglio dei controlli. Il linguaggio resta rivolto
allo studio, con stati `Da verificare`, `Pronto dopo controllo` o equivalenti
professionali, senza promesse statiche di conformita' piena e senza dati di
esempio hardcoded.

Aggiornamento 2026-05-12: `Impostazioni -> Calendari` 2.217.0 diventa un
pannello operativo per collegare Google, Outlook/Microsoft 365, iCloud/CalDAV,
WebCal/ICS e ambiente di prova locale. La UI usa sezioni compatte, icone
Lucide, stati e azioni reali per allineamento, pausa, scollegamento e conflitti;
non mostra token, password o lessico da sviluppatore. Smoke Chrome
desktop/tablet/mobile confermato senza overflow documentale o errori console.

Aggiornamento 2026-05-12: `/notifiche-legali` 2.216.8 aggiunge la
compilazione assistita da IUSENTRA. Il blocco iniziale propone pratica,
destinatario e documento letti da fascicoli, soggetti e documenti reali, con
icone Lucide e selettori compatti. I dati non disponibili restano vuoti o da
verificare, mentre l'interfaccia evita termini tecnici e conserva il controllo
professionale su PEC, attestazioni, firma e invio.

Aggiornamento 2026-05-12: `/notifiche-legali` 2.216.7 introduce una pagina
operativa compatta per separare notifica ex L. 53/1994, deposito prova e
comunicazione cliente. La UI usa card azionabili, icone Lucide, oggetto PEC
bloccato, campi di controllo per pubblico elenco/firma/ricevuta completa e
pannello laterale con esiti, senza usare lessico da sviluppatore o dati demo.

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

## Aggiornamento 2.236.3 - 2026-05-14

- `/profilo`, `/agenda/importa`, `/agenda/nuovo`, compose PEC/SMTP, portali PDP/PAT/SIGIT e scadenziario usano testi italiani operativi, icone Lucide e card/azioni coerenti con il design system IUSENTRA.
- I campi derivati in Agenda sono mostrati come dati professionali dello studio: codice fiscale, procedimento, ufficio e avvocato responsabile; nessun fallback demo o mock.
- Scadenziario sostituisce `repository_reali` con `dati dello studio` e mantiene azioni leggibili: filtra, completa, elimina, apri dettaglio, export e Lex.
- Le liste Clienti/Soggetti/Fascicoli conservano densita' tabellare ma aggiungono scrollbar superiore per l'uso desktop senza cambiare la disposizione mobile.
