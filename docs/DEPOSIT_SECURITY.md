# Sicurezza deposito telematico

## Regole invarianti

- Conferma umana obbligatoria prima di firma o invio reale.
- Controlli deterministici prima di eventuale supporto Lex AI.
- Nessun salvataggio di PIN, password token o credenziali PEC in chiaro.
- Nessun reinvio automatico dopo scarto senza nuova conferma dell'avvocato.
- Nessuna automazione nascosta sui portali ufficiali.

## Feature flag

Le integrazioni reali devono rispettare questi flag:

- `LEGAL_DEPOSIT_ENABLED`
- `PEC_SEND_ENABLED`
- `PEC_WATCHER_ENABLED`
- `SIGNATURE_ENABLED`
- `DEPOSIT_SANDBOX_MODE`

In sviluppo e test, l'invio reale resta disabilitato se `PEC_SEND_ENABLED` non e' impostato esplicitamente a `true`.

## Audit

Ogni precontrollo fallito, avviso forte, invio, ricevuta e scarto viene registrato nella timeline del fascicolo PDP o nelle tabelle `deposit_*` quando il workflow generico e' usato.

