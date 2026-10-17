# Consultazione mirata del catalogo modelli — 17 ottobre 2026

Il catalogo React deve leggere i modelli distribuiti e quelli del solo studio
autorizzato. Non deve cercare file runtime di tutti gli studi né riscrivere
modelli, schema o indici durante una consultazione.

I modelli completi sono conservati nel repository SQL nativo, nello snapshot
`template_runtime_state`. HTML, campi, date e metadati aggiuntivi rimangono
distinti dalla proiezione normalizzata. I modelli personali dell'editor e le
relative risorse continuano a essere preservati dal blocco nativo del repository.

`tools.prepare_template_catalog` usa il registro e i percorsi proprietari senza
avviare il runtime web. La prima adozione richiede scrittori fermi e backup
verificato del database esistente e del JSON storico. Il deploy controlla prima
gli studi; soltanto se necessario arresta app e worker e prepara i cataloghi
prima di attivare la candidata. Errori e snapshot discordanti fermano il passaggio.
Il riscontro della revisione proiettata impedisce di confondere uno snapshot
salvato con una preparazione terminata.

La creazione prepara il catalogo locale del nuovo studio. L'attivazione del
backend PostgreSQL prepara il catalogo dopo la connessione verificata. Le
scritture confrontano la revisione letta con quella SQL corrente: una versione
obsoleta non sostituisce né il modello né l'indice più recente.

Le prove sono registrate nelle fasi core e coverage-critical, con SQLite e
PostgreSQL controllati. Comprendono backup e ripresa, dati non validi,
formattazione, metadati, isolamento, sola lettura e concorrenza. Questo intervento
non dimostra velocità globale dell'applicativo: il perimetro è il catalogo React
e la lettura dei modelli. L'inventario amministrativo esplicito rimane distinto.

La verifica visiva dell'agente resta non eseguita; l'utente ha assunto il controllo
dell'interfaccia e autorizzato commit e deploy nonostante il blocco del browser.
