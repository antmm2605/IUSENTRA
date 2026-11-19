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
