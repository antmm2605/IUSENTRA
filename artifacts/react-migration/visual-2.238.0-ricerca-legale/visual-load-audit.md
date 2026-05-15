# Visual smoke Ricerca Legale 2.238.0

Data: 2026-05-15
Target: `http://127.0.0.1:8080/ricerca-legale?q=mediazione`
Runtime: Docker locale no-cache `2.238.0`

| Viewport | Esito | Evidenze |
| --- | --- | --- |
| Desktop 1440x980 | OK | Form `Cerca fonti, norme e giurisprudenza`, fonte PST `Portale Servizi Telematici`, contesto `22/04/2026`, nessun termine tecnico vietato, nessun overflow orizzontale. |
| Mobile 390x844 | OK | Stessi marker del desktop; nessun overflow orizzontale. |

Screenshot: `desktop.png`, `mobile.png`.

Nota strumentale: un primo controllo mobile ha usato il selettore testuale generico `Ricerca Legale`, intercettando anche l'etichetta nascosta della sidebar. Il retry con selettore `h1` e' passato senza failure prodotto.
