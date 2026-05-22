# Preset grafico globale IUSENTRA

Aggiornato: 22 maggio 2026.

Questo preset è obbligatorio per le superfici operative React di IUSENTRA. La sola pagina esclusa è `/sito-studio/builder`, che mantiene la grafica attuale del builder visuale.

## Struttura

Il preset ha due livelli.

Livello di frame globale: `IusentraRoutePresetFrame` avvolge le rotte React operative da `frontend/src/App.tsx`, registra la categoria della pagina, applica i token globali e normalizza le griglie locali note. Il frame è disattivato solo per `/sito-studio/builder`.

Livello di primitive pagina:

```tsx
<IusentraPageShell>
  <IusentraMainArea>
    <IusentraMainSurface>
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

## Esempi corretti

- DataSurface con tabella naturale, footer in basso e scroll orizzontale interno.
- SupportRail con `Cabina fascicoli`, `Alert operativi`, `Azioni rapide`.
- Filtri principali sopra la tabella e filtri avanzati nel contesto.
- Mobile con card/lista e azioni contestuali.
- Rotta React avvolta da `IusentraRoutePresetFrame`, con builder escluso esplicitamente.

## Esempi sbagliati

- Tabella che termina molto prima della rail destra.
- Righe allungate artificialmente per riempire lo spazio.
- Footer paginazione flottante a metà pagina.
- Sidebar che contiene il dato principale.
- Filtri avanzati sopra il contenuto principale come blocco dominante.
- Valori CSS hardcoded duplicati nelle pagine.
- Icone casuali o mix di set grafici.
- Layout alternativo locale non collegato al preset.
