# Lex Source Policy System

## Obiettivo

Rendere Lex utile davvero per l'avvocato:

- capisce il tipo di richiesta;
- cerca prima nel contesto interno;
- usa il web solo quando serve;
- classifica le fonti per affidabilita';
- espone sempre livello di fiducia e limiti.

## Entry point pubblico

Per integrazioni semplici resta disponibile il modulo compatibile:

```python
from ai_lex_sources import (
    infer_area,
    evaluate_source,
    SourceMode,
    batch_evaluate_sources,
)
```

La logica governabile vera vive in:

- `lex/research/source_policy/models.py`
- `lex/research/source_policy/catalog.py`
- `lex/research/source_policy/inference.py`
- `lex/research/source_policy/evaluation.py`
- `lex/research/request_profile.py`

## Flusso applicativo

1. `classify_request(...)` profila intento, rischio, modalita' fonti e schema risposta.
2. `build_lex_studio_context(...)` raccoglie contesto interno e, se utile, fonti ufficiali.
3. `SourceRouter` prova prima fonti interne e attiva `OfficialWebSource` solo quando la domanda o il gap di evidenza lo richiedono.
4. `rank_evidence(...)` pesa ogni fonte con trust, freshness, context fit e consensus, non solo con lo score di retrieval.
5. `LegalReferenceGuard` blocca o degrada le richieste legali ad alto rischio se non emergono riferimenti verificati o PDF ufficiali.
6. `AnswerBuilder` espone nella `LexResponse` i campi governati finali: `official_sources`, `coverage_gaps`, `fallback_triggered`, `compared_sources`, `retrieval_cache`, `confidence`, `answer_mode`.
7. `LexRetrievalCache` applica una cache TTL tenant-aware sul retrieval, cosi' le richieste ripetute dello stesso studio non riattivano inutilmente lo stesso giro di sorgenti.
8. Il bridge HTTP del widget chat porta lo stesso messaggio dentro il bounded workflow quando la richiesta e' operativa o legale, trasferendo `focus`, `request_profile`, `execution_policy`, messaggi di sessione e fallback web consentito.

## Catalogo fonti governate

Lex carica ora anche il catalogo fonti da `lex/research/source_policy/sources_registry.yaml`, derivato dal kit operativo delle fonti ufficiali, partner e riservate.

Ogni fonte puo' essere classificata come:

- `API aperta`
- `Open data`
- `Registrazione richiesta`
- `Fonte partner con credenziali`
- `Portale o canale istituzionale`
- `Portale riservato`

Effetti reali nel prodotto:

- i domini del catalogo entrano nel ranking della source policy e non restano piu' `unknown`;
- `OfficialWebSource` prova il fallback web solo sulle fonti davvero compatibili con ricerca pubblica;
- le fonti `partner` o `riservate` non producono risultati finti: finiscono nei `coverage_gaps` e nei `next_actions`;
- il payload finale di Lex conserva i badge di accesso (`source_access_label`, `source_requires_credentials`, `source_restricted`) fino al widget UI.

Esempi coperti:

- `Normattiva`, `Gazzetta Ufficiale`, `EUR-Lex`, `OpenGA`
- `Registro Imprese`
- `INI-PEC`
- `PST / ReGIndE / PdA`
- `PAT / SIGA`
- `PTT / SIGIT`

## Fast-path operativi

- `cabina`, `next_action`, `economico`, `telematico_status`, `compliance`
  usano il provider deterministico locale per risposte rapide, spiegabili e senza dipendenza dal runtime generativo.
- `normativa`, `giurisprudenza`, `prassi`, `fonti`
  restano workflow con retrieval, confronto fonti e obbligo di riferimenti ufficiali verificati.
- quando il runtime Ollama locale entra in circuito aperto dopo errori ripetuti, Lex degrada in modo esplicito invece di continuare a tentare chiamate opache.
- quando il retrieval e' gia' stato calcolato per lo stesso tenant e lo stesso contesto, Lex riusa il pacchetto evidenze dalla cache e dichiara il `cache hit` nel metadata finale.
- Se il pacchetto evidenze non e' sufficiente, Lex non completa in modo plausibile: produce risposta degradata con warning e gap evidenza.
- nelle richieste economiche (`preventivo`, `tariffario`, `fattura`) il bounded workflow evita risposte meta o simulate e apre direttamente il percorso operativo corretto.

## Modalita'

- `strict`: priorita' a fonti primarie o interne forti; se mancano, Lex si ferma.
- `balanced`: combina fonti interne e secondarie affidabili con prudenza.
- `broad`: utile per drafting e ricerca larga, ma con warning espliciti.

## Regole di prodotto

- Lex non inventa norme, sentenze o PDF ufficiali.
- I fatti sensibili devono derivare da contesto interno verificato o fonti forti.
- Le richieste ad alto rischio alzano automaticamente la prudenza.
- Se la base documentale non basta, Lex lo dichiara e non finge certezza.

## Punti di integrazione gia' attivi

- `web/services/assistente_studio_context.py`
- `web/services/assistente_live_web.py`
- `lex/retrieval/search_ranker.py`
- `lex/guards/grounding.py`
- `lex/orchestrator_http.py`
- `lex/http_bounded_bridge.py`
- `web/static/js/pct-lex-assistant.js`
- `lex/research/source_registry.py`
- `lex/research/source_policy/sources_registry.yaml`

## Test

Copertura minima dedicata:

- `lex/tests/unit/test_bundle_scenarios.py`
- `lex/tests/test_http_bounded_bridge.py`
- `lex/tests/unit/test_source_policy.py`
- `lex/tests/unit/test_source_policy_invariants.py`
- `lex/tests/unit/test_source_registry.py`
- `tests/test_telematico_resilience.py`
- `tests/test_local_ai.py`
- `tests/test_runtime_resilience.py`
- `tests/test_structured_logging.py`
- `tests/test_web_bootstrap.py`
- `tests/test_assistente_*.py`
- `tests/test_lex_*.py`
