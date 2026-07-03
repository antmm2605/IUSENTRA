# PolisWeb: lettura campo per campo da Studio Telematico

Generato: 02/07/2026 00:00 (Europe/Rome).

Questo file va riletto dopo ogni compattazione prima di lavorare su ricerca fascicoli, import fascicoli, agenda/scadenziario da PolisWeb, download documenti, notifiche PEC da fascicolo, portali PST o presidio PEC collegato ai fascicoli. Non sostituisce le fonti ufficiali: è il promemoria operativo interno che mette insieme sorgenti Studio Telematico, codice IUSENTRA e documentazione ministeriale PST.

Regola UI: in IUSENTRA non devono comparire riferimenti visibili a Studio Telematico, QuickOrganizer o dettagli tecnici interni. Questi nomi sono ammessi solo in artifact, test e note di sviluppo.

## Fonti lette

- `C:\Users\antmm\AppData\Local\Temp\quickorganizer_decompiled_full\QuickOrganizer\WizardImportaPraticheDaPolisWeb.cs`
- `C:\Users\antmm\AppData\Local\Temp\quickorganizer_decompiled_full\QuickOrganizer\PCT.cs`
- `C:\Users\antmm\AppData\Local\Temp\quickorganizer_decompiled_full\QuickOrganizer\Common.cs`
- `C:\Users\antmm\AppData\Local\Temp\quickorganizer_decompiled_full\QuickOrganizer\FormMain.cs`
- `C:\Users\antmm\AppData\Local\Temp\quickorganizer_decompiled_full\QuickOrganizer\PoliswebRole.cs`
- `C:\QuickOrganizer\ListaUfficiGiudiziari.xml`
- `C:\QuickOrganizer\QC_Uffici.xml`
- `pct/polisWeb.py`
- `web/services/telematico_runtime.py`
- `frontend/src/components/TelematicoSurfacePage.tsx`
- Fonte ufficiale PST corrente controllata il 03/07/2026: `https://pst.giustizia.it/PST/resources/cms/documents/Documentazione_servizi_web_v1.69.pdf`
- Pagina ufficiale PST documentazione corrente: `https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC4571`
- Pagina ufficiale PST servizi: `https://pst.giustizia.it/PST/it/services.page`
- Controllo triangolato fonte/Studio Telematico/IUSENTRA: `artifacts/react-migration/polisweb-controllo-fonti-iusentra-2026-07-03.md`

Fonte ministeriale verificata: il dettaglio PST indica `Documentazione servizi web esposti (versione 1.69)` con ultimo aggiornamento `12/02/2026`. La documentazione conferma che i servizi si invocano via SOAP/QBuilder con `InvocationDomain name="JPW"`, `group` come codice ufficio e `role` come ruolo applicativo; per Cassazione il `group` non va specificato nell'InvocationDomain. La v1.69 aggiunge namespace per consultazioni anonime Minorenni e Giudice di Pace: sono da conservare come catalogo/futuro canale anonimo, ma non sostituiscono il flusso autenticato di import fascicolo reale.

## Obiettivo operativo

IUSENTRA deve importare e sincronizzare fascicoli PolisWeb senza una ricerca generica e senza perdita di struttura. Il comportamento corretto è:

1. scegliere registro, ufficio, ruolo, anno e numero;
2. risolvere il servizio PST/JPW corretto;
3. invocare il metodo di ricerca specifico del registro;
4. salvare il risultato con registro, namespace, target, ufficio, ruolo, `subpro`, `idDfa` e identificativi ministeriali;
5. aprire il dettaglio con `ProfiloFascicolo`;
6. caricare parti, fascicolo precedente e scadenze quando presenti;
7. caricare storico/eventi;
8. ricavare documenti da `IDDOCUMENTO` tramite master/detail;
9. scaricare singoli documenti con `idCat`;
10. importare fascicolo, documenti, eventi, scadenze e notifiche nel tenant SQL, agenda/scadenziario e presidio PEC.

## Flussi Studio Telematico individuati

| Voce operativa | Flusso | Metodo/launcher | Scopo |
| --- | --- | --- | --- |
| Importa pratiche da PolisWeb | Wizard servizi | `ImportaPratichePolisWeb(-1)` | Cerca fascicoli, importa profilo, parti, storico e documenti. |
| Eventi di cancelleria | Wizard servizi | `ImportaPratichePolisWeb(-2)` con `RicercaNuoviEventi=true` | Cerca eventi per intervallo date su più uffici/registri. |
| Pratica già esistente | Wizard servizi | `ImportaPratichePolisWeb(numeroPratica)` | Sincronizza una pratica interna con il fascicolo PST. |
| Fascicolo d'ufficio | Browser PST assistito | `RecuperaDatiFascicoloUfficio(..., showBrowser:true)` | Apre il fascicolo nel portale, poi consente schede eventi/documenti/notifiche. |
| Agenda PolisWeb | Browser PST assistito | `UfficioRegistroRuolo("Agenda")` | Costruisce URL PST agenda per ufficio, registro e ruolo. |
| Scadenze PolisWeb | Browser PST assistito | `UfficioRegistroRuolo("Scadenze")` | Costruisce URL PST scadenze e intervallo date. |
| Documenti PolisWeb | Browser PST assistito/download | `UfficioRegistroRuolo("Documenti")` | Apre ricerca documenti e intercetta download WebView2. |
| Ricerca per costituzione | Browser PST assistito | `UfficioRegistroRuolo("Costituzione")` | Ricerca RG utile alla costituzione. |
| Cassazione civile | Browser PST assistito | URL diretto `registroRicerca=CASSCI` | Consultazione Cassazione civile con ufficio `80417740588`. |
| Cassazione penale | Browser PST assistito | URL diretto `registroRicerca=CASSPE` | Consultazione Cassazione penale con ufficio `80417740588`. |

Interpretazione per IUSENTRA: servono due superfici governate ma collegate. La prima è `Importa/sincronizza da PolisWeb`, basata su dati e API reali. La seconda è `Accedi al PolisWeb`, basata su browser/Local Signer/sessione reale, senza presentarla come import automatico quando non sono stati acquisiti i dati strutturati.

## Matrice registri e metodi

| Macroarea | Alias utente | Registro da inviare | Namespace/URN | Target/servizio | Ricerca esatta | Ricerca per anno | Note obbligatorie |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Civile ordinario | SICID / RGN / RNG / contenzioso | `CC` | `CONS-SICC-BE` | `JPW_SICID` | `RicercaInformazioniFascicoloPerTipo`, `tipo=RNG`, `numero`, `anno` | stesso metodo con `numero=0`/numero omesso e `anno` | IUSENTRA può mostrare “Civile ordinario”, ma deve inviare `CC`. |
| Lavoro | SIL / LAV | `LAV` | `CONS-SIL-BE` | `JPW_SICID` nel codice Studio; servizio logico IUSENTRA `JPW_SIL`/`JPW_SIL_DISTR` | `RicercaInformazioniFascicoloPerTipo`, `tipo=RNG` | stesso metodo con anno | Studio esclude uffici con `DISTACCATA`. Verificare con catalogo uffici prima di scartare. |
| Volontaria giurisdizione | SIVG / VG | `VG` | `CONS-SIVG-BE` | `JPW_SICID` nel codice Studio; servizio logico IUSENTRA `JPW_SIVG` | `RicercaInformazioniFascicoloPerTipo`, `tipo=RNG` | stesso metodo con anno | Ruoli osservati: `AVV`, `CTU`, `AUS`. |
| Minorenni | MIN / SIMIN | `MIN` | `CONS-MIN-BE` | `JPW_SICID` nel codice Studio; servizio logico IUSENTRA `JPW_MIN`/`JPW_SIMIN` | `RicercaInformazioniFascicoloPerTipo`, `tipo=RNG` | stesso metodo con anno | Accettare alias `MIN` e `SIMIN`; salvare sempre il registro ministeriale `MIN`. |
| Esecuzioni mobiliari | SIECIC / ESM | `ESM` | `CONS-SIECIC-BE` | `JPW_SIECIC` | `RicercaInformazioniFascicoloPerNumero`, `registro=ESM`, `tipo=RNG` | stesso metodo con anno | `idDfa` è strutturale per dettaglio, parti e documenti. |
| Esecuzioni immobiliari | SIECIC / ESIM | `ESIM` | `CONS-SIECIC-BE` | `JPW_SIECIC` | `RicercaInformazioniFascicoloPerNumero`, `registro=ESIM`, `tipo=RNG` | stesso metodo con anno | Non accorpare con `ESM`: il registro cambia. |
| Procedure concorsuali | SIECIC / FALL | `FALL` | `CONS-SIECIC-BE` | `JPW_SIECIC` | `RicercaInformazioniFascicoloPerNumero`, `registro=FALL`, `tipo=RNG` | stesso metodo con anno | Dopo profilo Studio chiama `ElencoPartiPC`. |
| Giudice di Pace | SIGP / GDP / GP | `GP` nel codice Studio, `GDP` nel portale/XML | `CONS-SIGP-BE` | `JPW_SIGP` | `RicercaInformazioniFascicoloPerTipo`, `tipo=RNG` | `RicercaInformazioniFascicoloPerRMO` senza numero | IUSENTRA deve accettare `GP`, `GDP`, `SIGP`; per URL portale usare `GDP`. |
| Cassazione civile | CASSCI | `CASSCI` | `CONS-CASSCI` | `JPW_CASS` / logico `JPW_CASSCI` | `ExecuteRicercaRicorsiCassazione`; Studio usa `QC_Ricorsi` per anno | intervallo anno `DATADEP_DA=01/01/YYYY`, `DATADEP_AL=31/12/YYYY` | Ufficio `80417740588`; il portale usa URL dedicato. |
| Cassazione penale | CASSPE | `CASSPE` | `CONS-CASSPE` | `JPW_CASS` / logico `JPW_CASSPE` | fonte ufficiale PST separa il namespace penale | da implementare come registro distinto | Non presente nel wizard import Studio, ma presente in Accesso PolisWeb e fonte ministeriale. |
| UNEP | Notifiche/esecuzioni UNEP | registri UNEP (`A`, `A/GP`, `A/TER/P`, `B/P`, `C`, `C/TER`) | da trattare separatamente | `JPW_UNEP` | non è import fascicolo civile ordinario | non è import fascicolo civile ordinario | Tenere fuori dal flusso fascicolo civile finché non c'è canale dedicato notifiche/UNEP. |

## Ruoli e sessione

Studio chiede un certificato web di autenticazione e memorizza `PCT_WebCertificateCommonName` e `PCT_WebCertificateSerialNumber`; questo non coincide con il certificato di firma qualificata. Le chiamate SOAP usano sempre `InvocationDomain name="JPW"`, `group=idUfficio` e `role=ruolo`, con eccezione osservata: se il ruolo selezionato è `CUR`, negli header Studio passa `TUT` in alcune buste QBuilder.

Ruoli esposti dal wizard:

| Codice | Etichetta Studio | Uso operativo |
| --- | --- | --- |
| `AVV` | Avvocato | ruolo standard avvocato |
| `DEL` | Delegato | usato su SICID/SIECIC dove ammesso |
| `AUS` | Ausiliario | usato su vari registri |
| `CTU` | Consulente/perito | usato su vari registri |
| `CUR` | Curatore | osservato su `FALL`; header può diventare `TUT` |
| `PARTE` | Parte | presente nel selettore ruolo, non sempre abilitato dal wizard |
| `CUS` | Custode | SIECIC |
| `NOT` | Notaio | SICID/Lavoro/Minorenni nel codice Studio |
| `TUT` | Tutore | SICID/Lavoro/Minorenni |

Fonte PST v1.69: i ruoli ufficiali cambiano per sistema (`SICID`, `SIECIC`, `SIGP`, `CASSAZIONE`). IUSENTRA non deve inventare ruoli, ma deve salvare ruolo richiesto, ruolo effettivamente inviato e risposta ministeriale. Se il ruolo non è abilitato per quel certificato, la UI deve mostrare un blocco puntuale, non una ricerca vuota generica.

### PIN e sessione PST

Studio Telematico carica un solo `_WebCertificate` e lo riusa per tutta la catena del wizard: ricerca, profilo, storico, master/detail, RegIndE e download. L'utente vede il messaggio `Inserisci il pin quando richiesto...` nella fase di verifica credenziali; poi le chiamate successive ricevono lo stesso oggetto certificato. Il PIN non è un campo dati del fascicolo e non va salvato.

Regola IUSENTRA:

- per visualizzare o leggere un fascicolo PST deve essere aperta una sola sessione autenticata `view` tramite Local Signer/certificato web;
- la sessione `view` deve restare riusabile per ricerca, anteprima, profilo, storico e master/detail finché non scade;
- per scaricare l'intero fascicolo non bisogna lanciare N download singoli: bisogna usare il batch `/pst/download-documenti-batch`;
- il batch deve usare un solo processo curl o una sessione equivalente per tutti gli `idCat`, così Windows/token chiede il PIN una sola volta per il lotto;
- se manca `idCat`, il lotto deve risolverlo in batch tramite profilo documento; non deve ricadere su download singolo se questo moltiplica i prompt PIN;
- se la sessione è scaduta, la UI deve chiedere una nuova autenticazione una sola volta e riprendere il batch, non continuare documento per documento;
- la sessione PST di consultazione è diversa dalla sessione PIN di firma: non mischiare certificato web PST e firma digitale qualificata.

Nel codice IUSENTRA questa regola è presidiata da `tools/local_signer.py`: cache `_pst_session_cache`, `PST_SESSION_TTL_SECONDS`, `_reuse_view_session_id_if_available`, `_pst_prepare_authenticated_session`, `_pst_download_documenti_batch` e `_pst_download_documenti_batch_payloads`. I test mirati stanno in `tests/test_local_signer.py` e vanno rilanciati quando si tocca ricerca/import/download PolisWeb.

## Pipeline end to end campo per campo

### 1. Disponibilità ufficio/servizi

Tabella Studio `dtServiziTelematici`:

| Campo | Significato per IUSENTRA |
| --- | --- |
| `idGestoreLocale` | gestore locale/endpoint da usare |
| `idUfficio` | codice ministeriale ufficio |
| `NomeUfficio` | nome ufficio |
| `JPW_SICID` | disponibilità consultazione SICID/LAV/VG/MIN via gateway Studio |
| `JPW_SIECIC` | disponibilità SIECIC |
| `JPW_SIGP` | disponibilità Giudice di Pace |
| `COM_TEL_136` | comunicazioni telematiche |
| `JPW_CASS` | disponibilità Cassazione |
| `Deposito_telematico` | capacità deposito |
| `IndirizzoPEC` | PEC ufficio |

IUSENTRA deve avere un catalogo equivalente per decidere quali registri proporre per ufficio. Se manca il servizio, la UI non deve fare una chiamata cieca: deve spiegare che quel registro non risulta disponibile per l'ufficio selezionato.

### 2. Ricerca elenco fascicoli

Campi di input da conservare:

| Campo | Origine | Obbligatorio |
| --- | --- | --- |
| `ufficio_codice` / `idUfficio` | selezione ufficio | sì |
| `ufficio_nome` | catalogo uffici | sì per UI/audit |
| `registro` | matrice registro | sì |
| `namespace_urn` | matrice registro | sì |
| `target_path` / `servizio_pst_preferito` | matrice registro/catalogo uffici | sì |
| `ruolo_polisweb` | selezione utente/certificato | sì |
| `numero_rg` | input utente o pratica esistente | facoltativo |
| `anno_rg` | input utente | sì per ricerca annuale/esatta |
| `tipo_numero` | Studio usa `RNG` | sì |
| `nome_parte` / `cf_parte` | filtri locali o payload se supportato | facoltativo |

Metodi osservati:

| Registro | Metodo | Value set da valorizzare |
| --- | --- | --- |
| `CC`, `LAV`, `VG`, `MIN` | `RicercaInformazioniFascicoloPerTipo` | `idUfficio`, `tipo=RNG`, `numero` se > 0, `anno`; `subpro` è dichiarato per `SIVG`/`SIGP` ma non valorizzato in ricerca Studio |
| `ESM`, `ESIM`, `FALL` | `RicercaInformazioniFascicoloPerNumero` | `idUfficio`, `idRuoloJPW`, `registro`, `tipo=RNG`, `numero` se > 0, `anno`, `NUMEROUNITARIO` dichiarato ma non valorizzato |
| `GP`/`GDP` con numero | `RicercaInformazioniFascicoloPerTipo` | `idUfficio`, `tipo=RNG`, `numero`, `anno` |
| `GP`/`GDP` senza numero | `RicercaInformazioniFascicoloPerRMO` | `idUfficio`; `numero` e `anno` dichiarati ma non valorizzati |
| `CASSCI` | `QC_Ricorsi` / `ExecuteRicercaRicorsiCassazione` | Studio valorizza intervallo deposito dell'anno, non un normale `numero/anno` |

### 3. Campi risultato ricerca

Tabella Studio `dtInfoFascicolo`:

| Campo | Mappatura IUSENTRA |
| --- | --- |
| `MyIndex` | chiave tecnica locale, non sufficiente da sola |
| `IDUFFICIO` | `ufficio_codice` |
| `ANNORUOLO` | `anno_rg` |
| `NUMERORUOLO` | `numero_rg` |
| `SUB_PROCEDIMENTO` | `sub_procedimento`, preservare zeri/valore originale |
| `DATAUDIENZA` | prossima udienza, convertire visibile in data italiana |
| `GIUDICE` | giudice/istruttore |
| `SEZIONE` | sezione |
| `ATTOREPRINCIPALE` | parte principale assistito/attore |
| `CONVENUTOPRINCIPALE` | controparte principale |
| `NUMEROATTORI` | conteggio attori |
| `NUMEROCONVENUTI` | conteggio convenuti |
| `DATAULTIMAMODIFICA` | data ultima modifica ministeriale |
| `IDDFA` | identificativo flusso fascicolo, obbligatorio per SIECIC |
| `IDFASCICOLO` | id repository fascicolo |
| `REGISTRO` | registro ministeriale normalizzato |
| `REGISTODECODE` | descrizione registro restituita |
| `NUMEROESTENSIONE` | numero estensione se presente |
| `CODRITO` | codice rito |
| `DESCRRITO` | descrizione rito |
| `CREDITORI` | per SIECIC, può alimentare attore principale |
| `DEBITORI` | per SIECIC, può alimentare convenuto principale |
| `DESCRIZIONEFASCICOLO` | titolo leggibile derivato, non fonte primaria |
| `NOMEUFFICIO` | nome ufficio |
| `URN` | namespace usato |
| `TARGHET_PATH` | target path usato da Studio |
| `NUMEROPRATICA` | pratica interna Studio, non importare come id IUSENTRA |
| `NUOVI_EVENTI` | flag ricerca eventi |
| `INDEX` | indice locale |
| `MATERIA` | materia |
| `ARCHIVIO` | archivio/flag |
| `TIPO` | tipo evento/fascicolo secondo risposta |
| `DESC` | descrizione evento/fascicolo |
| `DATA` | data evento |
| `DATAREGISTRAZIONE` | data registrazione evento |
| `IDDOCUMENTO` | id documento collegato allo storico |

Regola IUSENTRA: la chiave di deduplica deve includere almeno tenant, portale, ufficio, registro, anno, numero, `sub_procedimento`, `idDfa` quando presente. Per documenti serve anche `idDocumento`/`idCat`.

### 4. Apertura dettaglio fascicolo

Quando l'utente seleziona un risultato, Studio copia questi campi dal risultato:

| Campo selezionato | Uso successivo |
| --- | --- |
| `URN` | namespace per profilo/storico/documenti |
| `TARGHET_PATH` | endpoint/target |
| `REGISTRO` | registro da passare alle chiamate successive |
| `IDUFFICIO` | ufficio |
| `ANNORUOLO` | anno |
| `NUMERORUOLO` | numero |
| `SUB_PROCEDIMENTO` | subprocedimento |
| `IDDFA` | necessario per SIECIC |
| `NUMEROPRATICA` | collegamento pratica esistente |
| parti principali, sezione, giudice | precompilazione pratica |

Subito dopo Studio chiama:

1. `ProfiloFascicolo`;
2. `StoricoFascicolo`;
3. `SelezionaDocumentiFascicolo`, che deriva i documenti dallo storico.

### 5. Profilo fascicolo

Metodo: `ProfiloFascicolo`.

Value set:

| Campo SOAP | Regola |
| --- | --- |
| `idUfficio` | sempre |
| `anno` | sempre |
| `numero` | se presente |
| `subpro` | se presente |
| `fascPrecedente` | `0/1`; Studio usa `false` nel flusso import base |
| `scadTermini` | `0/1`; Studio usa `false` nel flusso import base |
| `idRuoloJPW` | ruolo |
| `registro` | registro |
| `idDfa` | valorizzare per SIECIC quando presente |

Campi profilo Studio `dtProfiloFascicolo`:

| Campo | Destinazione IUSENTRA |
| --- | --- |
| `idFascicolo` | id repository fascicolo |
| `idUfficio` | ufficio |
| `anno` | anno RG |
| `numero` | numero RG |
| `subprocedimento` | subprocedimento |
| `attoIntroduttivo` | dati fascicolo/profilo |
| `rito` | rito |
| `costituzione` | stato costituzione |
| `descRuolo` | ruolo/registro descrittivo |
| `descMateria` | materia |
| `descOggetto` | oggetto |
| `grado` | grado |
| `giudice` | giudice |
| `descSezione` | sezione |
| `dataIscrizione` | data iscrizione |
| `dataPrimaComparizione` | prima comparizione |
| `dataUltimaUdienza` | ultima udienza |
| `descStato` | stato fascicolo |
| `conservatoria` | flag conservatoria |
| `numeroSezionale` | numero sezionale |
| `annoSezionale` | anno sezionale |
| `dataUltimaModifica` | ultima modifica |
| `idoggetto` | oggetto ministeriale |

Sub-row del profilo:

| Classe | Tabella Studio | Dati da conservare |
| --- | --- | --- |
| `NUMEROCIVILE` | `dtNumeroCivile` | numeri civili collegati |
| `INFOPARTE` | `dtInfoParti` | parti processuali |
| `FASCICOLOPRECEDENTE` | `dtFascicoloPrecedente` | ufficio, anno, numero, provvedimento, data arrivo |
| `SCADENZATERMINE` | `dtScadenzaTerminiFascicolo` | data e descrizione scadenza |

Per `FALL`, dopo profilo Studio chiama `ElencoPartiPC`. Per `ESM` e `ESIM` chiama `ElencoPartiEC`. Queste chiamate richiedono `idUfficio`, `idRuoloJPW`, `registro`, `idDfa`.

### 6. Parti

Tabella Studio `dtInfoParti`:

| Campo | Destinazione |
| --- | --- |
| `COGNOME` | soggetto/parte |
| `NOME` | soggetto/parte |
| `TIPO` | ruolo processuale |
| `DATANASCITA` | anagrafica se disponibile |
| `CODICEFISCALEPARTE` | codice fiscale parte |
| `AVVOCATO` | nominativo avvocato |
| `TIPOLOGIA` | classificazione utente per import |
| `CODICEFISCALEAVVOCATO` | CF avvocato |
| `DOWNLOAD` | scelta/download collegata in UI Studio |

Per SIECIC, `ElencoPartiEC/PC` restituisce almeno `DESCRIZIONE`, `RUOLO`, `CODICE`. Studio mappa `DESCRIZIONE` su `COGNOME`, `RUOLO` su `TIPO`, `CODICE` su `CODICEFISCALEPARTE`; se il codice fiscale ha 16 caratteri e la descrizione ha due parole, prova a dividere cognome/nome. IUSENTRA deve conservare anche il testo originale per evitare errori su nominativi composti.

### 7. Storico fascicolo, eventi e agenda

Metodo: `StoricoFascicolo`.

Value set:

| Campo SOAP | Regola |
| --- | --- |
| `idUfficio` | sempre |
| `anno` | sempre |
| `numero` | se > 0 |
| `subpro` | se > 0 |
| `dal` | filtro data inizio se ricerca eventi |
| `al` | filtro data fine se ricerca eventi |
| `dataRegistrazione` | se filtro specifico |
| `idRuoloJPW` | ruolo |
| `registro` | registro |
| `idDfa` | per SIECIC |

Tabella Studio `dtStoricoFascicolo`:

| Campo | Destinazione IUSENTRA |
| --- | --- |
| `IDSTORICO` | id evento ministeriale |
| `DATA` | data evento/udienza, visibile in italiano |
| `TIPO` | tipo evento |
| `DESC` | descrizione evento |
| `IDUFFICIO` | ufficio |
| `ANNO` | anno RG |
| `NUMERO` | numero RG |
| `SUB_PROCEDIMENTO` | subprocedimento |
| `CODICEEVENTO` | codice evento ministeriale |
| `CODICETIPOEVENTO` | codice tipo evento |
| `DATAREGISTRAZIONE` | registrazione evento |
| `IDDOCUMENTO` | id atto/documento collegato |
| `TIPOLOGIA` | classificazione locale |
| `DOWNLOAD` | scelta download in UI |

Per IUSENTRA: ogni evento importato deve alimentare agenda/scadenziario solo se classificato e deduplicato con `IDSTORICO` più chiave fascicolo. Le date devono essere visualizzate in italiano e fuso `Europe/Rome` quando c'è ora.

### 8. Agenda eventi di cancelleria

Nella modalità `RicercaNuoviEventi`, Studio non parte da un fascicolo selezionato ma itera gli uffici/registri spuntati e chiama:

| Registro | Metodo agenda |
| --- | --- |
| `CC`, `VG`, `MIN`, `LAV`, `GP` | `ExecuteRicercaAgendaSICID` con namespace del registro |
| `ESM`, `ESIM`, `FALL` | `ExecuteRicercaAgendaSIECIC` con `registro` |

Per IUSENTRA: la ricerca eventi deve essere separata dalla ricerca fascicolo, ma deve usare la stessa matrice registri. Risultati con `IDDOCUMENTO` devono poter aprire master/detail e download come nello storico del singolo fascicolo.

### 9. Documenti fascicolo

Metodo: `DocumentiFascicolo`.

Value set:

| Campo SOAP | Regola |
| --- | --- |
| `idUfficio` | sempre |
| `idRuoloJPW` | ruolo |
| `numero` | se > 0 |
| `anno` | sempre |
| `subpro` | se > 0 |
| `registro` | registro |
| `idDfa` | per SIECIC |

Tabella Studio `dtDocumentiFascicolo`:

| Campo | Destinazione |
| --- | --- |
| `dataDeposito` | data deposito documento |
| `autore` | autore/depositante |
| `tipo` | tipo documento/atto |
| `idUfficio` | ufficio |
| `IdDocumento` | id documento o id atto |
| `IdDocMittente` | id mittente |
| `stato` | stato documento |
| `annoDocumento` | anno documento |
| `numeroDocumento` | numero documento |
| `annoFascicolo` | anno fascicolo |
| `numeroFascicolo` | numero fascicolo |
| `subprocedimento` | subprocedimento |

Osservazione importante: nel flusso wizard Studio non usa solo `DocumentiFascicolo`; scorre anche lo storico e, per ogni `IDDOCUMENTO`, chiama `EstraiMasterDetailAtto`. Quindi IUSENTRA deve supportare entrambe le strade:

- elenco documenti da `DocumentiFascicolo`;
- elenco documenti da storico `IDDOCUMENTO` + master/detail.

### 10. Master/detail atto

Metodo non SIECIC: `estraiMasterDetailAtto`, namespace `urn:BEAFascicoloInformatico-distr`.

Payload:

| Campo | Regola |
| --- | --- |
| `idUtenteCorrente` | Studio lascia vuoto nella busta letta |
| `idDoc` | `IDDOCUMENTO` dallo storico/elenco |
| `registro` | registro |
| `ruoloApplicativo` | ruolo |

Metodo SIECIC: `estraiMasterDetailAtto`, namespace `http://elsagdatamat.com/bea/pct/siecic/ws/fascicolo`.

Payload SIECIC:

| Campo | Regola |
| --- | --- |
| `idDoc` | `IDDOCUMENTO`; Studio non passa registro nel payload SIECIC master/detail |

Tabella Studio `dtDocPrimari`:

| Campo | Significato |
| --- | --- |
| `IdSubItem` | id documento padre (`IDDOCUMENTO`) |
| `IdCat` | id catalogo da usare per download |
| `dataDeposito` | data deposito |
| `nomeFileOriginale` | nome file originale |
| `CognomeNomeDepositante` | depositante |
| `TIPOLOGIA` | categoria scelta dall'utente |
| `DOWNLOAD` | duplicato/copia/no |

Tabella Studio `dtDocAllegati`:

| Campo | Significato |
| --- | --- |
| `IdSubItem` | id documento padre |
| `IdCat` | id catalogo allegato |
| `TIPOLOGIA` | categoria ereditata/nascosta |
| `nomeFileOriginale` | nome file allegato |
| `DOWNLOAD` | duplicato/copia/no |

Regole osservate:

- `IdDocumento` identifica atto/evento; `IdCat` identifica il file scaricabile.
- Il documento principale e gli allegati condividono `IdSubItem`.
- Per non SIECIC Studio filtra allegati `.xml`, `.xml.p7m` e `IndiceDocumentiDepositati.PDF`.
- Per SIECIC Studio non applica lo stesso filtro nel blocco letto.
- Nome speciale: `ATTOACQ.PDF` diventa `AttoACQ del {data}.pdf`.

### 11. Download documento

Metodo: `downloadDocumento`.

Namespace non SIECIC: `urn:BEAFascicoloInformatico-distr`.

Payload non SIECIC:

| Campo | Regola |
| --- | --- |
| `idUtenteCorrente` | presente nella busta |
| `idCat` | id catalogo file |
| `original` | `true` per duplicato, `false` per copia |

Namespace SIECIC: `http://elsagdatamat.com/bea/pct/siecic/ws/fascicolo`.

Payload SIECIC:

| Campo | Regola |
| --- | --- |
| `idCat` | id catalogo file |
| `original` | `true` per duplicato, `false` per copia |

Fonte PST v1.69: `original=true` restituisce il documento originale/firmato nel repository; `original=false` restituisce copia con rimozione/annotazione informazioni di firma secondo il tipo di firma. IUSENTRA deve quindi mostrare due opzioni distinte: `Duplicato informatico` e `Copia informatica`, salvando il valore richiesto.

Campi da salvare sul documento importato:

| Campo | Obbligatorio |
| --- | --- |
| tenant proprietario | sì |
| fascicolo IUSENTRA | sì |
| portale origine (`pst`) | sì |
| ufficio | sì |
| registro | sì |
| ruolo | sì |
| anno/numero/subprocedimento | sì |
| `idDocumento`/`IdSubItem` | sì |
| `idCat` | sì |
| nome file originale | sì |
| nome file salvato | sì |
| tipo atto/documento | sì |
| categoria utente | sì |
| duplicato/copia | sì |
| hash file | sì dopo scarico |
| data deposito | sì se presente |
| depositante/autore | sì se presente |
| esito download | sì |

Download intero fascicolo: non è emerso un endpoint unico. Studio scarica l'intero fascicolo iterando documenti principali e allegati selezionati. IUSENTRA deve implementarlo come batch governato con progress, deduplica, retry e audit, non come singolo endpoint immaginato.

### 12. Import pratica/fascicolo interno

Studio crea/aggiorna pratica, parti, agenda e documenti. Per IUSENTRA la destinazione deve rispettare il contratto dati:

| Area | Dati da importare |
| --- | --- |
| Fascicolo | ufficio, registro, numero, anno, subprocedimento, oggetto, stato, rito, sezione, giudice, materia, id ministeriali |
| Parti/soggetti | parti processuali, CF, ruolo, avvocati, CF avvocato, PEC RegIndE se recuperata |
| Agenda | storico selezionato, udienze, adempimenti, scadenze, memorie, eventi cancelleria |
| Scadenziario | scadenze da `SCADENZATERMINE` e classificazione eventi |
| Documenti | primari/allegati, idCat, file, hash, categoria, duplicato/copia |
| Presidio PEC | notifiche/comunicazioni collegate al fascicolo, ricevute e controlli automatici senza invio server-side |
| Notifiche web push | solo dopo persistenza reale di evento/scadenza/notifica e rispetto dei permessi browser |

## Gap IUSENTRA rilevati nel confronto

Questi punti vanno chiusi prima di dichiarare la ricerca/import PolisWeb completa:

1. `pct/polisWeb.py` accetta ancora una ricerca generica con `tribunale`, `numero_rg`, `anno_rg`, `nome_parte`, `cf`; deve accettare e propagare `registro`, `tipo_registro`, `servizio_pst_preferito`, `ruolo_polisweb`, `sub_procedimento`, `id_dfa`.
2. `_soap_ricerca_fascicoli_qbuilder()` deve scegliere il metodo in base al registro: `RicercaInformazioniFascicoloPerTipo`, `RicercaInformazioniFascicoloPerNumero`, `RicercaInformazioniFascicoloPerRMO`, Cassazione civile/penale.
3. `_soap_profilo_fascicolo_qbuilder()` deve passare sempre `registro`, `idRuoloJPW`, `subpro`, `idDfa`, `fascPrecedente`, `scadTermini` quando disponibili.
4. `_soap_documenti_qbuilder()` deve passare `registro`, `idRuoloJPW`, `subpro`, `idDfa`.
5. Il parser `FascicoloPolisWeb` deve conservare `registro`, `urn`, `target_path`, `id_dfa`, `id_fascicolo`, `cod_rito`, `descr_rito`, `materia`, `data_ultima_modifica`, `numero_estensione`, `registro_decode`.
6. Il parser documenti deve conservare `idDocumento`, `idCat`, `idSubItem`, `idDocMittente`, `tipoAtto`, `stato`, `autore`, `annoDocumento`, `numeroDocumento`, `dataDeposito`.
7. `web/services/telematico_runtime.py` deve inoltrare dalla UI a `crea_client().ricerca_fascicoli()` i campi registro/servizio/ruolo e non solo ufficio/numero/anno/parte.
8. `_preview_documenti_portale_server()` deve passare registro, subprocedimento e `idDfa`; altrimenti SIECIC rischia documenti incompleti o sbagliati.
9. `TelematicoSurfacePage.tsx` deve distinguere `ESM`, `ESIM`, `FALL` invece di un generico `SIECIC`, e `CC` invece di un generico `RGN` nel payload tecnico.
10. `GP`, `GDP` e `SIGP` devono essere alias dello stesso registro, con payload coerente verso QBuilder e URL portale.
11. Cassazione civile e penale devono restare separate (`CASSCI`, `CASSPE`), con metodi e target distinti.
12. Il download intero fascicolo deve essere batch di `idCat`, con opzione duplicato/copia e audit per ogni file.
13. L'import deve finire su SQL tenant-aware, non solo JSON o stato React.
14. Agenda, scadenziario, notifiche e web push devono ricevere solo eventi deduplicati e persistiti.

## Regole di implementazione IUSENTRA

- Nessun testo visibile deve citare Studio Telematico o QuickOrganizer.
- Il menu utente deve essere compatto e parlare in termini professionali: `Civile ordinario`, `Lavoro`, `Volontaria giurisdizione`, `Minorenni`, `Esecuzioni mobiliari`, `Esecuzioni immobiliari`, `Procedure concorsuali`, `Giudice di Pace`, `Cassazione civile`, `Cassazione penale`.
- Il payload tecnico deve salvare il registro ministeriale reale.
- I filtri “per anno” e “per numero/anno” sono modalità diverse, non semplici filtri testuali.
- Se un registro richiede `idDfa` e manca, bloccare solo dettaglio/documenti di quel fascicolo con motivo puntuale.
- Se il certificato web/sessione non è disponibile, indicare che serve autenticazione PST locale; non simulare dati come esito reale.
- Ogni data visibile va mostrata in italiano; valori raw possono restare solo nei payload tecnici.
- Ogni documento importato deve essere deduplicato con chiavi ministeriali e hash, non solo per nome file.
- Gli eventi importati devono alimentare Agenda/Scadenziario solo dopo classificazione e deduplica.
- Il presidio PEC deve usare i dati importati per controlli e notifiche, ma l'invio PEC operativo resta dal PC locale tramite Local Signer/servizio locale.

## Stato implementazione 02/07/2026

Confronto eseguito su tre fonti: sorgenti decompilati Studio Telematico (`PCT.cs`, `Common.cs`, `WizardImportaPraticheDaPolisWeb.cs`), cataloghi locali `ListaUfficiGiudiziari.xml`/`QC_Uffici.xml` e fonte ufficiale PST `Documentazione servizi web esposti v1.69`, pubblicata nella pagina PST con ultimo aggiornamento `12/02/2026`.

Aggiornamenti applicati in IUSENTRA:

- `pct/polisWeb.py` ora ha una matrice registro/servizio per `CC`, `LAV`, `VG`, `MIN`, `ESM`, `ESIM`, `FALL`, `GP/GDP`, `CASSCI`, `CASSPE`; la ricerca non dipende più solo da ufficio/numero/anno generici.
- Le chiamate QBuilder scelgono il metodo in base al registro: `RicercaInformazioniFascicoloPerTipo` per SICID/Lavoro/VG/Minorenni/Giudice di Pace con numero, `RicercaInformazioniFascicoloPerNumero` per SIECIC esplicito, `RicercaInformazioniFascicoloPerRMO` per Giudice di Pace annuale, chiamate Cassazione dedicate per civile/penale.
- `web/services/telematico_runtime.py` inoltra registro, servizio PST, ruolo, subprocedimento, `idDfa`, `urn` e `target_path` dal pannello React al client reale, e per PST/PolisWeb non crea più il client in modalità demo.
- `frontend/src/components/TelematicoSurfacePage.tsx` mostra macroaree professionali compatte e invia payload tecnici distinti per `ESM`, `ESIM`, `FALL`, `GDP`, `CASSCI`, `CASSPE`, senza riferimenti visibili a Studio Telematico, QuickOrganizer, JPW o dettagli interni.
- `tools/local_signer.py` preserva il percorso generico SIECIC già testato; quando il registro è esplicito (`ESM`, `ESIM`, `FALL`) usa i campi ministeriali completi `registro`, `idRuoloJPW`, `idDfa` per ricerca, profilo, documenti e sezioni fascicolo.
- Il download intero fascicolo resta un lotto unico tramite `/pst/download-documenti-batch`, così la sessione/certificato web viene riusata e il PIN non viene richiesto documento per documento.
- Correzione specifica dal confronto Studio Telematico: per SIECIC `estraiProfiloDocumento` continua a usare `idDoc`, ma `downloadDocumento` usa `idCat`. Se il profilo risolve `idCat`, il lotto scarica con quello; se un singolo profilo fallisce, il lotto resta batch e usa il miglior identificativo disponibile senza passare al download singolo.
- Miglioramento anti-regressione 03/07/2026 sui servizi già testati: i documenti legacy o incompleti ereditano nel batch `servizio_pst` e `registro_portale` dal contesto del fascicolo; il file scaricato conserva questi metadati insieme a `idCat`, modalità originale/copia e origine. Il master/detail ora prova prima `idDocumento`/`idDoc` e usa `idCat` solo come recupero finale se non esiste un identificativo documento, riducendo chiamate QBuilder sbagliate senza perdere la possibilità di recuperare cataloghi parziali.
- Miglioramento UI verificato il 03/07/2026 sulla pagina React `/portali/pst/acquisizione`: il menu `Tabella ministeriale` mostra `Civile ordinario`, `Lavoro e previdenza`, `Volontaria giurisdizione`, `Minorenni`, `Esecuzioni mobiliari`, `Esecuzioni immobiliari`, `Procedure concorsuali`, `Giudice di Pace`, `Cassazione civile`, `Cassazione penale`; non espone `JPW`, Studio Telematico o QuickOrganizer. La voce `Automatica` torna selezionabile e pulisce schema, registro, tabella ministeriale, servizio preferito e registro portale per permettere una nuova deduzione reale.
- Miglioramento visibile 03/07/2026: cronologia e pannello `Riprova scarico` traducono `Failed to fetch` in `connessione non riuscita` e mostrano timestamp come `18/06/2026 11:26`, senza ISO raw e senza virgola tra data e ora. La normalizzazione passa da `formatDateTimeIt`, quindi presidia anche gli altri pannelli React che usano lo stesso helper.
- Rinforzo import PST 03/07/2026: quando l'import riceve già file reali, catalogo o preview dal browser/Local Signer, `web/services/telematico_runtime.py` usa il client di sola importazione `ClientPolisWebImportOnly` per salvare pratica, parti, catalogo, documenti e audit senza tentare una nuova autenticazione live PST nel punto di persistenza. La ricerca live e l'anteprima live continuano invece a usare `crea_client(demo=False)`.
- Rinforzo tenant-aware 03/07/2026: se `create_app()` riceve un `CLIENTI_DB` esplicito, i default derivati `SOGGETTI_DB`, `SOGGETTI_PARTI_DB`, `PORTALE_DB`, `PORTALE_UPLOADS` e `PORTALE_IMPORT_LOG_DB` restano sotto la stessa root dati invece di ereditare variabili d'ambiente globali come `/data/...`. Questo evita import log e soggetti fuori tenant nei test, nelle copie locali e nelle installazioni multi-root.
- Correzione UI 03/07/2026 sul flusso già testato: quando la ricerca PST viene fermata prima della partenza perché sul PC non risulta un certificato CNS/CIE valido, il pannello di avanzamento mostra `Ricerca non avviata` e `Nessun passaggio avviato`, senza barra di progresso attiva e senza l'indicazione ambigua `Operazione in corso`.

Test eseguiti sul perimetro toccato:

- `python -m pytest tests\test_local_signer.py -q`: passato, 216 test.
- `python -m pytest tests\test_local_signer.py -q`: passato il 03/07/2026 dopo i rinforzi, 219 test.
- `python -m pytest tests\test_local_signer.py::test_download_documenti_batch_best_effort_non_azzera_lotto_se_un_profilo_fallisce -q`: passato.
- `python -m pytest tests\test_local_signer.py::test_pst_download_batch_inietta_contesto_ministeriale_su_documenti_legacy tests\test_local_signer.py::test_pst_download_file_payload_conserva_servizio_e_registro tests\test_local_signer.py::test_pst_master_detail_prova_tutti_gli_identificativi_del_catalogo tests\test_local_signer.py::test_pst_master_detail_usa_idcat_solo_se_manca_iddocumento -q`: passato.
- `python -m py_compile tools\local_signer.py tools\dist\local_signer.py`: passato.
- `python -m py_compile tools\local_signer.py tools\dist\local_signer.py web\services\telematico_runtime.py pct\polisWeb.py web\blueprints\api_v1_react.py`: passato.
- Test mirati `tests\test_polisweb.py` su client reale PST, SIECIC `ESIM`, documenti/profilo e SIGP/GDP: passati.
- Test mirati `tests\test_react_shell.py` sul pannello acquisizione PST e assenza codici tecnici nel badge: passati.
- Test mirati 03/07/2026 su etichette registro, reset `Automatica`, cronologia italiana e assenza testi tecnici: `python -m pytest tests\test_react_shell.py::test_pst_acquisizione_registri_e_cronologia_restano_visibili_professionali tests\test_react_shell.py::test_pst_acquisizione_badge_tabella_non_mostra_codici_tecnici tests\test_react_shell.py::test_pst_acquisizione_deduce_registri_ministeriali_non_lavoro tests\test_react_shell.py::test_pst_acquisizione_ricerca_non_parte_senza_certificato_preesistente -q`: passato.
- `python -m pytest tests\test_polisweb.py -q`: passato il 03/07/2026 dopo il rinforzo import-only PST, riallineamento route React/legacy e path tenant-aware per portale/soggetti.
- `npm run typecheck` in `frontend`: passato.
- `python -m pytest tests\test_utf8_integrity.py -q`: passato.
- `git diff --check`: passato dopo i fix UI.
- `python -m pytest tests\test_react_shell.py::test_pst_acquisizione_ricerca_non_parte_senza_certificato_preesistente -q`: passato dopo la correzione `Nessun passaggio avviato`.
- Prima della correzione `idCat` erano già passati i test mirati su ricerca SIECIC, mantenimento percorso generico SIECIC, batch con sessione view e badge React senza codici tecnici; rilanciare i gate indicati nella checklist se si toccano di nuovo UI, runtime o parser.

Stato verifica reale 03/07/2026: copia Docker locale reale ricostruita con `docker compose build --no-cache app`, riavviata con `docker compose up -d app` e `/api/pronto` verificato su `http://127.0.0.1:8080` (`ok=true`, versione `2.253.152`, timestamp `03/07/2026 01:16` Europe/Rome; container `iusentra-app` healthy). Browser integrato autenticato sulla stessa scheda reale `http://127.0.0.1:8080/portali/pst/acquisizione`: pagina caricata, menu registri visibile con le etichette professionali sopra elencate, nessun riferimento visibile a Studio Telematico, QuickOrganizer o `JPW`, nessun `Failed to fetch`, nessun timestamp ISO, nessuna data con virgola. Prova materiale del select: selezionato `Minorenni`, poi selezionato `Automatica`; il valore torna vuoto e il menu mostra `Automatica`. Responsive verificato con viewport desktop `1280x720`, tablet `900x900` e mobile `390x844`: scroll fino al fondo, nessun overflow orizzontale, nessun testo tecnico vietato, nessun timestamp raw.

Verifica reale aggiuntiva 03/07/2026 dopo la correzione del pannello di avanzamento: copia Docker locale ricostruita con `docker compose build app`, riavviata con `docker compose up -d app`, `/api/pronto` verificato su `http://127.0.0.1:8080` alle `02:18` Europe/Rome con container `iusentra-app` healthy. Nel browser integrato è stato caricato il bundle React `index-DjwyyfRQ.js`; click reale su `Cerca fascicoli` senza certificato CNS/CIE locale: il flusso non produce dati finti, mostra il messaggio puntuale sul certificato mancante e il riquadro di avanzamento contiene `Ricerca non avviata` / `Nessun passaggio avviato`, con `0` barre `<progress>`. Riprovato il menu `Tabella ministeriale`: `Minorenni`, `Giudice di Pace` e reset `Automatica` funzionano senza `JPW`, Studio Telematico, QuickOrganizer, timestamp ISO o date con virgola. Controllo responsive leggero sullo stesso browser reale: desktop `1280x720`, tablet `900x1000` e mobile `390x844` senza overflow orizzontale e senza testi tecnici vietati; viewport reset eseguito.

Nota dati reale 03/07/2026: durante la prova UI il tenant locale `tenant-8bf98719c459` aveva `studio.db` corrotto e il container bloccava `/api/v1/ui/telematico`. Il database è stato recuperato da snapshot SQLite valido `.studio.migrazione-20260703005431140775.db`, preservando una copia del DB corrotto in `data/tenants/tenant-8bf98719c459/backup/sqlite_corrupt_recovery/studio_corrotto_20260703_005611.db`. Dopo ripristino `PRAGMA quick_check=ok`; per la copia Docker locale su bind mount Windows il journal SQLite è stato riportato a `DELETE`, evitando il blocco `unable to open database file`.

## Checklist prima di dichiarare completata la tranche

- File di matrice registri implementato o equivalente in codice.
- Test unitari per la scelta metodo per `CC`, `LAV`, `VG`, `MIN`, `ESM`, `ESIM`, `FALL`, `GP/GDP`, `CASSCI`, `CASSPE`.
- Test parser su campi `idDfa`, `subpro`, `idCat`, `idDocumento`, `registro`.
- Test runtime: la UI inoltra registro/servizio/ruolo fino al client.
- Test import: fascicolo, parti, storico, documenti, agenda e scadenze salvati nel tenant.
- Verifica reale su `127.0.0.1:8080` con browser visibile per pannello ricerca/import.
- Report deve indicare cosa è stato visto nella UI reale; se non eseguito, scrivere `non verificato su macchina reale`.
