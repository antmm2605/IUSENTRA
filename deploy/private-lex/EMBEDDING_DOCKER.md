# Embedding Normattiva dal Docker locale

Il PC usa lo stesso embeddinggemma:300m e digest dell’indice canonico del server. Ollama resta su 127.0.0.1:11434. Il gateway ascolta esclusivamente su 172.17.0.1:11435, accessibile dal container locale mediante `LEX_EMBED_URL=http://host.docker.internal:11435`. Non cambiare `PCT_LOCAL_AI_BASE_URL`: il gateway riguarda solo l’embedding, mai la generazione. Le sole reti ammesse sono i bridge Docker 172.17.0.0/16 e 172.18.0.0/16. Non installare questo gateway sul server: lì Ollama è già nella rete Docker privata.

Sono ammesse soltanto le API di embedding del modello, tags filtrati, versione e identità del modello. Le API chat/generate/pull e gli altri modelli sono rifiutati. Nessun URL upstream è configurabile e non vengono seguiti redirect. I testi non sono registrati. Due richieste contemporanee al massimo; body massimo 1 MiB.

Installazione locale: copiare il sorgente verificato in `/home/antmm2605/.local/lib/iusentra/embedding_docker_gateway.py`, installare l’unità allegata in `/etc/systemd/system/`, quindi `systemctl daemon-reload` e `systemctl enable --now embedding_docker_gateway.service`. L’unità gira come utente non privilegiato. Controllare dall’app container `/api/tags` e una domanda reale. L’indice e il database devono essere installati e verificati separatamente.

Ripristino: disabilitare soltanto questa unità. Non modificare né arrestare Ollama, il server 35B o Tailscale. Nessuna porta pubblica e nessun accesso Tailscale vengono aggiunti.
