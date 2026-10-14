# Controllo delle regressioni di copertura critica

La candidata viene confrontata con l'ultima versione di `main` il cui deploy Hetzner e la cui CI sono riusciti sullo stesso commit. La baseline è selezionata dai registri GitHub, non da una percentuale scelta dal chiamante, e deve appartenere alla storia della candidata.

Il workflow conserva i dodici shard critici esistenti. Un ulteriore gruppo di dodici shard misura nuovamente il codice della versione accettata in una copia CI con HEAD staccato, senza commit, push o dati degli studi. Entrambi i gruppi usano Python 3.12.15, coverage 7.16.2 e gli stessi pacchetti congelati. La versione e l'impronta delle distribuzioni installate, la configurazione di misura, il perimetro, il commit, lo shard, il tentativo e i test selezionati sono registrati negli artefatti.

`Regressioni della copertura critica` è un controllo obbligatorio aggiuntivo. Usa `coverage.CoverageData` e il reporter standard: non ripristina il precedente aggregatore né modifica le esclusioni o abbassa soglie. Ogni gruppo deve contenere esattamente dodici file distinti. Gli artefatti originali della versione accettata sono recuperati e misurati sul relativo sorgente, conservando il riferimento alla misura storica.

| Esito | Comportamento |
| --- | --- |
| Copertura preservata o migliorata | Confronto ammesso se ambiente e perimetro sono omogenei. |
| Calo della percentuale | Blocco senza tolleranza numerica; confronto tramite frazioni esatte. |
| Riga prima coperta persa nel sorgente invariato | Blocco anche se altre righe fanno crescere il totale. |
| Ambiente, configurazione o moduli misurati differenti | Confronto non omogeneo e blocco esplicito; nessuna nuova baseline accettata automaticamente. |
| Nuovi test, stesso perimetro | Variazione dei test registrata; confronto mantenuto sulle stesse istruzioni. |
| Sorgente aggiornato nello stesso modulo | Differenza indicata nel report; la percentuale resta confrontata. Le righe delle due versioni non vengono confuse. |
| Artefatto o metadato mancante, duplicato o discordante | Blocco con causa registrata. |

Il report JSON conserva i valori macchina; il report Markdown mostra percentuali e data italiane, con orario Europe/Rome. I report sono pubblicati anche quando il confronto fallisce. Il gate finale esistente e il deploy continuano ad attendere tutti i controlli obbligatori.

Le ripetizioni CI conservano gli artefatti dei tentativi precedenti. Il registro GitHub seleziona una sola misura per shard, usando il tentativo più recente disponibile; commit, ambiente e test devono coincidere. Una duplicazione ambigua viene bloccata. La baseline viene ricalcolata dalla precedente versione realmente distribuita a ogni rilascio: non resta fissata alla percentuale di una versione remota nel tempo.

La modifica è in collaudo: prove sintetiche e lettura dei dodici artefatti reali della 2.437.25 effettuate. Il lettore riproduce 27.592/33.996 istruzioni, pari all'81,1624897%. Esecuzione del nuovo percorso completo in GitHub, accettazione della copia reale sul commit finale e deploy ancora necessari; questo documento non certifica la consegna.
