# Lex AI - risposte professionali

## Obiettivo

Lex AI non espone una seconda chat separata: la risposta professionale e' innestata nel flusso reale `LexOrchestrator -> AnswerBuilder`, quindi vale per UI, API e assistente fascicolo.

Dal 2.198.69 la pagina standalone `/lex` e' rimossa come superficie funzionale. L'unica UI supportata e' il widget/icona flottante, che invia tutte le risposte finali a `POST /api/assistente/chat` con payload canonico di sessione, messaggi, contesto pagina, fascicolo e allegati.

Ogni risposta finale viene ora organizzata in sezioni leggibili:

- `Sintesi operativa` o `Risposta professionale`
- `Quadro verificato`
- `Qualita della risposta`
- `Limiti e verifiche`
- `Prossime azioni`

## Regole operative

- La composizione professionale non inventa fonti: riordina la bozza del provider usando evidenze, citazioni, gap di copertura, rischio e confidenza gia' calcolati.
- Se mancano evidenze, fonti ufficiali o il rischio e' alto, Lex segnala revisione professionale obbligatoria prima di uso esterno, deposito o invio al cliente.
- I workflow pratici (`fascicolo`, `udienza`, `telematico`, `economico`, `cabina`, `compliance`) restano rapidi e operativi, ma mostrano sempre cosa e' stato considerato e cosa fare dopo.
- I workflow legali strict (`normativa`, `giurisprudenza`, `prassi`, `research`, `fonti`) richiedono fonti ufficiali o richiami verificati per chiudere una risposta conclusiva.

## Metadati

La risposta contiene `metadata.professional_answer` con:

- `enabled`
- `version`
- `workflow`
- `quality_label`
- `human_review_required`
- `sections`
- `source_profile`

Questi campi servono a UI, audit, test e futuri controlli di qualita' senza dipendere dal testo libero della risposta.
