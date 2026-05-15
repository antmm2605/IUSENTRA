---
name: Preparazione udienza
description: Prepara una scheda di udienza con punti, documenti e verifiche residue.
argument-hint: Indica rito, data, fase e documenti rilevanti.
user-invocable: true
allowed-tools:
  - document_context
  - source_policy
  - studio_profile
references:
  - Fascicolo interno
  - Policy fonti Lex
required-context:
  - fase_processuale
  - documenti_fascicolo
output-schema:
  - Punti udienza
  - Domande
  - Documenti
  - Rischi
  - Fonti
source-mode: strict
---

Prepara una traccia operativa, non una strategia definitiva.
Segnala termini, prove mancanti e documenti da portare all'udienza.
Le domande sono bozze da rivedere dall'avvocato.
