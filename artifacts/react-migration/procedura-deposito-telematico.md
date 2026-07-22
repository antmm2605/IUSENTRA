# Procedura deposito telematico IUSENTRA

## Aggiornamento 2026-07-22 - Presidio notifica e acquisizione PST senza riavvio del Local Signer

Caso reale controllato dal presidio notifiche in produzione, tenant Studio Legale Giuseppe Montagnese: `Romeo Maria`, R.G. `1428/2026`, `Tribunale di Palmi`, presidio `f5480e4d-5fc1-498f-8259-078dcc17fe84`, PEC sorgente `pec_d23c133a4ef8ada88ecb8c08`, documento da PEC ufficio `9732730s.pdf.zip`.

Passaggio completo da preservare:

1. dal presidio notifiche l'avvocato apre `Acquisisci originale`;
2. il wizard PST è già compilato con fascicolo, R.G., ufficio, registro, tabella ministeriale, assistito e PEC sorgente;
3. il Local Signer conferma il certificato PST sul PC dell'avvocato;
4. dopo certificato confermato, il frontend non deve più inviare `iusentra-local-signer://restart` né riavviare il servizio locale prima della ricerca;
5. la ricerca deve usare la sessione già autenticata e portare al solo provvedimento indicato dalla PEC;
6. l'import deve salvare il documento originale nel fascicolo, evitare duplicati e collegare lo stesso originale a relata, Agenda, Scadenziario, topbar e Web Push, senza effettuare alcun invio PEC.

Difetto individuato nel test reale: dopo `Certificato confermato; lettura dati dal portale ufficiale`, la UI richiamava `checkLocalSigner(true)` perché lo stato React non era ancora aggiornato, provocando l'apertura del protocollo locale e il possibile riavvio del Local Signer tra pre-controllo certificato e ricerca PST. L'effetto visibile era il falso errore `Canale locale non raggiungibile`, pur con Local Signer `1.6.102` raggiungibile e certificato presente.

Correzione applicata: in `frontend/src/components/TelematicoSurfacePage.tsx`, `executeSearch()` considera `precheckedPstCert` come prova sufficiente del Local Signer già vivo nella stessa operazione e costruisce uno stato locale `ok=true` senza auto-start. L'auto-start resta ammesso solo se il certificato PST non è stato ancora confermato.

Guardrail eseguiti prima del deploy di questa correzione:

- `python -m pytest tests/test_react_shell.py::test_react_wizard_pst_verifica_local_signer_dal_browser tests/test_react_shell.py::test_pst_acquisizione_ricerca_non_parte_senza_certificato_preesistente -q` → `2 passed`;
- `pnpm --dir frontend build`.

Stato operativo: il fix elimina il riavvio improprio del Local Signer nel passaggio presidio → PST. Prima di dichiarare chiuso il flusso resta obbligatoria la prova reale post-deploy dal presidio in produzione e, se il PST risponde, la verifica che il documento originale acquisito compaia nel fascicolo e alimenti relata, Agenda, Scadenziario, topbar e Web Push senza invio PEC.

## Aggiornamento 2026-07-22 - Riconciliazione presidio con documento PST già nel fascicolo

Caso reale emerso dopo la prova di acquisizione: nel fascicolo `78D6022C` del tenant Studio Legale Giuseppe Montagnese è già presente `SentenzaDefinitiva_35882174.pdf`, documento `DE29EE7F`, importato da PolisWeb/PST il 22/07/2026 con origine `pst:JPW_SIL_DISTR:35882174`, tipo atto portale `SentenzaDefinitiva` e impronta SHA-256 `ea33441ec44017f7b7525e52fda19b4f29d030bccac0afe6cc248b12b189a2da`.

Regola operativa fissata nel codice: il dettaglio del presidio non deve chiedere un nuovo scaricamento quando il documento PST decisorio è già nei Documenti e atti dello stesso fascicolo. La copia ZIP ricevuta via PEC resta evidenza della comunicazione di cancelleria, ma non è trattata come originale notificabile se esiste un documento PST collegabile.

Comportamento atteso:

1. aprendo il presidio, il backend legge solo il fascicolo già collegato al presidio;
2. considera soltanto documenti provenienti da PST/PolisWeb e di natura decisoria, come sentenza, provvedimento, ordinanza, decreto o verbale;
3. esclude documenti non decisori o non notificabili, come ricorsi, memorie, istanze, note, ricevute, esiti controlli e accettazioni deposito;
4. se trova un solo documento coerente, lo collega come `portal_original`, aggiorna lo stato a `ORIGINAL_ACQUIRED` e materializza la stessa fonte su relata, Agenda, Scadenziario, topbar e Web Push;
5. se non trova un documento coerente, mantiene il percorso `Scarica dal portale` già compilato e tenant-aware;
6. ogni apertura deve usare il lettore interno IUSENTRA tramite route del fascicolo, senza uscire dal software e senza invii PEC.

Guardrail aggiunti:

- `tests/test_pst_original_presidio_runtime.py::test_presidio_riconosce_provvedimento_pst_gia_presente_nel_fascicolo`;
- `tests/test_notification_presidia_payloads.py::test_dettaglio_presidio_collega_documento_pst_gia_presente_nel_fascicolo`.

Stato: test automatici mirati superati. Restano obbligatori deploy della correzione, prova reale in produzione dal presidio `f5480e4d-5fc1-498f-8259-078dcc17fe84`, verifica locale reale su `127.0.0.1:8080`, commit, push, deploy finale e pulizia.

## Aggiornamento 2026-07-22 - Ripristino contratto PST Locri, Local Signer 1.6.102 e sessioni download

Problema reale segnalato in produzione durante acquisizione mirata da PEC dell'ufficio per `Calabrò Daniela`, R.G. `3571/2025`, `Tribunale di Locri`, tabella `SICID_LAVORO`: il wizard mostrava `Impossibile determinare codice GL/servizio PST dell'ufficio selezionato`. La causa tecnica non era il fascicolo e non era il PIN: la UI consentiva la scelta di Locri dal catalogo PST pubblico (`0800430095`), mentre il resolver usato dal Local Signer dipendeva dallo snapshot ministeriale locale e non ricostruiva il codice GL/servizio quando quell'ufficio mancava dallo snapshot.

Correzione applicata:

- il resolver centrale `pct/uffici_giudiziari.py` legge anche il catalogo PST pubblico governato e, quando un ufficio civile non è presente nello snapshot ministeriale interno, ricostruisce una scheda tenant-agnostica con `codice_ministero`, `codice_gl` dedotto dal prefisso ministeriale già validato e servizi PST compatibili;
- per Tribunale/Corte d'appello/TM sono stati resi espliciti i servizi lavoro `JPW_SIL_DISTR`, `JPW_SIL`, `JPW_SILP_DISTR`, `JPW_SILP` e gli alias `LAV`, `LAVORO`, `SICID_LAVORO`, `PREVIDENZA`;
- il Local Signer usa lo stesso criterio anche in modalità snapshot/installato, quindi non resta dipendente dal solo file `uffici_ministero.json`;
- il batch download PST distingue ora in modo rigido tra sessione `view` e sessione `import`: riusa la sessione di visualizzazione solo se è autenticata e coerente con lo stesso servizio; se il documento richiede un servizio diverso o la sessione non è pronta, apre una sessione `import` governata senza warm-up/PIN separato;
- versione Local Signer portata a `1.6.102` e pacchetti dist rigenerati, così l'auto-update può rilevare che la build installata `1.6.101` non contiene il contratto corretto.

Guardrail eseguiti:

- `python -m pytest tests/test_reginde.py::test_catalogo_pst_pubblico_risolve_ufficio_civile_non_presente_nello_snapshot_ministeriale tests/test_local_signer.py::test_local_signer_risolve_locri_da_catalogo_pst_pubblico_quando_snapshot_ministeriale_manca tests/test_local_signer.py::test_local_signer_ha_guardia_istanza_unica_e_diagnosi_certificato tests/test_local_signer.py::test_wizard_pst_usa_snapshot_e_sessione_unica_anche_per_download tests/test_local_signer.py::test_local_signer_pst_curl_attiva_foreground_prompt_pin_windows tests/test_local_signer.py::test_run_curl_windows_silenzia_console_senza_perdere_foreground_pin tests/test_local_signer.py::test_local_signer_cleanup_termina_operazione_governata_e_ripulisce_prompt tests/test_local_signer.py::test_batch_curl_arresta_intero_lotto_al_primo_annullamento tests/test_local_signer.py::test_pst_preflight_import_riusa_sessione_view_attiva_senza_nuovo_handshake tests/test_local_signer.py::test_pst_download_batch_riusa_sessione_view_anche_se_client_chiede_import tests/test_local_signer.py::test_pst_download_batch_senza_sessione_autenticata_non_invia_cookie_non_pronti tests/test_local_signer.py::test_pst_download_batch_senza_sessione_crea_import_nuova tests/test_local_signer.py::test_pst_download_batch_applica_servizio_documenti_su_sessione_import tests/test_deposito.py::test_api_pkcs11_firma_documenti_batch_usa_una_sola_sessione tests/test_deposito.py::test_deposito_invia_pec_reale_richiede_sempre_local_signer_anche_con_smtp_server_abilitato tests/test_impostazioni_firma.py::test_script_impostazioni_firma_verifica_local_signer_sul_pc_locale tests/test_impostazioni_firma_local_signer_versione_react.py::test_impostazioni_firma_mostra_versione_e_pacchetto_windows_ufficiale tests/test_local_signer_installer_atomic.py -q` → `22 passed`;
- `python -m py_compile tools/local_signer.py pct/uffici_giudiziari.py tools/dist/local_signer.py`.

Stato operativo: la correzione è pronta per riallineamento locale/server. Prima di dichiarare chiuso restano obbligatori build locale reale `127.0.0.1:8080`, pubblicazione su `https://app.iusentra.it`, verifica `/impostazioni?tab=firma` con Local Signer aggiornabile a `1.6.102`, controllo `/api/pronto`, container Hetzner unico `iusentra-app` e prova materiale dell'acquisizione senza invio PEC reale.

## Aggiornamento 2026-07-20 - Topbar e prova notifica campione

La topbar non ricalcola fascicoli, PEC o documenti quando l'avvocato apre la campanella: legge esclusivamente il repository persistente tenant-aware. I job/eventi a monte materializzano i presidi e le relative notifiche; questa separazione è obbligatoria per evitare caricamenti lenti, duplicati o risultati diversi tra Presidio, Agenda e topbar.

Sul tenant Studio Legale Giuseppe Montagnese sono stati verificati in produzione, come campione non esteso, Romeo Maria/R.G. 1428/2026 e Alfano Giuseppe/R.G. 1100/2026. In entrambi i casi la comunicazione di cancelleria non è stata trattata come prova della notifica dell'avvocato: il sistema mostra `Sentenza da valutare per la notifica` e non registra una notifica come eseguita.

Il canale Web Push è configurato lato server, ma la prova di consegna al dispositivo richiede sottoscrizione browser e consenso dell'utente; non è stata eseguita né simulata. Prima della chiusura restano obbligatori prova locale su `127.0.0.1:8080`, eventuale prova senza invio della relata e audit dei soli residui reali.

## Aggiornamento 2026-07-20 - Presidio persistente notifiche legali

Il flusso Notifiche legali introduce un presidio persistente, tenant-aware e governato da SQL per seguire ordini di notifica, originali da acquisire, relate, RAC/RdAC, mancate consegne e prova da depositare senza rileggere la casella PEC o il fascicolo durante le GET della UI.

Regole operative confermate:

- l'invio PEC legale resta sempre dal PC dell'avvocato tramite Local Signer/servizio locale; il server prepara, classifica e conserva evidenze, ma non diventa canale SMTP reale;
- il flag globale spento non interroga tenant, repository, mailbox, ZIP, OCR, PDF o fascicoli;
- la modalità primaria per tenant mostra la vista React `Presidi notifiche` come superficie iniziale, mentre il workflow storico viene caricato solo quando l'utente seleziona `Operazioni di notifica`;
- lista, contatori e filtri leggono proiezioni SQL paginate e indicizzate; dettaglio, evidenze e transizioni si caricano solo su richiesta;
- gli stati per destinatario distinguono RAC, RdAC, consegna parziale e mancata consegna; una failure incerta resta in revisione umana e non viene chiusa automaticamente;
- ogni data/ora visibile resta in italiano e in fuso `Europe/Rome`.

Prova server eseguita sul tenant `Studio Legale Giuseppe Montagnese`:

- `https://app.iusentra.it/notifiche-legali` caricata in sessione autenticata come amministratore;
- sezione `Presidi notifiche` visibile, nessun errore console e caricamento osservato sotto il baseline richiesto;
- click reali su code, filtri, `Applica`, `Azzera`, `Aggiorna`, stato vuoto e ritorno dal workflow storico lazy;
- asset produzione controllati nel container con chunk JavaScript massimo sotto `500.000` byte;
- nessuna PEC reale, firma digitale o registrazione di notifica effettiva è stata eseguita durante il collaudo.

Stato di chiusura della tranche: prima del report finale restano obbligatori riallineamento e prova della copia locale reale `127.0.0.1:8080`, commit, push dei branch gemelli, deploy Hetzner finale sullo stesso commit, container `iusentra-app` unico/healthy e controllo `/api/pronto`.

## Aggiornamento 2026-07-19 - Uffici deposito, alias reali e audit fallente

Caso bloccante emerso in produzione: nel deposito del fascicolo `F7AA4E0C` l'ufficio veniva mostrato come `TRIBUNALE DI REGGIO DI CALABRIA`, mentre il catalogo ministeriale interno contiene `Tribunale di Reggio Calabria`. Il risultato era PEC non disponibile e codice ufficio non risolto.

Correzione applicata:

- il resolver centrale `pct/uffici_giudiziari.py` normalizza articoli, preposizioni e qualificatori non essenziali nei nomi ufficio;
- sono coperti alias reali di pratica come `TRIBUNALE DI ...`, `TRIBUNALE ORDINARIO DI ...`, `GIUDICE DI PACE DI ...`, `Corte d'Appello di ...` e varianti con trattino;
- quando esistono righe storiche `ex` o `non attivo`, viene preferita la riga operativa con PEC e codice completo;
- il payload React deposito usa il resolver centrale prima del fallback testuale interno.

Guardrail aggiunti:

- `tests/test_reginde.py::test_risoluzione_tribunale_reggio_calabria_accetta_alias_pratica_reale`;
- `tests/test_reginde.py::test_risoluzione_gdp_preferisce_ufficio_attivo_con_pec_su_alias_storico`;
- `scripts/audit_deposito_catalogo_end_to_end.py` prova ora alias reali per tutti gli uffici PCT operativi e fallisce se un solo alias non produce PEC/codice verificati.

Esito audit locale del 19/07/2026: 270 tipi deposito controllati, 252 generatori PCT, 18 UNEP, 593 uffici PCT operativi coperti, 0 uffici mancanti, 0 PEC/codici mancanti, 0 errori del resolver React deposito.

## Aggiornamento 2026-07-09 - Selezione documenti deposito e avvisi non bloccanti

Ambito: flusso React `Prepara deposito`, fase `Documenti da inviare` e fase `Pacchetto deposito`, con caso guida produzione `FB586324`.

Confronto operativo effettuato:

- fonte ministeriale corrente verificata: PST Giustizia, `Specifiche Tecniche ex art. 34 DM 44/2011 - Provvedimento 7 agosto 2024`, efficaci dal 30/09/2024, con avvisi di rettifica pubblicati sulla stessa scheda PST;
- nel materiale decompilato QuickOrganizer/Studio Legale Telematico il deposito lavora con atto principale distinto e lista allegati dedicata, poi costruisce `IndiceBusta.AttoPrincipale` e `IndiceBusta.Any` dai documenti presenti nella lista del deposito;
- il passaggio completo osservato nel decompilato conferma la sequenza: selezione atto principale, griglia allegati del deposito, generazione `DatiAtto.xml`, firma del metadato, busta con indice e allegati, cifratura in `Atto.enc`, preparazione PEC con allegato unico di deposito e invio tramite account PEC configurato;
- il comportamento coerente per IUSENTRA è quindi: il software legge tutto il fascicolo e segnala candidati, ma la busta usa solo i documenti collegati o selezionati/salvati dall'avvocato;
- gli slot documentali obbligatori non devono spegnere prova e simulazione se l'atto principale è già selezionato e il destinatario PEC dell'ufficio è verificato. Devono restare avvisi puntuali, non blocchi generici.

Modifiche applicate:

- rimossa l'autoselezione di tutti i documenti candidati nella fase `Documenti da inviare`;
- rimosso il comando `Invia tutto`, sostituito da `Ripristina documenti collegati`;
- `Firma e prepara prova` e `Simula invio PEC` restano disabilitati solo se manca l'atto principale o la PEC ufficio verificata;
- le scelte richieste ancora da verificare vengono mostrate come avviso con nome documento/slot, senza testo generico che non spiega quale scelta manca;
- il payload operativo continua a usare `documenti_selezionati_ids` derivato da `packageDocuments`, quindi solo dai documenti scelti nella UI.

Guardrail eseguiti:

- `python -m pytest tests/test_regia_ui_react.py::test_ui_deposito_prepara_legge_intero_fascicolo_e_distingue_canale tests/test_regia_ui_react.py::test_ui_deposito_avvisi_classificazione_non_spengono_prova_e_non_autoselezionano_tutto tests/test_regia_ui_react.py::test_ui_deposito_prova_guidata_non_salta_firma_e_mostra_audit_pec_indice -q`;
- `npm --prefix frontend run typecheck`;
- `npm --prefix frontend run build`;
- `python -m pytest tests/test_regia_api_payloads.py::test_api_deposito_classifica_documenti_collega_slot_e_metadati tests/test_regia_api_payloads.py::test_api_deposito_classifica_documenti_non_richiede_firma_su_contenitore_p7m tests/test_regia_api_payloads.py::test_api_deposito_classifica_documenti_non_cade_se_profilo_da_confermare tests/test_deposito_server_dry_run_audit.py::test_runner_server_dry_run_usa_proposta_react_e_prove_notifica -q`;
- `python -m py_compile web/services/deposito_route_helpers.py web/blueprints/api_v1_react.py`;
- `python -m pct.cli utf8-integrity --check-only --root frontend/src/components/FascicoloDepositoPage.tsx --root tests/test_regia_ui_react.py --root CHANGELOG.md --root artifacts/react-migration/procedura-deposito-telematico.md --json`.

Riscontro dai log reali già registrati:

- simulazione produzione `123E2EB2`: `IndiceBusta.xml` prima parte MIME, `DatiAtto.xml.p7m` presente, atto principale unico, allegati allineati, `Atto.enc` CMS `EnvelopedData` valido con algoritmo `aes256_cbc`, `OVERALL_OK=True` nella busta reale post-click;
- deposito PCT reale `795C50AC`: esito ministeriale `IDBUSTA 152649431`, `CodiceEsito=2`, `Accettazione manuale avvenuta con successo`, `NumeroRuolo=1084/2026`; il deposito risulta registrato nel fascicolo come `ACCETTATO_CANCELLERIA`;
- questa tranche non modifica le regole già validate su `IndiceBusta.xml`, `DatiAtto.xml.p7m`, `Atto.enc`, oggetto/corpo PEC, canale Local Signer o presidio ricevute.

Verifica produzione eseguita il 09/07/2026 su `https://app.iusentra.it/fascicoli/FB586324/deposito/prepara#generazione-busta`:

- pagina React caricata con `#root`, versione `/api/pronto` `2.254.18`, container `iusentra-app` unico e healthy;
- vecchio messaggio `1 scelte obbligatorie richiedono la selezione dell'avvocato` assente;
- comando `Invia tutto` assente; presenti `Ripristina documenti collegati`, `Deseleziona tutto`, `Salva classificazione`;
- `Firma e prepara prova` abilitato e con click reale apre la conferma di firma/preparazione prova;
- `Simula invio PEC` abilitato, con click reale apre conferma e, dopo conferma, avvia la simulazione senza spedizione esterna;
- la simulazione si ferma sul requisito reale `Local Signer non rilevato / non raggiungibile su questo PC`, senza `Message-ID` e senza conferma di invio PEC reale;
- `Invia deposito reale` resta disabilitato solo con motivo puntuale `Esegui prima la prova senza invio reale`;
- l'avviso residuo `Ricevuta contributo unificato` è mostrato come avviso non bloccante e dichiara che la scelta salvata dall'avvocato resta prevalente;
- controlli responsive desktop, tablet e mobile: nessun overflow orizzontale, nessun ritorno dei riferimenti tecnici vietati nella UI, pulsanti principali coerenti.

Stato: prova produzione reale eseguita con click sicuri e senza invio PEC esterno. Restano obbligatorie verifica locale reale su `127.0.0.1:8080`, commit, push branch gemelli, deploy Hetzner dal commit finale e controlli container/CI prima della chiusura.

### Audit catalogo depositi end-to-end - 09/07/2026

Richiesta utente: non limitare il confronto al caso reale già accettato, ma verificare ogni tipo deposito del catalogo contro la logica ricostruita dal decompilato e contro le regole ministeriali, senza falso verde.

Intervento:

- aggiunto `scripts/audit_deposito_catalogo_end_to_end.py`;
- il catalogo backend `pct/deposito_telematico_catalogo.py` ora recupera rami che il JSON menu non esponeva correttamente: `Ricorso702Bis`, memorie/istanze Cartabia, richiesta visibilità, pignoramenti SIECIC, progetto distribuzione CTU e deposito relazione iniziale del curatore;
- `Ricorso702Bis` non ricade più su un generatore senza classe: viene associato a `IntroduttiviSicid` e radice `Ricorso702Bis`;
- le memorie/istanze Cartabia vengono ricondotte al generatore comune `MemorieCartabia`;
- il refuso storico `Professionista_ESECUZIONI_SIECIC::Progett369oDistribuzione` viene normalizzato in `Professionista_ESECUZIONI_SIECIC::ProgettoDistribuzione`;
- la voce storica senza chiave `Atti del Curatore` viene normalizzata in `Curatore_CONCORSUALI_SIECIC::DepositoRelazioneIniziale`, conservando l'alias tecnico interno per tracciabilità;
- i rami che richiedono campi strutturati non ancora modellati nel nostro generatore non possono abilitare l'invio reale.

Esito audit:

- tipi totali controllati: `270`;
- PCT: `252`;
- UNEP/notifiche: `18`;
- PCT con `DatiAtto.xml` sintetico generato e radice verificata: `243`;
- PCT riconosciuti ma con invio reale sospeso fino a generatore/maschera dedicata: `9`;
- errori audit: `0`;
- comando: `python scripts/audit_deposito_catalogo_end_to_end.py`;
- test guardrail: `python -m pytest tests/test_deposito_telematico_catalogo.py -q`.

I 9 casi sospesi non sono scartati e non sono generici: sono mappati con chiave, radice, classe generatore e metodo di origine, ma restano bloccati per l'invio reale perché richiedono dati specifici che non devono essere inventati:

- `Parte_SICID::AttoRichiestaVisibilità`;
- `Parte_ESECUZIONI_SIECIC::AttoRichiestaVisibilità`;
- `Parte_CONCORSUALI_SIECIC::AttoRichiestaVisibilità`;
- `CorsoCausa_SIGP::AttoRichiestaVisibilità`;
- `Introduttivi_ESECUZIONI_SIECIC::IscrizioneRuoloPignoramentoImmobiliare`;
- `Introduttivi_ESECUZIONI_SIECIC::IscrizioneRuoloPignoramentoMobiliarePressoDebitore`;
- `Introduttivi_ESECUZIONI_SIECIC::IscrizioneRuoloPignoramentoMobiliarePressoTerzi`;
- `Professionista_ESECUZIONI_SIECIC::ProgettoDistribuzione`;
- `Curatore_CONCORSUALI_SIECIC::DepositoRelazioneIniziale`.

Stato corretto: copertura anti-falso-verde su `270/270`; invio reale automatizzato verificabile su `243/252` tipi PCT nel perimetro attuale; `9/252` tipi PCT richiedono tranche dedicata con campi UI/API e generatore nostro prima di poter essere dichiarati inviabili. Non va dichiarata accettazione ministeriale al 100% per quei 9 finché non sono prodotti XML e busta reali con dati completi.

### Aggiornamento audit severo catalogo depositi - 09/07/2026

Lo stato precedente `243/252` con `9/252` sospesi è superato da questa tranche. Non va più usato come stato operativo corrente.

Intervento correttivo:

- completata la generazione IUSENTRA dei rami critici: richieste visibilità SICID/SIECIC/SIGP, pignoramenti SIECIC, progetto distribuzione, deposito relazione iniziale curatore;
- `pct/deposito_telematico_catalogo.py` non marca più quei rami come `generatore dedicato da completare`;
- `web/services/deposito_catalogo_runtime.py` porta i dati specialistici in `datiatto_extra`;
- `web/bootstrap/deposito_routes.py` passa `datiatto_extra` a `DatiBusta` nelle azioni di generazione busta e prova/invio PEC;
- `frontend/src/components/FascicoloDepositoPage.tsx` non blocca la prova solo perché il flag storico `verified` non è già vero: profilo deposito e catalogo uffici vengono fusi automaticamente; se PEC e codice ufficio sono presenti, la prova può tentare il recupero del certificato dell'ufficio; se un dato non viene risolto, la UI lo indica come mancata risoluzione automatica di IUSENTRA/catalogo, non come dato manuale lasciato all'avvocato;
- `scripts/audit_deposito_catalogo_end_to_end.py` ora è severo: se torna un solo ramo PCT sospeso, se manca una radice, se manca un campo XML essenziale, se manca indice documenti/indice busta o se manca il contratto Local Signer/PEC locale, lo script fallisce.

Campi XML controllati in modo esplicito dallo script:

- richiesta visibilità: `Parte`, `Avvocato`, `codiceFiscale`, `parteRappresentata`, `procedimento`;
- pignoramento SIECIC: `AnagraficaProcedimento`, `DataConsegnaPignoramento`, `ImportoPrecetto`, `Beni`, `EstensioneAnagrafica`, `DatiDebitore`, `DatiProcedente`, `EstensioneDatiRito`, `titolo`, `titoloEsecutivo`, `benePignorato`, più `Custode` o `DatiTerzo` quando richiesti;
- progetto distribuzione: `procedimento`, `deposito`, `depositoPianoRiparto`;
- relazione iniziale curatore: `procedimento`, `numero`, `anno`;
- rami introduttivi PCT: `destinazione`, `Oggetto`, `AnagraficaProcedimento`;
- rami in corso causa/professionista/curatore: `procedimento`, `numero`, `anno`.

Esito nuovo:

- comando: `python scripts/audit_deposito_catalogo_end_to_end.py --output artifacts/react-migration/audit-deposito-catalogo-end-to-end-2026-07-09.json`;
- generatori PCT: `252/252`;
- rami sospesi: `0`;
- confronto uffici PCT operativi contro `C:\QuickOrganizer\ListaUfficiGiudiziari.xml`, `C:\QuickOrganizer\QC_Uffici.xml` e fonti PST/ministeriali importate: `593/593`;
- differenze PEC/codice ufficio sul perimetro operativo: `0`;
- errori resolver React PEC/codice: `0`.
- `ok=true`;
- tipi totali controllati: `270`;
- PCT: `252`;
- UNEP/notifiche: `18`;
- PCT con `DatiAtto.xml` generato e controllato: `252/252`;
- rami PCT sospesi: `0`;
- errori: `0`;
- report salvato: `artifacts/react-migration/audit-deposito-catalogo-end-to-end-2026-07-09.json`.

Guardrail eseguiti:

- `python -m pytest tests/test_deposito_telematico_catalogo.py -q` -> `9 passed`;
- `python -m pytest tests/test_regia_ui_react.py::test_ui_deposito_prova_guidata_non_salta_firma_e_mostra_audit_pec_indice tests/test_regia_ui_react.py::test_ui_deposito_avvisi_classificazione_non_spengono_prova_e_non_autoselezionano_tutto -q` -> `2 passed`;
- `python -m pytest tests/test_busta.py tests/test_canali_telematici_deposito.py tests/test_local_signer.py::test_catalogo_servizi_get_certificato_parser_estrae_base64 tests/test_local_signer.py::test_local_signer_espone_endpoint_certificato_ufficio_pst -q` -> `50 passed`;
- `python -m py_compile scripts/audit_deposito_catalogo_end_to_end.py pct/busta.py pct/deposito_telematico_catalogo.py web/services/deposito_catalogo_runtime.py web/bootstrap/deposito_routes.py`;
- `npm --prefix frontend run typecheck`.

Limite operativo corretto: `252/252` dimostra che i generatori e il pacchetto preparatorio sono coperti sul perimetro testato. La conferma del singolo deposito reale richiede comunque firma effettiva, `Atto.enc` generato con certificato dell'ufficio, PEC locale dal PC dell'avvocato, ricevute ed esito dell'ufficio.

## Aggiornamento 2026-07-07 - Ruleset presidio processuale e CU da RT XML

Ambito: presidio fascicoli/documenti, PEC, controllo economico e classificazione preventiva dei documenti.

Regola operativa aggiunta:

- il motore non deve cercare importi o scadenze in modo indistinto;
- prima classifica il documento dal contenuto, anche se nome file o tipo importato da QuickOrganizer/Studio Telematico sono generici o sbagliati;
- poi attiva il parser coerente con quella classe: CU/pagoPA, esenzione, SIAMM/LSG, sentenza, udienza, notifica, deposito, appello, Cassazione, Giudice di Pace, volontaria giurisdizione, famiglia/minori, esecuzione, ADR, concorsuale;
- `SIAMM` non significa automaticamente gratuito patrocinio: il ruleset distingue `Liquidazione spese di giustizia / SIAMM` da `Patrocinio a spese dello Stato`;
- una ricevuta telematica pagoPA RT XML può popolare il contributo unificato solo se contiene marcatori ministeriali di contributo/spese di giustizia, come `0702100TS`, `CONTRIB`, `causaleVersamento`, `datiSpecificiRiscossione`, `importoTotalePagato` o `singoloImportoPagato`;
- la frase generica `spese di giustizia` non basta più a classificare un documento come contributo unificato.

Caso guida coperto:

- fascicolo `Alfano Giuseppe / RG 1100/2026`;
- documento `rt_33E000GLVE6L4BIFLARMYPA0VKIRL7DIRYT.xml` importato come `ATTO_GIUDIZIARIO`;
- importo RT XML `€ 49,00`, data esito `12/05/2026`, fonte visibile `rt_33E000GLVE6L4BIFLARMYPA0VKIRL7DIRYT.xml`.

File e prove tecniche:

- ruleset: `pct/presidio_processuale_ruleset.py`;
- catalogo: `pct/fascicolo_document_catalog.py`;
- bridge economico React: `web/services/react_fascicoli_bridge.py`;
- dossier fonti e query: `artifacts/react-migration/presidio-processuale-ricerche-fonti-2026-07-07.md`;
- report implementazione: `artifacts/react-migration/presidio-processuale-implementazione-2026-07-07.md`;
- test mirati: `tests/test_presidio_processuale_ruleset.py`, `tests/test_fascicolo_document_catalog.py`, `tests/test_react_shell.py`.

Stato: logica tecnica implementata e coperta da test mirati; verifica reale locale su `127.0.0.1:8080` eseguita nella vista economica dopo rebuild Docker. Restano obbligatori deploy/controllo server `https://app.iusentra.it`, commit, push e verifica container Hetzner prima della chiusura.

## Fascicoli - proforma automatica in bozza e presidio economico server 2026-07-06

Ambito: fascicoli del tenant produzione `studio-legale-giuseppe-montagnese`, controllo economico, sentenze, contributo unificato, bozze proforma e assenza di doppioni.

Regola professionale confermata:

- la proforma deve essere automatica quando il fascicolo contiene una base economica certa;
- il documento generato resta `BOZZA` e non viene emesso automaticamente;
- la UI deve dire all'avvocato che la bozza è da visionare e confermare prima dell'emissione;
- il motore non deve creare documenti fittizi quando mancano sentenza, liquidazione o compenso pattuito;
- una parcella/proforma attiva già presente impedisce nuove bozze duplicate;
- in presenza di stesso cliente e stesso RG il software segnala la riconciliazione prima di aggiornare economia o proforma.

Modifiche applicate:

- `web/services/react_fascicoli_bridge.py` espone `proformaPresidio`, crea bozze automatiche da sentenza o da compenso pattuito/preventivato e legge sentenze fisiche PDF/testo quando non ancora indicizzate;
- `pct/fascicolo_sentenza_economica.py` normalizza gli RG importati con zeri iniziali, così una sentenza `00001548/2026` può alimentare il fascicolo `RG 1548/2026` se cliente e contesto coincidono;
- `frontend/src/components/FascicoliPage.tsx` mostra `Bozza proforma da visionare`, fonti leggibili e stati `Da verificare`/`Da calcolare` invece di placeholder tecnici;
- la route React `/api/v1/ui/fascicoli/presidio-economico/proforme` avvia il presidio idempotente e non crea duplicati.

Esito dati produzione:

- fascicoli in SQL: 333;
- fascicoli non archiviati visibili in lista: 300;
- stati SQL attuali: 238 `IN_CORSO`, 61 `DEFINITO`, 33 `ARCHIVIATO`, 1 `APERTO`;
- la card `Da archiviare` deve contare solo i 61 `DEFINITO` non archiviati; i 33 già archiviati devono restare nota separata, non sommati al numero principale;
- parcelle/proforme passate da 12 a 21;
- bozze automatiche create: 9;
- fascicoli definiti/archiviati ancora senza proforma/parcella: 78;
- dashboard produzione aggiornata: `ATTIVI 300`, `DA ARCHIVIARE 61`, `DOPPIONI 0`, `REGISTRATO € 14.340,00`, `PARCELLE 67`, `46 da emettere, 21 bozze da visionare`, `DOCUMENTI 13052`.

Prova visiva produzione:

- `https://app.iusentra.it/fascicoli?vista=economica` caricata in sessione autenticata;
- card iniziali verificate: `Da archiviare 61`, nota `61 definiti, 33 già archiviati`, `Parcelle 67`, nota `46 da emettere, 21 bozze da visionare`, `Doppioni 0`;
- riga Betti: proforma `2026/005` visibile come bozza da visionare, liquidazione `€ 1.100,00` e parcella `€ 1.605,03`;
- riga Betti: contributo unificato letto dalla ricevuta pagoPA come `€ 49,00`, stato `Pagato`, data `17/03/2026`, senza esporre il nome tecnico `20260317101453130.PDF`;
- riga Merdini: contributo unificato non previsto con fonte autocertificazione;
- ricerca `Betti`: lista ridotta a una sola riga, filtro verificato;
- nessun `sentenza_key`, `document_id`, `docai` o path tenant visibile nelle evidenze economiche.
- prova locale reale dopo rebuild Docker `2.253.188`: `http://127.0.0.1:8080/fascicoli?vista=economica` carica React nel browser integrato; sul tenant locale disponibile la card `Parcelle` mostra `1 da emettere, 1 bozze da visionare` e le righe economiche mostrano `Da calcolare` / `DA EMETTERE`, senza vecchia formula `da preparare` nella card.

Guardrail automatici eseguiti:

- `python -m py_compile web/services/react_fascicoli_bridge.py pct/fascicolo_sentenza_economica.py`;
- `python -m pytest tests/test_fascicolo_sentenza_economica.py::test_sentenza_con_rg_importato_a_zeri_iniziali_aggiorna_economia tests/test_fascicolo_sentenza_economica.py::test_sentenza_con_cliente_ma_rg_diverso_non_aggiorna_economia tests/test_react_shell.py::test_react_fascicoli_presidio_economico_crea_bozza_proforma_definito tests/test_react_shell.py::test_react_fascicoli_presidio_economico_legge_sentenza_fisica_non_indicizzata -q`.

Stato: hotfix verificato sul server reale e riallineato sulla copia Docker locale `127.0.0.1:8080`; restano obbligatori commit, push branch gemelli, deploy Hetzner dal commit finale e controlli GitHub/CodeQL prima della chiusura.

Aggiornato: 2026-07-06.

## Aggiornamento 2026-07-05 - Clienti, soggetti, sentenze economiche, email mobile e lettore documenti

Richiesta utente: correggere il salvataggio reale del cliente `FBA5C7FF` su produzione, introdurre suggerimento Comune con CAP/provincia per clienti e soggetti, far leggere automaticamente al fascicolo le sentenze utili al controllo economico, migliorare lettura email PEC/ordinaria su tablet/mobile e rendere fruibile l'anteprima documenti su mobile.

Modifiche applicate nel codice locale:

- `frontend/src/formSubmit.ts` ora considera errore operativo ogni risposta non JSON o redirect a login durante i salvataggi AJAX, impedendo il falso messaggio `salvato` quando la sessione è scaduta o il server risponde HTML;
- `web/services/territorio_forms.py`, `web/bootstrap/clienti_routes.py` e `web/bootstrap/soggetti_routes.py` normalizzano Comune, CAP e provincia lato server usando il database territoriale condiviso;
- `frontend/src/components/NuovoClientePage.tsx` usa autocomplete Comuni anche in modifica cliente/soggetto e compila automaticamente CAP/provincia;
- il runtime `web/services/sentenza_economic_runtime.py` legge i documenti candidati del fascicolo tramite Document AI/OCR/search index, senza limite fisso sui primi documenti, e salva audit/eventi economici quando trova sentenze, ordinanze, decreti o provvedimenti rilevanti;
- `frontend/src/components/EmailPecPage.tsx` e CSS mostrano su tablet/mobile l'elenco come vista primaria e aprono la email selezionata in un pannello `Lettura email`;
- `frontend/src/components/FascicoliPage.tsx` e CSS rendono l'anteprima documento un `Lettore documento` mobile/tablet a viewport pieno controllato.

Guardrail automatici eseguiti:

- `npm --prefix frontend run typecheck` -> passato;
- `python -m pytest -q tests/test_react_shell.py::test_react_comunicazioni_email_messaggi_collegate_nav_e_shell tests/test_react_shell.py::test_react_clienti_nuovo_e_soggetti_collegati_nav_api_lex_cf tests/test_react_shell.py::test_submit_form_json_non_accetta_html_come_successo tests/test_react_shell.py::test_post_modifica_cliente_json_normalizza_comune_e_persiste tests/test_react_shell.py::test_post_modifica_soggetto_json_normalizza_comune_e_persiste tests/test_territorio_italia.py tests/test_clienti.py::test_cliente_from_dict_accetta_alias_recapiti_legacy` -> passato;
- `python -m pytest -q tests/test_react_fascicoli_sentenze_economiche.py tests/test_sentenza_economic_runtime.py` -> passato.

Stato verifica:

- diagnosi produzione in sola lettura completata: la scheda `FBA5C7FF` esiste nel tenant SQLite Montagnese, ma il browser integrato non era autenticato e la rotta produzione ha reindirizzato a `/login`;
- non verificato su macchina reale autenticata e non ancora verificato su `https://app.iusentra.it` dopo deploy;
- il lavoro resta aperto finché produzione, locale `127.0.0.1:8080`, GitHub e Hetzner non risultano sullo stesso commit con prova visiva reale su cliente, soggetti, sentenze economiche, email responsive e lettore documenti.

## Aggiornamento 2026-06-29 - Prova produzione fascicolo 795C50AC e Local Signer

Richiesta utente: predisporre il test reale del deposito su `https://app.iusentra.it/fascicoli/795C50AC/deposito/prepara#proposta-busta`, arrivando alla fase in cui l'avvocato inserisce il PIN e tracciando log e stato.

Stato osservato su produzione `2.253.135`, commit server `2d39a1a3ef96d6ae45c0efde8b772a586ffa8542`:

- `/api/pronto` ha risposto `ok=true`, `timezone=Europe/Rome`, `versione=2.253.135`;
- container Hetzner osservati: `iusentra-app-1`, `iusentra-scheduler-worker-1`, `iusentra-ocr-worker-1` healthy;
- pagina React deposito aperta su fascicolo `795C50AC`, `2026/332`, cliente `Marchetti Lucia`, ufficio `Tribunale di Vicenza`, canale `PCT lavoro / SICID`, PEC `tribunale.vicenza@civile.ptel.giustiziacert.it`;
- fase `Documenti da inviare`: `13` documenti selezionati, `Ricorso.pdf.p7m` come atto principale, `Procura.PDF.p7m` come procura, `0` documenti ulteriori da firmare prima della busta;
- fase `Busta e indice`: `DatiAtto.xml` e `IndiceDocumentiDepositati.PDF` risultano generati, testo PEC visibile, pulsanti `Prova senza invio reale`, `Simula invio PEC` e `Invia deposito reale` visibili.

Prova eseguita nella scheda controllata:

- click su `Prova senza invio reale`, conferma modale `Preparare busta, indice documenti, destinatario e testo PEC senza inviare nulla?`;
- barra avanzamento visibile con `DatiAtto.xml`, `DatiAtto.xml.p7m`, `IndiceBusta.xml`, `IndiceDocumentiDepositati.PDF`, documenti selezionati e `Atto.enc`;
- log app Hetzner: `POST /api/v1/ui/fascicoli/795C50AC/deposito/classifica-documenti` `200`, `GET /api/v1/ui/fascicoli/795C50AC/deposito/certificato-cifratura?codice_ufficio=0640011` `200`, `POST /fascicoli/795C50AC/deposito/invia-pec` `200`;
- la prova non ha registrato un nuovo deposito valido e non ha inviato PEC reale: la UI si è fermata prima della firma di `DatiAtto.xml.p7m` con messaggio `Local Signer non raggiungibile dal browser per firmare DatiAtto.xml. Avvia il servizio locale sul PC in uso e ripeti la prova deposito.`

Diagnosi Local Signer sul PC:

- Local Signer locale inizialmente in ascolto su `127.0.0.1:27272`, versione `1.6.83`, ma con `riavvio_signer_consigliato=true`: il controllo fresco vedeva il token `CNS`, mentre il processo attivo non era allineato;
- eseguito riavvio del solo processo Local Signer locale e avvio diretto dello starter installato in `%APPDATA%\IUSENTRA\LocalSigner\start_local_signer.cmd`;
- dopo il riavvio `/ping` locale ha risposto `ok=true`, token `CNS` presente, libreria `C:\Windows\System32\bit4xpki.dll`, certificato firma Windows selezionato `GIUSEPPE MONTAGNESE`, nessun riavvio signer richiesto;
- CORS e Private Network verificati con `Origin: https://app.iusentra.it`: `Access-Control-Allow-Origin: https://app.iusentra.it`, `Access-Control-Allow-Private-Network: true`;
- CSP produzione verificata: `connect-src` consente `http://127.0.0.1:*` e `http://localhost:*`.

Fix applicato e distribuito:

- commit `c3fffbb76d728946c92ac03c4aae6a9b9a1e651c` su `Codex/legal-electronic-filing-kIxcV` e `claude/legal-electronic-filing-kIxcV`;
- deploy Hetzner completato sullo stesso commit, container `app`, `scheduler-worker`, `ocr-worker`, `redis`, `audit-postgres` e `audit-worm` healthy;
- `/api/pronto` produzione ha risposto `ok=true`, `timezone=Europe/Rome`, `versione=2.253.135`;
- bundle React produzione caricato nella pagina reale: `FascicoliPage-B4gZSukh.js`.

Prova reale successiva su Google Chrome dell'utente, pagina già aperta e autenticata:

- finestra reale osservata: `IUSENTRA - Google Chrome`, URL `https://app.iusentra.it/fascicoli/795C50AC/deposito/prepara#generazione-busta`;
- click materiale sul pulsante `Prova senza invio reale` nella pagina Chrome dell'utente;
- modale reale `Prova senza invio` visualizzata con testo `Preparare busta, indice documenti, destinatario e testo PEC senza inviare nulla?`;
- la prova è avanzata su `DatiAtto.xml.p7m` e ha concluso con esito UI `Prova deposito preparata: busta, indice, destinatario e testo PEC sono pronti per il controllo. Nessun invio PEC reale è stato eseguito.`;
- riferimento prova mostrato in UI: `506A6BDB`;
- destinatario PEC mostrato: `tribunale.vicenza@civile.ptel.giustiziacert.it`;
- oggetto PEC mostrato: `DEPOSITO TELEMATICO - RICORSO - Tribunale di Vicenza`;
- report UI `Compatibilità 100%` con controlli `OK`: `Atto.enc ministeriale AES256`, `DatiAtto.xml.p7m firmato`, `IndiceBusta.xml ministeriale`, `IndiceDocumentiDepositati.PDF`, `Atto principale e allegati controllati`, `PEC ufficio giudiziario`, `Oggetto PEC deposito`, `Corpo PEC verificabile`;
- ricevute ancora da presidiare dopo eventuale invio reale: ricevuta di accettazione PEC, RdAC/avvenuta consegna, esito controlli automatici, esito cancelleria;
- Codex non ha inserito, letto o salvato alcun PIN; la verifica si è limitata alla prova senza invio e alla preparazione firmata della busta.

Log produzione della prova Chrome reale:

- `29/06/2026 15:09:22` `POST /api/v1/ui/fascicoli/795C50AC/deposito/classifica-documenti` -> `200`;
- `29/06/2026 15:09:22` `GET /api/v1/ui/fascicoli/795C50AC/deposito/certificato-cifratura?codice_ufficio=0640011` -> `200`;
- `29/06/2026 15:09:23` `POST /fascicoli/795C50AC/deposito/invia-pec` -> `200`, payload controllo iniziale;
- `29/06/2026 15:09:40` `POST /fascicoli/795C50AC/deposito/invia-pec` -> `200`, payload busta circa `50 MB`.

Evidenza visiva temporanea fuori repository:

- `C:\Users\antmm\AppData\Local\Temp\iusentra-chrome-real-after-10s.png`.

## Aggiornamento 2026-06-29 - Esito PST reale negativo IDBUSTA 152631750 e formato MIME Atto.msg

Esito reale successivo alla prova preparatoria sul fascicolo `795C50AC`:

- l'avvocato ha eseguito l'invio reale dal proprio PC tramite Google Chrome e Local Signer; Codex non ha inserito, letto o salvato il PIN;
- ricevute PEC osservate in Aruba: `Ricevuta di accettazione` e `Ricevuta di avvenuta consegna` al destinatario `tribunale.vicenza@civile.ptel.giustiziacert.it`, consegna del `29/06/2026 15:12:44 (+0200)`;
- esito automatico PST ricevuto alle `15:13`: `Codice esito: -1`, `Descrizione esito: --`, `IDBUSTA: 152631750`, messaggio `Indice busta non trovato, necessario effettuare nuovamente il deposito`;
- quindi l'invio PEC locale, il destinatario, la consegna e Local Signer sono risultati operativi, ma il pacchetto ministeriale è stato rifiutato dal parser PST: il deposito non è concluso e non va dichiarato verde.

Causa tecnica individuata:

- il controllo precedente verificava `Atto.msg` con parser Python moderno e `iter_attachments()`, sufficiente a vedere un allegato chiamato `IndiceBusta.xml` ma non sufficiente a simulare il parser ministeriale;
- il vecchio `Atto.msg` era `multipart/mixed`, conteneva prima una parte `text/plain` descrittiva e poi `IndiceBusta.xml` come `application/xml` codificato base64, con nome presente solo in `Content-Disposition`;
- le prove e i campioni accettati mostrano parser e client legacy che identificano le parti MIME anche tramite `Content-Type; name=...`, parti `inline` e struttura `multipart/related`;
- l'esito `Indice busta non trovato` è coerente con un parser che decritta `Atto.enc` ma non censisce `IndiceBusta.xml` come file del contenuto busta.

Correzione applicata nel sorgente locale:

- `pct/busta.py` genera ora `Atto.msg` come `multipart/related` di sole parti file, senza corpo `text/plain` extra;
- `IndiceBusta.xml` è la prima parte file, `Content-Type: text/xml; charset="utf-8"; name="IndiceBusta.xml"`, `Content-ID: <IndiceBusta.xml>`, `Content-Disposition: inline; filename="IndiceBusta.xml"`, `Content-Transfer-Encoding: 7bit`;
- `DatiAtto.xml` non firmato usa `text/xml`; quando firmato resta `DatiAtto.xml.p7m` `application/pkcs7-mime`;
- tutti i file binari restano base64 ma hanno `name`, `filename` e `Content-ID` sicuro;
- la verifica interna di `Atto.msg` cammina tutte le parti MIME file-like, non solo `iter_attachments()`, e blocca parti senza nome file o `IndiceBusta.xml` privo di `name` MIME;
- `scripts/audit_deposito_server_dry_run.py` e i test di busta/simulazione usano la stessa logica, così il vecchio falso positivo non può rientrare nel gate.

Guardrail eseguiti sul fix locale:

- `python -m pytest tests\test_busta.py -q --tb=short` -> passato;
- `python -m pytest tests\test_simulazione_deposito.py tests\test_local_pec_runtime.py tests\test_deposito.py::test_deposito_invia_pec_simula_invio_senza_spedire_quando_busta_conforme tests\test_deposito.py::test_deposito_invia_pec_reale_payload_local_signer_base64_e_corpo_finale tests\test_deposito.py::test_deposito_invia_pec_rifiuta_dati_atto_firmato_su_busta_diversa tests\test_deposito.py::test_deposito_invia_pec_prova_senza_invio_non_restituisce_conflitto_http tests\test_deposito.py::test_deposito_invia_pec_reale_richiede_sempre_local_signer_anche_con_smtp_server_abilitato tests\test_deposito.py::test_deposito_invia_pec_prova_senza_invio_mostra_preview_anche_senza_pec_mittente -q --tb=short` -> passato;
- `python -m pytest tests\test_deposito_server_dry_run_audit.py -q --tb=short` -> passato;
- `python -m pytest tests\test_busta.py tests\test_simulazione_deposito.py tests\test_local_pec_runtime.py tests\test_deposito_server_dry_run_audit.py tests\test_deposito.py::test_deposito_invia_pec_simula_invio_senza_spedire_quando_busta_conforme tests\test_deposito.py::test_deposito_invia_pec_reale_payload_local_signer_base64_e_corpo_finale tests\test_deposito.py::test_deposito_invia_pec_rifiuta_dati_atto_firmato_su_busta_diversa tests\test_deposito.py::test_deposito_invia_pec_prova_senza_invio_non_restituisce_conflitto_http tests\test_deposito.py::test_deposito_invia_pec_reale_richiede_sempre_local_signer_anche_con_smtp_server_abilitato tests\test_deposito.py::test_deposito_invia_pec_prova_senza_invio_mostra_preview_anche_senza_pec_mittente tests\test_regia_ui_react.py::test_ui_deposito_prova_guidata_non_salta_firma_e_mostra_audit_pec_indice tests\test_regia_ui_react.py::test_ui_deposito_prepara_legge_intero_fascicolo_e_distingue_canale -q --tb=short` -> passato;
- `python -m py_compile pct\busta.py tests\test_busta.py tests\test_simulazione_deposito.py scripts\audit_deposito_server_dry_run.py` -> passato;
- `git diff --check -- pct\busta.py tests\test_busta.py tests\test_simulazione_deposito.py scripts\audit_deposito_server_dry_run.py` -> passato.

Stato aggiornato: il fix MIME iniziale è stato portato in produzione, ma la prova reale successiva del `29/06/2026 15:37-15:38` ha mostrato un secondo blocco prima dell'invio reale: `Busta ministeriale non conforme: Atto.msg contiene parti MIME senza nome file: text/plain, text/plain, text/plain`.

Diagnosi del secondo blocco:

- il file tecnico generato in produzione `/tmp/busta_5fm3xu7e/Atto.msg` era `multipart/related` e conteneva `IndiceBusta.xml` come prima parte nominata;
- tre allegati PEC `.eml` del fascicolo erano però inseriti come `message/rfc822`;
- il parser MIME Python apriva quei `.eml` come messaggi annidati e vedeva al loro interno tre parti `text/plain` prive di nome file;
- il controllo pre-invio ha quindi bloccato la busta prima della PEC reale: nessun nuovo deposito ministeriale sporco è stato spedito in quella prova.

Correzione applicata dopo il secondo blocco:

- `pct/busta.py` tratta `.eml` e `.msg` come file opachi `application/octet-stream` dentro `Atto.msg`, mantenendo `name`, `filename` e `Content-ID`;
- la verifica di `Atto.msg` legge le parti file di primo livello della busta, senza scendere dentro eventuali email allegate;
- aggiunto il test anti-regressione `test_atto_msg_tratta_eml_come_file_opaco_senza_parti_annidate`, che riproduce una ricevuta PEC `.eml` con contenuto `text/plain` e verifica che non diventi `message/rfc822` annidato;
- guardrail eseguiti: `python -m pytest tests\test_busta.py -q --tb=short` -> `18/18`; suite mirata deposito/PEC/dry-run -> passata.

Stato: lavoro ancora aperto finché questa seconda correzione non è committata, pushata, distribuita su Hetzner e riprovata in produzione sul fascicolo `795C50AC`. La chiusura positiva richiede ancora prova reale senza invio, poi invio reale eseguito dall'avvocato con PIN e controllo dell'esito automatico PST.

## Aggiornamento 2026-06-26 - Formato PEC deposito ministeriale

Richiesta utente: controllare `Formato_messaggi_e_descrizione_flusso_di_deposito_1.pdf` e chiarire se l'indice busta debba essere inviato come XML separato.

Esito del confronto tecnico:

- la PEC esterna di deposito deve avere oggetto con sintassi `DEPOSITO <testo libero>`;
- l'oggetto IUSENTRA `DEPOSITO TELEMATICO - RICORSO - RG ...` resta compatibile perché inizia con `DEPOSITO ` e il resto è testo libero;
- `IndiceBusta.xml` non va allegato separatamente alla PEC: sta dentro `Atto.msg`, poi `Atto.msg` viene cifrato nel pacchetto PEC `Atto.enc`;
- il corpo PEC resta testo semplice tramite Local Signer;
- `Atto.enc` resta requisito tecnico: deve essere CMS/PKCS#7 `EnvelopedData` ministeriale verificato e contenere la busta con `IndiceBusta.xml`;
- gli allegati ulteriori scelti dall'avvocato non sono bloccati automaticamente dal ponte PEC locale; il software blocca solo requisiti tecnici verificabili come oggetto non conforme e `Atto.enc` non valido.

Correzione applicata:

- aggiunto `pct/deposito_pec_contract.py` per il controllo riusabile dell'oggetto `DEPOSITO <testo libero>`;
- il report di compatibilità della simulazione controlla la sintassi ministeriale reale, non solo la stringa storica `DEPOSITO TELEMATICO`;
- il payload Local Signer rifiuta il deposito con `.enc` se l'oggetto non rispetta la sintassi ministeriale;
- il ponte PEC locale conserva gli allegati extra decisi dall'avvocato, verificando comunque `Atto.enc` quando presente.

Guardrail eseguito:

- `python -m pytest tests/test_local_pec_runtime.py tests/test_local_pec_bridge.py tests/test_deposito.py::test_deposito_invia_pec_simula_invio_senza_spedire_quando_busta_conforme tests/test_deposito.py::test_deposito_invia_pec_reale_payload_local_signer_base64_e_corpo_finale tests/test_deposito_server_dry_run_audit.py::test_prova_guidata_espone_destinatario_pec_testo_e_documenti -q` -> `18 passed`.

## Aggiornamento 2026-06-26 - Blocco anti `Indice busta non trovato`

Caso reale da presidiare: deposito PCT Tribunale di Vicenza inviato il `26/06/2026` alle `11:42`, con esito automatico PST ricevuto alle `11:43:26`, `Codice esito: -1`, `IDBUSTA: 152529323`, messaggio `Indice busta non trovato, necessario effettuare nuovamente il deposito`.

Evidenza tecnica ricavata dagli EML reali:

- l'invio PEC era partito e la ricevuta di consegna conteneva un allegato unico `Atto.enc`;
- `Atto.enc` era un CMS/PKCS#7 `EnvelopedData` con cifratura `aes256_cbc` e certificato PST del Tribunale di Vicenza;
- quindi il problema non era SMTP, destinatario PEC, certificato Vicenza o base64 dell'allegato, ma la mancanza di una prova interna sufficiente su `Atto.msg` e `IndiceBusta.xml` prima della cifratura consegnata al Local Signer.

Regola corretta da questo aggiornamento:

- `Atto.msg` viene verificato prima di produrre `Atto.enc`: deve contenere `IndiceBusta.xml`, `DatiAtto.xml.p7m`, atto principale, allegati selezionati e `IndiceDocumentiDepositati.PDF`;
- `IndiceBusta.xml` deve avere `<Atto Nome="...">` uguale all'atto principale realmente presente, un solo `Allegato Tipo="DA"` uguale a `DatiAtto.xml.p7m`, e ogni allegato dichiarato deve esistere davvero in `Atto.msg`;
- dopo la cifratura il software rilegge `Atto.enc`, verifica CMS `EnvelopedData`, AES256, coerenza della busta e registra hash SHA-256 di `Atto.msg` e `Atto.enc`;
- `Simula invio PEC`, `Prova senza invio` e `Invia deposito reale` usano lo stesso audit busta: la simulazione salta solo l'ultimo invio SMTP locale, non la generazione e il controllo del pacchetto ministeriale;
- il payload Local Signer per `Atto.enc` viene creato solo se contiene `ministerial_busta_verified=true` e se l'hash dell'allegato coincide con l'audit del pacchetto;
- il bottone `Invia deposito reale` non può più arrivare alla password PEC locale con un `Atto.enc` che sia solo CMS/base64 valido ma senza verifica ministeriale di `Atto.msg` e `IndiceBusta.xml`.

Guardrail automatici eseguiti su questa correzione:

- `python -m pytest tests/test_busta.py tests/test_local_pec_runtime.py tests/test_deposito.py::test_deposito_invia_pec_simula_invio_senza_spedire_quando_busta_conforme tests/test_deposito.py::test_deposito_invia_pec_reale_payload_local_signer_base64_e_corpo_finale tests/test_deposito.py::test_deposito_invia_pec_rifiuta_dati_atto_firmato_su_busta_diversa tests/test_deposito.py::test_deposito_invia_pec_prova_senza_invio_non_restituisce_conflitto_http tests/test_deposito.py::test_deposito_invia_pec_reale_richiede_sempre_local_signer_anche_con_smtp_server_abilitato tests/test_deposito.py::test_deposito_legacy_invia_richiede_sempre_local_signer_anche_con_smtp_server_abilitato tests/test_deposito.py::test_deposito_invia_pec_prova_senza_invio_mostra_preview_anche_senza_pec_mittente tests/test_deposito_guidato.py tests/test_deposito_server_dry_run_audit.py tests/test_regia_ui_react.py -q` -> `51 passed`;
- prova tecnica con certificato PST reale Vicenza: `Atto.msg` generato con `IndiceBusta.xml`, `DatiAtto.xml.p7m`, atto principale, allegati e indice PDF; `Atto.enc` riletto come CMS `enveloped_data`, algoritmo `aes256_cbc`, OID `2.16.840.1.101.3.4.1.42`, destinatario certificato Vicenza.

Stato server: da verificare su `https://app.iusentra.it` dopo applicazione del codice e rebuild Hetzner. La prova deve concentrarsi sul fascicolo reale indicato dall'utente e non deve inviare PEC reale durante `Simula invio PEC`.

## Aggiornamento 2026-06-26 - Job incrementali, PEC, notifiche e documenti Lex

Richiesta utente: eliminare i ripassi pesanti automatici. Dopo che PEC, email, notifiche, Web Push e documenti di fascicolo sono stati letti e memorizzati, i job devono controllare solo elementi nuovi, modificati o rimasti in coda.

Correzione applicata:

- i percorsi applicativi PEC/email ordinaria (`mailbox_sync_runtime`, dashboard React, route manuali, PDP penale e fatturazione) usano `incremental_only=True` come default operativo;
- il workflow condiviso `sincronizza_pec_e_fascicoli()` nasce ora incrementale; la scansione/riparazione storica resta disponibile solo dal motore IMAP basso livello con flag esplicito;
- il polling automatico di depositi e cancelleria usa finestre corte e cappate (`IUSENTRA_DEPOSIT_POLL_DAYS`, `IUSENTRA_PEC_CANCELLERIA_POLL_DAYS`, massimo 7 giorni);
- il presidio documentale Lex dei fascicoli registra in `pec_audit_log` un marker `pec.document_presidio.checked` calcolato da fascicolo, documento e hash SHA-256;
- se un documento fascicolo ha già `hash_sha256`, la sorgente Document AI non riapre il file solo per ricalcolare l'hash;
- il dataset Lex notturno salva fingerprint e opzioni in `source_index.json`/`latest_job.json` e restituisce `skipped_unchanged` quando `documenti_ai.json` non è cambiato;
- Web Push resta vincolato a `dedupe_key`: una notifica già esistente non viene reinviata.

Storage di memoria persistente:

- PEC/email: `/data/tenants/<studio>/email`, `EMAIL_CASELLA_DB`, `EMAIL_ORDINARIA_DB`, UID IMAP e `Message-ID`;
- PEC audit: `pec_audit.sqlite`, tabelle `pec_local_acquire_runs`, `pec_local_acquire_items`, `pec_messages`, `pec_jobs`, `pec_audit_log`;
- Documenti Lex: repository Document AI tenant-aware più marker `pec.document_presidio.checked`;
- Dataset Lex: `/data/tenants/<studio>/intelligence/lex_dataset/latest_job.json`, `jobs.json`, `source_index.json`;
- notifiche/Web Push: `/data/tenants/<studio>/notifications/notifications.db`, tabelle `notifications`, `push_subscriptions`, `notification_deliveries`.

Stato verifica: test mirati e rebuild/deploy da completare nello stesso ciclo prima del report finale. Riferimento operativo nuovo: `docs/INCREMENTAL_JOBS_AND_STORAGE.md`.

## Aggiornamento 2026-06-26 - Firma multipla non dovuta su allegato del ricorso

Caso reale da presidiare: fascicolo produzione `795C50AC`, deposito PCT Vicenza. La UI mostrava `Firma multipla da completare` su `Autocertificazione ricorso.PDF`, pur trattandosi di un allegato di supporto già presente nella selezione documentale e non di un nuovo atto principale da sottoscrivere in lotto.

Correzione applicata:

- il catalogo documentale riconosce `Autocertificazione ricorso.PDF`, dichiarazioni, documentazione reddituale, carta identità, contratti, diffide, richieste pagamento e allegati simili come `allegato` anche se nel nome compare la parola `ricorso` o se il tipo storico era stato salvato come `RICORSO`;
- la regola `Ricorso = atto principale` resta valida per i nomi realmente introduttivi, come `Ricorso introduttivo.pdf`, `Ricorso principale.pdf` e `Atto di ricorso`;
- `should_apply_catalog_type()` consente la correzione del vecchio tipo storico `RICORSO` solo quando il nuovo catalogo identifica con alta confidenza un allegato di supporto, evitando di lasciare bloccanti di firma non dovuti sui fascicoli esistenti;
- il flusso di deposito non cambia il trasporto PEC: la PEC operativa resta sempre inviata dal PC locale tramite Local Signer/servizio locale, mai dal server.

Guardrail eseguiti prima del deploy:

- `python -m pytest tests/test_fascicolo_document_catalog.py -q`;
- `python -m pytest tests/test_regia_ui_react.py -q`;
- `python -m pytest tests/test_fascicolo_document_catalog.py tests/test_regia_ui_react.py tests/test_packaging_consistency.py::test_versione_allineata_tra_package_docker_e_railway -q`.

Stato verifica reale: da completare dopo deploy `2.253.120` su `https://app.iusentra.it/fascicoli/795C50AC/deposito/prepara#firma-busta`, controllando visivamente che `Autocertificazione ricorso.PDF` non compaia più tra i documenti da firmare e che la simulazione deposito prosegua fino al blocco corretto successivo, se presente.

## Aggiornamento 2026-06-23 - Esito PST reale e blocco Atto.enc non CMS

Caso reale da presidiare: fascicolo server `F08F92A2`, deposito PCT Vicenza, messaggio PST `Codice esito: -1`, `IDBUSTA: 152329542`, testo `Indice busta non trovato, necessario effettuare nuovamente il deposito`. Questo esito supera il precedente falso-verde sul solo payload base64: un `Atto.enc` con nome e base64 valido non basta se il contenitore ministeriale o l'indice interno non sono riconoscibili dal PST.

Evidenze controllate:

- `pec_d60f8a7029ed933e57059b90 (1).eml` e `pec_8a5787494a7faee804e79394 (2).eml` sono ricevute PST/Legalmail con `EsitoAtto.xml`, `daticert.xml` e `smime.p7s`; non contengono l'originale `Atto.enc` inviato e non contengono `postacert.eml` nella copia locale disponibile;
- `pec_283b464edebba9fe474159e5.eml` è una copia testuale piccola, non multipart: se la UI mostra `postacert.eml`, `EsitoAtto.xml`, `daticert.xml` o `smime.p7s` come `Da recuperare con la sincronizzazione`, quel messaggio è corretto finché la sincronizzazione della casella PEC non recupera il MIME originale completo con allegati;
- verifica tecnica dei file utente del 23/06/2026: `pec_283b464edebba9fe474159e5.eml` ha `content_type=text/plain`, `multipart=false`, `attachments=0`; `pec_d60f8a7029ed933e57059b90 (1).eml` contiene `EsitoAtto.xml`, `daticert.xml` e `smime.p7s`; `pec_8a5787494a7faee804e79394 (2).eml` contiene `EsitoAtto.xml`, `daticert.xml` e `smime.p7s`;
- la copia non crittografata accettata `COPIA NON CRITTOGRAFATA DEPOSITO TELEMATICO_ Ricorso Romeo ... .EML` mostra il contenuto logico accettato, compreso `DatiAtto.xml.p7m` e `IndiceDocumentiDepositati.PDF`;
- gli originali di deposito accettati presenti in `Downloads` trasportano un solo allegato `Atto.enc` CMS `EnvelopedData`; alcuni campioni usano `tripledes_3key`, uno usa `aes256_cbc`, quindi la guardia decisiva è la struttura CMS ministeriale e non il solo nome file.

Correzione ulteriore applicata:

- `web.services.local_pec_runtime` rifiuta `Atto.enc` non CMS prima di costruire il payload Local Signer;
- `local_signer_mod.pec_bridge` rifiuta `Atto.enc` non CMS anche se un futuro ramo provasse ad aggirare il controllo server/UI;
- `frontend/src/components/FascicoliPage.tsx` verifica lato browser che il base64 di `Atto.enc` decodifichi in un DER CMS `EnvelopedData` prima di chiedere la password PEC;
- `pct.busta` valida il CMS prodotto dalla cifratura e registra algoritmo, OID e numero destinatari nell'audit tecnico;
- `pct.deposito_compatibilita` e `scripts/audit_deposito_server_dry_run.py` considerano conforme il trasporto reale solo se `Atto.enc` è CMS e se l'indice ministeriale è presente.

Stato prova reale locale `2.253.97`: Docker reale locale ricostruito su `127.0.0.1:8080`, `/api/pronto` `ok=true`, `versione=2.253.97`; nella UI React del deposito locale `DC5BF1DB` il click reale su `Simula invio PEC` non è passato a un falso invio, ma ha richiesto la firma locale di `DatiAtto.xml` e si è fermato con messaggio visibile `Token non pronto per la firma: verifica che il dispositivo fisico sia inserito`. Questo è il blocco corretto prima della password PEC quando manca il token fisico. Screenshot fuori repository: `C:\Users\antmm\AppData\Local\Temp\iusentra-225397-deposito-token-block-locale.png`.

Stato produzione `2.253.97`, commit `c77875f21d170fdd6ae896c7e9dcf851188a6584`: deploy Hetzner completato, `/api/pronto` `ok=true`, container `app`, `scheduler-worker` e `ocr-worker` healthy, prune Docker eseguito e snapshot temporaneo assente. Prova reale server eseguita su `https://app.iusentra.it/fascicoli/F08F92A2/deposito/prepara#generazione-busta`: pagina React caricata senza HTML grezzo, ufficio `Tribunale di Vicenza`, PEC `tribunale.vicenza@civile.ptel.giustiziacert.it`, `11` documenti in busta, `9` documenti da firmare e `2` firmati. Il click reale su `Simula invio PEC` ha mostrato la progress bar con `DatiAtto.xml`, `DatiAtto.xml.p7m`, `IndiceBusta.xml`, `IndiceDocumentiDepositati.PDF`, documenti e `Atto.enc`; il flusso si è fermato correttamente con `Local Signer non rilevato` / `Token non pronto per la firma`, senza chiedere la password PEC e senza inviare PEC reale. `Invia deposito reale` resta disabilitato solo per il requisito obbligatorio ancora mancante: firma/token locale necessari a produrre `DatiAtto.xml.p7m` e poi `Atto.enc` CMS prima dell'invio.

## Aggiornamento 2026-06-23 - IndiceBusta ministeriale e firma DatiAtto

Caso reale analizzato: deposito PCT Vicenza rifiutato con `Codice esito: -1`, `IDBUSTA: 152329542`, messaggio `Indice busta non trovato, necessario effettuare nuovamente il deposito`. Il controllo degli EML allegati ha confermato che l'esito proveniva dai controlli automatici del Tribunale di Vicenza; il confronto con la copia non crittografata di un deposito accettato ha mostrato la presenza del metadato firmato `DatiAtto.xml.p7m`.

Correzione applicata:

- `Atto.msg` include ora sempre `IndiceBusta.xml` ministeriale conforme alla DTD locale `docs/specs/ministero/DTD_20180328/IndiceBusta.dtd`, distinto dal PDF leggibile `IndiceDocumentiDepositati.PDF`;
- prima di generare `Atto.enc` il flusso PCT richiede la firma CAdES di `DatiAtto.xml` e rigenera la busta con `DatiAtto.xml.p7m`;
- il backend conserva `id_busta` e timestamp tra richiesta firma e creazione `Atto.enc`, evitando che il file firmato appartenga a una busta diversa;
- il backend calcola e verifica l'hash del `DatiAtto.xml` e controlla che il `.p7m` incapsuli proprio il metadato generato per quella busta; un `.p7m` valido ma riferito a XML diverso viene rifiutato;
- l'indice PDF è generato in modo deterministico, così l'hash inserito in `DatiAtto.xml` resta stabile durante il passaggio Local Signer;
- la progress bar di deposito mostra anche `DatiAtto.xml.p7m` e `IndiceBusta.xml`, oltre a `IndiceDocumentiDepositati.PDF`, documenti selezionati e `Atto.enc`;
- gli atti o allegati già `.p7m` restano documenti firmati e non vengono rifirmati; la nuova firma obbligatoria riguarda il metadato ministeriale `DatiAtto.xml`.

Test tecnici eseguiti:

- `python -m pytest tests/test_busta.py tests/test_deposito.py::test_deposito_invia_pec_simula_invio_senza_spedire_quando_busta_conforme tests/test_deposito.py::test_deposito_invia_pec_reale_payload_local_signer_base64_e_corpo_finale tests/test_deposito.py::test_deposito_invia_pec_rifiuta_dati_atto_firmato_su_busta_diversa tests/test_deposito.py::test_deposito_invia_pec_simulazione_guidata_non_restituisce_conflitto_http tests/test_deposito.py::test_deposito_invia_pec_prova_senza_invio_non_restituisce_conflitto_http tests/test_deposito.py::test_deposito_invia_pec_reale_richiede_sempre_local_signer_anche_con_smtp_server_abilitato tests/test_deposito.py::test_deposito_invia_pec_prova_senza_invio_mostra_preview_anche_senza_pec_mittente -q` (`22/22`);
- `python -m pytest tests/test_deposito.py tests/test_busta.py tests/test_deposito_server_dry_run_audit.py tests/test_profilo_deposito.py -q` (`56/56`);
- `python -m pytest tests/test_deposito_server_dry_run_audit.py tests/test_regia_ui_react.py -q` (`9/9`);
- `pnpm --dir frontend run build`;
- `pnpm --dir frontend run test`.

Stato prova reale locale `2.253.97`: eseguita su copia Docker reale `http://127.0.0.1:8080` dopo rebuild; la UI React mostra `DatiAtto.xml.p7m`, `IndiceBusta.xml`, `Atto.enc` e il controllo si ferma prima dell'invio perché il token fisico non è disponibile. Non dichiarare invio reale completato finché il token viene rilevato, il PIN viene inserito nella UI, `DatiAtto.xml.p7m` viene prodotto, `Atto.enc` CMS viene generato e il ramo `Invia deposito reale` arriva alla password PEC locale senza errori.

## Aggiornamento PEC presidiate - Lex AI, RAG e recupero documentale

Data intervento: 2026-06-20.

Obiettivo operativo: rendere automatico il presidio delle PEC e dei documenti di fascicolo quando l'avvocato deve produrre lavoro concreto: udienze, notifiche, termini, note scritte, memorie, lettura di provvedimenti e collegamenti audiovisivi. Le ricevute tecniche di deposito restano nel fascicolo e non entrano come scadenze generiche.

Fonti tecniche consultate: OpenAI File Search/vector stores (`https://developers.openai.com/api/docs/guides/tools-file-search`), Microsoft Azure AI Search RAG e chunking (`https://learn.microsoft.com/en-us/azure/search/retrieval-augmented-generation-overview`, `https://learn.microsoft.com/en-us/azure/search/vector-search-how-to-chunk-documents`), Qdrant payload filtering e hybrid queries (`https://qdrant.tech/documentation/search/filtering/`, `https://qdrant.tech/documentation/search/hybrid-queries/`), Pinecone data modeling (`https://docs.pinecone.io/guides/index-data/data-modeling`). Decisione applicativa: Lex AI e l'eventuale database vettoriale sono livelli di recupero/citazione, mentre le decisioni operative vengono normalizzate e salvate su repository applicativi con audit.

Modifiche applicate:

- i metadati delle sorgenti Lex dei documenti di fascicolo includono tenant, fascicolo, documento, hash, RG, ufficio, giudice, cliente, parte/soggetto e oggetto fascicolo, così un RAG o indice vettoriale può filtrare per contesto processuale senza usare il solo numero RG;
- aggiunto presidio automatico `recover_missing_hearings_from_fascicolo_documents`: indicizza con Lex i documenti del fascicolo, legge testo e metadati, estrae udienze e termini futuri, scarta date non operative o scadute e scrive in fascicolo, scadenziario e agenda con chiave idempotente;
- il presidio distingue termine e udienza anche quando lo stesso decreto contiene sia `termine per deposito note scritte` sia link audiovisivo: il link remoto viene applicato solo al candidato di udienza;
- lo scheduler PEC richiama anche il presidio documentale dopo i job PEC ordinari e produce notifiche operative come `Presidio documentale Lex`, senza far comparire le ricevute tecniche grezze;
- le comunicazioni in agenda/scadenziario includono profilo processuale leggibile: ufficio, giudice, RG, cliente, parte/soggetto, evento, fonte documentale, data e istruzioni/link se presenti.

Test automatici eseguiti in questa tranche:

- `python -m py_compile pct/pec_pipeline.py pct/document_intelligence/sources.py web/services/pec_pipeline_runtime.py pct/email_client.py web/services/topbar_operational.py`;
- `python -m pytest -q tests/test_pec_audit_pipeline.py -k "documentale_lex or pct_deposit or scadenziario_ignora or topbar_sopprime" --tb=short`;
- `python -m pytest -q tests/test_document_intelligence_api.py -k "lex_indexing or indicizza_file_anomalo or preferisce_record" --tb=short`;
- `python -m pytest -q tests/test_pec_audit_pipeline.py --tb=short` (`53/53`);
- `python -m pytest -q tests/test_react_scadenziario_additions.py tests/test_react_shell.py::test_react_agenda_bridge_presidio_documentale_lex_mostra_link_udienza_da_remoto tests/test_react_shell.py::test_react_agenda_bridge_presidio_documentale_lex_link_storico_da_controllare tests/test_react_shell.py::test_react_agenda_bridge_presidio_documentale_lex_non_confonde_deposito_note_con_udienza tests/test_react_shell.py::test_react_agenda_bridge_traduce_pec_udienza_in_linguaggio_professionale --tb=short` (`14/14`);
- `python -m pytest -q tests/test_utf8_integrity.py tests/test_react_asset_retention.py --tb=short` (`6/6`);
- `python scripts/audit_tenant_data_structure.py --registry data/tenants.json --json` e `python scripts/audit_data_flow_contract.py --registry data/tenants.json --json` dopo pulizia dei dati runtime di prova (`ok=true`, `errors=0`, `operational_untracked=0`);
- `corepack pnpm --filter @iusentra/studio build:vite`.

Prova reale locale eseguita su `http://127.0.0.1:8080` con Docker locale healthy, `/api/pronto` `versione=2.253.84`. Dati controllati: fascicolo `0DAC92F3`, documento `D3E7D1E6`, cliente `Mario Rossi Codex`, parte/soggetto `INPS - Istituto Nazionale Previdenza Sociale`, RG `1754/2026`, ufficio `Tribunale di Palmi`.

Verifica visiva reale:

- Agenda dettaglio `/agenda/B125093A?data=2026-07-21`, desktop e mobile `390x844`: visibili cliente, RG, ufficio, parte/soggetto, udienza da remoto, link Teams, allegato `Decreto fissazione udienza CODEX-PEC-LEX-REAL-20260620-1008.txt` e stato `link verificato sull'allegato`; dopo fix CSS mobile non ci sono sovrapposizioni tra righe operative e metadati.
- Scadenziario dettaglio `/scadenziario/f6e512d7-ad95-42f6-9324-3be15dda7632`: visibili `Udienza da remoto`, `Orario collegamento`, allegato completo, `Controllo link: Verificato sull'allegato`, operatività aperta e testo giuridico comprensibile per l'avvocato.
- Nel perimetro verificato non compaiono `ACCETTAZIONE DEPOSITO TELEMATICO`, `ESITO CONTROLLI AUTOMATICI DEPOSITO TELEMATICO`, `Ricevuta protocollo` o testo generico `Sono presenti anomalie non bloccanti`.
- Dopo la prova sono stati rimossi dal tenant locale il fascicolo, il documento, le scadenze, gli appuntamenti, l'utente test e i file Document AI marcati `CODEX-PEC-LEX-REAL`, senza toccare l'utente reale dello studio.

Stato rilascio della tranche PEC: commit applicativo `de196407d126a911bf74d6a2902d2cec5255c203` pushato su `Codex/legal-electronic-filing-kIxcV` e `claude/legal-electronic-filing-kIxcV`; required gate GitHub/CodeQL verdi sullo SHA corrente; deploy Hetzner CPX42 completato con `https://app.iusentra.it/api/pronto` `ok=true`, `versione=2.253.84`; server sullo stesso commit, container `iusentra-app-1`, `iusentra-scheduler-worker-1` e `iusentra-ocr-worker-1` healthy; `docker builder prune --all --force` eseguito (`0B`) e `/opt/iusentra/tmp-backup-snapshot` assente. Nota residua: la soppressione topbar delle ricevute tecniche PCT e' coperta da test, mentre la push mobile nativa non e' stata provata su dispositivo reale con permesso notifiche concesso.

## Aggiornamento 2.253.84 - PAT modello ministeriale XFA ufficiale

Data intervento: 2026-06-20.

Correzione applicata alla superficie React `/pat`, all'endpoint `/api/v1/ui/pat/moduli/compila` e al generatore `pct/pat_pdf_templates.py`:

- `Genera modulo ufficiale` produce come file principale il modello ministeriale PAT XFA originale compilato, non un PDF riassuntivo IUSENTRA;
- il generatore clona il template ufficiale presente in `pct/data/pat_moduli/`, preserva `/AcroForm` e `/XFA` e aggiorna i valori nel pacchetto XFA;
- la route normalizza gli alias `parte`, `amministrazione`, `controparte`, `resistente` prima della validazione, così i dati provenienti dalla UI o dal fascicolo alimentano i campi canonici del modello;
- il compilatore imposta anche i radio XFA persona fisica, persona giuridica e amministrazione per ricorrente e resistente, evitando moduli generati con controparte mancante;
- i documenti del fascicolo selezionati restano allegati Formweb separati: IUSENTRA li legge, li mostra, li controlla e li prepara, ma non li incorpora dentro il PDF del modulo;
- la UI indica che il PDF è un modello ministeriale XFA e che gli allegati sono file separati da caricare in Formweb;
- il vecchio builder backend che produceva un PDF standard `Modulo PAT compilato da IUSENTRA` e incorporava allegati e modulo XFA come file allegati è stato rimosso dal percorso attivo.

Nota tecnica importante per l'accettazione: i moduli ministeriali della Giustizia Amministrativa sono XFA/LiveCycle. Chrome/PDFium può mostrare la pagina di avviso Adobe Reader anche quando il file è esattamente il modello ufficiale compilato; per questo i test verificano i dati dentro il pacchetto XFA e il controllo operativo resta in IUSENTRA prima della consegna SIGA. L'apertura completa del modulo ministeriale compilato va fatta con Acrobat Reader.

Guardrail tecnici già eseguiti localmente prima del rebuild Docker: `python -m py_compile pct\pat_pdf_templates.py pct\pat_moduli.py web\blueprints\api_v1_react.py`, `python -m pytest tests\test_react_shell.py -k "pat_modulo_compilabile or pat_prefill or superfici_telematiche" -q`, `python -m pytest tests\test_canali_telematici_deposito.py -q`, `pnpm --filter @iusentra/studio build`. Dopo il controllo binario del 20/06/2026 sono stati aggiunti fix e test per il caso `amministrazione=Zurich Ass.Ni`: lo XFA generato contiene `Alessi`, `Robertino`, `RSSMRA80A01H501U`, `Zurich Ass.Ni`, oggetto e allegati selezionati.

Prova reale locale post rebuild Docker `2.253.84` eseguita il 20/06/2026 su `http://127.0.0.1:8080/pat`, browser integrato visibile:

- `/api/pronto` risponde `ok=true`, `versione=2.253.84`; container `app`, `scheduler-worker`, `ocr-worker` healthy;
- selezionato fascicolo `DC5BF1DB`, visibili `20` documenti del fascicolo, `20 selezionati, 4,7 MB`, pulsanti `Visualizza` e `Scarica`, ruoli allegato e flag `Firma PAdES`;
- compilati `Tipo ricorso=Ordinario` e `Contributo unificato=Pagato`; `Genera modulo ufficiale` produce `ModuloDepositoRicorso_4.02_compilato_iusentra.pdf` con link `Apri PDF compilato` e `Scarica PDF`;
- la preview reale nel container `/tmp/iusentra-pat-previews/tenant-8bf98719c459/VCQtybhX8SvE9HqCQotc6VoE.pdf` è PDF 1 pagina con XFA; il pacchetto XFA contiene `Alessi`, `Robertino`, `Zurich Ass.Ni`, oggetto del fascicolo, `decretoGenerico.pdf` e `MEMORIA_CONCLUSIVA_ZURICH.pdf.p7m`;
- Chrome mostra l'avviso Adobe Reader previsto per XFA, coerente con il modello ministeriale originale;
- hover e focus di `Avvia SIGA` restano leggibili: testo `rgb(255, 255, 255)` su fondo blu e outline focus visibile;
- responsive post rebuild: tablet `768x900` e mobile `390x844`, nessun overflow orizzontale, documenti leggibili e azioni SIGA impilate correttamente.

Stato operativo: il comportamento corretto è implementato, testato e verificato sulla copia Docker reale locale. Restano obbligatori commit, push branch gemelli, controlli GitHub/CodeQL, deploy Hetzner e prova produzione `https://app.iusentra.it/pat` sullo stesso commit.

## Aggiornamento 2.253.83 - PAT PDF visibile nel browser e hover SIGA

Nota 2026-06-20: questa sezione resta come cronologia del tentativo precedente, ma il comportamento attuale è quello documentato in `2.253.84`: modello ministeriale XFA ufficiale come file principale e allegati Formweb separati.

Data intervento: 2026-06-19.

Correzione applicata alla superficie React `/pat` e al generatore `pct/pat_pdf_templates.py`:

- il PDF prodotto da `Genera modulo ufficiale` non viene più servito solo come XFA LiveCycle, che nel viewer del browser può risultare vuoto o mostrare il warning Adobe;
- IUSENTRA genera un PDF operativo visibile nel browser con i dati compilati, mantiene il nome ufficiale del modulo e incorpora come allegato il modulo ministeriale XFA compilato, insieme agli allegati scelti dal fascicolo;
- `Apri PDF compilato` punta alla rotta di anteprima senza `download=1`; `Scarica PDF` resta separato e usa il download esplicito;
- la selezione documenti PAT rispetta il limite Formweb di 50 file anche quando il fascicolo contiene più allegati;
- il bottone `Avvia SIGA` ha regole hover/focus/disabled dedicate, con testo e icona sempre leggibili.

Prova reale locale eseguita su Docker `127.0.0.1:8080`, versione `2.253.83`, browser integrato visibile:

- `/api/pronto` risponde `ok=true`, `versione=2.253.83`;
- route `/pat` senza errori console, fascicolo `DC5BF1DB` selezionato, `20` documenti letti dal fascicolo, `20` allegati selezionati e totale visibile `4,7 MB`;
- campi modulo precompilati dal fascicolo: `Giudice di Pace - Palmi`, `Alessi Robertino`, `Zurich Ass.Ni`, oggetto e tipo ricorso `Ordinario`; completato `Contributo unificato=Pagato`;
- click reale su `Genera modulo ufficiale`: la UI mostra `ModuloDepositoRicorso_4.02_compilato_iusentra.pdf`, `20` allegati e `PDF 6.1 MB`;
- link `Apri PDF compilato` verificato senza `download=1`, link `Scarica PDF` verificato con `download=1`;
- click reale su `Apri PDF compilato`: il viewer Chrome apre `ModuloDepositoRicorso_4.02_compilato_iusentra.pdf`, pagina `1/2`, con titolo `Modulo PAT compilato da IUSENTRA` e campi compilati visibili. Non è stato visto PDF bianco;
- hover reale su `Avvia SIGA`: colore calcolato `rgb(255, 255, 255)` su fondo blu, testo `Avvia SIGA` leggibile e nessun salto layout;
- responsive reale: tablet `768x900` e mobile `390x844`, nessun overflow orizzontale, pulsanti SIGA impilati e leggibili.

Guardrail tecnici eseguiti localmente: `python scripts\react-migration\generate_api_contracts.py`, `python -m py_compile pct\pat_pdf_templates.py web\blueprints\api_v1_react.py`, `python -m pytest tests\test_react_shell.py -k "pat_modulo or pat_prefill or superfici_telematiche" -q`, `python -m pytest tests\test_backend_security_phase5.py::test_mappa_sicurezza_backend_generata_e_allineata tests\test_utf8_integrity.py -q --tb=short`, `npm run build`, rebuild Docker locale no-cache e prova visiva reale.

Stato operativo: il difetto PDF vuoto e il difetto hover/focus `Avvia SIGA` sono corretti e verificati localmente. Restano obbligatori commit, push branch gemelli, controlli GitHub/CodeQL, deploy Hetzner e prova produzione `https://app.iusentra.it/pat` sullo stesso commit.

## Aggiornamento 2.253.82 - PAT/SIGA operativo con moduli ufficiali e allegati dal fascicolo

Nota 2026-06-20: la parte sugli allegati incorporati nel PDF è superata dalla release `2.253.84`; gli allegati del fascicolo restano file separati per Formweb.

Data intervento: 2026-06-19.

Correzione applicata alla superficie React `/pat`, agli endpoint `/api/v1/ui/pat/moduli/*` e ai template ministeriali PAT:

- la pagina PAT è stata ridotta a percorso operativo essenziale: `Fascicolo`, `Deposito`, `Documenti`, `Modulo`, `SIGA`; rimossi KPI e pannelli non necessari alla lavorazione;
- IUSENTRA legge il fascicolo reale selezionato, mostra tutti i documenti disponibili, consente `Visualizza`, `Scarica`, selezione/deselezione massiva, ruolo documentale e spunta `Firma PAdES`;
- i moduli ufficiali PDF 4.x della Giustizia Amministrativa sono stati integrati nel repository applicativo come template sorgente, non come semplici link esterni;
- il PDF prodotto per `ModuloDepositoRicorso_4.02` mantiene il template ufficiale XFA/AcroForm e incorpora gli allegati selezionati dal fascicolo come file allegati al PDF;
- la UI non mostra dentro la pagina il warning XFA del viewer browser: IUSENTRA espone invece il controllo operativo dei dati compilati e degli allegati inclusi, con link al PDF ufficiale generato per firma/consegna;
- la fase SIGA resta la fase finale di consegna ufficiale: IUSENTRA prepara modulo, allegati e controlli; il portale ufficiale non viene forzato in iframe e non vengono intercettati SPID, CIE, CNS, PIN o token.

Prova reale locale eseguita su Docker `127.0.0.1:8080`, versione `2.253.82`, browser integrato visibile, route `/pat`, fascicolo `DC5BF1DB` (`RG 466/2023`, `Giudice di Pace - Palmi`, `Alessi Robertino c. Zurich Ass.Ni`):

- prima schermata: titolo `Prepara deposito PAT`, cinque passi operativi, nessun iframe, nessuna card KPI vecchia;
- selezione fascicolo: caricati `20` documenti reali, `20` selezionati automaticamente, totale visibile `4,7 MB`;
- hover/focus pulsante `Visualizza`: testo leggibile, contrasto stabile e nessun salto layout;
- anteprima documento: click reale su `decretoGenerico.pdf`, modal interno con toolbar PDF del browser, pagina del documento visibile e link `Apri in nuova scheda`;
- selezione allegati: `Nessuno` porta `0` selezionati e disabilita `20` selettori ruolo; `Seleziona tutti` riporta `20` selezionati e riabilita i ruoli;
- modulo ufficiale: sede, parte depositante, oggetto, tipo ricorso, ricorrente e controparte precompilati dal fascicolo; compilati `Codice fiscale / partita IVA` e `Contributo unificato`;
- generazione: `Genera modulo ufficiale` produce `ModuloDepositoRicorso_4.02_compilato_iusentra.pdf` con `20` allegati; la UI mostra `Dati compilati nel modulo ufficiale`, `Allegati inclusi nel PDF`, dimensione PDF `6,1 MB` e non mostra `Adobe Reader`, `Please wait` o `Anteprima PDF non disponibile`;
- fase finale: sezione `5. Consegna SIGA` visibile con `Avvia SIGA` abilitato e `Raccogli ricevute` / `Chiudi sessione` disabilitati finché la sessione non parte.

Prova responsive reale:

- desktop: scroll top/centro/fondo, pulsanti e testo leggibili;
- tablet `820x900`: nessun overflow orizzontale, passi e campi impilati correttamente;
- mobile `390x844`: rilevato un taglio reale dei campi modulo dovuto a `width:100%` senza `box-sizing:border-box`; corretto in CSS e riprovato dopo rebuild Docker. Dopo fix i controlli PAT non escono dalla colonna, i documenti hanno pulsanti verticali leggibili e il select ruolo resta visibile. L'unico elemento oltre viewport rilevato è la barra mobile globale, non il modulo PAT.

Stato operativo: localmente la preparazione PAT è accettata su macchina reale per pagina, documenti del fascicolo, generazione PDF ufficiale con allegati e responsive. Restano obbligatori commit, push branch gemelli, check GitHub/CodeQL, deploy Hetzner e verifica produzione `https://app.iusentra.it/pat` sullo stesso commit prima della chiusura complessiva.

## Aggiornamento 2.253.81 - PAT/SIGA come consegna finale, non pagina di link

Data intervento: 2026-06-19.

Correzione applicata alla superficie React `/pat` e agli endpoint `/api/v1/ui/pat/moduli/*`:

- il Portale Avvocato/SIGA viene trattato come fase finale di consegna, non come luogo in cui l'avvocato deve ricostruire da zero la pratica;
- la pagina PAT è stata riorganizzata nel percorso operativo `Fascicolo IUSENTRA -> Deposito Formweb -> Modulo compilabile -> Allegati e firme -> Sessione SIGA`;
- la pagina React `/portali/pat/acquisizione` è stata riallineata come fase finale `Consegna finale PAT / SIGA e rientro ricevute`, non più come importazione generica: accesso SIGA, deposito Formweb, rientro ricevute, file ufficiali, fascicolo IUSENTRA, verifica esiti e registrazione;
- il wizard PAT mostra che il portale ufficiale non viene incastrato in iframe quando SIGA lo blocca: la procedura primaria usa sessione ufficiale assistita dal Local Connector, con raccolta dei soli file autorizzati dall'avvocato e registrazione nel fascicolo;
- i moduli ufficiali restano fonti/versioni di riferimento, ma l'azione primaria non è più scaricare il modulo: IUSENTRA propone campi compilabili interni e genera un PDF dati modulo prima della sessione ufficiale;
- la precompilazione legge repository reali del tenant corrente: fascicoli, clienti e soggetti/parti processuali, senza creare una fonte dati parallela;
- il PDF compilato da IUSENTRA valida i campi obbligatori e, quando viene passato un fascicolo, rilegge i dati lato server prima di generare il documento;
- la sessione SIGA assistita resta governata dal Local Connector del PC, senza iframe del sito ufficiale e senza intercettare SPID, CIE, CNS, PIN o token.
- i testi visibili del wizard non espongono più `create new` o passaggi PST generici sul percorso PAT; hover, focus, selected e disabled dei pulsanti devono restare leggibili nella prova reale desktop/tablet/mobile.
- prova reale locale eseguita su Docker `127.0.0.1:8080/portali/pat/acquisizione` dopo rebuild: desktop con titolo `Consegna finale PAT / SIGA e rientro ricevute`, bottone `Vai alla consegna SIGA`, assenti `Vai alla ricerca`, `create new` e `Scarica modulo ufficiale`; click reali su Step 2 `Deposito`, Step 3 `Rientro`, Step 4 `File ufficiali` e ritorno Step 1; scroll completo senza overflow orizzontale; tablet `1024x768` e mobile `390x844` verificati; su mobile i pulsanti `Apri SIGA per consegna finale`, `Importa ricevute SIGA` e `Chiudi sessione` risultano impilati e leggibili.

Stato operativo: questa tranche prepara modulo, dati e PDF per PAT/Formweb e governa il rientro delle ricevute SIGA; non registra un deposito PAT come validamente inviato finché non risultano importate e collegate le ricevute ufficiali della sessione SIGA nel fascicolo. La prova reale locale su `/pat` e `/portali/pat/acquisizione` è stata eseguita su Docker `127.0.0.1:8080`; restano comunque obbligatori commit, push dei branch gemelli, controlli GitHub e deploy Hetzner prima della chiusura complessiva.

## Aggiornamento 2.253.77 - firma multipla .p7m e simulazione PEC senza invio reale

Data intervento: 2026-06-19.

Correzione applicata sul flusso React `Prepara deposito` e sulla route `/fascicoli/<id>/deposito/invia-pec`:

- i file già contenitori di firma CAdES (`.p7m`, `.sig`, `.pkcs7`) non vengono più inseriti nel batch di firma multipla Local Signer e non vengono più rimandati al token quando si clicca `Simula invio PEC` o `Prova senza invio reale`;
- questa esclusione non equivale a dichiarare `Firmato digitale`: la UI continua a mostrare `Firmato` solo quando il documento ha prova tecnica CAdES/PAdES verificata; un `.p7m` non verificato viene indicato come contenitore presente e non rifirmato;
- `Simula invio PEC` non genera più `Message-ID` fittizi e non registra più il deposito come `INVIATO`; registra solo `PROVA_SENZA_INVIO`, con `documenti_ids` collegati per presidio ricevute e senza impostare `id_deposito_pct` sui documenti come se fossero stati realmente depositati;
- la simulazione prepara lo stesso payload Local Signer dell’invio reale, incluso `Atto.enc` in `content_base64`, destinatario, oggetto, corpo PEC e allegato, ma non chiama l’invio PEC e non chiede la password;
- la risposta include `compatibility_report` con percentuale, controlli strutturali, confronto con i campioni PEC reali allegati dall’utente e piano ricevute (`accettazione`, `RdAC`, controlli automatici, esito cancelleria), mostrato nella preview busta.

Guardrail tecnici già eseguiti: `python -m pytest tests/test_regia_ui_react.py tests/test_regia_api_payloads.py::test_api_deposito_classifica_documenti_non_richiede_firma_su_contenitore_p7m tests/test_regia_api_payloads.py::test_api_fascicolo_mostra_p7m_solo_con_firma_reale tests/test_deposito.py::test_deposito_invia_pec_simula_invio_senza_spedire_quando_busta_conforme tests/test_deposito.py::test_deposito_invia_pec_simulazione_guidata_non_restituisce_conflitto_http tests/test_deposito.py::test_deposito_invia_pec_prova_senza_invio_non_restituisce_conflitto_http -q` → `10/10` passati.

Stato prova reale locale: eseguita il 19/06/2026 alle 10:17 su Docker reale `127.0.0.1:8080`, versione `2.253.77`, fascicolo `DC5BF1DB` (`RG 466/2023 - Alessi Robertino`, `Giudice di Pace - Palmi`). La pagina è React (`#root`), senza HTML grezzo visibile; dopo il caricamento API sono visibili ufficio `Ufficio del Giudice di Pace di Palmi`, PEC `gdp.palmi@civile.ptel.giustiziacert.it`, codici `0910401 / 0800570152`, `8` candidati busta e `8` firmati, `0` documenti da firmare.

Prova materiale finale su `Simula invio PEC`: click reale su pulsante, conferma modale, barra `SIMULAZIONE PEC IN CORSO` con scorrimento documenti (`DatiAtto.xml`, `IndiceDocumentiDepositati.PDF`, documenti `.p7m` e `Atto.enc`), nessuna richiesta di firma e nessun errore `ComputeSignature`. Esito UI: `Simulazione PEC completata senza invio reale: compatibilità 100%`; controlli OK per `Atto.enc ministeriale AES256`, `DatiAtto.xml`, `IndiceDocumentiDepositati.PDF`, atto/allegati, PEC ufficio, oggetto PEC, corpo PEC e simulazione senza SMTP. Il testo PEC è visibile e il riquadro finale mostra `Promemoria prima dell’invio reale`, non un blocco. Il bottone `Invia deposito reale` risulta abilitato (`disabled=false`).

La simulazione non registra un invio reale e non produce `Message-ID` fittizio: salva una prova `PROVA_SENZA_INVIO` e confronta la struttura con i campioni PEC reali allegati. L'invio reale resta demandato al PC locale tramite Local Signer/servizio locale, coerentemente con `/impostazioni?tab=pec`; il server prepara e verifica busta, destinatario, oggetto, corpo PEC, `Atto.enc` e ricevute da presidiare, ma non diventa canale SMTP operativo.

Stato produzione: da confermare su `https://app.iusentra.it/fascicoli/E5AE4668/deposito/` dopo commit, push branch gemelli e deploy Hetzner della stessa versione `2.253.77`. Fino a quella prova, la parte locale è accettata su macchina reale; la chiusura complessiva resta vincolata al server sullo stesso commit.
## Aggiornamento 2.253.64 - anteprima PST lavoro con catalogo completo

Data: 18/06/2026.

- Caso reale: Tribunale di Torino, registro LAV, RG 3950/2026.
- Dopo deploy `2.253.63`, prova reale su `https://app.iusentra.it` in Google Chrome: `Cerca fascicolo` ha confermato il certificato PST e ha trovato `RG 3950/2026`; `Carica anteprima` ha aperto Step 3 senza timeout verso `ext.processotelematico.giustizia.it`.
- Residuo corretto in `2.253.64`: l'anteprima mostrava solo 4 righe principali quando il fascicolo locale già importato conteneva il catalogo completo; ora la preview PST arricchisce lo snapshot parziale con i documenti portale del fascicolo locale esatto.
- Prova reale server `2.253.64` su Google Chrome: `Cerca fascicolo` ha trovato `RG 3950/2026`; `Carica anteprima` ha aperto Step 3 in circa 1 secondo, senza timeout, con `Documenti 31`, `7 buste o gruppi`, `Parti 2` ed `Eventi 1`.
- Guardrail: `test_api_portale_acquisizione_preview_pst_arricchisce_catalogo_da_fascicolo_locale` copre `29/29` documenti in preview e preserva anche un allegato reale senza id forte.
- Limite operativo: questa correzione riguarda consultazione/anteprima e catalogo documenti; non dichiara completo l'invio reale del deposito, che resta soggetto a firme, `Atto.enc`, PEC locale e ricevute.

## Stato operativo da non perdere

Stato consolidato `2.253.60`: la cache certificati PST è coperta per il catalogo operativo corrente dei canali PCT/SIGP/Cassazione che richiedono cifratura `Atto.enc` (`593/593` codici ministeriali coperti; `913` `.cer` fisici validi in cache). Da questo punto in avanti il software non deve più trattare il `.cer` di Palmi o Vicenza come mancante globale se la cache corrente è presente: un eventuale blocco su `Invia deposito reale` deve indicare solo il requisito effettivamente mancante nella singola prova, per esempio `Atto.enc` AES256 non generato, PEC mittente dello studio non configurata, firma obbligatoria non presente o destinatario PEC non verificato. L'invio operativo PEC non parte mai dal server: anche su `https://app.iusentra.it` il server prepara e verifica, mentre SMTP reale passa dal PC dell'avvocato tramite Local Signer. In `2.253.60` restano presidiati il gate `Local Signer boundaries`, la priorità del codice ufficio operativo in `TelematicoSurfacePage`, la sanificazione dei payload JSON deposito/firma/database senza perdere i messaggi operativi CAdES/PAdES e il limite governance del modulo firma.

La regola è fail-closed ma non pessimistica: se tutti i requisiti obbligatori del canale sono presenti, il bottone reale deve attivarsi; se resta disabilitato, la UI deve dire esattamente cosa manca e Codex deve correggere la logica prima di commit, push e deploy.

## Aggiornamento 2.253.61 - tracciatura tabella lavoro PST Torino RG 3950/2026

Data intervento: 2026-06-18.

Il fascicolo lavoro `RG 3950/2026` del Tribunale di Torino, registro `LAV`, è stato scaricato dal PST ufficiale con browser autenticato e importato nel fascicolo IUSENTRA `9B9DF2A1` (`Spagnolo Sara c. MIM`). Il log produzione è `PST-20260618085430-C4891C`.

Esito operativo:

- documenti PST individuati: 29;
- documenti scaricati: 29;
- documenti importati: 29;
- documenti mancanti, senza contenuto o scartati: 0;
- depositi ricostruiti: 4;
- eventi generati: 5;
- comunicazioni generate: 3;
- contatore visibile `Documenti e atti`: 52.

La correzione Local Signer tratta `lav_infofascicolo.wp` come superficie ministeriale equivalente alla tabella civile: riga principale, blocco `Allegati:`, nuova riga principale e paginazione. Il parser conserva la sezione reale del link, collega gli allegati al documento padre e non trascina più la sezione `Allegati` sui documenti principali successivi. Il download usa i link portale `downloadDocumentoSemplice.action` quando sono disponibili nella sessione PST autenticata.

Aggiornamento dopo prova utente: il flusso React `Carica anteprima` non deve più bloccare la vista con il timeout `ext.processotelematico.giustizia.it` quando la ricerca ha già restituito documenti PST utilizzabili. In `2.253.61` l'anteprima usa subito i documenti già ricevuti dalla ricerca; l'aggiornamento esterno resta un arricchimento e, se fallisce ma i documenti sono presenti, viene tracciato senza lasciare l'anteprima vuota.

Prova visiva server già eseguita su `https://app.iusentra.it/fascicoli/9B9DF2A1#documenti`: visibili tra gli altri `Ricorso.PDF`, `Nota d'iscrizione a ruolo.PDF`, `26830376s.pdf` e `20200029s.pdf`, con origine PST ufficiale e date portale. Dettaglio esteso in `artifacts/react-migration/tracciatura-tabella-lavoro-torino-rg-3950-2026.md`.

Dato sensibile: il PIN della pen drive e le credenziali dell'utente non sono stati scritti nei log o nei report.

## Incarico operativo di chiusura, da rileggere dopo ogni compattazione

Il lavoro deposito non è chiuso finché non è dimostrato nella vista reale, con fascicoli reali o controllati, che il software prepara, firma, controlla, simula e abilita l'invio secondo il canale corretto. I test automatici sono guardrail, non prova finale. Se la vista reale mostra un difetto, quel difetto prevale su build, typecheck, unit test o screenshot precedenti.

### Regola di sviluppo da seguire

1. Se l'utente segnala un difetto visibile, aprire subito la pagina reale indicata (`127.0.0.1:8080` oppure `https://app.iusentra.it`) e correggere il minimo necessario.
2. Provare subito la modifica nella stessa vista reale, con click, scroll e dati visibili.
3. Solo dopo il risultato reale positivo creare o aggiornare i test automatici.
4. Solo dopo test e prova reale procedere con commit, push dei branch gemelli, deploy Hetzner, verifica `/api/pronto` e igiene.
5. Se una prova reale resta aperta o fallisce, scriverlo qui e non dichiarare il deposito concluso.

### Cosa deve fare il software

- Risolvere il profilo deposito in tre casi: preventivo accettato con conferimento e fascicolo, nuovo fascicolo diretto, fascicolo veloce/autonomo.
- Salvare il profilo in SQL, non solo nel JSON, nelle colonne `profilo_deposito_json` di `preventivi_records`, `conferimenti_records` e `fascicoli`, con parità SQLite/PostgreSQL.
- Usare il canale corretto: PCT/SICID, PCT lavoro/SICID, PCT/SIECIC, SIGP/Giudice di Pace, Cassazione civile/PST, PDP, PAT, PTT, UNEP/notifiche sono canali diversi e non devono ereditare blocchi o certificati non pertinenti.
- Per PCT/SIGP/Cassazione con busta PST generare o presidiare `DatiAtto.xml`, `IndiceDocumentiDepositati.PDF`, `Atto.msg`, certificato pubblico `.cer` e `Atto.enc` AES256 quando richiesto.
- Per PDP, PAT e PTT preparare controlli, firme, limiti e ricevute secondo il portale specifico, senza pretendere `.cer` PST civile o `Atto.enc` PCT.
- Leggere l'intero fascicolo, proporre atto principale, procura, allegati e prove, ma lasciare all'avvocato le scelte non obbligatorie.
- Mostrare `Firmato` solo davanti a prova tecnica reale: CAdES/PKCS#7 `.p7m` o PAdES interno verificabile. Il testo del documento, il nome file o un vecchio flag non bastano.
- Firmare più documenti con un unico comando quando Local Signer/PKCS#11 è disponibile, salvando ogni `.p7m` nel fascicolo e aggiornando la UI prima del passo successivo.
- Mostrare `IndiceDocumentiDepositati.PDF` in anteprima reale e consentirne il download.
- Mostrare il corpo PEC che verrà predisposto; l'avvocato può modificarlo facoltativamente, ma la modifica non è obbligatoria.
- In simulazione o prova senza invio mostrare una barra avanzamento con il nome del documento o artefatto in lavorazione.
- Conservare o ripristinare `Simula invio PEC` e `Prova senza invio reale`, perché servono a controllare il flusso senza spedire nulla.
- Preparare l'invio reale usando le rotte corrette, il destinatario PEC verificato, la PEC mittente configurata e il payload locale per Local Signer; il server non deve essere canale SMTP reale e non devono comparire messaggi inutili alla cancelleria.
- Presidiare le ricevute dopo l'invio, senza registrare come deposito valido un pacchetto che non ha trasporto ministeriale conforme.

Regola permanente PEC locale: il riferimento operativo è la schermata `/impostazioni?tab=pec`, sezione `Verifiche PEC`, che indica `Il controllo dell'invio parte dal PC in uso: la password resta sul dispositivo locale.` Vale per deposito, notifiche legali e PEC operative: il server prepara e verifica, ma l'invio reale parte dal PC in uso tramite Local Signer/servizio locale. Se una rotta o un fallback prova a spedire dal server via SMTP, è una regressione da bloccare. La password PEC deve essere raccolta in una modale React locale, non tramite `window.prompt` e non in una rotta server.

### Quando `Invia deposito reale` deve attivarsi

Il bottone non deve restare spento per prudenza generica. Deve attivarsi quando sono veri tutti i requisiti obbligatori del canale:

- canale reale abilitato e riconosciuto;
- ufficio giudiziario e codice deposito/codice oggetto risolti;
- destinatario PEC verificato;
- PEC mittente e impostazioni SMTP disponibili per costruire il payload Local Signer, senza invio SMTP dal server;
- documenti selezionati e ruoli coerenti;
- firme obbligatorie già presenti o completate con Local Signer;
- `IndiceDocumentiDepositati.PDF` generato e visualizzabile;
- corpo PEC controllato;
- `.cer` PST valido solo se il canale lo richiede;
- `Atto.enc` AES256 generato solo se il canale lo richiede;
- prova senza invio o simulazione PEC completata senza errori bloccanti;
- ricevute presidiate dal fascicolo.

Se uno di questi punti manca, la UI deve indicarlo con testo puntuale. Se nessun punto manca e il bottone resta disabilitato, è una regressione da correggere prima di commit, push e deploy.

### Stato corrente da non perdere

- Cache certificati PST locale: `913` `.cer` fisici DER validi, `0` invalidi.
- Perimetro operativo che richiede `.cer/Atto.enc`: `593` codici ministeriali unici, `593/593` coperti, `0` mancanti.
- Fonti importate: `C:\QuickOrganizer\ListaUfficiGiudiziari.xml` e `C:\QuickOrganizer\QC_Uffici.xml`, più fallback PST diretto per codice/nome ufficio.
- Caso `Giudice di Pace - Palmi`, codice ministeriale `0800570152`: certificato recuperato e non deve essere più trattato come mancante globale se la cache corrente è presente.
- Caso `Tribunale di Vicenza`, fascicolo server `E5AE4668`, codice deposito `222050`: profilo deposito SQL già previsto con canale PCT, PEC e certificato quando il deploy è allineato.
- Prova locale reale aggiornata su `127.0.0.1:8080`: React autentico, PEC Palmi risolta, codice `0910401 / 0800570152` visibile, `Atto.enc` presente nella UI e anteprima `IndiceDocumentiDepositati.PDF` visibile con viewer PDF del browser, pagina `1/1`, toolbar, miniatura e contenuto `Indice documenti depositati`. Screenshot fuori repository: `C:\Users\antmm\AppData\Local\Temp\iusentra-dc5bf1db-indice-pdf-diretto-225356.png`.
- Prova locale reale controllata aggiornata al 2026-06-18: sul fascicolo `DC5BF1DB` il click reale su `Invia deposito reale` ha attraversato UI React, rotta `/deposito/invia-pec`, payload Local Signer e SMTP locale fittizio senza spedire all'esterno. Il pacchetto catturato contiene destinatario `gdp.palmi@civile.ptel.giustiziacert.it`, oggetto `DEPOSITO TELEMATICO - ATTO_GENERICO - RG 466/2023` e allegato unico `Atto.enc` da `4.637.389` byte. La configurazione PEC reale del tenant è stata ripristinata subito dopo e il server SMTP fittizio è stato spento.
- Fix sicurezza `2.253.60`: i payload di deposito React/legacy, database admin e apertura fascicolo da preventivo/conferimento passano da redazione pubblica; la cache/report `.cer` usa solo nomi file normalizzati dentro la directory prevista; la nota firma visibile non usa più regex fragile e non taglia note multilinea dell'utente. Gli helper firma CAdES/PAdES vivono nel service `fascicoli_signature_options`, così il bootstrap route resta sotto il limite governance senza cambiare comportamento.

### Prova finale richiesta prima di chiudere

- Server reale: fascicolo `E5AE4668` (`2026/330 - Marchetti c. MIM`) su `https://app.iusentra.it/fascicoli/E5AE4668/deposito/prepara`.
- Locale reale: fascicolo `DC5BF1DB` su `http://127.0.0.1:8080/fascicoli/DC5BF1DB/deposito/prepara`.
- Verifica visiva: apertura pagina, scroll completo, fasi deposito, lista documenti, ruoli, firme, indice, corpo PEC, simulazione PEC, prova senza invio e stato del bottone reale.
- Verifica tecnica: API e rotte di invio, destinatario PEC, mittente/SMTP, `Atto.enc` quando richiesto, ricevute, scheduler `.cer`, parità SQLite/PostgreSQL.
- Chiusura: commit, push su `Codex/legal-electronic-filing-kIxcV` e `claude/legal-electronic-filing-kIxcV`, check GitHub/CodeQL, deploy Hetzner, `/api/pronto`, prune Docker e repo hygiene.

### Relata e prova notifica

La relata non è un accessorio da confondere con la guida firma. Deve avere flusso proprio: testo reale visualizzato o generato, destinatari, domicilio digitale, dati obbligatori, documenti allegati, firma quando richiesta, prova senza invio e salvataggio nel fascicolo. Se la UI apre la guida quando si clicca firma/notifica, va corretto come difetto visivo-funzionale. La conformità della relata va scritta in questo file solo dopo prova reale e confronto con fonti ufficiali.

## Aggiornamento 2.253.57 - prova reale invio PEC locale senza spedizione esterna

Data intervento: 2026-06-18.

Perimetro verificato:

- copia Docker locale reale `http://127.0.0.1:8080`, fascicolo `DC5BF1DB`;
- superficie React `Prepara deposito`, fase `Busta e indice`;
- canale `SIGP/Giudice di Pace` con ufficio Palmi, codice ministeriale `0800570152` e PEC `gdp.palmi@civile.ptel.giustiziacert.it`;
- Local Signer raggiunto su `http://127.0.0.1:27272`;
- server SMTP fittizio temporaneo su `127.0.0.1:25252` usato solo per catturare la PEC senza inviare all'esterno;
- configurazione PEC reale del tenant ripristinata dopo il collaudo e server fittizio spento.

Correzioni applicate:

- `frontend/src/components/FascicoliPage.tsx`: `Invia deposito reale` usa la rotta JSON `/fascicoli/<id>/deposito/invia-pec` anche per il canale PST/SIGP che produce pacchetto JSON/Local Signer, evitando il fallback vecchio su `/deposito/genera-busta`;
- `frontend/src/components/FascicoliPage.tsx`: eliminata la dipendenza da `window.prompt`; la password PEC viene chiesta con modale React `Password PEC locale`, riepilogo mittente, destinatario, oggetto e allegati;
- `frontend/src/components/FascicoliPage.tsx`: la modale di conferma `Invia deposito reale` viene chiusa prima della richiesta password locale, così non resta un overlay bloccato su `Operazione...`;
- `frontend/src/components/FascicoliPage.css`: aggiunti gli stili della modale password PEC, con testo leggibile e campi che non escono dal contenitore;
- `web/bootstrap/deposito_routes.py` e `web/services/local_pec_runtime.py`: il server non usa SMTP reale per depositi legali; restituisce un payload `requires_local_pec` per il Local Signer e registra la conferma solo dopo `Message-ID` locale.

Prova materiale eseguita:

- click reale su `Prova senza invio reale`: UI con esito `Controlli software superati`, destinatario `gdp.palmi@civile.ptel.giustiziacert.it`, oggetto `DEPOSITO TELEMATICO - ATTO_GENERICO - RG 466/2023`;
- click reale su `Invia deposito reale`;
- conferma visibile accettata;
- modale `Password PEC locale` aperta nel browser, senza errore `prompt() is not supported`;
- inserita password fittizia solo per lo SMTP locale di collaudo;
- click reale su `Invia dal PC locale`;
- toast applicativo visto: `Deposito inviato via PEC e registrato nel fascicolo.`;
- nessun errore console nel browser durante il flusso.

Verifica post-rebuild Docker locale `2.253.57`:

- `docker compose build --no-cache app` completato con wheel `pct-studio-legale-2.253.57`;
- `docker compose up -d --force-recreate app`, container `iusentra-app` healthy;
- `GET http://127.0.0.1:8080/api/pronto` HTTP 200 con `versione=2.253.57`;
- browser integrato su `http://127.0.0.1:8080/fascicoli/DC5BF1DB/deposito/prepara#generazione-busta`;
- dopo il caricamento reale la pagina mostra `RG 466/2023 - Alessi Robertino`, `Giudice di Pace - Palmi`, PEC `gdp.palmi@civile.ptel.giustiziacert.it`, `8 documenti in busta`, `Indice dalla selezione`, nessun `n.d.` e nessun HTML grezzo;
- click reale su `Prova senza invio reale` dopo rebuild: esito `Prova deposito preparata`, riferimento prova `F81FDC8C`, controlli software superati e bottone `Invia deposito reale` attivo;
- click reale su `Visualizza IndiceDocumentiDepositati.PDF`: modal con URL diretto `/fascicoli/DC5BF1DB/deposito/indice-documenti?...`, toolbar PDF, miniatura, pagina `1/1` e contenuto `Indice documenti depositati`;
- screenshot prova indice post-rebuild fuori repository: `C:\Users\antmm\AppData\Local\Temp\iusentra-dc5bf1db-indice-pdf-post-rebuild-225357.png`.

PEC catturata dal server SMTP fittizio:

- file prova fuori repository: `C:\Users\antmm\AppData\Local\Temp\iusentra-fake-smtp-deposito.json`;
- EML fuori repository: `C:\Users\antmm\AppData\Local\Temp\iusentra-fake-smtp-deposito.eml`;
- mittente header: `roberto.montagnese@coapalmi.legalmail.it`;
- destinatario header: `gdp.palmi@civile.ptel.giustiziacert.it`;
- oggetto: `DEPOSITO TELEMATICO - ATTO_GENERICO - RG 466/2023`;
- `Message-ID`: `<178174394892.26844.7734756242688097457@pcmarco.station>`;
- corpo PEC contiene `Atto.enc` e l'elenco dei documenti inclusi;
- allegato unico: `Atto.enc`, `application/octet-stream`, `4.637.389` byte, SHA256 `1dfbb7d8a8383a05a3c0dcbd84bf8e76cfa382f09c8fb35f85816c3d8dd1d579`.

Limiti residui dichiarati:

- questa prova non ha spedito una PEC reale a una cancelleria: ha simulato il server SMTP in locale per verificare il click reale, la composizione PEC e l'allegato senza invio esterno;
- la firma multipla fisica con pen drive e PIN reale non può essere dichiarata completata durante l'assenza dell'utente: richiede token inserito, PIN digitato e firma effettiva di più documenti con salvataggio `.p7m`;
- prima della chiusura complessiva restano gate finali, rebuild Docker locale, commit, push branch gemelli, deploy Hetzner e verifica server sullo stesso commit.

## Regola permanente certificati PST, Atto.enc e canali deposito

Questa sezione va riletta dopo ogni compattazione prima di toccare deposito, PEC, firma digitale, Local Signer, scheduler `.cer`, `/tribunali` o `Invia deposito reale`.

### Regola di canale

`Atto.enc` e il certificato pubblico PST `.cer` dell'ufficio si applicano solo ai canali che usano la busta telematica PST con `Atto.msg` cifrato:

- `PCT/SICID`, compreso lavoro quando usa registro SICID;
- `PCT/SIECIC`;
- `SIGP/Giudice di Pace`;
- Cassazione civile/procedimento di legittimità quando usa la busta PST ministeriale.

Non si applicano, dentro il flusso deposito fascicolo IUSENTRA, a:

- `PDP penale`: usa il Portale Deposito atti Penali, non la busta PCT civile generata dallo studio;
- `PAT/SIGA amministrativo`: dal 1 febbraio 2026 il canale prioritario è Formweb; la PEC è residuale nei casi tecnici previsti;
- `PTT/SIGIT tributario`: usa il portale tributario e le regole MEF/DGT proprie;
- notifiche PEC, PEC stragiudiziale e flussi UNEP: sono canali separati dal deposito PCT del fascicolo e non devono essere dichiarati deposito PCT. Se in futuro si implementa un flusso UNEP dedicato, va documentato come canale autonomo e non ereditato dal PCT civile.

### Fonti normative operative

- PCT/PST civile e SIGP: specifiche tecniche DGSIA ex art. 34 D.M. 44/2011, provvedimento 7 agosto 2024, efficace dal 30 settembre 2024. Art. 15: atto principale in PDF/PDF-A, privo di elementi attivi, da documento testuale, firmato; firme ammesse PAdES-BES o CAdES-BES. Art. 17: nel procedimento civile la busta contiene `Atto.enc`, ottenuto dalla cifratura di `Atto.msg`; le chiavi pubbliche degli uffici sono nell'area pubblica PST e nel catalogo servizi; limite busta `60 MB`; invio via PEC ministeriale.
- PDP penale: decreto Ministero Giustizia 4 luglio 2023 e specifiche tecniche PDP pubblicate sul PST. Il deposito avviene sul PDP; limite indicato dalle specifiche PDP: `50 MB` per singolo file e `500 MB` per deposito complessivo; firme ammesse PAdES e CAdES secondo il caso.
- PAT/SIGA: regole tecnico-operative della Giustizia Amministrativa e modifica Formweb 2025/2026. Dal 1 febbraio 2026 Formweb è prioritario; limite Formweb documentato: massimo `50` file, `300 MB` per singolo file e `300 MB` complessivi.
- PTT/SIGIT: regole MEF/Dipartimento Giustizia Tributaria. Non usa `.cer` PST civile né `Atto.enc`; limite operativo aggiornato: `50 MB` per singolo file, con suddivisione dei file superiori.

### Stato tecnico certificati al controllo corrente

Controllo locale eseguito sulla cache `D:\legale\IUSENTRA\data\pst\certificati_cifratura`:

- `.cer` fisici in cache: `913`;
- `.cer` DER leggibili e validi: `913`;
- `.cer` fisici non validi: `0`;
- perimetro operativo che richiede `.cer/Atto.enc`: `593` codici ministeriali unici;
- target coperti: `593/593`;
- target mancanti o non validi: `0`;
- report job su disco: `data/pst/certificati_cifratura/audit_certificati_cifratura_pst.json`;
- ultimo report job: `ok=true`, `catalogo_pct_operativi=593`, `scaricati_o_validi=593`, `saltati_senza_certificato_pubblicato=0`, `errori=0`, `cache_cer_presenti=913`, `generated_at=2026-06-18T00:40:32.903271+02:00`.

La differenza tra `913` e `593` è voluta: `913` è la cache fisica valida complessiva; `593` è il perimetro operativo corrente degli uffici attivi che richiedono certificato PST per la cifratura `Atto.enc`. La cache conserva certificati extra validi senza usarli come obbligo su canali non pertinenti.

### Perimetro uffici coperto

Il target `593/593` comprende gli uffici attivi del catalogo PST/ministeriale che il software deve coprire per la busta PCT/SIGP:

- Corti d'Appello e uffici civili collegati;
- Tribunali ordinari e uffici civili collegati;
- Giudici di Pace/SIGP;
- Cassazione civile/PST dove prevista.

Il filtro esclude dal conteggio obbligatorio del deposito PCT:

- Procure, PDP penale e canali penali non PCT civile;
- PAT, PTT/SIGIT e portali amministrativi/tributari;
- UNEP e notifiche PEC, perché non sono il flusso `Prepara deposito` PCT del fascicolo;
- uffici storici/non attivi o sezioni accorpate che non devono bloccare il deposito corrente;
- uffici senza codice ministeriale utile alla cifratura.

### Origine dati e recupero certificati

Il software usa tre livelli, in questo ordine:

1. catalogo PST pubblico già presente in `pct/data/uffici_pst_pubblici.json`;
2. metadati ministeriali importati da `C:\QuickOrganizer\ListaUfficiGiudiziari.xml` e `C:\QuickOrganizer\QC_Uffici.xml`, riversati in `pct/data/uffici_ministero.json` e `pct/data/uffici_ministero_extra.json`;
3. fallback diretto PST per codice ministeriale e nome ufficio, anche quando il XML ministeriale non espone `nomeCertificatoCifra`.

Caso provato dall'utente e coperto: `Giudice di Pace - Palmi`, codice ministeriale `0800570152`, anche se nel XML il nome certificato è vuoto. Il downloader costruisce il nome ufficiale e scarica il `.cer` da PST; il certificato ottenuto è valido fino al 16 gennaio 2027 e ha subject `gdprc_cifra@civile.ptel.giustiziacert.it`.

### Regola fail-closed

Il risultato corretto non è promettere che il Ministero non cambierà mai catalogo. Il risultato corretto è:

- sul catalogo corrente controllato, tutti i target sono coperti (`593/593`);
- se il Ministero aggiunge, sposta o modifica un ufficio, il job `pst_certificati_cifratura_weekly` deve scaricare/validare il nuovo `.cer`;
- se per un singolo fascicolo il canale richiede `.cer` e quel `.cer` non è presente o non è valido, `Invia deposito reale` resta bloccato con motivo puntuale;
- PDP, PAT e PTT non devono essere bloccati per assenza di `.cer` PST civile, perché usano trasporti diversi;
- un deposito non deve essere registrato come valido se manca `Atto.enc` quando il canale lo richiede.

### Scheduler

Il job `pst_certificati_cifratura_weekly`:

- è settimanale, non giornaliero mascherato;
- usa `day_of_week` nel registry scheduler;
- usa worker configurabili con `PST_CERTIFICATI_CIFRATURA_WORKERS` o `PCT_PST_CERTIFICATI_CIFRATURA_WORKERS`;
- ritorna un report strutturato anche in caso di errore, così il registro scheduler non segna falsi positivi;
- scrive `source_of_truth=catalogo_pubblico_pst`, `tenant_scope=cache_tecnica_condivisa_non_operativa`, `json_authoritative=false`.

### Guardrail eseguiti su questa regola

- `python -m pytest -q tests\test_canali_telematici_deposito.py tests\test_scheduler_registry.py tests\test_checklist_atti.py tests\test_conformita_pst.py` -> esito: `59 passed`;
- controllo fisico cache `.cer`: `913` file, `913` certificati DER leggibili, `0` invalidi;
- controllo target: `593` codici unici, `0` mancanti;
- controllo policy codice: `pct_civile_dm44` usa `.cer`; `pdp_penale`, `pat_amministrativo`, `ptt_tributario` non usano `.cer` PST civile.

## Aggiornamento 2.253.56 - riallineamento locale anteprima indice e prova senza invio

Data intervento: 2026-06-17.

Perimetro verificato:

- copia Docker locale reale `http://127.0.0.1:8080`, non server temporaneo;
- container `iusentra-app` ricostruito no-cache, ricreato e healthy;
- `/api/pronto` HTTP 200, versione `2.253.56`;
- browser integrato Codex visibile sulla pagina `/fascicoli/DC5BF1DB/deposito/prepara#generazione-busta`.

Correzione applicata:

- `frontend/src/components/FascicoliPage.tsx`: il pulsante `Visualizza IndiceDocumentiDepositati.PDF` non costruisce più un URL `blob:` per l'iframe; dopo aver verificato con fetch che l'indice risponde, apre l'anteprima con l'URL diretto autenticato `/fascicoli/<id>/deposito/indice-documenti?...`;
- `tests/test_regia_ui_react.py`: aggiunto guardrail perché l'anteprima indice usi `url: previewUrl`, `downloadUrl: previewUrl` e non torni a `URL.createObjectURL` nel componente `DepositPdfPreviewButton`.

Prova materiale eseguita:

- pagina React caricata con `#root`, senza fallback legacy, senza HTML grezzo, senza `n.d.`;
- `Busta e indice` presente e caricata;
- `IndiceDocumentiDepositati.PDF` presente nella UI;
- click reale sul pulsante `Visualizza IndiceDocumentiDepositati.PDF`;
- modal aperto con titolo `IndiceDocumentiDepositati.PDF`, pulsanti `Scarica` e `Chiudi`;
- iframe circa `1180 x 630`, URL diretto `/fascicoli/DC5BF1DB/deposito/indice-documenti?...`, non `blob:`;
- viewer PDF Chrome visibile con toolbar, miniatura, pagina `1/1`, zoom `100%` e contenuto `Indice documenti depositati`;
- screenshot prova indice: `C:\Users\antmm\AppData\Local\Temp\iusentra-dc5bf1db-indice-pdf-diretto-225356.png`.

Prova senza invio e simulazione:

- `Prova senza invio reale` abilitato;
- conferma visibile: `Preparare busta, indice documenti, destinatario e testo PEC senza inviare nulla?`;
- barra avanzamento visibile con `DatiAtto.xml`, `IndiceDocumentiDepositati.PDF`, tutti i documenti `.p7m` selezionati e `Atto.enc`;
- esito visibile: `Prova deposito preparata: busta, indice, destinatario e testo PEC sono pronti per il controllo. Nessun invio PEC reale è stato eseguito.`;
- destinatario PEC: `gdp.palmi@civile.ptel.giustiziacert.it`;
- oggetto PEC: `DEPOSITO TELEMATICO - ATTO_GENERICO - RG 466/2023`;
- documenti indicati nel pacchetto: `DatiAtto.xml`, atto principale, allegati `.p7m` e `IndiceDocumentiDepositati.PDF`;
- corpo PEC visibile e coerente con `Atto.enc`;
- `Simula invio PEC` confermata con testo esplicito `senza spedire nulla all'esterno`;
- toast visibile: `Simulazione invio PEC registrata nel fascicolo. Nessun invio esterno eseguito.`;
- screenshot prova senza invio/simulazione: `C:\Users\antmm\AppData\Local\Temp\iusentra-dc5bf1db-prova-senza-invio-simulazione-225356.png`.

Stato del bottone reale osservato:

- `Invia deposito reale` resta disabilitato con motivo puntuale: `Invio reale sospeso: completa i controlli obbligatori indicati nella prova.`;
- il requisito mancante mostrato nella prova locale è `PEC mittente dello studio non configurata. Configura la PEC dello studio prima dell'invio reale.`;
- non risultano più blocchi visivi su indice PDF o certificato `.cer` Palmi nella prova locale aggiornata.

Guardrail eseguiti:

- `python -m pytest -q tests\test_regia_ui_react.py::test_ui_deposito_prova_guidata_non_salta_firma_e_mostra_audit_pec_indice`;
- `pnpm --filter @iusentra/studio typecheck`;
- `pnpm --filter @iusentra/studio build`;
- Docker locale: `docker compose build --no-cache app`, `docker compose up -d --force-recreate app`, container healthy, `/api/pronto` OK.

Stato ancora aperto prima della chiusura complessiva:

- configurare/verificare PEC mittente dello studio per abilitare realmente l'invio locale, oppure dimostrare su server che il tenant ha già mittente/SMTP completo;
- ripetere prova server sul commit allineato;
- commit, push branch gemelli, check GitHub/CodeQL, deploy Hetzner, `/api/pronto` server e igiene repository.

## Aggiornamento 2.253.54 - prova locale React deposito, indice e simulazione PEC

Data intervento: 2026-06-17.

Perimetro richiesto dall'utente:

- superficie React, non legacy, sulla copia locale reale `http://127.0.0.1:8080`;
- fascicolo reale locale `DC5BF1DB` (`RG 466/2023 - Alessi Robertino`);
- verifica visiva prima dei gate lunghi, con controllo di layout, indice PDF, corpo PEC modificabile, simulazione PEC e blocco puntuale del pulsante reale.

Prova materiale eseguita:

- container locale `iusentra-app` aggiornato e healthy, `/api/pronto` HTTP 200;
- pagina aperta in Google Chrome installato, modalità visibile, URL `/fascicoli/DC5BF1DB/deposito/prepara#generazione-busta`;
- `#root` React presente, nessun fallback legacy, nessun HTML grezzo visibile, nessun `n.d.`;
- ufficio e destinatario risolti da SQL/tenant: `Ufficio del Giudice di Pace di Palmi`, codice ufficio `0910401`, codice ministeriale `0800570152`, PEC `gdp.palmi@civile.ptel.giustiziacert.it`;
- card busta leggibili: l'atto principale `Note conclusive Alessi Robertino.pdf.p7m` non viene più spezzato verticalmente;
- `IndiceDocumentiDepositati.PDF` visualizzato nel viewer PDF con risposta `application/pdf`, `ATTO_GENERICO`, `RG 466/2023`, codice oggetto `145009` ed elenco documenti;
- `Modifica testo PEC` apre un campo editabile solo su scelta dell'avvocato; il testo standard resta usato automaticamente e contiene `Atto.enc` e l'elenco documenti;
- `Simula invio PEC` mostra barra di avanzamento con `DatiAtto.xml`, `IndiceDocumentiDepositati.PDF`, documenti selezionati e `Atto.enc`;
- la simulazione restituisce HTTP 200 e non produce errori console; la preview mostra destinatario PEC, oggetto `DEPOSITO TELEMATICO - ATTO_GENERICO - RG 466/2023`, riferimento prova, elenco documenti, testo PEC e controlli obbligatori mancanti;
- `Invia deposito reale` resta disabilitato solo se nella singola prova manca un requisito obbligatorio reale. Stato aggiornato `2.253.56`: il certificato PST `.cer` dell'ufficio `0800570152` non è più un mancante globale quando la cache corrente è presente; il blocco residuo corretto deve riguardare `Atto.enc` AES256 generato da `Atto.msg`, PEC mittente dello studio configurata o altro requisito effettivamente non presente nella prova.

Correzione applicata:

- nel ramo React `/fascicoli/<id>/deposito/invia-pec`, le modalità `prova_senza_invio=1` e `simula_invio_pec=1` ora restituiscono JSON HTTP 200 quando il pacchetto di controllo è stato preparato ma l'invio reale resta sospeso per requisiti obbligatori;
- il 409 resta per l'invio reale non conforme, così la UI può distinguere prova guidata da errore operativo.

Guardrail aggiunti/eseguiti:

- `python -m pytest tests/test_deposito.py::test_deposito_invia_pec_simulazione_guidata_non_restituisce_conflitto_http -q`;
- screenshot temporanei fuori repository: layout busta corretto, indice PDF visualizzato, editor corpo PEC, preview simulazione PEC.

Limiti residui:

- non è stato eseguito invio PEC reale;
- la firma multipla con PIN/token reale resta dichiarabile solo dopo firma effettiva di più documenti nella UI e salvataggio dei `.p7m`;
- prima della chiusura complessiva restano commit, push branch gemelli, check GitHub/CodeQL, deploy Hetzner e prova server sullo stesso commit.

## Aggiornamento 2.253.53 - matrice canali e scheduler certificati PST

Data intervento: 2026-06-17.

Chiarimento permanente dopo richiamo utente:

- il deposito non può essere ridotto al solo PCT civile: ogni canale ha normativa, trasporto, firma, ricevute e blocchi propri;
- il job `.cer` è solo il presidio tecnico dei canali che cifrano `Atto.msg` in `Atto.enc` con certificato pubblico PST dell'ufficio;
- PDP, PAT, PTT, notifiche PEC, UNEP e PEC stragiudiziale devono continuare a essere trattati come canali autonomi, senza ereditare certificati o blocchi PCT.

Matrice operativa aggiornata:

- `PCT/SICID`, `PCT lavoro/SICID`, `PCT/SIECIC`, `SIGP/Giudice di Pace`: fonti Ministero della Giustizia/PST, DM 44/2011 art. 34 e specifiche tecniche DGSIA 7 agosto 2024 efficaci dal 30 settembre 2024. IUSENTRA deve risolvere codice oggetto PST, ufficio, PEC, firma documentale, `DatiAtto.xml`, `IndiceDocumentiDepositati.PDF`, `Atto.msg`, certificato `.cer` PST e `Atto.enc` AES256. Se il `.cer` del proprio ufficio non è verificato o `Atto.enc` non è generato, l'invio reale è bloccato e la UI deve dire quale requisito manca.
- `PDP penale`: fonti PST/Ministero della Giustizia, Decreto Ministero Giustizia 4 luglio 2023 e specifiche tecniche Portale Deposito atti Penali efficaci dal 20 luglio 2023. Non genera busta PCT civile, non usa `DatiAtto.xml` civile e non usa `.cer` PST/`Atto.enc`. IUSENTRA deve preparare e controllare atti/allegati/firme secondo PDP, guidare o importare il deposito dal portale e salvare ricevute/esiti.
- `PAT/SIGA amministrativo`: fonti Giustizia Amministrativa, regole tecnico-operative PAT e modifica 2025/2026. Dal 1 febbraio 2026 Formweb è il canale prioritario; PEC è residuale solo per casi tecnici previsti. Non usa `.cer` PST civile né `Atto.enc` PCT. IUSENTRA deve preparare modulo/atto, allegati, firma PAdES quando richiesta, checklist PAT, upload assistito e ricevute.
- `PTT/SIGIT tributario`: fonti MEF/Dipartimento Giustizia Tributaria e Gazzetta Ufficiale, specifiche tecniche 6 novembre 2020 e modifiche 21 aprile 2023. Non usa `.cer` PST civile né `DatiAtto.xml` PCT. IUSENTRA deve controllare PDF/A quando richiesto, firme, limiti file, upload SIGIT e ricevute.
- `UNEP`, notifiche PEC e PEC stragiudiziale: canali separati dal deposito. Servono relata/testo, destinatari, domicilio digitale, firme e ricevute proprie; non devono essere dichiarati deposito PCT e non devono attivare `Atto.enc` salvo regola futura documentata.

Controllo scheduler `.cer`:

- cache operativa locale inizialmente assente per Vicenza e server;
- prova live ufficiale su codice ufficio `0241160092` ha scaricato il certificato PST del `Tribunale Ordinario - Vicenza`, SHA256 `28D0A5456A542FAC99B772AAE6B5F7E8AD909E1F569ED8D1EFD929DE9DC708AA`, valido fino all'11 gennaio 2029;
- su Hetzner il download falliva per catena TLS incompleta (`TI Trust Technologies OV CA` non inviato come intermedio completo al client Python); il downloader ora usa `certifi` e carica solo l'intermedio TI Trust/Sectigo pinnato con SHA256 `1BFD8702D8F9BB340F353820330C0BBA7E522C63164C91F295414DAC797F0863`, senza disabilitare la verifica SSL;
- dopo hotfix sul container Hetzner, `scripts/precarica_certificati_cifratura_pst.py --codice-ufficio 0241160092 --strict` ha scaricato `/data/pst/certificati_cifratura/0241160092.cer` con esito `ok=true`;
- dopo `repair_deposit_profiles(verify_certificates=True)` sui database server, il fascicolo `E5AE4668` (`2026/330`, `Marchetti c. MIM`, `Carta docente`) ha profilo SQL verificato: canale `pct_civile_dm44`, codice `222050`, ufficio `Tribunale di Vicenza`, codice ufficio `0241160092`, PEC `tribunale.vicenza@civile.ptel.giustiziacert.it`, `.cer` verificato e nessun blocco profilo;
- `scripts/precarica_certificati_cifratura_pst.py` accetta ora `--codice-ufficio` per controlli mirati su fascicoli reali;
- `precarica_certificati_cifratura` limita il ciclo settimanale ai canali PCT/SIGP che richiedono `.cer` per `Atto.enc`; uffici non operativi, non PCT o senza certificato pubblicato sono riportati come saltati/avvisi del report e non fanno fallire gli altri certificati;
- il singolo deposito resta comunque fail-closed: se il proprio canale richiede `.cer` e quel `.cer` non è verificato, l'invio reale non deve essere registrato come deposito valido.

Fonti ufficiali riconsultate:

- PST Ministero della Giustizia, specifiche tecniche ex art. 34 DM 44/2011 - provvedimento 7 agosto 2024;
- PST Ministero della Giustizia, specifiche tecniche PDP penale 2023;
- Giustizia Amministrativa, Processo Amministrativo Telematico e avviso Formweb/PEC dal 1 febbraio 2026;
- Gazzetta Ufficiale, specifiche tecniche Processo Tributario Telematico 6 novembre 2020 e modifiche 21 aprile 2023.

## Aggiornamento 2.253.50 - prova reale locale firma multipla, indice e prova senza invio

Data intervento: 2026-06-17.

Prova reale eseguita su macchina locale dell'utente:

- URL verificato: `http://127.0.0.1:8080/fascicoli/DC5BF1DB/deposito/prepara#generazione-busta`;
- versione runtime reale: `2.253.50`, verificata con `GET /api/pronto`;
- fascicolo locale di prova: `RG 466/2023 - Alessi Robertino`, ufficio `Giudice di Pace - Palmi`;
- superficie: React deposito su Docker locale reale, container `app`, `scheduler-worker` e `ocr-worker` healthy;
- azione materiale: inserito il PIN nel pannello Local Signer e confermato `Firma e prepara prova`;
- stato iniziale visto: 8 documenti candidati busta, 4 già firmati, 4 documenti da firmare nel comando busta;
- esito firma multipla: i 4 documenti non firmati sono stati firmati e salvati come `.pdf.p7m`; la UI è passata a `8 firmati`, `0 documenti da firmare`, `Firme coerenti`;
- file firmati osservati dopo la prova: `attoACQ.pdf.p7m`, `Note trattazione scritta Alessi Robertino c Zurich Ass.ni-signed.pdf.p7m`, `Note conclusive Alessi Robertino.pdf.p7m`, `Istanza trattazione scritta Alessi Robertino.pdf.p7m`;
- azione successiva: click reale su `Prova senza invio reale`, conferma del pannello e osservazione della barra `PREPARAZIONE DEPOSITO IN CORSO`;
- progress bar osservata: nome corrente `IndiceDocumentiDepositati.PDF` e ticker con `DatiAtto.xml`, `IndiceDocumentiDepositati.PDF`, tutti gli 8 `.p7m` e `Atto.enc`;
- esito prova senza invio: toast `Busta generata e scaricata`, nessun blocco su `Operazione...`, nessun errore tecnico grezzo PST o URL `servizipst` nella UI;
- testo PEC: visibile e modificabile facoltativamente; dopo la firma elenca gli 8 documenti `.p7m`;
- anteprima indice: click su `Visualizza IndiceDocumentiDepositati.PDF`, modal con titolo, pulsanti `Scarica`/`Chiudi` e iframe diretto visibile circa `1180 x 681`, senza riquadro grigio/vuoto;
- screenshot locale prova indice: `C:/Users/antmm/AppData/Local/Temp/iusentra-deposito-indice-firma-reale-225350.png`.

Correzioni e presidi collegati:

- `frontend/src/components/FascicoliPage.tsx`: la chiamata Local Signer `/firma-batch` ora ha timeout controllato a 45 secondi con `AbortController`; se il servizio locale non risponde, la UI mostra un errore esplicito e non prosegue alla busta senza firme salvate;
- la modifica non cambia il comportamento positivo della firma multipla: nella prova reale il lotto è stato firmato e salvato correttamente;
- `tests/test_regia_ui_react.py`: aggiunto guardrail statico su timeout firma batch, `AbortController`, `signal: controller.signal` e messaggio utente.

Limiti residui visti nella prova locale:

- il fascicolo locale `DC5BF1DB` è un fascicolo Giudice di Pace: nelle prove storiche la PEC ufficio non era presente nel catalogo locale e la UI mostrava `Indirizzo PEC non disponibile dal catalogo uffici`; stato aggiornato `2.253.56`: i metadati `C:\QuickOrganizer` e il fallback PST diretto coprono `Giudice di Pace - Palmi`/`0800570152`, quindi quell'avviso non deve ricomparire se cache e profilo sono aggiornati;
- la conformità ministeriale finale resta subordinata alla generazione reale di `Atto.enc` quando il canale/ufficio richiede cifratura ministeriale; la prova locale conferma firma multipla, indice, testo PEC e busta di controllo, non registra un deposito valido inviato.

## Aggiornamento 2.253.47 - prova reale busta, PEC e certificato PST guidato

Data intervento: 2026-06-17.

Prova reale eseguita su produzione:

- URL verificato: `https://app.iusentra.it/fascicoli/E5AE4668/deposito/prepara#generazione-busta`;
- fascicolo: `2026/330`, `Marchetti c. MIM`, cliente `Marchetti Lucia`;
- superficie: React deposito sul server Hetzner `app.iusentra.it`, sessione utente autenticata;
- azione materiale: click su `Prova senza invio reale`, conferma del pannello e osservazione della barra di avanzamento;
- esito visibile: barra `Preparazione deposito in corso` con scorrimento di `DatiAtto.xml`, `IndiceDocumentiDepositati.PDF`, documenti `.p7m` selezionati e `Atto.enc`;
- esito finale: pannello `Prova senza invio PEC` con destinatario `tribunale.vicenza@civile.ptel.giustiziacert.it`, oggetto `DEPOSITO TELEMATICO - RICORSO - Tribunale di Vicenza`, testo PEC predisposto e documenti indicati nel pacchetto;
- controllo regressione: non compare più l'errore tecnico grezzo `Download PST non riuscito` né l'URL PST nel contenuto visibile della UI;
- blocco corretto al momento della prova storica: `Invia deposito reale` restava disabilitato perché mancavano certificato pubblico PST `.cer` e `Atto.enc` AES256 conforme. Stato aggiornato `2.253.56`: i certificati PST del catalogo operativo risultano coperti; se il bottone resta disabilitato, il motivo non deve più essere un `.cer` già coperto, ma solo `Atto.enc` AES256, PEC mittente o altro requisito reale della singola pratica.

Correzioni applicate:

- `frontend/src/components/FascicoliPage.tsx`: la prova/invio deposito mostra una progress bar con nome del file in lavorazione e ticker dei documenti; il corpo PEC è visibile e modificabile solo facoltativamente; l'anteprima `IndiceDocumentiDepositati.PDF` usa URL diretto; la spunta `Da firmare` non viene mostrata sui documenti non selezionati per la busta;
- `frontend/src/components/FascicoliPage.css`: aggiunti stili per il blocco testo PEC e per la progress bar/ticker della busta;
- `pct/busta.py`: `Atto.msg` viene tracciato nell'audit prima del recupero certificato; se il `.cer` PST non è disponibile, l'audit resta consultabile e l'invio reale resta bloccato senza perdere il pacchetto di controllo;
- `web/bootstrap/deposito_routes.py`: le route React e storica trasformano `PSTCifraturaError` in risposta guidata `requires_guided_completion`, senza inviare alla UI il messaggio tecnico grezzo del download PST.

Guardrail tecnici eseguiti dopo la prova reale:

- `python -m pytest tests/test_busta.py -q`;
- `python -m pytest tests/test_deposito.py::test_deposito_invia_pec_civile_usa_local_signer_se_server_send_disabilitato -q`;
- `python -m pytest tests/test_regia_ui_react.py::test_ui_deposito_prova_guidata_non_salta_firma_e_mostra_audit_pec_indice -q`.

Limite residuo operativo:

- il software prepara indice, testo PEC, `Atto.msg` e audit del pacchetto, ma non deve registrare un deposito valido finché non viene generato `Atto.enc` ministeriale cifrato AES256 con certificato pubblico PST dell'ufficio;
- la prova firma multipla con token fisico/PIN resta da ripetere solo quando si esegue realmente il comando di firma; il PIN non è stato scritto nei file di progetto.

## Aggiornamento 2.253.46 - prova reale server e guardrail anti-lock deposito

Data intervento: 2026-06-17.

Prova reale eseguita su produzione:

- URL verificato: `https://app.iusentra.it/fascicoli/E5AE4668/deposito/prepara`;
- fascicolo: `2026/330`, `Marchetti c. MIM`, cliente `Marchetti Lucia`;
- superficie: React deposito sul server Hetzner `app.iusentra.it`, sessione utente autenticata;
- primo caricamento reale: la pagina ha mostrato `n.d.`, zero documenti e `Caricamento...` perché `/api/v1/ui/fascicoli/E5AE4668?include=all` ha ricevuto un lock transitorio SQLite su `studio.db`;
- dopo ricarica reale: API `include=all` ha risposto 200 e la UI ha mostrato `Tribunale di Vicenza`, canale `PCT lavoro / SICID`, 13 documenti letti, 11 candidati busta, 4 firmati e 7 da firmare.

Correzione applicata:

- `pct/storage.py`: `StudioDB.ensure_schema()` riusa la connessione thread-local esistente e ritenta se lo schema SQLite è temporaneamente occupato;
- `frontend/src/fascicoliData.ts`: le chiamate dati fascicoli ritentano brevemente su errori transitori `408/423/429/5xx`, evitando che un lock momentaneo sostituisca i dati reali con fallback vuoto;
- `frontend/src/components/FascicoliPage.css`: la vista `Prepara deposito` è stata resa più compatta su server e locale, riducendo testata, pulsanti, cockpit, badge e percorso deposito senza cambiare le regole di firma o conformità;
- versione riallineata a `2.253.46`.

Esito firma documento per documento osservato nella UI:

- i file `.pdf.p7m` osservati risultano `Firmato`;
- i file `.PDF` o `.pdf` non PAdES osservati restano `Da firmare`, anche quando il nome o il contenuto testuale potrebbero contenere la parola "Firmato";
- esempi visti come `Da firmare`: `Carta Identità e C.F. Lucia Marchetti.PDF`, `Contratto Rossi 2025-2026.pdf`, `Ricorso.pdf`, `Sentenza Cassazione.PDF`, `Sentenza_Tribunale_Vicenza_20-04-2023.PDF`;
- esempi visti come `Firmato`: `Autocertificazione ricorso.PDF.p7m`, `Autocertificazione situazione reddituale.PDF.p7m`, `Contratto 24-25.pdf.p7m`, `Procura.PDF.p7m`.

Limite residuo:

- prova firma multipla con token fisico/PIN non ancora ripetuta dopo il fix `2.253.46`;
- l'invio reale resta bloccato finché manca `Atto.enc` ministeriale cifrato AES256 conforme, come mostrato nella UI.

## Aggiornamento 2026-06-17 - profilo deposito SQL da preventivo a fascicolo

Data intervento: 2026-06-17.

Regola dati applicata:

- la fonte operativa è sempre SQL: `studio.db` in locale e PostgreSQL in produzione;
- i JSON tenant-aware restano solo mirror, bootstrap, import/export storico o cache rigenerabile;
- il profilo deposito non deve restare nascosto solo in `dati_json`: deve essere salvato anche nella colonna dedicata `profilo_deposito_json`;
- la colonna dedicata esiste e viene riallineata su `fascicoli`, `preventivi_records` e `conferimenti_records`, sia per SQLite sia per PostgreSQL;
- `StudioDB.ensure_schema()` applica l'upgrade idempotente anche su database già esistenti, così i tenant attivi non restano con una struttura vecchia dopo il deploy.

Flusso operativo deciso:

- quando nasce un preventivo o un fascicolo veloce, IUSENTRA prova a risolvere subito canale, regola canale, codice deposito, ufficio giudiziario, PEC ufficiale e certificato di cifratura `.cer` quando il canale lo richiede;
- quando il preventivo viene accettato, il profilo passa al conferimento incarico;
- quando dal conferimento incarico nasce il fascicolo, il profilo passa al fascicolo e viene rafforzato con i dati effettivi del fascicolo, in particolare ufficio giudiziario e codice deposito;
- la stessa logica vale anche per `Nuovo Fascicolo` e `Fascicolo veloce` autonomi: anche se non nascono da preventivo o conferimento, devono risolvere canale, regole, codice deposito, PEC ufficio, ufficio giudiziario e certificato `.cer` quando richiesto;
- il fascicolo non deve perdere il profilo se viene creato da preventivo, da conferimento, da form nuovo fascicolo o da fascicolo veloce;
- PAT, PTT e PDP sono canali distinti: non devono usare in modo improprio il certificato PST civile, ma devono avere regole dedicate e stato di validazione separato.

Fonti ufficiali rilette per la matrice canali:

- Portale Servizi Telematici del Ministero della Giustizia, documentazione e servizi PCT/PDP;
- Giustizia Amministrativa, sezione Processo Amministrativo Telematico;
- Dipartimento della Giustizia Tributaria, sezione Processo Tributario Telematico PTT/SIGIT.

Guardrail tecnici eseguiti:

- `python -m pytest tests/test_profilo_deposito.py -q`;
- `python -m pytest tests/test_profilo_deposito.py tests/test_canali_telematici_deposito.py tests/test_busta.py tests/test_simulazione_deposito.py tests/test_deposito_server_dry_run_audit.py tests/test_scheduler_registry.py -q`.

Guardrail aggiunto dopo chiarimento utente:

- `test_fascicolo_autonomo_risolve_profilo_deposito_senza_preventivo` crea un fascicolo diretto senza preventivo/conferimento e verifica canale PCT, codice `222050`, PEC del Tribunale di Vicenza, certificato `.cer` verificato e colonna SQL `profilo_deposito_json` popolata.

Stato prova reale:

- verificato su server reale in `2.253.46` per caricamento profilo, canale, documenti, stati firma CAdES/PAdES e blocco invio non conforme;
- prima della chiusura completa restano obbligatori commit, push branch gemelli, controlli GitHub/CodeQL, deploy Hetzner del fix `2.253.46`, prova post-deploy sulla vista compatta e igiene repository.

Aggiornamento operativo 2.253.45:

- rilanciato il blocco mirato deposito/canali/busta/scheduler e il guardrail React deposito dopo il chiarimento sul fascicolo autonomo;
- aggiunto il presidio documento per documento sulla firma digitale: `Firmato` in UI deriva solo da contenitore CAdES (`.p7m`/PKCS#7) o da prova tecnica PAdES salvata nel fascicolo;
- un file `.PDF` resta `Da firmare` se contiene solo testo o nome con "Firmato", oppure solo il vecchio flag `firmato`/`signed`, senza firma PAdES interna verificabile;
- la route di upload firma ora rifiuta PDF non PAdES e `.p7m` non CAdES, e salva nel fascicolo un metadato tecnico `signature_metadata` quando la firma è provata;
- se `studio.db` è vuoto, il JSON configurato viene usato solo per bootstrap controllato e poi rigenerato come mirror dopo il salvataggio SQL;
- confermati `pnpm --filter @iusentra/studio build`, retention asset React, packaging e `git diff --check`;
- il PIN fornito dall'utente per la firma reale non è stato scritto in file né log applicativi e va usato solo durante la prova materiale in UI;
- la chiusura resta subordinata a prova reale su `127.0.0.1:8080`, commit/push branch gemelli, CI/CodeQL, deploy Hetzner, health e prune Docker.

## Aggiornamento 2.253.44 - presidio CI SQL prima della prova server

Data intervento: 2026-06-17.

Stato operativo:

- rilevata sullo SHA `0f3a8eb` una failure di `Pytest core fase 6/10 parte 9/16`;
- corretto il presidio: il test semina `studio.db` con record SQL reali e svuota i JSON mirror per confermare che l'attivazione SQLite resti no-op SQL e non cancelli dati;
- verifiche locali verdi: shard 6/10 parte 9/16, test mirato e `tests/test_database.py` completo.

La prova deposito server resta aperta: non e' chiusa finche' non vengono verificati visivamente su `https://app.iusentra.it` selezione documenti, firma multipla Local Signer con PIN/token reale, creazione busta, indice documenti, testo email e dry-run senza invio PEC.

## Aggiornamento 2.253.43 - gate CI prima della prova server

Data intervento: 2026-06-17.

Stato operativo:

- il deposito e la firma multipla restano aperti fino alla prova visiva reale su `https://app.iusentra.it/fascicoli/E5AE4668/deposito/prepara`;
- prima della prova server e del deploy finale sono stati chiusi localmente i due rossi GitHub rimasti sullo SHA precedente: `Pytest core fase 6/10 parte 10/16` e `Pytest core fase 10/10`;
- il test database amministrazione ora conferma la regola `SQL operativo`: quando `studio.db` e' popolato, i JSON non sono piu' fonte vera ma mirror;
- i test Lex/Local AI usano un servizio applicativo finto ma conforme a `LexResponse` solo nei casi in cui devono verificare prompt, policy, follow-up e allegati, evitando timeout non pertinenti al deposito.

Guardrail tecnici confermati:

- `python -m pytest -q tests/test_local_ai.py --durations=10`;
- `python -m pytest -q tests\test_assistente_followup.py --durations=10`;
- `python -m pytest -q tests\test_web_bootstrap.py --durations=10`;
- `python scripts\run_pytest_phases.py --core-shard 6 --core-total-shards 10 --core-subshard 10 --core-total-subshards 16 --core-subdivide-items --timeout-minutes 5`;
- `python scripts\run_pytest_phases.py --core-shard 10 --core-total-shards 10 --core-subshard 1 --core-total-subshards 1 --timeout-minutes 5`.

Da fare prima della chiusura:

- commit e push dei branch gemelli;
- attesa completa dei gate GitHub, incluso `Code scanning results / CodeQL`;
- deploy Hetzner sullo stesso commit;
- verifica server con browser reale, scroll completo, dry-run deposito senza invio PEC e prova firma multipla reale con PIN/token.

Questo file va riletto prima di ogni intervento su `Prepara deposito`, busta, firma multipla, notifiche legali, portali telematici, agenda/scadenziario collegati a PEC e ricevute. Non sostituisce `AGENTS.md`: lo integra come memoria operativa specifica del deposito.

## Aggiornamento 2026-06-17 - hotfix CI dopo prova server deposito

Il primo push del lavoro deposito ha lasciato GitHub rosso sullo SHA `499e156` anche se la prova server hotfix era stata eseguita. Il lavoro non è considerato chiuso finché il nuovo SHA non passa CI/CodeQL, deploy Hetzner e riallineamento locale.

Correzioni applicate:

- la pre-verifica SQLite non confronta più `Impostazioni` come JSON grezzo: per gli studi SQL usa le sezioni normalizzate `settings_config`, così i JSON storici restano bootstrap/mirror e non diventano fonte di verità;
- il blocco anti-perdita resta operativo per dati core come clienti, fascicoli, agenda, scadenze, soggetti e comunicazioni;
- la route amministrativa database è stata alleggerita spostando l'ottimizzazione SQLite in helper dedicato, senza cambiare il flusso visibile;
- OpenAPI e versione sono riallineati a `2.253.38`.

Test locali mirati eseguiti prima del nuovo rilascio:

- database/pre-verifica SQLite Impostazioni e anti-perdita dati core;
- governance repository;
- provider OpenAPI;
- smoke contratti App V2;
- test mirati deposito React, classificazione, UI e nomi `.p7m`.

Stato: da chiudere con nuovo commit, push branch gemelli, check GitHub/CodeQL, deploy Hetzner, `/api/pronto` produzione, prune Docker e riallineamento Docker locale reale.

Nota successiva sullo SHA `116b3cf`: i gate SQL, governance, provider e CodeQL sono passati, ma il job `Local Signer e PKCS#11 (ubuntu-latest) parte 2/4` ha evidenziato un dist Local Signer non allineato al sorgente e un guardrail batch non aggiornato a `cert_thumbprint`. Il rilascio resta aperto finché il nuovo SHA non conferma anche la matrice Local Signer.

Nota successiva sullo SHA `9e0a776`: il fix precedente ha sbloccato il caso batch, ma la matrice remota ha segnalato anche `macos-latest` parte 3/4 sulla firma singola. Sono stati aggiornati i guardrail di firma singola e batch; localmente sono passati tutti gli shard Local Signer/PKCS#11 1/4, 2/4, 3/4 e 4/4. Il rilascio resta comunque aperto fino al verde remoto, deploy e riallineamento locale.

Nota successiva sullo SHA `49f9d8c`: `Coverage moduli critici parte 4/12` ha segnalato un test obsoleto che pretendeva ancora il fallback a JSON quando SQLite non è disponibile. La regola definitiva resta: SQL va creato/riallineato; se non riesce, il flusso si blocca con messaggio chiaro e non usa JSON storici come verità operativa.

Nota successiva sullo SHA `995683b`: `Coverage moduli critici parte 10/12` ha segnalato una seconda migrazione falsa su archivi tenant vuoti come `privacy/registro.json`, anche se `studio.db` era già inizializzato. Il runtime ora riconosce `settings_config` e i mirror SQL come seed valido e non rilancia migrazioni inutili, mantenendo SQL come fonte operativa.

## Aggiornamento 2026-06-17 - prova server reale e fix rapidi UI deposito

Ambiente verificato: produzione `https://app.iusentra.it`, fascicolo reale `E5AE4668` (`2026/330 - Marchetti Lucia`), studio `studio-legale-giuseppe-montagnese`.

Interventi applicati prima sul server, come richiesto dal workflow server-first:

- corretto l'adattamento topbar su laptop: il pulsante `+ Nuovo` non viene più tagliato e `Assistenza remota` passa a icona compatta sotto 1600 px;
- corretto il widget Lex chiuso: su tablet/mobile non resta più sovrapposto al logo, alla topbar o alla lista deposito;
- corretto il menu `Ruolo` della lista `Documenti da inviare`: il menu resta allineato sotto il campo, non esce dalla card e ora si chiude con `Esc`;
- confermato che `Da firmare` funziona a menu chiuso e, dopo il fix `Esc`, anche subito dopo avere aperto/chiuso il menu ruolo;
- verificato che i documenti firmati vengono mostrati con estensione reale `.pdf.p7m` e microcopy `File firmato .p7m`, senza dichiarare firmato un PDF non firmato;
- verificato che il lettore apre un `.p7m` direttamente in anteprima, con titolo documento, pulsanti `Scarica` e `Chiudi`, senza obbligare l'avvocato a scaricare il file;
- verificata la pagina firma singola reale `/fascicoli/E5AE4668/documenti/1CE0BB0F/firma`: mostra di nuovo `Modalità firma visibile nel PDF`, posizione firma, luogo, data/ora, PIN token e `Firma tramite Local Signer`; non mostra più il pannello inutile `Riallinea automaticamente`.

Prove visive server eseguite con browser reale collegato alla sessione autenticata:

- desktop 1524x857: scroll alto, centro e fondo della pagina `Prepara deposito`;
- tablet 900x857: scroll alto, centro e fondo della pagina `Prepara deposito`;
- mobile 430x857: scroll alto, centro e fondo della pagina `Prepara deposito`;
- click reale del menu `Ruolo`: 1 menu aperto, rettangolo menu allineato al campo, voci `Atto principale`, `Procura alle liti`, `Allegato`, `Prova notifica`, `Fuori busta`;
- pressione `Esc`: menu aperto `1 -> 0`;
- click reale `Da firmare`: stato `true -> false -> true`;
- click reale `Visualizza` su `Autocertificazione ricorso.PDF.p7m`: visualizzatore aperto e contenuto PDF visibile;
- fase `Firma`: stato visibile `0 documenti da firmare` e `Firme coerenti`, senza `Local Signer non rilevato` e senza riallineamento inutile;
- fase `Busta e indice`: aperta con click reale dal percorso deposito, non con hash manuale; mostrati `DatiAtto.xml`, `IndiceDocumentiDepositati.PDF` e documenti `.p7m` selezionati;
- click reale `Genera controllo e indice`, conferma modale `Prepara controllo`, download `Busta_2026-330_RICORSO.enc`.

Esito pacchetto scaricato nella prova server:

- file: `Busta_2026-330_RICORSO.enc`;
- dimensione download browser: 12.834.405 byte;
- SHA-256 locale della prova: `8d8c5f146970f480d179c7022ac885c90baf09c2a189bdf4deff3df62b7d2d94`;
- il file è un pacchetto di controllo leggibile come archivio zip, non un invio PEC e non va registrato come deposito valido ministeriale;
- voci presenti: `DatiAtto.xml`, `Autocertificazione ricorso.PDF.p7m`, `Autocertificazione situazione reddituale.PDF.p7m`, `Procura.PDF.p7m`, `IndiceDocumentiDepositati.PDF`;
- non è stata chiamata la route di invio PEC e nella UI non compare testo di PEC inviata.

Stato operativo:

- la parte server visibile del deposito è migliorata e provata sul fascicolo reale;
- resta obbligatorio riallineare la copia locale, eseguire build/gate mirati, aggiornare gli artefatti React, fare commit, push dei branch gemelli, controlli GitHub/CodeQL e deploy ordinato sullo stesso commit;
- il pacchetto generato è correttamente un pacchetto di controllo: finché manca l'adapter ministeriale per `Atto.enc` AES256, il software deve continuare a spiegare il limite e non deve presentarlo come deposito valido inviato.

## Regola utente non negoziabile

- Il deposito non va trattato come “fase finale guidata” da rinviare: il software deve risolvere subito tutto ciò che può risolvere.
- L’avvocato deve arrivare alla pagina `Prepara deposito` e vedere una proposta pronta, chiara e correggibile: atto principale, allegati, prove, ricevute, documenti da firmare, indice e canale.
- Se il software non riesce a classificare un documento con certezza, deve chiedere all’avvocato di selezionare/correggere solo quel punto, spiegando cosa manca e perché.
- Bloccano l’invio solo requisiti obbligatori previsti dal canale e dalla normativa. Le mancanze non obbligatorie sono avvisi professionali, non blocchi.
- Nessun blocco muto: ogni blocco deve indicare esattamente cosa manca e cosa deve fare l’avvocato per procedere.
- Non dichiarare la firma multipla funzionante finché, su `127.0.0.1:8080` con browser reale, l’utente non inserisce il PIN e il software firma più documenti nella stessa operazione, salva ogni `.p7m` nel fascicolo e abilita il passo successivo.
- Ogni intervento operativo su deposito, fascicolo, classificazione documenti, portali ministeriali, PEC, notifiche legali, firma digitale, Local Signer, PKCS#11, buste o ricevute deve essere trascritto in file. La traccia deve dire cosa è stato cambiato, quali fonti/norme sono state usate, quali test sono stati eseguiti, se la prova reale su `127.0.0.1:8080` è stata fatta oppure manca, e quali limiti restano aperti.

## Fonti ufficiali rilette il 2026-06-14

- PST, specifiche tecniche ex art. 34 D.M. 44/2011, provvedimento DGSIA 7 agosto 2024.
- PST, formato messaggi PEC e flusso deposito: il depositante predispone atto e allegati; il software produce la busta telematica; la PEC trasporta la busta; RdA/RdAC/esiti vanno presidiati.
- PST, aggiornamento algoritmo cifratura busta telematica: introduzione AES256 per `Atto.msg` e dismissione 3DES; da febbraio 2026 i depositi non conformi ad AES256 diventano bloccanti.
- PST documentazione ufficiale: PDP penale è canale autonomo del difensore; non va confuso con sistemi interni degli uffici.
- Giustizia Amministrativa, PAT: dal 1 febbraio 2026 Formweb è canale prioritario; PEC è residuale e solo per casi tecnici previsti. Alcune istanze particolari restano temporaneamente a modulo PEC secondo avvisi ufficiali.
- Specifiche/istruzioni PAT: atti nativi digitali, PDF, firma PAdES per ricorso/modulo quando richiesto.

## Evidenza reale allegata dall’utente

File letti da `C:\Users\antmm\Downloads` il 2026-06-14:

- `COPIA NON CRITTOGRAFATA DEPOSITO TELEMATICO_ Ricorso [JQ280-L01] [RefID_001_c3pnY4kBVA].EML`
  - allegati letti: `DatiAtto.xml.p7m`, `Ricorso.PDF`, `Nota d'iscrizione a ruolo.PDF`, `Procura.PDF`, prove documentali, ricevute PEC di notifica, `IndiceDocumentiDepositati.PDF`.
- `COPIA NON CRITTOGRAFATA DEPOSITO TELEMATICO_ Ricorso (originale notificato).pdf RG_ 1754 - 2026 [JQ280-L01] [RefID_001_zVNsJkqBF9]`
  - allegati letti: `DatiAtto.xml.p7m`, ricorso notificato, relata, ricevute di consegna/accettazione notifica, attestazione conformità, decreto fissazione udienza, procura, `IndiceDocumentiDepositati.PDF`.
- Depositi successivi reali letti: `Documento richiesto - prova interesse ad agire`, `Note scritte in sostituzione dell’udienza`, `Pagamento CU`, `Richiesta note scritte`, `Ricorso Contarino`.
  - nelle copie non crittografate è sempre presente `IndiceDocumentiDepositati.PDF`, anche quando l’invio contiene pochi documenti.
- Corrispondenti EML di invio reale letti:
  - contengono `Atto.enc` come allegato unico cifrato.

Conclusione operativa da questi file:

- La vista React deve mostrare tutti i documenti selezionati che entreranno nella busta.
- Il software deve generare sempre un indice documenti nel pacchetto preparato.
- Il pacchetto di controllo può contenere struttura verificabile, `DatiAtto.xml`/indice/documenti, ma non va presentato come deposito valido se manca `Atto.enc` ministeriale cifrato AES256.
- Un invio reale conforme PCT/SIGP richiede `Atto.enc`; le copie non crittografate servono come modello per controllare contenuto e indice.

## Caso reale PEC/EML JQ306-L01 fornito il 2026-06-16

L'utente ha fornito un esempio reale di deposito per chiarire la differenza tra copia non crittografata e PEC effettiva di deposito. I dati personali e gli indirizzi completi non vanno ricopiati nei report pubblici: la struttura tecnica invece diventa requisito operativo.

Schema osservato:

- la copia non crittografata ha oggetto `COPIA NON CRITTOGRAFATA DEPOSITO TELEMATICO: Ricorso [JQ306-L01] [RefID_...]`;
- la PEC effettiva ha oggetto `DEPOSITO TELEMATICO: Ricorso [JQ306-L01] [RefID_...]`;
- la PEC effettiva contiene come allegato operativo `Atto.enc` con MIME `application/octet-stream`;
- la copia non crittografata espone gli allegati leggibili o firmati indicati nel deposito, tra cui `DatiAtto.xml.p7m`, `Ricorso.PDF`, `Nota d'iscrizione a ruolo.PDF`, `Procura.PDF`, allegati documentali, ricevute/prove `.eml` quando incluse e `IndiceDocumentiDepositati.PDF`;
- il corpo del messaggio usa la formula al cancelliere e l'elenco puntuale dei file contenuti in `Atto.enc`;
- il riferimento `[JQ306-L01] [RefID_...]` va riportato nel corpo come riferimento da citare nella risposta;
- la data visibile della PEC è in ora italiana con offset `+0200`.

Regole software derivate dal caso reale:

- IUSENTRA deve produrre o mostrare chiaramente due oggetti distinti: `PEC effettiva di deposito` e `copia non crittografata di controllo`.
- La `PEC effettiva di deposito` non deve allegare singolarmente tutti i documenti: deve allegare `Atto.enc` quando l'adapter ministeriale è disponibile e conforme.
- La `copia non crittografata di controllo` deve servire a verificare contenuto, ordine, indice e allegati senza confonderla con l'invio valido.
- Il corpo del messaggio non deve essere duplicato: nell'esempio reale la visualizzazione mostra due volte la stessa formula/elenco; il software deve normalizzare la preview e generare un corpo unico, pulito e leggibile.
- La lista nel corpo deve coincidere con il contenuto della busta: atto principale, NIR quando presente, `DatiAtto.xml`/`DatiAtto.xml.p7m`, procura, allegati, prove PEC/EML e indice.
- I caratteri italiani devono restare UTF-8 validi: testi come `annualità` e virgolette italiane non devono diventare mojibake o caratteri sostitutivi.
- Gli allegati `.eml`, `.xml`, `.xml.p7m`, `.pdf.p7m` e `.txt` devono essere apribili in anteprima dal lettore globale, mantenendo il download dell'originale.
- Il validatore deve confrontare oggetto, destinatario ufficio, `Message-ID`, data, elenco allegati nel corpo, allegato `Atto.enc`, dimensione pacchetto e presenza dell'indice.
- Se viene generata solo la copia non crittografata o un pacchetto di controllo, la UI deve dire che non è ancora un deposito telematico valido e non deve registrare l'invio come completato.

Prova obbligatoria da eseguire sul server reale quando il flusso è pronto:

- generare il pacchetto del fascicolo reale senza invio PEC;
- verificare che la preview della PEC effettiva mostri `Atto.enc` come allegato unico;
- verificare che la copia non crittografata mostri gli allegati leggibili/firmati, `DatiAtto.xml.p7m` e `IndiceDocumentiDepositati.PDF`;
- verificare che il corpo non sia duplicato e che l'elenco dei file corrisponda esattamente alla busta;
- aprire visivamente almeno un `.eml`, un `.xml`/`.xml.p7m` e un `.pdf.p7m` dal lettore globale;
- fermarsi prima dell'invio PEC reale.

## Caso reale PEC/EML JQ332-L01 fornito il 2026-06-16

L'utente ha fornito tre ricevute reali collegate alla stessa busta di deposito. La struttura è stata verificata tramite `PecAuditRepository` sui file allegati alla conversazione, senza invio PEC e senza modificare dati di fascicolo.

Evidenza tecnica rilevata:

- la ricevuta `ESITO CONTROLLI AUTOMATICI DEPOSITO TELEMATICO` contiene `Codice esito: -1`, `IDBUSTA: 35508878`, `NOME FILE: DatiAtto.xml.p7m`;
- il testo ministeriale indica `Atto non conforme alle specifiche`, ma aggiunge che l'atto è in attesa di conferma della cancelleria, verrà comunque accettato e non è necessario effettuare nuovamente il deposito;
- le due ricevute successive `ACCETTAZIONE DEPOSITO TELEMATICO` contengono `Codice esito: 2`, lo stesso `IDBUSTA` e l'accettazione manuale avvenuta con successo;
- gli allegati di servizio osservati includono `EsitoAtto.xml`, `daticert.xml`, `postacert.eml` e `smime.p7s`.

Regola software derivata:

- `Codice esito -1` con `atto non conforme` non è sempre un rifiuto o un errore critico;
- se nello stesso testo è presente l'indicazione che la cancelleria deve confermare, che l'atto verrà comunque accettato o che non va ripetuto il deposito, IUSENTRA deve classificare l'esito come `warning`/presidio intermedio, non come `danger`;
- il software deve attendere o collegare la successiva ricevuta di accettazione/rifiuto deposito e non creare una nuova scadenza operativa duplicata;
- solo `errore fatale`, `rifiuto tecnico`, `rifiuto deposito` o accettazione negata esplicita devono produrre esito critico.

Verifica eseguita il 2026-06-16:

- primo EML JQ332: `event_type=pct_deposito`, `stage=esito_controlli_deposito`, `status=warning`, issue `pct_deposit_followup_expected`;
- secondo EML JQ332: `event_type=pct_deposito`, `stage=accettazione_deposito`, `status=ok`, nessuna issue critica di deposito;
- terzo EML JQ332: stesso esito positivo della ricevuta di accettazione.

## Matrice canali e comportamento software

### PCT SICID civile e PCT lavoro/SICID

- Esempi: civile ordinario, lavoro, previdenza, famiglia, decreto ingiuntivo, ricorso lavoro.
- Il codice oggetto PST ufficiale deve determinare pratica/canale. Se arriva come `222050 - Retribuzione`, il software deve normalizzare a `222050` per `DatiAtto.xml`.
- Il codice non deve essere una regola speciale per `222050`: qualunque codice ufficiale PST deve essere riconosciuto dal catalogo.
- Il software deve:
  - leggere l’intero fascicolo;
  - proporre atto principale e allegati;
  - separare comunicazioni/ricevute/cancelleria dal pacchetto, salvo siano prove necessarie;
  - includere prove di notifica quando il deposito è prova o ricorso originale notificato;
  - generare `DatiAtto.xml`;
  - generare `IndiceDocumentiDepositati.PDF`;
  - verificare codice ufficio, registro, RG/anno se necessari, codice oggetto ufficiale, firme, PDF/PDF-A, dimensione busta;
  - firmare in blocco i documenti richiesti quando Local Signer è pronto;
  - se manca adapter ministeriale reale, preparare controllo e indice ma sospendere l’invio diretto come deposito valido, spiegando che manca `Atto.enc` AES256.

### PCT SIECIC

- Esempi: esecuzioni mobiliari/immobiliari, pignoramenti, interventi, concorsuali, crisi d’impresa.
- Non deve essere confuso con SICID.
- Deve usare profilo `pct_siecic`, controlli propri e registro SIECIC.
- Generazione analoga a PCT: `DatiAtto.xml`, indice, atto, allegati, verifica dimensioni/firme, `Atto.enc` ministeriale per invio valido.

### SIGP / Giudice di Pace

- Canale autonomo, non PCT civile generico.
- Deve usare XSD/profilo SIGP, documenti e ricevute di portale.
- Il software prepara pacchetto, controlli, indice e guida upload/portale quando l’invio diretto non è disponibile.

### PDP penale

- Portale Deposito Penale del difensore.
- Non generare busta PCT civile.
- Il software deve preparare atti firmati, metadati, controlli formato/firma/PDF-A dove richiesti, e guidare upload sul portale PDP.
- Ricevute/stati PDP vanno importati nel fascicolo e non duplicati in agenda/scadenziario come scadenze operative improprie.

### PAT / SIGA amministrativo

- Dal 1 febbraio 2026 Formweb è prioritario.
- PEC solo residuale nei casi tecnici previsti; alcune istanze possono restare a modulo PEC secondo avvisi ufficiali.
- Il software deve preparare modulo/atto, allegati, firma PAdES quando richiesta, indice/checklist e guidare Formweb; non deve presentare l’invio PEC come canale ordinario se non ricorre il caso previsto.

### PTT / SIGIT tributario

- Canale tributario autonomo.
- Il software deve preparare atto e allegati, controllare limiti PTT/SIGIT, firma, ricevute e upload guidato.
- Non generare `DatiAtto.xml` PCT civile per PTT.

### UNEP

- Richieste notifiche/esecuzioni/492-bis e pagamenti collegati.
- Non confondere con relata L. 53/1994.
- Il software prepara richiesta, allegati, pagamenti se dovuti e ricevute portale/UNEP.

### PEC stragiudiziale e notifiche PEC L. 53/1994

- Canale distinto dal deposito PCT.
- La pagina principale per notifiche legali è `/notifiche-legali`.
- Dopo notifica, il software deve presidiare PEC e inserire RAC/RdAC/esiti nella sezione Comunicazioni del fascicolo, collegandoli al documento notificato.
- Se la notifica è già stata inviata e le prove sono già nel fascicolo/comunicazioni, non va riproposta come nuova attività.
- Le ricevute di deposito/accettazione/consegna non devono creare scadenze inutili in agenda/scadenziario: restano nel fascicolo e nei controlli del deposito/notifica.
- Le RAC/RdAC o ricevute equivalenti, quando sono prova della notifica da depositare, possono invece entrare nella busta come documenti prova. La regola è: niente duplicati operativi in Agenda/Scadenziario, ma conservazione e uso probatorio nel fascicolo/deposito quando necessario.

## Regola selezione documenti e busta

- La UI React deve mostrare `Proposta busta` con:
  - numero documenti selezionati;
  - checkbox per includere/escludere;
  - atto principale;
  - allegati;
  - prove notifica;
  - scelte manuali;
  - documenti da firmare;
  - elenco completo dei documenti che entreranno nel pacchetto.
- Il backend deve costruire la busta usando solo `atto_principale_id` e `allegati_ids` derivati dalla selezione visuale.
- Se arriva `documenti_selezionati_ids`, il backend deve verificare che corrisponda esattamente ad atto principale più allegati.
- Se la selezione vista a video e la busta divergono, bloccare la generazione con messaggio chiaro.
- Se un documento selezionato non è più nel fascicolo o non è reperibile su disco, bloccare la generazione spiegando quale file va ricaricato/corretto.

## Indice documenti

- Dai depositi reali allegati risulta presente `IndiceDocumentiDepositati.PDF` nelle copie non crittografate.
- Il software deve generare l’indice in tempo reale nel pacchetto preparato.
- L’indice deve riflettere l’ordine e i ruoli mostrati:
  - `DatiAtto.xml`;
  - atto principale;
  - allegati/prove/notifiche;
  - ricevute/attestazioni se incluse;
  - indice stesso come documento di chiusura del pacchetto.
- Il validatore non deve chiedere all’avvocato di allegare a mano l’indice se il software lo genera automaticamente.

## Stato codice al 2026-06-14

Già fatto in questa tranche:

- Normalizzazione centrale codice oggetto PST (`codice - descrizione` -> codice ufficiale).
- Resolver pratica/canale da codice PST, senza regola speciale solo per `222050`.
- Tutti i 1018 codici oggetto PST ufficiali importati dagli XSD ministeriali vengono accettati sia come codice puro sia come `codice - descrizione`, e arrivano al deposito come codice ministeriale pulito.
- Il codice scelto in apertura fascicolo non resta informativo: viene usato da Regia/Prepara deposito per profilo, canale, validazione e `DatiAtto.xml` quando il flusso lo richiede.
- Canale `PCT lavoro / SICID` mostrato per pratica lavoro/retribuzione.
- Matrice canali preservata: `pct_sicid`, `pct_siecic`, `sigp_gdp`, `pdp_penale`, `pat_siga`, `ptt_sigit`, `unep`, `pec_stragiudiziale`, `notifiche_pec`.
- La matrice canali non può essere ridotta a `PCT_CIVILE/PCT_LAVORO`: restano governati anche PCT SIECIC, SIGP/Giudice di Pace, PDP penale, PAT/SIGA, PTT/SIGIT, UNEP, PEC stragiudiziale e notifiche PEC.
- Tutti i profili depositabili devono risolvere una politica concreta (`direct_pec` o `portal_upload`), con canale ufficiale, tipo pacchetto e indice documenti generato dal software. Non deve passare un canale generico o ambiguo mascherato da deposito.
- Gli alias operativi dei canali sono blindati: `pct_sicid`, `pct_siecic`, `sigp`, `unep`, `pdp`, `pat`, `ptt`, `pec`, `notifica_pec`.
- Backend busta: controllo che selezione visuale e documenti effettivi coincidano.
- Generazione `IndiceDocumentiDepositati.PDF` dentro il pacchetto preparato.
- `DatiAtto.xml` richiama l'indice generato con hash SHA-256.
- Audit tecnico busta aggiornato: `indice_busta_generated = true` quando l'indice è presente.
- Runner server dry-run HTTP `scripts/server_deposito_dry_run_http.py`: effettua login sull'ambiente server, legge `/api/v1/ui/fascicoli/<id>?include=all`, costruisce la proposta documentale dalla stessa logica della pagina React e scarica il `.enc` dalla route reale `/fascicoli/<id>/deposito/genera-busta`, senza chiamare mai l'invio PEC.
- Test automatici passati in questa tranche:
  - `tests/test_codici_oggetto_pst_catalog.py`: 6 test, incluso controllo su tutti i 1018 codici ufficiali.
  - `tests/test_practice_engine_profiles.py`: 8 test, inclusi canali depositabili, alias e matrice non ridotta al solo PCT.
  - blocco mirato deposito/regia/portale/firma batch/asset React/dry-run server: 39 test.
  - `pnpm --filter @iusentra/studio typecheck`, `pnpm --filter @iusentra/studio test`, `pnpm --filter @iusentra/studio build`.
  - `check-route-gate`, `check-react-contracts`, OpenAPI provider e packaging.

Da fare/subito in questa tranche:

- Verificare UI reale su `127.0.0.1:8080`: proposta busta, elenco completo, selezione, scroll, card compatte, canale risolto, documenti mostrati senza tagli.
- Per richiesta esplicita dell'utente, la prova che chiude questa tranche deve essere server reale su `https://app.iusentra.it`: generare busta/pacchetto su ambiente server, non inviare a PEC reale, non registrare deposito valido se manca `Atto.enc` ministeriale AES256, e confrontare la struttura con i depositi reali allegati dall’utente.
- Non dichiarare firma multipla “funzionante” finché non avviene test reale con PIN e più `.p7m`.
- Aggiornare report, changelog, versione, Docker locale, push branch gemelli, checks GitHub, deploy Hetzner.

## Risposta operativa alla domanda sui codici

Alla data 2026-06-14, a livello codice e test automatici, il deposito riconosce tutti i 1018 codici oggetto PST ufficiali disponibili in apertura fascicolo.

Regola applicata:

- se il fascicolo contiene `222050 - Retribuzione`, il deposito usa `222050`;
- lo stesso vale per ogni altro codice ufficiale del catalogo, compresi codici numerici e alfanumerici come `B02001`;
- un codice non presente negli XSD ministeriali non viene accettato come codice deposito valido;
- il canale resta `da verificare` solo quando manca un codice ufficiale, il profilo non è determinabile o il canale richiede una scelta professionale effettiva.

Questa regola è protetta da test, ma non va dichiarata conclusa sul prodotto finché non viene vista nella pagina reale `Prepara deposito` dopo rebuild Docker su `127.0.0.1:8080`.

## Prova server dry-run della busta come deposito reale

La prova richiesta dall’utente va eseguita direttamente sull’ambiente server, dopo deploy della versione corrente, con invio PEC disattivato. Non deve essere una simulazione documentale finta: il software deve usare lo stesso flusso di generazione previsto per il deposito reale, fermandosi solo prima della spedizione PEC.

Obiettivo:

- generare la busta come se il deposito fosse reale, partendo da un fascicolo reale o controllato;
- fermare il flusso prima dell’invio PEC;
- verificare che il contenuto sia coerente con i depositi reali allegati dall’utente;
- produrre un report salvato in repository/artifact con differenze e blocchi.

Regole della prova:

- mai inviare PEC reale durante questa simulazione;
- usare destinatario di prova non consegnabile o modalità server `dry-run`, senza percorso demo che alteri la busta;
- non dichiarare deposito valido se manca `Atto.enc` ministeriale cifrato AES256;
- se il software produce solo pacchetto di controllo e non la busta ministeriale reale, il report deve dirlo chiaramente e bloccare ogni equivalenza con l’invio reale;
- confrontare almeno:
  - presenza e posizione di `DatiAtto.xml` o `DatiAtto.xml.p7m` quando firmato;
  - presenza di `IndiceDocumentiDepositati.PDF`;
  - ordine logico atto principale, procura, NIR, allegati, prove notifica, ricevute;
  - oggetto deposito e RG;
  - hash documenti;
  - dimensione pacchetto;
  - distinzione tra copia non crittografata e invio reale con `Atto.enc`;
  - assenza di documenti non selezionati;
  - messaggi operativi comprensibili per l’avvocato.

La prova è considerata riuscita solo se il report dice esattamente cosa coincide con i depositi reali allegati e cosa resta diverso perché manca adapter ministeriale o firma reale.

Esito preparatorio locale del 2026-06-14:

- creato `scripts/audit_deposito_server_dry_run.py`;
- creato `scripts/server_deposito_dry_run_http.py`;
- aggiunto test `tests/test_deposito_server_dry_run_audit.py`;
- audit locale su pacchetto generato e campioni reali allegati dall’utente:
  - pacchetto di controllo coerente con copia non crittografata: sì;
  - `IndiceDocumentiDepositati.PDF`: presente;
  - `DatiAtto.xml`: presente nel pacchetto generato;
  - campione reale copia non crittografata: contiene `DatiAtto.xml.p7m` e indice;
  - campione reale invio: contiene `Atto.enc`;
  - equivalenza con invio ministeriale reale: no, perché manca `Atto.enc` AES256 generato dall’adapter ministeriale e `DatiAtto.xml` firmato.

Quindi la prossima prova server deve usare lo stesso flusso reale di generazione busta via HTTP, fermarsi prima dell’invio PEC e produrre lo stesso audit. Se il risultato resta `ATTO_ENC_AES256_MISSING`, il software deve spiegare all’avvocato che il pacchetto è pronto per controllo ma non è ancora busta ministeriale valida per invio.

Comando operativo previsto dopo deploy:

```bash
python scripts/server_deposito_dry_run_http.py \
  --base-url https://app.iusentra.it \
  --username antmm26051975 \
  --password "$IUSENTRA_DRY_RUN_PASSWORD" \
  --fascicolo-id EFBE9117 \
  --output-dir /opt/iusentra/deposito-dry-run \
  --report-json /opt/iusentra/deposito-dry-run/server-dry-run.json
```

Subito dopo va eseguito l'audit sul file `.enc` prodotto dal server. La password non va scritta in report o file committati.

## Verifica visiva server E5AE4668 del 2026-06-14

Ambiente verificato davanti all'utente: `https://app.iusentra.it/fascicoli/E5AE4668/deposito/prepara`, browser visibile, login eseguito dall'utente, scroll completo della pagina dall'alto al fondo. Non è stato effettuato alcun invio PEC reale.

Esito onesto della prova:

- La pagina si apre sul server e legge il fascicolo reale.
- Il canale viene risolto come `PCT lavoro / SICID` quando è presente il codice ministeriale `222050`.
- Il fascicolo mostra cliente e ufficio, ma il campo RG risulta ancora `n.d.` in una vista in cui il deposito dovrebbe avere dati completi e verificabili.
- Il software genera/mostra `DatiAtto.xml` e `IndiceDocumentiDepositati.PDF`, ma il flusso non può essere dichiarato deposito pronto.
- Il pulsante `Prepara controllo busta` porta lo stato in preparazione e non invia PEC, ma non dimostra ancora la generazione ministeriale completa e conforme.

Problemi da correggere prima di dichiarare il deposito pronto:

- La firma digitale funziona nel prodotto, ma il deposito non deve limitarsi a dire che ci sono documenti da firmare: deve usare il flusso di firma multipla già previsto, firmare in blocco i documenti obbligatori prima del deposito, salvare ogni esito nel fascicolo e riabilitare il passo successivo.
- Il pannello `Verifica deposito` non va bene nella forma attuale: mostra blocchi lunghi e tecnici invece di una verifica professionale per avvocato con `pronto`, `da completare`, `bloccante`, `avviso` e azione immediata per risolvere.
- L'avvocato deve poter selezionare, escludere, allegare o correggere i documenti della proposta. Non basta mostrare solo ciò che il software ha scelto.
- Se il software non è sicuro della classificazione, deve evidenziare solo quel documento e chiedere conferma, non bloccare o nascondere la possibilità di correzione.
- Il pulsante di generazione controllo/indice risulta visivamente primario ma non azionabile; deve spiegare chiaramente perché è disabilitato e quale azione risolve il blocco.
- Non devono comparire stati tecnici visibili come `NON_INVIATO`, `IN_PREPARAZIONE` o `BLOCCATO_DA_ERRORI`: servono testi giuridici professionali.
- Le card compatte devono restare compatte ma leggibili; non devono tagliare parole come `Tutto fascicolo`, `Da firmare` o `Catalogo portale`.
- I documenti che la normativa richiede firmati devono entrare automaticamente nella firma multipla, non essere lasciati come promemoria finale.
- I blocchi obbligatori devono fermare l'invio solo quando il software non può risolverli da solo; i mancanti non obbligatori devono restare avvisi.

Stato della tranche dopo questa verifica: aperta. Il deposito non va dichiarato completo né conforme finché la prova reale non mostra selezione documenti correggibile, firma multipla effettiva su più documenti, indice generato dalla stessa selezione, busta coerente con i campioni reali e messaggi professionali senza testo tecnico.

## Aggiornamento server E5AE4668 del 2026-06-14 ore 19:58

Intervento eseguito direttamente sul server richiesto dall'utente, senza passaggio GitHub/deploy formale:

- aggiornato `frontend/src/components/FascicoliPage.tsx`;
- aggiornato `frontend/src/components/FascicoliPage.css`;
- ricompilato bundle React con `pnpm --filter @iusentra/studio build:vite`;
- copiato il bundle compilato in `/opt/iusentra/repo/web/static/react`;
- copiato il bundle nel container `iusentra-app-1:/app/web/static/react`;
- verificato container `iusentra-app-1` ancora `healthy`.

Regola applicata nella pagina `Prepara deposito`:

- la fase di preparazione non blocca più il lavoro solo perché i documenti devono essere firmati;
- i documenti non firmati entrano nella firma del comando finale `Firma e genera busta`;
- il comando finale richiama la firma multipla registrata dal pannello Local Signer prima della generazione busta;
- se il PIN non è inserito, il software deve chiederlo solo al momento della firma e non deve salvarlo; se invece Local Signer, versione, riavvio o token rilevabile non sono pronti, il software React deve tentare avvio, aggiornamento e riallineamento automatico prima di bloccare la firma;
- i soli blocchi visivi del comando finale restano atto principale mancante e scelte obbligatorie documentali non confermate.

Correzioni UI completate e viste sul server:

- badge e card non mostrano più `NON_INVIATO`, `IN_PREPARAZIONE` o `BLOCCATO_DA_ERRORI`;
- chip `n.d.` sostituito dal riferimento utile `2026/330` quando il campo RG normalizzato è mancante;
- canale visualizzato come `PCT lavoro / SICID`;
- nota errata `PCT civile SICID` sostituita con `Profilo lavoro applicato: usare il canale PCT lavoro/SICID`;
- messaggi grezzi `Impossibile validare...` trasformati in azioni operative:
  - `Collega il documento richiesto alla busta`;
  - `Ricarica il documento oppure correggi il collegamento`;
  - `Ricalcola l'impronta del documento prima della generazione`;
- aggiunta sezione `Documenti da inviare` con selezione correggibile;
- aggiunti comandi `Ripristina proposta`, `Seleziona tutti i documenti`, `Apri documenti fascicolo`;
- aggiunto pannello `Allega documentazione al fascicolo` dentro la proposta busta;
- verificato click reale sul pannello allegati: il form mostra file, classificazione, data documento, etichette, note, `Già firmato` e `Carica documenti`;
- card compatte riviste: `Tutto fascicolo`, `Firma software`, `Catalogo portale` e `Firme` non tagliano il testo;
- artefatti `DatiAtto.xml` e `IndiceDocumentiDepositati.PDF` separati dalla descrizione, senza testo attaccato;
- testo `firma multipla immediata` sostituito con `comando finale`;
- messaggio finale corretto da `1 slot obbligatori` a `1 scelta obbligatoria richiede la conferma dell'avvocato`;
- scroll visivo eseguito dall'alto al fondo della pagina server.

Screenshot locali della verifica visiva reale:

- `%TEMP%/iusentra-e5ae4668-deposito-visual-20260614/server_top_final.png`;
- `%TEMP%/iusentra-e5ae4668-deposito-visual-20260614/server_scroll_1_final2.png`;
- `%TEMP%/iusentra-e5ae4668-deposito-visual-20260614/server_upload_form.png`;
- `%TEMP%/iusentra-e5ae4668-deposito-visual-20260614/server_final_block_after_grammar.png`;
- `%TEMP%/iusentra-e5ae4668-deposito-visual-20260614/server_bottom_final.png`.

Stato completato in questa fase:

- preparazione deposito resa lavorabile senza falso blocco sulle firme;
- selezione documenti visibile e correggibile;
- allegato documento visibile e apribile;
- firma multipla agganciata al comando finale sul lato React;
- messaggi principali resi professionali e leggibili;
- scroll completo pagina server eseguito.

Stato ancora aperto e non dichiarabile verde:

- Local Signer nella sessione server/Chrome verificata risulta `non rilevato`;
- non è stato inserito PIN reale;
- non è stata eseguita firma multipla reale di più documenti;
- non sono stati salvati `.p7m` reali nel fascicolo in questa prova;
- non è stato generato un `Atto.enc` ministeriale valido AES256;
- non è stato eseguito invio PEC reale, per scelta corretta della prova.

Prossima prova obbligatoria:

- con Local Signer rilevato e token pronto, l'utente inserisce il PIN;
- premere `Firma e genera busta`;
- verificare che il software firmi in lotto i documenti selezionati, salvi ogni firmato nel fascicolo, aggiorni esiti/impronte, generi indice e pacchetto coerente con la selezione;
- se manca ancora l'adapter ministeriale `Atto.msg` -> `Atto.enc` AES256, il software deve continuare a spiegare che il pacchetto è di controllo/preparazione e non deposito ministeriale valido.

## Aggiornamento navigazione a fasi del 2026-06-14 ore 20:10

Richiesta utente: rendere `Prepara deposito` intuitivo, veloce e professionale, migliorandolo in fasi navigabili.

Intervento eseguito direttamente sul server, senza commit/push GitHub su richiesta operativa dell'utente:

- aggiornata la pagina React `frontend/src/components/FascicoliPage.tsx`;
- aggiornato lo stile `frontend/src/components/FascicoliPage.css`;
- ricompilato il bundle React con `pnpm --filter @iusentra/studio build:vite`;
- copiati sorgenti e bundle su `iusentra-hetzner`;
- copiati gli asset nel container `iusentra-app-1`;
- verificato container `iusentra-app-1` ancora `healthy`.

Nuova struttura visibile:

1. `Verifica pratica`: canale, profilo pratica, regola operativa e controlli obbligatori.
2. `Documenti da inviare`: selezione correggibile dei documenti, allegati e proposta busta.
3. `Firma documenti`: fase separata per firma multipla, PIN, Local Signer e documenti da firmare.
4. `Busta e indice`: riepilogo atto principale, allegati, `DatiAtto.xml`, `IndiceDocumentiDepositati.PDF`, documenti inclusi e comando finale.
5. `Inventario fascicolo`: lettura dell'intero fascicolo usata per classificazione e controllo.

Correzioni di navigazione:

- aggiunta barra `Percorso deposito` sopra i pannelli;
- ogni fase ha numero, titolo, stato e descrizione breve;
- le descrizioni sono state accorciate dopo prova visiva perché due testi venivano troncati;
- i link a `#firma-busta` e `#generazione-busta` ora aprono automaticamente il pannello e scorrono alla sezione anche quando la pagina React carica i dati dopo l'apertura;
- aggiunto margine di scorrimento per evitare che la sezione aperta finisca nascosta sotto la topbar;
- firma e busta/indice sono pannelli separati, non più nascosti dentro la stessa area documenti.

Verifica visiva reale su server:

- URL: `https://app.iusentra.it/fascicoli/E5AE4668/deposito/prepara`;
- browser: Google Chrome visibile sulla macchina dell'utente;
- screenshot iniziale: `%TEMP%/iusentra-e5ae4668-deposito-fasi-20260614/fase_top_final.png`;
- test link diretto firma: `%TEMP%/iusentra-e5ae4668-deposito-fasi-20260614/fase_firma_final.png`;
- test link diretto busta: `%TEMP%/iusentra-e5ae4668-deposito-fasi-20260614/fase_busta_final.png`.

Esito visivo:

- barra fasi visibile e compatta;
- testi delle fasi leggibili senza tagli evidenti;
- fase `Firma documenti` apre direttamente Local Signer e spiega che il PIN serve al comando finale;
- fase `Busta e indice` mostra atto principale, allegati, firme previste, `DatiAtto.xml`, `IndiceDocumentiDepositati.PDF`, documenti inclusi e motivo del blocco finale;
- il blocco finale resta professionale: `1 scelta obbligatoria richiede la conferma dell'avvocato`;
- il comportamento resta coerente con la regola: i documenti da firmare non bloccano la preparazione, vengono firmati nel comando finale.

Stato ancora aperto:

- Local Signer nella prova risulta ancora non rilevato;
- non è stato inserito PIN reale;
- non è stata eseguita firma multipla reale;
- non è stato prodotto `Atto.enc` AES256 reale;
- non è stato effettuato invio PEC reale.

## Verifica reale obbligatoria

Prima di dichiarare chiuso:

- Docker locale ricostruito no-cache e healthy su `http://127.0.0.1:8080`.
- Browser reale visibile sulla macchina dell’utente.
- Aprire almeno:
  - `/fascicoli/95557727/deposito/prepara` o fascicolo equivalente con codice `222050 - Retribuzione`;
  - `/fascicoli/2DE106E6/deposito/prepara` per firma multipla/pannello documenti;
  - un fascicolo con documenti da portale/import QuickOrganizer.
- Controllare visivamente:
  - canale non `da verificare` quando codice ufficiale è presente;
  - tutti i documenti selezionati visibili;
  - indice indicato e generato;
  - nessun testo tecnico incomprensibile;
  - nessuna card enorme o testo tagliato;
  - scroll fino in fondo;
  - mobile/tablet/desktop quando UI cambia.

## Fix Local Signer del 2026-06-14 ore 20:27

Richiesta utente: ripristinare il Local Signer, che prima funzionava e nella pagina `Prepara deposito` risultava `Local Signer non rilevato`.

Diagnosi reale:

- il servizio locale rispondeva su `http://127.0.0.1:27272`, ma il processo attivo era disallineato e mostrava `riavvio_signer_consigliato`;
- dopo riavvio controllato dei soli processi `IUSENTRA\LocalSigner\local_signer.py`, il ping locale ha rilevato il token:
  - versione Local Signer `1.6.72`;
  - token `CNS - Bit4id - JS2048 (LB) - slot 0`;
  - seriale token `7430010029148677`;
- nonostante il token pronto, Chrome sulla pagina server continuava a mostrare `Local Signer non rilevato`;
- causa effettiva trovata negli header HTTPS: `Permissions-Policy` negava `local-network-access`, `local-network` e `loopback-network`, impedendo alla pagina di usare correttamente `127.0.0.1:27272`.

Intervento eseguito:

- aggiornato `core/security/headers.py`: le pagine operative consentono ora `local-network-access=(self)`, `local-network=(self)` e `loopback-network=(self)`;
- aggiornato `deploy/hetzner/Caddyfile` con la stessa policy per il reverse proxy pubblico;
- aggiornato `tests/test_security_headers.py` per impedire regressioni verso `local-network-access=()`;
- test mirato eseguito: `python -m pytest tests/test_security_headers.py -q` -> `5 passed`;
- copiati i file corretti su `iusentra-hetzner`;
- ricostruita l'immagine `app` con `docker compose ... build --no-cache app`;
- ricreati i container `app` e `caddy` sul server reale;
- verificato `https://app.iusentra.it/api/pronto` con risposta `200 OK`, versione `2.253.22`;
- verificati header pubblici: entrambe le `Permissions-Policy` ora consentono loopback/local network a `self`.

Verifica visiva reale su macchina dell'utente:

- URL: `https://app.iusentra.it/fascicoli/E5AE4668/deposito/prepara?codex_local_signer=2#firma-busta`;
- browser: Google Chrome reale visibile;
- prima del fix: pannello `Firma documenti` mostrava `Local Signer non rilevato`;
- dopo il fix: pannello verde `Local Signer pronto`, con `CNS - Bit4id - JS2048 (LB) - slot 0`, versione `1.6.72`;
- click reale su `Riverifica`: il pannello resta `Local Signer pronto`;
- screenshot di prova:
  - `%TEMP%/iusentra-local-signer-fix-20260614/desktop-after-signer-restart.png`;
  - `%TEMP%/iusentra-local-signer-fix-20260614/desktop-after-policy-fix.png`;
  - `%TEMP%/iusentra-local-signer-fix-20260614/desktop-after-riverifica-click.png`.

Stato chiuso per questa sotto-fase:

- rilevazione Local Signer da browser reale su server ripristinata;
- token PKCS#11 visibile nella UI del deposito;
- bottone `Firma 2 documenti` visibile e abilitato quando il token è pronto;
- guardrail header aggiornato con test dedicato.

Stato ancora aperto e da non dichiarare verde:

- non è stato inserito il PIN reale;
- non è stata eseguita firma multipla reale;
- non sono stati salvati `.p7m` nel fascicolo durante questa verifica;
- non è stato verificato il passaggio successivo `firma -> salvataggio documenti firmati -> generazione busta`;
- resta obbligatoria prova con PIN inserito dall'avvocato prima di dichiarare funzionante la firma multipla del deposito.

## Aggiornamento 2026-06-16 - Deposito guidato semplice e slot documentale unico

Regola di esperienza utente:

- il deposito deve essere semplice, veloce, intuitivo e funzionale;
- la pagina `Prepara deposito` deve mostrare un pannello operativo alla volta, evitando schermate dense dove l'avvocato deve interpretare troppe sezioni insieme;
- la navigazione deve seguire le fasi `Verifica pratica`, `Documenti da inviare`, `Firma documenti`, `Busta e indice`, `Inventario fascicolo`;
- i pulsanti devono indicare azioni reali e comprensibili, senza linguaggio tecnico superfluo.

Slot documentale:

- tutti i documenti del fascicolo utili al deposito devono essere visibili nella sezione `Documenti da inviare`;
- l'avvocato può selezionare un documento, selezionare tutto con `Invia tutto`, oppure escludere un documento come `Fuori busta`;
- ogni documento selezionato deve avere una classificazione chiara e non ambigua: `Atto principale`, `Procura alle liti`, `Allegato`, `Prova notifica`, `Fuori busta`;
- la voce ibrida `Allegato / prova` non deve comparire nel menu: i documenti probatori ordinari del fascicolo sono `Allegato`, mentre `Prova notifica` è riservata a atto notificato, relata, PEC inviata, RAC/RdAC e ricevute/evidenze richieste dal deposito prova;
- la direttiva normativa e tecnica sui ruoli documentali è salvata in `docs/specs/ministero/PCT_RUOLI_DOCUMENTALI_DEPOSITO_2026-06-16.md` e va riletta prima di modificare il menu o la classificazione deposito;
- deve esistere un solo atto principale selezionato; se la proposta automatica ne trova più di uno, il sistema mantiene il primo coerente e riclassifica gli altri come allegati/prove;
- la classificazione visibile deve essere salvata prima di firma e busta tramite endpoint reale, non solo tenuta nello stato React.

Firma:

- lo stato `Firmato` è informativo e deriva dal documento reale;
- la UI non deve permettere di segnare manualmente come firmato un documento che non ha esito di firma reale;
- la firma multipla può essere dichiarata funzionante solo dopo prova reale in React con PIN digitato al momento della firma, token rilevato dal Local Signer, firma di più documenti nella stessa operazione, salvataggio dei `.p7m` nel fascicolo e riabilitazione del passo successivo senza errori.

Busta e invio:

- il comando finale deve salvare la classificazione, avviare la firma dei documenti realmente da firmare e poi generare il pacchetto;
- la prova richiesta per il fascicolo `E5AE4668` deve arrivare alla generazione o ispezione del pacchetto/busta senza invio PEC reale;
- se manca l'adapter ministeriale reale che produce `Atto.enc` AES256 conforme, il pacchetto deve essere chiamato pacchetto di controllo e non deposito valido;
- il sistema non deve registrare un invio come deposito valido se manca `Atto.enc` ministeriale o un requisito obbligatorio non producibile.

Lettore documenti firmati:

- i file `.pdf.p7m` devono essere visualizzabili in tutto il software, non solo nel deposito;
- l'anteprima deve estrarre il PDF interno quando il contenitore CAdES lo espone;
- il download deve continuare a servire il `.p7m` originale, senza sostituirlo con il PDF estratto;
- la stessa logica deve valere per documenti fascicolo, PEC, email ordinaria e ogni pannello che apre allegati/documenti firmati.

Regola UI corretta dopo prova server:

- lo stepper deve mostrare un solo pannello operativo alla volta;
- `Verifica operativa` e `Prepara controllo busta` devono dare un riscontro visibile immediato e portare alla fase coerente;
- gli slot documentali devono stare in un solo pannello largo, senza scroll interno, con testo, select e pulsanti leggibili;
- lo stesso pannello resta laterale sui desktop/laptop larghi e si impila come unico pannello sugli schermi più stretti;
- non deve esistere una seconda copia in fondo alla fase documentale.

Verifiche obbligatorie per questa tranche:

- browser reale visibile su `https://app.iusentra.it/fascicoli/E5AE4668/deposito/prepara`, con scroll completo dei pannelli;
- responsive desktop, tablet e mobile sul server reale;
- salvataggio classificazione documenti da UI sul server reale;
- aggiornamento macchina locale Docker e verifica `http://127.0.0.1:8080/api/pronto`;
- generazione pacchetto dry-run o ispezione reale equivalente;
- controllo contenuti: documenti selezionati, atto principale, procura, allegati, `DatiAtto.xml`, `IndiceDocumentiDepositati.PDF`, oggetto e testo email se prodotti;
- prova Local Signer React con controllo automatico di versione, avvio, aggiornamento e stop delle istanze vecchie; la firma multipla reale richiede poi il PIN digitato al momento della firma e il token fisico rilevato.

## Aggiornamento 2.253.36 - prova server firma multipla e pacchetto busta

Data intervento: 2026-06-16.

Prova reale eseguita sul server `https://app.iusentra.it`, fascicolo `E5AE4668` (`2026/330 - Marchetti Lucia`):

- accesso autenticato allo studio `studio-legale-giuseppe-montagnese` e lettura payload React `/api/v1/ui/fascicoli/E5AE4668?include=all`;
- verificato che l'atto principale `Autocertificazione ricorso.PDF.p7m` e la procura `Procura.PDF.p7m` risultano già firmati, con estensione `.p7m` visibile nel payload;
- scaricati dal server due documenti reali non firmati: `Autocertificazione situazione reddituale.PDF` e `Contratto 24-25.pdf`;
- firmati insieme con una sola chiamata Local Signer `/firma-batch`, token CNS Bit4id reale e PIN inserito nel processo di prova, senza salvare il PIN;
- ricaricati nel fascicolo come `Autocertificazione situazione reddituale.PDF.p7m` e `Contratto 24-25.pdf.p7m`;
- riletto il payload React dopo upload: entrambi i documenti risultano `signed=true` e mantengono il nome originale con sola aggiunta dell'estensione `.p7m`;
- salvata classificazione deposito con 4 documenti in busta: atto principale, procura, autocertificazione reddituale e contratto;
- chiamata la validazione deposito con form reale: 5 avvisi, 0 blocchi;
- generato il pacchetto con `/fascicoli/E5AE4668/deposito/genera-busta` senza usare `/deposito/invia-pec`;
- verificato il file `Busta_2026-330_RICORSO.enc` scaricato dal server: è un pacchetto zip di controllo con 6 voci, cioè `DatiAtto.xml`, `IndiceDocumentiDepositati.PDF` e i quattro documenti `.p7m`.

Avvisi rilevati nella validazione:

- atto introduttivo con RG già presente;
- oggetto dell'atto troppo sintetico;
- ricevuta contributo unificato non rilevata;
- prova di notifica non rilevata;
- conformità PDF/A non verificabile sul wrapper `.p7m`.

Stato operativo:

- la firma multipla Local Signer ha funzionato su documenti reali e ha salvato i `.p7m` nel fascicolo;
- il pacchetto busta di controllo è stato generato e contiene `DatiAtto.xml`, indice e documenti firmati;
- non è stato eseguito invio PEC;
- resta aperta la verifica visiva materiale nella scheda autenticata del browser dell'utente, con scroll completo di `#proposta-busta` e `#firma-busta`, controllo layout desktop/tablet/mobile e conferma che il pannello singolo documento mostra di nuovo le impostazioni di firma visibile al posto del blocco di riallineamento inutile.

## Aggiornamento 2.253.34 - scelta `Da firmare` e layout lista deposito

Data intervento: 2026-06-16.

Problema corretto:

- nella lista `Documenti da inviare` la voce `Da firmare` risultava percepita come controllo, ma non era utilizzabile dall'avvocato;
- la firma multipla doveva leggere una scelta reale per ogni documento, non soltanto dedurre tutto dal nome o dallo stato iniziale;
- sui formati laptop la riga documento e il menu ruolo potevano uscire dal pannello o comprimere testo, icone e badge.

Cambio operativo:

- `Da firmare` è diventato una spunta cliccabile per i documenti non ancora firmati che richiedono firma;
- se l'avvocato toglie la spunta, il documento resta selezionabile in busta ma non entra nel lotto firma;
- se l'avvocato rimette la spunta, il documento viene incluso e marcato per la firma nel comando finale;
- `Firmato` resta solo informativo e continua a derivare dal documento reale, da `.p7m` o da esito Local Signer salvato;
- il payload React verso `/api/v1/ui/fascicoli/<id>/deposito/classifica-documenti` porta anche `requires_signature`, così il backend può restituire e presidiare la scelta;
- se il comando finale trova documenti da firmare ma il pannello firma o il PIN non sono pronti, apre la fase `Firma documenti` e mostra il blocco nel punto corretto;
- la riga deposito è stata ricompattata in quattro colonne governate: invio, documento, azioni icona, ruolo/firma;
- le azioni `Visualizza` e `Scarica` restano icone con tooltip/label accessibile, senza testo visibile che rompa la griglia;
- il menu ruolo è ancorato alla riga con altezza controllata e z-index dedicato, evitando il pannello fuori asse visto nella prova reale.

Guardrail tecnici eseguiti prima del commit:

- `pnpm --filter @iusentra/studio typecheck`;
- `pnpm --filter @iusentra/studio build:vite`;
- `python -m pytest tests/test_regia_api_payloads.py::test_api_deposito_classifica_documenti_collega_slot_e_metadati tests/test_regia_ui_react.py -q`.

Stato prova reale:

- non ancora chiuso: serve deploy produzione sullo SHA corrente, poi prova visiva server su `https://app.iusentra.it/fascicoli/E5AE4668/deposito/prepara` con scroll completo, click reale sulla spunta `Da firmare`, apertura menu ruolo, verifica layout laptop/tablet/mobile, dry-run senza invio PEC e prova firma multipla con PIN/token reale.

## Aggiornamento 2.253.33 - scadenza certificato firma in Impostazioni

Data intervento: 2026-06-16.

Cambio operativo:

- la sezione React `Impostazioni > Firma Digitale` legge dal Local Signer il certificato Windows selezionato, inclusi codice fiscale, intestatario, emittente e scadenza;
- la scadenza viene salvata nella configurazione firma dello studio con data ISO per i calcoli e data italiana `gg/mm/aaaa` per la visualizzazione;
- il salvataggio usa l'endpoint dedicato `/api/v1/ui/impostazioni/firma/certificato`, senza modificare P12, PEM, driver PKCS#11 o altre impostazioni firma;
- al login, se mancano 20 giorni o meno alla scadenza salvata, l'avvocato vede un avviso con i giorni mancanti; se il certificato risulta scaduto, il messaggio invita al rinnovo prima di firmare o depositare atti.

Test automatici eseguiti:

- `python -m pytest tests/test_react_shell.py::test_impostazioni_firma_salva_scadenza_certificato_local_signer tests/test_react_shell.py::test_avviso_login_certificato_firma_a_venti_giorni tests/test_react_shell.py::test_impostazioni_react_frontend_copre_local_signer_occhio_e_ai_locale tests/test_local_signer.py::test_diagnosi_windows_mostra_certificato_avvocato_selezionato tests/test_local_signer.py::test_local_signer_ha_guardia_istanza_unica_e_diagnosi_certificato -q`

Stato prova reale:

- da verificare su macchina reale dopo rebuild Docker `127.0.0.1:8080`: apertura `Impostazioni > Firma Digitale`, click reale su `Verifica dispositivo collegato`, salvataggio scadenza letta dal Local Signer, ricarica UI con data italiana e avviso login se la soglia e' applicabile.

## Aggiornamento 2.253.32 - Local Signer 1.6.74, certificato e cataloghi

Intervento richiesto dopo il dubbio dell'utente su certificato avvocato e catalogo PST:

- `/ping` rilevava correttamente il certificato Windows selezionato dell'avvocato, ma `/diagnosi` mostrava solo i primi certificati dello store e poteva non visualizzare quello operativo;
- `/diagnosi` ora espone anche `certificato_windows_selezionato` e una riga leggibile `Certificato avvocato selezionato` con codice fiscale e scadenza;
- il processo Local Signer ora acquisisce una guardia di istanza unica per porta prima di aprire il server, cosi' una seconda istanza richiamata da avvio automatico o protocollo locale si chiude invece di restare viva in parallelo;
- il catalogo copiato dal pacchetto Local Signer è stato ricontrollato: `uffici_ministero.json` contiene 534 uffici mappati e 13 non mappati; `uffici_pst_pubblici.json` contiene 1.781 uffici civili e 1.416 penali, totale 3.197 voci PST pubbliche;
- il messaggio `Catalogo pubblico uffici PST civile/penale copiato` riguarda il catalogo PST pubblico civile/penale usato dal Local Signer e non esaurisce l'intero perimetro dei servizi telematici, dove PAT, PTT, PDP e altri flussi restano registri o adapter separati.

## Aggiornamento 2.253.30 - menu ruolo, Editor professionale e lettore globale

Intervento tecnico applicato prima della chiusura richiesta:

- sostituita la select nativa dei ruoli deposito con un selettore React ancorato alla riga, per evitare popup fuori asse nella lista `Documenti da inviare`;
- mantenuti come ruoli visibili solo `Atto principale`, `Procura alle liti`, `Allegato`, `Prova notifica`, `Fuori busta`;
- il valore storico `allegato_prova` resta accettato solo in compatibilità e viene normalizzato a `Allegato`;
- aggiunta la route full React `/editor-professionale`, distinta da `/redazione-atti`, con voce autonoma sotto `Studio`;
- esteso il lettore globale di allegati/documenti a `.xml`, `.xml.p7m`, `.eml`, `.eml.p7m`, `.txt`, `.txt.p7m`, oltre a `.pdf.p7m`;
- il download resta sempre dell'originale, soprattutto per i contenitori `.p7m`;
- rimossi rami di preview fascicolo duplicati per `.eml` e `.txt`, ora gestiti dal lettore unico, mantenendo `fascicoli_document_routes.py` sotto il limite di governance;
- introdotto code splitting Vite per separare vendor e icone e rimuovere il warning del chunk principale sopra 500 kB.

Guardrail tecnici eseguiti e registrati in `pytest-confirmed-ok.md`:

- TypeScript, contratti React, route gate, OpenAPI, frontend test e build Vite;
- test mirati deposito/regia, Editor professionale, fascicoli, PEC, email ordinaria, UTF-8 e asset retention;
- audit dati/tenant/topbar senza repair;
- quality gate `code` non usato come verde finale perché sullo stage completo blocca il bump versione obbligatorio di `Dockerfile`, `pct/__init__.py` e `railway.toml`;
- governance repo e sintassi Python.

Stato ancora aperto prima di dichiarare chiuso il deposito:

- commit, push branch gemelli e check GitHub/CodeQL dello SHA corrente;
- deploy Hetzner e verifica `/api/pronto`;
- riallineamento Docker locale su `127.0.0.1:8080`;
- prova visiva reale server desktop/tablet/mobile con click e scroll completo;
- dry-run server del fascicolo `E5AE4668` senza invio PEC reale;
- firma multipla reale da chiudere con PIN digitato al momento della firma e token fisico rilevato; installazione, aggiornamento e riallineamento Local Signer non sono un prerequisito esterno, ma responsabilità del software React.
## Aggiornamento 2.253.63 - Local Signer PST e anteprima fascicolo lavoro

Data intervento: 2026-06-18.

Per il fascicolo lavoro Tribunale di Torino RG 3950/2026 e per i flussi PST collegati:

- Local Signer aggiornato a `1.6.78`, con auto-selezione del certificato personale ArubaPEC Authentication e blocco dei certificati Adobe/intermedi/scaduti in modalita' automatica;
- launcher Windows corretto per non chiudere il processo padre del servizio in ascolto su `127.0.0.1:27272`;
- smoke reale Local Signer eseguito su macchina utente: `/ping?auto=1`, `/certificati`, `/diagnosi`, `/ai/status`, `/pst/status` e dipendenze `cryptography`, `asn1crypto`, `zeep`, `pdfplumber`, `mammoth`, `pypdf`, `reportlab`, `pkcs11`;
- React PST corretto per aprire l'anteprima dai dati fascicolo gia' restituiti dalla ricerca, senza bloccare la vista sul timeout esterno `ext.processotelematico.giustizia.it`;
- il timeout del PST esterno resta un avviso/limite del servizio ministeriale, non un motivo per lasciare vuota l'anteprima se il fascicolo e' gia' stato trovato.

Stato prova reale:

- certificato e Local Signer: verificati su macchina reale con Chrome e Local Signer locale `1.6.78`;
- anteprima server: ancora da ripetere dopo deploy Hetzner della versione `2.253.63`, perche' al momento della riproduzione `https://app.iusentra.it/api/pronto` rispondeva `2.253.60`.

## Aggiornamento 2.253.65 - UX acquisizione PST e uscita verso fascicolo

Data intervento: 2026-06-18.

Per il flusso PST lavoro `RG 3950/2026`, la procedura di acquisizione React è stata resa più esplicita:

- Step 4 è dedicato solo a cosa scaricare o includere: documenti, eventi, scadenziario, parti, formato PST e file già raccolti;
- la scelta del fascicolo interno resta nello Step 5, evitando duplicazioni nello Step 4;
- Step 7 presenta il riepilogo finale per destinazione, documenti e dati collegati;
- il comando finale registra nel fascicolo selezionato e, se il backend restituisce un URL interno, apre direttamente il fascicolo importato;
- il messaggio generico `Importazione completata o presa in carico dal gestionale operativo` è stato sostituito da messaggi puntuali: apertura automatica del fascicolo quando possibile, fallback `Fascicolo importato` solo se il redirect non è disponibile.

Il PIN del certificato non è stato scritto nei file di progetto né nei log.

Prova reale server del 18 giugno 2026:

- produzione Hetzner su `https://app.iusentra.it` verificata con commit `718ae2a241f3e9e1ec9200e2873f3fd463427f2b` e versione `2.253.65`;
- controllo visivo eseguito in Google Chrome reale sul PC dell'utente, non nel browser integrato, perché il Local Signer deve essere raggiunto da `127.0.0.1:27272`;
- Local Signer `1.6.78` raggiungibile da Chrome; auto-selezione del certificato ArubaPEC Authentication dell'avvocato confermata senza finestra Adobe e senza richiesta PIN in questa prova;
- Step 4 verificato con click reale: `Cosa scaricare`, dati/documenti/eventi/scadenziario/parti separati dal formato PST e dalla destinazione;
- Step 5 verificato con click reale: destinazione isolata in `Crea nuova pratica` / `Usa pratica esistente`;
- Step 7 verificato con click reale: riepilogo `Destinazione`, `Documenti`, `Dati collegati`, comando finale `Crea pratica e importa` o `Importa nel fascicolo selezionato`, e testo che chiarisce che non parte uno scarico nascosto dal portale;
- le vecchie diciture `Importa nel gestionale`, `Import completato` e `Importazione completata o presa in carico dal gestionale operativo` non compaiono più nella pagina server;
- la ricerca PST live del fascicolo `RG 3950/2026` in quella sessione è rimasta in attesa fino a circa 360 secondi e poi ha mostrato un messaggio guidato di servizio ministeriale lento. Per questo non è stato eseguito un import finale con `0/0` documenti e il redirect materiale al fascicolo non è stato cliccato; il redirect resta implementato e coperto dal guardrail React quando l'API restituisce un URL interno.

## Aggiornamento 2.253.66 - acquisizione PST e apertura fascicolo importato

Data intervento: 2026-06-18.

Per il flusso PST lavoro `RG 3950/2026`, lo Step 7 ora deve uscire dalla pagina di acquisizione appena l'importazione è stata registrata:

- il runtime telematico restituisce `fascicolo_url`, `redirect_url` e `documenti_url` sia in radice sia nel `summary`;
- `redirect_url` apre la scheda del fascicolo con ancora `#sezione-documenti-fascicolo`, cioè la zona in cui sono stati salvati i documenti;
- il frontend non si limita più a `fascicolo_url`/`url`: legge anche `documenti_url`, `dettaglio_url`, valori annidati e id fascicolo;
- la frase `Importazione completata. Fascicolo registrato nel gestionale.` non è più usata come fallback ordinario.

Questa modifica non tocca invio PEC, firma digitale, PIN, certificati o contenuto dei documenti. Interviene solo sul collegamento operativo post-import.

Guardrail locali:

- `python -m pytest tests/test_react_shell.py::test_react_wizard_pst_anteprima_riusa_snapshot_ricerca_rg tests/test_polisweb.py::test_api_portale_acquisizione_import_pst_importa_file_reali_e_salva_albero -q` passato;
- `pnpm --filter @iusentra/studio build` passato;
- `python tools/sync_packaging_files.py --check` passato.

## Aggiornamento 2.253.67 - PagoPA PST nel fascicolo

Data intervento: 2026-06-18.

Su richiesta utente, nella pagina dettaglio fascicolo React è stato aggiunto un comando PagoPA vicino alle azioni PDF e nel pannello laterale `Gestione fascicolo`:

- icona PagoPA fornita dall'utente copiata in `frontend/public/pagopa-removebg-preview.png` e pubblicata nel bundle statico come `/static/react/pagopa-removebg-preview.png`;
- il click apre una finestra sovrapposta al fascicolo con iframe verso `https://servizipst.giustizia.it/PST/it/pagopa_altripag.wp`;
- la finestra include il comando `Apri fuori`, necessario se il portale ministeriale impone restrizioni di incorporamento iframe;
- la modale si chiude con il pulsante `Chiudi` o con `Esc`, senza navigare via dal fascicolo;
- la modifica non salva dati di pagamento, non invia PEC, non usa PIN, non tocca firma digitale, Local Signer o deposito reale.

Guardrail locali:

- `pnpm --filter @iusentra/studio typecheck` passato;
- `python -m pytest tests/test_react_shell.py::test_react_fascicoli_suite_completa_route_componenti_e_lex tests/test_react_shell.py::test_react_fascicoli_page_collegata_nav_api_e_lex tests/test_react_shell.py::test_react_wizard_pst_anteprima_riusa_snapshot_ricerca_rg tests/test_polisweb.py::test_api_portale_acquisizione_import_pst_importa_file_reali_e_salva_albero -q --tb=short` passato;
- `pnpm --filter @iusentra/studio build` passato;
- `python -m pytest tests/test_react_asset_retention.py -q --tb=short` passato;
- `python -m pytest tests/test_utf8_integrity.py -q --tb=short` passato;
- `python tools/sync_packaging_files.py --check` passato.

Stato: da verificare dopo commit, push e deploy Hetzner su `https://app.iusentra.it/fascicoli/9B9DF2A1`, con click reale su `PagoPA`, apertura modale sopra il fascicolo, fallback `Apri fuori`, chiusura e controllo testi/card/bottoni.

## Aggiornamento 2.253.68 - PagoPA PST compilabile nel fascicolo

Data intervento: 2026-06-18.

Dopo la prova visiva su `https://app.iusentra.it/fascicoli/9B9DF2A1`, il portale ministeriale PagoPA ha mostrato il limite tecnico `X-Frame-Options: SAMEORIGIN`, che impedisce l'incorporamento diretto cross-origin in un iframe IUSENTRA.

Correzione applicata:

- il dettaglio fascicolo React non punta più l'iframe PagoPA direttamente al dominio ministeriale;
- la modale PagoPA usa il bridge autenticato IUSENTRA `/api/v1/ui/pst/pagopa-proxy/it/pagopa_altripag.wp?iusentra_fascicolo=<id>`;
- il bridge è limitato al solo host `servizipst.giustizia.it` e ai percorsi sotto `/PST/`, riscrive link, form, asset e redirect verso lo stesso proxy interno;
- i form PagoPA restano compilabili nella modale e i POST vengono inoltrati al PST senza consumare prima il corpo della richiesta;
- quando l'utente richiede manualmente la ricevuta PDF nel portale, la risposta PDF passa dal bridge, viene mostrata/scaricata dal browser e viene salvata nei documenti del fascicolo con fonte `PORTALE_TELEMATICO`, classificazione `RICEVUTA_PAGOPA` e tag `PagoPA`, `PST`, `ricevuta`;
- i comandi `Cliente` e `Soggetti` nel dettaglio fascicolo aprono ora la rispettiva pagina React in overlay interno, con lo stesso schema di modale usato da PagoPA, senza perdere la pratica aperta;
- `Apri fuori` resta disponibile come comando di emergenza, ma non è più il comportamento ordinario per la compilazione PagoPA.

Limiti operativi:

- IUSENTRA non genera ricevute PagoPA e non inventa link: intercetta e archivia il PDF solo quando il portale PST lo restituisce dopo la richiesta dell'utente;
- se durante il pagamento il circuito PagoPA porta l'utente su PSP, banca o dominio esterno al PST, quel tratto può imporre regole proprie di sicurezza; il bridge resta ristretto al PST ministeriale per non trasformarsi in proxy generico;
- nessun PIN, certificato, Local Signer, firma digitale o invio PEC è stato coinvolto da questa modifica.

Guardrail locali:

- `pnpm --filter @iusentra/studio typecheck` passato;
- `python -m pytest tests/test_react_shell.py::test_react_pst_pagopa_proxy_incorpora_portale_e_salva_ricevuta_pdf -q --tb=short` passato;
- `python -m pytest tests/test_react_shell.py::test_react_fascicoli_suite_completa_route_componenti_e_lex tests/test_react_shell.py::test_react_clienti_nuovo_e_soggetti_collegati_nav_api_lex_cf tests/test_react_shell.py::test_react_pst_pagopa_proxy_incorpora_portale_e_salva_ricevuta_pdf -q --tb=short` passato;
- `pnpm --filter @iusentra/studio build` passato;
- `python -m pytest tests/test_react_asset_retention.py -q --tb=short` passato;
- `python tools/sync_packaging_files.py --check` passato.

Stato: da portare su branch gemelli, deployare su Hetzner e verificare visivamente su produzione con click reale su `Cliente`, `Soggetti`, `PagoPA`, compilazione/visualizzazione iniziale del portale e richiesta ricevuta PDF quando disponibile.

## Aggiornamento 2.253.69 - TLS PagoPA PST

Data intervento: 2026-06-18.

La prova visiva server della versione `2.253.68` ha mostrato errore 502 nella modale PagoPA: il portale PST era raggiungibile da Chrome/curl Windows, ma `requests` locale e nel container fallivano con `CERTIFICATE_VERIFY_FAILED`.

Diagnosi:

- il leaf `servizipst.giustizia.it` risulta emesso da `TI Trust Technologies OV CA`;
- il server PST non espone una catena chiudibile dal bundle `requests/certifi`;
- con curl server l'errore era `unable to get local issuer certificate`;
- con bundle composto da `certifi` più l'intermedio ufficiale `TI Trust Technologies OV CA`, la chiamata al PST restituisce HTTP 200 e `text/html;charset=utf-8`.

Correzione applicata:

- aggiunto `web/certs/TITrustTechnologiesOVCA.pem`;
- il bridge PagoPA usa un bundle CA mirato `certifi + TI Trust` solo per `servizipst.giustizia.it/PST`;
- la verifica TLS resta attiva: non è stato introdotto `verify=False`;
- la modifica non tocca PIN, Local Signer, firma digitale, invio PEC, volumi o dati applicativi.

## Aggiornamento 2.253.70 - PagoPA PST DWR compilabile nel fascicolo

Data intervento: 2026-06-18.

Dopo la prova reale locale della modale PagoPA, il portale PST caricava la pagina iniziale ma il form `Nuovo pagamento` non era ancora affidabile: le chiamate DWR del Ministero uscivano verso `/PST/dwr`, perdevano il contesto della sessione e potevano ricevere errori CSRF o restare senza elenco uffici.

Correzione applicata:

- il bridge riscrive solo l'assegnazione DWR `_path`, lasciando invariato il resto dei JavaScript ministeriali per non corrompere sintassi o regex del PST;
- le POST DWR traducono `Referer`, `Origin`, `page` e `Content-Type` nel formato atteso dal portale ufficiale;
- `httpSessionId` vuoto viene valorizzato con il `JSESSIONID` PST già custodito nella sessione proxy;
- i percorsi raw `/PST/...` che sfuggono dal JavaScript vengono ricondotti al proxy IUSENTRA con redirect interno;
- la modale React concede `allow-same-origin` solo all'iframe PagoPA e usa referrer `same-origin`, così form, DWR e download PDF restano nello stesso contesto di proxy;
- la CSP rilassata con `unsafe-eval` è limitata alla risposta proxy PagoPA, perché il codice DWR storico del PST lo richiede; la CSP ordinaria IUSENTRA non viene allentata.

Prova reale locale:

- ambiente: Google Chrome installato su Windows, applicazione reale Docker `http://127.0.0.1:8080`, container healthy, `/api/pronto` con versione `2.253.70`;
- percorso: dettaglio fascicolo locale `9B9DF2A1`, click reale su `PagoPA`, apertura modale, click `+ Nuovo pagamento`;
- compilazione osservata: `Tipo pagamento` = `Contributo unificato e/o Diritti di cancelleria`, `Distretto` = `TORINO`, `Nominativo debitore` e `Codice fiscale` compilati;
- risultato: select `Ufficio Giudiziario` popolata con 66 opzioni, tra cui `Corte d'Appello - Torino`, `Giudice di Pace - Torino`, Procure e Tribunali del distretto;
- non sono comparsi errori CSRF, blocchi CSP pertinenti, errori console applicativi o timeout; non è stato premuto `Paga subito` e non è stato effettuato alcun pagamento;
- Browser plugin non disponibile nella sessione Codex: prova eseguita con Chrome installato controllato via Playwright, come fallback previsto per la verifica frontend;
- screenshot di prova fuori repository: `C:\Users\antmm\AppData\Local\Temp\iusentra-pagopa-225370-auth2-1781800757169\04-form-compilato-ok-locator.png`.

Limiti residui:

- IUSENTRA non inventa il link ricevuta: quando l'utente richiede manualmente la ricevuta PDF nel PST, il bridge intercetta il PDF restituito e lo collega ai documenti del fascicolo;
- se il pagamento passa a PSP, banca o dominio esterno al PST, quel tratto può imporre policy proprie e resta fuori dal proxy ristretto al Ministero;
- nessun PIN, certificato, firma digitale, Local Signer o invio PEC è stato usato da questa modifica.

## Aggiornamento 2.253.71 - Hardening CodeQL bridge PagoPA

Data intervento: 2026-06-18.

Il primo push della release PagoPA ha fatto emergere su CodeQL un alert di XSS riflesso sul punto in cui il proxy restituisce l'HTML ministeriale. Il comportamento è intenzionale solo dentro il bridge PagoPA, ma è stato irrigidito per evitare che path non pertinenti o redirect locali non governati entrino nel flusso.

Correzione applicata:

- il proxy serve solo path PST attesi per PagoPA: `it/pagopa_*`, `resources/` e `dwr/`;
- i path con schema, doppio slash, segmenti `..`, caratteri non previsti o prefissi fuori perimetro vengono rifiutati;
- la route di rientro `/PST/...` costruisce il target con `url_for("api_v1_react.pst_pagopa_proxy", ...)`, quindi resta sempre interna;
- la risposta testuale viene emessa come payload UTF-8 codificato, con commento CodeQL motivato perché il contenuto arriva dal dominio ministeriale verificato tramite bundle CA e rimane coperto da CSP/iframe PagoPA.

Test locali ripetuti:

- `python -m py_compile web\blueprints\api_v1_react.py web\bootstrap\telematico_portali_routes.py`;
- `python -m pytest tests\test_react_shell.py::test_react_pst_pagopa_proxy_incorpora_portale_e_salva_ricevuta_pdf tests\test_react_shell.py::test_react_fascicoli_suite_completa_route_componenti_e_lex tests\test_security_headers.py -q --tb=short`.


## Aggiornamento 2.253.72 - Cookie sessione IUSENTRA

Data intervento: 2026-06-18.

Su richiesta dell'utente il cookie HTTP di sessione dell'app viene rinominato da `hacs_session` a `iusentra_session`. La modifica è centralizzata nel runtime di sicurezza Flask e gli script di audit browser che impostano sessioni locali di collaudo sono stati aggiornati allo stesso nome. Non cambia il contenuto della sessione, non vengono salvati PIN o credenziali e restano invariati `HttpOnly`, `SameSite=Lax` e il perimetro tenant. Prova reale locale eseguita e ripetuta su Docker `2.253.73`: `/api/pronto` risponde `versione=2.253.73`, il container Flask espone `SESSION_COOKIE_NAME=iusentra_session`, Chrome installato su `http://127.0.0.1:8080/fascicoli/9B9DF2A1` ha aperto PagoPA nel fascicolo, selezionato `Contributo unificato e/o Diritti di cancelleria`, distretto `TORINO`, caricato `66` uffici e compilato nominativo/codice fiscale senza premere `Paga subito`.

## Aggiornamento 2.253.73 - Refactor CodeQL bridge PagoPA

Data intervento: 2026-06-18.

Sul nuovo SHA `34a42e9` CodeQL ha continuato a segnalare il sink XSS del bridge PagoPA, nonostante host, path e TLS fossero già allowlistati. Per eliminare il sink diretto, le risposte testuali del PST (`HTML`, `CSS`, `JavaScript`, `XML`) vengono ora servite inline da un file in memoria con `send_file`, dopo validazione del path PagoPA e riscritture controllate. Il comportamento visibile della modale resta invariato: il form ministeriale continua a essere renderizzato dentro il fascicolo e la cattura PDF resta agganciata alle risposte `application/pdf`.

Test ripetuti dopo il refactor:

- `python -m py_compile weblueprintspi_v1_react.py webootstrap	elematico_portali_routes.py web\services\security_runtime.py tests	est_security_headers.py`;
- `python -m pytest tests	est_react_shell.py::test_react_pst_pagopa_proxy_incorpora_portale_e_salva_ricevuta_pdf tests	est_react_shell.py::test_react_fascicoli_suite_completa_route_componenti_e_lex tests	est_security_headers.py -q --tb=short`.

## Aggiornamento 2.253.74 - CodeQL path bridge PagoPA

Data intervento: 2026-06-18.

Sul nuovo SHA 878ae1e il workflow CodeQL ha superato l'analisi, ma il required check di code scanning ha aperto un alert bloccante Uncontrolled data used in path expression sulla risposta send_file(BytesIO(...)) del bridge PagoPA. Il bridge ora scrive le risposte testuali PST in un file temporaneo creato dal server, con nome generato dal sistema, Content-Type ristretto ai tipi testuali attesi e nome inline costante. Il path non dipende più da contenuto PST o parametri utente; le chiamate DWR `/dwr/call/plaincall/...` tornano come `text/plain; charset=utf-8` così il motore DWR popola correttamente gli uffici. Il cookie di sessione resta `iusentra_session`. Prova reale locale su Docker `2.253.74`: Chrome installato su `127.0.0.1:8080/fascicoli/9B9DF2A1`, cookie visibile solo `iusentra_session`, PagoPA aperto, `Nuovo pagamento`, tipo `Contributo unificato e/o Diritti di cancelleria`, distretto `TORINO`, `66` uffici giudiziari caricati, nominativo/codice fiscale compilati, nessun click su `Paga subito`.
## Aggiornamento 2.253.75 - Guardrail SQLite WAL nei gate CI

Data intervento: 2026-06-18.

Dopo il push dello SHA `3e42314`, CodeQL è risultato `success`, ma il gate remoto `Pytest core fase 7/10 observability parte 3/3` ha fallito su `tests/test_storage_strategy.py::test_core_runtime_uses_tenant_paths_for_sensitive_repositories`. La causa non era il bridge PagoPA: il rilevatore `_sqlite_runtime_is_unseeded()` apriva `studio.db` con `immutable=1`; con WAL attivo la lettura poteva non vedere le modifiche appena committate nello stesso request e rilanciare una migrazione JSON su SQL già operativo. Il runtime ora usa `mode=ro` senza `immutable`, così legge lo stato reale del database senza aprirlo in scrittura e senza indebolire il blocco anti-perdita sui JSON vuoti.

Test locali ripetuti:

- `python scripts\run_pytest_phases.py --core-shard 7 --core-total-shards 10 --core-subshard 3 --core-total-subshards 3 --core-subdivide-items --timeout-minutes 5` -> 32/32 OK;
- `python -m pytest tests\test_storage_strategy.py::test_sqlite_runtime_non_rilancia_migrazione_se_settings_config_esiste tests\test_storage_strategy.py::test_core_runtime_uses_tenant_paths_for_sensitive_repositories -q --tb=short` -> 2/2 OK.

## Aggiornamento 2.253.76 - Pulizia rendering PagoPA PST

Data intervento: 2026-06-18.

Durante la prova visiva locale del bridge PagoPA, Chrome segnalava un errore MIME sul foglio opzionale `resources/static/css/print.css`: il portale PST lo restituiva come HTML, quindi il browser lo rifiutava come stylesheet. Il problema non bloccava la compilazione del pagamento, ma lasciava un errore console visibile nel controllo qualità.

Correzione applicata:

- per il solo stylesheet opzionale `print.css`, quando il PST risponde con contenuto non CSS, il bridge restituisce un CSS vuoto e valido (`text/css; charset=utf-8`);
- le pagine HTML, i JavaScript ministeriali, le chiamate DWR e i PDF ricevuta restano invariati;
- il cookie runtime resta `iusentra_session` e non vengono salvati PIN, credenziali, dati pagamento o certificati.

Prova reale locale su Docker `2.253.76`:

- ambiente: Google Chrome installato su Windows, applicazione reale `http://127.0.0.1:8080`, container healthy, `/api/pronto` con `versione=2.253.76`;
- runtime Flask nel container: `SESSION_COOKIE_NAME=iusentra_session`;
- percorso: fascicolo locale reale `DC5BF1DB`, click su `PagoPA`, apertura modale, click `+ Nuovo pagamento`;
- compilazione controllata senza invio: `Tipo` = `Contributo unificato e/o Diritti di cancelleria`, `Distretto` = `TORINO`, `Ufficio Giudiziario` = `Tribunale Ordinario - Torino` (`0012720095`), nominativo e codice fiscale fittizi;
- risultato: DWR ministeriale `PagamentiTelematiciAjaxServices.getUfficiGiudiziari.dwr` HTTP 200, select ufficio popolata con `66` opzioni, bottone `Paga subito` visibile, nessun click su `Paga subito`;
- console: `0` errori dopo la correzione del `print.css`; restano solo i warning standard di Chrome sul sandbox iframe con `allow-scripts` e `allow-same-origin`, necessari al PST/DWR;
- screenshot fuori repository: `C:\Users\antmm\AppData\Local\Temp\iusentra-pagopa-locale-225376-finale.png`.

Prova reale server su Hetzner `2.253.76`:

- ambiente: Google Chrome installato su Windows con Chrome visibile, produzione `https://app.iusentra.it`, commit server `d80b9ce`, container app/scheduler/OCR/Redis healthy e `/api/pronto` con `versione=2.253.76`;
- runtime Flask nel container Hetzner: `SESSION_COOKIE_NAME=iusentra_session`;
- percorso: fascicolo reale `9B9DF2A1`, `RG 3950/2026`, rif. interno `2026/308`, `Spagnolo Sara c. MIM`, click su `PagoPA`, modale incorporata con iframe `/api/v1/ui/pst/pagopa-proxy/it/pagopa_altripag.wp`;
- interazione verificata: click `+ Nuovo pagamento`, `Tipo` = `Contributo unificato e/o Diritti di cancelleria`, `Distretto` = `TORINO`, `Ufficio Giudiziario` = `Tribunale Ordinario - Torino` (`0012720095`), nominativo e codice fiscale fittizi;
- risultato: DWR ministeriale `PagamentiTelematiciAjaxServices.getUfficiGiudiziari.dwr` HTTP 200 `text/plain`, select ufficio popolata con `66` opzioni, bottone `Paga subito` visibile e abilitato, nessun click su `Paga subito`;
- `print.css`: proxy HTTP 200 `text/css; charset=utf-8`, contenuto CSS controllato e non HTML;
- console: nessun errore applicativo; restano solo i warning standard Chrome del sandbox iframe;
- Cliente e Soggetti: pulsanti top del fascicolo verificati nello stesso modello di modale incorporata, con iframe `/clienti/2A1216AA/modifica` e `/soggetti?fascicolo=9B9DF2A1`;
- screenshot fuori repository: `C:\Users\antmm\AppData\Local\Temp\iusentra-pagopa-produzione-225376.png` e `C:\Users\antmm\AppData\Local\Temp\iusentra-soggetti-modale-produzione-225376.png`.

Stato: codice, Docker locale, GitHub, CodeQL/check remoti e server reale risultano allineati sul comportamento verificato. Il presente blocco documenta la prova server e va mantenuto come guardrail per future modifiche a fascicoli/PagoPA.

## Aggiornamento 2.253.79 - Validazione CAdES atto principale

Data intervento: 2026-06-19.

Caso reale: nella prova su `https://app.iusentra.it/fascicoli/E5AE4668/deposito/prepara#generazione-busta`, fascicolo `2026/330 - Marchetti Lucia`, la UI React riconosceva l'atto principale `Autocertificazione ricorso.PDF.p7m` come contenitore `.p7m` e mostrava zero documenti da firmare, ma la simulazione PEC bloccava ancora con `Atto principale non firmato digitalmente`.

Causa: il validatore documentale controllava solo il flag storico `firmato_digitalmente`; per un contenitore CAdES già presente questo non è sufficiente, perché la prova tecnica primaria è il contenitore `.p7m`/PKCS#7 e non una stringa o un flag storico.

Correzione applicata:

- il validatore busta considera firmato un documento principale se il file selezionato è già un contenitore CAdES `.p7m`, `.sig` o `.pkcs7`;
- resta invariata la regola anti-falso-verde: un semplice nome o testo con parola `Firmato` non basta per mostrare firma digitale se il file non è un contenitore o non ha prova PAdES/CAdES;
- la firma multipla non deve rifirmare contenitori già firmati;
- aggiunto test mirato `test_orchestratore_non_blocca_atto_principale_cades_p7m_senza_flag_storico`.

Verifica tecnica eseguita prima del rebuild: `python -m py_compile pct\deposito_guidato.py` e test mirato `.p7m` verdi.

Prova reale locale `2.253.79` eseguita su `http://127.0.0.1:8080/fascicoli/DC5BF1DB/deposito/prepara#generazione-busta`, fascicolo `RG 466/2023 - Alessi Robertino`, ufficio `Giudice di Pace - Palmi`:

- pagina React autenticata, senza fallback legacy e senza HTML grezzo;
- `Simula invio PEC` cliccato e confermato dalla UI reale;
- esito visibile: `Simulazione PEC completata senza invio reale: compatibilità 100%`;
- nessun blocco `Atto principale non firmato digitalmente`;
- report UI con `Atto.enc ministeriale AES256`, `DatiAtto.xml`, `IndiceDocumentiDepositati.PDF`, `8 documenti operativi indicati nella busta`, `PEC ufficio giudiziario`, `Corpo PEC verificabile`, `Simulazione senza invio SMTP`;
- `Invia deposito reale` abilitato dopo la prova positiva;
- testo PEC verificato con gli 8 documenti operativi richiesti dall'utente.

Doppia verifica fisica locale `2.253.79`:

- file prodotti nel container reale: `/tmp/busta_8FA0E152/Atto.msg` da `4.636.574` byte e `/tmp/busta_8FA0E152/Atto.enc` da `4.637.389` byte;
- allegati effettivi in `Atto.msg`: `DatiAtto.xml`, `Note conclusive Alessi Robertino.pdf.p7m`, `attoACQ.pdf.p7m`, `Note trattazione scritta Alessi Robertino c Zurich Ass.ni-signed.pdf.p7m`, `perizia_r_ino_alessi__zurich_ass_ni.pdf.p7m`, `giudice_di_pace_di_palmi2.pdf.p7m`, `MEMORIA_CONCLUSIVA_ZURICH.pdf.p7m`, `Istanza trattazione scritta Alessi Robertino.pdf.p7m`, `MOD. Inizio Attivita Peritali.pdf.p7m`, `IndiceDocumentiDepositati.PDF`;
- confronto sugli 8 documenti operativi richiesti: `expected_present_count=8`, `missing=[]`, `extra_operativi=[]`;
- tecnici presenti e distinti dai documenti operativi: `DatiAtto.xml`, `IndiceDocumentiDepositati.PDF`;
- `Atto.enc`: CMS `enveloped_data`, algoritmo `aes256_cbc`, `aes256=true`.

Prova reale server `2.253.79` eseguita su `https://app.iusentra.it/fascicoli/E5AE4668/deposito/prepara#generazione-busta`, fascicolo `2026/330 - Marchetti Lucia`, ufficio `Tribunale di Vicenza`:

- server Hetzner sul commit `a9b9ed11d5e7c941b77df0c793effaee5f5fa953`, `/api/pronto` pubblico `versione=2.253.79`, container app, scheduler e OCR healthy;
- pagina React autenticata, senza fallback legacy e senza HTML grezzo;
- `Simula invio PEC` cliccato e confermato dalla UI reale, senza invio SMTP;
- esito visibile: `Simulazione PEC completata senza invio reale: compatibilità 100%`;
- nessun blocco `Atto principale non firmato digitalmente` su `Autocertificazione ricorso.PDF.p7m`;
- destinatario PEC confermato: `tribunale.vicenza@civile.ptel.giustiziacert.it`;
- report UI con `Atto.enc ministeriale AES256`, `DatiAtto.xml`, `IndiceDocumentiDepositati.PDF`, `11 documenti operativi indicati nella busta`, `PEC ufficio giudiziario`, `Corpo PEC verificabile`, `Simulazione senza invio SMTP`;
- `Invia deposito reale` abilitato dopo la prova positiva.

Doppia verifica fisica server `2.253.79`:

- file prodotti nel container Hetzner: `/tmp/busta_3BF49C3F/Atto.msg` da `36.630.676` byte e `/tmp/busta_3BF49C3F/Atto.enc` da `36.631.506` byte;
- allegati effettivi in `Atto.msg`: `DatiAtto.xml`, `Autocertificazione ricorso.PDF.p7m`, `Autocertificazione situazione reddituale.PDF.p7m`, `Carta Identità e C.F. Lucia Marchetti.PDF`, `Contratto 24-25.pdf.p7m`, `Contratto Rossi 2025-2026.pdf`, `Lettera di diffida Carta Docenti Marchetti Lucia.pdf`, `Procura.PDF.p7m`, `Richiesta pagamento annualità “CARTA DEL DOCENTE” - 2025-09-26T121520.067.eml`, `Richiesta pagamento annualità “CARTA DEL DOCENTE” - 2025-09-26T121525.647.eml`, `Richiesta pagamento annualità “CARTA DEL DOCENTE” - 2025-09-26T121528.773.eml`, `Ricorso.pdf`, `IndiceDocumentiDepositati.PDF`;
- confronto sugli 11 documenti operativi in busta: `expected_present_count=11`, `missing=[]`, `extra_operativi=[]`;
- tecnici presenti e distinti dai documenti operativi: `DatiAtto.xml`, `IndiceDocumentiDepositati.PDF`;
- `Atto.enc`: CMS `enveloped_data`, algoritmo `aes256_cbc`, `aes256=true`.

## Aggiornamento 2.253.78 - Doppia verifica Atto.enc deposito Palmi

Data intervento: 2026-06-19.

Controllo eseguito sulla copia reale locale Docker `http://127.0.0.1:8080`, versione `/api/pronto=2.253.78`, fascicolo `DC5BF1DB`, `RG 466/2023 - Alessi Robertino`, ufficio `Giudice di Pace - Palmi`, PEC `gdp.palmi@civile.ptel.giustiziacert.it`, codice ministeriale `0800570152`.

Esito prova reale UI:

- pagina React autenticata, senza fallback legacy e senza HTML grezzo;
- `Simula invio PEC` cliccato realmente dalla UI, conferma eseguita solo per simulazione senza invio;
- report finale visibile: `Simulazione PEC completata senza invio reale: compatibilità 100%`;
- report compatibilità: `Atto.enc ministeriale AES256`, `DatiAtto.xml`, `IndiceDocumentiDepositati.PDF`, `8 documenti operativi indicati nella busta`, `PEC ufficio giudiziario`, `Corpo PEC verificabile`, `Simulazione senza invio SMTP`;
- `Invia deposito reale` risulta abilitato dopo la prova positiva;
- nessuna richiesta di firma multipla e nessun tentativo di rifirma sui contenitori `.p7m`.

Doppia verifica documento per documento:

- corpo PEC predisposto: contiene la sezione `Il file Atto.enc contiene i seguenti documenti:` con gli 8 documenti operativi richiesti;
- report UI `Documenti indicati nel pacchetto`: contiene gli stessi 8 documenti operativi, più i tecnici `DatiAtto.xml` e `IndiceDocumentiDepositati.PDF`;
- file tecnici nel container reale: `/tmp/busta_EA46319E/Atto.msg` da `4.636.574` byte e `/tmp/busta_EA46319E/Atto.enc` da `4.637.389` byte;
- parsing tecnico di `Atto.msg`: allegati presenti `DatiAtto.xml`, `Note conclusive Alessi Robertino.pdf.p7m`, `attoACQ.pdf.p7m`, `Note trattazione scritta Alessi Robertino c Zurich Ass.ni-signed.pdf.p7m`, `perizia_r_ino_alessi__zurich_ass_ni.pdf.p7m`, `giudice_di_pace_di_palmi2.pdf.p7m`, `MEMORIA_CONCLUSIVA_ZURICH.pdf.p7m`, `Istanza trattazione scritta Alessi Robertino.pdf.p7m`, `MOD. Inizio Attivita Peritali.pdf.p7m`, `IndiceDocumentiDepositati.PDF`;
- confronto sugli 8 documenti operativi richiesti: `missing=[]`, `extra_operativi=[]`;
- parsing tecnico di `Atto.enc`: CMS `enveloped_data`, algoritmo `aes256_cbc`.

Nota ordine documenti: nell'`Atto.msg` l'ordine tecnico mette prima l'atto principale selezionato in UI, cioè `Note conclusive Alessi Robertino.pdf.p7m`, poi gli allegati. Il corpo PEC mostra invece gli 8 documenti operativi nell'ordine richiesto dall'utente. Non risultano documenti operativi aggiuntivi rispetto alla selezione prevista.

## Aggiornamento 2.253.80 - PAT/SIGA Formweb e Portale Avvocato in React

Data intervento: 2026-06-19.

Fonti consultate:

- documentazione ufficiale G.A. `Documentazione operativa, modulistica e manualistica`;
- `Manuale_Avvocato_pe005_ITA (1).pdf` fornito dall'utente e manuale ufficiale pubblicato;
- documento ufficiale `pubblicazione NTO del PAT Portale avvocato` sulle nuove regole Formweb;
- istruzioni ufficiali `Istruzioni per il download dei pdf`;
- istruzioni ufficiali per compilazione moduli di deposito aggiornate al 4 giugno 2025;
- requisiti tecnici ufficiali per avvocati difensori e cittadini;
- documento utente `Impostazione in chrome per download pdf.docx`.

Decisione operativa:

- per PAT/SIGA, dal regime 1 febbraio 2026 Formweb è trattato come canale prioritario;
- PEC resta solo residuale quando il Formweb non è utilizzabile per ragioni tecniche documentate;
- il vecchio upload dal nuovo portale non viene presentato come canale ordinario a regime;
- PAT/SIGA non usa certificati `.cer` PST né `Atto.enc`; la firma da presidiare è PAdES;
- i PDF ufficiali 4.x sono moduli dinamici da scaricare e aprire con Acrobat Reader, non da compilare nel viewer del browser.

Modifiche applicate:

- aggiunto `pct/pat_moduli.py` con catalogo ufficiale dei moduli PAT/SIGA, Formweb, limiti, fonti, guida Chrome/Acrobat e suggeritore modulo per materia/tipo deposito;
- aggiornato il profilo `pat_siga` in `legal_deposit/policies.py` con limiti Formweb 50 file, 300 MB per file e 300 MB totali, priorità Formweb dal 1 febbraio 2026 e PEC residuale;
- esteso `web/services/react_telematico_bridge.py` con `patProcedure`, card dedicate PAT, checklist Formweb/PAdES/ricevute e avviso operativo sul regime Formweb;
- esteso `frontend/src/telematicoSurfacesData.ts` e `frontend/src/components/TelematicoSurfacePage.tsx` con pannello React PAT/SIGA: sessione ufficiale SIGA governata dal Local Connector del PC dell'avvocato, senza iframe fragile, senza `window.open` e senza fallback esterno come soluzione, fasi operative, tipologie Formweb, filtro moduli per materia e fonti ufficiali;
- aggiornati gli stili in `frontend/src/components/TelematicoSurfacePage.css` con layout responsive desktop/tablet/mobile.
- corretto lo stato iniziale della superficie React: su `/pat` lo skeleton interno mostra `PAT Amministrativo`, non eredita più il titolo generico `PolisWeb / PST` quando l'API è ancora in caricamento o non risponde.
- aggiornato il resolver backend delle sessioni assistite: in Docker il container usa `host.docker.internal:27272`, mentre il browser chiama direttamente il Local Connector su `127.0.0.1:27272`; questo preserva il modello corretto anche su `https://app.iusentra.it`, dove il server non può raggiungere il `localhost` del PC dell'avvocato.

Test automatici eseguiti:

- `python -m py_compile pct/pat_moduli.py web/services/react_telematico_bridge.py legal_deposit/policies.py`;
- `python -m py_compile pct/pat_moduli.py web/services/telematico_runtime.py web/services/react_telematico_bridge.py legal_deposit/policies.py`;
- `python -m pytest tests/test_canali_telematici_deposito.py::test_pat_siga_catalogo_moduli_e_formweb_da_fonti_ufficiali tests/test_react_shell.py::test_react_superfici_telematiche_collegate_nav_api_css tests/test_react_shell.py::test_react_superfici_telematiche_api_payload_reale -q`;
- `python -m pytest tests/test_portali_payload_import_ui.py::test_assistant_start_docker_usa_local_connector_host_machine tests/test_portali_payload_import_ui.py::test_assistant_start_accetta_ptt_pat_pdp tests/test_react_shell.py::test_react_superfici_telematiche_api_payload_reale tests/test_web_bootstrap.py::test_docker_compose_prevede_runtime_ollama_sulla_stessa_macchina tests/test_canali_telematici_deposito.py::test_profili_pdp_pat_ptt_non_ereditano_busta_pct_o_pec_diretta tests/test_canali_telematici_deposito.py::test_pat_siga_catalogo_moduli_e_formweb_da_fonti_ufficiali tests/test_react_shell.py::test_react_wizard_pst_verifica_local_signer_dal_browser -q`;
- `pnpm --filter @iusentra/studio typecheck`;
- `pnpm --filter @iusentra/studio build`;
- `python -m pytest tests/test_canali_telematici_deposito.py::test_profili_pdp_pat_ptt_non_ereditano_busta_pct_o_pec_diretta tests/test_canali_telematici_deposito.py::test_pat_siga_catalogo_moduli_e_formweb_da_fonti_ufficiali tests/test_react_shell.py::test_react_superfici_telematiche_api_payload_reale tests/test_react_asset_retention.py -q`.
- `python -m pytest tests/test_react_asset_retention.py -q --tb=short`.

Docker locale reale:

- `docker compose build --no-cache app`;
- `docker compose up -d --no-build --force-recreate app scheduler-worker ocr-worker nginx`;
- `docker compose ps`: `app`, `scheduler-worker`, `ocr-worker`, `redis`, `audit-postgres` e `audit-worm` healthy, `nginx` up;
- `GET http://127.0.0.1:8080/api/pronto`: `ok=true`, `versione=2.253.80`;
- `docker compose exec -T app python -c "import pct; print(pct.__version__)"`: `2.253.80`;
- `GET http://127.0.0.1:27272/ping?light=1`: Local Connector `1.6.78` raggiungibile dalla macchina reale.

Prova reale locale eseguita nel browser integrato visibile su `http://127.0.0.1:8080/pat`:

- desktop `1280x900`: pagina autenticata, `h1=PAT Amministrativo`, zero iframe, nessun testo `Apri fuori`, nessun link esterno nella sezione sessione assistita, nessun overflow orizzontale;
- click reale su `Avvia sessione ufficiale SIGA`: la URL resta `/pat`, stato `monitor_download_attivo`, messaggio `Monitor download della sessione assistita attivo`, nessun errore `Local Connector non raggiungibile`;
- click reale su `Raccogli file ufficiali`: stato controllato, nessun file raccolto perché non è stato scaricato nulla dal portale ufficiale nella prova, nessun errore connettore;
- click reale su `Chiudi sessione`: stato `sessione_chiusa` e messaggio `Sessione assistita chiusa`;
- filtro moduli con testo `rimborso`: campo valorizzato, scheda `Modulo PDF deposito richiesta rimborso` visibile con comando `Scarica modulo ufficiale`;
- scroll completo fino al fondo: visibili guida Chrome/PDF, manuale avvocato, fonti ufficiali e collegamenti rapidi, senza overflow;
- tablet `820x1180`: `PAT Amministrativo` anche durante caricamento, nessun ritorno a `PolisWeb`, dati Formweb caricati, scroll completo fino al fondo, zero iframe, zero overflow e nessun errore console;
- mobile `390x844`: `PAT Amministrativo`, zero iframe, zero overflow, pulsanti sessione impilati e leggibili a `259x44`; click reale su `Avvia sessione ufficiale SIGA` dopo scroll materiale, stato `monitor_download_attivo`, nessun errore Local Connector, chiusura sessione e scroll completo fino al fondo con fonti e guide visibili.

Stato anti-regressione: i test mirati impediscono che PAT/SIGA torni a ereditare busta PCT, `.cer` PST, `Atto.enc` o PEC come canale ordinario, verificano che il payload React esponga moduli ufficiali, Formweb e portale ufficiale, e presidiano che l'avvio del Portale Avvocato passi da Local Connector/browser locale senza iframe o apertura esterna come soluzione finale.

## Aggiornamento 2.253.82 - PAT/SIGA documenti fascicolo e PDF ufficiali XFA

Data intervento: 2026-06-19.

Obiettivo operativo: trasformare `/pat` da pagina informativa/catalago a procedura effettiva per l'avvocato, con lettura dei documenti del fascicolo, selezione allegati, generazione del modulo ufficiale PAT e consegna finale SIGA.

Fonti e materiali usati:

- pagina ufficiale Giustizia Amministrativa `Documentazione operativa e modulistica`, sezione `Moduli 4.x aggiornati al 7/07/2025`;
- template ufficiali PDF XFA: `ModuloDepositoRicorso_4.02.pdf`, `ModuloDepositoAtto_4.02.pdf`, `ModuloDepositoRichiesteSegreteria_4.01.pdf`, `ModuloDepositoIstanza_4.01.pdf`, `ModuloDepositoPerAusiliariDelGiudiceEPartiNonRituali_4.01.pdf`, `ModuloDepositoRimborso_4.01_2026.pdf`;
- PDF prodotto in precedenza da IUSENTRA confrontato come non conforme perché era un riepilogo da pochi KB e non il modulo XFA ufficiale.

Modifiche applicate:

- aggiunto `pct/pat_pdf_templates.py`, compilatore XFA che clona il PDF ministeriale, valorizza il pacchetto `template` XFA e preserva `/AcroForm` e `/XFA`;
- aggiunti i PDF ufficiali in `pct/data/pat_moduli/`;
- `/api/v1/ui/pat/moduli/prefill` ora espone i documenti reali del fascicolo con id, nome, tipo, dimensione, stato firma, ruolo suggerito, URL `Visualizza` e URL `Scarica`;
- `/api/v1/ui/pat/moduli/compila` accetta `documents`, verifica che ogni documento appartenga al fascicolo selezionato, legge i file con `percorso_documento_lettura()` e `decrypt_doc()`, applica i limiti Formweb e incorpora gli allegati nel PDF generato;
- React `/pat` ora mostra solo le sezioni operative `Fascicolo`, `Deposito`, `Documenti`, `Modulo`, `SIGA`;
- la sezione `Documenti del fascicolo` consente selezione/deselezione, ruolo allegato, flag `Firma PAdES`, apertura anteprima e download del documento.

Verifiche automatiche già eseguite:

- `python -m compileall pct\pat_pdf_templates.py web\blueprints\api_v1_react.py`;
- `npm run typecheck`;
- generazione tecnica di tutti i moduli PAT ufficiali configurati: tutti hanno una pagina, `/AcroForm`, `/XFA=True`, dimensione circa 1,3-1,7 MB e allegati incorporati;
- `python -m pytest tests\test_react_shell.py -k "pat_modulo or pat_prefill or superfici_telematiche" -q`;
- `npm run build`.

Limiti residui prima della chiusura:

- prova reale su `127.0.0.1:8080/pat` dopo rebuild Docker locale ancora da eseguire in questa tranche;
- prova visiva produzione `https://app.iusentra.it/pat` ancora da eseguire dopo commit/push/deploy;
- la consegna ufficiale resta nel portale SIGA/Formweb: IUSENTRA prepara modulo e allegati, poi importa ricevute e file ufficiali prodotti dalla sessione.
## Aggiornamento 2.253.84 - PAT/SIGA modello ministeriale XFA ufficiale compilato

Data intervento: 2026-06-20.

Stato operativo: il comando `Genera modulo ufficiale` della superficie React `/pat` produce come file principale il modello ministeriale XFA originale compilato, non un riepilogo IUSENTRA e non un PDF standard alternativo. Gli allegati del fascicolo restano documenti separati, pronti per Formweb/SIGA.

Decisioni operative confermate:

- i template ufficiali PAT 4.x sono integrati in `pct/data/pat_moduli/` e vengono clonati preservando `/AcroForm` e `/XFA`;
- il compilatore XFA valorizza ricorrente, resistente, codice fiscale, oggetto e nomi allegati nei campi del modello;
- `ModuloDepositoRicorso_4.02.pdf` integrato nel repository è byte-identico al file ufficiale consegnato dall'utente per la verifica locale;
- Chrome/PDFium può mostrare l'avviso Adobe sui moduli LiveCycle/XFA: questo non indica PDF vuoto. Il dato compilato vive nel pacchetto XFA e va aperto con Acrobat Reader per la resa ministeriale completa;
- gli allegati selezionati dal fascicolo non vengono incorporati nel PDF modulo, perché Formweb li riceve come file separati.

Verifiche concluse:

- test locali mirati su compilatore PAT, superficie React, canali deposito, UTF-8, asset retention, OpenAPI e packaging;
- Docker locale reale `127.0.0.1:8080` healthy con versione `2.253.84`;
- browser integrato reale su `127.0.0.1:8080/pat`: fascicolo `DC5BF1DB`, `20` documenti letti dal fascicolo, PDF XFA generato con dati e allegati presenti, desktop/tablet/mobile senza overflow, `Avvia SIGA` leggibile;
- commit finale `0cee6f6caffd853cbecbde4cf5b5c78828d74058` pushato sui branch gemelli e required gate GitHub/CodeQL verdi;
- deploy Hetzner CPX42 completato, `https://app.iusentra.it/api/pronto` risponde `versione=2.253.84`, container app/scheduler/OCR healthy e cache Docker ripulita;
- browser produzione autenticato su `https://app.iusentra.it/pat`: superficie React `Prepara deposito PAT`, selezione fascicolo reale, documenti con `Visualizza`/`Scarica`, `Genera modulo ufficiale`, `Avvia SIGA`, zero errori console;
- probe nel container Hetzner: `build_pat_official_pdf("deposito_ricorso", ...)` produce `ModuloDepositoRicorso_4.02_compilato_iusentra.pdf`, una pagina, `/XFA=True`, con `Mario`, `Rossi`, `RSSMRA80A01H501U`, `Zurich Ass.Ni`, oggetto e allegati `decretoGenerico.pdf`/`attoACQ.pdf.p7m` presenti nello XFA.

## Rettifica analisi copertura XFA PAT/SIGA - 2026-06-20

La prova Acrobat confermata dall'utente riguarda un solo campo del modulo ministeriale XFA (`oggetto` del ricorso). Questo dimostra che IUSENTRA può scrivere valori visibili in Acrobat dentro il modello ufficiale, ma non equivale a copertura 100% dei moduli PAT.

La matrice operativa completa è stata registrata in `artifacts/react-migration/pat-xfa-coverage-matrix-2026-06-20.md` con colonne: modulo, campo obbligatorio, percorso XFA, campo IUSENTRA, dato DB, prova PDF e prova visiva Acrobat.

Stato bloccante prima del lavoro applicativo:

- non dichiarare `copertura 100%` finché ogni campo obbligatorio o obbligatorio condizionato non ha percorso XFA, campo UI, dato DB, test XFA e prova visiva Acrobat;
- le sezioni con pulsante `Aggiungi` devono essere trattate come array reali: parti, documenti, procure, notifiche, atti impugnati, CIG e versamenti;
- gli allegati non possono essere considerati coperti quando viene scritto solo il nome file: vanno collegati ai documenti del fascicolo, con ruolo PAT, hash, firma e destinazione Formweb;
- i campi difensore, PNRR, appalti/CIG, istanze, atti impugnati e rimborso richiedono struttura dati PAT dedicata prima di una validazione reale.

## Aggiornamento 2.253.85 - PEC presidiate, scadenze operative e lista fascicoli

Data intervento: 2026-06-20.

Obiettivo operativo: rendere il presidio PEC un servizio automatico strutturato. Le PEC tecniche di deposito aggiornano il fascicolo/deposito senza produrre avvisi grezzi; le comunicazioni di cancelleria e i documenti del fascicolo producono invece solo eventi operativi chiari per l'avvocato, propagati a profilo processuale, agenda, scadenziario, topbar, push e lista fascicoli.

Decisioni operative applicate:

- `Comunicazione.xml` viene usato per esporre cliente, parte/soggetto processuale, giudice, RG, evento e ufficio reale quando il codice ufficio è risolvibile;
- le notifiche tecniche `ACCETTAZIONE DEPOSITO TELEMATICO` ed `ESITO CONTROLLI AUTOMATICI DEPOSITO TELEMATICO` non devono comparire come eventi grezzi in topbar, push, agenda o scadenziario;
- scadenziario e agenda mostrano solo attività realmente operative: udienze, termini, notifiche, lettura provvedimenti, produzione atti o verifica mirata di allegati/link;
- la colonna `Prossima scad.` dei fascicoli legge le scadenze aperte già prodotte dalla matrice PEC/documenti anche quando il record storico non ha ancora l'ID interno del fascicolo;
- il collegamento della prossima scadenza segue ID interno, alias forte, RG univoco oppure RG più cliente/parte; se il solo RG è ambiguo resta `n.d.` e non viene assegnato automaticamente.

Stato tecnico locale prima della prova reale:

- parser PEC, bridge React Email PEC, scadenziario, agenda, topbar, push e fascicoli aggiornati a livello codice;
- test mirati documentati in `artifacts/react-migration/pytest-confirmed-ok.md`;
- prova reale su `127.0.0.1:8080` eseguita dopo rebuild Docker della copia utente.

Stato finale locale dopo rebuild e riparazione mirror SQLite:

- Docker locale reale riavviato su `127.0.0.1:8080`, `/api/pronto` risponde `ok=true`, `versione=2.253.85`, app/scheduler/OCR healthy;
- audit dati a freddo `scripts/audit_data_flow_contract.py --registry data/tenants.json --json` con `ok=true`, `source_of_truth=sqlite`, `quick_check=ok`, zero errori e zero warning bloccanti;
- il mirror rigenerabile `moduli_json_records` del tenant `tenant-8bf98719c459` è stato ricostruito dopo corruzione SQLite limitata al mirror, senza perdita delle tabelle core: `fascicoli=7`, `scadenze=177`, `appuntamenti=352`, `clienti=24`, `moduli_json_records=10613` nell'audit finale;
- la copia corrotta e i backup runtime della riparazione sono stati trattati come artefatti tecnici, non come dati applicativi da committare, e spostati fuori repository in `C:\Users\antmm\AppData\Local\Temp\iusentra-db-repair-backups\20260620-pec-presidiate`.

Prova matrice PEC reale sulla sessione autenticata locale:

- `POST /api/pec/rebuild-matrix?limit=0&worker_limit=1200`: `ok=true`, `processed=6`, `failed=0`;
- messaggio PEC reale `pec_d2ff602838502a92f3af58c9`, email `63bd5d3db70c401ea29c5ba701f23afe`, oggetto `POSTA CERTIFICATA: COMUNICAZIONE 274/2026/CC`;
- job correnti del tenant reale: una sola riga `done` per `parse`, `classify`, `ocr`, `signcheck`, `validate`, `link`; nessun `queued`, `error` o `failed` per `tenant-8bf98719c459`;
- `Comunicazione.xml` propaga in UI `LOPRETE DOMENICO`, `LOPRETE DOMENICO (Ricorrente principale)`, `LAZZARO FILIPPO (Convenuto principale)`, `Tribunale di Palmi`, `RUSCIO EMANUELA`, `RG 274/2026`, `CONFERMA UDIENZA EX ART. 171 BIS 3 c. CPC`, `09/07/2026 09:30`;
- scadenza automatica esistente `460714fe-7eda-419a-8650-257f9d7e2f24`, agenda collegata `34E102D2`, `deadline_kind=udienza`, `calendar_scope=agenda_and_scadenziario`, `event_time=09:30`.

Prova visiva reale su Chrome/Browser autenticato `127.0.0.1:8080`:

- PEC: screenshot `C:\Users\antmm\AppData\Local\Temp\iusentra-pec-profilo-loprete-post-repair-final.png`; il profilo processuale mostra cliente, parte/soggetto, soggetti e parti, ufficio reale, giudice, RG, evento e udienza;
- Scadenziario desktop: screenshot `C:\Users\antmm\AppData\Local\Temp\iusentra-scadenziario-loprete-post-repair-hover.png`; la riga LOPRETE è leggibile, contiene udienza, ufficio, giudice, evento e attività operativa, senza `Ricevuta protocollo`, `Protocollo nr` o vecchi testi tecnici;
- Scadenziario mobile: screenshot `C:\Users\antmm\AppData\Local\Temp\iusentra-scadenziario-loprete-mobile-post-repair.png`; la card mobile conserva `Udienza: 09/07/2026 09:30` e non taglia i dati essenziali;
- Agenda dettaglio: screenshot `C:\Users\antmm\AppData\Local\Temp\iusentra-agenda-loprete-post-repair-final.png`; `/agenda/34E102D2` mostra cliente, parte/soggetto, ufficio, giudice, evento, udienza e `Attività per l'avvocato`;
- Fascicoli: screenshot `C:\Users\antmm\AppData\Local\Temp\iusentra-fascicoli-prossima-scadenza-post-repair.png`; la colonna `Prossima scad.` è presente e valorizza solo le scadenze collegabili in modo affidabile. I fascicoli non presenti nel tenant SQL reale o collegabili soltanto con RG ambiguo restano `n.d.`;
- Topbar notifiche: screenshot `C:\Users\antmm\AppData\Local\Temp\iusentra-topbar-notifiche-post-repair.png`; il pannello notifiche non mostra `ACCETTAZIONE DEPOSITO TELEMATICO`, `ESITO CONTROLLI AUTOMATICI DEPOSITO TELEMATICO`, `Ricevuta protocollo`, `Protocollo nr`, `Classifica PEC e conferma adempimenti` o `Presidio ricevute PEC`.

Limite operativo verificato sul tenant locale:

- la lista fascicoli locale contiene solo i fascicoli presenti nello SQLite reale del tenant, non tutte le righe mostrate nello screenshot utente storico; la nuova logica popola `Prossima scad.` quando trova ID, alias, RG univoco o RG più cliente/parte. Se la PEC è cancellata o non basta, il presidio documentale legge i testi indicizzati del fascicolo e crea/upserta l'evento operativo prima di far comparire la data.
## Fix invio deposito reale, Atto.enc base64 e corpo PEC 2.253.96 - 2026-06-23

Difetto reale corretto: nel click `Invia deposito reale` il Local Signer poteva ricevere un allegato `Atto.enc` non più base64 valido dopo la redazione JSON del payload, e la prova senza invio poteva restare al 92% quando il testo PEC arrivava da una bozza precedente non allineata ai nomi finali della busta.

Decisioni operative applicate:

- i campi payload binari `content_base64`, `contenuto_base64`, `base64`, `documento_b64`, `file_base64`, `firmato_b64` e `bytes_base64` non vengono più alterati dal redattore JSON tecnico;
- il backend accetta un corpo PEC modificato dall'avvocato solo se richiama `Atto.enc` e tutti i documenti operativi finali della busta;
- se il corpo PEC è vecchio o incompleto, il software lo rigenera automaticamente dai nomi finali effettivi del pacchetto;
- il controllo `Corpo PEC verificabile` confronta documento per documento tutto l'elenco operativo, non solo i primi file;
- anche il ramo `Invia deposito reale` restituisce il report di compatibilità collegato al pacchetto appena generato;
- l'invio resta sempre demandato al PC locale tramite Local Signer: il server prepara destinatario, oggetto, corpo, `Atto.enc` e payload, ma non usa SMTP server-side per depositi legali.

Prova reale locale su Docker utente:

- `docker compose up -d --build app scheduler-worker ocr-worker`;
- `http://127.0.0.1:8080/api/pronto` ha risposto `ok=true`, `versione=2.253.96`, app/scheduler/OCR healthy;
- browser integrato autenticato su `http://127.0.0.1:8080/fascicoli/DC5BF1DB/deposito/prepara#generazione-busta`;
- il testo PEC visibile contiene esattamente gli 8 documenti previsti: `attoACQ.pdf.p7m`, `Note trattazione scritta Alessi Robertino c Zurich Ass.ni-signed.pdf.p7m`, `perizia_r_ino_alessi__zurich_ass_ni.pdf.p7m`, `giudice_di_pace_di_palmi2.pdf.p7m`, `MEMORIA_CONCLUSIVA_ZURICH.pdf.p7m`, `Note conclusive Alessi Robertino.pdf.p7m`, `Istanza trattazione scritta Alessi Robertino.pdf.p7m`, `MOD. Inizio Attivita Peritali.pdf.p7m`;
- click reale su `Simula invio PEC`: barra di avanzamento visibile con i nomi dei documenti e `Atto.enc`; esito `compatibilità 100%`, `Atto.enc ministeriale AES256` OK, `Corpo PEC verificabile` OK, `Simulazione senza invio SMTP` OK;
- dopo la simulazione il pulsante `Invia deposito reale` è attivo;
- click reale su `Invia deposito reale` e conferma: la UI arriva alla finestra `Password PEC locale`, riepilogo allegato `Atto.enc`, testo `La password non viene salvata: viene inviata solo al Local Signer sul PC in uso per spedire il deposito`;
- la prova è stata annullata nella finestra password, quindi nessuna PEC reale è stata inviata;
- non è comparso l'errore `Allegato Atto.enc non e' base64 valido`.

Stato residuo: per il deposito reale operativo l'avvocato deve inserire la password PEC locale nella finestra Local Signer. Il software arriva al punto corretto con busta conforme, payload locale e allegato `Atto.enc` valido.

### Prova produzione Hetzner post-deploy 2.253.96 - 2026-06-23

Deploy Hetzner completato sul commit `7712169c3c6d5ba17a6138045f3d09c09fb513bf`, senza backup preventivo e con `IUSENTRA_SKIP_BACKUP_CRON=1`. Le run GitHub `Deploy Hetzner CPX42` sui branch `Codex/legal-electronic-filing-kIxcV` e `claude/legal-electronic-filing-kIxcV` sono verdi. Verifica diretta server: `/opt/iusentra/repo` punta allo stesso commit, container `app`, `scheduler-worker` e `ocr-worker` healthy, `https://app.iusentra.it/api/pronto` risponde `ok=true`, `versione=2.253.96`.

Nota sul fascicolo indicato dall'utente: l'URL `https://app.iusentra.it/fascicoli/E5AE4668/deposito/prepara#generazione-busta` apre React ma il server non trova quel record in SQL, quindi mostra `n.d.`, zero documenti e pulsanti bloccati. Query read-only su tutti i tenant PostgreSQL/SQLite di produzione: nessun tenant ha un fascicolo con `id=E5AE4668`. Per `Marchetti c. MIM`, `Carta docente`, `Tribunale di Vicenza`, il fascicolo SQL reale trovato sul tenant `studio-legale-giuseppe-montagnese` è `F08F92A2`, numero `2026/332`.

Prova reale produzione eseguita quindi su `https://app.iusentra.it/fascicoli/F08F92A2/deposito/prepara#generazione-busta`:

- pagina React reale con `#root`, `2026/332 - Marchetti Lucia`, `Tribunale di Vicenza`, canale `PCT lavoro / SICID`;
- PEC destinatario verificata: `tribunale.vicenza@civile.ptel.giustiziacert.it`, profilo deposito SQL e codice `0640011 / 0241160092`;
- 11 documenti operativi in busta, `DatiAtto.xml` generato, `IndiceDocumentiDepositati.PDF` generato, atto principale `Ricorso.pdf.p7m`, procura `Procura.PDF.p7m`;
- click reale su `Simula invio PEC`, conferma modal `senza spedire nulla all'esterno`, barra avanzamento con documenti e `Atto.enc`;
- esito `Compatibilità 100%`, `Atto.enc ministeriale AES256` OK, `DatiAtto.xml presente` OK, `IndiceDocumentiDepositati.PDF` OK, `Atto principale e allegati controllati` OK, `PEC ufficio giudiziario` OK, `Oggetto PEC deposito` OK, `Corpo PEC verificabile` OK, `Simulazione senza invio SMTP` OK;
- il corpo PEC è stato rigenerato sui nomi finali effettivi: `DatiAtto.xml`, `Ricorso.pdf.p7m`, `Autocertificazione ricorso_63ee.PDF`, `Autocertificazione situazione reddituale_ff33.PDF`, `Carta Identità e C.F. Lucia Marchetti_d157.PDF`, `Contratto 24-25_81a0.pdf`, `Contratto Rossi 2025-2026_b301.pdf`, `Lettera di diffida Carta Docenti Marchetti Lucia_6df3.pdf`, `Procura.PDF.p7m`, le tre email con suffisso hash e `IndiceDocumentiDepositati.PDF`;
- dopo la simulazione `Invia deposito reale` è attivo;
- click reale su `Invia deposito reale` e conferma: il flusso arriva a `Invia dal PC locale` / password PEC locale, con `Atto.enc` nel payload locale e senza errore `Allegato Atto.enc non e' base64 valido`;
- prova annullata senza inserire password PEC: nessuna PEC reale inviata.

## Deposito firma selettiva e Simula PEC ministeriale 2.253.98 - 2026-06-23

Difetto reale corretto: la UI React del deposito poteva trasformare il vecchio `statusLabel` descrittivo del documento, per esempio `Da firmare`, in obbligo di firma nella busta. Questo poteva far apparire tutti gli allegati come documenti da firmare, allontanando il flusso dal problema reale segnalato dal PST (`Codice esito -1`, `Indice busta non trovato`).

Decisioni operative applicate:

- l'obbligo di firma deriva solo da ruolo ministeriale selezionato (`Atto principale`, `Procura alle liti`) o da richiesta esplicita di firma obbligatoria, non dal testo storico `Da firmare`, `Non firmato` o `Senza firma`;
- i file già in contenitore CAdES/PKCS#7 (`.p7m`, `.sig`, `.pkcs7`) non vengono rifirmati e possono mostrare `Firmato` solo se il backend ha prova tecnica;
- `Invia tutto` include i documenti in busta ma non imposta automaticamente la firma obbligatoria sugli allegati facoltativi;
- il contatore `Firma software` mostra i soli documenti che saranno davvero firmati prima della busta, non tutti i candidati non firmati;
- `DatiAtto.xml` viene presentato come metadato ministeriale della busta, non come allegato da scegliere; se la firma multipla ha già aperto una sessione PIN Local Signer, la firma tecnica di `DatiAtto.xml` riusa `pin_session_id`;
- il riepilogo busta indica documento per documento se la firma è già presente, obbligatoria, richiesta o non necessaria;
- il pulsante `Simula invio PEC` resta il controllo di confezionamento ministeriale: prima della PEC verifica `DatiAtto.xml.p7m`, `IndiceBusta.xml`, `IndiceDocumentiDepositati.PDF`, `Atto.enc` CMS/PKCS#7 `EnvelopedData` AES256, PEC destinatario, oggetto, corpo PEC e piano ricevute, senza invio SMTP reale.

Stato tecnico prima del deploy:

- test mirati React deposito e busta PCT aggiornati e verdi;
- build React `pnpm --filter @iusentra/studio build` completata;
- versione portata a `2.253.98`;
- prova visiva server richiesta dall'utente da eseguire dopo deploy su `https://app.iusentra.it/fascicoli/F08F92A2/deposito/prepara`.

## Deposito firma CAdES su documenti cifrati a riposo 2.253.99 - 2026-06-23

Difetto reale visto in produzione dopo il deploy `2.253.98`: sul fascicolo `F08F92A2` (`Marchetti Lucia`, Tribunale di Vicenza) la pagina React mostrava correttamente `Ricorso.pdf.p7m` come firmato, ma il click reale su `Simula invio PEC` bloccava la busta con `Atto principale non firmato digitalmente`.

Causa tecnica verificata: sul server i documenti del fascicolo sono cifrati a riposo con intestazione `PCTENC`. Il validator della simulazione e il payload React leggevano direttamente i byte cifrati invece del contenuto decifrato; quindi un contenitore CAdES valido veniva bocciato come non firmato. La verifica manuale sul server ha confermato che, dopo `decrypt_doc`, `Ricorso.pdf.p7m` è un PKCS#7/CAdES valido.

Decisioni operative applicate:

- la validazione firma del deposito decifra sempre i byte del documento prima di verificare CAdES/PAdES;
- il payload React dei documenti usa la stessa prova tecnica, così `Firmato` e il blocco busta leggono la stessa verità;
- i metadati storici non possono far passare un `.p7m` se il contenitore CAdES reale non è verificabile;
- per PAdES o metadati tecnici non-container resta ammesso il fallback governato già previsto;
- la route di classificazione deposito salva le scelte anche quando il profilo pratica deve ancora essere confermato, senza perdere la proposta busta.

Stato tecnico prima del deploy:

- test mirato aggiunto per `.p7m` CAdES salvato cifrato a riposo e poi letto dalla API React;
- test deposito/busta mirati confermati verdi;
- build React confermata;
- versione portata a `2.253.99`;
- prova visiva produzione da ripetere dopo deploy sullo stesso fascicolo `F08F92A2`, verificando che `Simula invio PEC` non mostri più `Atto principale non firmato digitalmente`.

## Deposito validator busta su CAdES cifrato 2.253.100 - 2026-06-23

La prova reale produzione su `2.253.99` ha mostrato che il fix era presente in payload React e runtime fascicoli, ma non ancora nel validator effettivo dell'orchestratore `pct/deposito_guidato.py`: il blocco `Atto principale non firmato digitalmente` restava attivo durante `Simula invio PEC`.

Correzione applicata:

- anche `_document_has_verified_signature()` dell'orchestratore decifra il file con `decrypt_doc()` prima di verificare CAdES/PAdES;
- se la decifratura fallisce, il validator resta bloccante e non usa il flag storico `firmato`;
- aggiunto test specifico sull'orchestratore con `Ricorso.pdf.p7m` CAdES valido, salvato cifrato a riposo con `PCT_DOC_KEY`, per impedire la regressione del caso visto su `F08F92A2`.

Stato tecnico prima del deploy:

- test orchestratore CAdES non valido / CAdES reale / CAdES cifrato a riposo verdi;
- test API React documenti firmati cifrati verdi;
- test busta/PEC mirati verdi;
- versione portata a `2.253.100`;
- prova visiva produzione da ripetere dopo deploy, con chiusura del vecchio alert e nuova simulazione sul fascicolo `F08F92A2`.

## Deposito simulazione PEC e firma DatiAtto senza modali sovrapposte 2.253.101 - 2026-06-23

Difetto reale visto nella prova produzione `2.253.100`: il vecchio blocco `Atto principale non firmato digitalmente` non compariva più, quindi il validator CAdES cifrato era corretto. La UI però manteneva ancora aperto il modal di conferma della simulazione (`Operazione...`) mentre richiedeva il PIN per firmare `DatiAtto.xml`, creando due stati visivi sovrapposti e impedendo una prova chiara del confezionamento.

Correzione applicata:

- quando la route restituisce `requires_local_signature`, il componente React `DepositActionButton` chiude subito la conferma iniziale prima di aprire il passaggio Local Signer;
- la progress bar del pacchetto resta attiva e continua a mostrare i file in lavorazione (`DatiAtto.xml`, `DatiAtto.xml.p7m`, `IndiceBusta.xml`, `IndiceDocumentiDepositati.PDF`, documenti e `Atto.enc`);
- il modal PIN di `DatiAtto.xml` continua a chiudersi prima della chiamata al Local Signer e non salva il PIN;
- non sono state cambiate le regole di firma dei documenti: gli allegati non diventano obbligatori per effetto del vecchio testo `Da firmare`, e `Firmato` resta ammesso solo con prova tecnica CAdES/PAdES.

Stato tecnico prima del deploy:

- guardrail React aggiornato per verificare che il modal di conferma si chiuda prima della firma locale di `DatiAtto.xml`;
- versione portata a `2.253.101`;
- prova visiva produzione da ripetere su `https://app.iusentra.it/fascicoli/F08F92A2/deposito/prepara#generazione-busta`, verificando simulazione PEC, firma `DatiAtto.xml`, generazione `IndiceBusta.xml`/`Atto.enc` e assenza del vecchio alert sull'atto principale.

## Deposito PEC locale e username SMTP separato 2.253.102 - 2026-06-24

Difetto segnalato in prova reale: durante il click su `Invia deposito reale` la UI riportava `Autenticazione SMTP PEC non riuscita. Verifica indirizzo, username e password.` Il messaggio nasce dal Local Signer sul PC in uso, non dal server, ma era ambiguo e il payload del deposito usava sempre l'indirizzo PEC come username SMTP.

Correzione applicata:

- `ConfigPEC` ora conserva anche `username` opzionale, mantenuto in fondo alla dataclass per non rompere gli usi posizionali storici;
- Impostazioni React mostra e salva `Username PEC` solo come dato opzionale, da compilare quando il provider richiede un login diverso dall'indirizzo PEC;
- il test `Verifica invio PEC` su `/impostazioni?tab=pec`, il guard runtime e il payload deposito usano lo stesso username: se configurato viene passato al Local Signer, altrimenti resta l'indirizzo PEC;
- il mittente PEC (`from` / `indirizzo`) resta separato dallo username di autenticazione SMTP;
- il modal di invio reale mostra anche `Username SMTP locale`, così prima della password è visibile quale login verrà usato dal PC locale;
- il messaggio di autenticazione fallita ora dichiara esplicitamente che l'errore è locale: l'invio parte dal PC in uso tramite Local Signer;
- la route deposito continua a non spedire SMTP dal server: senza `local_pec_confirmed=1` restituisce `requires_local_pec`; registra il deposito solo dopo Message-ID confermato dal Local Signer.

Stato anti-regressione:

- test mirati Local Signer PEC aggiornati per username separato e messaggio di autenticazione locale;
- test React impostazioni PEC aggiornati per impedire il ritorno a verifica SMTP server-side;
- test React deposito aggiornato per mostrare lo username SMTP locale nel modal di invio reale;
- resta vietato usare lo SMTP server-side per depositi, notifiche legali e invii PEC operativi.

## Deposito reale dopo prova senza invio persistita 2.253.103 - 2026-06-25

Difetto reale rilevato su produzione: nella pagina React `Prepara deposito` il fascicolo mostrava una ricevuta `PROVA SENZA INVIO`, PEC ufficio verificata, documenti in busta, `DatiAtto.xml`, `IndiceDocumentiDepositati.PDF` e corpo PEC presenti, ma il pulsante `Invia deposito reale` restava disabilitato con tooltip `Esegui prima la prova senza invio reale.`.

Correzione applicata:

- il prerequisito UI della prova senza invio ora riconosce anche una prova già persistita nel fascicolo, tramite deposito marcato come simulato o stato/messaggio `prova senza invio`;
- la prova persistita non viene mai trattata come invio valido e non registra ricevute reali;
- al click su `Invia deposito reale` il software rigenera comunque classificazione, firme richieste, `DatiAtto.xml.p7m`, `IndiceBusta.xml`, `Atto.enc` CMS/PKCS#7 AES256 e corpo PEC;
- l'invio reale continua a fermarsi prima dello SMTP server-side e richiede sempre `requires_local_pec`/Local Signer sul PC locale, con password inserita al momento;
- se la prova non esiste, oppure se manca PEC ufficio, Atto.enc conforme, PEC mittente locale o altro requisito obbligatorio, il pulsante resta bloccato o il backend restituisce il requisito preciso.

Stato anti-regressione:

- aggiunto guardrail React perché `Invia deposito reale` usi `packageReadyForRealSend`, cioè preview corrente oppure prova senza invio persistita;
- il guardrail conserva il divieto di `packageConfirmedForReal` manuale e il divieto di invio SMTP dal server;
- prova visiva da ripetere dopo build/deploy su `https://app.iusentra.it/fascicoli/795C50AC/deposito/prepara#generazione-busta`: con `Ricevute 1 PROVA SENZA INVIO`, il pulsante reale deve risultare cliccabile e, al click, deve aprire la richiesta password PEC locale/Local Signer oppure indicare un requisito tecnico mancante puntuale.

## Simula invio PEC: firma DatiAtto.xml e certificato Windows di firma 2.253.105 / Local Signer 1.6.80 - 2026-06-25

Difetto reale segnalato nel click `Simula invio PEC`: prima della simulazione il frontend riceveva `requires_local_signature` e chiedeva al Local Signer di firmare `DatiAtto.xml`; il Local Signer entrava nel ramo Windows Certificate Store e PowerShell restituiva l'errore tecnico `ComputeSignature` con codice `-1073741275`. Nessuna PEC veniva inviata, ma il messaggio grezzo rendeva la fase inutilizzabile.

Distinzione operativa:

- il rifiuto ministeriale `Indice busta non trovato` riguarda la presenza di `IndiceBusta.xml` dentro `Atto.enc`;
- l'errore `ComputeSignature` riguarda la firma locale CAdES di `DatiAtto.xml`, necessaria per creare poi `IndiceBusta.xml` e `Atto.enc`;
- i due problemi sono collegati nella sequenza del deposito, ma non hanno la stessa causa.

Correzione applicata:

- Local Signer `1.6.80` separa il certificato Windows usato per autenticazione PST dal certificato Windows usato per firma CAdES;
- per firmare `DatiAtto.xml` vengono esclusi certificati con indizi `auth`, `autenticazione`, `authentication`, `client`, `web`, `login` e viene preferito un certificato di firma qualificata;
- la risposta `/ping` espone `certificato_windows_firma_selezionato`; la UI React lo usa prima del vecchio `certificato_windows_selezionato`;
- la PowerShell di firma Windows Store non viene più lanciata come subprocess nascosto, così eventuali prompt PIN/driver possono apparire sul PC reale;
- l'errore `ComputeSignature` viene trasformato in un messaggio operativo: firma Windows non completata dal provider del token, verificare certificato di firma qualificata, prompt PIN e token; nessuna PEC inviata.

Guardrail anti-regressione:

- test Local Signer per impedire che un certificato `AUTENTICAZIONE WEB` venga scelto come certificato di firma;
- test Local Signer per impedire il ritorno alla firma Windows nascosta;
- test Local Signer per impedire la ricomparsa dello stack PowerShell grezzo nel messaggio utente;
- test React per assicurare che il frontend preferisca `certificato_windows_firma_selezionato`;
- `Simula invio PEC` deve restare senza SMTP reale: prepara/firma metadato, genera `IndiceBusta.xml`, `IndiceDocumentiDepositati.PDF`, `Atto.enc`, corpo PEC e report di compatibilità, ma non spedisce PEC.

Aggiornamento reale `1.6.80`: dopo installazione sulla macchina locale, `/ping?auto=1` su `127.0.0.1:27272` conferma token Bit4id presente, libreria `C:\Windows\System32\bit4xpki.dll`, certificato di autenticazione separato e certificato di firma qualificata `GIUSEPPE MONTAGNESE` esposto come `certificato_windows_firma_selezionato`. La chiamata reale `/firma` su un metadato minimo `DatiAtto.xml` non produce più lo stack `ComputeSignature`; il provider PKCS#11 restituisce `PinLocked` e il Local Signer risponde in JSON con messaggio operativo `PIN del dispositivo di firma bloccato... Nessuna PEC è stata inviata.`. Nessuna PEC è stata inviata durante la prova. La firma reale resta fisicamente bloccata finché il dispositivo dell'avvocato non viene sbloccato con procedura del fornitore/PUK.

Guardrail aggiunto in `1.6.80`: gli errori PKCS#11 vuoti o tecnici (`PinIncorrect`, `PinLocked`, token assente, sessione scaduta) vengono trasformati in messaggi operativi non vuoti; la UI React legge anche risposte Local Signer testuali, non solo JSON, per non perdere il messaggio reale nel click `Simula invio PEC`, firma multipla, firma singola o invio PEC locale.

## PAT / SIGA - struttura XFA ministeriale e compilazione moduli 4.x - 2026-06-23

Obiettivo operativo: IUSENTRA deve preparare il deposito PAT dentro il software e lasciare il portale ufficiale SIGA/Formweb solo come fase finale di consegna. Il modulo non deve essere ricostruito con un layout imitato: il PDF prodotto deve restare il modello ministeriale originale, con i valori scritti nei campi XFA ufficiali.

Correzione strutturale applicata:

- aggiunto estrattore XFA dei moduli PAT ufficiali in `pct/pat_xfa_schema.py`;
- il catalogo PAT espone per ogni modulo il numero di campi XFA, controlli compilabili, azioni ministeriali e gruppi ripetibili;
- la UI React `TelematicoSurfacePage` costruisce dinamicamente le sezioni operative in base al modulo selezionato: sede, ricorso, atti, documenti, notifiche, parti, campi flag/radio/select e gruppi con `Aggiungi riga`;
- i percorsi tecnici XFA restano fuori dalla vista operativa e non vengono mostrati all'avvocato;
- la rotta `/api/v1/ui/pat/moduli/compila` accetta `xfaValues` e li passa al compilatore PDF;
- il compilatore `pct/pat_pdf_templates.py` scrive valori su path XFA esatti, clona le righe ripetibili indicizzate e gestisce radio, checkbox e select;
- corretta la scrittura delle select XFA: ora usa i valori `save="1"` del modello ministeriale, quindi ad esempio `TAR Lazio - Roma` viene scritto come `tar_rm` e non resta sul default `tar_bz`;
- corretto il resolver dei path XFA quando il modello contiene sottoform fratelli con lo stesso nome: il compilatore segue il ramo che contiene davvero il campo successivo e usa l'indice solo quando il path lo richiede;
- la UI distingue i campi tecnici del PDF dai campi operativi compilabili dall'avvocato;
- il modulo Excel parti resta catalogato come supporto dati, non come PDF XFA.

Copertura tecnica dei moduli ufficiali presenti in `pct/data/pat_moduli`:

- `ModuloDepositoRicorso_4.02.pdf`: 210 campi XFA grezzi, 107 campi operativi, 54 tecnici, 35 azioni;
- `ModuloDepositoAtto_4.02.pdf`: 188 campi XFA grezzi, 105 campi operativi, 35 tecnici, 30 azioni;
- `ModuloDepositoRichiesteSegreteria_4.01.pdf`: 110 campi XFA grezzi, 57 campi operativi, 19 tecnici, 23 azioni;
- `ModuloDepositoPerAusiliariDelGiudiceEPartiNonRituali_4.01.pdf`: 101 campi XFA grezzi, 54 campi operativi, 18 tecnici, 21 azioni;
- `ModuloDepositoIstanza_4.01.pdf`: 150 campi XFA grezzi, 85 campi operativi, 25 tecnici, 27 azioni;
- `ModuloDepositoRimborso_4.01_2026.pdf`: 77 campi XFA grezzi, 55 campi operativi, 11 tecnici, 11 azioni;
- `FoglioExcelParti_2025.xlsx`: 5 colonne operative, senza XFA.

Verifiche automatiche eseguite:

- `python -m pytest -q tests\test_canali_telematici_deposito.py::test_pat_siga_catalogo_moduli_e_formweb_da_fonti_ufficiali tests\test_react_shell.py::test_react_pat_modulo_compilabile_produce_pdf tests\test_react_shell.py::test_react_pat_modulo_atto_compila_path_xfa_e_righe_aggiunte tests\test_react_shell.py::test_react_superfici_telematiche_api_payload_reale --tb=short`;
- `python -m pytest -q tests\test_react_shell.py::test_react_pat_moduli_ufficiali_scrivono_tutti_i_campi_xfa_operativi --tb=short`;
- `python -m pytest -q tests\test_canali_telematici_deposito.py::test_pat_siga_catalogo_moduli_e_formweb_da_fonti_ufficiali tests\test_react_shell.py::test_react_pat_modulo_compilabile_produce_pdf tests\test_react_shell.py::test_react_pat_modulo_atto_compila_path_xfa_e_righe_aggiunte tests\test_react_shell.py::test_react_pat_moduli_ufficiali_scrivono_tutti_i_campi_xfa_operativi tests\test_react_shell.py::test_react_superfici_telematiche_api_payload_reale --tb=short`;
- `pnpm --filter @iusentra/studio typecheck`;
- `pnpm --filter @iusentra/studio build`;
- `docker compose up -d --build app`;
- `http://127.0.0.1:8080/api/pronto` ha risposto `ok=true`, `versione=2.253.101`.

Nota sul test campo-per-campo: `test_react_pat_moduli_ufficiali_scrivono_tutti_i_campi_xfa_operativi` attraversa tutti i moduli PDF ufficiali, genera valori coerenti per campi testo, data, documento, select, checkbox e radio, compila il PDF ministeriale originale e rilegge il template XFA prodotto. Il test copre anche almeno una seconda riga per ogni gruppo ripetibile con path indicizzato, quindi blocca regressioni sui pulsanti `Aggiungi`.

Prova reale locale eseguita su `http://127.0.0.1:8080/pat` nel browser integrato:

- selezione `Modulo PDF deposito atto` visibile con conteggio `ModuloDepositoAtto_4.02.pdf: 188 campi XFA, 105 campi operativi, 30 azioni ministeriali`;
- sezioni operative visibili e ordinate: `Sede`, `Ricorso`, `Atti di causa`, `Documenti di causa`, sezioni parti/notifica richiudibili;
- sezione tecnica `Intestazione modulo` chiusa di default;
- click reale su `Aggiungi riga`: la UI passa da una a due righe e abilita `Rimuovi riga`;
- compilati in UI i dati `Speranza Carmelina`, `tar_rm`, `2026`, `1480`, `Istanza cautelare`, `222050 - Retribuzione`;
- click reale su `Genera modulo ufficiale`: la UI mostra `Modulo ministeriale XFA compilato` e il link `ModuloDepositoAtto_4.02_compilato_iusentra.pdf`;
- hover reale su `Aggiungi riga`, `Genera modulo ufficiale` e `Avvia SIGA`: testo leggibile, contrasto professionale, nessun salto dimensionale;
- responsive reale controllato su tablet `768x1024` e mobile `390x844`: nessun overflow orizzontale, pulsanti ripetibili non tagliati, nessun path XFA tecnico visibile nella superficie operativa.

Limite residuo da non dichiarare chiuso: il PDF generato dopo il fix è stato verificato via generatore backend e test XFA sui byte, ma non è ancora stato aperto davanti all'utente in Acrobat Reader con ispezione visiva campo per campo. Prima di dichiarare copertura PAT 100% servono ancora matrice modulo/campo obbligatorio/percorso XFA/campo IUSENTRA/dato DB/prova PDF/prova visiva Acrobat e prova reale su tutti i moduli, inclusi radio, checkbox, select e gruppi `Aggiungi`.

## OCR comune per PEC, notifiche e deposito - 2.253.118 - 2026-06-25

Richiesta utente: PEC, notifiche e deposito devono dipendere dalla stessa pipeline OCR nuova, così i dati riportati nei fascicoli, nella busta e nella conoscenza Lex AI non divergono.

Correzione applicata:

- `pct.ocr.estrai_testo` non è più un percorso OCR separato: per PDF e immagini delega prima a `pct.document_intelligence.extraction.extract_text_from_document`, quindi usa Unlimited-OCR quando self-hosted e pronto, oppure il fallback locale ibrido governato;
- `pct.pec_pipeline.extract_text_with_coverage` continua a usare `pct.ocr.estrai_testo`, ma ora passa dall'adapter comune e non da una lettura PDF parallela;
- il recupero documentale per notifiche/scadenze/agenda da fascicolo usa già `DocumentAIService.process_lex_indexing_sources` e quindi la stessa estrazione Document AI;
- il flusso React `Prepara deposito`, indice documenti e controlli documentali leggono i testi Document AI indicizzati del fascicolo: non devono reintrodurre OCR diretto o parser PDF non governati;
- se Unlimited-OCR non è configurato, il sistema non dichiara un risultato Baidu finto: usa fallback locale e warning, mantenendo testo completo, pagine, hash e manifest come sorgente per Lex AI.

Stato anti-regressione:

- `tests/test_ocr_pipeline_adapter.py` presidia la delega da `pct.ocr.estrai_testo` a Document AI e il supporto path locale;
- `tests/test_ocr_pipeline_adapter.py` presidia anche la configurazione Tesseract locale senza `--tessdata-dir` quotato, dopo la prova reale su `Sentenza_3080731.pdf`, `depositoMinutaSentenzaSemplificata.pdf`, `attoACQ.pdf` e `attoACQ.pdf.p7m`;
- `tests/test_pec_audit_pipeline.py::test_extract_text_with_coverage_pdf_usa_adapter_ocr_pipeline` blocca il ritorno della PEC a un OCR parallelo;
- `tests/test_pec_audit_pipeline.py::test_presidio_documentale_lex_recupera_udienza_termine_e_metadati_rag` conferma il percorso Document AI usato per recupero udienze/scadenze;
- verifica reale locale eseguita sul browser integrato dopo rebuild Docker `2.253.118`: `/email` e `/notifiche-legali` aprono superfici React senza errori; `/fascicoli/DC5BF1DB/deposito/prepara` mostra `RG 466/2023 - Alessi Robertino`, `20` documenti nel fascicolo, `8` documenti in busta e indice generato dal software in tempo reale.

## Certificati PST `.cer` e job reali scheduler - 2026-06-25

Durante il gate operativo `2.253.108` il controllo reale dei job ha bloccato il rilascio su `pst_certificati_cifratura_weekly`: il worker era vivo, ha eseguito il job, ma il report ha restituito `errori=1` per il codice ministeriale `0651160115` (`Tribunale per i Minorenni-Salerno`) perché il certificato in cache era scaduto.

Correzione applicata:

- se un `.cer` in cache è valido, il job può usarlo senza forzare il download remoto;
- se un `.cer` in cache è scaduto, non ancora valido o illeggibile, il resolver non si ferma più sulla cache e tenta subito il refresh remoto mirato dal PST;
- se anche il refresh remoto non produce un certificato valido, il job resta bloccante e deve indicare codice ufficio e causa puntuale;
- le run manuali richieste dal registro scheduler salvano il payload reale del job, non solo una stringa di sintesi;
- il gate `scripts/check_runtime_services.py` non considera più sufficiente lo stato `running` per il job obbligatorio: serve `completed` con riepilogo operativo.

Prova reale locale su Docker `127.0.0.1:8080`, versione `2.253.108`:

- run worker PST precedente: `failed`, causa `Il certificato di cifratura PST per l'ufficio 0651160115 è scaduto.`;
- refresh mirato del codice `0651160115`: nuovo certificato PST valido fino al `18/06/2029`;
- run worker PST successiva: `completed`, `scaricati_o_validi=593`, `errori=0`, `cache_cer_presenti=913`;
- gate worker Lex successivo: `lex_sentenza_economia_auto` `completed` con `errors=0` e `vector_embedding_errors=0`.

Regola operativa da mantenere: la cache tecnica `.cer` è una risorsa valida solo se il certificato è temporalmente valido e utilizzabile per cifratura; un singolo ufficio con certificato scaduto non deve essere mascherato come successo globale, ma deve essere rinfrescato o indicato come blocco puntuale per quell'ufficio/canale.

## Presidio PEC e job incrementali comuni - 2.253.117 - 2026-06-25

Il presidio PEC alimenta scadenziario, agenda, notifiche, Web Push, fascicoli, Lex AI e controlli di deposito. Per questo non deve diventare un ciclo pesante che rilegge tutta la casella a ogni run.

Correzione applicata:

- `pec_audit_pipeline_workers` mantiene i lotti piccoli, ma ora salva anche un cursore operativo nel repository PEC audit;
- dopo il bootstrap e l'esaurimento dell'arretrato, il worker acquisisce solo PEC nuove e la boundary di sicurezza, lasciando i job già accodati alla coda `pec_jobs`;
- se il batch si riempie, il cursore non avanza: il giro successivo riprende la stessa finestra, scarta ciò che è già presidiato e lavora gli arretrati rimasti;
- il risultato espone `scan_mode` (`bootstrap`, `incremental`, `incremental_backlog`), `archive_seen`, `scanned`, `cursor_saved`, così il gate può distinguere un worker realmente incrementale da una scansione completa;
- la full scan PEC è consentita solo con `IUSENTRA_PEC_AUTO_ACQUIRE_FULL_SCAN=1`;
- `lex_sentenza_economia_auto` usa la stessa disciplina sui Document AI: legge il cursore `mtime_ns` dall'ultimo run completato nel registro scheduler e apre solo `extracted_text.json` modificati dopo quel valore;
- la full scan Lex Sentenze è consentita solo con `IUSENTRA_SENTENZA_LEX_FULL_SCAN=1`;
- il gate runtime deve accettare run incrementali senza nuovi documenti (`documents_seen=0`) se il riepilogo operativo esiste e `errors=0`, `vector_embedding_errors=0`;
- `pec_audit_pipeline_workers`, `mailbox_sync_runtime`, `calendar_sync_engine_retry` e `local_ai_maintenance` restituiscono ora un report scheduler con `scan_mode`, `totals`, stato del tenant e motivi di skip/errore;
- `scripts/check_runtime_services.py --require-all-due-jobs` blocca i job operativi frequenti completati senza `totals` oppure con errori nel riepilogo, quindi il rilascio non può passare con worker vivi ma opachi.

Guardrail eseguiti prima del deploy:

- `python -m pytest tests\test_pec_auto_acquire.py tests\test_backfill_sentenza_lex_economics.py tests\test_scheduler.py tests\test_runtime_service_checks.py tests\test_pec_audit_pipeline.py tests\test_scheduler_worker.py tests\test_scheduler_registry.py -q --tb=short`;
- `python tools\sync_packaging_files.py --check`;
- `python scripts\validate_openapi.py docs\openapi.yaml`;
- `python -m pytest tests\test_pec_auto_acquire.py tests\test_backfill_sentenza_lex_economics.py tests\test_scheduler.py tests\test_runtime_service_checks.py -q --tb=short`;
- `git diff --check -- pct\incremental_jobs.py pct\pec_pipeline.py web\services\pec_pipeline_runtime.py scripts\backfill_sentenza_lex_economics.py pct\scheduler.py pct\scheduler_registry.py scripts\check_runtime_services.py tests\test_pec_auto_acquire.py tests\test_backfill_sentenza_lex_economics.py tests\test_scheduler.py tests\test_runtime_service_checks.py`.

Stato residuo: codice e test locali sono verdi, ma la consegna non è chiusa finché Docker locale reale e Hetzner non mostrano run `completed` dei worker sullo stesso commit, senza `missed` per istanza precedente ancora in corso.

## Catalogo documenti fascicolo e slot deposito - 2.253.119 - 2026-06-26

Richiesta utente: migliorare il catalogo nel fascicolo leggendo i PDF presenti, correggere i documenti che risultano atti ma non lo sono, usare la logica sempre sui fascicoli esistenti e futuri, e ricordare che `Ricorso` è sempre atto principale.

Correzione applicata:

- il nuovo classificatore `pct.fascicolo_document_catalog` legge nome file, tipo storico e testo OCR/Document AI integrale del fascicolo;
- il flusso non introduce OCR sincrono nella UI e non crea chunk per catalogare: usa il testo completo già indicizzato dal worker OCR/Document AI;
- `Ricorso` è classificato sempre come `atto_principale`, con `TipoDocumento.RICORSO`, sezione `atti`, ruolo deposito `atto_principale` e priorità nello slot principale;
- sentenze, ordinanze, decreti, verbali, CU/PagoPA, comunicazioni, richieste di visibilità, allegati e produzioni documentali non vengono più ammessi nello slot principale solo perché un tipo storico li chiamava genericamente `ATTO_GIUDIZIARIO`;
- il bridge React dei fascicoli espone il catalogo alla UI e alla lista documenti da inviare: `catalogRole`, `catalogLabel`, `catalogSection`, `catalogConfidence`, `catalogEvidence`, `depositRole`, `depositCandidate`;
- `frontend/src/components/FascicoliPage.tsx` usa `catalogSection` per ordinare i documenti e aggiunge la sezione `Pagamenti e contributi`;
- `pct.practice_engine.deposit_readiness` usa il catalogo per collegare gli slot: il principale accetta Ricorso/atto difensivo coerente e respinge provvedimenti, contributi, comunicazioni e allegati non principali;
- la rotta `/api/v1/ui/fascicoli/<id_fasc>/deposito/classifica-documenti` applica la stessa regola lato server: se il client prova a salvare come `atto_principale` un documento classificato con alta confidenza come non principale, il ruolo viene ricondotto a procura/prova notifica/fuori busta/allegato secondo il catalogo;
- lo script `scripts/reclassify_fascicolo_document_catalog.py` corregge i fascicoli esistenti usando SQLite/PostgreSQL come fonte di verità e report JSON come evidenza tecnica.

Prova locale su dati reali:

- dry-run `document-catalog-reclassify-local-dry-run-20260625.json`: `source_of_truth=sqlite`, `fascicoli_seen=7`, `documents_seen=75`, `documents_with_ocr_text=75`, `reclassified=26`, `wrong_atti_fixed=16`, `errors=0`;
- apply `document-catalog-reclassify-local-apply-20260625.json`: applicate le stesse riclassificazioni sulla copia SQLite locale;
- i tipi specifici già attendibili non sono stati sostituiti da inferenze generiche: `skipped_specific=45`.

Guardrail automatici:

- `tests/test_fascicolo_document_catalog.py` copre Ricorso come atto principale, provvedimenti non principali, CU/PagoPA, iniziali `C.U.`, match Document AI per hash e script di riclassificazione;
- `tests/test_practice_engine_validators.py` copre lo slot deposito: una sentenza storicamente etichettata `ATTO_GIUDIZIARIO` non viene più agganciata come atto principale, mentre la procura resta agganciabile allo slot corretto;
- la suite mirata OCR/Lex/PEC/deposito è passata al 100% prima del rebuild Docker.

Stato residuo prima della chiusura: prova reale nel browser integrato su `127.0.0.1:8080` dopo rebuild Docker `2.253.119`, poi deploy Hetzner, applicazione della ricatalogazione su `/data` produzione e verifica server con fascicoli reali.

Aggiornamento prova reale locale 26/06/2026, ore 02:14 Europe/Rome:

- Docker locale reale `2.253.119` ricostruito con `docker compose build --no-cache app scheduler-worker ocr-worker` e riavviato con `docker compose up -d --force-recreate app scheduler-worker ocr-worker`;
- `/api/pronto` ha risposto `ok=true`; `app`, `scheduler-worker` e `ocr-worker` risultano healthy;
- il gate `python scripts\check_runtime_services.py --wait-job-seconds 900 --require-all-due-jobs` ha atteso `lex_sentenza_economia_auto` `completed` alle `2026-06-26T00:07:15Z`, con `documents_catalogued=667`, `skipped_by_cursor=667`, `errors=0`, `vector_embedding_errors=0`; `pec_audit_pipeline_workers` ha completato senza errori;
- browser integrato visibile su `http://127.0.0.1:8080/fascicoli/DC5BF1DB#documenti`: il fascicolo `RG 466/2023 - Alessi Robertino` mostra `20` documenti, tutti pronti, nessun documento in coda/errore;
- nel catalogo fascicolo i file `note_di_trattazione_scritta_ZURICH_udienza_del_19-03-2025.pdf.p7m`, `note_di_trattazione_scritta_ZURICH_udienza_del_10-07-2024.pdf.p7m` e `istanza_per_fissazione_di_udienza_in_trattazione_scritta.pdf.p7m` sono in `Atti e memorie` con badge `Atto difensivo`, non piu' `Verbale`;
- `verbaleAttoGenerico.pdf` resta in `Provvedimenti` come `Verbale`;
- `attoACQ.pdf.p7m` e' in `Pagamenti e contributi` come `Contributo unificato / pagamento`;
- browser integrato visibile su `http://127.0.0.1:8080/fascicoli/DC5BF1DB/deposito/prepara#proposta-busta`: la proposta mostra `Tutto fascicolo 20 letto integralmente`, `Candidati busta 18`, `4 firmati`, `Atti principali 9 da confermare` e `Catalogo portale 50 separato dalla busta`;
- dopo ricarica dell'asset React aggiornato, le righe busta mostrano il ruolo tecnico `Allegato` ma con etichetta catalogo leggibile: `attoACQ.pdf.p7m` -> `Contributo unificato / pagamento (allegato busta)`, note/istanza -> `Atto difensivo (allegato busta)`, `verbaleAttoGenerico.pdf` -> `Verbale (allegato busta)`;
- il selettore ruolo della riga `attoACQ.pdf.p7m` riceve focus, resta leggibile e non modifica dati se aperto/chiuso senza selezione; lo scroll completo raggiunge `Dati fascicolo`, `Slot documentali` e `Audit`;
- verifica responsive reale con viewport `1280x900`, `768x900` e `390x844`: nessun overflow orizzontale, testi lunghi leggibili, badge e controlli non tagliati, console browser senza errori.

Stato ancora aperto prima della chiusura globale: commit/push dei branch gemelli, check GitHub/CodeQL, deploy Hetzner, applicazione ricatalogazione e reset/backfill importi su produzione, verifica `https://app.iusentra.it/api/pronto` e prova server con fascicoli reali.

## Prova reale deposito PCT Vicenza e controllo conformità tecnica - 2.253.121 - 2026-06-26

Richiesta utente: verificare sul fascicolo reale `795C50AC` che il deposito non ripeta l'errore ministeriale `Indice busta non trovato`, che gli allegati non obbligatori non vengano firmati a forza, che `Simula invio PEC` produca lo stesso pacchetto dell'invio reale senza spedire la PEC e che `Invia deposito reale` resti attivo solo dopo controlli conformi.

Fonti ufficiali controllate:

- PST Ministero della Giustizia, `Specifiche Tecniche ex art. 34 DM 44/2011 - Provvedimento 7 agosto 2024`, efficace dal `30/09/2024`;
- provvedimento DGSIA `m_dg.DOG07.07/08/2024.0004292.ID`, che disciplina PST, PEC ministeriali, CAdES, PAdES, PKCS#11, certificati, log PEC e catalogo servizi telematici;
- articolo 4 del provvedimento: gli uffici giudiziari usano caselle PEC del sottodominio ministeriale e la codifica uffici/PEC è nel catalogo servizi telematici;
- articolo 17 del provvedimento: per le trasmissioni telematiche si usano algoritmi di cifratura asimmetrica e chiavi di sessione; nel flusso IUSENTRA questo è presidiato da `Atto.msg` cifrato in `Atto.enc` CMS/PKCS#7 `EnvelopedData` con AES256 e certificato PST dell'ufficio.

Prova reale server su Chrome installato, non browser integrato Codex:

- URL verificato: `https://app.iusentra.it/fascicoli/795C50AC/deposito/prepara#generazione-busta`;
- fascicolo: `2026/332 - Marchetti Lucia`, ufficio `Tribunale di Vicenza`, PEC `tribunale.vicenza@civile.ptel.giustiziacert.it`;
- pagina React autenticata, nessun fallback legacy e nessun HTML grezzo;
- `Autocertificazione ricorso.PDF` e `Autocertificazione situazione reddituale.PDF` sono mostrati come `Allegato di prova - Firma non necessaria`, non più come documenti da firmare in lotto;
- `Firma` mostra `0 documenti da firmare`; `Ricorso.pdf.p7m` resta `atto principale` firmato e `Procura.PDF.p7m` resta `Procura alle liti` firmata;
- `Simula invio PEC` ha chiesto il PIN solo per firmare `DatiAtto.xml` in `DatiAtto.xml.p7m`, non per rifirmare allegati già firmati o allegati facoltativi;
- esito UI reale: `Simulazione PEC completata senza invio reale: compatibilità 100%`;
- controlli UI verdi: `Atto.enc ministeriale AES256`, `DatiAtto.xml.p7m firmato`, `IndiceBusta.xml ministeriale`, `IndiceDocumentiDepositati.PDF`, `Atto principale e allegati controllati`, `PEC ufficio giudiziario`, `Oggetto PEC deposito`, `Corpo PEC verificabile`;
- report UI: `Controlli software superati: destinatario PEC, indice, documenti, testo e trasporto risultano pronti per l'invio reale`;
- `Invia deposito reale` risulta attivo dopo la simulazione;
- nessuna PEC reale è stata inviata durante la prova;
- screenshot fuori repository: `C:\Users\antmm\AppData\Local\Temp\iusentra-795C50AC-simula-pec-compatibilita-100.png`.

Confronto tecnico con i requisiti ministeriali PCT/SICID:

- destinatario PEC: conforme sul caso provato perché usa PEC ministeriale dell'ufficio da profilo deposito SQL/catalogo;
- busta: conforme sul caso provato perché `Atto.enc` è generato come contenitore CMS/PKCS#7 `EnvelopedData`, non come file base64 fittizio o allegato non crittografato;
- cifratura: conforme sul caso provato perché il report tecnico indica AES256 con certificato PST;
- indice busta: conforme sul caso provato perché `IndiceBusta.xml` è generato e incluso in `Atto.msg`; questo presidia direttamente l'errore reale ricevuto `Indice busta non trovato`;
- metadati atto: conforme sul caso provato perché `DatiAtto.xml` viene firmato CAdES in `DatiAtto.xml.p7m` prima della generazione finale;
- indice documenti: conforme sul caso provato perché `IndiceDocumentiDepositati.PDF` è generato, incluso e visualizzabile;
- corpo PEC: conforme sul caso provato perché richiama `Atto.enc` e l'elenco dei documenti contenuti;
- firma documenti: conforme sul caso provato perché la UI mostra `Firmato` solo per `.p7m` verificati e non forza firme facoltative sugli allegati;
- invio PEC: conforme alla regola operativa IUSENTRA perché resta dal PC locale tramite Local Signer; il server prepara e controlla, ma non diventa canale SMTP reale.

Guardrail eseguiti:

- `python -m pytest tests/test_busta.py::test_busta_contiene_indice_busta_ministeriale tests/test_busta.py::test_busta_reale_usa_dati_atto_firmato_nell_indice_busta tests/test_busta.py::test_audit_busta_blocca_prima_della_generazione_reale tests/test_deposito.py::test_deposito_invia_pec_simula_invio_senza_spedire_quando_busta_conforme tests/test_local_pec_runtime.py::test_payload_local_pec_rifiuta_atto_enc_non_cms tests/test_local_pec_runtime.py::test_payload_local_pec_include_atto_enc_cms_base64 tests/test_deposito_server_dry_run_audit.py::test_audit_dry_run_confronta_busta_con_copia_non_crittografata_e_blocca_invio_reale tests/test_regia_ui_react.py::test_ui_deposito_prova_guidata_non_salta_firma_e_mostra_audit_pec_indice -q` -> `8 passed`;
- prova reale Chrome: compatibilità `100%`, nessun errore `Firma multipla da completare`, nessun `ComputeSignature`, nessun `Local Signer non raggiungibile`, nessuna autenticazione SMTP richiesta nella simulazione e nessuna PEC reale inviata.

Correzione collegata:

- durante la prova è emerso che il browser integrato Codex blocca `127.0.0.1:27272`/`localhost:27272` con `ERR_BLOCKED_BY_CLIENT`; Chrome installato invece raggiunge correttamente Local Signer e token CNS;
- il template di avvio Local Signer in `web/services/telematico_runtime.py` ora valuta tutti gli argomenti (`%*`) e non solo `%~1`, così `--background --force` e `iusentra-local-signer://restart` riallineano davvero il processo quando il token è presente ma il signer attivo non è aggiornato.

Stato operativo: sul caso reale `795C50AC` la conformità tecnica del pacchetto PCT/SICID è verificata documento per documento nella simulazione senza invio PEC reale. La dichiarazione non sostituisce una valutazione legale dell'atto processuale o della strategia difensiva: certifica il comportamento tecnico del software rispetto ai requisiti ministeriali verificabili nel pacchetto generato.
## Notifiche legali L. 53/1994: controllo invio, relata e allegati EML - 2.253.122 - 2026-06-26

Richiesta utente: verificare che `https://app.iusentra.it/notifiche-legali` tratti correttamente la notifica PEC, senza invii automatici dal server, con relata firmata solo da prova tecnica e con allegati `.eml` inviabili quando scelti dall'avvocato ma non proposti automaticamente come atti da notificare.

Fonti ufficiali operative:

- L. 21 gennaio 1994 n. 53, art. 3-bis: notifica a mezzo PEC dell'avvocato, oggetto obbligatorio, relata su documento informatico separato e firma digitale;
- D.L. 179/2012, art. 16-ter: uso dei pubblici elenchi per indirizzi PEC;
- regola IUSENTRA permanente: invio PEC legale dal PC locale tramite Local Signer/servizio locale, non SMTP server-side.

Correzione applicata:

- la proposta automatica dei `Documenti da notificare` seleziona solo file notificabili come atto/documento principale: `.pdf`, `.pdfa`, `.p7m`;
- i file `.eml` e `.msg` non entrano più automaticamente nella proposta documenti, così ricevute, richieste pagamento e messaggi PEC non vengono scambiati per atti principali;
- gli `.eml` e `.msg` scelti volontariamente dall'avvocato restano però allegati inviabili nella PEC di notifica;
- il validatore L. 53 accetta `.pdf`, `.pdfa`, `.p7m`, `.eml` e `.msg`, e continua a bloccare estensioni estranee;
- il pulsante `Invia PEC` resta disabilitato finché il controllo relata non è superato e finché mancano requisiti obbligatori: avvocato abilitato, PEC notificante validata, PEC destinatario da pubblico elenco, relata separata, relata firmata con prova CAdES/PAdES, ricevuta completa, approvazione finale e allegati ammessi;
- la UI mostra il motivo del blocco nel titolo/stato del pulsante invece di lasciare un invito ambiguo all'invio.

Prova reale eseguita prima della correzione su Chrome installato in produzione:

- pagina React aperta su `https://app.iusentra.it/notifiche-legali`, autenticata come studio reale, senza fallback legacy;
- selezionata pratica `2026/332 - Marchetti c. MIM`;
- il controllo `Controlla relata` ha mostrato oggetto PEC vincolato `notificazione ai sensi della legge n. 53 del 1994`, ricevuta completa, relata separata e blocchi puntuali prima dell'invio;
- blocchi osservati: avvocato abilitato/PEC mittente/PEC destinatario da pubblico elenco/relata firmata/dati procedimento, quindi nessuna notifica poteva essere considerata valida;
- nessuna PEC reale è stata inviata.

Guardrail automatici eseguiti:

- `python -m pytest tests/test_notifiche_legali.py::test_notifica_l53_accetta_eml_scelto_come_allegato_non_autoproposto tests/test_notifiche_legali.py::test_api_react_notifiche_legali_espone_workflow_separati tests/test_regia_ui_react.py::test_ui_notifiche_relata_firma_solo_con_prova_tecnica -q` -> `3 passed`;
- `pnpm --filter @iusentra/studio typecheck` -> verde;
- `pnpm --filter @iusentra/studio build:vite` -> verde; gli asset hashati locali sono stati puliti perché Docker/Hetzner ricompila il bundle React dal sorgente.

Stato: la regola funzionale richiesta è ora nel sorgente e nei test. Resta da verificare visivamente su `https://app.iusentra.it/notifiche-legali` dopo deploy del commit, perché la produzione serve il bundle generato in Docker.

Aggiornamento ulteriore richiesto il 2026-06-26:

- l'attestazione di conformità non viene più trattata come testo opzionale generico: quando un documento da notificare proviene dal fascicolo informatico, da comunicazione di cancelleria o da scansione analogica, IUSENTRA genera nel payload anche `Attestazione_conformita_<pratica>.pdf` come allegato operativo della PEC, oltre al blocco di attestazione nella relata;
- la PEC `.eml` dell'ufficio resta evidenza del rilascio/comunicazione, non sostituisce il documento scaricato dal portale che deve essere notificato;
- il nome avvocato viene normalizzato: se il profilo contiene già `Avv. Giuseppe Montagnese`, la relata stampa `Io sottoscritto Avv. Giuseppe Montagnese`, non `Avv. Avv.`;
- il blocco procedimento non stampa più campi vuoti: niente `Sezione ,` quando la sezione manca e niente `R.G. n. /2026`; se il numero RG non è nella colonna dedicata, viene derivato da `RG 466/2023` presente nel numero/label della pratica;
- test mirati aggiunti: normalizzazione avvocato/procedimento, derivazione RG da numero fascicolo, `.eml` ammessi ma non autoproposti, attestazione automatica lato React.

## Aggiornamento 2026-06-26 - verifica server anti `Indice busta non trovato` su `795C50AC`

Richiesta corrente dell'utente: eseguire la verifica sul server, non sulla copia locale, concentrandosi solo sul difetto reale ricevuto dal Ministero: esito automatico `Codice esito: -1`, `IDBUSTA: 152529323`, messaggio `Indice busta non trovato, necessario effettuare nuovamente il deposito`.

Verifica server eseguita su `iusentra-hetzner`, container `iusentra-app-1`, produzione `https://app.iusentra.it`, commit `5e99e9dd43f39e88601dcfaf1c39af8b7310e799`, versione `2.253.123`:

- fascicolo verificato: `795C50AC`, `2026/332 - Marchetti Lucia`, ufficio `Tribunale di Vicenza`;
- destinatario PEC risolto dalla produzione: `tribunale.vicenza@civile.ptel.giustiziacert.it`;
- la route reale usata da `Simula invio PEC` e `Invia deposito reale` è `/fascicoli/795C50AC/deposito/invia-pec`;
- primo passaggio: la route non genera `Atto.enc` se manca `DatiAtto.xml.p7m`; restituisce `requires_local_signature=true` e chiede la firma locale del solo `DatiAtto.xml`;
- controllo tecnico server di attraversamento: per non usare il token dell'avvocato nella prova automatica, è stata generata nel container una CAdES di test solo per attraversare il ramo successivo; questa prova non sostituisce la firma qualificata reale, ma verifica che la route reale costruisca busta e payload PEC corretti prima dello SMTP locale;
- `Simula invio PEC`: esito HTTP `200`, `ok=true`, `simulazione=true`, `package_ready=true`, nessuna chiamata SMTP, compatibilità `100%`;
- `Invia deposito reale` prima dello SMTP: esito HTTP `200`, `requires_local_pec=true`, `package_ready=true`, endpoint locale `http://127.0.0.1:27272/pec/send`, destinatario Vicenza e SMTP studio presente; nessuna PEC è stata inviata dal server;
- allegato generato per entrambi i rami: `Atto.enc` con `ministerial_busta_verified=true`, base64 presente solo nel payload al Local Signer e hash SHA-256 coerente con l'audit busta.

Controllo documento per documento del pacchetto reale pre-SMTP generato sul server:

- `Atto-realroute.msg` contiene `IndiceBusta.xml`;
- `IndiceBusta.xml` ha radice `IndiceBusta` e richiama `Atto Nome="Ricorso.pdf.p7m"`;
- `IndiceBusta.xml` contiene un solo allegato `Tipo="DA"` con `Nome="DatiAtto.xml.p7m"`;
- ogni voce richiamata dall'indice è presente dentro `Atto.msg`: `DatiAtto.xml.p7m`, `Procura.PDF.p7m`, `Autocertificazione ricorso.PDF`, `Autocertificazione situazione reddituale.PDF`, `Carta Identità e C.F. Lucia Marchetti.PDF`, `Contratto 24-25.pdf`, `Contratto Rossi 2025-2026.pdf`, `IndiceDocumentiDepositati.PDF`;
- `Atto-realroute.enc` è un CMS/PKCS#7 `EnvelopedData` valido, `content_type=data`, algoritmo `aes256_cbc`, OID `2.16.840.1.101.3.4.1.42`, `recipients=1`, dimensione `34.879.298` byte.

Verifica visiva su browser integrato Codex aperto sulla produzione:

- URL: `https://app.iusentra.it/fascicoli/795C50AC/deposito/prepara#generazione-busta`;
- pagina React visibile, nessun fallback legacy e nessun HTML grezzo;
- fase `Busta e indice`: PEC Vicenza visibile e verificata dal profilo deposito SQL;
- `Firma software` mostra `0 documenti da firmare`;
- `Autocertificazione ricorso.PDF`, `Autocertificazione situazione reddituale.PDF`, `Carta Identità e C.F. Lucia Marchetti.PDF`, `Contratto 24-25.pdf`, `Contratto Rossi 2025-2026.pdf`, `Sentenza Cassazione.PDF` e `Sentenza_Tribunale_Vicenza_20-04-2023.PDF` sono mostrati come `Firma non necessaria`, quindi non vengono firmati a forza;
- `Ricorso.pdf.p7m` e `Procura.PDF.p7m` sono mostrati come firmati;
- testo PEC visibile e modificabile facoltativamente, con riferimento a `Atto.enc` e all'elenco documenti;
- pulsanti `Prova senza invio reale`, `Simula invio PEC` e `Invia deposito reale` presenti e `disabled=false`;
- anteprima `IndiceDocumentiDepositati.PDF` aperta su produzione: modal con titolo, pulsante `Scarica`, pulsante `Chiudi`, nessuna area rotta/bianca.

Esito operativo: il difetto tecnico `Indice busta non trovato` è presidiato dal nuovo controllo perché l'invio reale non può più arrivare al Local Signer PEC se `Atto.msg` non contiene `IndiceBusta.xml`, se l'indice non richiama file realmente presenti, se manca `DatiAtto.xml.p7m` o se `Atto.enc` non è CMS AES256 verificato. L'ultimo passo SMTP resta correttamente sul PC locale dell'avvocato tramite Local Signer; il server non è e non deve diventare mittente SMTP del deposito legale.

## Acquisizione PST: certificato, tabella ministeriale automatica e hover pulsanti - 2026-06-26

Richiesta utente: rendere rapida la ricerca fascicolo PST, evitare tentativi lunghi quando manca il certificato, applicare automaticamente la tabella ministeriale corretta a tutti i registri supportati e correggere i pulsanti che diventavano illeggibili in hover/focus.

Correzione applicata:

- la ricerca PST si ferma prima di avviare il flusso Local Signer/PST se sul PC non risulta un certificato CNS/CIE valido già disponibile; la UI mostra un messaggio operativo e non parte con minuti di tentativi inutili;
- aggiunto endpoint React `GET /api/v1/ui/telematico/pst/schema-hint` per dedurre la tabella ministeriale dal fascicolo locale quando esiste un segnale affidabile;
- la logica frontend applica profili ministeriali per civile, lavoro/previdenza, volontaria giurisdizione, minori, esecuzioni/concorsuali, giudice di pace, Cassazione civile e Cassazione penale, non solo lavoro;
- il Local Signer 1.6.81 non esplora più tabelle ministeriali estranee quando il registro è esplicito, riducendo tentativi e tempi di ricerca;
- l'aggiornamento automatico Local Signer prova l'endpoint locale `/update` con `base_url` controllato e poi verifica in modo silenzioso per evitare intermittenza nella UI;
- la correzione di contrasto dei pulsanti è stata ristretta al componente PST/telematico: la topbar, incluso `Assistenza remota`, non viene più toccata da regole globali;
- nel blocco Local Signer i pulsanti primari mantengono testo e icona bianchi su blu in hover/focus; il link `Installa o aggiorna` mantiene testo e icona scuri su fondo bianco/azzurro.

Prova reale locale eseguita su browser integrato Codex, copia reale `http://127.0.0.1:8080`, URL `http://127.0.0.1:8080/portali/pst/acquisizione?ufficio=Tribunale+di+Palmi&numero=3441&anno=2025&schema=esecuzioni#step-search`:

- Docker locale ricostruito e container `iusentra-app` healthy;
- `/api/pronto` risponde HTTP 200;
- pagina React PST visibile senza fallback legacy;
- step `Accesso` aperto materialmente;
- hover reale verificato su `Verifica Local Signer`, `Avvia e verifica`, `Aggiorna automaticamente`, `Installa o aggiorna` e `Vai alla ricerca`: testo e icone restano leggibili;
- `Assistenza remota` in topbar è tornato al suo stile originale e resta leggibile;
- Local Signer distribuito dalla copia locale mostra ultima versione `1.6.81`;
- per il caso Palmi con `schema=esecuzioni`, il profilo ministeriale viene trattato come tabella esecuzioni/concorsuali; se non esiste alcun segnale locale o URL e manca il certificato, la ricerca si blocca subito invece di provare registri a cascata.

Guardrail automatici eseguiti:

- `pnpm --filter @iusentra/studio typecheck` -> OK;
- `pnpm --filter @iusentra/studio build` -> OK;
- `python -m py_compile web\blueprints\api_v1_react.py tools\local_signer.py` -> OK;
- `python -m pytest tests/test_react_shell.py::test_pst_acquisizione_deduce_tabella_ministeriale_da_fascicolo_locale tests/test_react_shell.py::test_pst_acquisizione_deduce_registri_ministeriali_non_lavoro tests/test_react_shell.py::test_pst_acquisizione_ricerca_non_parte_senza_certificato_preesistente tests/test_local_signer.py::test_pst_varianti_registro_esplicito_non_esplorano_tabelle_estranee -q` -> `4 passed`.

## Local Signer 1.6.82: prima installazione pulita e anti-regressione installer - 2026-06-26

Richiesta utente: verificare che un cliente che installa Local Signer per la prima volta non resti bloccato e che l'aggiornamento non rompa il servizio essenziale del deposito/PST.

Diagnosi sulla macchina reale:

- il Local Signer installato in `%APPDATA%\IUSENTRA\LocalSigner` era rimasto a `1.6.80` e non esponeva il servizio locale;
- il log installer mostrava due avvii quasi contemporanei: una installazione stava creando `.venv`, la seconda ha trovato una virtualenv incompleta e pip si e' fermato con `failed to locate pyvenv.cfg`;
- il problema non era il certificato PST o la UI, ma un installer Windows non idempotente sotto doppio avvio/aggiornamento concorrente.

Correzione applicata:

- l'installer Windows usa ora un lock esclusivo `%APPDATA%\IUSENTRA\LocalSigner\installer.lock`, con timeout e rilascio anche in caso di errore;
- se `.venv` esiste ma manca `pyvenv.cfg` o `python.exe`, l'installer la rimuove e la ricrea prima di installare le dipendenze;
- i pacchetti Local Signer sono stati rigenerati come `1.6.82` per Windows, macOS e Linux, mantenendo l'alias Windows `SetupLocalSigner.exe` puntato alla release corrente;
- i test di build verificano la presenza del lock e della riparazione virtualenv nel pacchetto Windows.

Prova reale locale eseguita:

- installazione corrente spostata fuori percorso runtime e nuova installazione da cartella vuota `%APPDATA%\IUSENTRA\LocalSigner`;
- servizio avviato su `127.0.0.1:27272`;
- `GET /ping` restituisce `ok=true`, `versione=1.6.82`, libreria PKCS#11 Windows presente e certificati Windows leggibili;
- Docker locale reale ricostruito su `2.253.125`, `/api/pronto` `ok=true`, e browser integrato su `http://127.0.0.1:8080/portali/pst/acquisizione?ufficio=Tribunale+di+Palmi&numero=3441&anno=2025&schema=esecuzioni#step-search` mostra `Local Signer pronto` e `rilevata 1.6.82`;
- la firma con token fisico/PIN resta da verificare solo quando il token dell'avvocato è collegato, ma il requisito di prima installazione, servizio locale e canale PST/Local Signer è stato verificato sulla macchina reale.

Limite residuo operativo: quando l'URL non contiene `schema`, non esiste profilo in cache e non c'è un fascicolo locale corrispondente da cui dedurre il registro, IUSENTRA non inventa la tabella ministeriale. In quel caso la UI deve chiedere un segnale reale o fermarsi se manca il certificato, evitando la ricerca lunga e non governata.

## Fascicoli, OCR economico e deposito - 2.253.126 - 2026-06-26

Richiesta collegata al deposito/PEC/notifiche: la pipeline deve usare la stessa nuova logica OCR/economica, perché dati sbagliati su CU, esborsi o catalogo documenti possono arrivare fino a fascicolo, busta, PEC, notifiche e Lex AI.

Presidio aggiornato:

- il CU viene valorizzato solo da prova di pagamento reale o esenzione esplicita presente nel fascicolo;
- importi Carta docente, soglie reddituali e autocertificazioni DPR 115/2002 non alimentano più `contributo_unificato`;
- `fondo_spese` non è più voce separata nel flusso operativo: viene assorbita in `Spese/esborsi`, evitando doppioni in vista economica, proforma e riepiloghi;
- il backfill automatico `lex_sentenza_economia_auto` usa lo stesso estrattore CU governato, quindi il dato reindicizzato per Lex/vector DB resta coerente con la matrice economica fascicolo;
- la UI fascicoli economica non espone più il filtro/colonna `Fondo spese`, così l'avvocato vede una sola voce `Spese/esborsi`.

Verifica locale dati prima del rebuild Docker:

- reset/backfill locale `sentenza-economia-reset-local-v6-cu-fondo-20260626.json`: `documents_catalogued=667`, `errors=0`, `vector_embedding_errors=0`, `vector_indexed=1`;
- merge locale `fondo-spese-merge-local-apply-20260626.json`: `fascicoli_seen=7`, `legacy_entries_removed=0`;
- controllo a freddo pagamenti locale: nessuna chiave `fondo_spese`, nessun CU sospetto `500,00` o `38.514,03`.

Stato: codice e dati locali sono pronti per prova reale su `127.0.0.1:8080`; dopo commit/push e deploy Hetzner lo stesso reset/backfill e merge devono essere eseguiti su `/data` produzione e verificati sui fascicoli reali indicati dall'utente.

## Fascicoli, OCR economico e deposito - verifica locale finale 2.253.126 - 2026-06-26

Verifica reale locale eseguita dopo rebuild Docker:

- `docker compose build --no-cache app scheduler-worker ocr-worker` completato;
- `app`, `scheduler-worker` e `ocr-worker` healthy sulla copia reale `127.0.0.1:8080`;
- `/api/pronto` restituisce `ok=true`, `timezone=Europe/Rome`, `versione=2.253.126`;
- `scripts/check_runtime_services.py --wait-job-seconds 900 --require-all-due-jobs` ha atteso e confermato il run reale `lex_sentenza_economia_auto` completato senza errori dopo il riavvio;
- browser integrato visibile su `http://127.0.0.1:8080/fascicoli?vista=economica`, desktop `1440x900`, tablet `820x1180` e mobile `390x844`.

Dati osservati nel fascicolo locale `RG 466/2023`:

- `Contributo unificato da pagare`: `€ 98,00`, stato `Da registrare`, data vuota;
- `Spese/esborsi`: `€ 125,00`, stato `Pagato`;
- `Liquidazione giudice`: `€ 1.500,00`, stato `Pagato`;
- `Parcella`: `€ 2.028,20`, stato `Da emettere`;
- `Totale registrato`: `€ 1.625,00`, quindi il CU dovuto non viene conteggiato come incasso pagato;
- la voce `Fondo spese` non compare più in tabella, card mobile, filtri economici o riepilogo.

Impatto su deposito/PEC/notifiche: la logica resta unica nella pipeline documentale. Il backfill e il worker scheduler usano lo stesso estrattore CU governato, mentre `fondo_spese` è solo alias legacy verso `spese_esborsi`; di conseguenza Fascicoli, Lex AI, preparazione deposito, notifiche e PEC leggono la stessa matrice economica, evitando importi duplicati o falsi CU da Carta docente/reddito/autocertificazioni.

Stato residuo prima della chiusura: dopo commit, push e check GitHub, ripetere su Hetzner deploy, reset/backfill e merge dati produzione senza backup, poi verificare visivamente i fascicoli reali segnalati nello screenshot.
## Local Signer 1.6.83: installer Windows, update automatico, PIN e UI - 2026-06-28

Richiesta utente: ripristinare il comportamento automatico di installazione/aggiornamento Local Signer, correggere la prima installazione Windows 11 quando il servizio non risponde su `127.0.0.1:27272`, preservare firma, assistenza remota, PEC/email, bridge AI e ricerca portali, silenziare le chiamate curl/subprocess e risolvere hover/focus dei pulsanti React.

Diagnosi tecnica:

- il Local Signer è un componente trasversale, non solo firma: espone firma singola/multipla, sessioni PIN, PST/PDP/PAT/PTT, PEC locale, assistenza remota, bridge AI, download e diagnostica;
- l'installer Windows installava le dipendenze base ma non includeva `pillow`, pur essendo presente in `requirements_local_signer.txt` e necessaria per l'assistenza remota con screenshot;
- il primo avvio preferiva `pythonw.exe`, quindi era silenzioso ma lasciava pochi log utili quando il servizio non partiva;
- il wizard React, nel flusso di ricerca, controllava Local Signer con `checkLocalSigner(false)` e quindi non tentava l'avvio automatico nel punto in cui l'avvocato si aspetta continuità;
- le regole CSS dei pulsanti Local Signer non fissavano in modo locale background, colore e icone per hover/focus/disabled, lasciando spazio a sovrascritture;
- il foreground PIN esisteva per curl/PST, ma la stessa protezione non era riusata nella firma via certificato Windows Store.

Fonti ufficiali consultate:

- Python Windows embeddable package: la distribuzione embedded è minima e le dipendenze di terze parti devono essere gestite dall'installer dell'applicazione, non lasciate implicite (`https://docs.python.org/3/using/windows.html#the-embeddable-package`);
- Microsoft `Register-ScheduledTask`: la registrazione dell'attività pianificata supporta eseguibili/script locali, ma non valida automaticamente la compatibilità del file eseguito (`https://learn.microsoft.com/en-us/powershell/module/scheduledtasks/register-scheduledtask`).

Correzioni applicate:

- versione Local Signer portata a `1.6.83`;
- l'installer Windows installa anche `pillow>=10.0.0`;
- il launcher generato usa `python.exe` nascosto con redirect verso `local_signer.out.log` e `local_signer.err.log`, mantenendo `pythonw.exe` solo come fallback;
- l'attesa prima di dichiarare non raggiungibile il servizio passa a 45 tentativi;
- l'avvio immediato imposta anche `IUSENTRA_LOCAL_SIGNER_UPDATE_URL`;
- la ricerca React tenta l'avvio automatico con `checkLocalSigner(true)` prima di bloccare;
- i pulsanti `Avvia e verifica`, `Aggiorna automaticamente` e `Vai alla ricerca` riusano la stessa logica visiva locale di `Verifica Local Signer`, con stati espliciti per normale, hover, focus e disabled;
- il runner nascosto con foreground PIN viene riusato anche dalla firma via Windows Store;
- aggiunti guardrail su middleware PIN comuni (`InfoCert`, `Namirial`, `IDProtect`, `SafeNet`, `Athena`, `Actalis`) e su avvio silenzioso senza finestre.

Test automatici eseguiti:

- `python -m py_compile tools\local_signer.py` -> OK;
- `python -m pytest -q tests/test_local_signer.py::test_local_signer_pst_curl_attiva_foreground_prompt_pin_windows tests/test_local_signer.py::test_run_curl_windows_silenzia_console_senza_perdere_foreground_pin tests/test_local_signer.py::test_local_signer_launcher_windows_usa_avvio_silenzioso tests/test_build_dist.py::test_build_windows_ps1_include_versione_e_script_originale tests/test_react_shell.py::test_react_wizard_pst_verifica_local_signer_dal_browser` -> `5 passed`.
- `python -m pytest -q tests/test_local_signer.py::test_download_requirements_local_signer_e_pubblico tests/test_local_signer.py::test_installer_local_signer_windows_ps1_legacy_restituisce_exe tests/test_local_signer.py::test_installer_local_signer_windows_setup_route_e_pubblica tests/test_local_signer.py::test_installer_local_signer_windows_exe_route_se_bundle_presente tests/test_local_signer.py::test_installer_local_signer_macos_e_pubblico tests/test_local_signer.py::test_installer_local_signer_linux_e_pubblico tests/test_local_signer.py::test_local_signer_launcher_windows_usa_avvio_silenzioso tests/test_build_dist.py::test_build_windows_ps1_include_versione_e_script_originale` -> `8 passed`.
- `python -m pytest -q tests/test_react_shell.py::test_react_wizard_pst_verifica_local_signer_dal_browser` -> `1 passed` dopo la correzione hover-only;
- `pnpm --filter @iusentra/studio test` -> contratti React, governance design system e divieti CSS OK dopo rimozione della proprietà CSS vietata;
- `python -m pytest tests/test_react_asset_retention.py -q --tb=short` -> `2 passed` con asset Vite aggiornati;
- `python -m pytest -q tests/test_local_signer.py::test_firma_windows_store_interattiva_usa_runner_pin_foreground_silenzioso` -> `1 passed`; presidia che la firma Windows Store usi il runner PIN foreground/silenzioso e non torni a `subprocess.run` diretto;
- `python scripts/run_pytest_phases.py --suite signer --suite-shard 1 --suite-total-shards 4 --suite-subdivide-items --timeout-minutes 5` -> shard signer `1/4` verde dopo riallineamento del test Windows Store al nuovo contratto;
- `pnpm --filter @iusentra/studio typecheck` -> OK;
- `pnpm --filter @iusentra/studio build` -> OK;
- `python -m pytest tests/test_utf8_integrity.py -q --tb=short` -> `4 passed`;
- `python -m pytest tests/test_react_asset_retention.py -q --tb=short` -> `2 passed`;
- `python tools\sync_packaging_files.py --check` -> packaging sincronizzato;
- `python -m pytest tests/test_packaging_consistency.py tests/test_release_readiness.py -q --tb=short` -> `10 passed`;
- `docker compose up -d --build app scheduler-worker ocr-worker` -> app, scheduler e OCR ricostruiti sulla copia reale locale;
- `Invoke-RestMethod http://127.0.0.1:8080/api/pronto` -> `ok=true`, `timezone=Europe/Rome`, `versione=2.253.134`.

Pacchetti generati:

- `tools/dist/SetupLocalSigner-1.6.83.exe`;
- `tools/dist/SetupLocalSigner.exe` aggiornato come alias legacy;
- `tools/dist/InstallaLocalSigner-1.6.83.ps1`;
- `tools/dist/InstallaLocalSigner-1.6.83.command`;
- `tools/dist/InstallaLocalSigner-1.6.83.run`;
- `tools/dist/LocalSigner-1.6.83.txt`.

Stato verifica reale:

- verificato su macchina reale `127.0.0.1:8080` con browser integrato Codex sulla route `/portali/pst/acquisizione`: step `Accesso` visibile, pulsanti `Verifica Local Signer`, `Avvia e verifica`, `Aggiorna automaticamente` e `Vai alla ricerca` leggibili, con testo bianco su sfondo blu;
- il bundle React caricato (`TelematicoSurfacePage-xPye0zGo.css`) contiene regole locali e specifiche che forzano testo, icone, opacità, `mix-blend-mode:normal` e sfondo anche in `:hover` e `:focus-visible`, senza usare proprietà vietate dal design system;
- dopo la richiesta utente di applicare la stessa logica di `Verifica Local Signer`, la regola è stata estesa anche a `.iu-tel-acq-actions button:not(:disabled)`, `.iu-tel-acq-actions button:hover:not(:disabled)` e `.iu-tel-acq-actions button:focus-visible:not(:disabled)`;
- ricontrollato anche `Installa o aggiorna`: resta link secondario leggibile con testo scuro su sfondo bianco, quindi il fix non forza i link secondari in bianco-su-bianco;
- dopo scroll alla sezione Local Signer e puntatore sopra `Avvia e verifica`, il browser visibile mostra `Avvia e verifica`, `Aggiorna automaticamente` e `Vai alla ricerca` leggibili; i colori computati restano `rgb(255, 255, 255)` su `rgb(29, 78, 216)`;
- la manovra automatizzata del puntatore non espone `matches(':hover')`, quindi se l'utente segnala ancora sparizione con mouse fisico la prova va ripetuta davanti alla stessa scheda, senza considerare i soli test automatici come accettazione finale;
- verificato update reale Local Signer dalla UI: dopo `Aggiorna automaticamente` il servizio locale ha risposto con versione `1.6.83`;
- verificato servizio `http://127.0.0.1:27272`: `ping?light=1` risponde con versione `1.6.83`, `support/status` risponde `ok=true`, runtime locale con `pillow=True`, `pkcs11=True`, `send_pec_local=True` e `test_pec_smtp_local=True`;
- non verificato con token fisico: il ping completo segnala `Nessun token PKCS#11 rilevato`; la comparsa reale della finestra PIN davanti all'utente resta aperta finché non è disponibile token/certificato.

Stato rilascio remoto:

- GitHub: branch gemelli pushati e check-run dello SHA corrente completati senza failure; CodeQL, Frontend React, CI, Required Gates, Local Signer/PKCS#11 e Quality Overlay verdi.
- Hetzner CPX42: `https://app.iusentra.it/api/pronto` risponde `ok=true`, `timezone=Europe/Rome`, `versione=2.253.134`; il manifest pubblico serve `assets/TelematicoSurfacePage-xPye0zGo.css`.
- Server: repository su commit pushato, container `iusentra-app`, `iusentra-scheduler-worker` e `iusentra-ocr-worker` healthy; eseguito `docker builder prune --all --force`; `/opt/iusentra/tmp-backup-snapshot` assente.

## Fascicoli, OCR economico e deposito - micro-fix CU esente 2.253.127 - 2026-06-26

- La pipeline usata da fascicoli, Lex economia, PEC/notifiche/deposito e indice documentale ora scrive le esenzioni CU senza data pagamento fittizia: se il fascicolo contiene prova di esenzione, viene riportato lo stato esente/non previsto; se non c'è prova, il valore resta vuoto.
- Prova locale reale su Docker `127.0.0.1:8080`: app/scheduler/OCR healthy, `/api/pronto` `versione=2.253.127`, vista economica Fascicoli controllata in browser integrato desktop e mobile.
- La procedura di rilascio prevede deploy Hetzner e bonifica produzione con lo stesso backfill dopo il push del commit `2.253.127`, senza backup, per riallineare i fascicoli già presenti sul server.

## Fatturazione, PDF, XML SdI e commercialista - presidio operativo - 2026-06-28

Richiesta utente collegata a fatturazione e flussi sensibili: il PDF parcella deve essere leggibile dentro IUSENTRA e le intestazioni tabellari devono usare una sola impostazione comune a tutti i PDF generati dal gestionale.

Presidio applicato:

- la resa grafica delle intestazioni tabellari ReportLab passa da `pct/pdf_style.py::pdf_table_header_style`;
- la regola comune usa sfondo bianco, testo scuro e linea inferiore blu, evitando sfondi scuri che rendono poco leggibili `Descrizione`, `Q.tà`, `Prezzo unit.` e `Importo`;
- i generatori principali di parcelle/fatture, preventivi, notifiche, template atti, editor, report e PDP penale riusano la stessa funzione;
- il PDF resta visualizzabile dentro la stessa pagina Fatturazione con opzione di download e tutto schermo.

Vincolo sensibile confermato:

- la modifica PDF non abilita alcun invio server-side;
- la firma XML FatturaPA e la preparazione PEC SdI/commercialista restano governate dal flusso Local Signer/PC locale;
- eventuali prove di invio devono essere dry-run o preparazione bozza finché l'avvocato non conferma l'invio reale dalla macchina locale.

Verifica reale locale:

- `127.0.0.1:8080` healthy, `/api/pronto` `ok=true`, `timezone=Europe/Rome`, `versione=2.253.134`;
- browser integrato su `/fatturazione/`, click `Apri dettaglio`, modal aperto nella stessa pagina;
- tab `Anteprima PDF` visualizzato nella stessa pagina; sezione `Prestazioni professionali` leggibile con intestazione chiara su sfondo bianco.
- tab `XML e SdI` visualizzato nella stessa pagina con XML originale disponibile, XML firmato da generare, PEC SdI non configurata, PEC non ancora inviata e azione rapida `Inserisci impostazioni PEC`;
- tab `Commercialista` visualizzato nella stessa pagina con stato non configurato/non inviato, scelta email ordinaria/PEC, scelta allegati e azione rapida `Inserisci commercialista`.

Stato ancora aperto per chiusura completa del flusso SdI/commercialista:

- firma XML simulata e preparazione PEC SdI senza invio reale;
- preparazione commercialista sia email ordinaria sia PEC, con stato `inviato/non inviato` visibile;
- confronto tecnico del file XML FatturaPA allegato dall'utente con il generatore IUSENTRA.
## Regola date/orari visibili PEC, email e audit - 2026-06-28

Aggiornamento post-bump `2.253.135`: dopo rebuild Docker senza cache e riavvio locale healthy, la verifica è stata ripetuta sul browser integrato; `/api/pronto` restituisce `versione=2.253.135`, `timezone=Europe/Rome` e il PDF parcella mostra `Data e ora italiana: 28/06/2026 22:04 (Europe/Rome)`.

Per tutti i flussi sensibili collegati a PEC, email ordinaria, notifiche, deposito, SdI, fatturazione e audit, i timestamp tecnici possono restare in UTC solo nei payload macchina, negli header originali EML/XML, nei timestamp RFC 3161 e nei tracciati ministeriali. In UI, PDF, report, pannelli e anteprime l'avvocato deve vedere sempre formato italiano e ora `Europe/Rome`.

Presidio applicato in questa tranche:

- `pct/formatting.py` contiene il formatter comune `format_datetime_it(..., include_timezone=True)`;
- `web/services/react_email_bridge.py` converte data/ora PEC/email in `Europe/Rome` prima di produrre la label visibile;
- `web/blueprints/fatturazione.py` mostra `Data e ora italiana` nel PDF parcella;
- `scripts/standardizza_date_italiane.py` verifica che non restino `Data UTC` o formattatori frontend italiani senza `Europe/Rome`.

Prova reale locale eseguita su `127.0.0.1:8080`: Tariffario, Fatturazione PDF, Email PEC ed Email ordinaria non espongono `Data UTC` né timestamp ISO raw; il PDF parcella mostra `Data e ora italiana: 28/06/2026 21:48 (Europe/Rome)`.

## Deposito PCT reale: DatiAtto ministeriale e indice interno - 2026-06-29

Richiesta utente: evitare altri invii reali a tentativi e verificare seriamente la busta completa, documento per documento, dopo gli esiti PST reali:

- `IDBUSTA 152631750`: `Indice busta non trovato`;
- `IDBUSTA 152633714`: `Atto principale mancante`.

Diagnosi tecnica:

- la busta reale conteneva fisicamente `IndiceBusta.xml`, `DatiAtto.xml.p7m`, `Ricorso.pdf.p7m`, `Procura.PDF.p7m`, allegati PDF, ricevute `.eml` e `IndiceDocumentiDepositati.PDF`;
- i campioni PST accettati e gli XSD ministeriali locali mostrano che il PST legge l'indice determinante dentro il `DatiAtto.xml.p7m` firmato, non solo dal file esterno `IndiceBusta.xml`;
- il vecchio `DatiAtto.xml` IUSENTRA era un XML proprietario `<DatiAtto>` con `<Documenti>`, quindi non esponeva il nodo ministeriale `<Ricorso>` con `<IndiceBusta>` interno;
- nei campioni accettati i documenti CAdES vengono trasportati come `application/pkcs7-mime`, ma con nome logico originale senza suffisso `.p7m` nel MIME e negli indici, per esempio `Ricorso.PDF` invece di `Ricorso.PDF.p7m`;
- la causa tecnica coerente con i due errori è: indice interno assente prima, e atto principale non risolto poi perché l'XML firmato non referenziava il `Content-ID` reale della parte MIME.

Correzione applicata:

- `pct/busta.py` costruisce una mappa unica dei documenti della busta con nome logico ministeriale, payload, tipo MIME, ruolo ministeriale e `Content-ID`;
- per il ricorso introduttivo viene generato un `DatiAtto.xml` ministeriale con root `<Ricorso>`, `destinazione`, `Oggetto`, eventuale `ValoreCausa`, `<IndiceBusta>` interno e `AnagraficaProcedimento`;
- `AttoPrincipale`, `ProcuraLiti` e gli altri allegati nel `DatiAtto.xml` puntano ai `Content-ID` delle parti MIME reali della stessa `Atto.msg`;
- i file `.pdf.p7m` restano payload CAdES `application/pkcs7-mime`, ma in busta vengono nominati come `Ricorso.pdf` e `Procura.PDF`;
- la verifica pre-cifratura apre `DatiAtto.xml.p7m`, estrae l'XML firmato e blocca la busta se il ricorso non contiene l'`IndiceBusta` interno o se un documento presente in `Atto.msg` non è referenziato;
- la route deposito recupera cliente, controparte e configurazione studio per costruire `AnagraficaProcedimento`; per il Ministero dell'Istruzione e del Merito viene riconosciuto il codice fiscale pubblico `80185250588`; se mancano dati obbligatori il flusso si ferma prima della firma/PIN con messaggio puntuale;
- il payload Local Signer e il corpo PEC usano la stessa lista di nomi logici che finisce nella `Atto.msg`.

Verifiche automatiche e offline eseguite:

Aggiornamento governance CI 2026-06-29:

- la logica di `AnagraficaProcedimento` per il ricorso e il valore causa è stata estratta in `web/services/deposito_anagrafica_ministeriale.py`, senza cambiare il contratto della busta;
- `web/bootstrap/deposito_routes.py` è scesa da 1205 a 999 righe e il controllo governance locale è tornato OK;
- sono stati ripetuti compilazione Python, test busta, test deposito mirati, dry-run audit e UTF-8;
- stato operativo invariato: non verificato su macchina reale dopo questo refactor e nessun nuovo invio PST reale va eseguito finché la produzione aggiornata non supera il controllo completo della busta generata.

Aggiornamento produzione fascicolo `795C50AC` 2026-06-29:

- controllo read-only su Hetzner, tenant `studio-legale-giuseppe-montagnese`, fascicolo `Marchetti c. MIM`;
- selezione reale: atto principale `431E29A1 Ricorso.pdf.p7m` e 12 allegati fisici presenti su disco;
- dato bloccante rilevato prima del PIN: il cliente `FDA63E4F` aveva CAP residenza vuoto nel `dati_json` SQL; il CAP è stato corretto a `36100` con indirizzo completo `Strada di Saviabona 256, 36100 Vicenza (VI)`, allineando anche il mirror JSON tenant-aware;
- verifica fonte CAP: OCR/documenti del fascicolo indicano residenza a Vicenza in Strada di Saviabona 256; fonti pubbliche CAP confermano `36100 Vicenza VI`;
- audit strutturale busta su produzione: `BUSTA_AUDIT_OK`, `Atto.msg` con 16 parti, `DatiAtto` root `Ricorso`, `IndiceBusta` interno presente, `AnagraficaProcedimento` presente, 14 riferimenti interni tutti risolti;
- nomi ministeriali confermati: `Ricorso.pdf` e `Procura.PDF` come parti CAdES `application/pkcs7-mime`, senza nomi logici `Ricorso.pdf.p7m` o `Procura.PDF.p7m`;
- `IndiceDocumentiDepositati.PDF`, `IndiceBusta.xml`, `DatiAtto.xml.p7m` e tutti i documenti del fascicolo selezionato risultano inclusi e referenziati;
- audit tecnico: `busta_verifica_valida=true`, `atto_msg_indice_busta_valid=true`, `atto_enc_cms_valid=true`, `dati_atto_signed=true`, `issues=[]`;
- limite residuo: non è ancora invio PST reale post-fix; prossimo passo operativo ammesso è firma reale del `DatiAtto.xml` con PIN utente, poi prova senza invio/Local Signer e solo dopo invio reale tracciato.

- `python -m py_compile pct\busta.py web\bootstrap\deposito_routes.py web\services\deposito_signature_runtime.py tests\test_busta.py tests\test_deposito.py` -> OK;
- `python -m pytest tests\test_busta.py -q --tb=short` -> `20 passed`;
- `python -m pytest tests\test_deposito.py -q --tb=short -k "dati_atto or busta or local_pec or invia_pec or indice"` -> `11 passed`;
- `python -m pytest tests\test_deposito_server_dry_run_audit.py -q --tb=short` -> `4 passed`;
- verifica offline su busta riproducibile con lista equivalente al deposito reale: root firmata `Ricorso`, parti MIME `IndiceBusta.xml`, `DatiAtto.xml.p7m`, `Ricorso.pdf`, allegati PDF, ricevute `.eml`, `Procura.PDF`, `IndiceDocumentiDepositati.PDF`; tutti i documenti sono richiamati dall'`IndiceBusta` interno tramite `Content-ID`; `Ricorso.pdf.p7m` e `Procura.PDF.p7m` non compaiono più come nomi logici della busta.

Stato prova reale:

- non verificato su macchina reale post-fix e non ancora provato con nuovo invio PST reale;
- lavoro aperto fino a deploy sulla produzione Hetzner, controllo reale della pagina `https://app.iusentra.it/fascicoli/795C50AC/deposito/prepara`, prova senza invio, firma Local Signer con PIN dell'utente e solo dopo eventuale invio reale tracciato;
- nessun nuovo invio reale va richiesto all'utente finché la busta generata dalla produzione aggiornata non supera il controllo offline completo su `Atto.msg`, `DatiAtto.xml.p7m`, nomi logici, `Content-ID`, `Atto.enc` e lista documenti.
## Deposito PCT reale `795C50AC`: correzione IndiceBusta.xml esterno - 2026-06-29

Rettifica operativa dopo nuovo esito PST reale:

- `IDBUSTA 152631750`: `Indice busta non trovato`;
- `IDBUSTA 152633714`: `Atto principale mancante`;
- `IDBUSTA 152641015` e `152642074`: `Allegato indicato in indice busta non presente` e `Presenza di allegati non definiti in Indice Busta`;
- `IDBUSTA 152644507`: `Indice busta non trovato`.

Conclusione tecnica dai log reali: il PST non accetta la busta se `IndiceBusta.xml` manca come parte fisica di `Atto.msg`. Il solo indice interno nel `DatiAtto.xml.p7m` non è sufficiente per il trasporto reale osservato. La correzione definitiva deve quindi preservare entrambe le condizioni che i fallimenti hanno isolato:

- `IndiceBusta.xml` deve essere incluso in `Atto.msg` come parte MIME nominata `text/xml`;
- ogni `Nome` e `ID` di `IndiceBusta.xml` deve combaciare con i file fisici e con il `Content-ID` MIME effettivo, inclusi i nomi firmati CAdES `.p7m` (`Ricorso.pdf.p7m`, `Procura.PDF.p7m`).

Correzione applicata:

- `pct/busta.py`: disattivata la modalità solo indice interno; `usa_indice_busta_esterno()` torna sempre vero per il trasporto PCT reale;
- `pct/busta.py`: `nome_file_ministeriale()` conserva il nome fisico reale e non rimuove più `.p7m`;
- `pct/busta.py`: `IndiceBusta.xml` usa gli stessi `Content-ID` delle parti MIME e blocca la busta se l'indice richiama documenti assenti o non indicizza parti presenti;
- `pct/deposito_compatibilita.py`: la simulazione PEC al 100% richiede `IndiceBusta.xml` nella lista documenti e nell'audit tecnico;
- `web/bootstrap/deposito_routes.py`: la lista documenti busta include sempre `IndiceBusta.xml`;
- `frontend/src/components/FascicoliPage.tsx`: il progresso visibile mostra `IndiceBusta.xml`, non più `IndiceBusta interno`;
- `scripts/audit_deposito_server_dry_run.py`: il dry-run segnala come blocco l'assenza di `IndiceBusta.xml`; l'eventuale indice anche interno resta solo avviso non bloccante.

Verifiche eseguite prima di riaprire il test all'utente:

- `python -m py_compile pct\busta.py pct\deposito_compatibilita.py web\bootstrap\deposito_routes.py web\services\deposito_signature_runtime.py web\services\local_pec_runtime.py scripts\audit_deposito_server_dry_run.py` -> OK;
- `python -m pytest tests\test_busta.py tests\test_deposito.py tests\test_deposito_server_dry_run_audit.py tests\test_local_pec_runtime.py tests\test_deposito_anagrafica_ministeriale.py tests\test_regia_ui_react.py -q --tb=short` -> `71 passed`;
- verifica materiale locale su busta generata con `Ricorso.pdf.p7m` e `Procura.PDF.p7m`: parti MIME `IndiceBusta.xml`, `DatiAtto.xml.p7m`, atto, procura, allegato e `IndiceDocumentiDepositati.PDF`; `missing_in_mime=[]`, `missing_in_index=[]`, `id_mismatches=[]`, `audit_mode=indice_busta_xml`, `external=True`;
- hotfix produzione Hetzner: copiati i file runtime, ricostruito `iusentra-app`, container unico healthy, `https://app.iusentra.it/api/pronto` OK alle `19:12:39` Europe/Rome, `docker builder prune --all --force` completato (`5.491GB`).

Stato operativo: prima di qualunque nuovo invio reale, la simulazione visibile del fascicolo `795C50AC` deve mostrare `IndiceBusta.xml` tra i documenti indicati nel pacchetto, insieme a `DatiAtto.xml.p7m`, atto principale `.p7m`, procura `.p7m`, allegati e `IndiceDocumentiDepositati.PDF`. Se `IndiceBusta.xml` non compare nella simulazione, l'invio reale resta bloccato.

## Deposito PCT reale `795C50AC`: blocco indice ambiguo e tipi RT - 2026-06-29

Nuovo esito reale ricevuto:

- `IDBUSTA 152647579`: `Indice busta ambiguo, necessario effettuare nuovamente il deposito`.

Diagnosi aggiornata sulle fonti lette:

- il PDF utente `Formato_Busta_Telematica (1).pdf` descrive `Atto.msg` come composto da `IndiceBusta.xml`, `DatiAtto.xml`, atto principale e allegati;
- la pagina ufficiale PST `https://pst.giustizia.it/PST/it/download.page` e la pagina specifiche DGSIA 7 agosto 2024 confermano le specifiche tecniche ex art. 34 D.M. 44/2011, con rettifiche ufficiali del 16/09/2024 e del 30/10/2024;
- la rettifica DGSIA 16/09/2024 corregge l'art. 17 comma 4 indicando `Atto.enc`, quindi il controllo pre-invio deve verificare l'allegato cifrato reale e non una bozza o uno zip;
- il file `Codifica_errori_controlli_1.0.pdf` collega direttamente `IndiceBusta.xml non presente` a `Indice busta non trovato`, indice non corretto a `Indice busta non corretto`, assenza di allegati indicati nell'indice a `Assente allegato definito in Indice Busta`, atto mancante a `Atto principale mancante`, allegati extra a `Presenza di allegati non definiti in Indice Busta`;
- la comunicazione DGSIA `m_dg.DOG07.19092024.0034552.U_20240916_Comunicazione_Dip._su_accetta.pdf` conferma che i depositi in stato `ERROR`, `WARNING` e `FATAL` restano fuori dal flusso di accettazione automatica, quindi la simulazione IUSENTRA deve bloccare prima dell'invio reale quando l'errore è strutturale;
- lo zip `20260325_Proxy_PDA_EXT.zip` contiene solo i certificati proxy `pda.processotelematico.giustizia.it.cer` e `ext.processotelematico.giustizia.it.cer`; non modifica la struttura della busta, ma resta censito come fonte tecnica PST allegata dall'utente;
- la DTD locale ministeriale `docs/specs/ministero/DTD_20180328/IndiceBusta.dtd` definisce `IndiceBusta` esterno con elemento `Allegato` e attributo `Tipo`; il valore `RT` è la ricevuta telematica di pagamento;
- gli XSD ministeriali locali 2026 (`tipi-allegati.xsd`) usano invece elementi descrittivi nell'indice interno, per esempio `RicevutaPagamento`; nel flusso reale `795C50AC` si usa `IndiceBusta.xml` esterno per evitare l'ambiguità già rifiutata dal PST.

Correzione applicata:

- `pct/busta.py` non genera più `IndiceBusta` interno nel `DatiAtto.xml.p7m` quando è presente `IndiceBusta.xml` esterno;
- la verifica pre-cifratura apre `DatiAtto.xml.p7m` e blocca la busta se trova sia `IndiceBusta.xml` esterno sia `IndiceBusta` interno;
- `IndiceBusta.xml` deve indicizzare tutti i file fisici di `Atto.msg` e nessun file assente, con `Nome` e `ID` uguali ai `Content-ID` MIME;
- la classificazione `RT` è ora limitata a ricevute telematiche di pagamento, PagoPA o contributo unificato; una semplice richiesta di pagamento o una email `.eml` non diventa più `RT`;
- le ricevute di notifica restano distinte: messaggio PEC di notifica `PA`, ricevuta di avvenuta consegna `RA`, allegati ordinari `SM`, procura `PL`, nota iscrizione ruolo `IR`, `DatiAtto` `DA`;
- `scripts/audit_deposito_server_dry_run.py` legge `IndiceBusta.xml`, controlla i tipi ministeriali e produce blocco `INDICE_BUSTA_TIPI` se una ricevuta telematica non è marcata `Tipo=RT` o se un allegato ha un tipo non ammesso.

Verifiche automatiche eseguite:

- `python -m py_compile pct\busta.py scripts\audit_deposito_server_dry_run.py` -> OK;
- `python -m pytest tests\test_busta.py tests\test_deposito_server_dry_run_audit.py -q --tb=short` -> `32 passed`.

Stato operativo: codice corretto a livello locale, ma non ancora verificato su macchina reale e non ancora deployato in produzione per questa tranche `2.253.137`. Prima di autorizzare un nuovo invio reale, la simulazione sul server deve mostrare un solo indice valido: `IndiceBusta.xml` esterno presente in `Atto.msg`, nessun `IndiceBusta` interno nel `DatiAtto.xml.p7m`, tipi allegato coerenti e nessun blocco `INDICE-BUSTA-AMBIGUO`, `INDICE-BUSTA-MIME-CONTRACT` o `INDICE-BUSTA-TIPI`.

## Deposito PCT `795C50AC`: confronto tra `Indice busta non trovato` e `Atto principale mancante` - 2026-06-29

Richiesta utente: ricostruire il passaggio in cui l'errore PST era passato da `Indice busta non trovato` a `Atto principale mancante` per capire come era stato risolto l'indice e applicare lo stesso metodo al controllo dell'atto principale, senza nuovi tentativi reali non presidiati.

Esiti storici confrontati:

- `IDBUSTA 152631750`: `Indice busta non trovato`;
- `IDBUSTA 152633714`: `Atto principale mancante`;
- `IDBUSTA 152647579`: `Indice busta ambiguo`.

Conclusione tecnica del confronto:

- `Indice busta non trovato` era causato dall'assenza o non riconoscibilità di `IndiceBusta.xml` come parte MIME fisica di `Atto.msg`;
- `Atto principale mancante` era lo stadio successivo: il PST leggeva l'indice, ma il nodo `Atto` dell'indice non risolveva il file fisico dell'atto principale nella stessa busta;
- la correzione determinante è stata rendere identici `Nome` e `ID` dell'`Atto` in `IndiceBusta.xml` al file e al `Content-ID` MIME realmente presenti in `Atto.msg`;
- per il caso reale `795C50AC`, il nome da preservare è il nome fisico firmato `Ricorso.pdf.p7m`, non il nome logico senza estensione `.p7m`;
- l'indice interno nel `DatiAtto.xml.p7m` non deve coesistere con `IndiceBusta.xml` esterno, perché il PST ha restituito `Indice busta ambiguo`.

Verifica server temporanea senza invio PEC reale, eseguita dentro `iusentra-app` su file fisici del fascicolo `795C50AC`:

- atto principale usato: `Ricorso.pdf.p7m`;
- documenti selezionati inclusi atto principale: `13`;
- `IndiceBusta.xml` presente in `Atto.msg`;
- `DatiAtto.xml` presente nella prova strutturale non firmata;
- `IndiceDocumentiDepositati.PDF` presente;
- `DatiAtto.xml` senza `IndiceBusta` interno;
- `Atto Nome="Ricorso.pdf.p7m"`;
- `ID` dell'`Atto`: uguale al `Content-ID` MIME della parte `Ricorso.pdf.p7m`;
- `indexed_not_mime=[]`;
- `id_mismatches=[]`;
- `indice_busta_mode=indice_busta_xml`;
- `indice_busta_external_included=true`;
- `indice_busta_mime_contract_ok=true`;
- `indice_busta_tipi_ok=true`;
- `indice_busta_ambiguous=false`;
- `busta_verifica_valida=true`;
- `atto_enc_cms_valid=true`;
- `uses_real_encryption=true`.

Test mirati rilanciati:

- `python -m pytest tests\test_busta.py::test_busta_reale_mantiene_nomi_fisici_cades_in_atto_msg tests\test_busta.py::test_busta_blocca_indice_busta_non_coerente_con_atto_msg tests\test_busta.py::test_busta_blocca_indice_busta_con_id_diversi_dai_content_id tests\test_busta.py::test_busta_reale_blocca_indice_busta_ambiguo -q --tb=short` -> `4 passed`;
- `python -m pytest tests\test_deposito_server_dry_run_audit.py::test_audit_dry_run_blocca_indice_interno_con_xml_esterno tests\test_deposito_server_dry_run_audit.py::test_audit_dry_run_blocca_ricevuta_telematica_senza_tipo_rt -q --tb=short` -> `2 passed`.

Stato operativo: il confronto conferma che la soluzione per `Atto principale mancante` è già la stessa disciplina applicata a `IndiceBusta`: non basta che il nome appaia nella lista visibile, il controllo deve verificare `IndiceBusta.xml` contro le parti MIME reali. Per autorizzare un invio reale successivo, la simulazione deve mostrare e mantenere questi invarianti: `Atto Nome=Ricorso.pdf.p7m`, `Content-ID` uguale, nessun indice interno duplicato, nessun allegato indicizzato ma assente e nessun allegato presente ma non indicizzato.

## Deposito PCT `795C50AC`: continuità busta tra simulazione e invio reale - 2026-06-29

Richiesta utente: evitare che `Simula invio PEC` e `Invia deposito reale` usino una logica o un'identità tecnica diversa, perché la simulazione al 100% deve corrispondere alla busta realmente inviata dal PC locale.

Correzione applicata e deploy hotfix server-first:

- `web/services/local_pec_runtime.py`: il payload Local Signer espone ora sempre `busta_id` e `busta_timestamp`, oltre a `id_deposito`;
- `web/services/deposito_pec_runtime.py`: la simulazione PEC conserva gli stessi metadati della busta generata;
- `web/bootstrap/deposito_routes.py`: prova senza invio, simulazione e invio reale propagano `busta.id_busta` e timestamp della busta corrente;
- `frontend/src/components/FascicoliPage.tsx`: il pannello di prova memorizza `bustaId` e `bustaTimestamp`; il click `Invia deposito reale` li rimanda al server con `local_pec_id_deposito`, `busta_id` e `busta_timestamp`;
- `frontend/src/components/FascicoliPage.tsx`: anche la conferma finale dopo invio PEC Local Signer reinvia `busta_id` e `busta_timestamp`, impedendo una nuova ricostruzione silenziosa al momento della registrazione.

Verifiche automatiche eseguite prima del deploy:

- `python -m pytest tests/test_deposito.py::test_deposito_invia_pec_simula_invio_senza_spedire_quando_busta_conforme tests/test_deposito.py::test_deposito_invia_pec_reale_payload_local_signer_base64_e_corpo_finale tests/test_regia_ui_react.py::test_ui_deposito_prova_guidata_non_salta_firma_e_mostra_audit_pec_indice -q --tb=short` -> `3 passed`.

Deploy produzione Hetzner eseguito prima del commit, su richiesta utente:

- copiati solo i file runtime necessari su `/opt/iusentra/repo`;
- `docker compose -f deploy/hetzner/docker-compose.hetzner.yml build --no-cache app` -> OK;
- `docker compose -f deploy/hetzner/docker-compose.hetzner.yml up -d --no-deps app` -> OK;
- container applicativo unico verificato: `iusentra-app`;
- `https://app.iusentra.it/api/pronto` -> `ok=true`, timestamp `2026-06-29T22:27:37+02:00`, versione `2.253.137`;
- `docker builder prune --all --force` -> completato, `5.493GB` rimossi;
- cartella temporanea `/opt/iusentra/repo/.__iusentra_hotfix_tmp` rimossa.

Stato operativo: hotfix attivo su produzione, ma l'accettazione resta aperta fino alla nuova prova materiale sul browser reale dell'utente. La pagina aperta prima del deploy deve essere ricaricata con `Ctrl+F5`, altrimenti resta in memoria il vecchio JavaScript e il click reale può non inviare `busta_id` e `busta_timestamp` della simulazione.

Verifica produzione sulla simulazione utente `123E2EB2`:

- trovata busta fisica esatta nel container `iusentra-app`: `/tmp/busta_2_v2v7ew/Atto.msg`;
- `Subject`: `Atto deposito telematico 123E2EB2`;
- parti MIME fisiche: `16`;
- `IndiceBusta.xml` presente come prima parte MIME;
- `DatiAtto.xml.p7m` presente, `DatiAtto.xml` non firmato assente;
- voci `IndiceBusta.xml`: `15`, tutte corrispondenti ai file fisici, con `missing_in_mime=[]`, `physical_not_indexed_except_index=[]`, `id_mismatches=[]`;
- atto principale unico: `Ricorso.pdf.p7m`, con `ID=partc96dcd6a2d13ed9607b46d37c8fc13e4` uguale al `Content-ID` MIME;
- `Procura.PDF.p7m` marcata `Tipo=PL`;
- le tre email Carta Docente `.eml` sono marcate `Tipo=SM`, non `RT`;
- `DatiAtto.xml.p7m` estratto senza `IndiceBusta` interno duplicato;
- `Atto.enc` fisico `/tmp/busta_2_v2v7ew/Atto.enc`, dimensione `37554370`, `CMS EnvelopedData=true`, `valid=true`, `content_type=data`, algoritmo `aes256_cbc`, OID `2.16.840.1.101.3.4.1.42`, destinatari `1`;
- bundle React attivo servito da produzione: `index-B2Xxg1l6.js` -> `FascicoliPage-B25XKLv2.js`, e il chunk contiene `local_pec_id_deposito`, `busta_id`, `busta_timestamp`.

Stato operativo della simulazione `123E2EB2`: i controlli tecnici su busta, indice, atto principale, allegati, tipi, assenza di indice ambiguo, cifratura `Atto.enc` e continuità React simulazione/invio reale sono positivi. Il successivo `Invia deposito reale`, se eseguito dalla stessa pagina ricaricata dopo deploy, usa il contratto aggiornato e deve conservare `busta_id`/`busta_timestamp` della simulazione.

Verifica dopo tentativo di invio reale non completato per password PEC errata:

- errore utente/Local Signer: `Autenticazione SMTP PEC locale non riuscita verso smtps.pec.aruba.it:465`;
- il server ha ricevuto il nuovo ciclo reale alle `22:31:52` e `22:32:08`, ma non risulta log `Deposito ... confermato da invio PEC Local Signer`;
- busta reale generata dopo il click: `/tmp/busta_xgakjvxg/Atto.msg`, `Subject=Atto deposito telematico 123E2EB2`;
- `Atto.msg` reale post-click: `16` parti MIME, `IndiceBusta.xml` presente, `DatiAtto.xml.p7m` presente, `DatiAtto.xml` non firmato assente;
- `IndiceBusta.xml` reale post-click: `15` voci, `missing_in_mime=[]`, `physical_not_indexed_except_index=[]`, `id_mismatches=[]`;
- atto principale reale post-click: unico `Ricorso.pdf.p7m`;
- nessun tipo `RT` improprio sulle email `.eml`;
- `DatiAtto.xml.p7m` reale post-click senza `IndiceBusta` interno duplicato;
- `Atto.enc` reale post-click valido, `CMS EnvelopedData=true`, algoritmo `aes256_cbc`, OID `2.16.840.1.101.3.4.1.42`;
- `OVERALL_OK=True`.

Conclusione: la generazione reale della busta è corretta; l'invio PEC non è stato completato perché l'autenticazione SMTP locale Aruba è fallita prima della conferma Local Signer/Message-ID. Si può ripetere `Invia deposito reale` dalla stessa pagina, senza cambiare documenti o corpo PEC, inserendo la password PEC corretta.
## Deposito PCT `795C50AC`: correzione firma CAdES documenti e `DatiAtto.xml.p7m` - 2026-06-29

Richiesta utente: non modificare le regole di indice/busta già funzionanti e intervenire solo sul problema firma emerso sull'esito reale `IDBUSTA 152648910`.

Esito PST reale analizzato:

- `Ricorso.pdf.p7m`: `Allegato non riconosciuto` e `Il mittente non e' tra i firmatari`;
- `DatiAtto.xml.p7m`: `Contenuto firmato non aderente alle specifiche: Il formato del file firmato non e' valido`;
- `Procura.PDF.p7m`: `Allegato non riconosciuto` e `Il mittente non e' tra i firmatari`.

Causa tecnica verificata:

- nella busta reale generata sul server i documenti del fascicolo sono conservati cifrati a riposo con intestazione interna `PCTENC`;
- la costruzione di `Atto.msg` leggeva i file direttamente dal disco, quindi un documento mostrato in UI come `.p7m` poteva entrare nell'allegato ministeriale come payload cifrato interno, non come CAdES leggibile dal PST;
- il controllo di simulazione non apriva materialmente i `.p7m` estratti da `Atto.msg`, quindi poteva dare esito positivo anche se il file fisico spedibile non era un `SignedData` CAdES estraibile;
- il `DatiAtto.xml.p7m` deve essere controllato come CAdES completo, non solo come PKCS#7 generico.

Correzione applicata:

- `pct/document_crypto.py`: helper condivisi per riconoscere, cifrare e decifrare documenti con prefisso `PCTENC`;
- `web/services/document_crypto.py`: wrapper verso gli helper condivisi, così runtime web e dominio PCT usano la stessa decifratura;
- `pct/busta.py`: prima di calcolare hash, indice, `DatiAtto.xml`, `Atto.msg` e dimensione busta, i documenti vengono letti con decifratura a riposo;
- `pct/busta.py`: ogni file `.p7m` incluso nella busta viene verificato come CAdES/PKCS#7 `SignedData`, con contenuto incorporato estraibile e almeno un firmatario leggibile;
- `pct/busta.py`: dopo la costruzione di `Atto.msg`, la verifica rilegge le parti MIME effettive e ricontrolla `Ricorso.pdf.p7m`, `Procura.PDF.p7m` e gli altri `.p7m` sui byte che partirebbero davvero;
- `pct/firma.py`: aggiunto controllo degli attributi firmati CAdES e requisito `signingCertificate`/`signingCertificateV2` per `DatiAtto.xml.p7m`;
- `pct/firma_pkcs11.py` e `tools/local_signer.py`: le firme CAdES generate includono `content_type`, `message_digest`, `signing_time` e `signingCertificateV2`;
- `web/services/deposito_signature_runtime.py`: se `DatiAtto.xml.p7m` non contiene una firma CAdES completa per il deposito ministeriale, la fase si ferma prima della PEC;
- `web/bootstrap/deposito_routes.py`: gli errori di firma/documento vengono restituiti in UI con il nome del file da correggere, senza arrivare alla password PEC o all'invio reale.

Regole lasciate intenzionalmente invariate:

- nessuna modifica alla disciplina già funzionante di `IndiceBusta.xml`;
- nessuna modifica ai tipi `RT`, `PL`, `SM`, `DA` o alla classificazione della procura;
- nessuna modifica a destinatario PEC, oggetto PEC, corpo PEC o canale Local Signer;
- nessun nuovo blocco su dati anagrafici non essenziali.

Verifiche automatiche eseguite:

- `python -m pytest tests/test_busta.py::test_busta_reale_mantiene_nomi_fisici_cades_in_atto_msg tests/test_busta.py::test_busta_reale_decripta_documenti_cades_prima_di_atto_msg tests/test_busta.py::test_busta_reale_blocca_p7m_non_cades -q --tb=short` -> `3 passed`;
- `python -m pytest tests/test_firma_pkcs11.py::test_build_cades_bes_embeds_content_and_certificate -q --tb=short` -> `1 passed`;
- `python -m pytest tests/test_local_signer.py::test_build_cades_bes_inline_restituisce_busta_pkcs7_valida_con_contenuto_embedded -q --tb=short` -> `1 passed`;
- `python -m pytest tests/test_busta.py tests/test_deposito.py::test_deposito_invia_pec_simula_invio_senza_spedire_quando_busta_conforme tests/test_deposito.py::test_deposito_invia_pec_reale_payload_local_signer_base64_e_corpo_finale tests/test_regia_ui_react.py::test_ui_deposito_prova_guidata_non_salta_firma_e_mostra_audit_pec_indice -q --tb=short` -> `30 passed`;
- `python -m pytest tests/test_deposito.py::test_deposito_invia_pec_simula_invio_senza_spedire_quando_busta_conforme tests/test_deposito.py::test_deposito_invia_pec_reale_payload_local_signer_base64_e_corpo_finale -q --tb=short` -> `2 passed`;
- `python -m pytest tests/test_deposito.py::test_firma_documento_ajax_valido_non_fallisce_se_sync_realtime_ha_errori tests/test_deposito.py::test_firma_documento_ajax_recupera_errore_spazio_con_fallback_compatto -q --tb=short` -> `2 passed`.

Stato operativo locale: codice corretto sul perimetro firma e busta. Il Local Signer installato su `C:\Users\antmm\AppData\Roaming\IUSENTRA\LocalSigner\local_signer.py` è stato riallineato al file aggiornato, riavviato e verificato su `http://127.0.0.1:27272/ping`: `ok=true`, versione `1.6.83`, token Bit4id presente e certificato di firma qualificata Aruba selezionato. Prima di autorizzare nuovo invio reale servono ancora deploy server, nuova simulazione PEC reale e controllo che il pacchetto blocchi eventuali `.p7m` non CAdES invece di dichiarare compatibilità positiva.
## Deposito PCT `795C50AC`: avviso DatiAtto non conforme su codice oggetto e valore causa - 2026-06-30

Esito PST reale analizzato:

- `IDBUSTA 152649431`;
- `NOME FILE: DatiAtto.xml.p7m`;
- `Atto non conforme alle specifiche. In attesa di conferma da parte della cancelleria: l'atto verrà comunque accettato non è necessario effettuare nuovamente il deposito`.

Conclusione operativa immediata: questo non è un errore bloccante di indice, allegati, firma o cifratura. Il messaggio ministeriale dice espressamente che l'atto verrà comunque accettato e che non è necessario effettuare nuovamente il deposito. Non va quindi generato un invio duplicato per questo deposito; bisogna presidiare le ricevute successive e l'esito cancelleria.

Controlli eseguiti sulla busta reale generata dal server:

- `Atto.msg` presente nei pacchetti temporanei del container `iusentra-app`;
- parti MIME fisiche presenti: `IndiceBusta.xml`, `DatiAtto.xml.p7m`, `Ricorso.pdf.p7m`, `Procura.PDF.p7m`, allegati PDF/EML e `IndiceDocumentiDepositati.PDF`;
- `DatiAtto.xml.p7m` CAdES valido e in formato firma ministeriale;
- estrazione del contenuto firmato riuscita;
- validazione XSD del `DatiAtto.xml` contro gli XSD SICI locali aggiornati al pacchetto ufficiale PST del `12/05/2026`: `XSD_OK=True`;
- nessun ritorno a `Indice busta non trovato`, `Indice busta ambiguo`, `Atto principale mancante`, allegati assenti o `.p7m` non CAdES.

Differenza semantica trovata confrontando la busta `795C50AC` con i campioni reali allegati dall'utente:

- la busta `795C50AC` usava `Oggetto=220050`, cioè ramo `retribuzione` del lavoro privato;
- i campioni reali Carta docente / Ministero usano `Oggetto=222050`, cioè `retribuzione` nel ramo `Pubblico impiego`;
- il fascicolo `Marchetti c. MIM` ha controparte pubblica (`MIM` / Avvocatura dello Stato) e oggetto `Bonus Docente`, quindi deve usare `222050`;
- il fascicolo aveva `valore_causa=0.0`, quindi il `DatiAtto.xml` non conteneva `ValoreCausa`;
- per Carta docente il valore ministeriale del ricorso viene ora valorizzato a `500.00`, preservando eventuali valori positivi già inseriti dall'utente.

Correzione applicata:

- nuovo helper `web/services/deposito_semantic_helpers.py`;
- `web/services/deposito_route_helpers.py`: se il fascicolo è Carta docente / MIM / Ministero e il codice storico è `220050`, la generazione della busta usa `222050`;
- `web/services/deposito_anagrafica_ministeriale.py`: `ValoreCausa` non resta più assente quando il fascicolo Carta docente ha valore storico `0.0`; viene usato `500.0`;
- nessuna modifica alle regole che hanno già fatto passare indice, allegati, `Content-ID`, firma CAdES, `Atto.enc` e invio PEC tramite Local Signer;
- record SQL di produzione del fascicolo `795C50AC` riallineato: `codice_oggetto_pst=222050`, `valore_causa=500.0`, profilo deposito aggiornato con gli stessi valori.

Verifiche eseguite:

- `python -m py_compile web\services\deposito_semantic_helpers.py web\services\deposito_route_helpers.py web\services\deposito_anagrafica_ministeriale.py` -> OK;
- `python -m pytest tests/test_deposito_route_helpers.py tests/test_deposito_anagrafica_ministeriale.py -q` -> `6 passed`;
- generazione tecnica locale di `DatiAtto.xml` con input `Marchetti c. MIM`: `Oggetto=222050`, `ValoreCausa=500.00`;
- hotfix server-first su Hetzner: file copiati in `/opt/iusentra/repo` e nel container `iusentra-app`;
- `docker exec iusentra-app python -m py_compile ...` -> OK;
- riavvio `iusentra-app` -> container unico healthy;
- `https://app.iusentra.it/api/pronto` -> `ok=true`, `timezone=Europe/Rome`, versione `2.253.137`;
- controllo runtime nel container sul fascicolo reale `795C50AC`: `codice=222050`, `valore_causa=500.0`;
- controllo XML prodotto nel container: `Oggetto=222050`, `ValoreCausa=500.00`.

Stato operativo: il deposito reale già inviato va monitorato, non duplicato, perché l'esito ministeriale indica accettazione comunque prevista. Per eventuali buste successive sullo stesso fascicolo, la produzione ora usa il ramo corretto `Pubblico impiego` e valorizza il `ValoreCausa` ministeriale; indice, firma e trasporto restano invariati rispetto alla versione che ha superato gli errori bloccanti precedenti.

## Acquisizione PST: ricerca rapida, pratica locale da aggiornare e avvisi rimossi - 2026-06-30

Richiesta utente: sulla pagina `https://app.iusentra.it/portali/pst/acquisizione` la ricerca del fascicolo deve essere più veloce; se il fascicolo è già presente in IUSENTRA deve comparire subito come pratica da aggiornare; nella dashboard telematica vanno rimosse le voci generiche `Regia telematica da presidiare` e `Canale assistito`.

Correzione applicata:

- `web/services/react_telematico_bridge.py`: il payload React telematico non genera più i due avvisi generici richiesti dall'utente; restano intatti gli avvisi specifici di superficie quando servono.
- `web/services/telematico_runtime.py`: i risultati della ricerca portale vengono arricchiti con match locale calcolato sui fascicoli IUSENTRA esistenti, usando `source_external_id` e confronto RG/anno/ufficio compatibile con il tipo di portale.
- `web/bootstrap/portali_acquisizione_routes.py`: nuovo endpoint leggero `/api/portali/<portale>/acquisizione/local-matches`, usato per arricchire i risultati arrivati dal Local Signer senza avviare preview, download documenti o importazioni.
- `web/templates/portale/acquisizione_wizard.html`: se il risultato è già presente, la card mostra `Pratica già presente`, il pulsante diventa `Aggiorna pratica` e la mappatura seleziona automaticamente la pratica locale compatibile.
- `web/templates/portale/acquisizione_wizard.html`: quando il risultato PST è univoco, l'apertura automatica resta leggera e non scarica subito i documenti via Local Signer; i documenti restano caricabili dal comando dedicato.
- `web/bootstrap/portali_acquisizione_routes.py`: i blocchi operativi di import PST e i messaggi di canale ufficiale assistito non vengono più sostituiti da errori generici.
- `web/services/telematico_runtime.py`: il preview PST scarta righe testuali senza forma documentale e deduplica il master/detail quando il deposito sintetico serve solo a raggruppare lo stesso documento.

Verifiche automatiche eseguite:

- `python -m py_compile web/services/telematico_runtime.py web/bootstrap/portali_acquisizione_routes.py web/bootstrap/telematico_surface_wiring.py web/services/react_telematico_bridge.py` -> OK;
- `python -m pytest tests/test_polisweb.py::test_acquisizione_wizard_pst_carica_documenti_local_signer_anche_in_modalita_assistita tests/test_polisweb.py::test_api_acquisizione_search_pst_marca_fascicolo_locale_da_aggiornare tests/test_polisweb.py::test_api_acquisizione_local_matches_pst_arricchisce_risultati_local_signer tests/test_react_shell.py::test_react_telematico_bridge_payload_minimo -q` -> `4 passed`;
- `python -m pytest tests/test_polisweb.py::test_portale_acquisizione_wizard_renderizza_javascript_valido -q` -> `1 passed`;
- `python -m pytest tests/test_portali_payload_import_ui.py -q` -> `32 passed`;
- `python -m pytest tests/test_polisweb.py -k "acquisizione or portale_acquisizione or portale_wizard" -q` -> `39 passed`;
- `python -m pytest tests/test_react_shell.py::test_react_telematico_bridge_payload_minimo -q` -> `1 passed`.

Stato server reale 2026-06-30: hotfix server-first copiato su Hetzner in `/opt/iusentra/repo` e nel container unico `iusentra-app`; `docker exec iusentra-app python -m py_compile ...` -> OK; dopo `docker restart iusentra-app`, `docker ps` mostra `iusentra-app` healthy e `https://app.iusentra.it/api/pronto` risponde `ok=true`, `timezone=Europe/Rome`, versione `2.253.137`. Il browser reale è stato aperto su `https://app.iusentra.it/portali/pst/acquisizione`, ma la pagina reindirizza a `https://app.iusentra.it/login?next=/portali/pst/acquisizione`: ricerca PST non ancora avviabile finché l'utente non completa l'accesso nella scheda visibile.

Stato verifica reale: codice e test mirati locali risultano coerenti. La prova materiale sul browser reale autenticato in produzione e sulla copia locale `127.0.0.1:8080` resta ancora da eseguire prima di dichiarare il flusso operativo concluso.

## Local Signer 1.6.86: avvio e aggiornamento automatico nella pagina PST - 2026-06-30

Richiesta utente: recuperare il comportamento già risolto nelle versioni precedenti, cioè Local Signer che si avvia e si aggiorna automaticamente dalla pagina `https://app.iusentra.it/portali/pst/acquisizione`, senza assistenza operativa dell'avvocato e senza testi tecnici visibili come endpoint, `fetch` o `XMLHttpRequest`.

Correzione applicata:

- `frontend/src/components/TelematicoSurfacePage.tsx`: il pulsante `Avvia e verifica` non usa più un iframe nascosto per `iusentra-local-signer://restart`; ora attiva il protocollo locale tramite link generato dal gesto reale del browser e poi ricontrolla il servizio.
- `frontend/src/components/TelematicoSurfacePage.tsx`: i dettagli tecnici di trasporto non vengono più composti nel messaggio utente. Il testo visibile resta governato e non espone URL locali, `fetch`, `xhr`, `XMLHttpRequest`, endpoint o diagnostica browser.
- `tests/test_react_shell.py`: aggiornati i guardrail per impedire il ritorno di `Endpoint provati`, `Dettaglio browser` e `XMLHttpRequest bloccato dal browser` nella superficie React.
- Local Signer distribuito come versione `1.6.86` con installer Windows `SetupLocalSigner-1.6.86.exe` e servizio locale aggiornabile dai sorgenti ufficiali serviti da IUSENTRA.

Verifiche automatiche eseguite:

- `pnpm --filter @iusentra/studio build` -> OK; bundle corrente `assets/TelematicoSurfacePage-BeJ-kLvh.js`;
- `python -m pytest tests/test_react_shell.py::test_react_wizard_pst_verifica_local_signer_dal_browser tests/test_react_shell.py::test_local_signer_verifica_avvia_autoaggiornamento_se_versione_vecchia -q` -> `2 passed`;
- controllo testuale sul bundle corrente pubblicato: nessuna occorrenza di `Endpoint provati`, `Dettaglio browser`, `XMLHttpRequest bloccato dal browser`, `fetch: Failed to fetch`, `xhr:`, `comando provati`, `Regia telematica da presidiare`, `Canale assistito`, `non usare scraping HTML`; presenti invece il messaggio pulito e il protocollo `iusentra-local-signer://restart`.

Hotfix produzione eseguito:

- pacchetto React pulito copiato su Hetzner in `/opt/iusentra/repo` e nel container unico `iusentra-app`;
- copiati anche `TelematicoSurfacePage.tsx`, `react_telematico_bridge.py`, sorgenti Local Signer e installer `1.6.86`;
- `docker restart iusentra-app` -> container `iusentra-app` healthy;
- `https://app.iusentra.it/api/pronto` -> `ok=true`, `timezone=Europe/Rome`, versione `2.253.137`;
- `https://app.iusentra.it/polisWeb/local-signer/setup/windows` -> `SetupLocalSigner-1.6.86.exe`, `content-length=393216`;
- `docker ps` -> un solo container applicativo, nome esatto `iusentra-app`.

Prova reale su Google Chrome dell'utente:

- pagina reale autenticata: `https://app.iusentra.it/portali/pst/acquisizione`;
- hard reload della scheda Chrome e ritorno allo `Step 1 - Accesso`;
- click su `Verifica Local Signer` con servizio attivo: UI visibile `Local Signer pronto`, `Local Signer rilevato su questo PC. La ricerca può usare il canale locale autorizzato.`, `ultima versione 1.6.86`, `rilevata 1.6.86`;
- nessun testo visibile con endpoint, `fetch`, `xhr`, `XMLHttpRequest`, `comando provati`, `Regia telematica da presidiare`, `Canale assistito` o `non usare scraping HTML`;
- processo locale fermato manualmente per test: `ping` su `127.0.0.1:27272` non raggiungibile;
- click reale su `Avvia e verifica` dalla stessa pagina Chrome: il protocollo locale ha riavviato Local Signer senza prompt operativo aggiuntivo; dopo pochi secondi `ping` tornato `ok=true`, versione `1.6.86`, e la UI è tornata a `Local Signer pronto`;
- processo dopo il riavvio automatico: un solo `python.exe` con `C:\Users\antmm\AppData\Roaming\IUSENTRA\LocalSigner\local_signer.py`;
- chiamata reale a `/update` del Local Signer: `ok=true`, `versione_corrente=1.6.86`, sorgenti aggiornati, riavvio automatico eseguito;
- controllo finale dopo update: un solo processo Local Signer, nessun `pythonw.exe` duplicato, `ping` ancora `ok=true`, versione `1.6.86`;
- nuovo click su `Verifica Local Signer`: UI ancora `Local Signer pronto`, versione `1.6.86`, zero testi tecnici o vecchie voci richieste dall'utente.

Stato operativo: server reale e Chrome reale dell'utente hanno confermato avvio da servizio fermo, aggiornamento endpoint e processo unico. Restano da completare, prima della chiusura formale del lavoro, riallineamento locale Docker su `127.0.0.1:8080`, commit, push dei branch gemelli, controlli GitHub richiesti e deploy ordinato sullo stesso commit.

## Local Signer 1.6.87: installazione Windows su profili utente con spazi - 2026-06-30

Richiesta utente: su un PC cliente l'installer arriva a `Il servizio non ha ancora risposto su http://127.0.0.1:27272`; il Local Signer quindi non parte dopo l'installazione.

Causa tecnica probabile individuata nel pacchetto 1.6.86: l'avvio immediato dell'installer passava `local_signer.py` a Python come stringa nuda. Su profili Windows con spazi nel percorso utente, per esempio `C:\Users\Studio Legale\...`, Python poteva ricevere il percorso spezzato e uscire prima di aprire la porta `27272`.

Correzione applicata:

- `tools/installa_local_signer_locale.ps1`: l'avvio immediato usa `-ArgumentList @($pythonScript)` sia per `python.exe` sia per `pythonw.exe`;
- `tools/local_signer.py` e `tools/dist/local_signer.py`: versione aggiornata a `1.6.87`;
- pacchetti rigenerati: `SetupLocalSigner-1.6.87.exe`, alias `SetupLocalSigner.exe`, `InstallaLocalSigner-1.6.87.ps1`, `.command`, `.run` e nota release;
- hash Windows `SetupLocalSigner-1.6.87.exe`: `CB8250451DD37B6188E64ED33E03D427C09B67D1C528B560444D17C057601005`.

Verifiche automatiche eseguite:

- `python -m pytest tests/test_local_signer.py::test_local_signer_dist_allineato_a_sorgente_e_installer_versionati tests/test_local_signer.py::test_local_signer_launcher_windows_usa_avvio_silenzioso tests/test_local_signer.py::test_installer_locale_windows_registra_protocollo_e_attesa_ping tests/test_build_dist.py::test_build_windows_ps1_include_versione_e_script_originale -q` -> `4 passed`;
- controllo pacchetti: `SetupLocalSigner-1.6.87.exe` e alias `SetupLocalSigner.exe` hanno lo stesso hash SHA256;
- controllo script versionato: `InstallaLocalSigner-1.6.87.ps1` contiene `-ArgumentList @($pythonScript)` e non l'avvio immediato con argomento nudo.

Diagnosi da fare sul PC cliente se il pacchetto 1.6.87 non risponde ancora:

- leggere `%APPDATA%\IUSENTRA\LocalSigner\local_signer.err.log`;
- verificare che esista un solo processo `python.exe`/`pythonw.exe` collegato a `local_signer.py`;
- controllare `Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 27272`;
- verificare il ping `http://127.0.0.1:27272/ping?light=1`.

## Acquisizione PST: avvio automatico Local Signer dal pulsante React - 2026-06-30

Richiesta utente: verificare se dalla pagina `https://app.iusentra.it/portali/pst/acquisizione` il servizio Local Signer si avvia automaticamente senza intervento manuale dell'avvocato.

Prova rapida su Windows:

- servizio fermato manualmente;
- ping `http://127.0.0.1:27272/ping?light=1` in timeout;
- chiamata diretta Windows `iusentra-local-signer://restart`;
- servizio riavviato e ping tornato `ok=true`, versione rilevata `1.6.86` sull'installazione locale di prova.

Esito: il protocollo locale registrato da Windows funziona. Il browser integrato Codex non è una prova valida per l'apertura dei protocolli esterni perché blocca le URL `iusentra-local-signer://` per policy di sicurezza; con click sulla pagina non è stato possibile dimostrare l'apertura del processo tramite quel browser.

Correzione applicata alla pagina React di acquisizione:

- `frontend/src/components/TelematicoSurfacePage.tsx`: il pulsante `Avvia e verifica` ora tenta il protocollo con iframe nascosto e link nascosto, allineandosi al metodo già usato nelle Impostazioni Local Signer;
- `tests/test_react_shell.py`: aggiunto guardrail statico perché il wizard PST mantenga entrambi i metodi di lancio del protocollo.

Verifiche eseguite:

- `python -m pytest tests/test_react_shell.py::test_react_wizard_pst_verifica_local_signer_dal_browser tests/test_local_signer.py::test_installer_locale_windows_registra_protocollo_e_attesa_ping tests/test_local_signer.py::test_local_signer_launcher_windows_usa_avvio_silenzioso -q` -> `3 passed`;
- `pnpm --filter @iusentra/studio typecheck` -> ok;
- `python scripts/react-migration/generate_api_contracts.py --check` -> contratti allineati;
- `pnpm --filter @iusentra/studio build` -> ok.

Stato: protocollo Windows verificato, correzione React pronta per deploy. La prova finale con Google Chrome reale del PC cliente resta da eseguire dopo deploy della pagina aggiornata perché il browser integrato non può aprire protocolli esterni.

## Local Signer 1.6.88: launcher VBS portabile e diagnosi cartella cliente - 2026-06-30

Richiesta utente: la cartella copiata dal PC cliente (`E:\LocalSigner`) mostra ancora che l'installazione non viene eseguita correttamente.

Diagnosi sulla cartella condivisa:

- `E:\LocalSigner\local_signer.py` è versione `1.6.83`, quindi non è il pacchetto aggiornato `1.6.87`;
- `E:\LocalSigner\start_local_signer.cmd --force --silent` avvia correttamente il servizio dalla copia condivisa e il ping risponde con `ok=true`, versione `1.6.83`;
- il problema non è l'eseguibilità del servizio in sé, ma l'aggiornamento/installazione che lascia il cliente su una copia vecchia o agganciata a un launcher creato con percorsi non più validi.

Correzione applicata al pacchetto `1.6.88`:

- `tools/installa_local_signer_locale.ps1`: `start_local_signer.vbs` non incorpora più il percorso assoluto del `.cmd`; calcola `start_local_signer.cmd` dalla propria cartella con `WScript.ScriptFullName` e `Scripting.FileSystemObject`;
- `tools/local_signer.py` e `tools/dist/local_signer.py`: versione aggiornata a `1.6.88`;
- pacchetti rigenerati: `SetupLocalSigner-1.6.88.exe`, alias `SetupLocalSigner.exe`, `InstallaLocalSigner-1.6.88.ps1`, `.command`, `.run` e nota release.

Stato prova reale:

- la copia condivisa `E:\LocalSigner` è stata avviata manualmente con il suo `start_local_signer.cmd` e ha risposto su `127.0.0.1:27272`;
- il pacchetto `1.6.88` non è stato promosso perché la prova d'installazione ha mostrato un modulo `local_signer_mod/security.py` non allineato al nuovo `local_signer.py`.

## Local Signer 1.6.89: installazione automatica reale e moduli allineati - 2026-06-30

Problema reale risolto:

- la cartella condivisa dal PC cliente `E:\LocalSigner` contiene ancora `local_signer.py` versione `1.6.83`;
- la copia `1.6.83` parte se avviata direttamente, quindi il servizio Python non era il punto rotto;
- il pacchetto successivo `1.6.88` è stato provato e scartato perché l'installazione copiava `local_signer.py` nuovo ma lasciava `local_signer_mod/security.py` vecchio, causando `ImportError: cannot import name 'is_allowed_origin_or_referer'`;
- lo stesso difetto avrebbe mascherato l'errore come "servizio non rilevato", senza spiegare che il processo cadeva prima di aprire `127.0.0.1:27272`.

Correzione applicata in `1.6.89`:

- `tools/build_local_signer_windows_exe.ps1` ora aggiorna anche `tools/dist/local_signer_mod/*.py`, oltre ai file inclusi nell'EXE IExpress;
- `tools/installa_local_signer_locale.ps1` genera un `start_local_signer.vbs` portabile che calcola il `.cmd` dalla propria cartella, senza percorso assoluto incorporato;
- lo stesso installer non resta più in attesa di `Invio` dopo il successo o negli errori automatici: la pausa è possibile solo impostando `IUSENTRA_LOCAL_SIGNER_KEEP_INSTALLER_OPEN=1` per debug;
- `tools/local_signer.py` e `tools/dist/local_signer.py` sono versione `1.6.89`;
- `SetupLocalSigner-1.6.89.exe` e alias `SetupLocalSigner.exe` hanno SHA256 `E9DC7EF5EE7958927F0B1D20844FD9F2FFCF57E6D7B41B3DEAFB84DC14646E9B`.

Prova reale eseguita sulla macchina locale Windows:

- eseguito `tools\dist\SetupLocalSigner-1.6.89.exe /Q`;
- l'installer è terminato con exit code `0`;
- `http://127.0.0.1:27272/ping?light=1` ha risposto `ok=true`, `versione=1.6.89`, `piattaforma=win32`;
- processo attivo verificato: `python.exe ...\IUSENTRA\LocalSigner\local_signer.py`;
- file installati verificati in `%APPDATA%\IUSENTRA\LocalSigner`: `local_signer.py` versione `1.6.89` e `local_signer_mod\security.py` con `is_allowed_origin_or_referer`.

Guardrail anti-regressione aggiunti:

- test che confronta `tools/dist/local_signer_mod/*.py` con `local_signer_mod/*.py`;
- test che verifica il contratto degli import da `local_signer_mod.security`;
- test che impedisce il ritorno della pausa `Read-Host` nel percorso normale dell'installer.

Stato: il pacchetto da pubblicare per il cliente è `1.6.89`; la `1.6.88` resta solo come diagnosi del difetto e non deve essere distribuita.

## Local Signer 1.6.90: prima installazione cliente e ping leggero - 2026-06-30

Richiesta utente: il problema non è sul PC di sviluppo, dove il Local Signer funziona, ma su un PC cliente con prima installazione. L'utente ha condiviso la cartella `E:\LocalSignerno\LocalSigner`.

Diagnosi sui file cliente:

- `E:\LocalSignerno\LocalSigner\local_signer.py` è versione `1.6.89`;
- nella cartella cliente sono presenti sia Python portatile (`python\python.exe`, `python\pythonw.exe`) sia `local_signer_mod`, incluso `security.py`;
- `installer.log` mostra installazioni ripetute con Python portatile scaricato, dipendenze installate, protocollo locale registrato e collegamento Startup creato;
- `local_signer.err.log` mostra che il servizio riceveva decine di richieste `HTTP GET /ping` tra le `13:15:34` e le `13:17:33`, ma l'installer concludeva comunque `Avvio non riuscito`;
- quindi il difetto reale non era la mancanza dei file principali in quella copia, ma il controllo finale dell'installer: usava `/ping` completo, che può interrogare certificati/token e non è un test corretto per dire se il servizio locale è partito.

Correzione applicata in `1.6.90`:

- `tools/installa_local_signer_locale.ps1`: `Wait-LocalSigner`, `Test-LocalSignerOnline` e il launcher Windows usano solo `http://127.0.0.1:27272/ping?light=1` per validare avvio e aggiornamento automatico;
- se il ping leggero fallisce davvero, l'installer scrive nel log cartella installata, Python selezionato, presenza dei file chiave, processo che occupa la porta `27272` e ultime righe di `local_signer.err.log`/`local_signer.out.log`;
- `web/services/telematico_runtime.py`: allineato anche il generatore legacy, così nessun percorso secondario torna al `/ping` completo;
- `frontend/src/components/TelematicoSurfacePage.tsx`: mantenuto il messaggio utente senza dettagli tecnici su `fetch`, `xhr` o endpoint;
- `web/blueprints/api_v1_react.py`: rimosso il riferimento pubblico al vecchio helper `.ps1` di Studio Telematico, mantenendo l'exe operativo.

Pacchetti generati:

- `SetupLocalSigner-1.6.90.exe`;
- alias `SetupLocalSigner.exe`;
- `InstallaLocalSigner-1.6.90.ps1`;
- `InstallaLocalSigner-1.6.90.command`;
- `InstallaLocalSigner-1.6.90.run`;
- hash SHA256 Windows: `483CA298C6D7CF221849BABE349077AE92B4B283DD51FFA3EF38C82F5CFF8F67`.

Prova reale eseguita sulla macchina locale Windows:

- eseguito `tools\dist\SetupLocalSigner-1.6.90.exe /Q`;
- log installazione: `Ping leggero Local Signer riuscito versione 1.6.90`;
- ping reale: `http://127.0.0.1:27272/ping?light=1` ha risposto `ok=true`, `versione=1.6.90`, `piattaforma=win32`;
- processo attivo: un solo `python.exe` collegato a `%APPDATA%\IUSENTRA\LocalSigner\local_signer.py`;
- la prova sul PC cliente reale resta da ripetere dopo deploy del pacchetto `1.6.90`, perché i file condivisi sono una copia diagnostica e non consentono di eseguire materialmente l'installer sulla macchina cliente dalla repository locale.

Verifiche automatiche eseguite:

- `python -m pytest tests/test_local_signer.py -q` -> verde;
- `python -m pytest tests/test_build_dist.py -q` -> verde;
- `python -m pytest tests/test_react_shell.py -q -k "telematico_scroll_usa_offset_topbar_non_scroll_into_view or import_studio_telematico_react_pubblica_exe_e_barra_avanzamento or local_signer"` -> verde.

Guardrail anti-regressione:

- test che vieta il ritorno del `/ping` completo nel controllo di avvio degli installer Windows;
- test che verifica il dist Local Signer e la diagnostica di avvio;
- test React sul messaggio Local Signer e sul flusso telematico.

## Presidio PEC deposito accettato e aggiornamento automatico RG - 2026-06-30

Richiesta utente: la PEC di accettazione deposito ricevuta deve risultare nel flusso del deposito e nel fascicolo, mostrando quando il deposito è stato registrato, da chi, quando è stato accettato e aggiornando automaticamente il numero RG ufficiale letto da `EsitoAtto.xml`.

Dati reali consultati:

- file PEC locale: `C:/Users/antmm/Downloads/pec_00119fb0a3713fdb69faaf7d.eml`;
- allegato tecnico: `EsitoAtto.xml`;
- `NumeroRuolo`: `1084/2026`;
- `IDBUSTA`: `152649431`;
- `CodiceEsito`: `2`;
- esito: `Accettazione manuale avvenuta con successo`;
- data esito ministeriale: `30/06/2026 08:44`;
- message-id deposito originario: `<jpec1329.20260630000219.66240.402.1.1@pec.aruba.it>`.

Modifiche applicate:

- `pct/pec_pipeline.py`: il testo ricevuta PCT ora conserva mittente PEC, destinatario PEC, data PEC in formato italiano, data esito in formato italiano, `Numero ruolo`, `IDBUSTA`, message-id del deposito originario e codice esito;
- `pct/pec_pipeline.py`: quando una ricevuta PCT forte contiene `NumeroRuolo`, il fascicolo collegato aggiorna automaticamente `numero_rg` e `anno_rg`; l'eventuale valore precedente viene annotato nelle note del deposito con la dicitura `RG fascicolo aggiornato da EsitoAtto.xml`;
- `web/services/react_fascicoli_bridge.py`: il payload React dei depositi espone `sentAt`, `acceptedAt`, `acceptedBy`, `registeredBy`, `registeredAt`, `roleNumber`, `receiptMessageId` e `sourceMessageId`, convertendo le date visibili in `Europe/Rome`;
- `frontend/src/components/FascicoliPage.tsx` e `frontend/src/components/FascicoliPage.css`: la sezione `Ricevute e cancelleria` mostra nella riga deposito e nello stato i fatti ufficiali principali: RG, IDBUSTA, data di accettazione, mittente PEC, utente che ha registrato e message-id del deposito.

Verifiche automatiche eseguite:

- `python -m pytest tests/test_pec_audit_pipeline.py::test_pct_deposit_receipts_upsert_one_fascicolo_card_and_no_duplicate_history tests/test_pec_audit_pipeline.py::test_pct_acceptance_updates_fascicolo_rg_and_react_deposit_facts -q` -> verde;
- `python -m pytest tests/test_pec_audit_pipeline.py::test_pct_esito_atto_fixtures_extract_strong_correlation_and_receipt_profile -q` -> verde;
- `npm --prefix frontend run typecheck` -> verde;
- parsing diretto del file reale `pec_00119fb0a3713fdb69faaf7d.eml` -> estratti `Numero ruolo: 1084/2026`, `IDBUSTA: 152649431`, `Data PEC: 30/06/2026 08:44`, `Data esito: 30/06/2026 08:44`.

Aggiornamento produzione eseguito dopo deploy `2.253.144`:

- tenant produzione: `studio-legale-giuseppe-montagnese`;
- fascicolo reale: `795C50AC`, `Marchetti c. MIM`;
- messaggio PEC presidiato: `pec_00119fb0a3713fdb69faaf7d`;
- pipeline rilanciata nel container `iusentra-app` con attore `codex-presidio-pec-rg`;
- report PEC rigenerato con `final_state=accepted_manually`, `NumeroRuolo=1084/2026`, `IDBUSTA=152649431`, `CodiceEsito=2`;
- fonte SQL produzione aggiornata: `fascicoli.numero_rg=1084`, `fascicoli.anno_rg=2026`;
- deposito registrato nel fascicolo: `F909FC53`, stato `ACCETTATO_CANCELLERIA`, `fonte_portale=PEC_PCT`, `id_deposito_esterno=152649431`;
- payload React produzione verificato nel container: la riga espone `acceptedAt=30/06/2026 08:44`, `acceptedBy=tribunale.vicenza@civile.ptel.giustiziacert.it`, `registeredBy=codex-presidio-pec-rg`, `roleNumber=1084/2026`, `receiptMessageId=<6E7707DF.01498C2D.174555AE.80D717CE.posta-certificata@legalmail.it>` e `sourceMessageId=<jpec1329.20260630000219.66240.402.1.1@pec.aruba.it>`.

Stato anti-regressione:

- il test `test_pct_acceptance_updates_fascicolo_rg_and_react_deposit_facts` fallisce se una PEC di accettazione finale non aggiorna il fascicolo da `NumeroRuolo`, non conserva i metadati ufficiali nella ricevuta o non li espone nel payload React;
- resta obbligatoria la prova visiva reale su `127.0.0.1:8080` dopo rebuild Docker locale, con apertura del fascicolo collegato e controllo della sezione `Ricevute e cancelleria`.

## Analisi QuickOrganizer: registri, menu PolisWeb e download fascicoli - 2026-06-30

Richiesta utente: analizzare Studio Legale Telematico/QuickOrganizer per capire struttura dei depositi, schemi ministeriali, registri consultazione fascicoli, importazione pratiche da PolisWeb, accesso diretto al PolisWeb, lettura fascicolo dal portale, scarico singoli documenti, scarico intero fascicolo e ricerca fascicoli per anno.

Fonti locali consultate:

- `C:/QuickOrganizer/QuickOrganizer.exe`;
- `C:/QuickOrganizer/QuickOrganizer.exe.config`;
- `C:/QuickOrganizer/QuickOrganizer.mdb`;
- `C:/QuickOrganizer/ListaUfficiGiudiziari.xml`;
- `C:/QuickOrganizer/QC_Uffici.xml`;
- sorgenti decompilati in `%TEMP%/quickorganizer_decompiled_full`, in particolare `FormMain.cs`, `WizardImportaPraticheDaPolisWeb.cs`, `PCT.cs`, `BrowserForm.cs`, `Common.cs`, `UfficioRegistroRuolo.cs` e `FormSentMailBee.cs`;
- cartella `C:/QuickOrganizer` con DLL, sottocartelle, certificati locali e risorse embedded.

Artefatti generati o aggiornati in `artifacts/react-migration`:

- `quickorganizer-indice-artefatti.md`;
- `catalogo-quickorganizer-depositi.md`;
- `quickorganizer-deposito-catalogo.json`;
- `xsd-quickorganizer-datiatto.md`;
- `quickorganizer-xsd-datiatto-manifest.json`;
- `quickorganizer-registri-consultazione-fascicoli.md`;
- `quickorganizer-registri-consultazione-fascicoli.json`;
- `quickorganizer-portale-lettura-download-fascicolo.md`;
- `quickorganizer-portale-lettura-download-fascicolo.json`;
- `quickorganizer-portali-polisweb-download.md`;
- `quickorganizer-database-fascicoli-pec.md`;
- `quickorganizer-firma-pin-sessioni.md`;
- `quickorganizer-pec-notifiche-ricevute.md`;
- `quickorganizer-confronto-certificati-codici.md`;
- `quickorganizer-risorse-dll-sottocartelle.md`;
- `lavoro-specializzazione-deposito-pec-fascicoli.md`.

Risultati tecnici principali:

- il catalogo depositi estratto da QuickOrganizer contiene 270 tipi in 6 macroaree;
- gli XSD non risultano distribuiti come file sciolti sotto `C:/QuickOrganizer`: QuickOrganizer usa classi generate dagli XSD ministeriali e metodi `Create_DatiAtto_*` dentro l'EXE;
- sono stati rilevati 148 metodi `Create_DatiAtto_*` e 56 mapping chiave deposito -> metodo DatiAtto;
- i registri consultazione rilevati coprono `SICID/CC`, `LAV/SIL`, `VG/SIVG`, `MIN/SIMIN`, `SIECIC` esecuzioni mobiliari, esecuzioni immobiliari e concorsuali, `SIGP/GDP`, `CASSCI`, `CASSPE` e registri UNEP;
- `Agrarie` e `Speciali` risultano tipi/filtro locali QuickOrganizer, senza combinazione JPW autonoma trovata nel catalogo XML;
- nel menu Studio Telematico la voce `Importa Pratiche dal PolisWeb` apre `ImportaPratichePolisWeb(-1)`, mentre `Cerca_Eventi_Polisweb` apre lo stesso wizard con `PCT.RicercaNuoviEventi=true`;
- il menu `Accesso al PolisWeb...` contiene azioni distinte: fascicolo d'ufficio, documenti fascicolo, eventi fascicolo, comunicazioni/notifiche, agenda PolisWeb, scadenze, scarico documenti, ricerca RG per costituzione, Cassazione civile, Cassazione penale e notifiche non perfezionate;
- la lettura del fascicolo dal portale parte da `RecuperaDatiFascicoloUfficio(..., showBrowser:true)` e poi `BrowserForm` seleziona i tab cercando link con `storicofascicolo`, `documentifascicolo` o `comunicazionifascicolo`;
- per accesso diretto PST QuickOrganizer costruisce URL con `registroRicerca`, `ufficioRicerca` e `ruoloRicerca={ruolo}@{ruolo}`;
- per `Scarica documenti dal PolisWeb`, `BrowserForm` intercetta download WebView2 di PDF, RTF, TXT, immagini, XML, P7M, ZIP, RAR e ricevute PagoPA, con destinazioni pratica, desktop o calcolo hash;
- lo scarico di un intero fascicolo non risulta un endpoint unico: QuickOrganizer lo tratta come iterazione/batch di documenti e allegati selezionati;
- la ricerca per anno usa il numero ruolo quando presente; quando manca, il wizard può usare `numero=0` e `anno=cboAnno.Text` sui metodi/registri che lo prevedono;
- per SIECIC restano da rispettare `idRuoloJPW`/`idDfa` reali quando richiesti: non vanno inventati;
- i certificati uffici non sono tutti embedded nell'EXE: QuickOrganizer ha certificati locali limitati, un vecchio `pst.cer` embedded e logica per scaricare certificati PST d'ufficio tramite catalogo servizi.

Implicazioni operative per IUSENTRA:

- separare in React due azioni: `Importa/sincronizza da PolisWeb` e `Accedi al PolisWeb`;
- il flusso `Accedi al PolisWeb` deve essere portale assistito con certificato/sessione dell'utente, non sostituto silenzioso dei servizi ufficiali;
- `Scarica intero fascicolo` deve essere batch governato di download singoli con progress, deduplica `idCat/IdDocumento/hash`, ripresa su errore e salvataggio SQL tenant-aware;
- ogni documento scaricato deve portare tenant, fascicolo, ufficio, registro, ruolo, origine portale, id documento, hash, data italiana e stato download;
- la ricerca fascicoli deve indicizzare RG, anno, ufficio, registro, oggetto, parti, documenti, PEC, ricevute, notifiche e scadenze;
- il presidio PEC può migliorare usando la struttura QuickOrganizer `PRATICHE`, `TESTI`, `EMAILS`, `AGENDA` e `TAVOLA`, ma mantenendo SQL/PostgreSQL come fonte operativa e JSON solo mirror;
- il deposito già provato realmente con accettazione cancelleria non va indebolito: questi artefatti sono mappa di estensione e confronto, non sostituzione dei guardrail esistenti.

Verifiche tecniche eseguite:

- `python -m py_compile scripts/generate_quickorganizer_analysis_artifacts.py`;
- `python scripts/generate_quickorganizer_analysis_artifacts.py`;
- controllo JSON dei nuovi file `quickorganizer-registri-consultazione-fascicoli.json` e `quickorganizer-portale-lettura-download-fascicolo.json`.

Stato verifica reale: non verificato su macchina reale. In questa tranche non è stato aperto il portale PST con certificato dell'utente e non è stata modificata/provata la UI IUSENTRA su `127.0.0.1:8080`; prima di trasformare queste mappe in funzione utente serviranno browser reale, sessione portale/certificato, salvataggio su fascicolo e prova visiva React.

## Anteprima pannello tipi deposito da Studio Telematico - 2026-06-30

Richiesta utente: iniziare l'integrazione del deposito con un pannello visibile prima della conferma definitiva, usando tutta la logica e tutta la struttura letta da Studio Telematico/QuickOrganizer. Il deposito reale già provato con accettazione cancelleria resta blindato e copre un solo caso: gli altri casi devono derivare dal catalogo completo Studio Telematico, non da scelte manuali o memoria.

File applicativi toccati in anteprima:

- `frontend/src/components/FascicoliPage.tsx`;
- `frontend/src/components/FascicoliPage.css`;
- `frontend/src/data/quickorganizer_deposito_catalogo_ui.json`;
- `tests/test_regia_ui_react.py`.

Scelta tecnica:

- il catalogo UI è generato dal file di analisi `artifacts/react-migration/quickorganizer-deposito-catalogo.json`;
- il file deployabile vive in `frontend/src/data/quickorganizer_deposito_catalogo_ui.json`, così il frontend builder Docker lo include senza dipendere da `artifacts/`;
- il catalogo viene caricato con import dinamico, quindi il chunk `quickorganizer_deposito_catalogo_ui` resta separato dal bundle principale `FascicoliPage`;
- il pannello è inserito nella sezione React `2. Documenti da inviare` del flusso `Prepara deposito`;
- i tre campi compatti sono `Macroarea`, `Categoria` e `Deposito`;
- i pulsanti `Schema` ed `Esplodi tutto` mostrano logica Studio Telematico, controlli automatici, documenti attesi e albero completo;
- una voce reale di QuickOrganizer, `Procedimenti concorsuali > Atti del Curatore`, era priva di chiave tecnica; non viene scartata, ma normalizzata con chiave stabile generata `studio-telematico::procedimenti-concorsuali-atti-del-curatore::186`, per non perdere nessuno dei 270 tipi.

Copertura catalogo verificata:

- totale mostrato in UI: `270` tipi;
- macroaree mostrate: `6`;
- albero espanso: `270` pulsanti deposito;
- macroaree viste nell'albero: `Contenzioso civile, Lavoro, Minorenni e Volontaria giurisdizione`, `Corte di Cassazione (civile)`, `Giudice di Pace`, `Procedimenti concorsuali`, `Processo esecutivo`, `UNEP - Ufficio Notificazioni, Esecuzioni e Protesti`;
- caso anomalo verificato: `Procedimenti concorsuali > Atti del Curatore > Atti del Curatore`;
- per il caso anomalo la UI mostra registro `SIECIC / FALL`, canale `SIECIC concorsuali`, trasporto `Atto.msg, IndiceBusta.xml, DatiAtto.xml.p7m, Atto.enc e PEC cancelleria`, controlli su ufficio, registro, codice deposito/oggetto, atto principale, firma digitale, DatiAtto, IndiceBusta, Atto.enc, PEC cancelleria e dati procedura quando richiesti.

Verifiche automatiche e build eseguite:

- `npm --prefix frontend run typecheck`;
- `python -m pytest tests\test_regia_ui_react.py -q`;
- `git diff --check`;
- `npm --prefix frontend run build`;
- `docker compose build app`;
- `docker compose up -d app`;
- `Invoke-WebRequest http://127.0.0.1:8080/api/pronto`, esito `ok=true`, versione `2.253.144`, timestamp `2026-06-30T18:53:36+02:00`;
- controllo asset catalogo su `http://127.0.0.1:8080/static/react/assets/quickorganizer_deposito_catalogo_ui-BLmCqhBA.js`, HTTP `200`.

Prova reale locale eseguita su browser integrato visibile:

- URL: `http://127.0.0.1:8080/fascicoli/DC5BF1DB/deposito/prepara?preview_catalogo=270_20260630#proposta-busta`;
- browser aggiornato al bundle `index-Ce7NEOVq.js`, dopo refresh forzato per eliminare il bundle precedente dalla memoria;
- cliccati i campi `Macroarea`, `Categoria` e `Deposito`;
- selezionato `Procedimenti concorsuali (18)`, `Atti del Curatore (1)`, `Atti del Curatore`;
- cliccati `Schema` e `Esplodi tutto`;
- verificato `treeButtonCount=270`;
- verificati hover/focus/scroll: il pulsante `Compatta` mantiene contrasto leggibile, focus su `BUTTON`, scroll interno albero `treeScrollTop=980`, nessun salto di layout rilevato nel controllo;
- controllo responsive con viewport temporanee `768x900` e `390x844`: nessun overflow orizzontale su pannello, controlli o albero; conteggio albero sempre `270`; viewport ripristinata dopo il test.

Stato operativo:

- anteprima visibile e provata su macchina reale locale;
- non ancora committata, pushata o distribuita su Hetzner perché l'utente ha chiesto di vederla prima e dare conferma dopo;
- la selezione del tipo deposito, in questa tranche, è pannello di anteprima e lettura logica: il collegamento definitivo a comportamento backend, codice oggetto, schema DatiAtto ministeriale, regole documentali bloccanti, Local Signer, invio PEC locale e presidio ricevute va eseguito solo dopo conferma utente;
- la prova reale già accettata dalla cancelleria non è stata modificata né indebolita.

## Integrazione catalogo Studio Telematico nel deposito IUSENTRA - 2026-06-30

Richiesta utente: integrare tutto prendendo le informazioni da Studio Telematico/QuickOrganizer e dalle fonti ministeriali, senza indebolire il caso reale già provato con accettazione dalla cancelleria.

File applicativi aggiornati in questa tranche:

- `pct/data/cataloghi/quickorganizer_depositi_studio_telematico.json`: copia tecnica condivisa del catalogo estratto, 270 tipi in 6 macroaree;
- `pct/deposito_telematico_catalogo.py`: normalizzazione backend del catalogo, regole canale, fonti ufficiali, payload operativo e guardrail invio;
- `web/services/react_fascicoli_bridge.py`: il dettaglio React del fascicolo espone `depositCatalog` quando si caricano deposito/regia;
- `web/blueprints/api_v1_react.py`: nuova route autenticata `/api/v1/ui/telematico/depositi/catalogo`, con risoluzione facoltativa della singola chiave;
- `web/bootstrap/deposito_routes.py`: download busta, indice e invio PEC risolvono la chiave catalogo lato backend e non si fidano solo dei campi inviati dal browser;
- `frontend/src/fascicoliData.ts`: contratto TypeScript `FascicoloDepositCatalog`;
- `frontend/src/components/FascicoliPage.tsx` e `.css`: il pannello nella sezione `2. Documenti da inviare` usa il catalogo API/backend, conserva la scelta in `selectedDepositTypeKey` e la invia nei payload di classificazione, indice, prova e invio;
- `tests/test_deposito_telematico_catalogo.py` e `tests/test_regia_ui_react.py`: guardrail su catalogo, route, regole canale e UI React.

Fonti ministeriali collegate nel catalogo backend:

- PST - Specifiche Tecniche ex art. 34 DM 44/2011, provvedimento DGSIA 7 agosto 2024: `https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC3429`;
- Normattiva - Decreto Ministero Giustizia 21 febbraio 2011, n. 44: `https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=011G0087`;
- PST - XSD ufficiali Processo Civile Telematico: `https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC1579`;
- PST - Portale Deposito atti Penali, specifiche tecniche PPT/PDP: `https://pst.giustizia.it/PST/resources/cms/documents/Specifiche_Tecniche_PPT_11.07.2023_post_DM_2023_signed.pdf`;
- Giustizia Amministrativa - PAT/Formweb: `https://www.giustizia-amministrativa.it/-/152174-737`;
- Gazzetta Ufficiale - PTT/SIGIT: `https://www.gazzettaufficiale.it/eli/id/2023/05/03/23A02531/SG`.

Regole operative introdotte:

- i tipi `SICID`, `SIECIC`, `SIGP/Giudice di Pace` e `Cassazione civile` usano policy `pct_civile_dm44`: `DatiAtto.xml`, `DatiAtto.xml.p7m`, `IndiceBusta.xml`, `Atto.msg`, `Atto.enc`, certificato PST `.cer`, Local Signer e PEC locale dal PC dell'avvocato;
- i tipi `UNEP` non possono essere preparati come deposito PCT civile: non attivano `Atto.enc` e vengono bloccati dal pannello PCT con messaggio che rinvia al flusso notifiche/UNEP;
- la scelta selezionata nel menu compatto viene rimandata al backend come `tipo_deposito_telematico_key`, `label`, `channel`, `registry`, `policy` e `schema_status`;
- il backend risolve di nuovo la chiave con `resolve_deposit_type_payload()` e sovrascrive `tipo_atto`/`codice_registro` con i valori del catalogo normalizzato;
- se la chiave non esiste nel catalogo backend, la rotta risponde con blocco esplicito;
- se la policy catalogo indica che il tipo non può produrre una busta PCT conforme, `genera-busta` e `invia-pec` rispondono con `package_ready=false` e motivo puntuale;
- l'invio PEC resta locale: nessuna modifica abilita invio SMTP server-side per depositi o notifiche legali.

Limite tecnico dichiarato e presidiato:

- IUSENTRA ha già il trasporto forte `Atto.msg`/`DatiAtto.xml.p7m`/`IndiceBusta.xml`/`Atto.enc`, ma il generatore ministeriale schema-specifico non copre ancora tutti i 270 tipi;
- il catalogo distingue i tipi selezionabili dai tipi realmente inviabili: per ora il generatore ministeriale governato è marcato come supportato solo dove la radice attuale è compatibile;
- i tipi PCT non ancora coperti da generatore `DatiAtto` specifico restano visibili e selezionabili, ma l'invio reale viene bloccato con messaggio esplicito;
- il caso reale già accettato dalla cancelleria non viene generalizzato artificialmente agli altri 269 casi e non viene indebolito.

Stato verifica:

- test automatici eseguiti: `python -m pytest tests/test_deposito_telematico_catalogo.py tests/test_regia_ui_react.py tests/test_deposito_guidato.py -k "pst_xsd_sici_20260611_tracciato_come_anticipazione_non_in_esercizio or catalogo_studio_telematico or catalogo_normalizza or catalogo_unep or api_e_rotte_busta or fascicoli_deposito" -q` con `5 passed`, `npm --prefix frontend run typecheck`, `npm --prefix frontend run build`;
- copia reale locale ricostruita con `docker compose build app` e `docker compose up -d app`; `/api/pronto` su `http://127.0.0.1:8080` ha risposto `ok=true`, versione `2.253.144`, timestamp finale `2026-06-30T20:38:30+02:00`, fuso `Europe/Rome`;
- prova reale su browser integrato visibile eseguita il `30/06/2026` su `http://127.0.0.1:8080/fascicoli/DC5BF1DB/deposito/prepara#proposta-busta`: visto `#root`, sezione `2. Documenti da inviare`, pannello `Catalogo Studio Telematico: 270 tipi in 6 macroaree`, nessuna vecchia anteprima statica;
- cliccati materialmente i campi `Macroarea`, `Categoria`, `Deposito`, i pulsanti `Schema`, `Esplodi tutto`/`Compatta`; verificati focus/hover leggibili e assenza di overflow orizzontale;
- caso `Atto di Citazione (in Appello)`: selezionabile ma `Da completare`, blocco esplicito su generatore `DatiAtto` ministeriale specifico prima dell'invio reale;
- caso `Ricorso (generico)`: `Operativo`, nessun blocker catalogo, trasporto PCT con `DatiAtto.xml.p7m` e `Atto.enc`;
- caso `UNEP - Richiesta di notifica di atto Civile (a debito)`: `Da completare`, canale notifiche/UNEP separato, `Atto.enc` non richiesto, blocker esplicito per non trattarlo come deposito PCT civile;
- `Schema` + `Esplodi tutto`: verificata presenza delle macroaree `Corte di Cassazione (civile)`, `Giudice di Pace`, `Procedimenti concorsuali`, `Processo esecutivo`, `UNEP`, voce `Ricorso (generico)` e pagamento UNEP;
- responsive riprovato con viewport `768x900` e `390x844`: nessun overflow, i tre menu su mobile si impilano a larghezza leggibile (`279px` circa), viewport ripristinata dopo il test.
- dopo la pulizia UTF-8 di `frontend/src/components/FascicoliPage.tsx`, ripetuti build, Docker locale e campione browser: pannello senza mojibake, `Ricorso (generico)` operativo, `UNEP` separato dal PCT civile, mobile ancora senza overflow.

Aggiornamento fonti ministeriali 2026-06-30:

- scaricati e letti gli XSD SICI preview `XSD_POL27A_11_06_2026.zip` dalla pagina PST `https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC4933`: `156` XSD estratti e archiviati in `docs/specs/ministero/xsd/2026-06-11-sici-preview/XSD_POL27A_11_06_2026/`;
- letta la nota ministeriale `modifiche_XSD_SICI_20260611.pdf`: nuovo atto `RichiestaVerbaleSINDACA` e nuovo codice oggetto `110046`; in IUSENTRA restano tracciati come preview/non in esercizio, quindi non abilitano ancora un deposito reale;
- scaricati e letti gli XSD Cassazione preview `XSD_Cassazione_20260611.zip` dalla pagina PST `https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC4951`: `116` XSD estratti e archiviati in `docs/specs/ministero/xsd/2026-06-15-cassazione-preview/XSD_Cassazione_20260611/`;
- aggiornato il catalogo PST versionato `pct/pst_catalog.py` e il payload deposito `pct/deposito_telematico_catalogo.py` con `ministerialXsdChannels` e `ministerialSchemaEvidence`, mantenendo il blocco anti falso-verde sulle fonti preview;
- file settoriale creato: `artifacts/react-migration/fonti-ministeriali-deposito-2026-06-30.md`.

Aggiornamento CI/governance 2026-06-30:

- dopo il push dello SHA `8ae954e`, GitHub ha bloccato `quality-gates` perché `web/bootstrap/deposito_routes.py` era salito a `1075` righe oltre il limite governance `1000`;
- la logica nuova non è stata rimossa: è stata estratta in moduli dedicati `web/services/deposito_catalogo_runtime.py`, `web/bootstrap/deposito_prepara_routes.py` e `web/bootstrap/deposito_esito_routes.py`;
- `web/bootstrap/deposito_routes.py` è rientrato a `972` righe, mantenendo il flusso React-first e il fallback legacy governato;
- controlli locali dopo il refactor: `python tools/check_repo_governance.py` -> OK; `python -m compileall -q web/bootstrap/deposito_routes.py web/bootstrap/deposito_prepara_routes.py web/bootstrap/deposito_esito_routes.py web/services/deposito_catalogo_runtime.py pct/deposito_telematico_catalogo.py` -> OK; test mirati deposito/catalogo -> `5 passed`;
- il refactor non abilita invio PEC server-side e non modifica le regole `Atto.enc`, Local Signer, PST `.cer` o blocco anti falso-verde dei 270 tipi.

## Generatore busta guidato dal tipo deposito QuickOrganizer - 2026-06-30

Richiesta utente: creare anche il generatore busta in base a quanto trovato in Studio Telematico/QuickOrganizer e in base al tipo deposito selezionato, senza usare messaggi generici o strade alternative.

Analisi tecnica incorporata:

- la nuova lettura dell'eseguibile ha corretto il mapping precedente: il vecchio catalogo runtime associava alcune chiavi a troppi `Create_DatiAtto_*`, mentre la nuova estrazione legge `664` casi `AttoDaInviareKey` e `148` metodi `Create_DatiAtto_*`;
- il catalogo runtime `pct/data/cataloghi/quickorganizer_depositi_studio_telematico.json` viene ora rigenerato dallo script `scripts/generate_quickorganizer_analysis_artifacts.py`, insieme agli artifact di analisi, così il prodotto non usa una matrice diversa dalla documentazione;
- per ogni tipo deposito vengono portati nel backend metodi QuickOrganizer, root `DatiAtto`, flag menu, dati richiesti e oggetti fissi quando rilevati;
- esempi verificati in runtime: `Introduttivi_SICID::Citazione` -> `Create_DatiAtto_Introduttivi_SICID_Cartabia_Citazione` e root `IntroduttiviSicid.Citazione`; `Parte_SICID::DepositoDocumentiRichiesti` -> root `Parte.ProduzioneDocumentiRichiesti`; `Parte_ESECUZIONI_SIECIC::AttoIntervento` -> root `ParteSiecicEsecuzioni.AttoIntervento`; `Parte_CASSAZIONE::Ricorso` -> root `ParteCassazione.Ricorso`.

Codice aggiornato:

- `pct/deposito_telematico_catalogo.py`: ricava `generatorClass`, root ministeriale, modalità e dati richiesti dal mapping reale QuickOrganizer; quando il root non contiene la classe, la ricava dal metodo `Create_DatiAtto_*`;
- `web/services/deposito_catalogo_runtime.py`: passa a `DatiBusta` anche `datiatto_required_data`;
- `web/bootstrap/deposito_routes.py`: `genera-busta` e `invia-pec` usano i dati `DatiAtto` risolti dal catalogo backend;
- `web/services/deposito_anagrafica_ministeriale.py`: genera `AnagraficaProcedimento` non solo per il ricorso base, ma per gli introduttivi e Cassazione, usando il namespace della famiglia quando noto;
- `pct/busta.py`: il generatore `DatiAtto.xml` seleziona root e namespace in base a `datiatto_generator_class`, `datiatto_root_name` e `datiatto_generator_mode`; gli introduttivi generano destinazione/oggetto/anagrafica, gli atti in corso causa generano riferimento procedimento, Cassazione usa il ramo dedicato con anagrafica.

Regola esplicita sui dati anagrafici non bloccanti:

- CAP, via, civico, comune, città, provincia, indirizzo cliente e indirizzo studio non sono requisiti bloccanti per la generazione della busta;
- se presenti vengono scritti nell'anagrafica, se assenti restano vuoti senza fermare il deposito;
- restano bloccanti solo i dati essenziali già necessari al `DatiAtto` ministeriale: codice fiscale cliente, controparte, codice fiscale controparte quando non risolvibile da dati noti, codice fiscale/cognome avvocato e i requisiti specifici del tipo deposito come data citazione o numero/anno RG.

Guardrail automatici eseguiti:

- `python -m py_compile pct\busta.py pct\deposito_telematico_catalogo.py web\services\deposito_anagrafica_ministeriale.py web\services\deposito_catalogo_runtime.py web\bootstrap\deposito_routes.py scripts\generate_quickorganizer_analysis_artifacts.py`;
- `python scripts\generate_quickorganizer_analysis_artifacts.py`: `270` tipi, `6` macroaree, `57` namespace XML, `148` metodi `Create_DatiAtto_*`, `664` mapping chiave/metodo;
- `python -m pytest tests\test_busta.py tests\test_deposito_anagrafica_ministeriale.py tests\test_deposito_telematico_catalogo.py -q --tb=short` -> `41 passed`.

Stato verifica:

- verifica automatica completata sul perimetro catalogo/generatore/anagrafica;
- non verificato su macchina reale per questa tranche finché la copia `127.0.0.1:8080` non viene aggiornata e il pannello deposito aperto nel browser reale non viene ricaricato e cliccato.
## Pulizia UI da riferimenti tecnici e nomi del vecchio gestionale - 2026-06-30

Richiesta utente: nella UI non devono comparire riferimenti a Studio Telematico o QuickOrganizer e non devono essere mostrati dettagli tecnici come nomi interni di file, schemi, certificati o sigle di trasporto.

Modifiche applicate:

- nel pannello `Prepara deposito`, sezione `2. Documenti da inviare`, il menu del tipo deposito mostra area, categoria, deposito, controlli automatici e documenti attesi con linguaggio utente;
- rimossi dalla resa visibile i riferimenti `Logica Studio Telematico`, `Catalogo Studio Telematico`, `DatiAtto`, `IndiceBusta`, `Atto.msg`, `Atto.enc`, `AES`, `.cer`, `PST` tecnico, `schema`, `hash`, `slot`, `token` e codici ufficio non necessari;
- gli stati di avanzamento dei pulsanti usano passaggi leggibili: controllo dati deposito, firma controlli, indice documenti, preparazione pacchetto e verifica finale;
- la modale PIN firma parla di `firma dati deposito` e `pacchetto finale`, senza mostrare il nome del file interno;
- la bozza PEC parla di `pacchetto di deposito telematico`, senza esporre il nome tecnico dell'allegato;
- i messaggi provenienti da backend, prova pacchetto, compatibilità, blocchi e Local Signer passano da normalizzazione UI prima di essere mostrati;
- la voce amministrativa e la pagina di import pratiche sono state rinominate in `Importa pratiche`, lasciando invariati route, permessi e compatibilità interne.

Guardrail aggiornati:

- `tests/test_regia_ui_react.py` ora presidia la resa pulita del deposito e impedisce il ritorno dei vecchi messaggi tecnici nel componente React;
- `tests/test_react_shell.py` e `tests/test_data_flow_contract.py` presidiano la nuova etichetta `Importa pratiche` sulla rotta esistente;
- il motore tecnico e gli artifact di analisi restano disponibili nei file di lavoro, ma non devono essere esposti nella UI operativa.

Stato verifica:

- test e prova reale devono essere rieseguiti dopo rebuild locale Docker su `127.0.0.1:8080`;
- il lavoro non va dichiarato chiuso finché la pagina reale non viene ricaricata e controllata visivamente nel browser integrato senza riferimenti visibili al vecchio gestionale e senza dettagli tecnici nel pannello deposito.

Aggiornamento 30/06/2026 23:44 (Europe/Rome):

- seconda lettura metadata di `C:\QuickOrganizer\QuickOrganizer.exe`: assembly `QuickOrganizer, Version=26.21.0.0`, `4394` tipi caricati, `576` tipi collegati a busta, deposito e schema;
- risorse embedded utili confermate: `ListaUfficiGiudiziari.xml`, `QC_Uffici.xml`, risorse `FormSentMailBee`, `FormDepositaConSoftwareEsterno`, `PoliswebRole`, `QualifiedCertificate`, `WizardImportaPraticheDaPolisWeb`, oltre a risorse contabili XML/XSLT;
- namespace schema più presenti nell'EXE: `CurSiecicConcorsuali` `88`, `ParteSiecicConcorsuali` `87`, `Atti_UNEP` `73`, `IntroduttiviSiecicConcorsuali` `68`, `IntroduttiviSicid` `50`, `Parte` `34`, `ParteCassazione` `29`, `ParteSiecicEsecuzioni` `20`, `ProfSiecicConcorsuali` `17`, `ProfSiecicEsecuzioni` `15`, `CusSiecicEsecuzioni` `14`, `CorsoCausa_SIGP` `12`;
- confermato contratto comune delle buste: `IndiceBusta` con `AttoPrincipale` e `Any`, riferimenti allegati tramite ID, `DepositoComplementare` con `RefId`, famiglie corso causa con `procedimento`, `riferimento`, `RefId`, `urgente`;
- correzione incorporata subito in IUSENTRA: i generatori `AttoSistema...` hanno `destinazione` e `IndiceBusta`, non `procedimento`; quindi il generatore non chiede numero/anno RG per questi root;
- codice aggiornato in `pct/deposito_telematico_catalogo.py` e `pct/busta.py`: riconoscimento operativo di `AttoSistemaSicid`, `AttoSistemaSiecic`, `AttoSistema_SIGP` nel parser root e nei metodi `Create_DatiAtto_*`, nuova modalità `sistema_destinazione`, namespace sistema per le tre famiglie, test anti-regressione `test_catalogo_atto_sistema_e_operativo_senza_numero_rg_obbligatorio` e `test_dati_atto_ministeriale_atto_sistema_usa_destinazione_senza_rg`;
- testi utente import pratiche corretti: i messaggi di errore/avviso non mostrano più cartelle tecniche `ATTI`/`EMAILS`, ma parlano di documenti e comunicazioni;
- guardrail mirati eseguiti: `python -m py_compile pct\busta.py pct\deposito_telematico_catalogo.py web\services\quickorganizer_import.py`; `python -m pytest tests\test_busta.py::test_dati_atto_ministeriale_atto_sistema_usa_destinazione_senza_rg tests\test_busta.py::test_dati_atto_ministeriale_catalogo_siecic_esecuzioni_usa_procedimento tests\test_deposito_telematico_catalogo.py tests\test_quickorganizer_import.py::test_import_studio_telematico_legge_zip_con_sole_cartelle_senza_errore_generico -q --tb=short` -> `7 passed`; `python -m pytest tests\test_deposito_telematico_catalogo.py::test_catalogo_atto_sistema_e_operativo_senza_numero_rg_obbligatorio tests\test_deposito_telematico_catalogo.py::test_catalogo_normalizza_chiave_mancante_e_canali_pct tests\test_busta.py::test_dati_atto_ministeriale_atto_sistema_usa_destinazione_senza_rg -q --tb=short` -> `3 passed`;
- prova reale locale ancora da ripetere dopo rebuild Docker su `127.0.0.1:8080`: non dichiarare chiuso il flusso finché non sono stati visti deposito e import pratiche nel browser integrato.

Aggiornamento 01/07/2026 00:20 (Europe/Rome):

- rebuild locale completato su copia reale Docker: `docker compose build app`, `docker compose up -d app`, container `iusentra-app` healthy su `127.0.0.1:8080`;
- `/api/pronto` locale ha risposto `ok=true`, versione `2.253.144`, timestamp `2026-07-01T00:06:00+02:00`, fuso `Europe/Rome`;
- guardrail automatici ripetuti: `npm --prefix frontend run typecheck`; `npm --prefix frontend run build`; `python -m pytest tests\test_busta.py::test_dati_atto_ministeriale_atto_sistema_usa_destinazione_senza_rg tests\test_deposito_telematico_catalogo.py::test_catalogo_atto_sistema_e_operativo_senza_numero_rg_obbligatorio tests\test_regia_ui_react.py -q --tb=short` -> `7 passed`;
- prova reale nel browser integrato visibile su `http://127.0.0.1:8080/fascicoli/DC5BF1DB/deposito/prepara#proposta-busta`: visto bundle React aggiornato, sezione `2. Documenti da inviare`, menu `Tipo deposito`, catalogo `270 tipi disponibili in 6 aree`, nessun riferimento visibile a Studio Telematico, QuickOrganizer, `DatiAtto`, `Atto.enc`, `Atto.msg`, `IndiceBusta`, `PKCS`, `AES256`, `Codice PST`, `ATTI` o `EMAILS`;
- corretto subito il residuo visibile `Deposito deposito telematico`, poi ricaricato il browser con cache busting e verificato il testo finale `Deposito telematico: il software deve risolvere ufficio, registro, codice oggetto, firme, busta e ricevute`;
- clic reali eseguiti su `Dettagli`, `Esplodi tutto`, `Macroarea`, `Categoria`, `Deposito`; confermata la presenza delle 6 macroaree e l'elenco esteso dei tipi;
- selezionate nel menu compatto le macroaree `Giudice di Pace`, `Corte di Cassazione (civile)`, `Procedimenti concorsuali`, `Processo esecutivo`, `UNEP` e ritorno a `Contenzioso civile`: nessun riferimento vietato e nessun overflow; per UNEP la UI passa al comportamento separato notifiche/UNEP, non al deposito PCT civile;
- verificata l'icona `Modifica nome` accanto a `Visualizza` e `Scarica originale` per `decretoGenerico.pdf` e gli altri documenti: il click apre il campo `Nuovo nome file decretoGenerico.pdf` senza uscire dal flusso;
- verificata la pagina `http://127.0.0.1:8080/importa-pratiche`: titolo `Importa pratiche`, testi su pratiche, documenti e comunicazioni, nessun nome visibile dei programmi sorgente e nessuna cartella tecnica `ATTI`/`EMAILS`;
- responsive materiale ripetuto con viewport `1366x900`, `768x900` e `390x844`: deposito e import pratiche senza overflow orizzontale, testi leggibili, catalogo 270 tipi presente su tutti i formati, viewport ripristinata al termine.

## Presidio documentale udienze da fascicolo - 2026-07-03

Richiesta utente: i documenti gia' presenti nel fascicolo devono essere letti automaticamente per recuperare udienze, trattazioni scritte e collegamenti audiovisivi solo quando il fascicolo non ha gia' una scadenza prefissata da PEC, PST o operatore.

Modifiche applicate:

- il provider tecnico del controllo e' `fascicolo_documenti_audit`, collegato al presidio PEC ma distinguibile dai messaggi PEC;
- il job `pec_audit_pipeline_workers` esegue anche il presidio documentale con lotto piccolo di default (`IUSENTRA_PEC_DOCUMENT_PRESIDIO_LIMIT=10`);
- il budget del job riguarda i documenti nuovi o modificati, non il numero di fascicoli: un fascicolo gia' presidiato viene saltato e il giro prosegue al fascicolo successivo;
- prima di indicizzare Lex AI vengono controllati `data_prossima_udienza`, `data_prima_udienza`, attivita' future del fascicolo e scadenziario aperto;
- se esiste gia' una scadenza futura, il report registra `skipped_prefixed_deadline` e non crea duplicati;
- se il documento produce una data valida, il flusso continua a salvare scadenziario, agenda, attivita' fascicolo, link udienza da remoto e coda notifiche/web push tramite il presidio automatico esistente;
- i bridge React di Agenda e Scadenziario riconoscono sia il vecchio `documento_fascicolo_lex` sia il nuovo `fascicolo_documenti_audit`.

Guardrail automatici eseguiti:

- `python -m pytest tests/test_pec_audit_pipeline.py::test_presidio_documentale_lex_recupera_udienza_termine_e_metadati_rag tests/test_pec_audit_pipeline.py::test_presidio_documentale_salta_fascicolo_gia_presidiato_e_processa_successivo -q` -> passato;
- `python -m pytest tests/test_scheduler.py::test_pec_audit_pipeline_job_restituisce_report_operativo tests/test_pec_auto_acquire.py::test_worker_pec_rispetta_budget_documentale_scheduler tests/test_pec_auto_acquire.py::test_notifica_scadenze_automatiche_agli_utenti_dello_studio tests/test_react_scadenziario_additions.py::test_react_scadenziario_bridge_non_sintetizza_presidio_documentale_lex_come_pec_generica -q` -> passato.

Stato verifica:

- test automatici mirati completati;
- prova reale locale completata dopo rebuild Docker di `app` e `scheduler-worker`: `/api/pronto` locale `ok=true`, container `iusentra-app` e `iusentra-scheduler` healthy;
- job reale `pec_audit_pipeline_workers` passato automaticamente alle `08:35` con `documenti Lex limit=10`, esito `0 job completati, 0 errori, documenti=39/2, notifiche=0/0`;
- DB audit locale aggiornato con eventi `pec.document_presidio.checked` e `scan_mode=incremental_new_or_changed_only`;
- prova visiva autenticata su `http://127.0.0.1:8080/scadenziario?vista=pec`: pagina `Scadenziario Legale` caricata, contatori visibili, nessuna nuova scadenza generata in locale per assenza di candidati operativi futuri nei documenti analizzati;
- prova reale server ancora da eseguire dopo deploy: non dichiarare chiuso il flusso finche' job vivo, fascicolo, agenda, scadenziario, notifiche e link remoto non sono stati verificati su `https://app.iusentra.it`.

## Presidio PEC incrementale e audit tenant-aware - 2026-07-03

Verifica produzione Hetzner: i due `pec_audit.sqlite` presenti sul server corrispondono a due tenant attivi e non sono duplicati da accorpare. La regola operativa resta un archivio audit PEC per tenant/studio, per preservare isolamento, fascicoli, allegati, audit e stati di lavorazione.

Correzione applicata:

- il presidio PEC resta incrementale: `pec_local_acquire_runs` conserva il cursore e `pec_local_acquire_items` marca i messaggi gia' letti/presidiati;
- i giri successivi non rileggono tutto l'archivio, ma partono dai nuovi arrivi e saltano gli elementi gia' presidiati;
- i lock temporanei del DB documentale Lex AI non falliscono l'intero job: vengono tracciati come documenti rinviati, non marcati come letti, e ripresi al ciclo successivo;
- il registro scheduler chiude la riga `running` con l'esito reale dello stesso avvio, cosi' il controllo operativo non mostra job appesi quando il worker ha realmente finito.

Test mirati:

- `test_presidio_documentale_lock_sqlite_rinvia_senza_marcare_letto`;
- `test_scheduler_registry_chiude_evento_scheduler_senza_running_residui`;
- test PEC incrementali su cursore e `skipped_presided`.

Aggiornamento 03/07/2026 10:04 (Europe/Rome):

- caso produzione `RG 1754/2026`: il documento di fissazione udienza conteneva udienza da remoto gia' passata e link Teams; il presidio ora registra comunque l'attivita' nel fascicolo con data, ora, fonte documento e `Link udienza audiovisiva`, senza creare una scadenza futura falsa in agenda/scadenziario;
- la stessa regola vale per tutti i fascicoli analoghi: udienza futura senza scadenza prefissata crea agenda/scadenziario/notifiche, udienza remota passata resta come attivita' documentale consultabile nel fascicolo;
- il job incrementale ordina prima i documenti probabilmente rilevanti (`udienza`, `fissazione`, `decreto`, `ordinanza`, `verbale`, `collegamento`, `audiovisivo`) per raggiungere rapidamente i casi operativi anche con lotto piccolo;
- gli errori non bloccanti di indicizzazione documentale, come file sopra limite Documenti AI o formato non supportato, vengono marcati in audit e non fanno fallire il worker PEC/documenti; i lock SQLite continuano invece a essere ritentati;
- la UI React del fascicolo conserva descrizioni attivita' piu' lunghe e rende cliccabili gli URL, con stile hover/focus, cosi' il link remoto resta leggibile nel dettaglio fascicolo.

Aggiornamento 03/07/2026 10:35 (Europe/Rome):

- il worker PEC/documenti mantiene il lotto piccolo per non appesantire il server, ma ordina prima i fascicoli senza scadenza futura visibile che contengono documenti con segnali `udienza`, `fissazione`, `decreto`, `ordinanza`, `verbale`, `rinvio`, `collegamento`, `audiovisivo`;
- i vecchi audit `pec.document_presidio.checked` senza campo `status`, con `candidates=0` e documento riconducibile a decreto/udienza, non bloccano piu' la nuova lettura: vengono rivalutati una volta e poi marcati con `status=checked`;
- guardrail aggiunti: priorita' tra fascicoli anche con lotto `limit=1` e ripresa di vecchio checked senza `status` sui decreti udienza.

Aggiornamento 03/07/2026 10:55 (Europe/Rome):

- durante il deploy su Hetzner il worker vivo ha intercettato riferimenti storici a documenti `.p7m` non piu' presenti nel path tenant-aware del fascicolo `0D4A4802`;
- questi riferimenti non devono essere scambiati per esito positivo, ma non devono nemmeno bloccare tutto il lotto PEC/documenti: il presidio ora li registra come `skipped_non_blocking` con motivo `file_documento_sorgente_non_trovato`;
- dopo la marcatura il giro successivo non rilegge gli stessi riferimenti rotti e puo' proseguire sui fascicoli successivi, incluso `RG 1754/2026` e gli altri fascicoli analoghi con decreti/ordinanze/verbali di udienza.

Aggiornamento 03/07/2026 11:10 (Europe/Rome):

- il ciclo automatico delle 11:05 ha dimostrato che, pur non fallendo piu', un fascicolo con molti documenti poteva ancora consumare il lotto e ritardare i fascicoli successivi;
- il worker ora applica anche `max_documents_per_fascicolo`: con il limite standard lavora solo una quota per fascicolo e poi passa agli altri, mantenendo prestazioni prevedibili senza lasciare indietro RG 1754/2026 e casi analoghi;
- guardrail aggiunto: `test_presidio_documentale_un_fascicolo_grande_non_monopolizza_il_lotto`.

Aggiornamento 03/07/2026 11:35 (Europe/Rome):

- la priorita' documentale non tratta piu' allo stesso modo un decreto generico e un decreto di fissazione udienza: segnali forti come `fissazione udienza`, link audiovisivi, Teams/Zoom/Meet/Webex, trattazione, 127-ter e note scritte passano prima dei soli `decreto`/`ordinanza`/`verbale`;
- i fascicoli gia' parzialmente presidiati vengono ruotati dietro ai fascicoli mai letti con segnali operativi, cosi' il worker vivo distribuisce il lotto sui casi analoghi e non resta agganciato sempre agli stessi archivi grandi;
- guardrail aggiunti: `test_presidio_documentale_fissazione_udienza_precede_decreto_generico` e `test_presidio_documentale_ruota_dopo_fascicolo_gia_toccato`.

Aggiornamento 03/07/2026 11:55 (Europe/Rome):

- il worker non ordina piu' solo per nome documento: quando `studio.db` contiene testo Lex gia' estratto, legge in sola lettura `fascicolo_documenti_ai` e `fascicolo_documenti_ai_testi` per promuovere i fascicoli con udienza da remoto e link reale Teams/Zoom/Meet/Webex;
- controllo server in sola lettura: `EFBE9117` (`RG 1754/2026`) ha testo AI con `DECRETO PER LO SVOLGIMENTO DI UDIENZA MEDIANTE COLLEGAMENTO DA REMOTO`, `N. R.G. 1754/2026`, data `20/05/2026 alle ore 10:00` e link `https://teams.microsoft.com/meet/38858779158973...`; la nuova priorita' lo classifica tra i fascicoli a priorita' massima non ancora letti;
- guardrail aggiunto: `test_presidio_documentale_testo_ai_con_link_remoto_precede_decreti_generici`.

Aggiornamento 03/07/2026 12:18 (Europe/Rome):

- prova server dopo deploy `2.253.156`: il worker vivo ha avviato automaticamente il run `12:05`, ha chiuso `ok=true`, `processed_jobs=6`, `ai_priority_fascicoli=84` per il tenant Montagnese e zero errori, ma `EFBE9117` risultava ancora marcato `checked` con `candidates=0`;
- causa corretta: il parser non riconosceva la formula reale `FISSA l'udienza in data 20/05/2026, alle ore 10:00` e il link Teams `meet?p=` spezzato a capo veniva troncato;
- hotfix `2.253.157`: aggiunti pattern `udienza in data`, ricomposizione link Teams `meet?p=` su riga successiva e `parser_version` nel ledger audit per rivalutare una volta i checked senza candidati creati prima del fix;
- hotfix `2.253.158`: il report operativo deduplica i candidati per documento/tipo/data quando Lex AI restituisce più record `ready` con lo stesso hash, così i controlli job non ripetono lo stesso evento pur mantenendo idempotente il salvataggio dell'attività;
- guardrail aggiunti: `test_extract_procedural_dates_reads_fissa_udienza_in_data_formula`, `test_remote_hearing_rebuilds_teams_meet_parameter_split_by_pdf_line_break`, `test_presidio_documentale_rilegge_checked_senza_candidati_con_parser_vecchio`, `test_presidio_documentale_non_duplica_report_con_record_ai_stesso_hash`.

## Catalogo documenti deposito Studio Telematico - 2026-07-03

Richiesta utente: nel flusso React `Prepara deposito` i documenti attesi e i documenti richiesti non devono restare uguali quando cambia il tipo deposito; servono anche `Deseleziona tutto` e stati hover/focus leggibili sul pulsante `Salva classificazione`.

Modifiche applicate:

- `pct/deposito_telematico_catalogo.py` non usa più una lista generica fissa `atto principale / procura / allegati`;
- i documenti attesi derivano dai flag importati dal catalogo Studio Telematico: `needProcura`, `needContributoUnificato`, `needNotaIscrizioneRuolo`, `VisualizzaAnagraficaProcedimento`, `VisualizzaGrigliaTerzi` e dai dati obbligatori `datiatto_required_data`;
- esempi presidiati: `Citazione` mostra atto, procura, contributo unificato, anagrafica procedimento, data citazione e valore causa; `Memoria 183` non mostra procura e contributo se Studio Telematico non li richiede; `Ricorso Cassazione` mostra nota iscrizione, provvedimento impugnato e prova notifica; UNEP resta nel flusso notifiche con relata, destinatari, spese e ricevute;
- `frontend/src/components/FascicoliPage.tsx` costruisce il pannello laterale `Documenti richiesti` dal tipo deposito selezionato, riusando gli slot reali della Regia quando esistono e marcando come requisiti di catalogo quelli derivati dalla matrice;
- i requisiti che sono dati del deposito, non file fisici, non mostrano il form `Collega` per evitare controlli apparenti;
- aggiunto il pulsante `Deseleziona tutto` accanto a `Invia tutto`;
- lo stile hover/focus di `Salva classificazione` resta blu con testo bianco e focus visibile.

Guardrail automatici eseguiti:

- `python -m pytest tests\test_deposito_telematico_catalogo.py tests\test_regia_ui_react.py -q --tb=short` -> passato;
- `python -m py_compile pct\deposito_telematico_catalogo.py` -> passato;
- `npm --prefix frontend run typecheck` -> passato;
- `npm --prefix frontend run build` -> passato.

Stato verifica:

- prova reale locale Docker eseguita il 03/07/2026 su `http://127.0.0.1:8080/fascicoli/DC5BF1DB/deposito/prepara#proposta-busta`, versione `2.253.161`, container `iusentra-app` healthy e `/api/pronto` `ok=true`;
- il browser integrato Codex non era disponibile (`agent.browsers.list() = []`), quindi la prova visiva è stata eseguita con Chrome locale via Playwright sulla stessa copia Docker reale `127.0.0.1:8080`;
- click reali eseguiti: `Deseleziona tutto` porta i documenti selezionati da `18` a `0`, `Invia tutto` porta la selezione a `20`, `Ripristina proposta` torna a `18`, `Salva classificazione` chiude con HTTP `200` e messaggio visibile `Classificazione deposito salvata: 18 documenti pronti per la busta.`;
- hover/focus di `Salva classificazione`: testo bianco, sfondo blu `rgb(37, 99, 235)`, bordo blu e focus ring visibile, senza bianco su fondo chiaro;
- cambio tipo deposito verificato in UI reale: `Atto di Citazione (in Appello)` mostra `8` documenti richiesti; `Memoria di Replica ex art. 183 cpc ultimo comma` mostra `4`; `Ricorso (Corte di Cassazione)` mostra `9` con `Nota iscrizione a ruolo`, `Provvedimento impugnato` e `Prova notifica`; `Richiesta di notifica di atto Civile (a debito)` UNEP mostra `6` con `Atto da notificare`, `Relata o richiesta`, `Destinatari`, `Contributo o anticipazione spese UNEP`, `Allegati`, `Ricevute`;
- screenshot fuori repository: `C:\Users\antmm\AppData\Local\Temp\iusentra-deposito-desktop-v6-top.png`, `C:\Users\antmm\AppData\Local\Temp\iusentra-deposito-desktop-v6-rail.png`, `C:\Users\antmm\AppData\Local\Temp\iusentra-deposito-desktop-v7-cassazione-rail-open.png`, `C:\Users\antmm\AppData\Local\Temp\iusentra-deposito-mobile-v6.png`, `C:\Users\antmm\AppData\Local\Temp\iusentra-deposito-tablet-v6.png`;
- responsive controllato su desktop `1365x820`, tablet `900x900` e mobile `390x844`: nessun overflow orizzontale rilevato.

## PEC Legal Event Understanding V2 - 2026-07-03

Richiesta utente: trasformare il presidio PEC in un motore professionale di comprensione dell'evento legale, collegato a fascicoli, Agenda, Scadenziario, notifiche, web push, Lex AI e DB vettoriale, senza risposte automatiche o termini conclusivi non verificati.

Modifiche applicate:

- aggiunto `pct/pec_legal_event_understanding.py` come motore V2 deterministico-first;
- aggiunto ruleset `pct/data/legal_pec_rules_v2026_07.json`;
- aggiunta specifica operativa `docs/specs/PEC_LEGAL_EVENT_UNDERSTANDING_V2.md`, da rileggere dopo compattazione per lavori PEC/Lex/udienze/scadenze;
- il worker `validate` della pipeline PEC materializza il presidio in `pec_legal_events`, `pec_legal_deadlines`, `pec_legal_hearings` e `pec_legal_payments`;
- le migrazioni SQLite e PostgreSQL sono state aggiornate in parità;
- Lex riceve memoria strutturata con fatti, fonti hashate e limiti di inferenza, non solo testo libero;
- le udienze da remoto/miste senza link diventano priorità `P0`;
- i link Teams vengono estratti anche da HTML `href`, testo e allegati OCR;
- la comunicazione di deposito sentenza non genera termine breve automatico ex art. 325 c.p.c.;
- spese, distrazione, antistatario, contributo unificato, esborsi e gratuito patrocinio vengono distinti nel payload pagamenti;
- penale, PAT, PTT e SIGIT restano fail-closed se non esiste ruleset dedicato.

Guardrail automatici eseguiti:

- `python -m pytest tests/test_pec_legal_event_understanding.py -q`;
- `python -m pytest tests/test_pec_hearing_understanding.py tests/test_pec_legal_workflow.py tests/test_pec_legal_deadline_cablaggio.py -q`;
- `python -m pytest tests/test_pec_audit_pipeline.py -k "pec_pipeline_ingests_synthetic_dataset_with_audit_grade_storage or pec_audit_header_summaries_support_lightweight_mode or lex_operational_tools_expose_pec_audit_control_context" -q`;
- `python -m pytest tests/test_pec_auto_acquire.py::test_worker_pec_rispetta_budget_documentale_scheduler tests/test_scheduler.py::test_pec_audit_pipeline_job_restituisce_report_operativo -q`;
- `python -m pytest tests/test_utf8_integrity.py -q`;
- controllo schema SQLite in memoria sulle nuove quattro tabelle.

Stato verifica:

- prova reale locale Docker eseguita su `127.0.0.1:8080`, versione `2.253.159`: `/api/pronto` `ok=true`, container `iusentra-app` e `iusentra-scheduler` healthy;
- worker reale nel container eseguito sul tenant `studio-montagnese`: `processed=0`, `failed=0`, nessun job PEC pendente, presidio documentale concluso senza errori;
- campione runtime isolato nel container: PEC con `RG 1754/2026`, udienza Teams, data `20/05/2026`, ora `10:00`, art. 127-bis; worker `parse/classify/ocr/signcheck/validate/link` completato con `processed=6`, `failed=0`, link Teams verificato, priorità `P1`, nessun falso errore PCT per placeholder `deposito_da_ricondurre`;
- prova server da eseguire dopo deploy: non dichiarare chiuso il presidio finché Hetzner non risulta sullo stesso commit, healthy e con worker verificato.

## Confronto notifiche legali Studio Telematico / IUSENTRA - 2026-07-03

Richiesta utente: confrontare il comportamento delle notifiche legali osservato nel decompilato Studio Telematico con IUSENTRA, campo per campo, senza backup e senza portare nella UI riferimenti tecnici o riferimenti a Studio Telematico.

Documento di confronto:

- `artifacts/react-migration/studio-telematico-notifiche-legali-confronto-2026-07-03.md`.

Sintesi operativa:

- Studio Telematico collega atto, relata, ricevuta di accettazione e ricevuta di consegna tramite destinatario, codice fiscale, PEC, pubblico elenco e identificativo notifica;
- IUSENTRA aveva già un modello più strutturato con `notification_cases`, `notification_recipients`, `notification_receipts`, `notification_evidence_links`, `notification_proof_bundles` e riferimenti deposito;
- gap corretto: la prova deposito ora non accetta ricevute non collegate a codice fiscale/partita IVA, PEC e pubblico elenco del destinatario;
- gap corretto: gli alias letterali del decompilato per pubblici elenchi vengono normalizzati nel dominio IUSENTRA;
- gap corretto: il guard PostgreSQL della matrice probatoria è stato riallineato al presidio SQLite sugli stati prova notifica;
- gap corretto: le aree UNEP e non PEC/raccomandata sono state portate nello stesso pannello React notifiche come flussi separati, con API e tabelle dedicate;
- UI corretta: il pannello visibile non mostra riferimenti a Studio Telematico, alias tecnici o testo tecnico del confronto; mostra solo dati operativi leggibili per l'avvocato.

Controllo esteso del perimetro:

- controllati anche `FormTipoNotificaUNEP.cs`, `FormDepositaConSoftwareEsterno.cs`, `NotificaEsito.cs` e i campi `TAVOLA` collegati a data/tipo notifica, ricevuta raccomandata e identificativo notifica;
- UNEP usa un canale proprio con tipo notifica, eventuale data notifica precetto, spese e ricevute: in IUSENTRA è ora disponibile nel tab `UNEP` di `/notifiche-legali` e resta separato dalla prova PEC L. 53;
- il tracciamento raccomandata/non PEC in `TAVOLA` è ora coperto dal tab `Non PEC` con campi `DataNotifica`, `TipoNotifica`, `DataRicevutaRaccomandata`, `NotificaID` e prova documentale;
- `NotificaEsito` riguarda esiti SdI/fatturazione elettronica e non è pertinente al pannello notifiche legali PEC.

Guardrail automatici eseguiti:

- `python -m pytest tests\test_notifiche_legali.py tests\test_procedure_lifecycle_repository.py -q` -> passato;
- `npm --prefix frontend run typecheck` -> passato;
- `npm --prefix frontend run test:app-v2` -> passato;
- `python -m pytest tests\test_utf8_integrity.py -q` -> passato;
- `git diff --check` -> passato.

Stato verifica:

- non verificato su macchina reale autenticata;
- copia Docker reale ricostruita senza cache e avviata su `127.0.0.1:8080`, container `iusentra-app` healthy, `/api/pronto` `ok=true`, versione `2.253.162`, fuso `Europe/Rome`;
- il browser integrato Codex ha esposto il backend `Codex In-app Browser`, ma non si è agganciato alla webview durante l'apertura di `/notifiche-legali`; l'accesso diretto senza sessione ha restituito redirect a login, quindi non è stata eseguita la prova materiale dei pulsanti;
- prima di dichiarare concluso il lavoro va provato materialmente `/notifiche-legali` in sessione autenticata, in particolare i tab `Notifica PEC`, `Deposito prova`, `UNEP`, `Non PEC`, `Cliente`, tutti i pulsanti di controllo, i testi visibili, hover/focus e responsive desktop/tablet/mobile.

## Notifiche legali React - correzione payload UI 2026-07-03

Durante la prova su produzione autenticata è stato trovato un problema non visibile nella schermata ma presente nel JSON dell'API: alcune diciture tecniche storiche potevano arrivare al frontend. La versione `2.253.163` aggiunge una sanitizzazione ricorsiva lato backend per il payload del pannello notifiche, il payload documenti pratica e le risposte dei controlli operativi; il formatter React dei blocker/warning applica la stessa sostituzione prima di mostrare il testo all'avvocato.

Guardrail eseguiti:

- `python -m pytest tests\test_notifiche_legali.py -q`;
- `npm --prefix frontend run typecheck`;
- `python -m pytest tests\test_regia_ui_react.py::test_ui_notifiche_relata_firma_solo_con_prova_tecnica -q`;
- `python -m pytest tests\test_react_shell.py::test_react_comunicazioni_email_messaggi_collegate_nav_e_shell -q`;
- `python -m pytest tests\test_react_shell.py::test_import_studio_telematico_react_pubblica_exe_e_barra_avanzamento -q`;
- `python -m pytest tests\test_react_shell.py::test_react_telematico_bridge_payload_minimo -q`;
- `python -m pytest tests\test_utf8_integrity.py -q`;
- `npm --prefix frontend run build`;
- `git diff --check`.

Stato: ridistribuito su Hetzner e verificato in produzione con browser reale autenticato su `https://app.iusentra.it/notifiche-legali` prima della correzione UX `2.253.164`.

## Notifiche legali React - verifica produzione e feedback controlli 2026-07-03

Prova produzione autenticata eseguita su `https://app.iusentra.it/notifiche-legali`, utente amministratore, senza riportare credenziali nei log o nella documentazione.

Verifica server:

- commit produzione verificato su Hetzner prima della correzione UX: `d5a71e8e395a2f1c04cea949a5fd007ea5a7169d`;
- `/api/pronto` produzione: `ok=true`, versione `2.253.163`, fuso `Europe/Rome`;
- container applicativo unico: `iusentra-app`, stato `healthy`;
- API pannello e validazioni controllate senza stringhe tecniche vietate nel payload utente.

Verifica browser reale eseguita:

- `Notifica ex L. 53/1994`: campi pratica, destinatari, documenti, modello relata, bozza relata, firma relata, approvazione finale; `Controlla relata` produce esito e blocchi specifici; `Invia PEC` resta bloccato con motivi puntuali finché mancano requisiti obbligatori;
- `Deposito prova notifica`: atto notificato, relata firmata, messaggio PEC, ricevute, destinatario, pubblico elenco e ricevuta completa; `Controlla prova deposito` produce elenco bloccante dei documenti/ricevute mancanti;
- `UNEP`: tipo notifica, ufficio NEP, destinatario, recapito, precetto, spese, atto, richiesta/relata e ricevuta pagamento; `Controlla richiesta UNEP` produce verifiche normative con stati bloccanti/superati;
- `Non PEC`: data, identificativo, raccomandata, spedizione, ricezione/giacenza, prova documentale e note; `Controlla notifica non PEC` conserva il canale separato da PEC L. 53;
- `Comunica al cliente`: modelli, oggetto e corpo ordinari separati dalla relata; il controllo ha evidenziato un difetto UX perché l'esito non veniva portato automaticamente in vista dopo il click.

Correzione applicata dopo la prova:

- versione `2.253.164`;
- `frontend/src/components/NotificheLegaliPage.tsx` ora porta sempre in vista il pannello esito dopo ogni controllo, compreso `Prepara comunicazione`;
- `tests/test_notifiche_legali.py` contiene il guardrail `test_ui_notifiche_legali_ogni_controllo_porta_esito_in_vista`;
- bundle React rigenerato con asset `NotificheLegaliPage-bdr8lesz.js`.

Guardrail eseguiti:

- `python -m pytest tests\test_notifiche_legali.py -q` -> passato;
- `npm --prefix frontend run typecheck` -> passato;
- `npm --prefix frontend run build` -> passato;
- `python scripts\react-migration\generate_api_contracts.py --check` -> passato;
- `python scripts\validate_openapi.py docs\openapi.yaml` -> passato;
- `python -m pytest tests\test_utf8_integrity.py -q` -> passato.

Stato operativo: prima di confermare la chiusura della versione `2.253.164` resta obbligatorio commit/push branch gemelli, deploy Hetzner, verifica `/api/pronto`, container unico healthy e nuova prova produzione del pulsante `Prepara comunicazione` con esito portato in vista.

## Fascicoli - lettore documenti mobile ed evidenze economiche automatiche 2026-07-05

Ambito: fascicoli, documenti, controllo economico sentenze, contributo unificato, prossima scadenza e visualizzazione documenti su mobile.

Modifiche applicate:

- la route autenticata `/fascicoli/<id_fasc>/documenti/<id_doc>/visualizza` supporta `?viewer=mobile`: per i PDF genera una pagina HTML interna con immagini PNG delle pagine, senza inviare documenti a servizi esterni e senza dipendere dal viewer PDF nativo del telefono;
- il componente React `PdfPreviewModal` usa il viewer mobile solo sotto i 900px e solo per documenti del fascicolo, lasciando invariata l'anteprima PDF nativa desktop;
- il controllo economico del fascicolo usa i testi Document AI/OCR già presenti nel fascicolo per compilare automaticamente contributo unificato, spese/esborsi, liquidazione e parcella quando il contesto RG/parti è compatibile;
- `Prossima scad.` viene proposta automaticamente dai documenti del fascicolo quando non è già presente una scadenza governata da Agenda/Scadenziario;
- le liste Clienti, Soggetti e Fascicoli sono state rese più leggibili nei viewport intermedi spostando le azioni nella cella principale della riga.

Fonti dati e vincoli:

- fonte operativa: SQLite/PostgreSQL del tenant e tabelle/indici Document AI già governati;
- JSON solo mirror/cache, non fonte decisionale;
- nessuna modifica al canale PEC reale e nessun invio server-side;
- gli importi visibili restano in formato italiano, per esempio `€ 21,50`;
- le date visibili restano in formato italiano, per esempio `13/01/2027`.

Guardrail automatici eseguiti:

- `python -m py_compile web/bootstrap/fascicoli_document_helpers.py web/bootstrap/fascicoli_document_routes.py web/services/react_fascicoli_bridge.py web/services/sentenza_economic_runtime.py`;
- `python -m pytest -q tests/test_polisweb.py::test_visualizza_documento_pdf_mobile_renderizza_pagine_png`;
- `python -m pytest -q tests/test_react_shell.py::test_react_fascicoli_lista_popola_economia_e_scadenza_da_documenti tests/test_react_shell.py::test_react_fascicoli_suite_completa_route_componenti_e_lex tests/test_react_shell.py::test_post_modifica_cliente_json_normalizza_comune_e_persiste`;
- `python -m pytest -q tests/test_react_fascicoli_sentenze_economiche.py tests/test_sentenza_economic_runtime.py`;
- `npm --prefix frontend run typecheck`.

Stato:

- test automatici mirati passati;
- prove visive reali produzione e locale ancora da completare sulla versione deployata e sulla copia Docker `127.0.0.1:8080` prima di dichiarare chiuso il lavoro.

## Fascicoli - presidio decreti udienza, doppioni e cosa fare oggi 2026-07-06

Ambito: fascicoli React, documenti indicizzati, decreti di fissazione udienza, termini per note scritte, controllo economico, topbar `Oggi` e panoramica operativa.

Fonti ufficiali considerate:

- art. 127-ter c.p.c. da Gazzetta Ufficiale: termine per note scritte in sostituzione dell'udienza, non inferiore a 15 giorni, con giorno di scadenza trattato come data di udienza;
- art. 127-bis c.p.c. da Gazzetta Ufficiale: udienza audiovisiva e richiesta di presenza entro 5 giorni dalla comunicazione;
- Cassazione, Sezioni Unite, sentenza n. 17603/2025: cautela sul termine indicato con orario, da presidiare come termine perentorio del giorno indicato;
- artt. 91 e 93 c.p.c. e DPR 115/2002 per il raccordo tra liquidazioni, spese, contributo unificato e controllo economico.

Modifiche applicate:

- nuovo presidio `pct/fascicolo_document_presidio.py`: interpreta testi già indicizzati dei documenti fascicolo senza salvare nuovo audio/file e senza introdurre nuove tabelle;
- riconoscimento dei decreti ex art. 127-ter c.p.c. con termine deposito note, onere notifica 30 giorni prima e verifica costituzione 10 giorni prima;
- riconoscimento dei decreti ex art. 127-bis c.p.c. con udienza audiovisiva, ora dell'udienza, costituzione 10 giorni prima e alert quando il termine di 5 giorni dipende dalla data di comunicazione non presente nel documento;
- il payload React dettaglio fascicolo espone `documentPresidio` e la sezione `Udienze e scadenze` mostra il pannello `Presidio documenti fascicolo` con data, fonte documento, perentorietà e avvisi;
- la lista Fascicoli rileva pratiche potenzialmente doppie tramite cliente normalizzato e RG, anche quando il nominativo arriva invertito da fonti diverse, senza avviare Document AI nella vista operativa;
- la vista economica mostra fonti documentali dei valori automatici già proposti da Document AI, così contributo, spese, liquidazione e parcella non appaiono come importi privi di origine;
- topbar `Oggi` e `WorkspaceIntelligente` aggiungono l'attività professionale `Verificare pratiche doppie per cliente e RG` quando il dato richiede controllo prima di usare scadenze, documenti o importi.

Fonti dati e vincoli:

- fonte operativa: repository fascicoli, Agenda, Scadenziario e testi Document AI già tenant-aware;
- SQL/SQLite/PostgreSQL restano fonte di verità dei dati strutturati; il nuovo presidio è derivato e non sostituisce scadenze o appuntamenti persistenti;
- la vista operativa `/fascicoli` non avvia Document AI automatico, preservando il caricamento rapido della lista;
- nessun invio PEC server-side e nessuna modifica al canale Local Signer/PEC locale.

Guardrail automatici eseguiti:

- `python -m py_compile pct\fascicolo_document_presidio.py web\services\react_fascicoli_bridge.py web\services\topbar_operational.py pct\workspace_intelligente.py`;
- `python -m pytest tests\test_fascicolo_document_presidio.py tests\test_topbar_operational_api.py tests\test_react_shell.py::test_react_fascicoli_lista_popola_economia_e_scadenza_da_documenti tests\test_react_shell.py::test_react_fascicoli_lista_operativa_non_avvia_document_ai_automatico tests\test_react_shell.py::test_react_fascicoli_lista_operativa_segnala_doppioni_senza_document_ai tests\test_react_shell.py::test_react_fascicolo_dettaglio_espone_presidio_documenti_udienza tests\test_react_shell.py::test_react_fascicolo_lazy_scadenze_unisce_presidio_documenti tests\test_react_shell.py::test_react_fascicoli_fonti_documentali_visibili_senza_id_tecnici -q`;
- `python -m pytest tests\test_utf8_integrity.py -q`;
- `pnpm --filter @iusentra/studio typecheck`;
- `pnpm --filter @iusentra/studio build`;
- `docker compose build --no-cache`;
- `docker compose up -d`;
- `docker compose ps`;
- `http://127.0.0.1:8080/api/pronto` -> `ok=true`, `timezone=Europe/Rome`, `versione=2.253.182`;
- `docker exec iusentra-app python -c "import pct; print(pct.__version__)"` -> `2.253.182`.

Prova reale locale su `127.0.0.1:8080`:

- browser integrato Codex visibile, copia Docker reale `iusentra-app` healthy su porta `8080`;
- vista `/fascicoli?vista=economica`: caricamento concluso con `Dati aggiornati`, importi in formato italiano, pannello `Lettura documenti` con fonte leggibile `Documento indicizzato del fascicolo`, nessun identificativo tecnico `document_id`, `docai` o `pst:JPW` visibile, nessun timestamp ISO, nessun overflow orizzontale, console senza errori;
- click materiale su `Modifica controllo economico`: il pulsante passa a `Chiudi modifica`, la tabella resta stabile, niente ID tecnici o date ISO visibili;
- dettaglio reale `/fascicoli/DC5BF1DB#udienze`, fascicolo `RG 466/2023`, cliente `Alessi Robertino`: click su `Udienze / scadenze`, pannello `Presidio documenti fascicolo` caricato con `8 controlli`, date italiane, fonte `Documento indicizzato del fascicolo`, avvisi comprensibili e accenti corretti (`modalità di trattazione`);
- responsive verificato su desktop `1280x720`, tablet `900x900` e mobile `390x844` con scroll fino al fondo: nessun overflow orizzontale, nessun ID tecnico visibile, nessuna data ISO, console senza errori;
- nel tenant locale reale il riepilogo `Doppioni` mostra `0 / nessun gruppo rilevato`; il percorso positivo con due fascicoli stesso cliente/RG è coperto da test mirato senza avviare Document AI nella vista operativa.

Stato:

- codice e prova locale reale completati sulla copia Docker `127.0.0.1:8080`;
- il gate di rilascio resta legato allo SHA finale: commit, push branch gemelli, controlli GitHub/CodeQL, deploy Hetzner, container unico `iusentra-app`, `/api/pronto` produzione e pulizia Docker devono risultare dal report operativo dello stesso commit.

## Fascicoli - logica economica documentale e anti-doppioni 2026-07-06

Ambito: lista Fascicoli economica, documenti indicizzati del fascicolo, contributo unificato, autocertificazioni/esenzioni, sentenze, liquidazioni, parcelle e duplicazioni cliente/RG.

Regola professionale introdotta:

- `€ 0,00` non è un dato economico utilizzabile se lo stato è ancora `Da registrare`, `Da emettere` o `Parziale`: è un placeholder storico e il motore deve provare a sostituirlo con evidenze documentali;
- se il fascicolo contiene ricevuta PagoPA/CU, la voce `Contributo unificato` viene proposta come pagata con importo, data e documento fonte;
- se il fascicolo contiene richiesta di versamento CU, la voce resta `Da registrare` ma con importo dovuto e fonte documento;
- se il fascicolo contiene autocertificazione reddituale, esenzione dal contributo, art. 9 comma 1-bis DPR 115/2002, ammissione al patrocinio a spese dello Stato o prenotazione a debito, la voce viene proposta come `Non previsto`/esente, senza importo fittizio e con fonte documento;
- se il PDF non è ancora OCRizzato o indicizzato, il nome/metadato del documento resta un'evidenza valida quando è specifico, ad esempio `Autocertificazione esenzione cu diritto lavoro.PDF`: in quel caso il motore deve proporre `Contributo unificato` come `Non previsto`, con fonte documento, senza attendere una lettura testuale;
- se il fascicolo contiene una sentenza compatibile per RG/parti, liquidazione, spese/esborsi e parcella proposta vengono popolati anche quando i campi storici erano a zero;
- il controllo economico non deve confondere importi Carta docente, soglie reddituali o valore della causa con contributo unificato pagato;
- una pratica con stesso cliente normalizzato e stesso RG non deve nascere: la creazione blocca il doppione e la riconciliazione storica accorpa documenti e pagamenti preservando le registrazioni manuali.

Quando rianalizzare:

- ogni aggiunta, sostituzione o rimozione documento marca il fascicolo come `Da rianalizzare`;
- la vista operativa non avvia lettura documentale pesante, per mantenere rapido il caricamento;
- la vista economica e il dettaglio, dove il dato è necessario all'avvocato, leggono i testi Document AI/OCR già presenti e mostrano stato, importo se dovuto, fonte e ragione;
- l'impronta dei documenti del fascicolo e delle pratiche riconciliate impedisce di trattare come aggiornato un controllo economico riferito a documenti cambiati.

Fonti normative e operative considerate:

- art. 9 comma 1-bis DPR 115/2002 per le esenzioni del contributo unificato nei casi previsti;
- DPR 115/2002 e PagoPA/PST per contributo unificato, versamenti e ricevute;
- artt. 91 e 93 c.p.c. per spese liquidate, distrazione e credito dell'avvocato antistatario;
- artt. 127-bis, 127-ter e 171-ter c.p.c. per raccordare udienze, termini e scadenze documentali con la regia operativa del fascicolo.

Guardrail automatici eseguiti in questa tranche:

- `python -m py_compile pct/fascicolo_sentenza_economica.py web/services/react_fascicoli_bridge.py`;
- `python -m pytest tests/test_react_shell.py::test_react_fascicoli_lista_popola_economia_e_scadenza_da_documenti tests/test_react_shell.py::test_react_fascicoli_economia_riconosce_cu_esente_da_autocertificazione_generica tests/test_react_shell.py::test_react_fascicoli_economia_sostituisce_zero_storico_con_pagopa_generico tests/test_react_shell.py::test_react_fascicoli_economia_sostituisce_zero_storico_con_sentenza -q`.
- `python -m pytest tests/test_react_shell.py::test_react_fascicoli_economia_usa_nome_documento_per_cu_esente_senza_ocr tests/test_react_shell.py::test_react_fascicoli_economia_riconosce_cu_esente_da_autocertificazione_generica tests/test_react_shell.py::test_react_fascicoli_economia_sostituisce_zero_storico_con_pagopa_generico tests/test_react_shell.py::test_react_fascicoli_economia_sostituisce_zero_storico_con_sentenza -q`.

Stato:

- codice locale aggiornato a `2.253.184`;
- prova server reale, riconciliazione dati produzione, prova visiva su `https://app.iusentra.it/fascicoli?vista=economica`, rebuild locale `127.0.0.1:8080`, commit, push branch gemelli, check GitHub/CodeQL e deploy Hetzner finale restano parte obbligatoria del rilascio prima della chiusura.

## Fascicoli - microcopy e autocertificazione CU importata 2026-07-06

Aggiornamento operativo `2.253.185`/`2.253.186`/`2.253.187`.

Problema reale visto su produzione: la vista economica mostrava chiavi tecniche come `sentenza_key:...` e, su alcuni fascicoli Montagnese, mostrava `Autocertificazione esenzione contributo unificato` senza trasformare il contributo in `Non previsto`. Per l'avvocato questo non è supporto: il sistema deve tradurre fonte, importo e stato in una decisione comprensibile.

Regola aggiunta:

- la fascia `Controllo documenti` non espone più chiavi interne, identificativi Document AI o motivazioni tecniche grezze;
- sentenze, autocertificazioni, ricevute pagoPA e documenti importati vengono mostrati con fonte leggibile;
- se un campo economico placeholder contiene nei propri metadati una fonte come `Autocertificazione esenzione cu diritto lavoro.PDF`, l'evidenza viene usata anche senza OCR;
- i nomi file importati con separatori tecnici, per esempio `AUTOCERTIFICAZIONE_DELLA_SITUAZIONE_REDDITUALE_-_ESENZIONE_CONTRIBUTO_UNIFICATO_2025.PDF`, vengono normalizzati prima della lettura logica;
- se l'autocertificazione CU è stata importata per errore sotto `spese/esborsi`, il presidio la sposta logicamente sul contributo unificato e non la tratta come spesa da registrare;
- un valore storico `€ 0,00` resta placeholder quando lo stato è `Da registrare` o `Da emettere`: non deve impedire alla lettura documentale di proporre lo stato corretto.

Guardrail eseguiti:

- `pnpm --filter @iusentra/studio typecheck`;
- `python -m py_compile web/services/react_fascicoli_bridge.py pct/fascicolo_sentenza_economica.py`;
- `python -m pytest tests/test_react_shell.py::test_react_fascicoli_economia_usa_nome_documento_per_cu_esente_senza_ocr tests/test_react_shell.py::test_react_fascicoli_economia_sposta_autocertificazione_importata_sul_cu tests/test_react_shell.py::test_react_fascicoli_economia_riconosce_cu_esente_da_autocertificazione_generica tests/test_react_shell.py::test_react_fascicoli_economia_sostituisce_zero_storico_con_pagopa_generico tests/test_react_shell.py::test_react_fascicoli_economia_sostituisce_zero_storico_con_sentenza -q`.

## Fascicoli importati senza RG - presidio deposito/notifiche 2026-07-06

Verifica sul database originale `E:\QuickOrganizer\QuickOrganizer.mdb`: per i `56` fascicoli senza RG in produzione, `PRATICHE.RUOLO_GEN` è vuoto in tutti i casi e `AGENDA` non contiene righe utili per recuperare `Ruolo`/`Anno_Ruolo_Gen`; `23` risultano già archiviati da `ARCHIVIO` o `DATA_ARC`, `33` restano non archiviati nel sorgente.

Regola per deposito, notifiche e scadenze: il numero interno pratica (`NUMEROPRATICA` o `2026/337`) non è RG e non abilita ricerche, depositi o notifiche come se fosse numero di ruolo. La UI deve mostrare `RG da acquisire`, mantenere il numero interno come riferimento secondario e chiedere acquisizione del numero di ruolo dal portale o da provvedimento prima di usare il fascicolo per adempimenti processuali.

Prova server reale eseguita su `https://app.iusentra.it/fascicoli?vista=economica`: dopo il primo rebuild `2.253.185` la UI non esponeva più `sentenza_key`, `Aggiornato in lettura` o `Lettura documenti`; la stessa prova ha fatto emergere il caso `Merdini Manjola - RG 2848/2026`, corretto con le regole `2.253.186` e `2.253.187` prima della chiusura.

## PEC - lettura messaggio completo senza duplicati 2026-07-06

La pagina React `/email/` deve mostrare il messaggio completo della PEC in modo forense ma leggibile: una sola busta PEC esterna, una sola sezione per il messaggio allegato `postacert.eml` e allegati testuali separati. Quando il MIME originale contiene sia `text/plain` sia `text/html` con contenuto equivalente, il bridge backend deduplica l'alternativa HTML; quando incontra un allegato `message/rfc822`, lo formatta come messaggio allegato senza attraversarne il corpo una seconda volta come parte autonoma della busta esterna.

Guardrail locale aggiunto: `tests/test_email_client.py::test_email_dettaglio_pec_non_duplica_busta_e_postacert`. La prova reale su `127.0.0.1:8080/email/` deve confermare che `Messaggio completo` non ripete `MESSAGGIO DI POSTA CERTIFICATA` e `CERTIFIED EMAIL MESSAGE`.

## Fascicoli - contributo unificato da RT XML e autocertificazioni generiche 2026-07-06

Aggiornamento operativo `2.253.193`.

Problema reale segnalato nella vista economica: diversi fascicoli mostravano `Contributo` come `Pagato` da `Ricevuta pagoPA`, ma senza importo (`Da verificare`), oppure non consideravano l'autocertificazione reddituale presente nel fascicolo. La causa tecnica era doppia: il presidio economico usava il documento classificato, ma se Document AI non aveva ancora testo non apriva sempre il file fisico PDF/XML; inoltre le RT XML PagoPA del PST espongono importo e causale in tag strutturati (`importoTotalePagato`, `singoloImportoPagato`, `causaleVersamento`) senza la dicitura testuale `Tipo pagamento: Contributo unificato`.

Regola professionale corretta:

- prima di concludere `Pagato senza importo`, il presidio apre il documento fisico del fascicolo se il testo Document AI/OCR non è disponibile;
- le ricevute telematiche XML PagoPA vengono lette dai tag ministeriali e dalla causale `/RFB/...//importo/TXT/...`, quindi casi come Alfano Giuseppe estraggono `€ 49,00` dalla RT XML reale;
- la data di pagamento viene letta anche dai tag XML con prefisso namespace, per esempio `<pay_j:dataEsitoSingoloPagamento>2026-05-12</...>`;
- `Autocertificazione`, `dichiarazione sostitutiva`, `reddito`, `reddituale`, `ISEE`, `art. 76`, `D.P.R. 115/2002` e `art. 9 comma 1-bis` fanno partire la lettura mirata anche quando il nome file non contiene `CU`;
- se l'autocertificazione contiene la soglia reddituale/esenzione CU, il contributo viene proposto come `Non previsto`, senza importo fittizio;
- se esiste una ricevuta con importo certo, il sistema registra l'importo; se esiste solo la classificazione del pagamento senza importo, resta un dato da leggere, non una prova economica completa.

Fonti ufficiali considerate:

- Ministero della Giustizia, circolare 11 maggio 2012 su art. 9 comma 1-bis D.P.R. 115/2002: per lavoro, previdenza, assistenza obbligatoria e pubblico impiego l'esenzione soggettiva è collegata alla soglia reddituale pari a tre volte l'importo dell'art. 76 D.P.R. 115/2002;
- Ministero della Giustizia, provvedimento 27 luglio 2024: la debenza del contributo unificato, anche ai fini dell'eventuale raddoppio, va verificata con riferimento al momento dell'iscrizione a ruolo.

Guardrail automatici eseguiti:

- `python -m py_compile pct/fascicolo_sentenza_economica.py web/services/react_fascicoli_bridge.py`;
- `python -m pytest tests/test_react_shell.py::test_react_fascicoli_economia_legge_rt_xml_pagopa_fisico_senza_document_ai tests/test_react_shell.py::test_react_fascicoli_economia_autocertificazione_generica_avvia_lettura_mirata tests/test_react_shell.py::test_react_fascicoli_economia_cu_classificato_avvia_ocr_mirato_e_popola_importo tests/test_react_shell.py::test_react_fascicoli_economia_riconosce_cu_esente_da_autocertificazione_generica -q`;
- `python -m pytest tests/test_react_shell.py::test_react_fascicoli_lista_popola_economia_e_scadenza_da_documenti tests/test_react_shell.py::test_react_fascicoli_economia_sostituisce_zero_storico_con_pagopa_generico tests/test_react_shell.py::test_react_fascicoli_economia_pagamento_cu_classificato_resta_da_registrare_senza_importo tests/test_react_shell.py::test_react_fascicoli_economia_usa_nome_documento_per_cu_esente_senza_ocr tests/test_react_shell.py::test_react_fascicoli_economia_sposta_autocertificazione_importata_sul_cu tests/test_react_shell.py::test_react_fascicoli_economia_sostituisce_zero_storico_con_sentenza tests/test_react_shell.py::test_react_fascicoli_economia_usa_candidati_documentali_senza_fallback_totale -q`;
- `python -m pytest tests/test_react_fascicoli_sentenze_economiche.py tests/test_backfill_sentenza_lex_economics.py::test_backfill_contributo_evidence_rifiuta_carta_docente_e_soglia_reddito tests/test_backfill_sentenza_lex_economics.py::test_backfill_contributo_evidence_non_scambia_iniziali_cu_per_pagamento -q`.

Prova reale obbligatoria prima della chiusura:

- rebuild Docker locale `127.0.0.1:8080` sul commit finale `2.253.194`;
- vista `/fascicoli?vista=economica`: verificare che i fascicoli con RT XML PagoPA mostrino importo italiano, stato `Pagato`, data italiana e fonte documento; verificare che le autocertificazioni reddituali pertinenti mostrino `Non previsto`;
- controllare almeno il caso `Alfano Giuseppe c. MIM / RG 1100/2026` e un caso con autocertificazione CU, poi ripetere su produzione Hetzner prima del report finale.

## Fascicoli - contributo unificato non pagato senza importo 2026-07-06

Aggiornamento operativo `2.253.195`.

Problema reale verificato sui dati dello studio Montagnese: alcuni fascicoli, tra cui `Alfano Giuseppe c. MIM / RG 1100/2026`, ricevevano lo stato `Pagato` solo perché il documento o il presidio storico erano classificati come `Contributo unificato / pagamento`, ma senza importo letto e senza prova completa. Per l'avvocato questo è fuorviante: una classificazione documentale indica dove leggere, non certifica da sola il pagamento.

Regola corretta:

- un documento classificato come pagamento CU resta candidato prioritario per lettura, OCR e controllo fisico;
- lo stato `Pagato` viene prodotto solo quando il motore legge un importo certo da ricevuta PagoPA, RT XML, testo OCR o altra evidenza economica completa;
- l'autocertificazione reddituale o l'esenzione CU possono portare a `Non previsto`, ma devono emergere da testo, nome documento o metadati coerenti;
- se esiste solo il marker `Import pratiche`, `Ricevuta pagoPA` o `Contributo unificato / pagamento` senza importo, il presidio economico resta `Da registrare` o `Da verificare` e non inventa un pagamento.

Guardrail aggiunti:

- `tests/test_fascicolo_sentenza_economica.py::test_pdf_contributo_classificato_senza_importo_non_diventa_pagato`;
- `tests/test_react_shell.py::test_react_fascicoli_economia_pagamento_cu_classificato_resta_da_registrare_senza_importo`.

Prove obbligatorie prima della chiusura del rilascio:

- rebuild Docker locale reale su `127.0.0.1:8080` con versione `2.253.195`;
- verifica API/UI locale React della vista economica;
- verifica server Hetzner su `https://app.iusentra.it/api/pronto`;
- verifica dati reali produzione: `Betti C. MIM / RG 3685/2026` deve conservare `Pagato € 49,00`, un fascicolo con autocertificazione deve conservare `Non previsto`, mentre `Alfano Giuseppe c. MIM / RG 1100/2026` non deve più risultare `Pagato` senza importo.

## Fascicoli - cache automatica presidio economico documentale 2026-07-06

Aggiornamento operativo `2.253.196`.

Problema emerso dopo la verifica server del rilascio `2.253.195`: la vista economica sui fascicoli dello studio Montagnese produceva dati corretti, ma poteva impiegare troppo tempo perché rileggeva PDF/XML e testi Document AI a ogni richiesta anche quando i documenti del fascicolo non erano cambiati. Questo non è un supporto professionale: il sistema deve sapere quando rianalizzare e quando riusare l'ultima lettura valida.

Regola corretta:

- la lettura automatica di contributo unificato, autocertificazioni, sentenze, liquidazioni e parcelle usa una cache LRU in memoria del processo applicativo;
- la chiave della cache contiene tenant, fascicolo, numero/RG, cliente, stato pagamenti e impronta documentale calcolata su id, nome, nome originale, tipo, hash, dimensione, data caricamento e id portale;
- se viene caricato, modificato o ricollegato un documento, l'impronta cambia e la lettura economica torna automaticamente da eseguire;
- se i documenti e i pagamenti restano identici, la vista economica riusa la fonte automatica già letta e non riapre fisicamente gli stessi file.
- una lettura senza evidenze ha durata breve, così un OCR di fondo completato dopo il primo caricamento può essere recepito senza attendere modifiche manuali al fascicolo.

Guardrail aggiunti:

- `tests/test_react_shell.py::test_react_fascicoli_economia_non_riapre_documenti_invariati`;
- `tests/test_react_shell.py::test_react_fascicoli_economia_cache_cambia_quando_arriva_nuovo_documento`.

Prove obbligatorie prima della chiusura del rilascio:

- verificare che i casi reali `Betti`, `Merdini` e `Alfano` conservino gli esiti corretti;
- misurare due richieste consecutive della vista economica sul server: la seconda deve essere sensibilmente più rapida perché non rilegge i file invariati;
- verificare locale Docker reale `127.0.0.1:8080`, commit GitHub gemelli, deploy Hetzner e container unico `iusentra-app`.

## Deposito React lazy chunk e E2E Nightly 2026-07-07

Aggiornamento operativo per alleggerire il caricamento iniziale di IUSENTRA e chiudere i failure notturni del workflow E2E Nightly.

Regola corretta:

- il flusso `Prepara deposito` non resta più dentro il blocco iniziale di `FascicoliPage.tsx`;
- il modulo operativo del deposito vive in `frontend/src/components/FascicoloDepositoPage.tsx`;
- `FascicoliPage.tsx` importa il deposito con `React.lazy()` solo quando la rotta è `/fascicoli/<id>/deposito/prepara`;
- la pagina elenco e il dettaglio fascicolo continuano a caricare solo il chunk fascicoli, mentre `FascicoloDepositoPage-*.js` viene richiesto quando l'avvocato clicca `Deposito telematico` o apre direttamente la rotta deposito;
- l'assistente vocale Studio e il visible text guard partono su finestra idle/fallback, così non competono con il primo render React.

Fix E2E Nightly collegati:

- `GestioneTenant.percorsi_dati()` espone di nuovo l'alias compatibile `STUDIO_CONFIG`, oltre a `CONFIG_STUDIO_DB`;
- `tests/e2e/test_ai_pipeline_full.py` verifica la tabella `legal_procedures` nel database reale del repository di coverage, non in uno `studio.db` temporaneo privo dello schema.

Guardrail eseguiti:

- `npm run typecheck` in `frontend`;
- `npm run build` in `frontend`;
- `npm test` in `frontend`;
- `python scripts/run_pytest_phases.py --suite e2e-nightly --suite-shard 1 --suite-total-shards 4 --timeout-minutes 5`;
- `python scripts/run_pytest_phases.py --suite e2e-nightly --suite-shard 2 --suite-total-shards 4 --timeout-minutes 5`;
- `python scripts/run_pytest_phases.py --suite e2e-nightly --suite-shard 3 --suite-total-shards 4 --timeout-minutes 5`;
- `python scripts/run_pytest_phases.py --suite e2e-nightly --suite-shard 4 --suite-total-shards 4 --timeout-minutes 5`;
- `python -m pytest -q tests/test_legal_coverage_surface.py tests/test_ai_coverage_pipeline.py tests/test_storage_postgres_migration.py`;
- `python -m pytest -q tests/test_web_bootstrap.py::test_tenant_percorsi_dati_fast_path_non_avvia_baseline_runtime tests/test_legal_coverage_pipeline.py::test_sqlite_coverage_repository_supporta_pipeline_end_to_end`;
- `python -m compileall -q pct web tests`;
- `docker compose build --no-cache` e `docker compose up -d` sulla copia locale reale.

Misure e prova reale locale:

- build Vite: `FascicoliPage` scende da circa `364 KB` raw a circa `264 KB` raw; il deposito viene emesso come chunk separato di circa `130 KB` raw;
- Docker reale `127.0.0.1:8080`: `/api/pronto` `http=200`, `time_starttransfer=0.005000`, `time_total=0.005179`;
- root locale `http=302`, `time_starttransfer=0.004492`, `time_total=0.004592`;
- browser integrato su `127.0.0.1:8080`: login tenant locale controllato, pagina `/fascicoli` con `8` fascicoli e `75` documenti visibili, stato `Dati aggiornati`, nessun chunk `FascicoloDepositoPage` caricato nell'elenco;
- click reale su fascicolo `DC5BF1DB`, pulsante `Deposito telematico`: apertura `/fascicoli/DC5BF1DB/deposito/prepara`, testo `Prepara deposito` visibile, stato non bloccato, e link al chunk `FascicoloDepositoPage-CSjEWB3t.js` presente solo dopo il click.

## Deposito Giudice di Pace / SIGP - prova reale locale 2026-07-09

Problema reale risolto sul fascicolo locale `DC5BF1DB`: dopo le modifiche precedenti, il pannello deposito poteva ripartire dalla prima voce del catalogo (`SICID`) invece dal ramo coerente `SIGP`, generando il blocco `Registro non compatibile con il procedimento` durante `Simula invio PEC`.

Regola corretta:

- il pannello tipo deposito non seleziona più la prima voce disponibile;
- quando il fascicolo è Giudice di Pace e l'atto principale è una nota/trattazione scritta, il software suggerisce `Deposito note scritte sostitutive udienza (Giudice di Pace)`;
- la scelta manuale dell'avvocato resta prevalente e non viene sovrascritta dal suggerimento automatico;
- il validatore backend accetta `SIGP` come canale coerente per ufficio Giudice di Pace e profili `RG/RGL/VG`;
- `SICID` resta bloccato se l'ufficio è Giudice di Pace, perché sarebbe il ramo sbagliato.

Guardrail eseguiti:

- `python -m py_compile pct/deposito_guidato.py scripts/audit_deposito_catalogo_end_to_end.py web/services/react_fascicoli_bridge.py`;
- `python scripts/audit_deposito_catalogo_end_to_end.py --output artifacts/react-migration/audit-deposito-catalogo-end-to-end-2026-07-09.json`;
- `python -m pytest tests/test_deposito_telematico_catalogo.py tests/test_busta.py tests/test_canali_telematici_deposito.py tests/test_deposito_guidato.py::test_orchestratore_accetta_sigp_su_giudice_di_pace tests/test_deposito_guidato.py::test_orchestratore_blocca_sicid_su_giudice_di_pace tests/test_deposito_guidato.py::test_orchestratore_accetta_sicid_su_tribunale_ordinario -q`;
- `python -m pytest tests/test_regia_ui_react.py::test_deposito_resolver_ufficio_completa_pec_e_codice_da_catalogo tests/test_regia_ui_react.py::test_deposito_resolver_non_si_ferma_a_pec_profilo_senza_codice tests/test_regia_ui_react.py::test_ui_deposito_tipo_deposito_non_prende_la_prima_voce_e_suggerisce_sigp_note tests/test_regia_ui_react.py::test_ui_deposito_avvisi_classificazione_non_spengono_prova_e_non_autoselezionano_tutto tests/test_regia_ui_react.py::test_ui_deposito_prova_guidata_non_salta_firma_e_mostra_audit_pec_indice -q`;
- `npm --prefix frontend run typecheck`;
- `npm --prefix frontend run build`;
- `docker compose build --no-cache`;
- `docker compose up -d`;
- `http://127.0.0.1:8080/api/pronto` -> `ok=true`, versione `2.254.19`.

Prova reale browser integrato su `127.0.0.1:8080`:

- pagina `/fascicoli/DC5BF1DB/deposito/prepara#generazione-busta` caricata dopo rebuild Docker;
- tipo deposito visibile: `Giudice di Pace (28)` / `Atti endo-processuali (11)` / `Deposito note scritte sostitutive udienza (Giudice di Pace)`;
- ufficio: `Ufficio del Giudice di Pace di Palmi`, PEC `gdp.palmi@civile.ptel.giustiziacert.it`, codice ufficio risolto automaticamente;
- atto principale: `Note trattazione scritta Alessi Robertino c Zurich Ass.ni-signed.pdf.p7m`;
- `Prova senza invio reale` e `Simula invio PEC` abilitati e cliccati materialmente;
- il blocco `Registro non compatibile con il procedimento` non compare più;
- entrambi i click si fermano sul requisito reale `Dispositivo non pronto per firmare i dati del deposito: Nessun dispositivo di firma rilevato`;
- `Invia deposito reale` resta disabilitato perché la prova senza invio non può superare la firma dei dati deposito senza dispositivo fisico disponibile.

Stato residuo da non dichiarare verde: per abilitare `Invia deposito reale` sul caso concreto serve ripetere la prova con smart card/token e middleware Local Signer realmente pronti, firmare i dati deposito, generare/verificare `Atto.enc` e solo dopo controllare l'abilitazione del bottone.

## Deposito - copertura generatori, scelta dell'avvocato e campi ministeriali 2026-07-12

Rapporto completo: `artifacts/react-migration/deposito-confronto-fonti-2026-07-12.md`.

La verifica combina il catalogo ricostruito dal materiale decompilato con gli XSD ministeriali attivi. Gli XSD restano la fonte decisiva per struttura, sequenza, cardinalità e validità del `DatiAtto.xml`.

Esito audit:

- 270 tipi complessivi;
- 252/252 generatori PCT eseguiti e validati;
- 0 rami PCT sospesi;
- 67 rami contributo/esenzione e 122 guardie sui campi obbligatori;
- 593 uffici PCT operativi confrontati, senza codici o PEC mancanti e senza difformità del resolver.

Regola UX aggiornata, che sostituisce il suggerimento automatico documentato nella tranche SIGP del 9 luglio 2026:

- nei casi nuovi l'avvocato sceglie il tipo di deposito;
- nei casi nuovi nessun documento viene incluso automaticamente;
- il software propone candidati, applica controlli e conserva le scelte già salvate;
- un tipo o un atto principale non scelti bloccano con un messaggio specifico;
- documenti non indispensabili restano avvisi e non spengono le prove;
- i dati ministeriali mancanti aprono direttamente il pannello nel quale inserirli.

Nel click reale sul fascicolo produzione `795C50AC`, il tipo salvato `Opposizione a decreto ingiuntivo (mediante ricorso)` ha richiesto numero, anno e data del decreto. Il primo tentativo ha scoperto un errore generico `HTTP 500`, poi corretto sia nel frontend sia nella rotta backend: il flusso ora mostra i campi, apre il pannello corretto e restituisce sempre una risposta controllata. Nessuna PEC è stata inviata.

Prova reale locale eseguita il 12/07/2026 sulla copia Docker obbligatoria `http://127.0.0.1:8080`, versione applicativa corrente `2.256.0`, container `iusentra-app` healthy e `/api/pronto` con fuso `Europe/Rome`:

- fascicolo controllato `A1FB22FE`, senza copiare dati dal tenant di produzione e senza salvare le scelte temporanee;
- ingresso nella fase `Documenti` con `0 selezionati`, tipo sul placeholder `Scegli il tipo di deposito` e nessun documento incluso automaticamente;
- cambio reale della macroarea in `Corte di Cassazione (civile)`: il tipo è rimasto vuoto, quindi il software non ha sostituito la scelta dell'avvocato;
- selezione temporanea di `Opposizione a decreto ingiuntivo (mediante ricorso)`: comparsi esattamente i tre campi obbligatori `Numero del decreto ingiuntivo`, `Anno del decreto ingiuntivo`, `Data del decreto ingiuntivo` e i due riferimenti facoltativi alla causa collegata;
- click reale su `Completa dati deposito`: apertura immediata del pannello e campi visibili, senza cambiare pagina e senza inviare PEC;
- fase pacchetto con blocco nominativo su atto principale e dati mancanti; i tre pulsanti restano correttamente disabilitati nel fascicolo locale privo di documenti, senza falso esito positivo;
- click reale finale sulla fase `Busta e indice`: Tribunale di Vicenza, PEC e codice ufficio risultano risolti automaticamente; la UI separa l'atto principale da scegliere dai tre dati obbligatori del decreto e mantiene procura/allegati come avvisi non bloccanti quando l'avvocato ha già salvato la propria scelta;
- secondo click reale su `Completa dati deposito`: ritorno immediato alla fase Documenti con i tre campi obbligatori e i due riferimenti facoltativi visibili; ricaricamento finale con tipo non selezionato e `0 selezionati`, senza salvataggi e senza invii;
- focus reale sul primo campo con bordo visibile e controllo dello stato hover del comando di salvataggio;
- scroll completo e prova responsive a `1440x900`, `1024x768` e `390x844`; durante la prima prova tablet il pulsante flottante dell'assistente copriva parzialmente `Firma`, quindi la navigazione ha ricevuto una riserva laterale solo nel relativo intervallo e i comandi mobile sono stati estesi alla larghezza disponibile; la seconda prova non ha mostrato sovrapposizioni né testo tagliato nei comandi.

Guardrail finali sul sorgente locale: 64 test deposito mirati e 152 test completi della shell React superati; typecheck e build frontend superati; gate qualità Codex, contratti API/OpenAPI, smoke, baseline Python, Ruff, Flake8, `compileall` e sincronizzazione pacchetto superati. La copia Docker reale risponde su `/api/pronto` con versione `2.256.0`, fuso `Europe/Rome` e container `iusentra-app` healthy.

Il gate governance ha bloccato una prima preparazione del commit per dimensione della rotta e due stringhe non integre nel generatore. I metadati `DatiBusta` e la trasformazione dell'errore ministeriale in risposta JSON controllata sono stati delegati ai servizi dedicati; le stringhe sono state corrette, i test statici sono stati riallineati alla delega e l'intera sequenza audit/test/governance è stata ripetuta con esito positivo. La prova browser è stata quindi ripetuta sulla nuova immagine Docker, non riutilizzata dalla build precedente.

Il primo push `80c0b1ad` ha inoltre evidenziato una mappa sicurezza backend generata non aggiornata per il nuovo endpoint di salvataggio. La CI ha correttamente fermato lint e shard dipendenti; la mappa è stata rigenerata a 270/270 endpoint autenticati e il commit correttivo `6429973c` ha poi superato lint, governance, smoke, frontend, CodeQL, coverage 12/12, tutti gli shard Pytest e Local Signer/PKCS#11 su macOS, Ubuntu e Windows.

Deploy Hetzner verificato sullo stesso commit: repository server allineato, un solo `iusentra-app`, servizi healthy, `/api/pronto` interno ed esterno `2.256.0` in `Europe/Rome`, impronte dei sorgenti e del bundle coincidenti, cache Docker vuota e nessuno snapshot temporaneo.

Prova server con click reali su `795C50AC`: scelta salvata invariata con il solo `Ricorso.pdf.p7m` come atto principale; ufficio, PEC e codice risolti; Procura non bloccante; prova senza invio e simulazione PEC cliccate e confermate. Entrambe hanno aperto i tre campi mancanti senza `HTTP 500`, senza PEC esterna e senza incrementare le `4` ricevute di prova già presenti. `Invia deposito reale` è rimasto disabilitato, correttamente, perché numero, anno e data del decreto non sono stati inseriti e non era disponibile una nuova prova completa con dispositivo di firma fisico.

Il codice runtime è chiuso sui branch gemelli al commit `6429973c`; il commit documentale finale deve superare a sua volta gli stessi gate e il deploy, senza modificare il runtime già provato. La prova completa del pacchetto sul caso concreto resta subordinata a inserimento dei tre dati da parte dell'avvocato, dispositivo di firma fisico e Local Signer pronti.

## React shell - entry Vite senza query string 2026-07-06

Aggiornamento operativo `2.253.194`.

Durante la prova reale su `https://app.iusentra.it/fascicoli?vista=economica` il browser integrato mostrava solo il widget Lex e il `#root` React restava vuoto. La diagnosi con Chrome separato ha evidenziato che l'entry Vite veniva richiesta due volte: `/static/react/assets/index-Dpk0SLzI.js?v=2.253.193` dal template e `/static/react/assets/index-Dpk0SLzI.js` dai chunk importati. Poiché i file Vite sono già hashati nel nome, la query `?v=` sull'entry ES module non è necessaria e può creare istanze modulo non canoniche.

Regola corretta: gli asset ES module Vite nella shell React si caricano con URL hashato puro (`{{ js_file }}`), mentre gli script classici non hashati restano versionati con `?v={{ app_version }}`. Guardrail aggiornati: `tests/test_react_shell.py::test_react_shell_mobile_sblocca_scroll_e_compatta_card` e `frontend/scripts/check-react-contracts.mjs`.

Prova locale eseguita su Docker reale `127.0.0.1:8080` dopo rebuild `--no-cache`: `/api/pronto` risponde `2.253.194`, `iusentra-app` è healthy, la pagina `/fascicoli?vista=economica` monta `#root` React e l'entry osservata è `/static/react/assets/index-Dpk0SLzI.js` senza query `?v=`.

## Presidio documentale incrementale persistente - 12/07/2026

Problema reale rilevato durante il controllo del deposito e dei processi automatici: il worker documentale conservava l'esito per documento, ma a ogni ciclo ricostruiva comunque l'inventario dei fascicoli e interrogava testi già estratti per stabilire la priorità. Nel tenant di produzione principale erano presenti `2.641.950` eventi storici `document_ai.read` attribuiti al vecchio attore `scheduler`; continuare con la stessa strategia avrebbe prodotto lavoro ripetuto, crescita del database e WAL e tempi non coerenti con un presidio professionale.

Regola applicata:

- un documento viene acquisito e analizzato una volta; testo ed esiti restano nelle tabelle SQL Document AI;
- il completamento dell'inventario viene salvato nell'audit SQL append-only `pec_audit_log` con stato `complete`, versione parser, numero documenti e impronta SHA-256 del fascicolo;
- l'impronta usa solo metadati persistiti: identificativo, nome, tipo, percorso, dimensione, hash contenuto, date documentali e versioni precedenti; non apre i file;
- se l'impronta è invariata, il job salta il fascicolo prima della raccolta sorgenti e prima della query ai testi;
- se arriva o cambia un documento, cambia l'impronta del fascicolo, ma gli identificativi documento+hash già marcati restano esclusi: viene elaborato soltanto il documento nuovo o modificato;
- un lotto parziale, un lock SQLite o un errore transitorio non vengono registrati falsamente come lettura completa;
- un fascicolo con scadenza futura già presidiata viene salvato con stato `deferred`, impronta corrente e `resume_after`: finché la data non scade e i documenti non cambiano, il job lo salta senza aprire i file; dopo la data o una modifica torna automaticamente nel perimetro di controllo;
- la priorità Lex interroga soltanto i fascicoli variati e collega testo e documento per tenant, fascicolo, documento e versione corrente, eliminando il precedente collegamento SQL troppo ampio;
- le aperture eseguite da persone continuano a produrre audit `document_ai.read`; soltanto gli attori automatici del worker non aggiungono milioni di eventi di lettura ridondanti.

Correzioni collegate emerse nei gate:

- la ricostruzione della matrice PEC ora genera un identificativo dell'evento legale deterministico anche rispetto alla versione analizzata, evitando il conflitto `UNIQUE` tra due versioni della stessa PEC e conservando entrambe;
- il test calendario all-day usa una data futura relativa, così non diventa falsamente rosso con il passare del tempo;
- la preparazione deposito salva classificazione documenti e profilo in un'unica transazione sul solo fascicolo interessato, sia con SQLite sia con PostgreSQL;
- prima di qualsiasi scrittura, prova senza invio e simulazione controllano i dati ministeriali obbligatori; una prova storica non riabilita l'invio reale dopo una modifica del pacchetto.

Guardrail automatici eseguiti:

- `17` test del presidio documentale, inclusi prima acquisizione, secondo ciclo senza richiamo alle sorgenti o ai testi, aggiunta di un solo documento, budget parziale, lock, rinvio persistente con riesame e rotazione;
- suite combinata `tests/test_pec_audit_pipeline.py`, `tests/test_document_intelligence_service.py`, `tests/test_regia_api_payloads.py` e `tests/test_regia_ui_react.py`: `110` test superati;
- `ruff` mirato sui moduli modificati: nessuna violazione;
- build Docker reale locale di app, scheduler e OCR; `http://127.0.0.1:8080/api/pronto` ha risposto `ok=true`, versione `2.256.0`, fuso `Europe/Rome`.

Prova materiale locale nel browser integrato su `127.0.0.1:8080`, fascicolo `A1FB22FE`, senza salvataggi e senza invii:

- tipo deposito inizialmente non scelto e `0` documenti selezionati automaticamente;
- selezione temporanea di `Opposizione a decreto ingiuntivo (mediante ricorso)` con comparsa puntuale di numero, anno e data del decreto come obbligatori e dei due riferimenti alla causa come facoltativi;
- `Completa dati deposito` è tornato al pannello corretto e il primo campo ha ricevuto il focus reale;
- Tribunale di Vicenza, PEC e codice ufficio sono stati risolti automaticamente;
- prova, simulazione e invio reale sono rimasti disabilitati per il motivo essenziale reale `Atto principale da selezionare`, non per avvisi facoltativi;
- controllo desktop, tablet `1024x768` e mobile `390x844`: nessun overflow orizzontale, testi leggibili e navigazione coerente;
- la password dell'account tecnico locale è stata cambiata solo per la sessione visibile e ripristinata subito dopo nei repository governati; nessun account di produzione è stato modificato.

Prova worker reale su Hetzner, senza cancellazioni, backup o modifiche ai documenti dello studio:

- baseline: `2.641.950` letture automatiche storiche, ultima alle `21:30` ora italiana dell'11/07/2026;
- dopo più cicli reali del job `pec_audit_pipeline_workers`, il contatore è rimasto `2.641.950`;
- `30` documenti nuovi o da rivalutare hanno prodotto `30` resource ID distinti e `0` duplicati;
- `14` fascicoli risultano già consolidati con impronta completa; il backlog restante procede nei lotti previsti senza rileggere quelli già marcati;
- cicli documentali chiusi con `0` errori e `0` rinvii per lock; il tratto caldo per il tenant principale si è chiuso in circa otto secondi;
- app, scheduler e OCR sono rimasti healthy; nessuna PEC o deposito reale è stato inviato.

Questa modifica non cambia generatori, tabelle ministeriali, scelta del tipo deposito o regole ricostruite dal materiale Studio Telematico. Restano valide le fonti e la matrice `252/252` già documentate in `deposito-confronto-fonti-2026-07-12.md`; cambia soltanto il riuso persistente dei risultati già acquisiti.

## Attestazione di conformità nella relata - 13/07/2026

La generazione dell'attestazione di conformità collegata alla notifica è stata riallineata al modello Word consegnato dallo studio. L'attestazione è unica per tutte e sole le copie selezionate dall'avvocato, viene inserita cumulativamente nella relata e può essere scaricata come DOCX senza duplicare una dichiarazione per ciascun allegato. La scelta documentale resta manuale e nessun documento viene incluso automaticamente.

Prova locale eseguita con tre documenti, click reali e download confermato su `127.0.0.1:8080`, senza firma, PEC o deposito reale. Il controllo strutturale dimostra che il generatore modifica soltanto `word/document.xml` del modello e conserva tutte le altre parti; il render Word è una pagina senza evidenziazioni, tagli o sovrapposizioni. Dettaglio completo: `artifacts/notifiche-legali/attestazione-conformita-unica-2026-07-13.md`.

Questa tranche non cambia `DatiAtto.xml`, `IndiceBusta.xml`, `Atto.enc`, generatori ministeriali o regole di abilitazione dell'invio deposito.

## Automazione successiva al deposito - scheda di cancelleria e copia PST 15/07/2026

Il ciclo successivo all'invio del ricorso è stato esteso usando come evidenza reale la scheda `Documento_30446614.pdf` del procedimento `RG 771/2025`. La scheda viene normalmente anticipata dalla comunicazione di cancelleria e acquisita successivamente nella sua copia ufficiale tramite PST.

Comportamento applicativo introdotto:

- ogni nuovo documento PEC, caricato o scaricato dal PST entra nel medesimo presidio incrementale;
- la scheda viene riconosciuta dalla struttura dei campi di ruolo, non dal solo nome del file;
- RG e anno sono la guardia primaria: una scheda discordante non può sovrascrivere un fascicolo diverso;
- ufficio, iscrizione, sezione, giudice, ruolo, materia, oggetto, parti, difensore, contributo unificato e prima udienza vengono consolidati solo se mancanti o coerenti;
- la provenienza, l'identificativo del documento e l'impronta SHA-256 restano nel fascicolo per audit e idempotenza;
- la copia PST completa la conoscenza del fascicolo senza diventare un documento da reinviare nella busta;
- al secondo ciclo, se identificativo e impronta non cambiano, il file non viene riaperto e non viene riletto;
- l'esenzione esplicita del contributo unificato viene registrata senza importo e senza creare una proforma;
- la prima udienza alimenta i processi già governati di fascicolo, Agenda e Scadenziario.

Prove automatiche superate: parser campo per campo sul testo reale, variante a testo compattato su una sola riga, aggiornamento fascicolo, conflitto RG, classificazione fuori busta, esenzione, job incrementale e secondo ciclo senza lettura. La chiusura resta subordinata alla prova visibile locale e sul server reale documentata nel verbale `artifacts/pst/verifica-acquisizione-rg-771-2025-2026-07-15.md`.

## Verifica pubblici elenchi e firma relata - 16/07/2026

La tranche notifiche legali collegata al fascicolo è stata consolidata senza modificare i generatori ministeriali del deposito e senza abilitare invii dal server.

Regole applicate:

- la verifica del pubblico elenco usa il servizio ReGIndE ufficiale per indirizzo PEC;
- notificante e destinatario sono controllati separatamente e il registro mostrato in UI coincide con quello interrogato;
- il codice fiscale del notificante resta immutabile;
- il codice fiscale del destinatario può essere corretto soltanto con risposta autorevole associata alla PEC cercata e con autorizzazione esplicita del controllo destinatario;
- risposta, indirizzi, ruoli, stato e impronta dell'evidenza vengono conservati per il controllo successivo;
- un solo PIN inserito accanto a `Firma relata` viene usato sul PC locale per completare verifica e firma, poi viene cancellato dallo stato della pagina;
- la firma salva la relata nel fascicolo e non implica approvazione finale o invio PEC;
- l'invio PEC operativo resta esclusivamente locale e non è stato eseguito durante i test.

Fonti tecniche consultate:

- catalogo WSDL ministeriale locale `docs/specs/ministero/A1_WSDL_CATALOG_v1.52/WSDL/Altri Servizi/ReGIndE/ServiziInterrogazioneSoggetto.wsdl`;
- implementazione e casistiche già documentate nel confronto interno sulle notifiche;
- notifiche e dati reali del tenant usati per verificare associazione di avvocato, parte rappresentata, destinatario e pubblico elenco, senza riportare riferimenti tecnici nella UI.

Guardrail eseguiti:

- `python -m pytest tests/test_local_signer.py tests/test_notifiche_legali.py tests/test_react_asset_retention.py -q` -> `314` test superati;
- `npm run build` in `frontend` -> typecheck e build superati;
- limite per singolo asset JavaScript/CSS inferiore a `500.000` byte;
- immagine Docker locale ricostruita e `iusentra-app` ricreato healthy su `127.0.0.1:8080`;
- Local Signer `1.6.92` installato, dispositivo e certificato di firma rilevati, un solo listener locale;
- produzione aggiornata, container applicativo unico healthy e `/api/pronto` positivo.

Stato di accettazione: resta obbligatoria la prova materiale nella scheda autenticata con click su `Firma relata`, inserimento PIN, verifica positiva dei pubblici elenchi, salvataggio e apertura della relata firmata. Nessun test automatico viene usato come sostituto di tale prova e nessuna PEC reale deve essere inviata.

### Correzione verifica enti ReGIndE e prova Locri - 17/07/2026

La verifica del destinatario ente non usa più il servizio destinato ai soli professionisti. Per Avvocature, Ordini e altri enti ReGIndE viene interrogata l'operazione ministeriale `ricercaEnteEx`, fornendo contemporaneamente denominazione, codice fiscale e indirizzo PEC. La risposta è valida soltanto se l'ente è visibile, attivo e coincide con tutti i dati mostrati nella relata; non sono consentiti riallineamenti automatici del codice fiscale.

Fonti e controlli:

- WSDL ministeriale `docs/specs/ministero/A1_WSDL_CATALOG_v1.52/WSDL/Altri Servizi/ReGIndE/ServiziInterrogazioneEnte.wsdl`;
- test mirati ReGIndE in `tests/test_local_signer.py`: `9` superati;
- compilazione Python, `git diff --check` e build React superati;
- pagina Notifiche legali costruita in un chunk di circa `133 kB`, sotto il limite di `500 kB`.

Prova visibile sul server: selezionata la pratica `2026/339`, `RG 1854/2026`, Tribunale di Locri. La UI ha proposto Avvocatura Distrettuale dello Stato di Reggio Calabria, codice fiscale `92006980806`, PEC `ads.rc@mailcert.avvocaturastato.it`, ReGIndE e Ministero dell'Istruzione e del Merito. Il click `Controlla relata` non ha prodotto invii e ha mantenuto bloccata la PEC in assenza di dispositivo, documento scelto, firma e approvazione finale.

La prova crittografica finale resta **non verificata su macchina reale** perché durante questo controllo la chiavetta non era inserita. L'avvocato deve inserire il dispositivo, scegliere i documenti, inserire il PIN, ottenere esito positivo per notificante e destinatario, firmare la relata, aprire il file firmato e solo dopo dare l'approvazione finale. Nessuna PEC reale è stata inviata durante questa verifica.

### Presidio richieste UNEP e catalogo uffici - 18/07/2026

Il canale UNEP resta autonomo rispetto al deposito civile e alla notifica PEC L. 53. La pagina Notifiche legali usa ora il medesimo catalogo della sezione Tribunali: l'ufficio viene selezionato con denominazione, codice ministeriale e PEC inseparabili. Il backend risolve nuovamente il codice sul catalogo corrente e blocca combinazioni alterate o storiche non più corrispondenti.

La matrice comprende quattro mezzi di notifica e diciotto tipi di richiesta distinti. Atto, richiesta o relata, eventuale pagamento e successivi ritorni restano documenti separati del fascicolo. L'indirizzo dell'ufficio UNEP non è trattato come PEC del destinatario e non abilita da solo alcun invio.

Il controllo automatico ripetibile è `python scripts/audit_legal_notification_coverage.py`; verifica copertura del catalogo, univocità di codici e PEC, corrispondenza con la UI, uso dell'indirizzo e copertura integrale dei tipi di richiesta. La prova finale richiede click reali su produzione e sulla copia locale `127.0.0.1:8080`, senza eseguire una richiesta UNEP o una PEC reale.
## Presidio udienze da PEC e documenti, aggiornamento 17/07/2026

Il flusso collegato PEC, fascicolo, Agenda e Scadenziario conserva le attività `UDIENZA` anche nella timeline del fascicolo. Lo stesso evento strutturato trasporta modalità, data, ora, piattaforma, ID riunione, codice di accesso, istruzioni, fonte e collegamento audiovisivo.

Il centro notifiche e il Web Push non ricostruiscono il dato dal testo libero: usano il payload materializzato dalla pipeline PEC. L'azione esterna `Collegati` è disponibile soltanto quando il collegamento è stato verificato sulla fonte e il dominio appartiene all'elenco audiovisivo ammesso. Un URL non verificato o un dominio somigliante apre soltanto il dettaglio interno per il controllo.

Quando un PDF o ZIP viene letto dopo la prima registrazione e aggiunge il link verificato, il sistema aggiorna la stessa scadenza, lo stesso appuntamento e la stessa notifica. Il record torna non letto e viene inviato un solo nuovo Web Push per l'informazione aggiunta; una seconda elaborazione invariata non crea duplicati.

Verifiche automatiche del 17/07/2026: 86 test mirati, build e contratti React, integrità UTF-8, conservazione asset e budget massimo di 500 kB per chunk. La chiusura resta subordinata alla prova materiale finale sul server e a una consegna Web Push osservata con sottoscrizione reale del browser.

### Prova reale locale dei canali udienza - 17/07/2026

Sulla copia reale `http://127.0.0.1:8080` è stato seguito con click il medesimo evento controllato attraverso Agenda, Scadenziario, timeline del fascicolo e centro notifiche. I quattro punti hanno mostrato gli stessi dati strutturati e il collegamento audiovisivo verificato, senza perdere note o fonte.

Nel pannello Notifiche il dispositivo è stato registrato, la notifica di prova è stata inviata e mostrata e lo stato finale è risultato `Attivo`. È stato inoltre eliminato lo stato indefinito `Attivazione...`: se il browser non conclude il permesso o il riallineamento, l'operazione termina entro il limite governato e restituisce un messaggio comprensibile. La verifica non ha prodotto invii PEC, depositi o notifiche legali reali.

### Ciclo dei pubblici elenchi per le notifiche - 18/07/2026

Il confronto approfondito del flusso di compilazione ha confermato che non deve esistere una rubrica statica presentata come certificata. La regola operativa implementata è: selezione della fonte corretta, ricerca del soggetto, associazione fra identità e PEC, registrazione di data e ora italiane e conservazione della prova nel fascicolo. La UI non espone riferimenti tecnici al prodotto usato per il confronto.

Le fonti sono governate per capacità effettiva:

- `ReGIndE`: interrogazione autenticata tramite il servizio ministeriale e prova restituita dal servizio;
- `Registro PP.AA.`: consultazione autenticata sul Portale dei Servizi Telematici, con conferma nominativa dell'avvocato dopo aver visto soggetto e PEC;
- `INI-PEC professionisti`, `INI-PEC imprese` e `Registro Imprese`: consultazione del portale ufficiale e conferma nominativa della corrispondenza;
- `INAD`: consultazione pubblica assistita; l'eventuale CAPTCHA resta svolto dall'avvocato e non viene eluso;
- `ANPR`: non è trattato come pubblico elenco PEC valido per una notifica e non può produrre una verifica positiva;
- `IPA`: resta distinto dal Registro PP.AA. del Ministero della Giustizia e non può certificarne l'esito.

La conferma conserva nel `source_snapshot` SQL-backed del fascicolo: tenant e fascicolo, fonte, URL ufficiale, PEC, codice fiscale o partita IVA, denominazione, data e ora della consultazione in `Europe/Rome`, operatore autenticato, metodo di verifica e impronta SHA-256 della prova. La validazione rifiuta fonti non ammesse, prove alterate, URL diversi dalla fonte configurata, identità mancanti, orari futuri o consultazioni assistite più vecchie di quattro ore. Non sono state aggiunte tabelle divergenti fra SQLite e PostgreSQL.

Guardrail eseguiti prima del collaudo reale: `89` test notifiche legali, `233` test Local Signer, audit di copertura con `7` fonti pubbliche, `141` uffici UNEP, `18` tipi di richiesta e nessun fallimento; typecheck e build React superati. Il modulo Notifiche legali pesa `142,15 kB` e il chunk JavaScript corrente più grande pesa `369,24 kB`, entrambi sotto il limite di `500 kB`.

Stato di accettazione: il codice e i guardrail sono pronti; la voce resta aperta finché non vengono eseguiti sul server e sulla copia reale locale i click di apertura della fonte, conferma, ricaricamento del fascicolo e rilettura della prova conservata. Nessuna PEC reale deve essere inviata durante il collaudo.

### Documenti del fascicolo d'ufficio: confronto del flusso - 18/07/2026

Il decompilato di confronto è stato seguito lungo entrambi i percorsi usati per i documenti ufficiali.

Consultazione dalla pratica:

- prima dell'apertura vengono validati autorità giudiziaria, codice ufficio, registro, numero e anno RG, ruolo dell'utente ed eventuale sotto-procedimento;
- il browser incorporato apre il fascicolo ufficiale già contestualizzato e, quando riconosce la pagina del fascicolo, individua il collegamento alla sezione documenti e vi naviga automaticamente;
- il contenuto mostrato resta quello del portale ufficiale: il gestionale non ricostruisce una pagina parallela e non richiede di ricercare nuovamente il fascicolo.

Acquisizione strutturata:

- la ricerca documenti interroga il servizio del registro corretto e ottiene per ogni deposito identificativo documento, stato, autore, data, tipo, ufficio e riferimenti del fascicolo;
- per ogni documento viene letto il dettaglio con un elemento principale e i suoi allegati, collegati tramite l'identificativo del deposito;
- l'elenco mostra data, depositante, nome file originale, tipologia e stato di download; gli allegati sono righe figlie del documento principale;
- per ogni file l'avvocato sceglie fra duplicato/originale informatico, copia di consultazione o esclusione;
- gli elementi già presenti nella pratica sono confrontati tramite l'identificativo ufficiale del documento, marcati come acquisiti e non scaricati di nuovo;
- al completamento il file viene associato alla pratica corrente con nome originale, identificativo ufficiale, origine telematica e stato firma, quindi l'elenco documenti viene aggiornato immediatamente;
- il download manuale dal browser usa la stessa pratica già selezionata; la scelta di un'altra pratica è richiesta solo quando il percorso è stato avviato senza contesto.

Confronto con IUSENTRA:

- il servizio locale dispone già di sessioni PST riusabili, ricerca documenti, dettaglio principale/allegati, download singolo e batch, scelta copia/originale e identificativi `id_documento`/`id_cat`;
- il runtime fascicoli conserva già identificativi portale, impronta, metadati e logica di aggiornamento senza duplicati;
- manca ancora nella superficie React del fascicolo il comando completo che avvia la ricerca con i dati della pratica, presenta l'albero ufficiale, consente la scelta per file e importa nel fascicolo senza passare da una pagina separata.

Regola di implementazione: la UI deve mostrare soltanto comandi operativi per l'avvocato, senza riferimenti al prodotto confrontato o dettagli tecnici. Nessun PIN, certificato o cookie di sessione deve transitare o essere conservato sul server. Stato: analisi completata; implementazione e prova reale ancora aperte.

### Selezione documenti da fascicolo per Notifica e Deposito - 18/07/2026

Il confronto operativo con il materiale decompilato conferma che destinatari e documenti devono essere scelti prima della fase finale di relata o deposito. Il pannello finale deve lavorare sul perimetro selezionato, non ricostruire ogni volta tutto il fascicolo.

Aggiornamento implementato:

- dal fascicolo i pulsanti `Notifica` e `Deposito telematico` aprono una finestra di scelta documenti;
- l'avvocato può cercare, selezionare uno o più documenti oppure aprire il flusso senza selezione;
- la pagina di destinazione riceve i soli documenti scelti tramite query `documenti`;
- Notifica usa quella query per idratare soltanto il perimetro richiesto e preselezionarlo;
- Deposito usa la stessa query come selezione iniziale dei documenti da inviare;
- se non esiste una selezione esplicita, il comportamento storico resta invariato;
- gli indirizzi di notifica non vengono più limitati ai soli destinatari della pratica: quelli della pratica restano evidenziati, ma la ricerca include anche gli altri indirizzi disponibili;
- il percorso NEP/UNEP resta separato dalla notifica PEC L. 53 ed è accessibile rapidamente dal pannello notifica.

Guardrail eseguiti:

- `python -m pytest tests/test_notifiche_legali.py::test_payload_documenti_pratica_rispetta_selezione_esplicita_oltre_primo_blocco tests/test_notifiche_legali.py::test_payload_documenti_pratica_idrata_nome_timestamp_da_contenuto -q`;
- `python -m pytest tests/test_regia_ui_react.py::test_ui_notifiche_relata_firma_solo_con_prova_tecnica tests/test_regia_ui_react.py::test_ui_notifiche_mantiene_indirizzi_generali_e_preselezione_documenti tests/test_regia_ui_react.py::test_ui_fascicolo_notifica_e_deposito_partono_da_documenti_scelti tests/test_regia_ui_react.py::test_ui_deposito_accetta_documenti_preselezionati_da_query_fascicolo -q`;
- `pnpm --dir frontend typecheck`;
- `python -m py_compile web\services\react_notifiche_legali_bridge.py web\blueprints\api_v1_react.py`;
- `git diff --check`;
- `pnpm --dir frontend build`, senza asset JavaScript o CSS sopra `500.000` byte.

Stato: implementazione e guardrail automatici completati. Restano obbligatori deploy, click reali sul server, riallineamento locale, commit e push prima della chiusura formale.

### Hotfix 19/07/2026 - aggancio pratica Notifica da URL

Nel test reale su `https://app.iusentra.it` e' emersa una regressione: entrando in Notifica dal fascicolo con `id_fascicolo` e `documenti=...`, la pagina poteva restare senza pratica selezionata quando l'indice pratiche non era gia' disponibile. In quel caso destinatari, percorso NEP/UNEP e documenti risultavano a zero.

Correzione applicata: l'URL con `id_fascicolo`, `id_fasc` o `fascicolo` avvia sempre il caricamento diretto della pratica tramite API, senza dipendere dall'indice iniziale. La fase (`notifica`, `deposito`, `unep`, `nonpec`) continua a essere letta dalla query.

Nel pannello `Documenti da notificare` ogni documento proposto mostra anche l'azione `Visualizza documento`, collegata al visualizzatore interno del fascicolo. L'avvocato può quindi aprire la fonte prima di includerla nella relata senza uscire dal software e senza trasformare la riga in un download esterno; l'apertura avviene in una finestra sopra la pagina Notifiche, così la selezione resta stabile quando il documento viene chiuso.

Seconda correzione dello stesso hotfix: le API Notifica risolvono ora il fascicolo anche quando l'URL contiene l'identificativo pubblico della route o un alias storico, mentre il repository risponde con un ID interno diverso. Questo evita che il link diretto mostri `0 dati già proposti`, nessun documento e nessun percorso NEP/UNEP.

Verifica da ripetere sul server: Fascicolo -> Notifica -> selezione documenti -> Notifica, controllando pratica agganciata, documenti preselezionati, ricerca destinatari completa, percorso NEP/UNEP visibile e icona di visualizzazione documento funzionante.

### Hotfix 19/07/2026 - controllo documenti nel pacchetto deposito

Richiesta utente: estendere al deposito la stessa logica già applicata alla notifica, cioè partire dai documenti scelti nel fascicolo, evitare di ricaricare tutto inutilmente e consentire all'avvocato di correggere il pacchetto senza uscire dal flusso.

Correzione applicata nel pannello React `Prepara deposito`:

- la fase `Pacchetto deposito` mostra ora un comando `Visualizza` su ogni documento della busta, usando il visualizzatore interno già presente;
- la stessa fase permette di cercare un altro documento già presente nel fascicolo e aggiungerlo subito alla busta;
- se il documento manca nel fascicolo, l'avvocato può caricarlo dal PC nella stessa fase: il file viene salvato nel fascicolo e, appena l'API restituisce l'identificativo creato, viene incluso nel deposito;
- l'aggiunta di documenti invalida la prova precedente e richiede una nuova verifica del pacchetto, così firma, indice e invio lavorano sempre sul perimetro corrente;
- il comportamento storico resta invariato quando il deposito viene aperto senza una selezione esplicita da fascicolo.

Guardrail eseguiti:

- `pnpm --filter @iusentra/studio typecheck`;
- `python -m pytest -q tests/test_regia_ui_react.py`;
- `pnpm --filter @iusentra/studio build`, con `FascicoloDepositoPage` a `158,41 kB` e nessun chunk JavaScript sopra `500 kB`.

Verifica reale su produzione del 19/07/2026:

- pagina aperta su `https://app.iusentra.it/fascicoli/F7AA4E0C/deposito/prepara?documenti=9D585112%2C2A81BC67%2C10E84CA1#generazione-busta`;
- pannello `Aggiungi documenti al deposito` visibile nella fase `Pacchetto deposito`, con 17 documenti aggiungibili dal fascicolo;
- ricerca interna provata con `Procura`: il selettore ha filtrato il documento `Procura.PDF`;
- comando `Aggiungi alla busta` provato: il contatore è passato da 3 a 4 documenti in busta e la lista pacchetto ha aggiunto una riga;
- reload pagina provato: la selezione temporanea non è stata salvata senza conferma e il perimetro è tornato ai 3 documenti della query;
- comando `Visualizza` provato su documento EML del pacchetto: il lettore documento si è aperto sopra la pagina, con contenuto leggibile e pulsanti `Scarica`/`Chiudi`;
- area `Carica da PC e inserisci nella busta` aperta e verificata con caricatore reale, senza upload di file di prova per non scrivere documenti non necessari nel fascicolo di produzione.

Stato: codice compilato, test automatici mirati eseguiti, produzione Hetzner aggiornata al commit pushato e verifica reale desktop completata. Resta non eseguito solo l'upload materiale di un file esterno nel fascicolo reale, per evitare dati di prova in produzione senza necessità operativa.

### Hotfix 19/07/2026 - prova deposito sempre cliccabile

Richiesta utente: `Prova senza invio reale` e `Simula invio PEC` non devono restare disabilitati quando il sistema deve ancora diagnosticare tipo deposito, atto principale o altri requisiti; quei blocchi devono impedire l'invio reale, non la prova controllata.

Log storico controllato:

- nella prova reale del 29/06/2026 sul fascicolo `795C50AC`, `Prova senza invio reale` era cliccabile e ha concluso con busta, indice, destinatario e testo PEC pronti per il controllo;
- il successivo invio reale è stato eseguito dall'avvocato dal PC locale, con ricevute PEC osservate e successivo esito PST che ha guidato le correzioni su `Atto.msg`, `IndiceBusta.xml` e allegati `.eml`;
- le prove successive su `DC5BF1DB`, `E5AE4668` e `F08F92A2` mostrano che la simulazione positiva abilita `Invia deposito reale`, mentre l'invio reale resta bloccato solo da requisiti obbligatori effettivi.

Correzione applicata:

- `Prova senza invio reale` e `Simula invio PEC` usano ora un blocco dedicato minimo: caricamento pagina, fascicolo non disponibile o azione di prova mancante;
- tipo deposito non scelto, atto principale non selezionato o ufficio non pronto restano mostrati come diagnosi visibile, ma la prova può partire e restituire un esito controllato senza inviare nulla;
- `Invia deposito reale` conserva il blocco pieno su tipo deposito, atto principale, ufficio, dati obbligatori, prova positiva, busta/trasporto e canale PEC locale.

Guardrail aggiunto:

- `tests/test_regia_ui_react.py::test_ui_deposito_avvisi_classificazione_non_spengono_prova_e_non_autoselezionano_tutto` fallisce se i due comandi di prova tornano a usare `disabled={actionBlocked}`.

Verifica reale su produzione del 19/07/2026: aperta `https://app.iusentra.it/fascicoli/F7AA4E0C/deposito/prepara?documenti=9D585112%2C2A81BC67%2C10E84CA1#generazione-busta` sul commit `e0bcdd4a35ab26f54977148150b593111671aef7`. `Prova senza invio reale` e `Simula invio PEC` risultano cliccabili. Il click reale su `Simula invio PEC` apre la conferma "senza spedire nulla all'esterno"; dopo `Conferma` il controllo non resta bloccato e riporta il requisito puntuale `Atto principale non selezionato. Seleziona l'atto principale nello step documenti.`. `Invia deposito reale` resta disabilitato, come previsto, finché tipo deposito, atto principale e prova positiva non sono completati.

### Aggiornamento 19/07/2026 - ordine documenti da depositare

Richiesta utente: la finestra `Documenti del fascicolo`, usata anche dal pulsante `Deposito telematico`, deve mostrare prima i documenti più recenti. Questo serve quando il fascicolo contiene molti depositi, ricevute o atti acquisiti e l'avvocato deve individuare subito i file appena caricati da includere nel deposito.

Correzione applicata:

- la modale condivisa Notifica/Deposito ordina i documenti per data documento visibile, data caricamento e data portale di fallback, dal più recente al meno recente;
- lo stesso ordine viene mantenuto durante ricerca, selezione dei proposti e riepilogo documenti scelti;
- l'ordinamento non cambia le regole di abilitazione deposito, firma, prova o invio: modifica solo la leggibilità della scelta documentale.

Guardrail eseguiti:

- `python -m pytest -q tests/test_regia_ui_react.py::test_ui_fascicolo_notifica_e_deposito_partono_da_documenti_scelti`;
- `pnpm --filter @iusentra/studio typecheck`;
- `git diff --check`;
- `pnpm --filter @iusentra/studio build`, senza chunk sopra `500 kB`.

Stato: pronto per deploy e verifica reale server su fascicolo con modale aperta da `Deposito telematico`.

### Aggiornamento 20/07/2026 - presidio notifiche fascicoli Montagnese e cutoff storico

Richiesta utente: sul tenant produzione `Studio Legale Giuseppe Montagnese` il presidio interno dei fascicoli non deve più mostrare notifiche da eseguire quando in realtà sono già state eseguite. Regola di dominio confermata dall'utente: fino al `19/07/2026` tutto ciò che andava notificato è stato eseguito e notificato; il tracciamento operativo stretto parte dal `20/07/2026`.

Correzione applicata:

- nel payload React del fascicolo il presidio relata riconosce la `prova_depositata` quando esistono documenti storici di notifica, RAC/RdAC e deposito prova;
- per lo storico ante `20/07/2026` è stato introdotto lo stato `storico_gestito`, che non genera più `Relata da firmare`, `Prepara relata` o azioni equivalenti a nuova notifica;
- dal `20/07/2026` in poi eventuali provvedimenti/documenti da notificare restano invece operativi e vengono riportati come residui veri;
- il presidio operativo interno al fascicolo non crea azioni per `prova_depositata` e `storico_gestito`;
- un nuovo audit fuori dal caricamento UI (`scripts/audit_notification_relata_fascicoli.py`) produce JSON/Markdown con elenco naturale di ciò che resta da notificare, azioni correlate, campione 30 fascicoli e tempi di calcolo;
- un nuovo materializzatore schedulato (`legal_notification_relata_presidio`) collega i residui futuri a notifiche operative/topbar/Web Push e, se sono vere notifiche da eseguire, allo scadenziario `TipoTermine.NOTIFICA`, con marker deduplicato `IUSENTRA_LEGAL_NOTIFICATION`.

Prova server reale sul tenant Montagnese:

- fonte di verità: `/data/tenants/studio-legale-giuseppe-montagnese/studio.db`, tabella `fascicoli`, campo `documenti_json`;
- audit produzione: `333` fascicoli DB, `301` visibili analizzati, `32` archiviati saltati;
- esito: `0` nuove notifiche da eseguire, `0` azioni correlate residue, `0` falsi positivi;
- conteggi: `250` `prova_depositata`, `17` `prova_raccolta`, `6` `storico_gestito`, `28` `monitoraggio`;
- performance audit: media `2.545 ms`, massimo `5.631 ms` per fascicolo, senza scansioni OCR/mailbox nel caricamento pagina;
- report conservati in `artifacts/notifiche-legali/audit-montagnese-301-20260720.json` e `.md`.

Verifica browser produzione:

- fascicolo reale `BE831526` aperto su `https://app.iusentra.it/fascicoli/BE831526`;
- visibile `Prova notifica depositata`;
- visibile messaggio `Notifica già eseguita e prova già depositata nel fascicolo: nessuna nuova notifica da preparare`;
- assenti `Relata da firmare` e `Firma relata`;
- click su `Apri prova depositata` porta a `#cancelleria` senza preparare una nuova notifica e senza invio.

Stato anti-regressione: coperto da `tests/test_notification_relata_fascicolo.py` e `tests/test_notification_relata_materializer.py`. Il server è stato verificato con `iusentra-app` unico/healthy e `/api/pronto` `ok=true`, fuso `Europe/Rome`. Il lavoro resta da riallineare su copia locale, commit/push branch gemelli e deploy finale da commit.
### Aggiornamento 21/07/2026 - fonti PEC ricevute e presidio notifica

Nel flusso Agenda/Scadenziario collegato a PEC e notifiche legali è stata uniformata la visualizzazione delle ricevute di accettazione/consegna:

- la fonte operativa non è più la casella PEC generica, ma la PEC specifica risolta da Control Tower e `pec_audit.sqlite`;
- `Apri origine` usa `/email/?audit_id=<PEC>&embed=source`, con vista incorporata priva di topbar operativa e widget Lex;
- la scheda operativa mostra oggetto, mittente, destinatario, allegati e attività concreta per l'avvocato;
- se il collegamento al fascicolo è debole, il software non forza cliente/RG e mostra solo `Possibile fascicolo da verificare`;
- se una riga storica è tipizzata male ma l'oggetto reale indica `CONSEGNA:`, la UI mostra `PEC di consegna`, così la classificazione visibile segue la ricevuta reale.

Caso reale verificato su produzione: scadenza `587c1f99-08a4-4847-8e13-c1ee372410fd`, PEC `pec_f205aa7f34c13b363f94af81`, ricevuta di accettazione della PEC inviata a `usp.vv@istruzione.it` per liquidazione spese legali relative alla sentenza n. 325/2025 del Tribunale di Vibo Valentia. Il possibile fascicolo `Contarese c. MIM` resta da verificare e non viene collegato come cliente certo.

Audit server su 30 ricevute omologhe: `30/30` aprono una PEC specifica, `17` match deboli non forzano `fascicoloId`, le consegne vengono etichettate come consegne anche con flag tecnico storico incoerente.

Test mirati collegati:

- `tests/test_react_scadenziario_additions.py::test_scadenziario_ricevuta_accettazione_control_tower_apre_pec_specifica`;
- `tests/test_react_scadenziario_additions.py::test_scadenziario_ricevuta_consegna_prevale_su_tipo_tecnico_storico`;
- `tests/test_react_shell.py::test_react_agenda_ricevuta_accettazione_apre_pec_specifica_senza_cancelleria_generica`;
- `tests/test_email_client.py::test_base_template_non_renderizza_vecchio_lex_duplicato`.

Stato: verificato sul server reale; resta aperto fino a riallineamento locale `127.0.0.1:8080`, gate completi, commit/push branch gemelli e deploy finale ordinato.

### Aggiornamento 21/07/2026 - sentenza ex art. 429 e notifica da valutare

Caso utente: sentenza Alfano Giuseppe c. MIM, RG `1100/2026`, Tribunale di Padova, ricevuta tramite PEC di cancelleria e documento `19040620s.pdf`.

Regola operativa fissata:

- la comunicazione di cancelleria o il deposito della sentenza non provano la notifica dell'avvocato;
- il termine breve di impugnazione non decorre automaticamente dalla sola comunicazione di cancelleria;
- se il provvedimento è una sentenza a verbale o sentenza ex art. 429 c.p.c., l'evento prevalente è `sentenza_a_verbale`, anche se nel verbale compare la modalità 127-ter usata prima della decisione;
- il presidio notifica resta aperto finché non risultano relata, invio PEC locale, RAC, RdAC completa e prova/deposito collegati al fascicolo;
- lo stato `NOTIFICATION_CONFIRMED` viene esposto come `Notifica necessaria confermata`, per evitare che l'avvocato lo interpreti come notifica già materialmente eseguita.

Audit produzione sul tenant `studio-legale-giuseppe-montagnese`:

- fonte fascicoli/scadenze/agenda: `studio.db`;
- fonte PEC/eventi/presidi: `email/pec_audit.sqlite`;
- PEC acquisite: `1.369`;
- PEC senza evento V2 dopo validazione: `0`;
- presidi notifica attivi: `5`, di cui `4` `NEEDS_REVIEW` e `1` `NOTIFICATION_CONFIRMED`;
- caso Alfano: presidio `NEEDS_REVIEW`, notifica da valutare/preparare, nessuna prova completa post-sorgente nel fascicolo.

Limite ancora aperto: la prova visiva automatica non è stata completata perché gli strumenti non hanno agganciato il browser integrato né un browser di default; lo screenshot desktop ha mostrato Codex e non IUSENTRA. Prima della consegna finale servono verifica materiale della UI produzione, riallineamento locale con snapshot tenant corretto e prova su `127.0.0.1:8080`.

### Aggiornamento 21/07/2026 - integrità `studio.db` e notifica affidabile

Per i flussi sensibili collegati a deposito, relata, PEC e prova notifica, il database del tenant è parte della conformità: se `studio.db` non è SQLite valido, il software non può dichiarare corretti presìdi, scadenze, topbar o stati fascicolo.

Sul tenant produzione `studio-legale-giuseppe-montagnese` è stato rilevato e corretto un caso bloccante:

- `studio.db` conteneva JSON dello Scadenziario invece di un database SQLite;
- il file anomalo e i relativi `-wal`/`-shm` sono stati preservati in backup forense;
- il nuovo `studio.db` è stato ricostruito da mirror tenant-aware core, verificato con `PRAGMA quick_check=ok` e installato dopo stop breve di app e scheduler;
- il nuovo database contiene solo dominio core e mirror leggeri, non OCR/PDF/ZIP/documenti_ai massivi;
- `pct/cache.py` blocca ora lettura/scrittura JSON su `.db`, `.sqlite` e `.sqlite3`.

Regola per chiusura futura: prima di considerare affidabile una notifica o un deposito derivato da fascicolo/PEC, verificare che la fonte SQL del tenant sia valida, leggera e coerente. Se il WAL cresce in modo anomalo o `studio.db` perde l'header SQLite, la consegna resta aperta anche se la UI sembra caricarsi.

### Aggiornamento 22/07/2026 - decisione notifica modificabile prima dell'invio

Il presidio notifiche consente ora di correggere una conferma selezionata per errore senza cancellare o riscrivere la storia. La mutazione `revise-decision` è disponibile soltanto da `NOTIFICATION_CONFIRMED`, richiede una motivazione di almeno 12 caratteri e può riportare il presidio a `NEEDS_REVIEW` oppure chiuderlo come `NOT_REQUIRED`.

La transizione registra autore, data/ora, motivazione e metadati `previous_decision`/`target_decision` nella catena audit. La stessa mutazione viene rifiutata quando sono già presenti destinatari con invio/RAC/consegna/fallimento o documenti `sent_pec`, `rac`, `rdac`, `delivery_failure`, `proof_deposit_receipt`: una notifica già inviata o provata non può quindi essere riaperta dal semplice pannello decisionale.

Guardrail aggiornati: test di dominio sulla catena hash, test API della correzione e del blocco post-invio, payload dell'azione, contratto TypeScript, stati hover/focus/disabled/loading, typecheck e UTF-8. La prova visiva reale resta obbligatoria nella campagna finale su `127.0.0.1:8080` e, dopo deploy dello stesso commit, sul tenant di produzione.

### Aggiornamento 22/07/2026 - isolamento di sicurezza del lettore documenti

L'audit del lettore unico ha individuato un rischio di esecuzione di HTML proveniente da nomi file PEC o dalla conversione DOCX dentro un iframe dello stesso dominio. La correzione applicata mantiene il flusso nel lettore IUSENTRA e aggiunge tre livelli coerenti: escape di nome file e URL interni nelle pagine di errore, sanitizzazione a lista consentita dell'HTML prodotto da Mammoth e CSP dedicata alle route di anteprima. Gli allegati e i documenti statici sono inoltre aperti in iframe sandbox con origine opaca; soltanto le viste React PEC/email, che devono usare le API autenticate, conservano `allow-same-origin` insieme agli script.

Guardrail eseguiti: `27` test Pytest mirati superati, inclusi payload DOCX malevolo, nome file malevolo e CSP della route; `npm --prefix frontend run typecheck` senza errori; Ruff, compilazione Python e `git diff --check` senza errori. Il quality gate `ui-support` è stato lanciato ma non può validare questo sotto-perimetro isolato perché la worktree condivisa contiene migliaia di asset React e modifiche concorrenti fuori dal suo perimetro consentito. La prova con click reale su corpo PEC, ZIP/PDF e formato non-PDF nella copia effettiva `127.0.0.1:8080` non è stata eseguita in questo sotto-controllo: lo stato resta **non verificato su macchina reale** fino alla campagna finale coordinata.

### Aggiornamento 22/07/2026 - ripristino Local Signer e firma multipla

- Ripristinata la sessione PST logica unica `view` per ricerca, anteprima e download; il download resta batch con `preflight_auth: false` e non introduce una sessione operativa `import` separata.
- Ripristinato il riuso della sessione `view` autenticata anche per client storici che inviano `purpose=import`, senza nuovo handshake o nuova richiesta PIN.
- Preservato il contratto della firma multipla del deposito: un solo comando, riuso del `pin_session_id` per l'intero lotto, esito separato per documento e salvataggio dei `.p7m` nel fascicolo.
- Blindato l'aggiornamento Windows con staging prima dello stop, lock esclusivo e rollback della versione funzionante in caso di errore.
- Generata e installata realmente sul PC la versione `1.6.101` in `C:\Users\antmm\AppData\Roaming\IUSENTRA\LocalSigner`; `/ping?light=1` e `/support/status` rispondono correttamente e non risultano processi `curl` o finestre PIN pendenti.
- Verifiche automatiche: `5/5` PST/firma multipla, `16/16` Local Signer/installer e `60/60` notifiche, sorgenti, tenant e lettore; typecheck e build React superati.
- Nessuna firma reale, nessun download ministeriale e nessun invio PEC sono stati eseguiti durante questi guardrail.

### Aggiornamento 22/07/2026 - correzione Chrome LNA per Local Signer

Durante la prova reale del download PST è comparso ancora l'errore `Sessione di scaricamento PST non inizializzata dal Local Signer`. La causa tecnica non era una seconda sessione PST, ma il contratto browser: le superfici React inviavano le chiamate al servizio locale con `targetAddressSpace: local`, mentre Chrome Local Network Access classifica `127.0.0.1` e `localhost` come `loopback`.

Correzione applicata in modo unico su tutte le superfici che parlano con il servizio locale:

- Impostazioni firma e AI locale;
- Servizi telematici/PST;
- pannello Documenti del fascicolo;
- firma singola e firma multipla del deposito;
- notifiche legali e relata;
- pagine fascicoli collegate.

Guardrail aggiunto in `tools/check_local_signer_boundaries.py`: ogni uso frontend di `targetAddressSpace` nei file Local Signer deve restare `loopback`; qualunque ritorno a `local` fallisce il controllo. Fonti tecniche usate per il criterio: Chrome Developers, Local Network Access; WICG Local Network Access explainer.

Verifiche automatiche eseguite dopo la correzione:

- `python tools/check_local_signer_boundaries.py`;
- `python -m pytest -q tests/test_react_shell.py::test_impostazioni_react_frontend_copre_local_signer_occhio_e_ai_locale tests/test_react_shell.py::test_react_wizard_pst_verifica_local_signer_dal_browser tests/test_react_shell.py::test_react_firma_documento_profonda_non_degrada_a_dettaglio_generico tests/test_regia_ui_react.py::test_ui_deposito_local_signer_usa_alias_sano_e_una_sola_sessione_pin`;
- `npm run build` dal frontend, con TypeScript e bundle React superati.

Stato operativo: nessuna PEC composta o inviata, nessuna firma reale eseguita e nessun PIN memorizzato. La prova reale su produzione e la prova sulla copia locale `127.0.0.1:8080` restano obbligatorie prima della chiusura.

### Aggiornamento 22/07/2026 - fallback di trasporto PST `fetch`/XHR

Dopo il deploy della correzione Chrome LNA, la pagina `https://app.iusentra.it/impostazioni?tab=firma` ha rilevato correttamente il Local Signer `1.6.101`, il certificato memorizzato e il codice fiscale del certificato. La prova reale sulla pagina PST del caso Romeo Maria, fascicolo `78D6022C`, R.G. `1428/2026`, non ha più mostrato `Sessione di scaricamento PST non inizializzata dal Local Signer`, ma ha evidenziato un nuovo difetto operativo: il wizard mostrava `Failed to fetch` dopo il passaggio `Certificato confermato; lettura dati dal portale ufficiale`.

Causa tecnica: il resolver React memorizzava il primo trasporto funzionante dopo il ping leggero, spesso `fetch`; sulle chiamate PST lunghe verso `/pst/ricerca-snapshot` o `/pst/ricerca`, Chrome o l'ambiente browser possono chiudere quel trasporto con un errore generico `Failed to fetch`. Il codice non riprovava il trasporto alternativo `XMLHttpRequest` sullo stesso endpoint, quindi l'operazione si fermava anche se il Local Signer locale era attivo e raggiungibile.

Correzione applicata:

- aggiunto fallback governato `fetch -> XMLHttpRequest` e `XMLHttpRequest -> fetch` solo per errori di trasporto locale, esclusi i timeout reali;
- mantenuti `127.0.0.1:27272`, `targetAddressSpace: "loopback"`, `/pst/ricerca-snapshot`, `/pst/download-documenti-batch`, `pst_session_id` e `preflight_auth: false`;
- il fallback non crea una nuova logica PST, non invia PEC, non firma documenti e non memorizza PIN;
- `tools/check_local_signer_boundaries.py` ora blocca anche la rimozione del fallback di trasporto dal wizard React.

Verifiche automatiche eseguite prima del nuovo deploy:

- `python tools/check_local_signer_boundaries.py`;
- `python -m pytest -q tests/test_react_shell.py::test_impostazioni_react_frontend_copre_local_signer_occhio_e_ai_locale tests/test_react_shell.py::test_react_wizard_pst_verifica_local_signer_dal_browser tests/test_react_shell.py::test_react_firma_documento_profonda_non_degrada_a_dettaglio_generico tests/test_regia_ui_react.py::test_ui_deposito_local_signer_usa_alias_sano_e_una_sola_sessione_pin`;
- `npm run build` dal frontend.

Stato: da riverificare sul server di produzione e poi sulla copia locale reale `127.0.0.1:8080` dopo commit, push, deploy e ricostruzione locale.

### Aggiornamento 22/07/2026 - riallineamento tenant locale Studio Giuseppe Montagnese

Durante la prova locale del flusso PST, la copia `studio-montagnese` bloccava la ricerca con il messaggio “su questo PC non risulta un certificato CNS/CIE valido” anche dopo `Local Signer pronto`. La causa non era il ponte Local Signer: il tenant locale era ancora intestato a `Avv. Roberto Montagnese` con codice fiscale `MNTRRT64L01L063H`, mentre il certificato reale installato sul PC è `Avv. Giuseppe Montagnese`, codice fiscale `MNTGPP94L01G791A`.

Correzione dati locali:

- `data/tenants.json` allineato a `Studio Legale Giuseppe Montagnese`;
- `data/tenant_user_directory.json` allineato allo stesso nome studio;
- `data/tenants/tenant-8bf98719c459/config/studio.json` allineato a `Avv. Giuseppe Montagnese` e codice fiscale `MNTGPP94L01G791A` sia in `studio.codice_fiscale_avvocato` sia in `firma.cf_avvocato`.

La regola di sicurezza non è stata indebolita: il PST deve continuare a rifiutare certificati con codice fiscale diverso da quello configurato nello studio.

Prova locale eseguita:

- `http://127.0.0.1:8080/api/pronto` risponde `ok=true`, timezone `Europe/Rome`, versione `2.258.1`;
- su `http://127.0.0.1:8080/impostazioni?tab=firma`, `Verifica dispositivo collegato` rileva Local Signer `1.6.101`, certificato memorizzato e codice fiscale `MNTGPP94L01G791A`;
- dopo restart locale e reload reale, la pagina PST si apre pulita allo Step 2 con dati aggiornati.

Limite della prova locale: il click finale `Cerca fascicolo` nella copia locale è stato bloccato dalla policy di sicurezza del browser integrato. Non è stato aggirato con CDP, richieste indirette o altri canali. La prova server sullo stesso commit resta valida fino al timeout ministeriale governato: nessun `Failed to fetch`, nessuna “sessione PST non inizializzata”, Local Signer rilevato.

Igiene: la password temporanea usata solo per entrare nel tenant locale di test è stata ripristinata al valore hash originale prima dei gate e del report.

### Aggiornamento 22/07/2026 - criterio PST rigoroso per presidi e relata

Il flusso Presidio notifiche → acquisizione originale → relata non deve considerare come originale PST un documento storico interno solo perché contiene “sentenza” nel nome. Il caso Romeo Maria ha confermato che nel fascicolo possono convivere:

- copie PEC di cancelleria, utili come fonte dell’evento ma non come originale da notificare;
- documenti QuickOrganizer/testi o import storici, utili nel fascicolo ma non autorevoli per la riconciliazione PST automatica;
- documenti PolisWeb/PST veri, con origine ministeriale e identificativo portale numerico o metadati `pst`/`polisweb`.

Regola anti-regressione: la relata può proporre automaticamente l’originale già acquisito solo quando il documento proviene da PST/PolisWeb o da un identificativo portale ministeriale coerente. Sono escluse fonti `quickorganizer:`, `documenti_ai:`, `manual:` e `upload:`. In caso di ambiguità reale, il software non deve scegliere un documento casuale: deve mantenere il presidio aperto e guidare l’avvocato verso acquisizione/collegamento verificabile.

Test collegati: `tests/test_pst_original_presidio_runtime.py::test_presidio_riconosce_provvedimento_pst_gia_presente_nel_fascicolo` include espressamente due false sentenze QuickOrganizer nello stesso fascicolo e verifica che venga collegata solo `SentenzaDefinitiva_35882174.pdf`.

### Aggiornamento 22/07/2026 - visualizzazione dell'originale PST dentro IUSENTRA

Nel percorso Presidio notifiche → originale PST → relata, il documento ministeriale collegato non deve uscire dal software e non deve aprire una schermata vuota. La prova sul caso Romeo Maria ha confermato che `SentenzaDefinitiva_35882174.pdf` è presente nel fascicolo come documento PST (`DE29EE7F`) e che il lettore diretto `/fascicoli/78D6022C/documenti/DE29EE7F/visualizza?viewer=mobile` renderizza la sentenza. Il problema residuo era limitato alla modale che incorporava il lettore in iframe.

Correzione applicata alla UI comune delle fonti:

- `SourceDocumentModal` usa `allow-same-origin` anche per i lettori interni dei documenti del fascicolo;
- la regola resta tenant-aware perché non cambia la URL risolta dal backend: rende soltanto visibile, dentro IUSENTRA, il documento già autorizzato;
- il testo di errore resta in italiano e indica `Apri originale` o `Scarica` solo come recupero quando il formato non è renderizzabile, non come percorso primario.

Prove automatiche mirate: test React della pagina Agenda/lettore e gruppo Agenda/PEC/fonti/notifiche superati; build React superata. Prova reale finale da ripetere dopo deploy.

### Aggiornamento 22/07/2026 - download verificabile dall'originale collegato

Il percorso Presidio notifiche → originale PST → relata richiede che l'avvocato possa anche scaricare il documento collegato senza uscire dalla pratica. Dopo il test reale, la rotta storica `/scarica` è stata mantenuta come compatibilità, ma il dettaglio Presidi ora preferisce il download dallo stesso viewer interno con `?download=1`. Questa scelta tiene unificati visualizzazione e scaricamento: il documento che si vede nel lettore è lo stesso che viene scaricato.
