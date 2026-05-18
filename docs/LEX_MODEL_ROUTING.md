# Lex — Model e Provider Routing Professionale

> Aggiornamento 2026-05-17: MTP/speculative decoding, LLM Wiki, GLM-OCR e Gemini Embedding 2 sono governati da `lex/advanced_runtime.py`, osservabili in `/api/metriche/runtime` e verificabili con `python -m pct.cli ai-avanzata --json`. Le capacita' restano opt-in: MTP richiede serving `vllm` o `sglang`, LLM Wiki resta un livello compilato sopra il RAG, GLM-OCR va preferito self-hosted e Gemini Embedding 2 richiede autorizzazione provider esterni piu' reindicizzazione completa del corpus.

**Modulo:** `lex/providers/registry.py`
**Versione:** 1.0.0
**Data:** 2026-05-08

---

## 1. Scopo

Il sistema di routing provider assegna a ogni richiesta Lex il provider e il modello ottimale per il tipo di elaborazione richiesta. Il routing è governato da cinque profili professionali distinti, ognuno ottimizzato per una categoria di workflow.

Prima dell'upgrade, la selezione del provider avveniva tramite il metodo `pick()` con logica implicita. Il Professional Upgrade introduce:
- Cinque profili espliciti con semantica chiara
- Il metodo `pick_with_profile()` che ritorna provider, nome profilo e motivazione
- Il metodo `get_routing_metadata()` per il payload debug
- Una funzione sicura `_get_ollama_url_safe()` che non espone credenziali

## Aggiornamento 2.245.33 - Policy di routing esplicita

La Fase 4 rende il routing ispezionabile come policy, non solo come scelta di
provider. `ProviderRegistry` espone ora:

- schema `iusentra.lex_model_routing.v1`;
- profilo selezionato;
- provider effettivo;
- motivazione leggibile;
- `llm_used` sì/no;
- `deterministic` sì/no;
- costo relativo (`none`, `low`, `medium`, `high`);
- target di latenza;
- regola di contesto;
- controllo qualità richiesto.

Questo permette di consumare meno crediti: i workflow come `cabina`,
`next_action`, `economico`, `compliance`, `deposito_telematico` e
`studio_data_lookup` restano deterministici e non chiamano modelli. I workflow
su fonti e giurisprudenza usano il profilo adatto solo quando servono sintesi o
ragionamento, partendo da evidenze già selezionate e compattate.

I provider esterni non sono fallback impliciti: `force_provider=openai` viene
rispettato solo se `LEX_EXTERNAL_ALLOWED=1`. In caso contrario il routing resta
interno e la motivazione segnala che il provider esterno non è autorizzato.
L'URL Ollama esposto nei metadati resta privo di credenziali.

---

## 2. Cinque profili workflow

### 2.1 `classifier`

**Scopo:** classificazione rapida dell'intent, routing leggero a bassa latenza.

**Caratteristiche:**
- Il provider scelto deve rispondere in meno di 2 secondi.
- Non richiede retrieval pesante né ragionamento normativo.
- Usato per classificare la query in ingresso prima di passarla al workflow corretto.

**Provider tipico:** `ollama` con modello leggero (es. `llama3.2:3b` o `phi3:mini`).

---

### 2.2 `retrieval_summarizer`

**Scopo:** sintesi di fonti multiple, output strutturato per citazioni.

**Caratteristiche:**
- Riceve un context window ampio con molte evidenze da diverse fonti.
- Il suo compito è sintetizzare e attribuire correttamente le fonti.
- Non si inventa informazioni: deve riportare fedelmente ciò che le fonti dicono.
- Produce output strutturato (citazioni numerate, sezioni tematiche).

**Provider tipico:** `ollama` con modello medio-grande (es. `llama3.1:8b`).

---

### 2.3 `legal_reasoner`

**Scopo:** ragionamento normativo su fonti ufficiali, materia civile/penale/amministrativa.

**Caratteristiche:**
- Richiede un provider con buone capacità di ragionamento giuridico.
- Riceve evidenze da fonti tier_1 (normattiva, cassazione, GU).
- Deve seguire il ragionamento norma → caso → conclusione.
- È il profilo più esigente in termini di qualità del modello.

**Provider tipico:** `ollama` con modello specializzato o `openai` se `LEX_EXTERNAL_ALLOWED=1`.

---

### 2.4 `drafter`

**Scopo:** generazione di bozze di atti, contratti, memorie, ricorsi.

**Caratteristiche:**
- Richiede generazione di testo lungo e strutturato (1.000–5.000 parole).
- Il provider deve gestire output strutturati con sezioni (intestazione, fatto, diritto, PQM).
- La qualità stilistica e la coerenza interna sono prioritarie rispetto alla velocità.
- Il draft prodotto è sempre marcato come `needs_review` finché non viene revisionato dall'avvocato.

**Provider tipico:** `ollama` con modello di generazione lunga (es. `llama3.1:8b`, `mistral:7b`).

---

### 2.5 `deterministic`

**Scopo:** risposta basata su regole, senza generazione neurale.

**Caratteristiche:**
- Nessuna chiamata a un modello linguistico.
- La risposta viene costruita a partire dal contesto strutturato dello studio (JSON fascicolo, agenda, scadenziario, preventivi).
- Confidence sempre alta (0.88–0.95) perché basata su dati certi.
- Latenza minima (< 50 ms).

**Provider:** `DeterministicProvider` (sempre, indipendentemente dalla configurazione).

---

## 3. Mapping workflow → profilo

| Workflow | Profilo | Note |
|---|---|---|
| `question_answering` | `classifier` | Classificazione rapida della domanda |
| `research` | `retrieval_summarizer` | Sintesi da retrieval pesante |
| `fonti` | `retrieval_summarizer` | Ricerca e comparazione fonti |
| `normativa` | `legal_reasoner` | Ragionamento su norma italiana/UE |
| `giurisprudenza` | `legal_reasoner` | Analisi sentenze e massime |
| `prassi` | `legal_reasoner` | Prassi e orientamenti applicativi |
| `atto` | `drafter` | Generazione bozza atto processuale |
| `documento` | `drafter` | Generazione documento legale |
| `economico` | `deterministic` | Calcolo parcelle, preventivi |
| `next_action` | `deterministic` | Suggerimento azione successiva |
| `cabina` | `deterministic` | Dashboard operativa fascicolo |
| `telematico_status` | `deterministic` | Stato deposito telematico |
| `compliance` | `deterministic` | Verifica conformità normativa |
| `fascicolo` (con contesto) | `deterministic` | Se il fascicolo ha contesto sufficiente |
| `fascicolo` (senza contesto) | `legal_reasoner` | Default per fascicoli senza contesto |
| `telematico` | `legal_reasoner` | Deposito telematico PCT/PDP/PAT |
| `udienza` | `legal_reasoner` | Preparazione udienza |
| `intelligence` | `legal_reasoner` | Aggiornamenti normativi automatici |
| Workflow sconosciuto | `legal_reasoner` | Default sicuro |

---

## 4. `pick_with_profile()` e `get_routing_metadata()`

### 4.1 `pick_with_profile(request, context, workflow, evidence)`

Seleziona il provider e restituisce una tupla `(provider, profile_name, reason)`.

```python
provider, profile, reason = registry.pick_with_profile(
    request=lex_request,
    context=studio_context,
    workflow="normativa",
    evidence=evidence_dict,
)

print(provider)   # <OllamaProvider>
print(profile)    # "legal_reasoner"
print(reason)     # "workflow 'normativa' richiede ragionamento normativo (profilo: legal_reasoner)"
```

**Ordine di priorità nella selezione:**
1. `metadata.force_provider` — override esplicito (rispettato solo se il provider forzato è disponibile e autorizzato)
2. `LEX_PROVIDER_FORCE_MOCK=1` — sempre mock (per ambienti di test)
3. Workflow deterministici — sempre `DeterministicProvider`
4. `AnswerContract.provider_hint` — hint dal contratto del workflow
5. `fascicolo` con contesto — `DeterministicProvider`
6. Workflow strict legal — `OllamaProvider`
7. Default — `OllamaProvider`

### 4.2 `get_routing_metadata(request, context, workflow, evidence)`

Restituisce un dizionario di metadati per il payload debug. Non espone credenziali.

```python
meta = registry.get_routing_metadata(
    request=lex_request,
    context=studio_context,
    workflow="normativa",
    evidence=evidence_dict,
)

# {
#   "provider": "ollama",
#   "profile": "legal_reasoner",
#   "reason": "workflow 'normativa' richiede ragionamento normativo (profilo: legal_reasoner)",
#   "workflow": "normativa",
#   "external_allowed": False,
#   "ollama_url": "http://localhost:11434"
# }
```

---

## 5. Provider disponibili

| Provider | Classe | Uso |
|---|---|---|
| `ollama` | `OllamaProvider` | Provider principale per tutti i workflow generativi. Usa il runtime Ollama locale. |
| `openai` | `OpenAIProvider` | Provider esterno facoltativo. Attivo solo se `LEX_EXTERNAL_ALLOWED=1`. |
| `deterministic` | `DeterministicProvider` | Risposta rule-based senza generazione. Usato per workflow operativi. |
| `mock` | `MockProvider` | Provider di test. Attivo solo in ambienti pytest o con `LEX_PROVIDER_FORCE_MOCK=1`. |

---

## 6. Come forzare un provider

Il provider può essere forzato tramite il campo `force_provider` nei metadata della richiesta. Questo meccanismo è utile per test, debug e casi speciali.

**Tramite metadata della richiesta:**

```python
lex_request.metadata["force_provider"] = "ollama"
# oppure
lex_request.metadata["force_provider"] = "deterministic"
```

**Regole di sicurezza per il force:**
- `force_provider="mock"` → accettato solo se `LEX_PROVIDER_FORCE_MOCK=1` (env) o se siamo in un test pytest.
- `force_provider="ollama"` → sempre accettato.
- `force_provider="deterministic"` → sempre accettato.
- `force_provider="openai"` → accettato solo se `LEX_EXTERNAL_ALLOWED=1`.
- Qualsiasi altro valore → ignorato, si usa la logica di selezione normale.

**Tramite variabile d'ambiente (globale):**

```bash
# Forza mock per tutti i workflow (solo test)
LEX_PROVIDER_FORCE_MOCK=1
```

---

## 7. Variabili d'ambiente

| Variabile | Default | Descrizione |
|---|---|---|
| `LEX_DEFAULT_PROVIDER` | `ollama` | Provider predefinito per workflow non deterministici. Attualmente non usato direttamente dal registry (il default è hardcoded su `ollama`), ma introdotto per futura configurabilità. |
| `LEX_EXTERNAL_ALLOWED` | non impostata (false) | Abilita provider esterni (OpenAI) e la trasmissione di query a LDR. Impostare a `1` solo dopo verifica delle policy privacy. |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | URL del runtime Ollama locale. Usato da `OllamaProvider`. Viene esposto nel debug solo come `http://host:porta` senza credenziali. |
| `LEX_PROVIDER_FORCE_MOCK` | non impostata | Forza il provider mock per tutti i workflow. Usare solo in ambienti di test. |

---

## 8. Fallback logic — cosa succede se Ollama non risponde

`OllamaProvider` gestisce il timeout e gli errori di connessione con le seguenti strategie:

1. **Timeout di connessione** — se Ollama non risponde entro il timeout configurato, `OllamaProvider` solleva un'eccezione che viene catturata dall'orchestratore.

2. **Fallback al guardrail** — quando `OllamaProvider` fallisce e il contratto del workflow ha `allow_abstention=True`, l'orchestratore attiva il blocco soft: la risposta viene sostituita da un messaggio guardrail (`"Non posso completare una risposta legale affidabile..."`) con `provider="guardrail"` e `answer_mode="needs_review"`.

3. **Nessun fallback automatico a OpenAI** — anche se `LEX_EXTERNAL_ALLOWED=1`, il fallback automatico da Ollama a OpenAI non è implementato. Il motivo è che il fallback implicito potrebbe violare le policy privacy per query con sensitivity `sensitive` senza una verifica esplicita.

4. **Log di errore** — ogni fallimento di Ollama viene registrato nel log applicativo con livello `WARNING` e incluso nel campo `skipped_generation_reason` del payload debug.

**Verifica della disponibilità Ollama:**

```bash
# Health check diretto
curl -s http://localhost:11434/api/tags | python3 -m json.tool

# Tramite diagnostica Lex (pannello admin)
# GET /admin/lex/diagnostics
```

---

## 9. Come aggiungere un nuovo provider

1. **Creare la classe del provider** in `lex/providers/` estendendo `BaseProvider`:

```python
# lex/providers/nuovo_provider.py
from .base import BaseProvider

class NuovoProvider(BaseProvider):
    name = "nuovo"

    def generate(self, prompt: str, context: dict, workflow: str, **kwargs) -> str:
        # Implementazione della generazione
        ...
```

2. **Registrare il provider nel `ProviderRegistry.__init__()`:**

```python
# lex/providers/registry.py
from .nuovo_provider import NuovoProvider

class ProviderRegistry:
    def __init__(self) -> None:
        self.providers: dict[str, Any] = {
            "mock": MockProvider(),
            "ollama": OllamaProvider(),
            "openai": OpenAIProvider(),
            "deterministic": DeterministicProvider(),
            "nuovo": NuovoProvider(),  # aggiunto
        }
```

3. **Aggiornare `pick()` se necessario** — aggiungere la logica di selezione nel metodo `pick()` se il nuovo provider deve essere scelto automaticamente per certi workflow.

4. **Aggiungere al controllo `force_provider`** — modificare il blocco `if forced in {...}` in `pick()` per includere il nuovo provider come valore valido.

5. **Scrivere i test** — il nuovo provider deve avere test unitari in `lex/tests/` che verificano il comportamento base (generazione, gestione errori, timeout).

---

## 10. Sicurezza — URL Ollama esposta nel debug

La funzione `_get_ollama_url_safe()` garantisce che nel payload debug venga esposto solo il componente `schema://host:porta` dell'URL Ollama, senza path, query string o credenziali.

**Esempio:**
```python
# OLLAMA_BASE_URL = "http://admin:segreto@ollama.lan:11434"
# _get_ollama_url_safe() ritorna:
"http://ollama.lan:11434"
# Le credenziali "admin:segreto" non compaiono mai nel debug
```

Questa protezione è implementata tramite `urllib.parse.urlparse()` e ricostruzione dell'URL senza il componente `netloc` completo.

**Nota per le installazioni con Ollama su host remoto:** se Ollama è esposto su rete interna (es. `http://192.168.1.10:11434`), l'IP apparirà nel debug. Questo è accettabile per gli amministratori, ma verificare che il pannello debug non sia accessibile a utenti non autorizzati.

---

## 11. FAQ

**Domanda:** Perché `fascicolo` senza contesto usa `legal_reasoner` invece di `deterministic`?
**Risposta:** Il `DeterministicProvider` produce risposte template-based adatte solo quando il fascicolo ha dati strutturati sufficienti (agenda, scadenziario, atti, controparte). Senza contesto, una risposta deterministica sarebbe generica e non utile. Il profilo `legal_reasoner` con `OllamaProvider` permette di rispondere sulla base del ragionamento giuridico anche in assenza di contesto specifico.

**Domanda:** Posso usare due provider in parallelo per confrontare le risposte?
**Risposta:** No, il design attuale del `ProviderRegistry` seleziona un solo provider per richiesta. Il confronto parallelo richiederebbe modifiche all'`orchestrator_workflow.py` e una logica di merge non ancora implementata.

**Domanda:** Il profilo viene comunicato all'avvocato?
**Risposta:** No, il profilo è un campo tecnico visibile solo nel payload debug agli amministratori. L'avvocato vede solo `answer_mode` e `confidence`. Il profilo è utile per la diagnostica e il tuning del sistema.

**Domanda:** Cosa succede se `AnswerContract.provider_hint` indica un provider non disponibile?
**Risposta:** Il registry controlla che `contract.provider_hint` sia una chiave presente nel dizionario `self.providers`. Se il provider non è disponibile, il controllo fallisce silenziosamente e la selezione procede con la logica successiva (tipicamente `OllamaProvider`).

---

*Documento interno — IUSENTRA Legal Platform*
