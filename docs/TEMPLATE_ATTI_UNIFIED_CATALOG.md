# Template Atti - Catalogo unificato

Aggiornato: 2026-05-12.

## Punto unico

`pct/template_atti_unified_catalog.py` e' il punto unico di accesso ai template. Ogni item viene arricchito con:

- `supports_timbro`;
- `supports_prefill`;
- `supports_cartabia_checks`;
- `supports_deposit_checks`;
- `supports_preview`;
- `supports_render`;
- `supports_compiler`;
- binding/fallback compilatore;
- capability mancanti.

## Regola di uso

Nessun template deve essere reso pronto senza passare da timbro, prefill, Cartabia, deposito e audit. I renderer legacy o custom vengono normalizzati dal catalogo unificato.

La compilazione operativa passa dal catalogo al compilatore del template. Dopo la validazione, se l'avvocato ha selezionato una pratica, la bozza viene importata automaticamente come documento del fascicolo e aperta nell'editor professionale.

## Performance

Il catalogo lavora su metadati leggeri. Il prefill dettagliato viene calcolato solo sul template selezionato e con contesto cliente/fascicolo.
