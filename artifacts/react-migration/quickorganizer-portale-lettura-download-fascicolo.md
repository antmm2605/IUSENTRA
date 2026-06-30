# Accesso PolisWeb, lettura fascicolo e download QuickOrganizer

Generato: 30/06/2026 21:39 (Europe/Rome).

Questo file separa i due comportamenti che in Studio Telematico convivono nello stesso menu: import/sincronizzazione dati tramite wizard e accesso diretto assistito al portale PST tramite browser WebView2.

## Menu Studio Telematico

Menu principale rilevato: `Accesso al PolisWeb...`.

| Voce | Key | Tipo | Launcher | Comportamento |
| --- | --- | --- | --- | --- |
| Importa Pratiche dal PolisWeb | Importa_Pratiche_PolisWeb | wizard_servizi | ImportaPratichePolisWeb(-1) | Apre `WizardImportaPraticheDaPolisWeb` in modalità importazione; interroga i servizi e crea/aggiorna pratiche, profilo, eventi e documenti. |
| Eventi di Cancelleria | Cerca_Eventi_Polisweb | wizard_servizi | ImportaPratichePolisWeb(-2) | Apre lo stesso wizard con `PCT.RicercaNuoviEventi=true` per cercare eventi di cancelleria. |
| Fascicolo d'ufficio | Fascicolo_Ufficio | portale_pst_browser | RecuperaDatiFascicoloUfficio(numeroPratica, showBrowser:true) | Parte dalla pratica selezionata e apre la pagina PST `_infofascicolo` nel browser interno. |
| Eventi fascicolo d'ufficio | Fascicolo_Ufficio_Eventi | portale_pst_browser | RecuperaDatiFascicoloUfficio(...); BrowserForm.SelezionaTabEventiFascicolo() | Dopo `_infofascicolo` cerca link contenente `storicofascicolo` e naviga alla scheda eventi/storico. |
| Documenti fascicolo d'ufficio | Fascicolo_Ufficio_Documenti | portale_pst_browser | RecuperaDatiFascicoloUfficio(...); BrowserForm.SelezionaTabDocumentiFascicolo() | Dopo `_infofascicolo` cerca link contenente `documentifascicolo` e naviga alla scheda documenti. |
| Comunicazioni/notifiche fascicolo d'ufficio | Fascicolo_Ufficio_Notifiche | portale_pst_browser | RecuperaDatiFascicoloUfficio(...); BrowserForm.SelezionaTabNotificheFascicolo() | Dopo `_infofascicolo` cerca link contenente `comunicazionifascicolo` e naviga alla scheda comunicazioni/notifiche. |
| Ricerca nello storico delle attività | Agenda_PolisWeb | portale_pst_browser | UfficioRegistroRuolo("Agenda") | Costruisce URL PST agenda per registro/ufficio/ruolo; BrowserForm compila `dataDal`, `dataAl` e clicca dopo `ruoloRicerca`. |
| Ricerca nel registro delle scadenze | Scarica_Udienze_Scadenze_PolisWeb | portale_pst_browser | UfficioRegistroRuolo("Scadenze") | Costruisce URL PST scadenze per registro/ufficio/ruolo; BrowserForm compila intervallo date e avvia la ricerca. |
| Scarica documenti dal PolisWeb | Scarica_Documenti_PolisWeb | portale_pst_browser_download | UfficioRegistroRuolo("Documenti") | Costruisce URL PST documenti; BrowserForm seleziona `tipiDocumento-5`, date deposito e intercetta i download WebView2. |
| Ricerca RG per costituzione | Ricerca_Fascicoli_Costituzione | portale_pst_browser | UfficioRegistroRuolo("Costituzione") | Costruisce URL PST per ricerca fascicoli ai fini della costituzione. |
| Cassazione civile | Consultazione_Fascicoli_Cassazione_Civile | portale_pst_browser | URL diretto PST | Apre `pst_2_9_2_2.wp?ufficioRicerca=80417740588&registroRicerca=CASSCI&ruoloRicerca=AVV@AVV`. |
| Cassazione penale | Consultazione_Fascicoli_Cassazione_Penale | portale_pst_browser | URL diretto PST | Apre `pst_2_9_1_2.wp?ufficioRicerca=80417740588&registroRicerca=CASSPE&ruoloRicerca=AVV@AVV`. |
| Area notifiche non perfezionate | NotificheNonPerfezionate | portale_pst_browser | BrowserForm via autenticazione PST | Parte da `authentication/it/pst_ar.wp`; BrowserForm rimappa la descrizione su `https://servizipst.giustizia.it/PST/PortaleNotifiche`. |

## URL portale PST per accesso diretto

QuickOrganizer costruisce URL con `registroRicerca`, `ufficioRicerca` e `ruoloRicerca={ruolo}@{ruolo}`. La base è `https://servizipst.giustizia.it/PST/it/`.

| Registro | Descrizione | Area PST | registroRicerca |
| --- | --- | --- | --- |
| CC | Contenzioso civile | pst_2_1_1 | CC |
| MIN | Minorenni | pst_2_1_1 | MIN |
| LAV | Lavoro | pst_2_1_2 | LAV |
| FALL | Procedure concorsuali | pst_2_1_3 | FALL |
| ESIM | Esecuzioni immobiliari | pst_2_1_4 | ESIM |
| ESM | Esecuzioni mobiliari | pst_2_1_5 | ESM |
| GP/GDP | Giudice di Pace | pst_2_1_6 | GDP |
| VG | Volontaria giurisdizione | pst_2_1_14 | VG |

### Suffissi funzione

| Funzione | Suffisso URL |
| --- | --- |
| Agenda | _1.wp |
| Scadenze | _2.wp |
| Documenti | _4.wp |
| Costituzione | _5.wp |

### Cassazione

| Registro | URL |
| --- | --- |
| CASSCI | https://servizipst.giustizia.it/PST/it/pst_2_9_2_2.wp?ufficioRicerca=80417740588&registroRicerca=CASSCI&ruoloRicerca=AVV@AVV |
| CASSPE | https://servizipst.giustizia.it/PST/it/pst_2_9_1_2.wp?ufficioRicerca=80417740588&registroRicerca=CASSPE&ruoloRicerca=AVV@AVV |

## Lettura fascicolo dal portale

- Le voci `Fascicolo d'ufficio`, `Eventi`, `Documenti` e `Notifiche` partono dalla pratica selezionata e chiamano `RecuperaDatiFascicoloUfficio(..., showBrowser:true)`.
- Quando la pagina contiene `_infofascicolo`, `BrowserForm` seleziona la scheda cercando link con `storicofascicolo`, `documentifascicolo` o `comunicazionifascicolo`.
- Questo è accesso portale assistito: richiede sessione PST/certificato dell'utente e va verificato in browser reale prima di copiarlo come flusso automatico.

## Ricerca fascicolo e ricerca per anno

| Modo | Comportamento QuickOrganizer | Metodi | Campi payload |
| --- | --- | --- | --- |
| ricerca_esatta_numero_anno | Se `NumeroPratica > 0`, il wizard passa numero ruolo e anno ruolo ai metodi di ricerca. | ExecuteRicercaInformazioniFascicoloPerTipo, ExecuteRicercaInformazioniFascicoloPerNumero, ExecuteRicercaRicorsiCassazione | idUfficio, tipo=RNG/RGN, numero, anno, role, registro |
| ricerca_per_anno | Se non c'è numero ruolo, il wizard passa `numeroRuolo=0` e `anno=cboAnno.Text`; il portale restituisce l'elenco dei fascicoli visibili per quell'anno. | ExecuteRicercaInformazioniFascicoloPerTipo, ExecuteRicercaInformazioniFascicoloPerNumero, ExecuteRicercaRicorsiCassazione, ExecuteRicercaInformazioniFascicoloPerRMO per SIGP senza numero | idUfficio, tipo=RNG/RGN, numero=0, anno, role, registro |
| cassazione_per_anno | La busta `EnvelopeRicercaRicorsiCassazione` usa `QC_Ricorsi` per civile e in IUSENTRA `QP_Ricorsi` per penale; per annuale si usano intervalli data dell'anno. | ExecuteRicercaRicorsiCassazione | DATADEP_DA/DATADEP_AL o DATAISCR_DA/DATAISCR_AL, ufficio 80417740588, registro CASSCI/CASSPE |

## Scarico singolo documento e intero fascicolo

| Passo | Nome | Dettaglio |
| --- | --- | --- |
| 1 | selezione registro/ufficio/ruolo/anno | Il wizard sceglie `sUrn`, `sTargetPath`, `sRole`, `sIDUfficio`, `sAnnoRuoloGenerale`, `sIdRegistro`. |
| 2 | ricerca elenco fascicoli | Chiama `RicercaInformazioniFascicoloPerTipo`, `RicercaInformazioniFascicoloPerNumero`, `RicercaInformazioniFascicoloPerRMO` o `RicercaRicorsiCassazione`. |
| 3 | profilo fascicolo | `ExecuteProfiloFascicolo` recupera oggetto, stato, data iscrizione, sezione, numero sezionale e dati base. |
| 4 | storico fascicolo | `ExecuteStoricoFascicolo` recupera eventi/storico e `IDDOCUMENTO` degli atti collegati. |
| 5 | master/detail documenti | `SelezionaDocumentiFascicolo` scorre lo storico; per ogni `IDDOCUMENTO` chiama `EstraiMasterDetailAtto` o `EstraiMasterDetailAttoSIECIC`. |
| 6 | download singolo documento | `DownloadDocumentoDIGSIA` invia `downloadDocumento` con `idCat` e `original=true/false`; estrae la parte MIME base64 e salva il file. |
| 7 | download intero fascicolo | Non risulta un endpoint unico: QuickOrganizer scarica l'intero fascicolo iterando tutti i documenti selezionati nella griglia, inclusi allegati. |

Interpretazione: non è emerso un endpoint unico `scarica intero fascicolo`. Studio Telematico scarica l'intero fascicolo come batch di download singoli, iterando documenti e allegati selezionati.

## Opzioni download servizi

| Opzione | Duplicato | Original | Effetto |
| --- | --- | --- | --- |
| Scarica come duplicato | True | True | salva duplicato; se PDF marca `signed=true` nel record TESTI |
| Scarica come copia | False | False | salva copia informatica e normalizza estensioni `.p7m` verso estensione originale quando possibile |
| Non scaricare |  |  | salta il documento |

## Download intercettato dal browser

- Evento: `OnWebView2DownloadStarting`.
- Estensioni/pattern ammessi: .PDF, .RTF, .TXT, .JPG, .GIF, .TIFF, .XML, .P7M, .ZIP, .RAR, action?crs=.
- Gestione `.p7m`: Se il `.p7m` non risulta firma CAdES valida, prova a normalizzare l'estensione verso il contenuto originale (`.pdf`, `.xml`, `.zip`, ecc.).

| Destinazione | Comportamento |
| --- | --- |
| PRATICA | Se non c'è pratica corrente chiede una pratica; poi salva file e record in `TESTI` con `TIPO=PCT` e `NUMEROPRATICA`. |
| DESKTOP | Sposta il file in `Desktop\POLISWEB\` o `Desktop\WHATSAPP\`. |
| HASH | Sposta in cartella temporanea e mostra SHA-256 tramite `FormHash`. |

## Regole per IUSENTRA

- Creare due azioni distinte: `Importa/sincronizza da PolisWeb` e `Accedi al PolisWeb`.
- `Scarica intero fascicolo` deve essere batch governato di documenti singoli, con progress, deduplica per `idCat/IdDocumento/hash` e ripresa su errore.
- Ogni documento deve salvare tenant, fascicolo, ufficio, registro, ruolo, origine portale, id documento, hash, data italiana e stato download.
- Lo scarico via portale non deve diventare prova di deposito o notifica: alimenta fascicolo, agenda, scadenziario e presidio PEC come origine documentale.
