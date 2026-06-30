# Fonti ministeriali deposito telematico - 2026-06-30

Questo file registra le fonti ministeriali lette per integrare il catalogo Studio Telematico/QuickOrganizer nel deposito IUSENTRA. Serve come promemoria operativo dopo compattazioni: le fonti preview non devono essere usate come schema attivo di invio finché il PST non comunica la messa in esercizio.

## Fonti PCT/SICI

- Fonte ufficiale: PST, pagina `Nuovi XSD SICI - 11/06/2026`, `https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC4933`.
- Pacchetto ufficiale scaricato: `https://pst.giustizia.it/PST/resources/cms/documents/XSD_POL27A_11_06_2026.zip`.
- Nota modifiche: `https://pst.giustizia.it/PST/resources/cms/documents/modifiche_XSD_SICI_20260611.pdf`.
- Copia locale archiviata: `docs/specs/ministero/xsd/2026-06-11-sici-preview/XSD_POL27A_11_06_2026/`.
- Conteggio file XSD estratti: `156`.
- Delta ministeriale letto dalla nota PDF: nuovo atto `RichiestaVerbaleSINDACA` dentro `IstanzaGenerica` di `sicid_v7/Parte.xsd`; nuovo codice oggetto `110046` nell'elenco comune dei codici oggetto.
- Stato IUSENTRA: fonte tracciata come preview/non in esercizio; il codice oggetto `110046` non viene ancora accettato come codice operativo di deposito reale.

## Fonti Cassazione

- Fonte ufficiale: PST, pagina `XSD per la Corte Suprema di Cassazione`, aggiornata al `15/06/2026`, `https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC4951`.
- Pacchetto ufficiale scaricato: `https://pst.giustizia.it/PST/resources/cms/documents/XSD_Cassazione_20260611.zip`.
- Copia locale archiviata: `docs/specs/ministero/xsd/2026-06-15-cassazione-preview/XSD_Cassazione_20260611/`.
- Conteggio file XSD estratti: `116`.
- Stato IUSENTRA: fonte tracciata come preview/non in esercizio; non sostituisce il canale Cassazione già marcato production-ready finché il PST non pubblica successivo avviso di messa in esercizio.

## Integrazione software

- Catalogo backend: `pct/deposito_telematico_catalogo.py`.
- Catalogo PST versionato: `pct/pst_catalog.py`.
- API React: `/api/v1/ui/telematico/depositi/catalogo`.
- Payload React fascicolo: `depositCatalog`, con `officialSources`, `ministerialXsdChannels` e `ministerialSchemaEvidence`.
- UI deposito: `frontend/src/components/FascicoliPage.tsx`, pannello compatto `Macroarea / Categoria / Deposito`, badge `Operativo` oppure `Da completare`, blocker puntuale per canali non ancora generabili in modo ministeriale.

## Regola anti falso-verde

I 270 tipi Studio Telematico sono visibili e selezionabili, ma l'invio reale resta abilitabile solo quando il tipo scelto ha generatore `DatiAtto.xml` conforme, `IndiceBusta.xml`, `Atto.msg`, `Atto.enc`, certificato PST `.cer`, firma e invio PEC locale dal PC dell'avvocato. Le fonti preview servono per preparare lo sviluppo dei generatori successivi, non per dichiarare valido un deposito che il PST non ha ancora messo in esercizio.
