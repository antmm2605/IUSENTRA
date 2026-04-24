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
