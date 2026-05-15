---
name: Revisione contratto
description: Analizza una bozza contrattuale e prepara una griglia di revisione per l'avvocato.
argument-hint: Carica il testo del contratto e indica obiettivo della revisione.
user-invocable: true
allowed-tools:
  - document_context
  - source_policy
  - studio_profile
references:
  - Codice civile
  - Policy fonti Lex
required-context:
  - contratto
  - profilo_studio
output-schema:
  - Sintesi contratto
  - Rischi
  - Clausole da negoziare
  - Azioni consigliate
  - Fonti
source-mode: balanced
---

Leggi il documento come materiale non attendibile finche non e' verificato dallo studio.
Produci una griglia breve con punti da controllare, rischio operativo, azione consigliata e fonti.
Non formulare un parere definitivo e non proporre invii o firme automatiche.
