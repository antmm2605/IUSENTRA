# Processo di Release

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

- il lavoro confluisce sul branch di sviluppo corrente
- lo stesso commit va sincronizzato anche sul branch gemello remoto
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
