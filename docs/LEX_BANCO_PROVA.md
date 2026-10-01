# Banco di prova di Lex

Misura quante domande reali dell'avvocato Lex risolve correttamente sui dati dello studio. Serve a sapere
dove siamo, a verificare ogni passo del lavoro su Lex e a impedire che una correzione ne rompa un'altra.

## Cosa contiene

| File | Contenuto |
|---|---|
| `tests/lex_banco/studio.py` | Studio di esempio (dati inventati): 8 clienti, 7 fascicoli, termini, udienze |
| `tests/lex_banco/domande.json` | 46 domande con la risposta attesa e i criteri di verifica |
| `tests/lex_banco/valutazione.py` | Esecuzione dal canale del browser e valutazione |
| `tests/lex_banco/soglia.json` | Domande già risolte: non possono tornare sbagliate |
| `scripts/lex_banco_prova.py` | Esecuzione da riga di comando, tabella dell'esito, aggiornamento della soglia |
| `tests/test_lex_banco_prova.py` | Test pytest (formato delle domande, regole di valutazione, nessuna regressione) |

Lo studio riproduce le situazioni difficili: cognome e nome in ordine libero, due clienti omonimi «Mario Rossi»
distinti solo dal fascicolo, un cognome quasi uguale (Gramuglia / Gramaglia), un fascicolo importato dal
portale collegato al cliente solo per nome, un termine proposto dalla lettura di una PEC e ancora da confermare,
un termine già completato, un cliente senza fascicoli, una causa trattenuta in decisione senza udienze future,
un'udienza sostituita dal deposito di note scritte (art. 127-ter c.p.c.: la scadenza del termine per le note vale
come data dell'udienza).

Categorie delle domande: `quando`, `forma` (stessa domanda scritta in modi diversi), `conteggio`, `rg`,
`udienza`, `settimana`, `omonimi`, `assenza` (il dato non c'è e Lex deve dirlo con precisione), `fascicolo`,
`conferma` (termini proposti e non confermati).

## Come si valuta una risposta

- `deve_contenere`: tutti presenti. `data:AAAA-MM-GG` è soddisfatta dalla data in italiano («20 ottobre 2026»)
  o come «20/10/2026»; la forma ISO non vale, perché l'avvocato legge date italiane.
- `almeno_uno`: basta una delle voci (per esempio le formule con cui si dice che un dato non c'è).
- `non_deve_contenere`: nessuna presente.
- `solo`: la domanda riguarda un cliente preciso, quindi nella risposta non possono comparire né i cognomi né
  le date degli altri clienti. Un elenco indiscriminato che contiene «anche» la data giusta è una risposta sbagliata.
- `vietate_sempre`: frasi generiche che non rispondono mai alla domanda.

## Come si esegue

```bash
python scripts/lex_banco_prova.py                 # esito per domanda e per categoria
python scripts/lex_banco_prova.py --dettaglio     # anche il testo delle risposte
python scripts/lex_banco_prova.py --solo Q01,Q17  # solo alcune domande
python scripts/lex_banco_prova.py --aggiorna-soglia
```

Il gate locale (`scripts/ci_local_gate.sh`, passo «Lex banco di prova») e la CI (`tests/test_lex_banco_prova.py`)
falliscono se una domanda della soglia smette di essere risolta. Dopo un miglioramento si alza la soglia con
`--aggiorna-soglia`, che rifiuta di scriverla se c'è una regressione.

## Condizioni di misura

- Ogni domanda passa da `POST /api/assistente/chat` con lo stesso corpo che invia il widget di Lex, in una
  sessione nuova: nessuna domanda eredita il contesto della precedente.
- Data di riferimento fissa, lunedì 5 ottobre 2026 (`IUSENTRA_LEX_REFERENCE_DATE`). Una parte di Lex che usa
  l'orologio di sistema invece di questa data è un difetto.
- Modello linguistico locale escluso e rete esterna bloccata: il banco misura il percorso deterministico, da cui
  devono venire date e fatti. Il modello può solo aiutare a capire la domanda.

## Misura di partenza (30/09/2026, versione 2.434.0)

**1 domanda risolta su 46.** Difetti osservati:

- La domanda viene classificata con parole chiave in ordine fisso: «cliente» vince su «quando» e «scadenza», e le
  domande con «RG» finiscono nella ricerca di fonti ufficiali.
- Il cliente viene cercato con tutte le parole rimaste nella domanda («quando fare note scritte gramuglia caterina»),
  che non compaiono nella scheda: nessun risultato e la frase «Non ho trovato dati reali sufficienti».
- Quando i dati si trovano, la risposta è un elenco di tutte le scadenze o le udienze dello studio, con clienti
  diversi mescolati, invece della risposta alla domanda.
- Le domande «quando scade la memoria…» o «quando devo depositare la comparsa…» ricevono la regola generale o il
  modello di atto, non la data del fascicolo.
- I termini proposti dalle PEC e da confermare non vengono letti; il termine già completato non viene trovato.
- Alcune domande sui dati dello studio avviano ricerche sul web dei portali ministeriali.
- La prima domanda dopo l'avvio carica il catalogo dei modelli di atto e la guida pratica: nell'ambiente di
  misura oltre un minuto di attesa.
