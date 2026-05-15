---
name: Revisione DPA
description: Controlla una bozza DPA o accordo nomina responsabile e individua gap.
argument-hint: Carica il DPA e indica ruoli, servizio e paese dei fornitori.
user-invocable: true
allowed-tools:
  - document_context
  - source_policy
  - studio_profile
references:
  - GDPR
  - Garante privacy
required-context:
  - dpa
  - ruoli_privacy
output-schema:
  - Ruoli privacy
  - Clausole DPA
  - Gap
  - Azioni
  - Fonti
source-mode: strict
---

Evidenzia ruoli, istruzioni, sub-responsabili, trasferimenti, sicurezza e audit.
Non approvare la bozza: indica solo punti da verificare e proposte di revisione.
