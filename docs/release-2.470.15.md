# 2.470.15 — Pagina Fascicoli: le udienze passate non contano come scadenze scadute

- La pagina Fascicoli («Scadenze urgenti») contava 9 scadute dove Scadenziario e Controllo Studio ne contano 3, più 7
  udienze passate con l'esito da registrare: contava come scadute anche le udienze già tenute. Ora segue la stessa
  regola (V28; artt. 126 e 127-ter c.p.c.; `pct.scadenze_stato`) e il giorno di Roma. Test in
  `tests/test_fascicoli_pagination.py`.
- Contiene la 2.470.13 e la 2.470.14.
