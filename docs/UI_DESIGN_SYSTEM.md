# IUSENTRA UI Design System

Questo documento definisce il design system interno IUSENTRA per le superfici React/Vite. L'obiettivo e' migliorare in modo progressivo la qualita' visiva del gestionale senza copiare template completi sopra il prodotto e senza perdere rotte, API, validazioni, permessi o workflow gia' presenti.

## Librerie integrate

- `shadcn/ui`: base per componenti React/Tailwind accessibili e modificabili nel repository. I componenti vivono in `frontend/src/components/ui/`.
- `lucide-react`: catalogo unico per le icone applicative. Evitare emoji, simboli isolati e mix di icon set.
- `class-variance-authority`, `clsx`, `tailwind-merge`: composizione governata di varianti, classi e override Tailwind.
- `radix-ui`: primitive accessibili usate dai componenti shadcn generati.
- `tw-animate-css`: animazioni compatibili con la configurazione Tailwind attuale.

Tremor, Recharts e Framer Motion non sono dipendenze obbligatorie di base. Vanno introdotte solo quando una pagina richiede davvero grafici, KPI avanzate o micro-interazioni selezionate.

## Struttura

- `frontend/src/components/ui/`: componenti shadcn generati e adattati.
- `frontend/src/components/iusentra/`: componenti applicativi riutilizzabili del gestionale.
- `frontend/src/components/layout/`: bridge layout esistenti verso il nuovo sistema.
- `frontend/src/components/app/`: entrypoint e provider condivisi per superfici applicative.
- `frontend/src/design/iusentraTokens.ts`: catalogo icone, toni semantici e mappa aree legali.
- `frontend/src/styles/iusentra-design-system.css`: token CSS, superfici, card, stati, focus ring e responsive.

Non duplicare componenti gia' presenti. Se una pagina usa `frontend/src/ui/*`, aggiornare il wrapper condiviso invece di riscrivere lo stesso pattern nella pagina.

## Componenti IUSENTRA

- `IusPageShell`: contenitore pagina responsive, con spaziature coerenti.
- `IusAppSidebar`: sidebar applicativa con icone Lucide e stato attivo.
- `IusTopBar`: barra superiore con ricerca, azioni rapide e stato utente.
- `IusSectionHeader`: titolo sezione, eyebrow, descrizione, azioni e icona.
- `IusMetricCard`: KPI e metriche operative.
- `IusActionCard`: card azionabile con stato e CTA.
- `IusStatusBadge`: badge di stato normalizzato.
- `IusEmptyState`: stato vuoto professionale con azione opzionale.
- `IusFormSection`: sezione form con intestazione e contenuto.
- `IusCollapsiblePanel`: pannello espandibile per pagine complesse.
- `IusDataTableShell`: shell tabellare responsive con toolbar e stato vuoto.
- `IusLoadingState`, `IusErrorState`, `IusSuccessState`, `IusRetryPanel`: stati applicativi professionali senza stacktrace o messaggi tecnici grezzi.
- `IusSkeletonTable`, `IusSkeletonCard`: caricamenti stabili per tabelle e card operative.
- `IusWizardStepper`: stepper compatto per wizard deposito, preventivi e percorsi guidati.
- `IusCompliancePanel`: pannello trasparente per verificato, non verificato, fonte mancante, fallback e revisione manuale.
- `IusDocumentStatusBadge`: badge documentali per OCR, PDF/A, firma, deposito e validazione non eseguita.
- `IusChannelCard`: card canale per PST/PDP/PAT/PTT/SIGP e import assistito, con stato, anomalie e azione primaria.
- `IusMessageList`: lista comunicazioni/PEC con stato letto, allegati, fascicolo collegato e canale.
- `IusLegalIcon`: wrapper unico per dimensioni, tono e accessibilita icone.
- `LexFloatingButton`: pulsante flottante per Lex AI dove previsto.
- `LexPanel`: drawer/pannello Lex con contesto, fonti, documenti usati, modalita operative e stati di contesto insufficiente.

## Preset grafico globale

Dal 22 maggio 2026 le pagine operative React devono comporre il preset documentato in [UI_PRESET_IUSENTRA.md](UI_PRESET_IUSENTRA.md): `IusentraRoutePresetFrame`, `IusentraPageShell`, `IusentraMainArea`, `IusentraMainSurface`, `IusentraSupportRail`, `IusentraPanelCard`, `IusentraDataSurface`, `IusentraFiltersBar`, `IusentraContextFilters`, `IusentraPaginationBar`, `IusentraActionCard` e `IusentraEmptyState`.

Il preset è applicato dalla shell React a tutte le pagine, con esclusione esplicita di `/sito-studio/builder`. `IusentraRoutePresetFrame` normalizza anche le griglie locali già presenti su Agenda, Clienti/Soggetti, PEC, Scadenziario, Telematico, Preventivi, Template atti e amministrazione. Le pagine con tabelle o liste devono usare `IusentraDataSurface` con footer/paginazione ancorato in basso; le pagine con rail laterale devono usare `IusentraMainArea` e `IusentraSupportRail`, così la superficie principale si allinea almeno all'altezza della colonna di supporto.

Lo stesso frame impone la sequenza `IUSENTRA_PAGE_SEQUENCE` su ogni superficie operativa: Header pagina, Sottotitolo operativo, Azioni principali, Filtri, Contesto filtri / riepilogo, Contenuto principale, Paginazione / footer, Sidebar di supporto. Le sezioni vengono marcate con `data-iusentra-sequence-slot`, ordinate dal CSS globale e verificate dal gate `audit-ui-preset-sequence.mjs`.

## Token colore

La palette deve restare istituzionale e leggibile:

- Blu notte: superfici di navigazione, intestazioni e azioni primarie.
- Oro tenue: accenti legali premium, highlight e stati importanti non distruttivi.
- Grigi neutri: testo secondario, bordi, sfondi funzionali.
- Bianco / avorio leggero: superfici operative e aree di lettura.

Usare i token CSS in `iusentra-design-system.css` e le classi semantiche `ius-tone-*`. Evitare palette casuali, gradienti vistosi, shadow pesanti e pagine dominate da una sola tinta.

## Icone

Usare sempre `lucide-react` tramite `IusLegalIcon`, `iusLegalIcons` o il registry `frontend/src/design/icons.tsx`:

- Fascicoli: `FolderOpen`, `FileText`, `BriefcaseBusiness`
- Clienti/Soggetti: `UserRound`, `UsersRound`, `Contact`
- Agenda/Scadenze: `CalendarDays`, `Clock`, `Bell`
- Telematico/PCT/PDP/PAT/PTT: `Landmark`, `Send`, `UploadCloud`, `ShieldCheck`
- Documenti: `FileText`, `Files`, `FileSignature`
- Tariffario/Preventivi: `Calculator`, `ReceiptText`, `Euro`
- Sicurezza/Privacy: `LockKeyhole`, `ShieldCheck`, `Fingerprint`
- Lex AI: `Bot`, `Sparkles`, `MessageCircle`
- Ricerca: `Search`
- Alert/Conformita: `AlertTriangle`, `CheckCircle2`, `Info`

Dimensioni consigliate: 18 px per toolbar e tabella, 20 px per card e sidebar, 24 px per header. Il colore va governato da CSS/token, non da valori hardcoded sparsi.

## Pattern pagina

Ogni pagina operativa deve comporre:

1. `IusPageShell`
2. `IusSectionHeader`
3. azioni principali o card operative con `IusActionCard` / `IusMetricCard`
4. toolbar o filtri con controlli reali
5. contesto filtri, riepilogo o stato operativo
6. contenuto principale con `IusDataTableShell`, `IusentraDataSurface` o pannelli collassabili
7. paginazione o footer agganciato alla superficie dati
8. sidebar di supporto solo per riepiloghi, alert, checklist e azioni secondarie
9. stati vuoti, errore, successo e loading espliciti
10. Lex AI flottante solo dove previsto dalla superficie

Esempio sintetico:

```tsx
<IusPageShell>
  <IusSectionHeader
    eyebrow="Fascicoli"
    title="Cabina operativa"
    description="Stato, prossime azioni e anomalie del fascicolo."
    area="fascicoli"
    actions={<Button>Nuova attivita</Button>}
  />
  <IusDataTableShell
    title="Documenti recenti"
    columns={columns}
    rows={documents}
    emptyState={<IusEmptyState area="documenti" title="Nessun documento" />}
  />
</IusPageShell>
```

## Form e toolbar

- Usare `IusFormSection` per raggruppare campi correlati.
- Usare `Button` shadcn per azioni, con `type="button"` implicito quando non e' submit.
- Preferire icone Lucide nei pulsanti compatti e testo italiano chiaro nelle CTA primarie.
- Date e ore devono arrivare gia' formattate con i filtri condivisi o funzioni di formato italiane esistenti.
- Non mostrare dati demo, nomi fittizi, ruoli inventati o conteggi non derivati da API/sessione/repository.
- Le schede a tab devono essere compatte e non devono mai generare colonne vuote, pannelli schiacciati o contenuto principale spostato fuori asse. Dopo ogni modifica a tab/form, verificare la route renderizzata su desktop e mobile.
- Le impostazioni operative devono restare in un unico pannello React: `Pagamenti`, `Notifiche`, `Backup` e `Calendari` sono tab di `Impostazioni`, non pagine tecniche separate. Gli alias `/impostazioni/pagamenti`, `/notifiche`, `/notifiche-whatsapp`, `/backup`, `/impostazioni/calendario` e `/sincronizzazione-calendari` devono aprire la stessa esperienza coerente.
- La coerenza grafica vale per tutto IUSENTRA: shell, densita', tab, card operative, badge, pulsanti, icone Lucide, spaziature, stati e responsive devono restare allineati tra Studio, Impostazioni, Backup, Calendari, Pagamenti, Notifiche e le altre superfici. Una pagina gia' React non va accettata se appare come isola grafica o usa vecchie card tecniche.
- In `Impostazioni -> PEC`, `Verifica invio PEC` deve controllare l'invio dal PC in uso tramite IUSENTRA Local Signer. La UI non deve presentare verifiche SMTP remote come equivalenti e deve spiegare solo che la password resta sul dispositivo locale.
- In `Impostazioni -> AI Locale`, le azioni desktop devono passare dal PC dello studio tramite IUSENTRA Local Signer: se Ollama o i modelli mancano, la UI deve offrire `Prepara AI locale`, mostrare che IUSENTRA controlla il computer e sceglie automaticamente i modelli, e non lasciare campi modello senza guida operativa. Su telefoni e tablet non mostrare installer Ollama o download modelli: Lex deve usare il motore AI sul server di produzione IUSENTRA, con language model, embedding e indice documenti lato server.
- Il pannello `Archivio e revisione Lex` non deve sembrare un requisito per usare Lex: serve a controllare documenti indicizzati, coda di revisione ed export facoltativi per eventuale fine-tuning manuale. Le risposte ordinarie di Lex devono usare il RAG e i dati studio indicizzati senza richiedere riaddestramento.

## Linguaggio visibile

- La UI finale parla all'avvocato e al personale di studio, non allo sviluppatore.
- Non mostrare codici interni, chiavi di sistema, nomi API, identificativi tecnici o parole come `endpoint`, `payload`, `json_api`, `config_studio`, `undefined`, `null`, `runtime`, `server-side`, `backend`, `frontend`, `bridge`.
- Se un'informazione tecnica serve davvero, tradurla in un'azione comprensibile e vicina al campo: "Da completare", "Verifica invio PEC", "Configurazione salvata", "AI locale non verificata".
- Non usare banner globali per spiegazioni ovvie sui segreti. Le password e i token devono indicare lo stato solo dentro il campo interessato; l'icona occhio serve a controllare il nuovo valore digitato, non a riesporre quello salvato.
- Non togliere aiuti operativi necessari. Nel campo `Email SMTP -> Password email`, se lo studio usa Gmail o Google Workspace, ricordare che serve una password per le app Google e offrire il link alla generazione su `https://myaccount.google.com/apppasswords`.
- I dettagli tecnici restano nei log, nei test e nei report agenti, non nelle schermate operative.
- Prima di chiudere una pagina UI, cercare nel testo visibile e negli screenshot eventuali parole interne o messaggi da sviluppatore.
- Per `Pagamenti`, usare parole come "canali", "chiavi riservate", "link parcella", "bonifico" e "conferme pagamento". Non mostrare all'utente termini come `provider`, `webhook`, `legacy`, `payload` o `backend`.
- Per `Notifiche`, mostrare destinatario, testo, promemoria e registro. Non esporre nomi di servizi interni, endpoint o codici stato non comprensibili allo studio.
- Per `Backup`, mostrare copie, verifica, scaricamento protetto e permessi. Evitare parole come `runtime`, `snapshot tecnico`, `rollback`, `legacy`, `backend` o `storage` nella UI rivolta allo studio.
- Per `Calendari`, mostrare link riservati, calendari collegati, promemoria e sincronizzazione manuale. Evitare `token`, `feed`, `sync`, `payload`, `endpoint` e sigle tecniche quando non indispensabili.

## Accessibilita e UX

- Mantenere focus ring visibile su controlli e link.
- Aggiungere `aria-label` ai pulsanti solo icona.
- Usare tooltip per icone non ovvie, senza trasformare la UI in un manuale.
- Gestire loading, empty, errore e successo in modo esplicito.
- Non nascondere errori API: mostrare messaggi professionali e recuperabili.
- Su mobile la sidebar deve diventare overlay o navigazione compatta, senza perdere azioni principali.

## Cosa non fare

- Non copiare template admin completi dentro IUSENTRA.
- Non introdurre Material UI, Ant Design, Bootstrap aggiuntivo o design system concorrenti.
- Non hardcodare dati di studio, utenti, fascicoli, notifiche o scadenze.
- Non usare emoji come icone applicative.
- Non creare componenti duplicati per varianti minime.
- Non sostituire workflow backend reali con logica solo frontend.
- Non promuovere una pagina a React pieno se letture, scritture, permessi, audit e rollback tecnico non sono allineati.
- Non consegnare una schermata con tab, card, form o riepiloghi rotti visivamente anche se build e test passano.

## Verifiche minime

Per ogni tranche UI eseguire almeno:

- `pnpm --filter @iusentra/studio typecheck`
- `pnpm --filter @iusentra/studio test`
- `pnpm --filter @iusentra/studio build`
- verifica browser su desktop/tablet/mobile delle route toccate
- controllo console per errori di import, asset e API

Quando si aggiornano asset compilati, includere anche `web/static/react` nella release.
