# Roadmap Legal Source Engine per Lex AI

## Fase 1

- documenti design;
- scheletro adapter;
- contratti fonte;
- registro;
- modello citazionale;
- answer policy;
- dogfood model;
- scorecard model;
- auto-populate locale controllato per registro, manoscritti, scorecard e source-card citabili;
- test;
- nessuna rete.

Stato desiderato: funzionalita spenta di default salvo attivazione locale esplicita, nessuna modifica alla produzione, nessun crawling, nessun indice generato committato.

## Fase 2

- ingestione campione Normattiva e Gazzetta Ufficiale;
- un solo atto;
- nessun crawler ampio;
- validazione citazioni fonte;
- salvataggio solo in cartella data/artifacts ignorata.

## Fase 3

- lookup esatto;
- lookup articolo;
- lookup versione a data;
- indice full-text;
- indice semantico;
- reranking.

## Fase 4

- adapter giurisprudenza;
- Corte Costituzionale;
- Cassazione;
- Giustizia Amministrativa;
- Banca Dati di Merito.

## Fase 5

- fonti UE/sovranazionali;
- EUR-Lex;
- HUDOC.

## Fase 6

- autorita/prassi;
- Agenzia Entrate;
- Garante Privacy;
- ANAC;
- AGCM.

## Fase 7

- registro tool Lex AI;
- integrazione UI IUSENTRA;
- audit log;
- permessi utente;
- workflow di conferma dell'avvocato.

## Fase 8

- aggiornamenti schedulati;
- monitoraggio fonti;
- security review di produzione;
- legal review;
- compliance review.

## Regole trasversali

- nessun test unitario deve usare rete;
- nessuna fonte viene abilitata di default;
- nessuna risposta giuridica senza citazioni;
- nessun dato cliente, fascicolo, PEC, tenant, fatturazione o utente entra negli indici delle fonti giuridiche;
- ogni ingestione futura deve essere riprendibile, auditabile, rate-limited, attribuita alla fonte e reversibile;
- ogni corpus, indice, embedding, SQLite, FAISS, HAR, cookie, token, PDF o pagina scaricata resta fuori da git.
