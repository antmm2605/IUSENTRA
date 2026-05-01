# Pattern OSS per migrazione React/TypeScript incrementale

Data analisi: 2026-05-01

Questo documento raccoglie pattern studiati su repository open-source attive e li traduce in regole applicabili a IUSENTRA. Le repo sono state usate come riferimento tecnico temporaneo, non come fonte di codice da importare.

## Fonti analizzate

- Apache Superset: `apache/superset`, commit osservato `98eaaaa`.
- Mattermost: `mattermost/mattermost`, commit osservato `5bad893`.
- p5.js Web Editor: `processing/p5.js-web-editor`, commit osservato `c5cdecb`.

Le copie locali sono temporanee e devono essere rimosse dopo l'analisi per rispettare la regola IUSENTRA della singola copia attiva del progetto.

## Confine di utilizzo

- Consentito: studiare architettura, script, CI, routing, migrazione incrementale, test e naming.
- Vietato: copiare componenti, helper o logica applicativa senza verifica licenza e senza adattamento esplicito al dominio IUSENTRA.
- Preferenza IUSENTRA: riscrivere pattern in modo proprietario e coerente con Flask, repository reali, tenant, audit, Local Signer e superfici legali.

## Pattern ricavati

### 1. TypeScript incrementale, non big-bang

Superset, Mattermost e p5 accettano una fase mista JS/TS, ma non una fase non governata.

Applicazione a IUSENTRA:

- mantenere `allowJs` solo come ponte temporaneo;
- ogni nuova pagina React deve essere TS/TSX;
- ogni nuova API bridge deve avere tipi espliciti;
- ogni dominio migrato deve aggiungere o aggiornare `npm run typecheck`;
- vietato promuovere una route solo perche' compila.

### 2. Typecheck come gate reale

Pattern osservati:

- Superset espone uno script dedicato di typecheck (`tsc --noEmit`) e lo combina con lint/test.
- Mattermost usa `check-types` separato dal build.
- p5 separa typecheck client e server con project references.

Applicazione a IUSENTRA:

- `npm run typecheck` resta obbligatorio dopo ogni modifica React;
- per ogni nuova pagina operativa si aggiunge almeno un test di contratto dati;
- una pagina con `any` o payload non tipizzato puo' essere `react_readonly`, ma non `react_operational_complete`.

### 3. Project boundary chiari

Pattern osservati:

- Superset divide frontend core, plugin e pacchetti con `references`.
- Mattermost divide piattaforma, componenti e canali.
- p5 divide client e server.

Applicazione a IUSENTRA:

- non creare pagine monolitiche che contengono fetch, form, mapping, card e fallback insieme;
- separare almeno: `data contract`, `page`, `cards/actions`, `form`, `runtime bridge`;
- le route Flask restano dominio di permessi, tenant, CSRF e audit;
- React consuma contratti reali, non ricrea logica legale.

### 4. Routing e navigazione testati

Pattern osservati:

- p5 testa componenti di routing come `ButtonOrLink` e `RouterTab`.
- Mattermost testa azioni di cambio contesto e navigazione con store/API mockate.

Applicazione a IUSENTRA:

- ogni card React deve avere un `href`, `action` o `form` reale;
- vietati link `#`, bottoni senza handler e CTA che aprono route non servite;
- ogni route profonda deve avere test HTTP e test di payload;
- la nav React puo' puntare a Jinja solo se lo stato e' esplicitamente `react_nav_only`.

### 5. CI per superfici, non solo build

Pattern osservati:

- Superset ha workflow separati per frontend, Playwright, E2E e dipendenze.
- Mattermost separa webapp CI, E2E, i18n e report.
- p5 ha test e deploy separati, piu' typecheck client/server.

Applicazione a IUSENTRA:

- il build React non basta;
- servono gate route/card/API per ogni pagina migrata;
- per ogni wave React bisogna aggiornare `tests/test_react_shell.py` o test dedicati;
- il gate deve fallire se una route marcata completa non ha API/card operative.

## Stati ufficiali di migrazione IUSENTRA

Ogni pagina deve avere uno stato esplicito nel manifest React:

- `legacy_only`: servita solo da Jinja/Flask classico.
- `react_nav_only`: usa nav/shell nuova ma contenuto operativo ancora classico.
- `react_readonly`: React legge dati reali, ma non copre azioni complete.
- `react_operational_partial`: React copre alcune azioni, con limiti documentati.
- `react_operational_complete`: React copre lettura, route profonde, card, form/download/API, test e fallback tecnico.

Solo `react_operational_complete` puo' diventare route React ufficiale senza ambiguita'.

## Protocollo obbligatorio pagina-per-pagina

1. Inventario route legacy: GET, POST, API, download, export, wizard, route profonde.
2. Inventario UI legacy: card, bottoni, modali, menu, filtri, stati vuoti, messaggi.
3. Inventario dati: repository JSON/SQLite/PostgreSQL, tenant, permessi, audit.
4. Contratto React: payload API tipizzato, senza mock operativo.
5. Implementazione React: componenti piccoli, token, responsive desktop/tablet/mobile.
6. Collegamento azioni: ogni card deve eseguire route/API/form/download reale.
7. Parita' funzionale: stesso risultato operativo della vista precedente, salvo miglioramenti documentati.
8. Test: route, API, card action, route profonda, fallback `_legacy=1` tecnico.
9. Switch controllato: aggiornare manifest/stato solo dopo test verdi.
10. Verifica release: build, typecheck, smoke locale e, se in perimetro, Railway/Hetzner.

## Anti-pattern da evitare

- Promuovere interi blocchi di menu senza completare le route profonde.
- Spostare utenti su React con card decorative.
- Usare `_legacy=1` come scorciatoia visibile per funzioni mancanti.
- Duplicare logica legale nel frontend.
- Nascondere una funzione legacy funzionante dietro una UI React incompleta.
- Dichiarare completa una pagina perche' risponde `200`.

## Checklist minima per nuova pagina React

- `GET` ufficiale servito correttamente.
- `GET ?_legacy=1` disponibile solo come percorso tecnico.
- API bridge reale sotto `/api/v1/ui/*` o route Flask operativa documentata.
- Nessun mock operativo o fallback JSON invisibile.
- Ogni card ha azione reale e test.
- Ogni form conserva POST, CSRF, tenant e audit.
- Ogni download/export resta funzionante.
- Date e testi in italiano.
- Responsive desktop/tablet/mobile.
- `npm run test`, `npm run typecheck`, `npm run build` verdi.
- Test Python route/API/card verdi.
- Stato manifest aggiornato solo dopo verifica.

## Regola pratica per IUSENTRA

La migrazione React non deve essere misurata in "pagine visualizzate", ma in "flussi operativi completati". Una pagina e' migrata solo quando l'avvocato puo' completare nello stesso modo, o meglio, il lavoro che completava nella vista precedente.
