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

## Libreria Prompt — LegalSkills Italia

`lex/legal_skills/prompt_library/` aggiunge al motore un catalogo read-only
di **1.303 prompt operativi in 26 aree del diritto italiano**, ciascuno
derivato da una voce con base normativa dichiarata (principio delle fonti
certe) e composto in una delle 5 forme della prassi forense:
`redazione_atto`, `parere`, `checklist`, `lettera`, `ricerca`.

- `prompt_library/models.py`: dataclass `AreaPrompt` e `VocePrompt`.
- `prompt_library/composer.py`: template per forma; ogni testo impone la
  revisione obbligatoria dell'avvocato e vieta l'invenzione di fonti.
- `prompt_library/library.py`: caricamento fail-closed del catalogo,
  ricerca su tutto il contenuto (testo, area, forma, riferimenti, tag),
  singleton `get_prompt_library()`.
- `prompt_library/catalog/`: 26 file JSON versionati (una area per file,
  263 voci totali con riferimenti normativi).

API: `/api/v1/legal-skills/prompt-library` (`/aree`, `/prompts`,
`/prompts/<id>`), blueprint `web/blueprints/api_v1_prompt_library.py`,
stesse guardie del motore (auth, flag `lex.legalSkills.enabled`, permesso
`legal_skills.leggi`, blocco parametri riservati).

UI: pagina `PromptLibraryPage` su `/legal-skills/prompt` (flag
`routes.appV2.legalSkills.promptLibrary`, attivo di default), con ricerca
full-catalog, filtri area/forma, dettaglio con riferimenti e copia negli
appunti.

Specializzazione per studio e fascicolo:

- **Precompilazione dal fascicolo**: `GET /prompts/<id>?fascicolo=<id>`
  (permesso aggiuntivo `fascicoli.leggi`) sostituisce i segnaposto
  `[PARTI]`, `[FATTI]`, `[DOCUMENTI…]`, `[DESTINATARIO]`, ecc. con i dati
  reali del fascicolo (parti, RG, ufficio, documenti, prossime scadenze)
  tramite `prompt_library/case_context.py` e il bridge
  `web/services/prompt_library_fascicolo_bridge.py`. I dati assenti
  restano segnaposto: niente viene inventato. In UI il fascicolo si
  collega dal selettore della pagina o con `?fascicolo=` nell'URL.
- **Aree preferite dal profilo studio**: `GET /aree` incrocia le
  `practice_areas` del `PracticeProfile` con il catalogo
  (`prompt_library/profile_matching.py`) e propone per prime le aree
  praticate dallo studio (`preferita: true`, chip dedicate in UI).
- **Percorsi guidati per procedimento**: catalogo versionato in
  `prompt_library/pathways_data/` (10 percorsi: monitorio, sfratto,
  separazione consensuale, impugnazione licenziamento, sinistro RC auto,
  opposizione a decreto ingiuntivo, ricorso TAR, responsabilità
  sanitaria, mediazione civile, data breach). Ogni passo richiama un
  prompt reale del catalogo (validazione fail-closed in
  `prompt_library/pathways.py`) e dichiara termini e riferimenti
  normativi. Avanzamento per fascicolo tenant-aware
  (`prompt_library/pathway_progress.py`, `LEGAL_SKILLS_PATHWAYS_DB`).
  API: `/api/v1/legal-skills/prompt-library/percorsi` (lista, dettaglio
  con `prossimo_passo`, `POST .../passi/<id>/stato`). UI: pagina
  `/legal-skills/percorsi` (flag `routes.appV2.legalSkills.pathways`)
  con timeline dei passi, termini da presidiare, "Apri prompt" con
  deep-link `?prompt=` e avanzamento per fascicolo.
- **Esecuzione governata ("Esegui con Lex")**: `POST /run`
  (permesso `legal_skills.esegui`) trasforma il prompt — precompilato dal
  fascicolo se indicato — in una skill sintetica read-only
  (`prompt_library/runner.py`, pack `prompt_library`) e la esegue nel
  `LegalSkillWorkflowEngine`: profilo studio obbligatorio (409 se
  incompleto), fonti di policy, guardrail, nota di revisione, salvataggio
  nella coda runs esistente con `prompt_id`/`fascicolo_id` tracciati.
  L'esito si rivede e approva su `/legal-skills/runs/<run_id>` con i
  flussi approve/export già governati.

Gate dedicato: `python -m pytest tests/test_prompt_library.py -q` (contratto
1.303 prompt / 26 aree, composizione per ogni forma, ricerca, API governate).

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
pnpm --filter @iusentra/studio test
pnpm --filter @iusentra/studio typecheck
pnpm --filter @iusentra/studio build
```
