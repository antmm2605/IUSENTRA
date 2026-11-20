# Harness di Lex: il motore che decide, il modello che scrive

Stato al 19/11/2026, branch `fix-lex-atti`. Il codice è in `lex/harness/`. L'ingresso HTTP è
`lex/orchestrator_http.py::_harness_http_payload`, chiamato all'inizio di `chat_response` e di
`build_context_response`, prima di ogni percorso operativo.

## Perché esiste

Il caso Ferrandina, cioè un racconto di fatti con la richiesta «Redigimi l'atto di citazione… valuta tu rito e
giudice», finiva al presidio PEC. Il motivo: i router operativi scelgono la rotta per sottostringhe («PEC», «termine»,
«oggi», «parte»). Con l'harness ogni domanda giuridica passa da passi fissi, che consultano le norme vigenti e le
regole del software, qualunque sia la forma in cui è scritta. Le domande operative restano ai percorsi dello studio,
per esempio «cosa scade oggi?» e «PEC di oggi».

## Le fasi

```
domanda ──► 1 comprensione ──► 2 fatti ──► 3 qualificazione (regola) ──► 4 norme vigenti
                │ operativa → percorso dello studio                 │
                │ termine/calcolo/norma senza regola → motori certi (risposte_certe)
                ▼
   6 rimedio · 7 competenza e foro · 8 rito · 9 procedibilità · 10 termini · 11 importi · 12 tranelli
                ▼
   13 dati mancanti · 14 modello d'atto e bozza ──► controllo (ancore, citazioni, doppio calcolo)
                ▼
   15 schema ──► [scrittore facoltativo + controllo dello schema] ──► risposta + registro
```

Ogni risposta porta il **registro** (`payload.lex_harness.registro`), con il risultato strutturato di ogni fase:

| Fase | Codice | Strumenti del software usati | Fonte di ogni affermazione |
|---|---|---|---|
| 1 Comprensione | `comprensione.py` | — | richiesta (parte «Richiesta dell'avvocato» se c'è) |
| 2 Fatti | `fatti.py`, `fattispecie/strumenti.py` | — | testo dei fatti (date, importi, parti, luoghi) |
| 3 Qualificazione | `fattispecie/__init__.py` (35 regole) | — | regola applicata, scritta nel registro |
| 4 Norme | `norme.py`, `dati/norme_vigenti.json`, `scripts/lex_harness_norme.py` | archivio Normattiva del software (`ricerca_legale_norma_citata`), Normattiva AKN (`lex/normativa/biblioteca/normattiva_akn.py`) per gli atti assenti | URN, data di aggiornamento, SHA-256 del testo |
| 5 Giurisprudenza | — | non usata (vedi sotto) | nessuna pronuncia è affermata |
| 6 Rimedio | regole | catalogo dei modelli d'atto (`pct/template_atti_schede`) | norma con ancora |
| 7 Competenza | `procedura.py` | testo vigente dell'art. 7 c.p.c. (soglie lette dal testo) + `pct/calcolatori/competenza_valore.py` (doppio controllo) + bundle dei 648 uffici (`pct/uffici_giudiziari.py`) + `pct/territorio_italia.py` (regione del TAR) | norma con ancora; ufficio nominato solo se esiste |
| 8 Rito | regole | — | norma con ancora |
| 9 Procedibilità | `procedura.py` | soglia letta dal testo dell'art. 3 d.l. 132/2014; materie dall'art. 5 d.lgs. 28/2010 | norma con ancora |
| 10 Termini | `termini.py` | motore dei termini `pct/termini_processuali.py` (art. 155 c.p.c., sospensione feriale) | calcolo con evento, durata, natura |
| 11 Importi | regole | `pct/strumenti_legali.calcola_contributo_unificato` (Ferrandina); somme e differenze dai fatti | importi dei fatti |
| 12 Tranelli | regole | — | avvertenze esplicite (termine scaduto, strumento inadatto, decadenza) |
| 13 Dati mancanti | regole | — | elenco «Dato da acquisire» |
| 14 Modello d'atto | `bozze.py` | schede del catalogo (codice nel registro, esistenza verificata) | struttura dell'art. 163 c.p.c. e dei modelli |
| 15 Controllo e schema | `controllo.py`, `composizione.py` | — | un'affermazione senza ancora trovata nel testo vigente va fra i dubbi; un articolo citato che non si legge nell'archivio viene segnalato |
| Scrittore | `scrittura.py` | Ollama o server llama.cpp (`LEX_HARNESS_SCRITTORE`) | la stesura è accettata solo se norme ⊆ schema e date e importi sono identici; altrimenti resta lo schema |

Quando non c'è una regola per una domanda di termine, calcolo o norma, l'harness passa la domanda ai motori certi già
collaudati (`lex/risposte_certe.py`: impugnazioni, opposizione a decreto ingiuntivo, memorie dell'art. 171-ter,
contributo unificato, testo degli articoli). Per l'appello civile aggiunge la nota sul rito del lavoro.

## Strumenti del software NON usati, e perché

| Strumento | Perché no (ancora) |
|---|---|
| Archivio giurisprudenza (SentenzeWeb, Consulta, OpenGA) | Nella prova del 18/11 la ricerca per «caparra… diffida… doppio» non ha restituito risultati. Le pronunce indicate nelle schede (Cass. S.U. 272/1999, Corte cost. 128/2024 e 194/2018) sono segnalate come «da leggere», mai affermate |
| `pct/ragionamento` (modello della causa) e Lettura del fascicolo | L'harness lavora oggi sul testo della richiesta. Collegarlo al fascicolo (`active_context.case_id`) è il passo successivo; la direttiva del 19/11 è registrata |
| Calcolatori di interessi, usura, TFR, D.M. 55/2014 (`pct/calcolatori/*`, `strumenti_legali`) | Le regole li citano ma non li usano: il collaudo delle utility ha trovato errori (interessi con un giorno in più, TFR senza rivalutazione, usura senza soglie del 4° trimestre 2026) da correggere prima |
| `pct/calcolatori/procedibilita_adr.py` | La procedibilità si decide sul testo vigente letto dall'archivio; il doppio controllo con questo calcolatore è da aggiungere, come già fatto per la competenza |
| Guide pratiche (`pct/guida_pratica`) | Contengono voci con istituti abrogati (comportamenti/lex.md, difetto 14): usarle senza revisione introdurrebbe errori |
| Compilatore dei modelli e salvataggio PDF nel fascicolo | Le bozze dell'harness seguono la struttura dei modelli ma non passano dal compilatore. Un altro agente sta portando le bozze in PDF |

## Collaudo

- `tests/test_lex_harness_instradamento.py`: domande giuridiche riconosciute prima delle rotte operative; le domande
  operative restano tali. Misura sul corpus dei test del router (574 frasi): 2 rotte cambiate, entrambe su testi di
  appoggio dei test e non su domande.
- `tests/test_lex_harness_collaudo.py`: batteria di 47 domande (11 materie) e 22 casi dell'avvocato
  (`tests/lex_collaudo/casi_avvocato.json`), ciascuno valutato su sette criteri e sulle norme inventate.
- `tests/test_lex_harness_scrittura.py`: controllo della stesura (norma nuova, data o importo cambiati o persi,
  servizio assente).
- `tests/test_ricerca_legale_norma_citata_numeri.py`: numeri d'articolo «281-undecies», «281-terdecies»,
  «473-bis.11», «21-nonies».
- `tests/lex_collaudo/scrittori.py`: confronto degli scrittori sullo stesso banco. Attende che il carico del PC scenda
  sotto 16 prima di ogni domanda.

## Limiti dichiarati

- Le regole sono state scritte e collaudate su questi casi. Il punteggio pieno sul banco non garantisce che reggano
  su casi nuovi della stessa materia. La misura vera è il banco indipendente.
- I fatti si leggono dal testo con espressioni regolari: una formulazione molto diversa può sfuggire. In quel caso
  la regola lascia il dato «[da completare]», non lo inventa.
- Il circondario di un comune che non è sede di tribunale (per esempio Modugno) non si ricava: la tabella comune →
  circondario (d.lgs. 155/2012) manca nel software.
- L'istantanea delle norme va rigenerata con `scripts/lex_harness_norme.py` quando l'archivio si aggiorna.

## Sospensione feriale: conclusioni verificate sulle fonti (19/11/2026)

| Termine | Feriale | Fonte |
|---|---|---|
| art. 617 c.p.c. (opposizione agli atti esecutivi) | **non** si applica | art. 92 r.d. 12/1941 (testo vigente da Normattiva, allegato: «opposizione all'esecuzione»), art. 3 l. 742/1969; Cass. ord. 21568/2017, Cass. 9998/2010. Modello `LEX_ESE_OPPOSIZIONE_ATTI_617`. Il modello `ESE_OPPOSIZIONE_ATTI_617` del motore applica la feriale: discordanza da correggere nel motore. |
| art. 1137 c.c. (impugnazione della delibera) | **si** applica | Corte cost. 2 febbraio 1990 n. 49 (illegittimità dell'art. 1 l. 742/1969 nella parte in cui non si estende a questo termine). Modello `LEX_CONDOMINIO_1137`, con l'invito alla prudenza se il termine attraversa agosto. |
| art. 481 c.p.c. (efficacia del precetto) | non si applica | Prassi e dottrina concordi, ricondotto all'esecuzione forzata (art. 92 ord. giud.); nessuna sentenza di Cassazione specifica trovata con estremi verificabili. Modello `ESE_PRECETTO_EFFICACIA_90GG` (senza feriale). |
| art. 669-octies c.p.c. (inizio del merito) | **dubbio** | Nessuna pronuncia di legittimità trovata con estremi verificabili; l'art. 92 esclude i «procedimenti cautelari», non il giudizio di merito. L'harness calcola senza sospensione e segnala il dubbio se il termine attraversa agosto (`LEX_CAU_MERITO_669OCTIES`, policy `da_verificare`). |

L'archivio giurisprudenza locale non ha risposto (ricerca FTS oltre 30 minuti con carico > 30): queste conclusioni vengono dal sito della Corte costituzionale e dalle massime pubblicate. Vanno riscontrate sull'archivio quando la ricerca sarà disponibile.

## Strumenti aggiunti il 19/11

- Ufficio competente per comune: `pct/uffici_competenti.ricerca_uffici_competenti`, cioè la banca dati ministeriale con il circondario (Modugno → Tribunale di Bari).
- Contributo unificato: `GestioneStrumentiLegali.calcola_contributo_unificato` in ogni competenza per valore, più l'anticipazione forfettaria.
- Indennità di licenziamento: `calcola_indennita_licenziamento`, con il regime `jobs_act` o `piccola_impresa`.
- Ancora per comma: `norme.contiene_nel_comma`, che usa `testo_del_comma` quando i commi sono numerati.
- Errori delle regole: `payload_harness` li registra nel log e risponde «Analisi non completata» con affidabilità 0, invece di deviare in silenzio.

## Aggiornamento 20/11/2026

- **Fatti dal modello della causa** (`lex/harness/causa.py`). Quando la domanda arriva da un fascicolo, la fase dei fatti legge il modello unico della causa (`raccogli_fonti` + `ragiona`). Prende rito, ufficio, ruolo del cliente, atti, udienze, termini assegnati e prossimi passi, ciascuno con il documento e la data da cui è letto. La risposta ha una sezione «Dal fascicolo». Le domande sul fascicolo senza regola (termini, udienze, «cosa devo fare») rispondono dal modello.
- **Accesso al fascicolo** (`lex/fascicolo_accesso.py`). Il `fascicolo_id` del client si usa solo se il fascicolo è visibile all'utente: fascicolo senza cliente, oppure `cliente_visibile`. Altrimenti è vuoto per tutti i percorsi e Lex risponde «Fascicolo non accessibile».
- **Vigenza alla data dei fatti** (`norme.modifiche_dopo`). Dalle note «AGGIORNAMENTO» del testo Normattiva si leggono le decorrenze delle modifiche. Se una norma sostanziale citata è stata modificata con effetto dopo il primo fatto, la risposta lo dichiara fra i dubbi e il registro lo riporta in `4b_vigenza_alla_data_dei_fatti`. Esempio: contratto del 2021 e art. 133 cod. cons., modificato dal d.lgs. 170/2021 per i contratti dal 01/01/2022. Le norme processuali sono escluse, perché seguono la data del giudizio.
- **Registro unico** (`lex/harness/registro_norme.py`). Il registro della conoscenza procedurale (`pct/procedura_fasi/fonti.py`) e l'harness hanno 63 articoli in comune, con lo stesso URN. Il testo di riferimento è l'istantanea dell'harness. Su 38 voci l'estratto del registro procedurale non è letterale: sono sintesi unite da «;» o testo diverso (elenco in `estratti_non_letterali()`), da riallineare da chi cura quel registro.
- **Requisiti dell'atto** (`lex/procedura_atti/requisiti_atti`). Ogni bozza dell'harness è controllata sui requisiti del suo modello (art. 163 c.p.c. per la citazione, artt. 660 e 663 per lo sfratto, art. 18 d.lgs. 546/1992 per il ricorso tributario…). Le bozze del banco non hanno requisiti mancanti. Le citazioni hanno attore e convenuto, «IN FATTO» e «IN DIRITTO» e gli avvertimenti; il ricorso tributario ha i «MOTIVI».
- **Bozza nel fascicolo** (`web/services/lex_bozza_fascicolo.py`). Una richiesta di redazione fatta dentro un fascicolo accessibile, da chi ha `fascicoli.scrivi`, salva la bozza come PDF con lo stesso formato e lo stesso registro delle bozze dei passi (`pct/bozze_passi`, dal branch fix-2490-1): tag «bozza», «bozza-passo» e «bozza-lex», segnaposti «[da completare: …]» contati, nessun duplicato. Non è mai firmata, inviata, depositata né notificata.
- **Archivio giurisprudenza in sola lettura** (`pct/giurisprudenza_corpus._connect`). L'archivio è in WAL, con file di root, in una cartella non scrivibile: `mode=ro` falliva con «attempt to write a readonly database» e la ricerca FTS rendeva in silenzio zero risultati. Ora si legge come istantanea immutabile e gli errori diversi dalla sintassi FTS non si nascondono più. La lentezza osservata (oltre 25 minuti) dipende dal disco saturo: processo in stato D su `folio_wait`, carico 30-57.
