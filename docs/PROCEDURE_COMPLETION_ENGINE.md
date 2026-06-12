# Procedure Completion Engine

Motore governato che completa le schede operative delle procedure partendo dal
catalogo ministeriale PST/XSD, dai template atti, dalla Procedure Lifecycle
Knowledge Pipeline e dalle fonti ufficiali predisposte. Ogni scheda nasce e
resta una **bozza per revisione avvocato**: la pubblicazione richiede fonti
ufficiali/tecniche, citazioni verificabili e approvazione umana. Non è un
chatbot e non genera contenuti giuridici liberi.

## Scopo

Dato un input come codice oggetto + denominazione (es. `010003`, «Procedimento
di ingiunzione ante causam»), il motore produce una scheda strutturata con:
codice, categoria, rito, competenza, uffici destinatari, fonte catalogo, fonte
normativa, articoli rilevanti con sintesi documentali, condizioni di
procedibilità, guida pratica, adempimenti fiscali, termini processuali,
allegati, avvertimenti obbligatori, atto principale e template candidati,
checklist e lifecycle, firma digitale/deposito/ricevute/notifiche (flusso PCT
da fonte tecnica), rischi, gap di evidenza, confidence, stato, review,
citazioni, hash fonti e timestamp.

L'input dell'utente **non è verità giuridica**: se il codice non è nel
catalogo ministeriale (es. la fixture `512075`), la scheda nasce
`needs_review` con gap bloccante «codice non trovato nel catalogo
ministeriale/template» e non è approvabile finché le fonti mancano.

## Architettura (riuso dei layer esistenti)

| Layer | Riuso |
|---|---|
| Catalogo ministeriale | `pct/pratiche_collegate_catalog.codice_oggetto_pst_entry` (PST/XSD ufficiali) |
| Riferimenti per famiglia XSD | `pct/procedure_source_research.build_source_plan_for_xsd` |
| Lifecycle | `pct/procedure_lifecycle_templates.build_lifecycle_steps_for_xsd` |
| Template atti | `GestioneTemplateRepository.select_best_templates` (via `default_template_search`) |
| Audit/sanitizzazione | `pct/procedure_lifecycle_repository.sanitize_audit_payload` + `stable_event_hash` |
| Lex | `lex/tools/registry.LexToolRegistry` (tool in-process governati) |
| Fonti ufficiali | retriever Normattiva/Gazzetta/Agenzia Entrate **iniettabili** e disabilitati di default (fail-closed: gap, non invenzione) |

Package: `pct/procedure_completion/` — `models` (dataclass), `schema`
(normalizzazione + chiavi client vietate), `repository` (SQLite +
audit sanificato), `source_plan` (piano fonti multi-sorgente), `extractor`
(citazioni via regex deterministiche, mai LLM per la struttura), `fusion`
(scheda + confidence), `validator` (regole fail-closed), `service`
(orchestratore con permessi).

## Data model

Migration idempotente `pct/sql/20260606_procedure_completion_engine.sql`:
`procedure_completion_runs`, `_cards`, `_sources`, `_citations`, `_gaps`,
`_template_links`, `_review_events`, `_audit_log`. `tenant_id` è nullable ma
sempre valorizzato server-side (mai accettato dal client); ogni mutazione
critica scrive audit con payload sanificato (email, CF, IBAN, telefoni, path,
segreti mascherati) e `event_hash` deterministico.

## Tipologie di fonte

- **official** (trust A: Normattiva, Gazzetta, EUR-Lex…): uniche fonti che
  rendono una scheda approvabile insieme alle tecniche.
- **technical** (trust B: catalogo PST, specifiche DGSIA, Agenzia Entrate):
  fatti tecnici del processo telematico.
- **professional**: sempre `summary_only`, estratto max 500 caratteri, mai
  copiate estesamente, mai promosse a diritto vincolante.
- **internal** (tenant-aware): se contengono possibili dati personali la
  scheda richiede `privacy_review_required`.

## Workflow

`preview → needs_review → approved → published`

- **preview** (`procedure_completion.esegui`): costruisce e salva la bozza con
  fonti, citazioni, gap e report di validazione. Nessuna scrittura "pubblica".
- **submit-review** (`esegui`): invia alla revisione avvocato.
- **approve** (`approva`): bloccata senza fonti ufficiali/tecniche o senza
  citazioni verificabili o con blocking error (termine processuale senza base
  normativa, citazione senza fonte, fonte professionale non summary_only…).
- **publish** (`pubblica`): solo da `approved`, con review avvocato registrata
  e report `publishable`. La confidence diventa HIGH solo con fonti ufficiali
  + template collegato + review; MEDIUM con fonti ma review pendente; LOW con
  gap o fonti insufficienti. La confidence non è mai una certezza legale.

## Integrazione Lex

`lex/tools/procedure_completion_tools.py`, registrati in `LexToolRegistry`
(transport `in_process`, mai web libero):

| Tool | Permesso |
|---|---|
| `procedure_completion_preview` | `procedure_completion.esegui` |
| `procedure_completion_search` | `procedure_completion.leggi` |
| `procedure_completion_explain_article` | `procedure_completion.leggi` |
| `procedure_completion_suggest_template` | `procedure_completion.leggi` |
| `procedure_completion_list_gaps` | `procedure_completion.leggi` |

Output sempre nel contratto governato: `official_sources`, `citations`,
`compared_sources`, `coverage_gaps`, `confidence`, `answer_mode`,
`needs_review`, `next_actions`. `explain_article` risponde **solo** dalle
citazioni già collegate alla scheda (sintesi documentale, non consulenza); se
il riferimento non è coperto risponde `needs_review` con azioni successive.

## API App V2

Bridge `web/services/react_procedure_completion_bridge.py`; endpoint in
`web/blueprints/api_v1_react.py` (sessione + RBAC + flag, tenant da `g`):

- `GET /api/v1/ui/procedure-completion` — dashboard (schede, gap, flag, permessi)
- `POST /api/v1/ui/procedure-completion/preview`
- `GET /api/v1/ui/procedure-completion/cards/<card_id>`
- `POST /api/v1/ui/procedure-completion/cards/<card_id>/submit-review`
- `POST /api/v1/ui/procedure-completion/cards/<card_id>/approve`
- `POST /api/v1/ui/procedure-completion/cards/<card_id>/publish`
- `GET /api/v1/ui/procedure-completion/gaps`

Il client non può imporre `tenant_id`, `studio_id`, `user_id`, `path`,
`token`, flag di sicurezza o trust score: la richiesta viene rifiutata con
`400 backend_security_control_param` (anche per chiavi annidate).

## UI React

`frontend/src/features/procedure-completion/` (rotta `/procedure-completion`,
pagina `ProcedureCompletionPage`): dashboard con contatori e coda gap, form di
anteprima, dettaglio scheda con banner «Bozza per revisione avvocato», badge
fonte/citazione accanto a ogni punto, avviso quando la fonte non è primaria,
confidence mostrata come affidabilità documentale (mai «certezza legale»),
pannelli fonti/gap/template fusion/review e lettura vocale.

## Voice read

`ProcedureCompletionVoiceReadPanel` usa **solo** la sintesi vocale locale del
browser (`speechSynthesis`, lingua it-IT): nessun provider esterno, nessun
clone o imitazione di voci reali. La lettura inizia sempre con «Voce generata
da intelligenza artificiale», include lo stato della scheda e l'avvertenza
quando la confidence non è HIGH, e non legge dati personali non necessari.
Flag: `lex.procedureCompletion.voiceRead.enabled` (default OFF, opt-in) e
`lex.procedureCompletion.voiceRead.localOnly` (default ON).

## Feature flag

| Flag | Default | Effetto |
|---|---|---|
| `lex.procedureCompletion.enabled` | ON | Abilita engine, API e tool Lex (OFF = 403 ovunque) |
| `routes.appV2.procedureCompletion.home` | ON | Pagina `/procedure-completion` nella shell App V2 |
| `lex.procedureCompletion.voiceRead.enabled` | OFF | Lettura vocale della scheda |
| `lex.procedureCompletion.voiceRead.localOnly` | ON | Solo TTS locale |

Override: `IUSENTRA_FF_LEX_PROCEDURECOMPLETION_ENABLED=0` ecc.

## Permessi RBAC

`procedure_completion.leggi / esegui / approva / pubblica / esporta`
(catalogo in `pct/auth.py`). Default: AVVOCATO tutti; COLLABORATORE
leggi+esegui; PRATICANTE leggi; AMMINISTRATORE/SUPERADMIN tutti.

## Limiti dichiarati

- Non deposita atti, non invia PEC, non firma, non scrive su fascicoli.
- Non verifica la vigenza testuale delle norme finché i retriever del Centro
  Fonti Ufficiali non sono abilitati: il gap `normattiva_non_abilitata` resta
  visibile e la verifica è demandata alla revisione avvocato.
- Gli adempimenti fiscali compaiono solo da fonte Agenzia Entrate configurata.
- Le sintesi sono troncamenti del passaggio recuperato, mai riscritture.
- Nessuna scheda costituisce consulenza legale o conformità garantita.

## Sicurezza

Tenant isolation server-side, RBAC su ogni endpoint/tool, audit sanificato con
hash deterministico, nessun dato cliente verso il web, divieto di scraping non
governato e di bypass di login/CAPTCHA/paywall, errori sanificati in risposta.

## Test e comandi

```bash
python -m pytest tests/test_procedure_completion_models.py -q
python -m pytest tests/test_procedure_completion_repository.py -q
python -m pytest tests/test_procedure_completion_validator.py -q
python -m pytest tests/test_procedure_completion_source_plan.py -q
python -m pytest tests/test_procedure_completion_fusion.py -q
python -m pytest tests/test_procedure_completion_service.py -q
python -m pytest tests/test_procedure_completion_api.py -q
python -m pytest tests/test_procedure_completion_security.py -q
python -m pytest tests/test_lex_procedure_completion_tools.py -q
python scripts/validate_openapi.py docs/openapi.yaml
python scripts/verify_openapi_provider.py
```

Fixture: `tests/fixtures/procedure_completion/512075_accordo_ristrutturazione_input.json`
(input utente + fonti dichiaratamente simulate; nessun test usa rete reale).
