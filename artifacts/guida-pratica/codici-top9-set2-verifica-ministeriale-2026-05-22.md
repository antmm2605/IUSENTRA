# Verifica ministeriale codici TOP9 set2 - 22 maggio 2026

## Oggetto

Codici verificati dopo l'integrazione dei moduli `kb_98_top9_set2_parte1.json` e `kb_98_top9_set2_parte2.json`:

- `100002` - Opposizione a decreto ingiuntivo (art. 645 c.p.c.)
- `413071` - Apertura della tutela ordinaria (interdizione di maggiorenne)
- `143002` - Responsabilità professionale del personale sanitario e della struttura sanitaria
- `220101` - Licenziamento individuale per giustificato motivo oggettivo
- `121003` - Divisione di comunione ereditaria
- `413011` - codice ufficiale ricevuto con descrizione non coerente con la scheda tutela minori
- `140012` - codice ufficiale ricevuto con descrizione non coerente con la scheda risoluzione compravendita immobiliare

## Fonti controllate

- Pagina PST `Download`: `https://pst.giustizia.it/PST/it/download.page`
- Pagina PST `XSD SICI`: `https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC3277`
- Pagina PST `XSD per i Giudici di pace`: `https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC3199`
- Pagina PST `XSD per UNEP`: `https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC3136`
- Pagina PST `XSD per la Corte Suprema di Cassazione`: `https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC4671`
- Pagina PST `XSD per REGINDE`: `https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC4437`

## Esito tecnico

Sono stati scaricati e controllati i pacchetti ufficiali vivi PST:

- `XSD_SICI_20260116.zip`, SHA-256 `9882A052EE7F4B16DDB89E533534435203F048CFB4C4D45C1E8EA1443AC1C4B0`
- `XSD_SIGP_20241128.zip`, SHA-256 `845C52B4335F46C1690A8E9359E6DD715F517B1E5A712E2E570878C07253A17F`
- `XSD_Cassazione_20260227.zip`, SHA-256 `8CCF63A9C16D87E65AFBF11D5913AF7C54E54F212F68225B3F44F96953D507EA`
- `XSD_REGINDE_20251010.zip`, SHA-256 `B7EA56C227764C2597D8D0389EDBB945A891D751D510C0A7FCB991681FBF0FDB`
- `XSD_PLO118_FASE2_per_SW_House_20241106.zip`, SHA-256 `01922D7AD93B0C73FB6F0421CDCC034751F6BF942F298B8BCBA7100C9C1F2C1F`

Controllo eseguito:

- parsing ricorsivo ZIP/XSD/XLSX con `pct.guida_pratica.xsd_catalog_importer`;
- ricerca testuale grezza ricorsiva dentro ZIP e allegati;
- controllo dell'XLSX ufficiale `Codici_oggetto_migrazione_PerStampa_20240122.xlsx`;
- confronto con `pct/data/cataloghi/codici_oggetto_pst.json`.

Risultato parte 1: `100002`, `413071` e `143002` non compaiono nelle enumeration ufficiali PST/XSD controllate e non compaiono negli allegati di supporto PST controllati. Non risultano quindi saltati dall'importatore locale.

Risultato parte 2:

- `220101` compare nel catalogo ufficiale come `Licenziamento individuale per giust. motivo oggettivo` ed è stato integrato come scheda ufficiale depositabile;
- `121003` non compare nel catalogo PST/XSD ufficiale locale e resta scheda interna non depositabile;
- `413011` compare nel catalogo ufficiale come `Provvedimenti urgenti prima dell'assunzione delle funzioni del tutore o del protutore (art. 361 c.c.)`, mentre la scheda ricevuta riguarda `Apertura della tutela ordinaria - minori`; la scheda è stata quindi integrata come `GUIDA_TUTELA_MINORI_ORDINARIA`, senza sovrascrivere il codice ufficiale;
- `140012` compare nel catalogo ufficiale come `Vendita di cose mobili`, mentre la scheda ricevuta riguarda `Risoluzione del contratto di compravendita immobiliare per inadempimento`; la scheda è stata quindi integrata come `GUIDA_COMPRAVENDITA_IMMOBILIARE_RISOLUZIONE`, senza sovrascrivere il codice ufficiale.

## Decisione prodotto

I codici non presenti o non coerenti con la descrizione ministeriale restano integrati come guide pratiche interne curate e facoltative. Non sono marcati come codici ministeriali depositabili e non bloccano il lavoro sul fascicolo.

Codici del modulo che risultano invece ufficiali nel catalogo PST/XSD locale:

- `111021`
- `220101`
- `620001`
