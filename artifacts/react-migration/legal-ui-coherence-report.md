# Legal UI coherence report

Generato: 2026-05-08T10:03:02.066Z

## Aggiornamento 2.249.14

- Template Atti usa linguaggio operativo italiano per studio legale: `Controllo finale`, `Esporta DOCX / PDF / RTF`, `Firma documento`, `Compilazione multipla`, `Inserisci campo` e `Documento salvato nel fascicolo come bozza modificabile`.
- Il workspace replica la struttura professionale richiesta: catalogo template, editor documento, tab Campi/Stile/Lex/Fonti/Controlli/Export, pannello revisione testo, timbro studio completo e spostabile, font registry e preset.
- Le azioni non sono decorative: cambio modello, campi fascicolo, Guida Pratica, Lex diff, import, export, compilazione multipla e firma sono state cliccate nel browser reale; nessun testo tecnico vietato o lingua inglese visibile nel flusso verificato.

Aggiornamento 2026-05-25: hotfix preset grafico operativo 2.248.56. Le pagine
Studio richieste sono state rivalutate contro il preset IUSENTRA e rese più
coerenti nelle dimensioni dei controlli: Fatturazione, Compensi Forensi,
Redazione Atti e Giurisprudenza/Ricerca non presentano più campi o pulsanti
sotto soglia su tablet e mobile. Il dettaglio fascicolo resta personalizzato,
ma il modal di eliminazione documento usa una struttura professionale,
contenuta e leggibile, con azioni chiaramente separabili e senza taglio del
testo.

Aggiornamento 2026-05-22: preset grafico globale 2.248.12. IUSENTRA dispone
di un vocabolario unico per superfici operative, support rail, filtri, contesto
filtri, DataSurface, paginazione, card e stati vuoti. Fascicoli è il caso
pilota: Cabina fascicoli, Alert operativi e Azioni rapide restano pannelli di
supporto; il contenuto principale è nella DataSurface allineata alla rail, con
linguaggio da studio legale e senza testi tecnici vietati. `/sito-studio/builder`
resta escluso per preservare il suo editor visuale.

Aggiornamento 2026-05-16: `/ricerca-legale/mediazione` 2.243.4 diventa un
registro professionale consultabile dentro IUSENTRA. La pagina mostra metriche,
mappa contesto, 5 filtri, tabella compatta con 80 risultati renderizzati e
schede fonte con contesto/uso pratico; i link ministeriali restano verifica
finale, non contenuto principale. Audit desktop/tablet/mobile verde senza
overflow, form POST HTML o lessico da sviluppatore.

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

## Aggiornamento 2.236.4 - 2026-05-15

- Revisione UI/UX severa completata su 46 route operative con Chrome CDP desktop/mobile: report `artifacts/react-migration/visual-2.236.4/visual-load-audit.md`, 92/92 controlli OK.
- Corrette incoerenze comuni: testi lunghi in card/menu, bottoni icona senza label, drawer/modali senza focus trap, tabelle non leggibili su mobile e stati di caricamento non sufficientemente governati.
- Ripuliti testi da sviluppatore in admin, AI locale, Lex assistant e compensi: la UI mostra linguaggio professionale per studio legale, date italiane dove toccate e messaggi errore leggibili.
- Le correzioni CSS restano nel design system: wrapping/clamp, action row responsivi, data table a card mobile e focus ring visibile; nessuna isola grafica nuova o palette estranea.

## Aggiornamento 2.236.5 - 2026-05-15

- Ricerca Studio e Controlli Atti hanno microcopy ulteriormente allineato alla regola "avvocato, non sviluppatore": niente sigle tecniche, tempi macchina, scorciatoie esposte o riferimenti al browser.
- Il badge di stato ricerca, il pulsante di aggiornamento e gli stati vuoti/loading usano espressioni professionali: `Indice avanzato`, `Aggiorna ricerca`, `archivio reale`, `postazione in uso`.
- L'audit visuale non segnala piu' falsi positivi sulle pagine con molti pulsanti e pochi link testuali; la coerenza viene valutata su azioni reali, non solo su collegamenti.
- Verifica Chrome CDP 2.236.5: audit completo con 91/92 OK e retry mirato `/soggetti/nuovo` mobile OK; nessun avviso residuo sulle rotte corrette.

## Aggiornamento 2.239.1 - 2026-05-15

- Sito Studio Builder Pro adotta un linguaggio da prodotto professionale: `Setup`, `Pagine`, `Blocchi`, `Contenuti`, `Aspetto`, `Media`, `SEO`, `Privacy`, `AI` e `Pubblica` raggruppano funzioni reali senza trasformare il pannello in una demo.
- La grafica replica il riferimento B: topbar scura, panel compatto, tab verticali con icone lineari, preview live dominante, card e controlli densi ma leggibili.
- I controlli avanzati non sono decorativi: font, dimensioni, colori, effetti, allineamenti, formattazione e media modificano realmente la preview e sono persistiti nel tema del sito pubblico.
- Verifica CDP: nessun overflow, footer live visibile, menu tablet/mobile presente, toolbar testo e resize funzionanti; screenshot in `artifacts/react-migration/visual-2.239.1-sito-studio-builder/`.

## Aggiornamento 2.239.3 - 2026-05-16

- `/legal-intelligence/` usa il titolo `Osservatorio Legale` e separa governo fonti/news/registri dalla ricerca puntuale.
- `/ricerca-legale` presenta una scheda fonte professionale con estratto, contesto, uso pratico e attendibilita', cosi l'avvocato non vede piu' una lista di accessi esterni.
- Card, mappa del contesto, tab e filtri usano icone Lucide, microcopy italiano e densita' coerente con il design system IUSENTRA.
- Verifica CDP desktop/mobile: 8/8 controlli OK sulle route Legal Intelligence, nessun testo tecnico vietato, nessun overflow e nessun form POST HTML.

## Aggiornamento 2.248.56 - 2026-05-25

- Amministrazione, Utenti, Profili e Permessi, Registro Attività, Database, Registro GDPR, Sito Studio Contatti e Sito Studio sono stati verificati come superfici React operative, con preset IUSENTRA attivo, contenuti reali e microcopy professionale.
- La verifica browser in-app autenticata ha coperto desktop, tablet e mobile con scroll alto/meta/fondo: 81 snapshot verdi, nessun errore console nuovo, nessun testo tecnico vietato e nessun controllo con testo o icona tagliati.
- Il preset condiviso ora impone CTA e link operativi da 44 px anche quando la regola specifica di pagina è più forte; Database usa una resa mobile a schede invece della tabella larga.
