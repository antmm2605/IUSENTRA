# Presidio processuale: ricerche, fonti e backlog

Data: 07/07/2026.

Obiettivo operativo: evitare ricerche ripetute e costruire una base unica per classificare i documenti del fascicolo prima di estrarre dati, scadenze e valori economici. Il presidio deve leggere il contenuto dei documenti, non fidarsi del nome file, e deve avviare parser mirati in base alla classe del documento.

## Metodo

Il motore deve lavorare in quattro passaggi:

1. Identifica il fascicolo: RG, anno, parti, cliente, ufficio, rito, registro, numero interno, collegamento PEC/documento.
2. Classifica il documento: provvedimento, udienza, ricevuta, notifica, deposito, pagamento, esenzione, sentenza, gratuito patrocinio, documento fiscale, documento cliente.
3. Estrae solo i dati pertinenti alla classe: data udienza, termine note, importo contributo, IUV, esito pagoPA, liquidazione, compensazione, distrazione, avviso PEC, ricevuta, termine costituzione, termine impugnazione.
4. Produce azione per l'avvocato: cosa fare oggi, cosa verificare, cosa depositare, cosa emettere, cosa archiviare, cosa non registrare automaticamente senza controllo.

## Fonti ufficiali già raccolte

### Civile ordinario e riti collegati

Fonti:

- Gazzetta Ufficiale, art. 127-ter c.p.c. e riforma Cartabia: https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticolo?art.codiceRedazionale=22G00158&art.dataPubblicazioneGazzetta=2022-10-17&art.flagTipoArticolo=0&art.idArticolo=3&art.idGruppo=2&art.idSottoArticolo=1&art.idSottoArticolo1=10&art.progressivo=1&art.versione=1
- Gazzetta Ufficiale, art. 133 c.p.c.: https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticolo?art.codiceRedazionale=040U1443&art.dataPubblicazioneGazzetta=1940-10-28&art.flagTipoArticolo=1&art.idArticolo=133&art.idGruppo=20&art.idSottoArticolo=1&art.idSottoArticolo1=10&art.progressivo=0&art.versione=4
- Gazzetta Ufficiale, art. 91 c.p.c.: https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticolo?art.codiceRedazionale=040U1443&art.dataPubblicazioneGazzetta=1940-10-28&art.flagTipoArticolo=1&art.idArticolo=91&art.idGruppo=15&art.idSottoArticolo=1&art.idSottoArticolo1=10&art.progressivo=0&art.versione=3
- Gazzetta Ufficiale, art. 543 c.p.c.: https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticolo?art.codiceRedazionale=040U1443&art.dataPubblicazioneGazzetta=1940-10-28&art.flagTipoArticolo=1&art.idArticolo=543&art.idGruppo=92&art.idSottoArticolo=1&art.idSottoArticolo1=10&art.progressivo=0&art.versione=8
- Gazzetta Ufficiale, artt. 669-sexies e 669-terdecies c.p.c.: https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticolo?art.codiceRedazionale=094A7751&art.dataPubblicazioneGazzetta=1994-12-09&art.flagTipoArticolo=0&art.idArticolo=4&art.idGruppo=0&art.idSottoArticolo=1&art.idSottoArticolo1=10&art.progressivo=0&art.versione=1

Chiavi da presidiare:

- `127-bis`, `collegamento audiovisivo`, `udienza da remoto`, `stanza virtuale`, `richiesta udienza in presenza`, `5 giorni dalla comunicazione`.
- `127-ter`, `note scritte`, `sostituzione dell'udienza`, `sole istanze e conclusioni`, `termine perentorio`, `opposizione`, `5 giorni dalla comunicazione`, `15 giorni`.
- `171-bis`, `verifiche preliminari`, `171-ter`, `memorie integrative`, `40 giorni`, `20 giorni`, `10 giorni`.
- `183`, `prima udienza`, `interrogatorio libero`, `tentativo di conciliazione`, `provvedimenti istruttori`.
- `281-sexies`, `discussione orale`, `lettura dispositivo`, `motivazione contestuale`.
- `sentenza`, `Repubblica Italiana`, `P.Q.M.`, `definitivamente pronunciando`, `pubblicazione`, `deposito sentenza`, `comunicazione cancelleria`.
- `art. 133 c.p.c.`, `comunicazione deposito sentenza`, `non idonea a far decorrere il termine breve`.
- `decreto di fissazione udienza`, `fissa l'udienza`, `udienza di comparizione`, `udienza di discussione`, `notifica ricorso e decreto`, `costituzione convenuto`.
- `cautelare`, `669-sexies`, `provvede con ordinanza`, `reclamo`, `669-terdecies`.
- `precetto`, `titolo esecutivo`, `formula esecutiva`, `pignoramento`, `pignoramento presso terzi`, `terzo pignorato`, `dichiarazione del terzo`, `art. 543`, `art. 547`.

Parser da attivare:

- parser RG e parti;
- parser udienza/data/ora;
- parser scadenze a ritroso rispetto alla data udienza;
- parser sentenza e P.Q.M.;
- parser spese/liquidazione/distrazione/compensazione;
- parser notifica/relata/esito PEC;
- parser esecuzione: precetto, pignoramento, termini di deposito e udienza.

### Economico, contributo unificato, spese e gratuito patrocinio

Fonti:

- DPR 115/2002, Testo unico spese di giustizia: https://www.gazzettaufficiale.it/eli/id/2002/06/15/002G0139/sg
- DPR 115/2002 PDF originale: https://www.gazzettaufficiale.it/eli/gu/2002/06/15/139/so/126/sg/pdf
- PST Giustizia, pagoPA e pagamenti telematici: https://servizipst.giustizia.it/PST/it/pagopa.wp
- PST Giustizia, altri pagamenti pagoPA: https://servizipst.giustizia.it/PST/it/pagopa_altripag.wp
- PST Giustizia, flussi pagamento telematico: https://servizipst.giustizia.it/PST/resources/cms/documents/PagTel_AllegatoA_Flussi_pagamento_telematico_erogati_tramite_PST_vers.5.3.pdf
- D.M. 55/2014 art. 2, spese generali forfettarie: https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticolo?art.codiceRedazionale=14G00067&art.dataPubblicazioneGazzetta=2014-04-02&art.flagTipoArticolo=0&art.idArticolo=2&art.idGruppo=1&art.idSottoArticolo=1&art.idSottoArticolo1=10&art.progressivo=0&art.versione=1

Chiavi da presidiare:

- Pagamento CU: `contributo unificato`, `CU`, `C.U.`, `PagoPA`, `pagoPA`, `IUV`, `ricevuta telematica`, `RT`, `RT.xml`, `identificativoMessaggioRicevuta`, `datiPagamento`, `codiceEsitoPagamento`, `importoTotalePagato`, `singoloImportoPagato`, `datiSpecificiRiscossione`, `CONTRIB`, `0702100TS`, `Ministero della Giustizia`, `spese di giustizia`.
- Esenzione CU: `esente dal pagamento del contributo unificato`, `esenzione contributo unificato`, `non dovuto`, `prenotazione a debito`, `autocertificazione`, `dichiarazione sostitutiva`, `art. 9 DPR 115/2002`, `art. 76 DPR 115/2002`, `reddito familiare`.
- Regolarizzazione CU: `omesso pagamento`, `insufficiente pagamento`, `invito al pagamento`, `richiesta versamento`, `integrazione contributo`, `depositare ricevuta`, `art. 248 DPR 115/2002`, `sanzione`, `interessi`.
- Liquidazione: `condanna alle spese`, `liquida`, `liquidando`, `compensi`, `onorari`, `esborsi`, `spese vive`, `spese generali`, `15%`, `IVA`, `CPA`, `accessori di legge`.
- Distrazione: `distrae`, `distrazione`, `antistatario`, `procuratore antistatario`, `in favore dell'avv.`, `in favore del difensore`.
- Compensazione: `compensa le spese`, `spese compensate`, `compensa integralmente`, `compensa parzialmente`, `soccombenza reciproca`.
- Gratuito patrocinio: `patrocinio a spese dello Stato`, `gratuito patrocinio`, `ammesso al patrocinio`, `istanza di liquidazione`, `decreto di pagamento`, `opposizione al decreto di pagamento`, `SIAMM`, `LSG`, `divieto di percepire compensi dall'assistito`.

Parser da attivare:

- RT XML pagoPA: estrazione importo da `importoTotalePagato` o `singoloImportoPagato`, IUV/identificativo, data esito, beneficiario, causale, esito pagamento.
- Ricevuta PDF pagoPA: OCR/lettura campo importo, IUV, beneficiario, causale, data.
- Autocertificazione esenzione: verifica esenzione/non dovuto/prenotazione a debito, senza creare importo fittizio.
- Sentenza economica: importi liquidati, spese generali, IVA/CPA, distrazione, compensazione totale/parziale.
- Proforma/parcella: proposta automatica da liquidazione, stato pratica, esito sentenza, eventuale gratuito patrocinio, divieto di percezione dall'assistito quando rilevante.

### Rito lavoro

Fonti:

- Gazzetta Ufficiale, modifiche e richiami artt. 415, 416, 420 c.p.c.: https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticolo?art.codiceRedazionale=011G0192&art.dataPubblicazioneGazzetta=2011-09-21&art.flagTipoArticolo=0&art.idArticolo=2&art.idGruppo=1&art.idSottoArticolo=1&art.idSottoArticolo1=10&art.progressivo=0&art.versione=1
- Gazzetta Ufficiale, richiamo a processo lavoro e nuovo decreto fissazione udienza: https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticolo?art.codiceRedazionale=011G0192&art.dataPubblicazioneGazzetta=2011-09-21&art.flagTipoArticolo=0&art.idArticolo=4&art.idGruppo=1&art.idSottoArticolo=1&art.idSottoArticolo1=10&art.progressivo=0&art.versione=1

Chiavi da presidiare:

- `rito del lavoro`, `ricorso ex art. 414`, `art. 415`, `decreto di fissazione udienza`, `udienza di discussione`, `notifica ricorso e decreto`, `costituzione del convenuto`, `memoria difensiva`, `art. 416`, `comparizione personale`, `interrogatorio libero`, `tentativo di conciliazione`, `art. 420`, `lettura dispositivo`, `art. 429`.

Parser da attivare:

- decreto lavoro: data deposito ricorso, data decreto, data udienza, termine notifica, termine costituzione/resistenza;
- sentenza lavoro: dispositivo, liquidazione, eventuale provvisoria esecutività;
- controllo economico: CU pagato/esente, spese liquidate, proforma da visionare.

### Famiglia, persone e minorenni

Fonti:

- Gazzetta Ufficiale, art. 473-bis e seguenti c.p.c.: https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticolo?art.codiceRedazionale=040U1443&art.dataPubblicazioneGazzetta=1940-10-28&art.flagTipoArticolo=1&art.idArticolo=473&art.idGruppo=70&art.idSottoArticolo=2&art.idSottoArticolo1=10&art.progressivo=0&art.versione=3

Chiavi da presidiare:

- `473-bis`, `persone minorenni e famiglie`, `ricorso`, `decreto fissazione udienza`, `notifica ricorso e decreto`, `costituzione convenuto`, `piano genitoriale`, `assegno di mantenimento`, `affidamento`, `collocamento`, `provvedimenti temporanei e urgenti`, `ordini di protezione`, `reclamo`.

Parser da attivare:

- data udienza e termini notifica/costituzione;
- importi periodici: mantenimento, arretrati, rivalutazione, assegno, spese straordinarie;
- avvisi operativi: documenti reddituali, dichiarazioni, piano genitoriale.

### Processo amministrativo e PAT

Fonti:

- Giustizia Amministrativa, processo amministrativo telematico: https://www.giustizia-amministrativa.it/processo-amministrativo-telematico
- Giustizia Amministrativa, Formweb prioritario dal 01/02/2026: https://www.giustizia-amministrativa.it/-/152174-737
- Giustizia Amministrativa, FAQ deposito notifiche: https://www.giustizia-amministrativa.it/faq
- Nuove regole tecnico-operative PAT: https://www.giustizia-amministrativa.it/documents/20142/74204502/pubblicazione%2BNTO%2Bdel%2BPAT%2BPortale%2Bavvocato-def.pdf/9cbe814a-21fa-2c0c-4fb6-ac775e9f8225?t=1754059365413

Chiavi da presidiare:

- `TAR`, `Consiglio di Stato`, `codice del processo amministrativo`, `CPA`, `ricorso`, `notifica ricorso`, `deposito ricorso`, `art. 45`, `trenta giorni`, `domanda cautelare`, `art. 55`, `camera di consiglio`, `decreto cautelare monocratico`, `art. 56`, `appello cautelare`, `art. 62`, `documenti`, `memorie`, `repliche`, `art. 73`, `udienza pubblica`, `art. 87`, `termini dimezzati`, `Formweb`, `PEC residuale`, `ricevuta SIGA/PAT`.

Parser da attivare:

- termine deposito ricorso;
- cautelare: camera di consiglio, termini brevi, documenti/memorie;
- merito: documenti 40 giorni liberi, memorie 30 giorni liberi, repliche 20 giorni liberi;
- canale deposito: Formweb prioritario dal 01/02/2026, PEC solo residuale per casi tecnici.

### Processo penale e PDP

Fonti:

- Gazzetta Ufficiale, art. 552 c.p.p.: https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticolo?art.codiceRedazionale=088G0492&art.dataPubblicazioneGazzetta=1988-10-24&art.flagTipoArticolo=0&art.idArticolo=552&art.idGruppo=79&art.idSottoArticolo=1&art.idSottoArticolo1=10&art.progressivo=0&art.versione=6
- Gazzetta Ufficiale, art. 157-ter c.p.p.: https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticolo?art.codiceRedazionale=088G0492&art.dataPubblicazioneGazzetta=1988-10-24&art.flagTipoArticolo=0&art.idArticolo=157&art.idGruppo=24&art.idSottoArticolo=3&art.idSottoArticolo1=10&art.progressivo=0&art.versione=1
- PST Giustizia, documentazione PDP: https://pst.giustizia.it/PST/it/documentation.page
- PST Giustizia, specifiche PDP 2023: https://pst.giustizia.it/PST/page/it/decreto_del_ministro_della_giustizia_del_4_luglio_2023__portale_deposito_atti_penali_pdp_pubblicato_sulla_gu_n_155_del_5_luglio_2023_adozione_delle_specifiche_tecniche?contentId=NWS2789&modelId=4
- Specifiche tecniche PDP: https://pst.giustizia.it/PST/resources/cms/documents/Specifiche_Tecniche_PPT_11.07.2023_post_DM_2023_signed.pdf

Chiavi da presidiare:

- `415-bis`, `conclusione delle indagini preliminari`, `20 giorni`, `presentare memorie`, `produrre documenti`, `depositare documentazione`, `chiedere interrogatorio`, `udienza preliminare`, `art. 419`, `richiesta rinvio a giudizio`, `decreto che dispone il giudizio`, `art. 429`, `citazione diretta a giudizio`, `art. 552`, `60 giorni prima`, `45 giorni urgenza`, `art. 601`, `notifica imputato`, `domicilio dichiarato`, `domicilio eletto`, `PDP`, `Portale Deposito atti Penali`.

Parser da attivare:

- avviso 415-bis: data notifica, termine 20 giorni, richieste difensive;
- citazione/decreto: data udienza, termine notifica, ufficio, imputato, difensore;
- deposito PDP: classe atto, allegati, ricevute, esiti.

### Tributario e PTT

Fonti:

- DEF Finanze, D.Lgs. 546/1992: https://def.finanze.it/DocTribFrontend/getAttoNormativoDetail.do?id=%7BECD81E71-D37B-4722-AA36-116B5BCB2232%7D
- DEF Finanze, art. 32 D.Lgs. 546/1992: https://def.finanze.it/DocTribFrontend/decodeurn?urn=urn%3Adoctrib%3A%3ADLG%3A1992%3B546_art32
- Gazzetta Ufficiale, art. 68 riforma tributaria 2024: https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticolo?art.codiceRedazionale=24G00193&art.dataPubblicazioneGazzetta=2024-11-28&art.flagTipoArticolo=1&art.idArticolo=68&art.idGruppo=9&art.idSottoArticolo=1&art.idSottoArticolo1=10&art.progressivo=0&art.versione=1
- Agenzia Entrate, D.Lgs. 546/1992 PDF: https://www.agenziaentrate.gov.it/portale/documents/20143/261426/Dlgs%2Bn546%2B31121992_decreto_legislativo_1992_546.pdf/eae0770d-65ba-e05a-fd0e-b9847ceeab36

Chiavi da presidiare:

- `processo tributario`, `Corte di giustizia tributaria`, `ricorso`, `costituzione in giudizio`, `deposito telematico`, `30 giorni dalla proposizione`, `controdeduzioni`, `documenti`, `20 giorni liberi`, `memorie illustrative`, `10 giorni liberi`, `brevi repliche`, `5 giorni liberi`, `comunicazione dispositivo`, `notificazione sentenza`, `deposito sentenza notificata`, `PTT`, `SIGIT`, `ricevuta deposito`, `scarto`, `accettazione`.

Parser da attivare:

- data notifica ricorso e termine costituzione;
- data trattazione/udienza e termini documenti/memorie/repliche;
- sentenza tributaria e termini successivi;
- ricevute PTT/SIGIT.

### PEC, notifiche e relata

Fonti:

- Normattiva, L. 53/1994 art. 3-bis: https://www.normattiva.it/uri-res/N2Ls?urn%3Anir%3Astato%3Alegge%3A1994-01-21%3B53%21vig=~art3bis
- Normattiva, L. 53/1994 art. 3-ter: https://www.normattiva.it/uri-res/N2Ls?urn%3Anir%3Astato%3Alegge%3A1994-01-21%3B53~art3ter=
- PST Giustizia, notificazioni via PEC degli avvocati: https://pst.giustizia.it/PST/it/dettaglio_schede_tematiche.page?contentId=ACC432&modelId=12
- Specifiche tecniche DM 44/2011 2024: https://pst.giustizia.it/PST/resources/cms/documents/m_dg.DOG07.07082024.0004292.ID_SPECIFICHETECNICHE_DM_44_2011_FINALE_31_.pdf
- AgID, pagina PEC: https://www.agid.gov.it/it/piattaforme/posta-elettronica-certificata
- AgID, regole tecniche PEC 2 novembre 2005: https://agid.gov.it/sites/default/files/repository_files/leggi_decreti_direttive/pec_regole_tecniche_dm_2-nov-2005.pdf
- AgID, note integrative PEC: https://agid.gov.it/sites/default/files/repository_files/documentazione_trasparenza/note_integrative_alle_regole_tecniche_v_12.0.pdf

Chiavi da presidiare:

- `postacert.eml`, `daticert.xml`, `ricevuta di accettazione`, `ricevuta di avvenuta consegna`, `avviso di mancata consegna`, `errore consegna`, `avviso di non accettazione`, `busta di trasporto`, `busta di anomalia`, `X-Ricevuta`, `identificativo messaggio`, `Message-ID`, `gestore-emittente`, `tipo ricevuta`, `breve`, `completa`, `sintetica`.
- `relata di notifica`, `relazione di notificazione`, `L. 53/1994`, `art. 3-bis`, `notificazione a mezzo PEC`, `pubblici elenchi`, `REGINDE`, `INI-PEC`, `IPA`, `INAD`, `procura alle liti`, `attestazione di conformità`, `impronta`, `firma digitale`.

Parser da attivare:

- PEC: mittente, destinatari, oggetto, data/ora italiana, identificativo, tipo ricevuta, esito, allegati, messaggio originale una sola volta.
- Notifica L.53: destinatario, domicilio digitale, fonte pubblico elenco, atto notificato, relata, ricevute accettazione/consegna, completezza prova.
- Azioni: associare a fascicolo, creare scadenza se l'atto genera termine, segnalare ricevute mancanti.

### PCT, PST e deposito telematico

Fonti:

- PST Giustizia, documentazione generale: https://pst.giustizia.it/PST/it/documentation.page
- Specifiche tecniche DM 44/2011 2024: https://pst.giustizia.it/PST/resources/cms/documents/m_dg.DOG07.07082024.0004292.ID_SPECIFICHETECNICHE_DM_44_2011_FINALE_31_.pdf
- PST Giustizia, pagamento telematico e ricevute RT: https://servizipst.giustizia.it/PST/resources/cms/documents/PagTel_AllegatoA_Flussi_pagamento_telematico_erogati_tramite_PST_vers.5.3.pdf
- PST Giustizia, codifica errori controlli deposito: https://pst.giustizia.it/PST/resources/cms/documents/Codifica_errori_controlli_1.0.pdf

Chiavi da presidiare:

- `deposito telematico`, `DatiAtto.xml`, `Atto.enc`, `Atto.msg`, `IndiceBusta.xml`, `IndiceDocumentiDepositati`, `ricevuta di accettazione`, `ricevuta di avvenuta consegna`, `RdAC`, `esito controlli automatici`, `accettazione deposito`, `warn`, `error`, `fatal`, `busta`, `certificato cifratura`, `ufficio giudiziario`, `codice oggetto`, `PST`, `SICID`, `SIECIC`, `SIGP`.

Parser da attivare:

- stato catena PEC deposito;
- esito controlli: warning, error, fatal, accettazione cancelleria;
- requisiti deposito: atto principale, allegati, firme, indice, ufficio, certificato, busta.

### Decreto ingiuntivo e opposizione

Fonti:

- Gazzetta Ufficiale, art. 633 c.p.c.: https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticolo?art.codiceRedazionale=040U1443&art.dataPubblicazioneGazzetta=1940-10-28&art.flagTipoArticolo=1&art.idArticolo=633&art.idGruppo=113&art.idSottoArticolo=1&art.idSottoArticolo1=10&art.progressivo=0&art.versione=2
- Gazzetta Ufficiale, art. 645 c.p.c.: https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticolo?art.codiceRedazionale=040U1443&art.dataPubblicazioneGazzetta=1940-10-28&art.flagTipoArticolo=1&art.idArticolo=645&art.idGruppo=113&art.idSottoArticolo=1&art.idSottoArticolo1=10&art.progressivo=0&art.versione=5
- Gazzetta Ufficiale, art. 648 c.p.c.: https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticolo?art.codiceRedazionale=040U1443&art.dataPubblicazioneGazzetta=1940-10-28&art.flagTipoArticolo=1&art.idArticolo=648&art.idGruppo=113&art.idSottoArticolo=1&art.idSottoArticolo1=10&art.progressivo=0&art.versione=5

Chiavi da presidiare:

- `decreto ingiuntivo`, `ingiunzione di pagamento`, `prova scritta`, `ricorso per decreto ingiuntivo`, `provvisoria esecuzione`, `opposizione a decreto ingiuntivo`, `atto di citazione in opposizione`, `ufficio giudiziario che ha emesso il decreto`, `sospensione dell'esecuzione`, `esecuzione provvisoria`, `cauzione`, `somme non contestate`.

Parser da attivare:

- importo ingiunto, interessi, spese decreto;
- data notifica decreto, data opposizione, ufficio, termine comparizione/costituzione;
- stato esecutività: concessa, sospesa, provvisoria in pendenza opposizione;
- azione economica: credito da recuperare, spese liquidate, eventuale proforma.

### Locazione, sfratto e convalida

Fonti:

- Gazzetta Ufficiale, art. 657 c.p.c.: https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticolo?art.codiceRedazionale=040U1443&art.dataPubblicazioneGazzetta=1940-10-28&art.flagTipoArticolo=1&art.idArticolo=657&art.idGruppo=114&art.idSottoArticolo=1&art.idSottoArticolo1=10&art.progressivo=0&art.versione=3
- Gazzetta Ufficiale, art. 658 c.p.c.: https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticolo?art.codiceRedazionale=040U1443&art.dataPubblicazioneGazzetta=1940-10-28&art.flagTipoArticolo=1&art.idArticolo=658&art.idGruppo=114&art.idSottoArticolo=1&art.idSottoArticolo1=10&art.progressivo=0&art.versione=2
- Gazzetta Ufficiale, art. 660 c.p.c.: https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticolo?art.codiceRedazionale=040U1443&art.dataPubblicazioneGazzetta=1940-10-28&art.flagTipoArticolo=1&art.idArticolo=660&art.idGruppo=114&art.idSottoArticolo=1&art.idSottoArticolo1=10&art.progressivo=0&art.versione=4
- Gazzetta Ufficiale, art. 664 c.p.c.: https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticolo?art.codiceRedazionale=040U1443&art.dataPubblicazioneGazzetta=1940-10-28&art.flagTipoArticolo=1&art.idArticolo=664&art.idGruppo=114&art.idSottoArticolo=1&art.idSottoArticolo1=10&art.progressivo=0&art.versione=1

Chiavi da presidiare:

- `intimazione di sfratto`, `licenza per finita locazione`, `sfratto per morosità`, `citazione per la convalida`, `convalida`, `mancato pagamento canone`, `ingiunzione canoni`, `opposizione`, `mutamento rito`, `ordinanza di rilascio`, `termine di grazia`, `canoni scaduti`, `canoni a scadere`.

Parser da attivare:

- data udienza convalida, notifica intimazione, comparizione;
- importi canoni, mensilità, spese intimazione;
- esito: convalida, opposizione, mutamento rito, decreto ingiuntivo canoni.

### Esecuzione, pignoramento, vendita e ricerca beni

Fonti:

- Gazzetta Ufficiale, art. 492-bis c.p.c.: https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticolo?art.codiceRedazionale=040U1443&art.dataPubblicazioneGazzetta=1940-10-28&art.flagTipoArticolo=1&art.idArticolo=492&art.idGruppo=84&art.idSottoArticolo=2&art.idSottoArticolo1=10&art.progressivo=0&art.versione=4
- Gazzetta Ufficiale, art. 543 c.p.c.: https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticolo?art.codiceRedazionale=040U1443&art.dataPubblicazioneGazzetta=1940-10-28&art.flagTipoArticolo=1&art.idArticolo=543&art.idGruppo=92&art.idSottoArticolo=1&art.idSottoArticolo1=10&art.progressivo=0&art.versione=8
- Gazzetta Ufficiale, art. 569 c.p.c.: https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticolo?art.codiceRedazionale=040U1443&art.dataPubblicazioneGazzetta=1940-10-28&art.flagTipoArticolo=1&art.idArticolo=569&art.idGruppo=96&art.idSottoArticolo=1&art.idSottoArticolo1=10&art.progressivo=0&art.versione=8
- PST Giustizia, pagamenti per 492-bis, UNEP notifiche e pignoramenti: https://pst.giustizia.it/PST/resources/cms/documents/PDA__Flussi_pagamento_telematico_tramite_PST_vers._6.3.pdf

Chiavi da presidiare:

- `titolo esecutivo`, `precetto`, `pignoramento`, `pignoramento presso terzi`, `terzo pignorato`, `dichiarazione del terzo`, `art. 543`, `art. 547`, `ricerca con modalità telematiche dei beni`, `492-bis`, `UNEP`, `UNPIG`, `UNNOT`, `CONTRBENI`, `istanza di vendita`, `documentazione ipocatastale`, `ordinanza di vendita`, `esperto stimatore`, `udienza ex art. 569`, `offerte d'acquisto`, `progetto di distribuzione`.

Parser da attivare:

- data notifica precetto/pignoramento e termine deposito;
- importo credito, interessi, spese, residuo credito;
- terzo, debitore, creditore, udienza, dichiarazione terzo;
- vendita: istanza, documentazione, udienza, prezzo base/offerte/scadenze.

### ATP previdenziale e consulenze

Fonti:

- Gazzetta Ufficiale, art. 445-bis c.p.c.: https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticolo?art.codiceRedazionale=011G0146&art.dataPubblicazioneGazzetta=2011-07-06&art.flagTipoArticolo=0&art.idArticolo=38&art.idGruppo=6&art.idSottoArticolo=1&art.idSottoArticolo1=10&art.progressivo=0&art.versione=1
- Gazzetta Ufficiale, art. 193/195 c.p.c. richiamati nella riforma Cartabia: https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticolo?art.codiceRedazionale=22G00158&art.dataPubblicazioneGazzetta=2022-10-17&art.flagTipoArticolo=0&art.idArticolo=3&art.idGruppo=2&art.idSottoArticolo=1&art.idSottoArticolo1=10&art.progressivo=3&art.versione=1

Chiavi da presidiare:

- `accertamento tecnico preventivo obbligatorio`, `445-bis`, `invalidità civile`, `handicap`, `disabilità`, `pensione di inabilità`, `assegno di invalidità`, `INPS`, `condizione di procedibilità`, `istanza di ATP`, `15 giorni`, `omologa`, `dissenso`, `consulente tecnico d'ufficio`, `CTU`, `giuramento`, `firma digitale`, `bozza peritale`, `osservazioni`, `relazione definitiva`, `liquidazione CTU`.

Parser da attivare:

- termine per istanza/completamento ATP;
- termine osservazioni e dissenso;
- decreto di omologa, liquidazione spese/CTU, eventuale sentenza;
- scadenze operative per deposito note/osservazioni.

### Mediazione e negoziazione assistita

Fonti:

- Gazzetta Ufficiale, D.Lgs. 28/2010 come modificato dalla riforma Cartabia: https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticolo?art.codiceRedazionale=22G00158&art.dataPubblicazioneGazzetta=2022-10-17&art.flagTipoArticolo=0&art.idArticolo=7&art.idGruppo=4&art.idSottoArticolo=1&art.idSottoArticolo1=10&art.progressivo=0&art.versione=1
- Gazzetta Ufficiale, mediazione condizione di procedibilità: https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticolo?art.codiceRedazionale=13G00116&art.dataPubblicazioneGazzetta=2013-06-21&art.flagTipoArticolo=0&art.idArticolo=84&art.idGruppo=15&art.idSottoArticolo=1&art.idSottoArticolo1=10&art.progressivo=0&art.versione=1
- Gazzetta Ufficiale, negoziazione assistita riforma Cartabia: https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticolo?art.codiceRedazionale=22G00158&art.dataPubblicazioneGazzetta=2022-10-17&art.flagTipoArticolo=0&art.idArticolo=9&art.idGruppo=4&art.idSottoArticolo=1&art.idSottoArticolo1=10&art.progressivo=0&art.versione=1

Chiavi da presidiare:

- `mediazione`, `condizione di procedibilità`, `domanda di mediazione`, `organismo di mediazione`, `primo incontro`, `mediazione demandata`, `verbale negativo`, `verbale positivo`, `accordo di conciliazione`, `improcedibilità`, `prima udienza`.
- `negoziazione assistita`, `invito alla stipula`, `convenzione di negoziazione`, `rifiuto`, `mancata adesione`, `30 giorni dalla ricezione`, `condizione di procedibilità`, `domanda pagamento somme non eccedenti cinquantamila euro`.

Parser da attivare:

- data invito/domanda, termine adesione, primo incontro;
- esito procedibilità: avverata, non avverata, iniziata ma non conclusa;
- allegati da fascicolo: invito, PEC, ricevute, verbale, accordo.

### Notifiche digitali PA e PND

Fonti:

- Gazzetta Ufficiale, art. 26 DL 76/2020 piattaforma notificazione digitale: https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticolo?art.codiceRedazionale=20A04921&art.dataPubblicazioneGazzetta=2020-09-14&art.flagTipoArticolo=0&art.idArticolo=26&art.idGruppo=7&art.idSottoArticolo=1&art.idSottoArticolo1=10&art.progressivo=0&art.versione=1
- Gazzetta Ufficiale, Decreto 8 febbraio 2022 n. 58: https://www.gazzettaufficiale.it/eli/id/2022/06/06/22G00067/SG
- Gazzetta Ufficiale, modifiche 2023 su avviso di avvenuta ricezione: https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticolo?art.codiceRedazionale=23A03864&art.dataPubblicazioneGazzetta=2023-07-05&art.flagTipoArticolo=0&art.idArticolo=6&art.idGruppo=2&art.idSottoArticolo=1&art.idSottoArticolo1=10&art.progressivo=0&art.versione=1

Chiavi da presidiare:

- `piattaforma notificazione digitale`, `SEND`, `PND`, `avviso di avvenuta ricezione`, `avviso di cortesia`, `deposito in piattaforma`, `perfezionamento`, `decimo giorno`, `irreperibilità`, `rimessione in termini`, `atti della pubblica amministrazione`, `spese notifica`.

Parser da attivare:

- data deposito piattaforma;
- data perfezionamento per amministrazione e destinatario;
- importi spese notifica e pagamento;
- collegamento a fascicolo tributario/amministrativo/civile se l'atto genera termine.

### Crisi d'impresa e procedure concorsuali

Fonti:

- Gazzetta Ufficiale, Codice crisi e insolvenza, procedimento unitario: https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticolo?art.codiceRedazionale=22G00090&art.dataPubblicazioneGazzetta=2022-07-01&art.flagTipoArticolo=0&art.idArticolo=12&art.idGruppo=1&art.idSottoArticolo=1&art.idSottoArticolo1=10&art.progressivo=0&art.versione=1

Chiavi da presidiare:

- `codice della crisi`, `liquidazione giudiziale`, `concordato`, `domanda di accesso`, `strumenti di regolazione della crisi`, `ricorso`, `commissario`, `curatore`, `stato passivo`, `domanda di ammissione al passivo`, `insinuazione`, `opposizione allo stato passivo`, `comitato creditori`, `PEC curatore`.

Parser da attivare:

- data domanda, decreto, udienza, termini creditori;
- importi credito, privilegio/chirografo, ammissione/esclusione;
- comunicazioni PEC curatore/commissario e scadenze per opposizione.

### Cassazione civile

Fonti:

- Corte Suprema di Cassazione, registri civili e penali su PST: https://www.cortedicassazione.it/it/registri_civ_pen_cassazione.page
- Corte Suprema di Cassazione, protocollo processo civile in Cassazione 01/03/2023: https://www.cortedicassazione.it/resources/cms/documents/Protocollo_di_intesa_sul_processo_civile_in_Cassazione___01.03.2023.pdf
- Gazzetta Ufficiale, art. 369 c.p.c. deposito ricorso: https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticolo?art.codiceRedazionale=040U1443&art.dataPubblicazioneGazzetta=1940-10-28&art.flagTipoArticolo=1&art.idArticolo=369&art.idGruppo=55&art.idSottoArticolo=1&art.idSottoArticolo1=10&art.progressivo=0&art.versione=5
- Corte Suprema di Cassazione, rassegna PCT aggiornata al 30/06/2025: https://www.cortedicassazione.it/resources/cms/documents/Rassegna_tematica_aggiornata_con_le_decisioni_pubblicate_al_30_giugno_2025.pdf

Chiavi da presidiare:

- `Corte Suprema di Cassazione`, `ricorso per cassazione`, `controricorso`, `ricorso incidentale`, `art. 369`, `deposito del ricorso`, `venti giorni dall'ultima notificazione`, `art. 370`, `380-bis`, `380-ter`, `adunanza camerale`, `pubblica udienza`, `proposta di definizione accelerata`, `memoria`, `contributo unificato`.

Parser da attivare:

- data ultima notifica e termine deposito ricorso;
- controricorso e ricorso incidentale;
- adunanza camerale/pubblica udienza;
- CU, ricevute e fascicolo informatico Cassazione/PST.

### SIAMM, LSG e gratuito patrocinio

Fonti:

- LSG/SIAMM Ministero Giustizia, portale liquidazione spese: https://lsg.giustizia.it/SIAMM/IstanzaWEB/
- Ministero della Giustizia, liquidazione spese di giustizia: https://www.giustizia.it/giustizia/page/it/come_fare_per_liquidazioni_spese_giustizia
- PST Giustizia, elenco servizi con portale liquidazione spese: https://pst.giustizia.it/PST/it/services.page
- DPR 115/2002 PDF Gazzetta Ufficiale: https://www.gazzettaufficiale.it/eli/gu/2002/06/15/139/so/126/sg/pdf

Chiavi da presidiare:

- `SIAMM`, `LSG`, `Sistema Liquidazioni Spese di Giustizia`, `istanza web`, `istanza di liquidazione`, `decreto di pagamento`, `opposizione al decreto di pagamento`, `art. 170 DPR 115/2002`, `difensore d'ufficio`, `imputati assolti`, `istanze Pinto`, `patrocinio a spese dello Stato`, `gratuito patrocinio`.

Parser da attivare:

- distinguere SIAMM/LSG generico da gratuito patrocinio;
- estrarre qualifica beneficiario, ufficio spese, decreto pagamento, opposizione;
- bloccare proforma verso assistito quando il fascicolo è coperto da patrocinio a spese dello Stato.

### Giudice di Pace e SIGP

Fonti:

- PST Giustizia, servizi online e documentazione: https://pst.giustizia.it/PST/it/services.page
- PST Giustizia, aggiornamento specifiche deposito atti SIGP 2024: https://pst.giustizia.it/PST/page/it/processo_telematico__comunicazione_per_le_software_house__aggiornamento_specifiche_tecniche_deposito_atti_sigp_it_4?contentId=NWS3477
- Gazzetta Ufficiale, art. 316 c.p.c.: https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticolo?art.codiceRedazionale=040U1443&art.dataPubblicazioneGazzetta=1940-10-28&art.flagTipoArticolo=1&art.idArticolo=316&art.idGruppo=50&art.idSottoArticolo=1&art.idSottoArticolo1=10&art.progressivo=0&art.versione=7
- Gazzetta Ufficiale, D.Lgs. 150/2011 art. 6 opposizione sanzioni amministrative: https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticolo?art.codiceRedazionale=011G0192&art.dataPubblicazioneGazzetta=2011-09-21&art.flagTipoArticolo=0&art.idArticolo=6&art.idGruppo=2&art.idSottoArticolo=1&art.idSottoArticolo1=10&art.progressivo=0&art.versione=1

Chiavi da presidiare:

- `Giudice di Pace`, `SIGP`, `servizi online giudici di pace`, `opposizione a sanzione amministrativa`, `verbale di accertamento`, `art. 204-bis`, `Legge 689/1981`, `D.Lgs. 150/2011`, `art. 316`, `art. 320`, `trattazione della causa`.

Parser da attivare:

- termine opposizione/ricorso;
- decreto di fissazione udienza e trattazione;
- importo sanzione, contributo, ufficio competente, esito SIGP.

### Volontaria giurisdizione e Tribunale Online

Fonti:

- PST Giustizia, Tribunale Online e volontaria giurisdizione: https://pst.giustizia.it/PST/page/it/avviata_la_seconda_fase_di_sperimentazione_del_tribunale_online?contentId=NWS4108&modelId=4
- PST Giustizia, documentazione Tribunale Online / D.M. 22/01/2024: https://pst.giustizia.it/PST/it/documentation.page
- Gazzetta Ufficiale, art. 737 c.p.c.: https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticolo?art.codiceRedazionale=040U1443&art.dataPubblicazioneGazzetta=1940-10-28&art.flagTipoArticolo=1&art.idArticolo=737&art.idGruppo=128&art.idSottoArticolo=1&art.idSottoArticolo1=10&art.progressivo=0&art.versione=1
- Gazzetta Ufficiale, richiamo art. 739 c.p.c.: https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticolo?art.codiceRedazionale=000G0442&art.dataPubblicazioneGazzetta=2000-12-30&art.flagTipoArticolo=0&art.idArticolo=96&art.idGruppo=15&art.idSottoArticolo=1&art.idSottoArticolo1=10&art.progressivo=0&art.versione=1

Chiavi da presidiare:

- `volontaria giurisdizione`, `Tribunale Online`, `giudice tutelare`, `amministrazione di sostegno`, `amministratore di sostegno`, `ADS`, `beneficiario`, `rendiconto`, `eredità giacente`, `nomina curatore`, `camera di consiglio`, `decreto motivato`, `reclamo`, `art. 739`.

Parser da attivare:

- istanza, decreto, udienza, adempimenti periodici e rendiconto;
- reclamo e termine;
- collegamento con deposito Tribunale Online quando presente.

### Famiglia, minori e ascolto del minore

Fonti:

- PST Giustizia, regole tecniche ascolto del minore 07/12/2023: https://pst.giustizia.it/PST/resources/cms/documents/m_dg.DOG07.09122023.0007510.ID_Regole_Tecniche_Registrazione_ascolto_mi.pdf
- PST Giustizia, pagina provvedimento ascolto minore: https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC2984
- Gazzetta Ufficiale, artt. 473-bis e seguenti: https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticolo?art.codiceRedazionale=22G00158&art.dataPubblicazioneGazzetta=2022-10-17&art.flagTipoArticolo=0&art.idArticolo=3&art.idGruppo=2&art.idSottoArticolo=1&art.idSottoArticolo1=10&art.progressivo=1&art.versione=1
- PST Giustizia, modifiche classificazione oggetti materia famiglia: https://pst.giustizia.it/PST/it/news.page?frame5_item=79&frame6_item=9&metadata_category_frame6=news_comunicazioni

Chiavi da presidiare:

- `473-bis`, `persone minorenni e famiglie`, `ascolto del minore`, `registrazione audiovisiva`, `piano genitoriale`, `provvedimenti temporanei e urgenti`, `ordini di protezione`, `affidamento`, `collocamento`, `assegno di mantenimento`, `spese straordinarie`, `relazione servizi sociali`.

Parser da attivare:

- udienza, termini notifica/costituzione, ascolto minore, misure urgenti;
- importi mantenimento, arretrati e spese straordinarie;
- documenti reddituali e piano genitoriale.

### Appelli e impugnazioni

Fonti:

- Gazzetta Ufficiale, appello civile e udienza di trattazione: https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticolo?art.codiceRedazionale=12A08941&art.dataPubblicazioneGazzetta=2012-08-11&art.flagTipoArticolo=0&art.idArticolo=54&art.idGruppo=13&art.idSottoArticolo=1&art.idSottoArticolo1=10&art.progressivo=0&art.versione=1
- DEF Finanze, D.Lgs. 546/1992 processo tributario e appello: https://def.finanze.it/DocTribFrontend/getAttoNormativoDetail.do?id=%7BECD81E71-D37B-4722-AA36-116B5BCB2232%7D
- DEF Finanze, Testo unico 175/2024 con controdeduzioni appello: https://def.finanze.it/DocTribFrontend/getAttoNormativoDetail.do?ACTION=getSommario&id=%7B5B1E09EB-071F-4645-B4E1-A664CCB95CED%7D
- Giustizia Amministrativa, PAT/Formweb: https://www.giustizia-amministrativa.it/processo-amministrativo-telematico

Chiavi da presidiare:

- Civile/lavoro: `atto di appello`, `ricorso in appello`, `appello incidentale`, `inibitoria`, `sospensione dell'efficacia esecutiva`, `art. 342`, `art. 343`, `art. 347`, `art. 351`, `art. 352`, `art. 433`, `art. 434`, `art. 435`, `art. 436`.
- Amministrativo: `Consiglio di Stato`, `appello amministrativo`, `appello cautelare`, `ricorso incidentale`, `motivi aggiunti`, `art. 92`, `art. 98`, `art. 101`, `art. 104`, `termini dimezzati`.
- Tributario: `appello tributario`, `Corte di giustizia tributaria di secondo grado`, `forma dell'appello`, `controdeduzioni dell'appellato`, `appello incidentale`, `PTT`, `SIGIT`, `art. 53`, `art. 54`, `art. 61 D.Lgs. 546/1992`.

Parser da attivare:

- termine impugnazione, data notifica, costituzione/controdeduzioni;
- inibitoria/appello cautelare;
- PTT/PAT ricevute, scarti, accettazioni e udienze.

## Copertura aggiornata nel ruleset

Coperto in questa tranche:

- identità fascicolo/RG;
- contributo unificato pagamento, esenzione, invito/regolarizzazione;
- SIAMM/LSG distinto da gratuito patrocinio;
- sentenza, liquidazione, distrazione, compensazione;
- udienze 127-bis e 127-ter, decreti udienza, memorie 171-ter, rito lavoro;
- amministrativo, penale, tributario/PTT;
- PEC, relata, deposito PCT, pagoPA RT XML;
- decreto ingiuntivo, sfratto, esecuzione, ATP/CTU, ADR;
- notifiche digitali PA/SEND;
- crisi d'impresa;
- Cassazione civile, Giudice di Pace/SIGP, volontaria giurisdizione, famiglia/minori, appelli civili/lavoro/amministrativi/tributari.

## Query già eseguite

Queste query sono state già usate e non vanno ripetute senza motivo:

- `site:gazzettaufficiale.it codice procedura civile art. 127-bis 127-ter 171-bis 171-ter 183 281-sexies udienza note scritte`
- `site:gazzettaufficiale.it codice procedura civile art. 91 92 93 133 spese distrazione comunicazione sentenza termine impugnazione`
- `site:gazzettaufficiale.it DPR 115/2002 contributo unificato art. 9 14 15 16 82 83 85 170 248`
- `site:servizipst.giustizia.it PST pagoPA contributo unificato ricevuta telematica IUV RT XML`
- `site:gazzettaufficiale.it codice processo amministrativo art. 45 55 73 87 deposito ricorso memorie udienza camera consiglio`
- `site:gazzettaufficiale.it codice procedura penale art. 415-bis 419 429 552 601 avviso udienza decreto citazione giudizio`
- `site:giustizia-amministrativa.it PAT deposito telematico processo amministrativo formweb specifiche tecniche deposito atti 2026`
- `site:giustizia.it portale deposito atti penali PDP specifiche tecniche deposito atti penali`
- `site:normattiva.it legge 53 1994 art. 3-bis notifica PEC avvocato pubblici elenchi relata`
- `site:normattiva.it DM 44 2011 art. 18 notificazione via PEC relata avvocato`
- `site:agid.gov.it linee guida posta elettronica certificata ricevuta completa breve sintetica daticert.xml postacert.eml`
- `site:pst.giustizia.it notifiche telematiche avvocato legge 53 1994 PEC pubblici elenchi relata`
- `site:gazzettaufficiale.it c.p.c. art. 415 416 420 rito lavoro decreto fissazione udienza costituzione convenuto`
- `site:gazzettaufficiale.it c.p.c. art. 473-bis.14 473-bis.17 procedimento persone minorenni famiglie ricorso decreto fissazione udienza`
- `site:gazzettaufficiale.it c.p.c. art. 669-sexies 669-terdecies procedimento cautelare reclamo udienza`
- `site:gazzettaufficiale.it c.p.c. art. 543 547 pignoramento presso terzi dichiarazione terzo udienza`
- `site:giustiziatributaria.gov.it processo tributario telematico PTT deposito notifica ricorso termini documenti 50 MB`
- `site:gazzettaufficiale.it d.lgs. 546 1992 art. 16-bis processo tributario telematico notifica deposito ricorso`
- `site:gazzettaufficiale.it d.lgs. 546 1992 art. 22 23 24 32 processo tributario ricorso costituzione documenti memorie`
- `site:giustiziatributaria.gov.it SIGIT processo tributario telematico ricevuta deposito accettazione scarto`
- `site:gazzettaufficiale.it c.p.c. art. 633 641 645 648 649 decreto ingiuntivo opposizione provvisoria esecuzione sospensione`
- `site:gazzettaufficiale.it decreto ingiuntivo art. 633 641 645 codice procedura civile caricaArticolo 040U1443`
- `site:gazzettaufficiale.it sfratto art. 657 658 663 665 667 codice procedura civile caricaArticolo 040U1443`
- `site:gazzettaufficiale.it istanza vendita art. 567 569 codice procedura civile caricaArticolo 040U1443`
- `site:gazzettaufficiale.it c.p.c. art. 445-bis accertamento tecnico preventivo previdenziale omologa dissenso INPS`
- `site:gazzettaufficiale.it d.lgs. 28 2010 mediazione condizione di procedibilita domanda giudiziale verbale`
- `site:gazzettaufficiale.it decreto legge 132 2014 negoziazione assistita condizione procedibilita invito convenzione`
- `site:gazzettaufficiale.it c.p.c. art. 195 consulente tecnico osservazioni consulenza tecnica d'ufficio termine`
- `site:gazzettaufficiale.it codice crisi impresa insolvenza domanda liquidazione giudiziale insinuazione passivo opposizione stato passivo`
- `site:gazzettaufficiale.it art. 492-bis c.p.c. ricerca telematica beni pignorare UNEP istanza`
- `site:pst.giustizia.it UNEP richieste notifica pignoramento 492-bis specifiche tecniche`
- `site:gazzettaufficiale.it piattaforma notifiche digitali atti pubblica amministrazione perfezionamento decimo giorno deposito piattaforma`
- `site:cortedicassazione.it processo civile telematico cassazione ricorso controricorso memorie udienza camerale contributo unificato`
- `site:pst.giustizia.it Cassazione processo telematico ricorso controricorso deposito memorie specifiche tecniche`
- `site:gazzettaufficiale.it codice procedura civile cassazione ricorso controricorso memoria adunanza camerale art. 369 370 380-bis 380-ter`
- `site:gazzettaufficiale.it contributo unificato cassazione DPR 115/2002 art 13 comma 1-quater`
- `site:pst.giustizia.it SIAMM liquidazione spese di giustizia gratuito patrocinio decreto pagamento opposizione art 170 DPR 115`
- `site:giustizia.it SIAMM patrocinio spese dello Stato liquidazione avvocato istanza decreto pagamento`
- `site:gazzettaufficiale.it DPR 115 2002 art. 82 83 84 85 170 patrocinio spese Stato decreto pagamento opposizione`
- `site:pst.giustizia.it servizi online portale liquidazione spese di giustizia istanze Pinto imputati assolti SIAMM`
- `site:pst.giustizia.it SIGP Giudice di Pace servizi online deposito telematico specifiche tecniche opposizione sanzioni amministrative`
- `site:gazzettaufficiale.it codice procedura civile giudice di pace art 316 317 318 319 320 costituzione udienza ricorso`
- `site:pst.giustizia.it Tribunale Online volontaria giurisdizione amministrazione sostegno deposito telematico`
- `site:gazzettaufficiale.it c.p.c. volontaria giurisdizione reclamo decreto camera consiglio artt 737 739 740`
- `site:gazzettaufficiale.it codice procedura civile appello citazione costituzione inibitoria sospensione efficacia esecutiva art 342 343 347 348-bis 351 352`
- `site:gazzettaufficiale.it rito lavoro appello art 433 434 435 436 437 438 codice procedura civile udienza discussione`
- `site:gazzettaufficiale.it codice processo amministrativo appello Consiglio di Stato ricorso incidentale motivi aggiunti appello cautelare art 92 98 101 104 119`
- `site:def.finanze.it d.lgs. 546 1992 appello tributario art 51 53 54 61 62 62-bis controdeduzioni memorie`
- `site:pst.giustizia.it registrazione audiovisiva ascolto minore fascicolo informatico provvedimento 7 dicembre 2023`
- `site:gazzettaufficiale.it art. 473-bis.14 473-bis.17 473-bis.21 reclamo provvedimenti temporanei urgenti cpc famiglia`
- `site:gazzettaufficiale.it 473-bis.70 473-bis.71 ordini protezione reclamo famiglia minori`
- `site:pst.giustizia.it processo telematico minorenni famiglia persone specifiche tecniche deposito atti`

## Cosa manca ancora da cercare

Priorità alta, perché può produrre scadenze o blocchi operativi:

- Cassazione penale: avvisi udienza, deposito motivi/memorie, trasmissione provvedimenti e registri penali Cassazione.
- Processo penale Giudice di Pace: citazione, udienza, oblazione, remissione querela, impugnazioni.
- Procedimenti monitori/ingiuntivi europei, titolo esecutivo europeo e notifiche transfrontaliere.
- Esecuzioni immobiliari: delegato vendita, custode, PVP, offerte telematiche, progetto distribuzione dettagliato.
- Fallimentare/concorsuale: portale procedure concorsuali, comunicazioni curatore, ammissione passivo e opposizioni con scadenze reali.
- Portali esterni non ministeriali ricorrenti nello studio: INPS, Agenzia Entrate-Riscossione, PagoPA enti locali, SEND/Piattaforma notifiche quando entrano come PEC.

Priorità media, perché rafforza classificazione e riduce falsi positivi:

- Sinonimi reali usati dagli studi per i documenti: `pagamento cu`, `pagam. c.u.`, `ricevuta contributo`, `CU esente`, `autocert. esenzione`, `istanza pagamento`, `liquidazione avvocato`, `sentenza spese`.
- Varianti OCR comuni: `contribut0`, `unifìcato`, `pag0PA`, `lUV` al posto di `IUV`, `R.G.` con spazi, apostrofi e accenti corrotti.
- File XML ministeriali e pagoPA: namespace diversi, tag con prefisso, ricevute non firmate, PDF promemoria distinto da RT XML.
- PEC con duplicazione corpo: `postacert.eml` + corpo esterno + allegati testuali, regola di deduplica.
- Classificazione documenti importati da QuickOrganizer/Studio Telematico con `tipo` generico o sbagliato.

## Regola di avanzamento

Ogni nuova ricerca va aggiunta qui con:

- query usata;
- fonte trovata;
- data;
- settore;
- parole chiave ricavate;
- parser o regola da aggiornare;
- test da creare.

Finché una fonte è in questa pagina come `da cercare`, non deve essere considerata coperta dal presidio.
