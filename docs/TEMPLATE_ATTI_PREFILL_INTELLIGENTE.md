# Template Atti - Prefill intelligente

Aggiornato: 2026-06-04.

## Principio

Il prefill cerca prima nei dati interni IUSENTRA e non usa campi manuali prima di aver scandagliato pratica, cliente, parti, studio, utente, documenti e dati telematici gia importati.

## Priorita operative

- Cliente/assistito: parti fascicolo, cliente collegato, form selezionato, preventivo/conferimento, manuale.
- Controparte: parti fascicolo, soggetti collegati, pratica/import autorizzato, manuale.
- Difensore/autore: `Impostazioni > Dati Studio > Avvocato titolare`, poi utente corrente/professionista assegnato, timbro/configurazione studio, manuale.
- Ufficio giudiziario/destinatario: fascicolo, import telematici, Practice Engine, portali autorizzati, manuale.
- Pratica collegata/RG: fascicolo, import portale, ricevute indicizzate, manuale.
- Oggetto: fascicolo, preventivo/conferimento, classificazione pratica, manuale.
- Allegati: documenti fascicolo, slot Practice Engine, upload, import portale, manuale.
- Dati studio: timbro studio, configurazione studio, profilo professionista, manuale.

## Campi risolti

Sono mappati anche i campi contestati nella missione: `Destinatario / Ufficio Giudiziario`, `Cliente / Mittente`, `Pratica Collegata`, `Autore`, oltre a controparte, RG, oggetto, allegati e dati studio. Questi quattro campi sono obbligatori in ogni risoluzione prefill: se l'avvocato non ha ancora selezionato pratica o cliente, il template resta comunque pronto come modello e la compilazione mostra il `missing_reason` per scegliere il contesto. Il campo `Autore` viene risolto prima dall'Avvocato titolare dei Dati Studio, non dall'utente corrente.

Quando una pratica e' selezionata e la bozza passa i controlli del compilatore, IUSENTRA salva automaticamente l'atto come documento HTML del fascicolo e apre l'editor professionale per l'impaginazione.

Ogni campo risolto include valore, fonte, confidence, alternative, conflitto, privacy level e `missing_reason` se non trovato.

## Conflitti

Se due fonti interne affidabili divergono, il resolver segnala `conflict=true`, mostra alternative e non nasconde la discordanza.

## Applicazione nell'editor template atti 2.249.15

Nel workspace `/template-atti/compila/<codice>` il prefill non resta implicito:
la colonna destra mostra `Collegamento IUSENTRA`, consente di selezionare
cliente e fascicolo e ricarica il modello con i dati risolti. Il test reale ha
confermato fascicolo `2DE106E6`, cliente `Moscato Marco`, R.G. `12/2026`,
ufficio giudiziario e materia disponibili nel documento.

I campi manuali dell'avvocato restano editabili senza troncamento: il valore
digitato aggiorna il placeholder corrispondente nell'editor e viene usato da
RTF/DOCX/PDF, copia, salvataggio nel fascicolo e firma. Se un dato automatico
non è certo, il campo resta visibile con fonte/motivo invece di essere inventato.
