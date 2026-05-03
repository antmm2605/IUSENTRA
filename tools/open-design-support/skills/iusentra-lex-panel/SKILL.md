---
name: iusentra-lex-panel
description: |
  Pannelli Lex AI per IUSENTRA: risposta assistita, fonti, confidence,
  fallback, gap di copertura, contesto fascicolo.
triggers:
  - Lex
  - AI
  - assistente
  - ricerca legale
  - fonti
od:
  mode: prototype
  platform: desktop
  scenario: product
  preview:
    type: html
    entry: index.html
  design_system:
    requires: true
    sections: [color, typography, layout, components]
---

# IUSENTRA Lex Panel Skill

## Workflow

1. Leggere `IUSENTRA_DESIGN.md`.
2. La UI Lex deve distinguere:
   - risposta;
   - fonti ufficiali;
   - fonti interne;
   - confidence;
   - gap di copertura;
   - fallback attivato;
   - azioni consigliate;
   - revisione umana.
3. Non presentare output AI come verita' assoluta.
4. Mostrare riferimenti e limiti in modo leggibile.
5. Usare warning professionali.
6. Non inventare fonti.
7. Non modificare retrieval, provider o guardrail senza task esplicito.
8. Prevedere stato loading, errore, assenza fonti.
9. Chiudere con self-check.

## Output atteso

Pannello AI professionale, verificabile e non ingannevole.
