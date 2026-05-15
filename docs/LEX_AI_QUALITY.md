# Lex AI - qualita', prove e tracciabilita'

Lex deve rispondere come assistente legale operativo, non come chatbot generico.
Ogni risposta tecnica deve esporre prove considerate, limiti, punti da verificare
e azioni pratiche. Quando mancano fonti verificabili, la risposta deve dirlo in
modo esplicito e abbassare la confidenza.

## Contratto operativo

- Risposte legali senza saluti, frasi introduttive vaghe o formule da chatbot.
- Fonti e citazioni sempre riconoscibili nei workflow `normativa`,
  `giurisprudenza`, `prassi`, `research` e `fonti`.
- Nei workflow strict non basta nominare una fonte: la risposta deve mostrare
  anche l'estratto o il contesto testuale usato. Se manca, la risposta resta
  da verificare e deve dichiarare il gap di evidenza.
- Distinzione tra dato certo, inferenza prudente e punto da verificare.
- Confidence cap quando una guardia segnala risposta generica o fonte non
  riconoscibile.
- Provenance envelope machine-readable nei metadata della risposta.
- Revisione umana richiesta per contenuti giuridici ad alto impatto.

## Metriche CI

Il package `lex.evaluation` espone metriche pure, senza dipendenze esterne:

- `exact_match`: confronto normalizzato per campi estratti.
- `token_f1`: precision, recall e F1 token-level.
- `citation_fidelity`: controllo deterministico minimo claim/evidenze.
- `refusal_correctness`: false accept e false reject per richieste da rifiutare.

Queste metriche non sostituiscono benchmark esterni come dataset accademici o
red-team manuale, ma fissano una soglia interna anti-regressione sempre
eseguibile in CI.

## Provenienza e trasparenza

`lex.telemetry.provenance.build_provenance_envelope` salva solo hash di query,
risposta ed evidenze, piu' metadati del provider e riferimenti sorgente. Se e'
configurata `LEX_PROVENANCE_HMAC_KEY` oppure `AUDIT_HMAC_KEY`, l'envelope viene
firmato con HMAC-SHA256.

Quando `LEX_DOCLING_ENABLED=1`, il retrieval documentale puo' aggiungere alle
evidenze metadati prodotti localmente da Docling: parser/versione, hash sorgente,
pagina, sezione, indice chunk, OCR e confidence. Questi valori servono per
rendere le citazioni piu' verificabili; non autorizzano Lex a dedurre dati
processuali non presenti negli atti o nei moduli specialistici.

L'envelope contiene:

- schema version;
- workflow;
- flag `ai_generated`;
- flag `human_review_required`;
- hash query, risposta ed evidenze;
- fonti/citazioni considerate;
- provider e parametri di confidenza.

## Comandi utili

```powershell
python -m pytest tests/test_lex_ai_quality_framework.py -q
python -m pytest lex/tests/unit/test_ollama_provider.py lex/tests/unit/test_professional_answer.py -q
```
