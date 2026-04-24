# Sito Studio

## Obiettivo

`Sito Studio` porta dentro IUSENTRA un modulo CMS nativo per ogni tenant, con pubblicazione web, contenuti editoriali, contatti e agenda appuntamenti, senza dipendere da WordPress esterno.

Il modulo nasce per essere:

- tenant-aware
- governabile da UI
- pubblicabile solo quando lo studio lo decide
- coerente con agenda, update intelligence, strumenti legali e applicazioni gia' presenti nel gestionale
- pronto per il supporto Lex Gateway: i contenuti del sito possono essere preparati con prompt e policy locali, senza inviare dati sensibili dello studio a provider esterni non autorizzati

## Superfici ufficiali

- `Studio -> Sito Studio` -> `/sito-studio/`
- `Piattaforma -> Siti studio` -> `/admin/siti-studio/`
- sito pubblico -> `/web/<public_slug>/`

## Cosa puo' gestire lo studio

- branding: logo, favicon, palette, claim, footer
- pagine a blocchi e home page
- articoli editoriali
- servizi dello studio
- professionisti
- sedi, contatti e mappa
- richieste contatto
- agenda appuntamenti pubblica con approvazione lato studio

## Sezioni opzionali pubbliche

Le sezioni seguenti non vengono esposte automaticamente sul sito pubblico.

L'amministratore del sito deve attivare i flag dedicati in `Sito Studio -> Impostazioni`:

- `Mostra Strumenti legali`
- `Mostra Applicazioni`
- `Mostra News giuridiche strutturate`

Effetto operativo:

- se il flag e' spento, la sezione non compare nel menu pubblico e la route pubblica risponde `404`
- se il flag e' acceso, la sezione viene resa nel sito pubblico con il relativo catalogo o feed

Route pubbliche interessate:

- `/web/<public_slug>/strumenti-legali`
- `/web/<public_slug>/applicazioni`
- `/web/<public_slug>/news-giuridiche`

## Agenda e contatti

Il modulo espone due canali pubblici reali:

- `Contatti`
- `Prenota appuntamento`

Flusso prenotazioni:

1. il cliente sceglie sede, data e slot disponibile
2. la richiesta entra nello stato `pending`
3. lo studio approva o rifiuta dalla dashboard `Sito Studio`
4. se approvata, la richiesta viene sincronizzata in agenda con `external_provider=site_studio`

La sincronizzazione agenda e' tenant-aware e usa il `studio.db` del tenant corrente.

## Storage governato

Il dominio `Sito Studio` non usa JSON come source of truth.

Persistenza ufficiale:

- SQLite / SQL locale tramite `SITE_STUDIO_DB`
- PostgreSQL tenant-aware quando configurato

Tabelle principali:

- `site_studio`
- `site_page`
- `site_article`
- `site_service`
- `site_professional`
- `site_office`
- `site_booking_rule`
- `site_booking_request`
- `site_contact_submission`

Schema SQL:

- `pct/sql/20260422_studio_site.sql`
- `pct/sql/20260422_studio_site_postgres.sql`

Asset caricati:

- percorso runtime `SITE_STUDIO_ASSETS_DIR`
- cartelle per slug pubblico sotto `site_assets/<public_slug>/`

## Governance piattaforma

Il `SUPERADMIN` ha una console dedicata:

- visione catalogo siti studio
- stato pubblicazione
- tenant slug
- URL pubblico
- riepilogo sezioni opzionali attive

Questa console non sostituisce la gestione editoriale del tenant, ma consente presidio e audit a livello piattaforma.

## Vincoli e comportamento atteso

- sito in bozza non visibile anonimamente
- preview bozza disponibile agli utenti autenticati dello studio
- pagine opzionali pubbliche governate solo dai flag di impostazione
- nessuna esposizione automatica di `strumenti legali`, `applicazioni` o `news` senza scelta esplicita dell'amministratore del sito
- nessun fallback invisibile a JSON quando il repository SQL/PostgreSQL e' attivo
