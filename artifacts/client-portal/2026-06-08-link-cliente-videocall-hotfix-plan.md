# Portale Cliente - hotfix Link Cliente e Videocall

Data: 8 giugno 2026.
Branch operativo: `Codex/legal-electronic-filing-kIxcV`.

## Richiesta corrente

L'utente segnala che nella UI non visualizza:

- il link cliente;
- la videocall.

Durante il lavoro l'utente ha chiesto anche l'invio del link tramite WhatsApp Web.
Ha chiesto inoltre una ricerca cliente con filtro durante la digitazione.

Il fix deve restare dentro la superficie React del Portale Cliente, usare API reali e non introdurre dati fittizi.

## Vincoli confermati

- Nessun backup.
- Nessun commit finché il fix non è completo e verificato.
- Copia finale reale su `http://127.0.0.1:8080`.
- Token invito salvato solo come hash nel database: il link completo è mostrabile solo subito dopo la generazione o rigenerazione.
- SQLite e PostgreSQL non richiedono nuove colonne se si usa il campo appuntamento `video_url` già presente.
- Test mirati e verifica browser prima del rilascio.

## Piano operativo

1. Classificare worktree e tenere fuori dal commit i file runtime in `data/`.
2. Aggiornare la dashboard studio:
   - aggiungere ricerca cliente nel form invito con filtro immediato durante la digitazione;
   - rendere visibile una sezione `Link cliente` per la pratica selezionata;
   - mostrare gli inviti esistenti con stato e scadenza;
   - aggiungere `Genera link cliente`, `Copia link` e `Apri vista cliente` per il link appena creato;
   - aggiungere `Invia con WhatsApp Web` con messaggio già predisposto e senza invio server-side;
   - aggiungere azione rapida `Link cliente` nella lista pratiche.
3. Aggiornare appuntamenti/videocall:
   - mostrare campo `Link videocall` nella proposta appuntamento quando la funzione è attiva;
   - mostrare un messaggio professionale quando la funzione non è attiva;
   - lato cliente mostrare `Apri videocall` sugli appuntamenti con link disponibile.
4. Rafforzare API/test:
   - endpoint invito deve restituire un link assoluto o comunque completo per il browser corrente;
   - endpoint appuntamento deve preservare `video_url` solo quando il flag videocall è attivo;
   - test API per link cliente e videocall.
5. Aggiornare documentazione/report del Portale Cliente.
6. Eseguire test mirati, build frontend, Docker reale `8080`, verifica browser desktop/mobile e screenshot.
7. Solo dopo esito verde: commit, push branch gemelli, attesa check GitHub, deploy Hetzner e verifica produzione.

## Controllo dopo rilettura

Il piano copre UI studio, UI cliente, sicurezza del token, feature flag videocall, backend/API, test, documentazione, Docker reale, CI e deploy. Non serve modificare schema SQL perché `video_url` esiste già nel modello appuntamenti.
WhatsApp Web resta un'azione manuale dello studio nel browser: nessuna credenziale WhatsApp viene salvata o usata dal backend.

## Stato esecuzione

- Implementati ricerca cliente, filtro fascicoli collegati, link cliente visibile, copia link, apertura vista cliente e WhatsApp Web.
- Implementata videocall negli appuntamenti studio/cliente con validazione `http/https`.
- Corretto il contrasto dei bottoni nel box link e nella vista cliente.
- Corretto il salvataggio orario appuntamento: input locale dello studio interpretato come ora italiana e normalizzato in UTC.
- Verificati test API, gate React, UTF-8, Docker reale `127.0.0.1:8080`, browser desktop e mobile.
- Commit, push branch gemelli, check GitHub/CodeQL e deploy Hetzner senza backup completati per `2.249.34`.
- Dopo il deploy finale è stato rilanciato `Avvia tutti` in produzione: 78 job richiesti e zero errori di accodamento; il controllo ha evidenziato che `legal_source_codice_strada`, fuori dalla fase 9 progressiva, veniva conteggiato come failure pur essendo un presidio rinviato. Correzione avviata in `2.249.35`.
- `2.249.35`: corretta la failure impropria, reso robusto il workflow SBOM, completati test locali, Docker reale, push branch gemelli, 175 check-run GitHub verdi, deploy Hetzner no-backup e nuova esecuzione `Avvia tutti` sul deployment definitivo.
- `2.249.36`: dopo il nuovo `Avvia tutti` sul deployment finale, individuata la failure reale del job storico disattivato `legal_updates_gazzetta`; la richiesta manuale di una pianificazione disattivata ora viene registrata come esito completato/non avviato, senza accodare template non autorizzati e senza aumentare i fallimenti. UI della console aggiornata: le righe pausate mostrano un pulsante disabilitato `Pausata`.
- `2.249.37`: durante la verifica finale di produzione è emerso un falso rosso su `legal_source_corte_conti`: la fonte aveva letto e processato 10 documenti, ma il canary veniva marcato come failure perché non erano state pubblicate nuove schede. Il wrapper fonte ora distingue timeout/errori interni da una lettura completata senza pubblicazioni nuove.
