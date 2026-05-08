# Documenti Compliance Report

## Controlli richiesti

Upload sicuro, tipologia, fascicolo, OCR, PDF/A, firma, metadati, audit, download controllato, anteprima sicura, eliminazione controllata, errori comprensibili.

## Interventi

Aggiunto `IusDocumentStatusBadge` per distinguere `Verificato`, `Non verificato`, `Conforme`, `Non conforme`, `Da controllare`, `Validazione non eseguita` e `Revisione manuale richiesta`.

## Regola applicata

Nessun documento viene dichiarato conforme da questa tranche se il controllo non e' stato eseguito. Non sono state modificate conversione PDF/A, firma, OCR, indicizzazione o deposito.

## Gap

Servono test mirati su upload, stato PDF/A/firma/OCR e audit download/eliminazione per ogni backend storage.
