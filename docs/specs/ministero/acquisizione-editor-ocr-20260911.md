# Editor atti: acquisizione in PDF, OCR facoltativo, colori e zoom a due dita

Data: 11/09/2026. Versione: 2.299.0. Stato: lavoro aperto finché non è
eseguita la prova su scanner, webcam e telefono reali dello studio.

## Richiesta

1. In `Colore testo` ed `Evidenzia` i colori non si vedevano.
2. Acquisire da scanner o webcam sul PC (Local Signer) e dalla fotocamera sul
   telefono; il risultato deve essere un PDF; dopo l'acquisizione l'avvocato può
   decidere di eseguire l'OCR.
3. Acquisizione da fotocamera professionale: il foglio viene rilevato e il
   riquadro di ciò che si acquisisce è mostrato durante l'inquadratura.
4. Sul telefono, zoom a due dita sul foglio mentre si scrive.

## Base normativa

- D.Lgs. 82/2005 (CAD), art. 22: copia informatica per immagine di documento
  analogico. L'OCR aggiunge un livello di testo ma il PDF resta una copia per
  immagine.
- Specifiche tecniche DGSIA ex art. 34 D.M. 44/2011 (rev. 07/08/2024, in
  `docs/specs/ministero/Specifiche_Tecniche_DGSIA_DM44_2011_2024_08_07.pdf`):
  - art. 15, comma 1, lett. c: l'atto principale è ottenuto da un documento
    testuale, «non è pertanto ammessa la scansione di immagini»;
  - art. 15, comma 1, lett. g: nel penale, per gli atti formati personalmente
    dalle parti, scansione ammessa «in bianco e nero e con una risoluzione pari
    a 200 dpi» → profilo «Atto penale di parte» (A4, 1654×2339 px, bianco e nero);
  - art. 16: allegati in PDF/JPEG; procura alle liti anche come copia per
    immagine in PDF → profilo «Allegato o procura».

## Diagnosi colori

Nel bundle di produzione i campioni risultavano bianchi e larghi 44 px:
`.iu-template-pro-toolbar button { background: #fff }` (specificità 0,1,1)
copriva `.iu-ted-swatch--*` (0,1,0) e il preset globale
`.iusentra-preset-active main button { min-width: 44px }` allargava i campioni
oltre la griglia. Correzione in `templateEditor.css` con selettori a
specificità 0,3,1 e variabile `--iu-ted-swatch`. Verificata iniettando le stesse
regole nella scheda reale su `app.iusentra.it/template-atti/editor` (colori e
evidenziatori visibili), poi rimosse.

## Architettura

| Livello | File | Responsabilità |
|---|---|---|
| Editor | `TemplateAttiPage.tsx` | pulsante `Acquisisci`, finestra caricata a richiesta (`lazy`), inserimento del testo riconosciuto nel punto del cursore |
| Finestra | `documentCapture/DocumentAcquisitionDialog.tsx` | sorgenti per dispositivo, stato, conferma di scarto |
| Sorgenti | `AcquisitionSources.tsx` | desktop: Scanner del PC, Webcam del PC; telefono: Fotocamera, App fotocamera; profilo della copia |
| Fotocamera | `SmartCamera.tsx`, `useCameraStream.ts`, `useDocumentDetection.ts` | video senza audio, riquadro dal vivo (~8 analisi/s), stabilità, scatto automatico, luce |
| Ritaglio | `CornerAdjust.tsx` | angoli trascinabili (mouse, dito, frecce), resa della pagina |
| Elaborazione | `detection/documentQuad.ts`, `quadRefine.ts`, `perspective.ts`, `enhance.ts`, `pageProcessing.ts` | rilevamento, affinamento angoli, omografia, filtri, JPEG finale |
| Sessione | `useAcquisitionSession.ts` | pagine, PDF A4, OCR, salvataggio confermato |
| OCR client | `services/documentOcr.ts` | una richiesta per pagina, unione con `/merge` |
| OCR server | `web/services/document_ocr.py`, `web/blueprints/api_v1_document_tools.py` | Tesseract `ita`, PDF ricercabile, paragrafi |
| Zoom | `templateEditor/usePinchZoom.ts` | pizzico a due dita e Ctrl + rotella sul solo foglio |

Il Local Signer non è stato modificato (flusso firma/deposito/PEC congelato il
09/09/2026): lo scanner usa l'endpoint `/scanner/acquire` già distribuito. La
webcam del PC è letta dal browser sullo stesso PC, perché il riquadro dal vivo
richiede i fotogrammi nella pagina; nessun fotogramma viene inviato al server
prima della conferma della pagina.

## Dati e sicurezza

- Nessuna nuova tabella né mirror JSON: pagine e PDF restano in memoria del
  browser; il salvataggio usa `/fascicoli/<id>/documenti/carica` (tenant,
  SQLite/PostgreSQL e audit `fascicoli.documento.carica` invariati), abilitato
  solo dopo la spunta di verifica.
- `/api/v1/ui/document-tools/ocr-page`: autenticazione `_richiedi_auth`, CSRF
  dal client, limite 60 MB e 50 megapixel, orientamento EXIF applicato,
  risposta `Cache-Control: no-store`, dizionario italiano obbligatorio (nessun
  ripiego su altre lingue), concorrenza `IUSENTRA_OCR_PAGE_CONCURRENCY`
  (predefinita 2), timeout 120 s per pagina.
- Fotocamera: `audio: false`, nessuna registrazione, tracce fermate alla
  chiusura e quando la scheda va in secondo piano.

## Verifiche eseguite (ambiente di sviluppo, non macchina dello studio)

- `node --test tests/js/document_acquisition.test.mjs`: 10 test (rilevamento su
  sfondi scuri e chiari, omografia, proporzione A4, filtri, stabilità, pizzico,
  client OCR a una e più pagine).
- `pytest tests/test_document_ocr.py tests/test_template_editor_acquisition_contract.py tests/test_document_tools.py tests/test_document_capture_contracts.py tests/test_template_atti_frontend_contract.py`:
  verdi, incluso OCR reale Tesseract `ita` su pagina A4.
- `npm test` del frontend (contratti React, governance design system, UI
  coverage) e `tsc --noEmit`: verdi.
- Prova end-to-end in Chromium con webcam simulata (foglio in prospettiva su
  tavolo): riquadro stabile in circa 2 s, angoli entro 2 px, scatto, ritaglio,
  seconda pagina da Local Signer simulato, PDF A4 di 2 pagine, OCR con testo
  italiano corretto, salvataggio nel fascicolo di prova.
- Prova mobile emulata (Pixel 7, touch): sorgenti del telefono, riquadro,
  maniglie da 48 px trascinabili, nessuno scorrimento orizzontale, pizzico
  0,48 → 1,68 → 0,60 senza zoom dell'intera pagina.

## Da verificare sulla macchina reale

- Scanner WIA reale tramite Local Signer dal PC dello studio.
- Webcam reale e fotocamera di un telefono Android e di un iPhone (Safari):
  rilevamento con luce e sfondi reali, permessi, luce del telefono.
- OCR sul server Hetzner con pagine reali (tempi per pagina).
- Pizzico a due dita durante la scrittura su telefono reale.

## Limiti noti

- Il rilevamento è pensato per un foglio che contrasti con lo sfondo; su fogli
  bianchi appoggiati su piani chiari gli angoli possono richiedere la
  correzione manuale (errore misurato fino a circa 17 px su 640 px).
- L'anteprima PDF nel riquadro usa il visualizzatore del browser.
