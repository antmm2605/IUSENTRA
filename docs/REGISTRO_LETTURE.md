# Registro delle letture

Aggiornato: 21/09/2026 (tranche 2.342.0).


## Riconciliazione dei motori e apertura fascicolo (2.342.0)

Il registro è la fonte centrale per i consumer delle letture. Per questo motivo
sono stati sospesi con audit undici job periodici derivativi che duplicavano
funzioni già alimentate dagli eventi; restano attivi i consumer necessari alla
consegna Agenda/Scadenziario e PEC, oltre a ricezione, sicurezza e backup. Dodici
run orfani sono stati riconciliati solo quando esisteva la coppia terminale con
lo stesso job e orario pianificato: nessun run ancora aperto è stato trasformato
in completato senza prova.

Le GET del fascicolo e del registro leggono lo stato persistito e non avviano
motori. L'apertura del fascicolo riusa il repository mirato e il controllo
sentenze economiche non ricarica l'archivio completo. Il GET letture usa il
loader singolo; il lavoro parte dagli eventi di importazione o modifica e dal
worker governato. Il tempo isolato del percorso economico è passato da 1,864 a
1,377 secondi. I vecchi GET da 64 a 121 secondi e i 503 di upstream restano
aperti come verifica di produzione: questo documento non li dichiara risolti.

Il pilot SQL del catalogo ha coperto 33 fascicoli e 319 embedding dopo la
riparazione del confine di validità; l'invariante osservato è 6,951 secondi con
zero letture catalogo/RAG. Due sorgenti PEC sono state migrate al segnale di
revisione e due EML binari sono stati riacquisiti preservando gli originali.
Il pilot Docling ha coperto cinque documenti reali con OCR spento; il gate
MiniCPM resta limitato al pilot, Gemma non è stato modificato e il batch di dieci
documenti sequenziali non è ancora stato lanciato.

Restano aperti il contaminante legacy RAG globale da 12 GB, 28 orfani OCR e gli
errori storici non ancora applicati, oltre al riallineamento commit/locale, alla
campagna visuale e all'accettazione finale della candidata produzione 2.342.0.
Il flusso deposito/firma/PEC congelato il 09/09/2026 non è stato toccato.

## Che cosa fa

Il gestionale legge i documenti e le PEC del fascicolo con più lettori: il testo
per la ricerca (OCR), l'indice documentale per Lex e il catalogo dal contenuto,
l'assistente locale (RAG), il presidio PEC sugli allegati, il presidio economico,
la proforma automatica, la lettura del fascicolo. Prima ognuno decideva da solo
se rileggere, e alcuni rileggevano sempre: l'indice documentale decifrava e
ricalcolava l'impronta di tutti i documenti a ogni apertura del fascicolo, la
proforma automatica rileggeva i PDF dal disco ogni quindici minuti.

Il registro delle letture (`pct/registro_letture/`) è la memoria comune:

- **inventario** degli oggetti del fascicolo — documenti, PEC collegate, allegati
  PEC — con impronta SHA-256 del contenuto, nome, dimensione, origine, data e le
  chiavi di associazione: nome e cognome del cliente, numero e anno di ruolo;
- **letture**: per ogni oggetto e per ogni lettore, l'impronta letta, la versione
  del lettore, lo stato (`letto`, `in_corso`, `errore`, `non_leggibile`), l'esito;
- **impronta del fascicolo** per lettore: se l'inventario è lo stesso dell'ultimo
  giro completo, il lettore non guarda nemmeno i documenti;
- **viste** per utente: che cosa è nuovo o cambiato dall'ultima apertura;
- **anomalie**: i dati letti che i controlli deterministici giudicano dubbi
  (date in primis), con motivo, gravità, valore proposto, stato
  (`aperta`, `confermata`, `corretta`, `ignorata`).

Un documento invariato non si rilegge. Cambia l'hash, si rilegge solo quello.
Cambia la versione di un lettore (nuovo motore OCR, nuovo risolutore del
catalogo), torna da leggere tutto per quel lettore soltanto.

## Dove sta

`REGISTRO_LETTURE_DB` = `/data/tenants/<studio>/intelligence/registro_letture.db`
(SQLite tenant-aware); PostgreSQL con `IUSENTRA_REGISTRO_LETTURE_DSN` o il
database del tenant. Schema gemello in `pct/sql/20260915_registro_letture.sql` e
`_postgres.sql` (tabelle `letture_oggetti`, `letture`, `letture_fascicoli`,
`letture_viste`, `letture_anomalie`; contratto verificato dal test).

## Chi lo usa

| Lettore | Dove consulta e scrive il registro |
| --- | --- |
| Testo e ricerca (OCR) | `web/services/ocr_runtime.py` rifiuta di accodare un documento già letto con la stessa impronta; `pct/ocr_worker.py` segna l'esito, estrae le date e registra le anomalie |
| Indice documentale | `pct/document_intelligence/sources.py` non decifra i documenti di cui il registro conosce l'impronta in chiaro; `web/services/document_intelligence_runtime.py` salta l'elaborazione se l'impronta del fascicolo è invariata e segna documenti e fascicolo |
| Catalogo dal contenuto | stato derivato dall'indice (stessa impronta) |
| Assistente locale (RAG) | `pct/local_ai.py` segna gli esiti (`indexed`, `skipped`, `unsupported`) tramite `service.registro_letture` |
| Presidio PEC | `pct/pec_pipeline.py` riusa l'OCR di un allegato con la stessa impronta già letto nello studio; il runtime allinea gli allegati letti e verifica udienze e termini rispetto alla PEC |
| Presidio economico | il marcatore `_presidio_documentale` è specchiato nel registro |
| Proforma automatica | `_ensure_auto_proforma_for_fascicolo` non rilegge i PDF se l'inventario è invariato |
| Lettura del fascicolo | cache breve invalidata da documenti e PEC (`web/services/lettura_cache.py`); pannello «Letture e verifiche» |

Eventi che aggiornano l'inventario: caricamento, sostituzione (editor),
ripristino, rinomina, cestino, eliminazione definitiva di un documento; PEC
collegata dalla lettura. Ogni evento invalida la lettura del fascicolo in cache.

## Verifica delle letture

`pct/registro_letture/verifica_date.py` giudica ogni data letta: calendario,
orizzonte del fascicolo (anno di ruolo, apertura), futuro oltre tre anni,
coerenza con un'altra fonte (data di deposito del portale, data di ricezione
della PEC), giorno e mese invertiti, lettere lette al posto delle cifre. Le
confusioni tipiche dell'OCR sono dichiarate una volta sola in
`legal_ocr/formulario/confusioni.py` e usate da date, cifre, codice fiscale,
partita IVA, CAP, IBAN, numero di ruolo e parole. Il presidio documentale
(`pct/fascicolo_document_presidio.py`) legge le date normalizzate e applica le
correzioni dell'avvocato; il runtime verifica le udienze e i termini letti dalle
PEC. Le anomalie compaiono nel pannello «Letture e verifiche» del fascicolo con
«È giusto», «Correggi», «Ignora».

## API

- `GET /api/v1/ui/fascicoli/<id>/letture` — stato per lettore e per oggetto,
  novità dall'ultima apertura (registra la vista), anomalie aperte.
- `POST /api/v1/ui/fascicoli/<id>/letture/aggiorna` — legge solo ciò che manca.
- `POST /api/v1/ui/fascicoli/<id>/letture/anomalie/<anomalia_id>` —
  `{"esito": "confermata|corretta|ignorata", "valore": "gg/mm/aaaa"}`.

## Archivio di alimentazione (2.317.0)

Due motori leggono, i presìdi consultano. Il **motore documenti**
(`pct/archivio_letture/motore_documenti.py`) legge il testo di ogni documento
del fascicolo — nativo dal PDF, OCR dalla cache dell'indice di ricerca, indice
documentale — ed estrae i *fatti*: date con il loro campo (udienza, termine,
costituzione, notifica, deposito, accettazione, consegna, comunicazione,
provvedimento, data dell'atto), numeri di ruolo, prove di notifica (relata,
ricevuta di accettazione, ricevuta di avvenuta consegna, attestazione di
conformità, atto notificato, comunicazione di cancelleria, deposito della
prova). Il **motore PEC** (`motore_pec.py`) traduce ciò che il presidio PEC ha
già letto (udienze, termini, eventi, ricevute riconosciute dall'oggetto
certificato dal gestore) e legge gli allegati con il motore documenti.

Una data è un fatto solo se è **vera** (formulario stretto: correzione O/l/S/B/Z
solo se ne esce una data del calendario con almeno metà dei segni già cifre),
**ancorata** (il testo dice che cos'è: «udienza del», «entro il», «notificato
il», «ricevuta di avvenuta consegna … ore»; un'ancora vale per la prima data che
la segue, mai per una tabella; date di nascita, documenti d'identità,
protocolli, versioni, periodi «dal…al» e date di leggi sono ancore negative) e
supera il **collaudo** (`collaudo.py`): calendario, forma, ancoraggio,
orizzonte del fascicolo, doppia lettura (la stessa data in una seconda
estrazione indipendente dello stesso documento), concordanza con agenda,
scadenziario, PEC del presidio e portale. Verdetto del software: `verificata`
(riscontro indipendente o origine non ottica senza correzioni), `plausibile`
(ben formata e ancorata, nessun riscontro: le sole udienze e termini plausibili
vengono chiesti in conferma nel pannello), `respinta` (smentita: resta
nell'archivio con le prove, non si propone). L'avvocato può rendere un fatto
`corretta` o `ignorata`: la decisione sopravvive alle riletture dello stesso
contenuto (`POST /api/v1/ui/fascicoli/<id>/letture/fatti/<fatto_id>`).

Tabella `letture_fatti` (stesso database del registro, schema gemello
SQLite/PostgreSQL; `pct/registro_letture/fatti_repository.py`). I lettori
`motore_documenti` e `motore_pec` sono censiti nel registro: un oggetto già
letto con la stessa impronta non si rilegge; cambia il contenuto o la versione
del motore, si rilegge solo quello.

**Chi alimenta**: la lettura automatica dello scheduler («Lettura automatica dei
fascicoli», ogni 10 minuti, `IUSENTRA_ARCHIVIO_LETTURE_LIMITE` oggetti per giro,
prima i fascicoli aperti; a fascicolo invariato non fa nulla); il caricamento o
la sostituzione di un documento e il collegamento di una PEC (thread di sfondo,
mai nella richiesta); il worker OCR a testo pronto; le verifiche automatiche
all'apertura della Lettura; «Leggi i nuovi». **Chi consuma**: il presidio
documentale (udienze e termini dall'archivio, senza rileggere i testi), il
presidio notifiche (relata, ricevute, atto notificato riconosciuti nel
contenuto e non solo nel nome del file), la Lettura del fascicolo (sezione
`archivio`), il pannello «Letture e verifiche».

**Collaudo del lettore** (`legal_ocr/collaudo/`): un corpus di pagine di prova
(decreto di fissazione, relata con dati anagrafici e documento d'identità,
comunicazione con tabella di date e protocolli) viene renderizzato e letto con
l'OCR reale ogni notte (job «Collaudo del lettore», 04:10) e a ogni esecuzione
dei test; l'esito (`intelligence/collaudo_lettore.json`) compare nel pannello.
Se il collaudo non passa, il pannello lo dice: non è l'avvocato a dover
controllare il lettore.

## Riconvalida e conferme mirate (2.318.0)

**Riconvalida** (`pct/registro_letture/riconvalida.py`). Le regole di lettura si
stringono nel tempo: quando una regola nuova stabilisce che un testo non è una
data, le anomalie e i fatti che quella lettura aveva già prodotto restano
registrati e continuano a chiedere conferme che il software non chiederebbe
più. A ogni giro di lettura (`web/services/archivio_letture_runtime._riconvalida`)
le anomalie **aperte** si ripassano con le regole correnti: quelle che oggi non
nascerebbero si chiudono da sole con il motivo che dichiara la regola superata e
l'autore «riconvalida automatica»; la riga resta nel registro, perché la
chiusura è tracciata e non cancellata (art. 20 CAD). I fatti dell'archivio che
oggi si riconoscono come riferimenti normativi vengono respinti, con la prova
`riconvalida`. Le decisioni dell'avvocato (`confermata`, `corretta`,
`ignorata`) non si toccano mai.

**Conferme mirate** (`pct/archivio_letture/presidi.da_confermare_ora`). Si chiede
conferma solo per le date che, confermate, cambiano qualcosa: udienze, termini e
costituzioni **future**, una volta sola per data. Una data già passata non si
chiede — l'udienza si è tenuta, il termine è scaduto — e una data d'atto o di
documento non produce alcuna azione. Le lacune della Lettura del fascicolo dicono
*quali* date attendono conferma e *quale* oggetto la lettura automatica deve
ancora leggere, con il motivo.

**Nessun oggetto resta in attesa per sempre.** Un oggetto dell'inventario che non
corrisponde più a un documento del fascicolo o a una PEC collegata veniva saltato
a ogni giro e restava «da leggere» all'infinito. Ora la sua lettura si chiude
come `non_leggibile` con il motivo («documento non più presente nel fascicolo»,
«messaggio PEC non più collegato al fascicolo», «allegato non più presente nella
PEC collegata») e il pannello elenca gli oggetti ancora in attesa
(`lettura_automatica.in_attesa`) con il motore che li aspetta e il perché.

Test: `tests/test_registro_letture.py`, `tests/test_registro_letture_runtime.py`,
`tests/test_archivio_letture.py`, `tests/test_archivio_letture_runtime.py`,
`tests/test_riconvalida_letture.py`, `tests/test_collaudo_lettore.py`,
`tests/js/letture_fascicolo.test.mjs`.

## Il ciclo e la consegna ai presìdi (2.319.0)

**Il ciclo** (`pct/archivio_letture/ciclo.py`). La lettura non è un lavoro
continuo: è un ciclo con tre stati dichiarati.

| Stato | Quando | Che cosa fa il software |
|---|---|---|
| `fermo` | tutto letto, impronta del fascicolo uguale a quella confermata dall'archivio, versione dei motori invariata | nulla: non apre un file, non allinea l'inventario, non tocca il disco |
| `da_leggere` | un documento nuovo o cambiato, una PEC arrivata, una versione di motore diversa, un fascicolo mai letto | i due motori leggono **solo** gli oggetti nuovi o cambiati e scrivono i fatti nell'archivio |
| `in_errore` | l'ultimo giro non è riuscito | il fascicolo resta dichiarato con il motivo e il giro successivo riprende |

L'impronta si calcola dal fascicolo vivo (identificativi, hash e dimensioni che
i documenti già portano), non dal registro: confrontare il registro con se
stesso direbbe sempre «invariato». Un ricontrollo periodico (`RICONCILIAZIONE_ORE
= 24`) riesamina anche i fascicoli fermi, perché un evento perso non lasci un
fascicolo indietro per sempre.

**La fusione canonica** (`pct/archivio_letture/deduplica.py`). I fatti grezzi
restano nel registro per audit, ma prima di arrivare ai presìdi vengono fusi:
se documento e PEC riportano la stessa udienza, lo stesso termine, la stessa
prova o lo stesso importo, i presìdi ricevono un solo fatto canonico con tutte
le fonti nelle prove. Questo evita che due letture equivalenti producano due
righe operative.

**Fonti normative e procedurali**. Ogni fatto collaudato porta anche una prova
`base_normativa` e una prova `procedura`: i presìdi non ricevono solo il dato,
ma anche la base digitale usata per governarlo e il riferimento alla procedura
interna del registro. Le PEC aggiungono, quando pertinente, la base normativa
specifica della ricevuta o del termine comunicato.

**La consegna** (`pct/archivio_letture/distribuzione.py`, tabella
`letture_consegne`). L'archivio sa quali presìdi usano quali fatti, li offre una
volta sola e tiene il conto di che cosa il presidio ne ha fatto: `consegnato`
con il riferimento della riga creata, `non_pertinente`, `rifiutato` con il
motivo (torna al giro dopo). Un fatto consegnato non viene più riproposto: è
questa contabilità che impedisce i doppioni.

Si consegnano solo i fatti `verificata` e `corretta`: un fatto soltanto
`plausibile` si chiede nel riquadro delle conferme, non si scrive.

| Presidio | Prende | Modo |
|---|---|---|
| Scadenziario | date di `termine` e `costituzione` | **scrive** una scadenza da confermare |
| Agenda | date di `udienza` | **scrive** un appuntamento |
| Calendario | date di `udienza`, `termine`, `costituzione` | consulta agenda e scadenziario alimentati dall'archivio |
| Presidio notifiche | `prova_notifica` | consulta |
| Presidio del fascicolo | date, ruoli, prove di notifica, eventi | consulta |
| Catalogo documentale fascicolo | date, ruoli, prove di notifica, importi | consulta |
| Presidio economico | `importo` | consulta |
| Contesto economico | `importo`, `evento` | consulta |
| Fatture e proforme | `importo` | consulta |
| Dati del fascicolo | `ruolo` | consulta |
| Lettura del fascicolo (cronologia) | `evento` | consulta |
| Lettura fascicolo | date, ruoli, prove di notifica, importi, eventi | consulta |
| Presidio documentale | date di udienza, termine, costituzione, provvedimento, notifica | consulta |

Un presidio nuovo si censisce aggiungendo una riga: senza riga non riceve
nulla, ed è voluto — nessun dato raggiunge una superficie che non lo ha
dichiarato. All'opposto, **nessuna categoria prodotta dai motori può restare
senza un presidio che la usa**: `categorie_senza_presidio()` lo misura e un test
lo impedisce, perché un motore che legge un dato che nessuno mostra lavora per
niente.

**Autocontrollo sui dati veri**. Sul server, non con dati inventati:

    docker compose exec app python scripts/verifica_catena_letture.py
    docker compose exec app python scripts/verifica_catena_letture.py --fascicolo <ID>

Riporta se il registro si apre, dove sta il ciclo di ogni fascicolo e perché,
che cosa hanno scritto i motori per categoria e verdetto, quanto ogni presidio
ha preso e quanto gli resta, quali categorie nessun presidio usa.
