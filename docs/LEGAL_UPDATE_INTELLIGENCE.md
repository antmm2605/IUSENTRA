# IUSENTRA Update Intelligence

## Obiettivo

Il motore di aggiornamento giuridico di IUSENTRA monitora fonti ufficiali e istituzionali, acquisisce contenuti nuovi o aggiornati, li normalizza, li classifica con supporto AI, li confronta con l'archivio interno e pubblica automaticamente cio' che e' utile allo studio legale quando supera i controlli di fonte, duplicazione e confidenza.

Il flusso operativo reale e':

1. `fonti -> fetch`
2. `acquisizione raw`
3. `normalizzazione`
4. `analisi AI + classificazione`
5. `matching con archivio interno`
6. `controllo utilita' per studio legale`
7. `coda revisioni o pubblicazione automatica`
8. `audit e storico`

## Fonti iniziali

Il seed iniziale include:

- Gazzetta Ufficiale
- Normattiva
- dati.normattiva.it
- Codice civile, procedura civile, penale, procedura penale, processo amministrativo e codice della strada tramite Normattiva
- Corte costituzionale
- Cassazione Massimario
- Cassazione - citazioni e principi verificati
- Giustizia Amministrativa
- OpenGA Giustizia Amministrativa
- OpenGA - Calendario udienze
- EUR-Lex
- Agenzia delle Entrate
- Ministero del Lavoro

Le fonti sono classificate per `trust_class`:

- `A`: fonte ufficiale primaria
- `B`: fonte istituzionale ufficiale
- `C`: fonte editoriale specialistica
- `D`: fonte non utilizzabile per aggiornamento strutturale

## Regole decisionali

Il motore usa classi chiuse:

- `NORMATIVA_NUOVA`
- `NORMATIVA_AGGIORNAMENTO`
- `GIURISPRUDENZA`
- `PRASSI`
- `NEWS`
- `COMMENTO`
- `DUPLICATO`
- `INCERTO`

Azioni possibili:

- `NEWS_ONLY`
- `NEW_NORMATIVE`
- `UPDATE_NORMATIVE`
- `NEW_CASE_LAW`
- `NEW_PRASSI`
- `DUPLICATE`
- `OUT_OF_SCOPE`
- `NEEDS_REVIEW`

Policy operative:

- prima di creare una proposta il motore confronta il contenuto con archivio strutturato e news gia' pubblicate
- sentenze, ordinanze, norme, prassi e news gia' presenti vengono chiuse come duplicato e non ripubblicate
- i contenuti fuori perimetro professionale dello studio legale vengono chiusi come `OUT_OF_SCOPE`
- norme, giurisprudenza, prassi e news da fonti ufficiali o istituzionali possono essere pubblicate automaticamente quando la classificazione e' sufficientemente affidabile e la verifica pubblica governata trova conferme coerenti
- per le proposte strutturate (`NEW_NORMATIVE`, `UPDATE_NORMATIVE`, `NEW_CASE_LAW`, `NEW_PRASSI`) servono almeno una fonte primaria e una seconda conferma da archivio fonti ufficiali, Normattiva, Gazzetta o ricerca web allowlist
- ogni aggiornamento normativo crea storico tramite `normative_versions`
- nessun contenuto editoriale secondario aggiorna da solo l'archivio normativo

## Storage e moduli

Il motore usa un archivio SQLite dedicato e condiviso di piattaforma, derivato
dal `LEGAL_INTELLIGENCE_DB` applicativo:

- database operativo: `legal_updates.db`
- export amministrativo opzionale: `legal_updates_repository.json`

`legal_updates.db` e' la sorgente di verita' condivisa per fonti, documenti
raw, analisi AI, review, news, normativa, giurisprudenza, prassi e audit. Lex
AI legge questo repository SQL tramite `LegalUpdatesSource` e tramite la sezione
di contesto `Aggiornamenti legali`; non usa `legal_updates_repository.json` come
sorgente runtime.

Il JSON resta solo un export manuale/diagnostico abilitabile esplicitamente. Anche il mirror legacy `giurisprudenza.json` e' disattivato di default: le pubblicazioni giurisprudenziali prodotte dal motore restano nella tabella SQL `jurisprudence` e vengono recuperate da Lex da li'.

Moduli principali:

- [pct/legal_update_repository.py](/D:/legale/IUSENTRA/pct/legal_update_repository.py)
- [pct/legal_update_ai.py](/D:/legale/IUSENTRA/pct/legal_update_ai.py)
- [pct/legal_update_pipeline.py](/D:/legale/IUSENTRA/pct/legal_update_pipeline.py)

## Note operative importanti

- La pagina `/admin/aggiornamenti-legali/staging` avvia una riconciliazione automatica prima di mostrare la lista: elementi gia' pubblicati vengono chiusi come duplicati, cataloghi/dataset tecnici non pubblicabili vengono archiviati e contenuti ufficiali utili ma non abbastanza strutturati vengono degradati a notizia informativa pubblicabile.
- Le fonti HTML non vengono piu' limitate artificialmente a 40 risultati: il fetch segue anche la paginazione dei portali che espongono piu' pagine tramite query string o script lato pagina.
- Le fonti CKAN JSON di OpenGA vengono lette come catalogo strutturato: IUSENTRA importa pacchetti, risorse e, per le risorse JSON disponibili, un estratto del contenuto utile a Lex e alla ricerca interna.
- Il seed `dati_normattiva` punta alla pagina ufficiale Normattiva OpenData richiesta, cosi' la fonte resta governata dal canale informativo pubblico corretto.
- I codici fondamentali sono presidiati come fonti Normattiva autonome (`codice_civile`, `codice_procedura_civile`, `codice_penale`, `codice_procedura_penale`, `codice_processo_amministrativo`, `codice_strada`) per coprire ricerche su famiglia, contratti, responsabilita', danno, notifiche/PEC, termini, decreto ingiuntivo, circolazione stradale e processo.
- Il canale `cassazione_citazioni_verificate` serve a separare citazioni e massime verificabili da semplici news: Lex deve mantenere `Da verificare` quando mancano numero, data, sezione, testo o conferma ufficiale.
- La pubblicazione automatica interroga anche [pct/legal_update_web_verification.py](/D:/legale/IUSENTRA/pct/legal_update_web_verification.py): se le conferme pubbliche non bastano, la proposta resta in revisione con nota leggibile per il revisore.
- La deduplica usa sia `external_id` di acquisizione sia una chiave canonica di archivio: numero/anno/autorita' per sentenze e ordinanze, tipo/numero/anno/emittente per norme e prassi, URL ufficiale e titolo/data per le news.
- La console admin espone `Pulisci duplicati`; la stessa pulizia viene eseguita anche prima delle scansioni automatiche e manuali.
- `Pubblica idonei` non si ferma piu' su uno slug normativo gia' presente: il repository riusa il record esistente quando lo riconosce, genera slug univoci quando serve e registra eventuali elementi saltati senza bloccare l'intero autopublish.
- [web/blueprints/legal_updates_admin.py](/D:/legale/IUSENTRA/web/blueprints/legal_updates_admin.py)
- [web/blueprints/legal_intelligence.py](/D:/legale/IUSENTRA/web/blueprints/legal_intelligence.py)

## CLI

Scansione manuale:

```bash
iusentra aggiornamenti-legali
```

Scansione di fonti specifiche:

```bash
iusentra aggiornamenti-legali --source gazzetta_ufficiale --source normattiva
```

Pubblicazione automatica delle review gia approvate:

```bash
iusentra aggiornamenti-legali --publish-approved
```

Pulizia archivio senza nuova scansione:

```bash
iusentra aggiornamenti-legali --cleanup-only
```

Export amministrativo opzionale:

```bash
iusentra aggiornamenti-legali --export-json
```

Mirror legacy opzionale, da usare solo per compatibilita' controllata:

```bash
iusentra aggiornamenti-legali --mirror-giurisprudenza-json
```

## Scheduler

Job pianificati:

- Archivi Normattiva e Gazzetta: ore 23:00
- Gazzetta Ufficiale: ore 23:10
- Batch principale di tutte le fonti con timeout per fonte/pubblicazione: ore 23:15
- Agenti Lex operativi per inventario studio: ore 01:20

La fascia notturna evita carico operativo durante l'uso quotidiano e consente di pubblicare automaticamente i nuovi contenuti idonei prima dell'avvio della giornata di studio.

La UI amministrativa dedicata e' in:

- `/admin/aggiornamenti-legali`
- `/admin/aggiornamenti-legali/fonti`
- `/admin/aggiornamenti-legali/staging`
- `/admin/aggiornamenti-legali/analisi`
- `/admin/aggiornamenti-legali/archivio`
- `/admin/aggiornamenti-legali/review`

La UI utente dedicata e' in:

- `/legal-intelligence/news`

La UI admin rende visibili tutti i blocchi della pipeline:

- `fonti` -> gestore fonti, frequenze, parser, acquisizione mirata
- `acquisizione` -> documenti grezzi e normalizzati con stato revisione
- `analisi` -> classificazione AI, materia, confidenza e azione proposta
- `archivio` -> normative, giurisprudenza, prassi, news e audit
- `review` -> approvazione, rifiuto, modifica e pubblicazione

## Governance multi-studio

Nel modello professionale di piattaforma:

- il `SUPERADMIN` e' unico e governa gli studi dalla console piattaforma
- il `SUPERADMIN` ha una superficie dedicata `admin/utenti-piattaforma` e non appartiene a nessun tenant
- gli studi non possono creare utenti `SUPERADMIN`
- il `SUPERADMIN` usa la persistenza auth di piattaforma anche quando gli studi girano su SQL locale o PostgreSQL tenant-aware
- la console `Aggiornamenti legali` non seleziona piu' uno studio: fetch, review, archive e publish operano sull'archivio legale condiviso da tutti gli studi
- la pagina `/admin/aggiornamenti-legali/fonti` governa una sola lista fonti per tutta la piattaforma, evitando scansioni duplicate per ogni studio
- i dati privati di studio restano tenant-aware negli altri domini; solo fonti e aggiornamenti legali pubblici sono condivisi

## Compilazione corretta delle fonti

Nella pagina `/admin/aggiornamenti-legali/fonti` e' presente una guida fissa ai campi del form. Le regole operative sono:

- `name`: nome leggibile del canale o della sezione
- `code`: identificatore tecnico stabile, solo minuscolo, senza spazi, con underscore
- `category`: usare preferibilmente `normativa`, `giurisprudenza`, `prassi`, `ue`, `news`
- `base_url`: deve appartenere davvero all'ente indicato nel nome
- `polling_minutes`: frequenza di scansione in minuti
- `parser_type`: nel dubbio lasciare `html`
- `trust_class`: `A` primaria, `B` istituzionale, `C` editoriale
- `source_type`: attualmente quasi sempre `web`
- `is_official`: da attivare solo per fonti ufficiali o istituzionali

Esempi corretti:

- Corte Costituzionale -> `corte_costituzionale` -> `https://www.cortecostituzionale.it/`
- Cassazione Massimario -> `cassazione_massimario` -> `https://www.cortedicassazione.it/`
- Cassazione - Terza Sezione Civile -> `cassazione_terza_sezione_civile` -> `https://www.cortedicassazione.it/it/terza_sezione_civile.page`
- Giustizia Amministrativa -> `giustizia_amministrativa` -> `https://www.giustizia-amministrativa.it/`

Regola di coerenza obbligatoria: nome fonte e URL devono riferirsi allo stesso ente. Un URL Cassazione non va salvato con il nome `Corte Costituzionale`.

## Sicurezza e qualita'

- la fonte originale resta sempre salvata
- i contenuti sono deduplicati via `external_id` e `content_hash`
- ogni pubblicazione produce audit
- le relazioni strutturate non sovrascrivono lo storico
- la tassonomia materie e' chiusa e governata
