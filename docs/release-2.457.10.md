# Etichette certe dai depositi e statistiche del catalogo

Seguito del censimento del 29/10/2026. Sul server risultavano 336 fascicoli, 11.938 documenti e solo 6 etichette certe utilizzabili: 4 correzioni e 2 conferme singole dell'avvocato. Le 97 conferme massive sono escluse. Le etichette del portale risultavano zero.

- **I metadati del portale stanno nel deposito.** Classificazione e tipo atto di ogni file importato dal PST sono conservati nel deposito (`EsitoDepositoPCT.documenti_portale`), non sempre nel documento. Il nuovo modulo `pct/document_intelligence/verita/depositi.py` li collega al file con il resolver condiviso del fascicolo (`GestioneFascicoli._trova_documento_portale_correlato`).
- **Depositi inviati dallo studio.** Il tipo atto dichiarato nel `DatiAtto.xml` della busta etichetta l'atto principale, riconosciuto dal nome registrato nel deposito. Gli allegati restano senza etichetta.
- **Tipi atto nuovi contati.** I tipi atto non ancora in tabella vengono contati per completare la corrispondenza con riscontri.
- **Statistiche del catalogo.** Il censimento riporta:
  - stato e origine delle catalogazioni;
  - fasce di confidenza delle proposte;
  - le voci «quasi certe» (proposte delle regole con confidenza almeno 96), candidate come base di addestramento da misurare solo sulle etichette certe.

Nessuna modifica alla classificazione in uso. Test in `tests/test_verita_catalogo.py`.
