# Preset grafico globale IUSENTRA

Aggiornato: 22 maggio 2026.

Questo preset è obbligatorio per le superfici operative React di IUSENTRA. La sola pagina esclusa è `/sito-studio/builder`, che mantiene la grafica attuale del builder visuale.

## Sequenza obbligatoria

Ogni pagina operativa React deve seguire la stessa sequenza visiva e logica. La sequenza è parte del preset globale, non una scelta locale della singola pagina:

1. Header pagina
2. Sottotitolo operativo
3. Azioni principali, preferibilmente card operative compatte
4. Filtri
5. Contesto filtri / riepilogo
6. Contenuto principale
7. Paginazione / footer
8. Sidebar di supporto

`IusentraRoutePresetFrame` applica questa sequenza a tutte le rotte operative tramite `IUSENTRA_PAGE_SEQUENCE`, `IUSENTRA_SEQUENCE_ROOT_SELECTORS` e gli attributi `data-iusentra-sequence-slot`. La pagina `/sito-studio/builder` è l'unica esclusa e non riceve né griglia né sequenza del preset.

Nessun blocco può restare senza ordine: se una sezione locale non viene riconosciuta dal classificatore centrale, il frame la marca come `main-content`. Questo impedisce a calcolatori, tab, note, card o pannelli locali di salire prima dell'header pagina. Tab e switcher sono filtri; note, alert e riepiloghi sono contesto; gli hero locali vengono resi come header pagina del preset unico.

Gli slot canonici sono:

- `page-header`: titolo della pagina;
- `operational-subtitle`: sottotitolo operativo sotto al titolo;
- `primary-actions`: azioni principali e card operative;
- `filters`: barra filtri principale;
- `context-filters`: filtri avanzati, riepilogo selezione, stato e contesto;
- `main-content`: tabella, lista, form o workspace operativo;
- `pagination-footer`: paginazione, footer di lista o controlli di navigazione;
- `support-sidebar`: rail laterale di supporto.

La regola importante è che le azioni principali precedono i filtri, i filtri precedono il contesto, il contenuto resta dopo il contesto e la paginazione/footer resta dopo il contenuto. La sidebar resta di supporto: su desktop può stare nella colonna destra, ma nel flusso logico e su mobile arriva dopo il contenuto e il footer.

## Struttura

Il preset ha tre livelli.

Livello di frame globale: `IusentraRoutePresetFrame` avvolge le rotte React operative da `frontend/src/App.tsx`, registra la categoria della pagina, applica i token globali e normalizza le griglie locali note. Il frame è disattivato solo per `/sito-studio/builder`.

Livello di sequenza globale: lo stesso frame marca e ordina le sezioni note con `data-iusentra-sequence-slot`, così le pagine esistenti non possono mettere toolbar, filtri o pannelli secondari davanti alle azioni e al contenuto principale.

Livello di primitive pagina:

```tsx
<IusentraPageShell>
  <IusentraMainArea>
    <IusentraMainSurface>
      <IusSectionHeader />
      <IusentraActionCard />
      <IusentraFiltersBar />
      <IusentraContextFilters />
      <IusentraDataSurface footer={<IusentraPaginationBar />}>
        contenuto operativo
      </IusentraDataSurface>
    </IusentraMainSurface>
    <IusentraSupportRail>
      <IusentraPanelCard />
      <IusentraPanelCard />
      <IusentraPanelCard title="Azioni rapide" />
    </IusentraSupportRail>
  </IusentraMainArea>
</IusentraPageShell>
```

I componenti vivono in `frontend/src/components/iusentra/IusentraPreset.tsx` e sono esportati da `frontend/src/components/iusentra/index.ts`.

Componenti obbligatori: `IusentraRoutePresetFrame`, `IusentraPageShell`, `IusentraMainArea`, `IusentraMainSurface`, `IusentraSupportRail`, `IusentraPanelCard`, `IusentraDataSurface`, `IusentraFiltersBar`, `IusentraContextFilters`, `IusentraPaginationBar`, `IusentraActionCard` e `IusentraEmptyState`.

## Griglia

Desktop:

- colonna principale: `minmax(0, 1fr)`;
- colonna laterale: `minmax(320px, var(--iusentra-support-rail-width))`, con token predefinito `360px`;
- gap: `var(--iusentra-layout-gap)`, pari a `16px`;
- allineamento: `start`;
- nessuna card fuori asse.

Tablet e mobile:

- la rail passa sotto il contenuto principale;
- filtri e contesto filtri diventano una colonna;
- le tabelle mantengono scroll interno o diventano liste/card quando la pagina già prevede variante mobile.

## Allineamento verticale

`IusentraMainArea` misura la `IusentraSupportRail` con `ResizeObserver` e passa l'altezza tramite `--iusentra-support-rail-min-height`.

`IusentraRoutePresetFrame` misura anche le rail delle griglie locali registrate, per esempio Agenda, Clienti, Soggetti, PEC, Scadenziario, Telematico, Admin database, Template atti e Preventivi. L'altezza viene esposta come `--iusentra-route-rail-height` e la superficie principale riceve una `min-height` coerente sul desktop.

Su desktop, `IusentraMainSurface` usa quel valore come altezza minima. Se il browser non consente la misura, resta attiva una regola CSS di fallback basata su viewport e token. La `IusentraDataSurface` può usare `fill` per occupare lo spazio residuo e tenere la paginazione in basso.

Regola: non si allungano righe o card per riempire spazio. Cresce la superficie contenitore, mentre il footer resta ancorato in basso.

## DataSurface

Ogni tabella o lista principale deve stare dentro `IusentraDataSurface`.

La struttura obbligatoria è:

- header con titolo e toolbar;
- corpo con tabella, lista o card operative;
- footer con paginazione o azioni di navigazione;
- scroll orizzontale interno per molte colonne;
- scroll verticale interno controllato solo quando serve;
- stato vuoto con `IusentraEmptyState` o messaggio operativo breve.

Se il testo è troppo lungo, usare anteprima corta, `line-clamp`, tooltip, drawer o pagina di dettaglio.

## Filtri

`IusentraFiltersBar` contiene solo i filtri principali: ricerca, tipo, stato, periodo, ufficio o canale. Deve stare prima del contenuto operativo.

`IusentraContextFilters` contiene filtri avanzati, riepiloghi di selezione o contesto secondario. Non deve schiacciare la tabella o prendere priorità sul contenuto principale.

## Paginazione

`IusentraPaginationBar` deve stare nel footer della `IusentraDataSurface`. Quando la lista è lunga, la pagina può aggiungere controlli anche sopra, ma il footer resta sempre in basso.

Per Fascicoli:

- `Per pagina` resta nell'header, in alto a destra;
- `Precedente / Pagina n di n / Successiva` resta nel footer;
- con pochi record la tabella non deforma le righe;
- con molti record si usa paginazione e scroll interno.

## SupportRail

La `IusentraSupportRail` contiene solo supporto alla pagina:

- riepiloghi;
- alert;
- checklist;
- azioni rapide;
- suggerimenti o controlli secondari.

Non contiene il contenuto principale. Ogni pannello usa `IusentraPanelCard` con titolo, icona coerente, badge opzionale, testo sintetico e azione solo quando necessaria.

## Nuove viste di dettaglio

Quando il contenuto non entra in modo ordinato:

- fascicolo troppo ricco: pagina dettaglio fascicolo;
- documento con molti metadati: drawer o pagina documento;
- molte azioni: menu contestuale;
- molti filtri: pannello filtri avanzati;
- testo lungo: anteprima corta e apertura dettaglio.

È vietato forzare tutto nella card principale creando finestre enormi o righe deformate.

## Token grafici

I token centrali sono in `frontend/src/styles/iusentra-design-system.css`:

- `--iusentra-radius-sm`, `--iusentra-radius-md`, `--iusentra-radius-lg`;
- `--iusentra-layout-gap`;
- `--iusentra-support-rail-width`;
- `--iusentra-toolbar-height`;
- `--iusentra-surface-min-height`;
- `--iusentra-border`, `--iusentra-border-soft`;
- `--iusentra-text`, `--iusentra-text-muted`;
- `--iusentra-primary`, `--iusentra-success`, `--iusentra-warning`, `--iusentra-danger`, `--iusentra-info`;
- `--iusentra-card-bg`, `--iusentra-page-bg`;
- `--iusentra-shadow-card`, `--iusentra-shadow-raised`.

Non duplicare questi valori nelle pagine.

## Icone

La mappa minima è centralizzata in `iusentraPresetIcons`:

- Fascicoli: `FolderOpen` / `BriefcaseBusiness`;
- Scadenze: `CalendarDays` / `Clock` / `Bell`;
- Documenti: `FileText` / `Paperclip`;
- PEC e comunicazioni: `Mail`;
- Depositi: `UploadCloud` / `Send`;
- Archivio: `Archive` / `Box`;
- Controlli: `ShieldCheck` / `CheckCircle2`;
- Alert: `Bell` / `TriangleAlert`;
- Azioni rapide: `Sparkles` / `Zap`;
- Cliente e soggetti: `UserRound` / `UsersRound`;
- Economico e fatture: `Euro` / `ReceiptText`;
- Ricerca: `Search`;
- Filtri: `SlidersHorizontal`.

Usare Lucide tramite la mappa o tramite `IusLegalIcon`.

## Audit e test

La sequenza non è affidata alla memoria di chi modifica una pagina. I gate obbligatori sono:

- `node frontend/scripts/check-react-contracts.mjs`: verifica che il frame globale, gli slot sequenza, il CSS ordine e Fascicoli restino agganciati al preset;
- `node scripts/react-migration/audit-ui-preset-sequence.mjs`: verifica gli 8 slot canonici, l'esclusione `/sito-studio/builder`, l'export dei componenti e l'inclusione del gate nel test frontend;
- `python -m pytest tests/test_react_shell.py::test_react_fascicoli_usa_preset_grafico_globale -q --tb=short`: impedisce regressioni su PageShell, MainArea, SupportRail, DataSurface, filtri, contesto e sequenza;
- browser reale desktop, tablet e mobile sulle rotte rappresentative: `/fascicoli`, `/agenda`, `/scadenziario`, `/clienti`, `/soggetti`, `/email/`, `/deposito/checklist`, `/admin/database` e `/sito-studio/builder`.

Il test deve fallire se una pagina operativa rimuove `IusentraRoutePresetFrame`, se il builder non resta escluso, se le azioni principali non precedono i filtri o se la paginazione perde l'ancoraggio nella superficie dati.

## Esempi corretti

- DataSurface con tabella naturale, footer in basso e scroll orizzontale interno.
- SupportRail con `Cabina fascicoli`, `Alert operativi`, `Azioni rapide`.
- Header, sottotitolo e card operative prima dei filtri.
- Filtri principali sopra la tabella e filtri avanzati nel contesto.
- Mobile con card/lista e azioni contestuali.
- Rotta React avvolta da `IusentraRoutePresetFrame`, con builder escluso esplicitamente.

## Esempi sbagliati

- Tabella che termina molto prima della rail destra.
- Righe allungate artificialmente per riempire lo spazio.
- Footer paginazione flottante a metà pagina.
- Sidebar che contiene il dato principale.
- Filtri, toolbar o pannelli secondari prima delle azioni principali.
- Filtri avanzati sopra il contenuto principale come blocco dominante.
- Valori CSS hardcoded duplicati nelle pagine.
- Icone casuali o mix di set grafici.
- Layout alternativo locale non collegato al preset.
