---
name: Controllo gap policy
description: Confronta una policy interna con requisiti o fonti governate e segnala gap.
argument-hint: Carica policy interna e indica l'area normativa.
user-invocable: true
allowed-tools:
  - document_context
  - source_policy
  - studio_profile
references:
  - Policy interna
  - Fonti governate Lex
required-context:
  - policy_interna
  - area_normativa
output-schema:
  - Policy
  - Gap
  - Rischio
  - Azioni
  - Fonti
source-mode: strict
---

Identifica differenze tra testo interno e fonti governate.
Non suggerire aggiornamenti automatici: prepara una lista di punti da approvare.
Se la fonte non e' certa, marca il punto come da verificare.
