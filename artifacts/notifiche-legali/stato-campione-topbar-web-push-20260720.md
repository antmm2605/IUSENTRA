# Stato campione: Presidio, Agenda, topbar e Web Push

Aggiornato: 20/07/2026 23:39 Europe/Rome.

## Risultati visibili sul server

- Nel tenant `Studio Legale Giuseppe Montagnese` il Presidio mostra Romeo Maria / R.G. 1428/2026 / Tribunale di Palmi e Alfano Giuseppe / R.G. 1100/2026 / Tribunale di Padova con il caso italiano `Sentenza da valutare per la notifica`.
- Non sono visibili codici interni nella tabella o nel dettaglio dei due casi campione.
- L'Agenda non mostra più per Alfano e Romeo la falsa `Opposizione alla trattazione scritta`.
- La topbar mostra subito i due titoli completi con nominativo, pratica e R.G.

## Correzione applicata

La campanella rileggeva agenda, scadenziario, PEC, fascicoli e documenti a ogni apertura. Questo causava caricamenti oltre il normale intervallo di aggiornamento. La topbar ora legge esclusivamente il repository notifiche persistente e tenant-aware; la materializzazione resta nei job/eventi PEC e Agenda, fuori dalla UI.

Il fix non ha modificato fascicoli, PEC, scadenze, appuntamenti, invii o prove di notifica.

## Web Push

La configurazione VAPID del server è presente e il backend Web Push risulta configurato. Non è stata accettata alcuna richiesta di permesso del browser e non è stata inviata una notifica di prova: manca quindi la sottoscrizione consapevole del dispositivo reale prima di poter dimostrare la consegna sul telefono.

## Test eseguiti

```powershell
python -m pytest -q tests\test_topbar_operational_api.py::test_topbar_today_notifications_deadlines_recent_and_timer tests\test_topbar_hooks.py --tb=short
```

Esito: 3 test superati.

## Cosa resta da fare, nell'ordine vincolante

1. Verificare il medesimo campione nella copia reale locale `http://127.0.0.1:8080` dopo il riallineamento del codice.
2. Attivare il consenso Web Push sul dispositivo reale e inviare una notifica di prova, senza esporre dati sensibili nella notifica.
3. Rieseguire la prova delle quattro superfici: Presidio, Agenda, topbar e Web Push.
4. Solo se il campione resta corretto e rapido, avviare l'audit incrementale dei 301 fascicoli e riportare esclusivamente i residui effettivamente da notificare.
5. Completare i gate, aggiornare la copia locale, commit, push dei due branch e deploy finale ordinato.

Lo stato non è conclusivo: l'audit dei 301 fascicoli non è stato avviato in questo ciclo.

## Aggiornamento 21/07/2026 22:45 Europe/Rome

La riconciliazione server-first sul tenant `Studio Legale Giuseppe Montagnese` ha eliminato il rumore storico delle sentenze già gestite e ha lasciato pubblicati solo i presìdi stabili ancora operativi.

Esito SQL dopo il secondo passaggio idempotente:

- presìdi notifiche attivi: `5`;
- duplicati attivi in `pec_legal_notification_presidia`: `0`;
- notifiche operative/topbar attive con `source_type=legal_notification_presidio`: `5`;
- righe Scadenziario operative con marker `IUSENTRA_LEGAL_NOTIFICATION`: `5`;
- vecchie righe PEC `sentenza_da_valutare_per_notifica` senza marker stabile ancora aperte: `0`.

Residui reali mostrati come da valutare/notificare: Calabrò Daniela, Speranza Carmelina, Monea Mariano, Alfano Giuseppe e Romeo Maria, ciascuno con PEC e allegato sorgente nominati.

Guardrail eseguito:

```powershell
python -m pytest -q tests/test_notification_relata_materializer.py
```

Esito: `5` test superati.

Resta da fare: prova reale browser in produzione su Presìdi notifiche, Scadenziario, Agenda, topbar e fonte PEC; poi riallineamento locale su `127.0.0.1:8080`, gate, commit, push dei branch gemelli e deploy finale.
