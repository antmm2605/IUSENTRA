# Fase 5 - Popolamento primo gruppo fonti verdi

Aggiornato il 19 maggio 2026. Esecuzione fonte per fonte, senza import massivo, senza scheduler globale, senza Web libero e con pubblicazione `guarded`.

## Sintesi

- Fonti eseguite: 11.
- Documenti trovati: 517.
- Documenti processati: 24.
- Documenti pubblicati unici: 20.
- Documenti RAG-only/non pubblicati: 8.
- Scarti guarded: 26.
- Ricerca Legale: 20/20 pubblicati ritrovati con query fonte mirata.
- Lex: 20/20 pubblicati interrogabili dal repository fonti.
- Archivio Giurisprudenza strutturato: 0 nuove schede; le pronunce senza promozione strutturata restano news/RAG ufficiale.

## Risultati per fonte

| fonte | trovati | processati | invariati | pubblicati | scarti guarded | evidenze | allegati | durata | note |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `agcom_provvedimenti` | 30 | 2 | 3 | 4 | 1 | 9 | 5 | 19.46s | ok |
| `anac_documenti` | 25 | 3 | 2 | 0 | 5 | 5 | 0 | 35.65s | ok |
| `cassazione_ultime_sent_ord_questioni` | 5 | 0 | 5 | 5 | 0 | 12 | 7 | 37.02s | ok |
| `corte_conti` | 10 | 5 | 0 | 3 | 2 | 14 | 9 | 47.78s | ok |
| `corte_costituzionale` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1.13s | ok |
| `curia_cgue_rss` | 10 | 2 | 3 | 1 | 4 | 5 | 0 | 17.01s | ok |
| `garante_privacy` | 5 | 5 | 0 | 0 | 5 | 5 | 0 | 10.59s | ok |
| `inps_circolari` | 50 | 2 | 3 | 5 | 0 | 15 | 10 | 79.06s | ok |
| `inps_messaggi` | 9 | 2 | 3 | 2 | 3 | 5 | 3 | 14.39s | ok |
| `openga_sentenze` | 372 | 3 | 2 | 0 | 5 | 3 | 0 | 26.71s | ok |
| `pst_giustizia_download` | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 0.51s | ok |

## Documenti pubblicati

| fonte | review | titolo | destinazione | PDF | OCR | riferimenti | domande | Ricerca Legale | Lex |
|---|---:|---|---|---|---|---:|---:|---|---|
| `agcom_provvedimenti` | 31 | Delibera 28/26/CSP | news | sì | pulito | 20 | 16 | sì | sì |
| `agcom_provvedimenti` | 32 | Delibera 102/26/CONS | news | sì | pulito | 8 | 16 | sì | sì |
| `agcom_provvedimenti` | 78 | Determina 14/26/DTC/CP | prassi | sì | pulito | 9 | 16 | sì | sì |
| `agcom_provvedimenti` | 79 | Determina 15/26/DTC/CP | prassi | sì | pulito | 11 | 16 | sì | sì |
| `cassazione_ultime_sent_ord_questioni` | 1 | Vai al documento Sospensione del processo al di fuori dei casi tipici - Illegittimità - Impugnabilità con il regolamento di competenza - Mancata impugnazione - Conseguenze. del 15/05/26 | news | sì | leggibile_con_note | 12 | 17 | sì | sì |
| `cassazione_ultime_sent_ord_questioni` | 2 | Vai al documento Interpretazione e portata dell’art. 7 quinquies della l. n. 212 del 2000 - Violazione di diritti fondamentali del contribuente - Principio di inutilizzabilità degli atti e dei documenti - Sussistenza. del 12/05/26 | news | sì | leggibile_con_note | 20 | 16 | sì | sì |
| `cassazione_ultime_sent_ord_questioni` | 3 | Vai al documento Giudicato esterno - Accertamento e prova - Certificazione ex art. 124 disp. att. c.p.c. - Altre libere modalità dimostrative. del 12/05/26 | news | sì | leggibile_con_note | 18 | 16 | sì | sì |
| `cassazione_ultime_sent_ord_questioni` | 55 | Vai al documento Cassa dei geometri - Iscrizione all'albo professionale - Art. 5 dello Statuto della Cassa Italiana di Previdenza ed Assistenza Geometri (CIPAG) - Svolgimento di libera professione - Presunzione semplice - Prova contraria - Modalità indicate nelle delibere del Consiglio di amministrazione - Efficacia - Limitazione degli ordinari mezzi di prova - Esclusione - Mere agevolazioni probatorie - Sussistenza. del 11/05/26 | news | sì | leggibile_con_note | 20 | 18 | sì | sì |
| `cassazione_ultime_sent_ord_questioni` | 56 | Vai al documento Omissioni contributive determinate da obiettiva incertezza sulla debenza della contribuzione - Accesso al regime sanzionatorio agevolato ex art. 116, comma 10, l. n. 388 del 2000 - Presupposto - Pagamento entro il termine fissato dall’Ente impositore - Interpretazione - Imposizione del termine - Definitivo superamento dell’incertezza interpretativa - Necessità - Esclusione. del 04/05/26 | news | sì | leggibile_con_note | 13 | 17 | sì | sì |
| `corte_conti` | 67 | Sentenza n. 127/2026 | news | sì | pulito | 8 | 16 | sì | sì |
| `corte_conti` | 68 | Sentenza n. 63/2026 e Massima | news | sì | pulito | 10 | 15 | sì | sì |
| `corte_conti` | 69 | Sentenza n. 96/2026 | news | sì | pulito | 5 | 15 | sì | sì |
| `curia_cgue_rss` | 72 | Sentenza della Corte nella causa C-797/23 | news | no | non_richiesto | 1 | 14 | sì | sì |
| `inps_circolari` | 4 | Circolare numero 55 del 14-05-2026 | news | sì | leggibile_con_note | 11 | 16 | sì | sì |
| `inps_circolari` | 5 | Circolare numero 56 del 14-05-2026 | news | sì | pulito | 8 | 16 | sì | sì |
| `inps_circolari` | 6 | Circolare numero 57 del 14-05-2026 | news | sì | leggibile_con_note | 15 | 16 | sì | sì |
| `inps_circolari` | 74 | Circolare numero 54 del 13-05-2026 | news | sì | pulito | 14 | 16 | sì | sì |
| `inps_circolari` | 75 | Circolare numero 53 del 07-05-2026 | news | sì | pulito | 20 | 16 | sì | sì |
| `inps_messaggi` | 51 | Messaggio numero 1618 del 14/05/2026 | news | sì | pulito | 9 | 16 | sì | sì |
| `inps_messaggi` | 53 | Messaggio numero 1493 del 04/05/2026 | news | sì | pulito | 8 | 16 | sì | sì |

## Documenti RAG-only / non pubblicati

| fonte | review | titolo | destinazione | motivo |
|---|---:|---|---|---|
| `corte_conti` | 70 | Sentenza n. 91/2026 | RAG-only | riferimenti non ritrovati nella diagnosi fonte |
| `corte_conti` | 71 | Sentenza n. 94/2026 | RAG-only | riferimenti non ritrovati nella diagnosi fonte |
| `openga_sentenze` | 22 | CDS - Sentenze - CDS - Sentenze - 2024 | RAG-only | Catalogo o dataset open data in formato tecnico/tabellare: conservato solo come evidenza RAG. |
| `openga_sentenze` | 23 | CDS - Sentenze - CDS - Sentenze - 2024 | RAG-only | Catalogo o dataset open data in formato tecnico/tabellare: conservato solo come evidenza RAG. |
| `openga_sentenze` | 24 | CDS - Sentenze - CDS - Sentenze - 2024 | RAG-only | Catalogo o dataset open data in formato tecnico/tabellare: conservato solo come evidenza RAG. |
| `openga_sentenze` | 83 | CDS - Sentenze - CDS - Sentenze - 2023 | RAG-only | Catalogo o dataset open data in formato tecnico/tabellare: conservato solo come evidenza RAG. |
| `openga_sentenze` | 84 | CDS - Sentenze - CDS - Sentenze - 2023 | RAG-only | Catalogo o dataset open data in formato tecnico/tabellare: conservato solo come evidenza RAG. |
| `pst_giustizia_download` | 54 | PST Giustizia - download tecnici | RAG-only | Pagina di navigazione, privacy, cookie, contatti o supporto: non pubblicabile come aggiornamento. |

## Scarti guarded

| fonte | motivo | occorrenze |
|---|---|---:|
| `agcom_provvedimenti` | duplicato già pubblicato | 1 |
| `anac_documenti` | Fonte ufficiale diretta acquisita, ma servono ulteriori conferme prima di trattare il riferimento come completato. | 5 |
| `corte_conti` | riferimenti non ritrovati nella diagnosi fonte | 2 |
| `curia_cgue_rss` | riferimenti non ritrovati nella diagnosi fonte | 4 |
| `garante_privacy` | Fonte ufficiale diretta acquisita, ma servono ulteriori conferme prima di trattare il riferimento come completato. | 3 |
| `garante_privacy` | riferimenti non ritrovati nella diagnosi fonte | 2 |
| `inps_messaggi` | testo tecnico grezzo non pubblicabile in UI | 3 |
| `openga_sentenze` | Catalogo o dataset open data in formato tecnico/tabellare: conservato solo come evidenza RAG. | 5 |
| `pst_giustizia_download` | destinazione non pubblicabile: solo RAG o fuori perimetro | 1 |

## Correzioni applicate

- Corte costituzionale: bloccato il fallback su captcha/navigazione e accettate solo schede pronuncia ufficiali.
- Corte dei conti: scartati link di navigazione, riconosciuti download ufficiali `/Download?id=...` con label PDF e sostituiti titoli generici con il titolo dell'allegato ufficiale.
- Output diagnostici fase 5 scritti in UTF-8 e verificati senza caratteri sostitutivi.

## Esclusioni operative

- `cassazione_citazioni_verificate`, `inps_sentenze`, `agcm_bollettino`, `ministero_lavoro_interpelli`, `agenzia_entrate`, `openga_ordinanze`, `openga_decreti`, `openga_pareri`: non eseguite in pubblicazione perché ancora in osservazione nel piano/report corrente.
- `corte_costituzionale`: eseguita ma non pubblicata perché la fonte diretta ha restituito zero schede pronuncia verificabili dopo il blocco del fallback.
- `anac_documenti` e `garante_privacy`: acquisite ma non pubblicate perché il guarded ha richiesto conferme ulteriori o riferimenti ritrovabili nella diagnosi.
- `pst_giustizia_download` e `openga_sentenze`: eseguite solo come RAG-only/non pubblicabili; nessuna news creata.

## Proposta fase normativa / archivi base

Prossima fase consigliata: pilot separato per normative e archivi base con `gazzetta_ufficiale`, `normattiva`/codici e, solo dopo un canary verde dedicato, `agenzia_entrate`, `ministero_lavoro_interpelli`, `agcm_bollettino` e `inps_sentenze`. Per OpenGA usare una tranche separata che promuova solo risorse PDF/documentali concrete, lasciando dataset CSV/JSON/ODS in RAG-only.
