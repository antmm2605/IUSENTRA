# PST / PolisWeb - fascicolo, schede e catalogo documenti

Data consultazione: 29 maggio 2026.

## Fonti verificate

- Ministero della Giustizia, Portale Servizi Telematici, documentazione servizi web per software house, `Documentazione_servizi_web_v1.69.pdf`: `https://pst.giustizia.it/PST/resources/cms/documents/Documentazione_servizi_web_v1.69.pdf`.
- Pacchetto ministeriale versionato in repository: `docs/specs/ministero/A1_WSDL_CATALOG_v1.52/`.
- WSDL ufficiali locali:
  - `WSDL/Accesso ai Documenti/Fascicolo Informatico/SICID/BEAFascicoloInformatico-distr.wsdl`;
  - `WSDL/Accesso ai Documenti/Fascicolo Informatico/SIECIC/bea-fascicolo-siecic.wsdl`;
  - `WSDL/Accesso ai Documenti/Fascicolo Informatico/SIGP/BEAFascicoloInformatico-distr.wsdl`;
  - `WSDL/Accesso ai Documenti/Fascicolo Informatico/SIGP/sigp-consultazioneDocumenti.wsdl`.
- Cataloghi qbuilder ufficiali locali:
  - `Catalog/Consultazione Registri/SICID/catalog_sicc_be.xml`;
  - `Catalog/Consultazione Registri/SICID/catalog_sil_be.xml`;
  - `Catalog/Consultazione Registri/SICID/catalog_sivg_be.xml`;
  - `Catalog/Consultazione Registri/SICID/catalog_min_be.xml`;
  - `Catalog/Consultazione Registri/SIECIC/catalog_siecic_be.xml`;
  - `Catalog/Consultazione Registri/SIGP/catalogJpw.xml`.

## Regola di importazione

L'importazione del fascicolo PST non deve considerare sufficiente la sola tabella `DocumentiFascicolo` o `ElencoDocumenti`. Il fascicolo visualizzato sul portale è composto da più schede logiche:

- dettaglio/profilo del fascicolo (`InfoFascicolo`, `ProfiloFascicolo`);
- catalogo documenti (`DocumentiFascicolo`, `ElencoDocumenti`);
- profilo e dettaglio del singolo atto (`estraiProfiloDocumento`, `estraiMasterDetailAtto`);
- storico/eventi del fascicolo (`StoricoFascicolo` o classi `Evento`);
- scadenze/udienze (`RicercaScadenze`, `InfoScadenze`, `ScadenzaTermine`);
- comunicazioni e notificazioni di cancelleria (`ComunicazioneCancelleria`, `DettaglioComunicazione`, classi `Comunicazioni`, `dettaglioComunicazioni`, `NotificaDaRitiro`);
- istanze o domande collegate (`DettaglioIstanze`, classe `IstanzaFascicolo`);
- dati accessori del profilo, come `FascicoloPrecedente` e `NumeroCivile`.

Per ogni documento principale esposto dal catalogo, quando il servizio lo permette, IUSENTRA deve interrogare `estraiMasterDetailAtto` in batch e aggiungere all'inventario anche `docPrimario` e `docsSecondari`. Gli allegati secondari devono restare selezionabili come gli altri documenti e conservare il collegamento con il documento padre (`id_documento_padre`, `parent_nome`, `is_allegato`). Il catalogo qbuilder può esporre più identificativi tecnici per lo stesso atto (`id_documento`, `id_cat`, `id_repeatto`, `id_reperto`, `msg_id`, `numero_documento`, `id_doc_mittente`): l'arricchimento master-detail deve provarli tutti, senza fermarsi al primo, perché su alcuni registri il primo valore consente il download del primario ma non restituisce l'elenco completo degli allegati visibile nel portale.

La ricerca per anno deve produrre una lista di fascicoli quando l'utente indica ufficio e anno senza numero. Il download non parte dalla lista annuale: l'utente seleziona il fascicolo e solo dopo IUSENTRA carica lo snapshot completo del fascicolo scelto.

Per la ricerca annuale qbuilder i nomi delle interrogazioni restano quelli del registro:

- `ArchivioFascicoli` per registri SICID-family e SIGP, come indicato dalla documentazione servizi web PST;
- `RicercaArchivioPC` e `RicercaArchivioEI` per SIECIC, così da coprire procedure concorsuali ed esecuzioni senza assumere una sola materia.

## Vincoli di non regressione

- Restano invariati i tre modi di selezione già verificati: importare tutto, un solo documento o più documenti selezionati.
- Il download resta batch tramite `/pst/download-documenti-batch`; non si reintroducono download singoli ripetuti né `/pst/preflight-auth`.
- Il catalogo documenti resta la fonte primaria per conteggio, selezione e diagnosi; il download serve solo a marcare quali file sono stati acquisiti.
- Le tabelle ministeriali cambiano per materia/servizio (`SICID`, `SIECIC`, `SIGP`, `SIL`, `SIVG`, `MIN/SIMIN`): il codice deve accettare campi equivalenti e conservare gli identificativi ufficiali (`id_documento`, `id_cat`, `id_repeatto`, `id_reperto`, `msg_id`, `id_doc_mittente`) senza sostituire i codici ministeriali del fascicolo.
