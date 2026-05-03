# IUSENTRA Legal Professional Design System

> Design system operativo per guidare Codex nella creazione e modifica delle interfacce IUSENTRA.

## Visual Theme & Atmosphere

IUSENTRA deve comunicare:
- affidabilita';
- precisione;
- sobrieta' professionale;
- ordine operativo;
- sicurezza;
- autorevolezza legale italiana.

La UI non deve sembrare:
- una startup crypto;
- un social network;
- un gestionale giocattolo;
- una demo generica;
- un template SaaS copiato senza adattamento.

Tono visivo:
- istituzionale ma moderno;
- denso ma leggibile;
- elegante senza decorazione inutile;
- orientato al lavoro quotidiano di studio legale.

## Color Palette & Roles

Palette consigliata:

- **Background app:** `#F6F7F9`
- **Surface:** `#FFFFFF`
- **Surface subtle:** `#F1F5F9`
- **Foreground:** `#111827`
- **Muted text:** `#64748B`
- **Border:** `#E2E8F0`
- **Primary:** `#1E3A8A`
- **Primary active:** `#1D4ED8`
- **Accent legal:** `#B08968`
- **Success:** `#15803D`
- **Warning:** `#B45309`
- **Danger:** `#B91C1C`
- **Info:** `#0369A1`

Regole:
- usare il primary per azioni principali e navigazione attiva;
- usare accent legal con moderazione per elementi istituzionali o premium;
- non usare piu' di un colore forte nella stessa area;
- evitare gradienti gratuiti;
- evitare glassmorphism e neon;
- evitare colori casuali fuori palette.

## Typography Rules

Font stack consigliato:
- headings: `Inter`, `system-ui`, `-apple-system`, `BlinkMacSystemFont`, `Segoe UI`, sans-serif;
- body: `Inter`, `system-ui`, `-apple-system`, `BlinkMacSystemFont`, `Segoe UI`, sans-serif;
- mono: `ui-monospace`, `SFMono-Regular`, `Consolas`, monospace.

Scala:
- 12px: microcopy, badge piccoli;
- 14px: testo tabellare, label;
- 16px: corpo standard;
- 20px: titoli card;
- 24px: titoli pagina;
- 32px: headline dashboard.

Regole:
- massima leggibilita';
- niente font decorativi;
- titoli brevi e concreti;
- microcopy in italiano;
- date e ore in formato italiano.

## Component Stylings

### Card

- sfondo bianco;
- bordo `1px solid #E2E8F0`;
- radius 14px;
- padding 16-24px;
- shadow leggerissima solo per superfici elevate.

### Pulsanti

- primary: blu istituzionale;
- secondary: bordo neutro;
- danger: rosso solo per azioni distruttive;
- testo chiaro, concreto, in italiano.

### Tabelle

- intestazioni compatte;
- righe leggibili;
- hover discreto;
- badge stato;
- azioni contestuali ordinate;
- niente icone senza testo quando il significato non e' ovvio.

### Form

- label sopra il campo;
- help text quando serve;
- validazione inline;
- errori chiari;
- campi obbligatori marcati in modo sobrio;
- CTA finale ben visibile.

### Badge

Usare badge per:
- stato fascicolo;
- urgenza scadenza;
- pagamento;
- deposito;
- fonte Lex;
- tenant/storage;
- esito controlli.

## Layout Principles

- navigazione stabile;
- gerarchia chiara;
- massimo una azione primaria per sezione;
- contenuto operativo sopra contenuto descrittivo;
- evitare pagine con sole card decorative;
- mostrare sempre il prossimo passo utile;
- desktop first ma responsive reale.

Griglie:
- dashboard: card KPI + area lavoro + attivita' recenti;
- fascicolo: header contestuale + tab operative + pannelli laterali;
- form lunghi: sezioni progressive;
- tabelle: filtri sopra, risultati sotto, azioni a destra.

## Depth & Elevation

Usare tre livelli:
- livello 0: background app;
- livello 1: card/surface;
- livello 2: modali, popover, dropdown.

No:
- ombre pesanti;
- neumorphism;
- effetti 3D;
- overlay decorativi inutili.

## Do's and Don'ts

### Do

- usare italiano professionale;
- rendere chiaro lo stato operativo;
- mostrare prossime azioni;
- distinguere dati certi, warning e dati mancanti;
- prevedere stati vuoti;
- prevedere loading;
- prevedere errore;
- prevedere conferma;
- mantenere coerenza con Bootstrap 5/Jinja o React esistente;
- rispettare permessi, audit e tenant quando la UI riguarda azioni sensibili.

### Don't

- non usare lorem ipsum;
- non usare testi inglesi visibili all'utente finale;
- non usare placeholder demo in UI finale;
- non inventare moduli non esistenti;
- non nascondere azioni importanti;
- non rompere navigazione esistente;
- non trasformare pagine operative in landing page;
- non usare animazioni inutili;
- non sacrificare leggibilita' per estetica.

## Responsive Behavior

Desktop:
- layout denso, pannelli multipli, tabelle complete.

Tablet:
- colonne ridotte;
- tab e filtri piu' compatti;
- azioni principali sempre visibili.

Mobile:
- contenuto in una colonna;
- tabelle trasformate in card quando necessario;
- azioni sticky solo se utili;
- nessuna perdita di informazione critica.

## Agent Prompt Guide

Quando Codex lavora su UI IUSENTRA deve:

1. leggere questo design system;
2. identificare il tipo di schermata;
3. scegliere la skill Open Design support piu' vicina;
4. proporre una direzione grafica prima di modificare;
5. rispettare italiano, date italiane e tono professionale;
6. non inventare dati o moduli;
7. considerare stati vuoti, errore, loading e conferma;
8. verificare responsive;
9. eseguire controlli pertinenti;
10. classificare il risultato con autoresearch-lite.
