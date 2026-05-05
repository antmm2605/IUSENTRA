# Lex Governed Only

Lex opera di default in modalita' professionale governata: non usa la chat libera come via ordinaria, non riversa allegati nel prompt e non produce risposte legali assertive senza evidenze.

## Perche' la chat libera e' disattivata

Nel gestionale di studio una risposta plausibile ma non verificabile e' un rischio operativo. La modalita' governed-only forza Lex a passare dalla pipeline controllata:

1. classificazione della richiesta;
2. contesto studio o fascicolo;
3. retrieval interno e fonti ufficiali quando richieste;
4. ranking evidenze;
5. provider deterministico o LLM locale con evidenze;
6. guardrail su citazioni, riferimenti legali e allucinazioni;
7. risposta finale con confidence, warning, limiti e prossime azioni.

Se questa pipeline non produce una base sufficiente, Lex deve fermarsi o degradare in modo esplicito.

## Bounded workflow e raw chat

Il bounded workflow e' il percorso professionale: ogni risposta passa da contratti di workflow, evidenze, guardrail, audit e payload strutturato.

La raw chat e' il vecchio canale generativo libero. Resta disponibile solo per test controllati o casi eccezionali e richiede due condizioni contemporanee:

- `LEX_RAW_CHAT_ENABLED=1`;
- payload della richiesta con `allow_unbounded_generation=true`.

Se manca una sola delle due condizioni, Lex restituisce una risposta prudenziale e non invia il prompt al provider libero.

## Variabili ambiente

- `LEX_GOVERNED_ONLY`: default `1`. Quando attiva, ogni richiesta non sociale passa dal bounded workflow.
- `LEX_RAW_CHAT_ENABLED`: default `0`. Abilita tecnicamente la raw chat, ma non basta senza `allow_unbounded_generation=true` nella richiesta.
- `LEX_AI_MODE`: governa il gateway provider, ad esempio `local_first` o `local_only`.
- `LEX_EXTERNAL_ALLOWED`: abilita provider esterni o fonti esterne solo dove la policy privacy e source policy lo consentono.

## Quando mancano fonti o evidenze

Lex non deve inventare norme, sentenze, PDF, ECLI, link ufficiali o estremi puntuali. In assenza di base sufficiente la risposta deve indicare:

- `answer_mode=needs_review`;
- confidence bassa o media al massimo;
- warning esplicito;
- `missing_evidence`;
- `next_actions` concrete, ad esempio agganciare un fascicolo, caricare un documento leggibile, attivare OCR, cercare su fonte ufficiale o verificare manualmente.

Per workflow strict come `normativa`, `giurisprudenza`, `prassi`, `research` e `fonti`, la mancanza di riferimenti verificati blocca o degrada con rischio alto.

## Allegati

Gli allegati non sono testo da incollare nel prompt. Devono essere trasformati in `EvidenceItem` tramite parsing governato o indicizzazione del fascicolo. Se il parsing non produce testo utile, Lex si ferma e chiede lettura/indicizzazione governata.

## Debug e audit

Il payload finale espone i campi principali per verificare perche' Lex ha risposto o si e' fermato:

- `confidence` e `confidence_label`;
- `answer_mode`;
- `risk_level`;
- `warnings`;
- `evidence_summary`;
- `missing_evidence`;
- `considered_sources`;
- `compared_sources`;
- `next_actions`;
- metadata provider come `provider`, `model`, `workflow`, `evidence_count`, `status` e `skipped_generation_reason`.

Questi campi servono alla UI, ai test e al debug operativo: non vanno rimossi per rendere la risposta piu' breve.
