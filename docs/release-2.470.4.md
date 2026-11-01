# 2.470.4 — Letture notturne senza «database is locked» ed errori superati chiusi

- **Archivio delle letture**: l'attesa quando l'archivio è occupato passa da 5 a 30 secondi, come all'apertura.
  Nella notte del 01/11/2026 la rilettura notturna e il giro ogni 10 minuti scrivevano insieme e 99 fascicoli sono
  finiti in errore («database is locked» o tempo esaurito dopo tre tentativi).
- **Errori superati**: quando un giro successivo legge per intero il fascicolo, l'errore del tentativo precedente si
  chiude; il pannello «Letture e verifiche» non mostra più «Verifiche non concluse» per un problema già risolto.
