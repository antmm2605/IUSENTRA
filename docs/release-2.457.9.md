# Censimento delle etichette certe: percorso dei fascicoli

Correzione della 2.457.8. Il censimento in sola lettura sul server si interrompeva al primo studio: trattava il gestore dei fascicoli come un dizionario (`'GestioneFascicoli' object has no attribute 'items'`). Ora percorre tutti i fascicoli, compresi gli archiviati, con l'elenco del gestore. Un fascicolo senza catalogo SQL non ferma il censimento.

Il nuovo test `test_censimento_dello_studio_percorre_tutti_i_fascicoli_anche_archiviati` copre il percorso usato sul server.
