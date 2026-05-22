# Registro screenshot Guida Pratica - Pacchetto completo v2

Questo registro blocca la sequenza visiva approvanda per evitare confusione con i mockup precedenti.

## Fonte canonica

- HTML sorgente: `artifacts/guida-pratica/mockups/guida-pratica-pacchetto-completo-v2.html`
- Directory screenshot canonici: `artifacts/guida-pratica/mockups/pacchetto-completo-v2/`
- Viewport di verifica: `1600x900`
- Data generazione: 22 maggio 2026

## Screenshot canonici da usare per l'implementazione

| Passaggio | Screenshot canonico | Vincolo da rispettare | SHA-256 |
|---|---|---|---|
| 1. Apertura fascicolo | `apertura.png` | Si parte dalla pagina fascicolo esistente, senza reinventare il flusso. | `526079657E77B64082501B0A887B1B95560162FFCBAD3F1708F8BE5D15A5CA36` |
| 2. Guida nascosta | `nascosta.png` | La Guida Pratica è facoltativa, richiudibile e non blocca il lavoro ordinario. | `499FB0F43CCFCB8E4F4A52F27492F4F92A4A8F85EB5683C05BD75FC1F24D8B41` |
| 3. Guida ora | `ora.png` | La guida mostra passaggi operativi compatti, intuitivi, non una pagina immensa. | `4121FF71848154FE491FEEF99396CBCBA5A1227E27BAE6BEE5BD2B631B1B50C3` |
| 4. Contesto e termini | `contesto.png` | Presupposti, legittimati, termini, fonti e controlli sono leggibili per sezioni. | `80E51BBF5673565ADC05E13809A4EFB0CCCCB54D778DA08C2B98C764F0595A30` |
| 5. Anteprima modifica | `editor.png` | Template filtrato dalla pratica, caricamento automatico se univoco, import PDF/Word, editor in anteprima, timbro e impaginazione da modello. | `65BBE96662B0A4B581B7E49D63B5A976ECBAA0C6998CB7B644BB7030157AD679` |
| 6. Rientro completato | `completato.png` | Il documento salvato rientra nel fascicolo, la guida completa solo il passaggio confermato e Lex si aggiorna. | `3C29B68BEFB0397357A03F68C123936B23E4BA7AEA4AD33FE434176410550F41` |

## Screenshot collegati da mantenere

Questi non sostituiscono la sequenza v2, ma restano vincolanti per dettagli specifici:

- `artifacts/guida-pratica/mockups/template-layout-model/modello-template-page-1.png`: riferimento principale per timbro, firma e impaginazione del template.
- `artifacts/guida-pratica/mockups/template-layout-model/modello-template-page-2.png`: pagina successiva del modello PDF.
- `artifacts/guida-pratica/mockups/template-layout-model/modello-template-page-3.png`: pagina successiva del modello PDF.
- `artifacts/guida-pratica/mockups/impostazioni-patrocinante/patrocinante-cassazione-preview.png`: riferimento per il campo libero `Qualifica professionale` nei Dati Studio.

## Screenshot superati

Non usare questi file come riferimento di implementazione, salvo confronto storico:

- `artifacts/guida-pratica/mockups/pacchetto-completo-v1/*`
- `artifacts/guida-pratica/mockups/flusso-reale/*`
- `artifacts/guida-pratica/mockups/flusso-reale-v2/*`
- `artifacts/guida-pratica/mockups/guida-pratica-redesign-*`
- `artifacts/guida-pratica/mockups/guida-pratica-storyboard-*`
- `artifacts/guida-pratica/mockups/guida-pratica-template-workflow-*`
- `artifacts/guida-pratica/mockups/pacchetto-completo-v2/_superati/editor-esatto-senza-template-import.png`

## Confronto con pacchetto v1

- I passaggi 1, 2, 3, 4 e 6 restano visivamente coerenti con il pacchetto v1 e vengono comunque ricopiati nella cartella v2 per avere una sequenza unica.
- Il passaggio 5 è stato aggiornato: ora mostra esplicitamente template filtrato dalla pratica, caricamento automatico, motivazione della guida e import PDF/Word.
- Da questo momento il riferimento operativo è sempre `pacchetto-completo-v2`, non `pacchetto-completo-v1`.

## Checklist anti-salto passaggi

Prima di implementare o modificare la Guida Pratica, confrontare la UI reale con questi punti:

- il fascicolo resta pagina principale;
- la guida resta opzionale e non bloccante;
- il codice ufficiale del fascicolo resta il codice depositabile PST/XSD quando previsto;
- la guida aggancia la pratica, ma non sostituisce il codice ufficiale;
- il template è filtrato in base alla pratica e al documento suggerito dalla guida;
- se un template è univoco, si apre direttamente in anteprima;
- se ci sono più template, si mostra scelta assistita e motivata;
- PDF e Word importati si aprono nella stessa anteprima;
- il documento importato può essere modificato se editabile, oppure salvato invariato;
- timbro, qualifica professionale e firma rispettano il modello PDF;
- il passaggio guida diventa completo solo dopo salvataggio o conferma;
- Lex conosce guida, template scelto, documento importato o generato e stato finale.
