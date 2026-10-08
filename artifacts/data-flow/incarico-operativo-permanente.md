# Incarico operativo permanente: dati, tenant, React e topbar

Ultimo aggiornamento: 2026-06-17.

Questo file va riletto dopo ogni compattazione insieme ad `AGENTS.md` prima di riprendere lavori su IUSENTRA. L'incarico dell'utente non riguarda un singolo pulsante: riguarda la chiusura dell'applicativo come sistema unico, con dati coerenti, route full React, tenant corretto e controlli reali.

Per lavori su PolisWeb, accesso PST, ricerca/import fascicoli, scarico documenti, eventi di cancelleria, notifiche PEC da fascicolo, agenda/scadenziario alimentati dal portale o presidio PEC collegato ai fascicoli, va riletto anche `artifacts/react-migration/polisweb-studio-telematico-end-to-end.md`. Quel file contiene la matrice registro per registro e campo per campo ricostruita da Studio Telematico, sorgenti locali e fonti ministeriali; non procedere a memoria.

Per lavori su presidio PEC, comprensione evento legale, udienze lette da PEC/documenti, link audiovisivi, sentenze, spese, liquidazioni, gratuito patrocinio, Agenda, Scadenziario, notifiche, web push o Lex AI alimentato da PEC va riletto anche `docs/specs/PEC_LEGAL_EVENT_UNDERSTANDING_V2.md`. Quel file contiene la matrice V2, lo schema dati, le tabelle SQLite/PostgreSQL e i test obbligatori del presidio legale professionale.

## Incarico permanente deposito telematico e relata

Questa parte non va più ricostruita dalla chat. Dopo ogni compattazione, quando si riprende deposito, PEC, firma digitale, Local Signer, certificati PST, scheduler, relata o prova notifica, l'obiettivo operativo è uno solo: chiudere il flusso reale, verificabile documento per documento, senza regressioni e senza dichiarare verde ciò che non è stato visto sulla macchina reale o sul server reale richiesto.

Regola di metodo:

1. per difetti visibili si corregge prima il comportamento nella vista reale indicata dall'utente;
2. solo dopo una prova reale positiva si consolidano test, documentazione, commit, push, deploy e igiene;
3. se il problema nasce su produzione, si verifica prima su `https://app.iusentra.it`, poi si riporta lo stesso codice in locale;
4. alla fine server, locale e GitHub devono puntare allo stesso commit, con Docker locale healthy su `127.0.0.1:8080` e Hetzner healthy su `https://app.iusentra.it/api/pronto`.

Guardrail Hetzner permanente: il profilo di produzione deve lasciare un solo container applicativo, chiamato esattamente `iusentra-app`. Dopo ogni commit, push, deploy o hotfix server va controllato `docker ps` e il `docker compose` di `deploy/hetzner`: se esistono `iusentra-app-1`, container del progetto Compose `repo`, copie app parallele o più servizi applicativi sulla porta 8080, il deploy resta non valido finché la copia parallela viene fermata/rimossa senza toccare volumi o dati applicativi e il servizio corretto torna healthy.

Il deposito deve funzionare in tutti i percorsi di nascita della pratica:

1. preventivo accettato, conferimento incarico, fascicolo;
2. nuovo fascicolo diretto;
3. fascicolo veloce o autonomo.

In tutti e tre i casi il software deve costruire e salvare in SQL il `profilo_deposito` con canale riconosciuto, regole canale, codice deposito/codice oggetto, ufficio giudiziario, PEC verificata, certificato `.cer` quando richiesto dal PCT/SIGP/Cassazione e motivi puntuali se qualcosa manca. Il dato non deve restare solo nel JSON: le colonne dedicate `profilo_deposito_json` di `preventivi_records`, `conferimenti_records` e `fascicoli` sono parte del contratto, con parità SQLite/PostgreSQL.

Per la firma digitale vale una regola assoluta: la UI può mostrare `Firmato` solo se esiste una prova tecnica reale. Per CAdES il file normalmente diventa `.pdf.p7m` o comunque contenitore PKCS#7 verificabile; per PAdES il PDF può restare `.pdf`, ma deve contenere una firma interna verificabile. Il software non deve mai scrivere `Firmato digitale` perché trova la parola "Firmato" nel testo, nel nome del file o in un flag storico.

`Invia deposito reale` deve restare disabilitato solo per un requisito obbligatorio effettivamente mancante. Se prova senza invio, firme salvate, indice visualizzabile, PEC destinatario verificata, corpo PEC controllato, busta/trasporto conforme, certificato `.cer` richiesto presente, `Atto.enc` richiesto generato e PEC mittente/SMTP disponibili risultano tutti corretti, il bottone deve attivarsi. Se resta disabilitato, la UI deve indicare esattamente il requisito bloccante; se non lo indica, è una regressione.

Regola permanente invio PEC: per depositi, notifiche legali e verifiche operative PEC il server non è mai il canale SMTP reale. Il comportamento corretto è quello dichiarato in `/impostazioni?tab=pec`, sezione `Verifiche PEC`: `Il controllo dell'invio parte dal PC in uso: la password resta sul dispositivo locale.` Quindi anche quando IUSENTRA gira su `https://app.iusentra.it`, il server prepara e verifica busta, destinatario, oggetto, corpo PEC, allegato `Atto.enc` e ricevute, ma l'invio effettivo parte dal PC dell'avvocato tramite Local Signer/servizio locale. Qualunque variabile, rotta legacy o scorciatoia che abiliti SMTP server-side per un invio legale è da trattare come regressione.

Regola permanente di velocità operativa: quando manca un dato configurabile che blocca un flusso sensibile, come PEC SdI, PEC mittente, email commercialista, firma o canale Local Signer, la UI deve offrire nello stesso pannello un'azione rapida per inserire i campi essenziali, salvarli tramite le API reali di Impostazioni e riprendere il flusso senza cambiare pagina o perdere contesto. Le impostazioni complete possono restare raggiungibili, ma il blocco non deve obbligare l'avvocato a ricostruire manualmente il percorso.

Regola permanente lingua/date/orari visibili: tutto ciò che l'avvocato vede deve usare italiano coerente, data italiana e ora `Europe/Rome` come standard unico di prodotto. Nessuna pagina, PDF, PEC/email in arrivo, email ordinaria, ricevuta, esito SdI/PCT, audit visibile, pannello amministrativo, report, pagamento, scadenza, topbar, assistente o documento generato può mostrare date macchina come `2026-04-09`, timestamp ISO raw, label `Data UTC`, suffissi `UTC`, formati inglesi o formati internazionali. Le date visibili devono diventare `09/04/2026`; le date con ora `09/04/2026 17:51` e, quando serve esplicitare il fuso, `09/04/2026 17:51 (Europe/Rome)`. I valori tecnici originali possono restare solo nei payload macchina, XML/XSD/EML originali, header email originali, firme, API interne, campi HTML tecnici e tracciati ministeriali; appena vengono mostrati a video o stampati in PDF/email devono passare dagli helper condivisi (`format_date_it`, `format_datetime_it`, `formatDateIt`, `formatDateTimeIt`). Ogni nuovo sviluppo deve controllare questa regola prima di commit e ogni difetto visibile va corretto sul perimetro reale, non solo nella pagina segnalata.

Regola permanente `Atto.enc`: nome file, estensione, dimensione o base64 valido non bastano mai per abilitare l'invio reale. Prima della password PEC locale il software deve verificare che l'allegato `Atto.enc` sia un CMS/PKCS#7 `EnvelopedData` ministeriale riconoscibile, generato da `Atto.msg` contenente `DatiAtto.xml.p7m` firmato CAdES, indice busta ministeriale coerente con i file fisici e `IndiceDocumentiDepositati.PDF`. Per i `DatiAtto.xml` ministeriali l'indice busta è interno a `DatiAtto.xml.p7m` e non va duplicato con `IndiceBusta.xml` esterno; il file esterno resta ammesso solo nei casi non ministeriali previsti. Il report deve mostrare algoritmo CMS effettivo e presenza dell'indice ministeriale; se il payload non è CMS, se l'indice busta manca o se `DatiAtto.xml.p7m` non incapsula il metadato della stessa busta, il flusso blocca prima della password PEC e non registra il deposito come valido.

Correzione operativa 29/06/2026 su esiti reali PST fascicolo `795C50AC`: l'indice solo interno nel `DatiAtto.xml.p7m` non è accettabile come prova di trasporto. Il software deve generare e verificare `IndiceBusta.xml` come parte MIME fisica di `Atto.msg`, oltre a `DatiAtto.xml.p7m`, `IndiceDocumentiDepositati.PDF`, atto principale e allegati. Il controllo bloccante prima della password PEC deve confrontare ogni `Nome` e `ID` di `IndiceBusta.xml` con il file fisico e il `Content-ID` MIME effettivo, inclusi i nomi firmati `.p7m`; in caso contrario il PST può restituire `Indice busta non trovato`, `Atto principale mancante`, `Allegato indicato in indice busta non presente` o `Presenza di allegati non definiti in Indice Busta`.

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

- `fascicoli/documenti_ai/**/*.json`, `fascicoli/importazioni/**/*.json` e `intelligence/lex_dataset/**/*.json` non entrano nel mirror SQL del bootstrap/runtime ordinario;
- queste famiglie pesanti e rigenerabili restano nei repository verticali dedicati e possono essere censite come `documenti_ai_file_*`, `fascicoli_importazione_*` e `lex_dataset_*` soltanto da un audit/riparazione esplicito con `include_recursive=True`, stima preventiva, backup e report;
- Agenda, Scadenziario, topbar, worker PEC e apertura del tenant non devono mai innescare la scansione ricorsiva di tali alberi.

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

- Fatto a livello codice il 2026-07-20 per Notifiche legali: nuovo presidio persistente `pec_notification_presidio` con migrazioni SQLite/PostgreSQL, repository tenant-aware, API JSON dedicata `/api/v1/ui/notifiche-legali/presidi`, route React full `Presidi notifiche`, rollout per tenant e guardrail che mantengono il flag spento a zero letture operative. Il workflow storico resta disponibile solo come import lazy su richiesta dell'utente.
- Fatto a livello codice: contratto applicativo dati/tenant/route React/topbar/sottomenu in `pct/data_flow_contract.py`.
- Fatto a livello codice: parità core PostgreSQL e migrazione per messaggi, privacy, notifiche, backup e time tracking.
- Fatto a livello script: `scripts/audit_data_flow_contract.py` diagnostica `studio.db`, mirror JSON e indice FTS e ripara solo cache rigenerabili quando l'opzione è esplicita.
- Fatto su tenant locale reale il 2026-06-14: audit `tenant-8bf98719c459` con `quick_check=ok`, `moduli_json_records` leggibile con 3734 record e `search_documenti` leggibile dopo riparazione FTS; la riparazione non ha modificato tabelle core.
- Fatto su tenant locale reale il 2026-06-16: `scripts/audit_tenant_data_structure.py` e' stato esteso per censire anche JSON operativi nascosti e famiglie dinamiche. Sul tenant `tenant-8bf98719c459` l'audit a freddo risulta `source_of_truth=sqlite`, `json_authoritative=false`, 436 moduli in `moduli_dati`, 7772 record in `moduli_json_records`, 242 JSON classificati come cache/archivio e 0 JSON operativi non censiti. Il mirror corrotto `agenda/calendar_sync_engine.json` e' stato preservato come `.bak` e rigenerato in UTF-8 valido senza BOM.
- Fatto su macchina reale locale il 2026-06-14, versione `2.253.24`: perimetro `Studio` verificato in Chrome visibile su `127.0.0.1:8080`, con apertura e scroll di `/studio`, `/fatturazione`, `/preventivi`, `/compensi-forensi`, `/documenti`, `/redazione-atti`, `/statistiche`, `/ricerca-legale`, `/legal-skills`, `/workflow-agents`, `/giurisprudenza`, `/strumenti-legali`, `/strumenti-operativi`; tutte le route hanno `#root`, menu Studio completo e nessun fallback `?_legacy=1`.
- Fatto su macchina reale locale il 2026-06-14, versione `2.253.24`: topbar verificata su Studio per `Voce Studio`, `Timer attività`, data italiana, `Scadenze rapide`, `Ultimi elementi aperti`, `Notifiche operative`, `Nuovo` e `Assistenza remota`; la sessione assistenza creata dal test è stata chiusa come `Chiusa`.
- Fatto a livello codice e verificato su macchina reale locale il 2026-06-14, versione `2.253.25`: l'icona `Recenti` della topbar è stata estesa a `Recenti e ricerche`; il badge ora somma elementi aperti e ricerche recenti, il pannello mostra sezioni distinte `Elementi aperti` e `Ricerche recenti`, e la nuova API protetta `/api/recent/search` registra query deduplicate collegate a `/global-search?q=...`. Prova reale eseguita in Google Chrome visibile su `127.0.0.1:8080`: ricerca `RG`, apertura `/fascicoli/8804C177`, ritorno a `/studio`, pannello `Recenti e ricerche (2)` con `items=1`, `searches=1`, `totalCount=2`, nessun errore console.
- Fatto a livello codice il 2026-07-02/03 per PolisWeb/PST: matrice registri e payload tecnici allineati al confronto Studio Telematico + fonte PST v1.67; SIECIC esplicito (`ESM`, `ESIM`, `FALL`) conserva `registro`, `idRuoloJPW` e `idDfa`; il download batch Local Signer usa `idCat` anche su SIECIC dopo profilo `idDoc`, preservando un solo lotto e senza ricadere su download singoli che moltiplicano il PIN. Il 03/07/2026 i flussi già testati sono stati rinforzati: i documenti legacy ereditano `servizio_pst`/`registro_portale` dal fascicolo e il master/detail prova prima `idDocumento`, usando `idCat` solo come recupero finale. Dettaglio operativo in `artifacts/react-migration/polisweb-studio-telematico-end-to-end.md`.
- Fatto a livello codice e test il 03/07/2026 per dati tenant-aware dei portali: quando il runtime riceve un `CLIENTI_DB` esplicito, anche `SOGGETTI_DB`, `SOGGETTI_PARTI_DB`, `PORTALE_DB`, `PORTALE_UPLOADS` e `PORTALE_IMPORT_LOG_DB` vengono derivati dalla stessa root e non da variabili d'ambiente globali. Il controllo evita import log, soggetti o metadati portale fuori tenant ed è coperto da `tests/test_polisweb.py`.
- Fatto su macchina reale locale il 2026-07-03 per `/portali/pst/acquisizione`: durante la verifica il `studio.db` del tenant `tenant-8bf98719c459` è risultato corrotto. È stato ripristinato da snapshot SQLite valido `.studio.migrazione-20260703005431140775.db`, il DB corrotto è stato conservato in `data/tenants/tenant-8bf98719c459/backup/sqlite_corrupt_recovery/studio_corrotto_20260703_005611.db`, `PRAGMA quick_check=ok` è stato verificato e il journal locale è stato portato a `DELETE` per evitare blocchi su bind mount Docker/Windows.
- Fatto su macchina reale locale il 2026-07-03, versione `2.253.152`: pagina React `/portali/pst/acquisizione` verificata nel browser integrato su `127.0.0.1:8080`. Menu registri professionale completo, reset `Automatica` funzionante dopo selezione `Minorenni`, cronologia e `Riprova scarico` senza `Failed to fetch`, senza timestamp ISO e senza virgola tra data e ora; nessun testo visibile `Studio Telematico`, `QuickOrganizer` o `JPW`. Responsive controllato su desktop `1280x720`, tablet `900x900` e mobile `390x844`, con scroll fino al fondo e nessun overflow orizzontale.
- Fatto su macchina reale locale il 2026-07-03, versione `2.253.152`: dopo ulteriore rebuild reale, il pannello ricerca PST senza certificato locale non mostra più un caricamento ambiguo. Click su `Cerca fascicoli` senza CNS/CIE valida: nessun dato finto, messaggio puntuale sul certificato mancante, riquadro `Ricerca non avviata` / `Nessun passaggio avviato`, nessuna barra di progresso attiva. Verificato bundle React `index-DjwyyfRQ.js`, menu `Minorenni` / `Giudice di Pace` / `Automatica`, desktop `1280x720`, tablet `900x1000` e mobile `390x844` senza overflow orizzontale e senza testi tecnici vietati.
- Fatto su macchina reale locale il 23/08/2026, release `2.278.66`: il job `daily_plan_incremental_refresh` del tenant `studio-montagnese` ha rilevato corruzione limitata a `intelligence/daily_plan.db`. Prima del ripristino sono stati verificati integri con `PRAGMA quick_check` `studio.db`, PEC, fascicoli, notifiche, ricerca e preventivi; app e scheduler sono stati fermati, il database corrotto, WAL/SHM e dump `.recover` sono stati conservati in `data/tenants/tenant-8bf98719c459/backup/daily_plan_recovery/phase0_20260823_153000/`. Il recupero SQLite ha preservato le sette tabelle e gli indici previsti; dopo scambio atomico `quick_check=ok`, `daily_plan_startup_recovery` e il job incrementale reale hanno terminato con `1` studio e `0` errori. Il repository resta una proiezione materializzata tenant-aware; fonti core, documenti e mirror JSON non sono stati modificati. Il journal locale resta `DELETE` per il bind mount Docker/Windows.
- Da fare prima di qualunque chiusura complessiva: verifica reale anche delle altre macro-aree e sottomenu, commit, push branch gemelli, controlli GitHub/CodeQL e deploy Hetzner.

## Regola deposito e flussi sensibili

Per deposito telematico, fascicoli, PEC, notifiche legali, portali, Local Signer e firma digitale resta obbligatorio aggiornare anche `artifacts/react-migration/procedura-deposito-telematico.md`. Il software deve preparare ciò che può preparare subito, spiegare cosa manca, bloccare solo requisiti obbligatori e non registrare come deposito valido un pacchetto ministeriale non conforme.

Regola permanente `Invia deposito reale`: nel flusso `Prepara deposito`, dopo verifica positiva di prova senza invio, firme salvate, indice documenti visualizzabile, destinatario PEC verificato, testo PEC controllato e busta/trasporto ministeriale conforme, il bottone `Invia deposito reale` deve attivarsi. Se resta disabilitato, la UI deve indicare il requisito obbligatorio mancante in modo puntuale e verificabile; se i requisiti previsti sono tutti rispettati, il blocco del bottone è una regressione da correggere prima di commit, push e deploy.

Regola permanente relata/notifica: la relata o la prova di notifica si chiude solo dopo confronto con fonti normative ufficiali, testo reale visualizzato o generato, dati obbligatori verificati, firma digitale della relata quando richiesta, prova senza invio reale e collegamento documentale nel fascicolo. Se tutto è conforme, l'esito deve essere documentato in `artifacts/react-migration/procedura-deposito-telematico.md`; se manca un requisito, la UI deve indicarlo e non deve registrare la notifica come effettiva.

## Regola anti falso-verde

Un test automatico verde non significa lavoro concluso. Per qualsiasi comportamento visibile serve prova reale sulla macchina dell'utente. Se non è stata eseguita, il report deve dire chiaramente: non verificato su macchina reale.

## Aggiornamento 20/07/2026 - presidio notifiche fascicoli, topbar e Web Push

- Fonte di verità del presidio notifiche interno ai fascicoli: `studio.db`, tabella `fascicoli`, campo `documenti_json`; i JSON tenant-aware restano mirror/storico e non sono fonte decisionale quando esiste SQL.
- Regola storica tenant Montagnese: fino al `19/07/2026` le notifiche dovute risultano eseguite dallo studio; il codice applica `storico_gestito` e non crea nuove azioni su quei segnali. Dal `20/07/2026` eventuali documenti/provvedimenti da notificare restano residui veri.
- La topbar non scansiona i fascicoli al caricamento: il job schedulato `legal_notification_relata_presidio` materializza fuori UI solo i residui veri in `notifications/notifications.db` con `source_type=legal_notification_presidio`.
- Web Push usa il repository notifiche esistente: se viene creato un nuovo residuo vero, il servizio `NotificationService.sync_operational_items` lo deduplica e lo invia solo ai dispositivi/subscription abilitati.
- Calendario/scadenziario: i residui con stato `da_preparare`, `da_firmare` o `pronta_invio` creano/aggiornano una scadenza `TipoTermine.NOTIFICA` con marker `IUSENTRA_LEGAL_NOTIFICATION`; quando il residuo sparisce, la scadenza aperta creata dal job viene completata.
- Audit server Montagnese: `301` fascicoli visibili analizzati, `0` notifiche residue, `0` azioni correlate, `0` falsi positivi; report in `artifacts/notifiche-legali/audit-montagnese-301-20260720.md`.

## Aggiornamento 21/07/2026 - isolamento PEC e guardrail contro la crescita di `studio.db`

- La fonte PEC verticale è `PEC_AUDIT_DB` del tenant, letta con lo slug/storage key; topbar e Web Push usano separatamente l'identificativo tecnico del tenant nel repository notifiche. I due identificativi non sono intercambiabili.
- Ogni nuovo ID PEC deriva da tenant e impronta MIME. Lookup per ID, Message-ID header e deduplicazione includono sempre il tenant; nessuna GET o inizializzazione può adottare, spostare o riassegnare righe `default` a un altro studio.
- Se il backend core/topbar è PostgreSQL e manca il DSN, il runtime fallisce chiuso prima di creare SQLite locali o completare/scadere notifiche. Un errore del repository presìdi non viene convertito in lista vuota durante la riconciliazione.
- Il bootstrap tenant sincronizza soltanto i moduli JSON core esplicitamente governati. La scansione ricorsiva di OCR, `documenti_ai`, importazioni e dataset Lex è riservata agli audit espliciti e non può partire dal caricamento ordinario.
- Causa accertata sul tenant Montagnese: il primo ciclo scheduler aveva incorporato circa 15 GB di JSON OCR/estratti in `moduli_dati` e `moduli_json_records`. Il guardrail runtime elimina la causa; la manutenzione del database deve rimuovere solo quei mirror ricostruibili, confrontare tutte le tabelle strutturate prima/dopo e conservare rollback verificabile.
- La copia locale e la produzione devono coincidere per commit, versione, schema e comportamento, non per contenuto privato. I dati reali Montagnese restano sul server; il collaudo locale usa un tenant isolato e dati controllati, senza copiare credenziali, sessioni o l'intero archivio documentale.

## Aggiornamento 22/07/2026 - contratto Local Signer loopback

- Il Local Signer, l'AI locale e i canali PST/firma/deposito/notifiche sono servizi su `127.0.0.1` o `localhost`: per Chrome Local Network Access lo spazio corretto è `loopback`, non `local`.
- Ogni superficie React che chiama il servizio locale deve usare lo stesso contratto; la distinzione tenant resta lato API e payload, non tramite URL o database paralleli.
- Il controllo `tools/check_local_signer_boundaries.py` è parte del doppio controllo dati/route: se un nuovo file frontend torna a `targetAddressSpace: local`, il lavoro non può essere dichiarato chiuso.
- La prova reale su produzione e su `127.0.0.1:8080` resta necessaria perché il guardrail verifica il contratto statico, non l'interazione materiale con Chrome, permesso locale, PIN e sessione PST.
# Aggiornamento 15 agosto 2026 - Notiziario Panoramica

- Fonte operativa: repository SQL `legal_updates`; nessun elenco dimostrativo o JSON usato per conteggi e contenuti.
- Proprietà tenant: lettura, preferiti e fascicolo collegato persistono in `settings_config`, con schema SQLite/PostgreSQL condiviso e sezione distinta per utente.
- API React: `/api/v1/ui/notiziario`, `/api/v1/ui/notiziario/<id>/interazione` e `/api/v1/ui/notiziario/fonti/<fonte>`.
- Interfaccia full React: `NotiziarioPanel` nella Panoramica, con ricerca, filtri, lettore, tutto schermo e azioni verso fascicolo e Scadenziario.
- Fonti esterne: soltanto lista istituzionale chiusa; recupero limitato e nessun URL libero inviato al backend.
- Collaudo reale e matrice completa: `artifacts/react-migration/notiziario-panoramica-2026-08-15.md`.


08/10/2026 — Hotfix proforma e verifica XML, incarico aperto. Contratto della richiesta interna corretto senza ampliare la whitelist: giorni_scadenza resta configurazione, regime fiscale persiste nello snapshot canonico e data_scadenza calcolata viene preservata. Prova materiale produzione sul fascicolo Giffi Giada RG806/2026: click Genera proforma ha aperto bozza2026/085, totale €310,96, id737b530e-9d29-471f-8cc0-245d17065a2a. Nessuna emissione, firma o PEC. Priorità IBAN/Banca da Dati Studio applicata in repo/runtime server e locale; server unico iusentra-app healthy, ricarica Gunicorn senza riavvio container. Guardrail fatturazione23 positivi prima della correzione XSD. Locale inizialmente bloccato da IBAN assente, causa reale mostrata; inserite tramite UI le coordinate dello stesso studio indicate dall’utente. Regime fiscale RF19 confermato esplicitamente dall’utente, salvato materialmente nelle impostazioni di entrambe le copie; persistenza server confermata dopo reload.

Confronto allegato FE251: XML originale supera lo schema ufficiale FPR12 v1.2.3; generatore IUSENTRA precedente non lo supera per namespace dei figli. Correzione generatore condiviso in locale e server: figli non qualificati, ordine XSD di ritenuta/bollo/cassa/riepiloghi/pagamenti, Cassa Forense nel solo blocco dedicato, senza duplicazione delle righe. Quattro casi nativi ora superano lo schema ufficiale; questi riscontri non sostituiscono download reale PDF/XML, firma, preparazione PEC e verifica ricevute, ancora aperti. Sorgenti ufficiali XSD FPR12 e XMLDSig salvate sotto docs/specs/ministero/fonti_ufficiali/2026-10-08; file studio originali preservati fuoriGit. Baseline pct/fattura_pa.py coincideva integralmente con il backup accettato; nuovo intervento limitato alla generazione fattura richiesta, nessuna modifica a Local Signer/deposito/SMTP congelati.

Lex locale: apertura512px, drag reale singolo da[1199,411] a[817,225] senza doppio movimento, riduzione e richiamo dalla barra, ingrandimento materiale osservati. Correzione cattura drag condivisa evita movimento concorrente del widget nativo; layer host partecipa alla stessa sovrapposizione. Typecheck positivo. Non ancora installata sul server; ridimensionamento, affiancamento, reset, hover/focus e responsive restano da accettare materialmente. Comprensione del documento aperto e contesto Lex condiviso ancora aperti. Nessun commit/push finale e nessuna sostituzione del modello embedding.


08/10/2026 — Recupero lettore fatturazione e pubblicazione urgente, incarico aperto. Recuperato dal backup accettato 09/09 il servizio web/services/react_fatturazione_pdf_preview.py, impronta a4fb9be0be3cf36effc6787cbb6429f8158cb507165afead38c86704e84e93fa verificata sul manifesto. Ripristinato il solo percorso PDF nativo con ?viewer=mobile e testo selezionabile; rimossa la registrazione impropria di emissione dalla GET di anteprima recuperando il comportamento accettato. Nessun intervento su firme/deposito/SMTP. Barre del dettaglio compatte, doppioni di download e tutto schermo eliminati in favore dei comandi nativi del lettore/finestra.
Prova materiale locale: apertura del documento controllato 2026/003, zoom 100→125→100, focus da tastiera, scorrimento fino al fondo, download XML/PDF osservati. XML effettivamente scaricato supera XSD ufficiale dopo correzione della punteggiatura tipografica nel solo tracciato macchina; 23 guardrail fatturazione positivi. Originale FE251 e PDF di prova renderizzati e osservati su tutte le rispettive pagine. Non dimostra equivalenza fiscale completa: bollo assorbito, dettaglio spese generali, annotazione RF19, unicità nome XML e validazione runtime restano da completare.
Produzione: proforma 2026/085 aperta materialmente dalla pagina /fatturazione, click Anteprima PDF, lettore interno visibile con titolo e comandi su una riga, totale € 310,96, IBAN e banca dalle impostazioni; download effettivo C:/Users/antmm/Downloads/proforma_2026-085.pdf. Prova visiva preservata fuori Git: fattura-server-reader-ripristinato-20261008.jpg. /api/pronto ok versione 2.436.11; app unica iusentra-app healthy, container attivo da 15 ore. Nessuna emissione/firma/invio SdI. Utente autorizza prova simulata del trasporto senza firma; deve restare esplicitamente collaudo senza destinazione SdI reale, senza falsa ricevuta né stato fiscale emesso/inviato.

Incidente di pubblicazione riconosciuto all’utente: asset copiati inizialmente nel solo app mentre Caddy serve tramite iusentra-static-assets-1 readonly; moduli/CSS restituivano 404, memorizzati immutable dal browser. Corretto creando immagine statica aggiornata dal medesimo albero di asset e ricreando solo static-assets, poi aggiornando app. Rivalidazione CSS per release nella shell e nomi di build coerenti hanno ripristinato materialmente la grafica e il lettore. Deve essere blindato il flusso di pubblicazione con verifica di tutti gli asset prima di rendere attiva la shell e impedita cache immutable delle risposte negative; ulteriori pagine e prove responsive/hover/focus restano nell’incarico. Tentativi falliti registrati: docker cp sul container statico readonly, compose senza env-file, vecchia cache degli import/CSS, comando diagnostico di log JSON su pipe Windows, un percorso frontend duplicato in script. Primo tar di asset incompleto nella ripresa precedente è stato ricreato dopo attesa e verificato; nessun volume/dato applicativo cancellato.
Inventario dei sorgenti del backup rileva numerosi percorsi assenti: non equivale automaticamente a capacità perse perché alcune possono essere rifattorizzate. Moduli nativi di delivery/ricevute/defaults/pagamenti/SdI recuperati soltanto fuori repo per analisi e confronto, non installati alla cieca. Resta da verificare/recuperare il flusso governato, aggiornare la copia locale reale con le ultime modifiche, commit/push gemelli, CI e deploy finale sincronizzato. Nessuna sostituzione embedding completata.

08/10/2026 — Bollo e XML: fonti ufficiali consultate (FiscoOggi, risposta 428/2022; guida Agenzia Entrate novembre 2024). Il professionista può sostenere il bollo senza riaddebitarlo; il tributo resta dovuto e indicato nell’XML. Il riaddebito nel forfettario concorre ai compensi: nessun automatismo che trasformi il rimborso in anticipazione esclusa. Scelta per documento, default storico preservato. Prova materiale nella sola bozza controllata 2026/003 su 8080: Cassa attiva, Bollo attivo, bollo a carico studio selezionato, Salva fattura, reload e checkbox ancora selezionata. XML scaricato realmente ITMNTGPP94L01G791A_G6WOZ (1).xml: RF19, N2.2, BolloVirtuale SI, ImportoBollo 2.00, Cassa 11.96, totale e pagamento 310.96; validazione offline XSD ufficiale positiva. Primo clic aveva causato errore React: currentTarget letto dentro updater differito; corretto catturando checked prima. Primo reload perdeva la rappresentazione della scelta perché normalizzatore JSON ometteva il campo: corretto e riprovato materialmente. Non sono false conferme di invio/emissione.
Validazione primaria XML ora usa XSD e XMLDSig ufficiali inclusi nel pacchetto senza rete; nome file mantiene identificativo fiscale completo e progressivo nativo univoco di cinque caratteri. 27 guardrail test_fattura_pa/test_react_fatturazione_bridge positivi; build/typecheck positivi. Simulazione trasporto nativo SMTP su socket 127.0.0.1: allegato integro e rifiuto destinatario governato, nessuna destinazione SdI reale né mutazione fiscale; rapporto e messaggio EML fuori Git. Questa simulazione non dimostra firma o accettazione SdI. Autofill browser riempie ancora il filtro fascicolo quando compare PIN: nuova indicazione autocomplete per PIN in verifica, non ancora accettata. Installazione coerente server asset prima della shell in corso; prove server XML/bollo/PDF e sincronizzazione Git finale restano aperte.

08/10/2026 11:21 — Installati in produzione i sorgenti fatturazione/XML/bollo e gli asset della build coerente, dopo backup sorgenti dedicato. Tutti i265asset referenziati dal manifest hanno risposto200 prima di attivare la shell. Static-assets ricreato separatamente, app primaria sempre unica iusentra-app healthy da16ore; nessun riavvio container app o modifica volumi/dati. /api/pronto positivo2.436.11. Prova materiale server sulla proforma2026/085: aperturaAnteprimaPDF, riga comandi compatta, spese generali€39,00, Cassa€11,96 e totale€310,96 visibili. Immagine fatturazione-server-xml-bollo-release-20261008.jpg fuoriGit. La prova della proforma non dimostra generazione/invio XML di una fattura server: quel flusso resta aperto, insieme a firma/ricevute/configurazionePEC, accettazione completa e commit/push/deploy finale.
Corretto anche Caddy: cache lunga degli asset solo su2xx/3xx; errori statici4xx/5xx no-store. Configurazione validata prima del reload senza riavvio; riscontri effettivi404no-store e200immutable, readiness corretta. L’incidente di cache negativa non viene mascherato. Guardrail tecnici non sostituiscono ulteriore accettazione reale del perimetro.

08/10/2026 11:24 — Ripresa periodica senza nuova scansione: SQL persistente embeddinggemma2_initial_normattiva attivo ogni2minuti, ultimo lotto completed39889righe con225aggiunte (39889−39664=225), successivo in corso. Metadati candidato40125/756290, prima costruzione non completa e riconvalida finale ancora richiesta. SHA256 del sorgente job effettivamente installato nel worker identico al checkout b96d0ef02f0c3ef36497f79a1e80a47b52ac01482fd4a84ac987aa740c638a6d: contatore nativo presente nel runtime reale, senza nuova attivazione né promozione. Nessuna inferenza su servizi esterni, nessuna rilettura dei fascicoli o riavvio produzione. Il confronto registrato degli importi non dimostra superiorità: modello operativo precedente preservato, accettazione candidata e rilascio completo ancora aperti.
Prova materiale locale8080 dopo ultima build: reload bozza2026/003 e clic XML e SdI non popolano più il filtro numero fascicolo, archivio ancora1risultato e PIN vuoto. Confermato il correttivo autocomplete per il PIN di firma; nessuna lettura di credenziali, firma o invio. Non equivale ad accettazione del percorso SdI completo. Errori diagnostici di glob Windows risolti cercando i percorsi effettivi; nessuna modifica dei dati primari.

08/10/2026 — Ritorno ricevute fiscali PEC/SdI, incarico aperto. Controllate puntualmente tre PEC originali di produzione: consegna SdI 18249436389 (FE250, ITMNTGPP94L01G791A_250.xml.p7m), scarto 18245070795 (ITMNTGPP94L01G791A_00250 (1).xml.p7m, motivo «Nome file non valido»), mancato recapito 18223062587 (FE156). Lo scarto e la consegna appartengono a trasmissioni diverse: nessuna assimilazione per numero fattura. Verificatore nativo recuperato con impronte del backup accettato: corretto il confronto con daticert/identificativo, che contiene il Message-ID PEC sostituito dal gestore, distinto da daticert/msgid del client (RFC 6109 §§3.1.1 e 4.4). Le tre buste reali superano firma S/MIME, catena, revoche attuali, mittente attestato e destinatario configurato; verificato il collegamento dell'allegato al contenuto firmato. Nessuno stato fattura modificato durante questa diagnosi, nessuna firma o trasmissione eseguita.
Prova materiale browser produzione /email/: aperta Ricevuta di consegna 18249436389. Vista erronea «Ricevuta PEC», «Qualità verde», «Udienza trattazione scritta» e suggerimenti di collegamento processuale, pur essendo leggibile l'XML SdI. Nuovo ramo fiscale condiviso distingue i tre esiti, esclude udienze e scadenze processuali, conserva lo scarto critico, non scambia la lettura XML con prova autentica. Prova tecnica sul candidato, sugli stessi tre MIME SQL reali in sola lettura, positiva: consegna warning finché autenticità e correlazione non vengono consegnate, scarto danger, mancato recapito warning, nessuna udienza/termine generati. Non è ancora accettazione della nuova UI.
Ripristinati repository e servizi nativi di ricevute, coda SdI nella coda PEC persistente con retry governato e contesto tenant verificato. Ricevuta senza fattura univoca conservata SQL come correlation_required, senza retry continuo, con fonte e motivo; può adottare la stessa evidenza quando emerge la corrispondenza esatta. Bloccato spostamento della ricevuta già associata a una diversa fattura. 16 guardrail mirati positivi, incluso isolamento tenant e busta con identificativi differenti; typecheck/build positivi. Rapporti e backup fuori Git in D:/legale/backups/IUSENTRA/recovery-20261007-versions/sdi-authenticity-point-20261008.json e sdi-fiscal-profile-point-20261008.json. Hotfix server con backup sorgenti, pubblicazione asset prima del manifest e senza riavvio container app in corso. Restano prove reali server e 8080, verifica dei retry di consegna, ripresa della correlazione su evento fattura, parità PostgreSQL, audit e collegamento UI fattura, successivo consolidamento Git/locale/deploy finale. Nessuna dichiarazione di flusso concluso.

08/10/2026 13:15 — Wizard, recupero puntuale e associazione: incarico aperto. Cause accertate SQL: quattro fascicoli importati avevano numero_rg/anno_rg vuoti; i resolver dei riferimenti deposito consideravano i depositi nativi, non le EML originali importate. Confrontati originali, accettazione cancelleria EsitoAtto.xml, Comunicazione.xml, ufficio, cliente e codice fiscale valido della parte. Recuperati mediante CAS e audit i ruoli di A5EBD924 (860/2026), CA70A15F (957/2026), 84DC4FE1 (958/2026), preservando stato, documenti e decisioni. Snapshot coerente delle quattro righe fascicolo/clienti, diagnosi e applicazione conservati sul server e seconda copia D:/legale/backups/IUSENTRA/recovery-20261007-versions/wizard-role-data-20261008; quattro SHA256 coincidenti.
Ricerca rapida condivisa FascicoloSearchSelect in Wizard e dettaglio Agenda, per nome/cognome e altri riferimenti, installata server con 267 asset HTTP200 prima della shell. Nessuna selezione automatica fittizia. Prova materiale server: ricerca Spasov Ivan restituisce il fascicolo 2026/323; dopo recupero il collegamento è visibile e il clic Prepara apre realmente la sessione e96a9f97-c19a-4955-a057-22a38ff2651b, fascicolo A5EBD924, appuntamento FD16D934. Immagine wizard-spasov-apertura-reale-20261008.jpg fuori Git. Nessuna firma o invio.
Resolver Wizard corretto: R.G. da solo non basta, necessari cliente e ufficio identificato concordanti mediante helper condiviso; link espliciti preesistenti preservati. Cinque guardrail test_operational_catalog_regressions positivi. Primo hotfix aveva dipendenza _case_role non installata nel runtime server e ha prodotto errore500 elenco; corretta subito la dipendenza usando direttamente case_identity_evidence, pagina ricaricata e clic Prepara riuscito. Backup sorgenti wizard-joint-20261008_130627 e _130725. Non occultare l'incidente.
1CAA5E17 non aggiornato: ricorso, contratti e letture native già pronte della carta d'identità indicano CONTARTESE CRISTINA e codice della parte concordante; SQL e Comunicazione.xml indicano CONTARESE CRISTINA, codice anagrafico assente. Controllata materialmente la carta nel lettore interno: cognome CONTARTESE e nome CRISTINA leggibili. Non è un errore OCR né sola somiglianza. Fonte ministeriale discordante preservata, nessuna certezza fittizia o modifica del documento. Letture recuperate dal repository SQL dello stesso fascicolo, nessuna nuova OCR né scansione generale.
Incidente backup: primo tentativo di snapshot completo13GB aveva portato disco97%; prima delle scritture identificato e terminato solo il processo puntuale, eliminato esclusivamente snapshot temporaneo non validato. Sostituito con snapshot coerente del perimetro realmente modificato; dopo ripristino24GB liberi,93%. App primaria unica iusentra-app healthy da18ore, nessun riavvio container né campagna storica.
Restano integrazione del recupero nel job per eventi, discordanza del quarto caso, rilettura PEC puntuale a valle, prove locali8080/responsive/hover/focus, anno completo nel dettaglio Wizard, attività storiche da sentenze di esempio impropriamente presenti e doppia riga Sicari da diagnosticare, consolidamento Git/CI/locale/deploy. Questa prova server non è accettazione locale né chiusura.
08/10/2026 13:22 — Riscontro ulteriore nel browser reale produzione: aperto dal catalogo il Documento d'identità.PDF del fascicolo 1CAA5E17 e scorso il lettore fino al fondo. Cognome CONTARTESE, nome CRISTINA e codice fiscale della parte realmente visibili nel fronte/retro, coerenti con il testo SQL già estratto; non è prova di concordanza con Comunicazione.xml, che mantiene CONTARESE. Nessuna modifica anagrafica o attribuzione automatica forzata. Rilevate anche classificazioni improprie già presenti nel catalogo: EML di accettazione PEC etichettata Accettazione con beneficio d'inventario, EML di consegna come Contratto di lavoro. Da correggere nel resolver condiviso con evidenze del contenuto e senza toccare i MIME originali; incarico aperto.
Pulizia Hetzner eseguita con procedura nativa: tre immagini IUSENTRA inattive eliminate, cache builder recuperata1,329GB, due immagini in uso conservate. Volumi/dati/backup preservati. Repository locale ha il correttivo del resolver e guardrail, runtime8080 non aggiornato con quest'ultimo batch: non verificato su macchina reale locale. Nessun commit/push finale né promozione embedding.

08/10/2026 13:24 — Checkpoint periodico embedding in sola lettura: job SQL embeddinggemma2_initial_normattiva abilitato, ultimi lotti completed con 50.363 → 50.475 → 50.592 righe. Contatori nativi concordanti: 112 e 117 aggiunte rispettivamente, senza riattivazione o scansione ripetuta. Candidato 50.592/756.290, ultimo_id51093, costruzione incompleta e riconvalida finale richiesta: modello precedente conservato. Browser reale visibile 127.0.0.1:8080/impostazioni?tab=ai aperto e pannello scorso: avviso leggibile, barra di avanzamento e testo che il motore attuale resta operativo. Aggiornamento automatico osservato a50.593 senza comando manuale. Questa osservazione accetta soltanto la visualizzazione dell’avanzamento, non qualità, sostituzione o intero incarico. Nessuna modifica impostazioni, firma, invio o riavvio produzione. Il pannello segnala inoltre Local Signer non rispondente sul PC; segnalazione preservata, non intervenuto sul flusso congelato. Errore diagnostico del glob Windows corretto usando rg nelle directory effettive.

08/10/2026 13:50 — Controllo periodico in sola lettura: job candidato prosegue, tre lotti completati 51.928 → 52.147 → 52.332 righe, contatori219 e185 concordanti. Ultimo_id52833, totale iniziale756290, costruzione incompleta, riconvalida finale ancora richiesta; nessuna promozione, nessuna nuova scansione. Avviato riscontro SQL dei chunk attraverso il checkpoint per distinguere lacune negli ID da fonti non collegabili: conteggi sul database reale lenti, quindi non acquisita una conclusione sulle esclusioni. Sonda successiva con budget3secondi interrotta dal progress handler; query plan conferma uso della chiave primaria per il limite ID. Nessuna scrittura SQL o inferenza esterna. Verificato docker top al termine: soltanto scheduler_worker, nessuna sonda diagnostica residua. Container locale app/scheduler/OCR/pilota healthy. Riscontro esclusioni resta aperto e deve usare una sonda limitata con budget esplicito e risultato persistito, senza ostacolare i lotti. Primo tentativo cercava un nome script inesistente, corretto con inventario rg. Nessuna sostituzione completata né verifica qualitativa finale.

08/10/2026 — Due documenti nel fascicolo, prova materiale server e locale. Il lettore unico del dettaglio sostituiva l’anteprima precedente: reimpiegato ContextWorkWindows con richiesta nativa same-origin, deduplicazione URL, ripristino del documento già aperto e controllo della finestra mittente per il download. Firma/deposito/PEC preservati. Primo affiancamento server ha mostrato overflow del contenuto grid; corretto grid-template-columns:minmax(0,1fr), secondo rilascio con 267 asset HTTP200 prima del manifest e senza riavvio del container app. Visti realmente Ricorso.PDF e Documento d’identità.PDF del fascicolo 1CAA5E17 affiancati, fonte originale Contartese leggibile e scroll indipendente della carta. Prova locale8080 sul fascicolo reale controllato 2DE106E6: 01_Memoria.pdf e 02_Indice_allegati.pdf aperti, minimizzazione del primo, dock2 e Affianca ripristinano entrambi con bordi e comandi visibili. Il primo tentativo locale mostrava ancora asset vecchi nel manifest in memoria: dopo HUP e reload la seconda prova è corretta. Guardrail tecnici: build/typecheck positivi, 30 test JS documenti/limiti finestre e 7 pytest discordanza positivi. Restano verifica estesa resize/focus/responsive e consolidamento Git/locale/deploy; incarico aperto.
Discordanza nome: installato servizio nativo sul server e pubblicata puntualmente nome_cliente_atto per 1CAA5E17 da originale Ricorso.PDF verificato con impronta. Anagrafica Contarese e atto Contartese restano invariati, avviso visto in topbar. Backup SQL prima conservato anche fuori container e sul PC. Non è prova dell’estensione automatica a ufficio/RG/altri campi, ancora da implementare usando motori condivisi. Nessuna conferma falsa. Incidente diagnostico: clic su indice numerico obsoleto ha attivato Aggiorna indice Lex del solo fascicolo, con 3 errori su 14 documenti mentre la UI riepilogativa mostrava zero; difetto da diagnosticare, nessuna scansione generale e nessuna cancellazione di avvisi.
Editor nel fascicolo: in corso integrazione del wizard di redazione condiviso con contesto nativo cliente/fascicolo preimpostato, caricamento differito, archivio documenti filtrato e apertura della bozza nell’area finestre senza perdere il fascicolo. Non ancora accettato: non dichiarare produzione documentale o supporto collaborativo completo.
08/10/2026 15:50 — Lettura anagrafica: prova reale locale sul documento Marchetti A1FB22FE. Recupero puntuale nella pipeline SQL nativa quando manca il testo corrente; primo tentativo ha esposto permessi root sul solo archivio documenti_ai del caso, corretti al proprietario applicativo senza alterare gli originali. Indicizzato un solo documento, nessun errore, versione2. Separati carta cartacea e tessera sanitaria, evitando la scadenza sanitaria come scadenza della carta. Visti nella UI nome, cognome, CF valido, nascita, numero carta, Comune emittente, rilascio e scadenza. Per l’indirizzo incerto della scansione riusate letture SQL correnti del solo fascicolo con CF/nome/nascita concordanti, due impronte diverse e verifica dei byte originali: Strada di Saviabona, civico256, Vicenza. Fonti1/2 presenti e Fonte2 aperta realmente nel lettore Contratto24-25.pdf con indirizzo visibile. Nessuna scrittura persistente della scheda cliente. Miglioramenti grafici diagnostici 300/450dpi, contrasto, Tesseract e regioni automatiche non hanno dimostrato da soli la via e non sono stati promossi a certezza; recupero grafico professionale integrato, audit tentativi, salvataggio/CAS e discordanza completa restano aperti.
08/10/2026 15:50 — CIE Rilasciato da: origine del difetto etichetta bilingue inline COMUNE DI/ MUNICIPAUTY ROMBIOLO non coperta dal parser. Primo hotfix assumeva righe separate e non ha compilato il campo; corretta la regola sulle effettive righe archiviate senza modificare il nome del Comune. Visti originali CIE e comando Leggi documento server: Comune di Rombiolo compilato. Copia locale8080 ha diverso collegamento cliente/caso: richiesta respinta correttamente, nessun link forzato; scaricato lo stesso originale con comando nativo e riletto in memoria tramite Carica documento, Comune di Rombiolo compilato anche in locale. Nessun salvataggio DB del cliente effettuato. Screenshot cie-issuer-server-20261008.png e cie-issuer-local-20261008.png fuoriGit. Undici guardrail tests/test_client_document_reader.py positivi. Backup server cie-issuer-20261008_154650 e _154757, installato stesso file SHA72615fedb92db7f0300e0780dd338570c6c6e06f74422cb228e39a1257f43aae. HUP worker, nessun riavvio app né volume modificato. Versioni runtime locale2.436.10/server2.436.11 ancora da consolidare; commit/push/deploy richiesti dopo questa tranche, incarico generale resta aperto.
08/10/2026 — Pre-consolidamento richiesto: salvati68sorgenti WIP Hetzner e seconda copia server-wip-before-consolidation-20261008.tar.gz fuoriGit. Confronto normalizzato: recuperati testo OCR con annotazioni FreeText/limite rasterizzazione, sorgenti card economica/provenienza, EconomicVerificationPanel e fascicoliData; mantenuti i correttivi locali più recenti di identità ruolo completo, delimitazione ufficio, audit leggibile e singolare ricerca, invece delle versioni server antecedenti. npm test190positivi più contratti/hook/presìdi/preset/design system/Storybook/UI coverage positivi; prima tentativi hanno esposto attributo HTML autocomplete come falsa credenziale e governance di CSS/geometry OCR non aggiornata, corretti in modo puntuale mantenendo controlli sui payload. Nessuna modifica al PIN o al flusso congelato. Build/typecheck positive3,8secondi Vite.110guardrail backend fatture/SdI/PEC/archivio/job/embedding/fonti positivi;23guardrail lettore/discrepanze/catalogo positivi. Primo comando pytest aveva percorso JS inesistente come .py: nessun test eseguito in quel tentativo, corretto elenco. Versione2.436.12 preparata per consolidamento, non ancora distribuita sullo stesso commit. Rilascio finale e prove globali ancora aperti; nessuna conclusione globale.
