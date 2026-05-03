---
name: iusentra-form-professionale
description: |
  Form professionali per IUSENTRA: clienti, fascicoli, preventivi, conferimenti,
  fatture, scadenze, configurazioni tenant.
triggers:
  - form
  - modulo
  - creazione
  - modifica
  - wizard
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

# IUSENTRA Form Professionale Skill

## Workflow

1. Leggere `IUSENTRA_DESIGN.md`.
2. Capire se il form e':
   - semplice;
   - multi-step;
   - wizard;
   - configurazione admin;
   - atto economico;
   - dato sensibile.
3. Ogni campo deve avere label italiana chiara.
4. Usare help text quando serve.
5. Prevedere validazione inline.
6. Prevedere errori e salvataggio.
7. Evidenziare campi obbligatori senza eccessi.
8. Per form lunghi usare sezioni.
9. Non usare placeholder come sostituti delle label.
10. Chiudere con self-check.

## Output atteso

Form chiaro, professionale, accessibile e coerente con IUSENTRA.
