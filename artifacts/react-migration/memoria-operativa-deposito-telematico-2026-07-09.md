# Memoria operativa deposito telematico - 09/07/2026

Questo file serve come punto di ripresa rapido per i prossimi controlli sul deposito telematico IUSENTRA. Va letto insieme a `AGENTS.md`, `artifacts/data-flow/incarico-operativo-permanente.md` e `artifacts/react-migration/procedura-deposito-telematico.md` prima di modificare ancora deposito, busta, PEC, firma, Local Signer, notifiche o catalogo generatori.

## Obiettivo utente

- Il flusso deposito deve essere veloce, intuitivo e coerente con la pagina esistente.
- Il software deve leggere l'intero fascicolo, ma non deve selezionare automaticamente tutti i documenti da inviare: la scelta finale resta dell'avvocato.
- I pulsanti `Firma e prepara prova` e `Simula invio PEC` non devono essere spenti da avvisi non obbligatori.
- `Invia deposito reale` deve restare disabilitato solo per requisiti obbligatori reali e deve mostrare il motivo preciso.
- Quando manca un dato inseribile, il software deve dire chiaramente cosa manca, permettere di inserirlo nello stesso flusso e poi continuare con la fase di invio.
- Nessun riferimento tecnico al confronto interno con il software di origine deve comparire nella UI.

## Fonti e confronto usati

- Fonti ministeriali PCT/PST: specifiche tecniche ex art. 34 DM 44/2011, provvedimento DGSIA 07/08/2024, efficaci dal 30/09/2024.
- XSD ministeriali SICI/SICID/SIECIC/SIGP disponibili in `docs/specs/ministero/xsd/2026-05-12-sici/`.
- Materiale decompilato consultato solo come fonte funzionale interna per ricostruire sequenza, classi, radici XML e campi, senza copiare codice proprietario e senza esporre riferimenti in UI.
- Log reali già registrati del deposito accettato e della simulazione produzione.

## Cosa è stato ricostruito dal confronto funzionale interno

Questa sezione indica ciò che è stato preso come comportamento, struttura e strategia operativa. Non è stato copiato codice sorgente, non sono state copiate stringhe proprietarie e nulla di questi riferimenti deve apparire nella UI.

### Sequenza deposito

- scelta del tipo deposito da catalogo;
- risoluzione di registro, ufficio, codice oggetto e canale;
- distinzione tra atto principale e allegati;
- costruzione di `DatiAtto.xml` con classe/radice coerente al tipo deposito;
- inserimento dell'indice della busta nei metadati ministeriali quando richiesto;
- firma digitale del metadato deposito;
- generazione dell'indice documenti leggibile;
- generazione di `IndiceBusta.xml`;
- costruzione di `Atto.msg` con parti fisiche coerenti con indice e `Content-ID`;
- cifratura in `Atto.enc`;
- preparazione PEC con oggetto, corpo e allegato unico;
- invio dal PC dell'avvocato e presidio delle ricevute.

### Regola documenti

- Il software può proporre e classificare, ma non deve sostituire la scelta dell'avvocato quando la classificazione non è certa.
- La busta deve usare solo i documenti collegati o selezionati nella fase `Documenti da inviare`.
- Le ricevute PEC, le comunicazioni di cancelleria e i documenti di contesto restano fuori dalla busta salvo scelta esplicita e coerente.
- L'atto principale deve essere unico.
- Gli allegati vengono ordinati e riportati nell'indice; non vanno inclusi allegati non dichiarati.

### Mappature generatori ricostruite

- `Ricorso702Bis` usa classe `IntroduttiviSicid` e radice `Ricorso702Bis`.
- Le memorie e istanze Cartabia confluiscono nel generatore comune `Parte.MemorieCartabia`.
- Le richieste di visibilità usano radici dedicate:
  - `Parte.AttoRichiestaVisibilita`;
  - `ParteSiecicEsecuzioni.AttoRichiestaVisibilita`;
  - `ParteSiecicConcorsuali.AttoRichiestaVisibilita`;
  - `CorsoCausa_SIGP.AttoRichiestaVisibilita`.
- I pignoramenti SIECIC introduttivi usano `IntroduttiviSiecicEsecuzioni.IscrizioneRuoloPignoramento`.
- Il progetto di distribuzione usa `ProfSiecicEsecuzioni.ProgettoDistribuzione`.
- Il deposito relazione iniziale usa `CurSiecicConcorsuali.DepositoRelazioneIniziale`.
- Il refuso storico del catalogo `Progett369oDistribuzione` va normalizzato in `ProgettoDistribuzione`.
- La voce storica generica `Atti del Curatore` va normalizzata in `DepositoRelazioneIniziale` quando il contesto è concorsuale curatore.

### Campi comuni di procedimento

- `AttoProcedimento` porta i dati del procedimento e l'eventuale riferimento.
- `RiferimentoProcedimento` contiene numero, anno, ufficio, ruolo e rito quando applicabile.
- `AnagraficaProcedimento` è obbligatoria nei rami introduttivi e nei rami che devono collegare parti, difensore, debitore, procedente o terzi.
- L'indice busta deve essere coerente con i file fisici realmente inseriti.

### Richiesta visibilità

- La richiesta visibilità richiede almeno parte rappresentata e avvocato.
- La parte deve avere identificativo interno e codice fiscale.
- L'avvocato deve avere codice fiscale, cognome, nome e collegamento alla parte rappresentata.
- Il collegamento parte-avvocato non deve essere inventato: se manca il dato anagrafico, il software deve bloccare con campo preciso e permettere la compilazione.
- Per SIGP cambiano namespace e forma anagrafica rispetto a SICID/SIECIC, quindi il generatore deve trattarlo separatamente.

### Pignoramenti SIECIC

- I tre casi sono:
  - pignoramento immobiliare;
  - pignoramento mobiliare presso debitore;
  - pignoramento mobiliare presso terzi.
- Campi obbligatori comuni:
  - `AnagraficaProcedimento`;
  - data consegna pignoramento;
  - importo precetto;
  - beni pignorati;
  - estensione anagrafica;
  - estensione dati rito;
  - titolo quando richiesto dal caso concreto.
- Per bene mobile servono tipologia, descrizione e valore.
- Per bene immobile/tavolare servono descrizione, indirizzo, catasto, dati catastali o denuncia, classe e diritti reali.
- Per presso debitore serve il custode con dati identificativi e indirizzo.
- Per presso terzi serve il terzo pignorato con codice fiscale e data notifica pignoramento.
- I dati procedente/debitore/avvocato devono arrivare da anagrafica fascicolo o da inserimento guidato, non da default inventati.

### Progetto distribuzione

- Il progetto di distribuzione usa il ramo professionista esecuzioni.
- La struttura contiene il procedimento e un blocco deposito.
- Nel comportamento ricostruito il contenuto operativo del deposito è sintetico e non richiede dettagli riparto quando non presenti.
- Se in futuro l'avvocato inserisce dettagli riparto strutturati, questi devono essere modellati e validati prima dell'invio reale.

### Deposito relazione iniziale curatore

- Il ramo curatore concorsuale richiede radice dedicata.
- La struttura minima ricostruita è basata su procedimento e dati fascicolo.
- I blocchi opzionali non devono essere inventati se non sono presenti.
- Se il caso concreto richiede scelta o dettaglio aggiuntivo, il software deve chiederlo in modo esplicito.

### Strategie UI ricavate dal confronto

- Il flusso deve procedere per passaggi brevi.
- Il blocco deve essere raro e puntuale.
- Avvisi non obbligatori non devono spegnere prova e simulazione.
- L'avvocato deve poter correggere subito documento, ruolo, dato anagrafico o dato del deposito senza cambiare pagina.
- La UI deve parlare solo in termini operativi IUSENTRA: documento, dato mancante, prova, busta, PEC, firma, ricevute.

## Cosa viene dalle fonti ministeriali e dagli XSD

### Fonti ufficiali consultate

- PST Giustizia, scheda `Specifiche Tecniche ex art. 34 DM 44/2011 - Provvedimento 7 agosto 2024`: `https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC3429`.
- PDF del provvedimento tecnico 07/08/2024: `https://pst.giustizia.it/PST/resources/cms/documents/m_dg.DOG07.07082024.0004292.ID_SPECIFICHETECNICHE_DM_44_2011_FINALE_31_.pdf`.
- PST Giustizia, comunicazione software house del 12/05/2026 su aggiornamento XSD SICI/SICID: `https://pst.giustizia.it/PST/page/it/processo_civile_telematico__comunicazione_alle_software_house_aggiornamento_specifiche_tecniche_deposito_atti_sicid_it_1?contentId=NWS4877`.
- XSD locali importati in repository: `docs/specs/ministero/xsd/2026-05-12-sici/XSD_SICI_20260508/XSD_SICI_20260508/`.

### Regole ministeriali applicate al trasporto

- `DatiAtto.xml` deve avere radice e namespace coerenti con tipo deposito, registro e ruolo.
- `DatiAtto.xml` deve essere firmato quando entra nella busta ministeriale.
- `IndiceBusta.xml` deve corrispondere ai file fisici inseriti nella busta.
- `Atto.msg` deve contenere i componenti previsti e coerenti tra nome, identificativo e contenuto.
- `Atto.enc` non è un file qualunque: deve essere busta cifrata ministeriale riconoscibile.
- Il certificato pubblico `.cer` PST dell'ufficio è requisito quando il canale richiede cifratura `Atto.enc`.
- Le PEC operative di deposito devono partire dal PC dell'avvocato tramite canale locale, non dal server applicativo.

### Namespace e radici ministeriali usati

- SICID parte v7: `http://schemi.processotelematico.giustizia.it/sicid/parte/v7`.
- SIECIC esecuzioni parte v8: `http://schemi.processotelematico.giustizia.it/siecic/esecuzioni/parte/v8`.
- SIECIC concorsuali parte v8: `http://schemi.processotelematico.giustizia.it/siecic/concorsuali/parte/v8`.
- SIGP corso causa v3: `http://schemi.processotelematico.giustizia.it/sigp/cartabia/corsocausa/v3`.
- SIECIC esecuzioni introduttivi v8: `http://schemi.processotelematico.giustizia.it/siecic/esecuzioni/introduttivi/v8`.
- SIECIC esecuzioni professionista v6: `http://schemi.processotelematico.giustizia.it/siecic/esecuzioni/professionista/v6`.
- SIECIC concorsuali curatore v11: `http://schemi.processotelematico.giustizia.it/siecic/concorsuali/curatore/v11`.
- Tipi atti v7: `http://schemi.processotelematico.giustizia.it/tipi/atti/v7`.
- Tipi anagrafiche v4: `http://schemi.processotelematico.giustizia.it/tipi/anagrafiche/v4`.
- SIGP tipi anagrafiche v2: `http://schemi.processotelematico.giustizia.it/sigp/tipi/anagrafiche/v2`.

### Campi ministeriali verificati negli XSD

- Richieste visibilità:
  - sequenza con parte e avvocato;
  - attributo identificativo parte;
  - codice fiscale parte;
  - codice fiscale avvocato;
  - collegamento avvocato-parte rappresentata.
- Pignoramenti:
  - `AnagraficaProcedimento`;
  - `DataConsegnaPignoramento`;
  - `ImportoPrecetto`;
  - `Beni`;
  - `EstensioneAnagrafica`;
  - `EstensioneDatiRito`;
  - dati debitore;
  - dati procedente;
  - dati avvocato;
  - dati custode per presso debitore;
  - dati terzo per presso terzi;
  - bene mobile con tipologia, descrizione e valore;
  - bene immobile con indirizzo, catasto, dati catastali e classe;
  - titolo/debitore quando il titolo è valorizzato.
- Progetto distribuzione:
  - blocco `deposito`;
  - scelta tra piano riparto o piano riparto parziale;
  - dettagli riparto opzionali.
- Relazione iniziale curatore:
  - radice dedicata;
  - estensione da atto procedimento;
  - elementi successivi opzionali secondo XSD.

### Conseguenza sul nostro software

- Un tipo deposito può essere dichiarato generabile solo se il nostro codice produce XML con radice, namespace e struttura coerenti.
- Un dato non modellato non può essere sostituito con testo generico o valori finti.
- Se il dato è obbligatorio, la UI deve farlo inserire.
- Se il dato è opzionale, la UI può mostrarlo come avviso o campo facoltativo.
- Il catalogo deve distinguere sempre:
  - tipo non PCT;
  - tipo PCT generabile;
  - tipo PCT generabile ma in attesa di dato obbligatorio;
  - tipo PCT non inviabile per mancanza tecnica reale.

## Stato verificato prima di questa memoria

- Caso produzione `FB586324`, pagina `https://app.iusentra.it/fascicoli/FB586324/deposito/prepara#generazione-busta`.
- Vecchio blocco generico `1 scelte obbligatorie richiedono la selezione dell'avvocato` rimosso dal flusso verificato.
- `Firma e prepara prova` abilitato quando atto principale e PEC ufficio sono presenti.
- `Simula invio PEC` abilitato e testato con click reale sicuro: si ferma su `Local Signer non rilevato`, senza invio esterno.
- `Invia deposito reale` disabilitato con motivo puntuale: `Esegui prima la prova senza invio reale`.
- Il comando `Invia tutto` è stato rimosso; restano `Ripristina documenti collegati`, `Deseleziona tutto`, `Salva classificazione`.
- Gli slot documentali mancanti sono avvisi non bloccanti per la prova se l'avvocato ha già selezionato atto principale e documenti.

## Modifiche codice già presenti

- `frontend/src/components/FascicoloDepositoPage.tsx`
  - Selezione documenti guidata dall'avvocato.
  - Payload busta basato su `documenti_selezionati_ids`.
  - Atto principale normalizzato e unico.
  - Prova e simulazione non bloccate da slot catalogo non essenziali.
  - Messaggi di blocco già più puntuali rispetto alla frase generica iniziale.

- `frontend/src/components/FascicoliPage.tsx`
  - Deposito caricato con lazy chunk dedicato.
  - Comportamento elenco/dettaglio fascicoli alleggerito.

- `pct/deposito_telematico_catalogo.py`
  - Catalogo deposito esteso con rami recuperati: `Ricorso702Bis`, memorie/istanze Cartabia, richieste visibilità, pignoramenti SIECIC, progetto distribuzione, relazione iniziale curatore.
  - Refuso storico `Progett369oDistribuzione` normalizzato in `ProgettoDistribuzione`.
  - Voce storica `Atti del Curatore` normalizzata in `Curatore_CONCORSUALI_SIECIC::DepositoRelazioneIniziale`.

- `pct/busta.py`
  - Aggiunto `datiatto_extra` in `DatiBusta`.
  - Avviata generazione ministeriale dedicata per richieste visibilità, progetto distribuzione, pignoramenti e relazione iniziale curatore.
  - Aggiunte funzioni per leggere dati extra, normalizzare date/importi e costruire parti XML specialistiche.

- `scripts/audit_deposito_catalogo_end_to_end.py`
  - Audit end-to-end catalogo/generatori.
  - Scopo: fallire se un tipo deposito non ha mappatura, sorgente, regole, generatori o stato invio coerente.

- Versione preparata: `2.254.19` in `pct/__init__.py`, `Dockerfile`, `railway.toml`, `docs/openapi.yaml`.

## Risultati audit già registrati

- Tipi totali controllati: `270`.
- Tipi PCT: `252`.
- Tipi UNEP/notifiche: `18`.
- Primo audit esteso: `243/252` PCT generavano `DatiAtto.xml`; `9` erano riconosciuti ma sospesi perché richiedevano generatori/dati dedicati.
- L'utente ha chiesto espressamente di non lasciare sospesi quei 9 rami e di completare i generatori.

## Nove rami da chiudere al 100%

- `Parte_SICID::AttoRichiestaVisibilità`
- `Parte_ESECUZIONI_SIECIC::AttoRichiestaVisibilità`
- `Parte_CONCORSUALI_SIECIC::AttoRichiestaVisibilità`
- `CorsoCausa_SIGP::AttoRichiestaVisibilità`
- `Introduttivi_ESECUZIONI_SIECIC::IscrizioneRuoloPignoramentoImmobiliare`
- `Introduttivi_ESECUZIONI_SIECIC::IscrizioneRuoloPignoramentoMobiliarePressoDebitore`
- `Introduttivi_ESECUZIONI_SIECIC::IscrizioneRuoloPignoramentoMobiliarePressoTerzi`
- `Professionista_ESECUZIONI_SIECIC::ProgettoDistribuzione`
- `Curatore_CONCORSUALI_SIECIC::DepositoRelazioneIniziale`

## Stato tecnico in lavorazione

- In `pct/busta.py` i generatori specializzati sono stati impostati, ma devono ancora essere completati e validati con audit/test.
- Da correggere ancora:
  - namespace anagrafiche SIGP nelle richieste visibilità;
  - anagrafica ministeriale v7 per classi SIECIC e radici `Parte` v7;
  - passaggio `datiatto_extra` dalle route deposito a `DatiBusta`;
  - campi rapidi UI/backend per dati non deducibili dal fascicolo;
  - test dedicati per visibilità, progetto distribuzione, relazione iniziale curatore e pignoramenti.
- Non dichiarare ancora `252/252` finché `python scripts/audit_deposito_catalogo_end_to_end.py` non passa con `0` sospesi e i test mirati non sono verdi.

Nota di aggiornamento 09/07/2026: lo stato `243/252` e `9 sospesi` sopra è superato dal controllo severo successivo. Non usarlo più come stato operativo corrente.

## Stato tecnico aggiornato 09/07/2026

- `pct/busta.py` genera i rami specializzati per richiesta visibilità, pignoramenti SIECIC, progetto distribuzione e relazione iniziale curatore.
- `web/services/deposito_catalogo_runtime.py` estrae `datiatto_extra` da JSON o campi singoli e lo porta alle route deposito.
- `web/bootstrap/deposito_routes.py` passa `datiatto_extra` a `DatiBusta` sia nella generazione busta sia nella prova/invio PEC.
- `scripts/audit_deposito_catalogo_end_to_end.py` è severo: controlla `270/270` tipi, `252/252` PCT, `0` sospesi, campi XML interni, indice documenti, indice busta, Local Signer, recupero certificato ufficio e PEC locale dal PC dell'avvocato.
- Report salvato: `artifacts/react-migration/audit-deposito-catalogo-end-to-end-2026-07-09.json`.

## Controllo certificato ufficio, PEC e codice ufficio 09/07/2026

- Dal confronto funzionale interno emerge che il software di riferimento usa il codice ufficio e recupera il certificato pubblico quando deve cifrare la busta, invece di dipendere solo da un elenco statico completo.
- IUSENTRA mantiene la stessa strategia operativa governata: profilo deposito e catalogo uffici vengono fusi; se il profilo ha solo la PEC, il resolver completa codice interno e codice ministeriale dal catalogo prima di consegnare il dato al flusso React.
- Il controllo aggiornato confronta il catalogo IUSENTRA con `C:\QuickOrganizer\ListaUfficiGiudiziari.xml`, `C:\QuickOrganizer\QC_Uffici.xml` e le fonti PST/ministeriali importate.
- Esito audit codici/PEC: `593` uffici PCT operativi controllati, `0` codici mancanti, `0` PEC mancanti, `0` differenze PEC rispetto alla fonte Studio/PST, `0` errori del resolver React.
- Se la PEC non viene risolta, la UI blocca con `IUSENTRA non ha risolto automaticamente la PEC dell'ufficio: aggiorna il catalogo uffici o verifica l'ufficio giudiziario della pratica.`.
- Se il codice ufficio non viene risolto per un canale che richiede il certificato, la UI blocca con `IUSENTRA non ha risolto automaticamente il codice dell'ufficio: aggiorna il catalogo uffici o verifica l'ufficio giudiziario della pratica.`.
- Questi blocchi non sono richieste manuali all'avvocato: indicano una mancata risoluzione automatica del software/catalogo e vanno corretti come difetto operativo.
- Se il certificato non è ancora disponibile, la prova indica il requisito puntuale; non deve tornare il messaggio generico `PEC dell'ufficio non verificata`.

## Esito audit severo 09/07/2026

- `python scripts/audit_deposito_catalogo_end_to_end.py --output artifacts/react-migration/audit-deposito-catalogo-end-to-end-2026-07-09.json` -> `ok=true`.
- Tipi totali: `270`.
- PCT: `252`.
- UNEP/notifiche: `18`.
- `DatiAtto.xml` generati: `252/252`.
- Rami sospesi: `0`.
- Uffici PCT operativi con PEC/codice verificati contro fonte Studio/PST: `593/593`.
- Errori: `0`.
- Test collegati: `python -m pytest tests/test_deposito_telematico_catalogo.py -q` -> `9 passed`.
- Test UI deposito mirati: `python -m pytest tests/test_regia_ui_react.py::test_ui_deposito_prova_guidata_non_salta_firma_e_mostra_audit_pec_indice tests/test_regia_ui_react.py::test_ui_deposito_avvisi_classificazione_non_spengono_prova_e_non_autoselezionano_tutto -q` -> `2 passed`.
- Test busta/certificati/Local Signer: `python -m pytest tests/test_busta.py tests/test_canali_telematici_deposito.py tests/test_local_signer.py::test_catalogo_servizi_get_certificato_parser_estrae_base64 tests/test_local_signer.py::test_local_signer_espone_endpoint_certificato_ufficio_pst -q` -> `50 passed`.
- Typecheck frontend: `npm --prefix frontend run typecheck` -> OK.

## Correzione prova reale Giudice di Pace / SIGP 09/07/2026

- Difetto reale visto nel browser su `http://127.0.0.1:8080/fascicoli/DC5BF1DB/deposito/prepara#generazione-busta`: il click su `Simula invio PEC` partiva con la prima voce del catalogo (`SICID`) e produceva `Registro non compatibile con il procedimento`.
- Correzione React: `DepositTypePreviewPanel` non seleziona più automaticamente la prima voce del catalogo. Il suggeritore usa ufficio, canale, profilo e atto principale; sul caso `Giudice di Pace - Palmi` con `Note trattazione scritta...pdf.p7m` seleziona `Deposito note scritte sostitutive udienza (Giudice di Pace)` / `CorsoCausa_SIGP::DepositoNoteScritteSostUdie`.
- Correzione backend: il validatore distingue registro di ruolo e canale tecnico; `SIGP` è compatibile con ufficio Giudice di Pace e profili `RG/RGL/VG`, mentre `SICID` resta bloccato su ufficio Giudice di Pace.
- Test aggiunti: `test_orchestratore_accetta_sigp_su_giudice_di_pace`, `test_orchestratore_blocca_sicid_su_giudice_di_pace`, `test_orchestratore_accetta_sicid_su_tribunale_ordinario`, `test_ui_deposito_tipo_deposito_non_prende_la_prima_voce_e_suggerisce_sigp_note`.
- Prova reale locale dopo rebuild Docker `2.254.19`: pagina aggiornata con `Giudice di Pace (28)`, `Atti endo-processuali (11)`, `Deposito note scritte sostitutive udienza (Giudice di Pace)`, PEC `gdp.palmi@civile.ptel.giustiziacert.it`, codice ufficio risolto, `Scelte obbligatorie collegate`, `Simula invio PEC` e `Prova senza invio reale` abilitati.
- Click reale su `Simula invio PEC` e click reale su `Prova senza invio reale`: il blocco `Registro non compatibile` non compare più. Entrambi i flussi si fermano solo sul requisito materiale `Dispositivo non pronto per firmare i dati del deposito: Nessun dispositivo di firma rilevato`, messaggio coerente con l'assenza di smart card/token/middleware pronto sulla macchina.
- Stato `Invia deposito reale`: resta disabilitato con motivo `Esegui prima la prova senza invio reale` perché la prova non può superare la firma dei dati deposito senza dispositivo di firma reale. Non dichiarare invio reale pronto finché non viene eseguita una prova con dispositivo di firma disponibile e `Atto.enc` verificato.

## Regola UX da preservare

Ogni blocco deve avere questa forma operativa:

1. dire cosa manca con nome campo/documento concreto;
2. spiegare perché è obbligatorio;
3. offrire nello stesso pannello il modo di inserirlo o collegarlo;
4. salvare tramite API reale;
5. ricaricare stato e consentire di riprendere prova/simulazione/invio senza ricominciare.

Esempi di messaggi vietati:

- `1 scelte obbligatorie richiedono la selezione dell'avvocato`;
- `Controlla i dati`;
- `Completa la fase`;
- blocchi senza nome del campo/documento.

Esempi di messaggi corretti:

- `Manca l'atto principale: scegli il documento nella lista Documenti da inviare.`;
- `Manca il custode del pignoramento presso debitore: inserisci codice fiscale, cognome, nome e indirizzo.`;
- `Manca il terzo pignorato: inserisci codice fiscale e data notifica pignoramento.`;
- `IUSENTRA non ha risolto automaticamente la PEC dell'ufficio: aggiorna il catalogo uffici o verifica l'ufficio giudiziario della pratica.`;
- `IUSENTRA non ha risolto automaticamente il codice dell'ufficio: aggiorna il catalogo uffici o verifica l'ufficio giudiziario della pratica.`;

## Prove da ripetere prima della chiusura

- `python -m py_compile pct/busta.py pct/deposito_telematico_catalogo.py scripts/audit_deposito_catalogo_end_to_end.py web/services/deposito_anagrafica_ministeriale.py`
- `python scripts/audit_deposito_catalogo_end_to_end.py`
- `python -m pytest tests/test_busta.py tests/test_deposito_telematico_catalogo.py tests/test_regia_ui_react.py -q`
- build frontend se viene toccata la UI: `npm --prefix frontend run typecheck` e `npm --prefix frontend run build`
- prova visiva reale su `127.0.0.1:8080` per:
  - documenti da inviare;
  - pannello dati deposito mancanti;
  - click `Firma e prepara prova`;
  - click `Simula invio PEC`;
  - stato disabilitato/abilitato `Invia deposito reale`;
  - scroll completo desktop/tablet/mobile.
- dopo commit/push: deploy Hetzner, container unico `iusentra-app`, `/api/pronto` produzione e controlli CI/CodeQL sullo SHA corrente.

## Limite da dichiarare sempre correttamente

Un audit generatori `252/252` dimostra copertura del catalogo e generazione `DatiAtto.xml` sul perimetro testato. Non equivale da solo ad accettazione ministeriale di ogni deposito reale: per confermare un deposito specifico servono prova senza invio, firma reale, `Atto.msg`, `Atto.enc`, PEC locale, ricevute e riscontro dell'ufficio sul caso concreto.
