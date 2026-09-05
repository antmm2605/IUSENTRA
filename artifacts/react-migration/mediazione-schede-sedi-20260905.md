# Registro mediazione: schede e sedi, 05/09/2026

## Stato della consegna

Intervento verificato sulla copia reale locale `http://127.0.0.1:8080`, versione di lavoro `2.278.86`.
Il lavoro complessivo resta **aperto**: commit/push, allineamento dei cambi precedenti e deploy Hetzner non ancora eseguiti per questa tranche. Non costituisce attestazione di completamento delle 14 fasi o dell'intero procedimento di mediazione nel fascicolo.

## Difetti osservati e correzioni

- Il caricamento del registro costruiva anche dashboard generale, monitor fascicoli, notizie e audit AI. Percorso di lettura dedicato, senza queste dipendenze; frontend con condivisione della richiesta già in corso, senza cache persistente di sessione.
- Dettaglio generico lontano dall'ente: nuova scheda inline immediatamente sotto la riga cliccata, un solo dettaglio aperto, comando di chiusura in fondo e ritorno del focus al pulsante dell'ente.
- Il collegamento diretto a un organismo di una pagina successiva conservava l'ID ma non rendeva visibile la scheda dopo un reload. La paginazione ora raggiunge l'organismo selezionato.
- La precedente importazione non acquisiva la sezione ministeriale Sedi. Importatore pubblico paginato, verifica identità dell'organismo, pagina corrente e totale; nessuna deduplicazione arbitraria di sedi coincidenti e nessun inventario parziale registrato come completo.
- Filtro Regione → Provincia basato sulle sedi effettive, non sulla sola sede legale. Cambiando regione si azzera la provincia. La scheda mostra le sedi della zona e permette di visualizzarle tutte quando esistono sedi ulteriori.
- Collegamenti HTTP/HTTPS ai siti, con esclusione di schemi eseguibili e credenziali negli URL; apertura in nuova scheda.
- Mobile/tablet: stessi campi disposti verticalmente, comandi accessibili senza scorrimento orizzontale; rilettura delle sedi e stati caricamento/errore espliciti.

## Dati e provenienza

Fonte: [registro ministeriale](https://mediazione.giustizia.it/ROM/ALBOORGANISMIMEDIAZIONE.ASPX), sezione Sedi raggiunta tramite il comando nativo del registro.

- Registro locale: 1.153 organismi, 491 attivi; 3.046 voci includendo enti di formazione e formatori.
- Acquisizione sedi del 05/09/2026: **491 organismi attivi su 491**, **6.673 righe sede**, **966 pagine ministeriali**. Nessun fallimento residuo nei cinque lotti.
- Per ciascun organismo il numero delle righe SQL coincide con il totale dichiarato dal Ministero. Le righe sede legale e operativa allo stesso indirizzo sono conservate come pubblicate.
- Esempi: ADR Center 42 sedi/5 pagine; Bologna 2/1; Foro di Palmi 2/1; Camera di Mediazione Nazionale 130/13; Rimedia 666/67.
- Gli organismi cancellati/sospesi non fanno parte di questa acquisizione delle sedi degli attivi. I dati ministeriali possono contenere refusi: non sono stati corretti o reinterpretati arbitrariamente.
- Fonte operativa sedi: `source_of_truth=sqlite`, `data/intelligence/mediazione_directory.db`. Tabelle `mediazione_organismi`, `mediazione_office_snapshots`, `mediazione_directory_audit`; JSON solo payload/bootstrap o colonna strutturata, non archivio alternativo per le decisioni.
- Schema condiviso SQLite/PostgreSQL in `pct/sql/20260905_mediazione_directory.sql`. Provati creazione schema, importazione organismo, salvataggio e rilettura sedi, elenco e conteggio su PostgreSQL 16 reale in un container diagnostico temporaneo, senza usare il database dello studio. Container diagnostico eliminato dopo la prova; non è una prova del deployment in produzione.
- Archivio pubblico distinto dai tenant. DSN ammesso solo tramite `MEDIAZIONE_DATABASE_URL`, senza inferirlo dal tenant autenticato. Nessun dato di fascicolo, PIN, credenziale, documento dello studio o sessione CNS inviato al Ministero.
- API autenticata: `GET /api/v1/ui/legal-intelligence/mediazione/organismi/{number}/sedi`; lettura SQL, nessuna acquisizione web durante il caricamento.

## Prova materiale locale

Browser integrato reale, scheda autenticata dell'utente; nessun browser isolato, server temporaneo o dato simulato usato come accettazione.

- Apertura/chiusura e contenuto verificati sulle 25 schede della prima pagina, con attesa del contenuto per i due casi inizialmente letti prima del termine della risposta.
- Tre schede dell'ultima pagina: ANTEMAR MEDIAZIONE, Assoedilizia (denominazione lunga), Organismo Italiano di Mediazione.
- Altri due organismi: Foro di Palmi e Camera di Mediazione Nazionale. Totale **30 organismi distinti controllati con interazioni reali**, non 491 click individuali.
- Calabria → RC: 51 risultati; Foro di Palmi mostra 2 sedi; Camera di Mediazione Nazionale mostra 3 sedi in provincia su 130, quindi 130 su 130 dopo il click sul comando dedicato.
- Cambio regione azzera il valore Provincia. Navigazione fino a pagina 20, 476–491; Successiva disabilitato correttamente.
- Reload del link `scheda=registro-mediazione-organismo-290`: prima nessun dettaglio e pagina 1; dopo correzione dettaglio Palmi visibile e pagina 7. Chiusura in fondo: focus sul pulsante di Palmi.
- Bologna: apertura reale, 2 sedi su 2, indirizzi e contatti leggibili; click Rileggi sedi e Chiudi questa scheda. Prove a larghezze 390, 900 e 1922 pixel sulla stessa macchina; non equivalgono a prove su dispositivi fisici iOS/Android.
- Scheda ADR Center scorsa nella parte alta, centrale e finale. Scheda Bologna mobile controllata fino al fondo. Focus da tastiera visibile sui comandi e nessuna etichetta scomparsa nello stato selezionato.
- Click Apri sito web: Camera di Mediazione Nazionale aperta in nuova scheda con titolo e dominio corretti. Click Verifica sedi: pagina ministeriale ROM=341 aperta, 130 totali e 13 pagine visibili.
- Prestazioni browser: prima due richieste di circa 42,1 e 42,7 secondi, 5,58 MB ciascuna; dopo richiesta unica circa 1,47 secondi, 3,20 MB con tutte le località. Dettagli sedi misurati tra circa 0,30 e 0,49 secondi. Sono misure di questa sessione, non SLA.

## Guardrail automatici

- `pnpm --filter @iusentra/studio typecheck`: esito positivo.
- Build Vite e build Docker locale: esito positivo; ricreazione del servizio reale eseguita, `iusentra-app` healthy e `/api/pronto` versione `2.278.86` alle 14:04 del 05/09/2026. Nuova apertura e rilettura della scheda Bologna: 2 sedi su 2. Il successivo guardrail di chiusura connessioni PostgreSQL e gli script non cambiano il comportamento SQLite già osservato.
- `tests/test_mediazione_offices_directory.py`: 5 test superati; parser, identità/pagina/colonne, ruoli dei contatti, sedi coincidenti, inventari incompleti respinti, aggiornamento SQL, assenza archivio esplicita, nessun caricamento dashboard/AI/fascicoli nel registro.
- Tre test selezionati mediazione di `tests/test_react_legal_intelligence_search.py`: superati.
- `tests/test_openapi_contracts_phase6.py`: 5 test superati dopo l'aggiornamento del parametro campione; Ruff e Flake8 sui nuovi moduli senza errori, contratti generati e packaging allineati.
- API reale senza autenticazione: 401. Generatore e validazione OpenAPI riallineati alla nuova rotta; il verificatore dei contratti ora sostituisce anche il parametro numerico `number` con un ID concreto, evitando il falso 405 sulla stringa letterale `{number}`.
- I guardrail automatici non sostituiscono la prova reale e non coprono l'intero prodotto.

## Passaggi ancora aperti e tutela delle modifiche precedenti

- Non tutti i 491 pulsanti sono stati cliccati singolarmente; l'inventario SQL è riconciliato integralmente, il collaudo UI riguarda i 30 organismi sopra elencati.
- La verifica delle pagine generiche delle tre fonti e dei vecchi comandi Scarica non è chiusa: i collegamenti generici non dimostrano uno snapshot scaricabile disponibile.
- Censimento dei portali/moduli e procedimento completo della mediazione nel fascicolo restano un perimetro distinto non consegnato da questo fix.
- Hetzner rilevato su `2f0ac3c9b`, unico `iusentra-app` healthy, con modifiche precedenti in CartelleCondivisePage, FascicoliPage e TelematicoSurfacePage. Non eseguire reset/deploy che le perda. Prima della consegna: riconciliare il codice precedente, gate, commit/push dei branch gemelli, backup preventivo e deploy ordinato.
- Anche il database pubblico acquisito deve essere distribuito/importato in modo governato: il solo deploy del codice non trasferisce automaticamente il nuovo inventario locale.
- Bootstrap/aggiornamento esplicito disponibile in `scripts/acquire_mediazione_offices.py --registry-json <snapshot ministeriale> --db <repository pubblico>`. Il comando resta limitato e riprendibile; un lotto fallito termina con errore e conserva le sedi verificate. `--number` consente la nuova acquisizione mirata di un organismo esistente. Il normale accesso alla pagina non esegue questo lavoro.
- Nessuna modifica alla logica di wizard, deposito, notifiche, firma o firma multipla durante questo intervento sulle schede mediazione.
