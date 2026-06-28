# Incarico operativo permanente: dati, tenant, React e topbar

Ultimo aggiornamento: 2026-06-17.

Questo file va riletto dopo ogni compattazione insieme ad `AGENTS.md` prima di riprendere lavori su IUSENTRA. L'incarico dell'utente non riguarda un singolo pulsante: riguarda la chiusura dell'applicativo come sistema unico, con dati coerenti, route full React, tenant corretto e controlli reali.

## Incarico permanente deposito telematico e relata

Questa parte non va più ricostruita dalla chat. Dopo ogni compattazione, quando si riprende deposito, PEC, firma digitale, Local Signer, certificati PST, scheduler, relata o prova notifica, l'obiettivo operativo è uno solo: chiudere il flusso reale, verificabile documento per documento, senza regressioni e senza dichiarare verde ciò che non è stato visto sulla macchina reale o sul server reale richiesto.

Regola di metodo:

1. per difetti visibili si corregge prima il comportamento nella vista reale indicata dall'utente;
2. solo dopo una prova reale positiva si consolidano test, documentazione, commit, push, deploy e igiene;
3. se il problema nasce su produzione, si verifica prima su `https://app.iusentra.it`, poi si riporta lo stesso codice in locale;
4. alla fine server, locale e GitHub devono puntare allo stesso commit, con Docker locale healthy su `127.0.0.1:8080` e Hetzner healthy su `https://app.iusentra.it/api/pronto`.

Il deposito deve funzionare in tutti i percorsi di nascita della pratica:

1. preventivo accettato, conferimento incarico, fascicolo;
2. nuovo fascicolo diretto;
3. fascicolo veloce o autonomo.

In tutti e tre i casi il software deve costruire e salvare in SQL il `profilo_deposito` con canale riconosciuto, regole canale, codice deposito/codice oggetto, ufficio giudiziario, PEC verificata, certificato `.cer` quando richiesto dal PCT/SIGP/Cassazione e motivi puntuali se qualcosa manca. Il dato non deve restare solo nel JSON: le colonne dedicate `profilo_deposito_json` di `preventivi_records`, `conferimenti_records` e `fascicoli` sono parte del contratto, con parità SQLite/PostgreSQL.

Per la firma digitale vale una regola assoluta: la UI può mostrare `Firmato` solo se esiste una prova tecnica reale. Per CAdES il file normalmente diventa `.pdf.p7m` o comunque contenitore PKCS#7 verificabile; per PAdES il PDF può restare `.pdf`, ma deve contenere una firma interna verificabile. Il software non deve mai scrivere `Firmato digitale` perché trova la parola "Firmato" nel testo, nel nome del file o in un flag storico.

`Invia deposito reale` deve restare disabilitato solo per un requisito obbligatorio effettivamente mancante. Se prova senza invio, firme salvate, indice visualizzabile, PEC destinatario verificata, corpo PEC controllato, busta/trasporto conforme, certificato `.cer` richiesto presente, `Atto.enc` richiesto generato e PEC mittente/SMTP disponibili risultano tutti corretti, il bottone deve attivarsi. Se resta disabilitato, la UI deve indicare esattamente il requisito bloccante; se non lo indica, è una regressione.

Regola permanente invio PEC: per depositi, notifiche legali e verifiche operative PEC il server non è mai il canale SMTP reale. Il comportamento corretto è quello dichiarato in `/impostazioni?tab=pec`, sezione `Verifiche PEC`: `Il controllo dell'invio parte dal PC in uso: la password resta sul dispositivo locale.` Quindi anche quando IUSENTRA gira su `https://app.iusentra.it`, il server prepara e verifica busta, destinatario, oggetto, corpo PEC, allegato `Atto.enc` e ricevute, ma l'invio effettivo parte dal PC dell'avvocato tramite Local Signer/servizio locale. Qualunque variabile, rotta legacy o scorciatoia che abiliti SMTP server-side per un invio legale è da trattare come regressione.

Regola permanente di velocità operativa: quando manca un dato configurabile che blocca un flusso sensibile, come PEC SdI, PEC mittente, email commercialista, firma o canale Local Signer, la UI deve offrire nello stesso pannello un'azione rapida per inserire i campi essenziali, salvarli tramite le API reali di Impostazioni e riprendere il flusso senza cambiare pagina o perdere contesto. Le impostazioni complete possono restare raggiungibili, ma il blocco non deve obbligare l'avvocato a ricostruire manualmente il percorso.

Regola permanente date/orari visibili: tutto ciò che l'avvocato vede deve usare data italiana e ora `Europe/Rome`. Timestamp UTC, stringhe ISO raw e label come `Data UTC` possono restare solo nei payload tecnici o nei sorgenti originali, non in UI, PDF, PEC/email in arrivo, email ordinaria, ricevute, esiti SdI/PCT, audit visibili, pannelli amministrativi o report. Per PEC/email la data di arrivo, invio, consegna e ricevuta deve essere mostrata sempre come ora italiana, mantenendo il valore tecnico originale solo nei metadati o header non trasformati.

Regola permanente `Atto.enc`: nome file, estensione, dimensione o base64 valido non bastano mai per abilitare l'invio reale. Prima della password PEC locale il software deve verificare che l'allegato `Atto.enc` sia un CMS/PKCS#7 `EnvelopedData` ministeriale riconoscibile, generato da `Atto.msg` contenente `IndiceBusta.xml`, `DatiAtto.xml.p7m` firmato CAdES e `IndiceDocumentiDepositati.PDF`. Il report deve mostrare algoritmo CMS effettivo e presenza dell'indice ministeriale; se il payload non è CMS, se `IndiceBusta.xml` manca o se `DatiAtto.xml.p7m` non incapsula il metadato della stessa busta, il flusso blocca prima della password PEC e non registra il deposito come valido.

La prova reale del deposito deve coprire almeno:

- apertura React, senza fallback legacy e senza HTML grezzo visibile;
- fascicolo reale indicato dall'utente quando presente, in particolare `E5AE4668` su server e `DC5BF1DB` in locale finché restano i casi di prova;
- codice deposito/codice oggetto, ufficio, PEC e certificato;
- lista documenti, ruoli, selezione `Da firmare` solo quando serve e firma multipla con PIN digitato al momento, senza salvare il PIN;
- `DatiAtto.xml`, `IndiceDocumentiDepositati.PDF` davvero visualizzabile, corpo PEC visibile e modificabile facoltativamente;
- simulazione PEC e prova senza invio reale, con barra avanzamento e nome del documento in lavorazione;
- click o dry-run controllato di `Invia deposito reale` senza sorprese sulle rotte, sul destinatario PEC, sul mittente, sull'SMTP usato dal software e sul presidio ricevute;
- scroll completo e controllo desktop/tablet/mobile quando la UI cambia.

Stato da non dimenticare: al 2026-06-17 la cache certificati PST locale risulta coperta sul perimetro operativo corrente (`593/593` codici ministeriali che richiedono `.cer/Atto.enc`; `913` `.cer` fisici DER validi; `0` invalidi). Quindi Palmi e Vicenza non devono più essere trattati come mancanze globali se la cache corrente è presente. Un blocco residuo deve riferirsi al singolo requisito reale mancante, per esempio `Atto.enc`, PEC mittente, firma obbligatoria, destinatario non verificato o canale non abilitato.

Stato aggiornato: il difetto dell'area PDF bianca su `IndiceDocumentiDepositati.PDF` è stato corretto riallineando la locale al comportamento già funzionante sul server, cioè anteprima con URL diretto e viewer PDF del browser. Prova reale locale eseguita su `http://127.0.0.1:8080/fascicoli/DC5BF1DB/deposito/prepara#generazione-busta`: il modal mostra titolo, toolbar PDF, miniatura, pagina `1/1` e contenuto `Indice documenti depositati`. Screenshot fuori repository: `C:\Users\antmm\AppData\Local\Temp\iusentra-dc5bf1db-indice-pdf-diretto-225356.png`.

La relata/prova notifica è un flusso collegato ma distinto dal deposito. Si chiude solo dopo testo reale visualizzato, dati obbligatori verificati, fonti normative ufficiali confrontate, firma della relata quando richiesta, prova senza invio reale, documenti collegati nel fascicolo e nessun click che apra per errore la guida firma al posto della funzione operativa.

## Obiettivo

Portare e mantenere tutto il perimetro operativo lato studio/prodotto in React reale, senza fallback mascherati a `?_legacy=1`, senza dati sparsi tra JSON, SQLite e PostgreSQL, senza topbar solo grafica e senza dichiarare verde un flusso non verificato sulla macchina reale.

## Regola principale

Ogni nuova funzione o modifica deve dichiarare e verificare:

1. dove nasce o viene inserito il dato;
2. quale tenant lo possiede;
3. quale path tenant-aware lo conserva;
4. quale JSON storico o sorgente di compatibilità lo alimenta, se esiste;
5. quale tabella SQLite lo indicizza nel `studio.db`;
6. quale tabella PostgreSQL o repository dedicato lo copre in produzione;
7. quale API JSON lo espone alla UI;
8. quale route e componente React lo mostrano;
9. quale voce di menu, sottomenu o alias visibile lo apre;
10. quali test automatici e quali prove reali sono state eseguite.

Se manca uno di questi passaggi, il lavoro resta aperto.

## Perimetro da presidiare

Le aree da controllare come unico sistema sono:

- Panoramica;
- Regia Operativa;
- Ricerca Studio;
- Agenda;
- Fascicoli;
- Clienti e Anagrafiche;
- Soggetti e Parti;
- Comunicazioni;
- Scadenze e Termini;
- Servizi Telematici;
- Studio;
- Sito Studio;
- Impostazioni;
- Amministrazione;
- topbar operativa.

La topbar deve restare collegata a dati reali per `Voce Studio`, `Assistenza remota`, data italiana, `Nuovo`, notifiche operative, ultimi elementi aperti, scadenze rapide e timer attività. Non basta mostrare icone: i collegamenti API e tenant devono esistere.

## Sottomenu e alias da controllare

Il controllo non si ferma alla voce principale della sidebar. Ogni sezione deve avere anche le sue voci interne, i badge/alias visibili e la struttura dati corrispondente. Esempi obbligatori:

- Agenda: `Calendario`, `Nuovo Appuntamento`, `Timesheet`;
- Fascicoli: `Tutti i Fascicoli`, `Nuovo Fascicolo`, `Archivio`;
- Clienti e Anagrafiche: `Anagrafica`, `Nuovo Cliente`, `Cartelle Condivise`, `Portale Clienti`;
- Soggetti e Parti: `Anagrafica`, `Nuovo Soggetto`;
- Comunicazioni: `Email PEC`, alias `PEC`, `Notifiche legali`, alias `L.53`, `Email ordinaria`, alias `SMTP`, `Messaggi`, `Nuovo SMS/WA`;
- Scadenze e Termini: `Scadenziario`, `Nuova Scadenza`, `Preparazione Udienza Guidata`, `Controlli Atti`;
- Servizi Telematici: `Centro Servizi Telematici`, `PolisWeb / PST`, `PDP Penale`, `PAT Amministrativo`, `PTT Tributario`, `Tribunali / PEC`, `Checklist deposito`, `Guida firma digitale`;
- Studio: `Studio`, `Parcelle e Fatture`, `Preventivi e Incarichi`, `Compensi Forensi`, `Documenti`, `Editor professionale`, `Redazione Atti`, `Statistiche`, `Ricerca Legale`, `Legal Skills`, `Regia Agentica`, `Archivio Giurisprudenza`, `Strumenti Forensi`, `Strumenti Operativi`;
- Sito Studio: `Sito Studio`, `Builder Sito`, `Redazione AI Sito`, `Contatti Sito`;
- Impostazioni: `Impostazioni Studio`, `Notifiche`, `Pagamenti`, `Canali SdI`, `Backup`, `Sincronizzazione Calendari`;
- Amministrazione: `Amministrazione`, `Utenti`, `Profili e Permessi`, `Registro Attività`, `Importa pratiche da Studio Telematico`, `Database`, `Registro GDPR`.

Ogni voce o alias deve avere route React governata, API reale quando necessaria, tenant path, JSON storico se esiste, tabella SQLite o repository verticale, parità PostgreSQL dove il dominio è persistente, test e prova reale. Se una voce viene aggiunta in UI senza contratto dati, il lavoro è incompleto.

## Route React

Le route operative richieste devono essere full React nel manifest e nella shell. La presenza di una pagina visibile non basta se il flusso cade su Jinja, su `?_legacy=1` o su un bridge senza dati reali.

Route sensibili da non dimenticare:

- `/`;
- `/workspace-intelligente`;
- `/global-search`;
- `/agenda`;
- `/agenda/nuovo`;
- `/timesheet`;
- `/fascicoli`;
- `/fascicoli/nuovo`;
- `/fascicoli/archivio`;
- `/fascicoli/:id/deposito/prepara`;
- `/clienti`;
- `/clienti/nuovo`;
- `/cartelle-condivise`;
- `/app/portale-clienti`;
- `/soggetti`;
- `/soggetti/nuovo`;
- `/email`;
- `/email-ordinaria`;
- `/messaggi`;
- `/messaggi/nuovo`;
- `/notifiche-legali`;
- `/scadenziario`;
- `/scadenziario/nuova`;
- `/telematico`;
- `/servizi-telematici`;
- `/polisWeb`;
- `/pdp`;
- `/pat`;
- `/sigit`;
- `/tribunali`;
- `/deposito/checklist`;
- `/guida/firma-digitale`;
- `/studio`;
- `/fatturazione`;
- `/preventivi`;
- `/compensi-forensi`;
- `/documenti`;
- `/editor-professionale`;
- `/redazione-atti`;
- `/statistiche`;
- `/ricerca-legale`;
- `/legal-skills`;
- `/workflow-agents`;
- `/giurisprudenza`;
- `/strumenti-legali`;
- `/strumenti-operativi`;
- `/sito-studio`;
- `/sito-studio/builder`;
- `/sito-studio/redazione-ai`;
- `/sito-studio/contatti`;
- `/impostazioni`;
- `/impostazioni/sdi`;
- `/impostazioni/calendario`;
- `/backup`;
- `/amministrazione`;
- `/utenti`;
- `/profili`;
- `/registro-attivita`;
- `/audit`;
- `/registro-gdpr`;
- `/privacy/registro`;
- `/importa-pratiche-studio-telematico`;
- `/admin/database`.

Nota: `/database` è solo alias storico e non deve essere usato come prova di React pieno; la pagina operativa governata è `/admin/database`.

## JSON, SQLite, PostgreSQL e tenant

Regola permanente da seguire per ogni lavoro successivo: negli studi in modalita SQL la fonte di verita e sempre `studio.db` o PostgreSQL. I JSON tenant-aware possono esistere solo come mirror rigenerabile, bootstrap controllato, import/export storico, cache o archivio. Se un JSON operativo esiste sotto il tenant, deve essere censito da `scripts/audit_tenant_data_structure.py`, avere un modulo SQL in `moduli_dati` e avere i record normalizzati in `moduli_json_records`, oppure deve appartenere a un repository verticale SQLite/PostgreSQL dedicato. Se lo script trova un JSON operativo non censito, il lavoro non si chiude: si crea subito il presidio SQL/mirror, si popola e si riesegue audit a freddo.

Le famiglie JSON dinamiche sono presidiate con moduli stabili derivati dal path:

- `fascicoli/documenti_ai/**/*.json` diventa mirror SQL `documenti_ai_file_*`;
- `fascicoli/importazioni/**/*.json` diventa mirror SQL `fascicoli_importazione_*`;
- `intelligence/lex_dataset/**/*.json` diventa mirror SQL `lex_dataset_*`.

Le famiglie note come repository o configurazioni operative sono censite esplicitamente: `studio_local_pack`, `editor_ai`, `pec_cancelleria_state`, repository `intelligence`, `giurisprudenza`, `legal_*`, `telematico_*`, `template_repository`, repository `preventivi` e `termini_processuali`. Cache, backup, file corrotti preservati e archivi restano ammessi solo se classificati come non operativi.

I JSON non devono restare l'unica fonte operativa quando il flusso è strutturato. Vanno indicizzati nel tenant `studio.db` tramite `moduli_dati` e `moduli_json_records`; i domini core devono avere anche tabella verticale SQLite e parità PostgreSQL.

Il controllo permanente vive in:

- `pct/data_flow_contract.py`;
- `scripts/audit_data_flow_contract.py`;
- `tests/test_data_flow_contract.py`.

Aggiornamento 2026-06-17 per deposito/preventivo/conferimento/fascicolo:

- i dati di profilo deposito devono essere persistiti in SQL con colonna dedicata `profilo_deposito_json`, non solo nel blob `dati_json`;
- le tabelle presidiate sono `preventivi_records`, `conferimenti_records` e `fascicoli`, con parità SQLite/PostgreSQL;
- `StudioDB.ensure_schema()` deve riallineare anche database esistenti, non solo creare schemi nuovi;
- se `studio.db` esiste ma la tabella fascicoli è vuota, il JSON configurato può essere usato solo come bootstrap controllato; dopo ogni salvataggio SQL il JSON fascicoli viene rigenerato come mirror, non come fonte decisionale;
- lo stato firma dei documenti non deve derivare dal flag storico `firmato` o da testo/nome file: per mostrare `Firmato` servono CAdES `.p7m`/PKCS#7 o metadati tecnici PAdES verificati nel documento;
- quando un preventivo viene accettato, il profilo passa al conferimento incarico; quando dal conferimento nasce il fascicolo, il profilo passa al fascicolo e viene rafforzato con ufficio, PEC, codice deposito e certificato quando il canale lo richiede;
- PAT, PTT e PDP restano canali separati con regole dedicate: non sono varianti del PCT civile e non devono ereditare certificati o blocchi non pertinenti.

Matrice permanente canali deposito e fonti ufficiali, da non perdere dopo compattazioni:

- `PCT/SICID`, `PCT lavoro/SICID`, `PCT/SIECIC`, `SIGP/Giudice di Pace` e Cassazione civile/PST quando usa busta ministeriale: fonte Ministero della Giustizia/PST, DM 44/2011 art. 34 e specifiche tecniche DGSIA 7 agosto 2024 efficaci dal 30 settembre 2024. Il software deve risolvere codice oggetto PST, ufficio, PEC ufficiale, documenti, firme richieste, `DatiAtto.xml`, `IndiceDocumentiDepositati.PDF`, `Atto.msg` e `Atto.enc` AES256. Il certificato `.cer` PST dell'ufficio è requisito del trasporto solo per questi canali/uffici quando generano `Atto.enc`. Limite busta PCT corrente: `60 MB`. Il job `pst_certificati_cifratura_weekly` aggiorna questa cache tecnica condivisa e deve saltare uffici non pertinenti, storici o non operativi senza far fallire gli altri certificati; il singolo deposito resta invece bloccato se il proprio ufficio richiede `.cer` e il certificato non è verificato.
- `PDP penale`: fonte PST/Ministero della Giustizia, Decreto Ministero Giustizia 4 luglio 2023 e specifiche tecniche Portale Deposito atti Penali efficaci dal 20 luglio 2023. Non usa `DatiAtto.xml` civile, non usa `Atto.enc` PCT e non deve ereditare il `.cer` PST civile. Il software deve preparare atto e allegati secondo formato/firma richiesti, guidare o importare il deposito dal portale PDP e salvare ricevute/esiti nel fascicolo. Limiti PDP da presidiare: `50 MB` per singolo file, `500 MB` per deposito complessivo.
- `PAT/SIGA amministrativo`: fonte Giustizia Amministrativa, regole tecnico-operative PAT e modifica 2025/2026. Dal 1 febbraio 2026 il deposito tramite Formweb è canale prioritario; la PEC è residuale solo per comprovate ragioni tecniche o casi previsti. Non usa `.cer` PST civile né `Atto.enc` PCT. Il software deve preparare modulo/atto, allegati, firme PAdES quando richieste, checklist PAT, upload assistito Formweb e import ricevute. Limiti Formweb da presidiare: massimo `50` file, `300 MB` per singolo file e `300 MB` complessivi.
- `PTT/SIGIT tributario`: fonte MEF/Dipartimento della Giustizia Tributaria e Gazzetta Ufficiale, specifiche tecniche PTT 6 novembre 2020 e modifiche 21 aprile 2023. Non usa `.cer` PST civile né `DatiAtto.xml` PCT. Il software deve controllare PDF/A quando richiesto, firma digitale, limite `50 MB` per singolo file, upload SIGIT e import ricevute/esiti.
- `UNEP`, notifiche PEC e PEC stragiudiziale: sono canali diversi dal deposito PCT del fascicolo. Devono avere relata/testo, destinatari, domicilio digitale, firme e ricevute governati dal flusso notifiche/PEC; non possono essere dichiarati deposito valido e non devono attivare `Atto.enc` nel flusso `Prepara deposito` salvo una regola futura documentata come canale autonomo.

Regola permanente certificati PST `.cer` e conteggi, da non perdere dopo compattazioni:

- il numero da usare per dire se il deposito PCT/SIGP/Cassazione è coperto non è il totale dei `.cer` fisici in cache, ma il perimetro dei codici ministeriali attivi che richiedono certificato per `Atto.enc`;
- controllo corrente locale: cache fisica `D:\legale\IUSENTRA\data\pst\certificati_cifratura`, `913` file `.cer`, `913` certificati DER validi, `0` invalidi;
- perimetro operativo corrente: `593` codici ministeriali unici che richiedono `.cer/Atto.enc`, `593/593` coperti, `0` mancanti;
- `/tribunali` può mostrare più righe ufficio rispetto ai codici unici perché alcuni uffici/alias condividono lo stesso codice ministeriale e lo stesso certificato; il controllo decisivo resta sul codice ministeriale unico;
- i metadati ministeriali importati da `C:\QuickOrganizer\ListaUfficiGiudiziari.xml` e `C:\QuickOrganizer\QC_Uffici.xml` alimentano `pct/data/uffici_ministero.json` e `pct/data/uffici_ministero_extra.json`;
- il downloader deve usare anche il recupero diretto PST per codice ministeriale e nome ufficio quando il XML ministeriale non espone `nomeCertificatoCifra`; caso provato: `Giudice di Pace - Palmi`, codice ministeriale `0800570152`;
- la certezza operativa corretta è: sul catalogo corrente controllato i target sono tutti coperti; se il Ministero cambia catalogo o aggiunge un ufficio, il job settimanale deve scaricare/validare il nuovo `.cer`; se un singolo fascicolo richiede `.cer` e quel certificato manca o non è valido, `Invia deposito reale` deve restare bloccato con motivo puntuale e non registrare il deposito come valido;
- report tecnico: `data/pst/certificati_cifratura/audit_certificati_cifratura_pst.json`, con `ok=true`, `catalogo_pct_operativi=593`, `scaricati_o_validi=593`, `saltati_senza_certificato_pubblicato=0`, `errori=0`, `cache_cer_presenti=913`.

Il comando operativo è:

```powershell
python scripts/audit_data_flow_contract.py --registry data/tenants.json --repair-json-mirror --repair-search-index --json
python scripts/audit_data_flow_contract.py --registry data/tenants.json --json
```

Per il presidio fisico della struttura tenant usare anche:

```powershell
python scripts/audit_tenant_data_structure.py --registry data/tenants.json --repair --json
python scripts/audit_tenant_data_structure.py --registry data/tenants.json --json
```

Il primo comando puo' creare o riallineare solo strutture e mirror rigenerabili; il secondo comando e' il controllo a freddo. Lo stato accettabile richiede `source_of_truth=sqlite` o `source_of_truth=postgresql`, `json_authoritative=false`, zero errori, zero warning bloccanti e `hidden_json_summary.operational_untracked=0`.

Il primo comando può riparare solo parti rigenerabili: mirror SQL `moduli_json_records` e indice di ricerca `search_documenti`. Non deve toccare dati principali come fascicoli, clienti, agenda, scadenze, documenti o comunicazioni. Il secondo comando è il controllo a freddo senza riparazioni e deve restare verde prima di parlare di struttura dati coerente.

## Stato attuale della tranche

- Fatto a livello codice: contratto applicativo dati/tenant/route React/topbar/sottomenu in `pct/data_flow_contract.py`.
- Fatto a livello codice: parità core PostgreSQL e migrazione per messaggi, privacy, notifiche, backup e time tracking.
- Fatto a livello script: `scripts/audit_data_flow_contract.py` diagnostica `studio.db`, mirror JSON e indice FTS e ripara solo cache rigenerabili quando l'opzione è esplicita.
- Fatto su tenant locale reale il 2026-06-14: audit `tenant-8bf98719c459` con `quick_check=ok`, `moduli_json_records` leggibile con 3734 record e `search_documenti` leggibile dopo riparazione FTS; la riparazione non ha modificato tabelle core.
- Fatto su tenant locale reale il 2026-06-16: `scripts/audit_tenant_data_structure.py` e' stato esteso per censire anche JSON operativi nascosti e famiglie dinamiche. Sul tenant `tenant-8bf98719c459` l'audit a freddo risulta `source_of_truth=sqlite`, `json_authoritative=false`, 436 moduli in `moduli_dati`, 7772 record in `moduli_json_records`, 242 JSON classificati come cache/archivio e 0 JSON operativi non censiti. Il mirror corrotto `agenda/calendar_sync_engine.json` e' stato preservato come `.bak` e rigenerato in UTF-8 valido senza BOM.
- Fatto su macchina reale locale il 2026-06-14, versione `2.253.24`: perimetro `Studio` verificato in Chrome visibile su `127.0.0.1:8080`, con apertura e scroll di `/studio`, `/fatturazione`, `/preventivi`, `/compensi-forensi`, `/documenti`, `/redazione-atti`, `/statistiche`, `/ricerca-legale`, `/legal-skills`, `/workflow-agents`, `/giurisprudenza`, `/strumenti-legali`, `/strumenti-operativi`; tutte le route hanno `#root`, menu Studio completo e nessun fallback `?_legacy=1`.
- Fatto su macchina reale locale il 2026-06-14, versione `2.253.24`: topbar verificata su Studio per `Voce Studio`, `Timer attività`, data italiana, `Scadenze rapide`, `Ultimi elementi aperti`, `Notifiche operative`, `Nuovo` e `Assistenza remota`; la sessione assistenza creata dal test è stata chiusa come `Chiusa`.
- Fatto a livello codice e verificato su macchina reale locale il 2026-06-14, versione `2.253.25`: l'icona `Recenti` della topbar è stata estesa a `Recenti e ricerche`; il badge ora somma elementi aperti e ricerche recenti, il pannello mostra sezioni distinte `Elementi aperti` e `Ricerche recenti`, e la nuova API protetta `/api/recent/search` registra query deduplicate collegate a `/global-search?q=...`. Prova reale eseguita in Google Chrome visibile su `127.0.0.1:8080`: ricerca `RG`, apertura `/fascicoli/8804C177`, ritorno a `/studio`, pannello `Recenti e ricerche (2)` con `items=1`, `searches=1`, `totalCount=2`, nessun errore console.
- Da fare prima di qualunque chiusura complessiva: verifica reale anche delle altre macro-aree e sottomenu, commit, push branch gemelli, controlli GitHub/CodeQL e deploy Hetzner.

## Regola deposito e flussi sensibili

Per deposito telematico, fascicoli, PEC, notifiche legali, portali, Local Signer e firma digitale resta obbligatorio aggiornare anche `artifacts/react-migration/procedura-deposito-telematico.md`. Il software deve preparare ciò che può preparare subito, spiegare cosa manca, bloccare solo requisiti obbligatori e non registrare come deposito valido un pacchetto ministeriale non conforme.

Regola permanente `Invia deposito reale`: nel flusso `Prepara deposito`, dopo verifica positiva di prova senza invio, firme salvate, indice documenti visualizzabile, destinatario PEC verificato, testo PEC controllato e busta/trasporto ministeriale conforme, il bottone `Invia deposito reale` deve attivarsi. Se resta disabilitato, la UI deve indicare il requisito obbligatorio mancante in modo puntuale e verificabile; se i requisiti previsti sono tutti rispettati, il blocco del bottone è una regressione da correggere prima di commit, push e deploy.

Regola permanente relata/notifica: la relata o la prova di notifica si chiude solo dopo confronto con fonti normative ufficiali, testo reale visualizzato o generato, dati obbligatori verificati, firma digitale della relata quando richiesta, prova senza invio reale e collegamento documentale nel fascicolo. Se tutto è conforme, l'esito deve essere documentato in `artifacts/react-migration/procedura-deposito-telematico.md`; se manca un requisito, la UI deve indicarlo e non deve registrare la notifica come effettiva.

## Regola anti falso-verde

Un test automatico verde non significa lavoro concluso. Per qualsiasi comportamento visibile serve prova reale sulla macchina dell'utente. Se non è stata eseguita, il report deve dire chiaramente: non verificato su macchina reale.
