# Canary fonti legali - 2026-05-19

Prima tornata e rerun mirati eseguiti solo con `legal-updates-canary`, sempre con `--limit 3`, `--max-seconds 90`, `--no-publish`, `--direct-only`, `--save-diagnostics` e `--json`. Nessuna pubblicazione automatica è stata eseguita. I JSON diagnostici sono salvati in `artifacts/legal-updates/canary-2026-05-19/`.

## Comandi
- `python -m pct.cli legal-updates-canary --source cassazione_ultime_sent_ord_questioni --limit 3 --max-seconds 90 --no-publish --direct-only --save-diagnostics --json`
- `python -m pct.cli legal-updates-canary --source gazzetta_ufficiale --limit 3 --max-seconds 90 --no-publish --direct-only --save-diagnostics --json`
- `python -m pct.cli legal-updates-canary --source inps_circolari --limit 3 --max-seconds 90 --no-publish --direct-only --save-diagnostics --json`
- `python -m pct.cli legal-updates-canary --source inps_messaggi --limit 3 --max-seconds 90 --no-publish --direct-only --save-diagnostics --json`
- `python -m pct.cli legal-updates-canary --source agcom_provvedimenti --limit 3 --max-seconds 90 --no-publish --direct-only --save-diagnostics --json`
- `python -m pct.cli legal-updates-canary --source anac_documenti --limit 3 --max-seconds 90 --no-publish --direct-only --save-diagnostics --json`
- `python -m pct.cli legal-updates-canary --source garante_privacy --limit 3 --max-seconds 90 --no-publish --direct-only --save-diagnostics --json`
- `python -m pct.cli legal-updates-canary --source pst_giustizia_download --limit 3 --max-seconds 90 --no-publish --direct-only --save-diagnostics --json`
- `python -m pct.cli legal-updates-canary --source openga_sentenze --limit 3 --max-seconds 90 --no-publish --direct-only --save-diagnostics --json`
- `python -m pct.cli legal-updates-canary --source curia_cgue_rss --limit 3 --max-seconds 90 --no-publish --direct-only --save-diagnostics --json`

## Esito fonte per fonte
| fonte | trovati | processati/cache | testo | allegati | PDF letti | OCR eseguiti/falliti | riferimenti | domande | destinazione | scarti | admin | Ricerca Legale | Lex | stato | nota |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- | --- | --- | --- | --- | --- | --- |
| `cassazione_ultime_sent_ord_questioni` | 3 | 0/3 | 3 | 0 | 3 | 3/0 | 7 | 24 | Giurisprudenza o RAG | nessuno | sì | predisposta, no-publish | sì | verde | Schede dettaglio ufficiali, PDF/testo già in qualità evidenze, riferimenti e domande presenti. |
| `gazzetta_ufficiale` | 27 | 0/3 | 3 | 3 | 0 | 0/0 | 6 | 24 | Normativa o notizia | nessuno | sì | predisposta, no-publish | sì | giallo | Il canary usa l'elenco ufficiale 30 giorni e trova il PDF; la verifica allegati non legge ancora il fascicolo PDF. |
| `inps_circolari` | 50 | 0/3 | 3 | 0 | 3 | 3/0 | 9 | 24 | Prassi | nessuno | sì | predisposta, no-publish | sì | verde | Circolari ufficiali con testo, PDF letto, riferimenti e domande. |
| `inps_messaggi` | 9 | 3/0 | 3 | 0 | 2 | 2/0 | 17 | 24 | Prassi o notizia | nessuno | sì | predisposta, no-publish | sì | verde | RSS pubblico INPS messaggi è incoerente; ora usa API elenco controllata e filtra solo `Messaggio`. |
| `agcom_provvedimenti` | 30 | 0/3 | 3 | 4 | 3 | 3/0 | 20 | 24 | Prassi, notizia o RAG | nessuno | sì | predisposta, no-publish | sì | verde | Entrano delibere/provvedimenti con PDF ufficiali, non navigazione o trasparenza. |
| `anac_documenti` | 25 | 1/2 | 3 | 2 | 0 | 0/0 | 14 | 24 | Prassi o notizia | nessuno | sì | predisposta, no-publish | sì | giallo | Entrano delibere/pareri/atti; alcune schede restano senza PDF letto e vanno osservate in pilot dedicato. |
| `garante_privacy` | 5 | 3/0 | 3 | 3 | 0 | 0/0 | 45 | 24 | Prassi o notizia | nessuno | sì | predisposta, no-publish | sì | giallo | Entrano newsletter/docweb ufficiali, non social; utile per RAG/prassi, PDF non sempre presente. |
| `pst_giustizia_download` | 20 | 0/3 | 3 | 3 | 0 | 0/0 | 0 | 24 | Solo RAG | nessuno | sì | predisposta, no-publish | sì | giallo | Fonte tecnica coerente RAG-only; non deve andare in pubblicazione news automatica. |
| `openga_sentenze` | 372 | 0/3 | 3 | 3 | 0 | 0/0 | 22 | 24 | Giurisprudenza se documentale, altrimenti solo RAG | nessuno | sì | predisposta, no-publish | sì | giallo | Dataset OpenGA correttamente RAG-only; serve promozione separata solo per risorse documentali concrete. |
| `curia_cgue_rss` | 10 | 0/3 | 3 | 0 | 0 | 0/0 | 6 | 24 | Giurisprudenza UE | nessuno | sì | predisposta, no-publish | sì | verde | Titoli ripuliti dal prefisso tecnico/null e cause UE riconosciute. |

## Problemi corretti
- Gazzetta Ufficiale: sostituita la scansione generica con l'elenco ufficiale degli ultimi 30 giorni della Serie Generale e link `downloadPdf` non criptato.
- INPS messaggi: il feed RSS pubblico `messaggi` restituisce contenuti incoerenti; il canary usa ora l'API elenco della pagina ufficiale e filtra solo elementi `Messaggio`.
- AGCOM, ANAC e Garante: aggiunto filtro/ranking fonte-specifico per scartare navigazione, social, trasparenza e servizi.
- Curia CGUE: ripuliti i titoli RSS da prefissi tecnici e `null`; riconosciute cause UE `C-.../...` e `T-.../...`.
- Diagnostica canary: gli elementi invariati riportano comunque documento normalizzato, `review_id` e qualità evidenze già salvata.
- UTF-8: rigenerate le diagnostiche con stdout UTF-8 e riparazione mojibake in ingresso parser/diagnostica.

## Candidate pilot guarded
1. `cassazione_ultime_sent_ord_questioni`: più completa, con PDF/testo/riferimenti/domande e destinazione giurisprudenza/RAG.
2. `inps_circolari`: prassi previdenziale con PDF/testo e riferimenti normativi.
3. `agcom_provvedimenti`: delibere/provvedimenti filtrati, con PDF ufficiali e destinazione prassi/news/RAG.

## Fonti in osservazione
- `gazzetta_ufficiale`: pronta come canary elenco/PDF link, ma gialla finché la lettura del PDF del fascicolo non entra nella verifica allegati.
- `anac_documenti`: utile e filtrata, ma gialla perché alcune schede restano senza PDF letto.
- `garante_privacy`: utile per newsletter/provvedimenti RAG/prassi, ma gialla perché non sempre ha PDF ufficiale.
- `pst_giustizia_download`: RAG-only tecnico, non pilot di pubblicazione news.
- `openga_sentenze`: RAG-only/open data; serve pilot dedicato per promuovere solo documenti giurisprudenziali concreti.

## Aggiornamento Fase 3 - correzione fonti gialle post-canary

Questo aggiornamento sostituisce lo stato delle cinque fonti gialle elencate sopra. I rerun mirati sono stati eseguiti il 19 maggio 2026 solo sulle fonti problematiche, sempre con `--limit 2`, `--max-seconds 60`, `--no-publish`, `--direct-only`, `--save-diagnostics` e `--json`. I payload JSON aggiornati sono stati riesportati in `artifacts/legal-updates/canary-2026-05-19/`.

| fonte | problema reale | fix applicato | rerun canary | nuovo stato | nota operativa |
|---|---|---|---|---|---|
| `gazzetta_ufficiale` | allegato PDF presente nel parser ma non riletto quando l'elemento risultava invariato | il canary rinfresca le evidenze degli invariati con PDF ufficiale; la verifica legge anche gli allegati già normalizzati | `documents_found=23`, `processed=0`, `skipped_unchanged=2`, `verification_attachments_saved=2`, qualità `pdf_found=true`, `text_read=true`, `ocr_status=pulito` | verde | candidata pilot: PDF fascicolo letto e hash/testo disponibili, nessuna pubblicazione eseguita |
| `anac_documenti` | falso allegato creato dal testo della scheda quando non esisteva un link PDF reale | il parser non crea più allegati da testo senza `<a href>` e conserva solo pagina ufficiale/HTML quando il PDF manca | `documents_found=25`, `processed=1`, `skipped_unchanged=1`, `attachment_count=0`, qualità `ready=true`, testo diretto presente | verde | PDF non obbligatorio per tutte le schede ANAC; resta review umana prima di pubblicare |
| `garante_privacy` | link normativo `GDPR`/`il-testo-del-regolamento` scambiato per allegato documento | rimosso il marker generico `testo` dagli allegati parser e aggiunto test specifico Garante | `documents_found=5`, `processed=2`, `attachment_count=0`, qualità `ready=true`, testo diretto presente | verde | fonte utile per prassi/news privacy quando il testo docweb è leggibile |
| `pst_giustizia_download` | pagine di navigazione/download tecnico trattate come possibili news | filtro PST più stretto: pagine generiche escluse, destinazione resta `RAG-only`/telematico | `documents_found=1`, `processed=1`, destinazione `RAG-only`, nessuna pubblicazione | RAG-only | fonte tecnica non pubblicabile come news; usare solo come evidenza tecnica Lex/telematico |
| `openga_sentenze` | risorse CSV/JSON/ODS con riferimenti interni sembravano documenti giurisprudenziali pubblicabili | le risorse tabellari OpenGA sono marcate come dataset tecnico e conservate solo come evidenza RAG; i PDF documentali restano promuovibili separatamente | `documents_found=372`, `processed=2`, destinazione `RAG-only`, motivo `Catalogo o dataset open data in formato tecnico/tabellare` | RAG-only | non pubblicare dataset; pilot separato solo per risorse PDF/documento giuridico concreto |
