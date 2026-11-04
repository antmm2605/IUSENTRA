# IUSENTRA 2.480.1 — sequenza notturna che parte davvero (04/11/2026)

Nella notte del 03-04/11 la sequenza notturna non è mai partita: il primo passo aspettava il semaforo dei motori senza
limite di tempo, mentre l'OCR rientrava sempre in coda con priorità più alta. L'unico thread della corsia lunga è
rimasto occupato tutta la notte e molti lavori sono risultati «saltati».

- Semaforo equo: chi aspetta guadagna priorità col tempo (un punto ogni 10 secondi), così nessun motore resta escluso.
- Nella catena l'attesa del semaforo è limitata a 5 minuti: se il semaforo è occupato il passo viene riprovato al giro
  successivo, senza bloccare lo scheduler, fino alle 07:30.
- I lavori leggeri a orario fisso (PEC, relate, avvisi) non passano dal semaforo e non bloccano la corsia rapida.
