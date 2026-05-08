# Lex — Pannello Debug per Amministratori

**Modulo:** `lex/formatting/debug_payload_builder.py`
**Versione:** 1.0.0
**Data:** 2026-05-08

---

## 1. Scopo

Il pannello debug di Lex rende trasparente il processo interno che ha portato a una risposta. Per ogni richiesta ricevuta, il sistema costruisce un payload di diagnostica che descrive: quale workflow è stato usato, quale provider ha generato la risposta, quante e quali fonti sono state consultate, perché la confidence ha raggiunto un certo valore, se LDR o il web ufficiale sono stati attivati, e quali gap di copertura rimangono aperti.

Il payload debug è disponibile **esclusivamente** per ruoli autorizzati (superadmin, admin_studio, admin) e non viene mai trasmesso ad altri utenti. I dati sensibili non appaiono mai nel debug: la query privata dell'utente è sempre oscurata, i token rimossi vengono indicati solo come conteggio, le chiavi API non compaiono mai, e i path assoluti vengono ridotti al solo basename.

---

## 2. Chi vede il debug

La verifica del ruolo viene eseguita dalla funzione `should_include_debug(user_role)` nel modulo `debug_payload_builder.py`.

| Ruolo | Vede il debug? |
|---|---|
| `superadmin` | Sì |
| `admin_studio` | Sì |
| `admin` | Sì |
| `avvocato` | No |
| `collaboratore` | No |
| `segreteria` | No |
| `cliente` | No |
| Qualsiasi altro ruolo | No |

Il controllo è case-insensitive e robusto ai valori vuoti o `None`.

---

## 3. Campi del payload debug

Il payload debug viene incluso nel JSON di risposta Lex sotto la chiave `"debug"`. Di seguito tutti i campi con la loro descrizione.

### 3.1 Routing e provider

| Campo | Tipo | Descrizione |
|---|---|---|
| `workflow` | `str` | Nome del workflow Lex usato (es. `normativa`, `giurisprudenza`, `fascicolo`, `economico`). |
| `provider` | `str` | Nome del provider che ha generato la risposta (es. `ollama`, `deterministic`, `guardrail`, `openai`). |
| `model` | `str` | Nome del modello specifico usato dal provider (es. `llama3.1:8b`, `mistral:7b`). Può essere vuoto se il provider è deterministico. |

### 3.2 Risposta e confidence

| Campo | Tipo | Descrizione |
|---|---|---|
| `answer_mode` | `str` | Modalità della risposta: `grounded` (risposta supportata da evidenze), `needs_review` (evidenze insufficienti), `blocked` (bloccato da guardrail). |
| `confidence` | `float` | Valore di confidence da 0.0 a 1.0 (es. `0.8750`). |
| `confidence_reason` | `str` | Spiegazione testuale del valore di confidence. Esempio: `"alta (87%); per 3 fonti ufficiali"`. |
| `risk_level` | `str` | Livello di rischio valutato dal guardrail: `low`, `medium`, `high`, `critical`. |

### 3.3 Evidenze

| Campo | Tipo | Descrizione |
|---|---|---|
| `evidence_count` | `int` | Numero totale di evidenze raccolte dal retrieval (interne + pubbliche). |
| `official_sources_count` | `int` | Numero di fonti istituzionali verificate (`official=True`) nelle evidenze. |
| `internal_sources_count` | `int` | Numero di fonti interne del tenant (fascicoli, agenda, scadenziario) nelle evidenze. |

### 3.4 Retrieval esteso

| Campo | Tipo | Descrizione |
|---|---|---|
| `ldr_used` | `bool` | True se Local Deep Research ha contribuito risultati alla risposta. |
| `ldr_blocked_reason` | `str` | Motivazione del blocco LDR. Esempi: `"LDR non configurato"`, `"Query sensibile: sensitivity=highly_sensitive"`, `"can_use_ldr=False per policy privacy"`. Vuota se LDR non è stato bloccato. |
| `web_used` | `bool` | True se la ricerca web su domini istituzionali allowlisted ha contribuito risultati. |
| `web_blocked_reason` | `str` | Motivazione del mancato uso del web. Esempi: `"OfficialWebSource.should_include()=False"`, `"Evidenza interna sufficiente"`. Vuota se il web è stato usato o non era necessario. |

### 3.5 Query (con protezione privacy)

| Campo | Tipo | Descrizione |
|---|---|---|
| `public_research_query` | `str` | Query pubblica anonimizzata usata per web e LDR. Contiene solo materia giuridica. |
| `private_context_query` | `str` | **Sempre** `"[REDATTO PER PRIVACY]"`. La query privata non viene mai esposta nel debug. |
| `removed_sensitive_tokens` | `dict` | Oggetto con un solo campo: `{"count": N}`. Solo il numero dei token rimossi, mai i valori reali. |

### 3.6 Fonti e gap

| Campo | Tipo | Descrizione |
|---|---|---|
| `considered_sources` | `list[str]` | Nomi delle sorgenti considerate durante il retrieval. |
| `compared_sources` | `list[dict]` | Struttura per il confronto comparativo tra fonti (titolo, score, tipo). |
| `official_sources` | `list[str]` | Nomi delle fonti ufficiali che hanno contribuito all'evidenza. |
| `restricted_sources` | `list[str]` | Fonti identificate come riservate (accesso ad abbonamento). Utile per spiegare gap di copertura. |
| `partner_sources` | `list[str]` | Fonti di partner (es. banche dati giuridiche integrate). |
| `coverage_gaps` | `list[str]` | Materie non coperte dalle fonti trovate. Esempio: `"Nessuna sentenza trovata per prescrizione tributaria"`. |
| `missing_evidence` | `list[str]` | Evidenze specifiche mancanti. Esempio: `"Massimario Cassazione sezione tributaria"`. |

### 3.7 Azioni

| Campo | Tipo | Descrizione |
|---|---|---|
| `next_actions` | `list[str]` | Azioni suggerite per colmare i gap di evidenza. Esempio: `"Consultare il portale DeJure per sentenze complete"`. |

### 3.8 Fallback e cache

| Campo | Tipo | Descrizione |
|---|---|---|
| `fallback_triggered` | `bool` | True se almeno un canale ha richiesto un fallback durante il retrieval. |
| `retrieval_cache` | `dict` | Metadati della cache di retrieval (TTL, hit/miss). Nessuna chiave sensibile. |
| `skipped_generation_reason` | `str` | Motivazione per cui la generazione è stata saltata (es. blocco soft di un guardrail post). Vuota se la generazione ha prodotto un draft. |

### 3.9 Versione e timestamp

| Campo | Tipo | Descrizione |
|---|---|---|
| `debug_version` | `str` | Versione del formato payload debug (attuale: `"1.0"`). |
| `debug_timestamp` | `str` | Timestamp ISO 8601 UTC della costruzione del payload. |

---

## 4. Come integrare nel template HTML

Il campo `debug` è presente nel payload JSON di risposta solo se il ruolo dell'utente è autorizzato. Il template deve verificare esplicitamente la presenza del campo prima di renderizzarlo.

**Snippet Jinja2 per il pannello debug:**

```html
{% if lex_response.get('debug') %}
<div class="card border-warning mt-3" id="lex-debug-panel">
  <div class="card-header bg-warning bg-opacity-10 d-flex align-items-center justify-content-between py-2">
    <span class="fw-semibold text-warning-emphasis">
      <i class="bi bi-bug me-1"></i>Debug Lex
    </span>
    <span class="badge bg-secondary font-monospace">
      v{{ lex_response.debug.debug_version }}
    </span>
  </div>
  <div class="card-body p-3">
    {# Routing #}
    <div class="row g-2 mb-3">
      <div class="col-md-4">
        <div class="text-muted small">Workflow</div>
        <code>{{ lex_response.debug.workflow }}</code>
      </div>
      <div class="col-md-4">
        <div class="text-muted small">Provider</div>
        <code>{{ lex_response.debug.provider }}</code>
      </div>
      <div class="col-md-4">
        <div class="text-muted small">Modello</div>
        <code>{{ lex_response.debug.model or '—' }}</code>
      </div>
    </div>

    {# Confidence #}
    <div class="mb-3">
      <div class="text-muted small mb-1">Confidence</div>
      <div class="d-flex align-items-center gap-2">
        <div class="progress flex-grow-1" style="height:8px">
          <div class="progress-bar {% if lex_response.debug.confidence >= 0.82 %}bg-success{% elif lex_response.debug.confidence >= 0.62 %}bg-warning{% else %}bg-danger{% endif %}"
               style="width: {{ (lex_response.debug.confidence * 100)|int }}%"></div>
        </div>
        <small class="text-muted">{{ (lex_response.debug.confidence * 100)|int }}%</small>
      </div>
      <div class="text-muted small mt-1">{{ lex_response.debug.confidence_reason }}</div>
    </div>

    {# Evidenze #}
    <div class="row g-2 mb-3">
      <div class="col">
        <div class="text-muted small">Evidenze totali</div>
        <strong>{{ lex_response.debug.evidence_count }}</strong>
      </div>
      <div class="col">
        <div class="text-muted small">Fonti ufficiali</div>
        <strong>{{ lex_response.debug.official_sources_count }}</strong>
      </div>
      <div class="col">
        <div class="text-muted small">Fonti interne</div>
        <strong>{{ lex_response.debug.internal_sources_count }}</strong>
      </div>
    </div>

    {# LDR e Web #}
    <div class="row g-2 mb-3">
      <div class="col-md-6">
        <div class="text-muted small">Local Deep Research</div>
        {% if lex_response.debug.ldr_used %}
          <span class="badge bg-success">Usato</span>
        {% else %}
          <span class="badge bg-secondary">Non usato</span>
          {% if lex_response.debug.ldr_blocked_reason %}
            <div class="text-muted small mt-1">{{ lex_response.debug.ldr_blocked_reason }}</div>
          {% endif %}
        {% endif %}
      </div>
      <div class="col-md-6">
        <div class="text-muted small">Ricerca web ufficiale</div>
        {% if lex_response.debug.web_used %}
          <span class="badge bg-success">Usata</span>
        {% else %}
          <span class="badge bg-secondary">Non usata</span>
          {% if lex_response.debug.web_blocked_reason %}
            <div class="text-muted small mt-1">{{ lex_response.debug.web_blocked_reason }}</div>
          {% endif %}
        {% endif %}
      </div>
    </div>

    {# Query pubblica #}
    {% if lex_response.debug.public_research_query %}
    <div class="mb-3">
      <div class="text-muted small">Query pubblica anonimizzata</div>
      <code class="small">{{ lex_response.debug.public_research_query }}</code>
      {% if lex_response.debug.removed_sensitive_tokens.count > 0 %}
        <div class="text-muted small mt-1">
          {{ lex_response.debug.removed_sensitive_tokens.count }} token sensibili rimossi
        </div>
      {% endif %}
    </div>
    {% endif %}

    {# Coverage gaps #}
    {% if lex_response.debug.coverage_gaps %}
    <div class="mb-2">
      <div class="text-muted small mb-1">Gap di copertura</div>
      <ul class="small mb-0">
        {% for gap in lex_response.debug.coverage_gaps %}
          <li class="text-warning-emphasis">{{ gap }}</li>
        {% endfor %}
      </ul>
    </div>
    {% endif %}

    {# Timestamp #}
    <div class="text-muted" style="font-size:0.7rem">
      Debug generato: {{ lex_response.debug.debug_timestamp }}
    </div>
  </div>
</div>
{% endif %}
```

**Condizione sul ruolo nella route Flask:**

```python
from lex.formatting.debug_payload_builder import should_include_debug, build_lex_debug_payload

# In build_bounded_http_payload() o nella route Lex:
user_role = current_user.ruolo  # oppure da sessione
if should_include_debug(user_role):
    payload["debug"] = build_lex_debug_payload(
        request=lex_request,
        context=studio_context,
        workflow=workflow_name,
        evidence=evidence_dict,
        draft=draft_response,
        verdict=guard_verdict,
        response=lex_response,
        public_research_query=rewritten.public_research_query,
        ldr_used=result.ldr_used,
        ldr_blocked_reason=result.ldr_blocked_reason,
        web_used=result.web_used,
        web_blocked_reason=result.web_blocked_reason,
    )
```

---

## 5. Esempio payload debug JSON completo

```json
{
  "debug": {
    "workflow": "normativa",
    "provider": "ollama",
    "model": "llama3.1:8b",
    "answer_mode": "grounded",
    "confidence": 0.8750,
    "confidence_reason": "alta (87%); per 3 fonti ufficiali",
    "risk_level": "low",
    "evidence_count": 7,
    "official_sources_count": 3,
    "internal_sources_count": 4,
    "ldr_used": false,
    "ldr_blocked_reason": "LDR non configurato o non disponibile",
    "web_used": true,
    "web_blocked_reason": "",
    "public_research_query": "prescrizione responsabilità contrattuale termine decorrenza codice civile",
    "private_context_query": "[REDATTO PER PRIVACY]",
    "removed_sensitive_tokens": {
      "count": 2
    },
    "considered_sources": [
      "NormativaSource",
      "GiurisprudenzaSource",
      "OfficialWebSource"
    ],
    "compared_sources": [
      {
        "title": "Art. 2946 Codice Civile — Prescrizione ordinaria",
        "score": 0.92,
        "type": "normativa",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1942-03-16;262~art2946"
      },
      {
        "title": "Cass. civ. n. 12345/2024 — Decorrenza prescrizione responsabilità contrattuale",
        "score": 0.78,
        "type": "giurisprudenza",
        "url": "https://www.cortedicassazione.it/cassazione-resources/resources/cms/documents/12345_2024.pdf"
      }
    ],
    "official_sources": [
      "Normattiva",
      "Corte di Cassazione",
      "Gazzetta Ufficiale"
    ],
    "restricted_sources": [
      "DeJure (abbonamento)",
      "Il Quotidiano Giuridico (abbonamento)"
    ],
    "partner_sources": [],
    "coverage_gaps": [
      "Sentenze di merito recenti (2024-2025) non disponibili nelle fonti interne"
    ],
    "missing_evidence": [
      "Massimario Cassazione sezione civile per prescrizione contrattuale post-2023"
    ],
    "next_actions": [
      "Consultare il portale DeJure per sentenze di merito recenti",
      "Verificare aggiornamenti su normattiva.it per eventuali modifiche legislative"
    ],
    "fallback_triggered": false,
    "retrieval_cache": {
      "hit": false,
      "ttl_seconds": 3600,
      "cache_key_prefix": "lex:normativa"
    },
    "skipped_generation_reason": "",
    "debug_version": "1.0",
    "debug_timestamp": "2026-05-08T14:32:07.441293+00:00"
  }
}
```

---

## 6. Come leggere il debug

### Perché Lex ha usato LDR?

Controllare `ldr_used`. Se `true`, LDR ha contribuito risultati. Se `false`, controllare `ldr_blocked_reason`:
- `"LDR non configurato"` → LDR non è installato o la URL non è impostata
- `"Query sensibile: sensitivity=highly_sensitive"` → la query conteneva troppi dati personali
- `"can_use_ldr=False per policy privacy"` → la query pubblica non ha superato il secondo controllo privacy
- `"LEX_EXTERNAL_ALLOWED non impostata"` → LDR richiede `LEX_EXTERNAL_ALLOWED=1`

### Perché la ricerca web è stata bloccata?

Controllare `web_used` e `web_blocked_reason`:
- Se `web_used=false` e `web_blocked_reason=""`, l'evidenza interna era già sufficiente e il web non era necessario (comportamento normale).
- `"OfficialWebSource.should_include()=False"` → il workflow o l'intent non richiedono fonti ufficiali esterne.
- `"Evidenza interna sufficiente"` → il retrieval interno ha già trovato abbastanza evidenze.
- `"Query altamente sensibile"` → la sensitivity `highly_sensitive` blocca il web.

### Perché la confidence è bassa?

Leggere `confidence_reason`:
- `"bassa (22%); per evidenze insufficienti"` → il retrieval non ha trovato fonti valide. Controllare `coverage_gaps`.
- `"bassa (38%); per 1 evidenza operativa (fallback esterno attivato)"` → il retrieval interno ha fallito e il web ha trovato solo una fonte.
- Verificare `official_sources_count`: se è 0, le fonti trovate non sono istituzionali e la confidence rimane bassa.

### Perché Lex ha risposto con `needs_review`?

`answer_mode = "needs_review"` indica che la risposta non è completamente supportata da evidenze. Verificare:
- `coverage_gaps` — indica quali materie non sono coperte
- `missing_evidence` — indica fonti specifiche mancanti
- `official_sources_count` — se è 0, le evidenze non sono di livello istituzionale

---

## 7. Security checklist — cosa NON esporre mai

Il modulo `debug_payload_builder.py` garantisce le seguenti protezioni. Verificare che non vengano aggirate in eventuali personalizzazioni del template:

- **Chiavi API e token** — le chiavi `api_key`, `token`, `secret`, `password`, `credential`, `auth`, `bearer`, `access_token`, `refresh_token` vengono rimosse dalla cache di retrieval prima di includerla nel payload. Non aggiungere mai questi campi nel template.

- **Query privata dell'utente** — il campo `private_context_query` è sempre `"[REDATTO PER PRIVACY]"`. Non tentare di ottenere la query privata da altri campi del payload.

- **Token sensibili rimossi** — `removed_sensitive_tokens` contiene solo `{"count": N}`. I valori reali (nomi propri, CF, IBAN) non vengono mai esposti.

- **Path assoluti** — i path assoluti nel payload (es. path a file di sistema) vengono ridotti al solo basename dalla funzione `_sanitize_path()`. Non esporre path assoluti nei log client-side.

- **URL Ollama con credenziali** — l'URL Ollama viene esposto come `http://host:porta` senza credenziali (via `_get_ollama_url_safe()`). Se Ollama usa autenticazione HTTP basic, le credenziali non compaiono mai nel debug.

- **Ruolo verificato server-side** — la verifica del ruolo per il debug deve avvenire esclusivamente server-side, prima di costruire il payload. Non usare flag client-side per nascondere il pannello debug.

---

## 8. FAQ

**Domanda:** Il payload debug aumenta significativamente la dimensione della risposta JSON?
**Risposta:** Il payload aggiunge tipicamente 1-3 KB al JSON di risposta, meno di una risposta testuale media di Lex. Per query con molte fonti comparate, può arrivare a 10 KB. Non è un problema rilevante per le performance di rete.

**Domanda:** Il debug viene loggato nel sistema di telemetria?
**Risposta:** Il payload debug come struttura completa non viene registrato dalla telemetria (troppo verboso). I campi chiave (`ldr_used`, `web_used`, `confidence`, `workflow`, `provider`) vengono registrati separatamente nei log di `LexTelemetry`.

**Domanda:** Posso abilitare il debug anche per il ruolo avvocato in ambienti di test?
**Risposta:** La funzione `should_include_debug()` controlla il ruolo rispetto alla lista `_AUTHORIZED_ROLES`. Per aggiungere un ruolo temporaneamente in test, impostare `LEX_PROVIDER_FORCE_MOCK=1` e verificare il payload mock che include sempre il campo debug nei test automatici.

**Domanda:** `debug_timestamp` usa UTC o l'ora locale?
**Risposta:** Sempre UTC, con offset `+00:00` esplicito. La conversione al fuso orario locale è responsabilità del frontend.

---

*Documento interno — IUSENTRA Legal Platform*
