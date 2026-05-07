# Lex Gateway

`lex/gateway` introduce un layer di instradamento intelligente per i provider AI.

Obiettivi:

- preferire runtime locali come Ollama o LM Studio;
- bloccare l'invio esterno di dati sensibili, fascicoli, RG, codice fiscale, IBAN e contenuti legali identificativi;
- consentire provider esterni solo quando `LEX_EXTERNAL_ALLOWED=1` e il contenuto non e' sensibile;
- mantenere un fallback provider-by-provider senza esporre chiavi API nella UI o nelle API diagnostiche.

## Configurazione

Variabili principali:

- `LEX_AI_MODE`: `local_first` o `local_only`
- `LEX_EXTERNAL_ALLOWED`: abilita/disabilita provider esterni
- `LEX_DEFAULT_PROVIDER`: provider predefinito
- `LEX_DEFAULT_MODEL`: modello predefinito
- `OLLAMA_BASE_URL`, `OLLAMA_DEFAULT_MODEL`, `OLLAMA_ENABLED`
- `LMSTUDIO_BASE_URL`, `LMSTUDIO_DEFAULT_MODEL`, `LMSTUDIO_ENABLED`
- `OPENROUTER_API_KEY`, `DEEPSEEK_API_KEY` per provider esterni opzionali

## API diagnostica

Route autenticata:

- `GET /api/assistente/gateway/stato`

La risposta espone mode, provider, modello predefinito e stato privacy senza restituire mai il valore delle chiavi API.

## Guardrail

I test in `lex/tests/test_gateway_privacy_guard.py`, `lex/tests/test_gateway_router.py` e `lex/tests/test_gateway_status.py` verificano classificazione privacy, routing local-first e diagnostica senza leakage di segreti.

## Local Deep Research sidecar

`docker-compose.ldr.yml` aggiunge Local Deep Research e SearXNG come profilo
opzionale `ldr`, riusando il sidecar Ollama locale. Il bridge Python vive in
`lex/integrations/local_deep_research_client.py` e applica la privacy guard
prima di chiamare le API LDR.

Uso previsto:

- ricerche pubbliche e non identificative;
- fonti normative, dottrina, giurisprudenza pubblica e news;
- report con citazioni da usare come evidenze da verificare.

Uso vietato come default:

- fascicoli, clienti, controparti, RG, CF, IBAN, atti e allegati interni;
- credenziali o sessioni di portale;
- qualunque contenuto che deve restare nel retrieval tenant-aware di Lex.

Dettaglio operativo: `docs/IUSENTRA_LOCAL_DEEP_RESEARCH.md`.
