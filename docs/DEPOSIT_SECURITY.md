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
- `PEC_WATCHER_ENABLED`
- `SIGNATURE_ENABLED`
- `DEPOSIT_SANDBOX_MODE`

Per i depositi e le notifiche legali operative il server non e' canale SMTP reale.
Il canale operativo e' il PC dell'avvocato tramite Local Signer
(`http://127.0.0.1:27272`) oppure, per i canali che lo prevedono, il portale
ufficiale. Il server prepara e verifica pacchetto, destinatario, oggetto, corpo,
allegati e ricevute; il browser consegna il payload al Local Signer, che usa la
password PEC digitata localmente senza salvarla nel server. Il test SMTP
server-side resta solo diagnostico per capire blocchi IP/provider e non e' il
canale di invio reale.

Dal collaudo `2.253.57` la password PEC non può essere richiesta con
`window.prompt`, perché il browser integrato può bloccarlo e lasciare il
flusso senza completamento. Il flusso corretto mostra una modale React
`Password PEC locale`, con riepilogo mittente, destinatario, oggetto e allegati,
chiude la conferma precedente prima della chiamata locale e invia la password
solo al Local Signer sul PC in uso. La password resta stato temporaneo del
browser e non viene inserita nel payload di conferma server.

## Audit

Ogni precontrollo fallito, avviso forte, invio, ricevuta e scarto viene registrato nella timeline del fascicolo PDP o nelle tabelle `deposit_*` quando il workflow generico e' usato.
