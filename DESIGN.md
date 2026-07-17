---
name: IUSENTRA
description: Il registro operativo dello studio legale italiano.
colors:
  legal-night: "#071329"
  institutional-blue: "#123d72"
  action-blue: "#2563eb"
  judicial-gold: "#b8860b"
  page-background: "#f5f7fb"
  surface: "#ffffff"
  surface-subtle: "#f8fbff"
  text: "#111827"
  text-muted: "#64748b"
  border: "#e2e8f0"
  success: "#15803d"
  warning: "#b45309"
  danger: "#b91c1c"
  info: "#0369a1"
typography:
  display:
    fontFamily: "Inter, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "clamp(25px, 2.15vw, 34px)"
    fontWeight: 950
    lineHeight: 1.08
    letterSpacing: "0"
  headline:
    fontFamily: "Inter, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "18px"
    fontWeight: 850
    lineHeight: 1.24
    letterSpacing: "0"
  title:
    fontFamily: "Inter, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "15px"
    fontWeight: 850
    lineHeight: 1.25
    letterSpacing: "0"
  body:
    fontFamily: "Inter, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "14px"
    fontWeight: 650
    lineHeight: 1.45
    letterSpacing: "0"
  label:
    fontFamily: "Inter, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "12px"
    fontWeight: 800
    lineHeight: 1.25
    letterSpacing: "0"
rounded:
  sm: "8px"
  md: "10px"
  lg: "12px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "20px"
  layout: "14px"
components:
  button-primary:
    backgroundColor: "{colors.institutional-blue}"
    textColor: "{colors.surface}"
    typography: "{typography.label}"
    rounded: "{rounded.md}"
    padding: "8px 14px"
    height: "44px"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    typography: "{typography.label}"
    rounded: "{rounded.md}"
    padding: "8px 14px"
    height: "44px"
  field:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "9px 11px"
    height: "44px"
  panel:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.lg}"
    padding: "16px"
  status-chip:
    backgroundColor: "{colors.surface-subtle}"
    textColor: "{colors.text-muted}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "4px 8px"
---

# Design System: IUSENTRA

## Overview

**Creative North Star: "Il Registro Operativo"**

IUSENTRA deve ricordare un registro professionale contemporaneo: autorevole, ordinato e immediatamente leggibile, con la densità necessaria per lavorare su fascicoli reali senza trasformare ogni dato in una card. La gerarchia nasce da titoli compatti, superfici bianche, bordi discreti e stati semantici inequivocabili.

L'interfaccia privilegia continuità e controllo. La navigazione resta stabile, le azioni principali sono riconoscibili, i pannelli laterali assistono il flusso senza sottrarre spazio al contenuto e ogni messaggio indica cosa è accaduto e quale azione è disponibile. Desktop, notebook, tablet e mobile conservano la stessa logica, cambiando disposizione e non significato.

Sono vietati l'aspetto da dashboard SaaS generica, la composizione da vetrina marketing, i dati decorativi, il glassmorphism gratuito e qualsiasi estetica che renda ambiguo lo stato operativo.

**Key Characteristics:**
- Denso ma scansionabile, con priorità visive stabili.
- Sobrio, istituzionale e specifico per il lavoro legale italiano.
- Azioni reali, stati espliciti e nessun controllo ornamentale.
- Superfici responsive con target touch minimi di 44px.
- Italiano corretto, date italiane e importi nel formato `€ 1.234,56`.

## Colors

La palette combina il blu istituzionale con neutri freddi e un accento oro giudiziario usato con parsimonia; verde, ambra e rosso comunicano esclusivamente stato e rischio.

### Primary
- **Blu Istituzionale:** governa azioni primarie, intestazioni operative e selezioni persistenti.
- **Blu Azione:** segnala focus, collegamenti e interazioni attive senza dominare la pagina.

### Secondary
- **Oro Giudiziario:** identifica dettagli di marca e segnali istituzionali; non sostituisce mai un colore semantico.

### Tertiary
- **Verde Esito, Ambra Presidio, Rosso Blocco e Azzurro Informazione:** sono riservati rispettivamente a successo, attenzione, errore bloccante e informazione verificabile.

### Neutral
- **Notte Legale:** fondale della navigazione principale e contrasto di marca.
- **Carta Operativa:** superficie primaria per moduli, tabelle e documenti.
- **Carta di Servizio:** separa filtri, righe secondarie e stati vuoti.
- **Inchiostro e Inchiostro Attenuato:** testo principale e metadati.
- **Linea Archivio:** bordo sottile e divisore, mai elemento decorativo dominante.

### Named Rules
**The Semantic Color Rule.** Verde, ambra e rosso non decorano: devono corrispondere a uno stato reale e leggibile anche nel testo.

**The Judicial Gold Rule.** L'oro è un accento raro; non deve superare visivamente le azioni blu o i contenuti legali.

## Typography

**Display Font:** Inter (con fallback di sistema)
**Body Font:** Inter (con fallback di sistema)
**Label/Mono Font:** Inter; numeri tabellari per importi, date, orari e conteggi

**Character:** una sola famiglia sans serif riduce il rumore e mantiene coerenza tra tabelle dense, moduli e documenti. Il peso crea gerarchia; la dimensione non viene scalata in base alla larghezza del viewport.

### Hierarchy
- **Display** (950, `clamp(25px, 2.15vw, 34px)`, 1.08): solo intestazioni di pagina vere, mai dentro pannelli compatti.
- **Headline** (850, 18px, 1.24): titoli di sezione e stati principali.
- **Title** (850, 15px, 1.25): titoli di card operative, righe e modali.
- **Body** (650, 14px, 1.45): testo operativo, descrizioni e istruzioni essenziali, con righe preferibilmente entro 72 caratteri.
- **Label** (800, 12px, 1.25): etichette, metadati e pulsanti; maiuscolo solo per categorie brevi.

### Named Rules
**The Legal Scan Rule.** Prima vengono numero, data, tipo e parte; il testo descrittivo non deve oscurare gli identificativi che l'avvocato usa per decidere.

**The Zero Tracking Rule.** La spaziatura tra lettere resta `0`; è ammessa solo una lieve apertura nelle etichette brevi già previste dal sistema.

## Elevation

Il sistema usa una profondità ambientale e contenuta. Bordi e variazioni tonali definiscono la struttura; l'ombra distingue superfici principali, modali e stati interattivi senza simulare oggetti sospesi.

### Shadow Vocabulary
- **Card ambientale** (`0 12px 34px rgba(15, 23, 42, 0.07)`): pannelli e superfici dati principali.
- **Superficie sollevata** (`0 22px 54px rgba(15, 23, 42, 0.10)`): modali, menu e strumenti temporaneamente sopra il flusso.
- **Interazione contenuta** (`0 14px 26px rgba(37, 99, 235, 0.10)`): solo hover di un controllo o elemento realmente cliccabile.

### Named Rules
**The Structural Depth Rule.** Una sezione non diventa una card per ottenere separazione; usare prima spazio, bordo e gerarchia tipografica.

## Components

### Buttons
- **Shape:** rettangoli compatti con angoli controllati (10px) e target minimo 44px.
- **Primary:** blu istituzionale, testo bianco, icona Lucide quando disponibile e un solo verbo d'azione.
- **Hover / Focus:** variazione di tono lieve; focus visibile con anello blu e nessun salto di layout.
- **Secondary / Ghost:** fondo bianco, bordo sottile, testo scuro; i comandi solo icona hanno tooltip e nome accessibile.
- **Disabled / Loading:** il testo resta leggibile, la causa del blocco è visibile nel contesto e la larghezza non cambia.

### Chips
- **Style:** etichette piccole, bordo sottile e fondo tonale; il colore dipende dallo stato reale.
- **State:** selezione evidente anche tramite testo, icona o bordo, non soltanto colore.

### Cards / Containers
- **Corner Style:** angoli moderati (12px); nessuna pillola per contenuti estesi.
- **Background:** bianco per la superficie primaria e carta di servizio per raggruppamenti secondari.
- **Shadow Strategy:** ombra ambientale solo sulle superfici autonome; sezioni interne piatte.
- **Border:** una linea tenue delimita struttura e tabella.
- **Internal Padding:** 12-16px; 8px solo per righe dense e toolbar.

### Inputs / Fields
- **Style:** fondo bianco, bordo archivio, altezza minima 44px e raggio 10px.
- **Focus:** bordo blu e anello visibile senza variazione dimensionale.
- **Error / Disabled:** errore con testo specifico e rosso semantico; disabilitato leggibile e accompagnato dalla ragione quando blocca un flusso.

### Navigation
- La navigazione principale usa Notte Legale, icone Lucide, etichette compatte e stato attivo con contrasto netto. Su mobile diventa un controllo raggiungibile senza coprire il contenuto; il click deve conservare contesto e destinazione.

### Registro Operativo
- Tabelle, timeline, planner e liste fascicoli sono le superfici distintive. Devono favorire confronto e scansione, mantenere colonne stabili su notebook e trasformarsi in righe impilate su mobile senza perdere RG, parte, data, stato e azione primaria.

## Do's and Don'ts

### Do:
- **Do** usare la scala di spazio 4, 8, 12, 16 e 20px e un gap di layout di 14px.
- **Do** mantenere azioni, filtri e stato nello stesso contesto operativo.
- **Do** usare icone Lucide, tooltip per comandi non familiari e target touch di almeno 44px.
- **Do** rendere visibili hover, focus, selected, disabled, loading, errore e successo.
- **Do** mostrare date, orari e importi nel formato italiano previsto dal prodotto.
- **Do** verificare ogni superficie a 1366x768, tablet e mobile prima della consegna.

### Don't:
- **Don't** creare una dashboard SaaS generica o una vetrina marketing.
- **Don't** usare glassmorphism gratuito, gradient text o una dark mode scelta solo per estetica tech.
- **Don't** mostrare dati hardcoded, link placeholder o scorciatoie `_legacy=1` visibili.
- **Don't** mescolare italiano e inglese nei testi operativi.
- **Don't** inserire card dentro card o trasformare intere sezioni in contenitori flottanti.
- **Don't** usare pillole testuali quando esiste un simbolo familiare o una vera azione di comando.
- **Don't** introdurre riferimenti visibili a prodotti terzi o dettagli tecnici interni nei flussi dell'avvocato.
- **Don't** nascondere un requisito bloccante dietro un pulsante disabilitato senza spiegazione e azione correttiva.
