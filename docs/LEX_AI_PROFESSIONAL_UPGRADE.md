# Lex AI — Professional Upgrade

**Versione:** 1.0.0
**Data:** 2026-05-08
**Ambito:** Trasformazione di Lex da assistente AI generativo a assistente legale professionale evidence-first

---

## 1. Scopo

L'obiettivo del Professional Upgrade è rendere Lex un assistente legale credibile e verificabile per l'avvocato. Prima dell'upgrade, Lex operava come un sistema di chat vincolata: rispondeva sulla base di ciò che il retrieval interno trovava, ma senza distinguere la query privata dell'utente dalla materia giuridica pubblica ricercabile, senza comunicare trasparentemente le ragioni delle proprie risposte, e senza integrare in modo automatico i canali di ricerca pubblica disponibili.

Il Professional Upgrade introduce quattro capacità nuove:

1. **Riscrittura privacy-safe della query** — la query originale dell'utente viene separata in una versione interna (con nomi propri, per il retrieval sui fascicoli) e una versione pubblica anonimizzata (solo materia giuridica, per web ufficiale e Local Deep Research).
2. **Gateway di ricerca pubblica coordinato** — un layer che coordina retrieval interno, ricerca web su domini ufficiali e Local Deep Research, normalizza i risultati e calcola i gap di copertura.
3. **Routing provider professionale per workflow** — cinque profili espliciti (classifier, retrieval_summarizer, legal_reasoner, drafter, deterministic) garantiscono che il provider corretto sia usato per ogni tipo di richiesta.
4. **Pannello debug per amministratori** — un payload di diagnostica completo (20+ campi) rende trasparente perché Lex ha risposto in un certo modo, quale provider ha usato, se LDR o il web sono stati coinvolti, e quale confidence ha raggiunto.

---

## 2. Flusso prima dell'upgrade

```
Richiesta utente
      |
      v
orchestrator_http.py
      |
      v
build_bounded_http_payload()
      |
      v
LexService.ask()  -->  LexOrchestrator.run()
                              |
                              v
                    QueryPlanner.plan()
                              |
                    [query originale usata direttamente]
                              |
                              v
                    SourceRouter.resolve()
                              |
                              v
                    RetrievalOrchestrator.collect()
                      |-- retrieval interno
                      |-- OfficialWebSource (se abilitato)
                      |   [query non anonimizzata: LDR blocca]
                      |
                              v
                    ProviderRegistry.pick()
                    [nessun profilo: pick() grezzo]
                              |
                              v
                    ResponseFormatter
                    [nessun campo debug nella UI]
                              |
                              v
                    payload JSON  -->  UI
                    [ldr_used, web_blocked_reason, public_research_query
                     non presenti nel payload]
```

**Limiti principali:**
- La query privata dell'utente (con nomi propri, numeri RG) veniva passata direttamente ai canali pubblici. LDR bloccava correttamente, ma la materia giuridica valida veniva persa.
- Il provider veniva selezionato con `pick()` grezzo, senza profilo esplicito.
- Il payload JSON alla UI non includeva i campi di diagnostica: l'avvocato non sapeva perché Lex aveva risposto in quel modo.

---

## 3. Flusso dopo l'upgrade

```
Richiesta utente
      |
      v
orchestrator_http.py
      |
      v
build_bounded_http_payload()
      |
      v
LexService.ask()  -->  LexOrchestrator.run()
                              |
                              v
                    QueryPlanner.plan()
                              |
                    [NUOVO] privacy_safe_query_rewriter.py
                    rewrite_query_for_legal_research()
                    |
                    |-- private_context_query   (con nomi propri → retrieval interno)
                    |-- public_research_query   (solo materia giuridica → web / LDR)
                    |-- official_sources_query  (ottimizzata per normattiva / GU)
                    |-- can_use_ldr             (bool)
                    |-- sensitivity             (public | internal | sensitive | highly_sensitive)
                              |
                              v
                    SourceRouter.resolve()
                              |
                              v
                    RetrievalOrchestrator.collect()
                      |-- retrieval interno (private_context_query)
                      |-- OfficialWebSource (public_research_query)
                      |-- [NUOVO] legal_research_integrator.py
                              run_public_research_for_request()
                              |
                              v
                         public_legal_research_gateway.py
                         run_public_legal_research()
                           |-- fonti ufficiali interne
                           |-- web ufficiale (domini allowlist)
                           |-- Local Deep Research (se can_use_ldr)
                           |-- dedup + ranking
                           |-- coverage_gaps
                              |
                              v
                    [AGGIORNATO] ProviderRegistry.pick_with_profile()
                    profilo: classifier | retrieval_summarizer |
                             legal_reasoner | drafter | deterministic
                              |
                              v
                    [AGGIORNATO] ResponseFormatter / professional_answer.py
                              |
                    [NUOVO] debug_payload_builder.py
                    build_lex_debug_payload()
                    [solo per superadmin, admin_studio, admin]
                              |
                              v
                    payload JSON  -->  UI
                    [include: ldr_used, web_used, public_research_query,
                     confidence_reason, removed_sensitive_tokens,
                     coverage_gaps, provider, profile, ...]
```

---

## 4. Componenti aggiunti

### 4.1 `lex/research/privacy_safe_query_rewriter.py`

Modulo che separa strutturalmente la query originale dell'utente in varianti per canali diversi.

**Funzione principale:** `rewrite_query_for_legal_research(original_query, ...)`

**Output:** `PrivacySafeResearchQuery` con i campi:
- `private_context_query` — mantiene nomi propri, rimuove solo identificatori forti (CF, IBAN, email, RG, telefono)
- `public_research_query` — solo materia giuridica, nessun dato personale
- `official_sources_query` — ottimizzata per normattiva.it, gazzettaufficiale.it, giustizia.it
- `local_deep_research_query` — uguale alla pubblica se `can_use_ldr`, altrimenti stringa vuota
- `sensitivity` — classificazione: `public | internal | sensitive | highly_sensitive`
- `can_use_ldr`, `can_use_official_web`, `can_use_external_provider`
- `removed_sensitive_tokens` — lista dei token rimossi
- `warnings` — avvisi sulla riscrittura

Documentazione completa: [LEX_PRIVACY_SAFE_QUERY_REWRITER.md](./LEX_PRIVACY_SAFE_QUERY_REWRITER.md)

---

### 4.2 `lex/research/public_legal_research_gateway.py`

Gateway che coordina tutti i canali di ricerca pubblica in un unico layer normalizzato.

**Funzione principale:** `run_public_legal_research(rewritten_query, source_mode, max_results)`

**Output:** `PublicLegalResearchResult` con campi principali:
- `sources` — lista di `NormalizedSource` (struttura uniforme per tutti i canali)
- `official_sources` — sottoinsieme con fonti istituzionali verificate
- `ldr_sources` — risultati LDR
- `coverage_gaps` — materie non coperte dalle fonti disponibili
- `ldr_used`, `ldr_blocked_reason`, `web_used`, `web_blocked_reason`
- `confidence_seed` — stima iniziale di confidenza basata sulle fonti trovate

Documentazione completa: [LEX_PUBLIC_RESEARCH_GATEWAY.md](./LEX_PUBLIC_RESEARCH_GATEWAY.md)

---

### 4.3 `lex/retrieval/legal_source_router.py`

Layer di classificazione del dominio giuridico che arricchisce la selezione delle fonti.

Riconosce 10 domini giuridici distinti tramite pattern token:
- Normativa nazionale, Normativa UE
- Giurisprudenza civile e penale
- Tributario
- Telematico civile (PCT/PST), penale (PDP), amministrativo (PAT/SIGA), tributario (PTT/SIGIT)
- Compensi forensi, mediazione, domicili digitali

Non sostituisce `SourceRouter` esistente: fornisce un layer di arricchimento che il `RetrievalOrchestrator` può interrogare.

---

### 4.4 `lex/retrieval/legal_chunking.py`

Suddivide atti, sentenze e documenti legali in chunk strutturati per sezione giuridica.

Sezioni riconosciute: `intestazione`, `parti`, `fatto`, `diritto`, `motivi`, `pqm`, `richieste`, `eccezioni`, `allegati`, `date`, `importi`, `norme_citate`, `sentenze_citate`, `scadenze`, `prove`, `ricevute_telematiche`.

Ogni chunk include metadati sufficienti (`section_type`, `doc_id`, `page`, `char_offset`) per essere usato come `EvidenceItem` nel pipeline senza perdere il contesto di provenienza.

---

### 4.5 `lex/retrieval/legal_research_integrator.py`

Connettore tra il Privacy-Safe Query Rewriter, il Public Legal Research Gateway e il `RetrievalOrchestrator` esistente.

**Funzione principale:** `run_public_research_for_request(request, context, workflow)`

Viene invocato dal `RetrievalOrchestrator` quando:
- Il workflow è in `{normativa, giurisprudenza, prassi, research, fonti}`
- L'evidenza interna non è sufficiente
- `allow_external_research=True` nella richiesta

Restituisce un dizionario di campi da mergiare nell'`EvidencePack`.

---

### 4.6 `lex/formatting/debug_payload_builder.py`

Costruisce il payload di diagnostica completo per amministratori.

**Funzione principale:** `build_lex_debug_payload(request, context, workflow, evidence, draft, verdict, response, ...)`

**Controllo accesso:** `should_include_debug(user_role)` — solo `superadmin`, `admin_studio`, `admin`.

I dati sensibili non vengono mai esposti: `private_context_query` appare come `[REDATTO PER PRIVACY]`, i token rimossi vengono esposti solo come conteggio, i path assoluti vengono sanitizzati al basename, le chiavi API non appaiono mai.

Documentazione completa: [LEX_DEBUG_UI.md](./LEX_DEBUG_UI.md)

---

### 4.7 `lex/providers/registry.py` (aggiornato)

Aggiunge i metodi `pick_with_profile()` e `get_routing_metadata()` al `ProviderRegistry` esistente.

`pick_with_profile()` ritorna una tupla `(provider, profile_name, reason)` dove `profile_name` è uno dei cinque profili: `classifier`, `retrieval_summarizer`, `legal_reasoner`, `drafter`, `deterministic`.

`get_routing_metadata()` ritorna un dizionario con `provider`, `profile`, `reason`, `workflow`, `external_allowed`, `ollama_url` — usato dal payload debug.

Documentazione completa: [LEX_MODEL_ROUTING.md](./LEX_MODEL_ROUTING.md)

---

### 4.8 `lex/formatting/professional_answer.py` (aggiornato)

Aggiorna il formatter della risposta professionale per includere i nuovi campi nel payload JSON finale:
- `ldr_used`, `ldr_blocked_reason`
- `web_used`, `web_blocked_reason`
- `public_research_query`
- `removed_sensitive_tokens` (solo conteggio)
- `official_sources_count`, `internal_sources_count`
- `debug` (payload debug, solo per ruoli autorizzati)

---

## 5. Variabili d'ambiente chiave

| Variabile | Default | Descrizione |
|---|---|---|
| `LEX_GOVERNED_ONLY` | `1` (true) | Abilita il bounded workflow per ogni richiesta. Impostare `0` solo per debug. |
| `LEX_EXTERNAL_ALLOWED` | non impostata (false) | Abilita provider esterni (OpenAI) e la trasmissione di query a LDR quando la sensitivity lo consente. |
| `LEX_RAW_CHAT_ENABLED` | non impostata (false) | Abilita la chat libera non governata. Mantenere disabilitata in produzione. |
| `LEX_DEFAULT_PROVIDER` | `ollama` | Provider predefinito per workflow non deterministici. |
| `LEX_PROVIDER_FORCE_MOCK` | non impostata | Forza il provider mock (usato dai test automatici). |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | URL del runtime Ollama locale. |
| `PCT_LEX_OFFICIAL_EXTRA_DOMAINS` | non impostata | Domini aggiuntivi per la ricerca web ufficiale (separati da virgola). |

---

## 6. Criteri di accettazione

I seguenti criteri devono essere verificabili dopo il deploy:

1. **Riscrittura query** — Data la query `"Nel fascicolo Rossi RG 1234/2025 posso eccepire la prescrizione?"`, il campo `public_research_query` nel payload debug deve contenere solo termini giuridici (es. `"prescrizione eccezione termine"`) e nessun nome proprio o numero RG.

2. **LDR bloccato su query sensibile** — Una query con sensitivity `highly_sensitive` deve avere `ldr_used=false` e `ldr_blocked_reason` non vuoto nel payload debug.

3. **Coverage gaps visibili** — Per un workflow `normativa` senza fonti interne disponibili, il campo `coverage_gaps` nel payload debug deve essere non vuoto e descrivere le fonti mancanti.

4. **Profilo provider corretto** — Per il workflow `giurisprudenza`, il campo `profile` nel payload debug deve essere `legal_reasoner` e il `provider` deve essere `ollama`.

5. **Provider deterministico solo per workflow operativi** — Per il workflow `economico`, il campo `provider` deve essere `deterministic` e `profile` deve essere `deterministic`.

6. **Debug visibile solo agli amministratori** — Un utente con ruolo `avvocato` non deve ricevere il campo `debug` nel payload JSON. Un utente con ruolo `admin` deve riceverlo.

7. **Nessuna chiave API nel debug** — Il payload debug non deve contenere alcuna chiave API, token di autenticazione o path assoluto a file di sistema.

8. **Fallback graceful su LDR non configurato** — Se LDR non è configurato, Lex deve rispondere normalmente senza bloccarsi, con `ldr_used=false` e `ldr_blocked_reason="LDR non configurato"`.

---

## 7. Rollback plan

In caso di regressione critica dopo il deploy:

```bash
# Identificare il commit prima dell'upgrade
git log --oneline -20

# Revert al commit precedente (creare un nuovo commit di revert)
git revert <commit-hash-upgrade>

# Push sul branch di sviluppo
git push origin claude/legal-electronic-filing-kIxcV
```

I moduli aggiunti (`privacy_safe_query_rewriter.py`, `public_legal_research_gateway.py`, `legal_source_router.py`, `legal_chunking.py`, `legal_research_integrator.py`, `debug_payload_builder.py`) sono disaccoppiati dal flusso principale: se il loro import fallisce, il `legal_research_integrator.py` restituisce un dizionario di errore senza bloccare il pipeline Lex.

I metodi `pick_with_profile()` e `get_routing_metadata()` sono aggiuntivi rispetto al `pick()` originale: il rollback del registry ripristina il comportamento precedente senza impatto sul flusso.

---

## 8. Riferimenti

- [LEX_PUBLIC_RESEARCH_GATEWAY.md](./LEX_PUBLIC_RESEARCH_GATEWAY.md) — gateway di ricerca pubblica
- [LEX_PRIVACY_SAFE_QUERY_REWRITER.md](./LEX_PRIVACY_SAFE_QUERY_REWRITER.md) — riscrittura query privacy-safe
- [LEX_DEBUG_UI.md](./LEX_DEBUG_UI.md) — pannello debug amministratori
- [LEX_MODEL_ROUTING.md](./LEX_MODEL_ROUTING.md) — routing provider e profili
- [LEX_AI_PROFESSIONAL_UPGRADE_AUDIT.md](./LEX_AI_PROFESSIONAL_UPGRADE_AUDIT.md) — audit tecnico di partenza

---

*Documento interno — IUSENTRA Legal Platform*
