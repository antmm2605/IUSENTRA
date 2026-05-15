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

### Legal Source Engine nativo

Il motore nativo `lex/legal_sources/` supporta una modalita operativa locale controllata: puo materializzare registro fonti, manoscritti, scorecard e source-card citabili in cartelle ignorate da git. La rete resta vietata di default e l'auto-populate non scarica corpora giuridici.

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `IUSENTRA_LEX_AI_LEGAL_SOURCES_ENABLED` | `false` | Abilita globalmente il Legal Source Engine. Default: spento. |
| `IUSENTRA_LEGAL_SOURCES_ALLOW_NETWORK` | `false` | Consente rete per future integrazioni fonte. Default: vietata. |
| `IUSENTRA_LEGAL_SOURCES_REQUIRE_CITATIONS` | `true` | Impone citazioni strutturate per risposte giuridiche. |
| `IUSENTRA_LEGAL_SOURCES_DATA_DIR` | `data/legal_sources` | Directory dati futura, ignorata da git. |
| `IUSENTRA_LEGAL_SOURCES_INDEX_DIR` | `indexes/legal_sources` | Directory indici futura, ignorata da git. |
| `IUSENTRA_LEGAL_SOURCES_ARTIFACT_DIR` | `artifacts/legal_sources` | Directory report e dry-run, ignorata da git. |
| `IUSENTRA_LEGAL_SOURCES_RATE_LIMIT_PER_MINUTE` | `30` | Rate limit conservativo per fonte quando la rete sara' abilitata. |
| `IUSENTRA_LEGAL_SOURCES_AUTO_POPULATE` | `false` | Genera automaticamente indice locale source-card quando il motore e' abilitato. Nessuna rete. |
| `IUSENTRA_LEGAL_SOURCES_POPULATE_ON_STARTUP` | `false` | Riservato all'avvio applicativo futuro; il codice corrente non aggiunge route pubbliche. |
| `IUSENTRA_LEGAL_SOURCES_ENABLE_ALL_SOURCES` | `false` | Abilita tutte le fonti registrate solo con opt-in esplicito. |
| `IUSENTRA_LEGAL_SOURCES_RUNTIME_CONFIG` | `data/legal_sources/runtime_config.json` | Config locale ignorata da git scritta dal comando di attivazione controllata. |

Flag per fonte, tutti `false` di default:

```env
IUSENTRA_SOURCE_NORMATTIVA_ENABLED=false
IUSENTRA_SOURCE_GAZZETTA_UFFICIALE_ENABLED=false
IUSENTRA_SOURCE_CORTE_COSTITUZIONALE_ENABLED=false
IUSENTRA_SOURCE_CASSAZIONE_ENABLED=false
IUSENTRA_SOURCE_GIUSTIZIA_AMMINISTRATIVA_ENABLED=false
IUSENTRA_SOURCE_BANCA_DATI_MERITO_ENABLED=false
IUSENTRA_SOURCE_EURLEX_ENABLED=false
IUSENTRA_SOURCE_HUDOC_ENABLED=false
IUSENTRA_SOURCE_AGENZIA_ENTRATE_ENABLED=false
IUSENTRA_SOURCE_GARANTE_PRIVACY_ENABLED=false
IUSENTRA_SOURCE_ANAC_ENABLED=false
IUSENTRA_SOURCE_AGCM_ENABLED=false
IUSENTRA_SOURCE_CAMERA_ENABLED=false
IUSENTRA_SOURCE_SENATO_ENABLED=false
IUSENTRA_SOURCE_LEGGI_REGIONALI_ENABLED=false
```

Attivazione locale controllata, senza rete e senza backup:

```powershell
python -m lex.legal_sources.populate --activate --populate --force --json
```

Il comando scrive solo in `data/legal_sources/`, `indexes/legal_sources/` e `artifacts/legal_sources/`, tutte cartelle ignorate da git.
Nei container/server con `PCT_DATA_ROOT=/data`, i default runtime vengono risolti sotto `/data/legal_sources`, `/data/indexes/legal_sources` e `/data/artifacts/legal_sources`.

### Operational Knowledge tenant-aware

Il layer `lex/operational_knowledge/` permette a Lex di interrogare dati reali dello studio con tool deterministici: clienti, soggetti, fascicoli, agenda, scadenziario, preventivi, conferimenti, tariffario, fatturazione, timesheet, documenti fascicolo, messaggi, notifiche, template atti, legal intelligence, update intelligence e fonti ufficiali locali. Non usa web per dati cliente/studio, non legge file arbitrari ed e' attivo di default nel bounded workflow Lex; puo' essere spento solo con opt-out esplicito.

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `LEX_OPERATIONAL_KNOWLEDGE_ENABLED` | `true` | Abilita il layer operativo tenant-aware dentro il bounded workflow Lex. Impostare `0` solo per rollback controllato. |
| `LEX_OPERATIONAL_AUDIT_ENABLED` | `false` | Registra eventi audit `lex.operational.query` / `lex.operational.blocked` tramite il repository audit dello studio. |
| `LEX_OPERATIONAL_STRICT_MODE_ENABLED` | `false` | Modalita' prudenziale per future restrizioni aggiuntive. Le guardie RBAC/tenant restano sempre attive. |
| `LEX_OPERATIONAL_MAX_RESULTS` | `12` | Limite massimo risultati per tool deterministico. |
| `LEX_OPERATIONAL_MAX_ANSWER_ITEMS` | `6` | Limite di elementi sintetizzati nella risposta naturale. |

Configurazione consigliata:

```env
LEX_OPERATIONAL_KNOWLEDGE_ENABLED=1
LEX_OPERATIONAL_AUDIT_ENABLED=1
LEX_OPERATIONAL_STRICT_MODE_ENABLED=1
```

Ogni risposta operativa espone fonti interne, permessi applicati, confidence, coverage gap e oggetti letti. Se il tenant, l'utente o i permessi non sono disponibili, il layer risponde fail-closed invece di usare fallback globali.

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
| Lex non consulta clienti, agenda o preventivi | `LEX_OPERATIONAL_KNOWLEDGE_ENABLED=0` oppure permessi/tenant mancanti | Riporta il flag a `1` e verifica `ai.usa` piu' i permessi dominio dell'utente |
| `confidence` sempre bassa | Nessuna evidenza indicizzata | Indicizza i documenti del fascicolo prima di chiedere |
| Risposta in lingua non italiana | Guard linguistico attivato | Verifica il campo `italian_response_guard_applied` nel metadata |
