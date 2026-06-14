# Incarico operativo permanente: dati, tenant, React e topbar

Ultimo aggiornamento: 2026-06-14.

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
- Studio: `Studio`, `Parcelle e Fatture`, `Preventivi e Incarichi`, `Compensi Forensi`, `Documenti`, `Redazione Atti`, `Statistiche`, `Ricerca Legale`, `Legal Skills`, `Regia Agentica`, `Archivio Giurisprudenza`, `Strumenti Forensi`, `Strumenti Operativi`;
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

I JSON non devono restare l'unica fonte operativa quando il flusso è strutturato. Vanno indicizzati nel tenant `studio.db` tramite `moduli_dati` e `moduli_json_records`; i domini core devono avere anche tabella verticale SQLite e parità PostgreSQL.

Il controllo permanente vive in:

- `pct/data_flow_contract.py`;
- `scripts/audit_data_flow_contract.py`;
- `tests/test_data_flow_contract.py`.

Il comando operativo è:

```powershell
python scripts/audit_data_flow_contract.py --registry data/tenants.json --repair-json-mirror --repair-search-index --json
python scripts/audit_data_flow_contract.py --registry data/tenants.json --json
```

Il primo comando può riparare solo parti rigenerabili: mirror SQL `moduli_json_records` e indice di ricerca `search_documenti`. Non deve toccare dati principali come fascicoli, clienti, agenda, scadenze, documenti o comunicazioni. Il secondo comando è il controllo a freddo senza riparazioni e deve restare verde prima di parlare di struttura dati coerente.

## Stato attuale della tranche

- Fatto a livello codice: contratto applicativo dati/tenant/route React/topbar/sottomenu in `pct/data_flow_contract.py`.
- Fatto a livello codice: parità core PostgreSQL e migrazione per messaggi, privacy, notifiche, backup e time tracking.
- Fatto a livello script: `scripts/audit_data_flow_contract.py` diagnostica `studio.db`, mirror JSON e indice FTS e ripara solo cache rigenerabili quando l'opzione è esplicita.
- Fatto su tenant locale reale il 2026-06-14: audit `tenant-8bf98719c459` con `quick_check=ok`, `moduli_json_records` leggibile con 3734 record e `search_documenti` leggibile dopo riparazione FTS; la riparazione non ha modificato tabelle core.
- Fatto su macchina reale locale il 2026-06-14, versione `2.253.24`: perimetro `Studio` verificato in Chrome visibile su `127.0.0.1:8080`, con apertura e scroll di `/studio`, `/fatturazione`, `/preventivi`, `/compensi-forensi`, `/documenti`, `/redazione-atti`, `/statistiche`, `/ricerca-legale`, `/legal-skills`, `/workflow-agents`, `/giurisprudenza`, `/strumenti-legali`, `/strumenti-operativi`; tutte le route hanno `#root`, menu Studio completo e nessun fallback `?_legacy=1`.
- Fatto su macchina reale locale il 2026-06-14, versione `2.253.24`: topbar verificata su Studio per `Voce Studio`, `Timer attività`, data italiana, `Scadenze rapide`, `Ultimi elementi aperti`, `Notifiche operative`, `Nuovo` e `Assistenza remota`; la sessione assistenza creata dal test è stata chiusa come `Chiusa`.
- Fatto a livello codice e verificato su macchina reale locale il 2026-06-14, versione `2.253.25`: l'icona `Recenti` della topbar è stata estesa a `Recenti e ricerche`; il badge ora somma elementi aperti e ricerche recenti, il pannello mostra sezioni distinte `Elementi aperti` e `Ricerche recenti`, e la nuova API protetta `/api/recent/search` registra query deduplicate collegate a `/global-search?q=...`. Prova reale eseguita in Google Chrome visibile su `127.0.0.1:8080`: ricerca `RG`, apertura `/fascicoli/8804C177`, ritorno a `/studio`, pannello `Recenti e ricerche (2)` con `items=1`, `searches=1`, `totalCount=2`, nessun errore console.
- Da fare prima di qualunque chiusura complessiva: verifica reale anche delle altre macro-aree e sottomenu, commit, push branch gemelli, controlli GitHub/CodeQL e deploy Hetzner.

## Regola deposito e flussi sensibili

Per deposito telematico, fascicoli, PEC, notifiche legali, portali, Local Signer e firma digitale resta obbligatorio aggiornare anche `artifacts/react-migration/procedura-deposito-telematico.md`. Il software deve preparare ciò che può preparare subito, spiegare cosa manca, bloccare solo requisiti obbligatori e non registrare come deposito valido un pacchetto ministeriale non conforme.

## Regola anti falso-verde

Un test automatico verde non significa lavoro concluso. Per qualsiasi comportamento visibile serve prova reale sulla macchina dell'utente. Se non è stata eseguita, il report deve dire chiaramente: non verificato su macchina reale.
