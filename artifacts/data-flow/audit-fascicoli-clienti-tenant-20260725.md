# Audit fascicoli/clienti tenant Montagnese - 25/07/2026

## Segnalazione

Nello Studio Legale Giuseppe Montagnese era stato creato il fascicolo `2026/344` con cliente `Martorano Mara`; il fascicolo risultava salvato, ma la scheda cliente non era rintracciabile in anagrafica.

## Diagnosi

- Tenant locale configurato: `studio-montagnese`, storage `tenant-8bf98719c459`.
- Tenant reale di produzione verificato nel container Hetzner: `/data/tenants/studio-legale-giuseppe-montagnese`.
- Fonte di verità usata per la diagnosi: SQLite `studio.db`; i JSON sono stati trattati solo come mirror.
- Il fascicolo `2026/344` era presente in produzione:
  - `id`: `B494AAB9`
  - `numero`: `2026/344`
  - `titolo`: `Martorano Mara c. MIM`
  - `id_cliente`: `BA82D89F`
  - `nome_cliente`: `Martorano Mara`
- La riga cliente `BA82D89F` non esisteva nella tabella `clienti` dello stesso `studio.db` e non era presente nel mirror `clienti/anagrafica.json`.
- L'audit produzione ha trovato 4 link fascicolo-cliente orfani nello stesso tenant:
  - `2026/337` / `13985944` / `Contarese Cristina`
  - `2026/340` / `9EDEB3C2` / `Merdini Manjola`
  - `2026/342` / `A70B2974` / `Romeo Letizia Anna Maria`
  - `2026/344` / `BA82D89F` / `Martorano Mara`

## Causa accertata

La route `/fascicoli/nuovo` accettava un `id_cliente` proveniente dal form anche quando `get_clienti().get(id_cliente)` non restituiva alcuna scheda. In quel caso salvava comunque il fascicolo con `id_cliente` valorizzato e `nome_cliente` non governato, creando un riferimento orfano. La route `/fascicoli/<id>/modifica` aveva un rischio simile durante il cambio cliente.

Il problema non era un difetto di ricerca UI: il dato era incoerente nella fonte SQL del tenant.

## Riparazione dati produzione

Eseguita sul container `iusentra-app`, tenant `/data/tenants/studio-legale-giuseppe-montagnese`.

Backup creati prima della scrittura:

- SQLite: `/data/tenants/studio-legale-giuseppe-montagnese/backup/client_link_repair/studio.before-client-link-repair-20260725211010.db`
- Mirror clienti: `/data/tenants/studio-legale-giuseppe-montagnese/backup/client_link_repair/anagrafica.json.before-client-link-repair-20260725211010.bak`

Clienti ricostruiti nella tabella `clienti` e nel mirror `clienti/anagrafica.json`:

- `13985944` / `Contarese Cristina`
- `9EDEB3C2` / `Merdini Manjola`
- `A70B2974` / `Romeo Letizia Anna Maria`
- `BA82D89F` / `Martorano Mara`

Verifica post-riparazione: `orphans_after_repair=[]`; la join `fascicoli -> clienti` risolve correttamente i quattro fascicoli, incluso `2026/344`.

## Correzioni codice

- `pct/fascicoli.py`
  - Aggiunto guardrail tenant-aware in `GestioneFascicoli`: quando `studio_db` è attivo, ogni `id_cliente` viene verificato nella tabella `clienti` dello stesso database.
  - Il `nome_cliente` del fascicolo viene riallineato dal record SQL cliente, evitando coppie id/nome incoerenti.
  - `nuovo()` e `aggiorna()` bloccano il salvataggio se il cliente selezionato non esiste nel tenant corrente.
- `web/bootstrap/fascicoli_create_routes.py`
  - La creazione fascicolo ora blocca subito un cliente selezionato ma assente dall'anagrafica dello studio, con messaggio operativo puntuale.
- `web/bootstrap/fascicoli_management_routes.py`
  - La modifica fascicolo applica lo stesso controllo e restituisce il messaggio specifico di validazione.
- `scripts/audit_fascicoli_clienti_links.py`
  - Nuovo audit/riparazione CLI per trovare link fascicolo-cliente orfani su `studio.db`.
  - In modalità `--repair` crea backup, ricostruisce schede cliente minime in SQL e aggiorna il mirror JSON.
- `scripts/audit_tenant_data_structure.py`
  - Classificate le cache `email/.preview-cache/**` come `cache_rigenerabile`, non come JSON operativi non censiti.
- `scripts/react-migration/check-full-react-route-contract.mjs`
  - Il gate ora legge anche i blueprint API modulari già governati (`client_portal`, `daily_plan`, `legal_skills`) e riconosce gli alias reali delle route parametrizzate.
- `frontend/src/components/FatturazionePage.tsx`
  - Rimossa l'anteprima fiscale canonica calcolata nel browser: il frontend raccoglie input, mentre numerazione, imponibile, CPA, IVA, ritenuta e totale restano governati dal backend tenant-aware.
- `frontend/src/components/RedazioneAttiPage.tsx`
  - Aggiunti stati visibili di errore e caricamento riuscito sul payload JSON.

## Riparazione locale

La copia locale `data/tenants/tenant-8bf98719c459/studio.db` aveva tabelle core leggibili ma `PRAGMA quick_check` non era pulito. È stata eseguita una ricostruzione SQLite conservativa con `VACUUM INTO` e sostituzione solo dopo `quick_check=ok`.

Backup locale creato:

- `data/tenants/tenant-8bf98719c459/backup/sqlite_repack_recovery/studio_before_repack_20260725211122.db`

Risultato finale locale: `PRAGMA quick_check=ok`.

## Audit route React/Jinja

Controlli eseguiti sul perimetro full React:

- `node scripts/react-migration/check-no-primary-html-post.mjs`: `OK`
- `node scripts/react-migration/check-no-legacy-post-form.mjs`: `OK`
- `node scripts/react-migration/check-route-gate.mjs`: `OK`
- `node scripts/react-migration/check-full-react-route-contract.mjs`: `OK`

Esito: nessuna route dichiarata full React contiene un form HTML `POST` primario o `LegacyPostForm`; i salvataggi principali devono passare dagli endpoint JSON governati.

## Test e audit eseguiti

- `python -m pytest tests/test_fascicoli.py::test_nuovo_sql_blocca_cliente_mancante_nel_tenant tests/test_fascicoli.py::test_nuovo_sql_riallinea_nome_cliente_da_anagrafica_tenant tests/test_fascicoli.py::test_aggiorna_sql_blocca_cambio_su_cliente_mancante tests/test_fascicoli_clienti_links_audit.py tests/test_storage_strategy.py::test_audit_tenant_data_structure_tratta_preview_cache_email_come_cache -q`
- `python -m compileall pct/fascicoli.py web/bootstrap/fascicoli_create_routes.py web/bootstrap/fascicoli_management_routes.py scripts/audit_fascicoli_clienti_links.py scripts/audit_tenant_data_structure.py`
- `python scripts/audit_fascicoli_clienti_links.py --studio-db data/tenants/tenant-8bf98719c459/studio.db --json`
- `python scripts/audit_data_flow_contract.py --registry data/tenants.json --tenant studio-montagnese --repair-json-mirror --repair-search-index --json`
- `python scripts/audit_tenant_data_structure.py --registry data/tenants.json --tenant studio-montagnese --repair`
- `python scripts/audit_tenant_data_structure.py --registry data/tenants.json --tenant studio-montagnese`

Esiti locali: `source_of_truth=sqlite`, `json_authoritative=false`, `quick_check=ok`, nessun link fascicolo-cliente orfano, nessuna mancanza nella struttura tenant.

## Verifica reale locale

Prima della pulizia dei record controllati è stata eseguita una prova materiale nel browser integrato su `http://127.0.0.1:8080`:

- creazione cliente controllato `CodexTenant Prova20260725192607`;
- creazione fascicolo collegato `CodexTenant Prova20260725192607 c. Verifica Tenant`;
- apertura del dettaglio fascicolo React;
- verifica SQL della join `fascicoli -> clienti` nello stesso `studio.db`;
- audit post-salvataggio con `orphans=[]`.

I record controllati creati per la prova sono stati eliminati usando i repository interni `GestioneFascicoli.elimina()` e `GestioneClienti.elimina()`. La password locale temporanea di collaudo è stata ripristinata e il file temporaneo rimosso.

Dopo rebuild Docker locale senza cache, container `iusentra-app` healthy e `/api/pronto` su versione `2.265.1`, è stata ripetuta la prova reale sul browser integrato:

- apertura React `/clienti/nuovo`, compilazione e click reale su `Salva cliente`;
- cliente salvato: `184A5F99`, `Verifica202607252152 CodexTenant PostRebuild202607252152`;
- apertura React `/fascicoli/nuovo`, selezione del cliente appena creato dal select tenant-aware e click reale su `Crea fascicolo`;
- fascicolo creato: `906A1FCB`, `CodexTenant PostRebuild 202607252152 c. Verifica Tenant`, `RG 344999/2026`, `numero 2026/011`;
- dettaglio fascicolo React aperto e scroll reale dall'alto fino al fondo (`scrollTop=3135`, fondo raggiunto);
- verifica SQL della join nello stesso `studio.db`: `fascicoli.id_cliente=184A5F99` e `clienti.id=184A5F99`;
- audit post-salvataggio: `source_of_truth=sqlite`, `json_authoritative=false`, `orphans=[]`.

I record controllati `906A1FCB` e `184A5F99` sono stati eliminati con `GestioneFascicoli.elimina()` e `GestioneClienti.elimina()`. Verifica post-pulizia: record assenti, `PRAGMA quick_check=ok`, audit anti-orfani ancora `orphans=[]`, struttura tenant senza mancanze.

## Follow-up 26/07/2026 - clienti presenti in SQL ma non visibili in UI

Dopo la segnalazione dell'utente ("non li vedo in Clienti e Anagrafiche") è stata verificata la fonte reale Hetzner usata dal runtime: `IUSENTRA_DATA_DIR=/opt/iusentra/data`.

Controlli eseguiti sul tenant produzione reale:

- `studio.db`: `/opt/iusentra/data/tenants/studio-legale-giuseppe-montagnese/studio.db`;
- `PRAGMA quick_check=ok`;
- tabella `clienti` presente;
- tabella `fascicoli` presente;
- i clienti `13985944`, `9EDEB3C2`, `A70B2974`, `BA82D89F` risultavano presenti in SQL e nel mirror `clienti/anagrafica.json`;
- la join `fascicoli -> clienti` risultava corretta per `2026/337`, `2026/340`, `2026/342`, `2026/344`;
- non c'erano più link fascicolo-cliente orfani.

Il problema residuo non era più un orfano SQL: i record venivano scartati dal repository applicativo in lettura. Causa tecnica: il payload storico `dati_json.documento` conteneva la chiave extra `file_path`; `Cliente.from_dict()` non filtrava le chiavi non supportate di `DocumentoIdentita` e quindi sollevava `TypeError`, poi `GestioneClienti._carica()` saltava la scheda.

Correzione codice:

- `pct/clienti.py`: `Cliente.from_dict()` filtra ora il payload `documento` sulle sole chiavi supportate da `DocumentoIdentita`, come già avveniva per i recapiti.
- `tests/test_fascicoli_clienti_links_audit.py`: aggiunta copertura che una scheda cliente riparata resta visibile da `GestioneClienti` anche se `dati_json.documento` contiene la chiave storica extra `file_path`.

Questa correzione evita che un cliente presente e collegato nel tenant venga nascosto dalla UI per payload documento legacy o arricchito.
