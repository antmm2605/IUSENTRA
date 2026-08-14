# Audit gerarchico menu e funzioni

Generato: 2026-08-14T02:43:15+02:00 (Europe/Rome).

## Perimetro estratto

- Superfici sorgente con menu o barre: 13
- Istanze di controllo dichiarate: 3017
- Percorsi raggiungibili: 1056
- Percorsi menu: 186
- Percorsi azione: 870
- Azioni distinte per chiave: 676
- Finestre con controlli cliccabili: 113
- Controlli cliccabili fuori dai menu: 558
- Voci funzionali complessive censite: 1428

## Rubrica pratiche

- Campi tabella PRATICHE: 37
- Filtri combinabili rilevati: 25
- Pratiche attive e archiviate: si
- Gruppi di fascicoli: si
- Ordinamento multiplo: si
- Raggruppamento per colonna: si
- Altezza righe fissa e variabile: si

### Campi

`ANNO_RUOLO_GEN`, `ARCHIVIO`, `AUT_GIUDIZ`, `AVV_CONTROP`, `AttorePrincipale`, `CANCELL`, `CTU`, `ConvenutoPrincipale`, `DATA_APE`, `DATA_ARC`, `ISTRUTTORE`, `LinkNotaSpese`, `NOTE`, `NUMEROPRATICA`, `NumeroAttori`, `NumeroConvenuti`, `OGGETTO_PRATICA`, `OwnerID`, `OwnerName`, `PRATICA`, `RIF`, `RUOLO_GEN`, `RUOLO_SEZ`, `SEZIONE`, `SUB_PROCEDIMENTO`, `TIPO`, `TXT_PERSONALIZZABILE1`, `TXT_PERSONALIZZABILE2`, `TitolareID`, `TitolareName`, `VALORE`, `Stato_Pratica`, `QualificaGiudizialeTitolarePratica`, `LinkCartellaEsterna`, `NomeGruppo`, `NumeroCCI`, `CTP`

### Filtri

- Digitare il registro da filtrare: `TIPO`
- Digitare il valore di pratica da filtrare: `VALORE`
- Digitare il nome del titolare pratica da filtrare: `TitolareName`
- Digitare il nome del responsabile pratica da filtrare: `OwnerName`
- Digitare l'oggetto pratica da filtrare: `OGGETTO_PRATICA`
- Digitare la denominazione pratica da filtrare: `PRATICA`
- Digitare il riferimento cartaceo da filtrare: `RIF`
- Digitare l'anno di Ruolo pratica da filtrare: `ANNO_RUOLO_GEN`
- Digitare l'anno di apertura pratica da filtrare: `DATA_APE`
- Digitare l'anno di archiviazione pratica da filtrare: `DATA_ARC`
- Digitare l'Autorità Giudiziaria da filtrare: `AUT_GIUDIZ`
- Digitare il numero di ruolo generale da filtrare: `RUOLO_GEN`
- Digitare il numero di sezione da filtrare: `SEZIONE`
- Digitare il numero di ruolo di sezione da filtrare: `RUOLO_SEZ`
- Digitare il nome del Giudice da filtrare: `ISTRUTTORE`
- Digitare il nome dell'Avvocato da filtrare: `AVV_CONTROP`
- Digitare l'annotazione da filtrare: `NOTE`
- Digitare il nome del Cancellliere da filtrare: `CANCELL`
- Digitare il nome del Consulente da filtrare: `CTU`
- Digitare il nome del consulente tecnico di parte da filtrare: `CTP`
- Digitare il valore da filtrare: `Stato_Pratica`
- Digitare il valore da filtrare: `AttorePrincipale`
- Digitare il valore da filtrare: `ConvenutoPrincipale`
- Digitare il valore da filtrare: `TXT_PERSONALIZZABILE1`
- Digitare il valore da filtrare: `TXT_PERSONALIZZABILE2`

## Albero menu

### BrowserForm

Sorgente: `QuickOrganizer/BrowserForm.cs`

#### non_associato

- `forwardButton`: BrowserForm > toolStrip1 > Avanti
- `goButton`: BrowserForm > toolStrip1 > Go
- `HomeButton`: BrowserForm > toolStrip1 > Home
- `backButton`: BrowserForm > toolStrip1 > Indietro
- `ReloadButton`: BrowserForm > toolStrip1 > Reload
### FormMain

Sorgente: `QuickOrganizer/FormMain.cs`

#### menu_contestuale

- `AttoCivileDebito`: FormMain > A debito > AttoCivileDebito
- `AttoPenaleDebito`: FormMain > A debito > AttoPenaleDebito
- `RichiestaPignoramentoImmobiliareADebito`: FormMain > A debito > RichiestaPignoramentoImmobiliareADebito
- `RichiestaPignoramentoMobiliareADebito`: FormMain > A debito > RichiestaPignoramentoMobiliareADebito
- `RichiestaPignoramentoPressoTerziADebito`: FormMain > A debito > RichiestaPignoramentoPressoTerziADebito
- `AttoCivileAPagamento`: FormMain > A pagamento > AttoCivileAPagamento
- `AttoPenaleAPagamento`: FormMain > A pagamento > AttoPenaleAPagamento
- `PagamentoRichiestaNotifica`: FormMain > A pagamento > PagamentoRichiestaNotifica
- `PagamentoRichiestaPignoramento`: FormMain > A pagamento > PagamentoRichiestaPignoramento
- `RichiestaPignoramentoImmobiliare`: FormMain > A pagamento > RichiestaPignoramentoImmobiliare
- `RichiestaPignoramentoMobiliare`: FormMain > A pagamento > RichiestaPignoramentoMobiliare
- `RichiestaPignoramentoPressoTerzi`: FormMain > A pagamento > RichiestaPignoramentoPressoTerzi
- `RichiestaRestituzioneSomme`: FormMain > A pagamento > RichiestaRestituzioneSomme
- `RichiestaRicercaBeni`: FormMain > A pagamento > RichiestaRicercaBeni
- `Agenda_PolisWeb`: FormMain > Accesso al Polisweb... > Agenda PolisWeb
- `Agenda_PolisWeb`: FormMain > Accesso al PolisWeb... > Agenda PolisWeb
- `ArchivioGiurisprudenzaNazionale`: FormMain > Accesso al Polisweb... > ArchivioGiurisprudenzaNazionale
- `Consultazione_Fascicoli_Cassazione_Civile`: FormMain > Accesso al Polisweb... > Consultazione Fascicoli Cassazione Civile
- `Consultazione_Fascicoli_Cassazione_Civile`: FormMain > Accesso al PolisWeb... > Consultazione Fascicoli Cassazione Civile
- `Consultazione_Fascicoli_Cassazione_Penale`: FormMain > Accesso al Polisweb... > Consultazione Fascicoli Cassazione Penale
- `Consultazione_Fascicoli_Cassazione_Penale`: FormMain > Accesso al PolisWeb... > Consultazione Fascicoli Cassazione Penale
- `Fascicolo_Telematico`: FormMain > Accesso al Polisweb... > Fascicolo Telematico
- `Fascicolo_Ufficio`: FormMain > Accesso al Polisweb... > Fascicolo Ufficio
- `Fascicolo_Ufficio`: FormMain > Accesso al PolisWeb... > Fascicolo Ufficio
- `Fascicolo_Ufficio_Documenti`: FormMain > Accesso al Polisweb... > Fascicolo Ufficio Documenti
- `Fascicolo_Ufficio_Documenti_Pratica`: FormMain > Accesso al PolisWeb... > Fascicolo Ufficio Documenti Pratica
- `Fascicolo_Ufficio_Eventi`: FormMain > Accesso al Polisweb... > Fascicolo Ufficio Eventi
- `Fascicolo_Ufficio_Eventi`: FormMain > Accesso al PolisWeb... > Fascicolo Ufficio Eventi
- `Fascicolo_Ufficio_Notifiche`: FormMain > Accesso al Polisweb... > Fascicolo Ufficio Notifiche
- `Fascicolo_Ufficio_Notifiche`: FormMain > Accesso al PolisWeb... > Fascicolo Ufficio Notifiche
- `NotificheNonPerfezionate`: FormMain > Accesso al Polisweb... > NotificheNonPerfezionate
- `NotificheNonPerfezionate`: FormMain > Accesso al PolisWeb... > NotificheNonPerfezionate
- `Pagamenti Telematici`: FormMain > Accesso al Polisweb... > Pagamenti Telematici
- `popupPagamentiTelematici`: FormMain > Accesso al PolisWeb... > popupPagamentiTelematici
- `RegistroIndirizziElettronici`: FormMain > Accesso al Polisweb... > RegistroIndirizziElettronici
- `RegistroIndirizziElettronici`: FormMain > Accesso al PolisWeb... > RegistroIndirizziElettronici
- `RegistroPubblicheAmministrazioni`: FormMain > Accesso al Polisweb... > RegistroPubblicheAmministrazioni
- `RegistroPubblicheAmministrazioni`: FormMain > Accesso al PolisWeb... > RegistroPubblicheAmministrazioni
- `Ricerca_ RG_per_costituzione`: FormMain > Accesso al PolisWeb... > Ricerca  RG per costituzione
- `Ricerca_RG`: FormMain > Accesso al Polisweb... > Ricerca RG
- `Scarica_Documenti_PolisWeb`: FormMain > Accesso al Polisweb... > Scarica Documenti PolisWeb
- `Scarica_Documenti_PolisWeb`: FormMain > Accesso al PolisWeb... > Scarica Documenti PolisWeb
- `Scarica_Udienze_Scadenze_PolisWeb`: FormMain > Accesso al Polisweb... > Scarica Udienze Scadenze PolisWeb
- `Scarica_Udienze_Scadenze_PolisWeb`: FormMain > Accesso al PolisWeb... > Scarica Udienze Scadenze PolisWeb
- `Acquisisci_Verbale_Udienza`: FormMain > Aggiungi > Acquisisci Verbale Udienza
- `Cerca_Eventi_Polisweb`: FormMain > Aggiungi > Cerca Eventi Polisweb
- `Fascicolo_Ufficio_Eventi`: FormMain > Aggiungi > Fascicolo Ufficio Eventi
- `MenuItem_Aggiungi_Adempimento`: FormMain > Aggiungi > MenuItem Aggiungi Adempimento
- `MenuItem_Aggiungi_Appuntamento`: FormMain > Aggiungi > MenuItem Aggiungi Appuntamento
- `MenuItem_Aggiungi_Attività`: FormMain > Aggiungi > MenuItem Aggiungi Attività
- `MenuItem_Aggiungi_Memorandum`: FormMain > Aggiungi > MenuItem Aggiungi Memorandum
- `MenuItem_Aggiungi_Scadenza`: FormMain > Aggiungi > MenuItem Aggiungi Scadenza
- `MenuItem_Aggiungi_Udienza`: FormMain > Aggiungi > MenuItem Aggiungi Udienza
- `Carica_XML_Fattura`: FormMain > Aggiungi Contabilità > Carica XML Fattura
- `MenuItem_Aggiungi_NotaCredito`: FormMain > Aggiungi Contabilità > MenuItem Aggiungi NotaCredito
- `MenuItem_Aggiungi_NotaCredito_Elettronica`: FormMain > Aggiungi Contabilità > MenuItem Aggiungi NotaCredito Elettronica
- `MenuItem_Aggiungi_NotaSpese`: FormMain > Aggiungi Contabilità > MenuItem Aggiungi NotaSpese
- `MenuItem_Aggiungi_PreavvisoParcella`: FormMain > Aggiungi Contabilità > MenuItem Aggiungi PreavvisoParcella
- `MenuItem_Aggiungi_Preventivo`: FormMain > Aggiungi Contabilità > MenuItem Aggiungi Preventivo
- `Nuova_Fattura_Acquisto`: FormMain > Aggiungi Contabilità > Nuova Fattura Acquisto
- `Nuova_Fattura_Cartacea`: FormMain > Aggiungi Contabilità > Nuova Fattura Cartacea
- `Nuova_Fattura_Elettronica`: FormMain > Aggiungi Contabilità > Nuova Fattura Elettronica
- `MenuItem_Aggiungi_EmailAccount`: FormMain > Aggiungi EmailAccounts > MenuItem Aggiungi EmailAccount
- `MenuItem_Aggiungi_EntrataUscita`: FormMain > Aggiungi Movimentazioni > MenuItem Aggiungi EntrataUscita
- `MenuItem_Aggiungi_NotaCredito_Elettronica_Pratica`: FormMain > Aggiungi Parcelle Pratica > MenuItem Aggiungi NotaCredito Elettronica Pratica
- `MenuItem_Aggiungi_NotaSpese_Pratica`: FormMain > Aggiungi Parcelle Pratica > MenuItem Aggiungi NotaSpese Pratica
- `MenuItem_Aggiungi_Preavviso_Pratica`: FormMain > Aggiungi Parcelle Pratica > MenuItem Aggiungi Preavviso Pratica
- `MenuItem_Aggiungi_Preventivo_Pratica`: FormMain > Aggiungi Parcelle Pratica > MenuItem Aggiungi Preventivo Pratica
- `Nuova_Fattura_Acquisto_Pratica`: FormMain > Aggiungi Parcelle Pratica > Nuova Fattura Acquisto Pratica
- `Nuova_Fattura_Elettronica_Pratica`: FormMain > Aggiungi Parcelle Pratica > Nuova Fattura Elettronica Pratica
- `MultiLine`: FormMain > Altezza della riga (oggetto)... > MultiLine
- `SingleLine`: FormMain > Altezza della riga (oggetto)... > SingleLine
- `Cerca_Eventi_Polisweb`: FormMain > Altro... > Cerca Eventi Polisweb
- `Depositi_Telematici_Amministrativi`: FormMain > Altro... > Depositi Telematici Amministrativi
- `Depositi_Telematici_Civile`: FormMain > Altro... > Depositi Telematici Civile
- `Depositi_Telematici_Penali`: FormMain > Altro... > Depositi Telematici Penali
- `Depositi_Telematici_Tributari`: FormMain > Altro... > Depositi Telematici Tributari
- `Importa_Pratiche_PolisWeb`: FormMain > Altro... > Importa Pratiche PolisWeb
- `NotificaMezzoPEC`: FormMain > Altro... > NotificaMezzoPEC
- `NotificheEdAltreRichiesteUNEP`: FormMain > Altro... > NotificheEdAltreRichiesteUNEP
- `Portale_Servizi_Telematici`: FormMain > Altro... > Portale Servizi Telematici
- `Rubrica_Telefonica`: FormMain > Altro... > Rubrica Telefonica
- `Sincronizza_Fascicolo_Ufficio`: FormMain > Altro... > Sincronizza Fascicolo Ufficio
- `WhatsAppWeb`: FormMain > Altro... > WhatsAppWeb
- `AnteprimaDiStampa_TimeLineMese`: FormMain > Anteprima di Stampa > AnteprimaDiStampa TimeLineMese
- `AnteprimaDiStampa_TimeLineOdierno`: FormMain > Anteprima di Stampa > AnteprimaDiStampa TimeLineOdierno
- `AnteprimaDiStampa_TimeLineSettimana`: FormMain > Anteprima di Stampa > AnteprimaDiStampa TimeLineSettimana
- `ApriConOpenOffice`: FormMain > Apri con... > ApriConOpenOffice
- `ApriConQuickWord`: FormMain > Apri con... > ApriConQuickWord
- `ApriConWinWord`: FormMain > Apri con... > ApriConWinWord
- `Colore_Adempimenti`: FormMain > Colore di default degli impegni > Colore Adempimenti
- `Colore_Allarmi`: FormMain > Colore di default degli impegni > Colore Allarmi
- `Colore_Appuntamenti`: FormMain > Colore di default degli impegni > Colore Appuntamenti
- `Colore_Attività_SenzaData`: FormMain > Colore di default degli impegni > Colore Attività SenzaData
- `Colore_Memorandum`: FormMain > Colore di default degli impegni > Colore Memorandum
- `Colore_Scadenze`: FormMain > Colore di default degli impegni > Colore Scadenze
- `Colore_Udienze`: FormMain > Colore di default degli impegni > Colore Udienze
- `Cerca_Eventi_Polisweb`: FormMain > ContextMenu_Agenda > Cerca Eventi Polisweb
- `Esporta`: FormMain > ContextMenu_Agenda > Esporta
- `Fascicolo_Ufficio`: FormMain > ContextMenu_Agenda > Fascicolo Ufficio
- `Invia`: FormMain > ContextMenu_Agenda > Invia
- `NotificaMezzoPEC`: FormMain > ContextMenu_Agenda > NotificaMezzoPEC
- `Stampa`: FormMain > ContextMenu_Agenda > Stampa
- `Elimina_Filtro_Contabilità`: FormMain > ContextMenu_Contabilità > Elimina Filtro Contabilità
- `Filtra_Contabilità`: FormMain > ContextMenu_Contabilità > Filtra Contabilità
- `PrintGrid`: FormMain > ContextMenu_Contabilità > PrintGrid
- `Trova_Contabilità_Sx`: FormMain > ContextMenu_Contabilità > Trova Contabilità Sx
- `Vedi_Pratica_Contabilità`: FormMain > ContextMenu_Contabilità > Vedi Pratica Contabilità
- `Connetti_And_Ricevi`: FormMain > ContextMenu_Email > Connetti And Ricevi
- `Email_Settings`: FormMain > ContextMenu_Email > Email Settings
- `Esporta`: FormMain > ContextMenu_Email > Esporta
- `Invia`: FormMain > ContextMenu_Email > Invia
- `Stampa`: FormMain > ContextMenu_Email > Stampa
- `Esporta`: FormMain > ContextMenu_GridEmail > Esporta
- `Invia`: FormMain > ContextMenu_GridEmail > Invia
- `RichiamaEmailDalCestino`: FormMain > ContextMenu_GridEmail > RichiamaEmailDalCestino
- `Segna_ComeNonLetta`: FormMain > ContextMenu_GridEmail > Segna ComeNonLetta
- `Stampa`: FormMain > ContextMenu_GridEmail > Stampa
- `Cerca_Eventi_Polisweb`: FormMain > ContextMenu_Rubrica > Cerca Eventi Polisweb
- `Connetti_And_Ricevi_Rubrica`: FormMain > ContextMenu_Rubrica > Connetti And Ricevi Rubrica
- `Elimina_Filtro_Rubrica`: FormMain > ContextMenu_Rubrica > Elimina Filtro Rubrica
- `Fascicolo_Ufficio`: FormMain > ContextMenu_Rubrica > Fascicolo Ufficio
- `Filtra_Rubrica`: FormMain > ContextMenu_Rubrica > Filtra Rubrica
- `NotificaMezzoPEC`: FormMain > ContextMenu_Rubrica > NotificaMezzoPEC
- `PrintGrid`: FormMain > ContextMenu_Rubrica > PrintGrid
- `Sincronizza_Fascicolo_Ufficio`: FormMain > ContextMenu_Rubrica > Sincronizza Fascicolo Ufficio
- `Trova_Rubrica_Sx`: FormMain > ContextMenu_Rubrica > Trova Rubrica Sx
- `ControllaXMLPrimaInvio`: FormMain > Controlla Fattura > ControllaXMLPrimaInvio
- `VisualizzaXMLPrimaInvio`: FormMain > Controlla Fattura > VisualizzaXMLPrimaInvio
- `MenuItem_Aggiungi_Adempimento`: FormMain > Cover Aggiungi Agenda > MenuItem Aggiungi Adempimento
- `MenuItem_Aggiungi_Appuntamento`: FormMain > Cover Aggiungi Agenda > MenuItem Aggiungi Appuntamento
- `MenuItem_Aggiungi_Attività`: FormMain > Cover Aggiungi Agenda > MenuItem Aggiungi Attività
- `MenuItem_Aggiungi_Memorandum`: FormMain > Cover Aggiungi Agenda > MenuItem Aggiungi Memorandum
- `MenuItem_Aggiungi_Scadenza`: FormMain > Cover Aggiungi Agenda > MenuItem Aggiungi Scadenza
- `MenuItem_Aggiungi_Udienza`: FormMain > Cover Aggiungi Agenda > MenuItem Aggiungi Udienza
#### UltraToolbarsManagerRight

- `Cover_Aggiungi_Agenda`: FormMain > Cover_Agenda > Cover Aggiungi Agenda
- `Cover_Aggiungi_Contabilità`: FormMain > Cover_Contabilità > Cover Aggiungi Contabilità
- `Cover_Aggiungi_Email`: FormMain > Cover_EmailRight > Cover Aggiungi Email
- `Cover_Aggiungi_Movimentazioni`: FormMain > Cover_Movimentazioni > Cover Aggiungi Movimentazioni
- `Cover_Aggiungi_Rubrica`: FormMain > Cover_Rubrica > Cover Aggiungi Rubrica
- `Cover_Aggiungi_Schedario`: FormMain > Cover_Schedario > Cover Aggiungi Schedario
- `Cover_Aggiungi_Agenda`: FormMain > Cover_TimeLineAgenda > Cover Aggiungi Agenda
- `Elimina_Agenda`: FormMain > Cover_TimeLineAgenda > Elimina Agenda
- `Modifica_Agenda`: FormMain > Cover_TimeLineAgenda > Modifica Agenda
- `OpzioniTimeLineAgenda`: FormMain > Cover_TimeLineAgenda > OpzioniTimeLineAgenda
- `Cover_Aggiungi_Videoscrittura`: FormMain > Cover_Videoscrittura > Cover Aggiungi Videoscrittura
- `Opzioni_VolumeAffari`: FormMain > Cover_VolumeAffari > Opzioni VolumeAffari
- `Aggiungi_Rubrica`: FormMain > DatiGenerali_Rubrica > Aggiungi Rubrica
- `Avviso`: FormMain > DatiGenerali_Rubrica > Avviso
- `Elimina_Rubrica`: FormMain > DatiGenerali_Rubrica > Elimina Rubrica
- `LabelDescrizioneRight`: FormMain > DatiGenerali_Rubrica > LabelDescrizioneRight
- `Modifica_Rubrica`: FormMain > DatiGenerali_Rubrica > Modifica Rubrica
- `Opzioni_Rubrica`: FormMain > DatiGenerali_Rubrica > Opzioni Rubrica
- `Aggiungi_Schedario`: FormMain > DatiGenerali_Schedario > Aggiungi Schedario
- `Avviso`: FormMain > DatiGenerali_Schedario > Avviso
- `Elimina_Schedario`: FormMain > DatiGenerali_Schedario > Elimina Schedario
- `LabelDescrizioneRight`: FormMain > DatiGenerali_Schedario > LabelDescrizioneRight
- `Modifica_Schedario`: FormMain > DatiGenerali_Schedario > Modifica Schedario
- `Opzioni_Schedario`: FormMain > DatiGenerali_Schedario > Opzioni Schedario
- `Aggiungi_Videoscrittura`: FormMain > DatiGenerali_Videoscrittura > Aggiungi Videoscrittura
- `Avviso`: FormMain > DatiGenerali_Videoscrittura > Avviso
- `Elimina_Videoscrittura`: FormMain > DatiGenerali_Videoscrittura > Elimina Videoscrittura
- `LabelDescrizioneRight`: FormMain > DatiGenerali_Videoscrittura > LabelDescrizioneRight
- `Modifica_Videoscrittura`: FormMain > DatiGenerali_Videoscrittura > Modifica Videoscrittura
- `Opzioni_Videoscrittura`: FormMain > DatiGenerali_Videoscrittura > Opzioni Videoscrittura
#### menu_contestuale

- `EsportaFilePer_DepositoProcessoAmministrativo`: FormMain > Depositi in materia Amministrativa > EsportaFilePer DepositoProcessoAmministrativo
- `Portale_Amministrativo_Telematico`: FormMain > Depositi in materia Amministrativa > Portale Amministrativo Telematico
- `Atto_Enc_Esterno`: FormMain > Depositi in materia Civile > Atto Enc Esterno
- `Deposito_Telematico_SingolaPratica`: FormMain > Depositi in materia Civile > Deposito Telematico SingolaPratica
- `EsportaFilePer_DepositoConSoftwareEsterno`: FormMain > Depositi in materia Civile > EsportaFilePer DepositoConSoftwareEsterno
- `EsportaFilePer_DepositoAttiPenali`: FormMain > Depositi in materia Penale > EsportaFilePer DepositoAttiPenali
- `Portale_DepositoAttiPenali`: FormMain > Depositi in materia Penale > Portale DepositoAttiPenali
- `EsportaTilePer_ProcessoTributario`: FormMain > Depositi in materia Tributaria > EsportaTilePer ProcessoTributario
- `Portale_Tributario_Telematico`: FormMain > Depositi in materia Tributaria > Portale Tributario Telematico
- `CopiaDocumentoInAltraPratica`: FormMain > Esporta > CopiaDocumentoInAltraPratica
- `Esporta_Formato_DOC`: FormMain > Esporta > Esporta Formato DOC
- `Esporta_Formato_PDF`: FormMain > Esporta > Esporta Formato PDF
- `Esporta_Formato_PDF_Firmato`: FormMain > Esporta > Esporta Formato PDF Firmato
- `Esporta_Formato_RTF`: FormMain > Esporta > Esporta Formato RTF
- `Esporta_Semplice_Videoscrittura`: FormMain > Esporta > Esporta Semplice Videoscrittura
- `MenuItem_Aggiungi_Fattura_Acconto_Pratica`: FormMain > Fattura Cartacea > MenuItem Aggiungi Fattura Acconto Pratica
- `MenuItem_Aggiungi_Fattura_Integrativa_Pratica`: FormMain > Fattura Cartacea > MenuItem Aggiungi Fattura Integrativa Pratica
- `MenuItem_Aggiungi_Fattura_Pratica`: FormMain > Fattura Cartacea > MenuItem Aggiungi Fattura Pratica
- `MenuItem_Aggiungi_Fattura_Elettronica`: FormMain > Fattura Elettronca > MenuItem Aggiungi Fattura Elettronica
- `MenuItem_Aggiungi_Fattura_Elettronica_Acconto`: FormMain > Fattura Elettronca > MenuItem Aggiungi Fattura Elettronica Acconto
- `MenuItem_Aggiungi_Fattura_Elettronica_Integrativa`: FormMain > Fattura Elettronca > MenuItem Aggiungi Fattura Elettronica Integrativa
- `Carica_XML_Fattura_Pratica`: FormMain > Fattura Elettronica > Carica XML Fattura Pratica
- `MenuItem_Aggiungi_Fattura_Elettronica_Acconto_Pratica`: FormMain > Fattura Elettronica > MenuItem Aggiungi Fattura Elettronica Acconto Pratica
- `MenuItem_Aggiungi_Fattura_Elettronica_Integrativa_Pratica`: FormMain > Fattura Elettronica > MenuItem Aggiungi Fattura Elettronica Integrativa Pratica
- `MenuItem_Aggiungi_Fattura_Elettronica_Pratica`: FormMain > Fattura Elettronica > MenuItem Aggiungi Fattura Elettronica Pratica
- `Elimina_Filtro_Email_SingolaPratica`: FormMain > Filtra > Elimina Filtro Email SingolaPratica
- `Email_EscludiEvase`: FormMain > Filtra > Email EscludiEvase
- `Email_EscludiRicevuteAccettazione`: FormMain > Filtra > Email EscludiRicevuteAccettazione
- `Email_EscludiRicevuteConsegna`: FormMain > Filtra > Email EscludiRicevuteConsegna
- `Email_MostraSoloCopiaNonCrittografata`: FormMain > Filtra > Email MostraSoloCopiaNonCrittografata
- `Email_MostraSoloDepositiTelematici`: FormMain > Filtra > Email MostraSoloDepositiTelematici
- `Email_MostraSoloEmailConAdempimentiDaRicordare`: FormMain > Filtra > Email MostraSoloEmailConAdempimentiDaRicordare
- `Email_MostraSoloEmailDaLeggere`: FormMain > Filtra > Email MostraSoloEmailDaLeggere
- `Email_MostraSoloEmailEvase`: FormMain > Filtra > Email MostraSoloEmailEvase
- `Email_MostraSoloEmailInAttesaDiRisposta`: FormMain > Filtra > Email MostraSoloEmailInAttesaDiRisposta
- `Email_MostraSoloEsitoControlliAutomatici`: FormMain > Filtra > Email MostraSoloEsitoControlliAutomatici
- `FiltraEmailPer_AccountName`: FormMain > Filtra > FiltraEmailPer AccountName
- `FiltraEmailPer_Destinatario`: FormMain > Filtra > FiltraEmailPer Destinatario
- `FiltraEmailPer_Mittente`: FormMain > Filtra > FiltraEmailPer Mittente
- `FiltraEmailPer_Oggetto`: FormMain > Filtra > FiltraEmailPer Oggetto
- `FiltraEmailPer_Responsabile`: FormMain > Filtra > FiltraEmailPer Responsabile
- `FiltraLettereDocumentiPraticaPer_Doc`: FormMain > Filtra per... > FiltraLettereDocumentiPraticaPer Doc
- `FiltraLettereDocumentiPraticaPer_P7m`: FormMain > Filtra per... > FiltraLettereDocumentiPraticaPer P7m
- `FiltraLettereDocumentiPraticaPer_PdfSemplice`: FormMain > Filtra per... > FiltraLettereDocumentiPraticaPer PdfSemplice
- `FiltraLettereDocumentiPraticaPer_PdfSigned`: FormMain > Filtra per... > FiltraLettereDocumentiPraticaPer PdfSigned
- `FiltraLettereDocumentiPraticaPer_Rtf`: FormMain > Filtra per... > FiltraLettereDocumentiPraticaPer Rtf
- `FirmaDigitaleCades`: FormMain > Firma digitale... > FirmaDigitaleCades
- `FirmaDigitalePades`: FormMain > Firma digitale... > FirmaDigitalePades
- `AttoEsenteLavoro`: FormMain > Iin materia di Lavoro > AttoEsenteLavoro
- `RichiestaPignoramentoImmobiliareMateriaLavoro`: FormMain > Iin materia di Lavoro > RichiestaPignoramentoImmobiliareMateriaLavoro
- `RichiestaPignoramentoMobiliareMateriaLavoro`: FormMain > Iin materia di Lavoro > RichiestaPignoramentoMobiliareMateriaLavoro
- `RichiestaPignoramentoPressoTerziMateriaLavoro`: FormMain > Iin materia di Lavoro > RichiestaPignoramentoPressoTerziMateriaLavoro
- `AttoEsenteLavoro`: FormMain > In materia di Lavoro > AttoEsenteLavoro
- `RichiestaPignoramentoImmobiliareMateriaLavoro`: FormMain > In materia di Lavoro > RichiestaPignoramentoImmobiliareMateriaLavoro
- `RichiestaPignoramentoMobiliareMateriaLavoro`: FormMain > In materia di Lavoro > RichiestaPignoramentoMobiliareMateriaLavoro
- `RichiestaPignoramentoPressoTerziMateriaLavoro`: FormMain > In materia di Lavoro > RichiestaPignoramentoPressoTerziMateriaLavoro
- `Invia_Come_Allegato_Semplice`: FormMain > Invia a mezzo email > Invia Come Allegato Semplice
- `Invia_Come_Allegato_Semplice`: FormMain > Invia a mezzo Email > Invia Come Allegato Semplice
- `Invia_Formato_PDF`: FormMain > Invia a mezzo email > Invia Formato PDF
- `Invia_Formato_PDF`: FormMain > Invia a mezzo Email > Invia Formato PDF
- `Invia_Formato_PDF_Firmato`: FormMain > Invia a mezzo email > Invia Formato PDF Firmato
- `Invia_Formato_PDF_Firmato`: FormMain > Invia a mezzo Email > Invia Formato PDF Firmato
- `Invia_Formato_RTF`: FormMain > Invia a mezzo email > Invia Formato RTF
- `Invia_Formato_RTF`: FormMain > Invia a mezzo Email > Invia Formato RTF
- `InviaFatturaConPEC`: FormMain > Invia fattura > InviaFatturaConPEC
- `InviaFatturaConPEC`: FormMain > Invia Fattura > InviaFatturaConPEC
- `InviaFatturaConSoftwareEsterno`: FormMain > Invia fattura > InviaFatturaConSoftwareEsterno
- `InviaFatturaConSoftwareEsterno`: FormMain > Invia Fattura > InviaFatturaConSoftwareEsterno
- `InviaFatturaUtilizzandoSitoWebAgenziaEntrate`: FormMain > Invia fattura > InviaFatturaUtilizzandoSitoWebAgenziaEntrate
- `InviaFatturaUtilizzandoSitoWebAgenziaEntrate`: FormMain > Invia Fattura > InviaFatturaUtilizzandoSitoWebAgenziaEntrate
- `Impegni_Inevasi`: FormMain > Mostra/Nascondi > Impegni Inevasi
- `Nascondi_Allarmi`: FormMain > Mostra/Nascondi > Nascondi Allarmi
- `Nascondi_AttivitàSenzaData`: FormMain > Mostra/Nascondi > Nascondi AttivitàSenzaData
- `AttoCivileAPagamento`: FormMain > Notifiche e altre richieste UNEP > AttoCivileAPagamento
- `AttoEsenteLavoro`: FormMain > Notifiche e altre richieste UNEP > AttoEsenteLavoro
- `AttoPenaleAPagamento`: FormMain > Notifiche e altre richieste UNEP > AttoPenaleAPagamento
- `PagamentoRichiestaNotifica`: FormMain > Notifiche e altre richieste UNEP > PagamentoRichiestaNotifica
- `PagamentoRichiestaPignoramento`: FormMain > Notifiche e altre richieste UNEP > PagamentoRichiestaPignoramento
- `RichiestaPignoramentoImmobiliare`: FormMain > Notifiche e altre richieste UNEP > RichiestaPignoramentoImmobiliare
- `RichiestaPignoramentoMobiliare`: FormMain > Notifiche e altre richieste UNEP > RichiestaPignoramentoMobiliare
- `RichiestaPignoramentoPressoTerzi`: FormMain > Notifiche e altre richieste UNEP > RichiestaPignoramentoPressoTerzi
- `RichiestaRestituzioneSomme`: FormMain > Notifiche e altre richieste UNEP > RichiestaRestituzioneSomme
- `RichiestaRicercaBeni`: FormMain > Notifiche e altre richieste UNEP > RichiestaRicercaBeni
- `NotificheAndRichiesteUnep_ADebito`: FormMain > Notifiche ed altre richieste UNEP > NotificheAndRichiesteUnep ADebito
- `NotificheAndRichiesteUnep_APagamneto`: FormMain > Notifiche ed altre richieste UNEP > NotificheAndRichiesteUnep APagamneto
- `NotificheAndRichiesteUnep_MateriaLavoro`: FormMain > Notifiche ed altre richieste UNEP > NotificheAndRichiesteUnep MateriaLavoro
- `Nuova_Fattura_Cartacea`: FormMain > Nuova_Fattura > Nuova Fattura Cartacea
- `Nuova_Fattura_Elettronica`: FormMain > Nuova_Fattura > Nuova Fattura Elettronica
- `Cerca_Eventi_Polisweb`: FormMain > Opzioni > Cerca Eventi Polisweb
- `Contabilità_ConvertiParcella`: FormMain > Opzioni > Contabilità ConvertiParcella
- `Esporta`: FormMain > Opzioni > Esporta
- `Importa_Pratiche_PolisWeb`: FormMain > Opzioni > Importa Pratiche PolisWeb
- `Invia`: FormMain > Opzioni > Invia
- `InviaFattura`: FormMain > Opzioni > InviaFattura
- `Portale_Servizi_Telematici`: FormMain > Opzioni > Portale Servizi Telematici
- `Rubrica_Telefonica`: FormMain > Opzioni > Rubrica Telefonica
- `SalvaInUnaPratica_In_FormatoPDF`: FormMain > Opzioni > SalvaInUnaPratica In FormatoPDF
- `Scorporo`: FormMain > Opzioni > Scorporo
- `Sincronizza_Fascicolo_Ufficio`: FormMain > Opzioni > Sincronizza Fascicolo Ufficio
- `Stampa`: FormMain > Opzioni > Stampa
- `Tariffario_Personale`: FormMain > Opzioni > Tariffario Personale
- `Trova_Contabilità_Dx`: FormMain > Opzioni > Trova Contabilità Dx
- `Vedi_Pratica_Contabilità`: FormMain > Opzioni > Vedi Pratica Contabilità
- `Computo_Termini`: FormMain > Opzioni TimeLineAgenda > Computo Termini
- `Google_Calendar_Agenda`: FormMain > Opzioni TimeLineAgenda > Google Calendar Agenda
- `Rinvia_Agenda`: FormMain > Opzioni TimeLineAgenda > Rinvia Agenda
- `StampaTimeLineAgenda`: FormMain > Opzioni TimeLineAgenda > StampaTimeLineAgenda
- `Vedi_Pratica_Agenda`: FormMain > Opzioni TimeLineAgenda > Vedi Pratica Agenda
- `PagamentiTelematici`: FormMain > Pagamenti Telematici > PagamentiTelematici
- `PagamentiTelematiciPagoPA`: FormMain > Pagamenti Telematici > PagamentiTelematiciPagoPA
- `Grassetto_Adempimenti`: FormMain > Planning > Grassetto Adempimenti
- `Grassetto_Appuntamenti`: FormMain > Planning > Grassetto Appuntamenti
- `Grassetto_Memorandum`: FormMain > Planning > Grassetto Memorandum
- `Grassetto_Scadenze`: FormMain > Planning > Grassetto Scadenze
- `Grassetto_Tutti`: FormMain > Planning > Grassetto Tutti
- `Grassetto_Udienze`: FormMain > Planning > Grassetto Udienze
- `Cerca_Eventi_Polisweb`: FormMain > Processo Telematico > Cerca Eventi Polisweb
- `Deposito_Telematico`: FormMain > Processo Telematico > Deposito Telematico
- `Fascicolo_Ufficio`: FormMain > Processo Telematico > Fascicolo Ufficio
- `Importa_Pratiche_PolisWeb`: FormMain > Processo Telematico > Importa Pratiche PolisWeb
- `NotificaMezzoPEC`: FormMain > Processo Telematico > NotificaMezzoPEC
- `15_Minuti`: FormMain > Promemoria (desktop alert) ... > 15 Minuti
- `30_Minuti`: FormMain > Promemoria (desktop alert) ... > 30 Minuti
- `5_Minuti`: FormMain > Promemoria (desktop alert) ... > 5 Minuti
- `Disattiva_Desktop_Alert`: FormMain > Promemoria (desktop alert) ... > Disattiva Desktop Alert
- `Ogni_3Ore`: FormMain > Promemoria (desktop alert) ... > Ogni 3Ore
- `Ogni_6Ore`: FormMain > Promemoria (desktop alert) ... > Ogni 6Ore
- `Ogni_Ora`: FormMain > Promemoria (desktop alert) ... > Ogni Ora
- `Recupera_Voci_Da_Precedente_Fattura`: FormMain > Recupera voci... > Recupera Voci Da Precedente Fattura
- `Recupera_Voci_Da_Precedente_Nota_Di_Credito`: FormMain > Recupera voci... > Recupera Voci Da Precedente Nota Di Credito
- `Recupera_Voci_Da_Precedente_Nota_Spese`: FormMain > Recupera voci... > Recupera Voci Da Precedente Nota Spese
- `Recupera_Voci_Da_Precedente_Preavviso_Di_Parcella`: FormMain > Recupera voci... > Recupera Voci Da Precedente Preavviso Di Parcella
- `Recupera_Voci_Da_Precedente_Preventivo`: FormMain > Recupera voci... > Recupera Voci Da Precedente Preventivo
- `Recupera_Voci_Dal_Tariffario`: FormMain > Recupera voci... > Recupera Voci Dal Tariffario
- `Recupera_Voci_Dalla_Pratica`: FormMain > Recupera voci... > Recupera Voci Dalla Pratica
- `Recupera_Voci_Dalla_PrimaNotaCassa`: FormMain > Recupera voci... > Recupera Voci Dalla PrimaNotaCassa
#### non_associato

- `Aggiungi_Rubrica`: FormMain > ribbonGroup1 > Aggiungi Rubrica
- `Elimina_Rubrica`: FormMain > ribbonGroup1 > Elimina Rubrica
- `Modifica_Rubrica`: FormMain > ribbonGroup1 > Modifica Rubrica
- `ribbonGroup2`: FormMain > ribbonGroup2
#### menu_contestuale

- `INIPEC_Imprese`: FormMain > Ricerca PEC... > INIPEC Imprese
- `INIPEC_Professionisti`: FormMain > Ricerca PEC... > INIPEC Professionisti
- `PEC_Pubbliche_Amministrazioni`: FormMain > Ricerca PEC... > PEC Pubbliche Amministrazioni
- `Registo_Imprese`: FormMain > Ricerca PEC... > Registo Imprese
- `RegistroIndirizziElettronici`: FormMain > Ricerca PEC... > RegistroIndirizziElettronici
- `Ricerca_Fascicoli_Costituzione`: FormMain > Ricerca RG per costituzione in giudizio > Ricerca Fascicoli Costituzione
- `Ricerca_Fascicoli_Costituzione_Cassazione`: FormMain > Ricerca RG per costituzione in giudizio > Ricerca Fascicoli Costituzione Cassazione
- `Print`: FormMain > Stampa > Print
- `Print Preview`: FormMain > Stampa > Print Preview
- `PrintGrid`: FormMain > Stampa > PrintGrid
- `Quick Print`: FormMain > Stampa > Quick Print
- `Anagrafica_Utente`: FormMain > Strumenti > Anagrafica Utente
- `Calcolo_Codice_Fiscale`: FormMain > Strumenti > Calcolo Codice Fiscale
- `Computo_Termini`: FormMain > Strumenti > Computo Termini
- `Configurazione_PEC`: FormMain > Strumenti > Configurazione PEC
- `Database`: FormMain > Strumenti > Database
- `DatabasePath`: FormMain > Strumenti > DatabasePath
- `Privacy`: FormMain > Strumenti > Privacy
- `Rubrica_Telefonica`: FormMain > Strumenti > Rubrica Telefonica
- `Scorporo`: FormMain > Strumenti > Scorporo
- `Sviluppo_Macro_Strumenti`: FormMain > Strumenti > Sviluppo Macro Strumenti
- `Tariffario_Personale_MenuApplication`: FormMain > Strumenti > Tariffario Personale MenuApplication
- `TestSmartCard`: FormMain > Strumenti > TestSmartCard
#### UltraToolbarsManagerAgenda

- `Giorno`: FormMain > UltraToolbarAgenda > Giorno
- `Mese`: FormMain > UltraToolbarAgenda > Mese
- `PopupMenuTool1`: FormMain > UltraToolbarAgenda > PopupMenuTool1
- `Settimana`: FormMain > UltraToolbarAgenda > Settimana
- `TimeLineAgenda`: FormMain > UltraToolbarAgenda > TimeLineAgenda
#### UltraToolbarsManagerAnagrafica

- `Altro`: FormMain > UltraToolbarAnagrafica > Altro
- `Clienti`: FormMain > UltraToolbarAnagrafica > Clienti
- `Controparti`: FormMain > UltraToolbarAnagrafica > Controparti
- `Rubrica_Telefonica_White`: FormMain > UltraToolbarAnagrafica > Rubrica Telefonica White
- `Tutti_Nomi`: FormMain > UltraToolbarAnagrafica > Tutti Nomi
#### UltraToolbarsManagerEmail

- `Cestino_Emails`: FormMain > UltraToolbarEmail > Cestino Emails
- `Connetti_And_Ricevi`: FormMain > UltraToolbarEmail > Connetti And Ricevi
- `Email_Inviate`: FormMain > UltraToolbarEmail > Email Inviate
- `Email_Ricevute`: FormMain > UltraToolbarEmail > Email Ricevute
- `Email_Settings`: FormMain > UltraToolbarEmail > Email Settings
- `Email_Tutte`: FormMain > UltraToolbarEmail > Email Tutte
#### UltraToolbarsManagerFatture

- `Altro`: FormMain > UltraToolbarFatture > Altro
- `Fatture_Elettroniche`: FormMain > UltraToolbarFatture > Fatture Elettroniche
- `Nota_Spese`: FormMain > UltraToolbarFatture > Nota Spese
- `Note_Credito_Elettroniche`: FormMain > UltraToolbarFatture > Note Credito Elettroniche
- `Preavvisi_Parcella`: FormMain > UltraToolbarFatture > Preavvisi Parcella
- `Preventivi_Parcella`: FormMain > UltraToolbarFatture > Preventivi Parcella
#### UltraToolbarsManagerGridSociCollaboratoriAgenda

- `Aggiungi_GridSociCollaboratori_Agenda`: FormMain > UltraToolbarGridSociCollaboratoriAgenda > Aggiungi GridSociCollaboratori Agenda
- `Elimina_GridSociCollaboratori_Agenda`: FormMain > UltraToolbarGridSociCollaboratoriAgenda > Elimina GridSociCollaboratori Agenda
- `Modifica_GridSociCollaboratori_Agenda`: FormMain > UltraToolbarGridSociCollaboratoriAgenda > Modifica GridSociCollaboratori Agenda
#### UltraToolbarsManagerHome

- `Anagrafica_Utente`: FormMain > UltraToolbarHome > Anagrafica Utente
- `Privacy`: FormMain > UltraToolbarHome > Privacy
#### UltraToolbarsManagerMovimentazioni

- `Prima_Nota_Cassa`: FormMain > UltraToolbarMovimentaioni > Prima Nota Cassa
- `Studi_di_Settore`: FormMain > UltraToolbarMovimentaioni > Studi di Settore
- `Volume_Affari`: FormMain > UltraToolbarMovimentaioni > Volume Affari
#### UltraToolbarsManagerRubrica

- `Connetti_And_Ricevi_Pratica`: FormMain > UltraToolbarRubrica > Connetti And Ricevi Pratica
- `Faldoni`: FormMain > UltraToolbarRubrica > Faldoni
- `Pratiche_Archiviate`: FormMain > UltraToolbarRubrica > Pratiche Archiviate
- `Pratiche_Attive`: FormMain > UltraToolbarRubrica > Pratiche Attive
- `Processo_Telematico`: FormMain > UltraToolbarRubrica > Processo Telematico
- `Rubrica_Telefonica_White`: FormMain > UltraToolbarRubrica > Rubrica Telefonica White
#### UltraToolbarsManagerStrumenti

- `Privacy`: FormMain > UltraToolbarStrumenti > Privacy
- `Strumenti`: FormMain > UltraToolbarStrumenti > Strumenti
#### UltraToolbarsManagerVideoscrittura

- `Altro_Videoscrittura`: FormMain > UltraToolbarVideoscrittura > Altro Videoscrittura
- `Cestino_Documenti`: FormMain > UltraToolbarVideoscrittura > Cestino Documenti
- `Documenti_Tutti`: FormMain > UltraToolbarVideoscrittura > Documenti Tutti
- `Formulario`: FormMain > UltraToolbarVideoscrittura > Formulario
#### UltraToolbarsManagerRight

- `Aggiungi_ParcellePratica`: FormMain > UTB Contabilità Pratica > Aggiungi ParcellePratica
- `Avviso`: FormMain > UTB Contabilità Pratica > Avviso
- `Elimina_Parcelle_Pratica`: FormMain > UTB Contabilità Pratica > Elimina Parcelle Pratica
- `LabelDescrizioneRight`: FormMain > UTB Contabilità Pratica > LabelDescrizioneRight
- `Modifica_Parcelle_Pratica`: FormMain > UTB Contabilità Pratica > Modifica Parcelle Pratica
- `Opzioni_ParcellePratica`: FormMain > UTB Contabilità Pratica > Opzioni ParcellePratica
- `Aggiungi_Agenda`: FormMain > UTB_Agenda > Aggiungi Agenda
- `Avviso`: FormMain > UTB_Agenda > Avviso
- `Elimina_Agenda`: FormMain > UTB_Agenda > Elimina Agenda
- `Elimina_Filtro_Agenda`: FormMain > UTB_Agenda > Elimina Filtro Agenda
- `Elimina_Filtro_Agenda_SingolaPratica`: FormMain > UTB_Agenda > Elimina Filtro Agenda SingolaPratica
- `Filtra_Agenda`: FormMain > UTB_Agenda > Filtra Agenda
- `Filtra_Agenda_SingolaPratica`: FormMain > UTB_Agenda > Filtra Agenda SingolaPratica
- `LabelDescrizioneRight`: FormMain > UTB_Agenda > LabelDescrizioneRight
- `Modifica_Agenda`: FormMain > UTB_Agenda > Modifica Agenda
- `Opzioni_Agenda`: FormMain > UTB_Agenda > Opzioni Agenda
- `Trova_Agenda_Dx`: FormMain > UTB_Agenda > Trova Agenda Dx
- `Aggiungi_Appunti_Pratica`: FormMain > UTB_AppuntiPratica > Aggiungi Appunti Pratica
- `Avviso`: FormMain > UTB_AppuntiPratica > Avviso
- `Elimina_Appunti_Pratica`: FormMain > UTB_AppuntiPratica > Elimina Appunti Pratica
- `LabelDescrizioneRight`: FormMain > UTB_AppuntiPratica > LabelDescrizioneRight
- `Modifica_Appunti_Pratica`: FormMain > UTB_AppuntiPratica > Modifica Appunti Pratica
- `Opzioni_AppuntiPratica`: FormMain > UTB_AppuntiPratica > Opzioni AppuntiPratica
- `Aggiungi_Prestazioni`: FormMain > UTB_Contabilità > Aggiungi Prestazioni
- `Avviso`: FormMain > UTB_Contabilità > Avviso
- `ControllaFattura`: FormMain > UTB_Contabilità > ControllaFattura
- `Elimina_OnorariPrestazioni`: FormMain > UTB_Contabilità > Elimina OnorariPrestazioni
- `InviaFattura`: FormMain > UTB_Contabilità > InviaFattura
- `LabelDescrizioneRight`: FormMain > UTB_Contabilità > LabelDescrizioneRight
- `LabelTool1`: FormMain > UTB_Contabilità > LabelTool1
- `Modifica_Contabilità`: FormMain > UTB_Contabilità > Modifica Contabilità
- `Opzioni_Parcelle`: FormMain > UTB_Contabilità > Opzioni Parcelle
#### UltraToolbarsManagerVerticale

- `Anagrafica_Utente`: FormMain > UTB_ContabilitàLeft > Anagrafica Utente
- `Contabilità_Intestatario`: FormMain > UTB_ContabilitàLeft > Contabilità Intestatario
- `IdentificazioneFiscale`: FormMain > UTB_ContabilitàLeft > IdentificazioneFiscale
- `Incassi_Parcella`: FormMain > UTB_ContabilitàLeft > Incassi Parcella
- `InviaFattura`: FormMain > UTB_ContabilitàLeft > InviaFattura
- `LabelTool1`: FormMain > UTB_ContabilitàLeft > LabelTool1
- `Onorario`: FormMain > UTB_ContabilitàLeft > Onorario
- `Parametri_Parcella`: FormMain > UTB_ContabilitàLeft > Parametri Parcella
#### UltraToolbarsManagerRight

- `Aggiungi_Email`: FormMain > UTB_Email > Aggiungi Email
- `Avviso`: FormMain > UTB_Email > Avviso
- `Connetti_And_Ricevi`: FormMain > UTB_Email > Connetti And Ricevi
- `ControlContainerPager`: FormMain > UTB_Email > ControlContainerPager
- `Elimina_Email`: FormMain > UTB_Email > Elimina Email
- `Elimina_Filtro_Email`: FormMain > UTB_Email > Elimina Filtro Email
- `Elimina_Filtro_Email_SingolaPratica`: FormMain > UTB_Email > Elimina Filtro Email SingolaPratica
- `Filtra_Email`: FormMain > UTB_Email > Filtra Email
- `Filtra_Email_SingolaPratica`: FormMain > UTB_Email > Filtra Email SingolaPratica
- `LabelDescrizioneRight`: FormMain > UTB_Email > LabelDescrizioneRight
- `Modifica_Email`: FormMain > UTB_Email > Modifica Email
- `Opzioni_GridEmail`: FormMain > UTB_Email > Opzioni GridEmail
- `Trova_EmailPratica`: FormMain > UTB_Email > Trova EmailPratica
- `Aggiungi_EntrataUscita_Pratica`: FormMain > UTB_EntrateUscitePratica > Aggiungi EntrataUscita Pratica
- `Avviso`: FormMain > UTB_EntrateUscitePratica > Avviso
- `Elimina_EntrataUscita_Pratica`: FormMain > UTB_EntrateUscitePratica > Elimina EntrataUscita Pratica
- `LabelDescrizioneRight`: FormMain > UTB_EntrateUscitePratica > LabelDescrizioneRight
- `Modifica_EntrataUscita_Pratica`: FormMain > UTB_EntrateUscitePratica > Modifica EntrataUscita Pratica
- `Opzioni_EntrateUscitePratica`: FormMain > UTB_EntrateUscitePratica > Opzioni EntrateUscitePratica
- `Cover_Aggiungi_Contabilità`: FormMain > UTB_FattureAcquisti > Cover Aggiungi Contabilità
- `Elimina_FattureAcquisto`: FormMain > UTB_FattureAcquisti > Elimina FattureAcquisto
- `LabelTool1`: FormMain > UTB_FattureAcquisti > LabelTool1
- `Modifica_FattureAcquisto`: FormMain > UTB_FattureAcquisti > Modifica FattureAcquisto
- `Aggiungi_LettereDocumenti_Pratica`: FormMain > UTB_LettereDocumentiPratica > Aggiungi LettereDocumenti Pratica
- `Avviso`: FormMain > UTB_LettereDocumentiPratica > Avviso
- `Elimina_Filtro_LettereDocumentiPratica`: FormMain > UTB_LettereDocumentiPratica > Elimina Filtro LettereDocumentiPratica
- `Elimina_LettereDocumenti_Pratica`: FormMain > UTB_LettereDocumentiPratica > Elimina LettereDocumenti Pratica
- `Filtra_LettereDocumentiPratica`: FormMain > UTB_LettereDocumentiPratica > Filtra LettereDocumentiPratica
- `LabelDescrizioneRight`: FormMain > UTB_LettereDocumentiPratica > LabelDescrizioneRight
- `Modifica_LettereDocumenti_Pratica`: FormMain > UTB_LettereDocumentiPratica > Modifica LettereDocumenti Pratica
- `Opzioni_LettereDocumentiPratica`: FormMain > UTB_LettereDocumentiPratica > Opzioni LettereDocumentiPratica
- `Trova_LettereDocumentiPratica`: FormMain > UTB_LettereDocumentiPratica > Trova LettereDocumentiPratica
- `Aggiungi_Movimentazioni`: FormMain > UTB_Movimentazioni > Aggiungi Movimentazioni
- `Avviso`: FormMain > UTB_Movimentazioni > Avviso
- `Elimina_Movimentazioni`: FormMain > UTB_Movimentazioni > Elimina Movimentazioni
- `LabelDescrizioneRight`: FormMain > UTB_Movimentazioni > LabelDescrizioneRight
- `Modifica_Movimentazioni`: FormMain > UTB_Movimentazioni > Modifica Movimentazioni
- `Opzioni_Movimentazioni`: FormMain > UTB_Movimentazioni > Opzioni Movimentazioni
- `Aggiungi_Nomi_Pratica`: FormMain > UTB_NomiPratica > Aggiungi Nomi Pratica
- `Avviso`: FormMain > UTB_NomiPratica > Avviso
- `Elimina_Nomi_Pratica`: FormMain > UTB_NomiPratica > Elimina Nomi Pratica
- `LabelDescrizioneRight`: FormMain > UTB_NomiPratica > LabelDescrizioneRight
- `Modifica_Nomi_Pratica`: FormMain > UTB_NomiPratica > Modifica Nomi Pratica
- `Opzioni_NomiPratica`: FormMain > UTB_NomiPratica > Opzioni NomiPratica
#### UltraToolbarsManagerLeft

- `Aggiungi_Rubrica`: FormMain > UTB_Rubrica > Aggiungi Rubrica
- `ContextMenu_GridRubrica`: FormMain > UTB_Rubrica > ContextMenu GridRubrica
- `Elimina_Filtro_Rubrica`: FormMain > UTB_Rubrica > Elimina Filtro Rubrica
- `Elimina_Rubrica`: FormMain > UTB_Rubrica > Elimina Rubrica
- `Filtra_Rubrica`: FormMain > UTB_Rubrica > Filtra Rubrica
- `LabelRubricaLeft`: FormMain > UTB_Rubrica > LabelRubricaLeft
- `Modifica_Rubrica`: FormMain > UTB_Rubrica > Modifica Rubrica
- `Trova_Rubrica_Sx`: FormMain > UTB_Rubrica > Trova Rubrica Sx
- `Aggiungi_Schedario`: FormMain > UTB_Schedario > Aggiungi Schedario
- `ContextMenu_GridSchedario`: FormMain > UTB_Schedario > ContextMenu GridSchedario
- `Elimina_Filtro_Schedario`: FormMain > UTB_Schedario > Elimina Filtro Schedario
- `Elimina_Schedario`: FormMain > UTB_Schedario > Elimina Schedario
- `Filtra_Schedario`: FormMain > UTB_Schedario > Filtra Schedario
- `LabelAnagraficaLeft`: FormMain > UTB_Schedario > LabelAnagraficaLeft
- `Modifica_Schedario`: FormMain > UTB_Schedario > Modifica Schedario
- `Trova_Schedario_Sx`: FormMain > UTB_Schedario > Trova Schedario Sx
- `Aggiungi_Videoscrittura`: FormMain > UTB_Videoscrittura > Aggiungi Videoscrittura
- `ContextMenu_GridVideoscrittura`: FormMain > UTB_Videoscrittura > ContextMenu GridVideoscrittura
- `Elimina_Filtro_Videoscrittura`: FormMain > UTB_Videoscrittura > Elimina Filtro Videoscrittura
- `Elimina_Videoscrittura`: FormMain > UTB_Videoscrittura > Elimina Videoscrittura
- `Filtra_Videoscrittura`: FormMain > UTB_Videoscrittura > Filtra Videoscrittura
- `LabelVideoscritturaLeft`: FormMain > UTB_Videoscrittura > LabelVideoscritturaLeft
- `Modifica_Videoscrittura`: FormMain > UTB_Videoscrittura > Modifica Videoscrittura
- `Trova_Videoscrittura_Sx`: FormMain > UTB_Videoscrittura > Trova Videoscrittura Sx
#### menu_contestuale

- `Aggiorna_Servizi_Telematici`: FormMain > Utilità database > Aggiorna Servizi Telematici
- `Backup`: FormMain > Utilità database > Backup
- `Compattazione`: FormMain > Utilità database > Compattazione
- `PosizioneDatabase`: FormMain > Utilità database > PosizioneDatabase
- `Restore`: FormMain > Utilità database > Restore
- `VerificaMedianteAndXor`: FormMain > Verifica firma digitale... > VerificaMedianteAndXor
- `VerificaMedianteDigitaSign`: FormMain > Verifica firma digitale... > VerificaMedianteDigitaSign
- `VerificaMedianteInfocert`: FormMain > Verifica firma digitale... > VerificaMedianteInfocert
- `VerificaMedianteNamirial`: FormMain > Verifica firma digitale... > VerificaMedianteNamirial
- `VerificaMedianteNostroSoftware`: FormMain > Verifica firma digitale... > VerificaMedianteNostroSoftware
- `VerificaMedianteNotariato`: FormMain > Verifica firma digitale... > VerificaMedianteNotariato
- `VerificaMediantePostecom`: FormMain > Verifica firma digitale... > VerificaMediantePostecom
### FormMotivoRicorsoCassazione

Sorgente: `QuickOrganizer/FormMotivoRicorsoCassazione.cs`

#### non_associato

- `deleteFieldToolStripMenuItem`: FormMotivoRicorsoCassazione > contextMenuApplicationFields > &Delete Field
- `fieldPropertiesToolStripMenuItem`: FormMotivoRicorsoCassazione > contextMenuApplicationFields > Field &Properties…
### FormVerbale

Sorgente: `QuickOrganizer/FormVerbale.cs`

#### non_associato

- `deleteFieldToolStripMenuItem`: FormVerbale > contextMenuApplicationFields > &Delete Field
- `fieldPropertiesToolStripMenuItem`: FormVerbale > contextMenuApplicationFields > Field &Properties…
### QualifiedCertificate

Sorgente: `QuickOrganizer/QualifiedCertificate.cs`

#### non_associato

- `deleteFieldToolStripMenuItem`: QualifiedCertificate > contextMenuApplicationFields > &Delete Field
- `fieldPropertiesToolStripMenuItem`: QualifiedCertificate > contextMenuApplicationFields > Field &Properties…
### SchedaAppunti

Sorgente: `QuickOrganizer/SchedaAppunti.cs`

#### non_associato

- `deleteFieldToolStripMenuItem`: SchedaAppunti > contextMenuApplicationFields > &Delete Field
- `fieldPropertiesToolStripMenuItem`: SchedaAppunti > contextMenuApplicationFields > Field &Properties…
- `saveFileAsToolStripMenuItem`: SchedaAppunti > menuStrip1 > &File > &Esporta Appunti...
- `pageSetupToolStripMenuItem`: SchedaAppunti > menuStrip1 > &File > &Setup pagina...
- `stampaToolStripMenuItem`: SchedaAppunti > menuStrip1 > &File > S&tampa...
- `characterToolStripMenuItem`: SchedaAppunti > menuStrip1 > &Formato > &Carattere...
- `paragraphToolStripMenuItem`: SchedaAppunti > menuStrip1 > &Formato > &Paragrafo...
- `columnsToolStripMenuItem`: SchedaAppunti > menuStrip1 > &Formato > Col&onne...
- `pasteToolStripMenuItem`: SchedaAppunti > menuStrip1 > &Modifica > &Incolla
- `cutToolStripMenuItem`: SchedaAppunti > menuStrip1 > &Modifica > &Taglia
- `copyToolStripMenuItem`: SchedaAppunti > menuStrip1 > &Modifica > C&opia
- `inserisciImmagineToolStripMenuItem`: SchedaAppunti > menuStrip1 > Immagine > Inserisci immagine...
### SchedaEmailRicevute

Sorgente: `QuickOrganizer/SchedaEmailRicevute.cs`

#### non_associato

- `CopySelectedTextToolStripMenuItem`: SchedaEmailRicevute > contextMenuApplicationFields > Copy
### SchedaNotifica

Sorgente: `QuickOrganizer/SchedaNotifica.cs`

#### non_associato

- `deleteFieldToolStripMenuItem`: SchedaNotifica > contextMenuApplicationFields > &Delete Field
- `fieldPropertiesToolStripMenuItem`: SchedaNotifica > contextMenuApplicationFields > Field &Properties…
- `saveFileAsToolStripMenuItem`: SchedaNotifica > menuStrip1 > &File > &Esporta Appunti...
- `pageSetupToolStripMenuItem`: SchedaNotifica > menuStrip1 > &File > &Setup pagina...
- `stampaToolStripMenuItem`: SchedaNotifica > menuStrip1 > &File > S&tampa...
- `characterToolStripMenuItem`: SchedaNotifica > menuStrip1 > &Formato > &Carattere...
- `paragraphToolStripMenuItem`: SchedaNotifica > menuStrip1 > &Formato > &Paragrafo...
- `columnsToolStripMenuItem`: SchedaNotifica > menuStrip1 > &Formato > Col&onne...
- `pasteToolStripMenuItem`: SchedaNotifica > menuStrip1 > &Modifica > &Incolla
- `cutToolStripMenuItem`: SchedaNotifica > menuStrip1 > &Modifica > &Taglia
- `copyToolStripMenuItem`: SchedaNotifica > menuStrip1 > &Modifica > C&opia
### SchedaOnorari

Sorgente: `QuickOrganizer/SchedaOnorari.cs`

#### menu_contestuale

- `Recupera_Voci_Da_Precedente_Fattura`: SchedaOnorari > Recupera voci... > Recupera Voci Da Precedente Fattura
- `Recupera_Voci_Da_Precedente_Nota_Di_Credito`: SchedaOnorari > Recupera voci... > Recupera Voci Da Precedente Nota Di Credito
- `Recupera_Voci_Da_Precedente_Nota_Spese`: SchedaOnorari > Recupera voci... > Recupera Voci Da Precedente Nota Spese
- `Recupera_Voci_Da_Precedente_Preavviso_Di_Parcella`: SchedaOnorari > Recupera voci... > Recupera Voci Da Precedente Preavviso Di Parcella
- `Recupera_Voci_Da_Precedente_Preventivo`: SchedaOnorari > Recupera voci... > Recupera Voci Da Precedente Preventivo
- `Recupera_Voci_Dal_Tariffario`: SchedaOnorari > Recupera voci... > Recupera Voci Dal Tariffario
- `Recupera_Voci_Dalla_Pratica`: SchedaOnorari > Recupera voci... > Recupera Voci Dalla Pratica
- `Recupera_Voci_Dalla_PrimaNotaCassa`: SchedaOnorari > Recupera voci... > Recupera Voci Dalla PrimaNotaCassa
### SchedaPratica

Sorgente: `QuickOrganizer/SchedaPratica.cs`

#### non_associato

- `deleteFieldToolStripMenuItem`: SchedaPratica > contextMenuApplicationFields > &Delete Field
- `fieldPropertiesToolStripMenuItem`: SchedaPratica > contextMenuApplicationFields > Field &Properties…
### SchedaResoconto

Sorgente: `QuickOrganizer/SchedaResoconto.cs`

#### non_associato

- `deleteFieldToolStripMenuItem`: SchedaResoconto > contextMenuApplicationFields > &Delete Field
- `fieldPropertiesToolStripMenuItem`: SchedaResoconto > contextMenuApplicationFields > Field &Properties…
- `saveFileAsToolStripMenuItem`: SchedaResoconto > menuStrip1 > &File > &Esporta Appunti...
- `pageSetupToolStripMenuItem`: SchedaResoconto > menuStrip1 > &File > &Setup pagina...
- `stampaToolStripMenuItem`: SchedaResoconto > menuStrip1 > &File > S&tampa...
- `characterToolStripMenuItem`: SchedaResoconto > menuStrip1 > &Formato > &Carattere...
- `paragraphToolStripMenuItem`: SchedaResoconto > menuStrip1 > &Formato > &Paragrafo...
- `columnsToolStripMenuItem`: SchedaResoconto > menuStrip1 > &Formato > Col&onne...
- `pasteToolStripMenuItem`: SchedaResoconto > menuStrip1 > &Modifica > &Incolla
- `cutToolStripMenuItem`: SchedaResoconto > menuStrip1 > &Modifica > &Taglia
- `copyToolStripMenuItem`: SchedaResoconto > menuStrip1 > &Modifica > C&opia
### frmFindReplace

Sorgente: `QuickOrganizer/frmFindReplace.cs`

#### non_associato

- `fontToolStripMenuItem`: frmFindReplace > contextMenuStrip2 > &Font...
### QuickWordMain

Sorgente: `QuickWord/QuickWordMain.cs`

#### menu_contestuale

- `Date Time`: QuickWordMain > Altri Dati > Date Time
- `Inserisci_Metadato_DataOdierna`: QuickWordMain > Altri Dati > Inserisci Metadato DataOdierna
- `Inserisci_Metadato_Luogo`: QuickWordMain > Altri Dati > Inserisci Metadato Luogo
- `Inserisci_Metadato_NomeAvvocatoControparte`: QuickWordMain > Altri Dati > Inserisci Metadato NomeAvvocatoControparte
- `Inserisci_Metadato_NomeDifensore`: QuickWordMain > Altri Dati > Inserisci Metadato NomeDifensore
- `Inserisci_Metadato_NomeIndirizzodifensore`: QuickWordMain > Altri Dati > Inserisci Metadato NomeIndirizzodifensore
- `Inserisci_Metadato_OrarioAttuale`: QuickWordMain > Altri Dati > Inserisci Metadato OrarioAttuale
- `Inserisci_Metadato_DataOdierna`: QuickWordMain > Altri Metadati > Inserisci Metadato DataOdierna
- `Inserisci_Metadato_Luogo`: QuickWordMain > Altri Metadati > Inserisci Metadato Luogo
- `Inserisci_Metadato_NomeAvvocatoControparte`: QuickWordMain > Altri Metadati > Inserisci Metadato NomeAvvocatoControparte
- `Inserisci_Metadato_NomeDifensore`: QuickWordMain > Altri Metadati > Inserisci Metadato NomeDifensore
- `Inserisci_Metadato_NomeIndirizzodifensore`: QuickWordMain > Altri Metadati > Inserisci Metadato NomeIndirizzodifensore
- `Inserisci_Metadato_OrarioAttuale`: QuickWordMain > Altri Metadati > Inserisci Metadato OrarioAttuale
#### non_associato

- `Table`: QuickWordMain > Azioni > Table
- `Table Properties`: QuickWordMain > Azioni > Table Properties
#### menu_contestuale

- `Format Bullets`: QuickWordMain > Bullets > Format Bullets
- `Other Symbols`: QuickWordMain > Bullets > Other Symbols
- `RecentlyUsedBullets`: QuickWordMain > Bullets > RecentlyUsedBullets
- `Capitalize Each Word`: QuickWordMain > Change Case > Capitalize Each Word
- `lowercase`: QuickWordMain > Change Case > lowercase
- `Sentence case`: QuickWordMain > Change Case > Sentence case
- `tOGGLE cASE`: QuickWordMain > Change Case > tOGGLE cASE
- `UPPERCASE`: QuickWordMain > Change Case > UPPERCASE
- `Inserisci_Metadato_AutovetturaCliente`: QuickWordMain > Cliente > Inserisci Metadato AutovetturaCliente
- `Inserisci_Metadato_CodiceFiscaleCliente`: QuickWordMain > Cliente > Inserisci Metadato CodiceFiscaleCliente
- `Inserisci_Metadato_DataLuogoCostituzioneNascita_Cliente`: QuickWordMain > Cliente > Inserisci Metadato DataLuogoCostituzioneNascita Cliente
- `Inserisci_Metadato_EmailCliente`: QuickWordMain > Cliente > Inserisci Metadato EmailCliente
- `Inserisci_Metadato_NomeCliente`: QuickWordMain > Cliente > Inserisci Metadato NomeCliente
- `Inserisci_Metadato_NomeIndirizzoCliente`: QuickWordMain > Cliente > Inserisci Metadato NomeIndirizzoCliente
- `Inserisci_Metadato_PartitaIVACliente`: QuickWordMain > Cliente > Inserisci Metadato PartitaIVACliente
- `Inserisci_Metadato_TelefonoCliente`: QuickWordMain > Cliente > Inserisci Metadato TelefonoCliente
#### non_associato

- `Copy`: QuickWordMain > Clipboard > Copy
- `Cut`: QuickWordMain > Clipboard > Cut
- `PasteMenu`: QuickWordMain > Clipboard > PasteMenu
- `Seleziona_Tutto`: QuickWordMain > Clipboard > Seleziona Tutto
#### menu_contestuale

- `To The Left`: QuickWordMain > Colonna > To The Left
- `To The Right`: QuickWordMain > Colonna > To The Right
- `cmdBtnMergeIntoCurrent`: QuickWordMain > Completa & Unione > cmdBtnMergeIntoCurrent
- `cmdBtnMergePrint`: QuickWordMain > Completa & Unione > cmdBtnMergePrint
- `cmdDrpDnMergeIntoIndivDocs`: QuickWordMain > Completa & Unione > cmdDrpDnMergeIntoIndivDocs
- `cmdDrpDnMergeSaveSingle`: QuickWordMain > Completa & Unione > cmdDrpDnMergeSaveSingle
#### non_associato

- `deleteFieldToolStripMenuItem`: QuickWordMain > contextMenuApplicationFields > &Delete Field
- `fieldPropertiesToolStripMenuItem`: QuickWordMain > contextMenuApplicationFields > Field &Properties…
#### menu_contestuale

- `Inserisci_Metadato_AutovetturaControparte`: QuickWordMain > Controparte > Inserisci Metadato AutovetturaControparte
- `Inserisci_Metadato_CodiceFiscaleControparte`: QuickWordMain > Controparte > Inserisci Metadato CodiceFiscaleControparte
- `Inserisci_Metadato_DataLuogoCostituzioneNascita_Controparte`: QuickWordMain > Controparte > Inserisci Metadato DataLuogoCostituzioneNascita Controparte
- `Inserisci_Metadato_EmailControparte`: QuickWordMain > Controparte > Inserisci Metadato EmailControparte
- `Inserisci_Metadato_NomeControparte`: QuickWordMain > Controparte > Inserisci Metadato NomeControparte
- `Inserisci_Metadato_NomeIndirizzoControparte`: QuickWordMain > Controparte > Inserisci Metadato NomeIndirizzoControparte
- `Inserisci_Metadato_PartitaIVAControparte`: QuickWordMain > Controparte > Inserisci Metadato PartitaIVAControparte
- `Inserisci_Metadato_TelefonoControparte`: QuickWordMain > Controparte > Inserisci Metadato TelefonoControparte
- `Inserisci_Metadato_AutovetturaCorrispondente`: QuickWordMain > Corrispondente > Inserisci Metadato AutovetturaCorrispondente
- `Inserisci_Metadato_CodiceFiscaleCorrispondente`: QuickWordMain > Corrispondente > Inserisci Metadato CodiceFiscaleCorrispondente
- `Inserisci_Metadato_DataLuogoCostituzioneNascita_Corrispondente`: QuickWordMain > Corrispondente > Inserisci Metadato DataLuogoCostituzioneNascita Corrispondente
- `Inserisci_Metadato_EmailCorrispondente`: QuickWordMain > Corrispondente > Inserisci Metadato EmailCorrispondente
- `Inserisci_Metadato_NomeCorrispondente`: QuickWordMain > Corrispondente > Inserisci Metadato NomeCorrispondente
- `Inserisci_Metadato_NomeIndirizzoCorrispondente`: QuickWordMain > Corrispondente > Inserisci Metadato NomeIndirizzoCorrispondente
- `Inserisci_Metadato_PartitaIVACorrispondente`: QuickWordMain > Corrispondente > Inserisci Metadato PartitaIVACorrispondente
- `Inserisci_Metadato_TelefonoCorrispondente`: QuickWordMain > Corrispondente > Inserisci Metadato TelefonoCorrispondente
- `Inserisci_Metadato_AnnoRuoloGenerale`: QuickWordMain > Curia > Inserisci Metadato AnnoRuoloGenerale
- `Inserisci_Metadato_Cancelliere`: QuickWordMain > Curia > Inserisci Metadato Cancelliere
- `Inserisci_Metadato_CTP`: QuickWordMain > Curia > Inserisci Metadato CTP
- `Inserisci_Metadato_CTU`: QuickWordMain > Curia > Inserisci Metadato CTU
- `Inserisci_Metadato_Curia`: QuickWordMain > Curia > Inserisci Metadato Curia
- `Inserisci_Metadato_Istruttore`: QuickWordMain > Curia > Inserisci Metadato Istruttore
- `Inserisci_Metadato_RuoloGenerale`: QuickWordMain > Curia > Inserisci Metadato RuoloGenerale
- `Inserisci_Metadato_Sezione`: QuickWordMain > Curia > Inserisci Metadato Sezione
- `Inserisci_Metadato_Valore`: QuickWordMain > Curia > Inserisci Metadato Valore
- `Inserisci_Metadato_AnnotazioniPratica`: QuickWordMain > Dati Generali Pratica > Inserisci Metadato AnnotazioniPratica
- `Inserisci_Metadato_DataApertura`: QuickWordMain > Dati Generali Pratica > Inserisci Metadato DataApertura
- `Inserisci_Metadato_DataArchiviazione`: QuickWordMain > Dati Generali Pratica > Inserisci Metadato DataArchiviazione
- `Inserisci_Metadato_NomePratica`: QuickWordMain > Dati Generali Pratica > Inserisci Metadato NomePratica
- `Inserisci_Metadato_NomeResponsabilePratica`: QuickWordMain > Dati Generali Pratica > Inserisci Metadato NomeResponsabilePratica
- `Inserisci_Metadato_OggettoPratica`: QuickWordMain > Dati Generali Pratica > Inserisci Metadato OggettoPratica
- `Inserisci_Metadato_RiferimentoCartaceo`: QuickWordMain > Dati Generali Pratica > Inserisci Metadato RiferimentoCartaceo
- `Inserisci_Metadato_TipoPratica`: QuickWordMain > Dati Generali Pratica > Inserisci Metadato TipoPratica
- `Dictation`: QuickWordMain > Dettatura vocale > Dictation
- `Speechnotes`: QuickWordMain > Dettatura vocale > Speechnotes
- `Talktype`: QuickWordMain > Dettatura vocale > Talktype
- `Dictation`: QuickWordMain > Dettatura vocale online... > Dictation
- `Speechnotes`: QuickWordMain > Dettatura vocale online... > Speechnotes
- `Talktype`: QuickWordMain > Dettatura vocale online... > Talktype
#### non_associato

- `Append`: QuickWordMain > Documents > Append
- `Formulario`: QuickWordMain > Documents > Formulario
- `Include`: QuickWordMain > Documents > Include
- `cmdBtnDraft`: QuickWordMain > DocumentViews > cmdBtnDraft
- `cmdBtnPrintLayout`: QuickWordMain > DocumentViews > cmdBtnPrintLayout
- `cmdDrpDnBtnZoom`: QuickWordMain > DocumentViews > cmdDrpDnBtnZoom
- `Inserisci`: QuickWordMain > Editing > Inserisci
- `Ortografia`: QuickWordMain > Editing > Ortografia
#### menu_contestuale

- `Delete Column`: QuickWordMain > Elimina > Delete Column
- `Delete Rows`: QuickWordMain > Elimina > Delete Rows
- `Delete Table`: QuickWordMain > Elimina > Delete Table
- `DOC`: QuickWordMain > Esporta... > DOC
- `DOCX`: QuickWordMain > Esporta... > DOCX
- `Esporta_Formato_PDF_Firmato`: QuickWordMain > Esporta... > Esporta Formato PDF Firmato
- `PDF`: QuickWordMain > Esporta... > PDF
- `RTF`: QuickWordMain > Esporta... > RTF
#### non_associato

- `cmdSpltBtnFinishAndMerge`: QuickWordMain > Finish > cmdSpltBtnFinishAndMerge
#### menu_contestuale

- `cmdBtnMergeToDOCs`: QuickWordMain > Fondi in (tanti) Documenti Esterni > cmdBtnMergeToDOCs
- `cmdBtnMergeToDOCXs`: QuickWordMain > Fondi in (tanti) Documenti Esterni > cmdBtnMergeToDOCXs
- `cmdBtnMergeToHTMLs`: QuickWordMain > Fondi in (tanti) Documenti Esterni > cmdBtnMergeToHTMLs
- `cmdBtnMergeToPDFs`: QuickWordMain > Fondi in (tanti) Documenti Esterni > cmdBtnMergeToPDFs
- `cmdBtnMergeToRTFs`: QuickWordMain > Fondi in (tanti) Documenti Esterni > cmdBtnMergeToRTFs
- `cmdBtnMergeToTXTs`: QuickWordMain > Fondi in (tanti) Documenti Esterni > cmdBtnMergeToTXTs
- `cmdBtnMergeToDOC`: QuickWordMain > Fondi in un Documento (unico) Esterno > cmdBtnMergeToDOC
- `cmdBtnMergeToDOCX`: QuickWordMain > Fondi in un Documento (unico) Esterno > cmdBtnMergeToDOCX
- `cmdBtnMergeToHTML`: QuickWordMain > Fondi in un Documento (unico) Esterno > cmdBtnMergeToHTML
- `cmdBtnMergeToPDF`: QuickWordMain > Fondi in un Documento (unico) Esterno > cmdBtnMergeToPDF
- `cmdBtnMergeToRTF`: QuickWordMain > Fondi in un Documento (unico) Esterno > cmdBtnMergeToRTF
- `cmdBtnMergeToTXT`: QuickWordMain > Fondi in un Documento (unico) Esterno > cmdBtnMergeToTXT
#### non_associato

- `Bold`: QuickWordMain > Font > Bold
- `Change Case`: QuickWordMain > Font > Change Case
- `Clear Formatting`: QuickWordMain > Font > Clear Formatting
- `Font Color`: QuickWordMain > Font > Font Color
- `FontName`: QuickWordMain > Font > FontName
- `FontSize`: QuickWordMain > Font > FontSize
- `Grow Font`: QuickWordMain > Font > Grow Font
- `Italic`: QuickWordMain > Font > Italic
- `Shrink Font`: QuickWordMain > Font > Shrink Font
- `Strikethrough`: QuickWordMain > Font > Strikethrough
- `Text Highlight Color`: QuickWordMain > Font > Text Highlight Color
- `UnderlineStyles`: QuickWordMain > Font > UnderlineStyles
#### menu_contestuale

- `Add Footer`: QuickWordMain > Footer > Add Footer
- `Delete Footer`: QuickWordMain > Footer > Delete Footer
- `Bottom`: QuickWordMain > Frame > Bottom
- `Left`: QuickWordMain > Frame > Left
- `Merge Frames`: QuickWordMain > Frame > Merge Frames
- `Outside Borders`: QuickWordMain > Frame > Outside Borders
- `Right`: QuickWordMain > Frame > Right
- `Top`: QuickWordMain > Frame > Top
- `Add Header`: QuickWordMain > Header > Add Header
- `Delete Header`: QuickWordMain > Header > Delete Header
#### non_associato

- `Footer_Menu`: QuickWordMain > Headers && Footers > Footer Menu
- `Header_Menu`: QuickWordMain > Headers && Footers > Header Menu
- `Page Number`: QuickWordMain > Headers && Footers > Page Number
- `Picture`: QuickWordMain > Images > Picture
#### menu_contestuale

- `PageNumber_Top_Center`: QuickWordMain > In alto... > PageNumber Top Center
- `PageNumber_Top_Left`: QuickWordMain > In alto... > PageNumber Top Left
- `PageNumber_Top_Right`: QuickWordMain > In alto... > PageNumber Top Right
- `PageNumber_Bottom_Center`: QuickWordMain > In basso... > PageNumber Bottom Center
- `PageNumber_Bottom_Left`: QuickWordMain > In basso... > PageNumber Bottom Left
- `PageNumber_Bottom_Right`: QuickWordMain > In basso... > PageNumber Bottom Right
- `Paste`: QuickWordMain > Incolla > Paste
- `Paste2`: QuickWordMain > Incolla > Paste2
#### non_associato

- `Cancella_Metadato`: QuickWordMain > Inserisci > Cancella Metadato
- `Inserisci_Altri_Metadati`: QuickWordMain > Inserisci > Inserisci Altri Metadati
- `Inserisci_Metadati_Anagrafica`: QuickWordMain > Inserisci > Inserisci Metadati Anagrafica
- `Inserisci_Metadati_Curia`: QuickWordMain > Inserisci > Inserisci Metadati Curia
- `Inserisci_Metadati_Pratica`: QuickWordMain > Inserisci > Inserisci Metadati Pratica
#### menu_contestuale

- `AUTO`: QuickWordMain > Inserisci Campo Merge > AUTO
- `CAP`: QuickWordMain > Inserisci Campo Merge > CAP
- `CELLU`: QuickWordMain > Inserisci Campo Merge > CELLU
- `CITTA`: QuickWordMain > Inserisci Campo Merge > CITTA
- `CODICE_FISCALE`: QuickWordMain > Inserisci Campo Merge > CODICE FISCALE
- `DATA_IDENTIFICAZIONE`: QuickWordMain > Inserisci Campo Merge > DATA IDENTIFICAZIONE
- `DATA_NA`: QuickWordMain > Inserisci Campo Merge > DATA NA
- `DOCUMENTO_IDENTIFICAZIONE`: QuickWordMain > Inserisci Campo Merge > DOCUMENTO IDENTIFICAZIONE
- `EMAIL`: QuickWordMain > Inserisci Campo Merge > EMAIL
- `FAX`: QuickWordMain > Inserisci Campo Merge > FAX
- `IBAN`: QuickWordMain > Inserisci Campo Merge > IBAN
- `INDIRIZZO`: QuickWordMain > Inserisci Campo Merge > INDIRIZZO
- `LEG_RAPP`: QuickWordMain > Inserisci Campo Merge > LEG RAPP
- `LUOGO_NA`: QuickWordMain > Inserisci Campo Merge > LUOGO NA
- `NOME`: QuickWordMain > Inserisci Campo Merge > NOME
- `PARTITA_IVA`: QuickWordMain > Inserisci Campo Merge > PARTITA IVA
- `TARGA`: QuickWordMain > Inserisci Campo Merge > TARGA
- `TEL`: QuickWordMain > Inserisci Campo Merge > TEL
- `TITOLO`: QuickWordMain > Inserisci Campo Merge > TITOLO
- `cmdBtnInsertDateField`: QuickWordMain > Inserisci Campo Speciale > cmdBtnInsertDateField
- `cmdBtnInsertIfField`: QuickWordMain > Inserisci Campo Speciale > cmdBtnInsertIfField
- `cmdBtnInsertIncludeTextField`: QuickWordMain > Inserisci Campo Speciale > cmdBtnInsertIncludeTextField
- `Altri_Dati`: QuickWordMain > Inserisci Speciale > Altri Dati
- `Clienti`: QuickWordMain > Inserisci Speciale > Clienti
- `Controparti`: QuickWordMain > Inserisci Speciale > Controparti
- `Corrispondenti`: QuickWordMain > Inserisci Speciale > Corrispondenti
- `Curia`: QuickWordMain > Inserisci Speciale > Curia
- `Pratica`: QuickWordMain > Inserisci Speciale > Pratica
- `Terzi`: QuickWordMain > Inserisci Speciale > Terzi
- `Testimoni`: QuickWordMain > Inserisci Speciale > Testimoni
- `Udienze`: QuickWordMain > Inserisci Speciale > Udienze
- `Invia_Formato_Pdf`: QuickWordMain > Invia a mezzo Email > Invia Formato Pdf
- `Invia_Formato_PDF_Firmato`: QuickWordMain > Invia a mezzo Email > Invia Formato PDF Firmato
- `Invia_Formato_Rft`: QuickWordMain > Invia a mezzo Email > Invia Formato Rft
- `1,0`: QuickWordMain > Line Spacing > 1,0
- `1,15`: QuickWordMain > Line Spacing > 1,15
- `1,5`: QuickWordMain > Line Spacing > 1,5
- `2,0`: QuickWordMain > Line Spacing > 2,0
- `2,5`: QuickWordMain > Line Spacing > 2,5
- `3,0`: QuickWordMain > Line Spacing > 3,0
#### non_associato

- `Bookmark`: QuickWordMain > Links > Bookmark
- `Hyperlink`: QuickWordMain > Links > Hyperlink
- `Find... `: QuickWordMain > Localizza > Find...
- `Got To... `: QuickWordMain > Localizza > Got To...
- `Replace... `: QuickWordMain > Localizza > Replace...
- `cmdBtnDeleteField`: QuickWordMain > MergeFields > cmdBtnDeleteField
- `cmdBtnFieldProps`: QuickWordMain > MergeFields > cmdBtnFieldProps
- `cmdDrpDnInsertSpecialField`: QuickWordMain > MergeFields > cmdDrpDnInsertSpecialField
- `cmdSpltBtnGlryInsMergeField`: QuickWordMain > MergeFields > cmdSpltBtnGlryInsMergeField
- `Select_Mailing_DataTable`: QuickWordMain > MergeFields > Select Mailing DataTable
#### menu_contestuale

- `Metadati_Clienti`: QuickWordMain > Metadati Anagrafica > Metadati Clienti
- `Metadati_Controparte`: QuickWordMain > Metadati Anagrafica > Metadati Controparte
- `Metadati_Corrispondente`: QuickWordMain > Metadati Anagrafica > Metadati Corrispondente
- `Metadati_Terzo`: QuickWordMain > Metadati Anagrafica > Metadati Terzo
- `Metadati_Testimone`: QuickWordMain > Metadati Anagrafica > Metadati Testimone
- `Metadati_Curia`: QuickWordMain > Metadati Curia > Metadati Curia
- `Metadati_Udienze`: QuickWordMain > Metadati Curia > Metadati Udienze
- `Inserisci_Metadato_AnnotazioniPratica`: QuickWordMain > Metadati Pratica > Inserisci Metadato AnnotazioniPratica
- `Inserisci_Metadato_DataApertura`: QuickWordMain > Metadati Pratica > Inserisci Metadato DataApertura
- `Inserisci_Metadato_DataArchiviazione`: QuickWordMain > Metadati Pratica > Inserisci Metadato DataArchiviazione
- `Inserisci_Metadato_Nome_Beni_Immobili_Pignorati`: QuickWordMain > Metadati Pratica > Inserisci Metadato Nome Beni Immobili Pignorati
- `Inserisci_Metadato_Nome_Beni_Mobili_Pignorati`: QuickWordMain > Metadati Pratica > Inserisci Metadato Nome Beni Mobili Pignorati
- `Inserisci_Metadato_Nome_Precisazione_Credito`: QuickWordMain > Metadati Pratica > Inserisci Metadato Nome Precisazione Credito
- `Inserisci_Metadato_Nome_Titolo_Esecutivo`: QuickWordMain > Metadati Pratica > Inserisci Metadato Nome Titolo Esecutivo
- `Inserisci_Metadato_NomePratica`: QuickWordMain > Metadati Pratica > Inserisci Metadato NomePratica
- `Inserisci_Metadato_NomeResponsabilePratica`: QuickWordMain > Metadati Pratica > Inserisci Metadato NomeResponsabilePratica
- `Inserisci_Metadato_OggettoPratica`: QuickWordMain > Metadati Pratica > Inserisci Metadato OggettoPratica
- `Inserisci_Metadato_RiferimentoCartaceo`: QuickWordMain > Metadati Pratica > Inserisci Metadato RiferimentoCartaceo
- `Inserisci_Metadato_TipoPratica`: QuickWordMain > Metadati Pratica > Inserisci Metadato TipoPratica
- `Format Numbered List...`: QuickWordMain > Numbering > Format Numbered List...
- `Recently Used Numbered Lists`: QuickWordMain > Numbering > Recently Used Numbered Lists
- `Sample Numbered Lists`: QuickWordMain > Numbering > Sample Numbered Lists
- `PageNumber_Bottom`: QuickWordMain > Numeri di Pagina > PageNumber Bottom
- `PageNumber_Remove`: QuickWordMain > Numeri di Pagina > PageNumber Remove
- `PageNumber_Top`: QuickWordMain > Numeri di Pagina > PageNumber Top
- `Orientamento_Orizzontale`: QuickWordMain > Orientamento > Orientamento Orizzontale
- `Orientamento_Verticale`: QuickWordMain > Orientamento > Orientamento Verticale
- `Controllo_Ortografico_Durante_Digitazione`: QuickWordMain > Ortografia & Sillabazione > Controllo Ortografico Durante Digitazione
- `Inizia_Controllo_Ortografico`: QuickWordMain > Ortografia & Sillabazione > Inizia Controllo Ortografico
- `Sillabazione`: QuickWordMain > Ortografia & Sillabazione > Sillabazione
#### non_associato

- `Blank Page`: QuickWordMain > Pages > Blank Page
- `Break`: QuickWordMain > Pages > Break
- `Align Text Left`: QuickWordMain > Paragraph > Align Text Left
- `Align Text Right`: QuickWordMain > Paragraph > Align Text Right
- `Bullets`: QuickWordMain > Paragraph > Bullets
- `Center Text`: QuickWordMain > Paragraph > Center Text
- `Decrease Indent`: QuickWordMain > Paragraph > Decrease Indent
- `Frame`: QuickWordMain > Paragraph > Frame
- `Increase Indent`: QuickWordMain > Paragraph > Increase Indent
- `Justify`: QuickWordMain > Paragraph > Justify
- `Line Spacing`: QuickWordMain > Paragraph > Line Spacing
- `Multilevel List`: QuickWordMain > Paragraph > Multilevel List
- `Numbering`: QuickWordMain > Paragraph > Numbering
- `Show Control Chars`: QuickWordMain > Paragraph > Show Control Chars
- `cmdBtnGoToFirstRecord`: QuickWordMain > Preview > cmdBtnGoToFirstRecord
- `cmdBtnGoToLastRecord`: QuickWordMain > Preview > cmdBtnGoToLastRecord
- `cmdBtnGoToNextRecord`: QuickWordMain > Preview > cmdBtnGoToNextRecord
- `cmdBtnGoToPrevRecord`: QuickWordMain > Preview > cmdBtnGoToPrevRecord
- `cmdTglBtnPreviewMergeFields`: QuickWordMain > Preview > cmdTglBtnPreviewMergeFields
#### menu_contestuale

- `Insert Row Above`: QuickWordMain > Riga > Insert Row Above
- `Insert Row Below`: QuickWordMain > Riga > Insert Row Below
- `Insert Bookmark`: QuickWordMain > Segnalibro > Insert Bookmark
- `Show Bookmark Markers`: QuickWordMain > Segnalibro > Show Bookmark Markers
- `Select Cell`: QuickWordMain > Seleziona > Select Cell
- `Select Row`: QuickWordMain > Seleziona > Select Row
- `Select Table`: QuickWordMain > Seleziona > Select Table
- `DataTable_Clienti`: QuickWordMain > Seleziona Database > DataTable Clienti
- `DataTable_Controparti`: QuickWordMain > Seleziona Database > DataTable Controparti
- `DataTable_Corrispondenti`: QuickWordMain > Seleziona Database > DataTable Corrispondenti
- `DataTable_Testimoni`: QuickWordMain > Seleziona Database > DataTable Testimoni
- `DataTable_Tutti_Nomi`: QuickWordMain > Seleziona Database > DataTable Tutti Nomi
#### non_associato

- `Bordi_Pagina`: QuickWordMain > Setup di Pagina > Bordi Pagina
- `Columns`: QuickWordMain > Setup di Pagina > Columns
- `Margins and Paper`: QuickWordMain > Setup di Pagina > Margins and Paper
- `Orientamento`: QuickWordMain > Setup di Pagina > Orientamento
- `sbtChkRulerHor`: QuickWordMain > Show > sbtChkRulerHor
- `sbtChkRulerVert`: QuickWordMain > Show > sbtChkRulerVert
- `sbtChkStatusBar`: QuickWordMain > Show > sbtChkStatusBar
#### menu_contestuale

- `Split Above`: QuickWordMain > Split Tabella > Split Above
- `Split Below`: QuickWordMain > Split Tabella > Split Below
- `Print`: QuickWordMain > Stampa... > Print
- `Print Preview`: QuickWordMain > Stampa... > Print Preview
- `Quick Print`: QuickWordMain > Stampa... > Quick Print
#### non_associato

- `Delete`: QuickWordMain > Strumenti > Delete
- `Insert Column`: QuickWordMain > Strumenti > Insert Column
- `Insert Row`: QuickWordMain > Strumenti > Insert Row
- `Select`: QuickWordMain > Strumenti > Select
- `Split`: QuickWordMain > Strumenti > Split
- `Symbol`: QuickWordMain > Symbols > Symbol
#### menu_contestuale

- `Grid Lines`: QuickWordMain > Tabella > Grid Lines
- `Insert Table`: QuickWordMain > Tabella > Insert Table
- `Inserisci_Metadato_AutovetturaTerzo`: QuickWordMain > Terzo > Inserisci Metadato AutovetturaTerzo
- `Inserisci_Metadato_CodiceFiscaleTerzo`: QuickWordMain > Terzo > Inserisci Metadato CodiceFiscaleTerzo
- `Inserisci_Metadato_DataLuogoCostituzioneNascita_Terzo`: QuickWordMain > Terzo > Inserisci Metadato DataLuogoCostituzioneNascita Terzo
- `Inserisci_Metadato_EmailTerzo`: QuickWordMain > Terzo > Inserisci Metadato EmailTerzo
- `Inserisci_Metadato_NomeIndirizzoTerzo`: QuickWordMain > Terzo > Inserisci Metadato NomeIndirizzoTerzo
- `Inserisci_Metadato_NomeTerzo`: QuickWordMain > Terzo > Inserisci Metadato NomeTerzo
- `Inserisci_Metadato_PartitaIVATerzo`: QuickWordMain > Terzo > Inserisci Metadato PartitaIVATerzo
- `Inserisci_Metadato_TelefonoTerzo`: QuickWordMain > Terzo > Inserisci Metadato TelefonoTerzo
- `Inserisci_Metadato_AutovetturaTestimone`: QuickWordMain > Testimone > Inserisci Metadato AutovetturaTestimone
- `Inserisci_Metadato_CodiceFiscaleTestimone`: QuickWordMain > Testimone > Inserisci Metadato CodiceFiscaleTestimone
- `Inserisci_Metadato_DataLuogoCostituzioneNascita_Testimone`: QuickWordMain > Testimone > Inserisci Metadato DataLuogoCostituzioneNascita Testimone
- `Inserisci_Metadato_EmailTestimone`: QuickWordMain > Testimone > Inserisci Metadato EmailTestimone
- `Inserisci_Metadato_NomeIndirizzoTestimone`: QuickWordMain > Testimone > Inserisci Metadato NomeIndirizzoTestimone
- `Inserisci_Metadato_NomeTestimone`: QuickWordMain > Testimone > Inserisci Metadato NomeTestimone
- `Inserisci_Metadato_PartitaIVATestimone`: QuickWordMain > Testimone > Inserisci Metadato PartitaIVATestimone
- `Inserisci_Metadato_TelefonoTestimone`: QuickWordMain > Testimone > Inserisci Metadato TelefonoTestimone
#### non_associato

- `Dati`: QuickWordMain > Text > Dati
- `Dettatura`: QuickWordMain > Text > Dettatura
- `Text Box`: QuickWordMain > Text > Text Box
#### menu_contestuale

- `Inserisci_Metadato_DataPenultimaUdienza`: QuickWordMain > Udienze > Inserisci Metadato DataPenultimaUdienza
- `Inserisci_Metadato_DataProssimaUdienza`: QuickWordMain > Udienze > Inserisci Metadato DataProssimaUdienza
- `Inserisci_Metadato_DataUltimaUdienza`: QuickWordMain > Udienze > Inserisci Metadato DataUltimaUdienza
- `Inserisci_Metadato_MotivoPenultimaUdienza`: QuickWordMain > Udienze > Inserisci Metadato MotivoPenultimaUdienza
- `Inserisci_Metadato_MotivoProssimaUdienza`: QuickWordMain > Udienze > Inserisci Metadato MotivoProssimaUdienza
- `Inserisci_Metadato_MotivoUltimaUdienza`: QuickWordMain > Udienze > Inserisci Metadato MotivoUltimaUdienza
- `Inserisci_Metadato_OrarioPenultimaUdienza`: QuickWordMain > Udienze > Inserisci Metadato OrarioPenultimaUdienza
- `Inserisci_Metadato_OrarioProssimaUdienza`: QuickWordMain > Udienze > Inserisci Metadato OrarioProssimaUdienza
- `Inserisci_Metadato_OrarioUltimaUdienza`: QuickWordMain > Udienze > Inserisci Metadato OrarioUltimaUdienza
- `Inserisci_Metadato_ResocontoPenultimaUdienza`: QuickWordMain > Udienze > Inserisci Metadato ResocontoPenultimaUdienza
- `Inserisci_Metadato_ResocontoUdienza`: QuickWordMain > Udienze > Inserisci Metadato ResocontoUdienza
- `Double`: QuickWordMain > UnderlineStyles > Double
- `DoubledWordsOnly`: QuickWordMain > UnderlineStyles > DoubledWordsOnly
- `Single`: QuickWordMain > UnderlineStyles > Single
- `SingleWordsOnly`: QuickWordMain > UnderlineStyles > SingleWordsOnly
#### non_associato

- `Help_Metadati`: QuickWordMain > Utilità > Help Metadati
#### menu_contestuale

- `cmdChkZoom_025`: QuickWordMain > Zoom > cmdChkZoom 025
- `cmdChkZoom_050`: QuickWordMain > Zoom > cmdChkZoom 050
- `cmdChkZoom_075`: QuickWordMain > Zoom > cmdChkZoom 075
- `cmdChkZoom_100`: QuickWordMain > Zoom > cmdChkZoom 100
- `cmdChkZoom_150`: QuickWordMain > Zoom > cmdChkZoom 150
- `cmdChkZoom_200`: QuickWordMain > Zoom > cmdChkZoom 200
- `cmdChkZoom_400`: QuickWordMain > Zoom > cmdChkZoom 400

## Controlli delle finestre

### FormSentMailBee

Sorgente: `FormSentMailBee.cs`

- `btnCaricaMessaggioDaFormulario.Click -> btnCaricaMessaggioDaFormulario_Click`: FormSentMailBee > (*) Carica dal formulario
- `btbBrowseMittente.Click -> btbBrowseMittente_Click`: FormSentMailBee > ...
- `btnIndietro.Click -> btnIndietro_Click`: FormSentMailBee > <  Indietro
- `btnInizioPannelloDepositiTelematici.Click -> btnInizioPannelloDepositiTelematici_Click`: FormSentMailBee > <<  Inizio
- `btnInizio.Click -> btnInizio_Click`: FormSentMailBee > <<  Inizio
- `btnAllegaDepositoTelematico.Click -> btnAllegaDepositoTelematico_Click`: FormSentMailBee > Aggiungi
- `btnAggiungiTerzo.Click -> btnAggiungiTerzo_Click`: FormSentMailBee > Aggiungi
- `btnAggiungiControparte.Click -> btnAggiungiControparte_Click`: FormSentMailBee > Aggiungi
- `btnAggiungiCliente.Click -> btnAggiungiCliente_Click`: FormSentMailBee > Aggiungi
- `btnAggiungiMotivoCassazione.Click -> btnAggiungiMotivoCassazione_Click`: FormSentMailBee > Aggiungi
- `btnAggiungiSanzioniGDP.Click -> btnAggiungiSanzioniGDP_Click`: FormSentMailBee > Aggiungi
- `btnCoDifesori.Click -> btnCoDifesori_Click`: FormSentMailBee > Aggiungi Co-Difensore
- `btnScannerAltriDocumentiDaDepositare.Click -> btnScannerAltriDocumentiDaDepositare_Click`: FormSentMailBee > Aggiungi da scanner
- `btnIncludiEventualeProcura.Click -> btnIncludiEventualeProcura_Click`: FormSentMailBee > Allega
- `btnAllega.Click -> btnAllega_Click`: FormSentMailBee > Allega
- `btnChiudi.Click -> btnChiudi_Click`: FormSentMailBee > Annulla
- `btnAnnulla.Click -> btnAnnulla_Click`: FormSentMailBee > Annulla
- `btnAnnullaDepositoTelematico.Click -> btnAnnullaDepositoTelematico_Click`: FormSentMailBee > Annulla
- `btnArchivia.Click -> btnArchivia_Click`: FormSentMailBee > Archivia
- `Attachments.DoubleClick -> Attachments_DoubleClick`: FormSentMailBee > Attachments
- `btnAvanti.Click -> btnAvanti_Click`: FormSentMailBee > Avanti  >
- `btnBozze.Click -> btnBozze_Click`: FormSentMailBee > Bozze
- `btnAppuntiPratica.Click -> btnAppuntiPratica_Click`: FormSentMailBee > btnAppuntiPratica
- `btnConnettiRiceviPannelloDepositiTelematici.Click -> btnConnettiRiceviPannelloDepositiTelematici_Click`: FormSentMailBee > Connetti & Ricevi
- `ultraLabel78.Click -> ultraLabel78_Click`: FormSentMailBee > Data del testamento:
- `grpDatiProcedimento.Click -> grpDatiProcedimento_Click`: FormSentMailBee > Dati relativi al procedimento:
- `btnEliminaElencoAltriDocumenti.Click -> btnEliminaElencoAltriDocumenti_Click`: FormSentMailBee > Elimina
- `btnDeleteEventualeProcura.Click -> btnDeleteEventualeProcura_Click`: FormSentMailBee > Elimina
- `btnEliminaTerzo.Click -> btnEliminaTerzo_Click`: FormSentMailBee > Elimina
- `btnEliminaControparte.Click -> btnEliminaControparte_Click`: FormSentMailBee > Elimina
- `btnEliminaCliente.Click -> btnEliminaCliente_Click`: FormSentMailBee > Elimina
- `btnEliminaMotivoCassazione.Click -> btnEliminaMotivoCassazione_Click`: FormSentMailBee > Elimina
- `btnDeleteNotaIscrizioneRuolo.Click -> btnDeleteNotaIscrizioneRuolo_Click`: FormSentMailBee > Elimina
- `btnElimina.Click -> btnElimina_Click`: FormSentMailBee > Elimina
- `btnEmiminaSanzioniGDP.Click -> btnEmiminaSanzioniGDP_Click`: FormSentMailBee > Elimina
- `btnEstremiPagamentoSpeseGiustiziaNotifica_avvocati_art_34_tu.Click -> btnEstremiPagamentoSpeseGiustiziaNotifica_avvocati_art_34_tu_Click`: FormSentMailBee > Estremi di pagamento
- `btnEstremiPagamentoSpeseGiustiziaDiritti_registrazione_ruolo_tu_art_30.Click -> btnEstremiPagamentoSpeseGiustiziaDiritti_registrazione_ruolo_tu_art_30_Click`: FormSentMailBee > Estremi di pagamento
- `btnEstremiPagamentoSpeseGiustiziaIntegrazione_69_2009_art_13_co_2_bis_tu.Click -> btnEstremiPagamentoSpeseGiustiziaIntegrazione_69_2009_art_13_co_2_bis_tu_Click`: FormSentMailBee > Estremi di pagamento
- `btnEstremiPagamentoContributoUnificato.Click -> btnEstremiPagamentoContributoUnificato_Click`: FormSentMailBee > Estremi di pagamento
- `btnFirmaAllegato.Click -> btnFirmaAllegato_Click`: FormSentMailBee > Firma
- `btnGeneraNotaIscrizioneRuolo.Click -> btnGeneraNotaIscrizioneRuolo_Click`: FormSentMailBee > Genera
- `helpDragDrop.Click -> helpDragDrop_Click`: FormSentMailBee > Help
- `btnIncludi.Click -> btnIncludi_Click`: FormSentMailBee > Includi
- `btnIndiceDocumenti.Click -> btnIndiceDocumenti_Click`: FormSentMailBee > Indice Documenti
- `btnInviaDepositoPrincipale.Click -> btnInviaDepositoPrincipale_Click`: FormSentMailBee > Invia
- `buttonSendMail.Click -> buttonSendMail_Click`: FormSentMailBee > Invia
- `lblDN.Click -> lblDN_Click`: FormSentMailBee > lblDN
- `lblUP.Click -> lblUP_Click`: FormSentMailBee > lblUP
- `btnCondizioniUso.Click -> btnCondizioniUso_Click`: FormSentMailBee > Licenza d'uso
- `btnModificaTerzo.Click -> btnModificaTerzo_Click`: FormSentMailBee > Modifica
- `btnModificaControparte.Click -> btnModificaControparte_Click`: FormSentMailBee > Modifica
- `btnModificaCliente.Click -> btnModificaCliente_Click`: FormSentMailBee > Modifica
- `btnModificaMotivoCassazione.Click -> btnModificaMotivoCassazione_Click`: FormSentMailBee > Modifica
- `btnModificaSanzioniGDP.Click -> btnModificaSanzioniGDP_Click`: FormSentMailBee > Modifica
- `btnModificaRelata.Click -> btnModificaRelata_Click`: FormSentMailBee > Modifica Relata
- `btnRemove.Click -> btnRemove_Click`: FormSentMailBee > Rimuovi
- `btnScanner.Click -> btnScanner_Click`: FormSentMailBee > Scanner
- `btnScannerizza.Click -> btnScannerizza_Click`: FormSentMailBee > Scanner
- `btnSettingsPannelloDepositoTelematico.Click -> btnSettingsDepositoTelematico_Click`: FormSentMailBee > Settings
- `btnSettings.Click -> btnSettings_Click`: FormSentMailBee > Settings
- `btnSettingsDepositoTelematico.Click -> btnSettingsDepositoTelematico_Click`: FormSentMailBee > Settings
- `btnSostituisciTuttiMetadati.Click -> btnSostituisciTuttiMetadati_Click`: FormSentMailBee > Sostituisci tutti i metadati
- `UltraGridTerzi.Click -> UltraGridTerzi_Click`: FormSentMailBee > UltraGrid1
- `UltraGridControparti.Click -> UltraGridControparti_Click`: FormSentMailBee > UltraGrid1
- `UltraGridClienti.Click -> UltraGridClienti_Click`: FormSentMailBee > UltraGrid1
- `UltraGridDepositiComplementari.Click -> UltraGridDepositiComplementari_Click`: FormSentMailBee > UltraGridDepositiComplementari
- `UltraGridDepositoPrincipale.Click -> UltraGridDepositoPrincipale_Click`: FormSentMailBee > UltraGridDepositoPrincipale
- `UltraTabPageControl3.Click -> UltraTabPageControl3_Click`: FormSentMailBee > UltraTabPageControl3
- `btnVisualizzaAllegato.Click -> btnVisualizzaAllegato_Click`: FormSentMailBee > Vedi/Modifica
- `btnModificaEventualeProcura.Click -> btnModificaEventualeProcura_Click`: FormSentMailBee > Vedi/Modifica
- `btnModificaNotaIscrizioneRuolo.Click -> btnModificaNotaIscrizioneRuolo_Click`: FormSentMailBee > Vedi/Modifica
- `btnVedi.Click -> btnVedi_Click`: FormSentMailBee > Visualizza
### Privacy

Sorgente: `QuickOrganizer.UserControls/Privacy.cs`

- `btnAggiungiUser.Click -> btnAggiungiUser_Click`: Privacy > Aggiungi
- `btnEliminaLog.Click -> btnEliminaLog_Click`: Privacy > Elimina
- `btnEliminaUser.Click -> btnEliminaUser_Click`: Privacy > Elimina
- `btnLogin.Click -> btnLogin_Click`: Privacy > Login
- `btnModificaUser.Click -> btnModificaUser_Click`: Privacy > Modifica
- `btnStampa.Click -> btnStampa_Click`: Privacy > Stampa
### UserControlHome

Sorgente: `QuickOrganizer.UserControls/UserControlHome.cs`

- `btnAgenda.Click -> btnAgenda_Click`: UserControlHome > Agenda
- `ultraButton3.Click -> ultraButton3_Click`: UserControlHome > Albo avvocati (CNF)
- `btnAnagrafica.Click -> btnAnagrafica_Click`: UserControlHome > Anagrafica
- `ultraButton2.Click -> ultraButton2_Click`: UserControlHome > Cassa Forense
- `btnGraficoPerMateria.Click -> btnGraficoPerMateria_Click`: UserControlHome > Clicca qui per vedere il grafico delle pratiche attive
- `btnEmail.Click -> btnEmail_Click`: UserControlHome > Email
- `btnFatture.Click -> btnFatture_Click`: UserControlHome > Fatture
- `ultraButton5.Click -> ultraButton5_Click`: UserControlHome > Fatture & Corrispettivi
- `ultraButton1.Click -> ultraButton1_Click_1`: UserControlHome > Gazzetta Ufficiale
- `btnMovimentazioni.Click -> btnMovimentazioni_Click`: UserControlHome > Movimenti
- `btnPoliswebNews.Click -> btnPoliswebNews_Click`: UserControlHome > Notiziario...
- `btnRubrica.Click -> btnRubrica_Click`: UserControlHome > Rubrica
- `btnStrumenti.Click -> btnStrumenti_Click`: UserControlHome > Strumenti
- `btnVideoscrittura.Click -> btnVideoscrittura_Click`: UserControlHome > Videoscrittura
### UserControlStrumenti

Sorgente: `QuickOrganizer.UserControls/UserControlStrumenti.cs`

- `btnAggiornamentoServiziTelematici.Click -> btnAggiornamentoServiziTelematici_Click`: UserControlStrumenti > Aggiornamento PCT
- `btcCalcoloCodiceFiscale.Click -> btcCalcoloCodiceFiscale_Click`: UserControlStrumenti > Calcolo Codice Fiscale
- `btnCompattazione.Click -> btnCompattazione_Click`: UserControlStrumenti > Compattazione degli Archivi
- `btnComputoTermini.Click -> btnComputoTermini_Click`: UserControlStrumenti > Computo dei Termini
- `btnConfigurazionePEC.Click -> btnConfigurazionePEC_Click`: UserControlStrumenti > Configurazione della PEC
- `btnConfigrazioneRete.Click -> btnConfigrazioneRete_Click`: UserControlStrumenti > Configurazione di Rete
- `btnGoogleCalendar.Click -> btnGoogleCalendar_Click`: UserControlStrumenti > Google Calendar
- `btnColorScheme.Click -> btnColorScheme_Click`: UserControlStrumenti > Interfaccia del Programma
- `btnSincronizzaPostaInArrivo.Click -> btnSincronizzaPostaInArrivo_Click`: UserControlStrumenti > Manutenzione Posta in Arrivo
- `btnPrivacy.Click -> btnPrivacy_Click`: UserControlStrumenti > Privacy
- `btnProfilotente.Click -> btnProfilotente_Click`: UserControlStrumenti > Profilo Utente (Licenza d'uso)
- `btnSviluppoMacro.Click -> btnSviluppoMacro_Click`: UserControlStrumenti > Programmaz. Macro
- `btnRipristinoDati.Click -> btnRipristinoDati_Click`: UserControlStrumenti > Ripristino dati (Restore)
- `btnSalvataggioDati.Click -> btnSalvataggioDati_Click`: UserControlStrumenti > Salvataggio dati (Backup)
- `btnScannerMultipagina.Click -> btnScannerMultipagina_Click`: UserControlStrumenti > Scanner Multipagina
- `btnSceltaWP.Click -> btnSceltaWP_Click`: UserControlStrumenti > Scelta WP
- `btnScorporo.Click -> btnScorporo_Click`: UserControlStrumenti > Scorporo dell'imposta
- `btnTariffarioPersonale.Click -> btnTariffarioPersonale_Click`: UserControlStrumenti > Tariffario Personale
- `btnTestSmartCard.Click -> btnTestSmartCard_Click`: UserControlStrumenti > Test della Smart Card
- `btnUnisciPDF.Click -> btnUnisciPDF_Click`: UserControlStrumenti > Unisci PDF in unico file
### Backup

Sorgente: `QuickOrganizer/Backup.cs`

- `btnCancel.Click -> btnCancel_Click`: Backup > Annulla
- `btnOk.Click -> btnOk_Click`: Backup > Inizia Backup!
- `btnBrowseOldBackup.Click -> btnBrowseOldBackup_Click`: Backup > Sfoglia...
### Compattazione

Sorgente: `QuickOrganizer/Compattazione.cs`

- `btnOK.Click -> btnOK_Click`: Compattazione > Compatta
### DataRinvioDialog

Sorgente: `QuickOrganizer/DataRinvioDialog.cs`

- `BtnOK.Click -> BtnOK_Click`: DataRinvioDialog > &OK
### DatabasePath

Sorgente: `QuickOrganizer/DatabasePath.cs`

- `btnOK.Click -> btnOK_Click`: DatabasePath > Salva & Chiudi
- `btnBrowse.Click -> btnBrowse_Click`: DatabasePath > Sfoglia...
### DocumentiBook

Sorgente: `QuickOrganizer/DocumentiBook.cs`

- `btnOK.Click -> btnOK_Click`: DocumentiBook > OK
- `cmdFindNext.Click -> cmdFindNext_Click`: DocumentiBook > Trova successivo
### DotNetTwain

Sorgente: `QuickOrganizer/DotNetTwain.cs`

- `lbLoadImageBar.Click -> lbLoadImageBar_Click`: DotNetTwain > Carica Immagini
- `lbCloseAnnotations.Click -> lbCloseAnnotations_Click`: DotNetTwain > CLOSE
- `picboxCrop.Click -> picboxCrop_Click`: DotNetTwain > picboxCrop
- `picboxDelete.Click -> picboxDelete_Click`: DotNetTwain > picboxDelete
- `picboxDeleteAll.Click -> picboxDeleteAll_Click`: DotNetTwain > picboxDeleteAll
- `picboxDeleteAnnotationA.Click -> picboxDeleteAnnotationA_Click`: DotNetTwain > picboxDeleteAnnotationA
- `picboxEllipse.Click -> picboxEllipse_Click`: DotNetTwain > picboxEllipse
- `picboxEllipseA.Click -> picboxEllipse_Click`: DotNetTwain > picboxEllipseA
- `picboxFirst.Click -> picboxFirst_Click`: DotNetTwain > picboxFirst
- `picboxFlip.Click -> picboxFlip_Click`: DotNetTwain > picboxFlip
- `picboxHand.Click -> picboxHand_Click`: DotNetTwain > picboxHand
- `picboxLast.Click -> picboxLast_Click`: DotNetTwain > picboxLast
- `picboxLine.Click -> picboxLine_Click`: DotNetTwain > picboxLine
- `picboxLineA.Click -> picboxLine_Click`: DotNetTwain > picboxLineA
- `picboxLoadImage.Click -> picboxLoadImage_Click`: DotNetTwain > picboxLoadImage
- `picboxMin.Click -> picboxMin_Click`: DotNetTwain > picboxMin
- `picboxMirror.Click -> picboxMirror_Click`: DotNetTwain > picboxMirror
- `picboxNext.Click -> picboxNext_Click`: DotNetTwain > picboxNext
- `picboxPoint.Click -> picboxPoint_Click`: DotNetTwain > picboxPoint
- `picboxPrevious.Click -> picboxPrevious_Click`: DotNetTwain > picboxPrevious
- `picboxRectangle.Click -> picboxRectangle_Click`: DotNetTwain > picboxRectangle
- `picboxRectangleA.Click -> picboxRectangle_Click`: DotNetTwain > picboxRectangleA
- `picboxResample.Click -> picboxResample_Click`: DotNetTwain > picboxResample
- `picboxRotate.Click -> picboxRotate_Click`: DotNetTwain > picboxRotate
- `picboxRotateLeft.Click -> picboxRotateLeft_Click`: DotNetTwain > picboxRotateLeft
- `picboxRotateRight.Click -> picboxRotateRight_Click`: DotNetTwain > picboxRotateRight
- `picboxSave.Click -> picboxSave_Click`: DotNetTwain > picboxSave
- `picboxScan.Click -> picboxScan_Click`: DotNetTwain > picboxScan
- `picboxText.Click -> picboxText_Click`: DotNetTwain > picboxText
- `picboxTextA.Click -> picboxText_Click`: DotNetTwain > picboxTextA
- `picboxZoom.Click -> picboxZoom_Click`: DotNetTwain > picboxZoom
- `picboxZoomIn.Click -> picboxZoomIn_Click`: DotNetTwain > picboxZoomIn
- `picboxZoomOut.Click -> picboxZoomOut_Click`: DotNetTwain > picboxZoomOut
- `lbTWAINSourceBar.Click -> lbTWAINSourceBar_Click`: DotNetTwain > SCANNER
### FattureAcquisto

Sorgente: `QuickOrganizer/FattureAcquisto.cs`

- `btnAppuntiPratica.Click -> btnAppuntiPratica_Click`: FattureAcquisto > btnAppuntiPratica
- `btnBrowseEventualeAllegato.Click -> btnBrowseEventualeAllegato_Click`: FattureAcquisto > btnBrowseEventualeAllegato
- `btnDeleteEventualeAllegato.Click -> btnDeleteEventualeAllegato_Click`: FattureAcquisto > btnDeleteEventualeAllegato
- `btnIncludiEventualeAllegato.Click -> btnIncludiEventualeAllegato_Click`: FattureAcquisto > btnIncludiEventualeAllegato
- `btnModificaEventualeAllegato.Click -> btnModificaEventualeAllegato_Click`: FattureAcquisto > btnModificaEventualeAllegato
- `btnElimina.Click -> btnElimina_Click`: FattureAcquisto > Elimina
- `lblControlloCodiceFiscale.Click -> lblControlloCodiceFiscale_Click`: FattureAcquisto > lblControlloCodiceFiscale
- `btnOK.Click -> btnOK_Click`: FattureAcquisto > Ok
- `btnScannerEventualeAllegato.Click -> btnScannerEventualeAllegato_Click`: FattureAcquisto > Scanner
### FindDateDialog

Sorgente: `QuickOrganizer/FindDateDialog.cs`

- `_btnOK.Click -> _btnOK_Click`: FindDateDialog > &OK
### FormAltriDifensori

Sorgente: `QuickOrganizer/FormAltriDifensori.cs`

- `_btnCancel.Click -> _btnCancel_Click`: FormAltriDifensori > Annulla
- `_btnOK.Click -> _btnOK_Click`: FormAltriDifensori > OK
### FormAttetazioniConformità

Sorgente: `QuickOrganizer/FormAttetazioniConformità.cs`

- `btnAggiungi.Click -> btnAggiungi_Click`: FormAttetazioniConformità > Aggiungi
- `btnCancel.Click -> btnCancel_Click`: FormAttetazioniConformità > Annulla
- `btnAnteprima.Click -> btnAnteprima_Click`: FormAttetazioniConformità > Anteprima
- `lblDN.Click -> LblDN_Click`: FormAttetazioniConformità > lblDN
- `lblUP.Click -> LblUP_Click`: FormAttetazioniConformità > lblUP
- `btnModifica.Click -> button1_Click`: FormAttetazioniConformità > Modifica
- `btnOK.Click -> btnOK_Click`: FormAttetazioniConformità > OK
- `btnRemove.Click -> btnRemove_Click_1`: FormAttetazioniConformità > Rimuovi
- `btnVedi.Click -> btnVedi_Click`: FormAttetazioniConformità > Visualizza
### FormCodiceFiscale

Sorgente: `QuickOrganizer/FormCodiceFiscale.cs`

- `btnCalcola.Click -> btnCalcola_Click`: FormCodiceFiscale > Calcola
- `btnMemorizza.Click -> btnMemorizza_Click`: FormCodiceFiscale > Memorizza
### FormComprimiFiles

Sorgente: `QuickOrganizer/FormComprimiFiles.cs`

- `btnAllega.Click -> btnAllega_Click_1`: FormComprimiFiles > Allega
- `btnCancel.Click -> btnCancel_Click`: FormComprimiFiles > Annulla
- `btnIncludi.Click -> btnIncludi_Click`: FormComprimiFiles > Includi
- `lblDN.Click -> LblDN_Click`: FormComprimiFiles > lblDN
- `lblUP.Click -> LblUP_Click`: FormComprimiFiles > lblUP
- `btnOK.Click -> btnOK_Click`: FormComprimiFiles > OK
- `btnRemove.Click -> btnRemove_Click_1`: FormComprimiFiles > Rimuovi
- `btnScannerizza.Click -> btnScannerizza_Click`: FormComprimiFiles > Scanner
- `btnVedi.Click -> btnVedi_Click`: FormComprimiFiles > Visualizza
### FormComputoTermini

Sorgente: `QuickOrganizer/FormComputoTermini.cs`

- `btnChiudi.Click -> btnChiudi_Click`: FormComputoTermini > Annulla
- `ultraButton1.Click -> ultraButton1_Click`: FormComputoTermini > Calcola data finale >>
- `cmdMemorizza.Click -> cmdMemorizza_Click`: FormComputoTermini > Memorizza
### FormCountDown

Sorgente: `QuickOrganizer/FormCountDown.cs`

- `btnAcquista.Click -> btnAcquista_Click`: FormCountDown > Acquista
- `btnChiudi.Click -> btnChiudi_Click`: FormCountDown > Chiudi
- `btnSerialKey.Click -> btnSerialKey_Click`: FormCountDown > Profilo Utente
- `label9.Click -> label9_Click`: FormCountDown > Studio Legale Telematico
### FormDepositaConSoftwareEsterno

Sorgente: `QuickOrganizer/FormDepositaConSoftwareEsterno.cs`

- `btnIncludi.Click -> btnIncludi_Click`: FormDepositaConSoftwareEsterno > Aggiungi
- `btnCancel.Click -> btnCancel_Click`: FormDepositaConSoftwareEsterno > Annulla
- `lblDN.Click -> LblDN_Click`: FormDepositaConSoftwareEsterno > lblDN
- `lblUP.Click -> LblUP_Click`: FormDepositaConSoftwareEsterno > lblUP
- `btnOK.Click -> btnOK_Click`: FormDepositaConSoftwareEsterno > OK
- `btnRemove.Click -> btnRemove_Click_1`: FormDepositaConSoftwareEsterno > Rimuovi
- `btnVedi.Click -> btnVedi_Click`: FormDepositaConSoftwareEsterno > Visualizza
### FormEstremiMatrimonio

Sorgente: `QuickOrganizer/FormEstremiMatrimonio.cs`

- `_btnCancel.Click -> _btnCancel_Click`: FormEstremiMatrimonio > Annulla
- `_btnOK.Click -> _btnOK_Click`: FormEstremiMatrimonio > OK
### FormEstremiPagamentoBollettinoPostale

Sorgente: `QuickOrganizer/FormEstremiPagamentoBollettinoPostale.cs`

- `btnDeleteRicevutaTelematica.Click -> btnDeleteRicevutaTelematica_Click`: FormEstremiPagamentoBollettinoPostale > 8
- `_btnCancel.Click -> _btnCancel_Click`: FormEstremiPagamentoBollettinoPostale > Annulla
- `btnIncludiRicevutaTelematica.Click -> btnIncludiRicevutaTelematica_Click`: FormEstremiPagamentoBollettinoPostale > btnIncludiRicevutaTelematica
- `btnModificaRicevutaTelematica.Click -> btnModificaRicevutaTelematica_Click`: FormEstremiPagamentoBollettinoPostale > btnModificaRicevutaTelematica
- `_btnOK.Click -> _btnOK_Click`: FormEstremiPagamentoBollettinoPostale > OK
- `btnScannerRicevutaTelematica.Click -> btnScannerRicevutaTelematica_Click`: FormEstremiPagamentoBollettinoPostale > Scanner
### FormEstremiPagamentoF23

Sorgente: `QuickOrganizer/FormEstremiPagamentoF23.cs`

- `btnDeleteRicevutaTelematica.Click -> btnDeleteRicevutaTelematica_Click`: FormEstremiPagamentoF23 > 8
- `_btnCancel.Click -> _btnCancel_Click`: FormEstremiPagamentoF23 > Annulla
- `btnIncludiRicevutaTelematica.Click -> btnIncludiRicevutaTelematica_Click`: FormEstremiPagamentoF23 > btnIncludiRicevutaTelematica
- `btnModificaRicevutaTelematica.Click -> btnModificaRicevutaTelematica_Click`: FormEstremiPagamentoF23 > btnModificaRicevutaTelematica
- `_btnOK.Click -> _btnOK_Click`: FormEstremiPagamentoF23 > OK
- `btnScannerRicevutaTelematica.Click -> btnScannerRicevutaTelematica_Click`: FormEstremiPagamentoF23 > Scanner
### FormEstremiPagamentoRicevutaTelematica

Sorgente: `QuickOrganizer/FormEstremiPagamentoRicevutaTelematica.cs`

- `_btnCancel.Click -> _btnCancel_Click`: FormEstremiPagamentoRicevutaTelematica > Annulla
- `btnDeleteRicevutaTelematica.Click -> btnDeleteRicevutaTelematica_Click`: FormEstremiPagamentoRicevutaTelematica > btnDeleteRicevutaTelematica
- `btnIncludiRicevutaTelematica.Click -> btnIncludiRicevutaTelematica_Click`: FormEstremiPagamentoRicevutaTelematica > btnIncludiRicevutaTelematica
- `btnModificaRicevutaTelematica.Click -> btnModificaRicevutaTelematica_Click`: FormEstremiPagamentoRicevutaTelematica > btnModificaRicevutaTelematica
- `_btnOK.Click -> _btnOK_Click`: FormEstremiPagamentoRicevutaTelematica > OK
### FormEstremiPagamentosingolaMarca

Sorgente: `QuickOrganizer/FormEstremiPagamentosingolaMarca.cs`

- `_btnCancel.Click -> _btnCancel_Click`: FormEstremiPagamentosingolaMarca > Annulla
- `_btnOK.Click -> _btnOK_Click`: FormEstremiPagamentosingolaMarca > OK
### FormFilterComboDialog

Sorgente: `QuickOrganizer/FormFilterComboDialog.cs`

- `_btnOK.Click -> _btnOK_Click`: FormFilterComboDialog > &OK
### FormFirmaAllegato

Sorgente: `QuickOrganizer/FormFirmaAllegato.cs`

- `cmdAnnulla.Click -> cmdAnnulla_Click`: FormFirmaAllegato > &Annulla
- `cmdNO.Click -> cmdNO_Click`: FormFirmaAllegato > &No
- `cmdSI.Click -> cmdSI_Click`: FormFirmaAllegato > &Si
### FormHash

Sorgente: `QuickOrganizer/FormHash.cs`

- `cmdCancel.Click -> cmdCancel_Click`: FormHash > &Annulla
- `cmdOK.Click -> cmdOK_Click`: FormHash > &OK
### FormMain

Sorgente: `QuickOrganizer/FormMain.cs`

- `btnPagerAvanti.Click -> btnPagerAvanti_Click`: FormMain > btnPagerAvanti
- `btnPagerEnd.Click -> btnPagerEnd_Click`: FormMain > btnPagerEnd
- `btnPagerIndietro.Click -> btnPagerIndietro_Click`: FormMain > btnPagerIndietro
- `btnPagerStart.Click -> btnPagerStart_Click`: FormMain > btnPagerStart
- `GridSociCollaboratoriAgenda.Click -> GridSociCollaboratori_Click`: FormMain > GridSociCollaboratoriAgenda
- `TimeLineAgenda.Click -> TimeLineAgenda_Click`: FormMain > TimeLineAgenda
- `TimeLineAgenda.DoubleClick -> TimeLineAgenda_DoubleClick`: FormMain > TimeLineAgenda
- `btnTutte.Click -> btnTutte_Click`: FormMain > Tutte
- `TxAgenda.Click -> TxAgenda_Click`: FormMain > TxAgenda
- `TxRubrica.Click -> TxRubrica_Click`: FormMain > TxRubrica
- `TxRubrica.DoubleClick -> TxRubrica_DoubleClick`: FormMain > TxRubrica
- `TxSchedario.Click -> TxSchedario_Click`: FormMain > TxSchedario
- `TxSchedario.DoubleClick -> TxSchedario_DoubleClick`: FormMain > TxSchedario
- `TxVideoscrittura.Click -> TxVideoscrittura_Click`: FormMain > TxVideoscrittura
- `TxVideoscrittura.DoubleClick -> TxVideoscrittura_DoubleClick`: FormMain > TxVideoscrittura
- `UltraStatusBar.ButtonClick -> UltraStatusBar_ButtonClick`: FormMain > UltraStatusBar
### FormModificaCredenziali

Sorgente: `QuickOrganizer/FormModificaCredenziali.cs`

- `btnAnnulla.Click -> btnAnnulla_Click`: FormModificaCredenziali > Annulla
- `btnConferma.Click -> btnConferma_Click`: FormModificaCredenziali > Conferma
### FormMotivoRicorsoCassazione

Sorgente: `QuickOrganizer/FormMotivoRicorsoCassazione.cs`

- `btnAggingiNormaViolata.Click -> btnAggingiNormaViolata_Click`: FormMotivoRicorsoCassazione > btnAggingiNormaViolata
- `btnModificaNormaViolata.Click -> btnModificaNormaViolata_Click`: FormMotivoRicorsoCassazione > btnModificaNormaViolata
- `btnOK.Click -> btnOK_Click`: FormMotivoRicorsoCassazione > Ok
### FormQualeAllegato

Sorgente: `QuickOrganizer/FormQualeAllegato.cs`

- `BtnCancel.Click -> BtnCancel_Click`: FormQualeAllegato > Annulla
- `BtnOK.Click -> BtnOK_Click`: FormQualeAllegato > Salva & Chiudi
- `btnSalvaContinua.Click -> btnSalvaContinua_Click`: FormQualeAllegato > Salva & Continua
- `ultraTree1.DoubleClick -> ultraTree1_DoubleClick`: FormQualeAllegato > ultraTree1
### FormQualeScarico

Sorgente: `QuickOrganizer/FormQualeScarico.cs`

- `btnOK.Click -> btnOK_Click`: FormQualeScarico > Ok
### FormQualificaGiudiziale

Sorgente: `QuickOrganizer/FormQualificaGiudiziale.cs`

- `_btnOK.Click -> _btnOK_Click`: FormQualificaGiudiziale > &OK
- `btnAnagrafica.Click -> btnAnagrafica_Click`: FormQualificaGiudiziale > Anagrafica
### FormRiferimentoNorme

Sorgente: `QuickOrganizer/FormRiferimentoNorme.cs`

- `lblHelp.Click -> lblHelp_Click`: FormRiferimentoNorme > (*) Llink ipertestuale permanente (es: vedi banca dati “Normattiva”)
- `btnOK.Click -> btnOK_Click`: FormRiferimentoNorme > Ok
### FormScorporo

Sorgente: `QuickOrganizer/FormScorporo.cs`

- `base.Click -> FormScorporo_Click`: FormScorporo > base
- `cmdCancel.Click -> cmdCancel_Click`: FormScorporo > Chiudi
- `label8.Click -> label8_Click`: FormScorporo > label8
- `cmdCalcola.Click -> cmdCalcola_Click`: FormScorporo > Memorizza
- `UltraCurrencyEditorSpeseEsenti.Click -> UltraCurrencyEditorSpeseEsenti_Click`: FormScorporo > UltraCurrencyEditorSpeseEsenti
- `UltraCurrencyEditorSpeseImponibili.Click -> UltraCurrencyEditorSpeseImponibili_Click`: FormScorporo > UltraCurrencyEditorSpeseImponibili
- `UltraCurrencyEditorTotaleDaOttenere.Click -> UltraCurrencyEditorTotaleDaOttenere_Click`: FormScorporo > UltraCurrencyEditorTotaleDaOttenere
### FormSearchCodiceOggetto

Sorgente: `QuickOrganizer/FormSearchCodiceOggetto.cs`

- `btnConferma.Click -> btnConferma_Click`: FormSearchCodiceOggetto > Conferma
- `cmdFindPrevious.Click -> cmdFindPrevious_Click`: FormSearchCodiceOggetto > Trova precedente
- `cmdFindNext.Click -> cmdFindNext_Click`: FormSearchCodiceOggetto > Trova successivo
### FormSearchInfo

Sorgente: `QuickOrganizer/FormSearchInfo.cs`

- `cmdCancel.Click -> cmdCancel_Click`: FormSearchInfo > Annulla
- `cmdFindPrevious.Click -> cmdFindPrevious_Click`: FormSearchInfo > Trova precedente
- `cmdFindNext.Click -> cmdFindNext_Click`: FormSearchInfo > Trova successivo
### FormTipoNotificaUNEP

Sorgente: `QuickOrganizer/FormTipoNotificaUNEP.cs`

- `_btnOK.Click -> _btnOK_Click`: FormTipoNotificaUNEP > &OK
### FormUnisciPDF

Sorgente: `QuickOrganizer/FormUnisciPDF.cs`

- `btnAllega.Click -> btnAllega_Click_1`: FormUnisciPDF > Allega
- `btnCancel.Click -> btnCancel_Click`: FormUnisciPDF > Annulla
- `btnIncludi.Click -> btnIncludi_Click`: FormUnisciPDF > Includi
- `lblDN.Click -> LblDN_Click`: FormUnisciPDF > lblDN
- `lblUP.Click -> LblUP_Click`: FormUnisciPDF > lblUP
- `btnOK.Click -> btnOK_Click`: FormUnisciPDF > OK
- `btnRemove.Click -> btnRemove_Click_1`: FormUnisciPDF > Rimuovi
- `btnScannerizza.Click -> btnScannerizza_Click`: FormUnisciPDF > Scanner
- `btnVedi.Click -> btnVedi_Click`: FormUnisciPDF > Visualizza
### FormVerbale

Sorgente: `QuickOrganizer/FormVerbale.cs`

- `btnOK.Click -> btnOK_Click`: FormVerbale > Ok
### FormVerificaFirmeDigitali

Sorgente: `QuickOrganizer/FormVerificaFirmeDigitali.cs`

- `btnOK.Click -> btnOK_Click`: FormVerificaFirmeDigitali > OK
- `btnStampa.Click -> btnStampa_Click`: FormVerificaFirmeDigitali > Stampa...
### FormWordCount

Sorgente: `QuickOrganizer/FormWordCount.cs`

- `_btnClose.Click -> _btnClose_Click`: FormWordCount > &Close
### GoogleCalendar

Sorgente: `QuickOrganizer/GoogleCalendar.cs`

- `btnAnnulla.Click -> btnAnnulla_Click`: GoogleCalendar > Annulla
- `btnOK.Click -> btnOK_Click`: GoogleCalendar > Ok
- `btnReset.Click -> btnReset_Click`: GoogleCalendar > Reset
- `btnSincronizza.Click -> btnTrasferisci_Click`: GoogleCalendar > Trasferisci
### InfragisticsStatusBar

Sorgente: `QuickOrganizer/InfragisticsStatusBar.cs`

- `_usbUltraStatusBar.ButtonClick -> _usbUltraStatusBar_ButtonClick`: InfragisticsStatusBar > usbUltraStatusBar
### LicenzaUsoDepostoTelematico

Sorgente: `QuickOrganizer/LicenzaUsoDepostoTelematico.cs`

- `btnOK.Click -> btnOK_Click`: LicenzaUsoDepostoTelematico > OK
### NotificaEsito

Sorgente: `QuickOrganizer/NotificaEsito.cs`

- `btnCancel.Click -> btnCancel_Click`: NotificaEsito > Annulla
- `btnInvia.Click -> btnInvia_Click`: NotificaEsito > Invia risposta al Sistema d'Interscambio
### NuovoTariffarioPersonale

Sorgente: `QuickOrganizer/NuovoTariffarioPersonale.cs`

- `btnAggiungi.Click -> btnAggiungi_Click`: NuovoTariffarioPersonale > Aggiungi
- `btnCancel.Click -> btnCancel_Click`: NuovoTariffarioPersonale > Annulla
- `btnCondizioniGeneraliDiContratto.Click -> btnCondizioniGeneraliDiContratto_Click`: NuovoTariffarioPersonale > Condizioni Generali di Contratto
- `btnElimina.Click -> btnElimina_Click`: NuovoTariffarioPersonale > Elimina
- `btnOK.Click -> btnOK_Click`: NuovoTariffarioPersonale > Ok
- `btnStampa.Click -> btnStampa_Click`: NuovoTariffarioPersonale > STAMPA
### ParametriNuovoTariffario

Sorgente: `QuickOrganizer/ParametriNuovoTariffario.cs`

- `btnCancel.Click -> btnCancel_Click`: ParametriNuovoTariffario > Annulla
- `btnOK.Click -> btnOK_Click`: ParametriNuovoTariffario > Ok
### ParametriParcella

Sorgente: `QuickOrganizer/ParametriParcella.cs`

- `btnCancel.Click -> btnCancel_Click`: ParametriParcella > Annulla
- `btnPredefiniti.Click -> btnPredefiniti_Click`: ParametriParcella > Imposta come predefiniti
- `btnOK.Click -> btnOK_Click`: ParametriParcella > Ok
- `UltraGroupBox3.Click -> UltraGroupBox3_Click`: ParametriParcella > Ritenuta d'acconto:
### PoliswebRole

Sorgente: `QuickOrganizer/PoliswebRole.cs`

- `btnAggiungiOwner.Click -> btnAggiungiOwner_Click`: PoliswebRole > btnAggiungiOwner
- `btnOK.Click -> btnOK_Click`: PoliswebRole > Ok
### QualeModificaContabilità

Sorgente: `QuickOrganizer/QualeModificaContabilità.cs`

- `btnOK.Click -> btnOK_Click`: QualeModificaContabilità > Ok
### QualeParcella

Sorgente: `QuickOrganizer/QualeParcella.cs`

- `btnOK.Click -> btnOK_Click`: QualeParcella > Ok
### QualeParcellaNotaSpese

Sorgente: `QuickOrganizer/QualeParcellaNotaSpese.cs`

- `btnOK.Click -> btnOK_Click`: QualeParcellaNotaSpese > Ok
### QualeSchedario

Sorgente: `QuickOrganizer/QualeSchedario.cs`

- `btnOK.Click -> btnOK_Click`: QualeSchedario > Ok
### QualeVideoscrittura

Sorgente: `QuickOrganizer/QualeVideoscrittura.cs`

- `btnOK.Click -> btnOK_Click`: QualeVideoscrittura > Ok
### QualifiedCertificate

Sorgente: `QuickOrganizer/QualifiedCertificate.cs`

- `btnAnnulla.Click -> btnAnnulla_Click`: QualifiedCertificate > Annulla
- `btnOK.Click -> btnOK_Click`: QualifiedCertificate > OK
- `help.Click -> help_Click`: QualifiedCertificate > Premi il pulsante per Help
- `btnFormulario.Click -> btnFormulario_Click`: QualifiedCertificate > Questo pulsante consente di recuperare l'Attestazione di conformità dal "Formulario utente" (vedi videoscrittura).
- `btnSostituisciTuttiMetadati.Click -> btnSostituisciTuttiMetadati_Click`: QualifiedCertificate > Questo pulsante consente di sostituire tutti i metadati  eventualmente presenti in un'attestazione di conformità.
- `btnAggiornaCertificato.Click -> btnAggiornaCertificato_Click`: QualifiedCertificate > Seleziona
### ResampleForm

Sorgente: `QuickOrganizer/ResampleForm.cs`

- `btnCancel.Click -> btnCancel_Click`: ResampleForm > Cancel
- `btnOk.Click -> btnOk_Click`: ResampleForm > OK
### Restore

Sorgente: `QuickOrganizer/Restore.cs`

- `btnCancel.Click -> btnCancel_Click`: Restore > Annulla
- `btnOK.Click -> btnOK_Click`: Restore > Inizia Ripristino!
- `btbBrowseNuovoQuick.Click -> btbBrowseNuovoQuick_Click`: Restore > Sfoglia...
- `btnBrowseVecchioQuick.Click -> btnBrowseVecchioQuick_Click`: Restore > Sfoglia...
### RotateForm

Sorgente: `QuickOrganizer/RotateForm.cs`

- `btnCancel.Click -> btnCancel_Click`: RotateForm > Cancel
- `btnOK.Click -> btnOK_Click`: RotateForm > OK
### SchedaAgenda

Sorgente: `QuickOrganizer/SchedaAgenda.cs`

- `lblPersonalizzabile1.Click -> lblPersonalizzabile1_Click`: SchedaAgenda > Attività:
- `btnAppuntiPratica.Click -> btnAppuntiPratica_Click`: SchedaAgenda > btnAppuntiPratica
- `btnResoconto.Click -> btnResoconto_Click`: SchedaAgenda > btnResoconto
- `btnElimina.Click -> btnElimina_Click`: SchedaAgenda > Elimina
- `LblIconaComputoTermini.Click -> LblIconaComputoTermini_Click`: SchedaAgenda > LblIconaComputoTermini
- `btnOK.Click -> btnOK_Click`: SchedaAgenda > Ok
- `lblResoconto.Click -> lblResoconto_Click`: SchedaAgenda > Resoconto: dell'udienza...
- `btnRinvia.Click -> btnRinvia_Click`: SchedaAgenda > Rinvia
- `StarPersonalizzabile1.Click -> StarPersonalizzabile1_Click`: SchedaAgenda > StarPersonalizzabile1
### SchedaAllarme

Sorgente: `QuickOrganizer/SchedaAllarme.cs`

- `btnVediImpegno.Click -> btnVediImpegno_Click`: SchedaAllarme > btnVediImpegno
- `btnElimina.Click -> btnElimina_Click`: SchedaAllarme > Elimina Allarme
- `btnOK.Click -> btnOK_Click`: SchedaAllarme > Ok
### SchedaAnagrafica

Sorgente: `QuickOrganizer/SchedaAnagrafica.cs`

- `btnAggiungi.Click -> btnAggiungi_Click`: SchedaAnagrafica > Aggiungi
- `btnRemoveFoto.Click -> btnRemoveFoto_Click`: SchedaAnagrafica > btnRemoveFoto
- `btnDomicilio.Click -> btnDomicilio_Click`: SchedaAnagrafica > Domicilio
- `btnElimina.Click -> btnElimina_Click`: SchedaAnagrafica > Elimina
- `btnFoto.Click -> btnFoto_Click`: SchedaAnagrafica > Fotografia
- `lblControlloCodiceFiscale.Click -> lblControlloCodiceFiscale_Click`: SchedaAnagrafica > lblControlloCodiceFiscale
- `btnModifica.Click -> btnModifica_Click`: SchedaAnagrafica > Modifica
- `btnOK.Click -> btnOK_Click`: SchedaAnagrafica > Ok
- `lblPersonalizzabile1.Click -> lblPersonalizzabile1_Click`: SchedaAnagrafica > Personalizzabile1
- `lblPersonalizzabile2.Click -> lblPersonalizzabile2_Click`: SchedaAnagrafica > Personalizzabile2
- `pictureBox1.Click -> pictureBox1_Click`: SchedaAnagrafica > pictureBox1
- `btnImmigrazione.Click -> btnImmigrazione_Click`: SchedaAnagrafica > Scheda Immigrazione
- `StarPersonalizzabile1.Click -> StarPersonalizzabile1_Click`: SchedaAnagrafica > StarPersonalizzabile1
- `StarPersonalizzabile2.Click -> StarPersonalizzabile2_Click`: SchedaAnagrafica > StarPersonalizzabile2
### SchedaAnagraficaUtente

Sorgente: `QuickOrganizer/SchedaAnagraficaUtente.cs`

- `btnAcquista.Click -> btnAcquista_Click`: SchedaAnagraficaUtente > Acquista Licenza
- `btnCancel.Click -> btnCancel_Click`: SchedaAnagraficaUtente > Annulla
- `btnRemoveFoto.Click -> btnRemoveFoto_Click`: SchedaAnagraficaUtente > btnRemoveFoto
- `btnCaricaFileLicenza.Click -> btnCaricaFileLicenza_Click`: SchedaAnagraficaUtente > Carica Licenza
- `btnLogo.Click -> btnLogo_Click`: SchedaAnagraficaUtente > Logo
- `btnOK.Click -> btnOK_Click`: SchedaAnagraficaUtente > Ok
- `pictureBox1.Click -> pictureBox1_Click`: SchedaAnagraficaUtente > pictureBox1
- `btnReset.Click -> btnReset_Click`: SchedaAnagraficaUtente > Reset
### SchedaAppunti

Sorgente: `QuickOrganizer/SchedaAppunti.cs`

- `btnCancel.Click -> btnCancel_Click`: SchedaAppunti > Annulla
- `btnElimina.Click -> btnElimina_Click`: SchedaAppunti > Elimina
- `btnOK.Click -> btnOK_Click`: SchedaAppunti > Ok
- `btnStampa.Click -> btnStampa_Click`: SchedaAppunti > Stampa
### SchedaBeneImmobile

Sorgente: `QuickOrganizer/SchedaBeneImmobile.cs`

- `_btnCancel.Click -> _btnCancel_Click`: SchedaBeneImmobile > Annulla
- `btnAggiungiComproprietario.Click -> btnAggiungiComproprietario_Click`: SchedaBeneImmobile > btnAggiungiComproprietario
- `btnEliminaComproprietario.Click -> btnEliminaComproprietario_Click`: SchedaBeneImmobile > btnEliminaComproprietario
- `_btnOK.Click -> _btnOK_Click`: SchedaBeneImmobile > OK
- `btnDatiTavolari.Click -> btnDatiTavolari_Click`: SchedaBeneImmobile > Tavolari
- `UltraGroupBox2.Click -> UltraGroupBox2_Click`: SchedaBeneImmobile > UltraGroupBox2
### SchedaBeneMobile

Sorgente: `QuickOrganizer/SchedaBeneMobile.cs`

- `_btnCancel.Click -> _btnCancel_Click`: SchedaBeneMobile > Annulla
- `btnAggiungiComproprietario.Click -> btnAggiungiComproprietario_Click`: SchedaBeneMobile > btnAggiungiComproprietario
- `btnEliminaComproprietario.Click -> btnEliminaComproprietario_Click`: SchedaBeneMobile > btnEliminaComproprietario
- `_btnOK.Click -> _btnOK_Click`: SchedaBeneMobile > OK
### SchedaDatiTavolari

Sorgente: `QuickOrganizer/SchedaDatiTavolari.cs`

- `_btnCancel.Click -> _btnCancel_Click`: SchedaDatiTavolari > Annulla
- `_btnOK.Click -> _btnOK_Click`: SchedaDatiTavolari > OK
### SchedaDocumento

Sorgente: `QuickOrganizer/SchedaDocumento.cs`

- `btnAppuntiPratica.Click -> btnAppuntiPratica_Click`: SchedaDocumento > btnAppuntiPratica
- `btnMicrosoftWord.Click -> btnMicrosoftWord_Click`: SchedaDocumento > Microsoft Word
- `btnOpenOffice.Click -> btnOpenOffice_Click`: SchedaDocumento > Open Office
- `btnQuickWord.Click -> btnQuickWord_Click`: SchedaDocumento > Quick Word
- `btnElencoAttiDepositabili.Click -> btnElencoAttiDepositabili_Click`: SchedaDocumento > Vedi Elenco (*)
### SchedaDomicilio

Sorgente: `QuickOrganizer/SchedaDomicilio.cs`

- `_btnCancel.Click -> _btnCancel_Click`: SchedaDomicilio > Annulla
- `_btnOK.Click -> _btnOK_Click`: SchedaDomicilio > OK
### SchedaEmailRicevute

Sorgente: `QuickOrganizer/SchedaEmailRicevute.cs`

- `btnCancel.Click -> btnCancel_Click`: SchedaEmailRicevute > Annulla
- `btnAppuntiPratica.Click -> btnAppuntiPratica_Click`: SchedaEmailRicevute > btnAppuntiPratica
- `btnMemorandum.Click -> btnMemorandum_Click`: SchedaEmailRicevute > btnMemorandum
- `btnEsporta.Click -> btnEsporta_Click`: SchedaEmailRicevute > Esporta
- `btnOK.Click -> btnOK_Click`: SchedaEmailRicevute > Ok
- `btnRedirigi.Click -> btnRedirigi_Click`: SchedaEmailRicevute > Redirigi
- `btnRispondi.Click -> btnRispondi_Click`: SchedaEmailRicevute > Rispondi
- `btnStampa.Click -> btnStampa_Click`: SchedaEmailRicevute > Stampa
- `btnVediPratica.Click -> btnVediPratica_Click`: SchedaEmailRicevute > Vedi Pratica
### SchedaImmigrazione

Sorgente: `QuickOrganizer/SchedaImmigrazione.cs`

- `_btnCancel.Click -> _btnCancel_Click`: SchedaImmigrazione > Annulla
- `_btnOK.Click -> _btnOK_Click`: SchedaImmigrazione > OK
### SchedaIncassi

Sorgente: `QuickOrganizer/SchedaIncassi.cs`

- `btnOK.Click -> btnOK_Click`: SchedaIncassi > Ok
### SchedaIpoteca

Sorgente: `QuickOrganizer/SchedaIpoteca.cs`

- `_btnCancel.Click -> _btnCancel_Click`: SchedaIpoteca > Annulla
- `_btnOK.Click -> _btnOK_Click`: SchedaIpoteca > OK
### SchedaNotifica

Sorgente: `QuickOrganizer/SchedaNotifica.cs`

- `btnOK.Click -> btnOK_Click`: SchedaNotifica > Ok
- `btnStampa.Click -> btnStampa_Click`: SchedaNotifica > Stampa...
### SchedaOnorari

Sorgente: `QuickOrganizer/SchedaOnorari.cs`

- `btnAggiungi.Click -> btnAggiungi_Click`: SchedaOnorari > Aggiungi
- `btnCancel.Click -> btnCancel_Click_1`: SchedaOnorari > Annulla
- `btnElimina.Click -> btnElimina_Click`: SchedaOnorari > Elimina
- `btnModifica.Click -> btnModifica_Click`: SchedaOnorari > Modifica
- `btnOK.Click -> btnOK_Click_1`: SchedaOnorari > Ok
- `lblScorporo.Click -> lblScorporo_Click`: SchedaOnorari > Scorporo
### SchedaParcella

Sorgente: `QuickOrganizer/SchedaParcella.cs`

- `btnAppuntiPratica.Click -> btnAppuntiPratica_Click`: SchedaParcella > btnAppuntiPratica
- `btnBrowseEventualeAllegato.Click -> btnBrowseEventualeAllegato_Click`: SchedaParcella > btnBrowseEventualeAllegato
- `btnDeleteEventualeAllegato.Click -> btnDeleteEventualeAllegato_Click`: SchedaParcella > btnDeleteEventualeAllegato
- `btnIncludiEventualeAllegato.Click -> btnIncludiEventualeAllegato_Click`: SchedaParcella > btnIncludiEventualeAllegato
- `btnModificaEventualeAllegato.Click -> btnModificaEventualeAllegato_Click`: SchedaParcella > btnModificaEventualeAllegato
- `btnElimina.Click -> btnElimina_Click`: SchedaParcella > Elimina
- `lblControlloCodiceFiscale.Click -> lblControlloCodiceFiscale_Click`: SchedaParcella > lblControlloCodiceFiscale
- `btnOK.Click -> btnOK_Click`: SchedaParcella > Ok
- `btnScannerEventualeAllegato.Click -> btnScannerEventualeAllegato_Click`: SchedaParcella > Scanner
### SchedaPratica

Sorgente: `QuickOrganizer/SchedaPratica.cs`

- `btnPraticheCollegate.Click -> btnPraticheCollegate_Click`: SchedaPratica > ...
- `btnLinkCartellaEsterna.Click -> btnLinkCartellaEsterna_Click`: SchedaPratica > ...
- `btnAvvocatoControparte.Click -> btnAvvocatoControparte_Click`: SchedaPratica > ...
- `btnResponsabilePratica.Click -> btnResponsabilePratica_Click`: SchedaPratica > ...
- `btnTitolarePratica.Click -> btnTitolarePratica_Click`: SchedaPratica > ...
- `btnElimina.Click -> btnElimina_Click`: SchedaPratica > Elimina
- `lblAnnotazioni.Click -> lblAnnotazioni_Click`: SchedaPratica > lblAnnotazioni
- `btnOK.Click -> btnOK_Click`: SchedaPratica > Ok
- `lblPersonalizzabile1.Click -> lblPersonalizzabile1_Click`: SchedaPratica > Personalizzabile1
- `lblPersonalizzabile2.Click -> lblPersonalizzabile2_Click`: SchedaPratica > Personalizzabile2
- `StarPersonalizzabile1.Click -> StarPersonalizzabile1_Click`: SchedaPratica > StarPersonalizzabile1
- `StarPersonalizzabile2.Click -> StarPersonalizzabile2_Click`: SchedaPratica > StarPersonalizzabile2
### SchedaPrestazioneSingola

Sorgente: `QuickOrganizer/SchedaPrestazioneSingola.cs`

- `btnCancel.Click -> btnCancel_Click`: SchedaPrestazioneSingola > Annulla
- `btnElimina.Click -> btnElimina_Click`: SchedaPrestazioneSingola > Elimina
- `LblHelp.Click -> LblHelp_Click`: SchedaPrestazioneSingola > LblHelp
- `btnOK.Click -> btnOK_Click`: SchedaPrestazioneSingola > Ok
- `btnTariffario.Click -> btnTariffario_Click`: SchedaPrestazioneSingola > Tariffario
### SchedaPrestazioniUpDown

Sorgente: `QuickOrganizer/SchedaPrestazioniUpDown.cs`

- `btnAggiungi.Click -> btnAggiungi_Click`: SchedaPrestazioniUpDown > Aggiungi
- `btnCancel.Click -> btnCancel_Click`: SchedaPrestazioniUpDown > Annulla
- `btnDown.Click -> btnDown_Click`: SchedaPrestazioniUpDown > btnDown
- `btnUP.Click -> btnUP_Click`: SchedaPrestazioniUpDown > btnUP
- `btnElimina.Click -> btnElimina_Click`: SchedaPrestazioniUpDown > Elimina
- `btnModifica.Click -> btnModifica_Click`: SchedaPrestazioniUpDown > Modifica
- `btnOK.Click -> btnOK_Click`: SchedaPrestazioniUpDown > Ok
### SchedaPrimaNotaCassa

Sorgente: `QuickOrganizer/SchedaPrimaNotaCassa.cs`

- `btnCancel.Click -> btnCancel_Click`: SchedaPrimaNotaCassa > Annulla
- `btnElimina.Click -> btnElimina_Click`: SchedaPrimaNotaCassa > Elimina
- `btnOK.Click -> btnOK_Click`: SchedaPrimaNotaCassa > Ok
### SchedaRecuperaVociDaPrecedenteParcella

Sorgente: `QuickOrganizer/SchedaRecuperaVociDaPrecedenteParcella.cs`

- `btnCancel.Click -> btnCancel_Click`: SchedaRecuperaVociDaPrecedenteParcella > Annulla
- `btnEliminaDiritti.Click -> btnEliminaDiritti_Click`: SchedaRecuperaVociDaPrecedenteParcella > Elimina Diritti
- `btnEliminaOnorari.Click -> btnEliminaOnorari_Click`: SchedaRecuperaVociDaPrecedenteParcella > Elimina Onorari
- `btnOK.Click -> btnOK_Click`: SchedaRecuperaVociDaPrecedenteParcella > Ok
### SchedaRecuperaVociDaPrimaNotaCassa

Sorgente: `QuickOrganizer/SchedaRecuperaVociDaPrimaNotaCassa.cs`

- `btnCancel.Click -> btnCancel_Click`: SchedaRecuperaVociDaPrimaNotaCassa > Annulla
- `btnOK.Click -> btnOK_Click`: SchedaRecuperaVociDaPrimaNotaCassa > Ok
### SchedaRecuperaVociDalTariffario

Sorgente: `QuickOrganizer/SchedaRecuperaVociDalTariffario.cs`

- `btnCancel.Click -> btnCancel_Click`: SchedaRecuperaVociDalTariffario > Annulla
- `btnOK.Click -> btnOK_Click`: SchedaRecuperaVociDalTariffario > Ok
### SchedaRecuperaVociDallaPratica

Sorgente: `QuickOrganizer/SchedaRecuperaVociDallaPratica.cs`

- `btnCancel.Click -> btnCancel_Click`: SchedaRecuperaVociDallaPratica > Annulla
- `btnOK.Click -> btnOK_Click`: SchedaRecuperaVociDallaPratica > Ok
### SchedaResoconto

Sorgente: `QuickOrganizer/SchedaResoconto.cs`

- `btnOK.Click -> btnOK_Click`: SchedaResoconto > Ok
- `btnStampa.Click -> btnStampa_Click`: SchedaResoconto > Stampa...
### SchedaSingolavoceNuovoTariffario

Sorgente: `QuickOrganizer/SchedaSingolavoceNuovoTariffario.cs`

- `btnCancel.Click -> btnCancel_Click`: SchedaSingolavoceNuovoTariffario > Annulla
- `btnOK.Click -> btnOK_Click`: SchedaSingolavoceNuovoTariffario > Ok
### SchedaSviluppoMacro

Sorgente: `QuickOrganizer/SchedaSviluppoMacro.cs`

- `btnAggiungi.Click -> btnAggiungi_Click`: SchedaSviluppoMacro > Aggiungi
- `btnAnnulla.Click -> btnAnnulla_Click`: SchedaSviluppoMacro > Annulla
- `btnElimina.Click -> btnElimina_Click`: SchedaSviluppoMacro > Elimina
- `btnParametri.Click -> btnParametri_Click`: SchedaSviluppoMacro > Parametri
- `btnRinomina.Click -> btnRinomina_Click`: SchedaSviluppoMacro > Rinomina
- `btnOK.Click -> btnOK_Click`: SchedaSviluppoMacro > Salva e Chiudi
### SchedaTitolo

Sorgente: `QuickOrganizer/SchedaTitolo.cs`

- `btnAggiungiIpoteca.Click -> btnAggiungiIpoteca_Click`: SchedaTitolo > Aggiungi
- `_btnCancel.Click -> _btnCancel_Click`: SchedaTitolo > Annulla
- `btnEliminaIpoteca.Click -> btnEliminaIpoteca_Click`: SchedaTitolo > Elimna
- `btnModificaIpoteca.Click -> btnModificaIpoteca_Click`: SchedaTitolo > Modifica
- `_btnOK.Click -> _btnOK_Click`: SchedaTitolo > OK
### SplashScreenQuickOrganizer

Sorgente: `QuickOrganizer/SplashScreenQuickOrganizer.cs`

- `base.DoubleClick -> SplashScreen_DoubleClick`: SplashScreenQuickOrganizer > base
- `pnlStatus.DoubleClick -> SplashScreen_DoubleClick`: SplashScreenQuickOrganizer > pnlStatus
- `lblTimeRemaining.DoubleClick -> SplashScreen_DoubleClick`: SplashScreenQuickOrganizer > Tempo trascorso:
### UfficioRegistroRuolo

Sorgente: `QuickOrganizer/UfficioRegistroRuolo.cs`

- `btnOK.Click -> btnOK_Click`: UfficioRegistroRuolo > Ok
### WizardImportaPraticheDaPolisWeb

Sorgente: `QuickOrganizer/WizardImportaPraticheDaPolisWeb.cs`

- `btnIndietro.Click -> btnIndietro_Click`: WizardImportaPraticheDaPolisWeb > <  Indietro
- `btnAnnulla.Click -> btnAnnulla_Click`: WizardImportaPraticheDaPolisWeb > Annulla
- `btnAvanti.Click -> btnAvanti_Click`: WizardImportaPraticheDaPolisWeb > Avanti  >
- `gridRisultatiRicerca.Click -> gridRisultatiRicerca_Click`: WizardImportaPraticheDaPolisWeb > gridRisultatiRicerca
- `btnSalva.Click -> btnSalva_Click`: WizardImportaPraticheDaPolisWeb > Salva
- `btnAggiornaCertificato.Click -> btnAggiornaCertificato_Click`: WizardImportaPraticheDaPolisWeb > Seleziona
- `btnAggiornaCertificato2.Click -> btnAggiornaCertificato2_Click`: WizardImportaPraticheDaPolisWeb > Seleziona
- `btnStampa.Click -> btnStampa_Click`: WizardImportaPraticheDaPolisWeb > Stampa
### WizardRinvia

Sorgente: `QuickOrganizer/WizardRinvia.cs`

- `btnIndietro.Click -> btnIndietro_Click`: WizardRinvia > <  Indietro
- `btnInizio.Click -> btnInizio_Click`: WizardRinvia > <<  Inizio
- `btnAnnulla.Click -> btnAnnulla_Click`: WizardRinvia > Annulla
- `btnAvanti.Click -> btnAvanti_Click`: WizardRinvia > Avanti  >
- `btnResoconto.Click -> btnResoconto_Click`: WizardRinvia > btnResoconto
- `LblIconaComputoTermini.Click -> lblPrimaIconaComputoTermini_Click`: WizardRinvia > LblIconaComputoTermini
- `lblResoconto.Click -> lblResoconto_Click`: WizardRinvia > Resoconto...
- `SecondaIconaComputoTermini.Click -> lblSecondaIconaComputoTermini_Click`: WizardRinvia > SecondaIconaComputoTermini
### ZoomForm

Sorgente: `QuickOrganizer/ZoomForm.cs`

- `btnCancel.Click -> btnCancel_Click`: ZoomForm > Cancel
- `btnOK.Click -> btnOK_Click`: ZoomForm > OK
### frmAccountSettings

Sorgente: `QuickOrganizer/frmAccountSettings.cs`

- `btnAggiungiAccount.Click -> btnAggiungiAccount_Click`: frmAccountSettings > Aggiungi
- `btnCancel.Click -> CancelSettings`: frmAccountSettings > Cancel
- `btnEliminaAccount.Click -> btnEliminaAccount_Click`: frmAccountSettings > Elimina
- `btnSave.Click -> btnSave_Click`: frmAccountSettings > Save
- `txtPop3Password.Click -> txtPop3Password_Click`: frmAccountSettings > txtPop3Password
- `txtSmtpPassword.Click -> txtSmtpPassword_Click`: frmAccountSettings > txtSmtpPassword
### frmAddressBook

Sorgente: `QuickOrganizer/frmAddressBook.cs`

- `btnAggiungiNuovo.Click -> btnAggiungiNuovo_Click`: frmAddressBook > Aggiungi Nuovo
- `btnModifica.Click -> btnModifica_Click`: frmAddressBook > Modifica
- `btnOK.Click -> btnOK_Click`: frmAddressBook > OK
- `cmdFindNext.Click -> cmdFindNext_Click`: frmAddressBook > Trova successivo
### frmEmailBook

Sorgente: `QuickOrganizer/frmEmailBook.cs`

- `btnAggiungiModifica.Click -> btnAggiungiModifica_Click`: frmEmailBook > Aggiungi
- `btnCancel.Click -> btnCancel_Click`: frmEmailBook > Annulla
- `btnOK.Click -> btnOK_Click`: frmEmailBook > OK
- `cmdFindNext.Click -> cmdFindNext_Click`: frmEmailBook > Trova
### frmFaldoni

Sorgente: `QuickOrganizer/frmFaldoni.cs`

- `btnEliminaFaldone.Click -> btnEliminaFaldone_Click`: frmFaldoni > Elimina faldone
- `btnOK.Click -> btnOK_Click`: frmFaldoni > OK
- `btnEliminaPratica.Click -> btnEliminaPratica_Click`: frmFaldoni > Rimuovi una pratica dal faldone
### frmFindReplace

Sorgente: `QuickOrganizer/frmFindReplace.cs`

- `button1.Click -> button1_Click`: frmFindReplace > << &Less
- `button3.Click -> button3_Click`: frmFindReplace > Annulla
- `btn_noFormatting.Click -> button4_Click`: frmFindReplace > No Forma&tting
- `button2.Click -> button2_Click`: frmFindReplace > Trova &Successivo
### frmMittenteSettings

Sorgente: `QuickOrganizer/frmMittenteSettings.cs`

- `btnCancel.Click -> CancelSettings`: frmMittenteSettings > Cancel
- `btnSave.Click -> SaveSettings`: frmMittenteSettings > Save
### frmParametriMacro

Sorgente: `QuickOrganizer/frmParametriMacro.cs`

- `btnAnnulla.Click -> btnAnnulla_Click`: frmParametriMacro > Annulla
- `btnOK.Click -> btnOK_Click`: frmParametriMacro > Ok
### frmPraticheBook

Sorgente: `QuickOrganizer/frmPraticheBook.cs`

- `btnAggiungiNuovo.Click -> btnAggiungiNuovo_Click`: frmPraticheBook > Aggiungi Nuovo
- `btnOK.Click -> btnOK_Click`: frmPraticheBook > OK
- `cmdFindNext.Click -> cmdFindNext_Click`: frmPraticheBook > Trova successivo
### frmRubricaTelefonica

Sorgente: `QuickOrganizer/frmRubricaTelefonica.cs`

- `btnCancel.Click -> btnCancel_Click`: frmRubricaTelefonica > Annulla
- `btnOK.Click -> btnOK_Click`: frmRubricaTelefonica > Memorizza
- `btnModifica.Click -> btnModifica_Click`: frmRubricaTelefonica > Modifica
- `cmdFindNext.Click -> cmdFindNext_Click`: frmRubricaTelefonica > Trova
### frmSoapError

Sorgente: `QuickOrganizer/frmSoapError.cs`

- `btnInviaSegnalazione.Click -> btnInviaSegnalazione_Click`: frmSoapError > Invia segnalazione al Supporto Tecnico
### FormInsertBreak

Sorgente: `QuickWord/FormInsertBreak.cs`

- `_btnCancel.Click -> _btnCancel_Click`: FormInsertBreak > &Cancel
- `_btnOK.Click -> _btnOK_Click`: FormInsertBreak > &OK
- `_rbnAtNewLine.Click -> radionButton_Clicked`: FormInsertBreak > Begin at new &line
- `_rbnAtNewPage.Click -> radionButton_Clicked`: FormInsertBreak > Begin at new &page
- `_rbnPageBreak.Click -> radionButton_Clicked`: FormInsertBreak > Insert page &break
- `_rbnWrappingBreak.Click -> radionButton_Clicked`: FormInsertBreak > Insert text &wrapping break
### FormSostituzioneMetadati

Sorgente: `QuickWord/FormSostituzioneMetadati.cs`

- `cmdCancel.Click -> cmdCancel_Click`: FormSostituzioneMetadati > &Annulla
- `cmdElimina.Click -> cmdElimina_Click`: FormSostituzioneMetadati > &Elimina
- `cmdOK.Click -> cmdOK_Click`: FormSostituzioneMetadati > &OK
### FormWordCount

Sorgente: `QuickWord/FormWordCount.cs`

- `_btnClose.Click -> _btnClose_Click`: FormWordCount > &Close
### FormularioBook

Sorgente: `QuickWord/FormularioBook.cs`

- `btnOK.Click -> btnOK_Click`: FormularioBook > OK
- `cmdFindNext.Click -> cmdFindNext_Click`: FormularioBook > Trova successivo
### FrmMaxRowsPreview

Sorgente: `QuickWord/FrmMaxRowsPreview.cs`

- `_btnCancel.Click -> _btnCancel_Click`: FrmMaxRowsPreview > Cancella
- `_btnOK.Click -> BtnOK_Click`: FrmMaxRowsPreview > OK
### GoToDialog

Sorgente: `QuickWord/GoToDialog.cs`

- `_btClose.Click -> _btnClose_Click`: GoToDialog > &Chiudi
- `_btPrevious.Click -> _btnPrevious_Click`: GoToDialog > &Precedente
- `_rbnGoToByNumber.Click -> _rbnGoToByNumber_Click`: GoToDialog > &rbnGoToByNumber
- `_rbnGoToByString.Click -> _rbnGoToByString_Click`: GoToDialog > &rbnGoToByString
- `_btGoToNext.Click -> _btnGoToNext_Click`: GoToDialog > Va&i a...
### InfragisticsStatusBar

Sorgente: `QuickWord/InfragisticsStatusBar.cs`

- `_usbUltraStatusBar.ButtonClick -> _usbUltraStatusBar_ButtonClick`: InfragisticsStatusBar > usbUltraStatusBar
### InsertHyperlinkDialog

Sorgente: `QuickWord/InsertHyperlinkDialog.cs`

- `_btnCancel.Click -> _btCancel_Click`: InsertHyperlinkDialog > &Cancella
- `_btnOK.Click -> _btOK_Click`: InsertHyperlinkDialog > &OK
- `_btnChooseFile.Click -> _btChooseFile_Click`: InsertHyperlinkDialog > Allega
- `_btnIncludiFile.Click -> _btnIncludiFile_Click`: InsertHyperlinkDialog > Includi
### OtherSymbolsDialog

Sorgente: `QuickWord/OtherSymbolsDialog.cs`

- `label.Click -> SelectEvent`: OtherSymbolsDialog > label
### QuickWordMain

Sorgente: `QuickWord/QuickWordMain.cs`

- `item3.Click -> AftherSubItem_Click`: QuickWordMain > item3
- `toolStripItem.Click -> esportaInFormatoRTF_Click`: QuickWordMain > toolStripItem
- `toolStripItem10.Click -> notificaMezzoPEC_Click`: QuickWordMain > toolStripItem10
- `toolStripItem11.Click -> depositoTelematico_Click`: QuickWordMain > toolStripItem11
- `toolStripItem2.Click -> esportaInFrmatoPDF_Click`: QuickWordMain > toolStripItem2
- `toolStripItem3.Click -> esportaInFrmatoPDF_Firmato_Click`: QuickWordMain > toolStripItem3
- `toolStripItem4.Click -> print_Click`: QuickWordMain > toolStripItem4
- `toolStripItem5.Click -> quickPrint_Click`: QuickWordMain > toolStripItem5
- `toolStripItem6.Click -> printPreview_Click`: QuickWordMain > toolStripItem6
- `toolStripItem7.Click -> inviaMezzoEmailInFormatoRTF_Click`: QuickWordMain > toolStripItem7
- `toolStripItem8.Click -> inviaMezzoEmailInFrmatoPDF_Click`: QuickWordMain > toolStripItem8
- `toolStripItem9.Click -> inviaMezzoEmailInFrmatoPDF_Firmato_Click`: QuickWordMain > toolStripItem9

## Nota di verifica

L'albero conserva il percorso raggiungibile dichiarato in InitializeComponent, incluse barre e menu contestuali, e censisce separatamente i controlli associati a eventi cliccabili nelle altre finestre. La parita IUSENTRA va attestata separatamente per ciascuna azione con dati, API, interfaccia e prova reale.
