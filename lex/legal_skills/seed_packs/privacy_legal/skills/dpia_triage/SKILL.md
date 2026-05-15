---
name: Triage DPIA
description: Verifica in modo preliminare se un trattamento richiede approfondimento DPIA.
argument-hint: Descrivi trattamento, dati, interessati, tecnologie e misure note.
user-invocable: true
allowed-tools:
  - source_policy
  - document_context
  - studio_profile
references:
  - GDPR
  - Garante privacy
required-context:
  - descrizione_trattamento
  - categorie_dati
output-schema:
  - Trattamento
  - Soglie DPIA
  - Rischi privacy
  - Misure
  - Fonti
source-mode: strict
---

Lavora solo come triage preliminare.
Se mancano finalita, categorie di dati o misure, segnala il blocco e chiedi integrazione.
La conclusione deve sempre richiedere revisione legale e privacy prima di adottare decisioni.
