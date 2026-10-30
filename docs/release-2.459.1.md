# 2.459.1 — Lettura Cassazione e recupero tracciato

Il lettore SentenzeWeb presenta il provvedimento con paragrafi, sezioni navigabili, dati del deposito, provenienza e impronte. Le trascrizioni recuperate conservano HTML e testo originali; la presentazione controlla hash e corrispondenza con il testo SQL prima di mostrarle. Il testo semplice resta disponibile con `?format=txt`; nessuna lettura esterna avviene nella pagina.

Il classificatore condiviso distingue avvisi di oscuramento da contenuto della decisione, senza dichiarare completo o professionalmente approvato un testo dalla sola presenza. Il recupero pubblico usa identità congiunta, fonte e digest, varianti aggiunte senza sostituire gli ID originali e ricevute SQL. La coda si alimenta dagli eventi del collettore, conserva i tentativi invariati e usa lotti limitati sotto lo stesso lock. Il job notturno esegue prima il delta ufficiale e poi un lotto di recuperi pendenti. Nessuna sintesi viene promossa a testo della sentenza.

Corretto anche il test della cache normativa: la fixture chiude esplicitamente la connessione SQLite dopo il commit, evitando un checkpoint WAL al garbage collector che cambiava la revisione durante l'asserzione. Il confronto storico Lex risolve anche il commit autentico upstream 2.435.0 acquisito in checkout shallow, mantenendo invariata l'implementazione storica confrontata.

Prove locali mirate, recuperi reali e ricevute sono nella cartella esterna integrazione-ricerca-release-20261029. Gate integrale aggiornato, nuova immagine, prove visive, commit/push/CI e deploy restano condizioni di rilascio: questa nota non ne attesta il completamento. Recupero integrale di tutte le fonti e revisione professionale di ogni decisione restano aperti. Nessuna modifica a dati degli studi o flussi di firma/deposito/PEC; nessuno spegnimento.


Il lettore delle fonti è collegato al gestore condiviso delle finestre dell'applicazione: i link SentenzeWeb salvati rientrano nella shell e aprono il documento incorporato, conservando l'ancora. La navigazione dei collegamenti alle fonti usa il lettore interno; è stata rimossa l'eccezione che apriva le fonti normative fuori dal lettore. Origine, login e separazione dei percorsi operativi restano controllati.

La pagina Norme dei modelli usa ora le1320identità del catalogo unificato invece delle sole195schede di riferimenti. Collega soltanto le associazioni esplicite dichiarate nelle schede:847voci collegate,473ancora da associare, senza trasformare il compilatore generico in prova di applicabilità. Ricerca testuale locale indicizzata sui metadati e riferimenti disponibili, filtri combinabili per materia/tipo/provenienza/stato e paginazione24voci. Le approvazioni sono distinte per identità del modello e studio.

Audit tecnico delle1320voci:7081collegamenti modello-articolo associati. Nella biblioteca locale precedente130collegamenti rimandavano a9atti non presenti; nella biblioteca già preparata suM tutti7081risultano con testo presente. Lettura sola, nessuna reimportazione o approvazione. Il collegamento della biblioteca completa al runtime, le473associazioni e la revisione di esattezza/applicabilità normativa sono ancora attività da completare: questi risultati non attestano correttezza giuridica globale.

Integrata la base main2.459.0 SHA68ca227e senza perdere le correzioni remote; archivio pubblico/stash e file privato preservati. La nuova patch adotta2.459.1 e richiede nuova candidata e gate sull’intero codice integrato.
