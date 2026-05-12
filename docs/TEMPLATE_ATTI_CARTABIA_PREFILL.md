# Template Atti Cartabia e Prefill

## Schema Cartabia

Il catalogo master `v1.2.0` arricchisce i 420 template con `cartabia_profile`, `processo_area`, riferimenti normativi governati, condizioni di procedibilita', termini rilevanti, dati obbligatori, controlli Cartabia, controlli deposito, avvisi redazionali, versione regole e stato di revisione.

Gli stati ammessi sono `draft_professionale`, `cartabia_review_required` e `cartabia_ready`. In assenza di validazione professionale documentata il sistema deve usare `cartabia_review_required`.

## Resolver precompilazione

`pct/template_atti_prefill.py` risolve i campi da timbro studio, configurazione studio, utente corrente, cliente, fascicolo, parti, documenti e valori gia' presenti nel compilatore. Ogni campo restituisce `value`, `source`, `source_label`, `confidence`, `editable`, `missing_reason`, `warnings` e `alternatives`.

I vecchi `campi_precompila` restano compatibili: vengono trasformati in binding dichiarativi e risolti dallo stesso resolver.

## Verifica

Eseguire:

```bash
python scripts/template_atti/apply_cartabia_schema.py
python scripts/template_atti/validate_cartabia_catalog.py
pytest tests/test_template_atti_master_catalog.py tests/test_template_atti_cartabia_prefill_timbro.py
```

Il report di copertura viene scritto in `artifacts/template-atti/cartabia-catalog-coverage.md`.

## Limiti

Il ruleset aiuta a controllare completezza e canale, ma non inventa norme puntuali o dati mancanti. Termini, condizioni di procedibilita', rito e strategia processuale restano oggetto di revisione professionale quando indicato.
