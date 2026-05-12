# Catalogo Master Template Atti

Il catalogo master dei template atti e' la fonte versionata usata da `Template Atti`, dal repository strutturato e da Lex AI per orientare redazione, ricerca e controlli di conformita'.

## File ufficiali

- `pct/template_atti_catalogo_data/catalogo_master.json`
- `pct/template_atti_catalogo_data/core.json`
- `pct/template_atti_catalogo_data/advanced.json`
- `pct/template_atti_catalogo_data/specialist.json`
- `pct/template_atti_catalogo_data/studio_interno.json`

Il master contiene `420` template e i file split coprono l'intero catalogo senza sovrapposizioni. Dalla versione `1.2.0` ogni voce contiene anche profilo Cartabia, binding di precompilazione e collegamento al compilatore operativo.

- `core`: civile, Giudice di Pace, monitorio, esecuzioni, cautelari
- `advanced`: famiglia, VG, locazioni, lavoro, responsabilita', stragiudiziale, bancario, societario, IP, privacy, consumatori
- `specialist`: penale, tributario, amministrativo, ADR, concorsuale
- `studio_interno`: incarichi, preventivi, procure, privacy cliente, note proforma e atti interni

## Schema obbligatorio

Ogni voce deve mantenere questi campi:

`id`, `slug`, `titolo`, `famiglia`, `area`, `macro_area`, `sottobranca`, `procedimento`, `fase`, `autorita`, `rito`, `canale_telematico`, `depositabile`, `tags`, `campi_precompila`, `blocchi_guidati`, `varianti`, `allegati_essenziali`, `checklist_conformita`, `note_operative`, `cartabia_profile`, `processo_area`, `normativa_riferimento`, `condizioni_procedibilita`, `termini_processuali_rilevanti`, `dati_obbligatori_cartabia`, `controlli_cartabia`, `controlli_deposito`, `avvisi_redazionali`, `richiede_verifica_avvocato`, `stato_conformita`, `data_ultimo_aggiornamento_normativo`, `versione_regole`, `fonte_regole`, `prefill_bindings`, `required_prefill_fields`, `optional_prefill_fields`, `cartabia_required_fields`, `deposit_required_fields`, `link_compilatore_code`, `versione`, `stato`, `ordinamento`.

`stato_conformita` non e' un bollino assoluto: puo' valere `draft_professionale`, `cartabia_review_required` o `cartabia_ready`. Lo stato `cartabia_ready` richiede regole superate e revisione documentata; in caso di dubbio resta `cartabia_review_required`.

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

La route `/template-atti/catalogo` deve mostrare il master dentro la superficie unica del catalogo template atti, senza creare tab o pagine separate:

- nessun tab `Master professionale`;
- 192 modelli operativi del compilatore sempre visibili e non sostituibili dal master;
- ricerca per titolo, ID, area, famiglia, tag e canale telematico;
- filtri per gruppi `core`, `advanced`, `specialist`, `studio_interno`;
- 420 card master reali con pulsante `Compila` collegato a un modello operativo del compilatore guidato tramite `link_compilatore_code`;
- binding esatto quando disponibile, fallback governato per canale/modulo/titolo quando il titolo master non coincide con un vecchio modello.

## Guardrail

I test in `tests/test_template_atti_master_catalog.py` verificano che:

- i cinque file JSON esistano e siano coerenti;
- tutti i template abbiano lo schema obbligatorio;
- gli split sommino il totale master;
- il workspace `Template Atti` importi il master senza perdere i template legacy con compilatore guidato;
- la route `/template-atti/catalogo` esponga tutte le 420 card master all'utente;
- nessun master resti senza collegamento alla logica compilatore funzionante.

## Manutenzione schema

Usare gli script dedicati invece di modificare a mano 420 voci:

- `python scripts/template_atti/apply_cartabia_schema.py`
- `python scripts/template_atti/validate_cartabia_catalog.py`
- `python scripts/template_atti/sync_split_catalogs.py`

Il report viene scritto in `artifacts/template-atti/cartabia-catalog-coverage.md` e mantiene conteggi master, split, prefill, timbro automatico e stati Cartabia.
