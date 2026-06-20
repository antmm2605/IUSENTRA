# Prova reale locale: Sentenza Lex AI, economia e fatturazione 2.253.86

Data prova: 2026-06-20.

## Ambiente

- Copia reale locale: `http://127.0.0.1:8080`.
- Versione verificata: `2.253.86`.
- Docker locale: `app`, `scheduler-worker`, `ocr-worker` e `redis` in stato healthy dopo rebuild e riavvio.
- Health finale: `/api/pronto` ha risposto `{"ok":true,"stato":"pronto","versione":"2.253.86"}`.
- Browser reale visibile: `C:\Program Files\Google\Chrome\Application\chrome.exe`.
- Nota tecnica: il browser integrato Codex non era controllabile tramite Node REPL per errore MCP `missing field sandboxPolicy`; la prova materiale è stata quindi eseguita in Google Chrome installato con remote debugging e profilo temporaneo locale.

## Prova UI fatturazione

- Aperta `/fatturazione` con React attivo e sessione locale autenticata.
- Verificati header, avvisi economici, KPI, archivio, card e scroll completo fino al fondo.
- Verificato pannello `Numerazione fatture`: focus sul campo `Ultimo numero usato`, click su `Salva numerazione`, messaggio visibile `Numerazione fatture aggiornata.` e risposta API `POST /api/v1/ui/fatturazione/numerazione` 200 dopo riavvio servizi.
- Verificato responsive desktop, tablet e mobile; tablet/mobile senza overflow orizzontale.

Screenshot principali:

- `C:\Users\antmm\AppData\Local\Temp\iusentra-fatturazione-desktop-20260620-203229.png`
- `C:\Users\antmm\AppData\Local\Temp\iusentra-fatturazione-tablet-20260620-203229.png`
- `C:\Users\antmm\AppData\Local\Temp\iusentra-fatturazione-mobile-20260620-203229.png`
- `C:\Users\antmm\AppData\Local\Temp\iusentra-fatturazione-numbering-after-retry-20260620-203704.png`

## Prova UI proforma

Per provare i pulsanti richiesti dall'utente senza usare dati di produzione, sono state create due proforme controllate nel tenant locale con origine `Sentenza Lex AI`. I record sono stati rimossi dal DB locale al termine della prova.

- Proforma controllata `2026/001`: click reale su `Emetti parcella`; stato finale osservato in UI e DB: `Fattura`, `Emessa`.
- Proforma controllata `2026/002`: click reale su `Registra bonifico`; stato finale osservato in UI e DB: `Fattura`, `Pagata`, incasso `20/06/2026`.
- I log app mostrano `POST /api/v1/ui/fatturazione/<id>/stato` 200 e `POST /api/v1/ui/fatturazione/<id>/segna-pagata` 200.
- Dopo pulizia runtime, il conteggio dei due ID controllati in `parcelle` è tornato a `0`.

Screenshot principali:

- `C:\Users\antmm\AppData\Local\Temp\iusentra-proforma-controlled-before-20260620-204445.png`
- `C:\Users\antmm\AppData\Local\Temp\iusentra-proforma-controlled-after-bonifico-20260620-204445.png`
- `C:\Users\antmm\AppData\Local\Temp\iusentra-proforma-controlled-final-20260620-204543.png`

## Prova UI fascicoli

- Aperta `/fascicoli` sulla copia reale locale.
- Verificate metriche, lista fascicoli, colonne `Prossima scad.` e `Stato`, tab e assenza di overlay di errore o fallback legacy.
- Screenshot: `C:\Users\antmm\AppData\Local\Temp\iusentra-fascicoli-desktop-20260620-203229.png`.

## Problema risolto durante la prova

Durante i salvataggi locali è riemerso il lock SQLite del volume Windows/Docker (`database is locked`). La prova non è stata dichiarata positiva su quel primo tentativo. Sono stati riavviati `app`, `scheduler-worker` e `ocr-worker`, verificata una scrittura di probe, ripetuto il click sul pannello numerazione e completata la prova proforma. Per rimuovere i record controllati è stato necessario fermare i servizi applicativi, cancellare solo i due ID di test dal `studio.db`, eliminare la tabella temporanea `codex_lock_probe` e riavviare la copia reale. Health finale OK.

## Limite residuo

La verifica locale copre estrazione, matrice dati, proforma, numerazione, bridge React e DB vettoriale tramite test mirati e dati controllati. I fascicoli con sentenze reali citati dall'utente si trovano sul server: dopo commit, push, check GitHub e deploy Hetzner, va eseguita la prova produzione su `https://app.iusentra.it`, controllando almeno un documento `Sentenza Tribunale` reale, la matrice economia del fascicolo, la proforma generata e l'indicizzazione Lex AI.
