# Generatori DatiAtto QuickOrganizer

Generato: 30/06/2026 21:39 (Europe/Rome).

Questo indice separa la logica dei generatori dal catalogo visibile. Il JSON completo conserva tutti i campi estratti dal C# decompilato; i file per macroarea servono per lettura rapida.

## Conteggi

| Voce | Totale |
| --- | --- |
| Tipi deposito nel catalogo Studio Telematico | 270 |
| Case reali letti nello switch `AttoDaInviareKey` | 664 |
| Metodi `Create_DatiAtto_*` decompilati | 148 |
| Case non presenti nel catalogo UI estratto | 370 |

## File per macroarea

- `artifacts/react-migration/quickorganizer-datiatto-generatori/contenzioso-civile-lavoro-minorenni-e-volontaria-giurisdizione.md` - Contenzioso civile, Lavoro, Minorenni e Volontaria giurisdizione.
- `artifacts/react-migration/quickorganizer-datiatto-generatori/corte-di-cassazione-civile.md` - Corte di Cassazione (civile).
- `artifacts/react-migration/quickorganizer-datiatto-generatori/giudice-di-pace.md` - Giudice di Pace.
- `artifacts/react-migration/quickorganizer-datiatto-generatori/procedimenti-concorsuali.md` - Procedimenti concorsuali.
- `artifacts/react-migration/quickorganizer-datiatto-generatori/processo-esecutivo.md` - Processo esecutivo.
- `artifacts/react-migration/quickorganizer-datiatto-generatori/unep-ufficio-notificazioni-esecuzioni-e-protesti.md` - UNEP - Ufficio Notificazioni, Esecuzioni e Protesti.
- `artifacts/react-migration/quickorganizer-datiatto-generatori/case-non-presenti-nel-catalogo-ui.md` - case dello switch non collegati al catalogo UI estratto.

## Regola operativa

- Per implementare un deposito in IUSENTRA non basta la root XML: bisogna usare anche dati richiesti, codici oggetto fissi, flag e controlli abilitati.
- I campi completi e gli assignment C# sono nel JSON `quickorganizer-datiatto-generatori-campo-per-campo.json`.
