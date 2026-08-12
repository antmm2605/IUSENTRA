# Audit download ReGIndE PST - 25/07/2026

## Fonte controllata

- Pagina PST: `https://servizipst.giustizia.it/PST/it/pst_2_2.wp`
- Area: Registro Generale degli Indirizzi Elettronici, form `Ricerca nel Registro`.
- Ora di acquisizione: 25/07/2026, circa 22:24-22:27, fuso `Europe/Rome`.

## Dati scaricati in JSON

- `artifacts/reginde/reginde-enti-pst-2026-07-25.json`
  - 11.726 enti presenti nel menu `ente` della pagina ReGIndE.
- `artifacts/reginde/reginde-ruoli-pst-2026-07-25.json`
  - 7 ruoli presenti nel menu `ruolo`.
- `artifacts/reginde/reginde-pagina-pst_2_2-summary-2026-07-25.json`
  - metadata del form e dei campi realmente esposti dalla pagina.
- `artifacts/reginde/reginde-pst-export-audit-2026-07-25.json`
  - indice unico dell’acquisizione, con hash dei file e prova anonima sugli endpoint SOAP.

## Cosa non espone la pagina

La pagina HTML non espone un pulsante o endpoint di esportazione JSON dell’intero archivio soggetti/PEC. La ricerca ReGIndE senza sessione autenticata restituisce `USER_NOT_ALLOWED`.

Il repository contiene già i riferimenti ufficiali WSDL:

- `docs/specs/ministero/A1_WSDL_CATALOG_v1.52/WSDL/Altri Servizi/ReGIndE/ServiziInterrogazioneSoggetto.wsdl`
- `docs/specs/ministero/A1_WSDL_CATALOG_v1.52/WSDL/Altri Servizi/ReGIndE/ServiziInterrogazioneEnte.wsdl`

Il codice Local Signer usa gli endpoint certificati:

- `https://ext.processotelematico.giustizia.it/ServiziInterrogazioneRegindeExt/ServiziInterrogazioneSoggetto`
- `https://ext.processotelematico.giustizia.it/ServiziInterrogazioneRegindeExt/ServiziInterrogazioneEnte`

La prova anonima senza certificato ha restituito `401 Unauthorized` su entrambi gli endpoint e sui rispettivi `?wsdl`, coerentemente con un servizio che richiede autenticazione/certificato.

## Conclusione operativa

Il JSON scaricato dalla pagina è utile come indice enti/ruoli ReGIndE già disponibile localmente, ma non è una prova completa dei domicili digitali PEC per notifiche. Per una notifica L. 53/1994 la verifica utile resta quella puntuale tramite servizio ReGIndE certificato/Local Signer, già prevista dal codice, su ciascun destinatario o su batch governato.

## Prova certificata con Local Signer

Local Signer locale raggiunto su `127.0.0.1:27272`, versione `1.6.103`.

Prova puntuale eseguita tramite `POST /pst/reginde` con certificato locale e PIN, senza invio di PEC:

- soggetto verificato: `AVVOCATURA DELLO STATO DI MILANO`;
- codice fiscale richiesto: `97021490152`;
- PEC richiesta: `ads.mi@mailcert.avvocaturastato.it`;
- esito: `verified=true`;
- data/ora verifica: `25/07/2026 22:29`;
- fonte: `reginde`;
- hash evidenza XML: `078d42328b0868bbecd365605de86f18307d1d0cc77d96b2e726e11b45c3db9d`.

Prova tecnica sul metodo WSDL `elencoPaginatoSoggetti`, sempre con certificato locale:

- richiesta minima: `da=1`, `count=1`;
- esito HTTP: `200`;
- `return_count=1`;
- hash risposta XML: `7f89ffb2ef286835a80cf662430b15efad78ee351d038346dbdde42e15d427f0`.

Mini-prova paginata:

- pagine richieste: `da=1, count=5`, `da=6, count=5`, `da=11, count=5`;
- esito: tutte HTTP `200`;
- record osservati: `15`;
- hash distinti: `15`;
- duplicati osservati: `0`;
- tempo medio rilevato: circa `13` secondi per pagina da 5.

Prova dimensione pagina:

- pagina richiesta: `da=1, count=50`;
- esito HTTP: `200`;
- record restituiti: `50`;
- corpo risposta: circa `98 KB`;
- tempo rilevato: circa `12` secondi;
- hash risposta XML: `5e2faa57226f8af29dc4723cd0fba403fd808535ccc52d8aa4ee071b1d32df38`.

Questo dimostra che con certificato/PIN il servizio autenticato fornisce il dato che serve. Per il prodotto va però mantenuto il principio di minimizzazione: salvare nel fascicolo le verifiche necessarie a mittente e destinatari della notifica, con hash/evidenza, evitando di riversare in repository l’intero archivio nazionale dei soggetti.

## Sincronizzatore locale governato

È stato aggiunto il tool:

- `tools/reginde_sync_cache.py`

Storage locale:

- cartella: `data/local/reginde/`;
- pagine JSONL: `data/local/reginde/pages/`;
- indice deduplicato SQLite: `data/local/reginde/reginde_cache.sqlite`;
- stato/ripresa: `data/local/reginde/state.json`;
- manifest: `data/local/reginde/manifest.json`.

Questi file sono runtime locali e sono esclusi da Git.

Prima tranche reale eseguita:

- pagine scaricate: `5`;
- pagina da: `1` a `250`;
- record distinti in cache: `250`;
- prossimo indice: `251`;
- stato: `complete=false`;
- errore: nessuno.

Comando di stato:

```powershell
python tools\reginde_sync_cache.py --status
```

Comando per continuare a tranche controllata:

```powershell
python tools\reginde_sync_cache.py --max-pages 20 --page-size 50 --pages-per-batch 3 --request-timeout 180
```

Comando per procedere fino alla prima pagina vuota:

```powershell
python tools\reginde_sync_cache.py --full --page-size 50 --pages-per-batch 3 --request-timeout 180 --delay 1.5
```

Il PIN non viene salvato nello stato, nel manifest o nei file pagina. Se non viene fornito da stdin o variabile ambiente, il tool lo chiede in modo interattivo.

## Uso dentro IUSENTRA

Aggancio applicativo aggiunto il 25/07/2026:

- endpoint autenticato `GET /api/v1/ui/notifiche-legali/reginde`;
- servizio read-only `web/services/reginde_cache_search.py`;
- ricerca dalla pagina React `/notifiche-legali`, nel campo già esistente `Cerca indirizzo o soggetto`;
- risultati normalizzati come destinatari di notifica con `fontePecSuggerita=reginde` e badge `ReGIndE`;
- nessun file cache, path locale o JSONL viene esposto alla UI;
- la verifica valida ai fini della notifica resta quella certificata puntuale tramite Local Signer/PST prima dell'invio.

La cache è quindi utilizzabile per compilare rapidamente destinatario, codice fiscale/partita IVA e PEC, mentre la prova di pubblico elenco viene salvata sul fascicolo solo quando il destinatario selezionato viene verificato.

## Prova reale UI locale

Prova eseguita il 25/07/2026 su Docker locale reale `http://127.0.0.1:8080`, container `iusentra-app` healthy, tenant `studio-montagnese`.

Esito osservato nella pagina React `/notifiche-legali`:

- il campo `Cerca indirizzo o soggetto` resta visibile anche quando il fascicolo non propone destinatari;
- digitando `Marta Barsotti` la UI mostra `MARTA BARSOTTI`, PEC `barsotti.marta@ordineavvocatiasti.eu` e badge `ReGIndE`;
- il messaggio operativo indica la cache locale in corso con `250 soggetti già indicizzati`;
- con click reale sulla card il destinatario viene aggiunto al riepilogo: `1 destinatario selezionato`, `1 indirizzo PEC`, `Fonte PEC: reginde`; dal confronto decompilato del 04/08/2026 l'invio operativo resta unico con destinatari nel campo `To`;
- endpoint autenticato `GET /api/v1/ui/notifiche-legali/reginde?q=Marta%20Barsotti&limit=5` verificato con login locale: HTTP `200`, `ok=true`, primo risultato `MARTA BARSOTTI`, fonte `reginde`;
- controllo focus sul campo ricerca, hover sulla card e scroll completo fino al fondo pagina: presenti `Controlla relata`, `Invia PEC`, fonti operative e nessun invio PEC eseguito;
- controllo responsive temporaneo su desktop `1280x900`, tablet `820x900` e mobile `390x820`: campo visibile, destinatario ancora selezionato e nessun overflow orizzontale di pagina.

Durante la prova è stato corretto anche il caso in cui la topbar desktop superava la larghezza disponibile quando sidebar e azioni rapide erano presenti: le azioni ora si comprimono/wrappano nello spazio utile senza coprire la pagina.

## Registro PP.AA. - verifica PST e cache SQL locale

Su richiesta dell'utente è stato controllato anche il Registro PP.AA. del PST:

- pagina contenitore: `https://servizipst.giustizia.it/PST/it/pst_2_8.wp`;
- pagina modulo: `https://servizipst.giustizia.it/PST/it/pst_2_8_2.wp`;
- form ufficiale: `Ricerca Pubblica Amministrazione`;
- campi realmente esposti: `denominazione`, `pec`, `codFiscale`;
- azione ufficiale: `/ExtStr2/do/pubbamm/searchPA.action`;
- pulsante: `Esegui ricerca`.

La pagina non espone un endpoint di esportazione JSON o una paginazione completa del Registro PP.AA.; il comportamento ufficiale osservato è una ricerca puntuale per denominazione, PEC o codice fiscale/partita IVA.

È stato quindi aggiunto un secondo canale SQL locale, separato da ReGIndE:

- tool: `tools/registro_ppaa_sync_cache.py`;
- cartella runtime: `data/local/registro_ppaa/`;
- database: `data/local/registro_ppaa/registro_ppaa_cache.sqlite`;
- fonte API React: `GET /api/v1/ui/notifiche-legali/registro-ppaa`;
- ricerca UI: stesso campo `Cerca indirizzo o soggetto`;
- badge risultato: `Registro PP.AA.`;
- fonte normalizzata: `registro_ppaa`;
- ruolo destinatario normalizzato: `pa`.

Il tool accetta import JSON/JSONL/XML controllati e, quando si usa il certificato locale, interroga il servizio PST enti tramite Local Signer. Il PIN non viene salvato in database, manifest, log o report.

Prova locale cache PP.AA. senza invio PEC:

- import controllato del record `AVVOCATURA DELLO STATO DI MILANO`;
- codice fiscale `97021490152`;
- PEC `ads.mi@mailcert.avvocaturastato.it`;
- database SQLite creato in `data/local/registro_ppaa/registro_ppaa_cache.sqlite`;
- record distinti: `1`;
- la cache è esclusa da Git.

## Aggiornamento 26/07/2026 - prova reale UI Registro PP.AA.

Prova eseguita su Docker locale reale `http://127.0.0.1:8080`, container `iusentra-app` healthy, `/api/pronto` `ok=true`, timezone `Europe/Rome`, dopo rebuild del bundle React.

Esito osservato nella pagina React `/notifiche-legali`:

- digitando `Avvocatura Milano` nel campo `Cerca indirizzo o soggetto` viene interrogata la cache SQL locale PP.AA. tramite API autenticata;
- la UI mostra il risultato `AVVOCATURA DELLO STATO DI MILANO`, PEC `ads.mi@mailcert.avvocaturastato.it`, badge `Registro PP.AA.`;
- il messaggio operativo non usa più la parola tecnica `cache` nella UI dell'avvocato e risulta: `Nessun soggetto trovato in ReGIndE locale. Registro PP.AA. locale in corso: 1 enti già indicizzati.`;
- con click reale sul risultato il destinatario entra nel riepilogo con `1 destinatario selezionato`, `1 indirizzo PEC`, `Pubblica amministrazione` e `Fonte PEC: registro_ppaa`; dal confronto decompilato del 04/08/2026 l'invio operativo resta unico con destinatari nel campo `To`;
- il pulsante risponde a click, stato selected e focus da click, consentendo deselezione e riselezione senza perdere PEC o fonte;
- scroll completo fino al fondo pagina: restano presenti `Invia PEC`, `Fonti operative`, `Presidi` e `Relata`; nessun invio PEC è stato eseguito;
- responsive verificato con viewport `390x844` e `768x1024`: risultato PP.AA. cliccabile, fonte visibile, nessun overflow orizzontale.

Guardrail eseguiti:

- `python -m pytest tests\test_reginde_sync_cache.py tests\test_reginde_cache_search.py tests\test_registro_ppaa_sync_cache.py tests\test_notifiche_legali.py -q`;
- `python -m compileall tools\reginde_sync_cache.py tools\registro_ppaa_sync_cache.py web\services\reginde_cache_search.py web\blueprints\api_v1_react.py pct\notifiche_legali.py`;
- `pnpm --filter @iusentra/studio typecheck`.

## Aggiornamento 12/08/2026 - popolamento completo Registro PP.AA. da export pubblico PST

Riesame della pagina contenitore `https://servizipst.giustizia.it/PST/it/pst_2_8.wp` e del modulo
`pst_2_8_2.wp`: la tabella dei risultati della `Ricerca Pubblica Amministrazione` e' generata con
Displaytag e la stessa azione ufficiale `/ExtStr2/do/pubbamm/searchPA.action` espone il parametro di
export `d-4001731-e=3` che restituisce, senza credenziali, l'intero insieme dei risultati in formato
XML (`<row>/<column>`: denominazione, codice fiscale, codice univoco, classe, PEC), superando la
paginazione da 20 righe.

Poiche' la ricerca e' a sottostringa, la copertura totale del registro si ottiene con 15 query:
`codFiscale=0..9` (ogni codice fiscale/partita IVA numerico contiene almeno una cifra) piu'
`denominazione=a,e,i,o,u` a copertura degli enti senza codice fiscale. E' stato aggiunto il tool
governato:

- `tools/registro_ppaa_harvest_public.py` (fetch cortese con delay, salvataggio pagine con SHA-256,
  parsing, dedup e import opzionale `--import-cache` nella cache SQL esistente);
- test: `tests/test_registro_ppaa_harvest_public.py`.

Esito reale del 12/08/2026 (fuso `Europe/Rome`):

- query eseguite: `15`; righe osservate totali: `117.884`;
- enti distinti dopo dedup: `10.796`, di cui `7.725` con PEC pubblicata;
- record importati nella cache `data/local/registro_ppaa/registro_ppaa_cache.sqlite`: `7.726` distinti
  (7.725 dall'export pubblico + 1 gia' presente, deduplicati per chiave record);
- gli enti senza PEC pubblicata (`3.071`) non vengono importati: la cache serve alla proposta PEC e
  non deve suggerire enti privi di domicilio digitale nel registro;
- ricerche campione verificate su cache reale: `Ministero istruzione` (uspmt@postacert.istruzione.it),
  `Comune di Milano` (attigiudiziari@pec.comune.milano.it), `Agenzia Entrate`
  (comunicazioni_cancellerie@pce.agenziaentrate.it), `INPS`
  (notifica.attigiudiziari.direzionegenerale@postacert.inps.gov.it), `Avvocatura Milano`
  (ads.mi@mailcert.avvocaturastato.it), tutte con fonte `registro_ppaa`.

Le pagine raw, il JSONL e il database restano evidenza runtime locale esclusa da Git. Comando per
ripetere il popolamento (anche sul server, dalla root del repo):

```powershell
python tools\registro_ppaa_harvest_public.py --import-cache
```

La verifica valida ai fini della notifica resta quella certificata puntuale prima dell'invio; la
cache alimenta la proposta destinatari con badge `Registro PP.AA.` nella pagina `/notifiche-legali`.

## Aggiornamento 12/08/2026 - ReGIndE enti "avvocatura": esito ricerca certificata

Su indicazione dell'utente la ricerca e' stata mirata agli **uffici** (avvocature), escludendo le
persone fisiche ReGIndE. Censimento dall'indice pubblico enti ReGIndE (11.726 voci, acquisizione
25/07): **37 enti "avvocatura"** — 26 Avvocature dello Stato, 10 avvocature comunali, 1 servizio
avvocatura regionale (Marche).

Prove reali con certificato CNS ArubaPEC (thumbprint `4F0CE033...`, PIN inserito dall'utente,
fuso `Europe/Rome`):

1. `ricercaEnteEx` con sola `descrizione` ("avvocatura" e 12 denominazioni esatte): HTTP `200`,
   busta `ricercaEnteExResponse` **vuota** (237 B) in tutti i casi.
2. `ricercaEnteEx` con solo `codiceFiscale` (5 CF, incluso il controllo ADS Milano
   `97021490152`): sempre risposta vuota.
3. `ricercaEnteEx` con **terna completa** `descrizione + codiceFiscale + indirizzoPec`
   (stesso schema del flusso Local Signer del 25/07): **4/4 verificati** — ADS Milano
   (`ads.mi@mailcert.avvocaturastato.it`), Comune di Eboli
   (`avvocatura.eboli@asmepec.legalmail.it`), Comune di Lanuvio
   (`segreterialanuvio@pec.provincia.roma.it`), Comune di Surbo (`comunesurbo@pec.it`).

**Conclusione tecnica**: il servizio certificato ReGIndE enti e' un servizio di *verifica*
(conferma una PEC attesa gia' nota), non di *discovery*: non consente di scoprire PEC non
esposte dai registri. Comportamento coerente con il principio fail-closed dei pubblici elenchi.

**Copertura finale avvocature**: 33/37 con PEC dal Registro PP.AA. pubblico gia' in cache;
Eboli, Lanuvio e Surbo confermate anche via ReGIndE certificato sulla PEC principale dell'ente
(record aggiornati in cache, `records_distinct` 7.726 -> 7.730); il Comune di Mugnano di Napoli
(sotto-struttura "AVVOCATURA", CF `00637570631`) **non ha alcuna PEC pubblicata** ne' nel
Registro PP.AA. ne' verificabile in ReGIndE: nessun indirizzo viene inventato, il dato resta
assente per scelta di fonte certa.
