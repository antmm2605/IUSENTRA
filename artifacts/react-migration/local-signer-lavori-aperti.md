# Local Signer - lavori aperti obbligatori

Data apertura: 28 giugno 2026

Questo file è la lista operativa da rileggere dopo ogni compattazione prima di proseguire sul Local Signer. Nessun punto va considerato chiuso senza codice, test mirati, documentazione e verifica reale sulla copia IUSENTRA `http://127.0.0.1:8080`.

## Perimetro funzionale da preservare

- Firma digitale singola e multipla, inclusa richiesta PIN e salvataggio degli esiti.
- Servizio locale `http://127.0.0.1:27272` e protocollo `iusentra-local-signer://`.
- Aggiornamento automatico e installazione guidata del Local Signer.
- PEC e posta elettronica gestite dal PC locale quando il flusso richiede segreti o invii operativi.
- Assistenza remota tramite Local Signer, inclusi screenshot e comandi autorizzati.
- Bridge AI locale, controlli PST/portali, ricerca telematica e download collegati.
- Avvio silenzioso dei processi di supporto, senza finestre terminale o schermate curl visibili.

## Difetti segnalati dall'utente

- L'installazione o aggiornamento automatico non parte piu' come prima dopo la verifica versione.
- Su Windows 11, dopo prima installazione su un nuovo PC, il servizio non risponde su `127.0.0.1:27272`.
- La console dell'installer mostra "Installazione completata con avviso" e chiede di avviare di nuovo il servizio.
- I pulsanti `Verifica Local Signer`, `Avvia e verifica`, `Aggiorna automaticamente` e `Vai alla ricerca` perdono leggibilita' in hover/focus.
- Le chiamate curl o equivalenti producono rumore visivo con finestre che si aprono e si chiudono.
- La richiesta PIN resta incastrata nella barra di Windows invece di emergere chiaramente davanti all'utente.

## Lavori da chiudere

1. Analizzare tutte le funzioni Local Signer senza limitarle alla firma.
2. Correggere l'installer Windows affinché installi tutte le dipendenze richieste, includendo quelle necessarie ad assistenza remota e posta.
3. Rendere l'avvio del servizio locale silenzioso ma diagnosticabile con log, senza finestre terminale visibili.
4. Ripristinare aggiornamento automatico e avvio automatico governato dove gia' previsto dal flusso.
5. Garantire che le invocazioni curl/subprocess su Windows usino esecuzione nascosta senza finestre.
6. Correggere hover, focus, disabled e loading dei pulsanti Local Signer nella pagina Servizi Telematici.
7. Correggere il flusso PIN: finestra in primo piano o istruzione UI esplicita se il provider token non consente forzatura sicura.
8. Blindare il tutto con test mirati su installer, servizio, frontend React e guardrail anti-regressione.
9. Aggiornare `artifacts/react-migration/procedura-deposito-telematico.md` con diagnosi, modifiche, test e verifica reale.
10. Rigenerare i pacchetti Local Signer versionati se cambia installer o servizio.
11. Verificare materialmente su `http://127.0.0.1:8080` con browser reale: hover/focus, avvio, aggiornamento, installazione, PIN dove possibile e stato servizio.
12. Eseguire commit, push sui branch gemelli, controlli GitHub, deploy Hetzner e pulizia Docker secondo `AGENTS.md`.

## Stato corrente

- Stato: aperto.
- Verifica reale su macchina dell'utente: eseguita parzialmente il 28 giugno 2026 su `http://127.0.0.1:8080`, route `/portali/pst/acquisizione`, Docker locale ricostruito e healthy.
- UI Local Signer: nello step `Accesso` i pulsanti `Avvia e verifica`, `Aggiorna automaticamente` e `Vai alla ricerca` ora riusano la stessa logica visiva di `Verifica Local Signer`; il CSS definitivo `TelematicoSurfacePage-xPye0zGo.css` forza normale/hover/focus con testo e icone bianchi su sfondo blu.
- Link secondario: `Installa o aggiorna` resta leggibile con testo scuro su sfondo bianco; il fix non introduce bianco-su-bianco sui link.
- Verifica visiva locale dopo rebuild Docker: browser integrato su `http://127.0.0.1:8080/portali/pst/acquisizione`, step `Accesso`, scroll alla sezione Local Signer; `Avvia e verifica`, `Aggiorna automaticamente` e `Vai alla ricerca` sono visibili e leggibili con colore computato `rgb(255, 255, 255)` su `rgb(29, 78, 216)`, coerente con `Verifica Local Signer`.
- Hover materiale: il puntatore automatizzato del browser integrato non espone `matches(':hover')`, ma il browser visibile e le regole CSS confermano che hover/focus non cambiano testo, icone, opacità o mix-blend; ripetere solo se l'utente segnala ancora sparizione con mouse fisico.
- Aggiornamento automatico: verificato dalla UI locale; il servizio Local Signer risponde con versione `1.6.83`.
- Servizio locale: `ping?light=1` e `support/status` rispondono; runtime locale con `pillow`, `pkcs11`, `send_pec_local` e `test_pec_smtp_local` disponibili.
- PIN reale: aperto, perché sulla macchina non è stato rilevato un token PKCS#11 fisico; non dichiarare chiuso finché non viene provata la finestra PIN davanti all'utente.
- Nessun punto è chiuso definitivamente finché non è riportato qui con data, commit, prova eseguita, push gemelli, controlli GitHub e deploy Hetzner.
