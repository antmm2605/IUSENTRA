# Piattaforma Legale Operativa

Aggiornato al **17 aprile 2026**.

Questa tranche porta IUSENTRA dal modello di gestionale avanzato a una **piattaforma legale operativa completa**: il profilo procedurale non vive piu soltanto nella ricerca o nei template, ma attraversa l'intero asse commerciale, operativo ed economico.

## Fonti integrate

Il catalogo operativo e' stato ricostruito a partire dai materiali allegati:

- `legal_taxonomy_postgresql_schema_seed.sql`
- `legal_taxonomy_seed_v2_impl.sql`
- `legal_taxonomy_seed_v2_wave1.sql`
- `legal_taxonomy_seed_v2_wave2.sql`
- `legal_procedure_generator_v2.py` con schema e preset associati

`wave3` era ancora solo segnaposto, quindi la copertura reale importata e verificata e' basata sulle procedure effettive di `wave1` e `wave2`.

## Copertura operativa

Il catalogo interno `pct/legal_platform_seed.py` contiene **22 procedure operative reali** con:

- area e sottobranca specialistica
- canale operativo e registro
- workflow operativo
- hint tariffario
- checklist, documenti richiesti e template
- binding coerenti per preventivo, conferimento, fascicolo, parcella e fattura

## Associazione modulo per modulo

| Modulo | Stato | Modalita di aggancio | Read/write parity |
|---|---|---|---|
| Preventivi | Operativo | `procedura_operativa_*` derivata da pratica, oggetto e rito | piena |
| Conferimento incarico | Operativo | eredita o risolve la stessa procedura del preventivo | piena |
| Tariffario / contesto economico | Operativo | il contesto economico incorpora la procedura e i suoi metadati | piena |
| Fascicolo | Operativo | il workflow di apertura propaga la procedura nel fascicolo | piena |
| Parcella | Operativo | la parcella eredita il profilo operativo del caso | piena |
| Fattura | Operativo | la FatturaPA usa la parcella e la causale arricchita dal contesto | piena tramite parcella |

## Effetto di prodotto

Con questa struttura la piattaforma puo':

- usare la stessa procedura lungo preventivo, conferimento, fascicolo e fatturazione;
- mantenere coerenza tra canale operativo, registro e workflow;
- fornire a Lex e ai repository strutturati un quadro unico e non frammentato;
- evitare che ogni modulo reinveti una propria classificazione locale.

## Regola architetturale

La procedura operativa e' trattata come **profilo condiviso** e non come testo libero. I moduli persistono campi scalari governabili (`procedura_operativa_codice`, `workflow_operativo_codice`, `canale_operativo`, `registro_operativo`, ecc.) e ricostruiscono il profilo completo tramite catalogo centrale.
