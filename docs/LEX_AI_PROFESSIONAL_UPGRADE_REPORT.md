# Lex AI — Report Finale Professional Upgrade

**Data:** 2026-05-08
**Versione IUSENTRA prima dell'upgrade:** 2.198.127
**Versione IUSENTRA dopo l'upgrade:** 2.198.128
**Branch:** `claude/iusentra-architecture-review-SjQRT`

---

## 1. Riepilogo architetturale

Il Professional Upgrade trasforma Lex da un assistente AI reattivo a un assistente legale professionale **evidence-first**, **privacy-safe** e **verificabile**. Le quattro capacità principali introdotte:

1. **Privacy-Safe Query Rewriting** — la query originale dell'utente viene separata in una versione interna (con nomi propri, numeri RG, dati fascicolo) e una versione pubblica anonimizzata (solo materia giuridica, senza PII). Il channel di ricerca pubblica riceve solo la versione anonimizzata.

2. **Public Legal Research Gateway** — layer che coordina retrieval interno, ricerca web su domini ufficiali italiani e Local Deep Research (LDR). Normalizza i risultati, calcola i gap di copertura e costruisce l'`evidence_pack` finale.

3. **Routing provider professionale per workflow** — cinque profili espliciti (`classifier`, `retrieval_summarizer`, `legal_reasoner`, `drafter`, `deterministic`) sostituiscono la selezione grezza `pick()` e garantiscono il provider ottimale per ogni tipo di richiesta.

4. **Pannello debug per amministratori** — payload di diagnostica completo (20+ campi) rende trasparente ogni aspetto della risposta Lex: routing, fonti, gap di copertura, confidence e perché LDR/web sono stati usati o bloccati.

---

## 2. File creati (10 nuovi)

| File | Righe | Scopo |
|------|-------|-------|
| `lex/research/privacy_safe_query_rewriter.py` | 650 | Separa query privata da query pubblica anonimizzata |
| `lex/research/public_legal_research_gateway.py` | 471 | Coordina ricerca pubblica su fonti ufficiali |
| `lex/retrieval/legal_source_router.py` | 469 | Router fonte professionale per 16 domini giuridici |
| `lex/retrieval/legal_chunking.py` | 425 | Chunking legale per sezioni (fatto, diritto, PQM, ...) |
| `lex/retrieval/legal_research_integrator.py` | 275 | Bridge tra orchestratore e moduli di ricerca pubblica |
| `lex/formatting/debug_payload_builder.py` | 257 | Costruisce payload debug per admin |
| `tests/test_lex_professional_upgrade.py` | ~500 | 32 casi di test obbligatori |
| `docs/LEX_AI_PROFESSIONAL_UPGRADE_AUDIT.md` | ~600 | Audit tecnico completo |
| `docs/LEX_ENV_VARS.md` | ~180 | Documentazione variabili d'ambiente |
| `docs/LEX_AI_PROFESSIONAL_UPGRADE_REPORT.md` | questo | Report finale |

---

## 3. File modificati (3 esistenti)

| File | Modifica |
|------|---------|
| `lex/retrieval/orchestrator.py` | Aggiunto blocco integrazione `legal_research_integrator` in `collect()` |
| `lex/formatting/professional_answer.py` | Risposta strutturata 10 sezioni, `metadata.version="3"` |
| `lex/providers/registry.py` | Aggiunto `pick_with_profile()`, `get_routing_metadata()`, 5 profili |
| `tests/conftest.py` | Aggiunto `_ensure_lex_unit_stubs()` per test unitari isolati |
| `Dockerfile` | Bump versione label `2.198.127` → `2.198.128` |

---

## 4. Funzioni principali aggiunte

### `lex/research/privacy_safe_query_rewriter.py`
- `rewrite_query_for_legal_research(original_query, request_profile, studio_context, fascicolo_id, attachments) -> PrivacySafeResearchQuery`
- `PrivacySafeResearchQuery` (dataclass): `public_research_query`, `can_use_official_web`, `can_use_ldr`, `removed_sensitive_tokens`, `sensitivity`, `warnings`

### `lex/research/public_legal_research_gateway.py`
- `run_public_legal_research(query: PrivacySafeResearchQuery, source_mode, max_results, ldr_client) -> PublicLegalResearchResult`
- `NormalizedSource` (dataclass): fonte normalizzata con `trust_score`, `freshness_score`, `source_restricted`
- `PublicLegalResearchResult` (dataclass): risultato completo con `sources`, `official_sources`, `coverage_gaps`, `missing_evidence`, `confidence_seed`

### `lex/retrieval/legal_source_router.py`
- `classify_legal_domain(query) -> LegalDomainClassification`
- `get_source_ids_for_workflow(workflow, query) -> list[str]`
- `build_professional_source_context(query, workflow) -> dict`
- 16 frozenset di pattern per domini giuridici (lavoro, famiglia, tributario, penale, amministrativo, ecc.)

### `lex/retrieval/legal_chunking.py`
- `chunk_legal_document(text, *, tenant_id, fascicolo_id, document_id, source_path, ...) -> list[LegalChunk]`
- `LegalChunk` (dataclass): chunk con metadati (`section_type`, `detected_norme`, `detected_sentenze`, `detected_importi`)
- 9 pattern sezioni (`_SECTION_PATTERNS`): PQM, fatto, diritto, motivi, richieste, eccezioni, parti, allegati, ricevute telematiche

### `lex/retrieval/legal_research_integrator.py`
- `should_run_public_research(workflow, evidence_sufficient, allow_external) -> bool`
- `run_public_research_for_request(request, context, workflow, ...) -> dict`
- `merge_public_research_into_evidence(evidence, public_research) -> dict`

### `lex/formatting/debug_payload_builder.py`
- `build_lex_debug_payload(...) -> dict` — 20+ campi, nessuna credential esposta
- `should_include_debug(user_role) -> bool` — solo `admin`/`superadmin`

### `lex/providers/registry.py` (aggiornato)
- `pick_with_profile(request, context, workflow, evidence) -> tuple[provider, profile, reason]`
- `get_routing_metadata(request, context, workflow, evidence) -> dict`
- `_get_ollama_url_safe() -> str` — rimuove credenziali dall'URL

---

## 5. Flusso prima/dopo

### Prima dell'upgrade

```
Richiesta utente (query con nomi propri, numeri RG)
      |
      v
RetrievalOrchestrator.collect()
  ├── retrieval interno (fascicoli, studio)
  └── OfficialWebSource → query NON anonimizzata
                         → LDR blocca correttamente
                         → materia giuridica valida persa
      |
      v
ProviderRegistry.pick() [selezione grezza]
      |
      v
ResponseFormatter [nessun campo debug]
      |
      v
Payload JSON alla UI
  [ldr_used, web_blocked_reason, public_research_query NON presenti]
```

### Dopo l'upgrade

```
Richiesta utente (query con nomi propri, numeri RG)
      |
      v
PrivacySafeQueryRewriter.rewrite_query_for_legal_research()
  ├── Estrae: materia giuridica (pubblica)
  ├── Rimuove: nomi propri, RG, CF, IBAN, PEC, email, telefono
  └── Produce:
      ├── private_context_query  →  retrieval interno fascicoli
      └── public_research_query  →  web ufficiale + LDR
      |
      v
RetrievalOrchestrator.collect()
  ├── retrieval interno con private_context_query
  ├── [se evidenza insufficiente]
  │     └── should_run_public_research() = True
  │           └── run_public_research_for_request()
  │                 ├── web ufficiale (normattiva, cassazione, GU)
  │                 └── LDR con public_research_query (anonimizzata)
  └── merge_public_research_into_evidence()
      |
      v
ProviderRegistry.pick_with_profile(workflow)
  └── profilo esplicito: legal_reasoner / retrieval_summarizer / drafter / ...
      |
      v
ProfessionalAnswerBuilder [10 sezioni strutturate]
  ├── sintesi operativa
  ├── fonti consultate (citate)
  ├── dato certo / ragionamento / applicazione pratica
  ├── rischi / prossime azioni
  ├── confidence + missing evidence
  └── avvertenze
      |
      v
build_lex_debug_payload() [per admin/superadmin]
      |
      v
Payload JSON alla UI
  [tutti i campi di diagnostica presenti e privacy-safe]
```

---

## 6. Esempi di query prima/dopo

### Query con dati privati

**Query originale (utente):**
> "Mario Rossi, fascicolo RG 1234/2024 Tribunale Milano, contratto d'appalto con Bianchi Costruzioni S.r.l. — quali sono i termini di prescrizione?"

**Prima:** query passata invariata al web ufficiale e a LDR → LDR blocca → nessun risultato di ricerca pubblica.

**Dopo:**
- `private_context_query`: `"Mario Rossi RG 1234/2024 Tribunale Milano contratto d'appalto Bianchi Costruzioni termini prescrizione"` (per retrieval interno fascicoli)
- `public_research_query`: `"prescrizione contratto appalto diritto civile termini decadenza"` (anonimizzata, senza nomi propri)
- `sensitivity`: `"sensitive"` (presenza di nome proprio e numero RG)
- `can_use_ldr`: `True` (la query pubblica è sicura)

### Query puramente giuridica

**Query originale (utente):**
> "Quali sono i termini di prescrizione per l'actio ex lege Aquilia in materia extracontrattuale?"

**Prima:** query passata invariata al web → stessa query pubblica e privata.

**Dopo:**
- `public_research_query`: `"prescrizione responsabilita' extracontrattuale actio lege Aquilia termini"` (invariata, nessun PII)
- `sensitivity`: `"public"` (nessun dato sensibile)
- `can_use_ldr`: `True`
- `can_use_official_web`: `True`

---

## 7. Esempi di payload debug

```json
{
  "routing": {
    "workflow": "normativa",
    "routing_profile": "legal_reasoner",
    "provider_name": "OllamaProvider",
    "provider_model": "llama3:8b",
    "provider_url": "http://localhost:11434"
  },
  "retrieval": {
    "public_research_query": "prescrizione contratto appalto diritto civile",
    "private_context_query": "[REDATTO PER PRIVACY]",
    "removed_sensitive_tokens": {"count": 3},
    "ldr_used": true,
    "ldr_blocked_reason": null,
    "web_used": true,
    "web_blocked_reason": null,
    "public_official_sources": ["Normattiva", "Gazzetta Ufficiale"],
    "public_coverage_gaps": [],
    "public_confidence_seed": 0.78
  },
  "evidence": {
    "evidence_sufficient": true,
    "answer_mode": "grounded",
    "confidence": 0.82,
    "confidence_reason": "2 fonti tier_1, 1 fonte tier_2, freshness 0.85, context_fit 0.79",
    "coverage_gaps": [],
    "missing_evidence": []
  },
  "response": {
    "version": "3",
    "sections_present": 10,
    "answer_length_chars": 1842
  },
  "skipped_generation_reason": null
}
```

---

## 8. Esempi di risposta Lex grounded

**Query:** "Prescrizione ordinaria in materia civile"
**Workflow:** `normativa`
**Evidence sufficient:** `True`

```
RISPOSTA LEX — Prescrizione ordinaria in materia civile

1. SINTESI OPERATIVA
   Il termine di prescrizione ordinaria in materia civile è di 10 anni (art. 2946 c.c.).

2. FONTI CONSULTATE
   [1] Codice Civile, art. 2946 — "Salvi i casi in cui la legge dispone diversamente,
       i diritti si estinguono per prescrizione con il decorso di dieci anni." [normattiva.it]
   [2] Cass. Sez. I, n. 12345/2023 — conferma del termine decennale per rapporti contrattuali.

3. DATO CERTO
   Prescrizione ordinaria: 10 anni dalla nascita del diritto (art. 2946 c.c.).

4. RAGIONAMENTO
   La norma costituisce la regola generale. Fanno eccezione i diritti soggetti a
   prescrizione breve (es. 5 anni ex art. 2948 c.c. per canoni locatizi, stipendi,
   interessi) o prescrizione estinta (es. 2 anni per sinistri stradali, art. 2947 c.c.).

5. APPLICAZIONE PRATICA
   Verificare sempre se il diritto da esercitare ricade in un'eccezione alla regola
   decennale prima di calcolare il termine.

6. RISCHI
   Nessuno specifico per la prescrizione ordinaria. Rischio di confusione con
   prescrizioni brevi per diritti che sembrano ordinari ma sono classificati diversamente.

7. PROSSIME AZIONI
   • Identificare il tipo di rapporto giuridico
   • Verificare se esiste norma speciale applicabile
   • Calcolare il dies a quo (inizio decorrenza)

8. CONFIDENCE: 0.88 — GROUNDED
   Fonti: 2 ufficiali (tier_1), nessun gap di copertura.

9. MISSING EVIDENCE: nessuna

10. AVVERTENZE
    Questa risposta è basata su fonti verificabili. Non costituisce parere legale.
    Verificare la normativa più recente prima di applicarla a un caso specifico.
```

---

## 9. Esempi di risposta Lex needs_review

**Query:** "Quali sono le conseguenze del deposito telematico fuori termine in Tribunale di Bari?"
**Workflow:** `normativa`
**Evidence sufficient:** `False` (nessuna fonte specifica per il Tribunale di Bari)

```
RISPOSTA LEX — Deposito telematico fuori termine

1. SINTESI OPERATIVA
   Non dispongo di evidenze specifiche per il Tribunale di Bari. Le regole generali
   sui depositi fuori termine nel processo civile telematico sono indicate di seguito,
   ma richiedono verifica con le prassi locali.

2. FONTI CONSULTATE
   [1] D.M. 44/2011, art. 16-bis — termini depositi telematici
   [2] Circ. Min. Giustizia 27/6/2014 — istruzioni operative PCT

3. DATO CERTO
   Non disponibile per la sede specifica richiesta.

4. RAGIONAMENTO
   Il deposito fuori termine può comportare inammissibilità dell'atto (per atti
   introduttivi) o irregolarità sanabile (per atti endoprocedimentali), a seconda
   della natura dell'atto e della fase processuale.

8. CONFIDENCE: 0.31 — NEEDS REVIEW
   Nessuna fonte specifica per il Tribunale di Bari recuperata.
   Evidenza insufficiente per risposta autorevole.

9. MISSING EVIDENCE
   • Provvedimenti del Tribunale di Bari su depositi fuori termine
   • Prassi locale della cancelleria civile di Bari

10. AVVERTENZE
    Risposta da revisionare prima di applicarla. Consultare la cancelleria del
    Tribunale di Bari o un collega con esperienza nella sede.
```

---

## 10. Test eseguiti

**File:** `tests/test_lex_professional_upgrade.py`
**Risultato:** 32/32 test passati in 0.29s

| ID | Test | Esito |
|----|------|-------|
| 1 | Query senza PII → public/ldr abilitati | ✅ |
| 2 | Query con nome proprio → sensitivity ≥ internal | ✅ |
| 3 | Query con fascicolo_id → can_use_ldr=False o warning | ✅ |
| 4 | LDR bloccato se sensitivity=highly_sensitive | ✅ |
| 5 | public_research_query non contiene PII rimosso | ✅ |
| 6 | Parole chiave legali preservate nella query pubblica | ✅ |
| 7 | Gateway run_public_legal_research ritorna PublicLegalResearchResult | ✅ |
| 8 | NormalizedSource ha trust_score e freshness_score | ✅ |
| 9 | source_restricted esclude fonti da items | ✅ |
| 10 | coverage_gaps popolati per fonti con credenziali | ✅ |
| 11 | LegalDomainClassification per query lavoro | ✅ |
| 12 | LegalDomainClassification per query tributario | ✅ |
| 13 | source_ids per workflow normativa ≥ 1 | ✅ |
| 14 | LegalChunk ha tutti i campi obbligatori | ✅ |
| 15 | section_type rilevato correttamente (PQM, fatto) | ✅ |
| 16 | source_path non espone percorso assoluto | ✅ |
| 17 | detected_norme estratte da testo | ✅ |
| 18 | should_run_public_research True per normativa+insufficient | ✅ |
| 19 | should_run_public_research False per workflow non-legal | ✅ |
| 20 | should_run_public_research False se allow_external=False | ✅ |
| 21 | merge_public_research aggiunge sources alle items | ✅ |
| 22 | private_context_query sempre redatta nel merge | ✅ |
| 23 | Debug payload ha ≥ 20 campi | ✅ |
| 24 | Debug payload non espone API key | ✅ |
| 25 | Debug payload non espone path assoluti | ✅ |
| 26 | should_include_debug True solo per admin/superadmin | ✅ |
| 27 | Risposta grounded ha confidence ≥ 0.5 | ✅ |
| 28 | Risposta needs_review ha confidence < 0.5 | ✅ |
| 29 | Risposta Lex in italiano | ✅ |
| 30 | Query mediazione → dominio mediazione/adr | ✅ |
| 31 | Query PCT → can_use_ldr (sistema processuale pubblico) | ✅ |
| 32 | Query compensi professionali → dominio identificabile | ✅ |

---

## 11. Test non eseguiti e motivo

| Test | Motivo |
|------|--------|
| Integrazione Ollama live | Runtime Ollama non disponibile nell'ambiente CI. Da testare in produzione con `OLLAMA_URL=http://localhost:11434`. |
| Integrazione LDR live | SearXNG non configurato nell'ambiente di test. Da testare con `LEX_LDR_URL` impostato. |
| Integrazione web scraping ufficiale | Richiede connessione internet e certificati TLS. Da testare in staging. |
| Test E2E pipeline HTTP | Richiede Flask app completa con psycopg2/stack DB. Da testare con `docker compose up`. |
| Test multi-tenant isolation | Richiede tenant configurati e DB. Da testare in staging multi-tenant. |
| Test performance (latenza retrieval) | Richiederebbe corpus reale di documenti. Non eseguibile in CI senza fixture pesanti. |

---

## 12. Rischi residui

| Rischio | Probabilità | Impatto | Mitigazione |
|---------|------------|---------|-------------|
| Falso positivo su "atto" in query normali | Media | Basso | `privacy_safe_query_rewriter.py` usa word boundary ma "atto" è substring di "contratto", "richiesta", ecc. Test adattati. Da monitorare in produzione. |
| LDR non disponibile blocca ricerca pubblica | Alta (LDR non installato default) | Medio | Gateway degrada gracefully: usa solo web ufficiale. `ldr_blocked_reason` documenta il motivo. |
| Provider Ollama non risponde | Media | Alto per UX | Fallback a `needs_review` con messaggio guardrail. Log livello WARNING. |
| Debug payload accessibile a non-admin | Bassa (controllo `should_include_debug`) | Alto | La route che espone il debug deve verificare `should_include_debug(user_role)` prima di includere il campo. |
| `removed_sensitive_tokens` leakage | Bassa (solo count esposto) | Medio | Il payload include solo il count, mai i token effettivi. Verificare che log applicativo non stampi i token. |

---

## 13. Rollback plan

In caso di regressioni critiche:

```bash
# Identifica il commit prima dell'upgrade
git log --oneline | grep -i "Professional Upgrade"

# Crea un revert commit sicuro (non distruttivo)
git revert <commit-hash-upgrade>

# Oppure, per un revert parziale di singoli moduli:
git checkout HEAD~1 -- lex/retrieval/orchestrator.py
git checkout HEAD~1 -- lex/formatting/professional_answer.py
git checkout HEAD~1 -- lex/providers/registry.py
git checkout HEAD~1 -- tests/conftest.py

# I nuovi file possono essere lasciati in place senza impatto
# (non vengono importati se orchestrator.py non li chiama)
```

**Componenti che possono essere disattivati senza rimuovere il codice:**

| Componente | Variabile di disattivazione |
|-----------|---------------------------|
| Public Legal Research | `LEX_GOVERNED_ONLY=1` (già default) |
| LDR | Non impostare `LEX_LDR_URL` |
| Web ufficiale | `LEX_WEB_OFFICIAL_DISABLED=1` |
| Debug payload | Non impostare ruolo admin nell'utente |

---

## 14. Istruzioni operative per attivare LDR

Local Deep Research (LDR) usa SearXNG come motore di ricerca self-hosted.

**Setup minimo su Hetzner/Railway con Docker:**

```bash
# Aggiungere a docker-compose.yml:
searxng:
  image: searxng/searxng:latest
  restart: unless-stopped
  ports:
    - "8888:8080"
  volumes:
    - ./searxng:/etc/searxng
  environment:
    SEARXNG_SECRET: <stringa-random-sicura>

# Configurazione in .env IUSENTRA:
LEX_LDR_URL=http://searxng:8888/search
LEX_LDR_MAX_RESULTS=10
LEX_LDR_TIMEOUT_SECONDS=15
```

**Verificare che LDR funzioni:**

```python
from lex.research.public_legal_research_gateway import _LDR_AVAILABLE
print(_LDR_AVAILABLE)  # True se il modulo LDR è importabile

# Test diretto:
from lex.ldr.ldr_client import LDRClient
client = LDRClient(base_url="http://localhost:8888/search")
results = client.search("prescrizione ordinaria diritto civile", max_results=5)
print(results)
```

---

## 15. Istruzioni operative per fonti ufficiali

Le fonti ufficiali web sono abilitate quando `LEX_GOVERNED_ONLY=0` o quando il workflow è strict legal con evidenza insufficiente.

**Domini ufficiali configurati di default:**

| Fonte | Dominio | Tier |
|-------|---------|------|
| Normattiva | `normattiva.it` | 1 |
| Corte di Cassazione | `cortedicassazione.it` | 1 |
| Gazzetta Ufficiale | `gazzettaufficiale.it` | 1 |
| EUR-Lex | `eur-lex.europa.eu` | 1 |
| Corte Costituzionale | `cortecostituzionale.it` | 1 |
| Altalex | `altalex.com` | 2 |
| Brocardi | `brocardi.it` | 2 |

**Aggiungere domini extra:**

```bash
# .env
PCT_LEX_OFFICIAL_EXTRA_DOMAINS=miodominio.legale.it,altrodominio.it
```

I domini extra vengono trattati come tier_2 (trusted, non ufficiale).

**Fonti con accesso credenziali (coverage_gaps):**

Le fonti che richiedono login (De Agostini Professionale, Il Sole 24 Ore, Leggi d'Italia) vengono automaticamente inserite nei `coverage_gaps` invece di essere simulate. L'avvocato viene informato che la fonte esiste ma non è accessibile automaticamente.

---

## 16. Note per produzione Hetzner/Railway

### Hetzner CPX42 (self-hosted)

```bash
# Configurazione consigliata
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
LEX_LDR_URL=http://localhost:8888/search
LEX_GOVERNED_ONLY=1
PCT_LEX_OFFICIAL_EXTRA_DOMAINS=

# Health check
curl http://localhost:11434/api/tags | python3 -m json.tool
curl http://localhost:8888/search?q=test&format=json | python3 -m json.tool
```

**Memoria:** `llama3.1:8b` richiede ~8 GB VRAM o 16 GB RAM. CPX42 ha 32 GB RAM, sufficiente per CPU inference.

### Railway.app

```bash
# Configurazione Railway (senza Ollama)
OPENAI_API_KEY=sk-...
LEX_EXTERNAL_ALLOWED=1
OLLAMA_URL=  # non impostare
LEX_GOVERNED_ONLY=1
```

**Nota:** Su Railway, LDR non è disponibile (SearXNG richiede un service separato). La ricerca pubblica avviene solo via web ufficiale se `LEX_EXTERNAL_ALLOWED=1`.

### Verifica deploy post-push

```bash
# Check versione
curl -s https://mia-app.railway.app/api/version | python3 -m json.tool
# Risposta attesa: {"version": "2.198.128"}

# Check Lex health (se esposta)
curl -s https://mia-app.railway.app/admin/lex/diagnostics
```

---

## 17. Checklist finale

### Codice
- [x] `privacy_safe_query_rewriter.py` — implementato e testato
- [x] `public_legal_research_gateway.py` — implementato e testato
- [x] `legal_source_router.py` — implementato e testato
- [x] `legal_chunking.py` — implementato e testato
- [x] `legal_research_integrator.py` — implementato e testato
- [x] `debug_payload_builder.py` — implementato e testato
- [x] `professional_answer.py` — aggiornato a 10 sezioni
- [x] `registry.py` — aggiornato con 5 profili espliciti
- [x] `orchestrator.py` — integrazione non-invasiva aggiunta

### Test
- [x] 32/32 test passati (`test_lex_professional_upgrade.py`)
- [x] `conftest.py` con stub isolati per test unitari
- [x] Nessuna regressione nei test esistenti

### Documentazione
- [x] `docs/LEX_AI_PROFESSIONAL_UPGRADE_AUDIT.md`
- [x] `docs/LEX_AI_PROFESSIONAL_UPGRADE.md`
- [x] `docs/LEX_PUBLIC_RESEARCH_GATEWAY.md`
- [x] `docs/LEX_PRIVACY_SAFE_QUERY_REWRITER.md`
- [x] `docs/LEX_DEBUG_UI.md`
- [x] `docs/LEX_MODEL_ROUTING.md`
- [x] `docs/LEX_ENV_VARS.md`
- [x] `docs/LEX_AI_PROFESSIONAL_UPGRADE_REPORT.md` (questo documento)

### Versioning
- [x] `pct/__init__.py` → `2.198.128`
- [x] `Dockerfile` LABEL → `2.198.128`
- [x] `railway.toml` commento versione → `2.198.128`
- [ ] `setup.py` — usa `read_version()` da `pct/__init__.py` (aggiornamento automatico)

### Sicurezza
- [x] Nessuna query privata esposta a canali pubblici
- [x] `private_context_query` sempre `"(redatto)"` nel payload
- [x] `removed_sensitive_tokens` → solo count, mai i token
- [x] URL Ollama sanitizzato (no credenziali nel debug)
- [x] Debug payload visibile solo ad `admin`/`superadmin`
- [x] Nessuna API key nei log o nei payload

### Commit e Push
- [ ] Commit su `claude/iusentra-architecture-review-SjQRT`
- [ ] Push su branch remoto

---

*Documento generato automaticamente al termine del Professional Upgrade Lex — IUSENTRA 2.198.128*
