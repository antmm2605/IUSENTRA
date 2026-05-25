# PST e Local Signer: baseline certificato

Data baseline operativo: 2026-05-11.
Data blindatura regressione: 2026-05-25.

Questo documento registra le regole funzionali certificate con test reale su PST/PolisWeb e Local Signer. Ogni modifica futura a ricerca fascicolo, anteprima, sessione PST o download documenti deve preservare queste invarianti oppure dichiarare in modo esplicito una nuova certificazione reale.

## Invarianti bloccanti

- La connessione al portale non basta: se l'utente cerca per numero e anno di ruolo, la ricerca deve essere esatta sul fascicolo e non deve aggiungere assistito, controparte o codice fiscale come filtri restrittivi.
- La visualizzazione del fascicolo usa la sessione PST già aperta dal Local Signer e passa sempre `pst_session_id` alle chiamate successive.
- Non deve esistere una chiamata preventiva `/pst/preflight-auth` nel wizard React o nel wizard classico: il PIN deve essere richiesto solo quando serve davvero al portale.
- Il comportamento certificato resta: un PIN per visualizzare il fascicolo e un PIN separato solo per scaricare l'intero fascicolo.
- Il download dell'intero fascicolo usa `/pst/download-documenti-batch` e `preflight_auth: false`; non deve tornare al download singolo ripetuto come flusso principale React.
- Il Local Signer non deve salvare PIN, credenziali CNS/CIE/SPID o sessioni portale nel cloud.
- Il tenant dello studio resta separato: i fascicoli interni di uno studio non devono essere usati come fallback per un altro studio.

## Presidi automatici

I presidi sono parte del gate `Local Signer boundaries` eseguito in CI Quality Overlay:

- `tools/check_local_signer_boundaries.py` verifica la presenza delle invarianti sopra in `tools/local_signer.py`, `tools/dist/local_signer.py`, `frontend/src/components/TelematicoSurfacePage.tsx` e `web/templates/portale/acquisizione_wizard.html`.
- `tests/test_local_signer.py` verifica che la SOAP di ricerca esatta numero/anno non includa `nomeParte` o `codiceFiscaleParte`, mentre la ricerca per parte continui a usarli.
- `tests/test_react_shell.py` e `tests/test_polisweb.py` impediscono il ritorno di preflight PIN e del filtro parte/CF nelle ricerche esatte del wizard.
