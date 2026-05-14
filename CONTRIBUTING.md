# Contributing

Aggiornato: 2026-05-14, fase 12 `fasereact`.

## Principio

Ogni modifica deve preservare comportamento corretto, sicurezza, isolamento tenant, reattivita e documentazione. Non usare dati demo o segreti reali. Non dichiarare test o tool come verdi se non eseguiti.

## Branch operativi

Nel contesto operativo corrente i soli branch ammessi sono:

- `Codex/legal-electronic-filing-kIxcV`
- `claude/legal-electronic-filing-kIxcV`

Non creare branch temporanei locali/remoti per task ordinari. A fine lavoro i due branch devono puntare allo stesso commit e `scripts/repo_hygiene.ps1` deve passare.

## Checklist PR minima

- [ ] Feature flag default-off se la modifica entra in App V2 sperimentale.
- [ ] Route guard e fallback documentati.
- [ ] Backend auth/RBAC/tenant isolation.
- [ ] Nessun `tenant_id`, `studio_id`, token o path accettato dal client.
- [ ] OpenAPI aggiornata se cambia API.
- [ ] Provider verification o limite documentato.
- [ ] Test backend mirati.
- [ ] Test frontend/typecheck/build se tocca React.
- [ ] Test feature flag on/off se tocca flag.
- [ ] Test RBAC e tenant isolation se tocca dati o permessi.
- [ ] Nessuna PII o secret leakage.
- [ ] Docs aggiornate.
- [ ] CI/gate locali equivalenti verdi.
- [ ] Rollback chiaro.

## Nuova pagina App V2

Seguire [docs/app-v2.md](docs/app-v2.md). In breve:

- censire route/manifest;
- usare flag `routes.appV2.*` default-off;
- nascondere menu se flag spento o permesso mancante;
- usare API JSON reali o stato vuoto se dati non disponibili;
- implementare loading, empty, error, forbidden, flag-off, readonly e success;
- aggiornare registry/generatori;
- eseguire test frontend/backend e browser smoke se user-facing.

## Nuovo endpoint

- Auth obbligatoria.
- RBAC dominio.
- Tenant corrente server-side.
- Validazione input e schema errore.
- OpenAPI + provider verification.
- Audit se legge/scrive dati sensibili o modifica stato.
- Nessun dato sensibile nei log o payload di errore.

## Feature flag

Naming: `routes.appV2.<area>.<pagina>` per App V2; alias legacy solo se serve compatibilita esplicita.

Comandi:

```powershell
python -m pytest -q tests/test_feature_flags.py tests/test_app_v2_feature_flags.py tests/test_app_v2_routing.py --tb=short
```

## Packaging

Sorgenti:

- runtime: `requirements/base.txt`;
- dev: `requirements/dev.txt`;
- extra: `requirements/pdf.txt`, `requirements/pades.txt`, `requirements/pkcs11.txt`;
- versione: `pct/__init__.py`.

Verifica:

```powershell
python tools\sync_packaging_files.py --check
python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short
```

## Gate locali consigliati

Eseguire solo i gate collegati al perimetro toccato; non rilanciare shard gia' documentati verdi senza motivo.

```powershell
python scripts\validate_docs_links.py
python scripts\validate_docs_commands.py
python scripts\react-migration\generate_app_v2_page_registry.py --check
python scripts\react-migration\generate_app_v2_area_requirements.py --check
python scripts\react-migration\generate_app_v2_test_docs.py --check
python scripts\validate_openapi.py docs\openapi.yaml
python scripts\verify_openapi_provider.py
npm --prefix frontend run test
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

## UI

- Testo visibile in italiano.
- Nessun termine tecnico da sviluppatore nelle schermate utente.
- Nessun dato demo/hardcoded come reale.
- Componenti IUSENTRA/shadcn e icone `lucide-react` dove applicabile.
- Verifica desktop/tablet/mobile per pagine user-facing importanti.

## PII e segreti

Non committare:

- password, token, API key, private key, PIN;
- PEC o email reali;
- dati cliente reali;
- documenti o allegati reali;
- path runtime generati.

Usare fixture neutre e tenant sintetici.

## Release e deploy

Ogni aggiornamento completato deve essere pushato sui due branch ammessi e deployato su Hetzner con procedura governata, senza dichiarare concluso finche' `/api/pronto` e container non sono verificati. Runbook: [docs/release-rollout.md](docs/release-rollout.md).
