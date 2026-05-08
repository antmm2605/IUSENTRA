# Lex AI — Audit tecnico per upgrade professionale

**Versione audit:** 1.0.0  
**Data:** 2026-05-08  
**Ambito:** Architettura bounded context Lex, flusso di esecuzione, gap UI, rischi e roadmap

---

## 1. Entrypoint reali di Lex

Il punto di ingresso HTTP è `lex/orchestrator_http.py`, che espone la funzione principale dell'orchestratore HTTP legacy. Questa funzione:

1. Riceve il payload HTTP dalla route Flask (`web/app.py` via `lex/blueprint.py`).
2. Risolve `studio_context`, `request_profile`, `effective_question` e allegati.
3. Chiama `build_bounded_http_payload` da `lex/http_bounded_bridge.py`.
4. Se il bounded context non è attivato (rarissimo: `LEX_GOVERNED_ONLY=0` e nessun allegato), valuta la raw chat.
5. Restituisce il payload JSON alla UI.

Il flusso bounded context è:

```
orchestrator_http.py
  └─ build_bounded_http_payload()          [http_bounded_bridge.py]
       └─ _application_lex_service().ask() [service.py → LexService]
            └─ LexOrchestrator.run()       [orchestrator.py]
                 └─ run_workflow()          [orchestrator_workflow.py]
                      ├─ workflow_router.resolve_workflow()
                      ├─ workflow_context_builder.build_request_context()
                      ├─ guard_orchestrator.run_pre()
                      ├─ retrieval_orchestrator.collect()
                      ├─ provider_registry.pick() → provider.generate()
                      ├─ guard_orchestrator.run_post()
                      └─ response_formatter.build_response()
```

---

## 2. Differenza tra context response, chat response e bounded workflow

| Tipo | Descrizione | Quando viene usato |
|---|---|---|
| **Context response** | Risposta costruita solo sul contesto studio (fascicolo, agenda, scadenziario, preventivi) senza retrieval esterno. Il provider è `deterministic`. | Workflow economico, cabina, next_action, telematico_status, compliance. Fascicolo con contesto interno sufficiente. |
| **Chat response (raw)** | Generazione libera senza evidence o workflow governato. Non costruisce un `LexRequest` né attraversa il bounded context. | Solo se `LEX_RAW_CHAT_ENABLED=1` **e** `allow_unbounded_generation=true` nel payload. Oggi bloccata di default. |
| **Bounded workflow** | Percorso completo: classificazione intent → routing fonti → retrieval → guard pre/post → provider → formatter. Produce una `LexResponse` con `answer_mode`, `confidence`, `citations`, `evidence_summary`. | Default assoluto quando `LEX_GOVERNED_ONLY=1` (default) o quando ci sono allegati. |

---

## 3. Quando viene usato `LEX_GOVERNED_ONLY`

La variabile `LEX_GOVERNED_ONLY` è letta da `_governed_only_enabled()` in `http_bounded_bridge.py`.

- **Default:** `True` (la variabile mancante equivale a `1`).
- Quando è `True`, `_should_use_bounded_workflow()` ritorna sempre `True` indipendentemente da qualunque altro parametro (presenza allegati, `request_profile.intent`, `focus_topic`, ecc.).
- L'unico modo per disattivarlo è impostare esplicitamente `LEX_GOVERNED_ONLY=0` nell'ambiente.
- Quando è `False`, si entra nella logica legacy che valuta `focus_topic`, `profile_intent`, `source_mode` e `web_execution_requested` per decidere se usare il bounded workflow.

**Implicazione:** Oggi, in ogni istanza di produzione con la configurazione di default, ogni richiesta Lex attraversa il bounded context completo.

---

## 4. Quando viene bloccata la raw chat

La raw chat è gestita in `orchestrator_http.py` con `_raw_chat_allowed(data)`:

```
raw_chat_blocked se:
  LEX_RAW_CHAT_ENABLED != "1"   (default: non impostata = bloccata)
  oppure
  allow_unbounded_generation != true nel payload
```

Quando bloccata, `orchestrator_http` restituisce `_raw_chat_blocked_payload()` con:
- `answer_mode: needs_review`
- `confidence: 0.12`
- `risk_level: medium`
- messaggio fisso: *"Non posso rispondere in modalita' chat libera senza evidenze governate."*

**Con `LEX_GOVERNED_ONLY=1`** (default), il blocco avviene ancora prima: `build_bounded_http_payload` viene invocato direttamente e la raw chat non è nemmeno valutata.

---

## 5. Quando viene attivato il retrieval interno

Il retrieval interno è sempre attivato nel bounded workflow tramite `RetrievalOrchestrator.collect()` in `lex/retrieval/orchestrator.py`:

1. `QueryPlanner.plan()` produce le query.
2. `SourceRouter.resolve()` risolve le sorgenti da usare:
   - Sempre: sorgenti per workflow (es. `AgendaSource`, `ScadenziarioSource`).
   - Se `fascicolo_id` presente: `FascicoliSource`, `DocumentiSource`.
   - Se `_should_include_legal_sources()` ritorna True: `LegalUpdatesSource`, `LegalIntelligenceSource`, `NormativeSource`, `GiurisprudenzaSource`.
3. Studio context seed (fino a 6 righe) viene iniettato come evidenza primaria.
4. Le sorgenti interne vengono interrogate, filtrate, deduplicate e rankate.

`_should_include_legal_sources()` ritorna `True` se:
- Workflow in `{normativa, giurisprudenza, prassi, research, fonti}`.
- `require_official_sources=True` nel `LexRequest`.
- `source_mode = "strict"` nel profilo.
- Per workflow fascicolo/udienza/documento: solo se c'è `external_sources_reason` o `source_mode="strict"`.
- Per altri workflow: se la query contiene token normativi/giuridici (`sentenza`, `norma`, `legge`, ecc.).

---

## 6. Quando viene attivato il fallback web ufficiale

Il fallback su `OfficialWebSource` avviene in `RetrievalOrchestrator.collect()` quando sono verificate **tutte** le seguenti condizioni:

1. L'evidenza interna **non è sufficiente** (`_evidence_is_sufficient()` ritorna False).
2. `request.allow_external_research = True`.
3. `OfficialWebSource` è presente nella lista sorgenti risolta da `SourceRouter`.

`OfficialWebSource.should_include()` è `True` quando:
- `require_official_sources=True` nel request, oppure
- Il focus_topic è `{ricerca_legale, archivio_sentenze, sentenze_civili, sentenze_web, telematico}`, oppure
- Intent è in `_STRICT_OFFICIAL_INTENTS = {giurisprudenza, normativa, pratica_procedura}`, oppure
- Il profilo ha `external_sources_reason` valorizzato.

La ricerca web avviene tramite `search_recognized_official_web()` in `lex/retrieval/official_web.py`, che interroga DuckDuckGo HTML `site:<domain>` solo su domini istituzionali riconosciuti (normattiva.it, gazzettaufficiale.it, giustizia.it, cortedicassazione.it, ecc.).

---

## 7. Quando viene attivato Local Deep Research

**Local Deep Research (LDR) non è attivato automaticamente nel flusso principale.** Non è integrato nel `RetrievalOrchestrator` né in `SourceRouter`. Il client `LocalDeepResearchClient` in `lex/integrations/local_deep_research_client.py` è un bridge HTTP autonomo che deve essere invocato esplicitamente.

LDR può essere invocato solo se:
- `LDR_BASE_URL`, `LDR_USERNAME`, `LDR_PASSWORD` sono configurate.
- La query supera la `validate_query_policy()`: nessun identificatore personale (email, CF, IBAN, telefono, RG) e nessun termine legale riservato allo studio (cliente, controparte, fascicolo, PST, PDP, PAT, consulenza legale, ecc.).
- `allow_sensitive=False` (default), oppure `LDR_ALLOW_SENSITIVE=1` per override esplicito.

**Gap attuale:** nessun componente esistente nella pipeline bounded orchestra LDR in modo automatico. Il modulo `lex/research/public_legal_research_gateway.py` (introdotto con questo audit) colma questo gap.

---

## 8. Quando viene scelto il provider (deterministic / Ollama / OpenAI)

La selezione avviene in `ProviderRegistry.pick()` (`lex/providers/registry.py`):

| Condizione | Provider |
|---|---|
| `force_provider="mock"` e env test | `MockProvider` |
| `force_provider` in metadata | Provider forzato |
| `LEX_PROVIDER_FORCE_MOCK=1` | `MockProvider` |
| Workflow in `{economico, next_action, cabina, telematico_status, compliance}` | `DeterministicProvider` |
| `AnswerContract.provider_hint` valorizzato | Provider suggerito dal contratto |
| Workflow `fascicolo` con contesto fascicolo disponibile | `DeterministicProvider` |
| Workflow in `{normativa, giurisprudenza, prassi, research, fonti}` | `OllamaProvider` |
| Workflow in `{telematico, udienza, atto, documento, question_answering, intelligence}` | `OllamaProvider` |
| Workflow `fascicolo` senza contesto fascicolo | `OllamaProvider` |
| Default (tutti gli altri) | `OllamaProvider` |

**OpenAI** è disponibile ma viene usato solo se `LEX_EXTERNAL_ALLOWED=1` e il provider è forzato esplicitamente (`force_provider="openai"`) oppure dal `LexGateway` (gateway separato, non nel bounded context principale).

---

## 9. Quando Lex risponde `grounded`

`answer_mode = "grounded"` viene impostato dal `ResponseFormatter` quando:
- Il retrieval ha prodotto evidenze sufficienti (`evidence_sufficient=True`).
- I guard post non hanno bloccato la risposta.
- Le citazioni sono disponibili e verificabili.
- Il workflow è di tipo operativo con contesto interno (deterministic).

Indicatori nella `LexResponse`:
- `confidence >= 0.55` (media o alta).
- `evidence_summary.evidence_count >= 1`.
- `missing_evidence` lista vuota o con solo gap minori.

---

## 10. Quando Lex risponde `needs_review`

`answer_mode = "needs_review"` viene impostato quando:
- Il guard post non blocca ma rileva insufficienza delle evidenze.
- Il retrieval non ha trovato fonti sufficienti per il workflow (es. normativa senza fonti tier_1).
- La raw chat è bloccata (`_raw_chat_blocked_payload`).
- Gli allegati non sono stati indicizzati (`_attachment_needs_indexing_payload`).
- Il provider generativo ha prodotto un draft con avvisi di qualità insufficiente.
- `answer_mode` è impostato esplicitamente a `needs_review` da guardrail specifici (es. `LegalAnswerQualityGuard`, `CitationGuard`).

Quando `answer_mode = "needs_review"`:
- `disable_exports=True` viene inviato alla UI.
- `confidence_label = "bassa"`.
- Il `confidence_reason` descrive il gap residuo.

---

## 11. Quando Lex si blocca

Ci sono tre tipi di blocco:

### Blocco hard (eccezione `LexGuardError`)
Avviene quando un guard **pre** blocca la richiesta (`run_pre()` ritorna `allowed=False`):
- `TenantGuard`: tenant non autorizzato o mancante.
- `PermissionGuard`: utente senza permessi per il workflow richiesto.
- `PrivacyGuard` (guards): contenuto altamente sensibile con provider non locale.
- `RiskGuard`: risk_level crítico.

`LexGuardError` viene catturata nell'orchestratore HTTP e trasformata in risposta di errore con `answer_mode="blocked"`.

### Blocco soft post-generazione (guardrail reply)
Avviene quando un guard **post** blocca il draft ma `contract.allow_abstention=True`:
- Il draft viene sostituito da `_guardrail_reply()` in `orchestrator_workflow.py`.
- Il provider diventa `"guardrail"`.
- La risposta è `"Non posso completare una risposta legale affidabile..."`.

### Blocco `AnswerContract.allow_abstention=False`
Per workflow operativi (`economico`, `cabina`, `next_action`, `compliance`) con `allow_abstention=False`, un blocco post lancia `LexGuardError` anche dopo la generazione.

---

## 12. Quali campi arrivano alla UI

Il payload JSON finale (da `build_bounded_http_payload`) include:

| Campo | Tipo | Note |
|---|---|---|
| `answer` | str | Testo risposta |
| `answer_mode` | str | `grounded` / `needs_review` / `blocked` |
| `confidence` | float | 0.0–1.0 |
| `confidence_label` | str | `alta` / `media` / `bassa` |
| `confidence_reason` | str | Descrizione motivazione confidenza |
| `risk_level` | str | `low` / `medium` / `high` / `critical` |
| `warnings` | list[str] | Avvisi generati |
| `next_actions` | list[str] | Azioni suggerite |
| `citations` | list[str] | Label citazioni |
| `sources` | list[dict] | Righe sorgenti con `title`, `url`, `authority`, `confidence`, `trust_class`, `source_access_status`, `source_access_label`, `source_requires_credentials`, `source_restricted`, `source_supports_web_search` |
| `legal_basis` | list[str] | Base normativa |
| `considered_sources` | list[str] | Sorgenti considerate |
| `compared_sources` | list[dict] | Confronto fonti |
| `missing_evidence` | list[str] | Evidenze mancanti |
| `evidence_summary` | dict | `evidence_count`, `official_count`, `trusted_count`, `attachment_count`, `evidence_sufficient` |
| `workflow` | str | Workflow usato |
| `provider` | str | Provider usato |
| `focus_topic` | str | Topic corrente |
| `focus_label` | str | Label human-readable topic |
| `external_sources_used` | bool | Se è stato usato il fallback web |
| `external_sources_reason` | str | Motivazione fonti esterne |
| `fascicolo_first` | bool | Se il fascicolo è il contesto primario |
| `disable_exports` | bool | Blocca export PDF/DOCX se needs_review o high-risk |
| `request_profile` | dict | Profilo richiesta |
| `source_policy_summary` | dict | Riepilogo policy fonti |
| `source_mode` | str | Modalità sorgenti: strict/balanced/broad |
| `routing` | dict | Routing payload |
| `followup_resolution` | dict | Risoluzione follow-up |
| `web_fallback_used` | bool | Se il fallback web è stato usato |
| `web_execution_requested` | bool | Se la ricerca web è stata richiesta |
| `competence_labels` | list[str] | Etichette competenza |

---

## 13. Quali campi mancano alla UI

I seguenti campi vengono prodotti internamente ma **non vengono inclusi nel payload JSON finale** verso la UI. Questo limita la trasparenza e la debuggabilità della risposta.

| Campo mancante | Dove viene prodotto | Impatto |
|---|---|---|
| `ldr_used` | `LocalDeepResearchClient.research_and_wait()` | La UI non sa se LDR è stato usato |
| `ldr_blocked_reason` | `LocalDeepResearchPolicyError` in LDR | La UI non sa perché LDR è stato bloccato |
| `web_used` | `OfficialWebSource` in `RetrievalOrchestrator` | Distinto da `external_sources_used` che è aggregato |
| `web_blocked_reason` | `OfficialWebSource.should_include()` = False | La UI non sa perché il web non è stato usato |
| `public_research_query` | Non esiste ancora | Query anonimizzata usata per web/LDR non è visibile |
| `private_context_query` | Non esiste ancora | Query per retrieval interno non è visibile |
| `removed_sensitive_tokens` | Non esiste ancora | Token rimossi dalla query non sono comunicati |
| `confidence_reason` | `_confidence_reason()` in `http_bounded_bridge.py` | **Questo è incluso nel payload** — ma non visibile nella UI |
| `skipped_generation_reason` | `_guardrail_reply()` (blocco soft) | La UI non vede la ragione dettagliata del blocco |
| `official_sources_count` | `evidence_summary` (parziale) | Non isolato come campo top-level |
| `internal_sources_count` | `evidence_summary` (parziale) | Non isolato come campo top-level |

**Nota:** `confidence_reason` è tecnicamente nel payload ma la UI attuale non lo visualizza in modo prominente. I campi `ldr_used`, `ldr_blocked_reason`, `web_used`, `web_blocked_reason`, `public_research_query`, `private_context_query`, `removed_sensitive_tokens`, `skipped_generation_reason`, `official_sources_count`, `internal_sources_count` non esistono nel flusso attuale e richiedono i nuovi moduli `privacy_safe_query_rewriter.py` e `public_legal_research_gateway.py`.

---

## 14. Perché oggi Lex può sembrare "non all'altezza"

L'architettura bounded context è solida, ma emergono sei cause principali di sotto-performance percepita:

### 14.1 Mancanza di riscrittura query per la ricerca pubblica
La query originale dell'utente — che spesso contiene nomi propri, numeri di RG, riferimenti a fascicoli specifici — viene usata direttamente sia per il retrieval interno che per la ricerca web. Questo:
- Blocca correttamente la query su LDR (politica privacy corretta).
- Ma impedisce anche la ricerca pubblica su materie giuridiche valide, perché il blocker LDR non distingue "RG 1234/2025 di Rossi → prescrizione" dalla materia legale "prescrizione in responsabilità contrattuale".
- Il modulo `privacy_safe_query_rewriter.py` risolve questo gap.

### 14.2 LDR non è integrato nel flusso automatico
`LocalDeepResearchClient` esiste come bridge HTTP ma non è mai invocato automaticamente dal `RetrievalOrchestrator` o da alcun workflow. Ricerche su giurisprudenza recente, dottrina, circolari non pubblicate su normattiva vengono perse.

### 14.3 Gap di copertura non comunicato alla UI
Quando le fonti riservate (DeJure, OneL, quotidianogiuridico.it) non sono accessibili, il sistema non dice esplicitamente all'avvocato "questa risposta è incompleta perché mancano le fonti X". Il campo `coverage_gaps` esiste nell'`EvidencePack` ma non è sempre surfacciato in modo prominente.

### 14.4 Assenza di normalizzazione e ranking cross-fonte
Non esiste un livello che normalizzi risultati da retrieval interno, web ufficiale e LDR in strutture uniformi e le rankini comparativamente. Le citazioni della risposta finale riflettono solo ciò che il provider ha ricevuto nel prompt, non una selezione ottimale di fonti.

### 14.5 Provider deterministic in workflow non operativi
Il `DeterministicProvider` produce risposte template-based adatte a workflow economici. Quando viene scelto erroneamente per workflow fascicolo senza contesto sufficiente, la risposta è generica e non citata.

### 14.6 Testo visibile inadeguato per query sensibili bloccate
Quando LDR blocca la query per dati sensibili, il messaggio di errore non suggerisce all'utente come riformulare la domanda. Con la riscrittura automatica, questo problema scompare perché la query pubblica viene generata automaticamente.

---

## 15. Rischi attuali

| Rischio | Gravità | Probabilità | Note |
|---|---|---|---|
| **Leak dati sensibili su LDR** | Alta | Bassa | Il guard privacy blocca correttamente, ma senza riscrittura query alcune query borderline potrebbero passare il check se non contengono pattern riconosciuti (es. nomi propri non riconosciuti) |
| **Risposta non grounded su materie normative** | Alta | Media | Se il DB normattiva.sqlite è vuoto o scaduto, il retrieval interno non trova nulla, il fallback web non è attivato, e Ollama genera senza evidenze |
| **Confidenza gonfiata** | Media | Media | Il `DeterministicProvider` imposta `confidence=0.9` per workflow operativi anche quando il contesto studio è minimale |
| **LDR non configurato silentemente** | Media | Alta | Se LDR non è configurato, nessun warning viene surfacciato nella risposta. L'utente non sa di stare ricevendo una risposta degradata |
| **Query nomi propri che passano il check** | Media | Media | `PrivacyGuard.redact()` non rimuove nomi propri italiani (solo CF, email, IBAN, RG, telefono). Un nome "Mario Rossi" non viene redactato |
| **Web fallback su DuckDuckGo down** | Bassa | Media | La ricerca web ha un `try/except` che continua silenziosamente, ma non c'è retry né circuit breaker |
| **Cache retrieval stale** | Bassa | Media | La cache retrieval ha un TTL ma non invalida quando le fonti cambiano |

---

## 16. Interventi necessari — le 13 fasi

### Fase 1: `privacy_safe_query_rewriter.py`
Crea il modulo `lex/research/privacy_safe_query_rewriter.py` con `rewrite_query_for_legal_research()`. Introduce la distinzione strutturale tra query privata (per retrieval interno) e query pubblica anonimizzata (per web e LDR). Rimuove nomi propri, RG, CF, IBAN, PEC, telefoni dalla query pubblica mantenendo la materia giuridica.

### Fase 2: `public_legal_research_gateway.py`
Crea il modulo `lex/research/public_legal_research_gateway.py` con `run_public_legal_research()`. Coordina retrieval interno, web ufficiale e LDR in un unico layer normalizzato. Produce `PublicLegalResearchResult` con `ldr_used`, `ldr_blocked_reason`, `web_used`, `web_blocked_reason`, ranking e `coverage_gaps`.

### Fase 3: Integrazione gateway nel `RetrievalOrchestrator`
Modifica `lex/retrieval/orchestrator.py` per invocare `run_public_legal_research()` come step aggiuntivo dopo il retrieval interno, quando il workflow richiede fonti pubbliche. I risultati vengono aggiunti all'`EvidencePack`.

### Fase 4: Propagazione campi mancanti al payload UI
Modifica `build_bounded_http_payload()` in `http_bounded_bridge.py` per includere nel payload finale: `ldr_used`, `ldr_blocked_reason`, `web_used`, `web_blocked_reason`, `public_research_query`, `removed_sensitive_tokens`, `official_sources_count`, `internal_sources_count`.

### Fase 5: Surfacing `coverage_gaps` nella UI
Modifica il template `web/templates/legal_intelligence/` e i componenti della topbar Lex per mostrare all'avvocato i gap di copertura in modo visibile, non solo nelle `warnings`.

### Fase 6: Upgrade `PrivacyGuard.redact()` per nomi propri
Integra i pattern di rimozione nomi propri italiani da `privacy_safe_query_rewriter.py` nel metodo `redact()` del `PrivacyGuard`, come opzione attivabile. Questo chiude il rischio di leak per nomi non riconosciuti dai pattern esistenti.

### Fase 7: Health check LDR nella diagnostica
Aggiungi il check di configurazione LDR in `lex/admin/healthcheck.py` e in `lex/admin/diagnostics.py`. Mostra un warning visibile nella UI admin quando LDR non è configurato.

### Fase 8: Metriche `ldr_used` / `web_used` in telemetria
Aggiungi i campi `ldr_used`, `web_used`, `ldr_blocked_reason`, `web_blocked_reason` al log di `LexTelemetry` e al sistema di audit in `lex/telemetry/`.

### Fase 9: Circuit breaker per il fallback web
Aggiungi un circuit breaker semplice in `lex/retrieval/official_web.py` per evitare che richieste reiterate a DuckDuckGo down degradino le performance. Usa un contatore errori con finestra temporale.

### Fase 10: Invalidazione cache retrieval su aggiornamento DB normativa
Quando il DB normattiva.sqlite viene aggiornato (import Normattiva), invalida la retrieval cache per le query normative. Aggiungi un hook in `lex/retrieval/cache.py`.

### Fase 11: Riscrittura automatica query nelle route giurisprudenza/normativa
Modifica `lex/workflows/giurisprudenza_workflow.py` e i workflow normativi per invocare `rewrite_query_for_legal_research()` prima di passare la query a `QueryPlanner`. Questo attiva automaticamente la distinzione pubblico/privato.

### Fase 12: Revisione `DeterministicProvider` per workflow fascicolo
Limita l'uso di `DeterministicProvider` ai soli workflow operativi (`economico`, `cabina`, `next_action`, `telematico_status`, `compliance`). Per workflow `fascicolo` senza contesto fascicolo adeguato, usa `OllamaProvider` con sistema prompt specializzato.

### Fase 13: Dashboard Lex per avvocati
Aggiungi un pannello visibile nella UI che mostri per ogni risposta: provider usato, fonti consultate (con tier), gap di copertura, query riscritta (solo porzione pubblica), se LDR è stato usato. Questo trasforma la trasparenza del sistema da tecnica a operativa.

---

*Documento generato per uso interno — Iusentra Legal Platform*
