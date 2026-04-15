# Lex

Modulo applicativo dedicato all'assistente Lex.

## Obiettivo

Lex vive fuori da `web/app.py` e fuori dal vecchio blueprint monolitico:

- `lex/blueprint.py` costruisce il blueprint Flask
- `lex/routes.py` espone le route HTTP
- `lex/service.py` orchestra i casi d'uso
- `lex/orchestrator.py` coordina contesto, retrieval, guardie, provider e output
- `lex/context/` raccoglie il contesto pratica riusabile
- `lex/context/today_summary.py` costruisce il quadro operativo giornaliero
- `lex/retrieval/` centralizza il recupero delle fonti
- `lex/guards/` applica perimetro, grounding e pulizia output
- `lex/memory/` gestisce follow-up, routing sociale e continuita' conversazionale
- `lex/prompts/` contiene prompt builder e regia linguistica
- `lex/providers/` isola il runtime LLM

## Compatibilita'

Il blueprint continua a chiamarsi `assistente`, quindi:

- le route `/api/assistente/*` restano invariate
- `url_for('assistente.assistente_chat')` continua a funzionare
- il widget esistente non richiede modifiche lato template o JavaScript
- i moduli legacy in `web/services/assistente_*.py` restano solo come facciate compatibili
