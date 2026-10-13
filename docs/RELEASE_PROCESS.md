# Processo di Release

> Direttiva utente 13/10/2026: `main` è il solo branch operativo e predefinito per commit, push e deploy. Le istruzioni storiche su branch gemelli e doppio push sono sostituite: nessun mirroring. I vecchi branch restano conservati come riferimenti storici; `chore/monorepo-foundation` resta intoccabile. Tutti i gate CI e le verifiche reali restano obbligatori.

## Obiettivo

Chiudere una release di IUSENTRA significa allineare codice, documentazione, CI, branch e ambienti, non soltanto fare merge di una feature.

## Checklist minima

1. Completare il lavoro e mantenere `web/app.py`, `web/bootstrap/` e `web/services/` entro i guardrail di repo.
2. Eseguire il bump di versione in:
   - `pct/__init__.py`
   - `setup.py`
   - `Dockerfile`
   - `railway.toml`
3. Aggiornare `CHANGELOG.md` con il contenuto della release.
4. Verificare che README e documentazione tecnica riflettano le modifiche introdotte.
   - se il flusso `cliente -> incasso` cambia, aggiornare anche `docs/DEMO_STUDIO_REALE.md`
5. Eseguire la suite minima pertinente:
   - bootstrap / sicurezza / storage
   - test del dominio toccato
   - eventuali smoke Local Signer o worker dedicati
   - `iusentra demo-check` o relativo test se cambia il percorso operativo end-to-end
6. Verificare la CI applicativa e i workflow di sicurezza:
   - `CI`
   - `CodeQL`
   - `Dependency Review` se il cambio passa da PR
   - `Security Supply Chain`
7. Ricostruire il runtime locale quando la release tocca il codice distribuito via container.
8. Allineare i branch remoti previsti dal progetto e confermare l'igiene repo.

## Disciplina branch e sincronizzazione

- il lavoro confluisce esclusivamente su `main`, branch predefinito
- il commit viene pushato soltanto a `origin/main`
- `scripts/repo_hygiene.ps1` installa in automatico `core.hooksPath=.githooks` e registra il repository come `safe.directory`, cosi' il bootstrap locale non dipende piu' da interventi manuali ripetuti
- gli hook versionati in `.githooks/` preservano i controlli locali senza modificare altri branch
- il workflow storico `.github/workflows/sync-claude-to-codex.yml` è disattivato per push e completamenti CI; l'avvio manuale conferma soltanto l'assenza di mirroring
- non lasciare release solo in locale
- prima di chiudere, eseguire `scripts/repo_hygiene.ps1`

## Release notes

Ogni release deve dichiarare almeno:

- versione
- area funzionale toccata
- eventuali rischi o compatibilita' storage/runtime
- impatto su CI, sicurezza o deployment
- stato della demo mentale `apro IUSENTRA e gestisco uno studio reale da zero`

## Tag e changelog

- il changelog e' la fonte narrativa della release
- il tag Git deve corrispondere alla stessa versione presente nei quattro file ufficiali
- evitare release mute: se il codice cambia, la release deve raccontarlo
