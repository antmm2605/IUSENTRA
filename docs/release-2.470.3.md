# 2.470.3 — Il giro automatico delle letture raggiunge tutti i fascicoli

- **Lettura automatica a rotazione**: il giro ogni 10 minuti partiva sempre dal primo fascicolo in ordine di codice
  con un tetto di 150 oggetti; quando i primi fascicoli consumavano il tetto, quelli in fondo all'elenco non venivano
  mai letti (verifica in produzione del 01/11/2026: 190 fascicoli letti da un motore vecchio, un fascicolo fermo dal
  17/09/2026). Ora il giro parte dai fascicoli mai letti e poi da quelli esaminati da più tempo.
- **Documenti del fascicolo**: durante il caricamento la scritta dice che l'elenco compare a caricamento concluso,
  non più «Apri la sezione documenti» a sezione già aperta.
