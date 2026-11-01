# 2.470.1 — Ogni indicizzazione nel registro, manutenzione RAG senza scritture inutili, azioni del fascicolo leggibili

- **Indice documentale nel registro da ogni via**: l'editor, il caricamento, la ricerca di importi e scadenze e la lettura
  del documento d'identità indicizzano con `indicizza_e_registra`, che segna l'esito nel registro delle letture.
  Prima quei documenti risultavano «da leggere» per sempre per l'indice documentale (analisi del 01/11/2026).
- **Manutenzione del RAG locale**: ogni 30 minuti non riscrive più una lettura per ogni documento invariato di ogni
  fascicolo; legge lo stato del registro una volta per fascicolo e registra solo le letture nuove.
- **Fascicolo**: i pulsanti di «Editor e redazione» e del cestino non si sovrappongono più (prendevano le colonne dei
  filtri dell'elenco); la redazione dal fascicolo non chiede di «selezionare il cliente» mentre legge i dati del
  fascicolo.
