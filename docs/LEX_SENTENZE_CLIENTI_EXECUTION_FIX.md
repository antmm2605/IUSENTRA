# LEX - Fix esecuzione sentenze esatte e dati cliente (v2.203.0)

> **Versione:** 2.203.0 - Data: 08/05/2026

Documento di audit e delivery che descrive i bug, le cause radice, le policy applicate e le modifiche implementate.

---

## 0. Audit tecnico v2.203.0

Il rilascio v2.202.0 aveva introdotto i primi guardrail, ma i due casi reali continuavano a fallire perche' il percorso HTTP bounded e il formatter finale non rispettavano ancora i metadati di exact-match e di lookup cliente.

1. Un frammento locale di sentenza veniva considerato sufficiente perche' `merge_public_research_into_evidence()` marcava sufficiente il pacchetto in presenza di fonti ufficiali generiche, mentre il formatter usava `evidence_count` e non `exact_match_count`.
2. `evidence_sufficient` viene calcolato in `lex/retrieval/orchestrator.py` tramite `_evidence_is_sufficient()` e poi nel `LexResearchService.build_evidence_pack()`. Per `giurisprudenza_specifica` ora viene forzato a `False` salvo exact-match con testo/dispositivo/motivazione.
3. `should_run_public_research()` parte in `lex/retrieval/legal_research_integrator.py`: ora `force`, `exact_reference`, `local_case_law_incomplete` e `user_requested_public_source` prevalgono sul conteggio evidenze, quando `allow_external=True`.
4. `giurisprudenza_specifica` non forzava davvero il web in UI perche' `lex/http_bounded_bridge.py` degradava `request_profile.intent=giurisprudenza_specifica` a `workflow_hint=giurisprudenza` usando il focus `sentenze_web`.
5. Le 12 sentenze correlate venivano mostrate da `ProfessionalAnswerComposer._fonti_lines()` perche' `AnswerBuilder` passava tutte le citation come fonti considerate.
6. La confidence saliva troppo perche' veniva pesata su `retrieved_count`/fonti ufficiali generiche invece che su exact-match, testo integrale, dispositivo e motivazione.
7. "Risposta deterministica per workflow" proveniva dai fallback provider/guardrail e non veniva sempre sanificata dal guard finale.
8. "cliente marco moscato" finiva nella risposta generica perche' il router riconosceva solo frasi tipo "dati del cliente" e il bridge non impostava `studio_data_lookup` sul focus `clienti`.
9. `studio_data_lookup` esisteva gia' in `contracts.py`, ma il percorso HTTP non lo attivava per la query secca "cliente <nome>".
10. Il contratto `studio_data_lookup` ora resta specifico: internal-only, no web, no citazioni, tool `studio_data_gateway`.
11. Il contesto cliente veniva perso tra `assistente_conversation_focus -> http_bounded_bridge -> LexRouter`, dove focus e intent non venivano convertiti in workflow obbligatorio.
12. File corretti: router, request profile, bounded bridge, source router, official web source, orchestrator, exact guard, source scope, studio data gateway, deterministic provider, answer builder, debug payload e focus UI.

Differenza essenziale: un frammento locale e' solo un indizio. Una fonte pubblica ufficiale e' un risultato verificabile con dominio/URL ufficiale e riferimento coerente. Lex non deve avere un database completo di sentenze: deve riconoscere il riferimento esatto, forzare ricerca ufficiale governata e abbassare la confidence quando mancano testo integrale, motivazione o dispositivo.

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
1. `studio_data_lookup` aveva il contratto, ma non veniva selezionato dal bridge per query secche tipo "cliente marco moscato".
2. `DeterministicProvider.generate()` non produceva una scheda cliente completa e il formatter ricadeva su evidenze/focus generici.
3. `build_lex_studio_context` e il focus `clienti` potevano ancora caricare contesto generico invece del solo gateway anagrafica.

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
- **`lex/research/case_law_exact_search.py`**: `CaseLawReference`, query normalizzate e completion result per ricerca exact-match governata.
- **`lex/research/source_scope_policy.py`**: separa `studio_internal`, `public_legal_source`, `mixed_private_public`, `diagnostic`, `operational_no_web`.
- **`lex/tools/studio_data_gateway.py`**: `StudioLookupResult`, pulizia query cliente, ranking anagrafica, template dati cliente e fascicoli collegati.

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

Nuovo/aggiornato file: `tests/test_lex_sentenze_clienti_fix.py` (25 test)

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
| TC-15/16 | HTTP bounded bridge: non degrada sentenza specifica e focus clienti |
| TC-17/18 | AnswerBuilder: no elenco 12 sentenze, cap confidence, template exact/no-match |
| TC-19/20 | Studio data gateway e AnswerBuilder: lookup interno cliente, web vietato |
| TC-21 | Guard output utente: blocca termini tecnici `workflow`/`provider` |

---

## 5. Regole invarianti (non modificabili)

1. `giurisprudenza_specifica` deve sempre attivare ricerca pubblica quando `allow_external=True`
2. Un frammento locale senza URL ufficiale non può mai avere confidence > 0.45
3. `studio_data_lookup` usa solo dati interni — mai web, mai LDR
4. Il testo "Risposta deterministica per workflow" non deve mai raggiungere l'utente
5. "Ciao, sono Lex." è vietato su query operative (sentenze, clienti, fascicoli, ecc.)
