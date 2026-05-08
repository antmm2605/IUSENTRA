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

Ogni pagina operativa dovrebbe comporre:

1. `IusPageShell`
2. `IusSectionHeader`
3. toolbar o filtri con controlli reali
4. contenuto principale con `IusActionCard`, `IusMetricCard`, `IusDataTableShell` o pannelli collassabili
5. stati vuoti, errore, successo e loading espliciti
6. Lex AI flottante solo dove previsto dalla superficie

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

## Verifiche minime

Per ogni tranche UI eseguire almeno:

- `npm run typecheck`
- `npm run test`
- `npm run build`
- verifica browser su desktop/tablet/mobile delle route toccate
- controllo console per errori di import, asset e API

Quando si aggiornano asset compilati, includere anche `web/static/react` nella release.
