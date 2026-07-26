# Clienti, Soggetti e registri pubblici - 26/07/2026

## Obiettivo

Separare in modo governato `Clienti e Anagrafiche` da `Soggetti e Parti`, evitando che clienti dello studio compaiano come soggetti processuali o parti. Il flusso `Nuovo Soggetto` deve inoltre poter partire dai registri pubblici locali ReGIndE e Registro PP.AA. alimentati dal Portale Servizi.

## Regola dati applicata

- Fonte di verità locale: `data/tenants/tenant-8bf98719c459/studio.db`, `source_of_truth=sqlite`.
- Fonte di verità produzione Montagnese: `/data/tenants/studio-legale-giuseppe-montagnese/studio.db`.
- I record storici già presenti in `soggetti` che coincidono con clienti non vengono cancellati in massa: la UI, le API e le opzioni fascicolo li filtrano, mentre i nuovi salvataggi li bloccano.
- I nuovi import da PolisWeb/PST e QuickOrganizer non creano più l'assistito come soggetto/parte: il cliente resta nel fascicolo e in `clienti`; le controparti restano in `soggetti` e `soggetti_parti`.
- Se un import opera su fascicoli SQL, anche i repository `clienti` e `soggetti` vengono riallineati allo stesso `studio.db` prima delle scritture.

## Superfici aggiornate

- `/clienti/nuovo`, tab soggetto: rimosso collegamento a cliente e aggiunto pannello `Registri pubblici`.
- `/soggetti`: rimossa colonna/azione `Cliente collegato`, riepilogo con clienti esclusi dalla rubrica parti.
- `/api/v1/ui/soggetti`: filtra record coincidenti con clienti e dichiara `clients_excluded_from_subjects`.
- `/api/v1/ui/soggetti/registri-pubblici`: cerca nelle cache locali ReGIndE e Registro PP.AA. e restituisce `subjectPatch` compilabile nel form.
- POST `/soggetti/nuovo` e `/soggetti/<id>/modifica`: blocco JSON 409 se il soggetto coincide con un cliente esistente.
- Fascicoli: opzioni soggetti e payload dettaglio escludono clienti dalla lista parti.

## Verifiche eseguite

- `python -m pytest tests/test_react_shell.py::test_route_map_salvataggi_principali_studio_restano_react_json tests/test_react_shell.py::test_react_clienti_nuovo_e_soggetti_api_usa_repository_reali tests/test_react_shell.py::test_soggetti_post_blocca_identita_cliente_esistente tests/test_react_shell.py::test_soggetti_registri_pubblici_riusa_cache_reginde_e_ppaa -q`
- `python -m pytest tests/test_quickorganizer_import.py -q`
- `python -m pytest tests/test_polisweb.py -q --durations=20`
- `python -m compileall pct web`
- `pnpm --filter @iusentra/studio typecheck`
- `pnpm --filter @iusentra/studio test`
- `pnpm --filter @iusentra/studio build`
- `python scripts/audit_tenant_data_structure.py --registry data/tenants.json --repair --json`
- `python scripts/audit_tenant_data_structure.py --registry data/tenants.json --json`
- `python scripts/audit_data_flow_contract.py --registry data/tenants.json --repair-json-mirror --repair-search-index --json`
- `python scripts/audit_data_flow_contract.py --registry data/tenants.json --json`
- `docker compose build --no-cache`
- `docker compose up -d`
- `curl http://127.0.0.1:8080/api/pronto`

## Prova reale locale

Su `http://127.0.0.1:8080/clienti/nuovo?tab=soggetto` è stato verificato nel browser integrato autenticato che:

- il pannello `Registri pubblici` è visibile;
- la ricerca `Avvocatura Milano` restituisce `AVVOCATURA DELLO STATO DI MILANO` da `Registro PP.AA.`;
- l'applicazione del risultato compila `tipo=PUBBLICA_AMMINISTRAZIONE`, `qualifica=CONTROPARTE`, ragione sociale, codice fiscale, partita IVA e PEC;
- nel form soggetto non esiste più alcun campo `id_cliente`.

Su `http://127.0.0.1:8080/soggetti` è stato verificato nel browser integrato autenticato che:

- il caricamento termina con `Dati aggiornati`;
- non compaiono testi o colonne `Cliente collegato`;
- `Martorano Mara`, `Contarese Cristina`, `Merdini Manjola` e `Romeo Letizia Anna Maria` non sono visibili nella rubrica soggetti;
- lo scroll completo non produce overflow orizzontale.

## Stato produzione

Da completare dopo commit e deploy Hetzner sullo stesso commit `2.265.5`: verifica container unico `iusentra-app`, `https://app.iusentra.it/api/pronto`, e controllo read-only che il payload soggetti filtri i clienti storici del tenant Montagnese.
