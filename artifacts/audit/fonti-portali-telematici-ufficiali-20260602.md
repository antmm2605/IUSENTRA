# Fonti ufficiali portali telematici - audit 2 giugno 2026

Questo audit raccoglie le fonti pubbliche e le prove autorizzate usate per
separare i canali telematici di IUSENTRA. Non contiene PIN, cookie, token o
sessioni private.

## PST / PCT / PolisWeb / PDP / Cassazione / UNEP / SIGP

Fonti ufficiali controllate:

- `https://pst.giustizia.it/PST/it/services.page`
- `https://servizipst.giustizia.it/PST/it/pst_2_4.wp?ufficioSelect=giudiziari&distretto=&localita=&tipoUfficio=&action%3Asearch=ricerca`
- `https://servizipst.giustizia.it/PST/it/pst_2_4.wp?ufficioSelect=penali&distretto=&localita=&tipoUfficio=&action%3Asearch=ricerca`
- `https://pst.giustizia.it/PST/it/documentation.page`
- `https://pst.giustizia.it/PST/it/download.page`
- `https://pst.giustizia.it/PST/it/malfunzionamenti.page`
- `https://pst.giustizia.it/PST/it/dettaglio_schede_tematiche.page?contentId=ACC433&modelId=12`
- `https://pst.giustizia.it/PST/resources/cms/documents/PagTel_Vademecum_unico.pdf`
- `https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC3099`
- `https://pst.giustizia.it/PST/resources/cms/documents/PDA__Flussi_pagamento_telematico_tramite_PST_vers._6.3.pdf`
- `https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC3076`
- `https://servizipst.giustizia.it/PST/it/pagopa.wp`
- `docs/specs/ministero/A1_WSDL_CATALOG_v1.52/WSDL/Altri Servizi/Catalogo UG/CatalogoServiziBeanService.wsdl`
- `C:\QuickOrganizer\ListaUfficiGiudiziari.xml`

Esito verificato:

- La pagina `Servizi` distingue area pubblica e area riservata: `Uffici giudiziari`
  è area pubblica; consultazione registri, Cassazione, RegIndE, PDP e richieste
  visibilità richiedono autenticazione.
- La pagina `Uffici giudiziari` conferma che gli indirizzi PEC civili sono per
  deposito telematico di atti/documenti processuali da soggetti abilitati.
- La stessa pagina conferma per il penale che, quando per l'atto è previsto il
  deposito tramite portale, l'invio tramite PEC non è consentito e non produce
  effetto di legge.
- Catalogo pubblico PST civili: 1.781 voci.
- Catalogo pubblico PST penali: 1.416 voci.
- Schede dettaglio pubbliche PST controllate: 2.454, con zero errori HTTP.
- Voci civili prudenzialmente depositabili: 1.041; voci storiche/non operative:
  740.
- Voci penali prudenzialmente depositabili: 1.413; voci storiche/non operative:
  3.
- La fonte pubblica non espone un flag universale `attivo`: IUSENTRA non sceglie
  automaticamente per nome voci con diciture di ufficio storico/non operativo,
  `ex`, `non attivo`, `Model Office` o `Formazione`.
- Le fonti pagamenti PST confermano il pagamento tramite area riservata, Punto
  di Accesso o area pubblica pagoPA per utenti non registrati; la prova tecnica
  del pagamento nei servizi telematici è la `RT.xml`.
- I codici riscossione governati sono `CONTRIB`, `DIRCANC`, `DIRCOPIA`,
  `CONTRBENI`, `UNPIG` e `UNNOT`; gli stati registrati sono `DISPONIBILE`,
  `USATO`, `OK_PSP` e `RIMBORSATO`.

Decisioni operative:

- Il codice civile e il codice penale dello stesso ufficio non sono
  intercambiabili.
- Corte d'Appello Reggio Calabria civile: `0800630064`.
- Corte d'Appello Reggio Calabria penale/PDP: `08006300604`.
- Tribunale Palmi civile: `0800570094`.
- Tribunale Palmi penale/PDP: `08005702201`.
- Procura Palmi penale/PDP: `08005702100`.
- Giudice di Pace Palmi: `0800570152`.
- UNEP Palmi: `08005702237`.
- UNEP Corte d'Appello Reggio Calabria: `08006300630`.
- Corte Suprema di Cassazione: `80417740588`, con `JPW_CASSCI` e `JPW_CASSPE`
  separati.

Limite accertato:

- La Corte di Assise di Appello di Reggio Calabria risulta nella fonte
  territoriale Giustizia Map con recapiti, ma il catalogo PST pubblico e il
  catalogo servizi WSDL non espongono un codice depositabile dedicato. IUSENTRA
  conserva l'ufficio territoriale e avvisa l'utente; non sostituisce quel dato
  con il codice della Corte d'Appello civile.

## PAT / SIGA - Giustizia Amministrativa

Fonti ufficiali controllate:

- `https://www.giustizia-amministrativa.it/web/guest/portale-avvocato`
- `https://www.giustizia-amministrativa.it/processo-amministrativo-telematico`
- `https://www.giustizia-amministrativa.it/web/guest/faq-nuovo-portale`
- `https://pe.prod.cloud.giustizia-amministrativa.it`
- `https://pe.prod.cloud.giustizia-amministrativa.it/#/fascicoli`

Esito verificato:

- La fonte pubblica conferma il Processo Amministrativo Telematico, il Portale
  dell'Avvocato, il deposito digitale di ricorsi, atti e documenti, la firma
  digitale PAdES dei moduli e l'uso di PEC presente nel RegIndE.
- Il pulsante pubblico `Vai al portale` porta al portale operativo
  `https://pe.prod.cloud.giustizia-amministrativa.it`.
- Il portale autenticato indicato dall'utente mostra fascicoli con NRG, sede
  TAR, sezione, oggetto, data deposito, stato fascicolo, parti, atti,
  provvedimenti, notifiche, avvisi e depositi con UID.

Decisione operativa:

- I dati PAT/SIGA restano nel profilo `pat_siga`.
- NRG TAR, UID deposito e sede amministrativa non sono codici ufficio PST e non
  devono essere normalizzati in SICID, SIECIC, SIGP o PDP.
- IUSENTRA blocca l'atto principale PAT firmato in CAdES `.p7m` e richiede
  PAdES, con test di regressione dedicato.
- Le fonti PAT/F24 Elide indicano che il pagamento del contributo unificato va
  tracciato con quietanza, data, estremi, importo, codice tributo, numero riga,
  elementi identificativi e copia informatica della quietanza.

## PTT / SIGIT - Giustizia Tributaria

Fonti ufficiali controllate:

- `https://assistenza.dgt.mef.gov.it/GiustiziaTributaria/s/most-viewed`
- `https://assistenza.dgt.mef.gov.it/GiustiziaTributaria/s/articolo-detail?urlName=DF-GiustiziaTributaria-3016`
- `https://assistenza.dgt.mef.gov.it/GiustiziaTributaria/s/articolo-detail?urlName=DF-GiustiziaTributaria-3059`
- `https://assistenza.dgt.mef.gov.it/GiustiziaTributaria/s/area-video`
- `https://sigit.giustiziatributaria.gov.it/Sigit/index.do`
- `https://www.mef.gov.it/ufficio-stampa/comunicati/2019/documenti/prot._5764-19_Circolare_PTT_4-7-2019.pdf`

Esito verificato:

- Le pagine MEF sono dinamiche: il rendering browser mostra la sezione ufficiale
  di assistenza ai servizi online del Dipartimento della Giustizia Tributaria.
- La pagina `Le più lette` espone `Processo Tributario Telematico`,
  `Utilizzare deposito telematico ricorsi e appelli`, `Predisposizione di atti e
  documenti`, `Deposito di atti e documenti`, `Consultare dati del fascicolo
  tramite PTT`, `Pagamenti con pagoPA` e `Telecontenzioso`.
- L'articolo `DF-GiustiziaTributaria-3016` mostra il workflow del processo
  telematico e le sezioni `Registrarsi ed accedere al Processo Tributario
  Telematico` ed `Effettuare il pagamento CUT`.
- L'articolo `DF-GiustiziaTributaria-3059` mostra `Utilizzare deposito
  telematico ricorsi e appelli`, deposito ricorsi/appelli e atti successivi.
- L'area video espone il contenuto `Formati documenti e tipologia di firma
  digitale`.
- SIGIT `Telecontenzioso` consente la consultazione delle informazioni nelle
  banche dati delle Corti di Giustizia Tributaria per ricorsi/appelli di
  competenza degli utenti abilitati al PTT o al solo Telecontenzioso.
- La circolare MEF sui pagamenti CUT pagoPA indica pagamento dal link ricevuto
  nella PEC con numero `RGR/RGA` o successivamente dall'Area personale PTT, con
  abbinamento automatico al ricorso o all'appello.

Decisione operativa:

- I dati PTT/SIGIT restano nel profilo `ptt_sigit`.
- Codici e flussi tributari non vanno risolti con catalogo PST civile/penale.
- Il software non crea un allegato sostitutivo quando SIGIT associa il CUT al
  numero `RGR/RGA`; registra invece la riconciliazione e segnala ciò che manca.

## Malfunzionamenti e indisponibilità

Fonte ufficiale controllata:

- `https://pst.giustizia.it/PST/it/malfunzionamenti.page`

Regola applicativa:

- Se una prova live su PST/PDP/PolisWeb fallisce, l'audit deve verificare anche
  la pagina malfunzionamenti prima di classificare il problema come regressione
  IUSENTRA, errore PIN o assenza fascicolo.
- Gli incidenti pubblicati dal PST sono fonte di contesto; non sostituiscono il
  log locale sanificato del Local Signer.
