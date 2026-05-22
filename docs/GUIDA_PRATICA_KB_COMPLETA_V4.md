# Guida Pratica KB completa v4 - IUSENTRA

## Stato consolidato 2.248.11

La v4 caricata dall'utente è stata applicata e completata sul catalogo ufficiale presente in repository, che contiene 1.018 record validi. I moduli TOP9 set2, set3 e set4 parte 1 e parte 2 sono stati integrati mantenendo separati codici ufficiali e schede interne.

## Numeri finali

- Moduli KB caricati: 26.
- Codici unificati nel KB full: 1.067.
- Record ufficiali nel catalogo PST/XSD: 1.018.
- Guide ufficiali curate: 1.018.
- Codici ufficiali senza guida curata: 0.
- Copertura finale: `{"curata": 1067}`.
- Schede interne o alias non depositabili: 49.

## Curation Codex del completamento automatico

Il modulo `kb_99_completamento_codici_ufficiali.json`, che inizialmente copriva 839 codici con profilo operativo automatico, è stato curato da Codex il 22 maggio 2026 con ricerca guidata da fonti ufficiali e profili per rito/materia.

Risultato:

- 839 schede trasformate in `curata_codex_fonti_ufficiali`;
- profili applicati: famiglia/minori, contenzioso ordinario, crisi d'impresa, impugnazioni, volontaria giurisdizione, lavoro/previdenza, cautelare, esecuzione, impresa/societario, monitorio, ATP e immigrazione/cittadinanza;
- ogni scheda conserva la Guida Pratica facoltativa, non blocca il fascicolo e legge cliente, parti, ufficio, oggetto, codice, valore, rito, fase, documenti, scadenze, note, preventivo, conferimento incarico e parcella quando presenti;
- Lex riceve contesto conversazionale tramite `guida_operativa_curata.lex_context`;
- i termini processuali sono stati reimportati nello scadenziario: 2.895 record, 832 template calcolabili e 2.017 presidi `manual_review`.
- l'audit voce per voce sui file utente controlla 36 schede, 724 righe campo e 612 voci effettivamente presenti nel materiale ricevuto: 0 perse nel KB full, 0 perse nel servizio/API, 0 non supportate da UI e 0 non leggibili da Lex.

Report:

- `artifacts/guida-pratica/codex-guida-pratica-curation-report.json`;
- `artifacts/guida-pratica/codex-guida-pratica-curation-audit.csv`;
- `artifacts/guida-pratica/termini-processuali-after-codex-curation-import-report.json`;
- `artifacts/guida-pratica/termini-processuali-after-codex-curation-audit.csv`.
- `artifacts/guida-pratica/guida-pratica-user-material-field-audit.json`;
- `artifacts/guida-pratica/guida-pratica-user-material-field-audit.csv`.
- `artifacts/guida-pratica/kb-set4-parte2-import-report.json`;
- `artifacts/guida-pratica/termini-processuali-set4-parte2-import-report.json`;
- `artifacts/guida-pratica/termini-processuali-set4-parte2-kb-audit.csv`.

## Audit voce per voce del materiale utente

Il controllo obbligatorio `scripts/audit_guida_pratica_user_material_fields.py` confronta i file ricevuti dall'utente con il software reale: modulo KB, KB full, `GuidaPraticaService`, pannello React e `GuidaPraticaSource` di Lex.

Risultato al 22 maggio 2026:

- file controllati: `kb_98_top9_codici_frequenti_dettaglio_massimo.json`, `kb_98_top9_set2_parte1.json`, `kb_98_top9_set2_parte2.json`, `kb_98_top9_set3_parte1.json`, `kb_98_top9_set3_parte2.json`, `kb_98_top9_set4_parte1.json`, `kb_98_top9_set4_parte2.json`;
- 36 schede controllate;
- 724 righe di audit;
- 612 voci presenti nei file ricevuti;
- 0 voci presenti nel materiale utente perse nel KB completo;
- 0 voci presenti nel materiale utente perse nel servizio/API;
- 0 voci presenti nel materiale utente non supportate dalla UI della Guida Pratica;
- 0 voci presenti nel materiale utente non leggibili da Lex.

Sette schede con codice numerico non coerente con la descrizione ministeriale locale sono state conservate come guide interne non depositabili, per non contaminare il catalogo ufficiale di deposito:

- `GUIDA_ONORARI_PROFESSIONALI_L794`, ricevuta come `141001`;
- `GUIDA_ADS_MODIFICA_REVOCA_413062`, ricevuta come `413062`;
- `GUIDA_RECESSO_SOCIO_SRL_150003`, ricevuta come `150003`;
- `GUIDA_RISOLUZIONE_APPALTO_140001`, ricevuta come `140001`;
- `GUIDA_RICONOSCIMENTO_PATERNITA_MATERNITA_111007`, ricevuta come `111007`;
- `GUIDA_ESCLUSIONE_SOCIO_SOCIETA_PERSONE_150010`, ricevuta come `150010`;
- `GUIDA_VIOLAZIONE_MARCHIO_BREVETTO_170011`, ricevuta come `170011`.

Nel CSV restano segnalate solo variazioni descrittive compatibili con il catalogo ufficiale locale per `111021`, `620001` e la competenza di `100011`; le voci operative, i termini, gli allegati, gli adempimenti e le sezioni specialistiche sono conservati.

## Cosa cambia rispetto alla v3

- I moduli caricati restano separati dal codice applicativo.
- Il modulo di completamento `kb_99_completamento_codici_ufficiali.json` porta i codici ufficiali mancanti o parziali allo stesso formato operativo della Guida Pratica e ora contiene la curation Codex con fonti ufficiali e contesto Lex.
- Gli alias storici `ESEC_*`, `LAV_*` e le vecchie varianti interne restano utilizzabili come guida interna, ma non sono codici depositabili.
- Il validatore ora distingue catalogo ufficiale, knowledge base e alias interni: un codice è depositabile solo se presente nel catalogo PST/XSD ufficiale.
- Il dettaglio fascicolo React mostra la guida come pannello operativo facoltativo: se il fascicolo non ha codice, può suggerire una scheda dall'oggetto senza bloccare il lavoro.
- Il badge `Uso facoltativo` resta visibile anche quando la scheda è collegata, così l'avvocato capisce che la guida aiuta ma non ferma il fascicolo.
- Lex conosce la Guida Pratica tramite `GuidaPraticaSource`: legge la scheda completa come fonte interna conversazionale per aiutare l'avvocato su primo controllo, atto, campi, allegati, avvertimenti e termini, senza confonderla con il codice di deposito.

## Regole operative confermate

1. I codici ufficiali di deposito vengono solo dal catalogo ministeriale PST/XSD caricato.
2. Il codice che apre il fascicolo resta sempre il codice ufficiale/normativo depositabile scelto nel fascicolo.
3. La Guida Pratica si aggancia alla stessa materia del fascicolo, ma non sostituisce mai il codice oggetto PST/XSD del fascicolo.
4. Se una scheda guida usa un alias interno o un identificativo non depositabile, quell'alias serve solo a recuperare la guida: il deposito usa sempre il codice ufficiale del fascicolo.
5. Ogni codice ufficiale deve avere guida curata prima del rilascio.
6. Gli alias interni non bloccano la consultazione, ma non possono essere usati come codice deposito.
7. La guida è supporto operativo per l'avvocato e deve restare dettagliata, leggibile e non tecnica.
8. Il validatore `--require-official-curated --fail-on-generated` è il gate obbligatorio.
9. Ogni nuova guida curata deve arricchire anche Lex: la conoscenza pratica va resa interrogabile in chat con tono conversazionale per l'avvocato.

## Comandi di controllo

```bash
python scripts\merge_legal_kb_modules.py
python scripts\validate_codici_oggetto_pst.py --min-records 1000
python scripts\verify_pst_xsd_catalog.py
python scripts\curate_codex_guida_pratica_completion.py --report artifacts\guida-pratica\codex-guida-pratica-curation-report.json --csv artifacts\guida-pratica\codex-guida-pratica-curation-audit.csv
python scripts\import_guida_pratica_termini_processuali.py --report artifacts\guida-pratica\termini-processuali-after-codex-curation-import-report.json --csv artifacts\guida-pratica\termini-processuali-after-codex-curation-audit.csv
python scripts\validate_guida_pratica.py --require-official-curated --fail-on-generated --report artifacts\guida-pratica\guida-pratica-audit.json --missing-guidance-csv artifacts\guida-pratica\codici-ufficiali-senza-guida-curata.csv
python scripts\audit_guida_pratica_user_material_fields.py --fail-on-loss --report artifacts\guida-pratica\guida-pratica-user-material-field-audit.json --csv artifacts\guida-pratica\guida-pratica-user-material-field-audit.csv
python -m pytest tests\test_guida_pratica_service.py tests\test_guida_pratica_api.py tests\test_import_pst_xsd_codici_oggetto.py tests\test_pst_xsd_catalog_importer.py tests\test_codici_oggetto_pst_catalog.py -q --tb=short
python -m pytest lex\tests\unit\test_guida_pratica_source.py -q --tb=short
pnpm --filter @iusentra/studio typecheck
pnpm --filter @iusentra/studio build
```
