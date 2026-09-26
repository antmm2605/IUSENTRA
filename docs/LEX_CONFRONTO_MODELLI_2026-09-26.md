# Confronto dei modelli locali: qwen3:4b e Spark-X2.5 4B (26/09/2026)

Le prove sono state fatte con Ollama 0.34.4 su una CPU a 2 core, a temperatura 0. I modelli erano quantizzati Q4_K_M, entrambi intorno ai 2,5 GB. Le domande sono le stesse usate in produzione. I testi sono documenti e PEC reali dello studio: restano fuori dal repository, e qui si riportano solo i risultati.

## Seconda lettura del catalogo documentale

- **Prova**: 19 documenti con la voce giusta nota (ricorsi, procure, decreti, verbali, sentenze, note scritte, memorie, contratti, autocertificazioni).
- **Domanda**: la stessa di `pct/document_intelligence/catalog_lex.py`, con voce scelta da un elenco chiuso e citazione verificata nel testo.

| | qwen3:4b | Spark-X2.5 4B |
|---|---|---|
| Voce giusta e applicata | 11 | **12** |
| Voce sbagliata e applicata | 8 | **2** |
| Risposta scartata perché la citazione non è nel testo | 0 | 5 |
| Tempo medio per documento | 177 s | **117 s** |

Qwen conferma quasi sempre una voce plausibile ma sbagliata. Per esempio:

- scambia il decreto di trattazione scritta per le note;
- scambia l'istanza di trattazione per le note;
- scambia la diffida per un'istanza.

Spark sbaglia meno. Quando non è sicuro, cita frasi che nel testo non ci sono, e il controllo della citazione scarta la risposta, così la proposta resta alle regole.

Entrambi i modelli sbagliano due casi:

- non riconoscono la sentenza di un altro ufficio come precedente;
- per l'atto di citazione il catalogo non ha una voce.

**Scelta**: Spark-X2.5 4B diventa il modello predefinito (licenza Apache 2.0). Se l'Ollama del server non esegue l'architettura `spark2_5`, la seconda lettura torna da sola a qwen3:4b. Le proposte già lette con qwen vengono rilette una volta con il nuovo modello (`da_rileggere` confronta il modello).

## Profilo processuale delle PEC

- **Prova**: 8 PEC reali:
  - comunicazione e notificazione di cancelleria;
  - accettazione e consegna di un deposito;
  - avviso di fissazione udienza del TAR;
  - nota di un Ministero;
  - consegna di una notifica ex L. 53/1994;
  - consegna di una diffida.
- **Campi valutati**: 27 (ufficio, R.G., giudice, cliente, controparte, data).

| | Campi giusti | Valori non presenti nel testo | Evento riconosciuto | Tempo |
|---|---|---|---|---|
| Regole in produzione fino alla 2.406 | 16/27 | 0 | — | istantaneo |
| **Regole 2.407.0** | **24/27** (25 con l'R.G. dell'EsitoAtto.xml) | 1 | — | istantaneo |
| qwen3:4b | 24/27 | 1 (il protocollo scambiato per R.G.) | 6/8 | 48 s |
| Spark-X2.5 4B | 22/27 | 0 | 3/8 | 35 s |

**Errori delle vecchie regole**:

- scrivevano come ufficio l'etichetta della regola («Ufficio giudiziario civile», «TAR o Consiglio di Stato»);
- non leggevano gli avvisi della Giustizia amministrativa;
- lasciavano il resistente seguito dalla formula «Si da' atto…»;
- mettevano la consegna di un deposito fra i «provvedimenti da leggere».

**Regole nuove** (`pct/pec_profilo_ufficio.py`):

- l'ufficio si legge dalla PEC della cancelleria nel registro uffici, dall'oggetto ministeriale del deposito o dal codice sede dell'avviso TAR;
- il R.G. si legge da `Comunicazione.xml`, `EsitoAtto.xml` e dal NRG dell'avviso;
- il cliente si legge dalla relata di notifica o dalla dicitura «A c/ B» dell'oggetto, sempre da verificare.

I profili già salvati si riallineano quando vengono letti.

**Scelta**: il profilo resta alle regole, che danno lo stesso risultato di qwen3:4b senza tempi di attesa e con fonti certe. Fra i due modelli è qwen3:4b a comportarsi meglio sulle PEC: riconosce meglio l'evento e non confonde l'avvocato con il cliente. Resta il candidato per una futura seconda lettura che compili solo i campi vuoti, con valore verificato nel testo.
