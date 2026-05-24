# Processo obbligatorio commit e push

Aggiornato: 22 maggio 2026.

Questa è la checklist operativa da usare ogni volta che Codex prepara un commit, un push o una consegna sui branch `Codex/legal-electronic-filing-kIxcV` e `claude/legal-electronic-filing-kIxcV`.

## Regola operativa

Prima di dichiarare concluso un lavoro:

1. verificare `git status --short` e classificare subito ogni modifica non collegata: completare, testare e includere solo le implementazioni utili; ripristinare o rimuovere artefatti runtime/generati e modifiche non necessarie;
2. eseguire i test mirati locali sul perimetro toccato;
3. aggiornare changelog, versione e report pertinenti;
4. committare e pushare il branch di sviluppo;
5. sincronizzare il branch gemello allo stesso commit;
6. controllare i gate GitHub del push con `tools/check_github_required_gates.py` e, quando esiste una PR, anche della PR;
7. registrare esiti verdi e problemi nei report di stato;
8. fare deploy Hetzner quando richiesto dal flusso corrente e verificare `/api/pronto`;
9. ripetere `git status --short` prima del report finale: la consegna è vietata se la worktree non è pulita.

### Regola anti-recidiva CI/Deploy/CodeQL

Segnalazione utente del 22 maggio 2026: non deve più ricapitare la situazione in cui il deploy Hetzner risulta verde ma la consegna resta instabile per CodeQL, lint o shard reali ancora rossi, saltati o in coda.

Quindi, dopo ogni push, la consegna è vietata finché non sono vere tutte queste condizioni:

- lo SHA corrente è identico su `Codex/legal-electronic-filing-kIxcV`, `claude/legal-electronic-filing-kIxcV` e remoti;
- i required checks sono quelli versionati in `.github/required-checks.json` e applicati in branch protection sui due branch operativi;
- `enforce_admins=false` nella branch protection è una scelta operativa per consentire il push diretto autorizzato sui soli branch gemelli; non autorizza la chiusura del lavoro senza check verdi, report automatico e deploy post-CI;
- il check `CI Required Gates / CI reale eseguita sul commit corrente` è verde e il relativo artifact `current-sha-required-gates` è generato dallo script, non scritto a mano;
- tutti i check-run GitHub dello SHA corrente sono `completed`;
- non esistono check-run con `conclusion` diversa da `success` o da uno `skipped` esplicitamente non richiesto;
- `CodeQL / Analyze (python)` e il check separato `CodeQL` / `Code scanning results / CodeQL` sono verificati sullo SHA corrente;
- `Lint + syntax` è verde prima di interpretare aggregatori Pytest, Signer o Coverage;
- gli shard reali Pytest, Coverage 12/12 e Local Signer/PKCS#11 sono letti direttamente, non dedotti dagli aggregatori;
- il deploy Hetzner è verificato dopo il push con commit server, container healthy, `https://app.iusentra.it/api/pronto` e pulizia cache Docker.

Comando minimo per non confondere run vecchi e run nuovi:

```powershell
$sha = git rev-parse HEAD
$repo = gh repo view --json nameWithOwner -q .nameWithOwner
$runs = @()
foreach ($p in 1..4) {
  $page = gh api "repos/$repo/commits/$sha/check-runs?per_page=100&page=$p" | ConvertFrom-Json
  $runs += $page.check_runs
}
$runs | Group-Object status,conclusion
$runs | Where-Object { $_.conclusion -and $_.conclusion -ne 'success' -and $_.conclusion -ne 'skipped' } |
  Select-Object name,status,conclusion,details_url
python tools\check_github_required_gates.py --event push --wait --check-branch-protection --report-md artifacts\ci\current-sha-required-gates.md --report-json artifacts\ci\current-sha-required-gates.json
```

Se CodeQL resta rosso, non usare annotazioni di commit precedenti: aprire solo le annotazioni del check-run CodeQL dello SHA corrente e correggere quel flusso prima di qualunque dichiarazione finale.

Gli aggregatori non sono diagnosi primaria. Se un aggregatore è rosso o `Skipped`, guardare prima `Lint + syntax`, `Governance repo`, smoke upstream e lo shard reale Pytest, Coverage o Signer.

Il vecchio aggregatore `CI / Coverage moduli critici` senza `parte` non deve essere reintrodotto come blocco PR: la coverage critica è governata dalle 12 parti.

Se GitHub, una dashboard esterna o un riepilogo storico espone ancora un aggregatore legacy, va trattato solo come advisory compatibile e registrato nella memoria operativa insieme agli shard reali verificati. Non va messo in branch protection, non diventa required check e non può sostituire `Coverage moduli critici parte */12` né gli shard Pytest/Signer per fase.

## Gate richiesti

Sicurezza e supply chain:

- `CodeQL / Analyze (python)` su `push` e `pull_request`;
- `Code scanning results / CodeQL`;
- `Dependency Review / Review dipendenze in ingresso` su `pull_request`;
- `Security Supply Chain / Audit dipendenze Python` su `pull_request`;
- `Security Supply Chain / Audit dipendenze frontend` su `pull_request`;
- `Security Supply Chain / Generate SBOM` su `pull_request`.

CI base:

- `CI / Governance repo` su `push` e `pull_request`;
- `CI / Lint + syntax` su `push` e `pull_request`;
- `CI / Smoke test Flask` su `push` e `pull_request`;
- `CI / Smoke scheduler worker` su `push` e `pull_request`;
- `CI / E2E smoke` su `push` e `pull_request`.

Frontend:

- `Frontend React CI / Frontend React CI` su `push` e `pull_request`;
- `Frontend React CI / Frontend React typecheck` su `push` e `pull_request`;
- `Frontend React CI / Frontend React contratti` su `push` e `pull_request`;
- `Frontend React CI / Frontend React build` su `push` e `pull_request`;
- `Frontend React CI / Frontend React storybook` su `push` e `pull_request`;
- `CI / Storybook visual regression` su `push` e `pull_request`.

Coverage critica:

- `CI / Coverage moduli critici parte 1/12` fino a `parte 12/12`, su `push` e `pull_request`.

Pytest core:

- `CI / Pytest core` su `push` e `pull_request`;
- `CI / Pytest core fase 1/10`, `2/10`, `3/10`, `4/10`, `10/10`, su `push` e `pull_request`;
- `CI / Pytest core fase 5/10 parte 1/6` fino a `parte 6/6`, su `push` e `pull_request`;
- `CI / Pytest core fase 6/10 parte 1/16` fino a `parte 16/16`, su `push` e `pull_request`;
- `CI / Pytest core fase 7/10 observability parte 1/3` fino a `parte 3/3`, su `push` e `pull_request`;
- `CI / Pytest core fase 8/10 OCR parte 1/3` fino a `parte 3/3`, su `push` e `pull_request`;
- `CI / Pytest core fase 9/10 parte 1/6` fino a `parte 6/6`, su `push` e `pull_request`.

Local Signer e PKCS#11:

- `CI / Local Signer e PKCS#11` su `push` e `pull_request`;
- `CI / Local Signer e PKCS#11 (macos-latest) parte 1/4` fino a `parte 4/4`, su `push` e `pull_request`;
- `CI / Local Signer e PKCS#11 (ubuntu-latest) parte 1/4` fino a `parte 4/4`, su `push` e `pull_request`;
- `CI / Local Signer e PKCS#11 (windows-latest) parte 1/4` fino a `parte 4/4`, su `push` e `pull_request`.

Quality overlay:

- `CI Quality Overlay / Targeted tests` su `push` e `pull_request`;
- `CI Quality Overlay / Targeted tests parte 1/3` fino a `parte 3/3`, su `push` e `pull_request`;
- `CI Quality Overlay / quality-gates` su `push` e `pull_request`.

Verifica finale:

- `CI Required Gates / CI reale eseguita sul commit corrente` su `push` e `pull_request`, con report automatico Markdown/JSON e status esterni come `Vercel` separati dai gate IUSENTRA;
- `Deploy su Hetzner CPX42` resta post-push operativo e non sostituisce i gate qualità: il workflow attende `tools/check_github_required_gates.py --wait` prima di eseguire SSH/deploy e poi si verifica con commit server, container, `/api/pronto` e prune Docker.

## Dove registrare

- `artifacts/react-migration/pytest-confirmed-ok.md`: test, shard e gate verdi;
- `artifacts/react-migration/pytest-open-issues.md`: failure, timeout, `Skipped`, workaround e rilanci necessari;
- `CHANGELOG.md`: modifiche utente o di comportamento;
- report React/audit pertinenti quando cambia una route, una UI, un gate o una fonte dati.
