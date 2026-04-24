# Catalogo Master Template Atti

Il catalogo master dei template atti e' la fonte versionata usata da `Template Atti`, dal repository strutturato e da Lex AI per orientare redazione, ricerca e controlli di conformita'.

## File ufficiali

- `pct/template_atti_catalogo_data/catalogo_master.json`
- `pct/template_atti_catalogo_data/core.json`
- `pct/template_atti_catalogo_data/advanced.json`
- `pct/template_atti_catalogo_data/specialist.json`
- `pct/template_atti_catalogo_data/studio_interno.json`

Il master contiene `420` template e i file split coprono l'intero catalogo senza sovrapposizioni:

- `core`: civile, Giudice di Pace, monitorio, esecuzioni, cautelari
- `advanced`: famiglia, VG, locazioni, lavoro, responsabilita', stragiudiziale, bancario, societario, IP, privacy, consumatori
- `specialist`: penale, tributario, amministrativo, ADR, concorsuale
- `studio_interno`: incarichi, preventivi, procure, privacy cliente, note proforma e atti interni

## Schema obbligatorio

Ogni voce deve mantenere questi campi:

`id`, `slug`, `titolo`, `famiglia`, `area`, `macro_area`, `sottobranca`, `procedimento`, `fase`, `autorita`, `rito`, `canale_telematico`, `depositabile`, `tags`, `campi_precompila`, `blocchi_guidati`, `varianti`, `allegati_essenziali`, `checklist_conformita`, `note_operative`, `versione`, `stato`, `ordinamento`.

Gli ID sono governati per modulo, ad esempio `CIV_ORD_001`, `GDP_001`, `MON_001`, `ESE_001`, `FAM_001`, `PEN_001`, `TRI_001`, `AMM_001`.

## Canali telematici

Il campo `canale_telematico` distingue il canale operativo reale:

- `PST`: civile, lavoro, famiglia, esecuzioni e altri depositi PCT/PST
- `PST_GDP`: Giudice di Pace
- `PST_CONCORSUALE`: procedure concorsuali e crisi
- `PDP`: penale
- `PAT`: amministrativo
- `PTT`: tributario
- `NESSUNO`: atti interni o stragiudiziali non depositabili

## Esposizione UI

La route `/template-atti/catalogo` deve mostrare il master come superficie autonoma, non solo come riepilogo:

- tab `Master professionale` sempre visibile accanto a `Per modello` e `Da pratica`;
- ricerca per titolo, ID, area, famiglia, tag e canale telematico;
- filtri per gruppi `core`, `advanced`, `specialist`, `studio_interno`;
- 420 card reali con pulsante `Genera dal master` collegato all'ID governato del template.

## Guardrail

I test in `tests/test_template_atti_master_catalog.py` verificano che:

- i cinque file JSON esistano e siano coerenti;
- tutti i template abbiano lo schema obbligatorio;
- gli split sommino il totale master;
- il workspace `Template Atti` importi il master senza perdere i template legacy con compilatore guidato;
- la route `/template-atti/catalogo` esponga tutte le 420 card master all'utente.
