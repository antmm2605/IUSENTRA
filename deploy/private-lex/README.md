# Lex attraverso la rete privata

Il modello esistente resta su loopback 8090. Il ponte `bridge.py` può ascoltare soltanto su un indirizzo Tailscale IPv4, porta 8091. Richiede sia l'indirizzo del server autorizzato sia una chiave casuale conservata fuori dal repository. Espone solo l'elenco modelli e la generazione non streaming, con limiti di dimensione e concorrenza; non registra richieste o risposte.

`prepare-private-lex.yml` prepara soltanto Tailscale sul server, senza modificare l'applicazione. Il collegamento personale di autorizzazione viene restituito cifrato con la chiave pubblica di questa consegna. La chiave privata resta sul PC, fuori dal repository. Non usare l'invito alla rete come chiave applicativa.

`configure-private-lex.yml` riceve la chiave applicativa da un Secret GitHub e la trasmette nello standard input SSH. Verifica prima l'accesso al modello privato; solo dopo conserva un backup protetto e aggiorna atomicamente le sole variabili llama.cpp. Il riavvio applicativo resta subordinato alla CI e al deploy ordinario.

Sul PC il servizio deve essere vincolato all'IP privato e al solo peer Hetzner; prima di rimuovere shields-up devono essere installate regole di ingresso dedicate che preservino le altre interfacce. Nessuna esposizione pubblica, Tailscale SSH, exit node o Funnel è richiesta.

Le risposte vanno collaudate con casi inventati e marcate come bozze da revisionare. Questa configurazione non addestra modelli e non autorizza spegnimenti.

Il collaudo `verify_questions.py` richiede singoli frammenti (fatti o conclusioni), non atti completi: controlla importi, dato mancante e rimedio. Il checker originale dei 300 caratteri resta attivo; un frammento corretto può essere classificato bozza incompleta. Il report conserva tale stato ed esclude soltanto questo rilievo di lunghezza dal giudizio funzionale del frammento. Tutti gli altri errori della revisione restano bloccanti. Questo collaudo non è una misura indipendente della qualità giuridica e conserva prima stesura e correzione.
