# IUSENTRA 2.480.2 — catena notturna completa per ogni fascicolo (04/11/2026)

La prova end-to-end (PEC di cancelleria con sentenza in .zip, anche scansionata, attraverso tutta la catena con il
semaforo vero) ha fatto emergere otto rotture, ora corrette con test (`tests/test_catena_notturna_fascicolo_completo.py`):

- con più studi i documenti salvati dalle PEC finivano nel registro sbagliato e non venivano letti;
- il recupero PEC girava a vuoto 40 minuti; le letture si chiudevano quando le due letture contemporanee erano occupate;
- l'ufficio della sentenza letto con «Repubblica italiana» impediva la definizione automatica;
- nello studio unico le letture in sfondo fallivano sulle discordanze;
- riletture e verifiche periodiche partivano solo tra 00 e 05; il catalogo Lex faceva un solo giro a notte;
- sentenza scansionata: secondo passaggio «attesa OCR + letture» nella fase 4 e testo OCR visibile alla proposta;
- un errore del controllo economico della sentenza non ferma più la lettura del fascicolo (resta nel registro).
