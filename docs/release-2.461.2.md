# 2.461.2 — corpus pubblico e ricerca diretta locale

La configurazione del corpus SentenzeWeb passa esplicitamente attraverso Compose e Portainer a applicazione, scheduler e OCR. Il corpus verificato resta preservato; l’attivazione richiede verifica runtime e prova reale.

La richiesta diretta di un articolo già presente con testo nativo verificato e identità corrispondente evita il fallback web. Le richieste di testo vigente e le ricerche più ampie conservano la verifica esterna. Nessuna nuova validazione giuridica viene attestata.

Prove mirate locali: 49 test ricerca e 17 test Portainer passati. Nuova immagine, prove visive, gate completo, CI e deploy ancora da completare.

Risultati interessi: etichette italiane, date gg/mm/aaaa, importi EUR con separatore migliaia e due decimali, tassi percentuali e dettaglio periodi formattati. Payload e aritmetica invariati. Sei test JS del catalogo utility passati.

La consultazione delle fonti già importate è collegata al corpus SQL nativo dello studio: ricerca per fonte, lettura interna del testo e PDF conservati con integrità SHA e streaming. Letture autenticate e autorizzate, nessuna migrazione o acquisizione durante la consultazione. Le revisioni includono corpus e WAL locali senza riletture documentali. Il lettore Cassazione impagina anche titoli uniti dall'OCR e lunghi blocchi preservando tutti i caratteri non bianchi della fonte.

77test integrati e build/typecheck frontend passati. Le prove visive della nuova immagine e il gate finale restano richiesti; il precedente gate R4 è verde sul suo albero precedente. La release non dichiara recuperati tutti gli archivi esterni né giuridicamente validate le1320voci: fonti protette, popolamento storico/incrementale e473associazioni normative hanno verifiche ancora aperte.


### 31 ottobre — lettore PDF e traduzione locale, candidata R6 in preparazione
R5 gate:42controlli passati3falliti per registry/routing e inventario/piano test generati; supervisore non ha finalizzato il proprio stato ma log conclusivo e assenza del gate riscontrati, codice exit non ricostruito. Rigenerazione con i generatori proprietari effettuata, nuova verifica necessaria.
Nuovo lettore PDF delle sole rotte corpus riusa il renderer a pagine condiviso: il PDF nativo rimane scaricabile byte per byte, permessi/SHA/Range preservati. Nessuna modifica ai flussi PEC/firma/deposito; confronto52percorsi precedenti senza differenze. Traduzione esplicita locale Hy-MT2-7B Q4_K_M Apache2.0 e llama.cppb12020, modelli/binari ufficiali con SHA verificati. OPUS-MT/M2M100/profilo1.8B comparati e scartati per omissioni o alterazioni osservate; non implica graduatoria universale. Riferimenti formali protetti, ricevute e segmenti SQL nello stesso proprietario corpus, originali preservati, cache per versione, ripresa esplicita e UI italiano/originale affiancati.75test integrati passati, buildReact/TypeScript passati; nuova immagine, test visivi reali, attivazione del worker e gate completo ancora necessari. Prova integrale sul CURIA pubblico in corso, nessuna equivalenza giuridica attestata. LauncherCPU verifica61file del runtime eGGUF, containerRO/senza rete/solo socket privato; verifica reale dell'intero modello ecompatibilità binario nell'immagineR5 riuscite, NON prova dell'inferenzaCPU o del servizio finale. I dati normativi non vengono reimportati.473associazioni e copertura/fonti/notturni rimangono aperti. Nessun commit/push/deploy2.461.2 e nessuno spegnimento.
