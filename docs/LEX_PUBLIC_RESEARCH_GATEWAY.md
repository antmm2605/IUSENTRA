# Lex — Public Legal Research Gateway

**Modulo:** `lex/research/public_legal_research_gateway.py`
**Versione:** 1.0.0
**Data:** 2026-05-08

---

## 1. Scopo

Il Public Legal Research Gateway coordina tutti i canali di ricerca pubblica disponibili in un unico layer normalizzato. Il suo ruolo è raccogliere evidenze da fonti istituzionali (normattiva.it, gazzettaufficiale.it, giustizia.it e simili), dal web ufficiale allowlisted e da Local Deep Research, normalizzare le evidenze in strutture uniformi, applicare deduplicazione e ranking, e calcolare i gap di copertura da comunicare all'avvocato.

Il gateway non inventa risultati. Se le fonti sono vuote, lo dichiara esplicitamente tramite `coverage_gaps` e `missing_evidence`. Non accede mai a dati privati dello studio: riceve esclusivamente la query pubblica anonimizzata prodotta dal `PrivacySafeQueryRewriter`.

**Principio fondamentale:** nessun dato personale, nome proprio, numero di RG o riferimento a fascicoli specifici viene trasmesso fuori dal perimetro del tenant.

Quando una domanda di ricerca legale contiene contesto interno ma richiede fonti normative, giurisprudenziali o ufficiali non coperte da quel contesto, il bounded workflow deve abilitare automaticamente la ricerca pubblica governata. La presenza di una scheda, fascicolo o archivio interno parziale non e' sufficiente per impedire il fallback web ufficiale.

---

## 2. Flusso in 5 step

```
Query pubblica anonimizzata (solo materia giuridica)
              |
              v
    STEP 1: Fonti ufficiali interne
    search_official_sources()
    [SQLite / JSONL indicizzati: normattiva, GU, giurisprudenza]
              |
              v
    STEP 2: Ricerca web su domini ufficiali allowlist
    search_recognized_official_web()
    [DuckDuckGo site:<dominio> solo su domini istituzionali]
              |
              v
    STEP 3: Local Deep Research (LDR)
    LocalDeepResearchClient.research_and_wait()
    [solo se rewritten_query.can_use_ldr == True]
              |
              v
    STEP 4: Deduplicazione e ranking
    _deduplicate() + _rank_sources()
    [dedup per hash excerpt, ranking per trust_score * freshness_score]
              |
              v
    STEP 5: Coverage gaps
    _compute_coverage_gaps()
    [confronto materie della query vs. fonti trovate]
              |
              v
    PublicLegalResearchResult
    [sources, official_sources, ldr_sources, coverage_gaps, confidence_seed, ...]
```

---

## 3. `NormalizedSource` — campi e significato

Struttura dati che rappresenta una singola fonte dopo la normalizzazione. Ogni fonte — indipendentemente dal canale di provenienza — viene convertita in questa struttura prima del ranking.

| Campo | Tipo | Significato |
|---|---|---|
| `id` | `str` | Hash SHA-256 (12 caratteri) del testo della fonte. Usato per la deduplicazione. |
| `title` | `str` | Titolo della fonte (nome della norma, numero sentenza, ecc.). |
| `source_name` | `str` | Nome dell'autorità emittente (es. `"Corte di Cassazione"`, `"Normattiva"`). |
| `source_type` | `str` | Categoria: `normativa`, `giurisprudenza`, `web_ufficiale`, `ldr`, `interno`. |
| `official` | `bool` | True se la fonte proviene da un'autorità istituzionale verificata. |
| `url` | `str` | URL della fonte originale. Può essere vuoto per fonti interne. |
| `date` | `str` | Data di pubblicazione (formato ISO, es. `"2025-03-15"`). |
| `excerpt` | `str` | Estratto testuale della fonte (max 500 caratteri). |
| `trust_score` | `float` | Punteggio di affidabilità: 0.0–1.0. Fonti tier_1 ottengono 0.92, tier_2 0.68, tier_3 0.35. |
| `freshness_score` | `float` | Punteggio di freschezza: 0.0–1.0. Decresce di 0.08 per anno di età. |
| `source_access_status` | `str` | `open` (accesso libero), `requires_auth` (richiede credenziali), `restricted` (accesso limitato). |
| `source_access_label` | `str` | Etichetta leggibile del tipo di accesso (es. `"Accesso libero"`, `"Richiede abbonamento"`). |
| `source_requires_credentials` | `bool` | True se la fonte richiede autenticazione per l'accesso completo. |
| `source_restricted` | `bool` | True se la fonte è accessibile solo parzialmente o su abbonamento. |
| `source_supports_web_search` | `bool` | True se il dominio della fonte supporta la ricerca web pubblica. |

Il metodo `to_evidence_dict()` converte la struttura nel formato `EvidenceItem` compatibile con l'`EvidencePack` del pipeline Lex.

Le risposte professionali Lex usano `excerpt`/`content` per mostrare all'avvocato il contesto fonte nella sezione "Fonti consultate". Nei workflow strict una fonte priva di estratto non deve rendere la risposta chiusa: il builder aggiunge un gap di evidenza e mantiene la risposta in revisione.

---

## 4. `PublicLegalResearchResult` — campi principali

| Campo | Tipo | Significato |
|---|---|---|
| `query_used` | `str` | Query pubblica anonimizzata effettivamente usata per la ricerca. |
| `sources` | `list[NormalizedSource]` | Tutte le fonti trovate, dopo dedup e ranking. |
| `official_sources` | `list[NormalizedSource]` | Sottoinsieme con sole fonti istituzionali verificate (`official=True`). |
| `ldr_sources` | `list[NormalizedSource]` | Fonti trovate tramite Local Deep Research. |
| `compared_sources` | `list[dict]` | Struttura per il confronto comparativo tra fonti diverse. |
| `coverage_gaps` | `list[str]` | Materie non coperte dalle fonti trovate (es. `"Nessuna sentenza recente trovata per la materia"`). |
| `missing_evidence` | `list[str]` | Evidenze mancanti specifiche (es. `"Massimario Cassazione non disponibile"`). |
| `warnings` | `list[str]` | Avvisi non bloccanti (es. `"Web non disponibile: DuckDuckGo non raggiungibile"`). |
| `next_actions` | `list[str]` | Azioni suggerite all'avvocato per colmare i gap. |
| `fallback_triggered` | `bool` | True se almeno un canale ha richiesto un fallback. |
| `confidence_seed` | `float` | Stima iniziale di confidenza basata sulle fonti trovate (0.0–1.0). |
| `research_log` | `list[str]` | Log cronologico delle operazioni di ricerca (per debug). |
| `ldr_used` | `bool` | True se Local Deep Research ha effettivamente contribuito risultati. |
| `ldr_blocked_reason` | `str` | Motivazione del blocco LDR (vuota se LDR non è stato bloccato). |
| `web_used` | `bool` | True se la ricerca web su domini ufficiali ha contribuito risultati. |
| `web_blocked_reason` | `str` | Motivazione del mancato uso del web (vuota se il web è stato usato o non era necessario). |

Il metodo `to_evidence_pack_dict()` converte il risultato in formato compatibile con l'`EvidencePack` del `RetrievalOrchestrator`.

---

## 5. Come attivare e disattivare LDR

Local Deep Research è un servizio opzionale che esegue ricerche approfondite su fonti non indicizzate internamente. Il gateway lo invoca automaticamente quando tutte le seguenti condizioni sono soddisfatte:

1. `rewritten_query.can_use_ldr == True` (la query pubblica ha superato il controllo privacy)
2. Il modulo `lex.integrations.local_deep_research_client` è importabile
3. La variabile `LEX_EXTERNAL_ALLOWED` è impostata a `1` o `true`

**Disabilitare LDR:**

```bash
# Non impostare LEX_EXTERNAL_ALLOWED oppure impostarla a 0
unset LEX_EXTERNAL_ALLOWED
# oppure
LEX_EXTERNAL_ALLOWED=0
```

**Verificare lo stato LDR nel payload debug:**

```json
{
  "ldr_used": false,
  "ldr_blocked_reason": "LDR non configurato o non disponibile"
}
```

**Forza disabilitazione LDR per query sensibile:**
Se la query pubblica ha sensitivity `sensitive` o `highly_sensitive`, `can_use_ldr` viene impostato a `false` automaticamente dal `PrivacySafeQueryRewriter`, indipendentemente dalla configurazione di `LEX_EXTERNAL_ALLOWED`.

---

## 6. Come aggiungere nuove fonti ufficiali

Il gateway usa un'allowlist di domini istituzionali per la ricerca web. Per aggiungere domini extra senza modificare il codice sorgente, usare la variabile d'ambiente:

```bash
PCT_LEX_OFFICIAL_EXTRA_DOMAINS="miodominio.giustizia.it,altrafonteufficialie.it"
```

I domini vengono aggiunti all'allowlist esistente (che include normattiva.it, gazzettaufficiale.it, giustizia.it, cortedicassazione.it, governo.it, senato.it, camera.it, ecc.).

**Aggiunta programmatica tramite codice** (per integrazioni permanenti):
Modificare la lista `_OFFICIAL_DOMAINS` in `lex/retrieval/official_web.py` e aggiungere la voce alla lista `_OFFICIAL_SOURCES_CONFIG` in `lex/research/official_sources.py`.

**Requisiti per un dominio da aggiungere:**
- Deve essere un dominio istituzionale italiano (`.gov.it`, `.giustizia.it`, `.senato.it`, ecc.) oppure un ente europeo riconosciuto (eur-lex.europa.eu, echr.coe.int, ecc.)
- Non deve richiedere autenticazione per le pagine indicizzabili pubblicamente
- Non deve essere un dominio commerciale o di commento dottrinale

---

## 7. Esempi Python di utilizzo diretto

**Utilizzo base:**

```python
from lex.research.privacy_safe_query_rewriter import rewrite_query_for_legal_research
from lex.research.public_legal_research_gateway import run_public_legal_research

# Passo 1: riscrittura query
rewritten = rewrite_query_for_legal_research(
    "Nel fascicolo Rossi RG 1234/2025 posso eccepire la prescrizione "
    "nella causa di responsabilità contrattuale?",
    fascicolo_id="fascicolo-abc-123",
)

print(rewritten.public_research_query)
# "prescrizione responsabilità contrattuale eccezione termine decorrenza"

print(rewritten.can_use_ldr)
# True

# Passo 2: ricerca pubblica
result = run_public_legal_research(
    rewritten_query=rewritten,
    source_mode="balanced",
    max_results=6,
)

print(f"Fonti trovate: {len(result.sources)}")
print(f"Fonti ufficiali: {len(result.official_sources)}")
print(f"LDR usato: {result.ldr_used}")
print(f"Web usato: {result.web_used}")
print(f"Gap di copertura: {result.coverage_gaps}")
```

**Utilizzo tramite integratore (dal RetrievalOrchestrator):**

```python
from lex.retrieval.legal_research_integrator import (
    should_run_public_research,
    run_public_research_for_request,
)

# Decisione se eseguire la ricerca pubblica
if should_run_public_research(
    workflow="normativa",
    evidence_sufficient=False,
    allow_external=request.allow_external_research,
):
    extra = run_public_research_for_request(
        request=lex_request,
        context=studio_context,
        workflow="normativa",
        source_mode="balanced",
    )
    # extra contiene: public_sources, ldr_used, coverage_gaps, ecc.
    evidence_pack.update(extra)
```

**Conversione in EvidencePack:**

```python
evidence_pack_dict = result.to_evidence_pack_dict()
# Struttura compatibile con EvidencePack.from_dict()
print(evidence_pack_dict["evidence_pack"]["sufficient"])
print(evidence_pack_dict["coverage_gaps"])
```

---

## 8. Sicurezza — perimetro dati

Il gateway opera esclusivamente sulla query pubblica prodotta dal `PrivacySafeQueryRewriter`. Questo garantisce che:

- **Nessun dato personale** (nomi propri, codici fiscali, IBAN, numeri di telefono, email) viene trasmesso a servizi esterni o al web.
- **Nessun riferimento a fascicoli specifici** (numeri RG, identificatori interni) esce dal perimetro del tenant.
- **La query per LDR** è la `local_deep_research_query` del rewriter — garantita pulita da un doppio controllo privacy (il rewriter verifica che anche la query pubblica risulti `public` o `internal` dopo la classificazione).
- **Il gateway non riceve mai** `private_context_query` né l'elenco dei `removed_sensitive_tokens`.

In caso di sensitivity `highly_sensitive`, il gateway non viene invocato affatto: sia LDR che il web vengono bloccati dal rewriter prima ancora che il gateway venga chiamato.

---

## 9. Troubleshooting

**Tutte le fonti sono vuote — `sources` è una lista vuota**

1. Verificare che il DB normativa interno (`normattiva.sqlite`) sia presente e non corrotto: `ls -la data/lex/normattiva.sqlite`
2. Verificare la connettività verso DuckDuckGo: `curl -s "https://html.duckduckgo.com/html/?q=prescrizione+codice+civile" | head -20`
3. Controllare il campo `warnings` nel risultato: può indicare errori di connessione o timeout.
4. Verificare che `LEX_EXTERNAL_ALLOWED` sia impostata se LDR e il web sono necessari.
5. Se `rewritten_query.public_research_query` è vuota, la query originale non conteneva termini giuridici riconoscibili. Controllare i `warnings` del rewriter.

**LDR non viene mai usato**

1. Verificare che `LDR_BASE_URL` o la variabile di configurazione LDR sia impostata.
2. Verificare che `LEX_EXTERNAL_ALLOWED=1` sia impostata.
3. Verificare che la query non abbia sensitivity `sensitive` o `highly_sensitive` (in quel caso LDR è bloccato per policy privacy).
4. Controllare `ldr_blocked_reason` nel payload debug.

**Il web restituisce risultati irrilevanti**

1. La `public_research_query` potrebbe essere troppo generica (poche keyword giuridiche riconosciute). Controllare il campo `public_research_query` nel payload debug.
2. I domini nell'allowlist potrebbero non avere contenuti indicizzati per la materia ricercata. Questo è normale per materie di nicchia: il gap verrà registrato in `coverage_gaps`.

**`coverage_gaps` è sempre vuoto anche senza fonti**

Il calcolo dei gap è basato sul confronto tra i token normativi presenti nella query e le fonti trovate. Se la query pubblica è troppo corta o generica, il calcolo non produce gap significativi. Verificare che `public_research_query` contenga almeno 3-4 termini giuridici.

---

*Documento interno — IUSENTRA Legal Platform*
