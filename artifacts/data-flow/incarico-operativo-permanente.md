# Incarico operativo permanente: dati, tenant, React e topbar

Ultimo aggiornamento: 2026-06-16.

Questo file va riletto dopo ogni compattazione insieme ad `AGENTS.md` prima di riprendere lavori su IUSENTRA. L'incarico dell'utente non riguarda un singolo pulsante: riguarda la chiusura dell'applicativo come sistema unico, con dati coerenti, route full React, tenant corretto e controlli reali.

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

## Regola anti falso-verde

Un test automatico verde non significa lavoro concluso. Per qualsiasi comportamento visibile serve prova reale sulla macchina dell'utente. Se non è stata eseguita, il report deve dire chiaramente: non verificato su macchina reale.
