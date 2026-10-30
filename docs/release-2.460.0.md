# Release 2.460.0

- Classificatore lineare (TF-IDF e regressione logistica in numpy) addestrato sul server sulle proposte quasi certe delle regole del catalogo; nessuna dipendenza nuova, nessuna GPU, nessun testo fuori dal server.
- Misura in sola lettura del catalogo: accordo con le regole sui documenti tenuti da parte, fasce 90-95 e incerte, confronto con le decisioni dell'avvocato documento per documento.
- I disaccordi sicuri con le regole restano nella cartella dello studio sul server, base della revisione rapida; il riepilogo porta solo conteggi e voci pubblicabili.
- Workflow manuale «Classificatore piccolo del catalogo» nel container scheduler-worker.
- Deploy Hetzner: se l'immagine precostruita indicata in .env.hetzner appartiene a un'altra release, il deploy costruisce l'immagine del commit invece di fermarsi.

## Base normativa
- Art. 3 D.M. 44/2011 e art. 20 CAD (integrità dei documenti informatici letti): il classificatore legge solo i testi già estratti e registrati dal catalogo.
- GDPR 2016/679 art. 5, par. 1, lett. c) e art. 25: nessun dato del cliente nel riepilogo; trattamento interamente sul server dello studio.
- Nessuna decisione automatica sul fascicolo: le proposte restano all'avvocato.

## Verifiche
- tests/test_classificatore_catalogo.py: addestramento deterministico, separazione stabile della verifica, disaccordi sicuri, riepilogo senza testi o nomi, salvataggio sul server.
