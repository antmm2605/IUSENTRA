# Lettura documento e salvataggio cliente — 14 ottobre 2026

Il comando normale deve applicare i dati leggibili anche quando la MRZ non supera i controlli, conservando l'avviso e senza attribuire a quella MRZ valori verificati. Il nuovo cliente deve essere salvato nel repository SQL e ritrovato nella scheda riaperta. Il preventivo iniziale è facoltativo e disattivato per default.

## Causa e correzione

Nel primo PDF sintetico la fonte nativa univa le due righe TD3, ciascuna di 44 caratteri, separandole con uno spazio. Il parser riconosceva soltanto le righe separate e perdeva numero del documento e nazionalità verificati. La correzione riconosce i confini esatti e riusa i controlli esistenti. Due passaporti differenti impediscono l'applicazione automatica; ripetizioni identiche non creano una falsa discordanza.

Il valore iniziale React del preventivo è ora false; rimosso checked anche nel modulo storico. Il DTO server era già coerente. Le bozze e le scelte esplicite non vengono cancellate.

## Prova materiale locale

Browser reale sulla copia Docker dell'utente, porta 8080, con documenti sintetici privati che non rappresentano persone reali:

- MRZ valida: lettura, applicazione di otto dati, Salva cliente, cartella AF8D97AC, riapertura tramite Modifica anagrafica. Nome, cognome, sesso, nascita, nazionalità, passaporto TSTSQ0001 e scadenza conservati.
- MRZ non valida: avviso visibile, sette dati leggibili applicati dal documento, Salva cliente, cartella B6118222 e riapertura. Passaporto TSTOCR002 e scadenza conservati. Nessuna trascrizione manuale dei dati riconosciuti.
- Nuovo modulo isolato: preventivo inizialmente deselezionato; attivazione e disattivazione manuali provate. Nel secondo salvataggio è rimasto deselezionato senza intervento.
- Lettura SQL in sola consultazione: entrambi i record corrispondono ai dati attesi; 33 clienti precedenti identici al backup coerente, collegamenti soggetti_parti invariati, campi non dimostrati vuoti.

41 guardrail del lettore superati; typecheck, build e suite frontend superati. Il contatore di completezza misura gruppi integralmente compilati: zero è coerente con la mancanza di codice fiscale, recapiti, indirizzo, ente e data di rilascio dei documenti sintetici.

Queste prove non attestano ogni documento possibile né il PostgreSQL operativo. Commit, gate GitHub, riallineamento locale esatto e deploy sono ancora da eseguire. L'incarico generale resta aperto.

## Correzione del gate CI

Lo shard core-04.01-4 del primo push ha evidenziato un test PEC non deterministico: sceglieva il primo messaggio pct_deposito fra tre fonti sintetiche della stessa data con stati differenti. Il risultato accettazione_deposito apparteneva a un'altra fixture, senza collegamento con il lettore anagrafico. Il test ora individua esattamente la ricevuta di avvenuta consegna RG 1234/2026 e richiede lo stato consegna_pec; esegue anche l'ordine inverso. Non sono modificati motore PEC, deposito, firma o invio. Il rilascio resta aperto fino ai nuovi gate e alle verifiche dello stesso commit.

Il push successivo ha evidenziato un difetto della scelta della baseline critica: un workflow terminato con successo per commit superato aveva saltato il deploy e veniva considerato distribuito. Il gate ora richiede, nel medesimo job/tentativo, esecuzione del deploy, riscontro del commit remoto, container healthy e controlli HTTPS eseguiti positivamente. Esamina anche i tentativi precedenti e ordina le prove per completamento reale, senza confondere un rerun tardivo con un nuovo rilascio. 25 test della configurazione/gate positivi; consultazione reale GitHub seleziona 6604cad0a98b459233f4b3184fc0206863e84dec con deploy 38509343639 e CI 38509343661, coincidente con HEAD server osservato via SSH. Soglie, perimetro, artefatti dei dodici shard e confronto omogeneo non vengono attenuati. Nuovo rilascio ancora in verifica.
