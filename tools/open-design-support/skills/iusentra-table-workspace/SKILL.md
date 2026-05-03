---
name: iusentra-table-workspace
description: |
  Tabelle e workspace densi per IUSENTRA: clienti, fascicoli, pagamenti,
  scadenze, documenti, audit, portali.
triggers:
  - tabella
  - lista
  - archivio
  - workspace
  - elenco
od:
  mode: prototype
  platform: desktop
  scenario: operation
  preview:
    type: html
    entry: index.html
  design_system:
    requires: true
    sections: [color, typography, layout, components]
---

# IUSENTRA Table Workspace Skill

## Workflow

1. Leggere `IUSENTRA_DESIGN.md`.
2. Definire cosa l'utente deve trovare o decidere.
3. Prevedere:
   - filtri;
   - ricerca;
   - ordinamento;
   - badge stato;
   - azioni contestuali;
   - paginazione o stato empty;
   - indicazione risultato.
4. Le colonne devono essere utili, non decorative.
5. Le azioni distruttive devono essere separate.
6. Mobile: trasformare in card o layout leggibile.
7. Non usare tabelle troppo larghe senza fallback.
8. Non nascondere dati critici.
9. Chiudere con self-check.

## Output atteso

Workspace tabellare chiaro, denso ma leggibile.
