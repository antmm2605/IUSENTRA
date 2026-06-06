# Guida Pratica KB completa v4 - IUSENTRA

## Stato consolidato 2.248.29

La v4 caricata dall'utente è stata applicata e completata sul catalogo ufficiale presente in repository, che contiene 1.018 record validi. I moduli TOP9 set2, set3, set4, set5, set6, set7, set8 e set9 sono stati integrati mantenendo separati codici ufficiali e schede interne.

## Numeri finali aggiornati al set33

- Moduli KB caricati: 104.
- Codici unificati nel KB full: 1.220.
- Record ufficiali nel catalogo PST/XSD: 1.018.
- Guide ufficiali curate: 1.018.
- Codici ufficiali senza guida curata: 0.
- Copertura finale: `{"curata": 1220}`.
- Schede interne o alias non depositabili: 202.
- Schede arricchite con fonti ufficiali web e presidi operativi integrativi: 1.220.
- Contaminazioni del codice deposito ufficiale rilevate dall'audit: 0.
- Termini Guida Pratica importati nello scadenziario: 3.567.
- Template scadenziario calcolabili da Guida Pratica: 1.119.

## Aggiornamento set33 - files (22).zip

Il pacchetto `files (22).zip` e' stato importato come otto moduli versionati:
`kb_98_set33_p1.json`, `kb_98_set33_p2.json`, `kb_98_set33_p3.json`,
`kb_98_set33_p4.json`, `kb_98_set33_p5.json`, `kb_98_set33_p6.json`,
`kb_98_set33_p7.json` e `kb_98_set33_p8.json`.

Risultato:

- 40 schede ricevute e integrate;
- 42 termini processuali grezzi estratti;
- 40 guide interne non depositabili perche' i codici ricevuti non coincidono
  con il catalogo PST/XSD locale;
- nessun codice ufficiale di deposito sostituito o contaminato;
- fonti web operative presenti in ogni scheda;
- Lex e UI leggono le schede tramite `GuidaPraticaService`,
  `GuidaPraticaSource` e pannello React;
- scadenziario rigenerato con 3.567 termini e 1.119 template calcolabili.

Report:

- `artifacts/guida-pratica/import-user-kb-2026-06-07-set33.json`;
- `artifacts/guida-pratica/kb-set33-structural-validation-report.json`;
- `artifacts/guida-pratica/termini-processuali-import-2026-06-07-set33.json`;
- `artifacts/guida-pratica/termini-processuali-import-2026-06-07-set33.csv`;
- `artifacts/guida-pratica/guida-pratica-user-material-field-audit-2026-06-07-set33.json`;
- `artifacts/guida-pratica/guida-pratica-user-material-field-audit-2026-06-07-set33.csv`;
- `artifacts/guida-pratica/guida-pratica-audit-2026-06-07-set33.json`;
- `artifacts/guida-pratica/codici-ufficiali-senza-guida-curata-2026-06-07-set33.csv`.

## Curation Codex del completamento automatico

Il modulo `kb_99_completamento_codici_ufficiali.json`, che inizialmente copriva 839 codici con profilo operativo automatico, è stato curato da Codex il 22 maggio 2026 con ricerca guidata da fonti ufficiali e profili per rito/materia.

Risultato:

- 839 schede trasformate in `curata_codex_fonti_ufficiali`;
- profili applicati: famiglia/minori, contenzioso ordinario, crisi d'impresa, impugnazioni, volontaria giurisdizione, lavoro/previdenza, cautelare, esecuzione, impresa/societario, monitorio, ATP e immigrazione/cittadinanza;
- ogni scheda conserva la Guida Pratica facoltativa, non blocca il fascicolo e legge cliente, parti, ufficio, oggetto, codice, valore, rito, fase, documenti, scadenze, note, preventivo, conferimento incarico e parcella quando presenti;
- Lex riceve contesto conversazionale tramite `guida_operativa_curata.lex_context`;
- i termini processuali sono stati reimportati nello scadenziario: 3.106 record, 975 template calcolabili e 2.017 presidi `manual_review`;
- l'audit voce per voce del 22 maggio 2026 controlla i file utente fino al set4: 36 schede, 724 righe campo e 612 voci effettivamente presenti nel materiale ricevuto, con 0 perse nel KB full, 0 perse nel servizio/API, 0 non supportate da UI e 0 non leggibili da Lex;
- i due moduli set7 del 23 maggio 2026 e i moduli set8/set9 del 24 maggio 2026 sono stati importati e validati; l'audit voce per voce Python include ora set1, set2, set3, set4, set5, set6, set7, set8 e set9, con presidio anche sulle sostituzioni scalar dei profili automatici e sui nuovi campi `fonti_verifica_web` e `presidi_operativi_integrativi`;
- l'arricchimento web centralizzato collega ogni scheda a fonti ufficiali o istituzionali pertinenti e le rende disponibili a servizio/API, UI Guida Pratica e Lex senza modificare il codice ufficiale del fascicolo.

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
- `artifacts/guida-pratica/kb-set5-parte1-import-report.json`;
- `artifacts/guida-pratica/kb-set5-parte2-import-report.json`;
- `artifacts/guida-pratica/kb-set5-structural-validation-report.json`.
- `artifacts/guida-pratica/kb-set6-parte1-import-report.json`;
- `artifacts/guida-pratica/kb-set6-parte2-import-report.json`;
- `artifacts/guida-pratica/kb-set6-structural-validation-report.json`.
- `artifacts/guida-pratica/kb-set7-parte1-import-report.json`;
- `artifacts/guida-pratica/kb-set7-parte2-import-report.json`;
- `artifacts/guida-pratica/kb-set7-structural-validation-report.json`;
- `artifacts/guida-pratica/termini-processuali-set7-dry-run-report.json`;
- `artifacts/guida-pratica/termini-processuali-set7-dry-run-audit.csv`.
- `artifacts/guida-pratica/kb-set7-8-9-import-summary.json`;
- `artifacts/guida-pratica/kb-set7-8-9-structural-validation-report.json`;
- `artifacts/guida-pratica/kb-set8-parte1-import-report.json`;
- `artifacts/guida-pratica/kb-set8-parte2-import-report.json`;
- `artifacts/guida-pratica/kb-set9-parte1-import-report.json`;
- `artifacts/guida-pratica/kb-set9-parte2-import-report.json`;
- `artifacts/guida-pratica/termini-processuali-set7-8-9-import-report.json`;
- `artifacts/guida-pratica/termini-processuali-set7-8-9-kb-audit.csv`;
- `artifacts/guida-pratica/guida-pratica-web-enrichment-audit.json`;
- `artifacts/guida-pratica/guida-pratica-web-enrichment-audit.csv`.
- `artifacts/guida-pratica/utf8-integrity-guida-pratica-2.248.29.json`.

## Audit voce per voce del materiale utente

Il controllo obbligatorio `scripts/audit_guida_pratica_user_material_fields.py` confronta i file ricevuti dall'utente con il software reale: modulo KB, KB full, `GuidaPraticaService`, pannello React e `GuidaPraticaSource` di Lex.

Risultato aggiornato al 24 maggio 2026:

- file controllati: `kb_98_top9_codici_frequenti_dettaglio_massimo.json`, `kb_98_top9_set2_parte1.json`, `kb_98_top9_set2_parte2.json`, `kb_98_top9_set3_parte1.json`, `kb_98_top9_set3_parte2.json`, `kb_98_top9_set4_parte1.json`, `kb_98_top9_set4_parte2.json`, `kb_98_top9_set5_parte1.json`, `kb_98_top9_set5_parte2.json`, `kb_98_top9_set6_parte1.json`, `kb_98_top9_set6_parte2.json`, `kb_98_top9_set7_parte1.json`, `kb_98_top9_set7_parte2.json`, `kb_98_top9_set8_parte1.json`, `kb_98_top9_set8_parte2.json`, `kb_98_top9_set9_parte1.json`, `kb_98_top9_set9_parte2.json`;
- 81 schede controllate;
- 1.805 righe di audit voce per voce;
- 1.413 voci effettivamente presenti nel materiale ricevuto e presidiate;
- audit voce per voce esteso ai moduli set7, set8 e set9;
- voci presenti nei file ricevuti preservate nel KB full e nella sorgente Lex;
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

Il set5 aggiunge cinque ulteriori guide interne non depositabili per codici assenti o non coincidenti con il catalogo locale:

- `GUIDA_REGOLAMENTO_CONFINI_130032`, ricevuta come `130032`;
- `GUIDA_IMPUGNAZIONE_TESTAMENTO_120020`, ricevuta come `120020`;
- `GUIDA_RESPONSABILITA_NOTAIO_COMMERCIALISTA_143003`, ricevuta come `143003`;
- `GUIDA_CONSUMATORE_CLAUSOLE_VESSATORIE_180001`, ricevuta come `180001`;
- `GUIDA_AZIONE_NEGATORIA_SERVITU_POSSESSORIA_130031`, ricevuta come `130031`.

Il set6 aggiunge otto ulteriori guide interne non depositabili e un codice ufficiale mantenuto depositabile:

- `GUIDA_PRELIMINARE_COMPRAVENDITA_2932_140002`, ricevuta come `140002`;
- `GUIDA_IMPUGNAZIONE_DELIBERE_ASSEMBLEARI_155001`, ricevuta come `155001`;
- `GUIDA_LICENZIAMENTO_DISCIPLINARE_220003`, ricevuta come `220003`;
- `GUIDA_OPPOSIZIONE_CARTELLA_ESATTORIALE_191001`, ricevuta come `191001`;
- `GUIDA_IMMISSIONI_INTOLLERABILI_130012`, ricevuta come `130012`;
- `GUIDA_EREDITA_GIACENTE_413021`, ricevuta come `413021`;
- `GUIDA_OPPOSIZIONE_SANZIONE_AMMINISTRATIVA_240001`, ricevuta come `240001`;
- `GUIDA_DEMANSIONAMENTO_DEQUALIFICAZIONE_220030`, ricevuta come `220030`;
- `111003`, mantenuto come codice ufficiale depositabile.

Il set7 aggiunge sette ulteriori guide interne non depositabili e due codici ufficiali mantenuti depositabili:

- `GUIDA_GARANZIA_VIZI_COSA_VENDUTA_140011`, ricevuta come `140011`;
- `GUIDA_RESPONSABILITA_COSE_CUSTODIA_160021`, ricevuta come `160021`;
- `GUIDA_DISTANZE_LEGALI_COSTRUZIONI_130011`, ricevuta come `130011`;
- `GUIDA_SCIOGLIMENTO_SOCIETA_PERSONE_211001`, ricevuta come `211001`;
- `GUIDA_TUTELA_MAGGIORE_GRAVE_HANDICAP_413051`, ricevuta come `413051`;
- `GUIDA_RISOLUZIONE_MUTUO_DECADENZA_TERMINE_142001`, ricevuta come `142001`;
- `GUIDA_OPPOSIZIONE_PRECETTO_199001`, ricevuta come `199001`;
- `011001` e `170001`, mantenuti come codici ufficiali depositabili.

I set8 e set9 aggiungono ulteriori schede civilistiche specialistiche, comprese esecuzioni, contratti bancari e assicurativi, proprietà industriale, lavoro, successioni, tutele cautelari e ADR. I codici ufficiali ricevuti e presenti nel catalogo locale restano codici depositabili; le schede non coincidenti con il catalogo sono conservate come guide interne facoltative e non contaminano `codice_oggetto_pst`.

Il CSV aggiornato non segnala più variazioni descrittive dei TOP9: le voci operative, i termini, gli allegati, gli adempimenti, le sezioni specialistiche e i valori scalar ricevuti sono conservati.

## Arricchimento web e collegamento UI/Lex

Dal 24 maggio 2026 ogni scheda restituita da `GuidaPraticaService` viene arricchita in modo centralizzato con:

- `fonti_verifica_web`: fonti ufficiali o istituzionali collegate alla materia, con URL, ambito e data di verifica;
- `presidi_operativi_integrativi`: indicazioni operative non bloccanti per deposito, termini, ADR, allegati, Lex, template e controlli di coerenza.

La UI Guida Pratica deve mostrare questo contesto senza diventare una pagina enorme:

- nella tab `Normativa`, sezione `Fonti ufficiali verificate`;
- nella tab `Contesto`, sezione `Presidi operativi integrativi`;
- sempre come supporto facoltativo, senza bloccare fascicolo, redazione atti o deposito.

Lex legge gli stessi campi tramite `GuidaPraticaSource` e li usa in modo conversazionale per l'avvocato, distinguendo fonti certe, presidi da verificare e limiti della scheda.

Le direttive normative e software usate dall'arricchimento sono versionate in `docs/specs/ministero/GUIDA_PRATICA_FONTI_WEB_E_DIRETTIVE_SOFTWARE.md`.

## Cosa cambia rispetto alla v3

- I moduli caricati restano separati dal codice applicativo.
- Il modulo di completamento `kb_99_completamento_codici_ufficiali.json` porta i codici ufficiali mancanti o parziali allo stesso formato operativo della Guida Pratica e ora contiene la curation Codex con fonti ufficiali e contesto Lex.
- Gli alias storici `ESEC_*`, `LAV_*` e le vecchie varianti interne restano utilizzabili come guida interna, ma non sono codici depositabili.
- Il validatore ora distingue catalogo ufficiale, knowledge base e alias interni: un codice è depositabile solo se presente nel catalogo PST/XSD ufficiale.
- Il dettaglio fascicolo React mostra la guida come pannello operativo facoltativo: se il fascicolo non ha codice, può suggerire una scheda dall'oggetto senza bloccare il lavoro.
- Il badge `Uso facoltativo` resta visibile anche quando la scheda è collegata, così l'avvocato capisce che la guida aiuta ma non ferma il fascicolo.
- Lex conosce la Guida Pratica tramite `GuidaPraticaSource`: legge la scheda completa come fonte interna conversazionale per aiutare l'avvocato su primo controllo, atto, campi, allegati, avvertimenti e termini, senza confonderla con il codice di deposito.
- Le fonti ufficiali web e i presidi operativi sono esposti allo stesso modo a servizio/API, UI e Lex; non restano nella chat o in log esterni.

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
10. Ogni arricchimento normativo o direttiva software usata dalla guida deve essere salvato in repository, citato nella scheda o nell'audit e verificabile da test.

## Comandi di controllo

```bash
python scripts\merge_legal_kb_modules.py
python scripts\validate_codici_oggetto_pst.py --min-records 1000
python scripts\verify_pst_xsd_catalog.py
python scripts\curate_codex_guida_pratica_completion.py --report artifacts\guida-pratica\codex-guida-pratica-curation-report.json --csv artifacts\guida-pratica\codex-guida-pratica-curation-audit.csv
python scripts\import_guida_pratica_termini_processuali.py --report artifacts\guida-pratica\termini-processuali-after-codex-curation-import-report.json --csv artifacts\guida-pratica\termini-processuali-after-codex-curation-audit.csv
python scripts\validate_guida_pratica.py --require-official-curated --fail-on-generated --report artifacts\guida-pratica\guida-pratica-audit.json --missing-guidance-csv artifacts\guida-pratica\codici-ufficiali-senza-guida-curata.csv
python scripts\audit_guida_pratica_user_material_fields.py --fail-on-loss --report artifacts\guida-pratica\guida-pratica-user-material-field-audit.json --csv artifacts\guida-pratica\guida-pratica-user-material-field-audit.csv
python scripts\audit_guida_pratica_web_enrichment.py --fail-on-missing --report artifacts\guida-pratica\guida-pratica-web-enrichment-audit.json --csv artifacts\guida-pratica\guida-pratica-web-enrichment-audit.csv
python -m pytest tests\test_guida_pratica_service.py tests\test_guida_pratica_api.py tests\test_import_pst_xsd_codici_oggetto.py tests\test_pst_xsd_catalog_importer.py tests\test_codici_oggetto_pst_catalog.py -q --tb=short
python -m pytest lex\tests\unit\test_guida_pratica_source.py -q --tb=short
pnpm --filter @iusentra/studio typecheck
pnpm --filter @iusentra/studio build
```
