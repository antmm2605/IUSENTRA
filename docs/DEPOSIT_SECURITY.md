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

In sviluppo, test e deploy cloud l'invio PEC reale lato server resta disabilitato se
`PEC_SEND_ENABLED` non e' impostato esplicitamente a `true`. Il canale operativo
predefinito e' il PC dell'avvocato tramite Local Signer (`http://127.0.0.1:27272`):
il server prepara la busta e il browser la consegna al Local Signer, che usa la
password PEC digitata localmente senza salvarla nel server. Il test SMTP server-side
rimane solo diagnostico per capire blocchi IP/provider e non e' il canale di invio reale.

## Audit

Ogni precontrollo fallito, avviso forte, invio, ricevuta e scarto viene registrato nella timeline del fascicolo PDP o nelle tabelle `deposit_*` quando il workflow generico e' usato.
