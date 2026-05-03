# Autoresearch-lite per IUSENTRA

## Scopo

Autoresearch-lite e' un metodo di lavoro ispirato a `karpathy/autoresearch`, adattato a IUSENTRA.

Non installa training LLM.
Non usa GPU.
Non aggiunge dipendenze.
Non modifica codice prodotto in autonomia.

Il suo scopo e' disciplinare il lavoro di Codex:

```text
baseline -> modifica piccola -> verifica -> keep/discard
```

## Differenza rispetto ad autoresearch originale

Autoresearch originale:

- modifica un file di training;
- esegue training LLM;
- misura una metrica numerica;
- continua cicli autonomi.

Autoresearch-lite per IUSENTRA:

- non modifica codice senza scope;
- non esegue loop infiniti;
- non crea branch extra;
- non fa reset distruttivi;
- misura qualita' tramite test, scope, CI, dipendenze, UI/UX e regressioni;
- produce report revisionabile.

## Metriche IUSENTRA

Una modifica e' migliorativa solo se:

- rispetta il perimetro;
- non tocca file vietati;
- non aggiunge dipendenze runtime;
- non indebolisce `AGENTS.md`;
- non indebolisce CI, coverage o security workflow;
- passa i test pertinenti;
- riduce ambiguita' o rischio;
- migliora davvero il risultato richiesto dall'utente;
- se riguarda UI/UX, rispetta il design system IUSENTRA e le regole Open Design support.

## Stati esperimento

- `keep`: miglioramento valido;
- `discard`: peggiora, non migliora o aggiunge complessita' inutile;
- `crash`: comandi o test falliti;
- `scope-violation`: modificati file fuori perimetro;
- `needs-review`: utile ma richiede revisione umana.

## Regola di sicurezza

Ogni esperimento deve avere:

- obiettivo;
- baseline;
- file modificabili;
- file vietati;
- comandi di verifica;
- criteri keep/discard;
- report finale.

Nessun esperimento puo' continuare indefinitamente.
Nessun esperimento puo' creare branch extra.
Nessun esperimento puo' modificare dipendenze runtime senza autorizzazione esplicita.
