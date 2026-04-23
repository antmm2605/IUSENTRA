# Perché questo blocco è coerente con i tuoi file reali

- `local_signer.py` è già un server locale grande che gestisce AI, firma e portali telematici nello stesso file.
- Il dispatcher POST include blocchi AI chiaramente separabili.
- `local_ai_host_bridge.py` ha già un client Ollama e bootstrap runtime riusabili.
- `lex_document_context.py` è già modulare e può restare importato senza toccarlo.

Questo pacchetto evita una riscrittura pericolosa e prepara il refactor serio in 2 fasi.
