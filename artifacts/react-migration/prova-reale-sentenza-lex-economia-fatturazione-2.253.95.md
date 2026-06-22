# Prova reale Sentenza Lex AI e Fatturazione 2.253.95

Data: 22/06/2026
Ambiente locale: `http://127.0.0.1:8080`
Versione: `2.253.95`

## Obiettivo

Verificare che la matrice Sentenza Tribunale non venga applicata a PDF strategici privi di conferma cliente/RG e che la pagina `Parcelle e Fatture` esponga card compatte operative, filtri reali e comportamento responsive coerente.

## Controlli eseguiti

- Docker locale ricostruito con `docker compose build --no-cache app` e riavviato con `docker compose up -d --force-recreate app nginx`.
- `/api/pronto` su `127.0.0.1:8080` ha risposto `ok=true`, `stato=pronto`, `versione=2.253.95`.
- Pagina `/fatturazione` aperta nel browser integrato Codex autenticato sulla copia locale reale.
- Console browser: nessun warning/errore applicativo rilevante durante apertura, click e responsive.

## Esito UI Fatturazione

- Card compatte operative viste: `12`.
- Card di stato: `Tutte`, `Bozza`, `Emessa`, `Pagata`, `Scaduta`, `Annullata`.
- Card azione: `Bonifico registrato`, `Parcella emessa`, `Nuova parcella`, `Export CSV`, `Numerazione`, `Canale SdI`.
- Click `Bonifico registrato`: il select `Filtro bonifico registrato` passa a `bonifico`.
- Click `Parcella emessa`: il select `Filtro parcella emessa` passa a `emessa`.
- Campi `Filtro cliente` e `Filtro numero fascicolo` accettano input reali; il placeholder fascicolo è `RG o ID fascicolo`.
- Click `Azzera filtri`: pagamento e parcella tornano a `all`, cliente/fascicolo tornano vuoti e resta attiva solo la card `Tutte`.
- Click `Numerazione`: URL aggiornato a `#fatturazione-numerazione`, pannello numerazione visibile.
- Click `Nuova parcella`: navigazione reale a `/fatturazione/nuova`, contenuto `Nuova parcella personalizzata` e comando `Crea parcella` presenti.
- Focus visibile sui filtri: bordo e box-shadow blu verificati sul campo `Cerca nell'archivio fatturazione`.

## Responsive

- Desktop: nessun overflow orizzontale; card `display:grid`, altezza minima `92px`.
- Mobile `390x844`: card in colonna singola, filtri visibili, click `Bonifico registrato` imposta `Sì`, `scrollWidth=375` e `clientWidth=375`.

## Struttura dati presidiata

- Il filtro `Nr fascicolo` usa campi dedicati del payload React: `caseId`, `caseReference`, `caseRg`.
- Test di contratto aggiunto in `tests/test_react_fatturazione_bridge.py` per evitare regressioni sul riferimento fascicolo.
- La regola Sentenza Tribunale richiede conferma del cliente e RG del fascicolo prima di applicare economia, proforma o indice Lex come sentenza del fascicolo.

## Limiti residui

- In locale l'archivio fatturazione corrente contiene `0` record reali, quindi la prova su righe proforma/parcella reali deve essere ripetuta sul server dopo deploy, dove stanno i fascicoli e i documenti indicati dall'utente.
- Il runtime del browser integrato non ha esposto `:hover` come stato DOM dopo movimento CUA; la regola CSS hover/focus è presente nello stesso blocco e il focus visibile è stato verificato materialmente.

## Stato

Locale: verificato su macchina reale `127.0.0.1:8080`.
Server: da verificare dopo commit, push, CI e deploy Hetzner sullo stesso commit.
