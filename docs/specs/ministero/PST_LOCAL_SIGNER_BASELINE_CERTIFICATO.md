# PST e Local Signer: baseline certificato

Data baseline operativo: 2026-05-11.
Data blindatura regressione: 2026-05-25.

Questo documento registra le regole funzionali certificate con test reale su PST/PolisWeb e Local Signer. Ogni modifica futura a ricerca fascicolo, anteprima, sessione PST o download documenti deve preservare queste invarianti oppure dichiarare in modo esplicito una nuova certificazione reale.

## Invarianti bloccanti

- La connessione al portale non basta: se l'utente cerca per numero e anno di ruolo, la ricerca deve essere esatta sul fascicolo e non deve aggiungere assistito, controparte o codice fiscale come filtri restrittivi.
- La selezione degli uffici nel wizard deve inviare sempre il `codice` ufficio importato dal catalogo ministeriale locale; `codice_ministero` / `codiceMinistero` resta solo traduzione interna per Local Signer/PST o fallback quando il codice ufficio manca. Esempio certificato: Tribunale di Palmi selezionato come `0910011`, con traduzione PST interna `0800570094`.
- Se il browser conserva un vecchio parametro `ufficio_codice` pari al `codiceMinistero`, la UI deve normalizzarlo al `codice` ufficiale prima della chiamata al Local Signer. Questa regola impedisce che cache, link o ricerche precedenti riportino Palmi a `0800570094` nel payload React o nel wizard classico.
- Il wizard React e il wizard classico devono attendere o risolvere il catalogo uffici prima di avviare una ricerca PST automatica: se l'utente parte da nome ufficio, codice ufficiale o `codiceMinistero`, il payload verso Local Signer deve contenere il `codice` ufficiale quando il catalogo lo conosce.
- Nella ricerca snapshot il registro principale resta quello del catalogo uffici. Se il registro non restituisce righe, il fallback deve restare nello stesso ufficio e nello stesso batch. Per SIECIC i nomi servizio qbuilder sono quelli del catalogo ministeriale locale: `InfoFascicolo` per la ricerca, `ProfiloFascicolo` per i metadati e `ElencoDocumenti` per il catalogo documenti; non vanno riusati i nomi SICID `RicercaInformazioniFascicoloPerTipo` e `DocumentiFascicolo` su SIECIC.
- Ogni ricerca reale PST dal browser deve salvare sul server dello studio una diagnosi operativa tenant-aware con ufficio, codice risolto, R.G./anno, versione Local Signer, risposta/fault e log locale sanificato quando disponibile. La diagnosi non deve includere PIN, credenziali o token di sessione sensibili.
- La visualizzazione del fascicolo usa la sessione PST già aperta dal Local Signer e passa sempre `pst_session_id` alle chiamate successive.
- Non deve esistere una chiamata preventiva `/pst/preflight-auth` nel wizard React o nel wizard classico: il PIN deve essere richiesto solo quando serve davvero al portale. Il Local Signer, però, deve eseguire internamente il preflight certificato come gate obbligatorio prima della ricerca operativa, dello snapshot, del catalogo documenti e del download batch; un rifiuto certificato/HTTP 401 non deve mai diventare "nessun fascicolo trovato".
- Su Windows, mentre `curl` attende il certificato client del PST, il Local Signer deve provare in modo best-effort a portare in primo piano la finestra PIN/Sicurezza Windows/smart card/CNS/CIE/Bit4id/Aruba/token, senza cambiare il numero di PIN richiesti e senza salvare PIN o chiavi.
- Il comportamento certificato resta: un PIN per visualizzare il fascicolo e un PIN separato solo per scaricare l'intero fascicolo.
- Il download dell'intero fascicolo usa `/pst/download-documenti-batch` e `preflight_auth: false`; non deve tornare al download singolo ripetuto come flusso principale React.
- Il pacchetto Windows del Local Signer resta blindato sul profilo certificato `SetupLocalSigner-1.6.35.exe`: builder nativo IExpress, SED `Class=IEXPRESS` / `InsideCompressed=0`, file pubblico solo `SetupLocalSigner-<versione>.exe` con alias `SetupLocalSigner.exe`, avvio `powershell.exe -NoProfile -ExecutionPolicy Bypass -File installa_local_signer_locale.ps1` e file principali copiati dal CAB locale. Non si introducono PyInstaller, NSIS, zip autoestraenti, download pubblico `.ps1` o download dinamici dei file principali durante l'installazione Windows senza nuova certificazione reale e test aggiornati.
- Il Local Signer non deve salvare PIN, credenziali CNS/CIE/SPID o sessioni portale nel cloud.
- Il tenant dello studio resta separato: i fascicoli interni di uno studio non devono essere usati come fallback per un altro studio.

## Presidi automatici

I presidi sono parte del gate `Local Signer boundaries` eseguito in CI Quality Overlay:

- `tools/check_local_signer_boundaries.py` verifica la presenza delle invarianti sopra in `tools/local_signer.py`, `tools/dist/local_signer.py`, `frontend/src/components/TelematicoSurfacePage.tsx` e `web/templates/portale/acquisizione_wizard.html`.
- `tests/test_local_signer.py` verifica che la SOAP di ricerca esatta numero/anno non includa `nomeParte` o `codiceFiscaleParte`, mentre la ricerca per parte continui a usarli.
- `tests/test_local_signer.py::test_local_signer_pst_curl_attiva_foreground_prompt_pin_windows` verifica che i `curl` PST usino l'helper di foreground della finestra PIN su Windows.
- `tests/test_react_shell.py` e `tests/test_polisweb.py` impediscono il ritorno di preflight PIN dal wizard, verificano la normalizzazione del codice ufficio e bloccano il filtro parte/CF nelle ricerche esatte del wizard.
