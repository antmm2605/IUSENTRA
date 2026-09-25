# Performance Guidelines

## Obiettivo
Bloccare regressioni evidenti prima che arrivino in produzione.

## Minimo richiesto
- smoke benchmark esistente
- controllo import / bootstrap / lex path
- soglie esplicite quando avrai numeri stabili

## Ricerca globale
- La richiesta interattiva usa soltanto `tenant_id` e l'indice
  `global_search.db`; non deve inizializzare i repository di dominio.
- Il contesto completo viene costruito solo quando l'indice del tenant e'
  vuoto e deve essere ricostruito.
- Il repository esegue il DDL soltanto se manca un oggetto dello schema; su un
  indice pronto usa `sqlite_master` per verificare tabelle, indici e FTS.
- Il test mirato e'
  `test_topbar_search_non_riapre_i_repository_con_indice_pronto`.

## Evoluzione
Fase attuale:
- presenza e coerenza di performance_smoke.py

Fase successiva:
- output JSON benchmarkato
- comparazione run corrente vs baseline
- fail CI su regressioni superiori a soglia
