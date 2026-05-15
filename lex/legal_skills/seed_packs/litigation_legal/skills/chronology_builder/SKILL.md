---
name: Cronologia fascicolo
description: Costruisce una cronologia verificabile da documenti e note fascicolo.
argument-hint: Carica documenti, note o elenco eventi del fascicolo.
user-invocable: true
allowed-tools:
  - document_context
  - studio_profile
references:
  - Documenti interni del fascicolo
required-context:
  - documenti_fascicolo
output-schema:
  - Cronologia
  - Prove
  - Lacune
  - Prossime verifiche
  - Fonti
source-mode: balanced
---

Ordina gli eventi solo se supportati da documenti o note interne.
Marca come lacuna ogni passaggio privo di prova o data certa.
Non creare fatti nuovi e non dare per pacifico cio che e' solo inferito.
