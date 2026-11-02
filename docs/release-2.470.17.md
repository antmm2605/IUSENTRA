# 2.470.17 — Letture in sfondo una o due alla volta: fine dei riavvii per memoria esaurita

- Controllo del 02/11/2026: il processo delle pianificazioni è stato chiuso dal kernel per memoria esaurita alle
  08:23, 10:34 e 10:59 (ora italiana) e ripartendo tornava in pochi minuti a 13 GB, con 112 thread; il sito
  rispondeva in 55 secondi. Causa: la ripresa della coda delle letture, a ogni minuto, avviava fino a 20 letture
  di fascicoli per studio senza contare quelle ancora in corso, e ogni lettura fallita si riprogrammava da sola
  dopo 30 secondi fuori da ogni conteggio. Con i 241 fascicoli rimessi in coda dopo la 2.470.16 le letture si
  sommavano fino a esaurire la memoria.
- Ora le letture in sfondo del processo sono al massimo due insieme (`LETTURE_CONCORRENTI`): il tick avvia solo
  i posti liberi, lo stesso fascicolo non parte due volte, e una lettura fallita resta in coda con la sua attesa
  e la riprende il tick, entro lo stesso limite. Test in `tests/test_archivio_letture_runtime.py` (fallisce
  senza la correzione).
- Base: art. 3 D.M. 44/2011 e art. 20 CAD (integrità della lettura dei documenti informatici); nessun cambiamento
  a ciò che si legge, solo a quante letture girano insieme.
