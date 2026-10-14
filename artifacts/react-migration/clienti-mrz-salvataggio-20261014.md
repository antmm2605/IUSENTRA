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
