# XSD SICI in esercizio dal 19 ottobre 2026

Pacchetto ufficiale `XSD_SICI_20260720.zip`, pubblicato dal PST il 22 luglio 2026.
La [notizia NWS5167](https://pst.giustizia.it/PST/page/it/processo_civile_telematico__comunicazione_alle_software_house_aggiornamento_specifiche_tecniche_deposito_atti_sicid_it_4?contentId=NWS5167&modelId=4) ne conferma la messa in esercizio il 19 ottobre.

I 156 XSD sono conservati senza modifiche. Impronta del pacchetto e di ogni file in `source-manifest.json`.
Il confronto integrale con maggio individua due soli file differenti:

- `tipi-base.xsd`: 13 codici oggetto TSAP aggiunti (835 totali), nessun codice precedente eliminato.
- `eventi.xsd`: valore 24, Documentazione InfoCamere.

L'anticipazione di giugno (`RichiestaVerbaleSINDACA`, 110046) non è compresa in questo pacchetto e resta separata.
Gli schemi storici restano conservati; il runtime usa soltanto gli entry point attivi del catalogo condiviso.
La validazione finale dell'atto selezionato resta obbligatoria. Non vengono introdotti requisiti aggiuntivi per campi facoltativi.
