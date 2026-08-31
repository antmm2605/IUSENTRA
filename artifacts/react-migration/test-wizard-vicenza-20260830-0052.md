# Log tecnico — Wizard PST Vicenza R.G. 1084/2026

**Data e ora:** 30/08/2026 00:52–00:58, ora italiana
**Ambiente:** `http://localhost:8080` — container `iusentra-app` sano, immagine `sha256:45f77d81e4e75d5d534521fcfd7da6e954337bd24315d06d8a2a79cfb2832f16` identica al server.
**Local Signer:** `1.6.116`, una sola istanza locale, connessione PKCS#11 disponibile.

## Richiesta registrata

| Campo | Valore |
| --- | --- |
| Ufficio UI | `0640011` — Tribunale di Vicenza |
| Codice PST risolto | `0241160092` |
| R.G. | `1084/2026` |
| Ruolo | `AVV` |
| Profilo | Lavoro (`LAV`) |
| Endpoint locale | `POST /pst/ricerca-snapshot` |
| Tabella effettiva | `JPW_SIL_DISTR` |

## Verifica della tabella

La selezione `JPW_SIL_DISTR` è corretta per il profilo Lavoro. La baseline positiva conserva la regola `LAV → JPW_SIL_DISTR` e documenta che questa è la stessa tabella delle consultazioni reali riuscite. `JPW_SICID` è il default generale dell’ufficio e non deve sovrascrivere il profilo Lavoro.

## Osservazioni durante la prova

- La richiesta ha risolto correttamente il codice UI `0640011` nel codice PST `0241160092`.
- Il Local Signer ha ricevuto due richieste successive di lotto download (`POST /pst/download-documenti-batch-job`) alle 00:54 e alle 00:58.
- Al momento della registrazione il log non contiene ancora l’esito finale numerico del lotto download; nessuna ulteriore richiesta è stata generata da Codex.
- Il monitoraggio non ha aperto una seconda sessione PST né richiesto un ulteriore PIN.

## Nota di integrità

Questo log registra esclusivamente quanto osservato. L’esito funzionale del download sarà annotato dopo la conferma visibile nella UI e nel log del Local Signer.

## Esito del lotto

La UI ha concluso **30/30 documenti elaborati**: **29 documenti PST scaricati e pronti per l’importazione**. Un solo documento non è stato scaricato:

- `ProduzioneDocumentiRichiesti_154017911.pdf` — il PST ha risposto HTTP 502 da `ext.processotelematico.giustizia.it`.

L’avviso individua un errore temporaneo del proxy/servizio ministeriale sul singolo file, non un errore di PIN, certificato o procedura locale. Non è stato effettuato alcun retry automatico né aperta una seconda richiesta PIN.
