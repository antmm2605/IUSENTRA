# Tariffario Coverage Report

## Aree coperte

Tariffario, compensi forensi, preventivi, conferimenti e fatturazione usano route React gia governate con calcolo backend e fonte DM55/DM147 da preservare.

## Aree parziali

Dettagli/export e sotto-route wildcard restano legacy. La copertura completa per mediazione, negoziazione, stragiudiziale e compenso a tempo richiede verifica delle tabelle applicabili.

## Fonti

Registro aggiornato in `pct/data/legal_sources_registry.json`: `dm_55_2014`, `dm_147_2022`, `l_247_2012_art_13`, Normattiva e Gazzetta Ufficiale.

## Fallback

Nessun valore tariffario nuovo e' stato inventato. Le fonti non verificate restano `manual_review_required`.

## Bug corretti

Aggiunta tracciabilita fonte in registry e test dedicato. Nessun calcolo tariffario modificato.

## Rischi residui

Serve coverage per singole tabelle/scaglioni e controllo UI che mostri coverage gap quando la base normativa non e' completa.
