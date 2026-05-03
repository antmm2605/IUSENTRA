---
name: iusentra-fascicolo-cabina
description: |
  Cabina operativa fascicolo IUSENTRA: quadro intelligente, documenti, attivita',
  scadenze, economia, comunicazioni, depositi e prossime azioni.
triggers:
  - fascicolo
  - cabina fascicolo
  - dettaglio fascicolo
  - quadro intelligente
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

# IUSENTRA Fascicolo Cabina Skill

## Workflow

1. Leggere `IUSENTRA_DESIGN.md`.
2. La pagina deve aiutare l'avvocato a capire subito:
   - stato fascicolo;
   - prossima azione;
   - scadenze;
   - documenti importanti;
   - attivita';
   - comunicazioni;
   - situazione economica;
   - eventuali alert.
3. Usare layout a tab o pannelli coerenti.
4. Evidenziare warning senza allarmismo grafico.
5. Mostrare stati vuoti utili, non pagine vuote.
6. Non nascondere azioni operative.
7. Non inventare workflow processuali.
8. Non modificare logica portali o storage.
9. Verificare responsive.
10. Chiudere con self-check UI/UX.

## Output atteso

Proposta grafica o prototipo, poi eventuale integrazione controllata.
