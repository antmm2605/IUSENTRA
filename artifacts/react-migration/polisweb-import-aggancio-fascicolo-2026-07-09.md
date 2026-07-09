# Import PolisWeb/PST: aggancio fascicolo esistente

Data: 09/07/2026.

## Problema operativo

Quando lo studio scarica o sincronizza un fascicolo da PolisWeb/PST, IUSENTRA non deve creare un nuovo fascicolo se la pratica esiste già. Allo stesso tempo non deve aggiornare un fascicolo sbagliato solo perché numero RG, anno e ufficio coincidono: nei registri ministeriali possono esistere discriminanti ulteriori, soprattutto su SIECIC e flussi importati dal portale.

Il comportamento corretto è quello di Studio Telematico: la pratica selezionata conserva i dati tecnici ricevuti dal portale e li usa per rientrare nello stesso fascicolo. In IUSENTRA questi dati devono essere salvati nel tenant SQL e riusati all'import successivo.

## Dati usati per l'aggancio

Il form `/polisWeb/importa` ora conserva e inoltra al modello `FascicoloPolisWeb` questi campi:

- `numero_rg`, `anno_rg`, `codice_ufficio`, `nome_ufficio`;
- `tipo_registro`, `registro_portale`, `servizio_pst`;
- `sub_procedimento`;
- `id_dfa`;
- `id_fascicolo_portale`;
- `urn`, `target_path`;
- `ruolo_polisweb`.

La chiave primaria di confronto resta `chiave_esterna_fascicolo_polisweb()`, che include i dati ministeriali disponibili. Se la chiave esatta esiste, viene aggiornato quel fascicolo.

## Regola di scelta del fascicolo

L'import segue questa priorità:

1. se arriva un `id_fasc` esplicito dalla UI, viene accettato solo se RG, anno, ufficio e discriminanti PST non sono in conflitto;
2. se esiste un fascicolo con `source_external_id` uguale alla chiave ministeriale attesa, viene sincronizzato quello;
3. se non c'è chiave esatta, IUSENTRA cerca RG, anno e ufficio solo tra fascicoli compatibili con `id_fascicolo_portale`, `id_dfa`, `sub_procedimento`, `registro_portale` e `servizio_pst`;
4. se esistono più fascicoli con stesso RG/anno/ufficio ma discriminanti diverse, l'import non ne sceglie uno a caso;
5. se esiste un solo fascicolo non ancora marcato con discriminanti PST, può essere collegato e arricchito con i nuovi metadati.

Questa regola evita due errori opposti: doppioni inutili quando il fascicolo è già presente, e sovrascrittura di un fascicolo diverso quando il numero RG coincide ma il contesto portale no.

## Test anti-regressione

È stato aggiunto il test `test_route_importa_polisweb_sceglie_fascicolo_esistente_da_iddfa`.

Scenario coperto:

- due fascicoli nello stesso tenant hanno stesso RG, stesso anno e stesso ufficio;
- il primo ha `idDfa` e `id_fascicolo_portale` A;
- il secondo ha `idDfa` e `id_fascicolo_portale` B;
- arriva un import PST senza `id_fasc` esplicito ma con i dati tecnici B;
- IUSENTRA aggiorna il fascicolo B, lascia invariato A e non crea un terzo fascicolo.

È stato aggiunto anche il controllo `test_doppioni_fascicolo_ignora_controparte_nel_nome_cliente`.

Scenario coperto:

- un fascicolo storico ha nel campo cliente un valore sporco come `Eugenio Grosso c. MIM`;
- un altro fascicolo ha lo stesso RG e il cliente pulito/invertito come `Grosso Eugenio`;
- la chiave di presidio elimina la parte di controparte dopo `c.` e riconosce il gruppo come possibile doppione;
- la UI può quindi mostrare il gruppo nella card `Doppioni` invece di dichiarare falsamente `0`.

Durante la prova di applicazione sul server è emerso anche un bug nella fusione dei metadati economici: un campo pagamento con lista vuota non deve generare `TypeError`. Il test `test_riconcilia_doppioni_cliente_rg_unisce_documenti_e_pagamenti` ora copre il caso `fonti_documentali=[]` e verifica che la fonte del duplicato venga conservata.

Aggiornamento prestazionale 09/07/2026: la riconciliazione dei fascicoli doppi in modalità SQL non deve usare il salvataggio globale `_salva()`, perché riscrive tutta la tabella `fascicoli` e il mirror JSON anche quando viene assorbito un solo duplicato. Il metodo ora aggiorna solo il fascicolo principale, cancella solo gli ID assorbiti e rigenera il mirror una volta. Il test `test_riconcilia_doppioni_cliente_rg_sql_salva_solo_record_coinvolti` fallisce se il flusso torna al full replace e verifica che nel DB resti una sola riga per il caso `Grosso Eugenio / RG 795/2026`.

Aggiornamento UI 09/07/2026 emerso da prova visiva server: nel dettaglio fascicolo il pannello `Indicizzazione Lex` non deve mostrare codici macchina come `NOT_INDEXED` né date abbreviate con virgola (`20/06/26, 18:49`). La UI ora normalizza lo stato tecnico in etichette italiane (`Parziale`, `Da aggiornare`, `Pronto`) e usa `formatDateTimeIt`, quindi l'avvocato vede date complete come `20/06/2026 18:49`. Il test `test_react_fascicolo_lex_indexing_non_mostra_status_tecnici_o_date_brevi` presidia questa regola.

Comandi locali già eseguiti sul perimetro:

```powershell
python -m py_compile scripts/audit_quickorganizer_import.py web/bootstrap/polisweb_routes.py
python -m pytest -q tests/test_codeql_public_surface_regressions.py::test_audit_quickorganizer_output_pubblico_redige_dati_privati tests/test_polisweb.py::test_route_importa_polisweb_sceglie_fascicolo_esistente_da_iddfa --tb=short
python -m pytest -q tests/test_codeql_public_surface_regressions.py tests/test_polisweb.py::test_importa_fascicolo_popola_cliente_parti_e_attivita tests/test_polisweb.py::test_importa_fascicolo_esistente_sincronizza_cliente_parti_e_attivita tests/test_polisweb.py::test_route_importa_polisweb_sincronizza_fascicolo_esistente tests/test_polisweb.py::test_route_importa_polisweb_via_local_signer_non_richiede_certificato_server tests/test_polisweb.py::test_route_importa_polisweb_riaggancia_fascicolo_target_ripulito tests/test_polisweb.py::test_route_importa_polisweb_sceglie_fascicolo_esistente_da_iddfa tests/test_polisweb.py::test_acquisizione_pst_collega_fascicolo_esistente_con_iddfa_specifico --tb=short
python -m pytest -q tests/test_fascicoli.py::test_aggiungi_documento_stesso_contenuto_nome_diverso_restano_distinti tests/test_fascicoli.py::test_aggiungi_documento_non_duplica_stesso_contenuto tests/test_fascicoli.py::test_riconcilia_documenti_duplicati_assorbe_record_e_riferimenti tests/test_fascicoli.py::test_riconcilia_documenti_duplicati_pdf_stesso_nome_conserva_versione --tb=short
python -m pytest -q tests/test_fascicoli.py::test_doppioni_fascicolo_ignora_controparte_nel_nome_cliente tests/test_fascicoli.py::test_aggiungi_documento_stesso_contenuto_nome_diverso_restano_distinti tests/test_fascicoli.py::test_aggiungi_documento_non_duplica_stesso_contenuto tests/test_fascicoli.py::test_riconcilia_documenti_duplicati_assorbe_record_e_riferimenti tests/test_fascicoli.py::test_riconcilia_documenti_duplicati_pdf_stesso_nome_conserva_versione --tb=short
python -m pytest -q tests/test_fascicoli.py::test_riconcilia_doppioni_cliente_rg_unisce_documenti_e_pagamenti tests/test_fascicoli.py::test_riconcilia_doppioni_cliente_rg_sql_salva_solo_record_coinvolti tests/test_fascicoli.py::test_doppioni_fascicolo_ignora_controparte_nel_nome_cliente tests/test_fascicoli.py::test_nuovo_blocca_doppione_cliente_rg tests/test_fascicoli.py::test_aggiorna_non_lascia_doppioni_cliente_rg --tb=short
python -m pytest -q tests/test_react_shell.py::test_react_fascicolo_lex_indexing_non_mostra_status_tecnici_o_date_brevi tests/test_fascicoli_pagination.py::test_fascicoli_api_filtra_rg_mancanti_da_card --tb=short
cd frontend; npm run typecheck
python -m ruff check --output-format=github --select E9,F63,F7,F82 scripts/audit_quickorganizer_import.py web/bootstrap/polisweb_routes.py tests/test_codeql_public_surface_regressions.py tests/test_polisweb.py
python -m ruff check pct/fascicoli.py tests/test_fascicoli.py scripts/reconcile_duplicate_fascicoli.py web/bootstrap/polisweb_routes.py scripts/audit_quickorganizer_import.py scripts/repair_fascicolo_document_duplicates.py
git diff --check
```

## Verifica reale

La verifica finale non può fermarsi ai test. Dopo commit, push e deploy, vanno controllati sul server:

- `/api/pronto` sul commit distribuito;
- import/sincronizzazione fascicolo senza creazione di duplicato quando il fascicolo esiste;
- assenza di documenti duplicati assorbibili nel tenant `studio-legale-giuseppe-montagnese`;
- visualizzazione dei documenti reali nel dettaglio fascicolo;
- tempi di caricamento della lista fascicoli e del dettaglio fascicolo.

Finché questi controlli server e UI non sono stati ripetuti dopo il deploy, il lavoro resta in verifica.
