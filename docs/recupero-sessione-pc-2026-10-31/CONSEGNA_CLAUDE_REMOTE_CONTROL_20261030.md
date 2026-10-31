# Consegna operativa a Claude — 30 ottobre 2026

Remote Control è collegato alla cartella `/home/antmm2605/iusentra-claude-20261029`, sessione «IUSENTRA progetto PC», con modalità permessi `default` e senza integrazione Chrome. La sessione precedente dei dataset in `/home/antmm2605/iusentra-addestramento` è stata conservata.

## Stato della copia condivisa

Il checkout era pulito prima di questo promemoria. HEAD `9be9898b2`, branch di recupero `recupero/sessione-pc-2026-10-29`: preservarne le correzioni. Non è una certificazione di release pronta. Leggere AGENTS.md; commit e push operativi soltanto su main. Confrontare con origin/main prima di integrare; non pubblicare il branch di recupero né sovrascrivere modifiche concorrenti.

La copia operativa usata da Codex è diversa: `/home/antmm2605/iusentra-openga-validazione-20261023`, main base `1c3ddceb87f9818269a0b7d6aaaa777407654849`, con lavoro2.458.1 NON committato. Non modificarla contemporaneamente senza coordinamento. La nuova immagine locale di prova2.458.1 è `sha256:05d5b705524931c186b8e2d0be10db55d7ae2d0cca9c31d7f0d376b3dc64484f`, tree `57fa52d57426ed667fc8b86b0592f9a19ae4e515`; il catalogo1320 e i nuovi filtri hanno ulteriori modifiche successive, non ancora in quell'immagine. Nessun nuovo deploy certificato.

## Evidenze già disponibili sul PC

Cartella prove: `/home/antmm2605/integrazione-ricerca-release-20261029`.
- `reader-visual-proof-245801-r6.json` riguarda il lettore impaginato; successivamente il collegamento è stato integrato nel gestore delle finestre IUSENTRA, provato visivamente sull'immagine sopra.
- `prova-notturno-immagine-245801-r6.json`: download pubblico reale1record, giro successivo0, testo80869caratteri, integritàok/0FK; non equivale a tutte le fonti o revisione giuridica.
- `audit-norme-1320-20261030.json`:1320identità,847collegate473da associare,7081collegamenti modello-articolo;130risultavano assenti dalla biblioteca locale in uso.
- `audit-norme-1320-biblioteca-preparata-20261030.json` e relativoSQLite: nella biblioteca già preparata `/mnt/iusentra-normativa-unificata-20261026/candidato/codici_leggi.sqlite`, tutti7081collegamenti risultano con testo presente. Nessuna reimportazione effettuata. Rimangono473associazioni mancanti e verifica dell'applicabilità giuridica; non dichiarare validati tutti i1320modelli.
- La sessione grafica locale è su127.0.0.1:8080. La presenza nel catalogo non è una certificazione normativa.

## Sequenza proposta dall'utente, ancora da eseguire e verificare

Le release2.460.0/2.461.0 citate nella proposta devono essere prima individuate per commit e contenuto: non si presumono presenti in questo checkout. Per ciascuna: prove locali reali, gate, commit main, CI e deploy allo stessoSHA, backup verificato e parità.
Il workflow del pacchetto di addestramento, il trasferimento, CUDA, la prova200esempi, l'addestramento e i benchmark non sono stati avviati da questa preparazione. Prima di operare verificare disponibilità e autorizzazioni dei dataset, pseudonimizzazione, GPU/VRAM, modello esatto, spazio, checkpoint e ripristino dei servizi. Non fermare il35B mentre un lavoro lo usa. Non cancellare testi o backup senza verifica del perimetro e conservazione richiesta. Non spegnere ilPC: autorizzazione revocata.
