# Lex attraverso la rete privata

Il modello esistente resta su loopback 8090. Il ponte `bridge.py` può ascoltare soltanto su un indirizzo Tailscale IPv4, porta 8091. Richiede sia l'indirizzo del server autorizzato sia una chiave casuale conservata fuori dal repository. Espone elenco modelli e generazione non streaming, oltre a proprietà del contesto, applicazione del template e conteggio dei token autenticati. Mantiene limiti di dimensione e concorrenza e non registra richieste o risposte.

`prepare-private-lex.yml` prepara soltanto Tailscale sul server, senza modificare l'applicazione. Il collegamento personale di autorizzazione viene restituito cifrato con la chiave pubblica di questa consegna. La chiave privata resta sul PC, fuori dal repository. Non usare l'invito alla rete come chiave applicativa.

`configure-private-lex.yml` riceve la chiave applicativa da un Secret GitHub e la trasmette nello standard input SSH. Verifica prima l'accesso al modello privato; solo dopo conserva un backup protetto e aggiorna atomicamente le sole variabili llama.cpp. Il riavvio applicativo resta subordinato alla CI e al deploy ordinario.

Sul PC il servizio deve essere vincolato all'IP privato e al solo peer Hetzner; prima di rimuovere shields-up devono essere installate regole di ingresso dedicate che preservino le altre interfacce. Nessuna esposizione pubblica, Tailscale SSH, exit node o Funnel è richiesta.

Le risposte vanno collaudate con casi inventati e marcate come bozze da revisionare. Questa configurazione non addestra modelli e non autorizza spegnimenti.

Il collaudo `verify_questions.py` richiede singoli frammenti (fatti o conclusioni), non atti completi: controlla importi, dato mancante e rimedio. Il checker originale dei 300 caratteri resta attivo; un frammento corretto può essere classificato bozza incompleta. Il report conserva tale stato ed esclude soltanto questo rilievo di lunghezza dal giudizio funzionale del frammento. Tutti gli altri errori della revisione restano bloccanti. Questo collaudo non è una misura indipendente della qualità giuridica e conserva prima stesura e correzione.

## Embedding e modello 35B sulla stessa GPU

Il file `ollama-cpu-with-35b.conf`, installato come
`/etc/systemd/system/ollama.service.d/zz-iusentra-lex35-cpu.conf`, mantiene
Ollama sulla CPU e su loopback 11434. Il prefisso `zz-` applica il limite
`OLLAMA_NUM_PARALLEL=1` anche dopo gli altri drop-in esistenti. Per rendere
effettivo il drop-in servono `systemctl daemon-reload` e il riavvio del solo
servizio Ollama, dopo avere verificato l'assenza di richieste attive.

Il gateway embedding già governato sulla porta Docker 11435 inoltra soltanto
le richieste di embedding consentite a Ollama: non è un secondo gateway di
stesura e non espone chat. La stesura usa il provider esplicito `llamacpp`
attraverso il ponte privato 8091. Il modello della chat generale è una
configurazione distinta: non sostituirlo per dedurre la rotta della stesura.

Il budget della stesura deve leggere il contesto effettivo da `/props` e
contare il messaggio con `/apply-template` e `/tokenize`; non assumere che il
contesto complessivo del server coincida con quello disponibile al singolo
slot. Il riscontro corrente è di 16.384 token per slot. La disponibilità del
ponte e un conteggio positivo non sostituiscono la prova di generazione con
Fonti effettivamente ricevute e lette.

### Versione del motore embedding

Le definizioni Compose locale e Hetzner fissano la stessa immagine ufficiale
Ollama 0.35.0 mediante digest del registro, oltre al digest del modello registrato
nell'indice. Il PC WSL è stato riscontrato sulla 0.35.0; l'aggiornamento del server
0.34.2 deve avvenire con il rilascio governato, conservando l'immagine precedente.
La verifica finale richiede versione effettiva, digest di EmbeddingGemma e
confronto delle query sulle due copie. Il pin non cambia il modello 9B della chat,
il provider 35B della stesura o i rispettivi checkpoint.
