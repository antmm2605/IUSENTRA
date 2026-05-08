# Lex AI Compliance Report

## Guardrail

Lex deve mostrare fonti, documenti usati, contesto fascicolo, assenza fonti, fallback, lingua italiana e richiesta di verifica professionale.

## Interventi

Aggiunto `LexPanel` e client `frontend/src/api/lex.ts` con stato `Contesto insufficiente per una risposta affidabile`, `Fonti utilizzate: nessuna fonte disponibile` e `La risposta richiede verifica professionale`.

## Regole

Nessuna risposta mock introdotta. Nessuna fonte inventata. Nessuna promessa di parere legale definitivo.

## Gap

Servono test end-to-end su RAG fascicolo completo, isolamento tenant, salvataggio output esplicito e provider local/cloud.
