# Lex

Modulo applicativo dedicato all'assistente Lex.

## Obiettivo

Lex vive fuori da `web/app.py` e fuori dal vecchio blueprint monolitico:

- `lex/blueprint.py` costruisce il blueprint Flask
- `lex/router.py`, `lex/contracts.py` e `lex/registry.py` definiscono l'ingresso applicativo riusabile
- `lex/routes.py` espone le route HTTP
- `lex/service.py` espone sia i metodi HTTP storici sia i casi d'uso bounded-context
- `lex/orchestrator.py` coordina contesto, retrieval, guardie, provider e output
- `lex/api/`, `lex/application/`, `lex/domain/`, `lex/workflows/`, `lex/tools/`, `lex/admin/` completano il bounded context
- `lex/context/` raccoglie il contesto pratica riusabile
- `lex/context/today_summary.py` costruisce il quadro operativo giornaliero
- `lex/retrieval/` centralizza il recupero delle fonti
- `lex/guards/` applica perimetro, grounding e pulizia output
- `lex/memory/` gestisce follow-up, routing sociale e continuita' conversazionale
- `lex/prompts/` contiene prompt builder e regia linguistica
- `lex/prompts/system/`, `lex/prompts/tasks/`, `lex/prompts/guards/` tengono i template testuali fuori dalle route
- `lex/formatting/document_export.py` gestisce l'export governabile dei contenuti
- `lex/guards/legal_reference_guard.py` applica i guard rail sui riferimenti legali
- `lex/memory/web_execution.py` decide quando una richiesta implica controllo web operativo
- `lex/runtime_dependencies.py` contiene il wiring runtime di produzione, cosi' `web/` resta solo facciata
- `lex/providers/local_ai_service.py` possiede il servizio AI locale applicativo
- `lex/providers/ollama_runtime.py` possiede la risoluzione runtime Ollama e il warmup del modello
- `lex/providers/` isola il runtime LLM e i bridge provider
- `lex/retrieval/document_parser_docling.py` contiene l'adapter opzionale Docling per parsing locale di documenti complessi, attivo solo con `LEX_DOCLING_ENABLED=1` e fallback automatico al parser legacy

## Compatibilita'

Il blueprint continua a chiamarsi `assistente`, quindi:

- le route `/api/assistente/*` restano invariate
- `url_for('assistente.assistente_chat')` continua a funzionare
- il widget esistente non richiede modifiche lato template o JavaScript
- i moduli legacy in `web/services/assistente_*.py` restano solo come facciate compatibili

## Architettura operativa aggiornata

Dal 16 aprile 2026 il bounded context `lex/` espone anche:

- `lex/adapters/` per facts, eventi e result pack modulo-per-modulo
- `lex/research/` per evidence pack, fonti ufficiali e trusted sources
- `lex/insights/` per segnali operativi, economici, compliance e udienza
- `lex/memory/service.py` per working memory strutturata

Matrice completa: [docs/LEX_AI_MODULE_MATRIX.md](../docs/LEX_AI_MODULE_MATRIX.md)
