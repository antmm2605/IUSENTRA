# Tariffario forense completo

Documento operativo per il motore `Tariffario / Preventivi / Compensi forensi`.

## Fonte dati

La fonte tabellare primaria e' `pct/data/tariffario_dm147_2022.json`. Il motore usa solo importi presenti nello snapshot o nei supplementi dichiarati in `TARIFFARIO_SNAPSHOT_SUPPLEMENTS`.

Tabelle coperte dal catalogo:

- Civile e lavoro: `A1`, `A2`, `A3`, `A4`, `A5`, `A6`, `A7`, `A8`, `A9`, `A10`, `A11`, `A12`, `A13`, `A14`.
- Penale: `A15-1`, `A15-2`, `A15-3`, `A15-4`, `A15-5`, `A15-6`, `A15-7`, `A15-8`, `A15-9`, `A15-10`, `A15-11`, `A15-12`, `A15-13`, piu' supplementi dichiarati `A15-CONVALIDA` e `A15-MSORV`.
- Esecuzioni e affari speciali: `A16`, `A17`, `A18`, `A19`, `A20`, supplemento dichiarato `A20-BIS`.
- Amministrativo e tributario: `A21`, `A22`, `A23`, `A24`.
- Stragiudiziale, arbitrato, ADR: `A25`, `A26`, `A27`.

## Stati di copertura

- `snapshot_esatto`: la tabella applicata e' presente nello snapshot DM 147/2022 e il profilo usa quei valori senza importi autonomi.
- `ricostruzione`: il profilo usa una tabella presente, ma con mapping operativo, coefficiente, supplemento dichiarato o fase non perfettamente speculare alla voce ministeriale.
- `fallback_tecnico`: il calcolo non deve essere silenzioso. Se compare, deve arrivare in note, warning e audit.

Ogni risultato espone `table_code`, `table_label`, `rule_code`, `rule_label`, `exact_snapshot`, `compliance_status`, `compliance_note`, `source_snapshot`, `reference_codes`, `riferimenti_normativi` e `audit_tariffario`.

## Aree operative

Sono esposte regole per civile ordinario, lavoro, previdenza, esecuzioni, volontaria giurisdizione/famiglia, penale, amministrativo, tributario, stragiudiziale, mediazione, negoziazione assistita, arbitrato, Corte dei Conti, crisi d'impresa e giurisdizioni superiori/europee.

Le regole specialistiche aggiunte includono lavoro dirigenziale, demansionamento, mobbing/straining, invalidita civile, accompagnamento, opposizioni INPS/INAIL, accesso atti, ottemperanza, appalti, cartelle, avvisi di accertamento, fermo/ipoteca, assistenza contrattuale, due diligence, recupero credito stragiudiziale, mediazione obbligatoria/volontaria/demandata, ADR con o senza accordo, arbitrato irrituale, giudizi contabili e procedure di crisi.

## Fascia oltre EUR 520.000

Tutte le tabelle a scaglioni selezionano esplicitamente `Oltre EUR 520.000` per valori `> 520000`, inclusi `520001`, `1000000` e `5000000`.

La settima colonna dello snapshot, quando rappresenta il valore indeterminabile e non una progressione di valore, non viene trattata come scaglione alto. Il motore mantiene separata la logica dell'indeterminabile e usa la fonte progressiva corretta per la fascia alta.

## Valore indeterminabile

La complessita `molto_alta` e' disponibile con label `Molto alta` e descrizione `Valore indeterminabile collocato nella fascia oltre EUR 520.000.`

Nel motore:

- `ComplessitaStimata.MOLTO_ALTA` usa valore virtuale `520001.0`.
- Il valore virtuale serve solo a scegliere lo scaglione, non diventa valore dichiarato dal cliente.
- Le note riportano `Valore indeterminabile parametrizzato` e l'audit espone `valore_indeterminabile_parametrizzato = true`.

## Riferimenti normativi

Il catalogo aggancia almeno:

- `l247_art13`, `dm55_parametri`, `dm147_aggiornamento`.
- `dm55_art2`, `dm55_art4`, `dm55_art4bis`, `dm55_art19`, `dm55_art20_adr`, `dm55_art22bis`.
- `l49_equo_compenso`, `l576_art11`, `dpr633_art15`, `dpr633_iva`.
- `d_lgs_28_2010_mediazione`, `dm150_2023_mediazione`, `dl132_2014_negoziazione`.
- `dlgs174_giustizia_contabile`, `dlgs14_crisi_impresa`.

## Aggiungere una tabella

1. Inserire i valori nello snapshot o in `TARIFFARIO_SNAPSHOT_SUPPLEMENTS`.
2. Aggiungere metadati in `TABELLE_SNAPSHOT_META`.
3. Collegare profilo e regole in `PROFILE_ROWS` / `RULE_ROWS`.
4. Agganciare `reference_codes` se la materia richiede riferimenti ulteriori.
5. Eseguire `validate_tariffario_catalog_coverage()` e i test dedicati.

## Test

Comandi principali:

```bash
python -m pytest tests/test_tariffario_catalogo_coverage.py -q
python -m pytest tests/test_tariffario_fascia_alta.py -q
python -m pytest tests/test_preventivi_wizard_tariffario_audit.py -q
```
