"""Conoscenza giuridica di Lex: schede di istituto per materia, viste generate dalle fonti canoniche del software.

Una scheda non è una fonte: è una VISTA ricostruibile delle regole dell'harness (norme vigenti con l'ancora letterale),
della biblioteca, dell'indice delle pronunce per norma (con il passaggio letto nel testo della pronuncia), dei modelli
d'atto e dei calcolatori. Ogni voce porta la provenienza e passa dal controllore anti-invenzione dell'harness
(``lex.harness.controllo``); le sezioni senza fonte restano dichiarate come mancanti.

- ``istituti``: tassonomia (materia → istituto → regole e norme di riferimento), ``dati/istituti.json``;
- ``generatore``: costruzione della scheda da un istituto;
- ``deposito``: record versionati con dipendenze, registro degli eventi append-only, viste ``index.md`` e ``log.md``;
- ``consultazione``: elenco, ricerca testuale senza embeddings, stato attuale (riconvalida), scheda per regola di Lex;
- ``annotazioni``: note dell'avvocato nel SQL dello studio, legate all'ID stabile della scheda;
- ``applicabile``: ``testo_applicabile(chiave, data_instaurazione)`` (testo vigente o anteriore al d.lgs. 149/2022
  secondo la decorrenza letta nella nota Normattiva; l'harness di Lex la può chiamare) e ``data_instaurazione(fatti)``.
"""
