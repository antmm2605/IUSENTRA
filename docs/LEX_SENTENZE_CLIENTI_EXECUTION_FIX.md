# LEX — Fix sentenze esatte e dati cliente (v2.202.0)

> **Versione:** 2.202.0 — Data: 08/05/2026

Documento di audit che descrive i bug corretti, le cause radice e le modifiche implementate.

---

## 1. Bug corretti

### BUG 1 — Sentenza esatta: frammento locale trattato come sufficiente

**Sintomo:** L'utente chiede "mi puoi trovare questa Sentenza n. 7919 del 31/03/2026". Lex trova un frammento locale (massima o estratto senza testo integrale, senza URL ufficiale), lo presenta come risposta sufficiente con "Evidenze elaborate: 12" e "Attendibilità alta/media". La risposta inizia con "Risposta deterministica per workflow 'giurisprudenza'".

**Causa radice:**
1. `giurisprudenza_specifica` NON era in `_STRICT_LEGAL_WORKFLOWS` → `should_run_public_research` non la includeva → ricerca web mai attivata
2. `_evidence_is_sufficient` per `giurisprudenza_specifica` cadeva nel ramo `else: return strong_count >= 1` → un singolo frammento con score ≥ 0.55 era sufficiente
3. Nessun confidence cap specifico per sentenze senza URL ufficiale o testo completo

### BUG 2 — Dati cliente: risposta cabina invece di anagrafica

**Sintomo:** L'utente chiede "dati del cliente marco moscato". Lex risponde con la cabina operativa (agenda, scadenze, panorama studio) invece di cercare e mostrare i dati del cliente nell'anagrafica.

**Causa radice:**
1. `studio_data_lookup` non aveva un contratto in `contracts.py` → cadeva nel default
2. `DeterministicProvider.generate()` non aveva un handler per `studio_data_lookup` → else fallback → "Risposta deterministica per workflow 'studio_data_lookup'"
3. `build_lex_studio_context` non distingueva il workflow → caricava sempre tutte le sezioni inclusa cabina/quadro operativo

---

## 2. Modifiche implementate

### 2.1 `lex/retrieval/legal_research_integrator.py`
- Aggiunto `"giurisprudenza_specifica"` a `_STRICT_LEGAL_WORKFLOWS`
- Esteso `should_run_public_research()` con parametri: `exact_reference`, `local_case_law_incomplete`, `user_requested_public_source`
- Per `giurisprudenza_specifica`: ritorna sempre `True` (ricerca pubblica obbligatoria)

### 2.2 `lex/retrieval/orchestrator.py`
- `_evidence_is_sufficient()`: per `giurisprudenza_specifica` ritorna sempre `False` (anche con risultati locali forti)
- Chiamata a `should_run_public_research()` estesa con i nuovi flag
- `exact_reference` e `local_case_law_incomplete` derivati dai metadata della request

### 2.3 `lex/contracts.py`
- Aggiunto contratto `studio_data_lookup`:
  - `provider_hint="deterministic"`, `web_forbidden=True`, `studio_internal_only=True`
  - Sezioni: cliente_individuato, dati_anagrafici, recapiti, fascicoli_collegati, dati_mancanti, prossima_azione

### 2.4 `lex/providers/deterministic_provider.py`
- Aggiunto handler `studio_data_lookup` → chiama `studio_data_gateway.find_cliente()`, formatta risultato con dati CF/email/PEC/fascicoli
- Eliminato il fallback `"Risposta deterministica per workflow '...'"` → sostituito con `_generic_operational_text()` che non espone nomi tecnici interni
- Aggiunti `_studio_data_lookup_text()` e `_generic_operational_text()`

### 2.5 `lex/formatting/answer_builder.py`
- `giurisprudenza_specifica` aggiunto a `strict_workflow`
- Confidence cap: senza `exact_match_found` in metadata → ≤ 0.45; con exact_match senza full text → ≤ 0.55
- Per `studio_data_lookup`: `official_sources=[]`, `trusted_sources=[]`, `considered_sources=[]`
- `answer_mode="lookup"` per `studio_data_lookup` invece di "grounded"

### 2.6 `lex/context/studio_context.py`
- `build_studio_context()`: percorso rapido per `studio_data_lookup` — salta tutto il contesto cabina, chiama direttamente `studio_data_gateway.find_cliente()`
- Popola `studio.sources` solo con dati cliente trovati

### 2.7 `lex/prompts/prompt_builder.py`
- "Ciao, sono Lex." solo per messaggi vuoti o saluti generici
- Lista esplicita di tipo query operative per cui il saluto è vietato

### 2.8 Nuovi moduli creati
- **`lex/research/case_law_completeness.py`**: `CaseLawCompletenessResult`, `detect_case_law_fragment()` — classifica se un item è un frammento giurisprudenziale incompleto
- **`lex/guards/exact_case_law_guard.py`**: `ExactCaseLawCheckResult`, `check_exact_case_law()` — confidence caps per match esatto/parziale/non trovato
- **`lex/guards/user_facing_output_guard.py`**: blocca/riscrive testo tecnico interno nelle risposte utente

---

## 3. Criteri di accettazione

### CASO 1: "mi puoi trovare questa Sentenza n. 7919 del 31/03/2026"

| Criterio | Prima | Dopo |
|----------|-------|------|
| Workflow | giurisprudenza | giurisprudenza_specifica |
| Ricerca web attivata | No | Sì (sempre) |
| Frammento locale sufficiente | Sì | No |
| Confidence senza exact_match | Alta | ≤ 0.45 |
| "Risposta deterministica" in output | Sì | No |
| "Ciao, sono Lex." | Sì | No |

### CASO 2: "dati del cliente marco moscato"

| Criterio | Prima | Dopo |
|----------|-------|------|
| Workflow | studio_data_lookup (senza handler) | studio_data_lookup (con handler) |
| Risposta | Cabina operativa / "Risposta deterministica" | Dati cliente: CF, email, PEC, fascicoli |
| Web usato | Sì (fallback) | No (web_forbidden=True) |
| Fonti sentenze in output | Sì | No |
| Fonti ufficiali in output | Sì | No |

---

## 4. Test di copertura

Nuovo file: `tests/test_lex_sentenze_clienti_fix.py` (17 test)

| Test | Copre |
|------|-------|
| TC-01/02 | `should_run_public_research` per `giurisprudenza_specifica` |
| TC-03 | `_STRICT_LEGAL_WORKFLOWS` contiene `giurisprudenza_specifica` |
| TC-04 | Contratto `studio_data_lookup` in `contracts.py` |
| TC-05 | `user_facing_output_guard` rileva e pulisce testo tecnico |
| TC-06/07 | `detect_case_law_fragment`: frammento incompleto, completo, non-sentenza |
| TC-08/09/10/11 | `check_exact_case_law`: not_found, possible_match, exact_match senza/con testo |
| TC-12 | `giurisprudenza_specifica` è in `strict_workflow` |
| TC-13/14 | Router: sentenza esatta → `giurisprudenza_specifica`; cliente → `studio_data_lookup` |

---

## 5. Regole invarianti (non modificabili)

1. `giurisprudenza_specifica` deve sempre attivare ricerca pubblica quando `allow_external=True`
2. Un frammento locale senza URL ufficiale non può mai avere confidence > 0.45
3. `studio_data_lookup` usa solo dati interni — mai web, mai LDR
4. Il testo "Risposta deterministica per workflow" non deve mai raggiungere l'utente
5. "Ciao, sono Lex." è vietato su query operative (sentenze, clienti, fascicoli, ecc.)
