# Audit fonti ufficiali Template Atti

- Data verifica: 2026-06-06
- Versione registro: 2026.06.06.template-fonti-ufficiali.v1
- Modelli catalogo unificato: 1320
- Modelli compilatore: 192
- Righe modello totali: 1512
- Righe modello OK: 1512
- Righe modello con problemi: 0
- Fonti nel registro: 106
- Fonti registro con problemi: 0

## Regola di audit

La fonte `base_comune` non chiude la copertura. Un modello è OK solo se
ha almeno una fonte professionale valida e almeno una fonte collegata
tra `telematica`, `secondaria_collegata`, `deontologia`,
`ordinamento_professionale` o `autorita`, non transitoria, con URL ufficiale
e data di verifica aggiornata. Questo impedisce di spacciare una fonte
generale per presidio specifico del modello.

## Fonti registro con problemi

- Nessuna.

## Fonti censite e ricerche web riportate in Ricerca Legale

| ID | Fonte | Ruolo | Tipo | Ambito | URL ufficiale | Modelli collegati | Termini |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `normattiva_codice_civile` | Codice civile | base_comune | normativa | generale | [apri](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=042U0262&atto.dataPubblicazioneGazzetta=1942-04-04&tipoDettaglio=vigente) | CIV, STR, SOC, LOC, RCD, FAM, VGS | civile, contratto, contrattuale, adempimento, inadempimento, responsabilita, risarcimento, societario, famiglia, succession |
| `cc_art_1219_mora` | Codice civile - costituzione in mora | specifica | normativa | specifica | [apri](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=042U0262&atto.dataPubblicazioneGazzetta=1942-04-04&tipoDettaglio=vigente) | STR, BAN, CON, LOC, RCD, LAV | diffida, mora, inadempimento, pagamento, sollecito, invito ad adempiere |
| `normattiva_cpc` | Codice di procedura civile | base_comune | normativa | generale processuale | [apri](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=040U1443&atto.dataPubblicazioneGazzetta=1940-10-28&tipoDettaglio=vigente) | CIV, CAU, ESE, MON, GDP, TMP-CIV, TMP-CAUT, TMP-ESE, LAV, FAM, RCD, CONC | cpc, c.p.c, citazione, comparsa, ricorso, memoria, appello, cassazione, esecuzione, cautelare, +1 |
| `cpc_art_163_citazione` | Codice di procedura civile - contenuto dell'atto di citazione | specifica | normativa | specifica | [apri](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=040U1443&atto.dataPubblicazioneGazzetta=1940-10-28&tipoDettaglio=vigente) | CIV_CIT, CIV_ORD, RCD, BAN, SOC | citazione, atto di citazione, vocatio, convenire |
| `cpc_art_167_comparsa` | Codice di procedura civile - comparsa di risposta | specifica | normativa | specifica | [apri](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=040U1443&atto.dataPubblicazioneGazzetta=1940-10-28&tipoDettaglio=vigente) | CIV_COM, CIV_ORD, CIV_IMP | comparsa, costituzione, risposta, convenuto, riconvenzionale, chiamata del terzo |
| `cpc_art_171_ter_memorie` | Codice di procedura civile - memorie integrative Cartabia | specifica | normativa | specifica | [apri](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=040U1443&atto.dataPubblicazioneGazzetta=1940-10-28&tipoDettaglio=vigente) | CIV_ORD, CIV_SUC | 171-ter, memoria n. 1, memoria n. 2, memoria n. 3, deduzioni istruttorie, memoria istruttoria |
| `cpc_rito_semplificato` | Codice di procedura civile - rito semplificato | specifica | normativa | specifica | [apri](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=040U1443&atto.dataPubblicazioneGazzetta=1940-10-28&tipoDettaglio=vigente) | CIV_INT, TMP-CIV | rito semplificato, 281-decies, 702-bis, semplificato |
| `cpc_procedimento_monitorio` | Codice di procedura civile - procedimento di ingiunzione | specifica | normativa | specifica | [apri](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=040U1443&atto.dataPubblicazioneGazzetta=1940-10-28&tipoDettaglio=vigente) | MON, TMP-CAUT | decreto ingiuntivo, ricorso per decreto ingiuntivo, monitorio, ingiunzione, opposizione a decreto ingiuntivo, provvisoria esecutorietà |
| `cpc_procedimenti_cautelari_uniformi` | Codice di procedura civile - procedimento cautelare uniforme | specifica | normativa | specifica | [apri](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=040U1443&atto.dataPubblicazioneGazzetta=1940-10-28&tipoDettaglio=vigente) | CAU, TMP-CAUT | cautelare, ricorso cautelare, reclamo cautelare, sequestro, inaudita altera parte, provvedimento urgente, urgenza |
| `cpc_art_700_urgenza` | Codice di procedura civile - provvedimenti d'urgenza | specifica | normativa | specifica | [apri](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=040U1443&atto.dataPubblicazioneGazzetta=1940-10-28&tipoDettaglio=vigente) | CAU, TMP-CAUT | 700, urgenza, provvedimento d'urgenza, ricorso cautelare d'urgenza |
| `cpc_sequestri` | Codice di procedura civile - sequestri | specifica | normativa | specifica | [apri](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=040U1443&atto.dataPubblicazioneGazzetta=1940-10-28&tipoDettaglio=vigente) | CAU, TMP-CAUT | sequestro conservativo, sequestro giudiziario, sequestro |
| `cpc_procedimenti_possessori` | Codice di procedura civile - procedimenti possessori | specifica | normativa | specifica | [apri](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=040U1443&atto.dataPubblicazioneGazzetta=1940-10-28&tipoDettaglio=vigente) | CIV, TMP-CAUT | possesso, possessoria, manutenzione nel possesso, reintegrazione nel possesso |
| `normattiva_d_lgs_149_2022_cartabia_civile` | Riforma civile Cartabia | specifica | normativa | riforma processuale | [apri](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=22G00158&atto.dataPubblicazioneGazzetta=2022-10-17&tipoDettaglio=originario) | CIV, CAU, ESE, FAM, ADR, LAV, CONC | cartabia, riforma civile, famiglia, 171-ter, 281-decies, mediazione, negoziazione assistita, esecuzione |
| `normattiva_d_lgs_164_2024_correttivo_cartabia_civile` | Correttivo Cartabia civile | specifica | normativa | riforma processuale | [apri](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=24G00183&atto.dataPubblicazioneGazzetta=2024-11-11&tipoDettaglio=vigente) | CIV, CAU, ESE, FAM, ADR, LAV, CONC | correttivo cartabia, processo civile, famiglia, esecuzione, negoziazione assistita, mediazione, rito |
| `pst_dm_44_2011` | Regole tecniche PCT | telematica | telematica | specifica | [apri](https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto:2011;44!vig=) | CIV, CAU, ESE, MON, GDP, FAM, LAV, RCD, BAN, SOC, IPD, CONC, TMP-CIV, TMP-CAUT, TMP-ESE, TMP-FAM, +3 | pct, pst, deposito telematico, datiatto, busta, reginde, processo civile telematico |
| `pst_specifiche_tecniche_pct` | Specifiche tecniche PCT/PST | telematica | telematica | specifica | [apri](https://pst.giustizia.it/PST/resources/cms/documents/SpecificheTecnicheTestoCoordinatoArticolato.pdf) | CIV, CAU, ESE, MON, GDP, FAM, LAV, CONC, TMP-CIV, TMP-CAUT, TMP-ESE, TMP-FAM, TMP-LAV, TMP-NOT, TMP-PROC | pct, pst, specifiche tecniche, deposito, allegati, busta, datiatto, pdf/a |
| `normattiva_dm_217_2023_giustizia_telematica` | Giustizia digitale - regole tecniche 2023 | secondaria_collegata | normativa secondaria | specifica | [apri](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=23G00224&atto.dataPubblicazioneGazzetta=2023-12-30&qId=&tipoDettaglio=originario) | CIV, CAU, ESE, MON, GDP, FAM, LAV, PEN, CONC, TMP-CIV, TMP-CAUT, TMP-ESE, TMP-FAM, TMP-LAV, TMP-NOT, TMP-PROC | deposito telematico, portale dei depositi telematici, giustizia digitale, dominio giustizia, ricevuta di accettazione, regole tecniche |
| `disp_att_cpc_art_196_quater_deposito_telematico` | Disposizioni di attuazione c.p.c. - deposito telematico | secondaria_collegata | normativa secondaria | specifica | [apri](https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1941-08-25;1368:1~art196quater=) | CIV, CAU, ESE, MON, GDP, FAM, LAV, CONC, TMP-CIV, TMP-CAUT, TMP-ESE, TMP-FAM, TMP-LAV, TMP-NOT, TMP-PROC | deposito telematico, obbligatorietà deposito telematico, sistemi non funzionanti, modalità non telematiche |
| `normattiva_dpr_115_2002_spese_giustizia` | Testo unico spese di giustizia | specifica | normativa | specifica | [apri](https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.presidente.repubblica:2002-05-30;115!vig=) | CIV, AMM, TRIB, FAM, LAV, CONC | contributo unificato, spese di giustizia, valore causa, nota iscrizione ruolo |
| `normattiva_legge_53_1994_notifiche` | Notificazioni in proprio dell'avvocato | specifica | normativa | specifica | [apri](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=094G0076&atto.dataPubblicazioneGazzetta=1994-01-26&tipoDettaglio=vigente) | CIV_NOT, STR, RCD, AMM, CON, BAN, TMP-NOT | notifica, relata, notificazione, pec, attestazione, conformita, consegna, accettazione |
| `normattiva_dpr_68_2005_pec` | Posta elettronica certificata | telematica | telematica | specifica | [apri](https://www.normattiva.it/uri-res/N2Ls?urn:nir:presidente.repubblica:decreto:2005-02-11;68=) | CIV_NOT, STR, PRI, CON, BAN, RCD, TMP-NOT, TMP-STR | pec, ricevuta, accettazione, consegna, busta di trasporto, dati di certificazione |
| `normattiva_cad_art_48` | Codice dell'amministrazione digitale - PEC e recapiti certificati | specifica | normativa | specifica | [apri](https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2005-03-07;82~art48=) | CIV_NOT, AMM, PRI, STR, TMP-NOT, TMP-STR | cad, domicilio digitale, pec, recapito certificato, pubblici elenchi |
| `normattiva_cpp` | Codice di procedura penale | base_comune | normativa | generale processuale | [apri](https://www.normattiva.it/eli/id/1988/10/24/088G0492/CONSOLIDATED) | PEN | penale, c.p.p, cpp, querela, denuncia, archiviazione, incidente probatorio, parte civile, impugnazione |
| `normattiva_codice_penale` | Codice penale | base_comune | normativa | sostanziale generale | [apri](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=030U1398&atto.dataPubblicazioneGazzetta=1930-10-26&tipoDettaglio=vigente) | PEN | reato, codice penale, delitto, contravvenzione, querela, denuncia, parte civile |
| `pst_pdp_penale` | Portale deposito atti penali | telematica | telematica | specifica | [apri](https://pst.giustizia.it/PST/resources/cms/documents/Specifiche_Tecniche_PPT_11.07.2023_post_DM_2023_signed.pdf) | PEN | pdp, ppt, deposito penale, portale deposito atti penali, atto penale telematico |
| `normattiva_d_lgs_150_2022_cartabia_penale` | Riforma penale Cartabia | specifica | normativa | riforma processuale | [apri](https://www.normattiva.it/eli/id/2022/10/17/22G00159/ORIGINAL) | PEN | cartabia penale, riforma penale, penale, impugnazione, querela |
| `pst_specifiche_penale_2024` | Specifiche tecniche deposito penale telematico | secondaria_collegata | telematica | specifica | [apri](https://pst.giustizia.it/PST/resources/cms/documents/m_dg.DOG07.07082024.0004292.ID_SPECIFICHETECNICHE_DM_44_2011_FINALE_31_.pdf) | PEN | deposito penale, processo penale telematico, specifiche tecniche, portale depositi telematici, richiesta copie |
| `normattiva_cpa` | Codice del processo amministrativo | specifica | normativa | specifica | [apri](https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2010-07-02;104@originale=) | AMM, TMP-AMM | amministrativo, tar, consiglio di stato, motivi aggiunti, ottemperanza, accesso agli atti, silenzio |
| `giustizia_amministrativa_pat` | Processo amministrativo telematico | telematica | telematica | specifica | [apri](https://www.giustizia-amministrativa.it/documents/20142/74204502/Pubblicazione%2BRegole%2Btecnico-operative%2BPAT.pdf/db2b8d35-4e88-c32a-a7c6-15715348d34b?t=1748969121419) | AMM, TMP-AMM | pat, siga, processo amministrativo telematico, modulo deposito, tar |
| `normattiva_decreto_22_05_2020_pat` | Regole tecnico-operative PAT | secondaria_collegata | normativa secondaria | specifica | [apri](https://www.normattiva.it/eli/id/2020/05/27/20A02846/ORIGINAL) | AMM, TMP-AMM | pat, siga, processo amministrativo telematico, modulo deposito, deposito amministrativo, ricorso tar |
| `giustizia_amministrativa_dpcs_2025_pat` | PAT - regole tecnico-operative aggiornate 2025 | secondaria_collegata | telematica | specifica | [apri](https://www.giustizia-amministrativa.it/en/-/152174-588) | AMM, TMP-AMM | pat, processo amministrativo telematico, regole tecniche-operative, depositi telematici, portali esterni |
| `normattiva_d_lgs_36_2023_appalti` | Codice dei contratti pubblici | specifica | normativa | specifica | [apri](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=23G00044&atto.dataPubblicazioneGazzetta=2023-03-31&tipoDettaglio=vigente) | AMM | appalto, appalti, gara, esclusione da gara, contratti pubblici, anac, precontenzioso |
| `anac_contratti_pubblici_pcp` | ANAC - Piattaforma contratti pubblici | autorita | autorita | specifica | [apri](https://www.anticorruzione.it/-/piattaforma-contratti%20-pubblici) | AMM | pcp, bdncp, anac, digitalizzazione contratti pubblici, contratti pubblici |
| `anac_precontenzioso_2023` | ANAC - pareri di precontenzioso | autorita | autorita | specifica | [apri](https://www.anticorruzione.it/-/regolamento-in-materia-di-pareri-di-precontenzioso-del.-n.-267-20.06.2023) | AMM | precontenzioso, parere anac, art. 220, gara |
| `normattiva_d_lgs_546_1992_tributario` | Processo tributario | specifica | normativa | specifica | [apri](https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:1992-12-31;546@originale=) | TRIB, TRI | tributario, corte di giustizia tributaria, ricorso tributario, sospensione, controdeduzioni, ptt |
| `giustizia_tributaria_ptt` | Processo tributario telematico | telematica | telematica | specifica | [apri](https://def.giustiziatributaria.gov.it/DocTribFrontend/executePrintArticolo.do?codiceOrdinamento=0000000000000010000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000&id=%7B9B8B2F76-C2FF-4972-BD82-69D51FB83CE1%7D&idAttoNormativo=%7B66C2D7E0-5F49-4C3F-9576-B05DFB713A20%7D) | TRIB, TRI | ptt, sigit, processo tributario telematico, deposito tributario |
| `normattiva_d_lgs_220_2023_contenzioso_tributario` | Riforma contenzioso tributario | specifica | normativa | riforma processuale | [apri](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=24G00001&atto.dataPubblicazioneGazzetta=2024-01-03&tipoDettaglio=vigente) | TRIB, TRI | contenzioso tributario, riforma fiscale, ricorso tributario, corte di giustizia tributaria, deposito tributario |
| `normattiva_dm_163_2013_ptt` | Processo tributario telematico - regole | secondaria_collegata | normativa secondaria | specifica | [apri](https://www.normattiva.it/uri-res/N2Ls?urn:nir:ministero.economia.e.finanze:decreto:2013-12-23;163!vig=) | TRIB, TRI | ptt, sigit, processo tributario telematico, deposito tributario, documento informatico, fascicolo informatico |
| `giustizia_tributaria_decreto_04_08_2015_specifiche_ptt` | PTT - specifiche tecniche | secondaria_collegata | telematica | specifica | [apri](https://def.giustiziatributaria.gov.it/DocTribFrontend/executePrintArticolo.do?codiceOrdinamento=0000000000000070000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000&id=%7BF26316C7-DFB9-4B44-9972-D2E9A54BCDE3%7D&idAttoNormativo=%7B66C2D7E0-5F49-4C3F-9576-B05DFB713A20%7D) | TRIB, TRI | ptt, sigit, specifiche tecniche, deposito tributario, anomalie, trasmissione telematica |
| `normattiva_d_lgs_28_2010_mediazione` | Mediazione civile e commerciale | specifica | normativa | specifica | [apri](https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2010-03-04;28=) | ADR, STR, CON, BAN, FAM | mediazione, mediatore, organismo, verbale di accordo, verbale di mancato accordo |
| `normattiva_dm_150_2023_mediazione` | Mediazione civile - registro, indennità e organismi | secondaria_collegata | normativa secondaria | specifica | [apri](https://www.normattiva.it/eli/id/2023/10/31/23G00163/CONSOLIDATED/20250124) | ADR, STR, CON, BAN, FAM | mediazione, organismo di mediazione, indennita mediazione, registro organismi, enti formazione, adr consumo |
| `giustizia_registro_mediazione_dm_150_2023` | Registro ministeriale organismi di mediazione | autorita | autorita | specifica | [apri](https://www.giustizia.it/giustizia/page/it/come_fare_per_iscriversi_al_registro_organismi_mediazione) | ADR, CON, BAN, FAM | mediazione, registro organismi, organismi mediazione, enti formazione, formatori mediazione |
| `normattiva_dl_132_2014_negoziazione` | Negoziazione assistita | specifica | normativa | specifica | [apri](https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto-legge:2014-09-12;132!vig=) | ADR, STR, FAM | negoziazione, invito a negoziazione, accordo di negoziazione, separazione negoziazione, divorzio negoziazione |
| `normattiva_d_lgs_216_2024_correttivo_adr` | Correttivo mediazione e negoziazione assistita | secondaria_collegata | normativa secondaria | correttivo ADR | [apri](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=25G00003&atto.dataPubblicazioneGazzetta=2025-01-10&tipoDettaglio=vigente) | ADR, STR, CON, BAN, FAM, RCD | mediazione, negoziazione assistita, correttivo mediazione, durata mediazione, piattaforma telematica mediazione, istruzione stragiudiziale |
| `normattiva_d_lgs_150_2011_riti` | Semplificazione dei riti civili | specifica | normativa | specifica | [apri](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=011G0192&atto.dataPubblicazioneGazzetta=2011-09-21&tipoDettaglio=vigente) | IMM, CIV, GDP | rito, opposizione, sanzione, immigrazione, protezione internazionale, semplificazione |
| `normattiva_legge_898_1970_divorzio` | Scioglimento del matrimonio e divorzio | specifica | normativa | specifica | [apri](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=070U0898&atto.dataPubblicazioneGazzetta=1970-12-03&currentPage=1) | FAM | divorzio, scioglimento matrimonio, cessazione effetti civili, assegno divorzile |
| `normattiva_legge_184_1983_adozione` | Adozione e affidamento dei minori | specifica | normativa | specifica | [apri](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=083U0184&atto.dataPubblicazioneGazzetta=1983-05-17&tipoDettaglio=vigente) | FAM, VGS | adozione, affidamento minore, minore, curatore speciale, giudice tutelare |
| `normattiva_d_lgs_154_2013_filiazione` | Filiazione e responsabilita genitoriale | specifica | normativa | specifica | [apri](https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2013;154!vig=) | FAM, VGS | filiazione, responsabilita genitoriale, affidamento, mantenimento figli, ascolto del minore |
| `normattiva_legge_76_2016_unioni_civili` | Unioni civili e convivenze | specifica | normativa | specifica | [apri](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=16G00082&atto.dataPubblicazioneGazzetta=2016-05-21&tipoDettaglio=vigente) | FAM, STR | unione civile, convivenza, conviventi, coppia |
| `normattiva_l_300_1970_statuto_lavoratori` | Statuto dei lavoratori | specifica | normativa | specifica | [apri](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=070U0300&atto.dataPubblicazioneGazzetta=1970-05-27&tipoDettaglio=vigente) | LAV | lavoro, lavoratore, datore, licenziamento, reintegra, mansioni, sindacale, controllo |
| `normattiva_l_604_1966_licenziamenti` | Licenziamenti individuali | specifica | normativa | specifica | [apri](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=066U0604&atto.dataPubblicazioneGazzetta=1966-08-06&tipoDettaglio=vigente) | LAV | licenziamento, giusta causa, giustificato motivo, impugnazione licenziamento |
| `normattiva_d_lgs_23_2015_tutele_crescenti` | Contratto a tutele crescenti | specifica | normativa | specifica | [apri](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=15G00037&atto.dataPubblicazioneGazzetta=2015-03-06&tipoDettaglio=vigente) | LAV | tutele crescenti, licenziamento, jobs act, indennita |
| `normattiva_d_lgs_81_2015_lavoro` | Disciplina organica contratti di lavoro | specifica | normativa | specifica | [apri](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=15G00095&atto.dataPubblicazioneGazzetta=2015-06-24&tipoDettaglio=vigente) | LAV | contratto di lavoro, termine, part-time, somministrazione, mansione |
| `normattiva_d_lgs_151_2015_dimissioni_telematiche` | Semplificazioni lavoro e dimissioni telematiche | specifica | normativa | specifica lavoro | [apri](https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2015;151=) | LAV | dimissioni, risoluzione consensuale, dimissioni telematiche, revoca dimissioni, rapporto di lavoro |
| `lavoro_dm_15_12_2015_dimissioni_telematiche` | Dimissioni telematiche - modulo e regole tecniche | secondaria_collegata | normativa secondaria | specifica | [apri](https://www.lavoro.gov.it/documenti-e-norme/normative/Documents/2015/Decreto_ministeriale_15_dicembre_2015) | LAV | dimissioni telematiche, modulo dimissioni, revoca dimissioni, standard tecnici, ministero lavoro |
| `inl_contestazione_licenziamento_gmo` | INL - contestazione licenziamento per giustificato motivo oggettivo | autorita | autorita | specifica | [apri](https://www.ispettorato.gov.it/servizi-e-modulistica/modalita-di-contestazione-del-licenziamento/) | LAV | licenziamento, giustificato motivo oggettivo, conciliazione, ispettorato, articolo 7 |
| `normattiva_l_223_1991_licenziamenti_collettivi` | Licenziamenti collettivi | specifica | normativa | specifica | [apri](https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1991;223~art24!vig=) | LAV | licenziamento collettivo, mobilita, procedura collettiva, criteri di scelta, riduzione personale |
| `normattiva_tub_385_1993` | Testo unico bancario | specifica | normativa | specifica | [apri](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=093G0428&atto.dataPubblicazioneGazzetta=1993-09-30&tipoDettaglio=vigente) | BAN | bancario, banca, mutuo, conto corrente, fideiussione, centrale rischi, abf, intermediario finanziario |
| `abf_normativa` | Arbitro Bancario Finanziario | autorita | autorita | specifica | [apri](https://www.arbitrobancariofinanziario.it/abf/normativa/index.html) | BAN | abf, arbitro bancario, ricorso abf, banca d'italia |
| `bancaditalia_trasparenza_operazioni_2025` | Trasparenza bancaria e correttezza intermediari | secondaria_collegata | autorita | specifica | [apri](https://www.bancaditalia.it/compiti/vigilanza/normativa/archivio-norme/disposizioni/trasparenza_operazioni/2025.02.13/SMDD-Disposizioni-di-trasparenza.pdf) | BAN | trasparenza bancaria, intermediario, cliente banca, reclamo banca, contratto bancario, credito, mutuo |
| `bancaditalia_abf_disposizioni_2025` | ABF - disposizioni procedurali | autorita | autorita | specifica | [apri](https://www.arbitrobancariofinanziario.it/abf/normativa/index.html) | BAN | abf, ricorso abf, arbitro bancario, reclamo banca, controversia bancaria, banca d'italia |
| `normattiva_tuf_58_1998` | Testo unico della finanza | specifica | normativa | specifica | [apri](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=098G0074&atto.dataPubblicazioneGazzetta=1998-03-26&tipoDettaglio=vigente) | BAN, SOC | finanziario, investimento, intermediario, consob, acf, strumenti finanziari |
| `acf_consob` | Arbitro per le Controversie Finanziarie | autorita | autorita | specifica | [apri](https://www.acf.consob.it/normativa/normativa-acf) | BAN, SOC | acf, arbitro controversie finanziarie, consob, investitore retail |
| `consob_acf_delibere_regolamento_2023` | ACF - regolamento e delibere Consob | autorita | autorita | specifica | [apri](https://www.acf.consob.it/normativa/normativa-acf) | BAN, SOC | acf, consob, ricorso acf, intermediario finanziario, investitore retail, regolamento acf |
| `normattiva_codice_assicurazioni_209_2005` | Codice delle assicurazioni private | specifica | normativa | specifica | [apri](https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2005;209) | RCD | assicurazione, assicurativo, sinistro, rc auto, polizza, ivass |
| `ivass_arbitro_assicurativo` | Arbitro Assicurativo | autorita | autorita | specifica | [apri](https://www.ivass.it/consumatori/aas/index.html) | RCD | arbitro assicurativo, aas, ivass, reclamo assicurazione, sinistro |
| `normattiva_dm_215_2024_arbitro_assicurativo` | Arbitro Assicurativo - regolamento | secondaria_collegata | normativa secondaria | specifica | [apri](https://www.normattiva.it/eli/id/2025/01/09/25G00001/ORIGINAL) | RCD | arbitro assicurativo, aas, ricorso assicurativo, reclamo assicurazione, controversia assicurativa |
| `ivass_provvedimento_106122_2025_aas` | AAS - disposizioni tecniche e attuative | secondaria_collegata | autorita | specifica | [apri](https://www.ivass.it/normativa/nazionale/secondaria-ivass/amministrativi-provv/2025/106122/index.html?dotcache=refresh) | RCD | arbitro assicurativo, aas, ivass, provvedimento 106122, ricorso assicurativo, pec arbitro |
| `normattiva_codice_consumo_206_2005` | Codice del consumo | specifica | normativa | specifica | [apri](https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2005;206!vig=) | CON | consumatore, garanzia, e-commerce, clausole vessatorie, rimborso, fornitore, telefonico, energia |
| `agcom_conciliaweb` | ConciliaWeb | autorita | autorita | specifica | [apri](https://www.agcom.it/competenze/consumatori/controversie-tra-utenti-finali-e-fornitori-di-servizi-di-comunicazioni-2023/procedura-di-conciliazione) | CON | conciliaweb, agcom, operatore telefonico, telefonico, comunicazioni elettroniche |
| `agcom_delibera_203_18_conciliaweb` | ConciliaWeb - regolamento controversie comunicazioni | secondaria_collegata | autorita | specifica | [apri](https://www.agcom.it/provvedimenti/delibera-203-18-cons) | CON | conciliaweb, agcom, corecom, controversie utenti operatori, telefonico, comunicazioni elettroniche |
| `agcom_delibera_194_23_cons_conciliaweb` | ConciliaWeb - modifiche regolamento 2023 | secondaria_collegata | autorita | specifica | [apri](https://www.agcom.it/sites/default/files/migration/delibera/Delibera%20194-23-CONS.pdf) | CON | conciliaweb, agcom, delibera 194/23, controversie comunicazioni, utenti operatori |
| `garante_gdpr` | GDPR - Garante Privacy | autorita | autorita | specifica | [apri](https://www.garanteprivacy.it/regolamentoue) | PRI, IPD, STR | privacy, gdpr, dati personali, data breach, profilazione, informativa, accesso ai dati, cancellazione dati |
| `garante_cookie_linee_guida_2021` | Cookie e altri strumenti di tracciamento | secondaria_collegata | autorita | specifica | [apri](https://www.garanteprivacy.it/web/guest/home/docweb/-/docweb-display/docweb/9677876%26nbsp) | PRI, IPD, STR | cookie, tracciamento, profilazione, consenso, informativa privacy, sito web |
| `eurlex_gdpr` | Regolamento (UE) 2016/679 | specifica | normativa | specifica | [apri](https://eur-lex.europa.eu/eli/reg/2016/679/oj/ita) | PRI, IPD, STR | gdpr, base giuridica, trattamento, interessato, informativa, diritti privacy |
| `normattiva_privacy_196_2003` | Codice privacy | specifica | normativa | specifica | [apri](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=003G0218&atto.dataPubblicazioneGazzetta=2003-07-29&tipoDettaglio=vigente) | PRI, IPD | privacy, dati personali, garante, trattamento illecito |
| `normattiva_d_lgs_101_2018_adeguamento_gdpr` | Adeguamento nazionale al GDPR | specifica | normativa | fonte collegata privacy | [apri](https://www.normattiva.it/eli/id/2018/09/04/18G00129/CONSOLIDATED/20231130) | PRI, IPD | privacy, gdpr, adeguamento, codice privacy, reclamo garante, diritti interessato |
| `normattiva_cpi_30_2005` | Codice della proprieta industriale | specifica | normativa | specifica | [apri](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=005G0055&atto.dataPubblicazioneGazzetta=2005-03-04&tipoDettaglio=vigente) | IPD, SOC | marchio, brevetto, contraffazione, proprieta industriale, inibitoria, nome a dominio |
| `uibm_deposito_telematico_proprieta_industriale` | UIBM - deposito telematico proprieta industriale | secondaria_collegata | autorita | specifica | [apri](https://uibm.mise.gov.it/index.php/it/i-servizi/assistenza-deposito-telmatico) | IPD, SOC | uibm, deposito telematico, marchio, brevetto, disegno, modello, rinnovo marchio, proprieta industriale |
| `normattiva_diritto_autore_633_1941` | Diritto d'autore | specifica | normativa | specifica | [apri](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=041U0633&atto.dataPubblicazioneGazzetta=1941-07-16&tipoDettaglio=vigente) | IPD | copyright, diritto d'autore, plagio, immagini, contenuti web, software, licenza |
| `siae_diritto_autore_repertori` | SIAE - diritto d'autore e repertori | secondaria_collegata | fonte collegata | specifica | [apri](https://www.siae.it/it/autori-ed-editori/diritto-autore/) | IPD | siae, diritto d'autore, repertorio, deposito opera, opera creativa, compenso autore, utilizzazione opere |
| `normattiva_codice_crisi_14_2019` | Codice della crisi d'impresa e dell'insolvenza | specifica | normativa | specifica | [apri](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=19G00007&atto.dataPubblicazioneGazzetta=2019-02-14&tipoDettaglio=vigente) | CONC, TMP-IMP | crisi, insolvenza, liquidazione giudiziale, concordato, esdebitazione, stato passivo, curatore |
| `normattiva_d_lgs_136_2024_correttivo_crisi` | Correttivo Codice della crisi d'impresa | secondaria_collegata | normativa secondaria | correttivo crisi | [apri](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=24G00154&atto.dataPubblicazioneGazzetta=2024-09-27&tipoDettaglio=vigente) | CONC, TMP-IMP | crisi, insolvenza, correttivo crisi, concordato, liquidazione giudiziale, sovraindebitamento, esdebitazione |
| `pst_portale_vendite_pubbliche_specifiche_concorsuali` | Portale Vendite Pubbliche e procedure concorsuali | secondaria_collegata | telematica | specifica | [apri](https://pst.giustizia.it/PST/resources/cms/documents/BDAG_ST_V1.2_23092024.pdf) | CONC, ESE, TMP-IMP | portale vendite pubbliche, pvp, procedure concorsuali, vendite, liquidazione giudiziale, bdag |
| `normattiva_legge_fallimentare_267_1942_transitoria` | Legge fallimentare - solo procedure anteriori/transitorie | specifica | normativa | transitoria | [apri](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=042U0267&atto.dataPubblicazioneGazzetta=1942-04-06&tipoDettaglio=vigente) | CONC | fallimento, legge fallimentare, procedura fallimentare previgente |
| `normattiva_tu_immigrazione_286_1998` | Testo unico immigrazione | specifica | normativa | specifica | [apri](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=098G0348&atto.dataPubblicazioneGazzetta=1998-08-18&tipoDettaglio=vigente) | IMM | immigrazione, permesso di soggiorno, espulsione, ricongiungimento, straniero |
| `normattiva_d_lgs_25_2008_protezione_internazionale` | Procedure per il riconoscimento della protezione internazionale | specifica | normativa | procedura protezione internazionale | [apri](https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2008-01-28;25=) | IMM | protezione internazionale, commissione territoriale, richiedente asilo, ricorso protezione, audizione, videoregistrazione |
| `interno_protezione_internazionale_commissioni` | Ministero dell'Interno - protezione internazionale | autorita | autorita | specifica | [apri](https://www.interno.gov.it/it/temi/immigrazione-e-asilo/protezione-internazionale) | IMM | protezione internazionale, ministero interno, commissione territoriale, commissione nazionale asilo, rifugiato, protezione sussidiaria |
| `normattiva_legge_392_1978_locazioni` | Locazioni immobili urbani | specifica | normativa | specifica | [apri](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=078U0392&atto.dataPubblicazioneGazzetta=1978-07-29&tipoDettaglio=vigente) | LOC, CIV_SFR, STR, TMP-STR | locazione, sfratto, morosita, canone, rilascio immobile |
| `normattiva_legge_431_1998_locazioni_abitative` | Locazioni abitative | specifica | normativa | specifica | [apri](https://www.normattiva.it/eli/id/1998/12/15/098G0483/CONSOLIDATED) | LOC, CIV_SFR, STR | locazione abitativa, rilascio, disdetta, canone abitativo |
| `agenzia_entrate_rli_locazioni` | Agenzia Entrate - RLI Web locazioni | secondaria_collegata | autorita | specifica | [apri](https://apptel.agenziaentrate.gov.it/RliWeb/) | LOC, CIV_SFR, STR, TMP-STR | rli, locazione, registrazione contratto locazione, cedolare secca, imposta di registro, adempimenti successivi, proroga, risoluzione |
| `normattiva_codice_strada_285_1992` | Codice della strada | specifica | normativa | specifica | [apri](https://www.normattiva.it/eli/stato/DECRETO_LEGISLATIVO/1992/04/30/285/CONSOLIDATED) | RCD, GDP | sinistro stradale, codice della strada, verbale, opposizione sanzione, rc auto |
| `normattiva_dpr_495_1992_regolamento_codice_strada` | Regolamento di esecuzione del Codice della strada | secondaria_collegata | normativa secondaria | specifica | [apri](https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.presidente.repubblica:1992;495=) | RCD, GDP | codice della strada, regolamento esecuzione, verbale, segnaletica, opposizione sanzione, sinistro stradale |
| `normattiva_l_247_2012_ordinamento_forense` | Ordinamento della professione forense | ordinamento_professionale | ordinamento professionale | specifica | [apri](https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:2012-12-31;247=) | STR_INC, STR_PREV, CIV_PROC, STD, PRI, SOC, STR, TMP-CIV, TMP-CAUT, TMP-ESE, TMP-FAM, TMP-LAV, TMP-NOT, TMP-PROC, TMP-STR | avvocato, mandato, incarico professionale, compenso, cliente, rinuncia al mandato, revoca mandato, deontologia |
| `cnf_codice_deontologico_forense` | Codice deontologico forense | deontologia | deontologia | specifica | [apri](https://codicedeontologico-cnf.it/) | STR_INC, STR_PREV, CIV_PROC, STD, PRI, STR, SOC, PEN, FAM, LAV, TMP-CIV, TMP-CAUT, TMP-ESE, TMP-FAM, TMP-LAV, TMP-NOT, +2 | deontologia, codice deontologico, riservatezza, segreto professionale, informazione al cliente, compenso, mandato, rinuncia, restituzione documenti, controparte |
| `cnf_cdf_art_24_conflitto_interessi` | Codice deontologico forense - conflitto di interessi | deontologia | deontologia | specifica | [apri](https://codicedeontologico-cnf.it/voci/art-24-cdf-conflitto-di-interessi/) | STD, STR_INC, CIV_PROC, FAM, PEN | conflitto di interessi, interessi confliggenti, parte già assistita, ex cliente, curatore speciale, controparte già assistita |
| `cnf_cdf_art_25_compensi` | Codice deontologico forense - accordi sul compenso | deontologia | deontologia | specifica | [apri](https://codicedeontologico-cnf.it/voci/art-25-cdf-accordi-sulla-definizione-del-compenso/) | STR_PREV, STR_INC, STD | compenso, preventivo, onorario, patto di quota lite, accordo compenso, pattuizione compensi |
| `gu_cdf_art_25_bis_equo_compenso_2026` | Codice deontologico forense - art. 25-bis equo compenso | deontologia | deontologia | specifica | [apri](https://www.gazzettaufficiale.it/eli/id/2026/02/05/26A00480/SG) | STR_PREV, STR_INC, STD, SOC | equo compenso, 25-bis, cliente forte, grande impresa, compenso non equo, convenzione professionale |
| `normattiva_l_49_2023_equo_compenso` | Equo compenso prestazioni professionali | specifica | normativa | specifica | [apri](https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:2023-04-21;49=) | STR_PREV, STR_INC, STD, SOC | equo compenso, cliente forte, grande impresa, convenzione professionale, compenso non equo |
| `cnf_cdf_art_26_adempimento_mandato` | Codice deontologico forense - adempimento del mandato | deontologia | deontologia | specifica | [apri](https://codicedeontologico-cnf.it/voci/art-26-cdf-adempimento-del-mandato/) | STD, STR_INC, CIV_PROC, PEN, FAM, LAV, AMM, TRI, TRIB, TMP-CIV, TMP-CAUT, TMP-ESE, TMP-FAM, TMP-LAV, TMP-NOT, TMP-PROC, +1 | mandato, adempimento mandato, incarico, competenza professionale, negligenza, ritardo, atti necessari |
| `cnf_cdf_art_27_informazione_cliente` | Codice deontologico forense - doveri di informazione | deontologia | deontologia | specifica | [apri](https://codicedeontologico-cnf.it/voci/art-27-cdf-doveri-di-informazione/) | STD, STR_INC, STR_PREV, ADR, FAM, LAV, PEN, AMM, TRI, TRIB, TMP-CIV, TMP-CAUT, TMP-ESE, TMP-FAM, TMP-LAV, TMP-NOT, +2 | informazione al cliente, dovere di informazione, costo prevedibile, rischi, negoziazione assistita, mandato, cliente |
| `cnf_cdf_art_28_segreto_professionale` | Codice deontologico forense - riserbo e segreto professionale | deontologia | deontologia | specifica | [apri](https://codicedeontologico-cnf.it/voci/art-28-cdf-riserbo-e-segreto-professionale/) | STD, STR_INC, PRI, PEN, FAM, SOC | segreto professionale, riserbo, riservatezza, documenti del cliente, dati del cliente, privacy studio |
| `cnf_cdf_art_29_richiesta_pagamento` | Codice deontologico forense - richiesta di pagamento | deontologia | deontologia | specifica | [apri](https://codicedeontologico-cnf.it/voci/art-29-cdf-richiesta-di-pagamento/) | STR_PREV, STR_INC, STD | pagamento, acconto, anticipo, nota spese, documento fiscale, compenso sproporzionato, patrocinio a spese dello stato |
| `gu_cdf_titolo_iv_adr_2025` | Codice deontologico forense - Titolo IV e negoziazione assistita | deontologia | deontologia | specifica | [apri](https://www.gazzettaufficiale.it/atto/serie_generale/caricaDettaglioAtto/originario?atto.codiceRedazionale=25A04804&atto.dataPubblicazioneGazzetta=2025-09-01&elenco30giorni=true) | ADR, FAM, CIV, LAV, STR | negoziazione assistita, adr, processo, risoluzione alternativa, titolo iv, 62-bis |
| `cnf_cdf_art_68_ex_cliente` | Codice deontologico forense - incarichi contro parte già assistita | deontologia | deontologia | specifica | [apri](https://codicedeontologico-cnf.it/voci/art-68-cdf-assunzione-di-incarichi-contro-una-parte-gia-assistita/) | FAM, STD, STR_INC, CIV_PROC | parte già assistita, ex cliente, contro ex cliente, controparte già assistita, curatore speciale del minore, genitore contro l'altro |
| `normattiva_dm_55_2014_parametri_forensi` | Parametri forensi | ordinamento_professionale | ordinamento professionale | specifica | [apri](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=014G00067&atto.dataPubblicazioneGazzetta=2014-04-02&tipoDettaglio=vigente) | STR_PREV, STR_INC, STD | preventivo, compenso, onorario, parametri forensi, incarico |

## Matrice completa modelli

| Origine | Codice | Modello | Stato | Ruoli fonte | Fonti valide | Problemi |
| --- | --- | --- | --- | --- | ---: | --- |
| catalogo_unificato | `ADR_001` | Invito alla mediazione | OK | autorita, deontologia, secondaria_collegata, specifica | 9 / collegate 5 | - |
| catalogo_unificato | `ADR_002` | Istanza di mediazione | OK | autorita, deontologia, secondaria_collegata, specifica | 9 / collegate 5 | - |
| catalogo_unificato | `ADR_003` | Adesione alla mediazione | OK | autorita, deontologia, secondaria_collegata, specifica | 9 / collegate 5 | - |
| catalogo_unificato | `ADR_004` | Verbale di accordo | OK | autorita, deontologia, secondaria_collegata, specifica | 11 / collegate 6 | - |
| catalogo_unificato | `ADR_005` | Verbale di mancato accordo | OK | autorita, deontologia, secondaria_collegata, specifica | 11 / collegate 6 | - |
| catalogo_unificato | `ADR_006` | Invito a negoziazione assistita | OK | autorita, deontologia, secondaria_collegata, specifica | 9 / collegate 5 | - |
| catalogo_unificato | `ADR_007` | Accordo di negoziazione assistita | OK | autorita, deontologia, secondaria_collegata, specifica | 9 / collegate 5 | - |
| catalogo_unificato | `ADR_008` | Diniego a negoziazione | OK | autorita, deontologia, secondaria_collegata, specifica | 9 / collegate 5 | - |
| catalogo_unificato | `ADR_009` | Clausola compromissoria standard | OK | autorita, deontologia, secondaria_collegata, specifica | 9 / collegate 5 | - |
| catalogo_unificato | `ADR_010` | Domanda di arbitrato | OK | autorita, deontologia, secondaria_collegata, specifica | 9 / collegate 5 | - |
| catalogo_unificato | `ADR_011` | Nomina arbitro | OK | autorita, deontologia, secondaria_collegata, specifica | 9 / collegate 5 | - |
| catalogo_unificato | `ADR_012` | Comparsa nel procedimento arbitrale | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica | 10 / collegate 5 | - |
| catalogo_unificato | `ADR_013` | Memoria arbitrale | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica | 9 / collegate 5 | - |
| catalogo_unificato | `ADR_014` | Accordo transattivo finale | OK | autorita, deontologia, secondaria_collegata, specifica | 9 / collegate 5 | - |
| catalogo_unificato | `AMM_001` | Ricorso al TAR | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| catalogo_unificato | `AMM_002` | Motivi aggiunti | OK | autorita, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| catalogo_unificato | `AMM_003` | Ricorso incidentale | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| catalogo_unificato | `AMM_004` | Domanda cautelare | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 13 / collegate 7 | - |
| catalogo_unificato | `AMM_005` | Memoria difensiva amministrativa | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| catalogo_unificato | `AMM_006` | Replica amministrativa | OK | autorita, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| catalogo_unificato | `AMM_007` | Istanza di prelievo | OK | autorita, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| catalogo_unificato | `AMM_008` | Istanza di accesso al fascicolo | OK | autorita, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| catalogo_unificato | `AMM_009` | Ricorso per accesso agli atti | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| catalogo_unificato | `AMM_010` | Ricorso per silenzio-inadempimento | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 13 / collegate 7 | - |
| catalogo_unificato | `AMM_011` | Appello al Consiglio di Stato | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| catalogo_unificato | `AMM_012` | Opposizione a decreto | OK | autorita, deontologia, secondaria_collegata, specifica, telematica | 13 / collegate 7 | - |
| catalogo_unificato | `AMM_013` | Ricorso per ottemperanza | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| catalogo_unificato | `AMM_014` | Ricorso in materia di appalti pubblici | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| catalogo_unificato | `AMM_015` | Ricorso per esclusione da gara | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| catalogo_unificato | `AMM_016` | Ricorso per revoca o annullamento di concessione | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| catalogo_unificato | `AMM_017` | Ricorso per sanzioni amministrative di settore | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| catalogo_unificato | `AMM_018` | Istanza di oscuramento dati | OK | autorita, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| catalogo_unificato | `BAN_001` | Diffida per consegna di documentazione bancaria | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 18 / collegate 11 | - |
| catalogo_unificato | `BAN_002` | Richiesta estratti conto ex art. 119 TUB | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 18 / collegate 11 | - |
| catalogo_unificato | `BAN_003` | Atto di citazione per anatocismo | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 18 / collegate 11 | - |
| catalogo_unificato | `BAN_004` | Atto di citazione per usura bancaria | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 18 / collegate 11 | - |
| catalogo_unificato | `BAN_005` | Azione di ripetizione di indebito bancario | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 18 / collegate 11 | - |
| catalogo_unificato | `BAN_006` | Atto in materia di fideiussione omnibus | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 18 / collegate 11 | - |
| catalogo_unificato | `BAN_007` | Opposizione a decreto su saldo di conto | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 19 / collegate 11 | - |
| catalogo_unificato | `BAN_008` | Perizia econometrica introduttiva | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 18 / collegate 11 | - |
| catalogo_unificato | `BAN_009` | Memoria di contestazione interessi e usura | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 18 / collegate 11 | - |
| catalogo_unificato | `BAN_010` | Opposizione a iscrizione in centrale rischi | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 20 / collegate 12 | - |
| catalogo_unificato | `BAN_011` | Diffida a intermediario finanziario | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 18 / collegate 11 | - |
| catalogo_unificato | `BAN_012` | Ricorso ABF preparatorio interno | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 18 / collegate 11 | - |
| catalogo_unificato | `CAU_001` | Ricorso ex art. 700 c.p.c. | OK | base_comune, secondaria_collegata, specifica, telematica | 9 / collegate 4 | - |
| catalogo_unificato | `CAU_002` | Reclamo cautelare | OK | base_comune, secondaria_collegata, specifica, telematica | 9 / collegate 4 | - |
| catalogo_unificato | `CAU_003` | Memoria del resistente in cautelare | OK | base_comune, secondaria_collegata, specifica, telematica | 9 / collegate 4 | - |
| catalogo_unificato | `CAU_004` | Istanza di provvedimento inaudita altera parte | OK | base_comune, secondaria_collegata, specifica, telematica | 9 / collegate 4 | - |
| catalogo_unificato | `CAU_005` | Sequestro conservativo | OK | base_comune, secondaria_collegata, specifica, telematica | 9 / collegate 4 | - |
| catalogo_unificato | `CAU_006` | Sequestro giudiziario | OK | base_comune, secondaria_collegata, specifica, telematica | 9 / collegate 4 | - |
| catalogo_unificato | `CAU_007` | Ricorso per ATP | OK | base_comune, secondaria_collegata, specifica, telematica | 9 / collegate 4 | - |
| catalogo_unificato | `CAU_008` | Ricorso per ATP ex art. 696-bis c.p.c. | OK | base_comune, secondaria_collegata, specifica, telematica | 9 / collegate 4 | - |
| catalogo_unificato | `CAU_009` | Istanza di nomina CTU preventiva | OK | base_comune, secondaria_collegata, specifica, telematica | 9 / collegate 4 | - |
| catalogo_unificato | `CAU_010` | Ricorso di reintegra nel possesso | OK | base_comune, secondaria_collegata, specifica, telematica | 11 / collegate 4 | - |
| catalogo_unificato | `CAU_011` | Ricorso di manutenzione nel possesso | OK | base_comune, secondaria_collegata, specifica, telematica | 10 / collegate 4 | - |
| catalogo_unificato | `CAU_012` | Denuncia di nuova opera | OK | base_comune, secondaria_collegata, specifica, telematica | 9 / collegate 4 | - |
| catalogo_unificato | `CAU_013` | Denuncia di danno temuto | OK | base_comune, secondaria_collegata, specifica, telematica | 9 / collegate 4 | - |
| catalogo_unificato | `CAU_014` | Istanza di sospensione della delibera | OK | base_comune, secondaria_collegata, specifica, telematica | 10 / collegate 4 | - |
| catalogo_unificato | `CAU_015` | Ricorso cautelare societario | OK | base_comune, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| catalogo_unificato | `CAU_016` | Ricorso urgente per consegna o rilascio | OK | base_comune, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CAU_017` | Ricorso inibitorio urgente | OK | base_comune, secondaria_collegata, specifica, telematica | 9 / collegate 4 | - |
| catalogo_unificato | `CIV_ORD_001` | Atto di citazione ordinario | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_002` | Atto di citazione con chiamata del terzo | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_003` | Atto di citazione con domanda riconvenzionale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_004` | Atto di citazione per adempimento contrattuale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_005` | Atto di citazione per risoluzione contrattuale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 15 / collegate 6 | - |
| catalogo_unificato | `CIV_ORD_006` | Atto di citazione per ripetizione di indebito | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_007` | Atto di citazione per arricchimento senza causa | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_008` | Atto di citazione per accertamento negativo del credito | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 15 / collegate 6 | - |
| catalogo_unificato | `CIV_ORD_009` | Comparsa di costituzione e risposta | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_010` | Comparsa con domanda riconvenzionale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_011` | Comparsa con chiamata del terzo | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_012` | Memoria ex art. 171-ter n. 1 c.p.c. | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_013` | Memoria ex art. 171-ter n. 2 c.p.c. | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_014` | Memoria ex art. 171-ter n. 3 c.p.c. | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_015` | Nota di deposito documenti | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_016` | Deduzioni istruttorie | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_017` | Capitoli di prova testimoniale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_018` | Istanza di interpello formale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_019` | Istanza di ordine di esibizione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_020` | Istanza di CTU | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_021` | Osservazioni alla CTU | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_022` | Note critiche alla CTU | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_023` | Istanza di sostituzione CTU | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_024` | Istanza di anticipazione udienza | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_025` | Istanza di rinvio udienza | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_026` | Istanza di trattazione scritta | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_027` | Istanza di discussione orale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_028` | Istanza di passaggio in decisione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_029` | Comparsa conclusionale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_030` | Memoria di replica | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_031` | Nota spese | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 15 / collegate 6 | - |
| catalogo_unificato | `CIV_ORD_032` | Istanza di distrazione spese | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_033` | Rinuncia agli atti | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 15 / collegate 6 | - |
| catalogo_unificato | `CIV_ORD_034` | Accettazione rinuncia | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 17 / collegate 7 | - |
| catalogo_unificato | `CIV_ORD_035` | Riassunzione dopo interruzione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_036` | Riassunzione dopo sospensione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 15 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_037` | Istanza di correzione errore materiale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_038` | Istanza di estinzione del giudizio | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CONC_001` | Domanda di insinuazione al passivo | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 22 / collegate 13 | - |
| catalogo_unificato | `CONC_002` | Domanda tardiva di insinuazione | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 24 / collegate 14 | - |
| catalogo_unificato | `CONC_003` | Opposizione allo stato passivo | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 23 / collegate 13 | - |
| catalogo_unificato | `CONC_004` | Istanza di rivendica | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 22 / collegate 13 | - |
| catalogo_unificato | `CONC_005` | Istanza di restituzione | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 22 / collegate 13 | - |
| catalogo_unificato | `CONC_006` | Domanda di ammissione di credito privilegiato | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `CONC_007` | Ricorso per liquidazione controllata | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 22 / collegate 13 | - |
| catalogo_unificato | `CONC_008` | Istanza al curatore | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 22 / collegate 13 | - |
| catalogo_unificato | `CONC_009` | Reclamo contro provvedimento del giudice delegato | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 22 / collegate 13 | - |
| catalogo_unificato | `CONC_010` | Domanda di esdebitazione | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 22 / collegate 13 | - |
| catalogo_unificato | `CONC_011` | Domanda di concordato minore | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 22 / collegate 13 | - |
| catalogo_unificato | `CONC_012` | Domanda del consumatore | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 22 / collegate 13 | - |
| catalogo_unificato | `CONC_013` | Osservazioni al piano | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 22 / collegate 13 | - |
| catalogo_unificato | `CONC_014` | Memoria dei creditori | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `CONC_015` | Istanza di autorizzazione ad atti del liquidatore | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 23 / collegate 13 | - |
| catalogo_unificato | `CON_001` | Diffida a operatore telefonico | OK | autorita, secondaria_collegata, specifica, telematica | 11 / collegate 7 | - |
| catalogo_unificato | `CON_002` | Diffida a fornitore di energia | OK | autorita, secondaria_collegata, specifica, telematica | 11 / collegate 7 | - |
| catalogo_unificato | `CON_003` | Diffida a fornitore di acqua | OK | autorita, secondaria_collegata, specifica, telematica | 11 / collegate 7 | - |
| catalogo_unificato | `CON_004` | Reclamo per trasporto aereo | OK | autorita, secondaria_collegata, specifica, telematica | 11 / collegate 7 | - |
| catalogo_unificato | `CON_005` | Reclamo per trasporto ferroviario | OK | autorita, secondaria_collegata, specifica, telematica | 11 / collegate 7 | - |
| catalogo_unificato | `CON_006` | Richiesta rimborso pacchetto turistico | OK | autorita, secondaria_collegata, specifica, telematica | 11 / collegate 7 | - |
| catalogo_unificato | `CON_007` | Diffida a e-commerce per mancata consegna | OK | autorita, secondaria_collegata, specifica, telematica | 11 / collegate 7 | - |
| catalogo_unificato | `CON_008` | Richiesta rimborso per acquisto difettoso | OK | autorita, secondaria_collegata, specifica, telematica | 11 / collegate 7 | - |
| catalogo_unificato | `CON_009` | Diffida per garanzia legale di conformità | OK | autorita, secondaria_collegata, specifica, telematica | 13 / collegate 8 | - |
| catalogo_unificato | `CON_010` | Invito a conciliazione paritetica | OK | autorita, secondaria_collegata, specifica, telematica | 12 / collegate 8 | - |
| catalogo_unificato | `CON_011` | Ricorso GDP del consumatore | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 11 / collegate 7 | - |
| catalogo_unificato | `CON_012` | Atto su clausole vessatorie | OK | autorita, secondaria_collegata, specifica, telematica | 11 / collegate 7 | - |
| catalogo_unificato | `ESE_001` | Atto di precetto | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 5 | - |
| catalogo_unificato | `ESE_002` | Precetto in rinnovazione | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 5 | - |
| catalogo_unificato | `ESE_003` | Precetto su sentenza | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 5 | - |
| catalogo_unificato | `ESE_004` | Precetto su decreto ingiuntivo | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `ESE_005` | Precetto su titolo stragiudiziale | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 5 | - |
| catalogo_unificato | `ESE_006` | Pignoramento mobiliare | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 5 | - |
| catalogo_unificato | `ESE_007` | Pignoramento presso terzi | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 5 | - |
| catalogo_unificato | `ESE_008` | Pignoramento presso terzi su conto corrente | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `ESE_009` | Pignoramento presso terzi su stipendio | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 5 | - |
| catalogo_unificato | `ESE_010` | Pignoramento presso terzi su pensione | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 5 | - |
| catalogo_unificato | `ESE_011` | Pignoramento di crediti commerciali | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 5 | - |
| catalogo_unificato | `ESE_012` | Pignoramento immobiliare | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 5 | - |
| catalogo_unificato | `ESE_013` | Istanza di ricerca telematica dei beni | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `ESE_014` | Istanza di assegnazione somme | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 5 | - |
| catalogo_unificato | `ESE_015` | Istanza di vendita | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 5 | - |
| catalogo_unificato | `ESE_016` | Istanza di conversione del pignoramento | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 5 | - |
| catalogo_unificato | `ESE_017` | Istanza di riduzione del pignoramento | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 5 | - |
| catalogo_unificato | `ESE_018` | Atto di intervento del creditore | OK | base_comune, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `ESE_019` | Opposizione all'esecuzione | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `ESE_020` | Opposizione agli atti esecutivi | OK | base_comune, secondaria_collegata, specifica, telematica | 9 / collegate 5 | - |
| catalogo_unificato | `ESE_021` | Opposizione di terzo all'esecuzione | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `ESE_022` | Istanza di sospensione dell'esecuzione | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `ESE_023` | Dichiarazione del terzo | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `ESE_024` | Contestazione della dichiarazione del terzo | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `ESE_025` | Istanza di liberazione dell'immobile | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `ESE_026` | Istanza di estinzione della procedura | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `ESE_027` | Rinuncia agli atti esecutivi | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `ESE_028` | Precisazione del credito | OK | base_comune, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `ESE_029` | Aggiornamento del conteggio del credito | OK | base_comune, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `ESE_030` | Osservazioni al progetto di distribuzione | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `ESE_031` | Reclamo contro provvedimento del GE | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `ESE_032` | Istanza di nomina del custode | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `ESE_033` | Istanza di sostituzione del custode | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `FAM_001` | Ricorso per separazione consensuale | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_002` | Ricorso per separazione giudiziale | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_003` | Ricorso per divorzio congiunto | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_004` | Ricorso per divorzio giudiziale | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_005` | Ricorso per modifica delle condizioni di separazione | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_006` | Ricorso per modifica delle condizioni di divorzio | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_007` | Ricorso per affidamento di figli nati fuori dal matrimonio | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_008` | Ricorso per regolamentazione della frequentazione | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_009` | Ricorso per revisione dell'assegno di mantenimento | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_010` | Ricorso per mantenimento del figlio maggiorenne | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_011` | Ricorso per revoca o riduzione dell'assegno | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_012` | Ricorso per limitazione della responsabilità genitoriale | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_013` | Ricorso per decadenza dalla responsabilità genitoriale | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 24 / collegate 14 | - |
| catalogo_unificato | `FAM_014` | Ricorso per autorizzazione ad atti di straordinaria amministrazione | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_015` | Istanza di provvedimenti urgenti familiari | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_016` | Memoria nel procedimento unitario di famiglia | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 25 / collegate 15 | - |
| catalogo_unificato | `FAM_017` | Istanza di CTU psicologica | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_018` | Istanza di ascolto del minore | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_019` | Istanza di nomina del curatore speciale del minore | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 27 / collegate 15 | - |
| catalogo_unificato | `FAM_020` | Ricorso per ordini di protezione | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_021` | Ricorso per allontanamento familiare | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_022` | Accordo di negoziazione assistita familiare | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_023` | Accordo di modifica consensuale delle condizioni | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_024` | Istanza per rilascio passaporto al minore | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 24 / collegate 14 | - |
| catalogo_unificato | `FAM_025` | Istanza per autorizzazione al trasferimento di residenza del minore | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `GDP_001` | Ricorso davanti al Giudice di Pace | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `GDP_002` | Atto di citazione davanti al Giudice di Pace | OK | base_comune, secondaria_collegata, specifica, telematica | 9 / collegate 5 | - |
| catalogo_unificato | `GDP_003` | Comparsa di costituzione Giudice di Pace | OK | base_comune, secondaria_collegata, specifica, telematica | 9 / collegate 5 | - |
| catalogo_unificato | `GDP_004` | Opposizione a verbale CDS | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `GDP_005` | Opposizione a sanzione amministrativa | OK | base_comune, secondaria_collegata, specifica, telematica | 11 / collegate 8 | - |
| catalogo_unificato | `GDP_006` | Opposizione a ordinanza-ingiunzione | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `GDP_007` | Ricorso danni da circolazione stradale | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `GDP_008` | Ricorso per restituzione somme | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `GDP_009` | Ricorso per beni di modico valore | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `GDP_010` | Istanza di sospensione esecutività | OK | base_comune, secondaria_collegata, specifica, telematica | 9 / collegate 5 | - |
| catalogo_unificato | `GDP_011` | Memoria integrativa Giudice di Pace | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `GDP_012` | Nota conclusiva Giudice di Pace | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `GDP_013` | Istanza di decisione secondo equità | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `GDP_014` | Opposizione a cartella su sanzioni | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `GDP_015` | Opposizione a intimazione di pagamento | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 6 | - |
| catalogo_unificato | `GDP_016` | Istanza di rinvio Giudice di Pace | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `IPD_001` | Diffida per violazione di marchio | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 13 / collegate 6 | - |
| catalogo_unificato | `IPD_002` | Diffida per violazione di copyright | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 13 / collegate 6 | - |
| catalogo_unificato | `IPD_003` | Diffida per uso illecito di immagini | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 13 / collegate 6 | - |
| catalogo_unificato | `IPD_004` | Diffida per plagio di contenuti web | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 13 / collegate 6 | - |
| catalogo_unificato | `IPD_005` | Diffida per contraffazione | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 13 / collegate 6 | - |
| catalogo_unificato | `IPD_006` | Diffida per concorrenza sleale online | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 13 / collegate 6 | - |
| catalogo_unificato | `IPD_007` | Richiesta di rimozione contenuti | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 12 / collegate 6 | - |
| catalogo_unificato | `IPD_008` | Richiesta di deindicizzazione | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 12 / collegate 6 | - |
| catalogo_unificato | `IPD_009` | Diffida in materia di nome a dominio | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 13 / collegate 6 | - |
| catalogo_unificato | `IPD_010` | Contestazione di recensioni diffamatorie | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 12 / collegate 6 | - |
| catalogo_unificato | `IPD_011` | Diffida a hosting o provider | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 13 / collegate 6 | - |
| catalogo_unificato | `IPD_012` | Atto cautelare inibitorio IP | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 12 / collegate 6 | - |
| catalogo_unificato | `IPD_013` | Richiesta danni in materia IP | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 12 / collegate 6 | - |
| catalogo_unificato | `IPD_014` | Diffida in materia di licenze software | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 13 / collegate 6 | - |
| catalogo_unificato | `IPD_015` | Diffida per violazione di NDA | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 13 / collegate 6 | - |
| catalogo_unificato | `LAV_001` | Ricorso rito lavoro | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 22 / collegate 10 | - |
| catalogo_unificato | `LAV_002` | Memoria difensiva nel rito lavoro | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 22 / collegate 10 | - |
| catalogo_unificato | `LAV_003` | Ricorso per impugnazione del licenziamento | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 22 / collegate 10 | - |
| catalogo_unificato | `LAV_004` | Ricorso per reintegra | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_005` | Ricorso per differenze retributive | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 26 / collegate 14 | - |
| catalogo_unificato | `LAV_006` | Ricorso per TFR | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_007` | Ricorso per ferie e permessi | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_008` | Ricorso per qualificazione del rapporto | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_009` | Ricorso per conversione del contratto a termine | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_010` | Ricorso per mobbing | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_011` | Ricorso per demansionamento | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_012` | Ricorso per infortunio sul lavoro | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_013` | Ricorso previdenziale INPS | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_014` | Ricorso per invalidità civile | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_015` | Ricorso per indennità di accompagnamento | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_016` | Appello in materia di lavoro | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_017` | Reclamo in materia di lavoro | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_018` | Verbale di conciliazione | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 27 / collegate 14 | - |
| catalogo_unificato | `LAV_019` | Diffida al datore di lavoro | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_020` | Messa in mora per crediti di lavoro | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LOC_001` | Intimazione di sfratto per morosità | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `LOC_002` | Citazione per convalida di sfratto | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 3 | - |
| catalogo_unificato | `LOC_003` | Intimazione di licenza per finita locazione | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 3 | - |
| catalogo_unificato | `LOC_004` | Opposizione a sfratto | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 3 | - |
| catalogo_unificato | `LOC_005` | Comparsa del conduttore | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 3 | - |
| catalogo_unificato | `LOC_006` | Istanza di ordinanza provvisoria di rilascio | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `LOC_007` | Ricorso monitorio per canoni di locazione | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `LOC_008` | Diffida per pagamento canoni | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 8 / collegate 4 | - |
| catalogo_unificato | `LOC_009` | Diffida per rilascio immobile | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `LOC_010` | Impugnazione di delibera condominiale | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 3 | - |
| catalogo_unificato | `LOC_011` | Ricorso per recupero quote condominiali | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `LOC_012` | Diffida all'amministratore di condominio | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `LOC_013` | Richiesta di accesso alla documentazione condominiale | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `LOC_014` | Citazione per infiltrazioni | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 3 | - |
| catalogo_unificato | `LOC_015` | Citazione per vizi dell'immobile | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 3 | - |
| catalogo_unificato | `LOC_016` | Diffida per vizi costruttivi | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `LOC_017` | Azione ex art. 1669 c.c. | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `LOC_018` | Atto in materia di servitù | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `LOC_019` | Atto in materia di confini | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `LOC_020` | Atto in materia di distanze | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `LOC_021` | Atto in materia di immissioni | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `MON_001` | Ricorso per decreto ingiuntivo | OK | base_comune, secondaria_collegata, specifica, telematica | 5 / collegate 4 | - |
| catalogo_unificato | `MON_002` | Ricorso per decreto ingiuntivo con provvisoria esecutorietà | OK | base_comune, secondaria_collegata, specifica, telematica | 5 / collegate 4 | - |
| catalogo_unificato | `MON_003` | Ricorso monitorio per fatture commerciali | OK | base_comune, secondaria_collegata, specifica, telematica | 5 / collegate 4 | - |
| catalogo_unificato | `MON_004` | Ricorso monitorio per parcella professionale | OK | base_comune, secondaria_collegata, specifica, telematica | 5 / collegate 4 | - |
| catalogo_unificato | `MON_005` | Ricorso monitorio per canoni di locazione | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 5 | - |
| catalogo_unificato | `MON_006` | Ricorso monitorio per oneri condominiali | OK | base_comune, secondaria_collegata, specifica, telematica | 5 / collegate 4 | - |
| catalogo_unificato | `MON_007` | Ricorso monitorio su assegni o cambiali | OK | base_comune, secondaria_collegata, specifica, telematica | 5 / collegate 4 | - |
| catalogo_unificato | `MON_008` | Istanza di concessione formula esecutiva | OK | base_comune, secondaria_collegata, specifica, telematica | 5 / collegate 4 | - |
| catalogo_unificato | `MON_009` | Istanza di correzione decreto ingiuntivo | OK | base_comune, secondaria_collegata, specifica, telematica | 5 / collegate 4 | - |
| catalogo_unificato | `MON_010` | Istanza di rinnovazione notifica decreto ingiuntivo | OK | base_comune, secondaria_collegata, specifica, telematica | 6 / collegate 4 | - |
| catalogo_unificato | `MON_011` | Opposizione a decreto ingiuntivo | OK | base_comune, secondaria_collegata, specifica, telematica | 6 / collegate 4 | - |
| catalogo_unificato | `MON_012` | Citazione in opposizione a decreto ingiuntivo | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 4 | - |
| catalogo_unificato | `MON_013` | Comparsa in opposizione a decreto ingiuntivo | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 4 | - |
| catalogo_unificato | `MON_014` | Istanza di sospensione esecutorietà del decreto ingiuntivo | OK | base_comune, secondaria_collegata, specifica, telematica | 6 / collegate 4 | - |
| catalogo_unificato | `MON_015` | Istanza di concessione o revoca della provvisoria esecuzione | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 4 | - |
| catalogo_unificato | `MON_016` | Memoria istruttoria in opposizione a decreto ingiuntivo | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 4 | - |
| catalogo_unificato | `MON_017` | Nota spese monitoria | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 6 / collegate 5 | - |
| catalogo_unificato | `MON_018` | Precetto su decreto ingiuntivo esecutivo | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 4 | - |
| catalogo_unificato | `PEN_001` | Nomina del difensore | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_002` | Revoca o rinuncia al mandato | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 9 | - |
| catalogo_unificato | `PEN_003` | Memoria difensiva ex art. 121 c.p.p. | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_004` | Istanza di rinvio udienza | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_005` | Istanza di legittimo impedimento | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_006` | Lista testi | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_007` | Opposizione a decreto penale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `PEN_008` | Opposizione alla richiesta di archiviazione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `PEN_009` | Querela | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_010` | Denuncia-querela | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_011` | Remissione di querela | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_012` | Costituzione di parte civile | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `PEN_013` | Istanza di dissequestro | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 8 | - |
| catalogo_unificato | `PEN_014` | Istanza di restituzione di beni sequestrati | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_015` | Istanza di copie atti | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_016` | Istanza di accesso al fascicolo | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_017` | Istanza di incidente probatorio | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_018` | Atto di appello penale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_019` | Ricorso per cassazione penale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_020` | Istanza per misure alternative | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_021` | Istanza di sospensione dell'ordine di esecuzione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 8 | - |
| catalogo_unificato | `PEN_022` | Istanza di revoca di misura cautelare | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `PEN_023` | Istanza di sostituzione di misura cautelare | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `PEN_024` | Memoria per udienza preliminare | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_025` | Eccezioni preliminari | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PRI_001` | Diffida per accesso ai dati personali | OK | autorita, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 11 / collegate 6 | - |
| catalogo_unificato | `PRI_002` | Diffida per rettifica o cancellazione dei dati | OK | autorita, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 11 / collegate 6 | - |
| catalogo_unificato | `PRI_003` | Diffida contro trattamento illecito | OK | autorita, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 11 / collegate 6 | - |
| catalogo_unificato | `PRI_004` | Riscontro a istanza privacy | OK | autorita, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 6 | - |
| catalogo_unificato | `PRI_005` | Messa in mora del titolare del trattamento | OK | autorita, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 11 / collegate 6 | - |
| catalogo_unificato | `PRI_006` | Richiesta danni da illecito trattamento | OK | autorita, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 6 | - |
| catalogo_unificato | `PRI_007` | Diffida per marketing indesiderato | OK | autorita, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 11 / collegate 6 | - |
| catalogo_unificato | `PRI_008` | Diffida per profilazione non autorizzata | OK | autorita, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 11 / collegate 6 | - |
| catalogo_unificato | `PRI_009` | Richiesta di esercizio dei diritti GDPR | OK | autorita, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 6 | - |
| catalogo_unificato | `PRI_010` | Contestazione di data breach | OK | autorita, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 6 | - |
| catalogo_unificato | `PRI_011` | Diffida al datore di lavoro per controllo illecito | OK | autorita, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 12 / collegate 6 | - |
| catalogo_unificato | `RCD_001` | Richiesta stragiudiziale di risarcimento danni | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 14 / collegate 8 | - |
| catalogo_unificato | `RCD_002` | Atto di citazione per risarcimento danni | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 14 / collegate 8 | - |
| catalogo_unificato | `RCD_003` | Atto di citazione per sinistro stradale | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 14 / collegate 8 | - |
| catalogo_unificato | `RCD_004` | Richiesta danni da malpractice medica | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 14 / collegate 8 | - |
| catalogo_unificato | `RCD_005` | Diffida a struttura sanitaria | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 16 / collegate 9 | - |
| catalogo_unificato | `RCD_006` | Richiesta danni da professionista | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 14 / collegate 8 | - |
| catalogo_unificato | `RCD_007` | Richiesta danni da cose in custodia | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 14 / collegate 8 | - |
| catalogo_unificato | `RCD_008` | Richiesta danni da infiltrazioni | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 14 / collegate 8 | - |
| catalogo_unificato | `RCD_009` | Richiesta danni da prodotto difettoso | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 14 / collegate 8 | - |
| catalogo_unificato | `RCD_010` | Richiesta danni da ritardo volo o trasporto | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 17 / collegate 10 | - |
| catalogo_unificato | `RCD_011` | Diffida per diffamazione online | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 14 / collegate 8 | - |
| catalogo_unificato | `RCD_012` | Diffida per lesione dell'immagine o reputazione | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 14 / collegate 8 | - |
| catalogo_unificato | `RCD_013` | ATP per danni | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 14 / collegate 8 | - |
| catalogo_unificato | `RCD_014` | Istanza di CTU preventiva per danni | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 14 / collegate 8 | - |
| catalogo_unificato | `RCD_015` | Messa in mora dell'assicurazione | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 14 / collegate 8 | - |
| catalogo_unificato | `SOC_001` | Diffida al socio | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 15 / collegate 9 | - |
| catalogo_unificato | `SOC_002` | Diffida all'amministratore | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 15 / collegate 9 | - |
| catalogo_unificato | `SOC_003` | Convocazione di assemblea | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 14 / collegate 9 | - |
| catalogo_unificato | `SOC_004` | Verbale di assemblea | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 16 / collegate 10 | - |
| catalogo_unificato | `SOC_005` | Impugnazione di delibera assembleare | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 15 / collegate 9 | - |
| catalogo_unificato | `SOC_006` | Impugnazione di delibera di SRL | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 15 / collegate 9 | - |
| catalogo_unificato | `SOC_007` | Azione di responsabilità contro amministratori | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 14 / collegate 9 | - |
| catalogo_unificato | `SOC_008` | Richiesta di esibizione dei libri sociali | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 14 / collegate 9 | - |
| catalogo_unificato | `SOC_009` | Azione di esclusione del socio | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 14 / collegate 9 | - |
| catalogo_unificato | `SOC_010` | Azione di recesso del socio | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 14 / collegate 9 | - |
| catalogo_unificato | `SOC_011` | Impugnazione del bilancio | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 15 / collegate 9 | - |
| catalogo_unificato | `SOC_012` | Azione di concorrenza sleale | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 14 / collegate 9 | - |
| catalogo_unificato | `SOC_013` | Diffida per violazione del patto di non concorrenza | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 12 | - |
| catalogo_unificato | `SOC_014` | Diffida per uso di marchio o nome commerciale | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 15 / collegate 9 | - |
| catalogo_unificato | `SOC_015` | Ricorso cautelare societario | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 16 / collegate 10 | - |
| catalogo_unificato | `SOC_016` | Inibitoria commerciale urgente | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 14 / collegate 9 | - |
| catalogo_unificato | `STD_001` | Conferimento di incarico | OK | deontologia, ordinamento_professionale, specifica | 12 / collegate 11 | - |
| catalogo_unificato | `STD_002` | Preventivo professionale | OK | deontologia, ordinamento_professionale, specifica | 12 / collegate 11 | - |
| catalogo_unificato | `STD_003` | Accettazione del preventivo | OK | deontologia, ordinamento_professionale, specifica, telematica | 14 / collegate 12 | - |
| catalogo_unificato | `STD_004` | Procura alle liti | OK | deontologia, ordinamento_professionale, specifica | 12 / collegate 11 | - |
| catalogo_unificato | `STD_005` | Scheda raccolta documenti | OK | deontologia, ordinamento_professionale, specifica | 12 / collegate 11 | - |
| catalogo_unificato | `STD_006` | Checklist pre-azione | OK | deontologia, ordinamento_professionale, specifica | 12 / collegate 11 | - |
| catalogo_unificato | `STD_007` | Lettera al cliente sullo stato pratica | OK | deontologia, ordinamento_professionale, specifica | 12 / collegate 11 | - |
| catalogo_unificato | `STD_008` | Sollecito integrazione documenti | OK | deontologia, ordinamento_professionale, specifica | 13 / collegate 11 | - |
| catalogo_unificato | `STD_009` | Lettera di rinuncia all'incarico | OK | deontologia, ordinamento_professionale, specifica | 12 / collegate 11 | - |
| catalogo_unificato | `STD_010` | Lettera di revoca del mandato | OK | deontologia, ordinamento_professionale, specifica | 12 / collegate 11 | - |
| catalogo_unificato | `STD_011` | Informativa privacy cliente | OK | autorita, deontologia, ordinamento_professionale, secondaria_collegata, specifica | 17 / collegate 13 | - |
| catalogo_unificato | `STD_012` | Informativa costi e rischi | OK | autorita, deontologia, ordinamento_professionale, specifica | 14 / collegate 12 | - |
| catalogo_unificato | `STD_013` | Piano attività pratica | OK | deontologia, ordinamento_professionale, specifica | 12 / collegate 11 | - |
| catalogo_unificato | `STD_014` | Verbale riunione cliente | OK | deontologia, ordinamento_professionale, secondaria_collegata, specifica | 14 / collegate 12 | - |
| catalogo_unificato | `STD_015` | Chiusura pratica con esito | OK | deontologia, ordinamento_professionale, specifica | 12 / collegate 11 | - |
| catalogo_unificato | `STD_016` | Sollecito pagamento parcella | OK | deontologia, ordinamento_professionale, specifica | 13 / collegate 11 | - |
| catalogo_unificato | `STD_017` | Messa in mora parcella | OK | deontologia, ordinamento_professionale, specifica | 13 / collegate 11 | - |
| catalogo_unificato | `STD_018` | Accordo saldo parcella | OK | deontologia, ordinamento_professionale, specifica | 12 / collegate 11 | - |
| catalogo_unificato | `STD_019` | Nota proforma | OK | deontologia, ordinamento_professionale, specifica | 12 / collegate 11 | - |
| catalogo_unificato | `STD_020` | Richiesta fondo spese | OK | deontologia, ordinamento_professionale, specifica | 12 / collegate 11 | - |
| catalogo_unificato | `STR_001` | Sollecito bonario | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| catalogo_unificato | `STR_002` | Primo sollecito commerciale | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| catalogo_unificato | `STR_003` | Secondo sollecito | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| catalogo_unificato | `STR_004` | Messa in mora | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| catalogo_unificato | `STR_005` | Diffida ad adempiere | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| catalogo_unificato | `STR_006` | Intimazione finale di pagamento | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 19 / collegate 10 | - |
| catalogo_unificato | `STR_007` | Piano di rientro | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| catalogo_unificato | `STR_008` | Accordo saldo e stralcio | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| catalogo_unificato | `STR_009` | Ricognizione di debito | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| catalogo_unificato | `STR_010` | Transazione semplice | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| catalogo_unificato | `STR_011` | Transazione novativa | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| catalogo_unificato | `STR_012` | Costituzione in mora del debitore | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 19 / collegate 9 | - |
| catalogo_unificato | `STR_013` | Costituzione in mora del fideiussore | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 19 / collegate 9 | - |
| catalogo_unificato | `STR_014` | Diffida per restituzione di beni | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| catalogo_unificato | `STR_015` | Diffida per cessazione di condotta lesiva | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| catalogo_unificato | `STR_016` | Lettera interruttiva della prescrizione | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| catalogo_unificato | `STR_017` | Invito a negoziazione assistita | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `STR_018` | Invito a mediazione | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `STR_019` | Riscontro a diffida | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| catalogo_unificato | `STR_020` | Lettera pre-precetto | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| catalogo_unificato | `TRI_001` | Ricorso tributario | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `TRI_002` | Reclamo-mediazione tributaria | OK | autorita, deontologia, secondaria_collegata, specifica, telematica | 15 / collegate 9 | - |
| catalogo_unificato | `TRI_003` | Appello tributario | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `TRI_004` | Controdeduzioni | OK | deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `TRI_005` | Memoria illustrativa tributaria | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `TRI_006` | Istanza di sospensione dell'esecutività dell'atto | OK | deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `TRI_007` | Istanza di trattazione in pubblica udienza | OK | deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `TRI_008` | Istanza di rinvio | OK | deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `TRI_009` | Nota di deposito documenti | OK | deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 7 | - |
| catalogo_unificato | `TRI_010` | Motivi aggiunti | OK | deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `TRI_011` | Ricorso contro cartella | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `TRI_012` | Ricorso contro intimazione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `TRI_013` | Ricorso contro fermo | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `TRI_014` | Ricorso contro ipoteca | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `TRI_015` | Ricorso IMU | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `TRI_016` | Ricorso TARI | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 7 | - |
| catalogo_unificato | `TRI_017` | Ricorso su tributi locali | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `TRI_018` | Ricorso contro avviso di accertamento | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `TRI_019` | Ricorso contro diniego di rimborso | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 6 | - |
| catalogo_unificato | `TRI_020` | Istanza di conciliazione tributaria | OK | autorita, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 7 | - |
| catalogo_unificato | `VGS_001` | Ricorso per amministrazione di sostegno | OK | base_comune, specifica, telematica | 6 / collegate 2 | - |
| catalogo_unificato | `VGS_002` | Istanza di modifica dell'amministrazione di sostegno | OK | base_comune, specifica, telematica | 6 / collegate 2 | - |
| catalogo_unificato | `VGS_003` | Istanza di rendiconto dell'amministrazione di sostegno | OK | base_comune, specifica, telematica | 6 / collegate 2 | - |
| catalogo_unificato | `VGS_004` | Ricorso per interdizione | OK | base_comune, specifica, telematica | 6 / collegate 2 | - |
| catalogo_unificato | `VGS_005` | Ricorso per inabilitazione | OK | base_comune, specifica, telematica | 6 / collegate 2 | - |
| catalogo_unificato | `VGS_006` | Ricorso per nomina del tutore | OK | base_comune, specifica, telematica | 6 / collegate 2 | - |
| catalogo_unificato | `VGS_007` | Ricorso per nomina del curatore | OK | base_comune, specifica, telematica | 7 / collegate 2 | - |
| catalogo_unificato | `VGS_008` | Ricorso al giudice tutelare per autorizzazione | OK | base_comune, specifica, telematica | 6 / collegate 2 | - |
| catalogo_unificato | `VGS_009` | Istanza di autorizzazione alla riscossione di somme | OK | base_comune, specifica, telematica | 6 / collegate 2 | - |
| catalogo_unificato | `VGS_010` | Istanza di autorizzazione alla vendita di bene del minore o incapace | OK | base_comune, specifica, telematica | 6 / collegate 2 | - |
| catalogo_unificato | `VGS_011` | Istanza di autorizzazione all'accettazione dell'eredità con beneficio | OK | base_comune, specifica, telematica | 8 / collegate 3 | - |
| catalogo_unificato | `VGS_012` | Istanza di autorizzazione alla rinuncia all'eredità | OK | base_comune, deontologia, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `VGS_013` | Ricorso per nomina del curatore dell'eredità giacente | OK | base_comune, specifica, telematica | 7 / collegate 2 | - |
| catalogo_unificato | `VGS_014` | Accettazione dell'eredità con beneficio di inventario | OK | base_comune, specifica, telematica | 10 / collegate 4 | - |
| catalogo_unificato | `VGS_015` | Rinuncia all'eredità | OK | base_comune, deontologia, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `VGS_016` | Istanza per la formazione dell'inventario | OK | base_comune, specifica, telematica | 8 / collegate 3 | - |
| catalogo_unificato | `VGS_017` | Ricorso per rettifica di atti di stato civile | OK | base_comune, specifica, telematica | 6 / collegate 2 | - |
| catalogo_unificato | `VGS_018` | Ricorso per cambio nome o cognome | OK | base_comune, specifica, telematica | 6 / collegate 2 | - |
| catalogo_unificato | `VGS_019` | Ricorso per autorizzazione alla divisione ereditaria con minori | OK | base_comune, specifica, telematica | 8 / collegate 3 | - |
| catalogo_unificato | `AMM_APPCAUT_001` | Appello Cautelare | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 13 / collegate 7 | - |
| catalogo_unificato | `AMM_APPCDS_001` | Appello al Consiglio di Stato | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| catalogo_unificato | `AMM_DEPDOC_001` | Deposito Documenti Amministrativo | OK | autorita, deontologia, secondaria_collegata, specifica, telematica | 13 / collegate 8 | - |
| catalogo_unificato | `AMM_ICAUT_001` | Istanza Cautelare Amministrativa | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 13 / collegate 7 | - |
| catalogo_unificato | `AMM_MEM_001` | Memoria Difensiva Amministrativa | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| catalogo_unificato | `AMM_MOTAGG_001` | Motivi Aggiunti | OK | autorita, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| catalogo_unificato | `AMM_NOTEUD_001` | Note d'Udienza Amministrative | OK | autorita, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| catalogo_unificato | `AMM_RIC_001` | Ricorso al TAR | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| catalogo_unificato | `AMM_SEG_001` | Istanza di Segreteria | OK | autorita, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| catalogo_unificato | `CIV_APP_001` | Appello Civile | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 13 / collegate 6 | - |
| catalogo_unificato | `CIV_CIT_001` | Atto di Citazione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_COM_001` | Comparsa di Costituzione e Risposta | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_CONCL_001` | Comparsa Conclusionale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_CONVSFR_001` | Citazione per Convalida di Sfratto | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 13 / collegate 5 | - |
| catalogo_unificato | `CIV_DEPDOC_001` | Deposito Documenti | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| catalogo_unificato | `CIV_ESE_001` | Pignoramento mobiliare | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 5 | - |
| catalogo_unificato | `CIV_ESE_002` | Pignoramento immobiliare | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 5 | - |
| catalogo_unificato | `CIV_ESE_003` | Istanza di ricerca telematica dei beni | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| catalogo_unificato | `CIV_ESE_004` | Istanza di vendita | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 5 | - |
| catalogo_unificato | `CIV_ESE_005` | Istanza di assegnazione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 5 | - |
| catalogo_unificato | `CIV_ESE_006` | Opposizione di terzo all'esecuzione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 5 | - |
| catalogo_unificato | `CIV_ESE_007` | Istanza di conversione del pignoramento | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 5 | - |
| catalogo_unificato | `CIV_ESE_008` | Istanza di riduzione del pignoramento | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 5 | - |
| catalogo_unificato | `CIV_ESE_009` | Intervento del creditore | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 6 | - |
| catalogo_unificato | `CIV_ESE_010` | Istanza di sospensione della procedura esecutiva | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_ESE_011` | Nota di precisazione del credito | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 6 | - |
| catalogo_unificato | `CIV_ESE_012` | Dichiarazione 553 c.p.c. | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| catalogo_unificato | `CIV_ICAUT_001` | Istanza Cautelare | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| catalogo_unificato | `CIV_IMP_001` | Comparsa di costituzione in appello | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_IMP_002` | Ricorso per cassazione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_IMP_003` | Controricorso | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_IMP_004` | Ricorso per revocazione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_IMP_005` | Opposizione di terzo | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_IMP_006` | Ricorso per regolamento di competenza | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_IMP_007` | Ricorso per regolamento di giurisdizione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_IMP_008` | Istanza di sospensione dell'esecutivita della sentenza | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 13 / collegate 5 | - |
| catalogo_unificato | `CIV_IMP_009` | Istanza di correzione errore materiale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_IMP_010` | Istanza di integrazione del contraddittorio | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_IMP_011` | Reclamo | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_IMP_012` | Ricorso ex legge Pinto | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_INT_001` | Ricorso ex art. 702-bis / rito semplificato | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| catalogo_unificato | `CIV_INT_002` | Riassunzione del giudizio | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| catalogo_unificato | `CIV_INT_003` | Reclamo cautelare | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_INT_004` | Ricorso per sequestro conservativo | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 13 / collegate 5 | - |
| catalogo_unificato | `CIV_INT_005` | Ricorso per sequestro giudiziario | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 13 / collegate 5 | - |
| catalogo_unificato | `CIV_INT_006` | Denuncia di nuova opera | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_INT_007` | Denuncia di danno temuto | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_INT_008` | Azione di manutenzione nel possesso | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| catalogo_unificato | `CIV_INT_009` | Azione di reintegrazione nel possesso | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_INT_010` | Ricorso per accertamento tecnico preventivo | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 13 / collegate 7 | - |
| catalogo_unificato | `CIV_IST_001` | Istanza Generica | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 13 / collegate 6 | - |
| catalogo_unificato | `CIV_LAVMEM_001` | Memoria Difensiva Lavoro | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_LAVRIC_001` | Ricorso in Materia di Lavoro | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_MEM_001` | Memoria Generica | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| catalogo_unificato | `CIV_NOTIFBASE_001` | Notifica / Adempimento Accessorio | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 6 | - |
| catalogo_unificato | `CIV_NOT_001` | Atto UNEP | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 6 | - |
| catalogo_unificato | `CIV_NOT_002` | Atto per notificazione in proprio | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 6 | - |
| catalogo_unificato | `CIV_NOT_003` | Relata di notifica PEC | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 6 | - |
| catalogo_unificato | `CIV_NOT_004` | Deposito telematico documenti | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 15 / collegate 7 | - |
| catalogo_unificato | `CIV_NOT_005` | Visibilita fascicolo telematico | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 6 | - |
| catalogo_unificato | `CIV_NOT_006` | Fascicolo di parte | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 6 | - |
| catalogo_unificato | `CIV_NOT_007` | Attestazione di conformita | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 6 | - |
| catalogo_unificato | `CIV_NOT_008` | Indice allegati | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 6 | - |
| catalogo_unificato | `CIV_NOT_009` | Note iscrizione ruolo | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 6 | - |
| catalogo_unificato | `CIV_OPATTESE_001` | Opposizione agli Atti Esecutivi | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 8 | - |
| catalogo_unificato | `CIV_OPESE_001` | Opposizione all'Esecuzione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 5 | - |
| catalogo_unificato | `CIV_OPPDI_001` | Opposizione a Decreto Ingiuntivo | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| catalogo_unificato | `CIV_PIGBASE_001` | Pignoramento Mobiliare / Immobiliare | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 5 | - |
| catalogo_unificato | `CIV_PPT_001` | Pignoramento Presso Terzi | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 6 | - |
| catalogo_unificato | `CIV_PREC_001` | Atto di Precetto | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 5 | - |
| catalogo_unificato | `CIV_PROCBASE_001` | Procura / Mandato Difensivo | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 17 / collegate 11 | - |
| catalogo_unificato | `CIV_PROC_001` | Procura alle liti | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 15 / collegate 10 | - |
| catalogo_unificato | `CIV_PROC_002` | Procura generale alle liti | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 16 / collegate 10 | - |
| catalogo_unificato | `CIV_PROC_003` | Procura speciale per ricorso monitorio | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 19 / collegate 11 | - |
| catalogo_unificato | `CIV_PROC_004` | Procura speciale per appello | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 19 / collegate 11 | - |
| catalogo_unificato | `CIV_PROC_005` | Procura speciale per ricorso per cassazione | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 19 / collegate 11 | - |
| catalogo_unificato | `CIV_PROC_006` | Procura per fase esecutiva | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 16 / collegate 10 | - |
| catalogo_unificato | `CIV_PROC_007` | Nomina domiciliatario | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 11 | - |
| catalogo_unificato | `CIV_PROC_008` | Revoca del mandato difensivo | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 17 / collegate 11 | - |
| catalogo_unificato | `CIV_PROC_009` | Rinuncia al mandato | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 17 / collegate 11 | - |
| catalogo_unificato | `CIV_PROC_010` | Elezione di domicilio | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 16 / collegate 10 | - |
| catalogo_unificato | `CIV_RCAUT_001` | Ricorso Cautelare | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| catalogo_unificato | `CIV_RDI_001` | Ricorso per Decreto Ingiuntivo | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| catalogo_unificato | `CIV_REPL_001` | Memoria di Replica | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| catalogo_unificato | `CIV_SFRINT_001` | Intimazione di Sfratto | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 6 | - |
| catalogo_unificato | `CIV_SUC_001` | Memoria n. 1 | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_SUC_002` | Memoria n. 2 | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_SUC_003` | Memoria n. 3 | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_SUC_004` | Memoria istruttoria | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_SUC_005` | Istanza di rinvio | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 17 / collegate 9 | - |
| catalogo_unificato | `CIV_SUC_006` | Istanza di trattazione scritta | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_SUC_007` | Note d'udienza | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_SUC_008` | Note conclusive | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_SUC_009` | Istanza di anticipazione udienza | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_SUC_010` | Istanza di riunione procedimenti | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_SUC_011` | Istanza di separazione procedimenti | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| catalogo_unificato | `CIV_SUC_012` | Istanza di provvisoria esecuzione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| catalogo_unificato | `FAM_ADS_001` | Ricorso Nomina Amministratore di Sostegno | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_AFF_001` | Ricorso Affidamento e Responsabilita Genitoriale | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_DIVC_001` | Ricorso Divorzio Congiunto | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_DIVG_001` | Ricorso Divorzio Giudiziale | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_MADS_001` | Ricorso Modifica/Revoca Amministrazione di Sostegno | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_MEMO_001` | Memoria Difensiva Famiglia | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_MOD_001` | Ricorso Modifica Condizioni Separazione/Divorzio | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_REC_001` | Reclamo / Appello in Materia di Famiglia | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_SEPC_001` | Ricorso Separazione Consensuale | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_SEPG_001` | Ricorso Separazione Giudiziale | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_TUT_001` | Ricorso Tutela / Curatela | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_VG_001` | Ricorso per ordine di protezione contro gli abusi familiari | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_VG_002` | Ricorso per autorizzazione ad atto di straordinaria amministrazione del minore | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_VG_003` | Istanze al giudice tutelare | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_VG_004` | Istanza al giudice tutelare | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_VG_005` | Volontaria giurisdizione | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 25 / collegate 15 | - |
| catalogo_unificato | `FAM_VG_006` | Ricorso per decreto tavolare | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `IMM_CITTA_001` | Ricorso per Cittadinanza | OK | autorita, base_comune, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `IMM_EXPUL_001` | Ricorso contro Espulsione / Respingimento | OK | autorita, base_comune, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `IMM_PERMSOG_001` | Ricorso Permesso di Soggiorno | OK | autorita, base_comune, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `IMM_PROT_001` | Ricorso Protezione Internazionale | OK | autorita, base_comune, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `IMM_RIUN_001` | Istanza Ricongiungimento Familiare | OK | autorita, base_comune, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `LAV_APPPREV_001` | Appello Previdenziale | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_APP_001` | Appello in Materia di Lavoro | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_BLT_001` | Ricorso d'urgenza in materia di lavoro | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 22 / collegate 10 | - |
| catalogo_unificato | `LAV_BLT_002` | Ricorso per differenze retributive | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 26 / collegate 14 | - |
| catalogo_unificato | `LAV_BLT_003` | Ricorso monitorio in materia di lavoro | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_BLT_004` | Opposizione a decreto ingiuntivo in materia di lavoro | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 22 / collegate 10 | - |
| catalogo_unificato | `LAV_BLT_005` | Ricorso per condotta antisindacale | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_DISC_001` | Ricorso per Procedura Disciplinare | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_IMPLIC_001` | Impugnazione Licenziamento | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 22 / collegate 10 | - |
| catalogo_unificato | `LAV_ISTAMM_001` | Ricorso Amministrativo Previdenziale | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 24 / collegate 13 | - |
| catalogo_unificato | `LAV_MEM_001` | Memoria Difensiva Lavoro | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_PREV_001` | Ricorso Previdenziale | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_RIC_001` | Ricorso in Materia di Lavoro | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `PEN_BLT_001` | Querela | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_BLT_002` | Denuncia | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_BLT_003` | Opposizione alla richiesta di archiviazione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `PEN_BLT_004` | Istanza di riesame di misura cautelare | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `PEN_BLT_005` | Appello cautelare penale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `PEN_BLT_006` | Ricorso per cassazione penale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_BLT_007` | Atto di costituzione di parte civile | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `PEN_BLT_008` | Lista testi | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_BLT_009` | Istanza di incidente probatorio | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_BLT_010` | Istanza di revoca o sostituzione della misura cautelare | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `PEN_COPIE_001` | Richiesta Copie | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_DEPDOC_001` | Deposito Documenti Penale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 9 | - |
| catalogo_unificato | `PEN_DISSEQ_001` | Istanza di Dissequestro | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 8 | - |
| catalogo_unificato | `PEN_IMP_001` | Atto di Impugnazione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_IST_001` | Istanza Generica Penale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_LISTATESTI_001` | Lista Testi | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_MEM_001` | Memoria Difensiva | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_NOM_001` | Nomina Difensore | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_NOTEUD_001` | Note d'Udienza Penale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_OPPDP_001` | Opposizione a Decreto Penale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `PEN_PARTECIVBASE_001` | Costituzione di Parte Civile | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `PEN_PM_001` | Istanza al Pubblico Ministero | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_RINV_001` | Istanza di Rinvio | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_SEGNBASE_001` | Querela / Denuncia | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `SOC_CONT_001` | Contratto Commerciale | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 16 / collegate 10 | - |
| catalogo_unificato | `SOC_DUEDIL_001` | Report Due Diligence Contrattuale | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 16 / collegate 10 | - |
| catalogo_unificato | `SOC_MEM_001` | Memoria Difensiva Societaria | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 16 / collegate 10 | - |
| catalogo_unificato | `SOC_OPSTR_001` | Parere su Operazione Straordinaria | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 16 / collegate 10 | - |
| catalogo_unificato | `SOC_PAR_001` | Parere Societario | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 16 / collegate 10 | - |
| catalogo_unificato | `SOC_RESP_001` | Atto per Responsabilita Organi Sociali | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 16 / collegate 10 | - |
| catalogo_unificato | `SOC_RIC_001` | Ricorso Contenzioso Societario | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 16 / collegate 10 | - |
| catalogo_unificato | `STR_ATR_001` | Accordo Transattivo | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 19 / collegate 9 | - |
| catalogo_unificato | `STR_BLT_001` | Diffida stragiudiziale collegata al fascicolo | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 19 / collegate 9 | - |
| catalogo_unificato | `STR_BLT_002` | Sollecito di pagamento | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 20 / collegate 10 | - |
| catalogo_unificato | `STR_BLT_003` | Lettera adeguamento canone locazione | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 20 / collegate 9 | - |
| catalogo_unificato | `STR_BLT_004` | Diffida ad adempiere | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| catalogo_unificato | `STR_BLT_005` | Richiesta di documentazione | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 19 / collegate 9 | - |
| catalogo_unificato | `STR_BLT_006` | Comunicazione di riserva diritti | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 19 / collegate 9 | - |
| catalogo_unificato | `STR_BLT_007` | Invito a negoziazione assistita | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `STR_BLT_008` | Atto di messa in mora | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 19 / collegate 9 | - |
| catalogo_unificato | `STR_COM_001` | Comunicazione Professionale | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| catalogo_unificato | `STR_CONTEST_001` | Lettera di Contestazione | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 19 / collegate 9 | - |
| catalogo_unificato | `STR_DIFF_001` | Diffida | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 22 / collegate 11 | - |
| catalogo_unificato | `STR_INC_001` | Incarico Professionale | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 28 / collegate 18 | - |
| catalogo_unificato | `STR_INVAD_001` | Invito ad Adempiere | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 19 / collegate 9 | - |
| catalogo_unificato | `STR_MM_001` | Messa in Mora | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 21 / collegate 11 | - |
| catalogo_unificato | `STR_PAR_001` | Parere Sintetico | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 19 / collegate 9 | - |
| catalogo_unificato | `STR_PREV_001` | Preventivo Professionale | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 24 / collegate 14 | - |
| catalogo_unificato | `STR_PTR_001` | Proposta Transattiva | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 22 / collegate 11 | - |
| catalogo_unificato | `STR_RDP_001` | Richiesta di Pagamento | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 20 / collegate 10 | - |
| catalogo_unificato | `STR_RISDIFF_001` | Riscontro a Diffida | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 19 / collegate 9 | - |
| catalogo_unificato | `STR_SOLL_001` | Sollecito Formale | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 19 / collegate 9 | - |
| catalogo_unificato | `TRIB_APP_001` | Appello Tributario | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 6 | - |
| catalogo_unificato | `TRIB_CONTROAPP_001` | Controdeduzioni in Appello | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 6 | - |
| catalogo_unificato | `TRIB_CONTRO_001` | Controdeduzioni | OK | deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 6 | - |
| catalogo_unificato | `TRIB_DEPDOC_001` | Deposito Documenti Tributario | OK | deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 7 | - |
| catalogo_unificato | `TRIB_IST_001` | Istanza Generica Tributaria | OK | deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 6 | - |
| catalogo_unificato | `TRIB_MEMILL_001` | Memoria Illustrativa | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 6 | - |
| catalogo_unificato | `TRIB_RIC_001` | Ricorso Tributario | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 6 | - |
| catalogo_unificato | `TRIB_SOSP_001` | Istanza di Sospensione | OK | deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 6 | - |
| catalogo_unificato | `ADR_001` | Invito alla mediazione | OK | autorita, deontologia, secondaria_collegata, specifica | 9 / collegate 5 | - |
| catalogo_unificato | `ADR_002` | Istanza di mediazione | OK | autorita, deontologia, secondaria_collegata, specifica | 9 / collegate 5 | - |
| catalogo_unificato | `ADR_003` | Adesione alla mediazione | OK | autorita, deontologia, secondaria_collegata, specifica | 9 / collegate 5 | - |
| catalogo_unificato | `ADR_004` | Verbale di accordo | OK | autorita, deontologia, secondaria_collegata, specifica | 11 / collegate 6 | - |
| catalogo_unificato | `ADR_005` | Verbale di mancato accordo | OK | autorita, deontologia, secondaria_collegata, specifica | 11 / collegate 6 | - |
| catalogo_unificato | `ADR_006` | Invito a negoziazione assistita | OK | autorita, deontologia, secondaria_collegata, specifica | 9 / collegate 5 | - |
| catalogo_unificato | `ADR_007` | Accordo di negoziazione assistita | OK | autorita, deontologia, secondaria_collegata, specifica | 9 / collegate 5 | - |
| catalogo_unificato | `ADR_008` | Diniego a negoziazione | OK | autorita, deontologia, secondaria_collegata, specifica | 9 / collegate 5 | - |
| catalogo_unificato | `ADR_009` | Clausola compromissoria standard | OK | autorita, deontologia, secondaria_collegata, specifica | 9 / collegate 5 | - |
| catalogo_unificato | `ADR_010` | Domanda di arbitrato | OK | autorita, deontologia, secondaria_collegata, specifica | 9 / collegate 5 | - |
| catalogo_unificato | `ADR_011` | Nomina arbitro | OK | autorita, deontologia, secondaria_collegata, specifica | 9 / collegate 5 | - |
| catalogo_unificato | `ADR_012` | Comparsa nel procedimento arbitrale | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica | 10 / collegate 5 | - |
| catalogo_unificato | `ADR_013` | Memoria arbitrale | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica | 9 / collegate 5 | - |
| catalogo_unificato | `ADR_014` | Accordo transattivo finale | OK | autorita, deontologia, secondaria_collegata, specifica | 9 / collegate 5 | - |
| catalogo_unificato | `AMM_001` | Ricorso al TAR | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| catalogo_unificato | `AMM_002` | Motivi aggiunti | OK | autorita, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| catalogo_unificato | `AMM_003` | Ricorso incidentale | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| catalogo_unificato | `AMM_004` | Domanda cautelare | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 13 / collegate 7 | - |
| catalogo_unificato | `AMM_005` | Memoria difensiva amministrativa | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| catalogo_unificato | `AMM_006` | Replica amministrativa | OK | autorita, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| catalogo_unificato | `AMM_007` | Istanza di prelievo | OK | autorita, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| catalogo_unificato | `AMM_008` | Istanza di accesso al fascicolo | OK | autorita, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| catalogo_unificato | `AMM_009` | Ricorso per accesso agli atti | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| catalogo_unificato | `AMM_010` | Ricorso per silenzio-inadempimento | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 13 / collegate 7 | - |
| catalogo_unificato | `AMM_011` | Appello al Consiglio di Stato | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| catalogo_unificato | `AMM_012` | Opposizione a decreto | OK | autorita, deontologia, secondaria_collegata, specifica, telematica | 13 / collegate 7 | - |
| catalogo_unificato | `AMM_013` | Ricorso per ottemperanza | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| catalogo_unificato | `AMM_014` | Ricorso in materia di appalti pubblici | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| catalogo_unificato | `AMM_015` | Ricorso per esclusione da gara | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| catalogo_unificato | `AMM_016` | Ricorso per revoca o annullamento di concessione | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| catalogo_unificato | `AMM_017` | Ricorso per sanzioni amministrative di settore | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| catalogo_unificato | `AMM_018` | Istanza di oscuramento dati | OK | autorita, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| catalogo_unificato | `AMM_APPCAUT_001` | Appello Cautelare | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 13 / collegate 7 | - |
| catalogo_unificato | `AMM_DEPDOC_001` | Deposito Documenti Amministrativo | OK | autorita, deontologia, secondaria_collegata, specifica, telematica | 13 / collegate 8 | - |
| catalogo_unificato | `AMM_ICAUT_001` | Istanza Cautelare Amministrativa | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 13 / collegate 7 | - |
| catalogo_unificato | `AMM_MEM_001` | Memoria Difensiva Amministrativa | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| catalogo_unificato | `AMM_NOTEUD_001` | Note d'Udienza Amministrative | OK | autorita, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| catalogo_unificato | `AMM_SEG_001` | Istanza di Segreteria | OK | autorita, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| catalogo_unificato | `BAN_001` | Diffida per consegna di documentazione bancaria | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 18 / collegate 11 | - |
| catalogo_unificato | `BAN_002` | Richiesta estratti conto ex art. 119 TUB | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 18 / collegate 11 | - |
| catalogo_unificato | `BAN_003` | Atto di citazione per anatocismo | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 18 / collegate 11 | - |
| catalogo_unificato | `BAN_004` | Atto di citazione per usura bancaria | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 18 / collegate 11 | - |
| catalogo_unificato | `BAN_005` | Azione di ripetizione di indebito bancario | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 18 / collegate 11 | - |
| catalogo_unificato | `BAN_006` | Atto in materia di fideiussione omnibus | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 18 / collegate 11 | - |
| catalogo_unificato | `BAN_007` | Opposizione a decreto su saldo di conto | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 19 / collegate 11 | - |
| catalogo_unificato | `BAN_008` | Perizia econometrica introduttiva | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 18 / collegate 11 | - |
| catalogo_unificato | `BAN_009` | Memoria di contestazione interessi e usura | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 18 / collegate 11 | - |
| catalogo_unificato | `BAN_010` | Opposizione a iscrizione in centrale rischi | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 20 / collegate 12 | - |
| catalogo_unificato | `BAN_011` | Diffida a intermediario finanziario | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 18 / collegate 11 | - |
| catalogo_unificato | `BAN_012` | Ricorso ABF preparatorio interno | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 18 / collegate 11 | - |
| catalogo_unificato | `CAU_001` | Ricorso ex art. 700 c.p.c. | OK | base_comune, secondaria_collegata, specifica, telematica | 9 / collegate 4 | - |
| catalogo_unificato | `CAU_002` | Reclamo cautelare | OK | base_comune, secondaria_collegata, specifica, telematica | 9 / collegate 4 | - |
| catalogo_unificato | `CAU_003` | Memoria del resistente in cautelare | OK | base_comune, secondaria_collegata, specifica, telematica | 9 / collegate 4 | - |
| catalogo_unificato | `CAU_004` | Istanza di provvedimento inaudita altera parte | OK | base_comune, secondaria_collegata, specifica, telematica | 9 / collegate 4 | - |
| catalogo_unificato | `CAU_005` | Sequestro conservativo | OK | base_comune, secondaria_collegata, specifica, telematica | 9 / collegate 4 | - |
| catalogo_unificato | `CAU_006` | Sequestro giudiziario | OK | base_comune, secondaria_collegata, specifica, telematica | 9 / collegate 4 | - |
| catalogo_unificato | `CAU_007` | Ricorso per ATP | OK | base_comune, secondaria_collegata, specifica, telematica | 9 / collegate 4 | - |
| catalogo_unificato | `CAU_008` | Ricorso per ATP ex art. 696-bis c.p.c. | OK | base_comune, secondaria_collegata, specifica, telematica | 9 / collegate 4 | - |
| catalogo_unificato | `CAU_009` | Istanza di nomina CTU preventiva | OK | base_comune, secondaria_collegata, specifica, telematica | 9 / collegate 4 | - |
| catalogo_unificato | `CAU_010` | Ricorso di reintegra nel possesso | OK | base_comune, secondaria_collegata, specifica, telematica | 11 / collegate 4 | - |
| catalogo_unificato | `CAU_011` | Ricorso di manutenzione nel possesso | OK | base_comune, secondaria_collegata, specifica, telematica | 10 / collegate 4 | - |
| catalogo_unificato | `CAU_012` | Denuncia di nuova opera | OK | base_comune, secondaria_collegata, specifica, telematica | 9 / collegate 4 | - |
| catalogo_unificato | `CAU_013` | Denuncia di danno temuto | OK | base_comune, secondaria_collegata, specifica, telematica | 9 / collegate 4 | - |
| catalogo_unificato | `CAU_014` | Istanza di sospensione della delibera | OK | base_comune, secondaria_collegata, specifica, telematica | 10 / collegate 4 | - |
| catalogo_unificato | `CAU_015` | Ricorso cautelare societario | OK | base_comune, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| catalogo_unificato | `CAU_016` | Ricorso urgente per consegna o rilascio | OK | base_comune, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CAU_017` | Ricorso inibitorio urgente | OK | base_comune, secondaria_collegata, specifica, telematica | 9 / collegate 4 | - |
| catalogo_unificato | `CIV_CONVSFR_001` | Citazione per Convalida di Sfratto | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 13 / collegate 5 | - |
| catalogo_unificato | `CIV_ESE_001` | Pignoramento mobiliare | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 5 | - |
| catalogo_unificato | `CIV_ESE_002` | Pignoramento immobiliare | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 5 | - |
| catalogo_unificato | `CIV_ESE_003` | Istanza di ricerca telematica dei beni | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| catalogo_unificato | `CIV_ESE_004` | Istanza di vendita | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 5 | - |
| catalogo_unificato | `CIV_ESE_005` | Istanza di assegnazione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 5 | - |
| catalogo_unificato | `CIV_ESE_006` | Opposizione di terzo all'esecuzione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 5 | - |
| catalogo_unificato | `CIV_ESE_007` | Istanza di conversione del pignoramento | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 5 | - |
| catalogo_unificato | `CIV_ESE_008` | Istanza di riduzione del pignoramento | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 5 | - |
| catalogo_unificato | `CIV_ESE_009` | Intervento del creditore | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 6 | - |
| catalogo_unificato | `CIV_ESE_010` | Istanza di sospensione della procedura esecutiva | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_ESE_011` | Nota di precisazione del credito | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 6 | - |
| catalogo_unificato | `CIV_ESE_012` | Dichiarazione 553 c.p.c. | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| catalogo_unificato | `CIV_ICAUT_001` | Istanza Cautelare | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| catalogo_unificato | `CIV_IMP_001` | Comparsa di costituzione in appello | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_IMP_002` | Ricorso per cassazione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_IMP_003` | Controricorso | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_IMP_004` | Ricorso per revocazione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_IMP_005` | Opposizione di terzo | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_IMP_006` | Ricorso per regolamento di competenza | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_IMP_007` | Ricorso per regolamento di giurisdizione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_IMP_008` | Istanza di sospensione dell'esecutivita della sentenza | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 13 / collegate 5 | - |
| catalogo_unificato | `CIV_IMP_009` | Istanza di correzione errore materiale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_IMP_010` | Istanza di integrazione del contraddittorio | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_IMP_011` | Reclamo | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_IMP_012` | Ricorso ex legge Pinto | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_INT_001` | Ricorso ex art. 702-bis / rito semplificato | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| catalogo_unificato | `CIV_INT_002` | Riassunzione del giudizio | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| catalogo_unificato | `CIV_INT_003` | Reclamo cautelare | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_INT_004` | Ricorso per sequestro conservativo | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 13 / collegate 5 | - |
| catalogo_unificato | `CIV_INT_005` | Ricorso per sequestro giudiziario | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 13 / collegate 5 | - |
| catalogo_unificato | `CIV_INT_006` | Denuncia di nuova opera | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_INT_007` | Denuncia di danno temuto | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_INT_008` | Azione di manutenzione nel possesso | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| catalogo_unificato | `CIV_INT_009` | Azione di reintegrazione nel possesso | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_INT_010` | Ricorso per accertamento tecnico preventivo | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 13 / collegate 7 | - |
| catalogo_unificato | `CIV_IST_001` | Istanza Generica | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 13 / collegate 6 | - |
| catalogo_unificato | `CIV_LAVMEM_001` | Memoria Difensiva Lavoro | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_LAVRIC_001` | Ricorso in Materia di Lavoro | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_NOTIFBASE_001` | Notifica / Adempimento Accessorio | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 6 | - |
| catalogo_unificato | `CIV_NOT_001` | Atto UNEP | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 6 | - |
| catalogo_unificato | `CIV_NOT_002` | Atto per notificazione in proprio | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 6 | - |
| catalogo_unificato | `CIV_NOT_003` | Relata di notifica PEC | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 6 | - |
| catalogo_unificato | `CIV_NOT_004` | Deposito telematico documenti | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 15 / collegate 7 | - |
| catalogo_unificato | `CIV_NOT_005` | Visibilita fascicolo telematico | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 6 | - |
| catalogo_unificato | `CIV_NOT_006` | Fascicolo di parte | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 6 | - |
| catalogo_unificato | `CIV_NOT_007` | Attestazione di conformita | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 6 | - |
| catalogo_unificato | `CIV_NOT_008` | Indice allegati | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 6 | - |
| catalogo_unificato | `CIV_NOT_009` | Note iscrizione ruolo | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 6 | - |
| catalogo_unificato | `CIV_ORD_001` | Atto di citazione ordinario | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_002` | Atto di citazione con chiamata del terzo | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_003` | Atto di citazione con domanda riconvenzionale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_004` | Atto di citazione per adempimento contrattuale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_005` | Atto di citazione per risoluzione contrattuale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 15 / collegate 6 | - |
| catalogo_unificato | `CIV_ORD_006` | Atto di citazione per ripetizione di indebito | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_007` | Atto di citazione per arricchimento senza causa | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_008` | Atto di citazione per accertamento negativo del credito | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 15 / collegate 6 | - |
| catalogo_unificato | `CIV_ORD_009` | Comparsa di costituzione e risposta | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_010` | Comparsa con domanda riconvenzionale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_011` | Comparsa con chiamata del terzo | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_012` | Memoria ex art. 171-ter n. 1 c.p.c. | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_013` | Memoria ex art. 171-ter n. 2 c.p.c. | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_014` | Memoria ex art. 171-ter n. 3 c.p.c. | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_015` | Nota di deposito documenti | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_016` | Deduzioni istruttorie | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_017` | Capitoli di prova testimoniale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_018` | Istanza di interpello formale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_019` | Istanza di ordine di esibizione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_020` | Istanza di CTU | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_021` | Osservazioni alla CTU | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_022` | Note critiche alla CTU | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_023` | Istanza di sostituzione CTU | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_024` | Istanza di anticipazione udienza | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_025` | Istanza di rinvio udienza | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_026` | Istanza di trattazione scritta | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_027` | Istanza di discussione orale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_028` | Istanza di passaggio in decisione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_029` | Comparsa conclusionale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_030` | Memoria di replica | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_031` | Nota spese | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 15 / collegate 6 | - |
| catalogo_unificato | `CIV_ORD_032` | Istanza di distrazione spese | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_033` | Rinuncia agli atti | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 15 / collegate 6 | - |
| catalogo_unificato | `CIV_ORD_034` | Accettazione rinuncia | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 17 / collegate 7 | - |
| catalogo_unificato | `CIV_ORD_035` | Riassunzione dopo interruzione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_036` | Riassunzione dopo sospensione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 15 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_037` | Istanza di correzione errore materiale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_ORD_038` | Istanza di estinzione del giudizio | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 5 | - |
| catalogo_unificato | `CIV_PIGBASE_001` | Pignoramento Mobiliare / Immobiliare | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 5 | - |
| catalogo_unificato | `CIV_PROCBASE_001` | Procura / Mandato Difensivo | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 17 / collegate 11 | - |
| catalogo_unificato | `CIV_PROC_001` | Procura alle liti | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 15 / collegate 10 | - |
| catalogo_unificato | `CIV_PROC_002` | Procura generale alle liti | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 16 / collegate 10 | - |
| catalogo_unificato | `CIV_PROC_003` | Procura speciale per ricorso monitorio | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 19 / collegate 11 | - |
| catalogo_unificato | `CIV_PROC_004` | Procura speciale per appello | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 19 / collegate 11 | - |
| catalogo_unificato | `CIV_PROC_005` | Procura speciale per ricorso per cassazione | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 19 / collegate 11 | - |
| catalogo_unificato | `CIV_PROC_006` | Procura per fase esecutiva | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 16 / collegate 10 | - |
| catalogo_unificato | `CIV_PROC_007` | Nomina domiciliatario | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 11 | - |
| catalogo_unificato | `CIV_PROC_008` | Revoca del mandato difensivo | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 17 / collegate 11 | - |
| catalogo_unificato | `CIV_PROC_009` | Rinuncia al mandato | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 17 / collegate 11 | - |
| catalogo_unificato | `CIV_PROC_010` | Elezione di domicilio | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 16 / collegate 10 | - |
| catalogo_unificato | `CIV_SFRINT_001` | Intimazione di Sfratto | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 6 | - |
| catalogo_unificato | `CIV_SUC_001` | Memoria n. 1 | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_SUC_002` | Memoria n. 2 | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_SUC_003` | Memoria n. 3 | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_SUC_004` | Memoria istruttoria | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_SUC_005` | Istanza di rinvio | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 17 / collegate 9 | - |
| catalogo_unificato | `CIV_SUC_006` | Istanza di trattazione scritta | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_SUC_007` | Note d'udienza | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_SUC_008` | Note conclusive | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_SUC_009` | Istanza di anticipazione udienza | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_SUC_010` | Istanza di riunione procedimenti | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| catalogo_unificato | `CIV_SUC_011` | Istanza di separazione procedimenti | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| catalogo_unificato | `CIV_SUC_012` | Istanza di provvisoria esecuzione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| catalogo_unificato | `CONC_001` | Domanda di insinuazione al passivo | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 22 / collegate 13 | - |
| catalogo_unificato | `CONC_002` | Domanda tardiva di insinuazione | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 24 / collegate 14 | - |
| catalogo_unificato | `CONC_003` | Opposizione allo stato passivo | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 23 / collegate 13 | - |
| catalogo_unificato | `CONC_004` | Istanza di rivendica | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 22 / collegate 13 | - |
| catalogo_unificato | `CONC_005` | Istanza di restituzione | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 22 / collegate 13 | - |
| catalogo_unificato | `CONC_006` | Domanda di ammissione di credito privilegiato | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `CONC_007` | Ricorso per liquidazione controllata | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 22 / collegate 13 | - |
| catalogo_unificato | `CONC_008` | Istanza al curatore | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 22 / collegate 13 | - |
| catalogo_unificato | `CONC_009` | Reclamo contro provvedimento del giudice delegato | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 22 / collegate 13 | - |
| catalogo_unificato | `CONC_010` | Domanda di esdebitazione | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 22 / collegate 13 | - |
| catalogo_unificato | `CONC_011` | Domanda di concordato minore | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 22 / collegate 13 | - |
| catalogo_unificato | `CONC_012` | Domanda del consumatore | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 22 / collegate 13 | - |
| catalogo_unificato | `CONC_013` | Osservazioni al piano | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 22 / collegate 13 | - |
| catalogo_unificato | `CONC_014` | Memoria dei creditori | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `CONC_015` | Istanza di autorizzazione ad atti del liquidatore | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 23 / collegate 13 | - |
| catalogo_unificato | `CON_001` | Diffida a operatore telefonico | OK | autorita, secondaria_collegata, specifica, telematica | 11 / collegate 7 | - |
| catalogo_unificato | `CON_002` | Diffida a fornitore di energia | OK | autorita, secondaria_collegata, specifica, telematica | 11 / collegate 7 | - |
| catalogo_unificato | `CON_003` | Diffida a fornitore di acqua | OK | autorita, secondaria_collegata, specifica, telematica | 11 / collegate 7 | - |
| catalogo_unificato | `CON_004` | Reclamo per trasporto aereo | OK | autorita, secondaria_collegata, specifica, telematica | 11 / collegate 7 | - |
| catalogo_unificato | `CON_005` | Reclamo per trasporto ferroviario | OK | autorita, secondaria_collegata, specifica, telematica | 11 / collegate 7 | - |
| catalogo_unificato | `CON_006` | Richiesta rimborso pacchetto turistico | OK | autorita, secondaria_collegata, specifica, telematica | 11 / collegate 7 | - |
| catalogo_unificato | `CON_007` | Diffida a e-commerce per mancata consegna | OK | autorita, secondaria_collegata, specifica, telematica | 11 / collegate 7 | - |
| catalogo_unificato | `CON_008` | Richiesta rimborso per acquisto difettoso | OK | autorita, secondaria_collegata, specifica, telematica | 11 / collegate 7 | - |
| catalogo_unificato | `CON_009` | Diffida per garanzia legale di conformità | OK | autorita, secondaria_collegata, specifica, telematica | 13 / collegate 8 | - |
| catalogo_unificato | `CON_010` | Invito a conciliazione paritetica | OK | autorita, secondaria_collegata, specifica, telematica | 12 / collegate 8 | - |
| catalogo_unificato | `CON_011` | Ricorso GDP del consumatore | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 11 / collegate 7 | - |
| catalogo_unificato | `CON_012` | Atto su clausole vessatorie | OK | autorita, secondaria_collegata, specifica, telematica | 11 / collegate 7 | - |
| catalogo_unificato | `ESE_001` | Atto di precetto | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 5 | - |
| catalogo_unificato | `ESE_002` | Precetto in rinnovazione | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 5 | - |
| catalogo_unificato | `ESE_003` | Precetto su sentenza | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 5 | - |
| catalogo_unificato | `ESE_004` | Precetto su decreto ingiuntivo | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `ESE_005` | Precetto su titolo stragiudiziale | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 5 | - |
| catalogo_unificato | `ESE_006` | Pignoramento mobiliare | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 5 | - |
| catalogo_unificato | `ESE_007` | Pignoramento presso terzi | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 5 | - |
| catalogo_unificato | `ESE_008` | Pignoramento presso terzi su conto corrente | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `ESE_009` | Pignoramento presso terzi su stipendio | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 5 | - |
| catalogo_unificato | `ESE_010` | Pignoramento presso terzi su pensione | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 5 | - |
| catalogo_unificato | `ESE_011` | Pignoramento di crediti commerciali | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 5 | - |
| catalogo_unificato | `ESE_012` | Pignoramento immobiliare | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 5 | - |
| catalogo_unificato | `ESE_013` | Istanza di ricerca telematica dei beni | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `ESE_014` | Istanza di assegnazione somme | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 5 | - |
| catalogo_unificato | `ESE_015` | Istanza di vendita | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 5 | - |
| catalogo_unificato | `ESE_016` | Istanza di conversione del pignoramento | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 5 | - |
| catalogo_unificato | `ESE_017` | Istanza di riduzione del pignoramento | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 5 | - |
| catalogo_unificato | `ESE_018` | Atto di intervento del creditore | OK | base_comune, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `ESE_019` | Opposizione all'esecuzione | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `ESE_020` | Opposizione agli atti esecutivi | OK | base_comune, secondaria_collegata, specifica, telematica | 9 / collegate 5 | - |
| catalogo_unificato | `ESE_021` | Opposizione di terzo all'esecuzione | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `ESE_022` | Istanza di sospensione dell'esecuzione | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `ESE_023` | Dichiarazione del terzo | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `ESE_024` | Contestazione della dichiarazione del terzo | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `ESE_025` | Istanza di liberazione dell'immobile | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `ESE_026` | Istanza di estinzione della procedura | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `ESE_027` | Rinuncia agli atti esecutivi | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `ESE_028` | Precisazione del credito | OK | base_comune, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `ESE_029` | Aggiornamento del conteggio del credito | OK | base_comune, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `ESE_030` | Osservazioni al progetto di distribuzione | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `ESE_031` | Reclamo contro provvedimento del GE | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `ESE_032` | Istanza di nomina del custode | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `ESE_033` | Istanza di sostituzione del custode | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `FAM_001` | Ricorso per separazione consensuale | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_002` | Ricorso per separazione giudiziale | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_003` | Ricorso per divorzio congiunto | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_004` | Ricorso per divorzio giudiziale | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_005` | Ricorso per modifica delle condizioni di separazione | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_006` | Ricorso per modifica delle condizioni di divorzio | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_007` | Ricorso per affidamento di figli nati fuori dal matrimonio | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_008` | Ricorso per regolamentazione della frequentazione | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_009` | Ricorso per revisione dell'assegno di mantenimento | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_010` | Ricorso per mantenimento del figlio maggiorenne | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_011` | Ricorso per revoca o riduzione dell'assegno | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_012` | Ricorso per limitazione della responsabilità genitoriale | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_013` | Ricorso per decadenza dalla responsabilità genitoriale | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 24 / collegate 14 | - |
| catalogo_unificato | `FAM_014` | Ricorso per autorizzazione ad atti di straordinaria amministrazione | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_015` | Istanza di provvedimenti urgenti familiari | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_016` | Memoria nel procedimento unitario di famiglia | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 25 / collegate 15 | - |
| catalogo_unificato | `FAM_017` | Istanza di CTU psicologica | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_018` | Istanza di ascolto del minore | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_019` | Istanza di nomina del curatore speciale del minore | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 27 / collegate 15 | - |
| catalogo_unificato | `FAM_020` | Ricorso per ordini di protezione | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_021` | Ricorso per allontanamento familiare | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_022` | Accordo di negoziazione assistita familiare | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_023` | Accordo di modifica consensuale delle condizioni | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_024` | Istanza per rilascio passaporto al minore | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 24 / collegate 14 | - |
| catalogo_unificato | `FAM_025` | Istanza per autorizzazione al trasferimento di residenza del minore | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_MADS_001` | Ricorso Modifica/Revoca Amministrazione di Sostegno | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_MEMO_001` | Memoria Difensiva Famiglia | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_REC_001` | Reclamo / Appello in Materia di Famiglia | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_TUT_001` | Ricorso Tutela / Curatela | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_VG_001` | Ricorso per ordine di protezione contro gli abusi familiari | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_VG_002` | Ricorso per autorizzazione ad atto di straordinaria amministrazione del minore | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_VG_003` | Istanze al giudice tutelare | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_VG_004` | Istanza al giudice tutelare | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `FAM_VG_005` | Volontaria giurisdizione | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 25 / collegate 15 | - |
| catalogo_unificato | `FAM_VG_006` | Ricorso per decreto tavolare | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| catalogo_unificato | `GDP_001` | Ricorso davanti al Giudice di Pace | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `GDP_002` | Atto di citazione davanti al Giudice di Pace | OK | base_comune, secondaria_collegata, specifica, telematica | 9 / collegate 5 | - |
| catalogo_unificato | `GDP_003` | Comparsa di costituzione Giudice di Pace | OK | base_comune, secondaria_collegata, specifica, telematica | 9 / collegate 5 | - |
| catalogo_unificato | `GDP_004` | Opposizione a verbale CDS | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `GDP_005` | Opposizione a sanzione amministrativa | OK | base_comune, secondaria_collegata, specifica, telematica | 11 / collegate 8 | - |
| catalogo_unificato | `GDP_006` | Opposizione a ordinanza-ingiunzione | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `GDP_007` | Ricorso danni da circolazione stradale | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `GDP_008` | Ricorso per restituzione somme | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `GDP_009` | Ricorso per beni di modico valore | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `GDP_010` | Istanza di sospensione esecutività | OK | base_comune, secondaria_collegata, specifica, telematica | 9 / collegate 5 | - |
| catalogo_unificato | `GDP_011` | Memoria integrativa Giudice di Pace | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `GDP_012` | Nota conclusiva Giudice di Pace | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `GDP_013` | Istanza di decisione secondo equità | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `GDP_014` | Opposizione a cartella su sanzioni | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `GDP_015` | Opposizione a intimazione di pagamento | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 6 | - |
| catalogo_unificato | `GDP_016` | Istanza di rinvio Giudice di Pace | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 5 | - |
| catalogo_unificato | `IMM_CITTA_001` | Ricorso per Cittadinanza | OK | autorita, base_comune, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `IMM_EXPUL_001` | Ricorso contro Espulsione / Respingimento | OK | autorita, base_comune, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `IMM_PERMSOG_001` | Ricorso Permesso di Soggiorno | OK | autorita, base_comune, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `IMM_PROT_001` | Ricorso Protezione Internazionale | OK | autorita, base_comune, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `IMM_RIUN_001` | Istanza Ricongiungimento Familiare | OK | autorita, base_comune, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `IPD_001` | Diffida per violazione di marchio | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 13 / collegate 6 | - |
| catalogo_unificato | `IPD_002` | Diffida per violazione di copyright | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 13 / collegate 6 | - |
| catalogo_unificato | `IPD_003` | Diffida per uso illecito di immagini | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 13 / collegate 6 | - |
| catalogo_unificato | `IPD_004` | Diffida per plagio di contenuti web | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 13 / collegate 6 | - |
| catalogo_unificato | `IPD_005` | Diffida per contraffazione | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 13 / collegate 6 | - |
| catalogo_unificato | `IPD_006` | Diffida per concorrenza sleale online | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 13 / collegate 6 | - |
| catalogo_unificato | `IPD_007` | Richiesta di rimozione contenuti | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 12 / collegate 6 | - |
| catalogo_unificato | `IPD_008` | Richiesta di deindicizzazione | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 12 / collegate 6 | - |
| catalogo_unificato | `IPD_009` | Diffida in materia di nome a dominio | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 13 / collegate 6 | - |
| catalogo_unificato | `IPD_010` | Contestazione di recensioni diffamatorie | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 12 / collegate 6 | - |
| catalogo_unificato | `IPD_011` | Diffida a hosting o provider | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 13 / collegate 6 | - |
| catalogo_unificato | `IPD_012` | Atto cautelare inibitorio IP | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 12 / collegate 6 | - |
| catalogo_unificato | `IPD_013` | Richiesta danni in materia IP | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 12 / collegate 6 | - |
| catalogo_unificato | `IPD_014` | Diffida in materia di licenze software | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 13 / collegate 6 | - |
| catalogo_unificato | `IPD_015` | Diffida per violazione di NDA | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 13 / collegate 6 | - |
| catalogo_unificato | `LAV_001` | Ricorso rito lavoro | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 22 / collegate 10 | - |
| catalogo_unificato | `LAV_002` | Memoria difensiva nel rito lavoro | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 22 / collegate 10 | - |
| catalogo_unificato | `LAV_003` | Ricorso per impugnazione del licenziamento | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 22 / collegate 10 | - |
| catalogo_unificato | `LAV_004` | Ricorso per reintegra | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_005` | Ricorso per differenze retributive | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 26 / collegate 14 | - |
| catalogo_unificato | `LAV_006` | Ricorso per TFR | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_007` | Ricorso per ferie e permessi | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_008` | Ricorso per qualificazione del rapporto | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_009` | Ricorso per conversione del contratto a termine | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_010` | Ricorso per mobbing | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_011` | Ricorso per demansionamento | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_012` | Ricorso per infortunio sul lavoro | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_013` | Ricorso previdenziale INPS | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_014` | Ricorso per invalidità civile | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_015` | Ricorso per indennità di accompagnamento | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_016` | Appello in materia di lavoro | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_017` | Reclamo in materia di lavoro | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_018` | Verbale di conciliazione | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 27 / collegate 14 | - |
| catalogo_unificato | `LAV_019` | Diffida al datore di lavoro | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_020` | Messa in mora per crediti di lavoro | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_APPPREV_001` | Appello Previdenziale | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_BLT_001` | Ricorso d'urgenza in materia di lavoro | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 22 / collegate 10 | - |
| catalogo_unificato | `LAV_BLT_002` | Ricorso per differenze retributive | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 26 / collegate 14 | - |
| catalogo_unificato | `LAV_BLT_003` | Ricorso monitorio in materia di lavoro | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_BLT_004` | Opposizione a decreto ingiuntivo in materia di lavoro | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 22 / collegate 10 | - |
| catalogo_unificato | `LAV_BLT_005` | Ricorso per condotta antisindacale | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_DISC_001` | Ricorso per Procedura Disciplinare | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `LAV_ISTAMM_001` | Ricorso Amministrativo Previdenziale | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 24 / collegate 13 | - |
| catalogo_unificato | `LOC_001` | Intimazione di sfratto per morosità | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `LOC_002` | Citazione per convalida di sfratto | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 3 | - |
| catalogo_unificato | `LOC_003` | Intimazione di licenza per finita locazione | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 3 | - |
| catalogo_unificato | `LOC_004` | Opposizione a sfratto | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 3 | - |
| catalogo_unificato | `LOC_005` | Comparsa del conduttore | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 3 | - |
| catalogo_unificato | `LOC_006` | Istanza di ordinanza provvisoria di rilascio | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `LOC_007` | Ricorso monitorio per canoni di locazione | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `LOC_008` | Diffida per pagamento canoni | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 8 / collegate 4 | - |
| catalogo_unificato | `LOC_009` | Diffida per rilascio immobile | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `LOC_010` | Impugnazione di delibera condominiale | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 3 | - |
| catalogo_unificato | `LOC_011` | Ricorso per recupero quote condominiali | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `LOC_012` | Diffida all'amministratore di condominio | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `LOC_013` | Richiesta di accesso alla documentazione condominiale | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `LOC_014` | Citazione per infiltrazioni | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 3 | - |
| catalogo_unificato | `LOC_015` | Citazione per vizi dell'immobile | OK | base_comune, secondaria_collegata, specifica, telematica | 8 / collegate 3 | - |
| catalogo_unificato | `LOC_016` | Diffida per vizi costruttivi | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `LOC_017` | Azione ex art. 1669 c.c. | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `LOC_018` | Atto in materia di servitù | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `LOC_019` | Atto in materia di confini | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `LOC_020` | Atto in materia di distanze | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `LOC_021` | Atto in materia di immissioni | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `MON_001` | Ricorso per decreto ingiuntivo | OK | base_comune, secondaria_collegata, specifica, telematica | 5 / collegate 4 | - |
| catalogo_unificato | `MON_002` | Ricorso per decreto ingiuntivo con provvisoria esecutorietà | OK | base_comune, secondaria_collegata, specifica, telematica | 5 / collegate 4 | - |
| catalogo_unificato | `MON_003` | Ricorso monitorio per fatture commerciali | OK | base_comune, secondaria_collegata, specifica, telematica | 5 / collegate 4 | - |
| catalogo_unificato | `MON_004` | Ricorso monitorio per parcella professionale | OK | base_comune, secondaria_collegata, specifica, telematica | 5 / collegate 4 | - |
| catalogo_unificato | `MON_005` | Ricorso monitorio per canoni di locazione | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 5 | - |
| catalogo_unificato | `MON_006` | Ricorso monitorio per oneri condominiali | OK | base_comune, secondaria_collegata, specifica, telematica | 5 / collegate 4 | - |
| catalogo_unificato | `MON_007` | Ricorso monitorio su assegni o cambiali | OK | base_comune, secondaria_collegata, specifica, telematica | 5 / collegate 4 | - |
| catalogo_unificato | `MON_008` | Istanza di concessione formula esecutiva | OK | base_comune, secondaria_collegata, specifica, telematica | 5 / collegate 4 | - |
| catalogo_unificato | `MON_009` | Istanza di correzione decreto ingiuntivo | OK | base_comune, secondaria_collegata, specifica, telematica | 5 / collegate 4 | - |
| catalogo_unificato | `MON_010` | Istanza di rinnovazione notifica decreto ingiuntivo | OK | base_comune, secondaria_collegata, specifica, telematica | 6 / collegate 4 | - |
| catalogo_unificato | `MON_011` | Opposizione a decreto ingiuntivo | OK | base_comune, secondaria_collegata, specifica, telematica | 6 / collegate 4 | - |
| catalogo_unificato | `MON_012` | Citazione in opposizione a decreto ingiuntivo | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 4 | - |
| catalogo_unificato | `MON_013` | Comparsa in opposizione a decreto ingiuntivo | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 4 | - |
| catalogo_unificato | `MON_014` | Istanza di sospensione esecutorietà del decreto ingiuntivo | OK | base_comune, secondaria_collegata, specifica, telematica | 6 / collegate 4 | - |
| catalogo_unificato | `MON_015` | Istanza di concessione o revoca della provvisoria esecuzione | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 4 | - |
| catalogo_unificato | `MON_016` | Memoria istruttoria in opposizione a decreto ingiuntivo | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 4 | - |
| catalogo_unificato | `MON_017` | Nota spese monitoria | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 6 / collegate 5 | - |
| catalogo_unificato | `MON_018` | Precetto su decreto ingiuntivo esecutivo | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 4 | - |
| catalogo_unificato | `PEN_001` | Nomina del difensore | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_002` | Revoca o rinuncia al mandato | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 9 | - |
| catalogo_unificato | `PEN_003` | Memoria difensiva ex art. 121 c.p.p. | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_004` | Istanza di rinvio udienza | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_005` | Istanza di legittimo impedimento | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_006` | Lista testi | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_007` | Opposizione a decreto penale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `PEN_008` | Opposizione alla richiesta di archiviazione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `PEN_009` | Querela | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_010` | Denuncia-querela | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_011` | Remissione di querela | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_012` | Costituzione di parte civile | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `PEN_013` | Istanza di dissequestro | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 8 | - |
| catalogo_unificato | `PEN_014` | Istanza di restituzione di beni sequestrati | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_015` | Istanza di copie atti | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_016` | Istanza di accesso al fascicolo | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_017` | Istanza di incidente probatorio | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_018` | Atto di appello penale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_019` | Ricorso per cassazione penale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_020` | Istanza per misure alternative | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_021` | Istanza di sospensione dell'ordine di esecuzione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 8 | - |
| catalogo_unificato | `PEN_022` | Istanza di revoca di misura cautelare | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `PEN_023` | Istanza di sostituzione di misura cautelare | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `PEN_024` | Memoria per udienza preliminare | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_025` | Eccezioni preliminari | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_BLT_001` | Querela | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_BLT_002` | Denuncia | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_BLT_003` | Opposizione alla richiesta di archiviazione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `PEN_BLT_004` | Istanza di riesame di misura cautelare | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `PEN_BLT_005` | Appello cautelare penale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `PEN_BLT_006` | Ricorso per cassazione penale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_BLT_007` | Atto di costituzione di parte civile | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `PEN_BLT_008` | Lista testi | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_BLT_009` | Istanza di incidente probatorio | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_BLT_010` | Istanza di revoca o sostituzione della misura cautelare | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `PEN_COPIE_001` | Richiesta Copie | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_DEPDOC_001` | Deposito Documenti Penale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 9 | - |
| catalogo_unificato | `PEN_DISSEQ_001` | Istanza di Dissequestro | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 8 | - |
| catalogo_unificato | `PEN_IMP_001` | Atto di Impugnazione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_IST_001` | Istanza Generica Penale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_LISTATESTI_001` | Lista Testi | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_NOTEUD_001` | Note d'Udienza Penale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_OPPDP_001` | Opposizione a Decreto Penale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `PEN_PARTECIVBASE_001` | Costituzione di Parte Civile | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `PEN_PM_001` | Istanza al Pubblico Ministero | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_RINV_001` | Istanza di Rinvio | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PEN_SEGNBASE_001` | Querela / Denuncia | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `PRI_001` | Diffida per accesso ai dati personali | OK | autorita, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 11 / collegate 6 | - |
| catalogo_unificato | `PRI_002` | Diffida per rettifica o cancellazione dei dati | OK | autorita, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 11 / collegate 6 | - |
| catalogo_unificato | `PRI_003` | Diffida contro trattamento illecito | OK | autorita, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 11 / collegate 6 | - |
| catalogo_unificato | `PRI_004` | Riscontro a istanza privacy | OK | autorita, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 6 | - |
| catalogo_unificato | `PRI_005` | Messa in mora del titolare del trattamento | OK | autorita, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 11 / collegate 6 | - |
| catalogo_unificato | `PRI_006` | Richiesta danni da illecito trattamento | OK | autorita, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 6 | - |
| catalogo_unificato | `PRI_007` | Diffida per marketing indesiderato | OK | autorita, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 11 / collegate 6 | - |
| catalogo_unificato | `PRI_008` | Diffida per profilazione non autorizzata | OK | autorita, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 11 / collegate 6 | - |
| catalogo_unificato | `PRI_009` | Richiesta di esercizio dei diritti GDPR | OK | autorita, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 6 | - |
| catalogo_unificato | `PRI_010` | Contestazione di data breach | OK | autorita, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 6 | - |
| catalogo_unificato | `PRI_011` | Diffida al datore di lavoro per controllo illecito | OK | autorita, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 12 / collegate 6 | - |
| catalogo_unificato | `RCD_001` | Richiesta stragiudiziale di risarcimento danni | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 14 / collegate 8 | - |
| catalogo_unificato | `RCD_002` | Atto di citazione per risarcimento danni | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 14 / collegate 8 | - |
| catalogo_unificato | `RCD_003` | Atto di citazione per sinistro stradale | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 14 / collegate 8 | - |
| catalogo_unificato | `RCD_004` | Richiesta danni da malpractice medica | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 14 / collegate 8 | - |
| catalogo_unificato | `RCD_005` | Diffida a struttura sanitaria | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 16 / collegate 9 | - |
| catalogo_unificato | `RCD_006` | Richiesta danni da professionista | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 14 / collegate 8 | - |
| catalogo_unificato | `RCD_007` | Richiesta danni da cose in custodia | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 14 / collegate 8 | - |
| catalogo_unificato | `RCD_008` | Richiesta danni da infiltrazioni | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 14 / collegate 8 | - |
| catalogo_unificato | `RCD_009` | Richiesta danni da prodotto difettoso | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 14 / collegate 8 | - |
| catalogo_unificato | `RCD_010` | Richiesta danni da ritardo volo o trasporto | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 17 / collegate 10 | - |
| catalogo_unificato | `RCD_011` | Diffida per diffamazione online | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 14 / collegate 8 | - |
| catalogo_unificato | `RCD_012` | Diffida per lesione dell'immagine o reputazione | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 14 / collegate 8 | - |
| catalogo_unificato | `RCD_013` | ATP per danni | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 14 / collegate 8 | - |
| catalogo_unificato | `RCD_014` | Istanza di CTU preventiva per danni | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 14 / collegate 8 | - |
| catalogo_unificato | `RCD_015` | Messa in mora dell'assicurazione | OK | autorita, base_comune, secondaria_collegata, specifica, telematica | 14 / collegate 8 | - |
| catalogo_unificato | `SOC_001` | Diffida al socio | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 15 / collegate 9 | - |
| catalogo_unificato | `SOC_002` | Diffida all'amministratore | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 15 / collegate 9 | - |
| catalogo_unificato | `SOC_003` | Convocazione di assemblea | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 14 / collegate 9 | - |
| catalogo_unificato | `SOC_004` | Verbale di assemblea | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 16 / collegate 10 | - |
| catalogo_unificato | `SOC_005` | Impugnazione di delibera assembleare | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 15 / collegate 9 | - |
| catalogo_unificato | `SOC_006` | Impugnazione di delibera di SRL | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 15 / collegate 9 | - |
| catalogo_unificato | `SOC_007` | Azione di responsabilità contro amministratori | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 14 / collegate 9 | - |
| catalogo_unificato | `SOC_008` | Richiesta di esibizione dei libri sociali | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 14 / collegate 9 | - |
| catalogo_unificato | `SOC_009` | Azione di esclusione del socio | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 14 / collegate 9 | - |
| catalogo_unificato | `SOC_010` | Azione di recesso del socio | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 14 / collegate 9 | - |
| catalogo_unificato | `SOC_011` | Impugnazione del bilancio | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 15 / collegate 9 | - |
| catalogo_unificato | `SOC_012` | Azione di concorrenza sleale | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 14 / collegate 9 | - |
| catalogo_unificato | `SOC_013` | Diffida per violazione del patto di non concorrenza | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 12 | - |
| catalogo_unificato | `SOC_014` | Diffida per uso di marchio o nome commerciale | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 15 / collegate 9 | - |
| catalogo_unificato | `SOC_015` | Ricorso cautelare societario | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 16 / collegate 10 | - |
| catalogo_unificato | `SOC_016` | Inibitoria commerciale urgente | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 14 / collegate 9 | - |
| catalogo_unificato | `SOC_CONT_001` | Contratto Commerciale | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 16 / collegate 10 | - |
| catalogo_unificato | `SOC_DUEDIL_001` | Report Due Diligence Contrattuale | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 16 / collegate 10 | - |
| catalogo_unificato | `SOC_MEM_001` | Memoria Difensiva Societaria | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 16 / collegate 10 | - |
| catalogo_unificato | `SOC_OPSTR_001` | Parere su Operazione Straordinaria | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 16 / collegate 10 | - |
| catalogo_unificato | `SOC_PAR_001` | Parere Societario | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 16 / collegate 10 | - |
| catalogo_unificato | `SOC_RESP_001` | Atto per Responsabilita Organi Sociali | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 16 / collegate 10 | - |
| catalogo_unificato | `SOC_RIC_001` | Ricorso Contenzioso Societario | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 16 / collegate 10 | - |
| catalogo_unificato | `STD_001` | Conferimento di incarico | OK | deontologia, ordinamento_professionale, specifica | 12 / collegate 11 | - |
| catalogo_unificato | `STD_002` | Preventivo professionale | OK | deontologia, ordinamento_professionale, specifica | 12 / collegate 11 | - |
| catalogo_unificato | `STD_003` | Accettazione del preventivo | OK | deontologia, ordinamento_professionale, specifica, telematica | 14 / collegate 12 | - |
| catalogo_unificato | `STD_004` | Procura alle liti | OK | deontologia, ordinamento_professionale, specifica | 12 / collegate 11 | - |
| catalogo_unificato | `STD_005` | Scheda raccolta documenti | OK | deontologia, ordinamento_professionale, specifica | 12 / collegate 11 | - |
| catalogo_unificato | `STD_006` | Checklist pre-azione | OK | deontologia, ordinamento_professionale, specifica | 12 / collegate 11 | - |
| catalogo_unificato | `STD_007` | Lettera al cliente sullo stato pratica | OK | deontologia, ordinamento_professionale, specifica | 12 / collegate 11 | - |
| catalogo_unificato | `STD_008` | Sollecito integrazione documenti | OK | deontologia, ordinamento_professionale, specifica | 13 / collegate 11 | - |
| catalogo_unificato | `STD_009` | Lettera di rinuncia all'incarico | OK | deontologia, ordinamento_professionale, specifica | 12 / collegate 11 | - |
| catalogo_unificato | `STD_010` | Lettera di revoca del mandato | OK | deontologia, ordinamento_professionale, specifica | 12 / collegate 11 | - |
| catalogo_unificato | `STD_011` | Informativa privacy cliente | OK | autorita, deontologia, ordinamento_professionale, secondaria_collegata, specifica | 17 / collegate 13 | - |
| catalogo_unificato | `STD_012` | Informativa costi e rischi | OK | autorita, deontologia, ordinamento_professionale, specifica | 14 / collegate 12 | - |
| catalogo_unificato | `STD_013` | Piano attività pratica | OK | deontologia, ordinamento_professionale, specifica | 12 / collegate 11 | - |
| catalogo_unificato | `STD_014` | Verbale riunione cliente | OK | deontologia, ordinamento_professionale, secondaria_collegata, specifica | 14 / collegate 12 | - |
| catalogo_unificato | `STD_015` | Chiusura pratica con esito | OK | deontologia, ordinamento_professionale, specifica | 12 / collegate 11 | - |
| catalogo_unificato | `STD_016` | Sollecito pagamento parcella | OK | deontologia, ordinamento_professionale, specifica | 13 / collegate 11 | - |
| catalogo_unificato | `STD_017` | Messa in mora parcella | OK | deontologia, ordinamento_professionale, specifica | 13 / collegate 11 | - |
| catalogo_unificato | `STD_018` | Accordo saldo parcella | OK | deontologia, ordinamento_professionale, specifica | 12 / collegate 11 | - |
| catalogo_unificato | `STD_019` | Nota proforma | OK | deontologia, ordinamento_professionale, specifica | 12 / collegate 11 | - |
| catalogo_unificato | `STD_020` | Richiesta fondo spese | OK | deontologia, ordinamento_professionale, specifica | 12 / collegate 11 | - |
| catalogo_unificato | `STR_001` | Sollecito bonario | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| catalogo_unificato | `STR_002` | Primo sollecito commerciale | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| catalogo_unificato | `STR_003` | Secondo sollecito | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| catalogo_unificato | `STR_004` | Messa in mora | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| catalogo_unificato | `STR_005` | Diffida ad adempiere | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| catalogo_unificato | `STR_006` | Intimazione finale di pagamento | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 19 / collegate 10 | - |
| catalogo_unificato | `STR_007` | Piano di rientro | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| catalogo_unificato | `STR_008` | Accordo saldo e stralcio | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| catalogo_unificato | `STR_009` | Ricognizione di debito | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| catalogo_unificato | `STR_010` | Transazione semplice | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| catalogo_unificato | `STR_011` | Transazione novativa | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| catalogo_unificato | `STR_012` | Costituzione in mora del debitore | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 19 / collegate 9 | - |
| catalogo_unificato | `STR_013` | Costituzione in mora del fideiussore | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 19 / collegate 9 | - |
| catalogo_unificato | `STR_014` | Diffida per restituzione di beni | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| catalogo_unificato | `STR_015` | Diffida per cessazione di condotta lesiva | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| catalogo_unificato | `STR_016` | Lettera interruttiva della prescrizione | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| catalogo_unificato | `STR_017` | Invito a negoziazione assistita | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `STR_018` | Invito a mediazione | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `STR_019` | Riscontro a diffida | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| catalogo_unificato | `STR_020` | Lettera pre-precetto | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| catalogo_unificato | `STR_ATR_001` | Accordo Transattivo | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 19 / collegate 9 | - |
| catalogo_unificato | `STR_BLT_001` | Diffida stragiudiziale collegata al fascicolo | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 19 / collegate 9 | - |
| catalogo_unificato | `STR_BLT_002` | Sollecito di pagamento | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 20 / collegate 10 | - |
| catalogo_unificato | `STR_BLT_003` | Lettera adeguamento canone locazione | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 20 / collegate 9 | - |
| catalogo_unificato | `STR_BLT_004` | Diffida ad adempiere | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| catalogo_unificato | `STR_BLT_005` | Richiesta di documentazione | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 19 / collegate 9 | - |
| catalogo_unificato | `STR_BLT_006` | Comunicazione di riserva diritti | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 19 / collegate 9 | - |
| catalogo_unificato | `STR_BLT_007` | Invito a negoziazione assistita | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| catalogo_unificato | `STR_BLT_008` | Atto di messa in mora | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 19 / collegate 9 | - |
| catalogo_unificato | `STR_COM_001` | Comunicazione Professionale | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| catalogo_unificato | `STR_CONTEST_001` | Lettera di Contestazione | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 19 / collegate 9 | - |
| catalogo_unificato | `STR_DIFF_001` | Diffida | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 22 / collegate 11 | - |
| catalogo_unificato | `STR_INC_001` | Incarico Professionale | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 28 / collegate 18 | - |
| catalogo_unificato | `STR_INVAD_001` | Invito ad Adempiere | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 19 / collegate 9 | - |
| catalogo_unificato | `STR_MM_001` | Messa in Mora | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 21 / collegate 11 | - |
| catalogo_unificato | `STR_PAR_001` | Parere Sintetico | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 19 / collegate 9 | - |
| catalogo_unificato | `STR_PREV_001` | Preventivo Professionale | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 24 / collegate 14 | - |
| catalogo_unificato | `STR_PTR_001` | Proposta Transattiva | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 22 / collegate 11 | - |
| catalogo_unificato | `STR_RDP_001` | Richiesta di Pagamento | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 20 / collegate 10 | - |
| catalogo_unificato | `STR_RISDIFF_001` | Riscontro a Diffida | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 19 / collegate 9 | - |
| catalogo_unificato | `STR_SOLL_001` | Sollecito Formale | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 19 / collegate 9 | - |
| catalogo_unificato | `TMP-AMM-001` | Ricorso al TAR | OK | base_comune, secondaria_collegata, specifica, telematica | 4 / collegate 3 | - |
| catalogo_unificato | `TMP-AMM-002` | Motivi aggiunti | OK | secondaria_collegata, specifica, telematica | 4 / collegate 3 | - |
| catalogo_unificato | `TMP-AMM-003` | Appello al Consiglio di Stato | OK | base_comune, secondaria_collegata, specifica, telematica | 4 / collegate 3 | - |
| catalogo_unificato | `TMP-CAUT-001` | Ricorso per decreto ingiuntivo | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 13 / collegate 8 | - |
| catalogo_unificato | `TMP-CAUT-002` | Opposizione a decreto ingiuntivo | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 14 / collegate 8 | - |
| catalogo_unificato | `TMP-CAUT-003` | Istanza di provvisoria esecuzione | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 15 / collegate 8 | - |
| catalogo_unificato | `TMP-CAUT-004` | Ricorso cautelare d'urgenza | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 13 / collegate 8 | - |
| catalogo_unificato | `TMP-CAUT-005` | Reclamo cautelare | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 13 / collegate 8 | - |
| catalogo_unificato | `TMP-CAUT-006` | Ricorso per sequestro conservativo | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 13 / collegate 8 | - |
| catalogo_unificato | `TMP-CAUT-007` | Ricorso per sequestro giudiziario | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 13 / collegate 8 | - |
| catalogo_unificato | `TMP-CAUT-008` | Denuncia di nuova opera | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 13 / collegate 8 | - |
| catalogo_unificato | `TMP-CAUT-009` | Denuncia di danno temuto | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 13 / collegate 8 | - |
| catalogo_unificato | `TMP-CAUT-010` | Azione di manutenzione nel possesso | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 13 / collegate 8 | - |
| catalogo_unificato | `TMP-CAUT-011` | Azione di reintegrazione nel possesso | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 14 / collegate 8 | - |
| catalogo_unificato | `TMP-CAUT-012` | Ricorso per accertamento tecnico preventivo | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 15 / collegate 10 | - |
| catalogo_unificato | `TMP-CIV-001` | Atto di citazione | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `TMP-CIV-002` | Ricorso ex art. 702-bis / rito semplificato | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 11 / collegate 8 | - |
| catalogo_unificato | `TMP-CIV-003` | Comparsa di costituzione e risposta | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `TMP-CIV-004` | Memoria n. 1 | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `TMP-CIV-005` | Memoria n. 2 | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `TMP-CIV-006` | Memoria n. 3 | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `TMP-CIV-007` | Memoria generica | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `TMP-CIV-008` | Memoria istruttoria | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `TMP-CIV-009` | Nota di deposito | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `TMP-CIV-010` | Istanza di rinvio | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `TMP-CIV-011` | Istanza di trattazione scritta | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `TMP-CIV-012` | Note d'udienza | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `TMP-CIV-013` | Comparsa conclusionale | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `TMP-CIV-014` | Memoria di replica | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `TMP-CIV-015` | Istanza di anticipazione udienza | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `TMP-CIV-016` | Istanza di riunione procedimenti | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `TMP-CIV-017` | Istanza di separazione procedimenti | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 11 / collegate 8 | - |
| catalogo_unificato | `TMP-CIV-018` | Riassunzione del giudizio | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `TMP-CIV-019` | Note conclusive | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `TMP-ESE-001` | Atto di precetto | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `TMP-ESE-002` | Pignoramento mobiliare | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `TMP-ESE-003` | Pignoramento presso terzi | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `TMP-ESE-004` | Pignoramento immobiliare | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `TMP-ESE-005` | Istanza di ricerca telematica dei beni | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `TMP-ESE-006` | Istanza di vendita | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `TMP-ESE-007` | Istanza di assegnazione | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `TMP-ESE-008` | Opposizione all'esecuzione | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 11 / collegate 8 | - |
| catalogo_unificato | `TMP-ESE-009` | Opposizione agli atti esecutivi | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 11 / collegate 8 | - |
| catalogo_unificato | `TMP-ESE-010` | Opposizione di terzo all'esecuzione | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 11 / collegate 8 | - |
| catalogo_unificato | `TMP-ESE-011` | Istanza di conversione del pignoramento | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `TMP-ESE-012` | Istanza di riduzione del pignoramento | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `TMP-ESE-013` | Intervento del creditore | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 11 / collegate 9 | - |
| catalogo_unificato | `TMP-ESE-014` | Istanza di sospensione della procedura esecutiva | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 11 / collegate 8 | - |
| catalogo_unificato | `TMP-ESE-015` | Nota di precisazione del credito | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 11 / collegate 9 | - |
| catalogo_unificato | `TMP-ESE-016` | Dichiarazione 553 c.p.c. | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `TMP-ESE-017` | Pignoramento stipendio o pensione | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `TMP-FAM-001` | Ricorso per separazione consensuale | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `TMP-FAM-002` | Ricorso per separazione giudiziale | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `TMP-FAM-003` | Ricorso per divorzio congiunto | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 11 / collegate 8 | - |
| catalogo_unificato | `TMP-FAM-004` | Ricorso per divorzio giudiziale | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 11 / collegate 8 | - |
| catalogo_unificato | `TMP-FAM-005` | Ricorso per modifica condizioni di separazione | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `TMP-FAM-006` | Ricorso per modifica condizioni di divorzio | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 11 / collegate 8 | - |
| catalogo_unificato | `TMP-FAM-007` | Ricorso per affidamento e mantenimento figli | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 11 / collegate 8 | - |
| catalogo_unificato | `TMP-FAM-008` | Ricorso per ordine di protezione contro gli abusi familiari | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `TMP-FAM-009` | Ricorso per autorizzazione ad atto di straordinaria amministrazione del minore | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 11 / collegate 8 | - |
| catalogo_unificato | `TMP-FAM-010` | Ricorso per amministrazione di sostegno | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `TMP-FAM-011` | Istanze al giudice tutelare | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 11 / collegate 8 | - |
| catalogo_unificato | `TMP-FAM-012` | Volontaria giurisdizione | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 12 / collegate 9 | - |
| catalogo_unificato | `TMP-FAM-013` | Ricorso per decreto tavolare | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `TMP-FAM-014` | Istanza al giudice tutelare | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 11 / collegate 8 | - |
| catalogo_unificato | `TMP-IMP-001` | Atto di appello | OK | base_comune, secondaria_collegata, specifica | 4 / collegate 2 | - |
| catalogo_unificato | `TMP-IMP-002` | Comparsa di costituzione in appello | OK | base_comune, secondaria_collegata, specifica | 5 / collegate 2 | - |
| catalogo_unificato | `TMP-IMP-003` | Ricorso per cassazione | OK | base_comune, secondaria_collegata, specifica | 4 / collegate 2 | - |
| catalogo_unificato | `TMP-IMP-004` | Controricorso | OK | base_comune, secondaria_collegata, specifica | 4 / collegate 2 | - |
| catalogo_unificato | `TMP-IMP-005` | Ricorso per revocazione | OK | base_comune, secondaria_collegata, specifica | 4 / collegate 2 | - |
| catalogo_unificato | `TMP-IMP-006` | Opposizione di terzo | OK | base_comune, secondaria_collegata, specifica | 5 / collegate 2 | - |
| catalogo_unificato | `TMP-IMP-007` | Ricorso per regolamento di competenza | OK | base_comune, secondaria_collegata, specifica | 4 / collegate 2 | - |
| catalogo_unificato | `TMP-IMP-008` | Ricorso per regolamento di giurisdizione | OK | base_comune, secondaria_collegata, specifica | 4 / collegate 2 | - |
| catalogo_unificato | `TMP-IMP-009` | Istanza di sospensione dell'esecutivita della sentenza | OK | base_comune, secondaria_collegata, specifica | 5 / collegate 2 | - |
| catalogo_unificato | `TMP-IMP-010` | Istanza di correzione errore materiale | OK | base_comune, secondaria_collegata, specifica | 4 / collegate 2 | - |
| catalogo_unificato | `TMP-IMP-011` | Istanza di integrazione del contraddittorio | OK | base_comune, secondaria_collegata, specifica | 4 / collegate 2 | - |
| catalogo_unificato | `TMP-IMP-012` | Reclamo | OK | base_comune, secondaria_collegata, specifica | 4 / collegate 2 | - |
| catalogo_unificato | `TMP-IMP-013` | Ricorso ex legge Pinto | OK | base_comune, secondaria_collegata, specifica | 4 / collegate 2 | - |
| catalogo_unificato | `TMP-LAV-001` | Ricorso lavoro | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `TMP-LAV-002` | Memoria difensiva nel rito lavoro | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 12 / collegate 8 | - |
| catalogo_unificato | `TMP-LAV-003` | Ricorso d'urgenza in materia di lavoro | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 11 / collegate 8 | - |
| catalogo_unificato | `TMP-LAV-004` | Impugnazione licenziamento | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 14 / collegate 9 | - |
| catalogo_unificato | `TMP-LAV-005` | Ricorso per differenze retributive | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 15 / collegate 12 | - |
| catalogo_unificato | `TMP-LAV-006` | Ricorso previdenziale | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `TMP-LAV-007` | Appello nel rito lavoro | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 12 / collegate 8 | - |
| catalogo_unificato | `TMP-LAV-008` | Ricorso monitorio in materia di lavoro | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `TMP-LAV-009` | Opposizione a decreto ingiuntivo in materia di lavoro | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 11 / collegate 8 | - |
| catalogo_unificato | `TMP-LAV-010` | Ricorso per condotta antisindacale | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| catalogo_unificato | `TMP-NOT-001` | Atto UNEP | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 12 / collegate 9 | - |
| catalogo_unificato | `TMP-NOT-002` | Atto per notificazione in proprio | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 12 / collegate 9 | - |
| catalogo_unificato | `TMP-NOT-003` | Relata di notifica PEC | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 12 / collegate 9 | - |
| catalogo_unificato | `TMP-NOT-004` | Deposito telematico documenti | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 13 / collegate 10 | - |
| catalogo_unificato | `TMP-NOT-005` | Visibilita fascicolo telematico | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 12 / collegate 9 | - |
| catalogo_unificato | `TMP-NOT-006` | Fascicolo di parte | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 12 / collegate 9 | - |
| catalogo_unificato | `TMP-NOT-007` | Attestazione di conformita | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 12 / collegate 9 | - |
| catalogo_unificato | `TMP-NOT-008` | Indice allegati | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 12 / collegate 9 | - |
| catalogo_unificato | `TMP-NOT-009` | Note iscrizione ruolo | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 12 / collegate 9 | - |
| catalogo_unificato | `TMP-PEN-001` | Querela | OK | base_comune, specifica, telematica | 2 / collegate 1 | - |
| catalogo_unificato | `TMP-PEN-002` | Denuncia | OK | base_comune, specifica, telematica | 2 / collegate 1 | - |
| catalogo_unificato | `TMP-PEN-003` | Nomina del difensore di fiducia | OK | base_comune, specifica, telematica | 2 / collegate 1 | - |
| catalogo_unificato | `TMP-PEN-004` | Opposizione alla richiesta di archiviazione | OK | base_comune, specifica, telematica | 3 / collegate 1 | - |
| catalogo_unificato | `TMP-PEN-005` | Memoria difensiva penale | OK | base_comune, specifica, telematica | 2 / collegate 1 | - |
| catalogo_unificato | `TMP-PEN-006` | Istanza di riesame di misura cautelare | OK | base_comune, specifica, telematica | 3 / collegate 1 | - |
| catalogo_unificato | `TMP-PEN-007` | Appello cautelare penale | OK | base_comune, specifica, telematica | 3 / collegate 1 | - |
| catalogo_unificato | `TMP-PEN-008` | Ricorso per cassazione penale | OK | base_comune, specifica, telematica | 2 / collegate 1 | - |
| catalogo_unificato | `TMP-PEN-009` | Atto di costituzione di parte civile | OK | base_comune, specifica, telematica | 3 / collegate 1 | - |
| catalogo_unificato | `TMP-PEN-010` | Lista testi | OK | base_comune, specifica, telematica | 2 / collegate 1 | - |
| catalogo_unificato | `TMP-PEN-011` | Istanza di incidente probatorio | OK | base_comune, specifica, telematica | 2 / collegate 1 | - |
| catalogo_unificato | `TMP-PEN-012` | Istanza di revoca o sostituzione della misura cautelare | OK | base_comune, specifica, telematica | 3 / collegate 1 | - |
| catalogo_unificato | `TMP-PROC-001` | Procura alle liti | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `TMP-PROC-002` | Procura generale alle liti | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `TMP-PROC-003` | Procura speciale per ricorso monitorio | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 12 / collegate 9 | - |
| catalogo_unificato | `TMP-PROC-004` | Procura speciale per appello | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 12 / collegate 9 | - |
| catalogo_unificato | `TMP-PROC-005` | Procura speciale per ricorso per cassazione | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 12 / collegate 9 | - |
| catalogo_unificato | `TMP-PROC-006` | Procura per fase esecutiva | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `TMP-PROC-007` | Nomina domiciliatario | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 11 / collegate 9 | - |
| catalogo_unificato | `TMP-PROC-008` | Revoca del mandato difensivo | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `TMP-PROC-009` | Rinuncia al mandato | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `TMP-PROC-010` | Elezione di domicilio | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| catalogo_unificato | `TMP-STR-001` | Diffida stragiudiziale collegata al fascicolo | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 6 | - |
| catalogo_unificato | `TMP-STR-002` | Sollecito di pagamento | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 11 / collegate 7 | - |
| catalogo_unificato | `TMP-STR-003` | Lettera adeguamento canone locazione | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 6 | - |
| catalogo_unificato | `TMP-STR-004` | Diffida ad adempiere | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 6 | - |
| catalogo_unificato | `TMP-STR-005` | Richiesta di documentazione | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `TMP-STR-006` | Comunicazione di riserva diritti | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `TMP-STR-007` | Invito a negoziazione assistita | OK | autorita, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 16 / collegate 10 | - |
| catalogo_unificato | `TMP-STR-008` | Atto di messa in mora | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 10 / collegate 6 | - |
| catalogo_unificato | `TMP-TRIB-001` | Ricorso tributario | OK | base_comune, secondaria_collegata, specifica, telematica | 7 / collegate 4 | - |
| catalogo_unificato | `TMP-TRIB-002` | Controdeduzioni nel giudizio tributario | OK | secondaria_collegata, specifica, telematica | 6 / collegate 4 | - |
| catalogo_unificato | `TMP-TRIB-003` | Appello tributario | OK | base_comune, secondaria_collegata, specifica, telematica | 6 / collegate 4 | - |
| catalogo_unificato | `TRIB_CONTROAPP_001` | Controdeduzioni in Appello | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 6 | - |
| catalogo_unificato | `TRIB_DEPDOC_001` | Deposito Documenti Tributario | OK | deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 7 | - |
| catalogo_unificato | `TRIB_IST_001` | Istanza Generica Tributaria | OK | deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 6 | - |
| catalogo_unificato | `TRIB_MEMILL_001` | Memoria Illustrativa | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 6 | - |
| catalogo_unificato | `TRIB_SOSP_001` | Istanza di Sospensione | OK | deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 6 | - |
| catalogo_unificato | `TRI_001` | Ricorso tributario | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `TRI_002` | Reclamo-mediazione tributaria | OK | autorita, deontologia, secondaria_collegata, specifica, telematica | 15 / collegate 9 | - |
| catalogo_unificato | `TRI_003` | Appello tributario | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `TRI_004` | Controdeduzioni | OK | deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `TRI_005` | Memoria illustrativa tributaria | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `TRI_006` | Istanza di sospensione dell'esecutività dell'atto | OK | deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `TRI_007` | Istanza di trattazione in pubblica udienza | OK | deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `TRI_008` | Istanza di rinvio | OK | deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `TRI_009` | Nota di deposito documenti | OK | deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 7 | - |
| catalogo_unificato | `TRI_010` | Motivi aggiunti | OK | deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `TRI_011` | Ricorso contro cartella | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `TRI_012` | Ricorso contro intimazione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `TRI_013` | Ricorso contro fermo | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `TRI_014` | Ricorso contro ipoteca | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `TRI_015` | Ricorso IMU | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `TRI_016` | Ricorso TARI | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 7 | - |
| catalogo_unificato | `TRI_017` | Ricorso su tributi locali | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `TRI_018` | Ricorso contro avviso di accertamento | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 6 | - |
| catalogo_unificato | `TRI_019` | Ricorso contro diniego di rimborso | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 6 | - |
| catalogo_unificato | `TRI_020` | Istanza di conciliazione tributaria | OK | autorita, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 7 | - |
| catalogo_unificato | `VGS_001` | Ricorso per amministrazione di sostegno | OK | base_comune, specifica, telematica | 6 / collegate 2 | - |
| catalogo_unificato | `VGS_002` | Istanza di modifica dell'amministrazione di sostegno | OK | base_comune, specifica, telematica | 6 / collegate 2 | - |
| catalogo_unificato | `VGS_003` | Istanza di rendiconto dell'amministrazione di sostegno | OK | base_comune, specifica, telematica | 6 / collegate 2 | - |
| catalogo_unificato | `VGS_004` | Ricorso per interdizione | OK | base_comune, specifica, telematica | 6 / collegate 2 | - |
| catalogo_unificato | `VGS_005` | Ricorso per inabilitazione | OK | base_comune, specifica, telematica | 6 / collegate 2 | - |
| catalogo_unificato | `VGS_006` | Ricorso per nomina del tutore | OK | base_comune, specifica, telematica | 6 / collegate 2 | - |
| catalogo_unificato | `VGS_007` | Ricorso per nomina del curatore | OK | base_comune, specifica, telematica | 7 / collegate 2 | - |
| catalogo_unificato | `VGS_008` | Ricorso al giudice tutelare per autorizzazione | OK | base_comune, specifica, telematica | 6 / collegate 2 | - |
| catalogo_unificato | `VGS_009` | Istanza di autorizzazione alla riscossione di somme | OK | base_comune, specifica, telematica | 6 / collegate 2 | - |
| catalogo_unificato | `VGS_010` | Istanza di autorizzazione alla vendita di bene del minore o incapace | OK | base_comune, specifica, telematica | 6 / collegate 2 | - |
| catalogo_unificato | `VGS_011` | Istanza di autorizzazione all'accettazione dell'eredità con beneficio | OK | base_comune, specifica, telematica | 8 / collegate 3 | - |
| catalogo_unificato | `VGS_012` | Istanza di autorizzazione alla rinuncia all'eredità | OK | base_comune, deontologia, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `VGS_013` | Ricorso per nomina del curatore dell'eredità giacente | OK | base_comune, specifica, telematica | 7 / collegate 2 | - |
| catalogo_unificato | `VGS_014` | Accettazione dell'eredità con beneficio di inventario | OK | base_comune, specifica, telematica | 10 / collegate 4 | - |
| catalogo_unificato | `VGS_015` | Rinuncia all'eredità | OK | base_comune, deontologia, specifica, telematica | 7 / collegate 3 | - |
| catalogo_unificato | `VGS_016` | Istanza per la formazione dell'inventario | OK | base_comune, specifica, telematica | 8 / collegate 3 | - |
| catalogo_unificato | `VGS_017` | Ricorso per rettifica di atti di stato civile | OK | base_comune, specifica, telematica | 6 / collegate 2 | - |
| catalogo_unificato | `VGS_018` | Ricorso per cambio nome o cognome | OK | base_comune, specifica, telematica | 6 / collegate 2 | - |
| catalogo_unificato | `VGS_019` | Ricorso per autorizzazione alla divisione ereditaria con minori | OK | base_comune, specifica, telematica | 8 / collegate 3 | - |
| compilatore_atti | `STR_DIFF_001` | Diffida | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| compilatore_atti | `STR_MM_001` | Messa in Mora | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| compilatore_atti | `STR_RDP_001` | Richiesta di Pagamento | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 19 / collegate 10 | - |
| compilatore_atti | `STR_SOLL_001` | Sollecito Formale | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| compilatore_atti | `STR_COM_001` | Comunicazione Professionale | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| compilatore_atti | `STR_CONTEST_001` | Lettera di Contestazione | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| compilatore_atti | `STR_RISDIFF_001` | Riscontro a Diffida | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| compilatore_atti | `STR_INVAD_001` | Invito ad Adempiere | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| compilatore_atti | `STR_PTR_001` | Proposta Transattiva | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| compilatore_atti | `STR_ATR_001` | Accordo Transattivo | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| compilatore_atti | `STR_PAR_001` | Parere Sintetico | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| compilatore_atti | `STR_INC_001` | Incarico Professionale | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 28 / collegate 18 | - |
| compilatore_atti | `STR_PREV_001` | Preventivo Professionale | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 24 / collegate 14 | - |
| compilatore_atti | `CIV_CIT_001` | Atto di Citazione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| compilatore_atti | `CIV_COM_001` | Comparsa di Costituzione e Risposta | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| compilatore_atti | `CIV_RDI_001` | Ricorso per Decreto Ingiuntivo | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| compilatore_atti | `CIV_OPPDI_001` | Opposizione a Decreto Ingiuntivo | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| compilatore_atti | `CIV_MEM_001` | Memoria Generica | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 5 | - |
| compilatore_atti | `CIV_IST_001` | Istanza Generica | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 5 | - |
| compilatore_atti | `CIV_DEPDOC_001` | Deposito Documenti | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 5 | - |
| compilatore_atti | `CIV_CONCL_001` | Comparsa Conclusionale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| compilatore_atti | `CIV_REPL_001` | Memoria di Replica | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 5 | - |
| compilatore_atti | `CIV_APP_001` | Appello Civile | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 5 | - |
| compilatore_atti | `CIV_PREC_001` | Atto di Precetto | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 5 | - |
| compilatore_atti | `CIV_PPT_001` | Pignoramento Presso Terzi | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 6 | - |
| compilatore_atti | `CIV_OPESE_001` | Opposizione all'Esecuzione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 5 | - |
| compilatore_atti | `CIV_OPATTESE_001` | Opposizione agli Atti Esecutivi | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 13 / collegate 8 | - |
| compilatore_atti | `CIV_RCAUT_001` | Ricorso Cautelare | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| compilatore_atti | `CIV_ICAUT_001` | Istanza Cautelare | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| compilatore_atti | `CIV_LAVRIC_001` | Ricorso in Materia di Lavoro | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| compilatore_atti | `CIV_LAVMEM_001` | Memoria Difensiva Lavoro | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| compilatore_atti | `CIV_SFRINT_001` | Intimazione di Sfratto | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 13 / collegate 6 | - |
| compilatore_atti | `CIV_CONVSFR_001` | Citazione per Convalida di Sfratto | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| compilatore_atti | `CIV_PROCBASE_001` | Procura / Mandato Difensivo | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 16 / collegate 11 | - |
| compilatore_atti | `CIV_NOTIFBASE_001` | Notifica / Adempimento Accessorio | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 13 / collegate 6 | - |
| compilatore_atti | `CIV_PIGBASE_001` | Pignoramento Mobiliare / Immobiliare | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 5 | - |
| compilatore_atti | `PEN_NOM_001` | Nomina Difensore | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| compilatore_atti | `PEN_MEM_001` | Memoria Difensiva | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| compilatore_atti | `PEN_IST_001` | Istanza Generica Penale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| compilatore_atti | `PEN_RINV_001` | Istanza di Rinvio | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| compilatore_atti | `PEN_COPIE_001` | Richiesta Copie | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| compilatore_atti | `PEN_DEPDOC_001` | Deposito Documenti Penale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 9 | - |
| compilatore_atti | `PEN_OPPDP_001` | Opposizione a Decreto Penale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| compilatore_atti | `PEN_IMP_001` | Atto di Impugnazione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| compilatore_atti | `PEN_PM_001` | Istanza al Pubblico Ministero | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| compilatore_atti | `PEN_DISSEQ_001` | Istanza di Dissequestro | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 8 | - |
| compilatore_atti | `PEN_NOTEUD_001` | Note d'Udienza Penale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| compilatore_atti | `PEN_SEGNBASE_001` | Querela / Denuncia | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| compilatore_atti | `PEN_PARTECIVBASE_001` | Costituzione di Parte Civile | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| compilatore_atti | `PEN_LISTATESTI_001` | Lista Testi | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| compilatore_atti | `AMM_RIC_001` | Ricorso al TAR | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| compilatore_atti | `AMM_MOTAGG_001` | Motivi Aggiunti | OK | autorita, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| compilatore_atti | `AMM_ICAUT_001` | Istanza Cautelare Amministrativa | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 13 / collegate 7 | - |
| compilatore_atti | `AMM_MEM_001` | Memoria Difensiva Amministrativa | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| compilatore_atti | `AMM_DEPDOC_001` | Deposito Documenti Amministrativo | OK | autorita, deontologia, secondaria_collegata, specifica, telematica | 13 / collegate 8 | - |
| compilatore_atti | `AMM_NOTEUD_001` | Note d'Udienza Amministrative | OK | autorita, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| compilatore_atti | `AMM_APPCDS_001` | Appello al Consiglio di Stato | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| compilatore_atti | `AMM_APPCAUT_001` | Appello Cautelare | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 13 / collegate 7 | - |
| compilatore_atti | `AMM_SEG_001` | Istanza di Segreteria | OK | autorita, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 7 | - |
| compilatore_atti | `TRIB_RIC_001` | Ricorso Tributario | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 6 | - |
| compilatore_atti | `TRIB_CONTRO_001` | Controdeduzioni | OK | deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 6 | - |
| compilatore_atti | `TRIB_SOSP_001` | Istanza di Sospensione | OK | deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 6 | - |
| compilatore_atti | `TRIB_MEMILL_001` | Memoria Illustrativa | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 6 | - |
| compilatore_atti | `TRIB_DEPDOC_001` | Deposito Documenti Tributario | OK | deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 7 | - |
| compilatore_atti | `TRIB_APP_001` | Appello Tributario | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 6 | - |
| compilatore_atti | `TRIB_CONTROAPP_001` | Controdeduzioni in Appello | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 6 | - |
| compilatore_atti | `TRIB_IST_001` | Istanza Generica Tributaria | OK | deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 6 | - |
| compilatore_atti | `FAM_SEPC_001` | Ricorso Separazione Consensuale | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| compilatore_atti | `FAM_SEPG_001` | Ricorso Separazione Giudiziale | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| compilatore_atti | `FAM_DIVC_001` | Ricorso Divorzio Congiunto | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| compilatore_atti | `FAM_DIVG_001` | Ricorso Divorzio Giudiziale | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| compilatore_atti | `FAM_MOD_001` | Ricorso Modifica Condizioni Separazione/Divorzio | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| compilatore_atti | `FAM_AFF_001` | Ricorso Affidamento e Responsabilita Genitoriale | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| compilatore_atti | `FAM_ADS_001` | Ricorso Nomina Amministratore di Sostegno | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| compilatore_atti | `FAM_MADS_001` | Ricorso Modifica/Revoca Amministrazione di Sostegno | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| compilatore_atti | `FAM_TUT_001` | Ricorso Tutela / Curatela | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| compilatore_atti | `FAM_REC_001` | Reclamo / Appello in Materia di Famiglia | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| compilatore_atti | `FAM_MEMO_001` | Memoria Difensiva Famiglia | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| compilatore_atti | `LAV_IMPLIC_001` | Impugnazione Licenziamento | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| compilatore_atti | `LAV_RIC_001` | Ricorso in Materia di Lavoro | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 20 / collegate 10 | - |
| compilatore_atti | `LAV_MEM_001` | Memoria Difensiva Lavoro | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 20 / collegate 10 | - |
| compilatore_atti | `LAV_APP_001` | Appello in Materia di Lavoro | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 20 / collegate 10 | - |
| compilatore_atti | `LAV_DISC_001` | Ricorso per Procedura Disciplinare | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 20 / collegate 10 | - |
| compilatore_atti | `LAV_PREV_001` | Ricorso Previdenziale | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 20 / collegate 10 | - |
| compilatore_atti | `LAV_APPPREV_001` | Appello Previdenziale | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 20 / collegate 10 | - |
| compilatore_atti | `LAV_ISTAMM_001` | Ricorso Amministrativo Previdenziale | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| compilatore_atti | `SOC_PAR_001` | Parere Societario | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 14 / collegate 9 | - |
| compilatore_atti | `SOC_CONT_001` | Contratto Commerciale | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 14 / collegate 9 | - |
| compilatore_atti | `SOC_MEM_001` | Memoria Difensiva Societaria | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 14 / collegate 9 | - |
| compilatore_atti | `SOC_RIC_001` | Ricorso Contenzioso Societario | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 14 / collegate 9 | - |
| compilatore_atti | `SOC_RESP_001` | Atto per Responsabilita Organi Sociali | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 14 / collegate 9 | - |
| compilatore_atti | `SOC_OPSTR_001` | Parere su Operazione Straordinaria | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 15 / collegate 10 | - |
| compilatore_atti | `SOC_DUEDIL_001` | Report Due Diligence Contrattuale | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 14 / collegate 9 | - |
| compilatore_atti | `IMM_PERMSOG_001` | Ricorso Permesso di Soggiorno | OK | autorita, base_comune, specifica | 4 / collegate 1 | - |
| compilatore_atti | `IMM_PROT_001` | Ricorso Protezione Internazionale | OK | autorita, base_comune, specifica | 4 / collegate 1 | - |
| compilatore_atti | `IMM_EXPUL_001` | Ricorso contro Espulsione / Respingimento | OK | autorita, base_comune, specifica | 4 / collegate 1 | - |
| compilatore_atti | `IMM_CITTA_001` | Ricorso per Cittadinanza | OK | autorita, base_comune, specifica | 4 / collegate 1 | - |
| compilatore_atti | `IMM_RIUN_001` | Istanza Ricongiungimento Familiare | OK | autorita, specifica | 4 / collegate 1 | - |
| compilatore_atti | `CIV_PROC_001` | Procura alle liti | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 15 / collegate 10 | - |
| compilatore_atti | `CIV_PROC_002` | Procura generale alle liti | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 15 / collegate 10 | - |
| compilatore_atti | `CIV_PROC_003` | Procura speciale per ricorso monitorio | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 19 / collegate 11 | - |
| compilatore_atti | `CIV_PROC_004` | Procura speciale per appello | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 11 | - |
| compilatore_atti | `CIV_PROC_005` | Procura speciale per ricorso per cassazione | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 11 | - |
| compilatore_atti | `CIV_PROC_006` | Procura per fase esecutiva | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 15 / collegate 10 | - |
| compilatore_atti | `CIV_PROC_007` | Nomina domiciliatario | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 17 / collegate 11 | - |
| compilatore_atti | `CIV_PROC_008` | Revoca del mandato difensivo | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 16 / collegate 11 | - |
| compilatore_atti | `CIV_PROC_009` | Rinuncia al mandato | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 16 / collegate 11 | - |
| compilatore_atti | `CIV_PROC_010` | Elezione di domicilio | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 15 / collegate 10 | - |
| compilatore_atti | `CIV_NOT_001` | Atto UNEP | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 13 / collegate 6 | - |
| compilatore_atti | `CIV_NOT_002` | Atto per notificazione in proprio | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 13 / collegate 6 | - |
| compilatore_atti | `CIV_NOT_003` | Relata di notifica PEC | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 13 / collegate 6 | - |
| compilatore_atti | `CIV_NOT_004` | Deposito telematico documenti | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 14 / collegate 7 | - |
| compilatore_atti | `CIV_NOT_005` | Visibilita fascicolo telematico | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 13 / collegate 6 | - |
| compilatore_atti | `CIV_NOT_006` | Fascicolo di parte | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 13 / collegate 6 | - |
| compilatore_atti | `CIV_NOT_007` | Attestazione di conformita | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 13 / collegate 6 | - |
| compilatore_atti | `CIV_NOT_008` | Indice allegati | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 13 / collegate 6 | - |
| compilatore_atti | `CIV_NOT_009` | Note iscrizione ruolo | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 13 / collegate 6 | - |
| compilatore_atti | `STR_BLT_001` | Diffida stragiudiziale collegata al fascicolo | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| compilatore_atti | `STR_BLT_002` | Sollecito di pagamento | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 19 / collegate 10 | - |
| compilatore_atti | `STR_BLT_003` | Lettera adeguamento canone locazione | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 19 / collegate 9 | - |
| compilatore_atti | `STR_BLT_004` | Diffida ad adempiere | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| compilatore_atti | `STR_BLT_005` | Richiesta di documentazione | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| compilatore_atti | `STR_BLT_006` | Comunicazione di riserva diritti | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| compilatore_atti | `STR_BLT_007` | Invito a negoziazione assistita | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| compilatore_atti | `STR_BLT_008` | Atto di messa in mora | OK | autorita, base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 18 / collegate 9 | - |
| compilatore_atti | `CIV_INT_001` | Ricorso ex art. 702-bis / rito semplificato | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| compilatore_atti | `CIV_INT_002` | Riassunzione del giudizio | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| compilatore_atti | `CIV_INT_003` | Reclamo cautelare | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| compilatore_atti | `CIV_INT_004` | Ricorso per sequestro conservativo | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 13 / collegate 5 | - |
| compilatore_atti | `CIV_INT_005` | Ricorso per sequestro giudiziario | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 13 / collegate 5 | - |
| compilatore_atti | `CIV_INT_006` | Denuncia di nuova opera | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| compilatore_atti | `CIV_INT_007` | Denuncia di danno temuto | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| compilatore_atti | `CIV_INT_008` | Azione di manutenzione nel possesso | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| compilatore_atti | `CIV_INT_009` | Azione di reintegrazione nel possesso | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| compilatore_atti | `CIV_INT_010` | Ricorso per accertamento tecnico preventivo | OK | base_comune, deontologia, ordinamento_professionale, secondaria_collegata, specifica, telematica | 13 / collegate 7 | - |
| compilatore_atti | `CIV_SUC_001` | Memoria n. 1 | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| compilatore_atti | `CIV_SUC_002` | Memoria n. 2 | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| compilatore_atti | `CIV_SUC_003` | Memoria n. 3 | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| compilatore_atti | `CIV_SUC_004` | Memoria istruttoria | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| compilatore_atti | `CIV_SUC_005` | Istanza di rinvio | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| compilatore_atti | `CIV_SUC_006` | Istanza di trattazione scritta | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| compilatore_atti | `CIV_SUC_007` | Note d'udienza | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| compilatore_atti | `CIV_SUC_008` | Note conclusive | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| compilatore_atti | `CIV_SUC_009` | Istanza di anticipazione udienza | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| compilatore_atti | `CIV_SUC_010` | Istanza di riunione procedimenti | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| compilatore_atti | `CIV_SUC_011` | Istanza di separazione procedimenti | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| compilatore_atti | `CIV_SUC_012` | Istanza di provvisoria esecuzione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| compilatore_atti | `CIV_IMP_001` | Comparsa di costituzione in appello | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| compilatore_atti | `CIV_IMP_002` | Ricorso per cassazione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| compilatore_atti | `CIV_IMP_003` | Controricorso | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| compilatore_atti | `CIV_IMP_004` | Ricorso per revocazione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| compilatore_atti | `CIV_IMP_005` | Opposizione di terzo | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| compilatore_atti | `CIV_IMP_006` | Ricorso per regolamento di competenza | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| compilatore_atti | `CIV_IMP_007` | Ricorso per regolamento di giurisdizione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| compilatore_atti | `CIV_IMP_008` | Istanza di sospensione dell'esecutivita della sentenza | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 12 / collegate 5 | - |
| compilatore_atti | `CIV_IMP_009` | Istanza di correzione errore materiale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| compilatore_atti | `CIV_IMP_010` | Istanza di integrazione del contraddittorio | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| compilatore_atti | `CIV_IMP_011` | Reclamo | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| compilatore_atti | `CIV_IMP_012` | Ricorso ex legge Pinto | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| compilatore_atti | `CIV_ESE_001` | Pignoramento mobiliare | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 5 | - |
| compilatore_atti | `CIV_ESE_002` | Pignoramento immobiliare | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 5 | - |
| compilatore_atti | `CIV_ESE_003` | Istanza di ricerca telematica dei beni | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 5 | - |
| compilatore_atti | `CIV_ESE_004` | Istanza di vendita | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 5 | - |
| compilatore_atti | `CIV_ESE_005` | Istanza di assegnazione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 5 | - |
| compilatore_atti | `CIV_ESE_006` | Opposizione di terzo all'esecuzione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 5 | - |
| compilatore_atti | `CIV_ESE_007` | Istanza di conversione del pignoramento | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 5 | - |
| compilatore_atti | `CIV_ESE_008` | Istanza di riduzione del pignoramento | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 5 | - |
| compilatore_atti | `CIV_ESE_009` | Intervento del creditore | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 6 | - |
| compilatore_atti | `CIV_ESE_010` | Istanza di sospensione della procedura esecutiva | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 5 | - |
| compilatore_atti | `CIV_ESE_011` | Nota di precisazione del credito | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 11 / collegate 6 | - |
| compilatore_atti | `CIV_ESE_012` | Dichiarazione 553 c.p.c. | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 5 | - |
| compilatore_atti | `FAM_VG_001` | Ricorso per ordine di protezione contro gli abusi familiari | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| compilatore_atti | `FAM_VG_002` | Ricorso per autorizzazione ad atto di straordinaria amministrazione del minore | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| compilatore_atti | `FAM_VG_003` | Istanze al giudice tutelare | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| compilatore_atti | `FAM_VG_004` | Istanza al giudice tutelare | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| compilatore_atti | `FAM_VG_005` | Volontaria giurisdizione | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 25 / collegate 15 | - |
| compilatore_atti | `FAM_VG_006` | Ricorso per decreto tavolare | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 23 / collegate 14 | - |
| compilatore_atti | `LAV_BLT_001` | Ricorso d'urgenza in materia di lavoro | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 22 / collegate 10 | - |
| compilatore_atti | `LAV_BLT_002` | Ricorso per differenze retributive | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 20 / collegate 10 | - |
| compilatore_atti | `LAV_BLT_003` | Ricorso monitorio in materia di lavoro | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 21 / collegate 10 | - |
| compilatore_atti | `LAV_BLT_004` | Opposizione a decreto ingiuntivo in materia di lavoro | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 22 / collegate 10 | - |
| compilatore_atti | `LAV_BLT_005` | Ricorso per condotta antisindacale | OK | autorita, base_comune, deontologia, secondaria_collegata, specifica, telematica | 20 / collegate 10 | - |
| compilatore_atti | `PEN_BLT_001` | Querela | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| compilatore_atti | `PEN_BLT_002` | Denuncia | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| compilatore_atti | `PEN_BLT_003` | Opposizione alla richiesta di archiviazione | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| compilatore_atti | `PEN_BLT_004` | Istanza di riesame di misura cautelare | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| compilatore_atti | `PEN_BLT_005` | Appello cautelare penale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| compilatore_atti | `PEN_BLT_006` | Ricorso per cassazione penale | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| compilatore_atti | `PEN_BLT_007` | Atto di costituzione di parte civile | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
| compilatore_atti | `PEN_BLT_008` | Lista testi | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| compilatore_atti | `PEN_BLT_009` | Istanza di incidente probatorio | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 9 / collegate 8 | - |
| compilatore_atti | `PEN_BLT_010` | Istanza di revoca o sostituzione della misura cautelare | OK | base_comune, deontologia, secondaria_collegata, specifica, telematica | 10 / collegate 8 | - |
