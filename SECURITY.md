# Security Policy

Aggiornato: 2026-05-14, fase 12 `fasereact`.

IUSENTRA tratta dati professionali, documenti, comunicazioni PEC/email, dati fiscali e informazioni potenzialmente sensibili di studi legali. Le regole qui sotto sono operative: non inserire segreti, token, password, PEC reali o dati personali reali nella repository, nei test o nei report.

## Security model

- Autenticazione: sessione web o API key tenant-aware dove ammessa.
- RBAC: il backend e' sempre fonte autoritativa; il frontend nasconde azioni solo come UX.
- Tenant isolation: ogni repository usa tenant corrente da request/sessione/API key; in multi-studio senza tenant valido si fallisce chiusi.
- Feature flag: i flag App V2 sono default-off e il backend applica enforcement sulle route sensibili.
- Audit log: azioni sensibili, denial e modifiche governate devono essere auditabili senza esporre payload sensibili.
- Denial log: `policy_denied`, `backend_security_control_param`, `feature_flag_denied` e denial tenant non devono includere segreti o valori client vietati.

## Multi-tenancy

Origine contesto tenant:

- sessione utente autenticata;
- `g.data_paths` e runtime tenant-aware;
- API key studio validata da `web/services/tenant_api_auth.py`.

Regole:

- il client non puo' inviare `tenant_id`, `tenant_slug`, `studio_id`, `studio_slug`, `user_id`, token o redirect liberi per cambiare contesto;
- cross-tenant deve risultare in errore controllato (`403`, `404` o `400` secondo il caso) senza confermare esistenza di risorse di altro studio;
- nessun fallback silenzioso a path globali per PEC, email ordinaria, fascicoli, agenda, impostazioni, fatturazione, preventivi o documenti;
- test richiesti: `tests/test_tenant_isolation_runtime.py`, `tests/test_backend_security_phase5.py`, test storage/API collegati alla modifica.

## RBAC

Ruoli e permessi reali sono gestiti nel dominio auth e nei profili applicativi. Regole:

- il backend verifica permesso prima di leggere o scrivere dati;
- route admin/settings/database/audit richiedono permessi espliciti;
- scritture su dati operativi richiedono permesso di scrittura del dominio;
- il frontend non deve permettere escalation via campi nascosti o payload JSON.

Documenti collegati:

- [docs/security-rbac-tenant-isolation.md](docs/security-rbac-tenant-isolation.md)
- [docs/backend-endpoint-security-map.md](docs/backend-endpoint-security-map.md)

## PII e dati sensibili

Non loggare e non committare:

- password, hash password, token, API key, private key, PIN, segreti provider;
- contenuti integrali di atti, documenti, allegati, PEC o email;
- codici fiscali, IBAN, dati sanitari o dati cliente non necessari;
- path filesystem interni visibili all'utente;
- payload completi di impostazioni, PEC/SMTP, pagamenti o integrazioni.

Usare esempi neutri `example.invalid` o fixture sintetiche non riferibili a persone reali.

## File/document security

- Upload: validare tipo, dimensione, tenant e permesso.
- Download: servire da route backend sicura, mai da path client.
- Preview: non esporre path locale o allegati di altro tenant.
- Path traversal: bloccare `..`, path assoluti e root in payload client.
- Allegati PEC/email: azioni disponibili solo se il file esiste nel repository tenant.
- Audit: scritture, restore, delete e azioni probatorie devono essere tracciate.

## API security

Standard minimi:

- `401` per sessione mancante;
- `403` per permesso/flag negato;
- `404` quando non si deve confermare esistenza di risorsa non accessibile;
- `422` o `400` per input invalido;
- schema errore normalizzato in [docs/api-contracts.md](docs/api-contracts.md);
- OpenAPI e provider verification obbligatori per endpoint P0/P1 o sensibili.

Comandi:

```powershell
python scripts\react-migration\generate_api_contracts.py --check
python scripts\validate_openapi.py docs\openapi.yaml
python scripts\verify_openapi_provider.py
python -m pytest -q tests/test_openapi_contracts_phase6.py --tb=short
```

## CI security gates

Gate reali:

- CodeQL Python;
- dependency review;
- `pip-audit`;
- `npm --prefix frontend audit --audit-level=critical --omit=dev`;
- RBAC/tenant/security pytest;
- OpenAPI/provider verification;
- feature flag/routing tests;
- supply-chain SBOM.

Inventario: [docs/ci-cd-gates.md](docs/ci-cd-gates.md).

## Secrets policy

- Segreti solo via environment, secret store o environment GitHub protetto.
- Non stampare token/password nei log o artifact.
- Non usare `pull_request_target` per workflow che leggono secrets.
- Le smoke autenticate usano solo variabili `IUSENTRA_*` dedicate e falliscono/saltano se assenti.

## Reporting vulnerability

Non aprire issue pubbliche con dettagli sfruttabili o dati reali. Usare il canale riservato concordato con IUSENTRA o il referente tecnico del progetto. Se il canale responsabile non e' definito per l'installazione, definirlo prima del rollout esterno.

Segnalazione minima:

- descrizione;
- superficie coinvolta;
- impatto;
- passi riproducibili;
- versione/commit;
- log minimizzati e senza segreti;
- tenant/utente solo in forma redatta.

## Tempi attesi

- presa in carico iniziale: entro 2 giorni lavorativi;
- classificazione: entro 5 giorni lavorativi;
- mitigazione vulnerabilita critica/alta: priorita immediata dopo triage;
- disclosure pubblica: solo dopo fix o mitigazione disponibile.

## Fuori ambito

- richieste di supporto funzionale;
- ambienti alterati o non supportati;
- test su sistemi di terzi senza autorizzazione;
- proof-of-concept con dati reali o segreti.
