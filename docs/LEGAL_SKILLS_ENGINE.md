# Legal Skills Engine

Aggiornato: 2026-05-15, fase Legal Skills.

## Scopo

Il Legal Skills Engine aggiunge a Lex un catalogo di skill legali versionate,
read-only e governate da profilo studio, fonti e revisione dell'avvocato.
L'architettura prende ispirazione pubblica dal progetto
`anthropics/claude-for-legal`, ma non copia prompt, contenuti o codice: i pack
IUSENTRA sono originali, italiani, tenant-aware e integrati nel runtime Lex.

Repository esterno di riferimento: <https://github.com/anthropics/claude-for-legal>

## Moduli

- `lex/legal_skills/models.py`: dataclass serializzabili e sanificate.
- `lex/legal_skills/parser.py`: frontmatter Markdown, validazioni e trust finding.
- `lex/legal_skills/registry.py`: catalogo seed pack read-only, cache e feature flag.
- `lex/legal_skills/profile_store.py`: profilo studio tenant-aware con snapshot.
- `lex/legal_skills/workflow_engine.py`: esecuzione governata, fonti, salvataggio risultati.
- `lex/legal_skills/guardrails.py`: note di revisione, citazioni, blocco export prudenziale.
- `lex/legal_skills/trust_layer.py`: controllo statico per skill custom, default-off.
- `lex/legal_skills/scheduled_agents.py`: agenti read-only, default-off.

Seed pack integrati:

- `commercial_legal`: revisione contratto e controllo rinnovi.
- `privacy_legal`: triage DPIA e revisione DPA.
- `litigation_legal`: cronologia fascicolo e preparazione udienza.
- `regulatory_legal`: monitor normativo e controllo gap policy.

## Feature flag

Il catalogo operativo e le pagine React Legal Skills sono attivi di default:

- `lex.legalSkills.enabled`
- `routes.appV2.legalSkills.catalog`
- `routes.appV2.legalSkills.profile`
- `routes.appV2.legalSkills.run`
- `routes.appV2.legalSkills.reviewQueue`

Restano spenti di default e fail-closed i flag piu' sensibili:

- `lex.legalSkills.trustLayer`
- `lex.legalSkills.customSkills`
- `lex.legalSkills.scheduledAgents`

## API

Endpoint base: `/api/v1/legal-skills`.

Le API richiedono sessione o API key valida, applicano il guardrail sui
parametri di controllo server, usano il tenant corrente e non accettano
`tenant_id` o `studio_id` dal client.

Permessi principali:

- `legal_skills.leggi`
- `legal_skills.esegui`
- `legal_skills.approva`
- `legal_skills.esporta`
- `legal_skills.profilo.scrivi`
- `legal_skills.trust_check`
- `legal_skills.scheduled.esegui`

## UI React

La superficie vive in `frontend/src/features/legal-skills/` con pagine:

- catalogo pack;
- profilo studio;
- esecuzione skill;
- revisione risultato.

La UI mostra sempre `Bozza per revisione`, citazioni, confidenza, modalita'
fonti e blocco export quando la base documentale non basta. Non invia
identificativi studio controllati dal client e non usa dati dimostrativi.

## Gate

Shard mirati:

```powershell
python -m pytest tests/test_legal_skills_engine.py -q
node frontend\scripts\check-legal-skills.mjs
python scripts\validate_openapi.py docs\openapi.yaml
python scripts\verify_openapi_provider.py
npm --prefix frontend run test
npm --prefix frontend run typecheck
npm --prefix frontend run build
```
