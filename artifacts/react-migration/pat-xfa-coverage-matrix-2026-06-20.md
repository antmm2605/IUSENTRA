# Matrice copertura XFA PAT/SIGA - 2026-06-20

Stato: analisi preliminare, non autorizza ancora dichiarazione di copertura 100%.

Obiettivo: verificare, prima di nuovo sviluppo, se IUSENTRA può compilare i moduli ministeriali PAT usando i PDF XFA originali e solo i campi obbligatori o obbligatori condizionati dalle scelte del modulo.

Fonti usate:

- pagina ufficiale Giustizia Amministrativa `Documentazione operativa, modulistica e manualistica`, sezione `Moduli 4.x aggiornati al 7/07/2025`;
- `PAT Istruzioni per Compilazione Moduli Deposito v9.6.1`, aggiornato al 4 giugno 2025;
- PDF ufficiali locali in `pct/data/pat_moduli/`;
- prova tecnica XFA in `tmp/pdfs/pat_all_fields_probe/`;
- prova Acrobat singolo campo: `tmp/pdfs/PROVA_CAMPO_MODULO_PAT_RICORSO.pdf`, confermata dall'utente con "primo campo arrivato".

Legenda prove:

- `OK Acrobat singolo`: campo visto in Acrobat Reader nella prova reale confermata dall'utente.
- `OK XFA`: valore presente nel pacchetto XFA generato da IUSENTRA; manca ancora conferma visiva Acrobat per quel campo.
- `Parziale`: percorso XFA trovato, ma oggi manca struttura dati completa, righe ripetibili, allegato reale o controllo visivo.
- `Non coperto`: campo obbligatorio/condizionato non ancora esposto o non ancora compilato da IUSENTRA.

## Gap bloccanti prima di dire "100%"

1. IUSENTRA oggi prova davvero un solo campo in Acrobat (`oggetto` ricorso). Tutti gli altri campi sono al massimo `OK XFA`, non `OK Acrobat`.
2. Le righe `Aggiungi` non sono ancora coperte al 100%: parti, documenti, procure, notifiche, atti impugnati, CIG e versamenti richiedono array ordinati, non una stringa unica.
3. Gli allegati oggi risultano soprattutto come nome file nei campi XFA; la matrice 100% deve distinguere nome allegato, file selezionato dal fascicolo, hash, firma e caricamento finale Formweb.
4. Difensori, dati studio, PNRR, istanze, appalti/CIG, atti impugnati, contributo versato e rimborso hanno campi obbligatori o obbligatori condizionati non ancora esposti in modo completo.
5. Il dato DB esiste solo in parte: `fascicoli`, `clienti`, `soggetti_parti`, `telematic_cases` e `telematic_documents` coprono molti campi, ma serve una struttura PAT dedicata per scelte modulo, istanze, versamenti e righe ripetibili.

## Deposito ricorso 4.02

| Modulo | Campo obbligatorio | Percorso XFA | Campo IUSENTRA | Dato DB | Prova PDF | Prova visiva Acrobat |
|---|---|---|---|---|---|---|
| Ricorso 4.02 | Sede | `template.ricorso.subform.selectSede` | `sede` | `fascicoli.tribunale`, `telematic_cases.office_name` | OK XFA (`tar_rm`) | Non ancora campo per campo |
| Ricorso 4.02 | Tipo ricorso | `...tableRicorso.rigaRicorso.subFormTipoRicorso.tipoRicorsoTar/Cds` | `tipo_ricorso` | `fascicoli.tipo_procedimento`, `profilo_deposito_json` | OK XFA | Non ancora |
| Ricorso 4.02 | Allegato ricorso | `...tableRicorso.rigaRicorso.txtAllegatoRicorso` | documento ruolo `ricorso` | `fascicoli.documenti_json`, `telematic_documents.document_role` | Parziale: nome file scritto | Non ancora; file reale da verificare |
| Ricorso 4.02 | PNRR obbligatorio | `...subFormPNRR.finanziamentoPNRR` | da esporre | DB mancante dedicato | Parziale: default `Z` | Non ancora |
| Ricorso 4.02 | Appalti: valore/CIG se rito appalti | `...subFormRitoAppalti.valoreAppalto`, `...tableCig.rigaCig.cig`, `...noCig` | da esporre condizionato | DB mancante dedicato | Non coperto | Non ancora |
| Ricorso 4.02 | Ricorrenti e tipo parte | `...subFormRicorrente.rbTipoRicorrente.*`, `...tableRicorrente.rigaRicorrente[*].subFormCella.*` | `ricorrente`, parti | `clienti`, `soggetti`, `soggetti_parti`, `fascicoli.nome_cliente` | OK XFA prima riga | Non ancora |
| Ricorso 4.02 | Difensori | `...tableDifensori.rigaDifensore[*].cognome/nome/codiceFiscale/pec`, `cassazionista`, `antistatarioDifensore` | da profilo studio/utente | DB utente/studio da mappare | Non coperto sui dati anagrafici | Non ancora |
| Ricorso 4.02 | Resistente/controinteressato | `...subFormResistente.rbTipoResistente.*`, `...tableResistente.rigaResistente[*].subFormCella.*`, `controinteressatoAssente` | `resistente` | `fascicoli.controparte`, `cf_controparte`, `soggetti_parti` | OK XFA prima riga | Non ancora |
| Ricorso 4.02 | Provvedimento impugnato se presente | `...tableProvvedimentoImpugnato...notifica`, allegato provvedimento | da esporre | DB mancante dedicato | Non coperto | Non ancora |
| Ricorso 4.02 | Atti impugnati se impugnazione | `...SubformAttiImpugnati.nonImpugnato`, `...tableAttiImpugnati.rigaAttoImpugnato[*].textFieldAutorita/listTipoAtto/numeroAtto/annoAtto` | da esporre | DB mancante dedicato | Parziale: solo default/codice | Non ancora |
| Ricorso 4.02 | Oggetto sintetico/esteso | `...tableOggetto.rigaOggetto.oggetto`, `...tableOggettoEsteso.rigaOggetto.oggettoEsteso` | `oggetto` | `fascicoli.oggetto`, `telematic_cases.notes/act_subject` | OK XFA | OK Acrobat singolo su prova oggetto |
| Ricorso 4.02 | Istanze Si/No/Non valorizzato | `...tableIstanze.*` | da esporre come check/radio | DB mancante dedicato | Parziale: default presenti | Non ancora |
| Ricorso 4.02 | Istanze ante causam collegate se selezionate | `...tableIstanzeAntecausam.*.checkBox*`, `agid*` | da esporre condizionato | DB mancante dedicato | Non coperto | Non ancora |
| Ricorso 4.02 | Elenco documenti/foliario | `...tableIndiceDocumenti.rigaDocumenti[*].descrizione/txtAllegatoIndice` | documenti selezionati | `fascicoli.documenti_json`, `telematic_documents` | Parziale: nome file | Non ancora; file reale da verificare |
| Ricorso 4.02 | Procura se richiesta | `...tableProcura.rigaProcura[*].parteProcura/difensoreProcura/dateProcura/procuraAttoIntroduttivo/txtAllegatoProcura` | documenti ruolo `procura` + data | `fascicoli.documenti_json`, campo data mancante | Parziale: nome file | Non ancora |
| Ricorso 4.02 | Notifica se richiesta | `...tableRelazione.rigaRelazione[*].parteNotificata/dateNotifica/dateRicezioneNotifica/txtModalita/txtAllegatoRelazione` | documenti ruolo `notifica/relata` | `fascicoli.documenti_json`, dati notifica mancanti | Parziale: nome file | Non ancora |
| Ricorso 4.02 | Contributo unificato | `...subFormContributo.rbContributo.*` | `contributo_unificato` | DB pagamenti/profilo da mappare | OK XFA stato base | Non ancora |
| Ricorso 4.02 | Versamento se pagato | `...tableContributo.rigaVersamento[*].dataVersamento/listModalitaVersamento/txtEstremiVersamento/txtImportoVersato/txtAllegatoVersamento` | da esporre strutturato | `fascicoli.pagamenti`, DB mancante per righe CU | Parziale: allegato; dati mancanti | Non ancora |

## Deposito atto 4.02

| Modulo | Campo obbligatorio | Percorso XFA | Campo IUSENTRA | Dato DB | Prova PDF | Prova visiva Acrobat |
|---|---|---|---|---|---|---|
| Atto 4.02 | Sede | `template.ricorso.subform.selectSede` | `sede` | `fascicoli.tribunale` | OK XFA | Non ancora |
| Atto 4.02 | NRG e anno | `...subFormRicorso.numeroRicorso`, `...annoRicorso` | `nrg`, `anno_rg` | `fascicoli.numero_rg`, `fascicoli.anno_rg` | OK XFA | Non ancora |
| Atto 4.02 | Tipo atto | `...tableAtti.rigaAtto.tipoAtto` | `tipologia_atto` | `profilo_deposito_json`, dato PAT dedicato mancante | OK XFA | Non ancora |
| Atto 4.02 | Allegato atto | `...tableAtti.rigaAtto.txtAllegatoAtto` | documento ruolo `atto_principale` | `fascicoli.documenti_json`, `telematic_documents` | Parziale: nome file | Non ancora |
| Atto 4.02 | PNRR | `...subFormPNRR.finanziamentoPNRR` | da esporre | DB mancante dedicato | Parziale: default | Non ancora |
| Atto 4.02 | Parti depositanti se non tutte le parti difese | `checkBoxTutteLePartiDifese`, `...tableRicorrente.rigaRicorrente[*].*` | selezione parti | `soggetti_parti`, `clienti`, `fascicoli.nome_cliente` | Parziale: prima riga | Non ancora |
| Atto 4.02 | Difensori | `...tableDifensori.rigaDifensore[*].*` | da profilo studio/utente | DB utente/studio da mappare | Non coperto sui dati anagrafici | Non ancora |
| Atto 4.02 | Oggetto/descrizione | `...tableOggettoEsteso.rigaOggetto.oggettoEsteso` | `oggetto` | `fascicoli.oggetto` | OK XFA | Non ancora |
| Atto 4.02 | Istanze Si/No | `...tableIstanze.*` | da esporre | DB mancante dedicato | Parziale: default | Non ancora |
| Atto 4.02 | Atti impugnati se nuova domanda/provvedimento | `...SubformAttiImpugnati.nonImpugnato`, `...tableAttiImpugnati.rigaAttoImpugnato[*].textFieldAutorita/listTipoAtto/numeroAtto/annoAtto` | da esporre condizionato | DB mancante dedicato | Parziale/non coperto | Non ancora |
| Atto 4.02 | Elenco documenti | `...tableIndiceDocumenti.rigaDocumenti[*].descrizione/txtAllegatoIndice` | documenti selezionati | `fascicoli.documenti_json`, `telematic_documents` | Parziale: nome file | Non ancora |
| Atto 4.02 | Procura/notifica/contributo se richiesti | `...tableProcura.*`, `...tableRelazione.*`, `...tableContributo.*` | ruoli documentali + dati | DB parziale | Parziale | Non ancora |

## Richieste segreteria 4.01

| Modulo | Campo obbligatorio | Percorso XFA | Campo IUSENTRA | Dato DB | Prova PDF | Prova visiva Acrobat |
|---|---|---|---|---|---|---|
| Richieste 4.01 | Sede | `template.ricorso.subform.selectSede` | `sede` | `fascicoli.tribunale` | OK XFA | Non ancora |
| Richieste 4.01 | NRG e anno | `...subFormRicorso.numeroRicorso`, `...annoRicorso` | oggi non esposto bene per questo modulo | `fascicoli.numero_rg`, `anno_rg` | Non coperto nel probe reale | Non ancora |
| Richieste 4.01 | Tipologia richiesta | `...tableAtti.rigaAtto.tipoAtto` | `tipo_richiesta` | DB PAT dedicato mancante | Non coperto dal mapper attuale | Non ancora |
| Richieste 4.01 | Allegato richiesta | `...tableAtti.rigaAtto.txtAllegatoAtto` | documento ruolo `istanza/richiesta` | `fascicoli.documenti_json` | Parziale: nome file | Non ancora |
| Richieste 4.01 | Elenco documenti | `...tableIndiceDocumenti.rigaDocumenti[*].descrizione/txtAllegatoIndice` | documenti selezionati | `fascicoli.documenti_json`, `telematic_documents` | Parziale | Non ancora |
| Richieste 4.01 | Parti depositanti se richieste | `...tableRicorrente.rigaRicorrente[*].*` | parti | `soggetti_parti`, `clienti` | Non coperto sui dati | Non ancora |
| Richieste 4.01 | Oggetto/dettaglio | `...tableOggettoEsteso.rigaOggetto.oggettoEsteso` | `dettaglio_richiesta`/`oggetto` | `fascicoli.oggetto`, DB PAT dedicato mancante | OK XFA generico | Non ancora |

## Ausiliari del giudice e parti non rituali 4.01

| Modulo | Campo obbligatorio | Percorso XFA | Campo IUSENTRA | Dato DB | Prova PDF | Prova visiva Acrobat |
|---|---|---|---|---|---|---|
| Ausiliari 4.01 | Sede | `template.ricorso.subform.selectSede` | `sede` | `fascicoli.tribunale` | OK XFA | Non ancora |
| Ausiliari 4.01 | NRG e anno | `...subFormRicorso.numeroRicorso`, `...annoRicorso` | `nrg`, `anno_rg` | `fascicoli.numero_rg`, `anno_rg` | OK XFA | Non ancora |
| Ausiliari 4.01 | Qualifica depositante | `...subFormRicorso.tipoDepositante` | `qualifica_depositante` | `soggetti.qualifica`, DB PAT dedicato mancante | OK XFA | Non ancora |
| Ausiliari 4.01 | Tipo atto e allegato | `...tableAtti.rigaAtto.tipoAtto/txtAllegatoAtto` | `descrizione_deposito`, documento ruolo `atto/relazione` | `fascicoli.documenti_json` | Parziale: tipo atto non sempre compilato | Non ancora |
| Ausiliari 4.01 | Depositante | `...subFormRicorrente.cognome/nome/codiceFiscale` oppure `...subFormParteAmministrazione.denominazione/codiceFiscale` | `parte_depositante` | `soggetti`, `soggetti_parti` | OK XFA prima riga | Non ancora |
| Ausiliari 4.01 | Oggetto deposito | `...tableOggettoEsteso.rigaOggetto.oggettoEsteso` | `descrizione_deposito`/`oggetto` | `fascicoli.oggetto`, DB PAT dedicato mancante | OK XFA | Non ancora |
| Ausiliari 4.01 | Elenco documenti | `...tableIndiceDocumenti.rigaDocumenti[*].descrizione/txtAllegatoIndice` | documenti selezionati | `fascicoli.documenti_json`, `telematic_documents` | Parziale | Non ancora |

## Istanza ante causam 4.01

| Modulo | Campo obbligatorio | Percorso XFA | Campo IUSENTRA | Dato DB | Prova PDF | Prova visiva Acrobat |
|---|---|---|---|---|---|---|
| Istanza 4.01 | Sede | `template.ricorso.subform.selectSede` | `sede` | `fascicoli.tribunale` | OK XFA | Non ancora |
| Istanza 4.01 | Tipo istanza | `...tableRicorso.rigaRicorso.subFormTipoRicorso.tipoRicorsoTar/Cds` | `tipo_ricorso` o tipo istanza | DB PAT dedicato mancante | OK XFA | Non ancora |
| Istanza 4.01 | Allegato istanza | `...tableRicorso.rigaRicorso.txtAllegatoRicorso` | documento ruolo `istanza` | `fascicoli.documenti_json` | Parziale: nome file | Non ancora |
| Istanza 4.01 | Istante | `...tableRicorrente.rigaRicorrente[*].subFormCella.*` | `istante` | `clienti`, `soggetti_parti` | OK XFA prima riga | Non ancora |
| Istanza 4.01 | Amministrazione resistente | `...tableResistente.rigaResistente[*].subFormCella.*` | `amministrazione_resistente` | `fascicoli.controparte`, `soggetti_parti` | OK XFA prima riga | Non ancora |
| Istanza 4.01 | Oggetto e ragioni urgenza | `...tableOggetto.rigaOggetto.oggetto`, `...tableOggettoEsteso.rigaOggetto.oggettoEsteso` | `oggetto`, `ragioni_urgenza` | `fascicoli.oggetto`, DB PAT dedicato mancante | OK XFA | Non ancora |
| Istanza 4.01 | Istanze/check specifiche | `...tableIstanze.*` | da esporre | DB mancante dedicato | Parziale: default `N` | Non ancora |
| Istanza 4.01 | Procura/documenti se richiesti | `...tableProcura.*`, `...tableIndiceDocumenti.*` | documenti selezionati | `fascicoli.documenti_json` | Parziale | Non ancora |
| Istanza 4.01 | TAR provenienza se ordinanza competenza | campi TAR provenienza nel modulo | da esporre condizionato | DB mancante dedicato | Non coperto | Non ancora |

## Rimborso contributo unificato 4.01 2026

| Modulo | Campo obbligatorio | Percorso XFA | Campo IUSENTRA | Dato DB | Prova PDF | Prova visiva Acrobat |
|---|---|---|---|---|---|---|
| Rimborso 4.01 2026 | Sede | `template.form1.Page1.selectSede` | `sede` | `fascicoli.tribunale` | OK XFA | Non ancora |
| Rimborso 4.01 2026 | Riferimento ricorso o non iscritto | `...subFormRicorso.numeroRicorso/annoRicorso/checkBoxRicorsoNonIscritto` | `nrg`, `anno_rg`, flag non iscritto da esporre | `fascicoli.numero_rg`, `anno_rg`; flag mancante | Parziale | Non ancora |
| Rimborso 4.01 2026 | Tipo ricorso/atto e anno/numero atto | `...subFormRicorso.tfAnnoAtto/tfNumeroAtto` | da esporre | DB PAT dedicato mancante | Non coperto | Non ancora |
| Rimborso 4.01 2026 | Allegato richiesta | `...tableRichieste.rigaAtto.txtAllegatoAtto` | documento ruolo `richiesta_rimborso` | `fascicoli.documenti_json` | Parziale: nome file | Non ancora |
| Rimborso 4.01 2026 | Parte depositante/richiedente | `...subFormRbParteDepositante.parteDepositante`, `...subFormPersonaFisica.*`, `...subFormPersonaGiuridica.*`, `...subFormAmministrazione.*` | `richiedente` | `clienti`, `soggetti`, `soggetti_parti` | Parziale: PF/PG scritti insieme | Non ancora |
| Rimborso 4.01 2026 | Versamento | `...Page2.subFormVersamento.ModalitaVersamento/dataVersamento/tfImportoVersamento/tfEstremiVersamento` | `dati_pagamento` oggi troppo generico | DB pagamenti/PAT dedicato mancante | Parziale: solo estremi/modalita | Non ancora |
| Rimborso 4.01 2026 | Importo richiesto | `...Page2.subFormRichiesta.tfImportoRichiesto` | da esporre | DB PAT dedicato mancante | Non coperto | Non ancora |
| Rimborso 4.01 2026 | Totale/parziale | `...Page2.subFormRichiesta.totaleParziale` | da esporre | DB PAT dedicato mancante | Non coperto | Non ancora |
| Rimborso 4.01 2026 | Metodo rimborso e IBAN | `...Page2.subFormRichiesta.modalitaRimborso/tfIban` | `iban`, metodo da esporre | DB PAT dedicato mancante | Parziale: IBAN | Non ancora |
| Rimborso 4.01 2026 | Motivazione | `...Page2.subFormMotivazioneNote.motivazioneRichiesta` | `motivo_rimborso` | DB PAT dedicato mancante | OK XFA | Non ancora |
| Rimborso 4.01 2026 | Documenti contabili | `...tableElencoDocumenti.rigaAtto.txtAllegatoAtto` | documenti selezionati | `fascicoli.documenti_json`, `telematic_documents` | Parziale | Non ancora |

## Struttura dati minima necessaria

La struttura esistente da riusare:

- `fascicoli`: `tribunale`, `numero_rg`, `anno_rg`, `nome_cliente`, `controparte`, `cf_controparte`, `oggetto`, `documenti_json`, `pagamenti`, `profilo_deposito_json`;
- `clienti`: persona fisica/giuridica, nome, cognome, ragione sociale, codice fiscale, partita IVA, email/PEC dentro `dati_json`;
- `soggetti` e `soggetti_parti`: ruoli processuali, co-clienti, controparti, CTU/ausiliari, amministrazioni;
- `telematic_cases`: caso PAT/SIGA collegato al fascicolo;
- `telematic_documents`: documenti importati o preparati per il deposito;
- `pat_deposits`: deposito PAT collegato al caso telematico.

Struttura PAT da aggiungere solo dopo approvazione della matrice:

- `pat_module_form_data`: modulo, versione, tipo deposito, sede, scelte PNRR/appalti/istanze, stato validazione;
- `pat_module_parties`: righe ripetibili parte, tipo parte, ruolo, CF/PIVA, PEC, origine DB;
- `pat_module_documents`: righe ripetibili documenti, ruolo PAT, id documento fascicolo, nome, hash, firma, obbligatorietà;
- `pat_module_payments`: righe versamento CU/rimborso, importo, data, estremi, allegato, stato;
- `pat_module_notifications`: notifiche, parte notificata, modalità, date, allegato;
- `pat_module_impugned_acts`: autorità, tipo, numero, anno, flag non conosciuto.

## Esito

Conferma tecnica attuale:

- si può compilare un campo XFA del modulo ministeriale originale;
- il campo `oggetto` del ricorso è stato visto in Acrobat;
- i template ufficiali XFA sono presenti e leggibili.

Conferma che non posso ancora dare:

- non posso dire copertura 100%;
- non posso dire che tutti i campi obbligatori arrivano al modulo;
- non posso dire che i PDF prodotti sono conformi campo per campo finché non esiste una prova Acrobat per tutte le righe obbligatorie e condizionate.

Prossimo passo possibile, solo dopo approvazione dell'utente: implementare la struttura dati PAT, esporre solo i campi obbligatori/condizionati, scrivere test XFA per ogni percorso della matrice, generare un PDF per modulo e fare prova visiva Acrobat campo per campo.
