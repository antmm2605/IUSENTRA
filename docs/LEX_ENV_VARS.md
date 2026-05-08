# LEX — Variabili d'Ambiente

Riferimento completo per le variabili d'ambiente del modulo Lex e dei suoi
componenti correlati. Ogni variabile ha un **default sicuro** che funziona
in assenza di configurazione esplicita.

---

## 1. Modalità e Governance

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `LEX_GOVERNED_ONLY` | `1` | Forza l'uso del bounded workflow governato. Con `1`, ogni richiesta non sociale passa dalla pipeline controllata. Impostare `0` solo in ambienti di test. |
| `LEX_RAW_CHAT_ENABLED` | `0` | Abilita tecnicamente la raw chat libera. **Non sufficiente da solo**: la richiesta deve anche contenere `allow_unbounded_generation=true`. Default sicuro: disabilitato. |
| `LEX_AI_MODE` | `local_first` | Modalità gateway provider. Valori: `local_first` (preferisce Ollama, fallback esterno se consentito), `local_only` (blocca qualsiasi provider esterno). |
| `LEX_EXTERNAL_ALLOWED` | `0` | Abilita provider esterni (OpenAI, OpenRouter, DeepSeek). Attivare solo su query anonimizzate e non sensibili. Default sicuro: disabilitato. |

---

## 2. Provider AI

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `LEX_DEFAULT_PROVIDER` | `ollama` | Provider di default. Valori: `ollama`, `openai`, `deterministic`, `mock`. |
| `LEX_DEFAULT_MODEL` | `llama3.1:8b` | Modello di default per provider LLM. |
| `LEX_PROVIDER_DEFAULT` | `ollama` | Alias legacy per `LEX_DEFAULT_PROVIDER`. |
| `LEX_OLLAMA_MODEL` | `llama3` | Modello Ollama specifico per Lex. |
| `LEX_PROVIDER_FORCE_MOCK` | `` | Se `1`, forza tutti i provider a MockProvider. Usato in CI/CD e test. |
| `LEX_MAX_CONTEXT_CHARS` | `12000` | Lunghezza massima del contesto inviato al provider. |
| `LEX_MAX_EVIDENCE_ITEMS` | `12` | Numero massimo di EvidenceItem passati al provider. |

---

## 3. Ollama (AI locale)

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434/api` | URL dell'API Ollama. Su Docker Desktop (Windows/Mac): `http://host.docker.internal:11434/api`. Su Railway/container Linux: `http://ollama:11434/api`. |
| `OLLAMA_MODEL` | `llama3.1` | Modello Ollama principale. |
| `OLLAMA_ENABLED` | `1` | Abilita/disabilita Ollama. Se `0`, Lex usa DeterministicProvider per tutti i workflow. |
| `OLLAMA_TIMEOUT_SECONDS` | `120` | Timeout HTTP per le chiamate Ollama in secondi. |
| `OLLAMA_DEFAULT_MODEL` | _(da `OLLAMA_MODEL`)_ | Modello usato dal gateway Ollama (può differire da quello di Lex). |

---

## 4. Local Deep Research (LDR)

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `LDR_BASE_URL` | `http://local-deep-research:5000` | URL del sidecar LDR. |
| `LDR_USERNAME` | `` | Username per autenticazione LDR. Obbligatorio per usare il bridge. |
| `LDR_PASSWORD` | `` | Password per autenticazione LDR. Obbligatorio per usare il bridge. |
| `LDR_TIMEOUT_SECONDS` | `30` | Timeout per le chiamate HTTP al sidecar LDR. |
| `LDR_ALLOW_SENSITIVE` | `0` | **NON abilitare in produzione.** Se `1`, consente l'invio di query sensibili a LDR. Default sicuro: disabilitato. |

**Come attivare LDR:**
1. Avvia il profilo Docker: `docker compose --profile ldr up -d`
2. Crea un utente LDR dalla UI web (`http://localhost:5000`)
3. Imposta `LDR_USERNAME` e `LDR_PASSWORD` nel file `.env`
4. Verifica con: `curl -u <user>:<password> http://localhost:5000/auth/csrf-token`

**Verifica che LDR sia usato:**
Il campo `ldr_used` nel debug payload Lex indica se LDR è stato interrogato.
`ldr_blocked_reason` spiega perché è stato bloccato (es. "Query sensibile").

---

## 5. Fonti Ufficiali

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `PCT_LEX_OFFICIAL_EXTRA_DOMAINS` | `` | Domini aggiuntivi autorizzati per la ricerca web ufficiale, separati da virgola. Es: `giustizia.it,cortecostituzionale.it`. |
| `PCT_DATA_DIR` | `data` | Directory root dei dati JSON e database SQLite. |

**Database fonti:**
- `data/fonti_ufficiali/lex_sources.sqlite` — Archivio fonti ufficiali
- `data/normativa/normattiva.sqlite` — Import Normattiva

---

## 6. Memoria e Telemetria

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `LEX_ENABLE_MEMORY` | `1` | Abilita la memoria conversazionale per sessione. |
| `LEX_ENABLE_TELEMETRY` | `1` | Abilita il logging di audit e telemetria. |
| `LEX_STRICT_CITATIONS` | `1` | Forza la verifica delle citazioni per workflow normativi. |

---

## 7. Privacy e Sicurezza

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| _(nessuna variabile aggiuntiva)_ | — | Il PrivacyGuard è sempre attivo per default. Non è disabilitabile. |

**Regola ferrea:** Le seguenti variabili hanno sempre default sicuro `0`/disabilitato:
- `LEX_RAW_CHAT_ENABLED=0`
- `LEX_EXTERNAL_ALLOWED=0`
- `LDR_ALLOW_SENSITIVE=0`

Non impostare mai queste variabili a `1` in produzione senza una policy esplicita di studio.

---

## 8. Esempi Configurazione

### Sviluppo locale (Docker)
```env
LEX_GOVERNED_ONLY=1
LEX_AI_MODE=local_first
LEX_EXTERNAL_ALLOWED=0
LEX_DEFAULT_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434/api
OLLAMA_MODEL=llama3.1:8b
LDR_BASE_URL=http://local-deep-research:5000
LDR_USERNAME=admin
LDR_PASSWORD=cambia_questa_password
LDR_ALLOW_SENSITIVE=0
```

### Produzione Railway / Hetzner
```env
LEX_GOVERNED_ONLY=1
LEX_AI_MODE=local_first
LEX_EXTERNAL_ALLOWED=0
OLLAMA_BASE_URL=http://ollama:11434/api
OLLAMA_MODEL=llama3.1:8b
LDR_BASE_URL=http://local-deep-research:5000
LDR_USERNAME=<utente-sicuro>
LDR_PASSWORD=<password-sicura>
LDR_ALLOW_SENSITIVE=0
```

### Test CI/CD
```env
LEX_GOVERNED_ONLY=1
LEX_PROVIDER_FORCE_MOCK=1
LEX_EXTERNAL_ALLOWED=0
LDR_ALLOW_SENSITIVE=0
```

---

## 9. Come Verificare la Configurazione

```bash
# Verifica stato Ollama
curl http://localhost:11434/api/tags

# Verifica stato LDR (se configurato)
curl -u $LDR_USERNAME:$LDR_PASSWORD $LDR_BASE_URL/auth/csrf-token

# Verifica stato gateway Lex (route autenticata)
curl -H "Authorization: Bearer <token>" http://localhost:8080/api/assistente/gateway/stato
```

---

## 10. Troubleshooting

| Sintomo | Causa probabile | Soluzione |
|---------|----------------|-----------|
| Lex risponde sempre `needs_review` | Ollama non raggiungibile | Verifica `OLLAMA_BASE_URL` e `OLLAMA_ENABLED=1` |
| LDR blocca tutte le query | Query contiene RG/CF/nomi | Verifica il campo `ldr_blocked_reason` nel debug |
| Fonti web non trovate | `LEX_EXTERNAL_ALLOWED=0` | Solo le fonti ufficiali allowlist sono disponibili |
| `confidence` sempre bassa | Nessuna evidenza indicizzata | Indicizza i documenti del fascicolo prima di chiedere |
| Risposta in lingua non italiana | Guard linguistico attivato | Verifica il campo `italian_response_guard_applied` nel metadata |
