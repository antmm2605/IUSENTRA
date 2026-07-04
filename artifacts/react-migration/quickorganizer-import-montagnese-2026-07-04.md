# Import pratiche Montagnese da Studio Telematico

Data operativa: 04/07/2026, fuso `Europe/Rome`.

Tenant produzione: `studio-legale-giuseppe-montagnese`.

Origine dati locale autorizzata: `E:\QuickOrganizer`.

Superficie utente: `https://app.iusentra.it/importa-pratiche`.

## Obiettivo

Rieseguire l'importazione delle pratiche storiche dello studio, correggendo i fascicoli che non avevano tutti i documenti e riallineando il nome visibile dei documenti al nome file originale usato da Studio Telematico.

La fonte di verità del tenant in produzione è SQLite: `/opt/iusentra/data/tenants/studio-legale-giuseppe-montagnese/studio.db`. I file JSON del tenant restano mirror o supporto storico, non base decisionale dell'audit.

## Confronto con Studio Telematico

Sono stati ricontrollati i sorgenti decompilati in:

- `C:\Users\antmm\AppData\Local\Temp\quickorganizer_decompiled_full\QuickOrganizer\WizardImportaPraticheDaPolisWeb.cs`;
- `C:\Users\antmm\AppData\Local\Temp\quickorganizer_decompiled_full\QuickOrganizer\PCT.cs`.

Il comportamento rilevante è che la griglia e il download dei documenti usano il campo `nomeFileOriginale` come nome del file da scaricare e conservare. In IUSENTRA il titolo/descrizione tabellare resta quindi un metadato descrittivo (`tipo_atto_portale`), mentre `nome`, `nome_originale` e `nome_portale` devono coincidere con il file effettivo.

## Modifica applicativa

File toccato: `web/services/quickorganizer_import.py`.

Intervento:

- aggiunto riallineamento dei metadati documento importati;
- sui nuovi documenti il nome visibile viene impostato al nome file originale;
- il titolo tabellare viene conservato in `tipo_atto_portale`;
- durante una riesecuzione parziale l'import controlla prima i duplicati già presenti tramite `id_documento_portale`, così può riparare i metadati anche se il pacchetto contiene solo i file mancanti;
- l'audit considera allineato un documento solo quando `nome`, `nome_originale` e `nome_portale` coincidono con il file originale e la descrizione tabellare resta separata.

Test aggiunto: `tests/test_quickorganizer_import.py::test_import_studio_telematico_reimport_riallinea_nomi_documenti_esistenti`.

## Analisi origine

Lettura `E:\QuickOrganizer\QuickOrganizer.mdb`:

- pratiche: `331`;
- nominativi: `313`;
- collegamenti parti: `820`;
- documenti tabella `TESTI`: `9202`;
- email tabella `EMAILS`: `4432`;
- agenda: `29`;
- file fisici trovati sotto `ATTI`/`EMAILS`: `15956`;
- dimensione file fisici analizzati: `26.022.137.330` byte;
- documenti mancanti nell'origine: `0`;
- email mancanti nell'origine: `0`.

Avviso non bloccante dell'analisi: `10` pratiche non avevano il cliente collegato con il vecchio indicatore Studio Telematico; l'import crea o collega il cliente ricostruito dalla pratica senza perdere il fascicolo.

## Stato produzione prima della riesecuzione

Tenant su Hetzner: `/opt/iusentra/data/tenants/studio-legale-giuseppe-montagnese`.

Conteggi prima dell'intervento:

- clienti: `261`;
- soggetti: `274`;
- parti fascicolo: `785`;
- fascicoli: `330`;
- fascicoli da import storico: `323`;
- documenti totali: `13221`;
- attività totali: `305`;
- fascicoli senza documenti: `19`.

Confronto prima della riesecuzione:

- pratiche attese: `331`;
- pratiche storiche presenti: `323`;
- pratiche mancanti: `306`, `327`, `328`, `329`, `330`, `331`, `332`, `333`;
- documenti attesi con pratica collegata: `9180`;
- email attese con pratica collegata: `4379`;
- documenti/email già presenti con nome non allineato al file originale: `13116`;
- documenti mancanti: `246`;
- email mancanti: `197`.

Backup dati prima dell'import:

`/opt/iusentra/data/tenants/studio-legale-giuseppe-montagnese/backup/quickorganizer_reimport/studio_pre_reimport_20260704184935.db`

## Riesecuzione produzione

Per evitare di ricaricare tutti i `26 GB`, è stato generato un pacchetto di riallineamento con il database completo e solo i file fisici mancanti:

- archivio locale: `C:\Users\antmm\AppData\Local\Temp\IUSENTRA-Montagnese-reimport-20260704-184759.zip`;
- archivio server: `/opt/iusentra/data/tenants/studio-legale-giuseppe-montagnese/fascicoli/importazioni/quickorganizer/manual/reimport-missing-files.zip`;
- file inclusi: `443`;
- dimensione non compressa: `615.876.932` byte;
- dimensione archivio server: circa `429 MB`.

Import eseguito nel container `iusentra-app` contro il tenant reale con `allow_partial=True`.

Esito import:

- durata: `13,29` secondi;
- fascicoli prima/dopo: `330` -> `338`;
- clienti prima/dopo: `261` -> `265`;
- soggetti prima/dopo: `274` -> `278`;
- documenti prima/dopo: `13221` -> `13664`;
- pratiche create: `8`;
- pratiche aggiornate: `323`;
- documenti importati: `246`;
- email importate: `197`;
- documenti mancanti: `0`;
- email mancanti: `0`;
- documenti con metadati riparati: `8934`;
- email con metadati riparati: `4182`;
- duplicati saltati: `13145`;
- errori: `0`.

## Audit post-import

Confronto completo tra `E:\QuickOrganizer`, file fisici e tenant produzione:

- pratiche attese: `331`;
- pratiche storiche presenti: `331`;
- pratiche mancanti: `0`;
- documenti attesi: `9180`;
- email attese: `4379`;
- documenti/email attesi presenti: `13559`;
- documenti mancanti: `0`;
- email mancanti: `0`;
- mismatch sui nomi: `0`;
- mismatch fisici: `0`;
- fascicoli con problemi: `0`.

Campioni tecnici controllati nel tenant:

- fascicolo storico `AB24A023`, pratica `quickorganizer:1`: documento `00000001.RTF` visibile come `00000001.RTF`, con descrizione tabellare `Ricorso.RTF`;
- fascicolo importato dalla riesecuzione `84DC4FE1`, pratica `quickorganizer:327`: documenti visibili come file `20260609104419720.PDF`, `20260609104420022.PDF`, `20260609104420214.PDF` e successivi, con descrizioni tabellari conservate in `tipo_atto_portale`;
- fascicolo storico riparato `DE674F4F`, pratica `quickorganizer:325`: documenti visibili come file `20260526121052925.PDF`, `20260526121053194.PDF`, `20260526121053371.PDF` e successivi.

## Test automatici

Eseguiti localmente sul perimetro toccato:

- `python -m pytest tests\test_quickorganizer_import.py -q`: `16` test passati;
- `python -m py_compile web\services\quickorganizer_import.py scripts\audit_quickorganizer_import.py`: passato;
- `python -m pytest tests\test_utf8_integrity.py -q`: `4` test passati.

## Stato prova reale

Da completare prima del report finale:

- verifica UI produzione su `https://app.iusentra.it/importa-pratiche`;
- apertura di almeno un fascicolo storico riparato e un fascicolo creato dalla riesecuzione;
- controllo visivo della lista documenti con nomi file originali, pulsanti di visualizzazione/scaricamento, scroll completo e assenza di testi tecnici visibili.

Il lavoro resta aperto finché produzione, repository, branch gemelli, Docker locale e deploy Hetzner non puntano allo stesso commit verificato.
