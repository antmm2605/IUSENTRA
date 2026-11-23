# Memoria giuridica di Lex — ricognizione sul software reale

Data: 23/11/2026. Codice: branch `schede-istituto` (da `lavoro/2490` + `lex-regole` 0f773c7a). Piano di riferimento:
«IUSENTRA — Lex con memoria giuridica persistente» (23/11/2026), sezioni 3-18 e 23.

Decisione dell'avvocato: il piano si realizza **sopra** il software esistente. La wiki è una **vista** della conoscenza
già canonica: niente secondo archivio, niente seconda verità. Si comincia dalle schede di istituto per materia.

Legenda: **esiste** = funziona ed è usato; **parziale** = c'è un pezzo, non il requisito intero; **manca** = da fare.

## 1. I quattro livelli del piano (sezione 3)

| Livello | Esito | Componente reale | Cosa fare |
|---|---|---|---|
| 1. Fonti originali (testi, versioni, impronte) | esiste | Fascicolo: documenti e PEC con impronta SHA-256 nel **registro delle letture** (`pct/registro_letture/`, `letture_sintesi_fascicolo`). Diritto: archivio Normattiva (`PCT_NORMATTIVA_DB`, 83.737 atti), biblioteca vigente `codici_leggi.sqlite` con edizioni e pacchetti datati (`lex/normativa/biblioteca/acquisizione.py`), Cassazione SentenzeWeb (422.088 decisioni con testo integrale), Consulta nell'archivio dello studio, OpenGA (solo metadati), prassi AdE/INPS (`pct/prassi/`), Gazzetta (`pct/gazzetta/`) | Nessun nuovo archivio: le schede leggono questi |
| 2. Conoscenza strutturata (affermazioni, eventi, questioni, norme) | parziale | Fascicolo: `archivio_letture` (`letture_fatti`, fatti con ancora e collaudo), modello della causa e catena (`pct/ragionamento/`, `pct/catena/guardiano.py`). Diritto: regole dell'harness di Lex (154 regole, `lex/harness/fattispecie/`) con norma e **ancora letterale** controllata sul testo vigente (`lex/harness/controllo.py`); indice pronunce per norma (`lex/harness/dati/giurisprudenza_per_norma.json`) | Le regole sono la conoscenza strutturata del diritto: le schede le proiettano per istituto |
| 3. Wiki persistente (pagine leggibili e collegate) | **fatto ora (schede di istituto)** | `lex/conoscenza/` + `docs/memoria-giuridica/conoscenza/` (index.md, log.md, una pagina per scheda) + sezione React «Conoscenza» | Prossimi tipi di pagina: norma, pronuncia, procedura, ricerca salvata; memoria del fascicolo |
| 4. Ricerca e ragionamento | parziale | Harness di Lex (comprensione → fatti → norme → regole → composizione → controllo), RAG esistente, ricerca Cassazione/Consulta/OpenGA | Fatto ora: ricerca testuale nelle schede senza embeddings; Lex consulta la scheda prima di rispondere |

## 2. Requisiti delle sezioni 3-18 → componenti

| Sez. | Requisito | Esito | Componente | Cosa fare |
|---|---|---|---|---|
| 3 | Wiki funzionante senza embeddings | **esiste (schede)** | `lex/conoscenza/consultazione.py::cerca` (titolo, sintesi, voci, citazioni; radici di parola) | Estendere ai tipi di pagina futuri |
| 3 | Riutilizzo finché valgono fonti e versioni | **esiste (schede)** | dipendenze `fonte → versione` per scheda; `stato_attuale` confronta con le versioni di oggi | Lavoro notturno nello scheduler (vedi §4) |
| 4 | Separazione delle memorie | parziale | Comune: schede (solo fonti pubbliche, nel prodotto). Studio: annotazioni nel SQL dello studio (`conoscenza_annotazioni`), decisioni `schede_fonti_decisioni`. Fascicolo: `archivio_letture`, permessi `lex/fascicolo_accesso.py`. Product/Studio/Update Pack: `web/services/installation_pack_surface.py` | Verificare che l'Update Pack porti `lex/conoscenza/dati/` e mai le annotazioni |
| 5 | Persistenza canonica unica, Markdown come vista | **esiste (schede)** | `lex/conoscenza/dati/schede_istituto.json` (record), `registro_conoscenza.jsonl` (eventi); Markdown rigenerato | — |
| 5 | Annotazioni umane che sopravvivono | **esiste (schede)** | `lex/conoscenza/annotazioni.py`, legate all'ID stabile e alla voce | — |
| 6 | Schede di istituto (presupposti, eccezioni, oneri, rimedi, processo, strumenti) | **esiste** | `lex/conoscenza/generatore.py` | Arricchire le regole (prove e oneri, eccezioni con norma) |
| 6 | ID stabili, rinomina senza rotture | **esiste** | `ist-<istituto>`, la materia non entra nell'ID | — |
| 6 | Relazioni qualificate (sostiene, contesta, interpreta…) | manca | — | Dopo le pagine di norma e pronuncia |
| 7 | Schema persistente versionato (wiki_schema) | parziale | `schema: 1` + `pipeline: schede-istituto/1` nei record; documentazione in questo file | `wiki_schema.md` quando arrivano altri tipi di pagina |
| 8 | Ingest guidato e batch dei documenti | parziale | Lettura dei documenti e PEC già incrementale e idempotente (registro delle letture, motori di `archivio_letture`, OCR worker, scheduler) | Pagine del fascicolo come viste di `letture_fatti` (fase successiva) |
| 9 | Query con citazioni verificate | parziale | Harness: ogni affermazione con ancora nel testo vigente; ora con la scheda consultata prima (`registro["0_scheda_istituto"]`) | Salvataggio delle analisi nella wiki |
| 9 | Formati (Marp, grafici, canvas) | manca | — | Fase successiva |
| 10 | Lint strutturale | parziale | Riconvalida dipendenze (`verifica`), sezioni mancanti e lacune per scheda; presidio norme dei modelli (`pct/schede_fonti/verifica.py`), confronto vigente (`confronto_vigente.py`) | Collegamenti rotti, orfani, duplicati quando ci saranno relazioni fra pagine |
| 11 | index.md reale per perimetro | **esiste (schede)** | `docs/memoria-giuridica/conoscenza/index.md` + `<materia>/index.md` | — |
| 12 | log.md append-only ricostruibile | **esiste (schede)** | `registro_conoscenza.jsonl` → `log.md`, prefisso `## [` | — |
| 13 | Memoria completa del fascicolo | parziale | inventario del registro delle letture, Lettura del fascicolo, modello della causa, guardiano della catena | Pagina «Memoria del fascicolo» come vista |
| 14 | Diritto nel tempo (vigenza alla data, transitorie) | parziale | `lex/harness/norme.py::modifiche_dopo` (dubbio di vigenza alla data dei fatti); biblioteca con edizioni e commi abrogati, `abrogato_ma_vigente` (abrogazioni differite) | Versioni storiche dell'articolo nella scheda |
| 14 | Massima ≠ testo integrale | **esiste (schede)** | `tipo_testo` della pronuncia; «massima: fatti e motivazione non letti» | — |
| 14 | Contrasti senza prevalenza automatica | **esiste (schede)** | orientamento «non classificato», valutazione solo dall'avvocato (annotazione con esito) | — |
| 15 | Registro delle sorgenti | parziale | `lex/operational_knowledge/source_registry.py` (50 sorgenti operative), `lex/legal_sources/registry.py`, `lex/research/official_sources.py`, registro fonti delle procedure `pct/procedura_fasi/fonti.py` (400 fonti) | Un'unica mappa con copertura e stato operativo |
| 16 | Specializzazioni per materia | parziale | 154 regole in 25 materie del catalogo strumenti (`~/iusentra-controlli/lex/copertura-strumenti/catalogo.json`); banco di prova `tests/lex_materie_casi.py` | Le schede mostrano per materia cosa è coperto e cosa manca |
| 17 | Metodo di risposta con fonti verificate | esiste | harness (6 passi) | — |
| 18 | Niente promozione circolare | **esiste (schede)** | le schede derivano solo da regole e fonti; le risposte di Lex non tornano nelle schede; le annotazioni restano dello studio | — |

## 3. Le schede di istituto (fatto in questo lavoro)

- **Tassonomia**: `lex/conoscenza/dati/istituti.json`, 153 istituti in 26 materie (le 25 del catalogo strumenti +
  «esecuzione contro la PA»), prima le materie frequenti nello studio. Ogni regola dell'harness è attaccata a un istituto.
- **Generazione** (`scripts/conoscenza_schede_istituto.py genera`): per ogni istituto si eseguono le sue regole sul nome
  dell'istituto (o sulla frase d'esempio), poi il **controllore di Lex** (`verifica_analisi`): entra solo ciò che ha
  l'ancora letterale nel testo vigente. I testi liberi delle regole (avvertenze, questioni) entrano solo se citano
  norme e tutte esistono nell'archivio, con la dichiarazione «affermazione non ancorata parola per parola».
- **Fonti con versione**: ogni norma porta URL Normattiva, data di aggiornamento dell'archivio e versione (SHA-256 del
  testo vigente); ogni pronuncia estremi, URL ufficiale, tipo di testo (integrale/massima) e versione.
- **Orientamenti**: solo pronunce dell'indice per norma in cui il testo cita davvero l'articolo, con il passaggio
  (`scripts/conoscenza_passaggi_pronunce.py`, letto nel container dove gli archivi sono leggibili).
- **Persistenza**: record con revisione e dipendenze; eventi append-only con ID deterministico; viste Markdown
  ricostruibili. Le annotazioni dell'avvocato nel SQL dello studio.
- **Riconvalida**: `stato_attuale` confronta le versioni registrate con quelle di oggi → «da riesaminare» con la
  fonte cambiata; la rigenerazione crea la nuova revisione con l'elenco delle fonti cambiate.
- **Interfaccia**: `/ricerca-legale/conoscenza` (React), API `/api/v1/ui/conoscenza`.
- **Lex**: `lex/harness/__init__.py::_scheda_istituto` consulta la scheda della regola prima dell'analisi; la risposta
  la cita e il registro della risposta la riporta (`0_scheda_istituto`).

## 4. Limiti dichiarati

- «Prove e oneri» e «Eccezioni» sono quasi sempre mancanti: le regole non hanno ancora affermazioni ancorate su questi
  punti. Restano dichiarate, non riempite.
- Le norme di riferimento del catalogo presenti in biblioteca ma non nel registro delle norme di Lex sono elencate fra
  le lacune: vanno aggiunte a `lex/harness/norme_materie.py` (lavoro del branch delle regole).
- L'indice delle pronunce per norma nasce da una ricerca testuale (citazione + rubrica): molte pronunce non citano
  l'articolo e quindi non entrano. Gli orientamenti restano pochi finché l'indice non si costruisce sulle citazioni.
- La rigenerazione non è ancora un lavoro dello scheduler: si lancia con lo script; lo stato «da riesaminare» è però
  calcolato dal vivo a ogni apertura.
