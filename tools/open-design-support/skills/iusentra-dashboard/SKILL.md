---
name: iusentra-dashboard
description: |
  Dashboard professionale per studio legale IUSENTRA: KPI, scadenze, fascicoli,
  attivita' recenti, pagamenti, Lex e prossime azioni.
triggers:
  - dashboard
  - cruscotto
  - regia operativa
  - home studio
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

# IUSENTRA Dashboard Skill

## Workflow

1. Leggere `IUSENTRA_DESIGN.md`.
2. Identificare il tipo di dashboard: studio, superadmin, tenant, fascicolo o economia.
3. Mostrare KPI concreti e plausibili:
   - fascicoli attivi;
   - scadenze imminenti;
   - attivita' da validare;
   - parcelle aperte;
   - incassi;
   - alert portali;
   - stato Lex.
4. Prevedere:
   - header pagina;
   - card KPI;
   - sezione prossime azioni;
   - elenco scadenze;
   - attivita' recenti;
   - eventuale pannello Lex;
   - stati vuoti e warning.
5. Usare italiano professionale.
6. Non inventare dati normativi.
7. Non usare colori fuori palette.
8. Non trasformare dashboard operative in landing page.
9. Verificare responsive desktop/tablet/mobile.
10. Chiudere con self-check.

## Output atteso

Prima prototipo o descrizione strutturata.
Solo dopo eventuale integrazione in Jinja/React, con scope esplicito.
