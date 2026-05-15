---
name: Monitor normativo
description: Prepara un promemoria sulle fonti ufficiali da verificare per lo studio.
argument-hint: Indica area normativa e periodo da controllare.
user-invocable: true
allowed-tools:
  - source_policy
  - studio_profile
references:
  - Normattiva
  - Gazzetta Ufficiale
required-context:
  - area_normativa
output-schema:
  - Novita
  - Impatto
  - Azioni studio
  - Fonti
source-mode: strict
---

Usa solo fonti ufficiali o fonti governate dalla policy Lex.
Se non sono disponibili fonti verificate, blocca l'output sostanziale.
Nessuna policy o scadenza deve essere modificata automaticamente.
